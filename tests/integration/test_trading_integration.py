"""
交易模块集成测试
测试交易执行、订单管理和风险控制的完整流程
"""

import pytest
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import threading
import time

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.trading.trade_executor import TradeExecutor
from src.trading.base_trader import BaseTrader
from src.risk.risk_engine import RiskEngine
from src.risk.position_manager import PositionManager
from src.risk.money_manager import MoneyManager


class TestTradingIntegration:
    """交易集成测试类"""
    
    @pytest.fixture(autouse=True)
    def setup(self, test_config, mock_trader, mock_risk_manager):
        """测试设置"""
        self.config = test_config
        self.mock_trader = mock_trader
        self.risk_manager = mock_risk_manager
        self.trade_executor = TradeExecutor(mock_trader)
        
        # 初始化投资组合
        self.portfolio = {
            'cash': 1000000.0,
            'positions': {
                '000001.SZ': {'quantity': 1000, 'avg_price': 10.0, 'market_value': 10000},
                '000002.SZ': {'quantity': 500, 'avg_price': 20.0, 'market_value': 10000}
            },
            'total_value': 1020000.0,
            'available_cash': 800000.0
        }
    
    @pytest.mark.integration
    def test_trade_execution_workflow(self):
        """测试交易执行工作流"""
        # 1. 连接交易接口
        assert self.trade_executor.connect()
        assert self.trade_executor.is_connected()
        
        # 2. 创建买入订单
        buy_order = {
            'stock_code': '000003.SZ',
            'action': 'buy',
            'quantity': 1000,
            'price': 15.0,
            'order_type': 'limit'
        }
        
        # 3. 提交订单
        result = self.trade_executor.submit_order(buy_order)
        assert result is not None
        assert result['status'] == 'filled'
        assert result['stock_code'] == '000003.SZ'
        assert result['action'] == 'buy'
        
        # 4. 验证订单记录
        assert len(self.mock_trader.executed_trades) == 1
        
        # 5. 创建卖出订单
        sell_order = {
            'stock_code': '000001.SZ',
            'action': 'sell',
            'quantity': 500,
            'price': 10.5,
            'order_type': 'limit'
        }
        
        # 6. 提交卖出订单
        sell_result = self.trade_executor.submit_order(sell_order)
        assert sell_result['status'] == 'filled'
        assert sell_result['action'] == 'sell'
        
        # 7. 验证交易记录
        assert len(self.mock_trader.executed_trades) == 2
    
    @pytest.mark.integration
    def test_risk_controlled_trading(self):
        """测试风控约束下的交易"""
        # 1. 创建风险引擎
        risk_config = {
            'max_position': 0.1,  # 最大持仓比例
            'max_single_stock': 0.05,  # 单股最大比例
            'stop_loss': 0.05,  # 止损比例
            'max_drawdown': 0.1  # 最大回撤
        }
        
        risk_engine = RiskEngine(risk_config)
        
        # 2. 创建大额交易信号（应该被风控限制）
        large_order = {
            'stock_code': '000004.SZ',
            'action': 'buy',
            'quantity': 10000,  # 大量订单
            'price': 50.0,  # 高价股票
            'strategy': 'test_strategy'
        }
        
        # 3. 风控检查
        risk_result = risk_engine.check_trade(large_order, self.portfolio)
        
        # 4. 验证风控结果
        if not risk_result['approved']:
            # 订单被拒绝
            assert 'risk_level' in risk_result
            assert 'warnings' in risk_result
        else:
            # 订单被调整
            assert risk_result['adjusted_quantity'] < large_order['quantity']
        
        # 5. 根据风控结果执行交易
        if risk_result['approved']:
            adjusted_order = large_order.copy()
            adjusted_order['quantity'] = risk_result['adjusted_quantity']
            
            result = self.trade_executor.submit_order(adjusted_order)
            assert result['status'] == 'filled'
            assert result['quantity'] == risk_result['adjusted_quantity']
    
    @pytest.mark.integration
    def test_position_management_integration(self):
        """测试持仓管理集成"""
        # 1. 创建持仓管理器
        position_manager = PositionManager(max_positions=10)
        
        # 2. 初始化持仓
        for stock_code, position in self.portfolio['positions'].items():
            position_manager.add_position(
                stock_code=stock_code,
                quantity=position['quantity'],
                price=position['avg_price']
            )
        
        # 3. 验证初始持仓
        assert len(position_manager.positions) == 2
        assert position_manager.get_position('000001.SZ') is not None
        
        # 4. 测试新增持仓
        new_trade = {
            'stock_code': '000003.SZ',
            'action': 'buy',
            'quantity': 800,
            'price': 25.0
        }
        
        position_manager.update_position(new_trade)
        assert len(position_manager.positions) == 3
        
        new_position = position_manager.get_position('000003.SZ')
        assert new_position['quantity'] == 800
        assert new_position['avg_price'] == 25.0
        
        # 5. 测试增加持仓
        add_trade = {
            'stock_code': '000003.SZ',
            'action': 'buy',
            'quantity': 200,
            'price': 26.0
        }
        
        position_manager.update_position(add_trade)
        updated_position = position_manager.get_position('000003.SZ')
        assert updated_position['quantity'] == 1000
        # 验证平均价格计算
        expected_avg = (800 * 25.0 + 200 * 26.0) / 1000
        assert abs(updated_position['avg_price'] - expected_avg) < 0.01
        
        # 6. 测试减少持仓
        reduce_trade = {
            'stock_code': '000001.SZ',
            'action': 'sell',
            'quantity': 300,
            'price': 10.5
        }
        
        position_manager.update_position(reduce_trade)
        reduced_position = position_manager.get_position('000001.SZ')
        assert reduced_position['quantity'] == 700
        
        # 7. 测试清仓
        clear_trade = {
            'stock_code': '000002.SZ',
            'action': 'sell',
            'quantity': 500,
            'price': 21.0
        }
        
        position_manager.update_position(clear_trade)
        assert position_manager.get_position('000002.SZ') is None
        assert len(position_manager.positions) == 2
    
    @pytest.mark.integration
    def test_money_management_integration(self):
        """测试资金管理集成"""
        # 1. 创建资金管理器
        money_manager = MoneyManager(
            initial_capital=1000000.0,
            reserve_ratio=0.1  # 保留10%现金
        )
        
        # 2. 设置当前持仓价值
        money_manager.update_portfolio_value(self.portfolio['total_value'])
        
        # 3. 测试可用资金计算
        available_cash = money_manager.get_available_cash()
        expected_available = self.portfolio['available_cash']
        assert abs(available_cash - expected_available) < 1.0
        
        # 4. 测试交易资金检查
        trade_amount = 50000.0  # 5万元交易
        can_trade = money_manager.can_afford_trade(trade_amount)
        assert can_trade  # 应该有足够资金
        
        # 5. 测试大额交易检查
        large_trade_amount = 900000.0  # 90万元交易
        can_large_trade = money_manager.can_afford_trade(large_trade_amount)
        assert not can_large_trade  # 应该资金不足
        
        # 6. 测试交易后资金更新
        successful_trade = {
            'action': 'buy',
            'quantity': 1000,
            'price': 30.0,
            'commission': 9.0,  # 手续费
            'stamp_tax': 0.0   # 买入无印花税
        }
        
        money_manager.update_after_trade(successful_trade)
        
        # 验证资金变化
        expected_cash_used = 1000 * 30.0 + 9.0
        updated_available = money_manager.get_available_cash()
        assert abs(updated_available - (available_cash - expected_cash_used)) < 1.0
    
    @pytest.mark.integration
    def test_order_management_workflow(self):
        """测试订单管理工作流"""
        # 1. 创建订单管理器
        order_manager = self.trade_executor.order_manager
        
        # 2. 提交多个订单
        orders = [
            {
                'stock_code': '000001.SZ',
                'action': 'buy',
                'quantity': 500,
                'price': 10.2,
                'order_type': 'limit'
            },
            {
                'stock_code': '000002.SZ',
                'action': 'sell',
                'quantity': 200,
                'price': 20.5,
                'order_type': 'limit'
            },
            {
                'stock_code': '000003.SZ',
                'action': 'buy',
                'quantity': 800,
                'price': 15.0,
                'order_type': 'market'
            }
        ]
        
        order_ids = []
        for order in orders:
            result = self.trade_executor.submit_order(order)
            order_ids.append(result['order_id'])
        
        # 3. 验证订单状态
        assert len(order_ids) == 3
        for order_id in order_ids:
            order_status = self.trade_executor.get_order_status(order_id)
            assert order_status is not None
            assert order_status['status'] in ['filled', 'pending', 'partial']
        
        # 4. 测试订单查询
        all_orders = self.trade_executor.get_all_orders()
        assert len(all_orders) >= 3
        
        # 5. 测试订单取消（如果支持）
        if hasattr(self.trade_executor, 'cancel_order'):
            # 创建一个新订单用于取消测试
            cancel_order = {
                'stock_code': '000004.SZ',
                'action': 'buy',
                'quantity': 1000,
                'price': 25.0,
                'order_type': 'limit'
            }
            
            cancel_result = self.trade_executor.submit_order(cancel_order)
            cancel_order_id = cancel_result['order_id']
            
            # 尝试取消订单
            cancel_success = self.trade_executor.cancel_order(cancel_order_id)
            if cancel_success:
                cancelled_status = self.trade_executor.get_order_status(cancel_order_id)
                assert cancelled_status['status'] == 'cancelled'
    
    @pytest.mark.integration
    def test_account_synchronization(self):
        """测试账户同步"""
        # 1. 获取账户信息
        account_info = self.trade_executor.get_account_info()
        assert account_info is not None
        assert 'total_asset' in account_info
        assert 'available_cash' in account_info
        
        # 2. 获取持仓信息
        positions = self.trade_executor.get_positions()
        assert isinstance(positions, list)
        
        # 3. 同步本地持仓与服务器持仓
        local_positions = self.portfolio['positions']
        server_positions = {pos['stock_code']: pos for pos in positions}
        
        # 验证关键持仓的一致性
        for stock_code in local_positions:
            if stock_code in server_positions:
                local_qty = local_positions[stock_code]['quantity']
                server_qty = server_positions[stock_code]['quantity']
                # 允许小幅差异（可能由于部分成交等原因）
                assert abs(local_qty - server_qty) <= local_qty * 0.1
        
        # 4. 测试资金同步
        local_cash = self.portfolio['available_cash']
        server_cash = account_info['available_cash']
        # 资金可能有延迟，允许一定差异
        cash_diff_ratio = abs(local_cash - server_cash) / max(local_cash, server_cash)
        assert cash_diff_ratio < 0.05  # 差异小于5%
    
    @pytest.mark.integration
    def test_trading_with_market_data(self, mock_stock_data):
        """测试结合市场数据的交易"""
        # 1. 获取实时价格
        stock_data = mock_stock_data[mock_stock_data['ts_code'] == '000001.SZ'].iloc[-1]
        current_price = stock_data['close']
        
        # 2. 创建基于市场价格的订单
        market_order = {
            'stock_code': '000001.SZ',
            'action': 'buy',
            'quantity': 1000,
            'price': current_price * 1.01,  # 稍高于市价买入
            'order_type': 'limit'
        }
        
        # 3. 提交订单
        result = self.trade_executor.submit_order(market_order)
        assert result['status'] == 'filled'
        
        # 4. 验证成交价格合理性
        filled_price = result['price']
        price_diff_ratio = abs(filled_price - current_price) / current_price
        assert price_diff_ratio < 0.05  # 成交价与市价差异小于5%
        
        # 5. 测试止损订单
        stop_loss_price = current_price * 0.95  # 5%止损
        stop_order = {
            'stock_code': '000001.SZ',
            'action': 'sell',
            'quantity': 500,
            'price': stop_loss_price,
            'order_type': 'stop_loss'
        }
        
        if hasattr(self.trade_executor, 'submit_stop_order'):
            stop_result = self.trade_executor.submit_stop_order(stop_order)
            assert stop_result is not None
    
    @pytest.mark.integration
    def test_concurrent_trading(self):
        """测试并发交易"""
        import threading
        import time
        
        results = []
        errors = []
        
        def execute_trade(thread_id):
            """并发执行交易"""
            try:
                for i in range(3):
                    order = {
                        'stock_code': f'00000{thread_id}.SZ',
                        'action': 'buy' if i % 2 == 0 else 'sell',
                        'quantity': (i + 1) * 100,
                        'price': 10.0 + i,
                        'order_type': 'limit'
                    }
                    
                    result = self.trade_executor.submit_order(order)
                    results.append((thread_id, result))
                    time.sleep(0.1)  # 短暂延迟
                    
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # 启动多个并发交易线程
        threads = []
        for i in range(3):
            t = threading.Thread(target=execute_trade, args=(i,))
            threads.append(t)
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join()
        
        # 验证并发交易结果
        assert len(errors) == 0, f"并发交易出现错误: {errors}"
        assert len(results) == 9  # 3个线程 × 3次交易
        
        # 验证所有交易都成功
        for thread_id, result in results:
            assert result['status'] == 'filled'
    
    @pytest.mark.integration
    def test_trading_error_handling(self):
        """测试交易错误处理"""
        # 1. 测试无效股票代码
        invalid_order = {
            'stock_code': 'INVALID.XX',
            'action': 'buy',
            'quantity': 1000,
            'price': 10.0
        }
        
        with pytest.raises(Exception):
            self.trade_executor.submit_order(invalid_order)
        
        # 2. 测试资金不足
        # 修改mock trader行为以模拟资金不足
        original_submit = self.mock_trader.submit_order
        
        def insufficient_funds_submit(order):
            if order['action'] == 'buy' and order['quantity'] * order['price'] > 100000:
                raise Exception("资金不足")
            return original_submit(order)
        
        self.mock_trader.submit_order = insufficient_funds_submit
        
        large_order = {
            'stock_code': '000001.SZ',
            'action': 'buy',
            'quantity': 50000,
            'price': 10.0
        }
        
        with pytest.raises(Exception) as exc_info:
            self.trade_executor.submit_order(large_order)
        assert "资金不足" in str(exc_info.value)
        
        # 恢复原始行为
        self.mock_trader.submit_order = original_submit
        
        # 3. 测试网络连接异常
        self.mock_trader.connected = False
        
        network_order = {
            'stock_code': '000001.SZ',
            'action': 'buy',
            'quantity': 1000,
            'price': 10.0
        }
        
        with pytest.raises(Exception):
            self.trade_executor.submit_order(network_order)
        
        # 恢复连接
        self.mock_trader.connected = True
    
    @pytest.mark.integration
    @pytest.mark.performance
    def test_trading_performance(self, performance_monitor):
        """测试交易性能"""
        performance_monitor.start()
        
        # 批量提交订单
        orders = []
        for i in range(100):
            order = {
                'stock_code': f'{i%10:06d}.SZ',
                'action': 'buy' if i % 2 == 0 else 'sell',
                'quantity': (i % 10 + 1) * 100,
                'price': 10.0 + (i % 5),
                'order_type': 'limit'
            }
            orders.append(order)
        
        # 批量执行
        results = []
        for order in orders:
            result = self.trade_executor.submit_order(order)
            results.append(result)
        
        performance_stats = performance_monitor.stop()
        
        # 性能验证
        assert performance_stats['execution_time'] < 30  # 30秒内完成
        assert len(results) == 100
        assert all(r['status'] == 'filled' for r in results)
        
        print(f"交易性能测试: {performance_stats}")
        print(f"平均每笔交易时间: {performance_stats['execution_time']/100:.4f}秒")
    
    @pytest.mark.integration
    def test_trading_state_recovery(self, temp_dir):
        """测试交易状态恢复"""
        # 1. 执行一些交易
        orders = [
            {
                'stock_code': '000001.SZ',
                'action': 'buy',
                'quantity': 1000,
                'price': 10.0
            },
            {
                'stock_code': '000002.SZ',
                'action': 'sell',
                'quantity': 500,
                'price': 20.0
            }
        ]
        
        for order in orders:
            self.trade_executor.submit_order(order)
        
        # 2. 保存交易状态
        state_file = os.path.join(temp_dir, "trading_state.json")
        self.trade_executor.save_state(state_file)
        assert os.path.exists(state_file)
        
        # 3. 创建新的交易执行器并恢复状态
        new_trader = Mock()
        new_trader.executed_trades = []
        new_trader.connected = True
        
        new_executor = TradeExecutor(new_trader)
        new_executor.load_state(state_file)
        
        # 4. 验证状态恢复
        # 这里根据实际实现验证状态恢复的正确性
        # 例如：订单历史、持仓状态等
        
        # 5. 验证新执行器可以正常工作
        test_order = {
            'stock_code': '000003.SZ',
            'action': 'buy',
            'quantity': 800,
            'price': 15.0
        }
        
        result = new_executor.submit_order(test_order)
        assert result['status'] == 'filled'


if __name__ == "__main__":
    # 运行交易集成测试
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short",
        "-m", "integration"
    ])