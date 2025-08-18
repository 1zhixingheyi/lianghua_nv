"""
回测系统使用示例
================

展示如何使用回测系统进行完整的策略回测和分析。
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.backtest import BacktestEngine, OrderSide, OrderType
from src.backtest.visualizer import BacktestVisualizer
try:
    from src.strategies.ma_crossover import MACrossoverStrategy
    from src.strategies.rsi_strategy import RSIStrategy
except ImportError:
    print("策略模块导入失败，将使用内置策略")


def create_sample_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    创建样本数据
    
    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        
    Returns:
        OHLCV数据
    """
    # 生成日期范围
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    # 过滤工作日
    date_range = date_range[date_range.weekday < 5]
    
    # 设置随机种子确保可重复
    np.random.seed(42)
    
    # 生成价格数据
    initial_price = 100.0
    returns = np.random.normal(0.0008, 0.015, len(date_range))
    
    # 添加一些趋势和周期性
    trend = np.linspace(0, 0.3, len(date_range))
    cycle = 0.1 * np.sin(np.linspace(0, 4*np.pi, len(date_range)))
    returns += trend / len(date_range) + cycle / len(date_range)
    
    # 生成累积价格
    prices = [initial_price]
    for ret in returns[1:]:
        prices.append(prices[-1] * (1 + ret))
    
    # 生成OHLCV数据
    data = []
    for i, (date, close_price) in enumerate(zip(date_range, prices)):
        # 模拟日内波动
        volatility = 0.02
        high = close_price * (1 + abs(np.random.normal(0, volatility)))
        low = close_price * (1 - abs(np.random.normal(0, volatility)))
        open_price = prices[i-1] if i > 0 else close_price
        volume = np.random.randint(1000000, 50000000)
        
        data.append({
            'open': open_price,
            'high': max(open_price, high, close_price),
            'low': min(open_price, low, close_price),
            'close': close_price,
            'volume': volume
        })
    
    df = pd.DataFrame(data, index=date_range)
    return df


def dual_ma_strategy(market_data, engine):
    """
    双移动平均线策略
    
    Args:
        market_data: 市场数据字典
        engine: 回测引擎实例
    """
    for symbol, data in market_data.items():
        if len(data) < 50:  # 需要足够数据
            continue
        
        # 计算移动平均线
        data = data.copy()
        data['ma10'] = data['close'].rolling(window=10).mean()
        data['ma30'] = data['close'].rolling(window=30).mean()
        
        # 检查是否有足够的数据
        if pd.isna(data['ma30'].iloc[-1]):
            continue
        
        # 获取最近两天的数据
        if len(data) < 2:
            continue
            
        latest = data.iloc[-1]
        previous = data.iloc[-2]
        
        current_position = engine.portfolio.get_position(symbol)
        current_price = engine.get_current_price(symbol)
        
        if current_price is None:
            continue
        
        # 金叉：短期均线上穿长期均线，买入
        if (latest['ma10'] > latest['ma30'] and 
            previous['ma10'] <= previous['ma30'] and 
            current_position == 0):
            
            # 使用30%资金买入
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
                print(f"买入信号: {symbol}, 价格: {current_price:.2f}, 数量: {quantity}")
        
        # 死叉：短期均线下穿长期均线，卖出
        elif (latest['ma10'] < latest['ma30'] and 
              previous['ma10'] >= previous['ma30'] and 
              current_position > 0):
            
            engine.submit_order(
                symbol=symbol,
                side=OrderSide.SELL,
                quantity=current_position,
                order_type=OrderType.MARKET
            )
            print(f"卖出信号: {symbol}, 价格: {current_price:.2f}, 数量: {current_position}")


