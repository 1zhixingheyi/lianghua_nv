#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置热重载功能测试脚本

提供完整的热重载功能测试，包括：
1. 基础热重载功能测试
2. 版本管理功能测试
3. 组件集成测试
4. 性能和稳定性测试

作者: 量化交易系统
日期: 2025-01-18
版本: 1.0.0
"""

import asyncio
import json
import logging
import os
import tempfile
import time
import unittest
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# 设置测试环境的日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HotReloadTestCase(unittest.TestCase):
    """配置热重载测试用例"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时测试目录
        self.test_dir = Path(tempfile.mkdtemp())
        self.config_dir = self.test_dir / "config"
        self.config_dir.mkdir(exist_ok=True)
        
        # 创建测试配置文件
        self.test_config_file = self.config_dir / "test_config.yaml"
        self.create_test_config()
        
        logger.info(f"测试环境准备完成，目录: {self.test_dir}")
    
    def tearDown(self):
        """测试后清理"""
        # 清理临时文件
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        logger.info("测试环境清理完成")
    
    def create_test_config(self):
        """创建测试配置文件"""
        test_config = {
            'version': '1.0.0',
            'enabled': True,
            'last_updated': datetime.now().isoformat(),
            'trading': {
                'timeout': 30,
                'retry_count': 3,
                'max_position': 100000
            },
            'risk_management': {
                'stop_loss_percent': 5.0,
                'stop_profit_percent': 10.0,
                'max_daily_loss': 20.0
            }
        }
        
        with open(self.test_config_file, 'w', encoding='utf-8') as f:
            yaml.dump(test_config, f, default_flow_style=False, allow_unicode=True)
    
    def update_test_config(self, updates: Dict[str, Any]):
        """更新测试配置文件"""
        with open(self.test_config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 深度更新配置
        def deep_update(base_dict, update_dict):
            for key, value in update_dict.items():
                if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                    deep_update(base_dict[key], value)
                else:
                    base_dict[key] = value
        
        deep_update(config, updates)
        config['last_updated'] = datetime.now().isoformat()
        
        with open(self.test_config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        logger.info(f"测试配置文件已更新: {updates}")


class TestConfigManager(HotReloadTestCase):
    """配置管理器测试"""
    
    def test_config_loading(self):
        """测试配置加载"""
        try:
            from config.config_manager import ConfigManager
            
            # 创建配置管理器
            config_manager = ConfigManager(config_dir=str(self.config_dir))
            
            # 测试加载配置
            config_data = config_manager.get_config('test_config')
            
            self.assertIsNotNone(config_data)
            self.assertTrue(config_data.get('enabled'))
            self.assertEqual(config_data.get('version'), '1.0.0')
            
            logger.info("配置加载测试通过")
            
        except ImportError as e:
            self.skipTest(f"配置管理器模块不可用: {e}")
    
    def test_config_validation(self):
        """测试配置验证"""
        try:
            from config.config_manager import ConfigManager
            
            config_manager = ConfigManager(config_dir=str(self.config_dir))
            
            # 测试有效配置
            valid_config = {
                'version': '1.0.0',
                'enabled': True,
                'trading': {'timeout': 30}
            }
            self.assertTrue(config_manager._validate_config(valid_config, 'test'))
            
            # 测试无效配置
            invalid_config = {
                'version': '1.0.0',
                'enabled': 'invalid_boolean',  # 应该是布尔值
                'trading': {'timeout': -1}     # 应该是正数
            }
            self.assertFalse(config_manager._validate_config(invalid_config, 'test'))
            
            logger.info("配置验证测试通过")
            
        except ImportError as e:
            self.skipTest(f"配置管理器模块不可用: {e}")


class TestHotReloadManager(HotReloadTestCase):
    """热重载管理器测试"""
    
    def test_file_monitoring(self):
        """测试文件监控功能"""
        try:
            from config.hot_reload_manager import HotReloadManager
            from config.config_manager import ConfigManager
            
            config_manager = ConfigManager(config_dir=str(self.config_dir))
            hot_reload_manager = HotReloadManager(config_manager)
            
            # 配置监控
            hot_reload_manager.add_watch_path(str(self.config_dir))
            
            # 启动监控
            hot_reload_manager.start_monitoring()
            self.assertTrue(hot_reload_manager.is_running)
            
            # 测试文件变更检测
            reload_triggered = False
            
            async def test_callback(file_path: str, event_type: str):
                nonlocal reload_triggered
                reload_triggered = True
                logger.info(f"检测到文件变更: {file_path}, 事件: {event_type}")
            
            hot_reload_manager.add_change_callback(test_callback)
            
            # 修改配置文件
            self.update_test_config({'trading': {'timeout': 60}})
            
            # 等待文件监控检测到变更
            time.sleep(2)
            
            # 停止监控
            hot_reload_manager.stop_monitoring()
            self.assertFalse(hot_reload_manager.is_running)
            
            logger.info("文件监控测试通过")
            
        except ImportError as e:
            self.skipTest(f"热重载管理器模块不可用: {e}")
    
    def test_config_reload(self):
        """测试配置重载"""
        try:
            from config.hot_reload_manager import HotReloadManager
            from config.config_manager import ConfigManager
            
            config_manager = ConfigManager(config_dir=str(self.config_dir))
            hot_reload_manager = HotReloadManager(config_manager)
            
            # 记录重载事件
            reload_events = []
            
            async def reload_callback(file_path: str, config_data: dict):
                reload_events.append({
                    'file_path': file_path,
                    'config_data': config_data,
                    'timestamp': datetime.now()
                })
                logger.info(f"配置重载回调触发: {file_path}")
            
            hot_reload_manager.add_reload_callback(reload_callback)
            
            # 手动触发配置重载
            asyncio.run(hot_reload_manager.reload_config_file(str(self.test_config_file)))
            
            # 验证重载事件
            self.assertEqual(len(reload_events), 1)
            self.assertIn('trading', reload_events[0]['config_data'])
            
            logger.info("配置重载测试通过")
            
        except ImportError as e:
            self.skipTest(f"热重载管理器模块不可用: {e}")


class TestVersionManager(HotReloadTestCase):
    """版本管理器测试"""
    
    def test_version_creation(self):
        """测试版本创建"""
        try:
            from config.version_manager import ConfigVersionManager
            
            # 创建版本管理器
            versions_dir = self.test_dir / "versions"
            version_manager = ConfigVersionManager(
                base_dir=str(self.config_dir),
                versions_dir=str(versions_dir)
            )
            
            # 创建配置版本
            version_id = version_manager.create_version(
                config_file="test_config.yaml",
                description="测试版本创建",
                author="test_user"
            )
            
            self.assertIsNotNone(version_id)
            self.assertTrue(version_id.startswith('v_'))
            
            # 验证版本信息
            versions = version_manager.get_version_list("test_config.yaml")
            self.assertEqual(len(versions), 1)
            self.assertEqual(versions[0]['version_id'], version_id)
            self.assertEqual(versions[0]['description'], "测试版本创建")
            
            logger.info(f"版本创建测试通过，版本ID: {version_id}")
            
        except ImportError as e:
            self.skipTest(f"版本管理器模块不可用: {e}")
    
    def test_version_rollback(self):
        """测试版本回滚"""
        try:
            from config.version_manager import ConfigVersionManager
            
            versions_dir = self.test_dir / "versions"
            version_manager = ConfigVersionManager(
                base_dir=str(self.config_dir),
                versions_dir=str(versions_dir)
            )
            
            # 创建初始版本
            version1_id = version_manager.create_version(
                config_file="test_config.yaml",
                description="初始版本",
                author="test_user"
            )
            
            # 修改配置文件
            original_timeout = 30
            new_timeout = 60
            
            self.update_test_config({'trading': {'timeout': new_timeout}})
            
            # 创建修改后的版本
            version2_id = version_manager.create_version(
                config_file="test_config.yaml",
                description="修改超时时间",
                author="test_user"
            )
            
            # 验证配置已修改
            with open(self.test_config_file, 'r', encoding='utf-8') as f:
                current_config = yaml.safe_load(f)
            self.assertEqual(current_config['trading']['timeout'], new_timeout)
            
            # 回滚到初始版本
            success = version_manager.rollback_to_version(version1_id)
            self.assertTrue(success)
            
            # 验证配置已回滚
            with open(self.test_config_file, 'r', encoding='utf-8') as f:
                rolled_back_config = yaml.safe_load(f)
            self.assertEqual(rolled_back_config['trading']['timeout'], original_timeout)
            
            logger.info("版本回滚测试通过")
            
        except ImportError as e:
            self.skipTest(f"版本管理器模块不可用: {e}")


class TestHotReloadService(HotReloadTestCase):
    """热重载服务测试"""
    
    def test_service_initialization(self):
        """测试服务初始化"""
        try:
            from config.hot_reload_service import HotReloadService
            from config.config_manager import ConfigManager
            
            config_manager = ConfigManager(config_dir=str(self.config_dir))
            service = HotReloadService(config_manager)
            
            self.assertFalse(service.is_running)
            self.assertEqual(len(service.component_handlers), 0)
            
            logger.info("热重载服务初始化测试通过")
            
        except ImportError as e:
            self.skipTest(f"热重载服务模块不可用: {e}")
    
    def test_component_handler_registration(self):
        """测试组件处理器注册"""
        try:
            from config.hot_reload_service import HotReloadService
            from config.config_manager import ConfigManager
            
            config_manager = ConfigManager(config_dir=str(self.config_dir))
            service = HotReloadService(config_manager)
            
            # 注册处理器
            handler_called = False
            
            async def test_handler(config_data: dict):
                nonlocal handler_called
                handler_called = True
                logger.info(f"测试处理器被调用: {list(config_data.keys())}")
            
            service.register_component_handler('test_component', test_handler)
            self.assertEqual(len(service.component_handlers), 1)
            self.assertIn('test_component', service.component_handlers)
            
            # 测试处理器调用
            test_config = {'test_key': 'test_value'}
            asyncio.run(service.component_handlers['test_component'](test_config))
            self.assertTrue(handler_called)
            
            logger.info("组件处理器注册测试通过")
            
        except ImportError as e:
            self.skipTest(f"热重载服务模块不可用: {e}")


class TestIntegration(HotReloadTestCase):
    """集成测试"""
    
    def test_end_to_end_hot_reload(self):
        """端到端热重载测试"""
        try:
            from config.hot_reload_service import HotReloadService
            from config.config_manager import ConfigManager
            
            # 初始化组件
            config_manager = ConfigManager(config_dir=str(self.config_dir))
            service = HotReloadService(config_manager)
            
            # 模拟组件状态
            component_state = {'config_loaded': False, 'last_config': None}
            
            async def component_handler(config_data: dict):
                component_state['config_loaded'] = True
                component_state['last_config'] = config_data
                logger.info("模拟组件配置已更新")
            
            service.register_component_handler('test_component', component_handler)
            
            # 启动服务
            asyncio.run(service.start())
            self.assertTrue(service.is_running)
            
            # 添加监控路径
            service.manager.add_watch_path(str(self.config_dir))
            
            # 修改配置文件
            updates = {
                'trading': {'timeout': 120, 'retry_count': 5},
                'risk_management': {'stop_loss_percent': 3.0}
            }
            self.update_test_config(updates)
            
            # 等待配置重载
            time.sleep(3)
            
            # 验证组件状态更新
            self.assertTrue(component_state['config_loaded'])
            self.assertIsNotNone(component_state['last_config'])
            
            # 停止服务
            asyncio.run(service.stop())
            self.assertFalse(service.is_running)
            
            logger.info("端到端热重载测试通过")
            
        except ImportError as e:
            self.skipTest(f"热重载模块不可用: {e}")


class TestPerformance(HotReloadTestCase):
    """性能测试"""
    
    def test_reload_performance(self):
        """测试重载性能"""
        try:
            from config.hot_reload_service import HotReloadService
            from config.config_manager import ConfigManager
            
            config_manager = ConfigManager(config_dir=str(self.config_dir))
            service = HotReloadService(config_manager)
            
            # 创建多个配置文件
            config_files = []
            for i in range(10):
                config_file = self.config_dir / f"test_config_{i}.yaml"
                config_data = {
                    'version': f'1.0.{i}',
                    'enabled': True,
                    'data': {'value': i, 'timestamp': datetime.now().isoformat()}
                }
                
                with open(config_file, 'w', encoding='utf-8') as f:
                    yaml.dump(config_data, f)
                
                config_files.append(config_file)
            
            # 测量重载时间
            reload_times = []
            
            for config_file in config_files:
                start_time = time.time()
                asyncio.run(service.manager.reload_config_file(str(config_file)))
                end_time = time.time()
                
                reload_time = end_time - start_time
                reload_times.append(reload_time)
            
            # 计算性能指标
            avg_reload_time = sum(reload_times) / len(reload_times)
            max_reload_time = max(reload_times)
            min_reload_time = min(reload_times)
            
            logger.info(f"重载性能测试结果:")
            logger.info(f"  平均重载时间: {avg_reload_time:.4f}s")
            logger.info(f"  最大重载时间: {max_reload_time:.4f}s")
            logger.info(f"  最小重载时间: {min_reload_time:.4f}s")
            
            # 性能断言（根据实际需求调整）
            self.assertLess(avg_reload_time, 1.0, "平均重载时间应小于1秒")
            self.assertLess(max_reload_time, 2.0, "最大重载时间应小于2秒")
            
            logger.info("重载性能测试通过")
            
        except ImportError as e:
            self.skipTest(f"热重载模块不可用: {e}")


class TestErrorHandling(HotReloadTestCase):
    """错误处理测试"""
    
    def test_invalid_config_handling(self):
        """测试无效配置处理"""
        try:
            from config.hot_reload_service import HotReloadService
            from config.config_manager import ConfigManager
            
            config_manager = ConfigManager(config_dir=str(self.config_dir))
            service = HotReloadService(config_manager)
            
            # 创建无效配置文件
            invalid_config_file = self.config_dir / "invalid_config.yaml"
            with open(invalid_config_file, 'w', encoding='utf-8') as f:
                f.write("invalid: yaml: content:\n  - missing\n    proper: indentation")
            
            # 尝试加载无效配置
            with self.assertLogs(level='ERROR'):
                asyncio.run(service.manager.reload_config_file(str(invalid_config_file)))
            
            logger.info("无效配置处理测试通过")
            
        except ImportError as e:
            self.skipTest(f"热重载模块不可用: {e}")
    
    def test_file_permission_error(self):
        """测试文件权限错误处理"""
        try:
            from config.hot_reload_service import HotReloadService
            from config.config_manager import ConfigManager
            
            config_manager = ConfigManager(config_dir=str(self.config_dir))
            service = HotReloadService(config_manager)
            
            # 创建受限权限的文件
            restricted_file = self.config_dir / "restricted_config.yaml"
            with open(restricted_file, 'w', encoding='utf-8') as f:
                yaml.dump({'test': 'data'}, f)
            
            # 移除读取权限（在Windows上可能不生效）
            if os.name != 'nt':  # 非Windows系统
                os.chmod(restricted_file, 0o000)
                
                # 尝试加载受限文件
                with self.assertLogs(level='ERROR'):
                    asyncio.run(service.manager.reload_config_file(str(restricted_file)))
                
                # 恢复权限以便清理
                os.chmod(restricted_file, 0o644)
            
            logger.info("文件权限错误处理测试通过")
            
        except ImportError as e:
            self.skipTest(f"热重载模块不可用: {e}")


def run_all_tests():
    """运行所有测试"""
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加测试用例
    test_classes = [
        TestConfigManager,
        TestHotReloadManager,
        TestVersionManager,
        TestHotReloadService,
        TestIntegration,
        TestPerformance,
        TestErrorHandling
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 输出测试结果摘要
    print(f"\n{'='*50}")
    print("测试结果摘要:")
    print(f"运行测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print(f"跳过: {len(result.skipped)}")
    
    if result.failures:
        print("\n失败的测试:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("开始配置热重载功能测试...")
    print(f"测试时间: {datetime.now()}")
    print("="*50)
    
    success = run_all_tests()
    
    if success:
        print("\n✅ 所有测试通过！")
        exit(0)
    else:
        print("\n❌ 部分测试失败！")
        exit(1)