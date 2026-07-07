"""
Database-laag: leest en schrijft gebruikers-portfolio's in Supabase.

Filtert ALTIJD op user_email in de Python-code zelf (zie supabase_schema.sql
voor de uitleg waarom dit hier gebeurt i.p.v. via Supabase's eigen
rij-beveiliging -- we gebruiken Google-login via Streamlit, niet Supabase's
eigen inlogsysteem, dus die twee kunnen we niet automatisch koppelen).
"""
from __future__ import annotations

import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["anon_key"]
    return create_client(url, key)


def get_user_holdings(user_email: str) -> list[dict]:
    """Geeft alle posities van deze specifieke gebruiker terug."""
    client = get_supabase_client()
    response = client.table("portfolio_holdings").select("*").eq("user_email", user_email).execute()
    return response.data


def add_holding(user_email: str, naam: str, ticker: str, shares: float = None) -> None:
    """Voegt een nieuwe positie toe voor deze gebruiker, optioneel met het aantal aandelen/eenheden."""
    client = get_supabase_client()
    client.table("portfolio_holdings").insert({
        "user_email": user_email,
        "naam": naam,
        "ticker": ticker,
        "shares": shares,
        "position_value": None,  # wordt pas gevuld na de eerste 'Update waarde'-klik
    }).execute()


def update_holding_value(holding_id: int, user_email: str, position_value: float) -> None:
    """Werkt de LAATST BEREKENDE waarde van 1 positie bij (shares x actuele koers)."""
    client = get_supabase_client()
    client.table("portfolio_holdings").update({"position_value": position_value}) \
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
    Geeft de e-mail-voorkeuren van deze gebruiker terug. Als er nog geen
    rij bestaat (nieuwe gebruiker), gelden de standaardwaarden: WEL de
    persoonlijke portfolio-mail, NIET de bredere screener-mail (opt-in).
    """
    client = get_supabase_client()
    response = client.table("user_preferences").select("*").eq("user_email", user_email).execute()
    if response.data:
        return response.data[0]
    return {"user_email": user_email, "wants_screener_email": False, "wants_portfolio_email": True}


def set_user_preferences(user_email: str, wants_screener_email: bool, wants_portfolio_email: bool) -> None:
    """Slaat de e-mail-voorkeuren op (maakt een nieuwe rij aan, of werkt de bestaande bij)."""
    client = get_supabase_client()
    client.table("user_preferences").upsert({
        "user_email": user_email,
        "wants_screener_email": wants_screener_email,
        "wants_portfolio_email": wants_portfolio_email,
    }).execute()


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
