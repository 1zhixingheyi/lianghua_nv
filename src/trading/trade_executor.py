"""
交易执行引擎

提供策略信号到实际交易的转换和执行功能
"""

import threading
import time
import queue
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid
from dataclasses import dataclass

from .base_trader import BaseTrader, OrderType, OrderSide, OrderStatus
from .order_manager import OrderManager
from .portfolio_tracker import PortfolioTracker
from ..strategies.base_strategy import Signal, SignalType
from ..risk.risk_engine import RiskEngine

class ExecutionMode(Enum):
    """执行模式"""
    IMMEDIATE = "immediate"      # 立即执行
    BATCH = "batch"             # 批量执行
    SCHEDULED = "scheduled"     # 定时执行
    GRADUAL = "gradual"         # 渐进执行

class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"         # 待执行
    EXECUTING = "executing"     # 执行中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"          # 执行失败
    CANCELLED = "cancelled"    # 已取消

@dataclass
class ExecutionTask:
    """执行任务"""
    task_id: str
    signal: Signal
    execution_mode: ExecutionMode
    priority: int = 5
    max_retries: int = 3
    retry_count: int = 0
    status: ExecutionStatus = ExecutionStatus.PENDING
    created_time: datetime = None
    start_time: datetime = None
    complete_time: datetime = None
    error_message: str = ""
    
    def __post_init__(self):
        if self.created_time is None:
            self.created_time = datetime.now()

