"""
仪表板控制器
=============

提供监控面板的页面路由和数据处理功能，包括：
- 首页仪表板：总览所有关键指标
- 策略监控页：实时策略运行状态
- 持仓管理页：当前持仓和盈亏情况
- 交易记录页：历史交易明细
- 回测分析页：回测结果和绩效分析
- 风控监控页：风险指标和告警信息
- 系统设置页：参数配置和系统管理

主要功能：
- 页面路由处理
- 数据聚合和格式化
- 实时数据获取
- 图表数据准备
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from typing import Dict, List, Any, Optional
import json

# 导入后端模块
from data import get_database_manager, get_tushare_client
from strategies import get_strategy_manager, get_strategy_catalog, AVAILABLE_STRATEGIES
from backtest import BacktestEngine, PerformanceAnalyzer, BacktestVisualizer
from risk import RiskConfig, BaseRiskManager, RiskMonitor
from trading.base_trader import OrderStatus, OrderSide, OrderType

# 配置日志
logger = logging.getLogger(__name__)

# 创建仪表板蓝图
dashboard_bp = Blueprint('dashboard', __name__)

class DashboardController:
    """仪表板控制器类"""
    
    def __init__(self):
        self.db_manager = None
        self.strategy_manager = None
        self.risk_manager = None
        self.risk_monitor = None
        self._init_components()
    
    def _init_components(self):
        """初始化各个组件"""
        try:
            # 初始化数据库管理器
            self.db_manager = get_database_manager()
            
            # 初始化策略管理器
            self.strategy_manager = get_strategy_manager()
            
            # 初始化风控组件
            risk_config = RiskConfig()
            self.risk_manager = BaseRiskManager(risk_config)
            self.risk_monitor = RiskMonitor(risk_config)
            
            logger.info("仪表板控制器组件初始化完成")
            
        except Exception as e:
            logger.error(f"仪表板控制器初始化失败: {e}")
    
    def get_dashboard_summary(self) -> Dict[str, Any]:
        """获取仪表板汇总数据"""
        try:
            # 模拟数据 - 实际应该从数据库或策略管理器获取
            summary = {
                'total_value': 1000000.0,
                'available_cash': 200000.0,
                'total_pnl': 50000.0,
                'daily_pnl': 2500.0,
                'total_return': 0.05,
                'daily_return': 0.0025,
                'running_strategies': 3,
                'total_positions': 8,
                'alerts_count': 2,
                'update_time': datetime.now()
            }
            
            # 获取策略状态
            if self.strategy_manager:
                summary['strategy_status'] = self._get_strategy_status()
            
            # 获取风险指标
            if self.risk_monitor:
                summary['risk_metrics'] = self._get_risk_metrics()
            
            return summary
            
        except Exception as e:
            logger.error(f"获取仪表板汇总数据失败: {e}")
            return self._get_default_summary()
    
    def get_strategy_performance(self) -> List[Dict[str, Any]]:
        """获取策略绩效数据"""
        try:
            # 模拟策略绩效数据
            strategies = []
            for strategy_name, strategy_info in AVAILABLE_STRATEGIES.items():
                perf = {
                    'name': strategy_name,
                    'display_name': strategy_info['name'],
                    'status': 'running',
                    'total_return': 0.08 + hash(strategy_name) % 10 * 0.01,
                    'daily_return': 0.002 + hash(strategy_name) % 5 * 0.001,
                    'max_drawdown': -0.05 - hash(strategy_name) % 3 * 0.01,
                    'sharpe_ratio': 1.2 + hash(strategy_name) % 8 * 0.1,
                    'positions': hash(strategy_name) % 5 + 1,
                    'last_signal': datetime.now() - timedelta(minutes=hash(strategy_name) % 60)
                }
                strategies.append(perf)
            
            return strategies
            
        except Exception as e:
            logger.error(f"获取策略绩效数据失败: {e}")
            return []
    
    def get_position_data(self) -> List[Dict[str, Any]]:
        """获取持仓数据"""
        try:
            # 模拟持仓数据
            positions = [
                {
                    'symbol': '000001.SZ',
                    'name': '平安银行',
                    'quantity': 1000,
                    'avg_price': 12.50,
                    'current_price': 13.20,
                    'market_value': 13200.0,
                    'unrealized_pnl': 700.0,
                    'pnl_ratio': 0.056,
                    'weight': 0.132
                },
                {
                    'symbol': '000002.SZ', 
                    'name': '万科A',
                    'quantity': 500,
                    'avg_price': 18.80,
                    'current_price': 19.50,
                    'market_value': 9750.0,
                    'unrealized_pnl': 350.0,
                    'pnl_ratio': 0.037,
                    'weight': 0.098
                },
                {
                    'symbol': '600036.SH',
                    'name': '招商银行',
                    'quantity': 300,
                    'avg_price': 35.20,
                    'current_price': 36.80,
                    'market_value': 11040.0,
                    'unrealized_pnl': 480.0,
                    'pnl_ratio': 0.045,
                    'weight': 0.110
                }
            ]
            
            return positions
            
        except Exception as e:
            logger.error(f"获取持仓数据失败: {e}")
            return []
    
    def get_trading_records(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取交易记录"""
        try:
            # 模拟交易记录
            records = []
            base_time = datetime.now()
            
            for i in range(limit):
                record = {
                    'order_id': f'ORD{20240818}{1001+i:04d}',
                    'symbol': ['000001.SZ', '000002.SZ', '600036.SH'][i % 3],
                    'name': ['平安银行', '万科A', '招商银行'][i % 3],
                    'side': 'buy' if i % 2 == 0 else 'sell',
                    'quantity': (i % 5 + 1) * 100,
                    'price': 10.0 + (i % 20),
                    'amount': (10.0 + (i % 20)) * ((i % 5 + 1) * 100),
                    'status': 'filled',
                    'create_time': base_time - timedelta(hours=i),
                    'update_time': base_time - timedelta(hours=i) + timedelta(minutes=5)
                }
                records.append(record)
            
            return records
            
        except Exception as e:
            logger.error(f"获取交易记录失败: {e}")
            return []
    
    def get_backtest_results(self) -> Dict[str, Any]:
        """获取回测结果数据"""
        try:
            # 模拟回测结果
            results = {
                'summary': {
                    'total_return': 0.245,
                    'annual_return': 0.186,
                    'max_drawdown': -0.085,
                    'sharpe_ratio': 1.42,
                    'win_rate': 0.65,
                    'profit_loss_ratio': 1.8,
                    'total_trades': 156
                },
                'equity_curve': self._generate_equity_curve(),
                'monthly_returns': self._generate_monthly_returns(),
                'drawdown_curve': self._generate_drawdown_curve()
            }
            
            return results
            
        except Exception as e:
            logger.error(f"获取回测结果失败: {e}")
            return {}
    
    def get_risk_alerts(self) -> List[Dict[str, Any]]:
        """获取风险告警"""
        try:
            alerts = [
                {
                    'id': 1,
                    'level': 'warning',
                    'title': '单票持仓超限',
                    'message': '000001.SZ持仓比例13.2%，超过单票限制10%',
                    'timestamp': datetime.now() - timedelta(minutes=15),
                    'status': 'active'
                },
                {
                    'id': 2,
                    'level': 'info',
                    'title': '策略信号',
                    'message': 'RSI策略产生买入信号：600036.SH',
                    'timestamp': datetime.now() - timedelta(minutes=30),
                    'status': 'acknowledged'
                }
            ]
            
            return alerts
            
        except Exception as e:
            logger.error(f"获取风险告警失败: {e}")
            return []
    
    def _get_strategy_status(self) -> Dict[str, Any]:
        """获取策略状态"""
        return {
            'total_strategies': len(AVAILABLE_STRATEGIES),
            'running_strategies': 3,
            'stopped_strategies': len(AVAILABLE_STRATEGIES) - 3,
            'error_strategies': 0
        }
    
    def _get_risk_metrics(self) -> Dict[str, Any]:
        """获取风险指标"""
        return {
            'var_1d': -0.02,
            'var_5d': -0.045,
            'max_drawdown': -0.085,
            'concentration_risk': 0.68,
            'leverage_ratio': 1.2,
            'risk_level': 'medium'
        }
    
    def _get_default_summary(self) -> Dict[str, Any]:
        """获取默认汇总数据"""
        return {
            'total_value': 0.0,
            'available_cash': 0.0,
            'total_pnl': 0.0,
            'daily_pnl': 0.0,
            'total_return': 0.0,
            'daily_return': 0.0,
            'running_strategies': 0,
            'total_positions': 0,
            'alerts_count': 0,
            'update_time': datetime.now()
        }
    
    def _generate_equity_curve(self) -> List[Dict[str, Any]]:
        """生成净值曲线数据"""
        curve_data = []
        base_date = datetime.now() - timedelta(days=252)  # 一年交易日
        base_value = 1.0
        
        for i in range(252):
            # 模拟净值波动
            daily_return = (hash(f"equity_{i}") % 100 - 50) / 10000  # -0.5% 到 0.5%
            base_value *= (1 + daily_return)
            
            curve_data.append({
                'date': (base_date + timedelta(days=i)).strftime('%Y-%m-%d'),
                'value': base_value,
                'benchmark': 1.0 + i * 0.0002  # 基准年化2%收益
            })
        
        return curve_data
    
    def _generate_monthly_returns(self) -> List[Dict[str, Any]]:
        """生成月度收益数据"""
        monthly_data = []
        base_date = datetime.now() - timedelta(days=365)
        
        for i in range(12):
            month_date = base_date + timedelta(days=i*30)
            monthly_return = (hash(f"monthly_{i}") % 200 - 100) / 1000  # -10% 到 10%
            
            monthly_data.append({
                'month': month_date.strftime('%Y-%m'),
                'return': monthly_return,
                'benchmark': 0.02 / 12  # 基准月度收益
            })
        
        return monthly_data
    
    def _generate_drawdown_curve(self) -> List[Dict[str, Any]]:
        """生成回撤曲线数据"""
        drawdown_data = []
        base_date = datetime.now() - timedelta(days=252)
        max_value = 1.0
        current_value = 1.0
        
        for i in range(252):
            # 模拟价格波动
            daily_return = (hash(f"drawdown_{i}") % 100 - 50) / 10000
            current_value *= (1 + daily_return)
            max_value = max(max_value, current_value)
            
            drawdown = (current_value - max_value) / max_value
            
            drawdown_data.append({
                'date': (base_date + timedelta(days=i)).strftime('%Y-%m-%d'),
                'drawdown': drawdown
            })
        
        return drawdown_data

