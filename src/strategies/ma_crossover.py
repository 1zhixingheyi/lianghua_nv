"""
双均线交叉策略

基于快慢均线交叉的趋势跟踪策略
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
from datetime import datetime

from .base_strategy import BaseStrategy, Signal, SignalType, TechnicalIndicators
import logging

logger = logging.getLogger(__name__)


class MovingAverageCrossoverStrategy(BaseStrategy):
    """双均线交叉策略
    
    策略逻辑：
    1. 当快速均线上穿慢速均线时，产生买入信号
    2. 当快速均线下穿慢速均线时，产生卖出信号
    3. 支持趋势过滤和信号确认机制
    """
    
    def __init__(self, name: str = "MA_Crossover", params: Dict[str, Any] = None):
        """
        初始化双均线策略
        
        Args:
            name: 策略名称
            params: 策略参数
        """
        super().__init__(name, params)
        
        # 信号状态跟踪
        self.last_signal_type = {}
        self.signal_confirmation = {}
    
    def get_default_parameters(self) -> Dict[str, Any]:
        """获取默认参数"""
        return {
            'fast_period': 10,          # 快速均线周期
            'slow_period': 30,          # 慢速均线周期
            'ma_type': 'SMA',           # 均线类型：SMA、EMA
            'min_crossover_gap': 0.01,  # 最小交叉幅度（%）
            'trend_filter': True,       # 是否启用趋势过滤
            'trend_period': 50,         # 趋势过滤周期
            'signal_confirmation': 1,   # 信号确认周期
            'min_data_length': 60,      # 最小数据长度
            'volume_filter': False,     # 是否启用成交量过滤
            'min_volume_ratio': 1.2     # 最小成交量比率
        }
    
    def _validate_parameters(self):
        """验证参数有效性"""
        fast_period = self.params.get('fast_period', 10)
        slow_period = self.params.get('slow_period', 30)
        
        if fast_period <= 0 or slow_period <= 0:
            raise ValueError("均线周期必须大于0")
        
        if fast_period >= slow_period:
            raise ValueError("快速均线周期必须小于慢速均线周期")
        
        ma_type = self.params.get('ma_type', 'SMA')
        if ma_type not in ['SMA', 'EMA']:
            raise ValueError("均线类型必须是SMA或EMA")
        
        min_crossover_gap = self.params.get('min_crossover_gap', 0.01)
        if min_crossover_gap < 0:
            raise ValueError("最小交叉幅度不能为负数")
        
        signal_confirmation = self.params.get('signal_confirmation', 1)
        if signal_confirmation < 1:
            raise ValueError("信号确认周期必须大于等于1")
    
    def calculate_indicators(self, data: pd.DataFrame) -> Dict[str, pd.Series]:
        """计算技术指标"""
        try:
            indicators = {}
            
            close_price = data['close']
            
            # 计算均线
            fast_period = self.params['fast_period']
            slow_period = self.params['slow_period']
            ma_type = self.params['ma_type']
            
            if ma_type == 'SMA':
                indicators['fast_ma'] = TechnicalIndicators.sma(close_price, fast_period)
                indicators['slow_ma'] = TechnicalIndicators.sma(close_price, slow_period)
            else:  # EMA
                indicators['fast_ma'] = TechnicalIndicators.ema(close_price, fast_period)
                indicators['slow_ma'] = TechnicalIndicators.ema(close_price, slow_period)
            
            # 计算趋势过滤指标
            if self.params.get('trend_filter', True):
                trend_period = self.params['trend_period']
                indicators['trend_ma'] = TechnicalIndicators.sma(close_price, trend_period)
            
            # 计算成交量指标
            if self.params.get('volume_filter', False):
                volume_period = fast_period
                indicators['avg_volume'] = TechnicalIndicators.sma(data['volume'], volume_period)
            
            # 计算交叉信号
            indicators['ma_diff'] = indicators['fast_ma'] - indicators['slow_ma']
            indicators['ma_diff_pct'] = (indicators['ma_diff'] / indicators['slow_ma']) * 100
            
            return indicators
            
        except Exception as e:
            logger.error(f"计算技术指标失败: {str(e)}")
            return {}
    
    def generate_signals(self, data: pd.DataFrame, indicators: Dict[str, pd.Series]) -> List[Signal]:
        """生成交易信号"""
        signals = []
        
        try:
            if not indicators or len(data) < 2:
                return signals
            
            close_price = data['close']
            volume = data['volume']
            
            fast_ma = indicators['fast_ma']
            slow_ma = indicators['slow_ma']
            ma_diff = indicators['ma_diff']
            ma_diff_pct = indicators['ma_diff_pct']
            
            # 获取参数
            min_crossover_gap = self.params['min_crossover_gap']
            signal_confirmation = self.params['signal_confirmation']
            
            # 检测交叉点
            for i in range(1, len(data)):
                if pd.isna(fast_ma.iloc[i]) or pd.isna(slow_ma.iloc[i]):
                    continue
                
                current_diff = ma_diff.iloc[i]
                prev_diff = ma_diff.iloc[i-1]
                current_diff_pct = abs(ma_diff_pct.iloc[i])
                
                signal_type = None
                confidence = 0.5
                reason = ""
                
                # 检测金叉（快线上穿慢线）
                if prev_diff <= 0 and current_diff > 0 and current_diff_pct >= min_crossover_gap:
                    signal_type = SignalType.BUY
                    reason = f"金叉：快线({fast_ma.iloc[i]:.2f})上穿慢线({slow_ma.iloc[i]:.2f})"
                    confidence = min(0.9, 0.5 + current_diff_pct / 2)
                
                # 检测死叉（快线下穿慢线）
                elif prev_diff >= 0 and current_diff < 0 and current_diff_pct >= min_crossover_gap:
                    signal_type = SignalType.SELL
                    reason = f"死叉：快线({fast_ma.iloc[i]:.2f})下穿慢线({slow_ma.iloc[i]:.2f})"
                    confidence = min(0.9, 0.5 + current_diff_pct / 2)
                
                if signal_type:
                    # 趋势过滤
                    if self.params.get('trend_filter', True):
                        trend_ma = indicators.get('trend_ma')
                        if trend_ma is not None and not pd.isna(trend_ma.iloc[i]):
                            current_price = close_price.iloc[i]
                            trend_price = trend_ma.iloc[i]
                            
                            # 只在趋势一致时发出信号
                            if signal_type == SignalType.BUY and current_price < trend_price:
                                logger.debug(f"金叉信号被趋势过滤器过滤: 价格({current_price:.2f}) < 趋势线({trend_price:.2f})")
                                continue
                            elif signal_type == SignalType.SELL and current_price > trend_price:
                                logger.debug(f"死叉信号被趋势过滤器过滤: 价格({current_price:.2f}) > 趋势线({trend_price:.2f})")
                                continue
                            
                            # 调整置信度
                            trend_strength = abs(current_price - trend_price) / trend_price
                            confidence = min(0.95, confidence + trend_strength)
                    
                    # 成交量过滤
                    if self.params.get('volume_filter', False):
                        avg_volume = indicators.get('avg_volume')
                        if avg_volume is not None and not pd.isna(avg_volume.iloc[i]):
                            current_volume = volume.iloc[i]
                            avg_vol = avg_volume.iloc[i]
                            min_volume_ratio = self.params['min_volume_ratio']
                            
                            if current_volume < avg_vol * min_volume_ratio:
                                logger.debug(f"信号被成交量过滤器过滤: 成交量({current_volume}) < 平均成交量({avg_vol:.0f}) * {min_volume_ratio}")
                                continue
                            
                            # 根据成交量调整置信度
                            volume_ratio = current_volume / avg_vol
                            confidence = min(0.95, confidence + (volume_ratio - 1) * 0.1)
                    
                    # 信号确认
                    if self._confirm_signal(data.index[i], signal_type, signal_confirmation):
                        timestamp = data.index[i] if hasattr(data.index[i], 'to_pydatetime') else datetime.now()
                        
                        signal = Signal(
                            symbol="",  # 将在process_data中设置
                            signal_type=signal_type,
                            timestamp=timestamp,
                            price=close_price.iloc[i],
                            volume=int(volume.iloc[i]) if not pd.isna(volume.iloc[i]) else None,
                            confidence=confidence,
                            reason=reason,
                            metadata={
                                'fast_ma': fast_ma.iloc[i],
                                'slow_ma': slow_ma.iloc[i],
                                'ma_diff': current_diff,
                                'ma_diff_pct': ma_diff_pct.iloc[i],
                                'trend_filter': self.params.get('trend_filter', False),
                                'volume_filter': self.params.get('volume_filter', False)
                            }
                        )
                        
                        signals.append(signal)
                        logger.debug(f"生成交易信号: {signal_type.value}, 价格: {close_price.iloc[i]:.2f}, 置信度: {confidence:.2f}")
            
            return signals
            
        except Exception as e:
            logger.error(f"生成交易信号失败: {str(e)}")
            return []
    
    def _confirm_signal(self, timestamp, signal_type: SignalType, confirmation_period: int) -> bool:
        """信号确认机制
        
        Args:
            timestamp: 时间戳
            signal_type: 信号类型
            confirmation_period: 确认周期
            
        Returns:
            是否确认信号
        """
        signal_key = f"{signal_type.value}"
        
        if signal_key not in self.signal_confirmation:
            self.signal_confirmation[signal_key] = []
        
        # 添加当前信号
        self.signal_confirmation[signal_key].append(timestamp)
        
        # 清理过期信号
        cutoff_time = timestamp - pd.Timedelta(periods=confirmation_period, freq='D')
        self.signal_confirmation[signal_key] = [
            t for t in self.signal_confirmation[signal_key] 
            if t >= cutoff_time
        ]
        
        # 检查确认条件
        if confirmation_period <= 1:
            return True
        
        return len(self.signal_confirmation[signal_key]) >= confirmation_period
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """获取策略详细信息"""
        base_info = self.get_strategy_status()
        
        # 添加策略特有信息
        strategy_info = {
            **base_info,
            'strategy_type': '双均线交叉',
            'description': '基于快慢均线交叉的趋势跟踪策略',
            'key_parameters': {
                'fast_period': self.params['fast_period'],
                'slow_period': self.params['slow_period'],
                'ma_type': self.params['ma_type'],
                'min_crossover_gap': self.params['min_crossover_gap'],
                'trend_filter': self.params.get('trend_filter', True),
                'signal_confirmation': self.params['signal_confirmation']
            }
        }
        
        return strategy_info
    
    def optimize_parameters(self, data: pd.DataFrame, param_ranges: Dict[str, List]) -> Dict[str, Any]:
        """参数优化
        
        Args:
            data: 历史数据
            param_ranges: 参数范围字典
            
        Returns:
            最优参数组合
        """
        # 这里可以实现网格搜索或其他优化算法
        # 暂时返回当前参数
        logger.info("参数优化功能将在后续版本中实现")
        return self.params