class TradeExecutor:
    """
    交易执行引擎
    
    负责将策略信号转换为实际的交易指令并执行
    """
    
    def __init__(self, trader: BaseTrader, order_manager: OrderManager,
                 portfolio_tracker: PortfolioTracker, risk_engine: RiskEngine,
                 config: Dict[str, Any] = None):
        """
        初始化交易执行引擎
        
        Args:
            trader: 交易接口
            order_manager: 订单管理器
            portfolio_tracker: 持仓跟踪器
            risk_engine: 风控引擎
            config: 配置参数
        """
        self.trader = trader
        self.order_manager = order_manager
        self.portfolio_tracker = portfolio_tracker
        self.risk_engine = risk_engine
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 执行队列
        self.execution_queue = queue.PriorityQueue()
        self.batch_queue = queue.Queue()
        
        # 执行任务管理
        self.tasks: Dict[str, ExecutionTask] = {}
        self.completed_tasks: List[ExecutionTask] = []
        
        # 线程管理
        self.execution_enabled = False
        self.executor_threads: List[threading.Thread] = []
        self.batch_thread: Optional[threading.Thread] = None
        
        # 执行配置
        self.max_concurrent_executions = config.get('max_concurrent_executions', 5)
        self.batch_interval = config.get('batch_interval', 10.0)  # 批量执行间隔（秒）
        self.position_sizing_method = config.get('position_sizing_method', 'fixed_amount')
        self.default_order_amount = config.get('default_order_amount', 10000.0)
        self.slippage_tolerance = config.get('slippage_tolerance', 0.01)  # 滑点容忍度
        
        # 事件回调
        self.callbacks: Dict[str, List[Callable]] = {
            'task_started': [],
            'task_completed': [],
            'task_failed': [],
            'execution_error': []
        }
        
        # 统计信息
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'total_orders': 0,
            'successful_orders': 0,
            'failed_orders': 0
        }
        
    def start(self):
        """启动交易执行引擎"""
        if self.execution_enabled:
            self.logger.warning("交易执行引擎已经启动")
            return
        
        self.execution_enabled = True
        
        # 启动执行线程
        for i in range(self.max_concurrent_executions):
            thread = threading.Thread(target=self._execution_worker, name=f"ExecutorThread-{i}")
            thread.daemon = True
            thread.start()
            self.executor_threads.append(thread)
        
        # 启动批量执行线程
        self.batch_thread = threading.Thread(target=self._batch_worker, name="BatchExecutorThread")
        self.batch_thread.daemon = True
        self.batch_thread.start()
        
        self.logger.info("交易执行引擎已启动")
    
    def stop(self):
        """停止交易执行引擎"""
        if not self.execution_enabled:
            return
        
        self.execution_enabled = False
        
        # 等待所有线程结束
        for thread in self.executor_threads:
            thread.join(timeout=5)
        
        if self.batch_thread:
            self.batch_thread.join(timeout=5)
        
        self.executor_threads.clear()
        self.batch_thread = None
        
        self.logger.info("交易执行引擎已停止")
    
    def submit_signal(self, signal: Signal, execution_mode: ExecutionMode = ExecutionMode.IMMEDIATE,
                     priority: int = 5) -> str:
        """
        提交交易信号
        
        Args:
            signal: 交易信号
            execution_mode: 执行模式
            priority: 优先级（数字越小优先级越高）
            
        Returns:
            str: 任务ID
        """
        # 创建执行任务
        task = ExecutionTask(
            task_id=str(uuid.uuid4()),
            signal=signal,
            execution_mode=execution_mode,
            priority=priority
        )
        
        self.tasks[task.task_id] = task
        self.stats['total_tasks'] += 1
        
        # 根据执行模式分发任务
        if execution_mode == ExecutionMode.IMMEDIATE:
            # 立即执行队列
            self.execution_queue.put((priority, task.task_id))
        elif execution_mode == ExecutionMode.BATCH:
            # 批量执行队列
            self.batch_queue.put(task.task_id)
        elif execution_mode == ExecutionMode.SCHEDULED:
            # TODO: 实现定时执行
            self.logger.warning("定时执行模式尚未实现")
        elif execution_mode == ExecutionMode.GRADUAL:
            # TODO: 实现渐进执行
            self.logger.warning("渐进执行模式尚未实现")
        
        self.logger.info(f"交易信号已提交: {task.task_id}, 模式: {execution_mode.value}")
        return task.task_id
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消执行任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 取消是否成功
        """
        if task_id not in self.tasks:
            self.logger.error(f"任务不存在: {task_id}")
            return False
        
        task = self.tasks[task_id]
        
        if task.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
            self.logger.error(f"任务已结束，无法取消: {task_id}")
            return False
        
        task.status = ExecutionStatus.CANCELLED
        task.complete_time = datetime.now()
        
        self.logger.info(f"任务已取消: {task_id}")
        return True
    
    def get_task_status(self, task_id: str) -> Optional[ExecutionTask]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            ExecutionTask: 任务信息，不存在返回None
        """
        return self.tasks.get(task_id)
    
    def get_pending_tasks(self) -> List[ExecutionTask]:
        """获取待执行任务列表"""
        return [task for task in self.tasks.values() if task.status == ExecutionStatus.PENDING]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        current_stats = {
            'pending': len([t for t in self.tasks.values() if t.status == ExecutionStatus.PENDING]),
            'executing': len([t for t in self.tasks.values() if t.status == ExecutionStatus.EXECUTING]),
            'completed': len([t for t in self.tasks.values() if t.status == ExecutionStatus.COMPLETED]),
            'failed': len([t for t in self.tasks.values() if t.status == ExecutionStatus.FAILED]),
            'cancelled': len([t for t in self.tasks.values() if t.status == ExecutionStatus.CANCELLED])
        }
        
        return {
            **self.stats,
            'current_status': current_stats,
            'queue_size': self.execution_queue.qsize(),
            'batch_queue_size': self.batch_queue.qsize()
        }
    
    def add_callback(self, event: str, callback: Callable):
        """添加事件回调"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
        else:
            self.logger.error(f"不支持的事件类型: {event}")
    
    def remove_callback(self, event: str, callback: Callable):
        """移除事件回调"""
        if event in self.callbacks and callback in self.callbacks[event]:
            self.callbacks[event].remove(callback)
    
    def _execution_worker(self):
        """执行工作线程"""
        while self.execution_enabled:
            try:
                # 获取执行任务
                try:
                    priority, task_id = self.execution_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                if task_id not in self.tasks:
                    continue
                
                task = self.tasks[task_id]
                
                # 检查任务状态
                if task.status != ExecutionStatus.PENDING:
                    continue
                
                # 执行任务
                self._execute_task(task)
                
            except Exception as e:
                self.logger.error(f"执行线程异常: {e}")
    
    def _batch_worker(self):
        """批量执行工作线程"""
        batch_tasks = []
        
        while self.execution_enabled:
            try:
                # 收集批量任务
                end_time = time.time() + self.batch_interval
                
                while time.time() < end_time and self.execution_enabled:
                    try:
                        task_id = self.batch_queue.get(timeout=1.0)
                        if task_id in self.tasks:
                            batch_tasks.append(self.tasks[task_id])
                    except queue.Empty:
                        continue
                
                # 执行批量任务
                if batch_tasks:
                    self._execute_batch_tasks(batch_tasks)
                    batch_tasks.clear()
                
            except Exception as e:
                self.logger.error(f"批量执行线程异常: {e}")
    
    def _execute_task(self, task: ExecutionTask):
        """
        执行单个任务
        
        Args:
            task: 执行任务
        """
        try:
            task.status = ExecutionStatus.EXECUTING
            task.start_time = datetime.now()
            
            self._trigger_callback('task_started', task)
            self.logger.info(f"开始执行任务: {task.task_id}")
            
            # 风控检查
            if not self._risk_check(task.signal):
                task.status = ExecutionStatus.FAILED
                task.error_message = "风控检查未通过"
                task.complete_time = datetime.now()
                self.stats['failed_tasks'] += 1
                self._trigger_callback('task_failed', task)
                return
            
            # 转换信号为订单
            orders = self._signal_to_orders(task.signal)
            
            if not orders:
                task.status = ExecutionStatus.FAILED
                task.error_message = "无法生成有效订单"
                task.complete_time = datetime.now()
                self.stats['failed_tasks'] += 1
                self._trigger_callback('task_failed', task)
                return
            
            # 执行订单
            success_count = 0
            for order_params in orders:
                if self._execute_order(order_params):
                    success_count += 1
                    self.stats['successful_orders'] += 1
                else:
                    self.stats['failed_orders'] += 1
                
                self.stats['total_orders'] += 1
            
            # 判断任务执行结果
            if success_count > 0:
                task.status = ExecutionStatus.COMPLETED
                self.stats['completed_tasks'] += 1
                self._trigger_callback('task_completed', task)
            else:
                task.status = ExecutionStatus.FAILED
                task.error_message = "所有订单执行失败"
                self.stats['failed_tasks'] += 1
                self._trigger_callback('task_failed', task)
            
            task.complete_time = datetime.now()
            self.logger.info(f"任务执行完成: {task.task_id}, 状态: {task.status.value}")
            
        except Exception as e:
            task.status = ExecutionStatus.FAILED
            task.error_message = str(e)
            task.complete_time = datetime.now()
            self.stats['failed_tasks'] += 1
            
            self.logger.error(f"任务执行异常: {task.task_id}, 错误: {e}")
            self._trigger_callback('task_failed', task)
            self._trigger_callback('execution_error', {'task': task, 'error': e})
    
    def _execute_batch_tasks(self, tasks: List[ExecutionTask]):
        """
        执行批量任务
        
        Args:
            tasks: 任务列表
        """
        if not tasks:
            return
        
        self.logger.info(f"开始批量执行任务: {len(tasks)}个")
        
        # 合并相同股票的信号
        merged_signals = self._merge_signals([task.signal for task in tasks])
        
        # 为每个合并后的信号创建订单
        all_orders = []
        for signal in merged_signals:
            orders = self._signal_to_orders(signal)
            all_orders.extend(orders)
        
        # 批量提交订单
        if all_orders:
            self._execute_batch_orders(all_orders)
        
        # 更新任务状态
        for task in tasks:
            task.status = ExecutionStatus.COMPLETED
            task.complete_time = datetime.now()
            self.stats['completed_tasks'] += 1
            self._trigger_callback('task_completed', task)
    
    def _risk_check(self, signal: Signal) -> bool:
        """
        风控检查
        
        Args:
            signal: 交易信号
            
        Returns:
            bool: 是否通过风控检查
        """
        try:
            # 调用风控引擎检查
            if self.risk_engine:
                return self.risk_engine.check_signal(signal)
            return True
            
        except Exception as e:
            self.logger.error(f"风控检查异常: {e}")
            return False
    
    def _signal_to_orders(self, signal: Signal) -> List[Dict[str, Any]]:
        """
        将信号转换为订单参数
        
        Args:
            signal: 交易信号
            
        Returns:
            List[Dict[str, Any]]: 订单参数列表
        """
        orders = []
        
        try:
            # 确定交易方向
            if signal.signal_type == SignalType.BUY:
                side = OrderSide.BUY
            elif signal.signal_type == SignalType.SELL:
                side = OrderSide.SELL
            else:
                return orders
            
            # 计算交易数量
            quantity = self._calculate_position_size(signal)
            
            if quantity <= 0:
                return orders
            
            # 确定订单类型和价格
            order_type, price = self._determine_order_type_and_price(signal)
            
            order_params = {
                'symbol': signal.symbol,
                'side': side,
                'order_type': order_type,
                'quantity': quantity,
                'price': price
            }
            
            orders.append(order_params)
            
        except Exception as e:
            self.logger.error(f"信号转换订单失败: {e}")
        
        return orders
    
    def _calculate_position_size(self, signal: Signal) -> int:
        """
        计算持仓规模
        
        Args:
            signal: 交易信号
            
        Returns:
            int: 交易数量（股）
        """
        try:
            if self.position_sizing_method == 'fixed_amount':
                # 固定金额
                price = signal.price if signal.price > 0 else self._get_current_price(signal.symbol)
                if price > 0:
                    quantity = int(self.default_order_amount / price)
                    return quantity - (quantity % 100)  # 调整为100的整数倍
            
            elif self.position_sizing_method == 'fixed_quantity':
                # 固定数量
                return int(self.config.get('fixed_quantity', 1000))
            
            elif self.position_sizing_method == 'percent_portfolio':
                # 按组合比例
                if self.portfolio_tracker.account:
                    total_value = self.portfolio_tracker.account.total_value
                    percent = self.config.get('position_percent', 0.05)
                    target_value = total_value * percent
                    
                    price = signal.price if signal.price > 0 else self._get_current_price(signal.symbol)
                    if price > 0:
                        quantity = int(target_value / price)
                        return quantity - (quantity % 100)
            
            elif self.position_sizing_method == 'risk_based':
                # 基于风险的仓位管理
                # TODO: 实现基于风险的仓位计算
                pass
            
            return 0
            
        except Exception as e:
            self.logger.error(f"计算持仓规模失败: {e}")
            return 0
    
    def _determine_order_type_and_price(self, signal: Signal) -> tuple[OrderType, float]:
        """
        确定订单类型和价格
        
        Args:
            signal: 交易信号
            
        Returns:
            tuple[OrderType, float]: 订单类型和价格
        """
        # 根据信号配置决定订单类型
        if signal.order_type:
            if signal.order_type.lower() == 'market':
                return OrderType.MARKET, 0.0
            elif signal.order_type.lower() == 'limit':
                price = signal.price if signal.price > 0 else self._get_current_price(signal.symbol)
                return OrderType.LIMIT, price
        
        # 默认使用限价单
        price = signal.price if signal.price > 0 else self._get_current_price(signal.symbol)
        
        # 考虑滑点
        if price > 0:
            if signal.signal_type == SignalType.BUY:
                price *= (1 + self.slippage_tolerance)
            else:
                price *= (1 - self.slippage_tolerance)
        
        return OrderType.LIMIT, price
    
    def _get_current_price(self, symbol: str) -> float:
        """
        获取当前价格
        
        Args:
            symbol: 股票代码
            
        Returns:
            float: 当前价格
        """
        try:
            # 从持仓跟踪器获取价格
            position = self.portfolio_tracker.get_position(symbol)
            if position and position.current_price > 0:
                return position.current_price
            
            # TODO: 从行情接口获取价格
            return 0.0
            
        except Exception as e:
            self.logger.error(f"获取价格失败: {symbol}, {e}")
            return 0.0
    
    def _execute_order(self, order_params: Dict[str, Any]) -> bool:
        """
        执行单个订单
        
        Args:
            order_params: 订单参数
            
        Returns:
            bool: 执行是否成功
        """
        try:
            order_id = self.order_manager.submit_order(**order_params)
            return order_id is not None
            
        except Exception as e:
            self.logger.error(f"执行订单失败: {e}")
            return False
    
    def _execute_batch_orders(self, orders: List[Dict[str, Any]]):
        """
        批量执行订单
        
        Args:
            orders: 订单参数列表
        """
        for order_params in orders:
            self._execute_order(order_params)
    
    def _merge_signals(self, signals: List[Signal]) -> List[Signal]:
        """
        合并相同股票的信号
        
        Args:
            signals: 信号列表
            
        Returns:
            List[Signal]: 合并后的信号列表
        """
        # 按股票代码分组
        signal_groups = {}
        for signal in signals:
            if signal.symbol not in signal_groups:
                signal_groups[signal.symbol] = []
            signal_groups[signal.symbol].append(signal)
        
        merged_signals = []
        for symbol, group_signals in signal_groups.items():
            # 简单合并：取最新的信号
            latest_signal = max(group_signals, key=lambda s: s.timestamp)
            merged_signals.append(latest_signal)
        
        return merged_signals
    
    def _trigger_callback(self, event: str, data: Any):
        """触发事件回调"""
        try:
            for callback in self.callbacks.get(event, []):
                callback(data)
        except Exception as e:
            self.logger.error(f"回调函数执行异常: {e}")
    
    def cleanup_completed_tasks(self, days: int = 7):
        """
        清理已完成的任务
        
        Args:
            days: 保留天数
        """
        cutoff_time = datetime.now() - timedelta(days=days)
        tasks_to_remove = []
        
        for task_id, task in self.tasks.items():
            if (task.complete_time and task.complete_time < cutoff_time and 
                task.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]):
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            task = self.tasks[task_id]
            self.completed_tasks.append(task)
            del self.tasks[task_id]
        
        # 只保留最近的完成任务
        self.completed_tasks = [t for t in self.completed_tasks if 
                               t.complete_time and t.complete_time >= cutoff_time]
        
        self.logger.info(f"清理已完成任务: {len(tasks_to_remove)}个")