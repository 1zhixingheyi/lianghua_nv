"""
数据采集系统主文件

简化的数据采集功能演示
"""

import os
import sys
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入配置
try:
    from config.config_manager import get_config_manager
except ImportError:
    logger.error("无法导入配置模块，请确保config/settings.py存在")
    sys.exit(1)


class SimpleTushareClient:
    """简化的Tushare客户端"""
    
    def __init__(self):
        config_manager = get_config_manager()
        api_config = config_manager.get_api_config('tushare')
        self.token = api_config.get('token', os.getenv('TUSHARE_TOKEN', '')) if api_config else os.getenv('TUSHARE_TOKEN', '')
        
        if not self.token:
            logger.warning("未配置TUSHARE_TOKEN，将使用模拟数据")
            self.pro = None
        else:
            try:
                import tushare as ts
                ts.set_token(self.token)
                self.pro = ts.pro_api()
                logger.info("Tushare客户端初始化成功")
            except ImportError:
                logger.error("未安装tushare包，请运行: pip install tushare")
                self.pro = None
    
    def get_mock_stock_data(self) -> pd.DataFrame:
        """获取模拟股票数据"""
        return pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ', '600000.SH', '600036.SH', '000858.SZ'],
            'symbol': ['000001', '000002', '600000', '600036', '000858'],
            'name': ['平安银行', '万科A', '浦发银行', '招商银行', '五粮液'],
            'area': ['深圳', '深圳', '上海', '上海', '四川'],
            'industry': ['银行', '房地产', '银行', '银行', '酿酒行业'],
            'market': ['主板', '主板', '主板', '主板', '主板'],
            'list_date': [pd.Timestamp('1991-04-03'), pd.Timestamp('1991-01-29'), 
                         pd.Timestamp('1999-11-10'), pd.Timestamp('2002-04-09'),
                         pd.Timestamp('1998-04-27')],
            'is_hs': ['N', 'H', 'N', 'N', 'N']
        })
    
    def get_mock_daily_data(self, ts_code: str) -> pd.DataFrame:
        """获取模拟日线数据"""
        dates = pd.date_range(start='2024-01-01', periods=20, freq='B')  # 工作日
        base_price = 10.0 + len(ts_code) % 10  # 根据股票代码生成不同基础价格
        
        data = []
        for i, date in enumerate(dates):
            price_change = (i % 5 - 2) * 0.1  # 模拟价格波动
            open_price = base_price + price_change
            high_price = open_price + 0.2
            low_price = open_price - 0.1
            close_price = open_price + 0.05
            
            data.append({
                'ts_code': ts_code,
                'trade_date': date,
                'open_price': round(open_price, 2),
                'high_price': round(high_price, 2),
                'low_price': round(low_price, 2),
                'close_price': round(close_price, 2),
                'pre_close': round(open_price - 0.05, 2),
                'change_pct': round((close_price - open_price + 0.05) / (open_price - 0.05) * 100, 2),
                'vol': 1000000 + i * 100000,
                'amount': round((open_price + close_price) / 2 * (1000000 + i * 100000), 2)
            })
        
        return pd.DataFrame(data)


class SimpleDatabase:
    """简化的数据库管理器"""
    
    def __init__(self):
        self.config = get_config_manager()
        self.engine = None
        self._test_connection()
    
    def _test_connection(self):
        """测试数据库连接"""
        try:
            from sqlalchemy import create_engine, text
            db_url = self.config.database_url
            self.engine = create_engine(db_url, echo=False)
            
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            logger.info("数据库连接成功")
            return True
            
        except Exception as e:
            logger.error(f"数据库连接失败: {str(e)}")
            logger.info("将使用文件模式保存数据")
            self.engine = None
            return False
    
    def save_to_database(self, df: pd.DataFrame, table_name: str) -> bool:
        """保存数据到数据库"""
        if self.engine is None:
            return self.save_to_file(df, table_name)
        
        try:
            df.to_sql(table_name, self.engine, if_exists='replace', index=False)
            logger.info(f"数据已保存到数据库表: {table_name}, {len(df)} 行")
            return True
        except Exception as e:
            logger.error(f"保存到数据库失败: {str(e)}")
            return self.save_to_file(df, table_name)
    
    def save_to_file(self, df: pd.DataFrame, table_name: str) -> bool:
        """保存数据到文件"""
        try:
            os.makedirs('data_output', exist_ok=True)
            file_path = f'data_output/{table_name}.csv'
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            logger.info(f"数据已保存到文件: {file_path}, {len(df)} 行")
            return True
        except Exception as e:
            logger.error(f"保存到文件失败: {str(e)}")
            return False


