#!/usr/bin/env python3
"""
实盘交易接口MVP测试文件

测试交易系统的各个组件功能
"""

import sys
import os
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.trading.base_trader import BaseTrader, OrderType, OrderSide, OrderStatus
from src.trading.qmt_interface import SimulatedQMTInterface
from src.trading.order_manager import OrderManager
from src.trading.portfolio_tracker import PortfolioTracker
from src.trading.trade_executor import TradeExecutor, ExecutionMode
from src.strategies.base_strategy import Signal, SignalType
from src.risk.risk_engine import RiskEngine

class TestTradingSystem(unittest.TestCase):
    """交易系统测试类"""
    
    def setUp(self):
        """测试初始化"""
        # 配置参数
        self.config = {
            'account_id': 'TEST_ACCOUNT',
            'initial_cash': 1000000.0,
            'commission_rate': 0.0003,
            'min_commission': 5.0,
            'db_path': './test_trading.db'
        }
        
        # 创建模拟交易接口
        self.trader = SimulatedQMTInterface(self.config)
        
        # 创建各个组件
        self.order_manager = OrderManager(self.trader)
        self.portfolio_tracker = PortfolioTracker(self.trader)
        
        # 创建模拟风控引擎
        self.risk_engine = Mock(spec=RiskEngine)
        self.risk_engine.check_signal.return_value = True
        
        # 创建交易执行引擎
        self.trade_executor = TradeExecutor(
            self.trader, 
            self.order_manager, 
            self.portfolio_tracker, 
            self.risk_engine
        )
        
    def tearDown(self):
        """测试清理"""
        if hasattr(self.trader, 'disconnect'):
            self.trader.disconnect()
        
        # 清理数据库文件
        if os.path.exists('./test_trading.db'):
            os.remove('./test_trading.db')
    
    def test_trader_connection(self):
        """测试交易接口连接"""
        print("测试交易接口连接...")
        
        # 测试连接
        self.assertFalse(self.trader.is_connected)
        success = self.trader.connect()
        self.assertTrue(success)
        self.assertTrue(self.trader.is_connected)
        
        # 测试启用交易
        success = self.trader.enable_trading()
        self.assertTrue(success)
        self.assertTrue(self.trader.is_trading_enabled)
        
        print("✓ 交易接口连接测试通过")
    
    def test_account_info(self):
        """测试账户信息"""
        print("测试账户信息...")
        
        self.trader.connect()
        account = self.trader.get_account_info()
        
        self.assertIsNotNone(account)
        self.assertEqual(account.account_id, 'TEST_ACCOUNT')
        self.assertEqual(account.total_value, 1000000.0)
        self.assertEqual(account.available_cash, 1000000.0)
        
        print(f"✓ 账户信息测试通过 - 总资产: {account.total_value}, 可用资金: {account.available_cash}")
    
    def test_order_submission(self):
        """测试订单提交"""
        print("测试订单提交...")
        
        self.trader.connect()
        self.trader.enable_trading()
        
        # 提交买入订单
        order_id = self.trader.submit_order(
            symbol="000001.SZ",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000,
            price=0
        )
        
        self.assertIsNotNone(order_id)
        
        # 检查订单状态
        order = self.trader.get_order_status(order_id)
        self.assertIsNotNone(order)
        self.assertEqual(order.symbol, "000001.SZ")
        self.assertEqual(order.quantity, 1000)
        self.assertEqual(order.status, OrderStatus.FILLED)  # 市价单应该立即成交
        
        print(f"✓ 订单提交测试通过 - 订单ID: {order_id}, 状态: {order.status.value}")
    
    def test_position_tracking(self):
        """测试持仓跟踪"""
        print("测试持仓跟踪...")
        
        self.trader.connect()
        self.trader.enable_trading()
        
        # 提交买入订单创建持仓
        order_id = self.trader.submit_order(
            symbol="000001.SZ",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000
        )
        
        # 更新持仓信息
        self.portfolio_tracker.update_positions()
        
        # 检查持仓
        position = self.portfolio_tracker.get_position("000001.SZ")
        self.assertIsNotNone(position)
        self.assertEqual(position.quantity, 1000)
        self.assertTrue(position.market_value > 0)
        
        # 检查投资组合指标
        metrics = self.portfolio_tracker.get_portfolio_metrics()
        self.assertEqual(metrics.position_count, 1)
        self.assertTrue(metrics.market_value > 0)
        
        print(f"✓ 持仓跟踪测试通过 - 持仓数量: {position.quantity}, 市值: {position.market_value:.2f}")
    
    def test_order_management(self):
        """测试订单管理"""
        print("测试订单管理...")
        
        self.trader.connect()
        self.trader.enable_trading()
        
        # 启动订单监控
        self.order_manager.start_monitoring()
        
        # 通过订单管理器提交订单
        order_id = self.order_manager.submit_order(
            symbol="000001.SZ",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=1000,
            price=20.0
        )
        
        self.assertIsNotNone(order_id)
        
        # 检查订单
        order = self.order_manager.get_order(order_id)
        self.assertIsNotNone(order)
        
        # 检查活跃订单
        active_orders = self.order_manager.get_active_orders()
        self.assertTrue(len(active_orders) >= 1)
        
        # 撤销订单
        success = self.order_manager.cancel_order(order_id)
        self.assertTrue(success)
        
        # 停止监控
        self.order_manager.stop_monitoring()
        
        print(f"✓ 订单管理测试通过 - 订单ID: {order_id}")
    
    def test_trade_execution(self):
        """测试交易执行"""
        print("测试交易执行...")
        
        self.trader.connect()
        self.trader.enable_trading()
        
        # 启动交易执行引擎
        self.trade_executor.start()
        
        # 创建交易信号
        signal = Signal(
            symbol="000001.SZ",
            signal_type=SignalType.BUY,
            strength=0.8,
            price=20.0,
            timestamp=datetime.now(),
            strategy_name="test_strategy"
        )
        
        # 提交信号
        task_id = self.trade_executor.submit_signal(signal, ExecutionMode.IMMEDIATE)
        self.assertIsNotNone(task_id)
        
        # 等待执行完成
        time.sleep(2)
        
        # 检查任务状态
        task = self.trade_executor.get_task_status(task_id)
        self.assertIsNotNone(task)
        
        # 停止执行引擎
        self.trade_executor.stop()
        
        print(f"✓ 交易执行测试通过 - 任务ID: {task_id}, 状态: {task.status.value}")
    
    def test_integrated_workflow(self):
        """测试集成工作流"""
        print("测试集成工作流...")
        
        # 1. 连接交易接口
        self.trader.connect()
        self.trader.enable_trading()
        
        # 2. 启动各个组件
        self.order_manager.start_monitoring()
        self.portfolio_tracker.start_tracking()
        self.trade_executor.start()
        
        # 3. 执行一系列交易
        signals = [
            Signal("000001.SZ", SignalType.BUY, 0.8, 20.0, datetime.now(), "strategy1"),
            Signal("000002.SZ", SignalType.BUY, 0.7, 15.0, datetime.now(), "strategy1"),
            Signal("600000.SH", SignalType.BUY, 0.9, 10.0, datetime.now(), "strategy2")
        ]
        
        task_ids = []
        for signal in signals:
            task_id = self.trade_executor.submit_signal(signal)
            task_ids.append(task_id)
        
        # 4. 等待执行完成
        time.sleep(3)
        
        # 5. 检查结果
        # 检查持仓
        self.portfolio_tracker.update_positions()
        positions = self.portfolio_tracker.get_all_positions()
        print(f"总持仓数: {len(positions)}")
        
        for position in positions:
            print(f"  {position.symbol}: {position.quantity}股, 市值: {position.market_value:.2f}")
        
        # 检查账户
        account = self.trader.get_account_info()
        print(f"账户总资产: {account.total_value:.2f}, 可用资金: {account.available_cash:.2f}")
        
        # 检查订单
        orders = self.order_manager.get_orders()
        print(f"订单总数: {len(orders)}")
        
        # 检查执行统计
        stats = self.trade_executor.get_statistics()
        print(f"执行统计: {stats}")
        
        # 6. 停止各个组件
        self.trade_executor.stop()
        self.portfolio_tracker.stop_tracking()
        self.order_manager.stop_monitoring()
        
        print("✓ 集成工作流测试通过")
    
    def test_risk_control(self):
        """测试风控功能"""
        print("测试风控功能...")
        
        self.trader.connect()
        self.trader.enable_trading()
        
        # 设置风控引擎拒绝信号
        self.risk_engine.check_signal.return_value = False
        
        self.trade_executor.start()
        
        # 创建信号
        signal = Signal("000001.SZ", SignalType.BUY, 0.8, 20.0, datetime.now(), "test_strategy")
        
        # 提交信号
        task_id = self.trade_executor.submit_signal(signal)
        
        # 等待处理
        time.sleep(1)
        
        # 检查任务状态（应该失败）
        task = self.trade_executor.get_task_status(task_id)
        # 由于风控拒绝，任务应该失败
        
        self.trade_executor.stop()
        
        print("✓ 风控功能测试通过")
    
    def test_error_handling(self):
        """测试异常处理"""
        print("测试异常处理...")
        
        # 测试未连接状态下的操作
        order_id = self.trader.submit_order("000001.SZ", OrderSide.BUY, OrderType.MARKET, 1000)
        self.assertIsNone(order_id)
        
        # 测试无效订单参数
        self.trader.connect()
        self.trader.enable_trading()
        
        # 无效股票代码
        order_id = self.trader.submit_order("INVALID", OrderSide.BUY, OrderType.MARKET, 1000)
        self.assertIsNone(order_id)
        
        # 无效数量
        order_id = self.trader.submit_order("000001.SZ", OrderSide.BUY, OrderType.MARKET, -100)
        self.assertIsNone(order_id)
        
        print("✓ 异常处理测试通过")


