"""
Portfolio Watch: volgt de HUIDIGE Supertrend-status van je eigen bestaande
posities (in tegenstelling tot screener.py, dat naar NIEUWE ideeën in
AEX/Nasdaq-100 zoekt). Dit is vooral relevant bij een geconcentreerde
portfolio -- weten of je grootste positie (bv. Tesla) nog steeds in een
bullish trend zit, is vaak belangrijker dan een willekeurig nieuw signaal.

Haalt je posities nu RECHTSTREEKS uit de database (dezelfde die 'My
Portfolio' op de site gebruikt), i.p.v. een hardgecodeerde lijst die
handmatig bijgewerkt moest worden -- deze mail blijft nu altijd
gesynchroniseerd met wat je daadwerkelijk bezit, ook als je iets koopt
of verkoopt. Alleen posities met shares > 0 worden meegenomen (geen
watchlist-items, geen posities die je al verkocht hebt).

Vereist: pip install -r requirements.txt
Vereist env-var: PORTFOLIO_WATCH_USER_EMAIL (welk account de posities gevolgd worden)

Gebruik: python portfolio_watch.py
"""
from __future__ import annotations

import os

import pandas as pd
import yfinance as yf

from indicators import supertrend, ema, resample_to_weekly
from screener import get_roic_data, fetch_weekly, get_earnings_surprise
from emailer import send_email, is_configured as email_is_configured
from database import get_user_holdings


def get_current_holdings() -> list:
    """
    Haalt de ACTUELE, eigen posities op uit de database (i.p.v. een
    hardgecodeerde lijst) -- alleen posities met shares > 0 (geen
    watchlist-items, geen verkochte posities). Vereist de env-var
    PORTFOLIO_WATCH_USER_EMAIL, zodat dit script weet WELK account
    gevolgd moet worden (het draait immers los van een ingelogde sessie).
    """
    user_email = os.getenv("PORTFOLIO_WATCH_USER_EMAIL")
    if not user_email:
        raise ValueError(
            "PORTFOLIO_WATCH_USER_EMAIL is niet ingesteld -- Portfolio Watch weet "
            "hierdoor niet welk account de posities gevolgd moeten worden."
        )
    all_holdings = get_user_holdings(user_email, is_watchlist=False)
    return [
        {"naam": h["naam"], "ticker": h["ticker"], "shares": h["shares"]}
        for h in all_holdings
        if (h.get("shares") or 0) > 0
    ]

ATR_LENGTH = 6
ATR_MULTIPLIER = 2.6
TREND_FILTER_EMA_LENGTH = 20
RECENT_CHANGE_WEEKS = 2  # een statusverandering binnen dit aantal weken wordt als 'LET OP' gemarkeerd
EARNINGS_RECENT_DAYS = 7  # hoe recent gerapporteerde cijfers moeten zijn om als 'deze week' te tellen


def get_upcoming_earnings_date(ticker: str):
    """
    Checkt of deze positie AANKOMENDE cijfers heeft binnen de komende 7
    dagen -- vooruitkijkend, in tegenstelling tot get_earnings_surprise()
    (die kijkt naar AL gerapporteerde cijfers). Geeft None terug als er
    geen aankomende cijfers binnen dat venster zijn, of als het niet op
    te halen is.
    """
    try:
        earnings_dates = yf.Ticker(ticker).get_earnings_dates(limit=8)
        if earnings_dates is None or earnings_dates.empty:
            return None
        today = pd.Timestamp.now(tz=earnings_dates.index.tz).normalize()
        window_end = today + pd.Timedelta(days=7)
        future_dates = earnings_dates.index[(earnings_dates.index >= today) & (earnings_dates.index <= window_end)]
        return future_dates[0] if len(future_dates) > 0 else None
    except Exception:
        return None


