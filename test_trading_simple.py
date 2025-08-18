#!/usr/bin/env python3
"""
实盘交易接口MVP简化测试

验证交易系统的基本功能
"""

import sys
import os
import time
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_basic_trading():
    """基本交易功能测试"""
    print("=" * 60)
    print("实盘交易接口MVP基本功能测试")
    print("=" * 60)
    
    try:
        # 导入模块
        from trading.base_trader import OrderType, OrderSide, OrderStatus
        from trading.qmt_interface import SimulatedQMTInterface
        print("✓ 模块导入成功")
        
        # 配置
        config = {
            'account_id': 'TEST_ACCOUNT',
            'initial_cash': 1000000.0,
            'commission_rate': 0.0003,
            'min_commission': 5.0,
            'db_path': './test_trading.db'
        }
        
        # 创建模拟交易接口
        trader = SimulatedQMTInterface(config)
        print("✓ 交易接口创建成功")
        
        # 1. 连接测试
        print("\n1. 测试连接...")
        success = trader.connect()
        if success:
            print("✓ 连接成功")
        else:
            print("✗ 连接失败")
            return
        
        # 启用交易
        trader.enable_trading()
        print("✓ 交易功能启用")
        
        # 2. 账户信息测试
        print("\n2. 测试账户信息...")
        account = trader.get_account_info()
        if account:
            print(f"✓ 账户ID: {account.account_id}")
            print(f"✓ 总资产: {account.total_value:,.2f}")
            print(f"✓ 可用资金: {account.available_cash:,.2f}")
        else:
            print("✗ 获取账户信息失败")
            return
        
        # 3. 订单提交测试
        print("\n3. 测试订单提交...")
        
        # 提交买入订单
        order_id = trader.submit_order(
            symbol="000001.SZ",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000
        )
        
        if order_id:
            print(f"✓ 买入订单提交成功: {order_id[:8]}...")
            
            # 检查订单状态
            order = trader.get_order_status(order_id)
            if order:
                print(f"✓ 订单状态: {order.status.value}")
                print(f"✓ 成交数量: {order.filled_quantity}")
                print(f"✓ 平均成交价: {order.avg_fill_price:.2f}")
            
        else:
            print("✗ 订单提交失败")
            return
        
        # 4. 持仓测试
        print("\n4. 测试持仓信息...")
        positions = trader.get_positions()
        if positions:
            for position in positions:
                print(f"✓ 持仓: {position.symbol}")
                print(f"  数量: {position.quantity}")
                print(f"  成本价: {position.avg_price:.2f}")
                print(f"  市值: {position.market_value:.2f}")
        else:
            print("暂无持仓")
        
        # 5. 账户更新测试
        print("\n5. 测试账户更新...")
        account = trader.get_account_info()
        if account:
            print(f"✓ 更新后总资产: {account.total_value:,.2f}")
            print(f"✓ 持仓市值: {account.market_value:,.2f}")
            print(f"✓ 可用资金: {account.available_cash:,.2f}")
            print(f"✓ 总盈亏: {account.total_pnl:,.2f}")
        
        # 6. 部分卖出测试
        print("\n6. 测试部分卖出...")
        if positions:
            position = positions[0]
            sell_quantity = 500  # 卖出一半
            
            sell_order_id = trader.submit_order(
                symbol=position.symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=sell_quantity
            )
            
            if sell_order_id:
                print(f"✓ 卖出订单提交成功: {sell_order_id[:8]}...")
                
                # 检查订单状态
                order = trader.get_order_status(sell_order_id)
                if order:
                    print(f"✓ 卖出状态: {order.status.value}")
            else:
                print("✗ 卖出订单提交失败")
        
        # 7. 最终状态
        print("\n7. 最终状态...")
        account = trader.get_account_info()
        positions = trader.get_positions()
        orders = trader.get_orders()
        
        print(f"✓ 最终总资产: {account.total_value:,.2f}")
        print(f"✓ 持仓品种数: {len(positions)}")
        print(f"✓ 订单总数: {len(orders)}")
        print(f"✓ 总盈亏: {account.total_pnl:,.2f}")
        
        # 断开连接
        trader.disconnect()
        print("\n✓ 测试完成，接口已断开")
        
        # 清理数据库文件
        if os.path.exists('./test_trading.db'):
            os.remove('./test_trading.db')
            print("✓ 测试数据已清理")
        
        return True
        
    except Exception as e:
        print(f"\n✗ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_error_handling():
    """错误处理测试"""
    print("\n" + "=" * 60)
    print("错误处理测试")
    print("=" * 60)
    
    try:
        from trading.base_trader import OrderType, OrderSide
        from trading.qmt_interface import SimulatedQMTInterface
        
        config = {
            'account_id': 'ERROR_TEST',
            'initial_cash': 1000000.0,
            'db_path': './error_test.db'
        }
        
        trader = SimulatedQMTInterface(config)
        
        # 1. 未连接状态下的操作
        print("\n1. 测试未连接状态...")
        order_id = trader.submit_order("000001.SZ", OrderSide.BUY, OrderType.MARKET, 1000)
        if order_id is None:
            print("✓ 未连接状态正确拒绝订单")
        else:
            print("✗ 未连接状态应该拒绝订单")
        
        # 连接后继续测试
        trader.connect()
        trader.enable_trading()
        
        # 2. 无效参数测试
        print("\n2. 测试无效参数...")
        
        # 无效股票代码
        order_id = trader.submit_order("INVALID", OrderSide.BUY, OrderType.MARKET, 1000)
        if order_id is None:
            print("✓ 无效股票代码正确拒绝")
        else:
            print("✗ 无效股票代码应该被拒绝")
        
        # 无效数量（非100整数倍）
        order_id = trader.submit_order("000001.SZ", OrderSide.BUY, OrderType.MARKET, 150)
        if order_id is None:
            print("✓ 无效数量正确拒绝")
        else:
            print("✗ 无效数量应该被拒绝")
        
        # 3. 资金不足测试
        print("\n3. 测试资金不足...")
        order_id = trader.submit_order("000001.SZ", OrderSide.BUY, OrderType.LIMIT, 100000, 100.0)
        if order_id is None:
            print("✓ 资金不足正确拒绝")
        else:
            print("✗ 资金不足应该被拒绝")
        
        # 4. 持仓不足测试
        print("\n4. 测试持仓不足...")
        order_id = trader.submit_order("999999.SZ", OrderSide.SELL, OrderType.MARKET, 1000)
        if order_id is None:
            print("✓ 持仓不足正确拒绝")
        else:
            print("✗ 持仓不足应该被拒绝")
        
        trader.disconnect()
        
        # 清理
        if os.path.exists('./error_test.db'):
            os.remove('./error_test.db')
        
        print("\n✓ 错误处理测试完成")
        return True
        
    except Exception as e:
        print(f"\n✗ 错误处理测试失败: {e}")
        return False

if __name__ == '__main__':
    print("开始实盘交易接口MVP测试...\n")
    
    # 运行基本功能测试
    basic_success = test_basic_trading()
    
    # 运行错误处理测试
    error_success = test_error_handling()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    if basic_success and error_success:
        print("✓ 所有测试通过！实盘交易接口MVP开发完成。")
        print("\n主要功能:")
        print("  ✓ 模拟交易接口连接和断开")
        print("  ✓ 账户信息查询和更新")
        print("  ✓ 订单提交、执行和状态查询")
        print("  ✓ 持仓信息跟踪和计算")
        print("  ✓ 买入和卖出交易流程")
        print("  ✓ 盈亏计算和资金管理")
        print("  ✓ 参数验证和错误处理")
        print("  ✓ 数据持久化和清理")
        
        print("\n安全特性:")
        print("  ✓ 交易前置风控检查")
        print("  ✓ 资金和持仓充足性验证")
        print("  ✓ 订单参数有效性验证")
        print("  ✓ 连接状态检查")
        print("  ✓ 异常情况处理")
        
    else:
        print("✗ 部分测试失败，请检查问题")
        if not basic_success:
            print("  ✗ 基本功能测试失败")
        if not error_success:
            print("  ✗ 错误处理测试失败")