-- 台股觀測站 - PostgreSQL 資料庫結構定義 (DDL)
-- 最後更新: 2024年1月
-- 資料庫: PostgreSQL 12+

-- =============================================
-- 1. 基礎設置
-- =============================================

-- 建立資料庫 (運行此腳本前執行)
-- CREATE DATABASE tw_stock_observer
--   ENCODING 'UTF8'
--   TEMPLATE 'template0'
--   LOCALE 'zh_TW.UTF-8';

-- 啟用擴展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "plpgsql";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- =============================================
-- 2. 使用者與認證表
-- =============================================

-- 使用者表
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    avatar_url VARCHAR(512),
    phone VARCHAR(20),
    
    -- 用戶類型: free, premium, professional
    user_type VARCHAR(20) DEFAULT 'free' CHECK(user_type IN ('free', 'premium', 'professional')),
    
    -- 驗證狀態
    email_verified BOOLEAN DEFAULT FALSE,
    email_verified_at TIMESTAMP WITH TIME ZONE,
    
    -- 帳戶狀態: active, suspended, deleted
    status VARCHAR(20) DEFAULT 'active' CHECK(status IN ('active', 'suspended', 'deleted')),
    
    -- 地區
    country VARCHAR(50) DEFAULT 'Taiwan',
    timezone VARCHAR(50) DEFAULT 'Asia/Taipei',
    language VARCHAR(10) DEFAULT 'zh-TW',
    
    -- 通知偏好
    notification_email BOOLEAN DEFAULT TRUE,
    notification_push BOOLEAN DEFAULT TRUE,
    
    -- 時間戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE,
    
    -- 索引
    CHECK(email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$')
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_created_at ON users(created_at);

-- 刷新令牌表 (用於登出追蹤)
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CHECK(expires_at > created_at)
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);

-- =============================================
-- 3. 股票基本資訊表
-- =============================================

-- 股票表
CREATE TABLE stocks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    english_name VARCHAR(255),
    
    -- 分類
    sector VARCHAR(100),           -- 產業別 (半導體業、電子業等)
    industry VARCHAR(100),         -- 細分行業
    market_type VARCHAR(10),       -- tse (上市), otc (櫃買)
    
    -- 上市資訊
    listing_date DATE,
    
    -- 公司資訊
    capital_stock BIGINT,          -- 股本
    shares BIGINT,                 -- 股數
    chairman VARCHAR(100),         -- 董事長
    ceo VARCHAR(100),              -- 執行長
    website VARCHAR(255),
    
    -- 財務資料 (定期更新)
    revenue BIGINT,                -- 營收
    net_income BIGINT,             -- 淨利
    eps DECIMAL(10, 2),            -- 每股盈餘
    pe_ratio DECIMAL(10, 2),       -- 本益比
    pb_ratio DECIMAL(10, 2),       -- 股價淨值比
    dividend_per_share DECIMAL(10, 2),  -- 股利
    dividend_yield DECIMAL(6, 2),  -- 股息殖利率
    
    -- 技術狀態
    is_active BOOLEAN DEFAULT TRUE,
    is_suspended BOOLEAN DEFAULT FALSE,
    suspension_reason VARCHAR(255),
    
    -- 時間戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    financial_data_updated_at TIMESTAMP WITH TIME ZONE
);

CREATE UNIQUE INDEX idx_stocks_symbol ON stocks(symbol);
CREATE INDEX idx_stocks_market_type ON stocks(market_type);
CREATE INDEX idx_stocks_sector ON stocks(sector);
CREATE INDEX idx_stocks_updated_at ON stocks(updated_at);

-- =============================================
-- 4. K線與行情資料表
-- =============================================

