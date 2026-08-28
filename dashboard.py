"""
Dashboard: visualiseert de resultaten van screener.py en portfolio_watch.py.
(Deze code-commentaren blijven in het Nederlands -- alleen de daadwerkelijk
zichtbare website-tekst is naar het Engels vertaald.)

Navigatie gebruikt sinds de stap-B-herstructurering st.navigation() (met
position="hidden") i.p.v. handmatige ?view=-query-param-routing -- elke
pagina heeft nu een eigen URL-pad (bv. /discover, /today), en de zijbalk
gebruikt st.page_link() i.p.v. gewone HTML-<a>-links. Dat voorkomt de
volledige pagina-herlading (met bijbehorende zwarte flits) die er bij de
oude opzet was.

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
import requests
import stripe
import streamlit as st
import yfinance as yf

from emailer import send_email
import database

st.set_page_config(page_title="Hesty's", page_icon="◆", layout="wide")

# --- Visuele identiteit: donkere 'kluis/terminal'-stijl, geen standaard-look ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,400,0,0&display=swap');

/* --- Ontwerptaal-fundament: kleuren als CSS-variabelen, 1 centrale
   plek om het palet te definieren i.p.v. losse rgba(...)-waarden overal
   door de code heen. Jade is bewust GERESERVEERD voor primaire acties,
   positieve waarden en het merk zelf -- secundaire elementen (randen,
   info-boxjes) gebruiken de neutrale grijsblauwe kleuren, zodat jade
   opvalt wanneer het verschijnt i.p.v. overal tegelijk te 'wassen'. ---
*/
:root {
    --color-jade: #1FAE96;
    --color-jade-soft: rgba(31, 174, 150, 0.12);
    --color-negative: #E5484D;
    --color-warning: #D4A857;
    --color-warning-soft: rgba(212, 168, 87, 0.12);
    --color-text-primary: #EAEDF1;
    --color-text-secondary: #8992A3;
    --color-border-neutral: rgba(137, 146, 163, 0.25);
    --color-bg-elevated: rgba(255, 255, 255, 0.03);
}

.material-symbols-outlined {
    font-family: 'Material Symbols Outlined';
    font-weight: normal;
    font-style: normal;
    display: inline-block;
    line-height: 1;
    text-transform: none;
    letter-spacing: normal;
    word-wrap: normal;
    white-space: nowrap;
    direction: ltr;
    vertical-align: middle;
}

html, body, p, span, div, label {
    font-family: 'Inter', sans-serif;
}
h1, h2, h3 {
    font-family: 'Fraunces', serif !important;
    font-weight: 600 !important;
    font-optical-sizing: auto;
    letter-spacing: -0.01em;
}
/* Grote, prominente koppen (hero-headlines) krijgen een zwaarder
   Fraunces-gewicht (700 i.p.v. 600) -- maakt het serif-karakter
   duidelijker zichtbaar en onderscheidend, i.p.v. bijna sans-serif-
   ogend bij een lichter gewicht. Toegepast via een aparte klasse i.p.v.
   alle h1 aan te passen, want kleinere koppen (h2/h3 in expanders etc.)
   ogen beter bij het lichtere gewicht. */
.hero-headline {
    font-family: 'Fraunces', serif !important;
    font-weight: 700 !important;
    font-optical-sizing: auto;
    letter-spacing: -0.015em;
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
/* Specifieke klasse voor de logo-titel in de zijbalk -- Streamlit's
   eigen interne CSS (een 'st-emotion-cache-...'-klasse) voegt standaard
   padding:1.25rem 0 1rem toe aan ELKE h1 binnen een markdown-blok. Onze
   eerdere margin:0-reset raakte dat niet (padding is een andere
   eigenschap), wat een onverwacht grote ruimte tussen 'HESTYS' en de
   tagline veroorzaakte. Een eigen, specifieke klasse (i.p.v. inline
   stijlen, die Streamlit soms deels lijkt te filteren) is betrouwbaarder. */
.sidebar-logo-title {
    font-size: 1.35rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.01em !important;
    font-family: 'Inter', sans-serif !important;
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1.1 !important;
}
.app-header .tagline {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.08em;
    color: #8992A3 !important;
    margin-top: 0.15rem;
}

/* Mobiel: header flink compacter -- op een smal scherm nam dit voorheen
   zoveel verticale ruimte in dat bezoekers eerst moesten scrollen
   voordat ze bij daadwerkelijke content kwamen. */
@media (max-width: 640px) {
    .app-header {
        padding: 0.7rem 0 0.5rem 0;
        margin-bottom: 0.75rem;
    }
    .app-header-top {
        gap: 0.6rem;
        margin-bottom: 0.6rem;
    }
    .app-header-top svg {
        width: 30px !important;
        height: 30px !important;
    }
    .app-header h1 {
        font-size: 1.35rem !important;
    }
    .app-header .tagline {
        font-size: 0.55rem;
    }
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
/* Google-logootje in de 'Continue with Google'-knop op de login-pagina --
   st.button() ondersteunt geen custom afbeeldingen als icoon (alleen
   emoji/Material Icons), dus via de .st-key-<key>-CSS-klasse (Streamlit's
   eigen, officiele manier om 1 specifieke widget te targeten) een
   achtergrond-afbeelding + linker-padding toegevoegd aan precies déze knop. */
.st-key-login_page_google button {
    background-image: url("data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTgiIGhlaWdodD0iMTgiIHZpZXdCb3g9IjAgMCAxOCAxOCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZmlsbD0iIzQyODVGNCIgZD0iTTE3LjY0IDkuMmMwLS42MzctLjA1Ny0xLjI1MS0uMTY0LTEuODRIOXYzLjQ4MWg0Ljg0NGMtLjIwOSAxLjEyNS0uODQzIDIuMDc4LTEuNzk2IDIuNzE3djIuMjU4aDIuOTA4YzEuNzAyLTEuNTY3IDIuNjg0LTMuODc0IDIuNjg0LTYuNjE1eiIvPgo8cGF0aCBmaWxsPSIjMzRBODUzIiBkPSJNOSAxOGMyLjQzIDAgNC40NjctLjgwNiA1Ljk1Ni0yLjE4bC0yLjkwOC0yLjI1OWMtLjgwNi41NC0xLjgzNy44Ni0zLjA0OC44Ni0yLjM0NCAwLTQuMzI4LTEuNTg0LTUuMDM2LTMuNzExSC45NTd2Mi4zMzJDMi40MzggMTUuOTgzIDUuNDgyIDE4IDkgMTh6Ii8+CjxwYXRoIGZpbGw9IiNGQkJDMDUiIGQ9Ik0zLjk2NCAxMC43MWMtLjE4LS41NC0uMjgyLTEuMTE3LS4yODItMS43MXMuMTAyLTEuMTcuMjgyLTEuNzFWNC45NThILjk1N0MuMzQ3IDYuMTczIDAgNy41NDggMCA5cy4zNDggMi44MjcuOTU3IDQuMDQybDMuMDA3LTIuMzMyeiIvPgo8cGF0aCBmaWxsPSIjRUE0MzM1IiBkPSJNOSAzLjU4YzEuMzIxIDAgMi41MDguNDU0IDMuNDQgMS4zNDVsMi41ODItMi41OEMxMy40NjMuODkxIDExLjQyNiAwIDkgMCA1LjQ4MiAwIDIuNDM4IDIuMDE3Ljk1NyA0Ljk1OEwzLjk2NCA3LjI5QzQuNjcyIDUuMTYzIDYuNjU2IDMuNTggOSAzLjU4MHoiLz4KPC9zdmc+");
    background-repeat: no-repeat;
    background-position: 16px center;
    padding-left: 42px !important;
}

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
.positions-table tbody tr:nth-child(even) {
    background: rgba(255,255,255,0.015);
}
.positions-table tbody tr:hover {
    background: rgba(31,174,150,0.06);
}
.positions-table th:first-child,
.positions-table td:first-child {
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.positions-table code {
    color: #1FAE96;
    background: none;
    font-size: 0.85rem;
}
.positions-table .position-logo {
    width: 20px;
    height: 20px;
    border-radius: 5px;
    object-fit: contain;
    background: #fff;
    padding: 2px;
    vertical-align: middle;
    margin-right: 0.5rem;
}
.positions-table .weight-bar-track {
    display: inline-block;
    width: 46px;
    height: 5px;
    border-radius: 3px;
    background: #232D3A;
    vertical-align: middle;
    margin-right: 0.5rem;
    overflow: hidden;
}
.positions-table .weight-bar-fill {
    display: block;
    height: 100%;
    background: #1FAE96;
    border-radius: 3px;
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
    Generieke, COMPACTE donut-chart voor een verdeling (sector/asset-type/
    regio). De legenda staat nu horizontaal ONDER de taart (i.p.v. rechts
    ernaast) -- dat voorkomt de grote, lege ruimte die ontstaat als een
    smalle taart wordt uitgerekt over een brede kolom met de legenda ver
    weggeduwd naar rechts.
    """
    palette = ["#1FAE96", "#E8A93C", "#4DA6FF", "#E5484D", "#C77DFF",
               "#3ED9C4", "#F5C518", "#FF8A5C", "#8992A3", "#5AC8B0", "#B0E0D8"]
    colors = (palette * (len(labels) // len(palette) + 1))[:len(labels)]

    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values, hole=0.6,
        marker=dict(colors=colors, line=dict(color="#101825", width=2)),
        texttemplate="%{percent:.0%}",
        textposition="inside",
        textfont=dict(family="Inter, sans-serif", size=11, color="#EAEDF1"),
        hovertemplate="%{label}: %{percent:.1%}<extra></extra>",
    )])
    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="top", y=-0.08, xanchor="center", x=0.5,
            font=dict(family="Inter, sans-serif", size=10, color="#8992A3"), bgcolor="rgba(0,0,0,0)",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=10, b=10, l=10, r=10),
        height=280,
        width=280,
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


TICKER_EXCHANGE_CURRENCY = {
    "AS": "EUR", "PA": "EUR", "DE": "EUR", "MI": "EUR", "MC": "EUR",
    "BR": "EUR", "LS": "EUR", "HE": "EUR", "VI": "EUR", "IR": "EUR",
    "L": "GBP",
    "TO": "CAD", "V": "CAD",
    "SW": "CHF",
    "ST": "SEK", "CO": "DKK", "OL": "NOK",
    "HK": "HKD",
    "T": "JPY",
    "AX": "AUD",
}


@st.cache_data(ttl=86400, show_spinner=False)
def get_cached_ticker_currency(ticker: str) -> str:
    """
    Cachet de valuta van een ticker voor 24 uur (i.p.v. de standaard 5
    minuten) -- de valuta van een ticker verandert vrijwel nooit, dus een
    lange cache-tijd voorkomt dat elke portfolio-refresh opnieuw de trage
    .info-aanroep per positie moet doen.

    Bepaalt de valuta EERST via het ticker-achtervoegsel (bv. '.AS' ->
    EUR, '.L' -> GBP) -- een VEEL betrouwbaardere bron dan yfinance's
    .info['currency']-veld, dat (net als eerder gevonden bij 'website')
    regelmatig lijkt te ontbreken. Concreet gevolg zonder deze fix: een
    EUR-aandeel als ADYEN.AS werd via de terugval-standaard 'USD'
    behandeld, waardoor er een ONTERECHTE USD->EUR-omrekening op een
    al-EUR-prijs plaatsvond (zichtbaar als een te lage getoonde prijs).
    Alleen als het achtervoegsel niet herkend wordt (bv. Amerikaanse
    tickers zonder achtervoegsel), valt dit terug op .info als laatste optie.
    """
    if "." in ticker:
        suffix = ticker.rsplit(".", 1)[-1].upper()
        if suffix in TICKER_EXCHANGE_CURRENCY:
            return TICKER_EXCHANGE_CURRENCY[suffix]
    if "-" in ticker:
        crypto_suffix = ticker.rsplit("-", 1)[-1].upper()
        if crypto_suffix in ("EUR", "GBP"):
            return crypto_suffix
        if crypto_suffix in ("USD", "USDT", "USDC"):
            return "USD"
    try:
        return yf.Ticker(ticker).info.get("currency", "USD")
    except Exception:
        return "USD"


