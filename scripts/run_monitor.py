#!/usr/bin/env python3
"""
量化交易监控面板启动脚本
=====================

用于启动监控面板Web应用的主要脚本。

使用方法:
python run_monitor.py [选项]

选项:
  --host HOST     监听地址 (默认: 127.0.0.1)
  --port PORT     监听端口 (默认: 5000)
  --debug         启用调试模式
  --config FILE   配置文件路径
  --no-realtime   禁用实时监控
  --test          运行测试模式
"""

import os
import sys
import argparse
import logging
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    from src.monitor.web_app import create_app
    from src.monitor.realtime_monitor import realtime_monitor
except ImportError as e:
    print(f"错误: 无法导入监控模块 - {e}")
    print("请确保已安装所有依赖项: pip install -r requirements.txt")
    sys.exit(1)


def setup_logging(debug=False):
    """设置日志记录"""
    log_level = logging.DEBUG if debug else logging.INFO
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # 创建日志目录
    log_dir = os.path.join(project_root, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 配置日志记录
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.FileHandler(
                os.path.join(log_dir, f'monitor_{datetime.now().strftime("%Y%m%d")}.log')
            ),
            logging.StreamHandler(sys.stdout)
        ]
    )


def load_config(config_file=None):
    """加载配置文件"""
    config = {
        'SECRET_KEY': 'dev-secret-key-change-in-production',
        'DEBUG': False,
        'TESTING': False,
        'DATABASE_URL': None,
        'REALTIME_ENABLED': True,
        'CACHE_SIZE': 1000,
        'CACHE_TTL': 300,
        'MAX_CLIENTS': 100,
        'UPDATE_INTERVAL': 1.0,
        'PORT_RANGE': (8765, 8770)
    }
    
    if config_file and os.path.exists(config_file):
        try:
            import json
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            config.update(user_config)
            print(f"已加载配置文件: {config_file}")
        except Exception as e:
            print(f"警告: 无法加载配置文件 {config_file}: {e}")
    
    return config


def check_dependencies():
    """检查依赖项"""
    required_packages = [
        'flask',
        'requests',
        'websockets',
        'asyncio'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("错误: 缺少以下依赖包:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\n请运行: pip install -r requirements.txt")
        return False
    
    return True


def check_backend_modules():
    """检查后端模块是否可用"""
    modules_status = {}
    
    # 检查数据模块
    try:
        import src.data
        modules_status['data'] = True
    except ImportError:
        modules_status['data'] = False
    
    # 检查策略模块
    try:
        import src.strategies
        modules_status['strategies'] = True
    except ImportError:
        modules_status['strategies'] = False
    
    # 检查交易模块
    try:
        import src.trading
        modules_status['trading'] = True
    except ImportError:
        modules_status['trading'] = False
    
    # 检查风控模块
    try:
        import src.risk
        modules_status['risk'] = True
    except ImportError:
        modules_status['risk'] = False
    
    return modules_status


def start_realtime_monitor(config):
    """启动实时监控"""
    if not config.get('REALTIME_ENABLED', True):
        return True
    
    try:
        # 配置实时监控参数
        realtime_monitor.configure(
            cache_size=config.get('CACHE_SIZE', 1000),
            cache_ttl=config.get('CACHE_TTL', 300),
            max_clients=config.get('MAX_CLIENTS', 100),
            update_interval=config.get('UPDATE_INTERVAL', 1.0),
            port_range=config.get('PORT_RANGE', (8765, 8770))
        )
        
        # 启动实时监控
        realtime_monitor.start()
        print("✓ 实时监控已启动")
        return True
        
    except Exception as e:
        print(f"✗ 启动实时监控失败: {e}")
        return False


def run_tests():
    """运行测试"""
    print("运行监控面板测试...")
    try:
        from src.monitor.test_monitor import main as test_main
        return test_main() == 0
    except ImportError:
        print("错误: 无法导入测试模块")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='量化交易监控面板启动脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_monitor.py                    # 使用默认设置启动
  python run_monitor.py --debug           # 启用调试模式
  python run_monitor.py --host 0.0.0.0    # 监听所有接口
  python run_monitor.py --port 8080       # 使用端口8080
  python run_monitor.py --config config.json  # 使用配置文件
  python run_monitor.py --test            # 运行测试模式
        """
    )
    
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='监听地址 (默认: 127.0.0.1)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='监听端口 (默认: 5000)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='启用调试模式'
    )
    
    parser.add_argument(
        '--config',
        help='配置文件路径'
    )
    
    parser.add_argument(
        '--no-realtime',
        action='store_true',
        help='禁用实时监控'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='运行测试模式'
    )
    
    args = parser.parse_args()
    
    # 设置日志记录
    setup_logging(args.debug)
    logger = logging.getLogger(__name__)
    
    print("=" * 60)
    print("量化交易监控面板")
    print("=" * 60)
    
    # 运行测试模式
    if args.test:
        success = run_tests()
        return 0 if success else 1
    
    # 检查依赖项
    print("检查依赖项...")
    if not check_dependencies():
        return 1
    print("✓ 依赖项检查通过")
    
    # 检查后端模块
    print("\n检查后端模块...")
    modules_status = check_backend_modules()
    for module, available in modules_status.items():
        status = "✓" if available else "✗"
        print(f"{status} {module}: {'可用' if available else '不可用'}")
    
    # 加载配置
    print("\n加载配置...")
    config = load_config(args.config)
    
    # 覆盖命令行参数
    if args.debug:
        config['DEBUG'] = True
    if args.no_realtime:
        config['REALTIME_ENABLED'] = False
    
    print("✓ 配置加载完成")
    
    # 启动实时监控
    print("\n启动实时监控...")
    if not start_realtime_monitor(config):
        print("警告: 实时监控启动失败，将在无实时功能模式下运行")
    
    # 创建Flask应用
    print("\n创建Web应用...")
    try:
        app = create_app(config)
        print("✓ Web应用创建成功")
    except Exception as e:
        logger.error(f"创建Web应用失败: {e}")
        return 1
    
    # 显示启动信息
    print("\n" + "=" * 60)
    print("启动信息:")
    print(f"- 监听地址: {args.host}")
    print(f"- 监听端口: {args.port}")
    print(f"- 调试模式: {'启用' if config['DEBUG'] else '禁用'}")
    print(f"- 实时监控: {'启用' if config['REALTIME_ENABLED'] else '禁用'}")
    print(f"- 访问地址: http://{args.host}:{args.port}")
    print("=" * 60)
    
    # 启动Web服务器
    try:
        print(f"\n启动监控面板...")
        print(f"请在浏览器中访问: http://{args.host}:{args.port}")
        print("按 Ctrl+C 停止服务器")
        
        app.run(
            host=args.host,
            port=args.port,
            debug=config['DEBUG'],
            use_reloader=False  # 避免重载器问题
        )
        
    except KeyboardInterrupt:
        print("\n\n收到停止信号，正在关闭服务器...")
        
    except Exception as e:
        logger.error(f"服务器运行错误: {e}")
        return 1
    
    finally:
        # 清理资源
        if config.get('REALTIME_ENABLED', True):
            try:
                realtime_monitor.stop()
                print("✓ 实时监控已停止")
            except Exception as e:
                logger.error(f"停止实时监控失败: {e}")
        
        print("监控面板已关闭")
    
    return 0


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)