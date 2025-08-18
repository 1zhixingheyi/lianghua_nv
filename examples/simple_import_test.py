#!/usr/bin/env python3
"""
简单的导入测试脚本
验证重构后的模块导入是否正常工作
"""

import sys
import os
import traceback

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_import(module_name, description):
    """测试单个模块的导入"""
    try:
        __import__(module_name)
        print(f"[OK] {description}: {module_name}")
        return True
    except ImportError as e:
        print(f"[FAIL] {description}: {module_name} - {e}")
        return False
    except Exception as e:
        print(f"[ERROR] {description}: {module_name} - {e}")
        return False

def main():
    """主测试函数"""
    print("开始导入测试...")
    print("=" * 50)
    
    # 测试模块列表
    test_modules = [
        ("src.config", "配置模块"),
        ("src.data", "数据模块"),
        ("src.backtest", "回测模块"),
        ("src.strategies", "策略模块"),
        ("src.risk", "风险管理模块"),
        ("src.trading", "交易模块"),
        ("src.monitor", "监控模块"),
        ("src.optimization", "优化模块"),
        ("src.validation", "验证模块"),
    ]
    
    success_count = 0
    total_count = len(test_modules)
    
    print(f"测试 {total_count} 个模块...")
    print()
    
    for module_name, description in test_modules:
        if test_import(module_name, description):
            success_count += 1
    
    print()
    print("=" * 50)
    print(f"测试结果: {success_count}/{total_count} 个模块导入成功")
    
    if success_count == total_count:
        print("所有模块导入测试通过！")
        return 0
    else:
        print(f"有 {total_count - success_count} 个模块导入失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())