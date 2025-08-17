"""
策略基类

提供策略开发的抽象接口和通用功能
"""

import logging
import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# 配置日志
logger = logging.getLogger(__name__)


class SignalType(Enum):
    """交易信号类型"""
    BUY = "buy"
    SELL = "sell" 
    HOLD = "hold"
    CLOSE = "close"


class PositionSide(Enum):
    """持仓方向"""
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class Signal:
    """交易信号数据结构"""
    symbol: str
    signal_type: SignalType
    timestamp: datetime
    price: float
    volume: Optional[int] = None
    confidence: float = 1.0  # 信号置信度 0-1
    reason: str = ""  # 信号产生原因
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    side: PositionSide
    size: float = 0.0
    avg_price: float = 0.0
    entry_time: Optional[datetime] = None
    pnl: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class StrategyState:
    """策略状态"""
    name: str
    is_active: bool = True
    positions: Dict[str, Position] = field(default_factory=dict)
    total_pnl: float = 0.0
    trade_count: int = 0
    win_rate: float = 0.0
    max_drawdown: float = 0.0
    last_update: Optional[datetime] = None


class BaseStrategy(ABC):
    """策略基类
    
    所有具体策略都应继承此基类并实现其抽象方法
    """
    
    def __init__(self, name: str, params: Optional[Dict[str, Any]] = None):
        """
        初始化策略
        
        Args:
            name: 策略名称
            params: 策略参数字典
        """
        self.name = name
        self.params = params or {}
        self.state = StrategyState(name=name)
        
        # 技术指标缓存
        self.indicators_cache = {}
        
        # 数据缓存
        self.data_cache = {}
        
        # 初始化策略参数
        self._init_parameters()
        
        # 验证参数
        self._validate_parameters()
        
        logger.info(f"策略 {self.name} 初始化完成，参数: {self.params}")
    
    def _init_parameters(self):
        """初始化默认参数"""
        default_params = self.get_default_parameters()
        for key, value in default_params.items():
            if key not in self.params:
                self.params[key] = value
    
    @abstractmethod
    def get_default_parameters(self) -> Dict[str, Any]:
        """获取默认参数
        
        Returns:
            默认参数字典
        """
        pass
    
    @abstractmethod
    def _validate_parameters(self):
        """验证参数有效性
        
        Raises:
            ValueError: 参数无效时抛出异常
        """
        pass
    
    @abstractmethod
    def calculate_indicators(self, data: pd.DataFrame) -> Dict[str, pd.Series]:
        """计算技术指标
        
        Args:
            data: 价格数据DataFrame，包含OHLCV数据
            
        Returns:
            技术指标字典
        """
        pass
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame, indicators: Dict[str, pd.Series]) -> List[Signal]:
        """生成交易信号
        
        Args:
            data: 价格数据
            indicators: 技术指标
            
        Returns:
            交易信号列表
        """
        pass
    
    def process_data(self, data: pd.DataFrame, symbol: str) -> List[Signal]:
        """处理数据并生成信号
        
        Args:
            data: 价格数据
            symbol: 交易品种代码
            
        Returns:
            交易信号列表
        """
        try:
            # 数据验证
            if not self._validate_data(data):
                logger.warning(f"数据验证失败: {symbol}")
                return []
            
            # 计算技术指标
            indicators = self.calculate_indicators(data)
            
            # 缓存指标
            self.indicators_cache[symbol] = indicators
            
            # 生成信号
            signals = self.generate_signals(data, indicators)
            
            # 为信号添加symbol信息
            for signal in signals:
                signal.symbol = symbol
            
            self.state.last_update = datetime.now()
            
            logger.debug(f"策略 {self.name} 处理 {symbol} 数据，生成 {len(signals)} 个信号")
            
            return signals
            
        except Exception as e:
            logger.error(f"策略 {self.name} 处理数据失败: {symbol}, 错误: {str(e)}")
            return []
    
    def _validate_data(self, data: pd.DataFrame) -> bool:
        """验证输入数据
        
        Args:
            data: 价格数据
            
        Returns:
            数据是否有效
        """
        if data is None or data.empty:
            return False
        
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            logger.warning(f"数据缺少必需列: {missing_columns}")
            return False
        
        # 检查数据长度
        min_length = self.params.get('min_data_length', 30)
        if len(data) < min_length:
            logger.warning(f"数据长度不足: {len(data)} < {min_length}")
            return False
        
        return True
    
    def update_position(self, symbol: str, signal: Signal):
        """更新持仓信息
        
        Args:
            symbol: 交易品种
            signal: 交易信号
        """
        if symbol not in self.state.positions:
            self.state.positions[symbol] = Position(symbol=symbol, side=PositionSide.FLAT)
        
        position = self.state.positions[symbol]
        
        if signal.signal_type == SignalType.BUY:
            if position.side == PositionSide.FLAT:
                position.side = PositionSide.LONG
                position.size = signal.volume or 100
                position.avg_price = signal.price
                position.entry_time = signal.timestamp
            elif position.side == PositionSide.LONG:
                # 加仓
                total_value = position.size * position.avg_price + (signal.volume or 100) * signal.price
                position.size += signal.volume or 100
                position.avg_price = total_value / position.size
        
        elif signal.signal_type == SignalType.SELL:
            if position.side == PositionSide.FLAT:
                position.side = PositionSide.SHORT
                position.size = signal.volume or 100
                position.avg_price = signal.price
                position.entry_time = signal.timestamp
        
        elif signal.signal_type == SignalType.CLOSE:
            if position.side != PositionSide.FLAT:
                # 计算盈亏
                if position.side == PositionSide.LONG:
                    pnl = (signal.price - position.avg_price) * position.size
                else:
                    pnl = (position.avg_price - signal.price) * position.size
                
                position.pnl += pnl
                self.state.total_pnl += pnl
                self.state.trade_count += 1
                
                # 平仓
                position.side = PositionSide.FLAT
                position.size = 0
                position.avg_price = 0
                position.entry_time = None
    
    def calculate_unrealized_pnl(self, symbol: str, current_price: float) -> float:
        """计算未实现盈亏
        
        Args:
            symbol: 交易品种
            current_price: 当前价格
            
        Returns:
            未实现盈亏
        """
        if symbol not in self.state.positions:
            return 0.0
        
        position = self.state.positions[symbol]
        
        if position.side == PositionSide.FLAT:
            return 0.0
        
        if position.side == PositionSide.LONG:
            unrealized_pnl = (current_price - position.avg_price) * position.size
        else:
            unrealized_pnl = (position.avg_price - current_price) * position.size
        
        position.unrealized_pnl = unrealized_pnl
        return unrealized_pnl
    
    def get_strategy_status(self) -> Dict[str, Any]:
        """获取策略状态
        
        Returns:
            策略状态字典
        """
        return {
            'name': self.name,
            'is_active': self.state.is_active,
            'total_pnl': self.state.total_pnl,
            'trade_count': self.state.trade_count,
            'win_rate': self.state.win_rate,
            'max_drawdown': self.state.max_drawdown,
            'positions_count': len([p for p in self.state.positions.values() if p.side != PositionSide.FLAT]),
            'last_update': self.state.last_update,
            'parameters': self.params
        }
    
    def reset_strategy(self):
        """重置策略状态"""
        self.state = StrategyState(name=self.name)
        self.indicators_cache.clear()
        self.data_cache.clear()
        logger.info(f"策略 {self.name} 状态已重置")
    
    def set_parameter(self, key: str, value: Any):
        """设置策略参数
        
        Args:
            key: 参数名
            value: 参数值
        """
        self.params[key] = value
        logger.info(f"策略 {self.name} 参数更新: {key} = {value}")
    
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """获取策略参数
        
        Args:
            key: 参数名
            default: 默认值
            
        Returns:
            参数值
        """
        return self.params.get(key, default)


