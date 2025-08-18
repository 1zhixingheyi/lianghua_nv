"""
风控引擎集成模块
================

将风控系统与策略和回测系统集成，提供：
- 统一的风控接口
- 与策略系统的集成
- 与回测系统的集成
- 实时风控检查
- 风控决策执行
"""

import logging
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass

from .risk_config import RiskConfig, RiskEvent, RiskEventType, RiskLevel
from .base_risk import BaseRiskManager, RiskCheckResult, RiskCheckStatus
from .position_manager import PositionManager
from .money_manager import MoneyManager
from .risk_monitor import RiskMonitor

# 导入策略系统
from src.strategies.base_strategy import Signal, SignalType, Position as StrategyPosition

logger = logging.getLogger(__name__)


@dataclass
class RiskDecision:
    """风控决策"""
    allow_trade: bool
    decision_reason: str
    risk_score: float
    suggested_quantity: Optional[float] = None
    warnings: List[str] = None
    restrictions: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.restrictions is None:
            self.restrictions = []


class RiskEngine:
    """风控引擎 - 统一的风控接口"""
    
    def __init__(self, initial_capital: float = 1000000.0, config_file: Optional[str] = None):
        """
        初始化风控引擎
        
        Args:
            initial_capital: 初始资金
            config_file: 风控配置文件路径
        """
        self.initial_capital = initial_capital
        
        # 初始化风控组件
        self.risk_config = RiskConfig(config_file)
        self.base_risk_manager = BaseRiskManager(self.risk_config)
        self.position_manager = PositionManager(self.risk_config, initial_capital)
        self.money_manager = MoneyManager(self.risk_config, initial_capital)
        self.risk_monitor = RiskMonitor(
            self.risk_config,
            self.base_risk_manager,
            self.position_manager,
            self.money_manager
        )
        
        # 风控决策缓存
        self.decision_cache: Dict[str, RiskDecision] = {}
        
        # 交易统计
        self.trade_stats = {
            'total_trades': 0,
            'blocked_trades': 0,
            'risk_triggered_exits': 0,
            'last_trade_time': None
        }
        
        logger.info("风控引擎初始化完成")
    
    def start_monitoring(self):
        """启动风控监控"""
        self.risk_monitor.start_monitoring()
        logger.info("风控监控已启动")
    
    def stop_monitoring(self):
        """停止风控监控"""
        self.risk_monitor.stop_monitoring()
        logger.info("风控监控已停止")
    
    def check_signal_risk(self, signal: Signal, current_portfolio: Optional[Dict] = None) -> RiskDecision:
        """
        检查交易信号的风险
        
        Args:
            signal: 交易信号
            current_portfolio: 当前投资组合状态
            
        Returns:
            风控决策
        """
        try:
            # 获取当前价格和持仓信息
            current_position = self.position_manager.get_position(signal.symbol)
            
            # 计算建议交易量
            if signal.signal_type in [SignalType.BUY, SignalType.SELL]:
                suggested_quantity, required_capital = self.money_manager.calculate_position_size(
                    signal.symbol, 
                    signal.price
                )
            else:
                suggested_quantity = signal.volume or 0
                required_capital = suggested_quantity * signal.price
            
            # 执行风控检查
            risk_checks = []
            warnings = []
            restrictions = []
            
            # 1. 基础风控检查
            if signal.signal_type == SignalType.SELL and current_position:
                # 止损止盈检查
                stop_loss_result = self.base_risk_manager.check_single_rule(
                    'stop_loss',
                    symbol=signal.symbol,
                    current_price=signal.price,
                    avg_price=current_position.avg_price,
                    position_size=current_position.quantity
                )
                if stop_loss_result:
                    risk_checks.append(stop_loss_result)
                
                stop_profit_result = self.base_risk_manager.check_single_rule(
                    'stop_profit',
                    symbol=signal.symbol,
                    current_price=signal.price,
                    avg_price=current_position.avg_price,
                    position_size=current_position.quantity
                )
                if stop_profit_result:
                    risk_checks.append(stop_profit_result)
            
            # 2. 交易时间检查
            time_result = self.base_risk_manager.check_single_rule(
                'trading_time',
                current_time=signal.timestamp
            )
            if time_result:
                risk_checks.append(time_result)
            
            # 3. 仓位限制检查
            if signal.signal_type == SignalType.BUY:
                position_result = self.position_manager.check_position_limits(
                    signal.symbol,
                    suggested_quantity,
                    signal.price
                )
                risk_checks.append(position_result)
            
            # 4. 资金检查
            if signal.signal_type == SignalType.BUY:
                margin_result = self.money_manager.check_margin_requirements(required_capital)
                risk_checks.append(margin_result)
            
            # 5. 现金限制检查
            cash_result = self.money_manager.check_cash_limits()
            risk_checks.append(cash_result)
            
            # 综合评估风控结果
            overall_status = RiskCheckStatus.PASS
            risk_score = 0.0
            
            for result in risk_checks:
                if result.status == RiskCheckStatus.BLOCKED:
                    overall_status = RiskCheckStatus.BLOCKED
                    restrictions.extend(result.blocked_operations)
                elif result.status == RiskCheckStatus.WARNING and overall_status == RiskCheckStatus.PASS:
                    overall_status = RiskCheckStatus.WARNING
                
                warnings.extend(result.warnings)
                risk_score += len(result.violations) * 10  # 每个违规加10分
            
            # 做出决策
            allow_trade = overall_status != RiskCheckStatus.BLOCKED
            
            if overall_status == RiskCheckStatus.BLOCKED:
                decision_reason = "风控检查未通过: " + "; ".join(restrictions)
                suggested_quantity = 0
            elif overall_status == RiskCheckStatus.WARNING:
                decision_reason = "风控警告，建议谨慎交易: " + "; ".join(warnings)
            else:
                decision_reason = "风控检查通过"
            
            decision = RiskDecision(
                allow_trade=allow_trade,
                decision_reason=decision_reason,
                risk_score=risk_score,
                suggested_quantity=suggested_quantity,
                warnings=warnings,
                restrictions=restrictions
            )
            
            # 缓存决策
            cache_key = f"{signal.symbol}_{signal.signal_type.value}_{signal.timestamp.timestamp()}"
            self.decision_cache[cache_key] = decision
            
            # 更新统计
            self.trade_stats['total_trades'] += 1
            if not allow_trade:
                self.trade_stats['blocked_trades'] += 1
            self.trade_stats['last_trade_time'] = datetime.now()
            
            logger.info(f"风控决策: {signal.symbol} {signal.signal_type.value} - {decision_reason}")
            
            return decision
            
        except Exception as e:
            logger.error(f"风控检查失败: {str(e)}")
            return RiskDecision(
                allow_trade=False,
                decision_reason=f"风控检查异常: {str(e)}",
                risk_score=100.0,
                restrictions=[f"系统异常: {str(e)}"]
            )
    
    def update_position(self, symbol: str, quantity: float, price: float, 
                       signal_type: SignalType, sector: Optional[str] = None):
        """
        更新持仓信息
        
        Args:
            symbol: 股票代码
            quantity: 数量变化
            price: 成交价格
            signal_type: 信号类型
            sector: 行业分类
        """
        try:
            # 根据信号类型调整数量
            if signal_type == SignalType.SELL or signal_type == SignalType.CLOSE:
                quantity = -abs(quantity)  # 卖出为负数
            
            # 更新仓位管理器
            self.position_manager.update_position(symbol, quantity, price, sector)
            
            # 更新资金管理器
            self.money_manager.update_exposure(symbol, quantity, price)
            
            logger.info(f"持仓更新: {symbol}, 数量变化: {quantity}, 价格: {price}")
            
        except Exception as e:
            logger.error(f"更新持仓失败: {str(e)}")
    
    def update_market_prices(self, price_data: Dict[str, float]):
        """
        更新市场价格
        
        Args:
            price_data: 价格数据 {symbol: price}
        """
        self.position_manager.update_current_prices(price_data)
        logger.debug(f"已更新 {len(price_data)} 个股票的价格")
    
    def check_stop_loss_profit(self, symbol: str, current_price: float) -> Optional[SignalType]:
        """
        检查止损止盈
        
        Args:
            symbol: 股票代码
            current_price: 当前价格
            
        Returns:
            如果触发止损止盈，返回相应的信号类型
        """
        position = self.position_manager.get_position(symbol)
        if not position or position.is_flat:
            return None
        
        try:
            # 检查止损
            stop_loss_result = self.base_risk_manager.check_single_rule(
                'stop_loss',
                symbol=symbol,
                current_price=current_price,
                avg_price=position.avg_price,
                position_size=position.quantity
            )
            
            if stop_loss_result and stop_loss_result.is_blocked:
                self.trade_stats['risk_triggered_exits'] += 1
                logger.warning(f"触发止损: {symbol} 当前价格 {current_price}, 成本价 {position.avg_price}")
                return SignalType.CLOSE
            
            # 检查止盈
            stop_profit_result = self.base_risk_manager.check_single_rule(
                'stop_profit',
                symbol=symbol,
                current_price=current_price,
                avg_price=position.avg_price,
                position_size=position.quantity
            )
            
            if stop_profit_result and stop_profit_result.warnings:
                logger.info(f"建议止盈: {symbol} 当前价格 {current_price}, 成本价 {position.avg_price}")
                # 止盈通常是建议性的，不强制执行
                return None
            
            return None
            
        except Exception as e:
            logger.error(f"止损止盈检查失败: {symbol}, 错误: {str(e)}")
            return None
    
    def get_position_suggestions(self) -> List[Dict[str, Any]]:
        """获取仓位调整建议"""
        return self.position_manager.suggest_position_adjustments()
    
    def get_capital_suggestions(self) -> Dict[str, Any]:
        """获取资金配置建议"""
        return self.money_manager.suggest_capital_allocation()
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """获取风控摘要"""
        return {
            'risk_config_summary': self.risk_config.get_config_summary(),
            'position_summary': self.position_manager.get_position_summary(),
            'capital_summary': self.money_manager.get_fund_utilization_stats(),
            'risk_metrics': self.risk_monitor.get_risk_metrics_summary(),
            'alert_statistics': self.risk_monitor.get_alert_statistics(),
            'trade_statistics': self.trade_stats,
            'monitoring_status': self.risk_monitor.get_monitoring_dashboard_data()
        }
    
    def generate_risk_report(self, report_type: str = "daily") -> Dict[str, Any]:
        """生成风控报告"""
        return self.risk_monitor.generate_risk_report(report_type)
    
    def reset(self):
        """重置风控引擎"""
        self.position_manager.reset()
        self.money_manager.reset()
        self.decision_cache.clear()
        self.trade_stats = {
            'total_trades': 0,
            'blocked_trades': 0,
            'risk_triggered_exits': 0,
            'last_trade_time': None
        }
        logger.info("风控引擎已重置")


