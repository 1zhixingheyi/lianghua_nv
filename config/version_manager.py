#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置版本管理工具

提供配置文件的版本管理功能，包括：
1. 配置变更历史记录
2. 配置回滚功能
3. 配置差异对比
4. 配置备份和恢复
5. 配置变更审计

作者: 量化交易系统
日期: 2025-01-18
版本: 1.0.0
"""

import json
import logging
import shutil
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from deepdiff import DeepDiff

logger = logging.getLogger(__name__)


@dataclass
class ConfigVersion:
    """配置版本信息"""
    version_id: str
    timestamp: datetime
    author: str
    description: str
    config_file: str
    backup_path: str
    changes: Dict[str, Any]
    parent_version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConfigVersion':
        """从字典创建"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class ConfigVersionManager:
    """配置版本管理器"""
    
    def __init__(self, base_dir: str = "config", versions_dir: str = "config/versions"):
        """初始化版本管理器
        
        Args:
            base_dir: 配置文件基础目录
            versions_dir: 版本存储目录
        """
        self.base_dir = Path(base_dir)
        self.versions_dir = Path(versions_dir)
        
        # 确保版本目录存在
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        
        # 版本历史文件
        self.history_file = self.versions_dir / "version_history.json"
        
        # 加载版本历史
        self.versions: Dict[str, ConfigVersion] = {}
        self._load_version_history()
        
        logger.info(f"配置版本管理器初始化完成，基础目录: {self.base_dir}, 版本目录: {self.versions_dir}")
    
    def _load_version_history(self):
        """加载版本历史"""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
                
                for version_id, version_data in history_data.items():
                    self.versions[version_id] = ConfigVersion.from_dict(version_data)
                
                logger.info(f"已加载 {len(self.versions)} 个配置版本")
            else:
                logger.info("版本历史文件不存在，从空历史开始")
                
        except Exception as e:
            logger.error(f"加载版本历史失败: {e}")
            self.versions = {}
    
    def _save_version_history(self):
        """保存版本历史"""
        try:
            history_data = {}
            for version_id, version in self.versions.items():
                history_data[version_id] = version.to_dict()
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=2, ensure_ascii=False)
            
            logger.debug("版本历史已保存")
            
        except Exception as e:
            logger.error(f"保存版本历史失败: {e}")
    
    def _generate_version_id(self) -> str:
        """生成版本ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"v_{timestamp}"
    
    def _backup_config_file(self, config_file: str, version_id: str) -> str:
        """备份配置文件
        
        Args:
            config_file: 配置文件路径
            version_id: 版本ID
            
        Returns:
            备份文件路径
        """
        config_path = Path(config_file)
        if not config_path.is_absolute():
            config_path = self.base_dir / config_path
        
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        # 创建备份文件名
        backup_filename = f"{config_path.stem}_{version_id}{config_path.suffix}"
        backup_path = self.versions_dir / backup_filename
        
        # 复制文件
        shutil.copy2(config_path, backup_path)
        
        logger.info(f"配置文件已备份: {config_path} -> {backup_path}")
        return str(backup_path)
    
    def _load_config_file(self, file_path: str) -> Dict[str, Any]:
        """加载配置文件
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            配置数据
        """
        path = Path(file_path)
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                if path.suffix.lower() in ['.yml', '.yaml']:
                    return yaml.safe_load(f) or {}
                elif path.suffix.lower() == '.json':
                    return json.load(f) or {}
                else:
                    # 尝试按YAML解析
                    return yaml.safe_load(f) or {}
                    
        except Exception as e:
            logger.error(f"加载配置文件失败: {file_path}, 错误: {e}")
            return {}
    
    def create_version(self, config_file: str, description: str, author: str = "system") -> str:
        """创建配置版本
        
        Args:
            config_file: 配置文件路径
            description: 版本描述
            author: 作者
            
        Returns:
            版本ID
        """
        try:
            # 生成版本ID
            version_id = self._generate_version_id()
            
            # 获取当前配置文件内容
            current_config = self._load_config_file(config_file)
            
            # 备份配置文件
            backup_path = self._backup_config_file(config_file, version_id)
            
            # 计算与父版本的差异
            parent_version_id = self._get_latest_version_id(config_file)
            changes = {}
            
            if parent_version_id:
                parent_version = self.versions[parent_version_id]
                parent_config = self._load_config_file(parent_version.backup_path)
                
                # 使用deepdiff计算差异
                diff = DeepDiff(parent_config, current_config, ignore_order=True)
                changes = {
                    'added': dict(diff.get('dictionary_item_added', {})),
                    'removed': dict(diff.get('dictionary_item_removed', {})),
                    'changed': dict(diff.get('values_changed', {})),
                    'type_changed': dict(diff.get('type_changes', {}))
                }
            else:
                changes = {'initial_version': current_config}
            
            # 创建版本对象
            version = ConfigVersion(
                version_id=version_id,
                timestamp=datetime.now(),
                author=author,
                description=description,
                config_file=config_file,
                backup_path=backup_path,
                changes=changes,
                parent_version=parent_version_id
            )
            
            # 保存版本
            self.versions[version_id] = version
            self._save_version_history()
            
            logger.info(f"配置版本已创建: {version_id} - {description}")
            return version_id
            
        except Exception as e:
            logger.error(f"创建配置版本失败: {e}")
            raise
    
    def _get_latest_version_id(self, config_file: str) -> Optional[str]:
        """获取指定配置文件的最新版本ID
        
        Args:
            config_file: 配置文件路径
            
        Returns:
            最新版本ID，如果没有则返回None
        """
        matching_versions = [
            v for v in self.versions.values()
            if v.config_file == config_file
        ]
        
        if not matching_versions:
            return None
        
        # 按时间戳排序，返回最新的
        latest_version = max(matching_versions, key=lambda v: v.timestamp)
        return latest_version.version_id
    
    def rollback_to_version(self, version_id: str) -> bool:
        """回滚到指定版本
        
        Args:
            version_id: 目标版本ID
            
        Returns:
            是否成功回滚
        """
        try:
            if version_id not in self.versions:
                logger.error(f"版本不存在: {version_id}")
                return False
            
            version = self.versions[version_id]
            
            # 检查备份文件是否存在
            backup_path = Path(version.backup_path)
            if not backup_path.exists():
                logger.error(f"备份文件不存在: {backup_path}")
                return False
            
            # 先创建当前配置的版本（回滚前备份）
            current_version_id = self.create_version(
                version.config_file,
                f"回滚前自动备份（回滚到 {version_id}）",
                "system"
            )
            
            # 恢复配置文件
            config_path = Path(version.config_file)
            if not config_path.is_absolute():
                config_path = self.base_dir / config_path
            
            shutil.copy2(backup_path, config_path)
            
            logger.info(f"配置已回滚到版本 {version_id}: {version.description}")
            return True
            
        except Exception as e:
            logger.error(f"回滚配置失败: {e}")
            return False
    
    def get_version_list(self, config_file: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取版本列表
        
        Args:
            config_file: 过滤指定配置文件的版本，None表示获取所有版本
            
        Returns:
            版本信息列表
        """
        versions = []
        
        for version_id, version in self.versions.items():
            if config_file is None or version.config_file == config_file:
                versions.append({
                    'version_id': version_id,
                    'timestamp': version.timestamp.isoformat(),
                    'author': version.author,
                    'description': version.description,
                    'config_file': version.config_file,
                    'parent_version': version.parent_version,
                    'has_backup': Path(version.backup_path).exists()
                })
        
        # 按时间戳降序排序
        versions.sort(key=lambda x: x['timestamp'], reverse=True)
        return versions
    
    def get_version_diff(self, version_id1: str, version_id2: str) -> Dict[str, Any]:
        """获取两个版本之间的差异
        
        Args:
            version_id1: 版本1 ID
            version_id2: 版本2 ID
            
        Returns:
            差异信息
        """
        try:
            if version_id1 not in self.versions or version_id2 not in self.versions:
                raise ValueError("版本ID不存在")
            
            version1 = self.versions[version_id1]
            version2 = self.versions[version_id2]
            
            config1 = self._load_config_file(version1.backup_path)
            config2 = self._load_config_file(version2.backup_path)
            
            diff = DeepDiff(config1, config2, ignore_order=True)
            
            return {
                'version1': {
                    'id': version_id1,
                    'description': version1.description,
                    'timestamp': version1.timestamp.isoformat()
                },
                'version2': {
                    'id': version_id2,
                    'description': version2.description,
                    'timestamp': version2.timestamp.isoformat()
                },
                'diff': {
                    'added': dict(diff.get('dictionary_item_added', {})),
                    'removed': dict(diff.get('dictionary_item_removed', {})),
                    'changed': dict(diff.get('values_changed', {})),
                    'type_changed': dict(diff.get('type_changes', {}))
                }
            }
            
        except Exception as e:
            logger.error(f"获取版本差异失败: {e}")
            return {}
    
    def export_version(self, version_id: str, export_path: str) -> bool:
        """导出版本配置
        
        Args:
            version_id: 版本ID
            export_path: 导出文件路径
            
        Returns:
            是否成功导出
        """
        try:
            if version_id not in self.versions:
                logger.error(f"版本不存在: {version_id}")
                return False
            
            version = self.versions[version_id]
            backup_path = Path(version.backup_path)
            
            if not backup_path.exists():
                logger.error(f"备份文件不存在: {backup_path}")
                return False
            
            shutil.copy2(backup_path, export_path)
            logger.info(f"版本 {version_id} 已导出到: {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出版本失败: {e}")
            return False
    
    def import_version(self, import_path: str, config_file: str, description: str, author: str = "import") -> Optional[str]:
        """导入版本配置
        
        Args:
            import_path: 导入文件路径
            config_file: 目标配置文件路径
            description: 版本描述
            author: 作者
            
        Returns:
            导入成功的版本ID，失败返回None
        """
        try:
            import_file = Path(import_path)
            if not import_file.exists():
                logger.error(f"导入文件不存在: {import_path}")
                return None
            
            # 临时替换配置文件进行版本创建
            config_path = Path(config_file)
            if not config_path.is_absolute():
                config_path = self.base_dir / config_path
            
            # 备份当前配置文件
            temp_backup = None
            if config_path.exists():
                temp_backup = config_path.with_suffix(config_path.suffix + '.temp_backup')
                shutil.copy2(config_path, temp_backup)
            
            # 复制导入文件到配置路径
            shutil.copy2(import_file, config_path)
            
            # 创建版本
            version_id = self.create_version(config_file, description, author)
            
            # 恢复原配置文件
            if temp_backup and temp_backup.exists():
                shutil.copy2(temp_backup, config_path)
                temp_backup.unlink()
            
            logger.info(f"版本已导入: {version_id} - {description}")
            return version_id
            
        except Exception as e:
            logger.error(f"导入版本失败: {e}")
            return None
    
    def cleanup_old_versions(self, keep_count: int = 10, config_file: Optional[str] = None):
        """清理旧版本
        
        Args:
            keep_count: 保留的版本数量
            config_file: 指定配置文件，None表示所有配置文件
        """
        try:
            # 按配置文件分组
            versions_by_file = {}
            for version_id, version in self.versions.items():
                if config_file is None or version.config_file == config_file:
                    if version.config_file not in versions_by_file:
                        versions_by_file[version.config_file] = []
                    versions_by_file[version.config_file].append((version_id, version))
            
            # 对每个配置文件的版本进行清理
            cleaned_count = 0
            for file_path, file_versions in versions_by_file.items():
                # 按时间戳排序，最新的在前
                file_versions.sort(key=lambda x: x[1].timestamp, reverse=True)
                
                # 删除多余的版本
                if len(file_versions) > keep_count:
                    versions_to_remove = file_versions[keep_count:]
                    
                    for version_id, version in versions_to_remove:
                        # 删除备份文件
                        backup_path = Path(version.backup_path)
                        if backup_path.exists():
                            backup_path.unlink()
                        
                        # 从版本记录中删除
                        del self.versions[version_id]
                        cleaned_count += 1
                        
                        logger.debug(f"已清理版本: {version_id}")
            
            # 保存更新后的版本历史
            if cleaned_count > 0:
                self._save_version_history()
                logger.info(f"版本清理完成，共清理 {cleaned_count} 个版本")
            else:
                logger.info("无需清理版本")
                
        except Exception as e:
            logger.error(f"清理版本失败: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取版本管理统计信息
        
        Returns:
            统计信息
        """
        stats = {
            'total_versions': len(self.versions),
            'config_files': {},
            'authors': {},
            'disk_usage': 0
        }
        
        for version in self.versions.values():
            # 按配置文件统计
            if version.config_file not in stats['config_files']:
                stats['config_files'][version.config_file] = 0
            stats['config_files'][version.config_file] += 1
            
            # 按作者统计
            if version.author not in stats['authors']:
                stats['authors'][version.author] = 0
            stats['authors'][version.author] += 1
            
            # 计算磁盘使用量
            backup_path = Path(version.backup_path)
            if backup_path.exists():
                stats['disk_usage'] += backup_path.stat().st_size
        
        # 转换字节为MB
        stats['disk_usage_mb'] = stats['disk_usage'] / (1024 * 1024)
        
        return stats


# 全局版本管理器实例
_version_manager = None


def get_version_manager() -> ConfigVersionManager:
    """获取配置版本管理器单例"""
    global _version_manager
    if _version_manager is None:
        _version_manager = ConfigVersionManager()
    return _version_manager


if __name__ == "__main__":
    # 测试版本管理器
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建版本管理器
    vm = get_version_manager()
    
    # 输出统计信息
    stats = vm.get_statistics()
    print("版本管理统计:")
    print(f"总版本数: {stats['total_versions']}")
    print(f"配置文件: {stats['config_files']}")
    print(f"磁盘使用: {stats['disk_usage_mb']:.2f} MB")
    
    # 获取版本列表
    versions = vm.get_version_list()
    print(f"\n最近的 5 个版本:")
    for version in versions[:5]:
        print(f"- {version['version_id']}: {version['description']} ({version['timestamp']})")