"""
Database-laag: leest en schrijft gebruikers-portfolio's in Supabase.

Filtert ALTIJD op user_email in de Python-code zelf (zie supabase_schema.sql
voor de uitleg waarom dit hier gebeurt i.p.v. via Supabase's eigen
rij-beveiliging -- we gebruiken Google-login via Streamlit, niet Supabase's
eigen inlogsysteem, dus die twee kunnen we niet automatisch koppelen).
"""
from __future__ import annotations

from datetime import datetime, timedelta

import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["anon_key"]
    return create_client(url, key)


def get_user_holdings(user_email: str, is_watchlist: bool = False) -> list[dict]:
    """Geeft alle EIGEN posities (is_watchlist=False) of alle WATCHLIST-items (True) van deze gebruiker terug."""
    client = get_supabase_client()
    response = client.table("portfolio_holdings").select("*") \
        .eq("user_email", user_email).eq("is_watchlist", is_watchlist).execute()
    return response.data


def add_holding(user_email: str, naam: str, ticker: str, shares: float = None, is_watchlist: bool = False) -> None:
    """Voegt een nieuwe positie toe (eigen positie, of alleen watchlist als is_watchlist=True)."""
    client = get_supabase_client()
    client.table("portfolio_holdings").insert({
        "user_email": user_email,
        "naam": naam,
        "ticker": ticker,
        "shares": shares,
        "position_value": None,  # wordt pas gevuld na de eerste 'Update waarde'-klik
        "is_watchlist": is_watchlist,
    }).execute()


def update_holding_shares(holding_id: int, user_email: str, shares: float) -> None:
    """Wijzigt het aantal shares/eenheden van een bestaande positie (zonder verwijderen+opnieuw-toevoegen)."""
    client = get_supabase_client()
    client.table("portfolio_holdings").update({"shares": shares}) \
        .eq("id", holding_id).eq("user_email", user_email).execute()


def add_transaction(
    user_email: str, holding_id: int, transaction_type: str,
    shares: float, price: float, fee: float, transaction_date: str,
) -> None:
    """
    Logt 1 buy/sell-transactie voor een positie. Filtert ALTIJD op
    user_email (zie de module-docstring voor waarom dit hier gebeurt).
    """
    client = get_supabase_client()
    client.table("portfolio_transactions").insert({
        "user_email": user_email,
        "holding_id": holding_id,
        "transaction_type": transaction_type,
        "shares": shares,
        "price": price,
        "fee": fee,
        "transaction_date": transaction_date,
    }).execute()


def get_transactions_for_holding(user_email: str, holding_id: int) -> list:
    """Geeft alle transacties voor 1 positie terug, oudste eerst."""
    client = get_supabase_client()
    response = (
        client.table("portfolio_transactions")
        .select("*")
        .eq("user_email", user_email)
        .eq("holding_id", holding_id)
        .order("transaction_date", desc=False)
        .execute()
    )
    return response.data or []


def get_all_transactions(user_email: str) -> dict:
    """Geeft ALLE transacties van een gebruiker terug, gegroepeerd per holding_id."""
    client = get_supabase_client()
    response = (
        client.table("portfolio_transactions")
        .select("*")
        .eq("user_email", user_email)
        .order("transaction_date", desc=False)
        .execute()
    )
    grouped: dict = {}
    for tx in (response.data or []):
        grouped.setdefault(tx["holding_id"], []).append(tx)
    return grouped


def update_holding_value(holding_id: int, user_email: str, position_value: float, value_currency: str = "EUR") -> None:
    """Werkt de LAATST BEREKENDE waarde van 1 positie bij (shares x actuele koers x wisselkoers), inclusief in welke valuta die staat."""
    client = get_supabase_client()
    client.table("portfolio_holdings").update({"position_value": position_value, "value_currency": value_currency}) \
        .eq("id", holding_id).eq("user_email", user_email).execute()


def delete_holding(holding_id: int, user_email: str) -> None:
    """
    Verwijdert een positie. Filtert OOK op user_email als extra
    veiligheidslaag (voorkomt dat iemand een ID van een ander zou kunnen
    raden en diens positie verwijderen).
    """
    client = get_supabase_client()
    client.table("portfolio_holdings").delete().eq("id", holding_id).eq("user_email", user_email).execute()


