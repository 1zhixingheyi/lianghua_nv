"""
配置热更新管理器
支持运行时配置变更、版本管理和自动回滚
"""

import asyncio
import logging
import json
import yaml
import os
import shutil
import threading
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Set, Union
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict, deque
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import tempfile


@dataclass
class ConfigVersion:
    """配置版本信息"""
    version: str
    timestamp: float
    checksum: str
    description: str = ""
    author: str = ""
    changes: List[str] = field(default_factory=list)
    

@dataclass 
class ConfigItem:
    """配置项"""
    key: str
    value: Any
    version: str
    timestamp: float
    source: str = ""  # 配置来源文件


@dataclass
class ValidationRule:
    """配置验证规则"""
    key_pattern: str
    value_type: type
    required: bool = False
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    allowed_values: Optional[List[Any]] = None
    custom_validator: Optional[Callable] = None


@dataclass
class HotReloadConfig:
    """热更新配置"""
    watch_directories: List[str] = field(default_factory=list)
    watch_files: List[str] = field(default_factory=list)
    file_patterns: List[str] = field(default_factory=lambda: ["*.json", "*.yaml", "*.yml", "*.toml"])
    auto_reload: bool = True
    backup_count: int = 10
    validation_timeout: float = 30.0
    rollback_timeout: float = 300.0
    change_detection_interval: float = 1.0
    enable_version_control: bool = True
    enable_change_validation: bool = True


class ConfigChangeType:
    """配置变更类型"""
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class ConfigChange:
    """配置变更记录"""
    key: str
    change_type: str
    old_value: Any
    new_value: Any
    timestamp: float
    version: str
    source_file: str = ""
    

class ConfigFileHandler(FileSystemEventHandler):
    """配置文件监控处理器"""
    
    def __init__(self, hot_reload_manager):
        self.manager = hot_reload_manager
        self.logger = logging.getLogger(f"{__name__}.FileHandler")
        
    def on_modified(self, event):
        if event.is_directory:
            return
            
        file_path = event.src_path
        
        # 检查文件是否匹配监控模式
        if self.manager._should_monitor_file(file_path):
            self.logger.info(f"检测到配置文件变更: {file_path}")
            asyncio.create_task(self.manager._handle_file_change(file_path))
            
    def on_created(self, event):
        if not event.is_directory:
            self.on_modified(event)
            
    def on_deleted(self, event):
        if not event.is_directory:
            file_path = event.src_path
            if self.manager._should_monitor_file(file_path):
                self.logger.info(f"检测到配置文件删除: {file_path}")
                asyncio.create_task(self.manager._handle_file_deletion(file_path))


class ComponentConfigHandler:
    """组件配置处理器"""
    
    def __init__(self, component_name: str):
        self.component_name = component_name
        self.config_cache: Dict[str, Any] = {}
        self.change_callbacks: List[Callable] = []
        self.validation_rules: List[ValidationRule] = []
        self._lock = threading.Lock()
        
    def add_change_callback(self, callback: Callable):
        """添加配置变更回调"""
        self.change_callbacks.append(callback)
        
    def add_validation_rule(self, rule: ValidationRule):
        """添加验证规则"""
        self.validation_rules.append(rule)
        
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        with self._lock:
            return self.config_cache.get(key, default)
            
    def set_config(self, key: str, value: Any, version: str = "manual"):
        """设置配置值"""
        with self._lock:
            old_value = self.config_cache.get(key)
            self.config_cache[key] = value
            
            # 通知变更
            change = ConfigChange(
                key=key,
                change_type=ConfigChangeType.MODIFIED if key in self.config_cache else ConfigChangeType.ADDED,
                old_value=old_value,
                new_value=value,
                timestamp=time.time(),
                version=version
            )
            
            self._notify_change(change)
            
    def validate_config(self, key: str, value: Any) -> bool:
        """验证配置"""
        for rule in self.validation_rules:
            if self._matches_pattern(key, rule.key_pattern):
                if not self._validate_with_rule(key, value, rule):
                    return False
        return True
        
    def _matches_pattern(self, key: str, pattern: str) -> bool:
        """检查键是否匹配模式"""
        import fnmatch
        return fnmatch.fnmatch(key, pattern)
        
    def _validate_with_rule(self, key: str, value: Any, rule: ValidationRule) -> bool:
        """使用规则验证配置"""
        # 类型检查
        if not isinstance(value, rule.value_type):
            return False
            
        # 数值范围检查
        if rule.min_value is not None and value < rule.min_value:
            return False
        if rule.max_value is not None and value > rule.max_value:
            return False
            
        # 允许值检查
        if rule.allowed_values is not None and value not in rule.allowed_values:
            return False
            
        # 自定义验证器
        if rule.custom_validator and not rule.custom_validator(key, value):
            return False
            
        return True
        
    def _notify_change(self, change: ConfigChange):
        """通知配置变更"""
        for callback in self.change_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(change))
                else:
                    callback(change)
            except Exception as e:
                logging.getLogger(__name__).error(f"配置变更回调失败: {e}")


