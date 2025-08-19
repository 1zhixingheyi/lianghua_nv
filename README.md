# 🚀 量化交易系统 (LiangHua VN)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)]()

一个功能完整、生产级别的A股量化交易系统，集成数据采集、策略开发、回测验证、风险控制、实盘交易、系统监控等全链路功能。

## 📋 系统概述

本系统是基于Python开发的企业级量化交易平台，采用模块化设计，支持多策略并行运行，具备完善的风控体系和实时监控能力。

### 核心特性

- 🔄 **完整交易链路**: 数据→策略→回测→风控→交易→监控
- 🛡️ **多层风控体系**: 实时风控、仓位管理、资金管理、止损止盈
- 📊 **专业回测引擎**: 事件驱动、多维度性能分析、可视化报告
- 🎯 **灵活策略框架**: 支持技术分析、基本面分析、机器学习策略
- 📈 **实时监控面板**: Web界面、REST API、实时数据推送
- 🔧 **完善运维体系**: 健康检查、性能监控、故障诊断、自动化部署

### 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                    量化交易系统架构                          │
├─────────────────────────────────────────────────────────────┤
│ 🌐 Web监控层     │ Flask Web应用 │ RESTful API │ WebSocket  │
├─────────────────────────────────────────────────────────────┤
│ 🎯 策略执行层     │ 策略引擎     │ 信号生成   │ 执行调度    │
├─────────────────────────────────────────────────────────────┤
│ 🛡️ 风控管理层     │ 实时风控     │ 仓位管理   │ 资金管理    │
├─────────────────────────────────────────────────────────────┤
│ 💹 交易执行层     │ QMT接口      │ 订单管理   │ 成交回报    │
├─────────────────────────────────────────────────────────────┤
│ 📊 数据服务层     │ Tushare     │ 实时行情   │ 数据缓存    │
├─────────────────────────────────────────────────────────────┤
│ 🗄️ 存储基础层     │ SQLite/MySQL│ Redis缓存  │ 文件存储    │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- 2GB+ 内存
- 现代Web浏览器
- QMT交易客户端 (实盘交易需要)

### 安装部署

1. **克隆项目**
```bash
git clone <repository-url>
cd lianghua_vn
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置系统**
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量文件
nano .env
```

4. **启动系统**
```bash
# 启动监控面板
python run_monitor.py

# 启动完整测试
python run_tests.py
```

5. **访问界面**
```
监控面板: http://127.0.0.1:5000
健康检查: http://127.0.0.1:5000/health
```

## 🎯 核心功能

### 📊 数据管理
- **多数据源接入**: Tushare专业版、QMT实时行情
- **数据质量控制**: 自动清洗、异常检测、补数机制
- **数据存储优化**: 分级存储、增量更新、快速查询

### 🧠 策略开发
- **策略框架**: 统一的策略基类、信号标准化、生命周期管理
- **技术指标库**: SMA、EMA、RSI、MACD、布林带等60+指标
- **因子研究**: 技术因子、基本面因子、另类数据因子
- **策略管理**: 策略注册、参数调优、绩效跟踪

### 🔬 回测验证
- **事件驱动引擎**: 避免未来函数、真实时间序列回放
- **完整成本模型**: 手续费、冲击成本、滑点模拟
- **多维度分析**: 收益分析、风险分析、归因分析
- **可视化报告**: 权益曲线、回撤分析、持仓分布

### 🛡️ 风险管理
- **实时风控**: 预交易检查、盘中监控、强制平仓
- **多层防护**: 账户级→策略级→品种级→订单级
- **智能风控**: 动态调仓、相关性监控、VaR计算
- **风控报告**: 实时监控、违规记录、风险预警

### 💹 实盘交易
- **QMT集成**: 支持QMT专业版交易接口
- **订单管理**: 智能路由、部分成交、订单跟踪
- **执行优化**: 最优执行算法、市场冲击最小化
- **交易记录**: 完整审计跟踪、绩效归因

### 📈 系统监控
- **实时监控**: 系统资源、交易指标、策略状态
- **可视化面板**: 仪表板、图表展示、告警中心
- **自动化运维**: 健康检查、故障恢复、性能优化
- **多维报告**: 日报、周报、月报、年报

## 🏗️ 项目结构

