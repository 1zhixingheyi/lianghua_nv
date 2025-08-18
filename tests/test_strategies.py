"""
策略框架测试脚本

测试策略框架的各个组件，包括策略信号生成、技术指标计算和与数据模块的集成
"""

import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入策略模块
try:
    from src.strategies import (
        get_strategy_manager, 
        MovingAverageCrossoverStrategy, 
        RSIStrategy,
        TechnicalIndicators,
        create_strategy_by_name,
        get_strategy_catalog
    )
    from src.data import get_database_manager, get_tushare_client
    from src.config.settings import get_config
except ImportError as e:
    logger.error(f"导入模块失败: {e}")
    sys.exit(1)


def generate_test_data(days: int = 100, start_price: float = 100.0) -> pd.DataFrame:
    """生成测试用的价格数据
    
    Args:
        days: 数据天数
        start_price: 起始价格
        
    Returns:
        测试数据DataFrame
    """
    dates = pd.date_range(start=datetime.now() - timedelta(days=days), 
                         end=datetime.now(), freq='D')
    
    # 生成随机走势数据
    np.random.seed(42)  # 确保结果可重现
    
    # 使用随机游走生成价格
    returns = np.random.normal(0.001, 0.02, len(dates))  # 日收益率
    prices = [start_price]
    
    for ret in returns[1:]:
        new_price = prices[-1] * (1 + ret)
        prices.append(max(new_price, 1.0))  # 防止价格为负
    
    # 生成OHLC数据
    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        # 简单的OHLC生成逻辑
        volatility = close * 0.02  # 2%的日内波动
        high = close + np.random.uniform(0, volatility)
        low = close - np.random.uniform(0, volatility)
        open_price = close + np.random.uniform(-volatility/2, volatility/2)
        volume = int(np.random.uniform(100000, 1000000))
        
        data.append({
            'trade_date': date,
            'open': max(open_price, 1.0),
            'high': max(high, max(open_price, close)),
            'low': min(low, min(open_price, close)),
            'close': close,
            'volume': volume
        })
    
    df = pd.DataFrame(data)
    df.set_index('trade_date', inplace=True)
    
    logger.info(f"生成测试数据: {len(df)} 行，价格范围: {df['close'].min():.2f} - {df['close'].max():.2f}")
    return df


def test_technical_indicators():
    """测试技术指标计算"""
    logger.info("=== 测试技术指标计算 ===")
    
    # 生成测试数据
    data = generate_test_data(50)
    close_prices = data['close']
    
    try:
        # 测试移动平均线
        sma_10 = TechnicalIndicators.sma(close_prices, 10)
        ema_10 = TechnicalIndicators.ema(close_prices, 10)
        
        # 测试RSI
        rsi_14 = TechnicalIndicators.rsi(close_prices, 14)
        
        # 测试布林带
        upper, middle, lower = TechnicalIndicators.bollinger_bands(close_prices, 20, 2)
        
        # 测试MACD
        macd_line, signal_line, histogram = TechnicalIndicators.macd(close_prices)
        
        # 验证结果
        assert not sma_10.empty, "SMA计算失败"
        assert not ema_10.empty, "EMA计算失败"
        assert not rsi_14.empty, "RSI计算失败"
        assert not upper.empty, "布林带计算失败"
        assert not macd_line.empty, "MACD计算失败"
        
        # 检查数值合理性
        assert 0 <= rsi_14.dropna().max() <= 100, "RSI值超出范围"
        assert rsi_14.dropna().min() >= 0, "RSI值为负"
        
        logger.info("✓ 技术指标计算测试通过")
        
        # 打印一些统计信息
        logger.info(f"SMA(10) 最新值: {sma_10.iloc[-1]:.2f}")
        logger.info(f"EMA(10) 最新值: {ema_10.iloc[-1]:.2f}")
        logger.info(f"RSI(14) 最新值: {rsi_14.iloc[-1]:.2f}")
        logger.info(f"布林带宽度: {(upper.iloc[-1] - lower.iloc[-1]):.2f}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 技术指标计算测试失败: {e}")
        return False


