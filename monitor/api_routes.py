"""
API路由定义
============

提供RESTful API接口，支持：
- 数据查询接口
- 策略管理接口  
- 交易操作接口
- 风控管理接口
- 系统管理接口
- 实时数据推送接口

主要功能：
- 统一的API响应格式
- 请求参数验证
- 错误处理和日志记录
- 权限验证
- 数据分页和筛选

API设计遵循RESTful规范：
- GET: 查询数据
- POST: 创建资源
- PUT: 更新资源  
- DELETE: 删除资源
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g, current_app
from functools import wraps
from typing import Dict, List, Any, Optional, Tuple
import json

# 导入后端模块
from data import get_database_manager, get_tushare_client
from strategies import (
    get_strategy_manager, get_strategy_catalog, AVAILABLE_STRATEGIES,
    create_strategy_by_name, list_strategy_categories
)
from backtest import BacktestEngine, PerformanceAnalyzer
from risk import RiskConfig, BaseRiskManager, RiskMonitor, RiskLevel
from trading.base_trader import OrderSide, OrderType, OrderStatus

# 导入仪表板控制器
from .dashboard import dashboard_controller

# 配置日志
logger = logging.getLogger(__name__)

# 创建API蓝图
api_bp = Blueprint('api', __name__)

# API响应状态码
class APIStatus:
    SUCCESS = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    INTERNAL_ERROR = 500

def api_response(success: bool = True, data: Any = None, message: str = "", 
                error: str = "", status_code: int = APIStatus.SUCCESS) -> Tuple[Dict, int]:
    """
    统一API响应格式
    
    Args:
        success: 是否成功
        data: 响应数据
        message: 成功消息
        error: 错误消息
        status_code: HTTP状态码
        
    Returns:
        响应数据和状态码
    """
    response = {
        'success': success,
        'timestamp': datetime.now().isoformat(),
        'message': message,
        'data': data
    }
    
    if not success:
        response['error'] = error
        
    return response, status_code

def validate_json_request(required_fields: List[str] = None):
    """
    验证JSON请求装饰器
    
    Args:
        required_fields: 必需字段列表
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return api_response(
                    success=False,
                    error="请求必须是JSON格式",
                    status_code=APIStatus.BAD_REQUEST
                )
            
            if required_fields:
                json_data = request.get_json()
                missing_fields = [field for field in required_fields if field not in json_data]
                if missing_fields:
                    return api_response(
                        success=False,
                        error=f"缺少必需字段: {', '.join(missing_fields)}",
                        status_code=APIStatus.BAD_REQUEST
                    )
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def handle_api_error(f):
    """API错误处理装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            logger.warning(f"API参数错误: {e}")
            return api_response(
                success=False,
                error=f"参数错误: {str(e)}",
                status_code=APIStatus.BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"API内部错误: {e}")
            return api_response(
                success=False,
                error="内部服务器错误",
                status_code=APIStatus.INTERNAL_ERROR
            )
    return decorated_function

# ========== 数据查询接口 ==========

@api_bp.route('/dashboard/summary', methods=['GET'])
@handle_api_error
def get_dashboard_summary():
    """获取仪表板汇总数据"""
    data = dashboard_controller.get_dashboard_summary()
    return api_response(
        success=True,
        data=data,
        message="仪表板数据获取成功"
    )

@api_bp.route('/strategies', methods=['GET'])
@handle_api_error
def get_strategies():
    """获取策略列表"""
    # 获取查询参数
    category = request.args.get('category')
    risk_level = request.args.get('risk_level')
    status = request.args.get('status')
    
    # 获取策略目录
    strategy_catalog = get_strategy_catalog()
    
    # 筛选策略
    if category:
        strategy_catalog = {k: v for k, v in strategy_catalog.items() 
                          if v.get('category') == category}
    
    if risk_level:
        strategy_catalog = {k: v for k, v in strategy_catalog.items() 
                          if v.get('risk_level') == risk_level}
    
    # 获取策略绩效数据
    performance_data = dashboard_controller.get_strategy_performance()
    
    # 合并数据
    strategies = []
    for name, info in strategy_catalog.items():
        perf = next((p for p in performance_data if p['name'] == name), {})
        strategy = {
            **info,
            'name': name,
            'performance': perf
        }
        
        # 状态筛选
        if status and perf.get('status') != status:
            continue
            
        strategies.append(strategy)
    
    return api_response(
        success=True,
        data={
            'strategies': strategies,
            'total': len(strategies),
            'categories': list_strategy_categories()
        },
        message="策略列表获取成功"
    )

@api_bp.route('/strategies/<strategy_name>', methods=['GET'])
@handle_api_error
def get_strategy_detail(strategy_name: str):
    """获取策略详情"""
    if strategy_name not in AVAILABLE_STRATEGIES:
        return api_response(
            success=False,
            error=f"策略 '{strategy_name}' 不存在",
            status_code=APIStatus.NOT_FOUND
        )
    
    strategy_info = AVAILABLE_STRATEGIES[strategy_name]
    performance_data = dashboard_controller.get_strategy_performance()
    perf = next((p for p in performance_data if p['name'] == strategy_name), {})
    
    return api_response(
        success=True,
        data={
            **strategy_info,
            'name': strategy_name,
            'performance': perf
        },
        message="策略详情获取成功"
    )

@api_bp.route('/positions', methods=['GET'])
@handle_api_error
def get_positions():
    """获取持仓列表"""
    # 获取查询参数
    symbol = request.args.get('symbol')
    sort_by = request.args.get('sort_by', 'market_value')
    order = request.args.get('order', 'desc')
    
    positions = dashboard_controller.get_position_data()
    
    # 筛选
    if symbol:
        positions = [p for p in positions if symbol.upper() in p['symbol'].upper()]
    
    # 排序
    reverse = order.lower() == 'desc'
    if sort_by in ['market_value', 'unrealized_pnl', 'pnl_ratio', 'weight']:
        positions.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)
    elif sort_by == 'symbol':
        positions.sort(key=lambda x: x.get('symbol', ''), reverse=reverse)
    
    # 计算汇总
    total_market_value = sum(p.get('market_value', 0) for p in positions)
    total_unrealized_pnl = sum(p.get('unrealized_pnl', 0) for p in positions)
    
    return api_response(
        success=True,
        data={
            'positions': positions,
            'summary': {
                'total_positions': len(positions),
                'total_market_value': total_market_value,
                'total_unrealized_pnl': total_unrealized_pnl,
                'total_pnl_ratio': total_unrealized_pnl / total_market_value if total_market_value > 0 else 0
            }
        },
        message="持仓数据获取成功"
    )

@api_bp.route('/trades', methods=['GET'])
@handle_api_error
def get_trades():
    """获取交易记录"""
    # 获取查询参数
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 50, type=int)
    symbol = request.args.get('symbol')
    side = request.args.get('side')
    status = request.args.get('status')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # 参数验证
    if limit > 1000:
        limit = 1000
    if page < 1:
        page = 1
    
    trades = dashboard_controller.get_trading_records(limit * 2)  # 获取更多数据用于筛选
    
    # 筛选
    if symbol:
        trades = [t for t in trades if symbol.upper() in t['symbol'].upper()]
    
    if side and side in ['buy', 'sell']:
        trades = [t for t in trades if t['side'] == side]
    
    if status:
        trades = [t for t in trades if t['status'] == status]
    
    # 日期筛选
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            trades = [t for t in trades if t['create_time'] >= start_dt]
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            trades = [t for t in trades if t['create_time'] <= end_dt]
        except ValueError:
            pass
    
    # 分页
    total = len(trades)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_trades = trades[start_idx:end_idx]
    
    return api_response(
        success=True,
        data={
            'trades': paginated_trades,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'pages': (total + limit - 1) // limit
            }
        },
        message="交易记录获取成功"
    )

@api_bp.route('/backtest/results', methods=['GET'])
@handle_api_error
def get_backtest_results():
    """获取回测结果"""
    results = dashboard_controller.get_backtest_results()
    return api_response(
        success=True,
        data=results,
        message="回测结果获取成功"
    )

@api_bp.route('/risk/alerts', methods=['GET'])
@handle_api_error
def get_risk_alerts():
    """获取风险告警"""
    level = request.args.get('level')
    status = request.args.get('status')
    limit = request.args.get('limit', 100, type=int)
    
    alerts = dashboard_controller.get_risk_alerts()
    
    # 筛选
    if level:
        alerts = [a for a in alerts if a.get('level') == level]
    
    if status:
        alerts = [a for a in alerts if a.get('status') == status]
    
    # 限制数量
    if limit > 0:
        alerts = alerts[:limit]
    
    return api_response(
        success=True,
        data={
            'alerts': alerts,
            'total': len(alerts)
        },
        message="风险告警获取成功"
    )

# ========== 策略管理接口 ==========

@api_bp.route('/strategies', methods=['POST'])
@validate_json_request(['strategy_name', 'instance_name'])
@handle_api_error
def create_strategy():
    """创建策略实例"""
    data = request.get_json()
    strategy_name = data['strategy_name']
    instance_name = data['instance_name']
    params = data.get('params', {})
    
    try:
        strategy = create_strategy_by_name(strategy_name, instance_name, params)
        return api_response(
            success=True,
            data={
                'instance_name': instance_name,
                'strategy_name': strategy_name,
                'params': params,
                'created_at': datetime.now().isoformat()
            },
            message="策略实例创建成功",
            status_code=APIStatus.CREATED
        )
    except ValueError as e:
        return api_response(
            success=False,
            error=str(e),
            status_code=APIStatus.BAD_REQUEST
        )

@api_bp.route('/strategies/<strategy_name>/start', methods=['POST'])
@handle_api_error
def start_strategy(strategy_name: str):
    """启动策略"""
    # 这里应该调用策略管理器的启动方法
    # 目前返回模拟响应
    return api_response(
        success=True,
        data={'strategy_name': strategy_name, 'status': 'started'},
        message=f"策略 {strategy_name} 启动成功"
    )

@api_bp.route('/strategies/<strategy_name>/stop', methods=['POST'])
@handle_api_error
def stop_strategy(strategy_name: str):
    """停止策略"""
    # 这里应该调用策略管理器的停止方法
    # 目前返回模拟响应
    return api_response(
        success=True,
        data={'strategy_name': strategy_name, 'status': 'stopped'},
        message=f"策略 {strategy_name} 停止成功"
    )

# ========== 交易操作接口 ==========

@api_bp.route('/orders', methods=['POST'])
@validate_json_request(['symbol', 'side', 'quantity'])
@handle_api_error
def submit_order():
    """提交订单"""
    data = request.get_json()
    
    # 参数验证
    symbol = data['symbol']
    side = data['side']
    quantity = data['quantity']
    order_type = data.get('order_type', 'market')
    price = data.get('price', 0.0)
    
    # 验证参数
    if side not in ['buy', 'sell']:
        return api_response(
            success=False,
            error="订单方向必须是 'buy' 或 'sell'",
            status_code=APIStatus.BAD_REQUEST
        )
    
    if quantity <= 0:
        return api_response(
            success=False,
            error="订单数量必须大于0",
            status_code=APIStatus.BAD_REQUEST
        )
    
    # 模拟订单提交
    order_id = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    return api_response(
        success=True,
        data={
            'order_id': order_id,
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'order_type': order_type,
            'price': price,
            'status': 'submitted',
            'submit_time': datetime.now().isoformat()
        },
        message="订单提交成功",
        status_code=APIStatus.CREATED
    )

@api_bp.route('/orders/<order_id>', methods=['DELETE'])
@handle_api_error
def cancel_order(order_id: str):
    """撤销订单"""
    # 这里应该调用交易接口的撤单方法
    # 目前返回模拟响应
    return api_response(
        success=True,
        data={
            'order_id': order_id,
            'status': 'cancelled',
            'cancel_time': datetime.now().isoformat()
        },
        message=f"订单 {order_id} 撤销成功"
    )

@api_bp.route('/orders/<order_id>', methods=['GET'])
@handle_api_error
def get_order_status(order_id: str):
    """查询订单状态"""
    # 模拟订单状态
    order_data = {
        'order_id': order_id,
        'symbol': '000001.SZ',
        'side': 'buy',
        'quantity': 1000,
        'price': 12.50,
        'filled_quantity': 500,
        'avg_fill_price': 12.48,
        'status': 'partial_filled',
        'create_time': (datetime.now() - timedelta(minutes=10)).isoformat(),
        'update_time': datetime.now().isoformat()
    }
    
    return api_response(
        success=True,
        data=order_data,
        message="订单状态查询成功"
    )

# ========== 风控管理接口 ==========

@api_bp.route('/risk/config', methods=['GET'])
@handle_api_error
def get_risk_config():
    """获取风控配置"""
    try:
        risk_config = RiskConfig()
        config_data = {
            'max_position_ratio': 0.1,
            'max_sector_ratio': 0.3,
            'stop_loss_ratio': 0.05,
            'take_profit_ratio': 0.15,
            'max_drawdown': 0.1,
            'risk_level': 'medium'
        }
        
        return api_response(
            success=True,
            data=config_data,
            message="风控配置获取成功"
        )
    except Exception as e:
        return api_response(
            success=False,
            error=f"获取风控配置失败: {str(e)}",
            status_code=APIStatus.INTERNAL_ERROR
        )

@api_bp.route('/risk/config', methods=['PUT'])
@validate_json_request()
@handle_api_error
def update_risk_config():
    """更新风控配置"""
    data = request.get_json()
    
    # 这里应该验证和更新风控配置
    # 目前返回模拟响应
    return api_response(
        success=True,
        data=data,
        message="风控配置更新成功"
    )

# ========== 系统管理接口 ==========

@api_bp.route('/system/status', methods=['GET'])
@handle_api_error
def get_system_status():
    """获取系统状态"""
    status_data = {
        'system_time': datetime.now().isoformat(),
        'uptime': '2 days, 3 hours, 45 minutes',
        'memory_usage': 0.65,
        'cpu_usage': 0.35,
        'disk_usage': 0.25,
        'database_status': 'connected',
        'trading_status': 'enabled',
        'risk_engine_status': 'running'
    }
    
    return api_response(
        success=True,
        data=status_data,
        message="系统状态获取成功"
    )

@api_bp.route('/system/logs', methods=['GET'])
@handle_api_error
def get_system_logs():
    """获取系统日志"""
    level = request.args.get('level', 'INFO')
    limit = request.args.get('limit', 100, type=int)
    
    # 模拟日志数据
    logs = []
    for i in range(min(limit, 50)):
        log_entry = {
            'timestamp': (datetime.now() - timedelta(minutes=i)).isoformat(),
            'level': ['INFO', 'WARNING', 'ERROR'][i % 3] if level == 'ALL' else level,
            'module': ['策略引擎', '风控系统', '交易接口'][i % 3],
            'message': f"模拟日志消息 {i+1}"
        }
        logs.append(log_entry)
    
    return api_response(
        success=True,
        data={
            'logs': logs,
            'total': len(logs)
        },
        message="系统日志获取成功"
    )

# ========== 数据导出接口 ==========

@api_bp.route('/export/positions', methods=['GET'])
@handle_api_error
def export_positions():
    """导出持仓数据"""
    format_type = request.args.get('format', 'json')
    
    positions = dashboard_controller.get_position_data()
    
    if format_type.lower() == 'csv':
        # 这里应该生成CSV格式数据
        return api_response(
            success=True,
            data={'format': 'csv', 'download_url': '/api/download/positions.csv'},
            message="持仓数据导出准备完成"
        )
    else:
        return api_response(
            success=True,
            data=positions,
            message="持仓数据导出成功"
        )

@api_bp.route('/export/trades', methods=['GET'])
@handle_api_error
def export_trades():
    """导出交易记录"""
    format_type = request.args.get('format', 'json')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    trades = dashboard_controller.get_trading_records(1000)
    
    return api_response(
        success=True,
        data=trades,
        message="交易记录导出成功"
    )

# ========== WebSocket实时数据接口 ==========

@api_bp.route('/ws/subscribe', methods=['POST'])
@validate_json_request(['channels'])
@handle_api_error
def subscribe_realtime_data():
    """订阅实时数据"""
    data = request.get_json()
    channels = data['channels']
    
    # 验证频道
    valid_channels = ['quotes', 'positions', 'orders', 'alerts']
    invalid_channels = [ch for ch in channels if ch not in valid_channels]
    
    if invalid_channels:
        return api_response(
            success=False,
            error=f"无效的订阅频道: {', '.join(invalid_channels)}",
            status_code=APIStatus.BAD_REQUEST
        )
    
    return api_response(
        success=True,
        data={
            'subscribed_channels': channels,
            'websocket_url': 'ws://localhost:5000/ws'
        },
        message="实时数据订阅成功"
    )

# 错误处理
@api_bp.errorhandler(404)
def api_not_found(error):
    """API端点不存在"""
    return api_response(
        success=False,
        error="API端点不存在",
        status_code=APIStatus.NOT_FOUND
    )

@api_bp.errorhandler(405)
def method_not_allowed(error):
    """HTTP方法不允许"""
    return api_response(
        success=False,
        error="HTTP方法不允许",
        status_code=405
    )