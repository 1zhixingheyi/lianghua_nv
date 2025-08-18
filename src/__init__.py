"""
量化交易系统 - 主包

这个包包含了量化交易系统的所有核心模块：
- backtest: 回测引擎
- config: 配置管理
- data: 数据管理
- monitor: 监控系统
- optimization: 优化模块
- risk: 风险管理
- strategies: 交易策略
- trading: 交易执行
- validation: 验证模块
"""

__version__ = "1.0.0"
__author__ = "Lianghua Trading Team"

# 导入核心模块
from . import backtest
from . import config
from . import data
from . import monitor
from . import optimization
from . import risk
from . import strategies
from . import trading
from . import validation

__all__ = [
    'backtest',
    'config', 
    'data',
    'monitor',
    'optimization',
    'risk',
    'strategies',
    'trading',
    'validation'
]