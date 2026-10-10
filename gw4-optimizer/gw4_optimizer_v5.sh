#!/usr/bin/env bash
# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║  GW4 Pro Optimizer Suite  v5.0.0                                            ║
# ║  Samsung SM-R870/SM-R875/SM-R895 · Exynos W920 · One UI 8.0 / Android 16   ║
# ║                                                                              ║
# ║  One-Click-Install:                                                          ║
# ║  bash <(curl -sL https://raw.githubusercontent.com/anonymousik/             ║
# ║    anonymousik.github.io/refs/heads/main/scripts/gw4-optimizer/             ║
# ║    gw4_optimizer_v5.sh)                                                      ║
# ║                                                                              ║
# ║  Changelog: v5 → Idempotentne operacje, _countdown_reboot, Factory Reset,   ║
# ║             _wait_for_reconnect, battery guard ART, WearOS-Style CLI UX     ║
# ║  SPDX-License-Identifier: MIT                                               ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

set -euo pipefail

# ───────────────────────────────────────────────────────────────────────────────
# §0  STAŁE — Exynos W920 / WearOS 6.0 / Android 16  (zweryfikowane empirycznie)
# ───────────────────────────────────────────────────────────────────────────────

readonly VERSION="5.0.0"
readonly SCRIPT_NAME="GW4 Pro Optimizer Suite"
readonly RAW_BASE="https://raw.githubusercontent.com/anonymousik/anonymousik.github.io/refs/heads/main/scripts/gw4-optimizer"
readonly DEFAULT_PORT="5555"
readonly ADB_RETRY=4
readonly ADB_TIMEOUT=12
readonly ADB_WAKE_RETRY=3
readonly ART_BATTERY_MIN=20          # Fix G blokowany poniżej tej wartości [%]
readonly RECONNECT_TIMEOUT=120       # Max oczekiwanie po restarcie [s]

# Exynos W920 — parametry sprzętowe
readonly W920_CPU_CORES=2
readonly W920_CPU_ARCH="Cortex-A55"
readonly W920_GPU="Mali-G68"
readonly W920_RAM_MB=1500

# schedutil — wartości optymalne dla 2-core A55 (Android 16 PELT miscalibration)
readonly SCHED_UP_DEFAULT=500    SCHED_UP_OPT=1000
readonly SCHED_DOWN_DEFAULT=20000  SCHED_DOWN_OPT=10000
readonly SCHED_LAT_DEFAULT=10000000  SCHED_LAT_OPT=8000000

# vm — redukuje freeze przy dekompresji zRAM na 2-core A55
readonly VM_SWAP_DEFAULT=100  VM_SWAP_OPT=60
readonly VM_EXTRA_FREE_KB=65536

# ART
readonly ART_HEAPTARGET=0.75
readonly ART_HEAPMAXFREE="8m"

# Ścieżki
readonly LOG_DIR="${HOME}/.gw4_optimizer"
readonly LOG_FILE="${LOG_DIR}/session_$(date +%Y%m%d_%H%M%S).log"
readonly BACKUP_FILE="${LOG_DIR}/backup_$(date +%Y%m%d_%H%M%S).txt"

# ───────────────────────────────────────────────────────────────────────────────
# §1  KOLORY / ANSI — WearOS-Style CLI
#     Hierarchia: CYAN=nawigacja, GREEN=sukces, YELLOW=ostrzeżenie, RED=błąd
# ───────────────────────────────────────────────────────────────────────────────

if [[ -t 1 ]] && tput colors &>/dev/null && [[ $(tput colors) -ge 8 ]]; then
    C0='\033[0m'      BOLD='\033[1m'    DIM='\033[2m'    UL='\033[4m'
    BLINK='\033[5m'   REV='\033[7m'
    GREEN='\033[32m'  LGREEN='\033[92m'
    RED='\033[31m'    LRED='\033[91m'
    YELLOW='\033[33m' LYELLOW='\033[93m'
    CYAN='\033[36m'   LCYAN='\033[96m'
    MAG='\033[35m'    WHITE='\033[97m'  GRAY='\033[90m'
else
    C0='' BOLD='' DIM='' UL='' BLINK='' REV=''
    GREEN='' LGREEN='' RED='' LRED='' YELLOW='' LYELLOW=''
    CYAN='' LCYAN='' MAG='' WHITE='' GRAY=''
fi

# Symbole (fallback ASCII gdy brak UTF-8)
if printf '\xe2\x94\x80' 2>/dev/null | grep -q $'\xe2'; then
    SYM_OK="✓" SYM_ERR="✗" SYM_WARN="⚠" SYM_ARR="→" SYM_FIX="⚙"
    SYM_SKIP="↷" SYM_KEY="⚡" SYM_LOCK="🔒"
else
    SYM_OK="OK" SYM_ERR="!!" SYM_WARN="!>" SYM_ARR="->" SYM_FIX="##"
    SYM_SKIP=">>" SYM_KEY="**" SYM_LOCK="[L]"
fi

# ───────────────────────────────────────────────────────────────────────────────
# §2  LOGGER
# ───────────────────────────────────────────────────────────────────────────────

_ts()    { date +"%H:%M:%S"; }
_log()   { echo "$(_ts) [$1] $2" >> "${LOG_FILE}"; }
ok()     { printf "${LGREEN}  ${SYM_OK}  ${C0}${BOLD}%s${C0}\n" "$*"; _log "OK   " "$*"; }
err()    { printf "${LRED}  ${SYM_ERR}  ${C0}${BOLD}%s${C0}\n" "$*" >&2; _log "ERROR" "$*"; }
warn()   { printf "${YELLOW}  ${SYM_WARN}  ${C0}%s\n" "$*"; _log "WARN " "$*"; }
info()   { printf "${CYAN}  ${SYM_ARR}  ${C0}%s\n" "$*"; _log "INFO " "$*"; }
fix()    { printf "${MAG}  ${SYM_FIX}  ${C0}%s\n" "$*"; _log "FIX  " "$*"; }
skip()   { printf "${GRAY}  ${SYM_SKIP}  skipped: %s${C0}\n" "$*"; _log "SKIP " "$*"; }
sub()    { printf "${GRAY}     %s${C0}\n" "$*"; }
hdr()    { printf "\n${CYAN}${BOLD}  ╔══ %s ══╗${C0}\n" "$*"; }
fatal()  { err "FATAL: $*"; exit 1; }

# Pasek postępu — używa \r (bez scroll)
_bar() {
    local label="$1" pct="$2"
    local filled=$(( pct * 30 / 100 ))
    local bar="" i
    for ((i=0;i<30;i++)); do
        [[ $i -lt $filled ]] && bar+="${GREEN}█${C0}" || bar+="${GRAY}░${C0}"
    done
    printf "\r  ${CYAN}%-28s${C0} [%b] ${WHITE}%3d%%${C0}" "${label}" "${bar}" "${pct}"
}

# Status inline — jedna linia, nadpisywana \r
_status() { printf "\r  ${CYAN}%-60s${C0}" "$*"; }

# ───────────────────────────────────────────────────────────────────────────────
# §3  INIT
# ───────────────────────────────────────────────────────────────────────────────

DEVICE=""
DEVICE_MODEL=""
DEVICE_FW=""
DEVICE_SDK="0"
DEVICE_BATTERY="-1"
BACKUP_DONE=false

_init() {
    mkdir -p "${LOG_DIR}"
    _log "START" "${SCRIPT_NAME} v${VERSION} | $(date)"
    command -v adb &>/dev/null || \
        fatal "adb nie znaleziono w PATH. Zainstaluj Android Platform Tools."
}

# ───────────────────────────────────────────────────────────────────────────────
# §4  ADB — połączenie, retry, auto-wake
# ───────────────────────────────────────────────────────────────────────────────

_adb()      { timeout "${ADB_TIMEOUT}" adb -s "${DEVICE}" "$@" 2>/dev/null; }
_sh()       { _adb shell "$@" 2>/dev/null | tr -d '\r'; }

_sh_retry() {
    local cmd="$*" attempt result
    for ((attempt=1; attempt<=ADB_WAKE_RETRY; attempt++)); do
        result="$(timeout "${ADB_TIMEOUT}" adb -s "${DEVICE}" shell "${cmd}" \
                    2>/dev/null | tr -d '\r')" \
            && { printf '%s' "${result}"; return 0; }
        [[ $attempt -lt $ADB_WAKE_RETRY ]] && {
            _status "Zegarek nie odpowiada (${attempt}/${ADB_WAKE_RETRY}) — wybudzam..."
            sleep 2
            adb -s "${DEVICE}" shell input keyevent KEYCODE_WAKEUP 2>/dev/null || true
            sleep 1
        }
    done
    return 1
}

# _apply_if_changed LABEL CURRENT DESIRED CMD...
# Wykonuje CMD tylko jeśli CURRENT != DESIRED. Idempotentna operacja.
_apply_if_changed() {
    local label="$1" current="$2" desired="$3"; shift 3
    if [[ "${current}" == "${desired}" ]]; then
        skip "${label} (już: ${desired})"
        return 0
    fi
    if _sh_retry "$@" &>/dev/null; then
        fix "${label}: ${current} → ${desired}"
    else
        warn "${label} — błąd (brak uprawnień lub nieobsługiwane)"
    fi
}

# _apply LABEL CMD... — bez weryfikacji stanu (dla operacji bez stanu)
_apply() {
    local label="$1"; shift
    if _sh_retry "$@" &>/dev/null; then
        fix "${label}"
    else
        warn "${label} — błąd (brak uprawnień lub nieobsługiwane)"
    fi
}

# Odczyt ustawienia ADB
_get_setting() { _sh_retry "settings get $1 $2" 2>/dev/null || echo 'null'; }
_get_prop()    { _sh_retry "getprop $1" 2>/dev/null || echo ''; }
_get_kernel()  { _sh "cat $1" 2>/dev/null || echo 'N/A'; }

