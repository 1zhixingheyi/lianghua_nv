"""
策略模块单元测试
测试各个策略组件的独立功能
"""

import pytest
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.strategies.base_strategy import BaseStrategy
from src.strategies.ma_crossover import MACrossoverStrategy
from src.strategies.rsi_strategy import RSIStrategy
from src.strategies.strategy_manager import StrategyManager


class TestBaseStrategyUnit:
    """基础策略单元测试"""
    
    def test_base_strategy_initialization(self):
        """测试基础策略初始化"""
        strategy = BaseStrategy("test_strategy")
        assert strategy.name == "test_strategy"
        assert strategy.created_at is not None
        assert isinstance(strategy.parameters, dict)
        assert strategy.is_active is True
    
    def test_base_strategy_abstract_methods(self):
        """测试基础策略抽象方法"""
        strategy = BaseStrategy("test_strategy")
        
        # 抽象方法应该抛出NotImplementedError
        with pytest.raises(NotImplementedError):
            strategy.calculate_indicators(pd.DataFrame())
        
        with pytest.raises(NotImplementedError):
            strategy.calculate_signals(pd.DataFrame())
    
    def test_strategy_state_management(self):
        """测试策略状态管理"""
        strategy = BaseStrategy("test_strategy")
        
        # 测试激活/停用
        strategy.deactivate()
        assert strategy.is_active is False
        
        strategy.activate()
        assert strategy.is_active is True
        
        # 测试参数更新
        strategy.update_parameters(param1="value1", param2=42)
        assert strategy.parameters["param1"] == "value1"
        assert strategy.parameters["param2"] == 42
    
    def test_strategy_validation(self):
        """测试策略验证"""
        strategy = BaseStrategy("test_strategy")
        
        # 测试名称验证
        with pytest.raises(ValueError):
            BaseStrategy("")  # 空名称
        
        with pytest.raises(ValueError):
            BaseStrategy(None)  # None名称


