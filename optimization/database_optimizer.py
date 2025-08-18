"""
数据库优化器

负责优化数据库性能，包括索引优化、查询优化等
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class OptimizationResult:
    """优化结果"""
    
    def __init__(self, optimization_type: str):
        self.optimization_type = optimization_type
        self.status = 'pending'  # pending, running, completed, failed
        self.start_time = None
        self.end_time = None
        self.before_metrics = {}
        self.after_metrics = {}
        self.improvements = {}
        self.actions_taken = []
        self.recommendations = []
        self.errors = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'optimization_type': self.optimization_type,
            'status': self.status,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'before_metrics': self.before_metrics,
            'after_metrics': self.after_metrics,
            'improvements': self.improvements,
            'actions_taken': self.actions_taken,
            'recommendations': self.recommendations,
            'errors': [str(e) for e in self.errors]
        }


class DatabaseOptimizer:
    """数据库优化器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 优化配置
        self.optimization_config = {
            'index_optimization': {
                'enabled': True,
                'analyze_threshold': 0.1,  # 查询时间阈值(秒)
                'max_indexes_per_table': 10
            },
            'query_optimization': {
                'enabled': True,
                'slow_query_threshold': 1.0,  # 慢查询阈值(秒)
                'explain_plan': True
            },
            'connection_pooling': {
                'enabled': True,
                'min_connections': 5,
                'max_connections': 20,
                'connection_timeout': 30.0
            },
            'table_optimization': {
                'enabled': True,
                'analyze_tables': True,
                'rebuild_indexes': False
            }
        }
        
        # 更新配置
        if 'database_optimization' in config:
            self.optimization_config.update(config['database_optimization'])
    
    async def optimize_database(self) -> Dict[str, OptimizationResult]:
        """执行数据库优化"""
        logger.info("开始数据库优化")
        
        results = {}
        
        # 执行各项优化
        optimizations = [
            ('index_optimization', self.optimize_indexes),
            ('query_optimization', self.optimize_queries),
            ('connection_pooling', self.optimize_connections),
            ('table_optimization', self.optimize_tables)
        ]
        
        for opt_name, opt_func in optimizations:
            if self.optimization_config[opt_name]['enabled']:
                try:
                    result = await opt_func()
                    results[opt_name] = result
                except Exception as e:
                    logger.error(f"{opt_name}优化失败: {e}")
                    error_result = OptimizationResult(opt_name)
                    error_result.status = 'failed'
                    error_result.errors.append(e)
                    results[opt_name] = error_result
        
        logger.info(f"数据库优化完成，执行了{len(results)}项优化")
        return results
    
    async def optimize_indexes(self) -> OptimizationResult:
        """优化数据库索引"""
        result = OptimizationResult('index_optimization')
        result.status = 'running'
        result.start_time = datetime.now()
        
        try:
            # 分析当前索引使用情况
            result.before_metrics = await self._analyze_index_usage()
            
            # 识别需要创建的索引
            missing_indexes = await self._identify_missing_indexes()
            
            # 识别冗余索引
            redundant_indexes = await self._identify_redundant_indexes()
            
            # 创建推荐的索引
            for index_suggestion in missing_indexes:
                try:
                    await self._create_index(index_suggestion)
                    result.actions_taken.append(f"创建索引: {index_suggestion['name']}")
                except Exception as e:
                    result.errors.append(e)
            
            # 删除冗余索引
            for redundant_index in redundant_indexes:
                try:
                    await self._drop_index(redundant_index)
                    result.actions_taken.append(f"删除冗余索引: {redundant_index['name']}")
                except Exception as e:
                    result.errors.append(e)
            
            # 重新分析索引使用情况
            result.after_metrics = await self._analyze_index_usage()
            
            # 计算改进效果
            result.improvements = self._calculate_index_improvements(
                result.before_metrics, 
                result.after_metrics
            )
            
            # 生成建议
            result.recommendations = self._generate_index_recommendations()
            
            result.status = 'completed'
            
        except Exception as e:
            result.status = 'failed'
            result.errors.append(e)
            logger.error(f"索引优化失败: {e}")
        
        result.end_time = datetime.now()
        return result
    
    async def optimize_queries(self) -> OptimizationResult:
        """优化数据库查询"""
        result = OptimizationResult('query_optimization')
        result.status = 'running'
        result.start_time = datetime.now()
        
        try:
            # 分析慢查询
            result.before_metrics = await self._analyze_slow_queries()
            
            # 获取查询统计
            query_stats = await self._get_query_statistics()
            
            # 识别需要优化的查询
            queries_to_optimize = await self._identify_problematic_queries(query_stats)
            
            # 优化查询
            for query_info in queries_to_optimize:
                try:
                    optimization = await self._optimize_query(query_info)
                    if optimization:
                        result.actions_taken.append(f"优化查询: {optimization['description']}")
                except Exception as e:
                    result.errors.append(e)
            
            # 重新分析慢查询
            result.after_metrics = await self._analyze_slow_queries()
            
            # 计算改进效果
            result.improvements = self._calculate_query_improvements(
                result.before_metrics,
                result.after_metrics
            )
            
            # 生成建议
            result.recommendations = self._generate_query_recommendations(queries_to_optimize)
            
            result.status = 'completed'
            
        except Exception as e:
            result.status = 'failed'
            result.errors.append(e)
            logger.error(f"查询优化失败: {e}")
        
        result.end_time = datetime.now()
        return result
    
    async def optimize_connections(self) -> OptimizationResult:
        """优化数据库连接"""
        result = OptimizationResult('connection_pooling')
        result.status = 'running'
        result.start_time = datetime.now()
        
        try:
            # 分析当前连接使用情况
            result.before_metrics = await self._analyze_connection_usage()
            
            # 优化连接池配置
            new_config = await self._optimize_connection_pool()
            
            if new_config:
                result.actions_taken.append(f"更新连接池配置: {new_config}")
            
            # 重新分析连接使用情况
            result.after_metrics = await self._analyze_connection_usage()
            
            # 计算改进效果
            result.improvements = self._calculate_connection_improvements(
                result.before_metrics,
                result.after_metrics
            )
            
            # 生成建议
            result.recommendations = self._generate_connection_recommendations()
            
            result.status = 'completed'
            
        except Exception as e:
            result.status = 'failed'
            result.errors.append(e)
            logger.error(f"连接优化失败: {e}")
        
        result.end_time = datetime.now()
        return result
    
    async def optimize_tables(self) -> OptimizationResult:
        """优化数据库表"""
        result = OptimizationResult('table_optimization')
        result.status = 'running'
        result.start_time = datetime.now()
        
        try:
            # 分析表统计信息
            result.before_metrics = await self._analyze_table_statistics()
            
            # 更新表统计信息
            await self._update_table_statistics()
            result.actions_taken.append("更新表统计信息")
            
            # 分析表碎片
            fragmented_tables = await self._analyze_table_fragmentation()
            
            # 重组碎片严重的表
            for table_info in fragmented_tables:
                if table_info['fragmentation_percent'] > 30:
                    try:
                        await self._rebuild_table(table_info['table_name'])
                        result.actions_taken.append(f"重组表: {table_info['table_name']}")
                    except Exception as e:
                        result.errors.append(e)
            
            # 重新分析表统计信息
            result.after_metrics = await self._analyze_table_statistics()
            
            # 计算改进效果
            result.improvements = self._calculate_table_improvements(
                result.before_metrics,
                result.after_metrics
            )
            
            # 生成建议
            result.recommendations = self._generate_table_recommendations()
            
            result.status = 'completed'
            
        except Exception as e:
            result.status = 'failed'
            result.errors.append(e)
            logger.error(f"表优化失败: {e}")
        
        result.end_time = datetime.now()
        return result
    
    async def _analyze_index_usage(self) -> Dict[str, Any]:
        """分析索引使用情况"""
        # 模拟索引分析
        return {
            'total_indexes': 15,
            'used_indexes': 12,
            'unused_indexes': 3,
            'avg_index_usage': 85.2,
            'index_size_mb': 156.7
        }
    
    async def _identify_missing_indexes(self) -> List[Dict[str, Any]]:
        """识别缺失的索引"""
        # 模拟缺失索引检测
        missing_indexes = [
            {
                'name': 'idx_stocks_symbol_date',
                'table': 'daily_data',
                'columns': ['symbol', 'trade_date'],
                'expected_improvement': '40% query speedup'
            },
            {
                'name': 'idx_strategies_active',
                'table': 'strategies',
                'columns': ['is_active'],
                'expected_improvement': '25% query speedup'
            }
        ]
        return missing_indexes
    
    async def _identify_redundant_indexes(self) -> List[Dict[str, Any]]:
        """识别冗余索引"""
        # 模拟冗余索引检测
        redundant_indexes = [
            {
                'name': 'idx_old_symbol',
                'table': 'daily_data',
                'reason': '被复合索引覆盖'
            }
        ]
        return redundant_indexes
    
    async def _create_index(self, index_info: Dict[str, Any]):
        """创建索引"""
        # 模拟索引创建
        await asyncio.sleep(0.1)
        logger.info(f"创建索引: {index_info['name']}")
    
    async def _drop_index(self, index_info: Dict[str, Any]):
        """删除索引"""
        # 模拟索引删除
        await asyncio.sleep(0.05)
        logger.info(f"删除索引: {index_info['name']}")
    
    async def _analyze_slow_queries(self) -> Dict[str, Any]:
        """分析慢查询"""
        # 模拟慢查询分析
        return {
            'total_queries': 1250,
            'slow_queries': 23,
            'avg_query_time': 0.156,
            'slowest_query_time': 3.2,
            'slow_query_rate': 1.84
        }
    
    async def _get_query_statistics(self) -> List[Dict[str, Any]]:
        """获取查询统计信息"""
        # 模拟查询统计
        return [
            {
                'query_hash': 'abc123',
                'query_text': 'SELECT * FROM daily_data WHERE symbol = ?',
                'execution_count': 450,
                'avg_duration': 0.23,
                'max_duration': 1.5
            }
        ]
    
    async def _identify_problematic_queries(self, query_stats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """识别有问题的查询"""
        threshold = self.optimization_config['query_optimization']['slow_query_threshold']
        
        problematic = []
        for query in query_stats:
            if query['avg_duration'] > threshold:
                problematic.append(query)
        
        return problematic
    
    async def _optimize_query(self, query_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """优化查询"""
        # 模拟查询优化
        await asyncio.sleep(0.1)
        
        return {
            'description': f"为查询添加索引提示",
            'before_time': query_info['avg_duration'],
            'after_time': query_info['avg_duration'] * 0.6
        }
    
    async def _analyze_connection_usage(self) -> Dict[str, Any]:
        """分析连接使用情况"""
        # 模拟连接分析
        return {
            'active_connections': 8,
            'max_connections': 15,
            'connection_utilization': 53.3,
            'avg_connection_time': 2.1,
            'connection_timeouts': 2
        }
    
    async def _optimize_connection_pool(self) -> Optional[Dict[str, Any]]:
        """优化连接池"""
        # 模拟连接池优化
        new_config = {
            'min_connections': 10,
            'max_connections': 25,
            'connection_timeout': 45.0
        }
        return new_config
    
    async def _analyze_table_statistics(self) -> Dict[str, Any]:
        """分析表统计信息"""
        # 模拟表统计分析
        return {
            'total_tables': 8,
            'total_size_mb': 1247.5,
            'avg_fragmentation': 15.3,
            'statistics_age_days': 3.2
        }
    
    async def _update_table_statistics(self):
        """更新表统计信息"""
        # 模拟统计信息更新
        await asyncio.sleep(0.2)
        logger.info("更新表统计信息")
    
    async def _analyze_table_fragmentation(self) -> List[Dict[str, Any]]:
        """分析表碎片"""
        # 模拟碎片分析
        return [
            {
                'table_name': 'daily_data',
                'fragmentation_percent': 35.2,
                'size_mb': 456.7
            },
            {
                'table_name': 'trades',
                'fragmentation_percent': 42.1,
                'size_mb': 123.4
            }
        ]
    
    async def _rebuild_table(self, table_name: str):
        """重建表"""
        # 模拟表重建
        await asyncio.sleep(1.0)
        logger.info(f"重建表: {table_name}")
    
    def _calculate_index_improvements(self, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        """计算索引优化改进"""
        improvements = {}
        
        if before and after:
            improvements['index_usage_improvement'] = after['avg_index_usage'] - before['avg_index_usage']
            improvements['unused_indexes_reduced'] = before['unused_indexes'] - after['unused_indexes']
        
        return improvements
    
    def _calculate_query_improvements(self, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        """计算查询优化改进"""
        improvements = {}
        
        if before and after:
            improvements['avg_query_time_reduction'] = before['avg_query_time'] - after['avg_query_time']
            improvements['slow_queries_reduced'] = before['slow_queries'] - after['slow_queries']
            improvements['slow_query_rate_reduction'] = before['slow_query_rate'] - after['slow_query_rate']
        
        return improvements
    
    def _calculate_connection_improvements(self, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        """计算连接优化改进"""
        improvements = {}
        
        if before and after:
            improvements['connection_timeout_reduction'] = before['connection_timeouts'] - after['connection_timeouts']
            improvements['utilization_improvement'] = after['connection_utilization'] - before['connection_utilization']
        
        return improvements
    
    def _calculate_table_improvements(self, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        """计算表优化改进"""
        improvements = {}
        
        if before and after:
            improvements['fragmentation_reduction'] = before['avg_fragmentation'] - after['avg_fragmentation']
            improvements['statistics_freshness'] = before['statistics_age_days'] - after['statistics_age_days']
        
        return improvements
    
    def _generate_index_recommendations(self) -> List[str]:
        """生成索引优化建议"""
        return [
            "定期监控索引使用情况，删除未使用的索引",
            "为经常使用的查询条件创建复合索引",
            "避免在小表上创建过多索引",
            "定期重建碎片化严重的索引"
        ]
    
    def _generate_query_recommendations(self, problematic_queries: List[Dict[str, Any]]) -> List[str]:
        """生成查询优化建议"""
        recommendations = [
            "使用查询计划分析器优化慢查询",
            "避免在WHERE子句中使用函数",
            "合理使用LIMIT限制返回结果数量"
        ]
        
        if len(problematic_queries) > 10:
            recommendations.append("慢查询数量过多，建议全面检查查询逻辑")
        
        return recommendations
    
    def _generate_connection_recommendations(self) -> List[str]:
        """生成连接优化建议"""
        return [
            "合理配置连接池大小",
            "使用连接池减少连接开销",
            "监控连接超时情况",
            "定期清理空闲连接"
        ]
    
    def _generate_table_recommendations(self) -> List[str]:
        """生成表优化建议"""
        return [
            "定期更新表统计信息",
            "监控表碎片化程度",
            "适时重建碎片化严重的表",
            "合理设置表的填充因子"
        ]
    
    def generate_optimization_report(self, results: Dict[str, OptimizationResult]) -> Dict[str, Any]:
        """生成优化报告"""
        report = {
            'summary': {
                'total_optimizations': len(results),
                'completed_optimizations': 0,
                'failed_optimizations': 0,
                'total_actions': 0,
                'overall_improvement': {}
            },
            'optimizations': {},
            'recommendations': [],
            'timestamp': datetime.now().isoformat()
        }
        
        # 汇总优化结果
        for opt_name, result in results.items():
            report['optimizations'][opt_name] = result.to_dict()
            
            if result.status == 'completed':
                report['summary']['completed_optimizations'] += 1
                report['summary']['total_actions'] += len(result.actions_taken)
                report['recommendations'].extend(result.recommendations)
            elif result.status == 'failed':
                report['summary']['failed_optimizations'] += 1
        
        # 去重建议
        report['recommendations'] = list(set(report['recommendations']))
        
        return report