def refresh_portfolio_values(holdings: list, user_email: str, display_currency: str = "EUR") -> tuple:
    """
    Haalt voor al je posities in 1x (via een gebatchte download) de
    actuele koers op, gebruikt een 24-uur-gecachte valuta-lookup per
    ticker (i.p.v. een trage .info-aanroep per positie bij elke refresh),
    rekent om naar de gekozen weergave-valuta, en werkt position_value
    bij. Rate-limited tot 1x per 10 seconden per gebruiker (ruim
    voldoende tegen per-ongeluk-dubbelklikken, zonder te frustreren).

    Geeft (success: bool, message: str) terug.
    """
    last_refresh = database.get_last_price_refresh(user_email)
    if last_refresh:
        last_refresh_dt = datetime.fromisoformat(last_refresh.replace("Z", "+00:00"))
        seconds_since = (datetime.now(timezone.utc) - last_refresh_dt).total_seconds()
        if seconds_since < 10:
            wait_seconds = int(10 - seconds_since)
            return False, f"Please wait {wait_seconds} more second(s) before updating again."

    tickers_to_fetch = list({h["ticker"] for h in holdings if h.get("shares")})
    if not tickers_to_fetch:
        return False, "No positions with shares to update."

    shared_prices = get_shared_history_for_holdings(
        [{"ticker": t} for t in tickers_to_fetch], period="5d"
    )
    today = datetime.now().date()

    fx_cache = {}
    updated_count = 0
    skipped_currencies = set()

    for holding in holdings:
        if not holding.get("shares"):
            continue
        try:
            hist = shared_prices.get(holding["ticker"])
            native_price = _price_near_date(hist, today, tolerance_days=10) if hist is not None else None
            if native_price is None:
                continue
            native_currency = get_cached_ticker_currency(holding["ticker"])

            if native_currency not in fx_cache:
                fx_cache[native_currency] = get_fx_rate(native_currency, display_currency)
            fx_rate = fx_cache[native_currency]

            if fx_rate is None:
                skipped_currencies.add(native_currency)
                continue

            new_value = holding["shares"] * native_price * fx_rate
            day_change_pct = compute_day_change_pct(hist)
            database.update_holding_value(
                holding["id"], user_email, new_value, value_currency=display_currency, day_change_pct=day_change_pct
            )
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

    Geeft (tekst) terug ZONDER het eigen emoji ervoor -- de aanroeper
    plakt daar zelf een icoon voor, consistent met de andere Today's
    radar-items.
    """
    total_value = sum(h.get("position_value") or 0 for h in holdings)
    if total_value <= 0:
        return None
    largest = max(holdings, key=lambda h: h.get("position_value") or 0)
    largest_pct = (largest.get("position_value") or 0) / total_value * 100
    if largest_pct > max_position_pct:
        return f"<b>{largest['naam']}</b> is now {largest_pct:.0f}% of your portfolio, above your {max_position_pct:.0f}% target."
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
    """Risico-kaart: gewogen koers-winst-verhouding + welke positie dat cijfer het meest beinvloedt."""
    findings = []
    total_value = sum(h.get("position_value") or 0 for h in holdings)
    if total_value <= 0:
        return ["No position values available yet -- click 'Update portfolio value' first."]

    pe_entries = [
        {"naam": h["naam"], "ticker": h["ticker"], "pe": infos.get(h["ticker"], {}).get("trailingPE"),
         "weight": h.get("position_value") or 0}
        for h in holdings
    ]
    pe_entries = [e for e in pe_entries if e["pe"] and e["weight"]]
    if pe_entries:
        weighted_pe = sum(e["pe"] * e["weight"] for e in pe_entries) / sum(e["weight"] for e in pe_entries)
        if weighted_pe >= 25:
            findings.append(f"{_icon_span('bar_chart', size_px=14, color='#8992A3')} Weighted average P/E: {weighted_pe:.1f}x -- relatively expensive vs. the long-term market average (roughly 15-20x).")
        elif weighted_pe <= 12:
            findings.append(f"{_icon_span('bar_chart', size_px=14, color='#8992A3')} Weighted average P/E: {weighted_pe:.1f}x -- relatively cheap vs. the long-term market average (roughly 15-20x).")
        else:
            findings.append(f"{_icon_span('bar_chart', size_px=14, color='#8992A3')} Weighted average P/E: {weighted_pe:.1f}x -- roughly in line with the long-term market average.")

        # Context: WELKE positie beinvloedt dit getal het meest? Een gewogen
        # gemiddelde zonder deze context kan misleidend zijn -- een enkele,
        # grote positie kan het cijfer volledig bepalen.
        dominant_entry = max(pe_entries, key=lambda e: e["weight"])
        dominant_weight_pct = dominant_entry["weight"] / total_value * 100
        if dominant_weight_pct >= 30:
            findings.append(
                f"{_icon_span('warning', size_px=14, color='#8992A3')} This is mostly driven by **{dominant_entry['naam']} ({dominant_entry['ticker']})** "
                f"-- {dominant_weight_pct:.0f}% of your portfolio, P/E {dominant_entry['pe']:.1f}x."
            )
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
            f"{_icon_span('payments', size_px=14, color='#8992A3')} Estimated annual dividend income: ~{currency_symbol}{total_annual_dividend:,.0f}{underestimate_note}."
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
    "Cloud / SaaS": "WCLD", "Data Centers": "DTCR", "Aerospace & Defense": "ITA",
    "Quantum Computing": "QTUM", "Nuclear Energy": "NLR", "Space": "ARKX",
    "Drones": "UAV", "Materials & Critical Minerals": "REMX", "Fintech": "FINX",
    "Infrastructure": "PAVE", "Power & Utilities": "XLU",
    "Crypto (Top 10)": "HODLX.SW", "Precious Metals": "GLTR",
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
            rotation = build_sector_rotation(region=region)
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
        theme_rotation = build_theme_rotation()
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


THEME_ROTATION_WINDOW_DAYS = 21  # handelsdagen -- zelfde als build_theme_rotation_trend()'s rolling_window_days


def build_theme_rotation(window_days: int = THEME_ROTATION_WINDOW_DAYS) -> list:
    """
    Zelfde logica als build_sector_rotation(), maar dan voor de populaire
    THEMA-ETF's (Robotics & AI, Clean Energy, etc.) i.p.v. de officiële
    GICS-sectoren.

    Gebruikt een EXACT 'N handelsdagen terug'-venster (i.p.v. yfinance's
    'period=1mo'-string) -- zodat dit getal exact overeenkomt met het
    laatste punt van build_theme_rotation_trend()'s grafiek. Voorheen
    gebruikten beide een net-iets-ander tijdvak (kalendermaand vs. 21
    handelsdagen), wat bij een volatiel thema zoals Genomics & Biotech
    tot een merkbaar afwijkend percentage kon leiden.
    """
    fetch_period = f"{window_days + 15}d"
    results = []
    for theme, ticker in THEME_ETFS.items():
        try:
            hist = get_cached_ticker_history(ticker, period=fetch_period)
            if hist is None or hist.empty:
                continue
            # Zelfde fix als bij build_sector_rotation(): de eerste/laatste
            # rij kan een onvolledige koers (NaN) zijn -- pak de eerste/
            # laatste GELDIGE koers i.p.v. blindelings de rand-rijen.
            valid_closes = hist["Close"].dropna()
            if len(valid_closes) > window_days:
                ret = (valid_closes.iloc[-1] / valid_closes.iloc[-1 - window_days] - 1) * 100
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


def _rotation_gradient_color(return_pct):
    """
    Interpoleert tussen rood (sterk negatief, <=-15%), amber (neutraal,
    rond 0%), en jade-groen (sterk positief, >=+15%) -- i.p.v. binair
    groen/rood, zodat echte uitschieters in BEIDE richtingen er visueel
    uitspringen t.o.v. iets dat maar een beetje beweegt.

    Gebruikt een vierkantswortel-curve i.p.v. een lineaire -- bij
    lineair bewoog een klein percentage (bv. +2.6%) nauwelijks weg van
    amber, waardoor + en - moeilijk uit elkaar te houden waren op het
    oog. Met sqrt() beweegt de kleur SNEL weg van amber bij kleine
    percentages, en vlakt af richting de uiterste kleur -- meer
    contrast precies waar het toe doet, terwijl grote uitschieters nog
    steeds gewoon uitkomen op puur rood/groen.

    Gedeeld tussen Sector rotation en Themes (zelfde tegel-stijl).
    """
    clamped = max(-15.0, min(15.0, return_pct))
    red, amber, green = (229, 72, 77), (232, 169, 60), (31, 174, 150)
    if clamped >= 0:
        t = (clamped / 15.0) ** 0.5  # 0 = amber, 1 = puur groen
        start, end = amber, green
    else:
        t = ((-clamped) / 15.0) ** 0.5  # 0 = amber, 1 = puur rood
        start, end = amber, red
    r = round(start[0] + (end[0] - start[0]) * t)
    g = round(start[1] + (end[1] - start[1]) * t)
    b = round(start[2] + (end[2] - start[2]) * t)
    return r, g, b


ROTATION_ROCKET_THRESHOLD_PCT = 10  # vanaf dit rendement verschijnt het 🚀-icoontje


def _rotation_tile_html(rank, name, return_pct):
    r, g, b = _rotation_gradient_color(return_pct)
    accent_rgb = f"{r},{g},{b}"
    text_color = f"rgb({accent_rgb})"
    trend_arrow = "↗" if return_pct >= 0 else "↘"

    # Inline i.p.v. absoluut gepositioneerd (voorkomt dat 'ie over de
    # naam heen kan vallen als die naar een 2e regel wrapt), en geen
    # omlijning/achtergrond -- gewoon het kale icoontje naast het
    # rangnummer.
    rocket_span = " 🚀" if return_pct >= ROTATION_ROCKET_THRESHOLD_PCT else ""

    # BELANGRIJK: geen voorloop-spaties/newlines binnen deze HTML-string
    # -- Markdown interpreteert 4+ spaties inspringing aan het begin van
    # een regel als een CODE-BLOK, niet als HTML, wat tegels als rauwe
    # HTML-tekst zou tonen i.p.v. gerenderd.
    #
    # height:100% + flex-column: laat de tegel uitrekken tot de hoogte
    # van de langste tegel IN DEZELFDE RIJ -- lost op dat een 2-regelige
    # naam de rij-hoogte laat verschillen t.o.v. een 1-regelige naam
    # ernaast. white-space:nowrap op het percentage-blok voorkomt dat de
    # pijl en het percentage naar een 2e regel wrappen.
    return (
        f'<div style="height:100%; box-sizing:border-box; display:flex; flex-direction:column; '
        f'background: linear-gradient(135deg, rgba({accent_rgb},0.20), rgba({accent_rgb},0.02)); '
        f'border: 1px solid rgba({accent_rgb},0.45); border-radius: 12px; padding: 0.9rem 1rem;">'
        f'<div style="font-size:0.65rem; color:#5B6472; font-weight:700;">#{rank}{rocket_span}</div>'
        f'<div style="font-size:0.78rem; color:#8992A3; font-weight:600; line-height:1.3; min-height:2.2em; margin-top:2px;">{name}</div>'
        f'<div style="font-size:1.5rem; font-weight:800; color:{text_color}; margin-top:auto; padding-top:6px; white-space:nowrap;">{trend_arrow} {return_pct:+.1f}%</div>'
        f'</div>'
    )


def _render_rotation_tiles(items: list, name_key: str) -> None:
    """
    Rendert een responsieve tegel-grid voor rotatie-data (Sectors of
    Themes) -- 1 gedeelde renderer i.p.v. losse implementaties, zodat
    beide secties er altijd exact hetzelfde uitzien.

    items: lijst met dicts, elk met minstens 'return_pct' en name_key
    (bv. 'sector' of 'theme'). Verwacht al gesorteerd te zijn (bepaalt
    de rangnummers).
    """
    tiles_html = "".join(
        _rotation_tile_html(i + 1, item[name_key], item["return_pct"]) for i, item in enumerate(items)
    )
    # CSS-grid met auto-fill/minmax i.p.v. st.columns() -- dat laatste
    # houdt altijd hetzelfde aantal kolommen aan (wordt alleen smaller op
    # mobiel, niet minder kolommen), terwijl auto-fill echt herschikt naar
    # minder kolommen op een smal scherm -- de kern van 'mobiel-vriendelijk'.
    st.markdown(
        f'<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(140px, 1fr)); '
        f'gap:0.6rem; margin: 0.5rem 0 1rem 0;">{tiles_html}</div>',
        unsafe_allow_html=True,
    )


def _signal_card_html(ticker: str, primary_label: str, primary_value: str, primary_positive, secondary_stats: list, standout: bool = False) -> str:
    """
    Bouwt 1 signaal-kaart (Momentocrats/Snowballers/Rocket List) -- i.p.v.
    een brede st.dataframe met 13+ kolommen, die op mobiel dubbel-scrollen
    afdwingt (verticaal EN horizontaal). Toont de KERN-metric groot en
    gekleurd, en een paar secundaire stats compact eronder.

    primary_positive: True (groen), False (rood), of None (neutraal wit)
    secondary_stats: lijst van (label, al-geformatteerde waarde)-tuples
    standout: True voor een extra visueel accent (sterkere rand + gloed +
    ⭐-badge) bij écht opvallende signalen (bv. Momentocrats-score >= 8) --
    precies de handvol die de moeite waard zijn om verder te bekijken.
    """
    # Normaliseer naar een NATIVE Python True/False/None -- een waarde die
    # rechtstreeks uit een pandas-vergelijking komt (bv. row['x'] < 0, of
    # een boolean-kolom uit een CSV) is een numpy.bool_, GEEN Python bool.
    # 'numpy.bool_(True) is True' geeft dan ONTERECHT False terug (identity-
    # check faalt bij een ander type), waardoor de kleur hieronder altijd
    # op het neutrale wit zou blijven hangen i.p.v. groen/rood. Ook een
    # ontbrekende waarde (NaN, bv. bij earnings_beat dat niet bekend is)
    # moet expliciet None worden -- bool(nan) geeft anders ONTERECHT True
    # terug (elk niet-nul getal is 'truthy' in Python, NaN incluis).
    if primary_positive is not None and pd.isna(primary_positive):
        primary_positive = None
    elif primary_positive is not None:
        primary_positive = bool(primary_positive)

    if primary_positive is True:
        color = "#1FAE96"
        accent_rgb = "31,174,150"
    elif primary_positive is False:
        color = "#E5484D"
        accent_rgb = "229,72,77"
    else:
        color = "#EAEDF1"
        accent_rgb = "137,146,163"

    # 2x2-grid i.p.v. alles op 1 rij -- bij 4 stats naast elkaar in een
    # smalle tegel was er te weinig ruimte per label, waardoor woorden
    # midden doorbraken (bv. 'FLIP'/'PED'). white-space:nowrap op zowel
    # het label als de waarde voorkomt dat definitief.
    secondary_html = "".join(
        f'<div style="min-width:0;">'
        f'<div style="font-size:0.62rem; color:#8992A3; text-transform:uppercase; letter-spacing:0.03em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{label}</div>'
        f'<div style="font-size:0.82rem; font-weight:600; color:#EAEDF1; margin-top:2px; white-space:nowrap;">{value}</div>'
        f'</div>'
        for label, value in secondary_stats
    )

    star_badge = ' <span style="font-size:0.9rem;">⭐</span>' if standout else ""
    # Achtergrond nu een KLEUR-GETINTE gradient (groen/rood/grijs, afhankelijk
    # van primary_positive) i.p.v. altijd hetzelfde neutrale grijs -- geeft
    # meer visuele 'pop', consistent met de rest van de app (opt-in-banner,
    # rotatie-tegels). Standout-kaarten krijgen een STERKERE versie van
    # DEZELFDE kleur (niet altijd jade, ook bij een negatieve standout).
    if standout:
        border_style = f"1.5px solid rgba({accent_rgb},0.6)"
        box_shadow = f"box-shadow:0 0 16px rgba({accent_rgb},0.2); "
        background = f"background: linear-gradient(135deg, rgba({accent_rgb},0.20), rgba({accent_rgb},0.03)); "
    else:
        border_style = f"1px solid rgba({accent_rgb},0.3)"
        box_shadow = ""
        background = f"background: linear-gradient(135deg, rgba({accent_rgb},0.12), rgba({accent_rgb},0.02)); "

    # Geen voorloop-spaties/newlines -- zelfde reden als bij de rotatie-
    # tegels: Markdown zou dit anders als een code-blok interpreteren.
    return (
        f'<div style="height:100%; box-sizing:border-box; {background}'
        f'border:{border_style}; {box_shadow}border-radius:12px; padding:0.9rem 1rem; '
        f'display:flex; flex-direction:column;">'
        f'<div style="font-size:1.05rem; font-weight:800; color:#EAEDF1;">{ticker}{star_badge}</div>'
        f'<div style="font-size:1.5rem; font-weight:800; color:{color}; margin-top:4px; white-space:nowrap;">{primary_value}</div>'
        f'<div style="font-size:0.68rem; color:#8992A3; margin-top:1px;">{primary_label}</div>'
        f'<div style="display:grid; grid-template-columns:repeat(2, 1fr); gap:6px 10px; margin-top:auto; padding-top:8px; '
        f'border-top:1px solid rgba(137,146,163,0.15);">{secondary_html}</div>'
        f'</div>'
    )


def _render_signal_cards(cards_html: list) -> None:
    """Rendert een responsieve grid van signaal-kaarten (zelfde auto-fill/minmax-aanpak als rotatie-tegels)."""
    combined = "".join(cards_html)
    st.markdown(
        f'<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(190px, 1fr)); '
        f'gap:0.6rem; margin: 0.5rem 0 1rem 0;">{combined}</div>',
        unsafe_allow_html=True,
    )


def _icon_span(name: str, size_px: int = 18, color: str = "currentColor") -> str:
    """
    Geeft 1 icoon terug uit dezelfde, consistente lijn-icoon-bibliotheek
    als de zijbalk (Material Symbols) -- i.p.v. losse emoji, die overal
    net anders ogen (kleurrijk, verschillende stijlen door elkaar). Werkt
    overal waar unsafe_allow_html gebruikt wordt (dus ook buiten
    st.page_link, waar Streamlit's eigen :material/naam:-syntax beperkt
    tot is).
    """
    return (
        f'<span class="material-symbols-outlined" '
        f'style="font-size:{size_px}px; color:{color};">{name}</span>'
    )


def _hero_stat_tile_html(label: str, icon_name: str, ticker: str, pct: float, accent_rgb: str, color: str) -> str:
    """
    Fancy hero-tegel voor een enkele, uitgelichte stat (bv. Top gainer/
    loser, Best/Worst today) -- gradient + gloed + icoon-badge, i.p.v.
    een plat kleurblok. Gedeeld tussen 'Yesterday's biggest movers' en
    'Your Portfolio Today', zodat beide er consistent uitzien.

    'icon_name' is een Material Symbol-naam (bv. 'trending_up'), niet
    een rauwe emoji -- consistent met de zijbalk en de andere hero-
    tegels elders op de site.
    """
    return (
        f'<div style="background: linear-gradient(135deg, rgba({accent_rgb},0.20), rgba({accent_rgb},0.03)); '
        f'border: 1.5px solid rgba({accent_rgb},0.5); border-radius: 12px; '
        f'box-shadow: 0 0 14px rgba({accent_rgb},0.15); padding: 0.7rem 0.5rem; text-align:center;">'
        f'<div style="width:30px; height:30px; border-radius:50%; background:rgba({accent_rgb},0.18); '
        f'display:flex; align-items:center; justify-content:center; margin:0 auto;">{_icon_span(icon_name, size_px=16, color=color)}</div>'
        f'<div style="font-size:0.6rem; color:#8992A3; text-transform:uppercase; letter-spacing:0.8px; margin-top:6px;">{label}</div>'
        f'<div style="font-size:0.95rem; font-weight:800; color:#EAEDF1; margin-top:1px;">{ticker}</div>'
        f'<div style="font-size:1.25rem; font-weight:800; color:{color}; margin-top:1px;">{pct:+.1f}%</div>'
        f'</div>'
    )


def _radar_row_html(icon: str, text: str) -> str:
    """
    Rendert 1 compacte 'Today's radar'-gebeurtenis-regel -- i.p.v. losse
    st.markdown()-aanroepen per bullet (voelde als een lange, rommelige
    wand van gemengde emoji-bullets, vooral op mobiel). 'text' mag HTML
    bevatten (bv. <b>...</b> voor nadruk), wordt zo doorgegeven.
    """
    return (
        f'<div style="display:flex; align-items:flex-start; gap:0.6rem; padding:7px 0; '
        f'border-bottom:1px solid rgba(137,146,163,0.12);">'
        f'<span style="font-size:1rem; flex-shrink:0; line-height:1.4;">{icon}</span>'
        f'<span style="font-size:0.88rem; color:#EAEDF1; line-height:1.4;">{text}</span>'
        f'</div>'
    )


def _render_radar_rows(rows_html: list) -> None:
    """Rendert alle Today's radar-regels als 1 samenhangend blok i.p.v. losse st.markdown-aanroepen per regel."""
    if not rows_html:
        return
    combined = "".join(rows_html)
    st.markdown(f'<div>{combined}</div>', unsafe_allow_html=True)


def build_sector_rotation(region: str = "US", window_days: int = THEME_ROTATION_WINDOW_DAYS) -> list:
    """
    Rangschikt sectoren op trailing-rendement -- een simpel sector-rotatie-
    signaal (welke sectoren doen het momenteel relatief goed/slecht?).
    Sectoren waarvan de ETF geen data teruggeeft, worden gewoon overgeslagen
    (geen crash bij een enkele niet-beschikbare ticker).

    Gebruikt een EXACT 'N handelsdagen terug'-venster (i.p.v. yfinance's
    'period=1mo'-string) -- zodat dit getal exact overeenkomt met het
    laatste punt van build_sector_rotation_trend()'s grafiek (zelfde fix
    als bij build_theme_rotation()).
    """
    fetch_period = f"{window_days + 15}d"
    etfs = US_SECTOR_ETFS if region == "US" else EU_SECTOR_ETFS
    results = []
    for sector, ticker in etfs.items():
        try:
            hist = get_cached_ticker_history(ticker, period=fetch_period)
            if hist is None or hist.empty:
                continue
            # Zelfde soort probleem als eerder elders gevonden: de EERSTE of
            # LAATSTE rij kan een onvolledige koers (NaN) zijn (bv. een
            # 'vandaag'-bar die nog niet volledig is, vaker voorkomend bij
            # niet-Amerikaanse beurzen met andere handelstijden) -- pak de
            # eerste/laatste GELDIGE koers i.p.v. blindelings de rand-rijen,
            # anders wordt het rendement NaN (toont als 'None' in de tabel).
            valid_closes = hist["Close"].dropna()
            if len(valid_closes) > window_days:
                ret = (valid_closes.iloc[-1] / valid_closes.iloc[-1 - window_days] - 1) * 100
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
            st.caption(f"Sell trigger set: {' or '.join(trigger_parts)} -- you'll see this on Today once reached.")

        edit_col, delete_col = st.columns(2)
        with edit_col:
            if st.button("Edit", key=f"dd_edit_btn_{version_id}"):
                st.session_state[edit_key] = True
                st.rerun()
        with delete_col:
            if st.button("Delete", key=f"dd_delete_{version_id}"):
                database.delete_deep_dive(version_id, user_email)
                st.success("Version deleted.")
                st.rerun()
    else:
        edit_business = st.text_area("Business overview", value=version.get("business_overview") or "", key=f"dd_edit_business_{version_id}")
        edit_thesis = st.text_area("Investment thesis", value=version.get("investment_thesis") or "", key=f"dd_edit_thesis_{version_id}")
        edit_thesis_score = st.columns([1, 1])[0].slider(
            "How compelling is the thesis?", 1.0, 10.0, float(version.get("thesis_score") or 5), step=0.5, key=f"dd_edit_thesis_score_{version_id}"
        )
        edit_management = st.text_area("Management/CEO", value=version.get("management_assessment") or "", key=f"dd_edit_management_{version_id}")
        edit_management_score = st.columns([1, 1])[0].slider(
            "How much confidence in management?", 1.0, 10.0, float(version.get("management_score") or 5), step=0.5, key=f"dd_edit_management_score_{version_id}"
        )
        edit_bear = st.text_area("Bear case", value=version.get("bear_case") or "", key=f"dd_edit_bear_{version_id}")
        edit_bear_score = st.columns([1, 1])[0].slider(
            "How manageable are the risks?", 1.0, 10.0, float(version.get("bear_case_score") or 5), step=0.5, key=f"dd_edit_bear_score_{version_id}",
            help="Higher = the risks are limited/well understood, not 'the risks are severe'.",
        )
        edit_valuation = st.text_area("Valuation", value=version.get("valuation_view") or "", key=f"dd_edit_valuation_{version_id}")
        edit_valuation_score = st.columns([1, 1])[0].slider(
            "How attractive is the valuation?", 1.0, 10.0, float(version.get("valuation_score") or 5), step=0.5, key=f"dd_edit_valuation_score_{version_id}"
        )
        edit_interested_price = st.number_input(
            f"Interested from price ({ticker_currency_symbol.strip()})", min_value=0.0, step=0.01,
            value=float(version.get("interested_price") or 0.0), key=f"dd_edit_price_{version_id}",
        )
        edit_technical_analysis = st.text_area(
            "Technical analysis", value=version.get("technical_analysis") or "", key=f"dd_edit_ta_{version_id}"
        )
        edit_technical_analysis_score = st.columns([1, 1])[0].slider(
            "How favorable is the technical setup?", 1.0, 10.0, float(version.get("technical_analysis_score") or 5), step=0.5, key=f"dd_edit_ta_score_{version_id}"
        )
        edit_catalysts = st.text_area("Catalysts", value=version.get("catalysts") or "", key=f"dd_edit_catalysts_{version_id}")
        edit_catalysts_score = st.columns([1, 1])[0].slider(
            "How strong are the catalysts?", 1.0, 10.0, float(version.get("catalysts_score") or 5), step=0.5, key=f"dd_edit_catalysts_score_{version_id}"
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
            if st.button("Save changes", type="primary", key=f"dd_save_edit_{version_id}"):
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
                if st.button("Remove image", key=f"dd_img_delete_{img['id']}"):
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


def _guess_domain_from_name(name: str) -> str:
    """
    Gokt een domeinnaam op basis van de bedrijfsnaam -- terugval voor
    wanneer yfinance's 'website'-veld ontbreekt (een bekende, terugkerende
    onbetrouwbaarheid in yfinance's .info-dict, bevestigd in meerdere
    GitHub-issues over verdwijnende velden tussen versies). Simpele
    heuristiek: strip veelvoorkomende bedrijfssuffixen, haal spaties/
    leestekens weg, plak '.com' erachter. Niet perfect (werkt bv. niet
    voor crypto, die worden apart uitgesloten), maar beter dan helemaal
    geen logo.
    """
    if not name:
        return None
    suffixes = [
        ", Inc.", " Inc.", " Inc", ", Corporation", " Corporation", " Corp.",
        " Corp", ", Ltd.", " Ltd.", " Ltd", " PLC", " plc", " N.V.", " NV",
        " S.A.", " AG", " Co.", ", Co", " Company", " Holdings", " Holding",
        " Group", " Class A", " Class B",
    ]
    cleaned = name
    for suf in suffixes:
        cleaned = cleaned.replace(suf, "")
    cleaned = cleaned.strip().lower().replace(" ", "").replace(",", "").replace(".", "").replace("&", "")
    if not cleaned:
        return None
    return f"{cleaned}.com"


@st.cache_data(ttl=86400, show_spinner=False)
def get_company_logo_url(ticker: str, company_name: str = None) -> str:
    """
    Geeft een logo-URL terug via Google's eigen, gratis favicon-dienst --
    geen aanmelding/API-sleutel nodig, en betrouwbaarder dan een kleine,
    losse gratis-dienst (Clearbit's gratis logo-API, ooit de standaardkeuze
    hiervoor, is per december 2025 gestopt te bestaan). Gebaseerd op het
    bedrijfsdomein uit yfinance's 'website'-veld -- met een terugval op
    een domein-gok uit de bedrijfsnaam, want 'website' bleek in de
    praktijk regelmatig te ontbreken (bekende yfinance-onbetrouwbaarheid).
    Geeft None terug als er geen domein af te leiden is (bv. crypto).

    'company_name' is een OPTIONELE, AL-BEKENDE bedrijfsnaam (bv. uit een
    eigen database-record) -- gebruikt als extra terugval wanneer
    yfinance's .info HELEMAAL leeg/onbereikbaar is (niet alleen het
    'website'-veld, maar ook 'shortName'/'longName' zelf). yfinance's
    .info-endpoint is namelijk aanzienlijk flakier dan .history() (vaker
    leeg/rate-limited) -- dus voor plekken waar de naam toch al bekend
    is (zoals deep-dives), is dit een veel betrouwbaardere bron dan
    volledig op yfinance's .info te vertrouwen.

    BELANGRIJK: de gegokte logo-URL wordt hier VOORAF (server-kant)
    daadwerkelijk opgehaald en gecontroleerd, in plaats van te
    vertrouwen op een client-side onerror-fallback in de HTML -- die
    laatste werkt namelijk NIET in Streamlit, want unsafe_allow_html
    saniteert de HTML met DOMPurify, dat standaard ALLE inline
    event-handlers (onerror, onclick, etc.) verwijdert. Zonder deze
    server-kant-check zou een verkeerd gegokt domein een kapot-plaatje-
    icoontje tonen i.p.v. netjes terug te vallen.

    24-uur gecached (i.p.v. de standaard 5 minuten van get_cached_ticker_info
    zelf) -- een logo verandert vrijwel nooit, en deze functie wordt nu ook
    gebruikt in My Portfolio's tabel (die bij ELK paginabezoek rendert), dus
    een lange cache voorkomt dat het paginabezoek zelf traag wordt. De
    verificatie-aanroep zelf gebeurt daardoor ook maar 1x per ticker per dag.
    """
    def _verify_logo_url(url: str) -> bool:
        """
        Haalt de URL daadwerkelijk op en controleert of 'ie een bruikbare
        afbeelding oplevert. Google's favicon-dienst geeft bij een niet-
        bestaand domein vaak een heel klein, generiek 'globe'-icoontje
        terug (i.p.v. een fout) -- een te klein bestand duidt dus op een
        mislukte gok, geen echt logo.
        """
        try:
            response = requests.get(url, timeout=3)
            if response.status_code != 200:
                return False
            if len(response.content) < 300:
                return False
            return True
        except Exception:
            return False

    try:
        info = get_cached_ticker_info(ticker)
        website = info.get("website")
        if website:
            domain = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
            candidate_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=256"
            if _verify_logo_url(candidate_url):
                return candidate_url

        # Terugval: geen 'website'-veld (of niet geverifieerd) --
        # crypto-achtige tickers (geen bedrijf, dus geen zinvol domein te
        # gokken) slaan we bewust over.
        ticker_suffix = ticker.rsplit("-", 1)[-1].upper() if "-" in ticker else ""
        if ticker_suffix in ("EUR", "USD", "GBP", "USDT", "USDC"):
            return None

        # Naam ophalen: eerst proberen via yfinance, met de ZELF-BEKENDE
        # company_name als terugval als .info leeg is.
        name = info.get("shortName") or info.get("longName") or company_name
        if not name:
            return None

        # Meerdere domein-varianten proberen, niet slechts 1 gok -- de
        # VOLLEDIGE naam ('Grab Holdings Limited' -> 'grabholdings.com')
        # klopt lang niet altijd (echt: grab.com); het EERSTE WOORD
        # alleen ('grab.com') is vaak een betere gok voor bedrijven met
        # generieke, beschrijvende extra woorden in hun officiele naam
        # (Holdings/Health/Technologies/Clean/etc.). Volledige naam eerst
        # geprobeerd (specifieker, dus minder kans op een TOEVALLIGE
        # match met een ander, bestaand bedrijf), eerste-woord als
        # terugval.
        candidate_domains = []
        full_guess = _guess_domain_from_name(name)
        if full_guess:
            candidate_domains.append(full_guess)
        first_word = name.split()[0] if name.split() else None
        if first_word:
            first_word_guess = _guess_domain_from_name(first_word)
            if first_word_guess and first_word_guess not in candidate_domains:
                candidate_domains.append(first_word_guess)

        for guessed_domain in candidate_domains:
            candidate_url = f"https://www.google.com/s2/favicons?domain={guessed_domain}&sz=256"
            if _verify_logo_url(candidate_url):
                return candidate_url
        return None
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
    confirm_url = f"https://hestys.streamlit.app/confirm?token={confirmation_token}"
    unsubscribe_url = f"https://hestys.streamlit.app/unsubscribe?token={unsubscribe_token}"
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


def compute_day_change_pct(history: pd.DataFrame) -> float:
    """
    Berekent de dagverandering (%) op basis van de laatste 2 GELDIGE
    slotkoersen in een AL opgehaalde geschiedenis -- geen extra
    netwerk-aanroep nodig, want deze data wordt toch al opgehaald bij
    een portfolio-refresh (period='5d').
    """
    if history is None or history.empty:
        return None
    valid_closes = history["Close"].dropna()
    if len(valid_closes) < 2:
        return None
    latest = float(valid_closes.iloc[-1])
    previous = float(valid_closes.iloc[-2])
    if previous == 0:
        return None
    return (latest - previous) / previous * 100


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
        success_url=f"{app_url}/premium?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{app_url}/premium",
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
        return_url=f"{app_url}/premium",
    )
    return session