```
lianghua_vn/
├── 📁 backtest/           # 回测系统
│   ├── engine.py          # 回测引擎
│   ├── portfolio.py       # 组合管理
│   ├── performance.py     # 绩效分析
│   └── visualizer.py      # 可视化
├── 📁 config/             # 配置管理 (企业级四层存储架构)
│   ├── config_manager.py  # 统一配置管理器
│   ├── hot_reload_manager.py # 热重载管理器
│   ├── schemas/           # 存储层配置
│   │   ├── mysql.yaml     # MySQL配置 (结构化数据层)
│   │   ├── clickhouse.yaml # ClickHouse配置 (分析层)
│   │   ├── redis.yaml     # Redis配置 (缓存层)
│   │   ├── minio.yaml     # MinIO配置 (对象存储层)
│   │   ├── api.yaml       # API配置
│   │   ├── logging.yaml   # 日志配置
│   │   └── system.yaml    # 系统配置
│   └── modules/           # 业务模块配置
│       ├── trading.yaml   # 交易配置
│       └── data_integrity.yaml # 数据完整性配置
├── 📁 data/               # 数据管理
│   ├── database.py        # 数据库操作
│   └── tushare_client.py  # 数据源接口
├── 📁 docs/               # 文档目录
│   ├── 项目架构设计.md     # 架构设计
│   ├── API文档.md         # 接口文档
│   └── 用户使用指南.md     # 使用说明
├── 📁 monitor/            # 监控系统
│   ├── web_app.py         # Web应用
│   ├── dashboard.py       # 监控面板
│   ├── api_routes.py      # API路由
│   └── templates/         # 页面模板
├── 📁 optimization/       # 性能优化
│   ├── cache_manager.py   # 缓存管理
│   └── memory_optimizer.py # 内存优化
├── 📁 risk/               # 风险管理
│   ├── risk_engine.py     # 风控引擎
│   ├── position_manager.py # 仓位管理
│   └── money_manager.py   # 资金管理
├── 📁 scripts/            # 工具脚本
│   └── health_check_scheduler.py # 健康检查
├── 📁 strategies/         # 策略模块
│   ├── base_strategy.py   # 策略基类
│   ├── ma_crossover.py    # 均线策略
│   └── rsi_strategy.py    # RSI策略
├── 📁 tests/              # 测试套件
│   ├── unit/              # 单元测试
│   └── integration/       # 集成测试
├── 📁 trading/            # 交易执行
│   ├── base_trader.py     # 交易基类
│   └── qmt_interface.py   # QMT接口
├── 📁 validation/         # 验证系统
│   └── system_checker.py  # 系统检查
├── 📋 .env                # 环境变量配置文件
├── 🚀 run_monitor.py      # 监控启动
├── 🧪 run_tests.py        # 测试运行
└── 📦 requirements.txt    # 依赖包列表
```

## 🛠️ 技术栈

### 核心框架
- **Python 3.8+**: 主要开发语言
- **Flask 2.3+**: Web框架
- **SQLAlchemy**: ORM数据库映射
- **Pandas**: 数据处理分析
- **NumPy**: 数值计算

### 数据源
- **Tushare**: 金融数据接口
- **QMT**: 实时行情和交易接口

### 前端技术
- **Bootstrap 5**: 响应式UI框架
- **Chart.js**: 数据可视化
- **WebSocket**: 实时通信
- **jQuery**: JavaScript库

### 数据存储
- **SQLite**: 默认数据库
- **MySQL**: 生产环境数据库
- **Redis**: 缓存系统

### 监控运维
- **Prometheus**: 指标收集
- **Grafana**: 监控面板
- **Docker**: 容器化部署

## 📚 使用指南

### 基础操作

```bash
# 启动系统监控
python run_monitor.py

# 启动时指定配置
python run_monitor.py --config custom_config.json

# 调试模式启动
python run_monitor.py --debug

# 运行回测示例
python backtest_example.py

# 运行策略测试
python test_strategies.py

# 执行系统检查
python run_tests.py
```

### 配置管理

系统采用企业级四层存储架构配置管理，支持YAML配置文件和环境变量：

#### 1. **四层存储架构**
- **MySQL层**: 结构化数据存储 (`config/schemas/mysql.yaml`)
- **ClickHouse层**: 分析数据存储 (`config/schemas/clickhouse.yaml`)
- **Redis层**: 缓存数据存储 (`config/schemas/redis.yaml`)
- **MinIO层**: 对象数据存储 (`config/schemas/minio.yaml`)

