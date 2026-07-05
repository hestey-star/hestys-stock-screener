"""
Dashboard: visualiseert de resultaten van screener.py en portfolio_watch.py.
(Deze code-commentaren blijven in het Nederlands -- alleen de daadwerkelijk
zichtbare website-tekst is naar het Engels vertaald.)

Navigatie is bewust GEEN st.tabs(): de opdracht was dat de startpagina
leeg is totdat je expliciet op 'Welcome' (of een andere nav-link/het logo)
klikt. Dat is met st.tabs() niet mogelijk (die toont altijd meteen de
inhoud van het eerste tabblad) -- daarom gebruiken we hier een eigen
navigatiebalk van HTML-links die de URL-query-parameter '?view=...'
aanpassen, en tonen we inhoud alleen als die parameter overeenkomt.
Dat maakt het logo ook op een natuurlijke manier klikbaar (het is zelf
ook zo'n link, naar '?view=welcome').

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

st.set_page_config(page_title="Hesty's Signals", page_icon="◆", layout="wide")

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

/* Header: logo (klikbaar, linkt naar Welcome) + navigatiebalk eronder */
.app-header {
    padding: 1.2rem 0 1rem 0;
    border-bottom: 2px solid #1FAE96;
    margin-bottom: 1.5rem;
}
.app-header-top {
    display: flex;
    align-items: center;
    gap: 0.9rem;
    text-decoration: none !important;
    margin-bottom: 1rem;
}
.app-header-top:hover, .app-header-top:visited, .app-header-top:active {
    text-decoration: none !important;
}
.app-header h1 {
    margin: 0 !important;
    font-size: 1.8rem !important;
    line-height: 1.1;
    color: #EAEDF1 !important;
}
.app-header .tagline {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.08em;
    color: #8992A3 !important;
    margin-top: 0.15rem;
}
.nav-bar {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}
.nav-link, .nav-link:visited, .nav-link:active {
    font-family: 'Inter', sans-serif;
    font-size: 0.9rem;
    font-weight: 500;
    padding: 0.4rem 1rem;
    border-radius: 6px;
    text-decoration: none !important;
    color: #8992A3 !important;
    border: 1px solid transparent;
}
.nav-link:hover {
    color: #EAEDF1 !important;
    border: 1px solid #1FAE96;
}
.nav-link.active, .nav-link.active:visited {
    color: #1FAE96 !important;
    background: rgba(31, 174, 150, 0.1);
    border: 1px solid #1FAE96;
}

/* Compacte, met lijntjes gescheiden posities-lijst in 'Your positions' */
.holding-text {
    font-size: 0.85rem;
    color: #EAEDF1;
}
.holding-divider {
    border: none;
    border-top: 1px solid #232D3A;
    margin: 0.35rem 0;
}

/* Compacte, duidelijk afgebakende tabel voor 'Your positions' */
.positions-table {
    width: 100%;
    border-collapse: collapse;
    background: #141B24;
    border: 1px solid #232D3A;
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 1.2rem;
}
.positions-table th {
    text-align: left;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.05em;
    color: #8992A3;
    padding: 0.5rem 0.9rem;
    border-bottom: 1px solid #232D3A;
}
.positions-table td {
    padding: 0.4rem 0.9rem;
    font-size: 0.85rem;
    color: #EAEDF1;
    border-bottom: 1px solid #1B2536;
}
.positions-table tr:last-child td {
    border-bottom: none;
}
.positions-table code {
    color: #1FAE96;
    background: none;
    font-size: 0.85rem;
}

/* Iets compactere tabellen: kleinere tekst in de databladen */
[data-testid="stDataFrame"] * {
    font-size: 0.85rem !important;
}
</style>
""", unsafe_allow_html=True)


def file_last_modified(path: str) -> str:
    if not os.path.exists(path):
        return "never"
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


