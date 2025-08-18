"""
风控系统测试脚本
==============

测试风控系统的各项功能，包括：
- 基础风控规则测试
- 仓位管理测试
- 资金管理测试
- 风控监控测试
- 风控引擎集成测试
"""

import sys
import os
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入风控模块
from src.risk.risk_config import RiskConfig, RiskLevel, RiskEventType
from src.risk.base_risk import BaseRiskManager, RiskCheckStatus
from src.risk.position_manager import PositionManager, PositionType
from src.risk.money_manager import MoneyManager, FundType
from src.risk.risk_monitor import RiskMonitor
from src.risk.risk_engine import RiskEngine, StrategyRiskAdapter, BacktestRiskAdapter

# 导入策略模块
from src.strategies.base_strategy import Signal, SignalType


class TestRiskConfig(unittest.TestCase):
    """测试风控配置模块"""
    
    def setUp(self):
        self.risk_config = RiskConfig()
    
    def test_default_config(self):
        """测试默认配置"""
        self.assertEqual(self.risk_config.position_limits.max_single_position_ratio, 0.20)
        self.assertEqual(self.risk_config.price_limits.stop_loss_ratio, 0.05)
        self.assertEqual(self.risk_config.capital_limits.min_cash_ratio, 0.05)
    
    def test_parameter_update(self):
        """测试参数更新"""
        # 测试有效参数更新
        result = self.risk_config.update_parameter('position_limits', 'max_single_position_ratio', 0.15)
        self.assertTrue(result)
        self.assertEqual(self.risk_config.position_limits.max_single_position_ratio, 0.15)
        
        # 测试无效参数更新
        result = self.risk_config.update_parameter('position_limits', 'invalid_param', 0.1)
        self.assertFalse(result)
    
    def test_config_validation(self):
        """测试配置验证"""
        validation_results = self.risk_config.validate_all_config()
        self.assertIn('errors', validation_results)
        self.assertIn('warnings', validation_results)
    
    def test_risk_event_management(self):
        """测试风控事件管理"""
        from src.risk.risk_config import RiskEvent
        
        event = RiskEvent(
            event_type=RiskEventType.STOP_LOSS,
            symbol="000001.SZ",
            timestamp=datetime.now(),
            risk_level=RiskLevel.HIGH,
            message="测试止损事件"
        )
        
        self.risk_config.add_risk_event(event)
        recent_events = self.risk_config.get_recent_events(1)
        self.assertEqual(len(recent_events), 1)
        self.assertEqual(recent_events[0].symbol, "000001.SZ")


class TestBaseRiskManager(unittest.TestCase):
    """测试基础风控管理器"""
    
    def setUp(self):
        self.risk_config = RiskConfig()
        self.risk_manager = BaseRiskManager(self.risk_config)
    
    def test_stop_loss_rule(self):
        """测试止损规则"""
        result = self.risk_manager.check_single_rule(
            'stop_loss',
            symbol="000001.SZ",
            current_price=9.0,
            avg_price=10.0,
            position_size=1000
        )
        
        # 亏损10%，超过默认5%止损线
        self.assertIsNotNone(result)
        self.assertEqual(result.status, RiskCheckStatus.BLOCKED)
        self.assertTrue(len(result.violations) > 0)
    
    def test_trading_time_rule(self):
        """测试交易时间规则"""
        # 测试交易时间内
        trading_time = datetime.now().replace(hour=10, minute=30)
        result = self.risk_manager.check_single_rule('trading_time', current_time=trading_time)
        self.assertEqual(result.status, RiskCheckStatus.PASS)
        
        # 测试交易时间外
        non_trading_time = datetime.now().replace(hour=20, minute=0)
        result = self.risk_manager.check_single_rule('trading_time', current_time=non_trading_time)
        self.assertEqual(result.status, RiskCheckStatus.BLOCKED)
    
    def test_volatility_rule(self):
        """测试波动率规则"""
        # 创建高波动率价格序列
        dates = pd.date_range('2023-01-01', periods=20, freq='D')
        prices = pd.Series([10 + i * 0.5 + np.random.normal(0, 2) for i in range(20)], index=dates)
        
        result = self.risk_manager.check_single_rule('volatility', symbol="000001.SZ", price_data=prices)
        self.assertIsNotNone(result)
    
    def test_rule_enable_disable(self):
        """测试规则启用/禁用"""
        # 禁用止损规则
        self.assertTrue(self.risk_manager.disable_rule('stop_loss'))
        
        # 检查规则状态
        status = self.risk_manager.get_rule_status()
        self.assertFalse(status['stop_loss']['enabled'])
        
        # 重新启用
        self.assertTrue(self.risk_manager.enable_rule('stop_loss'))
        status = self.risk_manager.get_rule_status()
        self.assertTrue(status['stop_loss']['enabled'])