# 创建控制器实例
dashboard_controller = DashboardController()

# 路由定义
@dashboard_bp.route('/')
def dashboard():
    """首页仪表板"""
    try:
        summary_data = dashboard_controller.get_dashboard_summary()
        return render_template('dashboard.html', summary=summary_data)
    except Exception as e:
        logger.error(f"仪表板页面加载失败: {e}")
        flash(f"加载仪表板数据失败: {e}", 'error')
        return render_template('dashboard.html', summary=dashboard_controller._get_default_summary())

@dashboard_bp.route('/strategies')
def strategies():
    """策略监控页"""
    try:
        strategy_data = dashboard_controller.get_strategy_performance()
        strategy_catalog = get_strategy_catalog()
        return render_template('strategies.html', 
                             strategies=strategy_data,
                             catalog=strategy_catalog)
    except Exception as e:
        logger.error(f"策略监控页面加载失败: {e}")
        flash(f"加载策略数据失败: {e}", 'error')
        return render_template('strategies.html', strategies=[], catalog={})

@dashboard_bp.route('/positions')
def positions():
    """持仓管理页"""
    try:
        position_data = dashboard_controller.get_position_data()
        return render_template('positions.html', positions=position_data)
    except Exception as e:
        logger.error(f"持仓管理页面加载失败: {e}")
        flash(f"加载持仓数据失败: {e}", 'error')
        return render_template('positions.html', positions=[])

