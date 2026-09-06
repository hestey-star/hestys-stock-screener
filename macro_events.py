"""
Gedeelde, handmatig bijgehouden kalender van macro-economische events
(FOMC/ECB-rentebesluiten, US CPI- en PPI-releases) -- gebruikt door zowel
de Streamlit-app (Today's radar) als de dagelijkse e-mail
(screener_daily.py), zonder dat de e-mail een Streamlit-afhankelijkheid
nodig heeft.

CPI/PPI-data geverifieerd tegen de officiele BLS-releasekalenders
(bls.gov/schedule/news_release/cpi.htm, .../ppi.htm). FOMC/ECB-data via
de officiele kalenders van de Federal Reserve en de ECB.

Moet jaarlijks bijgewerkt worden zodra de kalenders voor het volgende
jaar gepubliceerd worden (meestal eind van het voorgaande jaar).
"""
from __future__ import annotations

from datetime import datetime

MACRO_EVENTS_2026 = [
    {"date": "2026-01-13", "name": "US CPI (Dec 2025 data)", "time": "14:30 CET", "impact": "high"},
    {"date": "2026-01-14", "name": "US PPI (Nov 2025 data)", "time": "14:30 CET", "impact": "medium"},
    {"date": "2026-01-28", "name": "FOMC meeting (rate decision)", "time": "20:00 CET", "impact": "high"},
    {"date": "2026-01-30", "name": "US PPI (Dec 2025 data)", "time": "14:30 CET", "impact": "medium"},
    {"date": "2026-02-13", "name": "US CPI (Jan 2026 data)", "time": "14:30 CET", "impact": "high"},
    {"date": "2026-02-27", "name": "US PPI (Jan 2026 data)", "time": "14:30 CET", "impact": "medium"},
    {"date": "2026-03-11", "name": "US CPI (Feb 2026 data)", "time": "14:30 CET", "impact": "high"},
    {"date": "2026-03-18", "name": "FOMC meeting (rate decision)", "time": "20:00 CET", "impact": "high"},
    {"date": "2026-03-18", "name": "US PPI (Feb 2026 data)", "time": "14:30 CET", "impact": "medium"},
    {"date": "2026-03-19", "name": "ECB rate decision", "time": "14:15 CET", "impact": "high"},
    {"date": "2026-04-10", "name": "US CPI (Mar 2026 data)", "time": "14:30 CET", "impact": "high"},
    {"date": "2026-04-14", "name": "US PPI (Mar 2026 data)", "time": "14:30 CET", "impact": "medium"},
    {"date": "2026-04-29", "name": "FOMC meeting (rate decision)", "time": "20:00 CET", "impact": "high"},
    {"date": "2026-04-30", "name": "ECB rate decision", "time": "14:15 CET", "impact": "high"},
    {"date": "2026-05-12", "name": "US CPI (Apr 2026 data)", "time": "14:30 CET", "impact": "high"},
    {"date": "2026-05-13", "name": "US PPI (Apr 2026 data)", "time": "14:30 CET", "impact": "medium"},
    {"date": "2026-06-10", "name": "US CPI (May 2026 data)", "time": "14:30 CET", "impact": "high"},
    {"date": "2026-06-11", "name": "ECB rate decision", "time": "14:15 CET", "impact": "high"},
    {"date": "2026-06-11", "name": "US PPI (May 2026 data)", "time": "14:30 CET", "impact": "medium"},
    {"date": "2026-06-17", "name": "FOMC meeting (rate decision)", "time": "20:00 CET", "impact": "high"},
    {"date": "2026-07-14", "name": "US CPI (Jun 2026 data)", "time": "14:30 CET", "impact": "high"},
    {"date": "2026-07-15", "name": "US PPI (Jun 2026 data)", "time": "14:30 CET", "impact": "medium"},
    {"date": "2026-07-23", "name": "ECB rate decision", "time": "14:15 CET", "impact": "high"},
    {"date": "2026-07-29", "name": "FOMC meeting (rate decision)", "time": "20:00 CET", "impact": "high"},
    {"date": "2026-08-12", "name": "US CPI (Jul 2026 data)", "time": "14:30 CET", "impact": "high"},
    {"date": "2026-08-13", "name": "US PPI (Jul 2026 data)", "time": "14:30 CET", "impact": "medium"},
    {"date": "2026-09-10", "name": "ECB rate decision", "time": "14:15 CET", "impact": "high"},
    {"date": "2026-09-10", "name": "US PPI (Aug 2026 data)", "time": "14:30 CET", "impact": "medium"},
    {"date": "2026-09-11", "name": "US CPI (Aug 2026 data)", "time": "14:30 CET", "impact": "high"},
    {"date": "2026-09-16", "name": "FOMC meeting (rate decision)", "time": "20:00 CET", "impact": "high"},
    {"date": "2026-10-14", "name": "US CPI (Sep 2026 data)", "time": "14:30 CET", "impact": "high"},
    {"date": "2026-10-15", "name": "US PPI (Sep 2026 data)", "time": "14:30 CET", "impact": "medium"},
    {"date": "2026-10-28", "name": "FOMC meeting (rate decision)", "time": "20:00 CET", "impact": "high"},
    {"date": "2026-10-29", "name": "ECB rate decision", "time": "14:15 CET", "impact": "high"},
    {"date": "2026-11-10", "name": "US CPI (Oct 2026 data)", "time": "14:30 CET", "impact": "high"},
    {"date": "2026-11-13", "name": "US PPI (Oct 2026 data)", "time": "14:30 CET", "impact": "medium"},
    {"date": "2026-12-09", "name": "FOMC meeting (rate decision)", "time": "20:00 CET", "impact": "high"},
    {"date": "2026-12-10", "name": "US CPI (Nov 2026 data)", "time": "14:30 CET", "impact": "high"},
    {"date": "2026-12-15", "name": "US PPI (Nov 2026 data)", "time": "14:30 CET", "impact": "medium"},
    {"date": "2026-12-17", "name": "ECB rate decision", "time": "14:15 CET", "impact": "high"},
]


