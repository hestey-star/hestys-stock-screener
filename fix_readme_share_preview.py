"""
De README.md was sterk verouderd -- nog uit de allereerste crypto-bot/
command-line-fase, van vóór al het dashboard-werk. Dit is ook precies
waar Streamlit Cloud het Nederlandse subtekstje bij het delen van de
link vandaan haalde (share previews gebruiken de README, geen apart
instelbaar veld).

Nieuwe README: een pakkende, uitnodigende openingsalinea (die als
link-preview-tekst gaat dienen) + een actuele beschrijving van alle
huidige features.

Gebruik: python fix_readme_share_preview.py
Draai dit vanuit je stock_screener-map.

LET OP: Streamlit Cloud's share-preview-afbeelding is een dagelijkse
screenshot -- die kan tot 24 uur duren om bij te werken na deze wijziging,
en de tekst-preview kan ook enige tijd nodig hebben om te verversen bij
platforms die hun eigen cache gebruiken (WhatsApp, LinkedIn, etc.).
"""
NEW_README = "# Hesty's — Your Personal Investment Assistant\n\nCut through the noise. Hesty's scans global markets for real signals (not hype), tracks your actual portfolio return, and gives you a clear, personal briefing every morning. Free to explore, no account needed to start.\n\n👉 **[hestys.streamlit.app](https://hestys.streamlit.app)**\n\n## What's inside\n\n- **Today** — your daily briefing: portfolio stats, news, and what needs your attention\n- **Discover** — 3 signature signals (Momentocrats, Snowballers, Rocket List), sector rotation, top movers, and earnings surprises. Public, no login required.\n- **My Portfolio** — track your real positions, log actual buy/sell transactions (or import your DEGIRO history in one go), and see your real return\n- **Analyze** — concentration, diversification, and performance vs. the market (S&P 500, NASDAQ, EURO STOXX 50)\n- **Premium** — unlimited tracking, the full Discover lists, and the Smart DCA Assistant (a TradingView indicator that scales your contributions with how cheap or expensive the market looks)\n\n## Tech stack\n\nStreamlit · Supabase (Postgres) · GitHub Actions (scheduled scans + email) · Google OAuth · Stripe · yfinance\n\n## Structure\n\n| File | What it does |\n|---|---|\n| `dashboard.py` | The full Streamlit app (all pages) |\n| `screener.py` / `screener_daily.py` | Weekly/daily scans (Momentocrats, Snowballers, Rocket List) |\n| `daily_batch.py` / `daily_email_dispatch.py` | Daily scan + region-timed email delivery |\n| `weekly_batch.py` | Weekly scan + weekly signal emails + portfolio watch emails |\n| `database.py` | Supabase data layer |\n| `emailer.py` | Email sending |\n| `portfolio_watch.py` | Trend-status checks for tracked positions |\n\n## Running locally\n\n```\npip install -r requirements.txt\n```\n\nCopy your Supabase, Google OAuth, email, and Stripe credentials into `.streamlit/secrets.toml`, then:\n\n```\nstreamlit run dashboard.py\n```\n\n## This is a screener and portfolio tracker, not financial advice\n\nHesty's combines technical signals, fundamental screens, and portfolio analysis to help you research faster. Nothing here is personalized financial advice — you make your own calls.\n"

with open("README.md", "w", encoding="utf-8") as f:
    f.write(NEW_README)
print("Klaar. 'README.md' overschreven.")
print("git add .")
print('git commit -m "Rewrite README with hip, inviting opening for share previews"')
print("git push")