_adb_connect() {
    local target="$1"
    info "Łączenie z ${target}..."
    adb disconnect &>/dev/null || true
    sleep 0.5

    local attempt state
    for ((attempt=1; attempt<=ADB_RETRY; attempt++)); do
        adb connect "${target}" &>/dev/null || true
        sleep 1.5
        state="$(adb -s "${target}" get-state 2>/dev/null || echo 'offline')"
        case "${state}" in
            device)
                DEVICE="${target}"
                ok "Połączono: ${target}"
                return 0 ;;
            unauthorized)
                err "Urządzenie NIEAUTORYZOWANE"
                sub "Szukaj dialogu 'Czy zezwolić na debugowanie?' na ekranie zegarka"
                return 1 ;;
            offline)
                [[ $attempt -lt $ADB_RETRY ]] && {
                    _status "Offline — próba ${attempt}/${ADB_RETRY}..."
                    adb -s "${target}" shell input keyevent KEYCODE_WAKEUP 2>/dev/null || true
                    sleep 2
                } ;;
        esac
    done
    err "Brak połączenia z ${target} po ${ADB_RETRY} próbach"
    sub "Sprawdź: ta sama sieć Wi-Fi | ADB debugging włączone | zegarek aktywny"
    return 1
}

# ───────────────────────────────────────────────────────────────────────────────
# §5  WYKRYWANIE URZĄDZENIA + ODCZYT PARAMETRÓW
# ───────────────────────────────────────────────────────────────────────────────

_detect_device() {
    hdr "Wykrywanie urządzenia"

    local detected
    detected="$(adb devices 2>/dev/null \
        | awk 'NR>1 && $2=="device" && $1~/^[0-9]/{print $1}' | head -1)"

    if [[ -n "${detected}" ]]; then
        DEVICE="${detected}"
        info "Auto-wykryto: ${detected}"
    else
        printf "\n${CYAN}${BOLD}  Podaj IP zegarka${C0} ${GRAY}(format: 192.168.1.X lub IP:5555)${C0}\n"
        read -r -p "  > " _ip
        [[ "${_ip}" != *:* ]] && _ip="${_ip}:${DEFAULT_PORT}"
        _adb_connect "${_ip}" || return 1
    fi

    # Odczyt parametrów urządzenia
    DEVICE_MODEL="$(_sh_retry "getprop ro.product.model"   || echo '?')"
    DEVICE_FW="$(   _sh_retry "getprop ro.build.display.id"|| echo '?')"
    DEVICE_SDK="$(  _sh_retry "getprop ro.build.version.sdk"|| echo '0')"
    local av; av="$(_sh_retry "getprop ro.build.version.release" || echo '?')"
    DEVICE_BATTERY="$(_sh "dumpsys battery 2>/dev/null | grep -m1 level | awk '{print \$2}'" \
                     2>/dev/null || echo '-1')"
    DEVICE_BATTERY="${DEVICE_BATTERY//[^0-9]/}"
    [[ -z "${DEVICE_BATTERY}" ]] && DEVICE_BATTERY="-1"

    # Wyświetlenie tabeli parametrów
    printf "\n"
    printf "  ${GRAY}┌─────────────────────────────────────────────────────┐${C0}\n"
    printf "  ${GRAY}│${C0}  ${WHITE}%-20s${C0}  %-28s  ${GRAY}│${C0}\n" "Model:"    "${DEVICE_MODEL}"
    printf "  ${GRAY}│${C0}  ${WHITE}%-20s${C0}  %-28s  ${GRAY}│${C0}\n" "Firmware:" "${DEVICE_FW}"
    printf "  ${GRAY}│${C0}  ${WHITE}%-20s${C0}  Android %-3s (SDK %-3s)        ${GRAY}│${C0}\n" \
           "System:" "${av}" "${DEVICE_SDK}"
    local bat_color="${GREEN}"
    [[ "${DEVICE_BATTERY:-0}" -lt 20 ]] && bat_color="${RED}"
    [[ "${DEVICE_BATTERY:-0}" -lt 50 && "${DEVICE_BATTERY:-0}" -ge 20 ]] && bat_color="${YELLOW}"
    printf "  ${GRAY}│${C0}  ${WHITE}%-20s${C0}  ${bat_color}%d%%${C0}%-26s  ${GRAY}│${C0}\n" \
           "Bateria:" "${DEVICE_BATTERY:-?}" ""
    printf "  ${GRAY}└─────────────────────────────────────────────────────┘${C0}\n\n"

    # Weryfikacja modelu
    if [[ "${DEVICE_MODEL:-}" =~ ^SM-R8 ]]; then
        ok "Galaxy Watch 4 rozpoznany: ${DEVICE_MODEL}"
    else
        warn "Nierozpoznany model: ${DEVICE_MODEL:-?}"
        warn "Skrypt zoptymalizowany dla SM-R870/R875/R895"
        read -r -p "  Kontynuować mimo to? [t/N] " _c
        [[ "${_c,,}" != "t" ]] && { info "Anulowano."; exit 0; }
    fi
}

# ───────────────────────────────────────────────────────────────────────────────
# §6  BACKUP
# ───────────────────────────────────────────────────────────────────────────────

_backup_settings() {
    [[ "${BACKUP_DONE}" == "true" ]] && return 0
    info "Tworzę backup bieżących ustawień..."

    {
        echo "# ${SCRIPT_NAME} v${VERSION} — backup $(date)"
        echo "# Model: ${DEVICE_MODEL} | FW: ${DEVICE_FW} | SDK: ${DEVICE_SDK}"
        echo ""
        for key in \
            "global window_animation_scale" \
            "global transition_animation_scale" \
            "global animator_duration_scale" \
            "secure doze_always_on" "secure doze_enabled" \
            "global monitor_phantom_procs" "global high_priority_render_thread" \
            "global background_process_limit" "global supports_background_blur" \
            "system screen_brightness_mode"; do
            local ns="${key%% *}" k="${key##* }"
            echo "SETTINGS:${ns}:${k}=$(_get_setting "${ns}" "${k}")"
        done
        for prop in \
            "debug.hwui.renderer" "debug.hwui.profile" \
            "debug.hwui.skip_empty_damage" "debug.hwui.use_buffer_age" \
            "ro.surface_flinger.supports_background_blur"; do
            echo "PROP:${prop}=$(_get_prop "${prop}")"
        done
        for kpath in \
            "/sys/devices/system/cpu/cpufreq/policy0/schedutil/up_rate_limit_us" \
            "/sys/devices/system/cpu/cpufreq/policy0/schedutil/down_rate_limit_us" \
            "/proc/sys/vm/swappiness" "/proc/sys/kernel/sched_latency_ns"; do
            echo "KERNEL:${kpath}=$(_get_kernel "${kpath}")"
        done
    } > "${BACKUP_FILE}"

    BACKUP_DONE=true
    ok "Backup: ${BACKUP_FILE}"
}

# ───────────────────────────────────────────────────────────────────────────────
# §7  GUARD: SPRAWDZENIE BATERII
#     Używane przez Fix G — blokuje kompilację ART gdy bateria < ART_BATTERY_MIN
# ───────────────────────────────────────────────────────────────────────────────

_check_battery() {
    # Odświeżenie stanu baterii
    local lvl
    lvl="$(_sh "dumpsys battery 2>/dev/null | grep -m1 level | awk '{print \$2}'" \
               2>/dev/null || echo '-1')"
    lvl="${lvl//[^0-9]/}"
    [[ -z "${lvl}" ]] && lvl="-1"
    DEVICE_BATTERY="${lvl}"

    if [[ "${lvl}" -lt "${ART_BATTERY_MIN}" ]] 2>/dev/null; then
        printf "\n"
        printf "  ${RED}${BOLD}  ┌────────────────────────────────────────────────┐${C0}\n"
        printf "  ${RED}${BOLD}  │  ⚠  BATERIA ZBYT NISKA — %3d%%  (min: %d%%)      │${C0}\n" \
               "${lvl}" "${ART_BATTERY_MIN}"
        printf "  ${RED}${BOLD}  │  Kompilacja ART wymaga min. %d%% naładowania.    │${C0}\n" \
               "${ART_BATTERY_MIN}"
        printf "  ${RED}${BOLD}  │  Naładuj zegarek i spróbuj ponownie.           │${C0}\n"
        printf "  ${RED}${BOLD}  └────────────────────────────────────────────────┘${C0}\n\n"
        return 1
    fi
    return 0
}

# ───────────────────────────────────────────────────────────────────────────────
# §8  ANIMACJE TERMINALA
#     _spinner PID TEXT   — obraca spinner dopóki PID żyje
#     _countdown_reboot   — 60s odliczanie z pulsowaniem, przerywa dowolny klawisz
#     _wait_for_reconnect — czeka na ponowne połączenie ADB po restarcie
# ───────────────────────────────────────────────────────────────────────────────