#### 2. **业务模块配置**
- **交易配置**: `config/modules/trading.yaml`
- **数据完整性**: `config/modules/data_integrity.yaml`

#### 3. **环境变量配置** (`.env`)
```bash
# 数据库配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=lianghua_mysql

# ClickHouse配置
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=9000
CLICKHOUSE_DATABASE=lianghua_ch

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# MinIO配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# API配置
TUSHARE_TOKEN=your_tushare_token

# 系统配置
ENVIRONMENT=development
DEBUG_MODE=true
LOG_LEVEL=INFO
```

#### 4. **配置热重载**
系统支持配置文件变更监控和自动重载，无需重启服务。

#### 5. **多环境支持**
- 开发环境: `ENVIRONMENT=development`
- 测试环境: `ENVIRONMENT=testing`
- 生产环境: `ENVIRONMENT=production`

### 策略开发

```python
from strategies.base_strategy import BaseStrategy, Signal, SignalType

class MyStrategy(BaseStrategy):
    def get_default_parameters(self):
        return {
            'short_window': 10,
            'long_window': 30
        }
    
    def calculate_indicators(self, data):
        short_ma = data['close'].rolling(self.params['short_window']).mean()
        long_ma = data['close'].rolling(self.params['long_window']).mean()
        return {'short_ma': short_ma, 'long_ma': long_ma}
    
    def generate_signals(self, data, indicators):
        signals = []
        if indicators['short_ma'].iloc[-1] > indicators['long_ma'].iloc[-1]:
            signals.append(Signal(
                symbol=data.index[-1],
                signal_type=SignalType.BUY,
                timestamp=data.index[-1],
                price=data['close'].iloc[-1]
            ))
        return signals
```

## 🧪 测试与验证

### 测试覆盖范围

- ✅ **单元测试**: 各模块功能测试
- ✅ **集成测试**: 模块间协作测试  
- ✅ **性能测试**: 系统性能基准测试
- ✅ **压力测试**: 极限负载测试
- ✅ **回测验证**: 策略历史表现测试

### 运行测试

```bash
# 运行完整测试套件
python run_tests.py

# 运行特定模块测试
python -m pytest tests/unit/test_strategies.py

# 运行性能基准测试
python -m scripts.performance_benchmark_runner

# 运行集成测试
python test_integration.py
```

## 📊 性能指标

### 系统性能
- **响应时间**: < 100ms (API接口)
- **处理能力**: 10,000+ 记录/秒
- **并发支持**: 100+ 并发连接
- **内存使用**: < 2GB (正常运行)

### 交易性能
- **策略执行**: < 10ms (单策略)
- **风控检查**: < 5ms (单笔订单)
- **数据更新**: < 1s (全市场行情)
- **系统延迟**: < 50ms (订单提交)

## 🚀 部署选项

### 开发环境
```bash
# 直接运行
python run_monitor.py --debug
```

### 生产环境
```bash
# 使用Gunicorn
gunicorn -c gunicorn.conf.py monitor.web_app:app

# 使用Docker
docker-compose up -d
```

### 云部署
- 支持阿里云、腾讯云、AWS等主流云平台
- 提供Kubernetes部署配置
- 支持自动扩缩容

## 📖 文档资源

- 📋 [项目架构设计](docs/项目架构设计.md)
- 🔧 [API接口文档](docs/API文档.md)
- 👥 [用户使用指南](docs/用户使用指南.md)
- 🛠️ [开发者指南](docs/开发者指南.md)
- 🚀 [部署指南](docs/部署指南.md)
- 🔧 [故障排除指南](docs/故障排除指南.md)

## 🤝 贡献指南

我们欢迎所有形式的贡献！

### 参与方式
1. 🐛 **报告Bug**: 提交Issue描述问题
2. 💡 **功能建议**: 提出新功能想法
3. 📝 **文档改进**: 完善文档内容
4. 💻 **代码贡献**: 提交Pull Request

### 开发流程
1. Fork项目仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 📞 联系我们

- 📧 Email: [your-email@example.com]
- 🐛 Issues: [GitHub Issues](https://github.com/your-repo/issues)
- 📚 Wiki: [GitHub Wiki](https://github.com/your-repo/wiki)

## 🌟 致谢

感谢以下开源项目和社区的支持：
- vn.py社区
- Tushare数据源
- Flask框架
- 其他依赖包的维护者们

---

**⭐ 如果这个项目对您有帮助，请给我们一个Star！**