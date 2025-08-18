"""
仓位管理模块
============

实现全面的仓位管理和风控功能，包括：
- 单票仓位管理和限制
- 总仓位控制
- 行业集中度管理
- 持仓分布分析
- 仓位风控检查
- 动态仓位调整建议
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum

from .risk_config import RiskConfig, RiskEvent, RiskEventType, RiskLevel
from .base_risk import RiskCheckResult, RiskViolation, RiskCheckStatus

logger = logging.getLogger(__name__)


class PositionType(Enum):
    """持仓类型"""
    LONG = "long"       # 多头
    SHORT = "short"     # 空头
    FLAT = "flat"       # 空仓


@dataclass
class PositionInfo:
    """持仓信息"""
    symbol: str
    position_type: PositionType
    quantity: float
    avg_price: float
    current_price: float
    market_value: float
    cost_basis: float
    unrealized_pnl: float
    unrealized_pnl_ratio: float
    weight: float  # 在总资产中的权重
    sector: Optional[str] = None
    entry_time: Optional[datetime] = None
    holding_days: int = 0
    
    @property
    def is_profitable(self) -> bool:
        """是否盈利"""
        return self.unrealized_pnl > 0
    
    @property
    def is_flat(self) -> bool:
        """是否空仓"""
        return self.position_type == PositionType.FLAT or self.quantity == 0


@dataclass
class PortfolioSnapshot:
    """投资组合快照"""
    timestamp: datetime
    total_value: float
    cash: float
    total_market_value: float
    position_count: int
    long_positions: int
    short_positions: int
    total_weight: float
    sector_distribution: Dict[str, float] = field(default_factory=dict)
    top_holdings: List[str] = field(default_factory=list)


@dataclass 
class PositionLimits:
    """仓位限制配置"""
    max_single_position_ratio: float = 0.20      # 单票最大仓位比例
    max_total_position_ratio: float = 0.95       # 总仓位最大比例
    max_sector_concentration: float = 0.30       # 单行业最大集中度
    max_individual_stocks: int = 50              # 最大持股数量
    min_position_value: float = 1000.0          # 最小持仓价值
    max_position_value: float = 1000000.0       # 最大单票持仓价值
    max_new_position_ratio: float = 0.10        # 新建仓位最大比例


class PositionManager:
    """仓位管理器"""
    
    def __init__(self, risk_config: RiskConfig, initial_capital: float = 1000000.0):
        """
        初始化仓位管理器
        
        Args:
            risk_config: 风控配置
            initial_capital: 初始资金
        """
        self.risk_config = risk_config
        self.initial_capital = initial_capital
        
        # 持仓数据
        self.positions: Dict[str, PositionInfo] = {}
        self.cash = initial_capital
        self.total_value = initial_capital
        
        # 行业分类数据（简化版，实际应该从数据源获取）
        self.sector_mapping: Dict[str, str] = {}
        
        # 历史快照
        self.snapshots: List[PortfolioSnapshot] = []
        
        # 统计数据
        self.daily_turnover = 0.0
        self.total_trades = 0
        
        logger.info("仓位管理器初始化完成")
    
    def update_position(self, symbol: str, quantity: float, price: float, 
                       sector: Optional[str] = None, trade_time: Optional[datetime] = None):
        """
        更新持仓信息
        
        Args:
            symbol: 股票代码
            quantity: 变动数量（正数买入，负数卖出）
            price: 成交价格
            sector: 行业分类
            trade_time: 交易时间
        """
        if trade_time is None:
            trade_time = datetime.now()
        
        current_position = self.positions.get(symbol)
        
        if current_position is None:
            # 新建持仓
            if quantity > 0:
                market_value = quantity * price
                self.positions[symbol] = PositionInfo(
                    symbol=symbol,
                    position_type=PositionType.LONG,
                    quantity=quantity,
                    avg_price=price,
                    current_price=price,
                    market_value=market_value,
                    cost_basis=market_value,
                    unrealized_pnl=0.0,
                    unrealized_pnl_ratio=0.0,
                    weight=market_value / self.total_value,
                    sector=sector,
                    entry_time=trade_time,
                    holding_days=0
                )
                self.cash -= market_value
                
                if sector:
                    self.sector_mapping[symbol] = sector
                
                logger.info(f"新建持仓: {symbol}, 数量: {quantity}, 价格: {price}")
        else:
            # 更新现有持仓
            if quantity > 0:  # 加仓
                new_quantity = current_position.quantity + quantity
                total_cost = current_position.cost_basis + quantity * price
                new_avg_price = total_cost / new_quantity
                
                current_position.quantity = new_quantity
                current_position.avg_price = new_avg_price
                current_position.cost_basis = total_cost
                
                self.cash -= quantity * price
                
                logger.info(f"加仓: {symbol}, 增加数量: {quantity}, 新平均价格: {new_avg_price:.4f}")
                
            elif quantity < 0:  # 减仓或平仓
                sell_quantity = abs(quantity)
                if sell_quantity >= current_position.quantity:
                    # 完全平仓
                    proceeds = current_position.quantity * price
                    self.cash += proceeds
                    
                    logger.info(f"平仓: {symbol}, 数量: {current_position.quantity}")
                    del self.positions[symbol]
                else:
                    # 部分减仓
                    current_position.quantity -= sell_quantity
                    proceeds = sell_quantity * price
                    self.cash += proceeds
                    
                    logger.info(f"减仓: {symbol}, 减少数量: {sell_quantity}")
        
        # 更新所有持仓的当前价格和市值
        self._update_position_values()
        self.total_trades += 1
    
    def update_current_prices(self, price_data: Dict[str, float]):
        """
        更新当前价格
        
        Args:
            price_data: 价格数据字典 {symbol: price}
        """
        for symbol, price in price_data.items():
            if symbol in self.positions:
                position = self.positions[symbol]
                position.current_price = price
                position.market_value = position.quantity * price
                position.unrealized_pnl = position.market_value - position.cost_basis
                position.unrealized_pnl_ratio = position.unrealized_pnl / position.cost_basis if position.cost_basis > 0 else 0.0
        
        self._update_portfolio_totals()
    
    def _update_position_values(self):
        """更新持仓价值"""
        for position in self.positions.values():
            position.market_value = position.quantity * position.current_price
            position.unrealized_pnl = position.market_value - position.cost_basis
            position.unrealized_pnl_ratio = position.unrealized_pnl / position.cost_basis if position.cost_basis > 0 else 0.0
        
        self._update_portfolio_totals()
    
    def _update_portfolio_totals(self):
        """更新投资组合总值"""
        total_market_value = sum(pos.market_value for pos in self.positions.values())
        self.total_value = self.cash + total_market_value
        
        # 更新权重
        for position in self.positions.values():
            position.weight = position.market_value / self.total_value if self.total_value > 0 else 0.0
    
    def check_position_limits(self, symbol: str, target_quantity: float, 
                            target_price: float) -> RiskCheckResult:
        """
        检查仓位限制
        
        Args:
            symbol: 股票代码
            target_quantity: 目标数量
            target_price: 目标价格
            
        Returns:
            风控检查结果
        """
        result = RiskCheckResult(RiskCheckStatus.PASS)
        
        target_value = target_quantity * target_price
        target_weight = target_value / self.total_value
        
        limits = self.risk_config.position_limits
        
        # 检查单票仓位限制
        if target_weight > limits.max_single_position_ratio:
            violation = RiskViolation(
                rule_name="单票仓位限制",
                violation_type=RiskEventType.POSITION_LIMIT,
                symbol=symbol,
                current_value=target_weight,
                limit_value=limits.max_single_position_ratio,
                risk_level=RiskLevel.HIGH,
                message=f"单票仓位过高: {target_weight:.2%} > {limits.max_single_position_ratio:.2%}"
            )
            result.add_violation(violation)
        
        # 检查最小/最大持仓价值
        if target_value < limits.min_position_value:
            violation = RiskViolation(
                rule_name="最小持仓价值",
                violation_type=RiskEventType.POSITION_LIMIT,
                symbol=symbol,
                current_value=target_value,
                limit_value=limits.min_position_value,
                risk_level=RiskLevel.MEDIUM,
                message=f"持仓价值过小: {target_value:.2f} < {limits.min_position_value:.2f}"
            )
            result.add_violation(violation)
        
        if target_value > limits.max_position_value:
            violation = RiskViolation(
                rule_name="最大持仓价值",
                violation_type=RiskEventType.POSITION_LIMIT,
                symbol=symbol,
                current_value=target_value,
                limit_value=limits.max_position_value,
                risk_level=RiskLevel.HIGH,
                message=f"持仓价值过大: {target_value:.2f} > {limits.max_position_value:.2f}"
            )
            result.add_violation(violation)
        
        # 检查总仓位限制
        total_position_ratio = self.get_total_position_ratio()
        if total_position_ratio > limits.max_total_position_ratio:
            violation = RiskViolation(
                rule_name="总仓位限制",
                violation_type=RiskEventType.POSITION_LIMIT,
                symbol="PORTFOLIO",
                current_value=total_position_ratio,
                limit_value=limits.max_total_position_ratio,
                risk_level=RiskLevel.HIGH,
                message=f"总仓位过高: {total_position_ratio:.2%} > {limits.max_total_position_ratio:.2%}"
            )
            result.add_violation(violation)
        
        # 检查持股数量限制
        position_count = len(self.positions)
        if symbol not in self.positions:
            position_count += 1  # 新增持仓
        
        if position_count > limits.max_individual_stocks:
            violation = RiskViolation(
                rule_name="持股数量限制",
                violation_type=RiskEventType.POSITION_LIMIT,
                symbol="PORTFOLIO",
                current_value=position_count,
                limit_value=limits.max_individual_stocks,
                risk_level=RiskLevel.MEDIUM,
                message=f"持股数量过多: {position_count} > {limits.max_individual_stocks}"
            )
            result.add_violation(violation)
        
        return result
    
    def check_sector_concentration(self) -> RiskCheckResult:
        """检查行业集中度"""
        result = RiskCheckResult(RiskCheckStatus.PASS)
        
        sector_weights = self.get_sector_distribution()
        max_concentration = self.risk_config.position_limits.max_sector_concentration
        
        for sector, weight in sector_weights.items():
            if weight > max_concentration:
                violation = RiskViolation(
                    rule_name="行业集中度限制",
                    violation_type=RiskEventType.CONCENTRATION_LIMIT,
                    symbol=sector,
                    current_value=weight,
                    limit_value=max_concentration,
                    risk_level=RiskLevel.MEDIUM,
                    message=f"行业 {sector} 集中度过高: {weight:.2%} > {max_concentration:.2%}"
                )
                result.add_violation(violation)
        
        return result
    
    def get_position(self, symbol: str) -> Optional[PositionInfo]:
        """获取持仓信息"""
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> Dict[str, PositionInfo]:
        """获取所有持仓"""
        return self.positions.copy()
    
    def get_position_count(self) -> int:
        """获取持仓数量"""
        return len(self.positions)
    
    def get_total_market_value(self) -> float:
        """获取总市值"""
        return sum(pos.market_value for pos in self.positions.values())
    
    def get_total_position_ratio(self) -> float:
        """获取总仓位比例"""
        return self.get_total_market_value() / self.total_value if self.total_value > 0 else 0.0
    
    def get_cash_ratio(self) -> float:
        """获取现金比例"""
        return self.cash / self.total_value if self.total_value > 0 else 1.0
    
    def get_sector_distribution(self) -> Dict[str, float]:
        """获取行业分布"""
        sector_values = defaultdict(float)
        
        for symbol, position in self.positions.items():
            sector = self.sector_mapping.get(symbol, "未分类")
            sector_values[sector] += position.market_value
        
        # 转换为权重
        sector_weights = {}
        for sector, value in sector_values.items():
            sector_weights[sector] = value / self.total_value if self.total_value > 0 else 0.0
        
        return sector_weights
    
    def get_top_holdings(self, top_n: int = 10) -> List[Tuple[str, float]]:
        """获取前N大持仓"""
        positions_list = [(symbol, pos.weight) for symbol, pos in self.positions.items()]
        positions_list.sort(key=lambda x: x[1], reverse=True)
        return positions_list[:top_n]
    
    def get_profitable_positions(self) -> List[PositionInfo]:
        """获取盈利持仓"""
        return [pos for pos in self.positions.values() if pos.is_profitable]
    
    def get_losing_positions(self) -> List[PositionInfo]:
        """获取亏损持仓"""
        return [pos for pos in self.positions.values() if not pos.is_profitable]
    
    def get_total_unrealized_pnl(self) -> float:
        """获取总未实现盈亏"""
        return sum(pos.unrealized_pnl for pos in self.positions.values())
    
    def get_win_rate(self) -> float:
        """获取持仓胜率"""
        if not self.positions:
            return 0.0
        
        profitable_count = len(self.get_profitable_positions())
        return profitable_count / len(self.positions)
    
    def suggest_position_adjustments(self) -> List[Dict[str, Any]]:
        """建议仓位调整"""
        suggestions = []
        
        limits = self.risk_config.position_limits
        
        # 检查超限持仓
        for symbol, position in self.positions.items():
            if position.weight > limits.max_single_position_ratio:
                target_weight = limits.max_single_position_ratio * 0.9  # 留10%缓冲
                target_value = target_weight * self.total_value
                target_quantity = target_value / position.current_price
                reduce_quantity = position.quantity - target_quantity
                
                suggestions.append({
                    'action': 'REDUCE',
                    'symbol': symbol,
                    'reason': '单票仓位超限',
                    'current_weight': position.weight,
                    'target_weight': target_weight,
                    'reduce_quantity': reduce_quantity,
                    'priority': 'HIGH'
                })
        
        # 检查行业集中度
        sector_weights = self.get_sector_distribution()
        for sector, weight in sector_weights.items():
            if weight > limits.max_sector_concentration:
                # 找出该行业的持仓
                sector_positions = [
                    (symbol, pos) for symbol, pos in self.positions.items()
                    if self.sector_mapping.get(symbol, "未分类") == sector
                ]
                # 按权重排序，建议减持权重最大的
                sector_positions.sort(key=lambda x: x[1].weight, reverse=True)
                
                for symbol, position in sector_positions[:2]:  # 减持前2大持仓
                    suggestions.append({
                        'action': 'REDUCE',
                        'symbol': symbol,
                        'reason': f'行业{sector}集中度过高',
                        'current_sector_weight': weight,
                        'target_sector_weight': limits.max_sector_concentration * 0.9,
                        'priority': 'MEDIUM'
                    })
        
        # 检查现金比例
        cash_ratio = self.get_cash_ratio()
        min_cash_ratio = self.risk_config.capital_limits.min_cash_ratio
        if cash_ratio < min_cash_ratio:
            suggestions.append({
                'action': 'INCREASE_CASH',
                'reason': '现金比例不足',
                'current_cash_ratio': cash_ratio,
                'target_cash_ratio': min_cash_ratio,
                'priority': 'HIGH'
            })
        
        return suggestions
    
    def create_snapshot(self) -> PortfolioSnapshot:
        """创建投资组合快照"""
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(),
            total_value=self.total_value,
            cash=self.cash,
            total_market_value=self.get_total_market_value(),
            position_count=self.get_position_count(),
            long_positions=len([p for p in self.positions.values() if p.position_type == PositionType.LONG]),
            short_positions=len([p for p in self.positions.values() if p.position_type == PositionType.SHORT]),
            total_weight=self.get_total_position_ratio(),
            sector_distribution=self.get_sector_distribution(),
            top_holdings=[symbol for symbol, _ in self.get_top_holdings(5)]
        )
        
        self.snapshots.append(snapshot)
        
        # 保留最近100个快照
        if len(self.snapshots) > 100:
            self.snapshots = self.snapshots[-100:]
        
        return snapshot
    
    def get_position_summary(self) -> Dict[str, Any]:
        """获取持仓摘要"""
        return {
            'total_value': self.total_value,
            'cash': self.cash,
            'cash_ratio': self.get_cash_ratio(),
            'total_market_value': self.get_total_market_value(),
            'total_position_ratio': self.get_total_position_ratio(),
            'position_count': self.get_position_count(),
            'total_unrealized_pnl': self.get_total_unrealized_pnl(),
            'win_rate': self.get_win_rate(),
            'top_holdings': self.get_top_holdings(10),
            'sector_distribution': self.get_sector_distribution(),
            'profitable_positions': len(self.get_profitable_positions()),
            'losing_positions': len(self.get_losing_positions()),
            'last_update': datetime.now().isoformat()
        }
    
    def reset(self):
        """重置仓位管理器"""
        self.positions.clear()
        self.cash = self.initial_capital
        self.total_value = self.initial_capital
        self.snapshots.clear()
        self.daily_turnover = 0.0
        self.total_trades = 0
        logger.info("仓位管理器已重置")
    
    def export_positions(self) -> pd.DataFrame:
        """导出持仓数据为DataFrame"""
        if not self.positions:
            return pd.DataFrame()
        
        data = []
        for symbol, position in self.positions.items():
            data.append({
                'symbol': symbol,
                'position_type': position.position_type.value,
                'quantity': position.quantity,
                'avg_price': position.avg_price,
                'current_price': position.current_price,
                'market_value': position.market_value,
                'cost_basis': position.cost_basis,
                'unrealized_pnl': position.unrealized_pnl,
                'unrealized_pnl_ratio': position.unrealized_pnl_ratio,
                'weight': position.weight,
                'sector': position.sector,
                'holding_days': position.holding_days
            })
        
        return pd.DataFrame(data)