def check_holding(naam: str, ticker: str):
    # Earnings-verrassing (al gerapporteerd) EN aankomende earnings (komende
    # 7 dagen) zijn allebei onafhankelijk van of er genoeg historie is voor
    # Supertrend -- altijd proberen op te halen, ook als de technische check
    # hieronder faalt.
    earnings_info = get_earnings_surprise(ticker)
    upcoming_earnings = get_upcoming_earnings_date(ticker)

    try:
        df = fetch_weekly(ticker)
    except Exception as exc:
        print(f"  {naam} ({ticker}): fout bij ophalen ({exc})")
        return {
            "naam": naam, "ticker": ticker, "status": "ONBEKEND (fout bij ophalen)",
            "sinds": None, "weken_in_trend": None, "recent_gewijzigd": False,
            "prijs": None, "boven_ema20": None, "roic_pct": None, "roic_trend": "onbekend",
            "week_change_pct": None,
            "earnings_surprise_pct": earnings_info["surprise_pct"],
            "earnings_beat": earnings_info["beat"],
            "earnings_date": earnings_info["earnings_date"],
            "upcoming_earnings_date": upcoming_earnings,
        }

    min_needed = max(ATR_LENGTH, TREND_FILTER_EMA_LENGTH) + 5
    if df.empty or len(df) < min_needed:
        print(f"  {naam} ({ticker}): te weinig data voor Supertrend (nodig: {min_needed}, "
              f"gekregen: {len(df)})")
        latest_price = round(float(df['close'].iloc[-1]), 2) if not df.empty else None
        week_change_pct = None
        if len(df) >= 2:
            prev_close = float(df["close"].iloc[-2])
            if prev_close:
                week_change_pct = (float(df["close"].iloc[-1]) - prev_close) / prev_close * 100
        return {
            "naam": naam, "ticker": ticker, "status": "ONBEKEND (te weinig historie)",
            "sinds": None, "weken_in_trend": None, "recent_gewijzigd": False,
            "prijs": latest_price, "boven_ema20": None, "roic_pct": None, "roic_trend": "onbekend",
            "week_change_pct": week_change_pct,
            "earnings_surprise_pct": earnings_info["surprise_pct"],
            "earnings_beat": earnings_info["beat"],
            "earnings_date": earnings_info["earnings_date"],
            "upcoming_earnings_date": upcoming_earnings,
        }

    st = supertrend(df, length=ATR_LENGTH, multiplier=ATR_MULTIPLIER)
    df = df.copy()
    df["trend_dir"] = st["trend_dir"]
    df["ema_trend"] = ema(df["close"], TREND_FILTER_EMA_LENGTH)

    current_trend = int(df["trend_dir"].iloc[-1])
    trend_changes = df.index[df["trend_dir"] != df["trend_dir"].shift(1)]
    last_change = trend_changes[-1] if len(trend_changes) > 0 else df.index[0]
    weeks_in_current_trend = len(df.loc[last_change:]) - 1

    latest_row = df.iloc[-1]
    roic_data = get_roic_data(ticker)

    prev_close = float(df["close"].iloc[-2])
    week_change_pct = (float(latest_row["close"]) - prev_close) / prev_close * 100 if prev_close else None

    return {
        "naam": naam,
        "ticker": ticker,
        "status": "BULLISH" if current_trend == 1 else "BEARISH",
        "sinds": last_change.date(),
        "weken_in_trend": weeks_in_current_trend,
        "recent_gewijzigd": weeks_in_current_trend <= RECENT_CHANGE_WEEKS,
        "prijs": round(float(latest_row["close"]), 2),
        "boven_ema20": bool(latest_row["close"] > latest_row["ema_trend"]),
        "roic_pct": round(roic_data["roic"] * 100, 1) if roic_data["roic"] is not None else None,
        "roic_trend": roic_data["roic_trend"],
        "week_change_pct": week_change_pct,
        "earnings_surprise_pct": earnings_info["surprise_pct"],
        "earnings_beat": earnings_info["beat"],
        "earnings_date": earnings_info["earnings_date"],
        "upcoming_earnings_date": upcoming_earnings,
    }


