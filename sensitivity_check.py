"""
Gevoeligheids-check: laat zien hoeveel Supertrend-omslagen verschillende
ATR-instellingen zouden hebben gegeven, voor een paar aandelen naar keuze.

Dit is GEEN optimalisatie -- we zoeken niet naar 'de beste' instelling
(dat zou precies het overfitting-risico introduceren dat we willen
vermijden). Het is puur bedoeld om een gevoel te krijgen voor hoe
gevoelig/rustig een instelling is, per aandeel, zodat jij zelf een
weloverwogen keuze kan maken voor de screener.

Gebruik: python sensitivity_check.py
"""
from __future__ import annotations

import itertools

import pandas as pd
import yfinance as yf

from indicators import supertrend, resample_to_weekly

# --- Pas aan naar de aandelen die je wil vergelijken ---
TICKERS = ["AAPL", "ASML.AS", "TSLA", "JPM"]

# --- De combinaties om te vergelijken ---
ATR_LENGTHS = [6, 10, 14]
ATR_MULTIPLIERS = [2.0, 2.6, 3.0]

YEARS_OF_HISTORY = 5


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


def count_flips(df: pd.DataFrame, length: int, multiplier: float) -> int:
    """Telt hoe vaak de trend van richting wisselde (excl. de 'nep-omslag' bij de allereerste candle)."""
    st = supertrend(df, length=length, multiplier=multiplier)
    trend = st["trend_dir"]
    flips = int((trend != trend.shift(1)).sum()) - 1
    return max(flips, 0)


def main() -> None:
    print(f"Gevoeligheids-check over de laatste {YEARS_OF_HISTORY} jaar (weekly)\n")
    print("LET OP: dit optimaliseert niets -- het laat alleen zien hoeveel")
    print("signalen elke instelling zou hebben gegeven, als hulpmiddel om")
    print("een bewuste keuze te maken, niet om 'de beste' te vinden.\n")

    for ticker in TICKERS:
        print(f"=== {ticker} ===")
        try:
            df = fetch_weekly(ticker)
        except Exception as exc:
            print(f"  Fout bij ophalen: {exc}\n")
            continue

        if df.empty or len(df) < 30:
            print("  Te weinig data, overgeslagen.\n")
            continue

        results = []
        for length, multiplier in itertools.product(ATR_LENGTHS, ATR_MULTIPLIERS):
            n_flips = count_flips(df, length, multiplier)
            per_year = n_flips / (len(df) / 52)
            results.append({
                "ATR-periode": length,
                "Multiplier": multiplier,
                "Omslagen (totaal)": n_flips,
                "Omslagen/jaar": round(per_year, 1),
            })

        df_results = pd.DataFrame(results)
        print(df_results.to_string(index=False))
        print()

    print("--- Interpretatie ---")
    print("Meer omslagen/jaar = gevoeliger (sneller signaal, maar meer kans op ruis/whipsaws)")
    print("Minder omslagen/jaar = rustiger (trager signaal, mogelijk betrouwbaardere omslagen)")
    print("Er is hier bewust GEEN 'winnaar' berekend -- kies wat past bij hoe vaak")
    print("je meldingen wil ontvangen, niet wat historisch toevallig het best scoorde.")


if __name__ == "__main__":
    main()
