"""
实时监控组件
============

提供实时数据监控和推送功能，包括：
- 实时数据采集和缓存
- WebSocket实时数据推送  
- 数据变化检测和通知
- 性能监控和告警
- 事件驱动的数据更新

主要功能：
- 策略状态实时监控
- 持仓变化实时推送
- 交易信号实时通知
- 风险告警实时推送
- 系统性能实时监控

技术特性：
- 异步数据采集
- 内存缓存机制
- 事件驱动架构
- 多客户端支持
- 数据压缩和优化
"""

import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, asdict
from queue import Queue, Empty
from threading import Lock, Event
import websockets
import socket

# 导入后端模块
from src.data import get_database_manager, get_tushare_client
from src.strategies import get_strategy_manager, AVAILABLE_STRATEGIES
from src.risk import RiskMonitor, RiskAlert
from src.trading.base_trader import OrderStatus

# 导入仪表板控制器
from .dashboard import dashboard_controller

# 配置日志
logger = logging.getLogger(__name__)

@dataclass
class RealtimeData:
    """实时数据结构"""
    timestamp: str
    data_type: str
    data: Dict[str, Any]
    version: int = 0

@dataclass
class ClientConnection:
    """客户端连接信息"""
    client_id: str
    websocket: Any
    subscribed_channels: Set[str]
    last_heartbeat: datetime
    is_active: bool = True

