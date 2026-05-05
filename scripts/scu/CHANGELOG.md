## Changelog

| Wersja | Data | Zmiany |
|--------|------|--------|
| 3.0.0 | 2026-05-05 | ## SCU v3.0 — Rejestr wszystkich napraw

Każda zmiana jest znakowana `[FIX-XX]` w kodzie. Oto wyjaśnienie co i dlaczego:

---

### Błędy krytyczne (bezpieczeństwo / poprawność)

**[FIX-03] `eval` w `_retry()`** — najpoważniejszy bug. `eval "${cmd[@]}"` łączył tablicę w string i przekazywał do powłoki — word splitting niszczył argumenty ze spacjami, a każdy argument kontrolowany przez użytkownika mógł wstrzyknąć dowolne polecenie. Zamienione na `"$@"`.

**[FIX-05] `xargs -I{} grep -rl`** — `xargs` z pustą listą stdin wywołuje `grep` bez pliku (skanuje stdin zamiast nic), `-r` na konkretnym pliku nie ma sensu. Zamienione na jawną pętlę `for f in "${staged_files[@]}"` z `grep -qlP`.

**[FIX-09] `(( var++ ))` z `set -e`** — gdy zmienna wynosi `0`, wyrażenie `(( 0++ ))` ewaluuje do `0` (falsy), co przy aktywnym `set -e` natychmiast zabija skrypt. Dotyczyło `found++` w secret scanie i `polls++` w monitorze. Zamienione na `(( ++var ))` (pre-increment — zawsze zwraca nową wartość > 0).

**[FIX-02] `set -Eeuo pipefail` odkomentowane** — v2.0 miało je zakomentowane bez obejścia. v3.0 przywraca strict mode z precyzyjnymi wyjątkami (`|| true`, `{ cmd; } 2>/dev/null`).

---

### Błędy logiczne / race conditions

**[FIX-15] `dispatch_time` przed `sleep 8`** — v2.0 zapisywał czas PO sleep, więc event-time guard mógł pominąć bardzo szybko zainicjowany run. Teraz timestamp jest pobierany przed sleep.

**[FIX-07] Zduplikowany git check** — `_load_conf` i `main` obie sprawdzały `git rev-parse`. Wydzielone do `_preflight_git()`, wywołane raz po załadowaniu configa.

**[FIX-19] `exit_code=$?` w `_cleanup`** — musi być absolutnie pierwszą instrukcją funkcji. Każde polecenie przed nią nadpisuje `$?`.

---

### Błędy portabilności

**[FIX-10] `sha256sum` cross-platform** — macOS nie ma `sha256sum`, ma `shasum -a 256`. Dodano `_sha256sum()` z fallbackiem: `sha256sum → shasum → openssl dgst`.

**[FIX-12] `pkg` przed `apt-get`** — w non-Termux środowiskach `pkg` to narzędzie do zarządzania pakietami Go/npm, nie Termux. Dodano Termux detection (`_IS_TERMUX`) — `pkg` uruchamiany tylko gdy `_IS_TERMUX=true`.

**[FIX-01] Bash 4.0+ guard** — `declare -A` (tablice asocjacyjne) wymaga bash >= 4. Na macOS domyślny bash to 3.2. Skrypt teraz kończy się z komunikatem zanim dojdzie do undefined behavior.

---

### Błędy parsowania / konfiguracji

**[FIX-06] INI parser** — `IFS='=' read -r key val` przy wartości `WEBHOOK_URL=https://a.com/path?x=1` ucinałby wszystko po pierwszym `=`. Zamienione na `key="${line%%=*}"` / `val="${line#*=}"` — poprawnie obsługuje `=` w wartości.

**[FIX-08] Log rotation glob** — `logs=("$LOG_DIR"/scu_*.log)` gdy brak plików tworzy tablicę z dosłownym stringiem `*.log`. Zamienione na `find ... -print0 | while read -r -d ''`.

---

### Nowe funkcjonalności wymuszone przez doc-3

**[FIX-13] Workflow YAML** — generator przepisany by używać pełnego template z doc-3: job `validate` z outputs, `concurrency` group, `setup-android@v3.2.1`, NDK 27, `clear-cache` input, upload build logs (`if: always()`), GitHub Step Summary w Markdown.

**[FIX-14] Variant → artifact name mapping** — `_resolve_artifact_name()` mapuje `debug → neurosync-apk-debug`, `release → neurosync-apk-release` (pasuje do YAML `name: ${ARTIFACT_PREFIX}-${{ variant }}`). Możliwy override przez `--artifacts "myapp-{variant}"`.

**[FIX-16] Timeout guard** — `gh run watch` bez timeout może wisieć w nieskończoność. Owinięte w `timeout $(( MAX_WAIT_MIN * 60 ))` z fallback manual polling i twardym cap.

**[FIX-17] Pre-flight** — disk space (`df -m`), network (`curl --head api.github.com`, nie ping — Android blokuje ICMP), bash version check.
| 2.0.0 | 2026-05-05 | Lock file, backoff retry, secret scan, build matrix, multi-artifact, SHA-256, config INI, event-time guard, Termux:API, dry-run, summary report, pełny parser CLI |
| 1.0.0 | 2026-01-10 | Pierwsza wersja publiczna |