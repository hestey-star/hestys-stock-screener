"""
Streamlit-ONAFHANKELIJKE kopie van de Daily Radar-databerekening --
zelfde patroon als macro_events.py: gebruikt door zowel de Streamlit-app
(dashboard.py, als live-fallback + door de handmatige 'Refresh data'-knop)
als door het geplande achtergrond-script (daily_radar_batch.py, via
GitHub Actions elke 6 uur), zonder dat dat laatste script een
Streamlit-runtime nodig heeft.

BELANGRIJK: dashboard.py heeft voor het live/fallback-gebruik grotendeels
DEZELFDE logica als hier, met Streamlit-specifieke caching (@st.cache_data)
op de losse yfinance-aanroepen. Dat is een bewuste keuze (geen risico op
het al-werkende dashboard door het te laten IMPORTEREN vanuit dit
bestand), maar betekent wel: wijzig je hier iets inhoudelijks, wijzig het
dan ook in dashboard.py's eigen kopie (en andersom).

Geeft overal STRUCTURED DATA terug (dicts/lists), nooit kant-en-klare
HTML -- dat is een UI-detail dat bij dashboard.py's eigen rendering hoort
(iconen/kleuren), niet bij deze data-laag. Zo is de output ook direct
JSON-serialiseerbaar voor opslag in de cache-tabel.
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime

import pandas as pd
import yfinance as yf

from macro_events import get_todays_macro_events

# --- Sector/thema-ETF's -- zelfde lijsten als dashboard.py, bewust hier
# gedupliceerd (zie module-docstring hierboven). ---
US_SECTOR_ETFS = {
    "Technology": "XLK", "Financials": "XLF", "Energy": "XLE", "Health Care": "XLV",
    "Consumer Discretionary": "XLY", "Consumer Staples": "XLP", "Industrials": "XLI",
    "Materials": "XLB", "Utilities": "XLU", "Real Estate": "XLRE", "Communication Services": "XLC",
}
EU_SECTOR_ETFS = {
    "Banks": "EXV1.DE", "Technology": "EXV3.DE", "Health Care": "EXV4.DE",
    "Telecommunications": "EXV2.DE", "Oil & Gas": "EXH1.DE", "Food & Beverage": "EXH3.DE",
    "Industrial Goods & Services": "EXH4.DE", "Utilities": "EXH9.DE",
    "Basic Resources": "EXV6.DE", "Automobiles & Parts": "EXV5.DE",
}
THEME_ETFS = {
    "Robotics & AI": "BOTZ", "Clean Energy": "ICLN", "Cybersecurity": "CIBR",
    "Semiconductors": "SMH", "Genomics & Biotech": "ARKG",
    "Cloud / SaaS": "WCLD", "Data Centers": "DTCR", "Aerospace & Defense": "ITA",
    "Quantum Computing": "QTUM", "Nuclear Energy": "NLR", "Space": "ARKX",
    "Drones": "UAV", "Materials & Critical Minerals": "REMX", "Fintech": "FINX",
    "Infrastructure": "PAVE", "Power & Utilities": "XLU",
    "Crypto (Top 10)": "HODLX.SW", "Precious Metals": "GLTR",
}
THEME_ROTATION_WINDOW_DAYS = 21


# --- Kale yfinance-aanroepen, GEEN @st.cache_data hier (geen Streamlit-
# runtime beschikbaar in een batch-script) -- elke ticker wordt in de
# praktijk toch maar 1x per script-run aangeroepen, dus caching binnen
# 1 run levert weinig op. ---
def _ticker_history(ticker: str, period: str = None):
    try:
        return yf.Ticker(ticker).history(period=period)
    except Exception:
        return pd.DataFrame()


def _ticker_info(ticker: str) -> dict:
    try:
        return yf.Ticker(ticker).info
    except Exception:
        return {}


def _ticker_earnings_dates(ticker: str, limit: int = 8):
    try:
        return yf.Ticker(ticker).get_earnings_dates(limit=limit)
    except Exception:
        return None


def _currency_symbol_for_ticker(ticker: str) -> str:
    try:
        info = _ticker_info(ticker)
        currency = info.get("currency", "EUR")
    except Exception:
        currency = "EUR"
    symbol_map = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CHF": "CHF ", "CAD": "C$"}
    return symbol_map.get(currency, f"{currency} ")


def get_file_last_commit_date(path: str) -> str:
    """Zelfde als dashboard.py's versie: datum (YYYY-MM-DD) van de laatste git-commit van dit bestand, of None."""
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


