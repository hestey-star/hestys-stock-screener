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
import subprocess
from datetime import datetime, timezone, timedelta, date

import numpy as np
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


def get_file_last_commit_date(path: str) -> str:
    """
    Geeft alleen de DATUM (YYYY-MM-DD) van de laatste git-commit van dit
    bestand terug -- gebruikt om te vergelijken of een gebruiker een
    bepaalde scan-batch al heeft gezien. Geeft None terug als het niet
    lukt (bestand bestaat niet, of git niet beschikbaar).
    """
    if not os.path.exists(path):
        return None
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cd", "--date=format:%Y-%m-%d", "--", path],
            capture_output=True, text=True, timeout=5,
        )
        commit_date = result.stdout.strip()
        return commit_date or None
    except Exception:
        return None


def file_last_modified(path: str) -> str:
    """
    Geeft het tijdstip terug waarop dit bestand voor het laatst is
    BIJGEWERKT DOOR DE SCAN ZELF (git-commit-tijd, in UTC) -- niet het
    Streamlit-servers-eigen bestandssysteem-tijdstip (os.path.getmtime),
    want dat weerspiegelt alleen wanneer Streamlit Cloud het bestand voor
    het laatst binnenkreeg bij een eigen (re)deploy, wat kan afwijken van
    wanneer de scan daadwerkelijk draaide -- verwarrend bij het checken of
    de dagelijkse/wekelijkse mail wel op tijd is gegaan.
    """
    if not os.path.exists(path):
        return "never"
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cd", "--date=format:%Y-%m-%d %H:%M UTC", "--", path],
            capture_output=True, text=True, timeout=5,
        )
        commit_time = result.stdout.strip()
        if commit_time:
            return commit_time
    except Exception:
        pass
    # Terugval als git niet beschikbaar/succesvol is in deze omgeving
    ts = os.path.getmtime(path)
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") + " (server time, not scan time)"


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


@st.cache_data(ttl=300, show_spinner=False)
def get_fx_rate(from_currency: str, to_currency: str):
    """Haalt de actuele wisselkoers op (5 min gecached). Geeft None terug als het niet lukt (i.p.v. een gok te doen)."""
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


def build_breakdown_pie_chart(labels: list, values: list):
    """
    Generieke donut-chart voor een verdeling (sector/asset-type/regio) --
    zelfde visuele stijl als build_portfolio_pie_chart(), maar dan
    herbruikbaar voor willekeurige categorie-verdelingen i.p.v. alleen
    per-positie.
    """
    palette = ["#1FAE96", "#E8A93C", "#4DA6FF", "#E5484D", "#C77DFF",
               "#3ED9C4", "#F5C518", "#FF8A5C", "#8992A3", "#5AC8B0", "#B0E0D8"]
    colors = (palette * (len(labels) // len(palette) + 1))[:len(labels)]

    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values, hole=0.55,
        marker=dict(colors=colors, line=dict(color="#101825", width=2)),
        texttemplate="%{percent:.0%}",
        textposition="inside",
        textfont=dict(family="Inter, sans-serif", size=13, color="#EAEDF1"),
        hovertemplate="%{label}: %{percent:.1%}<extra></extra>",
    )])
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02,
                    font=dict(family="Inter, sans-serif", size=10, color="#8992A3"), bgcolor="rgba(0,0,0,0)"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=10, b=10, l=10, r=110),
        height=280,
        font=dict(family="Inter, sans-serif", color="#EAEDF1"),
    )
    return fig


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


@st.cache_data(ttl=300, show_spinner=False)
def get_cached_ticker_info(ticker: str) -> dict:
    """
    Cachet yfinance's .info per ticker voor 5 minuten -- voorkomt dat
    dezelfde koersinfo steeds opnieuw wordt opgehaald bij elke
    pagina-interactie (Streamlit herstart het hele script bij elke klik).
    """
    try:
        return yf.Ticker(ticker).info
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def get_cached_ticker_history(ticker: str, period: str = None, start: str = None, end: str = None):
    """Cachet yfinance's .history() per ticker+periode voor 5 minuten."""
    try:
        if start is not None:
            return yf.Ticker(ticker).history(start=start, end=end)
        return yf.Ticker(ticker).history(period=period)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def get_cached_ticker_dividends(ticker: str):
    """Cachet yfinance's .dividends (historische, per-share dividendbetalingen) per ticker voor 5 minuten."""
    try:
        return yf.Ticker(ticker).dividends
    except Exception:
        return pd.Series(dtype=float)


def get_annual_dividend_rate(ticker: str, info: dict):
    """
    Geeft het geschatte jaarlijkse dividend per aandeel terug, met 2
    terugvallen -- nodig omdat 'dividendRate' in yfinance's .info voor
    sommige effecten (vooral ETF's, zoals TDIV) niet betrouwbaar gevuld
    is, ook al keren ze wel degelijk dividend uit:
    1. info['dividendRate'] -- werkt betrouwbaar voor de meeste aandelen
    2. info['trailingAnnualDividendRate'] -- vaak wel gevuld voor ETF's
       als 'dividendRate' leeg is
    3. Som van de daadwerkelijke dividendbetalingen van de laatste 12
       maanden (uit de koersgeschiedenis) -- de meest betrouwbare,
       universele terugval, want gebaseerd op wat er al daadwerkelijk is
       uitgekeerd i.p.v. een (soms ontbrekende) vooruitkijkende schatting.
    """
    rate = info.get("dividendRate")
    if rate:
        return rate
    rate = info.get("trailingAnnualDividendRate")
    if rate:
        return rate
    try:
        dividends = get_cached_ticker_dividends(ticker)
        if dividends is not None and not dividends.empty:
            cutoff = pd.Timestamp.now(tz=dividends.index.tz) - pd.Timedelta(days=365)
            recent = dividends[dividends.index >= cutoff]
            if not recent.empty:
                return float(recent.sum())
    except Exception:
        pass
    return None


def get_tickers_info(holdings: list) -> dict:
    """Haalt 1x per ticker de yfinance-info op (via de 5-min-cache), voor hergebruik door meerdere analyses."""
    infos = {}
    for h in holdings:
        infos[h["ticker"]] = get_cached_ticker_info(h["ticker"])
    return infos


def get_concentration_alert(holdings: list, max_position_pct: float = 25.0):
    """
    Korte, 1-regelige concentratie-waarschuwing voor Today's radar -- geeft
    None terug als alles binnen je eigen doel-grens zit (geen ruis op
    normale dagen). Hergebruikt dezelfde logica als Analyze's Concentration
    Risk-kaart, maar dan alleen de 'is er iets mis'-check, niet de volledige
    uitleg/rebalancing-tip.
    """
    total_value = sum(h.get("position_value") or 0 for h in holdings)
    if total_value <= 0:
        return None
    largest = max(holdings, key=lambda h: h.get("position_value") or 0)
    largest_pct = (largest.get("position_value") or 0) / total_value * 100
    if largest_pct > max_position_pct:
        return f"⚖️ **{largest['naam']}** is now {largest_pct:.0f}% of your portfolio, above your {max_position_pct:.0f}% target."
    return None


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
        # Posities zonder een GICS-sector (crypto, edelmetalen-achtige
        # producten, e.d.) telden voorheen NIET mee in de uitsplitsing,
        # terwijl hun waarde wel in total_value (de noemer) zat -- dat
        # verklaarde waarom de percentages niet optelden tot 100%. Nu
        # krijgen ze een expliciete, herkenbare bucket i.p.v. te verdwijnen.
        bucket = sector if sector else "Non-equity / Other"
        sector_values[bucket] = sector_values.get(bucket, 0) + value

    if not sector_values:
        return ["No sector data available for your tracked positions."]

    # De 'concentratie-risico'-melding gaat specifiek over ECHTE sectoren --
    # 'Non-equity / Other' (crypto e.d.) meetellen als 'sector-concentratie'
    # zou een verwarrende melding geven, dus die sluiten we hier expliciet uit.
    real_sector_values = {s: v for s, v in sector_values.items() if s != "Non-equity / Other"}
    if real_sector_values:
        dominant_sector, dominant_value = max(real_sector_values.items(), key=lambda x: x[1])
        dominant_pct = dominant_value / total_value * 100

        if dominant_pct >= max_sector_pct * 1.5:
            level = "🔴 High concentration"
        elif dominant_pct > max_sector_pct:
            level = "🟡 Above your target"
        else:
            level = "🟢 Within your target"
        findings.append(f"{level}: {dominant_sector} makes up {dominant_pct:.0f}% of your tracked portfolio (your target max: {max_sector_pct:.0f}%).")
    else:
        findings.append("No positions with a known equity sector yet -- all tracked positions are non-equity (crypto, etc.).")

    breakdown = ", ".join(
        f"{s}: {v / total_value * 100:.0f}%" for s, v in sorted(sector_values.items(), key=lambda x: -x[1])
    )
    findings.append(f"Full breakdown -- {breakdown}.")

    return findings


def get_holding_region(ticker: str, info: dict) -> str:
    """
    Bepaalt de regio van een positie -- eerst via yfinance's 'country'-veld
    (het meest betrouwbaar), gegroepeerd in bredere regio's. Voor posities
    zonder land-info (zoals crypto) wordt teruggevallen op hetzelfde
    ticker-patroon-herkenning als bij Diversification.
    """
    country = (info or {}).get("country")
    if country:
        us_countries = {"United States"}
        eu_countries = {
            "Germany", "France", "Netherlands", "Belgium", "Spain", "Italy",
            "Ireland", "Luxembourg", "Austria", "Portugal", "Finland",
            "Sweden", "Denmark", "Norway", "Switzerland", "Poland",
        }
        if country in us_countries:
            return "United States"
        elif country in eu_countries:
            return "Europe"
        elif country == "United Kingdom":
            return "United Kingdom"
        else:
            return country  # bv. China, Japan, Canada -- toon het land zelf

    ticker_suffix = ticker.rsplit("-", 1)[-1].upper() if "-" in ticker else ""
    if ticker_suffix in ("EUR", "USD", "GBP", "USDT", "USDC"):
        return "Cryptocurrency"

    return "Unknown"


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
        raw_quote_type = infos.get(h["ticker"], {}).get("quoteType")
        if raw_quote_type:
            asset_type = raw_quote_type
        else:
            # Yfinance geeft soms geen (of een lege) quoteType terug --
            # vooral crypto-tickers (bv. 'BTC-EUR', 'SOL-EUR') volgen een
            # herkenbaar {SYMBOL}-{VALUTA}-patroon. Die herkennen we hier
            # expliciet, i.p.v. ze allemaal onder de vage, nietszeggende
            # stempel 'Unknown' te laten vallen.
            ticker_suffix = h["ticker"].rsplit("-", 1)[-1].upper() if "-" in h["ticker"] else ""
            if ticker_suffix in ("EUR", "USD", "GBP", "USDT", "USDC"):
                asset_type = "CRYPTOCURRENCY"
            else:
                asset_type = "UNKNOWN"
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


def analyze_dividend(holdings: list, infos: dict, display_currency: str = "EUR") -> dict:
    """
    Dividend-kaart: geschat jaarlijks dividend + aankomende ex-dividend-data,
    plus een per-positie-uitsplitsing (bedrag in de weergave-valuta en
    dividendrendement %). Rekent elke positie's dividend (dat yfinance in de
    EIGEN valuta van die beurs teruggeeft, bv. USD voor een Amerikaans
    aandeel) om naar 1 consistente weergave-valuta, i.p.v. bedragen in
    verschillende valuta zomaar bij elkaar op te tellen.
    """
    findings = []
    total_annual_dividend = 0.0
    conversion_failed = False
    upcoming = []
    per_position = []
    for h in holdings:
        info = infos.get(h["ticker"], {})
        shares = h.get("shares") or 0
        dividend_rate = get_annual_dividend_rate(h["ticker"], info)
        if dividend_rate and shares:
            native_currency = info.get("currency", display_currency)
            native_amount = dividend_rate * shares
            converted_amount = None
            if native_currency == display_currency:
                converted_amount = native_amount
            else:
                fx_rate = get_fx_rate(native_currency, display_currency)
                if fx_rate is not None:
                    converted_amount = native_amount * fx_rate
                else:
                    conversion_failed = True
            if converted_amount is not None:
                total_annual_dividend += converted_amount

            # Dividendrendement = jaarlijks dividend per aandeel / huidige koers.
            # Zelfde robuuste prijs-terugval als bij Performance (sommige
            # effecten missen currentPrice/regularMarketPrice in .info).
            current_price = info.get("currentPrice") or info.get("regularMarketPrice")
            if current_price is None:
                try:
                    fallback_hist = get_cached_ticker_history(h["ticker"], period="5d")
                    if fallback_hist is not None and not fallback_hist.empty:
                        current_price = float(fallback_hist["Close"].iloc[-1])
                except Exception:
                    pass
            yield_pct = (dividend_rate / current_price * 100) if current_price else None

            per_position.append({
                "naam": h["naam"],
                "ticker": h["ticker"],
                "annual_dividend": converted_amount,
                "yield_pct": yield_pct,
            })
        ex_div = info.get("exDividendDate")
        if ex_div:
            try:
                date_str = pd.Timestamp(ex_div, unit="s").date()
                # yfinance's exDividendDate is soms de MEEST RECENTE (al
                # gepasseerde) datum i.p.v. een daadwerkelijk toekomstige --
                # alleen tonen als 'ie ook echt nog moet komen.
                if date_str >= datetime.now().date():
                    upcoming.append((h["naam"], date_str))
            except Exception:
                pass

    currency_symbol = "€" if display_currency == "EUR" else ("$" if display_currency == "USD" else display_currency + " ")
    if total_annual_dividend > 0:
        underestimate_note = (
            " (couldn't convert every position's currency, so this may be a slight underestimate)"
            if conversion_failed else ""
        )
        findings.append(
            f"💰 Estimated annual dividend income: ~{currency_symbol}{total_annual_dividend:,.0f}{underestimate_note}."
        )
        if upcoming:
            upcoming.sort(key=lambda x: x[1])
            dates_str = ", ".join(f"{n} ({d})" for n, d in upcoming[:5])
            findings.append(f"Upcoming ex-dividend dates: {dates_str}.")
    else:
        findings.append("No dividend-paying positions detected (or data unavailable).")

    per_position.sort(key=lambda p: p["annual_dividend"] or 0, reverse=True)
    return {"findings": findings, "per_position": per_position, "currency_symbol": currency_symbol}


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
            hist = get_cached_ticker_history(h["ticker"], period="5d")
            if len(hist) < 2:
                continue
            price_today = float(hist["Close"].iloc[-1])
            price_yesterday = float(hist["Close"].iloc[-2])
            # Sommige dagen ontbreekt een koers (bv. rond een feestdag/data-gat) --
            # yfinance geeft dan NaN terug. Zonder deze check zou 1 NaN de HELE
            # portfolio-som NaN maken (NaN + iets = NaN), en 'total_value_yesterday
            # <= 0' vangt dat niet af (NaN-vergelijkingen zijn altijd False in
            # Python) -- vandaar dat '+nan%' anders alsnog getoond zou worden.
            if pd.isna(price_today) or pd.isna(price_yesterday) or price_yesterday <= 0:
                continue
            change_pct = (price_today / price_yesterday - 1) * 100
            performers.append({"naam": h["naam"], "change_pct": change_pct})
            total_value_today += shares * price_today
            total_value_yesterday += shares * price_yesterday
        except Exception:
            continue

    if not performers or total_value_yesterday <= 0:
        return None

    portfolio_change_pct = (total_value_today / total_value_yesterday - 1) * 100
    if pd.isna(portfolio_change_pct):
        # Laatste veiligheidsnet -- zou niet meer moeten gebeuren dankzij de
        # check hierboven, maar voorkomt sowieso ooit weer een '+nan%'.
        return None
    best = max(performers, key=lambda p: p["change_pct"])
    worst = min(performers, key=lambda p: p["change_pct"])

    return {
        "portfolio_change_pct": round(portfolio_change_pct, 2),
        "best_performer": best["naam"],
        "best_change_pct": round(best["change_pct"], 2),
        "worst_performer": worst["naam"],
        "worst_change_pct": round(worst["change_pct"], 2),
    }


def build_opportunities_today(holdings: list, watchlist_items: list, include_weekly: bool = True) -> dict:
    """
    Leest de dagelijkse (+ optioneel wekelijkse) screener-uitkomsten en
    telt hoeveel signalen ergens bij jou horen. include_weekly=False
    laat de weekly-signalen overal buiten beschouwing (tellingen blijven
    zo consistent) -- gebruikt op dagen dat de gebruiker de wekelijkse
    batch al eerder heeft gezien, om niet elke dag dezelfde 58 weekly-
    signalen opnieuw te melden.
    """
    holding_tickers = {h["ticker"] for h in holdings}
    watchlist_tickers = {w["ticker"] for w in watchlist_items}

    daily_df = pd.read_csv("supertrend_signals_daily.csv") if os.path.exists("supertrend_signals_daily.csv") else None
    weekly_df = (
        pd.read_csv("supertrend_signals.csv")
        if include_weekly and os.path.exists("supertrend_signals.csv") else None
    )

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

# Populaire THEMA-ETF's (niet officiële GICS-sectoren, maar cross-sector
# trends die veel gevolgd worden) -- bewust apart van Sector Rotation
# gehouden, anders zou een bedrijf dubbel meetellen (1x onder z'n echte
# sector, 1x onder het thema).
THEME_ETFS = {
    "Robotics & AI": "BOTZ", "Clean Energy": "ICLN", "Cybersecurity": "CIBR",
    "Semiconductors": "SMH", "Genomics & Biotech": "ARKG",
}

# yfinance's eigen 'sector'-veld gebruikt ANDERE namen dan onze
# US_SECTOR_ETFS-lijst (bv. 'Financial Services' i.p.v. 'Financials',
# 'Healthcare' i.p.v. 'Health Care') -- deze mapping overbrugt dat, zodat
# een deep-dive's sector-rotatie-context correct kan koppelen.
YFINANCE_SECTOR_TO_OURS = {
    "Technology": "Technology",
    "Financial Services": "Financials",
    "Energy": "Energy",
    "Healthcare": "Health Care",
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Industrials": "Industrials",
    "Basic Materials": "Materials",
    "Utilities": "Utilities",
    "Real Estate": "Real Estate",
    "Communication Services": "Communication Services",
}


def render_section_banner(title: str):
    """
    Dikke, opvallende sectie-banner (i.p.v. een dun lijntje) om groepen
    kaarten van elkaar te onderscheiden -- gebruikt op zowel Discover
    ('The Bigger Picture') als Analyze ('Risk & Diversification', 'Income').
    """
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, rgba(31,174,150,0.14), rgba(31,174,150,0.02));
                    border: 1px solid rgba(31,174,150,0.35); border-radius: 10px;
                    padding: 0.85rem 1.25rem; margin: 1.5rem 0 1rem 0;">
            <div style="color:#1FAE96; font-weight:700; font-size:0.8rem; letter-spacing:1.5px; text-transform:uppercase;">
                {title}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_sector_theme_threshold_alerts() -> list:
    """
    Checkt sectoren EN thema's op extreme 1-maands-trailing-rendementen --
    mogelijk een koop-/verkoopmoment (sterk gedaald) of iets om in de gaten
    te houden (sterk gestegen). Thema's krijgen een ruimere drempel dan
    sectoren, want smallere thema-ETF's (bv. BOTZ, ARKG) zijn van nature
    volatieler -- eenzelfde uitslag is daar minder bijzonder.

    Sectoren: onder -10% ('notable'), boven +10% ('notable'), boven +15%
    ('extreme'). Thema's: onder -15%, boven +15%, boven +20%.
    """
    alerts = []

    for region in ["US", "EU"]:
        try:
            rotation = build_sector_rotation(region=region, period="1mo")
        except Exception:
            continue
        for r in rotation:
            pct = r["return_pct"]
            if pct <= -10:
                alerts.append({"name": r["sector"], "kind": "sector", "region": region, "pct": pct, "level": "notable", "direction": "down"})
            elif pct >= 15:
                alerts.append({"name": r["sector"], "kind": "sector", "region": region, "pct": pct, "level": "extreme", "direction": "up"})
            elif pct >= 10:
                alerts.append({"name": r["sector"], "kind": "sector", "region": region, "pct": pct, "level": "notable", "direction": "up"})

    try:
        theme_rotation = build_theme_rotation(period="1mo")
    except Exception:
        theme_rotation = []
    for r in theme_rotation:
        pct = r["return_pct"]
        if pct <= -15:
            alerts.append({"name": r["theme"], "kind": "theme", "region": None, "pct": pct, "level": "notable", "direction": "down"})
        elif pct >= 20:
            alerts.append({"name": r["theme"], "kind": "theme", "region": None, "pct": pct, "level": "extreme", "direction": "up"})
        elif pct >= 15:
            alerts.append({"name": r["theme"], "kind": "theme", "region": None, "pct": pct, "level": "notable", "direction": "up"})

    alerts.sort(key=lambda a: abs(a["pct"]), reverse=True)
    return alerts


