"""
Wekelijks batch-script: draait de gedeelde screener EN stuurt elke
geregistreerde gebruiker een persoonlijke e-mail over hun eigen portfolio.

Bedoeld om te draaien via GitHub Actions (dus GEEN Streamlit-context --
leest configuratie via omgevingsvariabelen, niet via st.secrets zoals
het dashboard zelf doet).

Benodigde omgevingsvariabelen (als GitHub Actions secrets, of lokaal in .env):
  SUPABASE_URL, SUPABASE_ANON_KEY
  EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT, EMAIL_ADDRESS, EMAIL_APP_PASSWORD

Gebruik: python weekly_batch.py
"""
from __future__ import annotations

import os

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

import screener
from portfolio_watch import check_holding, build_email_body
from emailer import send_email


def get_supabase_client():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_ANON_KEY"]
    return create_client(url, key)


def get_all_users_with_holdings() -> dict:
    """Geeft alle gebruikers en hun posities terug, gegroepeerd per e-mailadres."""
    client = get_supabase_client()
    response = client.table("portfolio_holdings").select("*").execute()

    grouped: dict[str, list[dict]] = {}
    for row in response.data:
        grouped.setdefault(row["user_email"], []).append(row)
    return grouped


def run_screener_shared() -> None:
    """Draait de gedeelde screener 1x -- de resultaten zijn voor iedereen zichtbaar."""
    print("=== Gedeelde screener draaien (publiek, voor iedereen zichtbaar) ===")
    screener.main()


def run_portfolio_emails() -> None:
    """Checkt en mailt elke geregistreerde gebruiker zijn eigen, persoonlijke portfolio."""
    print("\n=== Persoonlijke portfolio-e-mails versturen ===")
    users = get_all_users_with_holdings()
    print(f"{len(users)} gebruiker(s) gevonden met een portfolio.")

    for user_email, holdings in users.items():
        print(f"\n--- {user_email} ({len(holdings)} positie(s)) ---")
        results = []
        for holding in holdings:
            result = check_holding(holding["naam"], holding["ticker"])
            if result:
                results.append(result)

        if not results:
            print("  Geen van de posities kon gecheckt worden -- geen mail verstuurd.")
            continue

        df = pd.DataFrame(results)
        text_body, html_body = build_email_body(df)
        n_changed = int(df["recent_gewijzigd"].sum())
        subject = (
            f"Portfolio Watch: {n_changed} wijziging(en)"
            if n_changed > 0 else "Portfolio Watch: geen wijzigingen"
        )

        send_email(subject=subject, body_text=text_body, body_html=html_body, to_email=user_email)


if __name__ == "__main__":
    run_screener_shared()
    run_portfolio_emails()
    print("\nKlaar.")
