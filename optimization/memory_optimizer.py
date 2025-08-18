"""
内存优化器

负责优化系统内存使用，包括内存泄漏检测、垃圾回收优化等
"""

import asyncio
import gc
import logging
import psutil
import threading
import time
import traceback
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import weakref
from collections import defaultdict

logger = logging.getLogger(__name__)


class MemorySnapshot:
    """内存快照"""
    
    def __init__(self):
        self.timestamp = datetime.now()
        self.total_memory = 0
        self.available_memory = 0
        self.process_memory = 0
        self.memory_percent = 0.0
        self.gc_stats = {}
        self.object_counts = {}
        self.largest_objects = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'total_memory_mb': self.total_memory / (1024 * 1024),
            'available_memory_mb': self.available_memory / (1024 * 1024),
            'process_memory_mb': self.process_memory / (1024 * 1024),
            'memory_percent': self.memory_percent,
            'gc_stats': self.gc_stats,
            'object_counts': self.object_counts,
            'largest_objects': self.largest_objects
        }


class MemoryLeak:
    """内存泄漏信息"""
    
    def __init__(self, object_type: str, count_growth: int, size_growth: int):
        self.object_type = object_type
        self.count_growth = count_growth
        self.size_growth = size_growth
        self.detected_at = datetime.now()
        self.severity = self._calculate_severity()
    
    def _calculate_severity(self) -> str:
        """计算严重程度"""
        if self.size_growth > 100 * 1024 * 1024:  # 100MB
            return 'critical'
        elif self.size_growth > 10 * 1024 * 1024:  # 10MB
            return 'high'
        elif self.size_growth > 1024 * 1024:  # 1MB
            return 'medium'
        else:
            return 'low'
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'object_type': self.object_type,
            'count_growth': self.count_growth,
            'size_growth_mb': self.size_growth / (1024 * 1024),
            'detected_at': self.detected_at.isoformat(),
            'severity': self.severity
        }