class StrategyRiskAdapter:
    """策略系统风控适配器"""
    
    def __init__(self, risk_engine: RiskEngine):
        self.risk_engine = risk_engine
    
    def process_strategy_signals(self, signals: List[Signal], 
                                current_positions: Dict[str, StrategyPosition]) -> List[Signal]:
        """
        处理策略信号，应用风控过滤
        
        Args:
            signals: 原始策略信号
            current_positions: 当前持仓
            
        Returns:
            经过风控过滤的信号列表
        """
        filtered_signals = []
        
        for signal in signals:
            try:
                # 风控检查
                decision = self.risk_engine.check_signal_risk(signal)
                
                if decision.allow_trade:
                    # 调整交易量
                    if decision.suggested_quantity and decision.suggested_quantity != signal.volume:
                        signal.volume = int(decision.suggested_quantity)
                        signal.metadata['risk_adjusted'] = True
                        signal.metadata['original_volume'] = signal.volume
                        signal.metadata['risk_reason'] = decision.decision_reason
                    
                    filtered_signals.append(signal)
                    logger.info(f"信号通过风控: {signal.symbol} {signal.signal_type.value}")
                else:
                    logger.warning(f"信号被风控阻止: {signal.symbol} {signal.signal_type.value} - {decision.decision_reason}")
                    
                    # 记录被阻止的信号
                    signal.metadata['blocked_by_risk'] = True
                    signal.metadata['block_reason'] = decision.decision_reason
                
            except Exception as e:
                logger.error(f"处理信号时出错: {signal.symbol}, 错误: {str(e)}")
        
        return filtered_signals
    
    def check_exit_conditions(self, positions: Dict[str, StrategyPosition], 
                             current_prices: Dict[str, float]) -> List[Signal]:
        """
        检查退出条件（止损止盈等）
        
        Args:
            positions: 当前持仓
            current_prices: 当前价格
            
        Returns:
            退出信号列表
        """
        exit_signals = []
        
        for symbol, position in positions.items():
            if position.side.value == 'flat' or position.size == 0:
                continue
                
            current_price = current_prices.get(symbol)
            if not current_price:
                continue
            
            # 检查止损止盈
            exit_signal_type = self.risk_engine.check_stop_loss_profit(symbol, current_price)
            
            if exit_signal_type:
                exit_signal = Signal(
                    symbol=symbol,
                    signal_type=exit_signal_type,
                    timestamp=datetime.now(),
                    price=current_price,
                    volume=int(position.size),
                    confidence=1.0,
                    reason="风控触发退出",
                    metadata={'triggered_by_risk': True}
                )
                
                exit_signals.append(exit_signal)
                logger.info(f"风控触发退出信号: {symbol} - {exit_signal_type.value}")
        
        return exit_signals