class TestPositionManager(unittest.TestCase):
    """测试仓位管理器"""
    
    def setUp(self):
        self.risk_config = RiskConfig()
        self.position_manager = PositionManager(self.risk_config, 1000000.0)
    
    def test_position_update(self):
        """测试持仓更新"""
        # 买入操作
        self.position_manager.update_position("000001.SZ", 1000, 10.0, "科技")
        
        position = self.position_manager.get_position("000001.SZ")
        self.assertIsNotNone(position)
        self.assertEqual(position.quantity, 1000)
        self.assertEqual(position.avg_price, 10.0)
        self.assertEqual(position.position_type, PositionType.LONG)
        
        # 加仓操作
        self.position_manager.update_position("000001.SZ", 500, 11.0, "科技")
        position = self.position_manager.get_position("000001.SZ")
        self.assertEqual(position.quantity, 1500)
        self.assertAlmostEqual(position.avg_price, 10.33, places=2)
        
        # 减仓操作
        self.position_manager.update_position("000001.SZ", -500, 12.0, "科技")
        position = self.position_manager.get_position("000001.SZ")
        self.assertEqual(position.quantity, 1000)
    
    def test_position_limits_check(self):
        """测试仓位限制检查"""
        # 测试正常仓位
        result = self.position_manager.check_position_limits("000001.SZ", 10000, 10.0)
        self.assertEqual(result.status, RiskCheckStatus.PASS)
        
        # 测试超限仓位（超过20%）
        result = self.position_manager.check_position_limits("000001.SZ", 25000, 10.0)
        self.assertEqual(result.status, RiskCheckStatus.BLOCKED)
    
    def test_sector_concentration(self):
        """测试行业集中度"""
        # 添加多个科技股
        self.position_manager.sector_mapping["000001.SZ"] = "科技"
        self.position_manager.sector_mapping["000002.SZ"] = "科技"
        self.position_manager.sector_mapping["000003.SZ"] = "金融"
        
        # 增加更多仓位使科技股占比超过默认30%限制
        self.position_manager.update_position("000001.SZ", 20000, 10.0, "科技")
        self.position_manager.update_position("000002.SZ", 20000, 10.0, "科技")
        self.position_manager.update_position("000003.SZ", 5000, 10.0, "金融")
        
        result = self.position_manager.check_sector_concentration()
        # 科技股占比40%，超过默认30%限制
        self.assertTrue(len(result.violations) > 0)
    
    def test_position_suggestions(self):
        """测试仓位调整建议"""
        # 创建超限持仓
        self.position_manager.update_position("000001.SZ", 25000, 10.0, "科技")
        
        suggestions = self.position_manager.suggest_position_adjustments()
        self.assertTrue(len(suggestions) > 0)
        self.assertEqual(suggestions[0]['action'], 'REDUCE')


