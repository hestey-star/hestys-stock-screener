"""
Database-laag: leest en schrijft gebruikers-portfolio's in Supabase.

Filtert ALTIJD op user_email in de Python-code zelf (zie supabase_schema.sql
voor de uitleg waarom dit hier gebeurt i.p.v. via Supabase's eigen
rij-beveiliging -- we gebruiken Google-login via Streamlit, niet Supabase's
eigen inlogsysteem, dus die twee kunnen we niet automatisch koppelen).

PRIVACY: elke functie hasht het e-mailadres intern (via hash_email()) vóórdat
het als sleutel in de database wordt gebruikt. Dat betekent: wie rechtstreeks
in de Supabase-tabellen kijkt (bv. tijdens het debuggen van iets heel anders)
ziet een betekenisloze hash i.p.v. een naam/e-mailadres -- geen toevallige
blik meer op wiens data dit is. De functies zelf blijven gewoon het ECHTE
e-mailadres als input verwachten (zoals Streamlit's login dat geeft) -- de
aanroepers in dashboard.py hoeven dus niet te veranderen.

Voor het daadwerkelijk VERSTUREN van mail (waar je het echte adres wel weer
nodig hebt) bestaat een aparte, kleine 'user_identity'-tabel die hash <-> echt
adres onthoudt -- zie ensure_user_identity() en get_real_email().
"""
from __future__ import annotations

import math
import hashlib
import os
import secrets
from datetime import datetime, timedelta

import streamlit as st
from supabase import create_client, Client

from user_hashing import hash_email


@st.cache_resource
def get_supabase_client() -> Client:
    """
    Haalt de Supabase-credentials op -- via st.secrets wanneer dit ECHT
    binnen een draaiende Streamlit-app gebeurt (de live site), of via
    omgevingsvariabelen wanneer dit bestand wordt aangeroepen vanuit een
    los script BUITEN Streamlit (bv. weekly_batch.py/daily_batch.py via
    GitHub Actions -- daar bestaat geen secrets.toml-bestand, wat
    st.secrets anders laat crashen met 'No secrets found').

    Deze fallback voorkomt structureel het probleem dat de wekelijkse
    Portfolio Watch-mail liet crashen: get_roic_trend_history() (in dit
    bestand) wordt ook vanuit weekly_batch.py aangeroepen, maar gebruikte
    tot nu toe ALLEEN st.secrets via deze functie.
    """
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["anon_key"]
    except Exception:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_ANON_KEY"]
    return create_client(url, key)


