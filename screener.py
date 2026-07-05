"""
Signalen-screener (GEEN geautomatiseerde strategie): checkt een lijst
aandelen op een RECENTE bullish Supertrend-omslag op de weekly timeframe,
zodat jij zelf -- met je eigen verdere analyse -- kan beslissen of je
long wil gaan.

Volledig zelfstandig project, los van de crypto-bot-codebase.

Standaard wordt de samenstelling van AEX + Nasdaq-100 (QQQ) automatisch
opgehaald van Wikipedia. Wil je een eigen vaste lijst (bv. je DEGIRO-
watchlist)? Zet TICKERS hieronder op een lijst i.p.v. None.

Vereist: pip install -r requirements.txt

Gebruik: python screener.py
"""
from __future__ import annotations

import io

import pandas as pd
import requests
import yfinance as yf

from indicators import supertrend, ema, resample_to_weekly, volume_ratio
from emailer import send_email, is_configured as email_is_configured

# Wikipedia blokkeert verzoeken zonder een 'normale' browser-User-Agent (403 Forbidden)
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _fetch_wikipedia_tables(url: str):
    response = requests.get(url, headers=_HEADERS, timeout=15)
    response.raise_for_status()
    # StringIO nodig omdat pd.read_html een kale string anders soms als
    # bestandsnaam/URL probeert te interpreteren i.p.v. als ruwe HTML-inhoud
    return pd.read_html(io.StringIO(response.text))

# --- Pas dit aan naar jouw eigen watchlist, of laat op None voor AEX + Nasdaq-100 ---
TICKERS = None

FALLBACK_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM", "V", "UNH",
    "ASML.AS", "ADYEN.AS", "SHELL.AS", "INGA.AS", "HEIA.AS",
    "SAP.DE", "SIE.DE", "MC.PA", "OR.PA",
]

# --- Instellingen (pas gerust aan om te 'tweaken') ---
ATR_LENGTH = 6
ATR_MULTIPLIER = 2.6
LOOKBACK_WEEKS_FOR_SIGNAL = 1
TREND_FILTER_EMA_LENGTH = 20
YEARS_OF_HISTORY = 3
BENCHMARK_LOOKBACK_WEEKS = 12
VOLUME_AVG_WEEKS = 20  # periode voor het gemiddelde volume, voor de volume-bevestiging
MIN_PRIOR_TREND_WEEKS = 10  # de voorgaande (bearish) periode moet minstens dit lang zijn geweest --
                            # filtert zigzag-ruis binnen een al lopende trend eruit
EARNINGS_RELEVANCE_WEEKS = 8  # een winst-verrassing telt alleen nog mee in de score als
                               # de cijfers niet ouder zijn dan dit -- daarna is het al 'verwerkt'  # periode waarover relatieve sterkte t.o.v. de index wordt vergeleken

BENCHMARKS = {".AS": "^AEX", ".DE": "^GDAXI", ".PA": "^FCHI"}  # index-suffix -> bijbehorende benchmark
DEFAULT_BENCHMARK = "^GSPC"  # al het overige (VS) -> S&P 500


def get_benchmark_for_ticker(ticker: str) -> str:
    for suffix, benchmark in BENCHMARKS.items():
        if ticker.endswith(suffix):
            return benchmark
    return DEFAULT_BENCHMARK


def get_trailing_return_pct(df: pd.DataFrame, weeks: int):
    """Rendement van de laatste 'weeks' weken, of None als er te weinig geschiedenis is."""
    if len(df) <= weeks:
        return None
    price_then = df["close"].iloc[-(weeks + 1)]
    price_now = df["close"].iloc[-1]
    return (price_now / price_then - 1) * 100


def fetch_benchmark_returns() -> dict:
    """Haalt voor elke benchmark-index 1x het trailing-rendement op."""
    returns = {}
    for benchmark_ticker in set(list(BENCHMARKS.values()) + [DEFAULT_BENCHMARK]):
        try:
            df_bench = fetch_weekly(benchmark_ticker)
            returns[benchmark_ticker] = get_trailing_return_pct(df_bench, BENCHMARK_LOOKBACK_WEEKS)
        except Exception as exc:
            print(f"Kon benchmark {benchmark_ticker} niet ophalen: {exc}")
            returns[benchmark_ticker] = None
    return returns