# --- Navigatie: leest de '?view=...'-parameter uit de URL. Geen parameter
#     (zoals bij het eerste bezoek) betekent: nog geen tabblad gekozen. ---
current_view = st.query_params.get("view", None)


def _nav_class(view_name: str) -> str:
    return "nav-link active" if current_view == view_name else "nav-link"


st.markdown(
    f"""
    <div class="app-header">
        <a href="?view=welcome" class="app-header-top" target="_self">
            <svg width="42" height="42" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                <rect x="6" y="6" width="36" height="36" rx="8" fill="none" stroke="#1FAE96"
                      stroke-width="2.5" transform="rotate(45 24 24)"/>
                <polyline points="13,30 20,22 26,26 33,15" fill="none" stroke="#1FAE96"
                          stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                <circle cx="33" cy="15" r="2.3" fill="#1FAE96"/>
            </svg>
            <div>
                <h1>Hesty's Signals</h1>
                <div class="tagline">PERSONAL &middot; CLEAR &middot; EASY</div>
            </div>
        </a>
        <div class="nav-bar">
            <a href="?view=welcome" class="{_nav_class('welcome')}" target="_self">Welcome</a>
            <a href="?view=screener" class="{_nav_class('screener')}" target="_self">New Signals</a>
            <a href="?view=portfolio" class="{_nav_class('portfolio')}" target="_self">My Portfolio</a>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# VIEW: WELCOME
# ============================================================
if current_view == "welcome":
    st.markdown("### What is this?")
    st.write(
        "Hesty's Signals is a personal research tool for exploring stock market trends. "
        "It has two parts, and you can jump straight to either one using the navigation above."
    )

    st.markdown("#### New Signals")
    st.write(
        "Scans the AEX, Nasdaq-100, S&P 500, DAX, and CAC 40 every week for stocks that "
        "just turned bullish on a weekly Supertrend indicator. Each signal is scored on "
        "several factors -- how fresh the trend change is, ROIC level and trend, relative "
        "strength versus the index, volume confirmation, earnings surprises, and how the "
        "price compares to analyst price targets. This part is public, no login required."
    )

    st.markdown("#### My Portfolio")
    st.write(
        "Log in with Google to privately track your own holdings. See their current trend "
        "status, recent news, and get a personal weekly email update -- visible only to you."
    )

# ============================================================
# VIEW: SCREENER (public, no login required)
# ============================================================
elif current_view == "screener":
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Signals")
        st.caption(f"Last updated: {file_last_modified('supertrend_signals.csv')}")
    with col2:
        run_screener = st.button("Refresh now (takes a while, 10-20+ min)", key="run_screener", type="primary")

    if run_screener:
        with st.spinner("Screener is running... this can take a while (AEX + Nasdaq-100 + S&P 500 + DAX + CAC40)."):
            import screener
            screener.main()
        st.success("Done! Refresh the page to see the new results.")

    df_screener = load_screener_data()
    if df_screener is None or df_screener.empty:
        st.info("No results yet. Run 'python screener.py' first, or click Refresh above.")
    else:
        df_screener = df_screener.sort_values("score", ascending=False)

        min_score = st.slider("Minimum score", float(df_screener["score"].min()),
                               float(df_screener["score"].max()), float(df_screener["score"].min()))
        filtered = df_screener[df_screener["score"] >= min_score].copy()

        # 'benchmark' is interne informatie (welke index gebruikt is voor de
        # vergelijking) -- niet interessant genoeg om te tonen, dus weg ermee
        filtered.drop(columns=["benchmark"], errors="ignore", inplace=True)

        # Nette, leesbare Engelse kolomnamen i.p.v. de ruwe Python-veldnamen met underscores
        column_labels = {
            "ticker": "Ticker", "flip_date": "Flip Date", "weken_geleden": "Weeks Ago",
            "voorgaande_trend_weken": "Prior Trend (Weeks)", "prijs_bij_omslag": "Price at Flip",
            "prijs_nu": "Price Now", "sinds_omslag_pct": "Since Flip", "boven_ema20": "Above EMA20",
            "relatieve_sterkte": "Relative Strength", "roic_pct": "ROIC", "roic_trend": "ROIC Trend",
            "volume_bevestigd": "Volume Confirmed", "earnings_surprise_pct": "Earnings Surprise",
            "earnings_beat": "Earnings Beat", "earnings_date": "Earnings Date",
            "weken_sinds_earnings": "Weeks Since Earnings", "fair_value": "Fair Value",
            "afwijking_fair_value_pct": "Vs Fair Value", "score": "Score",
        }
        filtered.rename(columns=column_labels, inplace=True)

        # Score als 3e kolom, de rest in de logische volgorde erachter
        preferred_order = [
            "Ticker", "Flip Date", "Score", "Weeks Ago", "Prior Trend (Weeks)",
            "Price at Flip", "Price Now", "Since Flip", "Above EMA20",
            "Relative Strength", "ROIC", "ROIC Trend", "Volume Confirmed",
            "Earnings Surprise", "Earnings Beat", "Earnings Date",
            "Weeks Since Earnings", "Fair Value", "Vs Fair Value",
        ]
        ordered_cols = [c for c in preferred_order if c in filtered.columns]
        ordered_cols += [c for c in filtered.columns if c not in ordered_cols]  # vangnet voor eventuele extra kolommen
        filtered = filtered[ordered_cols]

        format_dict = {
            "Price at Flip": "{:.2f}", "Price Now": "{:.2f}",
            "Since Flip": "{:+.2f}%", "Relative Strength": "{:+.2f}%",
            "ROIC": "{:+.1f}%", "Score": "{:.2f}",
            "Earnings Surprise": "{:+.1f}%", "Vs Fair Value": "{:+.1f}%",
            "Fair Value": "{:.2f}", "Weeks Since Earnings": "{:.0f}",
        }
        format_dict = {k: v for k, v in format_dict.items() if k in filtered.columns}

        st.dataframe(
            filtered.style.format(format_dict, na_rep="unknown")
                          .background_gradient(subset=["Score"], cmap="Greens")
                          .background_gradient(subset=["Relative Strength"], cmap="RdYlGn"),
            width="stretch",
            height=500,
        )
        st.caption(f"{len(filtered)} of {len(df_screener)} signals shown (filtered by score).")

# ============================================================
# VIEW: MY PORTFOLIO (personal, login required)
# ============================================================
elif current_view == "portfolio":
    if not st.user.is_logged_in:
        st.markdown(
            '<div class="privacy-seal">&#128274; PRIVATE &middot; visible only to you</div>',
            unsafe_allow_html=True,
        )
        st.info("Log in to track your own positions. No one else can see what you add.")
        st.button("Log in with Google", on_click=st.login, type="primary")
        st.stop()

    import database
    from portfolio_watch import check_holding

    user_email = st.user.email
    st.markdown(
        '<div class="privacy-seal">&#128274; PRIVATE &middot; visible only to you</div>',
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns([4, 1])
    with col1:
        st.subheader(f"Welcome, {st.user.name}")
        st.caption(user_email)
    with col2:
        st.button("Log out", on_click=st.logout)

    with st.expander("Email preferences", expanded=False):
        prefs = database.get_user_preferences(user_email)
        wants_screener = st.checkbox(
            "Receive the weekly screener email (new signals from AEX/Nasdaq-100/S&P500/DAX/CAC40)",
            value=prefs["wants_screener_email"],
        )
        wants_portfolio = st.checkbox(
            "Receive the weekly portfolio email (status + news for your own positions)",
            value=prefs["wants_portfolio_email"],
        )
        if st.button("Save preferences"):
            database.set_user_preferences(user_email, wants_screener, wants_portfolio)
            st.success("Preferences saved!")

    st.markdown("### Your positions")

    holdings = database.get_user_holdings(user_email)

    if not holdings:
        st.info("You haven't added any positions yet. Add your first one below.")
    else:
        rows_html = "".join(
            f'<tr><td>{h["naam"]}</td><td><code>{h["ticker"]}</code></td></tr>'
            for h in holdings
        )
        st.markdown(
            f"""
            <table class="positions-table">
                <thead><tr><th>Name</th><th>Ticker</th></tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
            """,
            unsafe_allow_html=True,
        )

        remove_options = {f"{h['naam']} ({h['ticker']})": h["id"] for h in holdings}
        rcol1, rcol2 = st.columns([4, 1])
        with rcol1:
            to_remove_label = st.selectbox(
                "Remove a position", list(remove_options.keys()), label_visibility="collapsed"
            )
        with rcol2:
            if st.button("Remove"):
                database.delete_holding(remove_options[to_remove_label], user_email)
                st.rerun()

    st.markdown("**Add a new position**")
    search_query = st.text_input(
        "Search for a company or crypto (e.g. 'Tesla', 'ASML', 'Bitcoin')", key="ticker_search"
    )

    selected_symbol = None
    selected_name = None

    if search_query:
        try:
            search_results = yf.Search(search_query, max_results=8).quotes
        except Exception as exc:
            search_results = []
            st.caption(f"Search failed: {exc}")

        if search_results:
            options = {}
            for r in search_results:
                name = r.get("shortname") or r.get("longname") or r.get("symbol")
                label = f"{name} ({r.get('symbol')}) -- {r.get('exchange', '')}"
                options[label] = r

            chosen_label = st.selectbox("Choose the right match", list(options.keys()))
            chosen = options[chosen_label]
            selected_symbol = chosen.get("symbol")
            selected_name = chosen.get("shortname") or chosen.get("longname") or selected_symbol
        else:
            st.caption("No results found for this search -- try a different name.")

    if selected_symbol and st.button("Add to my portfolio", type="primary"):
        with st.spinner(f"Checking data for {selected_symbol}..."):
            try:
                test_df = yf.Ticker(selected_symbol).history(period="5d")
            except Exception as exc:
                test_df = None
                st.error(f"Could not validate {selected_symbol}: {exc}")

        if test_df is not None and test_df.empty:
            st.error(f"No recent price data found for {selected_symbol} -- not added.")
        elif test_df is not None:
            database.add_holding(user_email, selected_name, selected_symbol)
            st.success(f"{selected_name} ({selected_symbol}) added!")
            st.rerun()

    st.divider()

    if holdings and st.button("Check my portfolio now", key="check_my_portfolio", type="primary"):
        with st.spinner("Checking your positions..."):
            results = []
            for holding in holdings:
                result = check_holding(holding["naam"], holding["ticker"])
                if result:
                    results.append(result)

        if not results:
            st.warning("Could not check any of your positions -- please verify the tickers.")
        else:
            df_my_portfolio = pd.DataFrame(results)
            changed = df_my_portfolio[df_my_portfolio["recent_gewijzigd"] == True]  # noqa: E712
            if len(changed) > 0:
                st.warning(f"{len(changed)} position(s) recently changed trend: "
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

            st.markdown("### Recent news")
            any_news = False
            for _, row in df_my_portfolio.iterrows():
                if row["nieuws"]:
                    any_news = True
                    with st.expander(f"{row['naam']} ({row['ticker']}) -- {len(row['nieuws'])} item(s)"):
                        for item in row["nieuws"]:
                            pub_date = item["published"].strftime("%Y-%m-%d")
                            st.markdown(f"**[{item['title']}]({item['link']})**  \n"
                                        f"*{item['publisher']}, {pub_date}*")
            if not any_news:
                st.caption("No recent news found for your positions.")

    st.caption("You'll also automatically receive a weekly email with this update, "
               "at the address you're logged in with.")

st.divider()
st.caption("This dashboard shows technical signals (Supertrend), fundamental context (ROIC estimate), "
           "and news. It is not an automated strategy and not financial advice.")
