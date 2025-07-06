CREATE TABLE IF NOT EXISTS stock_prices (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    close_last NUMERIC,
    volume BIGINT,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    file_name VARCHAR(128) NOT NULL,
    UNIQUE (date, file_name)
);

CREATE INDEX IF NOT EXISTS idx_stock_prices_file_name ON stock_prices (file_name);
CREATE INDEX IF NOT EXISTS idx_stock_prices_date ON stock_prices (date);