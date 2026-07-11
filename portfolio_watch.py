"""
Portfolio Watch: volgt de HUIDIGE Supertrend-status van je eigen bestaande
posities (in tegenstelling tot screener.py, dat naar NIEUWE ideeën in
AEX/Nasdaq-100 zoekt). Dit is vooral relevant bij een geconcentreerde
portfolio -- weten of je grootste positie (bv. Tesla) nog steeds in een
bullish trend zit, is vaak belangrijker dan een willekeurig nieuw signaal.

BELANGRIJK: check en corrigeer de tickers hieronder. Vooral crypto,
kleine fondsen en niet-beursgenoteerde/private-equity-achtige posities
(zoals SpaceX-exposure-producten) hebben vaak een niet voor de hand
liggende Yahoo Finance-ticker, of zijn er soms helemaal niet in te vinden.

Vereist: pip install -r requirements.txt

Gebruik: python portfolio_watch.py
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf

from indicators import supertrend, ema, resample_to_weekly
from screener import get_roic_data, fetch_weekly, get_recent_news
from emailer import send_email, is_configured as email_is_configured

# --- Jouw posities. CONTROLEER elke ticker, vooral de onderstaande met een '?' ---
PORTFOLIO_HOLDINGS = [
    {"naam": "Tesla", "ticker": "TSLA"},
    {"naam": "Bitcoin", "ticker": "BTC-EUR"},
    {"naam": "Solana", "ticker": "SOL-EUR"},
    {"naam": "Telcoin", "ticker": "TEL-USD"},
    {"naam": "AST SpaceMobile", "ticker": "ASTS"},
    {"naam": "Hims & Hers", "ticker": "HIMS"},
    {"naam": "Duolingo", "ticker": "DUOL"},
    {"naam": "Semiconductors ETF", "ticker": "SMH"},
    {"naam": "TDIV Dividend Leaders ETF", "ticker": "TDIV"},  # ? controleer exacte notering/beurs
    {"naam": "SpaceX", "ticker": "SPCX"},  # IPO 12 juni 2026 -- nog te weinig historie voor weekly Supertrend
    # PROP.COM (fractioneel vastgoed Dubai) is een niet-beursgenoteerd
    # exposure-product zonder ticker -- hier bewust weggelaten.
]

ATR_LENGTH = 6
ATR_MULTIPLIER = 2.6
TREND_FILTER_EMA_LENGTH = 20
RECENT_CHANGE_WEEKS = 2  # een statusverandering binnen dit aantal weken wordt als 'LET OP' gemarkeerd
NEWS_DAYS_BACK = 7       # hoe recent nieuws moet zijn om meegenomen te worden
NEWS_MAX_ITEMS = 3       # max. aantal nieuwsberichten per positie


def check_holding(naam: str, ticker: str):
    # Nieuws is onafhankelijk van of er genoeg historie is voor Supertrend --
    # altijd proberen op te halen, ook als de technische check hieronder faalt.
    news_items = get_recent_news(ticker, max_items=NEWS_MAX_ITEMS, days_back=NEWS_DAYS_BACK)

    try:
        df = fetch_weekly(ticker)
    except Exception as exc:
        print(f"  {naam} ({ticker}): fout bij ophalen ({exc})")
        return {
            "naam": naam, "ticker": ticker, "status": "ONBEKEND (fout bij ophalen)",
            "sinds": None, "weken_in_trend": None, "recent_gewijzigd": False,
            "prijs": None, "boven_ema20": None, "roic_pct": None, "roic_trend": "onbekend",
            "nieuws": news_items,
        }

    min_needed = max(ATR_LENGTH, TREND_FILTER_EMA_LENGTH) + 5
    if df.empty or len(df) < min_needed:
        print(f"  {naam} ({ticker}): te weinig data voor Supertrend (nodig: {min_needed}, "
              f"gekregen: {len(df)}) -- nieuws wordt wel getoond")
        latest_price = round(float(df['close'].iloc[-1]), 2) if not df.empty else None
        return {
            "naam": naam, "ticker": ticker, "status": "ONBEKEND (te weinig historie)",
            "sinds": None, "weken_in_trend": None, "recent_gewijzigd": False,
            "prijs": latest_price, "boven_ema20": None, "roic_pct": None, "roic_trend": "onbekend",
            "nieuws": news_items,
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
        "nieuws": news_items,
    }


def build_email_body(df: pd.DataFrame) -> tuple:
    """Bouwt de Portfolio Watch-mail -- zelfde Hesty's-stijl als de dagelijkse/wekelijkse signalen-mails."""
    changed = df[df["recent_gewijzigd"]]

    # --- Tekst-versie ---
    text_lines = ["Good morning from Hesty's -- here's your portfolio watch.", ""]

    if len(changed) > 0:
        text_lines.append(f"🔄 {len(changed)} position(s) just flipped trend:")
        for _, row in changed.iterrows():
            text_lines.append(f"  - {row['naam']} ({row['ticker']}): now {row['status']} since {row['sinds']}")
        text_lines.append("")

    text_lines.append(f"Full overview ({len(df)} positions):")
    for _, row in df.iterrows():
        roic_txt = f"{row['roic_pct']:+.1f}% ({row['roic_trend']})" if row["roic_pct"] is not None else "unknown"
        text_lines.append(
            f"  - {row['naam']} ({row['ticker']}): {row['status']} since {row['sinds']} "
            f"({row['weken_in_trend']} weeks), price {row['prijs']}, ROIC: {roic_txt}"
        )

    text_lines.append("")
    text_lines.append("Recent news (last 7 days):")
    any_news = False
    for _, row in df.iterrows():
        if row["nieuws"]:
            any_news = True
            text_lines.append(f"\n{row['naam']} ({row['ticker']}):")
            for item in row["nieuws"]:
                text_lines.append(f"  - [{item['published'].strftime('%Y-%m-%d')}] {item['title']} ({item['publisher']})")
                if item["link"]:
                    text_lines.append(f"    {item['link']}")
    if not any_news:
        text_lines.append("No recent news found for your positions.")

    text_lines += [
        "",
        "See the full analysis under Analyze on the site.",
        "",
        "-- Hesty's, your personal investment assistant",
        "",
        "This is a screener, not investment advice.",
    ]
    text_body = "\n".join(text_lines)

    # --- HTML-versie: lichte achtergrond met jade accent, zelfde stijl als
    # de dagelijkse/wekelijkse mail ---
    def _row_html(r):
        roic_str = f"{r['roic_pct']:+.1f}%" if r["roic_pct"] is not None else "-"
        status_color = "#0F8F6E" if r["status"] == "BULLISH" else "#C1524A"
        row_bg = "background-color:#EAF7F3;" if r["recent_gewijzigd"] else ""
        return (
            f"<tr style='border-bottom:1px solid #E5E8EC;{row_bg}'>"
            f"<td style='padding:8px;font-weight:600;color:#101825;'>{r['naam']}</td>"
            f"<td style='padding:8px;color:#5B6472;'>{r['ticker']}</td>"
            f"<td style='padding:8px;font-weight:600;color:{status_color};'>{r['status']}</td>"
            f"<td style='padding:8px;color:#5B6472;'>{r['sinds']}</td>"
            f"<td style='padding:8px;color:#5B6472;'>{r['weken_in_trend']}</td>"
            f"<td style='padding:8px;color:#101825;'>{r['prijs']}</td>"
            f"<td style='padding:8px;color:#5B6472;'>{roic_str}</td>"
            f"</tr>"
        )

    rows_html = "".join(_row_html(r) for _, r in df.iterrows())

    def _news_html(row):
        if not row["nieuws"]:
            return ""
        items_html = "".join(
            f"<li style='padding:4px 0;'><a href=\"{item['link']}\" style='color:#1FAE96;text-decoration:none;font-weight:600;'>{item['title']}</a> "
            f"<span style='color:#9AA1AC;font-size:12px;'>({item['publisher']}, {item['published'].strftime('%Y-%m-%d')})</span></li>"
            for item in row["nieuws"]
        )
        return (f"<p style='margin:16px 0 4px 0;font-weight:700;color:#101825;'>{row['naam']} ({row['ticker']})</p>"
                f"<ul style='margin:0;padding-left:20px;'>{items_html}</ul>")

    news_html = "".join(_news_html(r) for _, r in df.iterrows())
    if not news_html:
        news_html = "<p style='color:#5B6472;'>No recent news found for your positions.</p>"

    flip_banner = ""
    if len(changed) > 0:
        flip_banner = (
            f"<p style='background:#FFF3CD;padding:10px 14px;border-radius:8px;font-size:14px;color:#101825;margin-top:0;'>"
            f"🔄 {len(changed)} position(s) just flipped trend -- see highlighted rows below.</p>"
        )

    html_body = f"""
    <div style="font-family: -apple-system, 'Segoe UI', Roboto, Arial, sans-serif; max-width: 600px; margin: 0 auto; background:#ffffff;">
        <div style="background:#101825; padding: 28px 24px; border-radius: 12px 12px 0 0;">
            <div style="color:#1FAE96; font-size:13px; font-weight:600; letter-spacing:1px; text-transform:uppercase;">Hesty's Portfolio Watch</div>
            <div style="color:#EAEDF1; font-size:22px; font-weight:700; margin-top:4px;">Your positions, checked</div>
        </div>
        <div style="padding: 24px; border: 1px solid #E5E8EC; border-top: none; border-radius: 0 0 12px 12px;">
            {flip_banner}
            <table style="width:100%; border-collapse:collapse; margin-top:16px; font-size:14px;">
                <tr style="border-bottom:2px solid #101825;">
                    <th style="text-align:left; padding:8px; font-size:11px; color:#5B6472; text-transform:uppercase;">Name</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#5B6472; text-transform:uppercase;">Ticker</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#5B6472; text-transform:uppercase;">Trend</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#5B6472; text-transform:uppercase;">Since</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#5B6472; text-transform:uppercase;">Weeks</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#5B6472; text-transform:uppercase;">Price</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#5B6472; text-transform:uppercase;">ROIC</th>
                </tr>
                {rows_html}
            </table>

            <h4 style="color:#101825; font-size:16px; margin:24px 0 8px 0;">📰 Recent news</h4>
            {news_html}

            <p style="margin-top:20px; font-size:14px; color:#5B6472; line-height:1.5;">
                See the full analysis under
                <a href="https://hestys.streamlit.app/?view=analyze" style="color:#1FAE96; font-weight:600; text-decoration:none;">Analyze</a> on the site.
            </p>
            <p style="margin-top:24px; font-size:14px; color:#101825; font-weight:600;">&mdash; Hesty's, your personal investment assistant</p>
            <p style="margin-top:16px; font-size:12px; color:#9AA1AC; font-style:italic;">This is a screener, not investment advice.</p>
        </div>
    </div>
    """
    return text_body, html_body