class BacktestRiskAdapter:
    """回测系统风控适配器"""
    
    def __init__(self, risk_engine: RiskEngine):
        self.risk_engine = risk_engine
    
    def initialize_backtest(self, initial_capital: float, start_date: str, end_date: str):
        """初始化回测风控"""
        self.risk_engine.reset()
        logger.info(f"回测风控初始化: 初始资金 {initial_capital}, 期间 {start_date} 到 {end_date}")
    
    def process_backtest_order(self, symbol: str, side: str, quantity: float, price: float, 
                              timestamp: datetime) -> Tuple[bool, str, float]:
        """
        处理回测订单的风控检查
        
        Args:
            symbol: 股票代码
            side: 买卖方向 ('buy' or 'sell')
            quantity: 数量
            price: 价格
            timestamp: 时间戳
            
        Returns:
            (是否允许交易, 拒绝原因, 调整后的数量)
        """
        try:
            # 创建模拟信号
            signal_type = SignalType.BUY if side == 'buy' else SignalType.SELL
            signal = Signal(
                symbol=symbol,
                signal_type=signal_type,
                timestamp=timestamp,
                price=price,
                volume=int(quantity)
            )
            
            # 风控检查
            decision = self.risk_engine.check_signal_risk(signal)
            
            adjusted_quantity = decision.suggested_quantity or quantity
            
            return decision.allow_trade, decision.decision_reason, adjusted_quantity
            
        except Exception as e:
            logger.error(f"回测风控检查失败: {str(e)}")
            return False, f"风控检查异常: {str(e)}", 0
    
    def update_backtest_position(self, symbol: str, quantity: float, price: float, side: str):
        """更新回测持仓"""
        signal_type = SignalType.BUY if side == 'buy' else SignalType.SELL
        self.risk_engine.update_position(symbol, quantity, price, signal_type)
    
    def get_backtest_risk_metrics(self) -> Dict[str, Any]:
        """获取回测期间的风控指标"""
        return {
            'position_metrics': self.risk_engine.position_manager.get_position_summary(),
            'capital_metrics': self.risk_engine.money_manager.get_fund_utilization_stats(),
            'trade_statistics': self.risk_engine.trade_stats,
            'risk_violations': len(self.risk_engine.risk_config.risk_events)
        }