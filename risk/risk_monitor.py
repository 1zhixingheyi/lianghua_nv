"""
风控监控模块
============

实现全面的风控监控和告警功能，包括：
- 实时风险指标监控
- 风险等级评估和分类
- 自动告警和通知机制
- 风控事件统计和分析
- 风控报告生成
- 监控仪表板数据
"""

import logging
import pandas as pd
import numpy as np
import threading
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque

from .risk_config import RiskConfig, RiskEvent, RiskEventType, RiskLevel
from .base_risk import BaseRiskManager, RiskCheckResult, RiskCheckStatus
from .position_manager import PositionManager
from .money_manager import MoneyManager

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """告警类型"""
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    LOG = "log"
    CONSOLE = "console"


class MonitorStatus(Enum):
    """监控状态"""
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class RiskMetric:
    """风险指标"""
    name: str
    value: float
    threshold: float
    risk_level: RiskLevel
    timestamp: datetime
    unit: str = ""
    description: str = ""
    
    @property
    def is_breached(self) -> bool:
        """是否突破阈值"""
        return self.value > self.threshold
    
    @property
    def breach_ratio(self) -> float:
        """突破比例"""
        if self.threshold == 0:
            return 0.0
        return (self.value - self.threshold) / self.threshold


@dataclass
class RiskAlert:
    """风控告警"""
    alert_id: str
    alert_type: AlertType
    risk_level: RiskLevel
    title: str
    message: str
    source: str
    timestamp: datetime
    acknowledged: bool = False
    resolved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def acknowledge(self):
        """确认告警"""
        self.acknowledged = True
        logger.info(f"告警已确认: {self.alert_id}")
    
    def resolve(self):
        """解决告警"""
        self.resolved = True
        logger.info(f"告警已解决: {self.alert_id}")


@dataclass
class MonitoringSummary:
    """监控摘要"""
    timestamp: datetime
    total_alerts: int
    critical_alerts: int
    high_alerts: int
    medium_alerts: int
    low_alerts: int
    active_monitors: int
    risk_score: float
    overall_status: str


