# 03. Matryca ECU Fabia I (2000–2002) i rozwiązywanie problemów z komunikacją
**Projekt:** Škoda Fabia I (2000–2002) — dokumentacja diagnostyczna  
**Autor:** Anonymousik.is-a.dev | **Aktualizacja:** 22.11.2026

---

## 1. Złącze OBD-II w Škodzie Fabii I (2000–2002)
- **Lokalizacja:** mały otwierany schowek po lewej stronie pod kierownicą.
- **Pinout (SAE J1962):**
  - **Pin 7:** linia diagnostyczna **K-Line** *(jedyna szyna diagnostyczna dostępna w gnieździe)*
  - **Pin 16:** zasilanie **+12 V** *(chronione bezpiecznikiem nr 12 — 7,5 A / 10 A)*
  - **Piny 4 i 5:** masa pojazdu (`GND`)
  - **Piny 6 i 14:** **brak magistrali CAN dla diagnostyki OBD** *(komunikat `CAN ERROR` przy protokołach `ATSP6–A` jest całkowicie normalny)*

---

## 2. Zestawienie wszystkich sterowników ECU (roczniki 2000–2002)

| Silnik | Kody | Rodzina ECU | Norma / Sondy | Wsparcie ELM327 (EOBD) | VAG KKL (`KWP1281`) |
|---|---|---|---|---|---|
| **1.0 MPI 8V (37 kW)** | `AQV`, `ARV` | Siemens Simos 3PA / 3PB | `AQV`: EU3 (2x O2) / `ARV`: EU2 (1x O2) | `AQV`: ISO 9141-2 / KWP2000; `ARV`: brak EOBD | Pełne |
| **1.2 6V (40 kW)** *(od 2002)* | `AWY` | Siemens Simos 3PD | EU4 (2x O2) | ISO 9141-2 / KWP2000 | Pełne |
| **1.4 MPI 8V (44 kW)** | `AZF`, `AZE` | Siemens Simos 3PA / 3PB | `AZF`: EU4 (2x O2) / `AZE`: EU2 (1x O2) | `AZF`: ISO 9141-2 / KWP2000; `AZE`: brak EOBD | Pełne |
| **1.4 MPI 8V (50 kW)** | `AQW`, `ATZ`, `AME` | Siemens Simos 3PA / 3PB | `AQW/ATZ`: EU4/D4 (2x O2) / `AME`: EU2 (1x O2) | `AQW/ATZ`: ISO 9141-2 / KWP2000; `AME`: zwykle brak EOBD | Pełne |
| **1.4 16V (55 / 74 kW)** | `AUA`, `AUB`, `BBY`, `BBZ` | Magneti Marelli IAW 4LV / 4MV | EU3 / EU4 (2x O2 + EGR) | `4MV`: trudne; `4LV`: bardzo często brak / zrywa | Pełne |
| **2.0 MPI 8V (85 kW)** | `AZL` | Bosch Motronic ME 7.5 | EU4 | Stabilne: KWP2000 / ISO 9141-2 | Pełne |
| **1.9 SDI (47 kW)** | `ASY` | Bosch EDC15V / VM+ | EU3 (Diesel <2003) | **Brak EOBD** (`NO DATA`) | Pełne |
| **1.9 TDI (74 kW)** | `ATD` | Bosch EDC15P+ | EU3 (Diesel <2003) | Zwykle brak (tylko wybrane z końca 2002 r.) | Pełne |

---

## 3. Rozwiązywanie problemów komunikacji (`BUS INIT: ...ERROR` / `NO DATA`)

### A. Diagnoza na podstawie `log.txt` tego konkretnego egzemplarza
W `log.txt` interfejs `Vgate iCar Pro v2.2` połączył się z telefonem poprawnie, ale każda próba K-Line (`ATSP3`, `ATSP4`, `ATSP5`, profile `33`/`37`/`44` i komendy `ATIIA33 / ATKW0`) zakończyła się błędem **`BUS INIT: ...ERROR`**.  
Ponadto skanowanie Bluetooth wykryło w aucie urządzenie **`Jie Rui BT-5908`** (`D8:1A:23:93:0E:50`).

### B. Checklist odblokowania linii K-Line (krok po kroku)
1. **Niefabryczne radio (`Jie Rui BT-5908` / kostka ISO):**  
   W fabrycznej kostce ISO Fabii I na pinie 3 znajduje się linia diagnostyczna **K-Line**. Niefabryczne radia bardzo często zwierają ten pin do +12 V lub masy.  
   → *Rozwiązanie:* Wyjmij bezpiecznik radia albo wypnij kostkę ISO z tyłu radia na czas diagnostyki (docelowo wypnij pin K-Line z kostki radia).
2. **Centralka LPG wpięta w K-Line:**  
   Niektóre sterowniki LPG podpięte do linii K lub gniazda OBD2 zakłócają inicjalizację 5-baud.  
   → *Rozwiązanie:* Wyjmij bezpiecznik zasilania sterownika LPG na czas skanowania.
3. **Zasilanie gniazda i napięcie akumulatora:**  
   Inicjalizacja 5-baud wymaga włączonego zapłonu (`KL15`) oraz napięcia **> 11,5 V** (sprawdź **bezpiecznik nr 12** jeśli adapter nie świeci).
4. **Wersje Euro 2 (`AME`, `AZE`, `ARV`) oraz Diesle (`ASY`, `ATD`):**  
   Jeśli mimo odpiętego radia i LPG oraz sprawnego napięcia nadal występuje `BUS INIT: ...ERROR`, ECU najprawdopodobniej nie obsługuje zapytań EOBD (`0100` na adresie `33` hex) — użyj kabla **VAG KKL (USB)** po protokole `KWP1281`.
5. **Specyfika Magneti Marelli (`4LV` / `4MV`):**  
   Po każdej nieudanej próbie połączenia Marelli potrafi zablokować bufor linii K — **wyłącz zapłon i wyjmij kluczyk na 15 sekund** przed kolejną próbą. Dla `4LV` najpewniejszy jest kabel VAG KKL z `Latency Timer = 1 ms`.
6. **Specyfika licznika (Gateway K-Line):**  
   Linia K przechodzi przez zestaw wskaźników. Uszkodzenie lub nieumiejętna wymiana licznika również odcina komunikację z ECU.

---
*Podpisano: Anonymousik.is-a.dev*