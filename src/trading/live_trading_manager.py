"""
实盘交易管理器

统一管理实盘交易的所有组件和流程
"""

import asyncio
import logging
import threading
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from .live_qmt_interface import LiveQMTInterface
from .trade_executor import TradeExecutor
from ..data.realtime_data_stream import RealtimeDataStream, SubscriptionRequest, DataType
from ..risk.risk_engine import RiskEngine
from ..strategies.strategy_manager import StrategyManager
from ..monitor.realtime_monitor import RealtimeMonitor
from config.config_manager import get_config_manager

class TradingState(Enum):
    """交易状态"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"

@dataclass
class TradingStatus:
    """交易状态信息"""
    state: TradingState
    start_time: Optional[datetime] = None
    last_update: Optional[datetime] = None
    error_message: Optional[str] = None
    daily_pnl: float = 0.0
    total_trades: int = 0
    active_positions: int = 0

class LiveTradingManager:
    """
    实盘交易管理器
    
    统一管理和协调所有实盘交易组件
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化实盘交易管理器
        
        Args:
            config: 配置参数
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 配置管理
        self.config_manager = get_config_manager()
        self.config = config or self.config_manager.get_config('live_trading', {})
        
        # 交易状态
        self.status = TradingStatus(state=TradingState.STOPPED)
        
        # 核心组件
        self.trading_interface: Optional[LiveQMTInterface] = None
        self.data_stream: Optional[RealtimeDataStream] = None
        self.risk_engine: Optional[RiskEngine] = None
        self.strategy_manager: Optional[StrategyManager] = None
        self.trade_executor: Optional[TradeExecutor] = None
        self.monitor: Optional[RealtimeMonitor] = None
        
        # 事件循环和线程
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        self.main_thread: Optional[threading.Thread] = None
        self.running = False
        
        # 回调函数
        self.status_callbacks: List[Callable] = []
        self.trade_callbacks: List[Callable] = []
        self.error_callbacks: List[Callable] = []
        
        # 性能统计
        self.stats = {
            'start_time': None,
            'total_runtime_seconds': 0,
            'trades_executed': 0,
            'trades_successful': 0,
            'trades_failed': 0,
            'orders_submitted': 0,
            'orders_filled': 0,
            'orders_cancelled': 0,
            'average_execution_time_ms': 0.0,
            'data_messages_processed': 0,
            'risk_checks_performed': 0,
            'risk_violations': 0
        }
        
        # 初始化组件
        self._initialize_components()
        
    def _initialize_components(self):
        """初始化所有组件"""
        try:
            self.logger.info("初始化实盘交易组件...")
            
            # 检查实盘交易开关
            if not self._check_trading_enabled():
                raise RuntimeError("实盘交易未启用，请检查配置")
            
            # 初始化交易接口
            broker_config = self.config.get('brokers', {})
            if broker_config.get('qmt', {}).get('enabled', False):
                self.trading_interface = LiveQMTInterface(broker_config.get('qmt', {}))
            else:
                raise RuntimeError("未找到可用的交易接口")
            
            # 初始化数据流
            data_config = self.config.get('realtime_data', {})
            self.data_stream = RealtimeDataStream(data_config.get('stream_config', {}))
            
            # 初始化风控引擎
            risk_config = self.config.get('live_risk_management', {})
            initial_capital = self.config.get('testing', {}).get('paper_trading', {}).get('initial_capital', 1000000.0)
            self.risk_engine = RiskEngine(initial_capital)
            
            # 初始化策略管理器
            self.strategy_manager = StrategyManager()
            
            # 初始化交易执行器
            # 注意：这里需要导入实际的OrderManager和PortfolioTracker
            # 由于这些组件在原代码中被引用但未找到实现，我们先创建占位符
            self.trade_executor = None  # 需要实际的OrderManager和PortfolioTracker
            
            # 初始化监控组件
            monitor_config = self.config.get('live_monitoring', {})
            # self.monitor = RealtimeMonitor(monitor_config)  # 需要实际的监控组件
            
            self.logger.info("实盘交易组件初始化完成")
            
        except Exception as e:
            self.logger.error(f"组件初始化失败: {e}")
            self.status.state = TradingState.ERROR
            self.status.error_message = str(e)
            raise
    
    def _check_trading_enabled(self) -> bool:
        """检查实盘交易是否启用"""
        trading_mode = self.config.get('trading_mode', {})
        
        # 检查总开关
        if not trading_mode.get('enabled', False):
            self.logger.error("实盘交易总开关未启用")
            return False
        
        # 检查二次确认
        if not trading_mode.get('confirm_live_trading', False):
            self.logger.error("实盘交易未经二次确认")
            return False
        
        # 检查紧急停止
        if trading_mode.get('emergency_stop', False):
            self.logger.error("实盘交易处于紧急停止状态")
            return False
        
        # 检查环境
        environment = trading_mode.get('environment', 'test')
        if environment not in ['test', 'staging', 'production']:
            self.logger.error(f"无效的交易环境: {environment}")
            return False
        
        return True
    
    async def start_trading(self):
        """启动实盘交易"""
        try:
            if self.status.state != TradingState.STOPPED:
                raise RuntimeError(f"无法启动交易，当前状态: {self.status.state}")
            
            self.logger.info("启动实盘交易...")
            self.status.state = TradingState.STARTING
            self.status.start_time = datetime.now()
            self.status.error_message = None
            self.stats['start_time'] = datetime.now()
            
            # 连接交易接口
            if not self.trading_interface.connect():
                raise RuntimeError("交易接口连接失败")
            
            # 启用交易功能
            if not self.trading_interface.enable_trading():
                raise RuntimeError("启用交易功能失败")
            
            # 启动数据流
            await self.data_stream.start()
            
            # 启动风控监控
            self.risk_engine.start_monitoring()
            
            # 设置数据回调
            self.data_stream.add_data_callback(self._on_market_data)
            
            # 启动策略
            await self._start_strategies()
            
            # 启动监控任务
            asyncio.create_task(self._monitoring_task())
            asyncio.create_task(self._statistics_task())
            asyncio.create_task(self._heartbeat_task())
            
            self.running = True
            self.status.state = TradingState.RUNNING
            self.status.last_update = datetime.now()
            
            # 通知状态变化
            self._notify_status_change()
            
            self.logger.info("实盘交易启动成功")
            
        except Exception as e:
            self.logger.error(f"启动实盘交易失败: {e}")
            self.status.state = TradingState.ERROR
            self.status.error_message = str(e)
            self._notify_error(e)
            raise
    
    async def stop_trading(self):
        """停止实盘交易"""
        try:
            if self.status.state == TradingState.STOPPED:
                return
            
            self.logger.info("停止实盘交易...")
            self.status.state = TradingState.STOPPING
            
            # 停止接受新的交易信号
            self.running = False
            
            # 停止策略
            await self._stop_strategies()
            
            # 处理待处理的订单
            await self._handle_pending_orders()
            
            # 停止数据流
            await self.data_stream.stop()
            
            # 停止风控监控
            self.risk_engine.stop_monitoring()
            
            # 断开交易接口
            self.trading_interface.disconnect()
            
            # 更新统计信息
            if self.stats['start_time']:
                self.stats['total_runtime_seconds'] = (datetime.now() - self.stats['start_time']).total_seconds()
            
            self.status.state = TradingState.STOPPED
            self.status.last_update = datetime.now()
            
            # 通知状态变化
            self._notify_status_change()
            
            self.logger.info("实盘交易已停止")
            
        except Exception as e:
            self.logger.error(f"停止实盘交易失败: {e}")
            self.status.error_message = str(e)
            raise
    
    async def pause_trading(self):
        """暂停交易"""
        try:
            if self.status.state != TradingState.RUNNING:
                raise RuntimeError(f"无法暂停交易，当前状态: {self.status.state}")
            
            self.logger.info("暂停实盘交易...")
            
            # 暂停策略执行
            for strategy_name in self.strategy_manager.get_active_strategies():
                self.strategy_manager.deactivate_strategy(strategy_name)
            
            # 禁用交易功能
            self.trading_interface.disable_trading()
            
            self.status.state = TradingState.PAUSED
            self.status.last_update = datetime.now()
            
            self._notify_status_change()
            self.logger.info("交易已暂停")
            
        except Exception as e:
            self.logger.error(f"暂停交易失败: {e}")
            raise
    
    async def resume_trading(self):
        """恢复交易"""
        try:
            if self.status.state != TradingState.PAUSED:
                raise RuntimeError(f"无法恢复交易，当前状态: {self.status.state}")
            
            self.logger.info("恢复实盘交易...")
            
            # 启用交易功能
            if not self.trading_interface.enable_trading():
                raise RuntimeError("启用交易功能失败")
            
            # 恢复策略执行
            for strategy_name in self.strategy_manager.get_active_strategies():
                self.strategy_manager.activate_strategy(strategy_name)
            
            self.status.state = TradingState.RUNNING
            self.status.last_update = datetime.now()
            
            self._notify_status_change()
            self.logger.info("交易已恢复")
            
        except Exception as e:
            self.logger.error(f"恢复交易失败: {e}")
            raise
    
    async def _start_strategies(self):
        """启动策略"""
        try:
            # 从配置加载策略
            strategies_config = self.config_manager.get_config('trading', {}).get('strategies', {})
            
            for strategy_name, strategy_config in strategies_config.items():
                if strategy_config.get('enabled', False):
                    try:
                        # 创建策略实例
                        instance_name = self.strategy_manager.create_strategy(
                            strategy_name,
                            params=strategy_config.get('parameters', {})
                        )
                        
                        # 激活策略
                        self.strategy_manager.activate_strategy(instance_name)
                        
                        self.logger.info(f"策略 {strategy_name} 启动成功")
                        
                    except Exception as e:
                        self.logger.error(f"启动策略 {strategy_name} 失败: {e}")
            
            self.logger.info("策略启动完成")
            
        except Exception as e:
            self.logger.error(f"启动策略失败: {e}")
            raise
    
    async def _stop_strategies(self):
        """停止策略"""
        try:
            active_strategies = self.strategy_manager.get_active_strategies()
            
            for strategy_name in active_strategies:
                try:
                    self.strategy_manager.deactivate_strategy(strategy_name)
                    self.logger.info(f"策略 {strategy_name} 已停止")
                except Exception as e:
                    self.logger.error(f"停止策略 {strategy_name} 失败: {e}")
            
        except Exception as e:
            self.logger.error(f"停止策略失败: {e}")
    
    async def _handle_pending_orders(self):
        """处理待处理的订单"""
        try:
            # 获取所有待处理订单
            pending_orders = self.trading_interface.get_orders()
            pending_orders = [order for order in pending_orders if order.status.value in ['pending', 'submitted', 'partial_filled']]
            
            if not pending_orders:
                return
            
            self.logger.info(f"处理 {len(pending_orders)} 个待处理订单...")
            
            # 等待订单完成或超时撤销
            timeout = 60  # 60秒超时
            start_time = time.time()
            
            while pending_orders and (time.time() - start_time) < timeout:
                for order in pending_orders[:]:
                    # 查询最新状态
                    updated_order = self.trading_interface.get_order_status(order.order_id)
                    if updated_order and updated_order.status.value in ['filled', 'cancelled', 'rejected']:
                        pending_orders.remove(order)
                        self.logger.info(f"订单 {order.order_id} 状态: {updated_order.status.value}")
                
                if pending_orders:
                    await asyncio.sleep(1)
            
            # 撤销剩余的待处理订单
            for order in pending_orders:
                try:
                    if self.trading_interface.cancel_order(order.order_id):
                        self.logger.info(f"撤销订单: {order.order_id}")
                    else:
                        self.logger.warning(f"撤销订单失败: {order.order_id}")
                except Exception as e:
                    self.logger.error(f"撤销订单 {order.order_id} 异常: {e}")
            
        except Exception as e:
            self.logger.error(f"处理待处理订单失败: {e}")
    
    async def _on_market_data(self, market_data):
        """处理市场数据"""
        try:
            self.stats['data_messages_processed'] += 1
            
            # 更新风控引擎价格
            if market_data.data_type == DataType.TICK:
                price_data = {market_data.symbol: market_data.data.get('price', 0)}
                self.risk_engine.update_market_prices(price_data)
            
            # 检查止损止盈
            if market_data.data_type == DataType.TICK:
                exit_signal = self.risk_engine.check_stop_loss_profit(
                    market_data.symbol, 
                    market_data.data.get('price', 0)
                )
                
                if exit_signal:
                    # 创建平仓信号
                    # 这里需要与策略管理器集成
                    pass
            
            # 更新状态
            self.status.last_update = datetime.now()
            
        except Exception as e:
            self.logger.error(f"处理市场数据失败: {e}")
    
    async def _monitoring_task(self):
        """监控任务"""
        while self.running:
            try:
                # 检查连接状态
                if not self.trading_interface.is_connected:
                    self.logger.error("交易接口连接断开")
                    self.status.state = TradingState.ERROR
                    self.status.error_message = "交易接口连接断开"
                    break
                
                # 检查风控状态
                # 这里可以添加更多监控逻辑
                
                # 更新状态
                await self._update_trading_status()
                
                await asyncio.sleep(5)  # 每5秒检查一次
                
            except Exception as e:
                self.logger.error(f"监控任务异常: {e}")
                await asyncio.sleep(5)
    
    async def _statistics_task(self):
        """统计任务"""
        while self.running:
            try:
                # 更新统计信息
                await self._update_statistics()
                
                await asyncio.sleep(60)  # 每分钟更新一次
                
            except Exception as e:
                self.logger.error(f"统计任务异常: {e}")
                await asyncio.sleep(60)
    
    async def _heartbeat_task(self):
        """心跳任务"""
        while self.running:
            try:
                # 记录心跳
                self.logger.debug(f"交易管理器心跳 - 状态: {self.status.state}")
                
                await asyncio.sleep(30)  # 每30秒心跳
                
            except Exception as e:
                self.logger.error(f"心跳任务异常: {e}")
                await asyncio.sleep(30)
    
    async def _update_trading_status(self):
        """更新交易状态"""
        try:
            if not self.trading_interface:
                return
            
            # 获取账户信息
            account = self.trading_interface.get_account_info()
            if account:
                self.status.daily_pnl = account.total_pnl
            
            # 获取持仓信息
            positions = self.trading_interface.get_positions()
            self.status.active_positions = len([p for p in positions if p.quantity > 0])
            
            # 获取订单统计
            orders = self.trading_interface.get_orders()
            filled_orders = [o for o in orders if o.status.value == 'filled']
            self.status.total_trades = len(filled_orders)
            
            self.status.last_update = datetime.now()
            
        except Exception as e:
            self.logger.error(f"更新交易状态失败: {e}")
    
    async def _update_statistics(self):
        """更新统计信息"""
        try:
            # 获取交易接口统计
            if self.trading_interface:
                conn_stats = self.trading_interface.get_connection_stats()
                self.stats.update({
                    'orders_submitted': conn_stats.get('stats', {}).get('order_submits', 0),
                    'orders_cancelled': conn_stats.get('stats', {}).get('order_cancels', 0)
                })
            
            # 获取数据流统计
            if self.data_stream:
                data_stats = self.data_stream.get_stats()
                self.stats['data_messages_processed'] = data_stats.get('processed_messages', 0)
            
            # 获取风控统计
            if self.risk_engine:
                risk_summary = self.risk_engine.get_risk_summary()
                trade_stats = risk_summary.get('trade_statistics', {})
                self.stats['risk_checks_performed'] = trade_stats.get('total_trades', 0)
                self.stats['risk_violations'] = trade_stats.get('blocked_trades', 0)
            
        except Exception as e:
            self.logger.error(f"更新统计信息失败: {e}")
    
    def add_status_callback(self, callback: Callable):
        """添加状态变化回调"""
        self.status_callbacks.append(callback)
    
    def add_trade_callback(self, callback: Callable):
        """添加交易回调"""
        self.trade_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable):
        """添加错误回调"""
        self.error_callbacks.append(callback)
    
    def _notify_status_change(self):
        """通知状态变化"""
        for callback in self.status_callbacks:
            try:
                callback(self.status)
            except Exception as e:
                self.logger.error(f"状态回调执行失败: {e}")
    
    def _notify_error(self, error: Exception):
        """通知错误"""
        for callback in self.error_callbacks:
            try:
                callback(error)
            except Exception as e:
                self.logger.error(f"错误回调执行失败: {e}")
    
    def get_status(self) -> TradingStatus:
        """获取交易状态"""
        return self.status
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats.copy()
    
    def get_positions(self) -> List:
        """获取当前持仓"""
        if self.trading_interface:
            return self.trading_interface.get_positions()
        return []
    
    def get_orders(self) -> List:
        """获取订单列表"""
        if self.trading_interface:
            return self.trading_interface.get_orders()
        return []
    
    def get_account_info(self):
        """获取账户信息"""
        if self.trading_interface:
            return self.trading_interface.get_account_info()
        return None

# 全局实例
_live_trading_manager = None

def get_live_trading_manager() -> LiveTradingManager:
    """获取实盘交易管理器单例"""
    global _live_trading_manager
    if _live_trading_manager is None:
        _live_trading_manager = LiveTradingManager()
    return _live_trading_manager