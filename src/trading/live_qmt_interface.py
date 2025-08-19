"""
QMT实盘交易接口实现

提供真实的QMT客户端连接和交易功能
"""

import uuid
import time
import threading
import json
import sqlite3
import os
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
from concurrent.futures import ThreadPoolExecutor
import queue

from .base_trader import (
    BaseTrader, Order, Position, Account, 
    OrderType, OrderSide, OrderStatus
)

@dataclass
class QMTConfig:
    """QMT连接配置"""
    host: str = "127.0.0.1"
    port: int = 16099
    account_id: str = ""
    account_type: str = "STOCK"  # STOCK, FUTURES, OPTIONS
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # 实盘特有配置
    trading_password: str = ""
    authentication_method: str = "password"  # password, certificate
    certificate_path: Optional[str] = None
    encryption_enabled: bool = True
    
    # 风控配置
    enable_order_verification: bool = True
    max_single_order_value: float = 100000.0
    max_daily_trades: int = 1000
    enable_market_hours_check: bool = True

class LiveQMTInterface(BaseTrader):
    """
    QMT实盘交易接口
    
    提供真实的QMT客户端连接和交易功能
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化QMT实盘交易接口
        
        Args:
            config: 配置参数
        """
        super().__init__(config)
        
        # QMT配置
        self.qmt_config = QMTConfig(**config.get('qmt', {}))
        
        # 连接状态
        self.session = None
        self.last_heartbeat = None
        self.connection_retry_count = 0
        
        # 数据缓存
        self.account_cache = None
        self.positions_cache: Dict[str, Position] = {}
        self.orders_cache: Dict[str, Order] = {}
        
        # 线程池和队列
        self.executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="QMT")
        self.order_queue = queue.Queue()
        self.response_queue = queue.Queue()
        
        # 同步锁
        self.connection_lock = threading.Lock()
        self.cache_lock = threading.Lock()
        
        # 监控线程
        self.heartbeat_thread = None
        self.order_worker_thread = None
        self.response_worker_thread = None
        self.monitoring_enabled = False
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'connection_errors': 0,
            'order_submits': 0,
            'order_cancels': 0,
            'last_request_time': None
        }
        
        # 数据库
        self.db_path = config.get('db_path', 'live_trading.db')
        self._init_database()
        
        # 安全检查
        self._init_security_checks()
        
    def _init_database(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else '.', exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建实盘订单表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS live_orders (
                order_id TEXT PRIMARY KEY,
                qmt_order_id TEXT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                filled_quantity INTEGER DEFAULT 0,
                avg_fill_price REAL DEFAULT 0,
                status TEXT NOT NULL,
                create_time TEXT NOT NULL,
                update_time TEXT NOT NULL,
                error_message TEXT,
                commission REAL DEFAULT 0,
                metadata TEXT
            )
        ''')
        
        # 创建实盘成交记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS live_trades (
                trade_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                commission REAL NOT NULL,
                trade_time TEXT NOT NULL,
                counterparty TEXT,
                metadata TEXT,
                FOREIGN KEY (order_id) REFERENCES live_orders (order_id)
            )
        ''')
        
        # 创建连接日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS connection_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT,
                details TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def _init_security_checks(self):
        """初始化安全检查"""
        # 检查配置安全性
        if not self.qmt_config.account_id:
            raise ValueError("账户ID不能为空")
            
        if self.qmt_config.authentication_method == "certificate":
            if not self.qmt_config.certificate_path:
                raise ValueError("证书认证方式需要提供证书路径")
            if not os.path.exists(self.qmt_config.certificate_path):
                raise FileNotFoundError(f"证书文件不存在: {self.qmt_config.certificate_path}")
        
        # 初始化交易限制检查
        self.daily_trade_count = 0
        self.daily_trade_value = 0.0
        self.last_trade_date = None
        
    def connect(self) -> bool:
        """连接QMT客户端"""
        try:
            with self.connection_lock:
                if self.is_connected:
                    self.logger.warning("QMT接口已连接")
                    return True
                
                self.logger.info("正在连接QMT客户端...")
                
                # 创建会话
                self.session = requests.Session()
                self.session.timeout = self.qmt_config.timeout
                
                # 构建连接URL
                base_url = f"http://{self.qmt_config.host}:{self.qmt_config.port}/api"
                
                # 认证请求
                auth_data = {
                    'account_id': self.qmt_config.account_id,
                    'account_type': self.qmt_config.account_type
                }
                
                if self.qmt_config.authentication_method == "password":
                    auth_data['password'] = self.qmt_config.trading_password
                elif self.qmt_config.authentication_method == "certificate":
                    # 证书认证逻辑
                    auth_data['certificate'] = self._load_certificate()
                
                # 发送认证请求
                response = self._make_request('POST', f"{base_url}/auth", auth_data)
                
                if response and response.get('status') == 'success':
                    # 保存认证token
                    self.session.headers.update({
                        'Authorization': f"Bearer {response.get('token')}",
                        'Content-Type': 'application/json'
                    })
                    
                    # 验证连接
                    if self._verify_connection():
                        self.is_connected = True
                        self.connection_retry_count = 0
                        
                        # 启动监控线程
                        self._start_monitoring()
                        
                        # 初始化缓存
                        self._refresh_all_cache()
                        
                        self._log_connection_event('CONNECTED', '成功连接到QMT客户端')
                        self.logger.info("QMT客户端连接成功")
                        return True
                    else:
                        self.logger.error("连接验证失败")
                        return False
                else:
                    error_msg = response.get('message', '认证失败') if response else '无响应'
                    self.logger.error(f"QMT认证失败: {error_msg}")
                    return False
                    
        except Exception as e:
            self._log_connection_event('CONNECTION_ERROR', f'连接失败: {str(e)}')
            self.logger.error(f"连接QMT客户端失败: {e}")
            self.connection_retry_count += 1
            
            # 自动重连机制
            if self.connection_retry_count < self.qmt_config.max_retries:
                self.logger.info(f"将在{self.qmt_config.retry_delay}秒后重试连接...")
                time.sleep(self.qmt_config.retry_delay)
                return self.connect()
            
            return False
    
    def disconnect(self) -> bool:
        """断开QMT连接"""
        try:
            with self.connection_lock:
                if not self.is_connected:
                    return True
                
                self.logger.info("正在断开QMT连接...")
                
                # 停止监控
                self._stop_monitoring()
                
                # 发送断开连接请求
                if self.session:
                    try:
                        self._make_request('POST', '/api/disconnect', {})
                    except:
                        pass  # 忽略断开连接时的错误
                    
                    self.session.close()
                    self.session = None
                
                self.is_connected = False
                self._log_connection_event('DISCONNECTED', 'QMT连接已断开')
                self.logger.info("QMT连接已断开")
                
                # 清理资源
                self.executor.shutdown(wait=True)
                
                return True
                
        except Exception as e:
            self.logger.error(f"断开QMT连接失败: {e}")
            return False
    
    def get_account_info(self) -> Optional[Account]:
        """获取账户信息"""
        if not self.is_connected:
            self.logger.error("QMT接口未连接")
            return None
        
        try:
            response = self._make_request('GET', '/api/account/info', {})
            
            if response and response.get('status') == 'success':
                data = response.get('data', {})
                
                account = Account(
                    account_id=self.account_id,
                    total_value=float(data.get('total_asset', 0)),
                    available_cash=float(data.get('available_cash', 0)),
                    total_cash=float(data.get('total_cash', 0)),
                    market_value=float(data.get('market_value', 0)),
                    total_pnl=float(data.get('total_pnl', 0))
                )
                
                # 更新缓存
                with self.cache_lock:
                    self.account_cache = account
                
                return account
            else:
                self.logger.error(f"获取账户信息失败: {response.get('message', '未知错误') if response else '无响应'}")
                return None
                
        except Exception as e:
            self.logger.error(f"获取账户信息异常: {e}")
            return None
    
    def get_positions(self) -> List[Position]:
        """获取持仓信息"""
        if not self.is_connected:
            self.logger.error("QMT接口未连接")
            return []
        
        try:
            response = self._make_request('GET', '/api/positions', {})
            
            if response and response.get('status') == 'success':
                positions = []
                positions_data = response.get('data', [])
                
                for pos_data in positions_data:
                    position = Position(
                        symbol=pos_data.get('symbol', ''),
                        quantity=int(pos_data.get('quantity', 0)),
                        avg_price=float(pos_data.get('avg_price', 0)),
                        market_value=float(pos_data.get('market_value', 0)),
                        unrealized_pnl=float(pos_data.get('unrealized_pnl', 0))
                    )
                    positions.append(position)
                
                # 更新缓存
                with self.cache_lock:
                    self.positions_cache = {pos.symbol: pos for pos in positions}
                
                return positions
            else:
                self.logger.error(f"获取持仓信息失败: {response.get('message', '未知错误') if response else '无响应'}")
                return []
                
        except Exception as e:
            self.logger.error(f"获取持仓信息异常: {e}")
            return []
    
    def get_orders(self, symbol: str = None) -> List[Order]:
        """获取订单信息"""
        if not self.is_connected:
            self.logger.error("QMT接口未连接")
            return []
        
        try:
            params = {'symbol': symbol} if symbol else {}
            response = self._make_request('GET', '/api/orders', params)
            
            if response and response.get('status') == 'success':
                orders = []
                orders_data = response.get('data', [])
                
                for order_data in orders_data:
                    order = self._parse_order_response(order_data)
                    if order:
                        orders.append(order)
                
                # 更新缓存
                with self.cache_lock:
                    for order in orders:
                        self.orders_cache[order.order_id] = order
                
                return orders
            else:
                self.logger.error(f"获取订单信息失败: {response.get('message', '未知错误') if response else '无响应'}")
                return []
                
        except Exception as e:
            self.logger.error(f"获取订单信息异常: {e}")
            return []
    
    def submit_order(self, symbol: str, side: OrderSide, order_type: OrderType,
                    quantity: int, price: float = 0) -> Optional[str]:
        """提交订单"""
        if not self.is_connected:
            self.logger.error("QMT接口未连接")
            return None
        
        if not self.is_trading_enabled:
            self.logger.error("交易功能未启用")
            return None
        
        # 验证订单
        is_valid, error_msg = self.validate_order(symbol, side, quantity, price)
        if not is_valid:
            self.logger.error(f"订单验证失败: {error_msg}")
            return None
        
        # 安全检查
        if not self._security_check_order(symbol, side, quantity, price):
            return None
        
        try:
            order_id = str(uuid.uuid4())
            
            # 构建订单数据
            order_data = {
                'client_order_id': order_id,
                'symbol': symbol,
                'side': side.value,
                'order_type': order_type.value,
                'quantity': quantity,
                'price': price if order_type != OrderType.MARKET else 0
            }
            
            # 提交订单到QMT
            response = self._make_request('POST', '/api/orders', order_data)
            
            if response and response.get('status') == 'success':
                qmt_order_id = response.get('data', {}).get('order_id')
                
                # 创建订单记录
                order = Order(
                    order_id=order_id,
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    price=price if order_type != OrderType.MARKET else 0
                )
                order.status = OrderStatus.SUBMITTED
                
                # 保存订单到数据库
                self._save_order_to_db(order, qmt_order_id)
                
                # 更新缓存
                with self.cache_lock:
                    self.orders_cache[order_id] = order
                
                # 更新统计
                self.stats['order_submits'] += 1
                self._update_daily_trade_stats(quantity * price)
                
                self.logger.info(f"订单提交成功: {order_id} -> QMT: {qmt_order_id}")
                return order_id
            else:
                error_msg = response.get('message', '提交失败') if response else '无响应'
                self.logger.error(f"订单提交失败: {error_msg}")
                return None
                
        except Exception as e:
            self.logger.error(f"提交订单异常: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """撤销订单"""
        if not self.is_connected:
            self.logger.error("QMT接口未连接")
            return False
        
        try:
            # 查找订单
            order = self.orders_cache.get(order_id)
            if not order:
                # 从数据库查找
                order = self._load_order_from_db(order_id)
                if not order:
                    self.logger.error(f"订单不存在: {order_id}")
                    return False
            
            if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                self.logger.error(f"订单状态无法撤销: {order.status}")
                return False
            
            # 获取QMT订单ID
            qmt_order_id = self._get_qmt_order_id(order_id)
            if not qmt_order_id:
                self.logger.error(f"无法获取QMT订单ID: {order_id}")
                return False
            
            # 发送撤单请求
            cancel_data = {
                'order_id': qmt_order_id,
                'client_order_id': order_id
            }
            
            response = self._make_request('POST', '/api/orders/cancel', cancel_data)
            
            if response and response.get('status') == 'success':
                # 更新订单状态
                order.status = OrderStatus.CANCELLED
                order.update_time = datetime.now()
                
                # 更新缓存和数据库
                with self.cache_lock:
                    self.orders_cache[order_id] = order
                self._update_order_in_db(order)
                
                # 更新统计
                self.stats['order_cancels'] += 1
                
                self.logger.info(f"订单撤销成功: {order_id}")
                return True
            else:
                error_msg = response.get('message', '撤销失败') if response else '无响应'
                self.logger.error(f"订单撤销失败: {error_msg}")
                return False
                
        except Exception as e:
            self.logger.error(f"撤销订单异常: {e}")
            return False
    
    def get_order_status(self, order_id: str) -> Optional[Order]:
        """查询订单状态"""
        if not self.is_connected:
            self.logger.error("QMT接口未连接")
            return None
        
        try:
            # 先从缓存查找
            order = self.orders_cache.get(order_id)
            if order:
                return order
            
            # 从数据库查找
            order = self._load_order_from_db(order_id)
            if order:
                # 查询最新状态
                qmt_order_id = self._get_qmt_order_id(order_id)
                if qmt_order_id:
                    response = self._make_request('GET', f'/api/orders/{qmt_order_id}', {})
                    if response and response.get('status') == 'success':
                        updated_order = self._parse_order_response(response.get('data', {}))
                        if updated_order:
                            # 更新缓存
                            with self.cache_lock:
                                self.orders_cache[order_id] = updated_order
                            return updated_order
                
                return order
            
            return None
            
        except Exception as e:
            self.logger.error(f"查询订单状态异常: {e}")
            return None
    
    def _make_request(self, method: str, endpoint: str, data: Dict) -> Optional[Dict]:
        """发送HTTP请求"""
        try:
            self.stats['total_requests'] += 1
            self.stats['last_request_time'] = datetime.now()
            
            url = f"http://{self.qmt_config.host}:{self.qmt_config.port}{endpoint}"
            
            if method.upper() == 'GET':
                response = self.session.get(url, params=data, timeout=self.qmt_config.timeout)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, timeout=self.qmt_config.timeout)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
            
            response.raise_for_status()
            result = response.json()
            
            self.stats['successful_requests'] += 1
            return result
            
        except requests.exceptions.RequestException as e:
            self.stats['failed_requests'] += 1
            self.stats['connection_errors'] += 1
            self.logger.error(f"HTTP请求失败: {e}")
            return None
        except Exception as e:
            self.stats['failed_requests'] += 1
            self.logger.error(f"请求处理异常: {e}")
            return None
    
    def _verify_connection(self) -> bool:
        """验证连接状态"""
        try:
            response = self._make_request('GET', '/api/health', {})
            return response and response.get('status') == 'success'
        except:
            return False
    
    def _start_monitoring(self):
        """启动监控线程"""
        self.monitoring_enabled = True
        
        # 心跳监控线程
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_worker, daemon=True)
        self.heartbeat_thread.start()
        
        # 订单处理线程
        self.order_worker_thread = threading.Thread(target=self._order_worker, daemon=True)
        self.order_worker_thread.start()
        
        # 响应处理线程
        self.response_worker_thread = threading.Thread(target=self._response_worker, daemon=True)
        self.response_worker_thread.start()
    
    def _stop_monitoring(self):
        """停止监控线程"""
        self.monitoring_enabled = False
        
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=5)
        if self.order_worker_thread:
            self.order_worker_thread.join(timeout=5)
        if self.response_worker_thread:
            self.response_worker_thread.join(timeout=5)
    
    def _heartbeat_worker(self):
        """心跳工作线程"""
        while self.monitoring_enabled and self.is_connected:
            try:
                if self._verify_connection():
                    self.last_heartbeat = datetime.now()
                else:
                    self.logger.warning("心跳检查失败，尝试重连...")
                    if not self.connect():
                        self.logger.error("重连失败")
                        break
                
                time.sleep(30)  # 30秒心跳间隔
                
            except Exception as e:
                self.logger.error(f"心跳线程异常: {e}")
                time.sleep(5)
    
    def _order_worker(self):
        """订单处理工作线程"""
        while self.monitoring_enabled:
            try:
                # 处理订单队列
                if not self.order_queue.empty():
                    order_data = self.order_queue.get(timeout=1)
                    # 处理订单逻辑
                    self._process_order_update(order_data)
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"订单处理线程异常: {e}")
    
    def _response_worker(self):
        """响应处理工作线程"""
        while self.monitoring_enabled:
            try:
                # 处理响应队列
                if not self.response_queue.empty():
                    response_data = self.response_queue.get(timeout=1)
                    # 处理响应逻辑
                    self._process_response(response_data)
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"响应处理线程异常: {e}")
    
    def _security_check_order(self, symbol: str, side: OrderSide, quantity: int, price: float) -> bool:
        """订单安全检查"""
        try:
            # 检查交易时间
            if self.qmt_config.enable_market_hours_check and not self._is_trading_hours():
                self.logger.error("当前不在交易时间内")
                return False
            
            # 检查单笔订单金额
            order_value = quantity * price
            if order_value > self.qmt_config.max_single_order_value:
                self.logger.error(f"订单金额超过限制: {order_value} > {self.qmt_config.max_single_order_value}")
                return False
            
            # 检查日交易次数
            today = datetime.now().date()
            if self.last_trade_date != today:
                self.daily_trade_count = 0
                self.daily_trade_value = 0.0
                self.last_trade_date = today
            
            if self.daily_trade_count >= self.qmt_config.max_daily_trades:
                self.logger.error(f"今日交易次数已达上限: {self.daily_trade_count}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"安全检查异常: {e}")
            return False
    
    def _is_trading_hours(self) -> bool:
        """检查是否在交易时间内"""
        now = datetime.now()
        current_time = now.time()
        weekday = now.weekday()
        
        # 周末不交易
        if weekday >= 5:
            return False
        
        # 上午交易时间: 9:30-11:30
        morning_start = time(9, 30)
        morning_end = time(11, 30)
        
        # 下午交易时间: 13:00-15:00
        afternoon_start = time(13, 0)
        afternoon_end = time(15, 0)
        
        return (morning_start <= current_time <= morning_end) or \
               (afternoon_start <= current_time <= afternoon_end)
    
    def _update_daily_trade_stats(self, trade_value: float):
        """更新日交易统计"""
        self.daily_trade_count += 1
        self.daily_trade_value += trade_value
    
    def _refresh_all_cache(self):
        """刷新所有缓存"""
        try:
            self.get_account_info()
            self.get_positions()
            self.get_orders()
        except Exception as e:
            self.logger.error(f"刷新缓存失败: {e}")
    
    def _load_certificate(self) -> str:
        """加载证书文件"""
        if not self.qmt_config.certificate_path:
            raise ValueError("证书路径为空")
        
        with open(self.qmt_config.certificate_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _parse_order_response(self, order_data: Dict) -> Optional[Order]:
        """解析订单响应"""
        try:
            order = Order(
                order_id=order_data.get('client_order_id', ''),
                symbol=order_data.get('symbol', ''),
                side=OrderSide(order_data.get('side', '')),
                order_type=OrderType(order_data.get('order_type', '')),
                quantity=int(order_data.get('quantity', 0)),
                price=float(order_data.get('price', 0)),
                filled_quantity=int(order_data.get('filled_quantity', 0)),
                avg_fill_price=float(order_data.get('avg_fill_price', 0))
            )
            order.status = OrderStatus(order_data.get('status', 'pending'))
            
            return order
        except Exception as e:
            self.logger.error(f"解析订单响应失败: {e}")
            return None
    
    def _save_order_to_db(self, order: Order, qmt_order_id: str):
        """保存订单到数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO live_orders 
                (order_id, qmt_order_id, symbol, side, order_type, quantity, price, 
                 filled_quantity, avg_fill_price, status, create_time, update_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                order.order_id, qmt_order_id, order.symbol, order.side.value,
                order.order_type.value, order.quantity, order.price,
                order.filled_quantity, order.avg_fill_price, order.status.value,
                order.create_time.isoformat(), order.update_time.isoformat()
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"保存订单到数据库失败: {e}")
    
    def _update_order_in_db(self, order: Order):
        """更新数据库中的订单"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE live_orders SET
                filled_quantity = ?, avg_fill_price = ?, status = ?, update_time = ?
                WHERE order_id = ?
            ''', (
                order.filled_quantity, order.avg_fill_price, order.status.value,
                order.update_time.isoformat(), order.order_id
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"更新数据库订单失败: {e}")
    
    def _load_order_from_db(self, order_id: str) -> Optional[Order]:
        """从数据库加载订单"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT symbol, side, order_type, quantity, price, filled_quantity,
                       avg_fill_price, status, create_time, update_time
                FROM live_orders WHERE order_id = ?
            ''', (order_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                order = Order(
                    order_id=order_id,
                    symbol=row[0],
                    side=OrderSide(row[1]),
                    order_type=OrderType(row[2]),
                    quantity=int(row[3]),
                    price=float(row[4]),
                    filled_quantity=int(row[5]),
                    avg_fill_price=float(row[6])
                )
                order.status = OrderStatus(row[7])
                order.create_time = datetime.fromisoformat(row[8])
                order.update_time = datetime.fromisoformat(row[9])
                
                return order
            
            return None
            
        except Exception as e:
            self.logger.error(f"从数据库加载订单失败: {e}")
            return None
    
    def _get_qmt_order_id(self, client_order_id: str) -> Optional[str]:
        """获取QMT订单ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT qmt_order_id FROM live_orders WHERE order_id = ?', (client_order_id,))
            row = cursor.fetchone()
            conn.close()
            
            return row[0] if row else None
            
        except Exception as e:
            self.logger.error(f"获取QMT订单ID失败: {e}")
            return None
    
    def _log_connection_event(self, event_type: str, message: str, details: Dict = None):
        """记录连接事件"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO connection_log (timestamp, event_type, message, details)
                VALUES (?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(), event_type, message,
                json.dumps(details) if details else None
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"记录连接事件失败: {e}")
    
    def _process_order_update(self, order_data: Dict):
        """处理订单更新"""
        # 实现订单状态更新逻辑
        pass
    
    def _process_response(self, response_data: Dict):
        """处理响应数据"""
        # 实现响应处理逻辑
        pass
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """获取连接统计信息"""
        return {
            'is_connected': self.is_connected,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'connection_retry_count': self.connection_retry_count,
            'daily_trade_count': self.daily_trade_count,
            'daily_trade_value': self.daily_trade_value,
            'stats': self.stats.copy()
        }