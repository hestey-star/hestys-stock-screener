"""
EENMALIG migratie-script -- zet bestaande, RAUWE e-mailadressen in de
database om naar hashes (zie database.py's module-docstring voor de
reden hierachter: privacy, niet toevallig iemands data kunnen zien bij
het rondkijken in de tabellen).

WAT DIT DOET, in volgorde:
1. Zoekt ALLE unieke, rauwe e-mailadressen op in portfolio_holdings,
   portfolio_transactions, user_preferences, en portfolio_score_history.
2. Legt voor elk gevonden adres de koppeling hash<->echt adres vast in
   de nieuwe user_identity-tabel (nodig om later nog mail te kunnen
   versturen).
3. Werkt VERVOLGENS al die tabellen bij: user_email wordt overschreven
   met de hash, niet meer het rauwe adres.

VEREISTEN VOORDAT JE DIT DRAAIT:
- De user_identity-tabel moet al bestaan (zie supabase_schema.sql)
- user_hashing.py moet in dezelfde map staan als dit script
- Je Supabase-URL en -key bij de hand (dezelfde die ook in je Streamlit
  Cloud secrets.toml staan) -- dit script vraagt er interactief naar,
  je hebt geen lokaal secrets-bestand nodig.

Gebruik: python migrate_emails_to_hashes.py
Draai dit 1x, vanuit je stock_screener-map (hestys-fresh).
"""
from __future__ import annotations

import getpass

from supabase import create_client

from user_hashing import hash_email

TABLES_WITH_USER_EMAIL = [
    "portfolio_holdings",
    "portfolio_transactions",
    "user_preferences",
    "portfolio_score_history",
]


def main():
    print("Plak je Supabase-gegevens (dezelfde als in je Streamlit Cloud secrets.toml):")
    supabase_url = input("Supabase URL: ").strip()
    supabase_key = getpass.getpass("Supabase anon/secret key (blijft onzichtbaar tijdens typen): ").strip()

    client = create_client(supabase_url, supabase_key)

    print("\n=== Stap 1: alle unieke, rauwe e-mailadressen verzamelen ===")
    all_raw_emails = set()
    for table in TABLES_WITH_USER_EMAIL:
        response = client.table(table).select("user_email").execute()
        for row in response.data:
            email = row.get("user_email")
            # Als het er al uitziet als een hash (64 hex-tekens, geen '@'), is dit
            # al gemigreerd -- overslaan.
            if email and "@" in email:
                all_raw_emails.add(email)

    print(f"{len(all_raw_emails)} uniek(e), nog-niet-gemigreerd(e) e-mailadres(sen) gevonden.")
    if not all_raw_emails:
        print("Niks te migreren -- alles staat al op hashes, of de tabellen zijn leeg. Klaar.")
        return

    print("\nGevonden e-mailadres(sen):", ", ".join(all_raw_emails))
    confirm = input("\nDoorgaan met migreren? (typ 'ja' om te bevestigen): ").strip().lower()
    if confirm != "ja":
        print("Geannuleerd -- er is niks aangepast.")
        return

    print("\n=== Stap 2: user_identity vullen (hash <-> echt adres) ===")
    email_to_hash = {}
    for email in all_raw_emails:
        hashed = hash_email(email)
        email_to_hash[email] = hashed
        client.table("user_identity").upsert({
            "email_hash": hashed,
            "email": email,
        }, on_conflict="email_hash").execute()
        print(f"  {email} -> {hashed[:12]}...")

    print("\n=== Stap 3: tabellen bijwerken (rauw e-mailadres -> hash) ===")
    for table in TABLES_WITH_USER_EMAIL:
        for email, hashed in email_to_hash.items():
            result = client.table(table).update({"user_email": hashed}).eq("user_email", email).execute()
            n_updated = len(result.data) if result.data else 0
            if n_updated:
                print(f"  {table}: {n_updated} rij(en) bijgewerkt voor {email}")

    print("\nKlaar! Alle rauwe e-mailadressen zijn nu vervangen door hashes.")
    print("Controleer even in Supabase's Table Editor of het er goed uitziet.")


if __name__ == "__main__":
    main()
