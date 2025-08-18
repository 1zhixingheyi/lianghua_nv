#!/usr/bin/env python3
"""
监控面板测试脚本
================

用于测试监控面板的各项功能，包括：
- Web应用启动测试
- API接口测试  
- 数据完整性测试
- 性能测试
- 兼容性测试

使用方法:
python monitor/test_monitor.py
"""

import os
import sys
import time
import json
import requests
import unittest
import threading
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from monitor.web_app import create_app
from monitor.dashboard import dashboard_controller
from monitor.realtime_monitor import realtime_monitor


class MonitorTestCase(unittest.TestCase):
    """监控面板测试基类"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        
        # 启动测试服务器
        cls.server_thread = threading.Thread(
            target=cls.run_server,
            daemon=True
        )
        cls.server_thread.start()
        time.sleep(2)  # 等待服务器启动
        
        print("监控面板测试环境初始化完成")
    
    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        cls.app_context.pop()
        print("监控面板测试环境清理完成")
    
    @classmethod
    def run_server(cls):
        """运行测试服务器"""
        cls.app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)


class WebAppTest(MonitorTestCase):
    """Web应用测试"""
    
    def test_app_creation(self):
        """测试应用创建"""
        self.assertIsNotNone(self.app)
        self.assertTrue(self.app.config['TESTING'])
    
    def test_health_check(self):
        """测试健康检查端点"""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('status', data)
        self.assertIn('timestamp', data)
        self.assertIn('modules', data)
    
    def test_dashboard_route(self):
        """测试仪表板页面"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'dashboard', response.data)
    
    def test_strategies_route(self):
        """测试策略监控页面"""
        response = self.client.get('/strategies')
        self.assertEqual(response.status_code, 200)
    
    def test_positions_route(self):
        """测试持仓管理页面"""
        response = self.client.get('/positions')
        self.assertEqual(response.status_code, 200)
    
    def test_trades_route(self):
        """测试交易记录页面"""
        response = self.client.get('/trades')
        self.assertEqual(response.status_code, 200)
    
    def test_backtest_route(self):
        """测试回测分析页面"""
        response = self.client.get('/backtest')
        self.assertEqual(response.status_code, 200)
    
    def test_risk_route(self):
        """测试风控监控页面"""
        response = self.client.get('/risk')
        self.assertEqual(response.status_code, 200)
    
    def test_settings_route(self):
        """测试系统设置页面"""
        response = self.client.get('/settings')
        self.assertEqual(response.status_code, 200)
    
    def test_404_error(self):
        """测试404错误处理"""
        response = self.client.get('/nonexistent')
        self.assertEqual(response.status_code, 404)


