-- Voegt een expliciet currency-veld toe aan elke transactie -- lost de
-- structurele oorzaak op van de valuta-verwarring: tot nu toe moest de
-- app GOKKEN in welke valuta een transactieprijs stond (native
-- ticker-valuta? EUR, omdat DEGIRO's CSV-import dat altijd zo
-- opslaat?), en verschillende invoer-methodes (CSV-import vs.
-- handmatig loggen) gebruikten elk een andere, inconsistente aanname.

ALTER TABLE portfolio_transactions ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'EUR';

-- Bestaande transacties (allemaal ofwel via de DEGIRO-CSV-import
-- binnengekomen -- die BEWUST altijd EUR opslaat -- of handmatig
-- gelogd terwijl de UI tot nu toe overal een hardcoded €-teken toonde)
-- expliciet op 'EUR' zetten. Dit is dus GEEN gok voor bestaande data,
-- maar een correcte weerspiegeling van hoe ze al die tijd daadwerkelijk
-- werden ingevoerd.
UPDATE portfolio_transactions SET currency = 'EUR' WHERE currency IS NULL;
