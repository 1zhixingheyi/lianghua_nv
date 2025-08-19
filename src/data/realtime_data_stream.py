"""
实时数据流处理系统

提供高性能的实时市场数据流处理功能
"""

import asyncio
import websockets
import json
import threading
import time
from typing import Dict, List, Optional, Any, Callable, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque
import logging
import queue
from concurrent.futures import ThreadPoolExecutor
import aiohttp
import pandas as pd
import numpy as np
from enum import Enum

from config.config_manager import get_config_manager

class DataSourceType(Enum):
    """数据源类型"""
    WEBSOCKET = "websocket"
    REST_API = "rest_api" 
    TCP_SOCKET = "tcp_socket"
    UDP_SOCKET = "udp_socket"

class DataType(Enum):
    """数据类型"""
    TICK = "tick"              # tick数据
    KLINE = "kline"            # K线数据
    DEPTH = "depth"            # 深度数据
    TRADE = "trade"            # 成交数据
    ORDER_BOOK = "order_book"  # 订单薄
    INDEX = "index"            # 指数数据

@dataclass
class MarketData:
    """市场数据结构"""
    symbol: str
    data_type: DataType
    timestamp: datetime
    data: Dict[str, Any]
    source: str
    sequence: Optional[int] = None
    latency: Optional[float] = None  # 延迟(毫秒)

@dataclass 
class SubscriptionRequest:
    """订阅请求"""
    symbol: str
    data_type: DataType
    frequency: Optional[str] = None  # 频率: 1s, 5s, 1m, 5m等
    depth: Optional[int] = None      # 深度档位
    callback: Optional[Callable] = None
    
@dataclass
class DataStreamConfig:
    """数据流配置"""
    buffer_size: int = 10000
    batch_size: int = 100
    flush_interval: float = 1.0
    max_latency: float = 0.1
    compression: bool = True
    heartbeat_interval: float = 30.0
    
    # WebSocket配置
    websocket_config: Dict[str, Any] = field(default_factory=dict)
    
    # 质量控制配置
    quality_control: Dict[str, Any] = field(default_factory=dict)

