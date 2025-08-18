"""
配置调优器

负责优化系统配置参数，提升系统性能
"""

import asyncio
import logging
import json
import os
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
import copy
import math

logger = logging.getLogger(__name__)


class ConfigParameter:
    """配置参数"""
    
    def __init__(self, name: str, current_value: Any, param_type: str = 'auto'):
        self.name = name
        self.current_value = current_value
        self.param_type = param_type  # int, float, bool, str, auto
        self.suggested_value = None
        self.impact_score = 0.0
        self.optimization_reason = ""
        self.valid_range = None
        self.dependencies = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'name': self.name,
            'current_value': self.current_value,
            'suggested_value': self.suggested_value,
            'param_type': self.param_type,
            'impact_score': self.impact_score,
            'optimization_reason': self.optimization_reason,
            'valid_range': self.valid_range
        }


class ConfigOptimizationResult:
    """配置优化结果"""
    
    def __init__(self, config_section: str):
        self.config_section = config_section
        self.optimized_parameters = []
        self.performance_impact = 0.0
        self.recommendations = []
        self.warnings = []
        self.backup_created = False
        self.applied = False
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'config_section': self.config_section,
            'optimized_parameters': [p.to_dict() for p in self.optimized_parameters],
            'performance_impact': self.performance_impact,
            'recommendations': self.recommendations,
            'warnings': self.warnings,
            'backup_created': self.backup_created,
            'applied': self.applied,
            'timestamp': self.timestamp.isoformat()
        }