def demo_data_collection():
    """演示数据采集功能"""
    logger.info("=== 开始数据采集演示 ===")
    
    # 初始化客户端和数据库
    client = SimpleTushareClient()
    db = SimpleDatabase()
    
    # 获取股票基础信息
    logger.info("1. 获取股票基础信息...")
    stock_data = client.get_mock_stock_data()
    logger.info(f"获取到 {len(stock_data)} 只股票信息")
    print("\n股票信息示例:")
    print(stock_data.head())
    
    # 保存股票基础信息
    if db.save_to_database(stock_data, 'stock_basic'):
        logger.info("✓ 股票基础信息保存成功")
    else:
        logger.error("✗ 股票基础信息保存失败")
    
    # 获取日线数据
    logger.info("\n2. 获取日线数据...")
    all_daily_data = []
    
    for _, stock in stock_data.head(3).iterrows():  # 只处理前3只股票
        ts_code = stock['ts_code']
        logger.info(f"获取 {ts_code} ({stock['name']}) 的日线数据")
        
        daily_data = client.get_mock_daily_data(ts_code)
        all_daily_data.append(daily_data)
    
    # 合并所有日线数据
    combined_daily = pd.concat(all_daily_data, ignore_index=True)
    logger.info(f"获取到 {len(combined_daily)} 条日线数据")
    print("\n日线数据示例:")
    print(combined_daily.head())
    
    # 保存日线数据
    if db.save_to_database(combined_daily, 'daily_quotes'):
        logger.info("✓ 日线数据保存成功")
    else:
        logger.error("✗ 日线数据保存失败")
    
    # 数据统计
    logger.info("\n=== 数据采集统计 ===")
    logger.info(f"股票数量: {len(stock_data)}")
    logger.info(f"日线记录数: {len(combined_daily)}")
    logger.info(f"数据日期范围: {combined_daily['trade_date'].min()} 到 {combined_daily['trade_date'].max()}")
    
    # 行业分布
    industry_count = stock_data['industry'].value_counts()
    logger.info(f"行业分布: {dict(industry_count)}")
    
    logger.info("=== 数据采集演示完成 ===")


def test_system_components():
    """测试系统组件"""
    logger.info("=== 测试系统组件 ===")
    
    results = []
    
    # 测试配置加载
    try:
        config = get_config_manager()
        logger.info("✓ 配置文件加载成功")
        logger.info(f"数据库: {config.MYSQL_DATABASE}")
        logger.info(f"Tushare Token: {'已配置' if config.TUSHARE_TOKEN else '未配置'}")
        results.append(("配置加载", True))
    except Exception as e:
        logger.error(f"✗ 配置文件加载失败: {str(e)}")
        results.append(("配置加载", False))
    
    # 测试数据库连接
    try:
        db = SimpleDatabase()
        results.append(("数据库连接", db.engine is not None))
    except Exception as e:
        logger.error(f"✗ 数据库测试失败: {str(e)}")
        results.append(("数据库连接", False))
    
    # 测试Tushare客户端
    try:
        client = SimpleTushareClient()
        results.append(("Tushare客户端", client.pro is not None))
    except Exception as e:
        logger.error(f"✗ Tushare客户端测试失败: {str(e)}")
        results.append(("Tushare客户端", False))
    
    # 输出测试结果
    logger.info("\n=== 测试结果 ===")
    success_count = 0
    for test_name, success in results:
        status = "✓ 通过" if success else "✗ 失败"
        logger.info(f"{test_name}: {status}")
        if success:
            success_count += 1
    
    logger.info(f"\n测试完成: {success_count}/{len(results)} 个测试通过")
    return success_count == len(results)


def main():
    """主函数"""
    print("=" * 60)
    print("           凉花VN 数据采集系统 MVP")
    print("=" * 60)
    
    # 检查依赖
    required_packages = ['pandas', 'sqlalchemy', 'pymysql']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(f"缺少依赖包: {missing_packages}")
        logger.info("请运行: pip install " + " ".join(missing_packages))
        return
    
    # 运行测试
    logger.info("开始系统测试...")
    if test_system_components():
        logger.info("✅ 系统测试通过，开始数据采集演示")
        demo_data_collection()
    else:
        logger.warning("⚠️ 部分测试失败，但仍将运行演示")
        demo_data_collection()
    
    print("\n" + "=" * 60)
    print("数据采集系统演示完成！")
    print("数据已保存到 data_output/ 目录或数据库中")
    print("=" * 60)


if __name__ == "__main__":
    main()