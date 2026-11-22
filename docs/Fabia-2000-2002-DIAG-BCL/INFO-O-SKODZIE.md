# Kompletna dokumentacja projektu diagnostyczno-serwisowego
## Škoda Fabia I (6Y2) 1.4 MPI 8V (2002) + matryca generacji 2000–2002

> **Autor / Opracowanie:** **Anonymousik.is-a.dev**  
> **Data aktualizacji:** 22.11.2026  
> **Cel dokumentu:** Pełna konfiguracja aplikacji diagnostycznych (**BorbaCar Labs**, **Car Scanner ELM OBD2**, **VCDS-Lite / VAG KKL**), instrukcja użytkowania krok po kroku (również dla osoby nietechnicznej), zarządzanie plikami kopii oraz kompletny plan diagnozy usterek konkretnego egzemplarza.

---


## 1. Identyfikacja pojazdu (zweryfikowana z VIN i dokumentacji)

* **VIN:** `TMBNB46Y12X023205` *(uwaga: bez znaku `@` na końcu przy wpisywaniu w katalogach i aplikacjach)*
* **Marka / Model:** Škoda Fabia I (typ `6Y2`, 5-drzwiowy Hatchback)
* **Wersja wyposażenia:** Comfort *(pozycja 4 VIN: `N`)*
* **Rok produkcji / modelowy:** 2002 *(pozycja 10 VIN: `2`)*
* **Zakład montażowy:** Poznań, Polska *(pozycja 11 VIN: `X`)*
* **Silnik:** 1.4 MPI 8V, 1397 cm³, 50 kW (68 KM) *(pozycja 5 VIN: `B`)*
* **Paliwo:** Benzyna + instalacja LPG
* **Skrzynia biegów:** 5-biegowa manualna (`M-5` / `5-M`)
* **Sterownik silnika (ECU):** Siemens **Simos 3PA** lub **Simos 3PB**
* **Możliwe kody silnika:** **`AQW`** *(najczęstszy w 2002 r., Euro 4, 2 sondy lambda + EGR)*, **`ATZ`** *(D4/Euro 4)* lub **`AME`** *(Euro 2/3, 1 sonda lambda)*.  
  *Gdzie potwierdzić dokładny kod:* biała wlepka z kodami PR pod wykładziną bagażnika obok koła zapasowego, 1. strona książki serwisowej lub naklejka na obudowie rozrządu z przodu silnika.

## 3. Pełna konfiguracja oprogramowania i sprzętu

### A. Konfiguracja w **BorbaCar Labs**
* **Przywrócenie profilu:** w aplikacji wejdź w sekcję kopii zapasowej (*Backup / Restore*) i wskaż plik **`BorbaCar-backup_skoda-fabia.json`**.
* **Ustawienia profilu zapisane w kopii (`revision: 3`):**
  * **Name:** `Fabia2002` | **Make:** `Škoda` | **Model:** `Fabia` | **Year:** `2002`
  * **Market:** `Czech / Poland (EU)` | **Trim:** `6Y2 Hatchback Comfort`
  * **Engine:** `1.4 MPI 8V 50 kW (1397cc)` | **Fuel:** `Petrol / LPG` | **Transmission:** `5-M` *(opcjonalnie `M-5` wg konwencji katalogowej)*
  * **Notes:** `VIN: TMBNB46Y12X023205; Plant: Poznan; ECU: Simos 3PA/3PB; OBD2 Pin 7 K-Line (ISO 9141-2 / KWP2000 EOBD only); VAG KWP1281 requires KKL; Adapter: Vgate iCar Pro V-LINK`
* **Ograniczenia architektoniczne BorbaCar Labs, o których trzeba pamiętać:**
  1. Katalog pojazdów i zużycia paliwa (`vehicle_catalog.json` / `vehicle_efficiency.json`) obejmuje wyłącznie rynek brazylijski Inmetro PBE Veicular (2012–2026) — Fabia 2002 pozostaje profilem ręcznym (`USER_INPUT`).
  2. Program obsługuje wyłącznie generyczny standard **EOBD/OBD-II sterownika silnika** (nie odczyta ABS, Airbag, licznika ani wspomagania).
  3. Katalog kodów `generic-dtc-3` (nowszy niż `generic-dtc-1` widoczny w starych zapisach JSON) obejmuje kody ogólne `P0xxx`/`U0xxx` (z 26 dodanymi kodami), ale **nie zawiera kodów producenckich VAG `P1xxx`** ani kodów `P0141`, `P0161`, `P0180`, `P0553`.
  4. Pliki **CSV** w BorbaCar Labs służą wyłącznie do logów Live Data — do przywracania profilu służy wyłącznie **JSON**.

