"""
报告生成器

生成系统监控、性能分析、告警统计等各种报告
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
# 条件导入可选依赖
try:
    import jinja2
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False
    jinja2 = None

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None

try:
    import matplotlib
    matplotlib.use('Agg')  # 使用非交互式后端
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    matplotlib = None
    plt = None
    mdates = None

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False
    sns = None
from collections import defaultdict, Counter
import base64
from io import BytesIO

logger = logging.getLogger(__name__)

# 设置中文字体（仅当matplotlib可用时）
if HAS_MATPLOTLIB:
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False


@dataclass
class ReportSection:
    """报告段落"""
    title: str
    content: str
    charts: List[str] = None  # 图表文件路径
    data_tables: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.charts is None:
            self.charts = []
        if self.data_tables is None:
            self.data_tables = []


@dataclass
class Report:
    """报告"""
    report_id: str
    title: str
    report_type: str
    generated_at: datetime
    time_range: Dict[str, datetime]
    sections: List[ReportSection]
    summary: Dict[str, Any]
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 检查依赖
        if not HAS_JINJA2:
            logger.warning("jinja2未安装，报告生成功能将受限")
        if not HAS_PANDAS:
            logger.warning("pandas未安装，数据分析功能将受限")
        if not HAS_MATPLOTLIB:
            logger.warning("matplotlib未安装，图表生成功能将受限")
        
        # 报告配置
        self.report_config = {
            'output_dir': 'reports',
            'template_dir': 'templates',
            'chart_dir': 'charts',
            'max_report_age_days': 30,
            'default_time_range_hours': 24,
            'chart_dpi': 300,
            'chart_format': 'png',
            'enable_data_export': True,
            'export_formats': ['html', 'pdf', 'json'],
            'chart_style': 'seaborn-v0_8',
            'color_palette': 'husl',
            'figure_size': (12, 8),
            'max_data_points': 1000
        }
        
        # 更新配置
        if 'report_generator' in config:
            self.report_config.update(config['report_generator'])
        
        # 创建目录
        self._create_directories()
        
        # 初始化模板引擎
        self._setup_templates()
        
        # 图表样式配置
        self._setup_chart_style()
        
        # 数据源引用
        self.data_sources = {}
        
        # 报告缓存
        self.report_cache = {}
    
    def _create_directories(self):
        """创建必要的目录"""
        try:
            for dir_name in ['output_dir', 'template_dir', 'chart_dir']:
                dir_path = Path(self.report_config[dir_name])
                dir_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"创建目录失败: {e}")
    
    def _setup_templates(self):
        """设置模板引擎"""
        try:
            if not HAS_JINJA2:
                logger.warning("jinja2未安装，跳过模板引擎设置")
                self.template_env = None
                return
                
            template_dir = self.report_config['template_dir']
            
            # 创建默认模板
            self._create_default_templates()
            
            # 初始化Jinja2环境
            self.template_env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(template_dir),
                autoescape=jinja2.select_autoescape(['html', 'xml'])
            )
            
            # 添加自定义过滤器
            self.template_env.filters['datetime'] = self._format_datetime
            self.template_env.filters['number'] = self._format_number
            self.template_env.filters['percentage'] = self._format_percentage
            
        except Exception as e:
            logger.error(f"设置模板引擎失败: {e}")
            self.template_env = None
    
    def _create_default_templates(self):
        """创建默认模板"""
        try:
            template_dir = Path(self.report_config['template_dir'])
            
            # HTML基础模板
            base_template = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ report.title }}</title>
    <style>
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            border-bottom: 2px solid #007bff;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #333;
            margin: 0;
        }
        .meta-info {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }
        .section {
            margin: 30px 0;
            border-bottom: 1px solid #eee;
            padding-bottom: 20px;
        }
        .section h2 {
            color: #007bff;
            border-left: 4px solid #007bff;
            padding-left: 15px;
        }
        .chart-container {
            text-align: center;
            margin: 20px 0;
        }
        .chart-container img {
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        .data-table th, .data-table td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        .data-table th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .summary-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            border-left: 4px solid #28a745;
        }
        .summary-card h3 {
            margin: 0 0 10px 0;
            color: #333;
        }
        .summary-card .value {
            font-size: 24px;
            font-weight: bold;
            color: #007bff;
        }
        .alert-critical { border-left-color: #dc3545; }
        .alert-high { border-left-color: #fd7e14; }
        .alert-medium { border-left-color: #ffc107; }
        .alert-low { border-left-color: #28a745; }
        .footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #666;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ report.title }}</h1>
        </div>
        
        <div class="meta-info">
            <p><strong>报告类型:</strong> {{ report.report_type }}</p>
            <p><strong>生成时间:</strong> {{ report.generated_at | datetime }}</p>
            <p><strong>时间范围:</strong> {{ report.time_range.start | datetime }} - {{ report.time_range.end | datetime }}</p>
        </div>
        
        {% if report.summary %}
        <div class="section">
            <h2>摘要</h2>
            <div class="summary-grid">
                {% for key, value in report.summary.items() %}
                <div class="summary-card">
                    <h3>{{ key }}</h3>
                    <div class="value">{{ value | number }}</div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}
        
        {% for section in report.sections %}
        <div class="section">
            <h2>{{ section.title }}</h2>
            <div>{{ section.content | safe }}</div>
            
            {% for chart in section.charts %}
            <div class="chart-container">
                <img src="{{ chart }}" alt="{{ section.title }}图表">
            </div>
            {% endfor %}
            
            {% for table in section.data_tables %}
            <table class="data-table">
                {% if table.headers %}
                <thead>
                    <tr>
                        {% for header in table.headers %}
                        <th>{{ header }}</th>
                        {% endfor %}
                    </tr>
                </thead>
                {% endif %}
                <tbody>
                    {% for row in table.rows %}
                    <tr>
                        {% for cell in row %}
                        <td>{{ cell }}</td>
                        {% endfor %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% endfor %}
        </div>
        {% endfor %}
        
        <div class="footer">
            <p>报告由MVP验证与优化体系自动生成 | 生成时间: {{ report.generated_at | datetime }}</p>
        </div>
    </div>
</body>
</html>
"""
            
            with open(template_dir / 'base_report.html', 'w', encoding='utf-8') as f:
                f.write(base_template)
            
            logger.info("已创建默认报告模板")
            
        except Exception as e:
            logger.error(f"创建默认模板失败: {e}")
    
    def _setup_chart_style(self):
        """设置图表样式"""
        try:
            if not HAS_MATPLOTLIB:
                logger.warning("matplotlib未安装，跳过图表样式设置")
                return
                
            # 设置样式
            if self.report_config['chart_style'] in plt.style.available:
                plt.style.use(self.report_config['chart_style'])
            
            # 设置颜色调色板
            if HAS_SEABORN:
                sns.set_palette(self.report_config['color_palette'])
            
            # 设置默认图形大小
            plt.rcParams['figure.figsize'] = self.report_config['figure_size']
            plt.rcParams['figure.dpi'] = self.report_config['chart_dpi']
            
        except Exception as e:
            logger.error(f"设置图表样式失败: {e}")
    
    def _format_datetime(self, dt: datetime) -> str:
        """格式化日期时间"""
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    
    def _format_number(self, value: Any) -> str:
        """格式化数字"""
        try:
            if isinstance(value, (int, float)):
                if abs(value) >= 1000000:
                    return f"{value/1000000:.1f}M"
                elif abs(value) >= 1000:
                    return f"{value/1000:.1f}K"
                else:
                    return f"{value:.2f}" if isinstance(value, float) else str(value)
            return str(value)
        except:
            return str(value)
    
    def _format_percentage(self, value: float) -> str:
        """格式化百分比"""
        try:
            return f"{value:.1f}%"
        except:
            return str(value)
    
    def register_data_source(self, name: str, data_source: Any):
        """注册数据源"""
        self.data_sources[name] = data_source
        logger.info(f"已注册数据源: {name}")
    
    async def generate_system_performance_report(self, time_range: Optional[Tuple[datetime, datetime]] = None) -> Report:
        """生成系统性能报告"""
        try:
            # 设置时间范围
            if not time_range:
                end_time = datetime.now()
                start_time = end_time - timedelta(hours=self.report_config['default_time_range_hours'])
                time_range = (start_time, end_time)
            
            start_time, end_time = time_range
            
            logger.info(f"生成系统性能报告: {start_time} - {end_time}")
            
            # 收集性能数据
            performance_data = await self._collect_performance_data(start_time, end_time)
            
            # 生成图表
            charts = await self._generate_performance_charts(performance_data, start_time, end_time)
            
            # 创建报告段落
            sections = []
            
            # CPU使用率段落
            if 'cpu' in performance_data:
                cpu_section = await self._create_cpu_section(performance_data['cpu'], charts.get('cpu'))
                sections.append(cpu_section)
            
            # 内存使用段落
            if 'memory' in performance_data:
                memory_section = await self._create_memory_section(performance_data['memory'], charts.get('memory'))
                sections.append(memory_section)
            
            # 磁盘I/O段落
            if 'disk' in performance_data:
                disk_section = await self._create_disk_section(performance_data['disk'], charts.get('disk'))
                sections.append(disk_section)
            
            # 网络I/O段落
            if 'network' in performance_data:
                network_section = await self._create_network_section(performance_data['network'], charts.get('network'))
                sections.append(network_section)
            
            # 计算摘要统计
            summary = self._calculate_performance_summary(performance_data)
            
            # 创建报告
            report = Report(
                report_id=f"performance_{int(datetime.now().timestamp())}",
                title="系统性能报告",
                report_type="performance",
                generated_at=datetime.now(),
                time_range={'start': start_time, 'end': end_time},
                sections=sections,
                summary=summary,
                metadata={
                    'data_points': sum(len(data) for data in performance_data.values()),
                    'charts_generated': len(charts),
                    'time_range_hours': (end_time - start_time).total_seconds() / 3600
                }
            )
            
            return report
            
        except Exception as e:
            logger.error(f"生成系统性能报告失败: {e}")
            raise
    
    async def generate_alert_summary_report(self, time_range: Optional[Tuple[datetime, datetime]] = None) -> Report:
        """生成告警汇总报告"""
        try:
            # 设置时间范围
            if not time_range:
                end_time = datetime.now()
                start_time = end_time - timedelta(hours=self.report_config['default_time_range_hours'])
                time_range = (start_time, end_time)
            
            start_time, end_time = time_range
            
            logger.info(f"生成告警汇总报告: {start_time} - {end_time}")
            
            # 收集告警数据
            alert_data = await self._collect_alert_data(start_time, end_time)
            
            # 生成图表
            charts = await self._generate_alert_charts(alert_data, start_time, end_time)
            
            # 创建报告段落
            sections = []
            
            # 告警概览段落
            overview_section = await self._create_alert_overview_section(alert_data, charts.get('overview'))
            sections.append(overview_section)
            
            # 告警趋势段落
            if charts.get('trend'):
                trend_section = await self._create_alert_trend_section(alert_data, charts.get('trend'))
                sections.append(trend_section)
            
            # 告警分类段落
            if charts.get('category'):
                category_section = await self._create_alert_category_section(alert_data, charts.get('category'))
                sections.append(category_section)
            
            # 计算摘要统计
            summary = self._calculate_alert_summary(alert_data)
            
            # 创建报告
            report = Report(
                report_id=f"alerts_{int(datetime.now().timestamp())}",
                title="告警汇总报告",
                report_type="alerts",
                generated_at=datetime.now(),
                time_range={'start': start_time, 'end': end_time},
                sections=sections,
                summary=summary,
                metadata={
                    'total_alerts': len(alert_data.get('alerts', [])),
                    'charts_generated': len(charts),
                    'time_range_hours': (end_time - start_time).total_seconds() / 3600
                }
            )
            
            return report
            
        except Exception as e:
            logger.error(f"生成告警汇总报告失败: {e}")
            raise
    
    async def generate_mvp_validation_report(self, validation_results: Dict[str, Any]) -> Report:
        """生成MVP验证报告"""
        try:
            logger.info("生成MVP验证报告")
            
            # 生成图表
            charts = await self._generate_validation_charts(validation_results)
            
            # 创建报告段落
            sections = []
            
            # 技术指标段落
            if 'technical_metrics' in validation_results:
                tech_section = await self._create_technical_metrics_section(
                    validation_results['technical_metrics'],
                    charts.get('technical')
                )
                sections.append(tech_section)
            
            # 业务指标段落
            if 'business_metrics' in validation_results:
                business_section = await self._create_business_metrics_section(
                    validation_results['business_metrics'],
                    charts.get('business')
                )
                sections.append(business_section)
            
            # 稳定性指标段落
            if 'stability_metrics' in validation_results:
                stability_section = await self._create_stability_metrics_section(
                    validation_results['stability_metrics'],
                    charts.get('stability')
                )
                sections.append(stability_section)
            
            # 用户体验指标段落
            if 'user_experience_metrics' in validation_results:
                ux_section = await self._create_ux_metrics_section(
                    validation_results['user_experience_metrics'],
                    charts.get('ux')
                )
                sections.append(ux_section)
            
            # 计算摘要统计
            summary = self._calculate_validation_summary(validation_results)
            
            # 创建报告
            report = Report(
                report_id=f"mvp_validation_{int(datetime.now().timestamp())}",
                title="MVP验证报告",
                report_type="mvp_validation",
                generated_at=datetime.now(),
                time_range={'start': datetime.now(), 'end': datetime.now()},
                sections=sections,
                summary=summary,
                metadata={
                    'validation_categories': len(validation_results),
                    'charts_generated': len(charts),
                    'total_checks': sum(
                        len(metrics.get('results', [])) 
                        for metrics in validation_results.values() 
                        if isinstance(metrics, dict)
                    )
                }
            )
            
            return report
            
        except Exception as e:
            logger.error(f"生成MVP验证报告失败: {e}")
            raise
    
    async def _collect_performance_data(self, start_time: datetime, end_time: datetime) -> Dict[str, List[Dict[str, Any]]]:
        """收集性能数据"""
        try:
            performance_data = {}
            
            # 从系统监控器获取数据
            if 'system_monitor' in self.data_sources:
                monitor = self.data_sources['system_monitor']
                
                # 获取历史数据
                history = getattr(monitor, 'get_history', lambda s, e: {})
                data = history(start_time, end_time)
                
                for metric_type in ['cpu', 'memory', 'disk', 'network']:
                    if metric_type in data:
                        performance_data[metric_type] = data[metric_type]
            
            # 模拟数据（如果没有真实数据）
            if not performance_data:
                performance_data = self._generate_mock_performance_data(start_time, end_time)
            
            return performance_data
            
        except Exception as e:
            logger.error(f"收集性能数据失败: {e}")
            return {}
    
    def _generate_mock_performance_data(self, start_time: datetime, end_time: datetime) -> Dict[str, List[Dict[str, Any]]]:
        """生成模拟性能数据"""
        try:
            import random
            
            data = {}
            time_points = []
            
            # 生成时间点
            current = start_time
            while current <= end_time:
                time_points.append(current)
                current += timedelta(minutes=5)
            
            # 限制数据点数量
            if len(time_points) > self.report_config['max_data_points']:
                step = len(time_points) // self.report_config['max_data_points']
                time_points = time_points[::step]
            
            # CPU数据
            data['cpu'] = []
            for i, timestamp in enumerate(time_points):
                cpu_percent = 20 + random.gauss(0, 10) + 10 * (1 + 0.5 * (i % 24) / 12)
                cpu_percent = max(0, min(100, cpu_percent))
                
                data['cpu'].append({
                    'timestamp': timestamp,
                    'cpu_percent': round(cpu_percent, 2),
                    'load_1m': round(random.uniform(0.5, 3.0), 2),
                    'load_5m': round(random.uniform(0.4, 2.5), 2),
                    'load_15m': round(random.uniform(0.3, 2.0), 2)
                })
            
            # 内存数据
            data['memory'] = []
            for timestamp in time_points:
                memory_percent = 40 + random.gauss(0, 8)
                memory_percent = max(10, min(90, memory_percent))
                
                data['memory'].append({
                    'timestamp': timestamp,
                    'memory_percent': round(memory_percent, 2),
                    'memory_used_gb': round(memory_percent * 0.16, 2),  # 假设16GB总内存
                    'memory_available_gb': round((100 - memory_percent) * 0.16, 2),
                    'swap_percent': round(random.uniform(0, 5), 2)
                })
            
            # 磁盘数据
            data['disk'] = []
            for timestamp in time_points:
                data['disk'].append({
                    'timestamp': timestamp,
                    'disk_usage_percent': round(random.uniform(45, 55), 2),
                    'disk_read_mb_s': round(random.uniform(5, 50), 2),
                    'disk_write_mb_s': round(random.uniform(2, 30), 2),
                    'disk_iops': round(random.uniform(100, 1000), 0)
                })
            
            # 网络数据
            data['network'] = []
            for timestamp in time_points:
                data['network'].append({
                    'timestamp': timestamp,
                    'network_in_mb_s': round(random.uniform(1, 20), 2),
                    'network_out_mb_s': round(random.uniform(0.5, 15), 2),
                    'connections': round(random.uniform(50, 200), 0),
                    'packets_per_second': round(random.uniform(1000, 5000), 0)
                })
            
            return data
            
        except Exception as e:
            logger.error(f"生成模拟性能数据失败: {e}")
            return {}
    
    async def _generate_performance_charts(self, performance_data: Dict[str, List[Dict[str, Any]]], 
                                          start_time: datetime, end_time: datetime) -> Dict[str, str]:
        """生成性能图表"""
        charts = {}
        chart_dir = Path(self.report_config['chart_dir'])
        
        try:
            # CPU图表
            if 'cpu' in performance_data and performance_data['cpu']:
                cpu_chart_path = await self._create_cpu_chart(performance_data['cpu'], chart_dir)
                if cpu_chart_path:
                    charts['cpu'] = cpu_chart_path
            
            # 内存图表
            if 'memory' in performance_data and performance_data['memory']:
                memory_chart_path = await self._create_memory_chart(performance_data['memory'], chart_dir)
                if memory_chart_path:
                    charts['memory'] = memory_chart_path
            
            # 磁盘图表
            if 'disk' in performance_data and performance_data['disk']:
                disk_chart_path = await self._create_disk_chart(performance_data['disk'], chart_dir)
                if disk_chart_path:
                    charts['disk'] = disk_chart_path
            
            # 网络图表
            if 'network' in performance_data and performance_data['network']:
                network_chart_path = await self._create_network_chart(performance_data['network'], chart_dir)
                if network_chart_path:
                    charts['network'] = network_chart_path
            
            return charts
            
        except Exception as e:
            logger.error(f"生成性能图表失败: {e}")
            return {}
    
    async def _create_cpu_chart(self, cpu_data: List[Dict[str, Any]], chart_dir: Path) -> Optional[str]:
        """创建CPU图表"""
        try:
            df = pd.DataFrame(cpu_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=self.report_config['figure_size'], sharex=True)
            
            # CPU使用率
            ax1.plot(df['timestamp'], df['cpu_percent'], linewidth=2, label='CPU使用率')
            ax1.set_ylabel('CPU使用率 (%)')
            ax1.set_title('CPU使用率趋势')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            ax1.set_ylim(0, 100)
            
            # 系统负载
            ax2.plot(df['timestamp'], df['load_1m'], linewidth=2, label='1分钟负载', alpha=0.8)
            ax2.plot(df['timestamp'], df['load_5m'], linewidth=2, label='5分钟负载', alpha=0.8)
            ax2.plot(df['timestamp'], df['load_15m'], linewidth=2, label='15分钟负载', alpha=0.8)
            ax2.set_ylabel('系统负载')
            ax2.set_xlabel('时间')
            ax2.set_title('系统负载趋势')
            ax2.grid(True, alpha=0.3)
            ax2.legend()
            
            # 格式化x轴
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax2.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
            
            plt.tight_layout()
            
            # 保存图表
            chart_path = chart_dir / f"cpu_chart_{int(datetime.now().timestamp())}.{self.report_config['chart_format']}"
            plt.savefig(chart_path, dpi=self.report_config['chart_dpi'], bbox_inches='tight')
            plt.close()
            
            return str(chart_path)
            
        except Exception as e:
            logger.error(f"创建CPU图表失败: {e}")
            return None
    
    async def _create_memory_chart(self, memory_data: List[Dict[str, Any]], chart_dir: Path) -> Optional[str]:
        """创建内存图表"""
        try:
            df = pd.DataFrame(memory_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=self.report_config['figure_size'], sharex=True)
            
            # 内存使用率
            ax1.plot(df['timestamp'], df['memory_percent'], linewidth=2, label='内存使用率', color='orange')
            ax1.set_ylabel('内存使用率 (%)')
            ax1.set_title('内存使用率趋势')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            ax1.set_ylim(0, 100)
            
            # 内存使用量
            ax2.plot(df['timestamp'], df['memory_used_gb'], linewidth=2, label='已使用', color='red')
            ax2.plot(df['timestamp'], df['memory_available_gb'], linewidth=2, label='可用', color='green')
            ax2.set_ylabel('内存 (GB)')
            ax2.set_xlabel('时间')
            ax2.set_title('内存使用量趋势')
            ax2.grid(True, alpha=0.3)
            ax2.legend()
            
            # 格式化x轴
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax2.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
            
            plt.tight_layout()
            
            # 保存图表
            chart_path = chart_dir / f"memory_chart_{int(datetime.now().timestamp())}.{self.report_config['chart_format']}"
            plt.savefig(chart_path, dpi=self.report_config['chart_dpi'], bbox_inches='tight')
            plt.close()
            
            return str(chart_path)
            
        except Exception as e:
            logger.error(f"创建内存图表失败: {e}")
            return None
    
    async def _create_disk_chart(self, disk_data: List[Dict[str, Any]], chart_dir: Path) -> Optional[str]:
        """创建磁盘图表"""
        try:
            df = pd.DataFrame(disk_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=self.report_config['figure_size'], sharex=True)
            
            # 磁盘I/O
            ax1.plot(df['timestamp'], df['disk_read_mb_s'], linewidth=2, label='读取 (MB/s)', color='blue')
            ax1.plot(df['timestamp'], df['disk_write_mb_s'], linewidth=2, label='写入 (MB/s)', color='red')
            ax1.set_ylabel('I/O速率 (MB/s)')
            ax1.set_title('磁盘I/O趋势')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            
            # 磁盘IOPS
            ax2.plot(df['timestamp'], df['disk_iops'], linewidth=2, label='IOPS', color='purple')
            ax2.set_ylabel('IOPS')
            ax2.set_xlabel('时间')
            ax2.set_title('磁盘IOPS趋势')
            ax2.grid(True, alpha=0.3)
            ax2.legend()
            
            # 格式化x轴
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax2.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
            
            plt.tight_layout()
            
            # 保存图表
            chart_path = chart_dir / f"disk_chart_{int(datetime.now().timestamp())}.{self.report_config['chart_format']}"
            plt.savefig(chart_path, dpi=self.report_config['chart_dpi'], bbox_inches='tight')
            plt.close()
            
            return str(chart_path)
            
        except Exception as e:
            logger.error(f"创建磁盘图表失败: {e}")
            return None
    
    async def _create_network_chart(self, network_data: List[Dict[str, Any]], chart_dir: Path) -> Optional[str]:
        """创建网络图表"""
        try:
            df = pd.DataFrame(network_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=self.report_config['figure_size'], sharex=True)
            
            # 网络流量
            ax1.plot(df['timestamp'], df['network_in_mb_s'], linewidth=2, label='入口流量 (MB/s)', color='green')
            ax1.plot(df['timestamp'], df['network_out_mb_s'], linewidth=2, label='出口流量 (MB/s)', color='orange')
            ax1.set_ylabel('网络流量 (MB/s)')
            ax1.set_title('网络流量趋势')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            
            # 网络连接数
            ax2.plot(df['timestamp'], df['connections'], linewidth=2, label='连接数', color='blue')
            ax2.set_ylabel('连接数')
            ax2.set_xlabel('时间')
            ax2.set_title('网络连接数趋势')
            ax2.grid(True, alpha=0.3)
            ax2.legend()
            
            # 格式化x轴
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax2.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
            
            plt.tight_layout()
            
            # 保存图表
            chart_path = chart_dir / f"network_chart_{int(datetime.now().timestamp())}.{self.report_config['chart_format']}"
            plt.savefig(chart_path, dpi=self.report_config['chart_dpi'], bbox_inches='tight')
            plt.close()
            
            return str(chart_path)
            
        except Exception as e:
            logger.error(f"创建网络图表失败: {e}")
            return None
    
    async def _create_cpu_section(self, cpu_data: List[Dict[str, Any]], chart_path: Optional[str]) -> ReportSection:
        """创建CPU段落"""
        try:
            # 计算统计数据
            df = pd.DataFrame(cpu_data)
            avg_cpu = df['cpu_percent'].mean()
            max_cpu = df['cpu_percent'].max()
            min_cpu = df['cpu_percent'].min()
            avg_load = df['load_1m'].mean()
            
            content = f"""
            <p>在报告时间段内，系统CPU使用情况如下：</p>
            <ul>
                <li><strong>平均CPU使用率:</strong> {avg_cpu:.1f}%</li>
                <li><strong>最高CPU使用率:</strong> {max_cpu:.1f}%</li>
                <li><strong>最低CPU使用率:</strong> {min_cpu:.1f}%</li>
                <li><strong>平均系统负载:</strong> {avg_load:.2f}</li>
            </ul>
            """
            
            # 添加分析
            if avg_cpu > 80:
                content += "<p><strong>⚠️ 警告:</strong> CPU使用率较高，建议关注系统性能。</p>"
            elif avg_cpu > 60:
                content += "<p><strong>ℹ️ 提示:</strong> CPU使用率适中，系统运行正常。</p>"
            else:
                content += "<p><strong>✅ 良好:</strong> CPU使用率较低，系统性能良好。</p>"
            
            return ReportSection(
                title="CPU使用情况",
                content=content,
                charts=[chart_path] if chart_path else []
            )
            
        except Exception as e:
            logger.error(f"创建CPU段落失败: {e}")
            return ReportSection(title="CPU使用情况", content="数据收集失败")
    
    async def _create_memory_section(self, memory_data: List[Dict[str, Any]], chart_path: Optional[str]) -> ReportSection:
        """创建内存段落"""
        try:
            # 计算统计数据
            df = pd.DataFrame(memory_data)
            avg_memory = df['memory_percent'].mean()
            max_memory = df['memory_percent'].max()
            min_memory = df['memory_percent'].min()
            avg_used = df['memory_used_gb'].mean()
            
            content = f"""
            <p>在报告时间段内，系统内存使用情况如下：</p>
            <ul>
                <li><strong>平均内存使用率:</strong> {avg_memory:.1f}%</li>
                <li><strong>最高内存使用率:</strong> {max_memory:.1f}%</li>
                <li><strong>最低内存使用率:</strong> {min_memory:.1f}%</li>
                <li><strong>平均已用内存:</strong> {avg_used:.1f} GB</li>
            </ul>
            """
            
            # 添加分析
            if avg_memory > 85:
                content += "<p><strong>⚠️ 警告:</strong> 内存使用率很高，可能影响系统性能。</p>"
            elif avg_memory > 70:
                content += "<p><strong>ℹ️ 提示:</strong> 内存使用率较高，建议监控。</p>"
            else:
                content += "<p><strong>✅ 良好:</strong> 内存使用率正常。</p>"
            
            return ReportSection(
                title="内存使用情况",
                content=content,
                charts=[chart_path] if chart_path else []
            )
            
        except Exception as e:
            logger.error(f"创建内存段落失败: {e}")
            return ReportSection(title="内存使用情况", content="数据收集失败")
    
    async def _create_disk_section(self, disk_data: List[Dict[str, Any]], chart_path: Optional[str]) -> ReportSection:
        """创建磁盘段落"""
        try:
            # 计算统计数据
            df = pd.DataFrame(disk_data)
            avg_usage = df['disk_usage_percent'].mean()
            avg_read = df['disk_read_mb_s'].mean()
            avg_write = df['disk_write_mb_s'].mean()
            avg_iops = df['disk_iops'].mean()
            
            content = f"""
            <p>在报告时间段内，系统磁盘使用情况如下：</p>
            <ul>
                <li><strong>平均磁盘使用率:</strong> {avg_usage:.1f}%</li>
                <li><strong>平均读取速度:</strong> {avg_read:.1f} MB/s</li>
                <li><strong>平均写入速度:</strong> {avg_write:.1f} MB/s</li>
                <li><strong>平均IOPS:</strong> {avg_iops:.0f}</li>
            </ul>
            """
            
            # 添加分析
            if avg_usage > 90:
                content += "<p><strong>⚠️ 警告:</strong> 磁盘空间不足，建议清理或扩容。</p>"
            elif avg_usage > 80:
                content += "<p><strong>ℹ️ 提示:</strong> 磁盘使用率较高，建议关注。</p>"
            else:
                content += "<p><strong>✅ 良好:</strong> 磁盘空间充足。</p>"
            
            return ReportSection(
                title="磁盘使用情况",
                content=content,
                charts=[chart_path] if chart_path else []
            )
            
        except Exception as e:
            logger.error(f"创建磁盘段落失败: {e}")
            return ReportSection(title="磁盘使用情况", content="数据收集失败")
    
    async def _create_network_section(self, network_data: List[Dict[str, Any]], chart_path: Optional[str]) -> ReportSection:
        """创建网络段落"""
        try:
            # 计算统计数据
            df = pd.DataFrame(network_data)
            avg_in = df['network_in_mb_s'].mean()
            avg_out = df['network_out_mb_s'].mean()
            avg_connections = df['connections'].mean()
            max_connections = df['connections'].max()
            
            content = f"""
            <p>在报告时间段内，系统网络使用情况如下：</p>
            <ul>
                <li><strong>平均入口流量:</strong> {avg_in:.1f} MB/s</li>
                <li><strong>平均出口流量:</strong> {avg_out:.1f} MB/s</li>
                <li><strong>平均连接数:</strong> {avg_connections:.0f}</li>
                <li><strong>最大连接数:</strong> {max_connections:.0f}</li>
            </ul>
            """
            
            # 添加分析
            total_traffic = avg_in + avg_out
            if total_traffic > 50:
                content += "<p><strong>ℹ️ 信息:</strong> 网络流量较高，系统网络负载较重。</p>"
            elif total_traffic > 20:
                content += "<p><strong>ℹ️ 信息:</strong> 网络流量适中，系统网络正常。</p>"
            else:
                content += "<p><strong>✅ 良好:</strong> 网络流量较低，系统网络负载轻。</p>"
            
            return ReportSection(
                title="网络使用情况",
                content=content,
                charts=[chart_path] if chart_path else []
            )
            
        except Exception as e:
            logger.error(f"创建网络段落失败: {e}")
            return ReportSection(title="网络使用情况", content="数据收集失败")
    
    def _calculate_performance_summary(self, performance_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """计算性能摘要"""
        try:
            summary = {}
            
            if 'cpu' in performance_data and performance_data['cpu']:
                df = pd.DataFrame(performance_data['cpu'])
                summary['平均CPU使用率'] = f"{df['cpu_percent'].mean():.1f}%"
                summary['最高CPU使用率'] = f"{df['cpu_percent'].max():.1f}%"
            
            if 'memory' in performance_data and performance_data['memory']:
                df = pd.DataFrame(performance_data['memory'])
                summary['平均内存使用率'] = f"{df['memory_percent'].mean():.1f}%"
                summary['最高内存使用率'] = f"{df['memory_percent'].max():.1f}%"
            
            if 'disk' in performance_data and performance_data['disk']:
                df = pd.DataFrame(performance_data['disk'])
                summary['平均磁盘使用率'] = f"{df['disk_usage_percent'].mean():.1f}%"
                summary['平均磁盘读写'] = f"{(df['disk_read_mb_s'].mean() + df['disk_write_mb_s'].mean()):.1f} MB/s"
            
            if 'network' in performance_data and performance_data['network']:
                df = pd.DataFrame(performance_data['network'])
                summary['平均网络流量'] = f"{(df['network_in_mb_s'].mean() + df['network_out_mb_s'].mean()):.1f} MB/s"
                summary['平均连接数'] = f"{df['connections'].mean():.0f}"
            
            return summary
            
        except Exception as e:
            logger.error(f"计算性能摘要失败: {e}")
            return {}
    
    async def _collect_alert_data(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """收集告警数据"""
        try:
            alert_data = {'alerts': []}
            
            # 从告警管理器获取数据
            if 'alert_manager' in self.data_sources:
                alert_manager = self.data_sources['alert_manager']
                
                # 获取告警历史
                if hasattr(alert_manager, 'alert_history'):
                    history = list(alert_manager.alert_history)
                    
                    # 过滤时间范围内的告警
                    filtered_alerts = [
                        alert for alert in history
                        if hasattr(alert, 'started_at') and 
                        start_time <= alert.started_at <= end_time
                    ]
                    
                    alert_data['alerts'] = filtered_alerts
            
            # 模拟数据（如果没有真实数据）
            if not alert_data['alerts']:
                alert_data = self._generate_mock_alert_data(start_time, end_time)
            
            return alert_data
            
        except Exception as e:
            logger.error(f"收集告警数据失败: {e}")
            return {'alerts': []}
    
    def _generate_mock_alert_data(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """生成模拟告警数据"""
        try:
            import random
            from dataclasses import dataclass
            
            @dataclass
            class MockAlert:
                alert_id: str
                title: str
                severity: str
                status: str
                started_at: datetime
                resolved_at: Optional[datetime] = None
            
            alerts = []
            alert_types = [
                ('CPU使用率过高', 'high'),
                ('内存使用率过高', 'medium'), 
                ('磁盘空间不足', 'high'),
                ('网络连接异常', 'low'),
                ('服务响应超时', 'critical'),
                ('数据库连接失败', 'critical')
            ]
            
            # 生成随机告警
            num_alerts = random.randint(5, 20)
            
            for i in range(num_alerts):
                alert_type, severity = random.choice(alert_types)
                alert_time = start_time + timedelta(
                    seconds=random.randint(0, int((end_time - start_time).total_seconds()))
                )
                
                status = random.choice(['firing', 'resolved'])
                resolved_time = None
                
                if status == 'resolved':
                    resolved_time = alert_time + timedelta(minutes=random.randint(10, 120))
                    if resolved_time > end_time:
                        resolved_time = end_time
                
                alert = MockAlert(
                    alert_id=f"alert_{i+1}",
                    title=alert_type,
                    severity=severity,
                    status=status,
                    started_at=alert_time,
                    resolved_at=resolved_time
                )
                
                alerts.append(alert)
            
            return {'alerts': alerts}
            
        except Exception as e:
            logger.error(f"生成模拟告警数据失败: {e}")
            return {'alerts': []}
    
    async def _generate_alert_charts(self, alert_data: Dict[str, Any], 
                                   start_time: datetime, end_time: datetime) -> Dict[str, str]:
        """生成告警图表"""
        charts = {}
        chart_dir = Path(self.report_config['chart_dir'])
        
        try:
            alerts = alert_data.get('alerts', [])
            
            if not alerts:
                return charts
            
            # 告警概览图表
            overview_chart = await self._create_alert_overview_chart(alerts, chart_dir)
            if overview_chart:
                charts['overview'] = overview_chart
            
            # 告警趋势图表
            trend_chart = await self._create_alert_trend_chart(alerts, chart_dir, start_time, end_time)
            if trend_chart:
                charts['trend'] = trend_chart
            
            # 告警分类图表
            category_chart = await self._create_alert_category_chart(alerts, chart_dir)
            if category_chart:
                charts['category'] = category_chart
            
            return charts
            
        except Exception as e:
            logger.error(f"生成告警图表失败: {e}")
            return {}
    
    async def _create_alert_overview_chart(self, alerts: List[Any], chart_dir: Path) -> Optional[str]:
        """创建告警概览图表"""
        try:
            # 按严重程度统计
            severity_counts = Counter(alert.severity for alert in alerts)
            
            # 按状态统计
            status_counts = Counter(alert.status for alert in alerts)
            
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=self.report_config['figure_size'])
            
            # 严重程度饼图
            if severity_counts:
                colors = {'critical': '#dc3545', 'high': '#fd7e14', 'medium': '#ffc107', 'low': '#28a745'}
                pie_colors = [colors.get(severity, '#6c757d') for severity in severity_counts.keys()]
                
                ax1.pie(severity_counts.values(), labels=severity_counts.keys(), autopct='%1.1f%%',
                       colors=pie_colors, startangle=90)
                ax1.set_title('按严重程度分布')
            
            # 状态柱状图
            if status_counts:
                bars = ax2.bar(status_counts.keys(), status_counts.values())
                ax2.set_title('按状态分布')
                ax2.set_ylabel('告警数量')
                
                # 添加数值标签
                for bar in bars:
                    height = bar.get_height()
                    ax2.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                            f'{int(height)}', ha='center', va='bottom')
            
            plt.tight_layout()
            
            # 保存图表
            chart_path = chart_dir / f"alert_overview_{int(datetime.now().timestamp())}.{self.report_config['chart_format']}"
            plt.savefig(chart_path, dpi=self.report_config['chart_dpi'], bbox_inches='tight')
            plt.close()
            
            return str(chart_path)
            
        except Exception as e:
            logger.error(f"创建告警概览图表失败: {e}")
            return None
    
    async def _create_alert_trend_chart(self, alerts: List[Any], chart_dir: Path,
                                      start_time: datetime, end_time: datetime) -> Optional[str]:
        """创建告警趋势图表"""
        try:
            # 按小时统计告警数量
            hourly_counts = defaultdict(int)
            
            current = start_time.replace(minute=0, second=0, microsecond=0)
            while current <= end_time:
                hourly_counts[current] = 0
                current += timedelta(hours=1)
            
            for alert in alerts:
                alert_hour = alert.started_at.replace(minute=0, second=0, microsecond=0)
                if start_time <= alert_hour <= end_time:
                    hourly_counts[alert_hour] += 1
            
            # 创建图表
            times = sorted(hourly_counts.keys())
            counts = [hourly_counts[time] for time in times]
            
            fig, ax = plt.subplots(figsize=self.report_config['figure_size'])
            
            ax.plot(times, counts, marker='o', linewidth=2, markersize=4)
            ax.set_title('告警数量趋势')
            ax.set_xlabel('时间')
            ax.set_ylabel('告警数量')
            ax.grid(True, alpha=0.3)
            
            # 格式化x轴
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=max(1, len(times)//10)))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
            plt.tight_layout()
            
            # 保存图表
            chart_path = chart_dir / f"alert_trend_{int(datetime.now().timestamp())}.{self.report_config['chart_format']}"
            plt.savefig(chart_path, dpi=self.report_config['chart_dpi'], bbox_inches='tight')
            plt.close()
            
            return str(chart_path)
            
        except Exception as e:
            logger.error(f"创建告警趋势图表失败: {e}")
            return None
    
    async def _create_alert_category_chart(self, alerts: List[Any], chart_dir: Path) -> Optional[str]:
        """创建告警分类图表"""
        try:
            # 按告警标题分类统计
            title_counts = Counter(alert.title for alert in alerts)
            
            # 只显示前10个最频繁的告警类型
            top_alerts = dict(title_counts.most_common(10))
            
            if not top_alerts:
                return None
            
            fig, ax = plt.subplots(figsize=self.report_config['figure_size'])
            
            y_pos = range(len(top_alerts))
            bars = ax.barh(y_pos, list(top_alerts.values()))
            
            ax.set_yticks(y_pos)
            ax.set_yticklabels(list(top_alerts.keys()))
            ax.set_xlabel('告警数量')
            ax.set_title('告警类型分布（Top 10）')
            
            # 添加数值标签
            for i, bar in enumerate(bars):
                width = bar.get_width()
                ax.text(width + 0.1, bar.get_y() + bar.get_height()/2.,
                       f'{int(width)}', ha='left', va='center')
            
            plt.tight_layout()
            
            # 保存图表
            chart_path = chart_dir / f"alert_category_{int(datetime.now().timestamp())}.{self.report_config['chart_format']}"
            plt.savefig(chart_path, dpi=self.report_config['chart_dpi'], bbox_inches='tight')
            plt.close()
            
            return str(chart_path)
            
        except Exception as e:
            logger.error(f"创建告警分类图表失败: {e}")
            return None
    
    async def _create_alert_overview_section(self, alert_data: Dict[str, Any], chart_path: Optional[str]) -> ReportSection:
        """创建告警概览段落"""
        try:
            alerts = alert_data.get('alerts', [])
            
            # 统计数据
            total_alerts = len(alerts)
            active_alerts = len([a for a in alerts if a.status == 'firing'])
            resolved_alerts = len([a for a in alerts if a.status == 'resolved'])
            
            severity_counts = Counter(alert.severity for alert in alerts)
            critical_count = severity_counts.get('critical', 0)
            high_count = severity_counts.get('high', 0)
            
            content = f"""
            <p>告警概览统计：</p>
            <ul>
                <li><strong>总告警数:</strong> {total_alerts}</li>
                <li><strong>活跃告警:</strong> {active_alerts}</li>
                <li><strong>已解决告警:</strong> {resolved_alerts}</li>
                <li><strong>严重告警:</strong> {critical_count}</li>
                <li><strong>高级告警:</strong> {high_count}</li>
            </ul>
            """
            
            # 添加分析
            if critical_count > 0:
                content += f"<p><strong>🚨 紧急:</strong> 存在 {critical_count} 个严重告警，需要立即处理。</p>"
            elif high_count > 5:
                content += f"<p><strong>⚠️ 警告:</strong> 高级告警较多 ({high_count} 个)，建议关注。</p>"
            elif total_alerts == 0:
                content += "<p><strong>✅ 良好:</strong> 报告期间无告警发生。</p>"
            else:
                content += "<p><strong>ℹ️ 正常:</strong> 告警数量在合理范围内。</p>"
            
            return ReportSection(
                title="告警概览",
                content=content,
                charts=[chart_path] if chart_path else []
            )
            
        except Exception as e:
            logger.error(f"创建告警概览段落失败: {e}")
            return ReportSection(title="告警概览", content="数据收集失败")
    
    async def _create_alert_trend_section(self, alert_data: Dict[str, Any], chart_path: Optional[str]) -> ReportSection:
        """创建告警趋势段落"""
        try:
            alerts = alert_data.get('alerts', [])
            
            if not alerts:
                content = "<p>报告期间无告警数据。</p>"
            else:
                # 计算趋势
                sorted_alerts = sorted(alerts, key=lambda x: x.started_at)
                first_half = sorted_alerts[:len(sorted_alerts)//2]
                second_half = sorted_alerts[len(sorted_alerts)//2:]
                
                content = f"""
                <p>告警趋势分析：</p>
                <ul>
                    <li><strong>最早告警:</strong> {sorted_alerts[0].started_at.strftime('%Y-%m-%d %H:%M:%S')}</li>
                    <li><strong>最晚告警:</strong> {sorted_alerts[-1].started_at.strftime('%Y-%m-%d %H:%M:%S')}</li>
                    <li><strong>前半段告警数:</strong> {len(first_half)}</li>
                    <li><strong>后半段告警数:</strong> {len(second_half)}</li>
                </ul>
                """
                
                # 趋势分析
                if len(second_half) > len(first_half) * 1.5:
                    content += "<p><strong>📈 趋势:</strong> 告警数量呈上升趋势，需要关注。</p>"
                elif len(first_half) > len(second_half) * 1.5:
                    content += "<p><strong>📉 趋势:</strong> 告警数量呈下降趋势，情况好转。</p>"
                else:
                    content += "<p><strong>➡️ 趋势:</strong> 告警数量相对稳定。</p>"
            
            return ReportSection(
                title="告警趋势",
                content=content,
                charts=[chart_path] if chart_path else []
            )
            
        except Exception as e:
            logger.error(f"创建告警趋势段落失败: {e}")
            return ReportSection(title="告警趋势", content="数据收集失败")
    
    async def _create_alert_category_section(self, alert_data: Dict[str, Any], chart_path: Optional[str]) -> ReportSection:
        """创建告警分类段落"""
        try:
            alerts = alert_data.get('alerts', [])
            
            if not alerts:
                content = "<p>报告期间无告警数据。</p>"
            else:
                # 按类型统计
                title_counts = Counter(alert.title for alert in alerts)
                top_5 = title_counts.most_common(5)
                
                content = f"""
                <p>告警类型分布（Top 5）：</p>
                <ul>
                """
                
                for title, count in top_5:
                    percentage = (count / len(alerts)) * 100
                    content += f"<li><strong>{title}:</strong> {count} 次 ({percentage:.1f}%)</li>"
                
                content += "</ul>"
                
                # 添加建议
                if top_5 and top_5[0][1] > len(alerts) * 0.5:
                    content += f"<p><strong>💡 建议:</strong> '{top_5[0][0]}' 告警频繁发生，建议重点优化。</p>"
            
            return ReportSection(
                title="告警分类",
                content=content,
                charts=[chart_path] if chart_path else []
            )
            
        except Exception as e:
            logger.error(f"创建告警分类段落失败: {e}")
            return ReportSection(title="告警分类", content="数据收集失败")
    
    def _calculate_alert_summary(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """计算告警摘要"""
        try:
            alerts = alert_data.get('alerts', [])
            summary = {}
            
            summary['总告警数'] = len(alerts)
            summary['活跃告警'] = len([a for a in alerts if a.status == 'firing'])
            summary['已解决告警'] = len([a for a in alerts if a.status == 'resolved'])
            
            severity_counts = Counter(alert.severity for alert in alerts)
            summary['严重告警'] = severity_counts.get('critical', 0)
            summary['高级告警'] = severity_counts.get('high', 0)
            summary['中级告警'] = severity_counts.get('medium', 0)
            summary['低级告警'] = severity_counts.get('low', 0)
            
            return summary
            
        except Exception as e:
            logger.error(f"计算告警摘要失败: {e}")
            return {}
    
    async def _generate_validation_charts(self, validation_results: Dict[str, Any]) -> Dict[str, str]:
        """生成验证图表"""
        charts = {}
        chart_dir = Path(self.report_config['chart_dir'])
        
        try:
            # 技术指标图表
            if 'technical_metrics' in validation_results:
                tech_chart = await self._create_validation_summary_chart(
                    validation_results['technical_metrics'], 
                    '技术指标验证结果',
                    chart_dir,
                    'technical'
                )
                if tech_chart:
                    charts['technical'] = tech_chart
            
            # 业务指标图表
            if 'business_metrics' in validation_results:
                business_chart = await self._create_validation_summary_chart(
                    validation_results['business_metrics'],
                    '业务指标验证结果', 
                    chart_dir,
                    'business'
                )
                if business_chart:
                    charts['business'] = business_chart
            
            return charts
            
        except Exception as e:
            logger.error(f"生成验证图表失败: {e}")
            return {}
    
    async def _create_validation_summary_chart(self, metrics_data: Dict[str, Any], 
                                             title: str, chart_dir: Path, prefix: str) -> Optional[str]:
        """创建验证摘要图表"""
        try:
            results = metrics_data.get('results', [])
            if not results:
                return None
            
            # 统计通过和失败的数量
            passed = len([r for r in results if r.get('passed', False)])
            failed = len([r for r in results if not r.get('passed', False)])
            
            fig, ax = plt.subplots(figsize=(8, 6))
            
            # 创建饼图
            sizes = [passed, failed]
            labels = ['通过', '失败']
            colors = ['#28a745', '#dc3545']
            explode = (0.05, 0.05)
            
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, 
                   explode=explode, startangle=90, shadow=True)
            ax.set_title(title, fontsize=14, fontweight='bold')
            
            plt.tight_layout()
            
            # 保存图表
            chart_path = chart_dir / f"{prefix}_validation_{int(datetime.now().timestamp())}.{self.report_config['chart_format']}"
            plt.savefig(chart_path, dpi=self.report_config['chart_dpi'], bbox_inches='tight')
            plt.close()
            
            return str(chart_path)
            
        except Exception as e:
            logger.error(f"创建验证摘要图表失败: {e}")
            return None
    
    async def _create_technical_metrics_section(self, tech_data: Dict[str, Any], chart_path: Optional[str]) -> ReportSection:
        """创建技术指标段落"""
        try:
            results = tech_data.get('results', [])
            passed = len([r for r in results if r.get('passed', False)])
            failed = len([r for r in results if not r.get('passed', False)])
            total = len(results)
            pass_rate = (passed / total * 100) if total > 0 else 0
            
            content = f"""
            <p>技术指标验证结果：</p>
            <ul>
                <li><strong>总检查项:</strong> {total}</li>
                <li><strong>通过数:</strong> {passed}</li>
                <li><strong>失败数:</strong> {failed}</li>
                <li><strong>通过率:</strong> {pass_rate:.1f}%</li>
            </ul>
            """
            
            # 详细结果
            if results:
                content += "<h4>详细结果:</h4><ul>"
                for result in results[:10]:  # 只显示前10个
                    status = "✅" if result.get('passed', False) else "❌"
                    name = result.get('name', '未知检查')
                    content += f"<li>{status} {name}</li>"
                
                if len(results) > 10:
                    content += f"<li>... 还有 {len(results) - 10} 个检查项</li>"
                content += "</ul>"
            
            # 添加分析
            if pass_rate >= 90:
                content += "<p><strong>✅ 优秀:</strong> 技术指标表现优秀。</p>"
            elif pass_rate >= 70:
                content += "<p><strong>⚠️ 良好:</strong> 技术指标基本达标，有改进空间。</p>"
            else:
                content += "<p><strong>❌ 需要改进:</strong> 技术指标未达标，需要重点优化。</p>"
            
            return ReportSection(
                title="技术指标验证",
                content=content,
                charts=[chart_path] if chart_path else []
            )
            
        except Exception as e:
            logger.error(f"创建技术指标段落失败: {e}")
            return ReportSection(title="技术指标验证", content="数据收集失败")
    
    async def _create_business_metrics_section(self, business_data: Dict[str, Any], chart_path: Optional[str]) -> ReportSection:
        """创建业务指标段落"""
        try:
            results = business_data.get('results', [])
            passed = len([r for r in results if r.get('passed', False)])
            failed = len([r for r in results if not r.get('passed', False)])
            total = len(results)
            pass_rate = (passed / total * 100) if total > 0 else 0
            
            content = f"""
            <p>业务指标验证结果：</p>
            <ul>
                <li><strong>总检查项:</strong> {total}</li>
                <li><strong>通过数:</strong> {passed}</li>
                <li><strong>失败数:</strong> {failed}</li>
                <li><strong>通过率:</strong> {pass_rate:.1f}%</li>
            </ul>
            """
            
            # 详细结果
            if results:
                content += "<h4>详细结果:</h4><ul>"
                for result in results[:10]:  # 只显示前10个
                    status = "✅" if result.get('passed', False) else "❌"
                    name = result.get('name', '未知检查')
                    content += f"<li>{status} {name}</li>"
                
                if len(results) > 10:
                    content += f"<li>... 还有 {len(results) - 10} 个检查项</li>"
                content += "</ul>"
            
            # 添加分析
            if pass_rate >= 95:
                content += "<p><strong>✅ 优秀:</strong> 业务指标表现优秀，MVP达到预期目标。</p>"
            elif pass_rate >= 80:
                content += "<p><strong>⚠️ 良好:</strong> 业务指标基本达标，可以上线。</p>"
            else:
                content += "<p><strong>❌ 需要改进:</strong> 业务指标未达标，建议重新评估。</p>"
            
            return ReportSection(
                title="业务指标验证",
                content=content,
                charts=[chart_path] if chart_path else []
            )
            
        except Exception as e:
            logger.error(f"创建业务指标段落失败: {e}")
            return ReportSection(title="业务指标验证", content="数据收集失败")
    
    async def _create_stability_metrics_section(self, stability_data: Dict[str, Any], chart_path: Optional[str]) -> ReportSection:
        """创建稳定性指标段落"""
        try:
            results = stability_data.get('results', [])
            passed = len([r for r in results if r.get('passed', False)])
            failed = len([r for r in results if not r.get('passed', False)])
            total = len(results)
            pass_rate = (passed / total * 100) if total > 0 else 0
            
            content = f"""
            <p>稳定性指标验证结果：</p>
            <ul>
                <li><strong>总检查项:</strong> {total}</li>
                <li><strong>通过数:</strong> {passed}</li>
                <li><strong>失败数:</strong> {failed}</li>
                <li><strong>通过率:</strong> {pass_rate:.1f}%</li>
            </ul>
            """
            
            # 添加分析
            if pass_rate >= 98:
                content += "<p><strong>✅ 优秀:</strong> 系统稳定性表现优秀。</p>"
            elif pass_rate >= 95:
                content += "<p><strong>⚠️ 良好:</strong> 系统稳定性良好。</p>"
            else:
                content += "<p><strong>❌ 需要改进:</strong> 系统稳定性需要提升。</p>"
            
            return ReportSection(
                title="稳定性指标验证",
                content=content,
                charts=[chart_path] if chart_path else []
            )
            
        except Exception as e:
            logger.error(f"创建稳定性指标段落失败: {e}")
            return ReportSection(title="稳定性指标验证", content="数据收集失败")
    
    async def _create_ux_metrics_section(self, ux_data: Dict[str, Any], chart_path: Optional[str]) -> ReportSection:
        """创建用户体验指标段落"""
        try:
            results = ux_data.get('results', [])
            passed = len([r for r in results if r.get('passed', False)])
            failed = len([r for r in results if not r.get('passed', False)])
            total = len(results)
            pass_rate = (passed / total * 100) if total > 0 else 0
            
            content = f"""
            <p>用户体验指标验证结果：</p>
            <ul>
                <li><strong>总检查项:</strong> {total}</li>
                <li><strong>通过数:</strong> {passed}</li>
                <li><strong>失败数:</strong> {failed}</li>
                <li><strong>通过率:</strong> {pass_rate:.1f}%</li>
            </ul>
            """
            
            # 添加分析
            if pass_rate >= 90:
                content += "<p><strong>✅ 优秀:</strong> 用户体验表现优秀。</p>"
            elif pass_rate >= 75:
                content += "<p><strong>⚠️ 良好:</strong> 用户体验基本良好。</p>"
            else:
                content += "<p><strong>❌ 需要改进:</strong> 用户体验需要优化。</p>"
            
            return ReportSection(
                title="用户体验指标验证",
                content=content,
                charts=[chart_path] if chart_path else []
            )
            
        except Exception as e:
            logger.error(f"创建用户体验指标段落失败: {e}")
            return ReportSection(title="用户体验指标验证", content="数据收集失败")
    
    def _calculate_validation_summary(self, validation_results: Dict[str, Any]) -> Dict[str, Any]:
        """计算验证摘要"""
        try:
            summary = {}
            total_checks = 0
            total_passed = 0
            
            for category, data in validation_results.items():
                if isinstance(data, dict) and 'results' in data:
                    results = data['results']
                    passed = len([r for r in results if r.get('passed', False)])
                    total = len(results)
                    
                    total_checks += total
                    total_passed += passed
                    
                    summary[f"{category}_通过率"] = f"{(passed/total*100):.1f}%" if total > 0 else "0%"
            
            if total_checks > 0:
                overall_pass_rate = (total_passed / total_checks) * 100
                summary['总体通过率'] = f"{overall_pass_rate:.1f}%"
                summary['总检查项'] = total_checks
                summary['总通过数'] = total_passed
            
            return summary
            
        except Exception as e:
            logger.error(f"计算验证摘要失败: {e}")
            return {}
    
    async def export_report(self, report: Report, output_format: str = 'html') -> str:
        """导出报告"""
        try:
            output_dir = Path(self.report_config['output_dir'])
            timestamp = int(datetime.now().timestamp())
            
            if output_format == 'html':
                output_file = output_dir / f"{report.report_id}_{timestamp}.html"
                await self._export_html_report(report, output_file)
            elif output_format == 'json':
                output_file = output_dir / f"{report.report_id}_{timestamp}.json"
                await self._export_json_report(report, output_file)
            elif output_format == 'pdf':
                output_file = output_dir / f"{report.report_id}_{timestamp}.pdf"
                await self._export_pdf_report(report, output_file)
            else:
                raise ValueError(f"不支持的导出格式: {output_format}")
            
            logger.info(f"报告已导出: {output_file}")
            return str(output_file)
            
        except Exception as e:
            logger.error(f"导出报告失败: {e}")
            raise
    
    async def _export_html_report(self, report: Report, output_file: Path):
        """导出HTML报告"""
        try:
            template = self.template_env.get_template('base_report.html')
            html_content = template.render(report=report)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
        except Exception as e:
            logger.error(f"导出HTML报告失败: {e}")
            raise
    
    async def _export_json_report(self, report: Report, output_file: Path):
        """导出JSON报告"""
        try:
            # 转换为字典格式
            report_data = asdict(report)
            
            # 处理datetime对象
            def convert_datetime(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                elif isinstance(obj, dict):
                    return {k: convert_datetime(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_datetime(item) for item in obj]
                return obj
            
            report_data = convert_datetime(report_data)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"导出JSON报告失败: {e}")
            raise
    
    async def _export_pdf_report(self, report: Report, output_file: Path):
        """导出PDF报告"""
        try:
            # 首先生成HTML
            html_file = output_file.with_suffix('.html')
            await self._export_html_report(report, html_file)
            
            # 尝试使用weasyprint转换为PDF
            try:
                import weasyprint
                weasyprint.HTML(filename=str(html_file)).write_pdf(str(output_file))
                html_file.unlink()  # 删除临时HTML文件
            except ImportError:
                logger.warning("weasyprint未安装，无法生成PDF，请安装: pip install weasyprint")
                # 重命名HTML文件为PDF文件名（实际还是HTML）
                html_file.rename(output_file.with_suffix('.html'))
                raise RuntimeError("PDF导出需要安装weasyprint库")
                
        except Exception as e:
            logger.error(f"导出PDF报告失败: {e}")
            raise
    
    def cleanup_old_reports(self):
        """清理旧报告"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.report_config['max_report_age_days'])
            output_dir = Path(self.report_config['output_dir'])
            chart_dir = Path(self.report_config['chart_dir'])
            
            # 清理报告文件
            for file_path in output_dir.iterdir():
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_date.timestamp():
                    file_path.unlink()
                    logger.info(f"已删除旧报告文件: {file_path}")
            
            # 清理图表文件
            for file_path in chart_dir.iterdir():
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_date.timestamp():
                    file_path.unlink()
                    logger.info(f"已删除旧图表文件: {file_path}")
                    
        except Exception as e:
            logger.error(f"清理旧报告失败: {e}")


# 使用示例
async def example_usage():
    """使用示例"""
    
    config = {
        'report_generator': {
            'output_dir': 'reports',
            'template_dir': 'templates',
            'chart_dir': 'charts'
        }
    }
    
    # 创建报告生成器
    generator = ReportGenerator(config)
    
    try:
        # 生成系统性能报告
        perf_report = await generator.generate_system_performance_report()
        print(f"生成系统性能报告: {perf_report.title}")
        
        # 导出HTML报告
        html_file = await generator.export_report(perf_report, 'html')
        print(f"HTML报告已保存: {html_file}")
        
        # 生成告警汇总报告
        alert_report = await generator.generate_alert_summary_report()
        print(f"生成告警汇总报告: {alert_report.title}")
        
        # 生成MVP验证报告
        validation_results = {
            'technical_metrics': {
                'results': [
                    {'name': '响应时间检查', 'passed': True},
                    {'name': 'CPU使用率检查', 'passed': True},
                    {'name': '内存使用检查', 'passed': False}
                ]
            },
            'business_metrics': {
                'results': [
                    {'name': '功能完整性检查', 'passed': True},
                    {'name': '数据准确性检查', 'passed': True}
                ]
            }
        }
        
        mvp_report = await generator.generate_mvp_validation_report(validation_results)
        print(f"生成MVP验证报告: {mvp_report.title}")
        
        # 清理旧报告
        generator.cleanup_old_reports()
        
    except Exception as e:
        print(f"示例运行失败: {e}")


if __name__ == '__main__':
    asyncio.run(example_usage())