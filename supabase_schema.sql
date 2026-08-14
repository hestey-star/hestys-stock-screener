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
    day_change_pct numeric,  -- dagverandering (%) van de koers, 'gratis' meegenomen bij de refresh (zelfde opgehaalde data)
    is_watchlist boolean not null default false,  -- true = alleen volgen (geen eigendom), false = eigen positie
    created_at timestamp with time zone default now()
);

-- Als je portfolio_holdings AL bestond (van eerder), draai dan ALLEEN
-- deze regel om de nieuwe kolom toe te voegen:
-- alter table portfolio_holdings add column day_change_pct numeric;

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

-- Houdt bij op welke datum de gebruiker de wekelijkse signalen voor het
-- laatst zag -- zodat 'Today's radar' het aantal weekly-signalen alleen
-- toont op de dag dat de wekelijkse scan draaide (of de eerstvolgende
-- keer dat de gebruiker de site daarna opent), niet elke dag opnieuw.
alter table user_preferences add column last_seen_weekly_signals_date date;

-- Koppelt een gehasht e-mailadres terug aan het ECHTE, verstuurbare adres
-- -- de rest van de database (portfolio_holdings, portfolio_transactions,
-- user_preferences, portfolio_score_history) slaat alleen de HASH op, niet
-- het leesbare e-mailadres zelf. Deze tabel is puur nodig om daadwerkelijk
-- mail te kunnen versturen (de dagelijkse/wekelijkse batch-scripts zoeken
-- hier het echte adres op, vlak vóór het versturen).
create table user_identity (
    email_hash text primary key,
    email text not null,
    name text,
    updated_at timestamp with time zone default now()
);

-- Deep-dives: 1 rij per VERSIE (niet per aandeel) -- zo bouw je een
-- geschiedenis op van hoe je kijk op een aandeel is veranderd, i.p.v. een
-- enkele, telkens overschreven notitie. Alle rijen voor dezelfde ticker
-- (van dezelfde gebruiker) vormen samen de "geschiedenis" van dat aandeel.
create table deep_dives (
    id bigint generated always as identity primary key,
    user_email text not null,
    ticker text not null,
    naam text not null,
    created_at timestamp with time zone default now(),
    business_overview text,
    investment_thesis text,
    management_assessment text,
    bear_case text,
    valuation_view text,
    interested_price numeric,
    sell_trigger_price numeric,
    sell_trigger_date date,
    thesis_score numeric(3,1) check (thesis_score between 1 and 10),
    management_score numeric(3,1) check (management_score between 1 and 10),
    bear_case_score numeric(3,1) check (bear_case_score between 1 and 10),
    valuation_score numeric(3,1) check (valuation_score between 1 and 10),
    catalysts_score numeric(3,1) check (catalysts_score between 1 and 10),
    technical_analysis text,
    technical_analysis_score numeric(3,1) check (technical_analysis_score between 1 and 10),
    catalysts text,
    position_sizing_plan text,
    sell_criteria text,
    conclusion text check (conclusion in ('Buy', 'Watch', 'Pass')),
    price_at_creation numeric,
    fifty_two_week_high_at_creation numeric,
    fifty_two_week_low_at_creation numeric,
    market_cap_at_creation numeric,
    sector_at_creation text,
    dividend_yield_at_creation numeric,
    in_own_signals_at_creation text,
    sector_rotation_pct_at_creation numeric
);

-- Niet-ingelogde e-mail-abonnees voor de dagelijkse mail (laagdrempelig,
-- geen account nodig -- alleen e-mailadres + regio). Double opt-in via
-- confirmation_token; uitschrijven via unsubscribe_token, beide
-- willekeurige, unieke strings (geen gok-baar patroon).
create table email_subscribers (
    id bigint generated always as identity primary key,
    email text not null,
    email_region text not null check (email_region in ('EU', 'US_East', 'US_West')),
    confirmed boolean default false,
    confirmation_token text unique not null,
    unsubscribe_token text unique not null,
    subscribed_at timestamp with time zone default now(),
    confirmed_at timestamp with time zone
);
alter table email_subscribers add constraint email_subscribers_email_unique unique (email);

-- Deep-dive-afbeeldingen: meerdere per versie mogelijk (bv. een TA-
-- grafiek, een DAU-screenshot), elk met een eigen bijschrift. De
-- bestanden zelf staan in een Supabase Storage-bucket (aparte SQL
-- hieronder); deze tabel houdt alleen de referentie + het bijschrift bij.
create table deep_dive_images (
    id bigint generated always as identity primary key,
    deep_dive_id bigint not null references deep_dives(id) on delete cascade,
    user_email text not null,
    image_url text not null,
    storage_path text not null,
    caption text,
    uploaded_at timestamp with time zone default now()
);

-- De Storage-bucket zelf -- publiek, want dit is geen gevoelige data en
-- voorkomt dat we ingewikkelde losse RLS-policies moeten opzetten voor
-- een klein, persoonlijk project.
insert into storage.buckets (id, name, public) values ('deep-dive-images', 'deep-dive-images', true);

-- Performance-snapshot: de laatst-berekende Performance-resultaten, zodat
-- een volgend bezoek de pagina INSTANT kan tonen (uit deze tabel) i.p.v.
-- alles opnieuw te moeten berekenen -- verversen gebeurt alleen nog op
-- verzoek (een expliciete 'Refresh'-knop), niet automatisch bij elk bezoek.
create table performance_snapshots (
    user_email text primary key,
    computed_at timestamp with time zone default now(),
    overall_return_pct numeric,
    total_pnl numeric,
    earliest_date date,
    checkpoint_results jsonb,
    value_series jsonb,
    performance_rows jsonb
);