### B. Konfiguracja w **Car Scanner ELM OBD2** (Android — np. Realme 9 Pro 5G / RMX3472)
Analiza pliku `log.txt` wykazała błędy konfiguracji po stronie aplikacji, które należy poprawić przed kolejnym testem:
1. **Uprawnienia telefonu (Realme UI / Android 14):**
   * Sparuj interfejs **`V-LINK`** (`00:1D:A5:21:46:01`) w ustawieniach Bluetooth telefonu (kod `1234` lub `0000`) i przyznaj Car Scannerowi uprawnienie **Urządzenia w pobliżu** oraz **Lokalizacja**.
2. **Mój samochód / Zużycie paliwa (do poprawy względem `log.txt`!):**
   * **Pojemność skokowa:** zmień z `1,6` na **`1,4`**
   * **Pojazd hybrydowy lub PHEV:** **ODZNACZ** *(w `log.txt` było błędnie ustawione `FuelHybridCar=True`!)*
   * **Liczba cylindrów:** `4` | **Paliwo:** `Benzyna` *(lub `Propan` przy jeździe na LPG)*
3. **Połączenie i Profil:**
   * **Typ połączenia:** przetestuj **Bluetooth LE (4.0+)** *(zalecane dla Vgate iCar Pro v2.2)* lub klasyczny **Bluetooth** → urządzenie `V-LINK`.
   * **Profil połączenia:** `Škoda` → **`OBD-II / EOBD`** *(zgodnie z podpowiedzią aplikacji dla VAG sprzed 2010 r.)*.
4. **Protokół ECU (kolejność prób przy `BUS INIT: ...ERROR`):**
   * **Próba 1 (Tryb Domyślny):** Tryb inicjalizacji **`Domyślny`**, protokół **`3) ISO 9141-2 (5 baud init, 10.4 kbaud)`**, opcja *„Wypróbuj inne protokoły”* **WYŁĄCZONA**.
   * **Próba 2 (Tryb Domyślny):** Protokół **`4) ISO 14230-4 KWP (5 baud init)`**.
   * **Próba 3 (Tryb Niestandardowy — ręczne obejście sprawdzania bajtów kluczowych dla Simos 3):**  
     Wklej bez `ATSP0`:
     * *Wariant ISO 9141-2:* `ATZ` / `ATE0` / `ATH1` / `ATL0` / `ATS0` / `ATSP3` / `ATIIA33` / `ATIB10` / `ATKW0`
     * *Wariant KWP2000:* `ATZ` / `ATE0` / `ATH1` / `ATL0` / `ATS0` / `ATSP4` / `ATIIA33` / `ATIB10` / `ATKW0`

### C. Konfiguracja kabla **VAG KKL (USB)** + **VCDS-Lite** *(pełna diagnostyka VAG)*
Niezbędne, jeśli: silnik to wersja **`AME` (Euro 2 bez EOBD)**, linia K nie dogaduje się z ELM327 lub trzeba zdiagnozować **wspomaganie (`44`)**, **ABS (`03`)**, **Airbag (`15`)**, **licznik (`17`)** albo zrobić **adaptację przepustnicy**.
* **Wymagany kabel:** niebieski/czarny przewód **VAG KKL 409.1 USB** na układzie **FTDI (FT232R/RL)**.
* **Ustawienia Windows (Menedżer Urządzeń → Port COM kabla):**  
  Ustaw **Latency Timer (Czas opóźnienia)** z domyślnych `16 ms` na **`1–2 ms`**.
* **Ustawienia VCDS-Lite (Options):**  
  `Start Baud = 9600` *(lub `0`)*, `Blk Int = 55`, `Char Int = 1`, `KP2 Time = 25`.

---

## 4. Standardy diagnostyczne całej generacji Škoda Fabia I (2000–2002)

