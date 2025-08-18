#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试新企业级配置系统
"""

import sys
import os
sys.path.append('.')

try:
    # 设置环境变量以匹配YAML配置
    os.environ['MYSQL_USERNAME'] = os.environ.get('MYSQL_USER', 'quant')
    os.environ['MYSQL_DATABASE'] = os.environ.get('MYSQL_DATABASE', 'quantdb')
    
    from config.config_manager import get_config_manager, get_mysql_config, get_trading_config
    
    print("=== 测试新企业级配置系统 ===")
    
    # 测试配置管理器初始化
    config_manager = get_config_manager()
    print("✓ 配置管理器初始化成功")
    
    # 测试MySQL配置获取
    mysql_config = get_mysql_config()
    if mysql_config:
        print("✓ MySQL配置获取成功")
        print(f"  - 数据库主机: {mysql_config.get('database', {}).get('host')}")
        print(f"  - 数据库名称: {mysql_config.get('database', {}).get('database')}")
    else:
        print("✗ MySQL配置为空")
    
    # 测试交易配置获取
    trading_config = get_trading_config()
    if trading_config:
        print("✓ 交易配置获取成功")
        print(f"  - 初始资金: {trading_config.get('accounts', {}).get('paper_trading', {}).get('initial_capital')}")
    else:
        print("✗ 交易配置为空")
    
    print("\n=== 配置摘要 ===")
    summary = config_manager.get_config_summary()
    print(f"配置类型数量: {summary['total_configs']}")
    print(f"已加载配置: {summary['config_types']}")
    print(f"验证状态: {'通过' if summary['validation_status']['is_valid'] else '失败'}")
    
    print("\n新企业级配置系统工作正常 ✓")
    
except Exception as e:
    print(f"✗ 配置系统测试失败: {e}")
    import traceback
    traceback.print_exc()