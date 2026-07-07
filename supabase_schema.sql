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
    position_value numeric,  -- huidige waarde van de positie in EUR, voor concentratie-risico-berekening (optioneel, mag leeg zijn)
    created_at timestamp with time zone default now()
);

-- Als je portfolio_holdings AL bestond (van eerder), draai dan ALLEEN
-- deze regel om de nieuwe kolom toe te voegen, niet de create table hierboven:
-- alter table portfolio_holdings add column position_value numeric;

-- Index om snel te filteren op e-mailadres
create index idx_portfolio_holdings_user_email on portfolio_holdings (user_email);

-- E-mail-voorkeuren per gebruiker (opt-in voor de wekelijkse screener-mail
-- en/of de persoonlijke portfolio-mail)
create table user_preferences (
    user_email text primary key,
    wants_screener_email boolean not null default false,
    wants_portfolio_email boolean not null default true,
    updated_at timestamp with time zone default now()
);
