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

from macro_events import get_todays_macro_events

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
LOOKBACK_DAYS_FOR_SIGNAL = 2       # hoe 'vers' een omslag moet zijn (i.p.v. 2 WEKEN bij de wekelijkse variant)
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


def check_ticker_daily(ticker: str, benchmark_returns: dict, df: pd.DataFrame = None):
    if df is None:
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


def _get_macro_teaser_text() -> str:
    """
    Geeft 1 korte teaser-regel terug als er vandaag een macro-event is
    (CPI/FOMC/ECB), anders None -- bewust maar 1 regel, alleen op de
    dagen dat het er toe doet, geen volledige kalender (dat zou de mail
    te vol maken en de prikkel om naar de site te gaan verminderen).
    """
    events = get_todays_macro_events(max_items=1)
    if not events:
        return None
    e = events[0]
    return f"Also today: {e['name']} ({e['time']})"


def build_no_signals_email_daily() -> tuple:
    """Korte, warme mail voor een dag zonder signalen -- houdt het dagelijkse contactmoment in stand."""
    macro_teaser = _get_macro_teaser_text()
    macro_line_text = f"\n{macro_teaser}\n" if macro_teaser else ""
    macro_line_html = (
        f'<p style="margin-top:12px; font-size:13px; color:#1FAE96; font-weight:600;">📅 {macro_teaser}</p>'
        if macro_teaser else ""
    )

    text_body = (
        "Good morning from Hesty's\n\n"
        "No bullish flips showed up on today's scan -- a quiet day on that front.\n"
        f"{macro_line_text}\n"
        "Check Discover for sector rotation and top movers, Today for the day's key "
        "macro events, or Analyse for your own portfolio.\n\n"
        "-- Hesty's, your personal investment assistant\n\n"
        "This is a screener, not investment advice."
    )
    html_body = f"""
    <div style="font-family: -apple-system, 'Segoe UI', Roboto, Arial, sans-serif; max-width: 600px; margin: 0 auto; background:#ffffff;">
        <div style="background:#101825; padding: 28px 24px; border-radius: 12px 12px 0 0;">
            <div style="color:#1FAE96; font-size:13px; font-weight:600; letter-spacing:1px; text-transform:uppercase;">Hesty's Daily</div>
            <div style="color:#EAEDF1; font-size:22px; font-weight:700; margin-top:4px;">Good morning</div>
        </div>
        <div style="padding: 24px; border: 1px solid #E5E8EC; border-top: none; border-radius: 0 0 12px 12px;">
            <p style="font-size:15px; color:#101825; line-height:1.5; margin-top:0;">
                No bullish flips showed up on today's scan -- a quiet day on that front.
            </p>
            {macro_line_html}
            <p style="margin-top:16px; font-size:14px; color:#5B6472; line-height:1.5;">
                Check <a href="https://hestys.streamlit.app/?view=discover" style="color:#1FAE96; font-weight:600; text-decoration:none;">Discover</a>
                for sector rotation and top movers,
                <a href="https://hestys.streamlit.app/?view=today" style="color:#1FAE96; font-weight:600; text-decoration:none;">Today</a>
                for the day's key macro events, or
                <a href="https://hestys.streamlit.app/?view=analyze" style="color:#1FAE96; font-weight:600; text-decoration:none;">Analyse</a> for your own portfolio.
            </p>
            <p style="margin-top:24px; font-size:14px; color:#101825; font-weight:600;">&mdash; Hesty's, your personal investment assistant</p>
            <p style="margin-top:16px; font-size:12px; color:#9AA1AC; font-style:italic;">This is a screener, not investment advice.</p>
        </div>
    </div>
    """
    return text_body, html_body


