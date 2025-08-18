"""
数据模块集成测试
测试数据采集、存储和查询的完整流程
"""

import pytest
import os
import sys
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from data.tushare_client import TushareClient
from data.database import DatabaseManager


class TestDataIntegration:
    """数据集成测试类"""
    
    @pytest.fixture(autouse=True)
    def setup(self, test_database, temp_dir):
        """测试设置"""
        self.db = test_database
        self.temp_dir = temp_dir
        self.db_path = os.path.join(temp_dir, "test_data.db")
        self.db_manager = DatabaseManager(self.db_path)
    
    @pytest.mark.integration
    def test_tushare_data_collection(self, mock_tushare_client):
        """测试Tushare数据采集"""
        with patch('data.tushare_client.TushareClient') as mock_client_class:
            mock_client_class.return_value = mock_tushare_client
            
            # 创建数据客户端
            client = TushareClient("test_token")
            
            # 测试日线数据获取
            daily_data = client.get_daily_data("000001.SZ", "20231201", "20231205")
            assert not daily_data.empty
            assert len(daily_data) == 5
            assert all(col in daily_data.columns for col in ['ts_code', 'trade_date', 'close'])
            
            # 测试股票基本信息获取
            stock_basic = client.get_stock_basic()
            assert not stock_basic.empty
            assert 'ts_code' in stock_basic.columns
            assert 'name' in stock_basic.columns
    
    @pytest.mark.integration
    def test_database_operations(self):
        """测试数据库操作"""
        # 准备测试数据
        test_data = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'] * 3,
            'trade_date': ['20231201', '20231202', '20231203'] * 2,
            'open': [10.0, 20.0, 10.1, 20.1, 10.2, 20.2],
            'high': [10.5, 20.5, 10.6, 20.6, 10.7, 20.7],
            'low': [9.8, 19.8, 9.9, 19.9, 10.0, 20.0],
            'close': [10.2, 20.2, 10.3, 20.3, 10.4, 20.4],
            'vol': [1000000] * 6,
            'amount': [10200000, 40400000] * 3
        })
        
        # 保存数据
        self.db_manager.save_stock_data(test_data)
        
        # 查询单个股票数据
        stock_data = self.db_manager.get_stock_data("000001.SZ", "20231201", "20231203")
        assert len(stock_data) == 3
        assert all(stock_data['ts_code'] == '000001.SZ')
        
        # 查询多个股票数据
        multi_stock_data = self.db_manager.get_stock_data(
            ["000001.SZ", "000002.SZ"], "20231201", "20231203"
        )
        assert len(multi_stock_data) == 6
        
        # 查询最新数据
        latest_data = self.db_manager.get_latest_data("000001.SZ")
        assert latest_data is not None
        assert latest_data['trade_date'] == '20231203'
    
    @pytest.mark.integration
    def test_data_validation(self):
        """测试数据验证"""
        # 测试无效数据处理
        invalid_data = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'trade_date': ['20231201', '20231202'],
            'open': [10.0, None],  # 包含空值
            'high': [10.5, 20.5],
            'low': [9.8, 19.8],
            'close': [10.2, 20.2],
            'vol': [1000000, -1000],  # 包含负值
            'amount': [10200000, 20400000]
        })
        
        # 保存数据前验证
        cleaned_data = self.db_manager.validate_and_clean_data(invalid_data)
        assert len(cleaned_data) == 1  # 应该过滤掉无效记录
        assert cleaned_data.iloc[0]['ts_code'] == '000001.SZ'
    
    @pytest.mark.integration
    def test_data_update_and_sync(self):
        """测试数据更新和同步"""
        # 初始数据
        initial_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 3,
            'trade_date': ['20231201', '20231202', '20231203'],
            'open': [10.0, 10.1, 10.2],
            'high': [10.5, 10.6, 10.7],
            'low': [9.8, 9.9, 10.0],
            'close': [10.2, 10.3, 10.4],
            'vol': [1000000] * 3,
            'amount': [10200000] * 3
        })
        
        self.db_manager.save_stock_data(initial_data)
        
        # 更新数据
        update_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 2,
            'trade_date': ['20231203', '20231204'],  # 包含重复日期
            'open': [10.3, 10.4],  # 更新的价格
            'high': [10.8, 10.9],
            'low': [10.1, 10.2],
            'close': [10.5, 10.6],
            'vol': [1100000, 1200000],
            'amount': [11550000, 12720000]
        })
        
        self.db_manager.update_stock_data(update_data)
        
        # 验证更新结果
        updated_data = self.db_manager.get_stock_data("000001.SZ", "20231201", "20231204")
        assert len(updated_data) == 4  # 应该有4条记录
        
        # 验证更新的数据
        dec_03_data = updated_data[updated_data['trade_date'] == '20231203']
        assert len(dec_03_data) == 1
        assert dec_03_data.iloc[0]['close'] == 10.5  # 应该是更新后的价格
    
    @pytest.mark.integration
    def test_data_aggregation(self):
        """测试数据聚合功能"""
        # 准备测试数据（一个月的数据）
        dates = pd.date_range(start='2023-12-01', end='2023-12-31', freq='D')
        dates = [d for d in dates if d.weekday() < 5]  # 只保留工作日
        
        test_data = []
        for i, date in enumerate(dates):
            test_data.append({
                'ts_code': '000001.SZ',
                'trade_date': date.strftime('%Y%m%d'),
                'open': 10.0 + i * 0.1,
                'high': 10.5 + i * 0.1,
                'low': 9.8 + i * 0.1,
                'close': 10.2 + i * 0.1,
                'vol': 1000000 + i * 10000,
                'amount': 10200000 + i * 102000
            })
        
        df = pd.DataFrame(test_data)
        self.db_manager.save_stock_data(df)
        
        # 测试周数据聚合
        weekly_data = self.db_manager.get_weekly_data("000001.SZ", "20231201", "20231231")
        assert not weekly_data.empty
        assert len(weekly_data) <= len(dates) / 5 + 1  # 周数据应该少于日数据
        
        # 测试月数据聚合
        monthly_data = self.db_manager.get_monthly_data("000001.SZ", "20231201", "20231231")
        assert not monthly_data.empty
        assert len(monthly_data) == 1  # 只有一个月的数据
    
    @pytest.mark.integration
    def test_data_export_import(self, temp_dir):
        """测试数据导出导入"""
        # 准备测试数据
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
        
        self.db_manager.save_stock_data(test_data)
        
        # 导出数据
        export_file = os.path.join(temp_dir, "export_data.csv")
        self.db_manager.export_data("000001.SZ", "20231201", "20231205", export_file)
        assert os.path.exists(export_file)
        
        # 验证导出文件
        exported_data = pd.read_csv(export_file)
        assert len(exported_data) == 5
        assert all(col in exported_data.columns for col in ['ts_code', 'trade_date', 'close'])
        
        # 清空数据库
        self.db_manager.clear_stock_data("000001.SZ")
        
        # 导入数据
        self.db_manager.import_data(export_file)
        
        # 验证导入结果
        imported_data = self.db_manager.get_stock_data("000001.SZ", "20231201", "20231205")
        assert len(imported_data) == 5
    
    @pytest.mark.integration
    def test_data_backup_restore(self, temp_dir):
        """测试数据备份恢复"""
        # 准备测试数据
        test_data = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'] * 3,
            'trade_date': ['20231201', '20231202', '20231203'] * 2,
            'open': [10.0, 20.0] * 3,
            'high': [10.5, 20.5] * 3,
            'low': [9.8, 19.8] * 3,
            'close': [10.2, 20.2] * 3,
            'vol': [1000000] * 6,
            'amount': [10200000] * 6
        })
        
        self.db_manager.save_stock_data(test_data)
        
        # 创建备份
        backup_file = os.path.join(temp_dir, "backup.db")
        self.db_manager.backup_database(backup_file)
        assert os.path.exists(backup_file)
        
        # 验证备份文件
        backup_manager = DatabaseManager(backup_file)
        backup_data = backup_manager.get_stock_data(["000001.SZ", "000002.SZ"], "20231201", "20231203")
        assert len(backup_data) == 6
        
        # 模拟数据损坏
        self.db_manager.clear_all_data()
        remaining_data = self.db_manager.get_stock_data(["000001.SZ", "000002.SZ"], "20231201", "20231203")
        assert len(remaining_data) == 0
        
        # 从备份恢复
        self.db_manager.restore_database(backup_file)
        restored_data = self.db_manager.get_stock_data(["000001.SZ", "000002.SZ"], "20231201", "20231203")
        assert len(restored_data) == 6
    
    @pytest.mark.integration
    @pytest.mark.performance
    def test_large_data_performance(self, performance_monitor):
        """测试大数据量性能"""
        performance_monitor.start()
        
        # 生成大量测试数据
        stock_codes = [f"{i:06d}.SZ" for i in range(1, 101)]  # 100只股票
        dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
        dates = [d for d in dates if d.weekday() < 5]  # 工作日
        
        large_data = []
        for stock_code in stock_codes:
            for date in dates[:50]:  # 每只股票50个交易日
                large_data.append({
                    'ts_code': stock_code,
                    'trade_date': date.strftime('%Y%m%d'),
                    'open': 10.0,
                    'high': 10.5,
                    'low': 9.8,
                    'close': 10.2,
                    'vol': 1000000,
                    'amount': 10200000
                })
        
        df = pd.DataFrame(large_data)  # 5000条记录
        
        # 批量保存
        self.db_manager.save_stock_data(df)
        
        # 批量查询
        query_codes = stock_codes[:10]
        result = self.db_manager.get_stock_data(query_codes, "20230101", "20230331")
        assert len(result) > 0
        
        performance_stats = performance_monitor.stop()
        
        # 性能验证
        assert performance_stats['execution_time'] < 30  # 30秒内完成
        assert performance_stats['peak_memory_mb'] < 200  # 内存使用小于200MB
        
        print(f"大数据性能测试: {performance_stats}")
    
    @pytest.mark.integration
    def test_concurrent_data_access(self):
        """测试并发数据访问"""
        import threading
        import time
        
        # 准备测试数据
        test_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 10,
            'trade_date': [f"202312{i:02d}" for i in range(1, 11)],
            'open': list(range(10, 20)),
            'high': list(range(11, 21)),
            'low': list(range(9, 19)),
            'close': list(range(10, 20)),
            'vol': [1000000] * 10,
            'amount': [10200000] * 10
        })
        
        self.db_manager.save_stock_data(test_data)
        
        results = []
        errors = []
        
        def read_data(thread_id):
            """并发读取数据"""
            try:
                for i in range(5):
                    data = self.db_manager.get_stock_data("000001.SZ", "20231201", "20231210")
                    results.append((thread_id, len(data)))
                    time.sleep(0.1)
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        def write_data(thread_id):
            """并发写入数据"""
            try:
                for i in range(3):
                    new_data = pd.DataFrame({
                        'ts_code': [f'00000{thread_id}.SZ'],
                        'trade_date': [f'202312{10 + i:02d}'],
                        'open': [15.0],
                        'high': [15.5],
                        'low': [14.8],
                        'close': [15.2],
                        'vol': [1500000],
                        'amount': [22800000]
                    })
                    self.db_manager.save_stock_data(new_data)
                    time.sleep(0.1)
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # 启动并发线程
        threads = []
        
        # 3个读线程
        for i in range(3):
            t = threading.Thread(target=read_data, args=(f'read_{i}',))
            threads.append(t)
            t.start()
        
        # 2个写线程
        for i in range(2):
            t = threading.Thread(target=write_data, args=(f'write_{i}',))
            threads.append(t)
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join()
        
        # 验证结果
        assert len(errors) == 0, f"并发访问出现错误: {errors}"
        assert len(results) >= 15  # 3个读线程 × 5次读取
        
        # 验证数据完整性
        final_data = self.db_manager.get_stock_data("000001.SZ", "20231201", "20231210")
        assert len(final_data) == 10  # 原始数据应该完整


if __name__ == "__main__":
    # 运行数据集成测试
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short",
        "-m", "integration"
    ])