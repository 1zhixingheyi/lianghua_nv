"""
MVP验证运行器

自动化运行完整的MVP验证流程
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validation import MVPValidator, PerformanceAnalyzer, SystemChecker, BenchmarkRunner
from optimization import DatabaseOptimizer, CacheManager, MemoryOptimizer, ConfigTuner

logger = logging.getLogger(__name__)


class ValidationResult:
    """验证结果"""
    
    def __init__(self):
        self.mvp_validation = None
        self.performance_analysis = None
        self.system_health = None
        self.benchmark_results = None
        self.optimization_suggestions = None
        self.overall_status = "unknown"
        self.critical_issues = []
        self.warnings = []
        self.recommendations = []
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'mvp_validation': self.mvp_validation,
            'performance_analysis': self.performance_analysis,
            'system_health': self.system_health,
            'benchmark_results': self.benchmark_results,
            'optimization_suggestions': self.optimization_suggestions,
            'overall_status': self.overall_status,
            'critical_issues': self.critical_issues,
            'warnings': self.warnings,
            'recommendations': self.recommendations,
            'timestamp': self.timestamp.isoformat()
        }


class MVPValidationRunner:
    """MVP验证运行器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 验证配置
        self.validation_config = {
            'run_full_validation': True,
            'run_performance_analysis': True,
            'run_system_health_check': True,
            'run_benchmarks': True,
            'generate_optimization_suggestions': True,
            'auto_apply_optimizations': False,
            'fail_on_critical_issues': True,
            'save_results': True,
            'results_directory': 'validation_results',
            'validation_criteria': {
                'min_success_rate': 0.95,
                'max_response_time': 2.0,
                'max_error_rate': 0.05,
                'min_availability': 0.99
            },
            'benchmark_suites': [
                'data_processing',
                'trading_operations',
                'database_operations',
                'cache_operations'
            ]
        }
        
        # 更新配置
        if 'mvp_validation' in config:
            self.validation_config.update(config['mvp_validation'])
        
        # 初始化组件
        self.mvp_validator = MVPValidator(config)
        self.performance_analyzer = PerformanceAnalyzer(config)
        self.system_checker = SystemChecker(config)
        self.benchmark_runner = BenchmarkRunner(config)
        
        # 优化器
        self.database_optimizer = DatabaseOptimizer(config)
        self.cache_manager = CacheManager(config)
        self.memory_optimizer = MemoryOptimizer(config)
        self.config_tuner = ConfigTuner(config)
        
        # 确保结果目录存在
        os.makedirs(self.validation_config['results_directory'], exist_ok=True)
    
    async def run_full_validation(self) -> ValidationResult:
        """运行完整验证流程"""
        logger.info("开始MVP完整验证流程")
        
        result = ValidationResult()
        
        try:
            # 1. MVP基础验证
            if self.validation_config['run_full_validation']:
                logger.info("执行MVP基础验证...")
                result.mvp_validation = await self._run_mvp_validation()
            
            # 2. 性能分析
            if self.validation_config['run_performance_analysis']:
                logger.info("执行性能分析...")
                result.performance_analysis = await self._run_performance_analysis()
            
            # 3. 系统健康检查
            if self.validation_config['run_system_health_check']:
                logger.info("执行系统健康检查...")
                result.system_health = await self._run_system_health_check()
            
            # 4. 基准测试
            if self.validation_config['run_benchmarks']:
                logger.info("执行基准测试...")
                result.benchmark_results = await self._run_benchmarks()
            
            # 5. 生成优化建议
            if self.validation_config['generate_optimization_suggestions']:
                logger.info("生成优化建议...")
                result.optimization_suggestions = await self._generate_optimization_suggestions()
            
            # 6. 分析总体状态
            result.overall_status = self._analyze_overall_status(result)
            
            # 7. 生成关键问题和建议
            result.critical_issues = self._extract_critical_issues(result)
            result.warnings = self._extract_warnings(result)
            result.recommendations = self._generate_recommendations(result)
            
            # 8. 保存结果
            if self.validation_config['save_results']:
                await self._save_results(result)
            
            # 9. 检查是否需要失败
            if (self.validation_config['fail_on_critical_issues'] and 
                result.critical_issues and 
                result.overall_status in ['failed', 'critical']):
                logger.error(f"验证失败，发现 {len(result.critical_issues)} 个关键问题")
                raise RuntimeError(f"MVP验证失败: {', '.join(result.critical_issues)}")
            
            logger.info(f"MVP验证完成，总体状态: {result.overall_status}")
            
        except Exception as e:
            logger.error(f"MVP验证失败: {e}")
            result.overall_status = "failed"
            result.critical_issues.append(f"验证过程异常: {str(e)}")
            raise
        
        return result
    
    async def _run_mvp_validation(self) -> Dict[str, Any]:
        """运行MVP验证"""
        try:
            # 技术指标验证
            technical_results = await self.mvp_validator.validate_technical_metrics()
            
            # 业务指标验证
            business_results = await self.mvp_validator.validate_business_metrics()
            
            # 稳定性验证
            stability_results = await self.mvp_validator.validate_stability()
            
            # 用户体验验证
            ux_results = await self.mvp_validator.validate_user_experience()
            
            return {
                'technical_metrics': technical_results,
                'business_metrics': business_results,
                'stability': stability_results,
                'user_experience': ux_results,
                'status': 'completed'
            }
            
        except Exception as e:
            logger.error(f"MVP验证失败: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _run_performance_analysis(self) -> Dict[str, Any]:
        """运行性能分析"""
        try:
            # 启动性能监控
            await self.performance_analyzer.start_monitoring()
            
            # 等待收集足够的数据
            await asyncio.sleep(30)
            
            # 获取性能指标
            metrics = await self.performance_analyzer.get_current_metrics()
            
            # 分析性能瓶颈
            bottlenecks = await self.performance_analyzer.analyze_bottlenecks()
            
            # 生成性能报告
            report = self.performance_analyzer.generate_performance_report()
            
            # 停止监控
            await self.performance_analyzer.stop_monitoring()
            
            return {
                'metrics': metrics,
                'bottlenecks': bottlenecks,
                'report': report,
                'status': 'completed'
            }
            
        except Exception as e:
            logger.error(f"性能分析失败: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _run_system_health_check(self) -> Dict[str, Any]:
        """运行系统健康检查"""
        try:
            # 数据库检查
            db_health = await self.system_checker.check_database_health()
            
            # Web服务检查
            web_health = await self.system_checker.check_web_service_health()
            
            # 数据源检查
            datasource_health = await self.system_checker.check_data_source_health()
            
            # 文件系统检查
            filesystem_health = await self.system_checker.check_filesystem_health()
            
            # 网络检查
            network_health = await self.system_checker.check_network_health()
            
            # 服务检查
            service_health = await self.system_checker.check_service_health()
            
            return {
                'database': db_health,
                'web_service': web_health,
                'data_sources': datasource_health,
                'filesystem': filesystem_health,
                'network': network_health,
                'services': service_health,
                'status': 'completed'
            }
            
        except Exception as e:
            logger.error(f"系统健康检查失败: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _run_benchmarks(self) -> Dict[str, Any]:
        """运行基准测试"""
        try:
            results = {}
            
            for suite in self.validation_config['benchmark_suites']:
                logger.info(f"运行基准测试套件: {suite}")
                
                if suite == 'data_processing':
                    results[suite] = await self.benchmark_runner.run_data_processing_benchmark()
                elif suite == 'trading_operations':
                    results[suite] = await self.benchmark_runner.run_trading_benchmark()
                elif suite == 'database_operations':
                    results[suite] = await self.benchmark_runner.run_database_benchmark()
                elif suite == 'cache_operations':
                    results[suite] = await self.benchmark_runner.run_cache_benchmark()
            
            return {
                'results': results,
                'status': 'completed'
            }
            
        except Exception as e:
            logger.error(f"基准测试失败: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _generate_optimization_suggestions(self) -> Dict[str, Any]:
        """生成优化建议"""
        try:
            suggestions = {}
            
            # 数据库优化建议
            logger.info("分析数据库优化机会...")
            db_suggestions = await self.database_optimizer.analyze_and_optimize()
            suggestions['database'] = db_suggestions
            
            # 缓存优化建议
            logger.info("分析缓存优化机会...")
            cache_suggestions = await self.cache_manager.optimize_cache_strategy()
            suggestions['cache'] = cache_suggestions
            
            # 内存优化建议
            logger.info("分析内存优化机会...")
            memory_suggestions = await self.memory_optimizer.analyze_and_optimize()
            suggestions['memory'] = memory_suggestions
            
            # 配置优化建议
            logger.info("分析配置优化机会...")
            config_suggestions = await self.config_tuner.analyze_and_optimize()
            suggestions['config'] = config_suggestions
            
            return {
                'suggestions': suggestions,
                'status': 'completed'
            }
            
        except Exception as e:
            logger.error(f"生成优化建议失败: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _analyze_overall_status(self, result: ValidationResult) -> str:
        """分析总体状态"""
        try:
            criteria = self.validation_config['validation_criteria']
            issues = []
            warnings = []
            
            # 检查MVP验证结果
            if result.mvp_validation and result.mvp_validation.get('status') == 'failed':
                issues.append("MVP基础验证失败")
            
            # 检查性能指标
            if result.performance_analysis and result.performance_analysis.get('status') == 'completed':
                metrics = result.performance_analysis.get('metrics', {})
                
                # 检查响应时间
                avg_response_time = metrics.get('response_time', {}).get('avg', 0)
                if avg_response_time > criteria['max_response_time']:
                    issues.append(f"响应时间过高: {avg_response_time:.2f}s > {criteria['max_response_time']}s")
                
                # 检查错误率
                error_rate = metrics.get('error_rate', 0)
                if error_rate > criteria['max_error_rate']:
                    issues.append(f"错误率过高: {error_rate:.2%} > {criteria['max_error_rate']:.2%}")
            
            # 检查系统健康
            if result.system_health and result.system_health.get('status') == 'completed':
                for component, health in result.system_health.items():
                    if isinstance(health, dict) and health.get('status') == 'unhealthy':
                        issues.append(f"系统组件不健康: {component}")
            
            # 检查基准测试
            if result.benchmark_results and result.benchmark_results.get('status') == 'completed':
                benchmark_results = result.benchmark_results.get('results', {})
                for suite, suite_result in benchmark_results.items():
                    if isinstance(suite_result, dict):
                        success_rate = suite_result.get('success_rate', 0)
                        if success_rate < criteria['min_success_rate']:
                            issues.append(f"基准测试 {suite} 成功率过低: {success_rate:.2%}")
            
            # 判断总体状态
            if issues:
                if len(issues) >= 3 or any("失败" in issue for issue in issues):
                    return "critical"
                else:
                    return "failed"
            elif warnings:
                return "warning"
            else:
                return "passed"
                
        except Exception as e:
            logger.error(f"分析总体状态失败: {e}")
            return "unknown"
    
    def _extract_critical_issues(self, result: ValidationResult) -> List[str]:
        """提取关键问题"""
        issues = []
        
        try:
            # MVP验证问题
            if result.mvp_validation and result.mvp_validation.get('status') == 'failed':
                issues.append("MVP基础验证失败")
            
            # 性能问题
            if result.performance_analysis and result.performance_analysis.get('status') == 'completed':
                bottlenecks = result.performance_analysis.get('bottlenecks', [])
                critical_bottlenecks = [b for b in bottlenecks if b.get('severity') == 'critical']
                for bottleneck in critical_bottlenecks:
                    issues.append(f"关键性能瓶颈: {bottleneck.get('description', '')}")
            
            # 系统健康问题
            if result.system_health and result.system_health.get('status') == 'completed':
                for component, health in result.system_health.items():
                    if isinstance(health, dict) and health.get('status') == 'unhealthy':
                        if health.get('severity') == 'critical':
                            issues.append(f"关键系统组件故障: {component}")
            
        except Exception as e:
            logger.error(f"提取关键问题失败: {e}")
            issues.append(f"问题分析异常: {str(e)}")
        
        return issues
    
    def _extract_warnings(self, result: ValidationResult) -> List[str]:
        """提取警告"""
        warnings = []
        
        try:
            # 性能警告
            if result.performance_analysis and result.performance_analysis.get('status') == 'completed':
                bottlenecks = result.performance_analysis.get('bottlenecks', [])
                warning_bottlenecks = [b for b in bottlenecks if b.get('severity') == 'warning']
                for bottleneck in warning_bottlenecks:
                    warnings.append(f"性能警告: {bottleneck.get('description', '')}")
            
            # 系统健康警告
            if result.system_health and result.system_health.get('status') == 'completed':
                for component, health in result.system_health.items():
                    if isinstance(health, dict) and health.get('status') == 'degraded':
                        warnings.append(f"系统组件性能下降: {component}")
            
            # 优化建议中的警告
            if result.optimization_suggestions and result.optimization_suggestions.get('status') == 'completed':
                suggestions = result.optimization_suggestions.get('suggestions', {})
                for category, category_suggestions in suggestions.items():
                    if isinstance(category_suggestions, dict):
                        category_warnings = category_suggestions.get('warnings', [])
                        warnings.extend([f"{category}: {w}" for w in category_warnings])
        
        except Exception as e:
            logger.error(f"提取警告失败: {e}")
        
        return warnings
    
    def _generate_recommendations(self, result: ValidationResult) -> List[str]:
        """生成建议"""
        recommendations = []
        
        try:
            # 基于总体状态的建议
            if result.overall_status == "critical":
                recommendations.append("系统存在关键问题，建议立即停止生产使用并进行修复")
            elif result.overall_status == "failed":
                recommendations.append("系统存在重要问题，建议在修复后再投入生产使用")
            elif result.overall_status == "warning":
                recommendations.append("系统基本可用，但建议优化警告项目以提升稳定性")
            elif result.overall_status == "passed":
                recommendations.append("系统验证通过，可以投入生产使用")
            
            # 优化建议
            if result.optimization_suggestions and result.optimization_suggestions.get('status') == 'completed':
                suggestions = result.optimization_suggestions.get('suggestions', {})
                for category, category_suggestions in suggestions.items():
                    if isinstance(category_suggestions, dict):
                        category_recommendations = category_suggestions.get('recommendations', [])
                        recommendations.extend([f"{category}优化: {r}" for r in category_recommendations])
            
            # 通用建议
            recommendations.extend([
                "建议定期进行MVP验证以确保系统持续健康",
                "建议建立性能监控和告警机制",
                "建议制定系统容量规划和扩展策略",
                "建议定期备份关键数据和配置"
            ])
        
        except Exception as e:
            logger.error(f"生成建议失败: {e}")
        
        return recommendations
    
    async def _save_results(self, result: ValidationResult):
        """保存验证结果"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"mvp_validation_{timestamp}.json"
            filepath = os.path.join(self.validation_config['results_directory'], filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
            
            logger.info(f"验证结果已保存到: {filepath}")
            
            # 同时保存最新结果
            latest_filepath = os.path.join(self.validation_config['results_directory'], "latest_validation.json")
            with open(latest_filepath, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"保存验证结果失败: {e}")
    
    def generate_summary_report(self, result: ValidationResult) -> str:
        """生成摘要报告"""
        report_lines = [
            "=" * 60,
            "MVP验证摘要报告",
            "=" * 60,
            f"验证时间: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"总体状态: {result.overall_status.upper()}",
            ""
        ]
        
        # 关键问题
        if result.critical_issues:
            report_lines.extend([
                "关键问题:",
                "-" * 20
            ])
            for issue in result.critical_issues:
                report_lines.append(f"• {issue}")
            report_lines.append("")
        
        # 警告
        if result.warnings:
            report_lines.extend([
                "警告:",
                "-" * 20
            ])
            for warning in result.warnings[:5]:  # 只显示前5个警告
                report_lines.append(f"• {warning}")
            if len(result.warnings) > 5:
                report_lines.append(f"... 还有 {len(result.warnings) - 5} 个警告")
            report_lines.append("")
        
        # 建议
        if result.recommendations:
            report_lines.extend([
                "建议:",
                "-" * 20
            ])
            for recommendation in result.recommendations[:5]:  # 只显示前5个建议
                report_lines.append(f"• {recommendation}")
            if len(result.recommendations) > 5:
                report_lines.append(f"... 还有 {len(result.recommendations) - 5} 个建议")
            report_lines.append("")
        
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)


async def main():
    """主函数 - 命令行执行"""
    import argparse
    
    parser = argparse.ArgumentParser(description='MVP验证运行器')
    parser.add_argument('--config', '-c', default='config.json', help='配置文件路径')
    parser.add_argument('--output', '-o', help='结果输出文件路径')
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
        runner = MVPValidationRunner(config)
        
        # 运行验证
        result = await runner.run_full_validation()
        
        # 输出摘要报告
        summary = runner.generate_summary_report(result)
        print(summary)
        
        # 保存结果到指定文件
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
            print(f"\n详细结果已保存到: {args.output}")
        
        # 根据验证结果设置退出码
        if result.overall_status in ['failed', 'critical']:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"执行失败: {e}")
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())