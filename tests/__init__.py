"""
量化交易系统测试模块
包含单元测试、集成测试和性能测试
"""

__version__ = "1.0.0"
__author__ = "LiangHua Trading System"

# 导入常用测试工具
import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock

# 测试配置
TEST_CONFIG = {
    "database": {
        "test_db": "test_trading_system.db",
        "memory_db": ":memory:"
    },
    "mock_data": {
        "stock_codes": ["000001.SZ", "000002.SZ", "600000.SH"],
        "test_period": "2023-01-01",
        "test_end": "2023-12-31"
    },
    "performance": {
        "timeout": 30,  # 测试超时时间（秒）
        "max_memory": 1024 * 1024 * 100  # 最大内存使用（100MB）
    }
}

# 测试工具函数
def setup_test_environment():
    """设置测试环境"""
    import os
    import sys
    
    # 添加项目根目录到路径
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

def cleanup_test_environment():
    """清理测试环境"""
    import os
    import glob
    
    # 清理测试生成的文件
    test_files = glob.glob("test_*.db")
    for file in test_files:
        try:
            os.remove(file)
        except OSError:
            pass

# 测试装饰器
def require_network(func):
    """需要网络连接的测试装饰器"""
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        import socket
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return func(*args, **kwargs)
        except OSError:
            pytest.skip("需要网络连接")
    return wrapper

def slow_test(func):
    """标记慢速测试的装饰器"""
    return pytest.mark.slow(func)

def integration_test(func):
    """标记集成测试的装饰器"""
    return pytest.mark.integration(func)

# 自动设置测试环境
setup_test_environment()