class RealtimeDataStream:
    """实时数据流处理器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化实时数据流处理器
        
        Args:
            config: 配置参数
        """
        self.config = DataStreamConfig(**(config or {}))
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 订阅管理
        self.subscriptions: Dict[str, SubscriptionRequest] = {}
        self.active_symbols: Set[str] = set()
        
        # 数据缓冲区
        self.data_buffer: deque = deque(maxlen=self.config.buffer_size)
        self.tick_cache: Dict[str, MarketData] = {}
        
        # 连接管理
        self.connections: Dict[str, Any] = {}
        self.connection_status: Dict[str, bool] = {}
        
        # 线程和事件循环
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="DataStream")
        self.event_loop = None
        self.running = False
        
        # 回调函数
        self.data_callbacks: List[Callable] = []
        self.error_callbacks: List[Callable] = []
        
        # 统计信息
        self.stats = {
            'total_messages': 0,
            'processed_messages': 0,
            'error_messages': 0,
            'last_message_time': None,
            'average_latency': 0.0,
            'connections_count': 0
        }
        
        # 质量控制
        self.quality_controller = DataQualityController(
            self.config.quality_control
        )
        
        # 配置管理器
        self.config_manager = get_config_manager()
        
    async def start(self):
        """启动数据流"""
        try:
            self.running = True
            self.event_loop = asyncio.get_event_loop()
            
            self.logger.info("启动实时数据流处理器...")
            
            # 启动后台任务
            await asyncio.gather(
                self._data_processor_task(),
                self._heartbeat_task(),
                self._stats_task()
            )
            
        except Exception as e:
            self.logger.error(f"启动数据流失败: {e}")
            raise
    
    async def stop(self):
        """停止数据流"""
        try:
            self.logger.info("停止实时数据流处理器...")
            self.running = False
            
            # 关闭所有连接
            for source_name, connection in self.connections.items():
                try:
                    if hasattr(connection, 'close'):
                        await connection.close()
                except Exception as e:
                    self.logger.error(f"关闭连接 {source_name} 失败: {e}")
            
            # 清理资源
            self.connections.clear()
            self.connection_status.clear()
            self.executor.shutdown(wait=True)
            
            self.logger.info("数据流已停止")
            
        except Exception as e:
            self.logger.error(f"停止数据流失败: {e}")
    
    def subscribe(self, request: SubscriptionRequest) -> str:
        """
        订阅数据
        
        Args:
            request: 订阅请求
            
        Returns:
            订阅ID
        """
        subscription_id = f"{request.symbol}_{request.data_type.value}"
        
        if subscription_id in self.subscriptions:
            self.logger.warning(f"订阅已存在: {subscription_id}")
            return subscription_id
        
        self.subscriptions[subscription_id] = request
        self.active_symbols.add(request.symbol)
        
        # 异步启动订阅
        if self.event_loop:
            asyncio.run_coroutine_threadsafe(
                self._start_subscription(request),
                self.event_loop
            )
        
        self.logger.info(f"添加订阅: {subscription_id}")
        return subscription_id
    
    def unsubscribe(self, subscription_id: str):
        """取消订阅"""
        if subscription_id not in self.subscriptions:
            self.logger.warning(f"订阅不存在: {subscription_id}")
            return
        
        request = self.subscriptions[subscription_id]
        
        # 异步停止订阅
        if self.event_loop:
            asyncio.run_coroutine_threadsafe(
                self._stop_subscription(request),
                self.event_loop
            )
        
        del self.subscriptions[subscription_id]
        
        # 如果没有其他订阅，移除symbol
        if not any(req.symbol == request.symbol for req in self.subscriptions.values()):
            self.active_symbols.discard(request.symbol)
        
        self.logger.info(f"取消订阅: {subscription_id}")
    
    async def _start_subscription(self, request: SubscriptionRequest):
        """启动单个订阅"""
        try:
            # 根据数据类型选择数据源
            if request.data_type == DataType.TICK:
                await self._subscribe_tick_data(request)
            elif request.data_type == DataType.KLINE:
                await self._subscribe_kline_data(request)
            elif request.data_type == DataType.DEPTH:
                await self._subscribe_depth_data(request)
            elif request.data_type == DataType.TRADE:
                await self._subscribe_trade_data(request)
            else:
                self.logger.error(f"不支持的数据类型: {request.data_type}")
                
        except Exception as e:
            self.logger.error(f"启动订阅失败: {request.symbol} {request.data_type} - {e}")
    
    async def _stop_subscription(self, request: SubscriptionRequest):
        """停止单个订阅"""
        try:
            # 实现取消订阅逻辑
            connection_key = f"{request.symbol}_{request.data_type.value}"
            if connection_key in self.connections:
                connection = self.connections[connection_key]
                if hasattr(connection, 'close'):
                    await connection.close()
                del self.connections[connection_key]
                del self.connection_status[connection_key]
                
        except Exception as e:
            self.logger.error(f"停止订阅失败: {request.symbol} {request.data_type} - {e}")
    
    async def _subscribe_tick_data(self, request: SubscriptionRequest):
        """订阅tick数据"""
        try:
            # 获取WebSocket配置
            ws_config = self.config.websocket_config
            url = ws_config.get('tick_url', 'wss://api.example.com/ws/tick')
            
            # 建立WebSocket连接
            websocket = await websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            connection_key = f"{request.symbol}_{request.data_type.value}"
            self.connections[connection_key] = websocket
            self.connection_status[connection_key] = True
            self.stats['connections_count'] += 1
            
            # 发送订阅消息
            subscribe_msg = {
                "method": "subscribe",
                "params": [f"{request.symbol}@ticker"],
                "id": int(time.time())
            }
            
            await websocket.send(json.dumps(subscribe_msg))
            
            # 启动数据接收任务
            asyncio.create_task(self._handle_websocket_messages(websocket, request))
            
        except Exception as e:
            self.logger.error(f"订阅tick数据失败: {request.symbol} - {e}")
    
    async def _subscribe_kline_data(self, request: SubscriptionRequest):
        """订阅K线数据"""
        try:
            ws_config = self.config.websocket_config
            url = ws_config.get('kline_url', 'wss://api.example.com/ws/kline')
            
            websocket = await websockets.connect(url)
            
            connection_key = f"{request.symbol}_{request.data_type.value}"
            self.connections[connection_key] = websocket
            self.connection_status[connection_key] = True
            
            # 订阅K线数据
            frequency = request.frequency or '1m'
            subscribe_msg = {
                "method": "subscribe", 
                "params": [f"{request.symbol}@kline_{frequency}"],
                "id": int(time.time())
            }
            
            await websocket.send(json.dumps(subscribe_msg))
            asyncio.create_task(self._handle_websocket_messages(websocket, request))
            
        except Exception as e:
            self.logger.error(f"订阅K线数据失败: {request.symbol} - {e}")
    
    async def _subscribe_depth_data(self, request: SubscriptionRequest):
        """订阅深度数据"""
        try:
            ws_config = self.config.websocket_config
            url = ws_config.get('depth_url', 'wss://api.example.com/ws/depth')
            
            websocket = await websockets.connect(url)
            
            connection_key = f"{request.symbol}_{request.data_type.value}"
            self.connections[connection_key] = websocket
            self.connection_status[connection_key] = True
            
            # 订阅深度数据
            depth = request.depth or 20
            subscribe_msg = {
                "method": "subscribe",
                "params": [f"{request.symbol}@depth{depth}"],
                "id": int(time.time())
            }
            
            await websocket.send(json.dumps(subscribe_msg))
            asyncio.create_task(self._handle_websocket_messages(websocket, request))
            
        except Exception as e:
            self.logger.error(f"订阅深度数据失败: {request.symbol} - {e}")
    
    async def _subscribe_trade_data(self, request: SubscriptionRequest):
        """订阅成交数据"""
        try:
            ws_config = self.config.websocket_config
            url = ws_config.get('trade_url', 'wss://api.example.com/ws/trade')
            
            websocket = await websockets.connect(url)
            
            connection_key = f"{request.symbol}_{request.data_type.value}"
            self.connections[connection_key] = websocket
            self.connection_status[connection_key] = True
            
            # 订阅成交数据
            subscribe_msg = {
                "method": "subscribe",
                "params": [f"{request.symbol}@trade"],
                "id": int(time.time())
            }
            
            await websocket.send(json.dumps(subscribe_msg))
            asyncio.create_task(self._handle_websocket_messages(websocket, request))
            
        except Exception as e:
            self.logger.error(f"订阅成交数据失败: {request.symbol} - {e}")
    
    async def _handle_websocket_messages(self, websocket, request: SubscriptionRequest):
        """处理WebSocket消息"""
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._process_message(data, request)
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"解析消息失败: {e}")
                    self.stats['error_messages'] += 1
                    
                except Exception as e:
                    self.logger.error(f"处理消息失败: {e}")
                    self.stats['error_messages'] += 1
                    
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning(f"WebSocket连接关闭: {request.symbol}")
            connection_key = f"{request.symbol}_{request.data_type.value}"
            self.connection_status[connection_key] = False
            
            # 尝试重连
            if self.running:
                await asyncio.sleep(5)
                await self._start_subscription(request)
                
        except Exception as e:
            self.logger.error(f"WebSocket处理异常: {e}")
    
    async def _process_message(self, data: Dict, request: SubscriptionRequest):
        """处理接收到的消息"""
        try:
            # 计算延迟
            receive_time = datetime.now()
            if 'timestamp' in data:
                server_time = datetime.fromtimestamp(data['timestamp'] / 1000)
                latency = (receive_time - server_time).total_seconds() * 1000
            else:
                latency = None
            
            # 创建市场数据对象
            market_data = MarketData(
                symbol=request.symbol,
                data_type=request.data_type,
                timestamp=receive_time,
                data=data,
                source="websocket",
                latency=latency
            )
            
            # 质量检查
            if not self.quality_controller.validate_data(market_data):
                self.logger.warning(f"数据质量检查失败: {request.symbol}")
                return
            
            # 更新统计
            self.stats['total_messages'] += 1
            self.stats['processed_messages'] += 1
            self.stats['last_message_time'] = receive_time
            
            if latency:
                # 更新平均延迟
                current_avg = self.stats['average_latency']
                self.stats['average_latency'] = (current_avg * 0.9 + latency * 0.1)
            
            # 添加到缓冲区
            self.data_buffer.append(market_data)
            
            # 更新缓存
            if request.data_type == DataType.TICK:
                self.tick_cache[request.symbol] = market_data
            
            # 调用回调函数
            if request.callback:
                try:
                    await request.callback(market_data)
                except Exception as e:
                    self.logger.error(f"回调函数执行失败: {e}")
            
            # 调用全局回调
            for callback in self.data_callbacks:
                try:
                    await callback(market_data)
                except Exception as e:
                    self.logger.error(f"全局回调函数执行失败: {e}")
                    
        except Exception as e:
            self.logger.error(f"处理消息失败: {e}")
            self.stats['error_messages'] += 1
    
    async def _data_processor_task(self):
        """数据处理任务"""
        batch = []
        last_flush = time.time()
        
        while self.running:
            try:
                # 收集批量数据
                while len(batch) < self.config.batch_size and self.data_buffer:
                    batch.append(self.data_buffer.popleft())
                
                # 检查是否需要刷新
                current_time = time.time()
                should_flush = (
                    len(batch) >= self.config.batch_size or
                    (batch and current_time - last_flush >= self.config.flush_interval)
                )
                
                if should_flush and batch:
                    await self._process_batch(batch)
                    batch.clear()
                    last_flush = current_time
                
                await asyncio.sleep(0.001)  # 短暂休眠
                
            except Exception as e:
                self.logger.error(f"数据处理任务异常: {e}")
                await asyncio.sleep(1)
    
    async def _process_batch(self, batch: List[MarketData]):
        """处理批量数据"""
        try:
            # 按数据类型分组处理
            grouped_data = {}
            for data in batch:
                key = f"{data.symbol}_{data.data_type.value}"
                if key not in grouped_data:
                    grouped_data[key] = []
                grouped_data[key].append(data)
            
            # 并行处理各组数据
            tasks = []
            for key, data_list in grouped_data.items():
                task = asyncio.create_task(self._process_data_group(key, data_list))
                tasks.append(task)
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                
        except Exception as e:
            self.logger.error(f"处理批量数据失败: {e}")
    
    async def _process_data_group(self, key: str, data_list: List[MarketData]):
        """处理数据组"""
        try:
            # 数据聚合和预处理
            if data_list[0].data_type == DataType.TICK:
                await self._process_tick_data(data_list)
            elif data_list[0].data_type == DataType.KLINE:
                await self._process_kline_data(data_list)
            elif data_list[0].data_type == DataType.DEPTH:
                await self._process_depth_data(data_list)
            elif data_list[0].data_type == DataType.TRADE:
                await self._process_trade_data(data_list)
                
        except Exception as e:
            self.logger.error(f"处理数据组失败 {key}: {e}")
    
    async def _process_tick_data(self, data_list: List[MarketData]):
        """处理tick数据"""
        # 实现tick数据的聚合和分析
        for data in data_list:
            # 提取价格信息
            price_data = {
                'symbol': data.symbol,
                'price': data.data.get('price', 0),
                'volume': data.data.get('volume', 0),
                'timestamp': data.timestamp
            }
            
            # 存储到数据库或发送到下游系统
            # 这里可以集成到四层存储架构中
    
    async def _process_kline_data(self, data_list: List[MarketData]):
        """处理K线数据"""
        for data in data_list:
            kline_data = {
                'symbol': data.symbol,
                'open': data.data.get('open', 0),
                'high': data.data.get('high', 0), 
                'low': data.data.get('low', 0),
                'close': data.data.get('close', 0),
                'volume': data.data.get('volume', 0),
                'timestamp': data.timestamp
            }
    
    async def _process_depth_data(self, data_list: List[MarketData]):
        """处理深度数据"""
        for data in data_list:
            depth_data = {
                'symbol': data.symbol,
                'bids': data.data.get('bids', []),
                'asks': data.data.get('asks', []),
                'timestamp': data.timestamp
            }
    
    async def _process_trade_data(self, data_list: List[MarketData]):
        """处理成交数据"""
        for data in data_list:
            trade_data = {
                'symbol': data.symbol,
                'price': data.data.get('price', 0),
                'quantity': data.data.get('quantity', 0),
                'side': data.data.get('side', ''),
                'timestamp': data.timestamp
            }
    
    async def _heartbeat_task(self):
        """心跳任务"""
        while self.running:
            try:
                # 检查连接状态
                for connection_key, is_connected in self.connection_status.items():
                    if not is_connected:
                        self.logger.warning(f"连接断开: {connection_key}")
                        # 可以在这里实现重连逻辑
                
                # 发送心跳
                for connection_key, connection in self.connections.items():
                    try:
                        if hasattr(connection, 'ping'):
                            await connection.ping()
                    except Exception as e:
                        self.logger.error(f"发送心跳失败 {connection_key}: {e}")
                        self.connection_status[connection_key] = False
                
                await asyncio.sleep(self.config.heartbeat_interval)
                
            except Exception as e:
                self.logger.error(f"心跳任务异常: {e}")
                await asyncio.sleep(5)
    
    async def _stats_task(self):
        """统计任务"""
        while self.running:
            try:
                # 记录统计信息
                self.logger.debug(f"数据流统计: {self.stats}")
                
                # 检查延迟告警
                if self.stats['average_latency'] > self.config.max_latency * 1000:
                    self.logger.warning(f"数据延迟过高: {self.stats['average_latency']:.2f}ms")
                
                await asyncio.sleep(60)  # 每分钟记录一次
                
            except Exception as e:
                self.logger.error(f"统计任务异常: {e}")
                await asyncio.sleep(10)
    
    def add_data_callback(self, callback: Callable):
        """添加数据回调函数"""
        self.data_callbacks.append(callback)
    
    def remove_data_callback(self, callback: Callable):
        """移除数据回调函数"""
        if callback in self.data_callbacks:
            self.data_callbacks.remove(callback)
    
    def get_latest_tick(self, symbol: str) -> Optional[MarketData]:
        """获取最新tick数据"""
        return self.tick_cache.get(symbol)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            'subscriptions_count': len(self.subscriptions),
            'active_symbols_count': len(self.active_symbols),
            'buffer_size': len(self.data_buffer),
            'connections': {k: v for k, v in self.connection_status.items()}
        }