def compute_score(result: dict) -> float:
    """
    Score op een vaste schaal van 0 tot 10 -- GEEN geoptimaliseerde/
    gebacktestte formule, puur een gewogen, BEGRENSDE optelsom om je
    aandacht te sturen naar signalen die op meerdere vlakken sterk zijn.

    Opbouw (max. punten per onderdeel, totaal = 10):
    - Versheid van de omslag:              max 1,5 punten
    - ROIC-niveau + -trend:                max 1,5 punten
    - Relatieve sterkte vs. index:         max 2,5 punten
    - Volume-bevestiging:                  max 1,0 punt
    - Winst-verrassing (indien recent):    max 1,5 punten
    - Afwijking t.o.v. analisten-koersdoel: max 2,0 punten
    Bij ontbrekende data telt een onderdeel neutraal (de helft van het max.).
    """
    # --- Versheid (0-1,5 punten) ---
    freshness_score = max(0.0, (LOOKBACK_WEEKS_FOR_SIGNAL - result["weken_geleden"]) / LOOKBACK_WEEKS_FOR_SIGNAL * 1.5)

    # --- ROIC (0-1,5 punten): niveau (verzadigt bij 30%) + trend-bonus/malus ---
    if result["roic_pct"] is not None:
        level_points = min(max(result["roic_pct"], 0), 30) / 30 * 1.0
        trend_points = 0.5 if result["roic_trend"] == "stijgend" else (-0.5 if result["roic_trend"] == "dalend" else 0)
        roic_score = max(0.0, min(1.5, level_points + trend_points + 0.5))
    else:
        roic_score = 0.75

    # --- Relatieve sterkte (0-2,5 punten): begrensd tussen -20% en +20% ---
    if result["relatieve_sterkte"] is not None:
        clamped = min(max(result["relatieve_sterkte"], -20), 20)
        rs_score = (clamped + 20) / 40 * 2.5
    else:
        rs_score = 1.25

    # --- Volume-bevestiging (0-1 punt) ---
    if result.get("volume_bevestigd") is not None:
        volume_score = 1.0 if result["volume_bevestigd"] else 0.0
    else:
        volume_score = 0.5

    # --- Winst-verrassing (0-1,5 punten): alleen als recent genoeg, anders neutraal ---
    is_recent_enough = (
        result.get("weken_sinds_earnings") is not None
        and result["weken_sinds_earnings"] <= EARNINGS_RELEVANCE_WEEKS
    )
    if result.get("earnings_surprise_pct") is not None and is_recent_enough:
        clamped_surprise = min(max(result["earnings_surprise_pct"], -10), 10)
        earnings_score = (clamped_surprise + 10) / 20 * 1.5
    else:
        earnings_score = 0.75

    # --- Afwijking t.o.v. analisten-koersdoel (0-2 punten) ---
    # Negatieve afwijking = koers ONDER het koersdoel ('goedkoop') -> meer punten
    if result.get("afwijking_fair_value_pct") is not None:
        clamped_fv = min(max(result["afwijking_fair_value_pct"], -30), 30)
        fair_value_score = (30 - clamped_fv) / 60 * 2.0
    else:
        fair_value_score = 1.0

    return round(
        freshness_score + roic_score + rs_score + volume_score + earnings_score + fair_value_score, 2
    )


def _find_ticker_column(tables):
    for table in tables:
        cols_lower = [str(c).lower() for c in table.columns]
        for candidate in ["ticker", "symbol", "ticker symbol"]:
            if candidate in cols_lower:
                col_name = table.columns[cols_lower.index(candidate)]
                tickers = table[col_name].astype(str).str.strip().tolist()
                if len(tickers) >= 10:
                    return tickers
    return None


def fetch_aex_tickers():
    try:
        tables = _fetch_wikipedia_tables("https://en.wikipedia.org/wiki/AEX_index")
        tickers = _find_ticker_column(tables)
        if tickers:
            return [t if t.endswith(".AS") else f"{t}.AS" for t in tickers]
    except Exception as exc:
        print(f"Kon AEX-samenstelling niet automatisch ophalen: {exc}")
    return None