class TechnicalIndicators:
    """技术指标计算工具类"""
    
    @staticmethod
    def sma(data: pd.Series, period: int) -> pd.Series:
        """简单移动平均线
        
        Args:
            data: 价格序列
            period: 周期
            
        Returns:
            移动平均线序列
        """
        return data.rolling(window=period).mean()
    
    @staticmethod
    def ema(data: pd.Series, period: int, alpha: Optional[float] = None) -> pd.Series:
        """指数移动平均线
        
        Args:
            data: 价格序列
            period: 周期
            alpha: 平滑系数
            
        Returns:
            指数移动平均线序列
        """
        if alpha is None:
            alpha = 2.0 / (period + 1)
        return data.ewm(alpha=alpha).mean()
    
    @staticmethod
    def rsi(data: pd.Series, period: int = 14) -> pd.Series:
        """相对强弱指标
        
        Args:
            data: 价格序列
            period: 周期
            
        Returns:
            RSI序列
        """
        delta = data.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def bollinger_bands(data: pd.Series, period: int = 20, std_dev: float = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """布林带
        
        Args:
            data: 价格序列
            period: 周期
            std_dev: 标准差倍数
            
        Returns:
            上轨、中轨、下轨
        """
        middle = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return upper, middle, lower
    
    @staticmethod
    def macd(data: pd.Series, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD指标
        
        Args:
            data: 价格序列
            fast_period: 快线周期
            slow_period: 慢线周期
            signal_period: 信号线周期
            
        Returns:
            MACD线、信号线、柱状图
        """
        fast_ema = TechnicalIndicators.ema(data, fast_period)
        slow_ema = TechnicalIndicators.ema(data, slow_period)
        
        macd_line = fast_ema - slow_ema
        signal_line = TechnicalIndicators.ema(macd_line, signal_period)
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram