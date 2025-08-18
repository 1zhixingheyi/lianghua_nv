"""
压力测试运行器

执行系统压力测试并分析系统在高负载下的表现
"""

import asyncio
import logging
import time
import threading
import concurrent.futures
import psutil
import requests
import sqlite3
from typing import Dict, Any, List, Optional, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import random
import statistics
from collections import defaultdict, deque
import multiprocessing

logger = logging.getLogger(__name__)


@dataclass
class StressTestConfig:
    """压力测试配置"""
    test_name: str
    test_type: str  # cpu, memory, disk, network, database, web_api
    duration_seconds: int
    target_load: float  # 目标负载（百分比或绝对值）
    ramp_up_seconds: int = 30  # 加压时间
    ramp_down_seconds: int = 30  # 减压时间
    concurrent_workers: int = 4
    monitoring_interval: float = 1.0
    failure_threshold: float = 95.0  # 失败阈值（百分比）
    timeout_seconds: float = 30.0
    parameters: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


@dataclass
class StressTestResult:
    """压力测试结果"""
    test_name: str
    test_type: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    target_load: float
    actual_peak_load: float
    success_rate: float
    throughput: float
    avg_response_time: float
    max_response_time: float
    min_response_time: float
    error_count: int
    total_operations: int
    resource_usage: Dict[str, Any]
    performance_metrics: Dict[str, List[float]]
    warnings: List[str]
    errors: List[str]
    passed: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        data['end_time'] = self.end_time.isoformat()
        return data