def fetch_nasdaq100_tickers():
    try:
        tables = _fetch_wikipedia_tables("https://en.wikipedia.org/wiki/Nasdaq-100")
        tickers = _find_ticker_column(tables)
        if tickers:
            return [t.replace(".", "-") for t in tickers]
    except Exception as exc:
        print(f"Kon Nasdaq-100-samenstelling niet automatisch ophalen: {exc}")
    return None


def fetch_sp500_tickers():
    try:
        tables = _fetch_wikipedia_tables("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        tickers = _find_ticker_column(tables)
        if tickers:
            return [t.replace(".", "-") for t in tickers]  # bv. BRK.B -> BRK-B (Yahoo-notatie)
    except Exception as exc:
        print(f"Kon S&P 500-samenstelling niet automatisch ophalen: {exc}")
    return None


def fetch_dax_tickers():
    try:
        tables = _fetch_wikipedia_tables("https://en.wikipedia.org/wiki/DAX")
        tickers = _find_ticker_column(tables)
        if tickers:
            return [t if t.endswith(".DE") else f"{t}.DE" for t in tickers]
    except Exception as exc:
        print(f"Kon DAX-samenstelling niet automatisch ophalen: {exc}")
    return None


def fetch_cac40_tickers():
    try:
        tables = _fetch_wikipedia_tables("https://en.wikipedia.org/wiki/CAC_40")
        tickers = _find_ticker_column(tables)
        if tickers:
            return [t if t.endswith(".PA") else f"{t}.PA" for t in tickers]
    except Exception as exc:
        print(f"Kon CAC40-samenstelling niet automatisch ophalen: {exc}")
    return None


def build_ticker_list():
    tickers = []

    aex = fetch_aex_tickers()
    if aex:
        print(f"AEX: {len(aex)} tickers opgehaald.")
        tickers += aex
    else:
        print("AEX: automatisch ophalen mislukt, fallback-lijst gebruikt voor dit deel.")

    nasdaq100 = fetch_nasdaq100_tickers()
    if nasdaq100:
        print(f"Nasdaq-100 (QQQ): {len(nasdaq100)} tickers opgehaald.")
        tickers += nasdaq100
    else:
        print("Nasdaq-100: automatisch ophalen mislukt, fallback-lijst gebruikt voor dit deel.")

    sp500 = fetch_sp500_tickers()
    if sp500:
        print(f"S&P 500: {len(sp500)} tickers opgehaald.")
        tickers += sp500
    else:
        print("S&P 500: automatisch ophalen mislukt, fallback-lijst gebruikt voor dit deel.")

    dax = fetch_dax_tickers()
    if dax:
        print(f"DAX: {len(dax)} tickers opgehaald.")
        tickers += dax
    else:
        print("DAX: automatisch ophalen mislukt, fallback-lijst gebruikt voor dit deel.")

    cac40 = fetch_cac40_tickers()
    if cac40:
        print(f"CAC 40: {len(cac40)} tickers opgehaald.")
        tickers += cac40
    else:
        print("CAC 40: automatisch ophalen mislukt, fallback-lijst gebruikt voor dit deel.")

    if not tickers:
        print("Alle ophaal-pogingen mislukt -- volledige fallback-lijst gebruikt.")
        tickers = FALLBACK_TICKERS

    return sorted(set(tickers))


def fetch_weekly(ticker: str, years: int = YEARS_OF_HISTORY) -> pd.DataFrame:
    df = yf.download(ticker, period=f"{years}y", interval="1d", auto_adjust=True, progress=False)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]]
    return resample_to_weekly(df)