class ConfigTuner:
    """配置调优器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 调优配置
        self.tuning_config = {
            'auto_apply': False,  # 是否自动应用优化
            'backup_configs': True,  # 是否备份配置
            'performance_monitoring': True,  # 是否监控性能影响
            'safe_mode': True,  # 安全模式，只应用低风险优化
            'optimization_targets': {
                'performance': 0.7,  # 性能权重
                'stability': 0.2,    # 稳定性权重
                'resource_usage': 0.1  # 资源使用权重
            },
            'parameter_categories': {
                'database': {
                    'max_connections': {'type': 'int', 'range': [10, 1000], 'impact': 'high'},
                    'query_timeout': {'type': 'float', 'range': [1.0, 300.0], 'impact': 'medium'},
                    'connection_pool_size': {'type': 'int', 'range': [5, 100], 'impact': 'medium'}
                },
                'cache': {
                    'max_memory_mb': {'type': 'int', 'range': [100, 10000], 'impact': 'high'},
                    'ttl_seconds': {'type': 'int', 'range': [60, 86400], 'impact': 'medium'},
                    'cleanup_interval': {'type': 'int', 'range': [30, 3600], 'impact': 'low'}
                },
                'trading': {
                    'order_timeout': {'type': 'float', 'range': [1.0, 60.0], 'impact': 'high'},
                    'max_retry_count': {'type': 'int', 'range': [1, 10], 'impact': 'medium'},
                    'batch_size': {'type': 'int', 'range': [1, 1000], 'impact': 'medium'}
                },
                'monitoring': {
                    'sample_rate': {'type': 'float', 'range': [0.1, 10.0], 'impact': 'low'},
                    'retention_days': {'type': 'int', 'range': [1, 365], 'impact': 'low'},
                    'alert_threshold': {'type': 'float', 'range': [0.1, 0.9], 'impact': 'medium'}
                }
            }
        }
        
        # 更新配置
        if 'config_tuning' in config:
            self.tuning_config.update(config['config_tuning'])
        
        self.optimization_history = []
        self.performance_baseline = {}
        self.current_parameters = {}
        
        # 初始化
        self._load_current_parameters()
    
    def _load_current_parameters(self):
        """加载当前配置参数"""
        try:
            # 从配置文件或当前配置中加载参数
            for category, params in self.tuning_config['parameter_categories'].items():
                self.current_parameters[category] = {}
                
                # 从当前配置中获取参数值
                category_config = self.config.get(category, {})
                
                for param_name, param_info in params.items():
                    current_value = category_config.get(param_name)
                    if current_value is not None:
                        param = ConfigParameter(
                            name=param_name,
                            current_value=current_value,
                            param_type=param_info['type']
                        )
                        param.valid_range = param_info.get('range')
                        self.current_parameters[category][param_name] = param
        
        except Exception as e:
            logger.error(f"加载当前配置参数失败: {e}")
    
    async def analyze_and_optimize(self) -> Dict[str, ConfigOptimizationResult]:
        """分析并优化配置"""
        logger.info("开始配置分析和优化")
        
        results = {}
        
        try:
            # 获取性能基线
            await self._establish_performance_baseline()
            
            # 分析各个配置类别
            for category in self.current_parameters.keys():
                try:
                    result = await self._optimize_category(category)
                    if result:
                        results[category] = result
                except Exception as e:
                    logger.error(f"优化配置类别 {category} 失败: {e}")
            
            # 生成整体优化建议
            overall_recommendations = self._generate_overall_recommendations(results)
            
            # 如果启用自动应用，则应用优化
            if self.tuning_config['auto_apply']:
                await self._apply_optimizations(results)
            
            logger.info(f"配置优化完成，优化了 {len(results)} 个类别")
            
        except Exception as e:
            logger.error(f"配置优化失败: {e}")
        
        return results
    
    async def _establish_performance_baseline(self):
        """建立性能基线"""
        try:
            # 收集当前性能指标
            self.performance_baseline = {
                'response_time': await self._measure_response_time(),
                'throughput': await self._measure_throughput(),
                'resource_usage': await self._measure_resource_usage(),
                'error_rate': await self._measure_error_rate(),
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info("性能基线已建立")
            
        except Exception as e:
            logger.error(f"建立性能基线失败: {e}")
    
    async def _optimize_category(self, category: str) -> Optional[ConfigOptimizationResult]:
        """优化特定配置类别"""
        if category not in self.current_parameters:
            return None
        
        result = ConfigOptimizationResult(category)
        
        try:
            category_params = self.current_parameters[category]
            param_config = self.tuning_config['parameter_categories'][category]
            
            # 分析每个参数
            for param_name, param in category_params.items():
                optimization = await self._analyze_parameter(
                    category, param_name, param, param_config[param_name]
                )
                
                if optimization:
                    result.optimized_parameters.append(optimization)
            
            # 计算整体性能影响
            result.performance_impact = self._calculate_category_impact(result.optimized_parameters)
            
            # 生成类别特定的建议
            result.recommendations = self._generate_category_recommendations(category, result)
            
            # 生成警告
            result.warnings = self._generate_category_warnings(category, result)
            
        except Exception as e:
            logger.error(f"优化配置类别 {category} 失败: {e}")
            return None
        
        return result
    
    async def _analyze_parameter(self, category: str, param_name: str, 
                                param: ConfigParameter, param_config: Dict[str, Any]) -> Optional[ConfigParameter]:
        """分析单个参数"""
        try:
            # 创建参数副本进行分析
            optimized_param = copy.deepcopy(param)
            
            # 根据参数类型和当前性能进行优化
            if category == 'database':
                suggestion = await self._optimize_database_parameter(param_name, param, param_config)
            elif category == 'cache':
                suggestion = await self._optimize_cache_parameter(param_name, param, param_config)
            elif category == 'trading':
                suggestion = await self._optimize_trading_parameter(param_name, param, param_config)
            elif category == 'monitoring':
                suggestion = await self._optimize_monitoring_parameter(param_name, param, param_config)
            else:
                suggestion = await self._optimize_generic_parameter(param_name, param, param_config)
            
            if suggestion and suggestion != param.current_value:
                optimized_param.suggested_value = suggestion
                optimized_param.impact_score = self._calculate_parameter_impact(
                    category, param_name, param.current_value, suggestion, param_config
                )
                optimized_param.optimization_reason = self._generate_optimization_reason(
                    category, param_name, param.current_value, suggestion
                )
                
                return optimized_param
            
        except Exception as e:
            logger.error(f"分析参数 {category}.{param_name} 失败: {e}")
        
        return None
    
    async def _optimize_database_parameter(self, param_name: str, param: ConfigParameter, 
                                         param_config: Dict[str, Any]) -> Any:
        """优化数据库参数"""
        current_value = param.current_value
        param_range = param_config.get('range', [])
        
        if param_name == 'max_connections':
            # 基于当前连接使用情况优化
            current_usage = await self._get_connection_usage()
            if current_usage:
                peak_usage = current_usage.get('peak_connections', 0)
                # 设置为峰值的1.5倍，但不超过范围上限
                suggested = min(max(int(peak_usage * 1.5), param_range[0]), param_range[1])
                return suggested if suggested != current_value else None
                
        elif param_name == 'query_timeout':
            # 基于慢查询统计优化
            slow_queries = await self._get_slow_query_stats()
            if slow_queries:
                p95_time = slow_queries.get('p95_time', 0)
                # 设置为P95时间的2倍
                suggested = min(max(p95_time * 2, param_range[0]), param_range[1])
                return suggested if abs(suggested - current_value) > 0.1 else None
                
        elif param_name == 'connection_pool_size':
            # 基于连接池使用情况优化
            pool_stats = await self._get_connection_pool_stats()
            if pool_stats:
                avg_usage = pool_stats.get('avg_active_connections', 0)
                # 设置为平均使用量的1.2倍
                suggested = min(max(int(avg_usage * 1.2), param_range[0]), param_range[1])
                return suggested if suggested != current_value else None
        
        return None
    
    async def _optimize_cache_parameter(self, param_name: str, param: ConfigParameter, 
                                      param_config: Dict[str, Any]) -> Any:
        """优化缓存参数"""
        current_value = param.current_value
        param_range = param_config.get('range', [])
        
        if param_name == 'max_memory_mb':
            # 基于内存使用情况优化
            memory_stats = await self._get_memory_stats()
            if memory_stats:
                available_memory = memory_stats.get('available_memory_mb', 0)
                # 使用可用内存的20%作为缓存
                suggested = min(max(int(available_memory * 0.2), param_range[0]), param_range[1])
                return suggested if abs(suggested - current_value) > 100 else None
                
        elif param_name == 'ttl_seconds':
            # 基于缓存命中率优化
            cache_stats = await self._get_cache_stats()
            if cache_stats:
                hit_rate = cache_stats.get('hit_rate', 0)
                if hit_rate < 50:  # 命中率低，增加TTL
                    suggested = min(current_value * 1.5, param_range[1])
                elif hit_rate > 90:  # 命中率高，可以减少TTL
                    suggested = max(current_value * 0.8, param_range[0])
                else:
                    suggested = current_value
                return int(suggested) if abs(suggested - current_value) > 60 else None
                
        elif param_name == 'cleanup_interval':
            # 基于缓存逐出率优化
            eviction_rate = await self._get_cache_eviction_rate()
            if eviction_rate and eviction_rate > 0.1:  # 逐出率高，增加清理频率
                suggested = max(current_value * 0.7, param_range[0])
                return int(suggested) if abs(suggested - current_value) > 30 else None
        
        return None
    
    async def _optimize_trading_parameter(self, param_name: str, param: ConfigParameter, 
                                        param_config: Dict[str, Any]) -> Any:
        """优化交易参数"""
        current_value = param.current_value
        param_range = param_config.get('range', [])
        
        if param_name == 'order_timeout':
            # 基于订单执行统计优化
            order_stats = await self._get_order_stats()
            if order_stats:
                avg_execution_time = order_stats.get('avg_execution_time', 0)
                # 设置为平均执行时间的3倍
                suggested = min(max(avg_execution_time * 3, param_range[0]), param_range[1])
                return suggested if abs(suggested - current_value) > 0.5 else None
                
        elif param_name == 'max_retry_count':
            # 基于订单失败率优化
            failure_rate = await self._get_order_failure_rate()
            if failure_rate:
                if failure_rate > 0.05:  # 失败率高，增加重试次数
                    suggested = min(current_value + 1, param_range[1])
                elif failure_rate < 0.01:  # 失败率低，可以减少重试次数
                    suggested = max(current_value - 1, param_range[0])
                else:
                    suggested = current_value
                return suggested if suggested != current_value else None
                
        elif param_name == 'batch_size':
            # 基于系统吞吐量优化
            throughput = await self._get_system_throughput()
            if throughput:
                # 根据系统负载调整批次大小
                system_load = await self._get_system_load()
                if system_load and system_load < 0.7:  # 负载低，可以增加批次大小
                    suggested = min(current_value * 1.2, param_range[1])
                elif system_load and system_load > 0.9:  # 负载高，减少批次大小
                    suggested = max(current_value * 0.8, param_range[0])
                else:
                    suggested = current_value
                return int(suggested) if abs(suggested - current_value) > 10 else None
        
        return None
    
    async def _optimize_monitoring_parameter(self, param_name: str, param: ConfigParameter, 
                                           param_config: Dict[str, Any]) -> Any:
        """优化监控参数"""
        current_value = param.current_value
        param_range = param_config.get('range', [])
        
        if param_name == 'sample_rate':
            # 基于系统负载优化采样率
            system_load = await self._get_system_load()
            if system_load:
                if system_load > 0.8:  # 负载高，降低采样率
                    suggested = max(current_value * 0.7, param_range[0])
                elif system_load < 0.3:  # 负载低，可以提高采样率
                    suggested = min(current_value * 1.3, param_range[1])
                else:
                    suggested = current_value
                return suggested if abs(suggested - current_value) > 0.1 else None
                
        elif param_name == 'retention_days':
            # 基于存储使用情况优化
            storage_usage = await self._get_storage_usage()
            if storage_usage and storage_usage > 0.8:  # 存储使用率高，减少保留天数
                suggested = max(current_value * 0.8, param_range[0])
                return int(suggested) if abs(suggested - current_value) > 7 else None
        
        return None
    
    async def _optimize_generic_parameter(self, param_name: str, param: ConfigParameter, 
                                        param_config: Dict[str, Any]) -> Any:
        """优化通用参数"""
        # 通用优化逻辑
        return None
    
    def _calculate_parameter_impact(self, category: str, param_name: str, 
                                  current_value: Any, suggested_value: Any, 
                                  param_config: Dict[str, Any]) -> float:
        """计算参数优化的影响分数"""
        impact_level = param_config.get('impact', 'low')
        
        # 基础影响分数
        base_scores = {'low': 0.1, 'medium': 0.5, 'high': 0.8}
        base_score = base_scores.get(impact_level, 0.1)
        
        # 计算变化幅度
        try:
            if isinstance(current_value, (int, float)) and isinstance(suggested_value, (int, float)):
                change_ratio = abs(suggested_value - current_value) / max(abs(current_value), 1)
                # 变化幅度越大，影响分数越高
                change_factor = min(change_ratio, 1.0)
            else:
                change_factor = 0.5  # 非数值类型默认中等影响
        except:
            change_factor = 0.5
        
        # 最终影响分数
        final_score = base_score * (0.5 + 0.5 * change_factor)
        return min(final_score, 1.0)
    
    def _generate_optimization_reason(self, category: str, param_name: str, 
                                    current_value: Any, suggested_value: Any) -> str:
        """生成优化原因说明"""
        if isinstance(current_value, (int, float)) and isinstance(suggested_value, (int, float)):
            if suggested_value > current_value:
                direction = "增加"
                reason_prefix = "提高性能"
            else:
                direction = "减少"
                reason_prefix = "优化资源使用"
            
            change_percent = abs(suggested_value - current_value) / max(abs(current_value), 1) * 100
            
            return f"{reason_prefix}，{direction} {change_percent:.1f}%"
        else:
            return f"从 {current_value} 优化为 {suggested_value}"
    
    def _calculate_category_impact(self, optimized_parameters: List[ConfigParameter]) -> float:
        """计算类别整体影响分数"""
        if not optimized_parameters:
            return 0.0
        
        # 计算加权平均影响分数
        total_impact = sum(param.impact_score for param in optimized_parameters)
        return total_impact / len(optimized_parameters)
    
    def _generate_category_recommendations(self, category: str, 
                                         result: ConfigOptimizationResult) -> List[str]:
        """生成类别特定的建议"""
        recommendations = []
        
        if not result.optimized_parameters:
            recommendations.append(f"{category} 配置已优化，无需调整")
            return recommendations
        
        high_impact_params = [p for p in result.optimized_parameters if p.impact_score > 0.7]
        
        if high_impact_params:
            recommendations.append(f"发现 {len(high_impact_params)} 个高影响参数需要优化")
        
        if category == 'database':
            recommendations.extend([
                "建议在低峰期应用数据库配置更改",
                "监控数据库性能指标以验证优化效果"
            ])
        elif category == 'cache':
            recommendations.extend([
                "缓存配置更改可能需要重启服务",
                "监控缓存命中率和内存使用情况"
            ])
        elif category == 'trading':
            recommendations.extend([
                "交易参数调整可能影响订单执行",
                "建议在模拟环境中先验证配置"
            ])
        
        return recommendations
    
    def _generate_category_warnings(self, category: str, 
                                  result: ConfigOptimizationResult) -> List[str]:
        """生成类别特定的警告"""
        warnings = []
        
        critical_params = [p for p in result.optimized_parameters if p.impact_score > 0.8]
        
        if critical_params:
            warnings.append(f"发现 {len(critical_params)} 个关键参数的重大更改")
        
        if category == 'database' and result.performance_impact > 0.5:
            warnings.append("数据库配置更改可能影响系统稳定性")
        
        if category == 'trading':
            warnings.append("交易参数更改可能影响交易执行，请谨慎操作")
        
        return warnings
    
    def _generate_overall_recommendations(self, 
                                        results: Dict[str, ConfigOptimizationResult]) -> List[str]:
        """生成整体优化建议"""
        recommendations = []
        
        total_optimizations = sum(len(result.optimized_parameters) for result in results.values())
        
        if total_optimizations == 0:
            recommendations.append("系统配置已优化，无需调整")
        else:
            recommendations.append(f"发现 {total_optimizations} 个参数可以优化")
            
            # 按影响程度排序
            high_impact_categories = [
                name for name, result in results.items() 
                if result.performance_impact > 0.7
            ]
            
            if high_impact_categories:
                recommendations.append(f"优先处理高影响类别: {', '.join(high_impact_categories)}")
        
        recommendations.extend([
            "建议在非高峰期应用配置更改",
            "应用更改前创建配置备份",
            "应用后监控系统性能和稳定性",
            "如有问题及时回滚配置"
        ])
        
        return recommendations
    
    async def _apply_optimizations(self, results: Dict[str, ConfigOptimizationResult]):
        """应用配置优化"""
        if not self.tuning_config['auto_apply']:
            return
        
        logger.info("开始应用配置优化")
        
        try:
            # 创建备份
            if self.tuning_config['backup_configs']:
                await self._create_config_backup()
            
            # 应用优化
            for category, result in results.items():
                if self._should_apply_category(category, result):
                    await self._apply_category_optimizations(category, result)
                    result.applied = True
            
            logger.info("配置优化应用完成")
            
        except Exception as e:
            logger.error(f"应用配置优化失败: {e}")
    
    def _should_apply_category(self, category: str, result: ConfigOptimizationResult) -> bool:
        """判断是否应该应用类别优化"""
        if not result.optimized_parameters:
            return False
        
        # 安全模式下只应用低风险优化
        if self.tuning_config['safe_mode']:
            max_impact = max(p.impact_score for p in result.optimized_parameters)
            if max_impact > 0.5:
                return False
        
        # 检查警告
        if result.warnings and self.tuning_config['safe_mode']:
            return False
        
        return True
    
    async def _apply_category_optimizations(self, category: str, 
                                          result: ConfigOptimizationResult):
        """应用类别优化"""
        try:
            # 更新配置
            for param in result.optimized_parameters:
                if param.suggested_value is not None:
                    # 更新内存中的配置
                    if category not in self.config:
                        self.config[category] = {}
                    self.config[category][param.name] = param.suggested_value
                    
                    # 更新当前参数
                    if category in self.current_parameters and param.name in self.current_parameters[category]:
                        self.current_parameters[category][param.name].current_value = param.suggested_value
            
            # 保存配置到文件
            await self._save_config_to_file(category)
            
            logger.info(f"已应用 {category} 配置优化")
            
        except Exception as e:
            logger.error(f"应用 {category} 配置优化失败: {e}")
    
    async def _create_config_backup(self):
        """创建配置备份"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"config_backup_{timestamp}.json"
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"配置备份已创建: {backup_path}")
            
        except Exception as e:
            logger.error(f"创建配置备份失败: {e}")
    
    async def _save_config_to_file(self, category: str):
        """保存配置到文件"""
        try:
            # 这里应该根据实际的配置文件格式和位置来实现
            # 示例：保存到JSON配置文件
            config_file = f"{category}_config.json"
            
            category_config = self.config.get(category, {})
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(category_config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"已保存 {category} 配置到文件")
            
        except Exception as e:
            logger.error(f"保存 {category} 配置失败: {e}")
    
    # 性能测量方法（模拟实现）
    async def _measure_response_time(self) -> float:
        """测量响应时间"""
        # 模拟测量
        return 0.15
    
    async def _measure_throughput(self) -> float:
        """测量吞吐量"""
        # 模拟测量
        return 1000.0
    
    async def _measure_resource_usage(self) -> Dict[str, float]:
        """测量资源使用情况"""
        # 模拟测量
        return {'cpu': 45.0, 'memory': 60.0, 'disk': 30.0}
    
    async def _measure_error_rate(self) -> float:
        """测量错误率"""
        # 模拟测量
        return 0.02
    
    # 统计信息获取方法（模拟实现）
    async def _get_connection_usage(self) -> Optional[Dict[str, Any]]:
        """获取连接使用情况"""
        return {'peak_connections': 15, 'avg_connections': 8}
    
    async def _get_slow_query_stats(self) -> Optional[Dict[str, Any]]:
        """获取慢查询统计"""
        return {'p95_time': 1.2, 'count': 5}
    
    async def _get_connection_pool_stats(self) -> Optional[Dict[str, Any]]:
        """获取连接池统计"""
        return {'avg_active_connections': 12, 'max_connections': 20}
    
    async def _get_memory_stats(self) -> Optional[Dict[str, Any]]:
        """获取内存统计"""
        return {'available_memory_mb': 4096, 'used_memory_mb': 2048}
    
    async def _get_cache_stats(self) -> Optional[Dict[str, Any]]:
        """获取缓存统计"""
        return {'hit_rate': 75.0, 'miss_rate': 25.0}
    
    async def _get_cache_eviction_rate(self) -> Optional[float]:
        """获取缓存逐出率"""
        return 0.05
    
    async def _get_order_stats(self) -> Optional[Dict[str, Any]]:
        """获取订单统计"""
        return {'avg_execution_time': 0.8, 'success_rate': 0.98}
    
    async def _get_order_failure_rate(self) -> Optional[float]:
        """获取订单失败率"""
        return 0.02
    
    async def _get_system_throughput(self) -> Optional[float]:
        """获取系统吞吐量"""
        return 500.0
    
    async def _get_system_load(self) -> Optional[float]:
        """获取系统负载"""
        return 0.65
    
    async def _get_storage_usage(self) -> Optional[float]:
        """获取存储使用率"""
        return 0.45
    
    def get_optimization_report(self, results: Dict[str, ConfigOptimizationResult]) -> Dict[str, Any]:
        """生成优化报告"""
        report = {
            'summary': {
                'total_categories': len(results),
                'total_optimizations': sum(len(r.optimized_parameters) for r in results.values()),
                'avg_performance_impact': 0.0,
                'high_impact_optimizations': 0
            },
            'categories': {},
            'overall_recommendations': self._generate_overall_recommendations(results),
            'timestamp': datetime.now().isoformat()
        }
        
        # 类别详情
        total_impact = 0.0
        high_impact_count = 0
        
        for category, result in results.items():
            report['categories'][category] = result.to_dict()
            total_impact += result.performance_impact
            
            high_impact_params = [p for p in result.optimized_parameters if p.impact_score > 0.7]
            high_impact_count += len(high_impact_params)
        
        # 计算平均影响
        if len(results) > 0:
            report['summary']['avg_performance_impact'] = total_impact / len(results)
        
        report['summary']['high_impact_optimizations'] = high_impact_count
        
        return report
    
    def export_optimization_plan(self, results: Dict[str, ConfigOptimizationResult], 
                                filepath: str):
        """导出优化计划"""
        try:
            plan = {
                'generated_at': datetime.now().isoformat(),
                'optimization_results': self.get_optimization_report(results),
                'implementation_steps': self._generate_implementation_steps(results),
                'rollback_plan': self._generate_rollback_plan(results)
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(plan, f, indent=2, ensure_ascii=False)
            
            logger.info(f"优化计划已导出到: {filepath}")
            
        except Exception as e:
            logger.error(f"导出优化计划失败: {e}")
    
    def _generate_implementation_steps(self, 
                                     results: Dict[str, ConfigOptimizationResult]) -> List[Dict[str, Any]]:
        """生成实施步骤"""
        steps = []
        
        # 按影响程度排序类别
        sorted_categories = sorted(
            results.items(), 
            key=lambda x: x[1].performance_impact, 
            reverse=True
        )
        
        step_num = 1
        
        # 添加准备步骤
        steps.append({
            'step': step_num,
            'action': 'preparation',
            'description': '创建配置备份并准备回滚计划',
            'estimated_time': '10分钟',
            'risk_level': 'low'
        })
        step_num += 1
        
        # 为每个类别添加实施步骤
        for category, result in sorted_categories:
            if result.optimized_parameters:
                steps.append({
                    'step': step_num,
                    'action': f'optimize_{category}',
                    'description': f'应用{category}配置优化',
                    'parameters': [p.to_dict() for p in result.optimized_parameters],
                    'estimated_time': '15分钟',
                    'risk_level': 'high' if result.performance_impact > 0.7 else 'medium'
                })
                step_num += 1
        
        # 添加验证步骤
        steps.append({
            'step': step_num,
            'action': 'validation',
            'description': '验证配置更改效果并监控系统性能',
            'estimated_time': '30分钟',
            'risk_level': 'low'
        })
        
        return steps
    
    def _generate_rollback_plan(self, 
                              results: Dict[str, ConfigOptimizationResult]) -> Dict[str, Any]:
        """生成回滚计划"""
        rollback_plan = {
            'trigger_conditions': [
                '系统性能下降超过10%',
                '错误率增加超过5%',
                '出现严重系统异常'
            ],
            'rollback_steps': [
                {
                    'step': 1,
                    'action': '停止新的配置更改',
                    'description': '立即停止应用任何新的配置更改'
                },
                {
                    'step': 2,
                    'action': '恢复备份配置',
                    'description': '从备份文件恢复原始配置'
                },
                {
                    'step': 3,
                    'action': '重启相关服务',
                    'description': '重启受影响的服务以应用原始配置'
                },
                {
                    'step': 4,
                    'action': '验证回滚效果',
                    'description': '确认系统恢复正常运行'
                }
            ],
            'estimated_rollback_time': '20分钟'
        }
        
        return rollback_plan