| Silnik | Kody | Sterownik ECU | Protokół EOBD (ELM327 / BorbaCar) | Protokół VAG (Kabel KKL) |
|---|---|---|---|---|
| **1.0 MPI 8V (37 kW)** | `AQV`, `ARV` | Siemens Simos 3PA / 3PB | `AQV`: ISO 9141-2 / KWP2000; `ARV` (EU2): zwykle brak EOBD | KWP1281 (pełne) |
| **1.2 6V (40 kW)** *(od 2002)* | `AWY` | Siemens Simos 3PD | ISO 9141-2 / KWP2000 | KWP1281 (pełne) |
| **1.4 MPI 8V (44 kW)** | `AZF`, `AZE` | Siemens Simos 3PA / 3PB | `AZF`: ISO 9141-2 / KWP2000; `AZE` (EU2): zwykle brak EOBD | KWP1281 (pełne) |
| **1.4 MPI 8V (50 kW)** | `AQW`, `ATZ`, `AME` | Siemens Simos 3PA / 3PB | `AQW/ATZ`: ISO 9141-2 / KWP2000; `AME` (EU2): zwykle brak EOBD | KWP1281 (pełne) |
| **1.4 16V (55 / 74 kW)** | `AUA`, `AUB`, `BBY`, `BBZ` | Magneti Marelli IAW 4LV / 4MV | Bardzo czuły na timingi 5-baud (po błędzie zgaś zapłon na 15 s!) | KWP1281 (pełne) |
| **2.0 MPI 8V (85 kW)** | `AZL` | Bosch Motronic ME 7.5 | Stabilny: KWP2000 / ISO 9141-2 | KWP1281 / KWP2000 |
| **1.9 SDI / TDI (47 / 74 kW)** | `ASY`, `ATD` | Bosch EDC15V / EDC15P+ | Zwykle **brak EOBD** (diesel przed 2003/2004 r.) | KWP1281 (pełne) |

* **Złącze diagnostyczne w każdym modelu (2000–2002):** 16-pinowe OBD-II (mały schowek po lewej pod kierownicą), **Pin 7 = K-Line**, **Pin 16 = +12 V (bezpiecznik nr 12)**, **Piny 4/5 = masa**. Brak diagnostyki CAN na pinach 6 i 14 (`CAN ERROR` w logach jest normalnym objawem).

---

## 5. Analiza logu (`log.txt`) i diagnoza usterek tego auta

### Co wykazał `log.txt` (Car Scanner v2.2.52 + Vgate iCar Pro v2.2):
* Adapter **Vgate iCar Pro** (`VTI -> IcarPro v2.2`) komunikuje się z telefonem poprawnie.
* Wszystkie protokoły linii K (`ATSP3`, `ATSP4`, `ATSP5`, `33`, `37`, `44`, jak i ręczne `ATIIA33 / ATKW0`) zwróciły **`BUS INIT: ...ERROR`**.
* **Kluczowe znalezisko w logu Bluetooth:** wykryto urządzenie **`Jie Rui BT-5908`** (`D8:1A:23:93:0E:50`), czyli typowy chiński moduł Bluetooth / niefabryczne radio samochodowe. W Fabii I pin 3 fabrycznej kostki ISO radia jest połączony z linią K-Line — niefabryczne radio bardzo często zwiera tę linię i całkowicie blokuje diagnostykę!

### Zestawienie objawów auta i ich najbardziej prawdopodobne źródła:
1. **Przygasanie świateł + losowe zanikanie wspomagania kierownicy + losowe problemy z odpalaniem:**  
   Wspomaganie elektrohydrauliczne (TRW/Koyo) pobiera ogromny prąd i wyłącza się automatycznie przy spadkach napięcia. Typowe miejsca awarii w Fabii 2002: **pęknięte blaszki bezpiecznikowe w skrzynce na akumulatorze**, **regulator napięcia / alternator**, **skorodowana masa pod akumulatorem** oraz **zgnita wiązka w plastikowym korytku na lewej podłużnicy** (pod akumulatorem/filtrem powietrza).
2. **Brak światła stopu + kontrolka `EPC` + spadek mocy / szarpanie:**  
   W Fabii I włącznik stopu przy pedale hamulca jest 4-pinowy (dwuobwodowy). Uszkodzony czujnik stopu, przepalony bezpiecznik stopu lub obie spalone żarówki powodują błąd obwodu hamulca w ECU, co **bezpośrednio zapala kontrolkę `EPC`** i ogranicza moc.
3. **Problemy z odpalaniem znikające po zdjęciu klemy na dłużej + gaśnięcie na wolnych obrotach:**  
   Zdjęcie klemy resetuje wyuczone korekty paliwowe (`LTFT`) w ECU. W aucie z LPG jest to klasyczny objaw **rozjechanej mapy LPG** lub **przepuszczania gazu do kolektora na postoju** (nieszczelne wtryskiwacze LPG lub membrana reduktora). Dodatkową przyczyną gaśnięcia jest zabrudzona olejem przepustnica.