def get_roic_data(ticker: str) -> dict:
    """
    Schat ROIC (Return On Invested Capital) en de trend t.o.v. vorig jaar,
    op basis van yfinance's jaarlijkse financiele overzichten.

    ROIC = NOPAT / Invested Capital
      NOPAT       = Operating Income * (1 - belastingtarief)  [we gebruiken 25% als redelijke aanname]
      Invested Capital = Total Debt + Eigen Vermogen - Cash

    LET OP: dit is een SCHATTING, geen exacte boekhoudkundige ROIC (o.a. door
    de vaste belastingtarief-aanname), en yfinance's fundamentele data is niet
    voor elk aandeel compleet. Gebruik dit als extra context, niet als
    doorslaggevend cijfer.
    """
    try:
        ticker_obj = yf.Ticker(ticker)
        financials = ticker_obj.financials
        balance_sheet = ticker_obj.balance_sheet

        if financials is None or financials.empty or balance_sheet is None or balance_sheet.empty:
            return {"roic": None, "roic_vorig_jaar": None, "roic_trend": "onbekend"}

        def get_value(df, possible_row_names, period_col, default=0.0):
            for name in possible_row_names:
                if name in df.index:
                    val = df.loc[name, period_col]
                    if pd.notna(val):
                        return float(val)
            return default

        def compute_roic_for_period(period_col):
            operating_income = get_value(financials, ["Operating Income", "OperatingIncome"], period_col, default=None)
            if operating_income is None:
                return None

            tax_rate = 0.25
            nopat = operating_income * (1 - tax_rate)

            total_debt = get_value(balance_sheet, ["Total Debt", "TotalDebt"], period_col, default=0.0)
            total_equity = get_value(
                balance_sheet, ["Stockholders Equity", "Total Equity Gross Minority Interest",
                                "StockholdersEquity"], period_col, default=None
            )
            if total_equity is None:
                return None
            cash = get_value(
                balance_sheet, ["Cash And Cash Equivalents", "CashAndCashEquivalents"], period_col, default=0.0
            )

            invested_capital = total_debt + total_equity - cash
            if invested_capital <= 0:
                return None
            return nopat / invested_capital

        periods = list(financials.columns)  # meest recente periode eerst
        roic_now = compute_roic_for_period(periods[0]) if len(periods) > 0 else None
        roic_prev = compute_roic_for_period(periods[1]) if len(periods) > 1 else None

        trend = "onbekend"
        if roic_now is not None and roic_prev is not None:
            trend = "stijgend" if roic_now > roic_prev else "dalend"

        return {"roic": roic_now, "roic_vorig_jaar": roic_prev, "roic_trend": trend}
    except Exception as exc:
        print(f"    (ROIC voor {ticker} kon niet berekend worden: {exc})")
        return {"roic": None, "roic_vorig_jaar": None, "roic_trend": "onbekend"}


def get_recent_news(ticker: str, max_items: int = 3, days_back: int = 7) -> list:
    """
    Haalt de meest recente nieuwsberichten op voor een ticker via Yahoo
    Finance (yfinance), gefilterd op de laatste 'days_back' dagen.

    LET OP: yfinance's nieuws-dataformaat is in het verleden veranderd
    tussen versies -- deze functie probeert zowel de oudere als nieuwere
    veldnamen, en geeft gewoon een lege lijst terug als niets herkend wordt
    (i.p.v. te crashen).
    """
    try:
        ticker_obj = yf.Ticker(ticker)
        news_items = ticker_obj.news or []
    except Exception as exc:
        print(f"    (Nieuws voor {ticker} kon niet opgehaald worden: {exc})")
        return []

    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days_back)
    results = []

    for item in news_items:
        # Nieuwere yfinance-versies nesten de velden onder 'content'; oudere niet.
        content = item.get("content", item) if isinstance(item, dict) else {}

        title = content.get("title") or item.get("title")
        provider = content.get("provider") if isinstance(content.get("provider"), dict) else {}
        publisher = provider.get("displayName") or item.get("publisher")
        canonical = content.get("canonicalUrl") if isinstance(content.get("canonicalUrl"), dict) else {}
        link = canonical.get("url") or item.get("link")
        pub_time = content.get("pubDate") or item.get("providerPublishTime")

        if pub_time is None or title is None:
            continue

        try:
            pub_dt = (pd.Timestamp(pub_time, unit="s", tz="UTC")
                      if isinstance(pub_time, (int, float)) else pd.Timestamp(pub_time, tz="UTC"))
        except Exception:
            continue

        if pub_dt < cutoff:
            continue

        results.append({"title": title, "publisher": publisher or "onbekend", "link": link, "published": pub_dt})

    results.sort(key=lambda x: x["published"], reverse=True)
    return results[:max_items]


