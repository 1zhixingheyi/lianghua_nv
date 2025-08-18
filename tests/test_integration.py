"""
MVP验证与优化体系集成测试

验证所有模块的基本功能和集成性
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any, List
import tempfile
import shutil

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入测试模块
from src.validation import MVPValidator, PerformanceAnalyzer, SystemChecker, BenchmarkRunner
from src.optimization import DatabaseOptimizer, CacheManager, MemoryOptimizer, ConfigTuner
from src.monitor import SystemMonitor, DiagnosticAnalyzer, AlertManager, ReportGenerator
from scripts import (
    MVPValidationRunner, HealthCheckScheduler, 
    PerformanceBenchmarkRunner, StressTestRunner
)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)


class IntegrationTester:
    """集成测试器"""
    
    def __init__(self):
        # 创建临时目录用于测试
        self.temp_dir = Path(tempfile.mkdtemp(prefix='mvp_integration_test_'))
        
        # 基础配置
        self.config = {
            'database': {
                'type': 'sqlite',
                'database': str(self.temp_dir / 'test.db')
            },
            'redis': {
                'host': 'localhost',
                'port': 6379,
                'db': 1  # 使用测试数据库
            },
            'validation': {
                'technical_thresholds': {
                    'max_response_time_ms': 100,
                    'max_cpu_percent': 80,
                    'max_memory_percent': 70
                }
            },
            'stress_test': {
                'output_dir': str(self.temp_dir / 'stress_results')
            },
            'report_generator': {
                'output_dir': str(self.temp_dir / 'reports'),
                'chart_dir': str(self.temp_dir / 'charts')
            }
        }
        
        self.test_results = {}
        
    async def test_validation_module(self) -> bool:
        """测试验证模块"""
        logger.info("测试验证模块...")
        
        try:
            # 测试MVP验证器
            mvp_validator = MVPValidator(self.config)
            tech_results = await mvp_validator.validate_technical_metrics()
            assert 'results' in tech_results
            logger.info(f"MVP验证器测试通过: {len(tech_results['results'])} 个检查项")
            
            # 测试性能分析器
            performance_analyzer = PerformanceAnalyzer(self.config)
            await performance_analyzer.start_monitoring()
            await asyncio.sleep(2)  # 收集一些数据
            current_metrics = performance_analyzer.get_current_metrics()
            await performance_analyzer.stop_monitoring()
            assert current_metrics is not None
            logger.info("性能分析器测试通过")
            
            # 测试系统检查器
            system_checker = SystemChecker(self.config)
            health_results = await system_checker.run_health_checks()
            assert 'results' in health_results
            logger.info(f"系统检查器测试通过: {len(health_results['results'])} 个检查项")
            
            # 测试基准测试运行器
            benchmark_runner = BenchmarkRunner(self.config)
            benchmark_results = await benchmark_runner.run_data_processing_benchmark()
            assert 'passed' in benchmark_results
            logger.info("基准测试运行器测试通过")
            
            self.test_results['validation_module'] = True
            return True
            
        except Exception as e:
            logger.error(f"验证模块测试失败: {e}")
            self.test_results['validation_module'] = False
            return False
    
    async def test_optimization_module(self) -> bool:
        """测试优化模块"""
        logger.info("测试优化模块...")
        
        try:
            # 测试数据库优化器
            db_optimizer = DatabaseOptimizer(self.config)
            db_suggestions = await db_optimizer.analyze_query_performance()
            assert isinstance(db_suggestions, list)
            logger.info(f"数据库优化器测试通过: {len(db_suggestions)} 个建议")
            
            # 测试缓存管理器
            cache_manager = CacheManager(self.config)
            await cache_manager.set('test_key', 'test_value')
            value = await cache_manager.get('test_key')
            assert value == 'test_value'
            cache_stats = cache_manager.get_stats()
            assert 'total_operations' in cache_stats
            logger.info("缓存管理器测试通过")
            
            # 测试内存优化器
            memory_optimizer = MemoryOptimizer(self.config)
            memory_analysis = await memory_optimizer.analyze_memory_usage()
            assert 'current_usage' in memory_analysis
            logger.info("内存优化器测试通过")
            
            # 测试配置调优器
            config_tuner = ConfigTuner(self.config)
            tuning_suggestions = await config_tuner.analyze_config()
            assert isinstance(tuning_suggestions, list)
            logger.info(f"配置调优器测试通过: {len(tuning_suggestions)} 个建议")
            
            self.test_results['optimization_module'] = True
            return True
            
        except Exception as e:
            logger.error(f"优化模块测试失败: {e}")
            self.test_results['optimization_module'] = False
            return False
    
    async def test_monitoring_module(self) -> bool:
        """测试监控模块"""
        logger.info("测试监控模块...")
        
        try:
            # 测试系统监控器
            system_monitor = SystemMonitor(self.config)
            await system_monitor.start_monitoring()
            await asyncio.sleep(3)  # 收集一些数据
            metrics = system_monitor.get_current_metrics()
            await system_monitor.stop_monitoring()
            assert metrics is not None
            logger.info("系统监控器测试通过")
            
            # 测试诊断分析器
            diagnostic_analyzer = DiagnosticAnalyzer(self.config)
            test_metrics = [
                {'timestamp': '2023-01-01T00:00:00', 'cpu_percent': 95.0},
                {'timestamp': '2023-01-01T00:01:00', 'cpu_percent': 98.0},
                {'timestamp': '2023-01-01T00:02:00', 'cpu_percent': 96.0}
            ]
            anomalies = await diagnostic_analyzer.detect_anomalies('cpu_percent', test_metrics)
            assert isinstance(anomalies, list)
            logger.info(f"诊断分析器测试通过: 检测到 {len(anomalies)} 个异常")
            
            # 测试告警管理器
            alert_manager = AlertManager(self.config)
            await alert_manager.start()
            await asyncio.sleep(1)
            await alert_manager.stop()
            stats = alert_manager.get_alert_statistics()
            assert 'total_rules' in stats
            logger.info("告警管理器测试通过")
            
            # 测试报告生成器
            report_generator = ReportGenerator(self.config)
            test_validation_results = {
                'technical_metrics': {
                    'results': [
                        {'name': '测试项1', 'passed': True},
                        {'name': '测试项2', 'passed': False}
                    ]
                }
            }
            report = await report_generator.generate_mvp_validation_report(test_validation_results)
            assert report.title == 'MVP验证报告'
            logger.info("报告生成器测试通过")
            
            self.test_results['monitoring_module'] = True
            return True
            
        except Exception as e:
            logger.error(f"监控模块测试失败: {e}")
            self.test_results['monitoring_module'] = False
            return False
    
    async def test_scripts_module(self) -> bool:
        """测试脚本模块"""
        logger.info("测试脚本模块...")
        
        try:
            # 测试MVP验证运行器
            mvp_runner = MVPValidationRunner(self.config)
            validation_results = await mvp_runner.run_technical_validation()
            assert 'results' in validation_results
            logger.info("MVP验证运行器测试通过")
            
            # 测试健康检查调度器
            health_scheduler = HealthCheckScheduler(self.config)
            health_result = await health_scheduler.run_health_check()
            assert 'timestamp' in health_result
            logger.info("健康检查调度器测试通过")
            
            # 测试性能基准测试运行器
            benchmark_runner = PerformanceBenchmarkRunner(self.config)
            benchmark_results = await benchmark_runner.run_basic_benchmarks()
            assert isinstance(benchmark_results, list)
            logger.info(f"性能基准测试运行器测试通过: {len(benchmark_results)} 个基准测试")
            
            # 测试压力测试运行器
            stress_runner = StressTestRunner(self.config)
            from scripts.stress_test_runner import StressTestConfig
            
            test_config = StressTestConfig(
                test_name="集成测试CPU测试",
                test_type="cpu",
                duration_seconds=10,  # 短时间测试
                target_load=50.0,
                concurrent_workers=2
            )
            
            stress_result = await stress_runner.run_stress_test(test_config)
            assert stress_result.test_name == "集成测试CPU测试"
            logger.info("压力测试运行器测试通过")
            
            # 清理资源
            stress_runner.cleanup()
            
            self.test_results['scripts_module'] = True
            return True
            
        except Exception as e:
            logger.error(f"脚本模块测试失败: {e}")
            self.test_results['scripts_module'] = False
            return False
    
    async def test_integration(self) -> bool:
        """测试模块间集成"""
        logger.info("测试模块间集成...")
        
        try:
            # 集成测试：验证 -> 优化 -> 监控 -> 报告
            
            # 1. 运行验证
            mvp_validator = MVPValidator(self.config)
            validation_results = await mvp_validator.validate_technical_metrics()
            
            # 2. 基于验证结果进行优化
            if validation_results.get('overall_passed', True):
                logger.info("验证通过，进行优化...")
                cache_manager = CacheManager(self.config)
                await cache_manager.set('validation_status', 'passed')
                optimization_status = await cache_manager.get('validation_status')
                assert optimization_status == 'passed'
            
            # 3. 监控优化过程
            system_monitor = SystemMonitor(self.config)
            await system_monitor.start_monitoring()
            await asyncio.sleep(2)
            metrics = system_monitor.get_current_metrics()
            await system_monitor.stop_monitoring()
            
            # 4. 生成集成报告
            report_generator = ReportGenerator(self.config)
            integrated_results = {
                'validation': validation_results,
                'monitoring': {'metrics': metrics.to_dict() if metrics else {}}
            }
            
            # 模拟报告生成
            report_data = {
                'technical_metrics': {
                    'results': [
                        {'name': '集成测试项', 'passed': True}
                    ]
                }
            }
            
            report = await report_generator.generate_mvp_validation_report(report_data)
            
            logger.info("模块间集成测试通过")
            self.test_results['integration'] = True
            return True
            
        except Exception as e:
            logger.error(f"模块间集成测试失败: {e}")
            self.test_results['integration'] = False
            return False
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """运行所有集成测试"""
        logger.info("开始运行MVP验证与优化体系集成测试...")
        
        test_functions = [
            ('validation_module', self.test_validation_module),
            ('optimization_module', self.test_optimization_module),
            ('monitoring_module', self.test_monitoring_module),
            ('scripts_module', self.test_scripts_module),
            ('integration', self.test_integration)
        ]
        
        results = {}
        passed_tests = 0
        total_tests = len(test_functions)
        
        for test_name, test_func in test_functions:
            logger.info(f"运行测试: {test_name}")
            try:
                success = await test_func()
                results[test_name] = success
                if success:
                    passed_tests += 1
                    logger.info(f"✅ {test_name} 测试通过")
                else:
                    logger.error(f"❌ {test_name} 测试失败")
            except Exception as e:
                logger.error(f"❌ {test_name} 测试异常: {e}")
                results[test_name] = False
        
        # 计算总体结果
        pass_rate = (passed_tests / total_tests) * 100
        overall_passed = passed_tests == total_tests
        
        summary = {
            'overall_passed': overall_passed,
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'pass_rate': pass_rate,
            'detailed_results': results
        }
        
        logger.info("=" * 60)
        logger.info("集成测试完成!")
        logger.info(f"总测试数: {total_tests}")
        logger.info(f"通过测试: {passed_tests}")
        logger.info(f"失败测试: {total_tests - passed_tests}")
        logger.info(f"通过率: {pass_rate:.1f}%")
        logger.info(f"整体结果: {'✅ 通过' if overall_passed else '❌ 失败'}")
        
        return summary
    
    def cleanup(self):
        """清理测试资源"""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.info(f"已清理临时目录: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"清理临时目录失败: {e}")


async def main():
    """主函数"""
    tester = IntegrationTester()
    
    try:
        results = await tester.run_all_tests()
        
        # 输出最终结果
        if results['overall_passed']:
            print("\n🎉 MVP验证与优化体系集成测试全部通过!")
            print("系统已准备就绪，可以投入使用。")
            return 0
        else:
            print(f"\n⚠️  集成测试部分失败 (通过率: {results['pass_rate']:.1f}%)")
            print("请检查失败的测试项并修复相关问题。")
            return 1
            
    except Exception as e:
        logger.error(f"集成测试运行异常: {e}")
        print(f"\n❌ 集成测试运行失败: {e}")
        return 1
        
    finally:
        tester.cleanup()


if __name__ == '__main__':
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)