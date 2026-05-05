# CHANGELOG
## Smart Compile Ultimate — SecFERRO Division

> Format zgodny z [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)  
> Wersjonowanie: [Semantic Versioning 2.0.0](https://semver.org/)  
> Projekt: `anonymousik.is-a.dev/scripts/scu`

---

## [3.0.0] — 2026-05-05 · FERRO IRONCLAD

> Wydanie naprawcze i modernizacyjne. Wszystkie znalezione błędy krytyczne,
> portabilnościowe i logiczne zostały rozwiązane. Wprowadzono pełny workflow
> YAML z jobs `validate → build → notify`, pre-flight system oraz cross-platform
> SHA-256. Każda zmiana jest oznaczona tagiem `[FIX-XX]` bezpośrednio w kodzie.

### Bezpieczeństwo

- **[FIX-03]** Usunięto `eval "${cmd[@]}"` z `_retry()` — zastąpione przez `"$@"`.
  Poprzednia implementacja umożliwiała wstrzyknięcie dowolnego polecenia przez
  kontrolowany argument oraz niszczyła quoting argumentów zawierających spacje.
- **[FIX-05]** Przepisano `_secret_scan()` — usunięto `xargs -I{} grep -rl`:
  przy pustym stdin `xargs` uruchamiał `grep` bez pliku (skanował stdin),
  flaga `-r` na konkretnym pliku była bezużyteczna. Zastąpiono bezpieczną pętlą
  `for f in "${staged_files[@]}"` z `grep -qlP`.
- Rozszerzono wzorce secret scannera o tokeny Slack (`xox*`), GitHub OAuth
  (`gho_`) oraz generyczne klucze `secret=`.

### Naprawione błędy

- **[FIX-01]** Dodano guard na Bash 4.0+ — `declare -A` (tablice asocjacyjne)
  wymaga bash ≥ 4. Na macOS domyślny bash to 3.2; skrypt kończył się
  niezdefiniowanym zachowaniem zamiast czytelnym komunikatem.
- **[FIX-02]** Przywrócono `set -Eeuo pipefail` z precyzyjnymi wyjątkami inline
  (`|| true`, `{ cmd; } 2>/dev/null`). W v2.0 był zakomentowany bez
  żadnego obejścia, co uniemożliwiało wykrycie błędów.
- **[FIX-04]** Naprawiono jitter w `_backoff_sleep()` — przy małych wartościach
  `exp` wyrażenie `RANDOM % (exp/5)` ewaluowało do `RANDOM % 0` (dzielenie
  przez zero / UB w bash). Dodano guard: `jrange = max(exp/5, 2)`.
- **[FIX-06]** Przepisano parser INI w `_load_conf()` — `IFS='=' read -r key val`
  przy wartościach zawierających `=` (np. URL z query string
  `https://host/path?a=1`) ucinał wszystko po pierwszym znaku `=`. Zastąpiono
  `key="${line%%=*}"` / `val="${line#*=}"`.
- **[FIX-07]** Usunięto zduplikowany `git rev-parse` check z `_load_conf()` —
  weryfikacja git repo jest teraz wyłącznie w `_preflight_git()`, wywoływanym
  raz z `main()`.
- **[FIX-08]** Naprawiono rotację logów — glob `("$LOG_DIR"/scu_*.log)` bez
  plików tworzył tablicę z dosłownym stringiem `"*.log"`. Zastąpiono
  `find ... -print0 | while IFS= read -r -d ''`.
- **[FIX-09]** Zastąpiono `(( var++ ))` przez `(( ++var ))` wszędzie gdzie
  zmienna mogła mieć wartość `0`. Z aktywnym `set -e`: wyrażenie `(( 0++ ))`
  ewaluuje do `0` (falsy) → exit code 1 → natychmiastowe zakończenie skryptu.
  Dotyczyło `found++` w `_secret_scan()` oraz `polls++` w `_monitor_execution()`.
- **[FIX-10]** Dodano cross-platform `_sha256sum()` — macOS nie posiada
  `sha256sum`. Nowy fallback chain: `sha256sum → shasum -a 256 → openssl dgst -sha256`.
- **[FIX-11]** Naprawiono scope SHA-256 w `_download_artifacts()` — pętla
  `while read` wewnątrz pipe tworzy subshell; użycie `local` oraz zapis do
  pliku przeniesiono poza pipe przy użyciu process substitution (`< <(...)`).
- **[FIX-12]** Naprawiono detekcję menadżera pakietów — `pkg` w systemach
  non-Termux może oznaczać narzędzie Go/npm, nie Termux pkg. Dodano
  `_IS_TERMUX` flag; `pkg install` uruchamiany wyłącznie gdy `_IS_TERMUX=true`.
  Fallback chain: `pkg → apt-get → apk → brew`.
- **[FIX-15]** Naprawiono event-time guard w `_wait_for_run()` — `dispatch_time`
  był zapisywany PO `sleep 8`, przez co szybko zainicjowany run mógł mieć
  `createdAt` starszy niż timestamp i zostać pominięty przez filtr jq.
  Timestamp pobierany jest teraz przed `sleep`.
- **[FIX-19]** Naprawiono `_cleanup()` — `local exit_code=$?` musi być absolutnie
  pierwszą instrukcją funkcji trap. Każde polecenie wcześniej (np. `echo`) nadpisuje `$?`.

### Nowe funkcje

- **[FIX-13]** Przepisano generator workflow YAML (`.github/workflows/`) na
  podstawie produkcyjnego template:
  - Job `validate` z `outputs` (variant, cache-key) — oddzielenie walidacji
    od kompilacji
  - `concurrency` group z `cancel-in-progress: true` — eliminacja nakładających
    się runów przy push
  - `android-actions/setup-android@v3.2.1` z SDK 34, build-tools 34.0.0,
    NDK 27.0.12077973
  - Input `clear-cache` (workflow_dispatch) — czyszczenie Gradle cache na żądanie
  - `gradle/actions/wrapper-validation@v3` — weryfikacja integralności wrappera
  - Upload build logs (`if: always()`) → artefakt `build-logs-{variant}`
  - GitHub Step Summary w Markdown (variant, Java, runner, status, tail logu)
  - Job `notify` z diagnostycznymi wskazówkami debugowania przy failure
- **[FIX-14]** Dodano `_resolve_artifact_name()` — inteligentne mapowanie
  `variant → nazwa artefaktu` pasująca do YAML (`{ARTIFACT_PREFIX}-{variant}`).
  Obsługuje placeholder `{variant}` w `ARTIFACT_NAMES` oraz tryb auto z prefiksem.
- **[FIX-16]** Dodano timeout guard na `gh run watch` — bez limitu czasowego
  komenda mogła zawiesić się na czas nieokreślony. Owinięto w
  `timeout $(( MAX_WAIT_MIN * 60 ))` z fallback manual polling co 30s i twardym
  cap `MAX_WAIT_MIN` (domyślnie 60).
- **[FIX-17]** Dodano `_preflight_env()` i `_preflight_git()`:
  - Weryfikacja wersji Bash (≥ 4.0)
  - Sprawdzenie wolnego miejsca na dysku (≥ 300 MB)
  - Test łączności z `api.github.com` przez `curl --head` (nie ICMP —
    Android blokuje ping bez `CAP_NET_RAW`)
  - Detekcja środowiska Termux przez `/proc/version`, `$TERMUX_VERSION`,
    `/data/data/com.termux`
- **[FIX-18]** Dodano guard w `_generate_report()` — JSON report generowany
  tylko gdy `jq` jest dostępne; TXT report zawsze.
- **[FIX-20]** Wszystkie wywołania `gh` i `curl` owinięte w `timeout $GH_TIMEOUT_S`
  (domyślnie 30s) — zapobiega zawieszeniu przy problemach sieciowych lub
  throttlingu API.
- **[FIX-21]** Nowe flagi CLI: `--clear-cache`, `--max-wait N`,
  `--timeout N`, `--artifact-prefix`, `-f / --force` (alias dla `--force`).
- Dodano `_DISPATCHED_VARIANTS[]` — tablica śledzenia wysłanych wariantów,
  używana do automatycznego rozwiązywania nazw artefaktów w download.
- Dodano deduplikację listy artefaktów przed pobraniem.
- Rozszerzono `_self_diagnose()` o wydruk token scopes z `gh auth status`.
- `_err_trap()` wypisuje numer linii i treść polecenia przy każdym błędzie ERR.

### Zmiany łamiące kompatybilność (Breaking Changes)

- Zmienna `ARTIFACT_NAMES` zmieniła semantykę — domyślnie jest pusta;
  nazwy artefaktów są teraz auto-generowane jako `{ARTIFACT_PREFIX}-{variant}`.
  Poprzednie konfiguracje z `ARTIFACT_NAMES=neurosync-wearos-apk` wymagają
  migracji na `ARTIFACT_PREFIX=neurosync-wearos` lub jawnego `--artifacts`.
- Usunięto `ARTIFACT_NAMES` z domyślnego `scu.conf` — zastąpiono przez
  `ARTIFACT_PREFIX`.
- `_load_conf()` nie wykonuje już `git rev-parse` — skrypty wrapperowe
  wywołujące `_load_conf` bezpośrednio muszą osobno zadbać o weryfikację repo.

### Wymagania systemowe

| Zależność | Minimalna wersja | Zmiana względem v2.0 |
|-----------|-----------------|----------------------|
| `bash`    | **4.0**         | ↑ Poprzednio brak guardu |
| `git`     | 2.30+           | bez zmian |
| `gh`      | 2.40+           | bez zmian |
| `curl`    | 7.68+           | bez zmian |
| `jq`      | 1.6+            | Opcjonalne (report fallback) |
| `timeout` | GNU coreutils   | ↑ Nowe wymaganie |

---

## [2.0.0] — 2026-05-05

> Pierwsza wersja produkcyjna z pełną architekturą CI/CD.
> Refaktoryzacja z monolitycznego skryptu do modularnego systemu z
> konfiguracją, lokowaniem i pełnym parserem CLI.

### Dodane

- Lock file z PID-guard (`~/.scu/locks/scu.lock`) — blokada współbieżnych instancji
- Exponential backoff z jitter ±10% przy retry
- Rate-limit detection (HTTP 403/429) z automatycznym 60s oczekiwaniem
- Secret leak scanner — staged files grep pod 7 wzorców (AWS, GitHub PAT, OpenAI, PEM)
- Walidacja `CUSTOM_INPUTS` przez `jq empty` przed dispatch
- Smart polling `run_id` z event-time guard (`createdAt >= dispatch_time`)
- Multi-artifact download (CSV lista nazw w `ARTIFACT_NAMES`)
- Build matrix dispatch — iteracja po `BUILD_VARIANTS` (CSV)
- SHA-256 checksum po każdym pobranym artefakcie
- Config file INI (`~/.scu/scu.conf`) z auto-generacją przy pierwszym uruchomieniu
- Summary report: JSON (`~/.scu/reports/*.json`) + TXT
- Dry-run mode (`--dry-run`) — pełna symulacja bez efektów ubocznych
- Pełny parser CLI (22 flagi, aliasy krótkie `-r/-w/-b` itd.)
- Rotacja logów (max 20 plików, starsze gzip)
- Obsługa Termux:API (`termux-toast`) jako natywne powiadomienie Android
- Suggestion `gh run cancel` przy SIGINT
- Wielopoziomowy logger TRACE/DEBUG/INFO/WARN/ERROR/FATAL

### Zmienione

- Generator workflow YAML: JDK 17 → JDK 21 (temurin), `actions/upload-artifact@v3` → `v4`
- `wait_for_run`: polling z `.[0]` → filtr po `createdAt`

### Naprawione

- Brak obsługi błędów przy `gh workflow run` (brak retry w v1.0)
- Brak cleanup przy przerwaniu skryptu (SIGINT bez trap)

---

## [1.0.0] — 2026-01-10

> Pierwsza publiczna wersja. Podstawowy pipeline GitHub Actions
> uruchamiany z Termux.

### Dodane

- Podstawowy dispatch `gh workflow run` z 1 wariantem
- Prosty retry (stały `sleep 6`, bez backoff)
- Pobieranie artefaktów przez `gh run download`
- Powiadomienia Slack webhook i e-mail (placeholder)
- `gh auth login` przy braku sesji
- Auto-tworzenie repo `gh repo create --private`
- Auto-commit i push przed dispatch
- Generator workflow YAML (JDK 17, `upload-artifact@v3`)
- Kolorowe logi (INFO/WARN/ERROR/SUCCESS)
- `--help`, `AUTO_YES`, `RETRIES` przez zmienne środowiskowe

---

*[FERRO//ANON] · SecFERRO Division · `anonymousik.is-a.dev/scripts/scu` · MIT License*