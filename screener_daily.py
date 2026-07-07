"""
Dagelijkse variant van screener.py -- zelfde signaal-logica (Supertrend-
omslag + ROIC + winst-verrassing + fair value + relatieve sterkte), maar
op DAGELIJKSE candles i.p.v. wekelijkse, met instellingen die daarbij
passen (kortere periodes). Bedoeld voor swing trades (dagen-weken), naast
de bestaande wekelijkse screener (voor lange-termijn-overtuigingen).

Bewust een APART bestand i.p.v. de bestaande, uitgebreid-afgestelde
screener.py aan te passen -- dat voorkomt dat wijzigingen hier de
goed-werkende wekelijkse screener zouden kunnen breken. Hergebruikt wel
alle tijdschaal-onafhankelijke bouwstenen (tickerlijsten, ROIC,
winst-verrassing, fair value, nieuws) via import.

Gebruik: python screener_daily.py
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf

from indicators import supertrend, ema, volume_ratio
from screener import (
    FALLBACK_TICKERS, BENCHMARKS, DEFAULT_BENCHMARK,
    fetch_aex_tickers, fetch_nasdaq100_tickers, fetch_sp500_tickers,
    fetch_dax_tickers, fetch_cac40_tickers, build_ticker_list,
    get_benchmark_for_ticker, get_trailing_return_pct, get_prior_trend_duration,
    get_roic_data, get_earnings_surprise, get_fair_value_estimate,
)
from emailer import send_email, is_configured as email_is_configured

# --- Instellingen, geschaald voor dagelijkse candles (i.p.v. wekelijkse) ---
ATR_LENGTH = 10
ATR_MULTIPLIER = 3.0
LOOKBACK_DAYS_FOR_SIGNAL = 3       # hoe 'vers' een omslag moet zijn (i.p.v. 2 WEKEN bij de wekelijkse variant)
TREND_FILTER_EMA_LENGTH = 50       # bredere-trend-context (i.p.v. 20 WEKEN)
YEARS_OF_HISTORY = 2
BENCHMARK_LOOKBACK_DAYS = 60       # relatieve-sterkte-vergelijkingsperiode (i.p.v. 12 WEKEN)
VOLUME_AVG_DAYS = 20
MIN_PRIOR_TREND_DAYS = 15          # zigzag-ruis-filter (i.p.v. 8 WEKEN)
EARNINGS_RELEVANCE_DAYS = 45       # hoe recent winstcijfers moeten zijn (i.p.v. 8 WEKEN)


def fetch_daily(ticker: str, years: int = YEARS_OF_HISTORY) -> pd.DataFrame:
    """Haalt dagelijkse OHLCV-data op -- GEEN resampling naar weekly, in tegenstelling tot screener.py."""
    df = yf.download(ticker, period=f"{years}y", interval="1d", auto_adjust=True, progress=False)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]]
    return df


def fetch_benchmark_returns_daily() -> dict:
    """Haalt voor elke benchmark-index 1x het trailing-rendement op (dagelijkse basis)."""
    returns = {}
    for benchmark_ticker in set(list(BENCHMARKS.values()) + [DEFAULT_BENCHMARK]):
        try:
            df_bench = fetch_daily(benchmark_ticker)
            returns[benchmark_ticker] = get_trailing_return_pct(df_bench, BENCHMARK_LOOKBACK_DAYS)
        except Exception as exc:
            print(f"Kon benchmark {benchmark_ticker} niet ophalen: {exc}")
            returns[benchmark_ticker] = None
    return returns


def compute_score_daily(result: dict) -> float:
    """
    Zelfde score-opbouw als screener.py's compute_score (0-10, dezelfde
    gewichten), maar met dag-gebaseerde versheid/relevantie-drempels i.p.v.
    week-gebaseerde.
    """
    freshness_score = max(0.0, (LOOKBACK_DAYS_FOR_SIGNAL - result["dagen_geleden"]) / LOOKBACK_DAYS_FOR_SIGNAL * 1.5)

    if result["roic_pct"] is not None:
        level_points = min(max(result["roic_pct"], 0), 30) / 30 * 1.0
        trend_points = 0.5 if result["roic_trend"] == "stijgend" else (-0.5 if result["roic_trend"] == "dalend" else 0)
        roic_score = max(0.0, min(1.5, level_points + trend_points + 0.5))
    else:
        roic_score = 0.75

    if result["relatieve_sterkte"] is not None:
        clamped = min(max(result["relatieve_sterkte"], -20), 20)
        rs_score = (clamped + 20) / 40 * 2.5
    else:
        rs_score = 1.25

    if result.get("volume_bevestigd") is not None:
        volume_score = 1.0 if result["volume_bevestigd"] else 0.0
    else:
        volume_score = 0.5

    is_recent_enough = (
        result.get("dagen_sinds_earnings") is not None
        and result["dagen_sinds_earnings"] <= EARNINGS_RELEVANCE_DAYS
    )
    if result.get("earnings_surprise_pct") is not None and is_recent_enough:
        clamped_surprise = min(max(result["earnings_surprise_pct"], -10), 10)
        earnings_score = (clamped_surprise + 10) / 20 * 1.5
    else:
        earnings_score = 0.75

    if result.get("afwijking_fair_value_pct") is not None:
        clamped_fv = min(max(result["afwijking_fair_value_pct"], -30), 30)
        fair_value_score = (30 - clamped_fv) / 60 * 2.0
    else:
        fair_value_score = 1.0

    return round(
        freshness_score + roic_score + rs_score + volume_score + earnings_score + fair_value_score, 2
    )


def check_ticker_daily(ticker: str, benchmark_returns: dict):
    try:
        df = fetch_daily(ticker)
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
    df["volume_ratio"] = volume_ratio(df["volume"], length=VOLUME_AVG_DAYS)

    flips = df.index[(df["trend_dir"] == 1) & (df["trend_dir"].shift(1) == -1)]
    if len(flips) == 0:
        return None

    last_flip = flips[-1]
    days_since_flip = len(df.loc[last_flip:]) - 1
    if days_since_flip > LOOKBACK_DAYS_FOR_SIGNAL:
        return None

    prior_trend_days = get_prior_trend_duration(df, last_flip)
    if prior_trend_days < MIN_PRIOR_TREND_DAYS:
        return None  # waarschijnlijk zigzag-ruis binnen een al lopende trend

    flip_row = df.loc[last_flip]
    latest_row = df.iloc[-1]

    benchmark_ticker = get_benchmark_for_ticker(ticker)
    own_return = get_trailing_return_pct(df, BENCHMARK_LOOKBACK_DAYS)
    benchmark_return = benchmark_returns.get(benchmark_ticker)
    relative_strength = (
        round(own_return - benchmark_return, 2)
        if own_return is not None and benchmark_return is not None
        else None
    )

    volume_confirmed = (
        bool(flip_row["volume_ratio"] > 1) if pd.notna(flip_row["volume_ratio"]) else None
    )

    result = {
        "ticker": ticker,
        "flip_date": last_flip.date(),
        "dagen_geleden": days_since_flip,
        "voorgaande_trend_dagen": prior_trend_days,
        "prijs_bij_omslag": round(float(flip_row["close"]), 2),
        "prijs_nu": round(float(latest_row["close"]), 2),
        "sinds_omslag_pct": round((latest_row["close"] / flip_row["close"] - 1) * 100, 2),
        "boven_ema": bool(latest_row["close"] > latest_row["ema_trend"]),
        "benchmark": benchmark_ticker,
        "relatieve_sterkte": relative_strength,
        "volume_bevestigd": volume_confirmed,
    }

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
        days_since_earnings = (pd.Timestamp.now(tz=earnings_data["earnings_date"].tz) - earnings_data["earnings_date"]).days
        result["dagen_sinds_earnings"] = max(0, days_since_earnings)
    else:
        result["dagen_sinds_earnings"] = None

    fair_value_data = get_fair_value_estimate(ticker)
    result["fair_value"] = fair_value_data["fair_value"]
    result["afwijking_fair_value_pct"] = fair_value_data["afwijking_pct"]

    result["score"] = compute_score_daily(result)

    return result


def build_email_body_daily(df_hits: pd.DataFrame) -> tuple:
    lines = [f"Daily screener: {len(df_hits)} signals found (sorted by score, highest first).\n"]
    for _, row in df_hits.iterrows():
        lines.append(
            f"- [score {row['score']}] {row['ticker']}: flip on {row['flip_date']} "
            f"({row['dagen_geleden']} day(s) ago, after {row['voorgaande_trend_dagen']} days bearish), "
            f"price then {row['prijs_bij_omslag']}, now {row['prijs_nu']} ({row['sinds_omslag_pct']:+.2f}%)"
        )
    text_body = "\n".join(lines)
    text_body += "\n\nThis is a screener, not investment advice."

    rows_html = "".join(
        f"<tr><td><b>{r['score']}</b></td><td>{r['ticker']}</td><td>{r['flip_date']}</td>"
        f"<td>{r['dagen_geleden']}</td><td>{r['prijs_bij_omslag']}</td><td>{r['prijs_nu']}</td>"
        f"<td>{r['sinds_omslag_pct']:+.2f}%</td></tr>"
        for _, r in df_hits.iterrows()
    )
    html_body = f"""
    <h3>Daily screener: {len(df_hits)} signals found</h3>
    <table border="1" cellpadding="5" cellspacing="0">
      <tr><th>Score</th><th>Ticker</th><th>Flip Date</th><th>Days Ago</th>
          <th>Price at Flip</th><th>Price Now</th><th>Since Flip</th></tr>
      {rows_html}
    </table>
    <p><i>This is a screener, not investment advice. Intended for swing-trade timeframes (days-weeks).</i></p>
    """
    return text_body, html_body


def main(send_own_email: bool = True) -> None:
    tickers = build_ticker_list()

    print("Fetching benchmark returns (for relative strength)...")
    benchmark_returns = fetch_benchmark_returns_daily()

    print(f"\nScreening {len(tickers)} tickers for recent bullish Supertrend flips "
          f"(daily, ATR length {ATR_LENGTH}, multiplier {ATR_MULTIPLIER})...\n")

    hits = []
    for ticker in tickers:
        result = check_ticker_daily(ticker, benchmark_returns)
        if result:
            hits.append(result)
            print(f"  {ticker}: SIGNAL ({result['dagen_geleden']} day(s) ago, score {result['score']})")
        else:
            print(f"  {ticker}: no recent signal")

    if not hits:
        print("\nNo signals today.")
        if send_own_email and email_is_configured():
            send_email(subject="Daily screener: no signals today", body_text="No signals found today.")
        return

    df_hits = pd.DataFrame(hits)
    df_hits.sort_values("score", ascending=False, inplace=True)

    print(f"\n=== {len(hits)} SIGNALS FOUND ===\n")
    print(df_hits.to_string(index=False))

    df_hits.to_csv("supertrend_signals_daily.csv", index=False)
    print("\nSaved to 'supertrend_signals_daily.csv'.")

    if send_own_email and email_is_configured():
        text_body, html_body = build_email_body_daily(df_hits)
        send_email(subject=f"Daily screener: {len(hits)} new signals", body_text=text_body, body_html=html_body)


if __name__ == "__main__":
    main()
