"""
Flask Web应用主程序
==================

提供量化交易监控面板的Web服务，包括：
- Flask应用初始化和配置
- 蓝图注册
- 静态文件服务
- 会话管理
- 错误处理
- 中间件集成

主要功能：
- 监控面板Web界面
- RESTful API接口
- 实时数据推送
- 用户认证和权限管理
"""

import os
import logging
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from datetime import datetime
import json

# 导入配置
from config.settings import Config

# 导入后端模块
from data import get_database_manager, get_tushare_client
from strategies import get_strategy_manager, get_strategy_catalog
from backtest import BacktestEngine, PerformanceAnalyzer
from risk import RiskConfig, BaseRiskManager, RiskMonitor
from trading.base_trader import BaseTrader

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app(config_class=Config):
    """
    创建Flask应用实例
    
    Args:
        config_class: 配置类
        
    Returns:
        Flask应用实例
    """
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static')
    
    # 应用配置
    app.config.from_object(config_class)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
    app.config['JSON_AS_ASCII'] = False
    
    # 启用CORS
    CORS(app)
    
    # 注册蓝图
    register_blueprints(app)
    
    # 注册错误处理器
    register_error_handlers(app)
    
    # 注册模板上下文处理器
    register_template_context(app)
    
    # 初始化监控数据
    init_monitor_data(app)
    
    logger.info("Flask应用已创建并初始化完成")
    return app

def register_blueprints(app):
    """注册蓝图"""
    # 延迟导入避免循环依赖
    from .api_routes import api_bp
    from .dashboard import dashboard_bp
    
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    
    logger.info("蓝图注册完成")

def register_error_handlers(app):
    """注册错误处理器"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error': 'API端点不存在',
                'path': request.path
            }), 404
        return render_template('error.html', 
                             error_code=404, 
                             error_message="页面未找到"), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"内部服务器错误: {error}")
        if request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error': '内部服务器错误',
                'message': str(error)
            }), 500
        return render_template('error.html',
                             error_code=500,
                             error_message="内部服务器错误"), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        if request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error': '访问被禁止',
                'message': str(error)
            }), 403
        return render_template('error.html',
                             error_code=403,
                             error_message="访问被禁止"), 403

def register_template_context(app):
    """注册模板上下文处理器"""
    
    @app.context_processor
    def inject_global_vars():
        """注入全局模板变量"""
        return {
            'app_name': '量化交易监控面板',
            'current_time': datetime.now(),
            'version': '1.0.0'
        }
    
    @app.template_filter('datetime_format')
    def datetime_format(value, format='%Y-%m-%d %H:%M:%S'):
        """日期时间格式化过滤器"""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except:
                return value
        return value.strftime(format) if value else ''
    
    @app.template_filter('number_format')
    def number_format(value, decimal_places=2):
        """数字格式化过滤器"""
        try:
            return f"{float(value):,.{decimal_places}f}"
        except:
            return value
    
    @app.template_filter('percentage')
    def percentage_format(value, decimal_places=2):
        """百分比格式化过滤器"""
        try:
            return f"{float(value)*100:.{decimal_places}f}%"
        except:
            return value

def init_monitor_data(app):
    """初始化监控数据"""
    with app.app_context():
        try:
            # 初始化数据库连接
            db_manager = get_database_manager()
            if db_manager:
                logger.info("数据库连接已初始化")
            
            # 初始化数据源
            tushare_client = get_tushare_client()
            if tushare_client:
                logger.info("Tushare客户端已初始化")
            
            # 初始化策略管理器
            strategy_manager = get_strategy_manager()
            if strategy_manager:
                logger.info("策略管理器已初始化")
                
            # 初始化风控系统
            risk_config = RiskConfig()
            risk_manager = BaseRiskManager(risk_config)
            if risk_manager:
                logger.info("风控系统已初始化")
                
        except Exception as e:
            logger.error(f"监控数据初始化失败: {e}")

# 创建全局应用实例
app = create_app()

# 主路由
@app.route('/')
def index():
    """首页 - 重定向到仪表板"""
    return render_template('dashboard.html')

@app.route('/health')
def health_check():
    """健康检查端点"""
    try:
        # 检查各个模块状态
        status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'modules': {
                'database': check_database_status(),
                'strategies': check_strategies_status(),
                'risk_management': check_risk_status(),
                'trading': check_trading_status()
            }
        }
        
        # 检查是否有模块不健康
        unhealthy_modules = [k for k, v in status['modules'].items() if not v.get('healthy', False)]
        if unhealthy_modules:
            status['status'] = 'degraded'
            status['unhealthy_modules'] = unhealthy_modules
            
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

def check_database_status():
    """检查数据库状态"""
    try:
        db_manager = get_database_manager()
        if db_manager and hasattr(db_manager, 'test_connection'):
            return {'healthy': db_manager.test_connection(), 'message': '数据库连接正常'}
        return {'healthy': True, 'message': '数据库模块已加载'}
    except Exception as e:
        return {'healthy': False, 'message': f'数据库检查失败: {e}'}

def check_strategies_status():
    """检查策略状态"""
    try:
        strategy_catalog = get_strategy_catalog()
        strategy_count = len(strategy_catalog)
        return {
            'healthy': strategy_count > 0,
            'message': f'已加载 {strategy_count} 个策略',
            'strategy_count': strategy_count
        }
    except Exception as e:
        return {'healthy': False, 'message': f'策略检查失败: {e}'}

def check_risk_status():
    """检查风控状态"""
    try:
        risk_config = RiskConfig()
        return {
            'healthy': True,
            'message': '风控系统正常',
            'config_loaded': bool(risk_config)
        }
    except Exception as e:
        return {'healthy': False, 'message': f'风控检查失败: {e}'}

def check_trading_status():
    """检查交易状态"""
    try:
        # 这里可以检查交易接口状态
        return {
            'healthy': True,
            'message': '交易模块已加载',
            'note': '实际交易状态需要连接具体交易接口'
        }
    except Exception as e:
        return {'healthy': False, 'message': f'交易检查失败: {e}'}

if __name__ == '__main__':
    # 开发模式运行
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    logger.info(f"启动Flask应用，端口: {port}, 调试模式: {debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)