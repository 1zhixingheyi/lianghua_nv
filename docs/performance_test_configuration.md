# 性能测试配置和脚本规范

## 1. 测试配置文件

### 1.1 配置文件路径
```
config/performance_test.json
```

### 1.2 配置文件内容
```json
{
  "redis": {
    "host": "redis-cluster.local",
    "port": 6379,
    "password": null
  },
  "clickhouse": {
    "host": "clickhouse-cluster.local",
    "port": 9000,
    "database": "benchmark"
  },
  "mysql": {
    "host": "mysql-master.local", 
    "port": 3306,
    "user": "benchmark_user",
    "password": "benchmark_pass",
    "database": "benchmark_db"
  },
  "minio": {
    "endpoint": "minio-cluster.local:9000",
    "access_key": "benchmark_access",
    "secret_key": "benchmark_secret"
  },
  "tests": {
    "redis": {
      "data_size": 10000,
      "value_size": 1024,
      "concurrency": 50
    },
    "clickhouse": {
      "data_size": 100000,
      "batch_size": 1000,
      "query_count": 1000
    },
    "mysql": {
      "data_size": 50000,
      "batch_size": 500,
      "query_count": 500
    },
    "minio": {
      "bucket_name": "benchmark-test",
      "file_count": 100,
      "file_size_mb": 1
    }
  },
  "sla_targets": {
    "hot_layer_latency_ms": 10,
    "warm_layer_latency_ms": 100,
    "cool_layer_latency_ms": 500,
    "cold_layer_latency_ms": 2000,
    "min_availability_percent": 99.95
  }
}
```

## 2. 性能测试脚本架构

### 2.1 脚本功能模块

#### 2.1.1 数据类定义
```python
@dataclass
class PerformanceMetrics:
    layer: str
    operation: str
    qps: float
    latency_p50: float
    latency_p95: float
    latency_p99: float
    throughput_mbps: float
    error_rate: float
    cpu_usage: float
    memory_usage: float
```

#### 2.1.2 基准测试类
```python
class PerformanceBenchmark:
    def __init__(self, config_file: str)
    async def initialize_clients(self)
    async def test_redis_performance(self) -> PerformanceMetrics
    async def test_clickhouse_performance(self) -> PerformanceMetrics
    async def test_mysql_performance(self) -> PerformanceMetrics
    async def test_minio_performance(self) -> PerformanceMetrics
    async def run_all_tests(self) -> List[PerformanceMetrics]
    def generate_report(self, results: List[PerformanceMetrics]) -> str
    def save_results(self, results: List[PerformanceMetrics], filename: str)
```

### 2.2 测试方法详细说明

#### 2.2.1 Redis性能测试
- **写入测试**: 插入指定数量的键值对，记录每次操作延迟
- **读取测试**: 读取所有键值对，记录读取延迟
- **指标计算**: QPS、P50/P95/P99延迟、CPU和内存使用率

#### 2.2.2 ClickHouse性能测试
- **创建测试表**: 时间序列数据表结构
- **批量插入**: 按批次插入测试数据
- **查询测试**: 执行聚合查询、过滤查询等
- **清理**: 删除测试表和数据

#### 2.2.3 MySQL性能测试
- **创建测试表**: 业务数据表结构
- **事务插入**: 批量插入测试数据
- **查询测试**: 索引查询、聚合查询
- **清理**: 删除测试表

#### 2.2.4 MinIO性能测试
- **对象上传**: 上传指定大小文件
- **对象下载**: 下载测试文件
- **吞吐量计算**: 计算上传下载吞吐量
- **清理**: 删除测试文件

## 3. 性能指标定义

### 3.1 延迟指标
- **P50延迟**: 50%请求的响应时间
- **P95延迟**: 95%请求的响应时间  
- **P99延迟**: 99%请求的响应时间

### 3.2 吞吐量指标
- **QPS**: 每秒查询数
- **TPS**: 每秒事务数
- **带宽**: MB/s吞吐量

