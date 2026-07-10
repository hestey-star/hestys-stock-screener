"""
Dashboard: visualiseert de resultaten van screener.py en portfolio_watch.py.
(Deze code-commentaren blijven in het Nederlands -- alleen de daadwerkelijk
zichtbare website-tekst is naar het Engels vertaald.)

Navigatie is bewust GEEN st.tabs(): de opdracht was dat de startpagina
leeg is totdat je expliciet op 'Welcome' (of een andere nav-link/het logo)
klikt. Dat is met st.tabs() niet mogelijk (die toont altijd meteen de
inhoud van het eerste tabblad) -- daarom gebruiken we hier een eigen
navigatiebalk van HTML-links die de URL-query-parameter '?view=...'
aanpassen, en tonen we inhoud alleen als die parameter overeenkomt.
Dat maakt het logo ook op een natuurlijke manier klikbaar (het is zelf
ook zo'n link, naar '?view=welcome').

Lokaal draaien:
    streamlit run dashboard.py

Op internet zetten (gratis, voor jezelf of om te delen):
    1. Zet dit project op GitHub (in een repository)
    2. Ga naar https://share.streamlit.io, log in met GitHub
    3. Wijs naar je repository en dit bestand (dashboard.py)
    4. Streamlit Cloud host 'm gratis op een publieke URL

Vereist: pip install -r requirements.txt (incl. streamlit)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import stripe
import streamlit as st
import yfinance as yf

from emailer import send_email

st.set_page_config(page_title="Hesty's", page_icon="◆", layout="wide")

# --- Visuele identiteit: donkere 'kluis/terminal'-stijl, geen standaard-look ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, p, span, div, label {
    font-family: 'Inter', sans-serif;
}
h1, h2, h3 {
    font-family: 'Fraunces', serif !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em;
}
code, .stDataFrame, [data-testid="stMetricValue"] {
    font-family: 'IBM Plex Mono', monospace !important;
}

/* Het 'verzegeld'-badge: het signatuurelement dat vertrouwelijkheid concreet maakt */
.privacy-seal {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.9rem;
    border: 1px solid #1FAE96;
    border-radius: 999px;
    background: rgba(31, 174, 150, 0.08);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.8rem;
    color: #1FAE96;
    margin-bottom: 1rem;
}

/* Header: logo (klikbaar, linkt naar Welcome) + navigatiebalk eronder */
.app-header {
    padding: 1.2rem 0 1rem 0;
    border-bottom: 2px solid #1FAE96;
    margin-bottom: 1.5rem;
}
.app-header-top {
    display: flex;
    align-items: center;
    gap: 0.9rem;
    text-decoration: none !important;
    margin-bottom: 1rem;
}
.app-header-top:hover, .app-header-top:visited, .app-header-top:active {
    text-decoration: none !important;
}
.app-header h1 {
    margin: 0 !important;
    font-size: 1.8rem !important;
    line-height: 1.1;
    color: #EAEDF1 !important;
}
.app-header .tagline {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.08em;
    color: #8992A3 !important;
    margin-top: 0.15rem;
}
.nav-bar {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}
.nav-link, .nav-link:visited, .nav-link:active {
    font-family: 'Inter', sans-serif;
    font-size: 0.9rem;
    font-weight: 500;
    padding: 0.4rem 1rem;
    border-radius: 6px;
    text-decoration: none !important;
    color: #8992A3 !important;
    border: 1px solid transparent;
}
.nav-link:hover {
    color: #EAEDF1 !important;
    border: 1px solid #1FAE96;
}
.nav-link.active, .nav-link.active:visited {
    color: #1FAE96 !important;
    background: rgba(31, 174, 150, 0.1);
    border: 1px solid #1FAE96;
}

/* Mooie inline-link binnen lopende tekst (bv. '... zie Discover') --
   alleen het woord zelf is gestyled, niet de hele zin, en geen kaal
   blauw-onderstreept-link-gevoel */
.inline-link {
    color: #1FAE96 !important;
    font-weight: 600;
    text-decoration: none !important;
    border-bottom: 1.5px solid rgba(31, 174, 150, 0.4);
    padding-bottom: 1px;
    transition: border-color 0.15s ease;
}
.inline-link:hover {
    border-bottom-color: #1FAE96;
}

/* Knop-achtige link (voor bv. 'Buy smarter with DCA') -- oogt als een
   Streamlit-knop, is technisch een <a>, zodat 'ie in hetzelfde tabblad
   navigeert (st.link_button opent altijd een nieuw tabblad) */
.button-link, .button-link:visited {
    display: inline-block;
    font-family: 'Inter', sans-serif;
    font-size: 0.9rem;
    font-weight: 600;
    color: #101825 !important;
    background: #1FAE96;
    padding: 0.45rem 1.1rem;
    border-radius: 6px;
    text-decoration: none !important;
    margin-top: 0.4rem;
}
.button-link:hover {
    background: #24C4A8;
}

/* Naam/account-link in de kop (rechtsboven) -- verwijst naar Settings,
   gestyled als een subtiele pil i.p.v. platte tekst */
.account-link, .account-link:visited {
    display: inline-block;
    font-family: 'Inter', sans-serif;
    font-size: 0.85rem;
    font-weight: 500;
    color: #8992A3 !important;
    text-decoration: none !important;
    padding: 0.35rem 0.7rem;
    border-radius: 6px;
    border: 1px solid transparent;
}
.account-link:hover {
    color: #EAEDF1 !important;
    border-color: #1FAE96;
}
.account-link.active {
    color: #1FAE96 !important;
    border-color: #1FAE96;
    background: rgba(31, 174, 150, 0.1);
}

/* Compacte, met lijntjes gescheiden posities-lijst in 'Your positions' */
.holding-text {
    font-size: 0.85rem;
    color: #EAEDF1;
}
.holding-divider {
    border: none;
    border-top: 1px solid #232D3A;
    margin: 0.35rem 0;
}

/* Compacte, duidelijk afgebakende tabel voor 'Your positions' */
.positions-table {
    width: 100%;
    border-collapse: collapse;
    background: #141B24;
    border: 1px solid #232D3A;
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 1.2rem;
}
.positions-table th {
    text-align: left;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.05em;
    color: #8992A3;
    padding: 0.5rem 0.9rem;
    border-bottom: 1px solid #232D3A;
}
.positions-table td {
    padding: 0.4rem 0.9rem;
    font-size: 0.85rem;
    color: #EAEDF1;
    border-bottom: 1px solid #1B2536;
}
.positions-table tr:last-child td {
    border-bottom: none;
}
.positions-table code {
    color: #1FAE96;
    background: none;
    font-size: 0.85rem;
}

/* Iets compactere tabellen: kleinere tekst in de databladen */
[data-testid="stDataFrame"] * {
    font-size: 0.85rem !important;
}
</style>
""", unsafe_allow_html=True)


def file_last_modified(path: str) -> str:
    if not os.path.exists(path):
        return "never"
    ts = os.path.getmtime(path)
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def load_screener_data(csv_file: str = "supertrend_signals.csv"):
    if not os.path.exists(csv_file):
        return None
    df = pd.read_csv(csv_file)
    return df


def load_portfolio_data():
    if not os.path.exists("portfolio_watch.csv"):
        return None
    df = pd.read_csv("portfolio_watch.csv")
    return df


def load_portfolio_news():
    if not os.path.exists("portfolio_watch_news.json"):
        return {}
    with open("portfolio_watch_news.json", encoding="utf-8") as f:
        return json.load(f)


def get_fx_rate(from_currency: str, to_currency: str):
    """Haalt de actuele wisselkoers op. Geeft None terug als het niet lukt (i.p.v. een gok te doen)."""
    if from_currency == to_currency:
        return 1.0
    pair_ticker = f"{from_currency}{to_currency}=X"
    try:
        data = yf.Ticker(pair_ticker).history(period="1d")
        if not data.empty:
            return float(data["Close"].iloc[-1])
    except Exception:
        pass
    return None


def build_portfolio_pie_chart(holdings: list):
    """Bouwt een compacte donut-chart van de portfolio-verdeling, met de legenda naast (niet onder) de taart."""
    palette = ["#1FAE96", "#17876F", "#3ED9C4", "#0F5C4E", "#5AC8B0",
               "#0B4A3E", "#2FBFA3", "#0D6653", "#4DD0BA", "#124F42"]
    colors = (palette * (len(holdings) // len(palette) + 1))[:len(holdings)]

    labels = [h["naam"] for h in holdings]
    values = [h.get("position_value") or 0 for h in holdings]

    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values, hole=0.55,
        marker=dict(colors=colors, line=dict(color="#101825", width=2)),
        texttemplate="%{percent:.0%}",  # afgerond, geen decimalen
        textposition="inside",
        textfont=dict(family="Inter, sans-serif", size=14, color="#EAEDF1"),
        hovertemplate="%{label}: %{value:,.0f} (%{percent:.0%})<extra></extra>",
    )])
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02,
                    font=dict(family="Inter, sans-serif", size=10, color="#8992A3"), bgcolor="rgba(0,0,0,0)"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=10, b=10, l=10, r=100),  # ruimte rechts voor de legenda, naast de taart
        height=320,
        font=dict(family="Inter, sans-serif", color="#EAEDF1"),
    )
    return fig


def refresh_portfolio_values(holdings: list, user_email: str, display_currency: str = "EUR") -> tuple:
    """
    Haalt voor elke positie de actuele koers EN de eigen valuta op, rekent
    om naar de gekozen weergave-valuta (display_currency), en werkt
    position_value bij. Rate-limited tot 1x per 10 seconden per gebruiker
    (ruim voldoende tegen per-ongeluk-dubbelklikken, zonder te frustreren).

    Geeft (success: bool, message: str) terug.
    """
    last_refresh = database.get_last_price_refresh(user_email)
    if last_refresh:
        last_refresh_dt = datetime.fromisoformat(last_refresh.replace("Z", "+00:00"))
        seconds_since = (datetime.now(timezone.utc) - last_refresh_dt).total_seconds()
        if seconds_since < 10:
            wait_seconds = int(10 - seconds_since)
            return False, f"Please wait {wait_seconds} more second(s) before updating again."

    fx_cache = {}
    updated_count = 0
    skipped_currencies = set()

    for holding in holdings:
        if not holding.get("shares"):
            continue
        try:
            ticker_obj = yf.Ticker(holding["ticker"])
            price_data = ticker_obj.history(period="1d")
            if price_data.empty:
                continue
            native_price = float(price_data["Close"].iloc[-1])
            native_currency = ticker_obj.info.get("currency", "USD")

            if native_currency not in fx_cache:
                fx_cache[native_currency] = get_fx_rate(native_currency, display_currency)
            fx_rate = fx_cache[native_currency]

            if fx_rate is None:
                skipped_currencies.add(native_currency)
                continue

            new_value = holding["shares"] * native_price * fx_rate
            database.update_holding_value(holding["id"], user_email, new_value, value_currency=display_currency)
            updated_count += 1
        except Exception:
            continue

    database.set_last_price_refresh(user_email, datetime.now(timezone.utc).isoformat())

    message = f"Updated {updated_count} of {len(holdings)} position(s) in {display_currency}."
    if skipped_currencies:
        message += f" Could not get exchange rate for: {', '.join(skipped_currencies)}."
    return True, message


