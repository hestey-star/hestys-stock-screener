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


def get_all_preferences() -> dict:
    """Geeft de e-mail-voorkeuren van ALLE gebruikers terug die ooit iets hebben ingesteld."""
    client = get_supabase_client()
    response = client.table("user_preferences").select("*").execute()
    return {row["user_email"]: row for row in response.data}


def run_screener_shared() -> None:
    """
    Draait de gedeelde screener 1x -- de resultaten (CSV's, incl. Snowball
    Signal en Rocket List) zijn voor iedereen zichtbaar op de website.
    send_own_email=False, want de vaste mail naar het eigen GitHub-
    secrets-adres zou dubbel op kunnen tellen met de per-gebruiker-opt-in-
    mail hieronder (run_weekly_signals_emails) als dat hetzelfde adres is.
    """
    print("=== Gedeelde screener draaien (publiek, voor iedereen zichtbaar) ===")
    screener.main(send_own_email=False)


def _format_momentocrats_row(row) -> str:
    return (f"[score {row['score']}] {row['ticker']}: flipped {row['weken_geleden']} week(en) ago "
            f"({row['sinds_omslag_pct']:+.2f}% since)")


def _format_snowball_row(row) -> str:
    return (f"{row['ticker']}: ROIC {row['roic_pct']:.1f}%, "
            f"{row['afwijking_fair_value_pct']:+.1f}% vs. fair value")


def _format_rocket_row(row) -> str:
    return (f"{row['ticker']}: {row['groei_pct']:.1f}% growth, "
            f"{row['relatieve_sterkte']:+.1f}% relative strength")


SIGNAL_TYPES = {
    "momentocrats": {
        "pref_key": "wants_momentocrats_email", "csv": "supertrend_signals.csv",
        "title": "Momentocrats", "emoji": "📡", "sort_by": "score", "sort_asc": False,
        "formatter": _format_momentocrats_row,
    },
    "snowball": {
        "pref_key": "wants_snowball_email", "csv": "snowball_signals.csv",
        "title": "Snowballers", "emoji": "🐦", "sort_by": "afwijking_fair_value_pct", "sort_asc": True,
        "formatter": _format_snowball_row,
    },
    "rocket": {
        "pref_key": "wants_rocket_email", "csv": "rocket_list_signals.csv",
        "title": "Rocket List", "emoji": "🚀", "sort_by": "groei_pct", "sort_asc": False,
        "formatter": _format_rocket_row,
    },
}


def build_weekly_signals_email(sections: list, is_premium: bool = False) -> tuple:
    """
    Bouwt 1 gecombineerde mail voor alle signaal-types die deze gebruiker
    heeft aangevinkt -- top 3 (gratis) of ALLES (premium) per type, in
    Hesty's stijl (zelfde opmaak-taal als de dagelijkse mail).

    sections: lijst van dicts met keys 'title', 'emoji', 'df', 'formatter'.
    """
    display_limit = None if is_premium else 3  # None = pandas .head(None) geeft alles terug
    text_lines = ["Good morning from Hesty's -- your weekly signals are in.", ""]
    html_sections_list = []

    for section in sections:
        total_this_section = len(section["df"])
        top_n = section["df"].head(display_limit)
        shown_label = "all" if is_premium else f"top {len(top_n)}"
        text_lines.append(f"{section['emoji']} {section['title']} ({total_this_section} total, showing {shown_label}):")
        for _, row in top_n.iterrows():
            text_lines.append(f"  - {section['formatter'](row)}")
        text_lines.append("")

        rows_html = "".join(
            f"<li style='padding:4px 0;color:#101825;'>{section['formatter'](row)}</li>"
            for _, row in top_n.iterrows()
        )
        html_sections_list.append(f"""
        <h4 style="color:#101825; font-size:16px; margin:20px 0 8px 0;">{section['emoji']} {section['title']}</h4>
        <ul style="margin:0; padding-left:20px; font-size:14px;">{rows_html}</ul>
        """)

    if not is_premium:
        text_lines.append("🔒 You're seeing the free top 3 per signal. Upgrade to Premium to see everything.")
        text_lines.append("")

    text_lines += [
        "See the full lists, sector rotation, and top movers under Discover on the site.",
        "",
        "-- Hesty's, your personal investment assistant",
        "",
        "This is a screener, not investment advice.",
    ]
    text_body = "\n".join(text_lines)

    upgrade_hint_html = (
        """<p style="margin-top:16px; font-size:13px; color:#5B6472; background:#F5F7F9; padding:10px 14px; border-radius:8px;">
            &#128274; You're seeing the free top 3 per signal. Upgrade to Premium to see everything.
        </p>"""
        if not is_premium else ""
    )

    html_body = f"""
    <div style="font-family: -apple-system, 'Segoe UI', Roboto, Arial, sans-serif; max-width: 600px; margin: 0 auto; background:#ffffff;">
        <div style="background:#101825; padding: 28px 24px; border-radius: 12px 12px 0 0;">
            <div style="color:#1FAE96; font-size:13px; font-weight:600; letter-spacing:1px; text-transform:uppercase;">Hesty's Weekly</div>
            <div style="color:#EAEDF1; font-size:22px; font-weight:700; margin-top:4px;">Your weekly signals are in</div>
        </div>
        <div style="padding: 24px; border: 1px solid #E5E8EC; border-top: none; border-radius: 0 0 12px 12px;">
            {''.join(html_sections_list)}
            {upgrade_hint_html}
            <p style="margin-top:20px; font-size:14px; color:#5B6472; line-height:1.5;">
                See the full lists, sector rotation, and top movers under
                <a href="https://hestys-stock-screener.streamlit.app/?view=discover" style="color:#1FAE96; font-weight:600; text-decoration:none;">Discover</a> on the site.
            </p>
            <p style="margin-top:24px; font-size:14px; color:#101825; font-weight:600;">&mdash; Hesty's, your personal investment assistant</p>
            <p style="margin-top:16px; font-size:12px; color:#9AA1AC; font-style:italic;">This is a screener, not investment advice.</p>
        </div>
    </div>
    """
    return text_body, html_body


