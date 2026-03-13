# GW4 Pro Optimizer Suite 
STATUS: PRE-ALPHA
SEMI TESTED 

> **Kompleksowe narzędzie ADB do optymalizacji Samsung Galaxy Watch 4 po aktualizacji One UI 8.0 / WearOS 6.0**

[![Version](https://img.shields.io/badge/version-4.0.0-blue?style=flat-square)](CHANGELOG.md)
[![Shell](https://img.shields.io/badge/shell-bash%204%2B-green?style=flat-square)](https://www.gnu.org/software/bash/)
[![Platform](https://img.shields.io/badge/platform-SM--R870%20%7C%20SM--R875%20%7C%20SM--R895-lightgrey?style=flat-square)](https://www.samsung.com)
[![Android](https://img.shields.io/badge/Android-16%20(SDK%2036)-orange?style=flat-square)](https://developer.android.com)
[![License](https://img.shields.io/badge/license-MIT-yellow?style=flat-square)](LICENSE)

---

## Spis treści

- [O projekcie](#o-projekcie)
- [Kontekst techniczny](#kontekst-techniczny)
- [Wymagania](#wymagania)
- [Instalacja](#instalacja)
- [Konfiguracja zegarka](#konfiguracja-zegarka)
- [Użycie](#użycie)
- [Opis modułów](#opis-modułów)
- [Diagnostyka](#diagnostyka)
- [Przywracanie ustawień](#przywracanie-ustawień)
- [Ograniczenia](#ograniczenia)
- [Bezpieczeństwo](#bezpieczeństwo)
- [Licencja](#licencja)

---

## O projekcie

`gw4_optimizer.sh` to interaktywne narzędzie Bash, które łączy się z zegarkiem Galaxy Watch 4 przez **ADB over Wi-Fi** i stosuje precyzyjne poprawki systemowe bez konieczności rootowania urządzenia.

Skrypt powstał jako odpowiedź na powszechną regresję wydajności zgłaszaną przez społeczność użytkowników po wydaniu buildu `R870XXU1JYLYL6` (styczeń 2026). Każda implementowana poprawka jest oparta na analizie inżynieryjnej architektury Exynos W920 pod kontrolą Android 16 — nie na podejściu *trial-and-error*.

### Objawy, które skrypt adresuje

- Stutter i rwanie animacji interfejsu
- Lag 1–2 sekundy przy wybudzeniu ekranu z AOD
- Zamrożenia zegarka przy otwieraniu aplikacji (np. Spotify)
- Drastyczny drenaż baterii po aktualizacji
- Migotanie ekranu i niestabilne przejścia między widokami

---

## Kontekst techniczny

### Sprzęt — zweryfikowane stałe

| Parametr       | Wartość                        |
|----------------|--------------------------------|
| Model          | SM-R870 / SM-R875 / SM-R895    |
| SoC            | Exynos W920 (5 nm EUV)         |
| CPU            | 2× Cortex-A55 @ 1.18 GHz       |
| GPU            | Mali-G68 (2-core)              |
| RAM            | 1.5 GB LPDDR4X                 |
| System         | WearOS 6.0 / Android 16 SDK 36 |
| Docelowy build | R870XXU1JYLYL6                 |

### Dlaczego aktualizacja pogorszyła wydajność

Android 16 zaprojektowano z myślą o procesorach **big.LITTLE** z 4–8 rdzeniami. Exynos W920 posiada tylko **dwa identyczne rdzenie Cortex-A55** — brak rdzeni "big" sprawia, że nowoczesne mechanizmy jądra działają kontrproduktywnie:

| Mechanizm      | Problem na W920                                                              |
|----------------|------------------------------------------------------------------------------|
| **PELT**       | Zbyt krótkie okna analizy → thrashing częstotliwości → thermal throttle      |
| **MGLRU**      | Konflikt z agresywnym zRAM Samsunga (`swappiness=100`) → freeze przy przełączaniu aplikacji |
| **Vulkan**     | Wycieki pamięci w sterowniku Mali-G68 na Android 16 → niestabilne renderowanie |
| **HWC driver** | Bug w Hardware Composer → flickering i frame drops                           |
| **AOD driver** | Zbyt wolny voltage ramp GPU przy przejściu 1 Hz → 60 Hz → lag 1–2 s        |

---

## Wymagania

### Po stronie PC

| Wymaganie              | Wersja min. | Instalacja                                                                |
|------------------------|-------------|---------------------------------------------------------------------------|
| bash                   | 4.0+        | wbudowany (Linux/macOS) lub Git Bash / WSL2 (Windows)                    |
| Android Platform Tools | 34.0+       | [developer.android.com/tools/releases/platform-tools](https://developer.android.com/tools/releases/platform-tools) |
| adb                    | w PATH      | część Android Platform Tools                                              |

### Po stronie zegarka

- Samsung Galaxy Watch 4 (SM-R870, SM-R875 lub SM-R895)
- Build `R870XXU1JYLYL6` lub nowszy (One UI 8.0 / WearOS 6.0 / Android 16)
- Zegarek i PC w **tej samej sieci Wi-Fi**
- Włączone Opcje programisty z debugowaniem przez Wi-Fi

> **Uwaga:** Skrypt **nie wymaga roota**. Wszystkie operacje korzystają z uprawnień ADB (`shell`).
> Parametry jądra (`/proc/sys/`, `/sys/devices/`) mogą być niedostępne bez roota — skrypt wykrywa to i informuje o wyniku każdej operacji.

---

## Instalacja

```bash
# Pobierz skrypt
curl -O https://anonymousik.is-a.dev/scripts/atv/gw4_optimizer.sh

# Nadaj uprawnienia wykonania
chmod +x gw4_optimizer.sh

# Uruchom
bash gw4_optimizer.sh
```

Alternatywnie — klonowanie repozytorium:

```bash
git clone https://github.com/anonymousik/gw4-optimizer.git
cd gw4-optimizer
bash gw4_optimizer.sh
```

---

## Konfiguracja zegarka

Wykonaj **jednorazowo** przed pierwszym uruchomieniem skryptu.

### Krok 1 — Włącz Opcje programisty

```
Ustawienia → System → O oprogramowaniu → O zegarku
→ Numer kompilacji  [kliknij 7 razy]
→ Pojawi się: "Opcje programisty włączone"
```

### Krok 2 — Włącz debugowanie przez Wi-Fi

```
Ustawienia → Opcje programisty
→ Debugowanie przez Wi-Fi → Włącz
→ Zegarek wyświetli adres IP:PORT  ← zapisz
```

### Krok 3 — Zatwierdź klucz RSA

```bash
# Na PC — wpisz adres IP z kroku 2:
adb connect 192.168.X.X:5555
```

Na ekranie zegarka pojawi się dialog **„Czy zezwolić na debugowanie?"** — kliknij **Akceptuj**.

### Krok 4 — Weryfikacja

```bash
adb devices
# Oczekiwany wynik:
# 192.168.X.X:5555    device
```

> **Status `unauthorized`** — dialog RSA nie został zatwierdzony lub klucz wygasł.  
> **Status `offline`** — zegarek jest uśpiony; skrypt automatycznie próbuje go wybudzić (do 3 prób).

---

## Użycie

```bash
bash gw4_optimizer.sh
```

Skrypt automatycznie wykrywa podłączone urządzenie ADB (lub pyta o adres IP), weryfikuje model i firmware, tworzy backup ustawień i wyświetla interaktywne menu.

### Zalecana kolejność dla świeżej aktualizacji OTA

```
Z (Pakiet Kompleksowy)  →  restart zegarka  →  G (Kompilacja ART)
```

### Menu

```
  ══ OPTYMALIZACJE ══════════════════════════════════════════

  A) Animacje              ~2s   zero ryzyka, natychmiastowy efekt
  B) AOD — GPU voltage bug ~2s   główna przyczyna lagu wybudzenia
  C) SF / HWUI / Blur      ~5s   HWC bug fix + SkiaGL + blur off
  D) PELT / schedutil      ~2s   A55 2-core thrashing fix
  E) Pamięć (zRAM/MGLRU)  ~5s   swappiness 100→60, freeze fix
  F) Debloat + WAKE_LOCK   ~3s   One UI 8.0 + drenaż baterii
  G) Kompilacja ART        ~5min po aktualizacji OTA
  Z) PAKIET KOMPLEKSOWY    ~10min wszystkie fixy naraz

  ══ NARZĘDZIA ══════════════════════════════════════════════

  8) Diagnostyka systemu
  9) Przywróć ustawienia
  ?) Instrukcja ADB setup
  Q) Wyjście
```

---

## Opis modułów

### Fix A — Animacje

Skaluje prędkość animacji interfejsu (`window_animation_scale`, `transition_animation_scale`, `animator_duration_scale`). Efekt natychmiastowy, w pełni odwracalny. Dostępne tryby: `0.5×` (turbo), `0.0×` (wyłączone), `1.0×` (reset OEM).

### Fix B — AOD / GPU voltage ramp bug

**Główna przyczyna lagu przy wybudzeniu.** Sterownik Mali-G68 zbyt wolno podnosi napięcie szyny GPU przy przejściu z trybu AOD (1 Hz) do trybu aktywnego (60 Hz) — pierwsze kilka klatek jest renderowanych z ekstremalnie niską częstotliwością. Samsung nie wydał jeszcze patcha sterownika dla W920 (stan: marzec 2026).

Opcje: wyłącz AOD (całkowita eliminacja problemu), Low-Power AOD (ograniczone odświeżanie), przywróć.

### Fix C — SurfaceFlinger / HWUI / Background Blur

Pakiet trzech niezależnych poprawek renderowania:

**Force GPU composition** (`service call SurfaceFlinger 1008 i32 1`) — omija wadliwy sterownik Hardware Composer (HWC), eliminuje flickering i frame drops. Wbrew intuicji jest to zalecane na W920, ponieważ sterownik HWC w buildzie R870XXU1JYLYL6 zawiera buga.

**SkiaGL renderer** (`debug.hwui.renderer skiagl`) — stabilniejszy niż Vulkan na starych sterownikach W920. Vulkan na Android 16 powoduje wycieki pamięci przy renderowaniu HWUI.

**Background Blur off** (`supports_background_blur 0`) — efekty rozmycia tła One UI 8.0 mają nieproporcjonalny koszt obliczeniowy na Mali-G68 2-core.

### Fix D — PELT / schedutil

Koryguje parametry schedulera jądra Linux skalibrowane pod procesory big.LITTLE 4–8C, które na 2-core A55 powodują thrashing częstotliwości (agresywne skoki do 1.18 GHz → thermal throttle → rwanie animacji).

| Parametr             | Samsung default | Wartość optymalna | Efekt                                 |
|----------------------|-----------------|-------------------|---------------------------------------|
| `up_rate_limit_us`   | 500 µs          | **1 000 µs**      | Redukcja gwałtownych skoków taktowania |
| `down_rate_limit_us` | 20 000 µs       | **10 000 µs**     | Szybsze obniżanie po zadaniu          |
| `sched_latency_ns`   | 10 000 000 ns   | **8 000 000 ns**  | Redukcja opóźnienia wątku UI          |

> Parametry jądra resetują się przy restarcie. Dla trwałości wymagana aplikacja automatyzacji z wyzwalaczem `On Boot`.

### Fix E — Pamięć (zRAM / MGLRU / swappiness)

Samsung One UI 8.0 ustawia `vm.swappiness=100`. Na 2-core A55 agresywna kompresja/dekompresja zRAM blokuje oba rdzenie, objawiając się jako freeze 0.5–1.5 s przy otwieraniu aplikacji.

| Parametr                   | Samsung default | Wartość optymalna | Efekt                             |
|----------------------------|-----------------|-------------------|-----------------------------------|
| `vm.swappiness`            | 100             | **60**            | Redukcja narzutu zRAM na CPU      |
| `extra_free_kbytes`        | niskie          | **65 536 KB**     | Zapobiega direct reclaim (freeze) |
| `background_process_limit` | -1 (bez limitu) | **4**             | Kontrola liczby procesów tła      |

### Fix F — Debloat + WAKE_LOCK

| Pakiet / akcja                           | Problem                                    | Akcja              |
|------------------------------------------|--------------------------------------------|--------------------|
| `com.samsung.android.appcloud`           | Auto-restart w tle, zużycie CPU            | `pm disable-user`  |
| `com.google.android.assistant` WAKE_LOCK | Stały drenaż baterii, lagi wybudzenia      | `appops ignore`    |
| `com.android.vending` WAKE_LOCK          | Nadmiarowy WAKE_LOCK Play Store            | `appops ignore`    |
| `com.samsung.android.bixby.*`            | Stałe nasłuchiwanie w tle (opcjonalne)     | `pm disable-user`  |
| `com.samsung.android.messaging`          | Dublowanie powiadomień (opcjonalne)        | `pm disable-user`  |

> `pm disable-user --user 0` wyłącza pakiet dla bieżącego użytkownika — nie odinstalowuje go. Pełne przywrócenie: `adb shell pm enable NAZWA_PAKIETU`.

### Fix G — Kompilacja ART

Po aktualizacji OTA aplikacje pozostają w trybie `verified` (szybka instalacja, brak kompilacji JIT). Pierwsze uruchomienie każdej aplikacji jest znacznie wolniejsze. Moduł wymusza kompilację `speed-profile` (rekomendowane po OTA, ~5 min) lub `speed` dla wszystkich zainstalowanych pakietów.

---

## Diagnostyka

Opcja `8` zbiera komplet danych do katalogu `~/.gw4_optimizer/diag_YYYYMMDD_HHMMSS/`:

| Plik                  | Zawartość                                             |
|-----------------------|-------------------------------------------------------|
| `cpu_top.txt`         | Snapshot procesów CPU (Toybox-safe: `top -n 1 -d 1`)  |
| `mem_dump.txt`        | `dumpsys meminfo` + `/proc/meminfo` + zRAM/swap        |
| `scheduler.txt`       | Wartości `schedutil` i `sched_latency_ns`             |
| `gfx_info.txt`        | Frame timing, janky frames (`dumpsys gfxinfo`)        |
| `sf_dump.txt`         | Stan SurfaceFlinger                                   |
| `thermal.txt`         | Temperatura wszystkich stref termicznych W920          |
| `filtered_logs.txt`   | Logi pod kątem SF / AOD / GPU / PELT / Vulkan         |
| `RAPORT_ZBIORCZY.txt` | Skrócone podsumowanie — do wysłania przy zgłoszeniu   |

---

## Przywracanie ustawień

Opcja `9` przywraca ustawienia z ostatniego automatycznego backupu lub stosuje wartości fabryczne One UI 8.0, jeśli backup nie istnieje. Pliki backupu: `~/.gw4_optimizer/backup_YYYYMMDD_HHMMSS.txt`.

---

## Ograniczenia

**Parametry jądra nie są persistentne.** Zmiany `swappiness`, `schedutil` i `sched_latency_ns` są resetowane przy każdym restarcie. Trwałe zastosowanie wymaga aplikacji automatyzacji (np. Tasker z wyzwalaczem Autoboot).

**AOD bug wymaga patcha sterownika od Samsunga.** Wyłączenie AOD eliminuje objawy, lecz nie przyczynę — błąd w sterowniku GPU Mali-G68 pozostaje do czasu wydania oficjalnej aktualizacji.

**Nieobsługiwane modele.** Skrypt ostrzega przy wykryciu modelu innego niż SM-R870/R875/R895 i wymaga potwierdzenia przed kontynuacją.

---

## Bezpieczeństwo

- Skrypt nie wymaga roota na urządzeniu
- Skrypt nie modyfikuje partycji systemowych (`/system`, `/vendor`)
- Wszystkie zmiany są odwracalne przez opcję `9`
- Backup tworzony automatycznie przed każdą modyfikacją
- Skrypt nie nawiązuje żadnych połączeń sieciowych poza ADB

---

## Licencja

[MIT License](LICENSE) — skrypt nie jest powiązany z firmami Samsung ani Google.

Oparty na analizie technicznej architektury Exynos W920 pod kontrolą Android 16 oraz raportach społeczności XDA Developers i r/GalaxyWatch.