@dashboard_bp.route('/trades')
def trades():
    """交易记录页"""
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        
        trading_data = dashboard_controller.get_trading_records(limit)
        return render_template('trades.html', trades=trading_data, page=page)
    except Exception as e:
        logger.error(f"交易记录页面加载失败: {e}")
        flash(f"加载交易数据失败: {e}", 'error')
        return render_template('trades.html', trades=[], page=1)

@dashboard_bp.route('/backtest')
def backtest():
    """回测分析页"""
    try:
        backtest_data = dashboard_controller.get_backtest_results()
        return render_template('backtest.html', results=backtest_data)
    except Exception as e:
        logger.error(f"回测分析页面加载失败: {e}")
        flash(f"加载回测数据失败: {e}", 'error')
        return render_template('backtest.html', results={})

@dashboard_bp.route('/risk')
def risk():
    """风控监控页"""
    try:
        risk_alerts = dashboard_controller.get_risk_alerts()
        summary = dashboard_controller.get_dashboard_summary()
        risk_metrics = summary.get('risk_metrics', {})
        
        return render_template('risk.html', 
                             alerts=risk_alerts,
                             metrics=risk_metrics)
    except Exception as e:
        logger.error(f"风控监控页面加载失败: {e}")
        flash(f"加载风控数据失败: {e}", 'error')
        return render_template('risk.html', alerts=[], metrics={})

@dashboard_bp.route('/settings')
def settings():
    """系统设置页"""
    try:
        return render_template('settings.html')
    except Exception as e:
        logger.error(f"系统设置页面加载失败: {e}")
        flash(f"加载设置页面失败: {e}", 'error')
        return render_template('settings.html')

# AJAX数据接口
@dashboard_bp.route('/ajax/summary')
def ajax_summary():
    """AJAX获取汇总数据"""
    try:
        data = dashboard_controller.get_dashboard_summary()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"AJAX获取汇总数据失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@dashboard_bp.route('/ajax/strategies')
def ajax_strategies():
    """AJAX获取策略数据"""
    try:
        data = dashboard_controller.get_strategy_performance()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"AJAX获取策略数据失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@dashboard_bp.route('/ajax/positions')
def ajax_positions():
    """AJAX获取持仓数据"""
    try:
        data = dashboard_controller.get_position_data()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"AJAX获取持仓数据失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@dashboard_bp.route('/ajax/alerts')
def ajax_alerts():
    """AJAX获取告警数据"""
    try:
        data = dashboard_controller.get_risk_alerts()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"AJAX获取告警数据失败: {e}")
        return jsonify({'success': False, 'error': str(e)})