class RiskMonitor:
    """风控监控器"""
    
    def __init__(self, risk_config: RiskConfig, base_risk_manager: BaseRiskManager,
                 position_manager: Optional[PositionManager] = None,
                 money_manager: Optional[MoneyManager] = None):
        """
        初始化风控监控器

        Args:
            risk_config: 风控配置
            base_risk_manager: 基础风控管理器
            position_manager: 仓位管理器
            money_manager: 资金管理器
        """
        self.risk_config = risk_config
        self.base_risk_manager = base_risk_manager
        self.position_manager = position_manager
        self.money_manager = money_manager
        
        # 监控状态
        self.status = MonitorStatus.STOPPED
        self.last_check_time: Optional[datetime] = None
        
        # 风险指标
        self.risk_metrics: Dict[str, RiskMetric] = {}
        self.metric_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # 告警管理
        self.alerts: Dict[str, RiskAlert] = {}
        self.alert_counter = 0
        self.alert_handlers: Dict[AlertType, List[Callable]] = defaultdict(list)
        
        # 监控线程
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # 统计数据
        self.monitoring_stats = {
            'total_checks': 0,
            'total_alerts': 0,
            'uptime_start': datetime.now(),
            'last_error': None
        }
        
        # 自定义监控规则
        self.custom_monitors: Dict[str, Callable] = {}
        
        # 初始化默认告警处理器
        self._initialize_alert_handlers()
        
        logger.info("风控监控器初始化完成")
    
    def _initialize_alert_handlers(self):
        """初始化默认告警处理器"""
        # 日志告警处理器
        def log_alert_handler(alert: RiskAlert):
            level = {
                RiskLevel.LOW: logging.INFO,
                RiskLevel.MEDIUM: logging.WARNING,
                RiskLevel.HIGH: logging.ERROR,
                RiskLevel.CRITICAL: logging.CRITICAL
            }.get(alert.risk_level, logging.WARNING)
            
            logger.log(level, f"风控告警: [{alert.risk_level.value.upper()}] {alert.title} - {alert.message}")
        
        # 控制台告警处理器
        def console_alert_handler(alert: RiskAlert):
            print(f"[{alert.timestamp.strftime('%H:%M:%S')}] 风控告警: {alert.title}")
            print(f"级别: {alert.risk_level.value.upper()}")
            print(f"消息: {alert.message}")
            print("-" * 50)
        
        self.add_alert_handler(AlertType.LOG, log_alert_handler)
        self.add_alert_handler(AlertType.CONSOLE, console_alert_handler)
    
    def add_alert_handler(self, alert_type: AlertType, handler: Callable[[RiskAlert], None]):
        """添加告警处理器"""
        self.alert_handlers[alert_type].append(handler)
        logger.info(f"已添加 {alert_type.value} 告警处理器")
    
    def start_monitoring(self, check_interval: Optional[int] = None):
        """开始监控"""
        if self.status == MonitorStatus.RUNNING:
            logger.warning("监控已在运行中")
            return
        
        if check_interval is None:
            check_interval = self.risk_config.monitoring_config.check_frequency_seconds
        
        self.status = MonitorStatus.RUNNING
        self.stop_event.clear()
        
        # 启动监控线程
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(check_interval,),
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.info(f"风控监控已启动，检查间隔: {check_interval}秒")
    
    def stop_monitoring(self):
        """停止监控"""
        if self.status != MonitorStatus.RUNNING:
            logger.warning("监控未在运行")
            return
        
        self.status = MonitorStatus.STOPPED
        self.stop_event.set()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        logger.info("风控监控已停止")
    
    def _monitoring_loop(self, check_interval: int):
        """监控主循环"""
        while not self.stop_event.is_set():
            try:
                if self.status == MonitorStatus.RUNNING:
                    self._perform_risk_check()
                    self.monitoring_stats['total_checks'] += 1
                
                # 等待下次检查
                self.stop_event.wait(check_interval)
                
            except Exception as e:
                logger.error(f"监控循环出错: {str(e)}")
                self.monitoring_stats['last_error'] = str(e)
                self.status = MonitorStatus.ERROR
                time.sleep(check_interval)  # 出错后仍然等待
    
    def _perform_risk_check(self):
        """执行风控检查"""
        self.last_check_time = datetime.now()
        
        try:
            # 检查仓位风险
            if self.position_manager:
                self._check_position_risks()
            
            # 检查资金风险
            if self.money_manager:
                self._check_capital_risks()
            
            # 更新风险指标
            self._update_risk_metrics()
            
            # 清理过期告警
            self._cleanup_old_alerts()
            
        except Exception as e:
            logger.error(f"风控检查失败: {str(e)}")
            self._create_alert(
                AlertType.LOG,
                RiskLevel.HIGH,
                "监控系统错误",
                f"风控检查执行失败: {str(e)}",
                "monitor_system"
            )
    
    def _check_position_risks(self):
        """检查仓位风险"""
        if not self.position_manager:
            return
        
        # 检查总仓位比例
        total_position_ratio = self.position_manager.get_total_position_ratio()
        max_position_ratio = self.risk_config.position_limits.max_total_position_ratio
        
        if total_position_ratio > max_position_ratio:
            self._create_alert(
                AlertType.LOG,
                RiskLevel.HIGH,
                "总仓位超限",
                f"当前仓位比例 {total_position_ratio:.2%} 超过限制 {max_position_ratio:.2%}",
                "position_manager"
            )
        
        # 检查行业集中度
        sector_result = self.position_manager.check_sector_concentration()
        if sector_result.violations:
            for violation in sector_result.violations:
                self._create_alert(
                    AlertType.LOG,
                    violation.risk_level,
                    "行业集中度告警",
                    violation.message,
                    "position_manager"
                )
    
    def _check_capital_risks(self):
        """检查资金风险"""
        if not self.money_manager:
            return
        
        # 检查现金限制
        cash_result = self.money_manager.check_cash_limits()
        if cash_result.violations:
            for violation in cash_result.violations:
                self._create_alert(
                    AlertType.LOG,
                    violation.risk_level,
                    "资金风险告警",
                    violation.message,
                    "money_manager"
                )
    
    def _update_risk_metrics(self):
        """更新风险指标"""
        current_time = datetime.now()
        
        # 基础指标
        if self.position_manager:
            # 仓位相关指标
            total_position_ratio = self.position_manager.get_total_position_ratio()
            self._update_metric("total_position_ratio", total_position_ratio, 
                              self.risk_config.position_limits.max_total_position_ratio,
                              RiskLevel.HIGH, current_time, "%", "总仓位比例")
            
            # 持仓数量
            position_count = self.position_manager.get_position_count()
            self._update_metric("position_count", position_count,
                              self.risk_config.position_limits.max_individual_stocks,
                              RiskLevel.MEDIUM, current_time, "只", "持仓数量")
        
        if self.money_manager:
            # 资金相关指标
            cash_ratio = self.money_manager.get_cash_ratio()
            self._update_metric("cash_ratio", cash_ratio,
                              self.risk_config.capital_limits.min_cash_ratio,
                              RiskLevel.MEDIUM, current_time, "%", "现金比例")
        
        # 风险评分
        risk_score = self._calculate_overall_risk_score()
        self._update_metric("overall_risk_score", risk_score, 50.0,
                          RiskLevel.HIGH, current_time, "分", "综合风险评分")
    
    def _update_metric(self, name: str, value: float, threshold: float, 
                      risk_level: RiskLevel, timestamp: datetime, 
                      unit: str = "", description: str = ""):
        """更新风险指标"""
        metric = RiskMetric(
            name=name,
            value=value,
            threshold=threshold,
            risk_level=risk_level,
            timestamp=timestamp,
            unit=unit,
            description=description
        )
        
        self.risk_metrics[name] = metric
        self.metric_history[name].append((timestamp, value))
    
    def _calculate_overall_risk_score(self) -> float:
        """计算综合风险评分"""
        score = 0.0
        
        # 基于违规数量和严重程度计算
        recent_events = self.risk_config.get_recent_events(1)  # 最近1小时
        
        for event in recent_events:
            if event.risk_level == RiskLevel.CRITICAL:
                score += 20
            elif event.risk_level == RiskLevel.HIGH:
                score += 10
            elif event.risk_level == RiskLevel.MEDIUM:
                score += 5
            elif event.risk_level == RiskLevel.LOW:
                score += 1
        
        return min(score, 100.0)  # 最大100分
    
    def _create_alert(self, alert_type: AlertType, risk_level: RiskLevel,
                     title: str, message: str, source: str, **metadata):
        """创建告警"""
        self.alert_counter += 1
        alert_id = f"alert_{self.alert_counter:06d}"
        
        alert = RiskAlert(
            alert_id=alert_id,
            alert_type=alert_type,
            risk_level=risk_level,
            title=title,
            message=message,
            source=source,
            timestamp=datetime.now(),
            metadata=metadata
        )
        
        self.alerts[alert_id] = alert
        self.monitoring_stats['total_alerts'] += 1
        
        # 发送告警
        self._send_alert(alert)
        
        return alert_id
    
    def _send_alert(self, alert: RiskAlert):
        """发送告警"""
        if not self.risk_config.monitoring_config.alert_enabled:
            return
        
        # 调用相应的告警处理器
        handlers = self.alert_handlers.get(alert.alert_type, [])
        for handler in handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"告警处理器执行失败: {str(e)}")
    
    def _cleanup_old_alerts(self):
        """清理旧告警"""
        week_ago = datetime.now() - timedelta(days=7)
        old_alert_ids = [
            alert_id for alert_id, alert in self.alerts.items()
            if alert.timestamp < week_ago
        ]
        
        for alert_id in old_alert_ids:
            del self.alerts[alert_id]
        
        if old_alert_ids:
            logger.info(f"已清理 {len(old_alert_ids)} 个过期告警")
    
    def get_active_alerts(self, risk_level: Optional[RiskLevel] = None) -> List[RiskAlert]:
        """获取活跃告警"""
        alerts = [alert for alert in self.alerts.values() if not alert.resolved]
        
        if risk_level:
            alerts = [alert for alert in alerts if alert.risk_level == risk_level]
        
        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)
    
    def get_alert_statistics(self, hours: int = 24) -> Dict[str, int]:
        """获取告警统计"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_alerts = [
            alert for alert in self.alerts.values()
            if alert.timestamp >= cutoff_time
        ]
        
        stats = {
            'total': len(recent_alerts),
            'critical': len([a for a in recent_alerts if a.risk_level == RiskLevel.CRITICAL]),
            'high': len([a for a in recent_alerts if a.risk_level == RiskLevel.HIGH]),
            'medium': len([a for a in recent_alerts if a.risk_level == RiskLevel.MEDIUM]),
            'low': len([a for a in recent_alerts if a.risk_level == RiskLevel.LOW]),
            'acknowledged': len([a for a in recent_alerts if a.acknowledged]),
            'resolved': len([a for a in recent_alerts if a.resolved])
        }
        
        return stats
    
    def get_risk_metrics_summary(self) -> Dict[str, Any]:
        """获取风险指标摘要"""
        summary = {}
        
        for name, metric in self.risk_metrics.items():
            summary[name] = {
                'current_value': metric.value,
                'threshold': metric.threshold,
                'is_breached': metric.is_breached,
                'breach_ratio': metric.breach_ratio,
                'risk_level': metric.risk_level.value,
                'unit': metric.unit,
                'description': metric.description,
                'last_update': metric.timestamp.isoformat()
            }
        
        return summary
    
    def generate_risk_report(self, report_type: str = "daily") -> Dict[str, Any]:
        """生成风控报告"""
        if report_type == "daily":
            hours = 24
        elif report_type == "weekly":
            hours = 168
        elif report_type == "monthly":
            hours = 720
        else:
            hours = 24
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # 风险事件统计
        risk_events = self.risk_config.get_recent_events(hours)
        event_stats = defaultdict(int)
        for event in risk_events:
            event_stats[event.risk_level.value] += 1
        
        # 告警统计
        alert_stats = self.get_alert_statistics(hours)
        
        # 生成报告
        report = {
            'report_type': report_type,
            'report_period': f"{hours} hours",
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_risk_events': len(risk_events),
                'total_alerts': alert_stats['total'],
                'critical_issues': event_stats['critical'] + alert_stats['critical'],
                'overall_risk_score': self.risk_metrics.get('overall_risk_score', {}).value if hasattr(self.risk_metrics.get('overall_risk_score', {}), 'value') else 0
            },
            'risk_events': {
                'by_level': dict(event_stats),
                'by_type': defaultdict(int)
            },
            'alerts': alert_stats,
            'recommendations': self._generate_recommendations()
        }
        
        # 按事件类型统计
        for event in risk_events:
            report['risk_events']['by_type'][event.event_type.value] += 1
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        # 基于告警频率的建议
        recent_alerts = self.get_active_alerts()
        if len(recent_alerts) > 10:
            recommendations.append("告警数量较多，建议检查风控配置是否过于严格")
        
        # 基于风险指标的建议
        for name, metric in self.risk_metrics.items():
            if metric.is_breached:
                recommendations.append(f"风险指标 {metric.description} 超标，建议采取相应措施")
        
        if not recommendations:
            recommendations.append("风控系统运行正常")
        
        return recommendations
    
    def get_monitoring_dashboard_data(self) -> Dict[str, Any]:
        """获取监控仪表板数据"""
        current_time = datetime.now()
        uptime = current_time - self.monitoring_stats['uptime_start']
        
        return {
            'monitor_status': self.status.value,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'uptime_seconds': uptime.total_seconds(),
            'total_checks': self.monitoring_stats['total_checks'],
            'total_alerts': self.monitoring_stats['total_alerts'],
            'risk_metrics': self.get_risk_metrics_summary(),
            'alert_statistics': self.get_alert_statistics(),
            'active_alerts': len(self.get_active_alerts()),
            'overall_risk_score': self.risk_metrics.get('overall_risk_score', {}).value if hasattr(self.risk_metrics.get('overall_risk_score', {}), 'value') else 0
        }