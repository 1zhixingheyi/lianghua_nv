# 量化交易系统 API 文档

## 📋 文档概述

本文档详细描述了量化交易系统的RESTful API接口，包括请求格式、响应格式、错误处理和使用示例。

### API基本信息

- **基础URL**: `http://localhost:5000/api`
- **协议**: HTTP/HTTPS
- **数据格式**: JSON
- **字符编码**: UTF-8
- **API版本**: v1.0

### 统一响应格式

所有API接口都使用统一的响应格式：

```json
{
  "success": true,          // 请求是否成功
  "timestamp": "2025-08-18T12:00:00",  // 响应时间戳
  "message": "操作成功",      // 响应消息
  "data": {},              // 响应数据
  "error": ""              // 错误信息(仅在失败时存在)
}
```

### HTTP状态码

| 状态码 | 描述 | 使用场景 |
|--------|------|----------|
| 200 | OK | 请求成功 |
| 201 | Created | 资源创建成功 |
| 400 | Bad Request | 请求参数错误 |
| 401 | Unauthorized | 未授权访问 |
| 403 | Forbidden | 访问被禁止 |
| 404 | Not Found | 资源不存在 |
| 500 | Internal Server Error | 服务器内部错误 |

## 🔐 认证与授权

### JWT Token认证

系统使用JWT Token进行用户认证，需要在请求头中包含认证信息：

```
Authorization: Bearer <your_jwt_token>
```

### 获取Token

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

