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
from database import get_roic_trend_history, save_roic_trend_history
from emailer import send_email


def get_supabase_client():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_ANON_KEY"]
    return create_client(url, key)


def get_real_email(email_hash: str) -> str:
    """
    Zoekt het echte, verstuurbare e-mailadres op bij een hash -- nodig
    omdat portfolio_holdings/user_preferences alleen de hash kennen, niet
    het leesbare adres zelf (zie database.py's module-docstring).
    """
    client = get_supabase_client()
    response = client.table("user_identity").select("email").eq("email_hash", email_hash).execute()
    if response.data:
        return response.data[0]["email"]
    return None


def get_all_users_with_holdings() -> dict:
    """
    Geeft alle gebruikers en hun ACTIEVE, EIGEN posities terug, gegroepeerd
    per (gehasht) e-mailadres. Filtert expliciet op is_watchlist=false EN
    shares > 0 -- zonder deze filters kwamen watchlist-items en al-
    verkochte posities (shares=0, blijven soms als rij staan i.p.v.
    verwijderd) ook mee in de Portfolio Watch-mail, wat precies de bron
    was van 'ik krijg info over posities die ik al verkocht heb'.
    """
    client = get_supabase_client()
    response = (
        client.table("portfolio_holdings")
        .select("*")
        .eq("is_watchlist", False)
        .gt("shares", 0)
        .execute()
    )

    grouped: dict[str, list[dict]] = {}
    for row in response.data:
        grouped.setdefault(row["user_email"], []).append(row)
    return grouped


def get_all_preferences() -> dict:
    """Geeft de e-mail-voorkeuren van ALLE gebruikers terug (sleutel = gehasht e-mailadres)."""
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


def build_weekly_signals_email(sections: list, is_premium: bool = False, daily_flips_text: str = "", daily_flips_html: str = "") -> tuple:
    """
    Bouwt 1 gecombineerde mail voor alle signaal-types die deze gebruiker
    heeft aangevinkt, plus (optioneel) vrijdag's dagelijkse flips.

    Toont altijd top 3 per signaal, OOK voor premium -- een mail met
    tientallen regels per signaal is geen prettige samenvatting meer,
    dat is precies waar Discover (met een scrollbare tabel) voor is.
    De 'is_premium'-parameter blijft bestaan voor later (zodra premium
    functioneel is), maar beïnvloedt de mail-inhoud nu bewust niet.

    sections: lijst van dicts met keys 'title', 'emoji', 'df', 'formatter'.
    daily_flips_text/daily_flips_html: optioneel, van build_daily_flips_section() --
    leeg als er niks te melden was (dan wordt deze sectie gewoon overgeslagen).
    """
    display_limit = 3
    text_lines = ["Good morning from Hesty's -- your weekly signals are in.", ""]
    html_sections_list = []

    for section in sections:
        total_this_section = len(section["df"])
        top_n = section["df"].head(display_limit)
        text_lines.append(f"{section['emoji']} {section['title']} (top {len(top_n)} of {total_this_section} total):")
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

    if daily_flips_text:
        text_lines.append(daily_flips_text)
    if daily_flips_html:
        html_sections_list.append(daily_flips_html)

    text_lines += [
        "See the full lists, sector rotation, and top movers under Discover on the site.",
        "",
        "-- Hesty's, your personal investment assistant",
        "",
        "This is a screener, not investment advice.",
    ]
    text_body = "\n".join(text_lines)

    html_body = f"""
    <div style="font-family: -apple-system, 'Segoe UI', Roboto, Arial, sans-serif; max-width: 600px; margin: 0 auto; background:#ffffff;">
        <div style="background:#101825; padding: 28px 24px; border-radius: 12px 12px 0 0;">
            <div style="color:#1FAE96; font-size:13px; font-weight:600; letter-spacing:1px; text-transform:uppercase;">Hesty's Weekly</div>
            <div style="color:#EAEDF1; font-size:22px; font-weight:700; margin-top:4px;">Your weekly signals are in</div>
        </div>
        <div style="padding: 24px; border: 1px solid #E5E8EC; border-top: none; border-radius: 0 0 12px 12px;">
            {''.join(html_sections_list)}
            <p style="margin-top:20px; font-size:14px; color:#5B6472; line-height:1.5;">
                See the full lists, sector rotation, and top movers under
                <a href="https://hestys.streamlit.app/?view=discover" style="color:#1FAE96; font-weight:600; text-decoration:none;">Discover</a> on the site.
            </p>
            <p style="margin-top:24px; font-size:14px; color:#101825; font-weight:600;">&mdash; Hesty's, your personal investment assistant</p>
            <p style="margin-top:16px; font-size:12px; color:#9AA1AC; font-style:italic;">This is a screener, not investment advice.</p>
        </div>
    </div>
    """
    return text_body, html_body


