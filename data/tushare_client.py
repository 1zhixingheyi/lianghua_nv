"""
Tushare API客户端封装

提供股票数据获取、重试机制、数据清洗等功能
"""

import time
import logging
import pandas as pd
import tushare as ts
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from config.settings import get_config

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TushareClient:
    """Tushare API客户端"""
    
    def __init__(self, token: Optional[str] = None):
        """
        初始化Tushare客户端
        
        Args:
            token: Tushare API token，如果为None则从配置文件读取
        """
        config = get_config()
        self.token = token or config.TUSHARE_TOKEN
        if not self.token:
            raise ValueError("Tushare token 未配置，请在.env文件中设置TUSHARE_TOKEN")
        
        # 设置token
        ts.set_token(self.token)
        self.pro = ts.pro_api()
        
        # API调用频率控制（每分钟最多200次）
        self.call_interval = 0.3  # 秒
        self.last_call_time = 0
        
        logger.info("Tushare客户端初始化成功")
    
    def _rate_limit(self):
        """API调用频率限制"""
        current_time = time.time()
        time_diff = current_time - self.last_call_time
        
        if time_diff < self.call_interval:
            sleep_time = self.call_interval - time_diff
            time.sleep(sleep_time)
        
        self.last_call_time = time.time()
    
    def _retry_api_call(self, func, max_retries: int = 3, **kwargs) -> Optional[pd.DataFrame]:
        """
        API调用重试机制
        
        Args:
            func: API调用函数
            max_retries: 最大重试次数
            **kwargs: API参数
            
        Returns:
            DataFrame或None
        """
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                result = func(**kwargs)
                
                if result is not None and not result.empty:
                    logger.debug(f"API调用成功: {func.__name__}")
                    return result
                else:
                    logger.warning(f"API返回空数据: {func.__name__}, 尝试 {attempt + 1}/{max_retries}")
                    
            except Exception as e:
                logger.error(f"API调用失败: {func.__name__}, 尝试 {attempt + 1}/{max_retries}, 错误: {str(e)}")
                
                if attempt < max_retries - 1:
                    # 指数退避
                    wait_time = 2 ** attempt
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"API调用最终失败: {func.__name__}")
                    return None
        
        return None
    
    def get_stock_basic(self, exchange: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        获取股票基础信息
        
        Args:
            exchange: 交易所代码 ('SSE', 'SZSE', None表示全部)
            
        Returns:
            包含股票基础信息的DataFrame
        """
        logger.info(f"获取股票基础信息, 交易所: {exchange or '全部'}")
        
        result = self._retry_api_call(
            self.pro.stock_basic,
            exchange=exchange,
            list_status='L',  # 只获取上市股票
            fields='ts_code,symbol,name,area,industry,market,list_date,is_hs'
        )
        
        if result is not None:
            # 数据清洗
            result = self._clean_stock_basic(result)
            logger.info(f"获取到 {len(result)} 只股票基础信息")
        
        return result
    
    def get_daily_data(self, ts_code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        获取股票日线行情数据
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            
        Returns:
            包含日线数据的DataFrame
        """
        logger.debug(f"获取日线数据: {ts_code}, {start_date} - {end_date}")
        
        result = self._retry_api_call(
            self.pro.daily,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            fields='ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount'
        )
        
        if result is not None:
            # 数据清洗
            result = self._clean_daily_data(result)
            logger.debug(f"获取到 {len(result)} 条日线数据")
        
        return result
    
    def get_trade_dates(self, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        获取交易日历
        
        Args:
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            
        Returns:
            包含交易日期的DataFrame
        """
        logger.debug(f"获取交易日历: {start_date} - {end_date}")
        
        result = self._retry_api_call(
            self.pro.trade_cal,
            exchange='',
            start_date=start_date,
            end_date=end_date,
            is_open='1'  # 只获取开市日期
        )
        
        return result
    
    def get_latest_trade_date(self) -> Optional[str]:
        """
        获取最新交易日期
        
        Returns:
            最新交易日期字符串 (YYYYMMDD)
        """
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=10)).strftime('%Y%m%d')
        
        trade_dates = self.get_trade_dates(start_date, end_date)
        
        if trade_dates is not None and not trade_dates.empty:
            return trade_dates['cal_date'].max()
        
        return None
    
    def _clean_stock_basic(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗股票基础信息数据，适配数据库表结构
        
        Args:
            df: 原始数据DataFrame
            
        Returns:
            清洗后的DataFrame
        """
        if df is None or df.empty:
            return df
        
        # 移除空值
        df = df.dropna(subset=['ts_code', 'name'])
        
        # 数据类型转换
        if 'list_date' in df.columns:
            df['list_date'] = pd.to_datetime(df['list_date'], format='%Y%m%d', errors='coerce')
        
        return df
    
    def _clean_daily_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗日线数据，适配数据库表结构
        
        Args:
            df: 原始数据DataFrame
            
        Returns:
            清洗后的DataFrame
        """
        if df is None or df.empty:
            return df
        
        # 移除空值和异常值
        df = df.dropna(subset=['ts_code', 'trade_date', 'close'])
        
        # 价格数据不能为负数或0
        price_columns = ['open', 'high', 'low', 'close', 'pre_close']
        for col in price_columns:
            if col in df.columns:
                df = df[df[col] > 0]
        
        # 成交量不能为负数
        if 'vol' in df.columns:
            df = df[df['vol'] >= 0]
        
        # 数据类型转换
        if 'trade_date' in df.columns:
            df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d', errors='coerce')
        
        # 重命名列以适配数据库表结构 (daily_quotes表)
        column_mapping = {
            'open': 'open_price',
            'high': 'high_price', 
            'low': 'low_price',
            'close': 'close_price',
            'pct_chg': 'change_pct'
        }
        
        df = df.rename(columns=column_mapping)
        
        # 按日期排序
        df = df.sort_values('trade_date')
        
        return df
    
    def validate_data(self, df: pd.DataFrame, data_type: str) -> bool:
        """
        验证数据完整性
        
        Args:
            df: 待验证的DataFrame
            data_type: 数据类型 ('stock_basic', 'daily')
            
        Returns:
            验证结果
        """
        if df is None or df.empty:
            logger.warning(f"数据验证失败: {data_type} - 数据为空")
            return False
        
        if data_type == 'stock_basic':
            required_columns = ['ts_code', 'name']
        elif data_type == 'daily':
            required_columns = ['ts_code', 'trade_date', 'close_price']
        else:
            logger.warning(f"不支持的数据类型: {data_type}")
            return False
        
        # 检查必需列是否存在
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logger.warning(f"数据验证失败: {data_type} - 缺少列: {missing_columns}")
            return False
        
        # 检查数据行数
        if len(df) == 0:
            logger.warning(f"数据验证失败: {data_type} - 无有效数据行")
            return False
        
        logger.info(f"数据验证成功: {data_type} - {len(df)} 行数据")
        return True


# 单例模式，全局共享客户端实例
_tushare_client = None

def get_tushare_client() -> TushareClient:
    """获取Tushare客户端单例"""
    global _tushare_client
    if _tushare_client is None:
        _tushare_client = TushareClient()
    return _tushare_client