class TestMoneyManager(unittest.TestCase):
    """测试资金管理器"""
    
    def setUp(self):
        self.risk_config = RiskConfig()
        self.money_manager = MoneyManager(self.risk_config, 1000000.0)
    
    def test_fund_allocation(self):
        """测试资金分配"""
        # 分配资金
        allocation_id = self.money_manager.allocate_funds(100000.0, "股票投资", FundType.AVAILABLE)
        self.assertIsNotNone(allocation_id)
        
        # 检查可用资金减少
        self.assertLess(self.money_manager.available_cash, 1000000.0)
        
        # 释放资金
        result = self.money_manager.release_funds(allocation_id)
        self.assertTrue(result)
    
    def test_position_size_calculation(self):
        """测试建仓数量计算"""
        quantity, required_capital = self.money_manager.calculate_position_size("000001.SZ", 10.0)
        
        self.assertGreater(quantity, 0)
        self.assertGreater(required_capital, 0)
        self.assertEqual(quantity % 100, 0)  # 应该是100的整数倍
    
    def test_margin_requirements(self):
        """测试保证金要求"""
        result = self.money_manager.check_margin_requirements(500000.0)
        self.assertEqual(result.status, RiskCheckStatus.PASS)
        
        # 测试超出杠杆限制
        result = self.money_manager.check_margin_requirements(2000000.0)
        self.assertTrue(len(result.violations) > 0)
    
    def test_cash_limits(self):
        """测试现金限制"""
        # 正常情况
        result = self.money_manager.check_cash_limits()
        self.assertEqual(result.status, RiskCheckStatus.PASS)
        
        # 模拟现金不足
        self.money_manager.available_cash = 10000.0  # 设置很低的现金
        result = self.money_manager.check_cash_limits()
        self.assertTrue(len(result.violations) > 0)


class TestRiskMonitor(unittest.TestCase):
    """测试风控监控器"""
    
    def setUp(self):
        self.risk_config = RiskConfig()
        self.base_risk_manager = BaseRiskManager(self.risk_config)
        self.position_manager = PositionManager(self.risk_config, 1000000.0)
        self.money_manager = MoneyManager(self.risk_config, 1000000.0)
        self.risk_monitor = RiskMonitor(
            self.risk_config,
            self.base_risk_manager,
            self.position_manager,
            self.money_manager
        )
    
    def test_alert_creation(self):
        """测试告警创建"""
        from src.risk.risk_monitor import AlertType
        
        alert_id = self.risk_monitor._create_alert(
            AlertType.LOG,
            RiskLevel.HIGH,
            "测试告警",
            "这是一个测试告警",
            "test_source"
        )
        
        self.assertIsNotNone(alert_id)
        self.assertIn(alert_id, self.risk_monitor.alerts)
    
    def test_alert_statistics(self):
        """测试告警统计"""
        # 创建几个告警
        from src.risk.risk_monitor import AlertType
        
        self.risk_monitor._create_alert(AlertType.LOG, RiskLevel.HIGH, "告警1", "消息1", "source1")
        self.risk_monitor._create_alert(AlertType.LOG, RiskLevel.MEDIUM, "告警2", "消息2", "source2")
        
        stats = self.risk_monitor.get_alert_statistics(24)
        self.assertEqual(stats['total'], 2)
        self.assertEqual(stats['high'], 1)
        self.assertEqual(stats['medium'], 1)
    
    def test_risk_metrics(self):
        """测试风险指标"""
        # 添加一些持仓
        self.position_manager.update_position("000001.SZ", 10000, 10.0, "科技")
        
        # 手动触发指标更新
        self.risk_monitor._update_risk_metrics()
        
        metrics = self.risk_monitor.get_risk_metrics_summary()
        self.assertIn('total_position_ratio', metrics)
        self.assertIn('position_count', metrics)
    
    def test_monitoring_dashboard(self):
        """测试监控仪表板"""
        dashboard_data = self.risk_monitor.get_monitoring_dashboard_data()
        
        required_keys = ['monitor_status', 'total_checks', 'total_alerts', 'risk_metrics']
        for key in required_keys:
            self.assertIn(key, dashboard_data)


