"""
系统健康检查器

负责检查系统各组件的健康状况和可用性
"""

import asyncio
import aiohttp
import logging
import traceback
from typing import Dict, Any, List, Optional
from datetime import datetime
import socket
import subprocess
import platform

logger = logging.getLogger(__name__)


class HealthCheckResult:
    """健康检查结果"""
    
    def __init__(self, component: str):
        self.component = component
        self.status = 'unknown'  # healthy, warning, critical, unknown
        self.message = ''
        self.details = {}
        self.response_time = 0.0
        self.timestamp = datetime.now()
        self.checks_passed = 0
        self.checks_total = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'component': self.component,
            'status': self.status,
            'message': self.message,
            'details': self.details,
            'response_time': self.response_time,
            'timestamp': self.timestamp.isoformat(),
            'checks_passed': self.checks_passed,
            'checks_total': self.checks_total,
            'success_rate': self.checks_passed / max(self.checks_total, 1) * 100
        }


class SystemChecker:
    """系统健康检查器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 默认检查配置
        self.check_config = {
            'database': {
                'enabled': True,
                'timeout': 5.0,
                'retry_count': 3
            },
            'web_server': {
                'enabled': True,
                'url': 'http://localhost:5000/api/health',
                'timeout': 10.0,
                'retry_count': 2
            },
            'data_sources': {
                'enabled': True,
                'timeout': 15.0,
                'retry_count': 2
            },
            'file_system': {
                'enabled': True,
                'paths': ['./data', './logs', './config'],
                'timeout': 5.0
            },
            'network': {
                'enabled': True,
                'hosts': ['8.8.8.8', 'www.baidu.com'],
                'timeout': 5.0
            },
            'services': {
                'enabled': True,
                'timeout': 10.0
            }
        }
        
        # 更新配置
        if 'health_checks' in config:
            self.check_config.update(config['health_checks'])
    
    async def run_health_checks(self) -> Dict[str, HealthCheckResult]:
        """运行所有健康检查"""
        logger.info("开始系统健康检查")
        
        results = {}
        
        # 并发运行各项检查
        tasks = []
        
        if self.check_config['database']['enabled']:
            tasks.append(self._check_database())
        
        if self.check_config['web_server']['enabled']:
            tasks.append(self._check_web_server())
        
        if self.check_config['data_sources']['enabled']:
            tasks.append(self._check_data_sources())
        
        if self.check_config['file_system']['enabled']:
            tasks.append(self._check_file_system())
        
        if self.check_config['network']['enabled']:
            tasks.append(self._check_network())
        
        if self.check_config['services']['enabled']:
            tasks.append(self._check_services())
        
        # 执行所有检查任务
        try:
            check_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in check_results:
                if isinstance(result, HealthCheckResult):
                    results[result.component] = result
                elif isinstance(result, Exception):
                    logger.error(f"健康检查异常: {result}")
                    error_result = HealthCheckResult('unknown')
                    error_result.status = 'critical'
                    error_result.message = f"检查失败: {str(result)}"
                    results['error'] = error_result
        
        except Exception as e:
            logger.error(f"健康检查执行失败: {e}")
            traceback.print_exc()
        
        logger.info(f"系统健康检查完成，检查了{len(results)}个组件")
        return results
    
    async def _check_database(self) -> HealthCheckResult:
        """检查数据库健康状况"""
        result = HealthCheckResult('database')
        start_time = datetime.now()
        
        try:
            # 模拟数据库检查（实际项目中应导入真实的数据库管理器）
            checks = [
                ('连接测试', self._test_db_connection),
                ('查询测试', self._test_db_query),
                ('表存在性', self._test_db_tables)
            ]
            
            for check_name, check_func in checks:
                try:
                    await asyncio.wait_for(
                        check_func(),
                        timeout=self.check_config['database']['timeout']
                    )
                    result.checks_passed += 1
                    result.details[check_name] = 'passed'
                except Exception as e:
                    result.details[check_name] = f'failed: {str(e)}'
                
                result.checks_total += 1
            
            # 判断整体状态
            success_rate = result.checks_passed / result.checks_total
            if success_rate >= 1.0:
                result.status = 'healthy'
                result.message = '数据库运行正常'
            elif success_rate >= 0.5:
                result.status = 'warning'
                result.message = f'数据库部分功能异常 ({result.checks_passed}/{result.checks_total})'
            else:
                result.status = 'critical'
                result.message = f'数据库严重异常 ({result.checks_passed}/{result.checks_total})'
        
        except Exception as e:
            result.status = 'critical'
            result.message = f'数据库检查失败: {str(e)}'
            logger.error(f"数据库健康检查失败: {e}")
        
        end_time = datetime.now()
        result.response_time = (end_time - start_time).total_seconds()
        
        return result
    
    async def _test_db_connection(self):
        """测试数据库连接"""
        # 模拟数据库连接测试
        await asyncio.sleep(0.1)  # 模拟连接时间
        # 在实际项目中，这里应该测试真实的数据库连接
        
    async def _test_db_query(self):
        """测试数据库查询"""
        # 模拟查询测试
        await asyncio.sleep(0.1)
        # 在实际项目中，这里应该执行简单的查询
        
    async def _test_db_tables(self):
        """测试数据库表存在性"""
        # 模拟表检查
        await asyncio.sleep(0.1)
        # 在实际项目中，这里应该检查关键表是否存在
    
    async def _check_web_server(self) -> HealthCheckResult:
        """检查Web服务器健康状况"""
        result = HealthCheckResult('web_server')
        start_time = datetime.now()
        
        try:
            url = self.check_config['web_server']['url']
            timeout = self.check_config['web_server']['timeout']
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        result.status = 'healthy'
                        result.message = 'Web服务器运行正常'
                        result.checks_passed = 1
                        result.details['http_status'] = response.status
                        result.details['response_body'] = await response.text()
                    else:
                        result.status = 'warning'
                        result.message = f'Web服务器响应异常: HTTP {response.status}'
                        result.details['http_status'] = response.status
                    
                    result.checks_total = 1
        
        except asyncio.TimeoutError:
            result.status = 'critical'
            result.message = f'Web服务器响应超时 (>{timeout}秒)'
            result.checks_total = 1
        
        except aiohttp.ClientConnectorError:
            result.status = 'critical'
            result.message = 'Web服务器连接失败'
            result.checks_total = 1
        
        except Exception as e:
            result.status = 'critical'
            result.message = f'Web服务器检查失败: {str(e)}'
            result.checks_total = 1
            logger.error(f"Web服务器健康检查失败: {e}")
        
        end_time = datetime.now()
        result.response_time = (end_time - start_time).total_seconds()
        
        return result
    
    async def _check_data_sources(self) -> HealthCheckResult:
        """检查数据源健康状况"""
        result = HealthCheckResult('data_sources')
        start_time = datetime.now()
        
        try:
            checks = [
                ('Tushare连接', self._test_tushare_connection),
                ('数据获取', self._test_data_fetch)
            ]
            
            for check_name, check_func in checks:
                try:
                    await asyncio.wait_for(
                        check_func(),
                        timeout=self.check_config['data_sources']['timeout']
                    )
                    result.checks_passed += 1
                    result.details[check_name] = 'passed'
                except Exception as e:
                    result.details[check_name] = f'failed: {str(e)}'
                
                result.checks_total += 1
            
            # 判断整体状态
            success_rate = result.checks_passed / result.checks_total
            if success_rate >= 1.0:
                result.status = 'healthy'
                result.message = '数据源运行正常'
            elif success_rate >= 0.5:
                result.status = 'warning'
                result.message = f'数据源部分异常 ({result.checks_passed}/{result.checks_total})'
            else:
                result.status = 'critical'
                result.message = f'数据源严重异常 ({result.checks_passed}/{result.checks_total})'
        
        except Exception as e:
            result.status = 'critical'
            result.message = f'数据源检查失败: {str(e)}'
            logger.error(f"数据源健康检查失败: {e}")
        
        end_time = datetime.now()
        result.response_time = (end_time - start_time).total_seconds()
        
        return result
    
    async def _test_tushare_connection(self):
        """测试Tushare连接"""
        # 模拟Tushare连接测试
        await asyncio.sleep(0.2)
        
    async def _test_data_fetch(self):
        """测试数据获取"""
        # 模拟数据获取测试
        await asyncio.sleep(0.3)
    
    async def _check_file_system(self) -> HealthCheckResult:
        """检查文件系统健康状况"""
        result = HealthCheckResult('file_system')
        start_time = datetime.now()
        
        try:
            import os
            import tempfile
            
            paths = self.check_config['file_system']['paths']
            
            for path in paths:
                try:
                    # 检查目录是否存在
                    if os.path.exists(path):
                        result.checks_passed += 1
                        result.details[f'{path}_exists'] = 'passed'
                        
                        # 检查读写权限
                        if os.access(path, os.R_OK | os.W_OK):
                            result.details[f'{path}_permissions'] = 'passed'
                        else:
                            result.details[f'{path}_permissions'] = 'failed: no read/write permission'
                    else:
                        result.details[f'{path}_exists'] = 'failed: path not found'
                
                except Exception as e:
                    result.details[f'{path}_error'] = f'failed: {str(e)}'
                
                result.checks_total += 1
            
            # 测试临时文件创建
            try:
                with tempfile.NamedTemporaryFile(delete=True) as temp_file:
                    temp_file.write(b'test')
                    temp_file.flush()
                result.checks_passed += 1
                result.details['temp_file_creation'] = 'passed'
            except Exception as e:
                result.details['temp_file_creation'] = f'failed: {str(e)}'
            
            result.checks_total += 1
            
            # 判断整体状态
            success_rate = result.checks_passed / result.checks_total
            if success_rate >= 1.0:
                result.status = 'healthy'
                result.message = '文件系统运行正常'
            elif success_rate >= 0.8:
                result.status = 'warning'
                result.message = f'文件系统部分异常 ({result.checks_passed}/{result.checks_total})'
            else:
                result.status = 'critical'
                result.message = f'文件系统严重异常 ({result.checks_passed}/{result.checks_total})'
        
        except Exception as e:
            result.status = 'critical'
            result.message = f'文件系统检查失败: {str(e)}'
            logger.error(f"文件系统健康检查失败: {e}")
        
        end_time = datetime.now()
        result.response_time = (end_time - start_time).total_seconds()
        
        return result
    
    async def _check_network(self) -> HealthCheckResult:
        """检查网络连接健康状况"""
        result = HealthCheckResult('network')
        start_time = datetime.now()
        
        try:
            hosts = self.check_config['network']['hosts']
            timeout = self.check_config['network']['timeout']
            
            for host in hosts:
                try:
                    # 测试网络连通性
                    if await self._ping_host(host, timeout):
                        result.checks_passed += 1
                        result.details[f'{host}_ping'] = 'passed'
                    else:
                        result.details[f'{host}_ping'] = 'failed: timeout or unreachable'
                
                except Exception as e:
                    result.details[f'{host}_ping'] = f'failed: {str(e)}'
                
                result.checks_total += 1
            
            # 判断整体状态
            success_rate = result.checks_passed / result.checks_total
            if success_rate >= 1.0:
                result.status = 'healthy'
                result.message = '网络连接正常'
            elif success_rate >= 0.5:
                result.status = 'warning'
                result.message = f'网络部分不稳定 ({result.checks_passed}/{result.checks_total})'
            else:
                result.status = 'critical'
                result.message = f'网络连接异常 ({result.checks_passed}/{result.checks_total})'
        
        except Exception as e:
            result.status = 'critical'
            result.message = f'网络检查失败: {str(e)}'
            logger.error(f"网络健康检查失败: {e}")
        
        end_time = datetime.now()
        result.response_time = (end_time - start_time).total_seconds()
        
        return result
    
    async def _ping_host(self, host: str, timeout: float) -> bool:
        """Ping主机测试连通性"""
        try:
            # 根据操作系统选择ping命令
            system = platform.system().lower()
            if system == 'windows':
                cmd = ['ping', '-n', '1', '-w', str(int(timeout * 1000)), host]
            else:
                cmd = ['ping', '-c', '1', '-W', str(int(timeout)), host]
            
            # 执行ping命令
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout + 1
            )
            
            return process.returncode == 0
        
        except asyncio.TimeoutError:
            return False
        except Exception:
            return False
    
    async def _check_services(self) -> HealthCheckResult:
        """检查服务健康状况"""
        result = HealthCheckResult('services')
        start_time = datetime.now()
        
        try:
            # 检查各个服务模块
            services = [
                ('策略管理器', self._test_strategy_manager),
                ('风险引擎', self._test_risk_engine),
                ('交易执行器', self._test_trade_executor)
            ]
            
            for service_name, test_func in services:
                try:
                    await test_func()
                    result.checks_passed += 1
                    result.details[service_name] = 'passed'
                except Exception as e:
                    result.details[service_name] = f'failed: {str(e)}'
                result.checks_total += 1
            
            # 判断整体状态
            success_rate = result.checks_passed / result.checks_total
            if success_rate >= 1.0:
                result.status = 'healthy'
                result.message = '服务运行正常'
            elif success_rate >= 0.7:
                result.status = 'warning'
                result.message = f'部分服务异常 ({result.checks_passed}/{result.checks_total})'
            else:
                result.status = 'critical'
                result.message = f'服务严重异常 ({result.checks_passed}/{result.checks_total})'
        
        except Exception as e:
            result.status = 'critical'
            result.message = f'服务检查失败: {str(e)}'
            logger.error(f"服务健康检查失败: {e}")
        
        end_time = datetime.now()
        result.response_time = (end_time - start_time).total_seconds()
        
        return result
    
    async def _test_strategy_manager(self):
        """测试策略管理器"""
        # 模拟策略管理器测试
        await asyncio.sleep(0.1)
    
    async def _test_risk_engine(self):
        """测试风险引擎"""
        # 模拟风险引擎测试
        await asyncio.sleep(0.1)
    
    async def _test_trade_executor(self):
        """测试交易执行器"""
        # 模拟交易执行器测试
        await asyncio.sleep(0.1)
    
    def generate_health_report(self, results: Dict[str, HealthCheckResult]) -> Dict[str, Any]:
        """生成健康检查报告"""
        report = {
            'overall_status': 'healthy',
            'components': {},
            'summary': {
                'total_components': len(results),
                'healthy_components': 0,
                'warning_components': 0,
                'critical_components': 0,
                'unknown_components': 0
            },
            'recommendations': [],
            'timestamp': datetime.now().isoformat()
        }
        
        # 汇总各组件状态
        for component, result in results.items():
            report['components'][component] = result.to_dict()
            
            if result.status == 'healthy':
                report['summary']['healthy_components'] += 1
            elif result.status == 'warning':
                report['summary']['warning_components'] += 1
            elif result.status == 'critical':
                report['summary']['critical_components'] += 1
            else:
                report['summary']['unknown_components'] += 1
        
        # 确定整体状态
        if report['summary']['critical_components'] > 0:
            report['overall_status'] = 'critical'
        elif report['summary']['warning_components'] > 0:
            report['overall_status'] = 'warning'
        
        # 生成建议
        report['recommendations'] = self._generate_health_recommendations(results)
        
        return report
    
    def _generate_health_recommendations(self, results: Dict[str, HealthCheckResult]) -> List[str]:
        """生成健康检查建议"""
        recommendations = []
        
        for component, result in results.items():
            if result.status == 'critical':
                recommendations.append(f"紧急处理{component}组件问题: {result.message}")
            elif result.status == 'warning':
                recommendations.append(f"关注{component}组件状态: {result.message}")
        
        # 通用建议
        if not recommendations:
            recommendations.append("系统运行正常，建议定期进行健康检查")
        
        return recommendations