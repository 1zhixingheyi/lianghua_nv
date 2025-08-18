"""
告警管理器

处理告警规则、发送通知和管理告警状态
"""

import asyncio
import logging
import json
import smtplib
import requests
from typing import Dict, Any, List, Optional, Callable, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import defaultdict, deque
import hashlib
import os

logger = logging.getLogger(__name__)


@dataclass
class AlertRule:
    """告警规则"""
    rule_id: str
    name: str
    description: str
    metric_name: str
    condition: str  # >, <, >=, <=, ==, !=
    threshold: float
    severity: str  # critical, high, medium, low
    duration_minutes: int  # 持续时间
    enabled: bool = True
    labels: Dict[str, str] = None
    
    def __post_init__(self):
        if self.labels is None:
            self.labels = {}


@dataclass
class Alert:
    """告警实例"""
    alert_id: str
    rule_id: str
    title: str
    description: str
    severity: str
    status: str  # firing, resolved, suppressed
    metric_name: str
    current_value: float
    threshold: float
    started_at: datetime
    resolved_at: Optional[datetime] = None
    labels: Dict[str, str] = None
    annotations: Dict[str, str] = None
    
    def __post_init__(self):
        if self.labels is None:
            self.labels = {}
        if self.annotations is None:
            self.annotations = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        data['started_at'] = self.started_at.isoformat()
        if self.resolved_at:
            data['resolved_at'] = self.resolved_at.isoformat()
        return data


@dataclass
class NotificationChannel:
    """通知渠道"""
    channel_id: str
    name: str
    type: str  # email, webhook, slack, dingtalk
    config: Dict[str, Any]
    enabled: bool = True
    severity_filter: List[str] = None  # 只发送指定严重程度的告警
    
    def __post_init__(self):
        if self.severity_filter is None:
            self.severity_filter = ['critical', 'high', 'medium', 'low']