class HotReloadManager:
    """配置热更新管理器"""
    
    def __init__(self, config: Optional[HotReloadConfig] = None):
        self.config = config or HotReloadConfig()
        self.logger = logging.getLogger(__name__)
        
        # 配置存储
        self.configurations: Dict[str, Dict[str, Any]] = {}
        self.config_versions: Dict[str, List[ConfigVersion]] = defaultdict(list)
        self.config_items: Dict[str, ConfigItem] = {}
        self.change_history: deque = deque(maxlen=1000)
        
        # 组件处理器
        self.component_handlers: Dict[str, ComponentConfigHandler] = {}
        
        # 文件监控
        self.file_observer: Optional[Observer] = None
        self.file_handler: Optional[ConfigFileHandler] = None
        self.monitored_files: Set[str] = set()
        self.file_checksums: Dict[str, str] = {}
        
        # 控制变量
        self.is_running = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        # 回调函数
        self.global_change_callbacks: List[Callable] = []
        self.validation_callbacks: List[Callable] = []
        
        # 版本管理
        self.current_version = "1.0.0"
        self.version_counter = 1
        
        # 备份管理
        self.backup_directory = "config_backups"
        self._ensure_backup_directory()
        
        # 统计信息
        self.stats = {
            'files_monitored': 0,
            'changes_detected': 0,
            'successful_reloads': 0,
            'failed_reloads': 0,
            'rollbacks_performed': 0,
            'validation_errors': 0,
            'start_time': time.time()
        }
        
        self._lock = threading.Lock()
        
    def _ensure_backup_directory(self):
        """确保备份目录存在"""
        Path(self.backup_directory).mkdir(parents=True, exist_ok=True)
        
    def register_component(self, component_name: str) -> ComponentConfigHandler:
        """注册组件配置处理器"""
        handler = ComponentConfigHandler(component_name)
        self.component_handlers[component_name] = handler
        return handler
        
    def add_global_change_callback(self, callback: Callable):
        """添加全局配置变更回调"""
        self.global_change_callbacks.append(callback)
        
    def add_validation_callback(self, callback: Callable):
        """添加验证回调"""
        self.validation_callbacks.append(callback)
        
    async def start_monitoring(self):
        """开始监控"""
        if self.is_running:
            self.logger.warning("配置监控已在运行")
            return
            
        self.is_running = True
        self.stats['start_time'] = time.time()
        
        # 加载初始配置
        await self._load_initial_configs()
        
        # 启动文件监控
        if self.config.auto_reload:
            self._start_file_monitoring()
            
        # 启动定期检查任务
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        
        self.logger.info("配置热更新监控已启动")
        
    async def stop_monitoring(self):
        """停止监控"""
        self.is_running = False
        
        if self.file_observer:
            self.file_observer.stop()
            self.file_observer.join()
            
        if self.monitor_task:
            self.monitor_task.cancel()
            
        self.logger.info("配置热更新监控已停止")
        
    def _start_file_monitoring(self):
        """启动文件监控"""
        if self.file_observer:
            return
            
        self.file_observer = Observer()
        self.file_handler = ConfigFileHandler(self)
        
        # 监控目录
        for directory in self.config.watch_directories:
            if os.path.exists(directory):
                self.file_observer.schedule(
                    self.file_handler, 
                    directory, 
                    recursive=True
                )
                self.logger.info(f"开始监控目录: {directory}")
                
        # 监控文件
        for file_path in self.config.watch_files:
            if os.path.exists(file_path):
                directory = os.path.dirname(file_path)
                self.file_observer.schedule(
                    self.file_handler,
                    directory,
                    recursive=False
                )
                self.monitored_files.add(file_path)
                self.logger.info(f"开始监控文件: {file_path}")
                
        self.file_observer.start()
        
    async def _load_initial_configs(self):
        """加载初始配置"""
        # 加载监控目录中的配置文件
        for directory in self.config.watch_directories:
            await self._load_configs_from_directory(directory)
            
        # 加载监控文件
        for file_path in self.config.watch_files:
            if os.path.exists(file_path):
                await self._load_config_file(file_path)
                
    async def _load_configs_from_directory(self, directory: str):
        """从目录加载配置"""
        if not os.path.exists(directory):
            return
            
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                if self._should_monitor_file(file_path):
                    await self._load_config_file(file_path)
                    
    async def _load_config_file(self, file_path: str):
        """加载配置文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 计算文件校验和
            checksum = hashlib.md5(content.encode()).hexdigest()
            self.file_checksums[file_path] = checksum
            
            # 解析配置
            config_data = self._parse_config_file(file_path, content)
            
            if config_data:
                # 创建版本
                version = self._create_version(
                    f"v{self.version_counter}",
                    f"初始加载: {os.path.basename(file_path)}"
                )
                
                # 更新配置
                await self._update_configuration(file_path, config_data, version.version)
                
                self.stats['files_monitored'] += 1
                self.logger.info(f"加载配置文件: {file_path}")
                
        except Exception as e:
            self.logger.error(f"加载配置文件失败 {file_path}: {e}")
            
    def _parse_config_file(self, file_path: str, content: str) -> Optional[Dict[str, Any]]:
        """解析配置文件"""
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if file_ext == '.json':
                return json.loads(content)
            elif file_ext in ['.yaml', '.yml']:
                return yaml.safe_load(content)
            elif file_ext == '.toml':
                import toml
                return toml.loads(content)
            else:
                self.logger.warning(f"不支持的配置文件格式: {file_ext}")
                return None
        except Exception as e:
            self.logger.error(f"解析配置文件失败 {file_path}: {e}")
            return None
            
    def _should_monitor_file(self, file_path: str) -> bool:
        """检查是否应该监控文件"""
        # 检查文件扩展名
        file_ext = os.path.splitext(file_path)[1]
        
        for pattern in self.config.file_patterns:
            import fnmatch
            if fnmatch.fnmatch(os.path.basename(file_path), pattern):
                return True
                
        # 检查是否在监控文件列表中
        return file_path in self.monitored_files
        
    async def _monitoring_loop(self):
        """监控循环"""
        while self.is_running:
            try:
                # 检查文件变更
                await self._check_file_changes()
                
                # 清理过期备份
                self._cleanup_old_backups()
                
                await asyncio.sleep(self.config.change_detection_interval)
                
            except Exception as e:
                self.logger.error(f"监控循环异常: {e}")
                await asyncio.sleep(self.config.change_detection_interval)
                
    async def _check_file_changes(self):
        """检查文件变更"""
        for file_path in list(self.file_checksums.keys()):
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    current_checksum = hashlib.md5(content.encode()).hexdigest()
                    old_checksum = self.file_checksums.get(file_path, "")
                    
                    if current_checksum != old_checksum:
                        await self._handle_file_change(file_path)
                        
                except Exception as e:
                    self.logger.error(f"检查文件变更失败 {file_path}: {e}")
                    
    async def _handle_file_change(self, file_path: str):
        """处理文件变更"""
        try:
            self.stats['changes_detected'] += 1
            
            # 创建备份
            backup_path = await self._create_backup(file_path)
            
            # 加载新配置
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            new_config = self._parse_config_file(file_path, content)
            
            if new_config is None:
                self.logger.error(f"解析新配置失败: {file_path}")
                return
                
            # 验证配置
            if not await self._validate_configuration(file_path, new_config):
                self.logger.error(f"配置验证失败: {file_path}")
                self.stats['validation_errors'] += 1
                return
                
            # 创建新版本
            version = self._create_version(
                f"v{self.version_counter}",
                f"热更新: {os.path.basename(file_path)}"
            )
            
            # 更新配置
            await self._update_configuration(file_path, new_config, version.version)
            
            # 更新校验和
            self.file_checksums[file_path] = hashlib.md5(content.encode()).hexdigest()
            
            self.stats['successful_reloads'] += 1
            self.logger.info(f"配置热更新成功: {file_path}")
            
        except Exception as e:
            self.stats['failed_reloads'] += 1
            self.logger.error(f"配置热更新失败 {file_path}: {e}")
            
            # 尝试回滚
            if backup_path and os.path.exists(backup_path):
                await self._rollback_config(file_path, backup_path)
                
    async def _handle_file_deletion(self, file_path: str):
        """处理文件删除"""
        self.logger.info(f"配置文件被删除: {file_path}")
        
        # 从监控中移除
        if file_path in self.file_checksums:
            del self.file_checksums[file_path]
            
        # 清理相关配置
        config_key = self._get_config_key_from_path(file_path)
        if config_key in self.configurations:
            del self.configurations[config_key]
            
    async def _create_backup(self, file_path: str) -> str:
        """创建配置备份"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.basename(file_path)
        backup_filename = f"{filename}.{timestamp}.backup"
        backup_path = os.path.join(self.backup_directory, backup_filename)
        
        shutil.copy2(file_path, backup_path)
        return backup_path
        
    async def _validate_configuration(self, file_path: str, config_data: Dict[str, Any]) -> bool:
        """验证配置"""
        try:
            # 执行验证回调
            for callback in self.validation_callbacks:
                if asyncio.iscoroutinefunction(callback):
                    result = await asyncio.wait_for(
                        callback(file_path, config_data),
                        timeout=self.config.validation_timeout
                    )
                else:
                    result = callback(file_path, config_data)
                    
                if not result:
                    return False
                    
            return True
            
        except Exception as e:
            self.logger.error(f"配置验证异常: {e}")
            return False
            
    async def _update_configuration(self, file_path: str, config_data: Dict[str, Any], version: str):
        """更新配置"""
        config_key = self._get_config_key_from_path(file_path)
        
        with self._lock:
            old_config = self.configurations.get(config_key, {})
            self.configurations[config_key] = config_data
            
            # 记录变更
            changes = self._detect_changes(old_config, config_data)
            for change in changes:
                change.version = version
                change.source_file = file_path
                self.change_history.append(change)
                
            # 更新配置项
            for key, value in config_data.items():
                full_key = f"{config_key}.{key}" if config_key else key
                self.config_items[full_key] = ConfigItem(
                    key=full_key,
                    value=value,
                    version=version,
                    timestamp=time.time(),
                    source=file_path
                )
                
        # 通知组件配置变更
        await self._notify_config_changes(config_key, changes)
        
        # 通知全局变更
        for callback in self.global_change_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(config_key, config_data, version)
                else:
                    callback(config_key, config_data, version)
            except Exception as e:
                self.logger.error(f"全局配置变更回调失败: {e}")
                
    def _get_config_key_from_path(self, file_path: str) -> str:
        """从文件路径获取配置键"""
        # 使用文件名（不含扩展名）作为配置键
        return os.path.splitext(os.path.basename(file_path))[0]
        
    def _detect_changes(self, old_config: Dict[str, Any], new_config: Dict[str, Any]) -> List[ConfigChange]:
        """检测配置变更"""
        changes = []
        current_time = time.time()
        
        # 检查新增和修改
        for key, new_value in new_config.items():
            if key not in old_config:
                changes.append(ConfigChange(
                    key=key,
                    change_type=ConfigChangeType.ADDED,
                    old_value=None,
                    new_value=new_value,
                    timestamp=current_time,
                    version=""
                ))
            elif old_config[key] != new_value:
                changes.append(ConfigChange(
                    key=key,
                    change_type=ConfigChangeType.MODIFIED,
                    old_value=old_config[key],
                    new_value=new_value,
                    timestamp=current_time,
                    version=""
                ))
                
        # 检查删除
        for key, old_value in old_config.items():
            if key not in new_config:
                changes.append(ConfigChange(
                    key=key,
                    change_type=ConfigChangeType.DELETED,
                    old_value=old_value,
                    new_value=None,
                    timestamp=current_time,
                    version=""
                ))
                
        return changes
        
    async def _notify_config_changes(self, config_key: str, changes: List[ConfigChange]):
        """通知配置变更"""
        for component_name, handler in self.component_handlers.items():
            # 检查组件是否关心这个配置
            if self._component_cares_about_config(component_name, config_key):
                for change in changes:
                    await self._notify_component_change(handler, change)
                    
    def _component_cares_about_config(self, component_name: str, config_key: str) -> bool:
        """检查组件是否关心某个配置"""
        # 可以根据命名约定或配置映射来判断
        # 简单实现：组件名匹配配置键
        return component_name.lower() in config_key.lower() or config_key.lower() in component_name.lower()
        
    async def _notify_component_change(self, handler: ComponentConfigHandler, change: ConfigChange):
        """通知组件配置变更"""
        # 更新组件配置缓存
        if change.change_type == ConfigChangeType.DELETED:
            if change.key in handler.config_cache:
                del handler.config_cache[change.key]
        else:
            handler.config_cache[change.key] = change.new_value
            
        # 触发组件回调
        handler._notify_change(change)
        
    def _create_version(self, version: str, description: str) -> ConfigVersion:
        """创建配置版本"""
        config_version = ConfigVersion(
            version=version,
            timestamp=time.time(),
            checksum="",  # 可以根据需要计算
            description=description,
            author="system"
        )
        
        self.version_counter += 1
        return config_version
        
    async def _rollback_config(self, file_path: str, backup_path: str):
        """回滚配置"""
        try:
            self.stats['rollbacks_performed'] += 1
            
            # 恢复文件
            shutil.copy2(backup_path, file_path)
            
            # 重新加载配置
            await self._load_config_file(file_path)
            
            self.logger.info(f"配置回滚成功: {file_path}")
            
        except Exception as e:
            self.logger.error(f"配置回滚失败 {file_path}: {e}")
            
    def _cleanup_old_backups(self):
        """清理过期备份"""
        try:
            backup_files = []
            for file in os.listdir(self.backup_directory):
                if file.endswith('.backup'):
                    backup_path = os.path.join(self.backup_directory, file)
                    backup_files.append((backup_path, os.path.getmtime(backup_path)))
                    
            # 按时间排序，保留最新的几个
            backup_files.sort(key=lambda x: x[1], reverse=True)
            
            if len(backup_files) > self.config.backup_count:
                for backup_path, _ in backup_files[self.config.backup_count:]:
                    os.remove(backup_path)
                    self.logger.debug(f"删除过期备份: {backup_path}")
                    
        except Exception as e:
            self.logger.error(f"清理备份失败: {e}")
            
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        with self._lock:
            if key in self.config_items:
                return self.config_items[key].value
            return default
            
    def set_config(self, key: str, value: Any, persist: bool = False) -> bool:
        """设置配置值"""
        try:
            with self._lock:
                # 更新内存中的配置
                item = ConfigItem(
                    key=key,
                    value=value,
                    version=f"v{self.version_counter}",
                    timestamp=time.time(),
                    source="manual"
                )
                self.config_items[key] = item
                
            # 如果需要持久化，写入文件
            if persist:
                # 这里可以实现配置持久化逻辑
                pass
                
            self.logger.info(f"设置配置: {key} = {value}")
            return True
            
        except Exception as e:
            self.logger.error(f"设置配置失败 {key}: {e}")
            return False
            
    def get_configuration(self, config_key: str) -> Optional[Dict[str, Any]]:
        """获取配置组"""
        with self._lock:
            return self.configurations.get(config_key)
            
    def get_change_history(self, limit: int = 100) -> List[ConfigChange]:
        """获取变更历史"""
        return list(self.change_history)[-limit:]
        
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = time.time() - self.stats['start_time']
        
        return {
            **self.stats,
            'uptime_seconds': uptime,
            'uptime_hours': uptime / 3600,
            'configurations_count': len(self.configurations),
            'config_items_count': len(self.config_items),
            'component_handlers_count': len(self.component_handlers),
            'change_history_size': len(self.change_history),
            'reload_success_rate': (
                self.stats['successful_reloads'] / max(1, self.stats['changes_detected'])
            )
        }
        
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            'status': 'running' if self.is_running else 'stopped',
            'files_monitored': self.stats['files_monitored'],
            'last_change_time': max([
                change.timestamp for change in self.change_history
            ]) if self.change_history else 0,
            'configurations_loaded': len(self.configurations) > 0,
            'file_observer_active': self.file_observer is not None and self.file_observer.is_alive()
        }


