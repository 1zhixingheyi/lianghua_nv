#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Redis配置问题诊断脚本
"""

import sys
import traceback

def debug_redis_config():
    """诊断Redis配置问题"""
    print("🔍 诊断Redis配置问题...")
    
    try:
        sys.path.insert(0, '.')
        from config.config_manager import ConfigManager
        
        config_manager = ConfigManager()
        redis_config = config_manager.get_redis_config()
        
        print(f"Redis配置类型: {type(redis_config)}")
        print(f"Redis配置内容: {redis_config}")
        
        # 检查database字段
        if 'database' in redis_config:
            database_field = redis_config['database']
            print(f"\\nDatabase字段类型: {type(database_field)}")
            print(f"Database字段内容: {database_field}")
            
            # 如果database是字典，检查其内容
            if isinstance(database_field, dict):
                print("Database字段是字典，包含:")
                for key, value in database_field.items():
                    print(f"  - {key}: {value} ({type(value)})")
            else:
                print(f"❌ Database字段不是字典，而是: {type(database_field)}")
        
        # 检查Redis配置的其他字段
        print("\\nRedis配置结构:")
        for key, value in redis_config.items():
            print(f"  - {key}: {type(value)}")
        
        return redis_config
        
    except Exception as e:
        print(f"❌ Redis配置诊断失败: {e}")
        traceback.print_exc()
        return None

def check_redis_yaml_content():
    """检查Redis YAML文件内容"""
    print("\\n📄 检查Redis YAML文件内容...")
    
    try:
        import yaml
        
        with open('config/schemas/redis.yaml', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 查找database字段定义
        lines = content.split('\n')
        database_section = []
        in_database_section = False
        
        for i, line in enumerate(lines):
            if line.strip().startswith('database:'):
                in_database_section = True
                database_section.append(f"{i+1}: {line}")
            elif in_database_section:
                if line.startswith('  ') or line.strip() == '':
                    database_section.append(f"{i+1}: {line}")
                else:
                    break
        
        print("Database部分内容:")
        for line in database_section:
            print(f"  {line}")
            
        # 解析YAML内容
        try:
            parsed_yaml = yaml.safe_load(content)
            database_config = parsed_yaml.get('database')
            print(f"\\n解析后的database字段: {database_config}")
            print(f"Database字段类型: {type(database_config)}")
        except Exception as e:
            print(f"❌ YAML解析失败: {e}")
            
    except Exception as e:
        print(f"❌ 读取Redis YAML文件失败: {e}")

def test_environment_variable_replacement():
    """测试环境变量替换"""
    print("\\n🔧 测试环境变量替换...")
    
    import os
    print("相关环境变量:")
    env_vars = ['REDIS_HOST', 'REDIS_PORT', 'REDIS_PASSWORD', 'REDIS_DB']
    for var in env_vars:
        value = os.getenv(var)
        print(f"  - {var}: {value if value is not None else '未设置'}")

def main():
    """主函数"""
    print("=" * 60)
    print("🔍 Redis配置问题诊断")
    print("=" * 60)
    
    # 诊断Redis配置
    redis_config = debug_redis_config()
    
    # 检查YAML文件内容
    check_redis_yaml_content()
    
    # 测试环境变量替换
    test_environment_variable_replacement()
    
    print("\n" + "=" * 60)
    print("📊 诊断总结:")
    print("=" * 60)
    
    if redis_config:
        print("✅ Redis配置加载成功")
        if isinstance(redis_config.get('database'), dict):
            print("✅ Database字段结构正确")
        else:
            print("❌ Database字段结构异常")
            print("💡 建议: 检查Redis YAML文件的database字段定义")
    else:
        print("❌ Redis配置加载失败")

if __name__ == "__main__":
    main()