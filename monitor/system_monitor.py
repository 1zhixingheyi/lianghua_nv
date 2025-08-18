"""
系统监控器

实时监控系统性能指标、资源使用情况和应用状态
"""

import asyncio
import logging
import psutil
import time
import threading
from typing import Dict, Any, List, Optional, Callable, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import deque
import json
import os

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """监控指标点"""
    timestamp: datetime
    metric_name: str
    value: float
    labels: Dict[str, str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'metric_name': self.metric_name,
            'value': self.value,
            'labels': self.labels or {}
        }


@dataclass
class SystemMetrics:
    """系统指标快照"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_bytes_sent: int
    network_bytes_recv: int
    process_count: int
    load_average: List[float]
    boot_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class ApplicationMetrics:
    """应用指标快照"""
    timestamp: datetime
    response_time_avg: float
    response_time_p95: float
    request_count: int
    error_count: int
    error_rate: float
    active_connections: int
    database_connections: int
    cache_hit_rate: float
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class SystemMonitor:
    """系统监控器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 监控配置
        self.monitor_config = {
            'collection_interval': 5,  # 采集间隔（秒）
            'retention_hours': 24,     # 数据保留时间（小时）
            'max_metrics_per_type': 10000,  # 每种指标最大保留数量
            'enable_system_metrics': True,
            'enable_application_metrics': True,
            'enable_custom_metrics': True,
            'metrics_export': {
                'enabled': True,
                'format': 'json',  # json, prometheus, influxdb
                'file_path': 'metrics_export.json',
                'export_interval': 300  # 导出间隔（秒）
            },
            'alert_thresholds': {
                'cpu_warning': 70,
                'cpu_critical': 90,
                'memory_warning': 80,
                'memory_critical': 95,
                'disk_warning': 85,
                'disk_critical': 95,
                'response_time_warning': 1.0,
                'response_time_critical': 3.0,
                'error_rate_warning': 0.05,
                'error_rate_critical': 0.1
            }
        }
        
        # 更新配置
        if 'system_monitor' in config:
            self.monitor_config.update(config['system_monitor'])
        
        # 监控状态
        self.is_running = False
        self.monitor_task = None
        self.export_task = None
        
        # 指标存储
        self.system_metrics: deque = deque(maxlen=self.monitor_config['max_metrics_per_type'])
        self.application_metrics: deque = deque(maxlen=self.monitor_config['max_metrics_per_type'])
        self.custom_metrics: Dict[str, deque] = {}
        
        # 回调函数
        self.metric_callbacks: Dict[str, List[Callable]] = {}
        self.threshold_callbacks: List[Callable] = []
        
        # 导出目录
        export_dir = os.path.dirname(self.monitor_config['metrics_export']['file_path'])
        if export_dir:
            os.makedirs(export_dir, exist_ok=True)
    
    async def start(self):
        """启动监控"""
        if self.is_running:
            logger.warning("监控器已经在运行")
            return
        
        logger.info("启动系统监控器")
        
        self.is_running = True
        
        # 启动监控任务
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        
        # 启动导出任务
        if self.monitor_config['metrics_export']['enabled']:
            self.export_task = asyncio.create_task(self._export_loop())
        
        logger.info("系统监控器已启动")
    
    async def stop(self):
        """停止监控"""
        if not self.is_running:
            logger.warning("监控器未在运行")
            return
        
        logger.info("停止系统监控器")
        
        self.is_running = False
        
        # 停止监控任务
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        # 停止导出任务
        if self.export_task:
            self.export_task.cancel()
            try:
                await self.export_task
            except asyncio.CancelledError:
                pass
        
        # 最后导出一次数据
        if self.monitor_config['metrics_export']['enabled']:
            await self._export_metrics()
        
        logger.info("系统监控器已停止")
    
    async def _monitor_loop(self):
        """监控主循环"""
        while self.is_running:
            try:
                start_time = time.time()
                
                # 收集系统指标
                if self.monitor_config['enable_system_metrics']:
                    await self._collect_system_metrics()
                
                # 收集应用指标
                if self.monitor_config['enable_application_metrics']:
                    await self._collect_application_metrics()
                
                # 清理过期数据
                await self._cleanup_expired_metrics()
                
                # 检查阈值告警
                await self._check_thresholds()
                
                # 计算实际耗时并调整睡眠时间
                elapsed = time.time() - start_time
                sleep_time = max(0, self.monitor_config['collection_interval'] - elapsed)
                
                if sleep_time < self.monitor_config['collection_interval'] * 0.5:
                    logger.warning(f"监控数据收集耗时过长: {elapsed:.2f}s")
                
                await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                await asyncio.sleep(5)
    
    async def _collect_system_metrics(self):
        """收集系统指标"""
        try:
            timestamp = datetime.now()
            
            # CPU使用率
            cpu_percent = psutil.cpu_percent()
            
            # 内存使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # 磁盘使用率
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # 网络IO
            network = psutil.net_io_counters()
            network_bytes_sent = network.bytes_sent
            network_bytes_recv = network.bytes_recv
            
            # 进程数量
            process_count = len(psutil.pids())
            
            # 系统负载
            try:
                load_average = list(psutil.getloadavg())
            except AttributeError:
                # Windows系统没有loadavg
                load_average = [0.0, 0.0, 0.0]
            
            # 系统启动时间
            boot_time = psutil.boot_time()
            
            # 创建系统指标对象
            metrics = SystemMetrics(
                timestamp=timestamp,
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_percent=disk_percent,
                network_bytes_sent=network_bytes_sent,
                network_bytes_recv=network_bytes_recv,
                process_count=process_count,
                load_average=load_average,
                boot_time=boot_time
            )
            
            # 存储指标
            self.system_metrics.append(metrics)
            
            # 触发回调
            await self._trigger_callbacks('system_metrics', metrics)
            
        except Exception as e:
            logger.error(f"收集系统指标失败: {e}")
    
    async def _collect_application_metrics(self):
        """收集应用指标"""
        try:
            timestamp = datetime.now()
            
            # 这里需要从应用中获取指标，暂时使用模拟数据
            metrics = ApplicationMetrics(
                timestamp=timestamp,
                response_time_avg=0.15,  # 从实际应用获取
                response_time_p95=0.5,   # 从实际应用获取
                request_count=100,       # 从实际应用获取
                error_count=2,           # 从实际应用获取
                error_rate=0.02,         # 计算得出
                active_connections=25,   # 从实际应用获取
                database_connections=10, # 从数据库连接池获取
                cache_hit_rate=0.85      # 从缓存系统获取
            )
            
            # 存储指标
            self.application_metrics.append(metrics)
            
            # 触发回调
            await self._trigger_callbacks('application_metrics', metrics)
            
        except Exception as e:
            logger.error(f"收集应用指标失败: {e}")
    
    async def _cleanup_expired_metrics(self):
        """清理过期指标"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=self.monitor_config['retention_hours'])
            
            # 清理系统指标
            while (self.system_metrics and 
                   self.system_metrics[0].timestamp < cutoff_time):
                self.system_metrics.popleft()
            
            # 清理应用指标
            while (self.application_metrics and 
                   self.application_metrics[0].timestamp < cutoff_time):
                self.application_metrics.popleft()
            
            # 清理自定义指标
            for metric_name, metric_deque in self.custom_metrics.items():
                while (metric_deque and 
                       metric_deque[0].timestamp < cutoff_time):
                    metric_deque.popleft()
            
        except Exception as e:
            logger.error(f"清理过期指标失败: {e}")
    
    async def _check_thresholds(self):
        """检查阈值告警"""
        try:
            if not self.system_metrics:
                return
            
            latest_metrics = self.system_metrics[-1]
            thresholds = self.monitor_config['alert_thresholds']
            
            alerts = []
            
            # 检查CPU
            if latest_metrics.cpu_percent >= thresholds['cpu_critical']:
                alerts.append({
                    'level': 'critical',
                    'metric': 'cpu_percent',
                    'value': latest_metrics.cpu_percent,
                    'threshold': thresholds['cpu_critical'],
                    'message': f"CPU使用率达到临界值: {latest_metrics.cpu_percent:.1f}%"
                })
            elif latest_metrics.cpu_percent >= thresholds['cpu_warning']:
                alerts.append({
                    'level': 'warning',
                    'metric': 'cpu_percent',
                    'value': latest_metrics.cpu_percent,
                    'threshold': thresholds['cpu_warning'],
                    'message': f"CPU使用率过高: {latest_metrics.cpu_percent:.1f}%"
                })
            
            # 检查内存
            if latest_metrics.memory_percent >= thresholds['memory_critical']:
                alerts.append({
                    'level': 'critical',
                    'metric': 'memory_percent',
                    'value': latest_metrics.memory_percent,
                    'threshold': thresholds['memory_critical'],
                    'message': f"内存使用率达到临界值: {latest_metrics.memory_percent:.1f}%"
                })
            elif latest_metrics.memory_percent >= thresholds['memory_warning']:
                alerts.append({
                    'level': 'warning',
                    'metric': 'memory_percent',
                    'value': latest_metrics.memory_percent,
                    'threshold': thresholds['memory_warning'],
                    'message': f"内存使用率过高: {latest_metrics.memory_percent:.1f}%"
                })
            
            # 检查磁盘
            if latest_metrics.disk_percent >= thresholds['disk_critical']:
                alerts.append({
                    'level': 'critical',
                    'metric': 'disk_percent',
                    'value': latest_metrics.disk_percent,
                    'threshold': thresholds['disk_critical'],
                    'message': f"磁盘使用率达到临界值: {latest_metrics.disk_percent:.1f}%"
                })
            elif latest_metrics.disk_percent >= thresholds['disk_warning']:
                alerts.append({
                    'level': 'warning',
                    'metric': 'disk_percent',
                    'value': latest_metrics.disk_percent,
                    'threshold': thresholds['disk_warning'],
                    'message': f"磁盘使用率过高: {latest_metrics.disk_percent:.1f}%"
                })
            
            # 检查应用指标
            if self.application_metrics:
                latest_app_metrics = self.application_metrics[-1]
                
                # 检查响应时间
                if latest_app_metrics.response_time_avg >= thresholds['response_time_critical']:
                    alerts.append({
                        'level': 'critical',
                        'metric': 'response_time_avg',
                        'value': latest_app_metrics.response_time_avg,
                        'threshold': thresholds['response_time_critical'],
                        'message': f"平均响应时间达到临界值: {latest_app_metrics.response_time_avg:.3f}s"
                    })
                elif latest_app_metrics.response_time_avg >= thresholds['response_time_warning']:
                    alerts.append({
                        'level': 'warning',
                        'metric': 'response_time_avg',
                        'value': latest_app_metrics.response_time_avg,
                        'threshold': thresholds['response_time_warning'],
                        'message': f"平均响应时间过高: {latest_app_metrics.response_time_avg:.3f}s"
                    })
                
                # 检查错误率
                if latest_app_metrics.error_rate >= thresholds['error_rate_critical']:
                    alerts.append({
                        'level': 'critical',
                        'metric': 'error_rate',
                        'value': latest_app_metrics.error_rate,
                        'threshold': thresholds['error_rate_critical'],
                        'message': f"错误率达到临界值: {latest_app_metrics.error_rate:.2%}"
                    })
                elif latest_app_metrics.error_rate >= thresholds['error_rate_warning']:
                    alerts.append({
                        'level': 'warning',
                        'metric': 'error_rate',
                        'value': latest_app_metrics.error_rate,
                        'threshold': thresholds['error_rate_warning'],
                        'message': f"错误率过高: {latest_app_metrics.error_rate:.2%}"
                    })
            
            # 触发告警回调
            if alerts:
                for callback in self.threshold_callbacks:
                    try:
                        await callback(alerts)
                    except Exception as e:
                        logger.error(f"执行告警回调失败: {e}")
            
        except Exception as e:
            logger.error(f"检查阈值告警失败: {e}")
    
    async def _trigger_callbacks(self, metric_type: str, metrics: Any):
        """触发指标回调"""
        try:
            callbacks = self.metric_callbacks.get(metric_type, [])
            for callback in callbacks:
                try:
                    await callback(metrics)
                except Exception as e:
                    logger.error(f"执行指标回调失败: {e}")
        except Exception as e:
            logger.error(f"触发回调失败: {e}")
    
    async def _export_loop(self):
        """导出循环"""
        while self.is_running:
            try:
                await asyncio.sleep(self.monitor_config['metrics_export']['export_interval'])
                if self.is_running:
                    await self._export_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"导出循环异常: {e}")
                await asyncio.sleep(30)
    
    async def _export_metrics(self):
        """导出指标数据"""
        try:
            export_config = self.monitor_config['metrics_export']
            
            # 准备导出数据
            export_data = {
                'timestamp': datetime.now().isoformat(),
                'system_metrics': [m.to_dict() for m in list(self.system_metrics)],
                'application_metrics': [m.to_dict() for m in list(self.application_metrics)],
                'custom_metrics': {
                    name: [point.to_dict() for point in list(deque_data)]
                    for name, deque_data in self.custom_metrics.items()
                }
            }
            
            # 根据格式导出
            if export_config['format'] == 'json':
                with open(export_config['file_path'], 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"指标数据已导出到: {export_config['file_path']}")
            
        except Exception as e:
            logger.error(f"导出指标数据失败: {e}")
    
    def add_metric_callback(self, metric_type: str, callback: Callable):
        """添加指标回调"""
        if metric_type not in self.metric_callbacks:
            self.metric_callbacks[metric_type] = []
        self.metric_callbacks[metric_type].append(callback)
    
    def remove_metric_callback(self, metric_type: str, callback: Callable):
        """移除指标回调"""
        if metric_type in self.metric_callbacks:
            try:
                self.metric_callbacks[metric_type].remove(callback)
            except ValueError:
                pass
    
    def add_threshold_callback(self, callback: Callable):
        """添加阈值告警回调"""
        self.threshold_callbacks.append(callback)
    
    def remove_threshold_callback(self, callback: Callable):
        """移除阈值告警回调"""
        try:
            self.threshold_callbacks.remove(callback)
        except ValueError:
            pass
    
    async def add_custom_metric(self, metric_name: str, value: float, 
                              labels: Optional[Dict[str, str]] = None):
        """添加自定义指标"""
        try:
            if metric_name not in self.custom_metrics:
                self.custom_metrics[metric_name] = deque(
                    maxlen=self.monitor_config['max_metrics_per_type']
                )
            
            point = MetricPoint(
                timestamp=datetime.now(),
                metric_name=metric_name,
                value=value,
                labels=labels
            )
            
            self.custom_metrics[metric_name].append(point)
            
            # 触发回调
            await self._trigger_callbacks(f'custom_metric_{metric_name}', point)
            
        except Exception as e:
            logger.error(f"添加自定义指标失败: {e}")
    
    def get_latest_system_metrics(self) -> Optional[SystemMetrics]:
        """获取最新系统指标"""
        return self.system_metrics[-1] if self.system_metrics else None
    
    def get_latest_application_metrics(self) -> Optional[ApplicationMetrics]:
        """获取最新应用指标"""
        return self.application_metrics[-1] if self.application_metrics else None
    
    def get_system_metrics_history(self, minutes: int = 60) -> List[SystemMetrics]:
        """获取系统指标历史"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [m for m in self.system_metrics if m.timestamp >= cutoff_time]
    
    def get_application_metrics_history(self, minutes: int = 60) -> List[ApplicationMetrics]:
        """获取应用指标历史"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [m for m in self.application_metrics if m.timestamp >= cutoff_time]
    
    def get_custom_metric_history(self, metric_name: str, 
                                 minutes: int = 60) -> List[MetricPoint]:
        """获取自定义指标历史"""
        if metric_name not in self.custom_metrics:
            return []
        
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [p for p in self.custom_metrics[metric_name] if p.timestamp >= cutoff_time]
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """获取指标摘要"""
        try:
            summary = {
                'monitor_status': 'running' if self.is_running else 'stopped',
                'collection_interval': self.monitor_config['collection_interval'],
                'metrics_count': {
                    'system': len(self.system_metrics),
                    'application': len(self.application_metrics),
                    'custom': sum(len(deque_data) for deque_data in self.custom_metrics.values())
                },
                'latest_metrics': {},
                'uptime_seconds': 0
            }
            
            # 最新系统指标
            latest_system = self.get_latest_system_metrics()
            if latest_system:
                summary['latest_metrics']['system'] = latest_system.to_dict()
                summary['uptime_seconds'] = time.time() - latest_system.boot_time
            
            # 最新应用指标
            latest_app = self.get_latest_application_metrics()
            if latest_app:
                summary['latest_metrics']['application'] = latest_app.to_dict()
            
            # 自定义指标概览
            summary['custom_metrics'] = list(self.custom_metrics.keys())
            
            return summary
            
        except Exception as e:
            logger.error(f"获取指标摘要失败: {e}")
            return {'error': str(e)}
    
    async def generate_metrics_report(self, hours: int = 1) -> Dict[str, Any]:
        """生成指标报告"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            # 系统指标统计
            system_metrics = [m for m in self.system_metrics if m.timestamp >= cutoff_time]
            system_stats = {}
            if system_metrics:
                cpu_values = [m.cpu_percent for m in system_metrics]
                memory_values = [m.memory_percent for m in system_metrics]
                disk_values = [m.disk_percent for m in system_metrics]
                
                system_stats = {
                    'cpu': {
                        'avg': sum(cpu_values) / len(cpu_values),
                        'max': max(cpu_values),
                        'min': min(cpu_values)
                    },
                    'memory': {
                        'avg': sum(memory_values) / len(memory_values),
                        'max': max(memory_values),
                        'min': min(memory_values)
                    },
                    'disk': {
                        'avg': sum(disk_values) / len(disk_values),
                        'max': max(disk_values),
                        'min': min(disk_values)
                    }
                }
            
            # 应用指标统计
            app_metrics = [m for m in self.application_metrics if m.timestamp >= cutoff_time]
            app_stats = {}
            if app_metrics:
                response_times = [m.response_time_avg for m in app_metrics]
                error_rates = [m.error_rate for m in app_metrics]
                
                app_stats = {
                    'response_time': {
                        'avg': sum(response_times) / len(response_times),
                        'max': max(response_times),
                        'min': min(response_times)
                    },
                    'error_rate': {
                        'avg': sum(error_rates) / len(error_rates),
                        'max': max(error_rates),
                        'min': min(error_rates)
                    },
                    'total_requests': sum(m.request_count for m in app_metrics),
                    'total_errors': sum(m.error_count for m in app_metrics)
                }
            
            return {
                'report_period_hours': hours,
                'generated_at': datetime.now().isoformat(),
                'system_statistics': system_stats,
                'application_statistics': app_stats,
                'data_points': {
                    'system_metrics': len(system_metrics),
                    'application_metrics': len(app_metrics)
                }
            }
            
        except Exception as e:
            logger.error(f"生成指标报告失败: {e}")
            return {'error': str(e)}


