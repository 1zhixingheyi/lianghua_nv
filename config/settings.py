"""
量化交易系统MVP配置文件
"""
import os
from typing import Optional
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    """基础配置类"""
    
    # 数据库配置
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
    MYSQL_USER = os.getenv('MYSQL_USER', 'quant')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'quant123')
    MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'quantdb')
    
    # Redis配置
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)
    
    # Tushare配置
    TUSHARE_TOKEN = os.getenv('TUSHARE_TOKEN', '')
    
    # 交易配置
    INITIAL_CAPITAL = float(os.getenv('INITIAL_CAPITAL', 100000))  # 初始资金
    COMMISSION_RATE = float(os.getenv('COMMISSION_RATE', 0.0003))  # 手续费率
    
    # 风控配置
    MAX_POSITION_RATIO = float(os.getenv('MAX_POSITION_RATIO', 0.95))  # 最大仓位比例
    STOP_LOSS_RATIO = float(os.getenv('STOP_LOSS_RATIO', 0.05))  # 止损比例
    STOP_PROFIT_RATIO = float(os.getenv('STOP_PROFIT_RATIO', 0.15))  # 止盈比例
    
    # 日志配置
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_DIR = os.getenv('LOG_DIR', 'logs')
    
    # QMT配置
    QMT_HOST = os.getenv('QMT_HOST', 'localhost')
    QMT_PORT = int(os.getenv('QMT_PORT', 58610))
    QMT_ACCOUNT = os.getenv('QMT_ACCOUNT', '')
    
    @property
    def database_url(self) -> str:
        """数据库连接URL"""
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
    
    @property
    def redis_url(self) -> str:
        """Redis连接URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    TESTING = False


class TestingConfig(Config):
    """测试环境配置"""
    DEBUG = True
    TESTING = True
    MYSQL_DATABASE = 'quantdb_test'


# 配置映射
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(config_name: Optional[str] = None) -> Config:
    """获取配置对象"""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')
    return config_map.get(config_name, DevelopmentConfig)()