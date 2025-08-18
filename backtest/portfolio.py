"""
投资组合管理模块
================

管理回测过程中的资金、持仓和交易记录。
"""

import pandas as pd
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime
import logging


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    quantity: float
    avg_price: float
    market_value: float
    unrealized_pnl: float
    cost_basis: float


class Portfolio:
    """投资组合管理器"""
    
    def __init__(self, initial_capital: float = 1000000.0):
        """
        初始化投资组合
        
        Args:
            initial_capital: 初始资金
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, float] = {}  # symbol -> quantity
        self.avg_prices: Dict[str, float] = {}  # symbol -> avg_price
        self.total_commission = 0.0
        
        # 历史记录
        self.equity_history: List[float] = []
        self.cash_history: List[float] = []
        self.position_history: List[Dict] = []
        
        self.logger = logging.getLogger(__name__)
    
    def update_position(
        self,
        symbol: str,
        quantity: float,
        price: float,
        commission: float = 0.0
    ):
        """
        更新持仓
        
        Args:
            symbol: 证券代码
            quantity: 变动数量（正数买入，负数卖出）
            price: 成交价格
            commission: 手续费
        """
        current_quantity = self.positions.get(symbol, 0.0)
        current_avg_price = self.avg_prices.get(symbol, 0.0)
        
        if quantity > 0:  # 买入
            # 更新现金
            cost = quantity * price + commission
            if self.cash < cost:
                raise ValueError(f"资金不足: 需要 {cost:.2f}, 可用 {self.cash:.2f}")
            
            self.cash -= cost
            self.total_commission += commission
            
            # 更新持仓和平均价格
            total_cost = current_quantity * current_avg_price + quantity * price
            new_quantity = current_quantity + quantity
            
            if new_quantity > 0:
                self.avg_prices[symbol] = total_cost / new_quantity
                self.positions[symbol] = new_quantity
            
        elif quantity < 0:  # 卖出
            sell_quantity = abs(quantity)
            
            if current_quantity < sell_quantity:
                raise ValueError(f"持仓不足: 需要 {sell_quantity}, 持有 {current_quantity}")
            
            # 更新现金
            proceeds = sell_quantity * price - commission
            self.cash += proceeds
            self.total_commission += commission
            
            # 更新持仓
            new_quantity = current_quantity - sell_quantity
            self.positions[symbol] = new_quantity
            
            # 如果完全平仓，清除平均价格
            if new_quantity == 0:
                self.avg_prices.pop(symbol, None)
                self.positions.pop(symbol, None)
        
        self.logger.debug(f"持仓更新: {symbol}, 数量变动: {quantity}, "
                         f"价格: {price}, 手续费: {commission}")
    
    def get_position(self, symbol: str) -> float:
        """获取持仓数量"""
        return self.positions.get(symbol, 0.0)
    
    def get_avg_price(self, symbol: str) -> float:
        """获取平均成本价"""
        return self.avg_prices.get(symbol, 0.0)
    
    def get_position_value(self, symbol: str, current_price: float) -> float:
        """获取持仓市值"""
        quantity = self.get_position(symbol)
        return quantity * current_price
    
    def get_position_pnl(self, symbol: str, current_price: float) -> float:
        """获取持仓盈亏"""
        quantity = self.get_position(symbol)
        avg_price = self.get_avg_price(symbol)
        
        if quantity == 0:
            return 0.0
        
        return quantity * (current_price - avg_price)
    
    def get_total_value(self, current_prices: Dict[str, float]) -> float:
        """
        获取投资组合总价值
        
        Args:
            current_prices: 当前价格字典
            
        Returns:
            总价值
        """
        total_value = self.cash
        
        for symbol, quantity in self.positions.items():
            if symbol in current_prices and quantity > 0:
                total_value += quantity * current_prices[symbol]
        
        return total_value
    
    def get_total_market_value(self, current_prices: Dict[str, float]) -> float:
        """获取持仓总市值"""
        market_value = 0.0
        
        for symbol, quantity in self.positions.items():
            if symbol in current_prices and quantity > 0:
                market_value += quantity * current_prices[symbol]
        
        return market_value
    
    def get_total_pnl(self, current_prices: Dict[str, float]) -> float:
        """获取总盈亏"""
        total_pnl = 0.0
        
        for symbol in self.positions:
            if symbol in current_prices:
                total_pnl += self.get_position_pnl(symbol, current_prices[symbol])
        
        return total_pnl
    
    def get_cash_utilization(self, current_prices: Dict[str, float]) -> float:
        """获取资金使用率"""
        total_value = self.get_total_value(current_prices)
        if total_value == 0:
            return 0.0
        
        return (total_value - self.cash) / total_value
    
    def get_position_details(self, current_prices: Dict[str, float]) -> Dict[str, Position]:
        """
        获取详细持仓信息
        
        Args:
            current_prices: 当前价格字典
            
        Returns:
            持仓详情字典
        """
        positions = {}
        
        for symbol, quantity in self.positions.items():
            if quantity > 0 and symbol in current_prices:
                current_price = current_prices[symbol]
                avg_price = self.get_avg_price(symbol)
                market_value = quantity * current_price
                cost_basis = quantity * avg_price
                unrealized_pnl = market_value - cost_basis
                
                positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity,
                    avg_price=avg_price,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                    cost_basis=cost_basis
                )
        
        return positions
    
    def save_snapshot(self, current_prices: Dict[str, float], timestamp: datetime):
        """保存当前投资组合快照"""
        total_value = self.get_total_value(current_prices)
        self.equity_history.append(total_value)
        self.cash_history.append(self.cash)
        
        # 保存持仓快照
        position_snapshot = {
            'timestamp': timestamp,
            'total_value': total_value,
            'cash': self.cash,
            'positions': self.positions.copy(),
            'avg_prices': self.avg_prices.copy()
        }
        self.position_history.append(position_snapshot)
    
    def get_summary(self, current_prices: Dict[str, float]) -> Dict:
        """获取投资组合摘要"""
        total_value = self.get_total_value(current_prices)
        market_value = self.get_total_market_value(current_prices)
        total_pnl = self.get_total_pnl(current_prices)
        cash_utilization = self.get_cash_utilization(current_prices)
        
        return {
            'initial_capital': self.initial_capital,
            'current_value': total_value,
            'cash': self.cash,
            'market_value': market_value,
            'total_return': (total_value - self.initial_capital) / self.initial_capital,
            'total_pnl': total_pnl,
            'cash_utilization': cash_utilization,
            'total_commission': self.total_commission,
            'position_count': len(self.positions)
        }
    
    def reset(self):
        """重置投资组合"""
        self.cash = self.initial_capital
        self.positions.clear()
        self.avg_prices.clear()
        self.total_commission = 0.0
        self.equity_history.clear()
        self.cash_history.clear()
        self.position_history.clear()