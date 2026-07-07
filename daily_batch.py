"""
Dagelijks batch-script: draait de dagelijkse screener en stuurt de mail
naar elke gebruiker die zich daarvoor heeft aangemeld (wants_daily_email).
Analoog aan weekly_batch.py, maar voor de dagelijkse screener-variant.

Bedoeld om te draaien via GitHub Actions (dus GEEN Streamlit-context --
leest configuratie via omgevingsvariabelen).

Benodigde omgevingsvariabelen: SUPABASE_URL, SUPABASE_ANON_KEY,
EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT, EMAIL_ADDRESS, EMAIL_APP_PASSWORD

Gebruik: python daily_batch.py
"""
from __future__ import annotations

import os

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

import screener_daily
from emailer import send_email


def get_supabase_client():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_ANON_KEY"]
    return create_client(url, key)


def get_all_preferences() -> dict:
    """Geeft de e-mail-voorkeuren van ALLE gebruikers terug die ooit iets hebben ingesteld."""
    client = get_supabase_client()
    response = client.table("user_preferences").select("*").execute()
    return {row["user_email"]: row for row in response.data}


def run_daily_screener_emails(preferences: dict) -> None:
    """Stuurt de dagelijkse screener-mail naar gebruikers die zich daar expliciet voor hebben aangemeld."""
    print("\n=== Dagelijkse screener-mails versturen aan opt-in-gebruikers ===")
    opted_in = [email for email, prefs in preferences.items() if prefs.get("wants_daily_email")]
    print(f"{len(opted_in)} gebruiker(s) willen de dagelijkse screener-mail ontvangen.")

    if not opted_in:
        return

    if not os.path.exists("supertrend_signals_daily.csv"):
        print("Geen supertrend_signals_daily.csv gevonden -- kan geen mail versturen.")
        return

    df_hits = pd.read_csv("supertrend_signals_daily.csv")
    if df_hits.empty:
        print("Geen signalen vandaag -- geen mail nodig.")
        return

    text_body, html_body = screener_daily.build_email_body_daily(df_hits)
    subject = f"Daily screener: {len(df_hits)} new signals"

    for user_email in opted_in:
        send_email(subject=subject, body_text=text_body, body_html=html_body, to_email=user_email)


if __name__ == "__main__":
    # send_own_email=False: de per-gebruiker-opt-in hieronder dekt dit al,
    # en voorkomt een dubbele mail als het eigen adres ook is aangemeld
    # (zelfde reden als bij weekly_batch.py voor de wekelijkse screener)
    screener_daily.main(send_own_email=False)
    all_preferences = get_all_preferences()
    run_daily_screener_emails(all_preferences)
    print("\nKlaar.")
