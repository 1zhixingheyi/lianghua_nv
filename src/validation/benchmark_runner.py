"""
基准测试运行器

负责运行各种性能基准测试，评估系统性能
"""

import asyncio
import time
import logging
import statistics
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
import concurrent.futures
import traceback

logger = logging.getLogger(__name__)


class BenchmarkResult:
    """基准测试结果"""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.start_time = None
        self.end_time = None
        self.duration = 0.0
        self.iterations = 0
        self.throughput = 0.0  # 每秒操作数
        self.latencies = []    # 延迟列表
        self.success_count = 0
        self.error_count = 0
        self.errors = []
        self.metrics = {}
        self.status = 'pending'  # pending, running, completed, failed
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.success_count + self.error_count
        return (self.success_count / total * 100) if total > 0 else 0.0
    
    @property
    def avg_latency(self) -> float:
        """平均延迟"""
        return statistics.mean(self.latencies) if self.latencies else 0.0
    
    @property
    def p95_latency(self) -> float:
        """95百分位延迟"""
        return statistics.quantiles(self.latencies, n=20)[18] if len(self.latencies) >= 20 else 0.0
    
    @property
    def p99_latency(self) -> float:
        """99百分位延迟"""
        return statistics.quantiles(self.latencies, n=100)[98] if len(self.latencies) >= 100 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'test_name': self.test_name,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': self.duration,
            'iterations': self.iterations,
            'throughput': self.throughput,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'success_rate': self.success_rate,
            'avg_latency': self.avg_latency,
            'p95_latency': self.p95_latency,
            'p99_latency': self.p99_latency,
            'status': self.status,
            'metrics': self.metrics,
            'error_summary': self._summarize_errors()
        }
    
    def _summarize_errors(self) -> Dict[str, int]:
        """汇总错误信息"""
        error_summary = {}
        for error in self.errors:
            error_type = type(error).__name__
            error_summary[error_type] = error_summary.get(error_type, 0) + 1
        return error_summary