def get_tickers_info(holdings: list) -> dict:
    """Haalt 1x per ticker de yfinance-info op, voor hergebruik door meerdere analyses (voorkomt dubbele aanroepen)."""
    infos = {}
    for h in holdings:
        try:
            infos[h["ticker"]] = yf.Ticker(h["ticker"]).info
        except Exception:
            infos[h["ticker"]] = {}
    return infos


def analyze_concentration(holdings: list, max_position_pct: float = 25.0) -> list:
    """Concentratie Risk-kaart: grootste positie vs. jouw eigen doel-max, + rebalancing-tip."""
    findings = []
    total_value = sum(h.get("position_value") or 0 for h in holdings)
    if total_value <= 0:
        return ["No position values available yet -- click 'Update portfolio value' first."]

    sorted_holdings = sorted(holdings, key=lambda h: h.get("position_value") or 0, reverse=True)
    largest = sorted_holdings[0]
    largest_value = largest.get("position_value") or 0
    largest_pct = largest_value / total_value * 100

    if largest_pct >= max_position_pct * 1.5:
        findings.append(f"🔴 High concentration: {largest['naam']} is {largest_pct:.0f}% of your tracked portfolio (your target max: {max_position_pct:.0f}%).")
    elif largest_pct > max_position_pct:
        findings.append(f"🟡 Above your target: {largest['naam']} is {largest_pct:.0f}% of your tracked portfolio (your target max: {max_position_pct:.0f}%).")
    else:
        findings.append(f"🟢 Within your target: largest position is {largest['naam']} at {largest_pct:.0f}% (your target max: {max_position_pct:.0f}%).")

    if len(holdings) > 3:
        top3_pct = sum((h.get("position_value") or 0) for h in sorted_holdings[:3]) / total_value * 100
        findings.append(f"Your top 3 positions represent {top3_pct:.0f}% of your tracked portfolio.")

    if largest_pct > max_position_pct:
        target_value = total_value * (max_position_pct / 100)
        trim_amount = largest_value - target_value
        findings.append(
            f"↔️ Rebalancing idea: trimming {largest['naam']} by roughly {trim_amount:,.0f} "
            f"would bring it down to your target of {max_position_pct:.0f}%."
        )

    return findings


def analyze_sectors(holdings: list, infos: dict, max_sector_pct: float = 40.0) -> list:
    """Sectoren-kaart: grootste sector vs. jouw eigen doel-max, + volledige uitsplitsing."""
    findings = []
    total_value = sum(h.get("position_value") or 0 for h in holdings)
    if total_value <= 0:
        return ["No position values available yet -- click 'Update portfolio value' first."]

    sector_values = {}
    for h in holdings:
        value = h.get("position_value") or 0
        sector = infos.get(h["ticker"], {}).get("sector")
        if sector:
            sector_values[sector] = sector_values.get(sector, 0) + value

    if not sector_values:
        return ["No sector data available for your tracked positions."]

    dominant_sector, dominant_value = max(sector_values.items(), key=lambda x: x[1])
    dominant_pct = dominant_value / total_value * 100

    if dominant_pct >= max_sector_pct * 1.5:
        level = "🔴 High concentration"
    elif dominant_pct > max_sector_pct:
        level = "🟡 Above your target"
    else:
        level = "🟢 Within your target"
    findings.append(f"{level}: {dominant_sector} makes up {dominant_pct:.0f}% of your tracked portfolio (your target max: {max_sector_pct:.0f}%).")

    breakdown = ", ".join(
        f"{s}: {v / total_value * 100:.0f}%" for s, v in sorted(sector_values.items(), key=lambda x: -x[1])
    )
    findings.append(f"Full breakdown -- {breakdown}.")

    return findings


def analyze_diversification(holdings: list, infos: dict) -> list:
    """Diversificatie-kaart: aantal posities + asset-type-mix."""
    findings = []
    total_value = sum(h.get("position_value") or 0 for h in holdings)
    if total_value <= 0:
        return ["No position values available yet -- click 'Update portfolio value' first."]

    if len(holdings) <= 3:
        findings.append(f"🟡 Only {len(holdings)} position(s) tracked -- limited diversification.")
    elif len(holdings) <= 7:
        findings.append(f"🟢 {len(holdings)} positions tracked -- reasonable spread.")
    else:
        findings.append(f"🟢 {len(holdings)} positions tracked -- well spread out.")

    type_values = {}
    for h in holdings:
        value = h.get("position_value") or 0
        asset_type = infos.get(h["ticker"], {}).get("quoteType", "UNKNOWN")
        type_values[asset_type] = type_values.get(asset_type, 0) + value

    if type_values:
        breakdown = ", ".join(
            f"{t.title()}: {v / total_value * 100:.0f}%" for t, v in sorted(type_values.items(), key=lambda x: -x[1])
        )
        findings.append(f"Asset type breakdown -- {breakdown}.")
        if len(type_values) == 1:
            findings.append("🟡 All tracked positions are the same asset type -- no cross-asset-class diversification.")

    return findings


def analyze_risk(holdings: list, infos: dict) -> list:
    """Risico-kaart: gewogen koers-winst-verhouding (de correlatie-matrix wordt apart als grafiek getoond)."""
    findings = []
    total_value = sum(h.get("position_value") or 0 for h in holdings)
    if total_value <= 0:
        return ["No position values available yet -- click 'Update portfolio value' first."]

    pe_pairs = [
        (infos.get(h["ticker"], {}).get("trailingPE"), h.get("position_value") or 0)
        for h in holdings
    ]
    pe_pairs = [(pe, w) for pe, w in pe_pairs if pe and w]
    if pe_pairs:
        weighted_pe = sum(pe * w for pe, w in pe_pairs) / sum(w for _, w in pe_pairs)
        if weighted_pe >= 25:
            findings.append(f"📊 Weighted average P/E: {weighted_pe:.1f}x -- relatively expensive vs. the long-term market average (roughly 15-20x).")
        elif weighted_pe <= 12:
            findings.append(f"📊 Weighted average P/E: {weighted_pe:.1f}x -- relatively cheap vs. the long-term market average (roughly 15-20x).")
        else:
            findings.append(f"📊 Weighted average P/E: {weighted_pe:.1f}x -- roughly in line with the long-term market average.")
    else:
        findings.append("No valuation (P/E) data available for your tracked positions.")

    return findings


def analyze_dividend(holdings: list, infos: dict) -> list:
    """Dividend-kaart: geschat jaarlijks dividend + aankomende ex-dividend-data."""
    findings = []
    total_annual_dividend = 0.0
    upcoming = []
    for h in holdings:
        info = infos.get(h["ticker"], {})
        shares = h.get("shares") or 0
        dividend_rate = info.get("dividendRate")
        if dividend_rate and shares:
            total_annual_dividend += dividend_rate * shares
        ex_div = info.get("exDividendDate")
        if ex_div:
            try:
                date_str = pd.Timestamp(ex_div, unit="s").date()
                upcoming.append((h["naam"], date_str))
            except Exception:
                pass

    if total_annual_dividend > 0:
        findings.append(
            f"💰 Estimated annual dividend income: ~{total_annual_dividend:,.0f} "
            f"(sum of each position's own currency, not converted -- treat as an approximation)."
        )
        if upcoming:
            upcoming.sort(key=lambda x: x[1])
            dates_str = ", ".join(f"{n} ({d})" for n, d in upcoming[:5])
            findings.append(f"Upcoming ex-dividend dates: {dates_str}.")
    else:
        findings.append("No dividend-paying positions detected (or data unavailable).")

    return findings


def build_daily_portfolio_stats(holdings: list):
    """Dag-op-dag statistieken: totale verandering, en beste/slechtste presteerder van gisteren."""
    performers = []
    total_value_today = 0.0
    total_value_yesterday = 0.0

    for h in holdings:
        shares = h.get("shares") or 0
        if not shares:
            continue
        try:
            hist = yf.Ticker(h["ticker"]).history(period="5d")
            if len(hist) < 2:
                continue
            price_today = float(hist["Close"].iloc[-1])
            price_yesterday = float(hist["Close"].iloc[-2])
            change_pct = (price_today / price_yesterday - 1) * 100
            performers.append({"naam": h["naam"], "change_pct": change_pct})
            total_value_today += shares * price_today
            total_value_yesterday += shares * price_yesterday
        except Exception:
            continue

    if not performers or total_value_yesterday <= 0:
        return None

    portfolio_change_pct = (total_value_today / total_value_yesterday - 1) * 100
    best = max(performers, key=lambda p: p["change_pct"])
    worst = min(performers, key=lambda p: p["change_pct"])

    return {
        "portfolio_change_pct": round(portfolio_change_pct, 2),
        "best_performer": best["naam"],
        "best_change_pct": round(best["change_pct"], 2),
        "worst_performer": worst["naam"],
        "worst_change_pct": round(worst["change_pct"], 2),
    }