class TestRiskEngine(unittest.TestCase):
    """测试风控引擎"""
    
    def setUp(self):
        self.risk_engine = RiskEngine(1000000.0)
    
    def test_signal_risk_check(self):
        """测试信号风控检查"""
        # 创建买入信号（使用交易时间）
        trading_time = datetime.now().replace(hour=10, minute=30, second=0, microsecond=0)
        signal = Signal(
            symbol="000001.SZ",
            signal_type=SignalType.BUY,
            timestamp=trading_time,
            price=10.0,
            volume=1000
        )
        
        decision = self.risk_engine.check_signal_risk(signal)
        self.assertIsNotNone(decision)
        self.assertIsInstance(decision.allow_trade, bool)
        self.assertIsInstance(decision.risk_score, float)
    
    def test_position_update(self):
        """测试持仓更新"""
        self.risk_engine.update_position("000001.SZ", 1000, 10.0, SignalType.BUY, "科技")
        
        position = self.risk_engine.position_manager.get_position("000001.SZ")
        self.assertIsNotNone(position)
        self.assertEqual(position.quantity, 1000)
    
    def test_stop_loss_profit_check(self):
        """测试止损止盈检查"""
        # 先建立持仓
        self.risk_engine.update_position("000001.SZ", 1000, 10.0, SignalType.BUY, "科技")
        
        # 测试止损情况
        signal_type = self.risk_engine.check_stop_loss_profit("000001.SZ", 9.0)
        self.assertEqual(signal_type, SignalType.CLOSE)
        
        # 测试正常价格
        signal_type = self.risk_engine.check_stop_loss_profit("000001.SZ", 10.5)
        self.assertIsNone(signal_type)
    
    def test_risk_summary(self):
        """测试风控摘要"""
        summary = self.risk_engine.get_risk_summary()
        
        required_keys = ['risk_config_summary', 'position_summary', 'capital_summary', 'trade_statistics']
        for key in required_keys:
            self.assertIn(key, summary)


class TestStrategyRiskAdapter(unittest.TestCase):
    """测试策略风控适配器"""
    
    def setUp(self):
        self.risk_engine = RiskEngine(1000000.0)
        self.adapter = StrategyRiskAdapter(self.risk_engine)
    
    def test_signal_filtering(self):
        """测试信号过滤"""
        # 使用交易时间内的时间戳
        trading_time = datetime.now().replace(hour=10, minute=30, second=0, microsecond=0)
        
        signals = [
            Signal(
                symbol="000001.SZ",
                signal_type=SignalType.BUY,
                timestamp=trading_time,
                price=10.0,
                volume=1000
            ),
            Signal(
                symbol="000002.SZ",
                signal_type=SignalType.BUY,
                timestamp=trading_time,
                price=20.0,
                volume=50000  # 超大数量，可能被风控阻止
            )
        ]
        
        filtered_signals = self.adapter.process_strategy_signals(signals, {})
        
        # 至少应该有一个信号通过（小数量的正常信号）
        self.assertGreaterEqual(len(filtered_signals), 1)
        self.assertLessEqual(len(filtered_signals), len(signals))


class TestBacktestRiskAdapter(unittest.TestCase):
    """测试回测风控适配器"""
    
    def setUp(self):
        self.risk_engine = RiskEngine(1000000.0)
        self.adapter = BacktestRiskAdapter(self.risk_engine)
    
    def test_backtest_initialization(self):
        """测试回测初始化"""
        self.adapter.initialize_backtest(1000000.0, "2023-01-01", "2023-12-31")
        
        # 检查引擎是否重置
        self.assertEqual(len(self.risk_engine.position_manager.positions), 0)
    
    def test_backtest_order_processing(self):
        """测试回测订单处理"""
        # 使用交易时间
        trading_time = datetime.now().replace(hour=10, minute=30, second=0, microsecond=0)
        allow_trade, reason, adjusted_quantity = self.adapter.process_backtest_order(
            "000001.SZ", "buy", 1000, 10.0, trading_time
        )
        
        self.assertIsInstance(allow_trade, bool)
        self.assertIsInstance(reason, str)
        self.assertGreaterEqual(adjusted_quantity, 0)