# 单例模式的管理器实例
_hot_reload_manager_instance: Optional[HotReloadManager] = None

def get_hot_reload_manager(config: Optional[HotReloadConfig] = None) -> HotReloadManager:
    """获取热更新管理器单例实例"""
    global _hot_reload_manager_instance
    if _hot_reload_manager_instance is None:
        _hot_reload_manager_instance = HotReloadManager(config)
    return _hot_reload_manager_instance


if __name__ == "__main__":
    import asyncio
    
    async def config_validator(file_path: str, config_data: Dict[str, Any]) -> bool:
        # 示例验证器
        print(f"验证配置文件: {file_path}")
        return True
        
    async def config_change_handler(config_key: str, config_data: Dict[str, Any], version: str):
        print(f"配置变更: {config_key} -> {version}")
        
    async def main():
        config = HotReloadConfig(
            watch_directories=["./config"],
            watch_files=["./app.json"],
            auto_reload=True
        )
        
        manager = HotReloadManager(config)
        manager.add_validation_callback(config_validator)
        manager.add_global_change_callback(config_change_handler)
        
        # 注册组件
        app_handler = manager.register_component("app")
        
        await manager.start_monitoring()
        
        try:
            await asyncio.sleep(300)  # 运行5分钟
        finally:
            await manager.stop_monitoring()
            
        print("管理器统计:", manager.get_statistics())
        
    asyncio.run(main())