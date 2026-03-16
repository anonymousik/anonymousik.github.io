# Changelog — GW4 Pro Optimizer Suite

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · [SemVer](https://semver.org/)

---

## [6.0.0] — 2026-03-16

### Kontekst wydania

Wersja 6.0 integruje pięć dostarczonych dokumentów technicznych:
- **Raport PDF** — Analiza techniczna regresji Exynos W920 / WearOS 6.0 / Android 16 (styczeń 2026)
- **ANALIZA_REGRESJI_Android16.md** — Inżynieria odwrotna fixów (marzec 2026, FerroART)
- **Shizuku_Deployer_secferro_sh.txt** — SecFerro Division v2.1.1-FIX (rish deploy method)
- **ADBWebWIFI_SECFERRO.pdf** — WebUSB ADB Bootstrap architektura
- **gw4_optimizer_v5_2.sh** — Baza (v5.1.0 z drobną rozbieżnością VERSION)

### Added

- **Fix I — I/O Scheduler + sched_boost (opcja `I`):**
  Raport PDF str.1 identyfikuje `sched_boost` jako źródło problemu: One UI 8.0 faworyzuje
  procesy tła Google Play kosztem wątku UI (SurfaceFlinger). `sched_boost=1` wymusza
  priorytet wątków renderowania na 2-core Cortex-A55. Scheduler I/O `deadline` zastępuje
  `cfq` dla deterministycznego latency przy zRAM swap — krytyczne przy 1.5GB RAM.
  Tryby: (1) oba fixy, (2) tylko sched_boost, (3) tylko I/O, (4) przywróć.
  Stałe: `SCHED_BOOST_OPT=1`, `SCHED_BOOST_PATH`, `IO_SCHED_OPT="deadline"`.

- **Fix J — Shizuku/rish (opcja `J`):**
  Pełna implementacja na bazie `Shizuku_Deployer_secferro_sh.txt` (SecFerro Division
  v2.1.1-FIX). Shizuku umożliwia stosowanie fixów z uprawnieniami ADB-level bez kabla
  po jednorazowej konfiguracji. Funkcje:
  - `_shizuku_deploy_rish()` — wstrzykuje skrypt proxy rish do `/data/local/tmp/rish`
    metodą SecFerro (CLASSPATH + app_process + moe.shizuku.manager.shell.Shell)
  - `_shizuku_test_rish()` — weryfikacja działania rish przez `id` command
  - `_shizuku_apply_fixes()` — stosuje fixy A+C+E+F+I przez rish bez kabla ADB
  - `_shizuku_guide()` — instrukcja instalacji Shizuku na WearOS 6.0
  Stałe: `SHIZUKU_PKG`, `SHIZUKU_APK_URL`, `RISH_PATH=/data/local/tmp/rish`.

- **Fix K — Diagnostyka rozszerzona v6.0 (opcja `K`):**
  8 nowych wskaźników diagnostycznych z raportów styczeń + marzec 2026:
  1. `art_state.txt` — `compilationReason` + `compilerFilter` per-pakiet (walidacja JIT)
  2. `launch_timing.txt` — `am start -W` cold start timing, próg: 800ms
  3. `battery_stats.txt` — `dumpsys batterystats` idle drain + top WAKE_LOCK holders
  4. `lmk_events.txt` — `LowMemoryKiller` kills, próg alarmowy: 3 kills/h
  5. `rendering_diag.txt` — dirty_regions, Vulkan check, device_config SF dump
  6. `scheduler_state.txt` — sched_boost, I/O scheduler, schedutil per-device
  7. `art_runtime_flags.txt` — device_config runtime_native_boot, WiFi ADB state
  8. `RAPORT_v6.txt` — raport zbiorczy z progami alarmowymi
  Progi z raportu PDF: janky > 5%, battery idle > 2%/h, launch > 800ms, LMK > 3/h.

### Changed

- **Fix C rozszerzony — `render_dirty_regions=false`:**
  Dodano `setprop debug.hwui.render_dirty_regions false` do pakietu HWUI flags (opcja 1).
  Raport PDF identyfikuje dirty region tracking jako zbędny koszt na Mali-G68 2-core.

- **Fix F rozszerzony — shealth WAKE_LOCK:**
  `cmd appops set com.samsung.android.wear.shealth WAKE_LOCK ignore` dodane do opcji 1
  (bezpieczny debloat). Raport PDF str.3 identyfikuje `com.samsung.android.wear.shealth`
  jako 4. pakiet powodujący idle drain na One UI 8.0 (autodetekcja treningów).

- **Fix H rozszerzony — `disable_jit_zygote`:**
  `device_config put runtime_native_boot disable_jit_zygote false` — wyłącza JIT sampling
  w procesie Zygote, eliminuje background CPU spikes podczas inicjalizacji aplikacji.
  Źródło: ANALIZA_REGRESJI_Android16.md sekcja Krok 1.

- **Pakiet Kompleksowy (Z) — rozszerzony do 28 kroków:**
  Dodano 3 nowe kroki: sched_boost=1, I/O deadline, dirty_regions, shealth WAKE_LOCK,
  disable_jit_zygote. Summary zaktualizowane o nowe fixy v6.0.

- **VERSION:** 5.1.0 → 6.0.0
- **Nagłówek skryptu:** zaktualizowany changelog inline.

### Nowe stałe (§0)

```bash
SHIZUKU_PKG="moe.shizuku.privileged.api"
SHIZUKU_APK_URL="https://github.com/RikkaApps/Shizuku/releases/latest/download/shizuku.apk"
RISH_PATH="/data/local/tmp/rish"
IO_SCHED_OPT="deadline"
IO_SCHED_DEFAULT="cfq"
SCHED_BOOST_OPT=1
SCHED_BOOST_PATH="/proc/sys/kernel/sched_boost"
DIAG_JANKY_THRESHOLD=5        # > 5% janky → alarm
DIAG_BATTERY_IDLE_THRESHOLD=2 # > 2% / h idle → alarm
DIAG_APP_LAUNCH_THRESHOLD=800 # > 800ms am start -W → alarm
```

### Źródła i uzasadnienie techniczne

| Fix | Źródło | Problem | Rozwiązanie |
|-----|--------|---------|-------------|
| sched_boost=1 | PDF str.1 | One UI 8.0 faworyzuje procesy tła | UI thread = wyższy priorytet schedulera |
| I/O deadline | Analiza MD | CFQ nieoptymalne dla NAND/zRAM swap | Deterministyczne latency |
| dirty_regions=false | PDF str.3 | Zbędny draw call overhead | Wyłącz dirty region tracking |
| shealth WAKE_LOCK | PDF str.3 | Autodetekcja treningów = CPU idle | appops WAKE_LOCK ignore |
| disable_jit_zygote | Analiza MD | JIT sampling = background spikes | device_config runtime flag |
| Shizuku/rish | SecFerro deployer | Kabel ADB wymagany przy każdej sesji | rish proxy = fixy bez kabla |
| Diag K — compilationReason | Analiza MD | Weryfikacja stanu ART post-OTA | am start -W + dumpsys package |
| Diag K — am start -W | PDF + Analiza | Launch lag > 800ms = JIT thrashing | Timing benchmark per-app |
| Diag K — batterystats | Analiza MD | Idle drain > 2%/h | WAKE_LOCK holders analysis |
| Diag K — LMK events | Analiza MD | OOM killer > 3/h | logcat events + am_kill |

---

## [5.2.0] — 2026-03-14

Trwałość parametrów (Tasker XML, root hook, daemon), wsparcie Exynos 2100/2200,
profil sesji, diagnostyka różnicowa, CLI args (--target, --ip, --daemon).

## [5.1.0] — 2026-03-13

Fix H (ART device_config, MGLRU, SF device_config), compile-layouts, dex2oat priority,
ART verification. Źródło: analiza regresji Android 16 marzec 2026.

## [5.0.0] — 2026-03-13

WearOS-Style CLI, idempotentne operacje, Factory Reset (2-step), battery guard ART,
_countdown_reboot, _wait_for_reconnect spinner.

## [4.0.0] — 2026-03-13

Integracja raportu inżynieryjnego: PELT fix, SkiaGL, swappiness, WAKE_LOCK.
**[KOREKTA KRYTYCZNA]**: SF 1008 i32 1 = zalecane (nie odradzane) na W920.

## [3.0.0] — 2026-03-13

Pełna przebudowa, menu interaktywne, backup, Toybox-safe diagnostyka.

---

[6.0.0]: https://github.com/anonymousik/anonymousik.github.io/compare/v5.2.0...v6.0.0
[5.2.0]: https://github.com/anonymousik/anonymousik.github.io/compare/v5.1.0...v5.2.0
[5.1.0]: https://github.com/anonymousik/anonymousik.github.io/compare/v5.0.0...v5.1.0
[5.0.0]: https://github.com/anonymousik/anonymousik.github.io/compare/v4.0.0...v5.0.0
[4.0.0]: https://github.com/anonymousik/anonymousik.github.io/compare/v3.0.0...v4.0.0
[3.0.0]: https://github.com/anonymousik/anonymousik.github.io/releases/tag/v3.0.0