class DataQualityController:
    """数据质量控制器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 数据校验规则
        self.validation_rules = {
            'price_range_check': self.config.get('price_range_check', {}),
            'volume_check': self.config.get('volume_check', {}),
            'timestamp_check': self.config.get('timestamp_check', {}),
            'duplicate_check': self.config.get('duplicate_check', {})
        }
        
        # 重复检查窗口
        self.duplicate_window: deque = deque(maxlen=self.validation_rules['duplicate_check'].get('window_size', 100))
    
    def validate_data(self, data: MarketData) -> bool:
        """验证数据质量"""
        try:
            # 价格范围检查
            if not self._check_price_range(data):
                return False
            
            # 成交量检查
            if not self._check_volume(data):
                return False
            
            # 时间戳检查
            if not self._check_timestamp(data):
                return False
            
            # 重复数据检查
            if not self._check_duplicate(data):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"数据质量检查异常: {e}")
            return False
    
    def _check_price_range(self, data: MarketData) -> bool:
        """检查价格范围"""
        if not self.validation_rules['price_range_check'].get('enabled', True):
            return True
        
        try:
            price = data.data.get('price', 0)
            if price <= 0:
                return False
            
            # 检查价格变动幅度
            max_change = self.validation_rules['price_range_check'].get('max_change_percent', 20.0)
            # 这里需要与历史价格比较，简化实现
            
            return True
            
        except Exception as e:
            self.logger.error(f"价格范围检查失败: {e}")
            return False
    
    def _check_volume(self, data: MarketData) -> bool:
        """检查成交量"""
        if not self.validation_rules['volume_check'].get('enabled', True):
            return True
        
        try:
            volume = data.data.get('volume', 0)
            min_volume = self.validation_rules['volume_check'].get('min_volume', 0)
            
            if volume < min_volume:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"成交量检查失败: {e}")
            return False
    
    def _check_timestamp(self, data: MarketData) -> bool:
        """检查时间戳"""
        if not self.validation_rules['timestamp_check'].get('enabled', True):
            return True
        
        try:
            max_delay = self.validation_rules['timestamp_check'].get('max_delay_seconds', 10.0)
            current_time = datetime.now()
            
            if (current_time - data.timestamp).total_seconds() > max_delay:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"时间戳检查失败: {e}")
            return False
    
    def _check_duplicate(self, data: MarketData) -> bool:
        """检查重复数据"""
        if not self.validation_rules['duplicate_check'].get('enabled', True):
            return True
        
        try:
            # 生成数据指纹
            fingerprint = f"{data.symbol}_{data.data_type.value}_{data.timestamp}_{hash(str(data.data))}"
            
            if fingerprint in self.duplicate_window:
                return False
            
            self.duplicate_window.append(fingerprint)
            return True
            
        except Exception as e:
            self.logger.error(f"重复数据检查失败: {e}")
            return False


# 全局实例
_realtime_data_stream = None

def get_realtime_data_stream() -> RealtimeDataStream:
    """获取实时数据流单例"""
    global _realtime_data_stream
    if _realtime_data_stream is None:
        # 从配置管理器获取配置
        config_manager = get_config_manager()
        config = config_manager.get_config('live_trading', {}).get('realtime_stream', {})
        _realtime_data_stream = RealtimeDataStream(config)
    return _realtime_data_stream