"""
RSI策略

基于相对强弱指标的反转策略
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
from datetime import datetime

from .base_strategy import BaseStrategy, Signal, SignalType, TechnicalIndicators
import logging

logger = logging.getLogger(__name__)


class RSIStrategy(BaseStrategy):
    """RSI策略
    
    策略逻辑：
    1. RSI > 超买线时，产生卖出信号
    2. RSI < 超卖线时，产生买入信号
    3. 支持RSI背离检测和多级过滤
    """
    
    def __init__(self, name: str = "RSI_Strategy", params: Dict[str, Any] = None):
        """
        初始化RSI策略
        
        Args:
            name: 策略名称
            params: 策略参数
        """
        super().__init__(name, params)
        
        # 信号状态跟踪
        self.last_rsi_signal = {}
        self.price_extremes = {}  # 用于背离检测
        self.rsi_extremes = {}
    
    def get_default_parameters(self) -> Dict[str, Any]:
        """获取默认参数"""
        return {
            'rsi_period': 14,           # RSI周期
            'overbought_level': 70,     # 超买水平
            'oversold_level': 30,       # 超卖水平
            'extreme_overbought': 80,   # 极度超买
            'extreme_oversold': 20,     # 极度超卖
            'signal_confirmation': 2,   # 信号确认周期
            'divergence_detection': True,  # 是否检测背离
            'divergence_period': 20,    # 背离检测周期
            'price_filter': True,       # 价格过滤
            'trend_filter': False,      # 趋势过滤
            'trend_period': 50,         # 趋势周期
            'min_data_length': 30,      # 最小数据长度
            'volume_confirmation': False, # 成交量确认
            'min_volume_ratio': 1.1     # 最小成交量比率
        }
    
    def _validate_parameters(self):
        """验证参数有效性"""
        rsi_period = self.params.get('rsi_period', 14)
        if rsi_period <= 0:
            raise ValueError("RSI周期必须大于0")
        
        overbought = self.params.get('overbought_level', 70)
        oversold = self.params.get('oversold_level', 30)
        
        if not (0 < oversold < overbought < 100):
            raise ValueError("超买超卖水平设置无效")
        
        extreme_overbought = self.params.get('extreme_overbought', 80)
        extreme_oversold = self.params.get('extreme_oversold', 20)
        
        if extreme_overbought <= overbought or extreme_oversold >= oversold:
            raise ValueError("极值水平设置无效")
        
        signal_confirmation = self.params.get('signal_confirmation', 2)
        if signal_confirmation < 1:
            raise ValueError("信号确认周期必须大于等于1")
    
    def calculate_indicators(self, data: pd.DataFrame) -> Dict[str, pd.Series]:
        """计算技术指标"""
        try:
            indicators = {}
            
            close_price = data['close']
            high_price = data['high']
            low_price = data['low']
            volume = data['volume']
            
            # 计算RSI
            rsi_period = self.params['rsi_period']
            indicators['rsi'] = TechnicalIndicators.rsi(close_price, rsi_period)
            
            # 计算RSI移动平均（平滑RSI）
            indicators['rsi_sma'] = TechnicalIndicators.sma(indicators['rsi'], 3)
            
            # 计算趋势过滤指标
            if self.params.get('trend_filter', False):
                trend_period = self.params['trend_period']
                indicators['trend_ma'] = TechnicalIndicators.sma(close_price, trend_period)
            
            # 计算成交量指标
            if self.params.get('volume_confirmation', False):
                volume_period = rsi_period
                indicators['avg_volume'] = TechnicalIndicators.sma(volume, volume_period)
            
            # 计算背离检测所需的价格极值
            if self.params.get('divergence_detection', True):
                divergence_period = self.params['divergence_period']
                
                # 滚动最高价和最低价
                indicators['rolling_high'] = high_price.rolling(window=divergence_period).max()
                indicators['rolling_low'] = low_price.rolling(window=divergence_period).min()
                
                # RSI极值
                indicators['rsi_rolling_high'] = indicators['rsi'].rolling(window=divergence_period).max()
                indicators['rsi_rolling_low'] = indicators['rsi'].rolling(window=divergence_period).min()
            
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
            rsi = indicators['rsi']
            rsi_sma = indicators['rsi_sma']
            
            # 获取参数
            overbought = self.params['overbought_level']
            oversold = self.params['oversold_level']
            extreme_overbought = self.params['extreme_overbought']
            extreme_oversold = self.params['extreme_oversold']
            signal_confirmation = self.params['signal_confirmation']
            
            # 生成信号
            for i in range(signal_confirmation, len(data)):
                if pd.isna(rsi.iloc[i]) or pd.isna(rsi_sma.iloc[i]):
                    continue
                
                current_rsi = rsi.iloc[i]
                current_price = close_price.iloc[i]
                
                signal_type = None
                confidence = 0.5
                reason = ""
                
                # 检测超卖买入信号
                if current_rsi <= oversold:
                    # 确认RSI从超卖区域反弹
                    if self._confirm_rsi_reversal(rsi, i, 'oversold', signal_confirmation):
                        signal_type = SignalType.BUY
                        reason = f"RSI超卖反弹：RSI({current_rsi:.1f}) <= {oversold}"
                        
                        # 根据RSI值调整置信度
                        if current_rsi <= extreme_oversold:
                            confidence = 0.9
                            reason = f"RSI极度超卖反弹：RSI({current_rsi:.1f}) <= {extreme_oversold}"
                        else:
                            confidence = 0.7
                
                # 检测超买卖出信号
                elif current_rsi >= overbought:
                    # 确认RSI从超买区域回落
                    if self._confirm_rsi_reversal(rsi, i, 'overbought', signal_confirmation):
                        signal_type = SignalType.SELL
                        reason = f"RSI超买回落：RSI({current_rsi:.1f}) >= {overbought}"
                        
                        # 根据RSI值调整置信度
                        if current_rsi >= extreme_overbought:
                            confidence = 0.9
                            reason = f"RSI极度超买回落：RSI({current_rsi:.1f}) >= {extreme_overbought}"
                        else:
                            confidence = 0.7
                
                if signal_type:
                    # 背离检测
                    if self.params.get('divergence_detection', True):
                        divergence = self._detect_divergence(data, indicators, i)
                        if divergence:
                            confidence = min(0.95, confidence + 0.2)
                            reason += f" + {divergence}"
                    
                    # 趋势过滤
                    if self.params.get('trend_filter', False):
                        trend_ma = indicators.get('trend_ma')
                        if trend_ma is not None and not pd.isna(trend_ma.iloc[i]):
                            trend_price = trend_ma.iloc[i]
                            
                            # 只在趋势一致时发出信号
                            if signal_type == SignalType.BUY and current_price < trend_price * 0.98:
                                logger.debug(f"买入信号被趋势过滤器过滤: 价格({current_price:.2f}) < 趋势线({trend_price:.2f})")
                                continue
                            elif signal_type == SignalType.SELL and current_price > trend_price * 1.02:
                                logger.debug(f"卖出信号被趋势过滤器过滤: 价格({current_price:.2f}) > 趋势线({trend_price:.2f})")
                                continue
                    
                    # 成交量确认
                    if self.params.get('volume_confirmation', False):
                        avg_volume = indicators.get('avg_volume')
                        if avg_volume is not None and not pd.isna(avg_volume.iloc[i]):
                            current_volume = volume.iloc[i]
                            avg_vol = avg_volume.iloc[i]
                            min_volume_ratio = self.params['min_volume_ratio']
                            
                            if current_volume < avg_vol * min_volume_ratio:
                                logger.debug(f"信号被成交量过滤器过滤: 成交量({current_volume}) < 平均成交量({avg_vol:.0f}) * {min_volume_ratio}")
                                continue
                    
                    # 价格过滤（避免在价格跳空时交易）
                    if self.params.get('price_filter', True):
                        if i > 0:
                            prev_price = close_price.iloc[i-1]
                            price_change = abs(current_price - prev_price) / prev_price
                            if price_change > 0.05:  # 5%以上的跳空
                                logger.debug(f"信号被价格过滤器过滤: 价格跳空{price_change:.2%}")
                                continue
                    
                    timestamp = data.index[i] if hasattr(data.index[i], 'to_pydatetime') else datetime.now()
                    
                    signal = Signal(
                        symbol="",  # 将在process_data中设置
                        signal_type=signal_type,
                        timestamp=timestamp,
                        price=current_price,
                        volume=int(volume.iloc[i]) if not pd.isna(volume.iloc[i]) else None,
                        confidence=confidence,
                        reason=reason,
                        metadata={
                            'rsi': current_rsi,
                            'rsi_sma': rsi_sma.iloc[i],
                            'overbought_level': overbought,
                            'oversold_level': oversold,
                            'extreme_levels': [extreme_oversold, extreme_overbought],
                            'divergence_detection': self.params.get('divergence_detection', True),
                            'trend_filter': self.params.get('trend_filter', False)
                        }
                    )
                    
                    signals.append(signal)
                    logger.debug(f"生成RSI信号: {signal_type.value}, RSI: {current_rsi:.1f}, 价格: {current_price:.2f}")
            
            return signals
            
        except Exception as e:
            logger.error(f"生成交易信号失败: {str(e)}")
            return []
    
    def _confirm_rsi_reversal(self, rsi: pd.Series, current_index: int, zone: str, confirmation_period: int) -> bool:
        """确认RSI反转
        
        Args:
            rsi: RSI序列
            current_index: 当前索引
            zone: 区域类型 ('overbought' 或 'oversold')
            confirmation_period: 确认周期
            
        Returns:
            是否确认反转
        """
        if current_index < confirmation_period:
            return False
        
        try:
            current_rsi = rsi.iloc[current_index]
            
            if zone == 'oversold':
                # 检查是否从超卖区域反弹
                oversold_level = self.params['oversold_level']
                
                # 当前RSI需要在超卖线附近或以下
                if current_rsi > oversold_level + 5:
                    return False
                
                # 检查前几期是否有更低的RSI值
                prev_period = rsi.iloc[current_index-confirmation_period:current_index]
                if prev_period.min() >= current_rsi:
                    return False
                
                # 检查是否开始反弹
                if confirmation_period > 1:
                    recent_trend = rsi.iloc[current_index-1:current_index+1].diff().iloc[-1]
                    return recent_trend > 0
                
                return True
                
            elif zone == 'overbought':
                # 检查是否从超买区域回落
                overbought_level = self.params['overbought_level']
                
                # 当前RSI需要在超买线附近或以上
                if current_rsi < overbought_level - 5:
                    return False
                
                # 检查前几期是否有更高的RSI值
                prev_period = rsi.iloc[current_index-confirmation_period:current_index]
                if prev_period.max() <= current_rsi:
                    return False
                
                # 检查是否开始回落
                if confirmation_period > 1:
                    recent_trend = rsi.iloc[current_index-1:current_index+1].diff().iloc[-1]
                    return recent_trend < 0
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"RSI反转确认失败: {str(e)}")
            return False
    
    def _detect_divergence(self, data: pd.DataFrame, indicators: Dict[str, pd.Series], current_index: int) -> str:
        """检测价格与RSI背离
        
        Args:
            data: 价格数据
            indicators: 技术指标
            current_index: 当前索引
            
        Returns:
            背离描述字符串，无背离返回空字符串
        """
        try:
            divergence_period = self.params['divergence_period']
            
            if current_index < divergence_period:
                return ""
            
            close_price = data['close']
            rsi = indicators['rsi']
            
            # 获取当前和过去的极值
            current_price = close_price.iloc[current_index]
            current_rsi = rsi.iloc[current_index]
            
            # 查找过去一段时间的极值
            lookback_start = max(0, current_index - divergence_period)
            price_window = close_price.iloc[lookback_start:current_index]
            rsi_window = rsi.iloc[lookback_start:current_index]
            
            # 检测顶背离（价格新高，RSI不创新高）
            if current_price >= price_window.max() * 0.99:  # 当前价格接近或创新高
                max_rsi_in_period = rsi_window.max()
                if current_rsi < max_rsi_in_period * 0.95:  # RSI没有创新高
                    return "顶背离"
            
            # 检测底背离（价格新低，RSI不创新低）
            elif current_price <= price_window.min() * 1.01:  # 当前价格接近或创新低
                min_rsi_in_period = rsi_window.min()
                if current_rsi > min_rsi_in_period * 1.05:  # RSI没有创新低
                    return "底背离"
            
            return ""
            
        except Exception as e:
            logger.error(f"背离检测失败: {str(e)}")
            return ""
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """获取策略详细信息"""
        base_info = self.get_strategy_status()
        
        # 添加策略特有信息
        strategy_info = {
            **base_info,
            'strategy_type': 'RSI反转策略',
            'description': '基于相对强弱指标的反转交易策略',
            'key_parameters': {
                'rsi_period': self.params['rsi_period'],
                'overbought_level': self.params['overbought_level'],
                'oversold_level': self.params['oversold_level'],
                'extreme_levels': [self.params['extreme_oversold'], self.params['extreme_overbought']],
                'divergence_detection': self.params.get('divergence_detection', True),
                'signal_confirmation': self.params['signal_confirmation']
            }
        }
        
        return strategy_info
    
    def get_current_rsi_status(self, symbol: str) -> Dict[str, Any]:
        """获取当前RSI状态
        
        Args:
            symbol: 交易品种
            
        Returns:
            RSI状态信息
        """
        if symbol not in self.indicators_cache:
            return {}
        
        indicators = self.indicators_cache[symbol]
        if 'rsi' not in indicators:
            return {}
        
        rsi = indicators['rsi']
        current_rsi = rsi.iloc[-1] if len(rsi) > 0 else None
        
        if current_rsi is None or pd.isna(current_rsi):
            return {}
        
        # 判断RSI状态
        status = "中性"
        if current_rsi >= self.params['extreme_overbought']:
            status = "极度超买"
        elif current_rsi >= self.params['overbought_level']:
            status = "超买"
        elif current_rsi <= self.params['extreme_oversold']:
            status = "极度超卖"
        elif current_rsi <= self.params['oversold_level']:
            status = "超卖"
        
        return {
            'symbol': symbol,
            'current_rsi': current_rsi,
            'status': status,
            'overbought_level': self.params['overbought_level'],
            'oversold_level': self.params['oversold_level'],
            'extreme_levels': [self.params['extreme_oversold'], self.params['extreme_overbought']]
        }