def build_opportunities_today(holdings: list, watchlist_items: list) -> dict:
    """Leest de dagelijkse + wekelijkse screener-uitkomsten en telt hoeveel signalen ergens bij jou horen."""
    holding_tickers = {h["ticker"] for h in holdings}
    watchlist_tickers = {w["ticker"] for w in watchlist_items}

    daily_df = pd.read_csv("supertrend_signals_daily.csv") if os.path.exists("supertrend_signals_daily.csv") else None
    weekly_df = pd.read_csv("supertrend_signals.csv") if os.path.exists("supertrend_signals.csv") else None

    daily_count = len(daily_df) if daily_df is not None else 0
    weekly_count = len(weekly_df) if weekly_df is not None else 0

    all_signal_tickers = set()
    if daily_df is not None:
        all_signal_tickers |= set(daily_df["ticker"])
    if weekly_df is not None:
        all_signal_tickers |= set(weekly_df["ticker"])

    in_portfolio = all_signal_tickers & holding_tickers
    in_watchlist = (all_signal_tickers & watchlist_tickers) - in_portfolio
    new_opportunities = all_signal_tickers - holding_tickers - watchlist_tickers

    return {
        "total_signals": daily_count + weekly_count,
        "daily_signals": daily_count,
        "weekly_signals": weekly_count,
        "in_portfolio_count": len(in_portfolio),
        "in_watchlist_count": len(in_watchlist),
        "new_opportunities_count": len(new_opportunities),
    }


US_SECTOR_ETFS = {
    "Technology": "XLK", "Financials": "XLF", "Energy": "XLE", "Health Care": "XLV",
    "Consumer Discretionary": "XLY", "Consumer Staples": "XLP", "Industrials": "XLI",
    "Materials": "XLB", "Utilities": "XLU", "Real Estate": "XLRE", "Communication Services": "XLC",
}

# Geverifieerde iShares STOXX Europe 600 sector-ETF's (Xetra) -- een kleinere,
# minder gestandaardiseerde set dan de Amerikaanse SPDR-sector-ETF's, maar dit
# zijn de tickers die daadwerkelijk bestaan en op Yahoo Finance te vinden zijn.
EU_SECTOR_ETFS = {
    "Banks": "EXV1.DE", "Technology": "EXV3.DE", "Health Care": "EXV4.DE",
    "Telecommunications": "EXV2.DE", "Oil & Gas": "EXH1.DE", "Food & Beverage": "EXH3.DE",
    "Industrial Goods & Services": "EXH4.DE", "Utilities": "EXH9.DE",
    "Basic Resources": "EXV6.DE", "Automobiles & Parts": "EXV5.DE",
}


def build_sector_rotation(region: str = "US", period: str = "1mo") -> list:
    """
    Rangschikt sectoren op trailing-rendement -- een simpel sector-rotatie-
    signaal (welke sectoren doen het momenteel relatief goed/slecht?).
    Sectoren waarvan de ETF geen data teruggeeft, worden gewoon overgeslagen
    (geen crash bij een enkele niet-beschikbare ticker).
    """
    etfs = US_SECTOR_ETFS if region == "US" else EU_SECTOR_ETFS
    results = []
    for sector, ticker in etfs.items():
        try:
            hist = yf.Ticker(ticker).history(period=period)
            if len(hist) >= 2:
                ret = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100
                results.append({"sector": sector, "ticker": ticker, "return_pct": round(ret, 2)})
        except Exception:
            continue

    results.sort(key=lambda x: x["return_pct"], reverse=True)
    return results


def get_earnings_surprises_from_signals(max_items: int = 5, max_days_old: int = 60) -> list:
    """
    Licht signalen met een opvallende recente winst-verrassing uit de
    bestaande screener-CSV's (dagelijks + wekelijks) -- geen nieuwe
    data-ophaal nodig, dit zit al in de bestaande scores verwerkt.
    Alleen relevant tijdens 'earnings season' -- oude verrassingen
    (bv. van jaren geleden) worden genegeerd.
    """
    results = []
    for csv_file in ["supertrend_signals_daily.csv", "supertrend_signals.csv"]:
        if not os.path.exists(csv_file):
            continue
        try:
            df = pd.read_csv(csv_file)
        except Exception:
            continue
        if "earnings_surprise_pct" not in df.columns:
            continue
        df_with_earnings = df[df["earnings_surprise_pct"].notna()]
        for _, row in df_with_earnings.iterrows():
            earnings_date = row.get("earnings_date")
            if pd.isna(earnings_date):
                continue
            try:
                days_old = (datetime.now().date() - pd.to_datetime(earnings_date).date()).days
            except Exception:
                continue
            if not (0 <= days_old <= max_days_old):
                continue
            results.append({
                "ticker": row["ticker"],
                "earnings_surprise_pct": row["earnings_surprise_pct"],
                "earnings_beat": row.get("earnings_beat"),
                "earnings_date": row.get("earnings_date"),
            })

    results.sort(key=lambda x: abs(x["earnings_surprise_pct"]), reverse=True)
    return results[:max_items]


def get_top_news_for_tickers(holdings_and_watchlist: list, max_items: int = 3) -> list:
    """Haalt nieuws op voor alle meegegeven tickers, en geeft de meest recente 'max_items' items terug."""
    import screener as _screener  # lokale import: voorkomt een cirkelverwijzing bij module-laadtijd

    all_news = []
    for item in holdings_and_watchlist:
        try:
            news_items = _screener.get_recent_news(item["ticker"], max_items=3, days_back=3)
        except Exception:
            news_items = []
        for n in news_items:
            n["naam"] = item["naam"]
            all_news.append(n)

    all_news.sort(key=lambda x: x["published"], reverse=True)
    return all_news[:max_items]


def build_concentration_overview(holdings: list, infos: dict, cash_value: float = 0.0) -> dict:
    """
    Berekent de 'at a glance'-portfolio-kenmerken: top-positie%, verdeling
    over Crypto/Dividend/Growth/Other/Cash, en een 0-10-gezondheidsscore
    (concentratie + spreiding + categorie-balans).
    """
    holdings_value = sum(h.get("position_value") or 0 for h in holdings)
    total_value = holdings_value + cash_value

    if total_value <= 0:
        return None

    sorted_holdings = sorted(holdings, key=lambda h: h.get("position_value") or 0, reverse=True)
    top_holding = sorted_holdings[0] if sorted_holdings else None
    top_pct = (top_holding.get("position_value") or 0) / total_value * 100 if top_holding else 0.0

    category_values = {"Crypto": 0.0, "Dividend": 0.0, "Growth": 0.0, "Other": 0.0}
    for h in holdings:
        value = h.get("position_value") or 0
        info = infos.get(h["ticker"], {})
        quote_type = info.get("quoteType", "")
        has_dividend = bool(info.get("dividendRate"))
        if quote_type == "CRYPTOCURRENCY":
            category_values["Crypto"] += value
        elif has_dividend:
            category_values["Dividend"] += value
        elif quote_type in ("EQUITY", "ETF"):
            category_values["Growth"] += value
        else:
            category_values["Other"] += value

    category_pct = {k: v / total_value * 100 for k, v in category_values.items()}
    cash_pct = cash_value / total_value * 100

    max_category_pct = max(list(category_pct.values()) + [cash_pct])

    concentration_score = max(0.0, min(4.0, 4.0 - (top_pct / 100.0) * 8.0))
    n = len(holdings)
    if n <= 2:
        diversification_score = 0.0
    elif n <= 5:
        diversification_score = 1.5
    elif n <= 9:
        diversification_score = 2.5
    else:
        diversification_score = 3.0
    balance_score = max(0.0, 3.0 - (max_category_pct / 100.0) * 3.0)
    score = round(concentration_score + diversification_score + balance_score, 1)

    return {
        "top_holding_name": top_holding["naam"] if top_holding else None,
        "top_holding_pct": round(top_pct, 0),
        "category_pct": {k: round(v, 0) for k, v in category_pct.items()},
        "cash_pct": round(cash_pct, 0),
        "score": score,
    }


def build_correlation_matrix_chart(holdings: list):
    """Berekent de historische rendements-correlatie tussen je posities (6 maanden dagelijks), als heatmap."""
    if len(holdings) < 2:
        return None

    price_series = {}
    for h in holdings:
        try:
            hist = yf.Ticker(h["ticker"]).history(period="6mo")
            if len(hist) >= 20:
                price_series[h["naam"]] = hist["Close"].pct_change().dropna()
        except Exception:
            continue

    if len(price_series) < 2:
        return None

    df_returns = pd.DataFrame(price_series).dropna()
    if df_returns.empty or len(df_returns) < 10:
        return None

    corr = df_returns.corr()

    fig = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=corr.columns.tolist(),
        y=corr.columns.tolist(),
        colorscale=[[0, "#0B4A3E"], [0.5, "#101825"], [1, "#1FAE96"]],
        zmin=-1, zmax=1,
        text=[[f"{v:.2f}" for v in row] for row in corr.values],
        texttemplate="%{text}",
        textfont=dict(size=11, color="#EAEDF1"),
        hovertemplate="%{x} vs %{y}: %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text="Correlation matrix (6-month daily returns)", font=dict(family="Fraunces, serif", size=16, color="#EAEDF1")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=350,
        margin=dict(t=50, b=30, l=80, r=20),
        font=dict(family="Inter, sans-serif", color="#EAEDF1"),
        xaxis=dict(color="#8992A3"),
        yaxis=dict(color="#8992A3"),
    )
    return fig


def create_checkout_session(price_id: str, customer_email: str):
    """Maakt een Stripe Checkout Session aan voor een abonnement, geeft de sessie (met .url) terug."""
    stripe.api_key = st.secrets["stripe"]["secret_key"]
    app_url = st.secrets["app"]["url"]
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        customer_email=customer_email,
        success_url=f"{app_url}/?view=premium&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{app_url}/?view=premium",
    )
    return session


def verify_and_activate_premium(session_id: str) -> tuple:
    """
    Vraagt bij Stripe zelf na (met onze secret key, niet vertrouwend op de
    URL alleen) of deze sessie daadwerkelijk is afgerond. Zo ja: zet
    premium aan voor het bijbehorende e-mailadres.
    """
    stripe.api_key = st.secrets["stripe"]["secret_key"]
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        return False, None

    if session.status == "complete":
        customer_email = None
        if getattr(session, "customer_details", None):
            customer_email = session.customer_details.email
        if not customer_email:
            customer_email = session.customer_email
        if customer_email:
            database.set_premium_status(customer_email, True)
            if getattr(session, "customer", None):
                database.set_stripe_customer_id(customer_email, session.customer)
        return True, customer_email

    return False, None


def create_billing_portal_session(customer_id: str):
    """Maakt een Stripe Billing Portal-sessie aan -- hierin kan de klant zelf opzeggen/betaalmethode wijzigen."""
    stripe.api_key = st.secrets["stripe"]["secret_key"]
    app_url = st.secrets["app"]["url"]
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{app_url}/?view=premium",
    )
    return session