def build_theme_rotation(period: str = "1mo") -> list:
    """
    Zelfde logica als build_sector_rotation(), maar dan voor de populaire
    THEMA-ETF's (Robotics & AI, Clean Energy, etc.) i.p.v. de officiële
    GICS-sectoren.
    """
    results = []
    for theme, ticker in THEME_ETFS.items():
        try:
            hist = get_cached_ticker_history(ticker, period=period)
            if len(hist) >= 2:
                ret = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100
                results.append({"theme": theme, "ticker": ticker, "return_pct": round(ret, 2)})
        except Exception:
            continue

    results.sort(key=lambda x: x["return_pct"], reverse=True)
    return results


def build_sector_rotation_trend(region: str = "US", lookback_months: int = 6, rolling_window_days: int = 21) -> dict:
    """
    Geeft voor elke sector-ETF een TIJDREEKS van het rollende 1-maands-
    rendement terug (i.p.v. build_sector_rotation()'s enkele, huidige
    getal) -- laat zien of een sector aan het versnellen, vertragen, of
    OMSLAAN is, zodat een reversal visueel te herkennen is in een
    lijngrafiek. Sectoren met te weinig historische data worden
    overgeslagen (geen crash bij een enkele problematische ticker).
    """
    etfs = US_SECTOR_ETFS if region == "US" else EU_SECTOR_ETFS
    total_days_needed = lookback_months * 31 + rolling_window_days + 15  # ruime marge voor weekends/feestdagen
    result = {}
    for sector, ticker in etfs.items():
        try:
            hist = get_cached_ticker_history(ticker, period=f"{total_days_needed}d")
            if hist is None or hist.empty:
                continue
            closes = hist["Close"].dropna()
            if len(closes) < rolling_window_days + 5:
                continue
            rolling_return = (closes / closes.shift(rolling_window_days) - 1) * 100
            rolling_return = rolling_return.dropna()
            if rolling_return.empty:
                continue
            cutoff_date = rolling_return.index[-1] - pd.Timedelta(days=lookback_months * 31)
            rolling_return = rolling_return[rolling_return.index >= cutoff_date]
            result[sector] = {
                "dates": rolling_return.index.strftime("%Y-%m-%d").tolist(),
                "values": rolling_return.round(2).tolist(),
            }
        except Exception:
            continue
    return result


def build_theme_rotation_trend(lookback_months: int = 6, rolling_window_days: int = 21) -> dict:
    """
    Zelfde logica als build_sector_rotation_trend(), maar dan voor de
    THEMA-ETF's -- geeft per thema een tijdreeks van het rollende
    1-maands-rendement terug, i.p.v. build_theme_rotation()'s enkele,
    huidige getal.
    """
    total_days_needed = lookback_months * 31 + rolling_window_days + 15
    result = {}
    for theme, ticker in THEME_ETFS.items():
        try:
            hist = get_cached_ticker_history(ticker, period=f"{total_days_needed}d")
            if hist is None or hist.empty:
                continue
            closes = hist["Close"].dropna()
            if len(closes) < rolling_window_days + 5:
                continue
            rolling_return = (closes / closes.shift(rolling_window_days) - 1) * 100
            rolling_return = rolling_return.dropna()
            if rolling_return.empty:
                continue
            cutoff_date = rolling_return.index[-1] - pd.Timedelta(days=lookback_months * 31)
            rolling_return = rolling_return[rolling_return.index >= cutoff_date]
            result[theme] = {
                "dates": rolling_return.index.strftime("%Y-%m-%d").tolist(),
                "values": rolling_return.round(2).tolist(),
            }
        except Exception:
            continue
    return result


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
            hist = get_cached_ticker_history(ticker, period=period)
            if hist is None or hist.empty:
                continue
            # Zelfde soort probleem als eerder elders gevonden: de EERSTE of
            # LAATSTE rij kan een onvolledige koers (NaN) zijn (bv. een
            # 'vandaag'-bar die nog niet volledig is, vaker voorkomend bij
            # niet-Amerikaanse beurzen met andere handelstijden) -- pak de
            # eerste/laatste GELDIGE koers i.p.v. blindelings de rand-rijen,
            # anders wordt het rendement NaN (toont als 'None' in de tabel).
            valid_closes = hist["Close"].dropna()
            if len(valid_closes) >= 2:
                ret = (valid_closes.iloc[-1] / valid_closes.iloc[0] - 1) * 100
                results.append({"sector": sector, "ticker": ticker, "return_pct": round(ret, 2)})
        except Exception:
            continue

    results.sort(key=lambda x: x["return_pct"], reverse=True)
    return results


def _deep_dive_score_color(score: float) -> str:
    """Vertaalt een score (1-10) naar een betekenisvolle kleur -- groen (sterk), amber (gemiddeld), rood (zwak)."""
    if score >= 7.5:
        return "#1FAE96"  # Hesty's signature teal/groen -- sterk
    elif score >= 5.0:
        return "#E8A93C"  # amber -- gemiddeld
    else:
        return "#E5484D"  # rood -- zwak


def _compute_deep_dive_overall_score(version: dict):
    """
    Geeft het gemiddelde van de 5 ingevulde oordeel-scores terug (1-10),
    of None als er nog geen enkele score is ingevuld. Alle 5 scores staan
    in dezelfde richting (hoger = gunstiger voor een koopbeslissing),
    dus een simpel gemiddelde is hier zinvol.
    """
    score_fields = [
        "thesis_score", "management_score", "bear_case_score",
        "valuation_score", "catalysts_score", "technical_analysis_score",
    ]
    filled_scores = [version[f] for f in score_fields if version.get(f) is not None]
    if not filled_scores:
        return None
    return sum(filled_scores) / len(filled_scores)


def _render_deep_dive_version(version: dict, user_email: str):
    """
    Toont 1 versie van een deep-dive, met een 'Edit'-knop die overschakelt
    naar een voorgevuld bewerk-formulier -- voor het corrigeren van een
    typefout of het aanvullen van 1 onderdeel, ZONDER dat je alle andere
    velden opnieuw moet uitschrijven (dat zou nodig zijn als je in plaats
    daarvan een hele nieuwe versie zou toevoegen).
    """
    import database

    version_id = version["id"]
    edit_key = f"dd_editing_{version_id}"
    is_editing = st.session_state.get(edit_key, False)

    st.markdown(f"##### {version['created_at'][:10]} -- {version['conclusion']}")

    overall_score = _compute_deep_dive_overall_score(version)
    if overall_score is not None:
        score_color = _deep_dive_score_color(overall_score)
        st.markdown(
            f'<span style="font-size:1.3rem; font-weight:800; color:{score_color};">{overall_score:.1f}/10</span> '
            f'<span style="font-size:0.8rem; color:#8992A3;">overall score</span>',
            unsafe_allow_html=True,
        )

    ticker_currency_symbol = _currency_symbol_for_ticker(version["ticker"])

    snapshot_parts = []
    if version.get("price_at_creation"):
        snapshot_parts.append(f"Price: {ticker_currency_symbol}{version['price_at_creation']:.2f}")
    if version.get("fifty_two_week_high_at_creation") and version.get("fifty_two_week_low_at_creation"):
        snapshot_parts.append(
            f"52wk: {ticker_currency_symbol}{version['fifty_two_week_low_at_creation']:.2f}-"
            f"{ticker_currency_symbol}{version['fifty_two_week_high_at_creation']:.2f}"
        )
    if version.get("market_cap_at_creation"):
        snapshot_parts.append(f"Market cap: {ticker_currency_symbol}{version['market_cap_at_creation'] / 1e9:.1f}B")
    if version.get("sector_at_creation"):
        snapshot_parts.append(f"Sector: {version['sector_at_creation']}")
    if version.get("dividend_yield_at_creation"):
        snapshot_parts.append(f"Dividend: {version['dividend_yield_at_creation']:.2f}%")
    if version.get("in_own_signals_at_creation"):
        snapshot_parts.append(f"In your own signals: {version['in_own_signals_at_creation']}")
    if version.get("sector_rotation_pct_at_creation") is not None:
        snapshot_parts.append(f"Sector rotation (1m): {version['sector_rotation_pct_at_creation']:+.1f}%")
    if snapshot_parts:
        st.caption(" · ".join(snapshot_parts))

    if not is_editing:
        if version.get("business_overview"):
            st.markdown(f"**Business overview**: {version['business_overview']}")
        if version.get("investment_thesis"):
            st.markdown(f"**Investment thesis**: {version['investment_thesis']}")
        if version.get("management_assessment"):
            st.markdown(f"**Management/CEO**: {version['management_assessment']}")
        if version.get("bear_case"):
            st.markdown(f"**Bear case**: {version['bear_case']}")
        if version.get("valuation_view"):
            st.markdown(f"**Valuation**: {version['valuation_view']}")
        if version.get("interested_price"):
            st.markdown(f"**Interested from**: {ticker_currency_symbol}{version['interested_price']:.2f}")
        if version.get("technical_analysis"):
            st.markdown(f"**Technical analysis**: {version['technical_analysis']}")
        if version.get("catalysts"):
            st.markdown(f"**Catalysts**: {version['catalysts']}")
        if version.get("position_sizing_plan"):
            st.markdown(f"**Position sizing plan**: {version['position_sizing_plan']}")
        if version.get("sell_criteria"):
            st.markdown(f"**Sell criteria**: {version['sell_criteria']}")
        if version.get("sell_trigger_price") or version.get("sell_trigger_date"):
            trigger_parts = []
            if version.get("sell_trigger_price"):
                trigger_parts.append(f"at {ticker_currency_symbol}{version['sell_trigger_price']:.2f}")
            if version.get("sell_trigger_date"):
                trigger_parts.append(f"by {version['sell_trigger_date']}")
            st.caption(f"🔔 Sell trigger set: {' or '.join(trigger_parts)} -- you'll see this on Today once reached.")

        edit_col, delete_col = st.columns(2)
        with edit_col:
            if st.button("✏️ Edit", key=f"dd_edit_btn_{version_id}"):
                st.session_state[edit_key] = True
                st.rerun()
        with delete_col:
            if st.button("🗑️ Delete", key=f"dd_delete_{version_id}"):
                database.delete_deep_dive(version_id, user_email)
                st.success("Version deleted.")
                st.rerun()
    else:
        edit_business = st.text_area("Business overview", value=version.get("business_overview") or "", key=f"dd_edit_business_{version_id}")
        edit_thesis = st.text_area("Investment thesis", value=version.get("investment_thesis") or "", key=f"dd_edit_thesis_{version_id}")
        edit_thesis_score = st.columns([1, 1])[0].slider(
            "How compelling is the thesis?", 1, 10, int(version.get("thesis_score") or 5), key=f"dd_edit_thesis_score_{version_id}"
        )
        edit_management = st.text_area("Management/CEO", value=version.get("management_assessment") or "", key=f"dd_edit_management_{version_id}")
        edit_management_score = st.columns([1, 1])[0].slider(
            "How much confidence in management?", 1, 10, int(version.get("management_score") or 5), key=f"dd_edit_management_score_{version_id}"
        )
        edit_bear = st.text_area("Bear case", value=version.get("bear_case") or "", key=f"dd_edit_bear_{version_id}")
        edit_bear_score = st.columns([1, 1])[0].slider(
            "How manageable are the risks?", 1, 10, int(version.get("bear_case_score") or 5), key=f"dd_edit_bear_score_{version_id}",
            help="Higher = the risks are limited/well understood, not 'the risks are severe'.",
        )
        edit_valuation = st.text_area("Valuation", value=version.get("valuation_view") or "", key=f"dd_edit_valuation_{version_id}")
        edit_valuation_score = st.columns([1, 1])[0].slider(
            "How attractive is the valuation?", 1, 10, int(version.get("valuation_score") or 5), key=f"dd_edit_valuation_score_{version_id}"
        )
        edit_interested_price = st.number_input(
            f"Interested from price ({ticker_currency_symbol.strip()})", min_value=0.0, step=0.01,
            value=float(version.get("interested_price") or 0.0), key=f"dd_edit_price_{version_id}",
        )
        edit_technical_analysis = st.text_area(
            "Technical analysis", value=version.get("technical_analysis") or "", key=f"dd_edit_ta_{version_id}"
        )
        edit_technical_analysis_score = st.columns([1, 1])[0].slider(
            "How favorable is the technical setup?", 1, 10, int(version.get("technical_analysis_score") or 5), key=f"dd_edit_ta_score_{version_id}"
        )
        edit_catalysts = st.text_area("Catalysts", value=version.get("catalysts") or "", key=f"dd_edit_catalysts_{version_id}")
        edit_catalysts_score = st.columns([1, 1])[0].slider(
            "How strong are the catalysts?", 1, 10, int(version.get("catalysts_score") or 5), key=f"dd_edit_catalysts_score_{version_id}"
        )
        edit_sizing = st.text_area("Position sizing plan", value=version.get("position_sizing_plan") or "", key=f"dd_edit_sizing_{version_id}")
        edit_sell_criteria = st.text_area("Sell criteria", value=version.get("sell_criteria") or "", key=f"dd_edit_sell_{version_id}")

        edit_trigger_cols = st.columns(2)
        with edit_trigger_cols[0]:
            edit_sell_trigger_price = st.number_input(
                f"Sell at price ({ticker_currency_symbol.strip()})", min_value=0.0, step=0.01,
                value=float(version.get("sell_trigger_price") or 0.0), key=f"dd_edit_trigger_price_{version_id}",
            )
        with edit_trigger_cols[1]:
            existing_trigger_date = version.get("sell_trigger_date")
            if existing_trigger_date and isinstance(existing_trigger_date, str):
                try:
                    existing_trigger_date = datetime.strptime(existing_trigger_date, "%Y-%m-%d").date()
                except Exception:
                    existing_trigger_date = None
            edit_sell_trigger_date = st.date_input(
                "Sell by date", value=existing_trigger_date, key=f"dd_edit_trigger_date_{version_id}",
            )

        conclusion_options = ["Watch", "Buy", "Pass"]
        current_conclusion_index = (
            conclusion_options.index(version["conclusion"]) if version.get("conclusion") in conclusion_options else 0
        )
        edit_conclusion = st.selectbox(
            "Conclusion", conclusion_options, index=current_conclusion_index, key=f"dd_edit_conclusion_{version_id}"
        )

        save_col, cancel_col = st.columns(2)
        with save_col:
            if st.button("💾 Save changes", type="primary", key=f"dd_save_edit_{version_id}"):
                database.update_deep_dive(
                    version_id, user_email,
                    business_overview=edit_business or None,
                    investment_thesis=edit_thesis or None,
                    management_assessment=edit_management or None,
                    bear_case=edit_bear or None,
                    valuation_view=edit_valuation or None,
                    interested_price=edit_interested_price or None,
                    catalysts=edit_catalysts or None,
                    position_sizing_plan=edit_sizing or None,
                    sell_criteria=edit_sell_criteria or None,
                    conclusion=edit_conclusion,
                    sell_trigger_price=edit_sell_trigger_price or None,
                    sell_trigger_date=edit_sell_trigger_date.isoformat() if edit_sell_trigger_date else None,
                    thesis_score=edit_thesis_score,
                    management_score=edit_management_score,
                    bear_case_score=edit_bear_score,
                    valuation_score=edit_valuation_score,
                    catalysts_score=edit_catalysts_score,
                    technical_analysis=edit_technical_analysis or None,
                    technical_analysis_score=edit_technical_analysis_score,
                )
                st.session_state[edit_key] = False
                st.success("Version updated.")
                st.rerun()
        with cancel_col:
            if st.button("Cancel", key=f"dd_cancel_edit_{version_id}"):
                st.session_state[edit_key] = False
                st.rerun()

    st.markdown("**Images**")
    existing_images = database.get_deep_dive_images(version_id)
    if existing_images:
        img_cols = st.columns(min(len(existing_images), 3))
        for i, img in enumerate(existing_images):
            with img_cols[i % len(img_cols)]:
                st.image(img["image_url"], caption=img.get("caption") or None)
                if st.button("🗑️ Remove image", key=f"dd_img_delete_{img['id']}"):
                    database.delete_deep_dive_image(img["id"], user_email)
                    st.rerun()

    uploaded_image = st.file_uploader(
        "Add an image (chart, screenshot, etc.)", type=["png", "jpg", "jpeg"],
        key=f"dd_img_upload_{version_id}",
    )
    if uploaded_image is not None:
        image_caption = st.text_input("Caption (optional)", key=f"dd_img_caption_{version_id}")
        if st.button("Upload image", key=f"dd_img_upload_btn_{version_id}"):
            database.upload_deep_dive_image(
                user_email, version_id, uploaded_image.getvalue(), uploaded_image.name,
                uploaded_image.type, image_caption or None,
            )
            st.success("Image uploaded!")
            st.rerun()

    st.divider()


def get_deep_dive_triggers_hit(user_email: str, max_items: int = 5) -> list:
    """
    Checkt of een van je deep-dive-verkoop-triggers (prijs of datum) is
    bereikt -- gebruikt de MEEST RECENTE versie per ticker (je huidige
    kijk, niet een verouderde). De richting van een prijs-trigger wordt
    afgeleid uit de prijs-op-het-moment-van-opslaan (price_at_creation):
    staat de trigger HOGER dan dat, is het een winst-doel (trigger als de
    prijs OMHOOG naar dat niveau gaat); staat 'ie LAGER, is het een
    stop-loss (trigger als de prijs OMLAAG naar dat niveau gaat).

    Een GEBEURTENIS-trigger (vrije tekst in sell_criteria, bv. 'als ze 2
    kwartalen missen') wordt hier bewust NIET gecheckt -- dat kunnen we
    niet automatisch verifiëren, dus dat blijft een handmatig te checken
    herinnering op de Deep-dives-pagina zelf.
    """
    import database

    today = datetime.now().date()
    results = []
    entries = database.get_all_deep_dive_tickers(user_email)
    for entry in entries:
        ticker = entry["ticker"]
        naam = entry["naam"]

        sell_trigger_date = entry.get("sell_trigger_date")
        if sell_trigger_date:
            try:
                trigger_date = (
                    datetime.strptime(sell_trigger_date, "%Y-%m-%d").date()
                    if isinstance(sell_trigger_date, str) else sell_trigger_date
                )
                if trigger_date <= today:
                    results.append({
                        "ticker": ticker, "naam": naam, "type": "date",
                        "detail": f"reached your sell-by date ({sell_trigger_date})",
                    })
            except Exception:
                pass

        sell_trigger_price = entry.get("sell_trigger_price")
        if sell_trigger_price:
            try:
                info = get_cached_ticker_info(ticker)
                current_price = info.get("currentPrice") or info.get("regularMarketPrice")
                if current_price is None:
                    fallback_hist = get_cached_ticker_history(ticker, period="5d")
                    if fallback_hist is not None and not fallback_hist.empty:
                        valid_closes = fallback_hist["Close"].dropna()
                        if not valid_closes.empty:
                            current_price = float(valid_closes.iloc[-1])
                if current_price is not None:
                    trigger_currency_symbol = _currency_symbol_for_ticker(ticker)
                    price_at_creation = entry.get("price_at_creation")
                    is_take_profit = price_at_creation is None or sell_trigger_price >= price_at_creation
                    if is_take_profit and current_price >= sell_trigger_price:
                        results.append({
                            "ticker": ticker, "naam": naam, "type": "price",
                            "detail": f"hit your sell target of {trigger_currency_symbol}{sell_trigger_price:.2f} "
                                      f"(now {trigger_currency_symbol}{current_price:.2f})",
                        })
                    elif not is_take_profit and current_price <= sell_trigger_price:
                        results.append({
                            "ticker": ticker, "naam": naam, "type": "price",
                            "detail": f"hit your stop-loss of {trigger_currency_symbol}{sell_trigger_price:.2f} "
                                      f"(now {trigger_currency_symbol}{current_price:.2f})",
                        })
            except Exception:
                continue

    return results[:max_items]


