"""
缓存管理器

负责管理系统缓存，包括内存缓存、Redis缓存等
"""

import asyncio
import logging
import time
import json
import threading
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from collections import OrderedDict
import hashlib

logger = logging.getLogger(__name__)


class CacheStats:
    """缓存统计信息"""
    
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.evictions = 0
        self.memory_usage = 0
        self.start_time = datetime.now()
    
    @property
    def hit_rate(self) -> float:
        """缓存命中率"""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0
    
    @property
    def miss_rate(self) -> float:
        """缓存未命中率"""
        return 100.0 - self.hit_rate
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'hits': self.hits,
            'misses': self.misses,
            'sets': self.sets,
            'deletes': self.deletes,
            'evictions': self.evictions,
            'memory_usage': self.memory_usage,
            'hit_rate': self.hit_rate,
            'miss_rate': self.miss_rate,
            'uptime_seconds': (datetime.now() - self.start_time).total_seconds()
        }


class CacheItem:
    """缓存项"""
    
    def __init__(self, key: str, value: Any, ttl: Optional[int] = None):
        self.key = key
        self.value = value
        self.created_at = datetime.now()
        self.accessed_at = self.created_at
        self.access_count = 0
        self.ttl = ttl
        self.expires_at = self.created_at + timedelta(seconds=ttl) if ttl else None
    
    @property
    def is_expired(self) -> bool:
        """是否过期"""
        return self.expires_at and datetime.now() > self.expires_at
    
    @property
    def age_seconds(self) -> float:
        """存活时间(秒)"""
        return (datetime.now() - self.created_at).total_seconds()
    
    def access(self):
        """访问缓存项"""
        self.accessed_at = datetime.now()
        self.access_count += 1