def create_test_suite():
    """创建测试套件"""
    test_suite = unittest.TestSuite()
    
    # 添加所有测试类
    test_classes = [
        TestRiskConfig,
        TestBaseRiskManager,
        TestPositionManager,
        TestMoneyManager,
        TestRiskMonitor,
        TestRiskEngine,
        TestStrategyRiskAdapter,
        TestBacktestRiskAdapter
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    return test_suite


def run_comprehensive_test():
    """运行综合测试"""
    print("=" * 60)
    print("风控系统综合测试开始")
    print("=" * 60)
    
    # 创建风控引擎
    risk_engine = RiskEngine(1000000.0)
    
    # 启动监控
    risk_engine.start_monitoring()
    
    try:
        # 模拟交易场景
        print("\n1. 测试正常交易场景")
        trading_time = datetime.now().replace(hour=10, minute=30, second=0, microsecond=0)
        signal1 = Signal(
            symbol="000001.SZ",
            signal_type=SignalType.BUY,
            timestamp=trading_time,
            price=10.0,
            volume=5000
        )
        
        decision1 = risk_engine.check_signal_risk(signal1)
        print(f"买入信号检查: 允许={decision1.allow_trade}, 原因={decision1.decision_reason}")
        
        if decision1.allow_trade:
            risk_engine.update_position("000001.SZ", 5000, 10.0, SignalType.BUY, "科技")
            print("持仓已更新")
        
        # 测试止损场景
        print("\n2. 测试止损场景")
        risk_engine.update_market_prices({"000001.SZ": 9.0})
        exit_signal = risk_engine.check_stop_loss_profit("000001.SZ", 9.0)
        if exit_signal:
            print(f"触发止损信号: {exit_signal.value}")
        
        # 测试超限仓位
        print("\n3. 测试超限仓位检查")
        signal2 = Signal(
            symbol="000002.SZ",
            signal_type=SignalType.BUY,
            timestamp=trading_time,
            price=20.0,
            volume=30000  # 超大仓位
        )
        
        decision2 = risk_engine.check_signal_risk(signal2)
        print(f"超大仓位检查: 允许={decision2.allow_trade}, 原因={decision2.decision_reason}")
        
        # 生成风控报告
        print("\n4. 生成风控报告")
        report = risk_engine.generate_risk_report("daily")
        print(f"风控报告生成完成: {report['summary']}")
        
        # 获取建议
        print("\n5. 获取风控建议")
        position_suggestions = risk_engine.get_position_suggestions()
        capital_suggestions = risk_engine.get_capital_suggestions()
        
        print(f"仓位调整建议数量: {len(position_suggestions)}")
        print(f"资金配置建议: {len(capital_suggestions)}")
        
        # 风控摘要
        print("\n6. 风控系统摘要")
        summary = risk_engine.get_risk_summary()
        trade_stats = summary['trade_statistics']
        print(f"总交易次数: {trade_stats['total_trades']}")
        print(f"被阻止交易: {trade_stats['blocked_trades']}")
        print(f"风控触发退出: {trade_stats['risk_triggered_exits']}")
        
        print("\n" + "=" * 60)
        print("风控系统综合测试完成")
        print("=" * 60)
        
    finally:
        # 停止监控
        risk_engine.stop_monitoring()


if __name__ == "__main__":
    # 运行单元测试
    print("开始运行单元测试...")
    test_suite = create_test_suite()
    runner = unittest.TextTestRunner(verbosity=2)
    test_result = runner.run(test_suite)
    
    print(f"\n测试结果: 运行 {test_result.testsRun} 个测试")
    print(f"失败: {len(test_result.failures)}")
    print(f"错误: {len(test_result.errors)}")
    
    if test_result.failures:
        print("\n失败的测试:")
        for test, traceback in test_result.failures:
            print(f"- {test}: {traceback}")
    
    if test_result.errors:
        print("\n错误的测试:")
        for test, traceback in test_result.errors:
            print(f"- {test}: {traceback}")
    
    # 如果单元测试通过，运行综合测试
    if not test_result.failures and not test_result.errors:
        print("\n单元测试全部通过！开始综合测试...")
        run_comprehensive_test()
    else:
        print("\n单元测试存在问题，跳过综合测试")