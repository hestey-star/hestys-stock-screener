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
    created_at timestamp with time zone default now()
);

-- Index om snel te filteren op e-mailadres
create index idx_portfolio_holdings_user_email on portfolio_holdings (user_email);