class LRUCache:
    """LRU内存缓存"""
    
    def __init__(self, max_size: int = 1000, default_ttl: Optional[int] = None):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache = OrderedDict()
        self.stats = CacheStats()
        self.lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self.lock:
            if key not in self.cache:
                self.stats.misses += 1
                return None
            
            item = self.cache[key]
            
            # 检查是否过期
            if item.is_expired:
                del self.cache[key]
                self.stats.misses += 1
                self.stats.evictions += 1
                return None
            
            # 更新访问信息
            item.access()
            
            # 移动到末尾（最近使用）
            self.cache.move_to_end(key)
            
            self.stats.hits += 1
            return item.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        with self.lock:
            ttl = ttl or self.default_ttl
            item = CacheItem(key, value, ttl)
            
            # 如果key已存在，更新它
            if key in self.cache:
                del self.cache[key]
            
            # 检查是否需要清理空间
            while len(self.cache) >= self.max_size:
                # 删除最旧的项
                oldest_key, _ = self.cache.popitem(last=False)
                self.stats.evictions += 1
            
            self.cache[key] = item
            self.stats.sets += 1
            self._update_memory_usage()
            
            return True
    
    def delete(self, key: str) -> bool:
        """删除缓存项"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                self.stats.deletes += 1
                self._update_memory_usage()
                return True
            return False
    
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.stats = CacheStats()
    
    def keys(self) -> List[str]:
        """获取所有key"""
        with self.lock:
            return list(self.cache.keys())
    
    def size(self) -> int:
        """获取缓存大小"""
        with self.lock:
            return len(self.cache)
    
    def cleanup_expired(self) -> int:
        """清理过期项"""
        with self.lock:
            expired_keys = []
            for key, item in self.cache.items():
                if item.is_expired:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
                self.stats.evictions += 1
            
            if expired_keys:
                self._update_memory_usage()
            
            return len(expired_keys)
    
    def get_stats(self) -> CacheStats:
        """获取统计信息"""
        return self.stats
    
    def _update_memory_usage(self):
        """更新内存使用统计"""
        # 简单估算内存使用量
        total_size = 0
        for key, item in self.cache.items():
            total_size += len(str(key)) + len(str(item.value))
        self.stats.memory_usage = total_size


class CacheManager:
    """缓存管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 缓存配置
        self.cache_config = {
            'memory_cache': {
                'enabled': True,
                'max_size': 1000,
                'default_ttl': 3600,  # 1小时
                'cleanup_interval': 300  # 5分钟
            },
            'redis_cache': {
                'enabled': False,
                'host': 'localhost',
                'port': 6379,
                'db': 0,
                'default_ttl': 7200  # 2小时
            },
            'cache_layers': {
                'stock_data': {
                    'layer': 'memory',
                    'ttl': 300,  # 5分钟
                    'max_size': 500
                },
                'strategy_results': {
                    'layer': 'memory',
                    'ttl': 600,  # 10分钟
                    'max_size': 200
                },
                'market_data': {
                    'layer': 'memory',
                    'ttl': 60,   # 1分钟
                    'max_size': 1000
                }
            }
        }
        
        # 更新配置
        if 'cache' in config:
            self.cache_config.update(config['cache'])
        
        # 初始化缓存
        self.memory_caches = {}
        self.redis_client = None
        self.cleanup_task = None
        
        self._init_caches()
    
    def _init_caches(self):
        """初始化缓存"""
        # 初始化内存缓存
        if self.cache_config['memory_cache']['enabled']:
            # 为每个缓存层创建独立的LRU缓存
            for layer_name, layer_config in self.cache_config['cache_layers'].items():
                if layer_config['layer'] == 'memory':
                    self.memory_caches[layer_name] = LRUCache(
                        max_size=layer_config.get('max_size', self.cache_config['memory_cache']['max_size']),
                        default_ttl=layer_config.get('ttl', self.cache_config['memory_cache']['default_ttl'])
                    )
            
            # 启动清理任务
            self._start_cleanup_task()
        
        # 初始化Redis缓存
        if self.cache_config['redis_cache']['enabled']:
            self._init_redis()
    
    def _init_redis(self):
        """初始化Redis连接"""
        try:
            import redis
            self.redis_client = redis.Redis(
                host=self.cache_config['redis_cache']['host'],
                port=self.cache_config['redis_cache']['port'],
                db=self.cache_config['redis_cache']['db'],
                decode_responses=True
            )
            # 测试连接
            self.redis_client.ping()
            logger.info("Redis缓存连接成功")
        except Exception as e:
            logger.warning(f"Redis缓存连接失败: {e}")
            self.redis_client = None
    
    def _start_cleanup_task(self):
        """启动清理任务"""
        def cleanup_loop():
            while True:
                try:
                    time.sleep(self.cache_config['memory_cache']['cleanup_interval'])
                    self.cleanup_expired()
                except Exception as e:
                    logger.error(f"缓存清理任务异常: {e}")
        
        self.cleanup_task = threading.Thread(target=cleanup_loop, daemon=True)
        self.cleanup_task.start()
        logger.info("缓存清理任务已启动")
    
    def get(self, key: str, layer: str = 'default') -> Optional[Any]:
        """获取缓存值"""
        try:
            # 尝试从内存缓存获取
            if layer in self.memory_caches:
                value = self.memory_caches[layer].get(key)
                if value is not None:
                    return value
            
            # 尝试从Redis获取
            if self.redis_client:
                try:
                    value_str = self.redis_client.get(self._redis_key(key, layer))
                    if value_str:
                        value = json.loads(value_str)
                        # 回写到内存缓存
                        if layer in self.memory_caches:
                            layer_config = self.cache_config['cache_layers'].get(layer, {})
                            ttl = layer_config.get('ttl')
                            self.memory_caches[layer].set(key, value, ttl)
                        return value
                except Exception as e:
                    logger.error(f"Redis获取失败: {e}")
            
            return None
            
        except Exception as e:
            logger.error(f"缓存获取失败: {e}")
            return None
    
    def set(self, key: str, value: Any, layer: str = 'default', ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        try:
            success = False
            
            # 设置到内存缓存
            if layer in self.memory_caches:
                success = self.memory_caches[layer].set(key, value, ttl)
            
            # 设置到Redis
            if self.redis_client:
                try:
                    value_str = json.dumps(value, default=str)
                    redis_ttl = ttl or self.cache_config['redis_cache']['default_ttl']
                    self.redis_client.setex(
                        self._redis_key(key, layer),
                        redis_ttl,
                        value_str
                    )
                    success = True
                except Exception as e:
                    logger.error(f"Redis设置失败: {e}")
            
            return success
            
        except Exception as e:
            logger.error(f"缓存设置失败: {e}")
            return False
    
    def delete(self, key: str, layer: str = 'default') -> bool:
        """删除缓存项"""
        try:
            success = False
            
            # 从内存缓存删除
            if layer in self.memory_caches:
                success = self.memory_caches[layer].delete(key)
            
            # 从Redis删除
            if self.redis_client:
                try:
                    deleted = self.redis_client.delete(self._redis_key(key, layer))
                    success = success or (deleted > 0)
                except Exception as e:
                    logger.error(f"Redis删除失败: {e}")
            
            return success
            
        except Exception as e:
            logger.error(f"缓存删除失败: {e}")
            return False
    
    def clear(self, layer: Optional[str] = None):
        """清空缓存"""
        try:
            if layer:
                # 清空指定层
                if layer in self.memory_caches:
                    self.memory_caches[layer].clear()
                
                if self.redis_client:
                    try:
                        pattern = f"cache:{layer}:*"
                        keys = self.redis_client.keys(pattern)
                        if keys:
                            self.redis_client.delete(*keys)
                    except Exception as e:
                        logger.error(f"Redis清空失败: {e}")
            else:
                # 清空所有层
                for cache in self.memory_caches.values():
                    cache.clear()
                
                if self.redis_client:
                    try:
                        keys = self.redis_client.keys("cache:*")
                        if keys:
                            self.redis_client.delete(*keys)
                    except Exception as e:
                        logger.error(f"Redis清空失败: {e}")
            
            logger.info(f"缓存已清空: {layer or 'all'}")
            
        except Exception as e:
            logger.error(f"缓存清空失败: {e}")
    
    def cleanup_expired(self) -> int:
        """清理过期项"""
        total_cleaned = 0
        
        try:
            # 清理内存缓存
            for layer_name, cache in self.memory_caches.items():
                cleaned = cache.cleanup_expired()
                total_cleaned += cleaned
                if cleaned > 0:
                    logger.debug(f"内存缓存{layer_name}清理了{cleaned}个过期项")
            
            # Redis会自动清理过期项，无需手动处理
            
        except Exception as e:
            logger.error(f"缓存清理失败: {e}")
        
        return total_cleaned
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        stats = {
            'memory_caches': {},
            'redis_cache': None,
            'total_memory_usage': 0,
            'total_items': 0
        }
        
        try:
            # 内存缓存统计
            for layer_name, cache in self.memory_caches.items():
                cache_stats = cache.get_stats()
                stats['memory_caches'][layer_name] = cache_stats.to_dict()
                stats['total_memory_usage'] += cache_stats.memory_usage
                stats['total_items'] += cache.size()
            
            # Redis统计
            if self.redis_client:
                try:
                    redis_info = self.redis_client.info()
                    stats['redis_cache'] = {
                        'connected': True,
                        'used_memory': redis_info.get('used_memory', 0),
                        'connected_clients': redis_info.get('connected_clients', 0),
                        'total_commands_processed': redis_info.get('total_commands_processed', 0)
                    }
                except Exception as e:
                    stats['redis_cache'] = {'connected': False, 'error': str(e)}
            
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
        
        return stats
    
    def optimize_cache(self) -> Dict[str, Any]:
        """优化缓存配置"""
        optimization_result = {
            'actions_taken': [],
            'recommendations': [],
            'stats_before': self.get_stats(),
            'stats_after': None
        }
        
        try:
            # 分析缓存使用情况
            for layer_name, cache in self.memory_caches.items():
                stats = cache.get_stats()
                
                # 如果命中率低于50%，建议调整TTL
                if stats.hit_rate < 50:
                    optimization_result['recommendations'].append(
                        f"{layer_name}缓存命中率过低({stats.hit_rate:.1f}%)，建议增加TTL"
                    )
                
                # 如果逐出率高，建议增加缓存大小
                if stats.evictions > stats.sets * 0.1:
                    optimization_result['recommendations'].append(
                        f"{layer_name}缓存逐出率过高，建议增加最大缓存大小"
                    )
                
                # 清理过期项
                cleaned = cache.cleanup_expired()
                if cleaned > 0:
                    optimization_result['actions_taken'].append(
                        f"清理{layer_name}缓存中的{cleaned}个过期项"
                    )
            
            # 获取优化后的统计
            optimization_result['stats_after'] = self.get_stats()
            
        except Exception as e:
            logger.error(f"缓存优化失败: {e}")
            optimization_result['recommendations'].append(f"优化过程中发生错误: {e}")
        
        return optimization_result
    
    def _redis_key(self, key: str, layer: str) -> str:
        """生成Redis key"""
        return f"cache:{layer}:{key}"
    
    def _cache_key(self, prefix: str, *args) -> str:
        """生成缓存key"""
        key_parts = [prefix] + [str(arg) for arg in args]
        key_str = ":".join(key_parts)
        
        # 如果key太长，使用hash
        if len(key_str) > 200:
            key_hash = hashlib.md5(key_str.encode()).hexdigest()
            return f"{prefix}:hash:{key_hash}"
        
        return key_str
    
    # 便捷方法
    def cache_stock_data(self, symbol: str, data: Any, ttl: Optional[int] = None) -> bool:
        """缓存股票数据"""
        key = self._cache_key("stock", symbol)
        return self.set(key, data, "stock_data", ttl)
    
    def get_stock_data(self, symbol: str) -> Optional[Any]:
        """获取股票数据"""
        key = self._cache_key("stock", symbol)
        return self.get(key, "stock_data")
    
    def cache_strategy_result(self, strategy_name: str, symbol: str, result: Any, ttl: Optional[int] = None) -> bool:
        """缓存策略结果"""
        key = self._cache_key("strategy", strategy_name, symbol)
        return self.set(key, result, "strategy_results", ttl)
    
    def get_strategy_result(self, strategy_name: str, symbol: str) -> Optional[Any]:
        """获取策略结果"""
        key = self._cache_key("strategy", strategy_name, symbol)
        return self.get(key, "strategy_results")
    
    def cache_market_data(self, data_type: str, data: Any, ttl: Optional[int] = None) -> bool:
        """缓存市场数据"""
        key = self._cache_key("market", data_type)
        return self.set(key, data, "market_data", ttl)
    
    def get_market_data(self, data_type: str) -> Optional[Any]:
        """获取市场数据"""
        key = self._cache_key("market", data_type)
        return self.get(key, "market_data")
    
    def shutdown(self):
        """关闭缓存管理器"""
        try:
            # 停止清理任务
            if self.cleanup_task and self.cleanup_task.is_alive():
                # 这里应该有一个停止标志，但为了简化，我们只记录日志
                logger.info("缓存清理任务将在后台继续运行")
            
            # 关闭Redis连接
            if self.redis_client:
                self.redis_client.close()
                logger.info("Redis连接已关闭")
            
        except Exception as e:
            logger.error(f"缓存管理器关闭失败: {e}")