def get_deep_dive_market_snapshot(ticker: str) -> dict:
    """
    Verzamelt automatisch marktdata voor een deep-dive, op het moment van
    opslaan -- wordt als 'foto op dat moment' bij die versie bewaard, zodat
    je later kan zien wat de marktsituatie was toen je die versie schreef
    (in plaats van steeds de HUIDIGE, inmiddels verouderde cijfers te tonen
    bij een oude versie).
    """
    snapshot = {
        "price_at_creation": None,
        "fifty_two_week_high_at_creation": None,
        "fifty_two_week_low_at_creation": None,
        "market_cap_at_creation": None,
        "sector_at_creation": None,
        "dividend_yield_at_creation": None,
        "in_own_signals_at_creation": None,
        "sector_rotation_pct_at_creation": None,
    }
    try:
        info = get_cached_ticker_info(ticker)
    except Exception:
        info = {}

    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if current_price is None:
        # Zelfde robuuste terugval als bij Performance/Dividend -- sommige
        # effecten missen deze velden in .info.
        try:
            fallback_hist = get_cached_ticker_history(ticker, period="5d")
            if fallback_hist is not None and not fallback_hist.empty:
                valid_closes = fallback_hist["Close"].dropna()
                if not valid_closes.empty:
                    current_price = float(valid_closes.iloc[-1])
        except Exception:
            pass

    snapshot["price_at_creation"] = current_price
    snapshot["fifty_two_week_high_at_creation"] = info.get("fiftyTwoWeekHigh")
    snapshot["fifty_two_week_low_at_creation"] = info.get("fiftyTwoWeekLow")
    snapshot["market_cap_at_creation"] = info.get("marketCap")
    sector = info.get("sector")
    snapshot["sector_at_creation"] = sector

    dividend_rate = get_annual_dividend_rate(ticker, info)
    if dividend_rate and current_price:
        snapshot["dividend_yield_at_creation"] = round(dividend_rate / current_price * 100, 2)

    # Kruisverband met je eigen signalen (Daily, Momentocrats, Snowballers, Rocket List)
    own_signals = []
    signal_files = {
        "Daily": "supertrend_signals_daily.csv",
        "Momentocrats": "supertrend_signals.csv",
        "Snowballers": "snowball_signals.csv",
        "Rocket List": "rocket_list_signals.csv",
    }
    for label, filename in signal_files.items():
        try:
            if os.path.exists(filename):
                df_signal = pd.read_csv(filename)
                if "ticker" in df_signal.columns and ticker in df_signal["ticker"].values:
                    own_signals.append(label)
        except Exception:
            continue
    snapshot["in_own_signals_at_creation"] = ", ".join(own_signals) if own_signals else None

    # Sector-rotatie-context: waar staat DEZE sector momenteel in de rangschikking?
    if sector:
        mapped_sector = YFINANCE_SECTOR_TO_OURS.get(sector)
        if mapped_sector:
            try:
                rotation = build_sector_rotation(region="US")
                match = next((r for r in rotation if r["sector"] == mapped_sector), None)
                if match:
                    snapshot["sector_rotation_pct_at_creation"] = match["return_pct"]
            except Exception:
                pass

    return snapshot


def _currency_symbol_for_ticker(ticker: str) -> str:
    """
    Geeft het juiste valutasymbool terug, gebaseerd op de valuta waarin
    het aandeel ZELF noteert (i.p.v. altijd standaard EUR te tonen) --
    belangrijk omdat een groot deel van de aankopen in USD is, maar niet
    alles (bv. Europese aandelen blijven gewoon EUR).
    """
    try:
        info = get_cached_ticker_info(ticker)
        currency = info.get("currency", "EUR")
    except Exception:
        currency = "EUR"
    symbol_map = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CHF": "CHF ", "CAD": "C$"}
    return symbol_map.get(currency, f"{currency} ")


def get_company_logo_url(ticker: str) -> str:
    """
    Geeft een logo-URL terug via Google's eigen, gratis favicon-dienst --
    geen aanmelding/API-sleutel nodig, en betrouwbaarder dan een kleine,
    losse gratis-dienst (Clearbit's gratis logo-API, ooit de standaardkeuze
    hiervoor, is per december 2025 gestopt te bestaan). Gebaseerd op het
    bedrijfsdomein uit yfinance's 'website'-veld. Geeft None terug als er
    geen domein bekend is.
    """
    try:
        info = get_cached_ticker_info(ticker)
        website = info.get("website")
        if not website:
            return None
        domain = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
        return f"https://www.google.com/s2/favicons?domain={domain}&sz=256"
    except Exception:
        return None