**响应示例：**
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_in": 3600
  },
  "message": "登录成功"
}
```

## 📊 数据查询接口

### 1. 获取仪表板汇总数据

获取系统仪表板的汇总信息。

**请求**
```http
GET /api/dashboard/summary
```

**响应示例**
```json
{
  "success": true,
  "data": {
    "portfolio_value": 1250000.50,
    "daily_pnl": 15000.25,
    "total_positions": 15,
    "active_strategies": 5,
    "risk_score": 65.5,
    "system_status": "running"
  },
  "message": "仪表板数据获取成功"
}
```

### 2. 获取策略列表

获取系统中所有策略的列表信息。

**请求**
```http
GET /api/strategies?category=technical&risk_level=medium&status=active
```

**查询参数**
| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| category | string | 否 | 策略分类：technical, fundamental, quantitative |
| risk_level | string | 否 | 风险等级：low, medium, high |
| status | string | 否 | 策略状态：active, inactive, stopped |

**响应示例**
```json
{
  "success": true,
  "data": {
    "strategies": [
      {
        "name": "ma_crossover",
        "description": "双均线交叉策略",
        "category": "technical", 
        "risk_level": "medium",
        "performance": {
          "total_return": 0.125,
          "annual_return": 0.158,
          "max_drawdown": 0.085,
          "sharpe_ratio": 1.45,
          "status": "active"
        }
      }
    ],
    "total": 8,
    "categories": ["technical", "fundamental", "quantitative"]
  },
  "message": "策略列表获取成功"
}
```

### 3. 获取策略详情

获取指定策略的详细信息。

**请求**
```http
GET /api/strategies/{strategy_name}
```

**路径参数**
| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| strategy_name | string | 是 | 策略名称 |

**响应示例**
```json
{
  "success": true,
  "data": {
    "name": "ma_crossover",
    "description": "基于移动平均线交叉的趋势跟踪策略",
    "category": "technical",
    "risk_level": "medium",
    "parameters": {
      "short_window": 10,
      "long_window": 30,
      "stop_loss": 0.05
    },
    "performance": {
      "total_return": 0.125,
      "annual_return": 0.158,
      "max_drawdown": 0.085,
      "sharpe_ratio": 1.45,
      "win_rate": 0.65,
      "trade_count": 156
    }
  },
  "message": "策略详情获取成功"
}
```

### 4. 获取持仓列表

获取当前所有持仓信息。

**请求**
```http
GET /api/positions?symbol=000001&sort_by=market_value&order=desc
```

**查询参数**
| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| symbol | string | 否 | 股票代码筛选 |
| sort_by | string | 否 | 排序字段：market_value, unrealized_pnl, pnl_ratio, weight |
| order | string | 否 | 排序方向：asc, desc |

**响应示例**
```json
{
  "success": true,
  "data": {
    "positions": [
      {
        "symbol": "000001.SZ",
        "name": "平安银行",
        "quantity": 10000,
        "avg_price": 12.50,
        "current_price": 13.20,
        "market_value": 132000,
        "unrealized_pnl": 7000,
        "pnl_ratio": 0.056,
        "weight": 0.105
      }
    ],
    "summary": {
      "total_positions": 15,
      "total_market_value": 1250000,
      "total_unrealized_pnl": 50000,
      "total_pnl_ratio": 0.040
    }
  },
  "message": "持仓数据获取成功"
}
```

### 5. 获取交易记录

获取历史交易记录，支持分页和筛选。

**请求**
```http
GET /api/trades?page=1&limit=50&symbol=000001&side=buy&start_date=2025-01-01&end_date=2025-12-31
```

**查询参数**
| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| page | integer | 否 | 页码，默认1 |
| limit | integer | 否 | 每页数量，默认50，最大1000 |
| symbol | string | 否 | 股票代码筛选 |
| side | string | 否 | 交易方向：buy, sell |
| status | string | 否 | 订单状态 |
| start_date | string | 否 | 开始日期 (YYYY-MM-DD) |
| end_date | string | 否 | 结束日期 (YYYY-MM-DD) |

**响应示例**
```json
{
  "success": true,
  "data": {
    "trades": [
      {
        "trade_id": "T202508180001",
        "order_id": "ORD20250818001",
        "symbol": "000001.SZ",
        "side": "buy",
        "quantity": 1000,
        "price": 12.50,
        "amount": 12500,
        "commission": 3.75,
        "status": "filled",
        "create_time": "2025-08-18T09:30:00",
        "fill_time": "2025-08-18T09:30:15"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 50,
      "total": 234,
      "pages": 5
    }
  },
  "message": "交易记录获取成功"
}
```

### 6. 获取回测结果

获取策略回测的历史结果。

**请求**
```http
GET /api/backtest/results?strategy=ma_crossover&start_date=2024-01-01&end_date=2024-12-31
```

**查询参数**
| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| strategy | string | 否 | 策略名称筛选 |
| start_date | string | 否 | 回测开始日期 |
| end_date | string | 否 | 回测结束日期 |

**响应示例**
```json
{
  "success": true,
  "data": {
    "backtest_id": "BT20250818001",
    "strategy_name": "ma_crossover",
    "period": {
      "start_date": "2024-01-01",
      "end_date": "2024-12-31"
    },
    "performance": {
      "total_return": 0.158,
      "annual_return": 0.158,
      "max_drawdown": 0.085,
      "sharpe_ratio": 1.45,
      "volatility": 0.156,
      "calmar_ratio": 1.86
    },
    "equity_curve": [
      {"date": "2024-01-01", "value": 1000000},
      {"date": "2024-01-02", "value": 1002500}
    ],
    "trades_summary": {
      "total_trades": 156,
      "winning_trades": 101,
      "losing_trades": 55,
      "win_rate": 0.647
    }
  },
  "message": "回测结果获取成功"
}
```

### 7. 获取风险告警

获取系统风险告警信息。

**请求**
```http
GET /api/risk/alerts?level=WARNING&status=active&limit=100
```

**查询参数**
| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| level | string | 否 | 告警级别：INFO, WARNING, ERROR, CRITICAL |
| status | string | 否 | 告警状态：active, resolved, ignored |
| limit | integer | 否 | 返回数量限制 |

**响应示例**
```json
{
  "success": true,
  "data": {
    "alerts": [
      {
        "alert_id": "ALT20250818001",
        "level": "WARNING",
        "type": "position_concentration",
        "message": "单只股票持仓比例超过10%",
        "symbol": "000001.SZ",
        "current_value": 0.105,
        "threshold": 0.10,
        "create_time": "2025-08-18T10:30:00",
        "status": "active"
      }
    ],
    "total": 15
  },
  "message": "风险告警获取成功"
}
```

## 🎯 策略管理接口

### 1. 创建策略实例

创建新的策略实例。

**请求**
```http
POST /api/strategies
Content-Type: application/json

{
  "strategy_name": "ma_crossover",
  "instance_name": "ma_crossover_001", 
  "params": {
    "short_window": 10,
    "long_window": 30,
    "stop_loss": 0.05,
    "initial_capital": 100000
  }
}
```

**请求体参数**
| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| strategy_name | string | 是 | 策略名称 |
| instance_name | string | 是 | 实例名称(唯一) |
| params | object | 否 | 策略参数 |

**响应示例**
```json
{
  "success": true,
  "data": {
    "instance_name": "ma_crossover_001",
    "strategy_name": "ma_crossover",
    "params": {
      "short_window": 10,
      "long_window": 30,
      "stop_loss": 0.05,
      "initial_capital": 100000
    },
    "created_at": "2025-08-18T12:00:00"
  },
  "message": "策略实例创建成功"
}
```

### 2. 启动策略

启动指定的策略实例。

**请求**
```http
POST /api/strategies/{strategy_name}/start
```

**响应示例**
```json
{
  "success": true,
  "data": {
    "strategy_name": "ma_crossover_001",
    "status": "started",
    "start_time": "2025-08-18T12:00:00"
  },
  "message": "策略启动成功"
}
```

### 3. 停止策略

停止指定的策略实例。

**请求**
```http
POST /api/strategies/{strategy_name}/stop
```

**响应示例**
```json
{
  "success": true,
  "data": {
    "strategy_name": "ma_crossover_001",
    "status": "stopped",
    "stop_time": "2025-08-18T12:00:00"
  },
  "message": "策略停止成功"
}
```

## 💹 交易操作接口

### 1. 提交订单

提交新的交易订单。

**请求**
```http
POST /api/orders
Content-Type: application/json

{
  "symbol": "000001.SZ",
  "side": "buy",
  "quantity": 1000,
  "order_type": "limit",
  "price": 12.50
}
```

**请求体参数**
| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| symbol | string | 是 | 股票代码 |
| side | string | 是 | 交易方向：buy, sell |
| quantity | integer | 是 | 交易数量 |
| order_type | string | 否 | 订单类型：market, limit |
| price | number | 否 | 价格(限价单必需) |

**响应示例**
```json
{
  "success": true,
  "data": {
    "order_id": "ORD20250818001",
    "symbol": "000001.SZ",
    "side": "buy",
    "quantity": 1000,
    "order_type": "limit",
    "price": 12.50,
    "status": "submitted",
    "submit_time": "2025-08-18T12:00:00"
  },
  "message": "订单提交成功"
}
```

### 2. 撤销订单

撤销指定的订单。

**请求**
```http
DELETE /api/orders/{order_id}
```

**路径参数**
| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| order_id | string | 是 | 订单ID |

**响应示例**
```json
{
  "success": true,
  "data": {
    "order_id": "ORD20250818001",
    "status": "cancelled",
    "cancel_time": "2025-08-18T12:00:00"
  },
  "message": "订单撤销成功"
}
```

### 3. 查询订单状态

查询指定订单的当前状态。

**请求**
```http
GET /api/orders/{order_id}
```

**响应示例**
```json
{
  "success": true,
  "data": {
    "order_id": "ORD20250818001",
    "symbol": "000001.SZ",
    "side": "buy",
    "quantity": 1000,
    "price": 12.50,
    "filled_quantity": 500,
    "avg_fill_price": 12.48,
    "status": "partial_filled",
    "create_time": "2025-08-18T11:50:00",
    "update_time": "2025-08-18T12:00:00"
  },
  "message": "订单状态查询成功"
}
```

## 🛡️ 风控管理接口

### 1. 获取风控配置

获取当前的风控配置参数。

**请求**
```http
GET /api/risk/config
```

**响应示例**
```json
{
  "success": true,
  "data": {
    "max_position_ratio": 0.1,
    "max_sector_ratio": 0.3,
    "stop_loss_ratio": 0.05,
    "take_profit_ratio": 0.15,
    "max_drawdown": 0.1,
    "risk_level": "medium",
    "enable_auto_stop": true,
    "enable_position_limit": true
  },
  "message": "风控配置获取成功"
}
```

### 2. 更新风控配置

更新系统的风控配置参数。

**请求**
```http
PUT /api/risk/config
Content-Type: application/json

{
  "max_position_ratio": 0.08,
  "max_sector_ratio": 0.25,
  "stop_loss_ratio": 0.04,
  "take_profit_ratio": 0.12,
  "risk_level": "low"
}
```

**响应示例**
```json
{
  "success": true,
  "data": {
    "max_position_ratio": 0.08,
    "max_sector_ratio": 0.25,
    "stop_loss_ratio": 0.04,
    "take_profit_ratio": 0.12,
    "risk_level": "low",
    "updated_at": "2025-08-18T12:00:00"
  },
  "message": "风控配置更新成功"
}
```

## ⚙️ 系统管理接口

### 1. 获取系统状态

获取系统的运行状态信息。

**请求**
```http
GET /api/system/status
```

**响应示例**
```json
{
  "success": true,
  "data": {
    "system_time": "2025-08-18T12:00:00",
    "uptime": "2 days, 3 hours, 45 minutes",
    "memory_usage": 0.65,
    "cpu_usage": 0.35,
    "disk_usage": 0.25,
    "database_status": "connected",
    "trading_status": "enabled",
    "risk_engine_status": "running",
    "active_connections": 25
  },
  "message": "系统状态获取成功"
}
```

### 2. 获取系统日志

获取系统运行日志。

**请求**
```http
GET /api/system/logs?level=ERROR&limit=100
```

**查询参数**
| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| level | string | 否 | 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL |
| limit | integer | 否 | 返回数量限制 |

**响应示例**
```json
{
  "success": true,
  "data": {
    "logs": [
      {
        "timestamp": "2025-08-18T11:58:00",
        "level": "ERROR",
        "module": "风控系统",
        "message": "持仓比例超过限制",
        "details": {
          "symbol": "000001.SZ",
          "current_ratio": 0.12,
          "limit_ratio": 0.10
        }
      }
    ],
    "total": 5
  },
  "message": "系统日志获取成功"
}
```

## 📤 数据导出接口

### 1. 导出持仓数据

导出当前持仓数据。

**请求**
```http
GET /api/export/positions?format=csv
```

**查询参数**
| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| format | string | 否 | 导出格式：json, csv, excel |

**响应示例**
```json
{
  "success": true,
  "data": {
    "format": "csv",
    "download_url": "/api/download/positions_20250818.csv",
    "file_size": "15.2KB",
    "expires_at": "2025-08-18T18:00:00"
  },
  "message": "持仓数据导出准备完成"
}
```

### 2. 导出交易记录

导出历史交易记录。

**请求**
```http
GET /api/export/trades?format=excel&start_date=2025-01-01&end_date=2025-12-31
```

**查询参数**
| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| format | string | 否 | 导出格式：json, csv, excel |
| start_date | string | 否 | 开始日期 |
| end_date | string | 否 | 结束日期 |

**响应示例**
```json
{
  "success": true,
  "data": {
    "format": "excel",
    "download_url": "/api/download/trades_20250818.xlsx",
    "record_count": 1250,
    "file_size": "125.6KB"
  },
  "message": "交易记录导出成功"
}
```

## 🔄 WebSocket实时数据接口

### 1. 订阅实时数据

订阅WebSocket实时数据推送。

**请求**
```http
POST /api/ws/subscribe
Content-Type: application/json

{
  "channels": ["quotes", "positions", "orders", "alerts"]
}
```

**请求体参数**
| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| channels | array | 是 | 订阅频道列表 |

**可用频道**
- `quotes`: 实时行情数据
- `positions`: 持仓变化
- `orders`: 订单状态更新
- `alerts`: 风险告警
- `system`: 系统状态

**响应示例**
```json
{
  "success": true,
  "data": {
    "subscribed_channels": ["quotes", "positions", "orders"],
    "websocket_url": "ws://localhost:5000/ws",
    "connection_id": "ws_conn_123456"
  },
  "message": "实时数据订阅成功"
}
```

### 2. WebSocket消息格式

**连接WebSocket**
```javascript
const ws = new WebSocket('ws://localhost:5000/ws');

ws.onmessage = function(event) {
  const message = JSON.parse(event.data);
  console.log(message);
};
```

**消息格式示例**
```json
{
  "channel": "quotes",
  "type": "tick",
  "timestamp": "2025-08-18T12:00:00",
  "data": {
    "symbol": "000001.SZ",
    "price": 13.25,
    "volume": 1000,
    "bid_price": 13.24,
    "ask_price": 13.26
  }
}
```

## ⚠️ 错误处理

### 错误响应格式

所有错误都使用统一的响应格式：

```json
{
  "success": false,
  "timestamp": "2025-08-18T12:00:00",
  "error": "详细错误信息",
  "error_code": "VALIDATION_ERROR",
  "details": {
    "field": "symbol",
    "message": "股票代码格式错误"
  }
}
```

### 常见错误码

| 错误码 | HTTP状态码 | 描述 |
|--------|-----------|------|
| VALIDATION_ERROR | 400 | 请求参数验证失败 |
| AUTHENTICATION_FAILED | 401 | 认证失败 |
| AUTHORIZATION_FAILED | 403 | 权限不足 |
| RESOURCE_NOT_FOUND | 404 | 资源不存在 |
| DUPLICATE_RESOURCE | 409 | 资源重复 |
| RATE_LIMITED | 429 | 请求频率超限 |
| INTERNAL_ERROR | 500 | 服务器内部错误 |
| TRADING_DISABLED | 503 | 交易功能不可用 |

### 错误处理示例

```javascript
// JavaScript错误处理示例
fetch('/api/orders', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + token
  },
  body: JSON.stringify(orderData)
})
.then(response => response.json())
.then(data => {
  if (data.success) {
    console.log('订单提交成功:', data.data);
  } else {
    console.error('订单提交失败:', data.error);
    // 处理具体错误
    switch(data.error_code) {
      case 'VALIDATION_ERROR':
        // 处理参数错误
        break;
      case 'INSUFFICIENT_BALANCE':
        // 处理余额不足
        break;
      default:
        // 处理其他错误
    }
  }
})
.catch(error => {
  console.error('网络错误:', error);
});
```

## 📚 SDK和代码示例

### Python SDK示例

```python
import requests
import json