class _CurrentUser:
    """
    Uniforme 'huidige gebruiker'-representatie, ongeacht de inlogmethode
    (Google-OAuth via st.user, OF e-mail+wachtwoord via een eigen
    sessie-cookie). Heeft dezelfde 3 eigenschappen als st.user zelf
    (is_logged_in/email/name), zodat de rest van de site niet hoeft te
    weten HOE iemand precies is ingelogd.
    """
    def __init__(self, is_logged_in: bool, email, name):
        self.is_logged_in = is_logged_in
        self.email = email
        self.name = name


def get_current_user() -> "_CurrentUser":
    """
    Geeft de huidige gebruiker terug -- via Google (st.user, Streamlit's
    eigen OAuth-mechanisme) OF via e-mail+wachtwoord (een eigen sessie,
    bijgehouden in st.session_state en hersteld vanuit een cookie na een
    paginaverversing). Google krijgt voorrang als BEIDE ooit toevallig
    tegelijk actief zouden zijn (zou normaal nooit gebeuren).
    """
    if st.user.is_logged_in:
        return _CurrentUser(True, st.user.email, st.user.name)
    if st.session_state.get("password_auth_email"):
        return _CurrentUser(True, st.session_state["password_auth_email"], st.session_state.get("password_auth_name") or "")
    return _CurrentUser(False, None, None)


# --- Sessie herstellen vanuit een cookie (voor wachtwoord-login) -- lost
#     het probleem op dat een kale st.session_state een paginaverversing
#     niet overleeft (in tegenstelling tot Google-login, dat Streamlit's
#     eigen sessie-mechanisme gebruikt). Gebeurt VOOR get_current_user(),
#     zodat die de herstelde sessie meteen ziet. ---
from streamlit_cookies_controller import CookieController

_cookie_controller = CookieController(key="hestys_cookie_controller")

if "password_auth_email" not in st.session_state:
    _session_token = _cookie_controller.get("hestys_session_token")
    if _session_token:
        import database as _database_for_session_restore
        _restored = _database_for_session_restore.get_user_from_session_token(_session_token)
        if _restored:
            st.session_state["password_auth_email"] = _restored[0]
            st.session_state["password_auth_name"] = _restored[1]

# --- Navigatie: leest de '?view=...'-parameter uit de URL. Geen parameter
#     (zoals bij het eerste bezoek) betekent: nog geen tabblad gekozen. ---
# --- Navigatie: leest de '?view=...'-parameter uit de URL. Geen parameter
#     betekent: nog geen tabblad gekozen -- dan is de standaardpagina
#     afhankelijk van of je bent ingelogd. Niet ingelogd -> Discover (toont
#     meteen echte waarde aan een nieuwe bezoeker, geen account nodig).
#     Wel ingelogd -> Today (de gepersonaliseerde, dagelijkse pagina). ---
current_user = get_current_user()
_default_view = "today" if current_user.is_logged_in else "discover"
current_view = st.query_params.get("view", _default_view)


def _nav_class(view_name: str) -> str:
    return "nav-link active" if current_view == view_name else "nav-link"


def _nav_class_any(view_names: list) -> str:
    return "nav-link active" if current_view in view_names else "nav-link"


