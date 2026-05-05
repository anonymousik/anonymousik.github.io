# SMART COMPILE ULTIMATE v2.0
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
| 2.0.0 | 2026-05-05 | Lock file, backoff retry, secret scan, build matrix, multi-artifact, SHA-256, config INI, event-time guard, Termux:API, dry-run, summary report, pełny parser CLI |
| 1.0.0 | 2026-01-10 | Pierwsza wersja publiczna |

---

## Licencja i autorstwo

```
SMART COMPILE ULTIMATE v2.0
© 2026 anonymousik / FerroART · SecFERRO Division
https://anonymousik.is-a.dev

Projekt open-source na licencji MIT.
Dozwolone użycie komercyjne z zachowaniem nagłówka autorstwa.
```

---

*[FERRO//ANON] · SecFERRO Division · `◈`* 