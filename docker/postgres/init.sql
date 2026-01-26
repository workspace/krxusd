-- KRXUSD Database Initialization Script
-- PostgreSQL: 과거 일별 종가 데이터, 종목 마스터 정보 저장용

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================
-- Stock Master Table (종목 마스터 정보)
-- =============================================
CREATE TABLE IF NOT EXISTS stocks (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    name_en VARCHAR(100),
    market VARCHAR(10) NOT NULL CHECK (market IN ('KOSPI', 'KOSDAQ', 'KONEX')),
    sector VARCHAR(100),
    industry VARCHAR(100),
    listed_shares BIGINT,
    listing_date DATE,
    fiscal_month SMALLINT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for stocks table
CREATE INDEX IF NOT EXISTS idx_stocks_symbol ON stocks(symbol);
CREATE INDEX IF NOT EXISTS idx_stocks_market ON stocks(market);
CREATE INDEX IF NOT EXISTS idx_stocks_name ON stocks(name);
CREATE INDEX IF NOT EXISTS idx_stocks_is_active ON stocks(is_active);

-- =============================================
-- Daily Stock Price Table (일별 종가 데이터)
-- =============================================
CREATE TABLE IF NOT EXISTS stock_prices (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    price_date DATE NOT NULL,
    open_price NUMERIC(15, 2) NOT NULL,
    high_price NUMERIC(15, 2) NOT NULL,
    low_price NUMERIC(15, 2) NOT NULL,
    close_price NUMERIC(15, 2) NOT NULL,
    volume BIGINT NOT NULL DEFAULT 0,
    trading_value NUMERIC(20, 2),
    market_cap NUMERIC(20, 2),
    shares_outstanding BIGINT,
    exchange_rate NUMERIC(15, 4),
    close_price_usd NUMERIC(15, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_id, price_date)
);

-- Indexes for stock_prices table (optimized for common queries)
CREATE INDEX IF NOT EXISTS idx_stock_prices_stock_id ON stock_prices(stock_id);
CREATE INDEX IF NOT EXISTS idx_stock_prices_price_date ON stock_prices(price_date);
CREATE INDEX IF NOT EXISTS idx_stock_prices_stock_date ON stock_prices(stock_id, price_date DESC);

-- Partial index for recent data queries (last 1 year)
CREATE INDEX IF NOT EXISTS idx_stock_prices_recent
ON stock_prices(stock_id, price_date DESC)
WHERE price_date >= CURRENT_DATE - INTERVAL '1 year';

-- =============================================
-- Exchange Rate History Table (환율 히스토리)
-- =============================================
CREATE TABLE IF NOT EXISTS exchange_rates (
    id SERIAL PRIMARY KEY,
    currency_pair VARCHAR(10) NOT NULL DEFAULT 'USD/KRW',
    rate NUMERIC(15, 4) NOT NULL,
    rate_date TIMESTAMP WITH TIME ZONE NOT NULL,
    source VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(currency_pair, rate_date)
);

-- Indexes for exchange_rates table
CREATE INDEX IF NOT EXISTS idx_exchange_rates_pair_date ON exchange_rates(currency_pair, rate_date DESC);
CREATE INDEX IF NOT EXISTS idx_exchange_rates_date ON exchange_rates(rate_date);

-- =============================================
-- Data Sync Status Table (데이터 동기화 상태 추적)
-- =============================================
CREATE TABLE IF NOT EXISTS sync_status (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    data_type VARCHAR(20) NOT NULL CHECK (data_type IN ('daily_price', 'minute_price', 'fundamental')),
    last_sync_date DATE,
    last_sync_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'syncing', 'completed', 'failed')),
    error_message TEXT,
    UNIQUE(stock_id, data_type)
);

-- Index for sync_status
CREATE INDEX IF NOT EXISTS idx_sync_status_stock_id ON sync_status(stock_id);

-- =============================================
-- Popular/Trending Stocks Table (인기 종목 캐시)
-- =============================================
CREATE TABLE IF NOT EXISTS popular_stocks (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    ranking_type VARCHAR(20) NOT NULL CHECK (ranking_type IN ('volume', 'value', 'gain', 'loss')),
    rank_position SMALLINT NOT NULL,
    rank_date DATE NOT NULL DEFAULT CURRENT_DATE,
    metric_value NUMERIC(20, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_id, ranking_type, rank_date)
);

-- Index for popular_stocks
CREATE INDEX IF NOT EXISTS idx_popular_stocks_date_type ON popular_stocks(rank_date, ranking_type);

-- =============================================
-- Auto-update timestamp function
-- =============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to stocks table
DROP TRIGGER IF EXISTS update_stocks_updated_at ON stocks;
CREATE TRIGGER update_stocks_updated_at
    BEFORE UPDATE ON stocks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================
-- Useful Views
-- =============================================

-- View: Latest prices with stock info
CREATE OR REPLACE VIEW vw_latest_prices AS
SELECT
    s.id,
    s.symbol,
    s.name,
    s.market,
    sp.price_date,
    sp.close_price,
    sp.volume,
    sp.exchange_rate,
    sp.close_price_usd
FROM stocks s
LEFT JOIN LATERAL (
    SELECT *
    FROM stock_prices
    WHERE stock_id = s.id
    ORDER BY price_date DESC
    LIMIT 1
) sp ON true
WHERE s.is_active = true;

-- View: Stock price with change percentage
CREATE OR REPLACE VIEW vw_stock_price_changes AS
SELECT
    sp.stock_id,
    s.symbol,
    s.name,
    sp.price_date,
    sp.close_price,
    sp.close_price_usd,
    LAG(sp.close_price) OVER (PARTITION BY sp.stock_id ORDER BY sp.price_date) as prev_close,
    CASE
        WHEN LAG(sp.close_price) OVER (PARTITION BY sp.stock_id ORDER BY sp.price_date) > 0
        THEN ROUND(((sp.close_price - LAG(sp.close_price) OVER (PARTITION BY sp.stock_id ORDER BY sp.price_date))
            / LAG(sp.close_price) OVER (PARTITION BY sp.stock_id ORDER BY sp.price_date) * 100)::numeric, 2)
        ELSE 0
    END as change_percent
FROM stock_prices sp
JOIN stocks s ON s.id = sp.stock_id;

-- =============================================
-- Grant permissions
-- =============================================
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO krxusd;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO krxusd;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO krxusd;

-- Insert initial data: Common market indices as reference
INSERT INTO stocks (symbol, name, name_en, market, sector, is_active) VALUES
    ('KOSPI', 'KOSPI 지수', 'KOSPI Index', 'KOSPI', 'Index', true),
    ('KOSDAQ', 'KOSDAQ 지수', 'KOSDAQ Index', 'KOSDAQ', 'Index', true)
ON CONFLICT (symbol) DO NOTHING;

-- Done
SELECT 'KRXUSD Database initialized successfully!' as message;
