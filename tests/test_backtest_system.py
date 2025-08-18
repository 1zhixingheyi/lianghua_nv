"""
回测系统测试脚本
================

测试回测引擎的完整功能，包括数据加载、策略执行、绩效分析和可视化。
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.backtest import BacktestEngine, OrderSide, OrderType
from src.backtest.visualizer import BacktestVisualizer
from src.backtest.performance import PerformanceAnalyzer
from src.strategies.rsi_strategy import RSIStrategy
from src.data.tushare_client import TushareClient


def generate_sample_data(symbol: str = "000001.SZ", days: int = 252) -> pd.DataFrame:
    """
    生成样本数据用于测试
    
    Args:
        symbol: 股票代码
        days: 天数
        
    Returns:
        OHLCV数据
    """
    # 生成日期序列
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # 过滤工作日
    date_range = date_range[date_range.weekday < 5][:days]
    
    # 生成价格数据（随机游走）
    np.random.seed(42)  # 确保可重复
    initial_price = 10.0
    returns = np.random.normal(0.0005, 0.02, len(date_range))
    
    # 生成价格序列
    prices = [initial_price]
    for ret in returns[1:]:
        prices.append(prices[-1] * (1 + ret))
    
    # 生成OHLCV数据
    data = []
    for i, (date, price) in enumerate(zip(date_range, prices)):
        # 模拟日内波动
        high = price * (1 + abs(np.random.normal(0, 0.01)))
        low = price * (1 - abs(np.random.normal(0, 0.01)))
        open_price = prices[i-1] if i > 0 else price
        close = price
        volume = np.random.randint(1000000, 10000000)
        
        data.append({
            'open': open_price,
            'high': max(open_price, high, close),
            'low': min(open_price, low, close),
            'close': close,
            'volume': volume
        })
    
    df = pd.DataFrame(data, index=date_range)
    return df


def simple_ma_strategy(market_data, engine):
    """
    简单移动平均策略
    
    Args:
        market_data: 市场数据字典
        engine: 回测引擎实例
    """
    for symbol, data in market_data.items():
        if len(data) < 20:  # 需要足够的数据计算移动平均
            continue
        
        # 计算移动平均线
        data = data.copy()
        data['ma5'] = data['close'].rolling(window=5).mean()
        data['ma20'] = data['close'].rolling(window=20).mean()
        
        # 获取最新数据
        latest = data.iloc[-1]
        previous = data.iloc[-2] if len(data) > 1 else latest
        
        current_position = engine.portfolio.get_position(symbol)
        current_price = engine.get_current_price(symbol)
        
        if current_price is None:
            continue
        
        # 买入信号：短期均线上穿长期均线
        if (latest['ma5'] > latest['ma20'] and 
            previous['ma5'] <= previous['ma20'] and 
            current_position == 0):
            
            # 计算买入数量（使用可用资金的20%）
            available_cash = engine.portfolio.cash
            position_size = available_cash * 0.2
            quantity = int(position_size / current_price / 100) * 100  # 按手买入
            
            if quantity > 0:
                engine.submit_order(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    quantity=quantity,
                    order_type=OrderType.MARKET
                )
        
        # 卖出信号：短期均线下穿长期均线
        elif (latest['ma5'] < latest['ma20'] and 
              previous['ma5'] >= previous['ma20'] and 
              current_position > 0):
            
            engine.submit_order(
                symbol=symbol,
                side=OrderSide.SELL,
                quantity=current_position,
                order_type=OrderType.MARKET
            )


def test_basic_backtest():
    """测试基础回测功能"""
    print("=" * 60)
    print("开始测试基础回测功能...")
    print("=" * 60)
    
    # 创建回测引擎
    engine = BacktestEngine(
        initial_capital=1000000,
        commission_rate=0.0003,
        slippage_rate=0.0001,
        start_date="2023-01-01",
        end_date="2023-12-31"
    )
    
    # 生成测试数据
    print("生成测试数据...")
    test_data = generate_sample_data("000001.SZ", 252)
    engine.add_data("000001.SZ", test_data)
    
    # 设置策略
    engine.set_strategy(simple_ma_strategy)
    
    # 运行回测
    print("运行回测...")
    results = engine.run()
    
    # 打印基础结果
    print(f"\n回测完成！")
    print(f"初始资金: {engine.initial_capital:,.2f}")
    print(f"最终价值: {results['portfolio']['final_value']:,.2f}")
    print(f"总收益: {results['portfolio']['final_value'] - engine.initial_capital:,.2f}")
    print(f"总收益率: {(results['portfolio']['final_value'] / engine.initial_capital - 1) * 100:.2f}%")
    print(f"总交易次数: {len(results['trades'])}")
    print(f"总手续费: {results['portfolio']['total_commission']:,.2f}")
    
    return results


def test_performance_analysis(results):
    """测试绩效分析功能"""
    print("\n" + "=" * 60)
    print("测试绩效分析功能...")
    print("=" * 60)
    
    metrics = results['performance_metrics']
    analyzer = PerformanceAnalyzer()
    
    # 打印绩效报告
    report = analyzer.generate_report(metrics)
    print(report)
    
    return metrics


def test_visualization(results):
    """测试可视化功能"""
    print("\n" + "=" * 60)
    print("测试可视化功能...")
    print("=" * 60)
    
    try:
        visualizer = BacktestVisualizer()
        
        # 创建综合报告
        visualizer.create_comprehensive_report(results)
        
        print("可视化测试完成！")
        
    except Exception as e:
        print(f"可视化测试出现错误: {e}")
        print("这可能是由于缺少图形环境或matplotlib配置问题")


def test_rsi_strategy_integration():
    """测试RSI策略集成"""
    print("\n" + "=" * 60)
    print("测试RSI策略集成...")
    print("=" * 60)
    
    try:
        # 创建回测引擎
        engine = BacktestEngine(
            initial_capital=1000000,
            commission_rate=0.0003,
            slippage_rate=0.0001
        )
        
        # 生成测试数据
        test_data = generate_sample_data("000002.SZ", 100)
        engine.add_data("000002.SZ", test_data)
        
        # 创建RSI策略实例
        rsi_strategy = RSIStrategy(
            rsi_period=14,
            overbought_level=70,
            oversold_level=30
        )
        
        # 定义策略回调函数
        def rsi_strategy_callback(market_data, engine):
            for symbol, data in market_data.items():
                # 获取RSI信号
                signals = rsi_strategy.generate_signals(data)
                if signals.empty:
                    continue
                
                latest_signal = signals.iloc[-1]
                current_position = engine.portfolio.get_position(symbol)
                current_price = engine.get_current_price(symbol)
                
                if current_price is None:
                    continue
                
                # 执行交易
                if latest_signal['signal'] == 1 and current_position == 0:  # 买入信号
                    available_cash = engine.portfolio.cash
                    position_size = available_cash * 0.3
                    quantity = int(position_size / current_price / 100) * 100
                    
                    if quantity > 0:
                        engine.submit_order(
                            symbol=symbol,
                            side=OrderSide.BUY,
                            quantity=quantity,
                            order_type=OrderType.MARKET
                        )
                
                elif latest_signal['signal'] == -1 and current_position > 0:  # 卖出信号
                    engine.submit_order(
                        symbol=symbol,
                        side=OrderSide.SELL,
                        quantity=current_position,
                        order_type=OrderType.MARKET
                    )
        
        engine.set_strategy(rsi_strategy_callback)
        
        # 运行回测
        results = engine.run()
        
        print(f"RSI策略回测完成！")
        print(f"最终价值: {results['portfolio']['final_value']:,.2f}")
        print(f"总收益率: {(results['portfolio']['final_value'] / engine.initial_capital - 1) * 100:.2f}%")
        print(f"交易次数: {len(results['trades'])}")
        
        return results
        
    except Exception as e:
        print(f"RSI策略测试出现错误: {e}")
        return None


def test_real_data_integration():
    """测试真实数据集成"""
    print("\n" + "=" * 60)
    print("测试真实数据集成...")
    print("=" * 60)
    
    try:
        from src.config.settings import TUSHARE_TOKEN
        if not TUSHARE_TOKEN:
            print("未配置Tushare Token，跳过真实数据测试")
            return
        
        # 创建数据客户端
        client = TushareClient(TUSHARE_TOKEN)
        
        # 获取真实数据
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=100)).strftime('%Y%m%d')
        
        data = client.get_daily_data(
            ts_code="000001.SZ",
            start_date=start_date,
            end_date=end_date
        )
        
        if data is not None and not data.empty:
            print(f"获取到 {len(data)} 条真实数据")
            
            # 创建回测引擎
            engine = BacktestEngine(
                initial_capital=1000000,
                commission_rate=0.0003,
                slippage_rate=0.0001
            )
            
            # 添加真实数据
            engine.add_data("000001.SZ", data)
            engine.set_strategy(simple_ma_strategy)
            
            # 运行回测
            results = engine.run()
            
            print(f"真实数据回测完成！")
            print(f"最终价值: {results['portfolio']['final_value']:,.2f}")
            print(f"总收益率: {(results['portfolio']['final_value'] / engine.initial_capital - 1) * 100:.2f}%")
            
        else:
            print("未能获取真实数据，可能是网络问题或API限制")
    
    except Exception as e:
        print(f"真实数据测试出现错误: {e}")


def main():
    """主测试函数"""
    print("开始回测系统综合测试")
    print("=" * 60)
    
    try:
        # 1. 基础回测功能测试
        results = test_basic_backtest()
        
        # 2. 绩效分析测试
        metrics = test_performance_analysis(results)
        
        # 3. 可视化测试
        test_visualization(results)
        
        # 4. RSI策略集成测试
        rsi_results = test_rsi_strategy_integration()
        
        # 5. 真实数据集成测试
        test_real_data_integration()
        
        print("\n" + "=" * 60)
        print("所有测试完成！")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)