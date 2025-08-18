"""
策略模块

提供完整的量化交易策略框架，包括策略基类、具体策略实现和策略管理功能
"""

# 导入基础类和枚举
from .base_strategy import (
    BaseStrategy, 
    Signal, 
    SignalType, 
    Position, 
    PositionSide, 
    StrategyState,
    TechnicalIndicators
)

# 导入具体策略实现
from .ma_crossover import MovingAverageCrossoverStrategy
from .rsi_strategy import RSIStrategy

# 导入策略管理器
from .strategy_manager import StrategyManager, get_strategy_manager

# 模块公开接口
__all__ = [
    # 基础类和枚举
    'BaseStrategy',
    'Signal',
    'SignalType', 
    'Position',
    'PositionSide',
    'StrategyState',
    'TechnicalIndicators',
    
    # 具体策略
    'MovingAverageCrossoverStrategy',
    'RSIStrategy',
    
    # 策略管理
    'StrategyManager',
    'get_strategy_manager'
]

# 版本信息
__version__ = '1.0.0'

# 模块元信息
__author__ = 'LiangHua Quantitative Team'
__email__ = 'dev@lianghua.com'
__description__ = '量化交易策略框架MVP版本'

# 策略注册表 - 用于快速查找可用策略
AVAILABLE_STRATEGIES = {
    'MovingAverageCrossover': {
        'class': MovingAverageCrossoverStrategy,
        'name': '双均线交叉策略',
        'description': '基于快慢均线交叉的趋势跟踪策略',
        'category': '趋势跟踪',
        'risk_level': '中',
        'time_frame': ['日线', '小时线'],
        'market_type': ['股票', '期货', '数字货币']
    },
    'RSI': {
        'class': RSIStrategy,
        'name': 'RSI反转策略', 
        'description': '基于相对强弱指标的反转交易策略',
        'category': '反转策略',
        'risk_level': '中高',
        'time_frame': ['日线', '小时线', '分钟线'],
        'market_type': ['股票', '期货', '数字货币']
    }
}

def get_strategy_catalog():
    """获取策略目录
    
    Returns:
        策略目录字典
    """
    return AVAILABLE_STRATEGIES.copy()

def create_strategy_by_name(strategy_name: str, instance_name: str = None, params: dict = None):
    """根据策略名称创建策略实例
    
    Args:
        strategy_name: 策略名称
        instance_name: 实例名称
        params: 策略参数
        
    Returns:
        策略实例
        
    Raises:
        ValueError: 策略名称不存在时抛出
    """
    if strategy_name not in AVAILABLE_STRATEGIES:
        available = list(AVAILABLE_STRATEGIES.keys())
        raise ValueError(f"策略 '{strategy_name}' 不存在。可用策略: {available}")
    
    strategy_class = AVAILABLE_STRATEGIES[strategy_name]['class']
    instance_name = instance_name or f"{strategy_name}_instance"
    
    return strategy_class(name=instance_name, params=params)

def list_strategy_categories():
    """列出所有策略分类
    
    Returns:
        策略分类列表
    """
    categories = set()
    for info in AVAILABLE_STRATEGIES.values():
        categories.add(info['category'])
    return sorted(list(categories))

def get_strategies_by_category(category: str):
    """根据分类获取策略列表
    
    Args:
        category: 策略分类
        
    Returns:
        属于该分类的策略名称列表
    """
    strategies = []
    for name, info in AVAILABLE_STRATEGIES.items():
        if info['category'] == category:
            strategies.append(name)
    return strategies

def get_strategies_by_risk_level(risk_level: str):
    """根据风险等级获取策略列表
    
    Args:
        risk_level: 风险等级 ('低', '中', '高', '中高')
        
    Returns:
        属于该风险等级的策略名称列表
    """
    strategies = []
    for name, info in AVAILABLE_STRATEGIES.items():
        if info['risk_level'] == risk_level:
            strategies.append(name)
    return strategies

# 模块初始化日志
import logging
logger = logging.getLogger(__name__)
logger.info(f"策略模块已加载，包含 {len(AVAILABLE_STRATEGIES)} 个策略")