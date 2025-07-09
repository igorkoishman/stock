CREATE TABLE IF NOT EXISTS stock_prices (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    close_last NUMERIC,
    volume BIGINT,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    label VARCHAR(128) NOT NULL,
    UNIQUE (date, label)
);

CREATE INDEX IF NOT EXISTS idx_stock_prices_label ON stock_prices (label);
CREATE INDEX IF NOT EXISTS idx_stock_prices_date ON stock_prices (date);