"""
回测引擎核心模块
================

实现事件驱动的回测引擎，支持历史数据回放和策略执行。
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
import logging
from dataclasses import dataclass
from enum import Enum

from .portfolio import Portfolio
from .performance import PerformanceAnalyzer


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"  # 市价单
    LIMIT = "limit"    # 限价单


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


@dataclass
class Order:
    """订单数据结构"""
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType
    price: Optional[float] = None
    timestamp: Optional[datetime] = None
    order_id: Optional[str] = None


@dataclass
class Trade:
    """成交数据结构"""
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    timestamp: datetime
    commission: float = 0.0


@dataclass
class MarketData:
    """市场数据结构"""
    symbol: str
    timestamp: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float


class BacktestEngine:
    """回测引擎"""
    
    def __init__(
        self,
        initial_capital: float = 1000000.0,
        commission_rate: float = 0.0003,
        slippage_rate: float = 0.0001,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ):
        """
        初始化回测引擎
        
        Args:
            initial_capital: 初始资金
            commission_rate: 手续费率
            slippage_rate: 滑点率
            start_date: 回测开始日期
            end_date: 回测结束日期
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.start_date = pd.to_datetime(start_date) if start_date else None
        self.end_date = pd.to_datetime(end_date) if end_date else None
        
        # 组件初始化
        self.portfolio = Portfolio(initial_capital)
        self.performance_analyzer = PerformanceAnalyzer()
        
        # 数据和状态
        self.market_data: Dict[str, pd.DataFrame] = {}
        self.current_datetime: Optional[datetime] = None
        self.current_prices: Dict[str, float] = {}
        
        # 订单和交易
        self.orders: List[Order] = []
        self.trades: List[Trade] = []
        self.order_counter = 0
        
        # 策略回调
        self.strategy_callback: Optional[Callable] = None
        
        # 日志
        self.logger = logging.getLogger(__name__)
        
        # 运行状态
        self.is_running = False
        self.daily_returns: List[float] = []
        self.equity_curve: List[float] = []
        self.timestamps: List[datetime] = []
    
    def add_data(self, symbol: str, data: pd.DataFrame):
        """
        添加历史数据
        
        Args:
            symbol: 证券代码
            data: 历史数据，包含OHLCV
        """
        # 数据预处理
        data = data.copy()
        data.index = pd.to_datetime(data.index)
        
        # 按日期范围过滤
        if self.start_date:
            data = data[data.index >= self.start_date]
        if self.end_date:
            data = data[data.index <= self.end_date]
        
        # 确保列名标准化
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in data.columns:
                raise ValueError(f"数据缺少必要列: {col}")
        
        self.market_data[symbol] = data
        self.logger.info(f"添加数据: {symbol}, 数据量: {len(data)}")
    
    def set_strategy(self, strategy_callback: Callable):
        """
        设置策略回调函数
        
        Args:
            strategy_callback: 策略函数，接收当前市场数据和引擎实例
        """
        self.strategy_callback = strategy_callback
    
    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None
    ) -> str:
        """
        提交订单
        
        Args:
            symbol: 证券代码
            side: 订单方向
            quantity: 数量
            order_type: 订单类型
            price: 价格（限价单需要）
            
        Returns:
            订单ID
        """
        self.order_counter += 1
        order_id = f"order_{self.order_counter:06d}"
        
        order = Order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            timestamp=self.current_datetime,
            order_id=order_id
        )
        
        self.orders.append(order)
        
        # 立即执行市价单
        if order_type == OrderType.MARKET:
            self._execute_order(order)
        
        return order_id
    
    def _execute_order(self, order: Order):
        """执行订单"""
        if order.symbol not in self.current_prices:
            self.logger.warning(f"无法获取 {order.symbol} 的当前价格")
            return
        
        # 计算成交价格（考虑滑点）
        current_price = self.current_prices[order.symbol]
        if order.order_type == OrderType.MARKET:
            # 市价单考虑滑点
            if order.side == OrderSide.BUY:
                execution_price = current_price * (1 + self.slippage_rate)
            else:
                execution_price = current_price * (1 - self.slippage_rate)
        else:
            # 限价单使用指定价格
            execution_price = order.price
        
        # 计算手续费
        commission = order.quantity * execution_price * self.commission_rate
        
        # 检查资金充足性
        if order.side == OrderSide.BUY:
            required_cash = order.quantity * execution_price + commission
            if self.portfolio.cash < required_cash:
                self.logger.warning(f"资金不足，无法执行买入订单: {order.order_id}")
                return
        
        # 检查持仓充足性
        if order.side == OrderSide.SELL:
            current_position = self.portfolio.positions.get(order.symbol, 0)
            if current_position < order.quantity:
                self.logger.warning(f"持仓不足，无法执行卖出订单: {order.order_id}")
                return
        
        # 创建成交记录
        trade = Trade(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=execution_price,
            timestamp=self.current_datetime,
            commission=commission
        )
        
        self.trades.append(trade)
        
        # 更新投资组合
        self.portfolio.update_position(
            symbol=order.symbol,
            quantity=order.quantity if order.side == OrderSide.BUY else -order.quantity,
            price=execution_price,
            commission=commission
        )
        
        self.logger.info(f"订单执行: {order.order_id}, {order.symbol}, "
                        f"{order.side.value}, {order.quantity}, {execution_price:.4f}")
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """获取当前价格"""
        return self.current_prices.get(symbol)
    
    def get_portfolio_value(self) -> float:
        """获取投资组合总值"""
        return self.portfolio.get_total_value(self.current_prices)
    
    def run(self) -> Dict[str, Any]:
        """
        运行回测
        
        Returns:
            回测结果字典
        """
        if not self.market_data:
            raise ValueError("未添加市场数据")
        
        if not self.strategy_callback:
            raise ValueError("未设置策略")
        
        self.is_running = True
        self.logger.info("开始回测...")
        
        # 获取所有时间戳并排序
        all_timestamps = set()
        for symbol, data in self.market_data.items():
            all_timestamps.update(data.index)
        
        sorted_timestamps = sorted(all_timestamps)
        
        # 按时间顺序处理数据
        for i, timestamp in enumerate(sorted_timestamps):
            self.current_datetime = timestamp
            
            # 更新当前价格
            for symbol, data in self.market_data.items():
                if timestamp in data.index:
                    self.current_prices[symbol] = data.loc[timestamp, 'close']
            
            # 准备当前市场数据
            current_data = {}
            for symbol, data in self.market_data.items():
                # 获取到当前时间的所有历史数据（避免未来函数）
                available_data = data[data.index <= timestamp]
                if len(available_data) > 0:
                    current_data[symbol] = available_data
            
            # 调用策略
            if current_data and self.strategy_callback:
                try:
                    self.strategy_callback(current_data, self)
                except Exception as e:
                    self.logger.error(f"策略执行错误: {e}")
            
            # 记录每日权益
            portfolio_value = self.get_portfolio_value()
            self.equity_curve.append(portfolio_value)
            self.timestamps.append(timestamp)
            
            # 计算日收益率
            if len(self.equity_curve) > 1:
                daily_return = (portfolio_value - self.equity_curve[-2]) / self.equity_curve[-2]
                self.daily_returns.append(daily_return)
            
            # 进度输出
            if i % 100 == 0:
                progress = (i + 1) / len(sorted_timestamps) * 100
                self.logger.info(f"回测进度: {progress:.1f}%")
        
        self.is_running = False
        self.logger.info("回测完成")
        
        # 生成回测结果
        return self._generate_results()
    
    def _generate_results(self) -> Dict[str, Any]:
        """生成回测结果"""
        # 创建权益曲线DataFrame
        equity_df = pd.DataFrame({
            'equity': self.equity_curve,
            'timestamp': self.timestamps
        }).set_index('timestamp')
        
        # 创建交易记录DataFrame
        trades_df = pd.DataFrame([
            {
                'timestamp': trade.timestamp,
                'symbol': trade.symbol,
                'side': trade.side.value,
                'quantity': trade.quantity,
                'price': trade.price,
                'commission': trade.commission
            }
            for trade in self.trades
        ])
        
        # 计算绩效指标
        performance_metrics = self.performance_analyzer.calculate_metrics(
            equity_curve=equity_df['equity'],
            returns=pd.Series(self.daily_returns, index=self.timestamps[1:]),
            trades=trades_df
        )
        
        return {
            'equity_curve': equity_df,
            'trades': trades_df,
            'performance_metrics': performance_metrics,
            'portfolio': {
                'final_value': self.equity_curve[-1] if self.equity_curve else self.initial_capital,
                'cash': self.portfolio.cash,
                'positions': self.portfolio.positions.copy(),
                'total_commission': sum(trade.commission for trade in self.trades)
            }
        }