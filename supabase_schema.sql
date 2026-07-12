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
    wants_momentocrats_email boolean not null default false,  -- opt-in per signaal-type, i.p.v. 1 blanket 'wants_screener_email'
    wants_snowball_email boolean not null default false,
    wants_rocket_email boolean not null default false,
    wants_portfolio_email boolean not null default true,
    wants_daily_email boolean not null default false,  -- opt-in voor de dagelijkse screener-mail
    email_region text not null default 'EU',  -- 'EU', 'US_East', of 'US_West' -- bepaalt om welk lokaal tijdstip de dagelijkse mail aankomt
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
-- alter table user_preferences add column wants_momentocrats_email boolean not null default false;
-- alter table user_preferences add column wants_snowball_email boolean not null default false;
-- alter table user_preferences add column wants_rocket_email boolean not null default false;
-- alter table user_preferences add column email_region text not null default 'EU';
-- alter table user_preferences add column is_premium boolean not null default false;
-- alter table user_preferences add column cash_value numeric;
-- alter table user_preferences add column stripe_customer_id text;
-- alter table user_preferences add column investment_horizon text;
-- alter table user_preferences add column risk_tolerance text;
-- alter table user_preferences add column max_position_pct numeric;
-- alter table user_preferences add column max_sector_pct numeric;
-- alter table user_preferences add column target_cash_pct numeric;

-- Slaat 1 score-snapshot per dag op, per gebruiker -- zodat we op Today
-- kunnen tonen hoe de Portfolio Health Score verandert over tijd (bv.
-- '7.2/10, +0.4 t.o.v. vorige week').
create table portfolio_score_history (
    id bigint generated always as identity primary key,
    user_email text not null,
    date date not null,
    score numeric not null,
    created_at timestamp with time zone default now(),
    unique (user_email, date)  -- voorkomt dubbele snapshots op 1 dag, maakt upsert mogelijk
);

-- Buy/sell-transactiegeschiedenis per positie -- optioneel, alleen
-- gebruikt door wie z'n rendement wil zien (zie Analyze -> Performance).
-- Zodra een positie 1+ transacties heeft, wordt het aantal shares
-- daaruit afgeleid i.p.v. handmatig ingevoerd (voorkomt 2 conflicterende
-- bronnen van waarheid).
create table portfolio_transactions (
    id bigint generated always as identity primary key,
    user_email text not null,
    holding_id bigint not null references portfolio_holdings(id) on delete cascade,
    transaction_type text not null check (transaction_type in ('buy', 'sell')),
    shares numeric not null check (shares > 0),
    price numeric not null check (price >= 0),
    fee numeric not null default 0 check (fee >= 0),
    transaction_date date not null,
    created_at timestamp with time zone default now()
);

-- ISIN opslaan bij een positie (indien bekend, bv. via een broker-import)
-- -- zodat een LATERE herimport van dezelfde broker een eerder gekozen
-- ticker automatisch herkent en hergebruikt, zonder opnieuw te moeten
-- zoeken/kiezen.
alter table portfolio_holdings add column isin text;
