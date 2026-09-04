-- Voegt de 3 kolommen toe die nodig zijn voor watchlist-prijsalerts.
-- Draai dit 1x in de Supabase SQL-editor.

ALTER TABLE portfolio_holdings ADD COLUMN IF NOT EXISTS alert_target_price NUMERIC;
ALTER TABLE portfolio_holdings ADD COLUMN IF NOT EXISTS alert_direction TEXT;
ALTER TABLE portfolio_holdings ADD COLUMN IF NOT EXISTS alert_dismissed BOOLEAN DEFAULT FALSE;