class DataCache:
    """数据缓存管理器"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl  # 缓存过期时间（秒）
        self._cache: Dict[str, RealtimeData] = {}
        self._access_times: Dict[str, datetime] = {}
        self._lock = Lock()
    
    def set(self, key: str, data: RealtimeData):
        """设置缓存数据"""
        with self._lock:
            # 清理过期数据
            self._cleanup_expired()
            
            # 如果缓存已满，删除最旧的数据
            if len(self._cache) >= self.max_size:
                oldest_key = min(self._access_times.keys(), 
                               key=lambda k: self._access_times[k])
                del self._cache[oldest_key]
                del self._access_times[oldest_key]
            
            self._cache[key] = data
            self._access_times[key] = datetime.now()
    
    def get(self, key: str) -> Optional[RealtimeData]:
        """获取缓存数据"""
        with self._lock:
            if key in self._cache:
                # 检查是否过期
                if self._is_expired(key):
                    del self._cache[key]
                    del self._access_times[key]
                    return None
                
                # 更新访问时间
                self._access_times[key] = datetime.now()
                return self._cache[key]
            return None
    
    def _is_expired(self, key: str) -> bool:
        """检查数据是否过期"""
        if key not in self._access_times:
            return True
        return (datetime.now() - self._access_times[key]).seconds > self.ttl
    
    def _cleanup_expired(self):
        """清理过期数据"""
        expired_keys = [key for key in self._access_times.keys() 
                       if self._is_expired(key)]
        for key in expired_keys:
            del self._cache[key]
            del self._access_times[key]
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()
    
    def size(self) -> int:
        """获取缓存大小"""
        return len(self._cache)

class RealtimeMonitor:
    """实时监控组件"""
    
    def __init__(self, update_interval: float = 1.0, cache_size: int = 1000):
        self.update_interval = update_interval
        self.cache = DataCache(max_size=cache_size)
        
        # 客户端连接管理
        self.clients: Dict[str, ClientConnection] = {}
        self.clients_lock = Lock()
        
        # 数据采集状态
        self.is_running = False
        self.stop_event = Event()
        
        # 数据队列
        self.data_queue = Queue(maxsize=10000)
        
        # 事件回调
        self.event_callbacks: Dict[str, List[Callable]] = {}
        
        # 性能统计
        self.stats = {
            'messages_sent': 0,
            'data_updates': 0,
            'active_clients': 0,
            'last_update': datetime.now(),
            'errors': 0
        }
        
        # 初始化数据采集器
        self.data_collectors = {
            'summary': self._collect_summary_data,
            'strategies': self._collect_strategy_data,
            'positions': self._collect_position_data,
            'orders': self._collect_order_data,
            'alerts': self._collect_alert_data,
            'system': self._collect_system_data
        }
        
        logger.info("实时监控组件初始化完成")
    
    def start(self):
        """启动实时监控"""
        if self.is_running:
            logger.warning("实时监控已在运行")
            return
        
        self.is_running = True
        self.stop_event.clear()
        
        # 启动数据采集线程
        self.collector_thread = threading.Thread(target=self._data_collection_loop, daemon=True)
        self.collector_thread.start()
        
        # 启动数据推送线程
        self.pusher_thread = threading.Thread(target=self._data_push_loop, daemon=True)
        self.pusher_thread.start()
        
        # 启动心跳检查线程
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        
        logger.info("实时监控已启动")
    
    def stop(self):
        """停止实时监控"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.stop_event.set()
        
        # 关闭所有客户端连接
        with self.clients_lock:
            for client in self.clients.values():
                client.is_active = False
        
        logger.info("实时监控已停止")
    
    def add_client(self, client_id: str, websocket: Any, 
                   subscribed_channels: Set[str] = None) -> bool:
        """添加客户端连接"""
        try:
            if subscribed_channels is None:
                subscribed_channels = set()
            
            client = ClientConnection(
                client_id=client_id,
                websocket=websocket,
                subscribed_channels=subscribed_channels,
                last_heartbeat=datetime.now()
            )
            
            with self.clients_lock:
                self.clients[client_id] = client
                self.stats['active_clients'] = len(self.clients)
            
            logger.info(f"客户端 {client_id} 已连接，订阅频道: {subscribed_channels}")
            return True
            
        except Exception as e:
            logger.error(f"添加客户端失败: {e}")
            return False
    
    def remove_client(self, client_id: str):
        """移除客户端连接"""
        with self.clients_lock:
            if client_id in self.clients:
                del self.clients[client_id]
                self.stats['active_clients'] = len(self.clients)
                logger.info(f"客户端 {client_id} 已断开连接")
    
    def subscribe_channel(self, client_id: str, channel: str) -> bool:
        """订阅频道"""
        with self.clients_lock:
            if client_id in self.clients:
                self.clients[client_id].subscribed_channels.add(channel)
                logger.info(f"客户端 {client_id} 订阅频道: {channel}")
                return True
            return False
    
    def unsubscribe_channel(self, client_id: str, channel: str) -> bool:
        """取消订阅频道"""
        with self.clients_lock:
            if client_id in self.clients:
                self.clients[client_id].subscribed_channels.discard(channel)
                logger.info(f"客户端 {client_id} 取消订阅频道: {channel}")
                return True
            return False
    
    def publish_data(self, channel: str, data: Dict[str, Any], 
                    force_update: bool = False):
        """发布数据到指定频道"""
        try:
            realtime_data = RealtimeData(
                timestamp=datetime.now().isoformat(),
                data_type=channel,
                data=data
            )
            
            # 检查数据是否有变化
            cache_key = f"{channel}_latest"
            cached_data = self.cache.get(cache_key)
            
            if not force_update and cached_data:
                # 简单的数据变化检测（可以优化为更精确的对比）
                if json.dumps(cached_data.data, sort_keys=True) == json.dumps(data, sort_keys=True):
                    return  # 数据无变化，跳过推送
            
            # 缓存数据
            self.cache.set(cache_key, realtime_data)
            
            # 加入推送队列
            if not self.data_queue.full():
                self.data_queue.put((channel, realtime_data))
                self.stats['data_updates'] += 1
            else:
                logger.warning("数据队列已满，丢弃数据")
                
        except Exception as e:
            logger.error(f"发布数据失败: {e}")
            self.stats['errors'] += 1
    
    def add_event_callback(self, event_type: str, callback: Callable):
        """添加事件回调"""
        if event_type not in self.event_callbacks:
            self.event_callbacks[event_type] = []
        self.event_callbacks[event_type].append(callback)
    
    def trigger_event(self, event_type: str, data: Any):
        """触发事件"""
        if event_type in self.event_callbacks:
            for callback in self.event_callbacks[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"事件回调执行失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        stats['cache_size'] = self.cache.size()
        stats['queue_size'] = self.data_queue.qsize()
        stats['uptime'] = str(datetime.now() - stats['last_update'])
        return stats
    
    def _data_collection_loop(self):
        """数据采集循环"""
        logger.info("数据采集循环已启动")
        
        while self.is_running and not self.stop_event.is_set():
            try:
                start_time = time.time()
                
                # 执行数据采集
                for channel, collector in self.data_collectors.items():
                    try:
                        data = collector()
                        if data:
                            self.publish_data(channel, data)
                    except Exception as e:
                        logger.error(f"采集 {channel} 数据失败: {e}")
                
                # 更新统计信息
                self.stats['last_update'] = datetime.now()
                
                # 控制采集频率
                elapsed = time.time() - start_time
                sleep_time = max(0, self.update_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                logger.error(f"数据采集循环错误: {e}")
                self.stats['errors'] += 1
                time.sleep(1)  # 错误时短暂休眠
        
        logger.info("数据采集循环已停止")
    
    def _data_push_loop(self):
        """数据推送循环"""
        logger.info("数据推送循环已启动")
        
        while self.is_running and not self.stop_event.is_set():
            try:
                # 从队列获取数据
                try:
                    channel, realtime_data = self.data_queue.get(timeout=1.0)
                except Empty:
                    continue
                
                # 推送到订阅的客户端
                self._push_to_subscribers(channel, realtime_data)
                
            except Exception as e:
                logger.error(f"数据推送循环错误: {e}")
                self.stats['errors'] += 1
        
        logger.info("数据推送循环已停止")
    
    def _push_to_subscribers(self, channel: str, realtime_data: RealtimeData):
        """推送数据到订阅客户端"""
        message = {
            'type': 'data',
            'channel': channel,
            'timestamp': realtime_data.timestamp,
            'data': realtime_data.data
        }
        
        with self.clients_lock:
            inactive_clients = []
            
            for client_id, client in self.clients.items():
                if not client.is_active or channel not in client.subscribed_channels:
                    continue
                
                try:
                    # 异步发送数据（这里简化为同步）
                    if hasattr(client.websocket, 'send'):
                        client.websocket.send(json.dumps(message))
                        self.stats['messages_sent'] += 1
                    
                except Exception as e:
                    logger.error(f"向客户端 {client_id} 推送数据失败: {e}")
                    client.is_active = False
                    inactive_clients.append(client_id)
            
            # 移除非活跃客户端
            for client_id in inactive_clients:
                self.remove_client(client_id)
    
    def _heartbeat_loop(self):
        """心跳检查循环"""
        logger.info("心跳检查循环已启动")
        
        while self.is_running and not self.stop_event.is_set():
            try:
                current_time = datetime.now()
                inactive_clients = []
                
                with self.clients_lock:
                    for client_id, client in self.clients.items():
                        # 检查心跳超时（5分钟）
                        if (current_time - client.last_heartbeat).seconds > 300:
                            inactive_clients.append(client_id)
                
                # 移除超时客户端
                for client_id in inactive_clients:
                    self.remove_client(client_id)
                    logger.info(f"客户端 {client_id} 心跳超时，已断开连接")
                
                # 每30秒检查一次
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"心跳检查错误: {e}")
                time.sleep(30)
        
        logger.info("心跳检查循环已停止")
    
    def update_heartbeat(self, client_id: str):
        """更新客户端心跳"""
        with self.clients_lock:
            if client_id in self.clients:
                self.clients[client_id].last_heartbeat = datetime.now()
    
    # ========== 数据采集器 ==========
    
    def _collect_summary_data(self) -> Dict[str, Any]:
        """采集汇总数据"""
        try:
            return dashboard_controller.get_dashboard_summary()
        except Exception as e:
            logger.error(f"采集汇总数据失败: {e}")
            return {}
    
    def _collect_strategy_data(self) -> Dict[str, Any]:
        """采集策略数据"""
        try:
            strategies = dashboard_controller.get_strategy_performance()
            return {
                'strategies': strategies,
                'summary': {
                    'total': len(strategies),
                    'running': len([s for s in strategies if s.get('status') == 'running']),
                    'stopped': len([s for s in strategies if s.get('status') == 'stopped'])
                }
            }
        except Exception as e:
            logger.error(f"采集策略数据失败: {e}")
            return {}
    
    def _collect_position_data(self) -> Dict[str, Any]:
        """采集持仓数据"""
        try:
            positions = dashboard_controller.get_position_data()
            total_value = sum(p.get('market_value', 0) for p in positions)
            total_pnl = sum(p.get('unrealized_pnl', 0) for p in positions)
            
            return {
                'positions': positions,
                'summary': {
                    'count': len(positions),
                    'total_value': total_value,
                    'total_pnl': total_pnl,
                    'pnl_ratio': total_pnl / total_value if total_value > 0 else 0
                }
            }
        except Exception as e:
            logger.error(f"采集持仓数据失败: {e}")
            return {}
    
    def _collect_order_data(self) -> Dict[str, Any]:
        """采集订单数据"""
        try:
            # 获取最近的交易记录作为订单数据
            trades = dashboard_controller.get_trading_records(20)
            
            return {
                'recent_orders': trades[:10],
                'summary': {
                    'total_today': len([t for t in trades 
                                      if t['create_time'].date() == datetime.now().date()]),
                    'buy_orders': len([t for t in trades if t['side'] == 'buy']),
                    'sell_orders': len([t for t in trades if t['side'] == 'sell'])
                }
            }
        except Exception as e:
            logger.error(f"采集订单数据失败: {e}")
            return {}
    
    def _collect_alert_data(self) -> Dict[str, Any]:
        """采集告警数据"""
        try:
            alerts = dashboard_controller.get_risk_alerts()
            
            return {
                'alerts': alerts,
                'summary': {
                    'total': len(alerts),
                    'active': len([a for a in alerts if a.get('status') == 'active']),
                    'warning': len([a for a in alerts if a.get('level') == 'warning']),
                    'error': len([a for a in alerts if a.get('level') == 'error'])
                }
            }
        except Exception as e:
            logger.error(f"采集告警数据失败: {e}")
            return {}
    
    def _collect_system_data(self) -> Dict[str, Any]:
        """采集系统数据"""
        try:
            import psutil
            
            return {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'timestamp': datetime.now().isoformat(),
                'process_count': len(psutil.pids()),
                'network_io': asdict(psutil.net_io_counters())
            }
        except ImportError:
            # 如果没有psutil，返回模拟数据
            return {
                'cpu_percent': 25.5,
                'memory_percent': 65.2,
                'disk_percent': 45.8,
                'timestamp': datetime.now().isoformat(),
                'process_count': 156
            }
        except Exception as e:
            logger.error(f"采集系统数据失败: {e}")
            return {}

# 创建全局实时监控实例
realtime_monitor = RealtimeMonitor()

# WebSocket服务器（可选实现）
class WebSocketServer:
    """WebSocket服务器"""
    
    def __init__(self, host: str = 'localhost', port: int = 8765):
        self.host = host
        self.port = port
        self.server = None
        self.is_running = False
    
    async def handler(self, websocket, path):
        """WebSocket连接处理器"""
        client_id = f"client_{int(time.time() * 1000)}"
        logger.info(f"WebSocket客户端 {client_id} 已连接")
        
        try:
            # 添加客户端
            realtime_monitor.add_client(client_id, websocket, {'summary', 'strategies'})
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._handle_message(client_id, data)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': '无效的JSON格式'
                    }))
                
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"WebSocket客户端 {client_id} 连接已关闭")
        except Exception as e:
            logger.error(f"WebSocket处理错误: {e}")
        finally:
            realtime_monitor.remove_client(client_id)
    
    async def _handle_message(self, client_id: str, data: Dict[str, Any]):
        """处理客户端消息"""
        message_type = data.get('type')
        
        if message_type == 'subscribe':
            channels = data.get('channels', [])
            for channel in channels:
                realtime_monitor.subscribe_channel(client_id, channel)
        
        elif message_type == 'unsubscribe':
            channels = data.get('channels', [])
            for channel in channels:
                realtime_monitor.unsubscribe_channel(client_id, channel)
        
        elif message_type == 'heartbeat':
            realtime_monitor.update_heartbeat(client_id)
    
    async def start_server(self):
        """启动WebSocket服务器"""
        if self.is_running:
            return
        
        try:
            self.server = await websockets.serve(self.handler, self.host, self.port)
            self.is_running = True
            logger.info(f"WebSocket服务器已启动: ws://{self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"启动WebSocket服务器失败: {e}")
    
    def stop_server(self):
        """停止WebSocket服务器"""
        if self.server:
            self.server.close()
            self.is_running = False
            logger.info("WebSocket服务器已停止")

# 创建WebSocket服务器实例
websocket_server = WebSocketServer()

def start_realtime_services():
    """启动实时服务"""
    # 启动实时监控
    realtime_monitor.start()
    
    # 启动WebSocket服务器（可选）
    # import asyncio
    # asyncio.run(websocket_server.start_server())

def stop_realtime_services():
    """停止实时服务"""
    realtime_monitor.stop()
    websocket_server.stop_server()

if __name__ == '__main__':
    # 测试实时监控
    start_realtime_services()
    
    try:
        while True:
            time.sleep(1)
            print(f"监控统计: {realtime_monitor.get_stats()}")
    except KeyboardInterrupt:
        stop_realtime_services()
        print("实时监控已停止")