def get_earnings_surprise(ticker: str) -> dict:
    """
    Haalt de meest recente winst-verrassing op: rapporteerde het bedrijf
    beter of slechter dan verwacht bij de laatste kwartaalcijfers?

    Achterliggend idee: 'Post-Earnings-Announcement Drift' is een van de
    best gedocumenteerde patronen in de financiele literatuur -- aandelen
    die beter dan verwacht rapporteren, presteren daarna vaak nog weken
    tot maanden relatief beter.

    LET OP: yfinance's earnings-data is niet voor elk aandeel compleet,
    vooral niet-Amerikaanse aandelen missen dit vaker.
    """
    try:
        ticker_obj = yf.Ticker(ticker)
        try:
            df = ticker_obj.get_earnings_dates(limit=8)
        except Exception:
            df = getattr(ticker_obj, "earnings_dates", None)

        if df is None or df.empty:
            return {"surprise_pct": None, "beat": None, "earnings_date": None}

        reported_col = next((c for c in df.columns if "Reported" in str(c)), None)
        surprise_col = next((c for c in df.columns if "Surprise" in str(c)), None)
        if reported_col is None:
            return {"surprise_pct": None, "beat": None, "earnings_date": None}

        df = df.dropna(subset=[reported_col])
        if df.empty:
            return {"surprise_pct": None, "beat": None, "earnings_date": None}

        df = df.sort_index(ascending=False)  # meest recente gerapporteerde cijfers eerst
        latest = df.iloc[0]

        surprise_pct = float(latest[surprise_col]) if surprise_col and pd.notna(latest[surprise_col]) else None
        beat = (surprise_pct is not None and surprise_pct > 0)

        return {"surprise_pct": surprise_pct, "beat": beat, "earnings_date": df.index[0]}
    except Exception as exc:
        print(f"    (Earnings-data voor {ticker} kon niet opgehaald worden: {exc})")
        return {"surprise_pct": None, "beat": None, "earnings_date": None}


def get_prior_trend_duration(df: pd.DataFrame, flip_index) -> int:
    """
    Hoeveel weken duurde de trend ONMIDDELLIJK VOORAFGAAND aan deze omslag?
    (dus: hoe lang was de bearish periode vlak vóór deze bullish-flip)

    Dit onderscheidt een 'verse' omslag na een langere daling/zijwaartse
    periode van zigzag-ruis binnen een al lopende trend (waarbij een korte
    terugval steeds snel gevolgd wordt door weer een bullish-omslag).
    """
    position = df.index.get_loc(flip_index)
    if position == 0:
        return 0

    prior_trend = df["trend_dir"].iloc[position - 1]
    count = 0
    i = position - 1
    while i >= 0 and df["trend_dir"].iloc[i] == prior_trend:
        count += 1
        i -= 1
    return count


def get_fair_value_estimate(ticker: str) -> dict:
    """
    Gebruikt de gemiddelde analisten-koersdoel (via yfinance) als schatting
    van 'fair value'. Dit is GEEN eigen berekende waardering (geen DCF/
    P/E-model), maar de consensus-verwachting van professionele analisten
    -- transparanter dan een zelfverzonnen formule met eigen aannames.

    LET OP: analisten-koersdoelen zijn zelf ook maar schattingen (met eigen
    aannames, en soms verouderd), en niet voor elk aandeel beschikbaar --
    vooral kleinere en niet-Amerikaanse aandelen missen dit vaker.
    """
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        target = info.get("targetMeanPrice")
        current = info.get("currentPrice") or info.get("regularMarketPrice")

        if target is None or current is None:
            return {"fair_value": None, "afwijking_pct": None}

        afwijking_pct = (current / target - 1) * 100
        return {"fair_value": round(float(target), 2), "afwijking_pct": round(afwijking_pct, 1)}
    except Exception as exc:
        print(f"    (Fair value voor {ticker} kon niet opgehaald worden: {exc})")
        return {"fair_value": None, "afwijking_pct": None}