def test_ma_strategy():
    """测试双均线策略"""
    logger.info("=== 测试双均线策略 ===")
    
    try:
        # 创建策略实例
        strategy = MovingAverageCrossoverStrategy(
            name="测试双均线",
            params={
                'fast_period': 5,
                'slow_period': 20,
                'ma_type': 'SMA',
                'min_crossover_gap': 0.01,
                'trend_filter': False  # 简化测试
            }
        )
        
        # 生成测试数据
        data = generate_test_data(60)
        
        # 处理数据生成信号
        signals = strategy.process_data(data, "TEST.SH")
        
        logger.info(f"双均线策略生成信号数: {len(signals)}")
        
        # 验证信号
        for signal in signals[:3]:  # 只显示前3个信号
            logger.info(f"信号: {signal.signal_type.value}, 价格: {signal.price:.2f}, "
                       f"置信度: {signal.confidence:.2f}, 原因: {signal.reason}")
        
        # 获取策略状态
        status = strategy.get_strategy_status()
        logger.info(f"策略状态: {status}")
        
        logger.info("✓ 双均线策略测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ 双均线策略测试失败: {e}")
        return False


def test_rsi_strategy():
    """测试RSI策略"""
    logger.info("=== 测试RSI策略 ===")
    
    try:
        # 创建策略实例
        strategy = RSIStrategy(
            name="测试RSI",
            params={
                'rsi_period': 14,
                'overbought_level': 70,
                'oversold_level': 30,
                'signal_confirmation': 1,  # 简化测试
                'divergence_detection': False,  # 简化测试
                'trend_filter': False
            }
        )
        
        # 生成测试数据（添加一些极值来触发RSI信号）
        data = generate_test_data(50)
        
        # 人为创造一些极值情况
        data.loc[data.index[-10:], 'close'] *= 1.3  # 最后10天上涨30%
        data.loc[data.index[-5:], 'close'] *= 0.8   # 最后5天下跌20%
        
        # 重新计算OHLC
        for i in range(len(data)):
            if i > 0:
                close = data.iloc[i]['close']
                prev_close = data.iloc[i-1]['close']
                data.iloc[i, data.columns.get_loc('high')] = max(close, prev_close * 1.02)
                data.iloc[i, data.columns.get_loc('low')] = min(close, prev_close * 0.98)
                data.iloc[i, data.columns.get_loc('open')] = prev_close
        
        # 处理数据生成信号
        signals = strategy.process_data(data, "TEST.SH")
        
        logger.info(f"RSI策略生成信号数: {len(signals)}")
        
        # 验证信号
        for signal in signals[:3]:  # 只显示前3个信号
            logger.info(f"信号: {signal.signal_type.value}, 价格: {signal.price:.2f}, "
                       f"置信度: {signal.confidence:.2f}, 原因: {signal.reason}")
            logger.info(f"RSI值: {signal.metadata.get('rsi', 'N/A'):.2f}")
        
        # 获取RSI状态
        rsi_status = strategy.get_current_rsi_status("TEST.SH")
        if rsi_status:
            logger.info(f"当前RSI状态: {rsi_status}")
        
        logger.info("✓ RSI策略测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ RSI策略测试失败: {e}")
        return False


def test_strategy_manager():
    """测试策略管理器"""
    logger.info("=== 测试策略管理器 ===")
    
    try:
        # 获取策略管理器
        manager = get_strategy_manager()
        
        # 获取可用策略
        available_strategies = manager.get_available_strategies()
        logger.info(f"可用策略: {available_strategies}")
        
        # 创建策略实例
        ma_instance = manager.create_strategy(
            "MovingAverageCrossoverStrategy", 
            "MA_Test",
            {'fast_period': 10, 'slow_period': 30}
        )
        
        rsi_instance = manager.create_strategy(
            "RSIStrategy",
            "RSI_Test", 
            {'rsi_period': 14, 'overbought_level': 75}
        )
        
        logger.info(f"创建策略实例: {ma_instance}, {rsi_instance}")
        
        # 测试批量处理
        test_data = generate_test_data(50)
        
        # 模拟处理单个品种
        results = manager.process_symbol_data("000001.SZ", test_data)
        
        logger.info("策略处理结果:")
        for strategy_name, signals in results.items():
            logger.info(f"{strategy_name}: {len(signals)} 个信号")
        
        # 获取所有策略状态
        all_status = manager.get_all_strategies_status()
        logger.info(f"活跃策略数: {len(all_status)}")
        
        # 测试策略参数更新
        manager.update_strategy_parameters(ma_instance, {'fast_period': 12})
        logger.info("策略参数更新成功")
        
        # 停用策略
        manager.deactivate_strategy(rsi_instance)
        logger.info("策略停用成功")
        
        # 清理
        manager.remove_strategy(ma_instance)
        manager.remove_strategy(rsi_instance)
        
        logger.info("✓ 策略管理器测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ 策略管理器测试失败: {e}")
        return False