def build_email_body_daily(df_hits: pd.DataFrame) -> tuple:
    """
    Bouwt de dagelijkse mail -- zakelijk maar met een eigen stem: een korte,
    op de data gebaseerde toelichting (geen hype, geen giswerk) vooraf, dan
    de tabel, en een korte, herkenbare afsluiting namens Hesty's.
    """
    n = len(df_hits)
    top_pick = df_hits.iloc[0]  # df_hits is al gesorteerd op score (hoog naar laag)

    intro_line = (
        f"{n} stock{'s' if n != 1 else ''} just flipped bullish on today's scan. "
        f"{top_pick['ticker']} leads with the highest score ({top_pick['score']})."
    )
    macro_teaser = _get_macro_teaser_text()

    # --- Tekst-versie ---
    text_lines = [
        "Good morning from Hesty's",
        "",
        intro_line,
    ]
    if macro_teaser:
        text_lines.append(macro_teaser)
    text_lines += [
        "",
        "Today's signals (highest score first):",
    ]
    for _, row in df_hits.iterrows():
        text_lines.append(
            f"- [{row['score']}] {row['ticker']}: flipped {row['dagen_geleden']} day(s) ago "
            f"after {row['voorgaande_trend_dagen']} days bearish -- "
            f"{row['prijs_bij_omslag']} -> {row['prijs_nu']} ({row['sinds_omslag_pct']:+.2f}%)"
        )
    text_lines += [
        "",
        "See the full list, sector rotation, and top movers under Discover on the site, "
        "or check Today for the day's key macro events.",
        "",
        "-- Hesty's, your personal investment assistant",
        "",
        "This is a screener, not investment advice.",
    ]
    text_body = "\n".join(text_lines)

    # --- HTML-versie: lichte achtergrond (betrouwbaarder in e-mail-clients
    # dan een donkere), met de merk-kleur (jade) als accent ---
    rows_html = "".join(
        f"""<tr style="border-bottom:1px solid #E5E8EC;">
            <td style="padding:10px 8px;font-weight:700;color:#101825;">{r['score']}</td>
            <td style="padding:10px 8px;font-weight:600;color:#101825;">{r['ticker']}</td>
            <td style="padding:10px 8px;color:#5B6472;">{r['flip_date']}</td>
            <td style="padding:10px 8px;color:#5B6472;">{r['dagen_geleden']}d ago</td>
            <td style="padding:10px 8px;color:#5B6472;">{r['prijs_bij_omslag']} &rarr; {r['prijs_nu']}</td>
            <td style="padding:10px 8px;font-weight:600;color:{'#0F8F6E' if r['sinds_omslag_pct'] >= 0 else '#C1524A'};">{r['sinds_omslag_pct']:+.2f}%</td>
        </tr>"""
        for _, r in df_hits.iterrows()
    )

    macro_line_html = (
        f'<p style="margin-top:8px; font-size:13px; color:#1FAE96; font-weight:600;">📅 {macro_teaser}</p>'
        if macro_teaser else ""
    )

    html_body = f"""
    <div style="font-family: -apple-system, 'Segoe UI', Roboto, Arial, sans-serif; max-width: 600px; margin: 0 auto; background:#ffffff;">
        <div style="background:#101825; padding: 28px 24px; border-radius: 12px 12px 0 0;">
            <div style="color:#1FAE96; font-size:13px; font-weight:600; letter-spacing:1px; text-transform:uppercase;">Hesty's Daily</div>
            <div style="color:#EAEDF1; font-size:22px; font-weight:700; margin-top:4px;">Good morning</div>
        </div>
        <div style="padding: 24px; border: 1px solid #E5E8EC; border-top: none; border-radius: 0 0 12px 12px;">
            <p style="font-size:15px; color:#101825; line-height:1.5; margin-top:0;">{intro_line}</p>
            {macro_line_html}
            <table style="width:100%; border-collapse:collapse; margin-top:16px;">
                <tr style="border-bottom:2px solid #101825;">
                    <th style="text-align:left; padding:8px; font-size:11px; color:#5B6472; text-transform:uppercase;">Score</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#5B6472; text-transform:uppercase;">Ticker</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#5B6472; text-transform:uppercase;">Flip Date</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#5B6472; text-transform:uppercase;">Since</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#5B6472; text-transform:uppercase;">Price</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#5B6472; text-transform:uppercase;">Change</th>
                </tr>
                {rows_html}
            </table>
            <p style="margin-top:20px; font-size:14px; color:#5B6472; line-height:1.5;">
                Want sector rotation, top movers, and earnings surprises too? Check
                <a href="https://hestys.streamlit.app/?view=discover" style="color:#1FAE96; font-weight:600; text-decoration:none;">Discover</a> on the site,
                or see <a href="https://hestys.streamlit.app/?view=today" style="color:#1FAE96; font-weight:600; text-decoration:none;">Today</a>
                for the day's key macro events.
            </p>
            <p style="margin-top:24px; font-size:14px; color:#101825; font-weight:600;">&mdash; Hesty's, your personal investment assistant</p>
            <p style="margin-top:16px; font-size:12px; color:#9AA1AC; font-style:italic;">This is a screener, not investment advice.</p>
        </div>
    </div>
    """
    return text_body, html_body


def main(send_own_email: bool = True) -> None:
    tickers = build_ticker_list()

    print("Fetching benchmark returns (for relative strength)...")
    benchmark_returns = fetch_benchmark_returns_daily()

    print(f"\nScreening {len(tickers)} tickers for recent bullish Supertrend flips "
          f"(daily, ATR length {ATR_LENGTH}, multiplier {ATR_MULTIPLIER})...\n")

    hits = []
    movers = []
    for ticker in tickers:
        try:
            df = fetch_daily(ticker)
        except Exception as exc:
            print(f"  {ticker}: fout bij ophalen ({exc})")
            continue

        # Dag-op-dag-verandering, voor 'top movers' -- hergebruikt dezelfde
        # opgehaalde data als de signaal-check hieronder, dus GEEN extra
        # API-aanroepen nodig.
        if not df.empty and len(df) >= 2:
            try:
                day_change = (df["close"].iloc[-1] / df["close"].iloc[-2] - 1) * 100
                movers.append({"ticker": ticker, "change_pct": round(day_change, 2)})
            except Exception:
                pass

        result = check_ticker_daily(ticker, benchmark_returns, df=df)
        if result:
            hits.append(result)
            print(f"  {ticker}: SIGNAL ({result['dagen_geleden']} day(s) ago, score {result['score']})")
        else:
            print(f"  {ticker}: no recent signal")

    if movers:
        df_movers = pd.DataFrame(movers).sort_values("change_pct", ascending=False)
        df_movers.to_csv("top_movers.csv", index=False)
        print(f"\nSaved {len(df_movers)} tickers' daily change to 'top_movers.csv'.")

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
