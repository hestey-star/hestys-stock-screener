-- Nieuwe tabel voor de Dividend-pagina. Run dit 1x in Supabase's SQL editor
-- (Project -> SQL Editor -> New query -> plakken -> Run) VOORDAT je de
-- nieuwe dashboard.py/database.py live zet, anders faalt elke CSV-import
-- met dividend-rijen (database.add_dividend_income() verwacht deze tabel).

create table if not exists dividend_income (
    id bigint generated always as identity primary key,
    user_email text not null,          -- gehasht, zelfde patroon als portfolio_transactions
    ticker text not null,
    naam text,
    amount numeric not null,           -- in de ORIGINELE/native valuta van de bron
    currency text not null default 'USD',
    payout_date date not null,
    source text not null,              -- 'robinhood' | 'schwab' | 'trade_republic' | 'degiro'
    imported_at timestamptz not null default now()
);

create index if not exists dividend_income_user_email_idx on dividend_income (user_email);