# --- Navigatie: leest de '?view=...'-parameter uit de URL. Geen parameter
#     (zoals bij het eerste bezoek) betekent: nog geen tabblad gekozen. ---
current_view = st.query_params.get("view", None)


def _nav_class(view_name: str) -> str:
    return "nav-link active" if current_view == view_name else "nav-link"


def _nav_class_any(view_names: list) -> str:
    return "nav-link active" if current_view in view_names else "nav-link"


header_col, login_col = st.columns([5, 1])

with header_col:
    st.markdown(
        f"""
        <div class="app-header">
            <a href="?view=today" class="app-header-top" target="_self">
                <svg width="42" height="42" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                    <rect x="6" y="6" width="36" height="36" rx="8" fill="none" stroke="#1FAE96"
                          stroke-width="2.5" transform="rotate(45 24 24)"/>
                    <polyline points="13,30 20,22 26,26 33,15" fill="none" stroke="#1FAE96"
                              stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                    <circle cx="33" cy="15" r="2.3" fill="#1FAE96"/>
                </svg>
                <div>
                    <h1>Hesty's</h1>
                    <div class="tagline">YOUR PERSONAL INVESTMENT ASSISTANT</div>
                </div>
            </a>
            <div class="nav-bar">
                <a href="?view=today" class="{_nav_class('today')}" target="_self">Today</a>
                <a href="?view=portfolio" class="{_nav_class('portfolio')}" target="_self">My Portfolio</a>
                <a href="?view=analyze" class="{_nav_class('analyze')}" target="_self">Analyze</a>
                <a href="?view=discover" class="{_nav_class('discover')}" target="_self">Discover</a>
                <a href="?view=support" class="{_nav_class('support')}" target="_self">Support</a>
                <a href="?view=premium" class="{_nav_class('premium')}" target="_self">Premium</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with login_col:
    st.markdown("<div style='height: 1.4rem'></div>", unsafe_allow_html=True)  # verticaal uitlijnen met het logo
    if st.user.is_logged_in:
        st.markdown(
            f'<a href="?view=settings" class="account-link {" active" if current_view == "settings" else ""}" '
            f'target="_self">&#9881; {st.user.name}</a>',
            unsafe_allow_html=True,
        )
        st.button("Log out", on_click=st.logout, key="header_logout")
    else:
        st.button("Log in", on_click=st.login, key="header_login", type="primary")

# ============================================================
# VIEW: TODAY
# ============================================================
if current_view == "today":
    st.markdown("### Today")

    if not st.user.is_logged_in:
        st.write("Here are your daily points that deserve your attention.")
        st.info("Log in (top right), then add positions under My Portfolio or your Watchlist "
                 "to get personal signals and news here.")
        st.markdown("#### Discover")
        st.write(
            "Scans the AEX, Nasdaq-100, S&P 500, DAX, and CAC 40 for stocks that just turned "
            "bullish on a Supertrend indicator (weekly and daily variants), each scored on "
            "technical and fundamental factors. Public, no login required."
        )
    else:
        import database
        import screener as _screener_module  # noqa: F401 -- zorgt dat get_top_news_for_tickers 'm kan importeren

        user_email = st.user.email
        holdings = database.get_user_holdings(user_email)
        watchlist_items = database.get_user_holdings(user_email, is_watchlist=True)

        st.write("Here are your daily points that deserve your attention.")

        if not holdings and not watchlist_items:
            st.info("Add assets under My Portfolio or your Watchlist to get personal signals and news here.")
        else:
            tracked_items = holdings + watchlist_items

            # --- Top nieuws (portfolio + watchlist) ---
            with st.container(border=True):
                st.markdown("**Top news for you**")
                st.caption("The 5 most recent news items across your portfolio and watchlist "
                           "(up to 3 per position, from the last 3 days), most recent first.")
                with st.spinner("Checking news..."):
                    top_news = get_top_news_for_tickers(tracked_items, max_items=5)
                if top_news:
                    for n in top_news:
                        pub_date = n["published"].strftime("%Y-%m-%d")
                        st.markdown(f"- **{n['naam']}**: [{n['title']}]({n['link']}) *({n['publisher']}, {pub_date})*")
                else:
                    st.caption("No recent news found for your tracked positions.")

            # --- Portfolio-kenmerken ---
            if holdings:
                with st.container(border=True):
                    st.markdown("**Your portfolio today**")
                    with st.spinner("Checking today's price moves..."):
                        daily_stats = build_daily_portfolio_stats(holdings)
                    cash_value = database.get_cash_value(user_email)
                    infos = get_tickers_info(holdings)
                    overview = build_concentration_overview(holdings, infos, cash_value)

                    dcol1, dcol2, dcol3, dcol4 = st.columns(4)
                    with dcol1:
                        if daily_stats:
                            st.metric("Vs. yesterday", f"{daily_stats['portfolio_change_pct']:+.1f}%")
                        else:
                            st.metric("Vs. yesterday", "n/a")
                    with dcol2:
                        if daily_stats:
                            st.metric("Best today", daily_stats["best_performer"], f"{daily_stats['best_change_pct']:+.1f}%")
                        else:
                            st.metric("Best today", "n/a")
                    with dcol3:
                        if daily_stats:
                            st.metric("Worst today", daily_stats["worst_performer"], f"{daily_stats['worst_change_pct']:+.1f}%")
                        else:
                            st.metric("Worst today", "n/a")
                    with dcol4:
                        if overview:
                            st.metric("Cash", f"{overview['cash_pct']:.0f}%")
                        else:
                            st.metric("Cash", "n/a")

            # --- Opportunities today ---
            with st.container(border=True):
                st.markdown("**Opportunities today**")
                opportunities = build_opportunities_today(holdings, watchlist_items)
                st.write(
                    f"**{opportunities['total_signals']}** signal(s) found "
                    f"({opportunities['daily_signals']} daily, {opportunities['weekly_signals']} weekly) -- "
                    f"**{opportunities['in_portfolio_count']}** relate to your portfolio, "
                    f"**{opportunities['in_watchlist_count']}** are on your watchlist, "
                    f"**{opportunities['new_opportunities_count']}** are new ideas."
                )
                st.markdown(
                    'See the full list under <a href="?view=discover" class="inline-link" target="_self">Discover</a>.',
                    unsafe_allow_html=True,
                )

            # --- Earnings surprises (alleen je eigen portfolio + watchlist, max 2 dagen oud) ---
            def _is_recent_earnings(earnings_date_str, max_days=2):
                try:
                    earnings_date = pd.to_datetime(earnings_date_str).date()
                    days_since = (datetime.now().date() - earnings_date).days
                    return 0 <= days_since <= max_days
                except Exception:
                    return False

            tracked_tickers = {item["ticker"] for item in tracked_items}
            personal_surprises = [
                s for s in get_earnings_surprises_from_signals(max_items=50)
                if s["ticker"] in tracked_tickers and _is_recent_earnings(s["earnings_date"])
            ]
            with st.container(border=True):
                st.markdown("**Earnings surprises for you**")
                if personal_surprises:
                    for s in personal_surprises[:5]:
                        emoji = "🟢" if s["earnings_beat"] else "🔴"
                        st.markdown(f"- {emoji} **{s['ticker']}**: {s['earnings_surprise_pct']:+.1f}% surprise ({s['earnings_date']})")
                else:
                    st.caption("No recent earnings surprises on your positions (last 2 days).")

            # --- Algemeen marktnieuws (simpele proxy: S&P 500 + AEX) ---
            with st.container(border=True):
                st.markdown("**Market news**")
                with st.spinner("Checking market news..."):
                    market_news = get_top_news_for_tickers(
                        [{"naam": "S&P 500", "ticker": "^GSPC"}, {"naam": "AEX", "ticker": "^AEX"}],
                        max_items=3,
                    )
                if market_news:
                    for n in market_news:
                        pub_date = n["published"].strftime("%Y-%m-%d")
                        st.markdown(f"- [{n['title']}]({n['link']}) *({n['publisher']}, {pub_date})*")
                else:
                    st.caption("No market news available right now.")

# ============================================================
# VIEW: SCREENER (public, no login required)
# ============================================================
elif current_view == "discover":
    st.markdown("### Discover")

    # --- Daily Top Movers (bovenaan -- dit is de enige echt DAGELIJKSE check hier) ---
    with st.expander("📊 Daily Top Movers", expanded=True):
        if os.path.exists("top_movers.csv"):
            st.caption(f"Last updated: {file_last_modified('top_movers.csv')} -- updates once daily.")
            df_movers = pd.read_csv("top_movers.csv").dropna(subset=["change_pct"])
            mcol1, mcol2 = st.columns(2)
            with mcol1:
                st.markdown("Top gainers")
                gainers = df_movers.sort_values("change_pct", ascending=False).head(5).rename(
                    columns={"ticker": "Ticker", "change_pct": "Change %"}
                )
                st.dataframe(gainers.style.format({"Change %": "{:+.1f}%"}), width=220, hide_index=True)
            with mcol2:
                st.markdown("Top losers")
                losers = df_movers.sort_values("change_pct", ascending=True).head(5).rename(
                    columns={"ticker": "Ticker", "change_pct": "Change %"}
                )
                st.dataframe(losers.style.format({"Change %": "{:+.1f}%"}), width=220, hide_index=True)
        else:
            st.caption("No data yet -- this updates once daily via the scheduled scan. Check back tomorrow.")

    st.markdown(
        """
        <div style="background: linear-gradient(135deg, rgba(31,174,150,0.14), rgba(31,174,150,0.02));
                    border: 1px solid rgba(31,174,150,0.35); border-radius: 10px;
                    padding: 1rem 1.25rem; margin: 0.5rem 0 0.75rem 0;">
            <div style="color:#1FAE96; font-weight:700; font-size:0.75rem; letter-spacing:1.5px; text-transform:uppercase;">
                Hesty's Signature Signals
            </div>
            <div style="color:#EAEDF1; font-size:1.05rem; font-weight:600; margin-top:3px;">
                3 specially-built signals, each with its own investing style -- this is the core of Hesty's.
            </div>
            <div style="color:#8992A3; font-size:0.85rem; margin-top:10px; line-height:1.6;">
                📡 <b style="color:#EAEDF1;">Momentocrats</b> -- momentum + quality, for swing trades (days-weeks)<br>
                🐦 <b style="color:#EAEDF1;">Snowballers</b> -- quality at a good price, for the long-term investor<br>
                🚀 <b style="color:#EAEDF1;">Rocket List</b> -- accelerating growth, for higher risk/reward
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Sector rotation and earnings surprises further down are market context, not individual stock picks.")

    def _email_pref_toggle(signal_key: str, label: str, current_value: bool):
        """Kleine, inline 'mail me dit wekelijks'-toggle, direct binnen een signaal-kaart."""
        if not st.user.is_logged_in:
            st.caption("Log in (top right) to get this signal by email, weekly.")
            return
        new_value = st.checkbox(label, value=current_value, key=f"inline_{signal_key}")
        if new_value != current_value:
            if st.button("Save", key=f"save_{signal_key}"):
                import database as _database
                _database.set_signal_email_preference(st.user.email, signal_key, new_value)
                st.success("Saved!")
                st.rerun()

    if st.user.is_logged_in:
        import database
        _current_prefs = database.get_user_preferences(st.user.email)
        _is_premium_discover = database.is_premium_user(st.user.email)
    else:
        _current_prefs = {}
        _is_premium_discover = False
    _signal_display_limit = 10 if _is_premium_discover else 3

    # --- Momentocrats (bestaande, ongewijzigde signaal-logica) ---
    with st.expander("📡 Momentocrats", expanded=True):
        st.caption("Technical momentum + fundamental quality, combined. Best for swing trades (days-weeks).")
        timeframe = st.radio("Timeframe", ["Daily", "Weekly"], horizontal=True, key="screener_timeframe")
        csv_file = "supertrend_signals_daily.csv" if timeframe == "Daily" else "supertrend_signals.csv"

        st.caption(f"Last updated: {file_last_modified(csv_file)}")

        df_screener = load_screener_data(csv_file)
        if df_screener is None or df_screener.empty:
            st.info("No results yet -- check back after the next scheduled scan.")
        else:
            df_screener = df_screener.sort_values("score", ascending=False)

            min_score = st.slider("Minimum score", float(df_screener["score"].min()),
                                   float(df_screener["score"].max()), float(df_screener["score"].min()))
            filtered = df_screener[df_screener["score"] >= min_score].copy()

            # 'benchmark' is interne informatie (welke index gebruikt is voor de
            # vergelijking) -- niet interessant genoeg om te tonen, dus weg ermee
            filtered.drop(columns=["benchmark"], errors="ignore", inplace=True)

            # Nette, leesbare Engelse kolomnamen i.p.v. de ruwe Python-veldnamen met
            # underscores -- bevat zowel de wekelijkse (weken_*) als dagelijkse
            # (dagen_*) veldnamen, aangezien beide varianten hier getoond worden
            column_labels = {
                "ticker": "Ticker", "flip_date": "Flip Date",
                "weken_geleden": "Weeks Ago", "dagen_geleden": "Days Ago",
                "voorgaande_trend_weken": "Prior Trend (Weeks)", "voorgaande_trend_dagen": "Prior Trend (Days)",
                "prijs_bij_omslag": "Price at Flip",
                "prijs_nu": "Price Now", "sinds_omslag_pct": "Since Flip",
                "boven_ema20": "Above EMA", "boven_ema": "Above EMA",
                "relatieve_sterkte": "Relative Strength", "roic_pct": "ROIC", "roic_trend": "ROIC Trend",
                "volume_bevestigd": "Volume Confirmed", "earnings_surprise_pct": "Earnings Surprise",
                "earnings_beat": "Earnings Beat", "earnings_date": "Earnings Date",
                "weken_sinds_earnings": "Weeks Since Earnings", "dagen_sinds_earnings": "Days Since Earnings",
                "fair_value": "Fair Value",
                "afwijking_fair_value_pct": "Vs Fair Value", "score": "Score",
            }
            filtered.rename(columns=column_labels, inplace=True)

            # Score als 3e kolom, de rest in de logische volgorde erachter
            preferred_order = [
                "Ticker", "Flip Date", "Score", "Weeks Ago", "Days Ago",
                "Prior Trend (Weeks)", "Prior Trend (Days)",
                "Price at Flip", "Price Now", "Since Flip", "Above EMA",
                "Relative Strength", "ROIC", "ROIC Trend", "Volume Confirmed",
                "Earnings Surprise", "Earnings Beat", "Earnings Date",
                "Weeks Since Earnings", "Days Since Earnings", "Fair Value", "Vs Fair Value",
            ]
            ordered_cols = [c for c in preferred_order if c in filtered.columns]
            ordered_cols += [c for c in filtered.columns if c not in ordered_cols]  # vangnet voor eventuele extra kolommen
            filtered = filtered[ordered_cols]

            format_dict = {
                "Price at Flip": "{:.2f}", "Price Now": "{:.2f}",
                "Since Flip": "{:+.2f}%", "Relative Strength": "{:+.2f}%",
                "ROIC": "{:+.1f}%", "Score": "{:.2f}",
                "Earnings Surprise": "{:+.1f}%", "Vs Fair Value": "{:+.1f}%",
                "Fair Value": "{:.2f}", "Weeks Since Earnings": "{:.0f}",
            }
            format_dict = {k: v for k, v in format_dict.items() if k in filtered.columns}

            total_matching = len(filtered)
            filtered = filtered.head(_signal_display_limit)

            st.dataframe(
                filtered.style.format(format_dict, na_rep="unknown")
                              .background_gradient(subset=["Score"], cmap="Greens")
                              .background_gradient(subset=["Relative Strength"], cmap="RdYlGn"),
                width="stretch",
                height=500,
            )
            st.caption(f"{len(filtered)} of {total_matching} matching signals shown.")
            if not _is_premium_discover and total_matching > _signal_display_limit:
                st.info(f"🔒 Showing the top {_signal_display_limit} of {total_matching} matching signals. "
                        f"Upgrade to Premium for the full top 10.")

        st.divider()
        _email_pref_toggle("wants_momentocrats_email", f"📧 Email me this weekly (top {_signal_display_limit})",
                            _current_prefs.get("wants_momentocrats_email", False))

    # --- Snowball Signal (nieuw, wekelijks-only: kwaliteit + goede prijs) ---
    with st.expander("🐦 Snowballers"):
        st.caption("Quality companies trading below fair value, with low volatility. For the "
                   "long-term investor -- no fresh trend flip required.")
        st.caption(f"Updates weekly (same schedule as Momentocrats' weekly scan). "
                   f"Last updated: {file_last_modified('snowball_signals.csv')}.")
        if os.path.exists("snowball_signals.csv"):
            df_snowball = pd.read_csv("snowball_signals.csv")
            if not df_snowball.empty:
                df_display = df_snowball.rename(columns={
                    "ticker": "Ticker", "prijs_nu": "Price", "roic_pct": "ROIC",
                    "afwijking_fair_value_pct": "Vs Fair Value", "volatiliteit_pct": "Volatility",
                })[["Ticker", "Price", "ROIC", "Vs Fair Value", "Volatility"]]
                total_snowball = len(df_display)
                df_display = df_display.head(_signal_display_limit)
                st.dataframe(
                    df_display.style.format({
                        "Price": "{:.2f}", "ROIC": "{:+.1f}%", "Vs Fair Value": "{:+.1f}%", "Volatility": "{:.1f}%",
                    }),
                    width="stretch", hide_index=True,
                )
                st.caption(f"{len(df_display)} of {total_snowball} matching stocks shown.")
                if not _is_premium_discover and total_snowball > _signal_display_limit:
                    st.info(f"🔒 Showing the top {_signal_display_limit} of {total_snowball} matching stocks. "
                            f"Upgrade to Premium for the full top 10.")
            else:
                st.caption("No stocks currently meet the Snowballers criteria.")
        else:
            st.caption("No data yet -- this updates once a week via the scheduled scan.")

        st.divider()
        _email_pref_toggle("wants_snowball_email", f"📧 Email me this weekly (top {_signal_display_limit})",
                            _current_prefs.get("wants_snowball_email", False))

    # --- Rocket List (nieuw, wekelijks-only: versnellende groei + momentum) ---
    with st.expander("🚀 Rocket List"):
        st.caption("Accelerating growth stocks with strong momentum. For investors comfortable "
                   "with more risk in exchange for growth potential.")
        st.caption(f"Updates weekly (same schedule as Momentocrats' weekly scan). "
                   f"Last updated: {file_last_modified('rocket_list_signals.csv')}.")
        if os.path.exists("rocket_list_signals.csv"):
            df_rocket = pd.read_csv("rocket_list_signals.csv")
            if not df_rocket.empty:
                df_display = df_rocket.rename(columns={
                    "ticker": "Ticker", "prijs_nu": "Price", "groei_pct": "Growth",
                    "relatieve_sterkte": "Relative Strength",
                })[["Ticker", "Price", "Growth", "Relative Strength"]]
                total_rocket = len(df_display)
                df_display = df_display.head(_signal_display_limit)
                st.dataframe(
                    df_display.style.format({"Price": "{:.2f}", "Growth": "{:+.1f}%", "Relative Strength": "{:+.1f}%"}),
                    width="stretch", hide_index=True,
                )
                st.caption(f"{len(df_display)} of {total_rocket} matching stocks shown.")
                if not _is_premium_discover and total_rocket > _signal_display_limit:
                    st.info(f"🔒 Showing the top {_signal_display_limit} of {total_rocket} matching stocks. "
                            f"Upgrade to Premium for the full top 10.")
            else:
                st.caption("No stocks currently meet the Rocket List criteria.")
        else:
            st.caption("No data yet -- this updates once a week via the scheduled scan.")

        st.divider()
        _email_pref_toggle("wants_rocket_email", f"📧 Email me this weekly (top {_signal_display_limit})",
                            _current_prefs.get("wants_rocket_email", False))

    # --- Sector rotation (nieuw) ---
    with st.expander("🔄 Sector rotation"):
        st.caption("Which sectors are relatively strong or weak right now (trailing 1-month return)?")
        st.caption("Live data -- recalculated fresh every time you open this.")
        region = st.radio("Region", ["US", "EU"], horizontal=True, key="sector_region")
        with st.spinner("Checking sector performance..."):
            rotation = build_sector_rotation(region=region, period="1mo")
        if rotation:
            df_rotation = pd.DataFrame(rotation)[["sector", "return_pct"]]
            df_rotation.columns = ["Sector", "1-Month Return"]
            st.dataframe(
                df_rotation.style.format({"1-Month Return": "{:+.1f}%"})
                                  .background_gradient(subset=["1-Month Return"], cmap="RdYlGn"),
                width=320,
                hide_index=True,
            )
        else:
            st.caption("No sector data available right now.")

    # --- Earnings surprises (nieuw, hergebruikt bestaande screener-data) ---
    with st.expander("💰 Earnings surprises"):
        st.caption("Notable earnings beats/misses among today's and this week's signals -- "
                   "only shown during earnings season (last 60 days).")
        st.caption(f"Sourced from the daily and weekly scans. Last updated: "
                   f"{file_last_modified('supertrend_signals_daily.csv')} (daily), "
                   f"{file_last_modified('supertrend_signals.csv')} (weekly).")
        surprises = get_earnings_surprises_from_signals(max_items=5)
        if surprises:
            for s in surprises:
                emoji = "🟢" if s["earnings_beat"] else "🔴"
                st.markdown(f"- {emoji} **{s['ticker']}**: {s['earnings_surprise_pct']:+.1f}% surprise ({s['earnings_date']})")
        else:
            st.caption("No notable earnings surprises right now (or we're between earnings seasons).")

# ============================================================
# VIEW: MY PORTFOLIO (personal, login required)
# ============================================================
elif current_view == "portfolio":
    if not st.user.is_logged_in:
        st.markdown(
            '<div class="privacy-seal">&#128274; PRIVATE &middot; visible only to you</div>',
            unsafe_allow_html=True,
        )
        st.info("Log in (top right) to track your own positions. No one else can see what you add.")
        st.stop()

    import database
    from portfolio_watch import check_holding

    user_email = st.user.email
    st.markdown(
        '<div class="privacy-seal">&#128274; PRIVATE &middot; visible only to you</div>',
        unsafe_allow_html=True,
    )
    st.subheader(f"Welcome, {st.user.name}")

    holdings = database.get_user_holdings(user_email)
    holdings.sort(key=lambda h: h.get("position_value") or 0, reverse=True)
    is_premium = database.is_premium_user(user_email)

    if not holdings:
        st.info("You haven't added any positions yet -- add your first one under 'Manage' below.")

    # ============================================================
    # 1. OVERVIEW -- totaal, valuta, pie chart, en de tabel, samen in 1 vak
    # ============================================================
    if holdings:
        with st.container(border=True):
            st.markdown("**Overview**")
            display_currency = st.selectbox("Display currency", ["EUR", "USD"], key="display_currency")

            total_value = sum(h.get("position_value") or 0 for h in holdings)
            stored_currency = next((h.get("value_currency") for h in holdings if h.get("value_currency")), None)
            currency_symbol = "€" if display_currency == "EUR" else "$"

            if total_value > 0 and stored_currency == display_currency:
                st.markdown(f"#### Total: {currency_symbol}{total_value:,.0f}")
            elif total_value > 0:
                st.warning(f"Values currently shown are in {stored_currency}, not {display_currency}. Click 'Update portfolio value' to convert.")
                st.markdown(f"#### Total: {'€' if stored_currency == 'EUR' else '$'}{total_value:,.0f} ({stored_currency})")
            else:
                st.caption("Click 'Update portfolio value' to fetch current prices.")

            if st.button("Update portfolio value"):
                with st.spinner("Fetching current prices and exchange rates..."):
                    success, message = refresh_portfolio_values(holdings, user_email, display_currency)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.warning(message)

            if total_value > 0:
                with st.spinner("Analyzing portfolio mix..."):
                    infos_for_overview = get_tickers_info(holdings)
                    cash_value_for_overview = database.get_cash_value(user_email)
                    overview = build_concentration_overview(holdings, infos_for_overview, cash_value_for_overview)

                if overview:
                    ocol1, ocol2, ocol3, ocol4, ocol5, ocol6 = st.columns(6)
                    with ocol1:
                        st.metric("Top holding", f"{overview['top_holding_pct']:.0f}%", help=overview["top_holding_name"])
                    with ocol2:
                        st.metric("Crypto", f"{overview['category_pct']['Crypto']:.0f}%")
                    with ocol3:
                        st.metric("Dividend", f"{overview['category_pct']['Dividend']:.0f}%")
                    with ocol4:
                        st.metric("Growth", f"{overview['category_pct']['Growth']:.0f}%")
                    with ocol5:
                        st.metric("Cash", f"{overview['cash_pct']:.0f}%")
                    with ocol6:
                        st.metric("Score", f"{overview['score']:.1f}/10")

            def _format_pct(holding):
                if total_value <= 0:
                    return "-"
                value = holding.get("position_value") or 0
                return f"{value / total_value * 100:.0f}%"

            def _format_value(holding):
                value = holding.get("position_value")
                sym = "€" if holding.get("value_currency") == "EUR" else "$"
                return f"{sym}{value:,.0f}" if value else "-"

            rows_html = "".join(
                f'<tr><td>{h["naam"]}</td><td><code>{h["ticker"]}</code></td>'
                f'<td>{h.get("shares") or "-"}</td><td>{_format_value(h)}</td><td>{_format_pct(h)}</td></tr>'
                for h in holdings
            )
            st.markdown(
                f"""
                <table class="positions-table">
                    <thead><tr><th>Name</th><th>Ticker</th><th>Shares</th><th>Value</th><th>% of portfolio</th></tr></thead>
                    <tbody>{rows_html}</tbody>
                </table>
                """,
                unsafe_allow_html=True,
            )

    # ============================================================
    # 3. MANAGE -- 3 losse, individueel uitklapbare vakjes
    # ============================================================
    with st.container(border=True):
        st.markdown("**Manage**")

        with st.expander("Add a new position", expanded=not holdings):
            search_query = st.text_input(
                "Search for a company, crypto, commodity, or precious metal (e.g. 'Tesla', 'Bitcoin', 'Gold')",
                key="ticker_search",
            )
            shares_input = st.number_input(
                "Number of shares/units you hold (optional -- needed for value tracking and portfolio analysis)",
                min_value=0.0, value=0.0, step=1.0,
            )

            selected_symbol = None
            selected_name = None

            if search_query:
                try:
                    search_results = yf.Search(search_query, max_results=8).quotes
                except Exception as exc:
                    search_results = []
                    st.caption(f"Search failed: {exc}")

                if search_results:
                    options = {}
                    for r in search_results:
                        name = r.get("shortname") or r.get("longname") or r.get("symbol")
                        label = f"{name} ({r.get('symbol')}) -- {r.get('exchange', '')}"
                        options[label] = r

                    chosen_label = st.selectbox("Choose the right match", list(options.keys()))
                    chosen = options[chosen_label]
                    selected_symbol = chosen.get("symbol")
                    selected_name = chosen.get("shortname") or chosen.get("longname") or selected_symbol
                else:
                    st.caption("No results found for this search -- try a different name.")

            if selected_symbol and st.button("Add to my portfolio", type="primary"):
                with st.spinner(f"Checking data for {selected_symbol}..."):
                    try:
                        test_df = yf.Ticker(selected_symbol).history(period="5d")
                    except Exception as exc:
                        test_df = None
                        st.error(f"Could not validate {selected_symbol}: {exc}")

                if test_df is not None and test_df.empty:
                    st.error(f"No recent price data found for {selected_symbol} -- not added.")
                elif test_df is not None:
                    if len(holdings) >= 10 and not is_premium:
                        st.error(
                            "You've reached the free plan limit of 10 tracked positions. "
                            "Upgrade to Premium for unlimited tracking."
                        )
                    else:
                        database.add_holding(
                            user_email, selected_name, selected_symbol,
                            shares = shares_input if shares_input > 0 else None,
                        )
                        st.success(f"{selected_name} ({selected_symbol}) added!")
                        st.rerun()

        if holdings:
            holding_options = {f"{h['naam']} ({h['ticker']})": h for h in holdings}

            with st.expander("Edit shares", expanded=False):
                ecol1, ecol2, ecol3 = st.columns([3, 2, 1])
                with ecol1:
                    edit_label = st.selectbox(
                        "Position to edit", list(holding_options.keys()), key="edit_select", label_visibility="collapsed"
                    )
                with ecol2:
                    current_shares = holding_options[edit_label].get("shares") or 0.0
                    new_shares = st.number_input(
                        "New share count", min_value=0.0, value=float(current_shares), step=1.0,
                        key="edit_shares_input", label_visibility="collapsed",
                    )
                with ecol3:
                    if st.button("Save shares"):
                        database.update_holding_shares(holding_options[edit_label]["id"], user_email, new_shares)
                        st.rerun()

            with st.expander("Remove a position", expanded=False):
                rcol1, rcol2 = st.columns([4, 1])
                with rcol1:
                    to_remove_label = st.selectbox(
                        "Position to remove", list(holding_options.keys()), key="remove_select", label_visibility="collapsed"
                    )
                with rcol2:
                    if st.button("Remove"):
                        database.delete_holding(holding_options[to_remove_label]["id"], user_email)
                        st.rerun()

    # ============================================================
    # WATCHLIST -- volgen zonder eigendom, voor gepersonaliseerde info op Today
    # ============================================================
    with st.container(border=True):
        st.markdown("**Watchlist**")
        st.caption("Track tickers you don't own yet -- they'll show up with personalized "
                   "signals and news on the Today page.")

        watchlist_items = database.get_user_holdings(user_email, is_watchlist=True)

        if watchlist_items:
            rows_html = "".join(
                f'<tr><td>{w["naam"]}</td><td><code>{w["ticker"]}</code></td></tr>'
                for w in watchlist_items
            )
            st.markdown(
                f"""
                <table class="positions-table">
                    <thead><tr><th>Name</th><th>Ticker</th></tr></thead>
                    <tbody>{rows_html}</tbody>
                </table>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.caption("Your watchlist is empty.")

        with st.expander("Add to watchlist", expanded=not watchlist_items):
            watchlist_search = st.text_input(
                "Search for a company, crypto, commodity, or precious metal", key="watchlist_search",
            )
            w_selected_symbol = None
            w_selected_name = None
            if watchlist_search:
                try:
                    w_search_results = yf.Search(watchlist_search, max_results=8).quotes
                except Exception as exc:
                    w_search_results = []
                    st.caption(f"Search failed: {exc}")
                if w_search_results:
                    w_options = {}
                    for r in w_search_results:
                        name = r.get("shortname") or r.get("longname") or r.get("symbol")
                        label = f"{name} ({r.get('symbol')}) -- {r.get('exchange', '')}"
                        w_options[label] = r
                    w_chosen_label = st.selectbox("Choose the right match", list(w_options.keys()), key="watchlist_match")
                    w_chosen = w_options[w_chosen_label]
                    w_selected_symbol = w_chosen.get("symbol")
                    w_selected_name = w_chosen.get("shortname") or w_chosen.get("longname") or w_selected_symbol
                else:
                    st.caption("No results found for this search -- try a different name.")

            if w_selected_symbol and st.button("Add to watchlist", type="primary"):
                database.add_holding(user_email, w_selected_name, w_selected_symbol, is_watchlist=True)
                st.success(f"{w_selected_name} ({w_selected_symbol}) added to watchlist!")
                st.rerun()

        if watchlist_items:
            with st.expander("Remove from watchlist", expanded=False):
                w_remove_options = {f"{w['naam']} ({w['ticker']})": w["id"] for w in watchlist_items}
                wcol1, wcol2 = st.columns([4, 1])
                with wcol1:
                    w_to_remove = st.selectbox(
                        "Item to remove", list(w_remove_options.keys()),
                        key="watchlist_remove_select", label_visibility="collapsed",
                    )
                with wcol2:
                    if st.button("Remove", key="watchlist_remove_btn"):
                        database.delete_holding(w_remove_options[w_to_remove], user_email)
                        st.rerun()

    st.caption("Manage email preferences and cash amount under Instellingen. "
               "You'll also automatically receive a weekly email with this update, "
               "at the address you're logged in with.")

elif current_view == "analyze":
    st.markdown("### Analyze")

    if not st.user.is_logged_in:
        st.info("Log in (top right) to analyze your portfolio.")
        st.stop()

    import database
    from portfolio_watch import check_holding

    user_email = st.user.email
    holdings = database.get_user_holdings(user_email)
    holdings.sort(key=lambda h: h.get("position_value") or 0, reverse=True)
    is_premium = database.is_premium_user(user_email)

    if not holdings:
        st.info("Add positions under My Portfolio to see your analysis here.")
        st.stop()

    risk_profile = database.get_risk_profile(user_email)
    infos = get_tickers_info(holdings)

    # --- Concentratie Risk ---
    with st.expander("🎯 Concentration Risk", expanded=True):
        for finding in analyze_concentration(holdings, risk_profile["max_position_pct"]):
            st.markdown(f"- {finding}")

        total_value_check = sum(h.get("position_value") or 0 for h in holdings)
        if total_value_check > 0:
            largest_check = max(holdings, key=lambda h: h.get("position_value") or 0)
            largest_pct_check = (largest_check.get("position_value") or 0) / total_value_check * 100
            if largest_pct_check > risk_profile["max_position_pct"]:
                st.caption("One way to gradually correct an overweight position without a big, "
                           "one-time move: adjust future contributions with the Smart DCA Assistant.")
                st.markdown(
                    '<a href="?view=premium" class="button-link" target="_self">🧠 Buy smarter with DCA &rarr;</a>',
                    unsafe_allow_html=True,
                )

    # --- Sectoren ---
    with st.expander("🏭 Sectors"):
        for finding in analyze_sectors(holdings, infos, risk_profile["max_sector_pct"]):
            st.markdown(f"- {finding}")

        sector_values_check = {}
        for h in holdings:
            value = h.get("position_value") or 0
            sector = infos.get(h["ticker"], {}).get("sector")
            if sector:
                sector_values_check[sector] = sector_values_check.get(sector, 0) + value
        total_value_for_sectors = sum(h.get("position_value") or 0 for h in holdings)
        if sector_values_check and total_value_for_sectors > 0:
            dominant_sector_pct = max(sector_values_check.values()) / total_value_for_sectors * 100
            if dominant_sector_pct > risk_profile["max_sector_pct"]:
                st.caption("Overweight in one sector? Steering future contributions toward other "
                           "sectors is often smoother than selling. The Smart DCA Assistant can help with the timing.")
                st.markdown(
                    '<a href="?view=premium" class="button-link" target="_self">🧠 Buy smarter with DCA &rarr;</a>',
                    unsafe_allow_html=True,
                )

    # --- Diversificatie ---
    with st.expander("🧩 Diversification"):
        for finding in analyze_diversification(holdings, infos):
            st.markdown(f"- {finding}")

    # --- Risico ---
    with st.expander("⚖️ Risk"):
        for finding in analyze_risk(holdings, infos):
            st.markdown(f"- {finding}")

        if is_premium:
            if len(holdings) >= 2:
                with st.spinner("Building correlation matrix..."):
                    corr_chart = build_correlation_matrix_chart(holdings)
                if corr_chart is not None:
                    st.plotly_chart(corr_chart, width="stretch")
            else:
                st.caption("Add at least 2 positions to see a correlation matrix.")
        else:
            st.info("🔒 Upgrade to Premium for a correlation matrix (which positions move together?).")

    # --- Performance ---
    with st.expander("📈 Performance"):
        with st.spinner("Checking trend status..."):
            trend_results = []
            for holding in holdings:
                result = check_holding(holding["naam"], holding["ticker"])
                if result:
                    trend_results.append(result)

        if trend_results:
            df_trend = pd.DataFrame(trend_results)
            changed = df_trend[df_trend["recent_gewijzigd"] == True]  # noqa: E712
            if len(changed) > 0:
                st.warning(f"🔄 {len(changed)} position(s) just flipped trend: "
                           + ", ".join(f"{r['naam']} ({r['status']})" for _, r in changed.iterrows()))

            def _format_weeks(value):
                return "-" if value is None else f"{value:.0f}"

            df_display = pd.DataFrame([
                {
                    "Name": r["naam"],
                    "Ticker": r["ticker"],
                    "Weekly Trend": r["status"],
                    "Just Flipped": "🔄 Yes" if r["recent_gewijzigd"] else "",
                    "Weeks in Trend": _format_weeks(r["weken_in_trend"]),
                }
                for r in trend_results
            ])

            def _highlight_status(row):
                color = "#1B3A2E" if row["Weekly Trend"] == "BULLISH" else (
                    "#3A1F1D" if row["Weekly Trend"] == "BEARISH" else "#332B14"
                )
                return [f"background-color: {color}"] * len(row)

            st.caption("Weekly Supertrend status per position.")
            st.dataframe(
                df_display.style.apply(_highlight_status, axis=1),
                width="content",
                height=min(38 * (len(df_display) + 1), 300),
            )
        else:
            st.caption("No trend data available for your tracked positions.")

    # --- Dividend ---
    with st.expander("💰 Dividend"):
        if is_premium:
            for finding in analyze_dividend(holdings, infos):
                st.markdown(f"- {finding}")
        else:
            st.info("🔒 Upgrade to Premium for your dividend income overview and upcoming ex-dividend dates.")

elif current_view == "settings":
    import database

    st.markdown("### Settings")

    if st.user.is_logged_in:
        user_email = st.user.email
        is_premium = database.is_premium_user(user_email)

        with st.container(border=True):
            st.markdown("#### Email preferences")
            prefs = database.get_user_preferences(user_email)

            st.caption("Weekly signals (choose which ones you want -- delivered in 1 combined email)")
            wants_momentocrats = st.checkbox(
                "📡 Momentocrats -- technical momentum + fundamental quality combo",
                value=prefs.get("wants_momentocrats_email", False),
            )
            wants_snowball = st.checkbox(
                "🐦 Snowballers -- quality stocks below fair value, for the long term",
                value=prefs.get("wants_snowball_email", False),
            )
            wants_rocket = st.checkbox(
                "🚀 Rocket List -- accelerating growth + momentum",
                value=prefs.get("wants_rocket_email", False),
            )

            wants_daily = st.checkbox(
                "Receive the daily screener email (swing-trade signals, weekdays)",
                value=prefs.get("wants_daily_email", False),
            )
            region_options = ["EU", "US_East", "US_West"]
            region_labels = {
                "EU": "Europe (~07:00 CET / 08:00 CEST)",
                "US_East": "US East (~07:00 ET)",
                "US_West": "US West (~07:00 PT)",
            }
            email_region = st.selectbox(
                "Morning delivery time (for the daily email)",
                region_options,
                index=region_options.index(prefs.get("email_region", "EU")),
                format_func=lambda x: region_labels[x],
            )
            wants_portfolio = st.checkbox(
                "Receive the weekly portfolio email (status + news for your own positions)",
                value=prefs["wants_portfolio_email"],
            )
            if st.button("Save preferences"):
                database.set_user_preferences(
                    user_email, wants_portfolio,
                    wants_daily_email=wants_daily, email_region=email_region,
                    wants_momentocrats_email=wants_momentocrats,
                    wants_snowball_email=wants_snowball, wants_rocket_email=wants_rocket,
                )
                st.success("Preferences saved!")

            if is_premium:
                st.markdown("---")
                st.markdown("**Cash / uninvested amount**")
                current_cash = database.get_cash_value(user_email)
                new_cash = st.number_input(
                    "Cash not currently invested (used for the cash% check in Analyze)",
                    min_value=0.0, value=float(current_cash), step=100.0, key="cash_input",
                )
                if st.button("Save cash amount"):
                    database.set_cash_value(user_email, new_cash)
                    st.success("Saved!")

        with st.container(border=True):
            st.markdown("#### Risk profile")
            st.caption("Used to personalize your Concentration Risk and Sectors analysis under "
                       "Analyze. Not a one-time thing -- update it anytime your situation changes.")

            profile = database.get_risk_profile(user_email)
            horizon_options = ["short", "medium", "long"]
            horizon_labels = {"short": "Short (< 2 years)", "medium": "Medium (2-7 years)", "long": "Long (7+ years)"}
            horizon = st.selectbox(
                "Investment horizon", horizon_options,
                index=horizon_options.index(profile["investment_horizon"]),
                format_func=lambda x: horizon_labels[x],
                help="How long do you plan to hold most of your investments?",
            )

            tolerance_options = ["conservative", "balanced", "aggressive"]
            tolerance = st.selectbox(
                "Risk tolerance", tolerance_options,
                index=tolerance_options.index(profile["risk_tolerance"]),
                format_func=lambda x: x.capitalize(),
                help="How comfortable are you with short-term swings for potentially higher returns?",
            )

            max_position = st.slider(
                "Max % you're comfortable with in a single position", 5, 100,
                int(profile["max_position_pct"]),
                help="A common rule of thumb is 20-25%, but this is personal.",
            )
            max_sector = st.slider(
                "Max % you're comfortable with in a single sector", 5, 100,
                int(profile["max_sector_pct"]),
                help="A common rule of thumb is 30-40%.",
            )
            target_cash = st.slider(
                "Target cash buffer %", 0, 100, int(profile["target_cash_pct"]),
                help="How much of your total portfolio do you want to keep as uninvested cash?",
            )

            wcol1, wcol2 = st.columns(2)
            with wcol1:
                if st.button("Save risk profile", type="primary"):
                    database.set_risk_profile(user_email, horizon, tolerance, max_position, max_sector, target_cash)
                    st.success("Saved!")
            with wcol2:
                if st.button("Reset to defaults"):
                    database.reset_risk_profile(user_email)
                    st.success("Reset to defaults!")
                    st.rerun()
    else:
        st.info("Log in (top right) to manage your email preferences.")

elif current_view == "premium":
    import database

    st.markdown("### Premium")
    st.write(
        "Everything on the free plan, plus deeper portfolio analysis and unlimited tracking."
    )

    st.markdown(
        """
        <table class="positions-table">
            <thead><tr><th>Feature</th><th>Free</th><th>Premium</th></tr></thead>
            <tbody>
                <tr><td>Momentocrats, Snowballers, Rocket List (Discover)</td><td>Top 3 each</td><td>Full top 10</td></tr>
                <tr><td>Weekly email for your chosen signals</td><td>Top 3 each</td><td>Full top 10</td></tr>
                <tr><td>Tracked positions (My Portfolio)</td><td>Up to 10</td><td>Unlimited</td></tr>
                <tr><td>Concentration, Diversification, Sectors, Performance (Analyze)</td><td>&#10003;</td><td>&#10003;</td></tr>
                <tr><td>Dividend income overview (Analyze)</td><td>--</td><td>&#10003;</td></tr>
                <tr><td>Weighted valuation (P/E) &amp; correlation matrix (Analyze)</td><td>--</td><td>&#10003;</td></tr>
                <tr><td>Smart DCA Assistant (TradingView indicator download)</td><td>--</td><td>&#10003;</td></tr>
            </tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown("##### Smart DCA Assistant -- TradingView indicator")
        st.write(
            "A TradingView indicator that adjusts your periodic contribution based on how "
            "cheap or expensive the market looks (moving average distance, RSI, drawdown) -- "
            "buying a bit more when things look cheap, and holding back when they don't. Includes "
            "a built-in comparison against a fixed, regular DCA strategy."
        )
        with st.expander("See it running on a real chart"):
            try:
                st.image("premium_content/dca_screenshot.jpg", width=500)
            except Exception:
                pass
            st.caption(
                "The indicator running on a real chart (Alphabet, weekly) -- the labels show the "
                "suggested contribution at each point, and the panel on the right compares Smart DCA "
                "against a fixed, regular DCA over the same period. This is one historical example, "
                "not a guarantee of future results."
            )

        if st.user.is_logged_in and database.is_premium_user(st.user.email, ignore_free_for_all=True):
            try:
                with open("premium_content/smart_dca_assistant.pine", encoding="utf-8") as f:
                    pine_code = f.read()

                # Watermerk wordt NA de //@version=6-regel geplaatst (niet ervoor) --
                # bronnen spreken elkaar tegen of commentaar vóór die regel de
                # compilatie kan verstoren, dus voor de zekerheid altijd erna.
                lines = pine_code.split("\n", 1)
                watermark = (
                    f"// Licensed to: {st.user.email}\n"
                    f"// Downloaded from Hesty's on {datetime.now().strftime('%Y-%m-%d')}\n"
                    f"// For personal use only -- do not redistribute or republish.\n"
                )
                if len(lines) == 2:
                    watermarked_code = lines[0] + "\n" + watermark + lines[1]
                else:
                    watermarked_code = pine_code + "\n" + watermark

                st.download_button(
                    "Download smart_dca_assistant.pine",
                    data=watermarked_code,
                    file_name="smart_dca_assistant.pine",
                    mime="text/plain",
                )
                st.caption(
                    "Open TradingView -> Pine Editor -> New blank indicator -> paste the file contents -> "
                    "Add to chart. Right-click the indicator name in the chart legend and 'Pin to scale' "
                    "to the same scale as your candles."
                )
            except FileNotFoundError:
                st.caption("Indicator file not found -- contact support.")
        else:
            st.caption("🔒 Available for Premium members -- see Subscription below.")

    with st.container(border=True):
        st.markdown("##### Subscription")

        # --- Terugkeer van Stripe: verifieer de sessie en zet premium aan ---
        returned_session_id = st.query_params.get("session_id")
        if returned_session_id:
            with st.spinner("Confirming your payment..."):
                success, paid_email = verify_and_activate_premium(returned_session_id)
            if success:
                st.success(f"🎉 Payment confirmed! Premium is now active for {paid_email}.")
            else:
                st.warning(
                    "We couldn't confirm this payment yet. If you just completed checkout, "
                    "please wait a few seconds and refresh this page."
                )

        _premium_free_for_all = st.secrets.get("app", {}).get("premium_free_for_all", False)

        if not st.user.is_logged_in:
            st.info("Log in first (top right) so we know which account to upgrade.")
        elif _premium_free_for_all:
            st.success("🚀 Everything is unlocked for free while we're still getting started -- "
                       "no payment needed yet. Enjoy, and thanks for trying Hesty's early!")
        elif database.is_premium_user(st.user.email):
            st.success("You're already on Premium. Thank you!")
            customer_id = database.get_stripe_customer_id(st.user.email)
            if customer_id:
                if st.button("Manage subscription"):
                    with st.spinner("Preparing your subscription portal..."):
                        portal_session = create_billing_portal_session(customer_id)
                    st.link_button("Open subscription portal →", portal_session.url, type="primary")
                st.caption("Cancel anytime -- you'll keep Premium access until the end of your current billing period.")
            else:
                st.caption("Manage your subscription by contacting support -- see below.")
        else:
            st.write("Choose a plan:")
            pcol1, pcol2 = st.columns(2)
            with pcol1:
                st.markdown("**Monthly -- €7.99/mo** *(~$8.99)*")
                if st.button("Subscribe monthly", key="sub_monthly"):
                    with st.spinner("Preparing checkout..."):
                        session = create_checkout_session(
                            st.secrets["stripe"]["price_id_monthly"], st.user.email,
                        )
                    st.link_button("Continue to payment →", session.url, type="primary")
            with pcol2:
                st.markdown("**Yearly -- €75/yr** *(~$85)*")
                if st.button("Subscribe yearly", key="sub_yearly"):
                    with st.spinner("Preparing checkout..."):
                        session = create_checkout_session(
                            st.secrets["stripe"]["price_id_yearly"], st.user.email,
                        )
                    st.link_button("Continue to payment →", session.url, type="primary")
            st.caption("Payments are processed securely by Stripe -- we never see or store your card details. "
                       "USD amounts shown are approximate (current EUR/USD rate) -- you're charged in EUR.")

elif current_view == "support":
    st.markdown("### Support")
    st.write("Questions, ideas, or something not working as expected? Check the FAQ below, "
              "or send us a message directly. Business inquiries and partnerships are welcome too.")

    st.markdown("#### Frequently asked questions")

    with st.expander("What does Discover do?"):
        st.write(
            "It scans the AEX, Nasdaq-100, S&P 500, DAX, and CAC 40 (weekly and daily variants) "
            "for stocks that just turned bullish on a Supertrend indicator, scored on technical "
            "and fundamental factors. It's public, no login required."
        )

    with st.expander("Is my portfolio data private?"):
        st.write(
            "Yes. Your tracked positions are only visible to you, tied to your Google account. "
            "We never share or sell your data."
        )

    with st.expander("What's the difference between Free and Premium?"):
        st.write(
            "Free covers concentration, diversification, sector and asset mix, and up to 10 "
            "tracked positions. Premium adds dividend income, valuation, cash%, rebalancing "
            "ideas, a return-vs-benchmark chart, a correlation matrix, unlimited positions, and "
            "the Smart DCA Assistant TradingView indicator. See the Premium page for the full comparison."
        )

    with st.expander("How do I cancel my Premium subscription?"):
        st.write(
            "On the Premium page, under Subscription, click 'Manage subscription' -- this opens "
            "Stripe's secure billing portal, where you can cancel anytime. You'll keep Premium "
            "access until the end of your current billing period."
        )

    with st.expander("How do I get the Smart DCA Assistant TradingView indicator?"):
        st.write(
            "Premium members can download it directly from the Premium page, with setup "
            "instructions for TradingView's Pine Editor."
        )

    with st.expander("How do I change what emails I receive?"):
        st.write(
            "Log in, go to Settings, and use the Email preferences section to toggle the weekly "
            "screener, daily screener, and/or portfolio emails on or off."
        )

    st.markdown("#### Send us a message")
    st.write("Found a bug, have an idea, or need help with something else? Let us know.")

    contact_email = st.text_input("Your email")
    message_type = st.selectbox("Type", ["Idea", "Problem / bug", "Billing question", "Business inquiry", "Other"])
    message_body = st.text_area("Message", height=150)

    if st.button("Send message", type="primary"):
        if not contact_email or not message_body.strip():
            st.error("Please fill in your email and a message before sending.")
        else:
            support_email = st.secrets.get("support", {}).get("email")
            if not support_email:
                st.error("Support inbox isn't configured yet -- please try again later.")
            else:
                success = send_email(
                    subject=f"[Hesty's Support] {message_type} from {contact_email}",
                    body_text=message_body,
                    to_email=support_email,
                )
                if success:
                    st.success("Thanks! Your message has been sent -- we'll get back to you by email.")
                else:
                    st.error("Something went wrong sending your message -- please try again later.")

st.divider()
st.caption("This dashboard shows technical signals (Supertrend), fundamental context (ROIC estimate), "
           "and news. It is not an automated strategy and not financial advice.")
