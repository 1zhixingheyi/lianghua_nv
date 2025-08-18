#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一配置管理器

功能：
1. 加载和解析YAML配置文件
2. 配置验证和校验
3. 环境变量替换
4. 配置热更新
5. 配置缓存管理
6. 多环境配置支持

支持的配置文件：
- database.yaml: 数据库配置
- api.yaml: API配置
- cache.yaml: 缓存配置
- logging.yaml: 日志配置
- trading.yaml: 交易配置
- system.yaml: 系统配置
- data.yaml: 数据源配置

作者: 量化交易系统
日期: 2025-01-01
版本: 3.0.0
"""

import logging
import os
import re
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional, Union

import yaml

# 加载.env文件支持
try:
    from dotenv import load_dotenv
    _DOTENV_AVAILABLE = True
except ImportError:
    _DOTENV_AVAILABLE = False


class ConfigValidationError(Exception):
    """配置验证错误"""
    pass


class ConfigLoadError(Exception):
    """配置加载错误"""
    pass


class ConfigManager:
    """
    统一配置管理器

    负责管理系统所有配置文件的加载、验证、缓存和热更新
    """

    def __init__(self, config_dir: Optional[str] = None, environment: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            config_dir: 配置文件目录，默认为当前目录
            environment: 运行环境，默认从环境变量ENVIRONMENT获取
        """
        self.logger = logging.getLogger(__name__)

        # 设置配置目录
        if config_dir is None:
            self.config_dir = Path(__file__).parent
        else:
            self.config_dir = Path(config_dir)
        
        self.schemas_dir = self.config_dir / "schemas"

        # 设置运行环境
        self.environment = environment or os.getenv("ENVIRONMENT", "development")

        # 配置缓存
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        self._file_timestamps: Dict[str, float] = {}
        self._cache_lock = Lock()

        # 新架构：支持的配置文件映射
        self.modules_dir = self.config_dir / "modules"
        
        # 存储层配置文件（schemas目录）
        self.storage_configs = {
            "mysql": self.schemas_dir / "mysql.yaml",
            "clickhouse": self.schemas_dir / "clickhouse.yaml",
            "redis": self.schemas_dir / "redis.yaml",
            "minio": self.schemas_dir / "minio.yaml",
        }
        
        # 业务模块配置文件（modules目录）
        self.module_configs = {
            "trading": self.modules_dir / "trading.yaml",
            "data_integrity": self.modules_dir / "data_integrity.yaml",
        }
        
        # 系统级配置文件（schemas目录）
        self.system_configs = {
            "api": self.schemas_dir / "api.yaml",
            "cache": self.schemas_dir / "cache.yaml",
            "logging": self.schemas_dir / "logging.yaml",
            "system": self.schemas_dir / "system.yaml",
            "data": self.schemas_dir / "data.yaml",
        }
        
        # 合并所有配置文件映射（保持向后兼容）
        self.config_files = {
            **self.storage_configs,
            **self.module_configs,
            **self.system_configs,
            # 向后兼容的别名
            "database": self.storage_configs["mysql"],  # database现在指向mysql
            "storage": self.storage_configs["mysql"],   # storage现在指向mysql
        }

        # 初始化
        self._load_env_file()
        self.load_all_configs()  # 自动加载所有配置
        
        self.logger.info(
            f"配置管理器初始化完成，配置目录: {self.config_dir}, 环境: {self.environment}"
        )

    def _load_env_file(self) -> None:
        """加载.env文件"""
        if not _DOTENV_AVAILABLE:
            self.logger.warning("python-dotenv未安装，无法加载.env文件")
            return

        # 从config目录加载.env文件
        env_file = self.config_dir / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            self.logger.info(f"已加载环境变量文件: {env_file}")
        else:
            self.logger.warning(f"未找到.env文件: {env_file}")

    def load_all_configs(self) -> None:
        """加载所有YAML配置文件"""
        self.logger.info("开始加载配置文件...")

        for config_type, config_path in self.config_files.items():
            try:
                config_data = self._load_yaml_config(config_path)
                if config_data:
                    with self._cache_lock:
                        self._config_cache[config_type] = config_data
                    self.logger.info(f"配置文件 {config_path.name} 加载成功")
                else:
                    self.logger.warning(f"配置文件 {config_path.name} 为空或不存在")
            except Exception as e:
                self.logger.error(f"加载配置文件 {config_path.name} 失败: {e}")
                # 对于关键配置文件，抛出异常
                if config_type in ["database", "system"]:
                    raise ConfigLoadError(f"关键配置文件 {config_path.name} 加载失败: {e}")

        self.logger.info("所有配置文件加载完成")

    def _get_config_type_by_path(self, config_path: Path) -> Optional[str]:
        """根据文件路径确定配置类型"""
        for config_type, path in self.config_files.items():
            if path == config_path:
                return config_type
        return None

    def _load_yaml_config(self, config_path: Path) -> Optional[Dict[str, Any]]:
        """加载单个YAML配置文件"""
        if not config_path.exists():
            self.logger.warning(f"配置文件不存在: {config_path}")
            return None

        # 检查文件修改时间
        mtime = config_path.stat().st_mtime
        if str(config_path) in self._file_timestamps:
            if self._file_timestamps[str(config_path)] == mtime:
                # 文件未修改，从缓存返回已解析的配置
                config_type = self._get_config_type_by_path(config_path)
                if config_type and config_type in self._config_cache:
                    return self._config_cache[config_type]
                # 如果缓存中没有配置，继续正常加载

        self._file_timestamps[str(config_path)] = mtime

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 环境变量替换
            content = self._replace_env_vars(content)

            # 解析YAML
            config_data = yaml.safe_load(content)

            # 环境特定配置处理
            if isinstance(config_data, dict) and "environments" in config_data:
                env_config = config_data.get("environments", {}).get(
                    self.environment, {}
                )
                if env_config:
                    # 合并环境特定配置
                    config_data = self._deep_merge(config_data, env_config)
                # 移除environments节点
                config_data.pop("environments", None)

            return config_data

        except Exception as e:
            self.logger.error(f"解析YAML配置文件 {config_path} 失败: {e}")
            raise ConfigLoadError(f"解析配置文件失败: {e}")

    def _replace_env_vars(self, content: str) -> str:
        """替换配置文件中的环境变量

        支持格式: ${VAR_NAME} 或 ${VAR_NAME:default_value}
        """
        def replace_var(match):
            var_expr = match.group(1)
            if ":" in var_expr:
                var_name, default_value = var_expr.split(":", 1)
            else:
                var_name, default_value = var_expr, ""

            return os.environ.get(var_name, default_value)

        # 匹配 ${VAR_NAME} 或 ${VAR_NAME:default}
        pattern = r"\$\{([^}]+)\}"
        return re.sub(pattern, replace_var, content)

    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """深度合并两个字典"""
        from copy import deepcopy

        result = deepcopy(base)

        for key, value in update.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)

        return result

    def get(self, key: str, default: Any = None, config_type: str = None) -> Any:
        """获取配置值

        Args:
            key: 配置键，支持点分隔的嵌套键
            default: 默认值
            config_type: 配置类型 (database, api, cache, logging, trading, system, data)

        Returns:
            配置值
        """
        with self._cache_lock:
            if config_type:
                # 从指定配置类型获取
                if config_type not in self._config_cache:
                    return default
                config_data = self._config_cache[config_type]
            else:
                # 从所有配置中搜索
                config_data = {}
                for cfg_type, cfg_data in self._config_cache.items():
                    if isinstance(cfg_data, dict):
                        config_data.update(cfg_data)

            # 支持点分隔的嵌套键
            keys = key.split(".")
            current = config_data

            for k in keys:
                if isinstance(current, dict) and k in current:
                    current = current[k]
                else:
                    return default

            return current

    def set(self, key: str, value: Any, config_type: str) -> None:
        """设置配置值

        Args:
            key: 配置键，支持点分隔的嵌套键
            value: 配置值
            config_type: 配置类型
        """
        with self._cache_lock:
            if config_type not in self._config_cache:
                self._config_cache[config_type] = {}

            # 支持点分隔的嵌套键
            keys = key.split(".")
            current = self._config_cache[config_type]

            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]

            current[keys[-1]] = value

            self.logger.debug(f"设置配置: {config_type}.{key} = {value}")

    def has(self, key: str, config_type: str = None) -> bool:
        """检查配置键是否存在

        Args:
            key: 配置键
            config_type: 配置类型

        Returns:
            bool: 是否存在
        """
        return self.get(key, None, config_type) is not None

    def get_config(self, config_type: str) -> Optional[Dict[str, Any]]:
        """获取指定类型的配置

        Args:
            config_type: 配置类型 (database, api, cache, logging, trading, system, data)

        Returns:
            配置字典，如果不存在则返回None
        """
        with self._cache_lock:
            return self._config_cache.get(config_type, None)


    def get_api_config(self, api_name: str = None) -> Dict[str, Any]:
        """获取API配置

        Args:
            api_name: API名称，不指定则返回所有API配置

        Returns:
            API配置字典
        """
        api_config = self.get_config("api")
        if not api_config:
            return {}
            
        if api_name:
            # 查找指定的API配置
            for section in ["data_providers", "trading_apis", "external_services"]:
                if section in api_config and api_name in api_config[section]:
                    return api_config[section][api_name]
            return {}
        else:
            return api_config

    def get_cache_config(self, cache_type: str = None) -> Dict[str, Any]:
        """获取缓存配置

        Args:
            cache_type: 缓存类型 (redis, memory, strategies)

        Returns:
            缓存配置字典
        """
        cache_config = self.get_config("cache")
        if not cache_config:
            return {}
            
        if cache_type:
            return cache_config.get(cache_type, {})
        else:
            return cache_config

    def get_all(self, config_type: str = None) -> Dict[str, Any]:
        """获取所有配置

        Args:
            config_type: 配置类型，如果为None则返回所有配置

        Returns:
            配置字典
        """
        with self._cache_lock:
            if config_type:
                return self._config_cache.get(config_type, {}).copy()
            else:
                all_config = {}
                for cfg_type, cfg_data in self._config_cache.items():
                    all_config[cfg_type] = cfg_data.copy()
                return all_config

    def reload_config(self, config_type: str = None) -> None:
        """重新加载配置

        Args:
            config_type: 配置类型，如果为None则重新加载所有配置
        """
        if config_type:
            if config_type in self.config_files:
                try:
                    config_data = self._load_yaml_config(self.config_files[config_type])
                    if config_data:
                        with self._cache_lock:
                            self._config_cache[config_type] = config_data
                        self.logger.info(f"配置文件 {config_type}.yaml 重新加载成功")
                except Exception as e:
                    self.logger.error(f"重新加载配置文件 {config_type}.yaml 失败: {e}")
                    raise
        else:
            self.load_all_configs()

    def save_config(self, config_type: str, config_data: Dict[str, Any] = None) -> None:
        """保存配置到文件

        Args:
            config_type: 配置类型
            config_data: 配置数据，如果为None则保存当前缓存的配置
        """
        if config_data is None:
            with self._cache_lock:
                config_data = self._config_cache.get(config_type, {})

        if config_type not in self.config_files:
            raise ValueError(f"不支持的配置类型: {config_type}")

        config_path = self.config_files[config_type]

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    config_data,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    indent=2,
                )

            self.logger.info(f"配置文件 {config_path.name} 保存成功")
        except Exception as e:
            self.logger.error(f"保存配置文件 {config_path.name} 失败: {e}")
            raise

    def shutdown(self) -> None:
        """关闭配置管理器"""
        with self._cache_lock:
            # 清理缓存
            self._config_cache.clear()
            self._file_timestamps.clear()

            self.logger.info("配置管理器已关闭")

    def validate(self) -> tuple[bool, list[str]]:
        """验证配置完整性
        
        Returns:
            tuple: (是否有效, 错误列表)
        """
        errors = []
        
        # 检查必要的配置文件是否加载
        required_configs = ["database", "system"]
        for config_type in required_configs:
            if config_type not in self._config_cache:
                errors.append(f"缺少必要的配置文件: {config_type}.yaml")
        
        # 检查数据库配置
        db_config = self.get_config("database")
        if db_config and "databases" in db_config:
            # 检查MySQL配置
            mysql_config = db_config["databases"].get("mysql", {})
            if mysql_config.get("enabled", False):
                required_fields = ["host", "port", "username", "database"]
                for field in required_fields:
                    if not mysql_config.get(field):
                        errors.append(f"MySQL配置缺少字段: {field}")
            
            # 检查ClickHouse配置
            ch_config = db_config["databases"].get("clickhouse", {})
            if ch_config.get("enabled", False):
                required_fields = ["host", "port", "database"]
                for field in required_fields:
                    if not ch_config.get(field):
                        errors.append(f"ClickHouse配置缺少字段: {field}")
        
        # 检查系统配置
        sys_config = self.get_config("system")
        if sys_config:
            if not sys_config.get("project_name"):
                errors.append("系统配置缺少项目名称")
        
        return len(errors) == 0, errors

    def validate_config_standardization(self) -> tuple[bool, list[str]]:
        """验证配置标准化
        
        检查配置项命名是否符合标准化规范
        
        Returns:
            tuple: (是否符合标准, 问题列表)
        """
        issues = []
        
        # 标准化规范检查
        naming_patterns = {
            'timeout': r'.*timeout_seconds$',
            'interval': r'.*interval_seconds$',
            'delay': r'.*delay_seconds$',
            'attempts': r'.*max_attempts$',
            'cache_ttl': r'.*ttl_seconds$'
        }
        
        for config_type, config_data in self._config_cache.items():
            if not isinstance(config_data, dict):
                continue
                
            # 递归检查配置项命名
            def check_naming(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        
                        # 检查时间相关配置
                        if any(pattern in key.lower() for pattern in ['timeout', 'interval', 'delay']) and not key.endswith('_seconds'):
                            if isinstance(value, (int, float)) and key not in ['enabled', 'threshold', 'multiplier']:
                                issues.append(f"配置 {config_type}.{current_path} 应使用 '_seconds' 后缀")
                        
                        # 检查重试配置
                        if 'retry' in key.lower() and 'count' in key.lower():
                            issues.append(f"配置 {config_type}.{current_path} 应使用 'max_attempts' 而不是 'retry_count'")
                        
                        # 检查缓存TTL配置
                        if 'ttl' in key.lower() and not key.endswith('_seconds'):
                            issues.append(f"配置 {config_type}.{current_path} TTL应使用 '_seconds' 后缀")
                        
                        # 递归检查嵌套对象
                        check_naming(value, current_path)
            
            check_naming(config_data)
        
        return len(issues) == 0, issues

    def standardize_config_values(self, config_type: str = None) -> Dict[str, Any]:
        """标准化配置值
        
        将配置值转换为标准格式
        
        Args:
            config_type: 配置类型，为None时处理所有配置
            
        Returns:
            标准化后的配置字典
        """
        def standardize_dict(obj):
            if not isinstance(obj, dict):
                return obj
                
            standardized = {}
            for key, value in obj.items():
                new_key = key
                new_value = value
                
                # 标准化时间相关配置键名
                if any(pattern in key.lower() for pattern in ['timeout', 'interval', 'delay']):
                    if not key.endswith('_seconds') and isinstance(value, (int, float)):
                        new_key = f"{key}_seconds"
                
                # 标准化重试配置键名
                if key.lower() in ['retry_count', 'retries']:
                    new_key = 'max_attempts'
                
                # 标准化cache ttl键名
                if key.lower() == 'ttl' or (key.lower().endswith('ttl') and not key.endswith('_seconds')):
                    new_key = f"{key}_seconds" if not key.endswith('_seconds') else key
                
                # 递归处理嵌套字典
                if isinstance(value, dict):
                    new_value = standardize_dict(value)
                elif isinstance(value, list):
                    new_value = [standardize_dict(item) if isinstance(item, dict) else item for item in value]
                
                standardized[new_key] = new_value
            
            return standardized
        
        if config_type:
            config_data = self.get_config(config_type)
            if config_data:
                return standardize_dict(config_data)
            return {}
        else:
            # 处理所有配置
            all_standardized = {}
            for cfg_type, cfg_data in self._config_cache.items():
                if isinstance(cfg_data, dict):
                    all_standardized[cfg_type] = standardize_dict(cfg_data)
                else:
                    all_standardized[cfg_type] = cfg_data
            return all_standardized

    def find_duplicate_configs(self) -> Dict[str, list]:
        """查找重复配置项
        
        Returns:
            重复配置项字典，键为配置路径，值为出现的配置类型列表
        """
        config_paths = {}
        
        def extract_paths(obj, prefix="", config_type=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{prefix}.{key}" if prefix else key
                    
                    # 记录配置路径
                    if current_path not in config_paths:
                        config_paths[current_path] = []
                    config_paths[current_path].append(config_type)
                    
                    # 递归处理
                    if isinstance(value, dict):
                        extract_paths(value, current_path, config_type)
        
        # 提取所有配置路径
        for config_type, config_data in self._config_cache.items():
            if isinstance(config_data, dict):
                extract_paths(config_data, "", config_type)
        
        # 找出重复的配置路径
        duplicates = {path: types for path, types in config_paths.items() if len(set(types)) > 1}
        
        return duplicates

    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要信息
        
        Returns:
            配置摘要字典
        """
        summary = {
            'total_configs': len(self._config_cache),
            'config_types': list(self._config_cache.keys()),
            'validation_status': {},
            'standardization_status': {},
            'duplicate_configs': {},
            'file_timestamps': self._file_timestamps.copy()
        }
        
        # 验证状态
        is_valid, validation_errors = self.validate()
        summary['validation_status'] = {
            'is_valid': is_valid,
            'error_count': len(validation_errors),
            'errors': validation_errors
        }
        
        # 标准化状态
        is_standardized, standardization_issues = self.validate_config_standardization()
        summary['standardization_status'] = {
            'is_standardized': is_standardized,
            'issue_count': len(standardization_issues),
            'issues': standardization_issues
        }
        
        # 重复配置
        duplicates = self.find_duplicate_configs()
        summary['duplicate_configs'] = {
            'count': len(duplicates),
            'items': duplicates
        }
        
        return summary

    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.get_config("logging") or {}

    def get_trading_config(self) -> Dict[str, Any]:
        """获取交易配置"""
        return self.get_config("trading") or {}

    def get_system_config(self) -> Dict[str, Any]:
        """获取系统配置"""
        return self.get_config("system") or {}

    def get_data_config(self) -> Dict[str, Any]:
        """获取数据配置"""
        return self.get_config("data") or {}

    def get_storage_config(self) -> Dict[str, Any]:
        """获取存储配置"""
        return self.get_config("storage") or {}

    def get_storage_layer_config(self, layer: str) -> Dict[str, Any]:
        """获取指定存储层配置
        
        Args:
            layer: 存储层名称 (hot_layer, warm_layer, cool_layer, cold_layer)
            
        Returns:
            存储层配置字典
        """
        storage_config = self.get_storage_config()
        return storage_config.get(layer, {})
    
    # 新架构：四层存储配置获取方法
    def get_mysql_config(self) -> Dict[str, Any]:
        """获取MySQL配置（结构化数据层）"""
        return self.get_config("mysql") or {}
    
    def get_clickhouse_config(self) -> Dict[str, Any]:
        """获取ClickHouse配置（分析层）"""
        return self.get_config("clickhouse") or {}
    
    def get_redis_config(self) -> Dict[str, Any]:
        """获取Redis配置（缓存层）"""
        return self.get_config("redis") or {}
    
    def get_minio_config(self) -> Dict[str, Any]:
        """获取MinIO配置（对象存储层）"""
        return self.get_config("minio") or {}
    
    # 新架构：业务模块配置获取方法
    def get_trading_config(self) -> Dict[str, Any]:
        """获取交易配置"""
        return self.get_config("trading") or {}
    
    def get_data_integrity_config(self) -> Dict[str, Any]:
        """获取数据完整性配置"""
        return self.get_config("data_integrity") or {}
    
    # 新架构：schema获取方法（用于向后兼容）
    def get_schema_config(self, engine: str) -> Dict[str, Any]:
        """获取Schema表结构配置
        
        Args:
            engine: 数据库引擎 (mysql, clickhouse, redis, minio)
            
        Returns:
            Schema配置字典
        """
        config = self.get_config(engine) or {}
        return config.get('tables', {})

    def reload_all_configs(self) -> None:
        """重新加载所有配置"""
        self.load_all_configs()


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例

    Returns:
        ConfigManager: 配置管理器实例
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
        _config_manager.load_all_configs()
    return _config_manager


def init_config(
    config_dir: Optional[str] = None, environment: Optional[str] = None
) -> ConfigManager:
    """初始化全局配置管理器

    Args:
        config_dir: 配置目录路径
        environment: 运行环境 (development, testing, production)

    Returns:
        ConfigManager: 配置管理器实例
    """
    global _config_manager

    if _config_manager is not None:
        _config_manager.shutdown()

    _config_manager = ConfigManager(config_dir, environment)
    _config_manager.load_all_configs()

    return _config_manager


# 便捷函数
def get_config(key: str, default: Any = None, config_type: str = None) -> Any:
    """获取配置值的便捷函数"""
    return get_config_manager().get(key, default, config_type)




def get_api_config(api_name: str = None) -> Dict[str, Any]:
    """获取API配置的便捷函数"""
    return get_config_manager().get_api_config(api_name)


def get_cache_config(cache_type: str = None) -> Dict[str, Any]:
    """获取缓存配置的便捷函数"""
    return get_config_manager().get_cache_config(cache_type)


# 新架构：四层存储配置便捷函数
def get_mysql_config() -> Dict[str, Any]:
    """获取MySQL配置的便捷函数"""
    return get_config_manager().get_mysql_config()

def get_clickhouse_config() -> Dict[str, Any]:
    """获取ClickHouse配置的便捷函数"""
    return get_config_manager().get_clickhouse_config()

def get_redis_config() -> Dict[str, Any]:
    """获取Redis配置的便捷函数"""
    return get_config_manager().get_redis_config()

def get_minio_config() -> Dict[str, Any]:
    """获取MinIO配置的便捷函数"""
    return get_config_manager().get_minio_config()

# 新架构：业务模块配置便捷函数
def get_trading_config() -> Dict[str, Any]:
    """获取交易配置的便捷函数"""
    return get_config_manager().get_trading_config()

def get_data_integrity_config() -> Dict[str, Any]:
    """获取数据完整性配置的便捷函数"""
    return get_config_manager().get_data_integrity_config()

# 新架构：Schema获取便捷函数
def get_schema_config(engine: str) -> Dict[str, Any]:
    """获取Schema配置的便捷函数"""
    return get_config_manager().get_schema_config(engine)

def get_storage_config() -> Dict[str, Any]:
    """获取存储配置的便捷函数"""
    return get_config_manager().get_storage_config()


def get_storage_layer_config(layer: str) -> Dict[str, Any]:
    """获取存储层配置的便捷函数"""
    return get_config_manager().get_storage_layer_config(layer)


def reload_config(config_type: str = None) -> None:
    """重新加载配置的便捷函数"""
    get_config_manager().reload_config(config_type)


if __name__ == "__main__":
    # 示例用法
    import logging
    
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    # 初始化配置管理器
    config_manager = init_config()
    
    # 获取配置值
    print(f"数据库主机: {get_config('databases.mysql.host', config_type='database')}")
    print(f"系统名称: {get_config('project_name', config_type='system')}")
    print(f"日志级别: {get_config('level', config_type='logging')}")
    
    # 获取数据库配置
    mysql_config = get_mysql_config()
    print(f"MySQL配置: {mysql_config}")
    
    # 获取API配置
    api_config = get_api_config()
    print(f"API配置: {api_config}")
    
    # 关闭配置管理器
    config_manager.shutdown()