def run_weekly_signals_emails(preferences: dict, daily_flips_text: str = "", daily_flips_html: str = "") -> None:
    """
    Stuurt 1 gecombineerde mail per gebruiker, met alleen de signaal-types
    waar diegene zich voor heeft aangemeld (top 3 gratis / top 10 premium),
    plus (optioneel) vrijdag's dagelijkse flips erbij.

    daily_flips_text/daily_flips_html: alleen toegevoegd aan mails die
    sowieso al verstuurd worden (dus gebruikers met minstens 1 signaal-
    type aangevinkt) -- geen nieuwe categorie gebruikers die anders
    niks zouden ontvangen.
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

    for user_email_hash, prefs in preferences.items():
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

        real_email = get_real_email(user_email_hash)
        if not real_email:
            print(f"  Kon geen e-mailadres vinden voor hash {user_email_hash[:12]}... -- overgeslagen.")
            continue

        is_premium = bool(prefs.get("is_premium", False))
        print(f"  {real_email} ({'premium' if is_premium else 'free'}): {', '.join(s['title'] for s in sections)}")
        text_body, html_body = build_weekly_signals_email(
            sections, is_premium=is_premium,
            daily_flips_text=daily_flips_text, daily_flips_html=daily_flips_html,
        )
        total_signals = sum(len(s["df"]) for s in sections)
        subject = f"Hesty's Weekly: {total_signals} new signal(s) this week"
        send_email(subject=subject, body_text=text_body, body_html=html_body, to_email=real_email)


def run_portfolio_emails(preferences: dict) -> None:
    """
    Checkt en mailt elke geregistreerde gebruiker zijn eigen, persoonlijke
    portfolio -- behalve als hij dat expliciet heeft uitgezet. Standaard AAN
    (ook voor gebruikers die nog nooit hun voorkeuren hebben aangepast).
    """
    print("\n=== Persoonlijke portfolio-e-mails versturen ===")
    users = get_all_users_with_holdings()
    print(f"{len(users)} gebruiker(s) gevonden met een portfolio.")

    for user_email_hash, holdings in users.items():
        user_prefs = preferences.get(user_email_hash, {})
        if not user_prefs.get("wants_portfolio_email", True):
            print(f"\n--- {user_email_hash[:12]}...: heeft de portfolio-mail uitgezet, overgeslagen ---")
            continue

        real_email = get_real_email(user_email_hash)
        if not real_email:
            print(f"\n--- {user_email_hash[:12]}...: geen e-mailadres gevonden, overgeslagen ---")
            continue

        print(f"\n--- {real_email} ({len(holdings)} positie(s)) ---")
        results = []
        for holding in holdings:
            result = check_holding(holding["naam"], holding["ticker"])
            if result:
                result["shares"] = holding.get("shares")
                results.append(result)

        if not results:
            print("  Geen van de posities kon gecheckt worden -- geen mail verstuurd.")
            continue

        df = pd.DataFrame(results)

        # Alleen NIEUWE signalen laten meetellen -- zelfde logica als
        # portfolio_watch.py's eigen main().
        previous_states = get_roic_trend_history(df["ticker"].tolist())

        def _was_roic_trend(ticker, trend):
            return previous_states.get(ticker, {}).get("roic_trend") == trend

        def _was_fair_value_bucket(ticker, bucket):
            return previous_states.get(ticker, {}).get("fair_value_bucket") == bucket

        df["roic_decline_is_new"] = df.apply(
            lambda r: r["roic_trend"] == "dalend" and not _was_roic_trend(r["ticker"], "dalend"), axis=1
        )
        df["roic_improvement_is_new"] = df.apply(
            lambda r: r["roic_trend"] == "stijgend" and not _was_roic_trend(r["ticker"], "stijgend"), axis=1
        )
        df["fair_value_crossed_expensive_is_new"] = df.apply(
            lambda r: r["fair_value_bucket"] == "expensive" and not _was_fair_value_bucket(r["ticker"], "expensive"), axis=1
        )
        df["fair_value_crossed_cheap_is_new"] = df.apply(
            lambda r: r["fair_value_bucket"] == "cheap" and not _was_fair_value_bucket(r["ticker"], "cheap"), axis=1
        )

        text_body, html_body = build_email_body(df)
        n_changed = int(df["recent_gewijzigd"].sum())
        n_earnings = int((df["earnings_surprise_pct"].notna()).sum())
        subject_parts = []
        if n_changed > 0:
            subject_parts.append(f"{n_changed} trend change(s)")
        if n_earnings > 0:
            subject_parts.append(f"{n_earnings} earnings update(s)")
        subject = f"Portfolio Watch: {', '.join(subject_parts)}" if subject_parts else "Portfolio Watch: no notable changes this week"

        send_email(subject=subject, body_text=text_body, body_html=html_body, to_email=real_email)

        # De HUIDIGE stand opslaan als 'vorige week' voor de volgende run
        # -- onafhankelijk per ticker (niet per gebruiker), aangezien deze
        # waardes voor iedereen hetzelfde zijn.
        current_states = {
            row["ticker"]: {"roic_trend": row["roic_trend"], "fair_value_bucket": row["fair_value_bucket"]}
            for _, row in df.iterrows()
        }
        save_roic_trend_history(current_states)


def run_daily_flip_scan_for_weekly() -> None:
    """
    Draait de dagelijkse flip-scan OPNIEUW, specifiek voor de zaterdag-
    weekly-mail -- dit vangt de VOLLEDIGE, net-afgeronde vrijdag-sessie op.
    (De reguliere vrijdagochtend-scan draaide namelijk vroeg, VOORDAT de
    Amerikaanse beurs zelfs maar open was, en liet dus donderdag-vs-
    woensdag's beweging zien, niet de volledige vrijdag-sessie.)

    Schrijft dezelfde bestanden als de dagelijkse scan (supertrend_signals_daily.csv,
    top_movers.csv) -- verstuurt zelf GEEN aparte mail, de resultaten worden
    hieronder in de weekly-mail verwerkt.
    """
    import screener_daily
    print("\n=== Dagelijkse flip-scan opnieuw draaien (voor de volledige vrijdag-sessie) ===")
    screener_daily.main(send_own_email=False)


def build_daily_flips_section() -> tuple:
    """
    Bouwt een tekst- en HTML-fragment met de belangrijkste flips uit de
    zojuist opnieuw gedraaide dagelijkse scan (dus: vrijdag's volledige
    sessie) -- toegevoegd aan de zaterdag-weekly-mail, i.p.v. hiervoor een
    aparte mail te sturen. Geeft (leeg, leeg) terug als er geen data is
    of geen signalen waren, zodat de aanroeper deze sectie dan gewoon
    kan overslaan.
    """
    if not os.path.exists("supertrend_signals_daily.csv"):
        return "", ""
    df_daily = pd.read_csv("supertrend_signals_daily.csv")
    if df_daily.empty:
        return "", ""

    df_daily = df_daily.sort_values("score", ascending=False)
    display_limit = 5
    top_n = df_daily.head(display_limit)

    text_lines = [f"📅 Friday's daily flips (top {len(top_n)} of {len(df_daily)} total):"]
    for _, row in top_n.iterrows():
        text_lines.append(
            f"  - [{row['score']}] {row['ticker']}: {row['prijs_bij_omslag']} -> {row['prijs_nu']} "
            f"({row['sinds_omslag_pct']:+.2f}%)"
        )
    text_lines.append("")
    text_fragment = "\n".join(text_lines)

    rows_html = "".join(
        f"<li style='padding:4px 0;color:#101825;'>[{row['score']}] {row['ticker']}: "
        f"{row['prijs_bij_omslag']} &rarr; {row['prijs_nu']} ({row['sinds_omslag_pct']:+.2f}%)</li>"
        for _, row in top_n.iterrows()
    )
    html_fragment = f"""
    <h4 style="color:#101825; font-size:16px; margin:20px 0 8px 0;">📅 Friday's daily flips (top {len(top_n)} of {len(df_daily)} total)</h4>
    <ul style="margin:0; padding-left:20px; font-size:14px;">{rows_html}</ul>
    """
    return text_fragment, html_fragment


def run_saturday() -> None:
    """
    Zaterdag: de gedeelde screener + wekelijkse signalen-mails (Momentocrats/
    Snowballers/Rocket List) -- nu AANGEVULD met vrijdag's volledige
    dagelijkse flips (i.p.v. daarvoor een aparte mail te sturen). Portfolio
    Watch is BEWUST verplaatst naar zondag (zie run_sunday) -- anders kreeg
    je 2-3 mails tegelijk op zaterdagochtend.
    """
    run_screener_shared()
    run_daily_flip_scan_for_weekly()
    all_preferences = get_all_preferences()
    daily_flips_text, daily_flips_html = build_daily_flips_section()
    run_weekly_signals_emails(all_preferences, daily_flips_text=daily_flips_text, daily_flips_html=daily_flips_html)


def run_sunday() -> None:
    """Zondag: alleen Portfolio Watch -- apart van de zaterdag-signalen, geen mail-opeenstapeling meer."""
    all_preferences = get_all_preferences()
    run_portfolio_emails(all_preferences)


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "saturday"
    if mode == "saturday":
        run_saturday()
    elif mode == "sunday":
        run_sunday()
    else:
        raise ValueError(f"Onbekende modus: '{mode}' -- gebruik 'saturday' of 'sunday'.")
    print("\nKlaar.")
