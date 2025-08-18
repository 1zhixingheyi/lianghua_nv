"""
QMT交易接口实现

提供QMT接口的封装，支持实盘和模拟交易
"""

import uuid
import time
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import sqlite3
import os

from .base_trader import (
    BaseTrader, Order, Position, Account, 
    OrderType, OrderSide, OrderStatus
)

class SimulatedQMTInterface(BaseTrader):
    """
    模拟QMT交易接口
    
    提供完整的模拟交易功能，用于测试和开发
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化模拟交易接口
        
        Args:
            config: 配置参数
        """
        super().__init__(config)
        
        # 模拟账户配置
        self.initial_cash = config.get('initial_cash', 1000000.0)  # 初始资金100万
        self.commission_rate = config.get('commission_rate', 0.0003)  # 手续费率
        self.min_commission = config.get('min_commission', 5.0)  # 最低手续费
        
        # 内存数据
        self.account = Account(
            account_id=self.account_id,
            total_cash=self.initial_cash,
            available_cash=self.initial_cash,
            total_value=self.initial_cash
        )
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.trades: List[Dict] = []
        
        # 数据库文件
        self.db_path = config.get('db_path', 'trading_simulation.db')
        self._init_database()
        
        # 价格模拟（简单随机游走）
        self.price_cache: Dict[str, float] = {}
        self.price_update_thread = None
        self.price_update_running = False
        
    def _init_database(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else '.', exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建订单表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                filled_quantity INTEGER DEFAULT 0,
                avg_fill_price REAL DEFAULT 0,
                status TEXT NOT NULL,
                create_time TEXT NOT NULL,
                update_time TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def connect(self) -> bool:
        """连接模拟交易接口"""
        try:
            # 模拟连接延迟
            time.sleep(0.1)
            
            # 启动价格更新线程
            self._start_price_update()
            
            self.is_connected = True
            self.logger.info("模拟交易接口连接成功")
            return True
            
        except Exception as e:
            self.logger.error(f"连接模拟交易接口失败: {e}")
            return False
    
    def disconnect(self) -> bool:
        """断开模拟交易接口连接"""
        try:
            # 停止价格更新线程
            self._stop_price_update()
            
            self.is_connected = False
            self.logger.info("模拟交易接口断开连接")
            return True
            
        except Exception as e:
            self.logger.error(f"断开模拟交易接口失败: {e}")
            return False
    
    def get_account_info(self) -> Optional[Account]:
        """获取账户信息"""
        if not self.is_connected:
            self.logger.error("接口未连接")
            return None
        
        # 更新账户信息
        self._update_account()
        return self.account
    
    def get_positions(self) -> List[Position]:
        """获取持仓信息"""
        if not self.is_connected:
            self.logger.error("接口未连接")
            return []
        
        # 更新持仓市值
        for position in self.positions.values():
            current_price = self._get_current_price(position.symbol)
            if current_price > 0:
                position.market_value = position.quantity * current_price
                position.unrealized_pnl = position.market_value - position.quantity * position.avg_price
                position.update_time = datetime.now()
        
        return list(self.positions.values())
    
    def get_orders(self, symbol: str = None) -> List[Order]:
        """获取订单信息"""
        if not self.is_connected:
            self.logger.error("接口未连接")
            return []
        
        orders = list(self.orders.values())
        if symbol:
            orders = [order for order in orders if order.symbol == symbol]
        
        return orders
    
    def submit_order(self, symbol: str, side: OrderSide, order_type: OrderType,
                    quantity: int, price: float = 0) -> Optional[str]:
        """提交订单"""
        if not self.is_connected:
            self.logger.error("接口未连接")
            return None
        
        if not self.is_trading_enabled:
            self.logger.error("交易功能未启用")
            return None
        
        # 验证订单
        is_valid, error_msg = self.validate_order(symbol, side, quantity, price)
        if not is_valid:
            self.logger.error(f"订单验证失败: {error_msg}")
            return None
        
        # 检查资金/持仓
        if not self._check_order_feasibility(symbol, side, quantity, price, order_type):
            return None
        
        # 创建订单
        order_id = str(uuid.uuid4())
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price if order_type != OrderType.MARKET else 0
        )
        
        # 市价单立即成交
        if order_type == OrderType.MARKET:
            current_price = self._get_current_price(symbol)
            if current_price > 0:
                self._execute_order(order, current_price)
            else:
                order.status = OrderStatus.REJECTED
                self.logger.error(f"无法获取{symbol}的当前价格")
        else:
            order.status = OrderStatus.SUBMITTED
        
        self.orders[order_id] = order
        self.logger.info(f"订单提交成功: {order_id}")
        
        return order_id
    
    def cancel_order(self, order_id: str) -> bool:
        """撤销订单"""
        if not self.is_connected:
            self.logger.error("接口未连接")
            return False
        
        if order_id not in self.orders:
            self.logger.error(f"订单不存在: {order_id}")
            return False
        
        order = self.orders[order_id]
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            self.logger.error(f"订单状态无法撤销: {order.status}")
            return False
        
        order.status = OrderStatus.CANCELLED
        order.update_time = datetime.now()
        
        self.logger.info(f"订单撤销成功: {order_id}")
        return True
    
    def get_order_status(self, order_id: str) -> Optional[Order]:
        """查询订单状态"""
        if not self.is_connected:
            self.logger.error("接口未连接")
            return None
        
        return self.orders.get(order_id)
    
    def _check_order_feasibility(self, symbol: str, side: OrderSide, 
                               quantity: int, price: float, order_type: OrderType) -> bool:
        """检查订单可行性"""
        if side == OrderSide.BUY:
            # 检查资金是否充足
            required_cash = quantity * (price if order_type != OrderType.MARKET else self._get_current_price(symbol))
            commission = max(required_cash * self.commission_rate, self.min_commission)
            total_required = required_cash + commission
            
            if self.account.available_cash < total_required:
                self.logger.error(f"资金不足: 需要{total_required:.2f}, 可用{self.account.available_cash:.2f}")
                return False
                
        else:  # 卖出
            # 检查持仓是否充足
            position = self.positions.get(symbol)
            if not position or position.quantity < quantity:
                available = position.quantity if position else 0
                self.logger.error(f"持仓不足: 需要{quantity}, 可用{available}")
                return False
        
        return True
    
    def _execute_order(self, order: Order, execute_price: float):
        """执行订单"""
        try:
            # 计算手续费
            trade_value = order.quantity * execute_price
            commission = max(trade_value * self.commission_rate, self.min_commission)
            
            if order.side == OrderSide.BUY:
                # 买入
                total_cost = trade_value + commission
                
                # 更新账户资金
                self.account.available_cash -= total_cost
                self.account.total_cash -= commission  # 手续费从总资金中扣除
                
                # 更新持仓
                if order.symbol in self.positions:
                    # 已有持仓，计算平均成本
                    position = self.positions[order.symbol]
                    total_quantity = position.quantity + order.quantity
                    total_cost_basis = position.quantity * position.avg_price + trade_value
                    new_avg_price = total_cost_basis / total_quantity
                    
                    position.quantity = total_quantity
                    position.avg_price = new_avg_price
                    position.update_time = datetime.now()
                else:
                    # 新建持仓
                    self.positions[order.symbol] = Position(
                        symbol=order.symbol,
                        quantity=order.quantity,
                        avg_price=execute_price
                    )
                    
            else:  # 卖出
                # 更新持仓
                position = self.positions[order.symbol]
                position.quantity -= order.quantity
                
                # 更新账户资金
                net_proceeds = trade_value - commission
                self.account.available_cash += net_proceeds
                self.account.total_cash -= commission
                
                # 如果持仓为0，删除持仓记录
                if position.quantity == 0:
                    del self.positions[order.symbol]
                else:
                    position.update_time = datetime.now()
            
            # 更新订单状态
            order.filled_quantity = order.quantity
            order.avg_fill_price = execute_price
            order.status = OrderStatus.FILLED
            order.update_time = datetime.now()
            
            self.logger.info(f"订单执行成功: {order.order_id}, 价格: {execute_price}")
            
        except Exception as e:
            order.status = OrderStatus.REJECTED
            self.logger.error(f"订单执行失败: {e}")
    
    def _get_current_price(self, symbol: str) -> float:
        """获取当前价格（模拟）"""
        if symbol not in self.price_cache:
            # 初始价格设为10-100之间的随机值
            import random
            self.price_cache[symbol] = random.uniform(10.0, 100.0)
        
        return self.price_cache[symbol]
    
    def _update_account(self):
        """更新账户信息"""
        # 计算总市值
        total_market_value = 0
        for position in self.positions.values():
            current_price = self._get_current_price(position.symbol)
            if current_price > 0:
                position.market_value = position.quantity * current_price
                total_market_value += position.market_value
        
        # 更新账户信息
        self.account.market_value = total_market_value
        self.account.total_value = self.account.total_cash + total_market_value
        
        # 计算总盈亏
        self.account.total_pnl = self.account.total_value - self.initial_cash
        
        self.account.update_time = datetime.now()
    
    def _start_price_update(self):
        """启动价格更新线程"""
        self.price_update_running = True
        self.price_update_thread = threading.Thread(target=self._price_update_worker)
        self.price_update_thread.daemon = True
        self.price_update_thread.start()
    
    def _stop_price_update(self):
        """停止价格更新线程"""
        self.price_update_running = False
        if self.price_update_thread:
            self.price_update_thread.join(timeout=1)
    
    def _price_update_worker(self):
        """价格更新工作线程"""
        import random
        
        while self.price_update_running:
            try:
                # 模拟价格变动
                for symbol in list(self.price_cache.keys()):
                    if random.random() < 0.1:  # 10%的概率更新价格
                        change_rate = random.uniform(-0.02, 0.02)  # ±2%的变动
                        self.price_cache[symbol] *= (1 + change_rate)
                        self.price_cache[symbol] = max(0.01, self.price_cache[symbol])  # 最低0.01
                
                time.sleep(1)  # 每秒更新一次
                
            except Exception as e:
                self.logger.error(f"价格更新异常: {e}")
                time.sleep(1)