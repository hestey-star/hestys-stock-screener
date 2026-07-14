"""
Gedeelde, handmatig bijgehouden kalender van macro-economische events
(FOMC/ECB-rentebesluiten, US CPI-releases) -- gebruikt door zowel de
Streamlit-app (Today's radar) als de dagelijkse e-mail (screener_daily.py),
zonder dat de e-mail een Streamlit-afhankelijkheid nodig heeft.

CPI-data geverifieerd tegen de officiele BLS-releasekalender
(bls.gov/schedule/news_release/cpi.htm). FOMC/ECB-data via de officiele
kalenders van de Federal Reserve en de ECB.

Moet jaarlijks bijgewerkt worden zodra de kalenders voor het volgende
jaar gepubliceerd worden (meestal eind van het voorgaande jaar).
"""
from __future__ import annotations

from datetime import datetime

MACRO_EVENTS_2026 = [
    {"date": "2026-01-13", "name": "US CPI (Dec 2025 data)", "time": "14:30 CET"},
    {"date": "2026-01-28", "name": "FOMC meeting (rate decision)", "time": "20:00 CET"},
    {"date": "2026-02-13", "name": "US CPI (Jan 2026 data)", "time": "14:30 CET"},
    {"date": "2026-03-11", "name": "US CPI (Feb 2026 data)", "time": "14:30 CET"},
    {"date": "2026-03-18", "name": "FOMC meeting (rate decision)", "time": "20:00 CET"},
    {"date": "2026-03-19", "name": "ECB rate decision", "time": "14:15 CET"},
    {"date": "2026-04-10", "name": "US CPI (Mar 2026 data)", "time": "14:30 CET"},
    {"date": "2026-04-29", "name": "FOMC meeting (rate decision)", "time": "20:00 CET"},
    {"date": "2026-04-30", "name": "ECB rate decision", "time": "14:15 CET"},
    {"date": "2026-05-12", "name": "US CPI (Apr 2026 data)", "time": "14:30 CET"},
    {"date": "2026-06-10", "name": "US CPI (May 2026 data)", "time": "14:30 CET"},
    {"date": "2026-06-11", "name": "ECB rate decision", "time": "14:15 CET"},
    {"date": "2026-06-17", "name": "FOMC meeting (rate decision)", "time": "20:00 CET"},
    {"date": "2026-07-14", "name": "US CPI (Jun 2026 data)", "time": "14:30 CET"},
    {"date": "2026-07-23", "name": "ECB rate decision", "time": "14:15 CET"},
    {"date": "2026-07-29", "name": "FOMC meeting (rate decision)", "time": "20:00 CET"},
    {"date": "2026-08-12", "name": "US CPI (Jul 2026 data)", "time": "14:30 CET"},
    {"date": "2026-09-10", "name": "ECB rate decision", "time": "14:15 CET"},
    {"date": "2026-09-11", "name": "US CPI (Aug 2026 data)", "time": "14:30 CET"},
    {"date": "2026-09-16", "name": "FOMC meeting (rate decision)", "time": "20:00 CET"},
    {"date": "2026-10-14", "name": "US CPI (Sep 2026 data)", "time": "14:30 CET"},
    {"date": "2026-10-28", "name": "FOMC meeting (rate decision)", "time": "20:00 CET"},
    {"date": "2026-10-29", "name": "ECB rate decision", "time": "14:15 CET"},
    {"date": "2026-11-10", "name": "US CPI (Oct 2026 data)", "time": "14:30 CET"},
    {"date": "2026-12-09", "name": "FOMC meeting (rate decision)", "time": "20:00 CET"},
    {"date": "2026-12-10", "name": "US CPI (Nov 2026 data)", "time": "14:30 CET"},
    {"date": "2026-12-17", "name": "ECB rate decision", "time": "14:15 CET"},
]


def get_todays_macro_events(max_items: int = 3) -> list:
    """Geeft de macro-events terug die vandaag plaatsvinden (uit de handmatig bijgehouden kalender)."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    return [e for e in MACRO_EVENTS_2026 if e["date"] == today_str][:max_items]
