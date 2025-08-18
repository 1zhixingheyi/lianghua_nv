"""
数据库操作管理器

提供数据库连接、CRUD操作、批量导入等功能
"""

import logging
import pandas as pd
from sqlalchemy import create_engine, text, MetaData
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, List, Dict, Any
from datetime import datetime

from src.config.settings import get_config

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, config_name: Optional[str] = None):
        """
        初始化数据库管理器
        
        Args:
            config_name: 配置名称，如果为None则使用默认配置
        """
        self.config = get_config(config_name)
        self.engine = None
        self.session_factory = None
        self.metadata = None
        
        self._create_engine()
        logger.info("数据库管理器初始化成功")
    
    def _create_engine(self):
        """创建数据库引擎"""
        try:
            # 使用配置类的database_url属性
            db_url = self.config.database_url
            
            # 创建引擎
            self.engine = create_engine(
                db_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False  # 设为True可以看到SQL语句
            )
            
            # 创建会话工厂
            self.session_factory = sessionmaker(bind=self.engine)
            
            # 创建元数据对象
            self.metadata = MetaData()
            
            # 测试连接
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            logger.info("数据库连接创建成功")
            
        except Exception as e:
            logger.error(f"创建数据库连接失败: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"数据库连接测试失败: {str(e)}")
            return False
    
    def bulk_insert_dataframe(self, df: pd.DataFrame, table_name: str, 
                            if_exists: str = 'append', index: bool = False) -> bool:
        """
        批量插入DataFrame数据
        
        Args:
            df: 要插入的DataFrame
            table_name: 目标表名
            if_exists: 如果表存在的处理方式 ('fail', 'replace', 'append')
            index: 是否插入索引
            
        Returns:
            插入是否成功
        """
        if df is None or df.empty:
            logger.warning(f"DataFrame为空，跳过插入到表: {table_name}")
            return True
        
        try:
            # 批量插入数据
            df.to_sql(
                name=table_name,
                con=self.engine,
                if_exists=if_exists,
                index=index,
                method='multi',
                chunksize=1000
            )
            
            logger.info(f"批量插入成功: {table_name}, 插入 {len(df)} 行数据")
            return True
            
        except Exception as e:
            logger.error(f"批量插入失败: {table_name}, 错误: {str(e)}")
            return False
    
    def query_dataframe(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Optional[pd.DataFrame]:
        """
        查询数据并返回DataFrame
        
        Args:
            sql: 查询SQL语句
            params: 参数字典
            
        Returns:
            查询结果DataFrame
        """
        try:
            df = pd.read_sql(sql, self.engine, params=params)
            logger.debug(f"查询成功，返回 {len(df)} 行数据")
            return df
            
        except Exception as e:
            logger.error(f"查询失败: {sql}, 错误: {str(e)}")
            return None
    
    def check_table_exists(self, table_name: str) -> bool:
        """
        检查表是否存在
        
        Args:
            table_name: 表名
            
        Returns:
            表是否存在
        """
        try:
            sql = """
            SELECT COUNT(*) as count 
            FROM information_schema.tables 
            WHERE table_schema = :database_name AND table_name = :table_name
            """
            
            result = self.query_dataframe(sql, {
                'database_name': self.config.MYSQL_DATABASE,
                'table_name': table_name
            })
            
            return result is not None and result['count'].iloc[0] > 0
            
        except Exception as e:
            logger.error(f"检查表存在性失败: {table_name}, 错误: {str(e)}")
            return False
    
    def get_table_row_count(self, table_name: str) -> int:
        """
        获取表的行数
        
        Args:
            table_name: 表名
            
        Returns:
            行数
        """
        try:
            sql = f"SELECT COUNT(*) as count FROM {table_name}"
            result = self.query_dataframe(sql)
            
            if result is not None and not result.empty:
                return int(result['count'].iloc[0])
            
            return 0
            
        except Exception as e:
            logger.error(f"获取表行数失败: {table_name}, 错误: {str(e)}")
            return 0


# 单例模式，全局共享数据库管理器实例
_database_manager = None

def get_database_manager(config_name: Optional[str] = None) -> DatabaseManager:
    """获取数据库管理器单例"""
    global _database_manager
    if _database_manager is None:
        _database_manager = DatabaseManager(config_name)
    return _database_manager