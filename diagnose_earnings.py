"""
Diagnose: waarom staat een watchlist-ticker (bv. ASML) niet op de Today-agenda?

Draai vanuit je repo-map (waar database.py + secrets.toml staan):
    python diagnose_earnings.py            # alle watchlist-tickers
    python diagnose_earnings.py ASML       # alleen tickers die 'ASML' bevatten

Per ticker print je: (1) de ticker precies zoals opgeslagen, (2) wat de
sync-tabel (ticker_market_data) als next_earnings_date heeft, (3) wat
yfinance NU live teruggeeft, (4) wat radar_data er uiteindelijk van maakt.
"""
import sys
from datetime import datetime

import database
import radar_data

EMAIL = "hesseltorny@gmail.com"

needle = sys.argv[1].upper() if len(sys.argv) > 1 else None
watchlist = database.get_user_holdings(EMAIL, is_watchlist=True)
holdings = database.get_user_holdings(EMAIL)
items = [("WATCHLIST", h) for h in watchlist] + [("HOLDING", h) for h in holdings]
if needle:
    items = [(k, h) for k, h in items if needle in h["ticker"].upper()]

tickers = [h["ticker"] for _, h in items]
market_data = database.get_market_data_for_tickers(tickers)
today = datetime.now().date()
print(f"Vandaag: {today}\n")

for kind, h in items:
    t = h["ticker"]
    row = market_data.get(t)
    print(f"[{kind}] ticker={t!r} naam={h.get('naam')!r}")
    if row is None:
        print("   sync-tabel : GEEN rij voor deze ticker (sync heeft 'm nooit opgehaald)")
    else:
        print(f"   sync-tabel : next_earnings_date={row.get('next_earnings_date')} "
              f"last_updated={row.get('last_updated')}")
    df = radar_data._ticker_earnings_dates(t, limit=8)
    if df is None or df.empty:
        print("   yfinance   : GEEN earnings-datums teruggekregen (leeg/fout)")
    else:
        print("   yfinance   : " + ", ".join(str(ts.date()) for ts in df.index[:6]))
    print(f"   resolved   : {radar_data._resolve_next_earnings_date(t, market_data)}\n")
