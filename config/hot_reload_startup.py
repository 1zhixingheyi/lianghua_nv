#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置热重载启动器

负责在应用程序启动时初始化和启动配置热重载服务，
为量化交易系统提供配置热更新能力。

功能：
1. 应用程序启动时自动初始化热重载服务
2. 提供热重载服务的生命周期管理
3. 集成到量化交易系统的各个模块
4. 提供配置热重载的统一入口

作者: 量化交易系统
日期: 2025-01-18
版本: 1.0.0
"""

import asyncio
import atexit
import logging
import signal
import sys
from typing import Optional

from .hot_reload_service import HotReloadService, get_hot_reload_service
from .config_manager import get_config_manager


class HotReloadStartup:
    """配置热重载启动器"""
    
    def __init__(self):
        """初始化启动器"""
        self.logger = logging.getLogger(__name__)
        self.service: Optional[HotReloadService] = None
        self._shutdown_handlers_registered = False
        
    async def initialize(self) -> HotReloadService:
        """初始化热重载服务
        
        Returns:
            HotReloadService: 热重载服务实例
        """
        try:
            self.logger.info("正在初始化配置热重载服务...")
            
            # 获取服务实例
            self.service = get_hot_reload_service()
            
            # 启动服务
            await self.service.start()
            
            # 注册关闭处理器
            self._register_shutdown_handlers()
            
            self.logger.info("配置热重载服务初始化完成")
            return self.service
            
        except Exception as e:
            self.logger.error(f"初始化配置热重载服务失败: {e}")
            raise
            
    def _register_shutdown_handlers(self):
        """注册关闭处理器"""
        if self._shutdown_handlers_registered:
            return
            
        # 注册atexit处理器
        atexit.register(self._sync_shutdown)
        
        # 注册信号处理器
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, self._signal_handler)
        if hasattr(signal, 'SIGINT'):
            signal.signal(signal.SIGINT, self._signal_handler)
            
        self._shutdown_handlers_registered = True
        self.logger.debug("关闭处理器注册完成")
        
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        self.logger.info(f"接收到信号 {signum}，正在关闭热重载服务...")
        self._sync_shutdown()
        sys.exit(0)
        
    def _sync_shutdown(self):
        """同步关闭处理"""
        if self.service and self.service.is_running:
            try:
                # 创建新的事件循环来执行异步关闭
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.service.stop())
                loop.close()
                self.logger.info("配置热重载服务已关闭")
            except Exception as e:
                self.logger.error(f"关闭配置热重载服务时出错: {e}")
                
    async def shutdown(self):
        """异步关闭服务"""
        if self.service and self.service.is_running:
            try:
                await self.service.stop()
                self.logger.info("配置热重载服务已关闭")
            except Exception as e:
                self.logger.error(f"关闭配置热重载服务时出错: {e}")


# 全局启动器实例
_startup_instance: Optional[HotReloadStartup] = None

def get_hot_reload_startup() -> HotReloadStartup:
    """获取热重载启动器单例实例"""
    global _startup_instance
    if _startup_instance is None:
        _startup_instance = HotReloadStartup()
    return _startup_instance


async def initialize_hot_reload() -> HotReloadService:
    """初始化热重载服务的便捷函数
    
    Returns:
        HotReloadService: 热重载服务实例
    """
    startup = get_hot_reload_startup()
    return await startup.initialize()


async def shutdown_hot_reload():
    """关闭热重载服务的便捷函数"""
    startup = get_hot_reload_startup()
    await startup.shutdown()


# Flask应用集成辅助函数
def init_hot_reload_for_flask(app):
    """为Flask应用初始化热重载功能
    
    Args:
        app: Flask应用实例
    """
    @app.before_first_request
    def setup_hot_reload():
        """Flask应用首次请求前设置热重载"""
        try:
            # 在后台任务中初始化热重载
            asyncio.create_task(initialize_hot_reload())
            app.logger.info("Flask应用热重载功能已启用")
        except Exception as e:
            app.logger.error(f"Flask应用热重载功能初始化失败: {e}")
            
    @app.teardown_appcontext
    def cleanup_hot_reload(exception):
        """Flask应用上下文清理时的热重载清理"""
        if exception:
            app.logger.warning(f"Flask应用异常，热重载服务可能受影响: {exception}")


# 策略管理器集成辅助函数
def init_hot_reload_for_strategy_manager(strategy_manager):
    """为策略管理器初始化热重载功能
    
    Args:
        strategy_manager: 策略管理器实例
    """
    async def on_trading_config_changed(config_key: str, config_data: dict, version: str):
        """交易配置变更回调"""
        if hasattr(strategy_manager, 'reload_config'):
            try:
                await strategy_manager.reload_config(config_data)
                logging.info(f"策略管理器配置已更新: {version}")
            except Exception as e:
                logging.error(f"更新策略管理器配置失败: {e}")
                
    # 获取热重载服务并添加监听器
    service = get_hot_reload_service()
    service.add_change_listener(on_trading_config_changed)
    
    logging.info("策略管理器热重载功能已启用")


# 风控系统集成辅助函数
def init_hot_reload_for_risk_engine(risk_engine):
    """为风控引擎初始化热重载功能
    
    Args:
        risk_engine: 风控引擎实例
    """
    try:
        from .hot_reload_service import get_hot_reload_service
        
        # 获取热重载服务
        service = get_hot_reload_service()
        
        # 创建风控引擎配置处理器
        async def risk_config_handler(config_data: dict):
            """风控配置变更处理器"""
            try:
                await risk_engine.update_risk_parameters(config_data)
                logging.info("风控引擎配置已重新加载")
            except Exception as e:
                logging.error(f"风控引擎配置重新加载失败: {e}")
                raise
        
        # 注册处理器
        service.register_component_handler('risk_management', risk_config_handler)
        service.register_component_handler('risk', risk_config_handler)
        service.register_component_handler('trading', risk_config_handler)
        service.register_component_handler('execution', risk_config_handler)
        
        logging.info("风控引擎热重载功能初始化完成")
        
    except ImportError as e:
        logging.warning(f"热重载模块不可用: {e}")
    except Exception as e:
        logging.error(f"风控引擎热重载功能初始化失败: {e}")
        raise


# 数据库连接池集成辅助函数
def init_hot_reload_for_database(database_manager):
    """为数据库管理器初始化热重载功能
    
    Args:
        database_manager: 数据库管理器实例
    """
    async def on_database_config_changed(config_key: str, config_data: dict, version: str):
        """数据库配置变更回调"""
        if hasattr(database_manager, 'reload_connections'):
            try:
                await database_manager.reload_connections(config_data)
                logging.info(f"数据库连接池已更新: {version}")
            except Exception as e:
                logging.error(f"更新数据库连接池失败: {e}")
                
    # 获取热重载服务并添加监听器
    service = get_hot_reload_service()
    service.add_change_listener(on_database_config_changed)
    
    logging.info("数据库管理器热重载功能已启用")


if __name__ == "__main__":
    import logging
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def main():
        """测试热重载启动器"""
        try:
            # 初始化热重载服务
            service = await initialize_hot_reload()
            
            # 运行一段时间
            print("热重载服务运行中，按Ctrl+C停止...")
            print("统计信息:", service.get_statistics())
            print("健康状态:", await service.health_check())
            
            # 等待中断信号
            await asyncio.sleep(300)  # 运行5分钟
            
        except KeyboardInterrupt:
            print("\n接收到中断信号，正在关闭...")
        finally:
            await shutdown_hot_reload()
            print("热重载服务已关闭")
            
    asyncio.run(main())