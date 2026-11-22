# 01. Karta pojazdu i porządek w plikach
**Projekt:** Škoda Fabia I (2000–2002) — dokumentacja diagnostyczna  
**Autor:** Anonymousik.is-a.dev | **Aktualizacja:** 22.11.2026

---

## 1. Dane pojazdu (zweryfikowane po VIN)
- **VIN:** `TMBNB46Y12X023205` *(uwaga: bez znaku `@` na końcu przy wpisywaniu w katalogach i aplikacjach)*
- **Marka / Model:** Škoda Fabia I (`6Y2` — 5-drzwiowy Hatchback)
- **Wersja wyposażenia:** Comfort *(pozycja 4 VIN: `N`)*
- **Rok produkcji / modelowy:** 2002 *(pozycja 10 VIN: `2`)*
- **Zakład montażowy:** Poznań, Polska *(pozycja 11 VIN: `X`)*
- **Silnik:** 1.4 MPI 8V, 1397 cm³, 50 kW / 68 KM *(pozycja 5 VIN: `B`)*
- **Zasilanie:** Benzyna + instalacja LPG
- **Skrzynia biegów:** 5-biegowa manualna (`M-5` / `5-M`)
- **Sterownik silnika (ECU):** Siemens Simos 3PA lub Simos 3PB
- **Możliwe kody silnika:**
  - `AQW` *(najczęstszy w 2002 r., Euro 4, 2 sondy lambda + EGR)*
  - `ATZ` *(D4 / Euro 4, 2 sondy lambda)*
  - `AME` *(Euro 2 / Euro 3, 1 sonda lambda — często brak EOBD)*
- **Gdzie sprawdzić dokładny kod silnika:** biała wlepka z kodami PR pod wykładziną bagażnika obok koła zapasowego, 1. strona książki serwisowej lub naklejka na obudowie rozrządu.

---

## 2. Które pliki ZACHOWAĆ, a które USUNĄĆ na telefonie

### ZACHOWAJ
1. `BorbaCar-backup_skoda-fabia.json` *(62,34 kB, `revision: 3`)* — **jedyny aktualny plik kopii zapasowej** do przywrócenia w BorbaCar Labs.
   - *Wyjaśnienie sum kontrolnych:* SHA-256 pliku na dysku (`4e6df4de...`) i pole `"checksum"` wewnątrz JSON (`03de7f3d...`) to dwie różne, prawidłowe sumy — niczego nie edytuj ręcznie.
2. `06_Skoda_Fabia_I_2000-2002_Unified_BorbaCarLabs.csv` *(6,54 kB)* — kompletna baza referencyjna CSV (do podglądu / dla mechanika, nie do importu w aplikacji).
3. `01`–`05` z tego zestawu dokumentów.
4. *(Opcjonalnie)* `BorbaCar-Labs-1.2.0.apk` oraz `Workshop Manual...txt`.

### USUŃ (stare wersje, duplikaty i fikcyjne raporty)
- `BorbaCar-backup.json` i `BorbaCar-backup (1).json` *(stare kopie `revision: 2`)*
- `BorbaCar-skodafabia1-2002.json` *(najstarsza kopia robocza)*
- `Fabia2002.csv` i `Fabia2002-BorbaCarLabs-profile.csv` *(zastąpione plikiem `06_...Unified...csv`)*
- `relatorio-rea-obd.pdf` i `relatorio-rea-obd (1).pdf` *(zawierają fikcyjne kody `P0133` i `P0301` z symulatora, nie prawdziwe błędy auta)*
- `DashCommand v4.2.1 (DEMO).apk`

---
*Podpisano: Anonymousik.is-a.dev*