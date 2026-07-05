"""
Dashboard: visualiseert de resultaten van screener.py en portfolio_watch.py.

Dit dashboard LEEST de CSV/JSON-bestanden die de andere twee scripts
produceren -- het haalt zelf geen nieuwe data op (behalve via de
'Ververs nu'-knoppen), zodat het snel laadt.

Lokaal draaien:
    streamlit run dashboard.py

Op internet zetten (gratis, voor jezelf of om te delen):
    1. Zet dit project op GitHub (in een repository)
    2. Ga naar https://share.streamlit.io, log in met GitHub
    3. Wijs naar je repository en dit bestand (dashboard.py)
    4. Streamlit Cloud host 'm gratis op een publieke URL

Vereist: pip install -r requirements.txt (incl. streamlit)
"""
from __future__ import annotations

import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Trading Signalen Dashboard", page_icon="◆", layout="wide")

# --- Visuele identiteit: donkere 'kluis/terminal'-stijl, geen standaard-look ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, p, span, div, label {
    font-family: 'Inter', sans-serif;
}
h1, h2, h3 {
    font-family: 'Fraunces', serif !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em;
}
code, .stDataFrame, [data-testid="stMetricValue"] {
    font-family: 'IBM Plex Mono', monospace !important;
}

/* Het 'verzegeld'-badge: het signatuurelement dat vertrouwelijkheid concreet maakt */
.privacy-seal {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.9rem;
    border: 1px solid #1FAE96;
    border-radius: 999px;
    background: rgba(31, 174, 150, 0.08);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.8rem;
    color: #1FAE96;
    margin-bottom: 1rem;
}

/* Zorgt dat brede tabellen horizontaal kunnen scrollen, zonder de
   verticale hoogte/scroll van Streamlit's eigen tabel-weergave te
   verstoren (vandaar: alleen deze ene laag, niet de kind-elementen) */
[data-testid="stDataFrame"] {
    overflow-x: auto !important;
}

/* Duidelijke header-balk: onderscheidt de titel visueel van de inhoud eronder */
.app-header {
    padding: 1.2rem 0 1rem 0;
    border-bottom: 2px solid #1FAE96;
    margin-bottom: 1.5rem;
}
.app-header h1 {
    margin: 0 !important;
}

