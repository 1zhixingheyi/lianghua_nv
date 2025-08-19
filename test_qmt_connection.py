#!/usr/bin/env python3
"""
QMT连接测试脚本

测试国金证券QMT接口连接和基本功能
"""

import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.trading.live_qmt_interface import LiveQMTInterface, QMTConfig

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_qmt_connection():
    """测试QMT连接"""
    print("=" * 60)
    print("🚀 国金证券QMT接口连接测试")
    print("=" * 60)
    
    try:
        # 从环境变量读取配置
        qmt_config = {
            'qmt': {
                'host': os.getenv('QMT_HOST', 'localhost'),
                'port': int(os.getenv('QMT_PORT', 16099)),
                'account_id': os.getenv('QMT_ACCOUNT_ID'),
                'account_type': os.getenv('QMT_ACCOUNT_TYPE', 'STOCK'),
                'timeout': int(os.getenv('QMT_TIMEOUT', 30)),
                'max_retries': int(os.getenv('QMT_MAX_RETRIES', 3)),
                'retry_delay': float(os.getenv('QMT_RETRY_DELAY', 1.0)),
                'trading_password': os.getenv('QMT_PASSWORD'),
                'authentication_method': os.getenv('AUTHENTICATION_METHOD', 'password'),
                'encryption_enabled': os.getenv('ENCRYPTION_ENABLED', 'true').lower() == 'true',
                'enable_order_verification': os.getenv('ENABLE_ORDER_VERIFICATION', 'true').lower() == 'true',
                'max_single_order_value': float(os.getenv('MAX_SINGLE_ORDER_VALUE', 50000)),
                'max_daily_trades': int(os.getenv('MAX_DAILY_TRADES', 100)),
                'enable_market_hours_check': os.getenv('ENABLE_MARKET_HOURS_CHECK', 'true').lower() == 'true'
            },
            'account_id': os.getenv('QMT_ACCOUNT_ID'),
            'db_path': 'test_qmt_trading.db'
        }
        
        print(f"📋 连接配置:")
        print(f"   主机: {qmt_config['qmt']['host']}")
        print(f"   端口: {qmt_config['qmt']['port']}")
        print(f"   账号: {qmt_config['qmt']['account_id']}")
        print(f"   账户类型: {qmt_config['qmt']['account_type']}")
        print(f"   超时设置: {qmt_config['qmt']['timeout']}秒")
        print()
        
        # 创建QMT接口实例
        print("🔧 创建QMT接口实例...")
        qmt_interface = LiveQMTInterface(qmt_config)
        
        # 测试连接
        print("🔗 测试QMT连接...")
        if qmt_interface.connect():
            print("✅ QMT连接成功!")
            
            # 测试账户信息
            print("\n📊 获取账户信息...")
            account_info = qmt_interface.get_account_info()
            if account_info:
                print(f"✅ 账户信息获取成功:")
                print(f"   账户ID: {account_info.account_id}")
                print(f"   总资产: {account_info.total_value:,.2f}")
                print(f"   可用资金: {account_info.available_cash:,.2f}")
                print(f"   总现金: {account_info.total_cash:,.2f}")
                print(f"   市值: {account_info.market_value:,.2f}")
                print(f"   总盈亏: {account_info.total_pnl:,.2f}")
            else:
                print("❌ 账户信息获取失败")
            
            # 测试持仓信息
            print("\n📈 获取持仓信息...")
            positions = qmt_interface.get_positions()
            if positions:
                print(f"✅ 持仓信息获取成功，共{len(positions)}只股票:")
                for pos in positions[:5]:  # 只显示前5只
                    print(f"   {pos.symbol}: {pos.quantity}股, 均价{pos.avg_price:.2f}, 市值{pos.market_value:,.2f}")
            else:
                print("✅ 持仓信息获取成功，当前无持仓")
            
            # 测试订单信息
            print("\n📋 获取订单信息...")
            orders = qmt_interface.get_orders()
            if orders:
                print(f"✅ 订单信息获取成功，共{len(orders)}个订单:")
                for order in orders[-5:]:  # 只显示最近5个
                    print(f"   {order.order_id}: {order.symbol} {order.side.value} {order.quantity}股 @ {order.price:.2f}")
            else:
                print("✅ 订单信息获取成功，当前无订单")
            
            # 测试连接统计
            print("\n📊 连接统计信息:")
            stats = qmt_interface.get_connection_stats()
            print(f"   连接状态: {'✅ 已连接' if stats['is_connected'] else '❌ 未连接'}")
            print(f"   重试次数: {stats['connection_retry_count']}")
            print(f"   今日交易次数: {stats['daily_trade_count']}")
            print(f"   今日交易金额: {stats['daily_trade_value']:,.2f}")
            print(f"   总请求数: {stats['stats']['total_requests']}")
            print(f"   成功请求数: {stats['stats']['successful_requests']}")
            print(f"   失败请求数: {stats['stats']['failed_requests']}")
            
            # 断开连接
            print("\n🔌 断开QMT连接...")
            if qmt_interface.disconnect():
                print("✅ QMT连接断开成功!")
            else:
                print("❌ QMT连接断开失败")
                
        else:
            print("❌ QMT连接失败!")
            print("🔍 可能的原因:")
            print("   1. QMT客户端未启动")
            print("   2. 端口配置错误")
            print("   3. 账号密码错误")
            print("   4. 网络连接问题")
            
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {e}")
        logger.exception("QMT连接测试异常")
        
    print("\n" + "=" * 60)
    print("🏁 QMT连接测试完成")
    print("=" * 60)

