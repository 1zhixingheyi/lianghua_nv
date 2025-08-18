"""
基础风控规则模块
================

实现核心风控规则和检查机制，包括：
- 止损止盈检查
- 价格风控检查
- 波动率风控检查
- 流动性风控检查
- 时间风控检查
- 风控规则组合和执行
"""

import logging
import pandas as pd
import numpy as np
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from abc import ABC, abstractmethod

from .risk_config import RiskConfig, RiskEvent, RiskEventType, RiskLevel

logger = logging.getLogger(__name__)


class RiskCheckStatus(Enum):
    """风控检查状态"""
    PASS = "pass"           # 通过
    WARNING = "warning"     # 警告
    BLOCKED = "blocked"     # 阻止
    ERROR = "error"         # 错误


@dataclass
class RiskViolation:
    """风控违规记录"""
    rule_name: str
    violation_type: RiskEventType
    symbol: str
    current_value: float
    limit_value: float
    risk_level: RiskLevel
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __str__(self) -> str:
        return f"{self.rule_name}: {self.symbol} - {self.message}"


@dataclass
class RiskCheckResult:
    """风控检查结果"""
    status: RiskCheckStatus
    violations: List[RiskViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    blocked_operations: List[str] = field(default_factory=list)
    risk_score: float = 0.0
    
    @property
    def is_pass(self) -> bool:
        """是否通过检查"""
        return self.status == RiskCheckStatus.PASS
    
    @property
    def is_blocked(self) -> bool:
        """是否被阻止"""
        return self.status == RiskCheckStatus.BLOCKED
    
    def add_violation(self, violation: RiskViolation):
        """添加违规记录"""
        self.violations.append(violation)
        if violation.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            self.status = RiskCheckStatus.BLOCKED
            self.blocked_operations.append(violation.message)
        elif violation.risk_level == RiskLevel.MEDIUM:
            if self.status == RiskCheckStatus.PASS:
                self.status = RiskCheckStatus.WARNING
            self.warnings.append(violation.message)


class BaseRiskRule(ABC):
    """风控规则基类"""
    
    def __init__(self, name: str, risk_config: RiskConfig):
        self.name = name
        self.risk_config = risk_config
        self.enabled = True
        self.last_check_time: Optional[datetime] = None
    
    @abstractmethod
    def check(self, **kwargs) -> RiskCheckResult:
        """执行风控检查"""
        pass
    
    def is_enabled(self) -> bool:
        """检查规则是否启用"""
        return self.enabled
    
    def enable(self):
        """启用规则"""
        self.enabled = True
        logger.info(f"风控规则已启用: {self.name}")
    
    def disable(self):
        """禁用规则"""
        self.enabled = False
        logger.info(f"风控规则已禁用: {self.name}")


class StopLossRule(BaseRiskRule):
    """止损规则"""
    
    def __init__(self, risk_config: RiskConfig):
        super().__init__("止损规则", risk_config)
    
    def check(self, symbol: str, current_price: float, avg_price: float, 
              position_size: float, **kwargs) -> RiskCheckResult:
        """
        检查止损规则
        
        Args:
            symbol: 股票代码
            current_price: 当前价格
            avg_price: 平均成本价
            position_size: 持仓数量
        """
        result = RiskCheckResult(RiskCheckStatus.PASS)
        
        if not self.is_enabled() or position_size == 0:
            return result
        
        # 计算亏损比例
        loss_ratio = (avg_price - current_price) / avg_price
        stop_loss_threshold = self.risk_config.price_limits.stop_loss_ratio
        
        if loss_ratio > stop_loss_threshold:
            violation = RiskViolation(
                rule_name=self.name,
                violation_type=RiskEventType.STOP_LOSS,
                symbol=symbol,
                current_value=loss_ratio,
                limit_value=stop_loss_threshold,
                risk_level=RiskLevel.HIGH,
                message=f"触发止损: 亏损{loss_ratio:.2%} > 止损线{stop_loss_threshold:.2%}"
            )
            result.add_violation(violation)
        
        self.last_check_time = datetime.now()
        return result


class StopProfitRule(BaseRiskRule):
    """止盈规则"""
    
    def __init__(self, risk_config: RiskConfig):
        super().__init__("止盈规则", risk_config)
    
    def check(self, symbol: str, current_price: float, avg_price: float,
              position_size: float, **kwargs) -> RiskCheckResult:
        """
        检查止盈规则
        
        Args:
            symbol: 股票代码
            current_price: 当前价格
            avg_price: 平均成本价
            position_size: 持仓数量
        """
        result = RiskCheckResult(RiskCheckStatus.PASS)
        
        if not self.is_enabled() or position_size == 0:
            return result
        
        # 计算盈利比例
        profit_ratio = (current_price - avg_price) / avg_price
        stop_profit_threshold = self.risk_config.price_limits.stop_profit_ratio
        
        if profit_ratio > stop_profit_threshold:
            # 止盈通常是建议性的，不强制阻止
            result.warnings.append(
                f"建议止盈: {symbol} 盈利{profit_ratio:.2%} > 止盈线{stop_profit_threshold:.2%}"
            )
        
        self.last_check_time = datetime.now()
        return result


class VolatilityRule(BaseRiskRule):
    """波动率风控规则"""
    
    def __init__(self, risk_config: RiskConfig):
        super().__init__("波动率规则", risk_config)
    
    def check(self, symbol: str, price_data: pd.Series, **kwargs) -> RiskCheckResult:
        """
        检查波动率风控
        
        Args:
            symbol: 股票代码
            price_data: 价格序列（最近N天的收盘价）
        """
        result = RiskCheckResult(RiskCheckStatus.PASS)
        
        if not self.is_enabled() or len(price_data) < 2:
            return result
        
        # 计算日收益率
        returns = price_data.pct_change().dropna()
        
        if len(returns) == 0:
            return result
        
        # 计算波动率（标准差）
        volatility = returns.std()
        volatility_threshold = self.risk_config.price_limits.volatility_threshold
        
        if volatility > volatility_threshold:
            risk_level = RiskLevel.HIGH if volatility > volatility_threshold * 2 else RiskLevel.MEDIUM
            
            violation = RiskViolation(
                rule_name=self.name,
                violation_type=RiskEventType.VOLATILITY_LIMIT,
                symbol=symbol,
                current_value=volatility,
                limit_value=volatility_threshold,
                risk_level=risk_level,
                message=f"波动率过高: {volatility:.4f} > 阈值{volatility_threshold:.4f}"
            )
            result.add_violation(violation)
        
        self.last_check_time = datetime.now()
        return result


class PriceLimitRule(BaseRiskRule):
    """涨跌停风控规则"""
    
    def __init__(self, risk_config: RiskConfig):
        super().__init__("涨跌停规则", risk_config)
    
    def check(self, symbol: str, current_price: float, prev_close: float, 
              **kwargs) -> RiskCheckResult:
        """
        检查涨跌停风控
        
        Args:
            symbol: 股票代码
            current_price: 当前价格
            prev_close: 前收盘价
        """
        result = RiskCheckResult(RiskCheckStatus.PASS)
        
        if not self.is_enabled():
            return result
        
        # 计算涨跌幅
        price_change_ratio = (current_price - prev_close) / prev_close
        buffer = self.risk_config.price_limits.price_limit_buffer
        
        # 检查接近涨停（假设涨停为10%）
        if price_change_ratio > (0.10 - buffer):
            violation = RiskViolation(
                rule_name=self.name,
                violation_type=RiskEventType.CUSTOM,
                symbol=symbol,
                current_value=price_change_ratio,
                limit_value=0.10 - buffer,
                risk_level=RiskLevel.MEDIUM,
                message=f"接近涨停: 涨幅{price_change_ratio:.2%}"
            )
            result.add_violation(violation)
        
        # 检查接近跌停
        elif price_change_ratio < -(0.10 - buffer):
            violation = RiskViolation(
                rule_name=self.name,
                violation_type=RiskEventType.CUSTOM,
                symbol=symbol,
                current_value=price_change_ratio,
                limit_value=-(0.10 - buffer),
                risk_level=RiskLevel.HIGH,
                message=f"接近跌停: 跌幅{price_change_ratio:.2%}"
            )
            result.add_violation(violation)
        
        self.last_check_time = datetime.now()
        return result


class LiquidityRule(BaseRiskRule):
    """流动性风控规则"""
    
    def __init__(self, risk_config: RiskConfig):
        super().__init__("流动性规则", risk_config)
    
    def check(self, symbol: str, volume: float, avg_volume: float, 
              trade_volume: float = 0, **kwargs) -> RiskCheckResult:
        """
        检查流动性风控
        
        Args:
            symbol: 股票代码
            volume: 当前成交量
            avg_volume: 平均成交量
            trade_volume: 交易量
        """
        result = RiskCheckResult(RiskCheckStatus.PASS)
        
        if not self.is_enabled():
            return result
        
        # 检查成交量异常（过低）
        if volume < avg_volume * 0.3:  # 成交量低于平均的30%
            violation = RiskViolation(
                rule_name=self.name,
                violation_type=RiskEventType.LIQUIDITY_LIMIT,
                symbol=symbol,
                current_value=volume,
                limit_value=avg_volume * 0.3,
                risk_level=RiskLevel.MEDIUM,
                message=f"成交量异常偏低: {volume:.0f} < 平均值30%({avg_volume*0.3:.0f})"
            )
            result.add_violation(violation)
        
        # 检查是否有足够流动性执行交易
        if trade_volume > 0:
            # 交易量不应超过当前成交量的20%
            if trade_volume > volume * 0.2:
                violation = RiskViolation(
                    rule_name=self.name,
                    violation_type=RiskEventType.LIQUIDITY_LIMIT,
                    symbol=symbol,
                    current_value=trade_volume,
                    limit_value=volume * 0.2,
                    risk_level=RiskLevel.HIGH,
                    message=f"交易量过大: {trade_volume:.0f} > 成交量20%({volume*0.2:.0f})"
                )
                result.add_violation(violation)
        
        self.last_check_time = datetime.now()
        return result


class TradingTimeRule(BaseRiskRule):
    """交易时间风控规则"""
    
    def __init__(self, risk_config: RiskConfig):
        super().__init__("交易时间规则", risk_config)
    
    def check(self, current_time: Optional[datetime] = None, **kwargs) -> RiskCheckResult:
        """
        检查交易时间风控
        
        Args:
            current_time: 当前时间，如果为None则使用系统时间
        """
        result = RiskCheckResult(RiskCheckStatus.PASS)
        
        if not self.is_enabled():
            return result
        
        if current_time is None:
            current_time = datetime.now()
        
        # 获取配置的交易时间
        start_time = time.fromisoformat(self.risk_config.time_limits.trading_start_time)
        end_time = time.fromisoformat(self.risk_config.time_limits.trading_end_time)
        current_time_only = current_time.time()
        
        # 检查是否在交易时间内
        if not (start_time <= current_time_only <= end_time):
            violation = RiskViolation(
                rule_name=self.name,
                violation_type=RiskEventType.TIME_LIMIT,
                symbol="ALL",
                current_value=current_time_only.hour * 100 + current_time_only.minute,
                limit_value=start_time.hour * 100 + start_time.minute,
                risk_level=RiskLevel.HIGH,
                message=f"非交易时间: {current_time_only} 不在 {start_time}-{end_time}"
            )
            result.add_violation(violation)
        
        # 检查禁止交易日期
        current_date_str = current_time.strftime("%Y-%m-%d")
        if current_date_str in self.risk_config.time_limits.blackout_dates:
            violation = RiskViolation(
                rule_name=self.name,
                violation_type=RiskEventType.TIME_LIMIT,
                symbol="ALL",
                current_value=0,
                limit_value=1,
                risk_level=RiskLevel.HIGH,
                message=f"禁止交易日期: {current_date_str}"
            )
            result.add_violation(violation)
        
        self.last_check_time = datetime.now()
        return result


class DailyLossRule(BaseRiskRule):
    """单日亏损限制规则"""
    
    def __init__(self, risk_config: RiskConfig):
        super().__init__("单日亏损规则", risk_config)
        self._daily_pnl_cache: Dict[str, float] = {}  # 按日期缓存PnL
    
    def check(self, total_pnl_today: float, initial_capital: float, 
              **kwargs) -> RiskCheckResult:
        """
        检查单日亏损限制
        
        Args:
            total_pnl_today: 今日总盈亏
            initial_capital: 初始资金
        """
        result = RiskCheckResult(RiskCheckStatus.PASS)
        
        if not self.is_enabled():
            return result
        
        # 计算今日亏损比例
        daily_loss_ratio = abs(min(0, total_pnl_today)) / initial_capital
        max_daily_loss = self.risk_config.price_limits.max_daily_loss_ratio
        
        if daily_loss_ratio > max_daily_loss:
            violation = RiskViolation(
                rule_name=self.name,
                violation_type=RiskEventType.CUSTOM,
                symbol="PORTFOLIO",
                current_value=daily_loss_ratio,
                limit_value=max_daily_loss,
                risk_level=RiskLevel.CRITICAL,
                message=f"超出单日最大亏损: {daily_loss_ratio:.2%} > {max_daily_loss:.2%}"
            )
            result.add_violation(violation)
        
        self.last_check_time = datetime.now()
        return result


class BaseRiskManager:
    """基础风控管理器"""
    
    def __init__(self, risk_config: RiskConfig):
        """
        初始化风控管理器
        
        Args:
            risk_config: 风控配置
        """
        self.risk_config = risk_config
        self.rules: Dict[str, BaseRiskRule] = {}
        
        # 初始化所有风控规则
        self._initialize_rules()
        
        logger.info("基础风控管理器初始化完成")
    
    def _initialize_rules(self):
        """初始化风控规则"""
        self.rules = {
            'stop_loss': StopLossRule(self.risk_config),
            'stop_profit': StopProfitRule(self.risk_config),
            'volatility': VolatilityRule(self.risk_config),
            'price_limit': PriceLimitRule(self.risk_config),
            'liquidity': LiquidityRule(self.risk_config),
            'trading_time': TradingTimeRule(self.risk_config),
            'daily_loss': DailyLossRule(self.risk_config)
        }
        
        logger.info(f"已初始化 {len(self.rules)} 个风控规则")
    
    def check_all_rules(self, **kwargs) -> RiskCheckResult:
        """
        执行所有风控检查
        
        Args:
            **kwargs: 传递给各个规则的参数
            
        Returns:
            综合风控检查结果
        """
        combined_result = RiskCheckResult(RiskCheckStatus.PASS)
        combined_result.risk_score = 0.0
        
        for rule_name, rule in self.rules.items():
            if rule.is_enabled():
                try:
                    result = rule.check(**kwargs)
                    
                    # 合并结果
                    combined_result.violations.extend(result.violations)
                    combined_result.warnings.extend(result.warnings)
                    combined_result.blocked_operations.extend(result.blocked_operations)
                    
                    # 更新状态（取最严重的状态）
                    if result.status == RiskCheckStatus.BLOCKED:
                        combined_result.status = RiskCheckStatus.BLOCKED
                    elif (result.status == RiskCheckStatus.WARNING and 
                          combined_result.status == RiskCheckStatus.PASS):
                        combined_result.status = RiskCheckStatus.WARNING
                    
                    # 计算风险分数
                    for violation in result.violations:
                        if violation.risk_level == RiskLevel.CRITICAL:
                            combined_result.risk_score += 10.0
                        elif violation.risk_level == RiskLevel.HIGH:
                            combined_result.risk_score += 5.0
                        elif violation.risk_level == RiskLevel.MEDIUM:
                            combined_result.risk_score += 2.0
                        elif violation.risk_level == RiskLevel.LOW:
                            combined_result.risk_score += 1.0
                    
                except Exception as e:
                    logger.error(f"风控规则执行失败: {rule_name}, 错误: {str(e)}")
                    combined_result.warnings.append(f"风控规则 {rule_name} 执行失败")
        
        # 记录风控事件
        for violation in combined_result.violations:
            event = RiskEvent(
                event_type=violation.violation_type,
                symbol=violation.symbol,
                timestamp=violation.timestamp,
                risk_level=violation.risk_level,
                message=violation.message,
                details={
                    'rule_name': violation.rule_name,
                    'current_value': violation.current_value,
                    'limit_value': violation.limit_value
                }
            )
            self.risk_config.add_risk_event(event)
        
        return combined_result
    
    def check_single_rule(self, rule_name: str, **kwargs) -> Optional[RiskCheckResult]:
        """
        执行单个风控规则检查
        
        Args:
            rule_name: 规则名称
            **kwargs: 传递给规则的参数
            
        Returns:
            风控检查结果，如果规则不存在返回None
        """
        rule = self.rules.get(rule_name)
        if rule is None:
            logger.warning(f"风控规则不存在: {rule_name}")
            return None
        
        try:
            return rule.check(**kwargs)
        except Exception as e:
            logger.error(f"风控规则执行失败: {rule_name}, 错误: {str(e)}")
            return None
    
    def enable_rule(self, rule_name: str) -> bool:
        """启用风控规则"""
        rule = self.rules.get(rule_name)
        if rule:
            rule.enable()
            return True
        return False
    
    def disable_rule(self, rule_name: str) -> bool:
        """禁用风控规则"""
        rule = self.rules.get(rule_name)
        if rule:
            rule.disable()
            return True
        return False
    
    def get_rule_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有规则状态"""
        status = {}
        for rule_name, rule in self.rules.items():
            status[rule_name] = {
                'enabled': rule.is_enabled(),
                'last_check_time': rule.last_check_time.isoformat() if rule.last_check_time else None,
                'rule_type': type(rule).__name__
            }
        return status
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """获取风控摘要"""
        recent_events = self.risk_config.get_recent_events(24)
        
        # 按风险等级统计事件
        event_stats = {level.value: 0 for level in RiskLevel}
        for event in recent_events:
            event_stats[event.risk_level.value] += 1
        
        return {
            'total_rules': len(self.rules),
            'enabled_rules': len([r for r in self.rules.values() if r.is_enabled()]),
            'recent_events_24h': len(recent_events),
            'event_stats_24h': event_stats,
            'last_check_time': max(
                [r.last_check_time for r in self.rules.values() if r.last_check_time],
                default=None
            )
        }