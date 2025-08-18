#!/usr/bin/env python3
"""
监控面板数据集成模块
==================

用于集成各个后端模块的数据接口，为监控面板提供统一的数据访问层。

主要功能:
- 数据模块集成
- 策略模块集成
- 交易模块集成
- 风控模块集成
- 数据格式转换
- 错误处理
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import traceback

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

logger = logging.getLogger(__name__)


class DataIntegrationError(Exception):
    """数据集成异常"""
    pass


class BackendModuleAdapter:
    """后端模块适配器基类"""
    
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.module = None
        self.available = False
        self._load_module()
    
    def _load_module(self):
        """加载模块"""
        try:
            self.module = __import__(self.module_name)
            self.available = True
            logger.info(f"成功加载模块: {self.module_name}")
        except ImportError as e:
            logger.warning(f"无法加载模块 {self.module_name}: {e}")
            self.available = False
    
    def is_available(self) -> bool:
        """检查模块是否可用"""
        return self.available
    
    def get_module_info(self) -> Dict[str, Any]:
        """获取模块信息"""
        if not self.available:
            return {
                'name': self.module_name,
                'available': False,
                'error': 'Module not available'
            }
        
        return {
            'name': self.module_name,
            'available': True,
            'version': getattr(self.module, '__version__', 'unknown'),
            'path': getattr(self.module, '__file__', 'unknown')
        }


class DataModuleAdapter(BackendModuleAdapter):
    """数据模块适配器"""
    
    def __init__(self):
        super().__init__('data')
        self.data_source = None
        self._initialize_data_source()
    
    def _initialize_data_source(self):
        """初始化数据源"""
        if not self.available:
            return
        
        try:
            # 尝试初始化数据源
            if hasattr(self.module, 'TushareDataSource'):
                self.data_source = self.module.TushareDataSource()
            elif hasattr(self.module, 'DataSource'):
                self.data_source = self.module.DataSource()
            logger.info("数据源初始化成功")
        except Exception as e:
            logger.error(f"数据源初始化失败: {e}")
    
    def get_market_data(self, symbol: str, period: str = '1d', limit: int = 100) -> List[Dict]:
        """获取市场数据"""
        if not self.available or not self.data_source:
            return self._generate_mock_market_data(symbol, limit)
        
        try:
            data = self.data_source.get_market_data(symbol, period, limit)
            return self._format_market_data(data)
        except Exception as e:
            logger.error(f"获取市场数据失败: {e}")
            return self._generate_mock_market_data(symbol, limit)
    
    def get_stock_list(self) -> List[Dict]:
        """获取股票列表"""
        if not self.available or not self.data_source:
            return self._generate_mock_stock_list()
        
        try:
            stocks = self.data_source.get_stock_list()
            return self._format_stock_list(stocks)
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return self._generate_mock_stock_list()
    
    def _format_market_data(self, data) -> List[Dict]:
        """格式化市场数据"""
        formatted_data = []
        for item in data:
            formatted_data.append({
                'timestamp': item.get('timestamp', datetime.now().isoformat()),
                'symbol': item.get('symbol', '000001.SZ'),
                'open': float(item.get('open', 0)),
                'high': float(item.get('high', 0)),
                'low': float(item.get('low', 0)),
                'close': float(item.get('close', 0)),
                'volume': int(item.get('volume', 0)),
                'amount': float(item.get('amount', 0))
            })
        return formatted_data
    
    def _format_stock_list(self, stocks) -> List[Dict]:
        """格式化股票列表"""
        formatted_stocks = []
        for stock in stocks:
            formatted_stocks.append({
                'symbol': stock.get('symbol', ''),
                'name': stock.get('name', ''),
                'market': stock.get('market', ''),
                'industry': stock.get('industry', ''),
                'list_date': stock.get('list_date', '')
            })
        return formatted_stocks
    
    def _generate_mock_market_data(self, symbol: str, limit: int) -> List[Dict]:
        """生成模拟市场数据"""
        import random
        
        data = []
        base_price = 10.0
        
        for i in range(limit):
            timestamp = datetime.now() - timedelta(days=limit-i-1)
            change = random.uniform(-0.1, 0.1)
            base_price *= (1 + change)
            
            open_price = base_price * (1 + random.uniform(-0.02, 0.02))
            high_price = max(open_price, base_price) * (1 + random.uniform(0, 0.05))
            low_price = min(open_price, base_price) * (1 - random.uniform(0, 0.05))
            close_price = base_price
            volume = random.randint(100000, 1000000)
            
            data.append({
                'timestamp': timestamp.isoformat(),
                'symbol': symbol,
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'volume': volume,
                'amount': round(close_price * volume, 2)
            })
        
        return data
    
    def _generate_mock_stock_list(self) -> List[Dict]:
        """生成模拟股票列表"""
        stocks = [
            {'symbol': '000001.SZ', 'name': '平安银行', 'market': 'SZ', 'industry': '银行'},
            {'symbol': '000002.SZ', 'name': '万科A', 'market': 'SZ', 'industry': '房地产'},
            {'symbol': '600000.SH', 'name': '浦发银行', 'market': 'SH', 'industry': '银行'},
            {'symbol': '600036.SH', 'name': '招商银行', 'market': 'SH', 'industry': '银行'},
            {'symbol': '000858.SZ', 'name': '五粮液', 'market': 'SZ', 'industry': '酿酒'},
        ]
        return stocks


class StrategyModuleAdapter(BackendModuleAdapter):
    """策略模块适配器"""
    
    def __init__(self):
        super().__init__('strategies')
        self.strategy_manager = None
        self._initialize_strategy_manager()
    
    def _initialize_strategy_manager(self):
        """初始化策略管理器"""
        if not self.available:
            return
        
        try:
            if hasattr(self.module, 'StrategyManager'):
                self.strategy_manager = self.module.StrategyManager()
            logger.info("策略管理器初始化成功")
        except Exception as e:
            logger.error(f"策略管理器初始化失败: {e}")
    
    def get_strategies(self) -> List[Dict]:
        """获取策略列表"""
        if not self.available or not self.strategy_manager:
            return self._generate_mock_strategies()
        
        try:
            strategies = self.strategy_manager.get_strategies()
            return self._format_strategies(strategies)
        except Exception as e:
            logger.error(f"获取策略列表失败: {e}")
            return self._generate_mock_strategies()
    
    def get_strategy_performance(self, strategy_id: str) -> Dict:
        """获取策略绩效"""
        if not self.available or not self.strategy_manager:
            return self._generate_mock_performance(strategy_id)
        
        try:
            performance = self.strategy_manager.get_performance(strategy_id)
            return self._format_performance(performance)
        except Exception as e:
            logger.error(f"获取策略绩效失败: {e}")
            return self._generate_mock_performance(strategy_id)
    
    def start_strategy(self, strategy_id: str) -> bool:
        """启动策略"""
        if not self.available or not self.strategy_manager:
            return False
        
        try:
            return self.strategy_manager.start_strategy(strategy_id)
        except Exception as e:
            logger.error(f"启动策略失败: {e}")
            return False
    
    def stop_strategy(self, strategy_id: str) -> bool:
        """停止策略"""
        if not self.available or not self.strategy_manager:
            return False
        
        try:
            return self.strategy_manager.stop_strategy(strategy_id)
        except Exception as e:
            logger.error(f"停止策略失败: {e}")
            return False
    
    def _format_strategies(self, strategies) -> List[Dict]:
        """格式化策略列表"""
        formatted_strategies = []
        for strategy in strategies:
            formatted_strategies.append({
                'id': strategy.get('id', ''),
                'name': strategy.get('name', ''),
                'type': strategy.get('type', ''),
                'status': strategy.get('status', 'stopped'),
                'description': strategy.get('description', ''),
                'created_at': strategy.get('created_at', ''),
                'updated_at': strategy.get('updated_at', '')
            })
        return formatted_strategies
    
    def _format_performance(self, performance) -> Dict:
        """格式化策略绩效"""
        return {
            'total_return': performance.get('total_return', 0.0),
            'annual_return': performance.get('annual_return', 0.0),
            'max_drawdown': performance.get('max_drawdown', 0.0),
            'sharpe_ratio': performance.get('sharpe_ratio', 0.0),
            'win_rate': performance.get('win_rate', 0.0),
            'total_trades': performance.get('total_trades', 0),
            'profit_trades': performance.get('profit_trades', 0),
            'loss_trades': performance.get('loss_trades', 0)
        }
    
    def _generate_mock_strategies(self) -> List[Dict]:
        """生成模拟策略数据"""
        import random
        
        strategies = []
        strategy_types = ['RSI策略', '移动平均策略', '布林带策略', '动量策略', '均值回归策略']
        
        for i, strategy_type in enumerate(strategy_types):
            strategies.append({
                'id': f'strategy_{i+1}',
                'name': f'{strategy_type}_{i+1}',
                'type': strategy_type,
                'status': random.choice(['running', 'stopped', 'paused']),
                'description': f'{strategy_type}的实现',
                'created_at': (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat(),
                'updated_at': datetime.now().isoformat()
            })
        
        return strategies
    
    def _generate_mock_performance(self, strategy_id: str) -> Dict:
        """生成模拟绩效数据"""
        import random
        
        return {
            'total_return': round(random.uniform(-0.2, 0.3), 4),
            'annual_return': round(random.uniform(-0.1, 0.25), 4),
            'max_drawdown': round(random.uniform(0.05, 0.15), 4),
            'sharpe_ratio': round(random.uniform(0.5, 2.5), 2),
            'win_rate': round(random.uniform(0.4, 0.7), 2),
            'total_trades': random.randint(50, 500),
            'profit_trades': random.randint(20, 200),
            'loss_trades': random.randint(15, 150)
        }


class TradingModuleAdapter(BackendModuleAdapter):
    """交易模块适配器"""
    
    def __init__(self):
        super().__init__('trading')
        self.trading_engine = None
        self._initialize_trading_engine()
    
    def _initialize_trading_engine(self):
        """初始化交易引擎"""
        if not self.available:
            return
        
        try:
            if hasattr(self.module, 'TradingEngine'):
                self.trading_engine = self.module.TradingEngine()
            logger.info("交易引擎初始化成功")
        except Exception as e:
            logger.error(f"交易引擎初始化失败: {e}")
    
    def get_positions(self) -> List[Dict]:
        """获取持仓信息"""
        if not self.available or not self.trading_engine:
            return self._generate_mock_positions()
        
        try:
            positions = self.trading_engine.get_positions()
            return self._format_positions(positions)
        except Exception as e:
            logger.error(f"获取持仓信息失败: {e}")
            return self._generate_mock_positions()
    
    def get_trades(self, limit: int = 100) -> List[Dict]:
        """获取交易记录"""
        if not self.available or not self.trading_engine:
            return self._generate_mock_trades(limit)
        
        try:
            trades = self.trading_engine.get_trades(limit)
            return self._format_trades(trades)
        except Exception as e:
            logger.error(f"获取交易记录失败: {e}")
            return self._generate_mock_trades(limit)
    
    def get_account_info(self) -> Dict:
        """获取账户信息"""
        if not self.available or not self.trading_engine:
            return self._generate_mock_account_info()
        
        try:
            account = self.trading_engine.get_account_info()
            return self._format_account_info(account)
        except Exception as e:
            logger.error(f"获取账户信息失败: {e}")
            return self._generate_mock_account_info()
    
    def _format_positions(self, positions) -> List[Dict]:
        """格式化持仓信息"""
        formatted_positions = []
        for position in positions:
            formatted_positions.append({
                'symbol': position.get('symbol', ''),
                'name': position.get('name', ''),
                'quantity': int(position.get('quantity', 0)),
                'available_quantity': int(position.get('available_quantity', 0)),
                'avg_price': float(position.get('avg_price', 0)),
                'current_price': float(position.get('current_price', 0)),
                'market_value': float(position.get('market_value', 0)),
                'pnl': float(position.get('pnl', 0)),
                'pnl_ratio': float(position.get('pnl_ratio', 0))
            })
        return formatted_positions
    
    def _format_trades(self, trades) -> List[Dict]:
        """格式化交易记录"""
        formatted_trades = []
        for trade in trades:
            formatted_trades.append({
                'order_id': trade.get('order_id', ''),
                'symbol': trade.get('symbol', ''),
                'side': trade.get('side', ''),
                'quantity': int(trade.get('quantity', 0)),
                'price': float(trade.get('price', 0)),
                'amount': float(trade.get('amount', 0)),
                'fee': float(trade.get('fee', 0)),
                'timestamp': trade.get('timestamp', ''),
                'status': trade.get('status', '')
            })
        return formatted_trades
    
    def _format_account_info(self, account) -> Dict:
        """格式化账户信息"""
        return {
            'total_value': float(account.get('total_value', 0)),
            'available_cash': float(account.get('available_cash', 0)),
            'market_value': float(account.get('market_value', 0)),
            'frozen_cash': float(account.get('frozen_cash', 0)),
            'profit_loss': float(account.get('profit_loss', 0)),
            'profit_loss_ratio': float(account.get('profit_loss_ratio', 0))
        }
    
    def _generate_mock_positions(self) -> List[Dict]:
        """生成模拟持仓数据"""
        import random
        
        positions = []
        symbols = ['000001.SZ', '000002.SZ', '600000.SH', '600036.SH', '000858.SZ']
        names = ['平安银行', '万科A', '浦发银行', '招商银行', '五粮液']
        
        for symbol, name in zip(symbols, names):
            if random.random() > 0.3:  # 70%概率有持仓
                quantity = random.randint(100, 1000) * 100
                avg_price = random.uniform(8, 50)
                current_price = avg_price * (1 + random.uniform(-0.1, 0.15))
                market_value = quantity * current_price
                pnl = quantity * (current_price - avg_price)
                
                positions.append({
                    'symbol': symbol,
                    'name': name,
                    'quantity': quantity,
                    'available_quantity': quantity,
                    'avg_price': round(avg_price, 2),
                    'current_price': round(current_price, 2),
                    'market_value': round(market_value, 2),
                    'pnl': round(pnl, 2),
                    'pnl_ratio': round(pnl / (quantity * avg_price), 4)
                })
        
        return positions
    
    def _generate_mock_trades(self, limit: int) -> List[Dict]:
        """生成模拟交易记录"""
        import random
        import uuid
        
        trades = []
        symbols = ['000001.SZ', '000002.SZ', '600000.SH', '600036.SH', '000858.SZ']
        
        for i in range(limit):
            symbol = random.choice(symbols)
            side = random.choice(['buy', 'sell'])
            quantity = random.randint(1, 10) * 100
            price = random.uniform(8, 50)
            amount = quantity * price
            fee = amount * 0.0003
            timestamp = datetime.now() - timedelta(days=random.randint(0, 30))
            
            trades.append({
                'order_id': str(uuid.uuid4())[:8],
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'price': round(price, 2),
                'amount': round(amount, 2),
                'fee': round(fee, 2),
                'timestamp': timestamp.isoformat(),
                'status': 'filled'
            })
        
        return sorted(trades, key=lambda x: x['timestamp'], reverse=True)
    
    def _generate_mock_account_info(self) -> Dict:
        """生成模拟账户信息"""
        import random
        
        total_value = 1000000
        market_value = random.uniform(200000, 800000)
        available_cash = total_value - market_value
        profit_loss = random.uniform(-50000, 100000)
        
        return {
            'total_value': round(total_value, 2),
            'available_cash': round(available_cash, 2),
            'market_value': round(market_value, 2),
            'frozen_cash': round(random.uniform(0, 10000), 2),
            'profit_loss': round(profit_loss, 2),
            'profit_loss_ratio': round(profit_loss / total_value, 4)
        }


class RiskModuleAdapter(BackendModuleAdapter):
    """风控模块适配器"""
    
    def __init__(self):
        super().__init__('risk')
        self.risk_manager = None
        self._initialize_risk_manager()
    
    def _initialize_risk_manager(self):
        """初始化风控管理器"""
        if not self.available:
            return
        
        try:
            if hasattr(self.module, 'RiskManager'):
                self.risk_manager = self.module.RiskManager()
            logger.info("风控管理器初始化成功")
        except Exception as e:
            logger.error(f"风控管理器初始化失败: {e}")
    
    def get_risk_alerts(self) -> List[Dict]:
        """获取风险告警"""
        if not self.available or not self.risk_manager:
            return self._generate_mock_alerts()
        
        try:
            alerts = self.risk_manager.get_alerts()
            return self._format_alerts(alerts)
        except Exception as e:
            logger.error(f"获取风险告警失败: {e}")
            return self._generate_mock_alerts()
    
    def get_risk_metrics(self) -> Dict:
        """获取风险指标"""
        if not self.available or not self.risk_manager:
            return self._generate_mock_metrics()
        
        try:
            metrics = self.risk_manager.get_metrics()
            return self._format_metrics(metrics)
        except Exception as e:
            logger.error(f"获取风险指标失败: {e}")
            return self._generate_mock_metrics()
    
    def _format_alerts(self, alerts) -> List[Dict]:
        """格式化风险告警"""
        formatted_alerts = []
        for alert in alerts:
            formatted_alerts.append({
                'id': alert.get('id', ''),
                'level': alert.get('level', 'INFO'),
                'title': alert.get('title', ''),
                'message': alert.get('message', ''),
                'timestamp': alert.get('timestamp', ''),
                'source': alert.get('source', ''),
                'resolved': alert.get('resolved', False)
            })
        return formatted_alerts
    
    def _format_metrics(self, metrics) -> Dict:
        """格式化风险指标"""
        return {
            'var_1d': metrics.get('var_1d', 0.0),
            'var_5d': metrics.get('var_5d', 0.0),
            'max_drawdown': metrics.get('max_drawdown', 0.0),
            'portfolio_beta': metrics.get('portfolio_beta', 0.0),
            'concentration_risk': metrics.get('concentration_risk', 0.0),
            'leverage_ratio': metrics.get('leverage_ratio', 0.0)
        }
    
    def _generate_mock_alerts(self) -> List[Dict]:
        """生成模拟风险告警"""
        import random
        import uuid
        
        alerts = []
        alert_levels = ['INFO', 'WARNING', 'ERROR', 'CRITICAL']
        alert_types = [
            ('持仓集中度风险', '单一股票持仓占比过高'),
            ('价格波动告警', '股票价格异常波动'),
            ('资金使用告警', '可用资金不足'),
            ('策略风险提醒', '策略回撤超过预警线'),
            ('系统异常告警', '系统连接异常')
        ]
        
        for i in range(random.randint(3, 8)):
            title, message = random.choice(alert_types)
            level = random.choice(alert_levels)
            timestamp = datetime.now() - timedelta(hours=random.randint(0, 24))
            
            alerts.append({
                'id': str(uuid.uuid4())[:8],
                'level': level,
                'title': title,
                'message': message,
                'timestamp': timestamp.isoformat(),
                'source': 'risk_manager',
                'resolved': random.choice([True, False])
            })
        
        return sorted(alerts, key=lambda x: x['timestamp'], reverse=True)
    
    def _generate_mock_metrics(self) -> Dict:
        """生成模拟风险指标"""
        import random
        
        return {
            'var_1d': round(random.uniform(0.01, 0.05), 4),
            'var_5d': round(random.uniform(0.03, 0.12), 4),
            'max_drawdown': round(random.uniform(0.05, 0.15), 4),
            'portfolio_beta': round(random.uniform(0.8, 1.2), 2),
            'concentration_risk': round(random.uniform(0.1, 0.4), 2),
            'leverage_ratio': round(random.uniform(0.0, 0.3), 2)
        }


class DataIntegrationManager:
    """数据集成管理器"""
    
    def __init__(self):
        self.data_adapter = DataModuleAdapter()
        self.strategy_adapter = StrategyModuleAdapter()
        self.trading_adapter = TradingModuleAdapter()
        self.risk_adapter = RiskModuleAdapter()
        
        self.adapters = {
            'data': self.data_adapter,
            'strategies': self.strategy_adapter,
            'trading': self.trading_adapter,
            'risk': self.risk_adapter
        }
        
        logger.info("数据集成管理器初始化完成")
    
    def get_module_status(self) -> Dict[str, Dict]:
        """获取所有模块状态"""
        status = {}
        for name, adapter in self.adapters.items():
            status[name] = adapter.get_module_info()
        return status
    
    def get_dashboard_summary(self) -> Dict:
        """获取仪表板汇总数据"""
        try:
            account_info = self.trading_adapter.get_account_info()
            positions = self.trading_adapter.get_positions()
            strategies = self.strategy_adapter.get_strategies()
            alerts = self.risk_adapter.get_risk_alerts()
            
            # 计算汇总数据
            total_positions = len(positions)
            active_strategies = len([s for s in strategies if s['status'] == 'running'])
            unresolved_alerts = len([a for a in alerts if not a['resolved']])
            
            # 计算当日盈亏（模拟）
            import random
            daily_pnl = random.uniform(-5000, 8000)
            daily_return = daily_pnl / account_info['total_value'] if account_info['total_value'] > 0 else 0
            
            return {
                'total_value': account_info['total_value'],
                'available_cash': account_info['available_cash'],
                'market_value': account_info['market_value'],
                'total_pnl': account_info['profit_loss'],
                'daily_pnl': round(daily_pnl, 2),
                'total_return': account_info['profit_loss_ratio'],
                'daily_return': round(daily_return, 4),
                'total_positions': total_positions,
                'active_strategies': active_strategies,
                'pending_alerts': unresolved_alerts,
                'update_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取仪表板汇总数据失败: {e}")
            # 返回默认数据
            return {
                'total_value': 1000000,
                'available_cash': 500000,
                'market_value': 500000,
                'total_pnl': 0,
                'daily_pnl': 0,
                'total_return': 0,
                'daily_return': 0,
                'total_positions': 0,
                'active_strategies': 0,
                'pending_alerts': 0,
                'update_time': datetime.now().isoformat()
            }
    
    def get_all_strategies(self) -> List[Dict]:
        """获取所有策略"""
        return self.strategy_adapter.get_strategies()
    
    def get_all_positions(self) -> List[Dict]:
        """获取所有持仓"""
        return self.trading_adapter.get_positions()
    
    def get_all_trades(self, limit: int = 100) -> List[Dict]:
        """获取所有交易记录"""
        return self.trading_adapter.get_trades(limit)
    
    def get_all_alerts(self) -> List[Dict]:
        """获取所有告警"""
        return self.risk_adapter.get_risk_alerts()
    
    def get_risk_metrics(self) -> Dict:
        """获取风险指标"""
        return self.risk_adapter.get_risk_metrics()


# 创建全局数据集成管理器实例
data_integration_manager = DataIntegrationManager()


def get_data_integration_manager() -> DataIntegrationManager:
    """获取数据集成管理器实例"""
    return data_integration_manager


if __name__ == "__main__":
    # 测试数据集成功能
    manager = DataIntegrationManager()
    
    print("模块状态:")
    status = manager.get_module_status()
    for name, info in status.items():
        print(f"  {name}: {'可用' if info['available'] else '不可用'}")
    
    print("\n仪表板汇总:")
    summary = manager.get_dashboard_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")