def build_email_body(df: pd.DataFrame) -> tuple:
    """Bouwt de Portfolio Watch-mail -- zelfde Hesty's-stijl als de dagelijkse/wekelijkse signalen-mails."""
    changed = df[df["recent_gewijzigd"]]

    # --- Beknopt: alleen wat DEZE WEEK daadwerkelijk is veranderd, i.p.v.
    # een volledige, elke-keer-herhalende samenvatting van alles. ---
    from datetime import datetime as _datetime

    def _is_recent_earnings(earnings_date):
        if earnings_date is None:
            return False
        try:
            ed = earnings_date.date() if hasattr(earnings_date, "date") else earnings_date
            days_since = (_datetime.now().date() - ed).days
            return 0 <= days_since <= EARNINGS_RECENT_DAYS
        except Exception:
            return False

    earnings_mask = df["earnings_date"].apply(_is_recent_earnings) & df["earnings_surprise_pct"].notna()
    earnings_this_week = df[earnings_mask]

    upcoming_earnings = df[df["upcoming_earnings_date"].notna()].sort_values("upcoming_earnings_date")

    # --- Fundamentele signalen: dalende ROIC (jaar-op-jaar, al berekend
    # door get_roic_data() -- geen nieuwe opslag nodig) EN/OF een recente
    # earnings-misser -- allebei zaken die je mening over een positie
    # zouden kunnen bijstellen, in tegenstelling tot een neutrale
    # trend-flip of een earnings-beat. ---
    def _fundamental_reason(row):
        reasons = []
        if row["roic_trend"] == "dalend":
            reasons.append("ROIC declining year-over-year")
        if earnings_mask.get(row.name, False) and row["earnings_beat"] is False:
            reasons.append(f"missed earnings estimates by {row['earnings_surprise_pct']:+.1f}%")
        return " and ".join(reasons)

    fundamental_mask = (df["roic_trend"] == "dalend") | (earnings_mask & (df["earnings_beat"] == False))
    fundamental_concerns = df[fundamental_mask].copy()
    if not fundamental_concerns.empty:
        fundamental_concerns["reason"] = fundamental_concerns.apply(_fundamental_reason, axis=1)

    notable_tickers = set(changed["ticker"]) | set(earnings_this_week["ticker"]) | set(fundamental_concerns["ticker"])
    quiet_positions = df[~df["ticker"].isin(notable_tickers)]

    # --- Gewogen weekrendement + beste/slechtste positie deze week --
    # gewogen op huidige positiewaarde (shares x prijs), zodat een grote
    # positie logischerwijs zwaarder meetelt dan een kleine.
    df_with_value = df.copy()
    df_with_value["value"] = df_with_value["shares"].fillna(0) * df_with_value["prijs"].fillna(0)
    valid_week = df_with_value[df_with_value["week_change_pct"].notna() & (df_with_value["value"] > 0)]
    portfolio_week_change_pct = None
    if not valid_week.empty and valid_week["value"].sum() > 0:
        portfolio_week_change_pct = (valid_week["week_change_pct"] * valid_week["value"]).sum() / valid_week["value"].sum()

    best_this_week = worst_this_week = None
    valid_week_moves = df[df["week_change_pct"].notna()]
    if not valid_week_moves.empty:
        best_this_week = valid_week_moves.loc[valid_week_moves["week_change_pct"].idxmax()]
        worst_this_week = valid_week_moves.loc[valid_week_moves["week_change_pct"].idxmin()]
        if best_this_week["ticker"] == worst_this_week["ticker"]:
            worst_this_week = None  # slechts 1 positie met bekende weekbeweging -- niet 2x dezelfde tonen

    # --- Tekst-versie ---
    text_lines = ["Good morning from Hesty's -- here's your portfolio watch.", ""]

    if portfolio_week_change_pct is not None:
        text_lines.append(f"📈 Your portfolio this week: {portfolio_week_change_pct:+.1f}%")
        if best_this_week is not None:
            text_lines.append(f"  Best: {best_this_week['naam']} ({best_this_week['ticker']}) {best_this_week['week_change_pct']:+.1f}%")
        if worst_this_week is not None:
            text_lines.append(f"  Worst: {worst_this_week['naam']} ({worst_this_week['ticker']}) {worst_this_week['week_change_pct']:+.1f}%")
        text_lines.append("")

    if len(changed) > 0:
        text_lines.append("🔄 Trend changes this week:")
        for _, row in changed.iterrows():
            emoji = "🟢" if row["status"] == "BULLISH" else "🔴"
            text_lines.append(f"  {emoji} {row['naam']} ({row['ticker']}): flipped to {row['status']}")
    else:
        text_lines.append("🔄 No trend changes this week.")
    text_lines.append("")

    if not fundamental_concerns.empty:
        text_lines.append("⚠️ Worth a closer look:")
        for _, row in fundamental_concerns.iterrows():
            text_lines.append(f"  - {row['naam']} ({row['ticker']}): {row['reason']}")
        text_lines.append("")

    if len(earnings_this_week) > 0:
        text_lines.append("📊 Earnings this week:")
        for _, row in earnings_this_week.iterrows():
            beat_txt = "beat" if row["earnings_beat"] else "missed"
            text_lines.append(f"  - {row['naam']} ({row['ticker']}): {beat_txt} estimates by {row['earnings_surprise_pct']:+.1f}%")
        text_lines.append("")

    if len(upcoming_earnings) > 0:
        text_lines.append("📅 Earnings coming up next week:")
        for _, row in upcoming_earnings.iterrows():
            earnings_date_str = row["upcoming_earnings_date"].strftime("%A %Y-%m-%d")
            text_lines.append(f"  - {row['naam']} ({row['ticker']}): {earnings_date_str}")
        text_lines.append("")

    if len(quiet_positions) > 0:
        quiet_names = ", ".join(quiet_positions["ticker"].tolist())
        text_lines.append(f"✅ No notable changes ({len(quiet_positions)} position(s)): {quiet_names}")
        text_lines.append("")

    text_lines += [
        "See the full picture under Analyze > Portfolio Overview on the site.",
        "",
        "-- Hesty's, your personal investment assistant",
        "",
        "This is a screener, not investment advice.",
    ]
    text_body = "\n".join(text_lines)

    # --- HTML-versie: zelfde donkere-header-met-jade-accent-stijl als de
    # andere Hesty's-mails, maar nu bewust beknopt: korte secties i.p.v.
    # een volledige tabel + nieuws-dump. ---
    week_summary_html = ""
    if portfolio_week_change_pct is not None:
        week_color = "#0F8F6E" if portfolio_week_change_pct >= 0 else "#C1524A"
        best_worst_bits = []
        if best_this_week is not None:
            best_worst_bits.append(
                f"Best: <strong>{best_this_week['naam']} ({best_this_week['ticker']})</strong> "
                f"<span style='color:#0F8F6E;'>{best_this_week['week_change_pct']:+.1f}%</span>"
            )
        if worst_this_week is not None:
            best_worst_bits.append(
                f"Worst: <strong>{worst_this_week['naam']} ({worst_this_week['ticker']})</strong> "
                f"<span style='color:#C1524A;'>{worst_this_week['week_change_pct']:+.1f}%</span>"
            )
        best_worst_html = f"<p style='margin:6px 0 0 0; font-size:13px; color:#5B6472;'>{' &middot; '.join(best_worst_bits)}</p>" if best_worst_bits else ""
        week_summary_html = f"""
        <div style="background:#F7F9FA; border-radius:8px; padding:14px 16px; margin-bottom:20px;">
            <span style="font-size:14px; color:#5B6472;">📈 Your portfolio this week</span><br/>
            <span style="font-size:22px; font-weight:700; color:{week_color};">{portfolio_week_change_pct:+.1f}%</span>
            {best_worst_html}
        </div>
        """

    def _flip_row_html(r):
        emoji = "🟢" if r["status"] == "BULLISH" else "🔴"
        status_color = "#0F8F6E" if r["status"] == "BULLISH" else "#C1524A"
        return (
            f"<li style='padding:6px 0;'>{emoji} <strong style='color:#101825;'>{r['naam']} ({r['ticker']})</strong>: "
            f"flipped to <span style='color:{status_color}; font-weight:600;'>{r['status']}</span></li>"
        )

    if len(changed) > 0:
        flips_html = f"<ul style='margin:8px 0; padding-left:20px;'>{''.join(_flip_row_html(r) for _, r in changed.iterrows())}</ul>"
    else:
        flips_html = "<p style='color:#5B6472; margin:8px 0;'>No trend changes this week.</p>"

    fundamental_html = ""
    if not fundamental_concerns.empty:
        fundamental_items = "".join(
            f"<li style='padding:6px 0;'><strong style='color:#101825;'>{r['naam']} ({r['ticker']})</strong>: "
            f"<span style='color:#C1524A;'>{r['reason']}</span></li>"
            for _, r in fundamental_concerns.iterrows()
        )
        fundamental_html = (
            f"<h4 style='color:#101825; font-size:15px; margin:20px 0 4px 0;'>⚠️ Worth a closer look</h4>"
            f"<ul style='margin:8px 0; padding-left:20px;'>{fundamental_items}</ul>"
        )

    def _earnings_row_html(r):
        beat_txt = "beat" if r["earnings_beat"] else "missed"
        color = "#0F8F6E" if r["earnings_beat"] else "#C1524A"
        return (
            f"<li style='padding:6px 0;'><strong style='color:#101825;'>{r['naam']} ({r['ticker']})</strong>: "
            f"{beat_txt} estimates by <span style='color:{color}; font-weight:600;'>{r['earnings_surprise_pct']:+.1f}%</span></li>"
        )

    earnings_section_html = ""
    if len(earnings_this_week) > 0:
        earnings_items = "".join(_earnings_row_html(r) for _, r in earnings_this_week.iterrows())
        earnings_section_html = (
            f"<h4 style='color:#101825; font-size:15px; margin:20px 0 4px 0;'>📊 Earnings this week</h4>"
            f"<ul style='margin:8px 0; padding-left:20px;'>{earnings_items}</ul>"
        )

    upcoming_earnings_html = ""
    if len(upcoming_earnings) > 0:
        upcoming_items = "".join(
            f"<li style='padding:6px 0;'><strong style='color:#101825;'>{r['naam']} ({r['ticker']})</strong>: "
            f"{r['upcoming_earnings_date'].strftime('%A %Y-%m-%d')}</li>"
            for _, r in upcoming_earnings.iterrows()
        )
        upcoming_earnings_html = (
            f"<h4 style='color:#101825; font-size:15px; margin:20px 0 4px 0;'>📅 Earnings coming up next week</h4>"
            f"<ul style='margin:8px 0; padding-left:20px;'>{upcoming_items}</ul>"
        )

    quiet_html = ""
    if len(quiet_positions) > 0:
        quiet_names = ", ".join(quiet_positions["ticker"].tolist())
        quiet_html = (
            f"<p style='margin-top:20px; font-size:13px; color:#5B6472;'>"
            f"✅ No notable changes ({len(quiet_positions)}): {quiet_names}</p>"
        )

    html_body = f"""
    <div style="font-family: -apple-system, 'Segoe UI', Roboto, Arial, sans-serif; max-width: 600px; margin: 0 auto; background:#ffffff;">
        <div style="background:#101825; padding: 28px 24px; border-radius: 12px 12px 0 0;">
            <div style="color:#1FAE96; font-size:13px; font-weight:600; letter-spacing:1px; text-transform:uppercase;">Hesty's Portfolio Watch</div>
            <div style="color:#EAEDF1; font-size:22px; font-weight:700; margin-top:4px;">Your positions, checked</div>
        </div>
        <div style="padding: 24px; border: 1px solid #E5E8EC; border-top: none; border-radius: 0 0 12px 12px;">
            {week_summary_html}
            <h4 style="color:#101825; font-size:15px; margin:0 0 4px 0;">🔄 Trend changes this week</h4>
            {flips_html}
            {fundamental_html}
            {earnings_section_html}
            {upcoming_earnings_html}
            {quiet_html}
            <p style="margin-top:20px; font-size:14px; color:#5B6472; line-height:1.5;">
                See the full picture under
                <a href="https://hestys.streamlit.app/?view=analyze&subview=portfolio" style="color:#1FAE96; font-weight:600; text-decoration:none;">Analyze &gt; Portfolio Overview</a> on the site.
            </p>
            <p style="margin-top:24px; font-size:14px; color:#101825; font-weight:600;">&mdash; Hesty's, your personal investment assistant</p>
            <p style="margin-top:16px; font-size:12px; color:#9AA1AC; font-style:italic;">This is a screener, not investment advice.</p>
        </div>
    </div>
    """
    return text_body, html_body


