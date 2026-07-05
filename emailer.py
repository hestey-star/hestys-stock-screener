"""
Simpele, herbruikbare e-mail-notificatiemodule via SMTP. Werkt met Gmail,
Outlook, en de meeste andere providers.

BELANGRIJK bij Gmail: je normale wachtwoord werkt hier niet als je 2FA
aan hebt staan (aanbevolen). Je hebt een 'app-wachtwoord' nodig:
1. Ga naar https://myaccount.google.com/apppasswords
2. Maak een nieuw app-wachtwoord aan (naam maakt niet uit, bv. "python-bot")
3. Gebruik dat 16-tekens-wachtwoord hieronder in .env, NIET je normale wachtwoord

Benodigde .env-variabelen:
  EMAIL_SMTP_SERVER=smtp.gmail.com
  EMAIL_SMTP_PORT=587
  EMAIL_ADDRESS=jouw@gmail.com
  EMAIL_APP_PASSWORD=jouw-16-tekens-app-wachtwoord
  EMAIL_TO=waar-naartoe@gmail.com   (mag hetzelfde adres zijn als EMAIL_ADDRESS)

Voor Outlook/Hotmail: EMAIL_SMTP_SERVER=smtp.office365.com, poort 587,
en daar werkt vaak wel gewoon je normale wachtwoord (of ook een app-wachtwoord
als je 2FA hebt).
"""
from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")

# EMAIL_TO mag 1 adres zijn, of meerdere gescheiden door een komma, bv.:
#   EMAIL_TO=jouw@gmail.com,vriend@gmail.com
_email_to_raw = os.getenv("EMAIL_TO", EMAIL_ADDRESS)
EMAIL_TO_LIST = [addr.strip() for addr in _email_to_raw.split(",") if addr.strip()]
EMAIL_TO = ", ".join(EMAIL_TO_LIST)  # voor weergave in de 'To'-header


def is_configured() -> bool:
    return bool(EMAIL_ADDRESS and EMAIL_APP_PASSWORD and EMAIL_TO_LIST)


def send_email(subject: str, body_text: str, body_html: str = None, to_email: str = None) -> bool:
    """
    Verstuurt een e-mail via BCC: ontvangers zien elkaars adres niet.

    Als 'to_email' wordt meegegeven, gaat de mail ALLEEN naar dat ene
    adres (gebruikt door het wekelijkse batch-script, dat elke gebruiker
    een eigen, persoonlijke mail stuurt). Zonder 'to_email' wordt de vaste
    EMAIL_TO_LIST uit .env gebruikt (het oorspronkelijke, single-user-gedrag).

    Geeft True terug bij succes, False bij een fout (de fout wordt ook
    geprint, zodat je 'm in een logbestand kan terugzien als dit script
    via een geplande taak draait).
    """
    recipients = [to_email] if to_email else EMAIL_TO_LIST

    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD or not recipients:
        print("E-mail niet verstuurd: EMAIL_ADDRESS/EMAIL_APP_PASSWORD/ontvanger(s) "
              "ontbreken (compleet).")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_ADDRESS  # BCC: toon alleen jezelf, niet de andere ontvangers

    msg.attach(MIMEText(body_text, "plain"))
    if body_html:
        msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, recipients, msg.as_string())
        print(f"E-mail (BCC) verstuurd naar {len(recipients)} ontvanger(s).")
        return True
    except Exception as exc:
        print(f"E-mail versturen mislukt: {exc}")
        return False


if __name__ == "__main__":
    ok = send_email(
        subject="Testmail vanuit je trading-tools",
        body_text="Dit is een testbericht. Als je dit ontvangt, werkt je e-mail-configuratie!",
    )
    print("Gelukt!" if ok else "Niet gelukt, zie foutmelding hierboven.")
