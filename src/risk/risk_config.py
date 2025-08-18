"""
风控配置管理模块
================

提供风控系统的配置管理功能，包括：
- 风控参数配置和管理
- 风险等级定义
- 风控事件记录
- 动态配置更新
- 配置验证和默认值管理
"""

import logging
import json
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """风险等级枚举"""
    LOW = "low"           # 低风险
    MEDIUM = "medium"     # 中风险  
    HIGH = "high"         # 高风险
    CRITICAL = "critical" # 极高风险


class RiskEventType(Enum):
    """风控事件类型"""
    STOP_LOSS = "stop_loss"                    # 止损
    STOP_PROFIT = "stop_profit"                # 止盈
    POSITION_LIMIT = "position_limit"          # 仓位限制
    CAPITAL_LIMIT = "capital_limit"            # 资金限制
    VOLATILITY_LIMIT = "volatility_limit"      # 波动率限制
    LIQUIDITY_LIMIT = "liquidity_limit"        # 流动性限制
    CONCENTRATION_LIMIT = "concentration_limit" # 集中度限制
    TIME_LIMIT = "time_limit"                  # 时间限制
    CUSTOM = "custom"                          # 自定义事件


@dataclass
class RiskEvent:
    """风控事件数据结构"""
    event_type: RiskEventType
    symbol: str
    timestamp: datetime
    risk_level: RiskLevel
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    handled: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'event_type': self.event_type.value,
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'risk_level': self.risk_level.value,
            'message': self.message,
            'details': self.details,
            'handled': self.handled
        }


@dataclass
class PositionLimits:
    """仓位限制配置"""
    max_single_position_ratio: float = 0.20      # 单票最大仓位比例
    max_total_position_ratio: float = 0.95       # 总仓位最大比例
    max_sector_concentration: float = 0.30       # 行业最大集中度
    max_individual_stocks: int = 50              # 最大持股数量
    min_position_value: float = 1000.0          # 最小持仓价值
    max_position_value: float = 1000000.0       # 最大持仓价值


@dataclass
class PriceLimits:
    """价格风控限制"""
    stop_loss_ratio: float = 0.05               # 止损比例
    stop_profit_ratio: float = 0.15             # 止盈比例
    max_daily_loss_ratio: float = 0.03          # 单日最大亏损比例
    max_drawdown_ratio: float = 0.10            # 最大回撤比例
    volatility_threshold: float = 0.05          # 波动率阈值
    price_limit_buffer: float = 0.02            # 涨跌停缓冲区


@dataclass
class CapitalLimits:
    """资金管理限制"""
    min_cash_ratio: float = 0.05                # 最小现金比例
    max_leverage_ratio: float = 1.0             # 最大杠杆比例
    risk_capital_ratio: float = 0.02            # 风险资金比例
    emergency_cash_ratio: float = 0.10          # 紧急现金比例
    max_daily_turnover_ratio: float = 1.0       # 最大日换手率


@dataclass  
class TimeLimits:
    """时间限制配置"""
    trading_start_time: str = "09:30"           # 交易开始时间
    trading_end_time: str = "15:00"             # 交易结束时间
    max_holding_days: int = 30                  # 最大持仓天数
    cooling_period_hours: int = 24              # 冷却期（小时）
    blackout_dates: List[str] = field(default_factory=list)  # 禁止交易日期


@dataclass
class MonitoringConfig:
    """监控配置"""
    check_frequency_seconds: int = 60           # 检查频率（秒）
    alert_enabled: bool = True                  # 是否启用告警
    email_alerts: bool = False                  # 邮件告警
    sms_alerts: bool = False                   # 短信告警
    log_level: str = "INFO"                    # 日志级别
    max_events_per_hour: int = 100             # 每小时最大事件数


