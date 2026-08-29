"""
Achtergrond-sync-script: haalt verse marktdata op voor ELKE ticker die
ergens in iemands portfolio of watchlist staat (over ALLE gebruikers heen,
1x per ticker -- geen duplicaat-werk), en schrijft die naar de gedeelde
ticker_market_data-tabel in Supabase.

Dit is de kern van de nieuwe architectuur: dashboard.py haalt koersen/
dagrendement/earnings/ex-dividend/52-weken-data niet langer LIVE op
tijdens het laden van een pagina (traag, per-ticker yfinance-aanroepen),
maar leest die uit deze tabel (snel, 1 database-query voor alle tickers
tegelijk). Deze tabel wordt op zijn beurt elke 15 minuten vers gehouden
door dit script, via GitHub Actions.

'Update portfolio value' blijft WEL een live, on-demand yfinance-aanroep
(op eigen verzoek) -- dit script is daar volledig los van, en ververst
de achtergrond-weergave onafhankelijk daarvan.

Bedoeld om te draaien via GitHub Actions (dus GEEN Streamlit-context --
database.py's get_supabase_client() leest secrets.toml, dat de workflow
vooraf vanuit GitHub Secrets moet aanmaken, net als de andere batch-
scripts al doen).

Gebruik: python sync_market_data.py
"""
from __future__ import annotations

import time

import pandas as pd
import yfinance as yf

import database

# Kleine pauze tussen tickers om Yahoo niet te agressief te bevragen --
# geen officiele rate limit gepubliceerd, maar voorkomt IP-throttling bij
# een grotere gebruikersbasis met veel unieke tickers.
DELAY_BETWEEN_TICKERS_SECONDS = 0.3


def collect_all_unique_tickers() -> set:
    """
    Verzamelt alle unieke tickers over ALLE gebruikers' holdings EN
    watchlist-items heen (get_all_users_with_holdings() geeft beide terug,
    want de onderliggende tabel filtert niet op is_watchlist) -- zodat elke
    ticker maar 1x wordt opgehaald, ongeacht hoeveel gebruikers 'm volgen.
    """
    grouped = database.get_all_users_with_holdings()
    tickers = set()
    for holdings in grouped.values():
        for h in holdings:
            ticker = h.get("ticker")
            if ticker:
                tickers.add(ticker)
    return tickers


def fetch_market_data_for_ticker(ticker: str) -> dict:
    """
    Haalt verse marktdata op voor 1 ticker -- dezelfde, al-bevestigd-
    betrouwbare methodes als dashboard.py inmiddels gebruikt
    (regularMarketPrice/regularMarketPreviousClose uit .info, en
    get_earnings_dates() voor de eerstvolgende EN meest recente
    rapportagedatum + surprise). Geeft een dict terug met alleen de
    velden die daadwerkelijk zijn gelukt -- ontbrekende velden worden
    simpelweg niet meegestuurd (upsert laat die dan ongemoeid).
    """
    row = {"ticker": ticker}

    try:
        info = yf.Ticker(ticker).info
        current_price = info.get("regularMarketPrice") or info.get("currentPrice")
        previous_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
        if current_price is not None:
            row["current_price"] = current_price
        if previous_close:
            row["previous_close"] = previous_close
        if current_price is not None and previous_close:
            row["day_change_pct"] = (current_price - previous_close) / previous_close * 100
        if info.get("currency"):
            row["currency"] = info["currency"]
        if info.get("fiftyTwoWeekHigh") is not None:
            row["fifty_two_week_high"] = info["fiftyTwoWeekHigh"]
        if info.get("fiftyTwoWeekLow") is not None:
            row["fifty_two_week_low"] = info["fiftyTwoWeekLow"]
        ex_div = info.get("exDividendDate")
        if ex_div:
            try:
                row["ex_dividend_date"] = pd.Timestamp(ex_div, unit="s").date().isoformat()
            except Exception:
                pass
    except Exception as e:
        print(f"  [{ticker}] .info mislukt: {e}")

    try:
        dates_df = yf.Ticker(ticker).get_earnings_dates(limit=8)
        if dates_df is not None and not dates_df.empty:
            today = pd.Timestamp.now().normalize()
            upcoming = dates_df[dates_df.index > today]
            past_with_surprise = dates_df[
                (dates_df.index <= today) & dates_df["Surprise(%)"].notna()
            ] if "Surprise(%)" in dates_df.columns else dates_df.iloc[0:0]

            if not upcoming.empty:
                row["next_earnings_date"] = upcoming.index.min().date().isoformat()
            if not past_with_surprise.empty:
                most_recent = past_with_surprise.sort_index(ascending=False).iloc[0]
                row["last_earnings_date"] = past_with_surprise.sort_index(ascending=False).index[0].date().isoformat()
                row["last_earnings_surprise_pct"] = float(most_recent["Surprise(%)"])
    except Exception as e:
        print(f"  [{ticker}] earnings-datums mislukt: {e}")

    return row


def main():
    tickers = collect_all_unique_tickers()
    print(f"Gevonden: {len(tickers)} unieke tickers om te synchroniseren.")

    rows = []
    for i, ticker in enumerate(sorted(tickers), start=1):
        print(f"[{i}/{len(tickers)}] {ticker}...")
        row = fetch_market_data_for_ticker(ticker)
        if len(row) > 1:  # meer dan alleen 'ticker' -- er is iets gevonden
            rows.append(row)
        time.sleep(DELAY_BETWEEN_TICKERS_SECONDS)

    print(f"\nWegschrijven van {len(rows)} tickers naar ticker_market_data...")
    database.upsert_ticker_market_data(rows)
    print("Sync klaar.")


if __name__ == "__main__":
    main()