4. **Mocny ubytek oleju i wyrzucanie/dymienie z wydechu przy gazowaniu:**  
   Usterka mechaniczna silnika 1.4 MPI 8V (zapieczone/zużyte **pierścienie tłokowe**, **uszczelniacze zaworowe** lub **zapchana odma** wypychająca olej w dolot). Spalany olej zarzuca świece zapłonowe oraz sondę lambda, co nasila szarpanie.

---

## 6. Instrukcja użycia krok po kroku (wersja dla każdego użytkownika)

### Etap 1 — Bezpieczeństwo i szybka weryfikacja elektryki (zanim użyjesz skanera)
1. **Światła stopu (`EPC`):** sprawdź bezpiecznik świateł stopu w skrzynce z boku deski i żarówki w lampach. Jeśli są sprawne, a stopu dalej nie ma — wymień **czujnik (włącznik) stopu nad pedałem hamulca**.
2. **Ładowanie i masa:** zmierz napięcie na akumulatorze na pracującym silniku (ze światłami i przy kręceniu kierownicą). Prawidłowo powinno być **13,8–14,4 V**. Sprawdź wzrokowo blaszki bezpieczników na pokrywie akumulatora (czy nie są pęknięte lub nadtopione).
3. **Poziom oleju:** regularnie kontroluj bagnet przed każdą jazdą i dolewaj olej.

### Etap 2 — Domowy test instalacji LPG (bez narzędzi)
1. Zakręć ręczny zawór gazu na butli w bagażniku.
2. Wypal resztkę gazu z przewodów, aż auto samo przełączy się na benzynę.
3. Pojeździj **2–3 dni wyłącznie na benzynie**. Jeśli znikną problemy z odpalaniem i gaśnięciem na wolnych obrotach — konieczna jest wizyta u gazownika (uszczelnienie/regulacja LPG).

### Etap 3 — Podłączenie skanera OBD2 (procedura „czystej linii K”)
1. Wyłącz niefabryczne radio (najlepiej **wyjmij bezpiecznik radia** lub wypnij kostkę z tyłu radia) oraz **wyjmij bezpiecznik centralki LPG** na czas testu.
2. Włóż kostkę **`Vgate iCar Pro (V-LINK)`** do gniazda w schowku po lewej pod kierownicą.
3. Przekręć kluczyk na **zapłon** (kontrolki na desce muszą świecić; napięcie akumulatora >12 V).
4. W **Car Scannerze** kliknij **Połącz** (profil `Škoda → OBD-II / EOBD`, pojemność `1,4 l`, hybryda wyłączona, protokół `3) ISO 9141-2` lub `4) KWP 5-baud`).
5. *Alternatywnie w **BorbaCar Labs**:* po uprzednim wgraniu profilu `BorbaCar-backup_skoda-fabia.json` połącz się z adapterem V-LINK i odczytaj błędy silnika.
6. Jeśli mimo odpiętego radia i LPG nadal pojawia się `BUS INIT: ...ERROR` — **nie kupuj kolejnych adapterów Bluetooth**. Podjedź na odczyt kablem **VAG KKL (VCDS-Lite)**.

### Etap 4 — Gotowa lista kontrolna dla mechanika / elektryka
Przekaż warsztatowi dokładnie te 4 punkty:
1. *„Proszę sprawdzić ładowanie pod obciążeniem (światła + wspomaganie), blaszki bezpiecznikowe na akumulatorze, punkt masowy pod akumulatorem oraz wiązkę w korytku na lewej podłużnicy.”*
2. *„Brak świateł stopu i świecąca kontrolka EPC — proszę sprawdzić bezpiecznik, instalację lamp i czujnik stopu przy pedale hamulca.”*
3. *„Problem z komunikacją po linii K-Line w gnieździe OBD2 — proszę sprawdzić, czy niefabryczne radio (`Jie Rui`) lub sterownik LPG nie zwiera pinu 7, oraz odczytać błędy kablem VAG KKL (silnik + moduł 44 wspomagania).”*
4. *„Duży ubytek oleju, dymienie z wydechu przy gazowaniu i gaśnięcie na wolnych obrotach — proszę sprawdzić drożność odmy, wyczyścić przepustnicę (z adaptacją po czyszczeniu), ocenić świece zapłonowe i wykonać pomiar kompresji z próbą olejową.”*

---

**Opracował i podpisał:**  
( Z wykorzystaniem technologii Google Argon 5 ) 
`Anonymousik.is-a.dev`