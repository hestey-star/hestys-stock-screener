"""
Dagelijks scan-script: draait ALLEEN de dagelijkse screener-scan en slaat
de resultaten op (supertrend_signals_daily.csv + top_movers.csv).

Verstuurt zelf GEEN e-mails meer -- dat gebeurt nu in het aparte
daily_email_dispatch.py, dat per regio getimed apart draait (zodat
gebruikers in Europa/VS-oost/VS-west allemaal rond hun eigen ochtend
07:00 een mail kunnen krijgen, in plaats van 1 vast tijdstip voor
iedereen). Dit script draait zelf maar 1x per dag, vroeg (voor de
Europese ochtend), zodat de data klaarstaat voor alle latere dispatch-runs.

Bedoeld om te draaien via GitHub Actions (dus GEEN Streamlit-context --
leest configuratie via omgevingsvariabelen).

Gebruik: python daily_batch.py
"""
from __future__ import annotations

import screener_daily

if __name__ == "__main__":
    # send_own_email=False: het versturen gebeurt nu apart, via
    # daily_email_dispatch.py (per regio getimed)
    screener_daily.main(send_own_email=False)
    print("\nScan klaar.")