class LiangHuaAPI:
    def __init__(self, base_url, token):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }
    
    def get_strategies(self, category=None, risk_level=None):
        """获取策略列表"""
        url = f"{self.base_url}/api/strategies"
        params = {}
        if category:
            params['category'] = category
        if risk_level:
            params['risk_level'] = risk_level
        
        response = requests.get(url, params=params, headers=self.headers)
        return response.json()
    
    def submit_order(self, symbol, side, quantity, order_type='market', price=None):
        """提交订单"""
        url = f"{self.base_url}/api/orders"
        data = {
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'order_type': order_type
        }
        if price:
            data['price'] = price
        
        response = requests.post(url, json=data, headers=self.headers)
        return response.json()

# 使用示例
api = LiangHuaAPI('http://localhost:5000', 'your_token_here')

# 获取策略列表
strategies = api.get_strategies(category='technical')
print(strategies)

# 提交买单
order_result = api.submit_order('000001.SZ', 'buy', 1000, 'limit', 12.50)
print(order_result)
```

### JavaScript SDK示例

```javascript
class LiangHuaAPI {
  constructor(baseUrl, token) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.token = token;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}/api${endpoint}`;
    const config = {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.token}`,
        ...options.headers
      },
      ...options
    };

    try {
      const response = await fetch(url, config);
      const data = await response.json();
      return data;
    } catch (error) {
      throw new Error(`API请求失败: ${error.message}`);
    }
  }

  // 获取仪表板数据
  async getDashboardSummary() {
    return this.request('/dashboard/summary');
  }

  // 获取持仓列表
  async getPositions(filters = {}) {
    const params = new URLSearchParams(filters);
    return this.request(`/positions?${params}`);
  }

  // 提交订单
  async submitOrder(orderData) {
    return this.request('/orders', {
      method: 'POST',
      body: JSON.stringify(orderData)
    });
  }
}