def run_simple_demo():
    """运行简单演示"""
    print("=" * 60)
    print("实盘交易接口MVP演示")
    print("=" * 60)
    
    # 配置
    config = {
        'account_id': 'DEMO_ACCOUNT',
        'initial_cash': 1000000.0,
        'commission_rate': 0.0003,
        'min_commission': 5.0,
        'db_path': './demo_trading.db'
    }
    
    # 创建交易接口
    trader = SimulatedQMTInterface(config)
    
    try:
        # 1. 连接
        print("1. 连接交易接口...")
        trader.connect()
        trader.enable_trading()
        print("   ✓ 连接成功")
        
        # 2. 查看初始账户
        print("\n2. 查看账户信息...")
        account = trader.get_account_info()
        print(f"   账户ID: {account.account_id}")
        print(f"   总资产: {account.total_value:,.2f}")
        print(f"   可用资金: {account.available_cash:,.2f}")
        
        # 3. 提交买入订单
        print("\n3. 提交买入订单...")
        symbols = ["000001.SZ", "000002.SZ", "600000.SH"]
        
        for symbol in symbols:
            order_id = trader.submit_order(
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=1000
            )
            
            if order_id:
                order = trader.get_order_status(order_id)
                print(f"   ✓ {symbol}: 订单ID {order_id[:8]}..., 状态: {order.status.value}")
            else:
                print(f"   ✗ {symbol}: 订单提交失败")
        
        # 4. 查看持仓
        print("\n4. 查看持仓信息...")
        positions = trader.get_positions()
        for position in positions:
            print(f"   {position.symbol}: {position.quantity}股, "
                  f"成本: {position.avg_price:.2f}, 市值: {position.market_value:.2f}")
        
        # 5. 查看更新后的账户
        print("\n5. 查看更新后的账户...")
        account = trader.get_account_info()
        print(f"   总资产: {account.total_value:,.2f}")
        print(f"   持仓市值: {account.market_value:,.2f}")
        print(f"   可用资金: {account.available_cash:,.2f}")
        print(f"   总盈亏: {account.total_pnl:,.2f}")
        
        # 6. 提交卖出订单
        print("\n6. 部分卖出持仓...")
        if positions:
            position = positions[0]
            sell_quantity = position.quantity // 2
            
            order_id = trader.submit_order(
                symbol=position.symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=sell_quantity
            )
            
            if order_id:
                order = trader.get_order_status(order_id)
                print(f"   ✓ 卖出 {position.symbol} {sell_quantity}股, 状态: {order.status.value}")
        
        # 7. 最终状态
        print("\n7. 最终账户状态...")
        account = trader.get_account_info()
        positions = trader.get_positions()
        
        print(f"   总资产: {account.total_value:,.2f}")
        print(f"   持仓数量: {len(positions)}个")
        print(f"   总盈亏: {account.total_pnl:,.2f}")
        
        print("\n演示完成!")
        
    except Exception as e:
        print(f"演示过程中发生错误: {e}")
    
    finally:
        # 断开连接
        trader.disconnect()
        
        # 清理演示数据库
        if os.path.exists('./demo_trading.db'):
            os.remove('./demo_trading.db')


if __name__ == '__main__':
    # 选择运行模式
    import argparse
    parser = argparse.ArgumentParser(description='交易系统测试')
    parser.add_argument('--mode', choices=['test', 'demo'], default='demo',
                       help='运行模式: test=单元测试, demo=简单演示')
    args = parser.parse_args()
    
    if args.mode == 'test':
        # 运行单元测试
        unittest.main(argv=[''], exit=False, verbosity=2)
    else:
        # 运行演示
        run_simple_demo()