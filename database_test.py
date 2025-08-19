#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库连接配置验证脚本
"""

import sys
import os
import traceback
from typing import Dict, Any, Optional

def test_mysql_connection_config():
    """测试MySQL连接配置"""
    print("🔍 测试MySQL连接配置...")
    
    try:
        sys.path.insert(0, '.')
        from config.config_manager import ConfigManager
        
        config_manager = ConfigManager()
        mysql_config = config_manager.get_mysql_config()
        
        if not mysql_config:
            print("❌ MySQL配置为空")
            return False
        
        # 检查数据库连接配置
        db_config = mysql_config.get('database', {})
        print(f"  - Host: {db_config.get('host', '未设置')}")
        print(f"  - Port: {db_config.get('port', '未设置')}")
        print(f"  - Username: {db_config.get('username', '未设置')}")
        print(f"  - Database: {db_config.get('database', '未设置')}")
        print(f"  - Password: {'***设置***' if db_config.get('password') else '未设置'}")
        
        # 检查环境变量映射
        print("\n🔧 检查环境变量映射:")
        env_vars = {
            'MYSQL_HOST': os.getenv('MYSQL_HOST'),
            'MYSQL_PORT': os.getenv('MYSQL_PORT'),
            'MYSQL_USER': os.getenv('MYSQL_USER'),
            'MYSQL_USERNAME': os.getenv('MYSQL_USERNAME'),
            'MYSQL_PASSWORD': os.getenv('MYSQL_PASSWORD'),
            'MYSQL_DATABASE': os.getenv('MYSQL_DATABASE')
        }
        
        for var_name, value in env_vars.items():
            status = "✅ 已设置" if value else "❌ 未设置"
            print(f"  - {var_name}: {status}")
        
        # 检查配置完整性
        required_fields = ['host', 'port', 'username', 'database']
        missing_fields = []
        for field in required_fields:
            if not db_config.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            print(f"❌ 缺少必要配置字段: {missing_fields}")
            return False
        
        print("✅ MySQL配置检查完成")
        return True
        
    except Exception as e:
        print(f"❌ MySQL配置测试失败: {e}")
        traceback.print_exc()
        return False

def test_redis_connection_config():
    """测试Redis连接配置"""
    print("\n🔍 测试Redis连接配置...")
    
    try:
        sys.path.insert(0, '.')
        from config.config_manager import ConfigManager
        
        config_manager = ConfigManager()
        redis_config = config_manager.get_redis_config()
        
        if not redis_config:
            print("❌ Redis配置为空")
            return False
        
        # 检查数据库连接配置
        db_config = redis_config.get('database', {})
        print(f"  - Host: {db_config.get('host', '未设置')}")
        print(f"  - Port: {db_config.get('port', '未设置')}")
        print(f"  - Database: {db_config.get('database', '未设置')}")
        print(f"  - Password: {'***设置***' if db_config.get('password') else '未设置'}")
        
        # 检查环境变量映射
        print("\n🔧 检查环境变量映射:")
        env_vars = {
            'REDIS_HOST': os.getenv('REDIS_HOST'),
            'REDIS_PORT': os.getenv('REDIS_PORT'),
            'REDIS_PASSWORD': os.getenv('REDIS_PASSWORD'),
            'REDIS_DB': os.getenv('REDIS_DB')
        }
        
        for var_name, value in env_vars.items():
            status = "✅ 已设置" if value is not None else "❌ 未设置"
            print(f"  - {var_name}: {status}")
        
        # 检查配置完整性
        required_fields = ['host', 'port']
        missing_fields = []
        for field in required_fields:
            if not db_config.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            print(f"❌ 缺少必要配置字段: {missing_fields}")
            return False
        
        print("✅ Redis配置检查完成")
        return True
        
    except Exception as e:
        print(f"❌ Redis配置测试失败: {e}")
        traceback.print_exc()
        return False

def check_env_variable_compatibility():
    """检查环境变量兼容性"""
    print("\n🔧 检查环境变量兼容性...")
    
    # .env文件中的实际变量 vs YAML文件中期望的变量
    compatibility_issues = []
    
    # MySQL变量兼容性检查
    mysql_mapping = {
        'MYSQL_USER': 'MYSQL_USERNAME',  # .env中是MYSQL_USER，但YAML期望MYSQL_USERNAME
    }
    
    print("MySQL环境变量兼容性:")
    for env_var, expected_var in mysql_mapping.items():
        env_value = os.getenv(env_var)
        expected_value = os.getenv(expected_var)
        
        if env_value and not expected_value:
            print(f"  ⚠️  发现兼容性问题: {env_var}={env_value}，但配置期望 {expected_var}")
            compatibility_issues.append(f"MySQL: {env_var} -> {expected_var}")
        elif env_value and expected_value:
            print(f"  ✅ {env_var} 和 {expected_var} 都已设置")
        else:
            print(f"  ❌ {env_var} 和 {expected_var} 都未设置")
    
    return compatibility_issues

def test_actual_database_connections():
    """测试实际的数据库连接（如果可能）"""
    print("\n🌐 测试实际数据库连接...")
    
    results = {}
    
    # 测试MySQL连接
    try:
        import pymysql
        
        sys.path.insert(0, '.')
        from config.config_manager import ConfigManager
        
        config_manager = ConfigManager()
        mysql_config = config_manager.get_mysql_config()
        db_config = mysql_config.get('database', {})
        
        if all(db_config.get(field) for field in ['host', 'port', 'username', 'password', 'database']):
            try:
                connection = pymysql.connect(
                    host=db_config['host'],
                    port=int(db_config['port']),
                    user=db_config['username'],
                    password=db_config['password'],
                    database=db_config['database'],
                    connect_timeout=5
                )
                connection.close()
                results['mysql'] = True
                print("  ✅ MySQL连接测试成功")
            except Exception as e:
                results['mysql'] = False
                print(f"  ❌ MySQL连接测试失败: {e}")
        else:
            results['mysql'] = False
            print("  ❌ MySQL配置不完整，跳过连接测试")
            
    except ImportError:
        results['mysql'] = None
        print("  ⚠️  PyMySQL未安装，跳过MySQL连接测试")
    except Exception as e:
        results['mysql'] = False
        print(f"  ❌ MySQL连接测试异常: {e}")
    
    # 测试Redis连接
    try:
        import redis
        
        redis_config = config_manager.get_redis_config()
        db_config = redis_config.get('database', {})
        
        if db_config.get('host') and db_config.get('port'):
            try:
                r = redis.Redis(
                    host=db_config['host'],
                    port=int(db_config['port']),
                    db=int(db_config.get('database', 0)),
                    password=db_config.get('password', None),
                    socket_timeout=5,
                    socket_connect_timeout=5
                )
                r.ping()
                results['redis'] = True
                print("  ✅ Redis连接测试成功")
            except Exception as e:
                results['redis'] = False
                print(f"  ❌ Redis连接测试失败: {e}")
        else:
            results['redis'] = False
            print("  ❌ Redis配置不完整，跳过连接测试")
            
    except ImportError:
        results['redis'] = None
        print("  ⚠️  redis-py未安装，跳过Redis连接测试")
    except Exception as e:
        results['redis'] = False
        print(f"  ❌ Redis连接测试异常: {e}")
    
    return results

def main():
    """主测试函数"""
    print("=" * 60)
    print("🔍 数据库连接配置验证")
    print("=" * 60)
    
    # 测试配置
    mysql_ok = test_mysql_connection_config()
    redis_ok = test_redis_connection_config()
    
    # 检查兼容性
    compatibility_issues = check_env_variable_compatibility()
    
    # 测试实际连接
    connection_results = test_actual_database_connections()
    
    # 总结报告
    print("\n" + "=" * 60)
    print("📊 数据库配置验证结果:")
    print("=" * 60)
    
    print("📋 配置检查:")
    print(f"  - MySQL配置: {'✅' if mysql_ok else '❌'}")
    print(f"  - Redis配置: {'✅' if redis_ok else '❌'}")
    
    print("\n🔧 兼容性检查:")
    if compatibility_issues:
        print("  ⚠️  发现兼容性问题:")
        for issue in compatibility_issues:
            print(f"    - {issue}")
    else:
        print("  ✅ 无兼容性问题")
    
    print("\n🌐 连接测试:")
    for db_type, result in connection_results.items():
        if result is True:
            print(f"  - {db_type.upper()}: ✅ 连接成功")
        elif result is False:
            print(f"  - {db_type.upper()}: ❌ 连接失败")
        else:
            print(f"  - {db_type.upper()}: ⚠️  跳过测试（驱动未安装）")
    
    # 整体评估
    print("\n🎯 整体评估:")
    
    critical_issues = []
    if not mysql_ok:
        critical_issues.append("MySQL配置问题")
    if not redis_ok:
        critical_issues.append("Redis配置问题")
    if compatibility_issues:
        critical_issues.append("环境变量兼容性问题")
    
    if critical_issues:
        print("❌ 发现问题:")
        for issue in critical_issues:
            print(f"  - {issue}")
        print("\n💡 建议：")
        if compatibility_issues:
            print("  - 修复环境变量名称不匹配问题")
            print("  - 更新.env文件中的变量名称或修改YAML配置")
    else:
        print("✅ 数据库配置验证通过")

if __name__ == "__main__":
    main()