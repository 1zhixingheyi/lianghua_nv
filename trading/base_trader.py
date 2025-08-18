"""
交易接口基类

定义所有交易接口必须实现的标准方法和属性
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from enum import Enum
import logging
from datetime import datetime

class OrderType(Enum):
    """订单类型"""
    MARKET = "market"      # 市价单
    LIMIT = "limit"        # 限价单
    STOP = "stop"          # 止损单
    STOP_LIMIT = "stop_limit"  # 止损限价单

class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"           # 买入
    SELL = "sell"         # 卖出

class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"           # 待报
    SUBMITTED = "submitted"       # 已报
    PARTIAL_FILLED = "partial_filled"  # 部分成交
    FILLED = "filled"            # 全部成交
    CANCELLED = "cancelled"      # 已撤销
    REJECTED = "rejected"        # 已拒绝
    EXPIRED = "expired"          # 已过期

class Position:
    """持仓信息"""
    def __init__(self, symbol: str, quantity: int, avg_price: float, 
                 market_value: float = 0, unrealized_pnl: float = 0):
        self.symbol = symbol
        self.quantity = quantity
        self.avg_price = avg_price
        self.market_value = market_value
        self.unrealized_pnl = unrealized_pnl
        self.update_time = datetime.now()

class Order:
    """订单信息"""
    def __init__(self, order_id: str, symbol: str, side: OrderSide,
                 order_type: OrderType, quantity: int, price: float = 0,
                 filled_quantity: int = 0, avg_fill_price: float = 0):
        self.order_id = order_id
        self.symbol = symbol
        self.side = side
        self.order_type = order_type
        self.quantity = quantity
        self.price = price
        self.filled_quantity = filled_quantity
        self.avg_fill_price = avg_fill_price
        self.status = OrderStatus.PENDING
        self.create_time = datetime.now()
        self.update_time = datetime.now()

class Account:
    """账户信息"""
    def __init__(self, account_id: str, total_value: float = 0,
                 available_cash: float = 0, total_cash: float = 0,
                 market_value: float = 0, total_pnl: float = 0):
        self.account_id = account_id
        self.total_value = total_value
        self.available_cash = available_cash
        self.total_cash = total_cash
        self.market_value = market_value
        self.total_pnl = total_pnl
        self.update_time = datetime.now()

class BaseTrader(ABC):
    """
    交易接口基类
    
    所有具体的交易接口都必须继承此类并实现抽象方法
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化交易接口
        
        Args:
            config: 配置参数
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.is_connected = False
        self.is_trading_enabled = False
        self.account_id = config.get('account_id', '')
        
    @abstractmethod
    def connect(self) -> bool:
        """
        连接交易接口
        
        Returns:
            bool: 连接是否成功
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """
        断开交易接口连接
        
        Returns:
            bool: 断开是否成功
        """
        pass
    
    @abstractmethod
    def get_account_info(self) -> Optional[Account]:
        """
        获取账户信息
        
        Returns:
            Account: 账户信息，失败返回None
        """
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """
        获取持仓信息
        
        Returns:
            List[Position]: 持仓列表
        """
        pass
    
    @abstractmethod
    def get_orders(self, symbol: str = None) -> List[Order]:
        """
        获取订单信息
        
        Args:
            symbol: 股票代码，None表示获取全部
            
        Returns:
            List[Order]: 订单列表
        """
        pass
    
    @abstractmethod
    def submit_order(self, symbol: str, side: OrderSide, order_type: OrderType,
                    quantity: int, price: float = 0) -> Optional[str]:
        """
        提交订单
        
        Args:
            symbol: 股票代码
            side: 买卖方向
            order_type: 订单类型
            quantity: 数量
            price: 价格（市价单可为0）
            
        Returns:
            str: 订单ID，失败返回None
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        撤销订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            bool: 撤销是否成功
        """
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> Optional[Order]:
        """
        查询订单状态
        
        Args:
            order_id: 订单ID
            
        Returns:
            Order: 订单信息，失败返回None
        """
        pass
    
    def enable_trading(self) -> bool:
        """启用交易功能"""
        if not self.is_connected:
            self.logger.error("交易接口未连接，无法启用交易")
            return False
        self.is_trading_enabled = True
        self.logger.info("交易功能已启用")
        return True
    
    def disable_trading(self) -> bool:
        """禁用交易功能"""
        self.is_trading_enabled = False
        self.logger.info("交易功能已禁用")
        return True
    
    def validate_order(self, symbol: str, side: OrderSide, quantity: int, 
                      price: float = 0) -> tuple[bool, str]:
        """
        验证订单参数
        
        Args:
            symbol: 股票代码
            side: 买卖方向
            quantity: 数量
            price: 价格
            
        Returns:
            tuple[bool, str]: (是否有效, 错误信息)
        """
        if not symbol or len(symbol) < 6:
            return False, "股票代码无效"
        
        if quantity <= 0:
            return False, "数量必须大于0"
            
        if quantity % 100 != 0:
            return False, "股票交易数量必须是100的整数倍"
            
        if price < 0:
            return False, "价格不能为负数"
            
        return True, ""