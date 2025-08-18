"""
监控和诊断模块

提供系统监控、诊断分析、告警管理和报告生成功能
"""

from .system_monitor import SystemMonitor, MetricPoint, SystemMetrics, ApplicationMetrics
from .diagnostic_analyzer import DiagnosticAnalyzer, DiagnosticResult, PerformanceAnomaly
from .alert_manager import AlertManager, Alert, AlertRule, NotificationChannel
from .report_generator import ReportGenerator, Report, ReportSection

__all__ = [
    # 系统监控
    'SystemMonitor',
    'MetricPoint',
    'SystemMetrics',
    'ApplicationMetrics',
    
    # 诊断分析
    'DiagnosticAnalyzer',
    'DiagnosticResult',
    'PerformanceAnomaly',
    
    # 告警管理
    'AlertManager',
    'Alert',
    'AlertRule', 
    'NotificationChannel',
    
    # 报告生成
    'ReportGenerator',
    'Report',
    'ReportSection'
]

# 版本信息
__version__ = '1.0.0'
__author__ = 'MVP验证与优化体系'
__description__ = '监控和诊断模块 - 提供系统监控、诊断分析、告警管理和报告生成功能'