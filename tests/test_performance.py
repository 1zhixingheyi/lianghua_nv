"""
系统性能测试
测试系统在不同负载下的性能表现
"""

import pytest
import os
import sys
import time
import psutil
import threading
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from data.database import DatabaseManager
from strategies.ma_crossover import MACrossoverStrategy
from strategies.rsi_strategy import RSIStrategy
from backtest.engine import BacktestEngine


class PerformanceTracker:
    """性能跟踪器"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.start_memory = None
        self.peak_memory = None
        self.process = psutil.Process()
    
    def start(self):
        """开始跟踪"""
        self.start_time = time.time()
        self.start_memory = self.process.memory_info().rss
        self.peak_memory = self.start_memory
    
    def stop(self):
        """停止跟踪"""
        self.end_time = time.time()
        current_memory = self.process.memory_info().rss
        self.peak_memory = max(self.peak_memory, current_memory)
        
        return {
            'execution_time': self.end_time - self.start_time,
            'memory_usage_mb': self.peak_memory / 1024 / 1024,
            'memory_growth_mb': (self.peak_memory - self.start_memory) / 1024 / 1024,
            'cpu_percent': self.process.cpu_percent()
        }
    
    def update_memory(self):
        """更新内存峰值"""
        current_memory = self.process.memory_info().rss
        self.peak_memory = max(self.peak_memory, current_memory)


@pytest.fixture
def performance_tracker():
    """性能跟踪器夹具"""
    return PerformanceTracker()


@pytest.fixture
def large_stock_data():
    """大量股票数据夹具"""
    np.random.seed(42)  # 固定随机种子以便重现
    
    # 生成1年的交易数据，10只股票
    stock_codes = [f"{i:06d}.SZ" for i in range(1, 11)]
    dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
    trading_dates = [d for d in dates if d.weekday() < 5]  # 工作日
    
    all_data = []
    for stock_code in stock_codes:
        # 生成每只股票的价格序列
        base_price = np.random.uniform(10, 100)
        price_changes = np.random.normal(0, 0.02, len(trading_dates))
        prices = base_price * np.cumprod(1 + price_changes)
        
        for i, date in enumerate(trading_dates):
            price = prices[i]
            all_data.append({
                'ts_code': stock_code,
                'trade_date': date.strftime('%Y%m%d'),
                'open': price * np.random.uniform(0.99, 1.01),
                'high': price * np.random.uniform(1.0, 1.05),
                'low': price * np.random.uniform(0.95, 1.0),
                'close': price,
                'vol': np.random.randint(1000000, 10000000),
                'amount': price * np.random.randint(1000000, 10000000)
            })
    
    return pd.DataFrame(all_data)


class TestDataPerformance:
    """数据处理性能测试"""
    
    @pytest.mark.performance
    def test_large_data_insertion_performance(self, performance_tracker, large_stock_data, temp_dir):
        """测试大量数据插入性能"""
        db_path = os.path.join(temp_dir, "perf_test.db")
        db_manager = DatabaseManager(db_path)
        
        # 性能测试：插入大量数据
        performance_tracker.start()
        
        # 分批插入数据
        batch_size = 1000
        for i in range(0, len(large_stock_data), batch_size):
            batch = large_stock_data.iloc[i:i+batch_size]
            db_manager.save_stock_data(batch)
            performance_tracker.update_memory()
        
        stats = performance_tracker.stop()
        
        # 性能断言
        assert stats['execution_time'] < 30  # 30秒内完成
        assert stats['memory_usage_mb'] < 500  # 内存使用小于500MB
        
        print(f"大数据插入性能: {stats}")
        print(f"数据量: {len(large_stock_data)} 条记录")
        print(f"插入速度: {len(large_stock_data)/stats['execution_time']:.0f} 条/秒")
    
    @pytest.mark.performance
    def test_large_data_query_performance(self, performance_tracker, large_stock_data, temp_dir):
        """测试大量数据查询性能"""
        db_path = os.path.join(temp_dir, "perf_query_test.db")
        db_manager = DatabaseManager(db_path)
        
        # 先插入数据
        db_manager.save_stock_data(large_stock_data)
        
        # 性能测试：查询数据
        performance_tracker.start()
        
        # 执行多次查询
        for _ in range(100):
            stock_code = np.random.choice(['000001.SZ', '000002.SZ', '000003.SZ'])
            start_date = '20230601'
            end_date = '20230630'
            
            result = db_manager.get_stock_data(stock_code, start_date, end_date)
            assert not result.empty
            performance_tracker.update_memory()
        
        stats = performance_tracker.stop()
        
        # 性能断言
        assert stats['execution_time'] < 10  # 10秒内完成100次查询
        assert stats['memory_usage_mb'] < 200  # 内存使用小于200MB
        
        print(f"数据查询性能: {stats}")
        print(f"平均查询时间: {stats['execution_time']/100*1000:.2f} ms/次")
    
    @pytest.mark.performance
    def test_concurrent_data_access_performance(self, performance_tracker, large_stock_data, temp_dir):
        """测试并发数据访问性能"""
        db_path = os.path.join(temp_dir, "perf_concurrent_test.db")
        db_manager = DatabaseManager(db_path)
        
        # 插入测试数据
        db_manager.save_stock_data(large_stock_data.head(10000))  # 使用部分数据
        
        def query_worker(worker_id):
            """查询工作线程"""
            queries_per_worker = 50
            for i in range(queries_per_worker):
                stock_code = f"{(worker_id % 10) + 1:06d}.SZ"
                result = db_manager.get_stock_data(stock_code, '20230101', '20230131')
                assert not result.empty
        
        # 性能测试：并发查询
        performance_tracker.start()
        
        num_workers = 10
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(query_worker, i) for i in range(num_workers)]
            for future in futures:
                future.result()
                performance_tracker.update_memory()
        
        stats = performance_tracker.stop()
        
        # 性能断言
        total_queries = num_workers * 50
        assert stats['execution_time'] < 20  # 20秒内完成
        assert stats['memory_usage_mb'] < 300  # 内存使用小于300MB
        
        print(f"并发查询性能: {stats}")
        print(f"总查询次数: {total_queries}")
        print(f"并发查询速度: {total_queries/stats['execution_time']:.0f} 查询/秒")


class TestStrategyPerformance:
    """策略计算性能测试"""
    
    @pytest.mark.performance
    def test_ma_strategy_calculation_performance(self, performance_tracker, large_stock_data):
        """测试移动平均策略计算性能"""
        strategy = MACrossoverStrategy()
        
        # 性能测试：大量策略计算
        performance_tracker.start()
        
        signals = []
        for stock_code in large_stock_data['ts_code'].unique():
            stock_data = large_stock_data[large_stock_data['ts_code'] == stock_code]
            
            # 滑动窗口计算信号
            window_size = 50
            for i in range(window_size, len(stock_data), 10):  # 每10天计算一次
                window_data = stock_data.iloc[i-window_size:i+1]
                signal = strategy.calculate_signals(window_data)
                signals.append(signal)
                performance_tracker.update_memory()
        
        stats = performance_tracker.stop()
        
        # 性能断言
        assert stats['execution_time'] < 15  # 15秒内完成
        assert stats['memory_usage_mb'] < 200  # 内存使用小于200MB
        assert len(signals) > 0
        
        print(f"策略计算性能: {stats}")
        print(f"信号计算次数: {len(signals)}")
        print(f"计算速度: {len(signals)/stats['execution_time']:.0f} 信号/秒")
    
    @pytest.mark.performance
    def test_multiple_strategy_performance(self, performance_tracker, large_stock_data):
        """测试多策略并行计算性能"""
        strategies = [
            MACrossoverStrategy(),
            RSIStrategy()
        ]
        
        # 性能测试：多策略计算
        performance_tracker.start()
        
        def calculate_strategy_signals(strategy, data):
            """计算单个策略的信号"""
            results = []
            for stock_code in data['ts_code'].unique()[:5]:  # 限制股票数量
                stock_data = data[data['ts_code'] == stock_code]
                signal = strategy.calculate_signals(stock_data)
                results.append((strategy.name, stock_code, signal))
            return results
        
        all_results = []
        with ThreadPoolExecutor(max_workers=len(strategies)) as executor:
            futures = [
                executor.submit(calculate_strategy_signals, strategy, large_stock_data)
                for strategy in strategies
            ]
            
            for future in futures:
                results = future.result()
                all_results.extend(results)
                performance_tracker.update_memory()
        
        stats = performance_tracker.stop()
        
        # 性能断言
        assert stats['execution_time'] < 10  # 10秒内完成
        assert stats['memory_usage_mb'] < 300  # 内存使用小于300MB
        assert len(all_results) > 0
        
        print(f"多策略计算性能: {stats}")
        print(f"策略数量: {len(strategies)}")
        print(f"总信号数: {len(all_results)}")
    
    @pytest.mark.performance
    def test_backtest_performance(self, performance_tracker, large_stock_data):
        """测试回测引擎性能"""
        strategy = MACrossoverStrategy()
        backtest_engine = BacktestEngine(
            initial_capital=1000000,
            commission=0.0003,
            stamp_tax=0.001
        )
        
        # 性能测试：大规模回测
        performance_tracker.start()
        
        # 使用单只股票的一年数据进行回测
        stock_data = large_stock_data[large_stock_data['ts_code'] == '000001.SZ']
        
        results = backtest_engine.run_backtest(
            strategy=strategy,
            data=stock_data,
            start_date='20230101',
            end_date='20231231'
        )
        
        performance_tracker.update_memory()
        stats = performance_tracker.stop()
        
        # 性能断言
        assert stats['execution_time'] < 30  # 30秒内完成
        assert stats['memory_usage_mb'] < 400  # 内存使用小于400MB
        assert results is not None
        assert 'portfolio_value' in results
        
        print(f"回测性能: {stats}")
        print(f"回测数据量: {len(stock_data)} 条")
        print(f"回测速度: {len(stock_data)/stats['execution_time']:.0f} 条/秒")


class TestSystemLoadPerformance:
    """系统负载性能测试"""
    
    @pytest.mark.performance
    @pytest.mark.slow
    def test_memory_stress_test(self, performance_tracker):
        """内存压力测试"""
        performance_tracker.start()
        
        # 创建大量数据对象
        large_objects = []
        
        try:
            for i in range(100):
                # 创建大的DataFrame对象
                data = pd.DataFrame(np.random.randn(10000, 100))
                large_objects.append(data)
                performance_tracker.update_memory()
                
                # 检查内存使用
                if performance_tracker.peak_memory > 1024 * 1024 * 1024:  # 1GB
                    break
            
            stats = performance_tracker.stop()
            
            # 性能断言
            assert stats['memory_usage_mb'] < 1200  # 内存使用小于1.2GB
            
            print(f"内存压力测试: {stats}")
            print(f"创建对象数量: {len(large_objects)}")
            
        finally:
            # 清理内存
            del large_objects
            import gc
            gc.collect()
    
    @pytest.mark.performance
    def test_cpu_intensive_operations(self, performance_tracker):
        """CPU密集型操作测试"""
        performance_tracker.start()
        
        def cpu_bound_task(n):
            """CPU密集型任务"""
            result = 0
            for i in range(n):
                result += i ** 2
            return result
        
        # 并行执行CPU密集型任务
        num_processes = multiprocessing.cpu_count()
        task_size = 1000000
        
        with ProcessPoolExecutor(max_workers=num_processes) as executor:
            futures = [
                executor.submit(cpu_bound_task, task_size) 
                for _ in range(num_processes)
            ]
            
            results = [future.result() for future in futures]
            performance_tracker.update_memory()
        
        stats = performance_tracker.stop()
        
        # 性能断言
        assert stats['execution_time'] < 20  # 20秒内完成
        assert len(results) == num_processes
        
        print(f"CPU密集型测试: {stats}")
        print(f"进程数量: {num_processes}")
        print(f"任务大小: {task_size}")
    
    @pytest.mark.performance
    def test_io_intensive_operations(self, performance_tracker, temp_dir):
        """IO密集型操作测试"""
        performance_tracker.start()
        
        def io_bound_task(file_path, data_size):
            """IO密集型任务"""
            data = 'x' * data_size
            with open(file_path, 'w') as f:
                for _ in range(100):
                    f.write(data)
            
            # 读取文件
            with open(file_path, 'r') as f:
                content = f.read()
            
            return len(content)
        
        # 并行执行IO密集型任务
        num_threads = 20
        data_size = 10000
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for i in range(num_threads):
                file_path = os.path.join(temp_dir, f"test_file_{i}.txt")
                future = executor.submit(io_bound_task, file_path, data_size)
                futures.append(future)
            
            results = [future.result() for future in futures]
            performance_tracker.update_memory()
        
        stats = performance_tracker.stop()
        
        # 性能断言
        assert stats['execution_time'] < 15  # 15秒内完成
        assert len(results) == num_threads
        
        print(f"IO密集型测试: {stats}")
        print(f"线程数量: {num_threads}")
        print(f"文件数量: {num_threads}")


class TestScalabilityPerformance:
    """可扩展性性能测试"""
    
    @pytest.mark.performance
    @pytest.mark.parametrize("data_size", [1000, 5000, 10000, 50000])
    def test_data_processing_scalability(self, performance_tracker, data_size):
        """测试数据处理可扩展性"""
        # 生成不同大小的测试数据
        np.random.seed(42)
        test_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * data_size,
            'trade_date': [f'202301{i%30+1:02d}' for i in range(data_size)],
            'close': np.random.uniform(10, 100, data_size),
            'vol': np.random.randint(1000000, 10000000, data_size)
        })
        
        strategy = MACrossoverStrategy()
        
        performance_tracker.start()
        
        # 批量处理数据
        batch_size = 100
        signals = []
        for i in range(0, len(test_data), batch_size):
            batch = test_data.iloc[i:i+batch_size]
            if len(batch) >= 20:  # 确保有足够数据计算移动平均
                signal = strategy.calculate_signals(batch)
                signals.append(signal)
            performance_tracker.update_memory()
        
        stats = performance_tracker.stop()
        
        # 计算性能指标
        throughput = data_size / stats['execution_time']
        memory_per_record = stats['memory_usage_mb'] / data_size * 1024  # KB per record
        
        print(f"数据量: {data_size}, 耗时: {stats['execution_time']:.2f}s, "
              f"吞吐量: {throughput:.0f} 条/秒, "
              f"内存/记录: {memory_per_record:.2f} KB")
        
        # 可扩展性断言
        assert throughput > 100  # 最低吞吐量要求
        assert memory_per_record < 10  # 每条记录内存使用小于10KB
    
    @pytest.mark.performance
    def test_concurrent_user_simulation(self, performance_tracker, temp_dir):
        """模拟并发用户访问"""
        db_path = os.path.join(temp_dir, "concurrent_test.db")
        db_manager = DatabaseManager(db_path)
        
        # 准备测试数据
        test_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 1000,
            'trade_date': [f'202301{i%30+1:02d}' for i in range(1000)],
            'close': np.random.uniform(10, 100, 1000),
            'vol': np.random.randint(1000000, 10000000, 1000)
        })
        db_manager.save_stock_data(test_data)
        
        def simulate_user_session(user_id):
            """模拟用户会话"""
            operations = []
            start_time = time.time()
            
            # 执行一系列操作
            for _ in range(10):
                # 查询数据
                result = db_manager.get_stock_data('000001.SZ', '20230101', '20230115')
                operations.append(('query', len(result)))
                
                # 策略计算
                if not result.empty:
                    strategy = MACrossoverStrategy()
                    signal = strategy.calculate_signals(result)
                    operations.append(('strategy', signal['confidence']))
                
                time.sleep(0.1)  # 模拟用户思考时间
            
            return {
                'user_id': user_id,
                'duration': time.time() - start_time,
                'operations': len(operations)
            }
        
        # 性能测试：模拟多用户并发访问
        performance_tracker.start()
        
        num_users = 20
        with ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = [
                executor.submit(simulate_user_session, i) 
                for i in range(num_users)
            ]
            
            user_results = [future.result() for future in futures]
            performance_tracker.update_memory()
        
        stats = performance_tracker.stop()
        
        # 分析结果
        avg_session_time = np.mean([r['duration'] for r in user_results])
        total_operations = sum(r['operations'] for r in user_results)
        
        # 性能断言
        assert stats['execution_time'] < 30  # 总时间小于30秒
        assert avg_session_time < 5  # 平均会话时间小于5秒
        assert stats['memory_usage_mb'] < 500  # 内存使用小于500MB
        
        print(f"并发用户模拟: {stats}")
        print(f"用户数量: {num_users}")
        print(f"平均会话时间: {avg_session_time:.2f}s")
        print(f"总操作数: {total_operations}")
        print(f"操作吞吐量: {total_operations/stats['execution_time']:.0f} 操作/秒")


if __name__ == "__main__":
    # 运行性能测试
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short",
        "-m", "performance"
    ])