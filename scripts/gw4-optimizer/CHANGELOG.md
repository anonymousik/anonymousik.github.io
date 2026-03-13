# Changelog

Wszystkie istotne zmiany w projekcie są dokumentowane w tym pliku.

Format oparty na [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Wersjonowanie zgodne z [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [4.0.0] — 2026-03-13

### Kontekst wydania

Wersja 4.0 jest pełną przebudową opartą na analizie inżynieryjnej regresji wydajności platformy Exynos W920 pod kontrolą WearOS 6.0 / Android 16 (build `R870XXU1JYLYL6`, styczeń 2026) oraz zgłoszeniach użytkowników z XDA Developers i r/GalaxyWatch. Każda poprawka jest uzasadniona technicznie na poziomie architektury jądra i sterowników sprzętowych, a nie na zasadzie empirycznej.

### Added

- **Fix D — PELT/schedutil:** Nowy moduł korygujący parametry schedulera jądra Linux dostosowane do procesorów big.LITTLE 4–8C, które na 2-core Cortex-A55 powodują thrashing częstotliwości. Wartości optymalne wg analizy inżynieryjnej: `up_rate_limit_us` 500→1000 µs, `down_rate_limit_us` 20000→10000 µs, `sched_latency_ns` 10M→8M ns. Dodano wymuszenie `sched_boost=1` dla priorytetyzacji wątków UI.
- **Fix C — HWUI SkiaGL renderer:** Wymuszenie backendu `skiagl` zamiast Vulkan (`setprop debug.hwui.renderer skiagl`). Vulkan na Android 16 ze starymi sterownikami Mali-G68 powoduje wycieki pamięci i niestabilne renderowanie HWUI.
- **Fix C — HWUI optimization flags:** Dodano `debug.hwui.skip_empty_damage=true` i `debug.hwui.use_buffer_age=true` — redukcja zbędnych draw calls i optymalizacja przepustowości bufora ramki.
- **Fix C — Background Blur off:** Wyłączenie efektów rozmycia tła One UI 8.0 (`supports_background_blur=0` via `settings put global` + `setprop`). Na Mali-G68 2-core koszt obliczeniowy blur jest nieproporcjonalnie wysoki w stosunku do efektu wizualnego.
- **Fix E — vm.swappiness:** Redukcja agresywności zRAM: Samsung One UI 8.0 ustawia `swappiness=100`; wartość optymalna `60` eliminuje freeze 0.5–1.5 s przy przełączaniu aplikacji na 2-core A55.
- **Fix E — extra_free_kbytes:** Dodano `vm.extra_free_kbytes=65536` zapobiegające wejściu w direct reclaim (synchroniczne zatrzymanie procesów podczas odzyskiwania RAM).
- **Fix F — WAKE_LOCK restrictions:** Dodano `cmd appops set com.google.android.assistant WAKE_LOCK ignore` i `cmd appops set com.android.vending WAKE_LOCK ignore`. Kluczowe dla redukcji drenażu baterii — bez ryzykownego `pm disable` dla aplikacji systemowych Google.
- **Fix F — Debloat lista:** Rozszerzono o `com.samsung.android.appcloud` (auto-restart w tle, zużycie CPU w stanie bezczynności) oraz opcjonalne wyłączenie `com.samsung.android.bixby.*` i `com.samsung.android.messaging`.
- **Diagnostyka — scheduler.txt:** Nowy plik w zestawie diagnostycznym zawierający aktualne wartości `schedutil` i `sched_latency_ns` — kluczowe przy zgłaszaniu problemów z wydajnością.
- **Backup — parametry jądra:** Backup przed modyfikacją teraz obejmuje wartości `schedutil` i `swappiness` (wcześniej tylko `settings` i `getprop`).
- **Stałe sprzętowe:** Dodano `SCHED_UP_RATE_LIMIT_US_DEFAULT`, `SCHED_UP_RATE_LIMIT_US_OPT`, `SCHED_DOWN_RATE_LIMIT_US_DEFAULT`, `SCHED_DOWN_RATE_LIMIT_US_OPT`, `SCHED_LATENCY_NS_DEFAULT`, `SCHED_LATENCY_NS_OPT`, `VM_SWAPPINESS_SAMSUNG_DEFAULT`, `VM_SWAPPINESS_OPT`, `VM_EXTRA_FREE_KB` — parametry jako udokumentowane stałe z uzasadnieniem.

### Changed

- **[KOREKTA KRYTYCZNA] Fix C — SurfaceFlinger 1008:** W poprzedniej wersji (v3.0) komenda `service call SurfaceFlinger 1008 i32 1` była oznaczona jako *nie zalecana* z ostrzeżeniem o pogorszeniu wydajności. Analiza inżynieryjska wykazała, że sterownik HWC (Hardware Composer) Mali-G68 w buildzie R870XXU1JYLYL6 zawiera buga powodującego flickering i frame drops — Force GPU composition jest **zalecanym** obejściem dla W920. Menu Fix C zostało przeprojektowane, opcja 1 (pełny fix renderowania) teraz domyślnie włącza Force GPU.
- **Fix B — AOD:** Rozbudowano kontekst techniczny o opis mechanizmu błędu: GPU voltage ramp zbyt wolny przy przejściu AOD (1 Hz) → active (60 Hz). Menu teraz informuje o braku patcha sterownika od Samsunga (stan: marzec 2026).
- **Pakiet Kompleksowy (Z):** Zaktualizowano kolejność i zawartość — dodano wszystkie nowe fixy (PELT, SkiaGL, blur, swappiness, WAKE_LOCK). Liczba kroków wzrosła z 12 do 22. Force GPU jest teraz częścią pakietu domyślnego (zmiana relative do v3.0).
- **Przywracanie (opcja 9):** Rozszerzono przywracanie fabryczne o `WAKE_LOCK allow` dla Assistant i Play Store oraz `setprop debug.hwui.renderer ""` i przywrócenie `swappiness=100` (wartość OEM Samsung).
- **Stałe:** `ADB_TIMEOUT` zwiększone z 10 do 12 sekund — poprawa niezawodności przy uśpionym zegarku.

### Fixed

- **Diagnostyka — `top -b -n 1 -m 10`:** Flagi `-b` (batch) i `-m` (max processes) nie istnieją w Toybox (shell WearOS). Zastąpione przez `top -n 1 -d 1` z fallbackiem do `top -n 1` i `ps -A`.
- **Diagnostyka — `dumpsys SurfaceFlinger --latency`:** Flaga `--latency` nie jest obsługiwana na WearOS 6.0 — usunięta. `dumpsys SurfaceFlinger` wywołane bez flagi z `timeout 5` zapobiegającym zawieszeniu.
- **Backup — `settings delete` dla wartości `null`:** Naprawiono obsługę kluczy, które nie mają ustawionej wartości — poprzednio próba `settings put global KEY null` zapisywała literalne `"null"` jako wartość.
- **Restore — kernel paths:** Plik backupu teraz poprawnie przechowuje i przywraca wartości z `/proc/sys/` i `/sys/devices/` (nowa kategoria `KERNEL:` w pliku backup).
- **`_sh_retry` — auto-wake przy timeout:** Funkcja teraz wysyła `KEYCODE_WAKEUP` między próbami, co eliminuje false timeout przy uśpionym zegarku.

### Deprecated

- Opcja SF phase offset (`debug.sf.phase_offset_ns` / `debug.sf.early_phase_offset_ns`) — zastąpiona przez Force GPU composition i SkiaGL, które adresują przyczynę problemu (bug HWC), a nie objawy. Parametry phase offset pozostają dostępne jako część Fix C opcja 1 (pełny pakiet).

---

## [3.0.0] — 2026-03-13

### Kontekst wydania

Pełna przebudowa od zera na bazie raportów użytkowników. Zastąpił skrypty `GW4 Pro-Active Fixer v2.1` i `GW4 System Diagnostics Tool v2.0`, które zawierały liczne błędy krytyczne.

### Added

- Interaktywne menu z 6 modułami optymalizacyjnymi (A–G bez D) i narzędziami diagnostycznymi
- Automatyczny backup ustawień przed każdą modyfikacją (plik `backup_YYYYMMDD_HHMMSS.txt`)
- Funkcja przywracania ustawień z backupu lub z wartości fabrycznych OEM
- Auto-wykrywanie podłączonych urządzeń ADB (bez podawania IP przy istniejącym połączeniu)
- Mechanizm retry (do 3 prób) z auto-wake (`KEYCODE_WAKEUP`) przy uśpionym zegarku
- Weryfikacja modelu urządzenia (ostrzeżenie dla modeli spoza SM-R8xx)
- Odczyt i wyświetlanie parametrów urządzenia: model, firmware, SDK, hardware
- Diagnostyka Toybox-safe z 7 plikami wynikowymi i raportem zbiorczym
- Pasek postępu (`_bar`) dla długotrwałych operacji
- Kolorowe logi z fallbackiem dla środowisk bez tty
- Sesyjny plik logów (`session_YYYYMMDD_HHMMSS.log`)
- Fix: Animacje (A), AOD (B), SurfaceFlinger (C), Pamięć (E), Debloat (F), Kompilacja ART (G), Pakiet Kompleksowy (Z)
- Wbudowana instrukcja konfiguracji ADB (opcja `?`)

### Fixed

- `stop logd` — zastąpione przez bezpieczne `logcat -c` + `setprop logd.buffer.size 64K`
- Brak weryfikacji połączenia ADB przed wykonaniem komend
- `IP=TWOJE_IP` — zastąpione przez interaktywne pytanie o adres
- `top -b -n 1 -m 10` — zastąpione przez `top -n 1 -d 1` (Toybox-safe)
- `dumpsys SurfaceFlinger --latency` — usunięta nieobsługiwana flaga
- `cmd package bg-dexopt-job` — zastąpione przez `pm compile -m speed-profile -a` (Android 13+/SDK 33+)
- Brak obsługi `device unauthorized` / `offline` / `wrong key` — dodana pełna obsługa z komunikatami

---

## [2.1.0] — 2026-03-10 *(GW4 Pro-Active Fixer — legacy)*

> Wersja historyczna. Zawierała błędy krytyczne opisane w sekcji Fixed wersji 3.0.0.

### Added

- `service call SurfaceFlinger 1008 i32 1` (wyłączenie HW Overlays)
- `settings put global high_priority_render_thread 1`
- `settings put global monitor_phantom_procs false`
- `stop logd` *(błąd krytyczny — usunięty w v3.0)*

---

## [2.0.0] — 2026-03-10 *(GW4 System Diagnostics Tool — legacy)*

> Wersja historyczna. Zawierała błędy Toybox opisane w sekcji Fixed wersji 3.0.0.

### Added

- `top -b -n 1 -m 10` *(błąd — flagi nieistniejące w Toybox)*
- `dumpsys SurfaceFlinger --latency` *(błąd — flaga nieobsługiwana na WearOS)*
- `dumpsys gfxinfo`, `dumpsys meminfo`, `cat /proc/meminfo`
- `logcat -d *:W`

---

[4.0.0]: https://github.com/anonymousik/gw4-optimizer/compare/v3.0.0...v4.0.0
[3.0.0]: https://github.com/anonymousik/gw4-optimizer/compare/v2.1.0...v3.0.0
[2.1.0]: https://github.com/anonymousik/gw4-optimizer/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/anonymousik/gw4-optimizer/releases/tag/v2.0.0
