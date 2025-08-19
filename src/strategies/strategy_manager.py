"""
策略管理器

提供策略注册、发现、实例化和运行状态监控等功能
"""

import logging
import pandas as pd
from typing import Dict, Any, List, Optional, Type, Union
from datetime import datetime
import importlib
import inspect
from pathlib import Path

from .base_strategy import BaseStrategy, Signal, StrategyState
from src.data import get_database_manager, get_tushare_client
from config.config_manager import get_config_manager

logger = logging.getLogger(__name__)


class StrategyManager:
    """策略管理器
    
    负责策略的注册、发现、实例化、配置和运行状态监控
    """
    
    def __init__(self):
        """初始化策略管理器"""
        self._strategies_registry: Dict[str, Type[BaseStrategy]] = {}
        self._active_strategies: Dict[str, BaseStrategy] = {}
        self._strategy_configs: Dict[str, Dict[str, Any]] = {}
        
        # 数据源
        self.db_manager = get_database_manager()
        self.data_client = get_tushare_client()
        
        # 配置管理器
        self.config_manager = get_config_manager()
        
        # 初始化热重载功能
        self._setup_hot_reload()
        
        # 自动发现并注册策略
        self._discover_strategies()
        
        logger.info("策略管理器初始化完成")
    
    def _discover_strategies(self):
        """自动发现策略模块中的策略类"""
        try:
            # 获取策略模块目录
            strategies_dir = Path(__file__).parent
            
            # 扫描所有Python文件
            for py_file in strategies_dir.glob("*.py"):
                if py_file.name.startswith('__') or py_file.name == 'base_strategy.py':
                    continue
                
                module_name = py_file.stem
                try:
                    # 动态导入模块
                    module = importlib.import_module(f"strategies.{module_name}")
                    
                    # 查找策略类
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and 
                            issubclass(obj, BaseStrategy) and 
                            obj != BaseStrategy):
                            
                            strategy_name = obj.__name__
                            self._strategies_registry[strategy_name] = obj
                            logger.info(f"发现策略: {strategy_name} (来自 {module_name})")
                            
                except Exception as e:
                    logger.error(f"导入策略模块失败: {module_name}, 错误: {str(e)}")
        
        except Exception as e:
            logger.error(f"策略发现失败: {str(e)}")
    
    def register_strategy(self, strategy_class: Type[BaseStrategy], name: Optional[str] = None):
        """手动注册策略类
        
        Args:
            strategy_class: 策略类
            name: 策略名称，如果为None则使用类名
        """
        if not issubclass(strategy_class, BaseStrategy):
            raise ValueError("策略类必须继承自BaseStrategy")
        
        strategy_name = name or strategy_class.__name__
        self._strategies_registry[strategy_name] = strategy_class
        
        logger.info(f"手动注册策略: {strategy_name}")
    
    def get_available_strategies(self) -> List[str]:
        """获取可用策略列表
        
        Returns:
            策略名称列表
        """
        return list(self._strategies_registry.keys())
    
    def get_strategy_info(self, strategy_name: str) -> Dict[str, Any]:
        """获取策略信息
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            策略信息字典
        """
        if strategy_name not in self._strategies_registry:
            raise ValueError(f"策略不存在: {strategy_name}")
        
        strategy_class = self._strategies_registry[strategy_name]
        
        # 创建临时实例以获取默认参数
        temp_instance = strategy_class()
        default_params = temp_instance.get_default_parameters()
        
        return {
            'name': strategy_name,
            'class_name': strategy_class.__name__,
            'module': strategy_class.__module__,
            'doc': strategy_class.__doc__,
            'default_parameters': default_params,
            'is_active': strategy_name in self._active_strategies
        }
    
    def create_strategy(self, strategy_name: str, instance_name: Optional[str] = None, 
                       params: Optional[Dict[str, Any]] = None) -> str:
        """创建策略实例
        
        Args:
            strategy_name: 策略类名
            instance_name: 实例名称，如果为None则自动生成
            params: 策略参数
            
        Returns:
            策略实例ID
        """
        if strategy_name not in self._strategies_registry:
            raise ValueError(f"策略不存在: {strategy_name}")
        
        # 生成实例名称
        if instance_name is None:
            instance_name = f"{strategy_name}_{len(self._active_strategies) + 1}"
        
        if instance_name in self._active_strategies:
            raise ValueError(f"策略实例已存在: {instance_name}")
        
        # 创建策略实例
        strategy_class = self._strategies_registry[strategy_name]
        strategy_instance = strategy_class(name=instance_name, params=params)
        
        # 添加到活跃策略列表
        self._active_strategies[instance_name] = strategy_instance
        
        # 保存配置
        self._strategy_configs[instance_name] = {
            'strategy_class': strategy_name,
            'params': params or {},
            'created_time': datetime.now(),
            'is_active': True
        }
        
        logger.info(f"创建策略实例: {instance_name} (类型: {strategy_name})")
        return instance_name
    
    def remove_strategy(self, instance_name: str):
        """移除策略实例
        
        Args:
            instance_name: 实例名称
        """
        if instance_name not in self._active_strategies:
            raise ValueError(f"策略实例不存在: {instance_name}")
        
        # 停用策略
        self.deactivate_strategy(instance_name)
        
        # 移除实例
        del self._active_strategies[instance_name]
        del self._strategy_configs[instance_name]
        
        logger.info(f"移除策略实例: {instance_name}")
    
    def activate_strategy(self, instance_name: str):
        """激活策略
        
        Args:
            instance_name: 实例名称
        """
        if instance_name not in self._active_strategies:
            raise ValueError(f"策略实例不存在: {instance_name}")
        
        strategy = self._active_strategies[instance_name]
        strategy.state.is_active = True
        self._strategy_configs[instance_name]['is_active'] = True
        
        logger.info(f"激活策略: {instance_name}")
    
    def deactivate_strategy(self, instance_name: str):
        """停用策略
        
        Args:
            instance_name: 实例名称
        """
        if instance_name not in self._active_strategies:
            raise ValueError(f"策略实例不存在: {instance_name}")
        
        strategy = self._active_strategies[instance_name]
        strategy.state.is_active = False
        self._strategy_configs[instance_name]['is_active'] = False
        
        logger.info(f"停用策略: {instance_name}")
    
    def update_strategy_parameters(self, instance_name: str, params: Dict[str, Any]):
        """更新策略参数
        
        Args:
            instance_name: 实例名称
            params: 新参数
        """
        if instance_name not in self._active_strategies:
            raise ValueError(f"策略实例不存在: {instance_name}")
        
        strategy = self._active_strategies[instance_name]
        
        # 更新参数
        for key, value in params.items():
            strategy.set_parameter(key, value)
        
        # 更新配置
        self._strategy_configs[instance_name]['params'].update(params)
        
        logger.info(f"更新策略参数: {instance_name}, 参数: {params}")
    
    def process_symbol_data(self, symbol: str, data: pd.DataFrame, 
                           strategy_filter: Optional[List[str]] = None) -> Dict[str, List[Signal]]:
        """为指定品种处理数据并生成信号
        
        Args:
            symbol: 交易品种代码
            data: 价格数据
            strategy_filter: 策略过滤列表，如果为None则处理所有活跃策略
            
        Returns:
            策略信号字典 {strategy_name: [signals]}
        """
        results = {}
        
        # 确定要处理的策略
        strategies_to_process = strategy_filter or list(self._active_strategies.keys())
        
        for instance_name in strategies_to_process:
            if instance_name not in self._active_strategies:
                logger.warning(f"策略实例不存在: {instance_name}")
                continue
            
            strategy = self._active_strategies[instance_name]
            
            # 检查策略是否活跃
            if not strategy.state.is_active:
                logger.debug(f"跳过非活跃策略: {instance_name}")
                continue
            
            try:
                # 处理数据生成信号
                signals = strategy.process_data(data, symbol)
                results[instance_name] = signals
                
                logger.debug(f"策略 {instance_name} 为 {symbol} 生成了 {len(signals)} 个信号")
                
            except Exception as e:
                logger.error(f"策略 {instance_name} 处理 {symbol} 数据失败: {str(e)}")
                results[instance_name] = []
        
        return results
    
    def batch_process_symbols(self, symbols: List[str], 
                            strategy_filter: Optional[List[str]] = None) -> Dict[str, Dict[str, List[Signal]]]:
        """批量处理多个品种
        
        Args:
            symbols: 品种代码列表
            strategy_filter: 策略过滤列表
            
        Returns:
            嵌套字典 {symbol: {strategy_name: [signals]}}
        """
        results = {}
        
        for symbol in symbols:
            try:
                # 获取数据
                data = self._get_symbol_data(symbol)
                
                if data is not None and not data.empty:
                    # 处理数据
                    symbol_results = self.process_symbol_data(symbol, data, strategy_filter)
                    results[symbol] = symbol_results
                else:
                    logger.warning(f"无法获取 {symbol} 的数据")
                    results[symbol] = {}
                    
            except Exception as e:
                logger.error(f"处理品种 {symbol} 失败: {str(e)}")
                results[symbol] = {}
        
        return results
    
    def _get_symbol_data(self, symbol: str, days: int = 100) -> Optional[pd.DataFrame]:
        """获取品种数据
        
        Args:
            symbol: 品种代码
            days: 数据天数
            
        Returns:
            价格数据DataFrame
        """
        try:
            # 从数据库查询数据
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - pd.Timedelta(days=days)).strftime('%Y%m%d')
            
            sql = """
            SELECT trade_date, open_price as open, high_price as high, 
                   low_price as low, close_price as close, vol as volume
            FROM daily_quotes 
            WHERE ts_code = %s AND trade_date BETWEEN %s AND %s
            ORDER BY trade_date
            """
            
            data = self.db_manager.query_dataframe(sql, {
                'ts_code': symbol,
                'start_date': start_date,
                'end_date': end_date
            })
            
            if data is not None and not data.empty:
                # 设置索引
                data['trade_date'] = pd.to_datetime(data['trade_date'])
                data.set_index('trade_date', inplace=True)
                
                return data
            
            return None
            
        except Exception as e:
            logger.error(f"获取 {symbol} 数据失败: {str(e)}")
            return None
    
    def get_active_strategies(self) -> List[str]:
        """获取活跃策略列表
        
        Returns:
            活跃策略实例名称列表
        """
        return [name for name, strategy in self._active_strategies.items() 
                if strategy.state.is_active]
    
    def get_all_strategies_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有策略状态
        
        Returns:
            策略状态字典
        """
        status = {}
        
        for instance_name, strategy in self._active_strategies.items():
            status[instance_name] = {
                **strategy.get_strategy_status(),
                'config': self._strategy_configs[instance_name]
            }
        
        return status
    
    def get_strategy_instance(self, instance_name: str) -> Optional[BaseStrategy]:
        """获取策略实例
        
        Args:
            instance_name: 实例名称
            
        Returns:
            策略实例或None
        """
        return self._active_strategies.get(instance_name)
    
    def reset_strategy(self, instance_name: str):
        """重置策略状态
        
        Args:
            instance_name: 实例名称
        """
        if instance_name not in self._active_strategies:
            raise ValueError(f"策略实例不存在: {instance_name}")
        
        strategy = self._active_strategies[instance_name]
        strategy.reset_strategy()
        
        logger.info(f"重置策略状态: {instance_name}")
    
    def export_strategy_config(self, instance_name: str) -> Dict[str, Any]:
        """导出策略配置
        
        Args:
            instance_name: 实例名称
            
        Returns:
            策略配置字典
        """
        if instance_name not in self._active_strategies:
            raise ValueError(f"策略实例不存在: {instance_name}")
        
        config = self._strategy_configs[instance_name].copy()
        config['current_status'] = self._active_strategies[instance_name].get_strategy_status()
        
        return config
    
    def import_strategy_config(self, config: Dict[str, Any]) -> str:
        """导入策略配置
        
        Args:
            config: 策略配置字典
            
        Returns:
            创建的策略实例名称
        """
        strategy_class = config['strategy_class']
        params = config.get('params', {})
        
        # 生成新的实例名称
        base_name = f"{strategy_class}_imported"
        instance_name = base_name
        counter = 1
        
        while instance_name in self._active_strategies:
            instance_name = f"{base_name}_{counter}"
            counter += 1
        
        return self.create_strategy(strategy_class, instance_name, params)
    
    def _setup_hot_reload(self):
        """设置热重载功能"""
        try:
            from config.hot_reload_startup import init_hot_reload_for_strategy_manager
            init_hot_reload_for_strategy_manager(self)
            logger.info("策略管理器热重载功能已启用")
        except ImportError:
            logger.warning("热重载模块不可用，跳过热重载设置")
        except Exception as e:
            logger.error(f"设置策略管理器热重载功能失败: {e}")
    
    async def reload_config(self, config_data: Dict[str, Any]):
        """重新加载配置
        
        Args:
            config_data: 新的配置数据
        """
        try:
            logger.info("开始重新加载策略配置...")
            
            # 更新所有活跃策略的参数
            for instance_name, strategy in self._active_strategies.items():
                try:
                    # 获取策略相关配置
                    strategy_class = self._strategy_configs[instance_name]['strategy_class']
                    
                    # 查找匹配的配置
                    if strategy_class.lower() in str(config_data).lower():
                        # 提取相关配置参数
                        new_params = self._extract_strategy_params(config_data, strategy_class)
                        
                        if new_params:
                            # 更新策略参数
                            for key, value in new_params.items():
                                if hasattr(strategy, 'set_parameter'):
                                    strategy.set_parameter(key, value)
                                    
                            # 更新配置记录
                            self._strategy_configs[instance_name]['params'].update(new_params)
                            
                            logger.info(f"策略 {instance_name} 配置已更新: {new_params}")
                            
                except Exception as e:
                    logger.error(f"更新策略 {instance_name} 配置失败: {e}")
                    
            logger.info("策略配置重新加载完成")
            
        except Exception as e:
            logger.error(f"重新加载策略配置失败: {e}")
            
    def _extract_strategy_params(self, config_data: Dict[str, Any], strategy_class: str) -> Dict[str, Any]:
        """从配置数据中提取策略参数
        
        Args:
            config_data: 配置数据
            strategy_class: 策略类名
            
        Returns:
            提取的参数字典
        """
        params = {}
        
        try:
            # 查找策略相关配置
            if 'strategies' in config_data:
                strategies_config = config_data['strategies']
                
                # 检查是否有匹配的策略配置
                for key, value in strategies_config.items():
                    if strategy_class.lower() in key.lower():
                        if isinstance(value, dict):
                            params.update(value)
                            
            # 查找通用交易参数
            if 'risk_management' in config_data:
                risk_params = config_data['risk_management']
                if isinstance(risk_params, dict):
                    # 映射风险管理参数到策略参数
                    if 'max_position_size' in risk_params:
                        params['position_size'] = risk_params['max_position_size']
                    if 'stop_loss_percent' in risk_params:
                        params['stop_loss'] = risk_params['stop_loss_percent']
                        
            # 查找执行参数
            if 'execution' in config_data:
                exec_params = config_data['execution']
                if isinstance(exec_params, dict):
                    if 'order_timeout_seconds' in exec_params:
                        params['timeout'] = exec_params['order_timeout_seconds']
                        
        except Exception as e:
            logger.error(f"提取策略参数失败: {e}")
            
        return params
    
    def get_hot_reload_status(self) -> Dict[str, Any]:
        """获取热重载状态
        
        Returns:
            热重载状态信息
        """
        try:
            from config.hot_reload_service import get_hot_reload_service
            service = get_hot_reload_service()
            
            return {
                'enabled': True,
                'service_running': service.is_running,
                'active_strategies': len(self._active_strategies),
                'last_config_update': getattr(self, '_last_config_update', None),
                'trading_config_available': 'trading' in service.component_handlers
            }
            
        except ImportError:
            return {'enabled': False, 'reason': '热重载模块不可用'}
        except Exception as e:
            return {'enabled': False, 'error': str(e)}


# 全局策略管理器实例
_strategy_manager = None

def get_strategy_manager() -> StrategyManager:
    """获取策略管理器单例"""
    global _strategy_manager
    if _strategy_manager is None:
        _strategy_manager = StrategyManager()
    return _strategy_manager