def get_last_price_refresh(user_email: str):
    """Geeft het tijdstip van de laatste waarde-update terug (of None als nog nooit gedaan)."""
    client = get_supabase_client()
    response = client.table("user_preferences").select("last_price_refresh_at").eq("user_email", user_email).execute()
    if response.data and response.data[0].get("last_price_refresh_at"):
        return response.data[0]["last_price_refresh_at"]
    return None


def set_last_price_refresh(user_email: str, timestamp_iso: str) -> None:
    """Slaat het tijdstip van de zojuist uitgevoerde waarde-update op (voor de rate-limit)."""
    client = get_supabase_client()
    client.table("user_preferences").upsert({
        "user_email": user_email,
        "last_price_refresh_at": timestamp_iso,
    }).execute()


def get_user_preferences(user_email: str) -> dict:
    """
    Geeft de e-mail-voorkeuren (en premium-status) van deze gebruiker terug.
    Als er nog geen rij bestaat (nieuwe gebruiker), gelden de
    standaardwaarden: WEL de persoonlijke portfolio-mail, NIET de
    signaal-mails (allemaal opt-in, per type), GEEN premium, EU als regio.
    """
    client = get_supabase_client()
    response = client.table("user_preferences").select("*").eq("user_email", user_email).execute()
    if response.data:
        return response.data[0]
    return {
        "user_email": user_email, "wants_portfolio_email": True,
        "wants_daily_email": False, "is_premium": False, "email_region": "EU",
        "wants_momentocrats_email": False, "wants_snowball_email": False, "wants_rocket_email": False,
    }


def set_user_preferences(
    user_email: str, wants_portfolio_email: bool,
    wants_daily_email: bool = False, email_region: str = "EU",
    wants_momentocrats_email: bool = False, wants_snowball_email: bool = False,
    wants_rocket_email: bool = False,
) -> None:
    """Slaat de e-mail-voorkeuren op (maakt een nieuwe rij aan, of werkt de bestaande bij)."""
    client = get_supabase_client()
    client.table("user_preferences").upsert({
        "user_email": user_email,
        "wants_portfolio_email": wants_portfolio_email,
        "wants_daily_email": wants_daily_email,
        "email_region": email_region,
        "wants_momentocrats_email": wants_momentocrats_email,
        "wants_snowball_email": wants_snowball_email,
        "wants_rocket_email": wants_rocket_email,
    }).execute()


def set_signal_email_preference(user_email: str, signal_key: str, value: bool) -> None:
    """
    Zet 1 losse signaal-mail-voorkeur (bv. vanaf de Discover-pagina zelf,
    zonder de andere voorkeuren te moeten meesturen).
    """
    valid_keys = {"wants_momentocrats_email", "wants_snowball_email", "wants_rocket_email"}
    if signal_key not in valid_keys:
        raise ValueError(f"Onbekende signaal-sleutel: {signal_key}")
    client = get_supabase_client()
    client.table("user_preferences").upsert({
        "user_email": user_email,
        signal_key: value,
    }).execute()


def is_premium_user(user_email: str, ignore_free_for_all: bool = False) -> bool:
    """
    Handmatig te zetten (via Supabase) totdat er een echt betaalsysteem is.

    ignore_free_for_all: zet op True voor content die ECHT premium moet
    blijven, ook tijdens de 'iedereen premium'-testfase (bv. de download
    van het Smart DCA-script -- eenmaal weggegeven, krijg je 'm niet
    terug, in tegenstelling tot bv. extra rijen in een signalenlijst).
    """
    # Tijdelijke schakelaar (via secrets.toml) om EVERYONE als premium te
    # behandelen -- handig zolang Stripe nog in test-modus staat en je
    # eerst tractie wil opbouwen, voordat er daadwerkelijk afgerekend kan
    # worden. Terugzetten: verwijder de regel of zet 'm op false.
    if not ignore_free_for_all:
        try:
            if st.secrets.get("app", {}).get("premium_free_for_all", False):
                return True
        except Exception:
            pass
    prefs = get_user_preferences(user_email)
    return bool(prefs.get("is_premium", False))


def set_premium_status(user_email: str, is_premium: bool) -> None:
    """Zet de premium-status, aangeroepen nadat een Stripe-betaling geverifieerd is."""
    client = get_supabase_client()
    client.table("user_preferences").upsert({
        "user_email": user_email,
        "is_premium": is_premium,
    }).execute()


def set_stripe_customer_id(user_email: str, stripe_customer_id: str) -> None:
    """Onthoudt welke Stripe-klant bij dit e-mailadres hoort (voor het portaal en de dagelijkse abonnement-check)."""
    client = get_supabase_client()
    client.table("user_preferences").upsert({
        "user_email": user_email,
        "stripe_customer_id": stripe_customer_id,
    }).execute()


