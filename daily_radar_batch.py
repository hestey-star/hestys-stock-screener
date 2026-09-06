"""
Berekent de Daily Radar-bundel (Insights Summary + Week-Agenda) voor
ELKE gebruiker met minstens 1 holding of watchlist-item, en schrijft het
resultaat weg naar de gedeelde user_daily_radar_cache-tabel. Today's
pagina in dashboard.py leest die cache uit i.p.v. dit bij elke page-load
(of elke Streamlit-rerun) live te herberekenen -- dat was de bron van de
eerdere, merkbare laadtijd.

Bedoeld om te draaien via GitHub Actions, elke 6 uur (dus GEEN
Streamlit-context -- leest configuratie via omgevingsvariabelen, zelfde
patroon als daily_batch.py/screener_daily.py).

Draait bewust NIET de dagelijkse screener-scan zelf opnieuw (dat blijft
puur bij daily_batch.py, 1x per dag) -- dit script leest alleen wat er
al aan supertrend_signals(_daily).csv in de repo staat, en herberekent
de gebruikers-specifieke doorsnede daarmee (welke signalen relateren aan
JOUW portfolio/watchlist) + de live marktdata/sector-rotatie-kant van de
radar (die WEL elke paar uur kan verschuiven, ook zonder een nieuwe
screener-scan).

Gebruik: python daily_radar_batch.py
"""
from __future__ import annotations

import sys
import time

import database
import radar_data


def main() -> None:
    users_by_hash = database.get_all_users_with_holdings()
    print(f"{len(users_by_hash)} gebruiker(s) met minstens 1 positie/watchlist-item gevonden.")

    succeeded = 0
    failed = 0

    for email_hash, rows in users_by_hash.items():
        try:
            user_email = database.get_real_email(email_hash)
            if not user_email:
                # Kan voorkomen bij een verweesde/verwijderde gebruiker --
                # gewoon overslaan, geen harde fout voor de hele batch.
                continue

            holdings = [r for r in rows if not r.get("is_watchlist")]
            watchlist_items = [r for r in rows if r.get("is_watchlist")]
            if not holdings and not watchlist_items:
                continue

            tracked_tickers = [r["ticker"] for r in (holdings + watchlist_items)]
            market_data = database.get_market_data_for_tickers(tracked_tickers)

            bundle = radar_data.compute_daily_radar_bundle(user_email, holdings, watchlist_items, market_data)
            database.set_daily_radar_cache(user_email, bundle)
            succeeded += 1
        except Exception as e:
            failed += 1
            # 1 gebruiker die faalt (bv. een rare/verwijderde ticker) mag de
            # hele batch niet laten crashen -- gewoon loggen en doorgaan.
            print(f"  FOUT bij gebruiker (hash {email_hash[:8]}...): {e}", file=sys.stderr)
            continue

        # Kleine pauze om yfinance niet plat te bellen bij veel gebruikers
        # achter elkaar (elke gebruiker triggert een handvol losse
        # ticker-aanroepen voor de terugval-paden waar market_data niets
        # voor heeft).
        time.sleep(0.2)

    print(f"\nKlaar. {succeeded} gebruiker(s) bijgewerkt, {failed} mislukt.")


if __name__ == "__main__":
    main()