def check_ticker(ticker: str, benchmark_returns: dict):
    try:
        df = fetch_weekly(ticker)
    except Exception as exc:
        print(f"  {ticker}: fout bij ophalen ({exc})")
        return None

    min_needed = max(ATR_LENGTH, TREND_FILTER_EMA_LENGTH) + 5
    if df.empty or len(df) < min_needed:
        print(f"  {ticker}: te weinig data (nodig: {min_needed}, gekregen: {len(df)})")
        return None

    st = supertrend(df, length=ATR_LENGTH, multiplier=ATR_MULTIPLIER)
    df = df.copy()
    df["trend_dir"] = st["trend_dir"]
    df["ema_trend"] = ema(df["close"], TREND_FILTER_EMA_LENGTH)
    df["volume_ratio"] = volume_ratio(df["volume"], length=VOLUME_AVG_WEEKS)

    flips = df.index[(df["trend_dir"] == 1) & (df["trend_dir"].shift(1) == -1)]
    if len(flips) == 0:
        return None

    last_flip = flips[-1]
    weeks_since_flip = len(df.loc[last_flip:]) - 1
    if weeks_since_flip > LOOKBACK_WEEKS_FOR_SIGNAL:
        return None

    prior_trend_weeks = get_prior_trend_duration(df, last_flip)
    if prior_trend_weeks < MIN_PRIOR_TREND_WEEKS:
        return None  # waarschijnlijk zigzag-ruis binnen een al lopende trend, geen 'verse' omslag

    flip_row = df.loc[last_flip]
    latest_row = df.iloc[-1]

    # Relatieve sterkte: hoe deed dit aandeel het t.o.v. de relevante index,
    # over dezelfde trailing periode? Positief = sterker dan de markt.
    benchmark_ticker = get_benchmark_for_ticker(ticker)
    own_return = get_trailing_return_pct(df, BENCHMARK_LOOKBACK_WEEKS)
    benchmark_return = benchmark_returns.get(benchmark_ticker)
    relative_strength = (
        round(own_return - benchmark_return, 2)
        if own_return is not None and benchmark_return is not None
        else None
    )

    # Volume-bevestiging: was het volume op de omslag-week hoger dan gemiddeld?
    volume_confirmed = (
        bool(flip_row["volume_ratio"] > 1) if pd.notna(flip_row["volume_ratio"]) else None
    )

    result = {
        "ticker": ticker,
        "flip_date": last_flip.date(),
        "weken_geleden": weeks_since_flip,
        "voorgaande_trend_weken": prior_trend_weeks,
        "prijs_bij_omslag": round(float(flip_row["close"]), 2),
        "prijs_nu": round(float(latest_row["close"]), 2),
        "sinds_omslag_pct": round((latest_row["close"] / flip_row["close"] - 1) * 100, 2),
        "boven_ema20": bool(latest_row["close"] > latest_row["ema_trend"]),
        "benchmark": benchmark_ticker,
        "relatieve_sterkte": relative_strength,
        "volume_bevestigd": volume_confirmed,
    }

    # ROIC en winst-verrassing alleen berekenen voor tickers die al een
    # technisch signaal hebben (bespaart onnodige extra aanroepen)
    roic_data = get_roic_data(ticker)
    result["roic_pct"] = round(roic_data["roic"] * 100, 1) if roic_data["roic"] is not None else None
    result["roic_trend"] = roic_data["roic_trend"]

    earnings_data = get_earnings_surprise(ticker)
    result["earnings_surprise_pct"] = (
        round(earnings_data["surprise_pct"], 1) if earnings_data["surprise_pct"] is not None else None
    )
    result["earnings_beat"] = earnings_data["beat"]
    result["earnings_date"] = (
        earnings_data["earnings_date"].date() if earnings_data["earnings_date"] is not None else None
    )
    if earnings_data["earnings_date"] is not None:
        days_since = (pd.Timestamp.now(tz=earnings_data["earnings_date"].tz) - earnings_data["earnings_date"]).days
        result["weken_sinds_earnings"] = max(0, days_since // 7)
    else:
        result["weken_sinds_earnings"] = None

    fair_value_data = get_fair_value_estimate(ticker)
    result["fair_value"] = fair_value_data["fair_value"]
    result["afwijking_fair_value_pct"] = fair_value_data["afwijking_pct"]

    result["score"] = compute_score(result)

    return result


def build_email_body(df_hits: pd.DataFrame) -> tuple:
    lines = [f"Supertrend-screener: {len(df_hits)} signalen gevonden (gesorteerd op score, hoogste eerst).\n"]
    for _, row in df_hits.iterrows():
        roic_txt = f"{row['roic_pct']:+.1f}% ({row['roic_trend']})" if row['roic_pct'] is not None else "onbekend"
        rs_txt = f"{row['relatieve_sterkte']:+.2f}% vs {row['benchmark']}" if row['relatieve_sterkte'] is not None else "onbekend"
        vol_txt = ("ja" if row['volume_bevestigd'] is True else "nee" if row['volume_bevestigd'] is False else "onbekend")
        earn_txt = (
            f"{row['earnings_surprise_pct']:+.1f}% op {row['earnings_date']} ({row['weken_sinds_earnings']}w geleden)"
            if row['earnings_surprise_pct'] is not None else "onbekend"
        )
        fv_txt = (
            f"{row['fair_value']} (koers {row['afwijking_fair_value_pct']:+.1f}% t.o.v. dit koersdoel)"
            if row['fair_value'] is not None else "onbekend"
        )
        lines.append(
            f"- [score {row['score']}] {row['ticker']}: omslag op {row['flip_date']} "
            f"({row['weken_geleden']} week(en) geleden, na {row['voorgaande_trend_weken']} weken bearish), "
            f"prijs toen {row['prijs_bij_omslag']}, "
            f"nu {row['prijs_nu']} ({row['sinds_omslag_pct']:+.2f}%), "
            f"boven EMA20: {'ja' if row['boven_ema20'] else 'nee'}, "
            f"ROIC: {roic_txt}, relatieve sterkte: {rs_txt}, "
            f"volume-bevestiging: {vol_txt}, winst-verrassing: {earn_txt}, "
            f"analisten-koersdoel: {fv_txt}"
        )
    text_body = "\n".join(lines)
    text_body += "\n\nDit is een screener, geen koopadvies. Doe altijd je eigen verdere afweging."

    def _format_row_html(r):
        roic_str = f"{r['roic_pct']:+.1f}%" if r['roic_pct'] is not None else "-"
        rs_str = f"{r['relatieve_sterkte']:+.2f}%" if r['relatieve_sterkte'] is not None else "-"
        vol_str = "ja" if r['volume_bevestigd'] is True else ("nee" if r['volume_bevestigd'] is False else "-")
        earn_str = (
            f"{r['earnings_surprise_pct']:+.1f}% ({r['weken_sinds_earnings']}w geleden)"
            if r['earnings_surprise_pct'] is not None else "-"
        )
        fv_str = (
            f"{r['fair_value']} ({r['afwijking_fair_value_pct']:+.1f}%)"
            if r['fair_value'] is not None else "-"
        )
        return (
            f"<tr><td><b>{r['score']}</b></td><td>{r['ticker']}</td><td>{r['flip_date']}</td><td>{r['weken_geleden']}</td>"
            f"<td>{r['voorgaande_trend_weken']}</td>"
            f"<td>{r['prijs_bij_omslag']}</td><td>{r['prijs_nu']}</td>"
            f"<td>{r['sinds_omslag_pct']:+.2f}%</td><td>{'ja' if r['boven_ema20'] else 'nee'}</td>"
            f"<td>{roic_str}</td><td>{r['roic_trend']}</td><td>{rs_str}</td>"
            f"<td>{vol_str}</td><td>{earn_str}</td><td>{fv_str}</td></tr>"
        )

    rows_html = "".join(_format_row_html(r) for _, r in df_hits.iterrows())
    html_body = f"""
    <h3>Supertrend-screener: {len(df_hits)} signalen gevonden</h3>
    <p>Gesorteerd op score (hoogste eerst) -- combinatie van versheid, ROIC-niveau/-trend,
    relatieve sterkte, volume-bevestiging, en winst-verrassing.</p>
    <table border="1" cellpadding="5" cellspacing="0">
      <tr><th>Score</th><th>Ticker</th><th>Omslag-datum</th><th>Weken geleden</th>
          <th>Voorgaande trend (weken)</th>
          <th>Prijs bij omslag</th><th>Prijs nu</th><th>Sinds omslag</th><th>Boven EMA20</th>
          <th>ROIC</th><th>ROIC-trend</th><th>Rel. sterkte</th>
          <th>Volume-bevestiging</th><th>Winst-verrassing</th><th>Analisten-koersdoel (afwijking)</th></tr>
      {rows_html}
    </table>
    <p><i>Dit is een screener, geen koopadvies. Doe altijd je eigen verdere afweging.</i></p>
    <p><i>ROIC en winst-verrassing zijn schattingen op basis van yfinance-data, niet elke
    ticker heeft complete gegevens. De score is een simpele, ongeoptimaliseerde optelsom --
    geen gevalideerde voorspeller.</i></p>
    """
    return text_body, html_body


def main() -> None:
    tickers = TICKERS if TICKERS is not None else build_ticker_list()

    print("Benchmark-rendementen ophalen (voor relatieve sterkte)...")
    benchmark_returns = fetch_benchmark_returns()
    for bench, ret in benchmark_returns.items():
        print(f"  {bench}: {f'{ret:+.2f}%' if ret is not None else 'onbekend'} "
              f"(laatste {BENCHMARK_LOOKBACK_WEEKS} weken)")

    print(f"\nScreening {len(tickers)} tickers op recente bullish Supertrend-omslag "
          f"(weekly, ATR-periode {ATR_LENGTH}, multiplier {ATR_MULTIPLIER})...")
    print("(Dit kan enkele minuten duren bij een grote lijst zoals AEX + Nasdaq-100.)\n")

    hits = []
    for ticker in tickers:
        result = check_ticker(ticker, benchmark_returns)
        if result:
            hits.append(result)
            print(f"  {ticker}: SIGNAAL ({result['weken_geleden']} week(en) geleden, score {result['score']})")
        else:
            print(f"  {ticker}: geen recent signaal")

    if not hits:
        print(f"\nGeen enkel aandeel had de afgelopen {LOOKBACK_WEEKS_FOR_SIGNAL} "
              f"week(en) een bullish omslag.")
        if email_is_configured():
            send_email(
                subject="Supertrend-screener: geen signalen deze week",
                body_text=f"Geen van de {len(tickers)} gescreende tickers had de afgelopen "
                          f"{LOOKBACK_WEEKS_FOR_SIGNAL} week(en) een bullish Supertrend-omslag.",
            )
        return

    df_hits = pd.DataFrame(hits)
    df_hits.sort_values("score", ascending=False, inplace=True)

    print(f"\n=== {len(hits)} SIGNALEN GEVONDEN ===\n")
    # Voor de terminal-weergave: NaN in roic_pct netjes als 'onbekend' tonen
    # (de CSV-export blijft wel de kale numerieke waarde/NaN bevatten, handig
    # als je de data later zelf verder wil verwerken)
    display_df = df_hits.copy()
    display_df["roic_pct"] = display_df["roic_pct"].apply(lambda v: "onbekend" if pd.isna(v) else v)
    display_df["relatieve_sterkte"] = display_df["relatieve_sterkte"].apply(lambda v: "onbekend" if pd.isna(v) else v)
    display_df["volume_bevestigd"] = display_df["volume_bevestigd"].apply(lambda v: "onbekend" if pd.isna(v) else v)
    display_df["earnings_surprise_pct"] = display_df["earnings_surprise_pct"].apply(lambda v: "onbekend" if pd.isna(v) else v)
    display_df["weken_sinds_earnings"] = display_df["weken_sinds_earnings"].apply(lambda v: "onbekend" if pd.isna(v) else v)
    display_df["fair_value"] = display_df["fair_value"].apply(lambda v: "onbekend" if pd.isna(v) else v)
    display_df["afwijking_fair_value_pct"] = display_df["afwijking_fair_value_pct"].apply(lambda v: "onbekend" if pd.isna(v) else v)
    print(display_df.to_string(index=False))

    df_hits.to_csv("supertrend_signals.csv", index=False)
    print("\nOpgeslagen in 'supertrend_signals.csv'.")
    print("\nLET OP: dit is een screener, geen koopadvies. Doe altijd je eigen")
    print("verdere afweging (fundamentals, nieuws, sector, waardering) voordat")
    print("je op basis hiervan een positie overweegt.")

    if email_is_configured():
        text_body, html_body = build_email_body(df_hits)
        send_email(
            subject=f"Supertrend-screener: {len(hits)} nieuwe signalen",
            body_text=text_body,
            body_html=html_body,
        )
    else:
        print("\n(E-mail niet verstuurd: EMAIL_ADDRESS/EMAIL_APP_PASSWORD/EMAIL_TO "
              "nog niet ingesteld in .env.)")


if __name__ == "__main__":
    main()