# 使用示例
async def example_usage():
    """使用示例"""
    
    # 创建配置
    config = {
        'system_monitor': {
            'collection_interval': 5,
            'retention_hours': 24,
            'metrics_export': {
                'enabled': True,
                'export_interval': 300
            }
        }
    }
    
    # 创建监控器
    monitor = SystemMonitor(config)
    
    # 添加自定义指标回调
    async def on_high_cpu(metrics):
        if metrics.cpu_percent > 80:
            print(f"CPU使用率过高: {metrics.cpu_percent:.1f}%")
    
    monitor.add_metric_callback('system_metrics', on_high_cpu)
    
    # 添加告警回调
    async def on_alert(alerts):
        for alert in alerts:
            print(f"告警: {alert['message']}")
    
    monitor.add_threshold_callback(on_alert)
    
    try:
        # 启动监控
        await monitor.start()
        
        # 运行一段时间
        await asyncio.sleep(60)
        
        # 添加自定义指标
        await monitor.add_custom_metric('test_metric', 42.5, {'type': 'test'})
        
        # 获取指标摘要
        summary = monitor.get_metrics_summary()
        print("指标摘要:", summary)
        
        # 生成报告
        report = await monitor.generate_metrics_report(hours=1)
        print("指标报告:", report)
        
    finally:
        # 停止监控
        await monitor.stop()


if __name__ == '__main__':
    asyncio.run(example_usage())