class BenchmarkRunner:
    """基准测试运行器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.results = {}
        
        # 基准测试配置
        self.benchmark_config = {
            'data_fetch': {
                'enabled': True,
                'iterations': 100,
                'concurrency': 10,
                'timeout': 30.0
            },
            'strategy_execution': {
                'enabled': True,
                'iterations': 50,
                'concurrency': 5,
                'timeout': 60.0
            },
            'database_operations': {
                'enabled': True,
                'iterations': 200,
                'concurrency': 20,
                'timeout': 45.0
            },
            'risk_calculations': {
                'enabled': True,
                'iterations': 100,
                'concurrency': 10,
                'timeout': 30.0
            },
            'web_api': {
                'enabled': True,
                'iterations': 200,
                'concurrency': 20,
                'timeout': 60.0
            },
            'memory_usage': {
                'enabled': True,
                'duration': 300,  # 5分钟
                'interval': 1.0
            }
        }
        
        # 更新配置
        if 'benchmarks' in config:
            self.benchmark_config.update(config['benchmarks'])
    
    async def run_all_benchmarks(self) -> Dict[str, BenchmarkResult]:
        """运行所有基准测试"""
        logger.info("开始运行基准测试套件")
        
        # 运行各项基准测试
        benchmark_tasks = []
        
        if self.benchmark_config['data_fetch']['enabled']:
            benchmark_tasks.append(self.run_data_fetch_benchmark())
        
        if self.benchmark_config['strategy_execution']['enabled']:
            benchmark_tasks.append(self.run_strategy_execution_benchmark())
        
        if self.benchmark_config['database_operations']['enabled']:
            benchmark_tasks.append(self.run_database_benchmark())
        
        if self.benchmark_config['risk_calculations']['enabled']:
            benchmark_tasks.append(self.run_risk_calculation_benchmark())
        
        if self.benchmark_config['web_api']['enabled']:
            benchmark_tasks.append(self.run_web_api_benchmark())
        
        if self.benchmark_config['memory_usage']['enabled']:
            benchmark_tasks.append(self.run_memory_benchmark())
        
        # 并发执行基准测试
        try:
            results = await asyncio.gather(*benchmark_tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, BenchmarkResult):
                    self.results[result.test_name] = result
                elif isinstance(result, Exception):
                    logger.error(f"基准测试异常: {result}")
                    error_result = BenchmarkResult('error_test')
                    error_result.status = 'failed'
                    error_result.errors.append(result)
                    self.results['error'] = error_result
        
        except Exception as e:
            logger.error(f"基准测试执行失败: {e}")
            traceback.print_exc()
        
        logger.info(f"基准测试套件完成，执行了{len(self.results)}项测试")
        return self.results
    
    async def run_data_fetch_benchmark(self) -> BenchmarkResult:
        """数据获取基准测试"""
        result = BenchmarkResult('data_fetch')
        result.status = 'running'
        result.start_time = datetime.now()
        
        config = self.benchmark_config['data_fetch']
        
        try:
            # 准备测试数据
            test_symbols = ['000001.SZ', '000002.SZ', '600000.SH', '600036.SH', '000858.SZ']
            
            # 创建测试任务
            async def fetch_data_task():
                task_start = time.time()
                try:
                    # 模拟数据获取
                    await asyncio.sleep(0.1)  # 模拟网络延迟
                    symbol = test_symbols[result.iterations % len(test_symbols)]
                    # 在实际项目中，这里应该调用真实的数据获取方法
                    
                    task_end = time.time()
                    latency = task_end - task_start
                    result.latencies.append(latency)
                    result.success_count += 1
                    
                except Exception as e:
                    result.error_count += 1
                    result.errors.append(e)
                finally:
                    result.iterations += 1
            
            # 并发执行测试
            semaphore = asyncio.Semaphore(config['concurrency'])
            
            async def limited_task():
                async with semaphore:
                    await fetch_data_task()
            
            tasks = [limited_task() for _ in range(config['iterations'])]
            
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=config['timeout']
            )
            
            result.status = 'completed'
            
        except asyncio.TimeoutError:
            result.status = 'failed'
            result.errors.append(Exception("数据获取基准测试超时"))
            logger.warning("数据获取基准测试超时")
        
        except Exception as e:
            result.status = 'failed'
            result.errors.append(e)
            logger.error(f"数据获取基准测试失败: {e}")
        
        result.end_time = datetime.now()
        result.duration = (result.end_time - result.start_time).total_seconds()
        
        if result.duration > 0:
            result.throughput = result.success_count / result.duration
        
        logger.info(f"数据获取基准测试完成: {result.success_count}/{result.iterations} 成功")
        return result
    
    async def run_strategy_execution_benchmark(self) -> BenchmarkResult:
        """策略执行基准测试"""
        result = BenchmarkResult('strategy_execution')
        result.status = 'running'
        result.start_time = datetime.now()
        
        config = self.benchmark_config['strategy_execution']
        
        try:
            # 创建策略执行任务
            async def strategy_task():
                task_start = time.time()
                try:
                    # 模拟策略计算
                    await asyncio.sleep(0.2)  # 模拟策略计算时间
                    
                    # 在实际项目中，这里应该调用真实的策略执行
                    
                    task_end = time.time()
                    latency = task_end - task_start
                    result.latencies.append(latency)
                    result.success_count += 1
                    
                except Exception as e:
                    result.error_count += 1
                    result.errors.append(e)
                finally:
                    result.iterations += 1
            
            # 并发执行测试
            semaphore = asyncio.Semaphore(config['concurrency'])
            
            async def limited_task():
                async with semaphore:
                    await strategy_task()
            
            tasks = [limited_task() for _ in range(config['iterations'])]
            
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=config['timeout']
            )
            
            result.status = 'completed'
            
        except asyncio.TimeoutError:
            result.status = 'failed'
            result.errors.append(Exception("策略执行基准测试超时"))
            logger.warning("策略执行基准测试超时")
        
        except Exception as e:
            result.status = 'failed'
            result.errors.append(e)
            logger.error(f"策略执行基准测试失败: {e}")
        
        result.end_time = datetime.now()
        result.duration = (result.end_time - result.start_time).total_seconds()
        
        if result.duration > 0:
            result.throughput = result.success_count / result.duration
        
        logger.info(f"策略执行基准测试完成: {result.success_count}/{result.iterations} 成功")
        return result
    
    async def run_database_benchmark(self) -> BenchmarkResult:
        """数据库操作基准测试"""
        result = BenchmarkResult('database_operations')
        result.status = 'running'
        result.start_time = datetime.now()
        
        config = self.benchmark_config['database_operations']
        
        try:
            # 创建数据库操作任务
            async def db_task():
                task_start = time.time()
                try:
                    # 模拟数据库操作
                    await asyncio.sleep(0.05)  # 模拟数据库查询时间
                    
                    # 在实际项目中，这里应该执行真实的数据库操作
                    
                    task_end = time.time()
                    latency = task_end - task_start
                    result.latencies.append(latency)
                    result.success_count += 1
                    
                except Exception as e:
                    result.error_count += 1
                    result.errors.append(e)
                finally:
                    result.iterations += 1
            
            # 并发执行测试
            semaphore = asyncio.Semaphore(config['concurrency'])
            
            async def limited_task():
                async with semaphore:
                    await db_task()
            
            tasks = [limited_task() for _ in range(config['iterations'])]
            
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=config['timeout']
            )
            
            result.status = 'completed'
            
        except asyncio.TimeoutError:
            result.status = 'failed'
            result.errors.append(Exception("数据库基准测试超时"))
            logger.warning("数据库基准测试超时")
        
        except Exception as e:
            result.status = 'failed'
            result.errors.append(e)
            logger.error(f"数据库基准测试失败: {e}")
        
        result.end_time = datetime.now()
        result.duration = (result.end_time - result.start_time).total_seconds()
        
        if result.duration > 0:
            result.throughput = result.success_count / result.duration
        
        logger.info(f"数据库基准测试完成: {result.success_count}/{result.iterations} 成功")
        return result
    
    async def run_risk_calculation_benchmark(self) -> BenchmarkResult:
        """风险计算基准测试"""
        result = BenchmarkResult('risk_calculations')
        result.status = 'running'
        result.start_time = datetime.now()
        
        config = self.benchmark_config['risk_calculations']
        
        try:
            # 创建风险计算任务
            async def risk_task():
                task_start = time.time()
                try:
                    # 模拟风险计算
                    await asyncio.sleep(0.1)  # 模拟风险计算时间
                    
                    # 在实际项目中，这里应该调用真实的风险计算
                    
                    task_end = time.time()
                    latency = task_end - task_start
                    result.latencies.append(latency)
                    result.success_count += 1
                    
                except Exception as e:
                    result.error_count += 1
                    result.errors.append(e)
                finally:
                    result.iterations += 1
            
            # 并发执行测试
            semaphore = asyncio.Semaphore(config['concurrency'])
            
            async def limited_task():
                async with semaphore:
                    await risk_task()
            
            tasks = [limited_task() for _ in range(config['iterations'])]
            
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=config['timeout']
            )
            
            result.status = 'completed'
            
        except asyncio.TimeoutError:
            result.status = 'failed'
            result.errors.append(Exception("风险计算基准测试超时"))
            logger.warning("风险计算基准测试超时")
        
        except Exception as e:
            result.status = 'failed'
            result.errors.append(e)
            logger.error(f"风险计算基准测试失败: {e}")
        
        result.end_time = datetime.now()
        result.duration = (result.end_time - result.start_time).total_seconds()
        
        if result.duration > 0:
            result.throughput = result.success_count / result.duration
        
        logger.info(f"风险计算基准测试完成: {result.success_count}/{result.iterations} 成功")
        return result
    
    async def run_web_api_benchmark(self) -> BenchmarkResult:
        """Web API基准测试"""
        result = BenchmarkResult('web_api')
        result.status = 'running'
        result.start_time = datetime.now()
        
        config = self.benchmark_config['web_api']
        
        try:
            import aiohttp
            
            # API端点列表
            api_endpoints = [
                'http://localhost:5000/api/health',
                'http://localhost:5000/api/stocks',
                'http://localhost:5000/api/strategies'
            ]
            
            # 创建API请求任务
            async def api_task():
                task_start = time.time()
                try:
                    endpoint = api_endpoints[result.iterations % len(api_endpoints)]
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(endpoint, timeout=5.0) as response:
                            await response.text()
                    
                    task_end = time.time()
                    latency = task_end - task_start
                    result.latencies.append(latency)
                    result.success_count += 1
                    
                except Exception as e:
                    result.error_count += 1
                    result.errors.append(e)
                finally:
                    result.iterations += 1
            
            # 并发执行测试
            semaphore = asyncio.Semaphore(config['concurrency'])
            
            async def limited_task():
                async with semaphore:
                    await api_task()
            
            tasks = [limited_task() for _ in range(config['iterations'])]
            
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=config['timeout']
            )
            
            result.status = 'completed'
            
        except asyncio.TimeoutError:
            result.status = 'failed'
            result.errors.append(Exception("Web API基准测试超时"))
            logger.warning("Web API基准测试超时")
        
        except Exception as e:
            result.status = 'failed'
            result.errors.append(e)
            logger.error(f"Web API基准测试失败: {e}")
        
        result.end_time = datetime.now()
        result.duration = (result.end_time - result.start_time).total_seconds()
        
        if result.duration > 0:
            result.throughput = result.success_count / result.duration
        
        logger.info(f"Web API基准测试完成: {result.success_count}/{result.iterations} 成功")
        return result
    
    async def run_memory_benchmark(self) -> BenchmarkResult:
        """内存使用基准测试"""
        result = BenchmarkResult('memory_usage')
        result.status = 'running'
        result.start_time = datetime.now()
        
        config = self.benchmark_config['memory_usage']
        
        try:
            import psutil
            
            process = psutil.Process()
            initial_memory = process.memory_info().rss
            memory_samples = []
            
            duration = config['duration']
            interval = config['interval']
            samples = int(duration / interval)
            
            for i in range(samples):
                try:
                    # 记录内存使用
                    memory_info = process.memory_info()
                    memory_mb = memory_info.rss / (1024 * 1024)
                    memory_samples.append(memory_mb)
                    
                    result.success_count += 1
                    
                    # 模拟一些内存操作
                    temp_data = list(range(1000))  # 创建临时数据
                    del temp_data  # 删除临时数据
                    
                except Exception as e:
                    result.error_count += 1
                    result.errors.append(e)
                
                result.iterations += 1
                await asyncio.sleep(interval)
            
            # 计算内存统计
            if memory_samples:
                result.metrics['initial_memory_mb'] = initial_memory / (1024 * 1024)
                result.metrics['final_memory_mb'] = memory_samples[-1]
                result.metrics['peak_memory_mb'] = max(memory_samples)
                result.metrics['avg_memory_mb'] = statistics.mean(memory_samples)
                result.metrics['memory_growth_mb'] = memory_samples[-1] - memory_samples[0]
                result.metrics['memory_samples'] = len(memory_samples)
            
            result.status = 'completed'
            
        except Exception as e:
            result.status = 'failed'
            result.errors.append(e)
            logger.error(f"内存基准测试失败: {e}")
        
        result.end_time = datetime.now()
        result.duration = (result.end_time - result.start_time).total_seconds()
        
        logger.info(f"内存基准测试完成: {result.iterations} 个样本")
        return result
    
    def generate_benchmark_report(self) -> Dict[str, Any]:
        """生成基准测试报告"""
        report = {
            'summary': {
                'total_tests': len(self.results),
                'completed_tests': 0,
                'failed_tests': 0,
                'total_iterations': 0,
                'total_duration': 0.0,
                'overall_throughput': 0.0
            },
            'tests': {},
            'performance_analysis': {},
            'recommendations': [],
            'timestamp': datetime.now().isoformat()
        }
        
        # 汇总测试结果
        for test_name, result in self.results.items():
            report['tests'][test_name] = result.to_dict()
            
            if result.status == 'completed':
                report['summary']['completed_tests'] += 1
            elif result.status == 'failed':
                report['summary']['failed_tests'] += 1
            
            report['summary']['total_iterations'] += result.iterations
            report['summary']['total_duration'] += result.duration
        
        # 计算整体吞吐量
        if report['summary']['total_duration'] > 0:
            report['summary']['overall_throughput'] = (
                report['summary']['total_iterations'] / report['summary']['total_duration']
            )
        
        # 性能分析
        report['performance_analysis'] = self._analyze_performance()
        
        # 生成建议
        report['recommendations'] = self._generate_benchmark_recommendations()
        
        return report
    
    def _analyze_performance(self) -> Dict[str, Any]:
        """分析性能数据"""
        analysis = {
            'fastest_test': None,
            'slowest_test': None,
            'highest_throughput': None,
            'lowest_throughput': None,
            'latency_analysis': {}
        }
        
        completed_results = {
            name: result for name, result in self.results.items() 
            if result.status == 'completed'
        }
        
        if not completed_results:
            return analysis
        
        # 找出最快和最慢的测试
        avg_latencies = {
            name: result.avg_latency 
            for name, result in completed_results.items() 
            if result.latencies
        }
        
        if avg_latencies:
            analysis['fastest_test'] = min(avg_latencies, key=avg_latencies.get)
            analysis['slowest_test'] = max(avg_latencies, key=avg_latencies.get)
        
        # 找出吞吐量最高和最低的测试
        throughputs = {
            name: result.throughput 
            for name, result in completed_results.items() 
            if result.throughput > 0
        }
        
        if throughputs:
            analysis['highest_throughput'] = max(throughputs, key=throughputs.get)
            analysis['lowest_throughput'] = min(throughputs, key=throughputs.get)
        
        # 延迟分析
        for name, result in completed_results.items():
            if result.latencies:
                analysis['latency_analysis'][name] = {
                    'avg': result.avg_latency,
                    'p95': result.p95_latency,
                    'p99': result.p99_latency,
                    'min': min(result.latencies),
                    'max': max(result.latencies)
                }
        
        return analysis
    
    def _generate_benchmark_recommendations(self) -> List[str]:
        """生成基准测试建议"""
        recommendations = []
        
        for test_name, result in self.results.items():
            if result.status == 'failed':
                recommendations.append(f"修复{test_name}测试失败问题")
            elif result.status == 'completed':
                if result.success_rate < 95:
                    recommendations.append(f"提高{test_name}测试成功率 (当前: {result.success_rate:.1f}%)")
                
                if result.avg_latency > 1.0:
                    recommendations.append(f"优化{test_name}响应时间 (当前: {result.avg_latency:.2f}秒)")
                
                if result.throughput < 10:
                    recommendations.append(f"提高{test_name}吞吐量 (当前: {result.throughput:.1f} ops/sec)")
        
        # 通用建议
        if not recommendations:
            recommendations.append("基准测试结果良好，建议定期重新评估性能")
        
        return recommendations