def test_qmt_trading_functions():
    """测试QMT交易功能（模拟模式）"""
    print("\n" + "=" * 60)
    print("🧪 QMT交易功能测试（模拟模式）")
    print("=" * 60)
    
    try:
        # 使用模拟配置
        from src.trading.qmt_interface import SimulatedQMTInterface
        from src.trading.base_trader import OrderSide, OrderType
        
        config = {
            'account_id': os.getenv('QMT_ACCOUNT_ID'),
            'initial_cash': 100000.0,
            'commission_rate': 0.0003,
            'min_commission': 5.0,
            'db_path': 'test_simulation.db'
        }
        
        print("🔧 创建模拟交易接口...")
        sim_interface = SimulatedQMTInterface(config)
        
        # 连接
        if sim_interface.connect():
            print("✅ 模拟接口连接成功!")
            
            # 启用交易
            if sim_interface.enable_trading():
                print("✅ 交易功能已启用!")
                
                # 测试买入订单
                print("\n📈 测试买入订单...")
                symbol = "000001.SZ"  # 平安银行
                buy_order_id = sim_interface.submit_order(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=100
                )
                
                if buy_order_id:
                    print(f"✅ 买入订单提交成功: {buy_order_id}")
                    
                    # 查询订单状态
                    order_status = sim_interface.get_order_status(buy_order_id)
                    if order_status:
                        print(f"   订单状态: {order_status.status.value}")
                        print(f"   成交数量: {order_status.filled_quantity}")
                        print(f"   成交均价: {order_status.avg_fill_price:.2f}")
                else:
                    print("❌ 买入订单提交失败")
                
                # 测试卖出订单
                print("\n📉 测试卖出订单...")
                sell_order_id = sim_interface.submit_order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=50
                )
                
                if sell_order_id:
                    print(f"✅ 卖出订单提交成功: {sell_order_id}")
                else:
                    print("❌ 卖出订单提交失败")
                
                # 查看账户信息
                print("\n📊 查看账户信息...")
                account = sim_interface.get_account_info()
                if account:
                    print(f"   总资产: {account.total_value:,.2f}")
                    print(f"   可用资金: {account.available_cash:,.2f}")
                    print(f"   总盈亏: {account.total_pnl:,.2f}")
                
                # 查看持仓
                print("\n📈 查看持仓...")
                positions = sim_interface.get_positions()
                for pos in positions:
                    print(f"   {pos.symbol}: {pos.quantity}股, 均价{pos.avg_price:.2f}")
                
            sim_interface.disconnect()
            print("✅ 模拟接口断开成功!")
            
    except Exception as e:
        print(f"❌ 模拟测试异常: {e}")
        logger.exception("模拟交易测试异常")

if __name__ == "__main__":
    # 测试QMT连接
    test_qmt_connection()
    
    # 测试交易功能（模拟模式）
    test_qmt_trading_functions()
    
    print(f"\n🕒 测试完成时间: {datetime.now()}")