def build_sector_rotation(region: str = "US", window_days: int = THEME_ROTATION_WINDOW_DAYS) -> list:
    fetch_period = f"{window_days + 15}d"
    etfs = US_SECTOR_ETFS if region == "US" else EU_SECTOR_ETFS
    results = []
    for sector, ticker in etfs.items():
        try:
            hist = _ticker_history(ticker, period=fetch_period)
            if hist is None or hist.empty:
                continue
            valid_closes = hist["Close"].dropna()
            if len(valid_closes) > window_days:
                ret = (valid_closes.iloc[-1] / valid_closes.iloc[-1 - window_days] - 1) * 100
                results.append({"sector": sector, "ticker": ticker, "return_pct": round(ret, 2)})
        except Exception:
            continue
    results.sort(key=lambda x: x["return_pct"], reverse=True)
    return results


def build_theme_rotation(window_days: int = THEME_ROTATION_WINDOW_DAYS) -> list:
    fetch_period = f"{window_days + 15}d"
    results = []
    for theme, ticker in THEME_ETFS.items():
        try:
            hist = _ticker_history(ticker, period=fetch_period)
            if hist is None or hist.empty:
                continue
            valid_closes = hist["Close"].dropna()
            if len(valid_closes) > window_days:
                ret = (valid_closes.iloc[-1] / valid_closes.iloc[-1 - window_days] - 1) * 100
                results.append({"theme": theme, "ticker": ticker, "return_pct": round(ret, 2)})
        except Exception:
            continue
    results.sort(key=lambda x: x["return_pct"], reverse=True)
    return results


def get_sector_theme_threshold_alerts() -> list:
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


def get_concentration_alert(holdings: list, max_position_pct: float = 25.0):
    total_value = sum(h.get("position_value") or 0 for h in holdings)
    if total_value <= 0:
        return None
    largest = max(holdings, key=lambda h: h.get("position_value") or 0)
    largest_pct = (largest.get("position_value") or 0) / total_value * 100
    if largest_pct > max_position_pct:
        return f"<b>{largest['naam']}</b> is now {largest_pct:.0f}% of your portfolio, above your {max_position_pct:.0f}% target."
    return None


def build_opportunities_today(holdings: list, watchlist_items: list, include_weekly: bool = True) -> dict:
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
        # Een paar ECHTE tickersymbolen uit de nieuwe-ideeen-set, voor het
        # 'Top hits: ...'-snippet op Today -- bewust GEEN bedrijfsnaam of
        # 'stijl' (Value/Growth) erbij verzonnen: de screener-CSV's hebben
        # geen betrouwbare naam-kolom (Discover toont deze signalen ook
        # gewoon op tickersymbool), dus alleen het symbool zelf, nooit
        # nepdata.
        "new_opportunity_tickers": sorted(new_opportunities)[:3],
    }


def get_upcoming_ex_dividend_dates(holdings: list, market_data: dict, days_ahead: int = 5, max_items: int = 3) -> list:
    today = datetime.now().date()
    results = []
    for h in holdings:
        ticker = h["ticker"]
        if ticker in market_data:
            ex_div_str = market_data[ticker].get("ex_dividend_date")
        else:
            ex_div_str = None
            try:
                info = _ticker_info(ticker)
                ex_div_unix = info.get("exDividendDate")
                if ex_div_unix:
                    ex_div_str = pd.Timestamp(ex_div_unix, unit="s").date().isoformat()
            except Exception:
                pass
        if not ex_div_str:
            continue
        try:
            ex_div_date = pd.Timestamp(ex_div_str).date()
            days_until = (ex_div_date - today).days
            if 0 <= days_until <= days_ahead:
                results.append({"naam": h["naam"], "ticker": ticker,
                                 "ex_div_date": str(ex_div_date), "days_until": days_until})
        except Exception:
            continue
    results.sort(key=lambda r: r["days_until"])
    return results[:max_items]


