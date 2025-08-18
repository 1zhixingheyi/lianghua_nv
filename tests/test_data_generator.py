#!/usr/bin/env python3
"""
测试数据生成器
为各种测试场景生成模拟数据
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import random
from typing import List, Dict, Optional, Tuple
import sqlite3

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


class StockDataGenerator:
    """股票数据生成器"""
    
    def __init__(self, seed: int = 42):
        """初始化生成器"""
        np.random.seed(seed)
        random.seed(seed)
        
        # 预定义的股票代码和名称
        self.stock_info = {
            '000001.SZ': {'name': '平安银行', 'industry': '银行', 'base_price': 12.0},
            '000002.SZ': {'name': '万科A', 'industry': '房地产', 'base_price': 18.0},
            '600000.SH': {'name': '浦发银行', 'industry': '银行', 'base_price': 11.0},
            '600036.SH': {'name': '招商银行', 'industry': '银行', 'base_price': 42.0},
            '000858.SZ': {'name': '五粮液', 'industry': '食品饮料', 'base_price': 180.0},
            '600519.SH': {'name': '贵州茅台', 'industry': '食品饮料', 'base_price': 1800.0},
            '000858.SZ': {'name': '五粮液', 'industry': '食品饮料', 'base_price': 180.0},
            '002415.SZ': {'name': '海康威视', 'industry': '电子', 'base_price': 38.0},
            '600276.SH': {'name': '恒瑞医药', 'industry': '医药生物', 'base_price': 58.0},
            '300059.SZ': {'name': '东方财富', 'industry': '非银金融', 'base_price': 25.0}
        }
        
        # 行业特征
        self.industry_volatility = {
            '银行': 0.015,
            '房地产': 0.025,
            '食品饮料': 0.020,
            '电子': 0.030,
            '医药生物': 0.025,
            '非银金融': 0.035
        }
    
    def generate_price_series(
        self, 
        stock_code: str, 
        start_date: str, 
        end_date: str,
        trend: str = 'random'
    ) -> pd.DataFrame:
        """
        生成股票价格序列
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            trend: 趋势类型 ('up', 'down', 'sideways', 'random')
        """
        # 解析日期
        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')
        
        # 生成交易日期（排除周末）
        dates = []
        current = start
        while current <= end:
            if current.weekday() < 5:  # 周一到周五
                dates.append(current)
            current += timedelta(days=1)
        
        if not dates:
            return pd.DataFrame()
        
        # 获取股票信息
        stock_info = self.stock_info.get(stock_code, {
            'name': f'股票{stock_code}',
            'industry': '其他',
            'base_price': 10.0
        })
        
        base_price = stock_info['base_price']
        volatility = self.industry_volatility.get(stock_info['industry'], 0.025)
        
        # 生成价格序列
        prices = self._generate_price_path(
            base_price=base_price,
            num_days=len(dates),
            volatility=volatility,
            trend=trend
        )
        
        # 生成OHLC数据
        data = []
        for i, date in enumerate(dates):
            close_price = prices[i]
            
            # 生成开盘价（基于前一日收盘价）
            if i == 0:
                open_price = close_price * np.random.uniform(0.99, 1.01)
            else:
                open_price = prices[i-1] * np.random.uniform(0.98, 1.02)
            
            # 生成最高价和最低价
            daily_range = close_price * volatility * np.random.uniform(0.5, 2.0)
            high_price = max(open_price, close_price) + daily_range * np.random.uniform(0, 1)
            low_price = min(open_price, close_price) - daily_range * np.random.uniform(0, 1)
            
            # 确保价格合理性
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)
            
            # 生成成交量和成交额
            volume = self._generate_volume(close_price, base_price)
            amount = volume * (high_price + low_price + open_price + close_price) / 4
            
            data.append({
                'ts_code': stock_code,
                'trade_date': date.strftime('%Y%m%d'),
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'vol': int(volume),
                'amount': round(amount, 2)
            })
        
        return pd.DataFrame(data)
    
    def _generate_price_path(
        self, 
        base_price: float, 
        num_days: int, 
        volatility: float, 
        trend: str
    ) -> np.ndarray:
        """生成价格路径"""
        
        # 基础随机游走
        returns = np.random.normal(0, volatility, num_days)
        
        # 添加趋势
        if trend == 'up':
            trend_component = np.linspace(0, 0.3, num_days)  # 30%的上涨
        elif trend == 'down':
            trend_component = np.linspace(0, -0.2, num_days)  # 20%的下跌
        elif trend == 'sideways':
            trend_component = np.sin(np.linspace(0, 4*np.pi, num_days)) * 0.05  # 震荡
        else:  # random
            trend_component = np.zeros(num_days)
        
        # 计算累积收益
        total_returns = returns + trend_component / num_days
        cumulative_returns = np.cumsum(total_returns)
        
        # 生成价格序列
        prices = base_price * np.exp(cumulative_returns)
        
        return prices
    
    def _generate_volume(self, current_price: float, base_price: float) -> int:
        """生成成交量"""
        # 价格变动越大，成交量越大
        price_change_ratio = abs(current_price - base_price) / base_price
        base_volume = np.random.uniform(1000000, 5000000)
        volume_multiplier = 1 + price_change_ratio * 2
        
        return int(base_volume * volume_multiplier)
    
    def generate_multi_stock_data(
        self, 
        stock_codes: List[str], 
        start_date: str, 
        end_date: str,
        market_trend: str = 'random'
    ) -> pd.DataFrame:
        """生成多只股票的数据"""
        all_data = []
        
        for stock_code in stock_codes:
            # 为每只股票生成不同的趋势（但受市场趋势影响）
            individual_trends = ['up', 'down', 'sideways', 'random']
            if market_trend != 'random':
                # 70%概率跟随市场趋势
                if np.random.random() < 0.7:
                    trend = market_trend
                else:
                    trend = np.random.choice(individual_trends)
            else:
                trend = np.random.choice(individual_trends)
            
            stock_data = self.generate_price_series(
                stock_code, start_date, end_date, trend
            )
            all_data.append(stock_data)
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        else:
            return pd.DataFrame()
    
    def generate_extreme_scenarios(
        self, 
        stock_code: str, 
        scenario: str,
        num_days: int = 30
    ) -> pd.DataFrame:
        """
        生成极端市场场景数据
        
        Args:
            stock_code: 股票代码
            scenario: 场景类型 ('crash', 'rally', 'high_volatility', 'gap_up', 'gap_down')
            num_days: 天数
        """
        base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        dates = [base_date + timedelta(days=i) for i in range(num_days)]
        dates = [d for d in dates if d.weekday() < 5]  # 工作日
        
        stock_info = self.stock_info.get(stock_code, {
            'name': f'股票{stock_code}',
            'base_price': 10.0
        })
        base_price = stock_info['base_price']
        
        data = []
        
        if scenario == 'crash':
            # 股市崩盘场景
            prices = self._generate_crash_scenario(base_price, len(dates))
        elif scenario == 'rally':
            # 大幅上涨场景
            prices = self._generate_rally_scenario(base_price, len(dates))
        elif scenario == 'high_volatility':
            # 高波动场景
            prices = self._generate_high_volatility_scenario(base_price, len(dates))
        elif scenario == 'gap_up':
            # 跳空高开场景
            prices = self._generate_gap_scenario(base_price, len(dates), direction='up')
        elif scenario == 'gap_down':
            # 跳空低开场景
            prices = self._generate_gap_scenario(base_price, len(dates), direction='down')
        else:
            raise ValueError(f"未知场景类型: {scenario}")
        
        for i, date in enumerate(dates):
            close_price = prices[i]
            
            # 生成当日OHLC
            if scenario in ['gap_up', 'gap_down'] and i == 1:  # 跳空当日
                if scenario == 'gap_up':
                    open_price = prices[i-1] * 1.08  # 8%跳空
                else:
                    open_price = prices[i-1] * 0.92  # -8%跳空
            else:
                open_price = close_price * np.random.uniform(0.995, 1.005)
            
            if scenario == 'high_volatility':
                daily_range = close_price * 0.08  # 8%日内波动
            else:
                daily_range = close_price * 0.03
                
            high_price = max(open_price, close_price) + daily_range * np.random.uniform(0, 0.5)
            low_price = min(open_price, close_price) - daily_range * np.random.uniform(0, 0.5)
            
            # 确保价格合理性
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)
            
            # 极端场景下成交量放大
            volume_multiplier = 2.0 if scenario in ['crash', 'rally'] else 1.5
            volume = int(np.random.uniform(2000000, 10000000) * volume_multiplier)
            amount = volume * (high_price + low_price + open_price + close_price) / 4
            
            data.append({
                'ts_code': stock_code,
                'trade_date': date.strftime('%Y%m%d'),
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'vol': volume,
                'amount': round(amount, 2)
            })
        
        return pd.DataFrame(data)
    
    def _generate_crash_scenario(self, base_price: float, num_days: int) -> np.ndarray:
        """生成崩盘场景价格"""
        # 前几天正常，然后急剧下跌
        normal_days = min(5, num_days // 3)
        crash_days = num_days - normal_days
        
        normal_returns = np.random.normal(0, 0.02, normal_days)
        crash_returns = np.random.normal(-0.08, 0.04, crash_days)  # 平均-8%日跌幅
        
        all_returns = np.concatenate([normal_returns, crash_returns])
        cumulative_returns = np.cumsum(all_returns)
        
        return base_price * np.exp(cumulative_returns)
    
    def _generate_rally_scenario(self, base_price: float, num_days: int) -> np.ndarray:
        """生成大涨场景价格"""
        rally_returns = np.random.normal(0.05, 0.02, num_days)  # 平均5%日涨幅
        cumulative_returns = np.cumsum(rally_returns)
        
        return base_price * np.exp(cumulative_returns)
    
    def _generate_high_volatility_scenario(self, base_price: float, num_days: int) -> np.ndarray:
        """生成高波动场景价格"""
        high_vol_returns = np.random.normal(0, 0.06, num_days)  # 高波动
        cumulative_returns = np.cumsum(high_vol_returns)
        
        return base_price * np.exp(cumulative_returns)
    
    def _generate_gap_scenario(self, base_price: float, num_days: int, direction: str) -> np.ndarray:
        """生成跳空场景价格"""
        normal_returns = np.random.normal(0, 0.02, num_days)
        
        # 在第二天制造跳空
        if num_days > 1:
            if direction == 'up':
                normal_returns[1] += 0.08  # 8%跳空高开
            else:
                normal_returns[1] -= 0.08  # 8%跳空低开
        
        cumulative_returns = np.cumsum(normal_returns)
        return base_price * np.exp(cumulative_returns)


class TradeDataGenerator:
    """交易数据生成器"""
    
    def __init__(self, seed: int = 42):
        np.random.seed(seed)
        random.seed(seed)
    
    def generate_trade_records(
        self, 
        num_trades: int = 100,
        date_range: Tuple[str, str] = None
    ) -> List[Dict]:
        """生成交易记录"""
        if date_range is None:
            start_date = datetime.now() - timedelta(days=30)
            end_date = datetime.now()
        else:
            start_date = datetime.strptime(date_range[0], '%Y%m%d')
            end_date = datetime.strptime(date_range[1], '%Y%m%d')
        
        trades = []
        stock_codes = ['000001.SZ', '000002.SZ', '600000.SH', '600036.SH', '000858.SZ']
        strategies = ['ma_crossover', 'rsi_strategy', 'manual']
        
        for i in range(num_trades):
            # 随机生成交易时间
            trade_date = start_date + timedelta(
                days=random.randint(0, (end_date - start_date).days)
            )
            
            # 确保是交易日
            while trade_date.weekday() >= 5:
                trade_date += timedelta(days=1)
            
            trade_time = trade_date.replace(
                hour=random.randint(9, 14),
                minute=random.randint(0, 59),
                second=random.randint(0, 59)
            )
            
            stock_code = random.choice(stock_codes)
            action = random.choice(['buy', 'sell'])
            quantity = random.randint(100, 5000) * 100  # 100股的整数倍
            price = round(random.uniform(8.0, 50.0), 2)
            
            trade = {
                'id': f'trade_{i+1:06d}',
                'timestamp': trade_time.isoformat(),
                'stock_code': stock_code,
                'action': action,
                'quantity': quantity,
                'price': price,
                'amount': quantity * price,
                'commission': max(quantity * price * 0.0003, 5.0),  # 最低5元手续费
                'stamp_tax': quantity * price * 0.001 if action == 'sell' else 0.0,
                'strategy': random.choice(strategies),
                'status': random.choice(['filled', 'partial', 'cancelled']),
                'order_type': random.choice(['market', 'limit']),
                'notes': f'策略交易-{i+1}'
            }
            
            trades.append(trade)
        
        return sorted(trades, key=lambda x: x['timestamp'])
    
    def generate_portfolio_history(
        self, 
        initial_capital: float = 1000000.0,
        num_days: int = 252
    ) -> pd.DataFrame:
        """生成投资组合历史数据"""
        start_date = datetime.now() - timedelta(days=num_days)
        
        data = []
        current_capital = initial_capital
        
        for i in range(num_days):
            date = start_date + timedelta(days=i)
            
            # 跳过周末
            if date.weekday() >= 5:
                continue
            
            # 模拟投资组合价值变化
            daily_return = np.random.normal(0.0008, 0.02)  # 年化收益约20%，波动约30%
            current_capital *= (1 + daily_return)
            
            # 计算持仓价值分布
            cash_ratio = random.uniform(0.1, 0.3)  # 10%-30%现金
            stock_value = current_capital * (1 - cash_ratio)
            cash_value = current_capital * cash_ratio
            
            data.append({
                'date': date.strftime('%Y-%m-%d'),
                'total_value': round(current_capital, 2),
                'cash': round(cash_value, 2),
                'stock_value': round(stock_value, 2),
                'daily_return': round(daily_return * 100, 4),
                'cumulative_return': round((current_capital / initial_capital - 1) * 100, 2)
            })
        
        return pd.DataFrame(data)


class TestScenarioGenerator:
    """测试场景生成器"""
    
    def __init__(self):
        self.stock_generator = StockDataGenerator()
        self.trade_generator = TradeDataGenerator()
    
    def create_backtest_scenario(
        self, 
        scenario_name: str,
        stock_codes: List[str] = None,
        duration_days: int = 252
    ) -> Dict:
        """创建回测场景"""
        if stock_codes is None:
            stock_codes = ['000001.SZ', '000002.SZ', '600000.SH']
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=duration_days * 1.5)  # 多生成一些数据
        
        scenarios = {
            'bull_market': {
                'market_trend': 'up',
                'volatility': 'normal',
                'description': '牛市场景'
            },
            'bear_market': {
                'market_trend': 'down',
                'volatility': 'normal',
                'description': '熊市场景'
            },
            'volatile_market': {
                'market_trend': 'sideways',
                'volatility': 'high',
                'description': '震荡市场场景'
            },
            'crisis': {
                'market_trend': 'down',
                'volatility': 'extreme',
                'description': '危机场景'
            }
        }
        
        if scenario_name not in scenarios:
            scenario_name = 'bull_market'
        
        scenario_config = scenarios[scenario_name]
        
        # 生成股票数据
        stock_data = self.stock_generator.generate_multi_stock_data(
            stock_codes=stock_codes,
            start_date=start_date.strftime('%Y%m%d'),
            end_date=end_date.strftime('%Y%m%d'),
            market_trend=scenario_config['market_trend']
        )
        
        # 生成基准数据（市场指数）
        benchmark_data = self.stock_generator.generate_price_series(
            stock_code='000300.SH',  # 沪深300
            start_date=start_date.strftime('%Y%m%d'),
            end_date=end_date.strftime('%Y%m%d'),
            trend=scenario_config['market_trend']
        )
        
        return {
            'scenario_name': scenario_name,
            'description': scenario_config['description'],
            'stock_data': stock_data,
            'benchmark_data': benchmark_data,
            'config': scenario_config,
            'metadata': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'stock_codes': stock_codes,
                'total_records': len(stock_data)
            }
        }
    
    def create_stress_test_data(self) -> Dict:
        """创建压力测试数据"""
        stress_scenarios = {}
        
        # 市场崩盘
        stress_scenarios['market_crash'] = self.stock_generator.generate_extreme_scenarios(
            stock_code='000001.SZ',
            scenario='crash',
            num_days=20
        )
        
        # 暴涨行情
        stress_scenarios['market_rally'] = self.stock_generator.generate_extreme_scenarios(
            stock_code='000001.SZ',
            scenario='rally',
            num_days=15
        )
        
        # 高波动
        stress_scenarios['high_volatility'] = self.stock_generator.generate_extreme_scenarios(
            stock_code='000001.SZ',
            scenario='high_volatility',
            num_days=30
        )
        
        # 跳空场景
        stress_scenarios['gap_up'] = self.stock_generator.generate_extreme_scenarios(
            stock_code='000001.SZ',
            scenario='gap_up',
            num_days=10
        )
        
        stress_scenarios['gap_down'] = self.stock_generator.generate_extreme_scenarios(
            stock_code='000001.SZ',
            scenario='gap_down',
            num_days=10
        )
        
        return stress_scenarios
    
    def save_scenario_to_file(self, scenario_data: Dict, file_path: str):
        """保存场景数据到文件"""
        if file_path.endswith('.json'):
            # 保存为JSON格式
            json_data = {
                'scenario_name': scenario_data['scenario_name'],
                'description': scenario_data['description'],
                'config': scenario_data['config'],
                'metadata': scenario_data['metadata'],
                'stock_data': scenario_data['stock_data'].to_dict('records'),
                'benchmark_data': scenario_data['benchmark_data'].to_dict('records')
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        elif file_path.endswith('.db'):
            # 保存为SQLite数据库
            conn = sqlite3.connect(file_path)
            
            # 保存股票数据
            scenario_data['stock_data'].to_sql('stock_data', conn, if_exists='replace', index=False)
            scenario_data['benchmark_data'].to_sql('benchmark_data', conn, if_exists='replace', index=False)
            
            # 保存元数据
            metadata_df = pd.DataFrame([scenario_data['metadata']])
            metadata_df.to_sql('metadata', conn, if_exists='replace', index=False)
            
            conn.close()
        
        else:
            # 保存为CSV格式
            base_path = file_path.rsplit('.', 1)[0]
            scenario_data['stock_data'].to_csv(f'{base_path}_stock_data.csv', index=False)
            scenario_data['benchmark_data'].to_csv(f'{base_path}_benchmark_data.csv', index=False)
            
            # 保存元数据
            with open(f'{base_path}_metadata.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'scenario_name': scenario_data['scenario_name'],
                    'description': scenario_data['description'],
                    'config': scenario_data['config'],
                    'metadata': scenario_data['metadata']
                }, f, indent=2, ensure_ascii=False)


def main():
    """主函数 - 生成测试数据示例"""
    print("生成测试数据...")
    
    # 创建输出目录
    output_dir = "test_data"
    os.makedirs(output_dir, exist_ok=True)
    
    # 初始化生成器
    scenario_gen = TestScenarioGenerator()
    
    # 生成不同市场场景
    scenarios = ['bull_market', 'bear_market', 'volatile_market', 'crisis']
    
    for scenario in scenarios:
        print(f"生成{scenario}场景数据...")
        scenario_data = scenario_gen.create_backtest_scenario(
            scenario_name=scenario,
            stock_codes=['000001.SZ', '000002.SZ', '600000.SH', '600036.SH'],
            duration_days=252
        )
        
        # 保存数据
        output_file = os.path.join(output_dir, f"{scenario}.json")
        scenario_gen.save_scenario_to_file(scenario_data, output_file)
        print(f"✓ {scenario}场景数据已保存到 {output_file}")
    
    # 生成压力测试数据
    print("生成压力测试数据...")
    stress_data = scenario_gen.create_stress_test_data()
    
    for stress_name, stress_df in stress_data.items():
        output_file = os.path.join(output_dir, f"stress_{stress_name}.csv")
        stress_df.to_csv(output_file, index=False)
        print(f"✓ 压力测试数据 {stress_name} 已保存到 {output_file}")
    
    # 生成交易记录示例
    print("生成交易记录示例...")
    trade_gen = TradeDataGenerator()
    trades = trade_gen.generate_trade_records(num_trades=500)
    
    trades_file = os.path.join(output_dir, "sample_trades.json")
    with open(trades_file, 'w', encoding='utf-8') as f:
        json.dump(trades, f, indent=2, ensure_ascii=False)
    print(f"✓ 交易记录已保存到 {trades_file}")
    
    # 生成投资组合历史
    print("生成投资组合历史数据...")
    portfolio_history = trade_gen.generate_portfolio_history(
        initial_capital=1000000.0,
        num_days=252
    )
    
    portfolio_file = os.path.join(output_dir, "portfolio_history.csv")
    portfolio_history.to_csv(portfolio_file, index=False)
    print(f"✓ 投资组合历史已保存到 {portfolio_file}")
    
    print(f"\n所有测试数据已生成完成，保存在 {output_dir} 目录中")


if __name__ == "__main__":
    main()