# Logo-icoontje (oplopende staafjes + pijl) als base64-PNG -- gegenereerd
# beeld, ingebed als data-URI zodat het werkt ongeacht hosting/deployment,
# geen los statisch bestand nodig.
_LOGO_ICON_B64 = "iVBORw0KGgoAAAANSUhEUgAAAIMAAACgCAYAAAAvpd/+AAAh7klEQVR4nO19e5gcZZnv7/2+mkxCIFyNimK7yMUNyC0cuZ2lEaKw6qJUUhMuCuEWsILcBTSETgdEFOWymEZYNaywKN2h1dVdYVcfmQVXWMgBPZDznHM4ap3DOUIuDEkmk2Sm6nvPH1993dU9fau+zPRk+vc8PGS6q6ur6/vVe3/fD+hhuoAACMdx5GRfSA8TCwIg4DgSWUcyM5Ggyb6mHiYIevGTSQtZR5IQqLD0e2GPA45N5DNnzV+6tK/aSXqYehBwQHAcOHCw9tzFASuOvm8BODSRzxwN4OMA/hLAewAkAIiNV6SOHdm48RUAAoAyH+qRoftBcCCwIUlYNpdTTpbTghRK1h5zMHPmEYnH75kH4CQAJwM4GEB/hfO94dnu0UT0NjMTUDxTjwzdBQJAcBxyHGCeM49XyVWq7KkHgA8l8pkjARwH4EMATgVwUIXzKRQXW0FLjB97trsQnBKgtIoebLXzl/QQC3rhk0kBAKlnnlGrpFCsmJHLIZcrHNefyGdOBHAUgA8DeD+A0wHsWeGcQcm5tRoo/86fASAMrB8nCHqSYeJQ8tSvPffJAMxgLnnqDwAwN5HPHAPgRACHQOv5eRXOF33qKy18+bECwAbPducR0eZyFWFO0kPnIJysQ6hs5AFa3B8K4IMA/hrAsQDei/ESm1FcfLPwcdbOD8/5I892z3OyWZkbGAjKD+qpic5C5QZyAHIAMAuzrCMT//C3x0Jb9ycCOAzAfhU+F6C48GbxWwkWGSnwGwDIRXRQ+UE9tBuplEA6rRL5zAkAPgdgL2gr/7AKR5unHigufjvXxZAK3oB7Evl4nstcSoOeZOgE1heMs/kAroq8E0AvQvSJJ7T21NeDCs//Enz8XjETEY0jAlDb6OihWeRyAQDybDfj2e6HAHwDwB+gF6UPE3/fGcBDAEbotNOqEq+nJjoJZiIhOPQY9k3kMzaA6wAcETkqQHyDMNZVACBvyY1n0daRp1kTcpzxCPQkQ2dBxMwskExaJGjIs93vebb7UQB/A+BpALugF4dQZYFahFFJf8LWkd+DyLxWET0ydB4Kg4M+KyY4jiRBI57t/tyz3bP+3+IbTwTwKIARdMZuML7sTwH8mZ9YJFEWW4iiR4aJAyOXCwwpmJnGxkZe8Wz3wj/b1x4H4DboeIA+tj0w6/s0AEIVl7L84B4mDoxcLiAiBiCdV7MzRjH631GUDEa0t/49+jybPNt9kYgYueoqAuiRYTIhUpzi3JEDKpHP/AxACpoQ7VoTE7F8DsAmVrcJ1JE4vTjD5IBSzEgTqUQ+cxeAT6MYMm7r9wD4CQDgtGcqBprKD+5hYkEpZgqJkAKwEu13L42K2OjZ7hFEtJGZ65KhJxkmFlEiZAB8AZ2JM5io43oAG5VSFNooNdGzGSYOlEylZEiE26GJ4KOzAadfAiAaGKhrL6CDF9FDKcjJZkVuYCBI5DN3A7gRnYs8GhWxzbPdj4DggSsnpsrRkwwTgAgRVqB1IjBqP+XmvU0ANlCdqGMUPTJ0FpRMpayQCF8BsAqtESGa8awGQ5ZfAdjBCxc1HNnskaGDSKZScjCd9hP5zPUAvorWbARDomHop76ahDDnz8b9gh4ZOgNysllDhJsBfAtFC78ZIvjhZ1/wbPckADeF5ykX/0ZyvOHZ7gskCMjlGg5t98jQflAylZKhargdwF1oTLxXQwAdAvhnz3ZPJyle9Wz3HwG8AU2Q6GIbcvwSwFb+0SKJBu0FoEeGtqNMNdwK/VQ3QwSFojR5yLPdRRA0wu4n+gFshokslqa+zXr+AgBhdS7Wd/bI0EbMf2hpX0iEL0GrhgDNqQZT2i4ArPBs90oStAOKCW8+ZciVj5zf2A8CwLBnu78BEWOwcakA9MjQLlAylbTWXfHwWCKfWQVd5mYWNC4RjJH5JgDHs907kqmUxSrsc8ghICHYs91nAfw3FCufzcL/FsCfnSeeiKUigB4Z2gHSqmHQT+Qz1wFYAf3ENqMaTLLqT57tftKz3bVIJa3BdNpHxDbgFStEeOyvzUuR938NQOVWr45tn/QikC3CyToyN5ALEvnMlQAeRPNxBCPyn/ds93wi/JFPTVoYHPQrHEsgMKy+IxNP3P8fAGZBkyH4vxfccJK/c8dL4Oq1jtXQkwzNg3RnUs5EFpslAqNIhB94tvtxEvRHZsgqRAAATqmUwNjYq9CeA8LvfNnfseOlMOoYu6ayR4YmMX/pUhNZvBbNRxaNTpcA7vds9yISYpgVC9RZzPRA2nzP/SiqiRcAIE7UMYoeGZpAMpWy1j388FioGu5Fc0SIfmaJZ7vXpjglWKlKwaTxyEExM3m2+zyKhuRjBMQKNEXRI0NMJFMpKxJHeBDNeQ1GLWwHMODZ7t8j68g0pWslocoNUg4bYrZDN3O+4dnuf1EVuqsbRc+AbByUTCWN13ATgK+jOYlgPIaXPPuapcDYy0hWNRQNBBGpsvb9wnUBmIXZc/fC9g1vxbiO8V/SyoenEcjJZkVIhCuhidBM0skQ4Zee7S4gGnsZ7373bAwOVrcPHEdCE0EC2KPCEQxgpFUiAD0yNAJKppIm13ALiqohTmTReAxmjM45JGgLL4LEW29tR2WxTkgmLeRyAZiPSuQzLybymW8CQCqVqjSRpWUp3yNDbUQDSrcA+BriJ53M8RLASs92bRKkPYZcVY+BnKwjMDjoJ/KZhYl85hnoQR4fBACsXFl+fL2Cl4bQI0MNaBshbVTD1xA/smhsihEAX/BsN51iFmFouZrHIEkQR+IXTwDYNzx+FADW5+IloBpFjwyVQdprGPQT+czVaM5rMDUImwCc69nud7THQNWfYt2LGbDiOYl8Zg10/IIAjIXfPQoA8xynXe13JeiVyo8HRSTCVdBBnbhegzEU/+jZ7tkAXkUyaWEgV91jcByJXC5gPefpRwCOR5FQ5qH1gc5Jhh4ZSkFO1hG5gZyRCPcjnkSIGopPe7a7lIj+Ny9aJJGrSgSR4hTSlA4S+czHoLuy34fKHVbbm/lRjaJHhiKImUFEQViPYNLQjdoIRvxbANZ4tnsFCRpjxTKc5FIJggSpNKWRyGduBXB7+LoZ4FmOjq5Xz2bQICfrCCJCIp/5OjQR4hiL0ZF8d3i2e0mBCNVyDI4jiaBY8QcS+UwWpUSoti4zGv9J8dEjQ6FmMRck8pkboYtN4wSUDGlGASz2bHcFOGU8hkpEIKR0/IAZhyfymV8CcFDsmq61Jh1dr+muJoy+9hP5zBdRlAiNBpTMsdsALPJs91+QzUrQQHR6axRGFfmJfOZsAGug50Ca89TDrgaOaRrTmQzkZLOUpoEgoq/Nk9kIEYyB94Jnu1cA+B0cR6LC5FUAWi08+WRARFaoir4IPfnNRDMbQawytriYrmSg+UvnW7mBgbFQItyOeMaiIcJTuiqJhnhRDUPRcSTWrg2YuT+RzzwC4FyUFrE2io7EFwymJRlCUT0Wuo9x6hGiHkPGs92rSYiAlZJVQsuErCMwkAsAHJPIZ74LPSjUxA/ixgs6mmWebmQwXgMn8pk7AHwFpTOaayFqS3zDs92bWU9brWYoChJCsTZMLwTwAIA5KMYhmkFHDcjp5E1EvYYvQxMhOrO5FgwRtgI4z7Pdm+cvXdoX1hpWEt2SiBQr1Z/IZx4A8PcoEqFrd4+bNpKBBHEYYl6CeKNzjH3wX72Bqy+F778Ix5HrHn64pHy9ABNWZn5vIp95HMBpKM1ctoKeZGgRdMhZZ/Wz4hmJfOYaAN9DMd5fr7XdiPRfebZ7KgXBi4Uag2o1CLlcgJl7JhP5zG+gidDO6SwdtRl2ezLMX7rUev2pp3aF6eD7Im/VIwKgSbPas91PkRDvMHP18vUUBAGcyGfOTzz+jX8G8BdozT6YcOzOZCBkHRlWMV8G4Mso3cOpGqJh6JWe7V6VYh5jpUTkvXHfxSuZGTgQwGro8rSutg8qYXclA6U4RdDG4sUAHkaxkbXWbzYL6ENHFNNhDYLpiAaqqAcSxNBbB5pG2Cl3b6eMCIsBcrKOCFPCd0JLhOjGXtVgiPC6t+TGZdg68i9IJa0wRtDI1wLgUehClKbL1ScTuxsZTD2CKV41qqGeAWc8ht95tvtpAG8gmbSQrlm+Xgn1JE+r6CjBppwoq4EoEdIA7kR9IpRXLZ9Ogt5AEvX6GKqcqu6Wgq2io7mJ3YYMESLcBj2uH6hNhGif47c9211Cgt5mxRKDiCsRdgvsDmSgSFv8tQDSqO81GIkRALjJs90vkhBbG2l43Z0x1ckQVQ3LANyD+jWLxlB8B8BCz3bvdrJZ2XDD626MqWxARkfwXg/gm+Z11CfCf3gD7jL4eAmOU3H31y5FR69zqpKBwCnK6cKUr6KYfdTvjYeZeSQBrPVs9xIi2sbOolrFqnFgvtuHdi2nJKaimtCtZ5RWYTd0veyjKUGTAH7o2e75JMQ25ppVy82iLW1uk4WpRoaojbAcuhu6VoWSMRQFgOs82z2fmf1IaLkiKjS2TgtMJTUR1iOk/ZAId6A+EST0CL2rPNt9EpwS4SYc1QxFU7DarYZkr9IJRWPRD7OPxn2s5jUYIrzo2e75AF5HKiVA6VqLLKWUARHhwA8cfvLihZ98+d57790R8zqjOYxOoK+D554SaoJSzBR6DXdBN6MClYkQNRQf8Wz3TCJ6XYeWqxMhmUxaUsogCIL3LFx47jceeOCep4469dR+AGA9FqeRy4z5s5rCaCdP3u1kICebFeFWPncAuBnVjUWjMgSABz3bvZSEGOLjuK9GaJlSqZQ1ODjoB0Fw/JKLL3/6bx+4/0vzDj+sf/mymz4IACtXrpw2o466WU1E4wirACxHddVgEk07ACzzbHdNilmkiQjrCjUI5VZ+oaFl5ux9Llix4tZHr7j8UpICwf/x3p4xY4bcGwDWr18/bcjQrZIhSoRvQY/grVY+VhixC+B0z3bXgFMiMgehkrsnLMtiItrjhJNO/bsn1+YevfbaqzAyMuyPjo5Kq28GpJTNxAs6bTN0tFimGyVD6D4OBGHn0fWo3PJWXqP4BQD/E8mkBUr7ZccVkEwmrWeffdb3fX/vCy689Hsrln9l4YEHvlttfOtNkkJaQgjNHr0PZFz4KN3PuiNSpfaO1s2j28gQlQhfhW6CraQaos0sP/ZsdzERjemupur2Qdjn4AM45svLVz557TVXH9xnkf/O0Nuyz+ojpRgAMQDyO9zx3I3oJjUhI0S4EzqyWEk1RGsU7/Fsd4CEGNMRxaqBJGFZkolIHX74UZf84qlfrbl1+U0Hq2CnP7x9m2VZRIZfzACB0MimoLsbukUyUOKiZF9uYGBnqBqMRChXDea1nQA+59nuk3W6mgAkLSmf830/2O+ypcsWXfi5Cx867tiPYPPGDUpKYVmCoL1HbWMKwQxi8v3RWR38vV2JbiCDUQ07E/nMfQCuQWXVYAzFP3gX3HABdux4HllHhtHCikWqyVRK/tuqVX4Q8IcuvuyKnyz/8s1H7rvvHH/z2xuEtCxB5SqdCESCwYzAx0wA2LBhw7TxJiabDORwVoTZx69DE6F8llHUUHzBs93PAniz3sAsKSUPptO+nDFr0be+ec+9Sy783Pt37RxWW7cMWX2WpTeBZYALTof+2ygMItWMVyBRtPinHIkm02YQ8x9aaoVEWInixJSo+2QWxALwXc92zyCiN+HU3ItBMjMFQTDrI8cd7/7wh49nl1625P3Dw1uCMT8Q0poR7gbMIRGKX0WkbQYAUAr9TfymKBk6BqdD550sMpDDWQr3dLobQApFiWCeKKMqGLo07XIStJ25+mRVx3FMfoHP/qyz5vvf/f7qT/31WWrTpg0Kuhm22uWgYDMQsVLAztFds9v5g9uEjha3TAYZtI1QLEwxe0NHnygjId6GHsEflqZVn6yazWZlLpcLgiA47raVtz/30IPfXnTowR8INm/cICzLEpWJUJrwZCaAQv6R6nkTHUY0jvA1ALegdHCFSTRZAF72bPcSAK8gmbRyAwO14gcgouA97/sLJ/PtB5Z/4hNnHL1921AwvG2LtKSFypP5Cx+HIYT2Jk16I+5zMvW5M5GSIUqEu6GJEHUfo6Xrj3u2mySiV+A4Ufug5PF2HEdaUjIRiY+f9enrHnv0keyZZy44+p23NwVBEEgh4qjv0sWU3RSBmSBMlGQgkoJDItyH8e5jdLPO6zzbvY8EocJAzeJ2fjq+EADY55LLl/18xfKbj99//73V0OaNLElKDj0FFmFMsSrGpy6YFYLuLG+Z8vMZyMk6ggMlQ9Vg3EcjEQwRhgFc4NnufXXmKAJ6Zxbed9/9z39kzWP/es837zpl9uxZ/e8MvSOEkFJFPIU4RGDmcN5TMy5BYYpLJ/XFlJ72Fh3B+20Ay1D0GqLxg1dD++DFCommEjiOI9euXRsc+uFjPn/3XXf+4JNnLcCGzRsCxSwsq49Yx5ObBINZEUAgSzRTSBKgSOApl6jqpGQQIRH6EvnMd6CJYBbfPD1m9/cziOjFBvZqwrx584iZMXfu3LNOPvlEHhp6exczS0GCquzh1DCMx6ElQ9fWQXYMnSIDkRSKiCgkwhUoqgaTaFIA7vRs1yFBG2pORamAvhlyw/D2YSKC1E90e6Rzu87TIUy5glhBUigO1N6JfOYhAItRJIJREZsBXO7Z7o9DQzF2j+PYqL+vZVngNqpoQwTmru2zm1KzowUJUhyo2Yl85scAPoZST8EC8Ipnu5cRsA6OM4NzuTE0c+8JXEw0GadkPDGIqOGnvaAm0F25/YlCO3+zHoKpeO9EPpNHkQgmqiOg8wunENE6nj+/D7ncKJq0vllFkpU1zhBH7Bckg77wZkTylB7W0S7JEO6tpN6TyGd+Dj0S1zztArpQ9XrPdr8DoxbWrWupJ1GG91xnGM2/WkNo8DIzg/2gmURVlAyd0O/henXGn2gHGWQ4P3nPCBHMXCMLwBvewNXnwfefQ9aRGMi1vWg0XMSWz0OFCoeuNSI72tTbqkgTIRHmlBFBQhPhGc92/wq+/1xYf1BtmGYTUOA25ZJKiERGq8Xl64QQKPySziSxWyGDJEGKlXpXIp/5GYAkdMdPX3je73u2+3Ei+hMwv6/mFr9NoKnSkyoo2BXh/zQ1uteE7FQ9Q7Nqwuy/uH8in3kKwHHQdYkzw/9f6NlujoSA7nheV3nOcgtoh0tZ1dNoSuNMyWl/JWiGDCJChH+EJsIuaCK84g1c7cL3fwtOCaZ0rY7nSUd1T4MAMfXK1lpFXFmo4wiKD0rkM/8E4GToxe6H3r4vSb7/2zC/UK1QNYqmXXrSgYbCSZopbK9kdDIzgYE+KUeaua6JQK5D3kTjC+EYG4H3SeQzPwVwQvjOLgDLw+37tjJq1ieWfLcQgsPq5uaewhaf3XLJQBS+RgxSsqMdz92IRskg6UkKWPEBoddwbPj6n7yLbl7g2e6dTtaRddLOBpRKpYQUQimliJkP7LaGFW1LqDizEAwtLXR4hkInUZ8MTsFYfFcin/kJgFPCd37l2e6Z2Lbt33VZWiNuoyOllJxOp1Wg1IcvXLI0f1v6rtf33HPPw/X73TM+hyyK6f0UJsROWVuj3s2XtJYCVnxYIp/5NYpEuNOz3QVE9D/qlK0XvkdKCSAXBEGw9+kLzrxy9YPffymz+v7PnnTiCbO2bdt2kD4sRvu7qZsGAFBbloBZ2wzMDMG6nmHu3LldJbU6iUpk0Ox2IIkoYOaPJvKZtQCOgK5WvsKz3eXhTatatm7OpcvXhQqCwOrfY48zb7l15fOZ1asfvOA8Z3YwNjo2MjIcAHJ27LXsQPFyMVFFgOwu1TURqORaMpxQIjAfErqP7wawLqxG+n2kra2q2+g4jszn80FO1zB+eOHABX93/Q3XHXX0R46Ys23LEG/e/CbedcBcklJKgPfTd36yW9nCUjkClIplMxh0ej5DR1GJDJLWImDmgxL5zC+gifBTz3aXEOEdPrV2WxuAPmYOwmLVmSed9FcrvuBe6f7N2WfvA6WweeMmJQQJy+oHQBDCAprc1pdIP836iTa1CMU8RdycBTMgdOctlNKJqgZ7LcNaO94FHXQLX5ta9kOpmkgmLQABWzgy3HDrIAC3eLa7mAS9w1zbPkilUkJIMUZEaq+99v3Uvfevzj366A++Yp/zmX22b9sSbN36DluWEIUsY3GhYt80ISRIRC+fIsQIX6lDhPL3i+QCgKaGdUxpFCWD3oLP3w+Ys9cTmV8A8LzF7tkYwyv1294hU6k1fen0xTsBnHz55e75i88dWHbSiR/FyMiwv3nzZmlZltYIKN7w4o2PDyEEisUtWgKMG9rUQGFL+TE6hQ34SjWTwp7SMGQQyOWCRD6zAHpf6N97tnsOAaM8f35fKPIr6UIrlfo1Vq063U+nL54xf/4pty698vIv2ed8Zo4lmYc2v8UQlmX19QHjRLYhQrOSVF8Oh9KY2yKUCXq6PINYxFRdU9/eFEilBDNzIp85Dnqrv9We7X7ayWYDBmRYhFJOBB04ktJPpz/mM/NpD3/3kTWP/cOjt5+32JkzunO7Gh7eStKyhCCBOv1tLYDDNeD4m0pH7Iqy11mTi2MakFPKPKgIC+k0KJ3mg4/8T0Kw+szrr637X0SE3MBA5SST40iZzwfpdJoBHH/OovO/dsN11xx9zNFHvWvHjuHgnaGNwrKkkMKCrnOtToRWOOL7CkoxILUnzOBx54tT8hZGHaGYCWBY1FTfxJSGhXDB//Dqiy8B2iUM3cFyIgghhFK5XBAAM5PJBVeee94FqxYttPfqswhDQxsDIkhdsQygMBoHqEYIaqkByXy2udSx8TRKbYbi061o6rqIzSLqWgoAyFUeu29JKf0gCPpnzp6z6IYbvnTThZ8//6iD3ncghoaGgp07AhGGGEuWRQ+/qLVQLYgGQY3Uw9aEIYQQAkop/TfCoFNXp7AddKIOMkqGqpPWAfhBEBx13ueXXL3koosu/c+nnIjhbVt406a3YFlSRpudY/n1mDxNG5UIJYQlYhCBWHXx6L9JSGGntHGJBZ+yD/3BY0/k7r/3nktPOP5Y9famTcHY6ChJKUnfx/GnMU2sBkYkx4kD1L5wEasnohLGG5HRwR2x+vl3C9QLrAgi4j6iMxacfvphKhjzt27ZIoQQUhTGF8mS05gbW77wFZ9CtEIIpWc2NvF5E7HUI/8EiGT4fwGACRxACG4qKjqVUZMMRxxxBAPAnrP6h7Zu26LATCIMHDFRpLqoSABg/MJXc+OKixk+hMnWfkw9lMc5zDVVCluHsZUuRWdKYhuqgVQgIQQJIg7Gm2vFXpno4psbXK4uyqGfxmYgmopeFhddWyzlJChcatDNWctJbKLZtmXr/lQoVyy6jLoGsXQxK4R3S4gRfV2I8SHkhiEAYNxYz4ZBZpBXIT7BYFaho0pgMZ1zEzXAllCNJH3GqwGu+G/zt2KGarIBQgFNuSLjJUG1CGRTKewpjcbIwKruUxK1E+rd8OIbZX8PNnI1NT7fyEca9T4C7nkTlcA+i0aaVso9CKD+zS85PoYByUrFaqSpUhY//jVCaDj0JrdUPkiIoJH7Xm4sTsgUFG6MEtVc3orn6+7pLR1DQ2pCSOk3qp/b0Q0dCxTPiKy70GzmM0w/A7KhH6yUkkA8e63cc6h+XHPS2Pg0rTzEFdVa86eb6qjt5BtvNuBAP38NehTVXMtKZWb62DC+E8OAtIR2cxtdvHJvp1pEFDAFM9PKZKBDDjlkRkOSIWpW137KK9zYyE2v9L7iybnxNfMa3OHx7S2j7RFIev3110drkyEUDUFg5q2217gyKeNOIiqRRKSAtrYh2fVsaDcU6lYAhwQkonBEf/NLV/vmx7fV9Hyv+sSMSqRGPB2tumJfzgRjElLYRhgJKX2gcVex2qK312VTsYy9Smqqche2/recdiGnOmRY/dprBAD+2Fh/IwtZqXmleuFphRPEylrGL0WqlFKPwmRRJ9w97hLUJMPc9TqFLaXcCZTq3HJUKlqplJwyMC+X3PgY3oSCgq5OK1ZDxoeosPAcErWbwwyTMeCr8J1KihpPS7lEqPV321CDmOXXZTC+8gqIdmJRGMDqfskwCTbDvFBNjPr+HkD1xaxVxFKvnqFZgujcBGratHHPHd2eIOjqOMMkSAZT6SRI6P7KJhY1br9jwxDh9dRZ70rqS19rtQ9q1Sa7Wk10Bg0ZkATS6aBYHc3VI3xVEceAVIXSFNRu1BnvTtZyk5sNj08sJnlccP3ytXiVyq2qZVUyrCPU/w1mVoUQNbuvut9m6AxqSoZloZqw+vp21atVLLcb6oErKfy4xS0o9VzqHWP+rQ3b6LUUXJvx1xQPu//2x4IEETVWgNp4YAoodE83ASEI5R5OrWBX5dJ9/V95kWzBZ42Pltk0mZg0K8mQoFlvgqQIp8BXDxJFpUY1Q7Ke+ptOmOgdb0tQXAhTldw4BKLDOup/Tw/10ZBkICoa7W01rsicT8SOIKqwo0qjevyjWl1mRYJw4YBpVs6g0RAZgiCwOKw1bOUpq/TZpsnF2q0sTG6p873VurxKLwZhTeX0lCQ11cRrJlHl+/3msamlnxuthC4sTiuSpqzfglC9uKapiu3ujDl11Dit+ZPXmwiklDtNpLbabWxUYpRWKZe6eLF7LQuV0bUjkQ0bigWjFt2qJjra2NOga0mqsGYtGmOlVj3GuYeNQkQvndtoJNL0NTgbS1SN+rMqdCk3/aVFddH0KSBk495EPOhzBkFX7lHVUTS38UebPIpWTkNtGh7eQxE1yfBM8Z/FTccjhmKlaSxxwAUDspUas/FdXC2LeebWLmmKoqHcRH//jOHi4Lbayaq4aHXhyj/eCjnNx4ioiRT21BdTDUUg+2fOHCGqLQliLwABrZbeG5uhXWqLOZR63Zu1nDzX0sQZtg9vO6B4f0SV/+JBc4HATfpwuqGKoLOpZohIYxjPP+N6NnUpUQQodlx0wqKcAwApZ15HrNWGJIOvAisIWDErFQS7RHHqSTlqBZ44YiMwgkAhCBQrxU3t0RAEzH4QMBFzEIwW6tXqpdJL3+fCdQEEpRSCYAb7/phqcncT81SYnftajVaYNKrZ1K2jU2sbTFSJ/n3221/sPWeW8MfGCv0F4xe+SojXwPw0BvwgwJy99uzbe+99AWBW3AsXluzff/8DiGi0TymASvcpKjNyS7OkxWxmGMpmgBXDDwLMmjWrb5999oEgirlhGTOA/QC8N+5vaQCGZP0AsD53REfURT0yaGaT+Ne77rrrMkE0g1kRmVxAGJY0fxPMjTeLQpGwZak3wgye0T+Dh7ZsfRN9e/wOY1uAwdNUvQqX9evXMwCM+Sq/Mn37GYp9MOsLEKQjkQp6caUIxwHD9HTqfAYpPU+KRNHuUKwQ+Ap9loXtIzt3SZr57wBw2mmnqcHBulU3zApEhI0Avge9J7gMf3R09HL50yMAmOGjMvI+Q+8pvgvAntASgQE8CwDzXnutI2oiDsPM09vOCxEAdjRxTkOxmW28ligUWhfJZnFV2d/lMPO7oxU2AGA2eekL/x15wjoT4WqUDGRZVkcugJkRBIFATP3KzNTX19fJa2rmplOKU7RK3t6ErWB0aI0jVqwQSKeBDmVO/j/2bXvcEP566wAAAABJRU5ErkJggg=="


# ============================================================
# PAGINA-FUNCTIES (stap A van de navigatie-herstructurering: elke
# pagina wordt een losse functie, ZONDER de routing zelf al te wijzigen
# -- dat komt in stap B. Voor nu wordt elke functie nog gewoon aangeroepen
# vanuit de bestaande if/elif-keten op basis van current_view.)
# ============================================================

