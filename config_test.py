#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置系统兼容性验证脚本
"""

import sys
import os
import pathlib
import traceback
from typing import List, Dict, Any

def check_dependencies() -> Dict[str, bool]:
    """检查依赖模块"""
    deps = {}
    
    # 检查yaml
    try:
        import yaml
        deps['yaml'] = True
        print("✅ PyYAML模块可用")
    except ImportError as e:
        deps['yaml'] = False
        print(f"❌ PyYAML模块缺失: {e}")
    
    # 检查dotenv
    try:
        from dotenv import load_dotenv
        deps['dotenv'] = True
        print("✅ python-dotenv模块可用")
    except ImportError as e:
        deps['dotenv'] = False
        print(f"❌ python-dotenv模块缺失: {e}")
    
    return deps

def check_file_structure() -> Dict[str, bool]:
    """检查文件结构"""
    structure = {}
    
    # 检查配置目录
    config_dir = pathlib.Path('config')
    structure['config_dir'] = config_dir.exists()
    print(f"📁 配置目录存在: {structure['config_dir']}")
    
    if config_dir.exists():
        # 检查子目录
        schemas_dir = config_dir / 'schemas'
        modules_dir = config_dir / 'modules'
        
        structure['schemas_dir'] = schemas_dir.exists()
        structure['modules_dir'] = modules_dir.exists()
        
        print(f"  - schemas目录: {structure['schemas_dir']}")
        print(f"  - modules目录: {structure['modules_dir']}")
        
        # 检查关键配置文件
        key_files = {
            'mysql.yaml': (schemas_dir / 'mysql.yaml').exists(),
            'redis.yaml': (schemas_dir / 'redis.yaml').exists(),
            'trading.yaml': (modules_dir / 'trading.yaml').exists(),
            'data_integrity.yaml': (modules_dir / 'data_integrity.yaml').exists()
        }
        
        structure.update(key_files)
        
        print("🔍 关键配置文件检查:")
        for file, exists in key_files.items():
            print(f"  - {file}: {'✅' if exists else '❌'}")
    
    # 检查.env文件
    env_file = pathlib.Path('.env')
    structure['env_file'] = env_file.exists()
    print(f"📄 .env文件存在: {structure['env_file']}")
    
    return structure

def test_config_manager_import():
    """测试配置管理器导入"""
    try:
        # 添加当前目录到Python路径
        sys.path.insert(0, '.')
        
        from config.config_manager import ConfigManager
        print("✅ ConfigManager导入成功")
        return True
    except Exception as e:
        print(f"❌ ConfigManager导入失败: {e}")
        traceback.print_exc()
        return False

def test_config_manager_initialization():
    """测试配置管理器初始化"""
    try:
        sys.path.insert(0, '.')
        from config.config_manager import ConfigManager
        
        # 实例化配置管理器
        config_manager = ConfigManager()
        print("✅ ConfigManager实例化成功")
        
        # 检查配置加载状态
        loaded_configs = list(config_manager._config_cache.keys())
        print(f"📁 已加载的配置类型: {loaded_configs}")
        
        return config_manager, loaded_configs
        
    except Exception as e:
        print(f"❌ ConfigManager初始化失败: {e}")
        traceback.print_exc()
        return None, []

def test_config_methods(config_manager):
    """测试配置方法"""
    results = {}
    
    try:
        # 测试四层存储配置
        print("🔍 验证四层存储配置:")
        
        mysql_config = config_manager.get_mysql_config()
        results['mysql'] = bool(mysql_config)
        print(f"  - MySQL配置: {'✅ 存在' if mysql_config else '❌ 缺失'}")
        
        redis_config = config_manager.get_redis_config()
        results['redis'] = bool(redis_config)
        print(f"  - Redis配置: {'✅ 存在' if redis_config else '❌ 缺失'}")
        
        clickhouse_config = config_manager.get_clickhouse_config()
        results['clickhouse'] = bool(clickhouse_config)
        print(f"  - ClickHouse配置: {'✅ 存在' if clickhouse_config else '❌ 缺失'}")
        
        minio_config = config_manager.get_minio_config()
        results['minio'] = bool(minio_config)
        print(f"  - MinIO配置: {'✅ 存在' if minio_config else '❌ 缺失'}")
        
        # 测试业务模块配置
        print("🎯 验证业务模块配置:")
        
        trading_config = config_manager.get_trading_config()
        results['trading'] = bool(trading_config)
        print(f"  - Trading配置: {'✅ 存在' if trading_config else '❌ 缺失'}")
        
        data_integrity_config = config_manager.get_data_integrity_config()
        results['data_integrity'] = bool(data_integrity_config)
        print(f"  - Data Integrity配置: {'✅ 存在' if data_integrity_config else '❌ 缺失'}")
        
        # 配置验证
        print("🔧 配置验证:")
        is_valid, errors = config_manager.validate()
        results['validation'] = is_valid
        print(f"  - 配置验证: {'✅ 通过' if is_valid else '❌ 失败'}")
        
        if errors:
            print("❌ 配置错误:")
            for error in errors:
                print(f"    - {error}")
        
        return results
        
    except Exception as e:
        print(f"❌ 配置方法测试失败: {e}")
        traceback.print_exc()
        return {}

def main():
    """主测试函数"""
    print("=" * 60)
    print("🔍 量化交易系统配置兼容性验证")
    print("=" * 60)
    
    # 1. 检查依赖
    print("\n1️⃣ 检查依赖模块:")
    deps = check_dependencies()
    
    # 2. 检查文件结构
    print("\n2️⃣ 检查文件结构:")
    structure = check_file_structure()
    
    # 3. 测试配置管理器导入
    print("\n3️⃣ 测试配置管理器导入:")
    import_success = test_config_manager_import()
    
    if not import_success:
        print("❌ 配置管理器导入失败，无法继续测试")
        return
    
    # 4. 测试配置管理器初始化
    print("\n4️⃣ 测试配置管理器初始化:")
    config_manager, loaded_configs = test_config_manager_initialization()
    
    if not config_manager:
        print("❌ 配置管理器初始化失败，无法继续测试")
        return
    
    # 5. 测试配置方法
    print("\n5️⃣ 测试配置方法:")
    method_results = test_config_methods(config_manager)
    
    # 6. 总结报告
    print("\n" + "=" * 60)
    print("📊 验证结果总结:")
    print("=" * 60)
    
    # 依赖检查结果
    print("🔧 依赖模块:")
    for dep, status in deps.items():
        print(f"  - {dep}: {'✅' if status else '❌'}")
    
    # 文件结构检查结果
    print("📁 文件结构:")
    critical_files = ['config_dir', 'schemas_dir', 'modules_dir', 'env_file']
    for file in critical_files:
        if file in structure:
            print(f"  - {file}: {'✅' if structure[file] else '❌'}")
    
    # 配置方法测试结果
    print("⚙️ 配置功能:")
    for method, status in method_results.items():
        print(f"  - {method}: {'✅' if status else '❌'}")
    
    # 整体评估
    print("\n🎯 整体评估:")
    
    critical_issues = []
    if not all(deps.values()):
        critical_issues.append("依赖模块缺失")
    if not all(structure[f] for f in critical_files if f in structure):
        critical_issues.append("关键文件缺失")
    if not method_results.get('validation', False):
        critical_issues.append("配置验证失败")
    
    if critical_issues:
        print("❌ 发现关键问题:")
        for issue in critical_issues:
            print(f"  - {issue}")
        print("\n❗ 建议：需要解决上述问题才能确保系统正常运行")
    else:
        print("✅ 配置系统兼容性验证通过")
        print("✅ 系统可以正常运行")

if __name__ == "__main__":
    main()