_spinner() {
    local pid="$1" text="${2:-Proszę czekać...}"
    local frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
    local colors=("${CYAN}" "${LCYAN}" "${GREEN}" "${LGREEN}" "${CYAN}")
    local i=0 ci=0
    while kill -0 "${pid}" 2>/dev/null; do
        ci=$(( i % ${#colors[@]} ))
        printf "\r  ${colors[$ci]}%s${C0}  ${WHITE}%s${C0}  " \
               "${frames[$(( i % ${#frames[@]} ))]}" "${text}"
        sleep 0.12
        (( i++ )) || true
    done
    printf "\r  %-70s\r" " "   # wyczyść linię
}

_countdown_reboot() {
    local secs="${1:-60}"
    local msg="${2:-Restart za}"
    printf "\n"
    printf "  ${YELLOW}${BOLD}  ┌──────────────────────────────────────────────────────┐${C0}\n"
    printf "  ${YELLOW}${BOLD}  │  Naciśnij DOWOLNY KLAWISZ, aby anulować odliczanie  │${C0}\n"
    printf "  ${YELLOW}${BOLD}  └──────────────────────────────────────────────────────┘${C0}\n\n"

    local i="${secs}" aborted=false key
    while [[ ${i} -gt 0 ]]; do
        # Pulsowanie: naprzemiennie YELLOW i CYAN
        local col="${YELLOW}"
        (( i % 2 == 0 )) && col="${LCYAN}"
        [[ ${i} -le 10 ]] && col="${LRED}"

        _bar "${msg} ${i}s" $(( (secs - i) * 100 / secs ))
        printf "  "

        # Nieblokujące czytanie klawisza (read -t 1 -n 1 zgodnie z POSIX bash)
        if read -t 1 -n 1 key 2>/dev/null; then
            aborted=true
            break
        fi
        (( i-- )) || true
    done

    printf "\n"
    if [[ "${aborted}" == "true" ]]; then
        warn "Odliczanie przerwane przez użytkownika"
        return 1
    fi
    ok "Odliczanie zakończone"
    return 0
}

_wait_for_reconnect() {
    local target="${DEVICE}" timeout_s="${RECONNECT_TIMEOUT}"
    printf "\n"
    info "Oczekuję na ponowne połączenie ADB z ${target}..."
    info "Zegarek restartuje się. To może potrwać do ${timeout_s}s."
    printf "\n"

    local elapsed=0 state frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
    local fi=0
    while [[ ${elapsed} -lt ${timeout_s} ]]; do
        state="$(adb -s "${target}" get-state 2>/dev/null || echo 'offline')"
        if [[ "${state}" == "device" ]]; then
            printf "\r  %-70s\n" " "
            ok "Urządzenie ponownie połączone (${elapsed}s)"
            # Odśwież parametry
            DEVICE_BATTERY="$(_sh "dumpsys battery 2>/dev/null | grep -m1 level | awk '{print \$2}'" \
                             2>/dev/null || echo '-1')"
            DEVICE_BATTERY="${DEVICE_BATTERY//[^0-9]/}"
            return 0
        fi

        printf "\r  ${CYAN}%s${C0}  Oczekiwanie na ADB  ${GRAY}[%ds / %ds]${C0}  " \
               "${frames[$(( fi % ${#frames[@]} ))]}" "${elapsed}" "${timeout_s}"
        sleep 1
        (( elapsed++ )) || true
        (( fi++ ))      || true

        # Co 10s próbuj reconnect
        (( elapsed % 10 == 0 )) && {
            adb connect "${target}" &>/dev/null || true
        }
    done

    printf "\n"
    err "Timeout — zegarek nie powrócił w ciągu ${timeout_s}s"
    sub "Sprawdź czy zegarek uruchomił się poprawnie"
    sub "Następnie uruchom skrypt ponownie: bash gw4_optimizer_v5.sh"
    return 1
}

# ───────────────────────────────────────────────────────────────────────────────
# §9  FIX A — ANIMACJE
#     Idempotentne: odczytuje bieżącą wartość, zmienia tylko jeśli konieczne
# ───────────────────────────────────────────────────────────────────────────────

_fix_animations() {
    hdr "Fix A: Animacje interfejsu"
    _backup_settings

    # Odczyt stanu bieżącego
    local cur_wa cur_ta cur_da
    cur_wa="$(_get_setting global window_animation_scale)"
    cur_ta="$(_get_setting global transition_animation_scale)"
    cur_da="$(_get_setting global animator_duration_scale)"

    printf "\n  ${GRAY}Bieżące wartości:${C0}\n"
    printf "  ${WHITE}%-38s${C0} %s\n" "window_animation_scale:"     "${cur_wa}"
    printf "  ${WHITE}%-38s${C0} %s\n" "transition_animation_scale:" "${cur_ta}"
    printf "  ${WHITE}%-38s${C0} %s\n" "animator_duration_scale:"    "${cur_da}"
    printf "\n"
    printf "  ${CYAN}1${C0}) Turbo  ${GREEN}0.5x${C0}  ${GRAY}— widoczne animacje, wyraźnie szybsze${C0}\n"
    printf "  ${CYAN}2${C0}) Off    ${GREEN}0.0x${C0}  ${GRAY}— brak animacji, maksymalna szybkość${C0}\n"
    printf "  ${CYAN}3${C0}) Reset  ${YELLOW}1.0x${C0}  ${GRAY}— OEM default One UI 8.0${C0}\n"
    printf "  ${CYAN}0${C0}) Anuluj\n\n"
    read -r -p "  > " _c

    local scale
    case "${_c}" in
        1) scale="0.5" ;; 2) scale="0.0" ;; 3) scale="1.0" ;; 0) return ;;
        *) warn "Nieznana opcja"; return ;;
    esac

    _apply_if_changed "window_animation_scale"     "${cur_wa}" "${scale}" \
        "settings put global window_animation_scale ${scale}"
    _apply_if_changed "transition_animation_scale" "${cur_ta}" "${scale}" \
        "settings put global transition_animation_scale ${scale}"
    _apply_if_changed "animator_duration_scale"    "${cur_da}" "${scale}" \
        "settings put global animator_duration_scale ${scale}"
    ok "Animacje → ${scale}x (efekt natychmiastowy)"
}

# ───────────────────────────────────────────────────────────────────────────────
# §10  FIX B — AOD / GPU VOLTAGE RAMP BUG
#      Sterownik Mali-G68 nie podbija napięcia GPU wystarczająco szybko
#      przy przejściu AOD (1Hz) → active (60Hz) → lag 1-2s po wybudzeniu
# ───────────────────────────────────────────────────────────────────────────────

_fix_aod() {
    hdr "Fix B: AOD — błąd GPU voltage ramp (Mali-G68)"

    local cur_aod cur_doze
    cur_aod="$( _get_setting secure doze_always_on)"
    cur_doze="$(_get_setting secure doze_enabled)"

    printf "\n"
    printf "  ${GRAY}┌──────────────────────────────────────────────────┐${C0}\n"
    printf "  ${GRAY}│${C0}  ${WHITE}doze_always_on:${C0}  %-3s  ${GRAY}(1=AOD włączone)         │${C0}\n" \
           "${cur_aod}"
    printf "  ${GRAY}│${C0}  ${WHITE}doze_enabled:  ${C0}  %-3s  ${GRAY}(1=ambient display)      │${C0}\n" \
           "${cur_doze}"
    printf "  ${GRAY}│${C0}                                                    ${GRAY}│${C0}\n"
    printf "  ${GRAY}│${C0}  ${YELLOW}Bug: GPU voltage ramp zbyt wolny 1Hz→60Hz${C0}       ${GRAY}│${C0}\n"
    printf "  ${GRAY}│${C0}  ${YELLOW}Samsung nie wydał patcha sterownika (03/2026)${C0}   ${GRAY}│${C0}\n"
    printf "  ${GRAY}└──────────────────────────────────────────────────┘${C0}\n\n"

    printf "  ${CYAN}1${C0}) ${GREEN}Wyłącz AOD${C0}     ${GRAY}— eliminuje problem (zalecane)${C0}\n"
    printf "  ${CYAN}2${C0}) Włącz AOD      ${GRAY}— przywróć (bug pozostanie)${C0}\n"
    printf "  ${CYAN}3${C0}) Low-Power AOD  ${GRAY}— ograniczone odświeżanie, mniejszy narzut${C0}\n"
    printf "  ${CYAN}0${C0}) Anuluj\n\n"
    read -r -p "  > " _c

    case "${_c}" in
        1)
            _backup_settings
            _apply_if_changed "doze_always_on" "${cur_aod}"  "0" \
                "settings put secure doze_always_on 0"
            _apply_if_changed "doze_enabled"   "${cur_doze}" "0" \
                "settings put secure doze_enabled 0"
            ok "AOD wyłączone — lag wybudzenia znika"
            warn "Tymczasowe — oczekuj patcha sterownika od Samsunga" ;;
        2)
            _apply_if_changed "doze_always_on" "${cur_aod}"  "1" \
                "settings put secure doze_always_on 1"
            _apply_if_changed "doze_enabled"   "${cur_doze}" "1" \
                "settings put secure doze_enabled 1"
            ok "AOD włączone" ;;
        3)
            _backup_settings
            _apply "AOD on low-power" "settings put secure doze_always_on 1"
            _apply "AOD refresh rate" "setprop persist.sys.sf.aod_refresh_rate 1"
            _apply "Brightness fixed" "settings put system screen_brightness_mode 0"
            ok "Low-Power AOD aktywny"
            sub "Jeśli lag pozostaje → użyj opcji 1" ;;
        0) return ;;
        *) warn "Nieznana opcja" ;;
    esac
}

# ───────────────────────────────────────────────────────────────────────────────
# §11  FIX C — SURFACEFLINGER / HWUI / BACKGROUND BLUR
#      HWC driver bug w Mali-G68 → Force GPU jest ZALECANYM rozwiązaniem
#      Vulkan na Android 16 → wycieki pamięci → wymuś SkiaGL
# ───────────────────────────────────────────────────────────────────────────────

