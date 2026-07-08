-- Plak dit in Supabase's SQL Editor (linkermenu) en klik "Run"
--
-- LET OP over beveiliging: we gebruiken Google-login via Streamlit, niet
-- via Supabase's eigen inlogsysteem. Daarom kunnen we Supabase's
-- rij-beveiliging (Row Level Security) hier niet automatisch aan Google-
-- identiteit koppelen. In plaats daarvan filtert onze Python-code (die
-- ALTIJD server-side draait, nooit zichtbaar voor de browser van de
-- gebruiker) bij elke query expliciet op de ingelogde gebruiker. Dat is
-- voor dit schaalniveau een veilige, gangbare aanpak.

create table portfolio_holdings (
    id bigint generated always as identity primary key,
    user_email text not null,
    naam text not null,
    ticker text not null,
    shares numeric,          -- aantal aandelen/eenheden dat je bezit (NULL bij watchlist-items)
    position_value numeric,  -- LAATST BEREKENDE waarde (shares x koers x wisselkoers), bijgewerkt via de 'Update'-knop
    value_currency text,     -- in welke valuta position_value staat (bv. 'EUR' of 'USD') -- voorkomt verwarring bij het wisselen van weergave-valuta
    is_watchlist boolean not null default false,  -- true = alleen volgen (geen eigendom), false = eigen positie
    created_at timestamp with time zone default now()
);

-- Als je portfolio_holdings AL bestond (van eerder), draai dan ALLEEN
-- deze regels om de nieuwe kolommen toe te voegen, niet de create table hierboven:
-- alter table portfolio_holdings add column shares numeric;
-- alter table portfolio_holdings add column value_currency text;
-- alter table portfolio_holdings add column is_watchlist boolean not null default false;
-- (position_value bestond al van de vorige update)

-- Tijdstempel van de laatste keer dat de waardes zijn bijgewerkt, per
-- gebruiker -- voorkomt spam (max 1x per minuut, zie screener.py-achtige logica)
-- alter table user_preferences add column last_price_refresh_at timestamp with time zone;

-- Index om snel te filteren op e-mailadres
create index idx_portfolio_holdings_user_email on portfolio_holdings (user_email);

-- E-mail-voorkeuren per gebruiker (opt-in voor de wekelijkse screener-mail
-- en/of de persoonlijke portfolio-mail)
create table user_preferences (
    user_email text primary key,
    wants_screener_email boolean not null default false,
    wants_portfolio_email boolean not null default true,
    wants_daily_email boolean not null default false,  -- opt-in voor de dagelijkse screener-mail
    is_premium boolean not null default false,  -- handmatig te zetten totdat er een echt betaalsysteem is (zie punt 5 van de roadmap)
    cash_value numeric,  -- niet-geïnvesteerd kapitaal, voor de cash%-check in de premium-analyse
    stripe_customer_id text,  -- voor het 'Manage subscription'-portaal en de dagelijkse abonnement-check
    investment_horizon text,       -- risicoprofiel-wizard: 'short', 'medium', of 'long'
    risk_tolerance text,           -- risicoprofiel-wizard: 'conservative', 'balanced', of 'aggressive'
    max_position_pct numeric,      -- risicoprofiel-wizard: max % dat je prettig vindt in 1 positie
    max_sector_pct numeric,        -- risicoprofiel-wizard: max % dat je prettig vindt in 1 sector
    target_cash_pct numeric,       -- risicoprofiel-wizard: gewenste cash-buffer %
    last_price_refresh_at timestamp with time zone,  -- voor de rate-limit op de 'Update waarde'-knop
    updated_at timestamp with time zone default now()
);

-- Als je user_preferences AL bestond (van eerder), draai dan ALLEEN deze
-- regels om de nieuwe kolommen toe te voegen:
-- alter table user_preferences add column wants_daily_email boolean not null default false;
-- alter table user_preferences add column is_premium boolean not null default false;
-- alter table user_preferences add column cash_value numeric;
-- alter table user_preferences add column stripe_customer_id text;
-- alter table user_preferences add column investment_horizon text;
-- alter table user_preferences add column risk_tolerance text;
-- alter table user_preferences add column max_position_pct numeric;
-- alter table user_preferences add column max_sector_pct numeric;
-- alter table user_preferences add column target_cash_pct numeric;
