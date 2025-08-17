"""
配置模块初始化
"""
from .settings import get_config, Config, DevelopmentConfig, ProductionConfig, TestingConfig

__all__ = [
    'get_config',
    'Config', 
    'DevelopmentConfig',
    'ProductionConfig', 
    'TestingConfig'
]