_fix_surfaceflinger() {
    hdr "Fix C: SurfaceFlinger / HWUI / Background Blur"
    _backup_settings

    local cur_renderer cur_blur
    cur_renderer="$(_get_prop debug.hwui.renderer)"
    cur_blur="$(    _get_setting global supports_background_blur)"

    printf "\n"
    printf "  ${GRAY}Bieżące:  renderer=${cur_renderer:-auto}  blur=${cur_blur}${C0}\n\n"

    printf "  ${CYAN}1${C0}) ${GREEN}Pełny fix renderowania${C0} ${GRAY}(SF+HWUI+Blur) — optymalny pakiet${C0}\n"
    printf "     ${GRAY}├─ SF Force GPU (HWC bug fix / flickering)${C0}\n"
    printf "     ${GRAY}├─ HWUI renderer → skiagl (Vulkan memory leaks)${C0}\n"
    printf "     ${GRAY}└─ Background Blur off (nieproporcjonalny koszt)${C0}\n"
    printf "  ${CYAN}2${C0}) Force GPU (SF 1008)   ${GRAY}— naprawia HWC bug / flickering${C0}\n"
    printf "  ${CYAN}3${C0}) HWUI → SkiaGL         ${GRAY}— stabilniejszy niż Vulkan na W920${C0}\n"
    printf "  ${CYAN}4${C0}) Wyłącz Background Blur${GRAY}— odciąża Mali-G68 GPU${C0}\n"
    printf "  ${CYAN}5${C0}) Przywróć HWC          ${GRAY}— cofnij Force GPU${C0}\n"
    printf "  ${CYAN}0${C0}) Anuluj\n\n"
    read -r -p "  > " _c

    case "${_c}" in
        1)
            _bar "SF Force GPU" 15
            _sh "service call SurfaceFlinger 1008 i32 1" || true
            printf "\n"; fix "SurfaceFlinger 1008 → Force GPU (HWC bug fix)"

            _bar "SkiaGL renderer" 35
            _apply_if_changed "hwui.renderer" "${cur_renderer:-}" "skiagl" \
                "setprop debug.hwui.renderer skiagl"
            printf "\n"

            _bar "HWUI flags" 55
            _apply "hwui.skip_empty_damage=true" "setprop debug.hwui.skip_empty_damage true"
            _apply "hwui.use_buffer_age=true"    "setprop debug.hwui.use_buffer_age true"
            _apply "hwui.profile=false"          "setprop debug.hwui.profile false"
            _apply "hwui.overdraw=false"         "setprop debug.hwui.overdraw false"
            printf "\n"

            _bar "Blur off" 75
            _apply_if_changed "supports_background_blur" "${cur_blur}" "0" \
                "settings put global supports_background_blur 0"
            _apply "sf.supports_blur=0" \
                "setprop ro.surface_flinger.supports_background_blur 0"
            printf "\n"

            _bar "High-prio render" 90
            _apply "high_priority_render_thread=1" \
                "settings put global high_priority_render_thread 1"
            printf "\n"

            _bar "Gotowe" 100; printf "\n"
            ok "Pełny fix SF/HWUI zastosowany"
            sub "Zalecany restart (efekty renderowania widoczne po restarcie)" ;;
        2)
            _sh "service call SurfaceFlinger 1008 i32 1" || true
            ok "Force GPU włączone — HWC bug omijany" ;;
        3)
            _apply_if_changed "hwui.renderer" "${cur_renderer:-}" "skiagl" \
                "setprop debug.hwui.renderer skiagl"
            _apply "hwui.skip_empty_damage=true" "setprop debug.hwui.skip_empty_damage true"
            _apply "hwui.use_buffer_age=true"    "setprop debug.hwui.use_buffer_age true"
            ok "HWUI SkiaGL backend aktywny" ;;
        4)
            _apply_if_changed "supports_background_blur" "${cur_blur}" "0" \
                "settings put global supports_background_blur 0"
            ok "Background Blur wyłączony" ;;
        5)
            _sh "service call SurfaceFlinger 1008 i32 0" || true
            _apply "supports_background_blur=1" \
                "settings put global supports_background_blur 1"
            _apply "hwui.renderer reset" "setprop debug.hwui.renderer \"\""
            ok "SurfaceFlinger przywrócony (HWC ponownie aktywny)" ;;
        0) return ;;
        *) warn "Nieznana opcja" ;;
    esac
}

# ───────────────────────────────────────────────────────────────────────────────
# §12  FIX D — PELT / SCHEDUTIL / KERNEL SCHEDULER
#      Android 16 PELT kalibrowany pod big.LITTLE 4-8C.
#      Na 2-core A55: thrashing częstotliwości → thermal throttle → stutter
# ───────────────────────────────────────────────────────────────────────────────

_fix_kernel_scheduler() {
    hdr "Fix D: PELT / schedutil (2-core A55 calibration)"
    _backup_settings

    local cur_up cur_down cur_lat
    local sched_base="/sys/devices/system/cpu/cpufreq/policy0/schedutil"
    cur_up="$(  _get_kernel "${sched_base}/up_rate_limit_us")"
    cur_down="$(_get_kernel "${sched_base}/down_rate_limit_us")"
    cur_lat="$( _get_kernel "/proc/sys/kernel/sched_latency_ns")"

    printf "\n"
    printf "  ${GRAY}┌──────────────────────────────────────────────────────────┐${C0}\n"
    printf "  ${GRAY}│${C0}  ${WHITE}%-36s${C0}  %8s  →  %8s  ${GRAY}│${C0}\n" \
           "up_rate_limit_us:"   "${cur_up}"   "${SCHED_UP_OPT}"
    printf "  ${GRAY}│${C0}  ${WHITE}%-36s${C0}  %8s  →  %8s  ${GRAY}│${C0}\n" \
           "down_rate_limit_us:" "${cur_down}" "${SCHED_DOWN_OPT}"
    printf "  ${GRAY}│${C0}  ${WHITE}%-36s${C0}  %8s  →  %8s  ${GRAY}│${C0}\n" \
           "sched_latency_ns:"   "${cur_lat}"  "${SCHED_LAT_OPT}"
    printf "  ${GRAY}└──────────────────────────────────────────────────────────┘${C0}\n\n"
    printf "  ${GRAY}Efekt: redukcja thrashingu A55 + redukcja opóźnienia wątku UI${C0}\n\n"

    printf "  ${CYAN}1${C0}) ${GREEN}Optymalne wartości${C0} ${GRAY}(wg raportu inżynieryjnego 2026)${C0}\n"
    printf "  ${CYAN}2${C0}) Przywróć Samsung default\n"
    printf "  ${CYAN}0${C0}) Anuluj\n\n"
    read -r -p "  > " _c

    case "${_c}" in
        1)
            _bar "up_rate_limit_us" 25
            _sh "echo ${SCHED_UP_OPT} > ${sched_base}/up_rate_limit_us" 2>/dev/null || true
            printf "\n"
            _bar "down_rate_limit_us" 50
            _sh "echo ${SCHED_DOWN_OPT} > ${sched_base}/down_rate_limit_us" 2>/dev/null || true
            printf "\n"
            _bar "sched_latency_ns" 75
            _sh "echo ${SCHED_LAT_OPT} > /proc/sys/kernel/sched_latency_ns" 2>/dev/null || true
            printf "\n"
            _bar "sched_boost" 90
            _sh "echo 1 > /proc/sys/kernel/sched_boost" 2>/dev/null || true
            printf "\n"
            _bar "Gotowe" 100; printf "\n"
            ok "schedutil zoptymalizowany dla Exynos W920"
            sub "up=${SCHED_UP_OPT}µs | down=${SCHED_DOWN_OPT}µs | lat=${SCHED_LAT_OPT}ns"
            warn "Parametry jądra reset po restarcie (nie są persistentne)" ;;
        2)
            _sh "echo ${SCHED_UP_DEFAULT} > ${sched_base}/up_rate_limit_us" 2>/dev/null || true
            _sh "echo ${SCHED_DOWN_DEFAULT} > ${sched_base}/down_rate_limit_us" 2>/dev/null || true
            ok "schedutil przywrócony do Samsung default" ;;
        0) return ;;
        *) warn "Nieznana opcja" ;;
    esac
}

# ───────────────────────────────────────────────────────────────────────────────
# §13  FIX E — PAMIĘĆ: MGLRU + zRAM + SWAPPINESS
#      Samsung: swappiness=100 → kompresja/dekompresja zRAM blokuje oba A55
#      Objaw: freeze 0.5-1.5s przy otwieraniu aplikacji (np. Spotify)
# ───────────────────────────────────────────────────────────────────────────────

_fix_memory() {
    hdr "Fix E: Pamięć (MGLRU / zRAM / swappiness)"
    _backup_settings

    local meminfo; meminfo="$(_sh_retry "cat /proc/meminfo" || echo '')"
    local total_kb avail_kb
    total_kb="$(echo "${meminfo}" | awk '/^MemTotal/{print $2}')"
    avail_kb="$(echo "${meminfo}" | awk '/^MemAvailable/{print $2}')"
    local total_mb=$(( ${total_kb:-0} / 1024 ))
    local avail_mb=$(( ${avail_kb:-0} / 1024 ))
    local used_mb=$(( total_mb - avail_mb ))
    local pct=$(( used_mb * 100 / (total_mb > 0 ? total_mb : 1) ))
    local cur_swap; cur_swap="$(_get_kernel "/proc/sys/vm/swappiness")"
    local ram_color="${GREEN}"
    [[ ${pct} -gt 80 ]] && ram_color="${RED}"
    [[ ${pct} -gt 60 && ${pct} -le 80 ]] && ram_color="${YELLOW}"

    printf "\n"
    printf "  ${GRAY}┌──────────────────────────────────────────────────┐${C0}\n"
    printf "  ${GRAY}│${C0}  ${WHITE}%-18s${C0}  ${ram_color}%dMB / %dMB (%d%%)${C0}%-10s${GRAY}│${C0}\n" \
           "RAM:" "${used_mb}" "${total_mb}" "${pct}" ""
    printf "  ${GRAY}│${C0}  ${WHITE}%-18s${C0}  %s ${GRAY}(Samsung default: 100)${C0} ${GRAY}│${C0}\n" \
           "swappiness:" "${cur_swap}"
    printf "  ${GRAY}└──────────────────────────────────────────────────┘${C0}\n\n"

    [[ ${pct} -gt 80 ]] && warn "Krytyczne zużycie RAM!"

    printf "  ${CYAN}1${C0}) ${GREEN}Pełna optymalizacja pamięci${C0} ${GRAY}(pakiet optymalny)${C0}\n"
    printf "  ${CYAN}2${C0}) swappiness ${VM_SWAP_DEFAULT}→${VM_SWAP_OPT}     ${GRAY}— redukcja narzutu zRAM${C0}\n"
    printf "  ${CYAN}3${C0}) extra_free_kbytes      ${GRAY}— zapobiega direct reclaim freeze${C0}\n"
    printf "  ${CYAN}4${C0}) Trim caches            ${GRAY}— pm trim-caches${C0}\n"
    printf "  ${CYAN}5${C0}) Phantom Process off    ${GRAY}— nie zabijaj czujników/zdrowia${C0}\n"
    printf "  ${CYAN}6${C0}) Wyczyść log buffer     ${GRAY}— logcat -c (logd działa)${C0}\n"
    printf "  ${CYAN}0${C0}) Anuluj\n\n"
    read -r -p "  > " _c

    case "${_c}" in
        1)
            _bar "swappiness → ${VM_SWAP_OPT}" 14
            _sh "echo ${VM_SWAP_OPT} > /proc/sys/vm/swappiness" 2>/dev/null || true
            printf "\n"
            _bar "extra_free_kbytes" 28
            _sh "echo ${VM_EXTRA_FREE_KB} > /proc/sys/vm/extra_free_kbytes" 2>/dev/null || \
            _sh "setprop sys.sysctl.extra_free_kbytes ${VM_EXTRA_FREE_KB}" || true
            printf "\n"
            _bar "phantom_procs off" 42
            local cur_phan; cur_phan="$(_get_setting global monitor_phantom_procs)"
            _apply_if_changed "monitor_phantom_procs" "${cur_phan}" "false" \
                "settings put global monitor_phantom_procs false"
            printf "\n"
            _bar "bg process limit=4" 56
            local cur_bgl; cur_bgl="$(_get_setting global background_process_limit)"
            _apply_if_changed "background_process_limit" "${cur_bgl}" "4" \
                "settings put global background_process_limit 4"
            printf "\n"
            _bar "ART heap tuning" 70
            _apply "dalvik.heaptargetutilization" \
                "setprop dalvik.vm.heaptargetutilization ${ART_HEAPTARGET}"
            _apply "dalvik.heapmaxfree" \
                "setprop dalvik.vm.heapmaxfree ${ART_HEAPMAXFREE}"
            printf "\n"
            _bar "Trim caches" 85
            _sh_retry "pm trim-caches 0" 2>/dev/null || \
            _sh_retry "pm trim-caches 2147483647" 2>/dev/null || true
            printf "\n"
            _bar "Log buffer" 95
            _sh "logcat -c" 2>/dev/null || true
            _apply "logd.buffer.size=64K" "setprop logd.buffer.size 64K"
            printf "\n"
            _bar "Gotowe" 100; printf "\n"
            ok "Optymalizacja pamięci zakończona"
            sub "swap=${VM_SWAP_OPT} | extra_free=${VM_EXTRA_FREE_KB}KB" ;;
        2)  _sh "echo ${VM_SWAP_OPT} > /proc/sys/vm/swappiness" 2>/dev/null || true
            ok "swappiness → ${VM_SWAP_OPT}" ;;
        3)  _sh "echo ${VM_EXTRA_FREE_KB} > /proc/sys/vm/extra_free_kbytes" 2>/dev/null || true
            ok "extra_free_kbytes → ${VM_EXTRA_FREE_KB}KB" ;;
        4)  _sh_retry "pm trim-caches 0" || \
            _sh_retry "pm trim-caches 2147483647" || true
            ok "Cache aplikacji wyczyszczone" ;;
        5)  _apply_if_changed "monitor_phantom_procs" \
                "$(_get_setting global monitor_phantom_procs)" "false" \
                "settings put global monitor_phantom_procs false"
            ok "Phantom Process Monitor wyłączony"
            sub "Procesy czujników / zdrowia nie będą zabijane" ;;
        6)  _sh "logcat -c" 2>/dev/null || true
            _apply "logd.buffer.size=64K" "setprop logd.buffer.size 64K"
            ok "Log buffer wyczyszczony (logd DZIAŁA — nigdy nie używaj 'stop logd'!)" ;;
        0) return ;;
        *) warn "Nieznana opcja" ;;
    esac
}