def run_backtest_example():
    """
    运行回测示例
    """
    print("🚀 回测系统使用示例")
    print("=" * 50)
    
    # 1. 创建回测引擎
    print("\n1. 创建回测引擎...")
    engine = BacktestEngine(
        initial_capital=1000000,  # 100万初始资金
        commission_rate=0.0003,   # 万三手续费
        slippage_rate=0.0001,     # 万一滑点
        start_date="2023-01-01",
        end_date="2023-12-31"
    )
    
    # 2. 准备测试数据
    print("\n2. 准备测试数据...")
    symbols = ["000001.SZ", "000002.SZ", "600000.SH"]
    
    for symbol in symbols:
        data = create_sample_data(symbol, "2023-01-01", "2023-12-31")
        engine.add_data(symbol, data)
        print(f"添加 {symbol} 数据: {len(data)} 条记录")
    
    # 3. 设置策略
    print("\n3. 设置双移动平均线策略...")
    engine.set_strategy(dual_ma_strategy)
    
    # 4. 运行回测
    print("\n4. 运行回测...")
    results = engine.run()
    
    # 5. 输出基础结果
    print("\n5. 回测结果:")
    print("=" * 30)
    portfolio = results['portfolio']
    metrics = results['performance_metrics']
    
    print(f"初始资金: {engine.initial_capital:,.2f}")
    print(f"最终价值: {portfolio['final_value']:,.2f}")
    print(f"净收益: {portfolio['final_value'] - engine.initial_capital:,.2f}")
    print(f"总收益率: {metrics.get('total_return', 0):.2%}")
    print(f"年化收益率: {metrics.get('annualized_return', 0):.2%}")
    print(f"最大回撤: {metrics.get('max_drawdown', 0):.2%}")
    print(f"夏普比率: {metrics.get('sharpe_ratio', 0):.2f}")
    print(f"胜率: {metrics.get('win_rate', 0):.2%}")
    print(f"总交易次数: {len(results['trades'])}")
    print(f"总手续费: {portfolio['total_commission']:,.2f}")
    
    # 6. 详细交易记录
    print("\n6. 交易记录 (前10笔):")
    print("=" * 30)
    trades = results['trades']
    if not trades.empty:
        for i, trade in trades.head(10).iterrows():
            print(f"{trade['timestamp'].strftime('%Y-%m-%d')} {trade['side']} "
                  f"{trade['symbol']} {trade['quantity']} @ {trade['price']:.2f}")
        if len(trades) > 10:
            print(f"... 还有 {len(trades) - 10} 笔交易")
    
    # 7. 持仓分析
    print("\n7. 最终持仓:")
    print("=" * 30)
    for symbol, quantity in portfolio['positions'].items():
        if quantity > 0:
            current_price = engine.current_prices.get(symbol, 0)
            market_value = quantity * current_price
            print(f"{symbol}: {quantity} 股, 市值: {market_value:,.2f}")
    
    print(f"现金余额: {portfolio['cash']:,.2f}")
    
    # 8. 生成可视化报告
    print("\n8. 生成可视化报告...")
    try:
        visualizer = BacktestVisualizer()
        visualizer.create_comprehensive_report(results)
        print("可视化报告生成完成！")
    except Exception as e:
        print(f"可视化生成失败: {e}")
    
    return results


def compare_strategies():
    """
    比较不同策略的表现
    """
    print("\n" + "=" * 50)
    print("📊 策略比较分析")
    print("=" * 50)
    
    strategies = {
        "双均线策略": dual_ma_strategy,
        # 可以添加更多策略进行比较
    }
    
    results_comparison = {}
    
    for strategy_name, strategy_func in strategies.items():
        print(f"\n测试 {strategy_name}...")
        
        # 创建独立的回测引擎
        engine = BacktestEngine(
            initial_capital=1000000,
            commission_rate=0.0003,
            slippage_rate=0.0001,
            start_date="2023-01-01",
            end_date="2023-12-31"
        )
        
        # 添加数据
        data = create_sample_data("000001.SZ", "2023-01-01", "2023-12-31")
        engine.add_data("000001.SZ", data)
        
        # 设置策略并运行
        engine.set_strategy(strategy_func)
        results = engine.run()
        
        # 保存结果
        results_comparison[strategy_name] = {
            'total_return': results['performance_metrics'].get('total_return', 0),
            'max_drawdown': results['performance_metrics'].get('max_drawdown', 0),
            'sharpe_ratio': results['performance_metrics'].get('sharpe_ratio', 0),
            'total_trades': len(results['trades'])
        }
    
    # 比较结果
    print("\n策略比较结果:")
    print("=" * 60)
    print(f"{'策略名称':<15} {'总收益率':<10} {'最大回撤':<10} {'夏普比率':<10} {'交易次数':<8}")
    print("-" * 60)
    
    for name, metrics in results_comparison.items():
        print(f"{name:<15} {metrics['total_return']:<9.2%} {metrics['max_drawdown']:<9.2%} "
              f"{metrics['sharpe_ratio']:<9.2f} {metrics['total_trades']:<8}")


def main():
    """
    主函数
    """
    try:
        # 运行回测示例
        results = run_backtest_example()
        
        # 策略比较
        compare_strategies()
        
        print("\n✅ 回测示例运行完成！")
        return True
        
    except Exception as e:
        print(f"\n❌ 运行过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)