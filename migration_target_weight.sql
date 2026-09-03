-- Voegt een target_weight-veld toe aan portfolio_holdings -- het
-- percentage van de portfolio dat je voor deze positie wilt aanhouden.
-- Los, eigen instelbaar per positie (geen koppeling aan een vooraf-
-- gedefinieerde tier-structuur). NULL = geen target ingesteld (positie
-- doet dan niet mee aan rebalancing-suggesties).

ALTER TABLE portfolio_holdings ADD COLUMN IF NOT EXISTS target_weight NUMERIC;
