"""
完整的MVP验证与优化体系测试运行器

整合所有验证、优化、监控和压力测试功能
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

# 添加项目路径到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入所有模块
from src.validation import MVPValidator, PerformanceAnalyzer, SystemChecker, BenchmarkRunner
from src.optimization import DatabaseOptimizer, CacheManager, MemoryOptimizer, ConfigTuner
from scripts import (
    MVPValidationRunner, HealthCheckScheduler, 
    PerformanceBenchmarkRunner, StressTestRunner
)
from src.monitor import SystemMonitor, DiagnosticAnalyzer, AlertManager, ReportGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('mvp_test_system.log')
    ]
)

logger = logging.getLogger(__name__)


class MVPTestSystemRunner:
    """MVP验证与优化体系测试运行器"""
    
    def __init__(self, config_file: Optional[str] = None):
        # 默认配置
        self.config = {
            # 数据库配置
            'database': {
                'type': 'sqlite',
                'database': 'test_trading.db',
                'host': 'localhost',
                'port': 5432,
                'user': 'user',
                'password': 'password'
            },
            
            # Redis配置
            'redis': {
                'host': 'localhost',
                'port': 6379,
                'db': 0,
                'password': None
            },
            
            # Web服务配置
            'web_service': {
                'host': 'localhost',
                'port': 8000,
                'endpoints': ['/health', '/api/data', '/api/strategies']
            },
            
            # 验证配置
            'validation': {
                'technical_thresholds': {
                    'max_response_time_ms': 100,
                    'max_cpu_percent': 80,
                    'max_memory_percent': 70,
                    'min_success_rate': 99.5
                },
                'business_thresholds': {
                    'min_data_accuracy': 95.0,
                    'min_feature_coverage': 90.0,
                    'max_error_rate': 0.5
                }
            },
            
            # 优化配置
            'optimization': {
                'enable_database_optimization': True,
                'enable_cache_optimization': True,
                'enable_memory_optimization': True,
                'enable_config_tuning': True
            },
            
            # 监控配置
            'monitoring': {
                'enable_system_monitor': True,
                'enable_diagnostics': True,
                'enable_alerts': True,
                'monitoring_interval': 5.0
            },
            
            # 压力测试配置
            'stress_test': {
                'enable_cpu_test': True,
                'enable_memory_test': True,
                'enable_disk_test': True,
                'enable_api_test': True,
                'test_duration': 60,
                'concurrent_workers': 4
            },
            
            # 报告配置
            'reporting': {
                'output_dir': 'test_reports',
                'generate_html': True,
                'generate_json': True,
                'enable_charts': True
            }
        }
        
        # 加载配置文件
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                self.config.update(file_config)
                logger.info(f"已加载配置文件: {config_file}")
            except Exception as e:
                logger.warning(f"加载配置文件失败，使用默认配置: {e}")
        
        # 初始化组件
        self.components = {}
        self.test_results = {}
        
        logger.info("MVP验证与优化体系测试运行器已初始化")
    
    async def initialize_components(self):
        """初始化所有组件"""
        try:
            logger.info("开始初始化所有组件...")
            
            # 验证模块
            self.components['mvp_validator'] = MVPValidator(self.config)
            self.components['performance_analyzer'] = PerformanceAnalyzer(self.config)
            self.components['system_checker'] = SystemChecker(self.config)
            self.components['benchmark_runner'] = BenchmarkRunner(self.config)
            
            # 优化模块
            self.components['database_optimizer'] = DatabaseOptimizer(self.config)
            self.components['cache_manager'] = CacheManager(self.config)
            self.components['memory_optimizer'] = MemoryOptimizer(self.config)
            self.components['config_tuner'] = ConfigTuner(self.config)
            
            # 监控模块
            self.components['system_monitor'] = SystemMonitor(self.config)
            self.components['diagnostic_analyzer'] = DiagnosticAnalyzer(self.config)
            self.components['alert_manager'] = AlertManager(self.config)
            self.components['report_generator'] = ReportGenerator(self.config)
            
            # 脚本模块
            self.components['mvp_validation_runner'] = MVPValidationRunner(self.config)
            self.components['health_check_scheduler'] = HealthCheckScheduler(self.config)
            self.components['performance_benchmark_runner'] = PerformanceBenchmarkRunner(self.config)
            self.components['stress_test_runner'] = StressTestRunner(self.config)
            
            logger.info(f"成功初始化 {len(self.components)} 个组件")
            
        except Exception as e:
            logger.error(f"初始化组件失败: {e}")
            raise
    
    async def run_validation_tests(self) -> Dict[str, Any]:
        """运行验证测试"""
        logger.info("开始运行验证测试...")
        
        try:
            validation_results = {}
            
            # 运行MVP验证
            logger.info("运行MVP验证...")
            mvp_runner = self.components['mvp_validation_runner']
            mvp_results = await mvp_runner.run_full_validation()
            validation_results['mvp_validation'] = mvp_results
            
            # 运行性能基准测试
            logger.info("运行性能基准测试...")
            benchmark_runner = self.components['performance_benchmark_runner']
            benchmark_results = await benchmark_runner.run_all_benchmarks()
            validation_results['performance_benchmarks'] = benchmark_results
            
            # 运行系统健康检查
            logger.info("运行系统健康检查...")
            health_scheduler = self.components['health_check_scheduler']
            health_results = await health_scheduler.run_health_check()
            validation_results['health_check'] = health_results
            
            logger.info("验证测试完成")
            return validation_results
            
        except Exception as e:
            logger.error(f"运行验证测试失败: {e}")
            return {'error': str(e)}
    
    async def run_optimization_tests(self) -> Dict[str, Any]:
        """运行优化测试"""
        logger.info("开始运行优化测试...")
        
        try:
            optimization_results = {}
            
            if self.config['optimization']['enable_database_optimization']:
                logger.info("运行数据库优化...")
                db_optimizer = self.components['database_optimizer']
                db_results = await db_optimizer.optimize_all()
                optimization_results['database_optimization'] = db_results
            
            if self.config['optimization']['enable_cache_optimization']:
                logger.info("运行缓存优化...")
                cache_manager = self.components['cache_manager']
                cache_results = await cache_manager.optimize_cache()
                optimization_results['cache_optimization'] = cache_results
            
            if self.config['optimization']['enable_memory_optimization']:
                logger.info("运行内存优化...")
                memory_optimizer = self.components['memory_optimizer']
                memory_results = await memory_optimizer.optimize_memory()
                optimization_results['memory_optimization'] = memory_results
            
            if self.config['optimization']['enable_config_tuning']:
                logger.info("运行配置调优...")
                config_tuner = self.components['config_tuner']
                config_results = await config_tuner.auto_tune()
                optimization_results['config_tuning'] = config_results
            
            logger.info("优化测试完成")
            return optimization_results
            
        except Exception as e:
            logger.error(f"运行优化测试失败: {e}")
            return {'error': str(e)}
    
    async def run_stress_tests(self) -> Dict[str, Any]:
        """运行压力测试"""
        logger.info("开始运行压力测试...")
        
        try:
            stress_results = {}
            stress_runner = self.components['stress_test_runner']
            
            # 创建测试配置
            from scripts.stress_test_runner import StressTestConfig
            test_configs = []
            
            if self.config['stress_test']['enable_cpu_test']:
                test_configs.append(StressTestConfig(
                    test_name="CPU压力测试",
                    test_type="cpu",
                    duration_seconds=self.config['stress_test']['test_duration'],
                    target_load=80.0,
                    concurrent_workers=self.config['stress_test']['concurrent_workers']
                ))
            
            if self.config['stress_test']['enable_memory_test']:
                test_configs.append(StressTestConfig(
                    test_name="内存压力测试",
                    test_type="memory",
                    duration_seconds=self.config['stress_test']['test_duration'],
                    target_load=70.0,
                    concurrent_workers=2
                ))
            
            if self.config['stress_test']['enable_disk_test']:
                test_configs.append(StressTestConfig(
                    test_name="磁盘IO压力测试",
                    test_type="disk",
                    duration_seconds=self.config['stress_test']['test_duration'],
                    target_load=50.0,
                    concurrent_workers=self.config['stress_test']['concurrent_workers'],
                    parameters={
                        'file_size_mb': 100,
                        'file_count': self.config['stress_test']['concurrent_workers'],
                        'block_size': 4096
                    }
                ))
            
            if self.config['stress_test']['enable_api_test']:
                web_config = self.config['web_service']
                test_configs.append(StressTestConfig(
                    test_name="Web API压力测试",
                    test_type="web_api",
                    duration_seconds=self.config['stress_test']['test_duration'],
                    target_load=100.0,
                    concurrent_workers=self.config['stress_test']['concurrent_workers'],
                    parameters={
                        'base_url': f"http://{web_config['host']}:{web_config['port']}",
                        'endpoints': web_config['endpoints'],
                        'http_method': 'GET',
                        'request_timeout': 5.0
                    }
                ))
            
            # 运行压力测试套件
            if test_configs:
                results = await stress_runner.run_stress_test_suite(test_configs)
                stress_results['test_results'] = [result.to_dict() for result in results]
                stress_results['summary'] = {
                    'total_tests': len(results),
                    'passed_tests': len([r for r in results if r.passed]),
                    'failed_tests': len([r for r in results if not r.passed]),
                    'overall_pass_rate': (len([r for r in results if r.passed]) / len(results)) * 100 if results else 0
                }
            else:
                stress_results = {'message': '未启用任何压力测试'}
            
            logger.info("压力测试完成")
            return stress_results
            
        except Exception as e:
            logger.error(f"运行压力测试失败: {e}")
            return {'error': str(e)}
    
    async def run_monitoring_tests(self) -> Dict[str, Any]:
        """运行监控测试"""
        logger.info("开始运行监控测试...")
        
        try:
            monitoring_results = {}
            
            if self.config['monitoring']['enable_system_monitor']:
                logger.info("测试系统监控...")
                system_monitor = self.components['system_monitor']
                
                # 启动监控
                await system_monitor.start_monitoring()
                
                # 运行一段时间收集数据
                await asyncio.sleep(30)
                
                # 获取监控结果
                metrics = system_monitor.get_current_metrics()
                monitoring_results['system_metrics'] = metrics.to_dict() if metrics else None
                
                # 停止监控
                await system_monitor.stop_monitoring()
            
            if self.config['monitoring']['enable_diagnostics']:
                logger.info("测试诊断分析...")
                diagnostic_analyzer = self.components['diagnostic_analyzer']
                
                # 模拟一些异常数据进行诊断
                test_metrics = [
                    {'timestamp': datetime.now(), 'cpu_percent': 95.0, 'memory_percent': 85.0},
                    {'timestamp': datetime.now(), 'cpu_percent': 88.0, 'memory_percent': 82.0},
                    {'timestamp': datetime.now(), 'cpu_percent': 92.0, 'memory_percent': 87.0}
                ]
                
                anomalies = await diagnostic_analyzer.detect_anomalies('cpu_percent', test_metrics)
                monitoring_results['anomaly_detection'] = [anomaly.to_dict() for anomaly in anomalies]
            
            logger.info("监控测试完成")
            return monitoring_results
            
        except Exception as e:
            logger.error(f"运行监控测试失败: {e}")
            return {'error': str(e)}
    
    async def generate_comprehensive_report(self, all_results: Dict[str, Any]):
        """生成综合报告"""
        logger.info("开始生成综合报告...")
        
        try:
            report_generator = self.components['report_generator']
            
            # 生成MVP验证报告
            if 'validation_results' in all_results:
                validation_report = await report_generator.generate_mvp_validation_report(
                    all_results['validation_results']
                )
                
                # 导出报告
                if self.config['reporting']['generate_html']:
                    html_file = await report_generator.export_report(validation_report, 'html')
                    logger.info(f"MVP验证HTML报告已生成: {html_file}")
                
                if self.config['reporting']['generate_json']:
                    json_file = await report_generator.export_report(validation_report, 'json')
                    logger.info(f"MVP验证JSON报告已生成: {json_file}")
            
            # 生成系统性能报告
            if 'monitoring_results' in all_results:
                performance_report = await report_generator.generate_system_performance_report()
                
                if self.config['reporting']['generate_html']:
                    html_file = await report_generator.export_report(performance_report, 'html')
                    logger.info(f"系统性能HTML报告已生成: {html_file}")
            
            # 生成综合汇总报告
            summary_report = self._create_summary_report(all_results)
            summary_file = Path(self.config['reporting']['output_dir']) / f"comprehensive_summary_{int(datetime.now().timestamp())}.json"
            summary_file.parent.mkdir(exist_ok=True)
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary_report, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"综合汇总报告已生成: {summary_file}")
            
        except Exception as e:
            logger.error(f"生成综合报告失败: {e}")
    
    def _create_summary_report(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """创建汇总报告"""
        summary = {
            'test_run_info': {
                'timestamp': datetime.now().isoformat(),
                'total_components_tested': len(self.components),
                'config_summary': {
                    'validation_enabled': bool(all_results.get('validation_results')),
                    'optimization_enabled': bool(all_results.get('optimization_results')),
                    'stress_test_enabled': bool(all_results.get('stress_test_results')),
                    'monitoring_enabled': bool(all_results.get('monitoring_results'))
                }
            },
            'overall_results': {},
            'detailed_results': all_results
        }
        
        # 计算总体结果
        total_tests = 0
        passed_tests = 0
        
        # 验证测试结果
        if 'validation_results' in all_results:
            validation_data = all_results['validation_results']
            for category, data in validation_data.items():
                if isinstance(data, dict) and 'results' in data:
                    results = data['results']
                    total_tests += len(results)
                    passed_tests += len([r for r in results if r.get('passed', False)])
        
        # 压力测试结果
        if 'stress_test_results' in all_results:
            stress_data = all_results['stress_test_results']
            if 'summary' in stress_data:
                total_tests += stress_data['summary']['total_tests']
                passed_tests += stress_data['summary']['passed_tests']
        
        # 计算总体通过率
        overall_pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        summary['overall_results'] = {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'overall_pass_rate': overall_pass_rate,
            'grade': self._get_performance_grade(overall_pass_rate)
        }
        
        return summary
    
    def _get_performance_grade(self, pass_rate: float) -> str:
        """获取性能等级"""
        if pass_rate >= 95:
            return "优秀"
        elif pass_rate >= 85:
            return "良好"
        elif pass_rate >= 70:
            return "一般"
        else:
            return "需要改进"
    
    async def run_full_test_suite(self) -> Dict[str, Any]:
        """运行完整的测试套件"""
        logger.info("开始运行完整的MVP验证与优化体系测试套件")
        
        start_time = datetime.now()
        all_results = {}
        
        try:
            # 初始化组件
            await self.initialize_components()
            
            # 运行验证测试
            logger.info("=" * 50)
            validation_results = await self.run_validation_tests()
            all_results['validation_results'] = validation_results
            
            # 运行优化测试
            logger.info("=" * 50)
            optimization_results = await self.run_optimization_tests()
            all_results['optimization_results'] = optimization_results
            
            # 运行压力测试
            logger.info("=" * 50)
            stress_test_results = await self.run_stress_tests()
            all_results['stress_test_results'] = stress_test_results
            
            # 运行监控测试
            logger.info("=" * 50)
            monitoring_results = await self.run_monitoring_tests()
            all_results['monitoring_results'] = monitoring_results
            
            # 生成综合报告
            logger.info("=" * 50)
            await self.generate_comprehensive_report(all_results)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info("=" * 50)
            logger.info(f"完整测试套件运行完成，耗时: {duration:.2f} 秒")
            
            # 输出汇总结果
            summary = self._create_summary_report(all_results)
            overall_results = summary['overall_results']
            
            logger.info(f"测试汇总:")
            logger.info(f"  总测试数: {overall_results['total_tests']}")
            logger.info(f"  通过测试: {overall_results['passed_tests']}")
            logger.info(f"  失败测试: {overall_results['failed_tests']}")
            logger.info(f"  总体通过率: {overall_results['overall_pass_rate']:.1f}%")
            logger.info(f"  性能等级: {overall_results['grade']}")
            
            return all_results
            
        except Exception as e:
            logger.error(f"运行完整测试套件失败: {e}")
            return {'error': str(e)}
        
        finally:
            # 清理资源
            await self.cleanup()
    
    async def cleanup(self):
        """清理资源"""
        try:
            logger.info("开始清理资源...")
            
            # 清理各个组件
            for name, component in self.components.items():
                try:
                    if hasattr(component, 'cleanup'):
                        await component.cleanup()
                    elif hasattr(component, 'close'):
                        await component.close()
                    elif hasattr(component, 'stop'):
                        await component.stop()
                except Exception as e:
                    logger.warning(f"清理组件 {name} 失败: {e}")
            
            logger.info("资源清理完成")
            
        except Exception as e:
            logger.error(f"清理资源失败: {e}")


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='MVP验证与优化体系测试运行器')
    parser.add_argument('--config', '-c', help='配置文件路径')
    parser.add_argument('--mode', '-m', choices=['full', 'validation', 'optimization', 'stress', 'monitoring'], 
                       default='full', help='运行模式')
    parser.add_argument('--output', '-o', help='输出目录')
    
    args = parser.parse_args()
    
    # 创建测试运行器
    runner = MVPTestSystemRunner(args.config)
    
    # 更新输出目录
    if args.output:
        runner.config['reporting']['output_dir'] = args.output
    
    try:
        if args.mode == 'full':
            results = await runner.run_full_test_suite()
        elif args.mode == 'validation':
            await runner.initialize_components()
            results = await runner.run_validation_tests()
        elif args.mode == 'optimization':
            await runner.initialize_components()
            results = await runner.run_optimization_tests()
        elif args.mode == 'stress':
            await runner.initialize_components()
            results = await runner.run_stress_tests()
        elif args.mode == 'monitoring':
            await runner.initialize_components()
            results = await runner.run_monitoring_tests()
        
        # 输出结果摘要
        if 'error' not in results:
            print(f"\n{args.mode} 模式测试完成!")
            print(f"详细结果请查看日志文件和报告目录: {runner.config['reporting']['output_dir']}")
        else:
            print(f"\n{args.mode} 模式测试失败: {results['error']}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("用户中断测试")
        print("\n测试被用户中断")
    except Exception as e:
        logger.error(f"测试运行异常: {e}")
        print(f"\n测试运行失败: {e}")
        sys.exit(1)
    finally:
        await runner.cleanup()


if __name__ == '__main__':
    asyncio.run(main())