# ───────────────────────────────────────────────────────────────────────────────
# §14  FIX F — DEBLOAT + WAKE_LOCK
#      Procesy One UI 8.0 obciążające CPU w stanie bezczynności
# ───────────────────────────────────────────────────────────────────────────────

_fix_debloat() {
    hdr "Fix F: Debloat One UI 8.0 + WAKE_LOCK"

    printf "\n"
    printf "  ${GRAY}Pakiet                                              Problem${C0}\n"
    printf "  ${GRAY}──────────────────────────────────────────────────────────────────${C0}\n"
    printf "  ${WHITE}%-50s${C0} %s\n" "com.samsung.android.appcloud"     "Auto-restart CPU w bezczynności"
    printf "  ${WHITE}%-50s${C0} %s\n" "com.samsung.android.messaging"    "Duplikuje powiadomienia (vs GMsgs)"
    printf "  ${WHITE}%-50s${C0} %s\n" "com.google.android.assistant"     "WAKE_LOCK → drenaż + lagi"
    printf "  ${WHITE}%-50s${C0} %s\n" "com.android.vending"              "Nadmierny WAKE_LOCK Play Store"
    printf "  ${WHITE}%-50s${C0} %s\n" "com.samsung.android.bixby.*"      "Nasłuchiwanie w tle (nieużywane)"
    printf "\n"
    printf "  ${CYAN}1${C0}) ${GREEN}Bezpieczny debloat${C0}    ${GRAY}— WAKE_LOCK + appcloud (zalecane)${C0}\n"
    printf "  ${CYAN}2${C0}) WAKE_LOCK restrictions ${GRAY}— kluczowe dla baterii${C0}\n"
    printf "  ${CYAN}3${C0}) Wyłącz appcloud        ${GRAY}— marketingowe auto-install${C0}\n"
    printf "  ${CYAN}4${C0}) Wyłącz Bixby           ${GRAY}— jeśli nieużywane${C0}\n"
    printf "  ${CYAN}5${C0}) Wyłącz messaging       ${GRAY}— jeśli używasz Google Messages${C0}\n"
    printf "  ${CYAN}0${C0}) Anuluj\n\n"
    read -r -p "  > " _c

    case "${_c}" in
        1)
            _apply "Assistant WAKE_LOCK → ignore" \
                "cmd appops set com.google.android.assistant WAKE_LOCK ignore"
            _apply "Play Store WAKE_LOCK → ignore" \
                "cmd appops set com.android.vending WAKE_LOCK ignore"
            _apply "appcloud disabled" \
                "pm disable-user --user 0 com.samsung.android.appcloud"
            _apply "shealth autodetect off" \
                "pm disable-user --user 0 com.samsung.android.wear.shealth.autodetect" \
                2>/dev/null || true
            ok "Bezpieczny debloat zastosowany"
            sub "Oczekiwana poprawa baterii: 15-30%" ;;
        2)
            _apply "Assistant WAKE_LOCK → ignore" \
                "cmd appops set com.google.android.assistant WAKE_LOCK ignore"
            _apply "Play Store WAKE_LOCK → ignore" \
                "cmd appops set com.android.vending WAKE_LOCK ignore"
            ok "WAKE_LOCK restrictions aktywne" ;;
        3)
            _apply "appcloud disabled" \
                "pm disable-user --user 0 com.samsung.android.appcloud"
            ok "com.samsung.android.appcloud — wyłączone" ;;
        4)
            _apply "bixby.agent disabled" \
                "pm disable-user --user 0 com.samsung.android.bixby.agent"
            _apply "bixby.wakeup disabled" \
                "pm disable-user --user 0 com.samsung.android.bixby.wakeup"
            ok "Bixby wyłączony" ;;
        5)
            warn "Wyłączenie samsung.messaging usuwa natywne SMS/MMS na zegarku"
            read -r -p "  Potwierdzam — kontynuować? [tak/N] " _conf
            [[ "${_conf,,}" == "tak" ]] || return
            _apply "samsung.messaging disabled" \
                "pm disable-user --user 0 com.samsung.android.messaging"
            ok "com.samsung.android.messaging — wyłączone" ;;
        0) return ;;
        *) warn "Nieznana opcja" ;;
    esac
}

# ───────────────────────────────────────────────────────────────────────────────
# §15  FIX G — KOMPILACJA ART
#      Guard: blokada gdy bateria < ART_BATTERY_MIN (20%)
#      Po OTA aplikacje są w trybie "verified" — nie skompilowane
# ───────────────────────────────────────────────────────────────────────────────

_fix_art() {
    hdr "Fix G: Kompilacja ART (post-OTA)"

    # Guard baterii
    _check_battery || return 1

    info "Bateria: ${DEVICE_BATTERY}% ${GRAY}(min: ${ART_BATTERY_MIN}%)${C0}"
    info "Czas: 3-8 minut. Zegarek musi być połączony przez cały czas."
    printf "\n"
    printf "  ${CYAN}1${C0}) speed-profile  ${GRAY}— ${GREEN}ZALECANE${GRAY} po OTA, ~5 min${C0}\n"
    printf "  ${CYAN}2${C0}) speed          ${GRAY}— szybsze uruchomienie, ~8 min${C0}\n"
    printf "  ${CYAN}3${C0}) verify         ${GRAY}— szybkie, bez kompilacji, ~1 min${C0}\n"
    printf "  ${CYAN}4${C0}) reset profili  ${GRAY}— wymuś ponowną naukę (przed opcją 1)${C0}\n"
    printf "  ${CYAN}0${C0}) Anuluj\n\n"
    read -r -p "  > " _c

    case "${_c}" in
        4)
            info "Reset profili ART..."
            _sh_retry "pm compile --reset -a" || \
            _sh_retry "cmd package compile --reset -a" || true
            ok "Profile ART zresetowane"
            return ;;
        0) return ;;
        1|2|3) ;;
        *) warn "Nieznana opcja"; return ;;
    esac

    local mode
    case "${_c}" in 1) mode="speed-profile" ;; 2) mode="speed" ;; 3) mode="verify" ;; esac

    info "pm compile -m ${mode} -a ..."
    local sdk="${DEVICE_SDK:-31}" start_t="${SECONDS}"
    printf "\n"

    if [[ "${sdk}" -ge 33 ]]; then
        timeout 600 adb -s "${DEVICE}" shell "pm compile -m ${mode} -a" 2>/dev/null &
    else
        timeout 600 adb -s "${DEVICE}" shell "cmd package compile -m ${mode} --all" 2>/dev/null &
    fi
    local cpid=$!

    # Spinner z auto-wake
    local fi=0 frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
    local bat_warn=false
    while kill -0 ${cpid} 2>/dev/null; do
        local elapsed=$(( SECONDS - start_t ))
        printf "\r  ${CYAN}%s${C0}  Kompilowanie ART  ${GRAY}[%ds]${C0}  bat:${DEVICE_BATTERY}%%   " \
               "${frames[$(( fi % ${#frames[@]} ))]}" "${elapsed}"
        sleep 1.5
        (( fi++ )) || true
        adb -s "${DEVICE}" shell input keyevent KEYCODE_WAKEUP 2>/dev/null || true

        # Ostrzeżenie baterii w trakcie
        if [[ "${bat_warn}" == "false" && "${DEVICE_BATTERY}" -lt 15 ]] 2>/dev/null; then
            bat_warn=true
            printf "\n"
            warn "Bateria poniżej 15% podczas kompilacji — podłącz ładowarkę!"
        fi
    done
    wait ${cpid} && local rc=0 || local rc=$?
    printf "\n"

    local elapsed=$(( SECONDS - start_t ))
    if [[ ${rc} -eq 0 ]]; then
        ok "Kompilacja ART ukończona (${elapsed}s)"
        _sh "cmd package bg-dexopt-job" 2>/dev/null || true
        info "Pierwsze uruchomienia aplikacji będą teraz szybsze"
    else
        warn "Kompilacja: kod ${rc} — częściowo ukończona lub timeout"
    fi
}