class APITest(MonitorTestCase):
    """API接口测试"""
    
    def test_dashboard_summary_api(self):
        """测试仪表板汇总API"""
        response = self.client.get('/api/dashboard/summary')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        
        # 验证必要字段
        summary = data['data']
        expected_fields = [
            'total_value', 'available_cash', 'total_pnl', 
            'daily_pnl', 'total_return', 'daily_return'
        ]
        for field in expected_fields:
            self.assertIn(field, summary)
    
    def test_strategies_api(self):
        """测试策略列表API"""
        response = self.client.get('/api/strategies')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('strategies', data['data'])
        self.assertIn('total', data['data'])
    
    def test_positions_api(self):
        """测试持仓列表API"""
        response = self.client.get('/api/positions')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('positions', data['data'])
        self.assertIn('summary', data['data'])
    
    def test_trades_api(self):
        """测试交易记录API"""
        response = self.client.get('/api/trades')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('trades', data['data'])
        self.assertIn('pagination', data['data'])
    
    def test_risk_alerts_api(self):
        """测试风险告警API"""
        response = self.client.get('/api/risk/alerts')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('alerts', data['data'])
    
    def test_api_pagination(self):
        """测试API分页功能"""
        # 测试第一页
        response = self.client.get('/api/trades?page=1&limit=10')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['pagination']['page'], 1)
        self.assertEqual(data['data']['pagination']['limit'], 10)
    
    def test_api_filtering(self):
        """测试API筛选功能"""
        # 测试策略筛选
        response = self.client.get('/api/strategies?category=趋势跟踪')
        self.assertEqual(response.status_code, 200)
        
        # 测试持仓排序
        response = self.client.get('/api/positions?sort_by=market_value&order=desc')
        self.assertEqual(response.status_code, 200)
    
    def test_create_strategy_api(self):
        """测试创建策略API"""
        strategy_data = {
            'strategy_name': 'RSI',
            'instance_name': 'test_rsi_strategy',
            'params': {
                'period': 14,
                'oversold': 30,
                'overbought': 70
            }
        }
        
        response = self.client.post(
            '/api/strategies',
            data=json.dumps(strategy_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
    
    def test_api_error_handling(self):
        """测试API错误处理"""
        # 测试无效的策略名称
        response = self.client.get('/api/strategies/invalid_strategy')
        self.assertEqual(response.status_code, 404)
        
        # 测试无效的JSON请求
        response = self.client.post(
            '/api/strategies',
            data='invalid json',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)


class DashboardControllerTest(MonitorTestCase):
    """仪表板控制器测试"""
    
    def test_get_dashboard_summary(self):
        """测试获取仪表板汇总数据"""
        summary = dashboard_controller.get_dashboard_summary()
        
        self.assertIsInstance(summary, dict)
        self.assertIn('total_value', summary)
        self.assertIn('available_cash', summary)
        self.assertIn('update_time', summary)
    
    def test_get_strategy_performance(self):
        """测试获取策略绩效数据"""
        strategies = dashboard_controller.get_strategy_performance()
        
        self.assertIsInstance(strategies, list)
        if strategies:
            strategy = strategies[0]
            self.assertIn('name', strategy)
            self.assertIn('status', strategy)
            self.assertIn('total_return', strategy)
    
    def test_get_position_data(self):
        """测试获取持仓数据"""
        positions = dashboard_controller.get_position_data()
        
        self.assertIsInstance(positions, list)
        if positions:
            position = positions[0]
            self.assertIn('symbol', position)
            self.assertIn('quantity', position)
            self.assertIn('market_value', position)
    
    def test_get_trading_records(self):
        """测试获取交易记录"""
        trades = dashboard_controller.get_trading_records(10)
        
        self.assertIsInstance(trades, list)
        self.assertLessEqual(len(trades), 10)
        
        if trades:
            trade = trades[0]
            self.assertIn('order_id', trade)
            self.assertIn('symbol', trade)
            self.assertIn('side', trade)
    
    def test_get_risk_alerts(self):
        """测试获取风险告警"""
        alerts = dashboard_controller.get_risk_alerts()
        
        self.assertIsInstance(alerts, list)
        if alerts:
            alert = alerts[0]
            self.assertIn('level', alert)
            self.assertIn('title', alert)
            self.assertIn('message', alert)


class RealtimeMonitorTest(MonitorTestCase):
    """实时监控测试"""
    
    def test_monitor_initialization(self):
        """测试监控组件初始化"""
        self.assertIsNotNone(realtime_monitor)
        self.assertFalse(realtime_monitor.is_running)
    
    def test_data_cache(self):
        """测试数据缓存功能"""
        from monitor.realtime_monitor import DataCache, RealtimeData
        
        cache = DataCache(max_size=10, ttl=60)
        
        # 测试设置和获取数据
        test_data = RealtimeData(
            timestamp=datetime.now().isoformat(),
            data_type='test',
            data={'value': 123}
        )
        
        cache.set('test_key', test_data)
        retrieved_data = cache.get('test_key')
        
        self.assertIsNotNone(retrieved_data)
        self.assertEqual(retrieved_data.data['value'], 123)
        
        # 测试缓存大小限制
        self.assertEqual(cache.size(), 1)
    
    def test_client_management(self):
        """测试客户端连接管理"""
        # 模拟添加客户端
        client_id = 'test_client_001'
        websocket_mock = None  # 模拟WebSocket连接
        channels = {'summary', 'strategies'}
        
        success = realtime_monitor.add_client(client_id, websocket_mock, channels)
        self.assertTrue(success)
        
        # 测试订阅管理
        success = realtime_monitor.subscribe_channel(client_id, 'positions')
        self.assertTrue(success)
        
        success = realtime_monitor.unsubscribe_channel(client_id, 'summary')
        self.assertTrue(success)
        
        # 测试移除客户端
        realtime_monitor.remove_client(client_id)
    
    def test_data_publication(self):
        """测试数据发布功能"""
        test_data = {
            'timestamp': datetime.now().isoformat(),
            'value': 456
        }
        
        # 发布测试数据
        realtime_monitor.publish_data('test_channel', test_data)
        
        # 验证数据是否被缓存
        cached_data = realtime_monitor.cache.get('test_channel_latest')
        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data.data['value'], 456)


class PerformanceTest(MonitorTestCase):
    """性能测试"""
    
    def test_dashboard_load_time(self):
        """测试仪表板加载时间"""
        start_time = time.time()
        response = self.client.get('/')
        end_time = time.time()
        
        load_time = end_time - start_time
        self.assertEqual(response.status_code, 200)
        self.assertLess(load_time, 2.0)  # 加载时间应小于2秒
        
        print(f"仪表板加载时间: {load_time:.3f}秒")
    
    def test_api_response_time(self):
        """测试API响应时间"""
        api_endpoints = [
            '/api/dashboard/summary',
            '/api/strategies',
            '/api/positions',
            '/api/trades',
            '/api/risk/alerts'
        ]
        
        for endpoint in api_endpoints:
            start_time = time.time()
            response = self.client.get(endpoint)
            end_time = time.time()
            
            response_time = end_time - start_time
            self.assertEqual(response.status_code, 200)
            self.assertLess(response_time, 1.0)  # API响应时间应小于1秒
            
            print(f"{endpoint} 响应时间: {response_time:.3f}秒")
    
    def test_concurrent_requests(self):
        """测试并发请求处理"""
        import concurrent.futures
        
        def make_request():
            response = self.client.get('/api/dashboard/summary')
            return response.status_code
        
        # 并发执行10个请求
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # 验证所有请求都成功
        self.assertEqual(len(results), 10)
        for status_code in results:
            self.assertEqual(status_code, 200)
        
        print("并发请求测试通过：10个并发请求全部成功")


class IntegrationTest(MonitorTestCase):
    """集成测试"""
    
    def test_end_to_end_workflow(self):
        """测试端到端工作流"""
        # 1. 访问仪表板
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        
        # 2. 获取汇总数据
        response = self.client.get('/api/dashboard/summary')
        self.assertEqual(response.status_code, 200)
        summary_data = json.loads(response.data)
        self.assertTrue(summary_data['success'])
        
        # 3. 获取策略列表
        response = self.client.get('/api/strategies')
        self.assertEqual(response.status_code, 200)
        strategies_data = json.loads(response.data)
        self.assertTrue(strategies_data['success'])
        
        # 4. 获取持仓数据
        response = self.client.get('/api/positions')
        self.assertEqual(response.status_code, 200)
        positions_data = json.loads(response.data)
        self.assertTrue(positions_data['success'])
        
        # 5. 获取交易记录
        response = self.client.get('/api/trades')
        self.assertEqual(response.status_code, 200)
        trades_data = json.loads(response.data)
        self.assertTrue(trades_data['success'])
        
        print("端到端工作流测试通过")
    
    def test_data_consistency(self):
        """测试数据一致性"""
        # 获取汇总数据
        summary_response = self.client.get('/api/dashboard/summary')
        summary_data = json.loads(summary_response.data)['data']
        
        # 获取持仓数据
        positions_response = self.client.get('/api/positions')
        positions_data = json.loads(positions_response.data)['data']
        
        # 验证数据一致性（示例：持仓数量应该匹配）
        if 'total_positions' in summary_data and positions_data['positions']:
            calculated_positions = len(positions_data['positions'])
            self.assertEqual(summary_data['total_positions'], calculated_positions)
        
        print("数据一致性测试通过")


def run_http_tests():
    """运行HTTP请求测试"""
    base_url = 'http://127.0.0.1:5001'
    
    print("开始HTTP请求测试...")
    
    # 测试页面访问
    pages = ['/', '/strategies', '/positions', '/trades', '/backtest', '/risk', '/settings']
    
    for page in pages:
        try:
            response = requests.get(f"{base_url}{page}", timeout=5)
            print(f"✓ {page}: {response.status_code}")
        except Exception as e:
            print(f"✗ {page}: {e}")
    
    # 测试API接口
    apis = [
        '/api/dashboard/summary',
        '/api/strategies', 
        '/api/positions',
        '/api/trades',
        '/api/risk/alerts'
    ]
    
    for api in apis:
        try:
            response = requests.get(f"{base_url}{api}", timeout=5)
            data = response.json()
            status = "✓" if data.get('success') else "✗"
            print(f"{status} {api}: {response.status_code}")
        except Exception as e:
            print(f"✗ {api}: {e}")
    
    print("HTTP请求测试完成")


def main():
    """主测试函数"""
    print("=" * 60)
    print("量化交易监控面板测试")
    print("=" * 60)
    
    # 运行单元测试
    print("\n1. 运行单元测试...")
    test_suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    test_runner = unittest.TextTestRunner(verbosity=2)
    test_result = test_runner.run(test_suite)
    
    # 等待服务器启动
    print("\n2. 等待服务器启动...")
    time.sleep(3)
    
    # 运行HTTP测试
    print("\n3. 运行HTTP请求测试...")
    try:
        run_http_tests()
    except Exception as e:
        print(f"HTTP测试失败: {e}")
    
    # 测试总结
    print("\n" + "=" * 60)
    print("测试总结:")
    print(f"- 运行测试: {test_result.testsRun}")
    print(f"- 失败: {len(test_result.failures)}")
    print(f"- 错误: {len(test_result.errors)}")
    
    if test_result.failures:
        print("\n失败的测试:")
        for test, error in test_result.failures:
            print(f"  - {test}: {error}")
    
    if test_result.errors:
        print("\n错误的测试:")
        for test, error in test_result.errors:
            print(f"  - {test}: {error}")
    
    success = len(test_result.failures) == 0 and len(test_result.errors) == 0
    print(f"\n测试结果: {'通过' if success else '失败'}")
    print("=" * 60)
    
    return 0 if success else 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)