def render_analyze():
    st.markdown("### Analyze")

    if not current_user.is_logged_in:
        st.markdown(
            '<div class="privacy-seal">&#128274; PRIVATE &middot; visible only to you</div>',
            unsafe_allow_html=True,
        )
        st.info("Log in via the menu to track your own positions and analyze your portfolio. No one else can see what you add.")
        st.stop()

    # Sub-navigatie via segmented_control i.p.v. HTML-links -- geen
    # volledige pagina-herlading meer bij het wisselen van tabblad. De
    # subview blijft leesbaar via de URL bij het EERSTE bezoek (bv. een
    # gedeelde link naar /analyze?subview=dividend), maar daarna neemt
    # de widget het zelf over via zijn eigen, key-gebaseerde sessie-status.
    _analyze_subview_map = {
        "Performance": "performance", "Portfolio Overview": "portfolio",
        "Dividend": "dividend", "Deep-dives": "deepdives",
    }
    _analyze_subview_reverse = {v: k for k, v in _analyze_subview_map.items()}
    _analyze_default_label = _analyze_subview_reverse.get(
        st.query_params.get("subview", "performance"), "Performance",
    )
    _analyze_selected_label = st.segmented_control(
        "Analyze section", options=list(_analyze_subview_map.keys()),
        selection_mode="single", default=_analyze_default_label,
        key="analyze_subnav", label_visibility="collapsed",
    )
    if _analyze_selected_label is None:
        _analyze_selected_label = "Performance"
    current_subview = _analyze_subview_map[_analyze_selected_label]

    if current_subview == "deepdives":
        import database

        user_email = current_user.email

        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, rgba(31,174,150,0.14), rgba(31,174,150,0.02));
                        border: 1px solid rgba(31,174,150,0.35); border-radius: 10px;
                        padding: 1rem 1.25rem; margin: 0.5rem 0 1rem 0;">
                <div style="color:#1FAE96; font-weight:700; font-size:0.75rem; letter-spacing:1.5px; text-transform:uppercase;">
                    {_icon_span("menu_book", size_px=14, color="#1FAE96")} Deep-dives
                </div>
                <div style="color:#8992A3; font-size:0.9rem; margin-top:6px; line-height:1.5;">
                    Log your own research per stock -- every time you update it, the previous
                    version stays saved, so you can later see exactly how your view has changed.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("Add a new deep-dive (or update)", expanded=False, icon=":material/add:", key="add_a_new_deep_dive_or_update_expander"):
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
            dd_thesis_score = st.columns([1, 1])[0].slider("How compelling is the thesis?", 1.0, 10.0, 5.0, step=0.5, key="dd_thesis_score")

            st.markdown("**Management/CEO** -- assess the management and the CEO")
            dd_management = st.text_area("Management/CEO", label_visibility="collapsed", key="dd_management", height=80)
            dd_management_score = st.columns([1, 1])[0].slider("How much confidence in management?", 1.0, 10.0, 5.0, step=0.5, key="dd_management_score")

            st.markdown("**Bear case / risks** -- what could go wrong")
            dd_bear = st.text_area("Bear case", label_visibility="collapsed", key="dd_bear", height=80)
            dd_bear_score = st.columns([1, 1])[0].slider(
                "How manageable are the risks?", 1.0, 10.0, 5.0, step=0.5, key="dd_bear_score",
                help="Higher = the risks are limited/well understood, not 'the risks are severe' -- keeps the scale consistent with the other sliders (higher is always more favorable).",
            )

            st.markdown("**Valuation** -- do you think the current price is reasonable, and why")
            dd_valuation = st.text_area("Valuation", label_visibility="collapsed", key="dd_valuation", height=80)
            dd_valuation_score = st.columns([1, 1])[0].slider("How attractive is the valuation?", 1.0, 10.0, 5.0, step=0.5, key="dd_valuation_score")
            dd_interested_price = st.number_input(
                f"Interested from price ({dd_currency_symbol.strip()}, optional)", min_value=0.0, step=0.01, key="dd_interested_price",
                help="If filled in, and your conclusion is 'Buy', we'll later check this automatically on Today.",
            )

            st.markdown("**Technical analysis** -- what does the chart say (trend, support/resistance, momentum) "
                        "-- separate from Valuation, which is about the price vs. the FUNDAMENTALS")
            dd_technical_analysis = st.text_area("Technical analysis", label_visibility="collapsed", key="dd_technical_analysis", height=80)
            dd_technical_analysis_score = st.columns([1, 1])[0].slider("How favorable is the technical setup?", 1.0, 10.0, 5.0, step=0.5, key="dd_technical_analysis_score")

            st.markdown("**Catalysts** -- what upcoming events could move the price")
            dd_catalysts = st.text_area("Catalysts", label_visibility="collapsed", key="dd_catalysts", height=80)
            dd_catalysts_score = st.columns([1, 1])[0].slider("How strong are the catalysts?", 1.0, 10.0, 5.0, step=0.5, key="dd_catalysts_score")

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
                            logo_url = get_company_logo_url(entry["ticker"], entry.get("naam"))
                            conclusion_emoji = conclusion_emoji_map.get(entry["conclusion"], "")
                            tile_overall_score = _compute_deep_dive_overall_score(entry)

                            # logo_url is nu server-kant al geverifieerd
                            # (get_company_logo_url), dus altijd bruikbaar
                            # als 'ie niet None is -- geen client-side
                            # onerror-fallback meer nodig.
                            logo_html = (
                                f'<img src="{logo_url}" width="56" height="56" '
                                f'style="border-radius:12px; object-fit:contain; background:#fff; padding:4px;" />'
                                if logo_url else
                                f'<div style="width:56px; height:56px; border-radius:12px; background:rgba(31,174,150,0.12); '
                                f'display:flex; align-items:center; justify-content:center;">{_icon_span("candlestick_chart", size_px=24, color="#1FAE96")}</div>'
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
                            with st.expander("View history", key=f"view_history_expander_{entry['ticker']}"):
                                history = database.get_deep_dives_for_ticker(user_email, entry["ticker"])
                                st.caption(f"{len(history)} version(s) logged, most recent first.")
                                for version in history:
                                    _render_deep_dive_version(version, user_email)

        st.divider()

    elif current_subview == "portfolio":
        import database

        user_email = current_user.email
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
        with st.expander("Concentration Risk", expanded=True, key="concentration_risk_expander", icon=":material/target:"):
            for finding in analyze_concentration(holdings, risk_profile["max_position_pct"]):
                st.markdown(f"- {finding}")

            total_value_check = sum(h.get("position_value") or 0 for h in holdings)
            if total_value_check > 0:
                largest_check = max(holdings, key=lambda h: h.get("position_value") or 0)
                largest_pct_check = (largest_check.get("position_value") or 0) / total_value_check * 100
                if largest_pct_check > risk_profile["max_position_pct"]:
                    st.caption("One way to gradually correct an overweight position without a big, "
                               "one-time move: adjust future contributions with the Smart DCA Assistant.")
                    st.page_link(premium_page, label="Buy smarter with DCA", icon=":material/auto_awesome:")

        # --- Sectoren -- nu met een taartdiagram i.p.v. alleen tekst ---
        # --- Portfolio-samenstelling: Sectors + Asset Type + Region samen,
        # in een compactere 2-koloms-layout i.p.v. elk een eigen, volle-
        # breedte sectie. Elke categorie toont nu ook de tickers erachter
        # (bv. welk ETF, welke positie telt als 'Future') i.p.v. alleen een
        # kaal percentage. ---
        with st.expander("Portfolio Composition", expanded=True, key="portfolio_composition_expander", icon=":material/pie_chart:"):
            sector_groups, type_groups, region_groups = {}, {}, {}
            for h in holdings:
                value = h.get("position_value") or 0
                info = infos.get(h["ticker"], {})

                sector = info.get("sector") or "Non-equity / Other"
                sector_groups.setdefault(sector, []).append((h["naam"], h["ticker"], value))

                raw_quote_type = info.get("quoteType")
                if raw_quote_type:
                    asset_type = raw_quote_type.title()
                else:
                    ticker_suffix = h["ticker"].rsplit("-", 1)[-1].upper() if "-" in h["ticker"] else ""
                    asset_type = "Cryptocurrency" if ticker_suffix in ("EUR", "USD", "GBP", "USDT", "USDC") else "Unknown"
                type_groups.setdefault(asset_type, []).append((h["naam"], h["ticker"], value))

                region = get_holding_region(h["ticker"], info)
                region_groups.setdefault(region, []).append((h["naam"], h["ticker"], value))

            total_value_for_breakdown = sum(h.get("position_value") or 0 for h in holdings)

            def _render_breakdown(title, groups):
                with st.container(border=True):
                    st.markdown(f"**{title}**")
                    chart_values = {cat: sum(v for _, _, v in items) for cat, items in groups.items()}
                    if chart_values:
                        fig = build_breakdown_pie_chart(list(chart_values.keys()), list(chart_values.values()))
                        # Unieke key nodig -- deze functie wordt 3x aangeroepen
                        # (Sectors/Asset Type/Region) en st.plotly_chart() zonder
                        # key kan dan met StreamlitDuplicateElementId crashen.
                        chart_key = "breakdown_chart_" + title.lower().replace(" ", "_")
                        st.plotly_chart(fig, key=chart_key)

            comp_col1, comp_col2 = st.columns(2)
            with comp_col1:
                _render_breakdown("Sectors", sector_groups)
            with comp_col2:
                _render_breakdown("Asset Type", type_groups)

            # Region krijgt dezelfde kolomstructuur (i.p.v. los, gecentreerd
            # over de volle breedte) -- staat zo netjes uitgelijnd onder
            # Sectors, consistent met de blokken hierboven.
            region_col1, region_col2 = st.columns(2)
            with region_col1:
                _render_breakdown("Region", region_groups)

            sector_values_check = {
                s: sum(v for _, _, v in items) for s, items in sector_groups.items() if s != "Non-equity / Other"
            }
            if sector_values_check and total_value_for_breakdown > 0:
                dominant_sector_pct = max(sector_values_check.values()) / total_value_for_breakdown * 100
                if dominant_sector_pct > risk_profile["max_sector_pct"]:
                    st.caption("Overweight in one sector? Steering future contributions toward other "
                               "sectors is often smoother than selling. The Smart DCA Assistant can help with the timing.")
                    st.page_link(premium_page, label="Buy smarter with DCA", icon=":material/auto_awesome:")

        # --- Risico ---
        with st.expander("Risk", key="risk_expander", icon=":material/balance:"):
            for finding in analyze_risk(holdings, infos):
                st.markdown(f"- {finding}", unsafe_allow_html=True)

            if is_premium:
                if len(holdings) >= 2:
                    with st.spinner("Building correlation matrix..."):
                        corr_chart = build_correlation_matrix_chart(holdings)
                    if corr_chart is not None:
                        st.plotly_chart(corr_chart, width="stretch")
                else:
                    st.caption("Add at least 2 positions to see a correlation matrix.")
            else:
                st.info("Upgrade to Premium for a correlation matrix (which positions move together?).", icon=":material/lock:")


    elif current_subview == "dividend":
        import database

        user_email = current_user.email
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

        with st.expander("Dividend", key="dividend_expander", icon=":material/payments:"):
            if is_premium:
                dividend_result = analyze_dividend(holdings, infos)
                for finding in dividend_result["findings"]:
                    st.markdown(f"- {finding}", unsafe_allow_html=True)
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
                st.info("Upgrade to Premium for your dividend income overview and upcoming ex-dividend dates.", icon=":material/lock:")


    else:
        import database

        user_email = current_user.email
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
        with st.expander("Performance", expanded=True, key="performance_expander", icon=":material/monitoring:"):
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
                refresh_clicked = st.button("Refresh", key="perf_refresh_btn")

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
                    st.caption(
                        f"{_icon_span('warning', size_px=13, color='#8992A3')} Couldn't fetch a current price for: {', '.join(excluded_no_price)} -- "
                        f"excluded from the totals below until that's available again.",
                        unsafe_allow_html=True,
                    )

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



def render_portfolio():
    if not current_user.is_logged_in:
        st.markdown(
            '<div class="privacy-seal">&#128274; PRIVATE &middot; visible only to you</div>',
            unsafe_allow_html=True,
        )
        st.info("Log in via the menu to track your own positions. No one else can see what you add.")
        st.stop()

    import database
    from portfolio_watch import check_holding

    user_email = current_user.email
    st.markdown(
        '<div class="privacy-seal">&#128274; PRIVATE &middot; visible only to you</div>',
        unsafe_allow_html=True,
    )
    st.subheader(f"Welcome, {current_user.name}")

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
            # 'Display currency' klein en opzij i.p.v. een grote, losstaande
            # selectbox bovenaan -- het is een instelling, geen hoofdcontent,
            # en hoorde niet als eerste, meest prominente ding in beeld te
            # komen.
            header_col1, header_col2 = st.columns([3, 1])
            with header_col1:
                st.markdown("**Overview**")
            with header_col2:
                display_currency = st.selectbox(
                    "Display currency", ["EUR", "USD"], key="display_currency",
                    label_visibility="collapsed", help="Display currency",
                )

            total_value = sum(h.get("position_value") or 0 for h in holdings)
            stored_currency = next((h.get("value_currency") for h in holdings if h.get("value_currency")), None)
            currency_symbol = "€" if display_currency == "EUR" else "$"
            cash_value = database.get_cash_value(user_email)

            # Total en Cash nu op aparte, eigen regels i.p.v. samengeperst op
            # 1 regel met een '|'-scheidingsteken -- dat brak op mobiel
            # lelijk af naar een 2e regel.
            if total_value > 0 and stored_currency == display_currency:
                st.markdown(
                    f'<div style="font-size:0.68rem; color:#8992A3; text-transform:uppercase; letter-spacing:1px;">Total portfolio value</div>'
                    f'<div style="font-size:1.9rem; font-weight:800; color:#EAEDF1; margin-top:2px;">{currency_symbol}{total_value:,.0f}</div>'
                    f'<div style="font-size:0.85rem; color:#8992A3; margin-top:4px;">Cash: €{cash_value:,.0f}</div>',
                    unsafe_allow_html=True,
                )
            elif total_value > 0:
                st.warning(f"Values currently shown are in {stored_currency}, not {display_currency}. Click 'Update portfolio value' to convert.")
                st.markdown(
                    f'<div style="font-size:0.68rem; color:#8992A3; text-transform:uppercase; letter-spacing:1px;">Total portfolio value ({stored_currency})</div>'
                    f'<div style="font-size:1.9rem; font-weight:800; color:#EAEDF1; margin-top:2px;">{"€" if stored_currency == "EUR" else "$"}{total_value:,.0f}</div>'
                    f'<div style="font-size:0.85rem; color:#8992A3; margin-top:4px;">Cash: €{cash_value:,.0f}</div>',
                    unsafe_allow_html=True,
                )
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

            def _pct_of_portfolio(holding):
                if total_value <= 0:
                    return 0.0
                value = holding.get("position_value") or 0
                return value / total_value * 100

            # Tabel i.p.v. dikke kaarten -- veel sneller scanbaar bij meerdere
            # posities. st.dataframe handelt responsief gedrag zelf al netjes
            # af (geen geforceerd horizontaal scrollen zoals een losse HTML-
            # tabel zou geven), dus het mobiel-probleem dat de kaarten-aanpak
            # destijds oploste speelt hier niet opnieuw. GEEN logo-kolom (de
            # logo-gok-terugval faalt te vaak voor crypto/kleine tickers, en
            # het oogde sowieso niet strak) -- Ticker (bold, kort) + Name
            # (secundair) geven al genoeg houvast, net als in het aangereikte
            # voorbeeld. Alle kolommen expliciet smal, voor een dichte,
            # strakke tabel i.p.v. de brede standaard-kolombreedtes. Een
            # voortgangsbalk voor het portfolio-aandeel via column_config
            # geeft een modern, "fintech-dashboard"-gevoel -- pandas Styler
            # (voor kleur op dag%) kan HELAAS niet gecombineerd worden met
            # column_config (een bekende Streamlit-beperking), dus dag% staat
            # als gewoon getal met +/- i.p.v. rood/groen gekleurd.
            table_rows = [
                {
                    "Ticker": h["ticker"],
                    "Name": h["naam"],
                    "Shares": h.get("shares") or 0.0,
                    "Price": _format_price(h),
                    "Day %": h.get("day_change_pct") if h.get("day_change_pct") is not None else 0.0,
                    "Value": _format_value(h),
                    "% of Portfolio": round(_pct_of_portfolio(h), 1),
                }
                for h in holdings
            ]
            df_positions = pd.DataFrame(table_rows)
            if not df_positions.empty:
                df_positions = df_positions.sort_values("% of Portfolio", ascending=False)

            st.dataframe(
                df_positions,
                hide_index=True,
                width="stretch",
                column_config={
                    "Ticker": st.column_config.TextColumn("Ticker", width="small"),
                    "Name": st.column_config.TextColumn("Name", width="small"),
                    "Shares": st.column_config.NumberColumn("Shares", format="%.3f", width="small"),
                    "Price": st.column_config.TextColumn("Price", width="small"),
                    "Day %": st.column_config.NumberColumn("Day %", format="%+.1f%%", width="small"),
                    "Value": st.column_config.TextColumn("Value", width="small"),
                    "% of Portfolio": st.column_config.ProgressColumn(
                        "% of Portfolio", format="%.1f%%", min_value=0, max_value=100, width="small",
                    ),
                },
            )

            # --- Positie-detail: transacties + rendement + mini-koersgrafiek ---
            position_options = {f"{h['naam']} ({h['ticker']})": h for h in holdings}
            selected_position_label = st.selectbox(
                "View position details", ["-- Select a position --"] + list(position_options.keys()),
                key="portfolio_position_detail_select",
            )
            if selected_position_label != "-- Select a position --":
                selected_holding = position_options[selected_position_label]
                st.markdown(f"**{selected_holding['naam']} ({selected_holding['ticker']})**")
                detail_col1, detail_col2 = st.columns(2, gap="medium")

                with detail_col1:
                    with st.container(border=True):
                        transactions = database.get_transactions_for_holding(user_email, selected_holding["id"])
                        if transactions:
                            perf = compute_holding_performance(
                                transactions,
                                current_price=(selected_holding.get("position_value") or 0) / selected_holding["shares"]
                                if selected_holding.get("shares") else None,
                            )
                            if perf and perf.get("total_return_pct") is not None:
                                pct = perf["total_return_pct"]
                                color_emoji = "🟢" if pct >= 0 else "🔴"
                                st.markdown(f"{color_emoji} **Return: {pct:+.1f}%** (€{perf['total_pnl']:+,.2f})")
                            sorted_transactions = sorted(transactions, key=lambda t: t["transaction_date"], reverse=True)

                            DEFAULT_TRANSACTIONS_SHOWN = 5
                            show_all_transactions = True
                            if len(sorted_transactions) > DEFAULT_TRANSACTIONS_SHOWN:
                                st.caption(f"{len(sorted_transactions)} transactions total")
                                show_all_transactions = st.checkbox(
                                    f"Show all {len(sorted_transactions)} (most recent {DEFAULT_TRANSACTIONS_SHOWN} shown by default)",
                                    key=f"show_all_tx_{selected_holding['id']}",
                                )
                            else:
                                st.caption("Transactions (most recent first)")

                            transactions_to_show = (
                                sorted_transactions if show_all_transactions
                                else sorted_transactions[:DEFAULT_TRANSACTIONS_SHOWN]
                            )
                            for t in transactions_to_show:
                                type_emoji = "🟢" if t["transaction_type"] == "buy" else "🔴"
                                type_label = "Buy" if t["transaction_type"] == "buy" else "Sell"
                                st.markdown(
                                    f"- {type_emoji} {type_label}: {t['shares']:g} @ €{t['price']:,.2f} "
                                    f"*({t['transaction_date']})*"
                                )
                        else:
                            st.caption("No transactions logged for this position yet -- log one under 'Manage' below.")

                with detail_col2:
                    with st.container(border=True):
                        st.caption("Price -- last 6 months")
                        with st.spinner("Loading chart..."):
                            mini_hist = get_cached_ticker_history(selected_holding["ticker"], period="6mo")
                        if mini_hist is not None and not mini_hist.empty:
                            valid_mini_closes = mini_hist["Close"].dropna()
                            if len(valid_mini_closes) >= 2:
                                # De Y-as strak om de DAADWERKELIJKE prijsrange laten
                                # aansluiten (i.p.v. Plotly's standaard, ruimere
                                # marge) -- laat veel meer 'reliëf' in de koers zien,
                                # zodat verschillen tussen prijsniveaus beter opvallen.
                                y_min = float(valid_mini_closes.min())
                                y_max = float(valid_mini_closes.max())
                                y_padding = (y_max - y_min) * 0.05 or y_max * 0.02
                                mini_fig = go.Figure()
                                mini_fig.add_trace(go.Scatter(
                                    x=valid_mini_closes.index.strftime("%Y-%m-%d").tolist(),
                                    y=valid_mini_closes.tolist(),
                                    mode="lines",
                                    line=dict(color="#1FAE96", width=2),
                                    fill="tozeroy",
                                    fillcolor="rgba(31,174,150,0.10)",
                                    hovertemplate="%{x}: %{y:,.2f}<extra></extra>",
                                ))
                                mini_fig.update_layout(
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    plot_bgcolor="rgba(0,0,0,0)",
                                    font=dict(family="Inter, sans-serif", color="#EAEDF1", size=10),
                                    margin=dict(t=10, b=10, l=10, r=10),
                                    height=220,
                                    showlegend=False,
                                    xaxis=dict(gridcolor="rgba(137,146,163,0.15)"),
                                    yaxis=dict(
                                        gridcolor="rgba(137,146,163,0.15)",
                                        range=[y_min - y_padding, y_max + y_padding],
                                    ),
                                )
                                st.plotly_chart(mini_fig)
                            else:
                                st.caption("Not enough price data to show a chart.")
                        else:
                            st.caption("No price data available right now.")

    # ============================================================
    # 3. MANAGE
    # ============================================================
    with st.container(border=True):
        st.markdown("**Manage**")

        # --- Import from a broker -- bulk-importeren i.p.v. 1-voor-1 loggen ---
        with st.expander("Import from a broker", expanded=False, key="import_from_a_broker_expander"):
            st.caption("Currently supports DEGIRO. Upload your broker's 'Transactions' export "
                       "(CSV) to import your full buy/sell history in one go, instead of "
                       "logging each one by hand.")
            # Defensief: hasattr + try/except, zodat een eventueel niet
            # (nog) correct doorgekomen database.py-update deze SECTIE
            # laat degraderen (gewoon geen 'laatst geimporteerd'-regel
            # tonen) i.p.v. de HELE pagina te laten crashen.
            if hasattr(database, "get_last_csv_import"):
                try:
                    last_csv_import = database.get_last_csv_import(user_email)
                except Exception:
                    last_csv_import = None
                if last_csv_import:
                    import_dt = datetime.fromisoformat(last_csv_import["timestamp"])
                    filename_txt = f" ('{last_csv_import['filename']}')" if last_csv_import.get("filename") else ""
                    st.caption(f"Last CSV import: {import_dt.strftime('%b %d, %Y at %H:%M')}{filename_txt}")
            st.caption("Using a different broker?")
            st.page_link(support_page, label="Go to Support")
            degiro_file = st.file_uploader("Transactions CSV", type=["csv"], key="degiro_upload")

            already_imported = st.session_state.get("degiro_imported_filenames", set())

            if degiro_file is not None and degiro_file.name in already_imported:
                st.success(f"'{degiro_file.name}' was already imported.", icon=":material/check_circle:")
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
                    st.warning(
                        f"**{len(unmatched_keys)} security/securities need your attention** "
                        f"-- no ticker could be auto-matched. Fill these in manually below, "
                        f"or they'll be skipped:\n\n{unmatched_lines}",
                        icon=":material/warning:",
                    )

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
                        prefix = f"{_icon_span('warning', size_px=13, color='#E5484D')} " if key in unmatched_keys else ""
                        st.caption(f"{prefix}{group['product']} ({len(group['transactions'])} transactions)", unsafe_allow_html=True)
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
                        status_text.markdown(f"**Importing {group['product']}...** ({i + 1} of {len(to_import)})")

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
                    if hasattr(database, "set_last_csv_import"):
                        try:
                            database.set_last_csv_import(user_email, datetime.now().isoformat(), degiro_file.name)
                        except Exception:
                            pass  # het loggen van dit tijdstip mag de daadwerkelijke import nooit blokkeren
                    for state_key in ["degiro_parsed_filename", "degiro_grouped", "degiro_skipped",
                                       "degiro_ticker_matches", "degiro_ticker_candidates"]:
                        st.session_state.pop(state_key, None)
                    st.rerun()

        # --- Log a transaction (werkt ook zonder bestaande posities -- een
        # nieuwe positie kan direct via een eerste 'Log a buy' worden
        # aangemaakt) ---
        with st.expander("Log a transaction", expanded=False, key="log_a_transaction_expander"):
            st.caption("Log your actual buys and sells to see your real return under Analyze. "
                       "Optional -- positions without transactions logged just won't show a return.")

            position_mode_options = (
                ["Existing position", "New position"] if holdings else ["New position"]
            )
            tx_position_mode = st.segmented_control(
                "Position", options=position_mode_options, selection_mode="single",
                default=position_mode_options[0], key="tx_position_mode", label_visibility="collapsed",
            )
            if tx_position_mode is None:
                tx_position_mode = position_mode_options[0]

            tx_holding = None
            new_position_symbol = None
            new_position_name = None

            if tx_position_mode == "Existing position":
                tx_holding_options = {f"{h['naam']} ({h['ticker']})": h for h in holdings}
                tx_label = st.selectbox(
                    "Position", list(tx_holding_options.keys()), key="tx_select", label_visibility="collapsed",
                )
                tx_holding = tx_holding_options[tx_label]
                tx_type = st.segmented_control(
                    "Type", options=["Buy", "Sell"], selection_mode="single",
                    default="Buy", key="tx_type_radio",
                )
                if tx_type is None:
                    tx_type = "Buy"
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

            trow1_col1, trow1_col2 = st.columns(2)
            with trow1_col1:
                tx_shares = st.number_input("Shares", min_value=0.0, step=1.0, key="tx_shares_input")
            with trow1_col2:
                tx_price = st.number_input("Price per share", min_value=0.0, step=0.01, key="tx_price_input")
            trow2_col1, trow2_col2 = st.columns(2)
            with trow2_col1:
                tx_fee = st.number_input("Fee paid", min_value=0.0, step=0.01, value=0.0, key="tx_fee_input")
            with trow2_col2:
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
                                if st.button("✕", key=f"delete_tx_{t['id']}", help="Delete this transaction"):
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
    with st.expander("Watchlist", expanded=False, key="watchlist_expander"):
        st.caption("Track tickers you don't own yet -- they'll show up with personalized "
                   "signals and news on the Today page.")

        watchlist_items = database.get_user_holdings(user_email, is_watchlist=True)

        if watchlist_items:
            # Pills i.p.v. een tabel -- simpel genoeg (alleen naam+ticker) om
            # geen kaart-grid nodig te hebben, maar wel consistent met de
            # rest van de (inmiddels tegel-gebaseerde) pagina.
            pills_html = "".join(
                f'<div style="display:inline-flex; align-items:center; gap:0.4rem; '
                f'background:rgba(137,146,163,0.08); border:1px solid rgba(137,146,163,0.25); '
                f'border-radius:20px; padding:0.4rem 0.8rem;">'
                f'<span style="color:#EAEDF1; font-weight:600; font-size:0.85rem;">{w["naam"]}</span>'
                f'<span style="color:#1FAE96; font-family:\'IBM Plex Mono\', monospace; font-size:0.75rem;">{w["ticker"]}</span>'
                f'</div>'
                for w in watchlist_items
            )
            st.markdown(
                f'<div style="display:flex; flex-wrap:wrap; gap:0.5rem; margin-bottom:0.75rem;">{pills_html}</div>',
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




def render_discover():
    if not current_user.is_logged_in:
        # --- Hero-sectie: 1 gerichte, heldere binnenkomer voor nieuwe
        # bezoekers, vóór alle navigatie/content -- i.p.v. meteen met
        # tabbladen te beginnen. Zelfde HTML-op-1-regel-aanpak als de
        # thema-tegels (voorkomt dat Markdown het als code-blok
        # interpreteert door voorloop-spaties/newlines). ---
        hero_points = [
            ("search", "Discover new ideas", "signals, themes, trends"),
            ("bar_chart", "Analyze your own portfolio", "performance, risk, allocation"),
            ("mail", "Tailored daily & weekly updates", "matched to your investing style"),
            ("trending_up", "Expanding every week", "new signals, always improving"),
        ]
        # 2x2-grid i.p.v. flex-wrap (dat gaf op brede schermen 4 platte,
        # dunne vakjes op 1 rij -- saai). Een icoon-badge (gekleurde
        # cirkel) met dezelfde Material Symbol-lijniconen als de zijbalk
        # (i.p.v. losse emoji, die te speels oogden en niet aansloten
        # bij de rest van de site) geeft meer visueel gewicht.
        hero_points_html = "".join(
            f'<div style="background:rgba(31,174,150,0.08); border:1px solid rgba(31,174,150,0.25); '
            f'border-radius:12px; padding:1rem 1.1rem;">'
            f'<div style="width:36px; height:36px; border-radius:50%; background:rgba(31,174,150,0.18); '
            f'display:flex; align-items:center; justify-content:center;">{_icon_span(icon_name, size_px=18, color="#1FAE96")}</div>'
            f'<div style="color:#EAEDF1; font-size:0.88rem; font-weight:700; margin-top:9px; line-height:1.3;">{title}</div>'
            f'<div style="color:#8992A3; font-size:0.75rem; margin-top:3px; line-height:1.35;">{sub}</div>'
            f'</div>'
            for icon_name, title, sub in hero_points
        )
        st.markdown(
            '<div style="text-align:center; padding: 1.5rem 0.5rem 1rem 0.5rem;">'
            '<div style="display:inline-block; background:rgba(31,174,150,0.12); border:1px solid rgba(31,174,150,0.4); '
            'border-radius:20px; padding:5px 14px; color:#1FAE96; font-size:0.8rem; font-weight:600;">'
            'Free &mdash; no credit card needed</div>'
            '<h1 class="hero-headline" style="font-size:2.2rem; margin:0.9rem 0 0 0; line-height:1.25; color:#EAEDF1;">'
            'Your Investing Edge,<br/><span style="color:#1FAE96;">Built Around You</span></h1>'
            '<div style="max-width:520px; margin:0 auto;">'
            f'<div style="display:grid; grid-template-columns:repeat(2, 1fr); gap:0.7rem; margin-top:1.5rem;">{hero_points_html}</div>'
            '</div>'
            '<div style="margin-top:1.75rem; display:flex; gap:0.75rem; justify-content:center; flex-wrap:wrap;">'
            '<a href="#signup" style="background:#1FAE96; color:#0B1210; font-weight:700; font-size:0.95rem; '
            'padding:0.75rem 1.5rem; border-radius:10px; text-decoration:none; display:inline-block;">Start free, in seconds &rarr;</a>'
            '<a href="#signals" style="background:transparent; color:#EAEDF1; font-weight:600; font-size:0.95rem; '
            'padding:0.75rem 1.5rem; border-radius:10px; text-decoration:none; display:inline-block; '
            'border:1px solid rgba(234,237,241,0.3);">Browse today\'s signals</a>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown("### Discover")

    _discover_subview_map = {
        "Discover": "discover", "Sectors & Themes": "sectors_themes",
        "Earnings Surprises": "earnings_surprises",
    }
    _discover_subview_reverse = {v: k for k, v in _discover_subview_map.items()}
    _discover_default_label = _discover_subview_reverse.get(
        st.query_params.get("subview", "discover"), "Discover",
    )
    _discover_selected_label = st.segmented_control(
        "Discover section", options=list(_discover_subview_map.keys()),
        selection_mode="single", default=_discover_default_label,
        key="discover_subnav", label_visibility="collapsed",
    )
    if _discover_selected_label is None:
        _discover_selected_label = "Discover"
    current_discover_subview = _discover_subview_map[_discover_selected_label]

    if current_discover_subview == "sectors_themes":
        # --- Sector rotation (nieuw) ---
        with st.expander("Sector rotation", key="sector_rotation_expander", icon=":material/sync:"):
            st.caption("Which sectors are relatively strong or weak right now (1-month trailing).")
            region = st.segmented_control(
                "Region", options=["US", "EU"], selection_mode="single",
                default="US", key="sector_region", label_visibility="collapsed",
            )
            if region is None:
                region = "US"
            with st.spinner("Checking sector performance..."):
                rotation = build_sector_rotation(region=region)
            if rotation:
                _render_rotation_tiles(rotation, "sector")
            else:
                st.caption("No sector data available right now.")

            st.markdown("**Trend**")
            st.caption("A line crossing zero is a rotation signal.")
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
        with st.expander("Themes", key="themes_expander", icon=":material/lightbulb:"):
            st.caption("How popular investing themes are doing right now (1-month trailing).")
            with st.spinner("Checking theme performance..."):
                theme_rotation = build_theme_rotation()
            if theme_rotation:
                _render_rotation_tiles(theme_rotation, "theme")
            else:
                st.caption("No theme data available right now.")

            st.markdown("**Trend**")
            st.caption("A line crossing zero is a rotation signal.")
            with st.spinner("Building trend chart..."):
                theme_trend = build_theme_rotation_trend()
            if theme_trend:
                all_trend_themes = list(theme_trend.keys())
                # Nu er 11 thema's zijn (was 5), standaard de top-5 op basis
                # van het HUIDIGE (laatste) rendement tonen -- zelfde aanpak
                # als bij Sectors, voorkomt dat de grafiek meteen met 11
                # lijnen chaotisch oogt.
                default_themes = sorted(
                    all_trend_themes, key=lambda t: theme_trend[t]["values"][-1], reverse=True
                )[:5]
                selected_themes = st.multiselect(
                    "Themes to compare", all_trend_themes, default=default_themes, key="theme_trend_selection",
                )
                if selected_themes:
                    theme_fig = go.Figure()
                    theme_palette = [
                        "#1FAE96", "#E8A93C", "#E5484D", "#3ED9C4", "#8992A3",
                        "#5AC8B0", "#F5C518", "#C77DFF", "#4DA6FF", "#FF8A5C", "#B0E0D8",
                    ]
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
        with st.expander("Earnings surprises", key="earnings_surprises_expander", icon=":material/payments:"):
            st.caption("Notable earnings beats/misses among today's and this week's signals -- "
                       "only shown during earnings season (last 60 days).")
            surprises = get_earnings_surprises_from_signals(max_items=5)
            if surprises:
                cards_html = [
                    _signal_card_html(
                        s["ticker"], "Earnings surprise", f"{s['earnings_surprise_pct']:+.1f}%",
                        s["earnings_beat"], [("Reported", str(s["earnings_date"])[:10])],
                        standout=abs(s["earnings_surprise_pct"]) >= 15.0,
                    )
                    for s in surprises
                ]
                _render_signal_cards(cards_html)
                st.caption(f"Updated {file_last_modified('supertrend_signals_daily.csv')} (daily), "
                           f"{file_last_modified('supertrend_signals.csv')} (weekly). "
                           "⭐ = 15%+ surprise, in either direction.")
            else:
                st.caption("No notable earnings surprises right now (or we're between earnings seasons).")

    else:
        # --- Niet-ingelogde dagelijkse e-mail-opt-in -- laagdrempelig, geen
        #     account nodig. ALLEEN voor niet-ingelogde bezoekers -- een
        #     ingelogde gebruiker beheert z'n e-mail-voorkeuren al via
        #     Settings, en hoeft dit hier niet nogmaals te zien.
        #     Formulier direct zichtbaar (geen aparte 'onthul'-knop meer --
        #     dat gaf samen met de hero-knop het gevoel van '2x eenzelfde
        #     knop moeten indrukken' voor je bij het e-mailveld komt).
        if not current_user.is_logged_in:
            import database as _database_for_optin

            st.markdown(
                f"""
                <div id="signup" style="scroll-margin-top: 80px; background: linear-gradient(135deg, rgba(31,174,150,0.20), rgba(31,174,150,0.03));
                            border: 1.5px solid rgba(31,174,150,0.55); border-radius: 12px;
                            box-shadow: 0 0 24px rgba(31,174,150,0.12);
                            padding: 1.4rem 1.5rem; margin: 0.5rem 0 1.5rem 0;">
                    <div style="color:#1FAE96; font-weight:700; font-size:0.78rem; letter-spacing:1.5px; text-transform:uppercase;">
                        {_icon_span("mail", size_px=14, color="#1FAE96")} Free daily signals
                    </div>
                    <div style="color:#EAEDF1; font-size:1.25rem; font-weight:700; margin-top:8px; line-height:1.35;">
                        Quality stocks turning bullish today.
                    </div>
                    <div style="color:#C3E8E0; font-size:1rem; margin-top:4px; font-weight:500;">
                        Free, straight to your inbox, every weekday morning ☕
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
                optin_submitted = st.button("Activate", key="discover_optin_submit", type="primary")

            if optin_submitted:
                if not optin_email or "@" not in optin_email:
                    st.error("Please enter a valid email address.")
                else:
                    confirmation_token, unsubscribe_token = _database_for_optin.add_email_subscriber(optin_email, optin_region)
                    send_subscription_confirmation_email(optin_email, confirmation_token, unsubscribe_token)
                    st.success("Almost there! Check your inbox to confirm your subscription.")


        st.markdown(
            f"""
            <div id="signals" style="scroll-margin-top: 80px; background: linear-gradient(135deg, rgba(31,174,150,0.14), rgba(31,174,150,0.02));
                        border: 1px solid rgba(31,174,150,0.35); border-radius: 10px;
                        padding: 1rem 1.25rem; margin: 0.5rem 0 0.75rem 0;">
                <div style="color:#1FAE96; font-weight:700; font-size:0.75rem; letter-spacing:1.5px; text-transform:uppercase;">
                    Hesty's Signature Signals
                </div>
                <div style="color:#EAEDF1; font-size:1.05rem; font-weight:600; margin-top:3px;">
                    3 specially-built signals, each with its own investing style. This is the core of Hesty's.
                </div>
                <div style="color:#8992A3; font-size:0.85rem; margin-top:10px; line-height:1.6;">
                    {_icon_span("sensors", size_px=14, color="#8992A3")} <b style="color:#EAEDF1;">Momentocrats</b>: momentum + quality, for swing trades (days-weeks)<br>
                    {_icon_span("savings", size_px=14, color="#8992A3")} <b style="color:#EAEDF1;">Snowballers</b>: quality at a good price, for the long-term investor<br>
                    {_icon_span("rocket_launch", size_px=14, color="#8992A3")} <b style="color:#EAEDF1;">Rocket List</b>: accelerating growth, for higher risk/reward
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        def _email_pref_link(label: str):
            """Simpele verwijzing naar Settings om deze e-mail-voorkeur te beheren (i.p.v. een losse toggle hier)."""
            st.caption(f"{label} Manage in:")
            st.page_link(settings_page, label="Settings")

        def _next_weekly_scan_time() -> str:
            """Berekent het volgende geplande wekelijkse-scan-moment (zaterdag 07:00 UTC)."""
            now = datetime.now(timezone.utc)
            days_ahead = (5 - now.weekday()) % 7  # maandag=0 ... zaterdag=5
            if days_ahead == 0 and now.hour >= 7:
                days_ahead = 7  # het is al zaterdag na 07:00 UTC -> volgende week
            next_date = (now + timedelta(days=days_ahead)).replace(hour=7, minute=0, second=0, microsecond=0)
            return next_date.strftime("%Y-%m-%d %H:%M UTC")

        if current_user.is_logged_in:
            import database
            _current_prefs = database.get_user_preferences(current_user.email)
            _is_premium_discover = database.is_premium_user(current_user.email)
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
        with st.expander("Momentocrats", expanded=False, key="momentocrats_expander", icon=":material/sensors:"):
            st.caption("Technical momentum + fundamental quality, combined. Best for swing trades (days-weeks).")

            # st.segmented_control i.p.v. de eerdere URL-link-toggle -- die
            # laatste veroorzaakte een VOLLEDIGE paginaherlading (via
            # <a href="?...">), waardoor de expander steeds weer dichtklapte.
            # Een native widget zoals deze blijft BINNEN de Streamlit-sessie
            # (geen page-reload), dus de expander-status blijft nu intact --
            # en ziet er nog steeds modern/pill-achtig uit, geen oldschool
            # radio-bolletjes.
            current_timeframe = st.segmented_control(
                "Timeframe", options=["Daily", "Weekly"], selection_mode="single",
                default="Daily", key="momentocrats_timeframe", label_visibility="collapsed",
            )
            if current_timeframe is None:  # kan gebeuren als je 'm handmatig deselecteert
                current_timeframe = "Daily"
            csv_file = "supertrend_signals_daily.csv" if current_timeframe == "Daily" else "supertrend_signals.csv"

            df_screener = load_screener_data(csv_file)
            if df_screener is None or df_screener.empty:
                st.info("No results yet -- check back after the next scheduled scan.")
            else:
                df_screener = df_screener.sort_values("score", ascending=False)

                # De 'minimum score'-slider is weg -- bleek in de praktijk
                # nauwelijks gebruikt te worden. Toont nu gewoon alle
                # matchende signalen (tot de weergavelimiet), al gesorteerd
                # op score.
                total_matching = len(df_screener)
                filtered = df_screener.head(_signal_display_limit)

                # Kaarten i.p.v. een brede tabel (voorheen 13+ kolommen --
                # dat dwingt op mobiel dubbel scrollen af, verticaal EN
                # horizontaal). 'Weeks ago'/'Days ago' verschilt per
                # tijdvenster (weekly.csv heeft weken_geleden, daily.csv
                # heeft dagen_geleden) -- beide velden afgehandeld.
                cards_html = []
                for _, row in filtered.iterrows():
                    secondary = []
                    if "dagen_geleden" in row.index and pd.notna(row.get("dagen_geleden")):
                        secondary.append(("Flipped", f"{int(row['dagen_geleden'])}d ago"))
                    elif "weken_geleden" in row.index and pd.notna(row.get("weken_geleden")):
                        secondary.append(("Flipped", f"{int(row['weken_geleden'])}w ago"))
                    if pd.notna(row.get("sinds_omslag_pct")):
                        secondary.append(("Since flip", f"{row['sinds_omslag_pct']:+.1f}%"))
                    if pd.notna(row.get("roic_pct")):
                        secondary.append(("ROIC", f"{row['roic_pct']:+.1f}%"))
                    if pd.notna(row.get("relatieve_sterkte")):
                        secondary.append(("Rel. strength", f"{row['relatieve_sterkte']:+.1f}%"))
                    cards_html.append(_signal_card_html(
                        row["ticker"], "Score (out of 10)", f"{row['score']:.1f}", True, secondary,
                        standout=row["score"] >= 8.0,
                    ))
                _render_signal_cards(cards_html)
                st.caption(f"{len(filtered)} of {total_matching} shown, updated {file_last_modified(csv_file)}. "
                           "⭐ = score 8+, usually the ones worth a closer look.")
                if not _is_premium_discover and total_matching > _signal_display_limit:
                    st.info(f"Showing the top {_signal_display_limit} of {total_matching} matching signals. "
                            f"Upgrade to Premium to see all {total_matching}.", icon=":material/lock:")

            st.divider()
            _email_pref_link("Want this weekly by email?")

        # --- Snowball Signal (nieuw, wekelijks-only: kwaliteit + goede prijs) ---
        with st.expander("Snowballers", key="snowballers_expander", icon=":material/savings:"):
            st.caption("Quality companies trading below fair value, with low volatility. For the "
                       "long-term investor -- no fresh trend flip required.")
            if os.path.exists("snowball_signals.csv"):
                df_snowball = pd.read_csv("snowball_signals.csv")
                if not df_snowball.empty:
                    df_snowball = df_snowball.sort_values("afwijking_fair_value_pct", ascending=True)
                    total_snowball = len(df_snowball)
                    df_snowball = df_snowball.head(_signal_display_limit)

                    # Kaarten i.p.v. tabel. Kleur BEWUST omgekeerd t.o.v. de
                    # gebruikelijke +/- logica: een NEGATIEVE afwijking van
                    # fair value betekent 'goedkoper dan terecht' -- precies
                    # wat je wil bij dit signaaltype, dus GROEN, niet rood.
                    # Standout (ster) bij 20%+ onder fair value -- de écht
                    # opvallende koopjes.
                    cards_html = []
                    for _, row in df_snowball.iterrows():
                        secondary = []
                        if pd.notna(row.get("roic_pct")):
                            secondary.append(("ROIC", f"{row['roic_pct']:+.1f}%"))
                        if pd.notna(row.get("volatiliteit_pct")):
                            secondary.append(("Volatility", f"{row['volatiliteit_pct']:.1f}%"))
                        if pd.notna(row.get("prijs_nu")):
                            secondary.append(("Price", f"{row['prijs_nu']:.2f}"))
                        cards_html.append(_signal_card_html(
                            row["ticker"], "Vs fair value", f"{row['afwijking_fair_value_pct']:+.1f}%",
                            row["afwijking_fair_value_pct"] < 0, secondary,
                            standout=row["afwijking_fair_value_pct"] <= -20.0,
                        ))
                    _render_signal_cards(cards_html)
                    st.caption(f"{len(df_snowball)} of {total_snowball} shown, updated {file_last_modified('snowball_signals.csv')}. "
                               f"⭐ = 20%+ below fair value. Next update: {_next_weekly_scan_time()}.")
                    if not _is_premium_discover and total_snowball > _signal_display_limit:
                        st.info(f"Showing the top {_signal_display_limit} of {total_snowball} matching stocks. "
                                f"Upgrade to Premium to see all {total_snowball}.", icon=":material/lock:")
                else:
                    st.caption("No stocks currently meet the Snowballers criteria.")
            else:
                st.caption("No data yet -- this updates once a week via the scheduled scan.")

            st.divider()
            _email_pref_link("Want this weekly by email?")

        # --- Rocket List (nieuw, wekelijks-only: versnellende groei + momentum) ---
        with st.expander("Rocket List", key="rocket_list_expander", icon=":material/rocket_launch:"):
            st.caption("Accelerating growth stocks with strong momentum. For investors comfortable "
                       "with more risk in exchange for growth potential.")
            if os.path.exists("rocket_list_signals.csv"):
                df_rocket = pd.read_csv("rocket_list_signals.csv")
                if not df_rocket.empty:
                    df_rocket = df_rocket.sort_values("groei_pct", ascending=False)
                    total_rocket = len(df_rocket)
                    df_rocket = df_rocket.head(_signal_display_limit)

                    # Standout (ster) bij 25%+ groei -- de écht opvallende
                    # versnellers.
                    cards_html = []
                    for _, row in df_rocket.iterrows():
                        secondary = []
                        if pd.notna(row.get("relatieve_sterkte")):
                            secondary.append(("Rel. strength", f"{row['relatieve_sterkte']:+.1f}%"))
                        if pd.notna(row.get("prijs_nu")):
                            secondary.append(("Price", f"{row['prijs_nu']:.2f}"))
                        cards_html.append(_signal_card_html(
                            row["ticker"], "Growth", f"{row['groei_pct']:+.1f}%", True, secondary,
                            standout=row["groei_pct"] >= 25.0,
                        ))
                    _render_signal_cards(cards_html)
                    st.caption(f"{len(df_rocket)} of {total_rocket} shown, updated {file_last_modified('rocket_list_signals.csv')}. "
                               f"⭐ = 25%+ growth. Next update: {_next_weekly_scan_time()}.")
                    if not _is_premium_discover and total_rocket > _signal_display_limit:
                        st.info(f"Showing the top {_signal_display_limit} of {total_rocket} matching stocks. "
                                f"Upgrade to Premium to see all {total_rocket}.", icon=":material/lock:")
                else:
                    st.caption("No stocks currently meet the Rocket List criteria.")
            else:
                st.caption("No data yet -- this updates once a week via the scheduled scan.")

            st.divider()
            _email_pref_link("Want this weekly by email?")



def render_today():
    st.markdown("### Today")

    if not current_user.is_logged_in:
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
        # Tegels i.p.v. een bullet-lijst -- die voelde op mobiel al snel
        # 'supervol' aan met 6 losse regels + icoontjes. Zelfde stijl als
        # de hero-tegels (icoon-badge + titel + subtekst), en het overzicht
        # is meteen ook completer/actueler dan de oude lijst (mistte
        # 'nieuwe, persoonlijke signalen' -- een van de kernfeatures).
        today_points = [
            ("bar_chart", "Your daily performance", "best/worst positions, vs. yesterday"),
            ("event", "Earnings & dividends ahead", "for your actual holdings"),
            ("balance", "Risk & concentration alerts", "when a position outgrows your target"),
            ("candlestick_chart", "52-week highs & lows", "the moment they happen"),
            ("search", "New signals, personalized", "matched to what you hold or watch"),
            ("newspaper", "News, filtered to your tickers", "no noise"),
        ]
        today_points_html = "".join(
            f'<div style="background:rgba(31,174,150,0.08); border:1px solid rgba(31,174,150,0.25); '
            f'border-radius:12px; padding:0.85rem 1rem;">'
            f'<div style="width:32px; height:32px; border-radius:50%; background:rgba(31,174,150,0.18); '
            f'display:flex; align-items:center; justify-content:center;">{_icon_span(icon_name, size_px=16, color="#1FAE96")}</div>'
            f'<div style="color:#EAEDF1; font-size:0.85rem; font-weight:700; margin-top:8px; line-height:1.3;">{title}</div>'
            f'<div style="color:#8992A3; font-size:0.73rem; margin-top:2px; line-height:1.3;">{sub}</div>'
            f'</div>'
            for icon_name, title, sub in today_points
        )
        st.markdown(
            f'<div style="display:grid; grid-template-columns:repeat(2, 1fr); gap:0.6rem; margin-bottom:1rem;">{today_points_html}</div>',
            unsafe_allow_html=True,
        )
        st.page_link(discover_page, label="See what Hesty's can do (no login)")
        st.info("Log in via the menu once you're ready, then add positions under My Portfolio or "
                "your Watchlist to unlock this.")
    else:
        import database
        import screener as _screener_module  # noqa: F401 -- zorgt dat get_top_news_for_tickers 'm kan importeren

        user_email = current_user.email
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
                            f'{vs_yesterday_pct:+.1f}%</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown("**Your Portfolio Today**")

                    dcol2, dcol3 = st.columns(2, gap="medium")
                    with dcol2:
                        if daily_stats:
                            st.markdown(
                                _hero_stat_tile_html(
                                    "Best today", "trending_up", daily_stats["best_performer"], daily_stats["best_change_pct"],
                                    "31,174,150", "#1FAE96",
                                ),
                                unsafe_allow_html=True,
                            )
                        else:
                            st.metric("Best today", "n/a")
                    with dcol3:
                        if daily_stats:
                            st.markdown(
                                _hero_stat_tile_html(
                                    "Worst today", "trending_down", daily_stats["worst_performer"], daily_stats["worst_change_pct"],
                                    "229,72,77", "#E5484D",
                                ),
                                unsafe_allow_html=True,
                            )
                        else:
                            st.metric("Worst today", "n/a")

                    st.page_link(portfolio_page, label="View My Portfolio")

            # --- Yesterday's Top Movers (verplaatst hierheen vanuit Discover --
            # dit is een leuk, marktbreed dagelijks contactmoment, past beter bij
            # Today's 'wat is er vandaag interessant'-insteek dan bij Discover) ---
            with st.container(border=True):
                st.markdown("**Yesterday's biggest movers**")
                if os.path.exists("top_movers.csv"):
                    df_movers = pd.read_csv("top_movers.csv").dropna(subset=["change_pct"])
                    if not df_movers.empty:
                        top_gainer = df_movers.loc[df_movers["change_pct"].idxmax()]
                        top_loser = df_movers.loc[df_movers["change_pct"].idxmin()]

                        mover_col1, mover_col2 = st.columns(2, gap="medium")
                        with mover_col1:
                            st.markdown(
                                _hero_stat_tile_html("Top gainer", "trending_up", top_gainer["ticker"], top_gainer["change_pct"], "31,174,150", "#1FAE96"),
                                unsafe_allow_html=True,
                            )
                        with mover_col2:
                            st.markdown(
                                _hero_stat_tile_html("Top loser", "trending_down", top_loser["ticker"], top_loser["change_pct"], "229,72,77", "#E5484D"),
                                unsafe_allow_html=True,
                            )
                        st.markdown("<div style='height: 0.75rem'></div>", unsafe_allow_html=True)
                        with st.expander("See more movers", key="see_more_movers_expander"):
                            gainers = df_movers.sort_values("change_pct", ascending=False).head(5)
                            losers = df_movers.sort_values("change_pct", ascending=True).head(5)

                            st.markdown("**Top gainers**")
                            _render_signal_cards([
                                _signal_card_html(row["ticker"], "Change", f"{row['change_pct']:+.1f}%", True, [])
                                for _, row in gainers.iterrows()
                            ])
                            st.markdown("**Top losers**")
                            _render_signal_cards([
                                _signal_card_html(row["ticker"], "Change", f"{row['change_pct']:+.1f}%", False, [])
                                for _, row in losers.iterrows()
                            ])
                        # 'Last updated' bewust ONDERAAN i.p.v. bovenaan -- de
                        # belangrijkste info (de daadwerkelijke movers) hoort
                        # als eerste in beeld te komen, niet een meta-regel.
                        st.caption(f"Last updated: {file_last_modified('top_movers.csv')}")
                    else:
                        st.caption("No mover data available right now.")
                else:
                    st.caption("No data yet. This updates once daily via the scheduled scan. Check back tomorrow.")

            # --- Today's radar (events + opportunities + earnings-verrassingen, samengevoegd) ---
            with st.container(border=True):
                st.markdown("**Today's radar**")

                # Alle items verzamelen i.p.v. losse st.markdown()-aanroepen
                # per bullet -- dat voelde als een lange, rommelige wand van
                # gemengde emoji-bullets, vooral op mobiel. Nu 1 samenhangend
                # blok aan het eind.
                radar_rows = []

                macro_events = get_todays_macro_events(max_items=3)
                with st.spinner("Checking today's radar..."):
                    earnings_today = get_todays_portfolio_earnings(tracked_items, max_items=3)
                    infos = get_tickers_info(holdings) if holdings else {}
                todays_events = macro_events + [
                    {"name": f"{e['naam']} ({e['ticker']}) reports earnings today"} for e in earnings_today
                ]
                for event in todays_events[:3]:
                    time_part = f" ({event['time']})" if "time" in event else ""
                    radar_rows.append(_radar_row_html(_icon_span("event", size_px=15, color="#8992A3"), f"{event['name']}{time_part}"))

                # Aankomende earnings deze week -- niet alleen vandaag, ook een
                # heads-up ervoor, zodat je niet pas op de dag zelf verrast wordt.
                upcoming_earnings = get_upcoming_portfolio_earnings(tracked_items, days_ahead=5, max_items=3)
                for e in upcoming_earnings:
                    day_word = "tomorrow" if e["days_until"] == 1 else f"in {e['days_until']} days"
                    radar_rows.append(_radar_row_html(
                        _icon_span("calendar_month", size_px=15, color="#8992A3"),
                        f"<b>{e['naam']}</b> ({e['ticker']}) reports earnings {day_word} ({e['earnings_date']}).",
                    ))

                # Concentratie-waarschuwing -- alleen tonen als je eigen doel-grens
                # daadwerkelijk overschreden wordt (geen ruis op normale dagen).
                if holdings:
                    risk_profile = database.get_risk_profile(user_email)
                    concentration_alert = get_concentration_alert(holdings, risk_profile["max_position_pct"])
                    if concentration_alert:
                        radar_rows.append(_radar_row_html(_icon_span("balance", size_px=15, color="#8992A3"), concentration_alert))

                # Aankomende ex-dividend-data voor je HUIDIGE posities.
                upcoming_ex_div = get_upcoming_ex_dividend_dates(holdings, infos, days_ahead=5, max_items=3)
                for d in upcoming_ex_div:
                    day_word = "today" if d["days_until"] == 0 else ("tomorrow" if d["days_until"] == 1 else f"in {d['days_until']} days")
                    radar_rows.append(_radar_row_html(
                        _icon_span("payments", size_px=15, color="#8992A3"),
                        f"<b>{d['naam']}</b> goes ex-dividend {day_word} ({d['ex_div_date']}).",
                    ))

                # 52-weken-record -- een leuk, opvallend signaal als een van je
                # posities vandaag een nieuwe hoogte/laagte raakt.
                records_52wk = get_52_week_records(holdings, infos, max_items=3) if holdings else []
                for r in records_52wk:
                    icon_name = "trending_up" if r["type"] == "high" else "trending_down"
                    icon_color = "#1FAE96" if r["type"] == "high" else "#E5484D"
                    label = "new 52-week high" if r["type"] == "high" else "new 52-week low"
                    radar_rows.append(_radar_row_html(_icon_span(icon_name, size_px=15, color=icon_color), f"<b>{r['naam']}</b> ({r['ticker']}) just hit a {label}."))

                # Deep-dive verkoop-triggers (prijs of datum) die bereikt zijn --
                # ingesteld op een rustig moment, geen actie nodig behalve ernaar kijken.
                deep_dive_triggers = get_deep_dive_triggers_hit(user_email, max_items=3)
                for t in deep_dive_triggers:
                    radar_rows.append(_radar_row_html(_icon_span("notifications", size_px=15, color="#8992A3"), f"<b>{t['naam']}</b> ({t['ticker']}) {t['detail']}."))

                weekly_scan_date = get_file_last_commit_date("supertrend_signals.csv")
                last_seen_weekly = database.get_last_seen_weekly_signals_date(user_email)
                weekly_is_new = weekly_scan_date is not None and weekly_scan_date != last_seen_weekly
                if weekly_is_new:
                    database.set_last_seen_weekly_signals_date(user_email, weekly_scan_date)

                opportunities = build_opportunities_today(holdings, watchlist_items, include_weekly=weekly_is_new)
                weekly_part = f", {opportunities['weekly_signals']} weekly" if weekly_is_new else ""
                radar_rows.append(_radar_row_html(
                    _icon_span("search", size_px=15, color="#8992A3"),
                    f"<b>{opportunities['total_signals']}</b> signal(s) found "
                    f"({opportunities['daily_signals']} daily{weekly_part}). "
                    f"<b>{opportunities['in_portfolio_count']}</b> relate to your portfolio, "
                    f"<b>{opportunities['in_watchlist_count']}</b> are on your watchlist, "
                    f"<b>{opportunities['new_opportunities_count']}</b> are new ideas."
                ))

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
                    radar_rows.append(_radar_row_html(
                        emoji, f"<b>{s['ticker']}</b>: {s['earnings_surprise_pct']:+.1f}% earnings surprise ({s['earnings_date']})"
                    ))

                # Markt-brede verrassingen (NIET in je eigen portfolio/watchlist) --
                # strenger venster (1 dag i.p.v. 2), want minder persoonlijk relevant,
                # maar toch de moeite waard om even te vermelden.
                market_wide_surprises = [
                    s for s in all_recent_surprises
                    if s["ticker"] not in tracked_tickers and _is_recent_earnings(s["earnings_date"], max_days=1)
                ]
                for s in market_wide_surprises[:2]:
                    emoji = "🟢" if s["earnings_beat"] else "🔴"
                    radar_rows.append(_radar_row_html(
                        emoji,
                        f"Also worth noting (not in your portfolio): "
                        f"<b>{s['ticker']}</b> {s['earnings_surprise_pct']:+.1f}% surprise ({s['earnings_date']})"
                    ))

                # Sector/theme-drempel-meldingen -- een extreme 1-maands-beweging
                # kan een koop-/verkoopmoment zijn.
                with st.spinner("Checking for sector/theme extremes..."):
                    threshold_alerts = get_sector_theme_threshold_alerts()
                for alert in threshold_alerts[:3]:
                    move_emoji = "🔥" if alert["direction"] == "up" else "🥶"
                    extreme_marker = " (extreme move!)" if alert["level"] == "extreme" else ""
                    region_suffix = f" ({alert['region']})" if alert.get("region") else ""
                    kind_label = "sector" if alert["kind"] == "sector" else "theme"
                    radar_rows.append(_radar_row_html(
                        move_emoji,
                        f"<b>{alert['name']}</b>{region_suffix} ({kind_label}) is "
                        f"{alert['pct']:+.1f}% this month{extreme_marker}"
                    ))

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
                            radar_rows.append(_radar_row_html(emoji, f"<b>{f['naam']}</b> just flipped to {f['status']}"))

                if radar_rows:
                    _render_radar_rows(radar_rows)
                else:
                    st.caption("Nothing new to flag right now. A quiet day on your radar.")

                st.caption("See the full signal lists under:")
                st.page_link(discover_page, label="Discover")

            # --- Top nieuws (portfolio + watchlist) -- nu inklapbaar, want samen
            # met Market news voelde dit als een lange wand van tekst ---
            with st.expander("Top news for you", expanded=False, key="top_news_for_you_expander", icon=":material/newspaper:"):
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
            with st.expander("Market news", expanded=False, key="market_news_expander", icon=":material/public:"):
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


def render_premium():
    import database

    st.markdown("### Premium")

    _premium_free_for_all = st.secrets.get("app", {}).get("premium_free_for_all", False)
    if _premium_free_for_all:
        st.success("Everything is unlocked for free while we're still getting started -- "
                   "no payment needed yet. Enjoy, and thanks for trying Hesty's early!",
                   icon=":material/auto_awesome:")

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
        with st.expander("See it running on a real chart", key="see_it_running_on_a_real_chart_expander"):
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

        if current_user.is_logged_in and database.is_premium_user(current_user.email, ignore_free_for_all=True):
            try:
                with open("premium_content/smart_dca_assistant.pine", encoding="utf-8") as f:
                    pine_code = f.read()

                # Watermerk wordt NA de //@version=6-regel geplaatst (niet ervoor) --
                # bronnen spreken elkaar tegen of commentaar vóór die regel de
                # compilatie kan verstoren, dus voor de zekerheid altijd erna.
                lines = pine_code.split("\n", 1)
                watermark = (
                    f"// Licensed to: {current_user.email}\n"
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
            st.caption("Available for Premium members -- see Subscription below.")

    with st.container(border=True):
        st.markdown("##### Subscription")

        # --- Terugkeer van Stripe: verifieer de sessie en zet premium aan ---
        returned_session_id = st.query_params.get("session_id")
        if returned_session_id:
            with st.spinner("Confirming your payment..."):
                success, paid_email = verify_and_activate_premium(returned_session_id)
            if success:
                st.success(f"Payment confirmed! Premium is now active for {paid_email}.", icon=":material/celebration:")
            else:
                st.warning(
                    "We couldn't confirm this payment yet. If you just completed checkout, "
                    "please wait a few seconds and refresh this page."
                )

        if not current_user.is_logged_in:
            st.info("Log in via the menu first so we know which account to upgrade.")
        elif database.is_premium_user(current_user.email):
            st.success("You're already on Premium. Thank you!")
            customer_id = database.get_stripe_customer_id(current_user.email)
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
                            st.secrets["stripe"]["price_id_monthly"], current_user.email,
                        )
                    st.link_button("Continue to payment →", session.url, type="primary")
            with pcol2:
                st.markdown("**Yearly -- €75/yr** *(~$85)*")
                if st.button("Subscribe yearly", key="sub_yearly"):
                    with st.spinner("Preparing checkout..."):
                        session = create_checkout_session(
                            st.secrets["stripe"]["price_id_yearly"], current_user.email,
                        )
                    st.link_button("Continue to payment →", session.url, type="primary")
            st.caption("Payments are processed securely by Stripe -- we never see or store your card details. "
                       "USD amounts shown are approximate (current EUR/USD rate) -- you're charged in EUR.")


def render_settings():
    import database

    st.markdown("### Settings")

    if current_user.is_logged_in:
        user_email = current_user.email
        is_premium = database.is_premium_user(user_email)

        with st.container(border=True):
            st.markdown("#### Email preferences")
            prefs = database.get_user_preferences(user_email)

            st.caption("Weekly signals (choose which ones you want -- delivered in 1 combined email)")
            wants_momentocrats = st.checkbox(
                "Momentocrats -- technical momentum + fundamental quality combo",
                value=prefs.get("wants_momentocrats_email", False),
            )
            wants_snowball = st.checkbox(
                "Snowballers -- quality stocks below fair value, for the long term",
                value=prefs.get("wants_snowball_email", False),
            )
            wants_rocket = st.checkbox(
                "Rocket List -- accelerating growth + momentum",
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
        st.info("Log in via the menu to manage your email preferences.")


def render_confirm():
    import database as _database_for_confirm

    st.markdown("### Confirm your subscription")
    token = st.query_params.get("token", "")
    if not token:
        st.error("Missing confirmation link. Please use the link from your email.")
    elif _database_for_confirm.confirm_email_subscriber(token):
        st.success("You're all set! You'll get today's new bullish signals in your inbox every weekday morning.")
        st.page_link(discover_page, label="Back to Discover →")
    else:
        st.error("This confirmation link is invalid or has already been used.")


def render_unsubscribe():
    import database as _database_for_unsubscribe

    st.markdown("### Unsubscribe")
    token = st.query_params.get("token", "")
    if not token:
        st.error("Missing unsubscribe link. Please use the link from your email.")
    elif _database_for_unsubscribe.unsubscribe_email_subscriber(token):
        st.success("You've been unsubscribed. Sorry to see you go!")
    else:
        st.info("This link is invalid or you're already unsubscribed.")


def render_login():
    import database as _database_for_login

    _reset_token = st.query_params.get("reset_token")

    if current_user.is_logged_in:
        st.info("You're already logged in.")
        st.markdown(
            f'<a href="/{_default_view}" class="button-link" target="_self">Go to your dashboard &rarr;</a>',
            unsafe_allow_html=True,
        )
    elif _reset_token:
        # --- Iemand kwam hier via de reset-link uit de e-mail -- toon
        # het 'nieuw wachtwoord instellen'-formulier i.p.v. de normale
        # Sign In/Sign Up-toggle. ---
        st.markdown(
            '<div style="max-width:420px; margin:2rem auto 0 auto; text-align:center;">'
            '<h2 style="margin-bottom:0.3rem;">Set a new password</h2>'
            '</div>',
            unsafe_allow_html=True,
        )
        reset_col_l, reset_col_mid, reset_col_r = st.columns([1, 2, 1])
        with reset_col_mid:
            new_password = st.text_input("New password", type="password", key="reset_new_password",
                                          help="At least 8 characters.")
            new_password_confirm = st.text_input("Confirm new password", type="password", key="reset_new_password_confirm")
            if st.button("Set new password", type="primary", key="reset_submit"):
                if len(new_password) < 8:
                    st.error("Password must be at least 8 characters.")
                elif new_password != new_password_confirm:
                    st.error("Passwords don't match.")
                else:
                    success, message = _database_for_login.reset_password_with_token(_reset_token, new_password)
                    if success:
                        st.success(message)
                        st.page_link(login_page, label="Go to Sign In")
                    else:
                        st.error(message)
    elif st.session_state.get("show_forgot_password"):
        # --- 'Forgot password?' aangeklikt -- toon het e-mailadres-
        # formulier om een reset-link aan te vragen. ---
        st.markdown(
            '<div style="max-width:420px; margin:2rem auto 0 auto; text-align:center;">'
            '<h2 style="margin-bottom:0.3rem;">Reset your password</h2>'
            '<p style="color:#8992A3; margin-bottom:1.5rem;">Enter your email and we\'ll send you a reset link</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        forgot_col_l, forgot_col_mid, forgot_col_r = st.columns([1, 2, 1])
        with forgot_col_mid:
            forgot_email = st.text_input("Email", placeholder="you@example.com", key="forgot_password_email")
            if st.button("Send reset link", type="primary", key="forgot_password_submit"):
                if not forgot_email:
                    st.error("Enter your email address.")
                else:
                    reset_token = _database_for_login.create_password_reset_token(forgot_email)
                    if reset_token:
                        reset_url = f"https://hestys.streamlit.app/login?reset_token={reset_token}"
                        send_email(
                            to=forgot_email, subject="Reset your Hesty's password",
                            body=f"Click the link below to set a new password (valid for 1 hour):\n\n{reset_url}",
                        )
                    # BEWUST ALTIJD dezelfde, algemene bevestiging tonen --
                    # ongeacht of er echt een account/mail was, zodat een
                    # aanvaller niet kan afleiden welke e-mailadressen wel/
                    # niet bestaan.
                    st.success("If an account exists for this email, we've sent a reset link.")
            if st.button("Back to Sign In", key="back_to_signin_from_forgot"):
                st.session_state.pop("show_forgot_password", None)
                st.rerun()
    else:
        st.markdown(
            '<div style="max-width:420px; margin:2rem auto 0 auto; text-align:center;">'
            '<h2 class="hero-headline" style="margin-bottom:0.3rem;">Welcome back</h2>'
            '<p style="color:#8992A3; margin-bottom:1.5rem;">Sign in or create an account with email</p>'
            '</div>',
            unsafe_allow_html=True,
        )

        login_col_l, login_col_mid, login_col_r = st.columns([1, 2, 1])
        with login_col_mid:
            login_mode = st.segmented_control(
                "Mode", options=["Sign In", "Sign Up"], selection_mode="single",
                default="Sign In", key="login_mode_toggle", label_visibility="collapsed",
            )
            if login_mode is None:
                login_mode = "Sign In"

            if login_mode == "Sign In":
                login_email = st.text_input("Email", placeholder="you@example.com", key="login_email")
                login_password = st.text_input("Password", type="password", key="login_password")
                if st.button("Forgot password?", key="forgot_password_trigger", type="tertiary"):
                    st.session_state["show_forgot_password"] = True
                    st.rerun()
                if st.button("Sign In", type="primary", key="login_submit"):
                    if not login_email or not login_password:
                        st.error("Enter both your email and password.")
                    else:
                        success, result = _database_for_login.verify_password_login(login_email, login_password)
                        if success:
                            st.session_state["password_auth_email"] = login_email
                            st.session_state["password_auth_name"] = result
                            _new_token = _database_for_login.create_session_token(login_email)
                            _cookie_controller.set("hestys_session_token", _new_token)
                            st.query_params["view"] = "today"
                            st.rerun()
                        else:
                            st.error(result)
            else:
                signup_name = st.text_input("Name", placeholder="Your name", key="signup_name")
                signup_email = st.text_input("Email", placeholder="you@example.com", key="signup_email")
                signup_password = st.text_input("Password", type="password", key="signup_password",
                                                 help="At least 8 characters.")
                signup_password_confirm = st.text_input("Confirm password", type="password", key="signup_password_confirm")
                if st.button("Create account", type="primary", key="signup_submit"):
                    if not signup_name or not signup_email or not signup_password:
                        st.error("Fill in all fields.")
                    elif "@" not in signup_email:
                        st.error("Enter a valid email address.")
                    elif len(signup_password) < 8:
                        st.error("Password must be at least 8 characters.")
                    elif signup_password != signup_password_confirm:
                        st.error("Passwords don't match.")
                    else:
                        success, message = _database_for_login.sign_up_with_password(signup_email, signup_name, signup_password)
                        if success:
                            st.session_state["password_auth_email"] = signup_email
                            st.session_state["password_auth_name"] = signup_name
                            _new_token = _database_for_login.create_session_token(signup_email)
                            _cookie_controller.set("hestys_session_token", _new_token)
                            st.query_params["view"] = "today"
                            st.rerun()
                        else:
                            st.error(message)

            st.markdown(
                '<div style="display:flex; align-items:center; gap:0.75rem; margin:1.5rem 0 1rem 0;">'
                '<div style="flex:1; height:1px; background:rgba(137,146,163,0.25);"></div>'
                '<span style="color:#8992A3; font-size:0.8rem;">OR</span>'
                '<div style="flex:1; height:1px; background:rgba(137,146,163,0.25);"></div>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.button("Continue with Google", on_click=st.login, key="login_page_google", width="stretch")


def render_support():
    st.markdown("### Support")
    st.write("Questions, ideas, or something not working as expected? Check the FAQ below, "
              "or send us a message directly. Business inquiries and partnerships are welcome too.")

    st.markdown("#### Frequently asked questions")

    with st.expander("What does Discover do?", key="what_does_discover_do_expander"):
        st.write(
            "It scans the AEX, Nasdaq-100, S&P 500, DAX, and CAC 40 (weekly and daily variants) "
            "for stocks that just turned bullish on a Supertrend indicator, scored on technical "
            "and fundamental factors. It's public, no login required."
        )

    with st.expander("Can I import my transaction history from my broker?", key="can_i_import_my_transaction_history_from_my_broker_expander"):
        st.write(
            "Yes, for DEGIRO -- under My Portfolio, 'Import from a broker'. Using a different "
            "broker? Let us know via the contact form below, and we'll look into adding it."
        )

    with st.expander("Is my portfolio data private?", key="is_my_portfolio_data_private_expander"):
        st.write(
            "Yes. Your tracked positions are only visible to you, tied to your Google account. "
            "We never share or sell your data."
        )

    with st.expander("What's the difference between Free and Premium?", key="what_s_the_difference_between_free_and_premium_expander"):
        st.write(
            "Free covers concentration, diversification, sector and asset mix, and up to 10 "
            "tracked positions. Premium adds dividend income, valuation, cash%, rebalancing "
            "ideas, a return-vs-benchmark chart, a correlation matrix, unlimited positions, and "
            "the Smart DCA Assistant TradingView indicator. See the Premium page for the full comparison."
        )

    with st.expander("How do I cancel my Premium subscription?", key="how_do_i_cancel_my_premium_subscription_expander"):
        st.write(
            "On the Premium page, under Subscription, click 'Manage subscription' -- this opens "
            "Stripe's secure billing portal, where you can cancel anytime. You'll keep Premium "
            "access until the end of your current billing period."
        )

    with st.expander("How do I get the Smart DCA Assistant TradingView indicator?", key="how_do_i_get_the_smart_dca_assistant_tradingview_indicator_expander"):
        st.write(
            "Premium members can download it directly from the Premium page, with setup "
            "instructions for TradingView's Pine Editor."
        )

    with st.expander("How do I change what emails I receive?", key="how_do_i_change_what_emails_i_receive_expander"):
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


def render_privacy():
    st.markdown("### Privacy")
    st.caption("Plain language, not a legal document -- if you have questions beyond this, "
               "just ask via Support.")

    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, rgba(31,174,150,0.16), rgba(31,174,150,0.02));
                    border: 1px solid rgba(31,174,150,0.4); border-radius: 12px;
                    padding: 1.25rem 1.5rem; margin: 0.75rem 0 1.25rem 0;">
            <div style="color:#1FAE96; font-weight:700; font-size:0.75rem; letter-spacing:1.5px; text-transform:uppercase;">
                {_icon_span("lock", size_px=14, color="#1FAE96")} Your data is pseudonymized
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

    with st.expander("What we collect", key="what_we_collect_expander"):
        st.write(
            "When you log in (via Google or Microsoft), we get your email address and name. "
            "Beyond that, we only store what you actively enter: the positions and watchlist "
            "items you add, any buy/sell transactions you log (or import from a broker), your "
            "risk profile answers, your email preferences, and your cash amount if you fill "
            "one in."
        )

    with st.expander("Why we collect it", key="why_we_collect_it_expander"):
        st.write(
            "Purely to show you your own data back (My Portfolio, Analyze, your personalized "
            "Today briefing), and to send you the daily/weekly emails you've opted into. "
            "Nothing here is used to build a profile of you for advertising -- there are no ads "
            "on Hesty's, and there never will be."
        )

    with st.expander("Who can see it", key="who_can_see_it_expander"):
        st.write(
            "Only you, when logged into your own account. As explained above, your portfolio "
            "and transaction data is stored under a hashed identifier, not your readable email "
            "address. A small, separate table maps that hash back to your real address -- purely "
            "so we can still send you the emails you've opted into. We only ever look at "
            "anything ourselves to fix a bug or help with a support question."
        )

    with st.expander("Third parties involved", key="third_parties_involved_expander"):
        st.write(
            "Supabase hosts our database. Google or Microsoft handle the login itself (we "
            "never see your password). Stripe will handle payments once Premium is actually "
            "for sale. Market data (prices, company info) comes from Yahoo Finance -- no "
            "personal data is sent there, just ticker symbols."
        )

    with st.expander("Your control over it", key="your_control_over_it_expander"):
        st.write("You can remove any position, watchlist item, or transaction yourself at any time.")
        st.caption("Want your entire account and its data deleted? Reach out via:")
        st.page_link(support_page, label="Support")

    with st.expander("Cookies", key="cookies_expander"):
        st.write(
            "A login session cookie is used to keep you signed in -- that's required for "
            "Google/Microsoft login to work at all. We don't use tracking or advertising cookies."
        )


# ============================================================
# NAVIGATIE (stap B1): st.navigation i.p.v. handmatige ?view=-routing --
# geen volledige pagina-herlading meer bij het klikken tussen pagina's.
# Alle render_XXX()-functies hierboven (stap A) worden nu rechtstreeks
# als pagina's geregistreerd.
# ============================================================
today_page = st.Page(render_today, title="Today", url_path="today", default=current_user.is_logged_in)
discover_page = st.Page(render_discover, title="Discover", url_path="discover", default=not current_user.is_logged_in)
portfolio_page = st.Page(render_portfolio, title="My Portfolio", url_path="portfolio")
analyze_page = st.Page(render_analyze, title="Analyze", url_path="analyze")
settings_page = st.Page(render_settings, title="Settings", url_path="settings")
premium_page = st.Page(render_premium, title="Premium", url_path="premium")
support_page = st.Page(render_support, title="Support", url_path="support")
privacy_page = st.Page(render_privacy, title="Privacy", url_path="privacy")
login_page = st.Page(render_login, title="Login", url_path="login")
confirm_page = st.Page(render_confirm, title="Confirm", url_path="confirm")
unsubscribe_page = st.Page(render_unsubscribe, title="Unsubscribe", url_path="unsubscribe")

all_pages = [
    today_page, discover_page, portfolio_page, analyze_page, settings_page,
    premium_page, support_page, privacy_page, login_page, confirm_page, unsubscribe_page,
]
pg = st.navigation(all_pages, position="hidden")

with st.sidebar:
    st.markdown(
        f"""
        <div class="app-header" style="border-bottom:none; padding:0 0 0.5rem 0; margin-bottom:0.5rem;">
            <a href="{'/today' if current_user.is_logged_in else '/discover'}" class="app-header-top" target="_self">
                <img src="data:image/png;base64,{_LOGO_ICON_B64}" width="31" height="38"
                     style="object-fit:contain; flex-shrink:0;" alt="Hestys logo" />
                <div>
                    <h1 class="sidebar-logo-title">HESTYS</h1>
                    <div class="tagline" style="margin-top:0.02rem;">YOUR INVESTING EDGE</div>
                </div>
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Actieve pagina krijgt een linker accent-balk + jade tekstkleur. ---
    _active_url_path = getattr(pg, "url_path", "")
    _nav_css_parts = ["""
    <style>
    div[data-testid="stSidebarNav"] { display: none; }
    div[data-testid="stSidebar"] a[href$="/discover"],
    div[data-testid="stSidebar"] a[href$="/today"],
    div[data-testid="stSidebar"] a[href$="/portfolio"],
    div[data-testid="stSidebar"] a[href$="/analyze"],
    div[data-testid="stSidebar"] a[href$="/support"],
    div[data-testid="stSidebar"] a[href$="/premium"] {
        display: flex; align-items: center; gap: 0.75rem;
        font-family: 'Inter', sans-serif; font-size: 0.92rem; font-weight: 600;
        padding: 0.6rem 0.9rem 0.6rem 0.75rem; border-radius: 8px;
        text-decoration: none !important; color: #8992A3 !important;
        border-left: 3px solid transparent; margin-bottom: 3px;
    }
    div[data-testid="stSidebar"] a[href$="/discover"]:hover,
    div[data-testid="stSidebar"] a[href$="/today"]:hover,
    div[data-testid="stSidebar"] a[href$="/portfolio"]:hover,
    div[data-testid="stSidebar"] a[href$="/analyze"]:hover,
    div[data-testid="stSidebar"] a[href$="/support"]:hover,
    div[data-testid="stSidebar"] a[href$="/premium"]:hover {
        background: rgba(255,255,255,0.04);
    }
    """]
    if _active_url_path:
        _nav_css_parts.append(f"""
    div[data-testid="stSidebar"] a[href$="/{_active_url_path}"] {{
        color: #1FAE96 !important;
        background: linear-gradient(90deg, rgba(31,174,150,0.16), rgba(31,174,150,0.02));
        border-left: 3px solid #1FAE96 !important;
    }}
    """)
    _nav_css_parts.append("</style>")
    st.markdown("".join(_nav_css_parts), unsafe_allow_html=True)

    # CSS-injectie van de originele SVG-lijniconen bleek onbetrouwbaar
    # (verscheen soms helemaal niet) -- overgestapt op Streamlit's officieel
    # ondersteunde Material Symbols (via icon=":material/xxx:"), die een
    # subtiele, professionele lijn-stijl hebben -- veel dichter bij de
    # oorspronkelijke iconen dan emoji, en betrouwbaar (geen CSS-truc nodig).
    st.page_link(discover_page, label="Discover", icon=":material/search:")
    st.page_link(today_page, label="Today", icon=":material/calendar_today:")
    st.page_link(portfolio_page, label="My Portfolio", icon=":material/work:")
    st.page_link(analyze_page, label="Analyze", icon=":material/bar_chart:")
    st.page_link(support_page, label="Support", icon=":material/support_agent:")
    st.page_link(premium_page, label="Premium", icon=":material/star:")
    st.divider()
    if current_user.is_logged_in:
        import database as _database_for_identity
        _database_for_identity.ensure_user_identity(current_user.email, current_user.name)
        st.page_link(settings_page, label=current_user.name, icon=":material/settings:")
        if st.user.is_logged_in:
            # Ingelogd via Google -- Streamlit's eigen logout-mechanisme.
            st.button("Log out", on_click=st.logout, key="header_logout")
        else:
            # Ingelogd via e-mail+wachtwoord -- eigen sessie opruimen
            # (st.logout() is specifiek voor Google, raakt deze sessie niet).
            # Ook de sessie-token uit de database EN de cookie zelf
            # verwijderen -- anders zou een oude cookie na 'uitloggen'
            # je alsnog weer inloggen bij de volgende paginaverversing.
            def _password_logout():
                import database as _database_for_logout
                _old_token = _cookie_controller.get("hestys_session_token")
                if _old_token:
                    _database_for_logout.delete_session_token(_old_token)
                    _cookie_controller.remove("hestys_session_token")
                st.session_state.pop("password_auth_email", None)
                st.session_state.pop("password_auth_name", None)
            st.button("Log out", on_click=_password_logout, key="header_logout_password")
    else:
        st.page_link(login_page, label="Log in")


pg.run()

st.divider()
st.caption("Hesty's combines technical signals, fundamental screens, and portfolio analysis to help "
           "you research faster. It's not an automated trading strategy, and nothing here is "
           "personalized financial advice.")
st.page_link(privacy_page, label="Privacy")