/* Iets compactere tabellen: kleinere tekst in de databladen */
[data-testid="stDataFrame"] * {
    font-size: 0.85rem !important;
}
</style>
""", unsafe_allow_html=True)


def file_last_modified(path: str) -> str:
    if not os.path.exists(path):
        return "nooit"
    ts = os.path.getmtime(path)
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def load_screener_data():
    if not os.path.exists("supertrend_signals.csv"):
        return None
    df = pd.read_csv("supertrend_signals.csv")
    return df


def load_portfolio_data():
    if not os.path.exists("portfolio_watch.csv"):
        return None
    df = pd.read_csv("portfolio_watch.csv")
    return df


def load_portfolio_news():
    if not os.path.exists("portfolio_watch_news.json"):
        return {}
    with open("portfolio_watch_news.json", encoding="utf-8") as f:
        return json.load(f)


st.markdown(
    '<div class="app-header"><h1>Trading Signalen Dashboard</h1></div>',
    unsafe_allow_html=True,
)
st.caption("Persoonlijk onderzoeksproject -- geen koopadvies. Doe altijd je eigen verdere afweging.")

tab_screener, tab_portfolio = st.tabs(["Nieuwe signalen (Screener)", "Mijn Portfolio"])

# ============================================================
# TAB 1: SCREENER (publiek, geen login nodig)
# ============================================================
with tab_screener:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Nieuwe bullish Supertrend-signalen")
        st.caption(f"Laatst bijgewerkt: {file_last_modified('supertrend_signals.csv')}")
    with col2:
        run_screener = st.button("Ververs nu (duurt lang, 10-20+ min)", key="run_screener", type="primary")

    if run_screener:
        with st.spinner("Screener draait... dit kan lang duren (AEX + Nasdaq-100 + S&P 500 + DAX + CAC40)."):
            import screener
            screener.main()
        st.success("Klaar! Ververs de pagina om de nieuwe resultaten te zien.")

    df_screener = load_screener_data()
    if df_screener is None or df_screener.empty:
        st.info("Nog geen resultaten gevonden. Draai eerst 'python screener.py', of klik hierboven op Ververs.")
    else:
        df_screener = df_screener.sort_values("score", ascending=False)

        min_score = st.slider("Minimale score", float(df_screener["score"].min()),
                               float(df_screener["score"].max()), float(df_screener["score"].min()))
        filtered = df_screener[df_screener["score"] >= min_score]

        format_dict = {
            "prijs_bij_omslag": "{:.2f}", "prijs_nu": "{:.2f}",
            "sinds_omslag_pct": "{:+.2f}%", "relatieve_sterkte": "{:+.2f}%",
            "roic_pct": "{:+.1f}%", "score": "{:.2f}",
            "earnings_surprise_pct": "{:+.1f}%", "afwijking_fair_value_pct": "{:+.1f}%",
            "fair_value": "{:.2f}",
        }
        format_dict = {k: v for k, v in format_dict.items() if k in filtered.columns}

        st.dataframe(
            filtered.style.format(format_dict, na_rep="onbekend")
                          .background_gradient(subset=["score"], cmap="Greens")
                          .background_gradient(subset=["relatieve_sterkte"], cmap="RdYlGn"),
            width="stretch",
            height=500,
        )
        st.caption(f"{len(filtered)} van {len(df_screener)} signalen getoond (gefilterd op score).")

# ============================================================
# TAB 2: MIJN PORTFOLIO (persoonlijk, login vereist)
# ============================================================
with tab_portfolio:
    if not st.user.is_logged_in:
        st.markdown(
            '<div class="privacy-seal">&#128274; PRIVÉ &middot; alleen zichtbaar voor jou</div>',
            unsafe_allow_html=True,
        )
        st.info("Log in om je eigen posities bij te houden. Niemand anders ziet wat je toevoegt.")
        st.button("Inloggen met Google", on_click=st.login, type="primary")
        st.stop()

    import database
    from portfolio_watch import check_holding

    user_email = st.user.email
    st.markdown(
        '<div class="privacy-seal">&#128274; PRIVÉ &middot; alleen zichtbaar voor jou</div>',
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns([4, 1])
    with col1:
        st.subheader(f"Welkom, {st.user.name}")
        st.caption(user_email)
    with col2:
        st.button("Uitloggen", on_click=st.logout)

    with st.expander("E-mail-voorkeuren", expanded=False):
        prefs = database.get_user_preferences(user_email)
        wants_screener = st.checkbox(
            "Wekelijkse screener-mail ontvangen (nieuwe signalen uit AEX/Nasdaq-100/S&P500/DAX/CAC40)",
            value=prefs["wants_screener_email"],
        )
        wants_portfolio = st.checkbox(
            "Wekelijkse portfolio-mail ontvangen (status + nieuws van jouw eigen posities)",
            value=prefs["wants_portfolio_email"],
        )
        if st.button("Voorkeuren opslaan"):
            database.set_user_preferences(user_email, wants_screener, wants_portfolio)
            st.success("Voorkeuren opgeslagen!")

    st.markdown("### Jouw posities")

    holdings = database.get_user_holdings(user_email)

    if not holdings:
        st.info("Je hebt nog geen posities toegevoegd. Voeg hieronder je eerste toe.")
    else:
        for holding in holdings:
            hcol1, hcol2, hcol3 = st.columns([3, 3, 1])
            hcol1.write(holding["naam"])
            hcol2.write(holding["ticker"])
            if hcol3.button("Verwijder", key=f"delete_{holding['id']}"):
                database.delete_holding(holding["id"], user_email)
                st.rerun()

    st.markdown("**Nieuwe positie toevoegen**")
    search_query = st.text_input(
        "Zoek een bedrijf of crypto (bv. 'Tesla', 'ASML', 'Bitcoin')", key="ticker_search"
    )

    selected_symbol = None
    selected_name = None

    if search_query:
        try:
            search_results = yf.Search(search_query, max_results=8).quotes
        except Exception as exc:
            search_results = []
            st.caption(f"Zoeken mislukt: {exc}")

        if search_results:
            options = {}
            for r in search_results:
                name = r.get("shortname") or r.get("longname") or r.get("symbol")
                label = f"{name} ({r.get('symbol')}) -- {r.get('exchange', '')}"
                options[label] = r

            chosen_label = st.selectbox("Kies de juiste match", list(options.keys()))
            chosen = options[chosen_label]
            selected_symbol = chosen.get("symbol")
            selected_name = chosen.get("shortname") or chosen.get("longname") or selected_symbol
        else:
            st.caption("Geen resultaten gevonden voor deze zoekopdracht -- probeer een andere naam.")

    if selected_symbol and st.button("Toevoegen aan mijn portfolio", type="primary"):
        with st.spinner(f"Data controleren voor {selected_symbol}..."):
            try:
                test_df = yf.Ticker(selected_symbol).history(period="5d")
            except Exception as exc:
                test_df = None
                st.error(f"Kon {selected_symbol} niet valideren: {exc}")

        if test_df is not None and test_df.empty:
            st.error(f"Geen recente koersdata gevonden voor {selected_symbol} -- niet toegevoegd.")
        elif test_df is not None:
            database.add_holding(user_email, selected_name, selected_symbol)
            st.success(f"{selected_name} ({selected_symbol}) toegevoegd!")
            st.rerun()

    st.divider()

    if holdings and st.button("Check mijn portfolio nu", key="check_my_portfolio", type="primary"):
        with st.spinner("Bezig met checken van je posities..."):
            results = []
            for holding in holdings:
                result = check_holding(holding["naam"], holding["ticker"])
                if result:
                    results.append(result)

        if not results:
            st.warning("Kon geen van je posities checken -- controleer of de tickers kloppen.")
        else:
            df_my_portfolio = pd.DataFrame(results)
            changed = df_my_portfolio[df_my_portfolio["recent_gewijzigd"] == True]  # noqa: E712
            if len(changed) > 0:
                st.warning(f"{len(changed)} positie(s) recent van trend gewisseld: "
                           + ", ".join(f"{r['naam']} ({r['status']})" for _, r in changed.iterrows()))

            def _highlight_status(row):
                color = "#1B3A2E" if row["status"] == "BULLISH" else (
                    "#3A1F1D" if row["status"] == "BEARISH" else "#332B14"
                )
                return [f"background-color: {color}"] * len(row)

            display_cols = [c for c in df_my_portfolio.columns if c != "nieuws"]
            st.dataframe(
                df_my_portfolio[display_cols].style.apply(_highlight_status, axis=1),
                width="stretch",
                height=min(38 * (len(df_my_portfolio) + 1), 300),
            )

            st.markdown("### Recent nieuws")
            any_news = False
            for _, row in df_my_portfolio.iterrows():
                if row["nieuws"]:
                    any_news = True
                    with st.expander(f"{row['naam']} ({row['ticker']}) -- {len(row['nieuws'])} bericht(en)"):
                        for item in row["nieuws"]:
                            pub_date = item["published"].strftime("%Y-%m-%d")
                            st.markdown(f"**[{item['title']}]({item['link']})**  \n"
                                        f"*{item['publisher']}, {pub_date}*")
            if not any_news:
                st.caption("Geen recent nieuws gevonden voor je posities.")

    st.caption("Je ontvangt ook wekelijks automatisch een e-mail met deze update, "
               "op het adres waarmee je bent ingelogd.")

st.divider()
st.caption("Dit dashboard toont technische signalen (Supertrend), fundamentele context (ROIC-schatting) "
           "en nieuws. Het is geen geautomatiseerde strategie en geen financieel advies.")