class StressTestRunner:
    """压力测试运行器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 测试配置
        self.test_config = {
            'output_dir': 'stress_test_results',
            'enable_monitoring': True,
            'monitoring_interval': 1.0,
            'max_concurrent_tests': 1,
            'resource_limits': {
                'max_cpu_percent': 95.0,
                'max_memory_percent': 90.0,
                'max_disk_usage_percent': 90.0
            },
            'default_timeout': 300,
            'enable_cleanup': True,
            'save_detailed_logs': True
        }
        
        # 更新配置
        if 'stress_test' in config:
            self.test_config.update(config['stress_test'])
        
        # 创建输出目录
        self.output_dir = Path(self.test_config['output_dir'])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 测试状态
        self.running_tests = {}
        self.test_results = []
        self.is_monitoring = False
        self.monitoring_data = defaultdict(list)
        
        # 资源监控
        self.system_monitor = None
        self.monitoring_task = None
        
        # 线程池
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.test_config['max_concurrent_tests']
        )
        
        logger.info("压力测试运行器已初始化")
    
    async def run_stress_test(self, test_config: StressTestConfig) -> StressTestResult:
        """运行压力测试"""
        try:
            logger.info(f"开始压力测试: {test_config.test_name}")
            
            # 检查系统资源
            if not self._check_system_resources():
                raise RuntimeError("系统资源不足，无法运行压力测试")
            
            # 启动监控
            await self._start_monitoring(test_config.test_name)
            
            try:
                # 根据测试类型执行相应的测试
                if test_config.test_type == 'cpu':
                    result = await self._run_cpu_stress_test(test_config)
                elif test_config.test_type == 'memory':
                    result = await self._run_memory_stress_test(test_config)
                elif test_config.test_type == 'disk':
                    result = await self._run_disk_stress_test(test_config)
                elif test_config.test_type == 'web_api':
                    result = await self._run_web_api_stress_test(test_config)
                else:
                    raise ValueError(f"不支持的测试类型: {test_config.test_type}")
                
                # 分析结果
                result = self._analyze_test_result(result, test_config)
                
                # 保存结果
                await self._save_test_result(result)
                
                logger.info(f"压力测试完成: {test_config.test_name}, 通过: {result.passed}")
                
                return result
                
            finally:
                # 停止监控
                await self._stop_monitoring()
                
        except Exception as e:
            logger.error(f"压力测试失败 {test_config.test_name}: {e}")
            raise
    
    def _check_system_resources(self) -> bool:
        """检查系统资源是否足够"""
        try:
            # 检查CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > self.test_config['resource_limits']['max_cpu_percent']:
                logger.warning(f"CPU使用率过高: {cpu_percent}%")
                return False
            
            # 检查内存
            memory = psutil.virtual_memory()
            if memory.percent > self.test_config['resource_limits']['max_memory_percent']:
                logger.warning(f"内存使用率过高: {memory.percent}%")
                return False
            
            # 检查磁盘
            disk = psutil.disk_usage('/')
            if disk.percent > self.test_config['resource_limits']['max_disk_usage_percent']:
                logger.warning(f"磁盘使用率过高: {disk.percent}%")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"检查系统资源失败: {e}")
            return False
    
    async def _start_monitoring(self, test_name: str):
        """启动资源监控"""
        if not self.test_config['enable_monitoring']:
            return
        
        try:
            self.is_monitoring = True
            self.monitoring_data[test_name] = []
            
            # 启动监控任务
            self.monitoring_task = asyncio.create_task(
                self._monitoring_loop(test_name)
            )
            
        except Exception as e:
            logger.error(f"启动监控失败: {e}")
    
    async def _stop_monitoring(self):
        """停止资源监控"""
        try:
            self.is_monitoring = False
            
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
                
        except Exception as e:
            logger.error(f"停止监控失败: {e}")
    
    async def _monitoring_loop(self, test_name: str):
        """监控循环"""
        while self.is_monitoring:
            try:
                # 收集系统指标
                timestamp = datetime.now()
                
                cpu_percent = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                network = psutil.net_io_counters()
                
                monitoring_point = {
                    'timestamp': timestamp,
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'memory_used_gb': memory.used / (1024**3),
                    'disk_percent': disk.percent,
                    'network_bytes_sent': network.bytes_sent,
                    'network_bytes_recv': network.bytes_recv,
                    'load_average': psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0.0
                }
                
                self.monitoring_data[test_name].append(monitoring_point)
                
                # 等待下次监控
                await asyncio.sleep(self.test_config['monitoring_interval'])
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                await asyncio.sleep(1)
    
    async def _run_cpu_stress_test(self, config: StressTestConfig) -> StressTestResult:
        """运行CPU压力测试"""
        logger.info(f"开始CPU压力测试: 目标负载 {config.target_load}%")
        
        start_time = datetime.now()
        errors = []
        warnings = []
        
        try:
            # 创建CPU密集型任务
            def cpu_intensive_task(duration: float, target_load: float):
                """CPU密集型任务"""
                end_time = time.time() + duration
                work_time = target_load / 100.0  # 工作时间比例
                cycle_time = 0.1  # 每个周期100ms
                
                while time.time() < end_time:
                    cycle_start = time.time()
                    
                    # 执行CPU密集型操作
                    work_end = cycle_start + (cycle_time * work_time)
                    while time.time() < work_end:
                        # 计算密集型操作
                        for _ in range(1000):
                            sum(x * x for x in range(100))
                    
                    # 休息时间
                    sleep_time = cycle_time * (1 - work_time)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
            
            # 启动多个工作进程
            processes = []
            process_count = config.concurrent_workers or multiprocessing.cpu_count()
            
            # 主要测试阶段
            logger.info(f"CPU测试: {config.duration_seconds}秒，{process_count}个进程")
            for i in range(process_count):
                process = multiprocessing.Process(
                    target=cpu_intensive_task,
                    args=(config.duration_seconds, config.target_load)
                )
                process.start()
                processes.append(process)
            
            # 等待测试完成
            for process in processes:
                process.join()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 获取监控数据
            monitoring_data = self.monitoring_data.get(config.test_name, [])
            
            # 计算峰值CPU使用率
            peak_cpu = 0.0
            avg_cpu = 0.0
            if monitoring_data:
                cpu_values = [point['cpu_percent'] for point in monitoring_data]
                peak_cpu = max(cpu_values)
                avg_cpu = statistics.mean(cpu_values)
            
            # 评估测试结果
            success_rate = min(100.0, (peak_cpu / config.target_load) * 100) if config.target_load > 0 else 100.0
            passed = success_rate >= config.failure_threshold
            
            if not passed:
                warnings.append(f"CPU负载未达到目标: 目标{config.target_load}%, 实际峰值{peak_cpu:.1f}%")
            
            result = StressTestResult(
                test_name=config.test_name,
                test_type=config.test_type,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                target_load=config.target_load,
                actual_peak_load=peak_cpu,
                success_rate=success_rate,
                throughput=process_count * 1000 / duration,  # 操作/秒
                avg_response_time=0.1,  # CPU任务周期时间
                max_response_time=0.1,
                min_response_time=0.1,
                error_count=len(errors),
                total_operations=int(process_count * duration * 10),  # 估算操作数
                resource_usage={
                    'peak_cpu_percent': peak_cpu,
                    'avg_cpu_percent': avg_cpu,
                    'process_count': process_count
                },
                performance_metrics={
                    'cpu_percent': [point['cpu_percent'] for point in monitoring_data],
                    'load_average': [point['load_average'] for point in monitoring_data]
                },
                warnings=warnings,
                errors=errors,
                passed=passed
            )
            
            return result
            
        except Exception as e:
            logger.error(f"CPU压力测试异常: {e}")
            errors.append(str(e))
            
            return StressTestResult(
                test_name=config.test_name,
                test_type=config.test_type,
                start_time=start_time,
                end_time=datetime.now(),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                target_load=config.target_load,
                actual_peak_load=0.0,
                success_rate=0.0,
                throughput=0.0,
                avg_response_time=0.0,
                max_response_time=0.0,
                min_response_time=0.0,
                error_count=len(errors),
                total_operations=0,
                resource_usage={},
                performance_metrics={},
                warnings=warnings,
                errors=errors,
                passed=False
            )
    
    async def _run_memory_stress_test(self, config: StressTestConfig) -> StressTestResult:
        """运行内存压力测试"""
        logger.info(f"开始内存压力测试: 目标负载 {config.target_load}%")
        
        start_time = datetime.now()
        errors = []
        warnings = []
        allocated_memory = []
        
        try:
            # 计算目标内存使用量
            total_memory = psutil.virtual_memory().total
            target_bytes = int(total_memory * config.target_load / 100)
            
            logger.info(f"目标内存使用量: {target_bytes / (1024**3):.1f} GB")
            
            # 分块分配内存
            chunk_size = 100 * 1024 * 1024  # 100MB块
            chunks_needed = target_bytes // chunk_size
            memory_chunks = []
            
            # 渐进式分配内存
            for i in range(int(chunks_needed)):
                try:
                    # 分配内存块
                    chunk = bytearray(chunk_size)
                    # 写入数据以确保真实分配
                    for j in range(0, chunk_size, 4096):
                        chunk[j] = random.randint(0, 255)
                    
                    memory_chunks.append(chunk)
                    
                    # 记录分配进度
                    current_memory = psutil.virtual_memory()
                    allocated_memory.append({
                        'allocated_mb': len(memory_chunks) * chunk_size / (1024**2),
                        'memory_percent': current_memory.percent
                    })
                    
                    # 检查是否达到目标
                    if current_memory.percent >= config.target_load:
                        break
                    
                    await asyncio.sleep(0.1)
                    
                except MemoryError:
                    errors.append("内存分配失败: 系统内存不足")
                    break
                except Exception as e:
                    errors.append(f"内存分配异常: {e}")
                    break
            
            # 保持内存使用一段时间
            logger.info(f"保持内存使用 {config.duration_seconds} 秒")
            await asyncio.sleep(config.duration_seconds)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 获取监控数据
            monitoring_data = self.monitoring_data.get(config.test_name, [])
            
            # 计算峰值内存使用率
            peak_memory = 0.0
            avg_memory = 0.0
            if monitoring_data:
                memory_values = [point['memory_percent'] for point in monitoring_data]
                peak_memory = max(memory_values)
                avg_memory = statistics.mean(memory_values)
            
            # 清理内存
            logger.info("清理分配的内存")
            memory_chunks.clear()
            
            # 评估测试结果
            success_rate = min(100.0, (peak_memory / config.target_load) * 100) if config.target_load > 0 else 100.0
            passed = success_rate >= config.failure_threshold
            
            if not passed:
                warnings.append(f"内存负载未达到目标: 目标{config.target_load}%, 实际峰值{peak_memory:.1f}%")
            
            result = StressTestResult(
                test_name=config.test_name,
                test_type=config.test_type,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                target_load=config.target_load,
                actual_peak_load=peak_memory,
                success_rate=success_rate,
                throughput=len(allocated_memory) / duration,  # 分配操作/秒
                avg_response_time=0.1,  # 内存访问时间
                max_response_time=0.2,
                min_response_time=0.05,
                error_count=len(errors),
                total_operations=len(allocated_memory),
                resource_usage={
                    'peak_memory_percent': peak_memory,
                    'avg_memory_percent': avg_memory,
                    'allocated_chunks': len(memory_chunks),
                    'target_gb': target_bytes / (1024**3)
                },
                performance_metrics={
                    'memory_percent': [point['memory_percent'] for point in monitoring_data],
                    'memory_used_gb': [point['memory_used_gb'] for point in monitoring_data]
                },
                warnings=warnings,
                errors=errors,
                passed=passed
            )
            
            return result
            
        except Exception as e:
            logger.error(f"内存压力测试异常: {e}")
            errors.append(str(e))
            
            # 清理内存
            try:
                memory_chunks.clear()
            except:
                pass
            
            return StressTestResult(
                test_name=config.test_name,
                test_type=config.test_type,
                start_time=start_time,
                end_time=datetime.now(),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                target_load=config.target_load,
                actual_peak_load=0.0,
                success_rate=0.0,
                throughput=0.0,
                avg_response_time=0.0,
                max_response_time=0.0,
                min_response_time=0.0,
                error_count=len(errors),
                total_operations=0,
                resource_usage={},
                performance_metrics={},
                warnings=warnings,
                errors=errors,
                passed=False
            )
    
    async def _run_disk_stress_test(self, config: StressTestConfig) -> StressTestResult:
        """运行磁盘压力测试"""
        logger.info(f"开始磁盘压力测试: 目标负载 {config.target_load} MB/s")
        
        start_time = datetime.now()
        errors = []
        warnings = []
        io_operations = []
        
        try:
            # 创建测试目录
            test_dir = self.output_dir / f"disk_test_{int(time.time())}"
            test_dir.mkdir(exist_ok=True)
            
            # 测试文件配置
            file_size_mb = config.parameters.get('file_size_mb', 100)
            file_count = config.parameters.get('file_count', config.concurrent_workers)
            block_size = config.parameters.get('block_size', 4096)
            
            logger.info(f"磁盘测试参数: {file_count}个文件, 每个{file_size_mb}MB")
            
            async def disk_io_worker(worker_id: int):
                """磁盘I/O工作线程"""
                worker_ops = []
                file_path = test_dir / f"test_file_{worker_id}.dat"
                
                try:
                    # 写入测试
                    data_block = b'A' * block_size
                    blocks_per_file = (file_size_mb * 1024 * 1024) // block_size
                    
                    with open(file_path, 'wb') as f:
                        for block_num in range(blocks_per_file):
                            op_start = time.time()
                            f.write(data_block)
                            f.flush()  # 强制写入磁盘
                            op_end = time.time()
                            
                            worker_ops.append({
                                'operation': 'write',
                                'start_time': op_start,
                                'duration': op_end - op_start,
                                'bytes': block_size
                            })
                    
                    # 读取测试
                    with open(file_path, 'rb') as f:
                        while True:
                            op_start = time.time()
                            data = f.read(block_size)
                            op_end = time.time()
                            
                            if not data:
                                break
                                
                            worker_ops.append({
                                'operation': 'read',
                                'start_time': op_start,
                                'duration': op_end - op_start,
                                'bytes': len(data)
                            })
                    
                except Exception as e:
                    errors.append(f"工作线程 {worker_id} 异常: {e}")
                
                return worker_ops
            
            # 启动工作线程
            tasks = []
            for i in range(file_count):
                task = asyncio.create_task(disk_io_worker(i))
                tasks.append(task)
            
            # 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 收集所有I/O操作结果
            for result in results:
                if isinstance(result, Exception):
                    errors.append(str(result))
                elif isinstance(result, list):
                    io_operations.extend(result)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 清理测试文件
            if self.test_config['enable_cleanup']:
                try:
                    import shutil
                    shutil.rmtree(test_dir)
                    logger.info("清理磁盘测试文件完成")
                except Exception as e:
                    warnings.append(f"清理测试文件失败: {e}")
            
            # 计算性能指标
            if io_operations:
                total_bytes = sum(op['bytes'] for op in io_operations)
                total_ops = len(io_operations)
                avg_throughput = total_bytes / duration / (1024 * 1024)  # MB/s
                
                response_times = [op['duration'] for op in io_operations]
                avg_response_time = statistics.mean(response_times)
                max_response_time = max(response_times)
                min_response_time = min(response_times)
            else:
                avg_throughput = 0.0
                avg_response_time = 0.0
                max_response_time = 0.0
                min_response_time = 0.0
                total_ops = 0
            
            # 评估测试结果
            success_rate = min(100.0, (avg_throughput / config.target_load) * 100) if config.target_load > 0 else 100.0
            passed = success_rate >= config.failure_threshold and len(errors) == 0
            
            if not passed:
                if avg_throughput < config.target_load:
                    warnings.append(f"磁盘吞吐量未达到目标: 目标{config.target_load} MB/s, 实际{avg_throughput:.1f} MB/s")
                if errors:
                    warnings.append(f"测试过程中发生 {len(errors)} 个错误")
            
            result = StressTestResult(
                test_name=config.test_name,
                test_type=config.test_type,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                target_load=config.target_load,
                actual_peak_load=avg_throughput,
                success_rate=success_rate,
                throughput=avg_throughput,
                avg_response_time=avg_response_time * 1000,  # 转换为ms
                max_response_time=max_response_time * 1000,
                min_response_time=min_response_time * 1000,
                error_count=len(errors),
                total_operations=total_ops,
                resource_usage={
                    'avg_throughput_mb_s': avg_throughput,
                    'file_count': file_count,
                    'file_size_mb': file_size_mb,
                    'total_data_mb': file_count * file_size_mb
                },
                performance_metrics={
                    'response_times_ms': [t * 1000 for t in response_times] if io_operations else [],
                },
                warnings=warnings,
                errors=errors,
                passed=passed
            )
            
            return result
            
        except Exception as e:
            logger.error(f"磁盘压力测试异常: {e}")
            errors.append(str(e))
            
            return StressTestResult(
                test_name=config.test_name,
                test_type=config.test_type,
                start_time=start_time,
                end_time=datetime.now(),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                target_load=config.target_load,
                actual_peak_load=0.0,
                success_rate=0.0,
                throughput=0.0,
                avg_response_time=0.0,
                max_response_time=0.0,
                min_response_time=0.0,
                error_count=len(errors),
                total_operations=0,
                resource_usage={},
                performance_metrics={},
                warnings=warnings,
                errors=errors,
                passed=False
            )
    
    async def _run_web_api_stress_test(self, config: StressTestConfig) -> StressTestResult:
        """运行Web API压力测试"""
        logger.info(f"开始Web API压力测试: 目标负载 {config.target_load} 请求/秒")
        
        start_time = datetime.now()
        errors = []
        warnings = []
        request_results = []
        
        try:
            # API测试配置
            base_url = config.parameters.get('base_url', 'http://localhost:8000')
            endpoints = config.parameters.get('endpoints', ['/'])
            http_method = config.parameters.get('http_method', 'GET')
            request_timeout = config.parameters.get('request_timeout', 30.0)
            
            logger.info(f"API测试参数: {base_url}, 端点: {endpoints}")
            
            async def api_worker(worker_id: int):
                """API测试工作协程"""
                worker_results = []
                
                try:
                    operation_count = int(config.target_load * config.duration_seconds / config.concurrent_workers)
                    logger.info(f"工作协程 {worker_id} 将执行 {operation_count} 次请求")
                    
                    for i in range(operation_count):
                        # 随机选择端点
                        endpoint = random.choice(endpoints)
                        url = f"{base_url.rstrip('/')}{endpoint}"
                        
                        op_start = time.time()
                        
                        try:
                            # 在线程池中执行HTTP请求
                            def make_request():
                                try:
                                    if http_method.upper() == 'GET':
                                        response = requests.get(url, timeout=request_timeout)
                                    elif http_method.upper() == 'POST':
                                        response = requests.post(url, timeout=request_timeout)
                                    else:
                                        raise ValueError(f"不支持的HTTP方法: {http_method}")
                                    
                                    return {
                                        'status_code': response.status_code,
                                        'response_time': response.elapsed.total_seconds(),
                                        'content_length': len(response.content),
                                        'success': 200 <= response.status_code < 400,
                                        'error': None
                                    }
                                    
                                except requests.exceptions.Timeout:
                                    return {
                                        'status_code': 0,
                                        'response_time': request_timeout,
                                        'content_length': 0,
                                        'success': False,
                                        'error': 'timeout'
                                    }
                                except Exception as e:
                                    return {
                                        'status_code': 0,
                                        'response_time': 0,
                                        'content_length': 0,
                                        'success': False,
                                        'error': str(e)
                                    }
                            
                            loop = asyncio.get_event_loop()
                            request_result = await loop.run_in_executor(None, make_request)
                            
                            op_end = time.time()
                            total_duration = op_end - op_start
                            
                            worker_results.append({
                                'worker_id': worker_id,
                                'operation_id': i,
                                'url': url,
                                'method': http_method,
                                'start_time': op_start,
                                'total_duration': total_duration,
                                'response_time': request_result['response_time'],
                                'status_code': request_result['status_code'],
                                'content_length': request_result['content_length'],
                                'success': request_result['success'],
                                'error': request_result['error']
                            })
                            
                        except Exception as e:
                            op_end = time.time()
                            total_duration = op_end - op_start
                            
                            worker_results.append({
                                'worker_id': worker_id,
                                'operation_id': i,
                                'url': url,
                                'method': http_method,
                                'start_time': op_start,
                                'total_duration': total_duration,
                                'response_time': 0,
                                'status_code': 0,
                                'content_length': 0,
                                'success': False,
                                'error': str(e)
                            })
                        
                        # 控制请求速率
                        if config.target_load > 0 and i < operation_count - 1:
                            expected_interval = config.concurrent_workers / config.target_load
                            actual_duration = time.time() - op_start
                            if actual_duration < expected_interval:
                                await asyncio.sleep(expected_interval - actual_duration)
                    
                except Exception as e:
                    errors.append(f"API工作协程 {worker_id} 异常: {e}")
                
                return worker_results
            
            # 启动工作协程
            tasks = []
            for i in range(config.concurrent_workers):
                task = asyncio.create_task(api_worker(i))
                tasks.append(task)
            
            # 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 收集所有请求结果
            for result in results:
                if isinstance(result, Exception):
                    errors.append(str(result))
                elif isinstance(result, list):
                    request_results.extend(result)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 计算性能指标
            if request_results:
                successful_ops = [op for op in request_results if op['success']]
                failed_ops = [op for op in request_results if not op['success']]
                
                total_ops = len(request_results)
                success_count = len(successful_ops)
                success_rate = (success_count / total_ops) * 100 if total_ops > 0 else 0
                
                actual_throughput = total_ops / duration  # 请求/秒
                
                if successful_ops:
                    response_times = [op['response_time'] for op in successful_ops]
                    avg_response_time = statistics.mean(response_times)
                    max_response_time = max(response_times)
                    min_response_time = min(response_times)
                else:
                    avg_response_time = 0.0
                    max_response_time = 0.0
                    min_response_time = 0.0
                
                # 统计错误类型
                error_types = {}
                for op in failed_ops:
                    error_type = op['error'] or f"status_{op['status_code']}"
                    error_types[error_type] = error_types.get(error_type, 0) + 1
                
                if error_types:
                    warnings.extend([f"{error_type}: {count}次" for error_type, count in error_types.items()])
                
            else:
                success_rate = 0.0
                actual_throughput = 0.0
                avg_response_time = 0.0
                max_response_time = 0.0
                min_response_time = 0.0
                total_ops = 0
            
            # 评估测试结果
            throughput_rate = min(100.0, (actual_throughput / config.target_load) * 100) if config.target_load > 0 else 100.0
            passed = (throughput_rate >= config.failure_threshold and 
                     success_rate >= config.failure_threshold and 
                     len(errors) == 0)
            
            if not passed:
                if throughput_rate < config.failure_threshold:
                    warnings.append(f"API吞吐量未达到目标: 目标{config.target_load} 请求/秒, 实际{actual_throughput:.1f} 请求/秒")
                if success_rate < config.failure_threshold:
                    warnings.append(f"成功率过低: {success_rate:.1f}%")
            
            result = StressTestResult(
                test_name=config.test_name,
                test_type=config.test_type,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                target_load=config.target_load,
                actual_peak_load=actual_throughput,
                success_rate=success_rate,
                throughput=actual_throughput,
                avg_response_time=avg_response_time * 1000,  # 转换为ms
                max_response_time=max_response_time * 1000,
                min_response_time=min_response_time * 1000,
                error_count=len(errors) + len([op for op in request_results if not op['success']]),
                total_operations=total_ops,
                resource_usage={
                    'base_url': base_url,
                    'endpoints': endpoints,
                    'http_method': http_method,
                    'concurrent_workers': config.concurrent_workers,
                    'successful_requests': len([op for op in request_results if op['success']]),
                    'failed_requests': len([op for op in request_results if not op['success']])
                },
                performance_metrics={
                    'response_times_ms': [op['response_time'] * 1000 for op in request_results if op['success']]
                },
                warnings=warnings,
                errors=errors,
                passed=passed
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Web API压力测试异常: {e}")
            errors.append(str(e))
            
            return StressTestResult(
                test_name=config.test_name,
                test_type=config.test_type,
                start_time=start_time,
                end_time=datetime.now(),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                target_load=config.target_load,
                actual_peak_load=0.0,
                success_rate=0.0,
                throughput=0.0,
                avg_response_time=0.0,
                max_response_time=0.0,
                min_response_time=0.0,
                error_count=len(errors),
                total_operations=0,
                resource_usage={},
                performance_metrics={},
                warnings=warnings,
                errors=errors,
                passed=False
            )
    
    def _analyze_test_result(self, result: StressTestResult, config: StressTestConfig) -> StressTestResult:
        """分析测试结果并添加建议"""
        try:
            # 性能等级评定
            if result.success_rate >= 99 and result.actual_peak_load >= config.target_load * 0.95:
                performance_grade = "优秀"
            elif result.success_rate >= 95 and result.actual_peak_load >= config.target_load * 0.9:
                performance_grade = "良好"
            elif result.success_rate >= 90 and result.actual_peak_load >= config.target_load * 0.8:
                performance_grade = "一般"
            else:
                performance_grade = "需要改进"
            
            # 添加性能等级到资源使用信息
            result.resource_usage['performance_grade'] = performance_grade
            
            # 根据测试类型添加特定分析
            if config.test_type == 'cpu':
                if result.actual_peak_load < config.target_load * 0.8:
                    result.warnings.append("CPU负载可能受到其他进程影响")
                    
            elif config.test_type == 'memory':
                if result.actual_peak_load < config.target_load * 0.9:
                    result.warnings.append("内存分配可能受到系统限制")
                    
            elif config.test_type == 'disk':
                if result.throughput < config.target_load * 0.8:
                    result.warnings.append("磁盘I/O性能低于预期，可能是硬件限制")
                    
            elif config.test_type == 'web_api':
                if result.success_rate < 99:
                    result.warnings.append("API请求失败率较高，检查服务状态")
                if result.avg_response_time > 500:  # ms
                    result.warnings.append("API响应时间较慢，考虑性能优化")
            
            return result
            
        except Exception as e:
            logger.error(f"分析测试结果失败: {e}")
            return result
    
    async def _save_test_result(self, result: StressTestResult):
        """保存测试结果"""
        try:
            # 保存JSON格式结果
            timestamp = int(result.start_time.timestamp())
            result_file = self.output_dir / f"{result.test_name}_{timestamp}.json"
            
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
            
            # 添加到结果列表
            self.test_results.append(result)
            
            logger.info(f"测试结果已保存: {result_file}")
            
        except Exception as e:
            logger.error(f"保存测试结果失败: {e}")
    
    async def run_stress_test_suite(self, test_configs: List[StressTestConfig]) -> List[StressTestResult]:
        """运行压力测试套件"""
        logger.info(f"开始运行压力测试套件，共 {len(test_configs)} 个测试")
        
        results = []
        
        try:
            for i, config in enumerate(test_configs):
                logger.info(f"运行测试 {i+1}/{len(test_configs)}: {config.test_name}")
                
                try:
                    result = await self.run_stress_test(config)
                    results.append(result)
                    
                    # 测试间隔
                    if i < len(test_configs) - 1:
                        logger.info("等待系统恢复...")
                        await asyncio.sleep(30)  # 30秒间隔
                        
                except Exception as e:
                    logger.error(f"测试 {config.test_name} 失败: {e}")
                    # 创建失败结果
                    failed_result = StressTestResult(
                        test_name=config.test_name,
                        test_type=config.test_type,
                        start_time=datetime.now(),
                        end_time=datetime.now(),
                        duration_seconds=0.0,
                        target_load=config.target_load,
                        actual_peak_load=0.0,
                        success_rate=0.0,
                        throughput=0.0,
                        avg_response_time=0.0,
                        max_response_time=0.0,
                        min_response_time=0.0,
                        error_count=1,
                        total_operations=0,
                        resource_usage={},
                        performance_metrics={},
                        warnings=[],
                        errors=[str(e)],
                        passed=False
                    )
                    results.append(failed_result)
            
            # 生成汇总报告
            await self._generate_suite_summary(results)
            
            logger.info(f"压力测试套件完成，成功 {len([r for r in results if r.passed])}/{len(results)} 个测试")
            
            return results
            
        except Exception as e:
            logger.error(f"运行压力测试套件失败: {e}")
            return results
    
    async def _generate_suite_summary(self, results: List[StressTestResult]):
        """生成测试套件汇总报告"""
        try:
            timestamp = int(datetime.now().timestamp())
            summary_file = self.output_dir / f"stress_test_suite_summary_{timestamp}.json"
            
            # 计算汇总统计
            total_tests = len(results)
            passed_tests = len([r for r in results if r.passed])
            failed_tests = total_tests - passed_tests
            
            overall_pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
            
            # 按测试类型分组
            by_type = {}
            for result in results:
                test_type = result.test_type
                if test_type not in by_type:
                    by_type[test_type] = {'total': 0, 'passed': 0, 'results': []}
                
                by_type[test_type]['total'] += 1
                if result.passed:
                    by_type[test_type]['passed'] += 1
                by_type[test_type]['results'].append(result.to_dict())
            
            # 性能统计
            successful_results = [r for r in results if r.passed]
            if successful_results:
                avg_throughput = statistics.mean([r.throughput for r in successful_results])
                avg_response_time = statistics.mean([r.avg_response_time for r in successful_results])
                max_response_time = max([r.max_response_time for r in successful_results])
            else:
                avg_throughput = 0.0
                avg_response_time = 0.0
                max_response_time = 0.0
            
            # 创建汇总报告
            summary = {
                'generated_at': datetime.now().isoformat(),
                'summary_statistics': {
                    'total_tests': total_tests,
                    'passed_tests': passed_tests,
                    'failed_tests': failed_tests,
                    'overall_pass_rate': overall_pass_rate
                },
                'performance_statistics': {
                    'avg_throughput': avg_throughput,
                    'avg_response_time': avg_response_time,
                    'max_response_time': max_response_time
                },
                'by_test_type': by_type,
                'detailed_results': [result.to_dict() for result in results]
            }
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            logger.info(f"测试套件汇总报告已生成: {summary_file}")
            
        except Exception as e:
            logger.error(f"生成测试套件汇总报告失败: {e}")
    
    def get_test_results(self) -> List[StressTestResult]:
        """获取所有测试结果"""
        return self.test_results.copy()
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.executor:
                self.executor.shutdown(wait=True)
            
            # 清理监控数据
            self.monitoring_data.clear()
            
            logger.info("压力测试运行器清理完成")
            
        except Exception as e:
            logger.error(f"清理资源失败: {e}")


# 使用示例
async def example_usage():
    """使用示例"""
    
    config = {
        'stress_test': {
            'output_dir': 'stress_test_results',
            'enable_monitoring': True,
            'enable_cleanup': True
        }
    }
    
    # 创建压力测试运行器
    runner = StressTestRunner(config)
    
    try:
        # 定义测试配置
        test_configs = [
            # CPU压力测试
            StressTestConfig(
                test_name="CPU压力测试",
                test_type="cpu",
                duration_seconds=30,
                target_load=80.0,
                concurrent_workers=2,
                failure_threshold=90.0
            ),
            
            # 内存压力测试
            StressTestConfig(
                test_name="内存压力测试",
                test_type="memory",
                duration_seconds=30,
                target_load=70.0,
                concurrent_workers=2,
                failure_threshold=90.0
            ),
            
            # 磁盘I/O压力测试
            StressTestConfig(
                test_name="磁盘IO压力测试",
                test_type="disk",
                duration_seconds=30,
                target_load=50.0,  # MB/s
                concurrent_workers=2,
                failure_threshold=80.0,
                parameters={
                    'file_size_mb': 50,
                    'file_count': 2,
                    'block_size': 4096
                }
            )
        ]
        
        # 运行单个测试
        print("运行单个CPU压力测试...")
        cpu_result = await runner.run_stress_test(test_configs[0])
        print(f"CPU测试结果: {cpu_result.passed}, 峰值负载: {cpu_result.actual_peak_load:.1f}%")
        
        # 运行测试套件
        print("运行完整测试套件...")
        all_results = await runner.run_stress_test_suite(test_configs)
        
        # 输出结果汇总
        passed_count = len([r for r in all_results if r.passed])
        print(f"\n测试套件完成:")
        print(f"总测试数: {len(all_results)}")
        print(f"通过测试: {passed_count}")
        print(f"失败测试: {len(all_results) - passed_count}")
        print(f"通过率: {(passed_count / len(all_results) * 100):.1f}%")
        
        for result in all_results:
            status = "✅" if result.passed else "❌"
            print(f"{status} {result.test_name}: 成功率 {result.success_rate:.1f}%")
        
    finally:
        # 清理资源
        runner.cleanup()


if __name__ == '__main__':
    asyncio.run(example_usage())