class TestMACrossoverStrategyUnit:
    """移动平均交叉策略单元测试"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """测试设置"""
        self.strategy = MACrossoverStrategy()
        self.strategy.short_window = 5
        self.strategy.long_window = 20
        
        # 创建测试数据
        dates = pd.date_range(start='2023-12-01', periods=50, freq='D')
        prices = 10 + np.cumsum(np.random.normal(0, 0.1, 50))  # 随机游走价格
        
        self.test_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 50,
            'trade_date': [d.strftime('%Y%m%d') for d in dates],
            'open': prices + np.random.normal(0, 0.05, 50),
            'high': prices + np.abs(np.random.normal(0, 0.1, 50)),
            'low': prices - np.abs(np.random.normal(0, 0.1, 50)),
            'close': prices,
            'vol': np.random.randint(1000000, 5000000, 50),
            'amount': prices * np.random.randint(1000000, 5000000, 50)
        })
    
    def test_strategy_initialization(self):
        """测试策略初始化"""
        strategy = MACrossoverStrategy()
        assert strategy.name == "ma_crossover"
        assert strategy.short_window == 5  # 默认值
        assert strategy.long_window == 20  # 默认值
    
    def test_parameter_validation(self):
        """测试参数验证"""
        strategy = MACrossoverStrategy()
        
        # 测试无效窗口大小
        with pytest.raises(ValueError):
            strategy.update_parameters(short_window=0)
        
        with pytest.raises(ValueError):
            strategy.update_parameters(long_window=-1)
        
        with pytest.raises(ValueError):
            strategy.update_parameters(short_window=20, long_window=10)  # 短窗口大于长窗口
        
        # 测试有效参数
        strategy.update_parameters(short_window=5, long_window=20)
        assert strategy.short_window == 5
        assert strategy.long_window == 20
    
    def test_moving_average_calculation(self):
        """测试移动平均计算"""
        indicators = self.strategy.calculate_indicators(self.test_data)
        
        assert 'ma_short' in indicators
        assert 'ma_long' in indicators
        assert len(indicators['ma_short']) == len(self.test_data)
        assert len(indicators['ma_long']) == len(self.test_data)
        
        # 验证移动平均计算正确性
        expected_ma_short = self.test_data['close'].rolling(window=5).mean()
        np.testing.assert_array_almost_equal(
            indicators['ma_short'].dropna(), 
            expected_ma_short.dropna(), 
            decimal=6
        )
        
        expected_ma_long = self.test_data['close'].rolling(window=20).mean()
        np.testing.assert_array_almost_equal(
            indicators['ma_long'].dropna(), 
            expected_ma_long.dropna(), 
            decimal=6
        )
    
    def test_signal_generation_insufficient_data(self):
        """测试数据不足时的信号生成"""
        # 数据不足的情况
        small_data = self.test_data.head(10)
        signal = self.strategy.calculate_signals(small_data)
        
        assert signal['action'] == 'hold'
        assert signal['confidence'] == 0.5
        
        # 空数据
        empty_data = pd.DataFrame()
        signal = self.strategy.calculate_signals(empty_data)
        
        assert signal['action'] == 'hold'
        assert signal['confidence'] == 0
    
    def test_signal_generation_normal_data(self):
        """测试正常数据的信号生成"""
        signal = self.strategy.calculate_signals(self.test_data)
        
        assert 'action' in signal
        assert 'confidence' in signal
        assert signal['action'] in ['buy', 'sell', 'hold']
        assert 0 <= signal['confidence'] <= 1
        
        # 验证信号逻辑
        indicators = self.strategy.calculate_indicators(self.test_data)
        last_short_ma = indicators['ma_short'].iloc[-1]
        last_long_ma = indicators['ma_long'].iloc[-1]
        prev_short_ma = indicators['ma_short'].iloc[-2]
        prev_long_ma = indicators['ma_long'].iloc[-2]
        
        # 金叉：短期均线上穿长期均线
        if (last_short_ma > last_long_ma and prev_short_ma <= prev_long_ma):
            assert signal['action'] == 'buy'
        # 死叉：短期均线下穿长期均线
        elif (last_short_ma < last_long_ma and prev_short_ma >= prev_long_ma):
            assert signal['action'] == 'sell'
        else:
            assert signal['action'] == 'hold'
    
    def test_confidence_calculation(self):
        """测试置信度计算"""
        # 创建明显的趋势数据
        trend_up_data = self.test_data.copy()
        trend_up_data['close'] = np.linspace(10, 15, len(trend_up_data))
        
        signal_up = self.strategy.calculate_signals(trend_up_data)
        
        # 明显上升趋势应该有较高置信度
        if signal_up['action'] == 'buy':
            assert signal_up['confidence'] > 0.6
        
        # 创建明显的下降趋势数据
        trend_down_data = self.test_data.copy()
        trend_down_data['close'] = np.linspace(15, 10, len(trend_down_data))
        
        signal_down = self.strategy.calculate_signals(trend_down_data)
        
        # 明显下降趋势应该有较高置信度
        if signal_down['action'] == 'sell':
            assert signal_down['confidence'] > 0.6
    
    def test_crossover_detection(self):
        """测试交叉点检测"""
        # 构造特定的交叉数据
        crossover_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 30,
            'trade_date': [f'202312{i:02d}' for i in range(1, 31)],
            'close': [10] * 25 + [10.1, 10.2, 10.3, 10.4, 10.5],  # 最后5天上涨
            'open': [10] * 30,
            'high': [10.1] * 30,
            'low': [9.9] * 30,
            'vol': [1000000] * 30,
            'amount': [10000000] * 30
        })
        
        signal = self.strategy.calculate_signals(crossover_data)
        
        # 应该检测到金叉信号
        assert signal['action'] == 'buy'
        assert signal['confidence'] > 0.5


class TestRSIStrategyUnit:
    """RSI策略单元测试"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """测试设置"""
        self.strategy = RSIStrategy()
        self.strategy.rsi_period = 14
        self.strategy.overbought = 70
        self.strategy.oversold = 30
        
        # 创建测试数据
        np.random.seed(42)  # 固定随机种子
        dates = pd.date_range(start='2023-12-01', periods=50, freq='D')
        prices = 10 + np.cumsum(np.random.normal(0, 0.1, 50))
        
        self.test_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 50,
            'trade_date': [d.strftime('%Y%m%d') for d in dates],
            'close': prices,
            'open': prices + np.random.normal(0, 0.05, 50),
            'high': prices + np.abs(np.random.normal(0, 0.1, 50)),
            'low': prices - np.abs(np.random.normal(0, 0.1, 50)),
            'vol': np.random.randint(1000000, 5000000, 50),
            'amount': prices * np.random.randint(1000000, 5000000, 50)
        })
    
    def test_strategy_initialization(self):
        """测试RSI策略初始化"""
        strategy = RSIStrategy()
        assert strategy.name == "rsi_strategy"
        assert strategy.rsi_period == 14
        assert strategy.overbought == 70
        assert strategy.oversold == 30
    
    def test_rsi_calculation(self):
        """测试RSI指标计算"""
        indicators = self.strategy.calculate_indicators(self.test_data)
        
        assert 'rsi' in indicators
        assert len(indicators['rsi']) == len(self.test_data)
        
        # 验证RSI值范围
        rsi_values = indicators['rsi'].dropna()
        assert all(0 <= rsi <= 100 for rsi in rsi_values)
        
        # 验证RSI计算的数学正确性（简化验证）
        close_prices = self.test_data['close']
        price_changes = close_prices.diff()
        gains = price_changes.where(price_changes > 0, 0)
        losses = -price_changes.where(price_changes < 0, 0)
        
        avg_gains = gains.rolling(window=14).mean()
        avg_losses = losses.rolling(window=14).mean()
        
        rs = avg_gains / avg_losses
        expected_rsi = 100 - (100 / (1 + rs))
        
        # 验证最后几个有效值
        actual_rsi = indicators['rsi'].dropna()
        expected_rsi_clean = expected_rsi.dropna()
        
        if len(actual_rsi) > 0 and len(expected_rsi_clean) > 0:
            np.testing.assert_array_almost_equal(
                actual_rsi.iloc[-5:], 
                expected_rsi_clean.iloc[-5:], 
                decimal=2
            )
    
    def test_overbought_signal(self):
        """测试超买信号"""
        # 创建超买情况的数据
        overbought_data = self.test_data.copy()
        # 创建强烈上涨趋势导致RSI超买
        overbought_data['close'] = np.linspace(10, 20, len(overbought_data))
        
        signal = self.strategy.calculate_signals(overbought_data)
        indicators = self.strategy.calculate_indicators(overbought_data)
        
        last_rsi = indicators['rsi'].iloc[-1]
        if last_rsi > self.strategy.overbought:
            assert signal['action'] == 'sell'
            assert signal['confidence'] > 0.5
    
    def test_oversold_signal(self):
        """测试超卖信号"""
        # 创建超卖情况的数据
        oversold_data = self.test_data.copy()
        # 创建强烈下跌趋势导致RSI超卖
        oversold_data['close'] = np.linspace(20, 10, len(oversold_data))
        
        signal = self.strategy.calculate_signals(oversold_data)
        indicators = self.strategy.calculate_indicators(oversold_data)
        
        last_rsi = indicators['rsi'].iloc[-1]
        if last_rsi < self.strategy.oversold:
            assert signal['action'] == 'buy'
            assert signal['confidence'] > 0.5
    
    def test_normal_range_signal(self):
        """测试正常范围信号"""
        # 创建RSI在正常范围的数据
        normal_data = self.test_data.copy()
        # 保持价格相对稳定
        normal_data['close'] = 10 + np.sin(np.linspace(0, 4*np.pi, len(normal_data))) * 0.5
        
        signal = self.strategy.calculate_signals(normal_data)
        
        # 正常范围内应该持有
        assert signal['action'] == 'hold'
        assert signal['confidence'] <= 0.6  # 置信度相对较低
    
    def test_parameter_update(self):
        """测试参数更新"""
        self.strategy.update_parameters(
            rsi_period=21,
            overbought=75,
            oversold=25
        )
        
        assert self.strategy.rsi_period == 21
        assert self.strategy.overbought == 75
        assert self.strategy.oversold == 25
        
        # 测试无效参数
        with pytest.raises(ValueError):
            self.strategy.update_parameters(rsi_period=0)
        
        with pytest.raises(ValueError):
            self.strategy.update_parameters(overbought=50, oversold=60)  # 超买线低于超卖线
    
    def test_insufficient_data_handling(self):
        """测试数据不足处理"""
        # RSI需要至少period+1个数据点
        small_data = self.test_data.head(10)  # 少于14个数据点
        
        signal = self.strategy.calculate_signals(small_data)
        assert signal['action'] == 'hold'
        assert signal['confidence'] == 0.5


class TestStrategyManagerUnit:
    """策略管理器单元测试"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """测试设置"""
        self.manager = StrategyManager()
        self.ma_strategy = MACrossoverStrategy()
        self.rsi_strategy = RSIStrategy()
    
    def test_manager_initialization(self):
        """测试管理器初始化"""
        manager = StrategyManager()
        assert isinstance(manager.strategies, dict)
        assert len(manager.strategies) == 0
    
    def test_strategy_registration(self):
        """测试策略注册"""
        # 注册策略
        self.manager.register_strategy(self.ma_strategy)
        assert len(self.manager.strategies) == 1
        assert "ma_crossover" in self.manager.strategies
        
        # 注册另一个策略
        self.manager.register_strategy(self.rsi_strategy)
        assert len(self.manager.strategies) == 2
        assert "rsi_strategy" in self.manager.strategies
        
        # 重复注册应该覆盖
        new_ma_strategy = MACrossoverStrategy()
        new_ma_strategy.short_window = 10
        self.manager.register_strategy(new_ma_strategy)
        assert len(self.manager.strategies) == 2
        assert self.manager.strategies["ma_crossover"].short_window == 10
    
    def test_strategy_retrieval(self):
        """测试策略获取"""
        self.manager.register_strategy(self.ma_strategy)
        
        # 获取存在的策略
        retrieved = self.manager.get_strategy("ma_crossover")
        assert retrieved is not None
        assert retrieved.name == "ma_crossover"
        
        # 获取不存在的策略
        not_found = self.manager.get_strategy("nonexistent")
        assert not_found is None
    
    def test_strategy_removal(self):
        """测试策略移除"""
        self.manager.register_strategy(self.ma_strategy)
        self.manager.register_strategy(self.rsi_strategy)
        assert len(self.manager.strategies) == 2
        
        # 移除策略
        removed = self.manager.remove_strategy("ma_crossover")
        assert removed is True
        assert len(self.manager.strategies) == 1
        assert "ma_crossover" not in self.manager.strategies
        
        # 移除不存在的策略
        not_removed = self.manager.remove_strategy("nonexistent")
        assert not_removed is False
    
    def test_strategy_listing(self):
        """测试策略列表"""
        # 空列表
        empty_list = self.manager.list_strategies()
        assert len(empty_list) == 0
        
        # 添加策略后
        self.manager.register_strategy(self.ma_strategy)
        self.manager.register_strategy(self.rsi_strategy)
        
        strategy_list = self.manager.list_strategies()
        assert len(strategy_list) == 2
        assert "ma_crossover" in strategy_list
        assert "rsi_strategy" in strategy_list
    
    def test_signal_aggregation_simple(self):
        """测试简单信号聚合"""
        signals = {
            "strategy1": {"action": "buy", "confidence": 0.8},
            "strategy2": {"action": "buy", "confidence": 0.6},
            "strategy3": {"action": "hold", "confidence": 0.5}
        }
        
        aggregated = self.manager.aggregate_signals(signals)
        
        assert aggregated['action'] == 'buy'  # 多数买入
        assert 0.5 < aggregated['confidence'] < 1.0
    
    def test_signal_aggregation_weighted(self):
        """测试加权信号聚合"""
        signals = {
            "strategy1": {"action": "buy", "confidence": 0.7},
            "strategy2": {"action": "sell", "confidence": 0.9}
        }
        
        weights = {
            "strategy1": 0.3,
            "strategy2": 0.7
        }
        
        aggregated = self.manager.aggregate_signals(signals, weights)
        
        # 高权重的卖出信号应该占主导
        assert aggregated['action'] == 'sell'
        assert aggregated['confidence'] > 0.6
    
    def test_signal_aggregation_conflicting(self):
        """测试冲突信号聚合"""
        signals = {
            "strategy1": {"action": "buy", "confidence": 0.8},
            "strategy2": {"action": "sell", "confidence": 0.8}
        }
        
        aggregated = self.manager.aggregate_signals(signals)
        
        # 冲突信号应该导致持有
        assert aggregated['action'] == 'hold'
        assert aggregated['confidence'] <= 0.6
    
    def test_signal_consistency_check(self):
        """测试信号一致性检查"""
        # 一致信号
        consistent_signals = {
            "strategy1": {"action": "buy", "confidence": 0.8},
            "strategy2": {"action": "buy", "confidence": 0.6},
            "strategy3": {"action": "buy", "confidence": 0.7}
        }
        
        consistency = self.manager.check_signal_consistency(consistent_signals)
        assert consistency['agreement_rate'] == 1.0
        assert consistency['consensus_action'] == 'buy'
        
        # 不一致信号
        inconsistent_signals = {
            "strategy1": {"action": "buy", "confidence": 0.8},
            "strategy2": {"action": "sell", "confidence": 0.6},
            "strategy3": {"action": "hold", "confidence": 0.5}
        }
        
        consistency = self.manager.check_signal_consistency(inconsistent_signals)
        assert consistency['agreement_rate'] < 1.0
        assert 'consensus_action' in consistency
    
    def test_strategy_performance_calculation(self):
        """测试策略性能计算"""
        # 模拟历史信号和收益
        historical_signals = [
            {"action": "buy", "confidence": 0.8},
            {"action": "hold", "confidence": 0.5},
            {"action": "sell", "confidence": 0.7},
            {"action": "buy", "confidence": 0.6}
        ]
        
        actual_returns = [0.02, 0.01, -0.015, 0.03]  # 对应的实际收益
        
        performance = self.manager.calculate_strategy_performance(
            "test_strategy", historical_signals, actual_returns
        )
        
        assert 'total_signals' in performance
        assert 'buy_signals' in performance
        assert 'sell_signals' in performance
        assert 'accuracy' in performance
        assert 'avg_return' in performance
        
        assert performance['total_signals'] == 4
        assert performance['buy_signals'] == 2
        assert performance['sell_signals'] == 1
    
    def test_empty_signals_handling(self):
        """测试空信号处理"""
        empty_signals = {}
        aggregated = self.manager.aggregate_signals(empty_signals)
        
        assert aggregated['action'] == 'hold'
        assert aggregated['confidence'] == 0.5
    
    def test_invalid_signal_handling(self):
        """测试无效信号处理"""
        invalid_signals = {
            "strategy1": {"action": "invalid_action", "confidence": 0.8},
            "strategy2": {"action": "buy", "confidence": 1.5},  # 无效置信度
            "strategy3": {"action": "sell", "confidence": 0.7}
        }
        
        # 应该过滤掉无效信号
        aggregated = self.manager.aggregate_signals(invalid_signals)
        assert aggregated is not None
        assert aggregated['action'] in ['buy', 'sell', 'hold']


if __name__ == "__main__":
    # 运行策略单元测试
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short",
        "-m", "unit"
    ])