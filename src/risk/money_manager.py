"""
资金管理模块
============

实现全面的资金管理和风控功能，包括：
- 可用资金计算和管理
- 风险敞口控制
- 杠杆比例管理
- 资金分配策略
- 流动性管理
- 资金利用率优化
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from .risk_config import RiskConfig, RiskEvent, RiskEventType, RiskLevel
from .base_risk import RiskCheckResult, RiskViolation, RiskCheckStatus

logger = logging.getLogger(__name__)


class FundType(Enum):
    """资金类型"""
    AVAILABLE = "available"        # 可用资金
    RESERVED = "reserved"          # 保留资金
    EMERGENCY = "emergency"        # 紧急资金
    RISK_CAPITAL = "risk_capital"  # 风险资金
    MARGIN = "margin"              # 保证金


class AllocationStatus(Enum):
    """资金分配状态"""
    ALLOCATED = "allocated"        # 已分配
    PENDING = "pending"            # 待分配
    FROZEN = "frozen"              # 冻结
    AVAILABLE = "available"        # 可用


@dataclass
class FundAllocation:
    """资金分配记录"""
    allocation_id: str
    fund_type: FundType
    amount: float
    purpose: str
    status: AllocationStatus
    created_time: datetime
    updated_time: Optional[datetime] = None
    expired_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        """是否已过期"""
        return self.expired_time is not None and datetime.now() > self.expired_time
    
    @property
    def is_active(self) -> bool:
        """是否活跃"""
        return not self.is_expired and self.status in [AllocationStatus.ALLOCATED, AllocationStatus.PENDING]


@dataclass
class CashFlowRecord:
    """现金流记录"""
    timestamp: datetime
    amount: float
    flow_type: str  # inflow, outflow
    category: str   # trade, dividend, fee, etc.
    description: str
    balance_after: float


@dataclass
class LeverageInfo:
    """杠杆信息"""
    total_assets: float
    total_liabilities: float
    net_assets: float
    leverage_ratio: float
    margin_ratio: float
    free_margin: float
    margin_call_level: float
    stop_out_level: float


class MoneyManager:
    """资金管理器"""
    
    def __init__(self, risk_config: RiskConfig, initial_capital: float = 1000000.0):
        """
        初始化资金管理器
        
        Args:
            risk_config: 风控配置
            initial_capital: 初始资金
        """
        self.risk_config = risk_config
        self.initial_capital = initial_capital
        
        # 资金账户
        self.total_capital = initial_capital
        self.available_cash = initial_capital
        self.reserved_cash = 0.0
        self.emergency_cash = 0.0
        self.frozen_cash = 0.0
        
        # 风险敞口
        self.total_exposure = 0.0
        self.long_exposure = 0.0
        self.short_exposure = 0.0
        self.net_exposure = 0.0
        
        # 杠杆管理
        self.total_margin_used = 0.0
        self.max_leverage = risk_config.capital_limits.max_leverage_ratio
        
        # 资金分配记录
        self.allocations: Dict[str, FundAllocation] = {}
        self.allocation_counter = 0
        
        # 现金流记录
        self.cash_flows: List[CashFlowRecord] = []
        
        # 每日统计
        self.daily_stats: Dict[str, Dict[str, float]] = {}
        
        # 初始化保留资金
        self._initialize_reserved_funds()
        
        logger.info("资金管理器初始化完成")
    
    def _initialize_reserved_funds(self):
        """初始化保留资金"""
        # 设置紧急资金
        emergency_ratio = self.risk_config.capital_limits.emergency_cash_ratio
        self.emergency_cash = self.total_capital * emergency_ratio
        
        # 设置最低现金储备
        min_cash_ratio = self.risk_config.capital_limits.min_cash_ratio
        self.reserved_cash = self.total_capital * min_cash_ratio
        
        # 更新可用资金
        self._update_available_cash()
        
        logger.info(f"初始化保留资金: 紧急资金={self.emergency_cash:.2f}, 保留资金={self.reserved_cash:.2f}")
    
    def _update_available_cash(self):
        """更新可用资金"""
        self.available_cash = (self.total_capital - self.reserved_cash - 
                              self.emergency_cash - self.frozen_cash)
        self.available_cash = max(0, self.available_cash)
    
    def allocate_funds(self, amount: float, purpose: str, fund_type: FundType = FundType.AVAILABLE,
                      duration_hours: Optional[int] = None) -> Optional[str]:
        """
        分配资金
        
        Args:
            amount: 分配金额
            purpose: 分配目的
            fund_type: 资金类型
            duration_hours: 持续时间（小时）
            
        Returns:
            分配ID，失败返回None
        """
        # 检查资金充足性
        if not self._check_fund_availability(amount, fund_type):
            logger.warning(f"资金不足，无法分配 {amount:.2f} 用于 {purpose}")
            return None
        
        # 创建分配记录
        self.allocation_counter += 1
        allocation_id = f"alloc_{self.allocation_counter:06d}"
        
        expired_time = None
        if duration_hours:
            expired_time = datetime.now() + timedelta(hours=duration_hours)
        
        allocation = FundAllocation(
            allocation_id=allocation_id,
            fund_type=fund_type,
            amount=amount,
            purpose=purpose,
            status=AllocationStatus.ALLOCATED,
            created_time=datetime.now(),
            expired_time=expired_time
        )
        
        self.allocations[allocation_id] = allocation
        
        # 更新资金状态
        if fund_type == FundType.AVAILABLE:
            self.frozen_cash += amount
        elif fund_type == FundType.RESERVED:
            self.reserved_cash += amount
        elif fund_type == FundType.EMERGENCY:
            self.emergency_cash += amount
        
        self._update_available_cash()
        
        # 记录现金流
        self._record_cash_flow(-amount, "outflow", "allocation", f"资金分配: {purpose}")
        
        logger.info(f"资金分配成功: {allocation_id}, 金额: {amount:.2f}, 目的: {purpose}")
        return allocation_id
    
    def release_funds(self, allocation_id: str) -> bool:
        """
        释放资金分配
        
        Args:
            allocation_id: 分配ID
            
        Returns:
            释放是否成功
        """
        allocation = self.allocations.get(allocation_id)
        if not allocation:
            logger.warning(f"分配记录不存在: {allocation_id}")
            return False
        
        if allocation.status != AllocationStatus.ALLOCATED:
            logger.warning(f"分配状态不正确: {allocation_id}, 状态: {allocation.status}")
            return False
        
        # 释放资金
        amount = allocation.amount
        fund_type = allocation.fund_type
        
        if fund_type == FundType.AVAILABLE:
            self.frozen_cash -= amount
        elif fund_type == FundType.RESERVED:
            self.reserved_cash -= amount
        elif fund_type == FundType.EMERGENCY:
            self.emergency_cash -= amount
        
        # 更新分配状态
        allocation.status = AllocationStatus.AVAILABLE
        allocation.updated_time = datetime.now()
        
        self._update_available_cash()
        
        # 记录现金流
        self._record_cash_flow(amount, "inflow", "release", f"释放资金分配: {allocation.purpose}")
        
        logger.info(f"资金释放成功: {allocation_id}, 金额: {amount:.2f}")
        return True
    
    def _check_fund_availability(self, amount: float, fund_type: FundType) -> bool:
        """检查资金可用性"""
        if fund_type == FundType.AVAILABLE:
            return self.available_cash >= amount
        elif fund_type == FundType.RESERVED:
            return (self.total_capital - self.reserved_cash - self.emergency_cash) >= amount
        elif fund_type == FundType.EMERGENCY:
            return (self.total_capital - self.emergency_cash) >= amount
        
        return False
    
    def calculate_position_size(self, symbol: str, entry_price: float, 
                               risk_ratio: float = 0.02, max_position_ratio: float = 0.10) -> Tuple[int, float]:
        """
        计算建仓数量
        
        Args:
            symbol: 股票代码
            entry_price: 入场价格
            risk_ratio: 风险比例（默认2%）
            max_position_ratio: 最大仓位比例（默认10%）
            
        Returns:
            (建议数量, 所需资金)
        """
        # 基于风险比例计算
        risk_amount = self.total_capital * risk_ratio
        
        # 基于最大仓位比例计算
        max_position_value = self.total_capital * max_position_ratio
        
        # 取较小值
        position_value = min(risk_amount / 0.05, max_position_value)  # 假设5%止损
        
        # 检查可用资金
        if position_value > self.available_cash:
            position_value = self.available_cash * 0.95  # 留5%缓冲
        
        # 计算数量（100股为单位）
        quantity = int(position_value / entry_price / 100) * 100
        actual_value = quantity * entry_price
        
        return quantity, actual_value
    
    def check_margin_requirements(self, new_position_value: float) -> RiskCheckResult:
        """
        检查保证金要求
        
        Args:
            new_position_value: 新建仓位价值
            
        Returns:
            风控检查结果
        """
        result = RiskCheckResult(RiskCheckStatus.PASS)
        
        # 计算新的总敞口
        new_total_exposure = self.total_exposure + new_position_value
        leverage_ratio = new_total_exposure / self.total_capital
        
        # 检查杠杆比例
        if leverage_ratio > self.max_leverage:
            violation = RiskViolation(
                rule_name="杠杆比例限制",
                violation_type=RiskEventType.CAPITAL_LIMIT,
                symbol="PORTFOLIO",
                current_value=leverage_ratio,
                limit_value=self.max_leverage,
                risk_level=RiskLevel.HIGH,
                message=f"杠杆比例过高: {leverage_ratio:.2f} > {self.max_leverage:.2f}"
            )
            result.add_violation(violation)
        
        # 检查可用资金
        required_margin = new_position_value * 0.3  # 假设30%保证金
        if required_margin > self.available_cash:
            violation = RiskViolation(
                rule_name="保证金不足",
                violation_type=RiskEventType.CAPITAL_LIMIT,
                symbol="PORTFOLIO",
                current_value=self.available_cash,
                limit_value=required_margin,
                risk_level=RiskLevel.HIGH,
                message=f"保证金不足: 需要 {required_margin:.2f}, 可用 {self.available_cash:.2f}"
            )
            result.add_violation(violation)
        
        return result
    
    def check_cash_limits(self) -> RiskCheckResult:
        """检查现金限制"""
        result = RiskCheckResult(RiskCheckStatus.PASS)
        
        # 检查最低现金比例
        cash_ratio = self.available_cash / self.total_capital
        min_cash_ratio = self.risk_config.capital_limits.min_cash_ratio
        
        if cash_ratio < min_cash_ratio:
            violation = RiskViolation(
                rule_name="最低现金比例",
                violation_type=RiskEventType.CAPITAL_LIMIT,
                symbol="PORTFOLIO",
                current_value=cash_ratio,
                limit_value=min_cash_ratio,
                risk_level=RiskLevel.MEDIUM,
                message=f"现金比例不足: {cash_ratio:.2%} < {min_cash_ratio:.2%}"
            )
            result.add_violation(violation)
        
        # 检查紧急现金
        emergency_ratio = self.emergency_cash / self.total_capital
        min_emergency_ratio = self.risk_config.capital_limits.emergency_cash_ratio
        
        if emergency_ratio < min_emergency_ratio:
            violation = RiskViolation(
                rule_name="紧急现金不足",
                violation_type=RiskEventType.CAPITAL_LIMIT,
                symbol="PORTFOLIO",
                current_value=emergency_ratio,
                limit_value=min_emergency_ratio,
                risk_level=RiskLevel.MEDIUM,
                message=f"紧急现金不足: {emergency_ratio:.2%} < {min_emergency_ratio:.2%}"
            )
            result.add_violation(violation)
        
        return result
    
    def update_exposure(self, symbol: str, position_change: float, current_price: float):
        """
        更新风险敞口
        
        Args:
            symbol: 股票代码
            position_change: 仓位变化（正数增加，负数减少）
            current_price: 当前价格
        """
        exposure_change = position_change * current_price
        
        if position_change > 0:
            self.long_exposure += exposure_change
        else:
            self.short_exposure += abs(exposure_change)
        
        self.total_exposure = self.long_exposure + self.short_exposure
        self.net_exposure = self.long_exposure - self.short_exposure
        
        logger.debug(f"更新敞口: {symbol}, 变化: {exposure_change:.2f}, 总敞口: {self.total_exposure:.2f}")
    
    def calculate_value_at_risk(self, confidence_level: float = 0.95, 
                               time_horizon_days: int = 1) -> float:
        """
        计算风险价值(VaR)
        
        Args:
            confidence_level: 置信水平
            time_horizon_days: 时间范围（天）
            
        Returns:
            风险价值
        """
        # 简化计算，实际应该基于历史数据和相关性
        portfolio_volatility = 0.02  # 假设日波动率2%
        
        # 使用正态分布假设
        from scipy.stats import norm
        z_score = norm.ppf(1 - confidence_level)
        
        var = self.total_exposure * portfolio_volatility * np.sqrt(time_horizon_days) * abs(z_score)
        
        return var
    
    def get_leverage_info(self) -> LeverageInfo:
        """获取杠杆信息"""
        return LeverageInfo(
            total_assets=self.total_capital + self.total_exposure,
            total_liabilities=self.total_margin_used,
            net_assets=self.total_capital,
            leverage_ratio=self.total_exposure / self.total_capital if self.total_capital > 0 else 0,
            margin_ratio=self.total_margin_used / self.total_capital if self.total_capital > 0 else 0,
            free_margin=self.available_cash,
            margin_call_level=0.5,  # 50%保证金追缴水平
            stop_out_level=0.2      # 20%强制平仓水平
        )
    
    def _record_cash_flow(self, amount: float, flow_type: str, category: str, description: str):
        """记录现金流"""
        record = CashFlowRecord(
            timestamp=datetime.now(),
            amount=amount,
            flow_type=flow_type,
            category=category,
            description=description,
            balance_after=self.available_cash
        )
        self.cash_flows.append(record)
        
        # 保留最近1000条记录
        if len(self.cash_flows) > 1000:
            self.cash_flows = self.cash_flows[-1000:]
    
    def get_cash_flow_summary(self, days: int = 30) -> Dict[str, float]:
        """获取现金流摘要"""
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_flows = [flow for flow in self.cash_flows if flow.timestamp >= cutoff_date]
        
        inflows = sum(flow.amount for flow in recent_flows if flow.flow_type == "inflow")
        outflows = sum(abs(flow.amount) for flow in recent_flows if flow.flow_type == "outflow")
        net_flow = inflows - outflows
        
        return {
            "total_inflows": inflows,
            "total_outflows": outflows,
            "net_cash_flow": net_flow,
            "transaction_count": len(recent_flows)
        }
    
    def cleanup_expired_allocations(self):
        """清理过期的资金分配"""
        expired_allocations = []
        
        for allocation_id, allocation in self.allocations.items():
            if allocation.is_expired and allocation.status == AllocationStatus.ALLOCATED:
                expired_allocations.append(allocation_id)
        
        for allocation_id in expired_allocations:
            self.release_funds(allocation_id)
            logger.info(f"自动释放过期资金分配: {allocation_id}")
    
    def suggest_capital_allocation(self) -> Dict[str, Any]:
        """建议资金分配"""
        suggestions = {
            "cash_management": [],
            "risk_management": [],
            "optimization": []
        }
        
        # 现金管理建议
        cash_ratio = self.available_cash / self.total_capital
        optimal_cash_ratio = 0.1  # 建议10%现金比例
        
        if cash_ratio > optimal_cash_ratio * 1.5:
            suggestions["cash_management"].append({
                "action": "INCREASE_INVESTMENT",
                "reason": "现金比例过高，建议增加投资",
                "current_ratio": cash_ratio,
                "optimal_ratio": optimal_cash_ratio
            })
        elif cash_ratio < optimal_cash_ratio * 0.5:
            suggestions["cash_management"].append({
                "action": "REDUCE_POSITION",
                "reason": "现金比例过低，建议减少仓位",
                "current_ratio": cash_ratio,
                "optimal_ratio": optimal_cash_ratio
            })
        
        # 风险管理建议
        leverage_info = self.get_leverage_info()
        if leverage_info.leverage_ratio > 0.8:
            suggestions["risk_management"].append({
                "action": "REDUCE_LEVERAGE",
                "reason": "杠杆比例过高",
                "current_ratio": leverage_info.leverage_ratio,
                "max_ratio": self.max_leverage
            })
        
        # 优化建议
        var = self.calculate_value_at_risk()
        var_ratio = var / self.total_capital
        if var_ratio > 0.05:  # VaR超过总资产5%
            suggestions["optimization"].append({
                "action": "DIVERSIFY_PORTFOLIO",
                "reason": "投资组合风险集中度过高",
                "current_var_ratio": var_ratio,
                "recommended_var_ratio": 0.03
            })
        
        return suggestions
    
    def get_fund_utilization_stats(self) -> Dict[str, Any]:
        """获取资金利用率统计"""
        return {
            "total_capital": self.total_capital,
            "available_cash": self.available_cash,
            "available_ratio": self.available_cash / self.total_capital,
            "reserved_cash": self.reserved_cash,
            "reserved_ratio": self.reserved_cash / self.total_capital,
            "emergency_cash": self.emergency_cash,
            "emergency_ratio": self.emergency_cash / self.total_capital,
            "frozen_cash": self.frozen_cash,
            "frozen_ratio": self.frozen_cash / self.total_capital,
            "total_exposure": self.total_exposure,
            "exposure_ratio": self.total_exposure / self.total_capital,
            "leverage_ratio": self.get_leverage_info().leverage_ratio,
            "active_allocations": len([a for a in self.allocations.values() if a.is_active])
        }
    
    def export_allocations(self) -> pd.DataFrame:
        """导出资金分配记录"""
        if not self.allocations:
            return pd.DataFrame()
        
        data = []
        for allocation in self.allocations.values():
            data.append({
                "allocation_id": allocation.allocation_id,
                "fund_type": allocation.fund_type.value,
                "amount": allocation.amount,
                "purpose": allocation.purpose,
                "status": allocation.status.value,
                "created_time": allocation.created_time,
                "updated_time": allocation.updated_time,
                "expired_time": allocation.expired_time,
                "is_active": allocation.is_active
            })
        
        return pd.DataFrame(data)
    
    def export_cash_flows(self, days: int = 30) -> pd.DataFrame:
        """导出现金流记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_flows = [flow for flow in self.cash_flows if flow.timestamp >= cutoff_date]
        
        if not recent_flows:
            return pd.DataFrame()
        
        data = []
        for flow in recent_flows:
            data.append({
                "timestamp": flow.timestamp,
                "amount": flow.amount,
                "flow_type": flow.flow_type,
                "category": flow.category,
                "description": flow.description,
                "balance_after": flow.balance_after
            })
        
        return pd.DataFrame(data)
    
    def reset(self):
        """重置资金管理器"""
        self.total_capital = self.initial_capital
        self.available_cash = self.initial_capital
        self.reserved_cash = 0.0
        self.emergency_cash = 0.0
        self.frozen_cash = 0.0
        
        self.total_exposure = 0.0
        self.long_exposure = 0.0
        self.short_exposure = 0.0
        self.net_exposure = 0.0
        
        self.total_margin_used = 0.0
        
        self.allocations.clear()
        self.allocation_counter = 0
        self.cash_flows.clear()
        self.daily_stats.clear()
        
        self._initialize_reserved_funds()
        
        logger.info("资金管理器已重置")
    def get_cash_ratio(self) -> float:
        """获取现金比例"""
        total_capital = self.total_capital
        if total_capital <= 0:
            return 0.0
        return self.available_cash / total_capital