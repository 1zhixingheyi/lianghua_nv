"""
诊断分析器

对系统性能问题进行深度分析和诊断
"""

import asyncio
import logging
import statistics
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict, Counter
import json
import math

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticResult:
    """诊断结果"""
    issue_id: str
    severity: str  # critical, high, medium, low
    category: str  # performance, resource, stability, security
    title: str
    description: str
    impact: str
    root_causes: List[str]
    recommendations: List[str]
    confidence: float  # 0.0 - 1.0
    detected_at: datetime
    evidence: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'issue_id': self.issue_id,
            'severity': self.severity,
            'category': self.category,
            'title': self.title,
            'description': self.description,
            'impact': self.impact,
            'root_causes': self.root_causes,
            'recommendations': self.recommendations,
            'confidence': self.confidence,
            'detected_at': self.detected_at.isoformat(),
            'evidence': self.evidence
        }


@dataclass
class PerformanceAnomaly:
    """性能异常"""
    metric_name: str
    anomaly_type: str  # spike, drop, trend, outlier
    severity: float
    timestamp: datetime
    value: float
    baseline: float
    deviation: float
    context: Dict[str, Any]


class DiagnosticAnalyzer:
    """诊断分析器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 诊断配置
        self.diagnostic_config = {
            'analysis_window_minutes': 60,     # 分析窗口时间
            'anomaly_threshold': 2.0,          # 异常检测阈值（标准差倍数）
            'trend_analysis_points': 20,       # 趋势分析最少数据点
            'correlation_threshold': 0.7,      # 关联分析阈值
            'enable_root_cause_analysis': True,
            'enable_predictive_analysis': True,
            'confidence_threshold': 0.6,       # 最低置信度阈值
            'max_issues_per_analysis': 50,     # 每次分析最大问题数
            'performance_baselines': {
                'cpu_normal': 30,              # 正常CPU使用率
                'memory_normal': 50,           # 正常内存使用率
                'response_time_normal': 0.2,   # 正常响应时间
                'error_rate_normal': 0.01      # 正常错误率
            }
        }
        
        # 更新配置
        if 'diagnostic_analyzer' in config:
            self.diagnostic_config.update(config['diagnostic_analyzer'])
        
        # 诊断状态
        self.detected_issues: List[DiagnosticResult] = []
        self.anomaly_history: List[PerformanceAnomaly] = []
        self.baseline_cache: Dict[str, Dict[str, float]] = {}
        
        # 诊断规则
        self.diagnostic_rules = {
            'high_cpu_usage': self._analyze_high_cpu_usage,
            'memory_leak': self._analyze_memory_leak,
            'response_time_degradation': self._analyze_response_time_degradation,
            'error_rate_spike': self._analyze_error_rate_spike,
            'disk_space_exhaustion': self._analyze_disk_space_exhaustion,
            'connection_pool_exhaustion': self._analyze_connection_pool_exhaustion,
            'cache_performance_degradation': self._analyze_cache_performance,
            'database_slowdown': self._analyze_database_slowdown,
            'network_latency_issues': self._analyze_network_latency,
            'resource_contention': self._analyze_resource_contention
        }
    
    async def analyze_system_health(self, system_metrics: List[Any], 
                                  application_metrics: List[Any]) -> List[DiagnosticResult]:
        """分析系统健康状况"""
        logger.info("开始系统健康诊断分析")
        
        detected_issues = []
        
        try:
            # 数据预处理
            if not system_metrics and not application_metrics:
                logger.warning("没有可用的指标数据进行分析")
                return detected_issues
            
            # 更新基线
            await self._update_baselines(system_metrics, application_metrics)
            
            # 异常检测
            anomalies = await self._detect_anomalies(system_metrics, application_metrics)
            self.anomaly_history.extend(anomalies)
            
            # 运行诊断规则
            for rule_name, rule_func in self.diagnostic_rules.items():
                try:
                    logger.debug(f"运行诊断规则: {rule_name}")
                    issues = await rule_func(system_metrics, application_metrics, anomalies)
                    if issues:
                        detected_issues.extend(issues)
                except Exception as e:
                    logger.error(f"诊断规则 {rule_name} 执行失败: {e}")
            
            # 关联分析
            if self.diagnostic_config['enable_root_cause_analysis']:
                correlated_issues = await self._perform_correlation_analysis(detected_issues)
                detected_issues = correlated_issues
            
            # 过滤低置信度问题
            filtered_issues = [
                issue for issue in detected_issues 
                if issue.confidence >= self.diagnostic_config['confidence_threshold']
            ]
            
            # 按严重程度排序
            filtered_issues.sort(
                key=lambda x: (
                    {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}.get(x.severity, 0),
                    x.confidence
                ),
                reverse=True
            )
            
            # 限制问题数量
            max_issues = self.diagnostic_config['max_issues_per_analysis']
            if len(filtered_issues) > max_issues:
                filtered_issues = filtered_issues[:max_issues]
            
            # 更新已检测问题列表
            self.detected_issues = filtered_issues
            
            logger.info(f"诊断分析完成，检测到 {len(filtered_issues)} 个问题")
            
        except Exception as e:
            logger.error(f"系统健康诊断分析失败: {e}")
        
        return filtered_issues
    
    async def _update_baselines(self, system_metrics: List[Any], 
                              application_metrics: List[Any]):
        """更新基线数据"""
        try:
            # 计算系统指标基线
            if system_metrics:
                cpu_values = [m.cpu_percent for m in system_metrics[-50:]]  # 最近50个点
                memory_values = [m.memory_percent for m in system_metrics[-50:]]
                disk_values = [m.disk_percent for m in system_metrics[-50:]]
                
                self.baseline_cache['system'] = {
                    'cpu_mean': statistics.mean(cpu_values) if cpu_values else 0,
                    'cpu_std': statistics.stdev(cpu_values) if len(cpu_values) > 1 else 0,
                    'memory_mean': statistics.mean(memory_values) if memory_values else 0,
                    'memory_std': statistics.stdev(memory_values) if len(memory_values) > 1 else 0,
                    'disk_mean': statistics.mean(disk_values) if disk_values else 0,
                    'disk_std': statistics.stdev(disk_values) if len(disk_values) > 1 else 0
                }
            
            # 计算应用指标基线
            if application_metrics:
                response_times = [m.response_time_avg for m in application_metrics[-50:]]
                error_rates = [m.error_rate for m in application_metrics[-50:]]
                
                self.baseline_cache['application'] = {
                    'response_time_mean': statistics.mean(response_times) if response_times else 0,
                    'response_time_std': statistics.stdev(response_times) if len(response_times) > 1 else 0,
                    'error_rate_mean': statistics.mean(error_rates) if error_rates else 0,
                    'error_rate_std': statistics.stdev(error_rates) if len(error_rates) > 1 else 0
                }
                
        except Exception as e:
            logger.error(f"更新基线数据失败: {e}")
    
    async def _detect_anomalies(self, system_metrics: List[Any], 
                              application_metrics: List[Any]) -> List[PerformanceAnomaly]:
        """检测性能异常"""
        anomalies = []
        threshold = self.diagnostic_config['anomaly_threshold']
        
        try:
            # 检测系统指标异常
            if system_metrics and 'system' in self.baseline_cache:
                baseline = self.baseline_cache['system']
                latest_system = system_metrics[-1]
                
                # CPU异常
                cpu_deviation = abs(latest_system.cpu_percent - baseline['cpu_mean'])
                if baseline['cpu_std'] > 0 and cpu_deviation > threshold * baseline['cpu_std']:
                    anomalies.append(PerformanceAnomaly(
                        metric_name='cpu_percent',
                        anomaly_type='outlier',
                        severity=cpu_deviation / (baseline['cpu_std'] * threshold),
                        timestamp=latest_system.timestamp,
                        value=latest_system.cpu_percent,
                        baseline=baseline['cpu_mean'],
                        deviation=cpu_deviation,
                        context={'threshold': threshold, 'std': baseline['cpu_std']}
                    ))
                
                # 内存异常
                memory_deviation = abs(latest_system.memory_percent - baseline['memory_mean'])
                if baseline['memory_std'] > 0 and memory_deviation > threshold * baseline['memory_std']:
                    anomalies.append(PerformanceAnomaly(
                        metric_name='memory_percent',
                        anomaly_type='outlier',
                        severity=memory_deviation / (baseline['memory_std'] * threshold),
                        timestamp=latest_system.timestamp,
                        value=latest_system.memory_percent,
                        baseline=baseline['memory_mean'],
                        deviation=memory_deviation,
                        context={'threshold': threshold, 'std': baseline['memory_std']}
                    ))
            
            # 检测应用指标异常
            if application_metrics and 'application' in self.baseline_cache:
                baseline = self.baseline_cache['application']
                latest_app = application_metrics[-1]
                
                # 响应时间异常
                rt_deviation = abs(latest_app.response_time_avg - baseline['response_time_mean'])
                if baseline['response_time_std'] > 0 and rt_deviation > threshold * baseline['response_time_std']:
                    anomalies.append(PerformanceAnomaly(
                        metric_name='response_time_avg',
                        anomaly_type='outlier',
                        severity=rt_deviation / (baseline['response_time_std'] * threshold),
                        timestamp=latest_app.timestamp,
                        value=latest_app.response_time_avg,
                        baseline=baseline['response_time_mean'],
                        deviation=rt_deviation,
                        context={'threshold': threshold, 'std': baseline['response_time_std']}
                    ))
                
                # 错误率异常
                er_deviation = abs(latest_app.error_rate - baseline['error_rate_mean'])
                if baseline['error_rate_std'] > 0 and er_deviation > threshold * baseline['error_rate_std']:
                    anomalies.append(PerformanceAnomaly(
                        metric_name='error_rate',
                        anomaly_type='spike' if latest_app.error_rate > baseline['error_rate_mean'] else 'drop',
                        severity=er_deviation / (baseline['error_rate_std'] * threshold),
                        timestamp=latest_app.timestamp,
                        value=latest_app.error_rate,
                        baseline=baseline['error_rate_mean'],
                        deviation=er_deviation,
                        context={'threshold': threshold, 'std': baseline['error_rate_std']}
                    ))
            
            # 检测趋势异常
            trend_anomalies = await self._detect_trend_anomalies(system_metrics, application_metrics)
            anomalies.extend(trend_anomalies)
            
        except Exception as e:
            logger.error(f"异常检测失败: {e}")
        
        return anomalies
    
    async def _detect_trend_anomalies(self, system_metrics: List[Any], 
                                    application_metrics: List[Any]) -> List[PerformanceAnomaly]:
        """检测趋势异常"""
        anomalies = []
        min_points = self.diagnostic_config['trend_analysis_points']
        
        try:
            # 内存泄漏趋势检测
            if len(system_metrics) >= min_points:
                memory_values = [m.memory_percent for m in system_metrics[-min_points:]]
                trend_slope = self._calculate_trend_slope(memory_values)
                
                # 如果内存使用率持续上升且斜率较大
                if trend_slope > 0.5:  # 每个时间点上升0.5%
                    anomalies.append(PerformanceAnomaly(
                        metric_name='memory_percent',
                        anomaly_type='trend',
                        severity=min(trend_slope / 0.5, 5.0),  # 最高5倍严重度
                        timestamp=system_metrics[-1].timestamp,
                        value=system_metrics[-1].memory_percent,
                        baseline=memory_values[0],
                        deviation=memory_values[-1] - memory_values[0],
                        context={'trend_slope': trend_slope, 'trend_type': 'increasing'}
                    ))
            
            # 响应时间恶化趋势检测
            if len(application_metrics) >= min_points:
                rt_values = [m.response_time_avg for m in application_metrics[-min_points:]]
                trend_slope = self._calculate_trend_slope(rt_values)
                
                if trend_slope > 0.01:  # 每个时间点增加10ms
                    anomalies.append(PerformanceAnomaly(
                        metric_name='response_time_avg',
                        anomaly_type='trend',
                        severity=min(trend_slope / 0.01, 5.0),
                        timestamp=application_metrics[-1].timestamp,
                        value=application_metrics[-1].response_time_avg,
                        baseline=rt_values[0],
                        deviation=rt_values[-1] - rt_values[0],
                        context={'trend_slope': trend_slope, 'trend_type': 'increasing'}
                    ))
        
        except Exception as e:
            logger.error(f"趋势异常检测失败: {e}")
        
        return anomalies
    
    def _calculate_trend_slope(self, values: List[float]) -> float:
        """计算趋势斜率（简单线性回归）"""
        if len(values) < 2:
            return 0.0
        
        n = len(values)
        x_values = list(range(n))
        
        # 计算斜率
        x_mean = sum(x_values) / n
        y_mean = sum(values) / n
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)
        
        return numerator / denominator if denominator != 0 else 0.0
    
    async def _analyze_high_cpu_usage(self, system_metrics: List[Any], 
                                    application_metrics: List[Any], 
                                    anomalies: List[PerformanceAnomaly]) -> List[DiagnosticResult]:
        """分析高CPU使用率问题"""
        issues = []
        
        try:
            if not system_metrics:
                return issues
            
            latest_cpu = system_metrics[-1].cpu_percent
            baseline_cpu = self.diagnostic_config['performance_baselines']['cpu_normal']
            
            # 检查是否有持续的高CPU使用率
            recent_metrics = system_metrics[-10:]  # 最近10个数据点
            high_cpu_count = sum(1 for m in recent_metrics if m.cpu_percent > 80)
            
            if high_cpu_count >= 7:  # 70%的时间CPU都很高
                severity = 'critical' if latest_cpu > 95 else 'high' if latest_cpu > 85 else 'medium'
                
                # 分析可能的根因
                root_causes = []
                if len(recent_metrics) >= 5:
                    cpu_trend = self._calculate_trend_slope([m.cpu_percent for m in recent_metrics])
                    if cpu_trend > 1:
                        root_causes.append("CPU使用率持续上升，可能存在CPU密集型任务或死循环")
                
                # 检查进程数量
                if recent_metrics[-1].process_count > 200:
                    root_causes.append("系统进程数量过多，可能存在进程泄漏")
                
                if not root_causes:
                    root_causes.append("系统负载过高或存在性能瓶颈")
                
                issues.append(DiagnosticResult(
                    issue_id=f"high_cpu_{int(datetime.now().timestamp())}",
                    severity=severity,
                    category='performance',
                    title='CPU使用率过高',
                    description=f'CPU使用率达到 {latest_cpu:.1f}%，超过正常基线 {baseline_cpu}%',
                    impact='系统响应变慢，可能影响用户体验',
                    root_causes=root_causes,
                    recommendations=[
                        '检查CPU密集型进程并优化',
                        '考虑增加CPU资源或横向扩展',
                        '分析应用性能瓶颈',
                        '检查是否存在死循环或无限递归'
                    ],
                    confidence=min(0.9, high_cpu_count / 10),
                    detected_at=datetime.now(),
                    evidence={
                        'current_cpu_percent': latest_cpu,
                        'baseline_cpu_percent': baseline_cpu,
                        'high_cpu_periods': high_cpu_count,
                        'process_count': recent_metrics[-1].process_count
                    }
                ))
        
        except Exception as e:
            logger.error(f"分析高CPU使用率问题失败: {e}")
        
        return issues
    
    async def _analyze_memory_leak(self, system_metrics: List[Any], 
                                 application_metrics: List[Any], 
                                 anomalies: List[PerformanceAnomaly]) -> List[DiagnosticResult]:
        """分析内存泄漏问题"""
        issues = []
        
        try:
            if len(system_metrics) < 20:  # 需要足够的数据点
                return issues
            
            # 检查内存使用趋势
            memory_values = [m.memory_percent for m in system_metrics[-20:]]
            trend_slope = self._calculate_trend_slope(memory_values)
            
            # 如果内存持续上升
            if trend_slope > 0.3:  # 每个时间点上升0.3%
                latest_memory = system_metrics[-1].memory_percent
                severity = 'critical' if latest_memory > 90 else 'high' if latest_memory > 80 else 'medium'
                
                # 估算内存耗尽时间
                if trend_slope > 0:
                    remaining_memory = 100 - latest_memory
                    time_to_exhaustion = remaining_memory / trend_slope
                    time_to_exhaustion_hours = time_to_exhaustion * self.diagnostic_config['analysis_window_minutes'] / 60
                else:
                    time_to_exhaustion_hours = float('inf')
                
                confidence = min(0.95, trend_slope / 0.5)  # 趋势越明显置信度越高
                
                issues.append(DiagnosticResult(
                    issue_id=f"memory_leak_{int(datetime.now().timestamp())}",
                    severity=severity,
                    category='resource',
                    title='疑似内存泄漏',
                    description=f'内存使用率持续上升，当前 {latest_memory:.1f}%，上升趋势 {trend_slope:.2f}%/周期',
                    impact=f'可能在 {time_to_exhaustion_hours:.1f} 小时内耗尽内存' if time_to_exhaustion_hours < 100 else '长期内存消耗增长',
                    root_causes=[
                        '应用程序存在内存泄漏',
                        '缓存数据持续增长未清理',
                        '对象引用未正确释放',
                        '内存池配置不当'
                    ],
                    recommendations=[
                        '检查应用内存使用模式',
                        '分析堆转储文件定位泄漏源',
                        '检查缓存清理策略',
                        '优化对象生命周期管理',
                        '考虑重启服务释放内存'
                    ],
                    confidence=confidence,
                    detected_at=datetime.now(),
                    evidence={
                        'memory_trend_slope': trend_slope,
                        'current_memory_percent': latest_memory,
                        'estimated_exhaustion_hours': time_to_exhaustion_hours,
                        'analysis_window_size': len(memory_values)
                    }
                ))
        
        except Exception as e:
            logger.error(f"分析内存泄漏问题失败: {e}")
        
        return issues
    
    async def _analyze_response_time_degradation(self, system_metrics: List[Any], 
                                               application_metrics: List[Any], 
                                               anomalies: List[PerformanceAnomaly]) -> List[DiagnosticResult]:
        """分析响应时间恶化问题"""
        issues = []
        
        try:
            if not application_metrics:
                return issues
            
            latest_rt = application_metrics[-1].response_time_avg
            baseline_rt = self.diagnostic_config['performance_baselines']['response_time_normal']
            
            # 检查响应时间是否显著恶化
            if latest_rt > baseline_rt * 3:  # 超过基线3倍
                severity = 'critical' if latest_rt > 5.0 else 'high' if latest_rt > 2.0 else 'medium'
                
                # 分析可能的根因
                root_causes = []
                if len(application_metrics) >= 10:
                    rt_values = [m.response_time_avg for m in application_metrics[-10:]]
                    rt_trend = self._calculate_trend_slope(rt_values)
                    if rt_trend > 0.01:
                        root_causes.append("响应时间持续恶化，可能存在性能衰退")
                
                # 检查相关指标
                if system_metrics:
                    latest_system = system_metrics[-1]
                    if latest_system.cpu_percent > 80:
                        root_causes.append("CPU使用率过高影响响应时间")
                    if latest_system.memory_percent > 85:
                        root_causes.append("内存压力大可能导致GC频繁")
                
                if application_metrics[-1].database_connections > 80:
                    root_causes.append("数据库连接池可能接近饱和")
                
                if not root_causes:
                    root_causes.append("应用性能下降或外部依赖延迟")
                
                issues.append(DiagnosticResult(
                    issue_id=f"response_time_degradation_{int(datetime.now().timestamp())}",
                    severity=severity,
                    category='performance',
                    title='响应时间恶化',
                    description=f'平均响应时间 {latest_rt:.3f}s，超过正常基线 {baseline_rt:.3f}s',
                    impact='用户体验下降，可能导致请求超时',
                    root_causes=root_causes,
                    recommendations=[
                        '分析慢查询和数据库性能',
                        '检查网络延迟和外部服务',
                        '优化应用代码性能瓶颈',
                        '检查缓存命中率',
                        '分析GC日志和内存使用'
                    ],
                    confidence=min(0.9, latest_rt / baseline_rt / 10),
                    detected_at=datetime.now(),
                    evidence={
                        'current_response_time': latest_rt,
                        'baseline_response_time': baseline_rt,
                        'degradation_ratio': latest_rt / baseline_rt
                    }
                ))
        
        except Exception as e:
            logger.error(f"分析响应时间恶化问题失败: {e}")
        
        return issues
    
    async def _analyze_error_rate_spike(self, system_metrics: List[Any], 
                                      application_metrics: List[Any], 
                                      anomalies: List[PerformanceAnomaly]) -> List[DiagnosticResult]:
        """分析错误率激增问题"""
        issues = []
        
        try:
            if not application_metrics:
                return issues
            
            latest_error_rate = application_metrics[-1].error_rate
            baseline_error_rate = self.diagnostic_config['performance_baselines']['error_rate_normal']
            
            # 检查错误率是否异常
            if latest_error_rate > baseline_error_rate * 5:  # 超过基线5倍
                severity = 'critical' if latest_error_rate > 0.1 else 'high' if latest_error_rate > 0.05 else 'medium'
                
                # 分析错误模式
                root_causes = []
                if len(application_metrics) >= 5:
                    recent_errors = [m.error_rate for m in application_metrics[-5:]]
                    if all(rate > baseline_error_rate * 2 for rate in recent_errors):
                        root_causes.append("错误率持续偏高，可能系统存在稳定性问题")
                
                # 检查相关指标
                if system_metrics:
                    latest_system = system_metrics[-1]
                    if latest_system.cpu_percent > 90:
                        root_causes.append("CPU资源耗尽可能导致服务异常")
                    if latest_system.memory_percent > 90:
                        root_causes.append("内存不足可能导致应用错误")
                
                if application_metrics[-1].database_connections < 5:
                    root_causes.append("数据库连接不足可能导致连接错误")
                
                if not root_causes:
                    root_causes.append("应用逻辑错误或外部依赖故障")
                
                issues.append(DiagnosticResult(
                    issue_id=f"error_rate_spike_{int(datetime.now().timestamp())}",
                    severity=severity,
                    category='stability',
                    title='错误率激增',
                    description=f'错误率 {latest_error_rate:.2%}，超过正常基线 {baseline_error_rate:.2%}',
                    impact='系统稳定性下降，用户请求失败率增加',
                    root_causes=root_causes,
                    recommendations=[
                        '检查应用错误日志定位问题',
                        '检查外部依赖服务状态',
                        '验证数据库连接和查询',
                        '检查网络连接稳定性',
                        '分析资源使用情况'
                    ],
                    confidence=min(0.95, latest_error_rate / baseline_error_rate / 10),
                    detected_at=datetime.now(),
                    evidence={
                        'current_error_rate': latest_error_rate,
                        'baseline_error_rate': baseline_error_rate,
                        'spike_ratio': latest_error_rate / baseline_error_rate,
                        'total_errors': application_metrics[-1].error_count
                    }
                ))
        
        except Exception as e:
            logger.error(f"分析错误率激增问题失败: {e}")
        
        return issues
    
    async def _analyze_disk_space_exhaustion(self, system_metrics: List[Any], 
                                           application_metrics: List[Any], 
                                           anomalies: List[PerformanceAnomaly]) -> List[DiagnosticResult]:
        """分析磁盘空间耗尽问题"""
        issues = []
        
        try:
            if not system_metrics:
                return issues
            
            latest_disk = system_metrics[-1].disk_percent
            
            if latest_disk > 85:  # 磁盘使用率超过85%
                severity = 'critical' if latest_disk > 95 else 'high' if latest_disk > 90 else 'medium'
                
                # 预测磁盘耗尽时间
                if len(system_metrics) >= 10:
                    disk_values = [m.disk_percent for m in system_metrics[-10:]]
                    disk_trend = self._calculate_trend_slope(disk_values)
                    
                    if disk_trend > 0:
                        remaining_space = 100 - latest_disk
                        time_to_exhaustion = remaining_space / disk_trend
                        time_to_exhaustion_hours = time_to_exhaustion * self.diagnostic_config['analysis_window_minutes'] / 60
                    else:
                        time_to_exhaustion_hours = float('inf')
                else:
                    time_to_exhaustion_hours = float('inf')
                
                issues.append(DiagnosticResult(
                    issue_id=f"disk_space_exhaustion_{int(datetime.now().timestamp())}",
                    severity=severity,
                    category='resource',
                    title='磁盘空间不足',
                    description=f'磁盘使用率 {latest_disk:.1f}%，接近存储上限',
                    impact='可能导致应用无法写入数据，服务中断',
                    root_causes=[
                        '日志文件持续增长',
                        '临时文件未及时清理',
                        '数据文件增长过快',
                        '备份文件占用过多空间'
                    ],
                    recommendations=[
                        '清理日志文件和临时文件',
                        '配置日志轮转策略',
                        '迁移或压缩历史数据',
                        '扩展磁盘容量',
                        '实施数据归档策略'
                    ],
                    confidence=0.9,
                    detected_at=datetime.now(),
                    evidence={
                        'current_disk_percent': latest_disk,
                        'estimated_exhaustion_hours': time_to_exhaustion_hours if time_to_exhaustion_hours < 1000 else None
                    }
                ))
        
        except Exception as e:
            logger.error(f"分析磁盘空间耗尽问题失败: {e}")
        
        return issues
    
    async def _analyze_connection_pool_exhaustion(self, system_metrics: List[Any], 
                                                application_metrics: List[Any], 
                                                anomalies: List[PerformanceAnomaly]) -> List[DiagnosticResult]:
        """分析连接池耗尽问题"""
        issues = []
        
        try:
            if not application_metrics:
                return issues
            
            latest_db_connections = application_metrics[-1].database_connections
            
            # 假设最大连接数为100（实际应从配置获取）
            max_connections = 100
            connection_usage_rate = latest_db_connections / max_connections
            
            if connection_usage_rate > 0.8:  # 连接使用率超过80%
                severity = 'critical' if connection_usage_rate > 0.95 else 'high' if connection_usage_rate > 0.9 else 'medium'
                
                issues.append(DiagnosticResult(
                    issue_id=f"connection_pool_exhaustion_{int(datetime.now().timestamp())}",
                    severity=severity,
                    category='resource',
                    title='数据库连接池接近饱和',
                    description=f'数据库连接数 {latest_db_connections}/{max_connections}，使用率 {connection_usage_rate:.1%}',
                    impact='新请求可能无法获取数据库连接，导致请求失败',
                    root_causes=[
                        '连接泄漏未正确关闭',
                        '长时间运行的查询占用连接',
                        '连接池配置过小',
                        '并发请求量超出预期'
                    ],
                    recommendations=[
                        '检查连接泄漏和未关闭的连接',
                        '优化长时间运行的数据库查询',
                        '增加连接池大小',
                        '实施连接超时策略',
                        '分析数据库性能瓶颈'
                    ],
                    confidence=0.85,
                    detected_at=datetime.now(),
                    evidence={
                        'current_connections': latest_db_connections,
                        'max_connections': max_connections,
                        'usage_rate': connection_usage_rate
                    }
                ))
        
        except Exception as e:
            logger.error(f"分析连接池耗尽问题失败: {e}")
        
        return issues
    
    async def _analyze_cache_performance(self, system_metrics: List[Any], 
                                       application_metrics: List[Any], 
                                       anomalies: List[PerformanceAnomaly]) -> List[DiagnosticResult]:
        """分析缓存性能问题"""
        issues = []
        
        try:
            if not application_metrics:
                return issues
            
            latest_cache_hit_rate = application_metrics[-1].cache_hit_rate
            
            if latest_cache_hit_rate < 0.7:  # 缓存命中率低于70%
                severity = 'medium' if latest_cache_hit_rate > 0.5 else 'high'
                
                issues.append(DiagnosticResult(
                    issue_id=f"cache_performance_{int(datetime.now().timestamp())}",
                    severity=severity,
                    category='performance',
                    title='缓存命中率偏低',
                    description=f'缓存命中率 {latest_cache_hit_rate:.1%}，低于期望水平',
                    impact='数据库查询增加，响应时间可能变长',
                    root_causes=[
                        '缓存策略配置不当',
                        '缓存过期时间过短',
                        '数据访问模式发生变化',
                        '缓存容量不足导致频繁淘汰'
                    ],
                    recommendations=[
                        '分析数据访问模式优化缓存策略',
                        '调整缓存过期时间',
                        '增加缓存容量',
                        '优化缓存key设计',
                        '实施缓存预热策略'
                    ],
                    confidence=0.75,
                    detected_at=datetime.now(),
                    evidence={
                        'cache_hit_rate': latest_cache_hit_rate,
                        'expected_hit_rate': 0.8
                    }
                ))
        
        except Exception as e:
            logger.error(f"分析缓存性能问题失败: {e}")
        
        return issues
    
    async def _analyze_database_slowdown(self, system_metrics: List[Any], 
                                       application_metrics: List[Any], 
                                       anomalies: List[PerformanceAnomaly]) -> List[DiagnosticResult]:
        """分析数据库慢查询问题"""
        issues = []
        
        try:
            # 这个分析需要结合响应时间和数据库相关指标
            if not application_metrics:
                return issues
            
            latest_app = application_metrics[-1]
            
            # 如果响应时间高且缓存命中率正常，可能是数据库问题
            if (latest_app.response_time_avg > 1.0 and 
                latest_app.cache_hit_rate > 0.8 and 
                latest_app.database_connections > 20):
                
                issues.append(DiagnosticResult(
                    issue_id=f"database_slowdown_{int(datetime.now().timestamp())}",
                    severity='medium',
                    category='performance',
                    title='疑似数据库性能问题',
                    description='响应时间较高，但缓存命中率正常，可能存在数据库性能瓶颈',
                    impact='查询响应变慢，影响整体应用性能',
                    root_causes=[
                        '存在慢查询或锁等待',
                        '数据库索引缺失或失效',
                        '数据库连接数过多',
                        '数据库服务器资源不足'
                    ],
                    recommendations=[
                        '分析数据库慢查询日志',
                        '检查数据库索引使用情况',
                        '优化SQL查询性能',
                        '监控数据库服务器资源',
                        '考虑数据库连接池优化'
                    ],
                    confidence=0.6,
                    detected_at=datetime.now(),
                    evidence={
                        'response_time': latest_app.response_time_avg,
                        'cache_hit_rate': latest_app.cache_hit_rate,
                        'db_connections': latest_app.database_connections
                    }
                ))
        
        except Exception as e:
            logger.error(f"分析数据库慢查询问题失败: {e}")
        
        return issues
    
    async def _analyze_network_latency(self, system_metrics: List[Any], 
                                     application_metrics: List[Any], 
                                     anomalies: List[PerformanceAnomaly]) -> List[DiagnosticResult]:
        """分析网络延迟问题"""
        issues = []
        
        try:
            if not system_metrics or len(system_metrics) < 2:
                return issues
            
            # 简单的网络IO分析
            current_net = system_metrics[-1]
            previous_net = system_metrics[-2]
            
            # 计算网络IO变化（这里简化处理）
            net_bytes_diff = (current_net.network_bytes_sent + current_net.network_bytes_recv) - \
                           (previous_net.network_bytes_sent + previous_net.network_bytes_recv)
            
            # 如果网络IO很大但响应时间也很高，可能有网络问题
            if (application_metrics and 
                net_bytes_diff > 1000000 and  # 1MB网络IO
                application_metrics[-1].response_time_avg > 1.0):
                
                issues.append(DiagnosticResult(
                    issue_id=f"network_latency_{int(datetime.now().timestamp())}",
                    severity='medium',
                    category='performance',
                    title='疑似网络延迟问题',
                    description='网络IO较高且响应时间偏长，可能存在网络瓶颈',
                    impact='网络传输延迟影响应用响应性能',
                    root_causes=[
                        '网络带宽不足',
                        '网络设备延迟',
                        '外部服务响应慢',
                        'DNS解析问题'
                    ],
                    recommendations=[
                        '检查网络带宽使用情况',
                        '测试外部服务连接延迟',
                        '检查DNS解析性能',
                        '优化网络配置',
                        '考虑CDN或缓存优化'
                    ],
                    confidence=0.5,
                    detected_at=datetime.now(),
                    evidence={
                        'network_io_diff': net_bytes_diff,
                        'response_time': application_metrics[-1].response_time_avg
                    }
                ))
        
        except Exception as e:
            logger.error(f"分析网络延迟问题失败: {e}")
        
        return issues
    
    async def _analyze_resource_contention(self, system_metrics: List[Any], 
                                         application_metrics: List[Any], 
                                         anomalies: List[PerformanceAnomaly]) -> List[DiagnosticResult]:
        """分析资源竞争问题"""
        issues = []
        
        try:
            if not system_metrics or not application_metrics:
                return issues
            
            latest_system = system_metrics[-1]
            latest_app = application_metrics[-1]
            
            # 检查多个资源同时紧张的情况
            resource_pressure_count = 0
            pressure_details = []
            
            if latest_system.cpu_percent > 80:
                resource_pressure_count += 1
                pressure_details.append(f"CPU: {latest_system.cpu_percent:.1f}%")
            
            if latest_system.memory_percent > 80:
                resource_pressure_count += 1
                pressure_details.append(f"内存: {latest_system.memory_percent:.1f}%")
            
            if latest_app.database_connections > 80:
                resource_pressure_count += 1
                pressure_details.append(f"数据库连接: {latest_app.database_connections}")
            
            if latest_app.response_time_avg > 1.0:
                resource_pressure_count += 1
                pressure_details.append(f"响应时间: {latest_app.response_time_avg:.3f}s")
            
            # 如果多个资源同时紧张，可能存在资源竞争
            if resource_pressure_count >= 3:
                issues.append(DiagnosticResult(
                    issue_id=f"resource_contention_{int(datetime.now().timestamp())}",
                    severity='high',
                    category='performance',
                    title='多资源竞争问题',
                    description=f'检测到 {resource_pressure_count} 种资源同时存在压力',
                    impact='系统整体性能下降，可能出现连锁反应',
                    root_causes=[
                        '系统负载超出设计容量',
                        '资源配置不平衡',
                        '存在资源热点竞争',
                        '应用架构存在瓶颈'
                    ],
                    recommendations=[
                        '立即检查系统负载分布',
                        '分析资源使用模式',
                        '考虑紧急扩容',
                        '优化资源分配策略',
                        '实施负载均衡'
                    ],
                    confidence=0.8,
                    detected_at=datetime.now(),
                    evidence={
                        'pressure_count': resource_pressure_count,
                        'pressure_details': pressure_details
                    }
                ))
        
        except Exception as e:
            logger.error(f"分析资源竞争问题失败: {e}")
        
        return issues
    
    async def _perform_correlation_analysis(self, issues: List[DiagnosticResult]) -> List[DiagnosticResult]:
        """执行关联分析，找出问题间的因果关系"""
        try:
            if len(issues) <= 1:
                return issues
            
            # 根据问题类型和时间进行关联分析
            correlated_issues = []
            processed_issues = set()
            
            for i, issue in enumerate(issues):
                if i in processed_issues:
                    continue
                
                # 寻找相关问题
                related_issues = [issue]
                processed_issues.add(i)
                
                for j, other_issue in enumerate(issues[i+1:], i+1):
                    if j in processed_issues:
                        continue
                    
                    # 检查问题是否相关
                    if self._are_issues_related(issue, other_issue):
                        related_issues.append(other_issue)
                        processed_issues.add(j)
                
                # 如果找到相关问题，创建综合分析
                if len(related_issues) > 1:
                    composite_issue = self._create_composite_issue(related_issues)
                    correlated_issues.append(composite_issue)
                else:
                    correlated_issues.append(issue)
            
            return correlated_issues
        
        except Exception as e:
            logger.error(f"关联分析失败: {e}")
            return issues
    
    def _are_issues_related(self, issue1: DiagnosticResult, issue2: DiagnosticResult) -> bool:
        """判断两个问题是否相关"""
        # 时间相关性
        time_diff = abs((issue1.detected_at - issue2.detected_at).total_seconds())
        if time_diff > 300:  # 超过5分钟认为不相关
            return False
        
        # 类别相关性
        if issue1.category == issue2.category:
            return True
        
        # 特定关联规则
        related_combinations = {
            ('high_cpu_usage', 'response_time_degradation'),
            ('memory_leak', 'high_cpu_usage'),
            ('connection_pool_exhaustion', 'database_slowdown'),
            ('disk_space_exhaustion', 'error_rate_spike')
        }
        
        issue_pair = (issue1.title.lower().replace(' ', '_'), 
                     issue2.title.lower().replace(' ', '_'))
        
        return issue_pair in related_combinations or issue_pair[::-1] in related_combinations
    
    def _create_composite_issue(self, related_issues: List[DiagnosticResult]) -> DiagnosticResult:
        """创建综合问题分析"""
        # 选择最严重的问题作为主要问题
        primary_issue = max(related_issues, 
                          key=lambda x: {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}.get(x.severity, 0))
        
        # 合并相关信息
        all_root_causes = []
        all_recommendations = []
        all_evidence = {}
        
        for issue in related_issues:
            all_root_causes.extend(issue.root_causes)
            all_recommendations.extend(issue.recommendations)
            all_evidence.update(issue.evidence)
        
        # 去重
        unique_root_causes = list(dict.fromkeys(all_root_causes))
        unique_recommendations = list(dict.fromkeys(all_recommendations))
        
        # 创建综合问题
        composite_issue = DiagnosticResult(
            issue_id=f"composite_{int(datetime.now().timestamp())}",
            severity=primary_issue.severity,
            category='composite',
            title=f"复合问题: {', '.join([issue.title for issue in related_issues])}",
            description=f"检测到 {len(related_issues)} 个相关问题，可能存在连锁反应",
            impact="多个系统组件受影响，需要综合处理",
            root_causes=unique_root_causes,
            recommendations=unique_recommendations,
            confidence=min(0.95, sum(issue.confidence for issue in related_issues) / len(related_issues)),
            detected_at=min(issue.detected_at for issue in related_issues),
            evidence={
                **all_evidence,
                'related_issues': [issue.issue_id for issue in related_issues],
                'issue_count': len(related_issues)
            }
        )
        
        return composite_issue
    
    def get_diagnostic_summary(self) -> Dict[str, Any]:
        """获取诊断摘要"""
        try:
            issues_by_severity = Counter(issue.severity for issue in self.detected_issues)
            issues_by_category = Counter(issue.category for issue in self.detected_issues)
            
            return {
                'total_issues': len(self.detected_issues),
                'issues_by_severity': dict(issues_by_severity),
                'issues_by_category': dict(issues_by_category),
                'high_confidence_issues': len([i for i in self.detected_issues if i.confidence > 0.8]),
                'anomalies_detected': len(self.anomaly_history),
                'last_analysis': max([i.detected_at for i in self.detected_issues]).isoformat() if self.detected_issues else None
            }
        except Exception as e:
            logger.error(f"获取诊断摘要失败: {e}")
            return {'error': str(e)}
    
    def export_diagnostic_report(self, filepath: str):
        """导出诊断报告"""
        try:
            report_data = {
                'generated_at': datetime.now().isoformat(),
                'summary': self.get_diagnostic_summary(),
                'detected_issues': [issue.to_dict() for issue in self.detected_issues],
                'anomaly_history': [
                    {
                        'metric_name': anomaly.metric_name,
                        'anomaly_type': anomaly.anomaly_type,
                        'severity': anomaly.severity,
                        'timestamp': anomaly.timestamp.isoformat(),
                        'value': anomaly.value,
                        'baseline': anomaly.baseline,
                        'deviation': anomaly.deviation
                    }
                    for anomaly in self.anomaly_history[-100:]  # 最近100个异常
                ]
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"诊断报告已导出到: {filepath}")
            
        except Exception as e:
            logger.error(f"导出诊断报告失败: {e}")


# 使用示例
async def example_usage():
    """使用示例"""
    
    # 创建配置
    config = {
        'diagnostic_analyzer': {
            'analysis_window_minutes': 60,
            'enable_root_cause_analysis': True,
            'confidence_threshold': 0.6
        }
    }
    
    # 创建诊断分析器
    analyzer = DiagnosticAnalyzer(config)
    
    # 模拟指标数据
    system_metrics = []  # 实际使用时从SystemMonitor获取
    application_metrics = []  # 实际使用时从应用获取
    
    # 执行诊断分析
    issues = await analyzer.analyze_system_health(system_metrics, application_metrics)
    
    # 输出结果
    for issue in issues:
        print(f"问题: {issue.title}")
        print(f"严重程度: {issue.severity}")
        print(f"置信度: {issue.confidence:.2f}")
        print(f"描述: {issue.description}")
        print("---")
    
    # 获取诊断摘要
    summary = analyzer.get_diagnostic_summary()
    print("诊断摘要:", summary)
    
    # 导出报告
    analyzer.export_diagnostic_report("diagnostic_report.json")


if __name__ == '__main__':
    asyncio.run(example_usage())