-- K線資料表 (日線)
CREATE TABLE klines_daily (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(10) NOT NULL,
    stock_id UUID NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    
    -- 時間戳
    date DATE NOT NULL,
    
    -- OHLC 資料
    open DECIMAL(12, 2) NOT NULL,
    high DECIMAL(12, 2) NOT NULL,
    low DECIMAL(12, 2) NOT NULL,
    close DECIMAL(12, 2) NOT NULL,
    
    -- 成交資訊
    volume BIGINT NOT NULL,        -- 成交股數
    amount BIGINT NOT NULL,        -- 成交金額
    
    -- 衍生欄位
    change DECIMAL(12, 2),         -- 漲跌點數
    change_percent DECIMAL(6, 2),  -- 漲跌百分比
    
    -- 技術指標 (由計算服務填入)
    sma_20 DECIMAL(12, 2),
    sma_50 DECIMAL(12, 2),
    sma_200 DECIMAL(12, 2),
    rsi_14 DECIMAL(6, 2),
    macd DECIMAL(12, 4),
    macd_signal DECIMAL(12, 4),
    macd_histogram DECIMAL(12, 4),
    
    -- 時間戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_klines_daily_symbol_date ON klines_daily(symbol, date);
CREATE INDEX idx_klines_daily_stock_id ON klines_daily(stock_id);
CREATE INDEX idx_klines_daily_date ON klines_daily(date);
CREATE INDEX idx_klines_daily_close ON klines_daily(close);
CREATE INDEX idx_klines_daily_volume ON klines_daily(volume);

-- K線資料表 (分鐘線)
CREATE TABLE klines_minute (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(10) NOT NULL,
    stock_id UUID NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    
    -- 時間戳
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    period VARCHAR(10) NOT NULL,   -- '1m', '5m', '15m', '1h'
    
    -- OHLC 資料
    open DECIMAL(12, 2) NOT NULL,
    high DECIMAL(12, 2) NOT NULL,
    low DECIMAL(12, 2) NOT NULL,
    close DECIMAL(12, 2) NOT NULL,
    
    -- 成交資訊
    volume BIGINT NOT NULL,
    amount BIGINT NOT NULL,
    
    -- 時間戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_klines_minute_symbol_timestamp_period 
    ON klines_minute(symbol, timestamp, period);
CREATE INDEX idx_klines_minute_stock_id ON klines_minute(stock_id);
CREATE INDEX idx_klines_minute_timestamp ON klines_minute(timestamp);

-- 即時行情快照表 (用於歷史追蹤)
CREATE TABLE price_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(10) NOT NULL,
    stock_id UUID NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    
    -- 行情資訊
    price DECIMAL(12, 2) NOT NULL,
    bid DECIMAL(12, 2),
    ask DECIMAL(12, 2),
    volume BIGINT,
    
    -- 時間戳
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_price_snapshots_symbol_timestamp ON price_snapshots(symbol, timestamp);
CREATE INDEX idx_price_snapshots_stock_id ON price_snapshots(stock_id);
CREATE INDEX idx_price_snapshots_timestamp ON price_snapshots(timestamp);

-- =============================================
-- 5. 投資組合表
-- =============================================

-- 投資組合表
CREATE TABLE portfolios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- 基本資訊
    name VARCHAR(255) NOT NULL,
    description TEXT,
    visibility VARCHAR(20) DEFAULT 'private' CHECK(visibility IN ('private', 'public', 'shared')),
    
    -- 財務信息
    budget DECIMAL(15, 2),         -- 預算
    current_value DECIMAL(15, 2) DEFAULT 0,  -- 當前市值
    cost_basis DECIMAL(15, 2) DEFAULT 0,     -- 成本
    gain DECIMAL(15, 2) DEFAULT 0,           -- 收益
    gain_percent DECIMAL(8, 2) DEFAULT 0,    -- 收益率
    
    -- 目標與實績
    target_return DECIMAL(8, 2),   -- 目標報酬率
    actual_return DECIMAL(8, 2),   -- 實際報酬率
    
    -- 風險指標
    volatility DECIMAL(6, 2),      -- 波動率
    sharpe_ratio DECIMAL(6, 2),    -- 夏普比率
    beta DECIMAL(6, 2),            -- 貝塔係數
    max_drawdown DECIMAL(8, 2),    -- 最大回撤
    
    -- 狀態
    is_active BOOLEAN DEFAULT TRUE,
    is_archived BOOLEAN DEFAULT FALSE,
    
    -- 時間戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_portfolios_user_id ON portfolios(user_id);
CREATE INDEX idx_portfolios_created_at ON portfolios(created_at);
CREATE INDEX idx_portfolios_is_active ON portfolios(is_active);

-- 投資組合持倉表
CREATE TABLE portfolio_holdings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    stock_id UUID NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    symbol VARCHAR(10) NOT NULL,
    
    -- 持倉資訊
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    purchase_price DECIMAL(12, 2) NOT NULL,
    purchase_date DATE NOT NULL,
    
    -- 成本與收益
    cost_basis DECIMAL(15, 2) NOT NULL,
    current_price DECIMAL(12, 2),
    current_value DECIMAL(15, 2),
    gain DECIMAL(15, 2),
    gain_percent DECIMAL(8, 2),
    
    -- 股利資訊
    dividends_received DECIMAL(15, 2) DEFAULT 0,
    
    -- 狀態
    status VARCHAR(20) DEFAULT 'active' CHECK(status IN ('active', 'sold', 'disposed')),
    
    -- 時間戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    sold_at TIMESTAMP WITH TIME ZONE
);

CREATE UNIQUE INDEX idx_portfolio_holdings_portfolio_symbol 
    ON portfolio_holdings(portfolio_id, symbol) WHERE status = 'active';
CREATE INDEX idx_portfolio_holdings_stock_id ON portfolio_holdings(stock_id);
CREATE INDEX idx_portfolio_holdings_created_at ON portfolio_holdings(created_at);

-- =============================================
-- 6. 交易記錄表
-- =============================================

-- 交易記錄表
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    holding_id UUID REFERENCES portfolio_holdings(id) ON DELETE SET NULL,
    
    -- 交易資訊
    symbol VARCHAR(10) NOT NULL,
    transaction_type VARCHAR(20) NOT NULL CHECK(transaction_type IN ('buy', 'sell', 'dividend')),
    quantity INTEGER,
    price DECIMAL(12, 2),
    amount DECIMAL(15, 2),
    fee DECIMAL(12, 2) DEFAULT 0,  -- 手續費
    tax DECIMAL(12, 2) DEFAULT 0,  -- 稅款
    
    -- 執行資訊
    status VARCHAR(20) DEFAULT 'completed' CHECK(status IN ('pending', 'completed', 'cancelled', 'failed')),
    execution_date TIMESTAMP WITH TIME ZONE,
    
    -- 備註
    notes TEXT,
    
    -- 時間戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_portfolio_id ON transactions(portfolio_id);
CREATE INDEX idx_transactions_symbol ON transactions(symbol);
CREATE INDEX idx_transactions_execution_date ON transactions(execution_date);
CREATE INDEX idx_transactions_created_at ON transactions(created_at);

-- =============================================
-- 7. 技術分析與指標表
-- =============================================

-- 技術指標設置表 (用戶自定義)
CREATE TABLE indicator_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- 指標配置
    indicator_name VARCHAR(50) NOT NULL,  -- 'sma', 'rsi', 'macd'等
    parameters JSONB NOT NULL,            -- 參數配置
    
    -- 使用狀態
    is_active BOOLEAN DEFAULT TRUE,
    
    -- 時間戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_indicator_settings_user_id ON indicator_settings(user_id);
CREATE INDEX idx_indicator_settings_indicator_name ON indicator_settings(indicator_name);

-- 相關性分析結果表
CREATE TABLE correlation_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol1 VARCHAR(10) NOT NULL,
    symbol2 VARCHAR(10) NOT NULL,
    stock_id1 UUID NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    stock_id2 UUID NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    
    -- 相關係數
    correlation_coefficient DECIMAL(6, 4),
    
    -- 時間窗口
    period_days INTEGER NOT NULL,
    calculation_date DATE NOT NULL,
    
    -- 時間戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_correlation_symbol1_symbol2_period 
    ON correlation_analysis(symbol1, symbol2, period_days, calculation_date);

-- =============================================
-- 8. 告警與通知表
-- =============================================

-- 告警規則表
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    portfolio_id UUID REFERENCES portfolios(id) ON DELETE SET NULL,
    
    -- 告警配置
    symbol VARCHAR(10),            -- 特定股票或 NULL (整體組合)
    alert_type VARCHAR(50) NOT NULL,  -- 'price', 'performance', 'technical', 'risk'
    condition JSONB NOT NULL,      -- 告警條件
    
    -- 例: {"operator": "greater_than", "field": "price", "value": 620}
    -- 例: {"operator": "rsi_overbought", "field": "rsi_14", "threshold": 70}
    
    -- 觸發狀態
    is_active BOOLEAN DEFAULT TRUE,
    is_triggered BOOLEAN DEFAULT FALSE,
    last_triggered_at TIMESTAMP WITH TIME ZONE,
    
    -- 通知方式
    notify_email BOOLEAN DEFAULT TRUE,
    notify_push BOOLEAN DEFAULT FALSE,
    
    -- 時間戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_alerts_user_id ON alerts(user_id);
CREATE INDEX idx_alerts_portfolio_id ON alerts(portfolio_id);
CREATE INDEX idx_alerts_symbol ON alerts(symbol);
CREATE INDEX idx_alerts_is_active ON alerts(is_active);
CREATE INDEX idx_alerts_created_at ON alerts(created_at);

-- 通知歷史表
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    alert_id UUID REFERENCES alerts(id) ON DELETE SET NULL,
    
    -- 通知內容
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    notification_type VARCHAR(50),  -- 'alert', 'info', 'warning', 'error'
    
    -- 傳送狀態
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP WITH TIME ZONE,
    
    -- 傳送方式
    sent_via VARCHAR(20),  -- 'email', 'push', 'in_app'
    
    -- 時間戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_is_read ON notifications(is_read);
CREATE INDEX idx_notifications_created_at ON notifications(created_at);

-- =============================================
-- 9. 系統日誌表
-- =============================================

-- 審計日誌表
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- 動作資訊
    action VARCHAR(100) NOT NULL,   -- 'login', 'create_portfolio', 'buy', 'sell'等
    entity_type VARCHAR(50),        -- 'stock', 'portfolio', 'transaction'
    entity_id VARCHAR(50),
    
    -- 變更詳情
    changes JSONB,
    
    -- 請求資訊
    ip_address VARCHAR(45),
    user_agent TEXT,
    
    -- 時間戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_entity_type ON audit_logs(entity_type);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- 應用日誌表 (JSON 格式)
CREATE TABLE application_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    level VARCHAR(20) NOT NULL,  -- 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    logger_name VARCHAR(255),
    message TEXT NOT NULL,
    context JSONB,
    exception TEXT,
    
    -- 時間戳
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_application_logs_level ON application_logs(level);
CREATE INDEX idx_application_logs_logger_name ON application_logs(logger_name);
CREATE INDEX idx_application_logs_timestamp ON application_logs(timestamp);

-- =============================================
-- 10. 檢視表 (View)
-- =============================================

-- 使用者投資組合概覽
CREATE VIEW user_portfolio_summary AS
SELECT 
    p.id as portfolio_id,
    p.user_id,
    p.name,
    p.budget,
    p.current_value,
    p.cost_basis,
    COALESCE(p.current_value - p.cost_basis, 0) as gain,
    CASE 
        WHEN p.cost_basis > 0 
        THEN ROUND(((p.current_value - p.cost_basis) / p.cost_basis * 100)::numeric, 2)
        ELSE 0 
    END as gain_percent,
    COUNT(DISTINCT ph.id) as holdings_count,
    p.created_at,
    p.updated_at
FROM portfolios p
LEFT JOIN portfolio_holdings ph ON p.id = ph.portfolio_id AND ph.status = 'active'
GROUP BY p.id, p.user_id, p.name, p.budget, p.current_value, p.cost_basis, p.created_at, p.updated_at;

-- 股票績效排行
CREATE VIEW stock_performance_ranking AS
SELECT 
    s.symbol,
    s.name,
    s.sector,
    kd.date,
    kd.close as current_price,
    ROUND(((kd.close - LAG(kd.close) OVER (PARTITION BY s.symbol ORDER BY kd.date)) 
           / LAG(kd.close) OVER (PARTITION BY s.symbol ORDER BY kd.date) * 100)::numeric, 2) as daily_change_percent,
    kd.volume,
    RANK() OVER (PARTITION BY kd.date ORDER BY 
           ((kd.close - LAG(kd.close) OVER (PARTITION BY s.symbol ORDER BY kd.date)) 
           / LAG(kd.close) OVER (PARTITION BY s.symbol ORDER BY kd.date)) DESC) as ranking
FROM stocks s
LEFT JOIN klines_daily kd ON s.id = kd.stock_id
WHERE kd.date = CURRENT_DATE;

-- =============================================
-- 11. 觸發器與函數
-- =============================================

-- 自動更新 updated_at 欄位
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 為所有相關表建立觸發器
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_stocks_updated_at BEFORE UPDATE ON stocks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_portfolios_updated_at BEFORE UPDATE ON portfolios
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_portfolio_holdings_updated_at BEFORE UPDATE ON portfolio_holdings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_transactions_updated_at BEFORE UPDATE ON transactions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_alerts_updated_at BEFORE UPDATE ON alerts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 計算投資組合收益函數
CREATE OR REPLACE FUNCTION calculate_portfolio_gain(portfolio_id UUID)
RETURNS TABLE(total_cost NUMERIC, total_value NUMERIC, total_gain NUMERIC, gain_percent NUMERIC) AS $$
SELECT 
    SUM(ph.cost_basis),
    SUM(ph.current_value),
    SUM(ph.current_value - ph.cost_basis),
    CASE 
        WHEN SUM(ph.cost_basis) > 0 
        THEN ROUND(((SUM(ph.current_value) - SUM(ph.cost_basis)) / SUM(ph.cost_basis) * 100)::numeric, 2)
        ELSE 0 
    END
FROM portfolio_holdings ph
WHERE ph.portfolio_id = $1 AND ph.status = 'active';
$$ LANGUAGE SQL;

-- =============================================
-- 12. 初始化 / 種子資料 (可選)
-- =============================================

-- 插入一些初始股票資料
INSERT INTO stocks (symbol, name, english_name, sector, market_type, listing_date)
VALUES 
    ('2330', '台積電', 'Taiwan Semiconductor Manufacturing Company Limited', '半導體業', 'tse', '1994-06-05'),
    ('2454', '聯發科', 'MediaTek Inc.', '半導體業', 'tse', '1997-03-27'),
    ('1303', '南亞', 'Nan Ya Plastics Corporation', '塑膠業', 'tse', '1973-02-01'),
    ('2882', '國泰金', 'Cathay Financial Holdings Co., Ltd.', '金融保險業', 'tse', '1992-12-16'),
    ('0050', '元大台灣50', 'Taiwan Top 50 Tracker Fund', '基金', 'tse', '2003-06-30')
ON CONFLICT (symbol) DO NOTHING;

-- =============================================
-- 13. 備份與還原建議
-- =============================================

-- 備份整個資料庫 (在命令行運行)
-- pg_dump -U postgres -h localhost tw_stock_observer > backup.sql

-- 還原資料庫 (在命令行運行)
-- psql -U postgres -h localhost tw_stock_observer < backup.sql

-- 備份特定表
-- pg_dump -U postgres -h localhost tw_stock_observer -t stocks > stocks_backup.sql

-- =============================================
-- 14. 性能優化建議
-- =============================================

-- 定期分析和真空清理
-- ANALYZE;
-- VACUUM ANALYZE;

-- 建立部分索引 (僅針對活躍記錄)
-- CREATE INDEX idx_alerts_active ON alerts(user_id) WHERE is_active = TRUE;

-- 建立並行索引 (不鎖定表)
-- CREATE INDEX CONCURRENTLY idx_stocks_sector_concurrent ON stocks(sector);

-- =============================================
-- 修訂歷史
-- =============================================

/*
版本 1.0 (2024-01-15)
- 初始建立資料庫結構
- 完成用戶、股票、K線、投資組合等核心表設計
- 添加技術指標、告警、通知、日誌表
- 建立視圖與觸發器
*/