class AlertManager:
    """告警管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 告警配置
        self.alert_config = {
            'evaluation_interval': 60,  # 评估间隔（秒）
            'alert_retention_hours': 168,  # 告警保留时间（7天）
            'max_alerts_per_rule': 1000,  # 每个规则最大告警数
            'enable_alert_grouping': True,  # 启用告警分组
            'grouping_window_minutes': 5,  # 分组窗口时间
            'inhibit_rules': [],  # 抑制规则
            'default_channels': ['default_email'],  # 默认通知渠道
            'alert_webhook_timeout': 30,  # Webhook超时时间
            'email_rate_limit': 10,  # 邮件发送频率限制（每分钟）
            'storage': {
                'type': 'file',  # file, database, memory
                'file_path': 'alerts.json'
            }
        }
        
        # 更新配置
        if 'alert_manager' in config:
            self.alert_config.update(config['alert_manager'])
        
        # 告警状态
        self.alert_rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=10000)
        self.notification_channels: Dict[str, NotificationChannel] = {}
        
        # 评估状态
        self.rule_states: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.alert_groups: Dict[str, List[Alert]] = defaultdict(list)
        
        # 任务控制
        self.is_running = False
        self.evaluation_task = None
        
        # 通知限制
        self.notification_counters: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # 初始化默认通知渠道
        self._setup_default_channels()
        
        # 加载告警数据
        self._load_alert_data()
    
    def _setup_default_channels(self):
        """设置默认通知渠道"""
        try:
            # 默认邮件渠道
            if 'email' in self.config:
                email_config = self.config['email']
                self.notification_channels['default_email'] = NotificationChannel(
                    channel_id='default_email',
                    name='默认邮件通知',
                    type='email',
                    config=email_config,
                    enabled=email_config.get('enabled', False)
                )
            
            # 默认Webhook渠道
            if 'webhook' in self.config:
                webhook_config = self.config['webhook']
                self.notification_channels['default_webhook'] = NotificationChannel(
                    channel_id='default_webhook',
                    name='默认Webhook通知',
                    type='webhook',
                    config=webhook_config,
                    enabled=webhook_config.get('enabled', False)
                )
        
        except Exception as e:
            logger.error(f"设置默认通知渠道失败: {e}")
    
    def _load_alert_data(self):
        """加载告警数据"""
        try:
            storage_config = self.alert_config['storage']
            
            if storage_config['type'] == 'file':
                file_path = storage_config['file_path']
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 加载告警规则
                    if 'rules' in data:
                        for rule_data in data['rules']:
                            rule = AlertRule(**rule_data)
                            self.alert_rules[rule.rule_id] = rule
                    
                    # 加载活跃告警
                    if 'active_alerts' in data:
                        for alert_data in data['active_alerts']:
                            alert_data['started_at'] = datetime.fromisoformat(alert_data['started_at'])
                            if alert_data.get('resolved_at'):
                                alert_data['resolved_at'] = datetime.fromisoformat(alert_data['resolved_at'])
                            alert = Alert(**alert_data)
                            self.active_alerts[alert.alert_id] = alert
                    
                    logger.info(f"已加载 {len(self.alert_rules)} 个告警规则和 {len(self.active_alerts)} 个活跃告警")
                    
        except Exception as e:
            logger.error(f"加载告警数据失败: {e}")
    
    def _save_alert_data(self):
        """保存告警数据"""
        try:
            storage_config = self.alert_config['storage']
            
            if storage_config['type'] == 'file':
                # 确保目录存在
                file_path = storage_config['file_path']
                os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else '.', exist_ok=True)
                
                data = {
                    'saved_at': datetime.now().isoformat(),
                    'rules': [asdict(rule) for rule in self.alert_rules.values()],
                    'active_alerts': [alert.to_dict() for alert in self.active_alerts.values()]
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    
        except Exception as e:
            logger.error(f"保存告警数据失败: {e}")
    
    async def start(self):
        """启动告警管理器"""
        if self.is_running:
            logger.warning("告警管理器已经在运行")
            return
        
        logger.info("启动告警管理器")
        
        self.is_running = True
        
        # 启动评估任务
        self.evaluation_task = asyncio.create_task(self._evaluation_loop())
        
        logger.info("告警管理器已启动")
    
    async def stop(self):
        """停止告警管理器"""
        if not self.is_running:
            logger.warning("告警管理器未在运行")
            return
        
        logger.info("停止告警管理器")
        
        self.is_running = False
        
        # 停止评估任务
        if self.evaluation_task:
            self.evaluation_task.cancel()
            try:
                await self.evaluation_task
            except asyncio.CancelledError:
                pass
        
        # 保存告警数据
        self._save_alert_data()
        
        logger.info("告警管理器已停止")
    
    async def _evaluation_loop(self):
        """评估循环"""
        while self.is_running:
            try:
                start_time = asyncio.get_event_loop().time()
                
                # 清理过期告警
                await self._cleanup_expired_alerts()
                
                # 处理告警分组
                if self.alert_config['enable_alert_grouping']:
                    await self._process_alert_groups()
                
                # 定期保存数据
                self._save_alert_data()
                
                # 计算实际耗时并调整睡眠时间
                elapsed = asyncio.get_event_loop().time() - start_time
                sleep_time = max(0, self.alert_config['evaluation_interval'] - elapsed)
                
                await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"告警评估循环异常: {e}")
                await asyncio.sleep(30)
    
    def add_alert_rule(self, rule: AlertRule):
        """添加告警规则"""
        try:
            self.alert_rules[rule.rule_id] = rule
            logger.info(f"已添加告警规则: {rule.name}")
        except Exception as e:
            logger.error(f"添加告警规则失败: {e}")
    
    def remove_alert_rule(self, rule_id: str):
        """删除告警规则"""
        try:
            if rule_id in self.alert_rules:
                del self.alert_rules[rule_id]
                # 删除相关的活跃告警
                alerts_to_remove = [
                    alert_id for alert_id, alert in self.active_alerts.items()
                    if alert.rule_id == rule_id
                ]
                for alert_id in alerts_to_remove:
                    del self.active_alerts[alert_id]
                logger.info(f"已删除告警规则: {rule_id}")
            else:
                logger.warning(f"告警规则不存在: {rule_id}")
        except Exception as e:
            logger.error(f"删除告警规则失败: {e}")
    
    def add_notification_channel(self, channel: NotificationChannel):
        """添加通知渠道"""
        try:
            self.notification_channels[channel.channel_id] = channel
            logger.info(f"已添加通知渠道: {channel.name}")
        except Exception as e:
            logger.error(f"添加通知渠道失败: {e}")
    
    def remove_notification_channel(self, channel_id: str):
        """删除通知渠道"""
        try:
            if channel_id in self.notification_channels:
                del self.notification_channels[channel_id]
                logger.info(f"已删除通知渠道: {channel_id}")
            else:
                logger.warning(f"通知渠道不存在: {channel_id}")
        except Exception as e:
            logger.error(f"删除通知渠道失败: {e}")
    
    async def evaluate_metric(self, metric_name: str, value: float, timestamp: datetime = None):
        """评估指标并触发告警"""
        if timestamp is None:
            timestamp = datetime.now()
        
        try:
            # 查找适用的告警规则
            applicable_rules = [
                rule for rule in self.alert_rules.values()
                if rule.enabled and rule.metric_name == metric_name
            ]
            
            for rule in applicable_rules:
                await self._evaluate_rule(rule, value, timestamp)
                
        except Exception as e:
            logger.error(f"评估指标告警失败: {e}")
    
    async def _evaluate_rule(self, rule: AlertRule, value: float, timestamp: datetime):
        """评估单个告警规则"""
        try:
            # 检查条件是否满足
            condition_met = self._check_condition(rule.condition, value, rule.threshold)
            
            # 获取规则状态
            rule_state = self.rule_states[rule.rule_id]
            
            if condition_met:
                # 条件满足
                if 'first_breach_time' not in rule_state:
                    rule_state['first_breach_time'] = timestamp
                    rule_state['consecutive_breaches'] = 1
                else:
                    rule_state['consecutive_breaches'] = rule_state.get('consecutive_breaches', 0) + 1
                
                # 检查是否需要触发告警
                breach_duration = timestamp - rule_state['first_breach_time']
                if breach_duration.total_seconds() >= rule.duration_minutes * 60:
                    await self._fire_alert(rule, value, timestamp)
            else:
                # 条件不满足，检查是否需要解决告警
                if 'first_breach_time' in rule_state:
                    del rule_state['first_breach_time']
                    rule_state['consecutive_breaches'] = 0
                
                await self._resolve_alerts_for_rule(rule.rule_id, timestamp)
                
        except Exception as e:
            logger.error(f"评估告警规则失败 {rule.rule_id}: {e}")
    
    def _check_condition(self, condition: str, value: float, threshold: float) -> bool:
        """检查条件是否满足"""
        try:
            if condition == '>':
                return value > threshold
            elif condition == '<':
                return value < threshold
            elif condition == '>=':
                return value >= threshold
            elif condition == '<=':
                return value <= threshold
            elif condition == '==':
                return value == threshold
            elif condition == '!=':
                return value != threshold
            else:
                logger.warning(f"不支持的条件: {condition}")
                return False
        except Exception as e:
            logger.error(f"检查条件失败: {e}")
            return False
    
    async def _fire_alert(self, rule: AlertRule, value: float, timestamp: datetime):
        """触发告警"""
        try:
            # 生成告警ID
            alert_id = self._generate_alert_id(rule, timestamp)
            
            # 检查是否已存在相同的活跃告警
            if alert_id in self.active_alerts:
                # 更新现有告警
                existing_alert = self.active_alerts[alert_id]
                existing_alert.current_value = value
                existing_alert.annotations['last_updated'] = timestamp.isoformat()
                return
            
            # 创建新告警
            alert = Alert(
                alert_id=alert_id,
                rule_id=rule.rule_id,
                title=f"{rule.name}",
                description=f"{rule.description} - 当前值: {value}, 阈值: {rule.threshold}",
                severity=rule.severity,
                status='firing',
                metric_name=rule.metric_name,
                current_value=value,
                threshold=rule.threshold,
                started_at=timestamp,
                labels=rule.labels.copy(),
                annotations={
                    'rule_name': rule.name,
                    'condition': f"{rule.metric_name} {rule.condition} {rule.threshold}",
                    'duration': f"{rule.duration_minutes}m"
                }
            )
            
            # 添加到活跃告警
            self.active_alerts[alert_id] = alert
            self.alert_history.append(alert)
            
            # 发送通知
            await self._send_alert_notifications(alert)
            
            logger.info(f"触发告警: {alert.title} (ID: {alert_id})")
            
        except Exception as e:
            logger.error(f"触发告警失败: {e}")
    
    async def _resolve_alerts_for_rule(self, rule_id: str, timestamp: datetime):
        """解决指定规则的所有告警"""
        try:
            alerts_to_resolve = [
                alert for alert in self.active_alerts.values()
                if alert.rule_id == rule_id and alert.status == 'firing'
            ]
            
            for alert in alerts_to_resolve:
                await self._resolve_alert(alert.alert_id, timestamp)
                
        except Exception as e:
            logger.error(f"解决告警失败: {e}")
    
    async def _resolve_alert(self, alert_id: str, timestamp: datetime):
        """解决告警"""
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.status = 'resolved'
                alert.resolved_at = timestamp
                
                # 从活跃告警中移除
                del self.active_alerts[alert_id]
                
                # 发送解决通知
                await self._send_alert_notifications(alert)
                
                logger.info(f"解决告警: {alert.title} (ID: {alert_id})")
                
        except Exception as e:
            logger.error(f"解决告警失败: {e}")
    
    def _generate_alert_id(self, rule: AlertRule, timestamp: datetime) -> str:
        """生成告警ID"""
        # 使用规则ID和标签生成唯一ID
        content = f"{rule.rule_id}_{json.dumps(rule.labels, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    async def _send_alert_notifications(self, alert: Alert):
        """发送告警通知"""
        try:
            # 确定要使用的通知渠道
            channels_to_use = self.alert_config['default_channels'].copy()
            
            # 根据告警标签添加特定渠道
            if 'notification_channels' in alert.labels:
                additional_channels = alert.labels['notification_channels'].split(',')
                channels_to_use.extend(additional_channels)
            
            # 发送通知
            for channel_id in channels_to_use:
                if channel_id in self.notification_channels:
                    channel = self.notification_channels[channel_id]
                    
                    # 检查渠道是否启用
                    if not channel.enabled:
                        continue
                    
                    # 检查严重程度过滤
                    if alert.severity not in channel.severity_filter:
                        continue
                    
                    # 检查频率限制
                    if not self._check_rate_limit(channel_id):
                        logger.warning(f"通知渠道 {channel_id} 达到频率限制")
                        continue
                    
                    # 发送通知
                    await self._send_notification(channel, alert)
                    
        except Exception as e:
            logger.error(f"发送告警通知失败: {e}")
    
    def _check_rate_limit(self, channel_id: str) -> bool:
        """检查通知频率限制"""
        try:
            now = datetime.now()
            counter = self.notification_counters[channel_id]
            
            # 清理过期计数
            cutoff_time = now - timedelta(minutes=1)
            while counter and counter[0] < cutoff_time:
                counter.popleft()
            
            # 检查是否超过限制
            if len(counter) >= self.alert_config['email_rate_limit']:
                return False
            
            # 添加当前时间
            counter.append(now)
            return True
            
        except Exception as e:
            logger.error(f"检查频率限制失败: {e}")
            return True
    
    async def _send_notification(self, channel: NotificationChannel, alert: Alert):
        """发送单个通知"""
        try:
            if channel.type == 'email':
                await self._send_email_notification(channel, alert)
            elif channel.type == 'webhook':
                await self._send_webhook_notification(channel, alert)
            elif channel.type == 'slack':
                await self._send_slack_notification(channel, alert)
            elif channel.type == 'dingtalk':
                await self._send_dingtalk_notification(channel, alert)
            else:
                logger.warning(f"不支持的通知类型: {channel.type}")
                
        except Exception as e:
            logger.error(f"发送 {channel.type} 通知失败: {e}")
    
    async def _send_email_notification(self, channel: NotificationChannel, alert: Alert):
        """发送邮件通知"""
        try:
            config = channel.config
            
            # 创建邮件内容
            subject = f"[{alert.severity.upper()}] {alert.title}"
            
            body = f"""
