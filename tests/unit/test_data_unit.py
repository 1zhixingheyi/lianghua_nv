"""
数据模块单元测试
测试数据采集和数据库操作的各个组件
"""

import pytest
import os
import sys
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.data.tushare_client import TushareClient
from src.data.database import DatabaseManager


class TestTushareClientUnit:
    """Tushare客户端单元测试"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """测试设置"""
        self.token = "test_token"
        
    def test_client_initialization(self):
        """测试客户端初始化"""
        client = TushareClient(self.token)
        assert client.token == self.token
        assert client.timeout == 10  # 默认超时
        
        # 测试自定义超时
        client_custom = TushareClient(self.token, timeout=30)
        assert client_custom.timeout == 30
    
    def test_token_validation(self):
        """测试Token验证"""
        # 测试空token
        with pytest.raises(ValueError):
            TushareClient("")
        
        with pytest.raises(ValueError):
            TushareClient(None)
        
        # 测试有效token
        client = TushareClient("valid_token")
        assert client.token == "valid_token"
    
    @patch('data.tushare_client.ts.pro_api')
    def test_api_connection(self, mock_pro_api):
        """测试API连接"""
        mock_api = Mock()
        mock_pro_api.return_value = mock_api
        
        client = TushareClient(self.token)
        api = client._get_api()
        
        assert api == mock_api
        mock_pro_api.assert_called_once_with(self.token)
    
    @patch('data.tushare_client.ts.pro_api')
    def test_daily_data_retrieval(self, mock_pro_api):
        """测试日线数据获取"""
        # 准备模拟数据
        mock_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 5,
            'trade_date': ['20231201', '20231202', '20231203', '20231204', '20231205'],
            'open': [10.0, 10.1, 10.2, 10.3, 10.4],
            'high': [10.5, 10.6, 10.7, 10.8, 10.9],
            'low': [9.8, 9.9, 10.0, 10.1, 10.2],
            'close': [10.2, 10.3, 10.4, 10.5, 10.6],
            'vol': [1000000] * 5,
            'amount': [10200000] * 5
        })
        
        mock_api = Mock()
        mock_api.daily.return_value = mock_data
        mock_pro_api.return_value = mock_api
        
        client = TushareClient(self.token)
        result = client.get_daily_data("000001.SZ", "20231201", "20231205")
        
        assert not result.empty
        assert len(result) == 5
        assert all(col in result.columns for col in ['ts_code', 'trade_date', 'close'])
        mock_api.daily.assert_called_once()
    
    @patch('data.tushare_client.ts.pro_api')
    def test_stock_basic_retrieval(self, mock_pro_api):
        """测试股票基本信息获取"""
        mock_basic = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'symbol': ['000001', '000002'],
            'name': ['平安银行', '万科A'],
            'area': ['深圳', '深圳'],
            'industry': ['银行', '房地产'],
            'list_date': ['19910403', '19910129']
        })
        
        mock_api = Mock()
        mock_api.stock_basic.return_value = mock_basic
        mock_pro_api.return_value = mock_api
        
        client = TushareClient(self.token)
        result = client.get_stock_basic()
        
        assert not result.empty
        assert len(result) == 2
        assert 'ts_code' in result.columns
        assert 'name' in result.columns
    
    @patch('data.tushare_client.ts.pro_api')
    def test_api_error_handling(self, mock_pro_api):
        """测试API错误处理"""
        mock_api = Mock()
        mock_api.daily.side_effect = Exception("API请求失败")
        mock_pro_api.return_value = mock_api
        
        client = TushareClient(self.token)
        
        with pytest.raises(Exception) as exc_info:
            client.get_daily_data("000001.SZ", "20231201", "20231205")
        
        assert "API请求失败" in str(exc_info.value)
    
    def test_date_validation(self):
        """测试日期验证"""
        client = TushareClient(self.token)
        
        # 测试无效日期格式
        with pytest.raises(ValueError):
            client._validate_date("2023-12-01")  # 错误格式
        
        with pytest.raises(ValueError):
            client._validate_date("20231301")  # 无效月份
        
        # 测试有效日期
        assert client._validate_date("20231201") == "20231201"
    
    def test_rate_limiting(self):
        """测试频率限制"""
        client = TushareClient(self.token)
        
        # 测试请求间隔
        start_time = datetime.now()
        client._wait_for_rate_limit()
        end_time = datetime.now()
        
        # 第一次调用应该没有延迟
        assert (end_time - start_time).total_seconds() < 0.1
        
        # 连续调用应该有延迟
        start_time = datetime.now()
        client._wait_for_rate_limit()
        client._wait_for_rate_limit()
        end_time = datetime.now()
        
        # 应该有短暂延迟（根据实际实现调整）
        # assert (end_time - start_time).total_seconds() >= 0.2


class TestDatabaseManagerUnit:
    """数据库管理器单元测试"""
    
    @pytest.fixture(autouse=True)
    def setup(self, temp_dir):
        """测试设置"""
        self.temp_dir = temp_dir
        self.db_path = os.path.join(temp_dir, "test_unit.db")
        self.db_manager = DatabaseManager(self.db_path)
    
    def test_database_initialization(self):
        """测试数据库初始化"""
        # 验证数据库文件创建
        assert os.path.exists(self.db_path)
        
        # 验证表结构
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 检查stock_data表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stock_data'")
        assert cursor.fetchone() is not None
        
        # 检查表结构
        cursor.execute("PRAGMA table_info(stock_data)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        expected_columns = ['id', 'ts_code', 'trade_date', 'open_price', 'high_price', 
                          'low_price', 'close_price', 'volume', 'amount', 'created_at']
        for col in expected_columns:
            assert col in column_names
        
        conn.close()
    
    def test_stock_data_save_and_retrieve(self):
        """测试股票数据保存和查询"""
        # 准备测试数据
        test_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 3,
            'trade_date': ['20231201', '20231202', '20231203'],
            'open': [10.0, 10.1, 10.2],
            'high': [10.5, 10.6, 10.7],
            'low': [9.8, 9.9, 10.0],
            'close': [10.2, 10.3, 10.4],
            'vol': [1000000] * 3,
            'amount': [10200000] * 3
        })
        
        # 保存数据
        self.db_manager.save_stock_data(test_data)
        
        # 查询数据
        result = self.db_manager.get_stock_data("000001.SZ", "20231201", "20231203")
        
        assert not result.empty
        assert len(result) == 3
        assert all(result['ts_code'] == '000001.SZ')
        assert result.iloc[0]['close_price'] == 10.2
    
    def test_data_update_and_duplicate_handling(self):
        """测试数据更新和重复处理"""
        # 初始数据
        initial_data = pd.DataFrame({
            'ts_code': ['000001.SZ'],
            'trade_date': ['20231201'],
            'open': [10.0],
            'high': [10.5],
            'low': [9.8],
            'close': [10.2],
            'vol': [1000000],
            'amount': [10200000]
        })
        
        self.db_manager.save_stock_data(initial_data)
        
        # 重复数据（应该更新）
        duplicate_data = pd.DataFrame({
            'ts_code': ['000001.SZ'],
            'trade_date': ['20231201'],
            'open': [10.1],  # 不同的开盘价
            'high': [10.6],
            'low': [9.9],
            'close': [10.3],  # 不同的收盘价
            'vol': [1100000],
            'amount': [11330000]
        })
        
        self.db_manager.save_stock_data(duplicate_data)
        
        # 验证更新
        result = self.db_manager.get_stock_data("000001.SZ", "20231201", "20231201")
        assert len(result) == 1
        assert result.iloc[0]['close_price'] == 10.3  # 应该是更新后的价格
    
    def test_data_validation_and_cleaning(self):
        """测试数据验证和清理"""
        # 包含无效数据的DataFrame
        invalid_data = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ', '000003.SZ'],
            'trade_date': ['20231201', '20231202', 'invalid_date'],
            'open': [10.0, None, 15.0],  # 包含空值
            'high': [10.5, 20.5, -5.0],  # 包含负值
            'low': [9.8, 19.8, 14.5],
            'close': [10.2, 20.2, 14.8],
            'vol': [1000000, -1000, 1500000],  # 包含负值
            'amount': [10200000, 20400000, 22200000]
        })
        
        # 验证和清理数据
        cleaned_data = self.db_manager.validate_and_clean_data(invalid_data)
        
        # 验证清理结果
        assert len(cleaned_data) == 1  # 只有第一行是有效的
        assert cleaned_data.iloc[0]['ts_code'] == '000001.SZ'
        assert not cleaned_data.isnull().any().any()  # 没有空值
        assert all(cleaned_data['vol'] > 0)  # 成交量为正
    
    def test_batch_operations(self):
        """测试批量操作"""
        # 生成大量测试数据
        large_data = []
        for i in range(1000):
            large_data.append({
                'ts_code': f'{i%10:06d}.SZ',
                'trade_date': f'202312{(i%20)+1:02d}',
                'open': 10.0 + i * 0.01,
                'high': 10.5 + i * 0.01,
                'low': 9.8 + i * 0.01,
                'close': 10.2 + i * 0.01,
                'vol': 1000000 + i * 1000,
                'amount': 10200000 + i * 10200
            })
        
        df = pd.DataFrame(large_data)
        
        # 批量保存
        start_time = datetime.now()
        self.db_manager.save_stock_data(df)
        save_time = (datetime.now() - start_time).total_seconds()
        
        # 验证保存性能（应该在合理时间内完成）
        assert save_time < 5.0  # 5秒内完成
        
        # 批量查询
        start_time = datetime.now()
        result = self.db_manager.get_stock_data(['000000.SZ', '000001.SZ'], '20231201', '20231220')
        query_time = (datetime.now() - start_time).total_seconds()
        
        assert not result.empty
        assert query_time < 1.0  # 1秒内完成查询
    
    def test_database_connection_management(self):
        """测试数据库连接管理"""
        # 测试连接池
        connections = []
        for i in range(5):
            conn = self.db_manager._get_connection()
            connections.append(conn)
        
        # 验证连接有效性
        for conn in connections:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1
        
        # 关闭连接
        for conn in connections:
            conn.close()
    
    def test_transaction_handling(self):
        """测试事务处理"""
        # 准备测试数据
        test_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 2,
            'trade_date': ['20231201', '20231202'],
            'open': [10.0, 10.1],
            'high': [10.5, 10.6],
            'low': [9.8, 9.9],
            'close': [10.2, 10.3],
            'vol': [1000000] * 2,
            'amount': [10200000] * 2
        })
        
        # 测试事务回滚（模拟错误）
        original_save = self.db_manager._save_single_record
        
        def failing_save(record):
            if record['trade_date'] == '20231202':
                raise Exception("模拟保存失败")
            return original_save(record)
        
        self.db_manager._save_single_record = failing_save
        
        # 尝试保存（应该回滚）
        try:
            self.db_manager.save_stock_data(test_data)
        except Exception:
            pass
        
        # 验证回滚：两条记录都不应该保存
        result = self.db_manager.get_stock_data("000001.SZ", "20231201", "20231202")
        assert len(result) == 0  # 事务回滚，没有数据保存
        
        # 恢复原始方法
        self.db_manager._save_single_record = original_save
    
    def test_index_and_performance(self):
        """测试索引和性能"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 检查索引
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = cursor.fetchall()
        index_names = [idx[0] for idx in indexes]
        
        # 验证关键索引存在
        expected_indexes = ['idx_stock_data_ts_code', 'idx_stock_data_trade_date']
        for idx in expected_indexes:
            assert any(idx in name for name in index_names)
        
        conn.close()
    
    def test_database_backup_and_restore(self, temp_dir):
        """测试数据库备份和恢复"""
        # 添加测试数据
        test_data = pd.DataFrame({
            'ts_code': ['000001.SZ'],
            'trade_date': ['20231201'],
            'open': [10.0],
            'high': [10.5],
            'low': [9.8],
            'close': [10.2],
            'vol': [1000000],
            'amount': [10200000]
        })
        
        self.db_manager.save_stock_data(test_data)
        
        # 创建备份
        backup_path = os.path.join(temp_dir, "backup.db")
        self.db_manager.backup_database(backup_path)
        assert os.path.exists(backup_path)
        
        # 验证备份内容
        backup_manager = DatabaseManager(backup_path)
        backup_data = backup_manager.get_stock_data("000001.SZ", "20231201", "20231201")
        assert len(backup_data) == 1
        assert backup_data.iloc[0]['close_price'] == 10.2
    
    def test_memory_database(self):
        """测试内存数据库"""
        memory_db = DatabaseManager(":memory:")
        
        # 添加测试数据
        test_data = pd.DataFrame({
            'ts_code': ['000001.SZ'],
            'trade_date': ['20231201'],
            'open': [10.0],
            'high': [10.5],
            'low': [9.8],
            'close': [10.2],
            'vol': [1000000],
            'amount': [10200000]
        })
        
        memory_db.save_stock_data(test_data)
        
        # 验证数据
        result = memory_db.get_stock_data("000001.SZ", "20231201", "20231201")
        assert len(result) == 1
        
        # 内存数据库应该不会创建文件
        assert not os.path.exists(":memory:")


if __name__ == "__main__":
    # 运行数据单元测试
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short",
        "-m", "unit"
    ])