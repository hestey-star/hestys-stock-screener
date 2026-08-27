"""
Verstuurt de dagelijkse screener-mail aan gebruikers, per regio getimed
(zodat iedereen 'm rond hun eigen ochtend krijgt, i.p.v. 1 vast tijdstip
voor iedereen). Leest de AL bestaande CSV (van de ochtend-scan via
daily_batch.py) -- doet zelf GEEN nieuwe scan, dat zou zonde van de tijd
en API-aanroepen zijn als dit 3x per dag draait (1x per regio).

Bedoeld om te draaien via GitHub Actions (dus GEEN Streamlit-context --
leest configuratie via omgevingsvariabelen).

Benodigde omgevingsvariabelen: SUPABASE_URL, SUPABASE_ANON_KEY,
EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT, EMAIL_ADDRESS, EMAIL_APP_PASSWORD

Gebruik: python daily_email_dispatch.py <regio>
waarbij <regio> een van: EU, US_East, US_West
"""
from __future__ import annotations

import os
import sys

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

import screener_daily
from emailer import send_email
from user_hashing import hash_email

VALID_REGIONS = ["EU", "US_East", "US_West"]


def get_supabase_client():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_ANON_KEY"]
    return create_client(url, key)


def get_all_preferences() -> dict:
    """Geeft de e-mail-voorkeuren van ALLE gebruikers terug (sleutel = gehasht e-mailadres)."""
    client = get_supabase_client()
    response = client.table("user_preferences").select("*").execute()
    return {row["user_email"]: row for row in response.data}


def get_real_email_and_name(email_hash: str) -> tuple:
    """
    Zoekt het echte, verstuurbare e-mailadres ÉN de naam op bij een hash --
    de naam is nodig voor de persoonlijke aanhef ('Good morning, [naam]').
    """
    client = get_supabase_client()
    response = client.table("user_identity").select("email, name").eq("email_hash", email_hash).execute()
    if response.data:
        return response.data[0]["email"], response.data[0].get("name")
    return None, None


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


def _append_unsubscribe_footer(text_body: str, html_body: str, unsubscribe_token: str) -> tuple:
    """
    Voegt een persoonlijke uitschrijflink toe -- alleen voor niet-
    ingelogde abonnees (login-gekoppelde gebruikers beheren hun
    voorkeur via Settings, die hebben geen los token nodig).
    """
    unsubscribe_url = f"https://hestys.streamlit.app/unsubscribe?token={unsubscribe_token}"
    text_with_footer = text_body + f"\n\nUnsubscribe: {unsubscribe_url}"
    html_with_footer = html_body + (
        f'<p style="max-width:600px; margin:12px auto 0 auto; text-align:center; '
        f'font-size:11px; color:#9AA1AC;">'
        f'<a href="{unsubscribe_url}" style="color:#9AA1AC;">Unsubscribe</a></p>'
    )
    return text_with_footer, html_with_footer


def run_daily_screener_emails_for_region(preferences: dict, region: str) -> None:
    """
    Stuurt de dagelijkse screener-mail naar gebruikers die in DEZE regio
    zitten en opt-in zijn -- combineert 2 bronnen (login-gekoppelde
    voorkeuren EN niet-ingelogde abonnees), en dedupliceert op e-mailadres
    zodat iemand die toevallig via BEIDE routes is aangemeld niet 2x mail
    krijgt. Bij overlap wint de login-gekoppelde versie (geen los
    uitschrijf-token nodig, die persoon beheert het via Settings).

    De mail wordt per ontvanger apart opgebouwd (niet 1x gedeeld) --
    ingelogde gebruikers krijgen een persoonlijke aanhef ('Good morning,
    [naam]'), niet-ingelogde abonnees (geen naam bekend) de neutrale versie.
    """
    print(f"\n=== Dagelijkse screener-mails versturen voor regio: {region} ===")

    # --- Bron 1: login-gekoppelde gebruikers ---
    opted_in_hashes = [
        email_hash for email_hash, prefs in preferences.items()
        if prefs.get("wants_daily_email") and prefs.get("email_region", "EU") == region
    ]
    logged_in_recipients = {}  # lowercased e-mail -> {"name": ..., "unsubscribe_token": None}
    for email_hash in opted_in_hashes:
        real_email, name = get_real_email_and_name(email_hash)
        if real_email:
            logged_in_recipients[real_email.strip().lower()] = {"name": name, "unsubscribe_token": None}
        else:
            print(f"  Kon geen e-mailadres vinden voor hash {email_hash[:12]}... -- overgeslagen.")

    # --- Bron 2: niet-ingelogde, bevestigde abonnees (geen naam bekend) ---
    no_login_subs = get_confirmed_email_subscribers(region)
    no_login_recipients = {
        sub["email"].strip().lower(): {"name": None, "unsubscribe_token": sub["unsubscribe_token"]}
        for sub in no_login_subs
    }

    # --- Dedupliceren: bij overlap wint de login-gekoppelde versie (heeft een naam, geen token) ---
    all_recipients = {**no_login_recipients, **logged_in_recipients}
    print(f"{len(logged_in_recipients)} ingelogde gebruiker(s), {len(no_login_recipients)} niet-ingelogde "
          f"abonnee(s) in regio {region} -- {len(all_recipients)} unieke ontvanger(s) na deduplicatie.")

    if not all_recipients:
        return

    if not os.path.exists("supertrend_signals_daily.csv"):
        print("Geen supertrend_signals_daily.csv gevonden -- kan geen mail versturen.")
        return

    df_hits = pd.read_csv("supertrend_signals_daily.csv")
    has_signals = not df_hits.empty
    subject = f"Hesty's Daily: {len(df_hits)} new signal(s) today" if has_signals else "Hesty's Daily: a quiet day, no new signals"

    for email, info in all_recipients.items():
        if has_signals:
            text_body, html_body = screener_daily.build_email_body_daily(df_hits, name=info["name"])
        else:
            text_body, html_body = screener_daily.build_no_signals_email_daily(name=info["name"])
        if info["unsubscribe_token"]:
            text_body, html_body = _append_unsubscribe_footer(text_body, html_body, info["unsubscribe_token"])
        send_email(subject=subject, body_text=text_body, body_html=html_body, to_email=email)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in VALID_REGIONS:
        print(f"Gebruik: python daily_email_dispatch.py <regio>, waarbij <regio> een van {VALID_REGIONS} is.")
        sys.exit(1)

    target_region = sys.argv[1]
    all_preferences = get_all_preferences()
    run_daily_screener_emails_for_region(all_preferences, target_region)
    print("\nKlaar.")
