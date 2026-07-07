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
    shares numeric,          -- aantal aandelen/eenheden dat je bezit
    position_value numeric,  -- LAATST BEREKENDE waarde (shares x koers), bijgewerkt via de 'Update'-knop
    created_at timestamp with time zone default now()
);

-- Als je portfolio_holdings AL bestond (van eerder), draai dan ALLEEN
-- deze regels om de nieuwe kolommen toe te voegen, niet de create table hierboven:
-- alter table portfolio_holdings add column shares numeric;
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
    last_price_refresh_at timestamp with time zone,  -- voor de 1x-per-minuut rate-limit op de 'Update waarde'-knop
    updated_at timestamp with time zone default now()
);
