"""
2 fixes voor de wekelijkse mail, na een gemiste run (zelfde patroon als
eerder bij de dagelijkse mail -- GitHub's 'best effort'-planning miste de
tick):

1. Tijdstip: 07:00 UTC -> 06:00 UTC, zodat de mail rond 07:00 CET (winter)
   / 08:00 CEST (zomer) aankomt, i.p.v. 08:00/09:00 zoals voorheen.
2. Vangnet: een 2e tick om 06:30 UTC, die zichzelf overslaat als de
   06:00-run al gelukt is (voorkomt een dubbele mail), en anders alsnog
   de scan + mail draait.

Gebruik: python fix_weekly_mail_failsafe.py
Draai dit vanuit je stock_screener-map.
"""
import os

NEW_CONTENT = 'name: Wekelijkse screener en portfolio-mails\n\non:\n  schedule:\n    # Zaterdag:\n    # 06:00 UTC = scan + mail draaien (~07:00 CET winter / ~08:00 CEST zomer)\n    # 06:30 UTC = VANGNET -- als GitHub\'s planner de 06:00-tick een keer\n    #             mist (komt voor, \'best effort\'-planning), proberen we\n    #             het hier nog een keer. Slaat zichzelf over als de\n    #             06:00-run al gelukt is (voorkomt een dubbele mail).\n    - cron: "0 6 * * 6"\n    - cron: "30 6 * * 6"\n  workflow_dispatch:  # laat je dit ook handmatig starten via de GitHub-website, handig om te testen\n\njobs:\n  run-weekly:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Code ophalen\n        uses: actions/checkout@v4\n        with:\n          fetch-depth: 0  # volledige geschiedenis nodig om de laatste commit-datum te checken\n\n      - name: Python installeren\n        uses: actions/setup-python@v5\n        with:\n          python-version: "3.12"\n\n      - name: Dependencies installeren\n        run: pip install -r requirements.txt\n\n      - name: Checken of de scan/mail vandaag al gelukt is\n        id: determine\n        run: |\n          LAST_COMMIT_DATE=$(git log -1 --format=%cd --date=format:%Y-%m-%d -- supertrend_signals.csv 2>/dev/null || echo "never")\n          TODAY=$(date -u +%Y-%m-%d)\n          if [ "$LAST_COMMIT_DATE" = "$TODAY" ] && [ "${{ github.event.schedule }}" = "30 6 * * 6" ]; then\n            echo "already_done_today=true" >> "$GITHUB_OUTPUT"\n          else\n            echo "already_done_today=false" >> "$GITHUB_OUTPUT"\n          fi\n\n      - name: Wekelijks batch-script draaien\n        if: steps.determine.outputs.already_done_today == \'false\'\n        run: python weekly_batch.py\n        env:\n          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}\n          SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_ANON_KEY }}\n          EMAIL_SMTP_SERVER: smtp.gmail.com\n          EMAIL_SMTP_PORT: 587\n          EMAIL_ADDRESS: ${{ secrets.EMAIL_ADDRESS }}\n          EMAIL_APP_PASSWORD: ${{ secrets.EMAIL_APP_PASSWORD }}\n\n      - name: Bijgewerkte bestanden committen en pushen\n        if: steps.determine.outputs.already_done_today == \'false\'\n        run: |\n          git config --global user.name "github-actions[bot]"\n          git config --global user.email "github-actions[bot]@users.noreply.github.com"\n          for f in supertrend_signals.csv snowball_signals.csv rocket_list_signals.csv; do\n            [ -f "$f" ] && git add "$f"\n          done\n          git diff --staged --quiet || git commit -m "Automatische wekelijkse update"\n          git pull --rebase origin main\n          git push\n'

os.makedirs(".github/workflows", exist_ok=True)
with open(".github/workflows/weekly.yml", "w", encoding="utf-8") as f:
    f.write(NEW_CONTENT)
print(f"Klaar. 'weekly.yml' overschreven ({len(NEW_CONTENT)} tekens).")
print("git add . && git commit -m 'Add failsafe retry + earlier time for weekly email' && git push")
