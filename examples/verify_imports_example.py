#!/usr/bin/env python3
"""
导入验证示例脚本
验证目录重构后的导入路径是否正确
"""

import sys
import os

# 确保可以找到src模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_basic_imports():
    """测试基础模块导入"""
    print("🔍 测试基础模块导入...")
    
    try:
        # 测试策略模块
        from src.strategies import BaseStrategy, MovingAverageCrossoverStrategy, RSIStrategy
        print("[OK] 策略模块导入成功")
        
        # 测试回测模块
        from src.backtest import BacktestEngine, Portfolio
        print("[OK] 回测模块导入成功")
        
        # 测试风险管理模块
        from src.risk import RiskEngine, PositionManager
        print("[OK] 风险管理模块导入成功")
        
        # 测试数据模块
        from src.data import DatabaseManager, TushareClient
        print("[OK] 数据模块导入成功")
        
        # 测试监控模块
        from src.monitor import RealtimeMonitor, AlertManager
        print("[OK] 监控模块导入成功")
        
        # 测试配置模块
        from src.config import Settings
        print("[OK] 配置模块导入成功")
        
        # 测试交易模块
        from src.trading import BaseTrader, TradeExecutor
        print("[OK] 交易模块导入成功")
        
        # 测试优化模块
        from src.optimization import CacheManager, DatabaseOptimizer
        print("[OK] 优化模块导入成功")
        
        # 测试验证模块
        from src.validation import SystemChecker, BenchmarkRunner
        print("[OK] 验证模块导入成功")
        
        return True
        
    except ImportError as e:
        print(f"[ERROR] 导入失败: {e}")
        return False

def test_package_level_imports():
    """测试包级别导入"""
    print("\n🔍 测试包级别导入...")
    
    try:
        # 测试主包导入
        import src
        print(f"[OK] 主包导入成功，版本: {src.__version__}")
        
        # 测试子包导入
        from src import strategies, backtest, risk, data, monitor
        print("[OK] 子包导入成功")
        
        return True
        
    except ImportError as e:
        print(f"[ERROR] 包级别导入失败: {e}")
        return False

def test_strategy_creation():
    """测试策略创建"""
    print("\n🔍 测试策略创建...")
    
    try:
        from src.strategies import create_strategy_by_name, get_strategy_catalog
        
        # 获取策略目录
        catalog = get_strategy_catalog()
        print(f"[OK] 获取策略目录成功，包含 {len(catalog)} 个策略")
        
        # 创建策略实例
        ma_strategy = create_strategy_by_name('MovingAverageCrossover', 'test_ma')
        print(f"[OK] 创建移动平均策略成功: {ma_strategy.name}")
        
        rsi_strategy = create_strategy_by_name('RSI', 'test_rsi')
        print(f"[OK] 创建RSI策略成功: {rsi_strategy.name}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 策略创建失败: {e}")
        return False

def test_cross_module_imports():
    """测试跨模块导入"""
    print("\n🔍 测试跨模块导入...")
    
    try:
        # 创建一个使用多个模块的示例
        from src.strategies.base_strategy import BaseStrategy
        from src.risk.position_manager import PositionManager
        from src.data.database import DatabaseManager
        
        class TestStrategy(BaseStrategy):
            def __init__(self):
                super().__init__("test_strategy")
                self.position_manager = PositionManager()
                self.data_manager = DatabaseManager()
        
        test_strategy = TestStrategy()
        print(f"[OK] 跨模块导入成功，创建测试策略: {test_strategy.name}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 跨模块导入失败: {e}")
        return False

def show_import_examples():
    """显示导入示例"""
    print("\n📋 常用导入示例：")
    print("="*50)
    
    examples = [
        "# 策略模块",
        "from src.strategies import BaseStrategy, MovingAverageCrossoverStrategy",
        "from src.strategies import create_strategy_by_name",
        "",
        "# 回测模块", 
        "from src.backtest import BacktestEngine, Portfolio",
        "",
        "# 风险管理",
        "from src.risk import RiskEngine, PositionManager",
        "",
        "# 数据管理",
        "from src.data import DatabaseManager, TushareClient",
        "",
        "# 监控系统",
        "from src.monitor import RealtimeMonitor, AlertManager",
        "",
        "# 交易执行",
        "from src.trading import BaseTrader, TradeExecutor",
        "",
        "# 包级别导入",
        "import src",
        "from src import strategies, backtest, risk, data, monitor"
    ]
    
    for example in examples:
        print(example)

def main():
    """主函数"""
    print("[VERIFY] 量化交易系统导入验证")
    print("="*50)
    
    # 显示项目路径
    print(f"[DIR] 项目根目录: {project_root}")
    
    # 运行各种测试
    tests = [
        test_basic_imports,
        test_package_level_imports, 
        test_strategy_creation,
        test_cross_module_imports
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
    
    # 显示总结
    print("\n[SUMMARY] 测试总结")
    print("="*50)
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"[OK] 所有测试通过 ({passed}/{total})")
        print("🎉 导入路径配置正确，可以正常使用新的目录结构！")
    else:
        print(f"[ERROR] 部分测试失败 ({passed}/{total})")
        print("⚠️  请检查导入路径或项目配置")
    
    # 显示导入示例
    show_import_examples()
    
    print("\n💡 提示：")
    print("- 如果导入失败，请确保在项目根目录运行此脚本")
    print("- 或者使用 'pip install -e .' 安装开发版本")
    print("- 详细说明请参考: docs/导入路径更新指南.md")

if __name__ == "__main__":
    main()