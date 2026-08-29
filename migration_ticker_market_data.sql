-- Nieuwe, GEDEELDE tabel voor marktdata -- 1 rij per unieke ticker,
-- bijgewerkt door het nieuwe achtergrond-sync-script (elke 15 min),
-- gelezen door dashboard.py i.p.v. live yfinance-aanroepen tijdens het
-- laden van een pagina. Geen user_email-kolom nodig: dit is publieke
-- marktdata, gedeeld tussen ALLE gebruikers (geen duplicatie per persoon).

CREATE TABLE IF NOT EXISTS ticker_market_data (
    ticker TEXT PRIMARY KEY,
    current_price NUMERIC,
    previous_close NUMERIC,
    day_change_pct NUMERIC,
    next_earnings_date DATE,
    last_earnings_date DATE,
    last_earnings_surprise_pct NUMERIC,
    ex_dividend_date DATE,
    fifty_two_week_high NUMERIC,
    fifty_two_week_low NUMERIC,
    currency TEXT,
    last_updated TIMESTAMPTZ DEFAULT now()
);

-- Row-Level Security: net als je andere tabellen, maar deze tabel heeft
-- geen user_email om op te filteren (het is gedeelde, publieke data).
-- Iedereen (de app + het sync-script, beide via dezelfde anon-sleutel)
-- mag lezen EN schrijven -- er zit geen persoonlijke informatie in.
ALTER TABLE ticker_market_data ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read ticker market data"
    ON ticker_market_data FOR SELECT
    USING (true);

CREATE POLICY "Anyone can write ticker market data"
    ON ticker_market_data FOR ALL
    USING (true)
    WITH CHECK (true);

-- Index op last_updated -- handig om snel te checken hoe vers de data is
-- (bv. voor een 'laatst bijgewerkt'-tijdstempel in de UI).
CREATE INDEX IF NOT EXISTS idx_ticker_market_data_last_updated
    ON ticker_market_data (last_updated);
