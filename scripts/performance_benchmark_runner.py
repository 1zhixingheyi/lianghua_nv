"""
性能基准测试运行器

自动化运行性能基准测试并生成报告
"""

import asyncio
import logging
import json
import time
import statistics
from typing import Dict, Any, List, Optional, Callable, Tuple
from datetime import datetime, timedelta
import sys
import os
import concurrent.futures
from dataclasses import dataclass
import threading

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validation import BenchmarkRunner, PerformanceAnalyzer
from optimization import DatabaseOptimizer, CacheManager

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkScenario:
    """基准测试场景"""
    name: str
    description: str
    category: str
    duration_seconds: int
    concurrent_users: int
    operations_per_user: int
    parameters: Dict[str, Any]
    expected_metrics: Dict[str, float]


class PerformanceBenchmarkResult:
    """性能基准测试结果"""
    
    def __init__(self, scenario_name: str):
        self.scenario_name = scenario_name
        self.start_time = datetime.now()
        self.end_time = None
        self.duration_seconds = 0
        
        # 性能指标
        self.throughput = 0.0  # 吞吐量 (ops/sec)
        self.response_times = []  # 响应时间列表
        self.success_count = 0
        self.failure_count = 0
        self.error_details = []
        
        # 统计指标
        self.avg_response_time = 0.0
        self.p50_response_time = 0.0
        self.p90_response_time = 0.0
        self.p95_response_time = 0.0
        self.p99_response_time = 0.0
        self.min_response_time = 0.0
        self.max_response_time = 0.0
        
        # 资源使用
        self.cpu_usage = []
        self.memory_usage = []
        self.network_io = []
        self.disk_io = []
        
        # 评估结果
        self.performance_score = 0.0
        self.bottlenecks = []
        self.recommendations = []
        self.status = "running"
    
    def finalize(self):
        """完成测试并计算统计指标"""
        self.end_time = datetime.now()
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        
        if self.response_times:
            self.avg_response_time = statistics.mean(self.response_times)
            self.min_response_time = min(self.response_times)
            self.max_response_time = max(self.response_times)
            
            sorted_times = sorted(self.response_times)
            n = len(sorted_times)
            
            self.p50_response_time = sorted_times[int(n * 0.5)]
            self.p90_response_time = sorted_times[int(n * 0.9)]
            self.p95_response_time = sorted_times[int(n * 0.95)]
            self.p99_response_time = sorted_times[int(n * 0.99)]
        
        # 计算吞吐量
        total_operations = self.success_count + self.failure_count
        if self.duration_seconds > 0:
            self.throughput = total_operations / self.duration_seconds
        
        # 计算成功率
        self.success_rate = self.success_count / max(total_operations, 1)
        
        # 评估性能
        self._evaluate_performance()
        
        self.status = "completed"
    
    def _evaluate_performance(self):
        """评估性能"""
        score = 100.0
        
        # 基于响应时间评分
        if self.avg_response_time > 2.0:
            score -= 30
        elif self.avg_response_time > 1.0:
            score -= 15
        elif self.avg_response_time > 0.5:
            score -= 5
        
        # 基于成功率评分
        if self.success_rate < 0.95:
            score -= 40
        elif self.success_rate < 0.98:
            score -= 20
        elif self.success_rate < 0.99:
            score -= 10
        
        # 基于P95响应时间评分
        if self.p95_response_time > 5.0:
            score -= 20
        elif self.p95_response_time > 3.0:
            score -= 10
        
        self.performance_score = max(score, 0)
        
        # 生成瓶颈分析
        if self.avg_response_time > 1.0:
            self.bottlenecks.append("平均响应时间过高")
        
        if self.success_rate < 0.99:
            self.bottlenecks.append("操作成功率偏低")
        
        if self.p95_response_time > 3.0:
            self.bottlenecks.append("P95响应时间过高")
        
        # 生成优化建议
        if self.avg_response_time > 1.0:
            self.recommendations.append("优化应用性能，减少响应时间")
        
        if self.success_rate < 0.99:
            self.recommendations.append("提高系统稳定性，减少错误率")
        
        if self.throughput < 100:
            self.recommendations.append("提升系统吞吐量")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'scenario_name': self.scenario_name,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration_seconds,
            'throughput': self.throughput,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'success_rate': getattr(self, 'success_rate', 0),
            'response_time_stats': {
                'avg': self.avg_response_time,
                'min': self.min_response_time,
                'max': self.max_response_time,
                'p50': self.p50_response_time,
                'p90': self.p90_response_time,
                'p95': self.p95_response_time,
                'p99': self.p99_response_time
            },
            'performance_score': self.performance_score,
            'bottlenecks': self.bottlenecks,
            'recommendations': self.recommendations,
            'error_details': self.error_details[:10],  # 只保存前10个错误
            'status': self.status
        }