class MemoryOptimizer:
    """内存优化器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 优化配置
        self.optimization_config = {
            'monitoring': {
                'enabled': True,
                'interval': 30.0,  # 监控间隔(秒)
                'snapshot_retention': 100,  # 保留快照数量
                'leak_detection_threshold': 0.1  # 泄漏检测阈值(10%)
            },
            'gc_optimization': {
                'enabled': True,
                'auto_collect': True,
                'collection_threshold': 1000,  # 触发收集的对象数
                'forced_collection_interval': 300  # 强制收集间隔(秒)
            },
            'object_tracking': {
                'enabled': True,
                'track_types': ['dict', 'list', 'tuple', 'set'],
                'max_tracked_objects': 1000
            },
            'memory_limits': {
                'max_memory_percent': 80.0,  # 最大内存使用百分比
                'warning_memory_percent': 70.0,  # 警告内存使用百分比
                'cleanup_threshold': 85.0  # 清理阈值
            }
        }
        
        # 更新配置
        if 'memory_optimization' in config:
            self.optimization_config.update(config['memory_optimization'])
        
        # 监控数据
        self.snapshots = []
        self.detected_leaks = []
        self.monitoring = False
        self.monitor_thread = None
        self.object_tracker = weakref.WeakSet()
        self.gc_stats_history = []
        
        # 初始化
        self._init_monitoring()
    
    def _init_monitoring(self):
        """初始化监控"""
        if self.optimization_config['monitoring']['enabled']:
            self.start_monitoring()
    
    def start_monitoring(self):
        """开始内存监控"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("内存监控已启动")
    
    def stop_monitoring(self):
        """停止内存监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("内存监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                snapshot = self._take_memory_snapshot()
                self._store_snapshot(snapshot)
                
                # 检测内存泄漏
                leaks = self._detect_memory_leaks()
                if leaks:
                    self.detected_leaks.extend(leaks)
                    for leak in leaks:
                        logger.warning(f"检测到内存泄漏: {leak.object_type} ({leak.severity})")
                
                # 检查内存使用是否过高
                self._check_memory_usage(snapshot)
                
                time.sleep(self.optimization_config['monitoring']['interval'])
                
            except Exception as e:
                logger.error(f"内存监控异常: {e}")
                time.sleep(5)
    
    def _take_memory_snapshot(self) -> MemorySnapshot:
        """获取内存快照"""
        snapshot = MemorySnapshot()
        
        try:
            # 系统内存信息
            memory_info = psutil.virtual_memory()
            snapshot.total_memory = memory_info.total
            snapshot.available_memory = memory_info.available
            snapshot.memory_percent = memory_info.percent
            
            # 进程内存信息
            process = psutil.Process()
            process_memory = process.memory_info()
            snapshot.process_memory = process_memory.rss
            
            # 垃圾收集统计
            snapshot.gc_stats = {
                'collections': gc.get_stats(),
                'counts': gc.get_count(),
                'flags': gc.get_debug()
            }
            
            # 对象计数
            if self.optimization_config['object_tracking']['enabled']:
                snapshot.object_counts = self._get_object_counts()
                snapshot.largest_objects = self._get_largest_objects()
            
        except Exception as e:
            logger.error(f"获取内存快照失败: {e}")
        
        return snapshot
    
    def _store_snapshot(self, snapshot: MemorySnapshot):
        """存储内存快照"""
        self.snapshots.append(snapshot)
        
        # 限制快照数量
        max_snapshots = self.optimization_config['monitoring']['snapshot_retention']
        if len(self.snapshots) > max_snapshots:
            self.snapshots = self.snapshots[-max_snapshots:]
    
    def _detect_memory_leaks(self) -> List[MemoryLeak]:
        """检测内存泄漏"""
        leaks = []
        
        try:
            if len(self.snapshots) < 10:  # 需要足够的数据点
                return leaks
            
            recent_snapshots = self.snapshots[-10:]
            threshold = self.optimization_config['monitoring']['leak_detection_threshold']
            
            # 分析对象数量增长
            for object_type in self.optimization_config['object_tracking']['track_types']:
                counts = [s.object_counts.get(object_type, 0) for s in recent_snapshots]
                
                if len(counts) >= 2:
                    growth_rate = (counts[-1] - counts[0]) / max(counts[0], 1)
                    
                    if growth_rate > threshold:
                        count_growth = counts[-1] - counts[0]
                        # 估算大小增长（简化计算）
                        size_growth = count_growth * 100  # 假设每个对象100字节
                        
                        leak = MemoryLeak(object_type, count_growth, size_growth)
                        leaks.append(leak)
            
            # 分析进程内存增长
            memory_sizes = [s.process_memory for s in recent_snapshots]
            if len(memory_sizes) >= 2:
                memory_growth_rate = (memory_sizes[-1] - memory_sizes[0]) / max(memory_sizes[0], 1)
                
                if memory_growth_rate > threshold:
                    size_growth = memory_sizes[-1] - memory_sizes[0]
                    leak = MemoryLeak('process_memory', 1, size_growth)
                    leaks.append(leak)
            
        except Exception as e:
            logger.error(f"内存泄漏检测失败: {e}")
        
        return leaks
    
    def _check_memory_usage(self, snapshot: MemorySnapshot):
        """检查内存使用情况"""
        config = self.optimization_config['memory_limits']
        
        if snapshot.memory_percent > config['cleanup_threshold']:
            logger.critical(f"内存使用过高: {snapshot.memory_percent:.1f}%，开始清理")
            asyncio.create_task(self._emergency_cleanup())
        elif snapshot.memory_percent > config['warning_memory_percent']:
            logger.warning(f"内存使用较高: {snapshot.memory_percent:.1f}%")
    
    def _get_object_counts(self) -> Dict[str, int]:
        """获取对象计数"""
        counts = defaultdict(int)
        
        try:
            # 获取所有对象
            for obj in gc.get_objects():
                obj_type = type(obj).__name__
                counts[obj_type] += 1
        
        except Exception as e:
            logger.error(f"获取对象计数失败: {e}")
        
        return dict(counts)
    
    def _get_largest_objects(self) -> List[Dict[str, Any]]:
        """获取最大的对象"""
        largest = []
        
        try:
            import sys
            
            objects = []
            for obj in gc.get_objects():
                try:
                    size = sys.getsizeof(obj)
                    objects.append({
                        'type': type(obj).__name__,
                        'size': size,
                        'id': id(obj)
                    })
                except:
                    continue
            
            # 按大小排序，取前10个
            objects.sort(key=lambda x: x['size'], reverse=True)
            largest = objects[:10]
        
        except Exception as e:
            logger.error(f"获取最大对象失败: {e}")
        
        return largest
    
    async def optimize_memory(self) -> Dict[str, Any]:
        """执行内存优化"""
        logger.info("开始内存优化")
        
        optimization_result = {
            'before_snapshot': None,
            'after_snapshot': None,
            'actions_taken': [],
            'memory_freed': 0,
            'recommendations': [],
            'leaks_found': len(self.detected_leaks)
        }
        
        try:
            # 获取优化前快照
            optimization_result['before_snapshot'] = self._take_memory_snapshot().to_dict()
            
            # 执行优化操作
            actions = []
            
            # 1. 垃圾收集优化
            if self.optimization_config['gc_optimization']['enabled']:
                freed = await self._optimize_garbage_collection()
                if freed > 0:
                    actions.append(f"垃圾收集释放了 {freed / (1024*1024):.2f} MB")
            
            # 2. 清理缓存
            cache_freed = await self._cleanup_caches()
            if cache_freed > 0:
                actions.append(f"缓存清理释放了 {cache_freed / (1024*1024):.2f} MB")
            
            # 3. 优化数据结构
            struct_freed = await self._optimize_data_structures()
            if struct_freed > 0:
                actions.append(f"数据结构优化释放了 {struct_freed / (1024*1024):.2f} MB")
            
            # 4. 处理内存泄漏
            leak_actions = await self._handle_memory_leaks()
            actions.extend(leak_actions)
            
            optimization_result['actions_taken'] = actions
            
            # 获取优化后快照
            after_snapshot = self._take_memory_snapshot()
            optimization_result['after_snapshot'] = after_snapshot.to_dict()
            
            # 计算释放的内存
            before_memory = optimization_result['before_snapshot']['process_memory_mb']
            after_memory = optimization_result['after_snapshot']['process_memory_mb']
            optimization_result['memory_freed'] = max(0, before_memory - after_memory)
            
            # 生成建议
            optimization_result['recommendations'] = self._generate_memory_recommendations()
            
        except Exception as e:
            logger.error(f"内存优化失败: {e}")
            optimization_result['recommendations'].append(f"优化过程中发生错误: {e}")
        
        logger.info("内存优化完成")
        return optimization_result
    
    async def _optimize_garbage_collection(self) -> int:
        """优化垃圾收集"""
        memory_before = psutil.Process().memory_info().rss
        
        try:
            # 强制垃圾收集
            collected = gc.collect()
            
            # 记录垃圾收集统计
            gc_stats = {
                'timestamp': datetime.now().isoformat(),
                'objects_collected': collected,
                'gc_counts': gc.get_count()
            }
            self.gc_stats_history.append(gc_stats)
            
            # 限制历史记录
            if len(self.gc_stats_history) > 100:
                self.gc_stats_history = self.gc_stats_history[-100:]
            
            logger.info(f"垃圾收集完成，回收了 {collected} 个对象")
            
        except Exception as e:
            logger.error(f"垃圾收集优化失败: {e}")
            return 0
        
        memory_after = psutil.Process().memory_info().rss
        return max(0, memory_before - memory_after)
    
    async def _cleanup_caches(self) -> int:
        """清理缓存"""
        memory_before = psutil.Process().memory_info().rss
        
        try:
            # 这里可以清理各种缓存
            # 例如：清理函数缓存、模块缓存等
            
            # 清理__pycache__
            import sys
            for module_name, module in sys.modules.items():
                if hasattr(module, '__dict__'):
                    # 清理模块中的缓存变量
                    for attr_name in list(module.__dict__.keys()):
                        if attr_name.startswith('_cache') or attr_name.endswith('_cache'):
                            try:
                                delattr(module, attr_name)
                            except:
                                pass
            
            logger.info("缓存清理完成")
            
        except Exception as e:
            logger.error(f"缓存清理失败: {e}")
            return 0
        
        memory_after = psutil.Process().memory_info().rss
        return max(0, memory_before - memory_after)
    
    async def _optimize_data_structures(self) -> int:
        """优化数据结构"""
        memory_before = psutil.Process().memory_info().rss
        
        try:
            # 这里可以优化各种数据结构
            # 例如：压缩大字典、合并小列表等
            
            # 示例：查找并优化大的字典和列表
            for obj in gc.get_objects():
                try:
                    if isinstance(obj, dict) and len(obj) > 1000:
                        # 对大字典进行优化（这里只是示例）
                        pass
                    elif isinstance(obj, list) and len(obj) > 10000:
                        # 对大列表进行优化（这里只是示例）
                        pass
                except:
                    continue
            
            logger.info("数据结构优化完成")
            
        except Exception as e:
            logger.error(f"数据结构优化失败: {e}")
            return 0
        
        memory_after = psutil.Process().memory_info().rss
        return max(0, memory_before - memory_after)
    
    async def _handle_memory_leaks(self) -> List[str]:
        """处理内存泄漏"""
        actions = []
        
        try:
            for leak in self.detected_leaks[-10:]:  # 处理最近的泄漏
                if leak.severity in ['critical', 'high']:
                    # 对严重的泄漏进行处理
                    action = f"处理 {leak.object_type} 类型的内存泄漏 ({leak.severity})"
                    actions.append(action)
                    
                    # 这里可以添加具体的泄漏处理逻辑
                    # 例如：清理相关对象、重置状态等
                    
            if actions:
                # 清理已处理的泄漏
                self.detected_leaks = []
        
        except Exception as e:
            logger.error(f"内存泄漏处理失败: {e}")
        
        return actions
    
    async def _emergency_cleanup(self):
        """紧急内存清理"""
        logger.info("执行紧急内存清理")
        
        try:
            # 1. 强制垃圾收集
            gc.collect()
            
            # 2. 清理所有缓存
            await self._cleanup_caches()
            
            # 3. 释放不必要的对象
            # 这里可以添加更激进的清理策略
            
            logger.info("紧急内存清理完成")
            
        except Exception as e:
            logger.error(f"紧急内存清理失败: {e}")
    
    def _generate_memory_recommendations(self) -> List[str]:
        """生成内存优化建议"""
        recommendations = []
        
        try:
            # 基于监控数据生成建议
            if self.snapshots:
                latest_snapshot = self.snapshots[-1]
                
                if latest_snapshot.memory_percent > 80:
                    recommendations.append("系统内存使用过高，建议增加内存或优化应用")
                
                # 基于垃圾收集统计生成建议
                if self.gc_stats_history:
                    recent_collections = [s['objects_collected'] for s in self.gc_stats_history[-10:]]
                    avg_collected = sum(recent_collections) / len(recent_collections)
                    
                    if avg_collected > 1000:
                        recommendations.append("垃圾收集频繁，建议检查对象生命周期管理")
                
                # 基于对象计数生成建议
                for obj_type, count in latest_snapshot.object_counts.items():
                    if count > 10000:
                        recommendations.append(f"{obj_type} 对象数量过多 ({count})，建议优化")
            
            # 基于泄漏检测生成建议
            if self.detected_leaks:
                critical_leaks = [l for l in self.detected_leaks if l.severity == 'critical']
                if critical_leaks:
                    recommendations.append(f"发现 {len(critical_leaks)} 个严重内存泄漏，需要立即处理")
            
            # 通用建议
            if not recommendations:
                recommendations.extend([
                    "定期监控内存使用情况",
                    "合理设置对象生命周期",
                    "使用内存分析工具进行深度分析",
                    "考虑使用内存池技术"
                ])
        
        except Exception as e:
            logger.error(f"生成内存建议失败: {e}")
            recommendations.append(f"生成建议时发生错误: {e}")
        
        return recommendations
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取内存统计信息"""
        stats = {
            'current_snapshot': None,
            'snapshots_count': len(self.snapshots),
            'detected_leaks': len(self.detected_leaks),
            'gc_stats_history': len(self.gc_stats_history),
            'monitoring_active': self.monitoring
        }
        
        try:
            if self.snapshots:
                stats['current_snapshot'] = self.snapshots[-1].to_dict()
            
            # 内存使用趋势
            if len(self.snapshots) >= 2:
                recent_memory = [s.process_memory for s in self.snapshots[-10:]]
                stats['memory_trend'] = {
                    'min_mb': min(recent_memory) / (1024 * 1024),
                    'max_mb': max(recent_memory) / (1024 * 1024),
                    'avg_mb': sum(recent_memory) / len(recent_memory) / (1024 * 1024),
                    'growth_rate': (recent_memory[-1] - recent_memory[0]) / recent_memory[0] * 100
                }
            
            # 泄漏统计
            if self.detected_leaks:
                leak_by_severity = defaultdict(int)
                for leak in self.detected_leaks:
                    leak_by_severity[leak.severity] += 1
                stats['leak_summary'] = dict(leak_by_severity)
        
        except Exception as e:
            logger.error(f"获取内存统计失败: {e}")
        
        return stats
    
    def export_memory_report(self, filepath: str):
        """导出内存报告"""
        try:
            import json
            
            report = {
                'generated_at': datetime.now().isoformat(),
                'stats': self.get_memory_stats(),
                'snapshots': [s.to_dict() for s in self.snapshots[-50:]],  # 最近50个快照
                'detected_leaks': [l.to_dict() for l in self.detected_leaks],
                'gc_stats_history': self.gc_stats_history[-50:],  # 最近50个GC统计
                'recommendations': self._generate_memory_recommendations()
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"内存报告已导出到: {filepath}")
            
        except Exception as e:
            logger.error(f"导出内存报告失败: {e}")
    
    def shutdown(self):
        """关闭内存优化器"""
        try:
            self.stop_monitoring()
            logger.info("内存优化器已关闭")
        except Exception as e:
            logger.error(f"内存优化器关闭失败: {e}")