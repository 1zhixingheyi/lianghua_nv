"""
完整工作流集成测试
测试从数据采集到交易执行的完整流程
"""

import pytest
import os
import sys
import time
import asyncio
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.data.tushare_client import TushareClient
from src.data.database import DatabaseManager
from src.strategies.strategy_manager import StrategyManager
from src.strategies.ma_crossover import MACrossoverStrategy
from src.strategies.rsi_strategy import RSIStrategy
from src.backtest.engine import BacktestEngine
from src.risk.risk_engine import RiskEngine
from src.trading.trade_executor import TradeExecutor
from src.monitor.dashboard import Dashboard
from src.config.settings import Config


class TestFullWorkflow:
    """完整工作流测试类"""
    
    @pytest.fixture(autouse=True)
    def setup(self, test_config, test_database, mock_stock_data, temp_dir):
        """测试设置"""
        self.config = test_config
        self.db = test_database
        self.mock_data = mock_stock_data
        self.temp_dir = temp_dir
        
        # 初始化组件
        self.db_manager = DatabaseManager(":memory:")
        self.strategy_manager = StrategyManager()
        self.risk_engine = RiskEngine(test_config["risk"])
        
        # 创建测试配置文件
        self.config_file = os.path.join(temp_dir, "test_config.json")
        import json
        with open(self.config_file, 'w') as f:
            json.dump(test_config, f)
    
    @pytest.mark.integration
    def test_complete_data_pipeline(self, mock_tushare_client):
        """测试完整数据流水线"""
        # 1. 数据采集
        with patch('data.tushare_client.TushareClient') as mock_client_class:
            mock_client_class.return_value = mock_tushare_client
            
            # 创建数据客户端
            data_client = TushareClient("test_token")
            
            # 获取股票数据
            stock_data = data_client.get_daily_data("000001.SZ", "20231201", "20231205")
            assert not stock_data.empty
            assert len(stock_data) == 5
            
            # 2. 数据存储
            self.db_manager.save_stock_data(stock_data)
            
            # 3. 数据查询验证
            saved_data = self.db_manager.get_stock_data("000001.SZ", "20231201", "20231205")
            assert not saved_data.empty
            assert len(saved_data) == 5
    
    @pytest.mark.integration
    def test_strategy_workflow(self, mock_stock_data):
        """测试策略工作流"""
        # 1. 策略注册
        ma_strategy = MACrossoverStrategy()
        rsi_strategy = RSIStrategy()
        
        self.strategy_manager.register_strategy(ma_strategy)
        self.strategy_manager.register_strategy(rsi_strategy)
        
        assert len(self.strategy_manager.strategies) == 2
        
        # 2. 策略信号生成
        test_data = mock_stock_data[mock_stock_data['ts_code'] == '000001.SZ'].head(50)
        
        signals = {}
        for strategy_name, strategy in self.strategy_manager.strategies.items():
            signal = strategy.calculate_signals(test_data)
            signals[strategy_name] = signal
            assert signal is not None
            assert 'action' in signal
            assert signal['action'] in ['buy', 'sell', 'hold']
        
        # 3. 信号聚合
        aggregated_signal = self.strategy_manager.aggregate_signals(signals)
        assert aggregated_signal is not None
        assert 'action' in aggregated_signal
        assert 'confidence' in aggregated_signal
    
    @pytest.mark.integration
    def test_backtest_workflow(self, mock_stock_data):
        """测试回测工作流"""
        # 1. 准备回测数据
        test_data = mock_stock_data[mock_stock_data['ts_code'] == '000001.SZ'].head(100)
        test_data = test_data.sort_values('trade_date')
        
        # 2. 创建策略
        strategy = MACrossoverStrategy()
        strategy.short_window = 5
        strategy.long_window = 20
        
        # 3. 执行回测
        backtest_engine = BacktestEngine(
            initial_capital=1000000,
            commission=0.0003,
            stamp_tax=0.001
        )
        
        results = backtest_engine.run_backtest(
            strategy=strategy,
            data=test_data,
            start_date="20230101",
            end_date="20231231"
        )
        
        # 4. 验证回测结果
        assert results is not None
        assert 'portfolio_value' in results
        assert 'trades' in results
        assert 'performance_metrics' in results
        
        # 验证性能指标
        metrics = results['performance_metrics']
        assert 'total_return' in metrics
        assert 'sharpe_ratio' in metrics
        assert 'max_drawdown' in metrics
    
    @pytest.mark.integration
    def test_risk_management_workflow(self, mock_portfolio):
        """测试风控管理工作流"""
        # 1. 创建交易信号
        trade_signal = {
            'stock_code': '000001.SZ',
            'action': 'buy',
            'quantity': 10000,  # 故意设置大量订单测试风控
            'price': 10.0,
            'strategy': 'test_strategy'
        }
        
        # 2. 风控检查
        risk_result = self.risk_engine.check_trade(trade_signal, mock_portfolio)
        
        # 3. 验证风控结果
        assert risk_result is not None
        assert 'approved' in risk_result
        assert 'adjusted_quantity' in risk_result
        assert 'risk_level' in risk_result
        
        # 验证数量调整（应该被风控限制）
        if not risk_result['approved']:
            assert risk_result['adjusted_quantity'] < trade_signal['quantity']
    
    @pytest.mark.integration
    def test_trading_workflow(self, mock_trader):
        """测试交易执行工作流"""
        # 1. 创建交易执行器
        trade_executor = TradeExecutor(mock_trader)
        
        # 2. 连接交易接口
        assert trade_executor.connect()
        
        # 3. 提交订单
        order = {
            'stock_code': '000001.SZ',
            'action': 'buy',
            'quantity': 1000,
            'price': 10.0
        }
        
        result = trade_executor.submit_order(order)
        assert result is not None
        assert result['status'] == 'filled'
        
        # 4. 查询账户信息
        account_info = trade_executor.get_account_info()
        assert account_info is not None
        assert 'total_asset' in account_info
        
        # 5. 查询持仓
        positions = trade_executor.get_positions()
        assert isinstance(positions, list)
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_end_to_end_workflow(self, mock_tushare_client, mock_trader):
        """端到端完整工作流测试"""
        # 模拟完整的交易流程
        
        # 1. 数据采集阶段
        with patch('data.tushare_client.TushareClient') as mock_client_class:
            mock_client_class.return_value = mock_tushare_client
            
            data_client = TushareClient("test_token")
            stock_data = data_client.get_daily_data("000001.SZ", "20231201", "20231205")
            
            # 保存数据
            self.db_manager.save_stock_data(stock_data)
        
        # 2. 策略计算阶段
        strategy = MACrossoverStrategy()
        signal = strategy.calculate_signals(stock_data)
        
        # 3. 风控检查阶段
        portfolio = {
            'cash': 1000000.0,
            'positions': {},
            'total_value': 1000000.0
        }
        
        trade_signal = {
            'stock_code': '000001.SZ',
            'action': signal['action'],
            'quantity': 1000,
            'price': stock_data.iloc[-1]['close'],
            'strategy': 'ma_crossover'
        }
        
        risk_result = self.risk_engine.check_trade(trade_signal, portfolio)
        
        # 4. 交易执行阶段（如果风控通过）
        if risk_result['approved']:
            trade_executor = TradeExecutor(mock_trader)
            trade_executor.connect()
            
            order = {
                'stock_code': trade_signal['stock_code'],
                'action': trade_signal['action'],
                'quantity': risk_result['adjusted_quantity'],
                'price': trade_signal['price']
            }
            
            execution_result = trade_executor.submit_order(order)
            assert execution_result['status'] == 'filled'
        
        # 5. 验证完整流程
        assert signal is not None
        assert risk_result is not None
    
    @pytest.mark.integration
    def test_monitoring_integration(self):
        """测试监控面板集成"""
        # 创建监控面板
        dashboard = Dashboard()
        
        # 测试数据集成
        test_data = {
            'portfolio': {
                'total_value': 1000000,
                'cash': 500000,
                'positions': [
                    {'stock_code': '000001.SZ', 'quantity': 1000, 'market_value': 10000}
                ]
            },
            'performance': {
                'daily_return': 0.02,
                'total_return': 0.15,
                'sharpe_ratio': 1.5
            },
            'trades': [
                {
                    'timestamp': datetime.now(),
                    'stock_code': '000001.SZ',
                    'action': 'buy',
                    'quantity': 1000,
                    'price': 10.0
                }
            ]
        }
        
        # 更新监控数据
        dashboard.update_data(test_data)
        
        # 验证数据更新
        assert dashboard.get_portfolio_summary() is not None
        assert dashboard.get_performance_metrics() is not None
        assert dashboard.get_recent_trades() is not None
    
    @pytest.mark.integration
    def test_error_handling_workflow(self, mock_tushare_client):
        """测试错误处理工作流"""
        # 1. 测试数据获取失败
        with patch('data.tushare_client.TushareClient') as mock_client_class:
            mock_client = Mock()
            mock_client.daily.side_effect = Exception("API请求失败")
            mock_client_class.return_value = mock_client
            
            data_client = TushareClient("test_token")
            
            with pytest.raises(Exception):
                data_client.get_daily_data("000001.SZ", "20231201", "20231205")
        
        # 2. 测试策略计算异常
        strategy = MACrossoverStrategy()
        
        # 传入空数据
        empty_data = pd.DataFrame()
        signal = strategy.calculate_signals(empty_data)
        
        # 应该返回持有信号
        assert signal['action'] == 'hold'
        
        # 3. 测试风控拒绝
        risk_engine = RiskEngine({
            'max_position': 0.001,  # 设置非常严格的限制
            'max_single_stock': 0.001
        })
        
        large_trade = {
            'stock_code': '000001.SZ',
            'action': 'buy',
            'quantity': 100000,  # 大量交易
            'price': 10.0
        }
        
        portfolio = {'cash': 1000000.0, 'positions': {}, 'total_value': 1000000.0}
        result = risk_engine.check_trade(large_trade, portfolio)
        
        # 应该被拒绝或大幅调整
        assert not result['approved'] or result['adjusted_quantity'] < large_trade['quantity']
    
    @pytest.mark.integration
    @pytest.mark.performance
    def test_performance_workflow(self, performance_monitor, mock_stock_data):
        """测试性能工作流"""
        performance_monitor.start()
        
        # 执行大量数据处理
        large_dataset = pd.concat([mock_stock_data] * 10)  # 扩大数据集
        
        # 批量策略计算
        strategy = MACrossoverStrategy()
        signals = []
        
        for stock_code in large_dataset['ts_code'].unique():
            stock_data = large_dataset[large_dataset['ts_code'] == stock_code]
            if len(stock_data) >= 20:  # 确保有足够数据
                signal = strategy.calculate_signals(stock_data)
                signals.append(signal)
        
        performance_stats = performance_monitor.stop()
        
        # 验证性能指标
        assert performance_stats['execution_time'] < 30  # 30秒内完成
        assert performance_stats['peak_memory_mb'] < 500  # 内存使用小于500MB
        
        print(f"性能统计: {performance_stats}")
    
    @pytest.mark.integration
    def test_concurrent_workflow(self, mock_stock_data):
        """测试并发工作流"""
        import concurrent.futures
        
        def process_stock(stock_code):
            """处理单个股票的策略计算"""
            stock_data = mock_stock_data[mock_stock_data['ts_code'] == stock_code]
            if len(stock_data) >= 20:
                strategy = MACrossoverStrategy()
                return strategy.calculate_signals(stock_data)
            return {'action': 'hold', 'confidence': 0}
        
        # 并发处理多个股票
        stock_codes = mock_stock_data['ts_code'].unique()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(process_stock, code): code for code in stock_codes}
            results = {}
            
            for future in concurrent.futures.as_completed(futures):
                stock_code = futures[future]
                try:
                    result = future.result()
                    results[stock_code] = result
                except Exception as e:
                    results[stock_code] = {'error': str(e)}
        
        # 验证并发处理结果
        assert len(results) == len(stock_codes)
        for stock_code, result in results.items():
            assert 'action' in result or 'error' in result
    
    @pytest.mark.integration
    def test_data_persistence_workflow(self, temp_dir):
        """测试数据持久化工作流"""
        # 创建文件数据库
        db_path = os.path.join(temp_dir, "test_workflow.db")
        db_manager = DatabaseManager(db_path)
        
        # 1. 保存股票数据
        test_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 5,
            'trade_date': ['20231201', '20231202', '20231203', '20231204', '20231205'],
            'open': [10.0, 10.1, 10.2, 10.3, 10.4],
            'high': [10.5, 10.6, 10.7, 10.8, 10.9],
            'low': [9.8, 9.9, 10.0, 10.1, 10.2],
            'close': [10.2, 10.3, 10.4, 10.5, 10.6],
            'vol': [1000000] * 5,
            'amount': [10200000] * 5
        })
        
        db_manager.save_stock_data(test_data)
        
        # 2. 保存交易记录
        trade_record = {
            'strategy_name': 'test_strategy',
            'stock_code': '000001.SZ',
            'action': 'buy',
            'quantity': 1000,
            'price': 10.0,
            'timestamp': datetime.now(),
            'status': 'filled'
        }
        
        db_manager.save_trade(trade_record)
        
        # 3. 查询验证
        saved_data = db_manager.get_stock_data('000001.SZ', '20231201', '20231205')
        assert len(saved_data) == 5
        
        saved_trades = db_manager.get_trades('test_strategy')
        assert len(saved_trades) >= 1
        
        # 4. 验证文件存在
        assert os.path.exists(db_path)
        
        # 5. 重新连接验证数据持久性
        db_manager2 = DatabaseManager(db_path)
        data_check = db_manager2.get_stock_data('000001.SZ', '20231201', '20231205')
        assert len(data_check) == 5


if __name__ == "__main__":
    # 运行集成测试
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short",
        "-m", "integration"
    ])