# 04. Diagnoza usterek pojazdu i karta zlecenia dla warsztatu
**Projekt:** Škoda Fabia I (2000–2002) — `TMBNB46Y12X023205` (1.4 MPI + LPG)  
**Autor:** Anonymousik.is-a.dev | **Aktualizacja:** 22.11.2026

---

## 1. Powiązanie objawów z prawdopodobnymi przyczynami

### Grupa 1: Przygasanie świateł + losowe zanikanie wspomagania + problemy z odpalaniem
- **Mechanizm:** Elektrohydrauliczna pompa wspomagania (TRW / Koyo) pobiera wysoki prąd i automatycznie się wyłącza przy spadkach/skokach napięcia.
- **Typowe usterki w Fabii I (2002):**
  1. Pęknięte lub nadpalone **blaszki bezpiecznikowe na pokrywie akumulatora** (alternator / wspomaganie).
  2. Zużyty **regulator napięcia / alternator**.
  3. Skorodowany **przewód masowy** (akumulator → podłużnica → skrzynia biegów).
  4. **Zgnita wiązka elektryczna w plastikowym korytku na lewej podłużnicy** (pod akumulatorem i obudową filtra powietrza — stoi tam woda).

### Grupa 2: Brak światła stopu + kontrolka `EPC` + spadek mocy / szarpanie
- **Mechanizm:** W Fabii I włącznik świateł stopu nad pedałem hamulca jest **4-pinowy (dwuobwodowy)**: osobny obwód idzie na żarówki, a osobny do ECU (`Simos 3`). Brak sygnału hamowania lub zwarcie w obwodzie stopu **bezpośrednio zapala kontrolkę `EPC`** i ogranicza reakcję na gaz.
- **Do sprawdzenia:** bezpiecznik świateł stopu, wszystkie żarówki stopu (w tym 3. światło), wiązka klapy oraz **czujnik stopu przy pedale hamulca**.

### Grupa 3: Problem z odpalaniem (znika po odłączeniu klem na dłużej) + gaśnięcie na wolnych obrotach
- **Mechanizm:** Dłuższe odłączenie akumulatora kasuje wyuczone korekty paliwowe (`LTFT`) w sterowniku silnika.
- **Najczęstsze przyczyny:**
  1. **Instalacja LPG:** rozjechana mapa gazu albo puszczanie gazu do kolektora na postoju (nieszczelne wtryskiwacze LPG lub membrana reduktora przez podciśnienie).
  2. **Zabrudzona olejem przepustnica** (wymaga czyszczenia i późniejszej adaptacji kablem VAG KKL / VCDS).

### Grupa 4: Mocny ubytek oleju + dymienie/wyrzucanie z wydechu przy gazowaniu
- **Mechanizm:** Mechaniczne zużycie/nieszczelność silnika 1.4 MPI 8V — olej trafia do komór spalania lub dolotu, zarzucając świece i sondę lambda (co dodatkowo powoduje szarpanie i gaśnięcie).
- **Najczęstsze przyczyny:** **zapchana odma**, zużyte **uszczelniacze zaworowe** lub zużyte/zapieczone **pierścienie tłokowe**.

---

## 2. Karta dla mechanika / elektryka (do wydruku lub odczytania w warsztacie)

1. **Układ zasilania i ładowania (PILNE — bezpieczeństwo):**  
   *„Proszę zmierzyć ładowanie pod obciążeniem (włączone światła + kręcenie kierownicą), sprawdzić bezpieczniki blaszkowe na obudowie akumulatora, punkt masowy pod akumulatorem oraz stan wiązki w korytku na lewej podłużnicy (przygasają światła i znika wspomaganie).”*
2. **Światła stopu i EPC (PILNE — bezpieczeństwo):**  
   *„Brak świateł stopu i świecąca kontrolka EPC — proszę sprawdzić bezpiecznik, żarówki i wymienić/sprawdzić 4-pinowy czujnik stopu przy pedale hamulca.”*
3. **Brak komunikacji OBD2 (`BUS INIT: ...ERROR`):**  
   *„Auto nie łączy się po linii K-Line przez ELM327 — proszę sprawdzić, czy niefabryczne radio (`Jie Rui`) lub sterownik LPG nie zwiera pinu 7 gniazda OBD2, i odczytać błędy kablem VAG KKL / VCDS (silnik + moduł 44 wspomagania).”*
4. **Silnik, LPG i pobór oleju:**  
   *„Silnik bierze dużo oleju, dymi z wydechu przy gazowaniu, szarpie i gaśnie na wolnych (problem z odpalaniem znika po resecie klemy). Proszę sprawdzić drożność odmy, wyczyścić przepustnicę z adaptacją po czyszczeniu, ocenić świece zapłonowe oraz zmierzyć kompresję z próbą olejową (plus kontrola szczelności reduktora/wtryskiwaczy LPG).”*

---
*Podpisano: Anonymousik.is-a.dev*