def get_todays_portfolio_earnings(tracked_items: list, market_data: dict, max_items: int = 3) -> list:
    today = datetime.now().date()
    results = []
    for item in tracked_items:
        ticker = item["ticker"]
        try:
            if ticker in market_data:
                next_date_str = market_data[ticker].get("next_earnings_date")
                if next_date_str and pd.Timestamp(next_date_str).date() == today:
                    results.append({"naam": item["naam"], "ticker": ticker})
            else:
                dates_df = _ticker_earnings_dates(ticker, limit=8)
                if dates_df is None or dates_df.empty:
                    continue
                for earnings_date in dates_df.index:
                    if earnings_date.date() == today:
                        results.append({"naam": item["naam"], "ticker": ticker})
                        break
        except Exception:
            continue
        if len(results) >= max_items:
            break
    return results[:max_items]


def get_upcoming_portfolio_earnings(tracked_items: list, market_data: dict, days_ahead: int = 5, max_items: int = 3) -> list:
    today = datetime.now().date()
    results = []
    for item in tracked_items:
        ticker = item["ticker"]
        try:
            if ticker in market_data:
                next_date_str = market_data[ticker].get("next_earnings_date")
                if next_date_str:
                    earnings_date = pd.Timestamp(next_date_str).date()
                    days_until = (earnings_date - today).days
                    if 1 <= days_until <= days_ahead:
                        results.append({"naam": item["naam"], "ticker": ticker,
                                         "earnings_date": str(earnings_date), "days_until": days_until})
            else:
                dates_df = _ticker_earnings_dates(ticker, limit=8)
                if dates_df is None or dates_df.empty:
                    continue
                for earnings_date_ts in dates_df.index:
                    days_until = (earnings_date_ts.date() - today).days
                    if 1 <= days_until <= days_ahead:
                        results.append({"naam": item["naam"], "ticker": ticker,
                                         "earnings_date": str(earnings_date_ts.date()), "days_until": days_until})
                        break
        except Exception:
            continue
    results.sort(key=lambda r: r["days_until"])
    return results[:max_items]


def get_recent_earnings_surprises_for_tracked_items(tracked_items: list, market_data: dict, max_days_old: int = 7, max_items: int = 3) -> list:
    today = datetime.now().date()
    results = []
    for item in tracked_items:
        ticker = item["ticker"]
        try:
            if ticker in market_data:
                last_date_str = market_data[ticker].get("last_earnings_date")
                surprise_pct = market_data[ticker].get("last_earnings_surprise_pct")
                if last_date_str and surprise_pct is not None:
                    days_since = (today - pd.Timestamp(last_date_str).date()).days
                    if 0 <= days_since <= max_days_old:
                        results.append({
                            "naam": item["naam"], "ticker": ticker,
                            "earnings_date": str(pd.Timestamp(last_date_str).date()), "surprise_pct": float(surprise_pct),
                            "beat": surprise_pct >= 0,
                        })
            else:
                dates_df = _ticker_earnings_dates(ticker, limit=8)
                if dates_df is None or dates_df.empty or "Surprise(%)" not in dates_df.columns:
                    continue
                for earnings_date, row in dates_df.iterrows():
                    days_since = (today - earnings_date.date()).days
                    if not (0 <= days_since <= max_days_old):
                        continue
                    row_surprise = row.get("Surprise(%)")
                    if pd.isna(row_surprise):
                        continue
                    results.append({
                        "naam": item["naam"], "ticker": ticker,
                        "earnings_date": str(earnings_date.date()), "surprise_pct": float(row_surprise),
                        "beat": row_surprise >= 0,
                    })
                    break
        except Exception:
            continue
    results.sort(key=lambda r: abs(r["surprise_pct"]), reverse=True)
    return results[:max_items]


def get_52_week_records(holdings: list, market_data: dict, max_items: int = 3) -> list:
    results = []
    for h in holdings:
        ticker = h["ticker"]
        if ticker in market_data:
            high_52wk = market_data[ticker].get("fifty_two_week_high")
            low_52wk = market_data[ticker].get("fifty_two_week_low")
            current_price = market_data[ticker].get("current_price")
        else:
            high_52wk = low_52wk = current_price = None

        if current_price is None:
            try:
                info = _ticker_info(ticker)
                if high_52wk is None:
                    high_52wk = info.get("fiftyTwoWeekHigh")
                if low_52wk is None:
                    low_52wk = info.get("fiftyTwoWeekLow")
                current_price = info.get("currentPrice") or info.get("regularMarketPrice")
                if current_price is None:
                    fallback_hist = _ticker_history(ticker, period="5d")
                    if fallback_hist is not None and not fallback_hist.empty:
                        current_price = float(fallback_hist["Close"].iloc[-1])
            except Exception:
                continue
        if current_price is None:
            continue
        if high_52wk and current_price >= high_52wk:
            results.append({"naam": h["naam"], "ticker": ticker, "type": "high"})
        elif low_52wk and current_price <= low_52wk:
            results.append({"naam": h["naam"], "ticker": h["ticker"], "type": "low"})
    return results[:max_items]


