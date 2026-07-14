"""
Simpele, gedeelde functie om e-mailadressen om te zetten naar een
deterministische hash -- gebruikt als sleutel in de database i.p.v. het
leesbare e-mailadres zelf, zodat holdings/transacties niet direct aan
een naam/adres gekoppeld staan bij het rondkijken in de tabellen.

Geen afhankelijkheden (geen Streamlit, geen Supabase) -- zowel
database.py (binnen de Streamlit-app) als de losse GitHub Actions-
scripts (daily_email_dispatch.py, weekly_batch.py, die BUITEN een
Streamlit-context draaien) kunnen dit importeren.
"""
from __future__ import annotations

import hashlib
import re

# Een SHA-256-hash is altijd exact 64 hexadecimale tekens -- gebruikt om te
# herkennen of een waarde AL een hash is (voorkomt dubbel hashen als een
# al-gehashte waarde per ongeluk nog een keer door hash_email() zou gaan).
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def hash_email(value: str) -> str:
    """
    Geeft een deterministische SHA-256-hash van een e-mailadres terug
    (altijd hetzelfde e-mailadres -> altijd dezelfde hash, dus bruikbaar
    als opzoek-sleutel). Kleine letters + gestript van spaties vóór het
    hashen, zodat 'Naam@Gmail.com' en 'naam@gmail.com ' hetzelfde
    opleveren.

    Als 'value' er zelf al uitziet als een hash (64 hex-tekens), wordt
    'ie ongewijzigd teruggegeven -- een veiligheidsnet tegen dubbel hashen.
    """
    if not value:
        return value
    if _HASH_PATTERN.match(value):
        return value
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()
