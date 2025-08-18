"""
策略模块集成测试
测试策略计算、信号生成和管理的完整流程
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

from strategies.strategy_manager import StrategyManager
from strategies.ma_crossover import MACrossoverStrategy
from strategies.rsi_strategy import RSIStrategy
from strategies.base_strategy import BaseStrategy
from backtest.engine import BacktestEngine


class TestStrategyIntegration:
    """策略集成测试类"""
    
    @pytest.fixture(autouse=True)
    def setup(self, mock_stock_data):
        """测试设置"""
        self.mock_data = mock_stock_data
        self.strategy_manager = StrategyManager()
        
        # 准备测试数据
        self.test_data = mock_stock_data[mock_stock_data['ts_code'] == '000001.SZ'].head(100)
        self.test_data = self.test_data.sort_values('trade_date').reset_index(drop=True)
    
    @pytest.mark.integration
    def test_strategy_registration_and_management(self):
        """测试策略注册和管理"""
        # 创建策略实例
        ma_strategy = MACrossoverStrategy()
        rsi_strategy = RSIStrategy()
        
        # 注册策略
        self.strategy_manager.register_strategy(ma_strategy)
        self.strategy_manager.register_strategy(rsi_strategy)
        
        # 验证注册结果
        assert len(self.strategy_manager.strategies) == 2
        assert 'ma_crossover' in self.strategy_manager.strategies
        assert 'rsi_strategy' in self.strategy_manager.strategies
        
        # 测试策略列表获取
        strategy_list = self.strategy_manager.list_strategies()
        assert len(strategy_list) == 2
        
        # 测试策略获取
        retrieved_ma = self.strategy_manager.get_strategy('ma_crossover')
        assert retrieved_ma is not None
        assert isinstance(retrieved_ma, MACrossoverStrategy)
        
        # 测试策略移除
        self.strategy_manager.remove_strategy('rsi_strategy')
        assert len(self.strategy_manager.strategies) == 1
        assert 'rsi_strategy' not in self.strategy_manager.strategies
    
    @pytest.mark.integration
    def test_ma_crossover_strategy_signals(self):
        """测试移动平均交叉策略信号生成"""
        strategy = MACrossoverStrategy()
        strategy.short_window = 5
        strategy.long_window = 20
        
        # 测试不同数据量的信号生成
        
        # 1. 数据不足的情况
        small_data = self.test_data.head(10)
        signal = strategy.calculate_signals(small_data)
        assert signal['action'] == 'hold'  # 数据不足应该持有
        
        # 2. 正常数据量
        normal_data = self.test_data.head(50)
        signal = strategy.calculate_signals(normal_data)
        assert 'action' in signal
        assert signal['action'] in ['buy', 'sell', 'hold']
        assert 'confidence' in signal
        assert 0 <= signal['confidence'] <= 1
        
        # 3. 验证技术指标计算
        indicators = strategy.calculate_indicators(normal_data)
        assert 'ma_short' in indicators
        assert 'ma_long' in indicators
        assert len(indicators['ma_short']) == len(normal_data)
        assert len(indicators['ma_long']) == len(normal_data)
        
        # 验证移动平均线的数学正确性
        ma_short_manual = normal_data['close'].rolling(window=5).mean()
        np.testing.assert_array_almost_equal(
            indicators['ma_short'].dropna(), 
            ma_short_manual.dropna(), 
            decimal=4
        )
    
    @pytest.mark.integration
    def test_rsi_strategy_signals(self):
        """测试RSI策略信号生成"""
        strategy = RSIStrategy()
        strategy.rsi_period = 14
        strategy.overbought = 70
        strategy.oversold = 30
        
        # 测试RSI计算和信号生成
        signal = strategy.calculate_signals(self.test_data)
        assert 'action' in signal
        assert signal['action'] in ['buy', 'sell', 'hold']
        
        # 验证RSI指标计算
        indicators = strategy.calculate_indicators(self.test_data)
        assert 'rsi' in indicators
        assert len(indicators['rsi']) == len(self.test_data)
        
        # 验证RSI值范围
        rsi_values = indicators['rsi'].dropna()
        assert all(0 <= rsi <= 100 for rsi in rsi_values)
        
        # 测试极端RSI值的信号
        # 创建模拟超买数据
        overbought_data = self.test_data.copy()
        overbought_data['close'] = overbought_data['close'] * np.linspace(1, 2, len(overbought_data))
        
        overbought_signal = strategy.calculate_signals(overbought_data)
        # 在强烈上涨趋势中，RSI可能显示超买，策略应该给出卖出信号
        
        # 创建模拟超卖数据
        oversold_data = self.test_data.copy()
        oversold_data['close'] = oversold_data['close'] * np.linspace(1, 0.5, len(oversold_data))
        
        oversold_signal = strategy.calculate_signals(oversold_data)
        # 在强烈下跌趋势中，RSI可能显示超卖，策略应该给出买入信号
    
    @pytest.mark.integration
    def test_strategy_parameter_optimization(self):
        """测试策略参数优化"""
        strategy = MACrossoverStrategy()
        
        # 定义参数空间
        param_space = {
            'short_window': [5, 10, 15],
            'long_window': [20, 30, 40]
        }
        
        best_params = None
        best_performance = -float('inf')
        
        # 网格搜索优化
        for short_window in param_space['short_window']:
            for long_window in param_space['long_window']:
                if short_window >= long_window:
                    continue
                
                # 更新策略参数
                strategy.update_parameters(
                    short_window=short_window,
                    long_window=long_window
                )
                
                # 简单回测
                signals = []
                for i in range(long_window, len(self.test_data)):
                    window_data = self.test_data.iloc[i-long_window:i+1]
                    signal = strategy.calculate_signals(window_data)
                    signals.append(signal)
                
                # 简单性能评估（买入持有策略的超额收益）
                if signals:
                    buy_signals = sum(1 for s in signals if s['action'] == 'buy')
                    performance = buy_signals / len(signals)  # 简化的性能指标
                    
                    if performance > best_performance:
                        best_performance = performance
                        best_params = {'short_window': short_window, 'long_window': long_window}
        
        assert best_params is not None
        print(f"最优参数: {best_params}, 性能: {best_performance}")
    
    @pytest.mark.integration
    def test_multi_strategy_signal_aggregation(self):
        """测试多策略信号聚合"""
        # 创建多个策略
        ma_strategy = MACrossoverStrategy()
        rsi_strategy = RSIStrategy()
        
        # 注册策略
        self.strategy_manager.register_strategy(ma_strategy)
        self.strategy_manager.register_strategy(rsi_strategy)
        
        # 生成各策略信号
        signals = {}
        for strategy_name, strategy in self.strategy_manager.strategies.items():
            signal = strategy.calculate_signals(self.test_data)
            signals[strategy_name] = signal
        
        # 测试简单聚合
        aggregated = self.strategy_manager.aggregate_signals(signals)
        assert 'action' in aggregated
        assert 'confidence' in aggregated
        assert aggregated['action'] in ['buy', 'sell', 'hold']
        
        # 测试加权聚合
        weights = {'ma_crossover': 0.6, 'rsi_strategy': 0.4}
        weighted_aggregated = self.strategy_manager.aggregate_signals(signals, weights)
        assert 'action' in weighted_aggregated
        assert 'confidence' in weighted_aggregated
        
        # 测试一致性检查
        consistency = self.strategy_manager.check_signal_consistency(signals)
        assert 'agreement_rate' in consistency
        assert 0 <= consistency['agreement_rate'] <= 1
    
    @pytest.mark.integration
    def test_strategy_performance_tracking(self):
        """测试策略性能跟踪"""
        strategy = MACrossoverStrategy()
        
        # 模拟历史信号和实际收益
        historical_signals = []
        actual_returns = []
        
        for i in range(20, len(self.test_data)):
            window_data = self.test_data.iloc[i-20:i+1]
            signal = strategy.calculate_signals(window_data)
            historical_signals.append(signal)
            
            # 模拟实际收益（简化）
            if i < len(self.test_data) - 1:
                current_price = self.test_data.iloc[i]['close']
                next_price = self.test_data.iloc[i+1]['close']
                actual_return = (next_price - current_price) / current_price
                actual_returns.append(actual_return)
        
        # 计算策略性能指标
        performance = self.strategy_manager.calculate_strategy_performance(
            strategy.name, historical_signals, actual_returns
        )
        
        assert 'total_signals' in performance
        assert 'buy_signals' in performance
        assert 'sell_signals' in performance
        assert 'accuracy' in performance
        assert 'avg_return' in performance
    
    @pytest.mark.integration
    def test_strategy_with_backtest_integration(self):
        """测试策略与回测引擎集成"""
        strategy = MACrossoverStrategy()
        
        # 创建回测引擎
        backtest_engine = BacktestEngine(
            initial_capital=1000000,
            commission=0.0003,
            stamp_tax=0.001
        )
        
        # 执行回测
        results = backtest_engine.run_backtest(
            strategy=strategy,
            data=self.test_data,
            start_date=self.test_data.iloc[0]['trade_date'],
            end_date=self.test_data.iloc[-1]['trade_date']
        )
        
        # 验证回测结果
        assert results is not None
        assert 'portfolio_value' in results
        assert 'trades' in results
        assert 'performance_metrics' in results
        
        # 验证交易记录
        trades = results['trades']
        if len(trades) > 0:
            for trade in trades:
                assert 'timestamp' in trade
                assert 'action' in trade
                assert 'price' in trade
                assert 'quantity' in trade
        
        # 验证性能指标
        metrics = results['performance_metrics']
        assert 'total_return' in metrics
        assert 'annualized_return' in metrics
        assert 'volatility' in metrics
        assert 'sharpe_ratio' in metrics
        assert 'max_drawdown' in metrics
    
    @pytest.mark.integration
    def test_custom_strategy_creation(self):
        """测试自定义策略创建"""
        
        class CustomTestStrategy(BaseStrategy):
            def __init__(self):
                super().__init__("custom_test")
                self.threshold = 0.02
            
            def calculate_indicators(self, data):
                if len(data) < 2:
                    return {}
                
                # 简单的价格变化率指标
                price_change = data['close'].pct_change()
                return {'price_change': price_change}
            
            def calculate_signals(self, data):
                indicators = self.calculate_indicators(data)
                
                if not indicators or len(data) < 2:
                    return {'action': 'hold', 'confidence': 0.5}
                
                latest_change = indicators['price_change'].iloc[-1]
                
                if latest_change > self.threshold:
                    return {'action': 'buy', 'confidence': 0.8}
                elif latest_change < -self.threshold:
                    return {'action': 'sell', 'confidence': 0.8}
                else:
                    return {'action': 'hold', 'confidence': 0.5}
            
            def update_parameters(self, **kwargs):
                if 'threshold' in kwargs:
                    self.threshold = kwargs['threshold']
        
        # 测试自定义策略
        custom_strategy = CustomTestStrategy()
        
        # 注册到策略管理器
        self.strategy_manager.register_strategy(custom_strategy)
        assert 'custom_test' in self.strategy_manager.strategies
        
        # 测试信号生成
        signal = custom_strategy.calculate_signals(self.test_data)
        assert 'action' in signal
        assert signal['action'] in ['buy', 'sell', 'hold']
        
        # 测试参数更新
        custom_strategy.update_parameters(threshold=0.05)
        assert custom_strategy.threshold == 0.05
    
    @pytest.mark.integration
    def test_strategy_state_persistence(self, temp_dir):
        """测试策略状态持久化"""
        import pickle
        
        # 创建并配置策略
        strategy = MACrossoverStrategy()
        strategy.short_window = 8
        strategy.long_window = 25
        
        # 生成一些历史信号
        for i in range(30, len(self.test_data), 10):
            window_data = self.test_data.iloc[i-30:i+1]
            signal = strategy.calculate_signals(window_data)
            # 模拟策略状态更新
        
        # 保存策略状态
        strategy_file = os.path.join(temp_dir, "strategy_state.pkl")
        strategy.save_state(strategy_file)
        assert os.path.exists(strategy_file)
        
        # 创建新的策略实例并加载状态
        new_strategy = MACrossoverStrategy()
        new_strategy.load_state(strategy_file)
        
        # 验证状态恢复
        assert new_strategy.short_window == 8
        assert new_strategy.long_window == 25
        
        # 验证行为一致性
        test_signal_original = strategy.calculate_signals(self.test_data)
        test_signal_restored = new_strategy.calculate_signals(self.test_data)
        
        assert test_signal_original['action'] == test_signal_restored['action']
        assert abs(test_signal_original['confidence'] - test_signal_restored['confidence']) < 0.01
    
    @pytest.mark.integration
    @pytest.mark.performance
    def test_strategy_computation_performance(self, performance_monitor):
        """测试策略计算性能"""
        performance_monitor.start()
        
        # 创建多个策略
        strategies = [
            MACrossoverStrategy(),
            RSIStrategy(),
        ]
        
        # 大量信号计算
        all_signals = []
        for strategy in strategies:
            for i in range(50, len(self.test_data), 5):
                window_data = self.test_data.iloc[i-50:i+1]
                signal = strategy.calculate_signals(window_data)
                all_signals.append(signal)
        
        performance_stats = performance_monitor.stop()
        
        # 性能验证
        assert performance_stats['execution_time'] < 10  # 10秒内完成
        assert len(all_signals) > 0
        
        print(f"策略计算性能: {performance_stats}")
        print(f"总信号数: {len(all_signals)}")
    
    @pytest.mark.integration
    def test_strategy_error_handling(self):
        """测试策略错误处理"""
        strategy = MACrossoverStrategy()
        
        # 测试空数据
        empty_data = pd.DataFrame()
        signal = strategy.calculate_signals(empty_data)
        assert signal['action'] == 'hold'
        
        # 测试异常数据
        invalid_data = self.test_data.copy()
        invalid_data.loc[0, 'close'] = None  # 添加空值
        
        signal = strategy.calculate_signals(invalid_data)
        assert 'action' in signal  # 应该能处理异常数据
        
        # 测试数据列缺失
        incomplete_data = self.test_data[['ts_code', 'trade_date']].copy()
        
        with pytest.raises(KeyError):
            strategy.calculate_signals(incomplete_data)
        
        # 测试极端参数值
        strategy.update_parameters(short_window=0)  # 无效参数
        signal = strategy.calculate_signals(self.test_data)
        assert signal['action'] == 'hold'  # 应该回退到安全状态


if __name__ == "__main__":
    # 运行策略集成测试
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short",
        "-m", "integration"
    ])