def _hash_password(password: str) -> str:
    """
    Hasht een wachtwoord met scrypt -- Python's ingebouwde, voor
    wachtwoorden bedoelde hash-functie (traag met opzet, i.t.t. bv.
    sha256, wat brute-force-aanvallen bemoeilijkt). Geen extra
    dependency nodig. Geeft 1 string terug met salt+hash samengevoegd
    (hex, gescheiden door ':'), zodat 1 kolom volstaat.
    """
    salt = os.urandom(16)
    hashed = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f"{salt.hex()}:{hashed.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    """
    Controleert een ingevoerd wachtwoord tegen de opgeslagen salt+hash.
    secrets.compare_digest() i.p.v. == voorkomt een timing-aanval (bij ==
    zou een aanvaller uit de reactietijd kunnen afleiden hoeveel tekens
    er al kloppen).
    """
    try:
        salt_hex, hash_hex = stored.split(":")
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32)
        return secrets.compare_digest(actual, expected)
    except Exception:
        return False


def sign_up_with_password(email: str, name: str, password: str) -> tuple[bool, str]:
    """
    Maakt een nieuw account aan met e-mail+wachtwoord, of voegt een
    wachtwoord toe aan een bestaande, via Google aangemaakte identiteit
    (1 account, 2 inlogmethodes -- zelfde e-mailadres, dus dezelfde hash,
    dus dezelfde portfolio/voorkeuren, ongeacht hoe je binnenkomt).

    Geeft (False, reden) terug als er al een wachtwoord is ingesteld voor
    dit e-mailadres (voorkomt per ongeluk overschrijven van een bestaand
    account).
    """
    client = get_supabase_client()
    email_hash = hash_email(email)
    existing = client.table("user_identity").select("password_hash").eq("email_hash", email_hash).execute()
    if existing.data and existing.data[0].get("password_hash"):
        return False, "An account with this email already has a password set. Try signing in instead."

    client.table("user_identity").upsert({
        "email_hash": email_hash,
        "email": email,
        "name": name,
        "password_hash": _hash_password(password),
    }, on_conflict="email_hash").execute()
    return True, "Account created!"


def verify_password_login(email: str, password: str) -> tuple[bool, str]:
    """
    Controleert een e-mail+wachtwoord-combinatie. Geeft (True, echte naam)
    terug bij succes, of (False, foutmelding) terug bij een verkeerd
    e-mailadres/wachtwoord OF een account dat nog geen wachtwoord heeft
    ingesteld (bv. een puur-Google-account) -- BEWUST dezelfde,
    algemene foutmelding voor beide gevallen, zodat een aanvaller niet
    kan afleiden welke e-mailadressen wel/niet bestaan.
    """
    client = get_supabase_client()
    email_hash = hash_email(email)
    response = client.table("user_identity").select("password_hash,name").eq("email_hash", email_hash).execute()
    generic_error = "No account found with this email and password."
    if not response.data or not response.data[0].get("password_hash"):
        return False, generic_error
    stored_hash = response.data[0]["password_hash"]
    if _verify_password(password, stored_hash):
        return True, response.data[0].get("name") or email.split("@")[0]
    return False, generic_error


def ensure_user_identity(email: str, name: str = None) -> None:
    """
    Legt de koppeling hash <-> echt e-mailadres vast (of werkt 'm bij) --
    nodig om later daadwerkelijk mail te kunnen sturen, want de rest van
    de database slaat voortaan alleen de hash op. Veilig om bij elk
    paginabezoek van een ingelogde gebruiker aan te roepen (idempotent).
    """
    client = get_supabase_client()
    client.table("user_identity").upsert({
        "email_hash": hash_email(email),
        "email": email,
        "name": name,
    }, on_conflict="email_hash").execute()


def get_real_email(email_hash: str) -> str:
    """
    Zoekt het echte e-mailadres op bij een hash -- alleen gebruikt om
    daadwerkelijk mail te kunnen versturen (in de batch-scripts), niet
    door de normale app-functies zelf.
    """
    client = get_supabase_client()
    response = client.table("user_identity").select("email").eq("email_hash", email_hash).execute()
    if response.data:
        return response.data[0]["email"]
    return None


def create_session_token(email: str, days_valid: int = 30) -> str:
    """
    Maakt een nieuwe, willekeurige sessie-token aan voor deze gebruiker
    en slaat 'm op met een vervaldatum -- wordt in een browser-cookie
    gezet zodat een paginaverversing je niet meteen uitlogt (in
    tegenstelling tot de kale st.session_state, die dat wel doet).
    """
    client = get_supabase_client()
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now() + timedelta(days=days_valid)).isoformat()
    client.table("auth_sessions").insert({
        "token": token,
        "email_hash": hash_email(email),
        "expires_at": expires_at,
    }).execute()
    return token


def get_user_from_session_token(token: str):
    """
    Zoekt (e-mailadres, naam) op bij een sessie-token, mits nog geldig
    (niet verlopen). Geeft None terug als de token niet bestaat OF
    verlopen is -- in beide gevallen betekent dat: niet ingelogd.
    """
    if not token:
        return None
    client = get_supabase_client()
    response = client.table("auth_sessions").select("email_hash,expires_at").eq("token", token).execute()
    if not response.data:
        return None
    row = response.data[0]
    if datetime.fromisoformat(row["expires_at"]) < datetime.now():
        return None
    identity = client.table("user_identity").select("email,name").eq("email_hash", row["email_hash"]).execute()
    if not identity.data:
        return None
    return identity.data[0]["email"], identity.data[0].get("name")


def delete_session_token(token: str) -> None:
    """Verwijdert een sessie-token (bij uitloggen -- voorkomt dat een oude cookie nog geldig zou blijven)."""
    if not token:
        return
    client = get_supabase_client()
    client.table("auth_sessions").delete().eq("token", token).execute()


def create_password_reset_token(email: str):
    """
    Maakt een wachtwoord-reset-token aan, MAAR ALLEEN als er
    daadwerkelijk een account MET een wachtwoord bestaat voor dit
    e-mailadres. Geeft None terug als dat niet zo is -- de aanroepende
    code toont ALTIJD dezelfde, algemene bevestiging aan de gebruiker
    (ongeacht of er echt een mail verstuurd is), zodat een aanvaller niet
    kan afleiden welke e-mailadressen wel/niet een account hebben.
    """
    client = get_supabase_client()
    email_hash = hash_email(email)
    existing = client.table("user_identity").select("password_hash").eq("email_hash", email_hash).execute()
    if not existing.data or not existing.data[0].get("password_hash"):
        return None
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now() + timedelta(hours=1)).isoformat()
    client.table("user_identity").upsert({
        "email_hash": email_hash,
        "password_reset_token": token,
        "password_reset_expires_at": expires_at,
    }, on_conflict="email_hash").execute()
    return token


def reset_password_with_token(token: str, new_password: str) -> tuple[bool, str]:
    """
    Zet een nieuw wachtwoord, mits de reset-token geldig en niet verlopen
    is (1 uur geldigheid). De token wordt na gebruik meteen gewist, zodat
    'ie niet nogmaals gebruikt kan worden.
    """
    client = get_supabase_client()
    response = client.table("user_identity").select("email_hash,password_reset_expires_at").eq("password_reset_token", token).execute()
    if not response.data:
        return False, "This reset link is invalid or has already been used."
    row = response.data[0]
    if not row.get("password_reset_expires_at") or datetime.fromisoformat(row["password_reset_expires_at"]) < datetime.now():
        return False, "This reset link has expired. Please request a new one."
    client.table("user_identity").update({
        "password_hash": _hash_password(new_password),
        "password_reset_token": None,
        "password_reset_expires_at": None,
    }).eq("email_hash", row["email_hash"]).execute()
    return True, "Password updated! You can now sign in with your new password."


def get_user_holdings(user_email: str, is_watchlist: bool = False) -> list[dict]:
    """Geeft alle EIGEN posities (is_watchlist=False) of alle WATCHLIST-items (True) van deze gebruiker terug."""
    client = get_supabase_client()
    response = client.table("portfolio_holdings").select("*") \
        .eq("user_email", hash_email(user_email)).eq("is_watchlist", is_watchlist).execute()
    return response.data


def add_holding(user_email: str, naam: str, ticker: str, shares: float = None, is_watchlist: bool = False, isin: str = None) -> int:
    """Voegt een nieuwe positie toe (eigen positie, of alleen watchlist als is_watchlist=True). Geeft de nieuwe id terug."""
    client = get_supabase_client()
    response = client.table("portfolio_holdings").insert({
        "user_email": hash_email(user_email),
        "naam": naam,
        "ticker": ticker,
        "shares": shares,
        "position_value": None,  # wordt pas gevuld na de eerste 'Update waarde'-klik
        "is_watchlist": is_watchlist,
        "isin": isin,
    }).execute()
    return response.data[0]["id"]


def update_holding_shares(holding_id: int, user_email: str, shares: float) -> None:
    """Wijzigt het aantal shares/eenheden van een bestaande positie (zonder verwijderen+opnieuw-toevoegen)."""
    client = get_supabase_client()
    client.table("portfolio_holdings").update({"shares": shares}) \
        .eq("id", holding_id).eq("user_email", hash_email(user_email)).execute()


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
        "user_email": hash_email(user_email),
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
        .eq("user_email", hash_email(user_email))
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
        .eq("user_email", hash_email(user_email))
        .order("transaction_date", desc=False)
        .execute()
    )
    grouped: dict = {}
    for tx in (response.data or []):
        grouped.setdefault(tx["holding_id"], []).append(tx)
    return grouped


def delete_transaction(transaction_id: int, user_email: str) -> None:
    """Verwijdert 1 transactie (bv. per ongeluk verkeerd ingevoerd)."""
    client = get_supabase_client()
    client.table("portfolio_transactions").delete() \
        .eq("id", transaction_id).eq("user_email", hash_email(user_email)).execute()


def update_holding_value(holding_id: int, user_email: str, position_value: float, value_currency: str = "EUR", day_change_pct: float = None) -> None:
    """Werkt de LAATST BEREKENDE waarde van 1 positie bij (shares x actuele koers x wisselkoers), inclusief in welke valuta die staat, en de dagverandering (%) -- 'gratis' meegenomen bij dezelfde refresh."""
    client = get_supabase_client()
    update_data = {"position_value": position_value, "value_currency": value_currency}
    if day_change_pct is not None:
        update_data["day_change_pct"] = day_change_pct
    client.table("portfolio_holdings").update(update_data) \
        .eq("id", holding_id).eq("user_email", hash_email(user_email)).execute()


def delete_holding(holding_id: int, user_email: str) -> None:
    """
    Verwijdert een positie. Filtert OOK op user_email als extra
    veiligheidslaag (voorkomt dat iemand een ID van een ander zou kunnen
    raden en diens positie verwijderen).
    """
    client = get_supabase_client()
    client.table("portfolio_holdings").delete().eq("id", holding_id).eq("user_email", hash_email(user_email)).execute()


def get_last_price_refresh(user_email: str):
    """Geeft het tijdstip van de laatste waarde-update terug (of None als nog nooit gedaan)."""
    client = get_supabase_client()
    response = client.table("user_preferences").select("last_price_refresh_at").eq("user_email", hash_email(user_email)).execute()
    if response.data and response.data[0].get("last_price_refresh_at"):
        return response.data[0]["last_price_refresh_at"]
    return None


def set_last_price_refresh(user_email: str, timestamp_iso: str) -> None:
    """Slaat het tijdstip van de zojuist uitgevoerde waarde-update op (voor de rate-limit)."""
    client = get_supabase_client()
    client.table("user_preferences").upsert({
        "user_email": hash_email(user_email),
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
    hashed = hash_email(user_email)
    response = client.table("user_preferences").select("*").eq("user_email", hashed).execute()
    if response.data:
        return response.data[0]
    return {
        "user_email": hashed, "wants_portfolio_email": True,
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
        "user_email": hash_email(user_email),
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
        "user_email": hash_email(user_email),
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
        "user_email": hash_email(user_email),
        "is_premium": is_premium,
    }).execute()


def set_stripe_customer_id(user_email: str, stripe_customer_id: str) -> None:
    """Onthoudt welke Stripe-klant bij dit e-mailadres hoort (voor het portaal en de dagelijkse abonnement-check)."""
    client = get_supabase_client()
    client.table("user_preferences").upsert({
        "user_email": hash_email(user_email),
        "stripe_customer_id": stripe_customer_id,
    }).execute()


def get_stripe_customer_id(user_email: str):
    prefs = get_user_preferences(user_email)
    return prefs.get("stripe_customer_id")


def get_all_premium_users_with_stripe_id() -> list:
    """
    Voor de dagelijkse abonnement-check: alle premium-gebruikers die een
    Stripe-klant-ID hebben. LET OP: 'user_email' in het resultaat is de
    HASH (niet het leesbare adres) -- gebruik get_real_email() als je
    het echte adres nodig hebt (bv. om een mail te sturen), en geef de
    hash gewoon door aan set_premium_status() (die herkent 'm via het
    veiligheidsnet in hash_email() en hasht 'm niet nog een keer).
    """
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
        "user_email": hash_email(user_email),
        "cash_value": cash_value,
    }).execute()


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
        "user_email": hash_email(user_email),
        "investment_horizon": investment_horizon,
        "risk_tolerance": risk_tolerance,
        "max_position_pct": max_position_pct,
        "max_sector_pct": max_sector_pct,
        "target_cash_pct": target_cash_pct,
    }).execute()


def reset_risk_profile(user_email: str) -> None:
    """Zet het risicoprofiel terug naar de standaardwaarden."""
    set_risk_profile(user_email, **DEFAULT_RISK_PROFILE)


def get_last_seen_weekly_signals_date(user_email: str) -> str:
    """Geeft de datum terug waarop deze gebruiker de weekly-signalen voor het laatst zag (of None)."""
    client = get_supabase_client()
    response = (
        client.table("user_preferences")
        .select("last_seen_weekly_signals_date")
        .eq("user_email", hash_email(user_email))
        .execute()
    )
    if response.data:
        return response.data[0].get("last_seen_weekly_signals_date")
    return None


def set_last_seen_weekly_signals_date(user_email: str, date_str: str) -> None:
    """
    Markeert dat deze gebruiker de weekly-signalen van 'date_str' heeft
    gezien -- upsert, want de rij bestaat mogelijk nog niet als de
    gebruiker nog nooit eerdere voorkeuren heeft opgeslagen.
    """
    client = get_supabase_client()
    client.table("user_preferences").upsert({
        "user_email": hash_email(user_email),
        "last_seen_weekly_signals_date": date_str,
    }, on_conflict="user_email").execute()


def save_score_snapshot(user_email: str, score: float) -> None:
    """
    Slaat de Portfolio Health Score van vandaag op -- idempotent (overschrijft
    gewoon als er al een snapshot van vandaag bestaat, dankzij de unique-
    constraint op user_email+date). Veilig om bij elk paginabezoek aan te roepen.
    """
    client = get_supabase_client()
    today = datetime.now().date().isoformat()
    client.table("portfolio_score_history").upsert({
        "user_email": hash_email(user_email),
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
        .eq("user_email", hash_email(user_email))
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
    Geeft ALLE gebruikers en hun posities terug, gegroepeerd per (gehasht)
    e-mailadres. Gebruikt door het wekelijkse geplande script (niet door
    het dashboard zelf) om iedereen een persoonlijke e-mail te kunnen
    sturen -- de sleutels hier zijn hashes, gebruik get_real_email() om
    het echte adres op te zoeken vóór het versturen.
    """
    client = get_supabase_client()
    response = client.table("portfolio_holdings").select("*").execute()

    grouped: dict[str, list[dict]] = {}
    for row in response.data:
        grouped.setdefault(row["user_email"], []).append(row)
    return grouped


def add_deep_dive(
    user_email: str, ticker: str, naam: str,
    business_overview: str = None, investment_thesis: str = None,
    management_assessment: str = None,
    bear_case: str = None, valuation_view: str = None,
    interested_price: float = None, catalysts: str = None,
    position_sizing_plan: str = None, sell_criteria: str = None,
    conclusion: str = None, market_snapshot: dict = None,
    sell_trigger_price: float = None, sell_trigger_date: str = None,
    thesis_score: int = None, management_score: int = None,
    bear_case_score: int = None, valuation_score: int = None,
    catalysts_score: int = None,
    technical_analysis: str = None, technical_analysis_score: int = None,
) -> int:
    """
    Slaat een NIEUWE versie van een deep-dive op (nooit overschrijven --
    elke keer een nieuwe rij, zodat je kijk-verandering over tijd
    zichtbaar blijft). Geeft de nieuwe id terug.

    'market_snapshot' (optioneel): de automatisch aangeleverde marktdata
    op het moment van opslaan (prijs, 52wk-hi/lo, marktkap, sector,
    dividendrendement, signalen-kruisverband, sector-rotatie) -- een
    'foto op dat moment', zodat oude versies hun eigen, destijds-geldige
    cijfers bewaren i.p.v. steeds de HUIDIGE cijfers te tonen.

    'sell_trigger_price'/'sell_trigger_date' (optioneel): automatisch te
    checken verkoop-triggers -- komen terug op Today zodra de prijs dat
    niveau bereikt, of die datum is aangebroken. 'sell_criteria' (los,
    vrije tekst) blijft de plek voor een GEBEURTENIS-trigger (bv. 'als ze
    2 kwartalen missen') -- dat kunnen we niet automatisch verifiëren,
    dus dat blijft een handmatig te checken herinnering op deze pagina.

    '*_score' (optioneel, 1-10): een cijfer per oordeel-onderdeel, ALTIJD
    in dezelfde richting ('hoger = gunstiger voor een koopbeslissing') --
    dus ook bear_case_score: hoog = de risico's zijn goed te overzien,
    niet 'de risico's zijn ernstig'. Het gemiddelde van de ingevulde
    scores geeft een totaalcijfer per deep-dive.
    """
    client = get_supabase_client()
    row = {
        "user_email": hash_email(user_email),
        "ticker": ticker,
        "naam": naam,
        "business_overview": business_overview,
        "investment_thesis": investment_thesis,
        "management_assessment": management_assessment,
        "bear_case": bear_case,
        "valuation_view": valuation_view,
        "interested_price": interested_price,
        "catalysts": catalysts,
        "position_sizing_plan": position_sizing_plan,
        "sell_criteria": sell_criteria,
        "conclusion": conclusion,
        "sell_trigger_price": sell_trigger_price,
        "sell_trigger_date": sell_trigger_date,
        "thesis_score": thesis_score,
        "management_score": management_score,
        "bear_case_score": bear_case_score,
        "valuation_score": valuation_score,
        "catalysts_score": catalysts_score,
        "technical_analysis": technical_analysis,
        "technical_analysis_score": technical_analysis_score,
    }
    if market_snapshot:
        row.update(market_snapshot)
    response = client.table("deep_dives").insert(row).execute()
    return response.data[0]["id"]


def get_deep_dives_for_ticker(user_email: str, ticker: str) -> list:
    """Geeft alle versies voor 1 ticker terug, meest recente eerst."""
    client = get_supabase_client()
    response = (
        client.table("deep_dives")
        .select("*")
        .eq("user_email", hash_email(user_email))
        .eq("ticker", ticker)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def get_all_deep_dive_tickers(user_email: str) -> list:
    """
    Geeft 1 samenvattend overzicht terug -- per ticker de MEEST RECENTE
    versie (voor de overzichtslijst), gesorteerd op laatst bijgewerkt.
    """
    client = get_supabase_client()
    response = (
        client.table("deep_dives")
        .select("*")
        .eq("user_email", hash_email(user_email))
        .order("created_at", desc=True)
        .execute()
    )
    latest_per_ticker = {}
    for row in (response.data or []):
        if row["ticker"] not in latest_per_ticker:
            latest_per_ticker[row["ticker"]] = row
    return sorted(latest_per_ticker.values(), key=lambda r: r["created_at"], reverse=True)


def delete_deep_dive(deep_dive_id: int, user_email: str) -> None:
    """Verwijdert 1 specifieke versie (bv. per ongeluk aangemaakt)."""
    client = get_supabase_client()
    client.table("deep_dives").delete().eq("id", deep_dive_id).eq("user_email", hash_email(user_email)).execute()


def update_deep_dive(deep_dive_id: int, user_email: str, **fields) -> None:
    """
    Werkt EEN BESTAANDE versie bij (i.p.v. een nieuwe toe te voegen) --
    voor het corrigeren van een typefout, of het aanvullen van een enkel
    onderdeel zonder alle andere velden opnieuw te moeten uitschrijven.
    Dit is bewust iets anders dan add_deep_dive(): dat maakt een NIEUWE,
    aparte 'kijk op dit moment'-versie, dit past de HUIDIGE versie aan.
    """
    client = get_supabase_client()
    client.table("deep_dives").update(fields).eq("id", deep_dive_id).eq("user_email", hash_email(user_email)).execute()


def add_email_subscriber(email: str, region: str) -> tuple:
    """
    Meldt een e-mailadres aan voor de dagelijkse mail, ZONDER account.
    Slaat een ONBEVESTIGDE rij op met een uniek bevestigings- en
    uitschrijftoken, en geeft BEIDE terug (voor de bevestigingsmail,
    die ook meteen een uitschrijflink bevat). Als het adres al bestaat
    (bv. iemand vult 2x hetzelfde adres in), wordt de bestaande rij
    bijgewerkt (nieuwe regio, nieuwe tokens) i.p.v. een dubbele rij.
    """
    import secrets
    client = get_supabase_client()
    confirmation_token = secrets.token_urlsafe(32)
    unsubscribe_token = secrets.token_urlsafe(32)
    client.table("email_subscribers").upsert({
        "email": email.strip().lower(),
        "email_region": region,
        "confirmed": False,
        "confirmation_token": confirmation_token,
        "unsubscribe_token": unsubscribe_token,
    }, on_conflict="email").execute()
    return confirmation_token, unsubscribe_token


def confirm_email_subscriber(confirmation_token: str) -> bool:
    """Bevestigt een e-mail-abonnement via het token uit de bevestigingsmail. Geeft False terug als het token onbekend is."""
    client = get_supabase_client()
    response = client.table("email_subscribers").select("id").eq("confirmation_token", confirmation_token).execute()
    if not response.data:
        return False
    client.table("email_subscribers").update({
        "confirmed": True,
        "confirmed_at": datetime.now().isoformat(),
    }).eq("confirmation_token", confirmation_token).execute()
    return True


def unsubscribe_email_subscriber(unsubscribe_token: str) -> bool:
    """Meldt een e-mailadres af via het token uit de mail zelf. Geeft False terug als het token onbekend is."""
    client = get_supabase_client()
    response = client.table("email_subscribers").select("id").eq("unsubscribe_token", unsubscribe_token).execute()
    if not response.data:
        return False
    client.table("email_subscribers").delete().eq("unsubscribe_token", unsubscribe_token).execute()
    return True


def get_confirmed_email_subscribers(region: str) -> list:
    """Geeft alle BEVESTIGDE, niet-ingelogde abonnees voor deze regio terug (email + unsubscribe_token)."""
    client = get_supabase_client()
    response = (
        client.table("email_subscribers")
        .select("email, unsubscribe_token")
        .eq("email_region", region)
        .eq("confirmed", True)
        .execute()
    )
    return response.data or []


def upload_deep_dive_image(
    user_email: str, deep_dive_id: int, file_bytes: bytes, filename: str,
    content_type: str, caption: str = None,
) -> str:
    """
    Uploadt een afbeelding naar Supabase Storage en legt een referentie
    (+ bijschrift) vast in deep_dive_images. Geeft de publieke URL terug.
    Een unieke bestandsnaam (met een willekeurige component) voorkomt dat
    2 uploads met dezelfde oorspronkelijke bestandsnaam elkaar overschrijven.
    """
    import uuid
    client = get_supabase_client()
    unique_filename = f"{deep_dive_id}_{uuid.uuid4().hex}_{filename}"
    client.storage.from_("deep-dive-images").upload(
        unique_filename, file_bytes, {"content-type": content_type}
    )
    public_url = client.storage.from_("deep-dive-images").get_public_url(unique_filename)
    client.table("deep_dive_images").insert({
        "deep_dive_id": deep_dive_id,
        "user_email": hash_email(user_email),
        "image_url": public_url,
        "storage_path": unique_filename,
        "caption": caption,
    }).execute()
    return public_url


def get_deep_dive_images(deep_dive_id: int) -> list:
    """Geeft alle afbeeldingen voor 1 specifieke deep-dive-versie terug, oudste eerst."""
    client = get_supabase_client()
    response = (
        client.table("deep_dive_images")
        .select("*")
        .eq("deep_dive_id", deep_dive_id)
        .order("uploaded_at")
        .execute()
    )
    return response.data or []


def delete_deep_dive_image(image_id: int, user_email: str) -> None:
    """Verwijdert een afbeelding -- zowel het bestand uit Storage als de database-rij."""
    client = get_supabase_client()
    hashed_email = hash_email(user_email)
    response = (
        client.table("deep_dive_images")
        .select("storage_path")
        .eq("id", image_id)
        .eq("user_email", hashed_email)
        .execute()
    )
    if response.data:
        storage_path = response.data[0]["storage_path"]
        try:
            client.storage.from_("deep-dive-images").remove([storage_path])
        except Exception:
            pass  # het bestand is mogelijk al weg -- de database-rij verwijderen we hoe dan ook
    client.table("deep_dive_images").delete().eq("id", image_id).eq("user_email", hashed_email).execute()


def get_performance_snapshot(user_email: str) -> dict:
    """
    Haalt de laatst opgeslagen Performance-snapshot op (indien aanwezig)
    -- gebruikt om de Performance-pagina INSTANT te tonen i.p.v. bij elk
    bezoek alles opnieuw (traag) te herberekenen.
    """
    client = get_supabase_client()
    hashed_email = hash_email(user_email)
    response = client.table("performance_snapshots").select("*").eq("user_email", hashed_email).execute()
    return response.data[0] if response.data else None


def save_performance_snapshot(
    user_email: str, overall_return_pct: float, total_pnl: float,
    earliest_date: str, checkpoint_results: list, value_series: list, performance_rows: list,
) -> None:
    """Slaat een nieuwe Performance-snapshot op (overschrijft de vorige -- we bewaren alleen de laatste)."""
    client = get_supabase_client()
    hashed_email = hash_email(user_email)
    client.table("performance_snapshots").upsert({
        "user_email": hashed_email,
        "computed_at": datetime.now().isoformat(),
        "overall_return_pct": overall_return_pct,
        "total_pnl": total_pnl,
        "earliest_date": earliest_date,
        "checkpoint_results": checkpoint_results,
        "value_series": value_series,
        "performance_rows": performance_rows,
    }).execute()


def get_roic_trend_history(tickers: list) -> dict:
    """
    Haalt de LAATST BEKENDE ROIC-trend EN fair-value-status per ticker op
    (van de vorige Portfolio Watch-run) -- gebruikt om te bepalen of een
    signalering deze week ECHT NIEUW is, i.p.v. elke week opnieuw dezelfde,
    al-langer-bekende stand te tonen. Per TICKER bijgehouden (niet per
    gebruiker) -- deze waardes zijn voor iedereen hetzelfde, dus geen zin
    om ze per gebruiker te dupliceren.

    Geeft per ticker een dict terug: {'roic_trend': ..., 'fair_value_bucket': ...}
    """
    if not tickers:
        return {}
    client = get_supabase_client()
    response = (
        client.table("roic_trend_history")
        .select("ticker,last_roic_trend,last_fair_value_bucket")
        .in_("ticker", tickers)
        .execute()
    )
    return {
        row["ticker"]: {"roic_trend": row["last_roic_trend"], "fair_value_bucket": row.get("last_fair_value_bucket")}
        for row in response.data
    }


def save_roic_trend_history(ticker_states: dict) -> None:
    """
    Slaat de HUIDIGE ROIC-trend EN fair-value-status per ticker op, als
    'vorige stand' voor de volgende Portfolio Watch-run.

    ticker_states: {ticker: {'roic_trend': ..., 'fair_value_bucket': ...}}
    """
    if not ticker_states:
        return
    client = get_supabase_client()

    def _clean(value):
        """
        NaN (bv. van een pandas-kolom waar de berekening niet lukte --
        zoals bij een ticker met te weinig historische data) kan niet
        naar JSON: Supabase's upsert crasht daar anders op met 'Out of
        range float values are not JSON compliant: nan'. Zet 'm om naar
        None (wordt keurig JSON null).
        """
        if isinstance(value, float) and math.isnan(value):
            return None
        return value

    rows = [
        {
            "ticker": ticker, "last_roic_trend": _clean(state.get("roic_trend")),
            "last_fair_value_bucket": _clean(state.get("fair_value_bucket")),
            "last_checked_at": datetime.now().isoformat(),
        }
        for ticker, state in ticker_states.items()
    ]
    client.table("roic_trend_history").upsert(rows, on_conflict="ticker").execute()


def get_last_csv_import(user_email: str) -> dict | None:
    """
    Geeft tijdstip + bestandsnaam van de laatste broker-CSV-import terug
    (of None als nog nooit gedaan) -- zelfde patroon als
    get_last_price_refresh(), maar dan voor de 'Import from a broker'-
    functie.
    """
    client = get_supabase_client()
    response = (
        client.table("user_preferences")
        .select("last_csv_import_at,last_csv_import_filename")
        .eq("user_email", hash_email(user_email))
        .execute()
    )
    if response.data and response.data[0].get("last_csv_import_at"):
        return {
            "timestamp": response.data[0]["last_csv_import_at"],
            "filename": response.data[0].get("last_csv_import_filename"),
        }
    return None


def set_last_csv_import(user_email: str, timestamp_iso: str, filename: str) -> None:
    """Slaat tijdstip + bestandsnaam van een zojuist afgeronde broker-CSV-import op."""
    client = get_supabase_client()
    client.table("user_preferences").upsert({
        "user_email": hash_email(user_email),
        "last_csv_import_at": timestamp_iso,
        "last_csv_import_filename": filename,
    }).execute()
