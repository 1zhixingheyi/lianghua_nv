"""
健康检查调度器

定期执行系统健康检查并生成报告
"""

import asyncio
import logging
import json
import schedule
import threading
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validation import SystemChecker, PerformanceAnalyzer
from scripts.mvp_validation_runner import MVPValidationRunner

logger = logging.getLogger(__name__)


class HealthCheckResult:
    """健康检查结果"""
    
    def __init__(self):
        self.timestamp = datetime.now()
        self.overall_status = "unknown"
        self.component_statuses = {}
        self.performance_metrics = {}
        self.issues = []
        self.warnings = []
        self.recommendations = []
        self.trend_analysis = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'overall_status': self.overall_status,
            'component_statuses': self.component_statuses,
            'performance_metrics': self.performance_metrics,
            'issues': self.issues,
            'warnings': self.warnings,
            'recommendations': self.recommendations,
            'trend_analysis': self.trend_analysis
        }


class HealthCheckScheduler:
    """健康检查调度器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 调度配置
        self.scheduler_config = {
            'quick_check_interval': 5,      # 快速检查间隔（分钟）
            'detailed_check_interval': 30,  # 详细检查间隔（分钟）
            'full_validation_interval': 360, # 完整验证间隔（分钟，6小时）
            'enable_quick_checks': True,
            'enable_detailed_checks': True,
            'enable_full_validation': True,
            'alert_on_failures': True,
            'save_results': True,
            'results_directory': 'health_check_results',
            'max_history_days': 30,
            'notification_config': {
                'email_enabled': False,
                'webhook_enabled': False,
                'log_enabled': True
            },
            'alert_thresholds': {
                'response_time_ms': 2000,
                'cpu_usage_percent': 80,
                'memory_usage_percent': 85,
                'disk_usage_percent': 90,
                'error_rate_percent': 5
            }
        }
        
        # 更新配置
        if 'health_check_scheduler' in config:
            self.scheduler_config.update(config['health_check_scheduler'])
        
        # 初始化组件
        self.system_checker = SystemChecker(config)
        self.performance_analyzer = PerformanceAnalyzer(config)
        self.mvp_runner = MVPValidationRunner(config)
        
        # 调度器状态
        self.is_running = False
        self.scheduler_thread = None
        self.results_history = []
        self.last_full_validation = None
        
        # 确保结果目录存在
        os.makedirs(self.scheduler_config['results_directory'], exist_ok=True)
        
        # 加载历史结果
        self._load_history()
    
    def start(self):
        """启动调度器"""
        if self.is_running:
            logger.warning("调度器已经在运行")
            return
        
        logger.info("启动健康检查调度器")
        
        # 清除之前的调度
        schedule.clear()
        
        # 配置调度任务
        if self.scheduler_config['enable_quick_checks']:
            interval = self.scheduler_config['quick_check_interval']
            schedule.every(interval).minutes.do(self._run_quick_check_sync)
            logger.info(f"快速检查已配置，间隔: {interval} 分钟")
        
        if self.scheduler_config['enable_detailed_checks']:
            interval = self.scheduler_config['detailed_check_interval']
            schedule.every(interval).minutes.do(self._run_detailed_check_sync)
            logger.info(f"详细检查已配置，间隔: {interval} 分钟")
        
        if self.scheduler_config['enable_full_validation']:
            interval = self.scheduler_config['full_validation_interval']
            schedule.every(interval).minutes.do(self._run_full_validation_sync)
            logger.info(f"完整验证已配置，间隔: {interval} 分钟")
        
        # 启动调度器线程
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        # 立即执行一次快速检查
        self._run_quick_check_sync()
        
        logger.info("健康检查调度器已启动")
    
    def stop(self):
        """停止调度器"""
        if not self.is_running:
            logger.warning("调度器未在运行")
            return
        
        logger.info("停止健康检查调度器")
        
        self.is_running = False
        schedule.clear()
        
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        
        logger.info("健康检查调度器已停止")
    
    def _run_scheduler(self):
        """运行调度器主循环"""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(f"调度器执行异常: {e}")
                time.sleep(5)
    
    def _run_quick_check_sync(self):
        """同步运行快速检查"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.run_quick_check())
            loop.close()
            
            # 处理结果
            self._process_check_result(result, "quick")
            
        except Exception as e:
            logger.error(f"快速检查异常: {e}")
    
    def _run_detailed_check_sync(self):
        """同步运行详细检查"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.run_detailed_check())
            loop.close()
            
            # 处理结果
            self._process_check_result(result, "detailed")
            
        except Exception as e:
            logger.error(f"详细检查异常: {e}")
    
    def _run_full_validation_sync(self):
        """同步运行完整验证"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.run_full_validation())
            loop.close()
            
            # 处理结果
            self._process_check_result(result, "full")
            
        except Exception as e:
            logger.error(f"完整验证异常: {e}")
    
    async def run_quick_check(self) -> HealthCheckResult:
        """运行快速健康检查"""
        logger.info("执行快速健康检查")
        
        result = HealthCheckResult()
        
        try:
            # 检查关键服务状态
            critical_checks = [
                ('database', self.system_checker.check_database_health),
                ('web_service', self.system_checker.check_web_service_health),
                ('data_sources', self.system_checker.check_data_source_health)
            ]
            
            for component, check_func in critical_checks:
                try:
                    status = await check_func()
                    result.component_statuses[component] = status
                except Exception as e:
                    result.component_statuses[component] = {
                        'status': 'error',
                        'error': str(e)
                    }
                    result.issues.append(f"{component} 检查失败: {e}")
            
            # 获取基本性能指标
            try:
                metrics = await self.performance_analyzer.get_current_metrics()
                result.performance_metrics = {
                    'response_time': metrics.get('response_time', {}),
                    'cpu_usage': metrics.get('cpu_usage', 0),
                    'memory_usage': metrics.get('memory_usage', 0)
                }
            except Exception as e:
                result.warnings.append(f"性能指标获取失败: {e}")
            
            # 分析整体状态
            result.overall_status = self._analyze_quick_status(result)
            
            # 生成建议
            result.recommendations = self._generate_quick_recommendations(result)
            
            logger.info(f"快速健康检查完成，状态: {result.overall_status}")
            
        except Exception as e:
            logger.error(f"快速健康检查失败: {e}")
            result.overall_status = "error"
            result.issues.append(f"检查过程异常: {str(e)}")
        
        return result
    
    async def run_detailed_check(self) -> HealthCheckResult:
        """运行详细健康检查"""
        logger.info("执行详细健康检查")
        
        result = HealthCheckResult()
        
        try:
            # 执行所有系统组件检查
            all_checks = [
                ('database', self.system_checker.check_database_health),
                ('web_service', self.system_checker.check_web_service_health),
                ('data_sources', self.system_checker.check_data_source_health),
                ('filesystem', self.system_checker.check_filesystem_health),
                ('network', self.system_checker.check_network_health),
                ('services', self.system_checker.check_service_health)
            ]
            
            for component, check_func in all_checks:
                try:
                    status = await check_func()
                    result.component_statuses[component] = status
                except Exception as e:
                    result.component_statuses[component] = {
                        'status': 'error',
                        'error': str(e)
                    }
                    result.issues.append(f"{component} 检查失败: {e}")
            
            # 获取详细性能指标
            try:
                await self.performance_analyzer.start_monitoring()
                await asyncio.sleep(10)  # 收集10秒数据
                
                metrics = await self.performance_analyzer.get_current_metrics()
                result.performance_metrics = metrics
                
                # 分析性能瓶颈
                bottlenecks = await self.performance_analyzer.analyze_bottlenecks()
                if bottlenecks:
                    for bottleneck in bottlenecks:
                        severity = bottleneck.get('severity', 'info')
                        description = bottleneck.get('description', '')
                        if severity == 'critical':
                            result.issues.append(f"性能瓶颈: {description}")
                        elif severity == 'warning':
                            result.warnings.append(f"性能警告: {description}")
                
                await self.performance_analyzer.stop_monitoring()
                
            except Exception as e:
                result.warnings.append(f"性能分析失败: {e}")
            
            # 检查告警阈值
            self._check_alert_thresholds(result)
            
            # 分析整体状态
            result.overall_status = self._analyze_detailed_status(result)
            
            # 生成趋势分析
            result.trend_analysis = self._generate_trend_analysis(result)
            
            # 生成建议
            result.recommendations = self._generate_detailed_recommendations(result)
            
            logger.info(f"详细健康检查完成，状态: {result.overall_status}")
            
        except Exception as e:
            logger.error(f"详细健康检查失败: {e}")
            result.overall_status = "error"
            result.issues.append(f"检查过程异常: {str(e)}")
        
        return result
    
    async def run_full_validation(self) -> HealthCheckResult:
        """运行完整验证"""
        logger.info("执行完整MVP验证")
        
        result = HealthCheckResult()
        
        try:
            # 运行完整MVP验证
            validation_result = await self.mvp_runner.run_full_validation()
            
            # 转换验证结果
            result.overall_status = validation_result.overall_status
            result.issues = validation_result.critical_issues
            result.warnings = validation_result.warnings
            result.recommendations = validation_result.recommendations
            
            # 提取组件状态
            if validation_result.system_health:
                result.component_statuses = validation_result.system_health
            
            # 提取性能指标
            if validation_result.performance_analysis:
                result.performance_metrics = validation_result.performance_analysis.get('metrics', {})
            
            # 记录最后一次完整验证时间
            self.last_full_validation = datetime.now()
            
            logger.info(f"完整验证完成，状态: {result.overall_status}")
            
        except Exception as e:
            logger.error(f"完整验证失败: {e}")
            result.overall_status = "error"
            result.issues.append(f"验证过程异常: {str(e)}")
        
        return result
    
    def _analyze_quick_status(self, result: HealthCheckResult) -> str:
        """分析快速检查状态"""
        if result.issues:
            return "unhealthy"
        
        # 检查关键组件
        for component, status in result.component_statuses.items():
            if isinstance(status, dict):
                component_status = status.get('status', 'unknown')
                if component_status in ['unhealthy', 'error']:
                    return "unhealthy"
                elif component_status == 'degraded':
                    return "degraded"
        
        if result.warnings:
            return "degraded"
        
        return "healthy"
    
    def _analyze_detailed_status(self, result: HealthCheckResult) -> str:
        """分析详细检查状态"""
        critical_issues = 0
        degraded_components = 0
        
        # 计算问题严重程度
        for issue in result.issues:
            if any(keyword in issue.lower() for keyword in ['critical', 'failed', 'error']):
                critical_issues += 1
        
        # 检查组件状态
        for component, status in result.component_statuses.items():
            if isinstance(status, dict):
                component_status = status.get('status', 'unknown')
                if component_status in ['unhealthy', 'error']:
                    critical_issues += 1
                elif component_status == 'degraded':
                    degraded_components += 1
        
        # 判断总体状态
        if critical_issues >= 2:
            return "critical"
        elif critical_issues == 1:
            return "unhealthy"
        elif degraded_components > 0 or result.warnings:
            return "degraded"
        else:
            return "healthy"
    
    def _check_alert_thresholds(self, result: HealthCheckResult):
        """检查告警阈值"""
        thresholds = self.scheduler_config['alert_thresholds']
        metrics = result.performance_metrics
        
        # 检查响应时间
        response_time = metrics.get('response_time', {}).get('avg', 0)
        if response_time > thresholds['response_time_ms'] / 1000:
            result.warnings.append(f"响应时间过高: {response_time:.2f}s")
        
        # 检查CPU使用率
        cpu_usage = metrics.get('cpu_usage', 0)
        if cpu_usage > thresholds['cpu_usage_percent']:
            result.warnings.append(f"CPU使用率过高: {cpu_usage:.1f}%")
        
        # 检查内存使用率
        memory_usage = metrics.get('memory_usage', 0)
        if memory_usage > thresholds['memory_usage_percent']:
            result.warnings.append(f"内存使用率过高: {memory_usage:.1f}%")
        
        # 检查磁盘使用率
        disk_usage = metrics.get('disk_usage', 0)
        if disk_usage > thresholds['disk_usage_percent']:
            result.issues.append(f"磁盘使用率过高: {disk_usage:.1f}%")
        
        # 检查错误率
        error_rate = metrics.get('error_rate', 0) * 100
        if error_rate > thresholds['error_rate_percent']:
            result.issues.append(f"错误率过高: {error_rate:.1f}%")
    
    def _generate_trend_analysis(self, result: HealthCheckResult) -> Dict[str, Any]:
        """生成趋势分析"""
        trend_analysis = {}
        
        try:
            # 获取历史数据进行趋势分析
            if len(self.results_history) >= 3:
                recent_results = self.results_history[-3:]
                
                # CPU使用率趋势
                cpu_values = [r.get('performance_metrics', {}).get('cpu_usage', 0) 
                             for r in recent_results]
                if cpu_values:
                    trend_analysis['cpu_trend'] = self._calculate_trend(cpu_values)
                
                # 内存使用率趋势
                memory_values = [r.get('performance_metrics', {}).get('memory_usage', 0) 
                               for r in recent_results]
                if memory_values:
                    trend_analysis['memory_trend'] = self._calculate_trend(memory_values)
                
                # 响应时间趋势
                response_time_values = [
                    r.get('performance_metrics', {}).get('response_time', {}).get('avg', 0)
                    for r in recent_results
                ]
                if response_time_values:
                    trend_analysis['response_time_trend'] = self._calculate_trend(response_time_values)
        
        except Exception as e:
            logger.error(f"生成趋势分析失败: {e}")
        
        return trend_analysis
    
    def _calculate_trend(self, values: List[float]) -> Dict[str, Any]:
        """计算趋势"""
        if len(values) < 2:
            return {'direction': 'stable', 'change_rate': 0}
        
        # 计算简单线性趋势
        recent_avg = sum(values[-2:]) / 2
        earlier_avg = sum(values[:-2]) / max(len(values) - 2, 1)
        
        change_rate = ((recent_avg - earlier_avg) / max(earlier_avg, 0.01)) * 100
        
        if change_rate > 5:
            direction = 'increasing'
        elif change_rate < -5:
            direction = 'decreasing'
        else:
            direction = 'stable'
        
        return {
            'direction': direction,
            'change_rate': change_rate,
            'current_value': values[-1] if values else 0,
            'previous_value': values[-2] if len(values) > 1 else 0
        }
    
    def _generate_quick_recommendations(self, result: HealthCheckResult) -> List[str]:
        """生成快速检查建议"""
        recommendations = []
        
        if result.issues:
            recommendations.append("发现关键问题，建议立即进行详细检查")
        
        if result.warnings:
            recommendations.append("存在警告项目，建议监控相关指标")
        
        if result.overall_status == "healthy":
            recommendations.append("系统运行正常")
        
        return recommendations
    
    def _generate_detailed_recommendations(self, result: HealthCheckResult) -> List[str]:
        """生成详细检查建议"""
        recommendations = []
        
        # 基于状态的建议
        if result.overall_status == "critical":
            recommendations.append("系统处于危险状态，建议立即采取行动")
        elif result.overall_status == "unhealthy":
            recommendations.append("系统存在健康问题，建议尽快修复")
        elif result.overall_status == "degraded":
            recommendations.append("系统性能下降，建议优化相关组件")
        
        # 基于趋势的建议
        trends = result.trend_analysis
        for metric, trend in trends.items():
            if trend.get('direction') == 'increasing' and trend.get('change_rate', 0) > 10:
                recommendations.append(f"{metric}呈上升趋势，建议关注")
        
        # 基于性能指标的建议
        metrics = result.performance_metrics
        if metrics.get('memory_usage', 0) > 80:
            recommendations.append("内存使用率较高，考虑增加内存或优化内存使用")
        
        if metrics.get('cpu_usage', 0) > 70:
            recommendations.append("CPU使用率较高，考虑优化计算密集型操作")
        
        return recommendations
    
    def _process_check_result(self, result: HealthCheckResult, check_type: str):
        """处理检查结果"""
        try:
            # 添加到历史记录
            result_dict = result.to_dict()
            result_dict['check_type'] = check_type
            self.results_history.append(result_dict)
            
            # 保存结果
            if self.scheduler_config['save_results']:
                self._save_result(result, check_type)
            
            # 发送告警
            if (self.scheduler_config['alert_on_failures'] and 
                result.overall_status in ['unhealthy', 'critical', 'error']):
                self._send_alert(result, check_type)
            
            # 清理老旧历史
            self._cleanup_history()
            
        except Exception as e:
            logger.error(f"处理检查结果失败: {e}")
    
    def _save_result(self, result: HealthCheckResult, check_type: str):
        """保存检查结果"""
        try:
            timestamp = result.timestamp.strftime("%Y%m%d_%H%M%S")
            filename = f"health_check_{check_type}_{timestamp}.json"
            filepath = os.path.join(self.scheduler_config['results_directory'], filename)
            
            result_dict = result.to_dict()
            result_dict['check_type'] = check_type
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result_dict, f, indent=2, ensure_ascii=False)
            
            # 更新最新结果文件
            latest_filepath = os.path.join(
                self.scheduler_config['results_directory'], 
                f"latest_{check_type}_check.json"
            )
            with open(latest_filepath, 'w', encoding='utf-8') as f:
                json.dump(result_dict, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"保存检查结果失败: {e}")
    
    def _send_alert(self, result: HealthCheckResult, check_type: str):
        """发送告警"""
        try:
            alert_message = f"健康检查告警 - {check_type.upper()}"
            alert_details = [
                f"时间: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
                f"状态: {result.overall_status.upper()}",
                f"问题数量: {len(result.issues)}"
            ]
            
            if result.issues:
                alert_details.append("关键问题:")
                alert_details.extend([f"  • {issue}" for issue in result.issues[:3]])
                if len(result.issues) > 3:
                    alert_details.append(f"  ... 还有 {len(result.issues) - 3} 个问题")
            
            alert_text = "\n".join([alert_message] + alert_details)
            
            # 记录到日志
            if self.scheduler_config['notification_config']['log_enabled']:
                logger.warning(alert_text)
            
            # 其他告警方式（邮件、Webhook等）可以在这里添加
            
        except Exception as e:
            logger.error(f"发送告警失败: {e}")
    
    def _load_history(self):
        """加载历史结果"""
        try:
            results_dir = self.scheduler_config['results_directory']
            if not os.path.exists(results_dir):
                return
            
            # 加载最近的结果文件
            for filename in os.listdir(results_dir):
                if filename.startswith('health_check_') and filename.endswith('.json'):
                    filepath = os.path.join(results_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            result_data = json.load(f)
                            self.results_history.append(result_data)
                    except Exception as e:
                        logger.warning(f"加载历史结果文件失败 {filename}: {e}")
            
            # 按时间排序
            self.results_history.sort(key=lambda x: x.get('timestamp', ''))
            
            # 限制历史记录数量
            max_history = self.scheduler_config['max_history_days'] * 24 * 60 // 5  # 假设5分钟一次检查
            if len(self.results_history) > max_history:
                self.results_history = self.results_history[-max_history:]
                
        except Exception as e:
            logger.error(f"加载历史结果失败: {e}")
    
    def _cleanup_history(self):
        """清理历史记录"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.scheduler_config['max_history_days'])
            cutoff_str = cutoff_date.isoformat()
            
            # 清理内存中的历史记录
            self.results_history = [
                result for result in self.results_history
                if result.get('timestamp', '') > cutoff_str
            ]
            
            # 清理文件系统中的历史文件
            results_dir = self.scheduler_config['results_directory']
            if os.path.exists(results_dir):
                for filename in os.listdir(results_dir):
                    if (filename.startswith('health_check_') and 
                        filename.endswith('.json') and 
                        not filename.startswith('latest_')):
                        
                        filepath = os.path.join(results_dir, filename)
                        file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                        
                        if file_time < cutoff_date:
                            try:
                                os.remove(filepath)
                                logger.debug(f"已删除过期结果文件: {filename}")
                            except Exception as e:
                                logger.warning(f"删除过期文件失败 {filename}: {e}")
                                
        except Exception as e:
            logger.error(f"清理历史记录失败: {e}")
    
    def get_status_summary(self) -> Dict[str, Any]:
        """获取状态摘要"""
        try:
            latest_result = self.results_history[-1] if self.results_history else None
            
            summary = {
                'scheduler_status': 'running' if self.is_running else 'stopped',
                'last_check_time': latest_result.get('timestamp') if latest_result else None,
                'last_check_status': latest_result.get('overall_status') if latest_result else 'unknown',
                'total_checks': len(self.results_history),
                'last_full_validation': self.last_full_validation.isoformat() if self.last_full_validation else None,
                'recent_issues': 0,
                'recent_warnings': 0
            }
            
            # 统计最近的问题和警告
            recent_cutoff = datetime.now() - timedelta(hours=1)
            recent_cutoff_str = recent_cutoff.isoformat()
            
            for result in self.results_history:
                if result.get('timestamp', '') > recent_cutoff_str:
                    summary['recent_issues'] += len(result.get('issues', []))
                    summary['recent_warnings'] += len(result.get('warnings', []))
            
            return summary
            
        except Exception as e:
            logger.error(f"获取状态摘要失败: {e}")
            return {'error': str(e)}


async def main():
    """主函数 - 命令行执行"""
    import argparse
    
    parser = argparse.ArgumentParser(description='健康检查调度器')
    parser.add_argument('--config', '-c', default='config.json', help='配置文件路径')
    parser.add_argument('--daemon', '-d', action='store_true', help='后台运行模式')
    parser.add_argument('--once', '-o', action='store_true', help='只运行一次检查')
    parser.add_argument('--type', '-t', choices=['quick', 'detailed', 'full'], 
                       default='quick', help='检查类型')
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
        
        # 创建调度器
        scheduler = HealthCheckScheduler(config)
        
        if args.once:
            # 只运行一次检查
            if args.type == 'quick':
                result = await scheduler.run_quick_check()
            elif args.type == 'detailed':
                result = await scheduler.run_detailed_check()
            elif args.type == 'full':
                result = await scheduler.run_full_validation()
            
            print(f"检查完成，状态: {result.overall_status}")
            if result.issues:
                print("关键问题:")
                for issue in result.issues:
                    print(f"  • {issue}")
            
            if result.warnings:
                print("警告:")
                for warning in result.warnings[:3]:
                    print(f"  • {warning}")
            
        elif args.daemon:
            # 后台运行模式
            scheduler.start()
            
            try:
                while True:
                    await asyncio.sleep(60)
                    summary = scheduler.get_status_summary()
                    logger.info(f"调度器状态: {summary}")
            except KeyboardInterrupt:
                logger.info("收到停止信号")
            finally:
                scheduler.stop()
        
        else:
            # 交互模式
            scheduler.start()
            
            try:
                print("健康检查调度器已启动")
                print("按 Ctrl+C 停止")
                
                while True:
                    await asyncio.sleep(30)
                    summary = scheduler.get_status_summary()
                    print(f"状态: {summary['last_check_status']}, "
                          f"问题: {summary['recent_issues']}, "
                          f"警告: {summary['recent_warnings']}")
                    
            except KeyboardInterrupt:
                print("\n正在停止调度器...")
            finally:
                scheduler.stop()
                print("调度器已停止")
                
    except Exception as e:
        logger.error(f"执行失败: {e}")
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())