告警详情:
- 标题: {alert.title}
- 严重程度: {alert.severity}
- 状态: {alert.status}
- 指标: {alert.metric_name}
- 当前值: {alert.current_value}
- 阈值: {alert.threshold}
- 开始时间: {alert.started_at.strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            if alert.resolved_at:
                body += f"- 解决时间: {alert.resolved_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            body += f"\n描述: {alert.description}\n"
            
            if alert.labels:
                body += f"\n标签: {json.dumps(alert.labels, indent=2)}\n"
            
            # 发送邮件
            await self._send_email(
                smtp_host=config['smtp_host'],
                smtp_port=config['smtp_port'],
                username=config['username'],
                password=config['password'],
                from_addr=config['from_addr'],
                to_addrs=config['to_addrs'],
                subject=subject,
                body=body,
                use_tls=config.get('use_tls', True)
            )
            
            logger.info(f"已发送邮件通知: {alert.title}")
            
        except Exception as e:
            logger.error(f"发送邮件通知失败: {e}")
    
    async def _send_email(self, smtp_host: str, smtp_port: int, username: str, 
                         password: str, from_addr: str, to_addrs: List[str],
                         subject: str, body: str, use_tls: bool = True):
        """发送邮件"""
        def send_sync():
            try:
                msg = MIMEMultipart()
                msg['From'] = from_addr
                msg['To'] = ', '.join(to_addrs)
                msg['Subject'] = subject
                
                msg.attach(MIMEText(body, 'plain', 'utf-8'))
                
                if use_tls:
                    server = smtplib.SMTP(smtp_host, smtp_port)
                    server.starttls()
                else:
                    server = smtplib.SMTP_SSL(smtp_host, smtp_port)
                
                server.login(username, password)
                server.send_message(msg)
                server.quit()
                
            except Exception as e:
                logger.error(f"SMTP发送失败: {e}")
                raise
        
        # 在线程池中执行同步邮件发送
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, send_sync)
    
    async def _send_webhook_notification(self, channel: NotificationChannel, alert: Alert):
        """发送Webhook通知"""
        try:
            config = channel.config
            
            # 准备Webhook数据
            webhook_data = {
                'alert_id': alert.alert_id,
                'title': alert.title,
                'description': alert.description,
                'severity': alert.severity,
                'status': alert.status,
                'metric_name': alert.metric_name,
                'current_value': alert.current_value,
                'threshold': alert.threshold,
                'started_at': alert.started_at.isoformat(),
                'resolved_at': alert.resolved_at.isoformat() if alert.resolved_at else None,
                'labels': alert.labels,
                'annotations': alert.annotations
            }
            
            # 发送HTTP请求
            timeout = self.alert_config['alert_webhook_timeout']
            
            def send_webhook():
                headers = {'Content-Type': 'application/json'}
                if 'headers' in config:
                    headers.update(config['headers'])
                
                response = requests.post(
                    config['url'],
                    json=webhook_data,
                    headers=headers,
                    timeout=timeout
                )
                response.raise_for_status()
                return response
            
            # 在线程池中执行
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, send_webhook)
            
            logger.info(f"已发送Webhook通知: {alert.title}, 响应码: {response.status_code}")
            
        except Exception as e:
            logger.error(f"发送Webhook通知失败: {e}")
    
    async def _send_slack_notification(self, channel: NotificationChannel, alert: Alert):
        """发送Slack通知"""
        try:
            config = channel.config
            
            # 准备Slack消息
            color = {
                'critical': 'danger',
                'high': 'warning',
                'medium': 'warning',
                'low': 'good'
            }.get(alert.severity, 'warning')
            
            status_emoji = {
                'firing': '🔥',
                'resolved': '✅',
                'suppressed': '🔇'
            }.get(alert.status, '❓')
            
            slack_data = {
                'text': f"{status_emoji} {alert.title}",
                'attachments': [
                    {
                        'color': color,
                        'fields': [
                            {'title': '严重程度', 'value': alert.severity, 'short': True},
                            {'title': '状态', 'value': alert.status, 'short': True},
                            {'title': '指标', 'value': alert.metric_name, 'short': True},
                            {'title': '当前值', 'value': str(alert.current_value), 'short': True},
                            {'title': '阈值', 'value': str(alert.threshold), 'short': True},
                            {'title': '开始时间', 'value': alert.started_at.strftime('%Y-%m-%d %H:%M:%S'), 'short': True}
                        ],
                        'footer': 'Alert Manager',
                        'ts': int(alert.started_at.timestamp())
                    }
                ]
            }
            
            if alert.resolved_at:
                slack_data['attachments'][0]['fields'].append({
                    'title': '解决时间',
                    'value': alert.resolved_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'short': True
                })
            
            # 发送请求
            def send_slack():
                response = requests.post(
                    config['webhook_url'],
                    json=slack_data,
                    timeout=self.alert_config['alert_webhook_timeout']
                )
                response.raise_for_status()
                return response
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, send_slack)
            
            logger.info(f"已发送Slack通知: {alert.title}")
            
        except Exception as e:
            logger.error(f"发送Slack通知失败: {e}")
    
    async def _send_dingtalk_notification(self, channel: NotificationChannel, alert: Alert):
        """发送钉钉通知"""
        try:
            config = channel.config
            
            # 准备钉钉消息
            status_emoji = {
                'firing': '🔥',
                'resolved': '✅',
                'suppressed': '🔇'
            }.get(alert.status, '❓')
            
            text = f"{status_emoji} {alert.title}\n\n"
            text += f"**严重程度**: {alert.severity}\n"
            text += f"**状态**: {alert.status}\n"
            text += f"**指标**: {alert.metric_name}\n"
            text += f"**当前值**: {alert.current_value}\n"
            text += f"**阈值**: {alert.threshold}\n"
            text += f"**开始时间**: {alert.started_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            if alert.resolved_at:
                text += f"**解决时间**: {alert.resolved_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            text += f"\n**描述**: {alert.description}"
            
            dingtalk_data = {
                'msgtype': 'markdown',
                'markdown': {
                    'title': alert.title,
                    'text': text
                }
            }
            
            # 发送请求
            def send_dingtalk():
                response = requests.post(
                    config['webhook_url'],
                    json=dingtalk_data,
                    timeout=self.alert_config['alert_webhook_timeout']
                )
                response.raise_for_status()
                return response
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, send_dingtalk)
            
            logger.info(f"已发送钉钉通知: {alert.title}")
            
        except Exception as e:
            logger.error(f"发送钉钉通知失败: {e}")
    
    async def _cleanup_expired_alerts(self):
        """清理过期告警"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=self.alert_config['alert_retention_hours'])
            
            # 清理历史告警
            while (self.alert_history and 
                   hasattr(self.alert_history[0], 'started_at') and
                   self.alert_history[0].started_at < cutoff_time):
                self.alert_history.popleft()
            
            # 清理已解决的活跃告警
            resolved_alerts = [
                alert_id for alert_id, alert in self.active_alerts.items()
                if alert.status == 'resolved' and alert.resolved_at and alert.resolved_at < cutoff_time
            ]
            
            for alert_id in resolved_alerts:
                del self.active_alerts[alert_id]
            
            if resolved_alerts:
                logger.info(f"清理了 {len(resolved_alerts)} 个过期的已解决告警")
                
        except Exception as e:
            logger.error(f"清理过期告警失败: {e}")
    
    async def _process_alert_groups(self):
        """处理告警分组"""
        try:
            # 简单的分组策略：按严重程度和时间窗口分组
            now = datetime.now()
            window_minutes = self.alert_config['grouping_window_minutes']
            
            # 清理过期分组
            for group_key in list(self.alert_groups.keys()):
                group_alerts = self.alert_groups[group_key]
                # 移除超出时间窗口的告警
                group_alerts[:] = [
                    alert for alert in group_alerts
                    if (now - alert.started_at).total_seconds() < window_minutes * 60
                ]
                
                # 如果分组为空，删除
                if not group_alerts:
                    del self.alert_groups[group_key]
            
        except Exception as e:
            logger.error(f"处理告警分组失败: {e}")
    
    def get_active_alerts(self, severity_filter: List[str] = None) -> List[Alert]:
        """获取活跃告警"""
        try:
            alerts = list(self.active_alerts.values())
            
            if severity_filter:
                alerts = [alert for alert in alerts if alert.severity in severity_filter]
            
            # 按严重程度和时间排序
            severity_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
            alerts.sort(
                key=lambda x: (severity_order.get(x.severity, 0), x.started_at),
                reverse=True
            )
            
            return alerts
            
        except Exception as e:
            logger.error(f"获取活跃告警失败: {e}")
            return []
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """获取告警统计"""
        try:
            from collections import Counter
            
            active_alerts = list(self.active_alerts.values())
            
            stats = {
                'total_rules': len(self.alert_rules),
                'enabled_rules': len([r for r in self.alert_rules.values() if r.enabled]),
                'active_alerts': len(active_alerts),
                'alerts_by_severity': dict(Counter(alert.severity for alert in active_alerts)),
                'alerts_by_status': dict(Counter(alert.status for alert in active_alerts)),
                'notification_channels': len(self.notification_channels),
                'enabled_channels': len([c for c in self.notification_channels.values() if c.enabled]),
                'alert_history_size': len(self.alert_history)
            }
            
            # 最近24小时告警统计
            last_24h = datetime.now() - timedelta(hours=24)
            recent_alerts = [
                alert for alert in self.alert_history
                if hasattr(alert, 'started_at') and alert.started_at >= last_24h
            ]
            
            stats['last_24h'] = {
                'total_alerts': len(recent_alerts),
                'alerts_by_severity': dict(Counter(alert.severity for alert in recent_alerts))
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取告警统计失败: {e}")
            return {'error': str(e)}
    
    async def test_notification_channel(self, channel_id: str) -> bool:
        """测试通知渠道"""
        try:
            if channel_id not in self.notification_channels:
                logger.error(f"通知渠道不存在: {channel_id}")
                return False
            
            channel = self.notification_channels[channel_id]
            
            # 创建测试告警
            test_alert = Alert(
                alert_id='test_alert',
                rule_id='test_rule',
                title='测试告警',
                description='这是一个测试告警，用于验证通知渠道是否正常工作',
                severity='medium',
                status='firing',
                metric_name='test_metric',
                current_value=100.0,
                threshold=50.0,
                started_at=datetime.now(),
                labels={'test': 'true'},
                annotations={'test_channel': channel_id}
            )
            
            # 发送测试通知
            await self._send_notification(channel, test_alert)
            
            logger.info(f"测试通知渠道成功: {channel_id}")
            return True
            
        except Exception as e:
            logger.error(f"测试通知渠道失败 {channel_id}: {e}")
            return False


# 使用示例
async def example_usage():
    """使用示例"""
    
    # 创建配置
    config = {
        'alert_manager': {
            'evaluation_interval': 60,
            'default_channels': ['email_channel']
        },
        'email': {
            'enabled': True,
            'smtp_host': 'smtp.example.com',
            'smtp_port': 587,
            'username': 'alert@example.com',
            'password': 'password',
            'from_addr': 'alert@example.com',
            'to_addrs': ['admin@example.com'],
            'use_tls': True
        }
    }
    
    # 创建告警管理器
    alert_manager = AlertManager(config)
    
    # 添加告警规则
    cpu_rule = AlertRule(
        rule_id='high_cpu',
        name='CPU使用率过高',
        description='CPU使用率超过80%',
        metric_name='cpu_percent',
        condition='>',
        threshold=80.0,
        severity='high',
        duration_minutes=5,
        labels={'component': 'system'}
    )
    alert_manager.add_alert_rule(cpu_rule)
    
    try:
        # 启动告警管理器
        await alert_manager.start()
        
        # 模拟指标评估
        await alert_manager.evaluate_metric('cpu_percent', 85.0)
        
        # 等待一段时间
        await asyncio.sleep(10)
        
        # 获取活跃告警
        active_alerts = alert_manager.get_active_alerts()
        print(f"活跃告警数量: {len(active_alerts)}")
        
        # 获取统计信息
        stats = alert_manager.get_alert_statistics()
        print("告警统计:", stats)
        
        # 测试通知渠道
        test_result = await alert_manager.test_notification_channel('default_email')
        print(f"通知渠道测试结果: {test_result}")
        
    finally:
        # 停止告警管理器
        await alert_manager.stop()


if __name__ == '__main__':
    asyncio.run(example_usage())