def main() -> None:
    print(f"Portfolio Watch: {len(PORTFOLIO_HOLDINGS)} posities checken "
          f"(weekly, ATR-periode {ATR_LENGTH}, multiplier {ATR_MULTIPLIER})...\n")

    results = []
    for holding in PORTFOLIO_HOLDINGS:
        result = check_holding(holding["naam"], holding["ticker"])
        if result:
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
    # 'nieuws' is een lijst-per-rij -- hoort niet netjes in een CSV-cel of
    # brede tabel, laten we dat weg en tonen het apart
    df.drop(columns=["nieuws"]).to_csv("portfolio_watch.csv", index=False)

    # Nieuws apart opslaan als JSON, zodat het dashboard dit kan tonen
    # zonder alles opnieuw op te hoeven halen
    import json
    news_export = {}
    for _, row in df.iterrows():
        news_export[row["ticker"]] = [
            {**item, "published": item["published"].isoformat()} for item in row["nieuws"]
        ]
    with open("portfolio_watch_news.json", "w", encoding="utf-8") as f:
        json.dump(news_export, f, ensure_ascii=False, indent=2)

    print(f"\n=== OVERZICHT ===\n")
    print(df.drop(columns=["nieuws"]).to_string(index=False))

    print("\n=== RECENT NIEUWS (laatste 7 dagen) ===")
    any_news = False
    for _, row in df.iterrows():
        if row["nieuws"]:
            any_news = True
            print(f"\n{row['naam']} ({row['ticker']}):")
            for item in row["nieuws"]:
                print(f"  - [{item['published'].strftime('%Y-%m-%d')}] {item['title']} ({item['publisher']})")
                if item["link"]:
                    print(f"    {item['link']}")
    if not any_news:
        print("  Geen recent nieuws gevonden voor je posities.")

    print("\nOpgeslagen in 'portfolio_watch.csv'.")

    if email_is_configured():
        text_body, html_body = build_email_body(df)
        n_changed = df["recent_gewijzigd"].sum()
        subject = f"Portfolio Watch: {n_changed} wijziging(en)" if n_changed > 0 else "Portfolio Watch: geen wijzigingen"
        send_email(subject=subject, body_text=text_body, body_html=html_body)
    else:
        print("\n(E-mail niet verstuurd: nog niet ingesteld in .env.)")


if __name__ == "__main__":
    main()