def get_earnings_surprises_from_signals(max_items: int = 5, max_days_old: int = 21) -> list:
    """
    Licht signalen met een opvallende recente winst-verrassing uit de
    bestaande screener-CSV's (dagelijks + wekelijks) -- geen nieuwe
    data-ophaal nodig, dit zit al in de bestaande scores verwerkt.
    Alleen relevant tijdens 'earnings season' -- 21 dagen (~3 weken) dekt
    de kern van een kwartaal-rapportageperiode, zonder maanden later nog
    stale verrassingen te tonen (bedrijven rapporteren maar 1x per kwartaal).
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


# Handmatig bijgehouden kalender van de belangrijkste, maanden-vooruit-
# aangekondigde macro-events (FOMC + ECB-rentebesluiten). Bron: officiële
# Fed/ECB-kalenders. Bijwerken zodra een nieuw jaar bekend wordt gemaakt
# (meestal 1x per jaar, eind vorig jaar/begin dit jaar).
from macro_events import MACRO_EVENTS_2026, get_todays_macro_events


def get_upcoming_ex_dividend_dates(holdings: list, infos: dict, days_ahead: int = 5, max_items: int = 3) -> list:
    """
    Checkt of een van je HUIDIGE posities binnen 'days_ahead' dagen
    ex-dividend gaat -- zelfde 'alleen daadwerkelijk toekomstige datums'-
    filtering als Analyze's Dividend-kaart (yfinance's exDividendDate is
    soms de meest recente, al-gepasseerde datum i.p.v. een toekomstige).
    """
    today = datetime.now().date()
    results = []
    for h in holdings:
        info = infos.get(h["ticker"], {})
        ex_div = info.get("exDividendDate")
        if not ex_div:
            continue
        try:
            ex_div_date = pd.Timestamp(ex_div, unit="s").date()
            days_until = (ex_div_date - today).days
            if 0 <= days_until <= days_ahead:
                results.append({"naam": h["naam"], "ticker": h["ticker"],
                                 "ex_div_date": ex_div_date, "days_until": days_until})
        except Exception:
            continue
    results.sort(key=lambda r: r["days_until"])
    return results[:max_items]


def get_todays_portfolio_earnings(tracked_items: list, max_items: int = 3) -> list:
    """
    Checkt of een van je posities/watchlist-items VANDAAG earnings rapporteert
    (yfinance geeft ook toekomstige, aangekondigde earnings-datums terug).
    """
    today = datetime.now().date()
    results = []
    for item in tracked_items:
        try:
            dates_df = yf.Ticker(item["ticker"]).get_earnings_dates(limit=8)
            if dates_df is None or dates_df.empty:
                continue
            for earnings_date in dates_df.index:
                if earnings_date.date() == today:
                    results.append({"naam": item["naam"], "ticker": item["ticker"]})
                    break
        except Exception:
            continue
        if len(results) >= max_items:
            break
    return results[:max_items]


def get_upcoming_portfolio_earnings(tracked_items: list, days_ahead: int = 5, max_items: int = 3) -> list:
    """
    Checkt of een van je posities/watchlist-items binnen 'days_ahead' dagen
    earnings rapporteert (VANDAAG zelf niet meegeteld -- dat toont
    get_todays_portfolio_earnings al apart). Geeft een korte vooraankondiging,
    zodat je niet pas op de dag zelf verrast wordt.
    """
    today = datetime.now().date()
    results = []
    for item in tracked_items:
        try:
            dates_df = yf.Ticker(item["ticker"]).get_earnings_dates(limit=8)
            if dates_df is None or dates_df.empty:
                continue
            for earnings_date in dates_df.index:
                days_until = (earnings_date.date() - today).days
                if 1 <= days_until <= days_ahead:
                    results.append({"naam": item["naam"], "ticker": item["ticker"],
                                     "earnings_date": earnings_date.date(), "days_until": days_until})
                    break
        except Exception:
            continue
    results.sort(key=lambda r: r["days_until"])
    return results[:max_items]


def get_52_week_records(holdings: list, infos: dict, max_items: int = 3) -> list:
    """
    Checkt of een van je posities vandaag een nieuwe 52-weken-hoogte of
    -laagte heeft geraakt. yfinance's fiftyTwoWeekHigh/Low weerspiegelen
    het ROLLENDE 52-weken-record t/m de laatste koers -- als de huidige
    prijs daaraan gelijk is (of eroverheen), is vandaag het nieuwe record.
    """
    results = []
    for h in holdings:
        info = infos.get(h["ticker"], {})
        high_52wk = info.get("fiftyTwoWeekHigh")
        low_52wk = info.get("fiftyTwoWeekLow")
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        if current_price is None:
            try:
                fallback_hist = get_cached_ticker_history(h["ticker"], period="5d")
                if fallback_hist is not None and not fallback_hist.empty:
                    current_price = float(fallback_hist["Close"].iloc[-1])
            except Exception:
                continue
        if current_price is None:
            continue
        if high_52wk and current_price >= high_52wk:
            results.append({"naam": h["naam"], "ticker": h["ticker"], "type": "high"})
        elif low_52wk and current_price <= low_52wk:
            results.append({"naam": h["naam"], "ticker": h["ticker"], "type": "low"})
    return results[:max_items]


def send_subscription_confirmation_email(email: str, confirmation_token: str, unsubscribe_token: str) -> None:
    """
    Stuurt de dubbele-opt-in-bevestigingsmail voor de niet-ingelogde
    e-mail-aanmelding, in dezelfde huisstijl (donkere header + teal-
    accent) als de bestaande dagelijkse/wekelijkse mails. Bevat ook
    meteen een uitschrijflink, zodat iemand die per ongeluk bevestigt
    niet hoeft te wachten op de eerste dagelijkse mail om zich weer af
    te melden.
    """
    confirm_url = f"https://hestys.streamlit.app/?view=confirm&token={confirmation_token}"
    unsubscribe_url = f"https://hestys.streamlit.app/?view=unsubscribe&token={unsubscribe_token}"
    text_body = (
        "Confirm your subscription to Hesty's Daily\n\n"
        "One more step: click the link below to confirm this is your email address.\n\n"
        f"{confirm_url}\n\n"
        "Didn't request this? You can safely ignore this email, or unsubscribe here:\n"
        f"{unsubscribe_url}\n\n"
        "-- Hesty's, your personal investment assistant"
    )
    html_body = f"""
    <div style="font-family: -apple-system, 'Segoe UI', Roboto, Arial, sans-serif; max-width: 600px; margin: 0 auto; background:#ffffff;">
        <div style="background:#101825; padding: 28px 24px; border-radius: 12px 12px 0 0;">
            <div style="color:#1FAE96; font-size:13px; font-weight:600; letter-spacing:1px; text-transform:uppercase;">Hesty's Daily</div>
            <div style="color:#EAEDF1; font-size:22px; font-weight:700; margin-top:4px;">Confirm your subscription</div>
        </div>
        <div style="padding: 24px; border: 1px solid #E5E8EC; border-top: none; border-radius: 0 0 12px 12px;">
            <p style="font-size:15px; color:#101825; line-height:1.5; margin-top:0;">
                One more step: click the button below to confirm this is your email address.
            </p>
            <p style="margin-top:20px;">
                <a href="{confirm_url}" style="background:#1FAE96; color:#ffffff; padding:12px 24px; border-radius:8px; text-decoration:none; font-weight:600; display:inline-block;">Confirm subscription</a>
            </p>
            <p style="margin-top:24px; font-size:13px; color:#9AA1AC;">
                Didn't request this? You can safely ignore this email, or
                <a href="{unsubscribe_url}" style="color:#9AA1AC;">unsubscribe here</a>.
            </p>
            <p style="margin-top:20px; font-size:14px; color:#101825; font-weight:600;">&mdash; Hesty's, your personal investment assistant</p>
        </div>
    </div>
    """
    send_email(
        subject="Confirm your subscription to Hesty's Daily",
        body_text=text_body, body_html=html_body, to_email=email,
    )


def get_top_news_for_tickers(holdings_and_watchlist: list, max_items: int = 3) -> list:
    """
    Haalt nieuws op voor alle meegegeven tickers, en geeft de meest recente
    'max_items' items terug. Dedupliceert op artikel-URL -- 1 artikel dat
    toevallig meerdere van je posities noemt (bv. een brede markt-roundup)
    moet 1x verschijnen, niet 1x per positie die het noemt. Als hetzelfde
    artikel voor meerdere posities gevonden wordt, worden hun namen
    gecombineerd i.p.v. willekeurig de eerste te tonen.
    """
    import screener as _screener  # lokale import: voorkomt een cirkelverwijzing bij module-laadtijd

    news_by_link: dict = {}
    link_order = []
    for item in holdings_and_watchlist:
        try:
            news_items = _screener.get_recent_news(item["ticker"], max_items=3, days_back=3)
        except Exception:
            news_items = []
        for n in news_items:
            link = n.get("link")
            if link in news_by_link:
                if item["naam"] not in news_by_link[link]["naam"]:
                    news_by_link[link]["naam"] += f", {item['naam']}"
            else:
                n["naam"] = item["naam"]
                news_by_link[link] = n
                link_order.append(link)

    all_news = [news_by_link[link] for link in link_order]
    all_news.sort(key=lambda x: x["published"], reverse=True)
    return all_news[:max_items]


def parse_degiro_transactions_csv(file_bytes: bytes) -> dict:
    """
    Parseert een DEGIRO 'Transacties'-export (CSV). Groepeert per ISIN (of
    productnaam als er geen ISIN is, zoals bij crypto) en geeft per groep de
    losse buy/sell-transacties terug, al omgerekend naar EUR-prijs + EUR-fee.

    Bewuste keuzes:
    - Prijs en fee worden ALTIJD in EUR berekend (uit 'Waarde EUR' en
      'Totaal EUR'), niet uit de kolom 'Koers' zelf (die staat vaak in de
      lokale valuta, bv. USD) -- zo blijft alles consistent met de rest
      van de site.
    - Sommige crypto-rijen missen 'Aantal' in de export zelf -- die
      leiden we af uit lokale waarde / koers.
    - Rijen die zelfs dan niet te verwerken zijn (bv. een lege regel)
      worden overgeslagen en gerapporteerd, niet stilzwijgend genegeerd.
    """
    import io

    def parse_dutch_number(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip()
        if not s or s.lower() == "nan":
            return None
        return float(s.replace(".", "").replace(",", "."))

    df = pd.read_csv(io.BytesIO(file_bytes))

    grouped: dict = {}
    skipped_rows: list = []

    for idx, row in df.iterrows():
        product = row.get("Product")
        isin = row.get("ISIN")
        datum = row.get("Datum")

        if pd.isna(product) or pd.isna(datum):
            skipped_rows.append((idx, "Missing product name or date"))
            continue

        aantal = row.get("Aantal")
        koers = parse_dutch_number(row.get("Koers"))
        lokale_waarde = parse_dutch_number(row.get("Lokale waarde"))
        waarde_eur = parse_dutch_number(row.get("Waarde EUR"))
        totaal_eur = parse_dutch_number(row.get("Totaal EUR"))

        if pd.isna(aantal):
            if lokale_waarde is not None and koers not in (None, 0):
                # Aantal en lokale waarde hebben TEGENGESTELDE tekens (een koop
                # heeft een positief Aantal maar een negatieve lokale waarde --
                # geld gaat eruit) -- vandaar de min hier, anders komt een koop
                # er per ongeluk als verkoop uit te zien.
                aantal = -lokale_waarde / koers
            else:
                skipped_rows.append((idx, f"{product}: could not determine quantity"))
                continue
        else:
            aantal = float(aantal)

        if aantal == 0 or waarde_eur is None or totaal_eur is None:
            skipped_rows.append((idx, f"{product}: missing or zero value fields"))
            continue

        price_eur = abs(waarde_eur) / abs(aantal)
        fee_eur = abs(totaal_eur - waarde_eur)

        try:
            parsed_date = pd.to_datetime(datum, format="%d-%m-%Y").date().isoformat()
        except Exception:
            skipped_rows.append((idx, f"{product}: could not parse date '{datum}'"))
            continue

        key = isin if not pd.isna(isin) else product
        if key not in grouped:
            grouped[key] = {
                "product": product,
                "isin": isin if not pd.isna(isin) else None,
                "transactions": [],
            }

        grouped[key]["transactions"].append({
            "transaction_type": "buy" if aantal > 0 else "sell",
            "shares": round(abs(aantal), 6),
            "price": round(price_eur, 4),
            "fee": round(fee_eur, 2),
            "transaction_date": parsed_date,
        })

    return {"grouped": grouped, "skipped_rows": skipped_rows}


def filter_active_holdings(holdings: list) -> list:
    """
    Verbergt posities die op 0 shares staan (volledig verkocht, bv. via
    een bulk-import waarbij koop+verkoop samen tot 0 optellen) -- shares
    van None (nog helemaal niet ingevuld/bekend) blijft wel gewoon zichtbaar.
    """
    return [h for h in holdings if h.get("shares") is None or abs(h["shares"]) > 0.0001]


def sync_holding_shares_from_transactions(holding_id: int, user_email: str) -> float:
    """
    Herberekent het aantal shares uit ALLE transacties van deze positie, en
    schrijft dat terug naar portfolio_holdings.shares -- zodat de rest van
    de app (portfolio-waarde, concentratie-berekeningen, etc.) gewoon het
    opgeslagen 'shares'-veld kan blijven gebruiken, zonder overal apart de
    transacties te moeten optellen. Moet aangeroepen worden na ELKE
    toegevoegde of verwijderde transactie. Geeft het nieuwe aantal terug.
    """
    import database
    transactions = database.get_transactions_for_holding(user_email, holding_id)
    derived_shares = sum(
        t["shares"] if t["transaction_type"] == "buy" else -t["shares"]
        for t in transactions
    )
    database.update_holding_shares(holding_id, user_email, derived_shares)
    return derived_shares


def _looks_like_isin(value: str) -> bool:
    """Checkt of een string er zelf uitziet als een ISIN (2 letters + 9 alfanumeriek + 1 cijfer,
    12 tekens totaal) -- gebruikt om te detecteren als Yahoo's zoekfunctie per ongeluk de
    ISIN zelf teruggeeft als 'symbool' (komt voor bij ETF's met meerdere beursnoteringen)."""
    if not value or len(value) != 12:
        return False
    return value[:2].isalpha() and value[2:11].isalnum() and value[11].isdigit()


def get_ticker_candidates(product_name: str, isin: str = None) -> list:
    """
    Zoekt mogelijke ticker-kandidaten voor een positie uit een broker-
    export -- geeft een LIJST terug (niet alleen de beste gok), zodat de
    gebruiker bij twijfel zelf kan kiezen. Dit is nodig omdat veel
    fondsen (vooral UCITS-ETF's) op MEERDERE beurzen tegelijk genoteerd
    staan (bv. 'SMH' op de VS-beurs, in Milaan, EN Londen, elk met een
    andere prijs) -- een enkele blinde gok kan zomaar de verkeerde
    beursnotering pakken, met verkeerde koersen als gevolg.

    Elke kandidaat is een dict met 'symbol', 'name', 'exchange'. Filtert
    de valse 'ISIN als symbool'-match weg (zie _looks_like_isin). Bij
    crypto (geen ISIN) filteren we op quoteType 'CRYPTOCURRENCY'.
    """
    candidates = []
    seen_symbols = set()

    def _add_results(results):
        for r in results:
            symbol = r.get("symbol")
            if not symbol or symbol in seen_symbols or _looks_like_isin(symbol):
                continue
            seen_symbols.add(symbol)
            candidates.append({
                "symbol": symbol,
                "name": r.get("shortname") or r.get("longname") or symbol,
                "exchange": r.get("exchange", ""),
            })

    if isin:
        try:
            _add_results(yf.Search(isin, max_results=6).quotes)
        except Exception:
            pass
    else:
        try:
            all_results = yf.Search(product_name, max_results=6).quotes
            _add_results([r for r in all_results if r.get("quoteType") == "CRYPTOCURRENCY"])
        except Exception:
            pass

    if not candidates:
        try:
            _add_results(yf.Search(product_name, max_results=6).quotes)
        except Exception:
            pass

    return candidates


def guess_ticker_for_product(product_name: str, isin: str = None) -> str:
    """Compacte variant van get_ticker_candidates() die alleen de beste gok teruggeeft."""
    candidates = get_ticker_candidates(product_name, isin)
    return candidates[0]["symbol"] if candidates else None


# De 5 grootste/bekendste wereldwijde indices, als benchmark-keuze bij Performance
BENCHMARK_OPTIONS = {
    "S&P 500": "^GSPC",
    "NASDAQ Composite": "^IXIC",
    "EURO STOXX 50": "^STOXX50E",
}


def compute_price_return(price_history: pd.DataFrame, days_back: int = None, since_date=None) -> float:
    """
    Berekent het %-koersrendement over een periode -- ofwel de laatste
    'days_back' dagen, ofwel sinds een specifieke datum ('since_date',
    bv. 1 januari voor YTD). Puur op prijs gebaseerd (niet
    transactie-gebaseerd). Geeft None terug bij te weinig data.
    """
    if price_history is None or price_history.empty:
        return None
    price_history = price_history.sort_index()
    latest_price = float(price_history["Close"].iloc[-1])
    index_naive = price_history.index.tz_localize(None) if price_history.index.tz is not None else price_history.index

    if since_date is not None:
        mask = index_naive >= pd.Timestamp(since_date)
        if not mask.any():
            return None
        start_price = float(price_history["Close"].iloc[mask.argmax()])
    elif days_back is not None:
        cutoff = index_naive[-1] - pd.Timedelta(days=days_back)
        mask = index_naive <= cutoff
        if not mask.any():
            return None
        start_price = float(price_history["Close"].iloc[np.where(mask)[0][-1]])
    else:
        return None

    if start_price == 0:
        return None
    return (latest_price - start_price) / start_price * 100


def get_ticker_ytd_and_1y_return(ticker: str) -> dict:
    """Haalt YTD- en 1-jaars-koersrendement op voor 1 ticker."""
    try:
        history = yf.Ticker(ticker).history(period="2y")
    except Exception:
        return {"ytd_pct": None, "one_year_pct": None}
    if history is None or history.empty:
        return {"ytd_pct": None, "one_year_pct": None}

    jan_1_this_year = datetime(datetime.now().year, 1, 1)
    return {
        "ytd_pct": compute_price_return(history, since_date=jan_1_this_year),
        "one_year_pct": compute_price_return(history, days_back=365),
    }


def _price_near_date(history: pd.DataFrame, target_date, tolerance_days: int = 10):
    """
    Zoekt de koers het dichtst bij een specifieke datum, BINNEN een al
    opgehaalde (langere) geschiedenis -- i.p.v. voor elke periode een
    aparte, nieuwe netwerk-aanroep te doen. Geeft None terug als er geen
    geldige koers binnen de tolerantie ligt.
    """
    if history is None or history.empty:
        return None
    valid = history[history["Close"].notna()]
    if valid.empty:
        return None
    # yfinance geeft vaak een tijdzone-BEWUSTE index terug (bv.
    # 'America/New_York'), terwijl 'target_date' een gewone, tijdzone-
    # NAIEVE datum is -- zonder dit te normaliseren gooit pandas een fout
    # bij het vergelijken. Die fout werd elders stilzwijgend opgevangen
    # (try/except), waardoor sommige posities ONTBRAKEN uit de
    # berekening -- dat verklaarde de absurd hoge percentages (beginwaarde
    # onvolledig, eindwaarde wel compleet).
    index = valid.index
    if getattr(index, "tz", None) is not None:
        index = index.tz_localize(None)
    target_ts = pd.Timestamp(target_date)
    time_diffs = abs(index - target_ts)
    closest_pos = time_diffs.argmin()
    if time_diffs[closest_pos].days > tolerance_days:
        return None
    return float(valid["Close"].iloc[closest_pos])


@st.cache_data(ttl=3600, show_spinner=False)
def _batch_download_history(tickers_tuple: tuple, period: str = "max") -> dict:
    """
    Haalt de koersgeschiedenis van MEERDERE tickers op in 1 netwerk-
    aanroep (yfinance's batch-download), i.p.v. een aparte aanroep per
    ticker -- dit was de resterende bron van traagheid nadat de eerdere
    fix (1x per periode i.p.v. per periode-per-positie) al hielp, maar bij
    veel posities nog steeds 1 aanroep per positie deed.
    """
    tickers = list(tickers_tuple)
    if not tickers:
        return {}
    try:
        if len(tickers) == 1:
            data = yf.download(tickers[0], period=period, progress=False)
            return {tickers[0]: data}
        data = yf.download(tickers, period=period, progress=False, group_by="ticker")
        result = {}
        for ticker in tickers:
            try:
                result[ticker] = data[ticker]
            except Exception:
                result[ticker] = None
        return result
    except Exception:
        # Terugval: als de batch-download als geheel faalt, toch 1-voor-1
        # proberen -- trager, maar beter dan helemaal geen data.
        result = {}
        for ticker in tickers:
            try:
                result[ticker] = get_cached_ticker_history(ticker, period=period)
            except Exception:
                result[ticker] = None
        return result


def get_shared_history_for_holdings(holdings: list, period: str = "max") -> dict:
    """
    Haalt de koersgeschiedenis van AL je posities in 1x op (via een
    gecachte batch-download), voor hergebruik door MEERDERE berekeningen
    (YTD, 1-jaar, en de portfoliowaarde-over-tijd-grafiek) -- i.p.v. dat
    elke periode of elke positie zijn eigen, aparte netwerk-aanroep doet.
    """
    unique_tickers = tuple(sorted({h["ticker"] for h in holdings}))
    return _batch_download_history(unique_tickers, period=period)


def compute_portfolio_value_over_time(holdings: list, user_email: str, history_by_ticker: dict, num_points: int = 60) -> list:
    """
    Berekent de TOTALE portfoliowaarde op meerdere momenten in het
    verleden (gelijk verdeeld tussen je vroegste transactie en vandaag) --
    voor de 'zie je portfolio groeien'-grafiek. Gebruikt de AL opgehaalde,
    gedeelde geschiedenis (history_by_ticker) -- dus GEEN extra netwerk-
    aanroepen nodig, ondanks dat er relatief veel punten berekend worden.
    """
    import database

    all_transactions = {}
    earliest = None
    for h in holdings:
        transactions = database.get_transactions_for_holding(user_email, h["id"])
        all_transactions[h["ticker"]] = transactions
        for t in transactions:
            t_date = datetime.strptime(t["transaction_date"], "%Y-%m-%d").date()
            if earliest is None or t_date < earliest:
                earliest = t_date

    if earliest is None:
        return []

    today = datetime.now().date()
    total_days = (today - earliest).days
    if total_days <= 0:
        return []

    points = [
        earliest + timedelta(days=int(total_days * i / num_points))
        for i in range(num_points + 1)
    ]

    series = []
    for point_date in points:
        total_value = 0.0
        any_value = False
        for h in holdings:
            ticker = h["ticker"]
            shares_at_point = 0.0
            for t in all_transactions.get(ticker, []):
                t_date = datetime.strptime(t["transaction_date"], "%Y-%m-%d").date()
                if t_date <= point_date:
                    delta = t["shares"] if t["transaction_type"] == "buy" else -t["shares"]
                    shares_at_point += delta
            if shares_at_point > 0.0001:
                price = _price_near_date(history_by_ticker.get(ticker), point_date, tolerance_days=15)
                if price is not None:
                    total_value += shares_at_point * price
                    any_value = True
        if any_value:
            series.append({"date": point_date, "value": total_value})

    return series


def compute_personal_windowed_return(holdings: list, user_email: str, window_start, history_by_ticker: dict = None) -> dict:
    """
    Berekent je ECHTE, persoonlijke rendement over een specifieke periode
    (bv. YTD of de laatste 12 maanden) -- een vereenvoudigde Dietz-methode:

    - Begin-waarde: shares die je AL had vóór 'window_start', gewaardeerd
      tegen de koers van toen (niet je oorspronkelijke aankoopprijs --
      we meten wat er BINNEN deze periode is gebeurd)
    - Netto-inleg: aankopen (+) en verkopen (-) die BINNEN de periode
      vielen
    - Eind-waarde: de huidige positie-waarde nu

    Rendement = (eind-waarde - begin-waarde - netto-inleg) / (begin-waarde + netto-inleg)

    Geeft None terug als er te weinig data is om iets te zeggen.

    'history_by_ticker' (optioneel): een AL opgehaalde, langere
    koersgeschiedenis per ticker (bv. 3 jaar) -- als meegegeven, wordt
    die HERGEBRUIKT i.p.v. een nieuwe, aparte netwerk-aanroep per periode
    te doen. Dit is de kern van de snelheidsfix: zonder dit deed elke
    aparte periode (YTD, 1-jaar, straks meer) zijn EIGEN aanroep per
    positie, wat met meerdere periodes en posities snel optelde.
    """
    import database

    starting_value = 0.0
    net_contributions = 0.0
    ending_value = 0.0
    any_starting_data = False

    for h in holdings:
        transactions = database.get_transactions_for_holding(user_email, h["id"])
        if not transactions:
            continue

        shares_before_window = 0.0
        for t in transactions:
            t_date = datetime.strptime(t["transaction_date"], "%Y-%m-%d").date()
            delta = t["shares"] if t["transaction_type"] == "buy" else -t["shares"]
            if t_date < window_start:
                shares_before_window += delta
            else:
                if t["transaction_type"] == "buy":
                    net_contributions += t["shares"] * t["price"] + t["fee"]
                else:
                    net_contributions -= t["shares"] * t["price"] - t["fee"]

        if shares_before_window > 0.0001:
            try:
                if history_by_ticker is not None:
                    history = history_by_ticker.get(h["ticker"])
                else:
                    # Terugval als er geen gedeelde cache is meegegeven --
                    # werkt nog steeds, alleen zonder het snelheidsvoordeel.
                    history = get_cached_ticker_history(
                        h["ticker"],
                        start=(window_start - timedelta(days=10)).isoformat(),
                        end=(window_start + timedelta(days=10)).isoformat(),
                    )
                price_at_start = _price_near_date(history, window_start)
                if price_at_start is not None:
                    starting_value += shares_before_window * price_at_start
                    any_starting_data = True
            except Exception:
                pass

        position_value = h.get("position_value") or 0.0
        if not pd.isna(position_value):
            ending_value += position_value

    if not any_starting_data and net_contributions == 0:
        return None  # niks om over te rapporteren -- geen posities van vóór deze periode, geen nieuwe inleg

    denominator = starting_value + net_contributions
    if denominator <= 0:
        return None

    gain = ending_value - starting_value - net_contributions
    return_pct = gain / denominator * 100
    if pd.isna(return_pct) or pd.isna(gain):
        # Laatste veiligheidsnet -- zou niet meer moeten gebeuren dankzij de
        # checks hierboven, maar voorkomt sowieso ooit weer een '+nan%'.
        return None
    return {"return_pct": return_pct, "gain": gain}


def compute_holding_performance(transactions: list, current_price: float = None) -> dict:
    """
    Berekent rendement uit een lijst buy/sell-transacties, met de
    gemiddelde-kostprijs-methode (inclusief betaalde fees). Geeft None
    terug als er geen bruikbare transacties zijn -- geen dividenden
    meegenomen (bewust, voor nu).

    current_price is alleen nodig als er nog shares in bezit zijn (voor
    de ongerealiseerde winst/verlies) -- bij een VOLLEDIG GESLOTEN positie
    (0 shares over) is de huidige prijs irrelevant (0 x wat dan ook = 0),
    dus die mag dan gewoon None zijn zonder dat de functie stopt.
    """
    if not transactions:
        return None

    total_bought_shares = sum(tx["shares"] for tx in transactions if tx["transaction_type"] == "buy")
    total_bought_cost = sum(tx["shares"] * tx["price"] + tx["fee"] for tx in transactions if tx["transaction_type"] == "buy")
    total_sold_shares = sum(tx["shares"] for tx in transactions if tx["transaction_type"] == "sell")
    total_sold_proceeds = sum(tx["shares"] * tx["price"] - tx["fee"] for tx in transactions if tx["transaction_type"] == "sell")

    if total_bought_shares <= 0:
        return None  # geen aankopen gelogd, kan geen kostprijs bepalen

    avg_cost_per_share = total_bought_cost / total_bought_shares
    shares_held = total_bought_shares - total_sold_shares

    if shares_held > 0.0001 and current_price is None:
        return None  # er zijn nog shares in bezit, dan is de huidige prijs wel echt nodig

    cost_basis_held = shares_held * avg_cost_per_share
    price_for_calc = current_price if current_price is not None else 0.0
    unrealized_pnl = (price_for_calc * shares_held) - cost_basis_held
    realized_pnl = total_sold_proceeds - (total_sold_shares * avg_cost_per_share)
    total_pnl = unrealized_pnl + realized_pnl
    total_return_pct = (total_pnl / total_bought_cost) * 100 if total_bought_cost > 0 else None

    return {
        "shares_held": round(shares_held, 4),
        "avg_cost_per_share": round(avg_cost_per_share, 4),
        "cost_basis_held": round(cost_basis_held, 2),
        "current_value_held": round(price_for_calc * shares_held, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "realized_pnl": round(realized_pnl, 2),
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": round(total_return_pct, 2) if total_return_pct is not None else None,
    }


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
            hist = get_cached_ticker_history(h["ticker"], period="6mo")
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
# --- Navigatie: leest de '?view=...'-parameter uit de URL. Geen parameter
#     betekent: nog geen tabblad gekozen -- dan is de standaardpagina
#     afhankelijk van of je bent ingelogd. Niet ingelogd -> Discover (toont
#     meteen echte waarde aan een nieuwe bezoeker, geen account nodig).
#     Wel ingelogd -> Today (de gepersonaliseerde, dagelijkse pagina). ---
_default_view = "today" if st.user.is_logged_in else "discover"
current_view = st.query_params.get("view", _default_view)


def _nav_class(view_name: str) -> str:
    return "nav-link active" if current_view == view_name else "nav-link"


def _nav_class_any(view_names: list) -> str:
    return "nav-link active" if current_view in view_names else "nav-link"


header_col, login_col = st.columns([5, 1])

with header_col:
    st.markdown(
        f"""
        <div class="app-header">
            <a href="?view={_default_view}" class="app-header-top" target="_self">
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
                <a href="?view=discover" class="{_nav_class('discover')}" target="_self">Discover</a>
                <a href="?view=today" class="{_nav_class('today')}" target="_self">Today</a>
                <a href="?view=portfolio" class="{_nav_class('portfolio')}" target="_self">My Portfolio</a>
                <a href="?view=analyze" class="{_nav_class('analyze')}" target="_self">Analyze</a>
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
        import database as _database_for_identity
        _database_for_identity.ensure_user_identity(st.user.email, st.user.name)
        st.markdown(
            f'<a href="?view=settings" class="account-link {" active" if current_view == "settings" else ""}" '
            f'target="_self">&#9881; {st.user.name}</a>',
            unsafe_allow_html=True,
        )
        st.button("Log out", on_click=st.logout, key="header_logout")
    else:
        st.button("Log in", on_click=st.login, key="header_login_google", type="primary")

# ============================================================
# VIEW: TODAY
# ============================================================
if current_view == "today":
    st.markdown("### Today")

    if not st.user.is_logged_in:
        st.markdown(
            """
            <div style="background: linear-gradient(135deg, rgba(31,174,150,0.16), rgba(31,174,150,0.02));
                        border: 1px solid rgba(31,174,150,0.4); border-radius: 12px;
                        padding: 1.5rem 1.75rem; margin: 0.5rem 0 1.25rem 0;">
                <div style="color:#1FAE96; font-weight:700; font-size:0.75rem; letter-spacing:1.5px; text-transform:uppercase;">
                    What you're missing
                </div>
                <div style="color:#EAEDF1; font-size:1.4rem; font-weight:700; margin-top:6px; line-height:1.35;">
                    Your own, personalized morning briefing.
                </div>
                <div style="color:#8992A3; font-size:0.95rem; margin-top:10px; line-height:1.6; max-width: 560px;">
                    Log in and add your positions to get a Today page built around YOUR portfolio:
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            "- 📊 Your real return vs. yesterday, and your best/worst performer today\n"
            "- 📆 Earnings coming up this week for your positions -- not just on the day itself\n"
            "- ⚖️ A heads-up if a position outgrows your own risk target\n"
            "- 💰 Upcoming ex-dividend dates for what you actually hold\n"
            "- 🚀 A ping when one of your positions hits a new 52-week high or low\n"
            "- 📰 News, filtered to just the tickers you care about"
        )
        st.markdown(
            '<a href="?view=discover" class="button-link" target="_self">See what Hesty\'s can do (no login) &rarr;</a>',
            unsafe_allow_html=True,
        )
        st.info("Log in (top right) once you're ready, then add positions under My Portfolio or "
                "your Watchlist to unlock this.")
    else:
        import database
        import screener as _screener_module  # noqa: F401 -- zorgt dat get_top_news_for_tickers 'm kan importeren

        user_email = st.user.email
        holdings = filter_active_holdings(database.get_user_holdings(user_email))
        watchlist_items = database.get_user_holdings(user_email, is_watchlist=True)

        st.write("Here are your daily points that deserve your attention.")

        if not holdings and not watchlist_items:
            st.info("Add assets under My Portfolio or your Watchlist to get personal signals and news here.")
        else:
            tracked_items = holdings + watchlist_items

            # --- Your portfolio today (nu in een eigen kader, net als Yesterday's
            # biggest movers -- consistente stijl over de hele Today-pagina) ---
            if holdings:
                with st.spinner("Checking today's price moves..."):
                    daily_stats = build_daily_portfolio_stats(holdings)

                with st.container(border=True):
                    if daily_stats:
                        vs_yesterday_pct = daily_stats["portfolio_change_pct"]
                        vs_yesterday_color = "#1FAE96" if vs_yesterday_pct >= 0 else "#E5484D"
                        st.markdown(
                            f'<div style="display:flex; align-items:baseline; gap:0.5rem; flex-wrap:wrap;">'
                            f'<span style="font-weight:700;">Your Portfolio Today</span>'
                            f'<span style="font-size:0.85rem; font-weight:700; color:{vs_yesterday_color};">'
                            f'{vs_yesterday_pct:+.1f}% vs yesterday</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown("**Your Portfolio Today**")
                    st.caption("How your positions did today.")

                    dcol2, dcol3 = st.columns(2)
                    with dcol2:
                        if daily_stats:
                            st.markdown(
                                f'<div style="text-align:center; padding:0.9rem 0.5rem; border-radius:10px; '
                                f'margin-bottom:0.5rem; background:rgba(31,174,150,0.12);">'
                                f'<div style="font-size:0.7rem; color:#8992A3; text-transform:uppercase; letter-spacing:1px;">'
                                f'Best today</div>'
                                f'<div style="font-size:1.1rem; font-weight:700; color:#EAEDF1; margin-top:4px;">'
                                f'{daily_stats["best_performer"]}</div>'
                                f'<div style="font-size:1.4rem; font-weight:800; color:#1FAE96;">'
                                f'{daily_stats["best_change_pct"]:+.1f}%</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                        else:
                            st.metric("Best today", "n/a")
                    with dcol3:
                        if daily_stats:
                            st.markdown(
                                f'<div style="text-align:center; padding:0.9rem 0.5rem; border-radius:10px; '
                                f'margin-bottom:0.5rem; background:rgba(229,72,77,0.12);">'
                                f'<div style="font-size:0.7rem; color:#8992A3; text-transform:uppercase; letter-spacing:1px;">'
                                f'Worst today</div>'
                                f'<div style="font-size:1.1rem; font-weight:700; color:#EAEDF1; margin-top:4px;">'
                                f'{daily_stats["worst_performer"]}</div>'
                                f'<div style="font-size:1.4rem; font-weight:800; color:#E5484D;">'
                                f'{daily_stats["worst_change_pct"]:+.1f}%</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                        else:
                            st.metric("Worst today", "n/a")

                    st.markdown(
                        '<a href="?view=portfolio" class="button-link" target="_self">View My Portfolio &rarr;</a>',
                        unsafe_allow_html=True,
                    )

            # --- Yesterday's Top Movers (verplaatst hierheen vanuit Discover --
            # dit is een leuk, marktbreed dagelijks contactmoment, past beter bij
            # Today's 'wat is er vandaag interessant'-insteek dan bij Discover) ---
            with st.container(border=True):
                st.markdown("**Yesterday's biggest movers**")
                if os.path.exists("top_movers.csv"):
                    st.caption(f"Last updated: {file_last_modified('top_movers.csv')}")
                    df_movers = pd.read_csv("top_movers.csv").dropna(subset=["change_pct"])
                    if not df_movers.empty:
                        top_gainer = df_movers.loc[df_movers["change_pct"].idxmax()]
                        top_loser = df_movers.loc[df_movers["change_pct"].idxmin()]
                        mover_col1, mover_col2 = st.columns(2)
                        with mover_col1:
                            st.markdown(
                                f'<div style="text-align:center; padding:0.9rem 0.5rem; border-radius:10px; '
                                f'margin-bottom:0.5rem; background:rgba(31,174,150,0.12);">'
                                f'<div style="font-size:0.7rem; color:#8992A3; text-transform:uppercase; letter-spacing:1px;">'
                                f'Top gainer</div>'
                                f'<div style="font-size:1.2rem; font-weight:700; color:#EAEDF1; margin-top:4px;">'
                                f'{top_gainer["ticker"]}</div>'
                                f'<div style="font-size:1.5rem; font-weight:800; color:#1FAE96;">'
                                f'+{top_gainer["change_pct"]:.1f}%</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                        with mover_col2:
                            st.markdown(
                                f'<div style="text-align:center; padding:0.9rem 0.5rem; border-radius:10px; '
                                f'margin-bottom:0.5rem; background:rgba(229,72,77,0.12);">'
                                f'<div style="font-size:0.7rem; color:#8992A3; text-transform:uppercase; letter-spacing:1px;">'
                                f'Top loser</div>'
                                f'<div style="font-size:1.2rem; font-weight:700; color:#EAEDF1; margin-top:4px;">'
                                f'{top_loser["ticker"]}</div>'
                                f'<div style="font-size:1.5rem; font-weight:800; color:#E5484D;">'
                                f'{top_loser["change_pct"]:.1f}%</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                        st.markdown("<div style='height: 0.75rem'></div>", unsafe_allow_html=True)
                        with st.expander("See more movers"):
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
                        st.caption("No mover data available right now.")
                else:
                    st.caption("No data yet -- this updates once daily via the scheduled scan. Check back tomorrow.")

            # --- Today's radar (events + opportunities + earnings-verrassingen, samengevoegd) ---
            with st.container(border=True):
                st.markdown("**Today's radar**")

                macro_events = get_todays_macro_events(max_items=3)
                with st.spinner("Checking today's radar..."):
                    earnings_today = get_todays_portfolio_earnings(tracked_items, max_items=3)
                    infos = get_tickers_info(holdings) if holdings else {}
                todays_events = macro_events + [
                    {"name": f"{e['naam']} ({e['ticker']}) reports earnings today"} for e in earnings_today
                ]
                if todays_events:
                    for event in todays_events[:3]:
                        time_part = f" -- {event['time']}" if "time" in event else ""
                        st.markdown(f"- 📅 {event['name']}{time_part}")

                # Aankomende earnings deze week -- niet alleen vandaag, ook een
                # heads-up ervoor, zodat je niet pas op de dag zelf verrast wordt.
                upcoming_earnings = get_upcoming_portfolio_earnings(tracked_items, days_ahead=5, max_items=3)
                for e in upcoming_earnings:
                    day_word = "tomorrow" if e["days_until"] == 1 else f"in {e['days_until']} days"
                    st.markdown(f"- 📆 **{e['naam']}** ({e['ticker']}) reports earnings {day_word} ({e['earnings_date']}).")

                # Concentratie-waarschuwing -- alleen tonen als je eigen doel-grens
                # daadwerkelijk overschreden wordt (geen ruis op normale dagen).
                if holdings:
                    risk_profile = database.get_risk_profile(user_email)
                    concentration_alert = get_concentration_alert(holdings, risk_profile["max_position_pct"])
                    if concentration_alert:
                        st.markdown(f"- {concentration_alert}")

                # Aankomende ex-dividend-data voor je HUIDIGE posities.
                upcoming_ex_div = get_upcoming_ex_dividend_dates(holdings, infos, days_ahead=5, max_items=3)
                for d in upcoming_ex_div:
                    day_word = "today" if d["days_until"] == 0 else ("tomorrow" if d["days_until"] == 1 else f"in {d['days_until']} days")
                    st.markdown(f"- 💰 **{d['naam']}** goes ex-dividend {day_word} ({d['ex_div_date']}).")

                # 52-weken-record -- een leuk, opvallend signaal als een van je
                # posities vandaag een nieuwe hoogte/laagte raakt.
                records_52wk = get_52_week_records(holdings, infos, max_items=3) if holdings else []
                for r in records_52wk:
                    emoji = "🚀" if r["type"] == "high" else "📉"
                    label = "new 52-week high" if r["type"] == "high" else "new 52-week low"
                    st.markdown(f"- {emoji} **{r['naam']}** ({r['ticker']}) just hit a {label}.")

                # Deep-dive verkoop-triggers (prijs of datum) die bereikt zijn --
                # ingesteld op een rustig moment, geen actie nodig behalve ernaar kijken.
                deep_dive_triggers = get_deep_dive_triggers_hit(user_email, max_items=3)
                for t in deep_dive_triggers:
                    st.markdown(f"- 🔔 **{t['naam']}** ({t['ticker']}) {t['detail']}.")

                weekly_scan_date = get_file_last_commit_date("supertrend_signals.csv")
                last_seen_weekly = database.get_last_seen_weekly_signals_date(user_email)
                weekly_is_new = weekly_scan_date is not None and weekly_scan_date != last_seen_weekly
                if weekly_is_new:
                    database.set_last_seen_weekly_signals_date(user_email, weekly_scan_date)

                opportunities = build_opportunities_today(holdings, watchlist_items, include_weekly=weekly_is_new)
                weekly_part = f", {opportunities['weekly_signals']} weekly" if weekly_is_new else ""
                st.write(
                    f"- 🔍 **{opportunities['total_signals']}** signal(s) found "
                    f"({opportunities['daily_signals']} daily{weekly_part}) -- "
                    f"**{opportunities['in_portfolio_count']}** relate to your portfolio, "
                    f"**{opportunities['in_watchlist_count']}** are on your watchlist, "
                    f"**{opportunities['new_opportunities_count']}** are new ideas."
                )

                def _is_recent_earnings(earnings_date_str, max_days=2):
                    try:
                        earnings_date = pd.to_datetime(earnings_date_str).date()
                        days_since = (datetime.now().date() - earnings_date).days
                        return 0 <= days_since <= max_days
                    except Exception:
                        return False

                tracked_tickers = {item["ticker"] for item in tracked_items}
                all_recent_surprises = get_earnings_surprises_from_signals(max_items=50)
                personal_surprises = [
                    s for s in all_recent_surprises
                    if s["ticker"] in tracked_tickers and _is_recent_earnings(s["earnings_date"])
                ]
                for s in personal_surprises[:3]:
                    emoji = "🟢" if s["earnings_beat"] else "🔴"
                    st.markdown(f"- {emoji} **{s['ticker']}**: {s['earnings_surprise_pct']:+.1f}% earnings surprise ({s['earnings_date']})")

                # Markt-brede verrassingen (NIET in je eigen portfolio/watchlist) --
                # strenger venster (1 dag i.p.v. 2), want minder persoonlijk relevant,
                # maar toch de moeite waard om even te vermelden.
                market_wide_surprises = [
                    s for s in all_recent_surprises
                    if s["ticker"] not in tracked_tickers and _is_recent_earnings(s["earnings_date"], max_days=1)
                ]
                for s in market_wide_surprises[:2]:
                    emoji = "🟢" if s["earnings_beat"] else "🔴"
                    st.markdown(
                        f"- {emoji} Also worth noting (not in your portfolio): "
                        f"**{s['ticker']}** {s['earnings_surprise_pct']:+.1f}% surprise ({s['earnings_date']})"
                    )

                # Sector/theme-drempel-meldingen -- een extreme 1-maands-beweging
                # kan een koop-/verkoopmoment zijn.
                with st.spinner("Checking for sector/theme extremes..."):
                    threshold_alerts = get_sector_theme_threshold_alerts()
                for alert in threshold_alerts[:3]:
                    move_emoji = "🔥" if alert["direction"] == "up" else "🥶"
                    extreme_marker = " (extreme move!)" if alert["level"] == "extreme" else ""
                    region_suffix = f" ({alert['region']})" if alert.get("region") else ""
                    kind_label = "sector" if alert["kind"] == "sector" else "theme"
                    st.markdown(
                        f"- {move_emoji} **{alert['name']}**{region_suffix} ({kind_label}) is "
                        f"{alert['pct']:+.1f}% this month{extreme_marker}"
                    )

                if holdings:
                    weekly_scan_recent_date = get_file_last_commit_date("supertrend_signals.csv")
                    weekly_scan_within_days = (
                        weekly_scan_recent_date is not None
                        and (datetime.now().date() - datetime.strptime(weekly_scan_recent_date, "%Y-%m-%d").date()).days <= 3
                    )
                    if weekly_scan_within_days:
                        from portfolio_watch import check_holding
                        # Let op: 'recent_gewijzigd' uit portfolio_watch.py zelf is een
                        # WEKELIJKSE check (2 weken) -- bedoeld voor de wekelijkse mail.
                        # Hier op de site tonen we een flip specifiek 2 KALENDERDAGEN,
                        # berekend op basis van de exacte flip-datum ('sinds').
                        FLIP_VISIBLE_DAYS_ON_TODAY = 2
                        today_date = datetime.now().date()
                        with st.spinner("Checking for trend flips..."):
                            flipped = []
                            for h in holdings:
                                result = check_holding(h["naam"], h["ticker"])
                                if result and result.get("sinds"):
                                    days_since_flip = (today_date - result["sinds"]).days
                                    if days_since_flip <= FLIP_VISIBLE_DAYS_ON_TODAY:
                                        flipped.append(result)
                        for f in flipped[:3]:
                            emoji = "🟢" if f["status"] == "BULLISH" else "🔴"
                            st.markdown(f"- {emoji} **{f['naam']}** just flipped to {f['status']}")

                st.markdown(
                    'See the full signal lists under <a href="?view=discover" class="inline-link" target="_self">Discover</a>.',
                    unsafe_allow_html=True,
                )

            # --- Top nieuws (portfolio + watchlist) -- nu inklapbaar, want samen
            # met Market news voelde dit als een lange wand van tekst ---
            with st.expander("📰 Top news for you", expanded=False):
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

            # --- Algemeen marktnieuws (simpele proxy: S&P 500 + AEX) -- ook inklapbaar ---
            with st.expander("🌐 Market news", expanded=False):
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

    current_discover_subview = st.query_params.get("subview", "discover")

    def _discover_subnav_class(subview_name):
        return "nav-link active" if current_discover_subview == subview_name else "nav-link"

    st.markdown(
        f"""
        <div class="nav-bar" style="margin-bottom: 1.25rem;">
            <a href="?view=discover&subview=discover" class="{_discover_subnav_class('discover')}" target="_self">Discover</a>
            <a href="?view=discover&subview=sectors_themes" class="{_discover_subnav_class('sectors_themes')}" target="_self">Sectors &amp; Themes</a>
            <a href="?view=discover&subview=earnings_surprises" class="{_discover_subnav_class('earnings_surprises')}" target="_self">Earnings Surprises</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if current_discover_subview == "sectors_themes":
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

            st.markdown("**Trend -- spot a reversal before it shows up in the table above**")
            st.caption("Each line shows how a sector's trailing 1-month return has evolved over the last 6 months. "
                       "A line crossing from below zero to above (or vice versa) is a rotation signal.")
            with st.spinner("Building trend chart..."):
                rotation_trend = build_sector_rotation_trend(region=region)
            if rotation_trend:
                all_trend_sectors = list(rotation_trend.keys())
                # Standaard: de top-5 op basis van het HUIDIGE (laatste) rendement --
                # voorkomt dat de grafiek meteen met alle 11 lijnen chaotisch oogt.
                default_sectors = sorted(
                    all_trend_sectors, key=lambda s: rotation_trend[s]["values"][-1], reverse=True
                )[:5]
                selected_sectors = st.multiselect(
                    "Sectors to compare", all_trend_sectors, default=default_sectors, key="sector_trend_selection",
                )
                if selected_sectors:
                    trend_fig = go.Figure()
                    trend_palette = [
                        "#1FAE96", "#E8A93C", "#E5484D", "#3ED9C4", "#8992A3",
                        "#5AC8B0", "#F5C518", "#C77DFF", "#4DA6FF", "#FF8A5C", "#B0E0D8",
                    ]
                    for i, sector in enumerate(selected_sectors):
                        series = rotation_trend[sector]
                        trend_fig.add_trace(go.Scatter(
                            x=series["dates"], y=series["values"], mode="lines", name=sector,
                            line=dict(color=trend_palette[i % len(trend_palette)], width=2),
                            hovertemplate="%{x}: %{y:+.1f}%<extra>" + sector + "</extra>",
                        ))
                    trend_fig.add_hline(y=0, line_dash="dash", line_color="#8992A3", line_width=1)
                    trend_fig.update_layout(
                        yaxis_title="Trailing 1-month return (%)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="Inter, sans-serif", color="#EAEDF1", size=11),
                        legend=dict(orientation="h", yanchor="top", y=-0.15, font=dict(size=10)),
                        margin=dict(t=10, b=10, l=10, r=10),
                        height=420,
                        xaxis=dict(gridcolor="rgba(137,146,163,0.15)"),
                        yaxis=dict(gridcolor="rgba(137,146,163,0.15)"),
                    )
                    st.plotly_chart(trend_fig, width="stretch")
                else:
                    st.caption("Select at least 1 sector above to see the trend chart.")
            else:
                st.caption("No trend data available right now.")

        # --- Themes (nieuw) -- populaire cross-sector trends, apart van de officiële
        # GICS-sectoren gehouden (anders zou een bedrijf dubbel meetellen) ---
        with st.expander("💡 Themes"):
            st.caption("How popular investing themes are doing right now (trailing 1-month return) -- "
                       "these cut across sectors, so they're tracked separately from Sector rotation.")
            st.caption("Live data -- recalculated fresh every time you open this.")
            with st.spinner("Checking theme performance..."):
                theme_rotation = build_theme_rotation(period="1mo")
            if theme_rotation:
                df_themes = pd.DataFrame(theme_rotation)[["theme", "return_pct"]]
                df_themes.columns = ["Theme", "1-Month Return"]
                st.dataframe(
                    df_themes.style.format({"1-Month Return": "{:+.1f}%"})
                                    .background_gradient(subset=["1-Month Return"], cmap="RdYlGn"),
                    width=320,
                    hide_index=True,
                )
            else:
                st.caption("No theme data available right now.")

            st.markdown("**Trend -- spot a reversal before it shows up in the table above**")
            st.caption("Each line shows how a theme's trailing 1-month return has evolved over the last 6 months. "
                       "A line crossing from below zero to above (or vice versa) is a rotation signal.")
            with st.spinner("Building trend chart..."):
                theme_trend = build_theme_rotation_trend()
            if theme_trend:
                all_trend_themes = list(theme_trend.keys())
                # Bij Themes zijn er maar 5 (i.p.v. 11 sectoren), dus standaard
                # gewoon allemaal tonen -- minder kans op een chaotische grafiek.
                selected_themes = st.multiselect(
                    "Themes to compare", all_trend_themes, default=all_trend_themes, key="theme_trend_selection",
                )
                if selected_themes:
                    theme_fig = go.Figure()
                    theme_palette = ["#1FAE96", "#E8A93C", "#E5484D", "#4DA6FF", "#C77DFF"]
                    for i, theme in enumerate(selected_themes):
                        series = theme_trend[theme]
                        theme_fig.add_trace(go.Scatter(
                            x=series["dates"], y=series["values"], mode="lines", name=theme,
                            line=dict(color=theme_palette[i % len(theme_palette)], width=2),
                            hovertemplate="%{x}: %{y:+.1f}%<extra>" + theme + "</extra>",
                        ))
                    theme_fig.add_hline(y=0, line_dash="dash", line_color="#8992A3", line_width=1)
                    theme_fig.update_layout(
                        yaxis_title="Trailing 1-month return (%)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="Inter, sans-serif", color="#EAEDF1", size=11),
                        legend=dict(orientation="h", yanchor="top", y=-0.15, font=dict(size=10)),
                        margin=dict(t=10, b=10, l=10, r=10),
                        height=420,
                        xaxis=dict(gridcolor="rgba(137,146,163,0.15)"),
                        yaxis=dict(gridcolor="rgba(137,146,163,0.15)"),
                    )
                    st.plotly_chart(theme_fig, width="stretch")
                else:
                    st.caption("Select at least 1 theme above to see the trend chart.")
            else:
                st.caption("No trend data available right now.")

    elif current_discover_subview == "earnings_surprises":
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

    else:
        # --- Niet-ingelogde dagelijkse e-mail-opt-in -- laagdrempelig, geen
        #     account nodig. Bewust NA de 3 signalen (ze hebben net gezien wat
        #     de dagelijkse signalen opleveren), en de tekst legt zelf uit wat
        #     'dagelijks' precies inhoudt (i.p.v. te vertrouwen op dat de
        #     bezoeker zelf het daily/weekly-onderscheid al doorheeft).
        import database as _database_for_optin

        st.markdown(
            """
            <div style="background: linear-gradient(135deg, rgba(31,174,150,0.16), rgba(31,174,150,0.02));
                        border: 1px solid rgba(31,174,150,0.4); border-radius: 12px;
                        padding: 1.25rem 1.5rem; margin: 1.5rem 0;">
                <div style="color:#1FAE96; font-weight:700; font-size:0.75rem; letter-spacing:1.5px; text-transform:uppercase;">
                    📬 Free daily email
                </div>
                <div style="color:#EAEDF1; font-size:1.05rem; font-weight:600; margin-top:6px; line-height:1.5;">
                    In your inbox before your morning coffee ☕ -- today's new bullish signals, every weekday.
                </div>
                <div style="color:#8992A3; font-size:0.9rem; margin-top:6px;">
                    Just your email -- no account needed.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        optin_col1, optin_col2, optin_col3 = st.columns([2, 1, 1])
        with optin_col1:
            optin_email = st.text_input("Email address", placeholder="you@example.com", key="discover_optin_email", label_visibility="collapsed")
        with optin_col2:
            optin_region = st.selectbox(
                "Region", ["EU", "US_East", "US_West"],
                format_func=lambda x: x.replace("_", " "),
                key="discover_optin_region", label_visibility="collapsed",
            )
        with optin_col3:
            optin_submitted = st.button("Sign up", key="discover_optin_submit", type="primary")

        if optin_submitted:
            if not optin_email or "@" not in optin_email:
                st.error("Please enter a valid email address.")
            else:
                confirmation_token, unsubscribe_token = _database_for_optin.add_email_subscriber(optin_email, optin_region)
                send_subscription_confirmation_email(optin_email, confirmation_token, unsubscribe_token)
                st.success("Almost there! Check your inbox to confirm your subscription.")


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

        def _email_pref_link(label: str):
            """Simpele verwijzing naar Settings om deze e-mail-voorkeur te beheren (i.p.v. een losse toggle hier)."""
            st.markdown(
                f'<div style="color:#8992A3; font-size:0.85rem; margin-top:4px;">📧 {label} -- manage in '
                f'<a href="?view=settings" class="inline-link" target="_self">Settings</a>.</div>',
                unsafe_allow_html=True,
            )

        def _next_weekly_scan_time() -> str:
            """Berekent het volgende geplande wekelijkse-scan-moment (zaterdag 07:00 UTC)."""
            now = datetime.now(timezone.utc)
            days_ahead = (5 - now.weekday()) % 7  # maandag=0 ... zaterdag=5
            if days_ahead == 0 and now.hour >= 7:
                days_ahead = 7  # het is al zaterdag na 07:00 UTC -> volgende week
            next_date = (now + timedelta(days=days_ahead)).replace(hour=7, minute=0, second=0, microsecond=0)
            return next_date.strftime("%Y-%m-%d %H:%M UTC")

        if st.user.is_logged_in:
            import database
            _current_prefs = database.get_user_preferences(st.user.email)
            _is_premium_discover = database.is_premium_user(st.user.email)
        else:
            _current_prefs = {}
            # Discover vereist bewust geen login -- maar tijdens de 'iedereen
            # premium'-testfase moet dat OOK voor niet-ingelogde bezoekers
            # gelden, niet alleen voor wie toevallig al is ingelogd.
            try:
                _is_premium_discover = st.secrets.get("app", {}).get("premium_free_for_all", False)
            except Exception:
                _is_premium_discover = False
        _signal_display_limit = None if _is_premium_discover else 3  # None = pandas .head(None) geeft alles terug

        # --- Momentocrats (bestaande, ongewijzigde signaal-logica) ---
        with st.expander("📡 Momentocrats", expanded=False):
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
                    column_config={
                        "Score": st.column_config.NumberColumn(
                            "Score",
                            help=(
                                "Out of 10, built from 6 weighted parts: freshness of the flip (max 1.5), "
                                "ROIC level + trend (max 1.5), relative strength vs. the index (max 2.5), "
                                "volume confirmation (max 1.0), recent earnings surprise (max 1.5), and how "
                                "far below the analyst price target it trades (max 2.0). Missing data counts "
                                "as neutral (half the max) for that part."
                            ),
                        ),
                    },
                    height=500,
                )
                st.caption(f"{len(filtered)} of {total_matching} matching signals shown.")
                if not _is_premium_discover and total_matching > _signal_display_limit:
                    st.info(f"🔒 Showing the top {_signal_display_limit} of {total_matching} matching signals. "
                            f"Upgrade to Premium to see all {total_matching}.")

            st.divider()
            _email_pref_link("Want this weekly by email?")

        # --- Snowball Signal (nieuw, wekelijks-only: kwaliteit + goede prijs) ---
        with st.expander("🐦 Snowballers"):
            st.caption("Quality companies trading below fair value, with low volatility. For the "
                       "long-term investor -- no fresh trend flip required.")
            st.caption(f"Last updated: {file_last_modified('snowball_signals.csv')}")
            st.caption(f"Next scheduled update: {_next_weekly_scan_time()}")
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
                                f"Upgrade to Premium to see all {total_snowball}.")
                else:
                    st.caption("No stocks currently meet the Snowballers criteria.")
            else:
                st.caption("No data yet -- this updates once a week via the scheduled scan.")

            st.divider()
            _email_pref_link("Want this weekly by email?")

        # --- Rocket List (nieuw, wekelijks-only: versnellende groei + momentum) ---
        with st.expander("🚀 Rocket List"):
            st.caption("Accelerating growth stocks with strong momentum. For investors comfortable "
                       "with more risk in exchange for growth potential.")
            st.caption(f"Last updated: {file_last_modified('rocket_list_signals.csv')}")
            st.caption(f"Next scheduled update: {_next_weekly_scan_time()}")
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
                                f"Upgrade to Premium to see all {total_rocket}.")
                else:
                    st.caption("No stocks currently meet the Rocket List criteria.")
            else:
                st.caption("No data yet -- this updates once a week via the scheduled scan.")

            st.divider()
            _email_pref_link("Want this weekly by email?")

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

    holdings = filter_active_holdings(database.get_user_holdings(user_email))
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
            cash_value = database.get_cash_value(user_email)

            if total_value > 0 and stored_currency == display_currency:
                st.markdown(f"#### Total: {currency_symbol}{total_value:,.0f} "
                            f"<span style='font-size:0.9rem; color:#8992A3; font-weight:400;'>"
                            f"&nbsp;|&nbsp; Cash: €{cash_value:,.0f}</span>", unsafe_allow_html=True)
            elif total_value > 0:
                st.warning(f"Values currently shown are in {stored_currency}, not {display_currency}. Click 'Update portfolio value' to convert.")
                st.markdown(f"#### Total: {'€' if stored_currency == 'EUR' else '$'}{total_value:,.0f} ({stored_currency}) "
                            f"<span style='font-size:0.9rem; color:#8992A3; font-weight:400;'>"
                            f"&nbsp;|&nbsp; Cash: €{cash_value:,.0f}</span>", unsafe_allow_html=True)
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

            def _format_pct(holding):
                if total_value <= 0:
                    return "-"
                value = holding.get("position_value") or 0
                return f"{value / total_value * 100:.0f}%"

            def _format_value(holding):
                value = holding.get("position_value")
                sym = "€" if holding.get("value_currency") == "EUR" else "$"
                return f"{sym}{value:,.0f}" if value else "-"

            def _format_price(holding):
                """Huidige prijs per aandeel/eenheid -- afgeleid uit de al-opgeslagen
                positiewaarde (waarde / aantal), dus geen extra live-aanroep nodig en
                consistent met het laatste 'Update portfolio value'-moment."""
                value = holding.get("position_value")
                shares = holding.get("shares")
                if not value or not shares:
                    return "-"
                sym = "€" if holding.get("value_currency") == "EUR" else "$"
                return f"{sym}{value / shares:,.2f}"

            rows_html = "".join(
                f'<tr><td>{h["naam"]}</td><td><code>{h["ticker"]}</code></td>'
                f'<td>{h.get("shares") or "-"}</td><td>{_format_price(h)}</td>'
                f'<td>{_format_value(h)}</td><td>{_format_pct(h)}</td></tr>'
                for h in holdings
            )
            st.markdown(
                f"""
                <table class="positions-table">
                    <thead><tr><th>Name</th><th>Ticker</th><th>Shares</th><th>Price</th><th>Value</th><th>% of portfolio</th></tr></thead>
                    <tbody>{rows_html}</tbody>
                </table>
                """,
                unsafe_allow_html=True,
            )

    # ============================================================
    # 3. MANAGE
    # ============================================================
    with st.container(border=True):
        st.markdown("**Manage**")

        # --- Import from a broker -- bulk-importeren i.p.v. 1-voor-1 loggen ---
        with st.expander("Import from a broker", expanded=False):
            st.caption("Currently supports DEGIRO. Upload your broker's 'Transactions' export "
                       "(CSV) to import your full buy/sell history in one go, instead of "
                       "logging each one by hand.")
            st.caption("Using a different broker?")
            st.markdown(
                '<a href="?view=support" class="button-link" target="_self">Go to Support &rarr;</a>',
                unsafe_allow_html=True,
            )
            degiro_file = st.file_uploader("Transactions CSV", type=["csv"], key="degiro_upload")

            already_imported = st.session_state.get("degiro_imported_filenames", set())

            if degiro_file is not None and degiro_file.name in already_imported:
                st.success(f"✅ '{degiro_file.name}' was already imported.")
                if st.button("Process this file again anyway"):
                    already_imported.discard(degiro_file.name)
                    st.session_state["degiro_imported_filenames"] = already_imported
                    st.session_state.pop("degiro_parsed_filename", None)
                    st.rerun()
            elif degiro_file is not None:
                if st.session_state.get("degiro_parsed_filename") != degiro_file.name:
                    # Nieuw bestand -- opnieuw parsen en de matches resetten
                    with st.spinner("Reading your file..."):
                        parse_result = parse_degiro_transactions_csv(degiro_file.getvalue())
                    st.session_state["degiro_parsed_filename"] = degiro_file.name
                    st.session_state["degiro_grouped"] = parse_result["grouped"]
                    st.session_state["degiro_skipped"] = parse_result["skipped_rows"]
                    ticker_matches = {}
                    ticker_candidates = {}
                    # Herken ISIN's die je AL eerder hebt opgelost (bv. bij een vorige
                    # import) -- geen nieuwe zoekopdracht nodig, geen keuzelijst opnieuw.
                    existing_isin_to_ticker = {
                        h["isin"]: h["ticker"] for h in database.get_user_holdings(user_email) if h.get("isin")
                    }
                    with st.spinner(f"Looking up tickers for {len(parse_result['grouped'])} securities..."):
                        for key, group in parse_result["grouped"].items():
                            remembered_ticker = existing_isin_to_ticker.get(group.get("isin"))
                            if remembered_ticker:
                                ticker_matches[key] = remembered_ticker
                                ticker_candidates[key] = [{
                                    "symbol": remembered_ticker, "name": group["product"], "exchange": "remembered",
                                }]
                            else:
                                candidates = get_ticker_candidates(group["product"], group.get("isin"))
                                ticker_candidates[key] = candidates
                                ticker_matches[key] = candidates[0]["symbol"] if candidates else ""
                    st.session_state["degiro_ticker_matches"] = ticker_matches
                    st.session_state["degiro_ticker_candidates"] = ticker_candidates

                degiro_grouped = st.session_state["degiro_grouped"]
                degiro_skipped = st.session_state["degiro_skipped"]

                total_tx = sum(len(g["transactions"]) for g in degiro_grouped.values())
                st.success(f"Found {len(degiro_grouped)} securities, {total_tx} transactions.")
                if degiro_skipped:
                    reasons_preview = "; ".join(reason for _, reason in degiro_skipped[:5])
                    more = "..." if len(degiro_skipped) > 5 else ""
                    st.caption(f"{len(degiro_skipped)} row(s) couldn't be read and were skipped: "
                               f"{reasons_preview}{more}")

                unmatched_keys = [
                    key for key, group in degiro_grouped.items()
                    if not st.session_state["degiro_ticker_matches"].get(key, "").strip()
                ]
                if unmatched_keys:
                    unmatched_lines = "\n".join(
                        f"- **{degiro_grouped[key]['product']}**"
                        + (f" (ISIN: {degiro_grouped[key]['isin']})" if degiro_grouped[key]["isin"] else "")
                        for key in unmatched_keys
                    )
                    st.warning(f"⚠️ **{len(unmatched_keys)} security/securities need your attention** "
                               f"-- no ticker could be auto-matched. Fill these in manually below, "
                               f"or they'll be skipped:\n\n{unmatched_lines}")

                st.markdown("**Review the ticker for each security** (auto-suggested -- please "
                             "double-check and correct if wrong before importing). "
                             "Unmatched ones are shown first:")
                sorted_items = sorted(
                    degiro_grouped.items(),
                    key=lambda kv: st.session_state["degiro_ticker_matches"].get(kv[0], "").strip() != "",
                )
                for key, group in sorted_items:
                    dcol1, dcol2 = st.columns([3, 2])
                    with dcol1:
                        prefix = "⚠️ " if key in unmatched_keys else ""
                        st.caption(f"{prefix}{group['product']} ({len(group['transactions'])} transactions)")
                    with dcol2:
                        candidates = st.session_state["degiro_ticker_candidates"].get(key, [])
                        if len(candidates) >= 2:
                            # Meerdere beursnoteringen gevonden (bv. hetzelfde ETF op meerdere
                            # beurzen) -- laat kiezen met naam + beurs erbij, i.p.v. blind te gokken.
                            options = [f"{c['symbol']} -- {c['name']} ({c['exchange']})" for c in candidates]
                            options.append("Other (type manually)")
                            current_symbol = st.session_state["degiro_ticker_matches"].get(key, "")
                            default_index = next(
                                (i for i, c in enumerate(candidates) if c["symbol"] == current_symbol),
                                len(options) - 1,
                            )
                            chosen_label = st.selectbox(
                                "Ticker", options, index=default_index,
                                key=f"degiro_choice_{key}", label_visibility="collapsed",
                            )
                            if chosen_label == "Other (type manually)":
                                manual_default = current_symbol if current_symbol not in [c["symbol"] for c in candidates] else ""
                                manual_ticker = st.text_input(
                                    "Manual ticker", value=manual_default, key=f"degiro_manual_{key}",
                                    label_visibility="collapsed", placeholder="type ticker",
                                )
                                st.session_state["degiro_ticker_matches"][key] = manual_ticker
                            else:
                                chosen_symbol = candidates[options.index(chosen_label)]["symbol"]
                                st.session_state["degiro_ticker_matches"][key] = chosen_symbol
                        else:
                            current_guess = st.session_state["degiro_ticker_matches"].get(key, "")
                            new_ticker = st.text_input(
                                "Ticker", value=current_guess, key=f"degiro_ticker_{key}",
                                label_visibility="collapsed", placeholder="leave empty to skip",
                            )
                            st.session_state["degiro_ticker_matches"][key] = new_ticker

                ready_count = sum(1 for t in st.session_state["degiro_ticker_matches"].values() if t.strip())
                st.caption(f"{ready_count} of {len(degiro_grouped)} securities have a ticker -- "
                           f"the rest will be skipped.")

                if st.button("Import all matched transactions", type="primary"):
                    imported_positions = 0
                    imported_transactions = 0
                    imported_duplicates_skipped = 0
                    all_holdings_for_import = database.get_user_holdings(user_email)
                    to_import = [
                        (key, group) for key, group in degiro_grouped.items()
                        if st.session_state["degiro_ticker_matches"].get(key, "").strip()
                    ]

                    progress_bar = st.progress(0.0)
                    status_text = st.empty()

                    for i, (key, group) in enumerate(to_import):
                        ticker = st.session_state["degiro_ticker_matches"][key].strip()
                        status_text.markdown(f"📥 **Importing {group['product']}...** ({i + 1} of {len(to_import)})")

                        # Ook GESLOTEN posities meenemen (niet alleen de actieve lijst) --
                        # anders zou opnieuw kopen van iets dat je ooit volledig verkocht
                        # had, per ongeluk een dubbele, nieuwe positie aanmaken i.p.v. de
                        # bestaande (met z'n geschiedenis) te hergebruiken.
                        existing = next((h for h in all_holdings_for_import if h["ticker"] == ticker), None)
                        if existing:
                            holding_id = existing["id"]
                            existing_manual_shares = existing.get("shares") or 0.0
                            existing_tx = database.get_transactions_for_holding(user_email, holding_id)
                            if not existing_tx and existing_manual_shares > 0:
                                # Zelfde inhaal-logica als bij 'Log a transaction': bestaande
                                # handmatige shares vastleggen tegen de huidige prijs, vandaag.
                                try:
                                    backfill_price = float(yf.Ticker(ticker).history(period="1d")["Close"].iloc[-1])
                                except Exception:
                                    backfill_price = group["transactions"][0]["price"]
                                database.add_transaction(
                                    user_email, holding_id, "buy",
                                    shares=existing_manual_shares, price=backfill_price, fee=0.0,
                                    transaction_date=datetime.now().date().isoformat(),
                                )
                        else:
                            holding_id = database.add_holding(
                                user_email, group["product"], ticker, shares=None, isin=group.get("isin"),
                            )
                            imported_positions += 1

                        already_logged = database.get_transactions_for_holding(user_email, holding_id)

                        def _is_duplicate(new_tx, existing_list):
                            return any(
                                existing["transaction_type"] == new_tx["transaction_type"]
                                and existing["transaction_date"] == new_tx["transaction_date"]
                                and abs(existing["shares"] - new_tx["shares"]) < 0.0001
                                and abs(existing["price"] - new_tx["price"]) < 0.0001
                                for existing in existing_list
                            )

                        skipped_duplicates = 0
                        for t in group["transactions"]:
                            if _is_duplicate(t, already_logged):
                                skipped_duplicates += 1
                                continue
                            database.add_transaction(
                                user_email, holding_id, t["transaction_type"],
                                shares=t["shares"], price=t["price"], fee=t["fee"],
                                transaction_date=t["transaction_date"],
                            )
                            imported_transactions += 1

                        if skipped_duplicates:
                            imported_duplicates_skipped += skipped_duplicates

                        sync_holding_shares_from_transactions(holding_id, user_email)
                        progress_bar.progress((i + 1) / len(to_import))

                    status_text.empty()
                    progress_bar.empty()

                    dup_txt = f" ({imported_duplicates_skipped} already-imported duplicates skipped)" if imported_duplicates_skipped else ""
                    st.success(f"Imported {imported_transactions} transactions across "
                               f"{imported_positions} new position(s)!{dup_txt}")
                    already_imported.add(degiro_file.name)
                    st.session_state["degiro_imported_filenames"] = already_imported
                    for state_key in ["degiro_parsed_filename", "degiro_grouped", "degiro_skipped",
                                       "degiro_ticker_matches", "degiro_ticker_candidates"]:
                        st.session_state.pop(state_key, None)
                    st.rerun()

        # --- Log a transaction (werkt ook zonder bestaande posities -- een
        # nieuwe positie kan direct via een eerste 'Log a buy' worden
        # aangemaakt) ---
        with st.expander("Log a transaction", expanded=False):
            st.caption("Log your actual buys and sells to see your real return under Analyze. "
                       "Optional -- positions without transactions logged just won't show a return.")

            position_mode_options = (
                ["Existing position", "New position"] if holdings else ["New position"]
            )
            tx_position_mode = st.radio(
                "Position", position_mode_options, horizontal=True,
                key="tx_position_mode", label_visibility="collapsed",
            )

            tx_holding = None
            new_position_symbol = None
            new_position_name = None

            if tx_position_mode == "Existing position":
                tx_holding_options = {f"{h['naam']} ({h['ticker']})": h for h in holdings}
                tx_label = st.selectbox(
                    "Position", list(tx_holding_options.keys()), key="tx_select", label_visibility="collapsed",
                )
                tx_holding = tx_holding_options[tx_label]
                tx_type = st.radio(
                    "Type", ["Buy", "Sell"], horizontal=True, key="tx_type_radio",
                )
                is_buy = tx_type == "Buy"
            else:
                # Nieuwe positie: altijd een koop (je kan niet iets verkopen dat je nog niet hebt)
                is_buy = True
                tx_search_query = st.text_input(
                    "Search for the company/asset you bought", key="tx_search_query",
                )
                if tx_search_query:
                    try:
                        tx_search_results = yf.Search(tx_search_query, max_results=8).quotes
                    except Exception as exc:
                        tx_search_results = []
                        st.caption(f"Search failed: {exc}")
                    if tx_search_results:
                        tx_options = {}
                        for r in tx_search_results:
                            name = r.get("shortname") or r.get("longname") or r.get("symbol")
                            label = f"{name} ({r.get('symbol')}) -- {r.get('exchange', '')}"
                            tx_options[label] = r
                        tx_chosen_label = st.selectbox("Choose the right match", list(tx_options.keys()), key="tx_new_match")
                        tx_chosen = tx_options[tx_chosen_label]
                        new_position_symbol = tx_chosen.get("symbol")
                        new_position_name = tx_chosen.get("shortname") or tx_chosen.get("longname") or new_position_symbol
                    else:
                        st.caption("No results found for this search -- try a different name.")

            tcol1, tcol2, tcol3, tcol4 = st.columns(4)
            with tcol1:
                tx_shares = st.number_input("Shares", min_value=0.0, step=1.0, key="tx_shares_input")
            with tcol2:
                tx_price = st.number_input("Price per share", min_value=0.0, step=0.01, key="tx_price_input")
            with tcol3:
                tx_fee = st.number_input("Fee paid", min_value=0.0, step=0.01, value=0.0, key="tx_fee_input")
            with tcol4:
                tx_date = st.date_input("Date", key="tx_date_input")

            can_save = (tx_holding is not None) or (new_position_symbol is not None)

            if can_save and st.button("Save transaction", type="primary"):
                if tx_shares <= 0 or tx_price <= 0:
                    st.error("Shares and price must both be greater than 0.")
                else:
                    if tx_position_mode == "New position":
                        if len(holdings) >= 10 and not is_premium:
                            st.error(
                                "You've reached the free plan limit of 10 tracked positions. "
                                "Upgrade to Premium for unlimited tracking."
                            )
                        else:
                            new_id = database.add_holding(user_email, new_position_name, new_position_symbol, shares=None)
                            database.add_transaction(
                                user_email, new_id, "buy",
                                shares=tx_shares, price=tx_price, fee=tx_fee,
                                transaction_date=tx_date.isoformat(),
                            )
                            sync_holding_shares_from_transactions(new_id, user_email)
                            st.success(f"{new_position_name} ({new_position_symbol}) added, with your buy logged!")
                            st.rerun()
                    else:
                        existing_tx = database.get_transactions_for_holding(user_email, tx_holding["id"])
                        existing_manual_shares = tx_holding.get("shares") or 0.0
                        if not existing_tx and existing_manual_shares > 0:
                            # Eerste transactie voor deze positie, en er stond al een handmatig
                            # aantal shares -- die vangen we automatisch op als een 'gekocht
                            # tegen de huidige prijs, vandaag'-transactie (simpele standaard,
                            # geen keuzemenu nodig; later aanpasbaar als je de echte
                            # historische aankoopprijs nog weet).
                            try:
                                backfill_price = float(yf.Ticker(tx_holding["ticker"]).history(period="1d")["Close"].iloc[-1])
                            except Exception:
                                backfill_price = tx_price  # fallback als de live prijs niet op te halen is
                            database.add_transaction(
                                user_email, tx_holding["id"], "buy",
                                shares=existing_manual_shares, price=backfill_price, fee=0.0,
                                transaction_date=datetime.now().date().isoformat(),
                            )
                            existing_tx.append({"transaction_type": "buy", "shares": existing_manual_shares})
                            st.info(f"Your existing {existing_manual_shares:.2f} shares were logged as "
                                    f"bought at today's price (€{backfill_price:.2f}) -- edit this later if "
                                    f"you remember the actual original purchase price.")

                        database.add_transaction(
                            user_email, tx_holding["id"], "buy" if is_buy else "sell",
                            shares=tx_shares, price=tx_price, fee=tx_fee,
                            transaction_date=tx_date.isoformat(),
                        )
                        shares_after = sync_holding_shares_from_transactions(tx_holding["id"], user_email)

                        # Bij een verkoop naar ~0 shares: de positie NIET verwijderen (dat zou
                        # via de cascade ook de transactiegeschiedenis wissen, en dus je
                        # gerealiseerde winst/verlies uit Performance laten verdwijnen) --
                        # 'ie blijft gewoon bestaan met 0 shares, verborgen uit My Portfolio
                        # via filter_active_holdings(), maar telt nog mee bij Performance.
                        if not is_buy and shares_after <= 0.001:
                            st.success(f"Sell logged -- {tx_holding['naam']} is now fully closed. "
                                       f"Its history still counts toward your Performance stats.")
                            st.rerun()

                        st.success("Transaction saved!")
                        st.rerun()

            if tx_holding is not None:
                tx_history = database.get_transactions_for_holding(user_email, tx_holding["id"])
                if tx_history:
                    if st.checkbox(f"Show transaction history ({len(tx_history)})", key=f"show_tx_history_{tx_holding['id']}"):
                        for t in tx_history:
                            hcol1, hcol2 = st.columns([5, 1])
                            with hcol1:
                                emoji = "🟢" if t["transaction_type"] == "buy" else "🔴"
                                st.caption(f"{emoji} {t['transaction_date']}: {t['shares']:.2f} shares @ "
                                           f"€{t['price']:.2f} (fee: €{t['fee']:.2f})")
                            with hcol2:
                                if st.button("🗑️", key=f"delete_tx_{t['id']}", help="Delete this transaction"):
                                    database.delete_transaction(t["id"], user_email)
                                    remaining = [x for x in tx_history if x["id"] != t["id"]]
                                    if not remaining:
                                        # Geen transacties meer over voor deze positie -- voorkomt een
                                        # 'verweesde' positie zonder shares en zonder geschiedenis.
                                        database.delete_holding(tx_holding["id"], user_email)
                                        st.success("Transaction deleted -- this position had no other "
                                                   "transactions left, so it was removed too.")
                                    else:
                                        sync_holding_shares_from_transactions(tx_holding["id"], user_email)
                                        st.success("Transaction deleted.")
                                    st.rerun()

    # ============================================================
    # WATCHLIST -- volgen zonder eigendom, voor gepersonaliseerde info op Today
    # ============================================================
    with st.expander("Watchlist", expanded=False):
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

        st.markdown("**Add to watchlist**")
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
            st.markdown("**Remove from watchlist**")
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

    st.caption("Manage email preferences and cash amount under Settings. "
               "You'll also automatically receive a weekly email with this update, "
               "at the address you're logged in with.")


elif current_view == "analyze":
    st.markdown("### Analyze")

    if not st.user.is_logged_in:
        st.markdown(
            '<div class="privacy-seal">&#128274; PRIVATE &middot; visible only to you</div>',
            unsafe_allow_html=True,
        )
        st.info("Log in (top right) to track your own positions and analyze your portfolio. No one else can see what you add.")
        st.stop()

    current_subview = st.query_params.get("subview", "performance")

    def _subnav_class(subview_name):
        return "nav-link active" if current_subview == subview_name else "nav-link"

    st.markdown(
        f"""
        <div class="nav-bar" style="margin-bottom: 1.25rem;">
            <a href="?view=analyze&subview=performance" class="{_subnav_class('performance')}" target="_self">Performance</a>
            <a href="?view=analyze&subview=portfolio" class="{_subnav_class('portfolio')}" target="_self">Portfolio Overview</a>
            <a href="?view=analyze&subview=dividend" class="{_subnav_class('dividend')}" target="_self">Dividend</a>
            <a href="?view=analyze&subview=deepdives" class="{_subnav_class('deepdives')}" target="_self">Deep-dives</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if current_subview == "deepdives":
        import database

        user_email = st.user.email

        st.markdown(
            """
            <div style="background: linear-gradient(135deg, rgba(31,174,150,0.14), rgba(31,174,150,0.02));
                        border: 1px solid rgba(31,174,150,0.35); border-radius: 10px;
                        padding: 1rem 1.25rem; margin: 0.5rem 0 1rem 0;">
                <div style="color:#1FAE96; font-weight:700; font-size:0.75rem; letter-spacing:1.5px; text-transform:uppercase;">
                    📓 Deep-dives
                </div>
                <div style="color:#8992A3; font-size:0.9rem; margin-top:6px; line-height:1.5;">
                    Log your own research per stock -- every time you update it, the previous
                    version stays saved, so you can later see exactly how your view has changed.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("➕ Add a new deep-dive (or update)", expanded=False):
            dd_ticker = st.text_input("Ticker", placeholder="e.g. TSLA", key="dd_ticker_input").strip().upper()

            # Automatisch de bedrijfsnaam invullen zodra de ticker verandert
            # (via session_state, VÓÓR het naam-veld zelf wordt aangemaakt) --
            # scheelt typewerk, en je kan het altijd nog zelf overschrijven.
            if dd_ticker and dd_ticker != st.session_state.get("dd_last_looked_up_ticker"):
                st.session_state["dd_last_looked_up_ticker"] = dd_ticker
                try:
                    auto_info = get_cached_ticker_info(dd_ticker)
                    auto_name = auto_info.get("longName") or auto_info.get("shortName")
                    if auto_name:
                        st.session_state["dd_naam_input"] = auto_name
                except Exception:
                    pass

            dd_naam = st.text_input("Name", placeholder="e.g. Tesla Inc.", key="dd_naam_input")

            # Het valutasymbool volgt het aandeel zelf (bv. $voor een
            # Amerikaans aandeel, €voor een Europees) -- belangrijk omdat
            # het grootste deel van de aankopen in USD is, maar niet alles.
            dd_currency_symbol = _currency_symbol_for_ticker(dd_ticker) if dd_ticker else "€"

            st.markdown("**Business overview** -- what does the company do, in your own words")
            dd_business = st.text_area("Business overview", label_visibility="collapsed", key="dd_business", height=80)

            st.markdown("**Investment thesis** -- why this could be a good investment")
            dd_thesis = st.text_area("Investment thesis", label_visibility="collapsed", key="dd_thesis", height=80)
            dd_thesis_score = st.columns([1, 1])[0].slider("How compelling is the thesis?", 1, 10, 5, key="dd_thesis_score")

            st.markdown("**Management/CEO** -- assess the management and the CEO")
            dd_management = st.text_area("Management/CEO", label_visibility="collapsed", key="dd_management", height=80)
            dd_management_score = st.columns([1, 1])[0].slider("How much confidence in management?", 1, 10, 5, key="dd_management_score")

            st.markdown("**Bear case / risks** -- what could go wrong")
            dd_bear = st.text_area("Bear case", label_visibility="collapsed", key="dd_bear", height=80)
            dd_bear_score = st.columns([1, 1])[0].slider(
                "How manageable are the risks?", 1, 10, 5, key="dd_bear_score",
                help="Higher = the risks are limited/well understood, not 'the risks are severe' -- keeps the scale consistent with the other sliders (higher is always more favorable).",
            )

            st.markdown("**Valuation** -- do you think the current price is reasonable, and why")
            dd_valuation = st.text_area("Valuation", label_visibility="collapsed", key="dd_valuation", height=80)
            dd_valuation_score = st.columns([1, 1])[0].slider("How attractive is the valuation?", 1, 10, 5, key="dd_valuation_score")
            dd_interested_price = st.number_input(
                f"Interested from price ({dd_currency_symbol.strip()}, optional)", min_value=0.0, step=0.01, key="dd_interested_price",
                help="If filled in, and your conclusion is 'Buy', we'll later check this automatically on Today.",
            )

            st.markdown("**Technical analysis** -- what does the chart say (trend, support/resistance, momentum) "
                        "-- separate from Valuation, which is about the price vs. the FUNDAMENTALS")
            dd_technical_analysis = st.text_area("Technical analysis", label_visibility="collapsed", key="dd_technical_analysis", height=80)
            dd_technical_analysis_score = st.columns([1, 1])[0].slider("How favorable is the technical setup?", 1, 10, 5, key="dd_technical_analysis_score")

            st.markdown("**Catalysts** -- what upcoming events could move the price")
            dd_catalysts = st.text_area("Catalysts", label_visibility="collapsed", key="dd_catalysts", height=80)
            dd_catalysts_score = st.columns([1, 1])[0].slider("How strong are the catalysts?", 1, 10, 5, key="dd_catalysts_score")

            st.markdown("**Position sizing plan** -- how big a position, and why")
            dd_sizing = st.text_area("Position sizing plan", label_visibility="collapsed", key="dd_sizing", height=80)

            st.markdown("**Sell criteria** -- under what conditions do you exit "
                        "(this is also where a specific triggering EVENT belongs, e.g. "
                        "'if they miss 2 consecutive quarters' -- we can't check that "
                        "automatically, so it stays a reminder here on this page)")
            dd_sell_criteria = st.text_area("Sell criteria", label_visibility="collapsed", key="dd_sell_criteria", height=80)

            st.markdown("**Sell trigger (optional)** -- get a heads-up on Today when this is reached")
            dd_sell_trigger_cols = st.columns(2)
            with dd_sell_trigger_cols[0]:
                dd_sell_trigger_price = st.number_input(
                    f"Sell at price ({dd_currency_symbol.strip()})", min_value=0.0, step=0.01, key="dd_sell_trigger_price",
                    help="Works both ways: a target above today's price is treated as a profit "
                         "target, below it as a stop-loss.",
                )
            with dd_sell_trigger_cols[1]:
                dd_sell_trigger_date = st.date_input(
                    "Sell by date", value=None, key="dd_sell_trigger_date",
                    help="A hard deadline to reconsider this position, regardless of price.",
                )

            dd_conclusion = st.selectbox("Conclusion", ["Watch", "Buy", "Pass"], key="dd_conclusion")

            if st.button("Save this version", type="primary", key="dd_save_btn"):
                if not dd_ticker or not dd_naam:
                    st.error("Please fill in at least a ticker and name.")
                else:
                    with st.spinner("Fetching market data..."):
                        market_snapshot = get_deep_dive_market_snapshot(dd_ticker)
                    database.add_deep_dive(
                        user_email, dd_ticker, dd_naam,
                        business_overview=dd_business or None,
                        investment_thesis=dd_thesis or None,
                        management_assessment=dd_management or None,
                        bear_case=dd_bear or None,
                        valuation_view=dd_valuation or None,
                        interested_price=dd_interested_price or None,
                        catalysts=dd_catalysts or None,
                        position_sizing_plan=dd_sizing or None,
                        sell_criteria=dd_sell_criteria or None,
                        conclusion=dd_conclusion,
                        market_snapshot=market_snapshot,
                        sell_trigger_price=dd_sell_trigger_price or None,
                        sell_trigger_date=dd_sell_trigger_date.isoformat() if dd_sell_trigger_date else None,
                        thesis_score=dd_thesis_score,
                        management_score=dd_management_score,
                        bear_case_score=dd_bear_score,
                        valuation_score=dd_valuation_score,
                        catalysts_score=dd_catalysts_score,
                        technical_analysis=dd_technical_analysis or None,
                        technical_analysis_score=dd_technical_analysis_score,
                    )
                    st.success(f"New version for {dd_ticker} saved!")
                    st.rerun()

        st.markdown("**Your deep-dives**")
        dd_overview = database.get_all_deep_dive_tickers(user_email)
        if not dd_overview:
            st.caption("No deep-dives logged yet -- add one above.")
        else:
            conclusion_emoji_map = {"Buy": "🟢", "Watch": "🟡", "Pass": "🔴"}
            dd_tiles_per_row = 4
            for row_start in range(0, len(dd_overview), dd_tiles_per_row):
                row_entries = dd_overview[row_start:row_start + dd_tiles_per_row]
                tile_cols = st.columns(dd_tiles_per_row)
                for tile_col, entry in zip(tile_cols, row_entries):
                    with tile_col:
                        with st.container(border=True):
                            logo_url = get_company_logo_url(entry["ticker"])
                            conclusion_emoji = conclusion_emoji_map.get(entry["conclusion"], "")
                            tile_overall_score = _compute_deep_dive_overall_score(entry)

                            logo_html = (
                                f'<img src="{logo_url}" width="56" height="56" '
                                f'style="border-radius:12px; object-fit:contain; background:#fff; padding:4px;" />'
                                if logo_url else
                                '<div style="width:56px; height:56px; border-radius:12px; background:rgba(31,174,150,0.12); '
                                'display:flex; align-items:center; justify-content:center; font-size:1.4rem;">📈</div>'
                            )
                            if tile_overall_score is not None:
                                score_color = _deep_dive_score_color(tile_overall_score)
                                score_html = (
                                    f'<div style="font-size:2rem; font-weight:800; color:{score_color}; line-height:1;">'
                                    f'{tile_overall_score:.1f}<span style="font-size:0.85rem; font-weight:600; opacity:0.75;">/10</span></div>'
                                )
                            else:
                                score_html = '<div style="font-size:0.85rem; color:#8992A3;">No score yet</div>'

                            st.markdown(
                                f"""
                                <div style="text-align:center; padding: 0.25rem 0 0.75rem 0;">
                                    <div style="display:flex; justify-content:center; margin-bottom:8px;">{logo_html}</div>
                                    <div style="font-weight:700; font-size:1.1rem; color:#EAEDF1;">{entry['ticker']} {conclusion_emoji}</div>
                                    <div style="font-size:0.8rem; color:#8992A3; margin: 2px 0 10px 0;">{entry['naam']}</div>
                                    {score_html}
                                    <div style="font-size:0.7rem; color:#8992A3; margin-top:8px;">Updated {entry['created_at'][:10]}</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                            with st.expander("View history"):
                                history = database.get_deep_dives_for_ticker(user_email, entry["ticker"])
                                st.caption(f"{len(history)} version(s) logged, most recent first.")
                                for version in history:
                                    _render_deep_dive_version(version, user_email)

        st.divider()

    elif current_subview == "portfolio":
        import database

        user_email = st.user.email
        holdings = filter_active_holdings(database.get_user_holdings(user_email))
        holdings.sort(key=lambda h: h.get("position_value") or 0, reverse=True)
        is_premium = database.is_premium_user(user_email)

        if not holdings:
            st.info("Add positions under My Portfolio to see your analysis here.")
            st.stop()

        risk_profile = database.get_risk_profile(user_email)
        with st.spinner("Loading sector/valuation data..."):
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

        # --- Sectoren -- nu met een taartdiagram i.p.v. alleen tekst ---
        with st.expander("🏭 Sectors", expanded=True):
            for finding in analyze_sectors(holdings, infos, risk_profile["max_sector_pct"]):
                st.markdown(f"- {finding}")

            sector_values_chart = {}
            for h in holdings:
                value = h.get("position_value") or 0
                sector = infos.get(h["ticker"], {}).get("sector") or "Non-equity / Other"
                sector_values_chart[sector] = sector_values_chart.get(sector, 0) + value
            if sector_values_chart:
                sector_fig = build_breakdown_pie_chart(list(sector_values_chart.keys()), list(sector_values_chart.values()))
                st.plotly_chart(sector_fig, width="stretch")

            sector_values_check = {
                s: v for s, v in sector_values_chart.items() if s != "Non-equity / Other"
            }
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

        # --- Diversificatie -- nu met een taartdiagram i.p.v. alleen tekst ---
        with st.expander("🧩 Diversification", expanded=True):
            for finding in analyze_diversification(holdings, infos):
                st.markdown(f"- {finding}")

            type_values_chart = {}
            for h in holdings:
                value = h.get("position_value") or 0
                raw_quote_type = infos.get(h["ticker"], {}).get("quoteType")
                if not raw_quote_type:
                    ticker_suffix = h["ticker"].rsplit("-", 1)[-1].upper() if "-" in h["ticker"] else ""
                    asset_type = "CRYPTOCURRENCY" if ticker_suffix in ("EUR", "USD", "GBP", "USDT", "USDC") else "UNKNOWN"
                else:
                    asset_type = raw_quote_type
                type_values_chart[asset_type] = type_values_chart.get(asset_type, 0) + value
            if type_values_chart:
                type_fig = build_breakdown_pie_chart(
                    [t.title() for t in type_values_chart.keys()], list(type_values_chart.values())
                )
                st.plotly_chart(type_fig, width="stretch")

        # --- Regio -- nieuwe dimensie, nog niet eerder getoond ---
        with st.expander("🌍 Region", expanded=True):
            region_values = {}
            for h in holdings:
                value = h.get("position_value") or 0
                region = get_holding_region(h["ticker"], infos.get(h["ticker"], {}))
                region_values[region] = region_values.get(region, 0) + value
            total_value_for_region = sum(h.get("position_value") or 0 for h in holdings)
            if region_values and total_value_for_region > 0:
                region_fig = build_breakdown_pie_chart(list(region_values.keys()), list(region_values.values()))
                st.plotly_chart(region_fig, width="stretch")
                dominant_region, dominant_region_value = max(region_values.items(), key=lambda x: x[1])
                dominant_region_pct = dominant_region_value / total_value_for_region * 100
                st.caption(f"{dominant_region} makes up {dominant_region_pct:.0f}% of your tracked portfolio.")
            else:
                st.caption("No region data available for your tracked positions.")

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


    elif current_subview == "dividend":
        import database

        user_email = st.user.email
        holdings = filter_active_holdings(database.get_user_holdings(user_email))
        holdings.sort(key=lambda h: h.get("position_value") or 0, reverse=True)
        is_premium = database.is_premium_user(user_email)

        if not holdings:
            st.info("Add positions under My Portfolio to see your analysis here.")
            st.stop()

        risk_profile = database.get_risk_profile(user_email)

        # --- Performance (rendement uit gelogde transacties) ---
        # BELANGRIJK: dit gebruikt de SNELLE, gebatchte koersgeschiedenis
        # (shared_history) als EERSTE keuze voor de huidige prijs, i.p.v.
        # te wachten op infos/.info (die pas hierONDER wordt opgehaald,
        # en van yfinance bekend traag is). Zo verschijnt Performance
        # meteen, terwijl de rest van de pagina (Sectors/Diversification/
        # Risk, die WEL .info-velden nodig hebben) daarna pas verder laadt.
        with st.spinner("Loading dividend data..."):
            infos = get_tickers_info(holdings)

        with st.expander("💰 Dividend"):
            if is_premium:
                dividend_result = analyze_dividend(holdings, infos)
                for finding in dividend_result["findings"]:
                    st.markdown(f"- {finding}")
                if dividend_result["per_position"]:
                    if st.checkbox(f"Show breakdown per position ({len(dividend_result['per_position'])})", key="dividend_breakdown"):
                        df_div = pd.DataFrame(dividend_result["per_position"])
                        symbol = dividend_result["currency_symbol"]
                        df_display = pd.DataFrame({
                            "Name": df_div["naam"],
                            "Ticker": df_div["ticker"],
                            "Annual Dividend": df_div["annual_dividend"].apply(
                                lambda v: f"{symbol}{v:,.2f}" if v is not None else "-"
                            ),
                            "Yield": df_div["yield_pct"].apply(
                                lambda v: f"{v:.2f}%" if v is not None else "-"
                            ),
                        })
                        st.dataframe(
                            df_display, width=480, hide_index=True,
                            height=min(38 * (len(df_display) + 1), 300),
                        )
            else:
                st.info("🔒 Upgrade to Premium for your dividend income overview and upcoming ex-dividend dates.")


    else:
        import database

        user_email = st.user.email
        holdings = filter_active_holdings(database.get_user_holdings(user_email))
        holdings.sort(key=lambda h: h.get("position_value") or 0, reverse=True)
        is_premium = database.is_premium_user(user_email)

        if not holdings:
            st.info("Add positions under My Portfolio to see your analysis here.")
            st.stop()

        risk_profile = database.get_risk_profile(user_email)

        # --- Performance (rendement uit gelogde transacties) ---
        # BELANGRIJK: dit gebruikt de SNELLE, gebatchte koersgeschiedenis
        # (shared_history) als EERSTE keuze voor de huidige prijs, i.p.v.
        # te wachten op infos/.info (die pas hierONDER wordt opgehaald,
        # en van yfinance bekend traag is). Zo verschijnt Performance
        # meteen, terwijl de rest van de pagina (Sectors/Diversification/
        # Risk, die WEL .info-velden nodig hebben) daarna pas verder laadt.
        with st.expander("📈 Performance", expanded=True):
            st.caption("Your real return, based on the buy/sell transactions you've logged under "
                       "My Portfolio -- excludes dividends. Includes fully closed positions. "
                       "Positions without logged transactions won't show a return here.")

            snapshot = database.get_performance_snapshot(user_email)
            refresh_col1, refresh_col2 = st.columns([3, 1])
            with refresh_col1:
                if snapshot and snapshot.get("computed_at"):
                    st.caption(f"Last updated: {snapshot['computed_at'][:16].replace('T', ' ')}")
                else:
                    st.caption("Calculating your performance for the first time...")
            with refresh_col2:
                refresh_clicked = st.button("🔄 Refresh", key="perf_refresh_btn")

            if refresh_clicked or not snapshot:
                # VOLLEDIGE (trage) herberekening -- alleen op expliciet verzoek
                # (de Refresh-knop) of bij het allereerste bezoek, NIET meer bij
                # elk bezoek aan de pagina. Dit is de kern van de snelheidsfix:
                # een volgend bezoek toont de opgeslagen snapshot INSTANT.
                all_holdings_incl_closed = database.get_user_holdings(user_email)
                with st.spinner("Loading price history..."):
                    shared_history = get_shared_history_for_holdings(all_holdings_incl_closed, period="max")
                today = datetime.now().date()
                performance_rows = []
                total_invested = 0.0
                total_pnl = 0.0
                earliest_date = None
                excluded_no_price = []
                for h in all_holdings_incl_closed:
                    transactions = database.get_transactions_for_holding(user_email, h["id"])
                    if not transactions:
                        continue
                    current_price = _price_near_date(shared_history.get(h["ticker"]), today, tolerance_days=10)
                    if current_price is None:
                        single_info = get_cached_ticker_info(h["ticker"])
                        current_price = single_info.get("currentPrice") or single_info.get("regularMarketPrice")
                    perf = compute_holding_performance(transactions, current_price)
                    if perf:
                        is_closed = perf["shares_held"] <= 0.0001
                        performance_rows.append({"naam": h["naam"], "ticker": h["ticker"], "closed": is_closed, **perf})
                        bought_cost = sum(t["shares"] * t["price"] + t["fee"] for t in transactions if t["transaction_type"] == "buy")
                        total_invested += bought_cost
                        total_pnl += perf["total_pnl"]
                        for t in transactions:
                            if earliest_date is None or t["transaction_date"] < earliest_date:
                                earliest_date = t["transaction_date"]
                    elif current_price is None:
                        excluded_no_price.append(h["naam"])

                if excluded_no_price:
                    st.caption(f"⚠️ Couldn't fetch a current price for: {', '.join(excluded_no_price)} -- "
                               f"excluded from the totals below until that's available again.")

                if performance_rows:
                    overall_return_pct = (total_pnl / total_invested * 100) if total_invested else None
                    if overall_return_pct is not None and pd.isna(overall_return_pct):
                        overall_return_pct = None

                    checkpoints = []
                    if earliest_date:
                        try:
                            since_inception_date = datetime.strptime(earliest_date, "%Y-%m-%d").date()
                            checkpoints.append(("Since inception", since_inception_date))
                        except Exception:
                            pass
                    checkpoints.append(("3 years", (datetime.now() - timedelta(days=365 * 3)).date()))
                    checkpoints.append(("1 year", (datetime.now() - timedelta(days=365)).date()))
                    checkpoints.append(("YTD", date(datetime.now().year, 1, 1)))
                    checkpoints.append(("3 months", (datetime.now() - timedelta(days=90)).date()))
                    checkpoints.append(("1 month", (datetime.now() - timedelta(days=30)).date()))

                    checkpoint_results = []
                    for label, window_start in checkpoints:
                        result = compute_personal_windowed_return(
                            all_holdings_incl_closed, user_email, window_start, history_by_ticker=shared_history
                        )
                        if result is not None:
                            checkpoint_results.append({"label": label, "return_pct": result["return_pct"]})

                    value_series_raw = compute_portfolio_value_over_time(
                        all_holdings_incl_closed, user_email, shared_history, num_points=60
                    )
                    value_series = [{"date": p["date"].isoformat(), "value": p["value"]} for p in value_series_raw]

                    database.save_performance_snapshot(
                        user_email, overall_return_pct=overall_return_pct, total_pnl=total_pnl,
                        earliest_date=earliest_date, checkpoint_results=checkpoint_results,
                        value_series=value_series, performance_rows=performance_rows,
                    )
                    st.rerun()  # herlaad meteen om de zojuist opgeslagen snapshot te tonen (consistente weergave-route)
                else:
                    st.caption("No positions with logged transactions yet -- log a buy under My Portfolio "
                               "to start tracking your return.")

            elif snapshot:
                # INSTANT -- toon de opgeslagen snapshot, GEEN netwerk-aanroepen nodig.
                overall_return_pct = snapshot.get("overall_return_pct")
                total_pnl = snapshot.get("total_pnl")
                earliest_date = snapshot.get("earliest_date")
                checkpoint_results = snapshot.get("checkpoint_results") or []
                value_series = [
                    {"date": datetime.strptime(p["date"], "%Y-%m-%d").date(), "value": p["value"]}
                    for p in (snapshot.get("value_series") or [])
                ]
                performance_rows = snapshot.get("performance_rows") or []

                if overall_return_pct is not None:
                    since_txt = f" since {earliest_date}" if earliest_date else ""
                    st.metric(f"Overall return{since_txt}", f"{overall_return_pct:+.1f}%", f"€{total_pnl:+,.2f}")

                ytd_result = next((r for r in checkpoint_results if r["label"] == "YTD"), None)
                one_year_result = next((r for r in checkpoint_results if r["label"] == "1 year"), None)
                ytd_pct = ytd_result["return_pct"] if ytd_result else None
                one_year_pct = one_year_result["return_pct"] if one_year_result else None

                # Benchmark-vergelijking is nu OPT-IN (een knop) i.p.v. automatisch
                # bij elk bezoek -- scheelt een extra netwerk-aanroep als je 'm
                # niet nodig hebt.
                show_benchmark = st.checkbox("Compare against a benchmark", key="perf_show_benchmark")
                benchmark_ytd = benchmark_1y = None
                benchmark_name = None
                if show_benchmark:
                    benchmark_name = st.selectbox("Compare against", list(BENCHMARK_OPTIONS.keys()), key="perf_benchmark")
                    if st.button(f"Fetch {benchmark_name}", key="perf_fetch_benchmark"):
                        with st.spinner(f"Fetching {benchmark_name}..."):
                            try:
                                benchmark_history = get_cached_ticker_history(BENCHMARK_OPTIONS[benchmark_name], period="2y")
                                benchmark_ytd = compute_price_return(benchmark_history, since_date=datetime(datetime.now().year, 1, 1))
                                benchmark_1y = compute_price_return(benchmark_history, days_back=365)
                            except Exception:
                                benchmark_ytd = benchmark_1y = None

                pcol1, pcol2 = st.columns(2)
                with pcol1:
                    if ytd_pct is not None:
                        delta_txt = f"{ytd_pct - benchmark_ytd:+.1f}% vs {benchmark_name}" if benchmark_ytd is not None else None
                        st.metric("YTD", f"{ytd_pct:+.1f}%", delta_txt)
                    else:
                        st.metric("YTD", "n/a")
                with pcol2:
                    if one_year_pct is not None:
                        delta_txt = f"{one_year_pct - benchmark_1y:+.1f}% vs {benchmark_name}" if benchmark_1y is not None else None
                        st.metric("1-Year", f"{one_year_pct:+.1f}%", delta_txt)
                    else:
                        st.metric("1-Year", "n/a")
                st.caption("Your real return over this period -- accounts for shares you already "
                           "held plus any buys/sells you made during it.")

                if len(value_series) >= 2:
                    st.markdown("**Your portfolio value over time**")
                    chart_timeframe = st.radio(
                        "Timeframe", ["1M", "3M", "1Y", "3Y", "ALL"], index=4,
                        horizontal=True, key="perf_chart_timeframe",
                    )
                    # Filteren op de AL berekende data -- geen nieuwe netwerk-
                    # aanroepen nodig, dus dit is instant, ook vanuit een
                    # opgeslagen snapshot.
                    timeframe_days = {"1M": 30, "3M": 90, "1Y": 365, "3Y": 365 * 3, "ALL": None}
                    days_back = timeframe_days[chart_timeframe]
                    if days_back is not None:
                        cutoff_date = datetime.now().date() - timedelta(days=days_back)
                        filtered_series = [p for p in value_series if p["date"] >= cutoff_date]
                        if len(filtered_series) < 2:
                            # Te weinig punten binnen deze periode (bv. account
                            # bestaat nog niet zo lang) -- terugvallen op ALL
                            # i.p.v. een lege/kapotte grafiek te tonen.
                            filtered_series = value_series
                    else:
                        filtered_series = value_series

                    value_fig = go.Figure()
                    value_fig.add_trace(go.Scatter(
                        x=[p["date"].isoformat() for p in filtered_series],
                        y=[p["value"] for p in filtered_series],
                        mode="lines",
                        line=dict(color="#1FAE96", width=2),
                        fill="tozeroy",
                        fillcolor="rgba(31,174,150,0.10)",
                        hovertemplate="%{x}: €%{y:,.0f}<extra></extra>",
                    ))
                    value_fig.update_layout(
                        yaxis_title="Portfolio value (€)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="Inter, sans-serif", color="#EAEDF1", size=11),
                        margin=dict(t=30, b=10, l=10, r=10),
                        height=320,
                        showlegend=False,
                        xaxis=dict(gridcolor="rgba(137,146,163,0.15)"),
                        yaxis=dict(gridcolor="rgba(137,146,163,0.15)"),
                    )
                    st.plotly_chart(value_fig, width="stretch")

                if performance_rows and st.checkbox(f"Show individual positions ({len(performance_rows)})", key="show_perf_positions"):
                    for r in performance_rows:
                        pct = r["total_return_pct"]
                        closed_txt = " *(closed)*" if r.get("closed") else ""
                        if pct is not None:
                            color_emoji = "🟢" if pct >= 0 else "🔴"
                            st.markdown(f"- {color_emoji} **{r['naam']} ({r['ticker']})**{closed_txt}: {pct:+.1f}% (€{r['total_pnl']:+,.2f})")
                        else:
                            st.markdown(f"- {r['naam']} ({r['ticker']}){closed_txt}: return unknown")

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
                <tr><td>Momentocrats, Snowballers, Rocket List (Discover)</td><td>Top 3 each</td><td>All results</td></tr>
                <tr><td>Weekly email for your chosen signals</td><td>Top 3 each</td><td>All results</td></tr>
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

    with st.expander("Can I import my transaction history from my broker?"):
        st.write(
            "Yes, for DEGIRO -- under My Portfolio, 'Import from a broker'. Using a different "
            "broker? Let us know via the contact form below, and we'll look into adding it."
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

elif current_view == "privacy":
    st.markdown("### Privacy")
    st.caption("Plain language, not a legal document -- if you have questions beyond this, "
               "just ask via Support.")

    st.markdown(
        """
        <div style="background: linear-gradient(135deg, rgba(31,174,150,0.16), rgba(31,174,150,0.02));
                    border: 1px solid rgba(31,174,150,0.4); border-radius: 12px;
                    padding: 1.25rem 1.5rem; margin: 0.75rem 0 1.25rem 0;">
            <div style="color:#1FAE96; font-weight:700; font-size:0.75rem; letter-spacing:1.5px; text-transform:uppercase;">
                🔒 Your data is pseudonymized
            </div>
            <div style="color:#EAEDF1; font-size:1rem; font-weight:600; margin-top:6px; line-height:1.5;">
                Your email address is never stored in readable form alongside your portfolio.
            </div>
            <div style="color:#8992A3; font-size:0.9rem; margin-top:8px; line-height:1.6;">
                Every position, transaction, and preference is stored under a one-way hash --
                a scrambled, irreversible code -- instead of your actual email address. Even
                we can't casually see whose data is whose just by looking at the database.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("What we collect"):
        st.write(
            "When you log in (via Google or Microsoft), we get your email address and name. "
            "Beyond that, we only store what you actively enter: the positions and watchlist "
            "items you add, any buy/sell transactions you log (or import from a broker), your "
            "risk profile answers, your email preferences, and your cash amount if you fill "
            "one in."
        )

    with st.expander("Why we collect it"):
        st.write(
            "Purely to show you your own data back (My Portfolio, Analyze, your personalized "
            "Today briefing), and to send you the daily/weekly emails you've opted into. "
            "Nothing here is used to build a profile of you for advertising -- there are no ads "
            "on Hesty's, and there never will be."
        )

    with st.expander("Who can see it"):
        st.write(
            "Only you, when logged into your own account. As explained above, your portfolio "
            "and transaction data is stored under a hashed identifier, not your readable email "
            "address. A small, separate table maps that hash back to your real address -- purely "
            "so we can still send you the emails you've opted into. We only ever look at "
            "anything ourselves to fix a bug or help with a support question."
        )

    with st.expander("Third parties involved"):
        st.write(
            "Supabase hosts our database. Google or Microsoft handle the login itself (we "
            "never see your password). Stripe will handle payments once Premium is actually "
            "for sale. Market data (prices, company info) comes from Yahoo Finance -- no "
            "personal data is sent there, just ticker symbols."
        )

    with st.expander("Your control over it"):
        st.write("You can remove any position, watchlist item, or transaction yourself at any time.")
        st.markdown(
            'Want your entire account and its data deleted? Reach out via '
            '<a href="?view=support" class="inline-link" target="_self">Support</a> and we\'ll take care of it.',
            unsafe_allow_html=True,
        )

    with st.expander("Cookies"):
        st.write(
            "A login session cookie is used to keep you signed in -- that's required for "
            "Google/Microsoft login to work at all. We don't use tracking or advertising cookies."
        )

elif current_view == "confirm":
    import database as _database_for_confirm

    st.markdown("### Confirm your subscription")
    token = st.query_params.get("token", "")
    if not token:
        st.error("Missing confirmation link. Please use the link from your email.")
    elif _database_for_confirm.confirm_email_subscriber(token):
        st.success("✅ You're all set! You'll get today's new bullish signals in your inbox every weekday morning.")
        st.markdown(
            '<a href="?view=discover" class="button-link" target="_self">Back to Discover &rarr;</a>',
            unsafe_allow_html=True,
        )
    else:
        st.error("This confirmation link is invalid or has already been used.")

elif current_view == "unsubscribe":
    import database as _database_for_unsubscribe

    st.markdown("### Unsubscribe")
    token = st.query_params.get("token", "")
    if not token:
        st.error("Missing unsubscribe link. Please use the link from your email.")
    elif _database_for_unsubscribe.unsubscribe_email_subscriber(token):
        st.success("You've been unsubscribed. Sorry to see you go!")
    else:
        st.info("This link is invalid or you're already unsubscribed.")

st.divider()
st.caption("Hesty's combines technical signals, fundamental screens, and portfolio analysis to help "
           "you research faster. It's not an automated trading strategy, and nothing here is "
           "personalized financial advice.")
st.markdown(
    '<a href="?view=privacy" class="inline-link" target="_self">Privacy</a>',
    unsafe_allow_html=True,
)
