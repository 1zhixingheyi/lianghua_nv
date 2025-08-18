"""
回测模块
================

提供完整的量化交易回测功能，包括：
- 回测引擎
- 投资组合管理
- 绩效分析
- 结果可视化

主要组件:
- engine: 回测引擎核心
- portfolio: 投资组合管理
- performance: 绩效分析
- visualizer: 结果可视化
"""

from .engine import BacktestEngine, OrderSide, OrderType, Order, Trade, MarketData
from .portfolio import Portfolio, Position
from .performance import PerformanceAnalyzer

# 条件导入可视化模块
try:
    from .visualizer import BacktestVisualizer
    HAS_VISUALIZER = True
except ImportError:
    BacktestVisualizer = None
    HAS_VISUALIZER = False

__version__ = "1.0.0"
__author__ = "Lianghua VN Team"

__all__ = [
    "BacktestEngine",
    "OrderSide",
    "OrderType",
    "Order",
    "Trade",
    "MarketData",
    "Portfolio",
    "Position",
    "PerformanceAnalyzer"
]

# 如果可视化模块可用，添加到导出列表
if HAS_VISUALIZER:
    __all__.append("BacktestVisualizer")