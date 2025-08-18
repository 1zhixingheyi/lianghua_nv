"""
风控系统模块
============

提供全面的风险管理功能，包括：
- 基础风控规则（止损止盈、持仓限制）
- 仓位管理（单票仓位、总仓位、行业集中度）
- 资金管理（可用资金、风险敞口、杠杆控制）
- 风控监控（实时风险监测、告警机制）
- 风控配置（动态参数调整、规则热更新）

主要组件：
- RiskConfig: 风控配置管理
- BaseRiskManager: 基础风控规则
- PositionManager: 仓位管理
- MoneyManager: 资金管理
- RiskMonitor: 风控监控
"""

from .risk_config import RiskConfig, RiskLevel, RiskEvent
from .base_risk import BaseRiskManager, RiskCheckResult, RiskViolation
from .position_manager import PositionManager, PositionLimits
from .money_manager import MoneyManager, FundAllocation
from .risk_monitor import RiskMonitor, RiskAlert

__version__ = "1.0.0"
__author__ = "量化交易系统"

__all__ = [
    # 配置相关
    'RiskConfig',
    'RiskLevel', 
    'RiskEvent',
    
    # 基础风控
    'BaseRiskManager',
    'RiskCheckResult',
    'RiskViolation',
    
    # 仓位管理
    'PositionManager',
    'PositionLimits',
    
    # 资金管理
    'MoneyManager', 
    'FundAllocation',
    
    # 风控监控
    'RiskMonitor',
    'RiskAlert'
]

# 风控系统版本信息
RISK_SYSTEM_INFO = {
    'version': __version__,
    'author': __author__,
    'description': '量化交易风控系统',
    'components': [
        'RiskConfig - 风控配置管理',
        'BaseRiskManager - 基础风控规则',
        'PositionManager - 仓位管理',
        'MoneyManager - 资金管理', 
        'RiskMonitor - 风控监控'
    ]
}