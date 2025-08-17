-- 量化交易系统数据库初始化脚本

-- 创建数据库
CREATE DATABASE IF NOT EXISTS quantdb DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE quantdb;

-- 股票基础信息表
CREATE TABLE IF NOT EXISTS stock_basic (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    symbol VARCHAR(20) NOT NULL COMMENT '股票代码',
    name VARCHAR(50) NOT NULL COMMENT '股票名称',
    area VARCHAR(20) COMMENT '地域',
    industry VARCHAR(50) COMMENT '行业',
    market VARCHAR(10) COMMENT '市场类型',
    list_date DATE COMMENT '上市日期',
    is_hs VARCHAR(10) COMMENT '是否沪深港通',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ts_code (ts_code),
    INDEX idx_symbol (symbol),
    INDEX idx_industry (industry)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票基础信息表';

-- 日线行情表
CREATE TABLE IF NOT EXISTS daily_quotes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    trade_date DATE NOT NULL COMMENT '交易日期',
    open_price DECIMAL(10,3) COMMENT '开盘价',
    high_price DECIMAL(10,3) COMMENT '最高价',
    low_price DECIMAL(10,3) COMMENT '最低价',
    close_price DECIMAL(10,3) COMMENT '收盘价',
    pre_close DECIMAL(10,3) COMMENT '昨收价',
    change_pct DECIMAL(8,4) COMMENT '涨跌幅%',
    vol BIGINT COMMENT '成交量(手)',
    amount DECIMAL(15,3) COMMENT '成交额(千元)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_code_date (ts_code, trade_date),
    INDEX idx_trade_date (trade_date),
    INDEX idx_ts_code (ts_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='日线行情表';

-- 策略配置表
CREATE TABLE IF NOT EXISTS strategy_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_name VARCHAR(50) NOT NULL COMMENT '策略名称',
    strategy_type VARCHAR(20) NOT NULL COMMENT '策略类型',
    parameters JSON COMMENT '策略参数',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_strategy_name (strategy_name),
    INDEX idx_strategy_type (strategy_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='策略配置表';

-- 回测结果表
CREATE TABLE IF NOT EXISTS backtest_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_id INT NOT NULL COMMENT '策略ID',
    start_date DATE NOT NULL COMMENT '回测开始日期',
    end_date DATE NOT NULL COMMENT '回测结束日期',
    initial_capital DECIMAL(15,2) NOT NULL COMMENT '初始资金',
    final_capital DECIMAL(15,2) NOT NULL COMMENT '最终资金',
    total_return DECIMAL(8,4) COMMENT '总收益率',
    annual_return DECIMAL(8,4) COMMENT '年化收益率',
    max_drawdown DECIMAL(8,4) COMMENT '最大回撤',
    sharpe_ratio DECIMAL(8,4) COMMENT '夏普比率',
    win_rate DECIMAL(8,4) COMMENT '胜率',
    trade_count INT COMMENT '交易次数',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_strategy_id (strategy_id),
    INDEX idx_start_date (start_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='回测结果表';

-- 交易记录表
CREATE TABLE IF NOT EXISTS trade_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    strategy_id INT NOT NULL COMMENT '策略ID',
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    trade_date DATE NOT NULL COMMENT '交易日期',
    direction VARCHAR(10) NOT NULL COMMENT '买卖方向(BUY/SELL)',
    price DECIMAL(10,3) NOT NULL COMMENT '成交价格',
    quantity INT NOT NULL COMMENT '成交数量',
    amount DECIMAL(15,2) NOT NULL COMMENT '成交金额',
    commission DECIMAL(10,2) COMMENT '手续费',
    order_type VARCHAR(20) COMMENT '订单类型',
    is_simulation BOOLEAN DEFAULT TRUE COMMENT '是否模拟交易',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_strategy_id (strategy_id),
    INDEX idx_ts_code (ts_code),
    INDEX idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易记录表';

-- 风控记录表
CREATE TABLE IF NOT EXISTS risk_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    strategy_id INT NOT NULL COMMENT '策略ID',
    ts_code VARCHAR(20) COMMENT 'TS代码',
    risk_type VARCHAR(20) NOT NULL COMMENT '风控类型',
    risk_level VARCHAR(10) NOT NULL COMMENT '风险等级',
    description TEXT COMMENT '风险描述',
    action_taken VARCHAR(50) COMMENT '采取的行动',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_strategy_id (strategy_id),
    INDEX idx_risk_type (risk_type),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='风控记录表';

-- 插入一些示例数据
INSERT INTO strategy_config (strategy_name, strategy_type, parameters) VALUES 
('双均线策略', 'MA_CROSSOVER', '{"fast_window": 5, "slow_window": 20, "stop_loss": 0.05, "stop_profit": 0.15}'),
('RSI策略', 'RSI', '{"period": 14, "oversold": 30, "overbought": 70}');

-- 创建用户
CREATE USER IF NOT EXISTS 'quant'@'%' IDENTIFIED BY 'quant123';
GRANT ALL PRIVILEGES ON quantdb.* TO 'quant'@'%';
FLUSH PRIVILEGES;