def test_strategy_catalog():
    """测试策略目录功能"""
    logger.info("=== 测试策略目录功能 ===")
    
    try:
        # 获取策略目录
        catalog = get_strategy_catalog()
        logger.info(f"策略目录包含 {len(catalog)} 个策略")
        
        for name, info in catalog.items():
            logger.info(f"策略: {name} - {info['name']} ({info['category']})")
        
        # 测试根据名称创建策略
        ma_strategy = create_strategy_by_name("MovingAverageCrossover", "Test_MA")
        logger.info(f"创建策略: {ma_strategy.name}")
        
        # 测试不存在的策略
        try:
            invalid_strategy = create_strategy_by_name("NonExistentStrategy")
            logger.error("应该抛出异常")
            return False
        except ValueError as e:
            logger.info(f"正确捕获异常: {e}")
        
        logger.info("✓ 策略目录功能测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ 策略目录功能测试失败: {e}")
        return False


def test_data_integration():
    """测试与数据模块的集成"""
    logger.info("=== 测试数据模块集成 ===")
    
    try:
        # 测试数据库连接
        db_manager = get_database_manager()
        connection_ok = db_manager.test_connection()
        
        if connection_ok:
            logger.info("✓ 数据库连接正常")
            
            # 测试查询股票列表
            stocks_sql = "SELECT ts_code, name FROM stock_basic LIMIT 5"
            stocks_df = db_manager.query_dataframe(stocks_sql)
            
            if stocks_df is not None and not stocks_df.empty:
                logger.info(f"查询到 {len(stocks_df)} 只股票")
                logger.info(f"股票样例: {stocks_df.iloc[0]['ts_code']} - {stocks_df.iloc[0]['name']}")
                
                # 测试获取价格数据
                sample_code = stocks_df.iloc[0]['ts_code']
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
                
                price_sql = """
                SELECT trade_date, open_price as open, high_price as high, 
                       low_price as low, close_price as close, vol as volume
                FROM daily_quotes 
                WHERE ts_code = %(ts_code)s AND trade_date BETWEEN %(start_date)s AND %(end_date)s
                ORDER BY trade_date
                LIMIT 20
                """
                
                price_df = db_manager.query_dataframe(price_sql, {
                    'ts_code': sample_code,
                    'start_date': start_date,
                    'end_date': end_date
                })
                
                if price_df is not None and not price_df.empty:
                    logger.info(f"获取到 {len(price_df)} 条价格数据")
                    
                    # 测试策略处理真实数据
                    price_df['trade_date'] = pd.to_datetime(price_df['trade_date'])
                    price_df.set_index('trade_date', inplace=True)
                    
                    strategy = MovingAverageCrossoverStrategy(params={
                        'fast_period': 5,
                        'slow_period': 10,
                        'min_data_length': 15
                    })
                    
                    signals = strategy.process_data(price_df, sample_code)
                    logger.info(f"真实数据生成信号数: {len(signals)}")
                    
                else:
                    logger.warning("未获取到价格数据")
                    
            else:
                logger.warning("未获取到股票数据")
        else:
            logger.warning("数据库连接失败，跳过数据集成测试")
        
        logger.info("✓ 数据模块集成测试完成")
        return True
        
    except Exception as e:
        logger.error(f"✗ 数据模块集成测试失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    logger.info("开始运行策略框架完整测试")
    logger.info("=" * 50)
    
    tests = [
        ("技术指标计算", test_technical_indicators),
        ("双均线策略", test_ma_strategy),
        ("RSI策略", test_rsi_strategy),
        ("策略管理器", test_strategy_manager),
        ("策略目录功能", test_strategy_catalog),
        ("数据模块集成", test_data_integration)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n开始测试: {test_name}")
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"测试 {test_name} 发生异常: {e}")
            results[test_name] = False
        logger.info("-" * 30)
    
    # 汇总结果
    logger.info("\n" + "=" * 50)
    logger.info("测试结果汇总:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        logger.info("🎉 所有测试通过！策略框架MVP开发完成")
        return True
    else:
        logger.warning(f"⚠️  有 {total - passed} 个测试失败，请检查相关功能")
        return False


if __name__ == "__main__":
    # 运行测试
    success = run_all_tests()
    
    if success:
        print("\n策略框架测试成功完成！")
        print("可以开始使用以下功能：")
        print("1. 创建和配置交易策略")
        print("2. 生成交易信号")
        print("3. 管理多个策略实例")
        print("4. 与数据系统集成")
        sys.exit(0)
    else:
        print("\n策略框架测试未完全通过，请检查错误信息")
        sys.exit(1)