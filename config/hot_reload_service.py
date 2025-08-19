#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置热重载集成服务

负责将热重载管理器与现有配置管理器集成，
为量化交易系统提供统一的配置热更新服务。

功能：
1. 集成热重载管理器与配置管理器
2. 提供统一的配置变更通知接口
3. 支持组件级配置更新
4. 提供配置版本管理
5. 支持配置回滚和恢复

作者: 量化交易系统
日期: 2025-01-18
版本: 1.0.0
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from .config_manager import get_config_manager, ConfigManager
from .hot_reload_manager import (
    HotReloadManager, 
    HotReloadConfig, 
    ComponentConfigHandler,
    ConfigChange,
    get_hot_reload_manager
)


class HotReloadService:
    """配置热重载集成服务"""
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """初始化热重载服务
        
        Args:
            config_manager: 配置管理器实例，如果为None则使用全局实例
        """
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager or get_config_manager()
        
        # 创建热重载配置
        self.hot_reload_config = self._create_hot_reload_config()
        
        # 初始化热重载管理器
        self.hot_reload_manager = get_hot_reload_manager(self.hot_reload_config)
        
        # 注册组件处理器
        self.component_handlers: Dict[str, ComponentConfigHandler] = {}
        
        # 配置变更监听器
        self.change_listeners: List[Callable] = []
        
        # 运行状态
        self.is_running = False
        
        # 初始化
        self._setup_integration()
        
    def _create_hot_reload_config(self) -> HotReloadConfig:
        """创建热重载配置"""
        config_dir = self.config_manager.config_dir
        
        return HotReloadConfig(
            watch_directories=[
                str(config_dir / "schemas"),
                str(config_dir / "modules"),
            ],
            watch_files=[
                str(config_dir / "hot_reload.yaml"),
            ],
            file_patterns=["*.json", "*.yaml", "*.yml"],
            auto_reload=True,
            backup_count=20,
            validation_timeout=30.0,
            rollback_timeout=300.0,
            change_detection_interval=1.0,
            enable_version_control=True,
            enable_change_validation=True
        )
        
    def _setup_integration(self):
        """设置集成"""
        # 注册全局配置变更回调
        self.hot_reload_manager.add_global_change_callback(self._on_config_changed)
        
        # 注册配置验证回调
        self.hot_reload_manager.add_validation_callback(self._validate_config_change)
        
        # 注册系统组件
        self._register_system_components()
        
        self.logger.info("配置热重载服务集成完成")
        
    def _register_system_components(self):
        """注册系统组件"""
        # 数据库组件
        database_handler = self.hot_reload_manager.register_component("database")
        database_handler.add_change_callback(self._on_database_config_changed)
        self.component_handlers["database"] = database_handler
        
        # 存储组件
        storage_handler = self.hot_reload_manager.register_component("storage")
        storage_handler.add_change_callback(self._on_storage_config_changed)
        self.component_handlers["storage"] = storage_handler
        
        # 交易组件
        trading_handler = self.hot_reload_manager.register_component("trading")
        trading_handler.add_change_callback(self._on_trading_config_changed)
        self.component_handlers["trading"] = trading_handler
        
        # 风控组件
        risk_handler = self.hot_reload_manager.register_component("risk")
        risk_handler.add_change_callback(self._on_risk_config_changed)
        self.component_handlers["risk"] = risk_handler
        
        # 监控组件
        monitoring_handler = self.hot_reload_manager.register_component("monitoring")
        monitoring_handler.add_change_callback(self._on_monitoring_config_changed)
        self.component_handlers["monitoring"] = monitoring_handler
        
        self.logger.info(f"注册了 {len(self.component_handlers)} 个系统组件")
        
    async def start(self):
        """启动热重载服务"""
        if self.is_running:
            self.logger.warning("配置热重载服务已在运行")
            return
            
        try:
            # 启动热重载管理器
            await self.hot_reload_manager.start_monitoring()
            
            self.is_running = True
            self.logger.info("配置热重载服务启动成功")
            
        except Exception as e:
            self.logger.error(f"启动配置热重载服务失败: {e}")
            raise
            
    async def stop(self):
        """停止热重载服务"""
        if not self.is_running:
            return
            
        try:
            # 停止热重载管理器
            await self.hot_reload_manager.stop_monitoring()
            
            self.is_running = False
            self.logger.info("配置热重载服务已停止")
            
        except Exception as e:
            self.logger.error(f"停止配置热重载服务失败: {e}")
            
    def add_change_listener(self, listener: Callable):
        """添加配置变更监听器
        
        Args:
            listener: 监听器回调函数
        """
        self.change_listeners.append(listener)
        
    def remove_change_listener(self, listener: Callable):
        """移除配置变更监听器
        
        Args:
            listener: 监听器回调函数
        """
        if listener in self.change_listeners:
            self.change_listeners.remove(listener)
            
    async def _on_config_changed(self, config_key: str, config_data: Dict[str, Any], version: str):
        """配置变更处理"""
        try:
            self.logger.info(f"配置变更: {config_key} -> 版本 {version}")
            
            # 更新配置管理器
            await self._update_config_manager(config_key, config_data)
            
            # 通知监听器
            for listener in self.change_listeners:
                try:
                    if asyncio.iscoroutinefunction(listener):
                        await listener(config_key, config_data, version)
                    else:
                        listener(config_key, config_data, version)
                except Exception as e:
                    self.logger.error(f"配置变更监听器执行失败: {e}")
                    
        except Exception as e:
            self.logger.error(f"处理配置变更失败: {e}")
            
    async def _validate_config_change(self, file_path: str, config_data: Dict[str, Any]) -> bool:
        """验证配置变更"""
        try:
            self.logger.debug(f"验证配置文件: {file_path}")
            
            # 基本格式验证
            if not isinstance(config_data, dict):
                self.logger.error(f"配置文件格式无效: {file_path}")
                return False
                
            # 根据文件类型进行特定验证
            config_key = self._get_config_key_from_path(file_path)
            
            if config_key == "mysql" or config_key == "database":
                return self._validate_database_config(config_data)
            elif config_key == "trading":
                return self._validate_trading_config(config_data)
            elif config_key == "system":
                return self._validate_system_config(config_data)
                
            return True
            
        except Exception as e:
            self.logger.error(f"配置验证失败: {e}")
            return False
            
    def _validate_database_config(self, config_data: Dict[str, Any]) -> bool:
        """验证数据库配置"""
        # 检查必要的数据库连接参数
        if "host" in config_data:
            if not config_data["host"]:
                self.logger.error("数据库主机地址不能为空")
                return False
                
        if "port" in config_data:
            port = config_data["port"]
            if not isinstance(port, int) or port <= 0 or port > 65535:
                self.logger.error(f"数据库端口无效: {port}")
                return False
                
        return True
        
    def _validate_trading_config(self, config_data: Dict[str, Any]) -> bool:
        """验证交易配置"""
        # 检查风险参数
        if "risk_management" in config_data:
            risk_config = config_data["risk_management"]
            if "max_position_size" in risk_config:
                max_pos = risk_config["max_position_size"]
                if not isinstance(max_pos, (int, float)) or max_pos <= 0:
                    self.logger.error(f"最大持仓大小配置无效: {max_pos}")
                    return False
                    
        return True
        
    def _validate_system_config(self, config_data: Dict[str, Any]) -> bool:
        """验证系统配置"""
        # 检查项目名称
        if "project_name" in config_data:
            if not config_data["project_name"]:
                self.logger.error("项目名称不能为空")
                return False
                
        return True
        
    async def _update_config_manager(self, config_key: str, config_data: Dict[str, Any]):
        """更新配置管理器"""
        try:
            # 更新配置缓存
            with self.config_manager._cache_lock:
                self.config_manager._config_cache[config_key] = config_data
                
            self.logger.debug(f"配置管理器已更新: {config_key}")
            
        except Exception as e:
            self.logger.error(f"更新配置管理器失败: {e}")
            
    def _get_config_key_from_path(self, file_path: str) -> str:
        """从文件路径获取配置键"""
        return os.path.splitext(os.path.basename(file_path))[0]
        
    # 组件配置变更回调
    async def _on_database_config_changed(self, change: ConfigChange):
        """数据库配置变更处理"""
        self.logger.info(f"数据库配置变更: {change.key} = {change.new_value}")
        # 这里可以添加数据库连接池重新初始化等逻辑
        
    async def _on_storage_config_changed(self, change: ConfigChange):
        """存储配置变更处理"""
        self.logger.info(f"存储配置变更: {change.key} = {change.new_value}")
        # 这里可以添加存储客户端重新初始化等逻辑
        
    async def _on_trading_config_changed(self, change: ConfigChange):
        """交易配置变更处理"""
        self.logger.info(f"交易配置变更: {change.key} = {change.new_value}")
        # 这里可以添加交易参数更新通知等逻辑
        
    async def _on_risk_config_changed(self, change: ConfigChange):
        """风控配置变更处理"""
        self.logger.info(f"风控配置变更: {change.key} = {change.new_value}")
        # 这里可以添加风控参数实时更新等逻辑
        
    async def _on_monitoring_config_changed(self, change: ConfigChange):
        """监控配置变更处理"""
        self.logger.info(f"监控配置变更: {change.key} = {change.new_value}")
        # 这里可以添加监控阈值更新等逻辑
        
    def get_component_config(self, component_name: str, key: str, default: Any = None) -> Any:
        """获取组件配置值
        
        Args:
            component_name: 组件名称
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        if component_name in self.component_handlers:
            return self.component_handlers[component_name].get_config(key, default)
        return default
        
    def set_component_config(self, component_name: str, key: str, value: Any) -> bool:
        """设置组件配置值
        
        Args:
            component_name: 组件名称
            key: 配置键
            value: 配置值
            
        Returns:
            是否设置成功
        """
        if component_name in self.component_handlers:
            self.component_handlers[component_name].set_config(key, value)
            return True
        return False
        
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        base_stats = self.hot_reload_manager.get_statistics()
        
        return {
            **base_stats,
            "service_status": "running" if self.is_running else "stopped",
            "registered_components": len(self.component_handlers),
            "change_listeners": len(self.change_listeners),
        }
        
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        base_health = await self.hot_reload_manager.health_check()
        
        return {
            **base_health,
            "service_running": self.is_running,
            "config_manager_available": self.config_manager is not None,
            "components_registered": len(self.component_handlers) > 0,
        }


# 全局热重载服务实例
_hot_reload_service_instance: Optional[HotReloadService] = None

def get_hot_reload_service(config_manager: Optional[ConfigManager] = None) -> HotReloadService:
    """获取热重载服务单例实例"""
    global _hot_reload_service_instance
    if _hot_reload_service_instance is None:
        _hot_reload_service_instance = HotReloadService(config_manager)
    return _hot_reload_service_instance


if __name__ == "__main__":
    import asyncio
    
    async def config_change_listener(config_key: str, config_data: Dict[str, Any], version: str):
        print(f"监听到配置变更: {config_key} -> 版本 {version}")
        
    async def main():
        # 创建热重载服务
        service = HotReloadService()
        service.add_change_listener(config_change_listener)
        
        # 启动服务
        await service.start()
        
        try:
            print("热重载服务运行中...")
            print("统计信息:", service.get_statistics())
            print("健康检查:", await service.health_check())
            
            # 运行一段时间
            await asyncio.sleep(60)
            
        finally:
            await service.stop()
            
    asyncio.run(main())