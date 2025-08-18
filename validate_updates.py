#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import traceback

sys.path.append('.')

# 设置必要的环境变量
os.environ['MYSQL_USERNAME'] = os.environ.get('MYSQL_USER', 'quant')
os.environ['MYSQL_DATABASE'] = os.environ.get('MYSQL_DATABASE', 'quantdb')

def test_database_manager():
    """测试数据库管理器"""
    try:
        print("测试数据库管理器...")
        from src.data.database import DatabaseManager
        db_manager = DatabaseManager()
        print("✓ 数据库管理器初始化成功")
        print(f"  数据库URL: {db_manager.config.database_url[:50]}...")
        return True
    except Exception as e:
        print(f"❌ 数据库管理器测试失败: {e}")
        traceback.print_exc()
        return False

def test_tushare_client():
    """测试Tushare客户端"""
    try:
        print("测试Tushare客户端...")
        from src.data.tushare_client import TushareClient
        client = TushareClient()
        print("✓ Tushare客户端初始化成功")
        print(f"  Token前缀: {client.token[:10] if client.token else 'None'}...")
        return True
    except Exception as e:
        print(f"❌ Tushare客户端测试失败: {e}")
        traceback.print_exc()
        return False

def test_web_app():
    """测试Web应用"""
    try:
        print("测试Web应用...")
        from src.monitor.web_app import create_app
        app = create_app()
        print("✓ Web应用创建成功")
        print(f"  Debug模式: {app.config.get('DEBUG')}")
        return True
    except Exception as e:
        print(f"❌ Web应用测试失败: {e}")
        traceback.print_exc()
        return False

def main():
    print("=== 验证配置更新结果 ===\n")
    
    results = []
    results.append(test_database_manager())
    results.append(test_tushare_client())
    results.append(test_web_app())
    
    print(f"\n=== 测试结果 ===")
    print(f"通过: {sum(results)}/{len(results)}")
    
    if all(results):
        print("✓ 所有配置更新成功")
        return True
    else:
        print("❌ 部分配置更新失败")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)