# ───────────────────────────────────────────────────────────────────────────────
# §16  PAKIET KOMPLEKSOWY — wszystkie fixy
# ───────────────────────────────────────────────────────────────────────────────

_fix_all() {
    hdr "PAKIET KOMPLEKSOWY — One UI 8.0 Post-Update Fix"
    _backup_settings

    printf "\n"
    printf "  ${YELLOW}${BOLD}  ┌──────────────────────────────────────────────────────┐${C0}\n"
    printf "  ${YELLOW}${BOLD}  │  Zostaną zastosowane wszystkie optymalizacje.        │${C0}\n"
    printf "  ${YELLOW}${BOLD}  │  Backup: %-42s│${C0}\n" "$(basename "${BACKUP_FILE}")"
    printf "  ${YELLOW}${BOLD}  └──────────────────────────────────────────────────────┘${C0}\n\n"
    read -r -p "  Kontynuować? [t/N] " _conf
    [[ "${_conf,,}" != "t" ]] && { info "Anulowano."; return; }
    printf "\n"

    local s=0 t=22

    # A — Animacje 0.5x (idempotentne)
    local cwa; cwa="$(_get_setting global window_animation_scale)"
    _bar "Animacje 0.5x" $(( ++s*100/t )); printf "\n"
    _apply_if_changed "window_animation_scale"     "${cwa}" "0.5" \
        "settings put global window_animation_scale 0.5"
    _apply "transition_animation_scale=0.5" \
        "settings put global transition_animation_scale 0.5"
    _apply "animator_duration_scale=0.5" \
        "settings put global animator_duration_scale 0.5"

    # B — AOD off (idempotentne)
    local caod; caod="$(_get_setting secure doze_always_on)"
    _bar "AOD off (GPU bug)" $(( ++s*100/t )); printf "\n"
    _apply_if_changed "doze_always_on" "${caod}" "0" \
        "settings put secure doze_always_on 0"
    _apply "doze_enabled=0" "settings put secure doze_enabled 0"

    # C — SF Force GPU
    _bar "SF Force GPU" $(( ++s*100/t )); printf "\n"
    _sh "service call SurfaceFlinger 1008 i32 1" || true

    # C — SkiaGL
    local crend; crend="$(_get_prop debug.hwui.renderer)"
    _bar "HWUI SkiaGL" $(( ++s*100/t )); printf "\n"
    _apply_if_changed "hwui.renderer" "${crend:-}" "skiagl" \
        "setprop debug.hwui.renderer skiagl"

    # C — HWUI flags
    _bar "HWUI flags" $(( ++s*100/t )); printf "\n"
    _apply "hwui.skip_empty_damage=true" "setprop debug.hwui.skip_empty_damage true"
    _apply "hwui.use_buffer_age=true"    "setprop debug.hwui.use_buffer_age true"
    _apply "hwui.profile=false"          "setprop debug.hwui.profile false"

    # C — Blur off
    local cblur; cblur="$(_get_setting global supports_background_blur)"
    _bar "Blur off" $(( ++s*100/t )); printf "\n"
    _apply_if_changed "supports_background_blur" "${cblur}" "0" \
        "settings put global supports_background_blur 0"
    _apply "sf.supports_blur=0" \
        "setprop ro.surface_flinger.supports_background_blur 0"

    # C — High-prio render
    _bar "High-prio render" $(( ++s*100/t )); printf "\n"
    _apply "high_priority_render_thread=1" \
        "settings put global high_priority_render_thread 1"

    # D — schedutil
    local sched_base="/sys/devices/system/cpu/cpufreq/policy0/schedutil"
    _bar "schedutil up=${SCHED_UP_OPT}" $(( ++s*100/t )); printf "\n"
    _sh "echo ${SCHED_UP_OPT} > ${sched_base}/up_rate_limit_us" 2>/dev/null || true

    _bar "schedutil down=${SCHED_DOWN_OPT}" $(( ++s*100/t )); printf "\n"
    _sh "echo ${SCHED_DOWN_OPT} > ${sched_base}/down_rate_limit_us" 2>/dev/null || true

    _bar "sched_latency=${SCHED_LAT_OPT}" $(( ++s*100/t )); printf "\n"
    _sh "echo ${SCHED_LAT_OPT} > /proc/sys/kernel/sched_latency_ns" 2>/dev/null || true

    # E — vm
    _bar "swappiness → ${VM_SWAP_OPT}" $(( ++s*100/t )); printf "\n"
    _sh "echo ${VM_SWAP_OPT} > /proc/sys/vm/swappiness" 2>/dev/null || true

    _bar "extra_free_kbytes" $(( ++s*100/t )); printf "\n"
    _sh "echo ${VM_EXTRA_FREE_KB} > /proc/sys/vm/extra_free_kbytes" 2>/dev/null || true

    # E — phantom procs
    local cphan; cphan="$(_get_setting global monitor_phantom_procs)"
    _bar "phantom_procs off" $(( ++s*100/t )); printf "\n"
    _apply_if_changed "monitor_phantom_procs" "${cphan}" "false" \
        "settings put global monitor_phantom_procs false"

    # E — bg process limit
    local cbgl; cbgl="$(_get_setting global background_process_limit)"
    _bar "bg_process_limit=4" $(( ++s*100/t )); printf "\n"
    _apply_if_changed "background_process_limit" "${cbgl}" "4" \
        "settings put global background_process_limit 4"

    # E — ART heap
    _bar "ART heap tuning" $(( ++s*100/t )); printf "\n"
    _apply "dalvik.heaptargetutilization" \
        "setprop dalvik.vm.heaptargetutilization ${ART_HEAPTARGET}"
    _apply "dalvik.heapmaxfree" "setprop dalvik.vm.heapmaxfree ${ART_HEAPMAXFREE}"

    # F — WAKE_LOCK
    _bar "WAKE_LOCK restrictions" $(( ++s*100/t )); printf "\n"
    _apply "Assistant WAKE_LOCK → ignore" \
        "cmd appops set com.google.android.assistant WAKE_LOCK ignore"
    _apply "Play Store WAKE_LOCK → ignore" \
        "cmd appops set com.android.vending WAKE_LOCK ignore"

    # F — Debloat
    _bar "Debloat appcloud" $(( ++s*100/t )); printf "\n"
    _apply "appcloud disabled" \
        "pm disable-user --user 0 com.samsung.android.appcloud"

    # Trim + log
    _bar "Trim caches" $(( ++s*100/t )); printf "\n"
    _sh_retry "pm trim-caches 0" 2>/dev/null || true

    _bar "Log buffer" $(( ++s*100/t )); printf "\n"
    _sh "logcat -c" 2>/dev/null || true
    _apply "logd.buffer.size=64K" "setprop logd.buffer.size 64K"

    _bar "Finalizacja" 100; printf "\n\n"

    printf "  ${LGREEN}${BOLD}  ╔══════════════════════════════════════════════════════╗${C0}\n"
    printf "  ${LGREEN}${BOLD}  ║  PAKIET KOMPLEKSOWY ZASTOSOWANY ✓                   ║${C0}\n"
    printf "  ${LGREEN}${BOLD}  ╚══════════════════════════════════════════════════════╝${C0}\n\n"
    ok "A: Animacje 0.5x"
    ok "B: AOD off (GPU voltage bug — brak patcha sterownika 03/2026)"
    ok "C: SF Force GPU | SkiaGL | Blur off"
    ok "D: schedutil up=1000 down=10000 lat=8ms"
    ok "E: swappiness=60 | extra_free | phantom_procs off"
    ok "F: WAKE_LOCK restrict | appcloud disabled"
    printf "\n"
    warn "schedutil + swappiness reset po restarcie"
    info "Zalecany restart → Fix G (Kompilacja ART)"
}

# ───────────────────────────────────────────────────────────────────────────────
# §17  PRZYWRACANIE USTAWIEŃ
# ───────────────────────────────────────────────────────────────────────────────

