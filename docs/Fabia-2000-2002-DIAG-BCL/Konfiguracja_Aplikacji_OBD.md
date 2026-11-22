# 02. Konfiguracja aplikacji diagnostycznych i interfejsów
**Projekt:** Škoda Fabia I (2000–2002) — dokumentacja diagnostyczna  
**Autor:** Anonymousik.is-a.dev | **Aktualizacja:** 22.11.2026

---

## 1. BorbaCar Labs (Android)

### Wgranie profilu
1. Otwórz **BorbaCar Labs** → przejdź do funkcji przywracania kopii zapasowej (**Backup / Restore**).
2. Wybierz plik **`BorbaCar-backup_skoda-fabia.json`**.
3. Po wgraniu aktywny będzie profil **`Fabia2002`** (`revision: 3`).

### Parametry profilu zapisane w kopii
- **Make:** `Škoda` | **Model:** `Fabia` | **Manufacture / Model year:** `2002`
- **Market:** `Czech / Poland (EU)` | **Trim:** `6Y2 Hatchback Comfort`
- **Engine:** `1.4 MPI 8V 50 kW (1397cc)` | **Fuel:** `Petrol / LPG` | **Transmission:** `5-M` *(wg konwencji ekstraktora katalogu: `M-5`)*

### Ograniczenia BorbaCar Labs w tym pojeździe
- **Brak wbudowanego katalogu dla tego auta:** `vehicle_catalog.json` i `vehicle_efficiency.json` obejmują wyłącznie rynek brazylijski (Inmetro PBE Veicular 2012–2026). Profil musi pozostać ręczny (`USER_INPUT`).
- **Zakres diagnostyki:** wyłącznie generyczny standard **EOBD/OBD-II sterownika silnika** (brak obsługi ABS, Airbag, licznika, wspomagania i adaptacji przepustnicy).
- **Katalog błędów (`generic-dtc-3`):** zawiera kody ogólne `P0xxx`/`U0xxx` (w tym 26 dodanych kodów), ale **nie zawiera kodów VAG `P1xxx`** ani kodów `P0141`, `P0161`, `P0180`, `P0553`.
- **Formaty plików:** przywracanie profilu działa **tylko z JSON** (z walidacją SHA-256). Pliki **CSV** służą wyłącznie do zapisu logów Live Data.

---

## 2. Car Scanner ELM OBD2 (Android — Realme 9 Pro 5G / RMX3472)
**Adapter:** `Vgate iCar Pro v2.2` (`V-LINK`, MAC `00:1D:A5:21:46:01`)

### Krok A: Uprawnienia i parowanie Bluetooth
1. W ustawieniach telefonu sparuj urządzenie `V-LINK` (PIN `1234` lub `0000`).
2. W uprawnieniach aplikacji **Car Scanner** zezwól na **Urządzenia w pobliżu** oraz **Lokalizację**.

### Krok B: Poprawki profilu auta (wykryte w `log.txt`)
Wejdź w **Ustawienia → Mój samochód / Zużycie paliwa** i popraw błędne wpisy z logu:
- **Pojemność skokowa silnika:** zmień z `1,6` na **`1,4`**
- **Pojazd hybrydowy lub PHEV:** **WYŁĄCZ** *(w `log.txt` było błędnie włączone `FuelHybridCar=True`)*
- **Liczba cylindrów:** `4`
- **Rodzaj paliwa:** `Benzyna` *(lub `Propan` przy jeździe na LPG)*

### Krok C: Połączenie i Profil połączenia
- **Połączenie:** sprawdź **Bluetooth LE (4.0+)** *(zalecane dla iCar Pro v2.2)* lub klasyczny **Bluetooth** → wybierz `V-LINK`.
- **Profil połączenia:** `Škoda` → **`OBD-II / EOBD`**.

### Krok D: Ustawienia zaawansowane ECU (kolejność testów)
1. **Test 1 (Domyślny ISO 9141-2):**  
   Tryb inicjalizacji: **`Domyślny`** | Protokół: **`3) ISO 9141-2 (5 baud init, 10.4 kbaud)`** | *„Wypróbuj inne protokoły”*: **ODZNACZONE**.
2. **Test 2 (Domyślny KWP2000):**  
   Protokół: **`4) ISO 14230-4 KWP (5 baud init)`**.
3. **Test 3 (Niestandardowy — obejście sprawdzania bajtów kluczowych `ATKW0`):**  
   Tryb inicjalizacji: **`Niestandardowy`** *(bez `ATSP0`!)*:
   - *Wariant ISO 9141-2:*
     ```text
     ATZ
     ATE0
     ATH1
     ATL0
     ATS0
     ATSP3
     ATIIA33
     ATIB10
     ATKW0
     ```
   - *Wariant KWP2000 (jeśli wariant 1 nie połączy):*
     ```text
     ATZ
     ATE0
     ATH1
     ATL0
     ATS0
     ATSP4
     ATIIA33
     ATIB10
     ATKW0
     ```

---

## 3. Kabel VAG KKL (USB) + VCDS-Lite (Windows) — pełny dostęp serwisowy
Konieczny, gdy: silnik ma kod `AME` (Euro 2 bez EOBD), ELM327 zwraca `BUS INIT: ...ERROR` mimo sprawnej linii K, albo trzeba wejść w moduły **03-ABS**, **15-Airbag**, **17-Licznik**, **44-Wspomaganie** lub wykonać **adaptację przepustnicy**.

- **Sprzęt:** kabel **VAG KKL 409.1 USB** oparty o chip **FTDI (FT232R / FT232RL)**.
- **Konfiguracja portu COM w Windows (Menedżer Urządzeń → Porty COM → Właściwości → Zaawansowane):**  
  Zmień **Latency Timer (Czas opóźnienia)** z `16 ms` na **`1–2 ms`**.
- **Konfiguracja w VCDS-Lite → Options:**  
  `Start Baud = 9600` *(lub `0`)*, `Blk Int = 55`, `Char Int = 1`, `KP2 Time = 25`.

---
*Podpisano: Anonymousik.is-a.dev*