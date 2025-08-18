"""
pytest配置文件
定义测试夹具、配置和钩子函数
"""

import pytest
import os
import sys
import sqlite3
import tempfile
import shutil
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 测试配置
pytest_plugins = ["pytest_html", "pytest-cov"]

def pytest_configure(config):
    """pytest配置"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
    config.addinivalue_line(
        "markers", "network: marks tests that require network access"
    )

@pytest.fixture(scope="session")
def test_config():
    """测试配置夹具"""
    return {
        "tushare": {
            "token": "test_token",
            "timeout": 10
        },
        "database": {
            "path": ":memory:",
            "timeout": 30
        },
        "risk": {
            "max_position": 0.1,
            "max_single_stock": 0.05,
            "stop_loss": 0.05
        },
        "trading": {
            "commission": 0.0003,
            "stamp_tax": 0.001,
            "min_commission": 5
        }
    }

@pytest.fixture(scope="function")
def temp_dir():
    """临时目录夹具"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture(scope="function")
def test_database():
    """测试数据库夹具"""
    # 创建内存数据库
    conn = sqlite3.connect(":memory:")
    
    # 创建测试表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            open_price REAL,
            high_price REAL,
            low_price REAL,
            close_price REAL,
            volume INTEGER,
            amount REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_name TEXT NOT NULL,
            stock_code TEXT NOT NULL,
            action TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        )
    """)
    
    yield conn
    conn.close()

@pytest.fixture(scope="function")
def mock_stock_data():
    """模拟股票数据夹具"""
    dates = pd.date_range(start="2023-01-01", end="2023-12-31", freq="D")
    dates = [d for d in dates if d.weekday() < 5]  # 只保留工作日
    
    data = []
    for date in dates:
        for stock_code in ["000001.SZ", "000002.SZ", "600000.SH"]:
            # 生成模拟价格数据
            base_price = np.random.uniform(10, 100)
            open_price = base_price * np.random.uniform(0.98, 1.02)
            close_price = open_price * np.random.uniform(0.95, 1.05)
            high_price = max(open_price, close_price) * np.random.uniform(1.0, 1.03)
            low_price = min(open_price, close_price) * np.random.uniform(0.97, 1.0)
            volume = np.random.randint(100000, 10000000)
            amount = volume * (high_price + low_price) / 2
            
            data.append({
                "ts_code": stock_code,
                "trade_date": date.strftime("%Y%m%d"),
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "vol": volume,
                "amount": round(amount, 2)
            })
    
    return pd.DataFrame(data)

@pytest.fixture(scope="function")
def mock_tushare_client():
    """模拟Tushare客户端夹具"""
    mock_client = Mock()
    
    # 模拟daily接口
    def mock_daily(*args, **kwargs):
        df = pd.DataFrame({
            "ts_code": ["000001.SZ"] * 5,
            "trade_date": ["20231201", "20231202", "20231203", "20231204", "20231205"],
            "open": [10.0, 10.1, 10.2, 10.3, 10.4],
            "high": [10.5, 10.6, 10.7, 10.8, 10.9],
            "low": [9.8, 9.9, 10.0, 10.1, 10.2],
            "close": [10.2, 10.3, 10.4, 10.5, 10.6],
            "vol": [1000000] * 5,
            "amount": [10200000] * 5
        })
        return df
    
    mock_client.daily.return_value = mock_daily()
    mock_client.stock_basic.return_value = pd.DataFrame({
        "ts_code": ["000001.SZ", "000002.SZ", "600000.SH"],
        "symbol": ["000001", "000002", "600000"],
        "name": ["平安银行", "万科A", "浦发银行"],
        "area": ["深圳", "深圳", "上海"],
        "industry": ["银行", "房地产", "银行"],
        "list_date": ["19910403", "19910129", "19990810"]
    })
    
    return mock_client

@pytest.fixture(scope="function")
def mock_strategy():
    """模拟策略夹具"""
    from strategies.base_strategy import BaseStrategy
    
    class MockStrategy(BaseStrategy):
        def __init__(self):
            super().__init__("mock_strategy")
            self.signals = []
        
        def calculate_signals(self, data):
            # 简单的移动平均策略信号
            if len(data) < 2:
                return {"action": "hold", "confidence": 0.5}
            
            if data.iloc[-1]["close"] > data.iloc[-2]["close"]:
                return {"action": "buy", "confidence": 0.8}
            else:
                return {"action": "sell", "confidence": 0.6}
        
        def update_parameters(self, **kwargs):
            pass
    
    return MockStrategy()

@pytest.fixture(scope="function")
def mock_portfolio():
    """模拟投资组合夹具"""
    return {
        "cash": 1000000.0,
        "positions": {
            "000001.SZ": {"quantity": 1000, "avg_price": 10.0},
            "000002.SZ": {"quantity": 500, "avg_price": 20.0}
        },
        "total_value": 1030000.0,
        "daily_return": 0.02,
        "total_return": 0.03
    }

@pytest.fixture(scope="function")
def mock_risk_manager():
    """模拟风控管理器夹具"""
    from risk.risk_engine import RiskEngine
    
    class MockRiskManager(RiskEngine):
        def __init__(self):
            super().__init__({
                "max_position": 0.1,
                "max_single_stock": 0.05,
                "stop_loss": 0.05,
                "max_drawdown": 0.1
            })
            self.check_results = []
        
        def check_trade(self, trade_signal, portfolio):
            # 模拟风控检查
            result = {
                "approved": True,
                "adjusted_quantity": trade_signal.get("quantity", 100),
                "risk_level": "low",
                "warnings": []
            }
            self.check_results.append(result)
            return result
    
    return MockRiskManager()

@pytest.fixture(scope="function")
def mock_trader():
    """模拟交易执行器夹具"""
    class MockTrader:
        def __init__(self):
            self.executed_trades = []
            self.connected = True
        
        def connect(self):
            self.connected = True
            return True
        
        def disconnect(self):
            self.connected = False
        
        def submit_order(self, order):
            trade = {
                "order_id": f"order_{len(self.executed_trades) + 1}",
                "stock_code": order["stock_code"],
                "action": order["action"],
                "quantity": order["quantity"],
                "price": order["price"],
                "status": "filled",
                "timestamp": datetime.now()
            }
            self.executed_trades.append(trade)
            return trade
        
        def get_account_info(self):
            return {
                "total_asset": 1000000.0,
                "available_cash": 500000.0,
                "market_value": 500000.0
            }
        
        def get_positions(self):
            return [
                {"stock_code": "000001.SZ", "quantity": 1000, "avg_price": 10.0},
                {"stock_code": "000002.SZ", "quantity": 500, "avg_price": 20.0}
            ]
    
    return MockTrader()

@pytest.fixture(autouse=True)
def setup_test_environment():
    """自动设置测试环境"""
    # 设置测试环境变量
    os.environ["TESTING"] = "1"
    os.environ["TUSHARE_TOKEN"] = "test_token"
    
    yield
    
    # 清理测试环境
    if "TESTING" in os.environ:
        del os.environ["TESTING"]

# 性能测试工具
class PerformanceMonitor:
    def __init__(self):
        self.start_time = None
        self.peak_memory = 0
    
    def start(self):
        import psutil
        import time
        self.start_time = time.time()
        self.peak_memory = psutil.Process().memory_info().rss
    
    def stop(self):
        import psutil
        import time
        end_time = time.time()
        final_memory = psutil.Process().memory_info().rss
        self.peak_memory = max(self.peak_memory, final_memory)
        
        return {
            "execution_time": end_time - self.start_time,
            "peak_memory_mb": self.peak_memory / 1024 / 1024,
            "memory_growth_mb": (final_memory - self.peak_memory) / 1024 / 1024
        }

@pytest.fixture(scope="function")
def performance_monitor():
    """性能监控夹具"""
    return PerformanceMonitor()

# 测试数据清理
def pytest_runtest_teardown(item, nextitem):
    """每个测试后的清理"""
    import gc
    gc.collect()

# 测试报告钩子
def pytest_html_report_title(report):
    """HTML报告标题"""
    report.title = "量化交易系统测试报告"

def pytest_html_results_summary(prefix, summary, postfix):
    """HTML报告摘要"""
    prefix.extend([
        f"<p>测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
        "<p>测试范围: 完整系统集成测试</p>"
    ])