_restore() {
    hdr "Przywracanie ustawień"

    local -a backups=()
    while IFS= read -r -d '' f; do backups+=("${f}"); done \
        < <(find "${LOG_DIR}" -name "backup_*.txt" -print0 2>/dev/null | sort -z)

    if [[ ${#backups[@]} -eq 0 ]]; then
        warn "Brak backupu — przywracam wartości fabryczne One UI 8.0"
        _apply_if_changed "window_animation_scale" \
            "$(_get_setting global window_animation_scale)" "1.0" \
            "settings put global window_animation_scale 1.0"
        _apply "transition_animation_scale=1.0" \
            "settings put global transition_animation_scale 1.0"
        _apply "animator_duration_scale=1.0" \
            "settings put global animator_duration_scale 1.0"
        _apply "doze_always_on=1" "settings put secure doze_always_on 1"
        _apply "doze_enabled=1"   "settings put secure doze_enabled 1"
        _apply "monitor_phantom_procs=true" \
            "settings put global monitor_phantom_procs true"
        _apply "background_process_limit=-1" \
            "settings put global background_process_limit -1"
        _apply "supports_background_blur=1" \
            "settings put global supports_background_blur 1"
        _apply "delete high_priority_render_thread" \
            "settings delete global high_priority_render_thread"
        _sh "service call SurfaceFlinger 1008 i32 0" || true
        _apply "hwui.renderer reset" "setprop debug.hwui.renderer \"\""
        _apply "Assistant WAKE_LOCK → allow" \
            "cmd appops set com.google.android.assistant WAKE_LOCK allow"
        _apply "Play Store WAKE_LOCK → allow" \
            "cmd appops set com.android.vending WAKE_LOCK allow"
        _sh "echo ${VM_SWAP_DEFAULT} > /proc/sys/vm/swappiness" 2>/dev/null || true
        ok "Wartości fabryczne One UI 8.0 przywrócone"
        return
    fi

    printf "\n  Dostępne backupy:\n"
    for i in "${!backups[@]}"; do
        printf "  ${CYAN}%d${C0}) %s\n" "$((i+1))" "$(basename "${backups[$i]}")"
    done
    printf "  ${CYAN}0${C0}) Anuluj\n\n"
    read -r -p "  > " sel
    [[ "${sel}" == "0" ]] && return
    local idx=$(( sel - 1 ))
    [[ ${idx} -lt 0 || ${idx} -ge ${#backups[@]} ]] && { warn "Nieprawidłowy wybór"; return; }

    local bfile="${backups[$idx]}" restored=0 failed=0
    info "Przywracam z: $(basename "${bfile}")"
    while IFS= read -r line; do
        case "${line}" in
            SETTINGS:*)
                local rest="${line#SETTINGS:}" ns="${rest%%:*}" kv="${rest#*:}"
                local key="${kv%%=*}" val="${kv#*=}"
                if [[ "${val}" == "null" ]]; then
                    _sh_retry "settings delete ${ns} ${key}" 2>/dev/null \
                        && (( restored++ )) || (( failed++ ))
                else
                    _sh_retry "settings put ${ns} ${key} ${val}" 2>/dev/null \
                        && (( restored++ )) || (( failed++ ))
                fi ;;
            PROP:*)
                local pv="${line#PROP:}" prop="${pv%%=*}" val="${pv#*=}"
                [[ -z "${val}" ]] && continue
                _sh_retry "setprop ${prop} ${val}" 2>/dev/null \
                    && (( restored++ )) || (( failed++ )) ;;
            KERNEL:*)
                local kv="${line#KERNEL:}" kpath="${kv%%=*}" val="${kv#*=}"
                [[ "${val}" == "N/A" ]] && continue
                _sh "echo ${val} > ${kpath}" 2>/dev/null \
                    && (( restored++ )) || (( failed++ )) ;;
        esac
    done < "${bfile}"
    ok "Przywrócono: ${restored} parametrów (błędy: ${failed})"
}

# ───────────────────────────────────────────────────────────────────────────────
# §18  FACTORY RESET (MASTER CLEAR)
#      2-stopniowe potwierdzenie + instrukcja + _countdown_reboot + exit
# ───────────────────────────────────────────────────────────────────────────────

_factory_reset() {
    hdr "Factory Reset — Master Clear"

    printf "\n"
    printf "  ${RED}${BOLD}  ┌──────────────────────────────────────────────────────────┐${C0}\n"
    printf "  ${RED}${BOLD}  │  ⚠  OSTRZEŻENIE — OPERACJA NIEODWRACALNA               │${C0}\n"
    printf "  ${RED}${BOLD}  │                                                        │${C0}\n"
    printf "  ${RED}${BOLD}  │  • Wszystkie dane na zegarku zostaną usunięte           │${C0}\n"
    printf "  ${RED}${BOLD}  │  • Autoryzacja ADB wygaśnie                            │${C0}\n"
    printf "  ${RED}${BOLD}  │  • Zegarek wróci do ustawień fabrycznych               │${C0}\n"
    printf "  ${RED}${BOLD}  │  • Backupy skryptu POZOSTAJĄ na hoście (PC/Termux)     │${C0}\n"
    printf "  ${RED}${BOLD}  └──────────────────────────────────────────────────────────┘${C0}\n\n"

    # Potwierdzenie 1
    printf "  ${YELLOW}Potwierdzenie 1/2 — wpisz dokładnie:${C0} ${WHITE}RESET${C0}\n"
    read -r -p "  > " _c1
    if [[ "${_c1}" != "RESET" ]]; then
        info "Anulowano (nieprawidłowe potwierdzenie)"
        return
    fi

    # Potwierdzenie 2
    printf "\n  ${YELLOW}Potwierdzenie 2/2 — wpisz dokładnie:${C0} ${WHITE}POTWIERDZAM${C0}\n"
    read -r -p "  > " _c2
    if [[ "${_c2}" != "POTWIERDZAM" ]]; then
        info "Anulowano"
        return
    fi

    printf "\n"
    printf "  ${LGREEN}${BOLD}  ╔══════════════════════════════════════════════════════════════╗${C0}\n"
    printf "  ${LGREEN}${BOLD}  ║  CO ZROBIĆ PO RESTARCIE:                                    ║${C0}\n"
    printf "  ${LGREEN}${BOLD}  ║  1) Przejdź konfigurację pierwszego uruchomienia zegarka    ║${C0}\n"
    printf "  ${LGREEN}${BOLD}  ║  2) Połącz zegarek z Wi-Fi i sparuj z Galaxy Watch Manager ║${C0}\n"
    printf "  ${LGREEN}${BOLD}  ║  3) Włącz: Opcje programisty → Debugowanie przez Wi-Fi     ║${C0}\n"
    printf "  ${LGREEN}${BOLD}  ║  4) Uruchom skrypt ponownie i zastosuj Pakiet Kompleksowy   ║${C0}\n"
    printf "  ${LGREEN}${BOLD}  ║  5) Na koniec: Fix G (Kompilacja ART)                      ║${C0}\n"
    printf "  ${LGREEN}${BOLD}  ╚══════════════════════════════════════════════════════════════╝${C0}\n\n"

    if ! _countdown_reboot 30 "Master Clear za"; then
        info "Factory Reset anulowany"
        return
    fi

    info "Wysyłam polecenie Master Clear..."
    _log "ACTION" "FACTORY RESET wysłany na ${DEVICE}"

    # Wyślij reset (WearOS / Android)
    _sh "am broadcast -a android.intent.action.MASTER_CLEAR" 2>/dev/null || \
    _sh "recovery --wipe_data" 2>/dev/null || \
    _sh "am start -n com.samsung.android.sm.policy/.recovery.ResetSmartWatchActivity" \
        2>/dev/null || true

    warn "Factory Reset wysłany — zegarek uruchamia się ponownie"
    warn "Autoryzacja ADB wygasła. Skrypt kończy działanie."
    info "Następnie postępuj zgodnie z instrukcją powyżej."
    _log "ACTION" "FACTORY RESET zakończony — skrypt zamknięty"
    exit 0
}

# ───────────────────────────────────────────────────────────────────────────────
# §19  DIAGNOSTYKA  (Toybox-safe: bez top -b, bez SF --latency)
# ───────────────────────────────────────────────────────────────────────────────

_run_diagnostics() {
    hdr "Diagnostyka systemu (WearOS 6.0 / Toybox-safe)"

    local out_dir="${LOG_DIR}/diag_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "${out_dir}"
    info "Wyniki: ${out_dir}/"

    local s=0 t=10

    _bar "CPU processes" $(( ++s*100/t )); printf "\n"
    _sh_retry "top -n 1 -d 1" > "${out_dir}/cpu_top.txt" 2>&1 || \
        _sh_retry "top -n 1"  > "${out_dir}/cpu_top.txt" 2>&1 || \
        _sh_retry "ps -A"     > "${out_dir}/cpu_top.txt" 2>&1

    _bar "SurfaceFlinger" $(( ++s*100/t )); printf "\n"
    { timeout 5 adb -s "${DEVICE}" shell "dumpsys SurfaceFlinger" \
        > "${out_dir}/sf_dump.txt" 2>&1; } &
    wait $! 2>/dev/null || true

    _bar "GFX frame timing" $(( ++s*100/t )); printf "\n"
    _sh_retry "dumpsys gfxinfo" > "${out_dir}/gfx_info.txt" 2>&1 || true

    _bar "RAM + zRAM" $(( ++s*100/t )); printf "\n"
    {
        echo "=== dumpsys meminfo ==="
        _sh_retry "dumpsys meminfo"
        echo "=== /proc/meminfo ==="
        _sh_retry "cat /proc/meminfo"
        echo "=== swappiness ==="
        _get_kernel "/proc/sys/vm/swappiness"
        echo "=== zRAM/swap ==="
        _sh_retry "cat /proc/swaps" || echo "brak"
    } > "${out_dir}/mem_dump.txt" 2>&1

    _bar "schedutil params" $(( ++s*100/t )); printf "\n"
    {
        local sb="/sys/devices/system/cpu/cpufreq/policy0/schedutil"
        echo "=== schedutil ==="
        for p in up_rate_limit_us down_rate_limit_us; do
            printf "%-40s = %s\n" "${p}" "$(_get_kernel "${sb}/${p}")"
        done
        echo "=== sched_latency_ns ==="
        _get_kernel "/proc/sys/kernel/sched_latency_ns"
    } > "${out_dir}/scheduler.txt" 2>&1

    _bar "Bateria + termale" $(( ++s*100/t )); printf "\n"
    {
        echo "=== Battery ==="
        _sh_retry "dumpsys battery" 2>/dev/null || echo "N/A"
        echo ""
        echo "=== Thermal zones ==="
        _sh_retry "cat /sys/class/thermal/thermal_zone*/temp" 2>/dev/null || echo "N/A"
    } > "${out_dir}/thermal.txt" 2>&1

    _bar "Logcat (W+)" $(( ++s*100/t )); printf "\n"
    timeout 10 adb -s "${DEVICE}" logcat -d -v brief "*:W" 2>/dev/null \
        > "${out_dir}/system_logs.txt" || true
    grep -E "SurfaceFlinger|AOD|doze|lag|drop|jank|render|W920|Exynos|swapp|PELT|skia|vulkan|Mali|battery" \
        "${out_dir}/system_logs.txt" \
        > "${out_dir}/filtered_logs.txt" 2>/dev/null || true

    _bar "ADB props" $(( ++s*100/t )); printf "\n"
    {
        echo "=== Build & Hardware ==="
        for p in ro.product.model ro.build.display.id ro.build.version.release \
                 ro.build.version.sdk ro.hardware; do
            printf "%-45s = %s\n" "${p}" "$(_get_prop "${p}")"
        done
        echo ""
        echo "=== Rendering props ==="
        for p in debug.hwui.renderer debug.hwui.profile \
                 ro.surface_flinger.supports_background_blur; do
            printf "%-45s = %s\n" "${p}" "$(_get_prop "${p}")"
        done
        echo ""
        echo "=== Settings ==="
        for s in "global window_animation_scale" "global transition_animation_scale" \
                 "secure doze_always_on" "global monitor_phantom_procs" \
                 "global supports_background_blur"; do
            local ns="${s%% *}" k="${s##* }"
            printf "%-45s = %s\n" "${s}" "$(_get_setting "${ns}" "${k}")"
        done
    } > "${out_dir}/props.txt" 2>&1

    _bar "Raport zbiorczy" $(( ++s*100/t )); printf "\n"
    {
        printf "══════════════════════════════════════════════════════\n"
        printf "  GW4 Diagnostic Report — %s v%s\n" "${SCRIPT_NAME}" "${VERSION}"
        printf "  Data: %s\n" "$(date)"
        printf "  Urządzenie: %s | FW: %s\n" "${DEVICE_MODEL}" "${DEVICE_FW}"
        printf "  Bateria: %s%%\n" "${DEVICE_BATTERY}"
        printf "══════════════════════════════════════════════════════\n\n"
        echo "─── RAM Summary ───"
        grep -E "^MemTotal|^MemAvailable|^MemFree" "${out_dir}/mem_dump.txt" | head -5
        echo ""
        echo "─── Swappiness (Samsung=100, optimum=60) ───"
        grep "^[0-9]" "${out_dir}/mem_dump.txt" | head -3
        echo ""
        echo "─── schedutil ───"
        cat "${out_dir}/scheduler.txt"
        echo ""
        echo "─── Janky Frames ───"
        grep -iE "janky|total frames|missed vsync|dropped" \
            "${out_dir}/gfx_info.txt" 2>/dev/null | head -10 || echo "(brak)"
        echo ""
        echo "─── Filtered Error Logs ───"
        head -50 "${out_dir}/filtered_logs.txt" 2>/dev/null || echo "(brak)"
    } > "${out_dir}/RAPORT_ZBIORCZY.txt"

    _bar "Gotowe" 100; printf "\n\n"
    ok "Diagnostyka zapisana: ${out_dir}/"
    printf "\n  ${YELLOW}Wyślij RAPORT_ZBIORCZY.txt przy zgłaszaniu błędu:${C0}\n"
    for f in cpu_top.txt mem_dump.txt scheduler.txt filtered_logs.txt RAPORT_ZBIORCZY.txt; do
        printf "  ${CYAN}→${C0} %s/%s\n" "${out_dir}" "${f}"
    done
    printf "\n"
}

# ───────────────────────────────────────────────────────────────────────────────
# §20  PRZYWRACANIE (backup/fabryczne)
# ───────────────────────────────────────────────────────────────────────────────
# (zaimplementowane w §17)

# ───────────────────────────────────────────────────────────────────────────────
# §21  INSTRUKCJA KONFIGURACJI ADB
# ───────────────────────────────────────────────────────────────────────────────

_show_setup_guide() {
    clear
    printf "${CYAN}${BOLD}"
    printf "  ╔══════════════════════════════════════════════════════════════════╗\n"
    printf "  ║  Instrukcja: Pierwsze połączenie ADB — Galaxy Watch 4          ║\n"
    printf "  ╚══════════════════════════════════════════════════════════════════╝\n"
    printf "${C0}\n"
    printf "${BOLD}  KROK 1: Opcje programisty${C0}\n"
    printf "    ${GRAY}Ustawienia → System → O oprogramowaniu → O zegarku${C0}\n"
    printf "    → ${YELLOW}Numer kompilacji [kliknij 7 razy]${C0}\n\n"
    printf "${BOLD}  KROK 2: Debugowanie Wi-Fi${C0}\n"
    printf "    ${GRAY}Ustawienia → Opcje programisty${C0}\n"
    printf "    → ${YELLOW}Debugowanie przez Wi-Fi → Włącz${C0}\n"
    printf "    Zegarek wyświetli: ${CYAN}192.168.X.X:5555${C0}  ← zanotuj!\n\n"
    printf "${BOLD}  KROK 3: Zatwierdź klucz RSA${C0}\n"
    printf "    PC: ${CYAN}adb connect 192.168.X.X:5555${C0}\n"
    printf "    Zegarek: ${GREEN}Akceptuj${C0} w dialogu\n\n"
    printf "${BOLD}  KROK 4: Weryfikacja${C0}\n"
    printf "    ${CYAN}adb devices${C0}  →  status: ${GREEN}device${C0}\n\n"
    printf "${BOLD}  ONE-CLICK INSTALL (Termux / bash):${C0}\n"
    printf "    ${CYAN}bash <(curl -sL %s/gw4_optimizer_v5.sh)${C0}\n\n" "${RAW_BASE}"
    printf "  ${GRAY}• Ta sama sieć Wi-Fi dla PC/Termux i zegarka\n"
    printf "  • IP może się zmienić po reconnect Wi-Fi\n"
    printf "  • Skrypt auto-wybudza zegarek przy uśpieniu ADB${C0}\n\n"
    read -r -p "  Naciśnij Enter..."
}

# ───────────────────────────────────────────────────────────────────────────────
# §22  BANNER + MENU GŁÓWNE
# ───────────────────────────────────────────────────────────────────────────────

_banner() {
    clear
    local bat_col="${GREEN}"
    [[ "${DEVICE_BATTERY:-100}" -lt 20 ]] && bat_col="${RED}"
    [[ "${DEVICE_BATTERY:-100}" -lt 50 && "${DEVICE_BATTERY:-100}" -ge 20 ]] && \
        bat_col="${YELLOW}"

    printf "${CYAN}${BOLD}"
    printf "  ╔══════════════════════════════════════════════════════════════════════╗\n"
    printf "  ║  %-70s║\n" "${SCRIPT_NAME}  v${VERSION}"
    printf "  ║  %-70s║\n" "SM-R870/75/95 · Exynos W920 (A55 2C / Mali-G68) · One UI 8.0"
    if [[ -n "${DEVICE}" ]]; then
        printf "  ╠══════════════════════════════════════════════════════════════════════╣\n"
        printf "  ║  ${SYM_KEY} %-68s║\n" "${DEVICE}  |  ${DEVICE_MODEL:-?}  |  SDK ${DEVICE_SDK:-?}"
        printf "  ║    %-68s║\n" "FW: ${DEVICE_FW:-?}"
        printf "  ║    Bateria: ${bat_col}%-3s%%${CYAN}%-57s║\n" "${DEVICE_BATTERY:-?}" ""
    fi
    printf "  ╚══════════════════════════════════════════════════════════════════════╝${C0}\n\n"
}

_menu() {
    printf "  ${WHITE}${BOLD}─── OPTYMALIZACJE ──────────────────────────────────────────────────${C0}\n"
    printf "  ${LCYAN}A${C0}) Animacje              ${GRAY}~2s  │ zero ryzyka, efekt natychmiastowy${C0}\n"
    printf "  ${LCYAN}B${C0}) AOD — GPU voltage bug ${GRAY}~2s  │ ${YELLOW}główna przyczyna lag wybudzenia${C0}\n"
    printf "  ${LCYAN}C${C0}) SF/HWUI/Blur          ${GRAY}~5s  │ HWC bug fix + SkiaGL + blur off${C0}\n"
    printf "  ${LCYAN}D${C0}) PELT/schedutil        ${GRAY}~2s  │ A55 2-core thrashing fix${C0}\n"
    printf "  ${LCYAN}E${C0}) Pamięć (zRAM/MGLRU)  ${GRAY}~5s  │ swappiness 100→60, freeze fix${C0}\n"
    printf "  ${LCYAN}F${C0}) Debloat + WAKE_LOCK   ${GRAY}~3s  │ One UI 8.0 + bateria${C0}\n"
    printf "  ${LCYAN}G${C0}) Kompilacja ART        ${GRAY}~5m  │ po OTA │ ${YELLOW}min. ${ART_BATTERY_MIN}%% bat.${C0}\n"
    printf "  ${LCYAN}${BOLD}Z${C0}) ${LGREEN}${BOLD}PAKIET KOMPLEKSOWY${C0}    ${GRAY}~10m │ ${LGREEN}wszystkie fixy naraz${C0}\n"
    printf "\n"
    printf "  ${WHITE}${BOLD}─── NARZĘDZIA ──────────────────────────────────────────────────────${C0}\n"
    printf "  ${LCYAN}8${C0}) Diagnostyka systemu   ${GRAY}zbierz raporty (Toybox-safe)${C0}\n"
    printf "  ${LCYAN}9${C0}) Przywróć ustawienia   ${GRAY}z backupu lub OEM default${C0}\n"
    printf "  ${LCYAN}R${C0}) ${RED}Factory Reset${C0}         ${GRAY}Master Clear (2-step confirm)${C0}\n"
    printf "  ${LCYAN}?${C0}) Instrukcja ADB setup\n"
    printf "  ${LCYAN}Q${C0}) Wyjście\n\n"
}

# ───────────────────────────────────────────────────────────────────────────────
# §23  PĘTLA GŁÓWNA
# ───────────────────────────────────────────────────────────────────────────────

_loop() {
    while true; do
        _banner
        _menu
        read -r -p "  ${LCYAN}${BOLD}Wybierz${C0} > " opt

        case "${opt^^}" in
            A)  _fix_animations ;;
            B)  _fix_aod ;;
            C)  _fix_surfaceflinger ;;
            D)  _fix_kernel_scheduler ;;
            E)  _fix_memory ;;
            F)  _fix_debloat ;;
            G)  _fix_art ;;
            Z)  _fix_all ;;
            8)  _run_diagnostics ;;
            9)  _restore ;;
            R)  _factory_reset ;;
            '?'|H) _show_setup_guide ;;
            Q)  ok "Do widzenia!"; exit 0 ;;
            '')  continue ;;
            *)  warn "Nieznana opcja: '${opt}'" ;;
        esac

        printf "\n"
        read -r -p "  Naciśnij Enter, aby wrócić do menu..."
    done
}

# ───────────────────────────────────────────────────────────────────────────────
# §24  MAIN
# ───────────────────────────────────────────────────────────────────────────────

main() {
    _init
    _banner
    printf "  ${CYAN}Log:${C0} ${LOG_FILE}\n"
    printf "  ${GRAY}v${VERSION} | ADB: $(adb version 2>/dev/null | head -1 | awk '{print $NF}')${C0}\n\n"
    _detect_device
    _loop
}

main "$@"