def get_stripe_customer_id(user_email: str):
    prefs = get_user_preferences(user_email)
    return prefs.get("stripe_customer_id")


def get_all_premium_users_with_stripe_id() -> list:
    """Voor de dagelijkse abonnement-check: alle premium-gebruikers die een Stripe-klant-ID hebben."""
    client = get_supabase_client()
    response = client.table("user_preferences").select("user_email, stripe_customer_id") \
        .eq("is_premium", True).execute()
    return [row for row in response.data if row.get("stripe_customer_id")]


def get_cash_value(user_email: str) -> float:
    """Geeft het opgeslagen, niet-geïnvesteerde kapitaal terug (0.0 als nog niet ingesteld)."""
    prefs = get_user_preferences(user_email)
    return float(prefs.get("cash_value") or 0.0)


def set_cash_value(user_email: str, cash_value: float) -> None:
    client = get_supabase_client()
    client.table("user_preferences").upsert({
        "user_email": user_email,
        "cash_value": cash_value,
    }).execute()


# Standaardwaarden -- exact gelijk aan de eerder hardgecodeerde grenzen, dus
# niemands analyse verandert totdat ze zelf de wizard invullen.
DEFAULT_RISK_PROFILE = {
    "investment_horizon": "medium",
    "risk_tolerance": "balanced",
    "max_position_pct": 25.0,
    "max_sector_pct": 40.0,
    "target_cash_pct": 10.0,
}


def get_risk_profile(user_email: str) -> dict:
    """Geeft het risicoprofiel terug (wizard-antwoorden), met verstandige standaardwaarden."""
    prefs = get_user_preferences(user_email)
    profile = dict(DEFAULT_RISK_PROFILE)
    for key in DEFAULT_RISK_PROFILE:
        if prefs.get(key) is not None:
            profile[key] = prefs[key]
    return profile


def set_risk_profile(
    user_email: str, investment_horizon: str, risk_tolerance: str,
    max_position_pct: float, max_sector_pct: float, target_cash_pct: float,
) -> None:
    client = get_supabase_client()
    client.table("user_preferences").upsert({
        "user_email": user_email,
        "investment_horizon": investment_horizon,
        "risk_tolerance": risk_tolerance,
        "max_position_pct": max_position_pct,
        "max_sector_pct": max_sector_pct,
        "target_cash_pct": target_cash_pct,
    }).execute()


def reset_risk_profile(user_email: str) -> None:
    """Zet het risicoprofiel terug naar de standaardwaarden."""
    set_risk_profile(user_email, **DEFAULT_RISK_PROFILE)


def save_score_snapshot(user_email: str, score: float) -> None:
    """
    Slaat de Portfolio Health Score van vandaag op -- idempotent (overschrijft
    gewoon als er al een snapshot van vandaag bestaat, dankzij de unique-
    constraint op user_email+date). Veilig om bij elk paginabezoek aan te roepen.
    """
    client = get_supabase_client()
    today = datetime.now().date().isoformat()
    client.table("portfolio_score_history").upsert({
        "user_email": user_email,
        "date": today,
        "score": score,
    }, on_conflict="user_email,date").execute()


def get_score_days_ago(user_email: str, days_ago: int = 7) -> float:
    """
    Geeft de meest recente opgeslagen score terug van OP OF VOOR 'days_ago'
    dagen geleden (niet exact op de dag, want er is niet altijd een
    snapshot van precies die datum). Geeft None terug als er niets is.
    """
    client = get_supabase_client()
    target_date = (datetime.now().date() - timedelta(days=days_ago)).isoformat()
    response = (
        client.table("portfolio_score_history")
        .select("score")
        .eq("user_email", user_email)
        .lte("date", target_date)
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    if response.data:
        return float(response.data[0]["score"])
    return None


def get_all_users_with_holdings() -> dict[str, list[dict]]:
    """
    Geeft ALLE gebruikers en hun posities terug, gegroepeerd per e-mailadres.
    Gebruikt door het wekelijkse geplande script (niet door het dashboard
    zelf) om iedereen een persoonlijke e-mail te kunnen sturen.
    """
    client = get_supabase_client()
    response = client.table("portfolio_holdings").select("*").execute()

    grouped: dict[str, list[dict]] = {}
    for row in response.data:
        grouped.setdefault(row["user_email"], []).append(row)
    return grouped
