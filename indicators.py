"""
Eigen implementaties van de indicatoren die de screener nodig heeft.
Zelfstandig -- geen afhankelijkheid van de crypto-bot-codebase.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, length: int) -> pd.Series:
    """Exponentieel voortschrijdend gemiddelde."""
    return series.ewm(span=length, adjust=False).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    """De 'true range' van elke candle, basis voor ATR."""
    prev_close = df["close"].shift(1)
    ranges = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1)
    return ranges.max(axis=1)


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Average True Range met Wilder's smoothing."""
    tr = true_range(df)
    return tr.ewm(alpha=1 / length, adjust=False).mean()


def supertrend(df: pd.DataFrame, length: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """
    Berekent de Supertrend-indicator.
    Geeft een DataFrame terug met kolommen 'supertrend' en 'trend_dir'
    (1 = bullish, -1 = bearish).
    """
    atr_series = atr(df, length)
    hl2 = (df["high"] + df["low"]) / 2

    upperband = (hl2 + multiplier * atr_series).values
    lowerband = (hl2 - multiplier * atr_series).values

    n = len(df)
    final_upper = np.zeros(n)
    final_lower = np.zeros(n)
    trend = np.ones(n, dtype=int)
    st = np.zeros(n)

    close = df["close"].values

    for i in range(n):
        if i == 0:
            final_upper[i] = upperband[i]
            final_lower[i] = lowerband[i]
            trend[i] = 1
            st[i] = final_lower[i]
            continue

        final_upper[i] = (upperband[i] if (upperband[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1])
                           else final_upper[i - 1])
        final_lower[i] = (lowerband[i] if (lowerband[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1])
                           else final_lower[i - 1])

        if trend[i - 1] == 1:
            trend[i] = -1 if close[i] < final_lower[i] else 1
        else:
            trend[i] = 1 if close[i] > final_upper[i] else -1

        st[i] = final_lower[i] if trend[i] == 1 else final_upper[i]

    return pd.DataFrame({"supertrend": st, "trend_dir": trend}, index=df.index)


def volume_ratio(volume: pd.Series, length: int = 20) -> pd.Series:
    """Huidig volume gedeeld door het gemiddelde volume van de laatste N candles (excl. huidige)."""
    avg_volume = volume.shift(1).rolling(length).mean()
    return volume / avg_volume


def resample_to_weekly(df_daily: pd.DataFrame) -> pd.DataFrame:
    """Bouwt weekly OHLCV-candles op uit dagelijkse candles."""
    weekly = df_daily.resample("W").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })
    weekly.dropna(inplace=True)
    return weekly
