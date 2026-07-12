# Hesty's — Your Personal Investment Assistant

Cut through the noise. Hesty's scans global markets for real signals (not hype), tracks your actual portfolio return, and gives you a clear, personal briefing every morning. Free to explore, no account needed to start.

👉 **[hestys.streamlit.app](https://hestys.streamlit.app)**

## What's inside

- **Today** — your daily briefing: portfolio stats, news, and what needs your attention
- **Discover** — 3 signature signals (Momentocrats, Snowballers, Rocket List), sector rotation, top movers, and earnings surprises. Public, no login required.
- **My Portfolio** — track your real positions, log actual buy/sell transactions (or import your DEGIRO history in one go), and see your real return
- **Analyze** — concentration, diversification, and performance vs. the market (S&P 500, NASDAQ, EURO STOXX 50)
- **Premium** — unlimited tracking, the full Discover lists, and the Smart DCA Assistant (a TradingView indicator that scales your contributions with how cheap or expensive the market looks)

## Tech stack

Streamlit · Supabase (Postgres) · GitHub Actions (scheduled scans + email) · Google OAuth · Stripe · yfinance

## Structure

| File | What it does |
|---|---|
| `dashboard.py` | The full Streamlit app (all pages) |
| `screener.py` / `screener_daily.py` | Weekly/daily scans (Momentocrats, Snowballers, Rocket List) |
| `daily_batch.py` / `daily_email_dispatch.py` | Daily scan + region-timed email delivery |
| `weekly_batch.py` | Weekly scan + weekly signal emails + portfolio watch emails |
| `database.py` | Supabase data layer |
| `emailer.py` | Email sending |
| `portfolio_watch.py` | Trend-status checks for tracked positions |

## Running locally

```
pip install -r requirements.txt
```

Copy your Supabase, Google OAuth, email, and Stripe credentials into `.streamlit/secrets.toml`, then:

```
streamlit run dashboard.py
```

## This is a screener and portfolio tracker, not financial advice

Hesty's combines technical signals, fundamental screens, and portfolio analysis to help you research faster. Nothing here is personalized financial advice — you make your own calls.