// 使用示例
const api = new LiangHuaAPI('http://localhost:5000', 'your_token_here');

// 获取仪表板数据
api.getDashboardSummary()
  .then(data => console.log('仪表板数据:', data))
  .catch(error => console.error('错误:', error));
```

## 🔧 调试工具

### Postman集合

可以导入以下Postman集合进行API测试：

```json
{
  "info": {
    "name": "LiangHua Trading API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    {
      "key": "baseUrl",
      "value": "http://localhost:5000"
    },
    {
      "key": "token",
      "value": "your_jwt_token_here"
    }
  ],
  "item": [
    {
      "name": "获取策略列表",
      "request": {
        "method": "GET",
        "header": [
          {
            "key": "Authorization",
            "value": "Bearer {{token}}"
          }
        ],
        "url": {
          "raw": "{{baseUrl}}/api/strategies",
          "host": ["{{baseUrl}}"],
          "path": ["api", "strategies"]
        }
      }
    }
  ]
}
```

### cURL命令示例

```bash
# 获取策略列表
curl -X GET "http://localhost:5000/api/strategies" \
  -H "Authorization: Bearer your_token_here" \
  -H "Content-Type: application/json"

# 提交订单
curl -X POST "http://localhost:5000/api/orders" \
  -H "Authorization: Bearer your_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "000001.SZ",
    "side": "buy", 
    "quantity": 1000,
    "order_type": "limit",
    "price": 12.50
  }'

# 获取系统状态
curl -X GET "http://localhost:5000/api/system/status" \
  -H "Authorization: Bearer your_token_here"
```

## 📋 API变更日志

### v1.0.0 (2025-08-18)
- 初始版本发布
- 实现基础的数据查询接口
- 实现策略管理接口
- 实现交易操作接口
- 实现风控管理接口
- 实现系统管理接口
- 支持WebSocket实时数据推送

### 后续版本规划

#### v1.1.0 (计划)
- 增加批量操作接口
- 优化分页查询性能
- 增加更多数据导出格式
- 完善WebSocket消息类型

#### v1.2.0 (计划)
- 增加GraphQL支持
- 实现API版本控制
- 增加高级筛选功能
- 支持自定义字段查询

---

**文档版本**: v1.0  
**最后更新**: 2025年8月18日  
**维护团队**: API开发组

## 📞 技术支持

如有API使用问题，请联系：
- 📧 Email: api-support@lianghua.com
- 🐛 Issues: [GitHub Issues](https://github.com/lianghua/api/issues)
- 📚 API测试: [在线API文档](http://localhost:5000/docs)