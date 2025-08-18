# -*- coding: utf-8 -*-
"""
量化交易系统配置模块统一入口
Quantitative Trading System Configuration Module Unified Entry Point

新架构特点：
- 统一配置管理器：config_manager.py作为唯一配置管理入口
- YAML配置文件：所有配置存储在schemas/目录的YAML文件中
- 环境变量支持：通过.env文件管理敏感信息
- 简洁架构：只包含必要的配置文件和管理器

使用示例：
    from quant_system.config import config_manager, get_config
    
    # 获取数据库配置
    db_config = get_mysql_config()
    
    # 获取特定配置值
    mysql_host = get_config('databases.mysql.host', config_type='database')
    
    # 获取API配置
    api_config = get_api_config()
"""

from .config_manager import (
    ConfigManager,
    get_config_manager,
    get_config,
    # 四层存储架构配置
    get_mysql_config,
    get_clickhouse_config,
    get_redis_config,
    get_minio_config,
    # 业务模块配置
    get_trading_config,
    get_data_integrity_config,
    # Schema配置
    get_schema_config,
    # 原有配置
    get_api_config,
    get_cache_config,
    get_storage_config,
    get_storage_layer_config,
    reload_config
)

# 创建全局配置管理器实例
config_manager = get_config_manager()

# 便捷函数 - 四层存储架构配置
def get_mysql_config():
    """获取MySQL配置（结构化数据层）"""
    return config_manager.get_mysql_config()

def get_clickhouse_config():
    """获取ClickHouse配置（分析层）"""
    return config_manager.get_clickhouse_config()

def get_redis_config():
    """获取Redis配置（缓存层）"""
    return config_manager.get_redis_config()

def get_minio_config():
    """获取MinIO配置（对象存储层）"""
    return config_manager.get_minio_config()

# 便捷函数 - 业务模块配置
def get_trading_config():
    """获取交易配置"""
    return config_manager.get_trading_config()

def get_data_integrity_config():
    """获取数据完整性配置"""
    return config_manager.get_data_integrity_config()


def get_api_config():
    """获取API配置"""
    return config_manager.get_api_config()

def get_cache_config():
    """获取缓存配置"""
    return config_manager.get_cache_config()

def get_logging_config():
    """获取日志配置"""
    return config_manager.get_logging_config()

def get_system_config():
    """获取系统配置"""
    return config_manager.get_system_config()

def get_data_config():
    """获取数据配置"""
    return config_manager.get_data_config()

# 新架构 - Schema配置获取
def get_schema_config(engine: str):
    """获取Schema配置"""
    return config_manager.get_schema_config(engine)

# 便捷函数 - 获取特定配置值
def get_config(key: str, default=None, config_type: str = None):
    """获取配置值的便捷函数
    
    Args:
        key: 配置键，支持点分隔的嵌套键 (如: 'databases.mysql.host')
        default: 默认值
        config_type: 配置类型 ('database', 'api', 'cache', 'logging', 'trading', 'system', 'data')
    
    Returns:
        配置值
    
    Examples:
        # 获取数据库主机
        mysql_host = get_config('databases.mysql.host', config_type='database')
        
        # 获取日志级别
        log_level = get_config('level', config_type='logging')
        
        # 获取Tushare令牌
        tushare_token = get_config('data_sources.tushare.token', config_type='api')
        
        # 从所有配置中搜索
        value = get_config('some.nested.key')
    """
    return config_manager.get(key, default, config_type)

# 配置管理函数
def reload_config():
    """重新加载所有配置"""
    config_manager.reload_all_configs()

def load_all_configs():
    """加载所有配置（初始化时调用）"""
    config_manager.load_all_configs()

def get_all_configs():
    """获取所有配置的字典"""
    return {
        'database': get_mysql_config(),
        'api': get_api_config(),
        'cache': get_cache_config(),
        'logging': get_logging_config(),
        'trading': get_trading_config(),
        'system': get_system_config(),
        'data': get_data_config()
    }

# 向后兼容性函数
def get_data_config_legacy(key: str = None, default=None):
    """获取数据模块配置的便捷函数（向后兼容）"""
    if key:
        return config_manager.get(key, default, 'data')
    return config_manager.get_data_config()

def get_logging_config_legacy(key: str = None, default=None):
    """获取日志配置的便捷函数（向后兼容）"""
    if key:
        return config_manager.get(key, default, 'logging')
    return config_manager.get_logging_config()

def get_api_config_legacy(key: str = None, default=None):
    """获取API配置的便捷函数（向后兼容）"""
    if key:
        return config_manager.get(key, default, 'api')
    return config_manager.get_api_config()

def get_system_config_legacy(key: str = None, default=None):
    """获取系统配置的便捷函数（向后兼容）"""
    if key:
        return config_manager.get(key, default, 'system')
    return config_manager.get_system_config()

# 为测试兼容性创建config别名
config = config_manager

# 导出的公共接口
__all__ = [
    # 主要配置管理器
    "ConfigManager",
    "config_manager",
    "config",  # 添加config别名
    
    # 新架构：四层存储配置函数
    "get_mysql_config",
    "get_clickhouse_config",
    "get_redis_config",
    "get_minio_config",
    
    # 新架构：业务模块配置函数
    "get_trading_config",
    "get_data_integrity_config",
    
    # 新架构：Schema配置函数
    "get_schema_config",
    
    # 向后兼容：原有配置获取函数
    "get_api_config",
    "get_cache_config",
    "get_logging_config",
    "get_system_config",
    "get_data_config",
    "get_config",
    "get_all_configs",
    "get_storage_config",
    "get_storage_layer_config",
    
    # 配置管理函数
    "reload_config",
    "load_all_configs",
    
    # 向后兼容函数
    "get_data_config_legacy",
    "get_logging_config_legacy",
    "get_api_config_legacy",
    "get_system_config_legacy",
]