def run_weekly_signals_emails(preferences: dict) -> None:
    """
    Stuurt 1 gecombineerde mail per gebruiker, met alleen de signaal-types
    waar diegene zich voor heeft aangemeld (top 3 gratis / top 10 premium).
    """
    print("\n=== Wekelijkse signalen-mails versturen aan opt-in-gebruikers ===")

    # Laad elke CSV maar 1x, niet per gebruiker opnieuw
    csv_cache = {}
    for key, config in SIGNAL_TYPES.items():
        if os.path.exists(config["csv"]):
            df = pd.read_csv(config["csv"])
            if not df.empty:
                df = df.sort_values(config["sort_by"], ascending=config["sort_asc"])
                csv_cache[key] = df

    for user_email, prefs in preferences.items():
        sections = []
        for key, config in SIGNAL_TYPES.items():
            if not prefs.get(config["pref_key"]):
                continue
            if key not in csv_cache:
                continue
            sections.append({
                "title": config["title"], "emoji": config["emoji"],
                "df": csv_cache[key], "formatter": config["formatter"],
            })

        if not sections:
            continue

        is_premium = bool(prefs.get("is_premium", False))
        print(f"  {user_email} ({'premium' if is_premium else 'free'}): {', '.join(s['title'] for s in sections)}")
        text_body, html_body = build_weekly_signals_email(sections, is_premium=is_premium)
        total_signals = sum(len(s["df"]) for s in sections)
        subject = f"Hesty's Weekly: {total_signals} new signal(s) this week"
        send_email(subject=subject, body_text=text_body, body_html=html_body, to_email=user_email)


def run_portfolio_emails(preferences: dict) -> None:
    """
    Checkt en mailt elke geregistreerde gebruiker zijn eigen, persoonlijke
    portfolio -- behalve als hij dat expliciet heeft uitgezet. Standaard AAN
    (ook voor gebruikers die nog nooit hun voorkeuren hebben aangepast).
    """
    print("\n=== Persoonlijke portfolio-e-mails versturen ===")
    users = get_all_users_with_holdings()
    print(f"{len(users)} gebruiker(s) gevonden met een portfolio.")

    for user_email, holdings in users.items():
        user_prefs = preferences.get(user_email, {})
        if not user_prefs.get("wants_portfolio_email", True):
            print(f"\n--- {user_email}: heeft de portfolio-mail uitgezet, overgeslagen ---")
            continue

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
    all_preferences = get_all_preferences()
    run_weekly_signals_emails(all_preferences)
    run_portfolio_emails(all_preferences)
    print("\nKlaar.")
