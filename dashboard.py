"""
Dashboard: visualiseert de resultaten van screener.py en portfolio_watch.py.
(Deze code-commentaren blijven in het Nederlands -- alleen de daadwerkelijk
zichtbare website-tekst is naar het Engels vertaald.)

Navigatie gebruikt sinds de stap-B-herstructurering st.navigation() (met
position="hidden") i.p.v. handmatige ?view=-query-param-routing -- elke
pagina heeft nu een eigen URL-pad (bv. /discover, /today), en de zijbalk
gebruikt st.page_link() i.p.v. gewone HTML-<a>-links. Dat voorkomt de
volledige pagina-herlading (met bijbehorende zwarte flits) die er bij de
oude opzet was.

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
import subprocess
import base64
import time
from datetime import datetime, timezone, timedelta, date

import altair as alt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import stripe
import streamlit as st
import streamlit.components.v1 as components
import urllib.parse
import yfinance as yf

from emailer import send_email
import database
import radar_data

st.set_page_config(page_title="Hesty's", page_icon="◆", layout="wide")

# --- Visuele identiteit: donkere 'kluis/terminal'-stijl, geen standaard-look ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,400,0,0&display=swap');

/* Streamlit's eigen branding verbergen (hamburger-menu, footer, Deploy-
   knop/toolbar, de regenboog-decoratiebalk bovenaan, en de "Running..."-
   statuswidget) -- voor een schonere, minder duidelijk-'gemaakt-met-
   Streamlit'-uitstraling.
   BEWUST GEEN header {visibility:hidden} hier -- Hesty's gebruikt een
   custom zijbalk-navigatie (st.navigation(..., position="hidden") +
   een eigen st.sidebar-menu), en de zijbalk-toggle-knop op mobiel/
   smalle schermen kon niet met zekerheid worden bevestigd als volledig
   ONafhankelijk van de algehele header-balk. Het risico op een
   onbruikbare app (geen manier meer om de zijbalk te openen op mobiel)
   was te groot om te riskeren voor een puur cosmetische wijziging. */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
/* stToolbar zelf NIET meer volledig verbergen -- was de oorzaak van een
   bug waarbij het zijbalk-uitklap-pijltje (zichtbaar zodra de zijbalk
   is ingeklapt) na het inklappen nergens meer te vinden was: dat
   pijltje leeft kennelijk in dezelfde header-regio als deze toolbar.
   In plaats daarvan specifiek ALLEEN de Streamlit Cloud-actie-iconen
   verbergen (Share/ster/potlood/GitHub, rechtsboven) via de smallere
   stToolbarActions-testid -- die zit blijkbaar niet in dezelfde regio
   als het pijltje, dus dit is veiliger dan de hele toolbar te raken. */
div[data-testid="stToolbarActions"] {visibility: hidden; height: 0%;}
div[data-testid="stDecoration"] {visibility: hidden; height: 0%;}
div[data-testid="stStatusWidget"] {visibility: hidden; height: 0%;}

/* --- Ontwerptaal-fundament: kleuren als CSS-variabelen, 1 centrale
   plek om het palet te definieren i.p.v. losse rgba(...)-waarden overal
   door de code heen. Jade is bewust GERESERVEERD voor primaire acties,
   positieve waarden en het merk zelf -- secundaire elementen (randen,
   info-boxjes) gebruiken de neutrale grijsblauwe kleuren, zodat jade
   opvalt wanneer het verschijnt i.p.v. overal tegelijk te 'wassen'. ---
*/
html {
    /* Smooth scroll voor anchor-links (bv. de teaser-links onder Momentocrats/
       Snowballers naar #activate-signals) -- pure CSS, geen JS nodig. */
    scroll-behavior: smooth;
}

/* HET ene, globale bovenmarge-patroon voor _uniform_section_header_html()
   (Today, My Portfolio, Discover-screeners) -- EENMALIG hier gedefinieerd
   i.p.v. per aanroep opnieuw als losse <style>-tag geinjecteerd (dat gaf
   op pagina's met meerdere secties na elkaar, zoals de 3 Discover-
   screeners, inconsistent gedrag onder Streamlit's React-rendering).
   mt-10 op desktop (md:), mt-8 op mobiel -- garandeert dat de witruimte
   tussen ELK paar opeenvolgende secties die deze klasse gebruiken exact
   gelijk is, want er is nu maar 1 plek waar deze waarde kan worden
   gedefinieerd. */
.hesty-section-gap { margin-top: 2rem !important; }
@media (min-width: 768px) {
    .hesty-section-gap { margin-top: 2.5rem !important; }
}
/* Responsieve, COMPACTE titelgrootte voor _uniform_section_header_html()'s
   <h2> (text-base mobiel, text-lg desktop) -- !important overal, want een
   kale <h2>-tag heeft anders een fors grotere browser/Streamlit-standaard-
   grootte (~1.5em), wat eerder precies de 'veel te grote, lompe letters'
   verklaarde. Kleur/gewicht hier ook in de klasse i.p.v. inline, om
   dezelfde reden. */
.hesty-section-title-text {
    font-size: 1rem !important;
    font-weight: 700 !important;
    color: #F1F5F9 !important;
    line-height: 1.3 !important;
}
@media (min-width: 768px) {
    .hesty-section-title-text { font-size: 1.125rem !important; }
}

.discover-teaser-link, .discover-teaser-link:visited {
    /* Minimalistische 'Pro'-knop i.p.v. een platte tekstlink -- geen
       achtergrondvulling, een flinterdunne rand, slanke padding. Blijft
       een <a>-tag (geen widget), dus display:inline-block i.p.v. block:
       de knop moet zich naar z'n eigen tekst voegen, niet de volle
       breedte innemen zoals een tekstlink deed. margin-top(-only, geen
       bottom) zorgt dat de onderkant van de screener nog steeds GEEN
       eigen marge heeft -- de afstand naar de volgende sectie komt nog
       steeds uitsluitend van diens .hesty-section-gap-bovenmarge.
       !important overal -- Streamlit's eigen basis-linkstijl (kleur +
       underline) bleek eerder al vaker voorrang te krijgen boven een
       gewone class-selector (zelfde reden als bij de marketingknoppen
       en de <hr>-lijnen). */
    display: inline-block !important;
    color: #34D399 !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
    text-decoration: none !important;
    cursor: pointer !important;
    background: transparent !important;
    border: 1px solid rgba(51,65,85,0.7) !important;
    border-radius: 8px !important;
    padding: 0.4rem 1rem !important;
    margin: 0.75rem 0 0 0 !important;
    box-sizing: border-box !important;
    max-width: 100% !important;
}
.discover-teaser-link:hover {
    border-color: rgba(52,211,153,0.5) !important;
    text-decoration: none !important;
}

:root {
    --color-jade: #1FAE96;
    --color-jade-soft: rgba(31, 174, 150, 0.12);
    --color-negative: #E5484D;
    --color-warning: #D4A857;
    --color-warning-soft: rgba(212, 168, 87, 0.12);
    --color-text-primary: #EAEDF1;
    --color-text-secondary: #8992A3;
    --color-border-neutral: rgba(137, 146, 163, 0.25);
    --color-bg-elevated: rgba(255, 255, 255, 0.03);
}

.material-symbols-outlined {
    font-family: 'Material Symbols Outlined';
    font-weight: normal;
    font-style: normal;
    display: inline-block;
    line-height: 1;
    text-transform: none;
    letter-spacing: normal;
    word-wrap: normal;
    white-space: nowrap;
    direction: ltr;
    vertical-align: middle;
}

html, body, p, span, div, label {
    font-family: 'Inter', sans-serif;
}
h1, h2, h3 {
    font-family: 'Fraunces', serif !important;
    font-weight: 600 !important;
    font-optical-sizing: auto;
    letter-spacing: -0.01em;
}
/* Grote, prominente koppen (hero-headlines) krijgen een zwaarder
   Fraunces-gewicht (700 i.p.v. 600) -- maakt het serif-karakter
   duidelijker zichtbaar en onderscheidend, i.p.v. bijna sans-serif-
   ogend bij een lichter gewicht. Toegepast via een aparte klasse i.p.v.
   alle h1 aan te passen, want kleinere koppen (h2/h3 in expanders etc.)
   ogen beter bij het lichtere gewicht. */
.hero-headline {
    font-family: 'Fraunces', serif !important;
    font-weight: 700 !important;
    font-optical-sizing: auto;
    letter-spacing: -0.015em;
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
/* Specifieke klasse voor de logo-titel in de zijbalk -- Streamlit's
   eigen interne CSS (een 'st-emotion-cache-...'-klasse) voegt standaard
   padding:1.25rem 0 1rem toe aan ELKE h1 binnen een markdown-blok. Onze
   eerdere margin:0-reset raakte dat niet (padding is een andere
   eigenschap), wat een onverwacht grote ruimte tussen 'HESTYS' en de
   tagline veroorzaakte. Een eigen, specifieke klasse (i.p.v. inline
   stijlen, die Streamlit soms deels lijkt te filteren) is betrouwbaarder. */
.sidebar-logo-title {
    font-size: 1.35rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.01em !important;
    font-family: 'Inter', sans-serif !important;
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1.1 !important;
}
.app-header .tagline {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.08em;
    color: #8992A3 !important;
    margin-top: 0.15rem;
}

/* Mobiel: header flink compacter -- op een smal scherm nam dit voorheen
   zoveel verticale ruimte in dat bezoekers eerst moesten scrollen
   voordat ze bij daadwerkelijke content kwamen. */
@media (max-width: 640px) {
    .app-header {
        padding: 0.7rem 0 0.5rem 0;
        margin-bottom: 0.75rem;
    }
    .app-header-top {
        gap: 0.6rem;
        margin-bottom: 0.6rem;
    }
    .app-header-top svg {
        width: 30px !important;
        height: 30px !important;
    }
    .app-header h1 {
        font-size: 1.35rem !important;
    }
    .app-header .tagline {
        font-size: 0.55rem;
    }
}

/* Mooie inline-link binnen lopende tekst (bv. '... zie Discover') --
   alleen het woord zelf is gestyled, niet de hele zin, en geen kaal
   blauw-onderstreept-link-gevoel */
.inline-link {
    color: #1FAE96 !important;
    font-weight: 600;
    text-decoration: none !important;
    border-bottom: 1.5px solid rgba(31, 174, 150, 0.4);
    padding-bottom: 1px;
    transition: border-color 0.15s ease;
}
.inline-link:hover {
    border-bottom-color: #1FAE96;
}

/* Knop-achtige link (voor bv. 'Buy smarter with DCA') -- oogt als een
   Streamlit-knop, is technisch een <a>, zodat 'ie in hetzelfde tabblad
   navigeert (st.link_button opent altijd een nieuw tabblad) */
/* Google-logootje in de 'Continue with Google'-knop op de login-pagina --
   st.button() ondersteunt geen custom afbeeldingen als icoon (alleen
   emoji/Material Icons), dus via de .st-key-<key>-CSS-klasse (Streamlit's
   eigen, officiele manier om 1 specifieke widget te targeten) een
   achtergrond-afbeelding + linker-padding toegevoegd aan precies déze knop. */
.st-key-login_page_google button {
    background-image: url("data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTgiIGhlaWdodD0iMTgiIHZpZXdCb3g9IjAgMCAxOCAxOCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZmlsbD0iIzQyODVGNCIgZD0iTTE3LjY0IDkuMmMwLS42MzctLjA1Ny0xLjI1MS0uMTY0LTEuODRIOXYzLjQ4MWg0Ljg0NGMtLjIwOSAxLjEyNS0uODQzIDIuMDc4LTEuNzk2IDIuNzE3djIuMjU4aDIuOTA4YzEuNzAyLTEuNTY3IDIuNjg0LTMuODc0IDIuNjg0LTYuNjE1eiIvPgo8cGF0aCBmaWxsPSIjMzRBODUzIiBkPSJNOSAxOGMyLjQzIDAgNC40NjctLjgwNiA1Ljk1Ni0yLjE4bC0yLjkwOC0yLjI1OWMtLjgwNi41NC0xLjgzNy44Ni0zLjA0OC44Ni0yLjM0NCAwLTQuMzI4LTEuNTg0LTUuMDM2LTMuNzExSC45NTd2Mi4zMzJDMi40MzggMTUuOTgzIDUuNDgyIDE4IDkgMTh6Ii8+CjxwYXRoIGZpbGw9IiNGQkJDMDUiIGQ9Ik0zLjk2NCAxMC43MWMtLjE4LS41NC0uMjgyLTEuMTE3LS4yODItMS43MXMuMTAyLTEuMTcuMjgyLTEuNzFWNC45NThILjk1N0MuMzQ3IDYuMTczIDAgNy41NDggMCA5cy4zNDggMi44MjcuOTU3IDQuMDQybDMuMDA3LTIuMzMyeiIvPgo8cGF0aCBmaWxsPSIjRUE0MzM1IiBkPSJNOSAzLjU4YzEuMzIxIDAgMi41MDguNDU0IDMuNDQgMS4zNDVsMi41ODItMi41OEMxMy40NjMuODkxIDExLjQyNiAwIDkgMCA1LjQ4MiAwIDIuNDM4IDIuMDE3Ljk1NyA0Ljk1OEwzLjk2NCA3LjI5QzQuNjcyIDUuMTYzIDYuNjU2IDMuNTggOSAzLjU4MHoiLz4KPC9zdmc+");
    background-repeat: no-repeat;
    background-position: 20px center;
    padding-left: 48px !important;
    padding-right: 48px !important;
    background-color: rgba(15,23,42,0.4) !important;
    border: 1px solid rgba(51,65,85,0.6) !important;
    color: #EAEDF1 !important;
    font-weight: 600 !important;
    box-shadow: none !important;
    /* Volle breedte i.p.v. fit-content -- net zo breed als de groene
       Sign In-knop erboven. text-align:center + symmetrische links/
       rechts-padding centreert de tekst zelf keurig in de resterende
       ruimte (het logo blijft links gepind, zoals gebruikelijk bij
       'Sign in with Google'-knoppen). */
    display: block !important;
    text-align: center !important;
    margin: 0 !important;
    width: 100% !important;
}
.st-key-login_page_google button:hover {
    background-color: rgba(30,41,59,0.6) !important;
    border-color: rgba(71,85,105,0.7) !important;
}
.st-key-login_page_google {
    display: block !important;
    width: 100% !important;
}

.button-link, .button-link:visited {
    display: inline-block;
    font-family: 'Inter', sans-serif;
    font-size: 0.9rem;
    font-weight: 600;
    color: #101825 !important;
    background: #1FAE96;
    padding: 0.45rem 1.1rem;
    border-radius: 6px;
    text-decoration: none !important;
    margin-top: 0.4rem;
}
.button-link:hover {
    background: #24C4A8;
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
.positions-table tbody tr:nth-child(even) {
    background: rgba(255,255,255,0.015);
}
.positions-table tbody tr:hover {
    background: rgba(31,174,150,0.06);
}
.positions-table th:first-child,
.positions-table td:first-child {
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.positions-table code {
    color: #1FAE96;
    background: none;
    font-size: 0.85rem;
}
.positions-table .position-logo {
    width: 20px;
    height: 20px;
    border-radius: 5px;
    object-fit: contain;
    background: #fff;
    padding: 2px;
    vertical-align: middle;
    margin-right: 0.5rem;
}
.positions-table .weight-bar-track {
    display: inline-block;
    width: 46px;
    height: 5px;
    border-radius: 3px;
    background: #232D3A;
    vertical-align: middle;
    margin-right: 0.5rem;
    overflow: hidden;
}
.positions-table .weight-bar-fill {
    display: block;
    height: 100%;
    background: #1FAE96;
    border-radius: 3px;
}

/* Iets compactere tabellen: kleinere tekst in de databladen */
[data-testid="stDataFrame"] * {
    font-size: 0.85rem !important;
}

/* --- My Portfolio positierijen: responsief -- mobiel-eerst gestapeld
   (compacte kaart, huidige stijl), vanaf 768px een brede, meerkoloms-
   tabelweergave die de beschikbare breedte daadwerkelijk gebruikt i.p.v.
   een dunne strook met veel lege ruimte ertussen. Beide versies staan in
   de HTML (elke rij rendert 1x), CSS beslist welke zichtbaar is --
   Streamlit kent geen server-side viewport-detectie, dus dit is de
   standaard, betrouwbare aanpak. --- */
.portfolio-row-desktop { display: none; }
.portfolio-row-desktop-alltime { display: none; }
.portfolio-row-mobile { display: block; }
.portfolio-row-header { display: none; }
.portfolio-row-header-alltime { display: none; }

@media (min-width: 768px) {
    .portfolio-row-mobile { display: none; }
    .portfolio-row-desktop, .portfolio-row-header {
        display: grid;
        grid-template-columns: 40px 2.2fr 1fr 1.3fr 1fr 1.2fr;
        align-items: center;
        gap: 0.75rem;
    }
    /* All-time heeft 1 kolom extra t.o.v. Daily -- Cost price en Current
       price staan hier apart i.p.v. samengeperst in 1 'X -> Y'-pijl,
       die eerder verwarrend bleek (kon aangezien worden voor 1 getal). */
    .portfolio-row-desktop-alltime, .portfolio-row-header-alltime {
        display: grid;
        grid-template-columns: 40px 1.7fr 1fr 1fr 1.1fr 0.9fr 1.1fr;
        align-items: center;
        gap: 0.6rem;
    }
    .portfolio-row-desktop, .portfolio-row-desktop-alltime {
        border-bottom: 1px solid rgba(148,163,184,0.08);
        padding: 1.15rem 0.25rem;
    }
    .portfolio-row-header, .portfolio-row-header-alltime {
        padding: 0 0.25rem 0.4rem 0.25rem;
        color: #8992A3;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
}
/* Elk st.container(border=True) op de HELE site krijgt nu dezelfde,
   subtiele slate-tint als de position-rows (rgba(137,146,163,...))
   i.p.v. Streamlit's standaard, neutrale rand -- geeft in 1x
   consistentie voor elke sectie die zo'n kader gebruikt (o.a. Manage),
   niet alleen een losse, eenmalige fix. */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: rgba(137,146,163,0.05) !important;
    border: 1px solid rgba(137,146,163,0.18) !important;
    border-radius: 12px !important;
}
/* Het vak laten krimpen naar de knop -- was veel groter dan nodig voor
   zo'n kleine knop, wat een 'verdwaald-in-lege-ruimte'-gevoel gaf.
   En de knop zelf duidelijk anders vormgegeven (niet alleen een
   kleuraanpassing): volle breedte, meer body, subtiele schaduw + een
   licht hover-effect voor wat diepte/interactiviteit. */
div[data-testid="stFileUploader"] section {
    padding: 0.6rem !important;
    min-height: 0 !important;
}
div[data-testid="stFileUploader"] section button {
    background: transparent !important;
    color: #1FAE96 !important;
    border: 1px solid rgba(31,174,150,0.35) !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 0.4rem 1rem !important;
    border-radius: 6px !important;
    width: 100% !important;
    box-shadow: none !important;
    transition: background 0.15s ease !important;
}
div[data-testid="stFileUploader"] section button:hover {
    background: rgba(31,174,150,0.12) !important;
    box-shadow: none !important;
}
</style>
<style>
/* Watchlist prullenbak-knop compacter, via Streamlit's eigen
   .st-key-{key}-klasse (gebaseerd op een key die wijzelf definieren).
   De bel-knop (st.popover) wordt inline, direct bij de rij zelf
   gestyled -- ook via st.container(key=...), zie de watchlist-render-
   code verderop.
   flex+center toegevoegd: zonder expliciete uitlijning bleef de
   icoon-inhoud (icoon + bij de bel-knop ook de eigen chevron van
   st.popover) linksgedrukt/buiten het vak hangen bij zo'n krappe
   padding. */
[class*="st-key-watchlist_delete_"] button {
    padding: 0.2rem 0.5rem !important;
    min-width: 0 !important;
    min-height: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
</style>
""", unsafe_allow_html=True)

# Het '200MB per file * CSV'-tekstje bij de file-uploader verbergen.
# BELANGRIJKE ONTDEKKING: browsers voeren <script>-tags die via
# innerHTML-achtige DOM-invoeging worden toegevoegd NOOIT uit (een
# algemene, browserbrede beveiliging -- niet iets Streamlit-specifieks)
# -- daarom deed een <script>-tag BINNEN de st.markdown()-aanroep
# hierboven helemaal niets, ondanks een verder correcte, tekst-
# gebaseerde aanpak (geen giswerk naar tag-/testid-namen). st.components.
# v1.html() rendert wel in een echte <iframe>, waarin scripts WEL
# gewoon worden uitgevoerd -- vandaar hier apart, met window.parent.document
# om vanuit die iframe alsnog de ECHTE, omliggende Streamlit-pagina te
# bereiken en aan te passen. height=0 houdt de iframe zelf onzichtbaar.
components.html(
    """
    <script>
    function hideFileSizeHint() {
        window.parent.document.querySelectorAll('[data-testid="stFileUploader"] *').forEach(function(el) {
            if (el.children.length === 0 && el.textContent.indexOf('per file') !== -1) {
                el.style.display = 'none';
            }
        });
    }
    hideFileSizeHint();
    new MutationObserver(hideFileSizeHint).observe(window.parent.document.body, {childList: true, subtree: true});
    </script>
    """,
    height=0,
)


def get_file_last_commit_date(path: str) -> str:
    """
    Geeft alleen de DATUM (YYYY-MM-DD) van de laatste git-commit van dit
    bestand terug -- gebruikt om te vergelijken of een gebruiker een
    bepaalde scan-batch al heeft gezien. Geeft None terug als het niet
    lukt (bestand bestaat niet, of git niet beschikbaar).
    """
    if not os.path.exists(path):
        return None
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cd", "--date=format:%Y-%m-%d", "--", path],
            capture_output=True, text=True, timeout=5,
        )
        commit_date = result.stdout.strip()
        return commit_date or None
    except Exception:
        return None


def _signal_status_line_html(caption_intro: str, csv_path: str, extra: str = "") -> str:
    """
    Vervangt de informele '-- showing the top 3 of 6 matches, updated...'-
    zin door een ijskoude, minimalistische systeemstatus-regel. Geen
    liggende streepjes, geen pratende toon -- puur platte metadata,
    all-caps, gescheiden door een pipe.
    """
    status_text = caption_intro.upper()
    updated_text = f"SIGNAL UPDATED {file_last_modified(csv_path).upper()}"
    parts = f"STATUS: {status_text} | {updated_text}"
    if extra:
        parts += f" | {extra.upper()}"
    return (
        f'<div style="color:#64748B; font-size:10px; font-weight:700; letter-spacing:0.05em; '
        f'text-transform:uppercase; margin:0.3rem 0 0.75rem;">{parts}</div>'
    )


def file_last_modified(path: str) -> str:
    """
    Geeft het tijdstip terug waarop dit bestand voor het laatst is
    BIJGEWERKT DOOR DE SCAN ZELF (git-commit-tijd, in UTC) -- niet het
    Streamlit-servers-eigen bestandssysteem-tijdstip (os.path.getmtime),
    want dat weerspiegelt alleen wanneer Streamlit Cloud het bestand voor
    het laatst binnenkreeg bij een eigen (re)deploy, wat kan afwijken van
    wanneer de scan daadwerkelijk draaide -- verwarrend bij het checken of
    de dagelijkse/wekelijkse mail wel op tijd is gegaan.
    """
    if not os.path.exists(path):
        return "never"
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cd", "--date=format:%Y-%m-%d %H:%M UTC", "--", path],
            capture_output=True, text=True, timeout=5,
        )
        commit_time = result.stdout.strip()
        if commit_time:
            return commit_time
    except Exception:
        pass
    # Terugval als git niet beschikbaar/succesvol is in deze omgeving
    ts = os.path.getmtime(path)
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") + " (server time, not scan time)"


def load_screener_data(csv_file: str = "supertrend_signals.csv"):
    if not os.path.exists(csv_file):
        return None
    df = pd.read_csv(csv_file)
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


@st.cache_data(ttl=300, show_spinner=False)
def get_fx_rate(from_currency: str, to_currency: str):
    """
    Haalt de actuele wisselkoers op (5 min gecached). Geeft None terug
    als het niet lukt (i.p.v. een gok te doen).

    Gebruikt een venster van 5 dagen i.p.v. alleen 'vandaag' (period=
    '1d') -- op een weekend/feestdag kan er geen forex-candle voor
    EXACT vandaag bestaan, waardoor period='1d' een lege DataFrame
    teruggaf en de conversie stilzwijgend faalde. Concreet gevolg
    zonder deze fix: 'Update portfolio value' leek voor VALUTA-
    CONVERTERENDE posities (bv. EUR-aandelen bij een USD-weergave)
    niks te doen in het weekend, terwijl USD-genoteerde crypto (geen
    conversie nodig, from_currency==to_currency) wel gewoon bijwerkte
    -- exact het gemelde patroon.
    """
    if from_currency == to_currency:
        return 1.0
    pair_ticker = f"{from_currency}{to_currency}=X"
    try:
        data = yf.Ticker(pair_ticker).history(period="5d")
        valid_closes = data["Close"].dropna()
        if not valid_closes.empty:
            return float(valid_closes.iloc[-1])
    except Exception:
        pass
    return None


def build_breakdown_pie_chart(labels: list, values: list):
    """
    Generieke, COMPACTE donut-chart voor een verdeling (sector/asset-type/
    regio). De legenda staat nu horizontaal ONDER de taart (i.p.v. rechts
    ernaast) -- dat voorkomt de grote, lege ruimte die ontstaat als een
    smalle taart wordt uitgerekt over een brede kolom met de legenda ver
    weggeduwd naar rechts.
    """
    palette = ["#1FAE96", "#E8A93C", "#4DA6FF", "#E5484D", "#C77DFF",
               "#3ED9C4", "#F5C518", "#FF8A5C", "#8992A3", "#5AC8B0", "#B0E0D8"]
    colors = (palette * (len(labels) // len(palette) + 1))[:len(labels)]

    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values, hole=0.6,
        marker=dict(colors=colors, line=dict(color="#101825", width=2)),
        texttemplate="%{percent:.0%}",
        textposition="inside",
        textfont=dict(family="Inter, sans-serif", size=11, color="#EAEDF1"),
        hovertemplate="%{label}: %{percent:.1%}<extra></extra>",
    )])
    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="top", y=-0.08, xanchor="center", x=0.5,
            font=dict(family="Inter, sans-serif", size=10, color="#8992A3"), bgcolor="rgba(0,0,0,0)",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=10, b=10, l=10, r=10),
        height=280,
        width=280,
        font=dict(family="Inter, sans-serif", color="#EAEDF1"),
    )
    return fig


def build_portfolio_pie_chart(holdings: list):
    """Bouwt een compacte donut-chart van de portfolio-verdeling, met de legenda naast (niet onder) de taart."""
    palette = ["#1FAE96", "#17876F", "#3ED9C4", "#0F5C4E", "#5AC8B0",
               "#0B4A3E", "#2FBFA3", "#0D6653", "#4DD0BA", "#124F42"]
    colors = (palette * (len(holdings) // len(palette) + 1))[:len(holdings)]

    labels = [h["naam"] for h in holdings]
    values = [h.get("position_value") or 0 for h in holdings]

    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values, hole=0.55,
        marker=dict(colors=colors, line=dict(color="#101825", width=2)),
        texttemplate="%{percent:.0%}",  # afgerond, geen decimalen
        textposition="inside",
        textfont=dict(family="Inter, sans-serif", size=14, color="#EAEDF1"),
        hovertemplate="%{label}: %{value:,.0f} (%{percent:.0%})<extra></extra>",
    )])
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02,
                    font=dict(family="Inter, sans-serif", size=10, color="#8992A3"), bgcolor="rgba(0,0,0,0)"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=10, b=10, l=10, r=100),  # ruimte rechts voor de legenda, naast de taart
        height=320,
        font=dict(family="Inter, sans-serif", color="#EAEDF1"),
    )
    return fig


TICKER_EXCHANGE_CURRENCY = {
    "AS": "EUR", "PA": "EUR", "DE": "EUR", "MI": "EUR", "MC": "EUR",
    "BR": "EUR", "LS": "EUR", "HE": "EUR", "VI": "EUR", "IR": "EUR",
    "L": "GBP",
    "TO": "CAD", "V": "CAD",
    "SW": "CHF",
    "ST": "SEK", "CO": "DKK", "OL": "NOK",
    "HK": "HKD",
    "T": "JPY",
    "AX": "AUD",
}


@st.cache_data(ttl=86400, show_spinner=False)
def get_cached_ticker_currency(ticker: str) -> str:
    """
    Cachet de valuta van een ticker voor 24 uur (i.p.v. de standaard 5
    minuten) -- de valuta van een ticker verandert vrijwel nooit, dus een
    lange cache-tijd voorkomt dat elke portfolio-refresh opnieuw de trage
    .info-aanroep per positie moet doen.

    GEVONDEN, BELANGRIJKE CORRECTIE: yfinance's .info['currency'] wordt nu
    als PRIMAIRE bron gebruikt WANNEER die daadwerkelijk een waarde geeft
    (niet een .get(..., default)-aanname) -- het ticker-achtervoegsel (bv.
    '.AS' -> EUR) is de BETROUWBARE TERUGVAL voor als .info ontbreekt.
    Eerder stond dit omgekeerd (achtervoegsel eerst), wat een ANDERE bug
    gaf: SMH.L (VanEck Semiconductor UCITS ETF) staat genoteerd op Londen
    (.L) maar handelt daadwerkelijk in USD -- het achtervoegsel alleen
    zegt niets over de specifieke valuta van een individuele notering,
    zoals ook al eerder bleek bij USA.TO (Toronto-notering, maar USD-
    verhandeld). yfinance's .info geeft voor DIT soort uitzonderingen wel
    de juiste, specifieke waarde. De oorspronkelijke reden om het
    achtervoegsel eerst te proberen (ADYEN.AS, waar .info['currency']
    ONTBRAK en de .get(...,'USD')-default dus een VERKEERDE aanname was)
    blijft correct afgehandeld: als .info geen waarde heeft, valt dit nu
    alsnog terug op het achtervoegsel, niet op een blinde 'USD'-aanname.
    """
    try:
        info_currency = yf.Ticker(ticker).info.get("currency")
    except Exception:
        info_currency = None
    if info_currency:
        return info_currency
    if "." in ticker:
        suffix = ticker.rsplit(".", 1)[-1].upper()
        if suffix in TICKER_EXCHANGE_CURRENCY:
            return TICKER_EXCHANGE_CURRENCY[suffix]
    if "-" in ticker:
        crypto_suffix = ticker.rsplit("-", 1)[-1].upper()
        if crypto_suffix in ("EUR", "GBP"):
            return crypto_suffix
        if crypto_suffix in ("USD", "USDT", "USDC"):
            return "USD"
    return "USD"


def _native_currency_for_holding(h: dict) -> str:
    """
    Zelfde doel als get_cached_ticker_currency(), maar HOLDING-bewust:
    een Custom Yield Asset (fractioneel vastgoed e.d., h['custom_
    annual_cashflow'] is dan niet None) heeft geen echte markt-notering
    om een 'native handelsvaluta' voor op te zoeken -- get_cached_
    ticker_currency() viel voor zo'n fake ticker (bv. 'PROP.COM') altijd
    terug op de laatste 'return USD'-default, ongeacht in welke valuta
    de gebruiker 'm daadwerkelijk invoerde. Dat veroorzaakte een echte
    bug: overal waar native_currency != value_currency werd aangenomen
    (Daily/All-time-weergave, 'Update portfolio value'), werd een
    volledig overbodige EUR<->USD-FX-conversie op de waarde losgelaten.
    Voor een custom asset IS de opgeslagen value_currency de enige juiste
    valuta -- geen aparte 'markt'-valuta om ooit tegen te converteren.
    """
    if h.get("custom_annual_cashflow") is not None:
        return h.get("value_currency") or "EUR"
    return get_cached_ticker_currency(h["ticker"])


def _eur_position_value(h: dict) -> float:
    """
    Zet position_value om naar EUR, ongeacht in welke valuta 'ie toevallig
    het laatst is opgeslagen. 'value_currency' volgt de DISPLAY-valuta die
    actief was op de My Portfolio-pagina tijdens de laatste 'Update
    portfolio value'-klik (kan dus EUR of USD zijn, en wisselt per
    refresh) -- NIET een vaste, gegarandeerde valuta.

    GEVONDEN BUG (oorspronkelijk in de Wealth Engine): zonder deze
    conversie behandelde elke plek die absolute euro-bedragen toont een in
    USD opgeslagen totaal alsof het al EUR was. Omdat 1 USD < 1 EUR is,
    gaf datzelfde portfolio na een USD-refresh een HOGER (fout) EUR-bedrag
    te zien dan na een EUR-refresh. Op module-niveau gezet (i.p.v. een
    lokale closure binnen 1 functie) zodat elke plek die absolute
    portfolio-euro's berekent (Wealth Engine, Stress-Test's Crisis
    Simulator) 'm hergebruikt i.p.v. los, mogelijk inconsistent, hetzelfde
    wiel opnieuw uit te vinden.
    """
    raw_value = h.get("position_value") or 0
    if raw_value <= 0:
        return 0.0
    holding_currency = h.get("value_currency") or "EUR"
    if holding_currency == "EUR":
        return raw_value
    fx_rate = get_fx_rate(holding_currency, "EUR")
    if fx_rate is None:
        return raw_value  # zeldzame FX-storing -- liever een schatting tonen dan crashen
    return raw_value * fx_rate


def refresh_portfolio_values(holdings: list, user_email: str, display_currency: str = "EUR") -> tuple:
    """
    Haalt voor al je posities in 1x (via een gebatchte download) de
    actuele koers op, gebruikt een 24-uur-gecachte valuta-lookup per
    ticker (i.p.v. een trage .info-aanroep per positie bij elke refresh),
    rekent om naar de gekozen weergave-valuta, en werkt position_value
    bij. Rate-limited tot 1x per 10 seconden per gebruiker (ruim
    voldoende tegen per-ongeluk-dubbelklikken, zonder te frustreren).

    Geeft (success: bool, message: str) terug.
    """
    last_refresh = database.get_last_price_refresh(user_email)
    if last_refresh:
        last_refresh_dt = datetime.fromisoformat(last_refresh.replace("Z", "+00:00"))
        seconds_since = (datetime.now(timezone.utc) - last_refresh_dt).total_seconds()
        if seconds_since < 10:
            wait_seconds = int(10 - seconds_since)
            return False, f"Please wait {wait_seconds} more second(s) before updating again."

    tickers_to_fetch = list({h["ticker"] for h in holdings if h.get("shares")})
    if not tickers_to_fetch:
        return False, "No positions with shares to update."

    # De onderliggende koers-cache (_batch_download_history) staat 1 uur
    # vast -- prima voor gewone paginabezoeken, maar een EXPLICIETE klik op
    # 'Update portfolio value' moet gegarandeerd verse data ophalen, niet
    # mogelijk een tot 1 uur oude cache-hit teruggeven (voelde anders aan
    # alsof de knop niks deed). get_fx_rate() staat los en heeft zijn eigen,
    # kortere 5-min-cache, dus die hoeft hier niet geleegd te worden.
    #
    # GEVONDEN BUG: get_cached_ticker_info() (de PRIMAIRE prijsbron
    # hieronder, regularMarketPrice) heeft OOK een eigen 5-min-cache, die
    # hier VOORHEEN NIET gewist werd -- bij meerdere klikken binnen
    # dezelfde 5 minuten gaf de knop dus gegarandeerd dezelfde, oude
    # koers terug (het leek dan alsof de knop niet werkte). Nu ook deze
    # cache expliciet gewist.
    _batch_download_history.clear()
    get_cached_ticker_info.clear()

    shared_prices = get_shared_history_for_holdings(
        [{"ticker": t} for t in tickers_to_fetch], period="5d"
    )
    today = datetime.now().date()

    fx_cache = {}
    updated_count = 0
    skipped_currencies = set()
    fresh_market_data_rows = []

    for holding in holdings:
        if not holding.get("shares"):
            continue
        if holding.get("custom_annual_cashflow") is not None:
            # Custom yield asset -- geen echte ticker om bij Yahoo Finance
            # op te zoeken (het huidige gedrag ZONDER deze check is ook al
            # veilig, dankzij get_cached_ticker_info()'s eigen try/except
            # die {} teruggeeft, waarna native_price None blijft en de
            # holding hieronder alsnog wordt overgeslagen -- maar deze
            # expliciete check bespaart een nutteloze API-poging en maakt
            # de bedoeling duidelijk i.p.v. op toevallig gedrag te leunen).
            continue
        try:
            # 'regularMarketPrice' (of 'currentPrice' als terugval-veldnaam)
            # uit yfinance's .info wordt EERST geprobeerd -- dit veld
            # weerspiegelt specifiek de MEEST RECENTE koers (vergelijkbaar
            # met hoe Yahoo Finance's eigen site het toont), en bleek in de
            # praktijk BETROUWBAARDER/VERSER dan .history() alleen (die in
            # sommige gevallen ook nog een dag kan achterlopen, zelfs via
            # de al-gecorrigeerde Ticker().history()-methode). We vallen
            # terug op de geschiedenis-gebaseerde aanpak (_price_near_date)
            # als .info leeg is (een bekende, terugkerende yfinance-
            # onbetrouwbaarheid) of het veld ontbreekt.
            info = get_cached_ticker_info(holding["ticker"])
            native_price = info.get("regularMarketPrice") or info.get("currentPrice")
            hist = shared_prices.get(holding["ticker"])
            if native_price is None:
                native_price = _price_near_date(hist, today, tolerance_days=10) if hist is not None else None
            if native_price is None:
                continue
            native_currency = _native_currency_for_holding(holding)

            if native_currency not in fx_cache:
                fx_cache[native_currency] = get_fx_rate(native_currency, display_currency)
            fx_rate = fx_cache[native_currency]

            if fx_rate is None:
                skipped_currencies.add(native_currency)
                continue

            new_value = holding["shares"] * native_price * fx_rate
            day_change_pct = compute_day_change_pct(hist)
            database.update_holding_value(
                holding["id"], user_email, new_value, value_currency=display_currency, day_change_pct=day_change_pct
            )
            updated_count += 1

            # GEVONDEN BUG: My Portfolio's rij-weergave leest de 'Price'-
            # kolom uit de GEDEELDE ticker_market_data-tabel (de
            # achtergrond-sync, elke 15 min ververst) -- NIET uit deze
            # zojuist bijgewerkte position_value. Zonder dit zou de Price-
            # kolom dus de OUDE, achtergrond-gesynchroniseerde waarde
            # blijven tonen tot de volgende scheduled sync draait, ook al
            # werkte de knop 'achter de schermen' wel (position_value/
            # Total portfolio value klopten al meteen). native_price is
            # in de NATIEVE valuta (voor FX-conversie), consistent met hoe
            # sync_market_data.py dit ook opslaat -- geen conversie nodig.
            fresh_market_data_rows.append({
                "ticker": holding["ticker"], "current_price": native_price, "day_change_pct": day_change_pct,
            })
        except Exception:
            continue

    if fresh_market_data_rows:
        database.upsert_ticker_market_data(fresh_market_data_rows)

    database.set_last_price_refresh(user_email, datetime.now(timezone.utc).isoformat())

    message = f"Updated {updated_count} of {len(holdings)} position(s) in {display_currency}."
    if skipped_currencies:
        message += f" Could not get exchange rate for: {', '.join(skipped_currencies)}."
    return True, message


@st.cache_data(ttl=300, show_spinner=False)
@st.cache_data(ttl=300, show_spinner=False)
def get_cached_ticker_info(ticker: str) -> dict:
    """
    Cachet yfinance's .info per ticker voor 5 minuten -- voorkomt dat
    dezelfde koersinfo steeds opnieuw wordt opgehaald bij elke
    pagina-interactie (Streamlit herstart het hele script bij elke klik).

    BUGFIX 1: het @st.cache_data-decorator ontbrak hier -- ondanks dat de
    docstring en functienaam al die hele tijd BEWEERDEN dat dit gecached
    werd (in tegenstelling tot get_cached_ticker_history/_earnings_dates/
    _ticker_dividends hieronder, die het decorator wel correct hadden).

    BUGFIX 3: BUGFIX 2's retry checkte alleen 'is de dict niet-leeg?' --
    maar Yahoo Finance geeft bij een mislukte aanroep niet altijd een
    lege dict terug. Soms komt er een SCHIJN-geldige dict met slechts 1
    a 2 sleutels terug (bv. {'trailingPegRatio': None}) -- niet-leeg,
    dus 'succesvol' volgens de oude check, maar feitelijk waardeloos: een
    echte .info-respons voor een bestaande ticker heeft altijd tientallen
    tot 100+ velden. Nu wordt zo'n te-kleine dict ook als mislukking
    behandeld en opnieuw geprobeerd, i.p.v. meteen als 'geen dividend'
    (0%) te worden geinterpreteerd.
    """
    last_result = {}
    for _attempt in range(3):
        try:
            info = yf.Ticker(ticker).info
        except Exception:
            info = {}
        if info and len(info) > 5:
            return info
        last_result = info
        if _attempt < 2:
            time.sleep(0.6)
    return last_result


@st.cache_data(ttl=300, show_spinner=False)
def get_cached_ticker_history(ticker: str, period: str = None, start: str = None, end: str = None):
    """Cachet yfinance's .history() per ticker+periode voor 5 minuten."""
    try:
        if start is not None:
            return yf.Ticker(ticker).history(start=start, end=end)
        return yf.Ticker(ticker).history(period=period)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_earnings_dates(ticker: str, limit: int = 8):
    """
    Cachet yfinance's .get_earnings_dates() per ticker voor 1 uur (langer
    dan de meeste andere caches, want earnings-datums veranderen zelden
    binnen dezelfde dag). Was voorheen NIET gecached en werd bovendien
    DUBBEL aangeroepen (1x in get_todays_portfolio_earnings, 1x in
    get_upcoming_portfolio_earnings) -- bij meerdere posities/watchlist-
    items telde dat flink op en maakte Today's radar merkbaar traag.
    """
    try:
        return yf.Ticker(ticker).get_earnings_dates(limit=limit)
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def get_cached_ticker_dividends(ticker: str):
    """Cachet yfinance's .dividends (historische, per-share dividendbetalingen) per ticker voor 5 minuten."""
    try:
        return yf.Ticker(ticker).dividends
    except Exception:
        return pd.Series(dtype=float)


def _get_live_vix_value() -> float | None:
    """
    Haalt de actuele stand van de VIX-index (^VIX) op, voor de 'Market
    Volatility & Sector Momentum'-balk op Today (vervangt de oude Global
    Sector Heatmap daar). Hergebruikt de bestaande, 5 minuten gecachete
    get_cached_ticker_history() -- geen aparte, ongecachete live-aanroep.
    """
    try:
        vix_history = get_cached_ticker_history("^VIX", period="5d")
        if vix_history is None or vix_history.empty:
            return None
        return float(vix_history["Close"].iloc[-1])
    except Exception:
        return None


def get_annual_dividend_rate(ticker: str, info: dict):
    """
    Geeft het geschatte jaarlijkse dividend per aandeel terug, met 2
    terugvallen -- nodig omdat 'dividendRate' in yfinance's .info voor
    sommige effecten (vooral ETF's, zoals TDIV) niet betrouwbaar gevuld
    is, ook al keren ze wel degelijk dividend uit:
    1. info['dividendRate'] -- werkt betrouwbaar voor de meeste aandelen
    2. info['trailingAnnualDividendRate'] -- vaak wel gevuld voor ETF's
       als 'dividendRate' leeg is
    3. Som van de daadwerkelijke dividendbetalingen van de laatste 12
       maanden (uit de koersgeschiedenis) -- de meest betrouwbare,
       universele terugval, want gebaseerd op wat er al daadwerkelijk is
       uitgekeerd i.p.v. een (soms ontbrekende) vooruitkijkende schatting.
    """
    rate = info.get("dividendRate")
    if rate:
        return rate
    rate = info.get("trailingAnnualDividendRate")
    if rate:
        return rate
    try:
        dividends = get_cached_ticker_dividends(ticker)
        if dividends is not None and not dividends.empty:
            cutoff = pd.Timestamp.now(tz=dividends.index.tz) - pd.Timedelta(days=365)
            recent = dividends[dividends.index >= cutoff]
            if not recent.empty:
                return float(recent.sum())
    except Exception:
        pass
    return None


def get_tickers_info(holdings: list) -> dict:
    """Haalt 1x per ticker de yfinance-info op (via de 5-min-cache), voor hergebruik door meerdere analyses."""
    infos = {}
    for h in holdings:
        infos[h["ticker"]] = get_cached_ticker_info(h["ticker"])
    return infos


def get_concentration_alert(holdings: list, max_position_pct: float = 25.0):
    """
    Korte, 1-regelige concentratie-waarschuwing voor Today's radar -- geeft
    None terug als alles binnen je eigen doel-grens zit (geen ruis op
    normale dagen). Hergebruikt dezelfde logica als Analyze's Concentration
    Risk-kaart, maar dan alleen de 'is er iets mis'-check, niet de volledige
    uitleg/rebalancing-tip.

    Geeft (tekst) terug ZONDER het eigen emoji ervoor -- de aanroeper
    plakt daar zelf een icoon voor, consistent met de andere Today's
    radar-items.
    """
    total_value = sum(h.get("position_value") or 0 for h in holdings)
    if total_value <= 0:
        return None
    largest = max(holdings, key=lambda h: h.get("position_value") or 0)
    largest_pct = (largest.get("position_value") or 0) / total_value * 100
    if largest_pct > max_position_pct:
        return f"<b>{largest['naam']}</b> is now {largest_pct:.0f}% of your portfolio, above your {max_position_pct:.0f}% target."
    return None


def analyze_concentration(holdings: list, max_position_pct: float = 25.0) -> list:
    """Concentratie Risk-kaart: grootste positie vs. jouw eigen doel-max, + rebalancing-tip."""
    findings = []
    total_value = sum(h.get("position_value") or 0 for h in holdings)
    if total_value <= 0:
        return ["No position values available yet -- click 'Update portfolio value' first."]

    sorted_holdings = sorted(holdings, key=lambda h: h.get("position_value") or 0, reverse=True)
    largest = sorted_holdings[0]
    largest_value = largest.get("position_value") or 0
    largest_pct = largest_value / total_value * 100

    if largest_pct >= max_position_pct * 1.5:
        findings.append(f"🔴 High concentration: {largest['naam']} is {largest_pct:.0f}% of your tracked portfolio (your target max: {max_position_pct:.0f}%).")
    elif largest_pct > max_position_pct:
        findings.append(f"🟡 Above your target: {largest['naam']} is {largest_pct:.0f}% of your tracked portfolio (your target max: {max_position_pct:.0f}%).")
    else:
        findings.append(f"🟢 Within your target: largest position is {largest['naam']} at {largest_pct:.0f}% (your target max: {max_position_pct:.0f}%).")

    if len(holdings) > 3:
        top3_pct = sum((h.get("position_value") or 0) for h in sorted_holdings[:3]) / total_value * 100
        findings.append(f"Your top 3 positions represent {top3_pct:.0f}% of your tracked portfolio.")

    if largest_pct > max_position_pct:
        target_value = total_value * (max_position_pct / 100)
        trim_amount = largest_value - target_value
        findings.append(
            f"↔️ Rebalancing idea: trimming {largest['naam']} by roughly {trim_amount:,.0f} "
            f"would bring it down to your target of {max_position_pct:.0f}%."
        )

    return findings


def analyze_sectors(holdings: list, infos: dict, max_sector_pct: float = 40.0) -> list:
    """Sectoren-kaart: grootste sector vs. jouw eigen doel-max, + volledige uitsplitsing."""
    findings = []
    total_value = sum(h.get("position_value") or 0 for h in holdings)
    if total_value <= 0:
        return ["No position values available yet -- click 'Update portfolio value' first."]

    sector_values = {}
    for h in holdings:
        value = h.get("position_value") or 0
        sector = infos.get(h["ticker"], {}).get("sector")
        # Posities zonder een GICS-sector (crypto, edelmetalen-achtige
        # producten, e.d.) telden voorheen NIET mee in de uitsplitsing,
        # terwijl hun waarde wel in total_value (de noemer) zat -- dat
        # verklaarde waarom de percentages niet optelden tot 100%. Nu
        # krijgen ze een expliciete, herkenbare bucket i.p.v. te verdwijnen.
        bucket = sector if sector else "Non-equity / Other"
        sector_values[bucket] = sector_values.get(bucket, 0) + value

    if not sector_values:
        return ["No sector data available for your tracked positions."]

    # De 'concentratie-risico'-melding gaat specifiek over ECHTE sectoren --
    # 'Non-equity / Other' (crypto e.d.) meetellen als 'sector-concentratie'
    # zou een verwarrende melding geven, dus die sluiten we hier expliciet uit.
    real_sector_values = {s: v for s, v in sector_values.items() if s != "Non-equity / Other"}
    if real_sector_values:
        dominant_sector, dominant_value = max(real_sector_values.items(), key=lambda x: x[1])
        dominant_pct = dominant_value / total_value * 100

        if dominant_pct >= max_sector_pct * 1.5:
            level = "🔴 High concentration"
        elif dominant_pct > max_sector_pct:
            level = "🟡 Above your target"
        else:
            level = "🟢 Within your target"
        findings.append(f"{level}: {dominant_sector} makes up {dominant_pct:.0f}% of your tracked portfolio (your target max: {max_sector_pct:.0f}%).")
    else:
        findings.append("No positions with a known equity sector yet -- all tracked positions are non-equity (crypto, etc.).")

    breakdown = ", ".join(
        f"{s}: {v / total_value * 100:.0f}%" for s, v in sorted(sector_values.items(), key=lambda x: -x[1])
    )
    findings.append(f"Full breakdown -- {breakdown}.")

    return findings


def get_holding_region(ticker: str, info: dict) -> str:
    """
    Bepaalt de regio van een positie -- eerst via yfinance's 'country'-veld
    (het meest betrouwbaar), gegroepeerd in bredere regio's. Voor posities
    zonder land-info (zoals crypto) wordt teruggevallen op hetzelfde
    ticker-patroon-herkenning als bij Diversification.
    """
    country = (info or {}).get("country")
    if country:
        us_countries = {"United States"}
        eu_countries = {
            "Germany", "France", "Netherlands", "Belgium", "Spain", "Italy",
            "Ireland", "Luxembourg", "Austria", "Portugal", "Finland",
            "Sweden", "Denmark", "Norway", "Switzerland", "Poland",
        }
        if country in us_countries:
            return "United States"
        elif country in eu_countries:
            return "Europe"
        elif country == "United Kingdom":
            return "United Kingdom"
        else:
            return country  # bv. China, Japan, Canada -- toon het land zelf

    ticker_suffix = ticker.rsplit("-", 1)[-1].upper() if "-" in ticker else ""
    if ticker_suffix in ("EUR", "USD", "GBP", "USDT", "USDC"):
        return "Cryptocurrency"

    return "Unknown"


def analyze_diversification(holdings: list, infos: dict) -> list:
    """Diversificatie-kaart: aantal posities + asset-type-mix."""
    findings = []
    total_value = sum(h.get("position_value") or 0 for h in holdings)
    if total_value <= 0:
        return ["No position values available yet -- click 'Update portfolio value' first."]

    if len(holdings) <= 3:
        findings.append(f"🟡 Only {len(holdings)} position(s) tracked -- limited diversification.")
    elif len(holdings) <= 7:
        findings.append(f"🟢 {len(holdings)} positions tracked -- reasonable spread.")
    else:
        findings.append(f"🟢 {len(holdings)} positions tracked -- well spread out.")

    type_values = {}
    for h in holdings:
        value = h.get("position_value") or 0
        raw_quote_type = infos.get(h["ticker"], {}).get("quoteType")
        if raw_quote_type:
            asset_type = raw_quote_type
        else:
            # Yfinance geeft soms geen (of een lege) quoteType terug --
            # vooral crypto-tickers (bv. 'BTC-EUR', 'SOL-EUR') volgen een
            # herkenbaar {SYMBOL}-{VALUTA}-patroon. Die herkennen we hier
            # expliciet, i.p.v. ze allemaal onder de vage, nietszeggende
            # stempel 'Unknown' te laten vallen.
            ticker_suffix = h["ticker"].rsplit("-", 1)[-1].upper() if "-" in h["ticker"] else ""
            if ticker_suffix in ("EUR", "USD", "GBP", "USDT", "USDC"):
                asset_type = "CRYPTOCURRENCY"
            else:
                asset_type = "UNKNOWN"
        type_values[asset_type] = type_values.get(asset_type, 0) + value

    if type_values:
        breakdown = ", ".join(
            f"{t.title()}: {v / total_value * 100:.0f}%" for t, v in sorted(type_values.items(), key=lambda x: -x[1])
        )
        findings.append(f"Asset type breakdown -- {breakdown}.")
        if len(type_values) == 1:
            findings.append("🟡 All tracked positions are the same asset type -- no cross-asset-class diversification.")

    return findings


def analyze_risk(holdings: list, infos: dict) -> list:
    """Risico-kaart: gewogen koers-winst-verhouding + welke positie dat cijfer het meest beinvloedt."""
    findings = []
    total_value = sum(h.get("position_value") or 0 for h in holdings)
    if total_value <= 0:
        return ["No position values available yet -- click 'Update portfolio value' first."]

    pe_entries = [
        {"naam": h["naam"], "ticker": h["ticker"], "pe": infos.get(h["ticker"], {}).get("trailingPE"),
         "weight": h.get("position_value") or 0}
        for h in holdings
    ]
    pe_entries = [e for e in pe_entries if e["pe"] and e["weight"]]
    if pe_entries:
        weighted_pe = sum(e["pe"] * e["weight"] for e in pe_entries) / sum(e["weight"] for e in pe_entries)
        if weighted_pe >= 25:
            findings.append(f"{_icon_span('bar_chart', size_px=14, color='#8992A3')} Weighted average P/E: {weighted_pe:.1f}x -- relatively expensive vs. the long-term market average (roughly 15-20x).")
        elif weighted_pe <= 12:
            findings.append(f"{_icon_span('bar_chart', size_px=14, color='#8992A3')} Weighted average P/E: {weighted_pe:.1f}x -- relatively cheap vs. the long-term market average (roughly 15-20x).")
        else:
            findings.append(f"{_icon_span('bar_chart', size_px=14, color='#8992A3')} Weighted average P/E: {weighted_pe:.1f}x -- roughly in line with the long-term market average.")

        # Context: WELKE positie beinvloedt dit getal het meest? Een gewogen
        # gemiddelde zonder deze context kan misleidend zijn -- een enkele,
        # grote positie kan het cijfer volledig bepalen.
        dominant_entry = max(pe_entries, key=lambda e: e["weight"])
        dominant_weight_pct = dominant_entry["weight"] / total_value * 100
        if dominant_weight_pct >= 30:
            findings.append(
                f"{_icon_span('warning', size_px=14, color='#8992A3')} This is mostly driven by **{dominant_entry['naam']} ({dominant_entry['ticker']})** "
                f"-- {dominant_weight_pct:.0f}% of your portfolio, P/E {dominant_entry['pe']:.1f}x."
            )
    else:
        findings.append("No valuation (P/E) data available for your tracked positions.")

    return findings


def analyze_dividend(holdings: list, infos: dict, display_currency: str = "EUR") -> dict:
    """
    Dividend-kaart: geschat jaarlijks dividend + aankomende ex-dividend-data,
    plus een per-positie-uitsplitsing (bedrag in de weergave-valuta en
    dividendrendement %). Rekent elke positie's dividend (dat yfinance in de
    EIGEN valuta van die beurs teruggeeft, bv. USD voor een Amerikaans
    aandeel) om naar 1 consistente weergave-valuta, i.p.v. bedragen in
    verschillende valuta zomaar bij elkaar op te tellen.
    """
    findings = []
    total_annual_dividend = 0.0
    conversion_failed = False
    upcoming = []
    per_position = []
    for h in holdings:
        info = infos.get(h["ticker"], {})
        shares = h.get("shares") or 0
        dividend_rate = get_annual_dividend_rate(h["ticker"], info)
        if dividend_rate and shares:
            native_currency = info.get("currency", display_currency)
            native_amount = dividend_rate * shares
            converted_amount = None
            if native_currency == display_currency:
                converted_amount = native_amount
            else:
                fx_rate = get_fx_rate(native_currency, display_currency)
                if fx_rate is not None:
                    converted_amount = native_amount * fx_rate
                else:
                    conversion_failed = True
            if converted_amount is not None:
                total_annual_dividend += converted_amount

            # Dividendrendement = jaarlijks dividend per aandeel / huidige koers.
            # Zelfde robuuste prijs-terugval als bij Performance (sommige
            # effecten missen currentPrice/regularMarketPrice in .info).
            current_price = info.get("currentPrice") or info.get("regularMarketPrice")
            if current_price is None:
                try:
                    fallback_hist = get_cached_ticker_history(h["ticker"], period="5d")
                    if fallback_hist is not None and not fallback_hist.empty:
                        current_price = float(fallback_hist["Close"].iloc[-1])
                except Exception:
                    pass
            yield_pct = (dividend_rate / current_price * 100) if current_price else None

            per_position.append({
                "naam": h["naam"],
                "ticker": h["ticker"],
                "annual_dividend": converted_amount,
                "yield_pct": yield_pct,
            })
        ex_div = info.get("exDividendDate")
        if ex_div:
            try:
                date_str = pd.Timestamp(ex_div, unit="s").date()
                # yfinance's exDividendDate is soms de MEEST RECENTE (al
                # gepasseerde) datum i.p.v. een daadwerkelijk toekomstige --
                # alleen tonen als 'ie ook echt nog moet komen.
                if date_str >= datetime.now().date():
                    upcoming.append((h["naam"], date_str))
            except Exception:
                pass

    currency_symbol = "€" if display_currency == "EUR" else ("$" if display_currency == "USD" else display_currency + " ")
    if total_annual_dividend > 0:
        underestimate_note = (
            " (couldn't convert every position's currency, so this may be a slight underestimate)"
            if conversion_failed else ""
        )
        findings.append(
            f"{_icon_span('payments', size_px=14, color='#8992A3')} Estimated annual dividend income: ~{currency_symbol}{total_annual_dividend:,.0f}{underestimate_note}."
        )
        if upcoming:
            upcoming.sort(key=lambda x: x[1])
            dates_str = ", ".join(f"{n} ({d})" for n, d in upcoming[:5])
            findings.append(f"Upcoming ex-dividend dates: {dates_str}.")
    else:
        findings.append("No dividend-paying positions detected (or data unavailable).")

    per_position.sort(key=lambda p: p["annual_dividend"] or 0, reverse=True)
    return {"findings": findings, "per_position": per_position, "currency_symbol": currency_symbol}


def check_triggered_watchlist_alerts(watchlist_items: list, market_data: dict) -> list:
    """
    Controleert alle watchlist-items met een ingestelde alert tegen de
    huidige koers (uit de al-opgehaalde market_data, geen extra
    aanroepen nodig), en geeft de items terug waarvan de alert is
    GETRIGGERD (koers heeft de streefprijs in de ingestelde richting
    bereikt) en nog niet is afgehandeld (alert_dismissed=False).

    'below': triggert zodra de koers OP of ONDER de streefprijs komt.
    'above': triggert zodra de koers OP of BOVEN de streefprijs komt.
    """
    triggered = []
    for w in watchlist_items:
        target_price = w.get("alert_target_price")
        if target_price is None or w.get("alert_dismissed"):
            continue
        current_price = market_data.get(w["ticker"], {}).get("current_price")
        if current_price is None:
            continue
        direction = w.get("alert_direction")
        if direction == "below" and current_price <= target_price:
            triggered.append({**w, "current_price": current_price})
        elif direction == "above" and current_price >= target_price:
            triggered.append({**w, "current_price": current_price})
    return triggered


def get_watchlist_near_target_alerts(watchlist_items: list, market_data: dict, near_pct: float = 2.0, max_items: int = 3) -> list:
    """
    Zelfde basis als check_triggered_watchlist_alerts(), maar dan voor
    watchlist-items die hun alert-koers nog NIET geraakt hebben, maar er
    wel al dichtbij zijn (binnen 'near_pct' procent van de streefprijs).
    Bedoeld voor de 'Watchlist-Snack'-kaart op Today -- een vroege
    heads-up voordat de alert zelf afgaat.

    'distance_pct' is altijd positief en geeft aan hoeveel procent de
    huidige koers nog van de streefprijs verwijderd is. Al-getriggerde
    of afgehandelde alerts worden overgeslagen (die horen bij de
    bestaande, prominente alert-melding bovenaan Today).
    """
    near = []
    for w in watchlist_items:
        target_price = w.get("alert_target_price")
        if target_price is None or w.get("alert_dismissed") or not target_price:
            continue
        current_price = market_data.get(w["ticker"], {}).get("current_price")
        if current_price is None:
            continue
        direction = w.get("alert_direction")
        if direction == "below" and current_price > target_price:
            distance_pct = (current_price - target_price) / target_price * 100
        elif direction == "above" and current_price < target_price:
            distance_pct = (target_price - current_price) / target_price * 100
        else:
            continue  # al getriggerd, of geen geldige richting
        if distance_pct <= near_pct:
            near.append({**w, "current_price": current_price, "distance_pct": distance_pct})
    near.sort(key=lambda x: x["distance_pct"])
    return near[:max_items]


def build_rebalancing_suggestions(holdings: list, total_value: float, materiality_threshold_pct: float = 1.0) -> dict:
    """
    Berekent concrete koop/verkoop-suggesties voor elke positie met een
    ingesteld target_weight, om weer op de eigen, gewenste verdeling uit
    te komen.

    Alleen posities MET een ingesteld target_weight doen mee -- posities
    zonder target worden simpelweg overgeslagen (geen 'impliciet 0%'-
    aanname), dus de ingestelde targets hoeven niet op te tellen tot
    100%. WEL wordt gewaarschuwd als de som van de ingestelde targets
    boven de 100% uitkomt, want dat is wiskundig inconsistent (je kunt
    nooit alle targets tegelijk halen als ze samen meer dan de hele
    portfolio claimen).

    'materiality_threshold_pct' filtert triviale afwijkingen eruit (bv.
    0,3 procentpunt van je target af zitten is geen bruikbare suggestie
    om voor te handelen) -- standaard 1 procentpunt.

    Retourneert:
    {
        "suggestions": [{naam, ticker, current_pct, target_pct,
                          diff_pct, diff_value, diff_shares, action}, ...],
                         gesorteerd op grootste absolute afwijking eerst.
                         diff_shares is None als het aantal stuks van de
                         positie onbekend of nul is (kan dan niet worden
                         afgeleid).
        "targets_sum_pct": som van alle ingestelde targets,
        "any_targets_set": of er uberhaupt targets zijn ingesteld,
    }
    """
    positions_with_target = [h for h in holdings if h.get("target_weight") is not None]
    targets_sum_pct = sum(h["target_weight"] for h in positions_with_target)

    suggestions = []
    if total_value:
        for h in positions_with_target:
            current_value = h.get("position_value") or 0
            current_pct = (current_value / total_value) * 100
            target_pct = h["target_weight"]
            diff_pct = target_pct - current_pct
            if abs(diff_pct) < materiality_threshold_pct:
                continue
            target_value = total_value * (target_pct / 100)
            diff_value = target_value - current_value

            # Aantal aandelen afleiden uit de huidige prijs per stuk
            # (position_value / shares) -- geeft alleen een schatting als
            # zowel shares als position_value bekend en positief zijn.
            shares = h.get("shares") or 0
            if shares > 0 and current_value > 0:
                price_per_share = current_value / shares
                diff_shares = diff_value / price_per_share
            else:
                diff_shares = None

            suggestions.append({
                "naam": h["naam"],
                "ticker": h["ticker"],
                "current_pct": current_pct,
                "target_pct": target_pct,
                "diff_pct": diff_pct,
                "diff_value": diff_value,
                "diff_shares": diff_shares,
                "action": "buy" if diff_value > 0 else "sell",
            })
    suggestions.sort(key=lambda s: abs(s["diff_pct"]), reverse=True)

    return {
        "suggestions": suggestions,
        "targets_sum_pct": targets_sum_pct,
        "any_targets_set": len(positions_with_target) > 0,
    }


def build_daily_portfolio_stats(holdings: list, market_data: dict = None):
    """
    Dag-op-dag statistieken: totale verandering, en beste/slechtste
    presteerder van gisteren.

    'market_data' is het resultaat van database.get_market_data_for_tickers()
    -- de door het achtergrond-sync-script (elke 15 min) ververste, GEDEELDE
    tabel. Dit vervangt de vroegere LIVE yfinance-aanroep tijdens het laden
    van de pagina (traag) door een snelle database-lookup. Voor tickers die
    nog niet gesynchroniseerd zijn (net toegevoegd, of de eerste sync-run
    moet nog draaien) valt de functie netjes terug op de oude, live aanpak
    -- dus nooit een harde afhankelijkheid van de sync-tabel.
    """
    performers = []
    total_value_today = 0.0
    total_value_yesterday = 0.0
    market_data = market_data or {}

    for h in holdings:
        shares = h.get("shares") or 0
        if not shares:
            continue
        try:
            data = market_data.get(h["ticker"], {})

            # GEVONDEN BUG: deze functie vertrouwde de gedeelde,
            # achtergrond-gesynchroniseerde ticker_market_data-tabel altijd
            # blind, ongeacht hoe oud een rij daadwerkelijk was. Als het
            # sync-script (elke 15 min) voor 1 SPECIFIEKE ticker stilletjes
            # vastliep of faalde (netwerkhik, tijdelijke yfinance-storing --
            # exact dezelfde klasse bug als eerder al gevonden en gefixt in
            # screener_daily.py), bleef de oude 'previous_close'/
            # 'current_price' voor die ticker voor altijd staan, met een
            # 'Best today'/'Worst today'-percentage tot gevolg dat niets
            # meer met de werkelijke, huidige koers te maken had (bv. GRAB
            # die '+8.2%' toonde terwijl de koers allang niet meer zo hoog
            # stond). Nu: een rij ouder dan 1 uur (4x de sync-cyclus, ruime
            # marge) wordt NIET vertrouwd en behandeld als 'ontbrekend' --
            # dezelfde, al-bevestigd-betrouwbare live-yfinance-terugval
            # hieronder vangt 'm dan alsnog op.
            _last_updated_str = data.get("last_updated")
            _is_fresh = False
            if _last_updated_str:
                try:
                    _last_updated_dt = datetime.fromisoformat(_last_updated_str)
                    _is_fresh = (datetime.now() - _last_updated_dt) < timedelta(hours=1)
                except Exception:
                    _is_fresh = False

            price_today = data.get("current_price") if _is_fresh else None
            price_yesterday = data.get("previous_close") if _is_fresh else None

            if price_today is None or not price_yesterday:
                # Terugval: ticker nog niet (of nog niet recent) gesynchroniseerd
                # -- dezelfde, al-bevestigd-betrouwbare live-aanpak als voorheen.
                info = get_cached_ticker_info(h["ticker"])
                price_today = info.get("regularMarketPrice")
                price_yesterday = info.get("regularMarketPreviousClose") or info.get("previousClose")
                if price_today is None or not price_yesterday:
                    hist = get_cached_ticker_history(h["ticker"], period="5d")
                    if len(hist) < 2:
                        continue
                    price_today = float(hist["Close"].iloc[-1])
                    price_yesterday = float(hist["Close"].iloc[-2])
            # Sommige dagen ontbreekt een koers (bv. rond een feestdag/data-gat) --
            # yfinance geeft dan NaN terug. Zonder deze check zou 1 NaN de HELE
            # portfolio-som NaN maken (NaN + iets = NaN), en 'total_value_yesterday
            # <= 0' vangt dat niet af (NaN-vergelijkingen zijn altijd False in
            # Python) -- vandaar dat '+nan%' anders alsnog getoond zou worden.
            if pd.isna(price_today) or pd.isna(price_yesterday) or price_yesterday <= 0:
                continue
            change_pct = (price_today / price_yesterday - 1) * 100
            position_value_today = shares * price_today
            performers.append({"naam": h["naam"], "change_pct": change_pct, "position_value_today": position_value_today})
            total_value_today += position_value_today
            total_value_yesterday += shares * price_yesterday
        except Exception:
            continue

    if not performers or total_value_yesterday <= 0:
        return None

    portfolio_change_pct = (total_value_today / total_value_yesterday - 1) * 100
    if pd.isna(portfolio_change_pct):
        # Laatste veiligheidsnet -- zou niet meer moeten gebeuren dankzij de
        # check hierboven, maar voorkomt sowieso ooit weer een '+nan%'.
        return None
    best = max(performers, key=lambda p: p["change_pct"])
    worst = min(performers, key=lambda p: p["change_pct"])

    # Portfolio-weging van best/worst -- laat zien hoeveel IMPACT deze
    # stijger/daler daadwerkelijk heeft (een +8% dagbeweging op een
    # positie van 1% van je portfolio is heel iets anders dan dezelfde
    # +8% op een positie van 20%). total_value_today is hier altijd > 0,
    # want elke performer droeg een positieve shares*price bij.
    best_weight_pct = (best["position_value_today"] / total_value_today) * 100 if total_value_today else 0.0
    worst_weight_pct = (worst["position_value_today"] / total_value_today) * 100 if total_value_today else 0.0

    return {
        "portfolio_change_pct": round(portfolio_change_pct, 2),
        "best_performer": best["naam"],
        "best_change_pct": round(best["change_pct"], 2),
        "best_weight_pct": round(best_weight_pct, 2),
        "worst_performer": worst["naam"],
        "worst_change_pct": round(worst["change_pct"], 2),
        "worst_weight_pct": round(worst_weight_pct, 2),
    }


def _find_held_or_watched_technical_signal(holdings: list, watchlist_items: list) -> dict | None:
    """
    Zoekt een ECHT technisch screener-signaal (Supertrend bullish-omslag)
    op een ticker die je al BEZIT of VOLGT -- i.p.v. Today's Daily Radar
    een kale 'nieuwe screener-opportunity' als DDOG te laten tonen, een
    ticker die je toch niet bezit en dus weinig direct actiegericht is.
    Leest dezelfde CSV's als build_opportunities_today() (dag + week),
    filtert op je eigen tickers, en kiest bij meerdere matches de HOOGSTE
    score. Geeft None als er geen enkele match is -- de aanroeper valt dan
    terug op een neutrale 'system stable'-statusregel i.p.v. iets te
    verzinnen.
    """
    holding_tickers = {h["ticker"] for h in holdings}
    watchlist_tickers = {w["ticker"] for w in watchlist_items}
    own_tickers = holding_tickers | watchlist_tickers
    if not own_tickers:
        return None

    frames = []
    if os.path.exists("supertrend_signals_daily.csv"):
        df_daily = pd.read_csv("supertrend_signals_daily.csv")
        if not df_daily.empty:
            df_daily["_days_ago"] = df_daily.get("dagen_geleden")
            frames.append(df_daily)
    if os.path.exists("supertrend_signals.csv"):
        df_weekly = pd.read_csv("supertrend_signals.csv")
        if not df_weekly.empty:
            df_weekly["_days_ago"] = (
                df_weekly["weken_geleden"] * 7 if "weken_geleden" in df_weekly.columns else None
            )
            frames.append(df_weekly)
    if not frames:
        return None

    combined = pd.concat(frames, ignore_index=True, sort=False)
    matches = combined[combined["ticker"].isin(own_tickers)]
    if matches.empty or "score" not in matches.columns:
        return None

    best = matches.sort_values("score", ascending=False).iloc[0]
    return {
        "ticker": best["ticker"],
        "score": float(best["score"]) if pd.notna(best.get("score")) else None,
        "days_ago": int(best["_days_ago"]) if pd.notna(best.get("_days_ago")) else None,
        "since_pct": float(best["sinds_omslag_pct"]) if pd.notna(best.get("sinds_omslag_pct")) else None,
    }


def build_opportunities_today(holdings: list, watchlist_items: list, include_weekly: bool = True) -> dict:
    """
    Leest de dagelijkse (+ optioneel wekelijkse) screener-uitkomsten en
    telt hoeveel signalen ergens bij jou horen. include_weekly=False
    laat de weekly-signalen overal buiten beschouwing (tellingen blijven
    zo consistent) -- gebruikt op dagen dat de gebruiker de wekelijkse
    batch al eerder heeft gezien, om niet elke dag dezelfde 58 weekly-
    signalen opnieuw te melden.
    """
    holding_tickers = {h["ticker"] for h in holdings}
    watchlist_tickers = {w["ticker"] for w in watchlist_items}

    daily_df = pd.read_csv("supertrend_signals_daily.csv") if os.path.exists("supertrend_signals_daily.csv") else None
    weekly_df = (
        pd.read_csv("supertrend_signals.csv")
        if include_weekly and os.path.exists("supertrend_signals.csv") else None
    )

    daily_count = len(daily_df) if daily_df is not None else 0
    weekly_count = len(weekly_df) if weekly_df is not None else 0

    all_signal_tickers = set()
    if daily_df is not None:
        all_signal_tickers |= set(daily_df["ticker"])
    if weekly_df is not None:
        all_signal_tickers |= set(weekly_df["ticker"])

    in_portfolio = all_signal_tickers & holding_tickers
    in_watchlist = (all_signal_tickers & watchlist_tickers) - in_portfolio
    new_opportunities = all_signal_tickers - holding_tickers - watchlist_tickers

    return {
        "total_signals": daily_count + weekly_count,
        "daily_signals": daily_count,
        "weekly_signals": weekly_count,
        "in_portfolio_count": len(in_portfolio),
        "in_watchlist_count": len(in_watchlist),
        "new_opportunities_count": len(new_opportunities),
    }


US_SECTOR_ETFS = {
    "Technology": "XLK", "Financials": "XLF", "Energy": "XLE", "Health Care": "XLV",
    "Consumer Discretionary": "XLY", "Consumer Staples": "XLP", "Industrials": "XLI",
    "Materials": "XLB", "Utilities": "XLU", "Real Estate": "XLRE", "Communication Services": "XLC",
}

# Geverifieerde iShares STOXX Europe 600 sector-ETF's (Xetra) -- een kleinere,
# minder gestandaardiseerde set dan de Amerikaanse SPDR-sector-ETF's, maar dit
# zijn de tickers die daadwerkelijk bestaan en op Yahoo Finance te vinden zijn.
EU_SECTOR_ETFS = {
    "Banks": "EXV1.DE", "Technology": "EXV3.DE", "Health Care": "EXV4.DE",
    "Telecommunications": "EXV2.DE", "Oil & Gas": "EXH1.DE", "Food & Beverage": "EXH3.DE",
    "Industrial Goods & Services": "EXH4.DE", "Utilities": "EXH9.DE",
    "Basic Resources": "EXV6.DE", "Automobiles & Parts": "EXV5.DE",
}

# Populaire THEMA-ETF's (niet officiële GICS-sectoren, maar cross-sector
# trends die veel gevolgd worden) -- bewust apart van Sector Rotation
# gehouden, anders zou een bedrijf dubbel meetellen (1x onder z'n echte
# sector, 1x onder het thema).
THEME_ETFS = {
    "Robotics & AI": "BOTZ", "Clean Energy": "ICLN", "Cybersecurity": "CIBR",
    "Semiconductors": "SMH", "Genomics & Biotech": "ARKG",
    "Cloud / SaaS": "WCLD", "Data Centers": "DTCR", "Aerospace & Defense": "ITA",
    "Quantum Computing": "QTUM", "Nuclear Energy": "NLR", "Space": "ARKX",
    "Drones": "UAV", "Materials & Critical Minerals": "REMX", "Fintech": "FINX",
    "Infrastructure": "PAVE", "Power & Utilities": "XLU",
    "Crypto (Top 10)": "HODLX.SW", "Precious Metals": "GLTR",
}

# yfinance's eigen 'sector'-veld gebruikt ANDERE namen dan onze
# US_SECTOR_ETFS-lijst (bv. 'Financial Services' i.p.v. 'Financials',
# 'Healthcare' i.p.v. 'Health Care') -- deze mapping overbrugt dat, zodat
# een deep-dive's sector-rotatie-context correct kan koppelen.
YFINANCE_SECTOR_TO_OURS = {
    "Technology": "Technology",
    "Financial Services": "Financials",
    "Energy": "Energy",
    "Healthcare": "Health Care",
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Industrials": "Industrials",
    "Basic Materials": "Materials",
    "Utilities": "Utilities",
    "Real Estate": "Real Estate",
    "Communication Services": "Communication Services",
}


def render_section_banner(title: str):
    """
    Dikke, opvallende sectie-banner (i.p.v. een dun lijntje) om groepen
    kaarten van elkaar te onderscheiden -- gebruikt op zowel Discover
    ('The Bigger Picture') als Analyze ('Risk & Diversification', 'Income').
    """
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, rgba(31,174,150,0.14), rgba(31,174,150,0.02));
                    border: 1px solid rgba(31,174,150,0.35); border-radius: 10px;
                    padding: 0.85rem 1.25rem; margin: 1.5rem 0 1rem 0;">
            <div style="color:#1FAE96; font-weight:700; font-size:0.8rem; letter-spacing:1.5px; text-transform:uppercase;">
                {title}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_sector_theme_threshold_alerts() -> list:
    """
    Checkt sectoren EN thema's op extreme 1-maands-trailing-rendementen --
    mogelijk een koop-/verkoopmoment (sterk gedaald) of iets om in de gaten
    te houden (sterk gestegen). Thema's krijgen een ruimere drempel dan
    sectoren, want smallere thema-ETF's (bv. BOTZ, ARKG) zijn van nature
    volatieler -- eenzelfde uitslag is daar minder bijzonder.

    Sectoren: onder -10% ('notable'), boven +10% ('notable'), boven +15%
    ('extreme'). Thema's: onder -15%, boven +15%, boven +20%.
    """
    alerts = []

    for region in ["US", "EU"]:
        try:
            rotation = build_sector_rotation(region=region)
        except Exception:
            continue
        for r in rotation:
            pct = r["return_pct"]
            if pct <= -10:
                alerts.append({"name": r["sector"], "kind": "sector", "region": region, "pct": pct, "level": "notable", "direction": "down"})
            elif pct >= 15:
                alerts.append({"name": r["sector"], "kind": "sector", "region": region, "pct": pct, "level": "extreme", "direction": "up"})
            elif pct >= 10:
                alerts.append({"name": r["sector"], "kind": "sector", "region": region, "pct": pct, "level": "notable", "direction": "up"})

    try:
        theme_rotation = build_theme_rotation()
    except Exception:
        theme_rotation = []
    for r in theme_rotation:
        pct = r["return_pct"]
        if pct <= -15:
            alerts.append({"name": r["theme"], "kind": "theme", "region": None, "pct": pct, "level": "notable", "direction": "down"})
        elif pct >= 20:
            alerts.append({"name": r["theme"], "kind": "theme", "region": None, "pct": pct, "level": "extreme", "direction": "up"})
        elif pct >= 15:
            alerts.append({"name": r["theme"], "kind": "theme", "region": None, "pct": pct, "level": "notable", "direction": "up"})

    alerts.sort(key=lambda a: abs(a["pct"]), reverse=True)
    return alerts


THEME_ROTATION_WINDOW_DAYS = 21  # handelsdagen -- zelfde als build_theme_rotation_trend()'s rolling_window_days


def build_theme_rotation(window_days: int = THEME_ROTATION_WINDOW_DAYS) -> list:
    """
    Zelfde logica als build_sector_rotation(), maar dan voor de populaire
    THEMA-ETF's (Robotics & AI, Clean Energy, etc.) i.p.v. de officiële
    GICS-sectoren.

    Gebruikt een EXACT 'N handelsdagen terug'-venster (i.p.v. yfinance's
    'period=1mo'-string) -- zodat dit getal exact overeenkomt met het
    laatste punt van build_theme_rotation_trend()'s grafiek. Voorheen
    gebruikten beide een net-iets-ander tijdvak (kalendermaand vs. 21
    handelsdagen), wat bij een volatiel thema zoals Genomics & Biotech
    tot een merkbaar afwijkend percentage kon leiden.
    """
    fetch_period = f"{window_days + 15}d"
    results = []
    for theme, ticker in THEME_ETFS.items():
        try:
            hist = get_cached_ticker_history(ticker, period=fetch_period)
            if hist is None or hist.empty:
                continue
            # Zelfde fix als bij build_sector_rotation(): de eerste/laatste
            # rij kan een onvolledige koers (NaN) zijn -- pak de eerste/
            # laatste GELDIGE koers i.p.v. blindelings de rand-rijen.
            valid_closes = hist["Close"].dropna()
            if len(valid_closes) > window_days:
                ret = (valid_closes.iloc[-1] / valid_closes.iloc[-1 - window_days] - 1) * 100
                results.append({"theme": theme, "ticker": ticker, "return_pct": round(ret, 2)})
        except Exception:
            continue

    results.sort(key=lambda x: x["return_pct"], reverse=True)
    return results


def build_sector_rotation_trend(region: str = "US", lookback_months: int = 6, rolling_window_days: int = 21) -> dict:
    """
    Geeft voor elke sector-ETF een TIJDREEKS van het rollende 1-maands-
    rendement terug (i.p.v. build_sector_rotation()'s enkele, huidige
    getal) -- laat zien of een sector aan het versnellen, vertragen, of
    OMSLAAN is, zodat een reversal visueel te herkennen is in een
    lijngrafiek. Sectoren met te weinig historische data worden
    overgeslagen (geen crash bij een enkele problematische ticker).
    """
    etfs = US_SECTOR_ETFS if region == "US" else EU_SECTOR_ETFS
    total_days_needed = lookback_months * 31 + rolling_window_days + 15  # ruime marge voor weekends/feestdagen
    result = {}
    for sector, ticker in etfs.items():
        try:
            hist = get_cached_ticker_history(ticker, period=f"{total_days_needed}d")
            if hist is None or hist.empty:
                continue
            closes = hist["Close"].dropna()
            if len(closes) < rolling_window_days + 5:
                continue
            rolling_return = (closes / closes.shift(rolling_window_days) - 1) * 100
            rolling_return = rolling_return.dropna()
            if rolling_return.empty:
                continue
            cutoff_date = rolling_return.index[-1] - pd.Timedelta(days=lookback_months * 31)
            rolling_return = rolling_return[rolling_return.index >= cutoff_date]
            result[sector] = {
                "dates": rolling_return.index.strftime("%Y-%m-%d").tolist(),
                "values": rolling_return.round(2).tolist(),
            }
        except Exception:
            continue
    return result


def build_theme_rotation_trend(lookback_months: int = 6, rolling_window_days: int = 21) -> dict:
    """
    Zelfde logica als build_sector_rotation_trend(), maar dan voor de
    THEMA-ETF's -- geeft per thema een tijdreeks van het rollende
    1-maands-rendement terug, i.p.v. build_theme_rotation()'s enkele,
    huidige getal.
    """
    total_days_needed = lookback_months * 31 + rolling_window_days + 15
    result = {}
    for theme, ticker in THEME_ETFS.items():
        try:
            hist = get_cached_ticker_history(ticker, period=f"{total_days_needed}d")
            if hist is None or hist.empty:
                continue
            closes = hist["Close"].dropna()
            if len(closes) < rolling_window_days + 5:
                continue
            rolling_return = (closes / closes.shift(rolling_window_days) - 1) * 100
            rolling_return = rolling_return.dropna()
            if rolling_return.empty:
                continue
            cutoff_date = rolling_return.index[-1] - pd.Timedelta(days=lookback_months * 31)
            rolling_return = rolling_return[rolling_return.index >= cutoff_date]
            result[theme] = {
                "dates": rolling_return.index.strftime("%Y-%m-%d").tolist(),
                "values": rolling_return.round(2).tolist(),
            }
        except Exception:
            continue
    return result


def _rotation_gradient_color(return_pct):
    """
    Interpoleert tussen rood (sterk negatief, <=-15%), amber (neutraal,
    rond 0%), en jade-groen (sterk positief, >=+15%) -- i.p.v. binair
    groen/rood, zodat echte uitschieters in BEIDE richtingen er visueel
    uitspringen t.o.v. iets dat maar een beetje beweegt.

    Gebruikt een vierkantswortel-curve i.p.v. een lineaire -- bij
    lineair bewoog een klein percentage (bv. +2.6%) nauwelijks weg van
    amber, waardoor + en - moeilijk uit elkaar te houden waren op het
    oog. Met sqrt() beweegt de kleur SNEL weg van amber bij kleine
    percentages, en vlakt af richting de uiterste kleur -- meer
    contrast precies waar het toe doet, terwijl grote uitschieters nog
    steeds gewoon uitkomen op puur rood/groen.

    Gedeeld tussen Sector rotation en Themes (zelfde tegel-stijl).
    """
    clamped = max(-15.0, min(15.0, return_pct))
    red, amber, green = (229, 72, 77), (232, 169, 60), (31, 174, 150)
    if clamped >= 0:
        t = (clamped / 15.0) ** 0.5  # 0 = amber, 1 = puur groen
        start, end = amber, green
    else:
        t = ((-clamped) / 15.0) ** 0.5  # 0 = amber, 1 = puur rood
        start, end = amber, red
    r = round(start[0] + (end[0] - start[0]) * t)
    g = round(start[1] + (end[1] - start[1]) * t)
    b = round(start[2] + (end[2] - start[2]) * t)
    return r, g, b


ROTATION_ROCKET_THRESHOLD_PCT = 10  # vanaf dit rendement verschijnt het 🚀-icoontje

# Vaste, kleine cap voor HOEVEEL standout-signalen tegelijk getoond worden
# (Momentocrats/Snowballers/Rocket List) -- LOS van _signal_display_limit,
# want die laatste is None (= onbeperkt) voor Premium-gebruikers. Zonder
# deze aparte cap kon een week met bijzonder veel standouts (bv. tijdens
# een brede marktrally) alsnog tientallen kaarten tonen voor Premium-
# gebruikers, exact het probleem dat de standout-filtering net had moeten
# oplossen.
_STANDOUT_DISPLAY_CAP = 10


def _rotation_tile_html(rank, name, return_pct):
    r, g, b = _rotation_gradient_color(return_pct)
    text_color = f"rgb({r},{g},{b})"
    trend_arrow = "&#8599;" if return_pct >= 0 else "&#8600;"
    rocket_span = " &#128640;" if return_pct >= ROTATION_ROCKET_THRESHOLD_PCT else ""

    # Dunne, flinterdunne horizontale strip met een zachte, egale
    # achtergrondvulling (bg-slate-950/40) -- exact dezelfde designtaal
    # als de Rebalancing/Watchlist-kaarten, nu ook met wat 'textuur'
    # i.p.v. volledig transparant tegen de kale paginaeachtergrond.
    return (
        f'<div style="background:rgba(2,6,23,0.4); border:1px solid rgba(15,23,42,0.6); '
        f'border-radius:10px; padding:0.5rem 0.875rem; box-sizing:border-box; display:flex; '
        f'align-items:center; justify-content:space-between; gap:0.6rem; width:100%; max-width:100%; '
        f'overflow:hidden;">'
        f'<div style="display:flex; align-items:center; gap:0.5rem; min-width:0; overflow:hidden;">'
        f'<span style="font-size:0.65rem; color:#5B6472; font-weight:700; flex-shrink:0;">#{rank}</span>'
        f'<span style="font-size:0.82rem; color:#EAEDF1; font-weight:600; overflow:hidden; '
        f'text-overflow:ellipsis; white-space:nowrap;">{name}{rocket_span}</span>'
        f'</div>'
        f'<span style="font-size:0.9rem; font-weight:700; color:{text_color}; white-space:nowrap; '
        f'flex-shrink:0;">{trend_arrow} {return_pct:+.1f}%</span>'
        f'</div>'
    )


def _render_rotation_tiles(items: list, name_key: str) -> None:
    """
    Rendert een responsief 2-koloms grid van dunne strips voor rotatie-
    data (Sectors of Themes) -- 1 gedeelde renderer i.p.v. losse
    implementaties, zodat beide secties er altijd exact hetzelfde
    uitzien (nu ook in dezelfde stijl als Rebalancing/Watchlist).

    items: lijst met dicts, elk met minstens 'return_pct' en name_key
    (bv. 'sector' of 'theme'). Verwacht al gesorteerd te zijn (bepaalt
    de rangnummers).
    """
    tiles_html = "".join(
        _rotation_tile_html(i + 1, item[name_key], item["return_pct"]) for i, item in enumerate(items)
    )
    st.markdown(
        '<style>'
        '.hesty-rotation-grid { display:grid; grid-template-columns:repeat(2, 1fr); gap:0.5rem; '
        'width:100%; max-width:100%; overflow-x:hidden; box-sizing:border-box; margin:0.5rem 0 1rem 0; } '
        '@media (max-width:768px) { .hesty-rotation-grid { grid-template-columns:1fr; } } '
        '</style>'
        f'<div class="hesty-rotation-grid">{tiles_html}</div>',
        unsafe_allow_html=True,
    )


def _signal_card_html(ticker: str, primary_label: str, primary_value: str, primary_positive, secondary_stats: list, standout: bool = False, neutral_border: bool = False) -> str:
    """
    Bouwt 1 signaal-kaart (Momentocrats/Snowballers/Rocket List/Earnings
    surprises) -- i.p.v. een brede st.dataframe met 13+ kolommen, die op
    mobiel dubbel-scrollen afdwingt (verticaal EN horizontaal). Toont de
    KERN-metric groot en gekleurd, en een paar secundaire stats compact
    eronder.

    primary_positive: True (groen), False (rood), of None (neutraal wit)
    secondary_stats: lijst van (label, al-geformatteerde waarde)-tuples
    standout: True voor een extra visueel accent (sterkere rand + gloed +
    ⭐-badge) bij écht opvallende signalen (bv. Momentocrats-score >= 8) --
    precies de handvol die de moeite waard zijn om verder te bekijken.
    neutral_border: True voor een reguliere, dunne border-slate-800/60
    i.p.v. de gekleurde accent-rand -- gebruikt bij Earnings surprises,
    waar elke kaart een gelijkwaardig datapunt is (geen 'opvallendere'
    signalen zoals bij de screeners), dus een felle gekleurde rand op elke
    kaart oogde onterecht zwaar/opdringerig.
    """
    # Normaliseer naar een NATIVE Python True/False/None -- een waarde die
    # rechtstreeks uit een pandas-vergelijking komt (bv. row['x'] < 0, of
    # een boolean-kolom uit een CSV) is een numpy.bool_, GEEN Python bool.
    # 'numpy.bool_(True) is True' geeft dan ONTERECHT False terug (identity-
    # check faalt bij een ander type), waardoor de kleur hieronder altijd
    # op het neutrale wit zou blijven hangen i.p.v. groen/rood. Ook een
    # ontbrekende waarde (NaN, bv. bij earnings_beat dat niet bekend is)
    # moet expliciet None worden -- bool(nan) geeft anders ONTERECHT True
    # terug (elk niet-nul getal is 'truthy' in Python, NaN incluis).
    if primary_positive is not None and pd.isna(primary_positive):
        primary_positive = None
    elif primary_positive is not None:
        primary_positive = bool(primary_positive)

    if primary_positive is True:
        color = "#1FAE96"
        accent_rgb = "31,174,150"
    elif primary_positive is False:
        color = "#E5484D"
        accent_rgb = "229,72,77"
    else:
        color = "#EAEDF1"
        accent_rgb = "137,146,163"

    # 2x2-grid i.p.v. alles op 1 rij -- bij 4 stats naast elkaar in een
    # smalle tegel was er te weinig ruimte per label, waardoor woorden
    # midden doorbraken (bv. 'FLIP'/'PED'). white-space:nowrap op zowel
    # het label als de waarde voorkomt dat definitief.
    secondary_html = "".join(
        f'<div style="min-width:0;">'
        f'<div style="font-size:0.62rem; color:#8992A3; text-transform:uppercase; letter-spacing:0.03em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{label}</div>'
        f'<div style="font-size:0.82rem; font-weight:600; color:#EAEDF1; margin-top:2px; white-space:nowrap;">{value}</div>'
        f'</div>'
        for label, value in secondary_stats
    )

    star_badge = ' <span style="font-size:0.9rem;">⭐</span>' if standout else ""
    # Achtergrond nu een KLEUR-GETINTE gradient (groen/rood/grijs, afhankelijk
    # van primary_positive) i.p.v. altijd hetzelfde neutrale grijs -- geeft
    # meer visuele 'pop', consistent met de rest van de app (opt-in-banner,
    # rotatie-tegels). Standout-kaarten krijgen een STERKERE versie van
    # DEZELFDE kleur (niet altijd jade, ook bij een negatieve standout).
    if neutral_border:
        border_style = "1px solid rgba(51,65,85,0.6)"
        box_shadow = ""
        background = f"background: linear-gradient(135deg, rgba({accent_rgb},0.12), rgba({accent_rgb},0.02)); "
    elif standout:
        border_style = f"1.5px solid rgba({accent_rgb},0.6)"
        box_shadow = f"box-shadow:0 0 16px rgba({accent_rgb},0.2); "
        background = f"background: linear-gradient(135deg, rgba({accent_rgb},0.20), rgba({accent_rgb},0.03)); "
    else:
        border_style = f"1px solid rgba({accent_rgb},0.3)"
        box_shadow = ""
        background = f"background: linear-gradient(135deg, rgba({accent_rgb},0.12), rgba({accent_rgb},0.02)); "

    # Geen voorloop-spaties/newlines -- zelfde reden als bij de rotatie-
    # tegels: Markdown zou dit anders als een code-blok interpreteren.
    return (
        f'<div style="height:100%; box-sizing:border-box; {background}'
        f'border:{border_style}; {box_shadow}border-radius:10px; padding:0.65rem 0.75rem; '
        f'display:flex; flex-direction:column;">'
        f'<div style="font-size:0.88rem; font-weight:800; color:#EAEDF1;">{str(ticker).upper()}{star_badge}</div>'
        f'<div style="font-size:1.2rem; font-weight:800; color:{color}; margin-top:3px; white-space:nowrap;">{primary_value}</div>'
        f'<div style="font-size:0.6rem; color:#8992A3; margin-top:1px;">{primary_label}</div>'
        f'<div style="display:grid; grid-template-columns:repeat(2, 1fr); gap:4px 8px; margin-top:auto; padding-top:6px; '
        f'border-top:1px solid rgba(137,146,163,0.15);">{secondary_html}</div>'
        f'</div>'
    )


def _render_signal_cards(cards_html: list, blur_from_index: int = None) -> None:
    """
    Rendert een responsieve grid van signaal-kaarten (zelfde auto-fill/
    minmax-aanpak als rotatie-tegels). 'blur_from_index' (optioneel) --
    voor niet-ingelogde bezoekers bij Snowballers/Rocket List: kaarten
    VANAF die index krijgen een blur + slotje-overlay (bewijst dat er
    meer is, zonder de data zelf weg te geven) i.p.v. volledig te
    verbergen zoals eerder.
    """
    if blur_from_index is not None:
        wrapped = []
        for i, card in enumerate(cards_html):
            if i >= blur_from_index:
                wrapped.append(
                    f'<div style="position:relative;">'
                    f'<div style="filter:blur(4px); pointer-events:none; opacity:0.4;">{card}</div>'
                    f'<div style="position:absolute; inset:0; display:flex; align-items:center; '
                    f'justify-content:center;">{_icon_span("lock", size_px=22, color="#CBD5E1")}</div>'
                    f'</div>'
                )
            else:
                wrapped.append(card)
        combined = "".join(wrapped)
    else:
        combined = "".join(cards_html)
    st.markdown(
        f'<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(140px, 1fr)); '
        f'gap:0.5rem; margin: 0.5rem 0 1rem 0;">{combined}</div>',
        unsafe_allow_html=True,
    )


def _icon_span(name: str, size_px: int = 18, color: str = "currentColor") -> str:
    """
    Geeft 1 icoon terug uit dezelfde, consistente lijn-icoon-bibliotheek
    als de zijbalk (Material Symbols) -- i.p.v. losse emoji, die overal
    net anders ogen (kleurrijk, verschillende stijlen door elkaar). Werkt
    overal waar unsafe_allow_html gebruikt wordt (dus ook buiten
    st.page_link, waar Streamlit's eigen :material/naam:-syntax beperkt
    tot is).
    """
    return (
        f'<span class="material-symbols-outlined" '
        f'style="font-size:{size_px}px; color:{color};">{name}</span>'
    )


def _landing_table_skeleton_html(rows: int = 5) -> str:
    """
    Geblurde preview van een generieke tabel (Today/My Portfolio) -- puur
    neutrale skeleton-balkjes, GEEN nagemaakte tickers/bedragen. Zelfs
    geblurd zou nagemaakte data op zichzelf al kunnen worden aangezien
    voor echte cijfers.
    """
    row_html = (
        '<div style="display:flex; align-items:center; gap:0.75rem; padding:0.6rem 0;">'
        '<div style="width:28px; height:28px; border-radius:50%; background:rgba(137,146,163,0.15); flex-shrink:0;"></div>'
        '<div style="height:10px; width:35%; background:rgba(137,146,163,0.18); border-radius:4px;"></div>'
        '<div style="height:10px; width:15%; background:rgba(137,146,163,0.12); border-radius:4px; margin-left:auto;"></div>'
        '<div style="height:10px; width:12%; background:rgba(137,146,163,0.12); border-radius:4px;"></div>'
        '</div>'
    )
    return (
        f'<div style="filter:blur(4px); opacity:0.2; pointer-events:none; user-select:none; '
        f'-webkit-user-select:none;">{row_html * rows}</div>'
    )


def _landing_chart_skeleton_html() -> str:
    """
    Geblurde preview van een generiek staafdiagram (Analyze) -- zelfde
    'neutrale contouren, geen nagemaakte cijfers'-principe als de tabel-
    skeleton hierboven.
    """
    import random as _random
    _rng = _random.Random(42)  # vaste seed -- zelfde 'grafiek' bij elke render, geen flikkerende hoogtes
    bars_html = "".join(
        f'<div style="width:100%; height:{_rng.randint(30, 100)}%; background:rgba(137,146,163,0.15); '
        f'border-radius:4px 4px 0 0;"></div>'
        for _ in range(10)
    )
    return (
        f'<div style="filter:blur(4px); opacity:0.2; pointer-events:none; user-select:none; '
        f'-webkit-user-select:none; display:flex; align-items:flex-end; gap:0.6rem; height:200px;">'
        f'{bars_html}</div>'
    )


def _render_landing_soft_lock(title: str, icon_name: str, cta_text: str, button_label: str,
                               preview_html: str, key_prefix: str) -> None:
    """
    HET ene, universele 'niet-ingelogd'-landingssjabloon -- gedeeld door
    Today, My Portfolio en Analyze. Groene sectiekop + dunne lijn, dan 1
    grote, zachte tegel met een geblurde data-preview erin, en daarover-
    heen een kaarsrecht gecentreerde overlay (tekst + knop) die als een
    premium 'soft-lock' op de wazige data zweeft.
    """
    st.markdown(
        _uniform_section_header_html(title, icon_name, is_first=True),
        unsafe_allow_html=True,
    )
    _tile_key = f"{key_prefix}_landing_tile"
    _cta_key = f"{key_prefix}_landing_cta"
    _text_class = f"hesty-landing-cta-text-{key_prefix}"
    st.markdown(
        f'<style>'
        f'.st-key-{_tile_key} {{ position:relative !important; width:100% !important; min-height:300px !important; '
        f'background:rgba(15,23,42,0.3) !important; border:1px solid rgba(30,41,59,0.4) !important; '
        f'border-radius:14px !important; padding:1.5rem !important; box-sizing:border-box !important; '
        f'overflow:hidden !important; }} '
        f'@media (min-width:768px) {{ .st-key-{_tile_key} {{ padding:2rem !important; }} }} '
        f'.st-key-{_cta_key} {{ '
        f'position:absolute !important; top:50% !important; left:50% !important; '
        f'transform:translate(-50%, -50%) !important; z-index:10 !important; '
        f'width:auto !important; max-width:90% !important; '
        f'display:flex !important; flex-direction:column !important; align-items:center !important; '
        f'justify-content:center !important; text-align:center !important; }} '
        f'.{_text_class} {{ '
        f'max-width:32rem; color:#CBD5E1; font-weight:600; letter-spacing:0.04em; '
        f'text-transform:uppercase; line-height:1.6; font-size:0.78rem; }} '
        f'@media (min-width:768px) {{ .{_text_class} {{ font-size:0.85rem !important; }} }} '
        f'.st-key-{_cta_key} [data-testid="stButton"] {{ margin-top:1rem !important; }} '
        f'@media (min-width:768px) {{ '
        f'.st-key-{_cta_key} [data-testid="stButton"] {{ margin-top:1.25rem !important; }} '
        f'}} '
        f'.st-key-{_cta_key} button {{ '
        f'background:rgba(2,6,23,0.8) !important; backdrop-filter:blur(6px) !important; '
        f'-webkit-backdrop-filter:blur(6px) !important; color:#EAEDF1 !important; font-weight:700 !important; '
        f'text-transform:uppercase !important; letter-spacing:0.04em !important; font-size:0.85rem !important; '
        f'border:1px solid rgba(148,163,184,0.35) !important; border-radius:8px !important; '
        f'padding:0.6rem 1.5rem !important; width:auto !important; max-width:100% !important; '
        f'white-space:nowrap !important; box-shadow:0 8px 24px rgba(0,0,0,0.45) !important; }} '
        f'.st-key-{_cta_key} button:hover {{ border-color:rgba(31,174,150,0.6) !important; '
        f'color:#1FAE96 !important; }} '
        # Op mobiel is de tekst met white-space:nowrap breder dan het
        # scherm, waardoor 'ie symmetrisch links/rechts afloopt i.p.v.
        # netjes te passen (lijkt dan 'niet gecentreerd'). Op smalle
        # schermen: kleinere tekst + WEL laten omklappen.
        f'@media (max-width:480px) {{ '
        f'.st-key-{_cta_key} button {{ '
        f'white-space:normal !important; font-size:0.78rem !important; '
        f'padding:0.55rem 1.1rem !important; line-height:1.35 !important; text-align:center !important; }} '
        f'}} '
        f'</style>',
        unsafe_allow_html=True,
    )
    with st.container(key=_tile_key):
        st.markdown(preview_html, unsafe_allow_html=True)
        with st.container(key=_cta_key):
            st.markdown(f'<div class="{_text_class}">{cta_text}</div>', unsafe_allow_html=True)
            if st.button(button_label, key=f"{key_prefix}_landing_cta_btn"):
                st.session_state["login_prefill_mode"] = "Sign Up"
                st.switch_page(login_page)


def _uniform_section_header_html(title: str, icon_name: str, is_first: bool = False, action_html: str = "") -> str:
    """
    HET ene, universele sectiekop-patroon voor Today, My Portfolio en
    Discover -- groene, ALL-CAPS titel + een flinterdunne lijn die STRAK
    tegen de tekst aansluit.

    UITSLUITEND <div>/<span>-tags -- GEEN <h2> en GEEN <hr> meer. Door de
    hele rest van deze app heen is ELK stukje tekst/lijn dat met een
    <div> of <span> werd gestyled altijd probleemloos gegaan; ELK stukje
    dat een semantische tag gebruikte (<h2>, <hr>) gaf herhaaldelijk
    onverklaarbare afwijkingen (verkeerde marges, een verdwijnende lijn),
    zelfs met !important. Dat patroon is te consistent om toeval te zijn
    -- vermoedelijk heeft Streamlit's eigen thema specifieke, moeilijk te
    overschrijven basisstyling op dat soort semantische tags. Nu volledig
    vermeden: titel en icoon zijn platte <span>-elementen, de lijn is een
    platte <div>.

    Royale bovenmarge op de HELE container (mt-10 desktop / mt-8 mobiel,
    via de EENMALIG, globaal gedefinieerde .hesty-section-gap-klasse in
    de hoofd-stylesheet) zorgt voor een duidelijke afstand t.o.v. het
    EINDE van de vorige sectie; weggelaten bij de EERSTE sectie op een
    pagina.

    'action_html' (optioneel) is een stukje kant-en-klare HTML (meestal
    1 subtiele <a class="inline-link">-link) dat rechtsboven verschijnt,
    op dezelfde hoogte als de titel.
    """
    gap_class = "hesty-section-gap" if not is_first else ""
    outer_class = f' class="{gap_class}"' if gap_class else ""
    return (
        f'<div{outer_class}>'
        f'<div style="width:100%; margin:0; padding:0;">'
        f'<div style="display:flex; align-items:center; justify-content:space-between; gap:0.75rem; flex-wrap:wrap; margin:0; padding:0;">'
        f'<div style="display:flex; align-items:center; margin:0; padding:0;">'
        f'<span style="font-size:18px; color:#1FAE96; margin-right:0.5rem;" class="material-symbols-outlined">{icon_name}</span>'
        f'<span style="font-weight:700; color:#F1F5F9; text-transform:uppercase; letter-spacing:0.05em; '
        f'font-size:1rem;" class="hesty-section-title-text">{title}</span>'
        f'</div>'
        f'{action_html}'
        f'</div>'
        f'<div style="width:100%; height:1px; border-bottom:1px solid rgba(255,255,255,0.05); margin-top:6px; margin-bottom:18px; padding:0;"></div>'
        f'</div>'
        f'</div>'
    )


def _flowing_section_header_html(title: str, icon_name: str, is_first: bool = False) -> str:
    """
    Kop voor een sectie die NIET meer in een st.expander() zit (onderdeel
    van de bredere herstructurering naar 1 doorscrollende pagina i.p.v.
    losse uitklapvakken). Zonder de rand die een expander vroeger gaf,
    moet iets anders het 'hier begint iets nieuws'-signaal geven -- een
    duidelijke scheidingslijn erboven (weggelaten bij de EERSTE sectie op
    een pagina, want daar is geen vorig blok om van te scheiden) + een
    iets groter, steviger lettertype dan een gewone st.markdown("**...**").
    """
    divider_html = "" if is_first else '<div style="height:1px; background:rgba(137,146,163,0.15); margin:1.75rem 0 1.1rem 0;"></div>'
    return (
        f'{divider_html}'
        f'<div style="display:flex; align-items:center; gap:0.55rem; margin-bottom:0.3rem;">'
        f'{_icon_span(icon_name, size_px=19, color="#1FAE96")}'
        f'<span style="font-weight:700; font-size:1.1rem; color:#EAEDF1;">{title}</span></div>'
    )



def _today_metric_tile_html(label: str, icon_name: str, value_text: str, color: str, bg: str, border: str,
                             footer_text: str = None, value_color: str = None) -> str:
    """
    Zelfstandige, kleur-meebewegende tegel voor de 'Your Portfolio Today'-
    rij -- exact dezelfde visuele taal (rgba-achtergrond + rand + 12px
    afronding, groen/rood afhankelijk van de waarde) als de tegels in de
    Stress-Test's Systemic Risk Correlation Matrix (_stress_tile_style()),
    zodat de hele site 1 consistent 'tegel'-idioom gebruikt voor elke
    losse, op-zichzelf-staande metric i.p.v. kale tekst met een dunne
    scheidslijn ernaast.
    """
    footer_html = (
        f'<div style="font-size:0.68rem; color:#94A3B8; margin-top:6px; '
        f'font-family:\'Inter\', sans-serif !important;">{footer_text}</div>'
        if footer_text else ""
    )
    return (
        f'<div style="background:{bg}; border:1px solid {border}; border-radius:12px; padding:1rem 1.1rem; '
        f'transition:all 0.3s ease; height:100%; box-sizing:border-box;">'
        f'<div style="display:flex; align-items:center; gap:0.35rem;">'
        f'{_icon_span(icon_name, size_px=13, color=color)}'
        f'<span style="font-size:0.62rem; color:#8992A3; text-transform:uppercase; letter-spacing:0.1em; '
        f'font-weight:700; font-family:\'Inter\', sans-serif !important;">{label}</span>'
        f'</div>'
        f'<div style="font-size:1.55rem; font-weight:800; color:{value_color or color}; margin-top:6px; '
        f'line-height:1.1; font-family:\'Inter\', sans-serif !important; '
        f'font-variant-numeric: tabular-nums;">{value_text}</div>'
        f'{footer_html}'
        f'</div>'
    )


def _portfolio_mover_tile_html(label: str, icon_name: str, asset_name: str, pct: float, weight_pct: float, color: str) -> str:
    """
    Best/Worst-kolom voor 'Your Portfolio Today'. GEEN eigen kaart/
    achtergrond/rand meer -- pure, lichte content binnen een kolom; de
    scheiding tussen de kolommen komt van dunne verticale lijnen op de
    buitenste 3-koloms flex-container (zie de aanroep in render_today()),
    niet van losse omlijnde kaarten.

    Asset-naam ALTIJD in hoofdletters (expliciete keuze -- consistente,
    strakke ALL-CAPS-uitstraling i.p.v. titel-casing), groter en in een
    lichter grijs (#CBD5E1) dan de overige metadata, voor betere
    leesbaarheid. align-items:flex-start op de kolom zelf zorgt dat alle
    3 kolommen bovenaan uitlijnen, ongeacht tekstlengte.
    """
    return (
        f'<div style="display:flex; flex-direction:column; align-items:flex-start; min-width:0;">'
        f'<div style="display:flex; align-items:center; gap:0.3rem;">'
        f'{_icon_span(icon_name, size_px=13, color=color)}'
        f'<span style="font-size:0.62rem; color:#8992A3; text-transform:uppercase; letter-spacing:0.1em; '
        f'font-weight:700; font-family:\'Inter\', sans-serif !important;">{label}</span>'
        f'</div>'
        f'<div style="font-size:1.55rem; font-weight:800; color:{color}; margin-top:5px; line-height:1.1; '
        f'font-family:\'Inter\', sans-serif !important; font-variant-numeric: tabular-nums;">{pct:+.1f}%</div>'
        f'<div style="font-size:0.88rem; color:#CBD5E1; font-weight:500; margin-top:6px; '
        f'font-family:\'Inter\', sans-serif !important; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; '
        f'max-width:100%;" title="{asset_name}">{asset_name.upper()}</div>'
        f'<div style="font-size:0.66rem; color:#8992A3; margin-top:4px; font-family:\'Inter\', sans-serif !important;">Weight: {weight_pct:.1f}%</div>'
        f'</div>'
    )


# Approximatieve marktgewicht-verdeling per sector (afgerond op de
# S&P 500-samenstelling resp. een grove EU-proxy) -- ALLEEN gebruikt om
# de blokken in de Global Sector Heatmap relatief te laten schalen
# ('marktimpact'). Geen live marktkapitalisatie-data (dat zou 11+ extra
# aanroepen per page-load betekenen) -- een periodiek bijgewerkte,
# benaderde verdeling volstaat voor dit doel.
# Gedempt fintech-kleurenpalet, SPECIFIEK voor Today's positieve/negatieve
# indicatoren (Tailwind emerald/rose i.p.v. de fellere jade/rood die de
# rest van de site gebruikt -- bewust ALLEEN hier toegepast, niet als
# vervanging van de site-brede --color-jade/--color-negative-variabelen,
# dus Discover/Portfolio/Analyze blijven ongewijzigd). Kaarten zelf
# houden een neutrale, donkere achtergrond (TODAY_CARD_BG) -- de kleur
# zit ALLEEN in de dunne rand (20% opacity, zoals Tailwind's /20) en de
# tekst, niet in een gekleurde gradient-achtergrond.
TODAY_POSITIVE_TEXT = "#34D399"      # Tailwind emerald-400
TODAY_POSITIVE_BORDER_RGB = "16,185,129"  # Tailwind emerald-500
TODAY_NEGATIVE_TEXT = "#FB7185"      # Tailwind rose-400
TODAY_NEGATIVE_BORDER_RGB = "244,63,94"   # Tailwind rose-500
TODAY_CARD_BG = "rgba(137,146,163,0.04)"

US_SECTOR_MARKET_WEIGHTS = {
    "Technology": 32, "Financials": 13, "Health Care": 10, "Consumer Discretionary": 10,
    "Communication Services": 9, "Industrials": 8, "Consumer Staples": 6, "Energy": 3,
    "Utilities": 2.5, "Real Estate": 2, "Materials": 2,
}
EU_SECTOR_MARKET_WEIGHTS = {
    "Banks": 16, "Health Care": 15, "Industrial Goods & Services": 14, "Automobiles & Parts": 10,
    "Food & Beverage": 10, "Oil & Gas": 8, "Technology": 8, "Utilities": 7,
    "Basic Resources": 6, "Telecommunications": 6,
}


def _get_portfolio_sector_names(holdings: list) -> set:
    """
    Geeft de set van (naar onze eigen sector-namen gemapte) GICS-sectoren
    terug waar de huidige holdings in zitten -- gebruikt om de heatmap-
    blokken te markeren die matchen met het portfolio van de gebruiker.
    Elke ticker-lookup valt individueel stil terug (geen crash bij 1
    ticker zonder sector-info).
    """
    sectors = set()
    for h in holdings:
        try:
            info = get_cached_ticker_info(h["ticker"])
            mapped = YFINANCE_SECTOR_TO_OURS.get(info.get("sector"))
            if mapped:
                sectors.add(mapped)
        except Exception:
            continue
    return sectors


def _sector_heatmap_tile_html(sector: str, return_pct: float, weight: float, is_portfolio_match: bool, discover_url: str) -> str:
    """
    1 blok in de Global Sector Heatmap-grid. Geen rand en geen neutrale
    achtergrond -- alleen een zeer zachte, performance-gebaseerde
    kleurtint (nooit hoger dan ~0.09 alpha) en het gekleurde percentage-
    cijfer zelf dragen de betekenis, net zo mat/gedempt als het rood/
    groen in de portfolio-sectie hierboven. Het hele blok is 1 klikbare
    link naar Discover's Sectors & Themes-subview.
    """
    if return_pct > 0:
        color = TODAY_POSITIVE_TEXT
        tint_rgb = TODAY_POSITIVE_BORDER_RGB
    elif return_pct < 0:
        color = TODAY_NEGATIVE_TEXT
        tint_rgb = TODAY_NEGATIVE_BORDER_RGB
    else:
        color = "#EAEDF1"
        tint_rgb = "137,146,163"

    # Zachte achtergrondtint schaalt licht mee met de GROOTTE van de
    # beweging (nauwelijks zichtbaar bij een kleine beweging, nog steeds
    # mat/gedempt bij een grote) -- puur ter ondersteuning, de tekstkleur
    # draagt het meeste gewicht.
    intensity = min(abs(return_pct) / 15.0, 1.0)
    bg_alpha = 0.03 + intensity * 0.06

    # Grote, impactvolle sectoren (marktgewicht >= 10%) krijgen 2 grid-
    # kolommen i.p.v. 1 -- een vaste col-span i.p.v. een variabele
    # flex-basis, zodat blokken nooit uitrekken om een onvolledige rij
    # te vullen (dat is precies wat CSS Grid, anders dan flexbox, van
    # nature al NIET doet: een onvolledige rij laat de resterende
    # kolommen gewoon leeg).
    col_span = 2 if weight >= 10 else 1

    # Kompas-icoon inline, links van de sectornaam -- kan nooit overlappen,
    # ongeacht blokbreedte. Naam mag wrappen i.p.v. worden afgekapt.
    compass_icon = (
        f'<span style="font-size:0.8rem; flex-shrink:0; line-height:1.25;" '
        f'title="Matches assets in your portfolio">🧭</span>'
        if is_portfolio_match else ""
    )

    return (
        f'<a href="{discover_url}" target="_self" style="text-decoration:none; '
        f'grid-column: span {col_span}; display:block; '
        f'background: rgba({tint_rgb},{bg_alpha:.3f}); border-radius: 10px; '
        f'padding: 0.7rem 0.8rem; min-height: 76px; box-sizing:border-box;">'
        f'<div style="display:flex; align-items:flex-start; gap:5px;">'
        f'{compass_icon}'
        f'<span style="font-size:0.78rem; font-weight:700; color:#EAEDF1; line-height:1.25; '
        f'white-space:normal; overflow-wrap:break-word;">{sector}</span>'
        f'</div>'
        f'<div style="font-size:1.05rem; font-weight:800; color:{color}; margin-top:4px;">{return_pct:+.1f}%</div>'
        f'</a>'
    )


def _render_sector_heatmap(rotation: list, weights: dict, portfolio_sectors: set, discover_url: str) -> None:
    """
    Rendert de sector-heatmap als een strak CSS Grid (4 kolommen op
    desktop, 2 op mobiel), gesorteerd op marktgewicht (grootste sector
    eerst) zodat de grote, brede (col-span-2) blokken bovenaan/links
    staan -- net als bij een echte treemap. Grid i.p.v. flex-wrap: een
    onvolledige laatste rij rekt hierdoor NIET uit om de pagina te
    vullen, de resterende ruimte blijft gewoon leeg.
    """
    sorted_items = sorted(
        rotation, key=lambda r: weights.get(r["sector"], 1), reverse=True,
    )
    tiles_html = "".join(
        _sector_heatmap_tile_html(
            r["sector"], r["return_pct"], weights.get(r["sector"], 1),
            r["sector"] in portfolio_sectors, discover_url,
        )
        for r in sorted_items
    )
    st.markdown(
        '<style>.hesty-sector-grid{display:grid; grid-template-columns:repeat(4, 1fr); gap:0.6rem;} '
        '@media (max-width:768px){.hesty-sector-grid{grid-template-columns:repeat(2, 1fr);}}</style>'
        f'<div class="hesty-sector-grid">{tiles_html}</div>',
        unsafe_allow_html=True,
    )


def _insight_dismiss_button_html(insight_id: str) -> str:
    """
    Kleine '×'-dismissknop rechtsboven een Insight-kolom. De klik zelf
    werkt via een gewoon onclick-attribuut -- dat WORDT uitgevoerd, ook
    via st.markdown(); alleen losse <script>-tags worden genegeerd (zie
    streamlit_css_lessen.md #1). Verbergt de kolom direct EN schrijft een
    tijdstempel naar localStorage (5 dagen geldig, voorkomt alert
    fatigue). Het HERtoepassen van een eerdere dismiss bij de
    eerstvolgende page-load/Streamlit-rerun gebeurt in
    _render_insight_dismiss_autohide_script().
    """
    return (
        f"<span onclick=\"window.localStorage.setItem('hesty_dismissed_insight_{insight_id}', "
        f"Date.now().toString()); this.closest('[data-insight-col]').style.display='none';\" "
        f'style="position:absolute; top:0; right:2px; cursor:pointer; color:#8992A3; '
        f'font-size:0.95rem; line-height:1; opacity:0.5; transition:opacity 0.15s;" '
        f'onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.5" '
        f'title="Dismiss for 5 days">&times;</span>'
    )


def _render_insight_dismiss_autohide_script() -> None:
    """
    Verbergt bij page-load/rerun automatisch elke Insight-kolom die de
    afgelopen 5 dagen al gedismissed is. De klik zelf (zie
    _insight_dismiss_button_html) lost alleen de HUIDIGE render op --
    bij de eerstvolgende Streamlit-rerun (bv. door een widget elders op
    de pagina) wordt de hele 3-koloms-HTML opnieuw vanaf 0 opgebouwd, dus
    moet een eerdere dismiss ELKE keer opnieuw toegepast worden.
    st.components.v1.html() + MutationObserver is de bevestigd werkende
    omweg hiervoor (streamlit_css_lessen.md #1): losse <script>-tags in
    st.markdown() worden nooit uitgevoerd, dit wel (draait in een eigen
    iframe, bereikt de echte pagina via window.parent.document).
    """
    components.html(
        """
        <script>
        function hestyApplyDismissedInsights() {
            var doc = window.parent.document;
            var now = Date.now();
            var FIVE_DAYS_MS = 5 * 24 * 60 * 60 * 1000;
            doc.querySelectorAll('[data-insight-col]').forEach(function(el) {
                var id = el.getAttribute('data-insight-col');
                var key = 'hesty_dismissed_insight_' + id;
                var stored = window.parent.localStorage.getItem(key);
                if (stored) {
                    var dismissedAt = parseInt(stored, 10);
                    if (!isNaN(dismissedAt) && (now - dismissedAt) < FIVE_DAYS_MS) {
                        el.style.display = 'none';
                    } else {
                        window.parent.localStorage.removeItem(key);
                    }
                }
            });
        }
        hestyApplyDismissedInsights();
        new MutationObserver(hestyApplyDismissedInsights).observe(window.parent.document.body, {childList: true, subtree: true});
        </script>
        """,
        height=0,
    )


def _session_cached(cache_key: str, ttl_seconds: int, compute_fn):
    """
    Simpele session-state-cache met TTL. Voorkomt dat een Streamlit-
    rerun die eigenlijk alleen een st.dialog moet openen (bv. een klik
    op een Story-cirkel) alle dure netwerk-/database-aanroepen op Today
    OPNIEUW uitvoert -- Streamlit herlaadt bij ELKE widget-interactie
    het hele scriptpagina van boven naar beneden, dus zonder deze cache
    zou ook alles wat AL berekend was verderop in de pagina (marktdata,
    sector-heatmap, de hele radar-opbouw) telkens opnieuw draaien. Dat
    was de oorzaak van de ~10 seconden laadtijd bij elke Story-klik.
    'compute_fn' wordt alleen aangeroepen als er nog geen (verse) waarde
    in st.session_state staat.
    """
    now = datetime.now(timezone.utc)
    cached = st.session_state.get(cache_key)
    if cached is not None and (now - cached["computed_at"]).total_seconds() < ttl_seconds:
        return cached["value"]
    value = compute_fn()
    st.session_state[cache_key] = {"value": value, "computed_at": now}
    return value


def _rebalance_trigger_card_html(suggestion: dict, currency_symbol: str) -> str:
    """
    Herbalanceer-trigger als kolom-content (Insights staat weer naast
    elkaar in kolommen, net als 'Your Portfolio Today' -- maar BEWUST
    ZONDER verticale scheidslijnen en zonder kaart-achtergrond/-rand,
    zodat het meteen visueel verschilt van het portfolio-blok erboven).

    Het hoofdcijfer is NEUTRAAL gekleurd (het site-brede lichte
    tekst-wit, #EAEDF1) i.p.v. rood/groen -- dit is een doel-afwijking,
    geen dagrendement, en zou anders verward kunnen worden met winst/
    verlies. '-'/'below target' vs '+'/'above target' blijft het
    onderscheid duidelijk maken.
    """
    color = "#EAEDF1"
    insight_id = f"rebalance-{suggestion['ticker']}"
    if suggestion["action"] == "buy":
        sign = "-"
        target_label = "below target"
        context = "Consider pointing your next DCA at it."
    else:
        sign = "+"
        target_label = "above target"
        context = f'{suggestion["current_pct"]:.1f}% vs {suggestion["target_pct"]:.1f}% target.'
    return (
        f'<div data-insight-col="{insight_id}" style="position:relative; padding-right:26px;">'
        f'{_insight_dismiss_button_html(insight_id)}'
        f'<div style="display:flex; align-items:center; gap:0.3rem;">'
        f'{_icon_span("balance", size_px=13, color="#8992A3")}'
        f'<span style="font-size:0.62rem; color:#8992A3; text-transform:uppercase; letter-spacing:0.1em; '
        f'font-weight:700; font-family:\'Inter\', sans-serif !important;">Rebalance trigger</span>'
        f'</div>'
        f'<div style="font-size:1.65rem; font-weight:800; color:{color}; margin-top:6px; line-height:1.1; '
        f'font-family:\'Inter\', sans-serif !important; font-variant-numeric: tabular-nums;">'
        f'{sign}{abs(suggestion["diff_pct"]):.1f}% <span style="font-size:0.62rem; font-weight:700; '
        f'color:#8992A3; text-transform:none; letter-spacing:0;">{target_label}</span></div>'
        f'<div style="font-size:0.85rem; color:#CBD5E1; font-weight:600; margin-top:10px; '
        f'font-family:\'Inter\', sans-serif !important; white-space:normal; overflow-wrap:break-word;">'
        f'{suggestion["naam"].upper()}</div>'
        f'<div style="font-size:0.7rem; color:#64748B; margin-top:3px; font-family:\'Inter\', sans-serif !important;">'
        f'{context}</div>'
        f'</div>'
    )


def _watchlist_snack_card_html(alert: dict) -> str:
    """
    'Watchlist-Snack' als kolom-content -- zelfde structuur als
    _rebalance_trigger_card_html hierboven. Amber blijft hier de
    accentkleur (dit is een 'watch dit'-signaal, geen rendementscijfer,
    dus geen verwarring met winst/verlies).
    """
    color = "#E8A93C"
    insight_id = f"watchlist-{alert['ticker']}"
    return (
        f'<div data-insight-col="{insight_id}" style="position:relative; padding-right:26px;">'
        f'{_insight_dismiss_button_html(insight_id)}'
        f'<div style="display:flex; align-items:center; gap:0.3rem;">'
        f'{_icon_span("sell", size_px=13, color=color)}'
        f'<span style="font-size:0.62rem; color:{color}; text-transform:uppercase; letter-spacing:0.1em; '
        f'font-weight:700; font-family:\'Inter\', sans-serif !important;">Watchlist alert</span>'
        f'</div>'
        f'<div style="font-size:1.65rem; font-weight:800; color:{color}; margin-top:6px; line-height:1.1; '
        f'font-family:\'Inter\', sans-serif !important; font-variant-numeric: tabular-nums;">'
        f'{alert["distance_pct"]:.1f}% to go</div>'
        f'<div style="font-size:0.85rem; color:#CBD5E1; font-weight:600; margin-top:10px; '
        f'font-family:\'Inter\', sans-serif !important; white-space:normal; overflow-wrap:break-word;">'
        f'{alert["naam"].upper()}</div>'
        f'<div style="font-size:0.7rem; color:#64748B; margin-top:3px; font-family:\'Inter\', sans-serif !important;">'
        f'Now at {alert["current_price"]:.2f}, target {alert["alert_target_price"]:.2f}</div>'
        f'</div>'
    )


def _bucket_events_by_weekday(dated_items: list) -> dict:
    """
    Verdeelt een lijst van (date, icon_html, text)-tuples over Ma t/m Vr
    van de HUIDIGE week -- gedeelde bucketing-logica voor de Week-Agenda,
    zodat macro-events, ex-dividend-data en earnings-data allemaal op
    dezelfde manier onder de juiste dag terechtkomen. Events buiten deze
    week (zou niet moeten gebeuren bij de aanroepers hieronder, maar
    voor de zekerheid) worden stil genegeerd.

    Weekgrens (MOET exact gelijk lopen met radar_data.py's eigen
    berekening, anders vallen 's weekends alle events buiten de 0-4-
    range en verdwijnen ze stil): op zaterdag/zondag wijst 'de huidige
    week' via kale weekday()-aftrek naar de al-afgelopen maandag t/m
    vrijdag. In het weekend rollen we daarom door naar de AANKOMENDE
    maandag i.p.v. terug te kijken.
    """
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    today = datetime.now().date()
    if today.weekday() >= 5:  # 5 = zaterdag, 6 = zondag
        monday = today + timedelta(days=7 - today.weekday())
    else:
        monday = today - timedelta(days=today.weekday())
    buckets = {label: [] for label in labels}
    for item_date, icon_html, text in dated_items:
        offset = (item_date - monday).days
        if 0 <= offset <= 4:
            buckets[labels[offset]].append((icon_html, text))
    return buckets


def _week_agenda_html(buckets: dict) -> str:
    """
    Rendert de Week-Agenda in een eigen, zacht gevulde kaart (zelfde
    achtergrondtint als de 'Your Portfolio Today'-heldkolom, afgeronde
    hoeken, royale padding) -- laat de agenda als herkenbare tijdlijn
    boven de bulletins eronder uitspringen, die op de kale site-
    achtergrond blijven ademen. Daarbinnen: 5 gelijke, borderloze
    kolommen (Ma t/m Vr) naast elkaar op desktop, met dunne verticale
    scheidslijnen -- zelfde gap (1.75rem) en scheidslijnkleur/-dikte als
    het portfolio-blok hierboven. Op mobiel (<768px) stapelt de agenda
    verticaal -- 1 dag per rij met dunne HORIZONTALE scheidslijnen i.p.v.
    5 kolommen die op een smal scherm te krap/onleesbaar zouden worden.
    Via een vaste CSS-klasse + media query (i.p.v. inline styles, die
    niet responsief kunnen zijn). Catalysts staan als cleane bullet-regel
    in ALL-CAPS.
    """
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    today_label = labels[datetime.now().date().weekday()] if datetime.now().date().weekday() < 5 else None

    day_cols = []
    for i, label in enumerate(labels):
        is_today = label == today_label
        items = buckets.get(label, [])
        if items:
            items_html = "".join(
                f'<div style="display:flex; align-items:flex-start; gap:0.35rem; margin-top:0.5rem; '
                f'font-size:0.68rem; color:#94A3B8; line-height:1.4; text-transform:uppercase; letter-spacing:0.01em; '
                f'font-family:\'Inter\', sans-serif !important;">'
                f'<span style="flex-shrink:0; color:#8992A3;">&bull;</span><span>{text.upper()}</span></div>'
                for _icon_html, text in items
            )
        else:
            # 'NO EVENTS' i.p.v. een kale '--' -- zelfde ALL-CAPS/bullet-stijl
            # als een gevulde dag, zodat een lege dag niet visueel dood oogt.
            items_html = (
                '<div style="display:flex; align-items:flex-start; gap:0.35rem; margin-top:0.5rem; '
                'font-size:0.68rem; color:#94A3B8; line-height:1.4; text-transform:uppercase; letter-spacing:0.01em; '
                'font-family:\'Inter\', sans-serif !important;">'
                '<span style="flex-shrink:0; color:#8992A3;">&bull;</span><span>No events</span></div>'
            )

        label_color = "#1FAE96" if is_today else "#E2E8F0"
        day_class = "hesty-week-day hesty-week-day-last" if i == 4 else "hesty-week-day"
        day_cols.append(
            f'<div class="{day_class}">'
            f'<div style="font-size:1.05rem; font-weight:800; color:{label_color}; text-transform:uppercase; '
            f'letter-spacing:0.03em; font-family:\'Inter\', sans-serif !important;">{label}</div>'
            f'{items_html}'
            f'</div>'
        )
    return (
        '<style>'
        # Duidelijk zichtbare, matte achtergrondvulling (solide tint,
        # geen lage-opacity-overlay meer -- die viel bijna volledig weg
        # tegen de diepdonkere site-achtergrond) + een flinterdunne
        # rand voor extra definitie. Laat de week-agenda nu ECHT als
        # een aparte, herkenbare tijdlijn-tegel boven de bulletins
        # uitspringen.
        '.hesty-week-agenda-card { background:#151f32; border:1px solid rgba(148,163,184,0.12); '
        'border-radius:14px; padding:1.15rem 1.35rem; box-sizing:border-box; } '
        '.hesty-week-agenda { display:flex; align-items:flex-start; gap:1.75rem; } '
        '.hesty-week-day { flex:1; min-width:0; border-right:1px solid rgba(137,146,163,0.15); padding-right:1.75rem; } '
        '.hesty-week-day-last { border-right:none !important; padding-right:0 !important; } '
        '@media (max-width:768px) { '
        '.hesty-week-agenda { flex-direction:column; gap:0; } '
        '.hesty-week-day { width:100%; border-right:none !important; padding-right:0 !important; '
        'border-bottom:1px solid rgba(137,146,163,0.15); padding-bottom:0.75rem; margin-bottom:0.75rem; } '
        '.hesty-week-day-last { border-bottom:none !important; padding-bottom:0 !important; margin-bottom:0 !important; } '
        '} '
        '</style>'
        f'<div class="hesty-week-agenda-card"><div class="hesty-week-agenda">{"".join(day_cols)}</div></div>'
    )


def _portfolio_responsive_css() -> str:
    """
    Responsieve stylesheet voor 'Your Portfolio Today'. Desktop: kolom 1
    ('Your Portfolio Today' zelf) krijgt een eigen, zachte achtergrond-
    tegel (geen scheidslijn ernaast -- de ademruimte komt uit de
    flex-gap) zodat 'ie duidelijk de belangrijkste metric van de pagina
    is; kolom 2/3 (Best/Worst) blijven cleane tekstkolommen, gescheiden
    door een dunne verticale lijn. Mobiel (<640px): alle 3 gestapeld als
    losse kaartjes.
    """
    return (
        '<style>'
        '.hesty-portfolio-row { display:flex; align-items:flex-start; gap:1.75rem; } '
        '.hesty-portfolio-col { flex:1; min-width:0; border-right:1px solid rgba(137,146,163,0.15); '
        'padding-right:1.75rem; } '
        '.hesty-portfolio-col-last { border-right:none !important; padding-right:0 !important; } '
        '.hesty-portfolio-hero-col { flex:1; min-width:0; background:rgba(15,23,42,0.4); '
        'border-radius:14px; padding:1.15rem 1.35rem; box-sizing:border-box; } '
        '@media (max-width:768px) { '
        '.hesty-portfolio-row { flex-direction:column; gap:0.75rem; } '
        '.hesty-portfolio-col { width:100%; box-sizing:border-box; border-right:none !important; '
        'padding-right:0 !important; background:rgba(137,146,163,0.04); '
        'border:1px solid rgba(148,163,184,0.15); border-radius:12px; padding:0.85rem 1rem; } '
        '.hesty-portfolio-hero-col { width:100%; padding:1rem 1.15rem; } '
        '.hesty-portfolio-col-empty { display:none !important; } '
        '} '
        '</style>'
    )


def _position_row_html(ticker: str, name: str, value_text: str, pct_of_portfolio: float, mode: str,
                        currency_symbol: str = "$", logo_url: str = None,
                        day_change_pct: float = None, day_change_value: float = None,
                        current_price: float = None, avg_cost: float = None,
                        all_time_pct: float = None, all_time_pnl: float = None,
                        shares: float = None) -> str:
    """
    Positie-rij voor My Portfolio -- rendert BEIDE een compacte, gestapelde
    mobiele versie EN een brede, meerkoloms desktop-tabelversie (CSS
    beslist welke zichtbaar is via de .portfolio-row-mobile/-desktop-
    klassen in de hoofdstylesheet). Voorheen 1 vaste layout die op mobiel
    goed werkte maar op desktop een dunne strook met veel lege ruimte
    ertussen gaf -- de brede versie gebruikt de beschikbare breedte nu
    daadwerkelijk (aparte kolommen voor koers/verandering/waarde/
    allocatie i.p.v. alles samengeperst links+rechts).

    Schakelt tussen 'Daily' (dagrendement + huidige koers) en 'All-time'
    (rendement sinds aankoop, met Avg cost -> Current price -- alleen
    zinvol als er gelogde transacties zijn, anders een nette '-'-terugval).

    Logo links naast ticker/naam -- met een nette letter-cirkel-terugval
    als er geen logo beschikbaar is.

    Toont zowel het dollarbedrag als het percentage naast elkaar --
    'day_change_value'/'all_time_pnl' zijn de voorafberekende
    dollarbedragen, in dezelfde valuta als 'value_text'.
    """
    bar_pct = min(pct_of_portfolio, 100)

    if logo_url:
        logo_html = (
            f'<img src="{logo_url}" style="width:30px; height:30px; border-radius:8px; '
            f'object-fit:contain; background:#fff; padding:3px; flex-shrink:0;" />'
        )
    else:
        first_letter = (ticker[0] if ticker else "?").upper()
        logo_html = (
            f'<div style="width:30px; height:30px; border-radius:8px; background:rgba(137,146,163,0.15); '
            f'display:flex; align-items:center; justify-content:center; flex-shrink:0;">'
            f'<span style="color:#8992A3; font-weight:700; font-size:0.8rem;">{first_letter}</span></div>'
        )

    price_display = None
    if mode == "Daily":
        if day_change_pct is None:
            change_html = '<span style="color:#8992A3; font-weight:700;">-</span>'
        else:
            color = TODAY_POSITIVE_TEXT if day_change_pct >= 0 else TODAY_NEGATIVE_TEXT
            arrow = "&#9650;" if day_change_pct >= 0 else "&#9660;"
            value_part = (
                f'{currency_symbol}{abs(day_change_value):,.0f} ' if day_change_value is not None else ""
            )
            sign = "+" if day_change_pct >= 0 else "-"
            change_html = (
                f'<span style="color:{color}; font-weight:700; font-family:\'Inter\', sans-serif; font-variant-numeric: tabular-nums;">'
                f'{sign}{value_part}{day_change_pct:+.1f}% {arrow}</span>'
            )
        if current_price is not None:
            price_display = f'{currency_symbol}{current_price:,.2f}'
            detail_html = (
                f'<span style="color:#8992A3; font-family:\'Inter\', sans-serif; font-variant-numeric: tabular-nums; font-size:0.72rem; flex-shrink:0;">'
                f'&middot; {price_display}</span>'
            )
        else:
            detail_html = ""
    else:  # "All-time"
        if avg_cost is not None and current_price is not None and all_time_pct is not None:
            color = TODAY_POSITIVE_TEXT if all_time_pct >= 0 else TODAY_NEGATIVE_TEXT
            arrow = "&#9650;" if all_time_pct >= 0 else "&#9660;"
            value_part = (
                f'{currency_symbol}{abs(all_time_pnl):,.0f} ' if all_time_pnl is not None else ""
            )
            sign = "+" if all_time_pct >= 0 else "-"
            change_html = (
                f'<span style="color:{color}; font-weight:700; font-family:\'Inter\', sans-serif; font-variant-numeric: tabular-nums;">'
                f'{sign}{value_part}{all_time_pct:+.1f}% {arrow}</span>'
            )
            avg_cost_str = f'{currency_symbol}{avg_cost:,.2f}' if avg_cost is not None else "-"
            current_price_str_mobile = f'{currency_symbol}{current_price:,.2f}' if current_price is not None else "-"
            price_display = f'{avg_cost_str} &rarr; {current_price_str_mobile}'
            detail_html = (
                f'<span style="color:{color}; font-family:\'Inter\', sans-serif; font-variant-numeric: tabular-nums; font-size:0.72rem; flex-shrink:0;">'
                f'&middot; {price_display}</span>'
            )
        else:
            change_html = '<span style="color:#8992A3; font-weight:700;">-</span>'
            name = f"{name} (no logged purchase)"
            detail_html = ""
            price_display = "-"

    # Aantal stuks, als klein onderschrift onder de Value-cel -- 'shares:g'
    # verwijdert overbodige nullen (10 i.p.v. 10.000000, 0.085 voor
    # fractionele crypto-posities).
    shares_html = (
        f'<div style="color:#8992A3; font-size:0.72rem; margin-top:1px;">{shares:g} shares</div>'
        if shares is not None else ""
    )

    mobile_html = (
        f'<div class="portfolio-row-mobile" style="border-bottom:1px solid rgba(148,163,184,0.08); '
        f'padding:0.85rem 0.2rem; box-sizing:border-box; overflow:hidden;">'
        f'<div style="display:flex; align-items:center; gap:0.6rem; width:100%; min-width:0;">'
        f'{logo_html}'
        # Links: logo + ALL-CAPS naam (hoofdregel) + ticker/subnaam eronder
        # (gedempt, klein) -- vervangt de eerdere kriskras-opbouw (ticker
        # boven, naam onder, verspreid over 2 rijen samen met waarde/
        # verandering) door 1 nette, verticaal gestapelde linkerkolom.
        f'<div style="flex:1; min-width:0;">'
        f'<div style="font-weight:700; color:#EAEDF1; font-size:0.92rem; text-transform:uppercase; '
        f'letter-spacing:0.01em; font-family:\'Inter\', sans-serif !important; overflow:hidden; '
        f'text-overflow:ellipsis; white-space:nowrap;">{name.upper()}</div>'
        # Ticker + huidige koers compact op dezelfde regel -- 'detail_html'
        # (bevat de koers/Avg->Current-prijs) werd hierboven al berekend
        # maar stond nergens daadwerkelijk in de mobiele opmaak; dat was
        # de reden dat de koers niet zichtbaar was op mobiel.
        f'<div style="color:#8992A3; font-size:0.7rem; font-family:\'Inter\', sans-serif !important; '
        f'overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{ticker}{detail_html}</div>'
        f'</div>'
        # Rechts: alleen de 2 kerncijfers, gestapeld en rechts uitgelijnd --
        # waarde boven (groot), rendement/verandering eronder (klein).
        f'<div style="flex-shrink:0; text-align:right;">'
        f'<div style="font-weight:700; color:#EAEDF1; font-size:0.92rem; font-family:\'Inter\', sans-serif !important; '
        f'font-variant-numeric: tabular-nums; white-space:nowrap;">{value_text}</div>'
        f'<div style="font-size:0.72rem; white-space:nowrap;">{change_html}</div>'
        f'</div>'
        f'</div>'
        f'<div style="height:3px; background:rgba(137,146,163,0.1); border-radius:2px; margin-top:8px;">'
        f'<div style="height:100%; width:{bar_pct:.0f}%; background:rgba(31,174,150,0.55); border-radius:2px;"></div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )

    # Desktop: brede grid-tabel-weergave. Daily: Logo | Ticker+Naam | Koers |
    # Verandering | Waarde | Allocatie%+balk (6 kolommen). All-time: 1
    # kolom extra -- Cost price en Current price staan APART i.p.v.
    # samengeperst in 1 'X -> Y'-pijl, die eerder verwarrend bleek (kon
    # aangezien worden voor 1 enkel getal i.p.v. 2 losse prijzen).
    if mode == "Daily":
        desktop_html = (
            f'<div class="portfolio-row-desktop">'
            f'{logo_html}'
            f'<div style="min-width:0;">'
            f'<div style="font-weight:800; color:#EAEDF1; font-size:0.95rem;">{ticker}</div>'
            f'<div style="color:#64748B; font-size:0.7rem; text-transform:uppercase; letter-spacing:0.02em; '
            f'overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{name.upper()}</div>'
            f'</div>'
            f'<div style="color:#EAEDF1; font-family:\'Inter\', sans-serif; font-variant-numeric: tabular-nums; font-size:0.9rem; font-weight:700;">{price_display or "-"}</div>'
            f'<div style="font-size:0.85rem;">{change_html}</div>'
            f'<div>'
            f'<div style="color:#EAEDF1; font-weight:700; font-size:0.9rem; font-family:\'Inter\', sans-serif; font-variant-numeric: tabular-nums;">{value_text}</div>'
            f'{shares_html}'
            f'</div>'
            f'<div>'
            f'<div style="color:#8992A3; font-size:0.78rem; margin-bottom:3px;">{pct_of_portfolio:.1f}%</div>'
            f'<div style="height:3px; background:rgba(137,146,163,0.1); border-radius:2px;">'
            f'<div style="height:100%; width:{bar_pct:.0f}%; background:rgba(31,174,150,0.55); border-radius:2px;"></div>'
            f'</div>'
            f'</div>'
            f'</div>'
        )
    else:  # "All-time"
        cost_price_str = f'{currency_symbol}{avg_cost:,.2f}' if avg_cost is not None else "-"
        current_price_str = f'{currency_symbol}{current_price:,.2f}' if current_price is not None else "-"
        desktop_html = (
            f'<div class="portfolio-row-desktop-alltime">'
            f'{logo_html}'
            f'<div style="min-width:0;">'
            f'<div style="font-weight:800; color:#EAEDF1; font-size:0.95rem;">{ticker}</div>'
            f'<div style="color:#64748B; font-size:0.7rem; text-transform:uppercase; letter-spacing:0.02em; '
            f'overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{name.upper()}</div>'
            f'</div>'
            f'<div style="color:#EAEDF1; font-family:\'Inter\', sans-serif; font-variant-numeric: tabular-nums; font-size:0.9rem; font-weight:700;">{cost_price_str}</div>'
            f'<div style="color:#EAEDF1; font-family:\'Inter\', sans-serif; font-variant-numeric: tabular-nums; font-size:0.9rem; font-weight:700;">{current_price_str}</div>'
            f'<div style="font-size:0.85rem;">{change_html}</div>'
            f'<div>'
            f'<div style="color:#EAEDF1; font-weight:700; font-size:0.9rem; font-family:\'Inter\', sans-serif; font-variant-numeric: tabular-nums;">{value_text}</div>'
            f'{shares_html}'
            f'</div>'
            f'<div>'
            f'<div style="color:#8992A3; font-size:0.78rem; margin-bottom:3px;">{pct_of_portfolio:.1f}%</div>'
            f'<div style="height:3px; background:rgba(137,146,163,0.1); border-radius:2px;">'
            f'<div style="height:100%; width:{bar_pct:.0f}%; background:rgba(31,174,150,0.55); border-radius:2px;"></div>'
            f'</div>'
            f'</div>'
            f'</div>'
        )

    return mobile_html + desktop_html


def build_sector_rotation(region: str = "US", window_days: int = THEME_ROTATION_WINDOW_DAYS) -> list:
    """
    Rangschikt sectoren op trailing-rendement -- een simpel sector-rotatie-
    signaal (welke sectoren doen het momenteel relatief goed/slecht?).
    Sectoren waarvan de ETF geen data teruggeeft, worden gewoon overgeslagen
    (geen crash bij een enkele niet-beschikbare ticker).

    Gebruikt een EXACT 'N handelsdagen terug'-venster (i.p.v. yfinance's
    'period=1mo'-string) -- zodat dit getal exact overeenkomt met het
    laatste punt van build_sector_rotation_trend()'s grafiek (zelfde fix
    als bij build_theme_rotation()).
    """
    fetch_period = f"{window_days + 15}d"
    etfs = US_SECTOR_ETFS if region == "US" else EU_SECTOR_ETFS
    results = []
    for sector, ticker in etfs.items():
        try:
            hist = get_cached_ticker_history(ticker, period=fetch_period)
            if hist is None or hist.empty:
                continue
            # Zelfde soort probleem als eerder elders gevonden: de EERSTE of
            # LAATSTE rij kan een onvolledige koers (NaN) zijn (bv. een
            # 'vandaag'-bar die nog niet volledig is, vaker voorkomend bij
            # niet-Amerikaanse beurzen met andere handelstijden) -- pak de
            # eerste/laatste GELDIGE koers i.p.v. blindelings de rand-rijen,
            # anders wordt het rendement NaN (toont als 'None' in de tabel).
            valid_closes = hist["Close"].dropna()
            if len(valid_closes) > window_days:
                ret = (valid_closes.iloc[-1] / valid_closes.iloc[-1 - window_days] - 1) * 100
                results.append({"sector": sector, "ticker": ticker, "return_pct": round(ret, 2)})
        except Exception:
            continue

    results.sort(key=lambda x: x["return_pct"], reverse=True)
    return results


def _deep_dive_score_color(score: float) -> str:
    """
    Vertaalt een score (1-10) naar een betekenisvolle kleur -- groen
    (sterk), amber (gemiddeld), rood (onvoldoende). Grens voor rood ligt op
    5.5 (i.p.v. 5.0) -- consistent met de Nederlandse schoolcijfer-logica
    ('onvoldoende' begint onder een 5.5, niet onder een 5.0).
    """
    if score >= 7.5:
        return "#1FAE96"  # Hesty's signature teal/groen -- sterk
    elif score >= 5.5:
        return "#E8A93C"  # amber -- gemiddeld
    else:
        return "#E5484D"  # rood -- onvoldoende


def _compute_deep_dive_overall_score(version: dict):
    """
    Geeft het gemiddelde van de 5 ingevulde oordeel-scores terug (1-10),
    of None als er nog geen enkele score is ingevuld. Alle 5 scores staan
    in dezelfde richting (hoger = gunstiger voor een koopbeslissing),
    dus een simpel gemiddelde is hier zinvol.
    """
    score_fields = [
        "thesis_score", "management_score", "bear_case_score",
        "valuation_score", "catalysts_score", "technical_analysis_score",
    ]
    filled_scores = [version[f] for f in score_fields if version.get(f) is not None]
    if not filled_scores:
        return None
    return sum(filled_scores) / len(filled_scores)


def _render_deep_dive_version(version: dict, user_email: str):
    """
    Toont 1 versie van een deep-dive, met een 'Edit'-knop die overschakelt
    naar een voorgevuld bewerk-formulier -- voor het corrigeren van een
    typefout of het aanvullen van 1 onderdeel, ZONDER dat je alle andere
    velden opnieuw moet uitschrijven (dat zou nodig zijn als je in plaats
    daarvan een hele nieuwe versie zou toevoegen).
    """
    import database

    version_id = version["id"]
    edit_key = f"dd_editing_{version_id}"
    is_editing = st.session_state.get(edit_key, False)

    st.markdown(
        f'<div style="color:#F1F5F9; font-weight:700; font-size:0.85rem; margin-bottom:0.25rem;">'
        f'{version["created_at"][:10]} <span style="color:#64748B; font-weight:500;">&middot; {version["conclusion"].upper()}</span></div>',
        unsafe_allow_html=True,
    )

    overall_score = _compute_deep_dive_overall_score(version)
    if overall_score is not None:
        score_color = _deep_dive_score_color(overall_score)
        st.markdown(
            f'<span style="font-size:1.15rem; font-weight:800; color:{score_color};">{overall_score:.1f}/10</span> '
            f'<span style="font-size:0.68rem; color:#64748B; text-transform:uppercase; letter-spacing:0.03em;">overall score</span>',
            unsafe_allow_html=True,
        )

    ticker_currency_symbol = _currency_symbol_for_ticker(version["ticker"])

    # Alleen de prijs op het moment van deze deep-dive -- de rest
    # (52wk-range, market cap, sector, dividend, sector rotation) was
    # te veel info tegelijk gepropt en grotendeels overbodig; de prijs
    # is het enige dat echt nuttig is om later, bij het terugkijken,
    # nog te weten.
    if version.get("price_at_creation"):
        _price_date = (version.get("created_at") or "")[:10]
        _price_date_txt = f" (on {_price_date})" if _price_date else ""
        st.markdown(
            f'<div style="color:#64748B; font-size:0.7rem; margin-top:0.3rem;">'
            f'Price at time of this deep-dive: {ticker_currency_symbol}{version["price_at_creation"]:.2f}'
            f'{_price_date_txt}</div>',
            unsafe_allow_html=True,
        )

    def _dd_field_html(label: str, text: str) -> str:
        # Compacte, ALL-CAPS metadata-label + tekst eronder -- zelfde
        # stijl als de rest van het platform (bv. de input-labels op de
        # login/support-pagina's), i.p.v. Streamlit's **bold inline**-
        # markdown die vorige keer nog los/lomp oogde.
        return (
            f'<div style="margin-top:0.85rem;">'
            f'<div style="color:#64748B; font-size:0.65rem; font-weight:700; text-transform:uppercase; '
            f'letter-spacing:0.05em; margin-bottom:0.2rem;">{label}</div>'
            f'<div style="color:#CBD5E1; font-size:0.82rem; line-height:1.5;">{text}</div>'
            f'</div>'
        )

    if not is_editing:
        _view_tab_key = f"dd_view_active_subtab_{version_id}"
        _view_tab = st.pills(
            "Section", ["1-CLICK BRIEFING", "MY CONVICTION", "EXIT MATRIX"],
            default="1-CLICK BRIEFING", key=_view_tab_key, label_visibility="collapsed",
        )

        _dd_fields_html = ""
        if _view_tab == "1-CLICK BRIEFING":
            if version.get("business_overview"):
                _dd_fields_html += _dd_field_html("Business overview", version["business_overview"])
            if version.get("investment_thesis"):
                _dd_fields_html += _dd_field_html("Investment thesis", version["investment_thesis"])
            if version.get("bear_case"):
                _dd_fields_html += _dd_field_html("Core risks", version["bear_case"])
            if version.get("management_assessment"):
                _dd_fields_html += _dd_field_html("Management check", version["management_assessment"])
            if not _dd_fields_html:
                _dd_fields_html = _dd_field_html("Briefing", "Nothing logged yet -- generate an AI briefing or add this via Edit.")
        elif _view_tab == "MY CONVICTION":
            if version.get("technical_analysis"):
                _dd_fields_html += _dd_field_html("Technical notes", version["technical_analysis"])
            if version.get("catalysts"):
                _dd_fields_html += _dd_field_html("Catalysts notes", version["catalysts"])
            if version.get("position_sizing_plan"):
                _dd_fields_html += _dd_field_html("Position sizing plan", version["position_sizing_plan"])
            if version.get("management_score") is not None:
                _dd_fields_html += _dd_field_html("Management conviction", f"{version['management_score']:.1f} / 10")
            if version.get("bear_case_score") is not None:
                _dd_fields_html += _dd_field_html("Risk manageability", f"{version['bear_case_score']:.1f} / 10")
            if not _dd_fields_html:
                _dd_fields_html = _dd_field_html("Conviction", "Nothing logged yet -- add this via Edit.")
        elif _view_tab == "EXIT MATRIX":
            if version.get("thesis_score") is not None:
                _dd_fields_html += _dd_field_html("Conclusion score", f"{version['thesis_score']:.1f} / 10")
            if version.get("valuation_view"):
                _dd_fields_html += _dd_field_html("Valuation notes", version["valuation_view"])
            if version.get("valuation_score") is not None:
                _dd_fields_html += _dd_field_html("Valuation score", f"{version['valuation_score']:.1f} / 10")
            if version.get("interested_price"):
                _dd_fields_html += _dd_field_html("Interested from", f"{ticker_currency_symbol}{version['interested_price']:.2f}")
            _dd_fields_html += _dd_field_html("Status", version.get("conclusion", "Watch").upper())
            if version.get("sell_criteria"):
                _dd_fields_html += _dd_field_html("Sell criteria", version["sell_criteria"])
        st.markdown(_dd_fields_html, unsafe_allow_html=True)

        if _view_tab == "EXIT MATRIX" and (version.get("sell_trigger_price") or version.get("sell_trigger_date")):
            trigger_parts = []
            if version.get("sell_trigger_price"):
                trigger_parts.append(f"at {ticker_currency_symbol}{version['sell_trigger_price']:.2f}")
            if version.get("sell_trigger_date"):
                trigger_parts.append(f"by {version['sell_trigger_date']}")
            st.markdown(
                f'<div style="color:#64748B; font-size:0.7rem; margin-top:0.6rem;">Sell trigger set: '
                f'{" or ".join(trigger_parts)} -- you\'ll see this on Today once reached.</div>',
                unsafe_allow_html=True,
            )

        edit_col, delete_col = st.columns(2)
        with edit_col:
            if st.button("Edit", key=f"dd_edit_btn_{version_id}", use_container_width=True):
                st.session_state[edit_key] = True
                st.rerun()
        with delete_col:
            if st.button("Delete", key=f"dd_delete_{version_id}", use_container_width=True):
                database.delete_deep_dive(version_id, user_email)
                st.success("Version deleted.")
                st.rerun()
    else:
        _edit_tab_key = f"dd_edit_active_subtab_{version_id}"
        _edit_tab = st.pills(
            "Section", ["1-CLICK BRIEFING", "MY CONVICTION", "EXIT MATRIX"],
            default="1-CLICK BRIEFING", key=_edit_tab_key, label_visibility="collapsed",
        )

        if _edit_tab == "1-CLICK BRIEFING":
            _edit_ai_key = f"dd_edit_ai_briefing_wrap_{version_id}"
            st.markdown(
                f'<style>'
                f'.st-key-{_edit_ai_key} {{ margin-top:0.5rem !important; margin-bottom:1.5rem !important; }} '
                f'.st-key-{_edit_ai_key} button {{ '
                f'width:100% !important; background:rgba(2,6,23,0.8) !important; color:#a7f3d0 !important; '
                f'border:1px solid rgba(16,185,129,0.2) !important; font-size:0.72rem !important; '
                f'font-weight:700 !important; text-transform:uppercase !important; letter-spacing:0.15em !important; '
                f'padding:0.75rem 1.5rem !important; border-radius:12px !important; '
                f'box-shadow:0 8px 24px rgba(0,0,0,0.35) !important; transition:all 0.3s ease !important; }} '
                f'.st-key-{_edit_ai_key} button:hover {{ background:rgba(15,23,42,0.9) !important; '
                f'border-color:rgba(16,185,129,0.35) !important; }} '
                f'</style>',
                unsafe_allow_html=True,
            )
            with st.container(key=_edit_ai_key):
                if st.button("\u2726 Generate Anthropic Intelligence Briefing", key=f"dd_edit_ai_briefing_btn_{version_id}"):
                    if _run_ai_cockpit_briefing(
                        version["ticker"], version.get("naam", version["ticker"]), user_email,
                        field_prefix="dd_edit", key_suffix=f"_{version_id}",
                    ):
                        # Blijft in de bewerk-modus staan (edit_key blijft True)
                        # -- geen sprong terug naar de alleen-lezen weergave.
                        st.rerun()

            # Zelfde 'GEVONDEN BUG' als in het Add New-formulier: zonder de
            # '_committed'-mirror hieronder verwijdert Streamlit deze
            # tekstvelden uit session_state zodra je naar een andere tab
            # navigeert, waarna 'Save changes' stilletjes NULL zou
            # opslaan (en zo de oorspronkelijke, WEL opgeslagen tekst zou
            # overschrijven) voor elk veld dat niet op Exit Matrix staat.
            edit_business = st.text_area(
                "Business overview",
                value=st.session_state.get(f"dd_edit_business_committed_{version_id}", version.get("business_overview") or ""),
                key=f"dd_edit_business_{version_id}", height=90,
            )
            st.session_state[f"dd_edit_business_committed_{version_id}"] = edit_business

            edit_thesis = st.text_area(
                "Investment thesis",
                value=st.session_state.get(f"dd_edit_thesis_committed_{version_id}", version.get("investment_thesis") or ""),
                key=f"dd_edit_thesis_{version_id}", height=90,
            )
            st.session_state[f"dd_edit_thesis_committed_{version_id}"] = edit_thesis

            edit_bear = st.text_area(
                "Core risks",
                value=st.session_state.get(f"dd_edit_bear_committed_{version_id}", version.get("bear_case") or ""),
                key=f"dd_edit_bear_{version_id}", height=90,
            )
            st.session_state[f"dd_edit_bear_committed_{version_id}"] = edit_bear
            _dd_slider_value_html(f"dd_edit_bear_score_{version_id}")
            edit_bear_score = st.slider(
                "Risk score", 1.0, 10.0,
                st.session_state.get(f"dd_edit_bear_score_committed_{version_id}", float(version.get("bear_case_score") or 5)),
                step=0.5, key=f"dd_edit_bear_score_{version_id}", label_visibility="collapsed",
            )
            st.session_state[f"dd_edit_bear_score_committed_{version_id}"] = edit_bear_score

            edit_management = st.text_area(
                "Management check",
                value=st.session_state.get(f"dd_edit_management_committed_{version_id}", version.get("management_assessment") or ""),
                key=f"dd_edit_management_{version_id}", height=90,
            )
            st.session_state[f"dd_edit_management_committed_{version_id}"] = edit_management
            _dd_slider_value_html(f"dd_edit_management_score_{version_id}")
            edit_management_score = st.slider(
                "Management score", 1.0, 10.0,
                st.session_state.get(f"dd_edit_management_score_committed_{version_id}", float(version.get("management_score") or 5)),
                step=0.5, key=f"dd_edit_management_score_{version_id}", label_visibility="collapsed",
            )
            st.session_state[f"dd_edit_management_score_committed_{version_id}"] = edit_management_score

        elif _edit_tab == "MY CONVICTION":
            edit_technical_analysis = st.text_area(
                "Technical notes",
                value=st.session_state.get(f"dd_edit_ta_committed_{version_id}", version.get("technical_analysis") or ""),
                key=f"dd_edit_ta_{version_id}", height=90,
            )
            st.session_state[f"dd_edit_ta_committed_{version_id}"] = edit_technical_analysis
            _dd_slider_value_html(f"dd_edit_ta_score_{version_id}")
            edit_technical_analysis_score = st.slider(
                "Technical score", 1.0, 10.0,
                st.session_state.get(f"dd_edit_ta_score_committed_{version_id}", float(version.get("technical_analysis_score") or 5)),
                step=0.5, key=f"dd_edit_ta_score_{version_id}", label_visibility="collapsed",
            )
            st.session_state[f"dd_edit_ta_score_committed_{version_id}"] = edit_technical_analysis_score

            edit_catalysts = st.text_area(
                "Catalysts notes",
                value=st.session_state.get(f"dd_edit_catalysts_committed_{version_id}", version.get("catalysts") or ""),
                key=f"dd_edit_catalysts_{version_id}", height=90,
            )
            st.session_state[f"dd_edit_catalysts_committed_{version_id}"] = edit_catalysts
            _dd_slider_value_html(f"dd_edit_catalysts_score_{version_id}")
            edit_catalysts_score = st.slider(
                "Catalysts score", 1.0, 10.0,
                st.session_state.get(f"dd_edit_catalysts_score_committed_{version_id}", float(version.get("catalysts_score") or 5)),
                step=0.5, key=f"dd_edit_catalysts_score_{version_id}", label_visibility="collapsed",
            )
            st.session_state[f"dd_edit_catalysts_score_committed_{version_id}"] = edit_catalysts_score

            edit_sizing = st.text_area(
                "Position sizing plan",
                value=st.session_state.get(f"dd_edit_sizing_committed_{version_id}", version.get("position_sizing_plan") or ""),
                key=f"dd_edit_sizing_{version_id}", height=90,
            )
            st.session_state[f"dd_edit_sizing_committed_{version_id}"] = edit_sizing

        elif _edit_tab == "EXIT MATRIX":
            # Conclusion is nu een NIET-aanpasbare, live berekende score
            # -- het gemiddelde van de 5 andere schuifjes. Alleen
            # indirect te veranderen door die andere schuifjes te
            # verschuiven, niet rechtstreeks. Zelfde 'thesis_score'-veld
            # onder water, hier groot gepresenteerd.
            _edit_conclusion_inputs = [
                st.session_state.get(f"dd_edit_management_score_committed_{version_id}", float(version.get("management_score") or 5)),
                st.session_state.get(f"dd_edit_bear_score_committed_{version_id}", float(version.get("bear_case_score") or 5)),
                st.session_state.get(f"dd_edit_valuation_score_committed_{version_id}", float(version.get("valuation_score") or 5)),
                st.session_state.get(f"dd_edit_catalysts_score_committed_{version_id}", float(version.get("catalysts_score") or 5)),
                st.session_state.get(f"dd_edit_ta_score_committed_{version_id}", float(version.get("technical_analysis_score") or 5)),
            ]
            edit_thesis_score = sum(_edit_conclusion_inputs) / len(_edit_conclusion_inputs)
            st.session_state[f"dd_edit_thesis_score_{version_id}"] = edit_thesis_score
            _dd_label("Conclusion (average of all scores)")
            st.markdown(
                f'<div style="text-align:center; margin-bottom:1rem;">'
                f'<span style="color:#34D399; font-weight:800; font-size:2.2rem;">'
                f'{edit_thesis_score:.1f}</span>'
                f'<span style="color:#64748B; font-size:0.85rem;"> / 10</span></div>',
                unsafe_allow_html=True,
            )

            edit_valuation = st.text_area("Valuation notes", value=version.get("valuation_view") or "", key=f"dd_edit_valuation_{version_id}", height=90)
            _dd_slider_value_html(f"dd_edit_valuation_score_{version_id}")
            edit_valuation_score = st.slider(
                "Valuation score", 1.0, 10.0,
                st.session_state.get(f"dd_edit_valuation_score_committed_{version_id}", float(version.get("valuation_score") or 5)),
                step=0.5, key=f"dd_edit_valuation_score_{version_id}", label_visibility="collapsed",
            )
            st.session_state[f"dd_edit_valuation_score_committed_{version_id}"] = edit_valuation_score

            _dd_label(f"Interested from price ({ticker_currency_symbol.strip()})")
            edit_interested_price = st.number_input(
                "Interested from price", min_value=0.0, step=0.01,
                value=float(version.get("interested_price") or 0.0), key=f"dd_edit_price_{version_id}",
                label_visibility="collapsed",
            )

            _dd_label("Watch / Buy / Pass status")
            conclusion_options = ["Watch", "Buy", "Pass"]
            current_conclusion_index = (
                conclusion_options.index(version["conclusion"]) if version.get("conclusion") in conclusion_options else 0
            )
            edit_conclusion = st.selectbox(
                "Conclusion", conclusion_options, index=current_conclusion_index,
                key=f"dd_edit_conclusion_{version_id}", label_visibility="collapsed",
            )

            edit_sell_criteria = st.text_area("Sell criteria", value=version.get("sell_criteria") or "", key=f"dd_edit_sell_{version_id}", height=90)

            _dd_label(f"Sell trigger price ({ticker_currency_symbol.strip()})")
            edit_sell_trigger_price = st.number_input(
                "Sell trigger price", min_value=0.0, step=0.01,
                value=float(version.get("sell_trigger_price") or 0.0), key=f"dd_edit_trigger_price_{version_id}",
                label_visibility="collapsed",
            )
            _dd_label("Sell by date")
            existing_trigger_date = version.get("sell_trigger_date")
            if existing_trigger_date and isinstance(existing_trigger_date, str):
                try:
                    existing_trigger_date = datetime.strptime(existing_trigger_date, "%Y-%m-%d").date()
                except Exception:
                    existing_trigger_date = None
            edit_sell_trigger_date = st.date_input(
                "Sell by date", value=existing_trigger_date, key=f"dd_edit_trigger_date_{version_id}",
                label_visibility="collapsed",
            )

        # Alle velden leven in session_state ongeacht welke tab actief
        # is (zelfde principe als het Add New-formulier), dus de save
        # hieronder pakt ze allemaal terug via de keys, niet via lokale
        # variabelen die alleen bestaan als hun tab net actief was.
        _ess = st.session_state

        def _dd_edit_goto_tab(tab_name: str) -> None:
            # Zelfde reden als bij het Add New-formulier: rechtstreeks
            # session_state[_edit_tab_key] zetten NA het tekenen van de
            # st.pills()-widget in dezelfde run geeft een
            # StreamlitWidgetAlreadyInstantiatedError -- via on_click
            # draait dit veilig, voor de volgende widgets worden getekend.
            st.session_state[_edit_tab_key] = tab_name

        _edit_next_key = f"dd_edit_next_wrap_{version_id}"
        st.markdown(
            f'<style>'
            f'.st-key-{_edit_next_key} {{ margin-top:1.5rem !important; }} '
            f'.st-key-{_edit_next_key} button {{ '
            f'width:100% !important; background:rgba(31,174,150,0.12) !important; color:#1FAE96 !important; '
            f'border:1px solid rgba(31,174,150,0.3) !important; font-weight:700 !important; font-size:0.85rem !important; '
            f'padding:0.7rem 0 !important; border-radius:12px !important; box-shadow:none !important; }} '
            f'.st-key-{_edit_next_key} button:hover {{ background:rgba(31,174,150,0.2) !important; }} '
            f'</style>',
            unsafe_allow_html=True,
        )
        if _edit_tab == "1-CLICK BRIEFING":
            with st.container(key=_edit_next_key):
                st.button(
                    "Next: My Conviction (2/3) \u2192", key=f"dd_edit_next_conviction_{version_id}",
                    use_container_width=True, on_click=_dd_edit_goto_tab, args=("MY CONVICTION",),
                )
            if st.button("Cancel", key=f"dd_cancel_edit_{version_id}", use_container_width=True):
                st.session_state[edit_key] = False
                st.rerun()
        elif _edit_tab == "MY CONVICTION":
            with st.container(key=_edit_next_key):
                st.button(
                    "Next: Exit Matrix (3/3) \u2192", key=f"dd_edit_next_exit_{version_id}",
                    use_container_width=True, on_click=_dd_edit_goto_tab, args=("EXIT MATRIX",),
                )
            if st.button("Cancel", key=f"dd_cancel_edit_{version_id}", use_container_width=True):
                st.session_state[edit_key] = False
                st.rerun()
        else:
            save_col, cancel_col = st.columns(2)
            with save_col:
                if st.button("Save changes", type="primary", key=f"dd_save_edit_{version_id}", use_container_width=True):
                    database.update_deep_dive(
                        version_id, user_email,
                        # '_committed' i.p.v. de rauwe widget-sleutel voor elk
                        # tekstveld dat OOK op een andere tab dan Exit Matrix
                        # kan staan -- zie de toelichting bij die velden
                        # hierboven (voorkomt dat Save stilletjes NULL opslaat
                        # voor een veld dat je op een eerdere tab invulde).
                        business_overview=_ess.get(f"dd_edit_business_committed_{version_id}") or None,
                        investment_thesis=_ess.get(f"dd_edit_thesis_committed_{version_id}") or None,
                        management_assessment=_ess.get(f"dd_edit_management_committed_{version_id}") or None,
                        bear_case=_ess.get(f"dd_edit_bear_committed_{version_id}") or None,
                        valuation_view=_ess.get(f"dd_edit_valuation_{version_id}") or None,
                        interested_price=_ess.get(f"dd_edit_price_{version_id}") or None,
                        catalysts=_ess.get(f"dd_edit_catalysts_committed_{version_id}") or None,
                        position_sizing_plan=_ess.get(f"dd_edit_sizing_committed_{version_id}") or None,
                        sell_criteria=_ess.get(f"dd_edit_sell_{version_id}") or None,
                        conclusion=_ess.get(f"dd_edit_conclusion_{version_id}", version.get("conclusion", "Watch")),
                        sell_trigger_price=_ess.get(f"dd_edit_trigger_price_{version_id}") or None,
                        sell_trigger_date=(
                            _ess[f"dd_edit_trigger_date_{version_id}"].isoformat()
                            if _ess.get(f"dd_edit_trigger_date_{version_id}") else None
                        ),
                        thesis_score=_ess.get(f"dd_edit_thesis_score_{version_id}", float(version.get("thesis_score") or 5)),
                        management_score=_ess.get(f"dd_edit_management_score_committed_{version_id}", float(version.get("management_score") or 5)),
                        bear_case_score=_ess.get(f"dd_edit_bear_score_committed_{version_id}", float(version.get("bear_case_score") or 5)),
                        valuation_score=_ess.get(f"dd_edit_valuation_score_committed_{version_id}", float(version.get("valuation_score") or 5)),
                        catalysts_score=_ess.get(f"dd_edit_catalysts_score_committed_{version_id}", float(version.get("catalysts_score") or 5)),
                        technical_analysis=_ess.get(f"dd_edit_ta_committed_{version_id}") or None,
                        technical_analysis_score=_ess.get(f"dd_edit_ta_score_committed_{version_id}", float(version.get("technical_analysis_score") or 5)),
                    )
                    st.session_state[edit_key] = False
                    st.success("Version updated.")
                    st.rerun()
            with cancel_col:
                if st.button("Cancel", key=f"dd_cancel_edit_{version_id}", use_container_width=True):
                    st.session_state[edit_key] = False
                    st.rerun()

    # Afbeeldingen uitsluitend onder 'My Conviction' tonen (voorheen
    # onvoorwaardelijk, op ELKE tab zichtbaar -- dat voelde willekeurig
    # en rommelig los van de rest van de indeling).
    _active_subtab_key = f"dd_edit_active_subtab_{version_id}" if is_editing else f"dd_view_active_subtab_{version_id}"
    if st.session_state.get(_active_subtab_key) == "MY CONVICTION":
        st.markdown("**Images**")
        existing_images = database.get_deep_dive_images(version_id)
        if existing_images:
            img_cols = st.columns(min(len(existing_images), 3))
            for i, img in enumerate(existing_images):
                with img_cols[i % len(img_cols)]:
                    st.image(img["image_url"], caption=img.get("caption") or None)
                    if st.button("Remove image", key=f"dd_img_delete_{img['id']}"):
                        database.delete_deep_dive_image(img["id"], user_email)
                        st.rerun()

        uploaded_image = st.file_uploader(
            "Add an image (chart, screenshot, etc.)", type=["png", "jpg", "jpeg"],
            key=f"dd_img_upload_{version_id}",
        )
        if uploaded_image is not None:
            image_caption = st.text_input("Caption (optional)", key=f"dd_img_caption_{version_id}")
            if st.button("Upload image", key=f"dd_img_upload_btn_{version_id}"):
                database.upload_deep_dive_image(
                    user_email, version_id, uploaded_image.getvalue(), uploaded_image.name,
                    uploaded_image.type, image_caption or None,
                )
                st.success("Image uploaded!")
                st.rerun()

    st.divider()


def get_deep_dive_triggers_hit(user_email: str, max_items: int = 5) -> list:
    """
    Checkt of een van je deep-dive-verkoop-triggers (prijs of datum) is
    bereikt -- gebruikt de MEEST RECENTE versie per ticker (je huidige
    kijk, niet een verouderde). De richting van een prijs-trigger wordt
    afgeleid uit de prijs-op-het-moment-van-opslaan (price_at_creation):
    staat de trigger HOGER dan dat, is het een winst-doel (trigger als de
    prijs OMHOOG naar dat niveau gaat); staat 'ie LAGER, is het een
    stop-loss (trigger als de prijs OMLAAG naar dat niveau gaat).

    Een GEBEURTENIS-trigger (vrije tekst in sell_criteria, bv. 'als ze 2
    kwartalen missen') wordt hier bewust NIET gecheckt -- dat kunnen we
    niet automatisch verifiëren, dus dat blijft een handmatig te checken
    herinnering op de Deep-dives-pagina zelf.
    """
    import database

    today = datetime.now().date()
    results = []
    entries = database.get_all_deep_dive_tickers(user_email)
    for entry in entries:
        ticker = entry["ticker"]
        naam = entry["naam"]

        sell_trigger_date = entry.get("sell_trigger_date")
        if sell_trigger_date:
            try:
                trigger_date = (
                    datetime.strptime(sell_trigger_date, "%Y-%m-%d").date()
                    if isinstance(sell_trigger_date, str) else sell_trigger_date
                )
                if trigger_date <= today:
                    results.append({
                        "ticker": ticker, "naam": naam, "type": "date",
                        "detail": f"reached your sell-by date ({sell_trigger_date})",
                    })
            except Exception:
                pass

        sell_trigger_price = entry.get("sell_trigger_price")
        if sell_trigger_price:
            try:
                info = get_cached_ticker_info(ticker)
                current_price = info.get("currentPrice") or info.get("regularMarketPrice")
                if current_price is None:
                    fallback_hist = get_cached_ticker_history(ticker, period="5d")
                    if fallback_hist is not None and not fallback_hist.empty:
                        valid_closes = fallback_hist["Close"].dropna()
                        if not valid_closes.empty:
                            current_price = float(valid_closes.iloc[-1])
                if current_price is not None:
                    trigger_currency_symbol = _currency_symbol_for_ticker(ticker)
                    price_at_creation = entry.get("price_at_creation")
                    is_take_profit = price_at_creation is None or sell_trigger_price >= price_at_creation
                    if is_take_profit and current_price >= sell_trigger_price:
                        results.append({
                            "ticker": ticker, "naam": naam, "type": "price",
                            "detail": f"hit your sell target of {trigger_currency_symbol}{sell_trigger_price:.2f} "
                                      f"(now {trigger_currency_symbol}{current_price:.2f})",
                        })
                    elif not is_take_profit and current_price <= sell_trigger_price:
                        results.append({
                            "ticker": ticker, "naam": naam, "type": "price",
                            "detail": f"hit your stop-loss of {trigger_currency_symbol}{sell_trigger_price:.2f} "
                                      f"(now {trigger_currency_symbol}{current_price:.2f})",
                        })
            except Exception:
                continue

    return results[:max_items]


def get_deep_dive_market_snapshot(ticker: str) -> dict:
    """
    Verzamelt automatisch marktdata voor een deep-dive, op het moment van
    opslaan -- wordt als 'foto op dat moment' bij die versie bewaard, zodat
    je later kan zien wat de marktsituatie was toen je die versie schreef
    (in plaats van steeds de HUIDIGE, inmiddels verouderde cijfers te tonen
    bij een oude versie).
    """
    snapshot = {
        "price_at_creation": None,
        "fifty_two_week_high_at_creation": None,
        "fifty_two_week_low_at_creation": None,
        "market_cap_at_creation": None,
        "sector_at_creation": None,
        "dividend_yield_at_creation": None,
        "in_own_signals_at_creation": None,
        "sector_rotation_pct_at_creation": None,
    }
    try:
        info = get_cached_ticker_info(ticker)
    except Exception:
        info = {}

    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if current_price is None:
        # Zelfde robuuste terugval als bij Performance/Dividend -- sommige
        # effecten missen deze velden in .info.
        try:
            fallback_hist = get_cached_ticker_history(ticker, period="5d")
            if fallback_hist is not None and not fallback_hist.empty:
                valid_closes = fallback_hist["Close"].dropna()
                if not valid_closes.empty:
                    current_price = float(valid_closes.iloc[-1])
        except Exception:
            pass

    snapshot["price_at_creation"] = current_price
    snapshot["fifty_two_week_high_at_creation"] = info.get("fiftyTwoWeekHigh")
    snapshot["fifty_two_week_low_at_creation"] = info.get("fiftyTwoWeekLow")
    snapshot["market_cap_at_creation"] = info.get("marketCap")
    sector = info.get("sector")
    snapshot["sector_at_creation"] = sector

    dividend_rate = get_annual_dividend_rate(ticker, info)
    if dividend_rate and current_price:
        snapshot["dividend_yield_at_creation"] = round(dividend_rate / current_price * 100, 2)

    # Kruisverband met je eigen signalen (Daily, Momentocrats, Snowballers, Rocket List)
    own_signals = []
    signal_files = {
        "Daily": "supertrend_signals_daily.csv",
        "Momentocrats": "supertrend_signals.csv",
        "Snowballers": "snowball_signals.csv",
        "Rocket List": "rocket_list_signals.csv",
    }
    for label, filename in signal_files.items():
        try:
            if os.path.exists(filename):
                df_signal = pd.read_csv(filename)
                if "ticker" in df_signal.columns and ticker in df_signal["ticker"].values:
                    own_signals.append(label)
        except Exception:
            continue
    snapshot["in_own_signals_at_creation"] = ", ".join(own_signals) if own_signals else None

    # Sector-rotatie-context: waar staat DEZE sector momenteel in de rangschikking?
    if sector:
        mapped_sector = YFINANCE_SECTOR_TO_OURS.get(sector)
        if mapped_sector:
            try:
                rotation = build_sector_rotation(region="US")
                match = next((r for r in rotation if r["sector"] == mapped_sector), None)
                if match:
                    snapshot["sector_rotation_pct_at_creation"] = match["return_pct"]
            except Exception:
                pass

    return snapshot


def _currency_symbol_for_ticker(ticker: str) -> str:
    """
    Geeft het juiste valutasymbool terug, gebaseerd op de valuta waarin
    het aandeel ZELF noteert (i.p.v. altijd standaard EUR te tonen) --
    belangrijk omdat een groot deel van de aankopen in USD is, maar niet
    alles (bv. Europese aandelen blijven gewoon EUR).
    """
    try:
        info = get_cached_ticker_info(ticker)
        currency = info.get("currency", "EUR")
    except Exception:
        currency = "EUR"
    symbol_map = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CHF": "CHF ", "CAD": "C$"}
    return symbol_map.get(currency, f"{currency} ")


def _guess_domain_from_name(name: str) -> str:
    """
    Gokt een domeinnaam op basis van de bedrijfsnaam -- terugval voor
    wanneer yfinance's 'website'-veld ontbreekt (een bekende, terugkerende
    onbetrouwbaarheid in yfinance's .info-dict, bevestigd in meerdere
    GitHub-issues over verdwijnende velden tussen versies). Simpele
    heuristiek: strip veelvoorkomende bedrijfssuffixen, haal spaties/
    leestekens weg, plak '.com' erachter. Niet perfect (werkt bv. niet
    voor crypto, die worden apart uitgesloten), maar beter dan helemaal
    geen logo.
    """
    if not name:
        return None
    suffixes = [
        ", Inc.", " Inc.", " Inc", ", Corporation", " Corporation", " Corp.",
        " Corp", ", Ltd.", " Ltd.", " Ltd", " PLC", " plc", " N.V.", " NV",
        " S.A.", " AG", " Co.", ", Co", " Company", " Holdings", " Holding",
        " Group", " Class A", " Class B",
    ]
    cleaned = name
    for suf in suffixes:
        cleaned = cleaned.replace(suf, "")
    cleaned = cleaned.strip().lower().replace(" ", "").replace(",", "").replace(".", "").replace("&", "")
    if not cleaned:
        return None
    return f"{cleaned}.com"


@st.cache_data(ttl=86400, show_spinner=False)
def custom_asset_logo_data_uri() -> str:
    """
    Vast, eigen 'logo' voor Custom Yield Assets (fractioneel vastgoed,
    vaste-inkomstenproducten e.d.) -- deze hebben geen echt bedrijfs-
    domein om een logo voor te gokken (get_company_logo_url() zou voor
    zo'n fake ticker toch niks bruikbaars vinden). Een simpel huisje-
    icoon, in Hestys' eigen emerald-kleur, als data-URI -- kan direct
    als 'logo_url' meegegeven worden aan dezelfde <img>-rendering als
    een echt logo, geen aparte weergave-tak nodig.
    """
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        '<circle cx="12" cy="12" r="12" fill="#101825"/>'
        '<path d="M12 5.5 L19 11 V18.5 H14.5 V13.5 H9.5 V18.5 H5 V11 Z" '
        'fill="none" stroke="#34D399" stroke-width="1.6" stroke-linejoin="round"/>'
        '</svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


@st.cache_data(ttl=86400, show_spinner=False)
def get_company_logo_url(ticker: str, company_name: str = None) -> str:
    """
    Geeft een logo-URL terug via Google's eigen, gratis favicon-dienst --
    geen aanmelding/API-sleutel nodig, en betrouwbaarder dan een kleine,
    losse gratis-dienst (Clearbit's gratis logo-API, ooit de standaardkeuze
    hiervoor, is per december 2025 gestopt te bestaan). Gebaseerd op het
    bedrijfsdomein uit yfinance's 'website'-veld -- met een terugval op
    een domein-gok uit de bedrijfsnaam, want 'website' bleek in de
    praktijk regelmatig te ontbreken (bekende yfinance-onbetrouwbaarheid).
    Crypto-tickers (bv. BTC-USD) krijgen een apart munt-icoon via de
    gratis cryptocurrency-icons-bibliotheek (geen bedrijfsdomein om te
    gokken, maar wel vaak een bekend munt-icoon beschikbaar). Geeft None
    terug als er helemaal geen logo te vinden is.

    'company_name' is een OPTIONELE, AL-BEKENDE bedrijfsnaam (bv. uit een
    eigen database-record) -- gebruikt als extra terugval wanneer
    yfinance's .info HELEMAAL leeg/onbereikbaar is (niet alleen het
    'website'-veld, maar ook 'shortName'/'longName' zelf). yfinance's
    .info-endpoint is namelijk aanzienlijk flakier dan .history() (vaker
    leeg/rate-limited) -- dus voor plekken waar de naam toch al bekend
    is (zoals deep-dives), is dit een veel betrouwbaardere bron dan
    volledig op yfinance's .info te vertrouwen.

    BELANGRIJK: de gegokte logo-URL wordt hier VOORAF (server-kant)
    daadwerkelijk opgehaald en gecontroleerd, in plaats van te
    vertrouwen op een client-side onerror-fallback in de HTML -- die
    laatste werkt namelijk NIET in Streamlit, want unsafe_allow_html
    saniteert de HTML met DOMPurify, dat standaard ALLE inline
    event-handlers (onerror, onclick, etc.) verwijdert. Zonder deze
    server-kant-check zou een verkeerd gegokt domein een kapot-plaatje-
    icoontje tonen i.p.v. netjes terug te vallen.

    24-uur gecached (i.p.v. de standaard 5 minuten van get_cached_ticker_info
    zelf) -- een logo verandert vrijwel nooit, en deze functie wordt nu ook
    gebruikt in My Portfolio's tabel (die bij ELK paginabezoek rendert), dus
    een lange cache voorkomt dat het paginabezoek zelf traag wordt. De
    verificatie-aanroep zelf gebeurt daardoor ook maar 1x per ticker per dag.
    """
    def _verify_logo_url(url: str) -> bool:
        """
        Haalt de URL daadwerkelijk op en controleert of 'ie een bruikbare
        afbeelding oplevert. Google's favicon-dienst geeft bij een niet-
        bestaand domein vaak een heel klein, generiek 'globe'-icoontje
        terug (i.p.v. een fout) -- een te klein bestand duidt dus op een
        mislukte gok, geen echt logo.
        """
        try:
            response = requests.get(url, timeout=3)
            if response.status_code != 200:
                return False
            if len(response.content) < 300:
                return False
            return True
        except Exception:
            return False

    try:
        info = get_cached_ticker_info(ticker)
        website = info.get("website")
        if website:
            domain = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
            candidate_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=256"
            if _verify_logo_url(candidate_url):
                return candidate_url

        # Terugval: geen 'website'-veld (of niet geverifieerd) --
        # crypto-achtige tickers (bv. BTC-USD, SOL-USD) hebben geen
        # zinvol bedrijfsdomein om te gokken, maar WEL vaak een bekend
        # munt-icoon. Probeer eerst de gratis, betrouwbare
        # cryptocurrency-icons-bibliotheek (500+ munten, via jsdelivr's
        # CDN) op basis van het munt-symbool, vóórdat we deze tickers
        # helemaal overslaan.
        ticker_suffix = ticker.rsplit("-", 1)[-1].upper() if "-" in ticker else ""
        if ticker_suffix in ("EUR", "USD", "GBP", "USDT", "USDC"):
            coin_symbol = ticker.rsplit("-", 1)[0].lower()
            crypto_icon_url = (
                f"https://cdn.jsdelivr.net/gh/spothq/cryptocurrency-icons@master/128/color/{coin_symbol}.png"
            )
            if _verify_logo_url(crypto_icon_url):
                return crypto_icon_url
            return None

        # Naam ophalen: eerst proberen via yfinance, met de ZELF-BEKENDE
        # company_name als terugval als .info leeg is.
        name = info.get("shortName") or info.get("longName") or company_name
        if not name:
            return None

        # Meerdere domein-varianten proberen, niet slechts 1 gok -- de
        # VOLLEDIGE naam ('Grab Holdings Limited' -> 'grabholdings.com')
        # klopt lang niet altijd (echt: grab.com); het EERSTE WOORD
        # alleen ('grab.com') is vaak een betere gok voor bedrijven met
        # generieke, beschrijvende extra woorden in hun officiele naam
        # (Holdings/Health/Technologies/Clean/etc.). Volledige naam eerst
        # geprobeerd (specifieker, dus minder kans op een TOEVALLIGE
        # match met een ander, bestaand bedrijf), eerste-woord als
        # terugval.
        candidate_domains = []
        full_guess = _guess_domain_from_name(name)
        if full_guess:
            candidate_domains.append(full_guess)
        first_word = name.split()[0] if name.split() else None
        if first_word:
            first_word_guess = _guess_domain_from_name(first_word)
            if first_word_guess and first_word_guess not in candidate_domains:
                candidate_domains.append(first_word_guess)

        for guessed_domain in candidate_domains:
            candidate_url = f"https://www.google.com/s2/favicons?domain={guessed_domain}&sz=256"
            if _verify_logo_url(candidate_url):
                return candidate_url
        return None
    except Exception:
        return None


def get_earnings_surprises_from_signals(max_items: int = 5, max_days_old: int = 21) -> list:
    """
    Licht signalen met een opvallende recente winst-verrassing uit de
    bestaande screener-CSV's (dagelijks + wekelijks) -- geen nieuwe
    data-ophaal nodig, dit zit al in de bestaande scores verwerkt.
    Alleen relevant tijdens 'earnings season' -- 21 dagen (~3 weken) dekt
    de kern van een kwartaal-rapportageperiode, zonder maanden later nog
    stale verrassingen te tonen (bedrijven rapporteren maar 1x per kwartaal).
    """
    results = []
    for csv_file in ["supertrend_signals_daily.csv", "supertrend_signals.csv"]:
        if not os.path.exists(csv_file):
            continue
        try:
            df = pd.read_csv(csv_file)
        except Exception:
            continue
        if "earnings_surprise_pct" not in df.columns:
            continue
        df_with_earnings = df[df["earnings_surprise_pct"].notna()]
        for _, row in df_with_earnings.iterrows():
            earnings_date = row.get("earnings_date")
            if pd.isna(earnings_date):
                continue
            try:
                days_old = (datetime.now().date() - pd.to_datetime(earnings_date).date()).days
            except Exception:
                continue
            if not (0 <= days_old <= max_days_old):
                continue
            results.append({
                "ticker": row["ticker"],
                "earnings_surprise_pct": row["earnings_surprise_pct"],
                "earnings_beat": row.get("earnings_beat"),
                "earnings_date": row.get("earnings_date"),
            })

    results.sort(key=lambda x: abs(x["earnings_surprise_pct"]), reverse=True)
    return results[:max_items]


# Handmatig bijgehouden kalender van de belangrijkste, maanden-vooruit-
# aangekondigde macro-events (FOMC + ECB-rentebesluiten). Bron: officiële
# Fed/ECB-kalenders. Bijwerken zodra een nieuw jaar bekend wordt gemaakt
# (meestal 1x per jaar, eind vorig jaar/begin dit jaar).
from macro_events import get_todays_macro_events


def get_upcoming_ex_dividend_dates(holdings: list, market_data: dict, days_ahead: int = 5, max_items: int = 3) -> list:
    """
    Checkt of een van je HUIDIGE posities binnen 'days_ahead' dagen
    ex-dividend gaat -- zelfde 'alleen daadwerkelijk toekomstige datums'-
    filtering als Analyze's Dividend-kaart (yfinance's exDividendDate is
    soms de meest recente, al-gepasseerde datum i.p.v. een toekomstige).

    'market_data' komt uit database.get_market_data_for_tickers() (de
    achtergrond-gesynchroniseerde tabel) -- valt netjes terug op een live
    aanroep voor een ticker die daar nog niet in staat.
    """
    today = datetime.now().date()
    results = []
    for h in holdings:
        ticker = h["ticker"]
        if ticker in market_data:
            ex_div_str = market_data[ticker].get("ex_dividend_date")
        else:
            # Terugval: ticker zit HELEMAAL niet in market_data (nog niet
            # gesynchroniseerd) -- live proberen. Zit de ticker er wel in,
            # maar is dit veld leeg, dan betekent dat 'geen dividend
            # bekend' (een geldig, gesynchroniseerd antwoord) -- geen live
            # aanroep nodig, dat zou hetzelfde resultaat gewoon herhalen.
            ex_div_str = None
            try:
                info = get_cached_ticker_info(ticker)
                ex_div_unix = info.get("exDividendDate")
                if ex_div_unix:
                    ex_div_str = pd.Timestamp(ex_div_unix, unit="s").date().isoformat()
            except Exception:
                pass
        if not ex_div_str:
            continue
        try:
            ex_div_date = pd.Timestamp(ex_div_str).date()
            days_until = (ex_div_date - today).days
            if 0 <= days_until <= days_ahead:
                results.append({"naam": h["naam"], "ticker": ticker,
                                 "ex_div_date": ex_div_date, "days_until": days_until})
        except Exception:
            continue
    results.sort(key=lambda r: r["days_until"])
    return results[:max_items]


def get_todays_portfolio_earnings(tracked_items: list, market_data: dict, max_items: int = 3) -> list:
    """
    Checkt of een van je posities/watchlist-items VANDAAG earnings rapporteert.

    'market_data' komt uit database.get_market_data_for_tickers() (de
    achtergrond-gesynchroniseerde tabel, 'next_earnings_date'-veld) --
    valt netjes terug op een live aanroep voor een ticker die daar nog
    niet in staat.
    """
    today = datetime.now().date()
    results = []
    for item in tracked_items:
        ticker = item["ticker"]
        try:
            if ticker in market_data:
                next_date_str = market_data[ticker].get("next_earnings_date")
                if next_date_str and pd.Timestamp(next_date_str).date() == today:
                    results.append({"naam": item["naam"], "ticker": ticker})
            else:
                # Terugval: ticker zit helemaal niet in market_data (nog
                # niet gesynchroniseerd) -- live proberen.
                dates_df = get_cached_earnings_dates(ticker, limit=8)
                if dates_df is None or dates_df.empty:
                    continue
                for earnings_date in dates_df.index:
                    if earnings_date.date() == today:
                        results.append({"naam": item["naam"], "ticker": ticker})
                        break
        except Exception:
            continue
        if len(results) >= max_items:
            break
    return results[:max_items]


def get_upcoming_portfolio_earnings(tracked_items: list, market_data: dict, days_ahead: int = 5, max_items: int = 3) -> list:
    """
    Checkt of een van je posities/watchlist-items binnen 'days_ahead' dagen
    earnings rapporteert (VANDAAG zelf niet meegeteld -- dat toont
    get_todays_portfolio_earnings al apart). Geeft een korte vooraankondiging,
    zodat je niet pas op de dag zelf verrast wordt.

    'market_data' komt uit database.get_market_data_for_tickers() -- valt
    netjes terug op een live aanroep voor een ticker die daar nog niet in
    staat.
    """
    today = datetime.now().date()
    results = []
    for item in tracked_items:
        ticker = item["ticker"]
        try:
            if ticker in market_data:
                next_date_str = market_data[ticker].get("next_earnings_date")
                if next_date_str:
                    earnings_date = pd.Timestamp(next_date_str).date()
                    days_until = (earnings_date - today).days
                    if 1 <= days_until <= days_ahead:
                        results.append({"naam": item["naam"], "ticker": ticker,
                                         "earnings_date": earnings_date, "days_until": days_until})
            else:
                # Terugval: ticker zit helemaal niet in market_data.
                dates_df = get_cached_earnings_dates(ticker, limit=8)
                if dates_df is None or dates_df.empty:
                    continue
                for earnings_date_ts in dates_df.index:
                    days_until = (earnings_date_ts.date() - today).days
                    if 1 <= days_until <= days_ahead:
                        results.append({"naam": item["naam"], "ticker": ticker,
                                         "earnings_date": earnings_date_ts.date(), "days_until": days_until})
                        break
        except Exception:
            continue
    results.sort(key=lambda r: r["days_until"])
    return results[:max_items]


def get_recent_earnings_surprises_for_tracked_items(tracked_items: list, market_data: dict, max_days_old: int = 7, max_items: int = 3) -> list:
    """
    Checkt of een van je posities/watchlist-items RECENT (binnen
    max_days_old dagen) earnings heeft gerapporteerd met een noemenswaardige
    winst-verrassing.

    'market_data' komt uit database.get_market_data_for_tickers() (de
    achtergrond-gesynchroniseerde tabel, 'last_earnings_date'/
    'last_earnings_surprise_pct'-velden) -- valt netjes terug op een live
    aanroep voor een ticker die daar nog niet in staat.

    Dit is bewust een ANDERE, directere bron dan de bestaande
    get_earnings_surprises_from_signals() (die leunt op de supertrend-
    signalen-CSV) -- die laatste toont een verrassing ALLEEN als de ticker
    toevallig OOK als supertrend-signaal is gemarkeerd, dus voor JOUW
    eigen posities specifiek kon een verrassing gemist worden als de
    ticker net niet aan de signaal-criteria voldeed. Deze functie werkt
    voor ELKE gevolgde ticker, ongeacht of 'ie ook een signaal is.
    """
    today = datetime.now().date()
    results = []
    for item in tracked_items:
        ticker = item["ticker"]
        try:
            if ticker in market_data:
                last_date_str = market_data[ticker].get("last_earnings_date")
                surprise_pct = market_data[ticker].get("last_earnings_surprise_pct")
                if last_date_str and surprise_pct is not None:
                    days_since = (today - pd.Timestamp(last_date_str).date()).days
                    if 0 <= days_since <= max_days_old:
                        results.append({
                            "naam": item["naam"], "ticker": ticker,
                            "earnings_date": pd.Timestamp(last_date_str).date(), "surprise_pct": float(surprise_pct),
                            "beat": surprise_pct >= 0,
                        })
            else:
                # Terugval: ticker zit helemaal niet in market_data.
                dates_df = get_cached_earnings_dates(ticker, limit=8)
                if dates_df is None or dates_df.empty or "Surprise(%)" not in dates_df.columns:
                    continue
                for earnings_date, row in dates_df.iterrows():
                    days_since = (today - earnings_date.date()).days
                    if not (0 <= days_since <= max_days_old):
                        continue
                    row_surprise = row.get("Surprise(%)")
                    if pd.isna(row_surprise):
                        continue
                    results.append({
                        "naam": item["naam"], "ticker": ticker,
                        "earnings_date": earnings_date.date(), "surprise_pct": float(row_surprise),
                        "beat": row_surprise >= 0,
                    })
                    break
        except Exception:
            continue
    results.sort(key=lambda r: abs(r["surprise_pct"]), reverse=True)
    return results[:max_items]


def get_52_week_records(holdings: list, market_data: dict, max_items: int = 3) -> list:
    """
    Checkt of een van je posities vandaag een nieuwe 52-weken-hoogte of
    -laagte heeft geraakt. yfinance's fiftyTwoWeekHigh/Low weerspiegelen
    het ROLLENDE 52-weken-record t/m de laatste koers -- als de huidige
    prijs daaraan gelijk is (of eroverheen), is vandaag het nieuwe record.

    'market_data' komt uit database.get_market_data_for_tickers() -- valt
    netjes terug op een live aanroep voor een ticker die daar nog niet in
    staat.
    """
    results = []
    for h in holdings:
        ticker = h["ticker"]
        if ticker in market_data:
            high_52wk = market_data[ticker].get("fifty_two_week_high")
            low_52wk = market_data[ticker].get("fifty_two_week_low")
            current_price = market_data[ticker].get("current_price")
        else:
            high_52wk = low_52wk = current_price = None

        if current_price is None:
            # Terugval: ticker zit helemaal niet in market_data, OF de
            # sync-rij mist toevallig current_price (zou niet moeten
            # voorkomen, maar current_price is te essentieel om zonder
            # verder te gaan) -- live proberen.
            try:
                info = get_cached_ticker_info(ticker)
                if high_52wk is None:
                    high_52wk = info.get("fiftyTwoWeekHigh")
                if low_52wk is None:
                    low_52wk = info.get("fiftyTwoWeekLow")
                current_price = info.get("currentPrice") or info.get("regularMarketPrice")
                if current_price is None:
                    fallback_hist = get_cached_ticker_history(ticker, period="5d")
                    if fallback_hist is not None and not fallback_hist.empty:
                        current_price = float(fallback_hist["Close"].iloc[-1])
            except Exception:
                continue
        if current_price is None:
            continue
        if high_52wk and current_price >= high_52wk:
            results.append({"naam": h["naam"], "ticker": ticker, "type": "high"})
        elif low_52wk and current_price <= low_52wk:
            results.append({"naam": h["naam"], "ticker": h["ticker"], "type": "low"})
    return results[:max_items]


def send_subscription_confirmation_email(email: str, confirmation_token: str, unsubscribe_token: str) -> None:
    """
    Stuurt de dubbele-opt-in-bevestigingsmail voor de niet-ingelogde
    e-mail-aanmelding, in dezelfde huisstijl (donkere header + teal-
    accent) als de bestaande dagelijkse/wekelijkse mails. Bevat ook
    meteen een uitschrijflink, zodat iemand die per ongeluk bevestigt
    niet hoeft te wachten op de eerste dagelijkse mail om zich weer af
    te melden.
    """
    confirm_url = f"https://hestys.streamlit.app/confirm?token={confirmation_token}"
    unsubscribe_url = f"https://hestys.streamlit.app/unsubscribe?token={unsubscribe_token}"
    text_body = (
        "Confirm your subscription to Hesty's Daily\n\n"
        "One more step: click the link below to confirm this is your email address.\n\n"
        f"{confirm_url}\n\n"
        "Didn't request this? You can safely ignore this email, or unsubscribe here:\n"
        f"{unsubscribe_url}\n\n"
        "-- Hesty's, your personal investment assistant"
    )
    html_body = f"""
    <div style="font-family: -apple-system, 'Segoe UI', Roboto, Arial, sans-serif; max-width: 600px; margin: 0 auto; background:#ffffff;">
        <div style="background:#101825; padding: 28px 24px; border-radius: 12px 12px 0 0;">
            <div style="color:#1FAE96; font-size:13px; font-weight:600; letter-spacing:1px; text-transform:uppercase;">Hesty's Daily</div>
            <div style="color:#EAEDF1; font-size:22px; font-weight:700; margin-top:4px;">Confirm your subscription</div>
        </div>
        <div style="padding: 24px; border: 1px solid #E5E8EC; border-top: none; border-radius: 0 0 12px 12px;">
            <p style="font-size:15px; color:#101825; line-height:1.5; margin-top:0;">
                One more step: click the button below to confirm this is your email address.
            </p>
            <p style="margin-top:20px;">
                <a href="{confirm_url}" style="background:#1FAE96; color:#ffffff; padding:12px 24px; border-radius:8px; text-decoration:none; font-weight:600; display:inline-block;">Confirm subscription</a>
            </p>
            <p style="margin-top:24px; font-size:13px; color:#9AA1AC;">
                Didn't request this? You can safely ignore this email, or
                <a href="{unsubscribe_url}" style="color:#9AA1AC;">unsubscribe here</a>.
            </p>
            <p style="margin-top:20px; font-size:14px; color:#101825; font-weight:600;">&mdash; Hesty's, your personal investment assistant</p>
        </div>
    </div>
    """
    send_email(
        subject="Confirm your subscription to Hesty's Daily",
        body_text=text_body, body_html=html_body, to_email=email,
    )


def get_top_news_for_tickers(holdings_and_watchlist: list, max_items: int = 3) -> list:
    """
    Haalt nieuws op voor alle meegegeven tickers, en geeft de meest recente
    'max_items' items terug. Dedupliceert op artikel-URL -- 1 artikel dat
    toevallig meerdere van je posities noemt (bv. een brede markt-roundup)
    moet 1x verschijnen, niet 1x per positie die het noemt. Als hetzelfde
    artikel voor meerdere posities gevonden wordt, worden hun namen
    gecombineerd i.p.v. willekeurig de eerste te tonen.
    """
    import screener as _screener  # lokale import: voorkomt een cirkelverwijzing bij module-laadtijd

    news_by_link: dict = {}
    link_order = []
    for item in holdings_and_watchlist:
        try:
            news_items = _screener.get_recent_news(item["ticker"], max_items=3, days_back=3)
        except Exception:
            news_items = []
        for n in news_items:
            link = n.get("link")
            if link in news_by_link:
                if item["naam"] not in news_by_link[link]["naam"]:
                    news_by_link[link]["naam"] += f", {item['naam']}"
            else:
                n["naam"] = item["naam"]
                news_by_link[link] = n
                link_order.append(link)

    all_news = [news_by_link[link] for link in link_order]
    all_news.sort(key=lambda x: x["published"], reverse=True)
    return all_news[:max_items]


def parse_degiro_transactions_csv(file_bytes: bytes) -> dict:
    """
    Parseert een DEGIRO 'Transacties'-export (CSV). Groepeert per ISIN (of
    productnaam als er geen ISIN is, zoals bij crypto) en geeft per groep de
    losse buy/sell-transacties terug.

    Bewuste keuzes:
    - Prijs komt uit de kolom 'Koers' zelf (de EXACTE, native prijs).
      GEVONDEN, BELANGRIJKE VERBETERING: de valuta van 'Koers' wordt nu
      RECHTSTREEKS uit de CSV zelf gelezen -- DEGIRO's export heeft een
      ONGENAAMDE kolom DIRECT NA 'Koers' met daarin de expliciete valuta
      (bv. 'USD'), die pandas automatisch 'Unnamed: N' noemt. Voorheen
      werd de valuta GEGOKT op basis van het ticker-achtervoegsel (bv.
      '.TO' -> altijd CAD) -- dit bleek FOUT voor USD-genoteerde aandelen
      op een Canadese beurs (zoals USA.TO, die ondanks de .TO-notering
      gewoon in USD handelt). De CSV's eigen, expliciete valuta-kolom is
      een VEEL betrouwbaardere bron dan zo'n achtervoegsel-gok.
    - Fee blijft voorlopig in EUR (fee_eur) -- DEGIRO's transactiekosten
      worden altijd in EUR in rekening gebracht, ongeacht de valuta van
      het aandeel zelf -- wordt in de import-loop omgerekend naar
      dezelfde native valuta als de prijs. Hiervoor gebruiken we de
      EXACTE, HISTORISCHE wisselkoers uit de CSV zelf ('Wisselkoers'-
      kolom, de koers van DIE transactiedag) i.p.v. een live opgehaalde
      koers van vandaag -- anders geeft de fee (een klein bedrag) een
      kleine maar zichtbare afwijking in de gemiddelde kostprijs, puur
      omdat de wisselkoers sinds de aankoop is bewogen.
    - Als 'Koers' een keer ontbreekt (zeldzaam) valt de prijs terug op de
      oude, EUR-gebaseerde berekening, met is_native=False als signaal
      voor de import-loop om dan GEEN aparte valuta-conversie meer te
      doen (de prijs staat dan al in EUR, punt).
    - Sommige crypto-rijen missen 'Aantal' in de export zelf -- die
      leiden we af uit lokale waarde / koers.
    - Rijen die zelfs dan niet te verwerken zijn (bv. een lege regel)
      worden overgeslagen en gerapporteerd, niet stilzwijgend genegeerd.
    """
    import io

    def parse_dutch_number(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip()
        if not s or s.lower() == "nan":
            return None
        return float(s.replace(".", "").replace(",", "."))

    df = pd.read_csv(io.BytesIO(file_bytes))

    # De kolom DIRECT NA 'Koers' bevat de expliciete valuta (bv. 'USD')
    # -- ongenaamd in de CSV zelf, dus pandas noemt 'm 'Unnamed: N'. We
    # zoeken 'm op POSITIE (relatief aan 'Koers') i.p.v. op de exacte
    # 'Unnamed: N'-naam, want die N kan verschuiven als het aantal
    # kolommen vóór 'Koers' ooit verandert.
    koers_currency_col = None
    if "Koers" in df.columns:
        koers_idx = df.columns.get_loc("Koers")
        if koers_idx + 1 < len(df.columns):
            koers_currency_col = df.columns[koers_idx + 1]

    grouped: dict = {}
    skipped_rows: list = []

    for idx, row in df.iterrows():
        product = row.get("Product")
        isin = row.get("ISIN")
        datum = row.get("Datum")

        if pd.isna(product) or pd.isna(datum):
            skipped_rows.append((idx, "Missing product name or date"))
            continue

        aantal = row.get("Aantal")
        koers = parse_dutch_number(row.get("Koers"))
        lokale_waarde = parse_dutch_number(row.get("Lokale waarde"))
        waarde_eur = parse_dutch_number(row.get("Waarde EUR"))
        totaal_eur = parse_dutch_number(row.get("Totaal EUR"))
        koers_currency = (
            str(row.get(koers_currency_col)).strip().upper()
            if koers_currency_col and not pd.isna(row.get(koers_currency_col))
            else None
        )
        wisselkoers = parse_dutch_number(row.get("Wisselkoers"))

        if pd.isna(aantal):
            if lokale_waarde is not None and koers not in (None, 0):
                # Aantal en lokale waarde hebben TEGENGESTELDE tekens (een koop
                # heeft een positief Aantal maar een negatieve lokale waarde --
                # geld gaat eruit) -- vandaar de min hier, anders komt een koop
                # er per ongeluk als verkoop uit te zien.
                aantal = -lokale_waarde / koers
            else:
                skipped_rows.append((idx, f"{product}: could not determine quantity"))
                continue
        else:
            aantal = float(aantal)

        if aantal == 0 or waarde_eur is None or totaal_eur is None:
            skipped_rows.append((idx, f"{product}: missing or zero value fields"))
            continue

        fee_eur = abs(totaal_eur - waarde_eur)

        if koers not in (None, 0):
            # De exacte, native prijs -- geen wisselkoers-afronding, want
            # geen conversie nodig.
            price = abs(koers)
            price_is_native = True
        else:
            # Zeldzame terugval: geen 'Koers' beschikbaar -- de oude,
            # EUR-gebaseerde berekening, met is_native=False als signaal.
            price = abs(waarde_eur) / abs(aantal)
            price_is_native = False

        try:
            parsed_date = pd.to_datetime(datum, format="%d-%m-%Y").date().isoformat()
        except Exception:
            skipped_rows.append((idx, f"{product}: could not parse date '{datum}'"))
            continue

        key = isin if not pd.isna(isin) else product
        if key not in grouped:
            grouped[key] = {
                "product": product,
                "isin": isin if not pd.isna(isin) else None,
                "transactions": [],
            }

        grouped[key]["transactions"].append({
            "transaction_type": "buy" if aantal > 0 else "sell",
            "shares": round(abs(aantal), 6),
            "price": round(price, 4),
            "price_is_native": price_is_native,
            "fee_eur": round(fee_eur, 2),
            "transaction_date": parsed_date,
            "historical_fx_rate": wisselkoers,  # EUR -> native, van DIE transactiedag zelf
            "koers_currency": koers_currency,  # de EXPLICIETE valuta uit de CSV zelf, i.p.v. een ticker-achtervoegsel-gok
        })

    return {"grouped": grouped, "skipped_rows": skipped_rows}


def parse_degiro_account_statement_csv(file_bytes: bytes) -> dict:
    """
    Parseert DEGIRO's 'Rekeningoverzicht/Activiteitenoverzicht'-export (CSV)
    -- een ANDER bestand dan de 'Transacties'-export hierboven
    (parse_degiro_transactions_csv), en het ENIGE DEGIRO-bestand dat
    daadwerkelijk dividend-cashflow bevat.

    GEVONDEN, FUNDAMENTELE OORZAAK van 'DEGIRO-dividenden verschijnen niet
    op de Dividend-pagina': de Transacties-export toont UITSLUITEND koop/
    verkoop-orders -- geen dividenden, punt. Dividend-boekingen staan bij
    DEGIRO alleen in dit bredere rekeningoverzicht, samen met allerlei
    andere cash-mutaties (stortingen, Cash Sweep Transfers, transactie-
    kosten, rente, valuta-creditering/debitering, etc.) die hier bewust
    genegeerd worden -- alleen 'Omschrijving' == 'Dividend' telt mee.

    Bewuste keuzes:
    - 'Dividendbelasting' (de ingehouden bronbelasting, een aparte regel
      met een NEGATIEF bedrag, meestal direct naast de 'Dividend'-regel)
      wordt NIET verrekend -- het 'Dividend'-bedrag zelf is het BRUTO-
      bedrag, consistent met hoe de andere broker-parsers ook het
      brutobedrag vastleggen (Robinhood/Schwab/Trade Republic hebben geen
      aparte belastingregel in hun export om mee te verrekenen).
    - De 2 bedragkolommen ('Mutatie' en 'Saldo') zijn in dit bestand RAAR
      opgebouwd: de kolom met die naam bevat de VALUTA, en het
      daadwerkelijke bedrag staat in de ONGENAAMDE kolom ERNAAST (pandas
      noemt die 'Unnamed: 8'/'Unnamed: 10') -- zelfde soort 'kolomnaam
      hoort eigenlijk bij het VOLGENDE veld'-eigenaardigheid als 'Koers'
      in de Transacties-export.
    - 'Mutatie' (niet 'Saldo') geeft de valuta van DIT dividend zelf --
      DEGIRO mengt EUR- en USD-dividenden gewoon door elkaar in 1 bestand,
      afhankelijk van de beurs van elke positie.
    - 'ISIN' wordt als identifier teruggegeven (net als bij de gewone
      DEGIRO/Trade Republic-parsers) -- de aanroeper matcht 'm naar een
      echte ticker, bv. via bestaande holdings of get_ticker_candidates().
    """
    import io

    def parse_dutch_number(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip()
        if not s or s.lower() == "nan":
            return None
        return float(s.replace(".", "").replace(",", "."))

    df = pd.read_csv(io.BytesIO(file_bytes))

    mutatie_amount_col = None
    if "Mutatie" in df.columns:
        mutatie_idx = df.columns.get_loc("Mutatie")
        if mutatie_idx + 1 < len(df.columns):
            mutatie_amount_col = df.columns[mutatie_idx + 1]

    dividend_rows: list = []
    skipped_rows: list = []

    for idx, row in df.iterrows():
        if str(row.get("Omschrijving") or "").strip() != "Dividend":
            continue

        product = row.get("Product")
        isin = row.get("ISIN")
        datum = row.get("Datum")
        currency = row.get("Mutatie")
        amount = parse_dutch_number(row.get(mutatie_amount_col)) if mutatie_amount_col else None

        if pd.isna(product) or pd.isna(datum) or amount is None:
            skipped_rows.append((idx, "Missing product, date or amount on a Dividend row"))
            continue

        try:
            parsed_date = pd.to_datetime(datum, format="%d-%m-%Y").date().isoformat()
        except Exception:
            skipped_rows.append((idx, f"{product}: could not parse date '{datum}'"))
            continue

        dividend_rows.append({
            "asset_code": isin if not pd.isna(isin) else product,
            "product": product,
            "amount": abs(amount),
            "currency": str(currency).strip().upper() if not pd.isna(currency) else "EUR",
            "date": parsed_date,
        })

    return {"dividend_rows": dividend_rows, "skipped_rows": skipped_rows}


def detect_broker_from_csv(file_bytes: bytes) -> str:
    """
    Herkent welke broker een 'Transactions'-CSV heeft opgeleverd, puur op
    basis van de kolomkoppen -- geen bestandsnaam-gok (die kan de
    gebruiker altijd wijzigen), maar de daadwerkelijke, unieke kolommen
    die elke broker's export nu eenmaal heeft. Geeft 'degiro', 'robinhood',
    'schwab', 'trade_republic' of 'unknown' terug.

    Sommige exports (met name Schwab) beginnen met 1 of meer losse tekst-
    regels VOOR de daadwerkelijke koptekst (bv. een accountnaam-regel) --
    als we alleen regel 1 zouden checken, zou de herkenning daar altijd
    op stuklopen. We scannen daarom de eerste ~15 regels stuk voor stuk
    op een kolomkoppen-match, i.p.v. blind aan te nemen dat regel 1 al
    de koptekst is.
    """
    text = file_bytes.decode("utf-8", errors="replace")
    lines = text.splitlines()[:15]

    for line in lines:
        columns = {c.strip().strip('"') for c in line.split(",")}

        # DEGIRO Rekeningoverzicht/Activiteitenoverzicht (ALLE cash-
        # mutaties, incl. dividenden) -- moet VOOR de gewone DEGIRO-check
        # hieronder staan: 'Product'/'ISIN'/'Datum' komen in BEIDE DEGIRO-
        # exports voor, maar 'Omschrijving'/'Mutatie'/'Saldo' zijn uniek
        # voor dit bredere rekeningoverzicht (de Transacties-export heeft
        # in plaats daarvan 'Koers'/'Aantal'). Zonder deze volgorde zou dit
        # bestand nooit als 'degiro_account' herkend worden.
        if {"Product", "ISIN", "Datum", "Omschrijving", "Mutatie", "Saldo"}.issubset(columns):
            return "degiro_account"
        # DEGIRO: eigen, Nederlandstalige kolomnamen -- 'Product'/'ISIN'/
        # 'Koers'/'Datum' komen niet voor in een Robinhood-export.
        if {"Product", "ISIN", "Koers", "Datum"}.issubset(columns):
            return "degiro"
        # Robinhood: 'Trans Code'/'Asset Code' zijn uniek voor Robinhood's
        # eigen exportformaat.
        if {"Trans Code", "Asset Code"}.issubset(columns):
            return "robinhood"
        # Charles Schwab: 'Fees & Comm' is een vrij unieke kolomnaam.
        if {"Action", "Fees & Comm", "Symbol"}.issubset(columns):
            return "schwab"
        # Trade Republic: kent GEEN eigen, unieke kolomnaam (simpel/generiek
        # formaat: Date/Symbol/Type/Quantity/Price/Amount) -- daarom pas als
        # ALLERLAATSTE check, nadat de specifiekere formaten hierboven al
        # zijn uitgesloten, om te voorkomen dat dit per ongeluk een ANDER,
        # nog-te-bouwen formaat met soortgelijke kolomnamen inpikt.
        if {"Date", "Symbol", "Type", "Quantity", "Price", "Amount"}.issubset(columns):
            return "trade_republic"

    return "unknown"


def parse_robinhood_transactions_csv(file_bytes: bytes) -> dict:
    """
    Parseert een Robinhood 'Account Activity'-export (CSV). Groepeert per
    ticker ('Asset Code' -- Robinhood geeft, anders dan DEGIRO, de ticker
    al rechtstreeks mee, dus er is GEEN losse ticker-matching-stap nodig
    zoals bij DEGIRO).

    Bewuste keuzes:
    - Alleen 'BUY' en 'SELL' worden als positie-transacties meegenomen.
      Overige cashflows (zoals 'ACH' stortingen/opnames) tellen NIET mee
      als positie en worden overgeslagen.
    - 'DIV' (dividend) wordt NIET overgeslagen als ongeldige rij, maar
      ook niet als buy/sell-transactie geimporteerd -- onze transactie-
      structuur (en die van DEGIRO) kent alleen 'buy'/'sell', geen
      aparte dividend-transactie. DIV-rijen komen daarom apart terug in
      'dividend_rows', zodat de UI eerlijk kan laten zien hoeveel
      dividend-rijen gevonden zijn i.p.v. ze stilzwijgend te negeren OF
      ze foutief als een 'buy' te importeren (wat het aantal shares
      onterecht zou ophogen).
    - 'Asset Code' wordt gebruikt als ticker, met een eventuele '-USD'-
      extensie (crypto-notatie, bv. 'BTC-USD') gestript tot 'BTC' --
      voor consistentie met hoe onze database crypto-tickers al opslaat
      (zonder valuta-achtervoegsel).
    - Robinhood handelt uitsluitend in USD -- geen aparte valuta-
      conversie nodig zoals bij DEGIRO (dat wel meerdere valuta's kent).
    - Fee wordt afgeleid uit het verschil tussen 'Amount' en
      Quantity*Price (Robinhood's eigen exports hebben geen aparte fee-
      kolom; bij de meeste courtagevrije trades is dit verschil 0).
    """
    import io

    def _to_float(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        try:
            return float(str(val).strip().replace("$", "").replace(",", ""))
        except (TypeError, ValueError):
            return None

    df = pd.read_csv(io.BytesIO(file_bytes))

    grouped: dict = {}
    skipped_rows: list = []
    dividend_rows: list = []
    # Bekende, bewust-genegeerde cashflow-codes (geen positie, dus geen
    # melding nodig -- ACH is de bekende). Alles WAT NIET hierin staat
    # EN niet BUY/SELL/DIV is, komt terecht in 'other_ignored_codes'
    # zodat de gebruiker zichtbaar krijgt hoeveel rijen met een
    # onbekend codewoord genegeerd zijn, i.p.v. dat zoiets spoorloos
    # verdwijnt als Robinhood ooit een ander/nieuw codewoord gebruikt
    # voor iets wat wel relevant zou kunnen zijn.
    known_ignorable_codes = {"ACH", "ACATI", "ACATO", "GOLD", "INT"}
    other_ignored_codes: dict = {}

    for idx, row in df.iterrows():
        trans_code = str(row.get("Trans Code") or "").strip().upper()

        if trans_code == "DIV":
            dividend_rows.append({
                "asset_code": row.get("Asset Code"),
                "amount": _to_float(row.get("Amount")),
                "date": row.get("Activity Date"),
            })
            continue

        if trans_code not in ("BUY", "SELL"):
            if trans_code and trans_code not in known_ignorable_codes:
                other_ignored_codes[trans_code] = other_ignored_codes.get(trans_code, 0) + 1
            continue

        asset_code = row.get("Asset Code")
        activity_date = row.get("Activity Date")
        quantity = _to_float(row.get("Quantity"))
        price = _to_float(row.get("Price"))
        amount = _to_float(row.get("Amount"))

        if pd.isna(asset_code) or pd.isna(activity_date):
            skipped_rows.append((idx, "Missing asset code or date"))
            continue
        if quantity is None or price is None or quantity == 0:
            skipped_rows.append((idx, f"{asset_code}: missing or zero quantity/price"))
            continue

        try:
            parsed_date = pd.to_datetime(activity_date).date().isoformat()
        except Exception:
            skipped_rows.append((idx, f"{asset_code}: could not parse date '{activity_date}'"))
            continue

        # '-USD'-extensie strippen (crypto-notatie, bv. 'BTC-USD' -> 'BTC')
        # voor consistentie met hoe onze database crypto-tickers opslaat.
        ticker = str(asset_code).strip().upper()
        if ticker.endswith("-USD"):
            ticker = ticker[:-4]

        # Fee = het verschil tussen het opgegeven Amount en de rauwe
        # Quantity*Price -- bij courtagevrije trades (de meeste
        # Robinhood-transacties) is dit 0.
        fee = None
        if amount is not None:
            fee = round(abs(abs(amount) - abs(quantity * price)), 2)
            if fee < 0.01:
                fee = 0.0

        if ticker not in grouped:
            grouped[ticker] = {
                "product": row.get("Description") or ticker,
                "ticker": ticker,
                "transactions": [],
            }

        grouped[ticker]["transactions"].append({
            "transaction_type": "buy" if trans_code == "BUY" else "sell",
            "shares": round(abs(quantity), 6),
            "price": round(abs(price), 4),
            "fee": fee or 0.0,
            "transaction_date": parsed_date,
            "currency": "USD",
        })

    return {
        "grouped": grouped, "skipped_rows": skipped_rows, "dividend_rows": dividend_rows,
        "other_ignored_codes": other_ignored_codes,
    }


def parse_schwab_transactions_csv(file_bytes: bytes) -> dict:
    """
    Parseert een Charles Schwab 'Transactions'-export (CSV). Schwab-
    exports beginnen/eindigen vaak met losse tekst-regels (bv. een
    accountnaam-header of een disclaimer-footer) die GEEN geldige CSV-
    rijen zijn -- die worden via 'on_bad_lines' overgeslagen i.p.v. de
    hele import te laten crashen.

    Bewuste keuzes:
    - 'Action' wordt gefilterd op 'Buy'/'Sell' (Schwab's eigen exacte
      labels) -- alle varianten van dividend-acties (Schwab gebruikt
      meerdere labels, zoals 'Qual Dividend', 'Cash Dividend', 'Non-Qual
      Div') worden herkend via een 'DIVIDEND' substring-match, niet een
      exacte match, en komen in dividend_rows terecht (niet als buy/sell
      geimporteerd -- zelfde reden als bij Robinhood: onze transactie-
      structuur kent geen apart dividend-type).
    - 'Amount' wordt hard schoongemaakt ('$' en '-' gestript) voor de
      float-conversie -- de richting (buy=geld eruit, sell=geld erin)
      wordt sowieso al afgeleid uit 'Action', niet uit het teken van
      Amount zelf.
    - Ticker komt rechtstreeks uit 'Symbol' -- geen ISIN-matching nodig.
    - Valuta: Schwab is een Amerikaanse broker, dus altijd USD.
    - Fee komt rechtstreeks uit 'Fees & Comm' (Schwab heeft, anders dan
      Robinhood, wel een eigen fee-kolom -- geen aflezing via het
      Amount-verschil nodig).
    """
    import io

    def _clean_amount(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        try:
            cleaned = str(val).strip().replace("$", "").replace(",", "").replace("-", "")
            return float(cleaned) if cleaned else None
        except (TypeError, ValueError):
            return None

    def _to_float(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        try:
            return float(str(val).strip().replace("$", "").replace(",", ""))
        except (TypeError, ValueError):
            return None

    # Schwab-exports beginnen vaak met 1 of meer losse tekst-regels vóór
    # de daadwerkelijke koptekst (bv. een accountnaam/datum-regel) -- als
    # we die gewoon aan pd.read_csv() geven, ziet pandas die EERSTE regel
    # aan voor de koptekst (met maar 1 kolom), en gooit vervolgens de
    # ECHTE koptekst + ALLE transactieregels weg als 'foutieve regels'
    # (die hebben immers 8 kolommen i.p.v. 1). We zoeken daarom EERST
    # zelf de regel op die er daadwerkelijk als koptekst uitziet (bevat
    # 'Date' EN 'Action' EN 'Symbol'), en lezen pas vanaf DIE regel in.
    text = file_bytes.decode("utf-8", errors="replace")
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if "Date" in line and "Action" in line and "Symbol" in line:
            header_idx = i
            break
    if header_idx is not None:
        file_bytes = "\n".join(lines[header_idx:]).encode("utf-8")

    try:
        df = pd.read_csv(io.BytesIO(file_bytes), on_bad_lines="skip")
    except TypeError:
        # oudere pandas-versies kennen 'on_bad_lines' nog niet -- terugval
        # op het oudere 'error_bad_lines=False'.
        df = pd.read_csv(io.BytesIO(file_bytes), error_bad_lines=False)

    grouped: dict = {}
    skipped_rows: list = []
    dividend_rows: list = []

    for idx, row in df.iterrows():
        action = str(row.get("Action") or "").strip()
        action_upper = action.upper()

        if "DIVIDEND" in action_upper or action_upper in ("DIV",):
            dividend_rows.append({
                "asset_code": row.get("Symbol"),
                "amount": _clean_amount(row.get("Amount")),
                "date": row.get("Date"),
            })
            continue

        if action_upper not in ("BUY", "SELL"):
            continue

        symbol = row.get("Symbol")
        date_val = row.get("Date")
        quantity = _to_float(row.get("Quantity"))
        price = _to_float(row.get("Price"))
        fee = _clean_amount(row.get("Fees & Comm")) or 0.0

        if pd.isna(symbol) or not str(symbol).strip() or pd.isna(date_val):
            skipped_rows.append((idx, "Missing symbol or date"))
            continue
        if quantity is None or price is None or quantity == 0:
            skipped_rows.append((idx, f"{symbol}: missing or zero quantity/price"))
            continue

        try:
            parsed_date = pd.to_datetime(date_val).date().isoformat()
        except Exception:
            skipped_rows.append((idx, f"{symbol}: could not parse date '{date_val}'"))
            continue

        ticker = str(symbol).strip().upper()

        if ticker not in grouped:
            grouped[ticker] = {
                "product": row.get("Description") or ticker,
                "ticker": ticker,
                "transactions": [],
            }

        grouped[ticker]["transactions"].append({
            "transaction_type": "buy" if action_upper == "BUY" else "sell",
            "shares": round(abs(quantity), 6),
            "price": round(abs(price), 4),
            "fee": round(fee, 2),
            "transaction_date": parsed_date,
            "currency": "USD",
        })

    return {
        "grouped": grouped, "skipped_rows": skipped_rows, "dividend_rows": dividend_rows,
        "other_ignored_codes": {},
    }


def parse_trade_republic_transactions_csv(file_bytes: bytes) -> dict:
    """
    Parseert een Trade Republic 'Transactions'-export (CSV). Anders dan
    Robinhood/Schwab geeft Trade Republic GEEN ticker rechtstreeks mee,
    alleen een ISIN ('Symbol'-kolom bevat de ISIN) -- daarom groeperen
    we hier, EXACT als bij DEGIRO, per ISIN i.p.v. per ticker, en levert
    dit dezelfde 'grouped'-vorm op als parse_degiro_transactions_csv().
    Dat is bewust: zo kan de bestaande ISIN-naar-ticker-matching-UI (die
    de gebruiker laat kiezen/bevestigen welke ticker bij welke ISIN
    hoort, zie de DEGIRO-import) VOLLEDIG HERGEBRUIKT worden voor Trade
    Republic, i.p.v. een hele nieuwe matching-UI te bouwen -- 'naadloos
    synchroniseren met onze actieve portfolio-tabellen' loopt zo via
    dezelfde, al beproefde weg als DEGIRO.

    Bewuste keuzes:
    - 'Type' wordt gefilterd op BUY/SELL; DIVIDEND komt in dividend_rows
      terecht (zelfde reden als bij Robinhood/Schwab: geen apart
      dividend-transactietype in onze structuur).
    - Trade Republic is een Duitse/Europese broker en handelt in EUR --
      price_is_native=True met koers_currency='EUR', zodat de bestaande
      DEGIRO-import-loop geen extra FX-conversie probeert te doen (die
      is alleen nodig als de valuta AFWIJKT van EUR).
    """
    import io

    def _to_float(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        try:
            return float(str(val).strip().replace("€", "").replace(",", ""))
        except (TypeError, ValueError):
            return None

    df = pd.read_csv(io.BytesIO(file_bytes))

    grouped: dict = {}
    skipped_rows: list = []
    dividend_rows: list = []

    for idx, row in df.iterrows():
        tx_type = str(row.get("Type") or "").strip().upper()

        if tx_type == "DIVIDEND":
            dividend_rows.append({
                "asset_code": row.get("Symbol"),
                "amount": _to_float(row.get("Amount")),
                "date": row.get("Date"),
            })
            continue

        if tx_type not in ("BUY", "SELL"):
            continue

        isin = row.get("Symbol")
        date_val = row.get("Date")
        quantity = _to_float(row.get("Quantity"))
        price = _to_float(row.get("Price"))

        if pd.isna(isin) or not str(isin).strip() or pd.isna(date_val):
            skipped_rows.append((idx, "Missing ISIN or date"))
            continue
        if quantity is None or price is None or quantity == 0:
            skipped_rows.append((idx, f"{isin}: missing or zero quantity/price"))
            continue

        try:
            parsed_date = pd.to_datetime(date_val).date().isoformat()
        except Exception:
            skipped_rows.append((idx, f"{isin}: could not parse date '{date_val}'"))
            continue

        isin_clean = str(isin).strip().upper()

        if isin_clean not in grouped:
            grouped[isin_clean] = {
                "product": isin_clean,  # Trade Republic geeft geen productnaam mee, alleen de ISIN zelf
                "isin": isin_clean,
                "transactions": [],
            }

        grouped[isin_clean]["transactions"].append({
            "transaction_type": "buy" if tx_type == "BUY" else "sell",
            "shares": round(abs(quantity), 6),
            "price": round(abs(price), 4),
            "price_is_native": True,
            "fee_eur": 0.0,
            "transaction_date": parsed_date,
            "historical_fx_rate": None,
            "koers_currency": "EUR",
        })

    return {"grouped": grouped, "skipped_rows": skipped_rows, "dividend_rows": dividend_rows}


def _persist_dividend_rows(
    user_email: str, dividend_rows: list, source: str, currency: str = None,
    ticker_naam_lookup: dict = None,
) -> tuple[int, int]:
    """
    Slaat geparste dividend-rijen (het 'dividend_rows'-bijproduct van de
    broker-parsers hierboven) PERMANENT op in de 'dividend_income'-tabel
    (database.add_dividend_income()) -- i.p.v. ze, zoals voorheen, alleen
    1x als caption te tonen en daarna stilzwijgend weg te gooien.

    GEVONDEN, FUNDAMENTEEL PROBLEEM (voor de Dividend-pagina gebouwd kon
    worden): 'dividend_rows' bleek GEEN bewaarde datastructuur te zijn --
    puur een tijdelijk bijproduct van de import-stap zelf, dat na het
    klikken op 'Import' meteen uit session_state verdween. Een Dividend-
    pagina die daar 'historie' uit zou putten, zou dus altijd leeg zijn.
    Vanaf nu dus een ECHTE, aparte tabel (bewust GEEN 'DIV'-transactie in
    portfolio_transactions -- zie add_dividend_income()'s toelichting).

    Gededupliceerd tegen wat er al in de tabel staat (zelfde ticker +
    datum + bedrag, met een kleine tolerantie voor afrondingsverschillen)
    -- nodig omdat de gebruiker bewust OUDE, al eerder verwerkte CSV's
    opnieuw mag aanleveren om de volledige historie alsnog binnen te
    halen, zonder bij elke herhaalde upload dubbel te gaan tellen.
    """
    ticker_naam_lookup = ticker_naam_lookup or {}
    existing = database.get_dividend_income(user_email)

    def _is_duplicate(ticker: str, amount: float, payout_date: str) -> bool:
        for e in existing:
            if e.get("ticker") != ticker or e.get("payout_date") != payout_date:
                continue
            if abs(float(e.get("amount") or 0) - amount) <= max(abs(amount) * 0.01, 0.01):
                return True
        return False

    imported, skipped = 0, 0
    for row in dividend_rows:
        raw_ticker = row.get("asset_code")
        raw_amount = row.get("amount")
        raw_date = row.get("date")
        if raw_ticker is None or raw_amount is None or raw_date is None or pd.isna(raw_ticker) or pd.isna(raw_date):
            skipped += 1
            continue
        ticker = str(raw_ticker).strip().upper()
        if ticker.endswith("-USD"):
            ticker = ticker[:-4]
        try:
            payout_date = pd.to_datetime(raw_date).date().isoformat()
        except Exception:
            skipped += 1
            continue
        amount = abs(float(raw_amount))
        if amount <= 0:
            skipped += 1
            continue
        if _is_duplicate(ticker, amount, payout_date):
            skipped += 1
            continue
        # 'currency' is een PER-ROW override waar beschikbaar (bv. DEGIRO's
        # rekeningoverzicht, dat zowel EUR- als USD-dividenden in 1 bestand
        # mengt, afhankelijk van de beurs van elke individuele positie) --
        # anders de vaste, voor de hele upload geldende broker-valuta
        # (Robinhood/Schwab altijd USD, Trade Republic altijd EUR).
        row_currency = row.get("currency") or currency or "EUR"
        database.add_dividend_income(
            user_email, ticker, ticker_naam_lookup.get(ticker, ticker),
            amount, row_currency, payout_date, source,
        )
        existing.append({"ticker": ticker, "amount": amount, "payout_date": payout_date})
        imported += 1
    return imported, skipped


def filter_active_holdings(holdings: list) -> list:
    """
    Verbergt posities die op 0 shares staan (volledig verkocht, bv. via
    een bulk-import waarbij koop+verkoop samen tot 0 optellen) -- shares
    van None (nog helemaal niet ingevuld/bekend) blijft wel gewoon zichtbaar.
    """
    return [h for h in holdings if h.get("shares") is None or abs(h["shares"]) > 0.0001]


def sync_holding_shares_from_transactions(holding_id: int, user_email: str) -> float:
    """
    Herberekent het aantal shares uit ALLE transacties van deze positie, en
    schrijft dat terug naar portfolio_holdings.shares -- zodat de rest van
    de app (portfolio-waarde, concentratie-berekeningen, etc.) gewoon het
    opgeslagen 'shares'-veld kan blijven gebruiken, zonder overal apart de
    transacties te moeten optellen. Moet aangeroepen worden na ELKE
    toegevoegde of verwijderde transactie. Geeft het nieuwe aantal terug.
    """
    import database
    transactions = database.get_transactions_for_holding(user_email, holding_id)
    derived_shares = sum(
        t["shares"] if t["transaction_type"] == "buy" else -t["shares"]
        for t in transactions
    )
    database.update_holding_shares(holding_id, user_email, derived_shares)
    return derived_shares


def _looks_like_isin(value: str) -> bool:
    """Checkt of een string er zelf uitziet als een ISIN (2 letters + 9 alfanumeriek + 1 cijfer,
    12 tekens totaal) -- gebruikt om te detecteren als Yahoo's zoekfunctie per ongeluk de
    ISIN zelf teruggeeft als 'symbool' (komt voor bij ETF's met meerdere beursnoteringen)."""
    if not value or len(value) != 12:
        return False
    return value[:2].isalpha() and value[2:11].isalnum() and value[11].isdigit()


def get_ticker_candidates(product_name: str, isin: str = None) -> list:
    """
    Zoekt mogelijke ticker-kandidaten voor een positie uit een broker-
    export -- geeft een LIJST terug (niet alleen de beste gok), zodat de
    gebruiker bij twijfel zelf kan kiezen. Dit is nodig omdat veel
    fondsen (vooral UCITS-ETF's) op MEERDERE beurzen tegelijk genoteerd
    staan (bv. 'SMH' op de VS-beurs, in Milaan, EN Londen, elk met een
    andere prijs) -- een enkele blinde gok kan zomaar de verkeerde
    beursnotering pakken, met verkeerde koersen als gevolg.

    Elke kandidaat is een dict met 'symbol', 'name', 'exchange'. Filtert
    de valse 'ISIN als symbool'-match weg (zie _looks_like_isin). Bij
    crypto (geen ISIN) filteren we op quoteType 'CRYPTOCURRENCY'.
    """
    candidates = []
    seen_symbols = set()

    def _add_results(results):
        for r in results:
            symbol = r.get("symbol")
            if not symbol or symbol in seen_symbols or _looks_like_isin(symbol):
                continue
            seen_symbols.add(symbol)
            candidates.append({
                "symbol": symbol,
                "name": r.get("shortname") or r.get("longname") or symbol,
                "exchange": r.get("exchange", ""),
            })

    if isin:
        try:
            _add_results(yf.Search(isin, max_results=6).quotes)
        except Exception:
            pass
    else:
        try:
            all_results = yf.Search(product_name, max_results=6).quotes
            _add_results([r for r in all_results if r.get("quoteType") == "CRYPTOCURRENCY"])
        except Exception:
            pass

    if not candidates:
        try:
            _add_results(yf.Search(product_name, max_results=6).quotes)
        except Exception:
            pass

    return candidates


def guess_ticker_for_product(product_name: str, isin: str = None) -> str:
    """Compacte variant van get_ticker_candidates() die alleen de beste gok teruggeeft."""
    candidates = get_ticker_candidates(product_name, isin)
    return candidates[0]["symbol"] if candidates else None


# De 5 grootste/bekendste wereldwijde indices, als benchmark-keuze bij Performance
BENCHMARK_OPTIONS = {
    "S&P 500": "^GSPC",
    "NASDAQ Composite": "^IXIC",
    "EURO STOXX 50": "^STOXX50E",
}


def compute_price_return(price_history: pd.DataFrame, days_back: int = None, since_date=None) -> float:
    """
    Berekent het %-koersrendement over een periode -- ofwel de laatste
    'days_back' dagen, ofwel sinds een specifieke datum ('since_date',
    bv. 1 januari voor YTD). Puur op prijs gebaseerd (niet
    transactie-gebaseerd). Geeft None terug bij te weinig data.
    """
    if price_history is None or price_history.empty:
        return None
    price_history = price_history.sort_index()
    latest_price = float(price_history["Close"].iloc[-1])
    index_naive = price_history.index.tz_localize(None) if price_history.index.tz is not None else price_history.index

    if since_date is not None:
        mask = index_naive >= pd.Timestamp(since_date)
        if not mask.any():
            return None
        start_price = float(price_history["Close"].iloc[mask.argmax()])
    elif days_back is not None:
        cutoff = index_naive[-1] - pd.Timedelta(days=days_back)
        mask = index_naive <= cutoff
        if not mask.any():
            return None
        start_price = float(price_history["Close"].iloc[np.where(mask)[0][-1]])
    else:
        return None

    if start_price == 0:
        return None
    return (latest_price - start_price) / start_price * 100


def get_ticker_ytd_and_1y_return(ticker: str) -> dict:
    """Haalt YTD- en 1-jaars-koersrendement op voor 1 ticker."""
    try:
        history = yf.Ticker(ticker).history(period="2y")
    except Exception:
        return {"ytd_pct": None, "one_year_pct": None}
    if history is None or history.empty:
        return {"ytd_pct": None, "one_year_pct": None}

    jan_1_this_year = datetime(datetime.now().year, 1, 1)
    return {
        "ytd_pct": compute_price_return(history, since_date=jan_1_this_year),
        "one_year_pct": compute_price_return(history, days_back=365),
    }


def compute_day_change_pct(history: pd.DataFrame) -> float:
    """
    Berekent de dagverandering (%) op basis van de laatste 2 GELDIGE
    slotkoersen in een AL opgehaalde geschiedenis -- geen extra
    netwerk-aanroep nodig, want deze data wordt toch al opgehaald bij
    een portfolio-refresh (period='5d').
    """
    if history is None or history.empty:
        return None
    valid_closes = history["Close"].dropna()
    if len(valid_closes) < 2:
        return None
    latest = float(valid_closes.iloc[-1])
    previous = float(valid_closes.iloc[-2])
    if previous == 0:
        return None
    return (latest - previous) / previous * 100


def _price_near_date(history: pd.DataFrame, target_date, tolerance_days: int = 10):
    """
    Zoekt de koers het dichtst bij een specifieke datum, BINNEN een al
    opgehaalde (langere) geschiedenis -- i.p.v. voor elke periode een
    aparte, nieuwe netwerk-aanroep te doen. Geeft None terug als er geen
    geldige koers binnen de tolerantie ligt.
    """
    if history is None or history.empty:
        return None
    valid = history[history["Close"].notna()]
    if valid.empty:
        return None
    # yfinance geeft vaak een tijdzone-BEWUSTE index terug (bv.
    # 'America/New_York'), terwijl 'target_date' een gewone, tijdzone-
    # NAIEVE datum is -- zonder dit te normaliseren gooit pandas een fout
    # bij het vergelijken. Die fout werd elders stilzwijgend opgevangen
    # (try/except), waardoor sommige posities ONTBRAKEN uit de
    # berekening -- dat verklaarde de absurd hoge percentages (beginwaarde
    # onvolledig, eindwaarde wel compleet).
    index = valid.index
    if getattr(index, "tz", None) is not None:
        index = index.tz_localize(None)
    target_ts = pd.Timestamp(target_date)
    time_diffs = abs(index - target_ts)
    closest_pos = time_diffs.argmin()
    if time_diffs[closest_pos].days > tolerance_days:
        return None
    return float(valid["Close"].iloc[closest_pos])


@st.cache_data(ttl=3600, show_spinner=False)
def _batch_download_history(tickers_tuple: tuple, period: str = "max") -> dict:
    """
    Haalt de koersgeschiedenis van meerdere tickers op, 1x per ticker via
    get_cached_ticker_history() (die zelf 5 minuten gecached is en
    yf.Ticker().history() gebruikt).

    LET OP: gebruikte VROEGER yf.download() (yfinance's eigen batch-
    download, 1 netwerk-aanroep voor alle tickers tegelijk) voor
    snelheid -- maar dat bleek een BEVESTIGDE, in yfinance's eigen
    GitHub-issues gedocumenteerde bug te hebben: yf.download() loopt
    structureel 1+ dag ACHTER op yf.Ticker().history() (de laatste
    handelsdag ontbreekt soms compleet). Concreet gevolg: 'Update
    portfolio value' bleef VEROUDERDE koersen tonen, ook na het oplossen
    van de eigen caching-problemen (want yfinance zelf gaf al verouderde
    data terug, nog vóórdat onze eigen cache er iets mee deed). Nu dus
    per ticker via de betrouwbaardere .history()-methode, met een kleine
    snelheids-kost (meerdere kleine aanroepen i.p.v. 1 grote) die voor
    een doorsnee portfolio (een tiental posities) niet merkbaar is.
    """
    tickers = list(tickers_tuple)
    if not tickers:
        return {}
    result = {}
    for ticker in tickers:
        try:
            result[ticker] = get_cached_ticker_history(ticker, period=period)
        except Exception:
            result[ticker] = None
    return result


def get_shared_history_for_holdings(holdings: list, period: str = "max") -> dict:
    """
    Haalt de koersgeschiedenis van AL je posities in 1x op (via een
    gecachte batch-download), voor hergebruik door MEERDERE berekeningen
    (YTD, 1-jaar, en de portfoliowaarde-over-tijd-grafiek) -- i.p.v. dat
    elke periode of elke positie zijn eigen, aparte netwerk-aanroep doet.
    """
    unique_tickers = tuple(sorted({h["ticker"] for h in holdings}))
    return _batch_download_history(unique_tickers, period=period)


def compute_portfolio_value_over_time(holdings: list, user_email: str, history_by_ticker: dict, num_points: int = 60) -> list:
    """
    Berekent de TOTALE portfoliowaarde op meerdere momenten in het
    verleden (gelijk verdeeld tussen je vroegste transactie en vandaag) --
    voor de 'zie je portfolio groeien'-grafiek. Gebruikt de AL opgehaalde,
    gedeelde geschiedenis (history_by_ticker) -- dus GEEN extra netwerk-
    aanroepen nodig, ondanks dat er relatief veel punten berekend worden.
    """
    import database

    all_transactions = {}
    earliest = None
    for h in holdings:
        transactions = database.get_transactions_for_holding(user_email, h["id"])
        all_transactions[h["ticker"]] = transactions
        for t in transactions:
            t_date = datetime.strptime(t["transaction_date"], "%Y-%m-%d").date()
            if earliest is None or t_date < earliest:
                earliest = t_date

    if earliest is None:
        return []

    today = datetime.now().date()
    total_days = (today - earliest).days
    if total_days <= 0:
        return []

    points = [
        earliest + timedelta(days=int(total_days * i / num_points))
        for i in range(num_points + 1)
    ]

    series = []
    for point_date in points:
        total_value = 0.0
        any_value = False
        for h in holdings:
            ticker = h["ticker"]
            shares_at_point = 0.0
            for t in all_transactions.get(ticker, []):
                t_date = datetime.strptime(t["transaction_date"], "%Y-%m-%d").date()
                if t_date <= point_date:
                    delta = t["shares"] if t["transaction_type"] == "buy" else -t["shares"]
                    shares_at_point += delta
            if shares_at_point > 0.0001:
                price = _price_near_date(history_by_ticker.get(ticker), point_date, tolerance_days=15)
                if price is not None:
                    total_value += shares_at_point * price
                    any_value = True
        if any_value:
            series.append({"date": point_date, "value": total_value})

    return series


def compute_cumulative_contribution_over_time(holdings: list, user_email: str, num_points: int = 60) -> list:
    """
    Berekent de cumulatieve, ZELF-INGEBRACHTE kapitaal ('Net Capital
    Invested') op dezelfde reeks datumpunten als compute_portfolio_value_
    over_time() -- zodat beide lijnen (inleg vs. waarde) synchroon op
    dezelfde tijdsas geplot kunnen worden. Onze database houdt GEEN
    losse DEPOSIT/ACH-stortingsregels bij (die worden bij elke broker-
    CSV-import bewust overgeslagen -- zie parse_degiro/robinhood/schwab/
    trade_republic_transactions_csv), dus dit is een PROXY op basis van
    de netto BUY/SELL-kasstroom, exact dezelfde aanname als de Wealth
    Engine's jaarlijkse-inleg-schatting elders in deze functie.

    BUY draagt +(shares*price + fee) bij (geld dat de deur uit ging).
    SELL draagt -(shares*price - fee) bij (geld dat terugkwam, verminderd
    met de fee -- de fee is een kostenpost, dus verlaagt hoeveel er
    netto 'terugvloeide').
    """
    import database

    all_transactions = {}
    earliest = None
    for h in holdings:
        transactions = database.get_transactions_for_holding(user_email, h["id"])
        all_transactions[h["ticker"]] = transactions
        for t in transactions:
            t_date = datetime.strptime(t["transaction_date"], "%Y-%m-%d").date()
            if earliest is None or t_date < earliest:
                earliest = t_date

    if earliest is None:
        return []

    today = datetime.now().date()
    total_days = (today - earliest).days
    if total_days <= 0:
        return []

    points = [
        earliest + timedelta(days=int(total_days * i / num_points))
        for i in range(num_points + 1)
    ]

    series = []
    for point_date in points:
        net_invested = 0.0
        for ticker, transactions in all_transactions.items():
            for t in transactions:
                t_date = datetime.strptime(t["transaction_date"], "%Y-%m-%d").date()
                if t_date > point_date:
                    continue
                amount = (t.get("shares") or 0) * (t.get("price") or 0)
                fee = t.get("fee") or 0
                if t.get("transaction_type") == "buy":
                    net_invested += amount + fee
                else:
                    net_invested -= (amount - fee)
        series.append({"date": point_date, "value": net_invested})

    return series


def compute_personal_windowed_return(holdings: list, user_email: str, window_start, history_by_ticker: dict = None) -> dict:
    """
    Berekent je ECHTE, persoonlijke rendement over een specifieke periode
    (bv. YTD of de laatste 12 maanden) -- een vereenvoudigde Dietz-methode:

    - Begin-waarde: shares die je AL had vóór 'window_start', gewaardeerd
      tegen de koers van toen (niet je oorspronkelijke aankoopprijs --
      we meten wat er BINNEN deze periode is gebeurd)
    - Netto-inleg: aankopen (+) en verkopen (-) die BINNEN de periode
      vielen
    - Eind-waarde: de huidige positie-waarde nu

    Rendement = (eind-waarde - begin-waarde - netto-inleg) / (begin-waarde + netto-inleg)

    Geeft None terug als er te weinig data is om iets te zeggen.

    'history_by_ticker' (optioneel): een AL opgehaalde, langere
    koersgeschiedenis per ticker (bv. 3 jaar) -- als meegegeven, wordt
    die HERGEBRUIKT i.p.v. een nieuwe, aparte netwerk-aanroep per periode
    te doen. Dit is de kern van de snelheidsfix: zonder dit deed elke
    aparte periode (YTD, 1-jaar, straks meer) zijn EIGEN aanroep per
    positie, wat met meerdere periodes en posities snel optelde.
    """
    import database

    starting_value = 0.0
    net_contributions = 0.0
    ending_value = 0.0
    any_starting_data = False

    for h in holdings:
        transactions = database.get_transactions_for_holding(user_email, h["id"])
        if not transactions:
            continue

        shares_before_window = 0.0
        for t in transactions:
            t_date = datetime.strptime(t["transaction_date"], "%Y-%m-%d").date()
            delta = t["shares"] if t["transaction_type"] == "buy" else -t["shares"]
            if t_date < window_start:
                shares_before_window += delta
            else:
                if t["transaction_type"] == "buy":
                    net_contributions += t["shares"] * t["price"] + t["fee"]
                else:
                    net_contributions -= t["shares"] * t["price"] - t["fee"]

        if shares_before_window > 0.0001:
            try:
                if history_by_ticker is not None:
                    history = history_by_ticker.get(h["ticker"])
                else:
                    # Terugval als er geen gedeelde cache is meegegeven --
                    # werkt nog steeds, alleen zonder het snelheidsvoordeel.
                    history = get_cached_ticker_history(
                        h["ticker"],
                        start=(window_start - timedelta(days=10)).isoformat(),
                        end=(window_start + timedelta(days=10)).isoformat(),
                    )
                price_at_start = _price_near_date(history, window_start)
                if price_at_start is not None:
                    starting_value += shares_before_window * price_at_start
                    any_starting_data = True
            except Exception:
                pass

        position_value = h.get("position_value") or 0.0
        if not pd.isna(position_value):
            ending_value += position_value

    if not any_starting_data and net_contributions == 0:
        return None  # niks om over te rapporteren -- geen posities van vóór deze periode, geen nieuwe inleg

    denominator = starting_value + net_contributions
    if denominator <= 0:
        return None

    gain = ending_value - starting_value - net_contributions
    return_pct = gain / denominator * 100
    if pd.isna(return_pct) or pd.isna(gain):
        # Laatste veiligheidsnet -- zou niet meer moeten gebeuren dankzij de
        # checks hierboven, maar voorkomt sowieso ooit weer een '+nan%'.
        return None
    return {"return_pct": return_pct, "gain": gain}


def _infer_currency_from_transactions(transactions: list, fallback: str = None) -> str:
    """
    Leidt de 'native' valuta van een positie af uit de daadwerkelijk
    OPGESLAGEN transacties (de meest voorkomende currency erin) i.p.v.
    te GOKKEN op basis van het ticker-achtervoegsel (get_cached_
    ticker_currency) -- die gok bleek FOUT voor aandelen die ondanks
    hun beurs-notering in een andere valuta handelen (bv. USA.TO,
    genoteerd op Toronto (.TO, meestal CAD) maar daadwerkelijk in USD
    verhandeld). De transacties zelf hebben nu een betrouwbare,
    EXPLICIETE currency (rechtstreeks uit de CSV's eigen valuta-kolom,
    of de valuta die de gebruiker zelf koos bij handmatige invoer) --
    veel betrouwbaarder dan een achtervoegsel-gok.

    Valt terug op 'fallback' (meestal get_cached_ticker_currency) als er
    geen transacties zijn om uit af te leiden.
    """
    if not transactions:
        return fallback
    currencies = [t.get("currency") or "EUR" for t in transactions]
    return max(set(currencies), key=currencies.count)


def _convert_transactions_to_currency(transactions: list, target_currency: str) -> list:
    """
    Rekent elke transactie's prijs+fee om naar 'target_currency', aan de
    hand van de per-transactie opgeslagen 'currency' (het nieuwe,
    expliciete veld -- lost de structurele bug op waarbij de app moest
    GOKKEN in welke valuta een transactieprijs stond: CSV-import slaat
    altijd EUR op, handmatige invoer kon in principe elke valuta zijn,
    en het mengen daarvan gaf compleet verkeerde rendementen).

    Ontbreekt het 'currency'-veld nog (oudere transacties, van vóór deze
    fix)? Dan wordt 'EUR' aangenomen -- consistent met hoe ze feitelijk
    altijd zijn ingevoerd (CSV-import was al EUR-only, en het formulier
    toonde tot nu toe overal een hardcoded €-teken).
    """
    if not transactions:
        return transactions
    fx_cache = {}
    converted = []
    for t in transactions:
        tx_currency = t.get("currency") or "EUR"
        if tx_currency == target_currency:
            converted.append(t)
            continue
        if tx_currency not in fx_cache:
            fx_cache[tx_currency] = get_fx_rate(tx_currency, target_currency)
        fx_rate = fx_cache[tx_currency] or 1.0  # FX-conversie mislukt -- liever ongeconverteerd dan de transactie verliezen
        converted.append({
            **t,
            "price": t["price"] * fx_rate,
            "fee": t.get("fee", 0.0) * fx_rate,
        })
    return converted


def compute_holding_performance(transactions: list, current_price: float = None) -> dict:
    """
    Berekent rendement uit een lijst buy/sell-transacties, met de
    FIFO-methode (First-In-First-Out, inclusief betaalde fees) -- matcht
    hiermee DEGIRO's eigen 'GAK' en de meeste brokers/belastingdiensten.
    Geeft None terug als er geen bruikbare transacties zijn -- geen
    dividenden meegenomen (bewust, voor nu).

    GEVONDEN, BELANGRIJK VERSCHIL (met de vorige, eenvoudigere methode):
    bij een positie met TUSSENTIJDSE, GEDEELTELIJKE verkopen gaf een
    simpel gewogen gemiddelde van ALLE ooit gedane aankopen een compleet
    andere (en voor de gebruiker onherkenbare) kostprijs dan wat DEGIRO
    toont. FIFO beschouwt de OUDSTE aankopen als eerst verkocht -- de
    kostprijs van wat je NU nog in bezit hebt, is dus gebaseerd op de
    specifieke, meest recente aankoop-blokken die nog 'over' zijn, niet
    een gemiddelde van de hele (inclusief allang verkochte) geschiedenis.

    current_price is alleen nodig als er nog shares in bezit zijn (voor
    de ongerealiseerde winst/verlies) -- bij een VOLLEDIG GESLOTEN positie
    (0 shares over) is de huidige prijs irrelevant (0 x wat dan ook = 0),
    dus die mag dan gewoon None zijn zonder dat de functie stopt.
    """
    if not transactions:
        return None

    total_bought_shares = sum(tx["shares"] for tx in transactions if tx["transaction_type"] == "buy")
    total_bought_cost = sum(tx["shares"] * tx["price"] + tx["fee"] for tx in transactions if tx["transaction_type"] == "buy")
    total_sold_shares = sum(tx["shares"] for tx in transactions if tx["transaction_type"] == "sell")

    if total_bought_shares <= 0:
        return None  # geen aankopen gelogd, kan geen kostprijs bepalen

    # FIFO-simulatie: chronologisch (oud -> nieuw) door de transacties
    # lopen, met een wachtrij van 'lots' (aankoop-blokken). Een verkoop
    # verbruikt eerst de OUDSTE, nog-openstaande lots. BELANGRIJK: bij
    # transacties op DEZELFDE dag moet een buy ALTIJD vóór een sell komen
    # (anders kan een verkoop 'te vroeg' verwerkt worden, voordat de
    # aankoop van diezelfde dag al in de wachtrij zit -- dit gaf eerder
    # een fout, te hoog shares_held-aantal, omdat een deel van zo'n
    # verkoop niet gematcht kon worden en simpelweg genegeerd werd).
    sorted_tx = sorted(
        transactions,
        key=lambda t: (t["transaction_date"], 0 if t["transaction_type"] == "buy" else 1),
    )
    from collections import deque
    lots = deque()  # elk element: [aantal_over, kostprijs_per_stuk_incl_fee]
    realized_pnl = 0.0

    for tx in sorted_tx:
        if tx["transaction_type"] == "buy":
            cost_per_share = tx["price"] + (tx["fee"] / tx["shares"] if tx["shares"] else 0)
            lots.append([tx["shares"], cost_per_share])
        else:  # sell
            proceeds_per_share = tx["price"] - (tx["fee"] / tx["shares"] if tx["shares"] else 0)
            remaining_to_sell = tx["shares"]
            while remaining_to_sell > 0.0001 and lots:
                lot_shares, lot_cost = lots[0]
                matched = min(lot_shares, remaining_to_sell)
                realized_pnl += matched * (proceeds_per_share - lot_cost)
                remaining_to_sell -= matched
                if matched >= lot_shares - 0.0001:
                    lots.popleft()
                else:
                    lots[0][0] -= matched
            # Als remaining_to_sell > 0 blijft (meer verkocht dan ooit
            # gekocht -- een data-fout, bv. een ontbrekende aankoop) wordt
            # dat stuk simpelweg genegeerd i.p.v. te crashen.

    # De OVERGEBLEVEN lots vormen de huidige positie -- hun kostprijs is
    # de FIFO-gebaseerde 'gemiddelde kostprijs' die nu getoond wordt.
    shares_held = sum(lot_shares for lot_shares, _ in lots)
    cost_basis_held = sum(lot_shares * lot_cost for lot_shares, lot_cost in lots)
    avg_cost_per_share = cost_basis_held / shares_held if shares_held > 0.0001 else None

    if shares_held > 0.0001 and current_price is None:
        return None  # er zijn nog shares in bezit, dan is de huidige prijs wel echt nodig

    price_for_calc = current_price if current_price is not None else 0.0
    unrealized_pnl = (price_for_calc * shares_held) - cost_basis_held
    total_pnl = unrealized_pnl + realized_pnl
    total_return_pct = (total_pnl / total_bought_cost) * 100 if total_bought_cost > 0 else None

    return {
        "shares_held": round(shares_held, 4),
        "avg_cost_per_share": round(avg_cost_per_share, 4) if avg_cost_per_share is not None else None,
        "cost_basis_held": round(cost_basis_held, 2),
        "current_value_held": round(price_for_calc * shares_held, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "realized_pnl": round(realized_pnl, 2),
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": round(total_return_pct, 2) if total_return_pct is not None else None,
    }


def build_concentration_overview(holdings: list, infos: dict, cash_value: float = 0.0) -> dict:
    """
    Berekent de 'at a glance'-portfolio-kenmerken: top-positie%, verdeling
    over Crypto/Dividend/Growth/Other/Cash, en een 0-10-gezondheidsscore
    (concentratie + spreiding + categorie-balans).
    """
    holdings_value = sum(h.get("position_value") or 0 for h in holdings)
    total_value = holdings_value + cash_value

    if total_value <= 0:
        return None

    sorted_holdings = sorted(holdings, key=lambda h: h.get("position_value") or 0, reverse=True)
    top_holding = sorted_holdings[0] if sorted_holdings else None
    top_pct = (top_holding.get("position_value") or 0) / total_value * 100 if top_holding else 0.0

    category_values = {"Crypto": 0.0, "Dividend": 0.0, "Growth": 0.0, "Other": 0.0}
    for h in holdings:
        value = h.get("position_value") or 0
        info = infos.get(h["ticker"], {})
        quote_type = info.get("quoteType", "")
        has_dividend = bool(info.get("dividendRate"))
        if quote_type == "CRYPTOCURRENCY":
            category_values["Crypto"] += value
        elif has_dividend:
            category_values["Dividend"] += value
        elif quote_type in ("EQUITY", "ETF"):
            category_values["Growth"] += value
        else:
            category_values["Other"] += value

    category_pct = {k: v / total_value * 100 for k, v in category_values.items()}
    cash_pct = cash_value / total_value * 100

    max_category_pct = max(list(category_pct.values()) + [cash_pct])

    concentration_score = max(0.0, min(4.0, 4.0 - (top_pct / 100.0) * 8.0))
    n = len(holdings)
    if n <= 2:
        diversification_score = 0.0
    elif n <= 5:
        diversification_score = 1.5
    elif n <= 9:
        diversification_score = 2.5
    else:
        diversification_score = 3.0
    balance_score = max(0.0, 3.0 - (max_category_pct / 100.0) * 3.0)
    score = round(concentration_score + diversification_score + balance_score, 1)

    return {
        "top_holding_name": top_holding["naam"] if top_holding else None,
        "top_holding_pct": round(top_pct, 0),
        "category_pct": {k: round(v, 0) for k, v in category_pct.items()},
        "cash_pct": round(cash_pct, 0),
        "score": score,
    }


def build_correlation_matrix_chart(holdings: list):
    """Berekent de historische rendements-correlatie tussen je posities (6 maanden dagelijks), als heatmap."""
    if len(holdings) < 2:
        return None

    price_series = {}
    for h in holdings:
        try:
            hist = get_cached_ticker_history(h["ticker"], period="6mo")
            if len(hist) >= 20:
                price_series[h["naam"]] = hist["Close"].pct_change().dropna()
        except Exception:
            continue

    if len(price_series) < 2:
        return None

    df_returns = pd.DataFrame(price_series).dropna()
    if df_returns.empty or len(df_returns) < 10:
        return None

    corr = df_returns.corr()

    fig = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=corr.columns.tolist(),
        y=corr.columns.tolist(),
        colorscale=[[0, "#0B4A3E"], [0.5, "#101825"], [1, "#1FAE96"]],
        zmin=-1, zmax=1,
        text=[[f"{v:.2f}" for v in row] for row in corr.values],
        texttemplate="%{text}",
        textfont=dict(size=11, color="#EAEDF1"),
        hovertemplate="%{x} vs %{y}: %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text="Correlation matrix (6-month daily returns)", font=dict(family="Fraunces, serif", size=16, color="#EAEDF1")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=350,
        margin=dict(t=50, b=30, l=80, r=20),
        font=dict(family="Inter, sans-serif", color="#EAEDF1"),
        xaxis=dict(color="#8992A3"),
        yaxis=dict(color="#8992A3"),
    )
    return fig


def create_checkout_session(price_id: str, customer_email: str):
    """Maakt een Stripe Checkout Session aan voor een abonnement, geeft de sessie (met .url) terug."""
    stripe.api_key = st.secrets["stripe"]["secret_key"]
    app_url = st.secrets["app"]["url"]
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        customer_email=customer_email,
        success_url=f"{app_url}/premium?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{app_url}/premium",
    )
    return session


def verify_and_activate_premium(session_id: str) -> tuple:
    """
    Vraagt bij Stripe zelf na (met onze secret key, niet vertrouwend op de
    URL alleen) of deze sessie daadwerkelijk is afgerond. Zo ja: zet
    premium aan voor het bijbehorende e-mailadres.
    """
    stripe.api_key = st.secrets["stripe"]["secret_key"]
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        return False, None

    if session.status == "complete":
        customer_email = None
        if getattr(session, "customer_details", None):
            customer_email = session.customer_details.email
        if not customer_email:
            customer_email = session.customer_email
        if customer_email:
            database.set_premium_status(customer_email, True)
            if getattr(session, "customer", None):
                database.set_stripe_customer_id(customer_email, session.customer)
        return True, customer_email

    return False, None


def create_billing_portal_session(customer_id: str):
    """Maakt een Stripe Billing Portal-sessie aan -- hierin kan de klant zelf opzeggen/betaalmethode wijzigen."""
    stripe.api_key = st.secrets["stripe"]["secret_key"]
    app_url = st.secrets["app"]["url"]
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{app_url}/premium",
    )
    return session


class _CurrentUser:
    """
    Uniforme 'huidige gebruiker'-representatie, ongeacht de inlogmethode
    (Google-OAuth via st.user, OF e-mail+wachtwoord via een eigen
    sessie-cookie). Heeft dezelfde 3 eigenschappen als st.user zelf
    (is_logged_in/email/name), zodat de rest van de site niet hoeft te
    weten HOE iemand precies is ingelogd.
    """
    def __init__(self, is_logged_in: bool, email, name):
        self.is_logged_in = is_logged_in
        self.email = email
        self.name = name


def get_current_user() -> "_CurrentUser":
    """
    Geeft de huidige gebruiker terug -- via Google (st.user, Streamlit's
    eigen OAuth-mechanisme) OF via e-mail+wachtwoord (een eigen sessie,
    bijgehouden in st.session_state en hersteld vanuit een cookie na een
    paginaverversing). Google krijgt voorrang als BEIDE ooit toevallig
    tegelijk actief zouden zijn (zou normaal nooit gebeuren).
    """
    if st.user.is_logged_in:
        return _CurrentUser(True, st.user.email, st.user.name)
    if st.session_state.get("password_auth_email"):
        return _CurrentUser(True, st.session_state["password_auth_email"], st.session_state.get("password_auth_name") or "")
    return _CurrentUser(False, None, None)


# --- Sessie herstellen vanuit een cookie (voor wachtwoord-login) -- lost
#     het probleem op dat een kale st.session_state een paginaverversing
#     niet overleeft (in tegenstelling tot Google-login, dat Streamlit's
#     eigen sessie-mechanisme gebruikt). Gebeurt VOOR get_current_user(),
#     zodat die de herstelde sessie meteen ziet. ---
from streamlit_cookies_controller import CookieController

_cookie_controller = CookieController(key="hestys_cookie_controller")

if "password_auth_email" not in st.session_state:
    # De cookie-component kan bij de ALLEREERSTE run (met name direct na
    # een verse deploy/cold start) z'n JS-round-trip naar de browser nog
    # niet hebben afgerond -- intern is de cookie-store dan nog 'None',
    # en .get() gooit daardoor een TypeError ('argument of type NoneType
    # is not iterable') i.p.v. gewoon 'geen cookie gevonden' terug te
    # geven. Behandel die specifieke situatie hetzelfde als 'geen
    # sessie-token aanwezig' -- de gebruiker wordt dan simpelweg niet
    # automatisch ingelogd op DEZE ene run (Streamlit rerendert vanzelf
    # opnieuw zodra de component wel klaar is), i.p.v. de hele pagina te
    # laten crashen.
    try:
        _session_token = _cookie_controller.get("hestys_session_token")
    except TypeError:
        _session_token = None
    if _session_token:
        import database as _database_for_session_restore
        _restored = _database_for_session_restore.get_user_from_session_token(_session_token)
        if _restored:
            st.session_state["password_auth_email"] = _restored[0]
            st.session_state["password_auth_name"] = _restored[1]

# --- Navigatie: leest de '?view=...'-parameter uit de URL. Geen parameter
#     (zoals bij het eerste bezoek) betekent: nog geen tabblad gekozen. ---
# --- Navigatie: leest de '?view=...'-parameter uit de URL. Geen parameter
#     betekent: nog geen tabblad gekozen -- dan is de standaardpagina
#     afhankelijk van of je bent ingelogd. Niet ingelogd -> Discover (toont
#     meteen echte waarde aan een nieuwe bezoeker, geen account nodig).
#     Wel ingelogd -> Today (de gepersonaliseerde, dagelijkse pagina). ---
current_user = get_current_user()
_default_view = "today" if current_user.is_logged_in else "discover"
current_view = st.query_params.get("view", _default_view)


def _nav_class(view_name: str) -> str:
    return "nav-link active" if current_view == view_name else "nav-link"


def _nav_class_any(view_names: list) -> str:
    return "nav-link active" if current_view in view_names else "nav-link"


# Logo-icoontje (oplopende staafjes + pijl) als base64-PNG -- gegenereerd
# beeld, ingebed als data-URI zodat het werkt ongeacht hosting/deployment,
# geen los statisch bestand nodig.
_LOGO_ICON_B64 = "iVBORw0KGgoAAAANSUhEUgAAAIMAAACgCAYAAAAvpd/+AAAh7klEQVR4nO19e5gcZZnv7/2+mkxCIFyNimK7yMUNyC0cuZ2lEaKw6qJUUhMuCuEWsILcBTSETgdEFOWymEZYNaywKN2h1dVdYVcfmQVXWMgBPZDznHM4ap3DOUIuDEkmk2Sm6nvPH1993dU9fau+zPRk+vc8PGS6q6ur6/vVe3/fD+hhuoAACMdx5GRfSA8TCwIg4DgSWUcyM5Ggyb6mHiYIevGTSQtZR5IQqLD0e2GPA45N5DNnzV+6tK/aSXqYehBwQHAcOHCw9tzFASuOvm8BODSRzxwN4OMA/hLAewAkAIiNV6SOHdm48RUAAoAyH+qRoftBcCCwIUlYNpdTTpbTghRK1h5zMHPmEYnH75kH4CQAJwM4GEB/hfO94dnu0UT0NjMTUDxTjwzdBQJAcBxyHGCeM49XyVWq7KkHgA8l8pkjARwH4EMATgVwUIXzKRQXW0FLjB97trsQnBKgtIoebLXzl/QQC3rhk0kBAKlnnlGrpFCsmJHLIZcrHNefyGdOBHAUgA8DeD+A0wHsWeGcQcm5tRoo/86fASAMrB8nCHqSYeJQ8tSvPffJAMxgLnnqDwAwN5HPHAPgRACHQOv5eRXOF33qKy18+bECwAbPducR0eZyFWFO0kPnIJysQ6hs5AFa3B8K4IMA/hrAsQDei/ESm1FcfLPwcdbOD8/5I892z3OyWZkbGAjKD+qpic5C5QZyAHIAMAuzrCMT//C3x0Jb9ycCOAzAfhU+F6C48GbxWwkWGSnwGwDIRXRQ+UE9tBuplEA6rRL5zAkAPgdgL2gr/7AKR5unHigufjvXxZAK3oB7Evl4nstcSoOeZOgE1heMs/kAroq8E0AvQvSJJ7T21NeDCs//Enz8XjETEY0jAlDb6OihWeRyAQDybDfj2e6HAHwDwB+gF6UPE3/fGcBDAEbotNOqEq+nJjoJZiIhOPQY9k3kMzaA6wAcETkqQHyDMNZVACBvyY1n0daRp1kTcpzxCPQkQ2dBxMwskExaJGjIs93vebb7UQB/A+BpALugF4dQZYFahFFJf8LWkd+DyLxWET0ydB4Kg4M+KyY4jiRBI57t/tyz3bP+3+IbTwTwKIARdMZuML7sTwH8mZ9YJFEWW4iiR4aJAyOXCwwpmJnGxkZe8Wz3wj/b1x4H4DboeIA+tj0w6/s0AEIVl7L84B4mDoxcLiAiBiCdV7MzRjH631GUDEa0t/49+jybPNt9kYgYueoqAuiRYTIhUpzi3JEDKpHP/AxACpoQ7VoTE7F8DsAmVrcJ1JE4vTjD5IBSzEgTqUQ+cxeAT6MYMm7r9wD4CQDgtGcqBprKD+5hYkEpZgqJkAKwEu13L42K2OjZ7hFEtJGZ65KhJxkmFlEiZAB8AZ2JM5io43oAG5VSFNooNdGzGSYOlEylZEiE26GJ4KOzAadfAiAaGKhrL6CDF9FDKcjJZkVuYCBI5DN3A7gRnYs8GhWxzbPdj4DggSsnpsrRkwwTgAgRVqB1IjBqP+XmvU0ANlCdqGMUPTJ0FpRMpayQCF8BsAqtESGa8awGQ5ZfAdjBCxc1HNnskaGDSKZScjCd9hP5zPUAvorWbARDomHop76ahDDnz8b9gh4ZOgNysllDhJsBfAtFC78ZIvjhZ1/wbPckADeF5ykX/0ZyvOHZ7gskCMjlGg5t98jQflAylZKhargdwF1oTLxXQwAdAvhnz3ZPJyle9Wz3HwG8AU2Q6GIbcvwSwFb+0SKJBu0FoEeGtqNMNdwK/VQ3QwSFojR5yLPdRRA0wu4n+gFshokslqa+zXr+AgBhdS7Wd/bI0EbMf2hpX0iEL0GrhgDNqQZT2i4ArPBs90oStAOKCW8+ZciVj5zf2A8CwLBnu78BEWOwcakA9MjQLlAylbTWXfHwWCKfWQVd5mYWNC4RjJH5JgDHs907kqmUxSrsc8ghICHYs91nAfw3FCufzcL/FsCfnSeeiKUigB4Z2gHSqmHQT+Qz1wFYAf3ENqMaTLLqT57tftKz3bVIJa3BdNpHxDbgFStEeOyvzUuR938NQOVWr45tn/QikC3CyToyN5ALEvnMlQAeRPNxBCPyn/ds93wi/JFPTVoYHPQrHEsgMKy+IxNP3P8fAGZBkyH4vxfccJK/c8dL4Oq1jtXQkwzNg3RnUs5EFpslAqNIhB94tvtxEvRHZsgqRAAATqmUwNjYq9CeA8LvfNnfseOlMOoYu6ayR4YmMX/pUhNZvBbNRxaNTpcA7vds9yISYpgVC9RZzPRA2nzP/SiqiRcAIE7UMYoeGZpAMpWy1j388FioGu5Fc0SIfmaJZ7vXpjglWKlKwaTxyEExM3m2+zyKhuRjBMQKNEXRI0NMJFMpKxJHeBDNeQ1GLWwHMODZ7t8j68g0pWslocoNUg4bYrZDN3O+4dnuf1EVuqsbRc+AbByUTCWN13ATgK+jOYlgPIaXPPuapcDYy0hWNRQNBBGpsvb9wnUBmIXZc/fC9g1vxbiO8V/SyoenEcjJZkVIhCuhidBM0skQ4Zee7S4gGnsZ7373bAwOVrcPHEdCE0EC2KPCEQxgpFUiAD0yNAJKppIm13ALiqohTmTReAxmjM45JGgLL4LEW29tR2WxTkgmLeRyAZiPSuQzLybymW8CQCqVqjSRpWUp3yNDbUQDSrcA+BriJ53M8RLASs92bRKkPYZcVY+BnKwjMDjoJ/KZhYl85hnoQR4fBACsXFl+fL2Cl4bQI0MNaBshbVTD1xA/smhsihEAX/BsN51iFmFouZrHIEkQR+IXTwDYNzx+FADW5+IloBpFjwyVQdprGPQT+czVaM5rMDUImwCc69nud7THQNWfYt2LGbDiOYl8Zg10/IIAjIXfPQoA8xynXe13JeiVyo8HRSTCVdBBnbhegzEU/+jZ7tkAXkUyaWEgV91jcByJXC5gPefpRwCOR5FQ5qH1gc5Jhh4ZSkFO1hG5gZyRCPcjnkSIGopPe7a7lIj+Ny9aJJGrSgSR4hTSlA4S+czHoLuy34fKHVbbm/lRjaJHhiKImUFEQViPYNLQjdoIRvxbANZ4tnsFCRpjxTKc5FIJggSpNKWRyGduBXB7+LoZ4FmOjq5Xz2bQICfrCCJCIp/5OjQR4hiL0ZF8d3i2e0mBCNVyDI4jiaBY8QcS+UwWpUSoti4zGv9J8dEjQ6FmMRck8pkboYtN4wSUDGlGASz2bHcFOGU8hkpEIKR0/IAZhyfymV8CcFDsmq61Jh1dr+muJoy+9hP5zBdRlAiNBpTMsdsALPJs91+QzUrQQHR6axRGFfmJfOZsAGug50Ca89TDrgaOaRrTmQzkZLOUpoEgoq/Nk9kIEYyB94Jnu1cA+B0cR6LC5FUAWi08+WRARFaoir4IPfnNRDMbQawytriYrmSg+UvnW7mBgbFQItyOeMaiIcJTuiqJhnhRDUPRcSTWrg2YuT+RzzwC4FyUFrE2io7EFwymJRlCUT0Wuo9x6hGiHkPGs92rSYiAlZJVQsuErCMwkAsAHJPIZ74LPSjUxA/ixgs6mmWebmQwXgMn8pk7AHwFpTOaayFqS3zDs92bWU9brWYoChJCsTZMLwTwAIA5KMYhmkFHDcjp5E1EvYYvQxMhOrO5FgwRtgI4z7Pdm+cvXdoX1hpWEt2SiBQr1Z/IZx4A8PcoEqFrd4+bNpKBBHEYYl6CeKNzjH3wX72Bqy+F778Ix5HrHn64pHy9ABNWZn5vIp95HMBpKM1ctoKeZGgRdMhZZ/Wz4hmJfOYaAN9DMd5fr7XdiPRfebZ7KgXBi4Uag2o1CLlcgJl7JhP5zG+gidDO6SwdtRl2ezLMX7rUev2pp3aF6eD7Im/VIwKgSbPas91PkRDvMHP18vUUBAGcyGfOTzz+jX8G8BdozT6YcOzOZCBkHRlWMV8G4Mso3cOpGqJh6JWe7V6VYh5jpUTkvXHfxSuZGTgQwGro8rSutg8qYXclA6U4RdDG4sUAHkaxkbXWbzYL6ENHFNNhDYLpiAaqqAcSxNBbB5pG2Cl3b6eMCIsBcrKOCFPCd0JLhOjGXtVgiPC6t+TGZdg68i9IJa0wRtDI1wLgUehClKbL1ScTuxsZTD2CKV41qqGeAWc8ht95tvtpAG8gmbSQrlm+Xgn1JE+r6CjBppwoq4EoEdIA7kR9IpRXLZ9Ogt5AEvX6GKqcqu6Wgq2io7mJ3YYMESLcBj2uH6hNhGif47c9211Cgt5mxRKDiCsRdgvsDmSgSFv8tQDSqO81GIkRALjJs90vkhBbG2l43Z0x1ckQVQ3LANyD+jWLxlB8B8BCz3bvdrJZ2XDD626MqWxARkfwXg/gm+Z11CfCf3gD7jL4eAmOU3H31y5FR69zqpKBwCnK6cKUr6KYfdTvjYeZeSQBrPVs9xIi2sbOolrFqnFgvtuHdi2nJKaimtCtZ5RWYTd0veyjKUGTAH7o2e75JMQ25ppVy82iLW1uk4WpRoaojbAcuhu6VoWSMRQFgOs82z2fmf1IaLkiKjS2TgtMJTUR1iOk/ZAId6A+EST0CL2rPNt9EpwS4SYc1QxFU7DarYZkr9IJRWPRD7OPxn2s5jUYIrzo2e75AF5HKiVA6VqLLKWUARHhwA8cfvLihZ98+d57790R8zqjOYxOoK+D554SaoJSzBR6DXdBN6MClYkQNRQf8Wz3TCJ6XYeWqxMhmUxaUsogCIL3LFx47jceeOCep4469dR+AGA9FqeRy4z5s5rCaCdP3u1kICebFeFWPncAuBnVjUWjMgSABz3bvZSEGOLjuK9GaJlSqZQ1ODjoB0Fw/JKLL3/6bx+4/0vzDj+sf/mymz4IACtXrpw2o466WU1E4wirACxHddVgEk07ACzzbHdNilmkiQjrCjUI5VZ+oaFl5ux9Llix4tZHr7j8UpICwf/x3p4xY4bcGwDWr18/bcjQrZIhSoRvQY/grVY+VhixC+B0z3bXgFMiMgehkrsnLMtiItrjhJNO/bsn1+YevfbaqzAyMuyPjo5Kq28GpJTNxAs6bTN0tFimGyVD6D4OBGHn0fWo3PJWXqP4BQD/E8mkBUr7ZccVkEwmrWeffdb3fX/vCy689Hsrln9l4YEHvlttfOtNkkJaQgjNHr0PZFz4KN3PuiNSpfaO1s2j28gQlQhfhW6CraQaos0sP/ZsdzERjemupur2Qdjn4AM45svLVz557TVXH9xnkf/O0Nuyz+ojpRgAMQDyO9zx3I3oJjUhI0S4EzqyWEk1RGsU7/Fsd4CEGNMRxaqBJGFZkolIHX74UZf84qlfrbl1+U0Hq2CnP7x9m2VZRIZfzACB0MimoLsbukUyUOKiZF9uYGBnqBqMRChXDea1nQA+59nuk3W6mgAkLSmf830/2O+ypcsWXfi5Cx867tiPYPPGDUpKYVmCoL1HbWMKwQxi8v3RWR38vV2JbiCDUQ07E/nMfQCuQWXVYAzFP3gX3HABdux4HllHhtHCikWqyVRK/tuqVX4Q8IcuvuyKnyz/8s1H7rvvHH/z2xuEtCxB5SqdCESCwYzAx0wA2LBhw7TxJiabDORwVoTZx69DE6F8llHUUHzBs93PAniz3sAsKSUPptO+nDFr0be+ec+9Sy783Pt37RxWW7cMWX2WpTeBZYALTof+2ygMItWMVyBRtPinHIkm02YQ8x9aaoVEWInixJSo+2QWxALwXc92zyCiN+HU3ItBMjMFQTDrI8cd7/7wh49nl1625P3Dw1uCMT8Q0poR7gbMIRGKX0WkbQYAUAr9TfymKBk6BqdD550sMpDDWQr3dLobQApFiWCeKKMqGLo07XIStJ25+mRVx3FMfoHP/qyz5vvf/f7qT/31WWrTpg0Kuhm22uWgYDMQsVLAztFds9v5g9uEjha3TAYZtI1QLEwxe0NHnygjId6GHsEflqZVn6yazWZlLpcLgiA47raVtz/30IPfXnTowR8INm/cICzLEpWJUJrwZCaAQv6R6nkTHUY0jvA1ALegdHCFSTRZAF72bPcSAK8gmbRyAwO14gcgouA97/sLJ/PtB5Z/4hNnHL1921AwvG2LtKSFypP5Cx+HIYT2Jk16I+5zMvW5M5GSIUqEu6GJEHUfo6Xrj3u2mySiV+A4Ufug5PF2HEdaUjIRiY+f9enrHnv0keyZZy44+p23NwVBEEgh4qjv0sWU3RSBmSBMlGQgkoJDItyH8e5jdLPO6zzbvY8EocJAzeJ2fjq+EADY55LLl/18xfKbj99//73V0OaNLElKDj0FFmFMsSrGpy6YFYLuLG+Z8vMZyMk6ggMlQ9Vg3EcjEQwRhgFc4NnufXXmKAJ6Zxbed9/9z39kzWP/es837zpl9uxZ/e8MvSOEkFJFPIU4RGDmcN5TMy5BYYpLJ/XFlJ72Fh3B+20Ay1D0GqLxg1dD++DFCommEjiOI9euXRsc+uFjPn/3XXf+4JNnLcCGzRsCxSwsq49Yx5ObBINZEUAgSzRTSBKgSOApl6jqpGQQIRH6EvnMd6CJYBbfPD1m9/cziOjFBvZqwrx584iZMXfu3LNOPvlEHhp6exczS0GCquzh1DCMx6ElQ9fWQXYMnSIDkRSKiCgkwhUoqgaTaFIA7vRs1yFBG2pORamAvhlyw/D2YSKC1E90e6Rzu87TIUy5glhBUigO1N6JfOYhAItRJIJREZsBXO7Z7o9DQzF2j+PYqL+vZVngNqpoQwTmru2zm1KzowUJUhyo2Yl85scAPoZST8EC8Ipnu5cRsA6OM4NzuTE0c+8JXEw0GadkPDGIqOGnvaAm0F25/YlCO3+zHoKpeO9EPpNHkQgmqiOg8wunENE6nj+/D7ncKJq0vllFkpU1zhBH7Bckg77wZkTylB7W0S7JEO6tpN6TyGd+Dj0S1zztArpQ9XrPdr8DoxbWrWupJ1GG91xnGM2/WkNo8DIzg/2gmURVlAyd0O/henXGn2gHGWQ4P3nPCBHMXCMLwBvewNXnwfefQ9aRGMi1vWg0XMSWz0OFCoeuNSI72tTbqkgTIRHmlBFBQhPhGc92/wq+/1xYf1BtmGYTUOA25ZJKiERGq8Xl64QQKPySziSxWyGDJEGKlXpXIp/5GYAkdMdPX3je73u2+3Ei+hMwv6/mFr9NoKnSkyoo2BXh/zQ1uteE7FQ9Q7Nqwuy/uH8in3kKwHHQdYkzw/9f6NlujoSA7nheV3nOcgtoh0tZ1dNoSuNMyWl/JWiGDCJChH+EJsIuaCK84g1c7cL3fwtOCaZ0rY7nSUd1T4MAMfXK1lpFXFmo4wiKD0rkM/8E4GToxe6H3r4vSb7/2zC/UK1QNYqmXXrSgYbCSZopbK9kdDIzgYE+KUeaua6JQK5D3kTjC+EYG4H3SeQzPwVwQvjOLgDLw+37tjJq1ieWfLcQgsPq5uaewhaf3XLJQBS+RgxSsqMdz92IRskg6UkKWPEBoddwbPj6n7yLbl7g2e6dTtaRddLOBpRKpYQUQimliJkP7LaGFW1LqDizEAwtLXR4hkInUZ8MTsFYfFcin/kJgFPCd37l2e6Z2Lbt33VZWiNuoyOllJxOp1Wg1IcvXLI0f1v6rtf33HPPw/X73TM+hyyK6f0UJsROWVuj3s2XtJYCVnxYIp/5NYpEuNOz3QVE9D/qlK0XvkdKCSAXBEGw9+kLzrxy9YPffymz+v7PnnTiCbO2bdt2kD4sRvu7qZsGAFBbloBZ2wzMDMG6nmHu3LldJbU6iUpk0Ox2IIkoYOaPJvKZtQCOgK5WvsKz3eXhTatatm7OpcvXhQqCwOrfY48zb7l15fOZ1asfvOA8Z3YwNjo2MjIcAHJ27LXsQPFyMVFFgOwu1TURqORaMpxQIjAfErqP7wawLqxG+n2kra2q2+g4jszn80FO1zB+eOHABX93/Q3XHXX0R46Ys23LEG/e/CbedcBcklJKgPfTd36yW9nCUjkClIplMxh0ej5DR1GJDJLWImDmgxL5zC+gifBTz3aXEOEdPrV2WxuAPmYOwmLVmSed9FcrvuBe6f7N2WfvA6WweeMmJQQJy+oHQBDCAprc1pdIP836iTa1CMU8RdycBTMgdOctlNKJqgZ7LcNaO94FHXQLX5ta9kOpmkgmLQABWzgy3HDrIAC3eLa7mAS9w1zbPkilUkJIMUZEaq+99v3Uvfevzj366A++Yp/zmX22b9sSbN36DluWEIUsY3GhYt80ISRIRC+fIsQIX6lDhPL3i+QCgKaGdUxpFCWD3oLP3w+Ys9cTmV8A8LzF7tkYwyv1294hU6k1fen0xTsBnHz55e75i88dWHbSiR/FyMiwv3nzZmlZltYIKN7w4o2PDyEEisUtWgKMG9rUQGFL+TE6hQ34SjWTwp7SMGQQyOWCRD6zAHpf6N97tnsOAaM8f35fKPIr6UIrlfo1Vq063U+nL54xf/4pty698vIv2ed8Zo4lmYc2v8UQlmX19QHjRLYhQrOSVF8Oh9KY2yKUCXq6PINYxFRdU9/eFEilBDNzIp85Dnqrv9We7X7ayWYDBmRYhFJOBB04ktJPpz/mM/NpD3/3kTWP/cOjt5+32JkzunO7Gh7eStKyhCCBOv1tLYDDNeD4m0pH7Iqy11mTi2MakFPKPKgIC+k0KJ3mg4/8T0Kw+szrr637X0SE3MBA5SST40iZzwfpdJoBHH/OovO/dsN11xx9zNFHvWvHjuHgnaGNwrKkkMKCrnOtToRWOOL7CkoxILUnzOBx54tT8hZGHaGYCWBY1FTfxJSGhXDB//Dqiy8B2iUM3cFyIgghhFK5XBAAM5PJBVeee94FqxYttPfqswhDQxsDIkhdsQygMBoHqEYIaqkByXy2udSx8TRKbYbi061o6rqIzSLqWgoAyFUeu29JKf0gCPpnzp6z6IYbvnTThZ8//6iD3ncghoaGgp07AhGGGEuWRQ+/qLVQLYgGQY3Uw9aEIYQQAkop/TfCoFNXp7AddKIOMkqGqpPWAfhBEBx13ueXXL3koosu/c+nnIjhbVt406a3YFlSRpudY/n1mDxNG5UIJYQlYhCBWHXx6L9JSGGntHGJBZ+yD/3BY0/k7r/3nktPOP5Y9famTcHY6ChJKUnfx/GnMU2sBkYkx4kD1L5wEasnohLGG5HRwR2x+vl3C9QLrAgi4j6iMxacfvphKhjzt27ZIoQQUhTGF8mS05gbW77wFZ9CtEIIpWc2NvF5E7HUI/8EiGT4fwGACRxACG4qKjqVUZMMRxxxBAPAnrP6h7Zu26LATCIMHDFRpLqoSABg/MJXc+OKixk+hMnWfkw9lMc5zDVVCluHsZUuRWdKYhuqgVQgIQQJIg7Gm2vFXpno4psbXK4uyqGfxmYgmopeFhddWyzlJChcatDNWctJbKLZtmXr/lQoVyy6jLoGsXQxK4R3S4gRfV2I8SHkhiEAYNxYz4ZBZpBXIT7BYFaho0pgMZ1zEzXAllCNJH3GqwGu+G/zt2KGarIBQgFNuSLjJUG1CGRTKewpjcbIwKruUxK1E+rd8OIbZX8PNnI1NT7fyEca9T4C7nkTlcA+i0aaVso9CKD+zS85PoYByUrFaqSpUhY//jVCaDj0JrdUPkiIoJH7Xm4sTsgUFG6MEtVc3orn6+7pLR1DQ2pCSOk3qp/b0Q0dCxTPiKy70GzmM0w/A7KhH6yUkkA8e63cc6h+XHPS2Pg0rTzEFdVa86eb6qjt5BtvNuBAP38NehTVXMtKZWb62DC+E8OAtIR2cxtdvHJvp1pEFDAFM9PKZKBDDjlkRkOSIWpW137KK9zYyE2v9L7iybnxNfMa3OHx7S2j7RFIev3110drkyEUDUFg5q2217gyKeNOIiqRRKSAtrYh2fVsaDcU6lYAhwQkonBEf/NLV/vmx7fV9Hyv+sSMSqRGPB2tumJfzgRjElLYRhgJKX2gcVex2qK312VTsYy9Smqqche2/recdiGnOmRY/dprBAD+2Fh/IwtZqXmleuFphRPEylrGL0WqlFKPwmRRJ9w97hLUJMPc9TqFLaXcCZTq3HJUKlqplJwyMC+X3PgY3oSCgq5OK1ZDxoeosPAcErWbwwyTMeCr8J1KihpPS7lEqPV321CDmOXXZTC+8gqIdmJRGMDqfskwCTbDvFBNjPr+HkD1xaxVxFKvnqFZgujcBGratHHPHd2eIOjqOMMkSAZT6SRI6P7KJhY1br9jwxDh9dRZ70rqS19rtQ9q1Sa7Wk10Bg0ZkATS6aBYHc3VI3xVEceAVIXSFNRu1BnvTtZyk5sNj08sJnlccP3ytXiVyq2qZVUyrCPU/w1mVoUQNbuvut9m6AxqSoZloZqw+vp21atVLLcb6oErKfy4xS0o9VzqHWP+rQ3b6LUUXJvx1xQPu//2x4IEETVWgNp4YAoodE83ASEI5R5OrWBX5dJ9/V95kWzBZ42Pltk0mZg0K8mQoFlvgqQIp8BXDxJFpUY1Q7Ke+ptOmOgdb0tQXAhTldw4BKLDOup/Tw/10ZBkICoa7W01rsicT8SOIKqwo0qjevyjWl1mRYJw4YBpVs6g0RAZgiCwOKw1bOUpq/TZpsnF2q0sTG6p873VurxKLwZhTeX0lCQ11cRrJlHl+/3msamlnxuthC4sTiuSpqzfglC9uKapiu3ujDl11Dit+ZPXmwiklDtNpLbabWxUYpRWKZe6eLF7LQuV0bUjkQ0bigWjFt2qJjra2NOga0mqsGYtGmOlVj3GuYeNQkQvndtoJNL0NTgbS1SN+rMqdCk3/aVFddH0KSBk495EPOhzBkFX7lHVUTS38UebPIpWTkNtGh7eQxE1yfBM8Z/FTccjhmKlaSxxwAUDspUas/FdXC2LeebWLmmKoqHcRH//jOHi4Lbayaq4aHXhyj/eCjnNx4ioiRT21BdTDUUg+2fOHCGqLQliLwABrZbeG5uhXWqLOZR63Zu1nDzX0sQZtg9vO6B4f0SV/+JBc4HATfpwuqGKoLOpZohIYxjPP+N6NnUpUQQodlx0wqKcAwApZ15HrNWGJIOvAisIWDErFQS7RHHqSTlqBZ44YiMwgkAhCBQrxU3t0RAEzH4QMBFzEIwW6tXqpdJL3+fCdQEEpRSCYAb7/phqcncT81SYnftajVaYNKrZ1K2jU2sbTFSJ/n3221/sPWeW8MfGCv0F4xe+SojXwPw0BvwgwJy99uzbe+99AWBW3AsXluzff/8DiGi0TymASvcpKjNyS7OkxWxmGMpmgBXDDwLMmjWrb5999oEgirlhGTOA/QC8N+5vaQCGZP0AsD53REfURT0yaGaT+Ne77rrrMkE0g1kRmVxAGJY0fxPMjTeLQpGwZak3wgye0T+Dh7ZsfRN9e/wOY1uAwdNUvQqX9evXMwCM+Sq/Mn37GYp9MOsLEKQjkQp6caUIxwHD9HTqfAYpPU+KRNHuUKwQ+Ap9loXtIzt3SZr57wBw2mmnqcHBulU3zApEhI0Avge9J7gMf3R09HL50yMAmOGjMvI+Q+8pvgvAntASgQE8CwDzXnutI2oiDsPM09vOCxEAdjRxTkOxmW28ligUWhfJZnFV2d/lMPO7oxU2AGA2eekL/x15wjoT4WqUDGRZVkcugJkRBIFATP3KzNTX19fJa2rmplOKU7RK3t6ErWB0aI0jVqwQSKeBDmVO/j/2bXvcEP566wAAAABJRU5ErkJggg=="


# ============================================================
# PAGINA-FUNCTIES (stap A van de navigatie-herstructurering: elke
# pagina wordt een losse functie, ZONDER de routing zelf al te wijzigen
# -- dat komt in stap B. Voor nu wordt elke functie nog gewoon aangeroepen
# vanuit de bestaande if/elif-keten op basis van current_view.)
# ============================================================

def _conviction_tile_html(icon: str, label: str, weight_pct: float, warn: bool = False) -> str:
    """1 van de 3 conviction-tegels bovenaan Analyze -- totaal portfolio-gewicht per score-bucket."""
    border = "rgba(217,119,6,0.5)" if warn else "rgba(30,41,59,0.4)"
    warn_html = (
        '<div class="hesty-conviction-tile-warn">&#128680; Exceeds safe limit</div>'
        if warn else ""
    )
    return (
        f'<div class="hesty-conviction-tile" style="background:rgba(15,23,42,0.3); border:1px solid {border};">'
        f'<div class="hesty-conviction-tile-label">{icon} {label}</div>'
        f'<div class="hesty-conviction-tile-value">'
        f'{weight_pct:.0f}% <span class="hesty-conviction-tile-suffix">of portfolio</span></div>'
        f'{warn_html}'
        f'</div>'
    )


def _render_conviction_table(entries: list, key_prefix: str, unmapped: list = None) -> None:
    """
    Tabel opgebouwd met NATIVE st.columns() -- 4 kolommen (Asset/Score/
    Last validated/Action). De Core Thesis-kolom is verwijderd; die
    tekst leeft nu bovenin de geopende drawer i.p.v. afgekapt in de
    tabel. De klikbare actie blijft geisoleerd in een EIGEN, smalle
    kolom (potlood-icoon om bestaande research te openen, sterretje
    voor unmapped assets) -- puur platte st.markdown()-tekst voor de
    rest, exact de cellen die altijd al feilloos uitlijnden.
    """
    if not entries and not unmapped:
        st.markdown(
            '<div style="color:#64748B; font-size:0.82rem; padding:1rem 0.25rem;">Nothing here yet.</div>',
            unsafe_allow_html=True,
        )
        return

    # Eerste ~10 rijen zichtbaar, de rest bereikbaar via een normale
    # verticale scrollbalk (geen apart slider-element) -- alleen de
    # RIJEN zelf scrollen, de koptekst blijft gewoon zichtbaar.
    _unmapped = unmapped or []
    _total_rows = len(entries) + len(_unmapped)
    _scroll_rows = _total_rows > 10

    # Verhoudingen naar echte content-breedte (logo+ticker / score /
    # datum), niet naar "vult de rest van het scherm" -- dat laatste
    # gaf op een brede pagina juist een enorm, leeg ogend Last
    # Validated-vak. De tabel als GEHEEL wordt nu ook smaller gehouden
    # (max-width hieronder) i.p.v. altijd de volle containerbreedte
    # op te eisen.
    _col_ratios = [1.7, 1.1, 1, 0.45]
    _table_key = f"{key_prefix}_table"
    st.markdown(
        f'<style>'
        # Tabel als geheel smaller dan de volle breedte -- de daadwerke-
        # lijke oorzaak van de lege ruimte was niet de kolomverdeling,
        # maar dat de hele tabel geforceerd tot de containerrand werd
        # uitgerekt terwijl de inhoud (logo/ticker/score/datum) daar
        # nooit voor bedoeld was.
        f'.st-key-{_table_key} {{ overflow-x:hidden !important; max-width:760px !important; }} '
        f'.st-key-{_table_key} [data-testid="stHorizontalBlock"] {{ align-items:center !important; }} '
        f'.st-key-{_table_key} [data-testid="stColumn"] {{ '
        f'display:flex !important; flex-direction:column !important; justify-content:center !important; }} '
        # Asset/Score: geen tekst-terugloop, zodat ze echt strak/compact
        # tegen elkaar aan blijven staan i.p.v. los te wrappen.
        f'.st-key-{_table_key} [data-testid="stColumn"]:nth-of-type(1), '
        f'.st-key-{_table_key} [data-testid="stColumn"]:nth-of-type(2) {{ white-space:nowrap !important; }} '
        # Action-kolom (potlood/sterretje): hard tegen de rechterrand.
        f'.st-key-{_table_key} [data-testid="stColumn"]:nth-of-type(4) {{ '
        f'align-items:flex-end !important; padding-right:15px !important; }} '
        f'.st-key-{_table_key} button {{ '
        f'background:transparent !important; border:1px solid rgba(148,163,184,0.25) !important; '
        f'border-radius:6px !important; padding:2px 6px !important; box-shadow:none !important; '
        f'font-size:0.85rem !important; min-height:unset !important; height:auto !important; }} '
        f'.st-key-{_table_key} button:hover {{ border-color:rgba(31,174,150,0.5) !important; background:rgba(31,174,150,0.08) !important; }} '
        f'.hesty-conviction-thead {{ color:#64748B; font-size:0.65rem; font-weight:700; text-transform:uppercase; '
        f'letter-spacing:0.05em; }} '
        # Rijen-container: vaste hoogte (~10 rijen) met een eigen
        # verticale scrollbalk zodra er meer rijen zijn -- de koptekst
        # zelf blijft erboven staan, buiten dit scrollende vak.
        f'.st-key-{_table_key}_rows {{ max-height:620px; overflow-y:auto; overflow-x:hidden; padding-right:4px; }} '
        f'.st-key-{_table_key}_rows::-webkit-scrollbar {{ width:6px; }} '
        f'.st-key-{_table_key}_rows::-webkit-scrollbar-track {{ background:transparent; }} '
        f'.st-key-{_table_key}_rows::-webkit-scrollbar-thumb {{ background:rgba(148,163,184,0.25); border-radius:3px; }} '
        f'.st-key-{_table_key}_rows::-webkit-scrollbar-thumb:hover {{ background:rgba(148,163,184,0.4); }} '
        # Mobiel (<640px): st.columns() stapelt van zichzelf verticaal --
        # forceer de rij hard terug naar 1 horizontale lijn, en maak
        # alles compacter als extra vangnet.
        f'@media (max-width:640px) {{ '
        f'.st-key-{_table_key} [data-testid="stHorizontalBlock"] {{ '
        f'flex-direction:row !important; flex-wrap:nowrap !important; gap:0.35rem !important; }} '
        f'.st-key-{_table_key} [data-testid="stColumn"] {{ '
        f'min-width:0 !important; width:auto !important; padding:0 !important; box-sizing:border-box !important; }} '
        f'.st-key-{_table_key} img {{ width:18px !important; height:18px !important; }} '
        f'.st-key-{_table_key} button {{ padding:1px 5px !important; font-size:0.72rem !important; }} '
        f'.hesty-conviction-thead {{ font-size:0.58rem !important; }} '
        f'.st-key-{_table_key} span {{ font-size:0.68rem !important; }} '
        f'}} '
        f'</style>',
        unsafe_allow_html=True,
    )
    with st.container(key=_table_key):
        head_cols = st.columns(_col_ratios, gap="small")
        head_cols[0].markdown('<div class="hesty-conviction-thead">Asset</div>', unsafe_allow_html=True)
        head_cols[1].markdown('<div class="hesty-conviction-thead">Score</div>', unsafe_allow_html=True)
        head_cols[2].markdown('<div class="hesty-conviction-thead">Last validated</div>', unsafe_allow_html=True)
        head_cols[3].markdown(
            '<div class="hesty-conviction-thead" style="text-align:right;">&nbsp;</div>', unsafe_allow_html=True
        )
        st.markdown(
            '<div style="width:100%; height:1px; background-color:#334155; margin:0.4rem 0 0.3rem 0;"></div>',
            unsafe_allow_html=True,
        )

        with st.container(key=f"{_table_key}_rows"):
            for entry in entries:
                ticker = entry.get("ticker", "")
                naam = entry.get("naam", ticker)
                score = _compute_deep_dive_overall_score(entry)
                if score is not None:
                    if score >= 8:
                        _score_color = "#34D399"
                    elif score >= 5.5:
                        # Grens voor rood ligt op 5.5, niet 5.0 -- consistent
                        # met Nederlandse schoolcijfer-logica ('onvoldoende'
                        # begint onder een 5.5).
                        _score_color = "#FBBF24"
                    else:
                        _score_color = "#FB7185"
                    score_html = f'<span style="color:{_score_color}; font-weight:700; font-size:0.82rem;">{score:.1f} / 10</span>'
                else:
                    score_html = '<span style="color:#64748B; font-size:0.82rem;">-</span>'
                last_validated = (entry.get("created_at") or "")[:10] or "-"
                logo_url = get_company_logo_url(ticker, naam)
                logo_html = (
                    f'<img src="{logo_url}" style="width:24px; height:24px; border-radius:50%; object-fit:contain; '
                    f'background:#fff; vertical-align:middle;" />'
                    if logo_url else
                    f'<span style="display:inline-flex; width:24px; height:24px; border-radius:50%; '
                    f'background:rgba(137,146,163,0.15); align-items:center; justify-content:center; '
                    f'vertical-align:middle;"><span style="color:#8992A3; font-weight:700; '
                    f'font-size:0.62rem;">{(ticker[:1] or "?").upper()}</span></span>'
                )

                row_cols = st.columns(_col_ratios, gap="small")
                with row_cols[0]:
                    st.markdown(
                        f'<div style="display:flex; align-items:center; gap:0.5rem;">{logo_html}'
                        f'<div style="min-width:0;">'
                        f'<div style="color:#ffffff; font-weight:700; font-size:0.85rem; letter-spacing:0.03em; '
                        f'text-transform:uppercase; line-height:1.2; white-space:nowrap; overflow:hidden; '
                        f'text-overflow:ellipsis;">{ticker}</div>'
                        f'<div style="color:#8992A3; font-size:0.68rem; line-height:1.2; white-space:nowrap; '
                        f'overflow:hidden; text-overflow:ellipsis;">{naam}</div>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )
                with row_cols[1]:
                    st.markdown(score_html, unsafe_allow_html=True)
                with row_cols[2]:
                    st.markdown(f'<span style="color:#64748B; font-size:0.75rem;">{last_validated}</span>', unsafe_allow_html=True)
                with row_cols[3]:
                    if st.button("\u270F\uFE0F", key=f"edit_{key_prefix}_{ticker}", help=f"Open {ticker}"):
                        st.session_state["selected_research"] = ticker
                        # Schone start: reset de sub-tab-keuze in de drawer
                        # naar de eerste tab, zodat je nooit op een tab
                        # belandt die van een eerdere, andere ticker
                        # over is blijven staan in session_state.
                        st.session_state["dd_active_subtab"] = "1-CLICK BRIEFING"
                        st.session_state[f"dd_view_active_subtab_{ticker}"] = "1-CLICK BRIEFING"
                        st.rerun()
                st.markdown(
                    '<div style="width:100%; height:1px; background-color:#1E293B; margin:0.3rem 0;"></div>',
                    unsafe_allow_html=True,
                )

            for u in (unmapped or []):
                u_ticker = u.get("ticker", "")
                u_naam = u.get("naam", u_ticker)
                u_logo_url = get_company_logo_url(u_ticker, u_naam)
                u_logo_html = (
                    f'<img src="{u_logo_url}" style="width:24px; height:24px; border-radius:50%; object-fit:contain; '
                    f'background:#fff; vertical-align:middle;" />'
                    if u_logo_url else
                    f'<span style="display:inline-flex; width:24px; height:24px; border-radius:50%; '
                    f'background:rgba(137,146,163,0.1); align-items:center; justify-content:center; '
                    f'vertical-align:middle;"><span style="color:#64748B; font-weight:700; '
                    f'font-size:0.62rem;">{(u_ticker[:1] or "?").upper()}</span></span>'
                )

                row_cols = st.columns(_col_ratios, gap="small")
                with row_cols[0]:
                    st.markdown(
                        f'<div style="display:flex; align-items:center; gap:0.5rem;">{u_logo_html}'
                        f'<div style="min-width:0;">'
                        f'<div style="color:#94A3B8; font-weight:700; font-size:0.85rem; letter-spacing:0.03em; '
                        f'text-transform:uppercase; line-height:1.2; white-space:nowrap; overflow:hidden; '
                        f'text-overflow:ellipsis;">{u_ticker}</div>'
                        f'<div style="color:#64748B; font-size:0.68rem; line-height:1.2; white-space:nowrap; '
                        f'overflow:hidden; text-overflow:ellipsis;">{u_naam}</div>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )
                with row_cols[1]:
                    st.markdown(
                        '<span style="color:#a7f3d0; background-color:rgba(16,185,129,0.1); '
                        'border:1px solid rgba(52,211,153,0.2); border-radius:0.375rem; padding:2px 8px; '
                        'font-size:0.68rem; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; '
                        'display:inline-block;">\u2726 AI Ready</span>',
                        unsafe_allow_html=True,
                    )
                with row_cols[2]:
                    st.markdown('<span style="color:#64748B; font-size:0.75rem;">-</span>', unsafe_allow_html=True)
                with row_cols[3]:
                    if st.button("\u2726", key=f"scan_{key_prefix}_{u_ticker}", help=f"Run AI scan on {u_ticker}"):
                        st.session_state["dd_ticker_input"] = u_ticker
                        st.session_state["dd_naam_input"] = u_naam
                        st.session_state["selected_research"] = "__NEW__"
                        # Zelfde schone-start-reset als bij een bestaande
                        # ticker: de drawer opent gegarandeerd op '1-Click
                        # Briefing', nooit op een tab die nog van een eerdere
                        # sessie over was.
                        st.session_state["dd_active_subtab"] = "1-CLICK BRIEFING"
                        st.rerun()
                st.markdown(
                    '<div style="width:100%; height:1px; background-color:#1E293B; margin:0.3rem 0;"></div>',
                    unsafe_allow_html=True,
                )

def _detect_ai_response_language(user_email: str = None) -> str:
    """
    Bepaalt in welke taal AI-tekst (Cockpit Briefing, Cognitive Scan) moet
    antwoorden. Volgorde:

    1. Een expliciete, handmatige override in Settings ('ai_response_
       language' = 'nl'/'en') -- wint altijd. Bedoeld als vangnet voor als
       de automatische detectie hieronder een keer misgaat (bv. een
       CDN/proxy die de Accept-Language-header aanpast of wegfiltert
       voordat die de app bereikt), zonder de automatische detectie voor
       ALLE andere (nieuwe, niet-ingelogde) bezoekers te moeten opgeven.
    2. Automatische detectie via de Accept-Language-header van de browser
       -- geen opslag nodig, werkt voor iedere bezoeker.

    GEVONDEN, VERBETERDE PARSING: zoekt nu naar 'nl' OVERAL in de volledige
    taal-lijst (elk onderdeel van de komma-gescheiden Accept-Language-
    header), niet alleen in het EERSTE/primaire onderdeel. Een header als
    'en-US,nl;q=0.9' (bv. Engelse OS-taal, maar Nederlands wel als 2e
    voorkeur) gaf voorheen ten onrechte Engels terug, puur omdat alleen de
    eerste taal werd bekeken.
    """
    if user_email:
        try:
            import database as _lang_db
            override = _lang_db.get_user_preferences(user_email).get("ai_response_language")
            if override == "nl":
                return "Dutch (Nederlands)"
            if override == "en":
                return "English"
        except Exception:
            pass

    try:
        _accept_language = st.context.headers.get("Accept-Language", "")
    except Exception:
        _accept_language = ""
    _lang_tags = [
        tag.split(";")[0].strip().split("-")[0].lower()
        for tag in _accept_language.split(",") if tag.strip()
    ]
    return "Dutch (Nederlands)" if "nl" in _lang_tags else "English"


def _run_ai_cockpit_briefing(ticker: str, naam: str, user_email: str, field_prefix: str = "dd", key_suffix: str = "") -> bool:
    """
    Roept Claude Haiku 4.5 aan om een ticker te onderzoeken. Vult UITSLUITEND
    het formulier (session_state) -- slaat NIETS meer rechtstreeks op in
    Supabase. Eerder sloeg deze functie meteen op en navigeerde je door
    naar de alleen-lezen weergave, waarna je apart op 'Edit' moest klikken
    om de rest van de deep-dive (Valuation, Technical, Position sizing,
    Sell criteria/trigger) alsnog in te vullen -- een onnodige, verwarrende
    tussenstap. Nu blijf je gewoon in hetzelfde, doorlopende formulier
    staan: je ziet meteen wat de AI heeft ingevuld, kunt het bijstellen,
    vult zelf de rest aan, en klikt pas daarna zelf op 'Save Complete
    Deep-Dive ->'.

    Vult ALLEEN Management- en Bear Case-scores (die hebben allebei ECHTE
    tekstuele onderbouwing van de AI: management_assessment/bear_case).
    Valuation- en Catalysts-scores blijven bewust op hun neutrale 5.0
    staan -- de AI schrijft daar geen tekst over, en die 2 velden staan
    juist op de tabs 'My Conviction'/'Exit Matrix', die je eigen oordeel
    horen te representeren, niet een AI-gok zonder onderbouwing.

    field_prefix/key_suffix bepalen WELK formulier gevuld wordt: het
    nieuwe-positie-formulier (field_prefix='dd', key_suffix='') of het
    bewerk-formulier van een bestaande versie (field_prefix='dd_edit',
    key_suffix=f'_{version_id}').

    Model-ID 'claude-haiku-4-5-20251001' -- de precieze, huidige API-ID
    voor Claude Haiku 4.5 ('claude-3-5-haiku' uit het oorspronkelijk
    aangeleverde voorbeeld bestaat niet als volledig, geldig API-ID).
    """
    import json
    try:
        from anthropic import Anthropic
    except ImportError:
        st.error("The 'anthropic' package isn't installed -- add it to requirements.txt (pip install anthropic).")
        return False

    api_key = st.secrets.get("ANTHROPIC_API_KEY") or st.secrets.get("anthropic", {}).get("api_key")
    if not api_key:
        st.error(
            "AI research isn't configured yet -- add an ANTHROPIC_API_KEY (or an "
            "[anthropic] api_key = \"...\" section) to your Streamlit secrets."
        )
        return False

    client = Anthropic(api_key=api_key)

    _response_language = _detect_ai_response_language(user_email)

    system_prompt = (
        "You are the Hestys AI Research Assistant. Analyze the requested stock ticker. "
        "Respond with ONLY a raw JSON object -- no markdown code fences, no commentary before or after. "
        f"The JSON keys themselves must stay in English exactly as specified, but ALL TEXT VALUES "
        f"(business_overview, investment_thesis, bear_case, management_assessment) MUST be written "
        f"in {_response_language}, in uppercase (ALL-CAPS). Crisp, professional, institutional-grade "
        "insights. No chatty intros or fluff. Max 3 punchy points per text field, separated by ' | '."
    )
    user_prompt = f"""Analyze the ticker {ticker} ({naam}). Return a JSON object with exactly these keys:
- "business_overview" (string): what the company does and its business model
- "investment_thesis" (string): the bull case for a long-term position
- "bear_case" (string): the biggest fundamental risks
- "management_assessment" (string): a quick evaluation of the CEO and governance
- "management_score", "bear_case_score" (numbers, 0.0-10.0, half-point increments like 6.5 or 7.0 allowed): your rating of management quality and how manageable the bear case is, higher always meaning more favorable for a buy decision. These become the DEFAULT position of the corresponding sliders in the app -- the user can still drag them to a different value afterwards.

Respond with ONLY the JSON object, starting with {{ and ending with }}."""

    with st.spinner(f"\u2726 Engaging Anthropic Intelligence System... scanning {ticker}"):
        try:
            _api_kwargs = dict(
                model="claude-haiku-4-5-20251001",
                max_tokens=1200,
                temperature=0.2,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt},
                    # Prefill dwingt het model tot een schoon JSON-antwoord
                    # zonder omliggende tekst of markdown-codeblokken --
                    # betrouwbaarder dan alleen de instructie in de prompt.
                    {"role": "assistant", "content": "{"},
                ],
            )
            try:
                message = client.messages.create(**_api_kwargs)
            except TypeError as _te:
                # Sommige (oudere/afwijkende) versies van het 'anthropic'-
                # pakket accepteren 'temperature' niet als keyword-argument
                # op messages.create(). I.p.v. de hele scan te laten
                # crashen, proberen we het gewoon nog 1x ZONDER die
                # parameter -- temperature is een fijne-afstelling, geen
                # essentieel onderdeel; de scan werkt prima met de
                # standaardwaarde van de SDK zelf.
                if "temperature" in str(_te):
                    _api_kwargs.pop("temperature", None)
                    message = client.messages.create(**_api_kwargs)
                else:
                    raise
            raw_text = "{" + message.content[0].text
            ai_data = json.loads(raw_text)
        except json.JSONDecodeError:
            st.error("AI scan failed: the model didn't return valid JSON. Please try again.")
            return False
        except Exception as e:
            st.error(f"AI scan failed: {e}")
            return False

    def _safe_score(key):
        try:
            return max(1.0, min(10.0, float(ai_data.get(key, 5.0))))
        except (TypeError, ValueError):
            return 5.0

    _management_score = _safe_score("management_score")
    _bear_case_score = _safe_score("bear_case_score")

    # Formulier vullen (session_state) -- GEEN database-write hier. Voor
    # sliders ook de '_committed'-variant meteen zetten, want dat is de
    # bron-van-waarheid die het formulier bij het opslaan daadwerkelijk
    # leest (zie de 'committed'-toelichting elders in dit bestand).
    _ss = st.session_state
    _ss[f"{field_prefix}_business{key_suffix}"] = ai_data.get("business_overview") or ""
    _ss[f"{field_prefix}_business_committed{key_suffix}"] = ai_data.get("business_overview") or ""
    _ss[f"{field_prefix}_thesis{key_suffix}"] = ai_data.get("investment_thesis") or ""
    _ss[f"{field_prefix}_thesis_committed{key_suffix}"] = ai_data.get("investment_thesis") or ""
    _ss[f"{field_prefix}_bear{key_suffix}"] = ai_data.get("bear_case") or ""
    _ss[f"{field_prefix}_bear_committed{key_suffix}"] = ai_data.get("bear_case") or ""
    _ss[f"{field_prefix}_management{key_suffix}"] = ai_data.get("management_assessment") or ""
    _ss[f"{field_prefix}_management_committed{key_suffix}"] = ai_data.get("management_assessment") or ""
    _ss[f"{field_prefix}_bear_score{key_suffix}"] = _bear_case_score
    _ss[f"{field_prefix}_bear_score_committed{key_suffix}"] = _bear_case_score
    _ss[f"{field_prefix}_management_score{key_suffix}"] = _management_score
    _ss[f"{field_prefix}_management_score_committed{key_suffix}"] = _management_score

    st.success(
        f"AI briefing for {ticker} generated -- review it below, fill in the rest "
        f"(Valuation, Technical, etc.), then save when you're ready."
    )
    return True


def _dd_label(text: str) -> None:
    """Compacte, gedempte ALL-CAPS metadata-subkop -- vervangt de eerdere
    lange, informele '**Label** -- uitleg'-subteksten volledig."""
    st.markdown(
        f'<span style="font-size:11px; font-weight:700; letter-spacing:0.05em; color:#64748B; '
        f'text-transform:uppercase; margin-bottom:0.35rem; display:block;">{text}</span>',
        unsafe_allow_html=True,
    )


def _dd_slider_value_html(key: str, default: float = 5.0) -> None:
    """Toont de huidige slider-waarde groot, in text-emerald-400, VLAK
    boven de slider zelf (i.p.v. Streamlit's eigen, ongestylede getal)."""
    _val = st.session_state.get(key, default)
    st.markdown(
        f'<span style="color:#34D399; font-weight:800; font-size:1.1rem;">{_val:.1f}</span>'
        f'<span style="color:#64748B; font-size:0.7rem;"> / 10</span>',
        unsafe_allow_html=True,
    )


def _render_deep_dive_add_form(user_email: str) -> None:
    """
    Formulier om een nieuwe deep-dive (of een bijgewerkte versie) te
    loggen -- verhuisd vanaf de hoofdpagina naar de side-drawer. Nu
    opgedeeld in 3 interne sub-tabs (1-Click Briefing / My Conviction /
    Exit Matrix) i.p.v. 1 lange, kilometerslange lijst -- alle velden
    blijven gewoon in session_state staan ongeacht welke tab actief is,
    dus wisselen van tab verliest nooit ingevoerde data.
    """
    import database

    _ai_btn_key = "dd_ai_briefing_btn_wrap"

    _dd_label("Ticker")
    dd_ticker = st.text_input("Ticker", placeholder="e.g. TSLA", key="dd_ticker_input", label_visibility="collapsed").strip().upper()

    if dd_ticker and dd_ticker != st.session_state.get("dd_last_looked_up_ticker"):
        st.session_state["dd_last_looked_up_ticker"] = dd_ticker
        try:
            auto_info = get_cached_ticker_info(dd_ticker)
            auto_name = auto_info.get("longName") or auto_info.get("shortName")
            if auto_name:
                st.session_state["dd_naam_input"] = auto_name
        except Exception:
            pass

    _dd_label("Name")
    dd_naam = st.text_input("Name", placeholder="e.g. Tesla Inc.", key="dd_naam_input", label_visibility="collapsed")
    dd_currency_symbol = _currency_symbol_for_ticker(dd_ticker) if dd_ticker else "\u20ac"

    # --- Interne sub-tab-schakelaar -- st.pills, vlakke/minimalistische
    # stijl matchend met de rest van het platform. ---
    st.markdown(
        f'<style>'
        f'[data-testid="stPills"] {{ margin-bottom:0.75rem !important; }} '
        f'</style>',
        unsafe_allow_html=True,
    )
    _dd_tab = st.pills(
        "Section", ["1-CLICK BRIEFING", "MY CONVICTION", "EXIT MATRIX"],
        default="1-CLICK BRIEFING", key="dd_active_subtab", label_visibility="collapsed",
    )

    if _dd_tab == "1-CLICK BRIEFING":
        st.markdown(
            f'<style>'
            f'.st-key-{_ai_btn_key} {{ margin-top:0.5rem !important; margin-bottom:1.5rem !important; }} '
            f'.st-key-{_ai_btn_key} button {{ '
            f'width:100% !important; background:rgba(2,6,23,0.8) !important; color:#a7f3d0 !important; '
            f'border:1px solid rgba(16,185,129,0.2) !important; font-size:0.72rem !important; '
            f'font-weight:700 !important; text-transform:uppercase !important; letter-spacing:0.15em !important; '
            f'padding:0.75rem 1.5rem !important; border-radius:12px !important; '
            f'box-shadow:0 8px 24px rgba(0,0,0,0.35) !important; transition:all 0.3s ease !important; }} '
            f'.st-key-{_ai_btn_key} button:hover {{ background:rgba(15,23,42,0.9) !important; '
            f'border-color:rgba(16,185,129,0.35) !important; }} '
            f'</style>',
            unsafe_allow_html=True,
        )
        with st.container(key=_ai_btn_key):
            if st.button("\u2726 Generate Anthropic Intelligence Briefing", key="dd_ai_briefing_btn"):
                _briefing_ticker = dd_ticker
                _briefing_naam = dd_naam or _briefing_ticker
                if not _briefing_ticker:
                    st.error("Fill in a ticker above first, then generate the briefing.")
                else:
                    if _run_ai_cockpit_briefing(_briefing_ticker, _briefing_naam, user_email):
                        # Blijft in HETZELFDE formulier staan -- geen navigatie
                        # meer naar de alleen-lezen weergave. De widgets
                        # hieronder lezen hun (nu net gevulde) session_state
                        # meteen in deze zelfde run.
                        st.rerun()

        # GEVONDEN BUG: Streamlit verwijdert de session_state-waarde van een
        # widget zodra die widget in een rerun niet getekend wordt (bv. na
        # navigeren naar een andere wizard-tab) -- exact de reden waarom de
        # '_committed'-truc hieronder al langer voor de score-sliders
        # bestond, maar nooit was toegepast op deze tekstvelden. Zonder dit
        # gingen Business overview/Investment thesis/Core risks/Management
        # check STIL verloren zodra je naar 'My Conviction'/'Exit Matrix'
        # doorklikte -- de Save-knop op Exit Matrix vond dan alleen nog lege
        # tekstvelden terug (de scores overleefden wel, want die hadden de
        # bescherming al). 'value=' leest nu ook uit de committed-sleutel,
        # zodat teruggaan naar een eerdere tab de eerder getypte tekst ook
        # weer laat zien i.p.v. een leeg vak.
        _dd_label("Business overview")
        st.session_state["dd_business_committed"] = st.text_area(
            "Business overview", value=st.session_state.get("dd_business_committed", ""),
            label_visibility="collapsed", key="dd_business", height=90,
        )

        _dd_label("Investment thesis")
        st.session_state["dd_thesis_committed"] = st.text_area(
            "Investment thesis", value=st.session_state.get("dd_thesis_committed", ""),
            label_visibility="collapsed", key="dd_thesis", height=90,
        )

        _dd_label("Core risks")
        st.session_state["dd_bear_committed"] = st.text_area(
            "Core risks", value=st.session_state.get("dd_bear_committed", ""),
            label_visibility="collapsed", key="dd_bear", height=90,
        )
        _dd_slider_value_html("dd_bear_score")
        st.session_state["dd_bear_score_committed"] = st.slider(
            "Risk score", 1.0, 10.0, 5.0, step=0.5, key="dd_bear_score", label_visibility="collapsed",
        )

        _dd_label("Management check")
        st.session_state["dd_management_committed"] = st.text_area(
            "Management check", value=st.session_state.get("dd_management_committed", ""),
            label_visibility="collapsed", key="dd_management", height=90,
        )
        _dd_slider_value_html("dd_management_score")
        st.session_state["dd_management_score_committed"] = st.slider(
            "Management score", 1.0, 10.0, 5.0, step=0.5, key="dd_management_score", label_visibility="collapsed",
        )

    elif _dd_tab == "MY CONVICTION":
        _dd_label("Technical notes")
        st.session_state["dd_technical_analysis_committed"] = st.text_area(
            "Technical notes", value=st.session_state.get("dd_technical_analysis_committed", ""),
            label_visibility="collapsed", key="dd_technical_analysis", height=90,
        )
        _dd_slider_value_html("dd_technical_analysis_score")
        st.session_state["dd_technical_analysis_score_committed"] = st.slider(
            "Technical score", 1.0, 10.0, 5.0, step=0.5, key="dd_technical_analysis_score", label_visibility="collapsed",
        )

        _dd_label("Catalysts notes")
        st.session_state["dd_catalysts_committed"] = st.text_area(
            "Catalysts notes", value=st.session_state.get("dd_catalysts_committed", ""),
            label_visibility="collapsed", key="dd_catalysts", height=90,
        )
        _dd_slider_value_html("dd_catalysts_score")
        st.session_state["dd_catalysts_score_committed"] = st.slider(
            "Catalysts score", 1.0, 10.0, 5.0, step=0.5, key="dd_catalysts_score", label_visibility="collapsed",
        )

        _dd_label("Position sizing plan")
        st.session_state["dd_sizing_committed"] = st.text_area(
            "Position sizing plan", value=st.session_state.get("dd_sizing_committed", ""),
            label_visibility="collapsed", key="dd_sizing", height=90,
        )

        # Afbeeldingen (charts/screenshots) kunnen pas geupload worden
        # NADAT deze deep-dive minstens 1x is opgeslagen -- een upload
        # is gekoppeld aan een version_id in de database, die nog niet
        # bestaat zolang je nog in dit 'nieuwe deep-dive'-formulier zit.
        # Sla eerst op (via Exit Matrix); daarna verschijnt de upload
        # hier vanzelf, zodra je deze ticker opnieuw opent.
        st.caption("Save this deep-dive first to unlock image uploads here.")

    elif _dd_tab == "EXIT MATRIX":
        # Conclusion is nu een NIET-aanpasbare, live berekende score --
        # het gemiddelde van de 5 andere schuifjes (Management/Risk/
        # Valuation/Catalysts/Technical). Alleen indirect te veranderen
        # door die andere schuifjes te verschuiven, niet rechtstreeks.
        # Gebruikt onder water nog steeds het bestaande 'thesis_score'-
        # veld (voor compatibiliteit met de conviction-tegels/tabellen
        # elders, die allemaal op de 6 bestaande score-velden rekenen).
        _conclusion_inputs = [
            st.session_state.get("dd_management_score_committed", 5.0),
            st.session_state.get("dd_bear_score_committed", 5.0),
            st.session_state.get("dd_valuation_score", 5.0),
            st.session_state.get("dd_catalysts_score_committed", 5.0),
            st.session_state.get("dd_technical_analysis_score_committed", 5.0),
        ]
        _conclusion_score = sum(_conclusion_inputs) / len(_conclusion_inputs)
        st.session_state["dd_thesis_score"] = _conclusion_score
        _dd_label("Conclusion (average of all scores)")
        st.markdown(
            f'<div style="text-align:center; margin-bottom:1rem;">'
            f'<span style="color:#34D399; font-weight:800; font-size:2.2rem;">'
            f'{_conclusion_score:.1f}</span>'
            f'<span style="color:#64748B; font-size:0.85rem;"> / 10</span></div>',
            unsafe_allow_html=True,
        )

        _dd_label("Valuation notes")
        st.text_area("Valuation notes", label_visibility="collapsed", key="dd_valuation", height=90)
        _dd_slider_value_html("dd_valuation_score")
        st.slider("Valuation score", 1.0, 10.0, 5.0, step=0.5, key="dd_valuation_score", label_visibility="collapsed")

        _dd_label(f"Interested from price ({dd_currency_symbol.strip()})")
        st.number_input(f"Interested from price", min_value=0.0, step=0.01, key="dd_interested_price", label_visibility="collapsed")

        _dd_label("Watch / Buy / Pass status")
        st.selectbox("Status", ["Watch", "Buy", "Pass"], key="dd_conclusion", label_visibility="collapsed")

        _dd_label("Sell criteria")
        st.text_area("Sell criteria", label_visibility="collapsed", key="dd_sell_criteria", height=90)

        _dd_label(f"Sell trigger price ({dd_currency_symbol.strip()})")
        st.number_input("Sell trigger price", min_value=0.0, step=0.01, key="dd_sell_trigger_price", label_visibility="collapsed")

        _dd_label("Sell by date")
        st.date_input("Sell by date", value=None, key="dd_sell_trigger_date", label_visibility="collapsed")

    # --- Save-knop uitsluitend op 'Exit Matrix' -- op de andere 2 tabs
    # staat in plaats daarvan een 'Next'-knop die naar de volgende stap
    # doorschakelt (1/3 -> 2/3 -> 3/3), zodat het een logische wizard-
    # flow wordt i.p.v. overal dezelfde save-actie te tonen.
    def _dd_goto_tab(tab_name: str) -> None:
        # Moet via on_click i.p.v. een gewone if-knop-klik: Streamlit
        # verbiedt het overschrijven van session_state[key] voor een
        # widget die in DEZELFDE run al getekend is (StreamlitWidget
        # AlreadyInstantiatedError) -- een on_click-callback draait
        # WEL veilig, want die wordt uitgevoerd voordat de widgets van
        # de volgende run worden opgebouwd.
        st.session_state["dd_active_subtab"] = tab_name

    _next_key = "dd_next_btn_wrap"
    st.markdown(
        f'<style>'
        f'.st-key-{_next_key} {{ margin-top:1.5rem !important; }} '
        f'.st-key-{_next_key} button {{ '
        f'width:100% !important; background:rgba(31,174,150,0.12) !important; color:#1FAE96 !important; '
        f'border:1px solid rgba(31,174,150,0.3) !important; font-weight:700 !important; font-size:0.85rem !important; '
        f'padding:0.7rem 0 !important; border-radius:12px !important; box-shadow:none !important; }} '
        f'.st-key-{_next_key} button:hover {{ background:rgba(31,174,150,0.2) !important; }} '
        f'</style>',
        unsafe_allow_html=True,
    )
    if _dd_tab == "1-CLICK BRIEFING":
        with st.container(key=_next_key):
            st.button(
                "Next: My Conviction (2/3) \u2192", key="dd_next_to_conviction", use_container_width=True,
                on_click=_dd_goto_tab, args=("MY CONVICTION",),
            )
        return

    if _dd_tab == "MY CONVICTION":
        with st.container(key=_next_key):
            st.button(
                "Next: Exit Matrix (3/3) \u2192", key="dd_next_to_exit", use_container_width=True,
                on_click=_dd_goto_tab, args=("EXIT MATRIX",),
            )
        return

    _save_key = "dd_save_btn_wrap"
    st.markdown(
        f'<style>'
        f'.st-key-{_save_key} {{ margin-top:1.5rem !important; }} '
        f'.st-key-{_save_key} button {{ '
        f'width:100% !important; background:#10B981 !important; color:#020617 !important; '
        f'font-weight:700 !important; font-size:0.9rem !important; padding:0.75rem 0 !important; '
        f'border-radius:12px !important; border:none !important; box-shadow:0 4px 12px rgba(16,185,129,0.25) !important; }} '
        f'.st-key-{_save_key} button:hover {{ background:#059669 !important; }} '
        f'</style>',
        unsafe_allow_html=True,
    )
    with st.container(key=_save_key):
        _save_clicked = st.button("Save Complete Deep-Dive \u2192", key="dd_save_btn", use_container_width=True)
    if _save_clicked:
        if not dd_ticker or not dd_naam:
            st.error("Please fill in at least a ticker and name.")
        else:
            with st.spinner("Fetching market data..."):
                market_snapshot = get_deep_dive_market_snapshot(dd_ticker)
            _ss = st.session_state
            database.add_deep_dive(
                user_email, dd_ticker, dd_naam,
                # '_committed' i.p.v. de rauwe widget-sleutel voor elk
                # tekstveld dat OOK op een andere tab dan Exit Matrix kan
                # staan -- zie de toelichting bij die velden hierboven.
                business_overview=_ss.get("dd_business_committed") or None,
                investment_thesis=_ss.get("dd_thesis_committed") or None,
                management_assessment=_ss.get("dd_management_committed") or None,
                bear_case=_ss.get("dd_bear_committed") or None,
                valuation_view=_ss.get("dd_valuation") or None,
                interested_price=_ss.get("dd_interested_price") or None,
                catalysts=_ss.get("dd_catalysts_committed") or None,
                position_sizing_plan=_ss.get("dd_sizing_committed") or None,
                sell_criteria=_ss.get("dd_sell_criteria") or None,
                conclusion=_ss.get("dd_conclusion", "Watch"),
                market_snapshot=market_snapshot,
                sell_trigger_price=_ss.get("dd_sell_trigger_price") or None,
                sell_trigger_date=_ss["dd_sell_trigger_date"].isoformat() if _ss.get("dd_sell_trigger_date") else None,
                thesis_score=_ss.get("dd_thesis_score", 5.0),
                management_score=_ss.get("dd_management_score_committed", 5.0),
                bear_case_score=_ss.get("dd_bear_score_committed", 5.0),
                valuation_score=_ss.get("dd_valuation_score", 5.0),
                catalysts_score=_ss.get("dd_catalysts_score_committed", 5.0),
                technical_analysis=_ss.get("dd_technical_analysis_committed") or None,
                technical_analysis_score=_ss.get("dd_technical_analysis_score_committed", 5.0),
            )
            st.success(f"New version for {dd_ticker} saved!")
            st.session_state["selected_research"] = None
            st.rerun()


def _render_analyze_drawer(user_email: str) -> None:
    """
    De rechter drawer-kolom -- toont ofwel het 'nieuwe deep-dive'-
    formulier (selected_research == '__NEW__'), ofwel de volledige,
    rijke details + versiegeschiedenis van 1 geselecteerde ticker.
    """
    import database

    _drawer_key = "analyze_drawer"
    st.markdown(
        f'<style>.st-key-{_drawer_key} {{ '
        f'background:rgba(15,23,42,0.2) !important; border-left:1px solid rgba(30,41,59,0.6) !important; '
        f'padding:1.25rem !important; border-radius:0 14px 14px 0 !important; box-sizing:border-box !important; '
        f'position:relative !important; }} '
        # Definitieve fix: ABSOLUTE positionering t.o.v. de drawer zelf
        # i.p.v. flex/negatieve-marge-gefriemel -- dat bleef ondanks 2
        # pogingen ergens links vastlopen. Dit pint de knop letterlijk
        # vast aan de rechterbovenhoek van de drawer-box, los van
        # waar de kop-tekst zelf staat of hoe die precies stroomt.
        f'.st-key-analyze_drawer_close {{ position:absolute !important; top:1.25rem !important; '
        f'right:1.25rem !important; z-index:10 !important; width:auto !important; }} '
        f'.st-key-analyze_drawer_close button {{ '
        f'background:rgba(148,163,184,0.08) !important; border:1px solid rgba(148,163,184,0.15) !important; '
        f'box-shadow:none !important; color:#94A3B8 !important; font-size:0.95rem !important; '
        f'font-weight:400 !important; width:28px !important; height:28px !important; min-height:unset !important; '
        f'padding:0 !important; border-radius:50% !important; transition:all 0.2s ease !important; }} '
        f'.st-key-analyze_drawer_close button:hover {{ color:#F1F5F9 !important; '
        f'background:rgba(148,163,184,0.16) !important; border-color:rgba(148,163,184,0.3) !important; }} '
        # 'Back to research overview' -- uitsluitend op mobiel zichtbaar
        # (op desktop doet de bestaande '\u00d7' precies hetzelfde, geen
        # dubbele knop nodig daar). Op mobiel juist een grote,
        # opvallende, volle-breedte knop bovenaan -- dat is de enige weg
        # terug nu de linkerkolom daar volledig verborgen is.
        f'.st-key-analyze_drawer_back_mobile {{ display:none; }} '
        f'@media (max-width:768px) {{ '
        f'.st-key-{_drawer_key} {{ border-left:none !important; border-radius:14px !important; }} '
        f'.st-key-analyze_drawer_close {{ display:none !important; }} '
        f'.st-key-analyze_drawer_back_mobile {{ display:block !important; margin-bottom:1rem !important; }} '
        f'.st-key-analyze_drawer_back_mobile button {{ '
        f'width:100% !important; background:rgba(31,174,150,0.1) !important; '
        f'border:1px solid rgba(31,174,150,0.3) !important; color:#1FAE96 !important; '
        f'font-weight:700 !important; font-size:0.78rem !important; letter-spacing:0.04em !important; '
        f'text-transform:uppercase !important; padding:0.6rem 0 !important; border-radius:10px !important; '
        f'box-shadow:none !important; }} '
        f'}} '
        f'</style>',
        unsafe_allow_html=True,
    )

    def _render_drawer_close_button() -> None:
        with st.container(key="analyze_drawer_close"):
            if st.button("\u00d7", key="analyze_drawer_close_btn", help="Close"):
                st.session_state["selected_research"] = None
                st.rerun()

    with st.container(key=_drawer_key):
        with st.container(key="analyze_drawer_back_mobile"):
            if st.button("\u2190 Back to Research Overview", key="analyze_drawer_back_mobile_btn"):
                st.session_state["selected_research"] = None
                st.rerun()

        selected = st.session_state.get("selected_research")
        if selected == "__NEW__":
            st.markdown(
                '<div style="color:#1FAE96; font-weight:700; font-size:0.85rem; text-transform:uppercase; '
                'letter-spacing:0.03em; margin-bottom:1rem; display:flex; align-items:center; gap:0.4rem;">'
                '<span style="color:#34D399;">&#10022;</span> Add a new deep-dive</div>',
                unsafe_allow_html=True,
            )
            _render_drawer_close_button()
            _render_deep_dive_add_form(user_email)
        else:
            history = database.get_deep_dives_for_ticker(user_email, selected)
            if not history:
                _render_drawer_close_button()
                st.caption("No research found for this ticker.")
                return
            latest = history[0]
            st.markdown(
                f'<div style="color:#1FAE96; font-weight:700; font-size:0.85rem; text-transform:uppercase; '
                f'letter-spacing:0.03em; margin-bottom:0.35rem;">{selected} &middot; {latest.get("naam", selected)}</div>',
                unsafe_allow_html=True,
            )
            _render_drawer_close_button()
            # Investment thesis nu direct bovenin de drawer i.p.v. in de
            # tabel (waar 'ie was afgekapt op 60 tekens) -- de Core
            # Thesis-kolom bestaat niet meer in de tabel zelf.
            if latest.get("investment_thesis"):
                st.markdown(
                    f'<div style="color:#F1F5F9; font-weight:700; font-size:0.78rem; text-transform:uppercase; '
                    f'letter-spacing:0.02em; line-height:1.5; margin-bottom:1rem;">{latest["investment_thesis"]}</div>',
                    unsafe_allow_html=True,
                )
            st.caption(f"{len(history)} version(s) logged, most recent first.")
            for version in history:
                _render_deep_dive_version(version, user_email)


_STRESS_TEST_KNOWN_BETAS = {
    "TSLA": 2.3,
    "NVDA": 1.4,
    "SMH.L": 1.4,
}
_STRESS_TEST_SEMI_TECH_TICKERS = {"TSLA", "NVDA", "SMH.L"}


def _stress_test_beta_for_holding(h: dict) -> float:
    """
    Geeft de bèta (gevoeligheid t.o.v. een algemene marktbeweging) voor 1
    positie terug -- gecureerde tabel, want Yahoo Finance's eigen 'beta'-
    veld is onbetrouwbaar/vaak leeg voor kleinere of niet-Amerikaanse
    tickers. Vaste, met de hand gekozen waarden: TSLA=2.3 (notoir volatiel
    t.o.v. de brede markt), NVDA/SMH.L=1.4 (semiconductor-cluster, hoger
    dan gemiddeld maar minder extreem dan TSLA), Overig=1.1 (licht boven
    marktgemiddelde, een redelijke default voor een individueel aandeel).
    Crypto (ticker met een '-', zoals BTC-USD/SOL-USD) krijgt 1.8 -- hoog-
    volatiel, beweegt doorgaans harder dan aandelen bij eenzelfde macro-
    schok. Een Custom Yield Asset (fractioneel vastgoed e.d., geen echte
    beursnotering) krijgt 0.0 -- ontkoppeld van beurskoersen per definitie.
    """
    if h.get("custom_annual_cashflow") is not None:
        return 0.0
    ticker_upper = (h.get("ticker") or "").upper()
    if "-" in ticker_upper:
        return 1.8
    return _STRESS_TEST_KNOWN_BETAS.get(ticker_upper, 1.1)


def _stress_tile_style(impact_eur: float, base_eur: float) -> str:
    """
    Geeft een CSS-stijl-string terug voor 1 van de 3 Systemic Risk Tiles.
    De kleur van de rand/gloed volgt ALTIJD eerst het TEKEN van de live
    impact (winst = groen, verlies = rood/amber) en pas daarna de
    INTENSITEIT via hetzelfde 3-traps-systeem (rustig gedempt grijs bij
    weinig stress, sterker gekleurd bij meer). Relevant vooral voor de
    Currency Risk-tegel: die kan door de FX-slider (-20% tot +20%) zowel
    een positieve als negatieve live impact hebben, dus de tegel moet
    vloeiend van rood naar groen (en terug) kunnen omslaan i.p.v. altijd
    hardcoded rood te blijven zoals de andere 2 (altijd-negatieve) tegels.
    3 vaste drempels i.p.v. een continue CSS-gradient (niet zuiver
    berekenbaar in platte inline-CSS), consistent met hoe de rest van
    Hestys kleur-drempels al toepast (zie _deep_dive_score_color).
    """
    impact_pct = abs(impact_eur) / base_eur if base_eur else 0.0
    if impact_eur >= 0:
        if impact_pct >= 0.08:
            return (
                "background:rgba(16,185,129,0.10); border:1px solid rgba(16,185,129,0.45); "
                "border-radius:12px; padding:1rem; text-align:left; transition:all 0.3s ease;"
            )
        elif impact_pct >= 0.02:
            return (
                "background:rgba(16,185,129,0.06); border:1px solid rgba(16,185,129,0.3); "
                "border-radius:12px; padding:1rem; text-align:left; transition:all 0.3s ease;"
            )
        else:
            return (
                "background:rgba(15,23,42,0.3); border:1px solid rgba(30,41,59,0.4); "
                "border-radius:12px; padding:1rem; text-align:left; transition:all 0.3s ease;"
            )
    else:
        if impact_pct >= 0.08:
            return (
                "background:rgba(244,63,94,0.08); border:1px solid rgba(244,63,94,0.4); "
                "border-radius:12px; padding:1rem; text-align:left; transition:all 0.3s ease;"
            )
        elif impact_pct >= 0.02:
            return (
                "background:rgba(232,169,60,0.07); border:1px solid rgba(232,169,60,0.35); "
                "border-radius:12px; padding:1rem; text-align:left; transition:all 0.3s ease;"
            )
        else:
            return (
                "background:rgba(15,23,42,0.3); border:1px solid rgba(30,41,59,0.4); "
                "border-radius:12px; padding:1rem; text-align:left; transition:all 0.3s ease;"
            )


def _fmt_eur_signed(value: float) -> str:
    """Formatteert een euro-impact met expliciet teken en kleur (rood bij verlies, groen bij winst)."""
    color = "#FB7185" if value < 0 else "#34D399"
    sign = "-" if value < 0 else "+"
    return f'<span style="color:{color}; font-weight:800;">{sign}&euro;{abs(value):,.0f}</span>'


def _render_stress_test(user_email: str) -> None:
    """
    'Stress-Test' -- interactieve What-If Crisis Simulator. Volledig
    LOSSTAAND van Conviction Tracker/Wealth Engine: eigen, verse database-
    aanroepen, geen gedeelde state. Gebruikt UITSLUITEND de actieve,
    huidige posities (filter_active_holdings()) -- geen historische/
    gesloten posities die er ooit in hebben gezeten maar nu niet meer
    meetellen.

    3 lagen, ELK MET EEN EIGEN, BEWUST GESCHEIDEN ROL (geen dubbele
    weging van dezelfde schok over 2 secties heen):
    1. Macro Control Panel -- 3 sliders (equity crash / FX-schok / supply
       chain-schok) die een LIVE, zelf te bepalen 'wat als'-scenario sturen.
       Voeden UITSLUITEND de 3 tegels in laag 3, niet de historische tabel.
    2. Beta-Weighted Black Swan Timeline -- de 3 vaste, historische crashes
       (Dot-Com/2008/Covid) herrekend PER POSITIE met een eigen bèta i.p.v.
       1 vlak percentage over de hele portfolio. Volledig LOSGEKOPPELD van
       de 3 sliders (puur historisch percentage x bèta) en met een harde
       floor per positie (nooit meer dan -100% van die ene positie), zodat
       het totaal ook nooit groter kan zijn dan de totale portfoliowaarde.
    3. Systemic Risk Correlation Matrix -- 3 tegels die uitsluitend de
       LIVE slider-impact tonen voor de 3 concrete clusters in je eigen
       portfolio (tech/semiconductor, USD-blootstelling, crypto).
    """
    holdings = filter_active_holdings(database.get_user_holdings(user_email))

    _rows = []
    for h in holdings:
        ticker = h.get("ticker")
        eur_value = _eur_position_value(h)
        if not ticker or eur_value <= 0:
            continue
        ticker_upper = ticker.upper()
        _rows.append({
            "ticker": ticker_upper,
            "naam": h.get("naam", ticker),
            "eur_value": eur_value,
            "beta": _stress_test_beta_for_holding(h),
            "currency": _native_currency_for_holding(h),
            "is_crypto": "-" in ticker_upper,
            "is_semi_tech": ticker_upper in _STRESS_TEST_SEMI_TECH_TICKERS,
        })

    total_value = sum(r["eur_value"] for r in _rows)

    if total_value <= 0 or not _rows:
        st.markdown(
            '<div style="background:rgba(15,23,42,0.3); border:1px solid rgba(30,41,59,0.4); '
            'border-radius:14px; padding:2rem; text-align:center; color:#64748B; font-size:0.85rem;">'
            'Add some positions first (see Conviction Tracker) to run a stress-test.</div>',
            unsafe_allow_html=True,
        )
        return

    # ================================================================
    # 1. MACRO CONTROL PANEL -- 3 sliders die een LIVE 'wat-als'-scenario
    # sturen. Rechtstreeks de teruggegeven waarde van elke slider gebruikt
    # in de rest van deze functie (geen omweg via session_state) -- zelfde,
    # al-bewezen patroon als de Wealth Engine's Simulation Control Panel:
    # gegarandeerd synchroon bij elke rerun, geen extra plumbing nodig.
    # ================================================================
    st.markdown(
        _uniform_section_header_html("Macro Control Panel", "tune", is_first=True),
        unsafe_allow_html=True,
    )
    _sim_key = "stress_test_sim_panel"
    st.markdown(
        f'<style>'
        f'.st-key-{_sim_key} label p {{ '
        f'font-size:10px !important; font-weight:700 !important; letter-spacing:0.06em !important; '
        f'text-transform:uppercase !important; color:#64748B !important; }} '
        f'</style>',
        unsafe_allow_html=True,
    )
    with st.container(key=_sim_key):
        macro_col1, macro_col2, macro_col3 = st.columns(3, gap="medium")
        with macro_col1:
            equity_crash_pct = st.slider(
                "Global equity market crash (beta shock)", min_value=-50.0, max_value=0.0,
                value=0.0, step=1.0, key="stress_equity_crash_slider", format="%.0f%%",
            )
        with macro_col2:
            fx_shock_pct = st.slider(
                "USD / EUR exchange rate shock", min_value=-20.0, max_value=20.0,
                value=0.0, step=0.5, key="stress_fx_shock_slider", format="%.1f%%",
                help="Affects only your USD-denominated positions.",
            )
        with macro_col3:
            supply_chain_pct = st.slider(
                "Geopolitical supply chain shock", min_value=-50.0, max_value=0.0,
                value=0.0, step=1.0, key="stress_supply_chain_slider", format="%.0f%%",
                help="Affects only your semiconductor/tech cluster (TSLA, NVDA, SMH.L).",
            )
    _equity_shock_frac = equity_crash_pct / 100
    _fx_shock_frac = fx_shock_pct / 100
    _supply_chain_frac = supply_chain_pct / 100

    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

    # --- Risk metrics -- gewogen (naar positiegrootte) op basis van LIVE
    # Yahoo Finance-data (country/sector) + de al-bekende valuta per
    # positie. Geen vaste voorbeeldwaarden -- puur berekend uit jouw
    # daadwerkelijke, actieve portfolio.
    _country_weight: dict = {}
    _sector_weight: dict = {}
    _currency_weight: dict = {}
    for h in holdings:
        ticker = h.get("ticker")
        value = _eur_position_value(h)
        if not ticker or value <= 0:
            continue
        try:
            info = get_cached_ticker_info(ticker)
        except Exception:
            info = {}
        country = info.get("country")
        if country:
            _country_weight[country] = _country_weight.get(country, 0) + value
        sector = info.get("sector")
        if sector:
            _sector_weight[sector] = _sector_weight.get(sector, 0) + value
        currency = _native_currency_for_holding(h)
        if currency:
            _currency_weight[currency] = _currency_weight.get(currency, 0) + value

    def _dominant(weight_dict: dict):
        if not weight_dict:
            return None, 0.0
        top_key = max(weight_dict, key=weight_dict.get)
        top_pct = (weight_dict[top_key] / total_value) * 100
        return top_key, top_pct

    _top_country, _top_country_pct = _dominant(_country_weight)
    _top_sector, _top_sector_pct = _dominant(_sector_weight)
    _top_currency, _top_currency_pct = _dominant(_currency_weight)

    risk_col1, risk_col2, risk_col3 = st.columns(3, gap="medium")
    _risk_tile_style = (
        'background:rgba(15,23,42,0.3); border:1px solid rgba(30,41,59,0.4); '
        'border-radius:12px; padding:1rem; text-align:left;'
    )
    with risk_col1:
        _country_label = f"{_top_country_pct:.0f}% {_top_country.upper()}-EXPOSED" if _top_country else "UNKNOWN"
        st.markdown(
            f'<div style="{_risk_tile_style}">'
            f'<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; '
            f'color:#8992A3; margin-bottom:0.4rem;">&#127760; Geopolitical exposure</div>'
            f'<div style="font-size:1.15rem; font-weight:800; color:#F1F5F9;">{_country_label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with risk_col2:
        _sector_label = f"{_top_sector_pct:.0f}% {_top_sector.upper()} SECTOR" if _top_sector else "UNKNOWN"
        st.markdown(
            f'<div style="{_risk_tile_style}">'
            f'<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; '
            f'color:#8992A3; margin-bottom:0.4rem;">&#128268; Systemic dependency</div>'
            f'<div style="font-size:1.15rem; font-weight:800; color:#F1F5F9;">{_sector_label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with risk_col3:
        _currency_label = f"{_top_currency_pct:.0f}% {_top_currency}-DENOMINATED" if _top_currency else "UNKNOWN"
        st.markdown(
            f'<div style="{_risk_tile_style}">'
            f'<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; '
            f'color:#8992A3; margin-bottom:0.4rem;">&#128184; Currency overlap</div>'
            f'<div style="font-size:1.15rem; font-weight:800; color:#F1F5F9;">{_currency_label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

    # ================================================================
    # 2. BETA-WEIGHTED BLACK SWAN TIMELINE -- de 3 vaste, historische
    # marktdalingen (Dot-Com/2008/Covid) niet langer als 1 vlak percentage
    # over de hele portfoliowaarde, maar PER POSITIE herrekend met zijn
    # eigen b\u00e8ta (_stress_test_beta_for_holding).
    #
    # GEVONDEN, EERDERE FOUT: de 3 macro-sliders werden BOVENOP de
    # historische daling opgeteld, wat 2 wiskundig kapotte dingen gaf:
    # (1) een dubbele weging -- de sliders horen puur bij de LIVE 'wat-
    # als'-tegels onderin, niet ALSNOG een keer door de historische
    # tabel heen; (2) geen enkele ondergrens -- bij extreme sliderstanden
    # kon het berekende verlies makkelijk GROTER worden dan de totale
    # portfoliowaarde zelf (bv. -84k verlies op een 64k-portfolio), wat
    # onmogelijk is: je kunt nooit meer dan 100% van je inleg verliezen.
    # Nu volledig losgekoppeld van de sliders (puur historisch percentage
    # x b\u00e8ta) EN met een harde floor PER POSITIE: het verlies op 1 asset
    # kan nooit groter zijn dan de waarde van die ene positie, waardoor
    # het totaal ook nooit groter kan zijn dan de totale portfoliowaarde.
    # ================================================================
    # LET OP: hier staan bewust ECHTE PERCENTAGES (-54.0, 228.0, ...), geen
    # vooraf gedeelde fracties -- dat voorkomt elke twijfel over schaal en
    # matcht 1-op-1 de expliciete formule hieronder (.../100).
    _crash_scenarios = [
        ("Dot-Com Bubble Burst", -54.0, "beta-weighted"),
        ("2008 Great Financial Crisis", -38.0, "beta-weighted"),
        ("2020 Covid-19 Panic", -22.0, "beta-weighted"),
    ]

    # GOLDEN ERAS (UPSIDE) -- zelfde bèta-wiskunde als de crashes, maar dan
    # met een positief marktrendement. De "cluster-explosie" (tech/chips bij
    # Dot-Com, crypto bij Post-Covid) ontstaat vanzelf uit de bestaande
    # per-asset bèta's (TSLA/NVDA/SMH.L=1.4-2.3, crypto=1.8 t.o.v. default
    # 1.1) -- geen aparte extra vermenigvuldiging per cluster nodig.
    _golden_era_scenarios = [
        ("1982 Reaganomics Rally", 228.0, "beta-weighted"),
        ("1995 Dot-Com Exuberance Boom", 400.0, "tech-leveraged"),
        ("2020 Post-Covid Liquidity Injection", 70.0, "hyper-volatility"),
    ]

    def _scenario_pnl_eur(market_upside_percentage: float) -> float:
        """
        Loopt PER INDIVIDUELE ACTIEVE POSITIE (nooit een vooraf uitgemiddeld
        portefeuille-cijfer) en telt de resultaten daarna pas bij elkaar op,
        exact volgens:
            asset_gain = current_position_value * (market_upside_percentage / 100) * asset_beta
        Bèta's komen 1-op-1 uit _stress_test_beta_for_holding: TSLA=2.3,
        crypto (BTC/SOL, ticker met '-')=1.8, NVDA/SMH.L=1.4, Custom Yield
        Assets ("Prop.com"-achtige posities)=0.0, overig=1.1. Een cluster
        met een hoge bèta (tech/chips bij de Dot-Com Exuberance Boom,
        crypto bij de Post-Covid scenario) versterkt zichzelf hierdoor
        automatisch t.o.v. de rest van de portfolio -- geen platte 1-op-1
        vermenigvuldiging en geen aparte cluster-multiplier nodig.
        """
        _total_pnl = 0.0
        for r in _rows:
            current_position_value = r["eur_value"]
            asset_beta = r["beta"]
            asset_gain = current_position_value * (market_upside_percentage / 100.0) * asset_beta
            if market_upside_percentage < 0:
                # Alleen bij een verlies-scenario: harde floor per positie --
                # het verlies op DEZE ene positie kan nooit groter zijn dan
                # -100% van zijn eigen waarde. Bij een winst (Golden Eras) is
                # er bewust GEEN plafond: een bèta-versterkte winst van meer
                # dan 100% op 1 positie is wiskundig normaal en mag niet
                # worden afgekapt.
                asset_gain = max(-current_position_value, asset_gain)
            _total_pnl += asset_gain
        return _total_pnl

    _crash_header_style = (
        "text-transform:uppercase; font-size:10px; font-weight:700; color:#475569; "
        "letter-spacing:0.06em; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.1) !important; "
        "border-top:none !important; border-left:none !important; border-right:none !important;"
    )
    _crash_cell_base = (
        "border-bottom:1px solid rgba(255,255,255,0.05) !important; border-top:none !important; "
        "border-left:none !important; border-right:none !important; vertical-align:middle; padding:12px 0;"
    )

    # HESTYS SCENARIO-SCHAKELAAR -- wisselt de tabel eronder flitsloos/
    # synchroon tussen historische Black Swans (crashes) en Golden Eras
    # (bull-runs), puur via session_state, geen rerun-vertraging.
    _scenario_toggle_key = "stress_test_scenario_toggle"
    st.markdown(
        f'<style>.st-key-{_scenario_toggle_key} {{ margin-bottom: 0.6rem; }}</style>',
        unsafe_allow_html=True,
    )
    with st.container(key=_scenario_toggle_key):
        st.pills(
            "Scenario mode",
            options=["BLACK SWANS (CRASH)", "GOLDEN ERAS (UPSIDE)"],
            default=st.session_state.get("active_scenario_mode", "BLACK SWANS (CRASH)"),
            key="active_scenario_mode",
            label_visibility="collapsed",
        )
    _is_golden_era = st.session_state.get("active_scenario_mode") == "GOLDEN ERAS (UPSIDE)"

    _scenario_list = _golden_era_scenarios if _is_golden_era else _crash_scenarios
    _impact_header_label = "Projected gain (EUR)" if _is_golden_era else "Projected impact (EUR)"

    _crash_rows_html = ""
    for _label, _impact, _suffix in _scenario_list:
        _pnl_eur = _scenario_pnl_eur(_impact)
        if _is_golden_era:
            _value_style = "color:#34d399; font-weight:700;"
            _sign = "+"
        else:
            _value_style = "color:rgba(244,63,94,0.7); font-weight:700;"
            _sign = "-"
        _crash_rows_html += (
            f'<tr>'
            f'<td style="{_crash_cell_base} color:#8992A3; font-size:0.82rem;">{_label} ({_impact:+.0f}%, {_suffix})</td>'
            f'<td style="{_crash_cell_base} text-align:right; {_value_style} '
            f'font-size:0.85rem;">{_sign}&euro;{abs(_pnl_eur):,.0f}</td>'
            f'</tr>'
        )
    # Zelfde patroon als Snowball Milestones (Wealth Engine): raw <table>
    # binnen een EIGEN st.container(key=...) + expliciete CSS die de
    # standaard-tabelranden hard onderdrukt. Zonder die CSS-override
    # (die hier eerder ontbrak) tekent de browser/Streamlit's eigen
    # basis-stylesheet alsnog lelijke verticale kolomlijnen, ongeacht de
    # inline styles op de cellen zelf.
    _crash_table_key = "stress_test_crash_table"
    st.markdown(
        f'<style>.st-key-{_crash_table_key} table {{ width:100%; border-collapse:collapse; }} '
        f'.st-key-{_crash_table_key} td, .st-key-{_crash_table_key} th {{ border:none; }}</style>',
        unsafe_allow_html=True,
    )
    with st.container(key=_crash_table_key):
        st.markdown(
            f'<div style="max-width:640px;">'
            f'<table style="width:100%; border-collapse:collapse;">'
            f'<thead><tr>'
            f'<th style="{_crash_header_style} text-align:left;">Historical scenario</th>'
            f'<th style="{_crash_header_style} text-align:right;">{_impact_header_label}</th>'
            f'</tr></thead>'
            f'<tbody>{_crash_rows_html}</tbody>'
            f'</table>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)

    # ================================================================
    # 3. SYSTEMIC RISK CORRELATION MATRIX -- 3 grafische tegels i.p.v. de
    # eerdere pratende AI-bulletpoints. Elke tegel is 100% deterministisch
    # herberekend uit je eigen holdings + de 3 macro-sliders hierboven --
    # geen API-aanroep, dus flitsloos/synchroon bij elke slider-beweging.
    # ================================================================
    st.markdown(
        _uniform_section_header_html("Systemic Risk Correlation Matrix", "bar_chart", is_first=False),
        unsafe_allow_html=True,
    )

    # Zelfde harde floor per positie als bij de historische tabel: bij een
    # hoge bèta (TSLA=2.3) plus de equity- EN supply chain-slider allebei
    # op hun extreme stand samen, zou de ongefloorde som anders ook hier
    # over de -100% van die ene positie heen kunnen schieten.
    _semi_tech_rows = [r for r in _rows if r["is_semi_tech"]]
    _semi_tech_value = sum(r["eur_value"] for r in _semi_tech_rows)
    _semi_tech_impact = sum(
        max(-r["eur_value"], r["eur_value"] * r["beta"] * _equity_shock_frac + r["eur_value"] * _supply_chain_frac)
        for r in _semi_tech_rows
    )

    _usd_rows = [r for r in _rows if r["currency"] == "USD"]
    _usd_value = sum(r["eur_value"] for r in _usd_rows)
    _usd_pct_of_total = (_usd_value / total_value * 100) if total_value else 0.0
    _fx_impact = sum(r["eur_value"] * _fx_shock_frac for r in _usd_rows)

    _crypto_rows = [r for r in _rows if r["is_crypto"]]
    _crypto_value = sum(r["eur_value"] for r in _crypto_rows)
    _crypto_impact = sum(
        max(-r["eur_value"], r["eur_value"] * r["beta"] * _equity_shock_frac) for r in _crypto_rows
    )

    def _cluster_live_impact(rows: list) -> float:
        """
        Herbruikbare live-impact-berekening voor een willekeurige subset van
        _rows -- exact hetzelfde patroon als de 3 tegels hierboven: bèta-
        gewogen equity-shock (plus de supply chain-schok voor semi/tech-
        posities), met dezelfde harde floor per positie (nooit meer dan
        -100% van die ene positie). Gebruikt door tegel 4/5/6 zodat alle 6
        tegels identiek, flitsloos meebewegen met de sliders hierboven.
        """
        _total = 0.0
        for r in rows:
            _calc = r["eur_value"] * r["beta"] * _equity_shock_frac
            if r["is_semi_tech"]:
                _calc += r["eur_value"] * _supply_chain_frac
            _calc = max(-r["eur_value"], _calc)
            _total += _calc
        return _total

    # TILE 4 -- Alternative Asset Anchor: Prop.com (fractioneel vastgoed)
    # heeft per definitie bèta 0.0 (_stress_test_beta_for_holding), dus
    # volledig ontkoppeld van elke slider -- functioneert als liquiditeits-
    # anker tijdens equity-crashes.
    _prop_rows = [r for r in _rows if r["ticker"] == "PROP.COM"]
    _prop_value = sum(r["eur_value"] for r in _prop_rows)
    _prop_impact = _cluster_live_impact(_prop_rows)

    # TILE 5 -- Single-Asset Dominance: de grootste individuele positie in
    # de hele portfolio (dynamisch bepaald, niet hardcoded op "TSLA"), met
    # zijn concentratierisico (% van totaal) en zijn eigen live slider-
    # impact.
    _dominant_row = max(_rows, key=lambda r: r["eur_value"]) if _rows else None
    _dominant_pct = (_dominant_row["eur_value"] / total_value * 100) if (_dominant_row and total_value) else 0.0
    _dominant_impact = _cluster_live_impact([_dominant_row]) if _dominant_row else 0.0
    _dominant_status_color = "#FB7185" if _dominant_pct > 30 else "#94A3B8"

    # TILE 6 -- Asset Velocity Divergence: stabiele cashflow-ankers (dividend-
    # ETF, defensief consumentenaandeel, fractioneel vastgoed) t.o.v. pure
    # groei-/crypto-posities, allebei uitgedrukt als % van de totale
    # portfolio. De live-impact van de tegel volgt de groei-cluster, want
    # dat is het bèta-gevoelige deel van deze tegenstelling.
    _yield_tickers = {"TDIV.AS", "KHC", "PROP.COM"}
    _growth_tickers = {"TSLA", "ASTS", "HIMS", "BTC-USD", "SOL-USD"}
    _yield_rows = [r for r in _rows if r["ticker"] in _yield_tickers]
    _growth_rows = [r for r in _rows if r["ticker"] in _growth_tickers]
    _yield_value = sum(r["eur_value"] for r in _yield_rows)
    _growth_value = sum(r["eur_value"] for r in _growth_rows)
    _yield_pct = (_yield_value / total_value * 100) if total_value else 0.0
    _growth_pct = (_growth_value / total_value * 100) if total_value else 0.0
    _velocity_impact = _cluster_live_impact(_growth_rows)

    heat_col1, heat_col2, heat_col3 = st.columns(3, gap="medium")
    with heat_col1:
        st.markdown(
            f'<div style="{_stress_tile_style(_semi_tech_impact, total_value)}">'
            f'<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; '
            f'color:#8992A3; margin-bottom:0.4rem;">&#128680; Tech &amp; hardware overlap</div>'
            f'<div style="font-size:1.1rem; font-weight:800; color:#F1F5F9;">&euro;{_semi_tech_value:,.0f} '
            f'<span style="font-size:0.7rem; font-weight:600; color:#64748B;">exposed</span></div>'
            f'<div style="font-size:0.9rem; margin-top:0.3rem;">{_fmt_eur_signed(_semi_tech_impact)} '
            f'<span style="font-size:0.68rem; font-weight:600; color:#64748B;">live impact</span></div>'
            f'<div style="font-size:10px; color:#64748B; font-weight:700; letter-spacing:0.05em; '
            f'text-transform:uppercase; margin-top:0.5rem;">'
            f'AFFECTED CLUSTER TICKERS: {", ".join(r["ticker"] for r in _semi_tech_rows) if _semi_tech_rows else "NO EXPOSURE IN THIS CLUSTER"}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with heat_col2:
        st.markdown(
            f'<div style="{_stress_tile_style(_fx_impact, total_value)}">'
            f'<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; '
            f'color:#8992A3; margin-bottom:0.4rem;">&#128184; Currency risk exposure</div>'
            f'<div style="font-size:1.1rem; font-weight:800; color:#F1F5F9;">{_usd_pct_of_total:.0f}% '
            f'<span style="font-size:0.7rem; font-weight:600; color:#64748B;">USD-denominated</span></div>'
            f'<div style="font-size:0.9rem; margin-top:0.3rem;">{_fmt_eur_signed(_fx_impact)} '
            f'<span style="font-size:0.68rem; font-weight:600; color:#64748B;">live impact</span></div>'
            f'<div style="font-size:10px; color:#64748B; font-weight:700; letter-spacing:0.05em; '
            f'text-transform:uppercase; margin-top:0.5rem;">'
            f'TOTAL EXPOSED CAPITAL: &euro;{_usd_value:,.0f} | SENSITIVITY: DIRECT FX COUPLING</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with heat_col3:
        st.markdown(
            f'<div style="{_stress_tile_style(_crypto_impact, total_value)}">'
            f'<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; '
            f'color:#8992A3; margin-bottom:0.4rem;">&#9889; High-volatility cluster</div>'
            f'<div style="font-size:1.1rem; font-weight:800; color:#F1F5F9;">&euro;{_crypto_value:,.0f} '
            f'<span style="font-size:0.7rem; font-weight:600; color:#64748B;">crypto exposure</span></div>'
            f'<div style="font-size:0.9rem; margin-top:0.3rem;">{_fmt_eur_signed(_crypto_impact)} '
            f'<span style="font-size:0.68rem; font-weight:600; color:#64748B;">live impact</span></div>'
            f'<div style="font-size:10px; color:#64748B; font-weight:700; letter-spacing:0.05em; '
            f'text-transform:uppercase; margin-top:0.5rem;">'
            f'TICKERS: {", ".join(r["ticker"] for r in _crypto_rows) if _crypto_rows else "NONE"} '
            f'| COMPONENT CORE CORRELATION: HISTORICALLY MOVE SYNCHRONOUS DURING MAXIMUM DRAWDOWN EVENTS.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    heat_col4, heat_col5, heat_col6 = st.columns(3, gap="medium")
    with heat_col4:
        st.markdown(
            f'<div style="{_stress_tile_style(_prop_impact, total_value)}">'
            f'<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; '
            f'color:#8992A3; margin-bottom:0.4rem;">&#127970; Alternative asset anchor</div>'
            f'<div style="font-size:1.1rem; font-weight:800; color:#F1F5F9;">&euro;{_prop_value:,.0f} '
            f'<span style="font-size:0.7rem; font-weight:600; color:#64748B;">locked</span></div>'
            f'<div style="font-size:0.9rem; margin-top:0.3rem; color:#64748B; font-weight:700;">'
            f'0% LIQUIDITY CORRELATION</div>'
            f'<div style="font-size:10px; color:#64748B; font-weight:700; letter-spacing:0.05em; '
            f'text-transform:uppercase; margin-top:0.5rem;">'
            f'ASSET CLUSTER: REAL ESTATE | PROPERTY YIELD ACTING AS LIQUIDITY ANCHOR DURING EQUITY CRASHES.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with heat_col5:
        _dominant_ticker = _dominant_row["ticker"] if _dominant_row else "N/A"
        st.markdown(
            f'<div style="{_stress_tile_style(_dominant_impact, total_value)}">'
            f'<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; '
            f'color:#8992A3; margin-bottom:0.4rem;">&#128081; Single-asset dominance</div>'
            f'<div style="font-size:1.1rem; font-weight:800; color:#F1F5F9;">{_dominant_pct:.1f}% '
            f'<span style="font-size:0.7rem; font-weight:600; color:#64748B;">portfolio weight</span></div>'
            f'<div style="font-size:0.9rem; margin-top:0.3rem; color:{_dominant_status_color}; font-weight:700;">'
            f'CRITICAL CONCENTRATION</div>'
            f'<div style="font-size:10px; color:#64748B; font-weight:700; letter-spacing:0.05em; '
            f'text-transform:uppercase; margin-top:0.5rem;">'
            f'TICKER: {_dominant_ticker} | MAXIMUM DRAWDOWN EXPOSURE RISK IS HEAVILY LEVERAGED TO A SINGLE EQUITY FACTOR.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with heat_col6:
        st.markdown(
            f'<div style="{_stress_tile_style(_velocity_impact, total_value)}">'
            f'<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; '
            f'color:#8992A3; margin-bottom:0.4rem;">&#8987; Asset velocity divergence</div>'
            f'<div style="font-size:1.1rem; font-weight:800; color:#F1F5F9;">{_yield_pct:.0f}% '
            f'<span style="font-size:0.7rem; font-weight:600; color:#64748B;">yield anchors</span> / '
            f'{_growth_pct:.0f}% <span style="font-size:0.7rem; font-weight:600; color:#64748B;">growth engine</span></div>'
            f'<div style="font-size:0.9rem; margin-top:0.3rem; color:#F59E0B; font-weight:700;">'
            f'HIGH-BETA AGGRESSIVE</div>'
            f'<div style="font-size:10px; color:#64748B; font-weight:700; letter-spacing:0.05em; '
            f'text-transform:uppercase; margin-top:0.5rem;">'
            f'SYSTEMIC DRIFT: PORTFOLIO VELOCITY IS OPTIMIZED FOR AGGRESSIVE UPSIDE CAPITAL ACCELERATION.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Verplichte institutionele disclaimer -- helemaal onderaan de pagina,
    # klein en gedempt maar altijd zichtbaar.
    st.markdown(
        '<div style="color:#475569; font-size:10px; font-weight:400; letter-spacing:0.03em; '
        'text-transform:uppercase; margin-top:3rem; display:block;">Hestys provides financial data '
        'analysis and systemic exposure metrics for informational purposes only. No content on this '
        'platform constitutes investment, legal, or tax advice.</div>',
        unsafe_allow_html=True,
    )


def _run_ai_risk_alerts(tickers: list, exposure_context: dict, user_email: str = None) -> list:
    """
    Live Claude Haiku-aanroep: vraagt 2-3 ijskoude, PUUR FEITELIJKE
    correlatie-observaties (systemic overlap) over de gegeven tickers als
    GROEP -- geen mening, geen risico-DUIDING, geen actie-advies. Elke
    observatie is een 'Cognitive Scan': welke tickers samen in eenzelfde
    cluster (valuta/sector/land/keten) zitten, plus een kale, meetbare
    data-fact daarover. Geeft een lijst van (cluster, tickers, fact)-
    tuples terug, leeg bij een mislukte/niet-geconfigureerde aanroep.
    ROEPT NOOIT st.error() aan: dit paneel is een aanvulling, geen
    kernfunctie -- een mislukte aanroep hoort de rest van de Stress-Test-
    pagina (tegels, crash-simulator) niet te verstoren.
    """
    import json
    try:
        from anthropic import Anthropic
    except ImportError:
        return []

    api_key = st.secrets.get("ANTHROPIC_API_KEY") or st.secrets.get("anthropic", {}).get("api_key")
    if not api_key or not tickers:
        return []

    _response_language = _detect_ai_response_language(user_email)

    client = Anthropic(api_key=api_key)
    system_prompt = (
        "You are the Hestys Cognitive Scan engine. Given a list of stock tickers making up someone's "
        "portfolio, plus their current largest concentration percentages (country/sector/currency), "
        "identify hidden correlation/systemic-overlap CLUSTERS across the group (e.g. a shared "
        "currency dependency, a shared supply-chain link, a shared macro sensitivity). Respond with "
        "ONLY a raw JSON array -- no markdown fences, no commentary. Each item: {\"cluster\": a short "
        "cluster category label, \"tickers\": array of the specific tickers involved in that cluster, "
        "\"fact\": one single, cold, objective, MEASURABLE data statement about that cluster}. 2 to 3 "
        "items total. STRICT RULES for 'fact': state ONLY a verifiable fact or measurable exposure "
        "(a percentage, a dependency, a shared sensitivity) -- NEVER an opinion, a judgment of whether "
        "this is good or bad, a risk label, or any recommended/implied action (no 'reduce', 'shift', "
        "'buy', 'sell', 'should', 'consider', 'too high', 'risky', target percentages to move to, "
        "etc.). Pure factual correlation data only. 'cluster', 'tickers', and 'fact' MUST all be "
        f"written in {_response_language}, in uppercase (ALL-CAPS). 'fact' is one sentence, no fluff."
    )
    user_prompt = (
        f"Portfolio tickers: {', '.join(tickers)}. "
        f"Current largest exposures -- country: {exposure_context.get('top_country')} "
        f"({exposure_context.get('top_country_pct')}%), sector: {exposure_context.get('top_sector')} "
        f"({exposure_context.get('top_sector_pct')}%), currency: {exposure_context.get('top_currency')} "
        f"({exposure_context.get('top_currency_pct')}%). Identify the sharpest hidden correlation "
        f"clusters across this group."
    )

    with st.spinner("\u2726 Computing black swan stress-tests..."):
        try:
            _api_kwargs = dict(
                model="claude-haiku-4-5-20251001",
                max_tokens=700,
                temperature=0.3,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": "["},
                ],
            )
            try:
                message = client.messages.create(**_api_kwargs)
            except TypeError as _te:
                if "temperature" in str(_te):
                    _api_kwargs.pop("temperature", None)
                    message = client.messages.create(**_api_kwargs)
                else:
                    raise
            raw_text = "[" + message.content[0].text
            alerts_data = json.loads(raw_text)
            # Vangnet: sommige modellen verpakken de array toch in een
            # object (bv. {"alerts": [...]} of {"clusters": [...]}),
            # ondanks de expliciete instructie om een kale array terug te
            # geven. Pak in dat geval de eerste list-waarde die erin zit.
            if isinstance(alerts_data, dict):
                _list_values = [v for v in alerts_data.values() if isinstance(v, list)]
                alerts_data = _list_values[0] if _list_values else []
        except Exception as _e:
            # TIJDELIJK: laat de daadwerkelijke fout zien i.p.v. 'm
            # volledig stil te slikken -- puur om nu te kunnen
            # diagnosticeren waarom er geen alerts verschijnen. Zodra dit
            # bevestigd stabiel werkt, halen we deze regel er weer uit
            # (voor eindgebruikers moet dit straks weer stil falen).
            st.caption(f"Debug -- risk alert generation failed: {_e}")
            return []

    results = []
    for item in alerts_data[:3]:
        if isinstance(item, dict) and item.get("cluster") and item.get("fact"):
            tickers_involved = item.get("tickers") or []
            if isinstance(tickers_involved, list):
                tickers_str = ", ".join(str(t) for t in tickers_involved)
            else:
                tickers_str = str(tickers_involved)
            results.append((str(item["cluster"]), tickers_str, str(item["fact"])))
    return results


def _render_wealth_engine(user_email: str) -> None:
    """
    'Wealth Engine' -- rustgevende dividend- en vermogensprojector.
    Volledig LOSSTAAND van de Conviction Tracker-logica in render_analyze():
    eigen, verse database-aanroepen, geen gedeelde variabelen/state, dus
    kan hier niets van de bestaande tabellen/drawer-logica raken.

    Belangrijke, eerlijke aanname: onze database slaat GEEN losse
    'DEPOSIT'/'ACH'-regels op (die worden bij elke broker-CSV-import
    bewust overgeslagen, zie parse_degiro/robinhood/schwab/trade_republic
    _transactions_csv -- onze transactiestructuur kent alleen buy/sell).
    Er bestaat dus geen letterlijke stortingsgeschiedenis om uit te lezen.
    In plaats daarvan wordt de gemiddelde jaarlijkse inleg GESCHAT uit de
    netto buy-activiteit (aankopen min verkopen) per kalenderjaar -- de
    meest eerlijke proxy die met de beschikbare data mogelijk is. Dat
    wordt in de UI ook letterlijk zo benoemd, i.p.v. te doen alsof het
    exacte, opgegeven stortingen zijn.
    """
    import database as _wealth_db

    holdings = filter_active_holdings(_wealth_db.get_user_holdings(user_email))
    total_value = sum(_eur_position_value(h) for h in holdings)

    if total_value <= 0 or not holdings:
        st.markdown(
            '<div style="background:rgba(15,23,42,0.3); border:1px solid rgba(30,41,59,0.4); '
            'border-radius:14px; padding:2rem; text-align:center; color:#64748B; font-size:0.85rem;">'
            'Add some positions first (see Conviction Tracker) to see your wealth projection.</div>',
            unsafe_allow_html=True,
        )
        return

    # ================================================================
    # SUB-NAVIGATIE: 2 chronologische pills bovenaan -- i.p.v. 1 lange
    # doorlopende scroll (Verleden+Heden+Toekomst onder elkaar), wat als
    # een data-dump aanvoelde en het historie/toekomst-onderscheid
    # vertroebelde. Nu een harde knip: Tab 1 toont UITSLUITEND
    # gerealiseerde historie (geen sliders/projecties), Tab 2 UITSLUITEND
    # de interactieve simulator. st.pills + session_state schakelt
    # flitsloos tussen de twee (gewone Streamlit-widget-rerun, geen
    # page-reload).
    # ================================================================
    if "wealth_engine_sub_tab" not in st.session_state:
        st.session_state["wealth_engine_sub_tab"] = "🕒 HISTORICAL RECORD"
    _wealth_sub_tab = st.pills(
        "Wealth Engine section",
        ["🕒 HISTORICAL RECORD", "🔮 FORWARD PROJECTOR"],
        key="wealth_engine_sub_tab", label_visibility="collapsed",
    )
    st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)

    if _wealth_sub_tab == "🕒 HISTORICAL RECORD":
        # DEEL 1 content: pure geschiedenis -- geen sliders, geen
        # toekomstgrafieken. De actieve pill hierboven ("HISTORICAL RECORD")
        # doet al dienst als sectietitel, dus geen aparte kop meer hier.
        dividend_income_rows = _wealth_db.get_dividend_income(user_email)

        # --- Prop.com (of elke andere 'custom yield asset') se historische
        # maandelijkse cashflow -- er is geen aparte 'startdatum van de
        # investering'-veld; die wordt afgeleid uit de VROEGSTE buy-transactie
        # die bij het aanmaken van zo'n positie altijd wordt gelogd (zie 'Log
        # a transaction' -> custom yield asset). Vanaf die maand t/m de
        # huidige maand krijgt elke kalendermaand 1 cashflow-record.
        def _add_one_month(d):
            return d.replace(year=d.year + 1, month=1) if d.month == 12 else d.replace(month=d.month + 1)

        # Supabase/PostgREST kan een 'numeric'-kolom (zoals custom_annual_
        # cashflow of dividend_income.amount) als STRING teruggeven i.p.v. een
        # kaal getal (om precisieverlies te voorkomen) -- een kale float()/12
        # zou daar met een TypeError op stuklopen, of (erger, stiller) een
        # verkeerd bedrag opleveren. Daarom overal hieronder consequent via
        # deze ene, robuuste _to_float() i.p.v. losse, impliciete conversies.
        def _to_float(value) -> float:
            if value is None:
                return 0.0
            if isinstance(value, (int, float)):
                return float(value)
            try:
                return float(str(value).strip().replace(",", "."))
            except (TypeError, ValueError):
                return 0.0

        _custom_assets = [h for h in holdings if h.get("custom_annual_cashflow") is not None]
        _prop_events = []
        for asset in _custom_assets:
            monthly_amount = _to_float(asset.get("custom_annual_cashflow")) / 12.0
            if monthly_amount <= 0:
                continue
            try:
                asset_txs = _wealth_db.get_transactions_for_holding(user_email, asset["id"])
                start_date = min(
                    (datetime.strptime(t["transaction_date"], "%Y-%m-%d").date() for t in asset_txs),
                    default=None,
                )
            except Exception:
                start_date = None
            if start_date is None:
                continue
            cursor = start_date.replace(day=1)
            current_month = datetime.now().date().replace(day=1)
            while cursor <= current_month:
                _prop_events.append({"date": cursor, "amount_eur": monthly_amount, "naam": asset["naam"]})
                cursor = _add_one_month(cursor)

        # --- Staking (bv. SOL: X van je Y gestakete coins tegen Z% APY, via
        # het losse 'staked_amount'/'staking_apy_pct'-veld op een gewone
        # holding -- HELEMAAL LOS van 'custom_annual_cashflow'/Prop.com
        # hierboven). Zelfde synthetische-maandbedrag-aanpak als Prop.com: de
        # jaarlijkse APY over de EUR-waarde van het gestakete deel gedeeld
        # door 12, vanaf de eerste transactie van die holding. Werkt generiek
        # voor elke holding met beide velden ingevuld, niet alleen SOL.
        _staking_holdings = [h for h in holdings if h.get("staked_amount") and h.get("staking_apy_pct")]
        _staking_events = []
        for h in _staking_holdings:
            total_shares = h.get("shares") or 0
            if total_shares <= 0:
                continue
            staked_fraction = min(_to_float(h.get("staked_amount")) / float(total_shares), 1.0)
            staked_value_eur = _eur_position_value(h) * staked_fraction
            monthly_amount = staked_value_eur * (_to_float(h.get("staking_apy_pct")) / 100) / 12.0
            if monthly_amount <= 0:
                continue
            try:
                asset_txs = _wealth_db.get_transactions_for_holding(user_email, h["id"])
                start_date = min(
                    (datetime.strptime(t["transaction_date"], "%Y-%m-%d").date() for t in asset_txs),
                    default=None,
                )
            except Exception:
                start_date = None
            if start_date is None:
                continue
            cursor = start_date.replace(day=1)
            current_month = datetime.now().date().replace(day=1)
            while cursor <= current_month:
                _staking_events.append({
                    "date": cursor, "amount_eur": monthly_amount,
                    "ticker": h.get("ticker"), "naam": f"{h.get('naam') or h.get('ticker')} (Staking)",
                })
                cursor = _add_one_month(cursor)

        # --- Broker-uitkeringen (database.get_dividend_income(), de ECHTE,
        # PERMANENT opgeslagen historie -- niet de oude, tijdelijke 'dividend_
        # rows'-parserstructuur) hard omzetten naar EUR en optellen bij de
        # Prop.com-reeks hierboven, tot 1 chronologische lijst.
        # Broker-dividenden komen native binnen (USD voor Robinhood/Schwab,
        # EUR/USD gemengd voor DEGIRO's rekeningoverzicht, EUR voor Trade
        # Republic) -- omgerekend met de HUIDIGE wisselkoers (geen historische
        # FX-data beschikbaar per uitkeringsdatum, zelfde bewuste vereenvoudi-
        # ging als elders in de app bij ontbrekende historische koersen). 1x
        # per valuta opgehaald en gecached, niet opnieuw per rij.
        _fx_cache: dict = {}

        def _to_eur(amount: float, currency: str) -> float:
            if not currency or currency == "EUR":
                return amount
            if currency not in _fx_cache:
                _fx_cache[currency] = get_fx_rate(currency, "EUR") or 1.0
            return amount * _fx_cache[currency]

        broker_events = []
        for row in dividend_income_rows:
            raw_date = row.get("payout_date")
            if not raw_date:
                continue
            try:
                event_date = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d").date()
            except Exception:
                continue
            amount_eur = _to_eur(_to_float(row.get("amount")), row.get("currency"))
            if amount_eur <= 0:
                continue
            broker_events.append({
                "date": event_date, "amount_eur": amount_eur,
                "ticker": row.get("ticker"), "naam": row.get("naam") or row.get("ticker"),
            })

        prop_events_eur = [
            {"date": e["date"], "amount_eur": _to_float(e["amount_eur"]), "ticker": "PROP.COM", "naam": e["naam"]}
            for e in _prop_events
        ]

        # De 3 bronnen (broker-dividenden, Prop.com, staking) HARD samenvoegen
        # tot 1 chronologische reeks -- geen enkele overschrijft of verdringt
        # een andere, ze worden simpelweg allemaal in dezelfde lijst gestopt en
        # op datum gesorteerd. Alles verderop (tegels, Ladder, Snowball,
        # Upcoming) rekent UITSLUITEND met deze ene, gecombineerde
        # 'all_events'-lijst -- er is geen aparte, deels-Prop.com- of
        # deels-broker-only berekening meer ergens anders in de functie.
        all_events = broker_events + prop_events_eur + _staking_events
        all_events.sort(key=lambda e: e["date"])

        today_date = datetime.now().date()

        if not all_events:
            st.info(
                "No dividend history yet. Import a broker CSV under Manage -> Import transactions "
                "(Robinhood, Schwab or Trade Republic dividend rows are now tracked automatically), "
                "or add a custom yield asset like Prop.com."
            )
        else:
            # ============================================================
            # 1. METRICS -- 3 tegels, zelfde visuele taal als Today/Stress-Test
            # ============================================================
            _staking_tickers = {h.get("ticker") for h in _staking_holdings}
            total_collected = sum(e["amount_eur"] for e in all_events)
            prop_total = sum(e["amount_eur"] for e in all_events if e["ticker"] == "PROP.COM")
            staking_total = sum(
                e["amount_eur"] for e in all_events
                if e["ticker"] in _staking_tickers and e["naam"].endswith("(Staking)")
            )
            broker_total = total_collected - prop_total - staking_total
            first_date = all_events[0]["date"]
            months_active = max(1, (today_date.year - first_date.year) * 12 + (today_date.month - first_date.month) + 1)
            avg_monthly = total_collected / months_active

            # Payout consistency: hoeveel van de 12 KALENDERMAANDEN (ongeacht
            # jaar) ooit minstens 1 uitkering hebben gezien -- 10 van de 12
            # maanden ooit een uitkering = 83% 'year-round stability'. Meet dus
            # SPREIDING over het jaar, niet het totale aantal uitkeringen.
            months_with_payout = len({e["date"].month for e in all_events})
            consistency_pct = round(months_with_payout / 12 * 100)

            metric_col1, metric_col2, metric_col3 = st.columns(3, gap="medium")
            # Groen blijft over als accent (rand + icoon) en als kleur van de echte
            # datamarks (Ladder-balken, Snowball-fill) -- de tegel-WAARDES zelf
            # gaan naar neutrale inkt (#F1F5F9), anders schreeuwt letterlijk elk
            # element op de pagina in dezelfde emerald-tint en verliest de kleur
            # z'n signaalfunctie ("dit is data die ertoe doet").
            _tile_bg, _tile_border, _tile_color = "rgba(16,185,129,0.10)", "rgba(16,185,129,0.45)", "#34D399"
            _tile_value_color = "#F1F5F9"
            with metric_col1:
                st.markdown(
                    _today_metric_tile_html(
                        "Total Dividends Collected", "payments", f"€{total_collected:,.2f} COLLECTED",
                        _tile_color, _tile_bg, _tile_border, value_color=_tile_value_color,
                        footer_text=(
                            f"Brokers: €{broker_total:,.2f} · Prop.com: €{prop_total:,.2f}"
                            + (f" · Staking: €{staking_total:,.2f}" if staking_total > 0 else "")
                        ),
                    ),
                    unsafe_allow_html=True,
                )
            with metric_col2:
                st.markdown(
                    _today_metric_tile_html(
                        "Average Monthly Payout", "calendar_month", f"€{avg_monthly:,.2f} / MONTH",
                        _tile_color, _tile_bg, _tile_border, value_color=_tile_value_color,
                        footer_text=f"Over {months_active} active month(s)",
                    ),
                    unsafe_allow_html=True,
                )
            with metric_col3:
                st.markdown(
                    _today_metric_tile_html(
                        "Payout Consistency", "payments", f"{consistency_pct}% YEAR-ROUND STABILITY",
                        _tile_color, _tile_bg, _tile_border, value_color=_tile_value_color,
                        footer_text=f"Paid out in {months_with_payout}/12 calendar months",
                    ),
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='height: 2rem'></div>", unsafe_allow_html=True)

            # ============================================================
            # 2 + 3. THE DIVIDEND LADDER + THE DIVIDEND SNOWBALL -- compact
            # side-by-side (50/50), i.p.v. 2 kamerbrede grafieken onder elkaar.
            # Beide via Altair (alt.Chart) i.p.v. Plotly -- smallere, elegantere
            # marks die beter bij Hestys' verfijnde, typografische stijl passen
            # dan Plotly's dikkere standaard-balken/lijnen.
            # ============================================================
            grid_col1, grid_col2 = st.columns([1, 1], gap="medium")

            with grid_col1:
                st.markdown(
                    _uniform_section_header_html("The Dividend Ladder", "bar_chart"),
                    unsafe_allow_html=True,
                )
                # Som per KALENDERMAAND (JAN t/m DEC), over ALLE jaren heen
                # samengevoegd -- ALL-CAPS labels rechtstreeks in de data i.p.v.
                # via CSS text-transform (Altair's axis heeft geen betrouwbare
                # text-transform-optie).
                _month_labels = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                                  "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
                _month_totals = [0.0] * 12
                for e in all_events:
                    _month_totals[e["date"].month - 1] += e["amount_eur"]

                # Alleen de piekmaand(en) direct labelen i.p.v. elke balk -- bij
                # 12 datapunten wordt 'elke balk een eigen tekstlabel' al snel
                # rommelig en voegt weinig toe (de balkhoogte zelf laat het
                # verschil al zien). Top-2 hoogste, niet-nul maanden krijgen een
                # label; de rest laat alleen de hoogte spreken (tooltip on hover
                # toont het exacte bedrag voor elke maand).
                _nonzero_idx = [i for i, v in enumerate(_month_totals) if v > 0]
                _peak_idx = sorted(_nonzero_idx, key=lambda i: _month_totals[i], reverse=True)[:2]
                _ladder_df = pd.DataFrame({
                    "month": _month_labels,
                    "amount": _month_totals,
                    "label": [f"€{v:,.0f}" if i in _peak_idx else "" for i, v in enumerate(_month_totals)],
                })

                _ladder_x = alt.X(
                    "month:N", sort=_month_labels, title=None,
                    # paddingInner (i.p.v. discreteBandSize) trekt de balken smal
                    # en strak op elkaar -- een grote inner-padding t.o.v. de band
                    # zelf, precies het 'geen dikke, brede blokken meer'-effect.
                    scale=alt.Scale(paddingInner=0.5, paddingOuter=0.2),
                    axis=alt.Axis(
                        labelAngle=0, labelColor="#64748B", labelFontSize=10, labelFontWeight=700,
                        labelPadding=6, tickColor="transparent", domainColor="rgba(255,255,255,0.08)",
                    ),
                )
                _ladder_bars = alt.Chart(_ladder_df).mark_bar(
                    color="#34D399", cornerRadiusTopLeft=2, cornerRadiusTopRight=2,
                ).encode(
                    x=_ladder_x,
                    y=alt.Y("amount:Q", axis=None),
                    tooltip=[alt.Tooltip("month:N", title="Month"), alt.Tooltip("amount:Q", title="Amount (€)", format=",.2f")],
                )
                _ladder_labels = alt.Chart(_ladder_df).mark_text(
                    dy=-8, color="#94A3B8", fontSize=10, fontWeight=600,
                ).encode(x=_ladder_x, y=alt.Y("amount:Q"), text="label:N")
                ladder_chart = (
                    (_ladder_bars + _ladder_labels)
                    .properties(height=260, background="transparent")
                    .configure_view(strokeWidth=0)
                )
                st.altair_chart(ladder_chart, use_container_width=True)
                if _peak_idx:
                    _peak_names = " & ".join(_month_labels[i] for i in sorted(_peak_idx))
                    st.caption(f"PEAK IN {_peak_names}: TYPICALLY OVERLAPPING QUARTERLY DIVIDEND PAYOUTS.")

            with grid_col2:
                st.markdown(
                    _uniform_section_header_html("The Dividend Snowball", "trending_up"),
                    unsafe_allow_html=True,
                )
                # Chronologische cumulatieve som per kalender-JAAR-MAAND (dus de
                # ECHTE tijdas, niet Jan-Dec samengevoegd zoals de Ladder
                # hiernaast) -- kan per definitie nooit dalen, elk punt is een
                # cumulatieve som van alles ervoor.
                _by_year_month: dict = {}
                for e in all_events:
                    key = (e["date"].year, e["date"].month)
                    _by_year_month[key] = _by_year_month.get(key, 0.0) + e["amount_eur"]
                _sorted_keys = sorted(_by_year_month.keys())
                _running_total = 0.0
                _snowball_rows = []
                for y, m in _sorted_keys:
                    _running_total += _by_year_month[(y, m)]
                    _snowball_rows.append({"period": f"{y}-{m:02d}", "cumulative": _running_total})
                _snowball_df = pd.DataFrame(_snowball_rows)

                # Zachte, gedempte emerald-groene verloopkleur -- meer opaak vlak
                # onder de lijn (offset 1, top), bijna volledig transparant naar
                # de bodem toe (offset 0) -- een 'gloed' i.p.v. een vlakke,
                # egale vulkleur.
                _snowball_gradient = alt.Gradient(
                    gradient="linear",
                    stops=[
                        alt.GradientStop(color="rgba(52,211,153,0.02)", offset=0),
                        alt.GradientStop(color="rgba(52,211,153,0.20)", offset=1),
                    ],
                    x1=1, x2=1, y1=1, y2=0,
                )
                # Zelfde 'geen as-drukte, direct labelen'-stijl als de Ladder
                # hiernaast i.p.v. een aparte y-as met gridlines (was eerder een
                # inconsistente 2e visuele taal naast de Ladder) -- de y-as +
                # gridlines vervallen volledig, en het eindtotaal wordt als 1
                # direct label bij het laatste punt getoond, net als de
                # pieklabels in de Ladder.
                # X-as: alleen het JAAR labelen bij de januari-maand van elk jaar
                # i.p.v. een label per kalendermaand (was gekanteld -40 graden en
                # oogde druk) -- via labelExpr op de onderliggende 'YYYY-MM'-
                # stringwaarde, horizontaal (0 graden) net als de Ladder's as.
                _snowball_x = alt.X(
                    "period:N", sort=None, title=None,
                    axis=alt.Axis(
                        labelAngle=0, labelColor="#64748B", labelFontSize=10, labelFontWeight=700,
                        labelPadding=6, tickColor="transparent", domainColor="rgba(255,255,255,0.08)",
                        labelExpr="indexof(datum.value, '-01') === 4 ? slice(datum.value, 0, 4) : ''",
                    ),
                )
                snowball_area = alt.Chart(_snowball_df).mark_area(
                    line={"color": "#34D399", "strokeWidth": 2.5},
                    color=_snowball_gradient,
                    interpolate="monotone",
                ).encode(
                    x=_snowball_x,
                    y=alt.Y("cumulative:Q", title=None, axis=None),
                    tooltip=[alt.Tooltip("period:N", title="Month"), alt.Tooltip("cumulative:Q", title="Cumulative (€)", format=",.2f")],
                )
                _snowball_last = _snowball_df.iloc[[-1]].copy()
                _snowball_last["label"] = f"€{_snowball_last['cumulative'].iloc[0]:,.0f}"
                _snowball_end_label = alt.Chart(_snowball_last).mark_text(
                    align="right", dx=-4, dy=-12, color="#34D399", fontSize=11, fontWeight=700,
                ).encode(x=_snowball_x, y=alt.Y("cumulative:Q"), text="label:N")
                snowball_chart = (
                    (snowball_area + _snowball_end_label)
                    .properties(height=260, background="transparent")
                    .configure_view(strokeWidth=0)
                )
                st.altair_chart(snowball_chart, use_container_width=True)

            st.markdown("<div style='height: 1.25rem'></div>", unsafe_allow_html=True)
        # ============================================================
        # 4. UPCOMING PASSIVE INFLOW -- TDIV/KHC/TMUS (als je die aanhoudt)
        # + Prop.com's eerstvolgende 1e van de maand, binnen 60 dagen.
        # Ex-dividend-datum wordt als 'verwachte betaaldatum' gebruikt --
        # zelfde, al-bestaande conventie als radar_data.py's eigen
        # get_upcoming_ex_dividend_dates() (yfinance geeft geen betrouwbare,
        # aparte 'volgende pay-date' terug, ex-dividend-datum is de
        # standaard proxy die deze app al overal gebruikt).
        # ============================================================
        st.markdown(
            _uniform_section_header_html("Upcoming Passive Inflow (60-Day Outlook)", "event_upcoming"),
            unsafe_allow_html=True,
        )
        _watch_tickers = {"TDIV", "KHC", "TMUS"}
        _holdings_by_ticker = {h["ticker"].upper(): h for h in holdings}
        _upcoming_rows = []  # (company, payout_text, date, sort_key)

        for _wt in _watch_tickers:
            _h = _holdings_by_ticker.get(_wt)
            if not _h or not _h.get("shares"):
                continue
            try:
                info = get_cached_ticker_info(_wt)
                ex_div_unix = info.get("exDividendDate")
                if not ex_div_unix:
                    continue
                ex_div_date = pd.Timestamp(ex_div_unix, unit="s").date()
                if not (today_date <= ex_div_date <= today_date + timedelta(days=60)):
                    continue
                per_share = None
                dividends = get_cached_ticker_dividends(_wt)
                if dividends is not None and not dividends.empty:
                    per_share = float(dividends.iloc[-1])
                if not per_share:
                    continue
                expected_amount = per_share * _h["shares"]
                _upcoming_rows.append((_h["naam"] or _wt, f"€{expected_amount:,.2f}", ex_div_date))
            except Exception:
                continue

        # Prop.com (en elke andere custom-cashflow asset): eerstvolgende 1e van
        # de maand, altijd binnen 60 dagen.
        _next_first = (
            today_date.replace(day=1) if today_date.day == 1 else _add_one_month(today_date.replace(day=1))
        )
        for asset in _custom_assets:
            monthly_amount = (asset.get("custom_annual_cashflow") or 0.0) / 12.0
            if monthly_amount <= 0:
                continue
            _upcoming_rows.append((asset["naam"], f"€{monthly_amount:,.2f}", _next_first))

        # Staking (SOL en elke andere gestakete positie): zelfde synthetische
        # maandbedrag als in de historie hierboven, ook geland op de
        # eerstvolgende 1e van de maand.
        for h in _staking_holdings:
            total_shares = h.get("shares") or 0
            if total_shares <= 0:
                continue
            staked_fraction = min(_to_float(h.get("staked_amount")) / float(total_shares), 1.0)
            staked_value_eur = _eur_position_value(h) * staked_fraction
            monthly_amount = staked_value_eur * (_to_float(h.get("staking_apy_pct")) / 100) / 12.0
            if monthly_amount <= 0:
                continue
            _upcoming_rows.append((f"{h.get('naam') or h.get('ticker')} (Staking)", f"€{monthly_amount:,.2f}", _next_first))

        _upcoming_rows.sort(key=lambda r: r[2])

        if not _upcoming_rows:
            st.caption("No upcoming payouts detected within the next 60 days.")
        else:
            _header_style = (
                "text-transform:uppercase; font-size:10px; font-weight:700; color:#475569; "
                "letter-spacing:0.06em; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.1) !important; "
                "border-top:none !important; border-left:none !important; border-right:none !important;"
            )
            _cell_base = (
                "border-bottom:1px solid rgba(255,255,255,0.05) !important; border-top:none !important; "
                "border-left:none !important; border-right:none !important; vertical-align:middle; padding:12px 0;"
            )
            # Vaste, content-krappe kolombreedtes i.p.v. procentuele (40/30/30%
            # op de volle paginabreedte) -- bij 1-2 rijen anders een kamerbrede
            # tabel met absurd veel lege ruimte tussen de kolommen. Tabel zelf
            # ook op een max-breedte gehouden i.p.v. altijd de volle breedte
            # te vullen; groeit gewoon mee zodra er meer rijen/langere namen
            # bijkomen, tot die max-breedte.
            _rows_html = "".join(
                f'<tr>'
                f'<td style="{_cell_base} text-align:left; font-size:0.82rem; font-weight:700; '
                f'color:#F1F5F9; white-space:nowrap;">{company}</td>'
                f'<td style="{_cell_base} text-align:left; font-size:0.82rem; font-weight:600; '
                f'color:#CBD5E1; white-space:nowrap; padding-left:28px;">{payout_text}</td>'
                f'<td style="{_cell_base} text-align:right; font-size:0.78rem; color:#94A3B8; '
                f'white-space:nowrap; padding-left:28px;">{pay_date.strftime("%b %d, %Y")}</td>'
                f'</tr>'
                for company, payout_text, pay_date in _upcoming_rows
            )
            _upcoming_key = "wealth_engine_upcoming_table"
            st.markdown(
                f'<style>.st-key-{_upcoming_key} table {{ border-collapse:collapse; width:auto; '
                f'max-width:560px; }} .st-key-{_upcoming_key} td, .st-key-{_upcoming_key} th '
                f'{{ border:none; }}</style>',
                unsafe_allow_html=True,
            )
            with st.container(key=_upcoming_key):
                st.markdown(
                    f'<table style="border-collapse:collapse; width:auto; max-width:560px;">'
                    f'<thead><tr>'
                    f'<th style="{_header_style} text-align:left;">Company</th>'
                    f'<th style="{_header_style} text-align:left; padding-left:28px;">Expected Payout</th>'
                    f'<th style="{_header_style} text-align:right; padding-left:28px;">Payout Date</th>'
                    f'</tr></thead>'
                    f'<tbody>{_rows_html}</tbody>'
                    f'</table>',
                    unsafe_allow_html=True,
                )

    else:
        # --- 1. Portfolio dividend-metrics -- volledig live uit de Yahoo
        # Finance-koppeling. Een asset zonder dividend (yfinance geeft dan
        # 'None' terug, bv. HIMS/ASTS) weegt nu ECHT als 0% mee in het
        # gewogen gemiddelde -- de eerdere 3%-fallback gold daar ten
        # onrechte ook voor. Die fallback is nu uitsluitend nog een
        # vangnet voor als de API-aanroep zelf faalt (netwerkfout/rate
        # limit), niet voor 'yfinance zegt gewoon: geen dividend'.
        API_FALLBACK_YIELD = 0.03
        _weighted_yield_sum = 0.0
        for h in holdings:
            ticker = h.get("ticker")
            value = _eur_position_value(h)
            if not ticker or value <= 0:
                continue
            _custom_cashflow = h.get("custom_annual_cashflow")
            if _custom_cashflow is not None:
                # Custom yield asset (fractioneel vastgoed, vaste-inkomsten
                # e.d.) -- geen echte ticker om bij Yahoo Finance op te
                # zoeken, dus die stap slaan we hier bewust over. Het
                # rendement wordt direct afgeleid uit de handmatig ingevoerde
                # jaarlijkse cashflow t.o.v. de (eveneens handmatig
                # ingevoerde) positiewaarde.
                y = float(_custom_cashflow) / value
            else:
                try:
                    info = get_cached_ticker_info(ticker)
                    raw_yield = info.get("dividendYield")
                    if raw_yield is None:
                        # Yahoo Finance heeft dit ticker's dividend-veld gewoon
                        # leeg -- meestal omdat de asset simpelweg geen dividend
                        # uitkeert. Telt dus terecht als 0%, geen fallback.
                        y = 0.0
                    else:
                        y = float(raw_yield)
                        # yfinance geeft dividendYield soms als fractie (0.03) en
                        # soms al als percentage (3.05) -- afhankelijk van de
                        # yfinance-versie. Alles boven 1 wordt daarom als
                        # 'al-een-percentage' behandeld.
                        if y > 1:
                            y = y / 100
                        if y < 0:
                            y = 0.0
                except Exception:
                    # De API-aanroep zelf faalde (i.p.v. een geldig 'geen
                    # dividend'-antwoord) -- hier WEL de fallback, want dit is
                    # echt ontbrekende data, geen bevestigd 0%-dividend.
                    y = API_FALLBACK_YIELD
            _weighted_contribution = value * y

            # Staking -- een DEEL van deze positie (in aandelen/coins, niet
            # euro's) kan los een eigen yield opleveren, bv. 20 van 50
            # gehouden SOL gestaked tegen 7% APY. Telt BOVENOP de gewone
            # markt-yield hierboven mee (niet als vervanging) -- bij crypto
            # is die toch al 0%, maar dit werkt ook voor een aandeel met
            # zowel dividend als een apart gestaked deel.
            _staked_amount = h.get("staked_amount")
            _staking_apy = h.get("staking_apy_pct")
            _total_shares = h.get("shares") or 0
            if _staked_amount and _staking_apy and _total_shares > 0:
                _staked_fraction = min(float(_staked_amount) / float(_total_shares), 1.0)
                _staked_value_eur = value * _staked_fraction
                _staking_contribution = _staked_value_eur * (float(_staking_apy) / 100)
                _weighted_contribution += _staking_contribution

            _weighted_yield_sum += _weighted_contribution
        live_avg_yield = (_weighted_yield_sum / total_value) if total_value else 0.0
        annual_cashflow = total_value * live_avg_yield

        # Dividendgroei: Yahoo Finance biedt geen betrouwbaar 'historisch
        # dividend-CAGR'-veld per ticker (in tegenstelling tot dividendYield,
        # dat wel live opgehaald kan worden) -- daarom werken we hier met een
        # eigen, GECUREERDE tabel met bekende dividendgroei-tempo's voor de
        # tickers die we kennen (op basis van hun eigen track record), en 0%
        # voor alles wat niet in die tabel staat. Het gewogen gemiddelde
        # daarvan (naar positiegrootte, exact dezelfde methode als bij
        # Average Portfolio Yield hierboven) wordt de DYNAMISCHE start-
        # baseline, i.p.v. een vaste 5% voor iedereen.
        _KNOWN_DIVIDEND_GROWTH_RATES = {
            "TDIV": 0.05,
            "KHC": 0.01,
            "TMUS": 0.10,
        }
        _weighted_growth_sum = 0.0
        for h in holdings:
            ticker = (h.get("ticker") or "").upper()
            value = _eur_position_value(h)
            if not ticker or value <= 0:
                continue
            _weighted_growth_sum += value * _KNOWN_DIVIDEND_GROWTH_RATES.get(ticker, 0.0)
        DIVIDEND_GROWTH_RATE = (_weighted_growth_sum / total_value) if total_value else 0.0

        # --- Jaarlijkse inleg schatten uit netto buy-activiteit per jaar --
        # VOOR de tegels berekend (i.p.v. erna), want de 4e tegel toont 'm nu
        # ook. Zelfde eerlijke aanname als eerder: onze database kent geen
        # losse DEPOSIT/ACH-regels (die worden bij elke broker-CSV-import
        # bewust overgeslagen), dus dit is de netto buy-activiteit als
        # proxy, niet een letterlijke stortingshistorie.
        _yearly_net_buys = {}
        for h in holdings:
            txs = _wealth_db.get_transactions_for_holding(user_email, h["id"])
            for t in txs:
                try:
                    yr = int(t["transaction_date"][:4])
                except (TypeError, ValueError, KeyError):
                    continue
                amount = (t.get("shares") or 0) * (t.get("price") or 0) + (t.get("fee") or 0)
                if t.get("transaction_type") == "buy":
                    _yearly_net_buys[yr] = _yearly_net_buys.get(yr, 0) + amount
                else:
                    _yearly_net_buys[yr] = _yearly_net_buys.get(yr, 0) - amount

        if _yearly_net_buys:
            annual_contribution = max(sum(_yearly_net_buys.values()) / len(_yearly_net_buys), 0.0)
        else:
            annual_contribution = 0.0

        # DEEL 2 content: sliders + projectie -- eigen sub-tab, dus geen
        # scheidingslijn meer nodig boven de sliders (niets hierboven op
        # dezelfde tab om van te scheiden).
        # --- 2. Simulation Control Panel -- NU VOOR de tegels gerenderd
        # (i.p.v. erna), zodat tegel 1 rechtstreeks de teruggegeven waarde
        # van yield_slider kan gebruiken -- geen omweg via session_state
        # meer nodig, dus geen enkele twijfel meer over of de koppeling
        # daadwerkelijk elke rerun meebeweegt.
        _sim_key = "wealth_engine_sim_panel"
        st.markdown(
            f'<style>'
            f'.st-key-{_sim_key} label p {{ '
            f'font-size:10px !important; font-weight:700 !important; letter-spacing:0.06em !important; '
            f'text-transform:uppercase !important; color:#64748B !important; }} '
            f'</style>',
            unsafe_allow_html=True,
        )
        with st.container(key=_sim_key):
            sim_col1, sim_col2, sim_col3 = st.columns(3, gap="medium")
            with sim_col1:
                growth_slider = st.slider(
                    "Expected annual growth (price)", min_value=0.0, max_value=15.0,
                    value=7.0, step=0.5, key="wealth_growth_slider", format="%.1f%%",
                )
            with sim_col2:
                yield_slider = st.slider(
                    "Simulated dividend yield", min_value=0.0, max_value=10.0,
                    value=round(live_avg_yield * 100, 1), step=0.1, key="wealth_yield_slider", format="%.1f%%",
                )
                # 'value=' hierboven werkt ALLEEN bij de allereerste keer dat
                # deze slider in je sessie getekend wordt -- daarna blijft 'ie
                # op zijn laatst-versleepte positie staan, ook als de live
                # yield-berekening daarna verandert (bv. door een eerdere,
                # inmiddels-gefixte yfinance-hik die de starende waarde ooit
                # verkeerd zette). Deze knop zet 'm expliciet terug naar de
                # ZOJUIST verse berekening, zonder op een sessie-reset te
                # hoeven wachten.
                #
                # BUGFIX: session_state[key] direct zetten NA het tekenen van
                # de slider (binnen dezelfde run) is verboden in Streamlit --
                # StreamlitWidgetAlreadyInstantiatedError. Via on_click i.p.v.
                # een gewone if-knop: die callback draait VOORDAT de widgets
                # van de volgende run getekend worden, dus dat is wel
                # toegestaan.
                def _reset_yield_to_live(_live_value=round(live_avg_yield * 100, 1)):
                    st.session_state["wealth_yield_slider"] = _live_value

                st.button("\u21bb Reset to live yield", key="wealth_yield_reset_btn", on_click=_reset_yield_to_live)
            with sim_col3:
                contribution_slider = st.slider(
                    "Simulated annual contribution", min_value=0, max_value=50000,
                    value=int(round(annual_contribution)), step=500, key="wealth_contribution_slider",
                    format="\u20ac%d",
                )
        st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

        # De pill "FORWARD PROJECTOR" doet al dienst als sectietitel, dus
        # geen aparte "The Forward Projection"-kop meer hier.

        # --- Strak 4-koloms grid -- tegel 1 gebruikt nu rechtstreeks
        # yield_slider (de teruggegeven waarde van de widget hierboven), dus
        # gegarandeerd correct bij elke rerun/sleepbeweging.
        tile_col1, tile_col2, tile_col3, tile_col4 = st.columns(4, gap="medium")
        _tile_style = (
            'background:rgba(15,23,42,0.3); border:1px solid rgba(30,41,59,0.4); '
            'border-radius:12px; padding:1rem; text-align:left;'
        )
        simulated_annual_cashflow = total_value * (yield_slider / 100)
        with tile_col1:
            st.markdown(
                f'<div style="{_tile_style}">'
                f'<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; '
                f'color:#8992A3; margin-bottom:0.4rem;">&#128188; Annual passive cashflow</div>'
                f'<div style="font-size:1.4rem; font-weight:800; color:#F1F5F9;">&euro;{simulated_annual_cashflow:,.0f} '
                f'<span style="font-size:0.75rem; font-weight:600; color:#64748B;">/ year</span></div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with tile_col2:
            st.markdown(
                f'<div style="{_tile_style}">'
                f'<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; '
                f'color:#8992A3; margin-bottom:0.4rem;">&#128200; Average portfolio yield</div>'
                f'<div style="font-size:1.4rem; font-weight:800; color:#F1F5F9;">{live_avg_yield * 100:.2f}% '
                f'<span style="font-size:0.75rem; font-weight:600; color:#64748B;">yield</span></div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with tile_col3:
            st.markdown(
                f'<div style="{_tile_style}">'
                f'<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; '
                f'color:#8992A3; margin-bottom:0.4rem;">&#8987; Dividend growth rate</div>'
                f'<div style="font-size:1.4rem; font-weight:800; color:#F1F5F9;">{DIVIDEND_GROWTH_RATE * 100:.1f}% '
                f'<span style="font-size:0.75rem; font-weight:600; color:#64748B;">CAGR (est.)</span></div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with tile_col4:
            st.markdown(
                f'<div style="{_tile_style}">'
                f'<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; '
                f'color:#8992A3; margin-bottom:0.4rem;">&#128188; Annual contribution (est.)</div>'
                f'<div style="font-size:1.4rem; font-weight:800; color:#F1F5F9;">&euro;{contribution_slider:,.0f} '
                f'<span style="font-size:0.75rem; font-weight:600; color:#64748B;">/ year</span></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

        # --- Compounding-engine: 30-jarige projectie -- volledig gekoppeld
        # aan de 3 sliders hierboven. Streamlit herrekent en hertekent de
        # grafiek automatisch bij elke slider-beweging (gewone widget-
        # rerun), dus dit is al flitsloos/live zonder verdere aanpassingen.
        PROJECTION_YEARS = 30
        current_year = datetime.now().year
        simulated_price_growth = growth_slider / 100
        simulated_starting_cashflow = total_value * (yield_slider / 100)
        simulated_contribution = float(contribution_slider)

        # Dividend-groeitempo nu deels gekoppeld aan de EXPECTED ANNUAL
        # GROWTH-slider i.p.v. een volledig losstaande, vaste 5% -- bedrijven
        # met sterkere koersgroei verhogen doorgaans ook hun dividend sneller
        # (aangedreven door dezelfde onderliggende winstgroei). 50%-doorwerking
        # van elke afwijking t.o.v. de 7%-baseline, geclamped tussen 0% en 15%
        # zodat het nooit een onrealistisch of negatief tempo oplevert. Zonder
        # deze koppeling bleef het dividendinkomen (en dus de YoY-versnellings-
        # grafiek hieronder) altijd vlak op +5,0% staan, ongeacht de sliders --
        # dat leek eerder niet de bedoeling.
        _baseline_price_growth = 0.07
        effective_dividend_growth_rate = DIVIDEND_GROWTH_RATE + (simulated_price_growth - _baseline_price_growth) * 0.5
        effective_dividend_growth_rate = max(0.0, min(0.15, effective_dividend_growth_rate))

        years = [current_year]
        net_deposits = [total_value]
        total_wealth = [total_value]
        dividend_income_by_year = [simulated_starting_cashflow]

        # Het dividendinkomen wordt berekend als (vermogen op dat moment) x
        # (dividendrendement-per-aandeel op dat moment) -- i.p.v. een
        # dividendbedrag dat volledig LOSSTAAT van hoeveel vermogen er
        # daadwerkelijk is opgebouwd. Zo werkt herbeleggen/compounding pas
        # ECHT door: elk jaar extra ingelegd geld EN elk herbelegd dividend
        # vergroot de vermogensbasis waarover het VOLGENDE jaar weer dividend
        # wordt uitgekeerd. Het dividendrendement-per-aandeel zelf groeit nog
        # steeds licht per jaar (effective_dividend_growth_rate, gekoppeld
        # aan de groei-slider) -- dat simuleert dat bedrijven hun dividend
        # per aandeel verhogen, los van hoeveel aandelen je bezit.
        #
        # BELANGRIJK (bugfix): vermogen/rendement worden nu EERST voor het
        # nieuwe jaar bijgewerkt, en PAS DAARNA wordt dat jaar's dividend
        # berekend uit die vernieuwde stand. Eerder gebeurde dit in de
        # omgekeerde volgorde, waardoor jaar 1's dividend nog exact de OUDE
        # (jaar 0-)stand van vermogen/rendement gebruikte -- identiek aan
        # jaar 0 zelf, dus altijd +0,0% YoY in het eerste jaar, ongeacht de
        # sliders. Nu groeit elk jaar daadwerkelijk door t.o.v. het vorige.
        _wealth = total_value
        _deposits = total_value
        _yield_rate = yield_slider / 100
        for i in range(1, PROJECTION_YEARS + 1):
            _prior_dividend = dividend_income_by_year[-1]
            capital_growth = _wealth * simulated_price_growth
            _wealth = _wealth + capital_growth + _prior_dividend + simulated_contribution
            _deposits = _deposits + simulated_contribution
            _yield_rate = _yield_rate * (1 + effective_dividend_growth_rate)
            _dividend_this_year = _wealth * _yield_rate
            years.append(current_year + i)
            net_deposits.append(_deposits)
            total_wealth.append(_wealth)
            dividend_income_by_year.append(_dividend_this_year)

        # --- 3. Wealth Acceleration chart -- visuele legenda met gekleurde
        # lijntjes i.p.v. bullet-tekens (nu ONDER de chart, gevolgd door de
        # gedempte simulatie-parameters). ---
        wealth_fig = go.Figure()
        wealth_fig.add_trace(go.Scatter(
            x=years, y=net_deposits, name="Net Deposits", mode="lines",
            line=dict(color="rgba(148,163,184,0.55)", width=1.5),
            fill="tozeroy", fillcolor="rgba(148,163,184,0.08)",
            hovertemplate="%{x}: €%{y:,.0f}<extra></extra>",
        ))
        wealth_fig.add_trace(go.Scatter(
            x=years, y=total_wealth, name="Total Wealth", mode="lines",
            line=dict(color="#34D399", width=2.5),
            fill="tonexty", fillcolor="rgba(52,211,153,0.08)",
            hovertemplate="%{x}: €%{y:,.0f}<extra></extra>",
        ))
        wealth_fig.update_layout(
            height=340,
            margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            xaxis=dict(showgrid=False, zeroline=False, color="#64748B", tickfont=dict(size=10)),
            yaxis=dict(showgrid=False, zeroline=False, color="#64748B", tickfont=dict(size=10),
                       tickprefix="\u20ac", tickformat=",.0f"),
            hovermode="x unified",
            hoverlabel=dict(bgcolor="#101825", font_size=11, font_family="Inter"),
        )
        st.plotly_chart(wealth_fig, use_container_width=True, config={"displayModeBar": False})

        _legend_line_style = (
            'display:inline-block; width:14px; height:3px; border-radius:2px; '
            'margin-right:6px; vertical-align:middle;'
        )
        st.markdown(
            f'<div style="color:#64748B; font-size:10px; font-weight:700; letter-spacing:0.05em; '
            f'text-transform:uppercase; margin-top:15px; margin-bottom:1.5rem; line-height:1.9;">'
            f'<div><span style="{_legend_line_style} background-color:#64748b;"></span>Net Deposits</div>'
            f'<div><span style="{_legend_line_style} background-color:#34d399;"></span>Total Wealth</div>'
            f'<div style="margin-top:0.3rem;">Projected at {growth_slider:.1f}% growth + '
            f'{yield_slider:.1f}% reinvested yield</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
        # --- Cashflow Velocity -- absolute jaarlijkse passieve cashflow in
        # euro's, i.p.v. procentuele YoY-groei. Dalende groei-percentages
        # (het onvermijdelijke gevolg van compounding tegen een VASTE
        # jaarlijkse inleg, zie de projectie hierboven) voelden demotiverend
        # aan, terwijl het harde euro-bedrag zelf ieder jaar juist stevig
        # stijgt -- dat vliegwiel-effect komt hier nu rechtstreeks in beeld.
        # Geen st.bar_chart/plotly-staafgrafiek meer -- die paste met dikke,
        # platte balken totaal niet bij Hestys' rustige, typografische stijl.
        # Nu een pure HTML-datamatrix: 5 kolommen (komende 5 jaar), elk met
        # jaartal / absoluut eurobedrag / YoY-versnelling eronder. Puur
        # afgeleid van dezelfde dividend_income_by_year-reeks die de 3
        # sliders hierboven al voeden, dus deze matrix herrekent vanzelf mee
        # zodra je aan een slider schuift -- geen aparte logica nodig.
        st.markdown(
            '<div style="color:#94A3B8; font-size:0.875rem; font-weight:700; letter-spacing:0.05em; '
            'text-transform:uppercase; border-bottom:1px solid rgba(255,255,255,0.05); '
            'padding-bottom:8px; margin-bottom:15px;">&#128202; Passive Cashflow Acceleration '
            '(5-Year Velocity Matrix)</div>',
            unsafe_allow_html=True,
        )
        _matrix_cells_html = ""
        for i in range(0, 5):
            _yr = years[i]
            _eur = dividend_income_by_year[i]
            if i == 0:
                # Kolom 1 = HUIDIG jaar (2026) = je echte, actuele live cashflow
                # -- geen +YoY-berekening nodig/mogelijk, dit IS het startpunt
                # zelf, exact synchroon met de historische grafiek hierboven
                # (die ook in het huidige jaar eindigt).
                _yoy_html = '<div style="font-size:11px; font-weight:700; color:#34d399;">BASELINE</div>'
            else:
                _prev = dividend_income_by_year[i - 1]
                _pct = ((_eur - _prev) / _prev * 100) if _prev > 0 else 0.0
                _yoy_html = f'<div style="font-size:11px; font-weight:700; color:#34d399;">+{_pct:.1f}% YOY</div>'
            _matrix_cells_html += (
                f'<div style="width:20%; text-align:center;">'
                f'<div style="font-size:10px; font-weight:700; color:#475569; letter-spacing:0.05em; '
                f'text-transform:uppercase;">{_yr}</div>'
                f'<div style="font-size:16px; font-weight:700; color:#ffffff; padding:4px 0;">&euro;{_eur:,.0f}</div>'
                f'{_yoy_html}'
                f'</div>'
            )
        st.markdown(
            f'<div style="display:flex; width:100%;">{_matrix_cells_html}</div>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)

        # --- 4. Snowball Milestones -- echte <table> met expliciete border-
        # onderdrukking (zie verderop), 3 kolommen: Milestone / Required
        # Cashflow / Target Year.
        st.markdown(
            _uniform_section_header_html("Snowball Milestones", "shield", is_first=False),
            unsafe_allow_html=True,
        )

        def _find_milestone_year(condition):
            for idx, yr in enumerate(years):
                if condition(idx):
                    return yr
            return None

        # Onwrikbare ladder van 6 universele, oplopende mijlpalen -- van een
        # kopje koffie tot financial independence. Elke drempel is vast
        # (dividend_income_by_year >= X), behalve The Crossover Event, die
        # relatief blijft t.o.v. de SIMULEERBARE inleg-slider.
        _milestone_espresso = _find_milestone_year(lambda idx: dividend_income_by_year[idx] >= 60)
        _milestone_dinner = _find_milestone_year(lambda idx: dividend_income_by_year[idx] >= 250)
        _milestone_travel = _find_milestone_year(lambda idx: dividend_income_by_year[idx] >= 1200)
        _milestone_baseline = _find_milestone_year(lambda idx: dividend_income_by_year[idx] >= 5000)
        _milestone_crossover = _find_milestone_year(
            lambda idx: dividend_income_by_year[idx] > simulated_contribution
        ) if simulated_contribution > 0 else None
        # Instelbaar via Settings (was eerder een vast €30.000 voor iedereen) --
        # default €60.000 als de gebruiker nog nooit iets heeft ingesteld.
        _fi_target = _wealth_db.get_user_preferences(user_email).get("financial_independence_target") or 60000.0
        _milestone_freedom = _find_milestone_year(lambda idx: dividend_income_by_year[idx] >= _fi_target)

        def _milestone_year_html(year_val):
            if year_val is None:
                # Buiten de 30-jarige horizon -- gedempte rose/rode waarschuwings-
                # kleur, i.p.v. dezelfde neutrale grijstint als een bereikte
                # mijlpaal. Geeft meteen een visuele prikkel welke doelen nog
                # niet binnen bereik liggen.
                return '<span style="color:rgba(244,63,94,0.6); font-weight:700; letter-spacing:0.03em; white-space:nowrap;">&gt; 30 YRS</span>'
            if year_val == current_year:
                # Al VANDAAG bereikt (jaar 0 van de projectie) -- een groen
                # vinkje ernaast, ter onderscheid van een toekomstige
                # projectie die nog moet gebeuren.
                return (
                    f'<span style="color:#34d399; font-weight:700;">{year_val}</span> '
                    f'<span style="color:#34d399;">&#10003;</span>'
                )
            # Binnen de 30 jaar, maar pas in de TOEKOMST -- amber/oranje i.p.v.
            # groen, zodat groen exclusief 'nu al gehaald' betekent en oranje
            # 'onderweg, nog niet zover'.
            return f'<span style="color:#FBBF24; font-weight:700;">{year_val}</span>'

        # (naam, technische voorwaarde, jaartal-html)
        milestone_rows = [
            ("The Daily Espresso", "&euro;60", _milestone_year_html(_milestone_espresso)),
            ("The Dinner Appreciation", "&euro;250", _milestone_year_html(_milestone_dinner)),
            ("The Concierge Travel", "&euro;1,200", _milestone_year_html(_milestone_travel)),
            ("The Baseline Cover", "&euro;5,000", _milestone_year_html(_milestone_baseline)),
            ("The Crossover Event", "CASHFLOW &gt; CONTRIBUTION", _milestone_year_html(_milestone_crossover)),
            ("Financial Independence", f"&euro;{_fi_target:,.0f}", _milestone_year_html(_milestone_freedom)),
        ]

        # Echte <table> met <thead>, deze keer met HARDE, expliciete
        # onderdrukking van elke default-tabelrand (border:none !important op
        # elke cel) -- een vorige poging met een raw <table> kreeg ongewenste
        # verticale kolomlijnen via Streamlit's eigen basis-stylesheet, dat
        # voorkomen we nu expliciet i.p.v. te vertrouwen op border-collapse
        # alleen. Nu ook met een max-width-restrictie op de tabel zelf, zodat
        # de data compact links/midden blijft i.p.v. tot de rand van het
        # scherm uit te rekken.
        _milestones_key = "wealth_engine_milestones_table"
        _header_style = (
            "text-transform:uppercase; font-size:10px; font-weight:700; color:#475569; "
            "letter-spacing:0.06em; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.1) !important; "
            "border-top:none !important; border-left:none !important; border-right:none !important;"
        )
        _cell_base = (
            "border-bottom:1px solid rgba(255,255,255,0.05) !important; border-top:none !important; "
            "border-left:none !important; border-right:none !important; vertical-align:middle; padding:12px 0;"
        )
        _rows_html = "".join(
            f'<tr>'
            f'<td style="{_cell_base} width:35%; text-align:left; text-transform:uppercase; '
            f'font-size:0.78rem; font-weight:700; color:#F1F5F9;">{name}</td>'
            f'<td style="{_cell_base} width:35%; text-align:left; text-transform:uppercase; '
            f'font-size:0.69rem; font-weight:600; color:#64748b;">{value}</td>'
            f'<td style="{_cell_base} width:30%; text-align:right; font-size:0.78rem;">{year_html}</td>'
            f'</tr>'
            for name, value, year_html in milestone_rows
        )
        st.markdown(
            f'<style>.st-key-{_milestones_key} table {{ width:100%; border-collapse:collapse; }} '
            f'.st-key-{_milestones_key} td, .st-key-{_milestones_key} th {{ border:none; }}</style>',
            unsafe_allow_html=True,
        )
        with st.container(key=_milestones_key):
            st.markdown(
                f'<div style="max-width:640px;">'
                f'<table style="width:100%; border-collapse:collapse;">'
                f'<thead><tr>'
                f'<th style="{_header_style} width:35%; text-align:left;">Milestone</th>'
                f'<th style="{_header_style} width:35%; text-align:left;">Required cashflow</th>'
                f'<th style="{_header_style} width:30%; text-align:right;">Target year</th>'
                f'</tr></thead>'
                f'<tbody>{_rows_html}</tbody>'
                f'</table>'
                f'</div>',
                unsafe_allow_html=True,
            )


def render_wealth_engine():
    """
    'Wealth Engine' -- eigen hoofdpagina in de linker sidebar (net als
    voorheen 'Dividend'), i.p.v. een pill weggestopt onder Analyze. Toont
    de gefuseerde dividend-historie + 30-jaar projectie uit
    _render_wealth_engine() (die functie blijft ongewijzigd/herbruikbaar,
    dit is uitsluitend de pagina-wrapper eromheen: login-gate, mobiele
    overflow-vangnet en de paginatitel).
    """
    if not current_user.is_logged_in:
        _render_landing_soft_lock(
            title="Wealth Engine",
            icon_name="trending_up",
            cta_text="&#128274; TRACK YOUR REALIZED DIVIDEND HISTORY AND SIMULATE YOUR "
                      "30-YEAR PASSIVE INCOME PROJECTION.",
            button_label="Unlock Wealth Engine →",
            preview_html=_landing_chart_skeleton_html(),
            key_prefix="wealth_engine",
        )
        st.stop()

    # Zelfde mobiele-overflow-vangnet als Analyze -- deze pagina bevat
    # dezelfde brede Altair/Plotly-grafieken en tabellen die eerder onder
    # Analyze stonden, dus hetzelfde risico op ongewenste horizontale
    # scroll op mobiel.
    st.markdown(
        """
        <style>
        @media (max-width:768px) {
            [data-testid="stAppViewContainer"], [data-testid="stMain"], body {
                overflow-x: hidden !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        _uniform_section_header_html("Wealth Engine", "trending_up", is_first=True),
        unsafe_allow_html=True,
    )

    _render_wealth_engine(current_user.email)


def render_analyze():
    if not current_user.is_logged_in:
        _render_landing_soft_lock(
            title="Portfolio Analytics",
            icon_name="bar_chart",
            cta_text="&#128274; UNLOCK DEEP PORTFOLIO ANALYTICS. VIEW YOUR ASSET ALLOCATION, RISK "
                      "METRICS AND HISTORICAL PERFORMANCE.",
            button_label="Unlock Deep Portfolio Analytics \u2192",
            preview_html=_landing_chart_skeleton_html(),
            key_prefix="analyze",
        )
        st.stop()

    import database

    user_email = current_user.email

    if "selected_research" not in st.session_state:
        st.session_state["selected_research"] = None

    # Vangnet tegen elke horizontale overflow op mobiel (welke bron dan
    # ook) die de HELE pagina schuifbaar zou maken i.p.v. alleen intern
    # netjes af te kappen.
    st.markdown(
        """
        <style>
        @media (max-width:768px) {
            [data-testid="stAppViewContainer"], [data-testid="stMain"], body {
                overflow-x: hidden !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        _uniform_section_header_html("Portfolio Analytics", "bar_chart", is_first=True),
        unsafe_allow_html=True,
    )
    # Marketing-indicator: maakt zichtbaar dat er een AI-copilot achter
    # het platform zit -- rechtsboven, dicht tegen de hoofdsectietitel
    # aan getrokken via een negatieve margin-top. '+ Add New' is
    # verhuisd naar de Research Watchlist-sectie hieronder (dat is waar
    # nieuwe research daadwerkelijk aan toegevoegd wordt), dus deze
    # regel pakt nu zelf de -2.5rem-pull-up die eerder voor de knop was.
    st.markdown(
        '<div style="display:flex; justify-content:flex-end; margin-top:-2.5rem; margin-bottom:1.25rem;">'
        '<span style="font-size:10px; font-weight:700; letter-spacing:0.1em; color:#64748B; '
        'text-transform:uppercase;">&#9889; Cognitive co-pilot powered by Anthropic Claude&trade;</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Horizontale pills-navigatie i.p.v. losse sidebar-sub-items --
    # 'Conviction Tracker' is de bestaande, volledig uitgewerkte inhoud
    # van deze pagina. 'Wealth Engine' is VERHUISD naar een eigen
    # hoofdpagina in de linker sidebar (zie render_wealth_engine() +
    # wealth_engine_page hieronder) i.p.v. een pill hier -- die kreeg
    # inmiddels genoeg eigen inhoud (dividend-historie + 30-jaar
    # projectie) om als volwaardige, losstaande pagina te verdienen i.p.v.
    # weggestopt te zitten onder Analyze.
    if "active_sub_section_analyze" not in st.session_state:
        st.session_state["active_sub_section_analyze"] = "CONVICTION TRACKER"
    _analyze_sub_choice = st.pills(
        "Analyze section",
        ["CONVICTION TRACKER", "STRESS-TEST"],
        key="active_sub_section_analyze", label_visibility="collapsed",
    )
    st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)

    if _analyze_sub_choice == "STRESS-TEST":
        _render_stress_test(user_email)
        return

    holdings = filter_active_holdings(database.get_user_holdings(user_email))
    total_portfolio_value = sum(h.get("position_value") or 0 for h in holdings)
    held_tickers = {h["ticker"] for h in holdings if h.get("ticker")}
    holding_weight_by_ticker = {
        h["ticker"]: ((h.get("position_value") or 0) / total_portfolio_value * 100 if total_portfolio_value else 0)
        for h in holdings if h.get("ticker")
    }

    deep_dives = database.get_all_deep_dive_tickers(user_email)

    # --- 2-koloms drawer-splitsing: alleen actief zodra er iets
    # geselecteerd is (een ticker, of '__NEW__'). Zonder selectie vult
    # het overzicht de volledige breedte. ---
    _drawer_open = st.session_state["selected_research"] is not None
    if _drawer_open:
        # Iets bredere drawer nu de tabel zelf smaller/compacter is
        # geworden (max-width:640px) -- er is rechts genoeg lucht voor.
        _main_outer, drawer_col = st.columns([1.4, 1], gap="large")
        # main_col wordt nu een GENESTE container MET eigen key, i.p.v.
        # de kolom zelf -- zo hoeft de grote, bestaande 'with main_col:'-
        # content hieronder niet opnieuw ingesprongen te worden, en kan
        # de CSS hierboven 'm toch precies raken.
        with _main_outer:
            main_col = st.container(key="analyze_main_mobile_wrap")
        # Mobiel (<768px): st.columns() stapelt van zichzelf al verticaal,
        # maar we willen niet dat de tabellen dan nog BOVEN de drawer
        # meerenderen (dat gaf het 'formulier opent onzichtbaar
        # helemaal onderaan'-probleem). CSS-only 'scherm-switch': de
        # linkerkolom-inhoud krijgt een eigen container-key en wordt op
        # mobiel volledig verborgen; de drawer-kolom vult dan de volle
        # breedte. Geen JS/schermbreedte-detectie in Python nodig --
        # we weten al server-side of de drawer open is, en CSS regelt de
        # rest puur op basis van viewport-breedte.
        st.markdown(
            """
            <style>
            @media (max-width:768px) {
                .st-key-analyze_main_mobile_wrap { display:none !important; }
                .st-key-analyze_drawer { width:100% !important; }
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        main_col, drawer_col = st.container(), None

    with main_col:
        # --- 1. Conviction-tegels: som van portfolio-gewicht per score-
        # bucket, uitsluitend voor BEZETEN assets waar ook een deep-dive-
        # score voor bestaat. Alles wat bezeten is MAAR geen deep-dive
        # heeft (de 'blinde vlekken') wordt apart bijgehouden -- telt in
        # geen van de 3 tegels mee, maar bepaalt de waarschuwingsbalk
        # eronder. ---
        dive_by_ticker = {e.get("ticker"): e for e in deep_dives}
        high_weight = medium_weight = low_weight = unmapped_weight = 0.0
        unmapped_assets = []
        for h in holdings:
            ticker = h.get("ticker")
            if not ticker:
                continue
            weight = holding_weight_by_ticker.get(ticker, 0)
            entry = dive_by_ticker.get(ticker)
            score = _compute_deep_dive_overall_score(entry) if entry else None
            if score is None:
                unmapped_weight += weight
                unmapped_assets.append({"ticker": ticker, "naam": h.get("naam", ticker)})
            elif score >= 8:
                high_weight += weight
            elif score >= 5.5:
                # Grens ligt op 5.5, niet 5.0 -- consistent met de
                # Nederlandse schoolcijfer-logica die ook de rode
                # score-kleur elders bepaalt ('onvoldoende' onder een 5.5).
                medium_weight += weight
            else:
                low_weight += weight

        tiles_html = (
            _conviction_tile_html("\U0001F7E2", "High conviction (8-10)", high_weight)
            + _conviction_tile_html("\U0001F7E1", "Medium conviction (5.5-7.9)", medium_weight)
            + _conviction_tile_html("\U0001F534", "Speculative / Low (0-5.4)", low_weight, warn=(low_weight > 15))
        )
        # De 3 tegels (en de waarschuwingsbalk) verdwijnen VOLLEDIG zodra
        # de drawer open staat -- eerder werden ze alleen smaller
        # gemaakt (1 kolom i.p.v. 3), wat ze onder elkaar propte in de
        # al krappe linkerkolom. Nu is er simpelweg geen ruimte-conflict
        # meer: ze komen pas weer terug, over de volle breedte, zodra de
        # drawer weer dicht is.
        if not _drawer_open:
            st.markdown(
                f'<style>'
                f'.hesty-conviction-grid {{ display:grid; max-width:760px; '
                f'grid-template-columns:repeat(3, 1fr); gap:1rem; margin-bottom:0.75rem; }} '
                f'.hesty-conviction-tile {{ border-radius:14px; padding:1rem; text-align:left; }} '
                f'.hesty-conviction-tile-label {{ color:#8992A3; font-size:0.7rem; font-weight:700; '
                f'text-transform:uppercase; letter-spacing:0.05em; }} '
                f'.hesty-conviction-tile-value {{ color:#F1F5F9; font-size:1.6rem; font-weight:800; margin-top:6px; }} '
                f'.hesty-conviction-tile-suffix {{ font-size:0.7rem; font-weight:600; color:#64748B; text-transform:uppercase; }} '
                f'.hesty-conviction-tile-warn {{ color:#D97706; font-size:0.68rem; font-weight:700; margin-top:6px; '
                f'text-transform:uppercase; letter-spacing:0.03em; }} '
                # Mobiel: de 3 tegels blijven NAAST elkaar staan (geen volle
                # stapeling meer) maar worden supercompacte mini-balkjes --
                # veel minder padding, kleinere tekst, geen 'of portfolio'-
                # bijschrift (dat kost verhoudingsgewijs de meeste ruimte).
                f'@media (max-width:768px) {{ '
                f'.hesty-conviction-grid {{ grid-template-columns:repeat(3, 1fr) !important; gap:0.4rem !important; }} '
                # min-width:0 is de sleutel: grid-/flex-items hebben
                # standaard min-width:auto, wat betekent dat lange tekst
                # (zoals het label) ze NOOIT kleiner dan hun eigen inhoud
                # laat worden -- ondanks white-space:nowrap + ellipsis. Dat
                # duwde de tegel breder dan z'n toegewezen 1fr-aandeel, en
                # daarmee de hele pagina breder dan het scherm (de horizontale
                # scrollbar). min-width:0 laat 'm wel degelijk krimpen.
                f'.hesty-conviction-tile {{ padding:0.5rem !important; border-radius:10px !important; min-width:0 !important; overflow:hidden !important; }} '
                f'.hesty-conviction-tile-label {{ font-size:0.55rem !important; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }} '
                f'.hesty-conviction-tile-value {{ font-size:1.05rem !important; margin-top:2px !important; }} '
                f'.hesty-conviction-tile-suffix {{ display:none !important; }} '
                f'.hesty-conviction-tile-warn {{ font-size:0.55rem !important; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }} '
                f'}} '
                f'</style>'
                f'<div class="hesty-conviction-grid">{tiles_html}</div>',
                unsafe_allow_html=True,
            )
            if unmapped_weight > 0.5:
                st.markdown(
                    f'<div style="color:#94A3B8; font-size:0.78rem; margin-bottom:2rem;">'
                    f'<span style="color:#D97706; font-weight:700;">\u26A0\uFE0F UNMAPPED ASSETS:</span> '
                    f'{unmapped_weight:.0f}% OF PORTFOLIO HAS NO ACTIVE RESEARCH. RUN A QUICK SCAN TO '
                    f'CATEGORIZE THEM.</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown('<div style="margin-bottom:1.25rem;"></div>', unsafe_allow_html=True)

        # --- 2. Sectie A: Active Portfolio Conviction -- inclusief de
        # unmapped assets, die onderaan instromen (gedempt, met een
        # Quick AI Scan-knop i.p.v. een score). ---
        st.markdown(
            _uniform_section_header_html("Active Portfolio Conviction", "work", is_first=False),
            unsafe_allow_html=True,
        )
        owned_dive_entries = [e for e in deep_dives if e.get("ticker") in held_tickers]
        _render_conviction_table(owned_dive_entries, key_prefix="owned", unmapped=unmapped_assets)
        if not owned_dive_entries and not unmapped_assets:
            st.caption("You don't have any active holdings yet.")

        # --- 3. Sectie B: Research Watchlist ---
        st.markdown(
            _uniform_section_header_html("Research Watchlist", "visibility", is_first=False),
            unsafe_allow_html=True,
        )
        # '+ ADD NEW' -- hier, niet bovenaan de pagina: dit IS de plek
        # waar nieuwe research daadwerkelijk aan toegevoegd wordt.
        # Rechtsboven, dicht tegen deze sectietitel aan getrokken via een
        # negatieve margin-top. Een ECHTE st.button() i.p.v. een kale
        # tekstlink -- die laatste kan niet rechtstreeks naar Python-
        # state schrijven.
        _add_new_key = "analyze_add_new_link"
        st.markdown(
            f'<style>'
            f'.st-key-{_add_new_key} {{ display:flex !important; justify-content:flex-end !important; '
            f'margin-top:-2.5rem !important; margin-bottom:1.25rem !important; }} '
            f'.st-key-{_add_new_key} button {{ '
            f'background:transparent !important; border:none !important; box-shadow:none !important; '
            f'padding:0 !important; font-size:0.72rem !important; font-weight:700 !important; '
            f'letter-spacing:0.05em !important; text-transform:uppercase !important; color:#1FAE96 !important; }} '
            f'.st-key-{_add_new_key} button:hover {{ color:#24C7AB !important; }} '
            f'</style>',
            unsafe_allow_html=True,
        )
        with st.container(key=_add_new_key):
            if st.button("+ Add New", key="analyze_add_new_btn"):
                st.session_state["selected_research"] = "__NEW__"
                st.rerun()
        watchlist_entries = [
            e for e in deep_dives
            if e.get("ticker") not in held_tickers and e.get("conclusion") in ("Watch", "Pass")
        ]
        _render_conviction_table(watchlist_entries, key_prefix="watch")
        if not watchlist_entries:
            st.caption("No research-pipeline ideas yet -- click '+ Add New' above.")

    if _drawer_open:
        with drawer_col:
            _render_analyze_drawer(user_email)



def _demo_watermark_css(container_key: str) -> str:
    """
    Schuine, subtiele 'DEMO MODE'-stempel -- als CSS ::after-pseudo-
    element rechtstreeks op de .st-key-<container_key>-container zelf,
    i.p.v. een los HTML-element via st.markdown(). Dat laatste bleek
    onzichtbaar te blijven, vermoedelijk omdat Streamlit elke
    st.markdown()-aanroep in een eigen, klein element-container wikkelt
    die (met overflow:hidden of vergelijkbaar) het absoluut-gepositio-
    neerde kind kan wegclippen. Een ::after zit direct IN de doos van
    .st-key-<container_key> zelf -- geen aparte, door Streamlit beheerde
    DOM-node waar dat probleem kan optreden. content: attr(data-stamp)
    gebruikt de tekst uit een data-attribuut op diezelfde container
    (hieronder gezet), zodat de tekst niet hardcoded in de CSS zelf
    hoeft te staan.
    """
    return (
        f'<style>'
        # Vorige poging (overflow:hidden verplaatsen naar de buitenste
        # container) loste het NIET op, want de ::after-doos volgt via
        # inset:0 exact dezelfde grenzen als de ouder -- zelfde clip-
        # rand, dus geen verschil. De ECHTE oorzaak: 'font-size:12vw' is
        # relatief aan de VIEWPORT-breedte, niet aan de (veel smallere)
        # kaart-container zelf -- de tekst was daardoor al vóór het
        # draaien breder dan de doos, en justify-content:center knipte
        # 'm dan symmetrisch af aan beide kanten (de D vooraan en de
        # laatste E achteraan precies zo breed als het te veel was).
        # clamp() begrenst de tekst nu hard op een MAXIMALE grootte
        # (5rem) die ruim binnen een normale kaart-breedte past, en
        # schaalt alleen omlaag op kleinere containers -- kan dus nooit
        # meer breder worden dan de doos zelf.
        f'.st-key-{container_key} {{ position:relative !important; overflow:hidden !important; }}'
        f'.st-key-{container_key}::after {{ '
        f'content:"DEMO MODE"; position:absolute; inset:0; display:flex; align-items:center; '
        f'justify-content:center; pointer-events:none; z-index:5; '
        f'font-size:clamp(2.5rem, 9vw, 8rem); font-weight:900; letter-spacing:0.15em; color:#F1F5F9; '
        f'opacity:0.06; text-transform:uppercase; white-space:nowrap; '
        f'transform:translateY(-18%) rotate(-15deg); }}'
        f'</style>'
    )


def _render_portfolio_demo_landing() -> None:
    """
    'Demo Mode' voor de niet-ingelogde My Portfolio-pagina -- i.p.v. een
    geblurde placeholder (nagemaakte data blurren voelde vreemd/nutteloos)
    tonen we nu een volledig scherpe, live-aanvoelende preview met
    duidelijk gelabelde sample-data, gevolgd door een conversie-tegel.
    """
    st.markdown(
        _uniform_section_header_html("My Portfolio", "work", is_first=True),
        unsafe_allow_html=True,
    )
    _demo_wrap_key = "portfolio_demo_wrap"
    st.markdown(_demo_watermark_css(_demo_wrap_key), unsafe_allow_html=True)
    with st.container(key=_demo_wrap_key):
        st.markdown(
            '<div style="color:#64748B; font-size:0.68rem; font-weight:700; letter-spacing:0.08em; '
            'text-transform:uppercase; margin-bottom:1rem; display:flex; align-items:center; gap:0.4rem;">'
            '<span style="width:6px; height:6px; border-radius:50%; background:#F59E0B; display:inline-block;"></span>'
            'Demo mode &middot; sample assets, not your real data</div>',
            unsafe_allow_html=True,
        )

        _demo_positions = [
            {"name": "NVIDIA", "ticker": "NVDA", "value": 18420, "weight": 27.0, "target": 20.0, "change": 2.4},
            {"name": "ASML Holding", "ticker": "ASML", "value": 12980, "weight": 19.0, "target": 20.0, "change": -0.8},
            {"name": "Apple", "ticker": "AAPL", "value": 10750, "weight": 15.8, "target": 15.0, "change": 0.6},
            {"name": "Bitcoin", "ticker": "BTC", "value": 6300, "weight": 9.2, "target": 15.0, "change": -3.1},
            {"name": "Microsoft", "ticker": "MSFT", "value": 9870, "weight": 14.5, "target": 15.0, "change": 1.1},
        ]
        _demo_watch = {"name": "Tesla", "ticker": "TSLA", "change": 4.2}

        # --- Posities-tabel: exact dezelfde compacte, monochrome rij-stijl
        # als de ingelogde pagina (dunne scheidingslijn i.p.v. losse
        # kaartranden, ALL-CAPS namen, teal/rose voor op/neer). ---
        _rows_html = "".join(
            f'<div style="display:flex; align-items:center; justify-content:space-between; '
            f'padding:0.75rem 0.25rem; border-bottom:1px solid rgba(148,163,184,0.08);">'
            f'<div style="min-width:0;">'
            f'<div style="color:#EAEDF1; font-weight:600; font-size:0.85rem; text-transform:uppercase; '
            f'letter-spacing:0.01em;">{p["name"]}</div>'
            f'<div style="color:#64748B; font-size:0.72rem; margin-top:1px;">{p["ticker"]} &middot; {p["weight"]:.1f}% of portfolio</div>'
            f'</div>'
            f'<div style="text-align:right; flex-shrink:0;">'
            f'<div style="color:#F1F5F9; font-weight:700; font-size:0.85rem;">&euro;{p["value"]:,.0f}</div>'
            f'<div style="color:{"#34D399" if p["change"] >= 0 else "#F87171"}; font-size:0.72rem; font-weight:600; margin-top:1px;">'
            f'{p["change"]:+.1f}% today</div>'
            f'</div>'
            f'</div>'
            for p in _demo_positions
        )
        st.markdown(
            f'<div style="background:rgba(2,6,23,0.4); border:1px solid rgba(15,23,42,0.6); '
            f'border-radius:14px; padding:0.5rem 1rem; margin-bottom:1rem;">{_rows_html}</div>',
            unsafe_allow_html=True,
        )

        # --- Watchlist: single-line, zelfde stijl als de ingelogde pagina. ---
        st.markdown(
            f'<div style="background:rgba(2,6,23,0.4); border:1px solid rgba(15,23,42,0.6); '
            f'border-radius:14px; padding:0.6rem 1rem; margin-bottom:2rem; display:flex; align-items:center; '
            f'justify-content:space-between;">'
            f'<div style="color:#94A3B8; font-size:0.75rem; font-weight:600; text-transform:uppercase; '
            f'letter-spacing:0.02em;">&#128065; Watching: {_demo_watch["name"]} <span style="color:#64748B; '
            f'font-weight:400; text-transform:none;">({_demo_watch["ticker"]})</span></div>'
            f'<div style="color:{"#34D399" if _demo_watch["change"] >= 0 else "#F87171"}; font-size:0.8rem; '
            f'font-weight:700;">{_demo_watch["change"]:+.1f}%</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # --- Rebalancing-grid: zelfde 2-koloms kaartenstijl als de ingelogde
        # pagina, nu met de sample-data die daadwerkelijk uit het lood
        # hangen -- dit IS de functionele bewijslast. ---
        st.markdown(
            _uniform_section_header_html("Rebalancing", "swap_horiz", is_first=False),
            unsafe_allow_html=True,
        )
        _rebalance_cards = []
        for p in _demo_positions:
            _diff = p["weight"] - p["target"]
            if abs(_diff) < 3:
                continue
            _action = "SELL" if _diff > 0 else "BUY"
            _action_color = "#F87171" if _diff > 0 else "#34D399"
            _rebalance_cards.append(
                f'<div style="background:rgba(15,23,42,0.3); border:1px solid rgba(30,41,59,0.4); '
                f'border-radius:10px; padding:0.6rem 0.9rem;">'
                f'<div style="display:flex; align-items:center; justify-content:space-between;">'
                f'<div style="color:#EAEDF1; font-weight:600; font-size:0.8rem; text-transform:uppercase;">'
                f'{p["ticker"]}</div>'
                f'<div style="color:{_action_color}; font-weight:700; font-size:0.8rem;">{_action} REQUIRED</div>'
                f'</div>'
                f'<div style="color:#64748B; font-size:0.68rem; margin-top:0.2rem;">'
                f'Target {p["target"]:.0f}% &nbsp;|&nbsp; Current {p["weight"]:.0f}%</div>'
                f'</div>'
            )
        st.markdown(
            '<style>.hesty-demo-rebalance-grid { display:grid; grid-template-columns:repeat(2, 1fr); '
            'gap:0.5rem; } @media (max-width:768px) { .hesty-demo-rebalance-grid { grid-template-columns:1fr; } }</style>'
            f'<div class="hesty-demo-rebalance-grid">{"".join(_rebalance_cards)}</div>',
            unsafe_allow_html=True,
        )

        # --- Conversie-tegel: zelfde opbouw als de andere niet-ingelogde
        # landingspagina's (_render_landing_soft_lock), maar los opgebouwd
        # omdat de content BOVEN de tegel hier scherpe demo-data is i.p.v.
        # een geblurde preview. ---
        _demo_cta_key = "portfolio_demo_cta_tile"
        st.markdown(
            f'<style>'
            f'.st-key-{_demo_cta_key} {{ '
            f'background:rgba(15,23,42,0.3) !important; border:1px solid rgba(30,41,59,0.4) !important; '
            f'border-radius:14px !important; padding:1.5rem !important; width:100% !important; '
            f'box-sizing:border-box !important; display:flex !important; flex-direction:column !important; '
            f'align-items:center !important; justify-content:center !important; text-align:center !important; '
            f'margin-top:2rem !important; }} '
            # Streamlit nest de content van st.container(key=...) in een
            # EIGEN, binnenste stVerticalBlock -- die erft flex NIET
            # automatisch over van de buitenste .st-key-div, vandaar hier
            # expliciet nogmaals dezelfde flex-column-opmaak afgedwongen.
            # Dit was de daadwerkelijke oorzaak van tekst+knop die los onder
            # elkaar bleven staan i.p.v. als 1 samenhangende, gecentreerde
            # tegel.
            f'.st-key-{_demo_cta_key} > div {{ '
            f'display:flex !important; flex-direction:column !important; align-items:center !important; '
            f'justify-content:center !important; text-align:center !important; width:100% !important; }} '
            f'@media (min-width:768px) {{ .st-key-{_demo_cta_key} {{ padding:2rem !important; }} }} '
            f'.hesty-demo-cta-text {{ '
            f'max-width:32rem; color:#CBD5E1; font-weight:600; letter-spacing:0.04em; '
            f'text-transform:uppercase; line-height:1.6; font-size:0.78rem; }} '
            f'@media (min-width:768px) {{ .hesty-demo-cta-text {{ font-size:0.85rem !important; }} }} '
            f'.st-key-{_demo_cta_key} [data-testid="stButton"] {{ margin-top:1rem !important; width:auto !important; }} '
            f'@media (min-width:768px) {{ '
            f'.st-key-{_demo_cta_key} [data-testid="stButton"] {{ margin-top:1.25rem !important; }} '
            f'}} '
            f'.st-key-{_demo_cta_key} button {{ '
            f'background:rgba(2,6,23,0.8) !important; backdrop-filter:blur(6px) !important; '
            f'-webkit-backdrop-filter:blur(6px) !important; color:#EAEDF1 !important; font-weight:700 !important; '
            f'text-transform:uppercase !important; letter-spacing:0.04em !important; font-size:0.85rem !important; '
            f'border:1px solid rgba(148,163,184,0.35) !important; border-radius:8px !important; '
            f'padding:0.6rem 1.5rem !important; width:auto !important; white-space:nowrap !important; '
            f'box-shadow:0 8px 24px rgba(0,0,0,0.45) !important; }} '
            f'.st-key-{_demo_cta_key} button:hover {{ border-color:rgba(31,174,150,0.6) !important; '
            f'color:#1FAE96 !important; }} '
            f'@media (max-width:480px) {{ '
            f'.st-key-{_demo_cta_key} button {{ white-space:normal !important; font-size:0.78rem !important; '
            f'padding:0.55rem 1.1rem !important; line-height:1.35 !important; }} '
            f'}} '
            f'</style>',
            unsafe_allow_html=True,
        )
        with st.container(key=_demo_cta_key):
            st.markdown(
                '<div class="hesty-demo-cta-text">&#128161; YOU ARE CURRENTLY VIEWING HESTYS IN DEMO MODE '
                'WITH SAMPLE ASSETS. READY TO MASTER YOUR OWN CAPITAL? SECURELY CONNECT YOUR PORTFOLIO OR '
                'INPUT YOUR REAL POSITIONS TO ACTIVATE YOUR LIVE COCKPIT.</div>',
                unsafe_allow_html=True,
            )
            if st.button("Connect to Activate My Portfolio \u2192", key="portfolio_demo_cta_btn"):
                st.session_state["login_prefill_mode"] = "Sign Up"
                st.switch_page(login_page)


def render_portfolio():
    if not current_user.is_logged_in:
        _render_portfolio_demo_landing()
        st.stop()

    import database
    from portfolio_watch import check_holding

    user_email = current_user.email

    holdings = filter_active_holdings(database.get_user_holdings(user_email))
    holdings.sort(key=lambda h: h.get("position_value") or 0, reverse=True)
    is_premium = database.is_premium_user(user_email)

    # Achtergrond-gesynchroniseerde marktdata (elke 15 min ververst) --
    # zie render_today() voor de volledige toelichting op deze
    # architectuur. Hier gebruikt voor de koers/dagrendement-weergave in
    # de Daily-modus.
    market_data = database.get_market_data_for_tickers([h["ticker"] for h in holdings])

    # Totaal dagrendement (bedrag + %) over de HELE portfolio -- vooraf
    # berekend zodat dit meteen bovenaan getoond kan worden, naast Total
    # portfolio value. Zelfde logica als de per-positie-berekening
    # verderop, maar gesommeerd: voor elke holding de dag-verandering in
    # waarde optellen, dan het percentage afleiden uit totaal-nu vs.
    # totaal-gisteren (i.p.v. losse percentages simpelweg optellen, wat
    # scheef zou trekken bij ongelijke positiegroottes).
    total_day_change_value = 0.0
    total_day_change_known = False
    for h in holdings:
        h_pos_value = h.get("position_value")
        h_day_change_pct = market_data.get(h["ticker"], {}).get("day_change_pct")
        if h_pos_value and h_day_change_pct is not None and (1 + h_day_change_pct / 100) != 0:
            h_prev_value = h_pos_value / (1 + h_day_change_pct / 100)
            total_day_change_value += h_pos_value - h_prev_value
            total_day_change_known = True
    total_prev_value = sum(h.get("position_value") or 0 for h in holdings) - total_day_change_value
    total_day_change_pct = (
        (total_day_change_value / total_prev_value * 100) if total_prev_value else None
    ) if total_day_change_known else None

    if not holdings:
        st.info("You haven't added any positions yet -- add your first one under 'Manage' below.")

    # ============================================================
    # 1. OVERVIEW -- totaal, valuta, pie chart, en de tabel, samen in 1 vak
    # ============================================================
    if holdings:
        st.markdown(
            _uniform_section_header_html("Portfolio", "account_balance_wallet", is_first=True),
            unsafe_allow_html=True,
        )
        # --- Header: totale portfoliowaarde + toggles -- GEEN omlijnd
        # kader meer (borderloze stijl, net als Today), 2 kolommen over de
        # volle breedte (Streamlit's st.columns() stapelt dit al vanzelf op
        # mobiel, geen extra CSS nodig). De positietabel verderop krijgt
        # nog WEL een eigen st.container(border=True) -- die blijft
        # voorlopig ongewijzigd, dat is de volgende restyling-stap. ---
        total_value = sum(h.get("position_value") or 0 for h in holdings)
        stored_currency = next((h.get("value_currency") for h in holdings if h.get("value_currency")), None)
        cash_value_eur = database.get_cash_value(user_email)  # altijd opgeslagen in EUR

        overview_col1, overview_col2 = st.columns([2, 1])
        with overview_col2:
            # Privacy-indicator verhuisd van een grote, groen-omrande pil
            # linksboven naar een cleane, gedempte tekstregel hier -- direct
            # boven de valuta/Update-controls waar 'ie hoort, zonder de
            # linkerkant (het portfoliobedrag) te storen.
            st.markdown(
                '<div style="font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em; '
                'color:#64748B; font-weight:500; font-family:\'Inter\', sans-serif !important; '
                'text-align:right; margin-bottom:0.3rem;">&#128274; Private data</div>',
                unsafe_allow_html=True,
            )
            display_currency = st.selectbox(
                "Display currency", ["EUR", "USD"], key="display_currency",
                label_visibility="collapsed", help="Display currency",
            )

        if total_value > 0 and stored_currency != display_currency:
            st.warning(f"Values currently shown are in {stored_currency}, not {display_currency}. Click 'Update portfolio value' to convert.")

        with overview_col1:
            if total_value > 0:
                shown_currency = display_currency if stored_currency == display_currency else stored_currency
                shown_symbol = "€" if shown_currency == "EUR" else "$"
                label_suffix = "" if stored_currency == display_currency else f" ({stored_currency})"

                # Cash stond vast in EUR getoond, ook als de weergave-
                # valuta USD was -- omrekenen naar dezelfde valuta als
                # Total portfolio value hierboven, consistent met hoe
                # de posities zelf ook omgerekend worden.
                if shown_currency == "EUR":
                    cash_display_value, cash_symbol = cash_value_eur, "€"
                else:
                    eur_to_shown_rate = get_fx_rate("EUR", shown_currency)
                    if eur_to_shown_rate:
                        cash_display_value, cash_symbol = cash_value_eur * eur_to_shown_rate, shown_symbol
                    else:
                        # FX-conversie mislukt (zeldzaam) -- toon liever
                        # het correcte EUR-bedrag dan een fout $-bedrag.
                        cash_display_value, cash_symbol = cash_value_eur, "€"

                # Dagrendement nu in de gedempte emerald/rose-tint (zelfde
                # TODAY_POSITIVE_TEXT/TODAY_NEGATIVE_TEXT als Today) i.p.v.
                # het felle neon-rood/groen, en zonder de zware pil-
                # achtergrond -- gewoon platte, bold gekleurde tekst.
                total_day_change_html = ""
                if total_day_change_pct is not None:
                    change_color = TODAY_POSITIVE_TEXT if total_day_change_pct >= 0 else TODAY_NEGATIVE_TEXT
                    change_arrow = "&#9650;" if total_day_change_pct >= 0 else "&#9660;"
                    change_sign = "+" if total_day_change_pct >= 0 else "-"
                    total_day_change_html = (
                        f'<div style="margin-top:8px; font-size:1rem; font-weight:700; color:{change_color}; '
                        f'font-family:\'Inter\', sans-serif !important; font-variant-numeric: tabular-nums;">'
                        f'{change_sign}{shown_symbol}{abs(total_day_change_value):,.0f} '
                        f'{total_day_change_pct:+.1f}% {change_arrow}</div>'
                    )
                label_suffix_html = f'<span style="font-size:0.9rem; color:#8992A3; font-weight:400;"> {label_suffix.strip()}</span>' if label_suffix else ""
                st.markdown(
                    f'<div style="display:flex; align-items:baseline; gap:0.9rem; flex-wrap:wrap;">'
                    f'<div style="font-size:2.75rem; font-weight:800; color:#EAEDF1; font-family:\'Inter\', sans-serif !important; '
                    f'font-variant-numeric: tabular-nums; line-height:1.1;">{shown_symbol}{total_value:,.0f}{label_suffix_html}</div>'
                    f'<div style="font-size:0.9rem; color:#94A3B8; font-weight:500; '
                    f'font-family:\'Inter\', sans-serif !important; white-space:nowrap;">'
                    f'Cash: {cash_symbol}{cash_display_value:,.0f}</div>'
                    f'</div>'
                    f'{total_day_change_html}',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Click 'Update portfolio value' to fetch current prices.")

        with overview_col2:
            # Toggle + Update-knop rechts uitgelijnd, in de minimalistische
            # stijl van de rest van de site: het toggle verliest z'n zware
            # rand (transparant, alleen de actieve optie krijgt een zachte
            # teal-achtergrond), en de Update-knop krijgt exact dezelfde
            # subtiele teal-outline-stijl + padding als Today's refresh-knop.
            st.markdown("<div style='height: 0.3rem'></div>", unsafe_allow_html=True)
            _pf_toggle_key = "portfolio_view_mode_toggle_wrap"
            _pf_update_key = "portfolio_update_btn_wrap"
            st.markdown(
                f'<style>'
                f'.st-key-{_pf_toggle_key} div[data-testid="stSegmentedControl"] button {{ '
                f'border:none !important; background:transparent !important; color:#8992A3 !important; '
                f'font-weight:600 !important; font-size:0.82rem !important; }} '
                f'.st-key-{_pf_toggle_key} div[data-testid="stSegmentedControl"] button[aria-pressed="true"] {{ '
                f'background:rgba(31,174,150,0.15) !important; color:#1FAE96 !important; }} '
                f'.st-key-{_pf_update_key} button {{ '
                f'background:transparent !important; border:1px solid rgba(31,174,150,0.35) !important; '
                f'color:#1FAE96 !important; font-weight:600 !important; padding:0.3rem 0.9rem !important; '
                f'border-radius:6px !important; }} '
                f'.st-key-{_pf_update_key} button:hover {{ background:rgba(31,174,150,0.12) !important; }} '
                f'</style>',
                unsafe_allow_html=True,
            )
            toggle_col, button_col = st.columns([1, 1.1])
            with toggle_col:
                with st.container(key=_pf_toggle_key):
                    portfolio_view_mode = st.segmented_control(
                        "View", options=["Daily", "All-time"], default="Daily",
                        key="portfolio_view_mode", label_visibility="collapsed",
                    )
                if portfolio_view_mode is None:
                    portfolio_view_mode = "Daily"
            with button_col:
                with st.container(key=_pf_update_key):
                    if st.button("Update", width="stretch", icon=":material/refresh:", help="Update portfolio value"):
                        with st.spinner("Fetching current prices and exchange rates..."):
                            success, message = refresh_portfolio_values(holdings, user_email, display_currency)
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.warning(message)

        # --- Positietabel: geen dikke omlijning meer, maar WEL een hele
        # zachte, egale achtergrond (bg-slate-950/40) + royale padding --
        # zodat de tabel een duidelijk, rustig 'eiland' vormt t.o.v. de
        # Rebalancing-sectie eronder. GEEN eigen 'Positions'-kop meer --
        # de groene 'Portfolio'-kop bovenaan (met de lijn eronder) is de
        # officiele start van deze sectie, de tabel begint er direct onder.
        _pf_table_card_key = "portfolio_table_card"
        st.markdown(
            f'<style>.st-key-{_pf_table_card_key} {{ background:rgba(2,6,23,0.4) !important; '
            f'border-radius:14px !important; padding:1.25rem 1.5rem !important; }} </style>',
            unsafe_allow_html=True,
        )
        with st.container(key=_pf_table_card_key):

            def _format_value(holding):
                value = holding.get("position_value")
                sym = "€" if holding.get("value_currency") == "EUR" else "$"
                return f"{sym}{value:,.0f}" if value else "-"

            def _format_price(holding):
                """Huidige prijs per aandeel/eenheid -- afgeleid uit de al-opgeslagen
                positiewaarde (waarde / aantal), dus geen extra live-aanroep nodig en
                consistent met het laatste 'Update portfolio value'-moment."""
                value = holding.get("position_value")
                shares = holding.get("shares")
                if not value or not shares:
                    return "-"
                sym = "€" if holding.get("value_currency") == "EUR" else "$"
                return f"{sym}{value / shares:,.2f}"

            def _pct_of_portfolio(holding):
                if total_value <= 0:
                    return 0.0
                value = holding.get("position_value") or 0
                return value / total_value * 100

            position_rows_data = []
            for h in holdings:
                market_row = market_data.get(h["ticker"], {})
                current_price_num = market_row.get("current_price")
                shares = h.get("shares")
                pos_value = h.get("position_value")
                if current_price_num is None and shares and pos_value:
                    # Terugval: ticker nog niet gesynchroniseerd -- de
                    # laatst-opgeslagen (mogelijk wat oudere) waarde uit de
                    # database, i.p.v. helemaal geen koers te tonen.
                    current_price_num = pos_value / shares

                # GEVONDEN BUG (Daily-modus): de 'Price'-kolom in Daily-modus
                # gebruikte current_price_num (native ticker-valuta, bv.
                # altijd EUR voor ADYEN.AS) RECHTSTREEKS, met het symbool
                # gebaseerd op value_currency (bv. USD als de gebruiker USD
                # als weergave koos) -- ZONDER ooit om te rekenen. Resultaat:
                # het getoonde GETAL bleef de EUR-prijs, alleen het SYMBOOL
                # werd (fout) $ -- exact wat er gemeld werd voor ADYEN. Dit
                # was eerder al gefixt voor All-time (all_time_display_price)
                # maar niet voor Daily -- nu ook hier consistent gemaakt.
                # current_price_num zelf blijft ONGEWIJZIGD (native), want de
                # All-time-berekening verderop heeft de ONgeconverteerde
                # waarde nodig als basis voor compute_holding_performance.
                #
                # Hier BEWUST nog get_cached_ticker_currency (de goedkope,
                # ticker-achtervoegsel-gok) i.p.v. de transactie-afgeleide
                # valuta -- die laatste vereist een extra database-aanroep
                # PER HOLDING, wat de Daily-pagina (de standaard, meest
                # gebruikte weergave) merkbaar zou vertragen bij een grote
                # portfolio. All-time-modus (verderop) haalt de transacties
                # sowieso al op voor de berekening zelf, dus daar gebruiken
                # we WEL de precieze, transactie-afgeleide valuta.
                current_price_display = current_price_num
                if current_price_num is not None:
                    display_native_currency = _native_currency_for_holding(h)
                    display_row_currency = h.get("value_currency")
                    if display_native_currency and display_row_currency and display_native_currency != display_row_currency:
                        display_fx_rate = get_fx_rate(display_native_currency, display_row_currency)
                        if display_fx_rate:
                            current_price_display = current_price_num * display_fx_rate

                # Dagrendement komt nu uit market_data (de achtergrond-
                # gesynchroniseerde tabel, elke 15 min ververst) i.p.v. een
                # LIVE yfinance-aanroep tijdens het laden van de pagina --
                # dit is de kern van de snelheid-fix. Valt netjes terug op
                # een live aanroep voor een ticker die nog niet
                # gesynchroniseerd is (net toegevoegd, of de eerste sync-
                # run moet nog draaien).
                day_change_value = None
                day_change_pct = None
                if portfolio_view_mode == "Daily":
                    if h["ticker"] in market_data:
                        day_change_pct = market_row.get("day_change_pct")
                    else:
                        info = get_cached_ticker_info(h["ticker"])
                        fresh_price = info.get("regularMarketPrice")
                        prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
                        if fresh_price is not None and prev_close:
                            day_change_pct = (fresh_price - prev_close) / prev_close * 100
                        else:
                            # Terugval binnen de terugval: .info leeg (bekende
                            # yfinance-onbetrouwbaarheid) -- geschiedenis-
                            # gebaseerde aanpak.
                            hist = get_cached_ticker_history(h["ticker"], period="5d")
                            day_change_pct = compute_day_change_pct(hist)
                    if day_change_pct is not None and pos_value is not None and (1 + day_change_pct / 100) != 0:
                        prev_value = pos_value / (1 + day_change_pct / 100)
                        day_change_value = pos_value - prev_value

                avg_cost = None
                all_time_pct = None
                all_time_pnl = None
                all_time_display_price = current_price_display
                if portfolio_view_mode == "All-time":
                    tx = database.get_transactions_for_holding(user_email, h["id"])
                    # BELANGRIJK, gecorrigeerd inzicht: het conversie-DOELWIT
                    # moet de valuta van de LIVE MARKTPRIJS zijn (current_
                    # price_num, uit market_data) -- get_cached_ticker_currency
                    # geeft die correct (bevestigd: matcht wat Daily-modus al
                    # goed toont). De transactie's EIGEN valuta (nu correct
                    # dankzij de CSV-fix, kan legitiem AFWIJKEN van de markt-
                    # notering -- bv. USA.TO: marktprijs in CAD (Toronto-
                    # notering), maar DEGIRO voerde de koop uit in USD) wordt
                    # binnen _convert_transactions_to_currency zelf gebruikt
                    # om ELKE transactie correct naar dit doelwit om te
                    # rekenen -- ongeacht in welke valuta ze oorspronkelijk
                    # stonden.
                    native_currency = _native_currency_for_holding(h)
                    # Elke transactie kan z'n EIGEN valuta hebben (CSV-import
                    # is altijd EUR, handmatige invoer kan elke valuta zijn,
                    # zoals de gebruiker die koos in het formulier) -- eerst
                    # ALLES omrekenen naar de native ticker-valuta (consistent
                    # met current_price_num, ongeconverteerd rechtstreeks uit
                    # market_data), zodat compute_holding_performance appels
                    # met appels vergelijkt, ongeacht hoe elke individuele
                    # transactie ooit is ingevoerd.
                    tx_native = _convert_transactions_to_currency(tx, native_currency) if native_currency else tx
                    perf = compute_holding_performance(tx_native, current_price_num) if tx_native else None
                    if perf:
                        row_currency = h.get("value_currency")
                        if native_currency and row_currency and native_currency != row_currency:
                            fx_rate = get_fx_rate(native_currency, row_currency)
                        else:
                            fx_rate = 1.0
                        if not fx_rate:
                            fx_rate = 1.0  # FX-conversie mislukt -- toon liever de ongeconverteerde waarde dan niks
                        avg_cost = perf["avg_cost_per_share"] * fx_rate if perf["avg_cost_per_share"] is not None else None
                        all_time_pnl = perf["total_pnl"] * fx_rate
                        all_time_pct = perf["total_return_pct"]  # verhouding, valuta-onafhankelijk
                        # De 'huidige prijs' in de avg_cost -> current_price-
                        # pijl moet in DEZELFDE (nu omgerekende) valuta staan
                        # als avg_cost zelf, anders vergelijk je appels met
                        # peren in de weergave.
                        if current_price_num is not None:
                            all_time_display_price = current_price_num * fx_rate

                position_rows_data.append({
                    "pct": _pct_of_portfolio(h),
                    "html": _position_row_html(
                        h["ticker"], h["naam"], _format_value(h), _pct_of_portfolio(h),
                        portfolio_view_mode,
                        currency_symbol="€" if h.get("value_currency") == "EUR" else "$",
                        logo_url=(
                            custom_asset_logo_data_uri() if h.get("custom_annual_cashflow") is not None
                            else get_company_logo_url(h["ticker"], h.get("naam"))
                        ),
                        day_change_pct=day_change_pct, day_change_value=day_change_value,
                        current_price=all_time_display_price, avg_cost=avg_cost,
                        all_time_pct=all_time_pct, all_time_pnl=all_time_pnl,
                        shares=shares,
                    ),
                })
            position_rows_data.sort(key=lambda r: r["pct"], reverse=True)
            if portfolio_view_mode == "Daily":
                st.markdown(
                    '<div class="portfolio-row-header">'
                    '<div></div><div>Position</div><div>Price</div><div>Change</div><div>Value</div><div>Allocation</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:  # "All-time"
                st.markdown(
                    '<div class="portfolio-row-header-alltime">'
                    '<div></div><div>Position</div>'
                    '<div title="Average price you paid per share, including transaction fees">Cost price &#9432;</div>'
                    '<div>Current price</div><div>Change</div><div>Value</div><div>Allocation</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                "".join(r["html"] for r in position_rows_data),
                unsafe_allow_html=True,
            )

            # --- Positie-detail: transacties + rendement + mini-koersgrafiek ---
            position_options = {f"{h['naam']} ({h['ticker']})": h for h in holdings}
            # Minimalistische dropdown-stijl (dunne slate-rand, geen
            # glimmend/gevuld standaard-Streamlit-uiterlijk) -- zelfde
            # gedempte designtaal als de rest van de tabel hierboven.
            _pf_select_key = "portfolio_position_detail_select_wrap"
            st.markdown(
                f'<style>'
                f'.st-key-{_pf_select_key} div[data-baseweb="select"] > div {{ '
                f'background:transparent !important; border:1px solid rgba(148,163,184,0.18) !important; '
                f'box-shadow:none !important; border-radius:6px !important; }} '
                f'</style>',
                unsafe_allow_html=True,
            )
            with st.container(key=_pf_select_key):
                selected_position_label = st.selectbox(
                    "View position details", ["-- Select a position --"] + list(position_options.keys()),
                    key="portfolio_position_detail_select",
                )
            if selected_position_label != "-- Select a position --":
                selected_holding = position_options[selected_position_label]
                title_col, target_col, target_save_col = st.columns([3, 1.3, 1])
                with title_col:
                    # Titel krachtig in ALL-CAPS, zelfde conventie als de
                    # rest van de site (Today's asset-namen, portfolio-
                    # tabel-tickers) i.p.v. platte st.markdown()-bold.
                    st.markdown(
                        f'<div style="font-size:1.1rem; font-weight:800; color:#EAEDF1; '
                        f'text-transform:uppercase; letter-spacing:0.02em; '
                        f'font-family:\'Inter\', sans-serif !important;">'
                        f'{selected_holding["naam"].upper()} ({selected_holding["ticker"]})</div>',
                        unsafe_allow_html=True,
                    )
                with target_col:
                    _target_input_key = f"detail_target_weight_wrap_{selected_holding['id']}"
                    st.markdown(
                        f'<style>.st-key-{_target_input_key} div[data-baseweb="input"] {{ '
                        f'background:transparent !important; border:1px solid rgba(148,163,184,0.18) !important; '
                        f'box-shadow:none !important; }} '
                        f'</style>',
                        unsafe_allow_html=True,
                    )
                    with st.container(key=_target_input_key):
                        detail_new_target = st.number_input(
                            "Target weight %", min_value=0.0, max_value=100.0, step=0.5,
                            value=float(selected_holding.get("target_weight") or 0.0),
                            key=f"detail_target_weight_{selected_holding['id']}",
                            help="The % of your portfolio you want this position to make up",
                        )
                with target_save_col:
                    st.markdown("<div style='height: 1.8rem'></div>", unsafe_allow_html=True)
                    _save_target_key = f"detail_save_target_wrap_{selected_holding['id']}"
                    st.markdown(
                        f'<style>.st-key-{_save_target_key} button {{ '
                        f'background:transparent !important; border:1px solid rgba(31,174,150,0.35) !important; '
                        f'color:#1FAE96 !important; font-weight:600 !important; padding:0.3rem 0.9rem !important; '
                        f'border-radius:6px !important; }} '
                        f'.st-key-{_save_target_key} button:hover {{ background:rgba(31,174,150,0.12) !important; }} '
                        f'</style>',
                        unsafe_allow_html=True,
                    )
                    with st.container(key=_save_target_key):
                        if st.button("Save", key=f"detail_save_target_{selected_holding['id']}"):
                            database.set_target_weight(
                                selected_holding["id"], user_email,
                                detail_new_target if detail_new_target > 0 else None,
                            )
                            st.rerun()

                # --- Staking -- voor posities waarvan een DEEL (in
                # aandelen/coins, niet euro's) los een eigen yield
                # oplevert, bv. 20 van je 50 gehouden SOL gestaked tegen
                # 7% APY. Los van eventuele live markt-dividendyield van
                # de positie zelf, en telt in de Wealth Engine bovenop
                # mee, niet als vervanging.
                _staking_key = f"detail_staking_wrap_{selected_holding['id']}"
                st.markdown(
                    f'<style>.st-key-{_staking_key} div[data-baseweb="input"] {{ '
                    f'background:transparent !important; border:1px solid rgba(148,163,184,0.18) !important; '
                    f'box-shadow:none !important; }} '
                    f'</style>',
                    unsafe_allow_html=True,
                )
                with st.container(key=_staking_key):
                    _staking_col1, _staking_col2, _staking_col3 = st.columns([1.3, 1.3, 1])
                    with _staking_col1:
                        detail_staked_amount = st.number_input(
                            "Staked amount (shares/coins)", min_value=0.0, step=1.0,
                            value=float(selected_holding.get("staked_amount") or 0.0),
                            key=f"detail_staked_amount_{selected_holding['id']}",
                            help="How many shares/coins of this position are staked (not euros).",
                        )
                    with _staking_col2:
                        detail_staking_apy = st.number_input(
                            "Staking APY %", min_value=0.0, max_value=100.0, step=0.5,
                            value=float(selected_holding.get("staking_apy_pct") or 0.0),
                            key=f"detail_staking_apy_{selected_holding['id']}",
                        )
                    with _staking_col3:
                        st.markdown("<div style='height: 1.8rem'></div>", unsafe_allow_html=True)
                        if st.button("Save", key=f"detail_save_staking_{selected_holding['id']}"):
                            database.set_staking_info(
                                selected_holding["id"], user_email,
                                staked_amount=detail_staked_amount if detail_staked_amount > 0 else None,
                                staking_apy_pct=detail_staking_apy if detail_staking_apy > 0 else None,
                            )
                            st.rerun()

                # --- Transacties (links) / prijsgrafiek (rechts) -- geen
                # omlijnde kaders meer, alleen een dunne verticale
                # scheidslijn tussen de 2 kolommen (zelfde rgba-waarde als
                # overal elders op het platform). ---
                _detail_row_key = f"portfolio_detail_row_{selected_holding['id']}"
                st.markdown(
                    f'<style>'
                    f'.st-key-{_detail_row_key} [data-testid="column"]:first-child {{ '
                    f'border-right:1px solid rgba(148,163,184,0.15); padding-right:1.5rem; }} '
                    f'.st-key-{_detail_row_key} [data-testid="column"]:last-child {{ padding-left:1.5rem; }} '
                    f'@media (max-width:768px) {{ '
                    f'.st-key-{_detail_row_key} [data-testid="column"]:first-child {{ '
                    f'border-right:none !important; padding-right:0 !important; '
                    f'border-bottom:1px solid rgba(148,163,184,0.15); padding-bottom:1rem; margin-bottom:1rem; }} '
                    f'.st-key-{_detail_row_key} [data-testid="column"]:last-child {{ padding-left:0 !important; }} '
                    f'}} '
                    f'</style>',
                    unsafe_allow_html=True,
                )
                with st.container(key=_detail_row_key):
                    detail_col1, detail_col2 = st.columns(2, gap="medium")

                    with detail_col1:
                        transactions = database.get_transactions_for_holding(user_email, selected_holding["id"])
                        detail_currency_symbol = "€" if selected_holding.get("value_currency") == "EUR" else "$"
                        if transactions:
                            # Zelfde fix als de overzicht-rijen: elke transactie
                            # kan z'n EIGEN valuta hebben (CSV-import is altijd
                            # EUR, handmatige invoer kan elke valuta zijn) --
                            # eerst omrekenen naar de native ticker-valuta
                            # (consistent met detail_native_price hieronder),
                            # dan pas de berekening doen, en het RESULTAAT
                            # omrekenen voor weergave.
                            detail_market_row = market_data.get(selected_holding["ticker"], {})
                            detail_native_price = detail_market_row.get("current_price")
                            if detail_native_price is None and selected_holding.get("shares"):
                                detail_native_price = (selected_holding.get("position_value") or 0) / selected_holding["shares"]
                            detail_native_currency = _native_currency_for_holding(selected_holding)
                            transactions_native = (
                                _convert_transactions_to_currency(transactions, detail_native_currency)
                                if detail_native_currency else transactions
                            )
                            perf = compute_holding_performance(transactions_native, current_price=detail_native_price)
                            if perf:
                                detail_row_currency = selected_holding.get("value_currency")
                                if detail_native_currency and detail_row_currency and detail_native_currency != detail_row_currency:
                                    detail_fx_rate = get_fx_rate(detail_native_currency, detail_row_currency)
                                else:
                                    detail_fx_rate = 1.0
                                if not detail_fx_rate:
                                    detail_fx_rate = 1.0
                                perf["total_pnl"] = perf["total_pnl"] * detail_fx_rate
                                if perf["avg_cost_per_share"] is not None:
                                    perf["avg_cost_per_share"] = perf["avg_cost_per_share"] * detail_fx_rate
                                # total_return_pct is een verhouding, valuta-onafhankelijk -- geen conversie nodig
                            if perf and perf.get("total_return_pct") is not None:
                                pct = perf["total_return_pct"]
                                return_color = TODAY_POSITIVE_TEXT if pct >= 0 else TODAY_NEGATIVE_TEXT
                                return_icon = "trending_up" if pct >= 0 else "trending_down"
                                st.markdown(
                                    f'<div style="display:flex; align-items:center; gap:0.4rem; margin-bottom:0.2rem;" '
                                    f'title="Total return includes both your current holdings (vs. avg. cost) and any past sells -- '
                                    f'a loss on an earlier sale still counts, even if the current price is above your average cost.">'
                                    f'{_icon_span(return_icon, size_px=18, color=return_color)}'
                                    f'<span style="font-weight:700; color:{return_color};">Total return: {pct:+.1f}%</span>'
                                    f'<span style="color:#8992A3;">({detail_currency_symbol}{perf["total_pnl"]:+,.2f})</span>'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )
                                # Expliciet tonen WANNEER er daadwerkelijk gerealiseerde
                                # winst/verlies meetelt -- dit is precies wat een
                                # 'avg. cost lager dan huidige prijs, toch negatief
                                # totaalrendement'-situatie verklaart, i.p.v. dat de
                                # gebruiker alleen op de tooltip moet vertrouwen.
                                if perf.get("realized_pnl") and abs(perf["realized_pnl"]) >= 0.01:
                                    realized_color = TODAY_POSITIVE_TEXT if perf["realized_pnl"] >= 0 else TODAY_NEGATIVE_TEXT
                                    st.markdown(
                                        f'<div style="font-size:0.78rem; color:#8992A3; margin-bottom:0.5rem;">'
                                        f'Includes <span style="color:{realized_color}; font-weight:600;">'
                                        f'{detail_currency_symbol}{perf["realized_pnl"]:+,.2f}</span> realized from earlier sells'
                                        f'</div>',
                                        unsafe_allow_html=True,
                                    )
                            sorted_transactions = sorted(transactions, key=lambda t: t["transaction_date"], reverse=True)

                            DEFAULT_TRANSACTIONS_SHOWN = 5
                            show_all_transactions = True
                            if len(sorted_transactions) > DEFAULT_TRANSACTIONS_SHOWN:
                                show_all_transactions = st.toggle(
                                    f"Show all {len(sorted_transactions)} transactions",
                                    key=f"show_all_tx_{selected_holding['id']}",
                                    help=f"Most recent {DEFAULT_TRANSACTIONS_SHOWN} shown by default",
                                )
                            else:
                                st.caption("Transactions (most recent first)")

                            transactions_to_show = (
                                sorted_transactions if show_all_transactions
                                else sorted_transactions[:DEFAULT_TRANSACTIONS_SHOWN]
                            )
                            # Nette, interactieve rijen i.p.v. een platte HTML-
                            # string-lijst -- elke rij is nu individueel
                            # deletable (rood kruisje rechts), zelfde patroon
                            # als de tabel onder Log transaction. Dat maakt de
                            # eerdere, aparte 'Show transaction history'-lijst
                            # daar overbodig -- deze IS nu de ene, centrale
                            # plek om transacties te bekijken en te wissen.
                            _tx_hist_table_key = f"portfolio_tx_history_table_{selected_holding['id']}"
                            st.markdown(
                                f'<style>'
                                f'.st-key-{_tx_hist_table_key} [data-testid="stHorizontalBlock"] {{ align-items:center !important; }} '
                                f'.st-key-{_tx_hist_table_key} [data-testid="stColumn"] {{ '
                                f'display:flex !important; flex-direction:column !important; justify-content:center !important; }} '
                                f'.st-key-{_tx_hist_table_key} [data-testid="stColumn"]:last-of-type {{ '
                                f'align-items:flex-end !important; }} '
                                f'.st-key-{_tx_hist_table_key} button {{ '
                                f'background:transparent !important; border:none !important; box-shadow:none !important; '
                                f'color:#64748B !important; padding:0 !important; min-height:unset !important; height:auto !important; }} '
                                f'.st-key-{_tx_hist_table_key} button:hover {{ color:#E5484D !important; }} '
                                f'</style>',
                                unsafe_allow_html=True,
                            )
                            with st.container(key=_tx_hist_table_key):
                                for t in transactions_to_show:
                                    is_buy = t["transaction_type"] == "buy"
                                    type_color = TODAY_POSITIVE_TEXT if is_buy else TODAY_NEGATIVE_TEXT
                                    type_icon = "add_circle" if is_buy else "remove_circle"
                                    type_label = "Buy" if is_buy else "Sell"
                                    # Het symbool per transactie is gebaseerd op DIE
                                    # transactie's eigen, opgeslagen currency (niet
                                    # het algemene detail_currency_symbol) -- een
                                    # transactie kan in een andere valuta zijn
                                    # ingevoerd dan de holding's huidige weergave-
                                    # valuta, en de RUWE prijs hier getoond wordt
                                    # zoals ze daadwerkelijk is ingevoerd (geen
                                    # conversie, gewoon het juiste label).
                                    tx_own_currency = t.get("currency") or "EUR"
                                    tx_own_symbol = "€" if tx_own_currency == "EUR" else ("$" if tx_own_currency == "USD" else tx_own_currency + " ")
                                    pcol1, pcol2, pcol3 = st.columns([2.2, 5, 0.5], gap="small")
                                    with pcol1:
                                        st.markdown(
                                            f'<span style="display:inline-flex; align-items:center; gap:0.4rem; '
                                            f'font-size:0.8rem;">'
                                            f'{_icon_span(type_icon, size_px=14, color=type_color)}'
                                            f'<span style="font-weight:700; color:{type_color}; '
                                            f'font-family:\'Inter\', sans-serif !important;">{type_label}</span></span>',
                                            unsafe_allow_html=True,
                                        )
                                    with pcol2:
                                        st.markdown(
                                            f'<span style="font-size:0.8rem; color:#8992A3; '
                                            f'font-family:\'Inter\', sans-serif !important; '
                                            f'font-variant-numeric: tabular-nums;">'
                                            f'{t["shares"]:g} @ {tx_own_symbol}{t["price"]:,.2f} &middot; {t["transaction_date"]}</span>',
                                            unsafe_allow_html=True,
                                        )
                                    with pcol3:
                                        if st.button("\u2715", key=f"portfolio_delete_tx_{t['id']}", help="Delete this transaction"):
                                            database.delete_transaction(t["id"], user_email)
                                            remaining = [x for x in transactions if x["id"] != t["id"]]
                                            if not remaining:
                                                # Geen transacties meer over voor deze positie -- voorkomt
                                                # een 'verweesde' positie zonder shares en zonder
                                                # geschiedenis.
                                                database.delete_holding(selected_holding["id"], user_email)
                                                st.success("Transaction deleted -- this position had no "
                                                           "other transactions left, so it was removed too.")
                                            else:
                                                sync_holding_shares_from_transactions(selected_holding["id"], user_email)
                                                st.success("Transaction deleted.")
                                            st.rerun()
                                    st.markdown(
                                        '<div style="width:100%; height:1px; background-color:#1E293B; margin:0.15rem 0;"></div>',
                                        unsafe_allow_html=True,
                                    )

                            # Alles-in-1x wissen voor DEZE positie -- verhuisd
                            # hierheen vanaf 'Log transaction' (stond daar
                            # onder een nu-verwijderde, dubbele lijst). Handig
                            # om oude, minder-precieze transacties (bv. van
                            # vóór een CSV-parser-verbetering) op te schonen
                            # vóór een schone herimport, i.p.v. ze 1-voor-1 te
                            # moeten verwijderen. 2-staps-bevestiging
                            # (destructieve actie).
                            st.markdown("<div style='height: 0.5rem'></div>", unsafe_allow_html=True)
                            _delete_all_pos_confirm_key = f"confirm_delete_all_tx_{selected_holding['id']}"
                            if not st.session_state.get(_delete_all_pos_confirm_key, False):
                                if st.button(
                                    "Delete all transactions for this position", icon=":material/delete_sweep:",
                                    key=f"delete_all_tx_btn_{selected_holding['id']}",
                                ):
                                    st.session_state[_delete_all_pos_confirm_key] = True
                                    st.rerun()
                            else:
                                st.warning(
                                    f"This will permanently delete all {len(transactions)} transactions for "
                                    f"{selected_holding['naam']} -- useful if you want to re-import this "
                                    f"position cleanly (e.g. after a CSV-import precision fix). This cannot "
                                    f"be undone."
                                )
                                _pos_confirm_col1, _pos_confirm_col2 = st.columns(2)
                                with _pos_confirm_col1:
                                    if st.button("Yes, delete all", key=f"confirm_delete_all_tx_btn_{selected_holding['id']}", type="primary"):
                                        database.delete_all_transactions_for_holding(selected_holding["id"], user_email)
                                        database.delete_holding(selected_holding["id"], user_email)
                                        st.session_state[_delete_all_pos_confirm_key] = False
                                        st.success(f"All transactions for {selected_holding['naam']} deleted -- "
                                                   f"you can now re-import it cleanly.")
                                        st.rerun()
                                with _pos_confirm_col2:
                                    if st.button("Cancel", key=f"cancel_delete_all_tx_btn_{selected_holding['id']}"):
                                        st.session_state[_delete_all_pos_confirm_key] = False
                                        st.rerun()
                        else:
                            st.caption("No transactions logged for this position yet -- log one under 'Manage' below.")

                    with detail_col2:
                        st.caption("Price -- last 6 months")
                        retry_chart_key = f"retry_chart_{selected_holding['ticker']}"
                        with st.spinner("Loading chart..."):
                            mini_hist = get_cached_ticker_history(selected_holding["ticker"], period="6mo")
                        if mini_hist is not None and not mini_hist.empty:
                            valid_mini_closes = mini_hist["Close"].dropna()
                            if len(valid_mini_closes) >= 2:
                                # De Y-as strak om de DAADWERKELIJKE prijsrange laten
                                # aansluiten (i.p.v. Plotly's standaard, ruimere
                                # marge) -- laat veel meer 'reliëf' in de koers zien,
                                # zodat verschillen tussen prijsniveaus beter opvallen.
                                y_min = float(valid_mini_closes.min())
                                y_max = float(valid_mini_closes.max())
                                y_padding = (y_max - y_min) * 0.05 or y_max * 0.02
                                mini_fig = go.Figure()
                                mini_fig.add_trace(go.Scatter(
                                    x=valid_mini_closes.index.strftime("%Y-%m-%d").tolist(),
                                    y=valid_mini_closes.tolist(),
                                    mode="lines",
                                    line=dict(color="#1FAE96", width=2),
                                    fill="tozeroy",
                                    fillcolor="rgba(31,174,150,0.10)",
                                    hovertemplate="%{x}: %{y:,.2f}<extra></extra>",
                                ))
                                mini_fig.update_layout(
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    plot_bgcolor="rgba(0,0,0,0)",
                                    font=dict(family="Inter, sans-serif", color="#EAEDF1", size=10),
                                    margin=dict(t=10, b=10, l=10, r=10),
                                    height=220,
                                    showlegend=False,
                                    # As-teksten (bv. 'Apr 2026', '110') klein en
                                    # gedempt (text-xs text-slate-500) -- laat de
                                    # koerslijn zelf spreken, de assen zijn puur
                                    # ondersteunend en horen niet te concurreren.
                                    xaxis=dict(gridcolor="rgba(137,146,163,0.15)", tickfont=dict(size=9, color="#64748B")),
                                    yaxis=dict(
                                        gridcolor="rgba(137,146,163,0.15)",
                                        range=[y_min - y_padding, y_max + y_padding],
                                        tickfont=dict(size=9, color="#64748B"),
                                    ),
                                )
                                st.plotly_chart(mini_fig)
                            else:
                                st.caption("Not enough price data to show a chart.")
                        else:
                            # yfinance is een bekend onbetrouwbare databron --
                            # een voorbijgaande netwerkhapering geeft een lege
                            # DataFrame terug, die vervolgens 5 min gecached
                            # blijft (get_cached_ticker_history's ttl). Een
                            # Retry-knop wist die specifieke cache-entry, i.p.v.
                            # dat je 5 minuten moet wachten voor een nieuwe poging.
                            st.caption("No price data available right now -- this can happen with a temporary network hiccup.")
                            if st.button("Retry", key=retry_chart_key, icon=":material/refresh:"):
                                get_cached_ticker_history.clear()
                                st.rerun()

    # ============================================================
    # 2. REBALANCING -- concrete koop/verkoop-suggesties o.b.v. target weights
    # ============================================================
    if holdings:
        rebalance_total_value = sum(h.get("position_value") or 0 for h in holdings)
        rebalance_currency = next((h.get("value_currency") for h in holdings if h.get("value_currency")), None)
        rebalance_symbol = "€" if rebalance_currency == "EUR" else "$"
        rebalance_result = build_rebalancing_suggestions(holdings, rebalance_total_value)

        if rebalance_result["any_targets_set"]:
            st.markdown(
                _uniform_section_header_html("Rebalancing", "swap_horiz", is_first=False),
                unsafe_allow_html=True,
            )
            # --- Rebalancing is nu een 2-koloms grid van losse kaarten
            # (elk met een dunne, subtiele rand) i.p.v. een verticale
            # tabel-achtige lijst -- voelt daardoor als een actiegerichte
            # 'to-do lijst' i.p.v. een datatabel, en maakt in 1 oogopslag
            # duidelijk dat dit een APART blok is t.o.v. de Positions-
            # tabel hierboven. Logica/berekeningen (euro-bedragen, shares,
            # percentages) volledig ongewijzigd. ---
            if rebalance_result["targets_sum_pct"] > 100:
                # Zachte, chique amber-waarschuwing i.p.v. Streamlit's eigen
                # felle st.warning()-balk.
                st.markdown(
                    f'<div style="background:rgba(69,26,3,0.2); border:1px solid rgba(120,53,15,0.35); '
                    f'border-radius:8px; padding:0.7rem 1rem; margin-bottom:0.9rem; display:flex; '
                    f'align-items:flex-start; gap:0.5rem;">'
                    f'{_icon_span("warning", size_px=16, color="#E8A93C")}'
                    f'<span style="color:#E8A93C; font-size:0.85rem; line-height:1.5; '
                    f'font-family:\'Inter\', sans-serif !important;">'
                    f'Your target weights add up to {rebalance_result["targets_sum_pct"]:.0f}% -- '
                    f'more than 100%, so not every target can be fully reached at once. '
                    f'Consider lowering a few targets under \'Manage\'.</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            if rebalance_result["suggestions"]:
                rebalance_cards_html = []
                for sugg in rebalance_result["suggestions"]:
                    action_word = "Buy" if sugg["action"] == "buy" else "Sell"
                    action_color = TODAY_POSITIVE_TEXT if sugg["action"] == "buy" else TODAY_NEGATIVE_TEXT
                    shares_txt = ""
                    if sugg["diff_shares"] is not None:
                        shares_txt = (
                            f' <span style="color:#64748B; font-size:0.68rem; font-weight:400;">&middot; '
                            f'{abs(sugg["diff_shares"]):.2f} shares</span>'
                        )

                    # Lichte, subtiele balk: huidige% als vulling, een
                    # verticale streep op de target%-positie -- geeft in
                    # 1 oogopslag de afstand tot het doel, naast de
                    # tekstuele percentages. Nog compacter (h-0.75, minder
                    # marge erboven) zodat 'ie puur functioneel aanwezig is.
                    bar_current_pct = min(sugg["current_pct"], 100)
                    bar_target_pct = min(sugg["target_pct"], 100)
                    bar_html = (
                        '<div style="position:relative; height:3px; background:rgba(137,146,163,0.10); '
                        'border-radius:2px; margin-top:0.3rem;">'
                        f'<div style="position:absolute; height:100%; width:{bar_current_pct:.1f}%; '
                        f'background:{action_color}; border-radius:2px;"></div>'
                        f'<div style="position:absolute; left:{bar_target_pct:.1f}%; top:-1.5px; height:6px; '
                        'width:2px; background:#EAEDF1; border-radius:1px;"></div>'
                        '</div>'
                    )

                    rebalance_cards_html.append(
                        f'<div style="background:rgba(15,23,42,0.3); border:1px solid rgba(30,41,59,0.4); '
                        f'border-radius:10px; padding:0.45rem 0.85rem; width:100%; max-width:100%; '
                        f'box-sizing:border-box; overflow:hidden;">'
                        # Driedelige flex-rij, ALTIJD horizontaal (nooit
                        # flex-col op mobiel): midden (naam+ticker) MOET
                        # kunnen krimpen (flex:1 + min-width:0 + truncate),
                        # rechts (Buy/Sell-data) blijft hard vast (flex-
                        # shrink:0) en altijd volledig zichtbaar tegen de
                        # rechterrand. Zonder min-width:0 weigert een
                        # flex-item van nature te krimpen onder z'n eigen
                        # inhoud (hier: de volledige, niet-afgebroken naam),
                        # wat de kaart -- en daarmee de hele pagina -- breder
                        # duwde dan het scherm op mobiel.
                        f'<div style="display:flex; flex-direction:row; align-items:center; '
                        f'justify-content:space-between; width:100%; gap:0.6rem;">'
                        f'<div style="flex:1 1 0%; min-width:0; overflow:hidden; white-space:nowrap; '
                        f'text-overflow:ellipsis; '
                        f'color:#EAEDF1; font-size:0.8rem; font-weight:600; text-transform:uppercase; '
                        f'letter-spacing:0.01em; font-family:\'Inter\', sans-serif !important;">'
                        f'{sugg["naam"].upper()} <span style="color:#8992A3; font-weight:400; '
                        f'text-transform:none;">({sugg["ticker"]})</span></div>'
                        f'<div style="display:flex; align-items:baseline; gap:0.3rem; flex-shrink:0; '
                        f'white-space:nowrap; text-align:right;">'
                        f'<span style="color:{action_color}; font-weight:600; font-size:0.8rem; '
                        f'font-family:\'Inter\', sans-serif !important;">{action_word}</span>'
                        f'<span style="color:#F1F5F9; font-weight:700; font-size:0.85rem; '
                        f'font-family:\'Inter\', sans-serif !important;">{rebalance_symbol}{abs(sugg["diff_value"]):,.0f}</span>'
                        f'{shares_txt}'
                        '</div>'
                        '</div>'
                        # Percentages/doel: nog kleiner en gedempter (bijna
                        # text-[10px], slate-500) -- puur ondersteunende info,
                        # samen met de balk de enige 2e regel van de kaart.
                        # white-space:nowrap + overflow:hidden zodat ook deze
                        # regel nooit breder kan worden dan de kaart zelf.
                        f'<div style="color:#64748B; font-size:0.65rem; margin-top:0.15rem; '
                        f'white-space:nowrap; overflow:hidden; text-overflow:ellipsis; '
                        f'font-family:\'Inter\', sans-serif !important;">'
                        f'{sugg["current_pct"]:.1f}% now &#8594; {sugg["target_pct"]:.1f}% target</div>'
                        f'{bar_html}'
                        '</div>'
                    )
                st.markdown(
                    '<style>'
                    '.hesty-rebalance-grid { display:grid; grid-template-columns:repeat(2, 1fr); gap:0.5rem; '
                    'width:100%; max-width:100%; overflow-x:hidden; box-sizing:border-box; } '
                    '@media (max-width:768px) { .hesty-rebalance-grid { grid-template-columns:1fr; } } '
                    '</style>'
                    f'<div class="hesty-rebalance-grid">{"".join(rebalance_cards_html)}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("All positions with a target weight are already close enough to their target -- nothing to rebalance right now.")
        # Geen 'else' hier -- als er nergens een target is ingesteld, blijft
        # deze sectie gewoon volledig ongetoond (geen lege sectie/verwijzing-
        # ruis voor gebruikers die de target-weight-feature niet gebruiken).

    # ============================================================
    # 3. MANAGE
    # ============================================================
    st.markdown(
        _uniform_section_header_html("Manage", "tune", is_first=False),
        unsafe_allow_html=True,
    )
    manage_section_options = [
        ":material/upload_file: Import from broker",
        ":material/receipt_long: Log transaction",
        ":material/visibility: Watchlist",
        ":material/delete_forever: Delete portfolio",
    ]
    _manage_tabs_key = "manage_section_select_wrap"
    # Nog een keer versterkt -- raakt nu ook expliciet de BaseWeb
    # button-group-wrapper (de component die st.segmented_control() onder
    # de motorkap gebruikt) en dwingt border-width apart op 0, voor het
    # geval een eerdere, minder brede selector de daadwerkelijke rand-
    # bron nog niet volledig raakte.
    st.markdown(
        f'<style>'
        f'.st-key-{_manage_tabs_key} div[data-testid="stSegmentedControl"], '
        f'.st-key-{_manage_tabs_key} div[data-baseweb="button-group"] {{ '
        f'border:none !important; border-width:0 !important; background:transparent !important; '
        f'box-shadow:none !important; }} '
        f'.st-key-{_manage_tabs_key} div[data-testid="stSegmentedControl"] button, '
        f'.st-key-{_manage_tabs_key} div[data-testid="stSegmentedControl"] label, '
        f'.st-key-{_manage_tabs_key} div[data-baseweb="button-group"] button {{ '
        f'border:none !important; border-width:0 !important; outline:none !important; box-shadow:none !important; '
        f'background:transparent !important; color:#8992A3 !important; '
        f'font-weight:600 !important; font-size:0.85rem !important; }} '
        f'.st-key-{_manage_tabs_key} div[data-testid="stSegmentedControl"] button[aria-pressed="true"], '
        f'.st-key-{_manage_tabs_key} div[data-testid="stSegmentedControl"] label[data-checked="true"] {{ '
        f'background:rgba(31,174,150,0.15) !important; color:#1FAE96 !important; border:none !important; }} '
        f'</style>',
        unsafe_allow_html=True,
    )
    with st.container(key=_manage_tabs_key):
        manage_section_selected = st.segmented_control(
            "Manage section", options=manage_section_options,
            default=manage_section_options[0], key="manage_section_select", label_visibility="collapsed",
        )
    if manage_section_selected is None:
        manage_section_selected = manage_section_options[0]
    # De iconen-prefix (":material/...: ") eraf strippen zodat de rest van
    # de code hieronder gewoon de bekende, korte namen kan blijven
    # vergelijken -- alleen de WEERGAVE kreeg een icoon, niet de logica.
    manage_section = manage_section_selected.split(": ", 1)[-1]

    if manage_section == "Import from broker":
        # Geen omlijnd kader meer om deze sectie -- content ademt clean op
        # de achtergrond, net als de rest van de vernieuwde pagina.
        with st.container(border=False):
            # --- Import from a broker -- bulk-importeren i.p.v. 1-voor-1 loggen ---
            # Upload is nu de EERSTE, meest prominente actie -- geen
            # badge/uitleg-tekst meer ervoor die de aandacht wegtrekt van
            # de hoofdtaak zelf.
            st.markdown("**Upload your transactions**")
            # Toelichtingstekst nu BOVEN de uploader (tussen kop en widget)
            # i.p.v. eronder -- betere leeshierarchie: eerst uitleggen wat
            # je moet doen, dan pas de widget zelf.
            st.markdown(
                '<div style="font-size:0.75rem; color:#64748B; font-family:\'Inter\', sans-serif !important; '
                'line-height:1.5; max-width:36rem; margin-bottom:1rem;">Export your broker\'s \'Transactions\' '
                'CSV and upload it here to import your full buy/sell history in one go, instead of logging '
                'each one by hand.</div>',
                unsafe_allow_html=True,
            )
            # width='stretch' i.p.v. een vaste 320px -- de uploader vult nu
            # de volle breedte van de linkerkolom, strak doorlopend met de
            # breedte van de sub-navigatie-knoppen erboven. Val terug op de
            # oude, vaste-breedte-aanroep als deze (relatief nieuwe)
            # parameter-waarde niet bestaat in de geïnstalleerde
            # Streamlit-versie.
            try:
                broker_upload = st.file_uploader("Transactions CSV", type=["csv"], key="broker_upload",
                                                  label_visibility="collapsed", width="stretch")
            except (TypeError, ValueError):
                try:
                    broker_upload = st.file_uploader("Transactions CSV", type=["csv"], key="broker_upload",
                                                      label_visibility="collapsed", width=320)
                except TypeError:
                    broker_upload = st.file_uploader("Transactions CSV", type=["csv"], key="broker_upload",
                                                      label_visibility="collapsed")

            # Puur automatische herkenning op basis van de kolomkoppen in
            # de CSV zelf (zie detect_broker_from_csv) -- geen handmatige
            # keuze meer nodig.
            degiro_file = None
            degiro_account_file = None
            robinhood_file = None
            schwab_file = None
            trade_republic_file = None
            if broker_upload is not None:
                detected_broker = detect_broker_from_csv(broker_upload.getvalue())
                _detected_labels = {
                    "degiro": "DEGIRO", "degiro_account": "DEGIRO (Account statement -- dividends)",
                    "robinhood": "Robinhood", "schwab": "Charles Schwab", "trade_republic": "Trade Republic",
                }
                if detected_broker in _detected_labels:
                    st.caption(f"\U0001F50D Detected: {_detected_labels[detected_broker]}")
                if detected_broker == "degiro":
                    degiro_file = broker_upload
                elif detected_broker == "degiro_account":
                    degiro_account_file = broker_upload
                elif detected_broker == "robinhood":
                    robinhood_file = broker_upload
                elif detected_broker == "schwab":
                    schwab_file = broker_upload
                elif detected_broker == "trade_republic":
                    trade_republic_file = broker_upload
                else:
                    st.error(
                        "Couldn't recognize this CSV's format -- make sure it's an unmodified "
                        "'Transactions' export from a supported broker (see the list below)."
                    )

            # Trade Republic hergebruikt de VOLLEDIGE, bestaande DEGIRO-
            # ticker-matching-UI hieronder (zelfde 'grouped per ISIN'-vorm,
            # zie parse_trade_republic_transactions_csv) -- door 'm hier
            # aan degiro_file toe te wijzen (met een apart vlaggetje om te
            # onthouden welke parser daadwerkelijk moet draaien) hoeft die
            # hele, complexe matching-UI verderop geen letter te wijzigen.
            is_trade_republic_import = trade_republic_file is not None
            if is_trade_republic_import:
                degiro_file = trade_republic_file
            _active_broker_parser = (
                parse_trade_republic_transactions_csv if is_trade_republic_import
                else parse_degiro_transactions_csv
            )

            if hasattr(database, "get_last_csv_import"):
                try:
                    last_csv_import = database.get_last_csv_import(user_email)
                except Exception:
                    last_csv_import = None
                if last_csv_import:
                    import_dt = datetime.fromisoformat(last_csv_import["timestamp"])
                    filename_txt = f" ('{last_csv_import['filename']}')" if last_csv_import.get("filename") else ""
                    st.markdown(
                        f'<div style="font-size:0.75rem; color:#64748B; font-family:\'Inter\', sans-serif !important; '
                        f'margin-top:2px;">Last CSV import: {import_dt.strftime("%b %d, %Y at %H:%M")}{filename_txt}</div>',
                        unsafe_allow_html=True,
                    )

            # 'Supported brokers'-lijst i.p.v. een losse badge -- schaalt
            # netjes mee zodra er een 2e/3e broker bijkomt. Favicon via
            # Google's favicon-service (zelfde, al-geplande aanpak als
            # bedrijfslogo's bij deep-dives) i.p.v. een zelf-gehost, echt
            # DEGIRO-merklogo -- vermijdt trademark-issues.
            st.markdown("<div style='height: 0.5rem'></div>", unsafe_allow_html=True)
            st.markdown("**Supported brokers**")
            st.caption(
                "DEGIRO tip: dividends only show up if you upload the **Account statement** "
                "export (Activiteitenoverzicht) -- the regular Transactions export never "
                "contains dividend rows, only buy/sell orders."
            )
            st.markdown(
                '<div style="display:flex; align-items:center; gap:0.5rem; padding:0.3rem 0;">'
                '<img src="https://www.google.com/s2/favicons?domain=degiro.com&sz=32" '
                'style="width:18px; height:18px; border-radius:4px;">'
                '<span style="color:#94A3B8; font-size:0.78rem; font-weight:600; text-transform:uppercase; '
                'letter-spacing:0.04em; font-family:\'Inter\', sans-serif !important;">DEGIRO</span>'
                '</div>'
                '<div style="display:flex; align-items:center; gap:0.5rem; padding:0.3rem 0;">'
                '<img src="https://www.google.com/s2/favicons?domain=robinhood.com&sz=32" '
                'style="width:18px; height:18px; border-radius:4px;">'
                '<span style="color:#94A3B8; font-size:0.78rem; font-weight:600; text-transform:uppercase; '
                'letter-spacing:0.04em; font-family:\'Inter\', sans-serif !important;">Robinhood</span>'
                '</div>'
                '<div style="display:flex; align-items:center; gap:0.5rem; padding:0.3rem 0;">'
                '<img src="https://www.google.com/s2/favicons?domain=schwab.com&sz=32" '
                'style="width:18px; height:18px; border-radius:4px;">'
                '<span style="color:#94A3B8; font-size:0.78rem; font-weight:600; text-transform:uppercase; '
                'letter-spacing:0.04em; font-family:\'Inter\', sans-serif !important;">Charles Schwab</span>'
                '</div>'
                '<div style="display:flex; align-items:center; gap:0.5rem; padding:0.3rem 0;">'
                '<img src="https://www.google.com/s2/favicons?domain=traderepublic.com&sz=32" '
                'style="width:18px; height:18px; border-radius:4px;">'
                '<span style="color:#94A3B8; font-size:0.78rem; font-weight:600; text-transform:uppercase; '
                'letter-spacing:0.04em; font-family:\'Inter\', sans-serif !important;">Trade Republic</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<style>'
                '.hesty-request-broker-link { display:block !important; margin-top:2.5rem !important; '
                'font-size:10px !important; font-weight:700 !important; letter-spacing:0.12em !important; '
                'color:#64748B !important; text-transform:uppercase !important; text-align:left !important; '
                'text-decoration:none !important; transition:color 0.2s ease !important; }'
                '.hesty-request-broker-link:visited { color:#64748B !important; text-decoration:none !important; }'
                '.hesty-request-broker-link:hover, .hesty-request-broker-link:focus, '
                '.hesty-request-broker-link:active { color:#CBD5E1 !important; text-decoration:none !important; }'
                '</style>'
                '<a href="/support" target="_self" class="hesty-request-broker-link">'
                'Request a new broker &rarr;</a>',
                unsafe_allow_html=True,
            )

            already_imported = st.session_state.get("degiro_imported_filenames", set())

            if degiro_file is not None and degiro_file.name in already_imported:
                st.success(f"'{degiro_file.name}' was already imported.", icon=":material/check_circle:")
                if st.button("Process this file again anyway"):
                    already_imported.discard(degiro_file.name)
                    st.session_state["degiro_imported_filenames"] = already_imported
                    st.session_state.pop("degiro_parsed_filename", None)
                    st.rerun()
            elif degiro_file is not None:
                if st.session_state.get("degiro_parsed_filename") != degiro_file.name:
                    # Nieuw bestand -- opnieuw parsen en de matches resetten
                    with st.spinner("Reading your file..."):
                        parse_result = _active_broker_parser(degiro_file.getvalue())
                    st.session_state["degiro_parsed_filename"] = degiro_file.name
                    st.session_state["degiro_grouped"] = parse_result["grouped"]
                    st.session_state["degiro_skipped"] = parse_result["skipped_rows"]
                    # 'dividend_rows' bestaat ALLEEN bij Trade Republic (DEGIRO's
                    # eigen export bevat sowieso geen dividend-rijen -- z'n
                    # parser geeft dan ook geen 'dividend_rows'-sleutel terug,
                    # vandaar .get() met een lege lijst als terugval). Voorheen
                    # werd dit hier zelfs helemaal niet opgevangen -- Trade
                    # Republic-dividenden verdwenen dus spoorloos, zonder zelfs
                    # maar een 'N rows found'-melding.
                    st.session_state["degiro_dividends"] = parse_result.get("dividend_rows", [])
                    ticker_matches = {}
                    ticker_candidates = {}
                    # Herken ISIN's die je AL eerder hebt opgelost (bv. bij een vorige
                    # import) -- geen nieuwe zoekopdracht nodig, geen keuzelijst opnieuw.
                    existing_isin_to_ticker = {
                        h["isin"]: h["ticker"] for h in database.get_user_holdings(user_email) if h.get("isin")
                    }
                    with st.spinner(f"Looking up tickers for {len(parse_result['grouped'])} securities..."):
                        for key, group in parse_result["grouped"].items():
                            remembered_ticker = existing_isin_to_ticker.get(group.get("isin"))
                            if remembered_ticker:
                                ticker_matches[key] = remembered_ticker
                                ticker_candidates[key] = [{
                                    "symbol": remembered_ticker, "name": group["product"], "exchange": "remembered",
                                }]
                            else:
                                candidates = get_ticker_candidates(group["product"], group.get("isin"))
                                ticker_candidates[key] = candidates
                                ticker_matches[key] = candidates[0]["symbol"] if candidates else ""
                    st.session_state["degiro_ticker_matches"] = ticker_matches
                    st.session_state["degiro_ticker_candidates"] = ticker_candidates

                degiro_grouped = st.session_state["degiro_grouped"]
                degiro_skipped = st.session_state["degiro_skipped"]
                degiro_dividends = st.session_state.get("degiro_dividends", [])

                total_tx = sum(len(g["transactions"]) for g in degiro_grouped.values())
                st.success(f"Found {len(degiro_grouped)} securities, {total_tx} transactions.")
                if degiro_dividends:
                    st.caption(
                        f"{len(degiro_dividends)} dividend row(s) found -- will be added to your "
                        f"Dividend history (not as buy/sell transactions)."
                    )
                if degiro_skipped:
                    reasons_preview = "; ".join(reason for _, reason in degiro_skipped[:5])
                    more = "..." if len(degiro_skipped) > 5 else ""
                    st.caption(f"{len(degiro_skipped)} row(s) couldn't be read and were skipped: "
                               f"{reasons_preview}{more}")

                unmatched_keys = [
                    key for key, group in degiro_grouped.items()
                    if not st.session_state["degiro_ticker_matches"].get(key, "").strip()
                ]
                if unmatched_keys:
                    unmatched_lines = "\n".join(
                        f"- **{degiro_grouped[key]['product']}**"
                        + (f" (ISIN: {degiro_grouped[key]['isin']})" if degiro_grouped[key]["isin"] else "")
                        for key in unmatched_keys
                    )
                    st.warning(
                        f"**{len(unmatched_keys)} security/securities need your attention** "
                        f"-- no ticker could be auto-matched. Fill these in manually below, "
                        f"or they'll be skipped:\n\n{unmatched_lines}",
                        icon=":material/warning:",
                    )

                st.markdown("**Review the ticker for each security** (auto-suggested -- please "
                             "double-check and correct if wrong before importing). "
                             "Unmatched ones are shown first:")
                sorted_items = sorted(
                    degiro_grouped.items(),
                    key=lambda kv: st.session_state["degiro_ticker_matches"].get(kv[0], "").strip() != "",
                )
                existing_tickers_set = {h["ticker"] for h in holdings}
                for key, group in sorted_items:
                    current_ticker = st.session_state["degiro_ticker_matches"].get(key, "").strip()
                    is_new_position = current_ticker and current_ticker not in existing_tickers_set
                    # Naam krijgt de VOLLE breedte i.p.v. een eigen, smalle kolom
                    # -- op mobiel werd de rest (ticker-keuze, target%) anders
                    # samengeperst in nog krappere kolommen ernaast. Ticker +
                    # target staan nu in een eigen, ruimere rij eronder.
                    prefix = f"{_icon_span('warning', size_px=13, color='#E5484D')} " if key in unmatched_keys else ""
                    st.caption(f"{prefix}{group['product']} ({len(group['transactions'])} transactions)", unsafe_allow_html=True)
                    dcol2, dcol3 = st.columns([2, 1]) if is_new_position else (st.columns([1])[0], None)
                    with dcol2:
                        candidates = st.session_state["degiro_ticker_candidates"].get(key, [])
                        if len(candidates) >= 2:
                            # Meerdere beursnoteringen gevonden (bv. hetzelfde ETF op meerdere
                            # beurzen) -- laat kiezen met naam + beurs erbij, i.p.v. blind te gokken.
                            options = [f"{c['symbol']} -- {c['name']} ({c['exchange']})" for c in candidates]
                            options.append("Other (type manually)")
                            current_symbol = st.session_state["degiro_ticker_matches"].get(key, "")
                            default_index = next(
                                (i for i, c in enumerate(candidates) if c["symbol"] == current_symbol),
                                len(options) - 1,
                            )
                            chosen_label = st.selectbox(
                                "Ticker", options, index=default_index,
                                key=f"degiro_choice_{key}", label_visibility="collapsed",
                            )
                            if chosen_label == "Other (type manually)":
                                manual_default = current_symbol if current_symbol not in [c["symbol"] for c in candidates] else ""
                                manual_ticker = st.text_input(
                                    "Manual ticker", value=manual_default, key=f"degiro_manual_{key}",
                                    label_visibility="collapsed", placeholder="type ticker",
                                )
                                st.session_state["degiro_ticker_matches"][key] = manual_ticker
                            else:
                                chosen_symbol = candidates[options.index(chosen_label)]["symbol"]
                                st.session_state["degiro_ticker_matches"][key] = chosen_symbol
                        else:
                            current_guess = st.session_state["degiro_ticker_matches"].get(key, "")
                            new_ticker = st.text_input(
                                "Ticker", value=current_guess, key=f"degiro_ticker_{key}",
                                label_visibility="collapsed", placeholder="leave empty to skip",
                            )
                            st.session_state["degiro_ticker_matches"][key] = new_ticker
                    # Target weight ALLEEN vragen voor een NIEUWE positie (nog
                    # niet in je bestaande holdings) -- eenmalig, bij aanmaak,
                    # i.p.v. een aparte lijst met ALLE posities achteraf (die
                    # voelde als een dubbele, overbodige waslijst naast de
                    # portfolio-tabel zelf). Optioneel, leeg = geen target.
                    if dcol3 is not None:
                        with dcol3:
                            st.session_state.setdefault("degiro_target_weights", {})
                            st.session_state["degiro_target_weights"][key] = st.number_input(
                                "Target %", min_value=0.0, max_value=100.0, step=0.5, value=0.0,
                                key=f"degiro_target_{key}", label_visibility="collapsed",
                                help="Optional -- target allocation % for this new position",
                            )
                    st.markdown("<div style='height: 0.4rem'></div>", unsafe_allow_html=True)



                ready_count = sum(1 for t in st.session_state["degiro_ticker_matches"].values() if t.strip())
                st.caption(f"{ready_count} of {len(degiro_grouped)} securities have a ticker -- "
                           f"the rest will be skipped.")

                if st.button("Import all matched transactions", type="primary"):
                    imported_positions = 0
                    imported_transactions = 0
                    imported_duplicates_skipped = 0
                    all_holdings_for_import = database.get_user_holdings(user_email)
                    to_import = [
                        (key, group) for key, group in degiro_grouped.items()
                        if st.session_state["degiro_ticker_matches"].get(key, "").strip()
                    ]

                    progress_bar = st.progress(0.0)
                    status_text = st.empty()

                    for i, (key, group) in enumerate(to_import):
                        ticker = st.session_state["degiro_ticker_matches"][key].strip()
                        status_text.markdown(f"**Importing {group['product']}...** ({i + 1} of {len(to_import)})")

                        # Ook GESLOTEN posities meenemen (niet alleen de actieve lijst) --
                        # anders zou opnieuw kopen van iets dat je ooit volledig verkocht
                        # had, per ongeluk een dubbele, nieuwe positie aanmaken i.p.v. de
                        # bestaande (met z'n geschiedenis) te hergebruiken.
                        existing = next((h for h in all_holdings_for_import if h["ticker"] == ticker), None)
                        if existing:
                            holding_id = existing["id"]
                            existing_manual_shares = existing.get("shares") or 0.0
                            existing_tx = database.get_transactions_for_holding(user_email, holding_id)
                            if not existing_tx and existing_manual_shares > 0:
                                # Zelfde inhaal-logica als bij 'Log a transaction': bestaande
                                # handmatige shares vastleggen tegen de huidige prijs, vandaag.
                                try:
                                    backfill_price = float(yf.Ticker(ticker).history(period="1d")["Close"].iloc[-1])
                                    backfill_currency = get_cached_ticker_currency(ticker)
                                except Exception:
                                    backfill_price = group["transactions"][0]["price"]
                                    backfill_currency = (
                                        get_cached_ticker_currency(ticker)
                                        if group["transactions"][0]["price_is_native"] else "EUR"
                                    )
                                database.add_transaction(
                                    user_email, holding_id, "buy",
                                    shares=existing_manual_shares, price=backfill_price, fee=0.0,
                                    transaction_date=datetime.now().date().isoformat(),
                                    currency=backfill_currency,
                                )
                        else:
                            holding_id = database.add_holding(
                                user_email, group["product"], ticker, shares=None, isin=group.get("isin"),
                                value_currency=get_cached_ticker_currency(ticker),
                            )
                            imported_positions += 1
                            # De optioneel ingevulde target weight (bij deze
                            # nieuwe positie zelf ingevuld, zie hierboven)
                            # direct opslaan -- eenmalig, bij aanmaak.
                            import_target_weight = st.session_state.get("degiro_target_weights", {}).get(key)
                            if import_target_weight and import_target_weight > 0:
                                database.set_target_weight(holding_id, user_email, import_target_weight)

                        already_logged = database.get_transactions_for_holding(user_email, holding_id)

                        def _is_duplicate(new_tx, existing_list):
                            # Prijs-tolerantie: 1% relatief (met een kleine
                            # absolute ondergrens voor goedkope posities) i.p.v.
                            # helemaal geen prijs-check (te los -- zag bij
                            # meerdere, losse aankopen op dezelfde dag/aantal
                            # een 2e, ECHT andere aankoopprijs onterecht als
                            # duplicaat overslaan, bv. GRAB/ORBS/ADURO) EN i.p.v.
                            # een exacte match (te strak -- zag bij een
                            # parser-versie-verschil een allang-verkochte positie
                            # (EXXY.DE/ALFEN.AS) niet meer herkennen en dus
                            # dubbel importeren). 1% dekt het typische parser-
                            # afrondingsverschil ruim, terwijl een 2e, bewust
                            # andere aankoop met een ANDERE koers vrijwel altijd
                            # verder dan 1% uit elkaar ligt.
                            for existing in existing_list:
                                if existing["transaction_type"] != new_tx["transaction_type"]:
                                    continue
                                if existing["transaction_date"] != new_tx["transaction_date"]:
                                    continue
                                if abs(existing["shares"] - new_tx["shares"]) >= 0.0001:
                                    continue
                                price_tolerance = max(abs(new_tx["price"]) * 0.01, 0.02)
                                if abs(existing["price"] - new_tx["price"]) <= price_tolerance:
                                    return True
                            return False

                        # Terugval-valuta (als de CSV geen expliciete
                        # koers_currency heeft voor een specifieke rij, bv.
                        # een oudere export-versie) -- 1x bepaald buiten de
                        # loop, puur als fallback.
                        import_fallback_currency = get_cached_ticker_currency(ticker)
                        import_fee_fx_rate_fallback = None  # lazy: alleen als de CSV geen 'Wisselkoers'-kolom had

                        skipped_duplicates = 0
                        for t in group["transactions"]:
                            if _is_duplicate(t, already_logged):
                                skipped_duplicates += 1
                                continue
                            # De EXPLICIETE valuta uit de CSV zelf ('Koers'-
                            # kolom se eigen valuta-indicator) heeft ALTIJD
                            # voorrang boven een ticker-achtervoegsel-gok --
                            # die gok bleek fout voor USD-genoteerde aandelen
                            # op een Canadese beurs (bv. USA.TO, dat ondanks
                            # de .TO-notering gewoon in USD handelt).
                            row_native_currency = t.get("koers_currency") or import_fallback_currency
                            if t["price_is_native"] and row_native_currency and row_native_currency != "EUR":
                                # BELANGRIJK: de EXACTE, HISTORISCHE wisselkoers
                                # van DIE transactiedag gebruiken (uit de CSV's
                                # eigen 'Wisselkoers'-kolom), niet een live
                                # opgehaalde koers van vandaag -- anders geeft
                                # de fee (een klein bedrag) een kleine maar
                                # zichtbare afwijking in de gemiddelde
                                # kostprijs, puur omdat de wisselkoers sinds de
                                # aankoop is bewogen. Per transactie apart (niet
                                # 1x gedeeld voor de hele groep), want
                                # verschillende aankopen op verschillende dagen
                                # hebben elk hun eigen, andere historische koers.
                                if t.get("historical_fx_rate"):
                                    fee_fx_rate = t["historical_fx_rate"]
                                else:
                                    if import_fee_fx_rate_fallback is None:
                                        import_fee_fx_rate_fallback = get_fx_rate("EUR", row_native_currency) or 1.0
                                    fee_fx_rate = import_fee_fx_rate_fallback
                                t_fee = t["fee_eur"] * fee_fx_rate
                                t_currency = row_native_currency
                            else:
                                # Prijs is al EUR (geen 'Koers' beschikbaar in
                                # de export, zeldzame terugval) -- fee blijft
                                # ook gewoon in EUR, geen conversie nodig.
                                t_fee = t["fee_eur"]
                                t_currency = "EUR"
                            database.add_transaction(
                                user_email, holding_id, t["transaction_type"],
                                shares=t["shares"], price=t["price"], fee=t_fee,
                                transaction_date=t["transaction_date"], currency=t_currency,
                            )
                            imported_transactions += 1

                        if skipped_duplicates:
                            imported_duplicates_skipped += skipped_duplicates

                        sync_holding_shares_from_transactions(holding_id, user_email)
                        progress_bar.progress((i + 1) / len(to_import))

                    status_text.empty()
                    progress_bar.empty()

                    # Dividend-rijen permanent opslaan -- ALLEEN relevant voor
                    # Trade Republic (DEGIRO heeft er nooit). Trade Republic's
                    # 'asset_code' is een ISIN, geen ticker (zie de parser's
                    # eigen toelichting) -- dus eerst dezelfde ISIN-naar-ticker-
                    # matching hergebruiken die de gebruiker hierboven al voor
                    # de buy/sell-rijen deed, i.p.v. de ISIN zelf als 'ticker'
                    # in dividend_income op te slaan.
                    degiro_div_imported = degiro_div_skipped = 0
                    if degiro_dividends:
                        _isin_to_resolved = {
                            group.get("isin"): st.session_state["degiro_ticker_matches"].get(key, "").strip()
                            for key, group in degiro_grouped.items() if group.get("isin")
                        }
                        _div_naam_by_isin = {
                            group.get("isin"): group["product"]
                            for group in degiro_grouped.values() if group.get("isin")
                        }
                        _resolved_degiro_dividends = [
                            {**d, "asset_code": _isin_to_resolved.get(d.get("asset_code")) or d.get("asset_code")}
                            for d in degiro_dividends
                        ]
                        _div_naam_lookup = {
                            (_isin_to_resolved.get(isin) or isin): naam
                            for isin, naam in _div_naam_by_isin.items()
                        }
                        degiro_div_imported, degiro_div_skipped = _persist_dividend_rows(
                            user_email, _resolved_degiro_dividends,
                            "trade_republic" if is_trade_republic_import else "degiro",
                            "EUR", ticker_naam_lookup=_div_naam_lookup,
                        )

                    dup_txt = f" ({imported_duplicates_skipped} already-imported duplicates skipped)" if imported_duplicates_skipped else ""
                    div_txt = f" Plus {degiro_div_imported} dividend payment(s) added to your Dividend history." if degiro_div_imported else ""
                    st.success(f"Imported {imported_transactions} transactions across "
                               f"{imported_positions} new position(s)!{dup_txt}{div_txt}")
                    already_imported.add(degiro_file.name)
                    st.session_state["degiro_imported_filenames"] = already_imported
                    if hasattr(database, "set_last_csv_import"):
                        try:
                            database.set_last_csv_import(user_email, datetime.now().isoformat(), degiro_file.name)
                        except Exception:
                            pass  # het loggen van dit tijdstip mag de daadwerkelijke import nooit blokkeren
                    for state_key in ["degiro_parsed_filename", "degiro_grouped", "degiro_skipped",
                                       "degiro_dividends", "degiro_ticker_matches", "degiro_ticker_candidates"]:
                        st.session_state.pop(state_key, None)
                    st.rerun()

            # --- DEGIRO Rekeningoverzicht (Account statement) -- de ENIGE
            # bron van DEGIRO-dividenden (zie parse_degiro_account_
            # statement_csv's toelichting: de Transacties-export hierboven
            # bevat er GEEN -- dat was de kern van waarom DEGIRO-dividenden
            # niet op de Dividend-pagina verschenen). Simpeler dan de volle
            # Transacties-matching-UI: dividend-only, dus geen buy/sell-
            # groepering nodig, alleen een ISIN-naar-ticker-resolutie per
            # UNIEKE ISIN -- met bestaande holdings als eerste, snelste bron
            # (je hebt de bijbehorende positie hoogstwaarschijnlijk al
            # eerder via de Transacties-export geimporteerd).
            already_imported_da = st.session_state.get("degiro_account_imported_filenames", set())

            if degiro_account_file is not None and degiro_account_file.name in already_imported_da:
                st.success(f"'{degiro_account_file.name}' was already imported.", icon=":material/check_circle:")
                if st.button("Process this file again anyway", key="degiro_account_reimport_btn"):
                    already_imported_da.discard(degiro_account_file.name)
                    st.session_state["degiro_account_imported_filenames"] = already_imported_da
                    st.session_state.pop("degiro_account_parsed_filename", None)
                    st.rerun()
            elif degiro_account_file is not None:
                if st.session_state.get("degiro_account_parsed_filename") != degiro_account_file.name:
                    with st.spinner("Reading your file..."):
                        da_parse_result = parse_degiro_account_statement_csv(degiro_account_file.getvalue())
                    st.session_state["degiro_account_parsed_filename"] = degiro_account_file.name
                    st.session_state["degiro_account_dividends"] = da_parse_result["dividend_rows"]
                    st.session_state["degiro_account_skipped"] = da_parse_result["skipped_rows"]

                    existing_isin_to_ticker = {
                        h["isin"]: h["ticker"] for h in database.get_user_holdings(user_email) if h.get("isin")
                    }
                    isin_matches = {}
                    isin_candidates = {}
                    unique_isins = {
                        (d["asset_code"], d.get("product")) for d in da_parse_result["dividend_rows"]
                    }
                    with st.spinner(f"Looking up tickers for {len(unique_isins)} securities..."):
                        for isin, product in unique_isins:
                            remembered = existing_isin_to_ticker.get(isin)
                            if remembered:
                                isin_matches[isin] = remembered
                                isin_candidates[isin] = [{"symbol": remembered, "name": product, "exchange": "remembered"}]
                            else:
                                candidates = get_ticker_candidates(product or isin, isin)
                                isin_candidates[isin] = candidates
                                isin_matches[isin] = candidates[0]["symbol"] if candidates else ""
                    st.session_state["degiro_account_ticker_matches"] = isin_matches
                    st.session_state["degiro_account_ticker_candidates"] = isin_candidates

                da_dividends = st.session_state["degiro_account_dividends"]
                da_skipped = st.session_state["degiro_account_skipped"]

                st.success(f"Found {len(da_dividends)} dividend row(s).")
                if da_skipped:
                    reasons_preview = "; ".join(reason for _, reason in da_skipped[:5])
                    more = "..." if len(da_skipped) > 5 else ""
                    st.caption(f"{len(da_skipped)} row(s) couldn't be read and were skipped: "
                               f"{reasons_preview}{more}")

                _unique_by_isin = {}
                for d in da_dividends:
                    _unique_by_isin.setdefault(d["asset_code"], d.get("product") or d["asset_code"])

                if da_dividends:
                    st.markdown("**Review the ticker for each security** (auto-suggested from your "
                                 "existing positions where possible -- double-check before importing):")
                    for isin, product in _unique_by_isin.items():
                        current_guess = st.session_state["degiro_account_ticker_matches"].get(isin, "")
                        candidates = st.session_state["degiro_account_ticker_candidates"].get(isin, [])
                        st.caption(product)
                        if len(candidates) >= 2:
                            options = [f"{c['symbol']} -- {c['name']} ({c['exchange']})" for c in candidates]
                            options.append("Other (type manually)")
                            default_index = next(
                                (i for i, c in enumerate(candidates) if c["symbol"] == current_guess),
                                len(options) - 1,
                            )
                            chosen_label = st.selectbox(
                                "Ticker", options, index=default_index,
                                key=f"degiro_account_choice_{isin}", label_visibility="collapsed",
                            )
                            if chosen_label == "Other (type manually)":
                                manual_default = current_guess if current_guess not in [c["symbol"] for c in candidates] else ""
                                manual_ticker = st.text_input(
                                    "Manual ticker", value=manual_default, key=f"degiro_account_manual_{isin}",
                                    label_visibility="collapsed", placeholder="type ticker",
                                )
                                st.session_state["degiro_account_ticker_matches"][isin] = manual_ticker
                            else:
                                st.session_state["degiro_account_ticker_matches"][isin] = (
                                    candidates[options.index(chosen_label)]["symbol"]
                                )
                        else:
                            new_ticker = st.text_input(
                                "Ticker", value=current_guess, key=f"degiro_account_ticker_{isin}",
                                label_visibility="collapsed", placeholder="leave empty to skip",
                            )
                            st.session_state["degiro_account_ticker_matches"][isin] = new_ticker

                    if st.button("Import these dividends", key="degiro_account_import_btn", type="primary"):
                        _resolved_rows = []
                        for d in da_dividends:
                            _resolved_ticker = st.session_state["degiro_account_ticker_matches"].get(
                                d["asset_code"], "",
                            ).strip()
                            if not _resolved_ticker:
                                continue
                            _resolved_rows.append({**d, "asset_code": _resolved_ticker})
                        _naam_lookup = {
                            st.session_state["degiro_account_ticker_matches"].get(isin, "").strip(): product
                            for isin, product in _unique_by_isin.items()
                        }
                        da_div_imported, da_div_skipped = _persist_dividend_rows(
                            user_email, _resolved_rows, "degiro", ticker_naam_lookup=_naam_lookup,
                        )
                        st.success(
                            f"Imported {da_div_imported} dividend payment(s) to your Dividend history "
                            f"({da_div_skipped} skipped as duplicate/invalid/unmatched)."
                        )
                        already_imported_da.add(degiro_account_file.name)
                        st.session_state["degiro_account_imported_filenames"] = already_imported_da
                        for state_key in ["degiro_account_parsed_filename", "degiro_account_dividends",
                                           "degiro_account_skipped", "degiro_account_ticker_matches",
                                           "degiro_account_ticker_candidates"]:
                            st.session_state.pop(state_key, None)
                        st.rerun()

            # --- Robinhood: veel eenvoudiger dan DEGIRO -- de CSV geeft de
            # ticker al rechtstreeks mee ('Asset Code'), dus geen aparte
            # ticker-matching-stap nodig. Rechtstreeks parsen -> importeren.
            # robinhood_file wordt hierboven al gevuld via het gedeelde
            # upload-vak + de automatische broker-herkenning -- geen eigen
            # losse uploader meer nodig.
            already_imported_rh = st.session_state.get("robinhood_imported_filenames", set())

            if robinhood_file is not None and robinhood_file.name in already_imported_rh:
                st.success(f"'{robinhood_file.name}' was already imported.", icon=":material/check_circle:")
                if st.button("Process this file again anyway", key="robinhood_reimport_btn"):
                    already_imported_rh.discard(robinhood_file.name)
                    st.session_state["robinhood_imported_filenames"] = already_imported_rh
                    st.session_state.pop("robinhood_parsed_filename", None)
                    st.rerun()
            elif robinhood_file is not None:
                if st.session_state.get("robinhood_parsed_filename") != robinhood_file.name:
                    with st.spinner("Reading your file..."):
                        rh_parse_result = parse_robinhood_transactions_csv(robinhood_file.getvalue())
                    st.session_state["robinhood_parsed_filename"] = robinhood_file.name
                    st.session_state["robinhood_grouped"] = rh_parse_result["grouped"]
                    st.session_state["robinhood_skipped"] = rh_parse_result["skipped_rows"]
                    st.session_state["robinhood_dividends"] = rh_parse_result["dividend_rows"]
                    st.session_state["robinhood_other_ignored"] = rh_parse_result["other_ignored_codes"]

                rh_grouped = st.session_state["robinhood_grouped"]
                rh_skipped = st.session_state["robinhood_skipped"]
                rh_dividends = st.session_state["robinhood_dividends"]
                rh_other_ignored = st.session_state.get("robinhood_other_ignored", {})

                total_rh_tx = sum(len(g["transactions"]) for g in rh_grouped.values())
                st.success(f"Found {len(rh_grouped)} securities, {total_rh_tx} buy/sell transaction(s).")
                if rh_dividends:
                    st.caption(
                        f"{len(rh_dividends)} dividend row(s) found -- will be added to your "
                        f"Dividend history (not as buy/sell transactions)."
                    )
                if rh_other_ignored:
                    # Transparant maken WELKE onherkende codewoorden er waren
                    # (i.p.v. ze stilzwijgend te negeren) -- zodat je zelf kunt
                    # beoordelen of daar iets relevants tussen zat.
                    codes_summary = ", ".join(f"{code} ({count}x)" for code, count in rh_other_ignored.items())
                    st.caption(f"Ignored other row type(s) not tracked as positions: {codes_summary}")
                if rh_skipped:
                    reasons_preview = "; ".join(reason for _, reason in rh_skipped[:5])
                    more = "..." if len(rh_skipped) > 5 else ""
                    st.caption(f"{len(rh_skipped)} row(s) couldn't be read and were skipped: "
                               f"{reasons_preview}{more}")

                if rh_grouped and st.button("Import these transactions", key="robinhood_import_btn", type="primary"):
                    all_holdings_rh = database.get_user_holdings(user_email)
                    rh_progress = st.progress(0.0)
                    rh_status = st.empty()
                    rh_imported_tx = 0
                    rh_imported_pos = 0
                    rh_dup_skipped = 0

                    for i, (ticker, group) in enumerate(rh_grouped.items()):
                        rh_status.markdown(f"**Importing {group['product']}...** ({i + 1} of {len(rh_grouped)})")
                        existing = next((h for h in all_holdings_rh if h["ticker"] == ticker), None)
                        if existing:
                            holding_id = existing["id"]
                        else:
                            holding_id = database.add_holding(
                                user_email, group["product"], ticker, shares=None,
                                value_currency="USD",
                            )
                            rh_imported_pos += 1

                        already_logged_rh = database.get_transactions_for_holding(user_email, holding_id)

                        def _is_duplicate_rh(new_tx, existing_list):
                            # Zelfde 1%-prijstolerantie-logica als bij DEGIRO
                            # (zie de uitgebreide toelichting daar).
                            for existing_tx in existing_list:
                                if existing_tx["transaction_type"] != new_tx["transaction_type"]:
                                    continue
                                if existing_tx["transaction_date"] != new_tx["transaction_date"]:
                                    continue
                                if abs(existing_tx["shares"] - new_tx["shares"]) >= 0.0001:
                                    continue
                                price_tolerance = max(abs(new_tx["price"]) * 0.01, 0.02)
                                if abs(existing_tx["price"] - new_tx["price"]) <= price_tolerance:
                                    return True
                            return False

                        for t in group["transactions"]:
                            if _is_duplicate_rh(t, already_logged_rh):
                                rh_dup_skipped += 1
                                continue
                            database.add_transaction(
                                user_email, holding_id, t["transaction_type"],
                                shares=t["shares"], price=t["price"], fee=t["fee"],
                                transaction_date=t["transaction_date"], currency=t["currency"],
                            )
                            rh_imported_tx += 1

                        sync_holding_shares_from_transactions(holding_id, user_email)
                        rh_progress.progress((i + 1) / len(rh_grouped))

                    rh_status.empty()
                    rh_progress.empty()

                    rh_div_imported, rh_div_skipped = _persist_dividend_rows(
                        user_email, rh_dividends, "robinhood", "USD",
                        ticker_naam_lookup={t: g["product"] for t, g in rh_grouped.items()},
                    )

                    dup_txt_rh = f" ({rh_dup_skipped} already-imported duplicates skipped)" if rh_dup_skipped else ""
                    div_txt_rh = f" Plus {rh_div_imported} dividend payment(s) added to your Dividend history." if rh_div_imported else ""
                    st.success(f"Imported {rh_imported_tx} transactions across "
                               f"{rh_imported_pos} new position(s)!{dup_txt_rh}{div_txt_rh}")
                    already_imported_rh.add(robinhood_file.name)
                    st.session_state["robinhood_imported_filenames"] = already_imported_rh
                    for state_key in ["robinhood_parsed_filename", "robinhood_grouped",
                                       "robinhood_skipped", "robinhood_dividends", "robinhood_other_ignored"]:
                        st.session_state.pop(state_key, None)
                    st.rerun()

            # --- Charles Schwab: zelfde eenvoudige route als Robinhood --
            # de CSV geeft de ticker al rechtstreeks mee ('Symbol'), dus
            # geen aparte ticker-matching-stap nodig.
            already_imported_sw = st.session_state.get("schwab_imported_filenames", set())

            if schwab_file is not None and schwab_file.name in already_imported_sw:
                st.success(f"'{schwab_file.name}' was already imported.", icon=":material/check_circle:")
                if st.button("Process this file again anyway", key="schwab_reimport_btn"):
                    already_imported_sw.discard(schwab_file.name)
                    st.session_state["schwab_imported_filenames"] = already_imported_sw
                    st.session_state.pop("schwab_parsed_filename", None)
                    st.rerun()
            elif schwab_file is not None:
                if st.session_state.get("schwab_parsed_filename") != schwab_file.name:
                    with st.spinner("Reading your file..."):
                        sw_parse_result = parse_schwab_transactions_csv(schwab_file.getvalue())
                    st.session_state["schwab_parsed_filename"] = schwab_file.name
                    st.session_state["schwab_grouped"] = sw_parse_result["grouped"]
                    st.session_state["schwab_skipped"] = sw_parse_result["skipped_rows"]
                    st.session_state["schwab_dividends"] = sw_parse_result["dividend_rows"]

                sw_grouped = st.session_state["schwab_grouped"]
                sw_skipped = st.session_state["schwab_skipped"]
                sw_dividends = st.session_state["schwab_dividends"]

                total_sw_tx = sum(len(g["transactions"]) for g in sw_grouped.values())
                st.success(f"Found {len(sw_grouped)} securities, {total_sw_tx} buy/sell transaction(s).")
                if sw_dividends:
                    st.caption(
                        f"{len(sw_dividends)} dividend row(s) found -- will be added to your "
                        f"Dividend history (not as buy/sell transactions)."
                    )
                if sw_skipped:
                    reasons_preview = "; ".join(reason for _, reason in sw_skipped[:5])
                    more = "..." if len(sw_skipped) > 5 else ""
                    st.caption(f"{len(sw_skipped)} row(s) couldn't be read and were skipped: "
                               f"{reasons_preview}{more}")

                if sw_grouped and st.button("Import these transactions", key="schwab_import_btn", type="primary"):
                    all_holdings_sw = database.get_user_holdings(user_email)
                    sw_progress = st.progress(0.0)
                    sw_status = st.empty()
                    sw_imported_tx = 0
                    sw_imported_pos = 0
                    sw_dup_skipped = 0

                    for i, (ticker, group) in enumerate(sw_grouped.items()):
                        sw_status.markdown(f"**Importing {group['product']}...** ({i + 1} of {len(sw_grouped)})")
                        existing = next((h for h in all_holdings_sw if h["ticker"] == ticker), None)
                        if existing:
                            holding_id = existing["id"]
                        else:
                            holding_id = database.add_holding(
                                user_email, group["product"], ticker, shares=None,
                                value_currency="USD",
                            )
                            sw_imported_pos += 1

                        already_logged_sw = database.get_transactions_for_holding(user_email, holding_id)

                        def _is_duplicate_sw(new_tx, existing_list):
                            # Zelfde 1%-prijstolerantie-logica als bij DEGIRO/
                            # Robinhood (zie de uitgebreide toelichting bij DEGIRO).
                            for existing_tx in existing_list:
                                if existing_tx["transaction_type"] != new_tx["transaction_type"]:
                                    continue
                                if existing_tx["transaction_date"] != new_tx["transaction_date"]:
                                    continue
                                if abs(existing_tx["shares"] - new_tx["shares"]) >= 0.0001:
                                    continue
                                price_tolerance = max(abs(new_tx["price"]) * 0.01, 0.02)
                                if abs(existing_tx["price"] - new_tx["price"]) <= price_tolerance:
                                    return True
                            return False

                        for t in group["transactions"]:
                            if _is_duplicate_sw(t, already_logged_sw):
                                sw_dup_skipped += 1
                                continue
                            database.add_transaction(
                                user_email, holding_id, t["transaction_type"],
                                shares=t["shares"], price=t["price"], fee=t["fee"],
                                transaction_date=t["transaction_date"], currency=t["currency"],
                            )
                            sw_imported_tx += 1

                        sync_holding_shares_from_transactions(holding_id, user_email)
                        sw_progress.progress((i + 1) / len(sw_grouped))

                    sw_status.empty()
                    sw_progress.empty()

                    sw_div_imported, sw_div_skipped = _persist_dividend_rows(
                        user_email, sw_dividends, "schwab", "USD",
                        ticker_naam_lookup={t: g["product"] for t, g in sw_grouped.items()},
                    )

                    dup_txt_sw = f" ({sw_dup_skipped} already-imported duplicates skipped)" if sw_dup_skipped else ""
                    div_txt_sw = f" Plus {sw_div_imported} dividend payment(s) added to your Dividend history." if sw_div_imported else ""
                    st.success(f"Imported {sw_imported_tx} transactions across "
                               f"{sw_imported_pos} new position(s)!{dup_txt_sw}{div_txt_sw}")
                    already_imported_sw.add(schwab_file.name)
                    st.session_state["schwab_imported_filenames"] = already_imported_sw
                    for state_key in ["schwab_parsed_filename", "schwab_grouped",
                                       "schwab_skipped", "schwab_dividends"]:
                        st.session_state.pop(state_key, None)
                    st.rerun()

    elif manage_section == "Log transaction":
        # --- Geen omlijnd kader meer om het hele formulier -- alles ademt
        # clean op de achtergrond. 1 brede, scope-gevende container-key
        # eromheen zodat de CSS hieronder ALLE inputs/dropdowns/toggles/
        # +--knoppen in dit formulier in 1x kan raken (minimalistische
        # dunne rand, platte segmented-controls, subtiele teal Save-knop),
        # zonder andere pagina's se widgets te raken. ---
        _log_tx_form_key = "log_tx_form_wrap"
        st.markdown(
            f'<style>'
            # Tekstvelden, dropdowns en de datumkiezer: flinterdunne,
            # zachte rand i.p.v. Streamlit's standaard gevulde/glimmende
            # look, met een subtiele focus-state.
            f'.st-key-{_log_tx_form_key} div[data-baseweb="input"], '
            f'.st-key-{_log_tx_form_key} div[data-baseweb="select"] > div, '
            f'.st-key-{_log_tx_form_key} div[data-baseweb="datepicker"] div[data-baseweb="input"] {{ '
            f'background:transparent !important; border:1px solid rgba(148,163,184,0.18) !important; '
            f'box-shadow:none !important; }} '
            f'.st-key-{_log_tx_form_key} div[data-baseweb="input"]:focus-within, '
            f'.st-key-{_log_tx_form_key} div[data-baseweb="select"] > div:focus-within {{ '
            f'border-color:rgba(31,174,150,0.45) !important; }} '
            # +/- stap-knoppen naast de numerieke velden: platte tekst-
            # knoppen i.p.v. zware omlijnde blokjes.
            f'.st-key-{_log_tx_form_key} button[data-testid="stNumberInputStepUp"], '
            f'.st-key-{_log_tx_form_key} button[data-testid="stNumberInputStepDown"] {{ '
            f'background:transparent !important; border:none !important; box-shadow:none !important; '
            f'color:#8992A3 !important; }} '
            # Segmented-controls (Existing/New position, Buy/Sell): zelfde
            # platte stijl als de Daily/All-time-toggle bovenaan de pagina.
            f'.st-key-{_log_tx_form_key} div[data-testid="stSegmentedControl"] {{ '
            f'border:none !important; background:transparent !important; box-shadow:none !important; }} '
            f'.st-key-{_log_tx_form_key} div[data-testid="stSegmentedControl"] button, '
            f'.st-key-{_log_tx_form_key} div[data-testid="stSegmentedControl"] label {{ '
            f'border:none !important; outline:none !important; box-shadow:none !important; '
            f'background:transparent !important; color:#8992A3 !important; font-weight:600 !important; }} '
            f'.st-key-{_log_tx_form_key} div[data-testid="stSegmentedControl"] button[aria-pressed="true"], '
            f'.st-key-{_log_tx_form_key} div[data-testid="stSegmentedControl"] label[data-checked="true"] {{ '
            f'background:rgba(31,174,150,0.15) !important; color:#1FAE96 !important; border:none !important; }} '
            f'</style>',
            unsafe_allow_html=True,
        )
        with st.container(key=_log_tx_form_key):
            # --- Log a transaction (werkt ook zonder bestaande posities -- een
            # nieuwe positie kan direct via een eerste 'Log a buy' worden
            # aangemaakt) ---
            st.markdown(
                '<div style="color:#64748B; font-size:10px; font-weight:700; letter-spacing:0.06em; '
                'text-transform:uppercase; margin-bottom:1.5rem;">Note: positions without logged '
                'transactions will not account for realized return under Analyze.</div>',
                unsafe_allow_html=True,
            )

            position_mode_options = (
                ["Existing position", "New position"] if holdings else ["New position"]
            )
            tx_position_mode = st.segmented_control(
                "Position", options=position_mode_options, selection_mode="single",
                default=position_mode_options[0], key="tx_position_mode", label_visibility="collapsed",
            )
            if tx_position_mode is None:
                tx_position_mode = position_mode_options[0]

            tx_holding = None
            new_position_symbol = None
            new_position_name = None

            if tx_position_mode == "Existing position":
                tx_holding_options = {f"{h['naam']} ({h['ticker']})": h for h in holdings}
                tx_label = st.selectbox(
                    "Position", list(tx_holding_options.keys()), key="tx_select", label_visibility="collapsed",
                )
                tx_holding = tx_holding_options[tx_label]
                tx_type = st.segmented_control(
                    "Type", options=["Buy", "Sell"], selection_mode="single",
                    default="Buy", key="tx_type_radio",
                )
                if tx_type is None:
                    tx_type = "Buy"
                is_buy = tx_type == "Buy"
            else:
                # Nieuwe positie: altijd een koop (je kan niet iets verkopen dat je nog niet hebt)
                is_buy = True
                tx_is_custom_asset = st.checkbox(
                    "\u2726 Log as custom yield asset (real estate, fixed income)",
                    key="tx_is_custom_asset",
                    help="For assets without a Yahoo Finance ticker -- fractional real estate, "
                         "private fixed-income products, etc. You enter the cashflow yourself "
                         "instead of it being looked up live.",
                )
                if tx_is_custom_asset:
                    new_position_name = st.text_input(
                        "Asset name", key="tx_custom_name",
                        placeholder="e.g. Prop.com -- Lisbon apartment",
                    )
                    new_position_symbol = st.text_input(
                        "Identifier", key="tx_custom_symbol",
                        placeholder="e.g. PROP.COM or REALESTATE1",
                        help="A short, unique label for this asset -- used instead of a ticker.",
                    ).strip().upper()
                else:
                    tx_search_query = st.text_input(
                        "Search for the company/asset you bought", key="tx_search_query",
                    )
                    if tx_search_query:
                        try:
                            tx_search_results = yf.Search(tx_search_query, max_results=8).quotes
                        except Exception as exc:
                            tx_search_results = []
                            st.caption(f"Search failed: {exc}")
                        if tx_search_results:
                            tx_options = {}
                            for r in tx_search_results:
                                name = r.get("shortname") or r.get("longname") or r.get("symbol")
                                label = f"{name} ({r.get('symbol')}) -- {r.get('exchange', '')}"
                                tx_options[label] = r
                            tx_chosen_label = st.selectbox("Choose the right match", list(tx_options.keys()), key="tx_new_match")
                            tx_chosen = tx_options[tx_chosen_label]
                            new_position_symbol = tx_chosen.get("symbol")
                            new_position_name = tx_chosen.get("shortname") or tx_chosen.get("longname") or new_position_symbol
                        else:
                            st.caption("No results found for this search -- try a different name.")

            if tx_position_mode == "New position" and st.session_state.get("tx_is_custom_asset"):
                # Custom yield asset: geen Shares/Price/Fee/Currency-keuze --
                # gewoon het geinvesteerde bedrag en de verwachte jaarlijkse
                # cashflow. Shares wordt straks bij het opslaan hard op 1
                # gezet, Price op het totale investeringsbedrag (zie verderop).
                custom_col1, custom_col2 = st.columns(2)
                with custom_col1:
                    tx_custom_capital = st.number_input(
                        "Total capital invested (\u20ac)", min_value=0.0, step=50.0,
                        key="tx_custom_capital",
                    )
                with custom_col2:
                    tx_custom_cashflow = st.number_input(
                        "Estimated annual cashflow (\u20ac)", min_value=0.0, step=10.0,
                        key="tx_custom_cashflow",
                    )
                tx_date = st.date_input("Date", key="tx_date_input")
                tx_shares, tx_price, tx_fee, tx_currency = 1.0, tx_custom_capital, 0.0, "EUR"
                tx_target_weight = 0.0
                if tx_position_mode == "New position":
                    tx_target_weight = st.number_input(
                        "Target allocation % (optional)", min_value=0.0, max_value=100.0, step=0.5,
                        value=0.0, key="tx_target_weight_input",
                        help="Optional -- the % of your portfolio you want this position to make up.",
                    )
            else:
                trow1_col1, trow1_col2 = st.columns(2)
                with trow1_col1:
                    tx_shares = st.number_input("Shares", min_value=0.0, step=1.0, key="tx_shares_input")
                with trow1_col2:
                    tx_price = st.number_input("Price per share", min_value=0.0, step=0.01, key="tx_price_input")
                trow2_col1, trow2_col2 = st.columns(2)
                with trow2_col1:
                    tx_fee = st.number_input("Fee paid", min_value=0.0, step=0.01, value=0.0, key="tx_fee_input")
                with trow2_col2:
                    tx_date = st.date_input("Date", key="tx_date_input")

                # Valuta expliciet vragen i.p.v. altijd EUR aan te nemen --
                # was voorheen de bron van een echte, verwarrende bug: een
                # Amerikaans aandeel gekocht in USD werd stilzwijgend als EUR
                # behandeld, wat het rendement volledig verkeerd berekende.
                # Slimme default: de native valuta van de gekozen ticker (zoals
                # je die op je broker-overzicht zou zien), maar altijd
                # aanpasbaar -- voor het geval je toch de EUR-equivalente
                # prijs invoert (bv. van een DEGIRO-overzicht).
                tx_ticker_for_currency = tx_holding["ticker"] if tx_holding else new_position_symbol
                tx_default_currency = (
                    get_cached_ticker_currency(tx_ticker_for_currency) if tx_ticker_for_currency else "EUR"
                )
                tx_currency_options = ["EUR", "USD", "GBP", "CAD", "CHF", "SEK", "DKK", "NOK", "HKD", "JPY", "AUD"]
                tx_currency_default_index = (
                    tx_currency_options.index(tx_default_currency) if tx_default_currency in tx_currency_options else 0
                )
                tx_currency = st.selectbox(
                    "Price currency", tx_currency_options, index=tx_currency_default_index, key="tx_currency_input",
                    help="The currency the price above is in -- usually the ticker's native trading currency.",
                )

                # Target weight ALLEEN vragen bij een NIEUWE positie -- eenmalig,
                # bij aanmaak, i.p.v. een aparte lijst met ALLE posities achteraf.
                tx_target_weight = 0.0
                if tx_position_mode == "New position":
                    tx_target_weight = st.number_input(
                        "Target allocation % (optional)", min_value=0.0, max_value=100.0, step=0.5,
                        value=0.0, key="tx_target_weight_input",
                        help="Optional -- the % of your portfolio you want this position to make up.",
                    )

            can_save = (tx_holding is not None) or (new_position_symbol is not None)

            _save_tx_key = "log_tx_save_btn_wrap"
            st.markdown(
                f'<style>'
                f'.st-key-{_save_tx_key} {{ margin-top:1rem !important; }} '
                f'.st-key-{_save_tx_key} button {{ '
                f'width:100% !important; background:#10B981 !important; color:#020617 !important; '
                f'font-weight:700 !important; font-size:0.9rem !important; padding:0.75rem 0 !important; '
                f'border-radius:12px !important; border:none !important; box-shadow:0 4px 12px rgba(16,185,129,0.25) !important; }} '
                f'.st-key-{_save_tx_key} button:hover {{ background:#059669 !important; }} '
                f'</style>',
                unsafe_allow_html=True,
            )
            with st.container(key=_save_tx_key):
                save_tx_clicked = can_save and st.button("Save transaction", use_container_width=True)

            if save_tx_clicked:
                if tx_shares <= 0 or tx_price <= 0:
                    st.error("Shares and price must both be greater than 0.")
                else:
                    if tx_position_mode == "New position":
                        if len(holdings) >= 10 and not is_premium:
                            st.error(
                                "You've reached the free plan limit of 10 tracked positions. "
                                "Upgrade to Premium for unlimited tracking."
                            )
                        elif st.session_state.get("tx_is_custom_asset") and not new_position_symbol:
                            st.error("Please fill in an identifier for this custom yield asset.")
                        elif st.session_state.get("tx_is_custom_asset"):
                            # Custom yield asset: geen Yahoo Finance-ticker om op te
                            # zoeken, dus 'value_currency' hard op EUR i.p.v. via
                            # get_cached_ticker_currency() (die zou voor een
                            # fake ticker als 'PROP.COM' falen/onzin teruggeven).
                            new_id = database.add_holding(
                                user_email, new_position_name, new_position_symbol, shares=1,
                                value_currency="EUR", custom_annual_cashflow=tx_custom_cashflow,
                            )
                            if tx_target_weight > 0:
                                database.set_target_weight(new_id, user_email, tx_target_weight)
                            database.add_transaction(
                                user_email, new_id, "buy",
                                shares=1, price=tx_custom_capital, fee=0.0,
                                transaction_date=tx_date.isoformat(), currency="EUR",
                            )
                            # position_value moet HIER meteen gezet worden -- een
                            # custom asset heeft geen live koers, dus de normale
                            # prijs-ververs-stap zal 'm nooit vullen. Zonder deze
                            # regel zou de positie overal (My Portfolio, Analyze,
                            # Wealth Engine) als €0 meetellen.
                            database.update_holding_value(new_id, user_email, tx_custom_capital, value_currency="EUR")
                            st.success(f"{new_position_name} ({new_position_symbol}) added as a custom yield asset!")
                            st.rerun()
                        else:
                            new_id = database.add_holding(
                                user_email, new_position_name, new_position_symbol, shares=None,
                                value_currency=get_cached_ticker_currency(new_position_symbol),
                            )
                            if tx_target_weight > 0:
                                database.set_target_weight(new_id, user_email, tx_target_weight)
                            database.add_transaction(
                                user_email, new_id, "buy",
                                shares=tx_shares, price=tx_price, fee=tx_fee,
                                transaction_date=tx_date.isoformat(), currency=tx_currency,
                            )
                            sync_holding_shares_from_transactions(new_id, user_email)
                            st.success(f"{new_position_name} ({new_position_symbol}) added, with your buy logged!")
                            st.rerun()
                    else:
                        existing_tx = database.get_transactions_for_holding(user_email, tx_holding["id"])
                        existing_manual_shares = tx_holding.get("shares") or 0.0
                        if not existing_tx and existing_manual_shares > 0:
                            # Eerste transactie voor deze positie, en er stond al een handmatig
                            # aantal shares -- die vangen we automatisch op als een 'gekocht
                            # tegen de huidige prijs, vandaag'-transactie (simpele standaard,
                            # geen keuzemenu nodig; later aanpasbaar als je de echte
                            # historische aankoopprijs nog weet).
                            try:
                                backfill_price = float(yf.Ticker(tx_holding["ticker"]).history(period="1d")["Close"].iloc[-1])
                                backfill_currency = _native_currency_for_holding(tx_holding)
                            except Exception:
                                backfill_price = tx_price  # fallback als de live prijs niet op te halen is
                                backfill_currency = tx_currency
                            database.add_transaction(
                                user_email, tx_holding["id"], "buy",
                                shares=existing_manual_shares, price=backfill_price, fee=0.0,
                                transaction_date=datetime.now().date().isoformat(), currency=backfill_currency,
                            )
                            existing_tx.append({"transaction_type": "buy", "shares": existing_manual_shares})
                            backfill_symbol = "€" if backfill_currency == "EUR" else ("$" if backfill_currency == "USD" else backfill_currency + " ")
                            st.info(f"Your existing {existing_manual_shares:.2f} shares were logged as "
                                    f"bought at today's price ({backfill_symbol}{backfill_price:.2f}) -- edit this later if "
                                    f"you remember the actual original purchase price.")

                        database.add_transaction(
                            user_email, tx_holding["id"], "buy" if is_buy else "sell",
                            shares=tx_shares, price=tx_price, fee=tx_fee,
                            transaction_date=tx_date.isoformat(), currency=tx_currency,
                        )
                        shares_after = sync_holding_shares_from_transactions(tx_holding["id"], user_email)

                        # Bij een verkoop naar ~0 shares: de positie NIET verwijderen (dat zou
                        # via de cascade ook de transactiegeschiedenis wissen, en dus je
                        # gerealiseerde winst/verlies uit Performance laten verdwijnen) --
                        # 'ie blijft gewoon bestaan met 0 shares, verborgen uit My Portfolio
                        # via filter_active_holdings(), maar telt nog mee bij Performance.
                        if not is_buy and shares_after <= 0.001:
                            st.success(f"Sell logged -- {tx_holding['naam']} is now fully closed. "
                                       f"Its history still counts toward your Performance stats.")
                            st.rerun()

                        st.success("Transaction saved!")
                        st.rerun()

    elif manage_section == "Watchlist":
        try:
            watchlist_narrow_col = st.columns([1], width=900)[0]
        except Exception:
            watchlist_narrow_col = st.columns([1])[0]
        with watchlist_narrow_col:
            # Geen omlijnd kader meer om het hele tabblad -- content ademt
            # clean op de achtergrond, net als Rebalancing/Log transaction.
            # Extra vangnet tegen horizontale overflow (bovenop de per-rij-
            # fix hieronder): de hoofdcontainer zelf mag NOOIT breder worden
            # dan het scherm, wat ook de oorzaak zou zijn (bv. een toekomstig
            # element dat vergeet zichzelf in te perken).
            _watchlist_wrap_key = "watchlist_main_wrap"
            st.markdown(
                f'<style>.st-key-{_watchlist_wrap_key} {{ max-width:100% !important; '
                f'overflow-x:hidden !important; box-sizing:border-box !important; width:100% !important; }} '
                f'</style>',
                unsafe_allow_html=True,
            )
            with st.container(key=_watchlist_wrap_key):
                # --- WATCHLIST -- volgen zonder eigendom, voor gepersonaliseerde info op Today ---
                st.markdown(
                    '<div style="color:#64748B; font-size:10px; font-weight:700; letter-spacing:0.06em; '
                    'text-transform:uppercase; margin-bottom:1rem;">Track tickers you don\'t own yet. '
                    'They will show up with personalized signals and news on the Today page.</div>',
                    unsafe_allow_html=True,
                )

                watchlist_items = database.get_user_holdings(user_email, is_watchlist=True)

                if watchlist_items:
                    # Compacte lijst i.p.v. pills -- elke rij toont favicon+naam+
                    # ticker, plus een bel-icoon (prijs-alert instellen/aanpassen
                    # via popover) en een prullenbak-icoon (direct verwijderen,
                    # geen bevestiging nodig -- een watchlist-item heeft geen
                    # transactiegeschiedenis om per ongeluk kwijt te raken).
                    # BEWUST geen extra marktdata (koers/verandering) in de rij
                    # zelf -- alleen zichtbaar in de alert-popover, waar het
                    # nodig is als context voor de streefprijs.
                    #
                    # 2-koloms-indeling behouden; zebra-striping (afwisselend
                    # gekleurde rij-boxen) VERVANGEN door een flinterdunne
                    # border-bottom per rij -- zelfde, lichtere designtaal als
                    # Rebalancing hierboven i.p.v. losse gekleurde kaartjes.
                    watchlist_tickers = [w["ticker"] for w in watchlist_items]
                    watchlist_market_data = database.get_market_data_for_tickers(watchlist_tickers)

                    def _render_watchlist_row(w, row_idx):
                        # st.container(key=...) geeft een betrouwbare
                        # .st-key-{key}-klasse (bevestigd, al eerder gebruikt
                        # voor de prullenbak-knop), met een veilige fallback
                        # voor een oudere Streamlit-versie die 'key' op
                        # st.container() nog niet ondersteunt.
                        row_key = f"watchlist_row_{w['id']}"
                        try:
                            row_ctx = st.container(key=row_key)
                        except Exception:
                            row_ctx = st.container()
                            row_key = None
                        if row_key:
                            # Zelfde kaart-styling als Rebalancing hierboven --
                            # dunne rand, zachte egale achtergrond, afgeronde
                            # hoeken, py-2.5-padding -- i.p.v. de eerdere
                            # platte lijst met alleen een border-bottom.
                            # margin-bottom geeft de ademruimte tussen kaarten
                            # die de border-bottom-scheiding voorheen deed.
                            st.markdown(
                                f'<style>'
                                f'.st-key-{row_key} {{ '
                                f'background:rgba(15,23,42,0.3) !important; '
                                f'border:1px solid rgba(30,41,59,0.4) !important; '
                                f'border-radius:10px !important; '
                                f'padding:0.5rem 0.75rem !important; margin:0 !important; '
                                f'min-height:3.25rem !important; '
                                f'display:flex !important; align-items:center !important; '
                                f'justify-content:space-between !important; '
                                f'width:100% !important; max-width:100% !important; '
                                f'overflow-x:hidden !important; box-sizing:border-box !important; '
                                f'cursor:default !important; touch-action:pan-y !important; }} '
                                f'.st-key-{row_key} [data-testid="stHorizontalBlock"] {{ '
                                f'flex-direction:row !important; flex-wrap:nowrap !important; '
                                f'align-items:center !important; width:100% !important; max-width:100% !important; }} '
                                # Universele min-width:0-reset op ALLES binnen deze rij --
                                # dit was de ontbrekende schakel: min-width:0 op alleen de
                                # kolom zelf hielp niet, want Streamlit wrapt elke kolom nog
                                # in eigen tussenlagen (stVerticalBlock, element-container)
                                # die STANDAARD 'min-width:auto' hebben (weigeren te krimpen
                                # onder hun eigen inhoud) -- overflow-x:hidden verborg het
                                # gevolg daarvan (de knoppen) i.p.v. het echt op te lossen.
                                # min-width:0 op * is voor de vaste-breedte-elementen (logo,
                                # ticker, knoppen) onschadelijk -- die blijven vast dankzij
                                # hun eigen flex-shrink:0/expliciete breedte hieronder.
                                #
                                # Ook -webkit-user-drag:none + user-select:none op ALLES --
                                # de 'versleepbare rij'-bug kwam van de favicon-<img>: browsers
                                # maken afbeeldingen STANDAARD sleepbaar (draggable), ook zonder
                                # een expliciete draggable="true"-attribuut of drag-and-drop-
                                # library (die dit project sowieso niet gebruikt). Dat sleepte
                                # zichtbaar een 'schaduw' van de rij mee bij een touch/muis-
                                # gebaar. touch-action:pan-y op de rij zelf zorgt bovendien dat
                                # verticaal scrollen altijd gewoon soepel doorloopt i.p.v. dat
                                # een rij het gebaar als eigen gebeurtenis probeert te 'vangen'.
                                f'.st-key-{row_key} * {{ min-width:0 !important; '
                                f'-webkit-user-drag:none !important; user-select:none !important; }} '
                                # Kolom 1 (logo+naam): MOET krimpen (flex-1 min-w-0) zodat
                                # lange namen kunnen afkappen i.p.v. de rij breder te duwen
                                # dan het scherm.
                                f'.st-key-{row_key} [data-testid="column"]:first-child {{ '
                                f'display:flex !important; align-items:center !important; padding:0 !important; '
                                f'flex:1 1 0% !important; overflow:hidden !important; }} '
                                # Kolom 2/3 (klokje, prullenbak): vaste breedte, NOOIT
                                # krimpen (flex-shrink-0) -- blijven altijd volledig
                                # zichtbaar, strak rechts verankerd.
                                f'.st-key-{row_key} [data-testid="column"]:nth-child(2), '
                                f'.st-key-{row_key} [data-testid="column"]:nth-child(3) {{ '
                                f'display:flex !important; align-items:center !important; padding:0 !important; '
                                f'flex:0 0 auto !important; flex-shrink:0 !important; width:auto !important; }} '
                                f'.st-key-{row_key} [data-testid="stVerticalBlock"] {{ gap:0 !important; }} '
                                f'.st-key-{row_key} [data-testid="element-container"], '
                                f'.st-key-{row_key} [data-testid="stPopover"], '
                                f'.st-key-{row_key} [data-testid="stButton"] {{ '
                                f'margin:0 !important; padding:0 !important; }} '
                                f'</style>',
                                unsafe_allow_html=True,
                            )
                        with row_ctx:
                            try:
                                w_row_col1, w_row_col2, w_row_col3 = st.columns([9, 1.5, 1], gap="small")
                            except Exception:
                                w_row_col1, w_row_col2, w_row_col3 = st.columns([9, 1.5, 1])
                            with w_row_col1:
                                # Favicon via yfinance's eigen 'website'-veld i.p.v. een
                                # ticker-naar-domein-gok (die voor GOOG->'goog.com' of
                                # een future als 'GC=F' compleet onzinnig zou zijn) --
                                # ontbreekt 'website' (bv. bij futures/grondstoffen),
                                # dan een strakke letter-placeholder i.p.v. helemaal
                                # niets, zodat de tekst ernaast NOOIT verspringt.
                                try:
                                    website = get_cached_ticker_info(w["ticker"]).get("website")
                                except Exception:
                                    website = None
                                first_letter = w["naam"].strip()[0].upper() if w["naam"].strip() else "?"
                                # Logo-slot met EXACT vaste breedte/hoogte (28x28,
                                # ~ w-8/h-8) -- ongeacht of er een echt logo is of
                                # de letter-placeholder, dit blokje neemt altijd
                                # dezelfde ruimte in, dus de tekst ernaast staat
                                # altijd kaarsrecht onder elkaar.
                                if website:
                                    favicon_domain = website.replace("https://", "").replace("http://", "").split("/")[0]
                                    logo_html = (
                                        f'<div style="width:28px; height:28px; flex-shrink:0; display:flex; '
                                        f'align-items:center; justify-content:center;">'
                                        f'<img src="https://www.google.com/s2/favicons?domain={favicon_domain}&sz=32" '
                                        f'draggable="false" '
                                        f'style="width:18px; height:18px; border-radius:4px; -webkit-user-drag:none; '
                                        f'user-select:none; pointer-events:none;" '
                                        f'onerror="this.style.display=\'none\'"></div>'
                                    )
                                else:
                                    logo_html = (
                                        f'<div style="width:28px; height:28px; flex-shrink:0; border-radius:50%; '
                                        f'background:rgba(137,146,163,0.15); display:flex; align-items:center; '
                                        f'justify-content:center; font-size:0.68rem; font-weight:700; color:#8992A3; '
                                        f'font-family:\'Inter\', sans-serif !important;">{first_letter}</div>'
                                    )
                                # min-width:0 + flex:1 op de naam-span zelf (niet alleen
                                # op de buitenste rij-div) -- zonder dit weigert de flex-
                                # child te krimpen onder de volledige, niet-afgebroken
                                # naamlengte, wat de rij (en daarmee de hele pagina)
                                # breder duwde dan het scherm.
                                st.markdown(
                                    f'<div style="display:flex; align-items:center; gap:0.5rem; min-width:0; '
                                    f'width:100%;" title="{w["naam"]} ({w["ticker"]})">'
                                    f'{logo_html}'
                                    f'<div style="display:flex; flex-direction:column; justify-content:center; '
                                    f'min-width:0; flex:1 1 0%;">'
                                    f'<div style="color:#EAEDF1; font-weight:600; font-size:0.85rem; text-transform:uppercase; '
                                    f'letter-spacing:0.01em; font-family:\'Inter\', sans-serif !important; line-height:1.3; '
                                    f'overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{w["naam"].upper()}</div>'
                                    f'<div style="color:#8992A3; font-size:0.68rem; line-height:1.3; margin-top:1px; '
                                    f'overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{w["ticker"]}</div>'
                                    f'</div>'
                                    '</div>',
                                    unsafe_allow_html=True,
                                )
                            with w_row_col2:
                                has_alert = w.get("alert_target_price") is not None
                                # BELANGRIJKE FIX: de :material:-icoon-syntax hoort in de
                                # aparte 'icon'-parameter van st.popover(), NIET in het
                                # 'label' zelf -- het label ondersteunt volgens Streamlit's
                                # eigen documentatie alleen Bold/Italics/Links/Images, geen
                                # material-icon-syntax. Dat verklaarde waarom er nooit een
                                # bel-icoon verscheen (het label-materiaal werd genegeerd/
                                # kaal weergegeven, alleen de eigen chevron van de popover
                                # bleef zichtbaar).
                                # Ook gewrapt in st.container(key=...) -- een betrouwbare,
                                # bevestigd-werkende manier om deze specifieke knop te
                                # stylen: nu volledig plat (geen achtergrond/rand meer),
                                # alleen een zachte hover-opacity, i.p.v. een omlijnd
                                # vierkantje.
                                bell_wrap_key = f"watchlist_bell_wrap_{w['id']}"
                                try:
                                    bell_wrap_ctx = st.container(key=bell_wrap_key)
                                except Exception:
                                    bell_wrap_ctx = st.container()
                                    bell_wrap_key = None
                                if bell_wrap_key:
                                    st.markdown(
                                        f'<style>.st-key-{bell_wrap_key} button {{ '
                                        f'padding: 0.15rem 0.4rem !important; '
                                        f'min-width: 0 !important; min-height: 0 !important; '
                                        f'display: flex !important; align-items: center !important; '
                                        f'justify-content: center !important; gap: 0.2rem !important; '
                                        f'white-space: nowrap !important; '
                                        f'background:transparent !important; border:none !important; '
                                        f'box-shadow:none !important; opacity:0.75 !important; '
                                        f'transition:opacity 0.15s ease !important; }} '
                                        f'.st-key-{bell_wrap_key} button:hover {{ opacity:1 !important; '
                                        f'background:transparent !important; }}</style>',
                                        unsafe_allow_html=True,
                                    )
                                with bell_wrap_ctx:
                                    with st.popover(
                                        "",
                                        icon=":material/notifications_active:" if has_alert else ":material/notifications:",
                                        use_container_width=False,
                                    ):
                                        current_price = watchlist_market_data.get(w["ticker"], {}).get("current_price")
                                        if current_price is None:
                                            try:
                                                current_price = get_cached_ticker_info(w["ticker"]).get("regularMarketPrice")
                                            except Exception:
                                                current_price = None
                                        st.markdown(f"**Price alert for {w['naam']}**")
                                        if current_price is not None:
                                            st.caption(f"Current: {current_price:.2f}")
                                        if has_alert:
                                            direction_word = "drops to" if w.get("alert_direction") == "below" else "rises to"
                                            st.caption(f"Alert set: notify me when the price {direction_word} "
                                                      f"{w['alert_target_price']:.2f}")
                                        new_target_price = st.number_input(
                                            "Target price", min_value=0.0, step=0.5,
                                            value=float(w.get("alert_target_price") or 0.0),
                                            key=f"watchlist_alert_target_{w['id']}",
                                        )
                                        alert_btn_col1, alert_btn_col2 = st.columns(2)
                                        with alert_btn_col1:
                                            if st.button("Set alert", key=f"watchlist_set_alert_{w['id']}", type="primary",
                                                        disabled=(new_target_price <= 0 or current_price is None)):
                                                database.set_watchlist_alert(w["id"], user_email, new_target_price, current_price)
                                                st.rerun()
                                        with alert_btn_col2:
                                            if has_alert and st.button("Clear", key=f"watchlist_clear_alert_{w['id']}"):
                                                database.clear_watchlist_alert(w["id"], user_email)
                                                st.rerun()
                            with w_row_col3:
                                # Zelfde platte, borderloze behandeling als de
                                # bel-knop hierboven -- via een eigen
                                # container-key, want een kale st.button() zonder
                                # scope zou anders Streamlit's standaard,
                                # omlijnde knop-chrome behouden.
                                delete_wrap_key = f"watchlist_delete_wrap_{w['id']}"
                                st.markdown(
                                    f'<style>.st-key-{delete_wrap_key} button {{ '
                                    f'background:transparent !important; border:none !important; '
                                    f'box-shadow:none !important; color:#8992A3 !important; '
                                    f'opacity:0.75 !important; transition:opacity 0.15s ease !important; }} '
                                    f'.st-key-{delete_wrap_key} button:hover {{ opacity:1 !important; '
                                    f'background:transparent !important; }}</style>',
                                    unsafe_allow_html=True,
                                )
                                with st.container(key=delete_wrap_key):
                                    if st.button("", icon=":material/delete:", key=f"watchlist_delete_{w['id']}",
                                                help="Remove from watchlist"):
                                        database.delete_holding(w["id"], user_email)
                                        st.rerun()

                    half = (len(watchlist_items) + 1) // 2
                    left_items = watchlist_items[:half]
                    right_items = watchlist_items[half:]
                    # Streamlit voegt standaard ZELF al een verticale gap
                    # (~1rem) toe tussen gestapelde elementen binnen een
                    # kolom -- dat kwam bovenop de kaart-eigen margin-bottom,
                    # vandaar de te grote gaten. Deze wrapper-key dwingt die
                    # eigen Streamlit-gap hard naar 0.5rem (gap-y-2), exact
                    # gelijk aan de Rebalancing-grid hieronder aangepast.
                    _watchlist_grid_key = "watchlist_grid_wrap"
                    st.markdown(
                        f'<style>.st-key-{_watchlist_grid_key} [data-testid="stVerticalBlock"] {{ '
                        f'gap:0.5rem !important; }}</style>',
                        unsafe_allow_html=True,
                    )
                    with st.container(key=_watchlist_grid_key):
                        watchlist_outer_left, watchlist_outer_right = st.columns(2)
                        for row_idx in range(half):
                            with watchlist_outer_left:
                                _render_watchlist_row(left_items[row_idx], row_idx)
                            if row_idx < len(right_items):
                                with watchlist_outer_right:
                                    _render_watchlist_row(right_items[row_idx], row_idx)
                else:
                    st.caption("Your watchlist is empty.")

                st.markdown("<div style='height: 0.5rem'></div>", unsafe_allow_html=True)
                st.markdown(
                    '<div style="color:#64748B; font-size:10px; font-weight:700; letter-spacing:0.08em; '
                    'text-transform:uppercase; margin-bottom:0.75rem;">Add to watchlist</div>',
                    unsafe_allow_html=True,
                )
                # Zelfde flinterdunne, zachte rand + subtiele focus-state als
                # de invoervelden bij Log Transaction -- geen zware omlijning
                # meer op het zoekveld en de match-dropdown.
                _watchlist_search_key = "watchlist_search_wrap"
                st.markdown(
                    f'<style>'
                    f'.st-key-{_watchlist_search_key} div[data-baseweb="input"], '
                    f'.st-key-{_watchlist_search_key} div[data-baseweb="select"] > div {{ '
                    f'background:transparent !important; border:1px solid rgba(148,163,184,0.18) !important; '
                    f'box-shadow:none !important; }} '
                    f'.st-key-{_watchlist_search_key} div[data-baseweb="input"]:focus-within, '
                    f'.st-key-{_watchlist_search_key} div[data-baseweb="select"] > div:focus-within {{ '
                    f'border-color:rgba(31,174,150,0.45) !important; }} '
                    f'.st-key-{_watchlist_search_key} button {{ '
                    f'background:transparent !important; border:1px solid rgba(31,174,150,0.35) !important; '
                    f'color:#1FAE96 !important; font-weight:600 !important; padding:0.3rem 0.9rem !important; '
                    f'border-radius:6px !important; }} '
                    f'.st-key-{_watchlist_search_key} button:hover {{ background:rgba(31,174,150,0.12) !important; }} '
                    f'</style>',
                    unsafe_allow_html=True,
                )
                with st.container(key=_watchlist_search_key):
                    _dd_label("Search for a company, crypto, commodity, or precious metal")
                    watchlist_search = st.text_input(
                        "Search for a company, crypto, commodity, or precious metal", key="watchlist_search",
                        label_visibility="collapsed",
                    )
                    w_selected_symbol = None
                    w_selected_name = None
                    if watchlist_search:
                        try:
                            w_search_results = yf.Search(watchlist_search, max_results=8).quotes
                        except Exception as exc:
                            w_search_results = []
                            st.caption(f"Search failed: {exc}")
                        if w_search_results:
                            w_options = {}
                            for r in w_search_results:
                                name = r.get("shortname") or r.get("longname") or r.get("symbol")
                                label = f"{name} ({r.get('symbol')}) -- {r.get('exchange', '')}"
                                w_options[label] = r
                            w_chosen_label = st.selectbox("Choose the right match", list(w_options.keys()), key="watchlist_match")
                            w_chosen = w_options[w_chosen_label]
                            w_selected_symbol = w_chosen.get("symbol")
                            w_selected_name = w_chosen.get("shortname") or w_chosen.get("longname") or w_selected_symbol
                        else:
                            st.caption("No results found for this search -- try a different name.")

                    if w_selected_symbol and st.button("Add to watchlist"):
                        database.add_holding(user_email, w_selected_name, w_selected_symbol, is_watchlist=True)
                        st.success(f"{w_selected_name} ({w_selected_symbol}) added to watchlist!")
                        st.rerun()

    elif manage_section == "Delete portfolio":
        # Eigen, gelijkwaardig tabblad naast Import/Log transaction/
        # Watchlist -- deze actie is portfolio-breed (raakt zowel
        # geimporteerde als handmatig ingevoerde transacties), dus hoort
        # niet thuis onder 1 specifieke sub-actie zoals 'Import from
        # broker' of verstopt onder een checkbox bij 1 losse positie.
        # Geen eigen sectiekop hier -- de andere tabs (Import from
        # broker, Log transaction, Watchlist) hebben er ook geen; de
        # pagina-hoofdkop + de tab-balk zelf geven al genoeg context.
        st.markdown(
            '<div style="color:#64748B; font-size:10px; font-weight:700; letter-spacing:0.06em; '
            'text-transform:uppercase; margin-bottom:1.5rem;">This permanently deletes every position '
            'and its full transaction history, regardless of whether it was imported or logged '
            'manually. Your watchlist is not affected.</div>',
            unsafe_allow_html=True,
        )
        if not st.session_state.get("confirm_reset_all_holdings", False):
            _reset_all_btn_key = "reset_all_holdings_btn_wrap"
            st.markdown(
                f'<style>'
                f'.st-key-{_reset_all_btn_key} button {{ '
                f'display:block !important; text-align:left !important; '
                f'font-size:0.85rem !important; font-weight:700 !important; '
                f'color:#F1F5F9 !important; background:rgba(229,72,77,0.1) !important; '
                f'border:1px solid rgba(229,72,77,0.3) !important; border-radius:10px !important; '
                f'padding:0.6rem 1.2rem !important; height:auto !important; min-height:0 !important; '
                f'transition:all 0.2s ease !important; }} '
                f'.st-key-{_reset_all_btn_key} button:hover {{ '
                f'background:rgba(229,72,77,0.18) !important; border-color:rgba(229,72,77,0.5) !important; }} '
                f'</style>',
                unsafe_allow_html=True,
            )
            with st.container(key=_reset_all_btn_key):
                reset_all_clicked = st.button(
                    "Delete all my positions", key="reset_all_holdings_btn",
                )
            if reset_all_clicked:
                st.session_state["confirm_reset_all_holdings"] = True
                st.rerun()
        else:
            st.warning(
                "This will permanently delete ALL your positions and their full "
                "transaction history -- useful if you want to cleanly re-import "
                "everything after a data-precision fix. Your watchlist is not affected. "
                "This cannot be undone."
            )
            reset_confirm_col1, reset_confirm_col2 = st.columns(2)
            with reset_confirm_col1:
                if st.button("Yes, delete everything", key="confirm_reset_all_holdings_btn", type="primary"):
                    database.delete_all_holdings_and_transactions(user_email)
                    st.session_state["confirm_reset_all_holdings"] = False
                    st.success("All positions and transactions deleted -- you can now re-import cleanly under Import from broker.")
                    st.rerun()
            with reset_confirm_col2:
                if st.button("Cancel", key="cancel_reset_all_holdings_btn"):
                    st.session_state["confirm_reset_all_holdings"] = False
                    st.rerun()

def _render_unlock_premium_button(context_key: str, label: str = "Unlock all premium weekly signals \u2192") -> None:
    """
    'Unlock all premium weekly signals' -- st.button() + st.switch_page()
    i.p.v. een kale <a href="/login">-tag. Een rauwe <a>-tag wordt door de
    browser als een VOLLEDIGE paginaherlading behandeld (wit scherm,
    traag) omdat Streamlit's eigen frontend die niet onderschept -- een
    'echte' Streamlit-widget zoals deze GEBRUIKT Streamlit's bestaande
    websocket-verbinding, dus geen page-reload, geen flikkering.
    st.switch_page() heeft als bonus t.o.v. st.page_link() dat we EERST
    st.session_state kunnen zetten (welke tab -- Sign In/Sign Up -- de
    inlogpagina straks moet tonen) voordat de navigatie plaatsvindt --
    dat kan met st.page_link() niet, die ondersteunt geen query-params
    of on_click. 'label' is per-context aanpasbaar (bv. een andere tekst
    onder Earnings Surprises dan onder Snowballers/Rocket List).
    """
    btn_key = f"unlock_premium_btn_{context_key}"
    st.markdown(
        f'<style>'
        f'.st-key-{btn_key} button {{ '
        f'display:inline-block !important; color:#34D399 !important; font-size:0.72rem !important; '
        f'font-weight:600 !important; letter-spacing:0.05em !important; text-transform:uppercase !important; '
        f'background:transparent !important; border:1px solid rgba(51,65,85,0.7) !important; '
        f'border-radius:8px !important; padding:0.4rem 1rem !important; width:auto !important; '
        f'box-shadow:none !important; }} '
        f'.st-key-{btn_key} button:hover {{ '
        f'border-color:rgba(52,211,153,0.5) !important; background:transparent !important; }} '
        f'</style>',
        unsafe_allow_html=True,
    )
    with st.container(key=btn_key):
        if st.button(label, key=f"unlock_premium_{context_key}"):
            st.session_state["login_prefill_mode"] = "Sign Up"
            st.switch_page(login_page)


def _render_discover_signup_form() -> None:
    """
    HET ene, centrale e-mail-activatieblok -- staat nu 1x, als grote
    afsluiter helemaal onderaan de Discover-pagina (na Rocket List),
    i.p.v. verspreid onder elke screener (2 volledige formulieren zo
    kort na elkaar oogde druk/rommelig). Onder Momentocrats/Snowballers
    staat nu alleen nog een subtiele teaser-link die hier met een
    smooth-scroll naartoe verwijst (zie 'html { scroll-behavior:smooth }'
    in de globale stylesheet + de '#activate-signals'-anchor hieronder).

    3-op-1-rij (e-mail, tijdzone, knop) op desktop via st.columns() --
    Streamlit's eigen kolommen stapelen dit al automatisch netjes onder
    elkaar op mobiel, geen aparte media-query nodig.

    Regio-keuze bewust BEHOUDEN -- die bepaalt in welke tijdzone de
    dagelijkse e-mail aankomt, een functionele noodzaak, geen decoratie.
    """
    import database as _database_for_optin

    st.markdown(
        '<div id="activate-signals" style="scroll-margin-top:80px; text-align:left; '
        'padding:1.5rem 0 0.75rem 0; max-width:640px; width:100%; margin:0; '
        'box-sizing:border-box; overflow-x:hidden;">'
        '<div style="color:#CBD5E1; font-size:0.85rem; font-weight:600; letter-spacing:0.04em; '
        'text-transform:uppercase; line-height:1.6;">'
        '&#128235; Activate daily Momentocrats alerts: get the full list of fresh bullish '
        'flips in your inbox every weekday morning.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    form_key = "discover_signup_form_wrap"
    st.markdown(
        f'<style>'
        f'.st-key-{form_key} {{ max-width:640px !important; margin:0 !important; }} '
        # Volledig, breed resetten van ALLES binnen de select/input-
        # wrapper -- de vorige selector (alleen '> div', 1 niveau) raakte
        # een verkeerd, te diep genest binnen-element van BaseWeb's
        # select-component (vandaar het losse groene blokje om alleen de
        # pijltjes-chevron, met de tekst 'Choose timezone' kaal ernaast).
        # Nu ELK niveau binnen de select hard getransparant + van dezelfde
        # buitenrand voorzien, zodat de HELE box er als 1 samenhangend
        # geheel uitziet, ongeacht hoeveel binnenlagen BaseWeb gebruikt.
        f'.st-key-{form_key} div[data-baseweb="input"], '
        f'.st-key-{form_key} div[data-baseweb="select"], '
        f'.st-key-{form_key} div[data-baseweb="select"] > div, '
        f'.st-key-{form_key} div[data-baseweb="select"] div {{ '
        f'background:transparent !important; box-shadow:none !important; border:none !important; }} '
        f'.st-key-{form_key} div[data-baseweb="input"], '
        f'.st-key-{form_key} div[data-baseweb="select"] > div {{ '
        f'border:1px solid rgba(148,163,184,0.25) !important; border-radius:8px !important; }} '
        f'.st-key-{form_key} div[data-baseweb="input"]:focus-within, '
        f'.st-key-{form_key} div[data-baseweb="select"] > div:focus-within {{ '
        f'border-color:rgba(31,174,150,0.6) !important; }} '
        f'.st-key-{form_key} div[data-baseweb="select"] span {{ color:#EAEDF1 !important; }} '
        # Regio-dropdown krijgt een gegarandeerde minimumbreedte -- de
        # tekst 'Choose timezone' werd anders afgekapt tot 'Choose time'
        # zodra de kolom smaller werd dan de tekst zelf nodig had.
        f'.st-key-{form_key} [data-testid="column"]:nth-child(2) {{ '
        f'min-width:220px !important; flex:0 0 auto !important; }} '
        # Premium knop: solide teal-vulling, geen harde rand, zachte
        # hover, subtiele schaduw voor wat 'diepte' -- consistent met de
        # andere primaire actieknoppen op het platform. Padding nu exact
        # gelijk aan de rest van het platform (py-2 px-5).
        f'.st-key-{form_key} button {{ '
        f'background:#1FAE96 !important; color:#0B1210 !important; font-weight:700 !important; '
        f'font-size:0.9rem !important; border:none !important; border-radius:8px !important; '
        f'padding:0.5rem 1.25rem !important; width:auto !important; white-space:nowrap !important; '
        f'box-shadow:0 1px 3px rgba(0,0,0,0.3) !important; transition:background 0.15s ease !important; }} '
        f'.st-key-{form_key} button:hover {{ background:#24C7AB !important; }} '
        f'.st-key-{form_key} button:active {{ background:#189E88 !important; }} '
        f'.st-key-{form_key} [data-testid="stHorizontalBlock"] {{ '
        f'align-items:center !important; gap:1.25rem !important; flex-wrap:wrap !important; }} '
        f'.st-key-{form_key} [data-testid="column"]:last-child, '
        f'.st-key-{form_key} [data-testid="column"]:nth-child(3) {{ '
        f'flex:0 0 auto !important; width:auto !important; min-width:0 !important; }} '
        f'</style>',
        unsafe_allow_html=True,
    )
    try:
        form_ctx = st.container(key=form_key)
    except Exception:
        form_ctx = st.container()
    with form_ctx:
        email_col, region_col, button_col = st.columns([2.2, 2, 1.3], gap="medium")
        with email_col:
            form_email = st.text_input(
                "Email address", placeholder="you@example.com",
                key="discover_signup_email", label_visibility="collapsed",
            )
        with region_col:
            form_region_raw = st.selectbox(
                "Region", ["Choose timezone", "EU", "US_East", "US_West"],
                format_func=lambda x: x.replace("_", " "),
                key="discover_signup_region", label_visibility="collapsed",
            )
        with button_col:
            form_submitted = st.button(
                "Activate Free Signals", key="discover_signup_submit",
            )

    if form_submitted:
        if not form_email or "@" not in form_email:
            st.error("Please enter a valid email address.")
        elif form_region_raw == "Choose timezone":
            st.error("Please choose your timezone.")
        else:
            confirmation_token, unsubscribe_token = _database_for_optin.add_email_subscriber(form_email, form_region_raw)
            send_subscription_confirmation_email(form_email, confirmation_token, unsubscribe_token)
            st.success("Almost there! Check your inbox to confirm your subscription.")


def render_discover_dispatcher():
    """
    Router voor de Discover-pagina. Niet-ingelogde bezoekers behouden de
    volledige, ongewijzigde scrollende storytelling-flow (render_discover_
    signals() zelf regelt daar alles al voor -- geen pills, geen frictie).
    Ingelogde gebruikers krijgen in plaats daarvan een horizontale pills-
    balk direct onder de hoofdsectiekop, die flitsloos (puur via
    session_state, geen st.switch_page/page-reload) tussen de 3 secties
    wisselt.
    """
    if not current_user.is_logged_in:
        # Volledige, vloeiend scrollende storytelling-flow: alle 3
        # secties op DEZELFDE pagina, direct onder elkaar -- geen pills,
        # geen navigatie-frictie. render_discover_sectors_themes() en
        # render_discover_earnings_surprises() regelen zelf al hun eigen
        # soft-lock/blur-gedrag voor niet-ingelogde bezoekers (dat
        # bestond al), dus die kunnen hier gewoon 1-op-1 hergebruikt
        # worden mét hun eigen kop (render_own_header=True, de default).
        render_discover_signals()
        st.markdown("<div style='height:3rem'></div>", unsafe_allow_html=True)
        render_discover_sectors_themes()
        st.markdown("<div style='height:3rem'></div>", unsafe_allow_html=True)
        render_discover_earnings_surprises()
        return

    st.markdown(
        _uniform_section_header_html("Discover", "search", is_first=True),
        unsafe_allow_html=True,
    )
    if "active_sub_section_discover" not in st.session_state:
        st.session_state["active_sub_section_discover"] = "SIGNATURE SIGNALS"
    sub_choice = st.pills(
        "Discover section",
        ["SIGNATURE SIGNALS", "SECTORS & THEMES", "EARNINGS SURPRISES"],
        key="active_sub_section_discover", label_visibility="collapsed",
    )
    st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)

    if sub_choice == "SECTORS & THEMES":
        render_discover_sectors_themes(render_own_header=False)
    elif sub_choice == "EARNINGS SURPRISES":
        render_discover_earnings_surprises(render_own_header=False)
    else:
        render_discover_signals()


def render_discover_signals():
    # --- Marketing-first opening: GEEN 'Discover'-sectiekop meer bovenaan --
    # de grote titel hieronder ("Your Investing Edge, Built Around You.")
    # IS zelf al de sterkste binnenkomer. HET ene, centrale e-mail-
    # activatieblok staat helemaal onderaan de pagina (zie
    # _render_discover_signup_form(), na Rocket List) -- onder
    # Momentocrats/Snowballers/Rocket List staat alleen nog een subtiele
    # teaser-link/knop ernaartoe. De sub-navigatie (Sectors & Themes,
    # Earnings Surprises) is verhuisd naar de zijbalk als eigen pagina's
    # -- geen in-page tab-rij meer die uitgelogde bezoekers afleidde van
    # de daadwerkelijke, bewijzende data.
    if not current_user.is_logged_in:
        st.markdown(
            '<style>'
            '.discover-hero { text-align:left; padding:0.5rem 0 0; width:100%; '
            'max-width:100%; box-sizing:border-box; overflow-x:hidden; margin-bottom:2rem; }'
            '.discover-hero-buttons { margin-top:1.5rem; display:flex; flex-direction:row; '
            'gap:1rem; justify-content:flex-start; align-items:center; width:100%; '
            'box-sizing:border-box; }'
            '.discover-hero-btn { font-weight:600 !important; font-size:0.875rem !important; '
            'padding:0.625rem 1.5rem !important; border-radius:10px !important; '
            'text-decoration:none !important; box-sizing:border-box !important; text-align:center !important; '
            'line-height:1.2 !important; white-space:nowrap !important; display:inline-block !important; }'
            '.discover-hero-btn-primary, .discover-hero-btn-primary:link, .discover-hero-btn-primary:visited {'
            'background:#1FAE96 !important; color:#0B111E !important; border:none !important; }'
            '.discover-hero-btn-secondary, .discover-hero-btn-secondary:link, .discover-hero-btn-secondary:visited {'
            'background:transparent !important; color:#EAEDF1 !important; '
            'border:1px solid rgba(148,163,184,0.35) !important; }'
            '@media (max-width:768px) { '
            '.discover-hero-buttons { flex-direction:column; align-items:stretch; width:100%; '
            'gap:0.75rem; padding:0 1rem; } '
            '.discover-hero-btn { width:100%; white-space:normal; } '
            '} '
            '</style>'
            '<div id="hero-top" class="discover-hero">'
            '<div style="color:#F8FAFC; font-size:1.75rem; font-weight:800; text-transform:uppercase; '
            'letter-spacing:0.01em; line-height:1.3;">Your Investing Edge,<br>'
            '<span style="color:#1FAE96;">Built Around You.</span></div>'
            '<div class="discover-hero-buttons">'
            '<a href="#activate-signals" target="_self" class="discover-hero-btn discover-hero-btn-primary">'
            'Start free, in seconds &rarr;</a>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )


    st.markdown(
        _uniform_section_header_html("Signature Signals", "sensors", is_first=False),
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <style>
        .signature-signals-line {{ font-size: 0.72rem; }}
        @media (min-width: 768px) {{ .signature-signals-line {{ font-size: 0.85rem !important; }} }}
        </style>
        <div id="signals" style="scroll-margin-top: 80px; background: rgba(2,6,23,0.4);
                    border: 1px solid rgba(15,23,42,0.6); border-radius: 14px;
                    padding: 1.25rem; margin: 0.5rem 0 0.75rem 0;">
            <span style="color:#64748B; font-size:0.68rem; font-weight:600; letter-spacing:0.05em; text-transform:uppercase; margin-bottom:1rem; display:block;">
                3 specially-built signals, each with its own investing style. This is the core of Hesty's.
            </span>
            <p class="signature-signals-line" style="margin:0; padding:0; color:#94A3B8; line-height:1.9;">
                <span style="color:#F1F5F9; font-weight:700; text-transform:uppercase;">&#128225; Momentocrats:</span> Identifies high-quality stocks trading bullish today.
            </p>
            <p class="signature-signals-line" style="margin:0; padding:0; color:#94A3B8; line-height:1.9;">
                <span style="color:#F1F5F9; font-weight:700; text-transform:uppercase;">&#127811; Snowballers:</span> Finds premium, compounding assets at an attractive discount.
            </p>
            <p class="signature-signals-line" style="margin:0; padding:0; color:#94A3B8; line-height:1.9;">
                <span style="color:#F1F5F9; font-weight:700; text-transform:uppercase;">&#128640; Rocket List:</span> Spots accelerating revenue growth for high-conviction bets.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    def _email_pref_link(label: str):
        """Simpele verwijzing naar Settings om deze e-mail-voorkeur te beheren (i.p.v. een losse toggle hier)."""
        st.caption(f"{label} Manage in:")
        st.page_link(settings_page, label="Settings")

    def _next_weekly_scan_time() -> str:
        """Berekent het volgende geplande wekelijkse-scan-moment (zaterdag 07:00 UTC)."""
        now = datetime.now(timezone.utc)
        days_ahead = (5 - now.weekday()) % 7  # maandag=0 ... zaterdag=5
        if days_ahead == 0 and now.hour >= 7:
            days_ahead = 7  # het is al zaterdag na 07:00 UTC -> volgende week
        next_date = (now + timedelta(days=days_ahead)).replace(hour=7, minute=0, second=0, microsecond=0)
        return next_date.strftime("%Y-%m-%d %H:%M UTC")

    if current_user.is_logged_in:
        import database
        _current_prefs = database.get_user_preferences(current_user.email)
        _is_premium_discover = database.is_premium_user(current_user.email)
    else:
        _current_prefs = {}
        # Discover vereist bewust geen login -- maar tijdens de 'iedereen
        # premium'-testfase moet dat OOK voor niet-ingelogde bezoekers
        # gelden, niet alleen voor wie toevallig al is ingelogd.
        try:
            _is_premium_discover = st.secrets.get("app", {}).get("premium_free_for_all", False)
        except Exception:
            _is_premium_discover = False
    _signal_display_limit = None if _is_premium_discover else 3  # None = pandas .head(None) geeft alles terug

    # --- Momentocrats (bestaande, ongewijzigde signaal-logica) ---
    st.markdown(
        _uniform_section_header_html("Momentocrats", "sensors", is_first=False),
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="color:#64748B; font-size:10px; font-weight:700; letter-spacing:0.08em; '
        'text-transform:uppercase; margin-bottom:0.75rem; font-family:\'Inter\', sans-serif !important;">'
        'Technical momentum + fundamental quality, combined. Best for swing trades (days-weeks).</div>',
        unsafe_allow_html=True,
    )

    # st.segmented_control i.p.v. de eerdere URL-link-toggle -- die
    # laatste veroorzaakte een VOLLEDIGE paginaherlading (via
    # <a href="?...">), waardoor de expander steeds weer dichtklapte.
    # Een native widget zoals deze blijft BINNEN de Streamlit-sessie
    # (geen page-reload), dus de expander-status blijft nu intact.
    # Vlakke, minimalistische stijl -- zelfde patroon als de sub-tabs
    # bovenaan de pagina en de Daily/All-time-toggle op Portfolio --
    # i.p.v. de eerdere felle groene omlijning. Ook voor niet-ingelogde
    # bezoekers zichtbaar -- zonder deze toggle is de Weekly-variant van
    # Momentocrats voor hen niet te zien, dus deze blijft voor iedereen.
    _momentum_tf_key = "momentocrats_timeframe_wrap"
    st.markdown(
        f'<style>'
        f'.st-key-{_momentum_tf_key} div[data-testid="stSegmentedControl"] {{ '
        f'border:none !important; background:transparent !important; box-shadow:none !important; }} '
        f'.st-key-{_momentum_tf_key} div[data-testid="stSegmentedControl"] button, '
        f'.st-key-{_momentum_tf_key} div[data-testid="stSegmentedControl"] label {{ '
        f'border:none !important; outline:none !important; box-shadow:none !important; '
        f'background:transparent !important; color:#8992A3 !important; font-weight:600 !important; }} '
        f'.st-key-{_momentum_tf_key} div[data-testid="stSegmentedControl"] button[aria-pressed="true"], '
        f'.st-key-{_momentum_tf_key} div[data-testid="stSegmentedControl"] label[data-checked="true"] {{ '
        f'background:rgba(31,174,150,0.15) !important; color:#1FAE96 !important; border:none !important; }} '
        f'</style>',
        unsafe_allow_html=True,
    )
    with st.container(key=_momentum_tf_key):
        current_timeframe = st.segmented_control(
            "Timeframe", options=["Daily", "Weekly"], selection_mode="single",
            default="Daily", key="momentocrats_timeframe", label_visibility="collapsed",
        )
    if current_timeframe is None:  # kan gebeuren als je 'm handmatig deselecteert
        current_timeframe = "Daily"
    csv_file = "supertrend_signals_daily.csv" if current_timeframe == "Daily" else "supertrend_signals.csv"

    df_screener = load_screener_data(csv_file)
    if df_screener is None or df_screener.empty:
        st.info("No results yet -- check back after the next scheduled scan.")
    else:
        df_screener = df_screener.sort_values("score", ascending=False)

        # Weergave-drempel op 7.5 (i.p.v. 8.0) -- op verzoek ook de
        # 'net iets minder dan 8, maar nog steeds sterk'-signalen
        # tonen. De ⭐-ster (verderop, bij standout=row["score"]>=8.0)
        # blijft WEL op 8.0 staan -- die markeert specifiek de écht
        # uitzonderlijke signalen, 7.5-7.9 wordt dus wel getoond maar
        # zonder ster. Een max-cap (_STANDOUT_DISPLAY_CAP) blijft als
        # vangnet voor het (zeldzame) geval dat er heel veel
        # kwalificerende signalen in 1 week zijn.
        standouts = df_screener[df_screener["score"] >= 7.5]
        total_matching = len(df_screener)
        if not standouts.empty:
            filtered = standouts.head(_STANDOUT_DISPLAY_CAP)
            caption_intro = f"{len(filtered)} standout signal(s) (score 7.5+) of {total_matching} total matches"
        else:
            # Geen enkele standout deze scan -- toch de top 3 tonen i.p.v.
            # de sectie helemaal leeg te laten ogen.
            filtered = df_screener.head(3)
            caption_intro = f"No score-7.5+ standouts right now | showing the top {len(filtered)} of {total_matching} matches"

        # Kaarten i.p.v. een brede tabel (voorheen 13+ kolommen --
        # dat dwingt op mobiel dubbel scrollen af, verticaal EN
        # horizontaal). 'Weeks ago'/'Days ago' verschilt per
        # tijdvenster (weekly.csv heeft weken_geleden, daily.csv
        # heeft dagen_geleden) -- beide velden afgehandeld.
        cards_html = []
        for _, row in filtered.iterrows():
            secondary = []
            if "dagen_geleden" in row.index and pd.notna(row.get("dagen_geleden")):
                secondary.append(("Flipped", f"{int(row['dagen_geleden'])}d ago"))
            elif "weken_geleden" in row.index and pd.notna(row.get("weken_geleden")):
                secondary.append(("Flipped", f"{int(row['weken_geleden'])}w ago"))
            if pd.notna(row.get("sinds_omslag_pct")):
                secondary.append(("Since flip", f"{row['sinds_omslag_pct']:+.1f}%"))
            if pd.notna(row.get("roic_pct")):
                secondary.append(("ROIC", f"{row['roic_pct']:+.1f}%"))
            if pd.notna(row.get("relatieve_sterkte")):
                secondary.append(("Rel. strength", f"{row['relatieve_sterkte']:+.1f}%"))
            cards_html.append(_signal_card_html(
                row["ticker"], "Score (out of 10)", f"{row['score']:.1f}", True, secondary,
                standout=row["score"] >= 8.0,
            ))
        _render_signal_cards(cards_html)
        # Voor niet-ingelogde bezoekers: een subtiele teaser-link i.p.v.
        # een compleet 2e formulier hier (2 volledige e-mailformulieren
        # zo kort na elkaar oogde druk) -- verwijst naar het ENE, grote
        # centrale formulier onderaan de pagina (zie
        # _render_discover_signup_form(), na Rocket List). Alleen
        # getoond als er daadwerkelijk meer te unlocken valt.
        if not current_user.is_logged_in:
            _remaining_momentocrats = max(total_matching - (_signal_display_limit or 0), 0)
            if _remaining_momentocrats > 0:
                st.markdown(
                    '<a href="#activate-signals" target="_self" class="discover-teaser-link">'
                    'Activate daily alerts &rarr;</a>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(_signal_status_line_html(caption_intro, csv_file), unsafe_allow_html=True)
            if _signal_display_limit is not None and total_matching > _signal_display_limit and not _is_premium_discover:
                st.info(f"Showing the top {_signal_display_limit} of {total_matching} matching signals. "
                        f"Upgrade to Premium to see all {total_matching}.", icon=":material/lock:")

    # --- Snowball Signal (nieuw, wekelijks-only: kwaliteit + goede prijs) ---
    st.markdown(
        _uniform_section_header_html("Snowballers", "savings", is_first=False),
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="color:#64748B; font-size:10px; font-weight:700; letter-spacing:0.08em; '
        'text-transform:uppercase; margin-bottom:0.75rem;">Quality companies trading below fair '
        'value, with low volatility.</div>',
        unsafe_allow_html=True,
    )
    if os.path.exists("snowball_signals.csv"):
        df_snowball = pd.read_csv("snowball_signals.csv")
        if not df_snowball.empty:
            df_snowball = df_snowball.sort_values("afwijking_fair_value_pct", ascending=True)
            total_snowball = len(df_snowball)

            # Alleen de STANDOUT-resultaten (20%+ onder fair value)
            # standaard tonen i.p.v. simpelweg de top-N -- zelfde reden
            # als bij Momentocrats: voorkomt een eindeloze muur kaarten
            # bij veel wekelijkse matches.
            snowball_standouts = df_snowball[df_snowball["afwijking_fair_value_pct"] <= -20.0]
            if not snowball_standouts.empty:
                df_snowball = snowball_standouts.head(_STANDOUT_DISPLAY_CAP)
                snowball_caption_intro = f"{len(df_snowball)} standouts over 20% below fair value | {total_snowball} total matches"
            else:
                df_snowball = df_snowball.head(3)
                snowball_caption_intro = f"No 20%+ standouts right now | showing the top {len(df_snowball)} of {total_snowball} matches"

            # Kaarten i.p.v. tabel. Kleur BEWUST omgekeerd t.o.v. de
            # gebruikelijke +/- logica: een NEGATIEVE afwijking van
            # fair value betekent 'goedkoper dan terecht' -- precies
            # wat je wil bij dit signaaltype, dus GROEN, niet rood.
            # Standout (ster) bij 20%+ onder fair value -- de écht
            # opvallende koopjes.
            cards_html = []
            for _, row in df_snowball.iterrows():
                secondary = []
                if pd.notna(row.get("roic_pct")):
                    secondary.append(("ROIC", f"{row['roic_pct']:+.1f}%"))
                if pd.notna(row.get("volatiliteit_pct")):
                    secondary.append(("Volatility", f"{row['volatiliteit_pct']:.1f}%"))
                if pd.notna(row.get("prijs_nu")):
                    secondary.append(("Price", f"{row['prijs_nu']:.2f}"))
                cards_html.append(_signal_card_html(
                    row["ticker"], "Vs fair value", f"{row['afwijking_fair_value_pct']:+.1f}%",
                    row["afwijking_fair_value_pct"] < 0, secondary,
                    standout=row["afwijking_fair_value_pct"] <= -20.0,
                ))
            _render_signal_cards(cards_html, blur_from_index=(1 if not current_user.is_logged_in else None))
            if not current_user.is_logged_in:
                _remaining_snowballers = max(total_snowball - (_signal_display_limit or 0), 0)
                if _remaining_snowballers > 0:
                    _render_unlock_premium_button("snowballers")
            else:
                st.markdown(
                    _signal_status_line_html(snowball_caption_intro, "snowball_signals.csv"),
                    unsafe_allow_html=True,
                )
                if _signal_display_limit is not None and total_snowball > _signal_display_limit and not _is_premium_discover:
                    st.info(f"Showing the top {_signal_display_limit} of {total_snowball} matching stocks. "
                            f"Upgrade to Premium to see all {total_snowball}.", icon=":material/lock:")
        else:
            st.caption("No stocks currently meet the Snowballers criteria.")
    else:
        st.caption("No data yet -- this updates once a week via the scheduled scan.")

    # --- Rocket List (nieuw, wekelijks-only: versnellende groei + momentum) ---
    st.markdown(
        _uniform_section_header_html("Rocket List", "rocket_launch", is_first=False),
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="color:#64748B; font-size:10px; font-weight:700; letter-spacing:0.08em; '
        'text-transform:uppercase; margin-bottom:0.75rem; font-family:\'Inter\', sans-serif !important;">'
        'Accelerating growth stocks with strong momentum. For investors comfortable with more risk '
        'in exchange for growth potential.</div>',
        unsafe_allow_html=True,
    )
    if os.path.exists("rocket_list_signals.csv"):
        df_rocket = pd.read_csv("rocket_list_signals.csv")
        if not df_rocket.empty:
            df_rocket = df_rocket.sort_values("groei_pct", ascending=False)
            total_rocket = len(df_rocket)

            # Alleen de STANDOUT-resultaten (25%+ groei) standaard tonen
            # i.p.v. simpelweg de top-N -- exact het gemelde probleem
            # (soms 50-60+ matches, een eindeloze muur op mobiel).
            rocket_standouts = df_rocket[df_rocket["groei_pct"] >= 25.0]
            if not rocket_standouts.empty:
                df_rocket = rocket_standouts.head(_STANDOUT_DISPLAY_CAP)
                rocket_caption_intro = f"{len(df_rocket)} standouts over 25% growth | {total_rocket} total matches"
            else:
                df_rocket = df_rocket.head(3)
                rocket_caption_intro = f"No 25%+ standouts right now | showing the top {len(df_rocket)} of {total_rocket} matches"

            # Standout (ster) bij 25%+ groei -- de écht opvallende
            # versnellers.
            cards_html = []
            for _, row in df_rocket.iterrows():
                secondary = []
                if pd.notna(row.get("relatieve_sterkte")):
                    secondary.append(("Rel. strength", f"{row['relatieve_sterkte']:+.1f}%"))
                if pd.notna(row.get("prijs_nu")):
                    secondary.append(("Price", f"{row['prijs_nu']:.2f}"))
                cards_html.append(_signal_card_html(
                    row["ticker"], "Growth", f"{row['groei_pct']:+.1f}%", True, secondary,
                    standout=row["groei_pct"] >= 25.0,
                ))
            _render_signal_cards(cards_html, blur_from_index=(1 if not current_user.is_logged_in else None))
            if not current_user.is_logged_in:
                _remaining_rocket = max(total_rocket - (_signal_display_limit or 0), 0)
                if _remaining_rocket > 0:
                    _render_unlock_premium_button("rocket_list")
            else:
                st.markdown(
                    _signal_status_line_html(
                        rocket_caption_intro, "rocket_list_signals.csv",
                        extra=f"Next update: {_next_weekly_scan_time()}",
                    ),
                    unsafe_allow_html=True,
                )
                if _signal_display_limit is not None and total_rocket > _signal_display_limit and not _is_premium_discover:
                    st.info(f"Showing the top {_signal_display_limit} of {total_rocket} matching stocks. "
                            f"Upgrade to Premium to see all {total_rocket}.", icon=":material/lock:")
        else:
            st.caption("No stocks currently meet the Rocket List criteria.")
    else:
        st.caption("No data yet -- this updates once a week via the scheduled scan.")

    # --- HET ene, centrale e-mail-activatieblok -- de grote afsluiter
    # van de Discover-pagina voor niet-ingelogde bezoekers, na alle 3
    # de screeners. De teaser-links onder Momentocrats/Snowballers
    # scrollen hier met een smooth-scroll naartoe. ---
    if not current_user.is_logged_in:
        _render_discover_signup_form()
    else:
        # 'Manage in: Settings' is alleen zinvol voor een ingelogde
        # gebruiker (die HEEFT immers toegang tot Settings) -- voor een
        # niet-ingelogde bezoeker is dit een verwarrende, dode link naar
        # een pagina die 'ie nog niet kan bereiken.
        st.divider()
        _email_pref_link("Want this weekly by email?")



def render_discover_sectors_themes(render_own_header: bool = True):
    # --- Sector rotation -- geen expander meer: content staat gewoon
    # altijd zichtbaar op de pagina (scrollend), zoals moderne sites
    # dit doen -- een accordion voegde hier geen overzicht toe, het
    # verstopte 'm juist onnodig achter een klik.
    if render_own_header:
        st.markdown(
            _uniform_section_header_html("Sectors & Themes", "sync", is_first=True),
            unsafe_allow_html=True,
        )
    st.caption("Which sectors are relatively strong or weak right now (1-month trailing).")
    region = st.segmented_control(
        "Region", options=["US", "EU"], selection_mode="single",
        default="US", key="sector_region", label_visibility="collapsed",
    )
    if region is None:
        region = "US"
    with st.spinner("Checking sector performance..."):
        rotation = build_sector_rotation(region=region)
    if rotation:
        _render_rotation_tiles(rotation, "sector")
    else:
        st.caption("No sector data available right now.")

    st.markdown(
        '<div style="font-size:0.72rem; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; '
        'color:#94A3B8; margin-top:1.5rem; margin-bottom:0.5rem;">Trend</div>',
        unsafe_allow_html=True,
    )
    st.caption("A line crossing zero is a rotation signal.")
    with st.spinner("Building trend chart..."):
        rotation_trend = build_sector_rotation_trend(region=region)
    if rotation_trend:
        all_trend_sectors = list(rotation_trend.keys())
        # Standaard: de top-5 op basis van het HUIDIGE (laatste) rendement --
        # voorkomt dat de grafiek meteen met alle 11 lijnen chaotisch oogt.
        default_sectors = sorted(
            all_trend_sectors, key=lambda s: rotation_trend[s]["values"][-1], reverse=True
        )[:5]
        st.markdown(
            '<div style="font-size:0.72rem; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; '
            'color:#94A3B8; margin-top:1.5rem; margin-bottom:0.5rem;">Sectors to compare</div>',
            unsafe_allow_html=True,
        )
        selected_sectors = st.multiselect(
            "Sectors to compare", all_trend_sectors, default=default_sectors, key="sector_trend_selection",
            label_visibility="collapsed",
        )
        if selected_sectors:
            trend_fig = go.Figure()
            trend_palette = [
                "#1FAE96", "#E8A93C", "#E5484D", "#3ED9C4", "#8992A3",
                "#5AC8B0", "#F5C518", "#C77DFF", "#4DA6FF", "#FF8A5C", "#B0E0D8",
            ]
            for i, sector in enumerate(selected_sectors):
                series = rotation_trend[sector]
                trend_fig.add_trace(go.Scatter(
                    x=series["dates"], y=series["values"], mode="lines", name=sector,
                    line=dict(color=trend_palette[i % len(trend_palette)], width=2),
                    hovertemplate="%{x}: %{y:+.1f}%<extra>" + sector + "</extra>",
                ))
            trend_fig.add_hline(y=0, line_dash="dash", line_color="#8992A3", line_width=1)
            trend_fig.update_layout(
                yaxis_title="Trailing 1-month return (%)",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, sans-serif", color="#EAEDF1", size=11),
                legend=dict(orientation="h", yanchor="top", y=-0.15, font=dict(size=10)),
                margin=dict(t=10, b=10, l=10, r=10),
                height=420,
                xaxis=dict(gridcolor="rgba(137,146,163,0.15)"),
                yaxis=dict(gridcolor="rgba(137,146,163,0.15)"),
            )
            st.plotly_chart(trend_fig, width="stretch")
        else:
            st.caption("Select at least 1 sector above to see the trend chart.")
    else:
        st.caption("No trend data available right now.")

    # --- Themes -- geen expander meer, zelfde reden als Sector rotation
    # hierboven. Apart van de officiële GICS-sectoren gehouden (anders
    # zou een bedrijf dubbel meetellen). ---
    st.markdown(
        _uniform_section_header_html("Themes", "lightbulb", is_first=False),
        unsafe_allow_html=True,
    )
    st.caption("How popular investing themes are doing right now (1-month trailing).")
    with st.spinner("Checking theme performance..."):
        theme_rotation = build_theme_rotation()
    if theme_rotation:
        _render_rotation_tiles(theme_rotation, "theme")
    else:
        st.caption("No theme data available right now.")

    st.markdown("**Trend**")
    st.caption("A line crossing zero is a rotation signal.")
    with st.spinner("Building trend chart..."):
        theme_trend = build_theme_rotation_trend()
    if theme_trend:
        all_trend_themes = list(theme_trend.keys())
        # Nu er 11 thema's zijn (was 5), standaard de top-5 op basis
        # van het HUIDIGE (laatste) rendement tonen -- zelfde aanpak
        # als bij Sectors, voorkomt dat de grafiek meteen met 11
        # lijnen chaotisch oogt.
        default_themes = sorted(
            all_trend_themes, key=lambda t: theme_trend[t]["values"][-1], reverse=True
        )[:5]
        selected_themes = st.multiselect(
            "Themes to compare", all_trend_themes, default=default_themes, key="theme_trend_selection",
        )
        if selected_themes:
            theme_fig = go.Figure()
            theme_palette = [
                "#1FAE96", "#E8A93C", "#E5484D", "#3ED9C4", "#8992A3",
                "#5AC8B0", "#F5C518", "#C77DFF", "#4DA6FF", "#FF8A5C", "#B0E0D8",
            ]
            for i, theme in enumerate(selected_themes):
                series = theme_trend[theme]
                theme_fig.add_trace(go.Scatter(
                    x=series["dates"], y=series["values"], mode="lines", name=theme,
                    line=dict(color=theme_palette[i % len(theme_palette)], width=2),
                    hovertemplate="%{x}: %{y:+.1f}%<extra>" + theme + "</extra>",
                ))
            theme_fig.add_hline(y=0, line_dash="dash", line_color="#8992A3", line_width=1)
            theme_fig.update_layout(
                yaxis_title="Trailing 1-month return (%)",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, sans-serif", color="#EAEDF1", size=11),
                legend=dict(orientation="h", yanchor="top", y=-0.15, font=dict(size=10)),
                margin=dict(t=10, b=10, l=10, r=10),
                height=420,
                xaxis=dict(gridcolor="rgba(137,146,163,0.15)"),
                yaxis=dict(gridcolor="rgba(137,146,163,0.15)"),
            )
            st.plotly_chart(theme_fig, width="stretch")
        else:
            st.caption("Select at least 1 theme above to see the trend chart.")
    else:
        st.caption("No trend data available right now.")



def render_discover_earnings_surprises(render_own_header: bool = True):
    if render_own_header:
        st.markdown(
            _uniform_section_header_html("Earnings surprises", "payments", is_first=True),
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div style="color:#64748B; font-size:10px; font-weight:700; letter-spacing:0.12em; '
        'text-transform:uppercase; margin-bottom:0.75rem;">Data interval: recent 60-day active signal window.</div>',
        unsafe_allow_html=True,
    )
    surprises = get_earnings_surprises_from_signals(max_items=5)
    if surprises:
        cards_html = [
            _signal_card_html(
                s["ticker"], "Earnings surprise", f"{s['earnings_surprise_pct']:+.1f}%",
                s["earnings_beat"], [("Reported", str(s["earnings_date"])[:10])],
                standout=abs(s["earnings_surprise_pct"]) >= 15.0, neutral_border=True,
            )
            for s in surprises
        ]
        # Zelfde soft-lock als Snowballers/Rocket List: eerste 3 kaarten
        # (de bewijslast) volledig zichtbaar, alles vanaf kaart 4 geblurd
        # met een slotje-overlay voor niet-ingelogde bezoekers.
        _render_signal_cards(cards_html, blur_from_index=(3 if not current_user.is_logged_in else None))
        if not current_user.is_logged_in:
            if len(surprises) > 3:
                _render_unlock_premium_button(
                    "earnings_surprises",
                    label="Unlock all earnings catalysts with a free account \u2192",
                )
        else:
            st.caption(f"Updated {file_last_modified('supertrend_signals_daily.csv')} (daily), "
                       f"{file_last_modified('supertrend_signals.csv')} (weekly). "
                       "⭐ = 15%+ surprise, in either direction.")
    else:
        st.markdown(
            '<div style="color:#94A3B8; font-size:0.75rem; font-weight:500; letter-spacing:0.03em; '
            'text-transform:uppercase;">No active earnings surprises recorded for this period.</div>',
            unsafe_allow_html=True,
        )



def _render_today_demo_landing() -> None:
    """
    'Demo Mode' voor de niet-ingelogde Today-pagina -- zelfde principe als
    de My Portfolio-demo: geen geblurde placeholder, maar een volledig
    scherpe, live-aanvoelende preview met duidelijk herkenbare sample-
    data (populaire large caps + macro-events), gevolgd door de
    conversie-tegel. Hergebruikt zoveel mogelijk dezelfde HTML-helpers/
    CSS-klassen als de ingelogde pagina voor 100% visuele consistentie.
    De Global Sector Heatmap is hier bewust weggelaten (geen directe
    meerwaarde voor een landingspagina).
    """
    st.markdown(
        _uniform_section_header_html("Your Portfolio Today", "calendar_today", is_first=True),
        unsafe_allow_html=True,
    )
    _demo_wrap_key = "today_demo_wrap"
    st.markdown(_demo_watermark_css(_demo_wrap_key), unsafe_allow_html=True)
    with st.container(key=_demo_wrap_key):
        st.markdown(
            '<div style="color:#64748B; font-size:0.68rem; font-weight:700; letter-spacing:0.08em; '
            'text-transform:uppercase; margin-bottom:1rem; display:flex; align-items:center; gap:0.4rem;">'
            '<span style="width:6px; height:6px; border-radius:50%; background:#F59E0B; display:inline-block;"></span>'
            'Demo mode &middot; sample assets, not your real data</div>',
            unsafe_allow_html=True,
        )

        # --- 1. Performance-tegels (Portfolio today / Best / Worst) ---
        st.markdown(_portfolio_responsive_css(), unsafe_allow_html=True)
        col1_html = (
            '<div style="display:flex; flex-direction:column; align-items:flex-start; min-width:0;">'
            '<div style="font-size:0.64rem; color:#1FAE96; text-transform:uppercase; letter-spacing:0.1em; '
            'font-weight:700;">Your Portfolio Today</div>'
            f'<div style="font-size:2.75rem; font-weight:800; color:{TODAY_POSITIVE_TEXT}; margin-top:8px; '
            'line-height:1.1; font-variant-numeric: tabular-nums;">+0.6%</div>'
            '</div>'
        )
        col2_html = _portfolio_mover_tile_html(
            "Best today", "trending_up", "Nvidia (NVDA)", 5.4, 18.5, TODAY_POSITIVE_TEXT,
        )
        col3_html = _portfolio_mover_tile_html(
            "Worst today", "trending_down", "Bitcoin (BTC-USD)", -3.8, 12.0, TODAY_NEGATIVE_TEXT,
        )
        st.markdown(
            f'<div class="hesty-portfolio-row">'
            f'<div class="hesty-portfolio-hero-col">{col1_html}</div>'
            f'<div class="hesty-portfolio-col">{col2_html}</div>'
            f'<div class="hesty-portfolio-col hesty-portfolio-col-last">{col3_html}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # --- 2. Daily Radar: week-agenda + 3 bullet-regels. GEEN 'Explore
        # all signals'-link meer -- niet functioneel op een demo-preview. ---
        st.markdown(
            _uniform_section_header_html("Daily Radar", "radar", is_first=False),
            unsafe_allow_html=True,
        )
        _today_date = datetime.now().date()
        _monday = (
            _today_date - timedelta(days=_today_date.weekday()) if _today_date.weekday() < 5
            else _today_date + timedelta(days=7 - _today_date.weekday())
        )
        _demo_dated_items = [
            (_monday, "", "\U0001F1FA\U0001F1F8 US markets closed (Labor Day)"),
            (_monday + timedelta(days=1), "", "\U0001F34F Apple Inc (AAPL) | Q3 earnings release (after market)"),
            (_monday + timedelta(days=3), "", "\U0001F1EA\U0001F1FA ECB interest rate decision (14:15 CET)"),
            (_monday + timedelta(days=4), "", "\U0001F1FA\U0001F1F8 US CPI data (Aug release) (14:30 CET)"),
        ]
        st.markdown(_week_agenda_html(_bucket_events_by_weekday(_demo_dated_items)), unsafe_allow_html=True)
        st.markdown("<div style='height: 1.1rem'></div>", unsafe_allow_html=True)

        _demo_summary_rows = [
            ("\u2713", "DAILY SUMMARY", "4 item(s) on your radar today.", None),
            ("\U0001F50D", "SCREENER HITS", "6 new long-term ideas found in your active screeners.", "Top hits: NVDA, ASML, MSFT"),
            ("\u26A1", "MACRO CATALYST", "3 key global market movement(s) detected today.", "Biggest movers: Crypto (Top 10) +4.2%, Energy -1.8%"),
        ]
        st.markdown(
            "".join(
                f'<div style="margin-top:8px;">'
                f'<div style="display:flex; align-items:flex-start; gap:0.5rem; '
                f'font-size:0.83rem; color:#CBD5E1; line-height:1.5;">'
                f'<span style="flex-shrink:0; width:1.5rem; display:inline-flex; justify-content:center; '
                f'align-items:center;">{icon}</span>'
                f'<span><b style="color:#EAEDF1; letter-spacing:0.03em;">{label}:</b> {text}</span>'
                f'</div>'
                + (
                    f'<div style="margin-left:2rem; margin-top:3px; font-size:0.72rem; color:#94A3B8;">'
                    f'&rarr; {snippet}</div>' if snippet else ""
                )
                + '</div>'
                for icon, label, text, snippet in _demo_summary_rows
            ),
            unsafe_allow_html=True,
        )

        # --- 3. Portfolio Health & DCA Insights: 2 rebalance-triggers.
        # GEEN 'Adjust target allocations'-link meer -- niet functioneel op
        # een demo-preview. ---
        st.markdown(
            _uniform_section_header_html("Portfolio Health & DCA Insights", "insights", is_first=False),
            unsafe_allow_html=True,
        )

        def _demo_rebalance_card_html(ticker: str, name: str, diff_pct: float, current_pct: float, target_pct: float) -> str:
            sign = "-" if diff_pct < 0 else "+"
            target_label = "below target" if diff_pct < 0 else "above target"
            context = (
                "Consider pointing your next DCA at it." if diff_pct < 0
                else f"{current_pct:.1f}% vs {target_pct:.1f}% target."
            )
            return (
                '<div>'
                '<div style="display:flex; align-items:center; gap:0.3rem;">'
                + _icon_span("balance", size_px=13, color="#8992A3") +
                '<span style="font-size:0.62rem; color:#8992A3; text-transform:uppercase; letter-spacing:0.1em; '
                'font-weight:700;">Rebalance trigger</span>'
                '</div>'
                f'<div style="font-size:1.65rem; font-weight:800; color:#EAEDF1; margin-top:6px; line-height:1.1; '
                f'font-variant-numeric: tabular-nums;">{sign}{abs(diff_pct):.1f}% '
                f'<span style="font-size:0.62rem; font-weight:700; color:#8992A3; text-transform:none; '
                f'letter-spacing:0;">{target_label}</span></div>'
                f'<div style="font-size:0.85rem; color:#CBD5E1; font-weight:600; margin-top:10px;">{name.upper()} '
                f'<span style="color:#64748B; font-weight:400;">({ticker})</span></div>'
                f'<div style="font-size:0.7rem; color:#64748B; margin-top:3px;">{context}</div>'
                '</div>'
            )

        _demo_health_cards = [
            _demo_rebalance_card_html("TSLA", "Tesla Inc", -12.5, 7.5, 20.0),
            _demo_rebalance_card_html("AAPL", "Apple Inc", 6.8, 21.8, 15.0),
        ]
        insight_cols_html = "".join(f'<div class="hesty-insights-col">{c}</div>' for c in _demo_health_cards)
        st.markdown(
            '<style>'
            '.hesty-insights-row { display:flex; align-items:flex-start; gap:2rem; margin-top:0.4rem; } '
            '.hesty-insights-col { flex:1; min-width:0; } '
            '@media (max-width:768px) { '
            '.hesty-insights-row { flex-direction:column; gap:1.25rem; } '
            '.hesty-insights-col { width:100%; } '
            '} '
            '</style>'
            f'<div class="hesty-insights-row">{insight_cols_html}</div>',
            unsafe_allow_html=True,
        )

        # --- 4. CTA-tegel: geen Sector Heatmap meer eronder, dus dit is nu
        # de directe afsluiter van de pagina. Zelfde 'gedeelde container,
        # dubbel geforceerde flex-column'-structuur als de My Portfolio-demo
        # -- Streamlit's binnenste stVerticalBlock erft flex niet automatisch
        # over van de buitenste .st-key-div, vandaar op BEIDE niveaus gezet. ---
        _demo_cta_key = "today_demo_cta_tile"
        st.markdown(
            f'<style>'
            f'.st-key-{_demo_cta_key} {{ '
            f'background:rgba(15,23,42,0.3) !important; border:1px solid rgba(30,41,59,0.4) !important; '
            f'border-radius:14px !important; padding:1.5rem !important; width:100% !important; '
            f'box-sizing:border-box !important; display:flex !important; flex-direction:column !important; '
            f'align-items:center !important; justify-content:center !important; text-align:center !important; '
            f'margin-top:2rem !important; }} '
            f'.st-key-{_demo_cta_key} > div {{ '
            f'display:flex !important; flex-direction:column !important; align-items:center !important; '
            f'justify-content:center !important; text-align:center !important; width:100% !important; }} '
            f'@media (min-width:768px) {{ .st-key-{_demo_cta_key} {{ padding:2rem !important; }} }} '
            f'.hesty-today-demo-cta-text {{ '
            f'max-width:32rem; color:#CBD5E1; font-weight:600; letter-spacing:0.04em; '
            f'text-transform:uppercase; line-height:1.6; font-size:0.78rem; }} '
            f'@media (min-width:768px) {{ .hesty-today-demo-cta-text {{ font-size:0.85rem !important; }} }} '
            f'.st-key-{_demo_cta_key} [data-testid="stButton"] {{ margin-top:1rem !important; width:auto !important; }} '
            f'@media (min-width:768px) {{ '
            f'.st-key-{_demo_cta_key} [data-testid="stButton"] {{ margin-top:1.25rem !important; }} '
            f'}} '
            f'.st-key-{_demo_cta_key} button {{ '
            f'background:rgba(2,6,23,0.8) !important; backdrop-filter:blur(6px) !important; '
            f'-webkit-backdrop-filter:blur(6px) !important; color:#EAEDF1 !important; font-weight:700 !important; '
            f'text-transform:uppercase !important; letter-spacing:0.04em !important; font-size:0.85rem !important; '
            f'border:1px solid rgba(148,163,184,0.35) !important; border-radius:8px !important; '
            f'padding:0.6rem 1.5rem !important; width:auto !important; white-space:nowrap !important; '
            f'box-shadow:0 8px 24px rgba(0,0,0,0.45) !important; }} '
            f'.st-key-{_demo_cta_key} button:hover {{ border-color:rgba(31,174,150,0.6) !important; '
            f'color:#1FAE96 !important; }} '
            f'@media (max-width:480px) {{ '
            f'.st-key-{_demo_cta_key} button {{ white-space:normal !important; font-size:0.78rem !important; '
            f'padding:0.55rem 1.1rem !important; line-height:1.35 !important; }} '
            f'}} '
            f'</style>',
            unsafe_allow_html=True,
        )
        with st.container(key=_demo_cta_key):
            st.markdown(
                '<div class="hesty-today-demo-cta-text">&#128161; YOU ARE CURRENTLY VIEWING HESTYS IN DEMO MODE '
                'WITH SAMPLE DATA. READY TO ACTIVATE YOUR PERSONAL COCKPIT? SECURELY CONNECT YOUR PORTFOLIO OR '
                'WATCHLIST TO UNLOCK YOUR DAILY RADAR.</div>',
                unsafe_allow_html=True,
            )
            if st.button("Connect to Activate Today \u2192", key="today_demo_cta_btn"):
                st.session_state["login_prefill_mode"] = "Sign Up"
                st.switch_page(login_page)


def render_today():
    if not current_user.is_logged_in:
        _render_today_demo_landing()
    else:
        import database
        import screener as _screener_module  # noqa: F401 -- zorgt dat get_top_news_for_tickers 'm kan importeren

        user_email = current_user.email
        holdings = filter_active_holdings(database.get_user_holdings(user_email))
        watchlist_items = database.get_user_holdings(user_email, is_watchlist=True)

        if not holdings and not watchlist_items:
            st.info("Add assets under My Portfolio or your Watchlist to get personal signals and news here.")
        else:
            tracked_items = holdings + watchlist_items

            # 1x, centraal, de achtergrond-gesynchroniseerde marktdata ophalen
            # voor ALLE gevolgde tickers (holdings + watchlist) -- i.p.v. dat
            # elke functie hieronder zijn eigen, LIVE yfinance-aanroepen doet.
            # Dit is de kern van de snelheid-fix: 1 snelle database-query
            # i.p.v. tientallen losse, live netwerk-aanroepen tijdens het
            # laden van de pagina. Elke functie hieronder valt zelf nog
            # netjes terug op een live aanroep voor een ticker die (nog)
            # niet in de tabel staat (net toegevoegd, of sync moet nog
            # draaien) -- dus nooit een harde afhankelijkheid. Gecached
            # (3 min) zodat een Streamlit-rerun die alleen een Story-dialoog
            # opent deze query niet telkens opnieuw hoeft te doen.
            market_data = _session_cached(
                f"today_market_data_{user_email}", 180,
                lambda: database.get_market_data_for_tickers([item["ticker"] for item in tracked_items]),
            )

            # --- Getriggerde watchlist-prijsalerts -- bovenaan, prominent,
            # want dit is precies het soort tijdgevoelig nieuws waar Today
            # voor bedoeld is. Hergebruikt de al-opgehaalde market_data
            # hierboven (geen extra aanroepen). ---
            if watchlist_items:
                triggered_alerts = check_triggered_watchlist_alerts(watchlist_items, market_data)
                for alert in triggered_alerts:
                    direction_word = "dropped to" if alert["alert_direction"] == "below" else "rose to"
                    alert_col1, alert_col2 = st.columns([5, 1])
                    with alert_col1:
                        st.success(
                            f"**{alert['naam']}** ({alert['ticker']}) {direction_word} your alert "
                            f"price of {alert['alert_target_price']:.2f} -- now at {alert['current_price']:.2f}.",
                            icon=":material/notifications_active:",
                        )
                    with alert_col2:
                        st.markdown("<div style='height: 0.6rem'></div>", unsafe_allow_html=True)
                        if st.button("Dismiss", key=f"dismiss_alert_{alert['id']}"):
                            database.dismiss_watchlist_alert(alert["id"], user_email)
                            st.rerun()

            # --- Your portfolio today -- 3 gelijke, borderloze kolommen naast
            # elkaar (Portfolio-rendement / Best today / Worst today), elk
            # gescheiden door 1 dunne verticale lijn. Alles als 1 zelfstandig
            # HTML-blok opgebouwd (i.p.v. st.columns() + CSS-nesting erop) --
            # zelfde 'eigen HTML'-aanpak als de streamlit_css_lessen.md
            # aanraadt voor precieze controle zonder tegen Streamlit's eigen,
            # onbekende DOM-lagen te hoeven vechten. Geen losse 'View My
            # Portfolio'-link meer in kolom 1 -- laatste stukje handmatige
            # navigatieruis, verwijderd. ---
            # Alvast op None gezet (i.p.v. alleen binnen 'if holdings:'
            # gedefinieerd) -- zodat de Daily Radar-sectie hieronder 'm
            # veilig kan uitlezen ook als er geen holdings zijn (alleen
            # watchlist-items), zonder een NameError te riskeren.
            daily_stats = None
            if holdings:
                with st.spinner("Checking today's price moves..."):
                    daily_stats = build_daily_portfolio_stats(holdings, market_data)

                st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
                st.markdown(
                    _uniform_section_header_html("Your Portfolio Today", "account_balance_wallet", is_first=True),
                    unsafe_allow_html=True,
                )

                # VIX vooraf ophalen -- hoort inhoudelijk niet bij het
                # portfolio-rendement, maar krijgt hier een eigen tegel
                # ALS 4e kolom in dezelfde rij i.p.v. een hele aparte
                # sectie verderop (die voor 1 losse regel te zwaar oogde).
                _vix_value = _get_live_vix_value()
                if _vix_value is not None:
                    if _vix_value > 25:
                        _vix_status, _vix_color = "CRITICAL COOLDOWN", TODAY_NEGATIVE_TEXT
                        _vix_bg, _vix_border = "rgba(244,63,94,0.08)", "rgba(244,63,94,0.4)"
                    elif _vix_value >= 15:
                        _vix_status, _vix_color = "TACTICAL", "#E8A93C"
                        _vix_bg, _vix_border = "rgba(232,169,60,0.07)", "rgba(232,169,60,0.35)"
                    else:
                        _vix_status, _vix_color = "LOW", TODAY_POSITIVE_TEXT
                        _vix_bg, _vix_border = "rgba(15,23,42,0.3)", "rgba(30,41,59,0.4)"
                    vix_tile_html = _today_metric_tile_html(
                        "Market Volatility (VIX)", "speed", f"{_vix_value:.2f}", _vix_color, _vix_bg, _vix_border,
                        footer_text=f"Status: {_vix_status}",
                    )
                else:
                    vix_tile_html = _today_metric_tile_html(
                        "Market Volatility (VIX)", "speed", "n/a", "#8992A3",
                        "rgba(15,23,42,0.3)", "rgba(30,41,59,0.4)", footer_text="Data not available right now",
                    )

                if daily_stats:
                    vs_yesterday_pct = daily_stats["portfolio_change_pct"]
                    vs_yesterday_color = TODAY_POSITIVE_TEXT if vs_yesterday_pct >= 0 else TODAY_NEGATIVE_TEXT
                    vs_yesterday_bg = "rgba(16,185,129,0.06)" if vs_yesterday_pct >= 0 else "rgba(244,63,94,0.08)"
                    vs_yesterday_border = "rgba(16,185,129,0.3)" if vs_yesterday_pct >= 0 else "rgba(244,63,94,0.4)"

                    best_pct = daily_stats["best_change_pct"]
                    best_color = TODAY_POSITIVE_TEXT if best_pct >= 0 else TODAY_NEGATIVE_TEXT
                    best_bg = "rgba(16,185,129,0.06)" if best_pct >= 0 else "rgba(244,63,94,0.08)"
                    best_border = "rgba(16,185,129,0.3)" if best_pct >= 0 else "rgba(244,63,94,0.4)"

                    worst_pct = daily_stats["worst_change_pct"]
                    worst_color = TODAY_POSITIVE_TEXT if worst_pct >= 0 else TODAY_NEGATIVE_TEXT
                    worst_bg = "rgba(16,185,129,0.06)" if worst_pct >= 0 else "rgba(244,63,94,0.08)"
                    worst_border = "rgba(16,185,129,0.3)" if worst_pct >= 0 else "rgba(244,63,94,0.4)"

                    tile1 = _today_metric_tile_html(
                        "Your Portfolio Today", "account_balance_wallet", f"{vs_yesterday_pct:+.1f}%",
                        vs_yesterday_color, vs_yesterday_bg, vs_yesterday_border,
                    )
                    tile2 = _today_metric_tile_html(
                        "Best Today", "trending_up", f"{best_pct:+.1f}%", best_color, best_bg, best_border,
                        footer_text=f"{daily_stats['best_performer'].upper()} &middot; Weight: {daily_stats['best_weight_pct']:.1f}%",
                    )
                    tile3 = _today_metric_tile_html(
                        "Worst Today", "trending_down", f"{worst_pct:+.1f}%", worst_color, worst_bg, worst_border,
                        footer_text=f"{daily_stats['worst_performer'].upper()} &middot; Weight: {daily_stats['worst_weight_pct']:.1f}%",
                    )

                    tile_col1, tile_col2, tile_col3, tile_col4 = st.columns(4, gap="medium")
                    with tile_col1:
                        st.markdown(tile1, unsafe_allow_html=True)
                    with tile_col2:
                        st.markdown(tile2, unsafe_allow_html=True)
                    with tile_col3:
                        st.markdown(tile3, unsafe_allow_html=True)
                    with tile_col4:
                        st.markdown(vix_tile_html, unsafe_allow_html=True)
                else:
                    mcol1, mcol2, mcol3, mcol4 = st.columns(4, gap="medium")
                    with mcol1:
                        st.metric("Your Portfolio Today", "n/a")
                    with mcol2:
                        st.metric("Best today", "n/a")
                    with mcol3:
                        st.metric("Worst today", "n/a")
                    with mcol4:
                        st.markdown(vix_tile_html, unsafe_allow_html=True)

            # --- Daily Radar -- 2e hoofdsectie van de pagina (direct onder
            # Your Portfolio Today). Geen klikbare Stories-cirkels meer: de
            # belangrijkste bulletins staan nu direct, plat leesbaar onder de
            # titel (Today's Insights Summary) -- zie _compute_radar_bundle()
            # verderop voor dezelfde onderliggende data als voorheen. Een
            # handmatige ververs-knop rechtsboven in de titelregel; de pagina
            # laadt standaard nog steeds gewoon uit de gecachete data (zie
            # _session_cached()). ---
            st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
            radar_header_col, radar_refresh_col = st.columns([11, 1])
            with radar_header_col:
                _radar_explore_link_html = (
                    '<a href="/discover" target="_self" class="inline-link" '
                    'style="font-size:0.78rem; white-space:nowrap;">Explore all signals on Discover &rarr;</a>'
                )
                st.markdown(
                    _uniform_section_header_html(
                        "Daily Radar", "radar", is_first=False, action_html=_radar_explore_link_html,
                    ),
                    unsafe_allow_html=True,
                )
            with radar_refresh_col:
                radar_refresh_key = "today_radar_refresh"
                st.markdown(
                    f'<style>.st-key-{radar_refresh_key} button {{ all:unset !important; cursor:pointer !important; '
                    f'color:#8992A3 !important; font-size:1rem !important; padding:4px !important; '
                    f'display:flex !important; justify-content:flex-end !important; width:100% !important; }} '
                    f'.st-key-{radar_refresh_key} button:hover {{ color:#1FAE96 !important; }} '
                    f'</style>',
                    unsafe_allow_html=True,
                )
                with st.container(key=radar_refresh_key):
                    if st.button("", icon=":material/refresh:", key=f"{radar_refresh_key}_click", help="Refresh data"):
                        st.session_state.pop(f"today_radar_bundle_{user_email}", None)
                        with st.spinner("Refreshing daily radar..."):
                            fresh_bundle = radar_data.compute_daily_radar_bundle(
                                user_email, holdings, watchlist_items, market_data,
                            )
                            database.set_daily_radar_cache(user_email, fresh_bundle)
                        st.rerun()

            # --- Data ophalen: eerst de achtergrond-berekende cache
            # (database.get_daily_radar_cache(), elke 6 uur ververst door
            # daily_radar_batch.py via GitHub Actions), pas als die
            # ontbreekt of te oud is (>7 uur -- iets ruimer dan de 6-uurs
            # cron, voorkomt onnodige live fallbacks door kleine planning-
            # vertragingen) een LIVE herberekening via dezelfde
            # radar_data.compute_daily_radar_bundle() die het batch-script
            # ook gebruikt (geen aparte kopie van de logica hier -- 1
            # bron van waarheid). Binnen 1 sessie bovendien nog een keer
            # met _session_cached() omwikkeld, zodat een Streamlit-rerun
            # (bv. een ander widget elders op de pagina) niet zelfs de
            # databasequery hoeft te herhalen.
            def _load_radar_bundle():
                cached = database.get_daily_radar_cache(user_email)
                if cached and cached.get("computed_at"):
                    computed_at = datetime.fromisoformat(cached["computed_at"])
                    if computed_at.tzinfo is None:
                        computed_at = computed_at.replace(tzinfo=timezone.utc)
                    age_hours = (datetime.now(timezone.utc) - computed_at).total_seconds() / 3600
                    if age_hours < 7:
                        return cached["data"]
                return radar_data.compute_daily_radar_bundle(user_email, holdings, watchlist_items, market_data)

            radar_bundle = _session_cached(f"today_radar_bundle_{user_email}", 300, _load_radar_bundle)
            day_items = radar_bundle["day_items"]
            macro_items = radar_bundle["macro_items"]
            opportunities = radar_bundle["opportunities"]
            macro_top_movers = radar_bundle.get("macro_top_movers", [])
            new_opportunity_tickers = opportunities.get("new_opportunity_tickers", [])

            # --- Horizontale Week-Agenda (Ma t/m Vr) -- nu BOVENAAN de
            # sectie, direct onder de titel (prominenter dan de bulletins
            # eronder). Rauwe, gedateerde events komen al kant-en-klaar uit
            # de radar-bundel (batch of live, zelfde vorm); hier alleen
            # omzetten naar de (datum, icoon-HTML, tekst)-tuples die
            # _bucket_events_by_weekday() verwacht. ---
            dated_agenda_items = [
                (
                    datetime.strptime(d["date"], "%Y-%m-%d").date(),
                    _icon_span(d["icon"], size_px=13, color="#8992A3"),
                    d["text"],
                )
                for d in radar_bundle["dated_agenda_items"]
            ]
            st.markdown(_week_agenda_html(_bucket_events_by_weekday(dated_agenda_items)), unsafe_allow_html=True)

            st.markdown("<div style='height: 1.1rem'></div>", unsafe_allow_html=True)

            # --- Today's Insights Summary -- nu ONDER de agenda. Vervangt
            # de klikbare Stories-cirkels door direct scanbare, platte
            # tekst: dezelfde 3 categorieen data (dag-gebeurtenissen,
            # screener-hits, macro-catalysts) als voorheen, nu meteen
            # zichtbaar i.p.v. achter een klik verstopt. Screener Hits en
            # Macro Catalyst krijgen een ingesprongen snippet-regel eronder
            # met de daadwerkelijke tickers/uitschieters (ECHTE data, geen
            # mock -- zie radar_data.py's toelichting bij
            # new_opportunity_tickers/macro_top_movers). ---
            screener_snippet = (
                f"Top hits: {', '.join(new_opportunity_tickers)}" if new_opportunity_tickers else None
            )

            # GEVONDEN, DERDE AANPASSING (op verzoek na live-gebruik): een
            # aparte 4e "THEME ALERT"-regel was overbodig -- als een thema
            # 10%+ beweegt hoort dat gewoon MEE te tellen in de bestaande
            # MACRO CATALYST-regel, niet als eigen bulletin ernaast. Daarom
            # nu VOOR macro_snippet al build_theme_rotation() erbij pakken
            # (dezelfde 15-min gecachete data als voorheen) en de thema's die
            # nog niet al genoemd worden via macro_top_movers (radar_data.py
            # heeft zijn eigen, strengere thema-drempel) toevoegen aan zowel
            # de macro-teller als de macro-snippet zelf.
            _theme_rotation = _session_cached("today_theme_rotation", 900, build_theme_rotation)
            _extreme_themes = (
                sorted(
                    [t for t in _theme_rotation if abs(t["return_pct"]) >= 10],
                    key=lambda t: abs(t["return_pct"]), reverse=True,
                )
                if _theme_rotation else []
            )
            _extra_theme_movers = [
                f"{t['theme']} {t['return_pct']:+.1f}%" for t in _extreme_themes
                if not any(t["theme"] in mover for mover in macro_top_movers)
            ]
            _combined_macro_count = len(macro_items) + len(_extra_theme_movers)
            _combined_macro_movers = list(macro_top_movers) + _extra_theme_movers
            macro_snippet = (
                f"Biggest movers: {', '.join(_combined_macro_movers)}" if _combined_macro_movers else None
            )

            # GEEN pratende 'X item(s) on your radar today' meer -- die zin
            # vermeldde WEL een aantal maar liet nooit zien WELK specifiek
            # aandeel/signaal daar concreet achter zat.
            #
            # GEVONDEN, TWEEDE PROBLEEM (na live-gebruik): de eerste versie
            # gebruikte hiervoor de slechtst presterende positie van vandaag
            # -- maar dat is EXACT dezelfde asset + hetzelfde percentage als
            # de 'Worst today'-tegel rechtsboven al toont. Pure duplicatie,
            # geen nieuwe informatie. De radar mag daarom NOOIT nog een keer
            # dezelfde best/worst-performer laten zien: eerst wordt de
            # naam van vandaag's best/worst performer opgezocht in holdings
            # (om de bijbehorende ticker te vinden), en die ticker(s) worden
            # expliciet UITGESLOTEN als kandidaat voor het radar-signaal.
            #
            # GEVONDEN, DERDE PROBLEEM (na live-gebruik): een 'nieuwe
            # screener-opportunity' zoals DDOG is per DEFINITIE een ticker
            # die je niet bezit en niet volgt (zie build_opportunities_
            # today()'s eigen 'new_opportunities = ... - holding_tickers -
            # watchlist_tickers') -- dus weinig direct bruikbaar op een
            # persoonlijke Daily Radar. Nu vervangen door
            # _find_held_or_watched_technical_signal(): een ECHT technisch
            # Supertrend-signaal, maar UITSLUITEND op een ticker die al in
            # je portfolio of watchlist staat. Geen macro-catalyst-fallback
            # meer hier (die uitschieters horen al bij hun eigen 'MACRO
            # CATALYST'-regel verderop) -- als er geen match is, gewoon de
            # eerlijke 'system stable'-statusregel.
            _excluded_radar_tickers = set()
            if daily_stats:
                _name_to_ticker = {h["naam"]: h["ticker"] for h in holdings}
                _excluded_radar_tickers = {
                    _name_to_ticker.get(daily_stats.get("best_performer")),
                    _name_to_ticker.get(daily_stats.get("worst_performer")),
                }
                _excluded_radar_tickers.discard(None)

            # GEVONDEN, VIERDE UITBREIDING (op verzoek na live-gebruik): de
            # radar keek tot nu toe ALLEEN naar een technisch Supertrend-
            # signaal. Maar radar_data.py berekent al 3 andere, minstens zo
            # actiegerichte dag-gebeurtenissen die nergens los zichtbaar
            # waren (alleen meegeteld in day_items): een deep-dive sell-
            # trigger die vandaag geraakt is, een 52-week high/low, en een
            # ex-dividend datum binnen 5 dagen.
            #
            # EERSTE VERSIE toonde hiervan maar 1 (de "belangrijkste") op 1
            # regel -- maar als er op dezelfde dag toevallig 2 of 3 van deze
            # dingen spelen (bv. een sell-trigger EN een 52-week high op
            # verschillende tickers), wil je die allebei zien, niet alleen
            # de "winnaar". Daarom nu: ALLE gevonden signalen worden verzameld
            # (elk als eigen regel), gededupliceerd per TICKER (dezelfde asset
            # verschijnt maar 1x -- met de belangrijkste soort signaal als er
            # toevallig meerdere types op dezelfde ticker spelen), in deze
            # volgorde van belangrijkheid: sell-trigger (je eigen vooraf
            # ingestelde regel wordt geraakt) > 52-week record (zeldzaam en
            # prijs-relevant) > technisch Supertrend-signaal > ex-dividend
            # (gepland, minst urgent). Geen enkel signaal gevonden -> 1x de
            # eerlijke "system stable"-statusregel.
            _deep_dive_hits = radar_data.get_deep_dive_triggers_hit(user_email, max_items=5)
            _deep_dive_hits = [d for d in _deep_dive_hits if d["ticker"] not in _excluded_radar_tickers]

            _week_52_hits = radar_data.get_52_week_records(holdings, market_data, max_items=3) if holdings else []
            _week_52_hits = [r for r in _week_52_hits if r["ticker"] not in _excluded_radar_tickers]

            _held_signal = _find_held_or_watched_technical_signal(holdings, watchlist_items)

            _ex_div_hits = radar_data.get_upcoming_ex_dividend_dates(holdings, market_data, days_ahead=5, max_items=3) if holdings else []
            _ex_div_hits = [e for e in _ex_div_hits if e["ticker"] not in _excluded_radar_tickers]

            _radar_signals = []
            _seen_radar_tickers = set()

            for _hit in _deep_dive_hits:
                if _hit["ticker"] in _seen_radar_tickers:
                    continue
                _seen_radar_tickers.add(_hit["ticker"])
                _radar_signals.append((_hit["ticker"], f"SELL TRIGGER, {_hit['detail'].upper()}"))

            for _hit in _week_52_hits:
                if _hit["ticker"] in _seen_radar_tickers:
                    continue
                _seen_radar_tickers.add(_hit["ticker"])
                _radar_signals.append((_hit["ticker"], f"52-WEEK {_hit['type'].upper()} HIT"))

            if _held_signal and _held_signal["ticker"] not in _seen_radar_tickers:
                _seen_radar_tickers.add(_held_signal["ticker"])
                _trigger_parts = ["BULLISH FLIP"]
                if _held_signal["score"] is not None:
                    _trigger_parts.append(f"SCORE {_held_signal['score']:.1f}")
                if _held_signal["days_ago"] is not None:
                    _trigger_parts.append(f"{_held_signal['days_ago']}D AGO")
                if _held_signal["since_pct"] is not None:
                    _trigger_parts.append(f"{_held_signal['since_pct']:+.1f}% SINCE FLIP")
                _radar_signals.append((_held_signal["ticker"], ", ".join(_trigger_parts)))

            for _hit in _ex_div_hits:
                if _hit["ticker"] in _seen_radar_tickers:
                    continue
                _seen_radar_tickers.add(_hit["ticker"])
                _radar_signals.append((_hit["ticker"], f"EX-DIVIDEND IN {_hit['days_until']}D ({_hit['ex_div_date']})"))

            if _radar_signals:
                _radar_rows = [
                    ("\u2726", "RADAR SIGNAL", f"ASSET: {_asset.upper()} | TRIGGER: {_trigger}", None)
                    for _asset, _trigger in _radar_signals
                ]
            else:
                _radar_rows = [(
                    "\u2726", "RADAR STATUS",
                    "SYSTEM STABLE | NO ANOMALIES DETECTED WITHIN ACTIVE HOLDINGS", None,
                )]

            summary_rows = [
                *_radar_rows,
                (
                    "\U0001F50D", "SCREENER HITS",
                    f"{opportunities.get('new_opportunities_count', 0)} new long-term ideas found in your active screeners.",
                    screener_snippet,
                ),
                (
                    "\u26A1", "MACRO CATALYST",
                    f"{_combined_macro_count} key global market movement(s) detected today.",
                    macro_snippet,
                ),
            ]
            # Typografie-fix: loepzuivere text-sm (0.875rem, i.p.v. de
            # eerdere 0.83rem/0.72rem die in het donker wegvielen),
            # onwrikbare ALL-CAPS metadata-stijl, helderwitte hoofdtekst
            # (#F1F5F9) met gedempte text-slate-300 (#CBD5E1) voor de
            # ingesprongen snippet-regel, en ruimere verticale ademruimte
            # tussen de alerts (margin-top + padding-bottom, samen goed
            # voor >1rem lucht per item -- Tailwind's space-y-4-equivalent).
            st.markdown(
                "".join(
                    f'<div style="margin-top:16px; padding-bottom:14px;">'
                    f'<div style="display:flex; align-items:flex-start; gap:0.5rem; '
                    f'font-size:0.875rem; color:#F1F5F9; line-height:1.5; text-transform:uppercase; '
                    f'letter-spacing:0.02em; font-family:\'Inter\', sans-serif !important;">'
                    f'<span style="flex-shrink:0; width:1.5rem; display:inline-flex; justify-content:center; '
                    f'align-items:center;">{icon}</span>'
                    f'<span><b style="color:#F1F5F9; font-weight:700; letter-spacing:0.03em;">{label}:</b> {text}</span>'
                    f'</div>'
                    + (
                        f'<div style="margin-left:2rem; margin-top:4px; font-size:0.8rem; color:#CBD5E1; '
                        f'text-transform:uppercase; letter-spacing:0.02em; '
                        f'font-family:\'Inter\', sans-serif !important;">&rarr; {snippet}</div>'
                        if snippet else ""
                    )
                    + '</div>'
                    for icon, label, text, snippet in summary_rows
                ),
                unsafe_allow_html=True,
            )

            # --- Portfolio Health & DCA Insights -- horizontale kolommen,
            # net als 'Your Portfolio Today' hierboven, maar BEWUST ZONDER
            # verticale scheidslijnen en zonder kaart-achtergrond/-rand --
            # dat visuele verschil is precies wat deze sectie een eigen
            # identiteit geeft t.o.v. het blok erboven. Herbalanceer-
            # triggers hergebruiken de bestaande build_rebalancing_
            # suggestions()-logica (ongewijzigd, al aanwezig voor
            # Analyze); Watchlist-Snack is nieuw. Elke kolom is los
            # dismissbaar (5 dagen, via localStorage). ---
            if holdings:
                total_portfolio_value = sum(h.get("position_value") or 0 for h in holdings)
                rebalancing = build_rebalancing_suggestions(holdings, total_portfolio_value)
                near_target_watchlist = (
                    get_watchlist_near_target_alerts(watchlist_items, market_data) if watchlist_items else []
                )

                # Gecombineerd, gecapt op 3 -- exact zoveel kolommen als de
                # sectie heeft (Insight 1/2/3).
                health_cards_html = ([
                    _rebalance_trigger_card_html(suggestion, "$")
                    for suggestion in rebalancing["suggestions"][:2]
                ] + [
                    _watchlist_snack_card_html(alert) for alert in near_target_watchlist
                ])[:3]

                if health_cards_html:
                    _insights_link_html = (
                        '<a href="/portfolio" target="_self" class="inline-link" '
                        'style="font-size:0.78rem; white-space:nowrap;">Adjust target allocations in My Portfolio &rarr;</a>'
                    )
                    st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
                    st.markdown(
                        _uniform_section_header_html(
                            "Portfolio Health & DCA Insights", "insights", is_first=False,
                            action_html=_insights_link_html,
                        ),
                        unsafe_allow_html=True,
                    )

                    insight_cols_html = "".join(
                        f'<div class="hesty-insights-col">{card}</div>' for card in health_cards_html
                    )
                    st.markdown(
                        '<style>'
                        '.hesty-insights-row { display:flex; align-items:flex-start; gap:2rem; margin-top:0.4rem; } '
                        '.hesty-insights-col { flex:1; min-width:0; } '
                        '@media (max-width:768px) { '
                        '.hesty-insights-row { flex-direction:column; gap:1.25rem; } '
                        '.hesty-insights-col { width:100%; } '
                        '} '
                        '</style>'
                        f'<div class="hesty-insights-row">{insight_cols_html}</div>',
                        unsafe_allow_html=True,
                    )
                    _render_insight_dismiss_autohide_script()

            # Market Volatility (VIX) heeft GEEN eigen sectie meer -- die gaf
            # voor 1 losse regel te veel gewicht op de pagina. Zit nu als 4e
            # tegel in de 'Your Portfolio Today'-rij hierboven, in exact
            # hetzelfde kleur-meebewegende tegel-idioom.

            # --- Your Daily Briefing -- eigen hoofdsectie, helemaal onderaan.
            # Zelfde borderloze 'flowing section'-stijl als de rest van de
            # pagina (geen st.expander()-kader meer), 2 kolommen naast elkaar
            # op desktop (Top News For You / Global Market News), gescheiden
            # door exact dezelfde dunne verticale lijn als het portfolio-blok
            # -- en op mobiel netjes gestapeld i.p.v. naast elkaar geperst. ---
            st.markdown(
                _uniform_section_header_html("Your Daily Briefing", "newspaper", is_first=False),
                unsafe_allow_html=True,
            )

            with st.spinner("Checking news..."):
                top_news = get_top_news_for_tickers(tracked_items, max_items=5)
            with st.spinner("Checking market news..."):
                market_news = get_top_news_for_tickers(
                    [{"naam": "S&P 500", "ticker": "^GSPC"}, {"naam": "AEX", "ticker": "^AEX"}],
                    max_items=3,
                )

            def _news_item_html(n: dict, show_name: bool) -> str:
                # Asset-naam blijft strak bold + ALL-CAPS vóór de titel (zelfde
                # conventie als de rest van Today) -- bron + datum verhuizen
                # naar een eigen, kleine/gedempte regel ERONDER, zodat de
                # titel zelf alle ruimte krijgt i.p.v. te moeten delen met een
                # opdringerige inline '(bron, datum)'-toevoeging.
                pub_date = n["published"].strftime("%Y-%m-%d")
                name_prefix = f'<b>{n["naam"].upper()}:</b> ' if show_name else ""
                return (
                    f'<div style="margin-bottom:13px;">'
                    f'<a href="{n["link"]}" target="_blank" class="hesty-news-link">{name_prefix}{n["title"]}</a>'
                    f'<div class="hesty-news-meta">{n["publisher"]} &bull; {pub_date}</div>'
                    f'</div>'
                )

            top_news_html = (
                "".join(_news_item_html(n, show_name=True) for n in top_news) if top_news
                else '<div style="font-size:0.8rem; color:#8992A3;">No recent news found for your tracked positions.</div>'
            )
            market_news_html = (
                "".join(_news_item_html(n, show_name=False) for n in market_news) if market_news
                else '<div style="font-size:0.8rem; color:#8992A3;">No market news available right now.</div>'
            )

            st.markdown(
                '<style>'
                '.hesty-news-row { display:flex; align-items:flex-start; gap:1.75rem; } '
                '.hesty-news-col { flex:1; min-width:0; border-right:1px solid rgba(137,146,163,0.15); '
                'padding-right:1.75rem; } '
                '.hesty-news-col-last { border-right:none !important; padding-right:0 !important; } '
                '.hesty-news-col-title { font-size:0.68rem; font-weight:600; text-transform:uppercase; '
                'letter-spacing:0.08em; color:#1FAE96; font-family:\'Inter\', sans-serif !important; } '
                '.hesty-news-col-subcaption { font-size:0.68rem; color:#94A3B8; margin-top:4px; '
                'margin-bottom:16px; line-height:1.4; min-height:2rem; '
                'font-family:\'Inter\', sans-serif !important; } '
                '.hesty-news-link, .hesty-news-link:visited { '
                'color:#E2E8F0 !important; text-decoration:none !important; font-size:0.85rem; '
                'line-height:1.4; display:block; font-family:\'Inter\', sans-serif !important; } '
                '.hesty-news-link:hover { color:#1FAE96 !important; } '
                '.hesty-news-meta { font-size:0.68rem; color:#64748B; margin-top:3px; } '
                '@media (max-width:768px) { '
                '.hesty-news-row { flex-direction:column; gap:0; } '
                '.hesty-news-col { width:100%; border-right:none !important; padding-right:0 !important; '
                'border-bottom:1px solid rgba(137,146,163,0.15); padding-bottom:1.5rem; margin-bottom:1.5rem; } '
                '.hesty-news-col-last { border-bottom:none !important; padding-bottom:0 !important; margin-bottom:0 !important; } '
                '.hesty-news-col-subcaption { min-height:0; } '
                '} '
                '</style>'
                '<div class="hesty-news-row">'
                '<div class="hesty-news-col">'
                '<div class="hesty-news-col-title">Top News For You</div>'
                '<div class="hesty-news-col-subcaption">'
                'The 5 most recent items across your portfolio and watchlist (last 3 days), most recent first.</div>'
                f'{top_news_html}'
                '</div>'
                '<div class="hesty-news-col hesty-news-col-last">'
                '<div class="hesty-news-col-title">Global Market News</div>'
                '<div class="hesty-news-col-subcaption">'
                'Latest S&amp;P 500 and AEX headlines.</div>'
                f'{market_news_html}'
                '</div>'
                '</div>',
                unsafe_allow_html=True,
            )


def render_premium():
    st.markdown(
        _uniform_section_header_html("Hestys Premium", "workspace_premium", is_first=True),
        unsafe_allow_html=True,
    )
    # Subtekst reageert op inlogstatus -- een bezoeker die de deal nog
    # moet claimen krijgt de wervende pitch, een gebruiker die 'm al heeft
    # geclaimd krijgt een bevestiging i.p.v. dezelfde 'kom erbij'-tekst
    # nogmaals te zien (voelt overbodig/onprofessioneel als je 'm al hebt).
    if current_user.is_logged_in:
        _premium_subtext = "WELCOME TO THE INNER CIRCLE | YOUR LIFETIME FREE PRO ACCESS IS LOCKED IN."
    else:
        _premium_subtext = "BUILT FOR SERIOUS INVESTORS | BE AN EARLY ADOPTER AND LOCK IN YOUR ACCESS FOR LIFE."
    st.markdown(
        f'<div style="color:#64748B; font-size:0.75rem; font-weight:600; text-transform:uppercase; '
        f'letter-spacing:0.03em; margin-bottom:1.25rem;">{_premium_subtext}</div>',
        unsafe_allow_html=True,
    )

    # --- 2-koloms 'Early Access Lifetime'-opzet i.p.v. de oude
    # vergelijkingstabel + losse Smart DCA Assistant-container (die tunen
    # we achter de schermen verder, komt later terug) -- de volledige
    # focus ligt nu op 1 boodschap: vroege gebruikers krijgen voorgoed
    # gratis PRO-status, inclusief alle toekomstige features. ---
    pcol1, pcol2 = st.columns(2, gap="medium")

    _early_card_key = "premium_early_adopter_card"
    _early_btn_key = "premium_early_adopter_btn"
    st.markdown(
        f'<style>'
        f'.st-key-{_early_card_key} {{ '
        f'background:rgba(15,23,42,0.4) !important; border:1px solid rgba(31,174,150,0.4) !important; '
        f'border-radius:14px !important; padding:1.5rem !important; box-sizing:border-box !important; }} '
        f'.st-key-{_early_btn_key} {{ margin-top:1.25rem !important; }} '
        f'.st-key-{_early_btn_key} button {{ '
        f'background:transparent !important; color:#1FAE96 !important; font-weight:700 !important; '
        f'text-transform:uppercase !important; letter-spacing:0.04em !important; font-size:0.85rem !important; '
        f'border:1px solid rgba(31,174,150,0.5) !important; border-radius:8px !important; '
        f'padding:0.6rem 1.25rem !important; width:100% !important; box-shadow:none !important; }} '
        f'.st-key-{_early_btn_key} button:hover {{ background:rgba(31,174,150,0.12) !important; }} '
        # 'inactief' t.o.v. de linkerkaart komt nu ALLEEN nog van de
        # gedempte kleuren zelf (rand/achtergrond/tekst) -- GEEN
        # container-brede opacity meer. Die verdubbelde eerder met de
        # toch al gedempte tekstkleuren (#8992A3/#64748B op 0.4 opacity
        # = vrijwel onleesbaar), i.p.v. gewoon leesbaar-maar-gedempt.
        f'.st-key-premium_future_card {{ '
        f'background:rgba(15,23,42,0.2) !important; border:1px solid rgba(30,41,59,0.4) !important; '
        f'border-radius:14px !important; padding:1.5rem !important; box-sizing:border-box !important; '
        f'pointer-events:none !important; user-select:none !important; }} '
        f'.st-key-premium_future_card button {{ '
        f'background:transparent !important; color:#64748B !important; font-weight:700 !important; '
        f'text-transform:uppercase !important; letter-spacing:0.04em !important; font-size:0.85rem !important; '
        f'border:1px solid rgba(100,116,139,0.35) !important; border-radius:8px !important; '
        f'padding:0.6rem 1.25rem !important; width:100% !important; box-shadow:none !important; '
        f'margin-top:1.25rem !important; cursor:default !important; }} '
        f'.hesty-premium-title-early {{ '
        f'color:#34D399; font-weight:800; font-size:1rem; text-transform:uppercase; '
        f'letter-spacing:0.04em; margin-bottom:1rem; }} '
        f'@media (min-width:768px) {{ .hesty-premium-title-early {{ font-size:1.125rem !important; }} }} '
        f'.hesty-premium-title-future {{ '
        f'color:#CBD5E1; font-weight:700; font-size:0.95rem; text-transform:uppercase; '
        f'letter-spacing:0.04em; margin-bottom:1rem; }} '
        f'</style>',
        unsafe_allow_html=True,
    )
    def _premium_feature_line(text: str, paren: str = None, icon: str = "&#10003;",
                               icon_color: str = "rgba(16,185,129,0.8)", text_color: str = "#CBD5E1") -> str:
        """
        1 feature-regel als eigen <div> (i.p.v. alles met <br> aaneen te
        rijgen in 1 platte tekstmuur) -- geeft elke regel z'n eigen
        padding voor luchtige, scanbare ademruimte, en houdt de tekst
        tussen haakjes als een LOS, gedempt element i.p.v. dezelfde
        felwitte opmaak als de hoofdtekst.
        """
        paren_html = (
            f' <span style="color:#64748B; font-size:0.68rem; font-weight:500; '
            f'letter-spacing:0.03em; text-transform:uppercase;">({paren})</span>'
            if paren else ""
        )
        return (
            f'<div style="padding:0.4rem 0;">'
            f'<span style="color:{icon_color}; font-weight:700; margin-right:0.5rem;">{icon}</span>'
            f'<span style="color:{text_color}; font-weight:600; text-transform:uppercase; '
            f'letter-spacing:0.02em; font-size:0.85rem;">{text}</span>{paren_html}'
            f'</div>'
        )

    with pcol1:
        with st.container(key=_early_card_key):
            _early_features = "".join([
                _premium_feature_line("Unlimited asset tracking", "launch special"),
                _premium_feature_line("Full access to all Signature Signals", "no blurs"),
                _premium_feature_line("Deep portfolio risk &amp; concentration metrics"),
                _premium_feature_line("Includes access to all future premium features"),
                _premium_feature_line("Your daily personalized radar"),
                _premium_feature_line("Portfolio rebalancing tips"),
                _premium_feature_line("Establish your own deepdives"),
            ])
            st.markdown(
                '<div class="hesty-premium-title-early">Early Adopter (Free Now)</div>'
                f'<div>{_early_features}</div>'
                # De afsluitregel krijgt bewust EXTRA bovenruimte (mt-2) +
                # een eigen, iets grotere/witte stijl -- dit is de grote
                # 'closer' van het pakket, geen gewone feature-regel.
                '<div style="margin-top:0.5rem; color:#EAEDF1; font-weight:700; font-size:0.85rem; '
                'text-transform:uppercase; letter-spacing:0.02em;">'
                '&#127873; Lifetime PRO status: join now and stay free forever.'
                '</div>',
                unsafe_allow_html=True,
            )
            if current_user.is_logged_in:
                # Geen 'Claim'-knop meer als je 'm al hebt geclaimd -- een
                # niet-klikbare, oplichtende status-badge bevestigt dat je
                # actief bent i.p.v. dezelfde actieknop nogmaals te tonen.
                st.markdown(
                    '<div style="background:rgba(6,78,59,0.4); color:#34D399; '
                    'border:1px solid rgba(16,185,129,0.3); font-size:0.72rem; font-weight:700; '
                    'letter-spacing:0.08em; text-transform:uppercase; padding:0.65rem 1.25rem; '
                    'border-radius:10px; text-align:center; width:100%; box-sizing:border-box; '
                    'margin-top:1.25rem;">&#10003; Your early adopter status is active</div>',
                    unsafe_allow_html=True,
                )
            else:
                with st.container(key=_early_btn_key):
                    if st.button("Claim Free Pro Access \u2192", key="premium_early_adopter_claim"):
                        st.session_state["login_prefill_mode"] = "Sign Up"
                        st.switch_page(login_page)
    with pcol2:
        with st.container(key="premium_future_card"):
            _future_features = "".join([
                _premium_feature_line("Limited to max 10 assets", icon="&#10003;",
                                       icon_color="#475569", text_color="#64748B"),
                _premium_feature_line("Blurred signals &amp; screener results", icon="&#10003;",
                                       icon_color="#475569", text_color="#64748B"),
                _premium_feature_line("Future Pro upgrade will cost $7 / month", icon="&#10003;",
                                       icon_color="#475569", text_color="#64748B"),
                _premium_feature_line("Daily personalized radar", "limited version", icon="&#8722;",
                                       icon_color="#475569", text_color="#64748B"),
                _premium_feature_line("Portfolio rebalancing tips", "limited version", icon="&#8722;",
                                       icon_color="#475569", text_color="#64748B"),
                _premium_feature_line("Establish your own deepdives", "limited version", icon="&#8722;",
                                       icon_color="#475569", text_color="#64748B"),
            ])
            st.markdown(
                '<div class="hesty-premium-title-future">Future Free Plan (Post-Launch)</div>'
                f'<div>{_future_features}</div>',
                unsafe_allow_html=True,
            )
            st.button("Coming Soon", key="premium_future_coming_soon", disabled=True)


def render_settings():
    import database

    st.markdown("### Settings")

    if current_user.is_logged_in:
        user_email = current_user.email
        is_premium = database.is_premium_user(user_email)

        with st.container(border=True):
            st.markdown("#### Email preferences")
            prefs = database.get_user_preferences(user_email)

            # 3 duidelijk GESCHEIDEN e-mails, elk met een eigen subkop --
            # voorheen stonden de 3 signalen-checkboxes en de daily/weekly-
            # toggles allemaal los onder elkaar, zonder dat de opmaak
            # duidelijk maakte dat het om 3 aparte mails gaat (en welke
            # instelling bij welke mail hoort).
            st.markdown("**Weekly signals email**")
            st.caption("Pick which signal type(s) you want -- delivered together in 1 combined email, once a week.")
            wants_momentocrats = st.checkbox(
                "Momentocrats -- technical momentum + fundamental quality combo",
                value=prefs.get("wants_momentocrats_email", False),
            )
            wants_snowball = st.checkbox(
                "Snowballers -- quality stocks below fair value, for the long term",
                value=prefs.get("wants_snowball_email", False),
            )
            wants_rocket = st.checkbox(
                "Rocket List -- accelerating growth + momentum",
                value=prefs.get("wants_rocket_email", False),
            )

            st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
            st.markdown("**Daily screener email**")
            wants_daily = st.checkbox(
                "Receive the daily screener email (swing-trade signals, weekdays)",
                value=prefs.get("wants_daily_email", False),
            )
            region_options = ["EU", "US_East", "US_West"]
            region_labels = {
                "EU": "Europe (~07:00 CET / 08:00 CEST)",
                "US_East": "US East (~07:00 ET)",
                "US_West": "US West (~07:00 PT)",
            }
            email_region = st.selectbox(
                "Morning delivery time (for the daily email)",
                region_options,
                index=region_options.index(prefs.get("email_region", "EU")),
                format_func=lambda x: region_labels[x],
            )

            st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
            st.markdown("**Weekly portfolio email**")
            wants_portfolio = st.checkbox(
                "Receive the weekly portfolio email (status + news for your own positions)",
                value=prefs["wants_portfolio_email"],
            )
            st.markdown("---")
            st.markdown("**Wealth Engine**")
            financial_independence_target = st.number_input(
                "Financial Independence target (annual passive cashflow, \u20ac)",
                min_value=0, step=1000,
                value=int(prefs.get("financial_independence_target") or 60000),
                help="Used by the Snowball Milestones on the Wealth Engine (Analyze) to determine "
                     "when your projected passive cashflow reaches full financial independence.",
            )
            st.markdown("---")
            st.markdown("**AI response language**")
            st.caption(
                "The Cockpit Briefing and Cognitive Scan normally detect your language "
                "automatically from your browser. Force a specific language here if that "
                "ever picks the wrong one."
            )
            _lang_options = ["auto", "nl", "en"]
            _lang_labels = {"auto": "Automatic (detect from browser)", "nl": "Nederlands", "en": "English"}
            ai_response_language = st.selectbox(
                "AI response language", _lang_options,
                index=_lang_options.index(prefs.get("ai_response_language") or "auto"),
                format_func=lambda x: _lang_labels[x], label_visibility="collapsed",
            )
            if st.button("Save preferences"):
                database.set_user_preferences(
                    user_email, wants_portfolio,
                    wants_daily_email=wants_daily, email_region=email_region,
                    wants_momentocrats_email=wants_momentocrats,
                    wants_snowball_email=wants_snowball, wants_rocket_email=wants_rocket,
                    financial_independence_target=financial_independence_target,
                    ai_response_language=ai_response_language,
                )
                st.success("Preferences saved!")

            if is_premium:
                st.markdown("---")
                st.markdown("**Cash / uninvested amount**")
                current_cash = database.get_cash_value(user_email)
                new_cash = st.number_input(
                    "Cash not currently invested (used for the cash% check in Analyze)",
                    min_value=0, value=int(current_cash), step=100, key="cash_input",
                )
                if st.button("Save cash amount"):
                    database.set_cash_value(user_email, new_cash)
                    st.success("Saved!")
    else:
        st.info("Log in via the menu to manage your email preferences.")


def render_confirm():
    import database as _database_for_confirm

    st.markdown("### Confirm your subscription")
    token = st.query_params.get("token", "")
    if not token:
        st.error("Missing confirmation link. Please use the link from your email.")
    elif _database_for_confirm.confirm_email_subscriber(token):
        st.success("You're all set! You'll get today's new bullish signals in your inbox every weekday morning.")
        st.page_link(discover_page, label="Back to Discover →")
    else:
        st.error("This confirmation link is invalid or has already been used.")


def render_unsubscribe():
    import database as _database_for_unsubscribe

    st.markdown("### Unsubscribe")
    token = st.query_params.get("token", "")
    if not token:
        st.error("Missing unsubscribe link. Please use the link from your email.")
    elif _database_for_unsubscribe.unsubscribe_email_subscriber(token):
        st.success("You've been unsubscribed. Sorry to see you go!")
    else:
        st.info("This link is invalid or you're already unsubscribed.")


def render_login():
    import database as _database_for_login

    _reset_token = st.query_params.get("reset_token")

    if current_user.is_logged_in:
        st.info("You're already logged in.")
        st.markdown(
            f'<a href="/{_default_view}" class="button-link" target="_self">Go to your dashboard &rarr;</a>',
            unsafe_allow_html=True,
        )
    elif _reset_token:
        # --- Iemand kwam hier via de reset-link uit de e-mail -- toon
        # het 'nieuw wachtwoord instellen'-formulier i.p.v. de normale
        # Sign In/Sign Up-toggle. ---
        st.markdown(
            '<div style="max-width:420px; margin:2rem auto 0 auto; text-align:center;">'
            '<h2 style="margin-bottom:0.3rem;">Set a new password</h2>'
            '</div>',
            unsafe_allow_html=True,
        )
        reset_col_l, reset_col_mid, reset_col_r = st.columns([1, 2, 1])
        with reset_col_mid:
            new_password = st.text_input("New password", type="password", key="reset_new_password",
                                          help="At least 8 characters.")
            new_password_confirm = st.text_input("Confirm new password", type="password", key="reset_new_password_confirm")
            if st.button("Set new password", type="primary", key="reset_submit"):
                if len(new_password) < 8:
                    st.error("Password must be at least 8 characters.")
                elif new_password != new_password_confirm:
                    st.error("Passwords don't match.")
                else:
                    success, message = _database_for_login.reset_password_with_token(_reset_token, new_password)
                    if success:
                        st.success(message)
                        st.page_link(login_page, label="Go to Sign In")
                    else:
                        st.error(message)
    elif st.session_state.get("show_forgot_password"):
        # --- 'Forgot password?' aangeklikt -- toon het e-mailadres-
        # formulier om een reset-link aan te vragen. ---
        st.markdown(
            '<div style="max-width:420px; margin:2rem auto 0 auto; text-align:center;">'
            '<h2 style="margin-bottom:0.3rem;">Reset your password</h2>'
            '<p style="color:#8992A3; margin-bottom:1.5rem;">Enter your email and we\'ll send you a reset link</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        forgot_col_l, forgot_col_mid, forgot_col_r = st.columns([1, 2, 1])
        with forgot_col_mid:
            forgot_email = st.text_input("Email", placeholder="you@example.com", key="forgot_password_email")
            if st.button("Send reset link", type="primary", key="forgot_password_submit"):
                if not forgot_email:
                    st.error("Enter your email address.")
                else:
                    reset_token = _database_for_login.create_password_reset_token(forgot_email)
                    if reset_token:
                        reset_url = f"https://hestys.streamlit.app/login?reset_token={reset_token}"
                        send_email(
                            to=forgot_email, subject="Reset your Hesty's password",
                            body=f"Click the link below to set a new password (valid for 1 hour):\n\n{reset_url}",
                        )
                    # BEWUST ALTIJD dezelfde, algemene bevestiging tonen --
                    # ongeacht of er echt een account/mail was, zodat een
                    # aanvaller niet kan afleiden welke e-mailadressen wel/
                    # niet bestaan.
                    st.success("If an account exists for this email, we've sent a reset link.")
            if st.button("Back to Sign In", key="back_to_signin_from_forgot"):
                st.session_state.pop("show_forgot_password", None)
                st.rerun()
    else:
        # Prefill welke tab actief moet zijn -- gezet door
        # _render_unlock_premium_button() op Discover (via st.session_state
        # + st.switch_page(), zie daar) voor bezoekers die specifiek op
        # 'Unlock premium' klikten en dus een NIEUW account willen maken,
        # niet inloggen op een bestaand account. .pop() zodat dit maar 1x
        # geldt -- een latere, gewone bezoek aan /login (bv. via de
        # zijbalk) valt terug op de normale 'Sign In'-default.
        _login_prefill_mode = st.session_state.pop("login_prefill_mode", "Sign In")

        # Complete formulier nu STRAK LINKS uitgelijnd (was gecentreerd via
        # lege zij-kolommen) -- gescoped via 1 gedeelde container-key met
        # een max-width (max-w-md), i.p.v. de oude 3-koloms-truc die alles
        # naar het midden van het scherm duwde. Dat brak de links-
        # uitgelijnde standaard van de rest van de site.
        _form_wrap_key = "login_form_wrap"
        st.markdown(
            f'<style>'
            f'.st-key-{_form_wrap_key} {{ '
            f'max-width:28rem !important; width:100% !important; margin:0 !important; '
            f'padding:0 0.25rem !important; box-sizing:border-box !important; }} '
            # Input-labels: kleine, gedempte ALL-CAPS metadata i.p.v. de
            # Streamlit-standaard labelgrootte.
            f'.hesty-login-label {{ '
            f'font-size:11px; font-weight:700; letter-spacing:0.05em; color:#64748B; '
            f'text-transform:uppercase; margin-bottom:0.35rem; display:block; }} '
            # 'Forgot password?' als compacte, gedempte ALL-CAPS metadata
            # i.p.v. gewone kleine letters.
            f'.st-key-forgot_password_wrap {{ margin:0.35rem 0 0 0 !important; }} '
            f'.st-key-forgot_password_wrap button {{ '
            f'background:transparent !important; border:none !important; box-shadow:none !important; '
            f'padding:0 !important; font-size:11px !important; font-weight:600 !important; '
            f'letter-spacing:0.05em !important; text-transform:uppercase !important; '
            f'color:#64748B !important; transition:color 0.15s ease !important; }} '
            f'.st-key-forgot_password_wrap button:hover {{ color:#CBD5E1 !important; }} '
            # 'Create account'/'Sign In'-knop: GEEN type="primary" meer --
            # dat triggert Streamlit's eigen, sterk-getemate thema-styling
            # die zelfs met !important bleef doorschemeren (zelfde patroon
            # als bij st.segmented_control). Een gewone knop, volledig
            # eigen CSS, is wél 100% betrouwbaar te overschrijven.
            # Simpelere, single-class selector (niet meer via de ouder-
            # container gekoppeld) + width:100% ook op de WRAPPER zelf --
            # anders blijft de knop binnen een krappe, om-de-tekst-heen-
            # passende wrapper hangen, ook al wil de knop zelf 100% breed.
            f'.st-key-login_submit_wrap {{ '
            f'margin-top:1rem !important; width:100% !important; display:block !important; }} '
            f'.st-key-login_submit_wrap [data-testid="stButton"] {{ width:100% !important; }} '
            f'.st-key-login_submit_wrap button {{ '
            f'display:block !important; width:100% !important; background:#10B981 !important; '
            f'color:#020617 !important; font-weight:700 !important; font-size:0.9rem !important; '
            f'padding:0.75rem 1rem !important; border-radius:12px !important; border:none !important; '
            f'box-shadow:0 4px 12px rgba(16,185,129,0.25) !important; }} '
            f'.st-key-login_submit_wrap button:hover {{ background:#059669 !important; }} '
            # Google-knop: gat naar de knop erboven fors verkleind, blijft
            # links uitgelijnd binnen dezelfde max-w-md-breedte.
            f'.st-key-{_form_wrap_key} .st-key-login_page_google {{ margin-top:0 !important; }} '
            f'</style>',
            unsafe_allow_html=True,
        )
        with st.container(key=_form_wrap_key):
            # Toggle: st.pills() -- Streamlit's eigen, native pil-widget.
            # Reageert gegarandeerd direct op een klik (geen CSS-overlay-
            # trucs meer die Streamlit's eigen click-handling in de weg
            # konden zitten).
            st.markdown(
                """
                <style>
                [data-testid="stPills"] {
                    background-color: rgba(15, 23, 42, 0.6) !important;
                    border: 1px solid rgb(15, 23, 42) !important;
                    border-radius: 0.5rem !important;
                    padding: 2px !important;
                    width: fit-content !important;
                    margin-bottom: 1.5rem !important;
                }
                [data-testid="stPills"] button[aria-selected="true"] {
                    background-color: rgba(30, 41, 59, 0.6) !important;
                    color: rgb(52, 211, 153) !important;
                    font-weight: 700 !important;
                    font-size: 0.75rem !important;
                    letter-spacing: 0.05em !important;
                    border-radius: 0.375rem !important;
                    border: none !important;
                }
                [data-testid="stPills"] button[aria-selected="false"] {
                    background-color: transparent !important;
                    color: rgb(100, 116, 139) !important;
                    font-weight: 500 !important;
                    font-size: 0.75rem !important;
                    letter-spacing: 0.05em !important;
                    border: none !important;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )
            _login_prefill_pill = "SIGN UP" if _login_prefill_mode == "Sign Up" else "SIGN IN"
            active_tab = st.pills(
                label="Mode", options=["SIGN IN", "SIGN UP"], default=_login_prefill_pill,
                label_visibility="collapsed", key="login_pills_toggle",
            )
            if active_tab is None:  # kan gebeuren als je 'm handmatig deselecteert
                active_tab = "SIGN IN"
            login_mode = "Sign Up" if active_tab == "SIGN UP" else "Sign In"

            # Titel + subtekst reageren live op de actieve tab -- 'Welcome
            # back' is verwarrend voor iemand die net op 'Unlock premium'
            # klikte om een NIEUW account aan te maken, niet om terug te
            # keren naar een bestaand account. Bij Sign Up specifiek staat
            # de 'Early Access Lifetime'-boodschap er nu ook -- de plek
            # waar iedereen die zich registreert 'm sowieso ziet, dus
            # niemand mist de deal.
            if login_mode == "Sign Up":
                _login_title = "Create your free account"
                _login_subtext = (
                    'LAUNCH SPECIAL | ALL PREMIUM FEATURES (INCLUDING ALL FUTURE RELEASES) ARE 100% '
                    'UNLOCKED. JOIN AS AN EARLY ADOPTER TO LOCK IN YOUR LIFETIME FREE PRO STATUS '
                    'BEFORE THE DOOR CLOSES.'
                )
                _login_subtext_style = (
                    'color:#34D399; font-size:11px; font-weight:600; letter-spacing:0.05em; '
                    'text-transform:uppercase; line-height:1.6; max-width:28rem; display:block; '
                    'margin-top:0.5rem; margin-bottom:1.5rem;'
                )
            else:
                _login_title = "Welcome back"
                _login_subtext = "Sign in or create an account in seconds."
                _login_subtext_style = (
                    'color:#8992A3; font-size:0.75rem; font-weight:600; letter-spacing:0.04em; '
                    'text-transform:uppercase;'
                )
            st.markdown(
                f'<div style="max-width:28rem; margin:0 0 1.5rem 0; text-align:left;">'
                f'<h2 class="hero-headline" style="margin-bottom:0.3rem; text-transform:uppercase;">'
                f'{_login_title}</h2>'
                f'<p style="{_login_subtext_style}">{_login_subtext}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

            if login_mode == "Sign In":
                st.markdown('<span class="hesty-login-label">Email</span>', unsafe_allow_html=True)
                login_email = st.text_input("Email", placeholder="you@example.com", key="login_email",
                                             label_visibility="collapsed")
                st.markdown('<span class="hesty-login-label">Password</span>', unsafe_allow_html=True)
                login_password = st.text_input("Password", type="password", key="login_password",
                                                label_visibility="collapsed")
                with st.container(key="forgot_password_wrap"):
                    if st.button("Forgot password?", key="forgot_password_trigger", type="tertiary"):
                        st.session_state["show_forgot_password"] = True
                        st.rerun()
                with st.container(key="login_submit_wrap"):
                    _login_submit_clicked = st.button("Sign In", key="login_submit", use_container_width=True)
                if _login_submit_clicked:
                    if not login_email or not login_password:
                        st.error("Enter both your email and password.")
                    else:
                        success, result = _database_for_login.verify_password_login(login_email, login_password)
                        if success:
                            st.session_state["password_auth_email"] = login_email
                            st.session_state["password_auth_name"] = result
                            _new_token = _database_for_login.create_session_token(login_email)
                            _cookie_controller.set("hestys_session_token", _new_token)
                            st.query_params["view"] = "today"
                            st.rerun()
                        else:
                            st.error(result)
            else:
                st.markdown('<span class="hesty-login-label">Name</span>', unsafe_allow_html=True)
                signup_name = st.text_input("Name", placeholder="Your name", key="signup_name",
                                             label_visibility="collapsed")
                st.markdown('<span class="hesty-login-label">Email</span>', unsafe_allow_html=True)
                signup_email = st.text_input("Email", placeholder="you@example.com", key="signup_email",
                                              label_visibility="collapsed")
                st.markdown('<span class="hesty-login-label">Password</span>', unsafe_allow_html=True)
                signup_password = st.text_input("Password", type="password", key="signup_password",
                                                 help="At least 8 characters.", label_visibility="collapsed")
                st.markdown('<span class="hesty-login-label">Confirm password</span>', unsafe_allow_html=True)
                signup_password_confirm = st.text_input("Confirm password", type="password",
                                                          key="signup_password_confirm", label_visibility="collapsed")
                with st.container(key="login_submit_wrap"):
                    _signup_submit_clicked = st.button("Create account", key="signup_submit", use_container_width=True)
                if _signup_submit_clicked:
                    if not signup_name or not signup_email or not signup_password:
                        st.error("Fill in all fields.")
                    elif "@" not in signup_email:
                        st.error("Enter a valid email address.")
                    elif len(signup_password) < 8:
                        st.error("Password must be at least 8 characters.")
                    elif signup_password != signup_password_confirm:
                        st.error("Passwords don't match.")
                    else:
                        success, message = _database_for_login.sign_up_with_password(signup_email, signup_name, signup_password)
                        if success:
                            st.session_state["password_auth_email"] = signup_email
                            st.session_state["password_auth_name"] = signup_name
                            _new_token = _database_for_login.create_session_token(signup_email)
                            _cookie_controller.set("hestys_session_token", _new_token)
                            st.query_params["view"] = "today"
                            st.rerun()
                        else:
                            st.error(message)

            st.markdown(
                '<div style="display:flex; align-items:center; gap:0.75rem; margin:1rem 0 1rem 0;">'
                '<div style="flex:1; height:1px; background:rgba(137,146,163,0.25);"></div>'
                '<span style="color:#8992A3; font-size:0.8rem;">OR</span>'
                '<div style="flex:1; height:1px; background:rgba(137,146,163,0.25);"></div>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.button("Continue with Google", on_click=st.login, key="login_page_google")


def render_support():
    st.markdown(
        _uniform_section_header_html("Support &amp; Help", "support_agent", is_first=True),
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="color:#64748B; font-size:0.75rem; font-weight:600; text-transform:uppercase; '
        'letter-spacing:0.03em; margin-bottom:2rem;">'
        'QUESTIONS, IDEAS, OR SOMETHING NOT WORKING AS EXPECTED? CHECK THE FAQ BELOW OR SEND US A '
        'MESSAGE DIRECTLY.</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="hesty-support-subhead">Frequently Asked Questions</div>',
        unsafe_allow_html=True,
    )

    # FAQ als zachte, afgeronde dashboard-strips i.p.v. de scherpe,
    # paginabrede standaard-accordeonlijnen -- st.expander() blijft het
    # klap-mechanisme (geen custom JS-accordeon nodig, dat bracht eerder
    # elders onnodige complexiteit), maar volledig herstyled via CSS.
    st.markdown(
        """
        <style>
        .hesty-support-subhead {
            color: #E2E8F0; font-size: 0.85rem; font-weight: 700; text-transform: uppercase;
            letter-spacing: 0.05em; margin-top: 2rem; margin-bottom: 1rem; display: block;
        }
        @media (min-width: 768px) { .hesty-support-subhead { font-size: 1rem !important; } }
        div[data-testid="stExpander"] {
            background-color: rgba(15,23,42,0.3) !important;
            border: 1px solid rgba(30,41,59,0.4) !important;
            border-radius: 14px !important;
            margin-bottom: 0.75rem !important;
            max-width: 56rem;
            overflow: hidden !important;
        }
        div[data-testid="stExpander"] details {
            background-color: transparent !important;
        }
        div[data-testid="stExpander"] summary {
            padding: 1rem !important;
            background-color: transparent !important;
        }
        div[data-testid="stExpander"] summary p {
            color: #F1F5F9 !important;
            font-weight: 600 !important;
            font-size: 0.9rem !important;
        }
        div[data-testid="stExpanderDetails"] {
            padding: 0 1rem 1rem 1rem !important;
            background-color: transparent !important;
        }
        div[data-testid="stExpanderDetails"] p {
            color: #94A3B8 !important;
            font-size: 0.82rem !important;
            line-height: 1.6 !important;
            margin-top: 0.5rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("What does Discover do?", key="what_does_discover_do_expander"):
        st.write(
            "It scans the AEX, Nasdaq-100, S&P 500, DAX, and CAC 40 (weekly and daily variants) "
            "for stocks that just turned bullish on a Supertrend indicator, scored on technical "
            "and fundamental factors. It's public, no login required."
        )

    with st.expander("Can I import my transaction history from my broker?", key="can_i_import_my_transaction_history_from_my_broker_expander"):
        st.write(
            "Yes, for DEGIRO -- under My Portfolio, 'Import from a broker'. Using a different "
            "broker? Let us know via the contact form below, and we'll look into adding it."
        )

    with st.expander("Is my portfolio data private?", key="is_my_portfolio_data_private_expander"):
        st.write(
            "Yes. Your tracked positions are only visible to you, tied to your Google account. "
            "We never share or sell your data."
        )

    with st.expander("What's the difference between Free and Premium?", key="what_s_the_difference_between_free_and_premium_expander"):
        st.write(
            "Right now, everyone gets full Premium access for free as part of our Early Access "
            "launch -- unlimited tracked positions, all Discover signals unblurred, and every "
            "future Premium feature we build. Join now as an Early Adopter and that stays free "
            "for you for life. After launch, the free plan will be limited to 10 tracked positions "
            "with blurred signals -- see the Premium page for the full breakdown."
        )

    with st.expander("How do I change what emails I receive?", key="how_do_i_change_what_emails_i_receive_expander"):
        st.write(
            "Log in, go to Settings, and use the Email preferences section to toggle the weekly "
            "screener, daily screener, and/or portfolio emails on or off."
        )

    st.markdown(
        '<div class="hesty-support-subhead">Send Us a Message</div>',
        unsafe_allow_html=True,
    )

    _support_form_key = "support_contact_form"
    st.markdown(
        f'<style>'
        f'.st-key-{_support_form_key} {{ '
        f'max-width:28rem !important; width:100% !important; box-sizing:border-box !important; }} '
        f'.st-key-{_support_form_key} [data-testid="stTextInput"], '
        f'.st-key-{_support_form_key} [data-testid="stSelectbox"], '
        f'.st-key-{_support_form_key} [data-testid="stTextArea"] {{ '
        f'width:100% !important; max-width:100% !important; }} '
        f'.hesty-support-label {{ '
        f'font-size:11px; font-weight:700; letter-spacing:0.05em; color:#64748B; '
        f'text-transform:uppercase; margin-bottom:0.35rem; display:block; }} '
        f'.st-key-support_submit_wrap {{ '
        f'margin-top:1rem !important; width:100% !important; display:block !important; }} '
        f'.st-key-support_submit_wrap [data-testid="stButton"] {{ width:100% !important; }} '
        f'.st-key-support_submit_wrap button {{ '
        f'display:block !important; width:100% !important; background:#10B981 !important; '
        f'color:#020617 !important; font-weight:700 !important; font-size:0.9rem !important; '
        f'padding:0.75rem 1rem !important; border-radius:12px !important; border:none !important; '
        f'box-shadow:0 4px 12px rgba(16,185,129,0.25) !important; }} '
        f'.st-key-support_submit_wrap button:hover {{ background:#059669 !important; }} '
        f'</style>',
        unsafe_allow_html=True,
    )
    with st.container(key=_support_form_key):
        st.markdown('<span class="hesty-support-label">Your email</span>', unsafe_allow_html=True)
        contact_email = st.text_input("Your email", label_visibility="collapsed")
        st.markdown('<span class="hesty-support-label">Type</span>', unsafe_allow_html=True)
        message_type = st.selectbox(
            "Type", ["Idea", "Problem / bug", "Billing question", "Business inquiry", "Other"],
            label_visibility="collapsed",
        )
        st.markdown('<span class="hesty-support-label">Message</span>', unsafe_allow_html=True)
        message_body = st.text_area("Message", height=150, label_visibility="collapsed")

        with st.container(key="support_submit_wrap"):
            _support_submit_clicked = st.button("Send Message \u2192", key="support_submit")
        if _support_submit_clicked:
            if not contact_email or not message_body.strip():
                st.error("Please fill in your email and a message before sending.")
            else:
                support_email = st.secrets.get("support", {}).get("email")
                if not support_email:
                    st.error("Support inbox isn't configured yet -- please try again later.")
                else:
                    success = send_email(
                        subject=f"[Hesty's Support] {message_type} from {contact_email}",
                        body_text=message_body,
                        to_email=support_email,
                    )
                    if success:
                        st.success("Thanks! Your message has been sent -- we'll get back to you by email.")
                    else:
                        st.error("Something went wrong sending your message -- please try again later.")


def render_privacy():
    st.markdown("### Privacy")
    st.caption("Plain language, not a legal document -- if you have questions beyond this, "
               "just ask via Support.")

    st.markdown(
        f"""
        <div style="background: rgba(137,146,163,0.05);
                    border: 1px solid rgba(137,146,163,0.2); border-radius: 12px;
                    padding: 1.25rem 1.5rem; margin: 0.75rem 0 1.25rem 0;">
            <div style="color:#8992A3; font-weight:700; font-size:0.75rem; letter-spacing:1.5px; text-transform:uppercase;">
                {_icon_span("lock", size_px=14, color="#8992A3")} Your data is pseudonymized
            </div>
            <div style="color:#EAEDF1; font-size:1rem; font-weight:600; margin-top:6px; line-height:1.5;">
                Your email address is never stored in readable form alongside your portfolio.
            </div>
            <div style="color:#8992A3; font-size:0.9rem; margin-top:8px; line-height:1.6;">
                Every position, transaction, and preference is stored under a one-way hash --
                a scrambled, irreversible code -- instead of your actual email address. Even
                we can't casually see whose data is whose just by looking at the database.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("What we collect", key="what_we_collect_expander"):
        st.write(
            "When you log in (via Google or Microsoft), we get your email address and name. "
            "Beyond that, we only store what you actively enter: the positions and watchlist "
            "items you add, any buy/sell transactions you log (or import from a broker), your "
            "risk profile answers, your email preferences, and your cash amount if you fill "
            "one in."
        )

    with st.expander("Why we collect it", key="why_we_collect_it_expander"):
        st.write(
            "Purely to show you your own data back (My Portfolio, Analyze, your personalized "
            "Today briefing), and to send you the daily/weekly emails you've opted into. "
            "Nothing here is used to build a profile of you for advertising -- there are no ads "
            "on Hesty's, and there never will be."
        )

    with st.expander("Who can see it", key="who_can_see_it_expander"):
        st.write(
            "Only you, when logged into your own account. As explained above, your portfolio "
            "and transaction data is stored under a hashed identifier, not your readable email "
            "address. A small, separate table maps that hash back to your real address -- purely "
            "so we can still send you the emails you've opted into. We only ever look at "
            "anything ourselves to fix a bug or help with a support question."
        )

    with st.expander("Third parties involved", key="third_parties_involved_expander"):
        st.write(
            "Supabase hosts our database. Google or Microsoft handle the login itself (we "
            "never see your password). Stripe will handle payments once Premium is actually "
            "for sale. Market data (prices, company info) comes from Yahoo Finance -- no "
            "personal data is sent there, just ticker symbols."
        )

    with st.expander("Your control over it", key="your_control_over_it_expander"):
        st.write("You can remove any position, watchlist item, or transaction yourself at any time.")
        st.caption("Want your entire account and its data deleted? Reach out via:")
        st.page_link(support_page, label="Support")

    with st.expander("Cookies", key="cookies_expander"):
        st.write(
            "A login session cookie is used to keep you signed in -- that's required for "
            "Google/Microsoft login to work at all. We don't use tracking or advertising cookies."
        )


# ============================================================
# NAVIGATIE (stap B1): st.navigation i.p.v. handmatige ?view=-routing --
# geen volledige pagina-herlading meer bij het klikken tussen pagina's.
# Alle render_XXX()-functies hierboven (stap A) worden nu rechtstreeks
# als pagina's geregistreerd.
# ============================================================
today_page = st.Page(render_today, title="Today", url_path="today", default=current_user.is_logged_in)
discover_page = st.Page(render_discover_dispatcher, title="Discover", url_path="discover", default=not current_user.is_logged_in)
discover_sectors_themes_page = st.Page(
    render_discover_sectors_themes, title="Sectors & Themes", url_path="discover-sectors-themes",
)
discover_earnings_surprises_page = st.Page(
    render_discover_earnings_surprises, title="Earnings Surprises", url_path="discover-earnings-surprises",
)
portfolio_page = st.Page(render_portfolio, title="My Portfolio", url_path="portfolio")
wealth_engine_page = st.Page(render_wealth_engine, title="Wealth Engine", url_path="wealth-engine")
analyze_page = st.Page(render_analyze, title="Analyze", url_path="analyze")
settings_page = st.Page(render_settings, title="Settings", url_path="settings")
premium_page = st.Page(render_premium, title="Premium", url_path="premium")
support_page = st.Page(render_support, title="Support", url_path="support")
privacy_page = st.Page(render_privacy, title="Privacy", url_path="privacy")
login_page = st.Page(render_login, title="Login", url_path="login")
confirm_page = st.Page(render_confirm, title="Confirm", url_path="confirm")
unsubscribe_page = st.Page(render_unsubscribe, title="Unsubscribe", url_path="unsubscribe")

all_pages = [
    today_page, discover_page, discover_sectors_themes_page, discover_earnings_surprises_page,
    portfolio_page, wealth_engine_page, analyze_page, settings_page,
    premium_page, support_page, privacy_page, login_page, confirm_page, unsubscribe_page,
]
pg = st.navigation(all_pages, position="hidden")

with st.sidebar:
    st.markdown(
        f"""
        <div class="app-header" style="border-bottom:none; padding:0 0 0.5rem 0; margin-bottom:0.5rem;">
            <div class="app-header-top">
                <img src="data:image/png;base64,{_LOGO_ICON_B64}" width="31" height="38"
                     style="object-fit:contain; flex-shrink:0;" alt="Hestys logo" />
                <div>
                    <h1 class="sidebar-logo-title">HESTYS</h1>
                    <div class="tagline" style="margin-top:0.02rem;">YOUR INVESTING EDGE</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Sidebar-achtergrond EXACT gelijk aan de hoofd-app (monochroom
    # effect) + een flinterdunne rand rechts i.p.v. een zichtbaar
    # kleurverschil tussen zijbalk en pagina. #101825 is de EXACTE
    # backgroundColor uit .streamlit/config.toml's [theme]-blok.
    # Streamlit's sidebar gebruikt standaard secondaryBackgroundColor
    # (#1B2536, zichtbaar lichter/blauwer), vandaar het kleurverschil.
    #
    # BELANGRIJKE FIX t.o.v. de vorige poging: alle selectors hieronder
    # gebruiken nu [data-testid="..."] ZONDER een voorafgaand tag-type
    # (dus niet meer 'div[data-testid=...]') -- recente Streamlit-versies
    # renderen de zijbalk als <section>, niet als <div>, waardoor een
    # tag-gekwalificeerde selector als 'div[data-testid="stSidebar"]'
    # NOOIT matchte en de achtergrondkleur dus nooit daadwerkelijk werd
    # overschreven, ongeacht !important. Bovendien nu 3 mogelijke
    # wrapper-lagen tegelijk geraakt (stSidebar zelf + 2 bekende, recente
    # interne wrapper-testid's) als extra vangnet, en zowel 'background'
    # als 'background-color' gezet (voor het geval Streamlit's eigen CSS
    # de 'background'-shorthand gebruikt, die anders alsnog had kunnen
    # doorschemeren ondanks een background-color-override).
    _active_url_path = getattr(pg, "url_path", "")
    # 'today_page' is de default-pagina (default=is_logged_in) -- Streamlit
    # serveert een default-pagina op het 'kale' pad, waardoor pg.url_path
    # dan een LEGE string teruggeeft i.p.v. 'today'. Zonder deze regel
    # matchte de highlight-logica hieronder Today dus NOOIT.
    if _active_url_path == "" and current_user.is_logged_in:
        _active_url_path = "today"
    # Discover is de default-pagina voor NIET-ingelogde bezoekers
    # (default=not current_user.is_logged_in) -- exact dezelfde
    # 'lege string op het kale pad'-eigenaardigheid als hierboven bij
    # Today, alleen dan voor het uitgelogde geval. Zonder deze regel
    # matchte de highlight-logica Discover dus nooit wanneer je
    # uitgelogd was.
    if _active_url_path == "" and not current_user.is_logged_in:
        _active_url_path = "discover"
    # 'Discover' en 'Signature Signals' wijzen naar DEZELFDE url (/discover)
    # -- een CSS-regel op basis van de href alleen kan ze dus NOOIT uit
    # elkaar houden (dat verklaarde de rare uitlijning/'snijdende balk').
    # Vanaf nu wordt ELK item gescoped via z'n EIGEN st.container(key=...),
    # niet via de href -- 100% ondubbelzinnig, ongeacht welke 2 items
    # toevallig naar dezelfde pagina linken.
    _nav_css_parts = ["""
    <style>
    [data-testid="stSidebarNav"] { display: none; }
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] > div,
    [data-testid="stSidebarContent"],
    [data-testid="stSidebarUserContent"] {
        background: #101825 !important;
        background-color: #101825 !important;
    }
    [data-testid="stSidebar"] {
        border-right: 1px solid rgba(148,163,184,0.15) !important;
    }
    /* Sidebar-brede verkleining van Streamlit's eigen tussenruimte tussen
       gestapelde st.container()'s -- elk hoofdmenu-item (en de Discover-
       subnav-groep) is een EIGEN container, en Streamlit's standaard
       tussenruimte daartussen (~1rem) was de daadwerkelijke bron van de
       'te los'-uitstraling, niet de padding/margin op de items zelf. */
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.2rem !important;
    }
    /* Today/My Portfolio/Analyze/Discover: allemaal ECHTE st.button()'s
       i.p.v. st.page_link() -- st.page_link() rendert een
       <a data-testid="stPageLink-NavLink"> met Streamlit's eigen,
       automatisch gegenereerde 'emotion'-CSS-klassen, die zelfs met
       !important niet naar een vaste, kleine hoogte te dwingen bleken
       (de hover-achtergrond bleef over de buurknop heen lopen, EN de
       icoon-positionering week net iets af van een <button>). Een
       st.button() hebben we elders in dit project (login-knop, close-
       knop) al herhaaldelijk volledig kunnen herstijlen, dus dat is de
       betrouwbaardere route -- nu voor ALLE 4 hoofdknoppen consequent
       hetzelfde widget-type, dus gegarandeerd identieke uitlijning. */
    .st-key-nav_discover, .st-key-nav_today, .st-key-nav_portfolio, .st-key-nav_wealth_engine, .st-key-nav_analyze {
        width: 100% !important;
    }
    .st-key-nav_discover button, .st-key-nav_today button, .st-key-nav_portfolio button, .st-key-nav_wealth_engine button, .st-key-nav_analyze button {
        display: flex !important; align-items: center !important; justify-content: flex-start !important;
        gap: 0.75rem !important; width: 100% !important;
        font-family: 'Inter', sans-serif !important; font-size: 0.92rem !important; font-weight: 600 !important;
        background: transparent !important; border: none !important; box-shadow: none !important;
        padding: 0.3rem 0.9rem 0.3rem 0.75rem !important; border-radius: 8px !important;
        color: #EAEDF1 !important; margin: 0 !important; height: auto !important; min-height: 0 !important;
    }
    .st-key-nav_discover button:hover, .st-key-nav_today button:hover, .st-key-nav_portfolio button:hover, .st-key-nav_wealth_engine button:hover, .st-key-nav_analyze button:hover {
        background: rgba(255,255,255,0.04) !important; color: #EAEDF1 !important; border: none !important;
    }
    /* Support/Premium: verhuisd naar onderaan de sidebar, als kleinere,
       gedempte 'utility'-knoppen i.p.v. dezelfde nadruk als de 3
       hoofdknoppen hierboven. */
    .st-key-nav_support, .st-key-nav_premium {
        width: 100% !important;
    }
    .st-key-nav_support button, .st-key-nav_premium button {
        display: flex !important; align-items: center !important; justify-content: flex-start !important;
        gap: 0.6rem !important; width: 100% !important;
        font-family: 'Inter', sans-serif !important; font-size: 11px !important; font-weight: 700 !important;
        letter-spacing: 0.06em !important; text-transform: uppercase !important;
        background: transparent !important; border: none !important; box-shadow: none !important;
        padding: 0.3rem 0.75rem !important; border-radius: 8px !important;
        color: #64748B !important; margin: 0 !important; height: auto !important; min-height: 0 !important;
        transition: color 0.2s ease !important;
    }
    .st-key-nav_support button:hover, .st-key-nav_premium button:hover {
        background: transparent !important; color: #CBD5E1 !important; border: none !important;
    }
    /* Support/Premium verankerd aan de ONDERKANT van de sidebar via
       flexbox. Via de Inspect-HTML die je aanleverde bleek de ECHTE
       structuur dieper genest te zijn dan mijn vorige poging aannam:
       stSidebarUserContent > kale <div> (geen testid) > EEN grote
       stVerticalBlock die ALLE nav-items als broertjes bevat (elk
       gewikkeld in een <div data-testid="stLayoutWrapper">). Mijn
       vorige CSS zette display:flex alleen op stSidebarUserContent
       zelf -- die heeft maar 1 kind (die kale wrapper-div), dus er was
       geen echte flex-verdeling mogelijk tussen de navigatie-items.
       Nu alle 3 lagen expliciet flex gemaakt, en margin-top:auto op de
       stLayoutWrapper die de utilities-container bevat (met :has(),
       want margin:auto moet op de ECHTE flex-item staan, niet op een
       kind daarbinnen). */
    [data-testid="stSidebarUserContent"] {
        display: flex !important;
        flex-direction: column !important;
        min-height: 100vh !important;
    }
    [data-testid="stSidebarUserContent"] > div {
        display: flex !important;
        flex-direction: column !important;
        flex: 1 !important;
        min-height: 0 !important;
    }
    [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] {
        display: flex !important;
        flex-direction: column !important;
        flex: 1 !important;
        min-height: 0 !important;
    }
    div[data-testid="stLayoutWrapper"]:has(.st-key-hestys_utilities_container) {
        margin-top: auto !important;
    }
    .st-key-hestys_utilities_container {
        padding-top: 15px !important;
        border-top: 1px solid rgba(255,255,255,0.05) !important;
        margin-bottom: 20px !important;
    }
    """]
    # Container-key -> url_path-mapping, voor de actieve-status-highlight.
    # 'nav_discover' licht op zodra je op ÉÉN van de 3 Discover-detail-
    # pagina's zit (niet alleen exact /discover) -- die pagina's hebben
    # geen eigen sidebar-item meer, dus lichten ze allemaal hetzelfde
    # ene 'Discover'-item op.
    _main_key_by_path = {
        "today": "nav_today", "portfolio": "nav_portfolio", "wealth-engine": "nav_wealth_engine",
        "analyze": "nav_analyze", "support": "nav_support", "premium": "nav_premium",
        # Discover EN z'n 2 losse detail-pagina's (nog steeds bereikbaar
        # via een directe URL, ook al staan ze niet meer als aparte
        # items in de sidebar) lichten allemaal hetzelfde ene
        # 'Discover'-item in de sidebar op -- er is nu geen aparte
        # sub-item-highlight meer nodig.
        "discover": "nav_discover", "discover-sectors-themes": "nav_discover",
        "discover-earnings-surprises": "nav_discover",
    }
    if _active_url_path in _main_key_by_path:
        # 'De Bloomberg-wet': geen groot, afgerond groenblauw blok meer
        # achter de actieve knop -- uitsluitend heldere witte tekst plus
        # een flinterdun, oplichtend streepje aan de linkerrand. Zowel
        # 'button' (Today/My Portfolio/Analyze/Support/Premium) als 'a'
        # (Discover, die nog st.page_link() gebruikt) worden hier
        # geraakt -- exact dezelfde uitlijning/padding-compensatie voor
        # allebei, dus Discover lijnt kaarsrecht uit met de rest.
        _nav_css_parts.append(f"""
    .st-key-{_main_key_by_path[_active_url_path]} button,
    .st-key-{_main_key_by_path[_active_url_path]} a {{
        color: #FFFFFF !important;
        font-weight: 700 !important;
        background: transparent !important;
        border-radius: 0 !important;
        border-left: 2px solid #34D399 !important;
        padding-left: calc(0.75rem - 2px) !important;
    }}
    .st-key-{_main_key_by_path[_active_url_path]} a * {{
        font-weight: 700 !important;
    }}
    """)
    _nav_css_parts.append("</style>")
    st.markdown("".join(_nav_css_parts), unsafe_allow_html=True)

    # CSS-injectie van de originele SVG-lijniconen bleek onbetrouwbaar
    # (verscheen soms helemaal niet) -- overgestapt op Streamlit's officieel
    # ondersteunde Material Symbols (via icon=":material/xxx:"), die een
    # subtiele, professionele lijn-stijl hebben -- veel dichter bij de
    # oorspronkelijke iconen dan emoji, en betrouwbaar (geen CSS-truc nodig).
    #
    # 'Discover' was tot nu toe nog een st.page_link() (de reden was
    # gedeelde URL met de subpagina's-in-de-sidebar) -- die subpagina's
    # staan er niet meer, dus die reden vervalt. Nu ECHT hetzelfde
    # widget-type als Today/My Portfolio/Analyze (st.button() +
    # st.switch_page()), wat de scheve uitlijning definitief oplost --
    # st.page_link() en st.button() renderen intern nu eenmaal net
    # anders (andere padding/icoon-positionering), ongeacht hoe
    # identiek de CSS eromheen is.
    with st.container(key="nav_discover"):
        if st.button("DISCOVER", key="navbtn_discover", icon=":material/search:"):
            st.switch_page(discover_page)
    # Subpagina's staan NERGENS meer los in de sidebar -- niet voor
    # ingelogde gebruikers (die krijgen de horizontale pills-balk
    # bovenaan de Discover-pagina zelf) en ook niet voor niet-ingelogde
    # bezoekers (die zien uitsluitend: Discover, Today, My Portfolio,
    # Analyze, Log in -- een harde, ondubbelzinnige lijst zonder
    # uitzondering).
    # Today/My Portfolio/Analyze: overgestapt van st.page_link() naar
    # st.button() + st.switch_page(). st.page_link() rendert een
    # <a data-testid="stPageLink-NavLink"> met Streamlit's eigen,
    # automatisch gegenereerde 'emotion'-CSS-klassen, die zelfs
    # met !important niet naar een vaste, kleine hoogte te dwingen
    # bleken -- de hover-achtergrond bleef daardoor over de buurknop
    # heen lopen. st.button() hebben we elders in dit project (login-
    # knop, close-knop, etc.) al herhaaldelijk volledig kunnen
    # herstijlen, dus dat is de betrouwbaardere route hier ook.
    with st.container(key="nav_today"):
        if st.button("TODAY", key="navbtn_today", icon=":material/calendar_today:"):
            st.switch_page(today_page)
    with st.container(key="nav_portfolio"):
        if st.button("MY PORTFOLIO", key="navbtn_portfolio", icon=":material/work:"):
            st.switch_page(portfolio_page)
    with st.container(key="nav_wealth_engine"):
        if st.button("WEALTH ENGINE", key="navbtn_wealth_engine", icon=":material/trending_up:"):
            st.switch_page(wealth_engine_page)
    with st.container(key="nav_analyze"):
        if st.button("ANALYZE", key="navbtn_analyze", icon=":material/bar_chart:"):
            st.switch_page(analyze_page)
    # Support/Premium hard naar de onderkant van de sidebar verankerd via
    # flexbox (margin-top:auto), i.p.v. gewoon 'volgend in de rij' te
    # staan -- dat laatste plakte ze namelijk gewoon direct onder Analyze
    # i.p.v. daadwerkelijk onderaan te laten zweven.
    with st.container(key="hestys_utilities_container"):
        with st.container(key="nav_support"):
            if st.button("SUPPORT", key="navbtn_support", icon=":material/support_agent:"):
                st.switch_page(support_page)
        with st.container(key="nav_premium"):
            if st.button("PREMIUM", key="navbtn_premium", icon=":material/star:"):
                st.switch_page(premium_page)
    # Profielnaam + Log out/Log in: minimalistische all-caps links i.p.v.
    # de zware, grijze native Streamlit-knop -- exact dezelfde 11px/
    # font-bold/tracking-wider-stijl als Support/Premium, met voldoende
    # verticale ademruimte (margin-top >= 12px) tussen naam, scheidings-
    # lijn en de actie zelf, zodat het niet meer tegen elkaar aan plakt.
    st.markdown(
        f'<style>'
        f'.st-key-sidebar_profile_link a {{ '
        f'display: flex !important; align-items: center !important; gap: 0.6rem !important; '
        f'font-family: \'Inter\', sans-serif !important; font-size: 0.85rem !important; font-weight: 600 !important; '
        f'color: #EAEDF1 !important; text-decoration: none !important; padding: 0.3rem 0.75rem !important; '
        f'border-radius: 8px !important; margin: 0 !important; }} '
        f'.st-key-sidebar_profile_link a:hover {{ background: rgba(255,255,255,0.04) !important; }} '
        f'.st-key-sidebar_logout_link {{ margin-top: 14px !important; }} '
        f'.st-key-sidebar_logout_link button {{ '
        f'background: transparent !important; border: none !important; box-shadow: none !important; '
        f'padding: 0.3rem 0.75rem !important; width: 100% !important; text-align: left !important; '
        f'font-family: \'Inter\', sans-serif !important; font-size: 11px !important; font-weight: 700 !important; '
        f'letter-spacing: 0.06em !important; text-transform: uppercase !important; '
        f'color: #64748B !important; height: auto !important; min-height: 0 !important; '
        f'transition: color 0.2s ease !important; }} '
        f'.st-key-sidebar_logout_link button:hover {{ background: transparent !important; color: #FB7185 !important; }} '
        f'.st-key-sidebar_login_link {{ margin-top: 14px !important; }} '
        f'.st-key-sidebar_login_link a {{ '
        f'display: block !important; padding: 0.3rem 0.75rem !important; '
        f'font-family: \'Inter\', sans-serif !important; font-size: 11px !important; font-weight: 700 !important; '
        f'letter-spacing: 0.06em !important; text-transform: uppercase !important; '
        f'color: #64748B !important; text-decoration: none !important; transition: color 0.2s ease !important; }} '
        f'.st-key-sidebar_login_link a:hover {{ color: #34D399 !important; }} '
        f'</style>',
        unsafe_allow_html=True,
    )
    if current_user.is_logged_in:
        import database as _database_for_identity
        _database_for_identity.ensure_user_identity(current_user.email, current_user.name)
        with st.container(key="sidebar_profile_link"):
            st.page_link(settings_page, label=current_user.name, icon=":material/settings:")
        st.markdown(
            '<div style="height:1px; background-color:rgba(148,163,184,0.1); margin:12px 0.75rem 0;"></div>',
            unsafe_allow_html=True,
        )
        with st.container(key="sidebar_logout_link"):
            if st.user.is_logged_in:
                # Ingelogd via Google -- Streamlit's eigen logout-mechanisme.
                st.button("LOG OUT", on_click=st.logout, key="header_logout")
            else:
                # Ingelogd via e-mail+wachtwoord -- eigen sessie opruimen
                # (st.logout() is specifiek voor Google, raakt deze sessie niet).
                # Ook de sessie-token uit de database EN de cookie zelf
                # verwijderen -- anders zou een oude cookie na 'uitloggen'
                # je alsnog weer inloggen bij de volgende paginaverversing.
                def _password_logout():
                    import database as _database_for_logout
                    _old_token = _cookie_controller.get("hestys_session_token")
                    if _old_token:
                        _database_for_logout.delete_session_token(_old_token)
                        _cookie_controller.remove("hestys_session_token")
                    st.session_state.pop("password_auth_email", None)
                    st.session_state.pop("password_auth_name", None)
                st.button("LOG OUT", on_click=_password_logout, key="header_logout_password")
    else:
        with st.container(key="sidebar_login_link"):
            st.page_link(login_page, label="LOG IN")


pg.run()

st.markdown("<div style='height: 8rem'></div>", unsafe_allow_html=True)
st.divider()


def _footer_accordion_column_header_html(title: str, col_id: str) -> str:
    """
    2 versies van dezelfde titel in 1x meegegeven: een platte, bold
    st.markdown("**TITLE**")-look voor DESKTOP (ongewijzigd), en een
    klikbare rij met +/- -icoontje voor MOBIEL -- CSS (media query)
    kiest welke zichtbaar is, nooit allebei tegelijk. De content eronder
    (st.page_link()-weets, gewrapt in st.container(key=...)) is op
    desktop altijd volledig zichtbaar (geen max-height-beperking daar);
    op mobiel begint 'ie ingeklapt (max-height:0) en klapt open via het
    JS-scriptje onderaan de footer (_render_footer_accordion_script()).
    """
    content_key = f"footer_acc_content_{col_id}"
    return (
        f'<style>'
        f'.hesty-footer-acc-header-{col_id} {{ display:none; }} '
        f'@media (max-width:768px) {{ '
        f'.hesty-footer-title-{col_id} {{ display:none !important; }} '
        f'.hesty-footer-acc-header-{col_id} {{ display:flex !important; align-items:center; '
        f'justify-content:space-between; cursor:pointer; padding:0.7rem 0; '
        f'border-bottom:1px solid rgba(148,163,184,0.12); }} '
        f'.st-key-{content_key} {{ max-height:0; overflow:hidden; transition:max-height 0.25s ease; }} '
        f'.st-key-{content_key}.hesty-footer-acc-open {{ max-height:500px; }} '
        f'}} '
        f'</style>'
        f'<div class="hesty-footer-title-{col_id}"><b>{title}</b></div>'
        f'<div class="hesty-footer-acc-header hesty-footer-acc-header-{col_id}" data-footer-target="{content_key}">'
        f'<span style="font-weight:700; font-size:0.85rem; color:#EAEDF1;">{title}</span>'
        f'<span class="hesty-footer-acc-icon" style="color:#8992A3; font-size:1rem; '
        f'transition:transform 0.2s ease;">+</span>'
        f'</div>'
    ), content_key


def _render_footer_accordion_script() -> None:
    """
    Bindt de klik-op-titel-om-open-te-klappen-interactie voor de mobiele
    footer-accordeons. Zelfde, bevestigd betrouwbare aanpak als
    _render_insight_dismiss_autohide_script() elders op de site:
    st.components.v1.html() + event delegation op window.parent.document
    .body (overleeft Streamlit-reruns, i.p.v. losse listeners per
    element die bij een rerun weer verdwijnen). Puur client-side (geen
    st.rerun() nodig) -- voelt daardoor instant aan, geen server-round-
    trip per tik.
    """
    components.html(
        """
        <script>
        function hestyBindFooterAccordion() {
            var doc = window.parent.document;
            if (doc.body.__hestyFooterAccBound) { return; }
            doc.body.__hestyFooterAccBound = true;
            doc.body.addEventListener('click', function(e) {
                var header = e.target.closest('.hesty-footer-acc-header');
                if (!header) { return; }
                var targetKey = header.getAttribute('data-footer-target');
                var content = doc.querySelector('.st-key-' + targetKey);
                if (!content) { return; }
                var isOpen = content.classList.toggle('hesty-footer-acc-open');
                var icon = header.querySelector('.hesty-footer-acc-icon');
                if (icon) { icon.textContent = isOpen ? '\\u2212' : '+'; }
            });
        }
        hestyBindFooterAccordion();
        </script>
        """,
        height=0,
    )


footer_col1, footer_col2, footer_col3, footer_col4 = st.columns(4)
with footer_col1:
    _header_html, _content_key = _footer_accordion_column_header_html("PRODUCT", "product")
    st.markdown(_header_html, unsafe_allow_html=True)
    with st.container(key=_content_key):
        st.page_link(discover_page, label="Discover")
        st.page_link(today_page, label="Today")
        st.page_link(portfolio_page, label="My Portfolio")
        st.page_link(wealth_engine_page, label="Wealth Engine")
        st.page_link(analyze_page, label="Analyze")
with footer_col2:
    _header_html, _content_key = _footer_accordion_column_header_html("ACCOUNT", "account")
    st.markdown(_header_html, unsafe_allow_html=True)
    with st.container(key=_content_key):
        st.page_link(settings_page, label="Settings")
        st.page_link(premium_page, label="Premium")
with footer_col3:
    _header_html, _content_key = _footer_accordion_column_header_html("SUPPORT", "support")
    st.markdown(_header_html, unsafe_allow_html=True)
    with st.container(key=_content_key):
        st.page_link(support_page, label="Support")
        st.page_link(privacy_page, label="Privacy Policy")
with footer_col4:
    _header_html, _content_key = _footer_accordion_column_header_html("SOCIALS", "socials")
    st.markdown(_header_html, unsafe_allow_html=True)
    with st.container(key=_content_key):
        # Externe URL -- gewoon een rauwe <a>-link is hier veilig (in
        # tegenstelling tot interne Streamlit-paden, die st.page_link()
        # MOETEN gebruiken om de eerder gevonden 'Page Not Found'-bug te
        # vermijden).
        st.markdown(
            '<a href="https://x.com/HestysInvest" target="_blank" style="text-decoration:none; '
            'color:#8992A3; font-size:0.9rem;">X (@HestysInvest)</a>',
            unsafe_allow_html=True,
        )

_render_footer_accordion_script()

st.markdown("<div style='height: 0.75rem'></div>", unsafe_allow_html=True)
st.caption("Hesty's combines technical signals, fundamental screens, and portfolio analysis to help "
           "you research faster. It's not an automated trading strategy, and nothing here is "
           "personalized financial advice.")
st.caption(f"© {datetime.now().year} Hesty's. All rights reserved.")
