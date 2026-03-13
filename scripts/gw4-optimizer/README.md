# GW4 Pro Optimizer Suite
STATUS:ALPHA 

[STRONA PROJEKTU](https://anonymousik.is-a.dev/scripts/gw4-optimizer)
<div align="center"> 

### Zaawansowane narzędzie ADB do naprawy regresji wydajności<br>Samsung Galaxy Watch 4 po aktualizacji One UI 8.0 / WearOS 6.0

[![Version](https://img.shields.io/badge/version-5.0.0-blue?style=flat-square&logo=github)](CHANGELOG.md)
[![Shell](https://img.shields.io/badge/shell-bash%204%2B-green?style=flat-square&logo=gnubash)](https://www.gnu.org/software/bash/)
[![Platform](https://img.shields.io/badge/SM--R870%20%7C%20SM--R875%20%7C%20SM--R895-lightgrey?style=flat-square&logo=samsung)](https://www.samsung.com)
[![WearOS](https://img.shields.io/badge/WearOS-6.0%20%2F%20Android%2016-orange?style=flat-square&logo=wear-os)](https://developer.android.com)
[![License](https://img.shields.io/badge/license-MIT-yellow?style=flat-square)](LICENSE)
---

### ⚡ One-Click Install

```bash
bash <(curl -sL https://raw.githubusercontent.com/anonymousik/anonymousik.github.io/refs/heads/main/scripts/gw4-optimizer/gw4_optimizer_v5.sh)
```

> Uruchom w **Termux na telefonie** (po włączeniu debugowania Wi-Fi na zegarku)  
> lub w dowolnym terminalu z `adb` w PATH.

</div>

---

## Spis treści

- [O projekcie](#o-projekcie)
- [Wymagania systemowe](#wymagania-systemowe)
- [Szybka instalacja](#szybka-instalacja)
- [Konfiguracja zegarka](#konfiguracja-zegarka)
- [Użycie](#użycie)
- [Schemat modułów](#schemat-modułów)
- [Diagnostyka](#diagnostyka)
- [Przywracanie i Factory Reset](#przywracanie-i-factory-reset)
- [Archiwum wersji](#archiwum-wersji)
- [Ograniczenia](#ograniczenia)
- [Bezpieczeństwo](#bezpieczeństwo)
- [Licencja](#licencja)

---

## O projekcie

`gw4_optimizer_v5.sh` to interaktywne narzędzie Bash uruchamiane na hoście (PC / telefon z Termux), które łączy się z zegarkiem Galaxy Watch 4 przez **ADB over Wi-Fi** i stosuje precyzyjne poprawki systemowe **bez rootowania urządzenia**.

Każda poprawka jest uzasadniona inżynieryjnie na poziomie architektury jądra Exynos W920 — nie opiera się na podejściu *trial-and-error*. Źródłem jest analiza techniczna regresji wydajności na platformie Android 16 / One UI 8.0 (styczeń 2026).

### Adresowane objawy

| Objaw | Przyczyna techniczna | Moduł |
|-------|---------------------|-------|
| Stutter / rwanie animacji | PELT miscalibration na 2-core A55 | Fix D |
| Lag 1–2 s przy wybudzeniu | GPU voltage ramp bug (AOD → active) | Fix B |
| Freeze przy otwieraniu aplikacji | zRAM aggressiveness (`swappiness=100`) | Fix E |
| Migotanie ekranu / frame drops | HWC driver bug w Mali-G68 | Fix C |
| Drenaż baterii po aktualizacji | WAKE_LOCK Google Assistant / Play | Fix F |
| Wolne uruchomienia po OTA | Brak kompilacji ART (tryb `verified`) | Fix G |

---

## Wymagania systemowe

### Smartwatch (urządzenie docelowe)

| Parametr | Wymaganie |
|----------|-----------|
| Model | Samsung Galaxy Watch 4: SM-R870 / SM-R875 / SM-R895 |
| SoC | Exynos W920 (5 nm EUV, 2× Cortex-A55 @ 1.18 GHz, Mali-G68) |
| RAM | 1.5 GB LPDDR4X |
| System | One UI 8.0 / WearOS 6.0 / Android 16 (SDK 36) |
| Build | `R870XXU1JYLYL6` lub nowszy (region XEO) |
| Sieć | Wi-Fi (ta sama sieć co host) |
| Opcje programisty | Włączone — Debugowanie przez Wi-Fi |
| Root | **Nie wymagany** |

### Środowisko uruchomieniowe (Host)

| Platforma | Wymaganie | Status |
|-----------|-----------|--------|
| **Termux** (Android) | `bash` 4+, `android-tools` (adb) | ✅ Obsługiwane |
| Linux (Ubuntu/Debian) | `bash` 4+, `adb` w PATH | ✅ Obsługiwane |
| macOS | `bash` 4+ (via Homebrew), `adb` | ✅ Obsługiwane |
| Windows (WSL2) | bash 4+, `adb.exe` w PATH | ✅ Obsługiwane |
| Windows (Git Bash) | `bash` 4+, `adb.exe` w PATH | ⚠ Wkrótce |
| ChromeOS (Crostini) | bash 4+, adb | 🔜 SOON |

> **Minimalna wersja ADB:** 34.0+ (Android Platform Tools)  
> Pobierz: [developer.android.com/tools/releases/platform-tools](https://developer.android.com/tools/releases/platform-tools)

---

## Szybka instalacja

### Termux (zalecane — zegarek + telefon = ta sama sieć)

```bash
# Krok 1 — Aktualizacja i instalacja zależności (jeden wiersz)
pkg update && pkg upgrade -y && pkg install -y android-tools curl bash

# Krok 2 — One-Click Install (uruchamia skrypt bez pobierania)
bash <(curl -sL https://raw.githubusercontent.com/anonymousik/anonymousik.github.io/refs/heads/main/scripts/gw4-optimizer/gw4_optimizer_v5.sh)
```

> **Wskazówka Termux:** IP zegarka znajdziesz w  
> `Ustawienia → Opcje programisty → Debugowanie przez Wi-Fi`

### Linux / macOS

```bash
# Pobierz i uruchom
curl -sL https://raw.githubusercontent.com/anonymousik/anonymousik.github.io/refs/heads/main/scripts/gw4-optimizer/gw4_optimizer_v5.sh -o gw4_optimizer_v5.sh
chmod +x gw4_optimizer_v5.sh
bash gw4_optimizer_v5.sh
```

### Windows WSL2 — SOON

```bash
# Upewnij się że adb.exe jest w PATH Windows i dostępny w WSL2
# wsl --install  (jeśli nie zainstalowany)
# Następnie: bash <(curl -sL ...)
```

### Git Bash / PowerShell — SOON

---

## Konfiguracja zegarka

Wykonaj **jednorazowo** przed pierwszym uruchomieniem.

### Krok 1 — Opcje programisty

```
Ustawienia → System → O oprogramowaniu → O zegarku
→ Numer kompilacji  ──►  kliknij 7 razy
→ Komunikat: "Opcje programisty włączone"
```

### Krok 2 — Debugowanie Wi-Fi

```
Ustawienia → Opcje programisty
→ Debugowanie przez Wi-Fi  →  Włącz
→ Zegarek wyświetli:  192.168.X.X:5555  ◄── zanotuj
```

### Krok 3 — Parowanie klucza RSA

```bash
adb connect 192.168.X.X:5555
# Na zegarku: "Czy zezwolić na debugowanie?" → [Akceptuj]
```

### Krok 4 — Weryfikacja

```bash
adb devices
# Oczekiwany wynik:
# List of devices attached
# 192.168.X.X:5555    device
```

| Status ADB | Znaczenie | Rozwiązanie |
|------------|-----------|-------------|
| `device` | ✅ Gotowy | — |
| `unauthorized` | Dialog RSA nie zatwierdzony | Akceptuj na zegarku |
| `offline` | Zegarek uśpiony | Skrypt auto-wybudza (3 próby) |

---

## Użycie

```bash
bash gw4_optimizer_v5.sh
# lub One-Click:
bash <(curl -sL https://raw.githubusercontent.com/anonymousik/anonymousik.github.io/refs/heads/main/scripts/gw4-optimizer/gw4_optimizer_v5.sh)
```

### Zalecana kolejność po OTA

```
Z  (Pakiet Kompleksowy)
  └─► restart zegarka
      └─► G  (Kompilacja ART)  ◄── wymaga min. 20% baterii
```

### Interfejs CLI

```
  ╔══════════════════════════════════════════════════════════════════════╗
  ║  GW4 Pro Optimizer Suite  v5.0.0                                   ║
  ║  SM-R870/75/95 · Exynos W920 (A55 2C / Mali-G68) · One UI 8.0     ║
  ╠══════════════════════════════════════════════════════════════════════╣
  ║  ⚡ 192.168.1.X:5555  |  SM-R870  |  SDK 36                        ║
  ║    R870XXU1JYLYL6                                                   ║
  ║    Bateria: 87%                                                     ║
  ╚══════════════════════════════════════════════════════════════════════╝

  ─── OPTYMALIZACJE ─────────────────────────────────────────────────────
  A) Animacje              ~2s  │ zero ryzyka, efekt natychmiastowy
  B) AOD — GPU voltage bug ~2s  │ główna przyczyna lag wybudzenia
  C) SF/HWUI/Blur          ~5s  │ HWC bug fix + SkiaGL + blur off
  D) PELT/schedutil        ~2s  │ A55 2-core thrashing fix
  E) Pamięć (zRAM/MGLRU)  ~5s  │ swappiness 100→60, freeze fix
  F) Debloat + WAKE_LOCK   ~3s  │ One UI 8.0 + bateria
  G) Kompilacja ART        ~5m  │ po OTA │ min. 20% bat.
  Z) PAKIET KOMPLEKSOWY    ~10m │ wszystkie fixy naraz

  ─── NARZĘDZIA ─────────────────────────────────────────────────────────
  8) Diagnostyka systemu
  9) Przywróć ustawienia
  R) Factory Reset          Master Clear (2-step confirm)
  ?) Instrukcja ADB setup
  Q) Wyjście
```

---

## Schemat modułów

Każdy moduł opisany wg schematu: **Nazwa → Cel → Działanie**.

---

### Fix A — Animacje

**Cel:** Redukcja czasu trwania animacji interfejsu bez ryzyka destabilizacji systemu.

**Działanie:**
```
settings get global window_animation_scale       → odczyt stanu
  jeśli ≠ żądana wartość:
settings put global window_animation_scale X     → zmiana
settings put global transition_animation_scale X
settings put global animator_duration_scale X
```
Dostępne wartości: `0.5×` (turbo) · `0.0×` (wyłączone) · `1.0×` (OEM default).  
Operacja idempotentna — pomija zmianę jeśli wartość jest już ustawiona.

---

### Fix B — AOD / GPU Voltage Ramp Bug

**Cel:** Eliminacja lagu 1–2 s przy wybudzeniu ekranu z AOD.

**Działanie:**
```
settings get secure doze_always_on              → odczyt stanu AOD
  Bug: Mali-G68 driver zbyt wolny voltage ramp:
  AOD state (GPU @ 1Hz partial) → active (GPU @ 60Hz)
  → pierwsze klatki renderowane z ekstremalnie niską częstotliwością
  
Opcja 1 (zalecane):
  settings put secure doze_always_on 0          → wyłącz AOD całkowicie
  settings put secure doze_enabled 0            → wyłącz ambient display

Opcja 3 (kompromis):
  setprop persist.sys.sf.aod_refresh_rate 1     → ogranicz odświeżanie
```
> Samsung nie wydał patcha sterownika Mali-G68 dla W920 (stan: marzec 2026).

---

### Fix C — SurfaceFlinger / HWUI / Background Blur

**Cel:** Naprawa flickeringu, frame drops i wycieków pamięci renderowania.

**Działanie:**
```
┌─ SF Force GPU ───────────────────────────────────────────────────────┐
│  service call SurfaceFlinger 1008 i32 1                              │
│  HWC driver w buildzie R870XXU1JYLYL6 zawiera buga → Force GPU omija │
│  wadliwy Hardware Composer i eliminuje flickering                    │
├─ HWUI SkiaGL renderer ───────────────────────────────────────────────┤
│  setprop debug.hwui.renderer skiagl                                  │
│  Vulkan na Android 16 + stare sterowniki Mali-G68 → wycieki pamięci  │
│  OpenGL ES (SkiaGL) = dojrzałe sterowniki, stabilne renderowanie     │
├─ HWUI optimization flags ────────────────────────────────────────────┤
│  setprop debug.hwui.skip_empty_damage true                           │
│  setprop debug.hwui.use_buffer_age true                              │
└─ Background Blur off ────────────────────────────────────────────────┘
   settings put global supports_background_blur 0
   Efekty blur One UI 8.0 → nieproporcjonalny koszt na Mali-G68 2-core
```

---

### Fix D — PELT / schedutil

**Cel:** Korekcja parametrów schedulera jądra Linux dla architektury 2-core A55.

**Działanie:**
```
Android 16 PELT: skalibrowany pod big.LITTLE 4-8C
  Problem na W920 (2× A55, brak rdzeni "big"):
  up_rate_limit_us=500 → zbyt agresywne podbijanie → thermal throttle

Korekcja:
  /sys/devices/system/cpu/cpufreq/policy0/schedutil/
    up_rate_limit_us:    500  → 1000  µs  (redukcja thrashingu)
    down_rate_limit_us:  20000 → 10000 µs  (szybsze obniżanie)
  /proc/sys/kernel/sched_latency_ns:  10M → 8M ns  (priorytet UI thread)
  /proc/sys/kernel/sched_boost:       0 → 1         (priorytet interakcji)
```
> ⚠ Parametry jądra są **nietrwałe** — resetują się po restarcie.

---

### Fix E — Pamięć (zRAM / MGLRU / swappiness)

**Cel:** Eliminacja freeze 0.5–1.5 s przy otwieraniu aplikacji.

**Działanie:**
```
Samsung One UI 8.0 default: vm.swappiness=100 (agresywne zRAM)
  Problem: kompresja/dekompresja zRAM blokuje oba rdzenie A55
  Objaw: freeze przy Spotify, galeria, mapy

Korekcja:
  /proc/sys/vm/swappiness:           100 → 60    (redukcja narzutu CPU)
  /proc/sys/vm/extra_free_kbytes:      0 → 65536 (bufor przed direct reclaim)
  settings put global background_process_limit 4  (kontrola procesów tła)
  settings put global monitor_phantom_procs false (nie zabijaj czujników)
  pm trim-caches 0                                (natychmiastowe zwolnienie)
```

---

### Fix F — Debloat + WAKE_LOCK

**Cel:** Redukcja bezczynnego zużycia CPU i drenażu baterii przez procesy One UI 8.0.

**Działanie:**
```
Cel → Akcja → Pakiet

WAKE_LOCK restrict:
  cmd appops set com.google.android.assistant WAKE_LOCK ignore
  cmd appops set com.android.vending WAKE_LOCK ignore

pm disable-user --user 0:
  com.samsung.android.appcloud    → auto-restart w tle, CPU idle
  com.samsung.android.bixby.*    → nasłuchiwanie tła (opcjonalne)
  com.samsung.android.messaging  → duplikacja powiadomień (opcjonalne)
```
> `pm disable-user` nie usuwa pakietu — przywracanie: `adb shell pm enable PAKIET`

---

### Fix G — Kompilacja ART

**Cel:** Eliminacja lagów pierwszego uruchomienia aplikacji po aktualizacji OTA.

**Działanie:**
```
Guard: dumpsys battery | grep level
  Jeśli poziom < 20% → blokada z komunikatem  ← nowość v5.0

Po OTA: aplikacje w trybie "verified" (brak kompilacji JIT)

Kompilacja:
  SDK ≥ 33: pm compile -m speed-profile -a     (~5 min, zalecane)
  SDK < 33: cmd package compile -m speed-profile --all

Auto-wake: KEYCODE_WAKEUP co 1.5s podczas kompilacji
Post-compile: cmd package bg-dexopt-job
```

---

### Pakiet Kompleksowy (Z)

**Cel:** Jednorazowe zastosowanie wszystkich optymalizacji po aktualizacji OTA.

**Działanie:** Sekwencyjne wywołanie fixów A → B → C → D → E → F z idempotentną weryfikacją stanu przed każdą operacją. Pełny pasek postępu (22 kroki). Automatyczny backup przed zmianami.

---

## Diagnostyka

Opcja `8` — zbiera dane do `~/.gw4_optimizer/diag_YYYYMMDD_HHMMSS/`:

| Plik | Zawartość | Metoda |
|------|-----------|--------|
| `cpu_top.txt` | Procesy CPU | `top -n 1 -d 1` (Toybox-safe) |
| `sf_dump.txt` | Stan SurfaceFlinger | `dumpsys SurfaceFlinger` (bez `--latency`) |
| `gfx_info.txt` | Frame timing, janky frames | `dumpsys gfxinfo` |
| `mem_dump.txt` | RAM, zRAM, swappiness | `dumpsys meminfo` + `/proc/meminfo` |
| `scheduler.txt` | schedutil params | `/sys/devices/system/cpu/...` |
| `thermal.txt` | Temperatura stref W920 | `dumpsys battery` + thermal zones |
| `filtered_logs.txt` | Logi SF / AOD / GPU / PELT | `logcat -d *:W` + grep |
| `RAPORT_ZBIORCZY.txt` | Podsumowanie | Agregacja powyższych |

> 📎 Prześlij `RAPORT_ZBIORCZY.txt` przy zgłaszaniu problemu.

---

## Przywracanie i Factory Reset

### Przywracanie ustawień (opcja `9`)

Automatyczny backup tworzony przed każdą modyfikacją (`~/.gw4_optimizer/backup_*.txt`). Opcja `9` przywraca z wybranego pliku lub stosuje wartości fabryczne One UI 8.0 jeśli brak backupu.

### Factory Reset / Master Clear (opcja `R`)

Twardy reset — **operacja nieodwracalna**. Wymaga dwustopniowego potwierdzenia:

```
Potwierdzenie 1/2 → wpisz: RESET
Potwierdzenie 2/2 → wpisz: POTWIERDZAM
  └─► odliczanie 30s (przerwanie dowolnym klawiszem)
      └─► wysłanie polecenia Master Clear
          └─► skrypt zamyka się (ADB autoryzacja wygasa)
```

**Po restarcie:**
1. Przejdź konfigurację pierwszego uruchomienia zegarka
2. Połącz z Wi-Fi i sparuj z Galaxy Watch Manager
3. Włącz: Opcje programisty → Debugowanie przez Wi-Fi
4. Uruchom skrypt ponownie → Pakiet Kompleksowy (Z)
5. Fix G (Kompilacja ART) — po naładowaniu do >20%

---

## Archiwum wersji

Historyczne wersje skryptu dostępne pod adresem:

```
https://raw.githubusercontent.com/anonymousik/anonymousik.github.io/refs/heads/main/scripts/gw4-optimizer/UPDATES/{version}/gw4_optimizer_{version}.sh
```

| Wersja | Data | Kluczowa zmiana |
|--------|------|-----------------|
| `v5.0.0` | 2026-03-13 | WearOS-Style CLI, idempotentne operacje, Factory Reset, battery guard ART, countdown/reconnect |
| `v4.0.0` | 2026-03-13 | Integracja raportu inżynieryjnego: PELT fix, SkiaGL, swappiness, WAKE_LOCK |
| `v3.0.0` | 2026-03-13 | Pełna przebudowa, menu interaktywne, backup, Toybox-safe diagnostyka |
| `v2.1.0` | 2026-03-10 | GW4 Pro-Active Fixer (legacy) |
| `v2.0.0` | 2026-03-10 | GW4 System Diagnostics Tool (legacy) |

Przykład pobrania archiwum:
```bash
curl -sL https://raw.githubusercontent.com/anonymousik/anonymousik.github.io/refs/heads/main/scripts/gw4-optimizer/UPDATES/v4.0.0/gw4_optimizer_v4.0.0.sh -O
```

---

## Ograniczenia

**Parametry jądra nietrwałe.** Zmiany `swappiness`, `schedutil` i `sched_latency_ns` resetują się przy każdym restarcie. Trwałe zastosowanie wymaga aplikacji automatyzacji (np. Tasker z wyzwalaczem `On Boot`) lub modyfikacji na poziomie roota.

**AOD bug — brak patcha sterownika.** Wyłączenie AOD (Fix B opcja 1) eliminuje objawy, lecz nie przyczynę — błąd w sterowniku GPU Mali-G68 pozostaje do czasu wydania oficjalnej aktualizacji Samsung.

**Fix G wymaga min. 20% baterii.** Kompilacja ART jest energochłonna — skrypt blokuje operację przy niskim poziomie naładowania i informuje użytkownika.

**Nieobsługiwane modele.** Skrypt ostrzega przy wykryciu modelu innego niż SM-R870/R875/R895 i wymaga jawnego potwierdzenia.

---

## Bezpieczeństwo

| Właściwość | Stan |
|------------|------|
| Wymaga roota na zegarku | ❌ Nie |
| Modyfikuje partycje systemowe | ❌ Nie |
| Nawiązuje połączenia sieciowe poza ADB | ❌ Nie |
| Backup przed każdą modyfikacją | ✅ Automatyczny |
| Wszystkie zmiany odwracalne (opcja 9) | ✅ Tak |
| Factory Reset — 2-stopniowe potwierdzenie | ✅ Tak |
| `pm disable-user` vs odinstalowanie | ✅ Tylko disable (przywracalne) |

---

## Licencja

[MIT License](LICENSE) — projekt nie jest powiązany z Samsung Electronics ani Google LLC.

Oparty na:
- Analizie technicznej regresji wydajności platformy Exynos W920 / WearOS 6.0 (styczeń 2026)
- Raportach społeczności XDA Developers i r/GalaxyWatch
- Specyfikacji Android 16 PELT/schedutil i MGLRU
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
curl -O https://anonymousik.is-a.dev/scripts/gw4_optimizer_v4.sh

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

**AOD bug wymaga patcha sterownika od Samsunga.** Wyłączenie AOD eliminuje objawy, lecz nie przyczynę — błąd w sterowniku GPU Mali-G68 pozostaje do czasu wydania oficjalnej aktualizacji 

LUB WYKONAMY TO ZA SAMSUNGA! 😃🤚 LECZ BĘDZIE SIĘ TO WIĄZAĆ Z KONIECZNOŚCIĄ NADANIA UPRAWNIEŃ ROOT I POTENCJALNIE WIĄZAĆ Z STAŁYM UCEGLENIEM PRZY NIEUMIEJĘTNYM ZASTOSOWANIU SIĘ DO KONSTRUKCJI ) .

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