def main() -> None:
    portfolio_holdings = get_current_holdings()
    print(f"Portfolio Watch: {len(portfolio_holdings)} posities checken "
          f"(weekly, ATR-periode {ATR_LENGTH}, multiplier {ATR_MULTIPLIER})...\n")

    results = []
    for holding in portfolio_holdings:
        result = check_holding(holding["naam"], holding["ticker"])
        if result:
            result["shares"] = holding.get("shares")
            results.append(result)
            marker = " <-- LET OP, recent gewijzigd" if result["recent_gewijzigd"] else ""
            if result["sinds"] is not None:
                print(f"  {result['naam']}: {result['status']} sinds {result['sinds']} "
                      f"({result['weken_in_trend']} weken){marker}")
            else:
                print(f"  {result['naam']}: {result['status']}")

    if not results:
        print("\nGeen enkele positie kon gecheckt worden -- controleer je tickers.")
        return

    df = pd.DataFrame(results)
    df.to_csv("portfolio_watch.csv", index=False)

    print(f"\n=== OVERZICHT ===\n")
    print(df.to_string(index=False))

    print("\nOpgeslagen in 'portfolio_watch.csv'.")

    if email_is_configured():
        text_body, html_body = build_email_body(df)
        n_changed = int(df["recent_gewijzigd"].sum())
        n_earnings = int((df["earnings_surprise_pct"].notna()).sum())
        subject_parts = []
        if n_changed > 0:
            subject_parts.append(f"{n_changed} trend change(s)")
        if n_earnings > 0:
            subject_parts.append(f"{n_earnings} earnings update(s)")
        subject = f"Portfolio Watch: {', '.join(subject_parts)}" if subject_parts else "Portfolio Watch: no notable changes this week"
        send_email(subject=subject, body_text=text_body, body_html=html_body)
    else:
        print("\n(E-mail niet verstuurd: nog niet ingesteld in .env.)")


if __name__ == "__main__":
    main()