class RiskConfig:
    """风控配置管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化风控配置
        
        Args:
            config_file: 配置文件路径，如果为None则使用默认配置
        """
        self.config_file = config_file
        self.position_limits = PositionLimits()
        self.price_limits = PriceLimits()
        self.capital_limits = CapitalLimits()
        self.time_limits = TimeLimits()
        self.monitoring_config = MonitoringConfig()
        
        # 风控事件历史
        self.risk_events: List[RiskEvent] = []
        
        # 动态配置缓存
        self._config_cache: Dict[str, Any] = {}
        self._last_update: Optional[datetime] = None
        
        # 如果指定了配置文件，加载配置
        if config_file:
            self.load_config(config_file)
        
        logger.info("风控配置管理器初始化完成")
    
    def load_config(self, config_file: str) -> bool:
        """
        从文件加载配置
        
        Args:
            config_file: 配置文件路径
            
        Returns:
            加载是否成功
        """
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 更新各个配置组件
            if 'position_limits' in config_data:
                self._update_dataclass(self.position_limits, config_data['position_limits'])
            
            if 'price_limits' in config_data:
                self._update_dataclass(self.price_limits, config_data['price_limits'])
            
            if 'capital_limits' in config_data:
                self._update_dataclass(self.capital_limits, config_data['capital_limits'])
            
            if 'time_limits' in config_data:
                self._update_dataclass(self.time_limits, config_data['time_limits'])
            
            if 'monitoring_config' in config_data:
                self._update_dataclass(self.monitoring_config, config_data['monitoring_config'])
            
            self._last_update = datetime.now()
            logger.info(f"风控配置加载成功: {config_file}")
            return True
            
        except Exception as e:
            logger.error(f"加载风控配置失败: {config_file}, 错误: {str(e)}")
            return False
    
    def save_config(self, config_file: Optional[str] = None) -> bool:
        """
        保存配置到文件
        
        Args:
            config_file: 配置文件路径，如果为None则使用初始化时的文件
            
        Returns:
            保存是否成功
        """
        file_path = config_file or self.config_file
        if not file_path:
            logger.error("未指定配置文件路径")
            return False
        
        try:
            config_data = {
                'position_limits': asdict(self.position_limits),
                'price_limits': asdict(self.price_limits),
                'capital_limits': asdict(self.capital_limits),
                'time_limits': asdict(self.time_limits),
                'monitoring_config': asdict(self.monitoring_config),
                'last_update': datetime.now().isoformat()
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"风控配置保存成功: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存风控配置失败: {file_path}, 错误: {str(e)}")
            return False
    
    def _update_dataclass(self, instance: Any, data: Dict[str, Any]):
        """更新数据类实例"""
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
    
    def update_parameter(self, category: str, parameter: str, value: Any) -> bool:
        """
        动态更新配置参数
        
        Args:
            category: 配置类别 (position_limits, price_limits, 等)
            parameter: 参数名
            value: 新值
            
        Returns:
            更新是否成功
        """
        try:
            config_obj = getattr(self, category, None)
            if config_obj is None:
                logger.error(f"未知的配置类别: {category}")
                return False
            
            if not hasattr(config_obj, parameter):
                logger.error(f"参数不存在: {category}.{parameter}")
                return False
            
            # 验证参数值
            if not self._validate_parameter(category, parameter, value):
                return False
            
            setattr(config_obj, parameter, value)
            self._last_update = datetime.now()
            
            logger.info(f"配置参数已更新: {category}.{parameter} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"更新配置参数失败: {category}.{parameter}, 错误: {str(e)}")
            return False
    
    def _validate_parameter(self, category: str, parameter: str, value: Any) -> bool:
        """验证参数值的有效性"""
        # 比例类参数验证
        ratio_params = [
            'max_single_position_ratio', 'max_total_position_ratio', 
            'max_sector_concentration', 'stop_loss_ratio', 'stop_profit_ratio',
            'max_daily_loss_ratio', 'max_drawdown_ratio', 'min_cash_ratio',
            'risk_capital_ratio', 'emergency_cash_ratio'
        ]
        
        if parameter in ratio_params:
            if not isinstance(value, (int, float)) or value < 0 or value > 1:
                logger.error(f"比例参数值无效: {parameter} = {value}, 应该在0-1之间")
                return False
        
        # 正数参数验证
        positive_params = [
            'max_individual_stocks', 'min_position_value', 'max_position_value',
            'max_holding_days', 'cooling_period_hours', 'check_frequency_seconds',
            'max_events_per_hour'
        ]
        
        if parameter in positive_params:
            if not isinstance(value, (int, float)) or value <= 0:
                logger.error(f"正数参数值无效: {parameter} = {value}, 应该大于0")
                return False
        
        return True
    
    def get_parameter(self, category: str, parameter: str) -> Any:
        """获取配置参数值"""
        try:
            config_obj = getattr(self, category, None)
            if config_obj is None:
                return None
            
            return getattr(config_obj, parameter, None)
            
        except Exception as e:
            logger.error(f"获取配置参数失败: {category}.{parameter}, 错误: {str(e)}")
            return None
    
    def add_risk_event(self, event: RiskEvent):
        """添加风控事件"""
        self.risk_events.append(event)
        logger.warning(f"风控事件: {event.event_type.value} - {event.symbol} - {event.message}")
    
    def get_recent_events(self, hours: int = 24) -> List[RiskEvent]:
        """获取最近的风控事件"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [event for event in self.risk_events if event.timestamp >= cutoff_time]
    
    def get_events_by_symbol(self, symbol: str, hours: int = 24) -> List[RiskEvent]:
        """获取特定股票的风控事件"""
        recent_events = self.get_recent_events(hours)
        return [event for event in recent_events if event.symbol == symbol]
    
    def clear_old_events(self, days: int = 7):
        """清理旧的风控事件"""
        cutoff_time = datetime.now() - timedelta(days=days)
        initial_count = len(self.risk_events)
        self.risk_events = [event for event in self.risk_events if event.timestamp >= cutoff_time]
        cleared_count = initial_count - len(self.risk_events)
        
        if cleared_count > 0:
            logger.info(f"已清理 {cleared_count} 个过期风控事件")
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            'position_limits': asdict(self.position_limits),
            'price_limits': asdict(self.price_limits),
            'capital_limits': asdict(self.capital_limits),
            'time_limits': asdict(self.time_limits),
            'monitoring_config': asdict(self.monitoring_config),
            'last_update': self._last_update.isoformat() if self._last_update else None,
            'total_events': len(self.risk_events),
            'recent_events': len(self.get_recent_events())
        }
    
    def validate_all_config(self) -> Dict[str, List[str]]:
        """验证所有配置的有效性"""
        validation_results = {
            'errors': [],
            'warnings': []
        }
        
        # 验证仓位限制
        if self.position_limits.max_single_position_ratio > self.position_limits.max_total_position_ratio:
            validation_results['errors'].append("单票最大仓位比例不能大于总仓位比例")
        
        if self.position_limits.max_sector_concentration > self.position_limits.max_total_position_ratio:
            validation_results['warnings'].append("行业集中度较高，可能增加风险")
        
        # 验证价格限制
        if self.price_limits.stop_loss_ratio >= self.price_limits.stop_profit_ratio:
            validation_results['warnings'].append("止损比例接近或大于止盈比例")
        
        # 验证资金限制
        total_reserved_ratio = (self.capital_limits.min_cash_ratio + 
                               self.capital_limits.emergency_cash_ratio)
        if total_reserved_ratio > 0.5:
            validation_results['warnings'].append("现金储备比例过高，可能影响收益")
        
        return validation_results


# 创建默认的全局风控配置实例
default_risk_config = RiskConfig()