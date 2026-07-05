# Supertrend Stock Screener

Losstaand van de crypto-bot: screent AEX + Nasdaq-100 (QQQ) op recente
bullish Supertrend-omslagen (weekly), en stuurt optioneel een e-mail.
Dit is een **signaal/screener**, geen geautomatiseerde strategie — jij
beslist zelf of je op basis van een signaal iets doet.

## Structuur

| Bestand | Wat het doet |
|---|---|
| `indicators.py` | Supertrend, EMA, en dag-naar-week-resampling |
| `emailer.py` | E-mail-notificaties versturen (Gmail/Outlook/etc.) |
| `screener.py` | Hoofdscript: haalt data op, checkt signalen, verstuurt mail |

## Installatie

```
pip install -r requirements.txt
```

Kopieer `.env.example` naar `.env` en vul je e-mailgegevens in (optioneel —
zonder e-mail-instellingen print het script de resultaten gewoon, zonder
te mailen).

## Gebruiken

```
python screener.py
```

Standaard wordt de samenstelling van AEX en Nasdaq-100 automatisch van
Wikipedia gehaald. Wil je een eigen vaste lijst (bv. je DEGIRO-watchlist)?
Open `screener.py` en zet `TICKERS` op je eigen lijst i.p.v. `None`.

Instellingen om te 'tweaken' staan bovenin `screener.py`:
- `ATR_LENGTH` / `ATR_MULTIPLIER` — de Supertrend zelf
- `LOOKBACK_WEEKS_FOR_SIGNAL` — hoe 'vers' een omslag moet zijn
- `TREND_FILTER_EMA_LENGTH` — extra brede-trend-context

## Automatisch laten draaien (Windows Taakplanner)

Zie de eerdere uitleg — zelfde principe, alleen wijst het pad nu naar
deze `stock_screener`-map in plaats van `crypto_bot`.

## Volgende stap: dashboard

Dit project is bewust simpel en command-line-gebaseerd gehouden, zodat
het een schone basis is om een dashboard/front-end op te bouwen zonder
ballast van de crypto-bot-codebase.