def get_todays_macro_events(max_items: int = 3) -> list:
    """Geeft de macro-events terug die vandaag plaatsvinden (uit de handmatig bijgehouden kalender)."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    return [e for e in MACRO_EVENTS_2026 if e["date"] == today_str][:max_items]

def get_high_impact_macro_events_for_range(start_date, end_date) -> list:
    """
    Geeft alle macro-events met impact='high' terug die vallen tussen
    start_date en end_date (beide inclusief, als datetime.date-objecten).
    Gebruikt door radar_data.py voor de Week-Agenda op Today -- alleen
    de marktbreed koersgevoelige events (CPI, FOMC, ECB), PPI (impact=
    'medium') blijft hier bewust buiten beeld, dat is te veel ruis voor
    een compacte week-agenda.
    """
    return [
        e for e in MACRO_EVENTS_2026
        if e.get("impact") == "high"
        and start_date <= datetime.strptime(e["date"], "%Y-%m-%d").date() <= end_date
    ]

# Officiele NYSE/beurskalender-feestdagen -- volledig GESLOTEN dagen.
# Bron: officiele NYSE-holiday-kalender (nyse.com/markets/hours-calendars).
# Independence Day 2026 valt op zaterdag 4 juli -> beurs sluit i.p.v.
# daarvoor op de vrijdag ervoor (3 juli), zoals gebruikelijk bij een
# NYSE-feestdag die in het weekend valt. Moet jaarlijks bijgewerkt
# worden zodra de kalender voor het volgende jaar gepubliceerd wordt.
US_MARKET_HOLIDAYS_2026 = [
    {"date": "2026-01-01", "name": "New Year's Day"},
    {"date": "2026-01-19", "name": "Martin Luther King Jr. Day"},
    {"date": "2026-02-16", "name": "Washington's Birthday"},
    {"date": "2026-04-03", "name": "Good Friday"},
    {"date": "2026-05-25", "name": "Memorial Day"},
    {"date": "2026-06-19", "name": "Juneteenth National Independence Day"},
    {"date": "2026-07-03", "name": "Independence Day (observed)"},
    {"date": "2026-09-07", "name": "Labor Day"},
    {"date": "2026-11-26", "name": "Thanksgiving Day"},
    {"date": "2026-12-25", "name": "Christmas Day"},
]


# Bekende VROEGE-sluitingsdagen (beurs blijft open, sluit om 13:00 EST
# i.p.v. de gebruikelijke 16:00 EST) -- alleen de dagen die niet zelf
# al een volledige feestdag zijn.
US_MARKET_EARLY_CLOSE_DAYS_2026 = [
    {"date": "2026-11-27", "name": "Day after Thanksgiving", "close_time": "13:00 EST"},
    {"date": "2026-12-24", "name": "Christmas Eve", "close_time": "13:00 EST"},
]


def get_market_holiday(date_str: str):
    """Geeft de holiday-entry terug als de beurs op deze datum VOLLEDIG gesloten is, anders None."""
    for h in US_MARKET_HOLIDAYS_2026:
        if h["date"] == date_str:
            return h
    return None


def get_market_early_close(date_str: str):
    """Geeft de early-close-entry terug als de beurs op deze datum VROEG sluit, anders None."""
    for e in US_MARKET_EARLY_CLOSE_DAYS_2026:
        if e["date"] == date_str:
            return e
    return None
