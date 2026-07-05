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
    changed = df[df["recent_gewijzigd"]]
    lines = [f"Portfolio Watch: status van {len(df)} posities.\n"]

    if len(changed) > 0:
        lines.append(f"LET OP -- {len(changed)} positie(s) recent van trend gewisseld:")
        for _, row in changed.iterrows():
            lines.append(f"  * {row['naam']} ({row['ticker']}): nu {row['status']} sinds {row['sinds']}")
        lines.append("")

    lines.append("Volledig overzicht:")
    for _, row in df.iterrows():
        roic_txt = f"{row['roic_pct']:+.1f}% ({row['roic_trend']})" if row["roic_pct"] is not None else "onbekend"
        lines.append(
            f"- {row['naam']} ({row['ticker']}): {row['status']} sinds {row['sinds']} "
            f"({row['weken_in_trend']} weken), prijs {row['prijs']}, ROIC: {roic_txt}"
        )

    lines.append("\n--- Recent nieuws (laatste 7 dagen) ---")
    any_news = False
    for _, row in df.iterrows():
        if row["nieuws"]:
            any_news = True
            lines.append(f"\n{row['naam']} ({row['ticker']}):")
            for item in row["nieuws"]:
                lines.append(f"  - [{item['published'].strftime('%Y-%m-%d')}] {item['title']} ({item['publisher']})")
                if item["link"]:
                    lines.append(f"    {item['link']}")
    if not any_news:
        lines.append("Geen recent nieuws gevonden voor je posities.")

    text_body = "\n".join(lines)

    def _row_html(r):
        roic_str = f"{r['roic_pct']:+.1f}%" if r["roic_pct"] is not None else "-"
        highlight = ' style="background-color:#fff3cd;"' if r["recent_gewijzigd"] else ""
        return (
            f"<tr{highlight}><td>{r['naam']}</td><td>{r['ticker']}</td><td>{r['status']}</td>"
            f"<td>{r['sinds']}</td><td>{r['weken_in_trend']}</td><td>{r['prijs']}</td>"
            f"<td>{roic_str}</td><td>{r['roic_trend']}</td></tr>"
        )

    rows_html = "".join(_row_html(r) for _, r in df.iterrows())

    def _news_html(row):
        if not row["nieuws"]:
            return ""
        items_html = "".join(
            f"<li><a href=\"{item['link']}\">{item['title']}</a> "
            f"<i>({item['publisher']}, {item['published'].strftime('%Y-%m-%d')})</i></li>"
            for item in row["nieuws"]
        )
        return f"<p><b>{row['naam']} ({row['ticker']})</b></p><ul>{items_html}</ul>"

    news_html = "".join(_news_html(r) for _, r in df.iterrows())
    if not news_html:
        news_html = "<p>Geen recent nieuws gevonden voor je posities.</p>"

    html_body = f"""
    <h3>Portfolio Watch</h3>
    <p>{len(changed)} positie(s) recent van trend gewisseld (geel gemarkeerd).</p>
    <table border="1" cellpadding="5" cellspacing="0">
      <tr><th>Naam</th><th>Ticker</th><th>Status</th><th>Sinds</th><th>Weken</th>
          <th>Prijs</th><th>ROIC</th><th>ROIC-trend</th></tr>
      {rows_html}
    </table>
    <h3>Recent nieuws (laatste 7 dagen)</h3>
    {news_html}
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
