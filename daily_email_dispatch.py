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

VALID_REGIONS = ["EU", "US_East", "US_West"]


def get_supabase_client():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_ANON_KEY"]
    return create_client(url, key)


def get_all_preferences() -> dict:
    """Geeft de e-mail-voorkeuren van ALLE gebruikers terug die ooit iets hebben ingesteld."""
    client = get_supabase_client()
    response = client.table("user_preferences").select("*").execute()
    return {row["user_email"]: row for row in response.data}


def run_daily_screener_emails_for_region(preferences: dict, region: str) -> None:
    """Stuurt de dagelijkse screener-mail naar gebruikers die in DEZE regio zitten en opt-in zijn."""
    print(f"\n=== Dagelijkse screener-mails versturen voor regio: {region} ===")
    opted_in = [
        email for email, prefs in preferences.items()
        if prefs.get("wants_daily_email") and prefs.get("email_region", "EU") == region
    ]
    print(f"{len(opted_in)} gebruiker(s) in regio {region} willen de dagelijkse screener-mail ontvangen.")

    if not opted_in:
        return

    if not os.path.exists("supertrend_signals_daily.csv"):
        print("Geen supertrend_signals_daily.csv gevonden -- kan geen mail versturen.")
        return

    df_hits = pd.read_csv("supertrend_signals_daily.csv")
    if df_hits.empty:
        print("Geen signalen vandaag -- toch een korte, warme mail versturen (dagelijks contactmoment).")
        text_body, html_body = screener_daily.build_no_signals_email_daily()
        subject = "Hesty's Daily: a quiet day, no new signals"
        for user_email in opted_in:
            send_email(subject=subject, body_text=text_body, body_html=html_body, to_email=user_email)
        return

    text_body, html_body = screener_daily.build_email_body_daily(df_hits)
    subject = f"Hesty's Daily: {len(df_hits)} new signal(s) today"

    for user_email in opted_in:
        send_email(subject=subject, body_text=text_body, body_html=html_body, to_email=user_email)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in VALID_REGIONS:
        print(f"Gebruik: python daily_email_dispatch.py <regio>, waarbij <regio> een van {VALID_REGIONS} is.")
        sys.exit(1)

    target_region = sys.argv[1]
    all_preferences = get_all_preferences()
    run_daily_screener_emails_for_region(all_preferences, target_region)
    print("\nKlaar.")