### 3.3 资源利用率
- **CPU使用率**: 测试期间CPU占用百分比
- **内存使用率**: 测试期间内存占用百分比
- **磁盘I/O**: 读写IOPS和带宽

## 4. SLA目标对比

### 4.1 各层延迟目标
| 存储层 | P99延迟目标 | QPS目标 | 吞吐量目标 |
|--------|-------------|---------|------------|
| HOT层 (Redis) | <10ms | >50,000 | N/A |
| WARM层 (ClickHouse) | <100ms | >3,000 | N/A |
| COOL层 (MySQL) | <500ms | >800 | N/A |
| COLD层 (MinIO) | <2000ms | N/A | >500MB/s |

### 4.2 SLA达成度评估
```python
def evaluate_sla_compliance(metrics: PerformanceMetrics) -> dict:
    sla_results = {}
    
    # 延迟SLA检查
    if metrics.layer == "HOT_Redis":
        sla_results['latency'] = metrics.latency_p99 <= 10.0
        sla_results['qps'] = metrics.qps >= 50000
    elif metrics.layer == "WARM_ClickHouse":
        sla_results['latency'] = metrics.latency_p99 <= 100.0
        sla_results['qps'] = metrics.qps >= 3000
    # ... 其他层级判断
    
    return sla_results
```

## 5. 报告生成规范

### 5.1 报告结构
1. **测试概述**: 测试时间、环境、配置
2. **性能指标汇总**: 表格形式对比各层性能
3. **SLA达成情况**: 逐层分析是否达标
4. **优化建议**: 基于测试结果提供优化方向
5. **详细数据**: 原始测试数据附录

### 5.2 报告格式
- **文件名**: `performance_report_{timestamp}.md`
- **数据文件**: `performance_test_results_{timestamp}.json`
- **编码格式**: UTF-8

## 6. 测试执行流程

### 6.1 准备阶段
1. 检查配置文件有效性
2. 验证各存储服务连通性
3. 创建必要的数据库和表空间

### 6.2 执行阶段
1. 并行执行各层性能测试
2. 实时监控系统资源使用
3. 记录异常和错误信息

### 6.3 结果阶段
1. 生成性能测试报告
2. 保存原始测试数据
3. 清理测试环境

## 7. 扩展测试场景

### 7.1 压力测试
- **目标**: 测试系统在高负载下的稳定性
- **方法**: 逐步增加并发数和数据量
- **指标**: 吞吐量、错误率、资源使用率

### 7.2 持续性测试  
- **目标**: 验证长时间运行稳定性
- **方法**: 持续24-72小时负载测试
- **指标**: 内存泄漏、性能衰减、可用性

### 7.3 故障切换测试
- **目标**: 验证高可用切换能力
- **方法**: 模拟节点故障和网络分区
- **指标**: 切换时间、数据一致性、服务可用性

## 8. 自动化集成

### 8.1 CI/CD集成
```yaml
# GitHub Actions示例
name: Performance Test
on:
  schedule:
    - cron: '0 2 * * *'  # 每天凌晨2点执行
  
jobs:
  performance_test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run Performance Tests
        run: python scripts/performance_benchmark.py
      - name: Upload Results
        uses: actions/upload-artifact@v2
        with:
          name: performance-results
          path: performance_report_*.md
```

### 8.2 监控告警
- **Prometheus**: 采集性能指标
- **Grafana**: 可视化性能趋势
- **AlertManager**: 性能异常告警

## 9. 性能优化建议

### 9.1 基于测试结果的优化策略
- **延迟超标**: 检查网络、存储、索引优化
- **QPS不达标**: 增加节点、优化查询、调整配置
- **资源使用过高**: 扩容硬件、优化算法、调整参数

### 9.2 持续性能优化
- **定期基准测试**: 每月执行完整性能测试
- **趋势分析**: 监控性能指标变化趋势
- **容量规划**: 基于增长预测调整资源配置

---

*本文档定义了四层存储架构性能测试的完整规范，为系统性能验证和优化提供指导。*