class PerformanceBenchmarkRunner:
    """性能基准测试运行器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 基准测试配置
        self.benchmark_config = {
            'default_duration': 60,  # 默认测试时长（秒）
            'default_concurrent_users': 10,  # 默认并发用户数
            'default_operations_per_user': 100,  # 默认每用户操作数
            'warmup_duration': 10,  # 预热时间（秒）
            'cooldown_duration': 5,  # 冷却时间（秒）
            'monitor_resources': True,  # 是否监控资源使用
            'save_results': True,  # 是否保存结果
            'results_directory': 'benchmark_results',
            'scenarios': self._get_default_scenarios(),
            'performance_thresholds': {
                'avg_response_time': 1.0,
                'p95_response_time': 2.0,
                'success_rate': 0.99,
                'throughput': 100
            }
        }
        
        # 更新配置
        if 'performance_benchmark' in config:
            self.benchmark_config.update(config['performance_benchmark'])
        
        # 初始化组件
        self.benchmark_runner = BenchmarkRunner(config)
        self.performance_analyzer = PerformanceAnalyzer(config)
        
        # 确保结果目录存在
        os.makedirs(self.benchmark_config['results_directory'], exist_ok=True)
        
        # 监控状态
        self.monitoring_active = False
        self.resource_monitor_task = None
    
    def _get_default_scenarios(self) -> List[Dict[str, Any]]:
        """获取默认测试场景"""
        return [
            {
                'name': 'data_processing_light',
                'description': '轻量级数据处理测试',
                'category': 'data_processing',
                'duration_seconds': 30,
                'concurrent_users': 5,
                'operations_per_user': 50,
                'parameters': {'data_size': 'small'},
                'expected_metrics': {
                    'avg_response_time': 0.5,
                    'throughput': 50
                }
            },
            {
                'name': 'data_processing_heavy',
                'description': '重量级数据处理测试',
                'category': 'data_processing',
                'duration_seconds': 60,
                'concurrent_users': 10,
                'operations_per_user': 100,
                'parameters': {'data_size': 'large'},
                'expected_metrics': {
                    'avg_response_time': 1.0,
                    'throughput': 100
                }
            },
            {
                'name': 'trading_operations_normal',
                'description': '正常交易操作测试',
                'category': 'trading',
                'duration_seconds': 45,
                'concurrent_users': 8,
                'operations_per_user': 75,
                'parameters': {'order_type': 'market'},
                'expected_metrics': {
                    'avg_response_time': 0.3,
                    'throughput': 200
                }
            },
            {
                'name': 'database_operations_crud',
                'description': 'CRUD操作测试',
                'category': 'database',
                'duration_seconds': 40,
                'concurrent_users': 15,
                'operations_per_user': 80,
                'parameters': {'operation_mix': 'crud'},
                'expected_metrics': {
                    'avg_response_time': 0.2,
                    'throughput': 300
                }
            },
            {
                'name': 'cache_operations_intensive',
                'description': '缓存密集操作测试',
                'category': 'cache',
                'duration_seconds': 30,
                'concurrent_users': 20,
                'operations_per_user': 100,
                'parameters': {'cache_hit_ratio': 0.8},
                'expected_metrics': {
                    'avg_response_time': 0.1,
                    'throughput': 500
                }
            }
        ]
    
    async def run_benchmark_suite(self, scenarios: Optional[List[str]] = None) -> Dict[str, PerformanceBenchmarkResult]:
        """运行基准测试套件"""
        logger.info("开始性能基准测试套件")
        
        results = {}
        
        try:
            # 确定要运行的场景
            available_scenarios = self.benchmark_config['scenarios']
            
            if scenarios:
                # 过滤指定的场景
                scenarios_to_run = [
                    s for s in available_scenarios 
                    if s['name'] in scenarios
                ]
            else:
                scenarios_to_run = available_scenarios
            
            if not scenarios_to_run:
                raise ValueError("没有找到可运行的测试场景")
            
            logger.info(f"将运行 {len(scenarios_to_run)} 个测试场景")
            
            # 启动资源监控
            if self.benchmark_config['monitor_resources']:
                await self._start_resource_monitoring()
            
            # 依次运行每个场景
            for i, scenario_config in enumerate(scenarios_to_run):
                logger.info(f"运行场景 {i+1}/{len(scenarios_to_run)}: {scenario_config['name']}")
                
                scenario = BenchmarkScenario(**scenario_config)
                result = await self._run_single_scenario(scenario)
                results[scenario.name] = result
                
                # 场景间休息
                if i < len(scenarios_to_run) - 1:
                    logger.info("场景间休息...")
                    await asyncio.sleep(self.benchmark_config['cooldown_duration'])
            
            # 停止资源监控
            if self.benchmark_config['monitor_resources']:
                await self._stop_resource_monitoring()
            
            # 保存结果
            if self.benchmark_config['save_results']:
                await self._save_suite_results(results)
            
            logger.info(f"基准测试套件完成，运行了 {len(results)} 个场景")
            
        except Exception as e:
            logger.error(f"基准测试套件失败: {e}")
            if self.benchmark_config['monitor_resources']:
                await self._stop_resource_monitoring()
            raise
        
        return results
    
    async def _run_single_scenario(self, scenario: BenchmarkScenario) -> PerformanceBenchmarkResult:
        """运行单个测试场景"""
        logger.info(f"开始场景: {scenario.name}")
        
        result = PerformanceBenchmarkResult(scenario.name)
        
        try:
            # 预热阶段
            logger.info("预热阶段...")
            await self._warmup_phase(scenario)
            
            # 主测试阶段
            logger.info("主测试阶段...")
            result.start_time = datetime.now()
            
            # 启动并发任务
            tasks = []
            for user_id in range(scenario.concurrent_users):
                task = asyncio.create_task(
                    self._run_user_operations(scenario, user_id, result)
                )
                tasks.append(task)
            
            # 等待所有任务完成或超时
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=scenario.duration_seconds + 30  # 额外30秒超时缓冲
                )
            except asyncio.TimeoutError:
                logger.warning(f"场景 {scenario.name} 执行超时")
                for task in tasks:
                    if not task.done():
                        task.cancel()
            
            # 完成测试
            result.finalize()
            
            logger.info(f"场景 {scenario.name} 完成，性能分数: {result.performance_score:.1f}")
            
        except Exception as e:
            logger.error(f"场景 {scenario.name} 执行失败: {e}")
            result.status = "failed"
            result.error_details.append(str(e))
            result.finalize()
        
        return result
    
    async def _warmup_phase(self, scenario: BenchmarkScenario):
        """预热阶段"""
        warmup_duration = self.benchmark_config['warmup_duration']
        
        # 运行少量操作进行预热
        warmup_users = min(scenario.concurrent_users, 3)
        warmup_ops = min(scenario.operations_per_user, 10)
        
        tasks = []
        for user_id in range(warmup_users):
            task = asyncio.create_task(
                self._run_warmup_operations(scenario, user_id, warmup_ops)
            )
            tasks.append(task)
        
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=warmup_duration
            )
        except asyncio.TimeoutError:
            logger.warning("预热阶段超时")
    
    async def _run_warmup_operations(self, scenario: BenchmarkScenario, 
                                   user_id: int, operations: int):
        """运行预热操作"""
        try:
            for _ in range(operations):
                await self._execute_operation(scenario, user_id, warmup=True)
                await asyncio.sleep(0.1)  # 预热期间慢一点
        except Exception as e:
            logger.debug(f"预热操作失败: {e}")
    
    async def _run_user_operations(self, scenario: BenchmarkScenario, 
                                 user_id: int, result: PerformanceBenchmarkResult):
        """运行用户操作"""
        operations_completed = 0
        start_time = time.time()
        
        try:
            while (operations_completed < scenario.operations_per_user and
                   time.time() - start_time < scenario.duration_seconds):
                
                try:
                    operation_start = time.time()
                    await self._execute_operation(scenario, user_id)
                    operation_end = time.time()
                    
                    response_time = operation_end - operation_start
                    result.response_times.append(response_time)
                    result.success_count += 1
                    
                except Exception as e:
                    result.failure_count += 1
                    error_msg = f"User {user_id} operation {operations_completed}: {str(e)}"
                    result.error_details.append(error_msg)
                    logger.debug(error_msg)
                
                operations_completed += 1
                
                # 简单的速率控制
                await asyncio.sleep(0.01)
                
        except Exception as e:
            logger.error(f"用户 {user_id} 操作失败: {e}")
    
    async def _execute_operation(self, scenario: BenchmarkScenario, 
                               user_id: int, warmup: bool = False):
        """执行具体操作"""
        category = scenario.category
        parameters = scenario.parameters
        
        if category == 'data_processing':
            await self._execute_data_processing_operation(parameters, user_id)
        elif category == 'trading':
            await self._execute_trading_operation(parameters, user_id)
        elif category == 'database':
            await self._execute_database_operation(parameters, user_id)
        elif category == 'cache':
            await self._execute_cache_operation(parameters, user_id)
        else:
            await self._execute_generic_operation(parameters, user_id)
    
    async def _execute_data_processing_operation(self, parameters: Dict[str, Any], user_id: int):
        """执行数据处理操作"""
        try:
            data_size = parameters.get('data_size', 'small')
            
            if data_size == 'small':
                # 模拟小数据量处理
                await asyncio.sleep(0.1)  # 模拟100ms处理时间
                data = list(range(100))
                result = sum(x * x for x in data)
            elif data_size == 'large':
                # 模拟大数据量处理
                await asyncio.sleep(0.3)  # 模拟300ms处理时间
                data = list(range(1000))
                result = sum(x * x for x in data)
            
            # 模拟调用数据处理基准测试
            await self.benchmark_runner.run_data_processing_benchmark()
            
        except Exception as e:
            raise Exception(f"数据处理操作失败: {e}")
    
    async def _execute_trading_operation(self, parameters: Dict[str, Any], user_id: int):
        """执行交易操作"""
        try:
            order_type = parameters.get('order_type', 'market')
            
            # 模拟订单处理
            if order_type == 'market':
                await asyncio.sleep(0.05)  # 市价单较快
            else:
                await asyncio.sleep(0.1)   # 限价单较慢
            
            # 模拟调用交易基准测试
            await self.benchmark_runner.run_trading_benchmark()
            
        except Exception as e:
            raise Exception(f"交易操作失败: {e}")
    
    async def _execute_database_operation(self, parameters: Dict[str, Any], user_id: int):
        """执行数据库操作"""
        try:
            operation_mix = parameters.get('operation_mix', 'crud')
            
            # 模拟数据库操作
            if operation_mix == 'crud':
                # 随机选择CRUD操作
                import random
                operation = random.choice(['create', 'read', 'update', 'delete'])
                
                if operation == 'read':
                    await asyncio.sleep(0.02)  # 读取较快
                else:
                    await asyncio.sleep(0.05)  # 写入较慢
            
            # 模拟调用数据库基准测试
            await self.benchmark_runner.run_database_benchmark()
            
        except Exception as e:
            raise Exception(f"数据库操作失败: {e}")
    
    async def _execute_cache_operation(self, parameters: Dict[str, Any], user_id: int):
        """执行缓存操作"""
        try:
            cache_hit_ratio = parameters.get('cache_hit_ratio', 0.8)
            
            # 模拟缓存操作
            import random
            if random.random() < cache_hit_ratio:
                await asyncio.sleep(0.001)  # 缓存命中很快
            else:
                await asyncio.sleep(0.1)    # 缓存未命中需要查数据库
            
            # 模拟调用缓存基准测试
            await self.benchmark_runner.run_cache_benchmark()
            
        except Exception as e:
            raise Exception(f"缓存操作失败: {e}")
    
    async def _execute_generic_operation(self, parameters: Dict[str, Any], user_id: int):
        """执行通用操作"""
        # 默认操作
        await asyncio.sleep(0.05)
    
    async def _start_resource_monitoring(self):
        """启动资源监控"""
        try:
            self.monitoring_active = True
            await self.performance_analyzer.start_monitoring()
            
            # 启动资源监控任务
            self.resource_monitor_task = asyncio.create_task(
                self._monitor_resources()
            )
            
            logger.info("资源监控已启动")
            
        except Exception as e:
            logger.error(f"启动资源监控失败: {e}")
    
    async def _stop_resource_monitoring(self):
        """停止资源监控"""
        try:
            self.monitoring_active = False
            
            if self.resource_monitor_task:
                self.resource_monitor_task.cancel()
                try:
                    await self.resource_monitor_task
                except asyncio.CancelledError:
                    pass
            
            await self.performance_analyzer.stop_monitoring()
            
            logger.info("资源监控已停止")
            
        except Exception as e:
            logger.error(f"停止资源监控失败: {e}")
    
    async def _monitor_resources(self):
        """监控资源使用"""
        while self.monitoring_active:
            try:
                metrics = await self.performance_analyzer.get_current_metrics()
                
                # 记录资源使用情况（这里可以存储到结果中）
                logger.debug(f"资源使用: CPU={metrics.get('cpu_usage', 0):.1f}%, "
                           f"Memory={metrics.get('memory_usage', 0):.1f}%")
                
                await asyncio.sleep(1)  # 每秒监控一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"资源监控异常: {e}")
                await asyncio.sleep(5)
    
    async def _save_suite_results(self, results: Dict[str, PerformanceBenchmarkResult]):
        """保存套件结果"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"benchmark_suite_{timestamp}.json"
            filepath = os.path.join(self.benchmark_config['results_directory'], filename)
            
            # 转换结果为可序列化格式
            results_dict = {
                'timestamp': datetime.now().isoformat(),
                'suite_summary': self._generate_suite_summary(results),
                'scenarios': {name: result.to_dict() for name, result in results.items()}
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(results_dict, f, indent=2, ensure_ascii=False)
            
            # 保存最新结果
            latest_filepath = os.path.join(
                self.benchmark_config['results_directory'], 
                "latest_benchmark_suite.json"
            )
            with open(latest_filepath, 'w', encoding='utf-8') as f:
                json.dump(results_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(f"基准测试结果已保存到: {filepath}")
            
        except Exception as e:
            logger.error(f"保存基准测试结果失败: {e}")
    
    def _generate_suite_summary(self, results: Dict[str, PerformanceBenchmarkResult]) -> Dict[str, Any]:
        """生成套件摘要"""
        if not results:
            return {}
        
        total_scenarios = len(results)
        successful_scenarios = sum(1 for r in results.values() if r.status == "completed")
        failed_scenarios = total_scenarios - successful_scenarios
        
        # 计算平均性能分数
        completed_results = [r for r in results.values() if r.status == "completed"]
        avg_performance_score = 0
        if completed_results:
            avg_performance_score = statistics.mean(r.performance_score for r in completed_results)
        
        # 收集所有瓶颈和建议
        all_bottlenecks = []
        all_recommendations = []
        for result in completed_results:
            all_bottlenecks.extend(result.bottlenecks)
            all_recommendations.extend(result.recommendations)
        
        # 去重并计数
        bottleneck_counts = {}
        for bottleneck in all_bottlenecks:
            bottleneck_counts[bottleneck] = bottleneck_counts.get(bottleneck, 0) + 1
        
        recommendation_counts = {}
        for recommendation in all_recommendations:
            recommendation_counts[recommendation] = recommendation_counts.get(recommendation, 0) + 1
        
        return {
            'total_scenarios': total_scenarios,
            'successful_scenarios': successful_scenarios,
            'failed_scenarios': failed_scenarios,
            'success_rate': successful_scenarios / total_scenarios,
            'avg_performance_score': avg_performance_score,
            'common_bottlenecks': sorted(bottleneck_counts.items(), key=lambda x: x[1], reverse=True)[:5],
            'common_recommendations': sorted(recommendation_counts.items(), key=lambda x: x[1], reverse=True)[:5],
            'overall_status': self._determine_overall_status(avg_performance_score, successful_scenarios, total_scenarios)
        }
    
    def _determine_overall_status(self, avg_score: float, successful: int, total: int) -> str:
        """确定总体状态"""
        success_rate = successful / total
        
        if success_rate < 0.8:
            return "critical"
        elif success_rate < 0.9 or avg_score < 60:
            return "poor"
        elif avg_score < 80:
            return "acceptable"
        elif avg_score < 90:
            return "good"
        else:
            return "excellent"
    
    async def run_custom_scenario(self, scenario_config: Dict[str, Any]) -> PerformanceBenchmarkResult:
        """运行自定义场景"""
        logger.info(f"运行自定义场景: {scenario_config.get('name', 'unnamed')}")
        
        try:
            scenario = BenchmarkScenario(**scenario_config)
            
            if self.benchmark_config['monitor_resources']:
                await self._start_resource_monitoring()
            
            result = await self._run_single_scenario(scenario)
            
            if self.benchmark_config['monitor_resources']:
                await self._stop_resource_monitoring()
            
            return result
            
        except Exception as e:
            logger.error(f"自定义场景执行失败: {e}")
            if self.benchmark_config['monitor_resources']:
                await self._stop_resource_monitoring()
            raise
    
    def generate_performance_report(self, results: Dict[str, PerformanceBenchmarkResult]) -> str:
        """生成性能报告"""
        if not results:
            return "没有可用的基准测试结果"
        
        report_lines = [
            "=" * 80,
            "性能基准测试报告",
            "=" * 80,
            f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"测试场景数: {len(results)}",
            ""
        ]
        
        # 总体摘要
        summary = self._generate_suite_summary(results)
        report_lines.extend([
            "总体摘要:",
            "-" * 40,
            f"成功场景: {summary.get('successful_scenarios', 0)}/{summary.get('total_scenarios', 0)}",
            f"平均性能分数: {summary.get('avg_performance_score', 0):.1f}",
            f"总体状态: {summary.get('overall_status', 'unknown').upper()}",
            ""
        ])
        
        # 各场景详情
        report_lines.extend([
            "场景详情:",
            "-" * 40
        ])
        
        for name, result in results.items():
            status_icon = "✓" if result.status == "completed" else "✗"
            score_color = "🟢" if result.performance_score >= 80 else "🟡" if result.performance_score >= 60 else "🔴"
            
            report_lines.extend([
                f"{status_icon} {name}",
                f"  性能分数: {score_color} {result.performance_score:.1f}/100",
                f"  吞吐量: {result.throughput:.1f} ops/sec",
                f"  平均响应时间: {result.avg_response_time:.3f}s",
                f"  P95响应时间: {result.p95_response_time:.3f}s",
                f"  成功率: {getattr(result, 'success_rate', 0):.2%}",
                ""
            ])
            
            if result.bottlenecks:
                report_lines.extend([
                    "  瓶颈:",
                    *[f"    • {bottleneck}" for bottleneck in result.bottlenecks[:3]],
                    ""
                ])
        
        # 优化建议
        common_recommendations = summary.get('common_recommendations', [])
        if common_recommendations:
            report_lines.extend([
                "优化建议:",
                "-" * 40
            ])
            for recommendation, count in common_recommendations:
                report_lines.append(f"• {recommendation} (出现 {count} 次)")
            report_lines.append("")
        
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)


async def main():
    """主函数 - 命令行执行"""
    import argparse
    
    parser = argparse.ArgumentParser(description='性能基准测试运行器')
    parser.add_argument('--config', '-c', default='config.json', help='配置文件路径')
    parser.add_argument('--scenarios', '-s', nargs='+', help='指定要运行的场景')
    parser.add_argument('--output', '-o', help='结果输出文件路径')
    parser.add_argument('--report', '-r', action='store_true', help='生成报告')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 加载配置
        if os.path.exists(args.config):
            with open(args.config, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            logger.warning(f"配置文件 {args.config} 不存在，使用默认配置")
            config = {}
        
        # 创建运行器
        runner = PerformanceBenchmarkRunner(config)
        
        # 运行基准测试
        results = await runner.run_benchmark_suite(args.scenarios)
        
        # 生成报告
        if args.report:
            report = runner.generate_performance_report(results)
            print(report)
        else:
            # 简单摘要
            summary = runner._generate_suite_summary(results)
            print(f"基准测试完成:")
            print(f"  成功场景: {summary.get('successful_scenarios', 0)}/{summary.get('total_scenarios', 0)}")
            print(f"  平均性能分数: {summary.get('avg_performance_score', 0):.1f}")
            print(f"  总体状态: {summary.get('overall_status', 'unknown').upper()}")
        
        # 保存结果到指定文件
        if args.output:
            results_dict = {
                'timestamp': datetime.now().isoformat(),
                'scenarios': {name: result.to_dict() for name, result in results.items()}
            }
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results_dict, f, indent=2, ensure_ascii=False)
            print(f"\n详细结果已保存到: {args.output}")
        
        # 根据测试结果设置退出码
        summary = runner._generate_suite_summary(results)
        if summary.get('overall_status') in ['critical', 'poor']:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"执行失败: {e}")
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())