def get_deep_dive_triggers_hit(user_email: str, max_items: int = 5) -> list:
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
                info = _ticker_info(ticker)
                current_price = info.get("currentPrice") or info.get("regularMarketPrice")
                if current_price is None:
                    fallback_hist = _ticker_history(ticker, period="5d")
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


def get_earnings_surprises_from_signals(max_items: int = 5, max_days_old: int = 21) -> list:
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
                "earnings_beat": bool(row.get("earnings_beat")),
                "earnings_date": str(row.get("earnings_date")),
            })
    results.sort(key=lambda x: abs(x["earnings_surprise_pct"]), reverse=True)
    return results[:max_items]


def compute_daily_radar_bundle(user_email: str, holdings: list, watchlist_items: list, market_data: dict) -> dict:
    """
    Hoofdfunctie -- verzamelt ALLE data voor Today's Daily Radar (Insights
    Summary + Week-Agenda) in 1x. Zelfde berekeningen als dashboard.py's
    eigen live-versie, maar geeft overal STRUCTURED DATA terug (dicts met
    een 'icon'/'color'/'text'-vorm) i.p.v. kant-en-klare HTML -- dashboard.py
    rendert dat zelf, met z'n eigen iconen/kleuren-conventies.

    'market_data' -- database.get_market_data_for_tickers()-resultaat,
    door de aanroeper meegegeven (batch-script of dashboard.py) zodat
    deze module zelf geen Supabase-afhankelijkheid heeft.
    """
    import database  # lokaal, zodat deze module ook zonder database-context te importeren blijft

    tracked_items = holdings + watchlist_items

    day_items = []
    screener_items = []
    macro_items = []

    macro_events = get_todays_macro_events(max_items=3)
    earnings_today = get_todays_portfolio_earnings(tracked_items, market_data, max_items=3)
    todays_events = macro_events + [
        {"name": f"{e['naam']} ({e['ticker']}) reports earnings today"} for e in earnings_today
    ]
    for event in todays_events[:3]:
        time_part = f" ({event['time']})" if "time" in event else ""
        day_items.append({"icon": "event", "color": "neutral", "text": f"{event['name']}{time_part}"})

    upcoming_earnings = get_upcoming_portfolio_earnings(tracked_items, market_data, days_ahead=5, max_items=3)
    for e in upcoming_earnings:
        day_word = "tomorrow" if e["days_until"] == 1 else f"in {e['days_until']} days"
        day_items.append({
            "icon": "calendar_month", "color": "neutral",
            "text": f"<b>{e['naam']}</b> ({e['ticker']}) reports earnings {day_word} ({e['earnings_date']}).",
        })

    if holdings:
        risk_profile = database.get_risk_profile(user_email)
        concentration_alert = get_concentration_alert(holdings, risk_profile["max_position_pct"])
        if concentration_alert:
            day_items.append({"icon": "balance", "color": "neutral", "text": concentration_alert})

    upcoming_ex_div = get_upcoming_ex_dividend_dates(holdings, market_data, days_ahead=5, max_items=3)
    for d in upcoming_ex_div:
        day_word = "today" if d["days_until"] == 0 else ("tomorrow" if d["days_until"] == 1 else f"in {d['days_until']} days")
        day_items.append({
            "icon": "payments", "color": "neutral",
            "text": f"<b>{d['naam']}</b> goes ex-dividend {day_word} ({d['ex_div_date']}).",
        })

    records_52wk = get_52_week_records(holdings, market_data, max_items=3) if holdings else []
    for r in records_52wk:
        icon_name = "trending_up" if r["type"] == "high" else "trending_down"
        color = "positive" if r["type"] == "high" else "negative"
        label = "new 52-week high" if r["type"] == "high" else "new 52-week low"
        day_items.append({"icon": icon_name, "color": color, "text": f"<b>{r['naam']}</b> ({r['ticker']}) just hit a {label}."})

    deep_dive_triggers = get_deep_dive_triggers_hit(user_email, max_items=3)
    for t in deep_dive_triggers:
        day_items.append({"icon": "notifications", "color": "neutral", "text": f"<b>{t['naam']}</b> ({t['ticker']}) {t['detail']}."})

    weekly_scan_date = get_file_last_commit_date("supertrend_signals.csv")
    last_seen_weekly = database.get_last_seen_weekly_signals_date(user_email)
    weekly_is_new = weekly_scan_date is not None and weekly_scan_date != last_seen_weekly
    if weekly_is_new:
        database.set_last_seen_weekly_signals_date(user_email, weekly_scan_date)

    opportunities = build_opportunities_today(holdings, watchlist_items, include_weekly=weekly_is_new)
    opportunities["weekly_part"] = f", {opportunities['weekly_signals']} weekly" if weekly_is_new else ""

    tracked_tickers = {item["ticker"] for item in tracked_items}

    personal_surprises = get_recent_earnings_surprises_for_tracked_items(
        tracked_items, market_data, max_days_old=7, max_items=3,
    )
    for s in personal_surprises:
        icon_name = "trending_up" if s["beat"] else "trending_down"
        color = "positive" if s["beat"] else "negative"
        screener_items.append({
            "icon": icon_name, "color": color,
            "text": f"<b>{s['naam']}</b> ({s['ticker']}): {s['surprise_pct']:+.1f}% earnings surprise ({s['earnings_date']})",
        })

    def _is_recent_earnings(earnings_date_str, max_days=1):
        try:
            earnings_date = pd.to_datetime(earnings_date_str).date()
            days_since = (datetime.now().date() - earnings_date).days
            return 0 <= days_since <= max_days
        except Exception:
            return False

    all_recent_surprises = get_earnings_surprises_from_signals(max_items=50)
    market_wide_surprises = [
        s for s in all_recent_surprises
        if s["ticker"] not in tracked_tickers and _is_recent_earnings(s["earnings_date"], max_days=1)
    ]
    for s in market_wide_surprises[:2]:
        icon_name = "trending_up" if s["earnings_beat"] else "trending_down"
        color = "positive" if s["earnings_beat"] else "negative"
        macro_items.append({
            "icon": icon_name, "color": color,
            "text": f"Also worth noting (not in your portfolio): "
                    f"<b>{s['ticker']}</b> {s['earnings_surprise_pct']:+.1f}% surprise ({s['earnings_date']})",
        })

    threshold_alerts = get_sector_theme_threshold_alerts()
    for alert in threshold_alerts[:3]:
        move_emoji = "🔥" if alert["direction"] == "up" else "🥶"
        extreme_marker = " (extreme move!)" if alert["level"] == "extreme" else ""
        region_suffix = f" ({alert['region']})" if alert.get("region") else ""
        kind_label = "sector" if alert["kind"] == "sector" else "theme"
        macro_items.append({
            "icon": move_emoji, "color": "emoji",
            "text": f"<b>{alert['name']}</b>{region_suffix} ({kind_label}) is "
                    f"{alert['pct']:+.1f}% this month{extreme_marker}",
        })

    # Top 2 ECHTE sector/thema-uitschieters (uit threshold_alerts hierboven,
    # al gesorteerd op |pct| aflopend) als kort snippet voor Today's
    # 'Macro Catalyst'-bulletin -- bewust GEEN losstaande macro-tickers als
    # ruwe olie/dollarindex (die worden nergens anders in de app gevolgd,
    # dus dat zou verzonnen data zijn).
    macro_top_movers = [
        f"{a['name']} {a['pct']:+.1f}%" for a in threshold_alerts[:2]
    ]

    if holdings:
        weekly_scan_recent_date = get_file_last_commit_date("supertrend_signals.csv")
        weekly_scan_within_days = (
            weekly_scan_recent_date is not None
            and (datetime.now().date() - datetime.strptime(weekly_scan_recent_date, "%Y-%m-%d").date()).days <= 3
        )
        if weekly_scan_within_days:
            from portfolio_watch import check_holding
            FLIP_VISIBLE_DAYS_ON_TODAY = 2
            today_date = datetime.now().date()
            flipped = []
            for h in holdings:
                result = check_holding(h["naam"], h["ticker"])
                if result and result.get("sinds"):
                    days_since_flip = (today_date - result["sinds"]).days
                    if days_since_flip <= FLIP_VISIBLE_DAYS_ON_TODAY:
                        flipped.append(result)
            for f in flipped[:3]:
                emoji = "🟢" if f["status"] == "BULLISH" else "🔴"
                screener_items.append({
                    "icon": emoji, "color": "emoji",
                    "text": f"<b>{f['naam']}</b> just flipped to {f['status']}",
                })

    # --- Week-agenda: alle gedateerde events (macro + earnings + ex-div)
    # als (datum-string, icon, text)-tuples, zodat dashboard.py ze zelf
    # per weekdag kan bucketen (_bucket_events_by_weekday()) -- dezelfde
    # bucketing-functie blijft in dashboard.py, dit is puur de rauwe data.
    #
    # Weekgrens: op een ZATERDAG/ZONDAG wijst 'de huidige week' (via
    # weekday()) naar de net-afgelopen maandag t/m vrijdag -- die week is
    # dan al voorbij en toont dus GEEN aankomende events meer (bv. een
    # vrijdag-CPI die pas over een paar dagen komt). In het weekend rollen
    # we daarom door naar de AANKOMENDE maandag i.p.v. terug te kijken.
    from macro_events import get_high_impact_macro_events_for_range, get_market_holiday, get_market_early_close
    from datetime import timedelta as _timedelta
    today_d = datetime.now().date()
    if today_d.weekday() >= 5:  # 5 = zaterdag, 6 = zondag
        monday = today_d + _timedelta(days=7 - today_d.weekday())
    else:
        monday = today_d - _timedelta(days=today_d.weekday())
    friday = monday + _timedelta(days=4)

    # Alleen 'High Impact'-events (CPI, FOMC, ECB) op de week-agenda --
    # PPI (impact='medium') is te veel ruis voor dit compacte overzicht.
    week_macro_events = sorted(
        get_high_impact_macro_events_for_range(monday, friday),
        key=lambda e: e["date"],
    )
    dated_agenda_items = []
    for me in week_macro_events:
        time_part = f" ({me['time']})" if "time" in me else ""
        dated_agenda_items.append({"date": me["date"], "icon": "event", "text": f"{me['name']}{time_part}"})
    for e in earnings_today:
        dated_agenda_items.append({"date": str(today_d), "icon": "calendar_month", "text": f"<b>{e['naam']}</b> earnings"})
    for e in upcoming_earnings:
        e_date = today_d + _timedelta(days=e["days_until"])
        dated_agenda_items.append({"date": str(e_date), "icon": "calendar_month", "text": f"<b>{e['naam']}</b> earnings"})
    for d in upcoming_ex_div:
        d_date = today_d + _timedelta(days=d["days_until"])
        dated_agenda_items.append({"date": str(d_date), "icon": "payments", "text": f"<b>{d['naam']}</b> ex-dividend"})

    # --- US Market Holidays / vroege sluitingen -- een VOLLEDIGE
    # marktsluiting OVERSCHRIJFT al het andere op die dag (ook de
    # eventuele High Impact macro-events erboven): een gesloten beurs is
    # altijd het belangrijkste wat er die dag te melden valt, en moet
    # meteen in het oog springen i.p.v. te verdrinken tussen andere
    # bulletjes. Een VROEGE sluiting overschrijft niets -- de beurs is
    # gewoon open, dus dat wordt als extra regel TOEGEVOEGD.
    for _offset in range(5):
        _day = monday + _timedelta(days=_offset)
        _day_str = str(_day)
        _holiday = get_market_holiday(_day_str)
        if _holiday:
            dated_agenda_items = [item for item in dated_agenda_items if item["date"] != _day_str]
            dated_agenda_items.append({
                "date": _day_str, "icon": "event",
                "text": f"US markets closed ({_holiday['name']})",
            })
            continue
        _early_close = get_market_early_close(_day_str)
        if _early_close:
            dated_agenda_items.append({
                "date": _day_str, "icon": "event",
                "text": f"US markets close early ({_early_close['close_time']})",
            })

    return {
        "day_items": day_items,
        "screener_items": screener_items,
        "macro_items": macro_items,
        "macro_top_movers": macro_top_movers,
        "dated_agenda_items": dated_agenda_items,
        "opportunities": opportunities,
        "computed_at": datetime.now(tz=None).isoformat(),
    }
