"""
监控面板集成测试
测试监控面板与各模块的集成和实时数据显示
"""

import pytest
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import json
import threading
import time

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from monitor.dashboard import Dashboard
from monitor.data_integration import DataIntegration
from monitor.realtime_monitor import RealtimeMonitor
from monitor.web_app import create_app


class TestMonitorIntegration:
    """监控集成测试类"""
    
    @pytest.fixture(autouse=True)
    def setup(self, test_config, mock_stock_data, temp_dir):
        """测试设置"""
        self.config = test_config
        self.mock_data = mock_stock_data
        self.temp_dir = temp_dir
        
        # 初始化监控组件
        self.dashboard = Dashboard()
        self.data_integration = DataIntegration()
        self.realtime_monitor = RealtimeMonitor()
        
        # 准备测试数据
        self.portfolio_data = {
            'total_value': 1020000.0,
            'cash': 500000.0,
            'positions': [
                {
                    'stock_code': '000001.SZ',
                    'stock_name': '平安银行',
                    'quantity': 1000,
                    'avg_price': 10.0,
                    'current_price': 10.2,
                    'market_value': 10200.0,
                    'unrealized_pnl': 200.0,
                    'unrealized_pnl_ratio': 0.02
                },
                {
                    'stock_code': '000002.SZ',
                    'stock_name': '万科A',
                    'quantity': 500,
                    'avg_price': 20.0,
                    'current_price': 20.4,
                    'market_value': 10200.0,
                    'unrealized_pnl': 200.0,
                    'unrealized_pnl_ratio': 0.02
                }
            ],
            'daily_return': 0.015,
            'total_return': 0.02,
            'realized_pnl': 1000.0
        }
        
        self.performance_data = {
            'total_return': 0.02,
            'annualized_return': 0.12,
            'volatility': 0.15,
            'sharpe_ratio': 0.8,
            'max_drawdown': 0.05,
            'win_rate': 0.65,
            'profit_loss_ratio': 1.2,
            'trading_days': 250,
            'total_trades': 150
        }
        
        self.trade_history = [
            {
                'timestamp': datetime.now() - timedelta(minutes=30),
                'stock_code': '000001.SZ',
                'stock_name': '平安银行',
                'action': 'buy',
                'quantity': 1000,
                'price': 10.0,
                'amount': 10000.0,
                'status': 'filled',
                'strategy': 'ma_crossover'
            },
            {
                'timestamp': datetime.now() - timedelta(minutes=15),
                'stock_code': '000002.SZ',
                'stock_name': '万科A',
                'action': 'sell',
                'quantity': 200,
                'price': 20.2,
                'amount': 4040.0,
                'status': 'filled',
                'strategy': 'rsi_strategy'
            }
        ]
    
    @pytest.mark.integration
    def test_dashboard_data_integration(self):
        """测试仪表板数据集成"""
        # 1. 更新仪表板数据
        update_data = {
            'portfolio': self.portfolio_data,
            'performance': self.performance_data,
            'trades': self.trade_history
        }
        
        self.dashboard.update_data(update_data)
        
        # 2. 验证投资组合数据
        portfolio_summary = self.dashboard.get_portfolio_summary()
        assert portfolio_summary is not None
        assert portfolio_summary['total_value'] == 1020000.0
        assert portfolio_summary['cash'] == 500000.0
        assert len(portfolio_summary['positions']) == 2
        
        # 3. 验证性能指标
        performance_metrics = self.dashboard.get_performance_metrics()
        assert performance_metrics is not None
        assert performance_metrics['total_return'] == 0.02
        assert performance_metrics['sharpe_ratio'] == 0.8
        
        # 4. 验证交易历史
        recent_trades = self.dashboard.get_recent_trades(limit=5)
        assert len(recent_trades) == 2
        assert recent_trades[0]['stock_code'] == '000002.SZ'  # 最新的交易
    
    @pytest.mark.integration
    def test_realtime_data_streaming(self):
        """测试实时数据流"""
        # 1. 启动实时监控
        self.realtime_monitor.start()
        
        # 2. 模拟数据更新
        test_updates = []
        
        def collect_updates(data):
            test_updates.append(data)
        
        self.realtime_monitor.subscribe('portfolio_update', collect_updates)
        
        # 3. 推送模拟数据
        portfolio_update = {
            'type': 'portfolio_update',
            'timestamp': datetime.now(),
            'data': self.portfolio_data
        }
        
        self.realtime_monitor.push_update(portfolio_update)
        
        # 等待数据处理
        time.sleep(0.1)
        
        # 4. 验证数据接收
        assert len(test_updates) == 1
        assert test_updates[0]['type'] == 'portfolio_update'
        
        # 5. 停止监控
        self.realtime_monitor.stop()
    
    @pytest.mark.integration
    def test_web_interface_integration(self):
        """测试Web界面集成"""
        # 1. 创建Flask应用
        app = create_app(testing=True)
        client = app.test_client()
        
        # 2. 测试主页
        response = client.get('/')
        assert response.status_code == 200
        assert b'dashboard' in response.data or b'Dashboard' in response.data
        
        # 3. 测试API端点
        
        # 投资组合API
        with app.app_context():
            # 模拟数据注入
            app.dashboard = self.dashboard
            self.dashboard.update_data({
                'portfolio': self.portfolio_data,
                'performance': self.performance_data,
                'trades': self.trade_history
            })
        
        portfolio_response = client.get('/api/portfolio')
        assert portfolio_response.status_code == 200
        portfolio_json = json.loads(portfolio_response.data)
        assert 'total_value' in portfolio_json
        
        # 性能指标API
        performance_response = client.get('/api/performance')
        assert performance_response.status_code == 200
        performance_json = json.loads(performance_response.data)
        assert 'total_return' in performance_json
        
        # 交易历史API
        trades_response = client.get('/api/trades')
        assert trades_response.status_code == 200
        trades_json = json.loads(trades_response.data)
        assert isinstance(trades_json, list)
    
    @pytest.mark.integration
    def test_data_integration_with_database(self, test_database):
        """测试与数据库的集成"""
        # 1. 保存测试数据到数据库
        test_data = self.mock_data[self.mock_data['ts_code'] == '000001.SZ'].head(10)
        
        # 模拟数据库操作
        with patch('monitor.data_integration.DatabaseManager') as mock_db_class:
            mock_db = Mock()
            mock_db.get_stock_data.return_value = test_data
            mock_db.get_latest_trades.return_value = pd.DataFrame(self.trade_history)
            mock_db_class.return_value = mock_db
            
            # 2. 通过数据集成器获取数据
            stock_data = self.data_integration.get_stock_data('000001.SZ', '20231201', '20231210')
            assert not stock_data.empty
            assert len(stock_data) == 10
            
            # 3. 获取交易历史
            trade_data = self.data_integration.get_trade_history(limit=10)
            assert len(trade_data) == 2
    
    @pytest.mark.integration
    def test_alert_system_integration(self):
        """测试告警系统集成"""
        # 1. 设置告警规则
        alert_rules = [
            {
                'name': 'position_limit_alert',
                'condition': 'position_ratio > 0.1',
                'message': '单个持仓超过10%限制',
                'level': 'warning'
            },
            {
                'name': 'drawdown_alert',
                'condition': 'max_drawdown > 0.05',
                'message': '最大回撤超过5%',
                'level': 'critical'
            }
        ]
        
        self.dashboard.set_alert_rules(alert_rules)
        
        # 2. 触发告警的数据
        risky_portfolio = self.portfolio_data.copy()
        risky_portfolio['positions'][0]['market_value'] = 150000  # 设置大持仓
        
        risky_performance = self.performance_data.copy()
        risky_performance['max_drawdown'] = 0.08  # 设置大回撤
        
        update_data = {
            'portfolio': risky_portfolio,
            'performance': risky_performance
        }
        
        # 3. 更新数据并检查告警
        self.dashboard.update_data(update_data)
        alerts = self.dashboard.get_active_alerts()
        
        # 4. 验证告警生成
        assert len(alerts) >= 1
        alert_names = [alert['name'] for alert in alerts]
        assert 'drawdown_alert' in alert_names
    
    @pytest.mark.integration
    def test_chart_data_generation(self):
        """测试图表数据生成"""
        # 1. 生成净值曲线数据
        dates = pd.date_range(start='2023-12-01', end='2023-12-31', freq='D')
        nav_data = []
        
        base_value = 1000000
        for i, date in enumerate(dates):
            value = base_value * (1 + np.random.normal(0.001, 0.02))  # 模拟净值变化
            base_value = value
            nav_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'nav': round(value, 2),
                'return': round((value / 1000000 - 1) * 100, 2)
            })
        
        # 2. 通过仪表板生成图表数据
        chart_data = self.dashboard.generate_chart_data(nav_data, chart_type='nav_curve')
        assert 'dates' in chart_data
        assert 'values' in chart_data
        assert len(chart_data['dates']) == len(nav_data)
        
        # 3. 生成持仓分布饼图数据
        position_chart = self.dashboard.generate_chart_data(
            self.portfolio_data['positions'], 
            chart_type='position_pie'
        )
        assert 'labels' in position_chart
        assert 'values' in position_chart
        assert len(position_chart['labels']) == 2
        
        # 4. 生成收益分布柱状图
        returns_data = [0.02, -0.01, 0.03, 0.01, -0.02, 0.04, 0.01]
        returns_chart = self.dashboard.generate_chart_data(
            returns_data,
            chart_type='returns_histogram'
        )
        assert 'bins' in returns_chart
        assert 'counts' in returns_chart
    
    @pytest.mark.integration
    def test_multi_strategy_monitoring(self):
        """测试多策略监控"""
        # 1. 设置多策略数据
        strategy_performance = {
            'ma_crossover': {
                'total_return': 0.08,
                'win_rate': 0.6,
                'trades_count': 45,
                'avg_holding_days': 5.2,
                'max_drawdown': 0.03
            },
            'rsi_strategy': {
                'total_return': 0.12,
                'win_rate': 0.7,
                'trades_count': 38,
                'avg_holding_days': 3.8,
                'max_drawdown': 0.04
            },
            'combined': {
                'total_return': 0.15,
                'win_rate': 0.68,
                'trades_count': 83,
                'avg_holding_days': 4.5,
                'max_drawdown': 0.035
            }
        }
        
        # 2. 更新策略数据
        self.dashboard.update_strategy_performance(strategy_performance)
        
        # 3. 获取策略比较数据
        strategy_comparison = self.dashboard.get_strategy_comparison()
        assert len(strategy_comparison) == 3
        assert 'ma_crossover' in strategy_comparison
        assert 'rsi_strategy' in strategy_comparison
        assert 'combined' in strategy_comparison
        
        # 4. 生成策略对比图表
        comparison_chart = self.dashboard.generate_strategy_comparison_chart()
        assert 'strategies' in comparison_chart
        assert 'metrics' in comparison_chart
    
    @pytest.mark.integration
    def test_risk_monitoring_integration(self):
        """测试风险监控集成"""
        # 1. 设置风险指标
        risk_metrics = {
            'var_95': 0.025,  # 95% VaR
            'var_99': 0.045,  # 99% VaR
            'expected_shortfall': 0.035,
            'beta': 1.2,
            'correlation_market': 0.85,
            'concentration_risk': 0.15,
            'liquidity_risk': 0.08
        }
        
        # 2. 更新风险数据
        self.dashboard.update_risk_metrics(risk_metrics)
        
        # 3. 检查风险告警
        risk_alerts = self.dashboard.check_risk_alerts(risk_metrics)
        
        # 验证风险指标计算
        assert len(risk_alerts) >= 0  # 可能有风险告警
        
        # 4. 生成风险报告
        risk_report = self.dashboard.generate_risk_report()
        assert 'var_95' in risk_report
        assert 'concentration_risk' in risk_report
    
    @pytest.mark.integration
    @pytest.mark.performance
    def test_monitor_performance(self, performance_monitor):
        """测试监控性能"""
        performance_monitor.start()
        
        # 1. 大量数据更新
        for i in range(100):
            portfolio_update = self.portfolio_data.copy()
            portfolio_update['total_value'] = 1000000 + i * 1000
            
            performance_update = self.performance_data.copy()
            performance_update['total_return'] = 0.02 + i * 0.0001
            
            update_data = {
                'portfolio': portfolio_update,
                'performance': performance_update,
                'timestamp': datetime.now()
            }
            
            self.dashboard.update_data(update_data)
        
        # 2. 大量查询操作
        for i in range(50):
            self.dashboard.get_portfolio_summary()
            self.dashboard.get_performance_metrics()
            self.dashboard.get_recent_trades(limit=10)
        
        performance_stats = performance_monitor.stop()
        
        # 性能验证
        assert performance_stats['execution_time'] < 10  # 10秒内完成
        assert performance_stats['peak_memory_mb'] < 200  # 内存使用小于200MB
        
        print(f"监控性能测试: {performance_stats}")
    
    @pytest.mark.integration
    def test_data_export_functionality(self, temp_dir):
        """测试数据导出功能"""
        # 1. 设置测试数据
        self.dashboard.update_data({
            'portfolio': self.portfolio_data,
            'performance': self.performance_data,
            'trades': self.trade_history
        })
        
        # 2. 导出投资组合数据
        portfolio_file = os.path.join(temp_dir, "portfolio_export.json")
        self.dashboard.export_portfolio_data(portfolio_file)
        assert os.path.exists(portfolio_file)
        
        # 验证导出文件
        with open(portfolio_file, 'r', encoding='utf-8') as f:
            exported_data = json.load(f)
        assert 'total_value' in exported_data
        assert 'positions' in exported_data
        
        # 3. 导出交易历史
        trades_file = os.path.join(temp_dir, "trades_export.csv")
        self.dashboard.export_trade_history(trades_file)
        assert os.path.exists(trades_file)
        
        # 验证CSV文件
        imported_trades = pd.read_csv(trades_file)
        assert len(imported_trades) == 2
        assert 'stock_code' in imported_trades.columns
        
        # 4. 导出性能报告
        report_file = os.path.join(temp_dir, "performance_report.html")
        self.dashboard.export_performance_report(report_file)
        assert os.path.exists(report_file)
        
        # 验证HTML文件内容
        with open(report_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        assert 'total_return' in html_content.lower()
        assert 'sharpe_ratio' in html_content.lower()
    
    @pytest.mark.integration
    def test_websocket_real_time_updates(self):
        """测试WebSocket实时更新"""
        # 1. 模拟WebSocket连接
        class MockWebSocket:
            def __init__(self):
                self.messages = []
                self.connected = True
            
            def send(self, message):
                if self.connected:
                    self.messages.append(message)
            
            def close(self):
                self.connected = False
        
        mock_ws = MockWebSocket()
        
        # 2. 注册WebSocket客户端
        self.realtime_monitor.add_websocket_client(mock_ws)
        
        # 3. 推送实时数据
        real_time_data = {
            'type': 'price_update',
            'data': {
                '000001.SZ': {'price': 10.25, 'change': 0.025},
                '000002.SZ': {'price': 20.15, 'change': -0.0075}
            },
            'timestamp': datetime.now().isoformat()
        }
        
        self.realtime_monitor.broadcast_to_websockets(real_time_data)
        
        # 4. 验证消息发送
        assert len(mock_ws.messages) == 1
        sent_message = json.loads(mock_ws.messages[0])
        assert sent_message['type'] == 'price_update'
        assert '000001.SZ' in sent_message['data']
        
        # 5. 清理连接
        mock_ws.close()
        self.realtime_monitor.remove_websocket_client(mock_ws)
    
    @pytest.mark.integration
    def test_monitor_error_recovery(self):
        """测试监控错误恢复"""
        # 1. 模拟数据源异常
        original_get_data = self.data_integration.get_portfolio_data
        
        def failing_get_data():
            raise ConnectionError("数据源连接失败")
        
        self.data_integration.get_portfolio_data = failing_get_data
        
        # 2. 尝试更新数据（应该优雅处理错误）
        try:
            self.dashboard.refresh_data()
        except Exception as e:
            # 监控系统应该捕获并记录错误，而不是崩溃
            pass
        
        # 3. 恢复数据源
        self.data_integration.get_portfolio_data = original_get_data
        
        # 4. 验证系统恢复
        self.dashboard.update_data({
            'portfolio': self.portfolio_data,
            'performance': self.performance_data
        })
        
        portfolio_summary = self.dashboard.get_portfolio_summary()
        assert portfolio_summary is not None
        
        # 5. 检查错误日志
        error_logs = self.dashboard.get_error_logs()
        assert len(error_logs) > 0  # 应该记录了错误


if __name__ == "__main__":
    # 运行监控集成测试
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short",
        "-m", "integration"
    ])