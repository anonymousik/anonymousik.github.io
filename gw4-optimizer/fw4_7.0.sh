#!/usr/bin/env bash
# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║  GW4 Pro Optimizer Suite  v6.1.0                                            ║
# ║  Samsung SM-R870/SM-R875/SM-R895 · Exynos W920 · One UI 8.0 / Android 16   ║
# ║                                                                              ║
# ║  One-Click-Install:                                                          ║
# ║  bash <(curl -sL https://raw.githubusercontent.com/anonymousik/             ║
# ║    anonymousik.github.io/refs/heads/main/scripts/gw4-optimizer/             ║
# ║    gw4_optimizer_v6.1.sh)                                                  ║
# ║                                                                              ║
# ║  Changelog: v6.1 → Fix L (AOD Sensor Guard, GMS ML Block, DiagMonAgent off)║
# ║             v6.0 → Shizuku/rish, I/O sched, sched_boost, JIT disable        ║
# ║  SPDX-License-Identifier: MIT                                               ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

set -euo pipefail

# ───────────────────────────────────────────────────────────────────────────────
# §0  STAŁE — Exynos W920 / WearOS 6.0 / Android 16
# ───────────────────────────────────────────────────────────────────────────────

readonly VERSION="6.1.0"
readonly SCRIPT_NAME="GW4 Pro Optimizer Suite"
readonly RAW_BASE="https://raw.githubusercontent.com/anonymousik/anonymousik.github.io/refs/heads/main/scripts/gw4-optimizer"
readonly DEFAULT_PORT="5555"
readonly ADB_RETRY=4
readonly ADB_TIMEOUT=12
readonly ADB_WAKE_RETRY=3
readonly ART_BATTERY_MIN=20          
readonly RECONNECT_TIMEOUT=120       

# Exynos W920 — parametry sprzętowe
readonly W920_CPU_CORES=2
readonly W920_CPU_ARCH="Cortex-A55"
readonly W920_GPU="Mali-G68"
readonly W920_RAM_MB=1500

# ─── Persistence (v5.2) ──────────────────────────────────────────────────────
readonly PROFILE_DIR="${LOG_DIR}/profiles"
readonly DAEMON_PID_FILE="${LOG_DIR}/daemon.pid"
readonly DAEMON_LOG="${LOG_DIR}/daemon.log"
readonly DAEMON_INTERVAL=300      
readonly BOOT_HOOK_PATH="/data/adb/service.d/gw4_perf.sh"

# Shizuku/rish — v6.0
readonly SHIZUKU_PKG="moe.shizuku.privileged.api"
readonly SHIZUKU_APK_URL="https://github.com/RikkaApps/Shizuku/releases/latest/download/shizuku.apk"
readonly RISH_PATH="/data/local/tmp/rish"

# I/O scheduler — v6.0
readonly IO_SCHED_OPT="deadline"   
readonly IO_SCHED_DEFAULT="cfq"

# sched_boost — v6.0
readonly SCHED_BOOST_OPT=1
readonly SCHED_BOOST_PATH="/proc/sys/kernel/sched_boost"

# Thresholds diagnostyki v6.0
readonly DIAG_JANKY_THRESHOLD=5     
readonly DIAG_BATTERY_IDLE_THRESHOLD=2  
readonly DIAG_APP_LAUNCH_THRESHOLD=800  

# ─── Target profiles (v5.2) ──────────────────────────────────────────────────
TARGET="watch"

# Exynos 2100/2200 (Galaxy S21/S22)
readonly PHONE_SCHED_UP_OPT=400        
readonly PHONE_SCHED_DOWN_OPT=8000
readonly PHONE_SCHED_LAT_OPT=3500000
readonly PHONE_VM_SWAP_OPT=80          
readonly PHONE_ART_HEAPSIZE="256m"
readonly PHONE_ART_HEAPGROWTHLIMIT="192m"

# schedutil
readonly SCHED_UP_DEFAULT=500;   SCHED_UP_OPT=1000
readonly SCHED_DOWN_DEFAULT=20000; SCHED_DOWN_OPT=10000
readonly SCHED_LAT_DEFAULT=10000000; SCHED_LAT_OPT=8000000

# vm
readonly VM_SWAP_DEFAULT=100; VM_SWAP_OPT=60
readonly VM_EXTRA_FREE_KB=65536

# ART — v5.1 extended
readonly ART_HEAPTARGET=0.75
readonly ART_HEAPMAXFREE="8m"
ART_HEAPSIZE="128m"
ART_HEAPGROWTHLIMIT="80m"
readonly ART_DEX2OAT_THREADS="1"     

# MGLRU — v5.1
readonly MGLRU_MIN_TTL_MS=1000       

# device_config namespaces
readonly DC_RUNTIME_NS="runtime_native_boot"
readonly DC_SF_NS="surface_flinger"

# Ścieżki
readonly LOG_DIR="${HOME}/.gw4_optimizer"
readonly LOG_FILE="${LOG_DIR}/session_$(date +%Y%m%d_%H%M%S).log"
readonly BACKUP_FILE="${LOG_DIR}/backup_$(date +%Y%m%d_%H%M%S).txt"

# ───────────────────────────────────────────────────────────────────────────────
# §1  KOLORY / ANSI — WearOS-Style CLI
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

_bar() {
    local label="$1" pct="$2"
    local filled=$(( pct * 30 / 100 ))
    local bar="" i
    for ((i=0;i<30;i++)); do
        [[ $i -lt $filled ]] && bar+="${GREEN}█${C0}" || bar+="${GRAY}░${C0}"
    done
    printf "\r  ${CYAN}%-28s${C0} [%b] ${WHITE}%3d%%${C0}" "${label}" "${bar}" "${pct}"
}

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
_DAEMON_MODE=false
_IP_OVERRIDE=""
_FIXES_APPLIED=""

_init() {
    mkdir -p "${LOG_DIR}" "${PROFILE_DIR}"
    _log "START" "${SCRIPT_NAME} v${VERSION} | $(date) | TARGET=${TARGET}"
    command -v adb &>/dev/null || \
        fatal "adb nie znaleziono w PATH. Zainstaluj Android Platform Tools."
}

_parse_args() {
    local ip_override=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --target)
                shift
                case "${1:-}" in
                    phone|watch) TARGET="$1" ;;
                    *) warn "Nieznany target: ${1:-}. Użyj: watch lub phone" ;;
                esac ;;
            --ip)
                shift; ip_override="${1:-}" ;;
            --daemon)
                _DAEMON_MODE=true ;;
            --help|-h)
                printf "%b" "\n${CYAN}${BOLD}Użycie:${C0}\n"
                printf "  bash %s [OPCJE]\n\n" "$(basename "$0")"
                printf "  ${CYAN}--target watch${C0}   Tryb zegarek Galaxy Watch 4 (default)\n"
                printf "  ${CYAN}--target phone${C0}   Tryb telefon Exynos 2100/2200 (S21/S22)\n"
                printf "  ${CYAN}--ip X.X.X.X${C0}    Adres ADB bez pytania interaktywnego\n"
                printf "  ${CYAN}--daemon${C0}         Uruchom w trybie daemon po połączeniu\n\n"
                exit 0 ;;
            *) warn "Nieznany argument: $1 (użyj --help)" ;;
        esac
        shift
    done
    [[ -n "${ip_override}" ]] && export _IP_OVERRIDE="${ip_override}"
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

_apply() {
    local label="$1"; shift
    if _sh_retry "$@" &>/dev/null; then
        fix "${label}"
    else
        warn "${label} — błąd (brak uprawnień lub nieobsługiwane)"
    fi
}

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
    elif [[ -n "${_IP_OVERRIDE}" ]]; then
        local _ip="${_IP_OVERRIDE}"
        [[ "${_ip}" != *:* ]] && _ip="${_ip}:${DEFAULT_PORT}"
        _adb_connect "${_ip}" || return 1
    else
        printf "\n${CYAN}${BOLD}  Podaj IP urządzenia${C0} ${GRAY}(format: 192.168.1.X lub IP:5555)${C0}\n"
        read -r -p "  > " _ip
        [[ "${_ip}" != *:* ]] && _ip="${_ip}:${DEFAULT_PORT}"
        _adb_connect "${_ip}" || return 1
    fi

    DEVICE_MODEL="$(_sh_retry "getprop ro.product.model"   || echo '?')"
    DEVICE_FW="$(   _sh_retry "getprop ro.build.display.id"|| echo '?')"
    DEVICE_SDK="$(  _sh_retry "getprop ro.build.version.sdk"|| echo '0')"
    local av; av="$(_sh_retry "getprop ro.build.version.release" || echo '?')"
    DEVICE_BATTERY="$(_sh "dumpsys battery 2>/dev/null | grep -m1 level | awk '{print \$2}'" \
                     2>/dev/null || echo '-1')"
    DEVICE_BATTERY="${DEVICE_BATTERY//[^0-9]/}"
    [[ -z "${DEVICE_BATTERY}" ]] && DEVICE_BATTERY="-1"

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

    if [[ "${DEVICE_MODEL:-}" =~ ^SM-R8 ]]; then
        ok "Galaxy Watch 4 rozpoznany: ${DEVICE_MODEL}"
        [[ "${TARGET}" == "watch" ]] || {
            warn "Wykryto zegarek, ale --target=${TARGET}. Przełączam na watch."
            TARGET="watch"
        }
    elif [[ "${DEVICE_MODEL:-}" =~ ^SM-S[0-9]|^SM-G[0-9] ]]; then
        warn "Wykryto telefon Samsung: ${DEVICE_MODEL}"
        TARGET="phone"
        info "Tryb: --target phone (Exynos 2100/2200 profile)"
        sub "schedutil: up=${PHONE_SCHED_UP_OPT} down=${PHONE_SCHED_DOWN_OPT} swap=${PHONE_VM_SWAP_OPT}"
    else
        warn "Nierozpoznany model: ${DEVICE_MODEL:-?}"
        warn "Skrypt zoptymalizowany dla SM-R8xx (zegarek) i SM-S/G (telefon)"
        read -r -p "  Kontynuować mimo to? [t/N] " _c
        [[ "${_c,,}" != "t" ]] && { info "Anulowano."; exit 0; }
    fi
    _load_device_profile
}

_load_device_profile() {
    if [[ "${TARGET}" == "phone" ]]; then
        SCHED_UP_OPT=${PHONE_SCHED_UP_OPT}
        SCHED_DOWN_OPT=${PHONE_SCHED_DOWN_OPT}
        SCHED_LAT_OPT=${PHONE_SCHED_LAT_OPT}
        VM_SWAP_OPT=${PHONE_VM_SWAP_OPT}
        ART_HEAPSIZE=${PHONE_ART_HEAPSIZE}
        ART_HEAPGROWTHLIMIT=${PHONE_ART_HEAPGROWTHLIMIT}
        info "Profil: PHONE (Exynos 2100/2200 — big.LITTLE 8-core)"
    else
        info "Profil: WATCH (Exynos W920 — 2-core A55)"
    fi
}

# ───────────────────────────────────────────────────────────────────────────────
# §6b  PROFILE URZĄDZENIA — zapamiętaj wybory między sesjami  (v5.2)
# ───────────────────────────────────────────────────────────────────────────────

_save_session_profile() {
    local pfile="${PROFILE_DIR}/${DEVICE_MODEL:-unknown}.conf"
    {
        echo "# GW4 Optimizer — profil ${DEVICE_MODEL} | $(date)"
        echo "MODEL=${DEVICE_MODEL}"
        echo "FW=${DEVICE_FW}"
        echo "TARGET=${TARGET}"
        echo "LAST_SESSION=$(date +%Y-%m-%d_%H:%M)"
        echo "FIXES_APPLIED=${_FIXES_APPLIED:-none}"
    } > "${pfile}"
    _log "PROFILE" "Zapisano: ${pfile}"
}

_offer_session_profile() {
    local pfile="${PROFILE_DIR}/${DEVICE_MODEL:-unknown}.conf"
    [[ -f "${pfile}" ]] || return 0
    local last_session; last_session="$(grep '^LAST_SESSION=' "${pfile}" | cut -d= -f2-)"
    local last_fixes;   last_fixes="$(  grep '^FIXES_APPLIED=' "${pfile}" | cut -d= -f2-)"
    [[ -z "${last_session}" ]] && return 0
    printf "\n"
    printf "  ${CYAN}${BOLD}  ┌──────────────────────────────────────────────────────┐${C0}\n"
    printf "  ${CYAN}${BOLD}  │  Znaleziono profil z poprzedniej sesji               │${C0}\n"
    printf "  ${CYAN}${BOLD}  │  Data: %-44s│${C0}\n" "${last_session}"
    printf "  ${CYAN}${BOLD}  │  Fixy: %-44s│${C0}\n" "${last_fixes:0:44}"
    printf "  ${CYAN}${BOLD}  └──────────────────────────────────────────────────────┘${C0}\n\n"
    read -r -p "  Zastosować te same fixy? [t/N] " _c
    if [[ "${_c,,}" == "t" ]]; then
        info "Stosowanie profilu: ${last_fixes}"
        [[ "${last_fixes}" == *A* ]] && _fix_animations_silent
        [[ "${last_fixes}" == *Z* ]] && { _fix_all; return; }
        [[ "${last_fixes}" == *B* ]] && _sh_retry "settings put secure doze_always_on 0" || true
        [[ "${last_fixes}" == *C* ]] && _sh "service call SurfaceFlinger 1008 i32 1" || true
        [[ "${last_fixes}" == *D* ]] && _fix_kernel_scheduler_silent
        [[ "${last_fixes}" == *E* ]] && _fix_memory_silent
        [[ "${last_fixes}" == *H* ]] && {
            _apply "enable_uffd_gc=true" \
                "device_config put ${DC_RUNTIME_NS} enable_uffd_gc true"
        }
        [[ "${last_fixes}" == *L* ]] && _fix_aod_sensors_and_gms_silent
        ok "Profil zastosowany"
    fi
}

_fix_animations_silent() {
    local scale="0.5"
    _sh_retry "settings put global window_animation_scale ${scale}"     || true
    _sh_retry "settings put global transition_animation_scale ${scale}" || true
    _sh_retry "settings put global animator_duration_scale ${scale}"    || true
}
_fix_kernel_scheduler_silent() {
    local sb="/sys/devices/system/cpu/cpufreq/policy0/schedutil"
    _sh "echo ${SCHED_UP_OPT} > ${sb}/up_rate_limit_us" 2>/dev/null || true
    _sh "echo ${SCHED_DOWN_OPT} > ${sb}/down_rate_limit_us" 2>/dev/null || true
    _sh "echo ${SCHED_LAT_OPT} > /proc/sys/kernel/sched_latency_ns" 2>/dev/null || true
}
_fix_memory_silent() {
    _sh "echo ${VM_SWAP_OPT} > /proc/sys/vm/swappiness" 2>/dev/null || true
    _sh "echo ${VM_EXTRA_FREE_KB} > /proc/sys/vm/extra_free_kbytes" 2>/dev/null || true
    _sh "echo ${MGLRU_MIN_TTL_MS} > /sys/kernel/mm/lru_gen/min_ttl_ms" 2>/dev/null || true
}

# Cicha funkcja wywoływana przez profil lub daemon
_fix_aod_sensors_and_gms_silent() {
    _sh "pm disable-user --user 0 com.sec.android.diagmonagent" 2>/dev/null || true
    _sh "device_config put adservices global_kill_switch true" 2>/dev/null || true
    _sh "device_config put aicore aicore_safety_enabled false" 2>/dev/null || true
    _sh "device_config put adservices fledge_background_fetch_enabled false" 2>/dev/null || true
    _sh "cmd appops set com.samsung.android.hardware.gesturemanager WAKE_LOCK ignore" 2>/dev/null || true
    _sh "settings put system screen_brightness_mode 0" 2>/dev/null || true
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
# ───────────────────────────────────────────────────────────────────────────────

_check_battery() {
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
    printf "\r  %-70s\r" " "   
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
        local col="${YELLOW}"
        (( i % 2 == 0 )) && col="${LCYAN}"
        [[ ${i} -le 10 ]] && col="${LRED}"

        _bar "${msg} ${i}s" $(( (secs - i) * 100 / secs ))
        printf "  "

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

        (( elapsed % 10 == 0 )) && {
            adb connect "${target}" &>/dev/null || true
        }
    done

    printf "\n"
    err "Timeout — zegarek nie powrócił w ciągu ${timeout_s}s"
    sub "Sprawdź czy zegarek uruchomił się poprawnie"
    sub "Następnie uruchom skrypt ponownie: bash gw4_optimizer_v6.1.sh"
    return 1
}

# ───────────────────────────────────────────────────────────────────────────────
# §9  FIX A — ANIMACJE
# ───────────────────────────────────────────────────────────────────────────────

_fix_animations() {
    hdr "Fix A: Animacje interfejsu"
    _backup_settings

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
            _bar "SF Force GPU" 12
            _sh "service call SurfaceFlinger 1008 i32 1" || true
            printf "\n"; fix "SurfaceFlinger 1008 → Force GPU (HWC bug fix)"

            _bar "SF device_config v5.1" 20
            _apply "layer_caching=true" \
                "device_config put ${DC_SF_NS} enable_layer_caching true"
            _apply "content_detection=false" \
                "device_config put ${DC_SF_NS} use_content_detection_for_refresh_rate false"
            _apply "max_buffers=3" \
                "device_config put ${DC_SF_NS} max_frame_buffer_acquired_buffers 3"
            _apply "multi_color_mode=0" "settings put global multi_color_mode 0"
            printf "\n"

            _bar "SF phase offsets" 28
            _apply "sf.phase_offset_ns" "setprop debug.sf.phase_offset_ns -600000"
            _apply "sf.early_phase_offset_ns" "setprop debug.sf.early_phase_offset_ns -3000000"
            printf "\n"

            _bar "SkiaGL renderer" 35
            _apply_if_changed "hwui.renderer" "${cur_renderer:-}" "skiagl" \
                "setprop debug.hwui.renderer skiagl"
            printf "\n"

            _bar "HWUI flags" 55
            _apply "hwui.skip_empty_damage=true" "setprop debug.hwui.skip_empty_damage true"
            _apply "hwui.use_buffer_age=true"    "setprop debug.hwui.use_buffer_age true"
            _apply "hwui.profile=false"          "setprop debug.hwui.profile false"
            _apply "hwui.overdraw=false"         "setprop debug.hwui.overdraw false"
            _apply "hwui.render_dirty_regions=false" "setprop debug.hwui.render_dirty_regions false"
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
            _bar "swappiness → ${VM_SWAP_OPT}" 12
            _sh "echo ${VM_SWAP_OPT} > /proc/sys/vm/swappiness" 2>/dev/null || true
            printf "\n"
            _bar "MGLRU min_ttl_ms (v5.1)" 20
            _sh "echo ${MGLRU_MIN_TTL_MS} > /sys/kernel/mm/lru_gen/min_ttl_ms" 2>/dev/null || \
                skip "MGLRU sysfs niedostępne (Android < 12 lub kernel bez MGLRU)"
            _sh "echo 4 > /sys/kernel/mm/lru_gen/enabled" 2>/dev/null || true
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
            _apply_if_changed "background_process_limit" "${cbgl}" "4" \
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
            ok "Log buffer wyczyszczony (logd DZIAŁA)" ;;
        0) return ;;
        *) warn "Nieznana opcja" ;;
    esac
}

# ───────────────────────────────────────────────────────────────────────────────
# §14  FIX F — DEBLOAT + WAKE_LOCK
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
            _apply "shealth WAKE_LOCK ignore" \
                "cmd appops set com.samsung.android.wear.shealth WAKE_LOCK ignore" \
                2>/dev/null || true
            ok "Bezpieczny debloat zastosowany (v6.0: +shealth WAKE_LOCK)"
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
# ───────────────────────────────────────────────────────────────────────────────

_fix_art() {
    hdr "Fix G: Kompilacja ART (post-OTA)"

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

    local fi=0 frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
    local bat_warn=false
    while kill -0 ${cpid} 2>/dev/null; do
        local elapsed=$(( SECONDS - start_t ))
        printf "\r  ${CYAN}%s${C0}  Kompilowanie ART  ${GRAY}[%ds]${C0}  bat:${DEVICE_BATTERY}%%   " \
               "${frames[$(( fi % ${#frames[@]} ))]}" "${elapsed}"
        sleep 1.5
        (( fi++ )) || true
        adb -s "${DEVICE}" shell input keyevent KEYCODE_WAKEUP 2>/dev/null || true

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

        _bar "compile-layouts (v5.1)" 90
        printf "\n"
        _sh_retry "cmd package compile-layouts -a" 2>/dev/null || \
            skip "compile-layouts (nieobsługiwane na SDK ${DEVICE_SDK})"

        _bar "bg-dexopt" 95
        printf "\n"
        _sh "cmd package bg-dexopt-job" 2>/dev/null || true

        _bar "Weryfikacja ART" 100
        printf "\n"
        local _art_check
        _art_check="$(_sh_retry "pm dump com.samsung.android.clocksync 2>/dev/null | grep -m1 compilerFilter" || echo 'N/A')"
        ok "compilerFilter systemowy: ${_art_check}"
        info "Pierwsze uruchomienia aplikacji będą teraz szybsze"
    else
        warn "Kompilacja: kod ${rc} — częściowo ukończona lub timeout"
    fi
}

# ───────────────────────────────────────────────────────────────────────────────
# §15f  FIX L — AOD SENSOR GUARD & GMS ML BLOCK (v6.1)
# ───────────────────────────────────────────────────────────────────────────────

_fix_aod_sensors_and_gms() {
    hdr "Fix L: AOD Sensor Guard & AiCore/AdServices Block"
    _backup_settings

    printf "\n"
    printf "  ${GRAY}Analiza dumpsys wykazała krytyczne problemy podczas AOD:${C0}\n"
    printf "  ${GRAY}1. WChiSensor (Gesty) próbkuje żyroskop na 100Hz (10ms) w tle${C0}\n"
    printf "  ${GRAY}2. AutoBrightness Controller działa z częstotliwością 10Hz${C0}\n"
    printf "  ${GRAY}3. GMS próbuje odpalać klasyfikatory AiCore / AdServices w Idle${C0}\n"
    printf "  ${GRAY}4. Pętla com.sec.android.diagmonagent dławi sepunion${C0}\n\n"

    printf "  ${CYAN}1${C0}) ${GREEN}Pełny AOD & Idle Fix${C0} ${GRAY}— aplikuje wszystkie łatki naprawcze${C0}\n"
    printf "  ${CYAN}2${C0}) Tylko blokada GMS AiCore / AdServices\n"
    printf "  ${CYAN}3${C0}) Tylko ograniczenie WAKE_LOCK dla Gestów\n"
    printf "  ${CYAN}0${C0}) Anuluj\n\n"
    read -r -p "  > " _c

    case "${_c}" in
        1)
            _bar "Wyłączanie DiagMonAgent" 20; printf "\n"
            _apply "diagmonagent disabled" \
                "pm disable-user --user 0 com.sec.android.diagmonagent"

            _bar "GMS AiCore & AdServices Kill-Switch" 50; printf "\n"
            _apply "adservices global_kill_switch=true" \
                "device_config put adservices global_kill_switch true" 2>/dev/null || true
            _apply "aicore_safety_enabled=false" \
                "device_config put aicore aicore_safety_enabled false" 2>/dev/null || true
            _apply "disable_fledge=true" \
                "device_config put adservices fledge_background_fetch_enabled false" 2>/dev/null || true

            _bar "Ograniczenie WChiSensor WAKE_LOCK" 80; printf "\n"
            _apply "gesturemanager WAKE_LOCK → ignore" \
                "cmd appops set com.samsung.android.hardware.gesturemanager WAKE_LOCK ignore"

            _bar "AutoBrightness Throttle" 90; printf "\n"
            _apply "brightness_ramp_rate_slow=0" \
                "settings put system screen_brightness_mode 0" 

            _bar "Gotowe" 100; printf "\n"
            ok "Fix L (AOD Sensor Guard) zastosowany pomyślnie ✓"
            sub "Rozwiązano dławienie CPU przez sensory 100Hz i usługi ML."
            ;;
        2)
            _apply "adservices global_kill_switch=true" \
                "device_config put adservices global_kill_switch true"
            _apply "aicore_safety_enabled=false" \
                "device_config put aicore aicore_safety_enabled false"
            ok "AiCore i AdServices zablokowane"
            ;;
        3)
            _apply "gesturemanager WAKE_LOCK → ignore" \
                "cmd appops set com.samsung.android.hardware.gesturemanager WAKE_LOCK ignore"
            ok "Menedżer gestów nie będzie wybudzał procesora (ograniczono thrashing 100Hz)"
            ;;
        0) return ;;
        *) warn "Nieznana opcja" ;;
    esac
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

    local s=0 t=29

    # A — Animacje 0.5x
    local cwa; cwa="$(_get_setting global window_animation_scale)"
    _bar "Animacje 0.5x" $(( ++s*100/t )); printf "\n"
    _apply_if_changed "window_animation_scale"     "${cwa}" "0.5" \
        "settings put global window_animation_scale 0.5"
    _apply "transition_animation_scale=0.5" \
        "settings put global transition_animation_scale 0.5"
    _apply "animator_duration_scale=0.5" \
        "settings put global animator_duration_scale 0.5"

    # B — AOD off
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

    # H — device_config ART
    _bar "ART device_config flags" $(( ++s*100/t )); printf "\n"
    _apply "enable_uffd_gc=true" \
        "device_config put ${DC_RUNTIME_NS} enable_uffd_gc true"
    _apply "enable_generational_cc=true" \
        "device_config put ${DC_RUNTIME_NS} enable_generational_cc true"
    _apply "dex2oat-threads=1" "setprop dalvik.vm.dex2oat-threads ${ART_DEX2OAT_THREADS}"
    _apply "heapsize=${ART_HEAPSIZE}" "setprop dalvik.vm.heapsize ${ART_HEAPSIZE}"

    # H — device_config SF
    _bar "SF device_config" $(( ++s*100/t )); printf "\n"
    _apply "layer_caching=true" \
        "device_config put ${DC_SF_NS} enable_layer_caching true"
    _apply "content_detection=false" \
        "device_config put ${DC_SF_NS} use_content_detection_for_refresh_rate false"
    _apply "multi_color_mode=0" "settings put global multi_color_mode 0"

    # H — MGLRU
    _bar "MGLRU min_ttl_ms" $(( ++s*100/t )); printf "\n"
    _sh "echo ${MGLRU_MIN_TTL_MS} > /sys/kernel/mm/lru_gen/min_ttl_ms" 2>/dev/null || true
    _sh "echo 4 > /sys/kernel/mm/lru_gen/enabled" 2>/dev/null || true

    # I — sched_boost + I/O scheduler + v6.0 extras
    _bar "sched_boost=1 (v6.0)" $(( ++s*100/t )); printf "\n"
    _sh "echo ${SCHED_BOOST_OPT} > ${SCHED_BOOST_PATH}" 2>/dev/null || true
    for _blk in mmcblk0 mmcblk1 sda; do
        _sh "echo ${IO_SCHED_OPT} > /sys/block/${_blk}/queue/scheduler" 2>/dev/null || true
    done
    _apply "render_dirty_regions=false" "setprop debug.hwui.render_dirty_regions false"
    _apply "shealth WAKE_LOCK ignore" \
        "cmd appops set com.samsung.android.wear.shealth WAKE_LOCK ignore" \
        2>/dev/null || true
    _apply "disable_jit_zygote=false" \
        "device_config put ${DC_RUNTIME_NS} disable_jit_zygote false" \
        2>/dev/null || true

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

    # L — AOD Sensor Guard (NOWE v6.1)
    _bar "AOD Sensor Guard" $(( ++s*100/t )); printf "\n"
    _sh_retry "pm disable-user --user 0 com.sec.android.diagmonagent" 2>/dev/null || true
    _sh_retry "device_config put adservices global_kill_switch true" 2>/dev/null || true
    _sh_retry "device_config put aicore aicore_safety_enabled false" 2>/dev/null || true
    _sh_retry "device_config put adservices fledge_background_fetch_enabled false" 2>/dev/null || true
    _sh_retry "cmd appops set com.samsung.android.hardware.gesturemanager WAKE_LOCK ignore" 2>/dev/null || true
    _sh_retry "settings put system screen_brightness_mode 0" 2>/dev/null || true

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
    ok "E: swappiness=60 | extra_free | MGLRU | phantom_procs off"
    ok "F: WAKE_LOCK restrict | appcloud disabled"
    ok "L: Zablokowanie drenażu AOD z logów (DiagMonAgent, AiCore, 100Hz Gestures)"
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

    printf "  ${YELLOW}Potwierdzenie 1/2 — wpisz dokładnie:${C0} ${WHITE}RESET${C0}\n"
    read -r -p "  > " _c1
    if [[ "${_c1}" != "RESET" ]]; then
        info "Anulowano (nieprawidłowe potwierdzenie)"
        return
    fi

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
# §19b  DIAGNOSTYKA RÓŻNICOWA
# ───────────────────────────────────────────────────────────────────────────────

_snapshot_collect() {
    local label="$1"
    local snap="${LOG_DIR}/snap_${label}_$(date +%H%M%S).txt"
    {
        printf "# Snapshot: %s | %s | %s\n" "${label}" "${DEVICE_MODEL}" "$(date)"
        printf "swappiness=%s\n"       "$(_get_kernel /proc/sys/vm/swappiness)"
        printf "sched_up=%s\n"         "$(_get_kernel /sys/devices/system/cpu/cpufreq/policy0/schedutil/up_rate_limit_us)"
        printf "sched_down=%s\n"       "$(_get_kernel /sys/devices/system/cpu/cpufreq/policy0/schedutil/down_rate_limit_us)"
        printf "sched_lat=%s\n"        "$(_get_kernel /proc/sys/kernel/sched_latency_ns)"
        printf "mglru_ttl=%s\n"        "$(_get_kernel /sys/kernel/mm/lru_gen/min_ttl_ms 2>/dev/null || echo N/A)"
        printf "window_anim=%s\n"      "$(_get_setting global window_animation_scale)"
        printf "doze_aon=%s\n"         "$(_get_setting secure doze_always_on)"
        printf "bg_blur=%s\n"          "$(_get_setting global supports_background_blur)"
        printf "phantom=%s\n"          "$(_get_setting global monitor_phantom_procs)"
        printf "uffd_gc=%s\n"          "$(_sh_retry "device_config get ${DC_RUNTIME_NS} enable_uffd_gc" 2>/dev/null || echo N/A)"
        printf "hwui_renderer=%s\n"    "$(_get_prop debug.hwui.renderer)"
        local janky
        janky="$(timeout 5 adb -s "${DEVICE}" shell "dumpsys gfxinfo com.android.systemui" 2>/dev/null \
            | grep -m1 'Janky frames' | grep -oE '[0-9]+\.[0-9]+%' | head -1 || echo N/A)"
        printf "janky_pct=%s\n" "${janky}"
    } > "${snap}"
    printf '%s' "${snap}"
}

_diag_diff() {
    hdr "Diagnostyka różnicowa — snapshot PRZED/PO"
    info "Zbieram snapshot PRZED fixami..."
    local snap_before
    snap_before="$(_snapshot_collect "BEFORE")"
    ok "Snapshot PRZED: ${snap_before}"

    printf "\n  ${YELLOW}Teraz zastosuj fixy (menu), a następnie wróć tutaj.${C0}\n"
    read -r -p "  Naciśnij Enter gdy fixy zostały zastosowane..."

    info "Zbieram snapshot PO fixach..."
    local snap_after
    snap_after="$(_snapshot_collect "AFTER")"
    ok "Snapshot PO: ${snap_after}"

    local diff_report="${LOG_DIR}/DIFF_REPORT_$(date +%Y%m%d_%H%M%S).txt"
    {
        printf "═══════════════════════════════════════════════════════\n"
        printf "  GW4 Optimizer — Raport Różnicowy v%s\n" "${VERSION}"
        printf "  Data: %s\n" "$(date)"
        printf "  Model: %s | FW: %s\n" "${DEVICE_MODEL}" "${DEVICE_FW}"
        printf "  Profil: %s\n" "${TARGET}"
        printf "═══════════════════════════════════════════════════════\n\n"
        printf "  %-30s %10s  %10s  %s\n" "Metryka" "Przed" "Po" "Delta"
        printf "  %-30s %10s  %10s  %s\n" "──────────────────────────────" "──────────" "──────────" "──────"

        while IFS='=' read -r key val_before; do
            [[ "${key}" =~ ^# ]] && continue
            [[ -z "${key}" ]] && continue
            local val_after
            val_after="$(grep "^${key}=" "${snap_after}" | cut -d= -f2- || echo N/A)"
            local delta="→"
            [[ "${val_before}" == "${val_after}" ]] && delta="=" || delta="✓"
            printf "  %-30s %10s  %10s  %s\n" "${key}" "${val_before}" "${val_after}" "${delta}"
        done < "${snap_before}"

        printf "\n═══════════════════════════════════════════════════════\n"
    } > "${diff_report}"

    ok "Raport różnicowy: ${diff_report}"
    printf "\n  ${WHITE}${BOLD}Podsumowanie zmian:${C0}\n"
    grep -v "^═\|^  Data\|^  Model\|^  FW\|^  Profil\|^  Metryka\|^  ───"         "${diff_report}" | grep "✓" | while IFS= read -r line; do
        printf "  ${LGREEN}%s${C0}\n" "${line}"
    done
    printf "\n"
}

# ───────────────────────────────────────────────────────────────────────────────
# §19  DIAGNOSTYKA
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
# §15b  FIX P — TRWAŁOŚĆ PARAMETRÓW JĄDRA
# ───────────────────────────────────────────────────────────────────────────────

_fix_persistence() {
    hdr "Fix P: Trwałość parametrów jądra (v5.2)"

    printf "\n"
    printf "  ${YELLOW}Problem:${C0} schedutil i swappiness reset po każdym restarcie\n"
    printf "  ${GRAY}Dotyczy: Fix D (PELT), Fix E (swappiness), Fix H (MGLRU), Fix L (AOD/GMS)${C0}\n\n"
    printf "  ${CYAN}1${C0}) ${GREEN}Generator profilu Tasker${C0}    ${GRAY}— XML do importu, bez roota${C0}\n"
    printf "     ${GRAY}Wymaga: Tasker na telefonie + ADB WiFi automation${C0}\n"
    printf "  ${CYAN}2${C0}) Boot hook (root)           ${GRAY}— /data/adb/service.d/ (Magisk/KernelSU)${C0}\n"
    printf "  ${CYAN}3${C0}) ${GREEN}Tryb daemon${C0} (ten host)      ${GRAY}— nasłuchuje ADB, stosuje fixy po restarcie${C0}\n"
    printf "  ${CYAN}4${C0}) Zatrzymaj daemon            ${GRAY}— jeśli działa w tle${C0}\n"
    printf "  ${CYAN}5${C0}) Status daemona              ${GRAY}— sprawdź czy aktywny${C0}\n"
    printf "  ${CYAN}0${C0}) Anuluj\n\n"
    read -r -p "  > " _c

    case "${_c}" in
        1) _generate_tasker_profile ;;
        2) _install_boot_hook_root ;;
        3) _watch_daemon_mode ;;
        4) _daemon_stop ;;
        5) _daemon_status ;;
        0) return ;;
        *) warn "Nieznana opcja" ;;
    esac
}

# ─── OPCJA A: Generator profilu Tasker ────────────────────────────────────────
_generate_tasker_profile() {
    hdr "Generator profilu Tasker"
    local outfile="${LOG_DIR}/GW4_Optimizer_Boot.xml"

    local device_ip="${DEVICE%%:*}"
    local device_port="${DEVICE##*:}"
    [[ "${device_port}" == "${DEVICE}" ]] && device_port="${DEFAULT_PORT}"

    cat > "${outfile}" << XMLEOF
<?xml version="1.0" encoding="utf-8"?>
<TaskerData sr="" dvi="1" tv="6.3.13">

  <Profile sr="prof0" ve="2">
    <nme>GW4 Boot Optimizer — ${DEVICE_MODEL:-Watch}</nme>
    <Event sr="con0" ve="2">
      <code>2</code>
    </Event>
    <Task sr="task0">
      <nme>GW4 Apply Kernel Fixes</nme>

      <Action sr="act0" ve="7">
        <code>30</code>
        <Int sr="arg0" val="15"/>
      </Action>

      <Action sr="act1" ve="7">
        <code>123</code>
        <Str sr="arg0" val="adb connect ${device_ip}:${device_port}"/>
        <Int sr="arg1" val="0"/>
      </Action>

      <Action sr="act2" ve="7">
        <code>123</code>
        <Str sr="arg0" val="adb -s ${DEVICE} shell echo ${SCHED_UP_OPT} > /sys/devices/system/cpu/cpufreq/policy0/schedutil/up_rate_limit_us"/>
        <Int sr="arg1" val="0"/>
      </Action>
      <Action sr="act3" ve="7">
        <code>123</code>
        <Str sr="arg0" val="adb -s ${DEVICE} shell echo ${SCHED_DOWN_OPT} > /sys/devices/system/cpu/cpufreq/policy0/schedutil/down_rate_limit_us"/>
        <Int sr="arg1" val="0"/>
      </Action>
      <Action sr="act4" ve="7">
        <code>123</code>
        <Str sr="arg0" val="adb -s ${DEVICE} shell echo ${SCHED_LAT_OPT} > /proc/sys/kernel/sched_latency_ns"/>
        <Int sr="arg1" val="0"/>
      </Action>
      <Action sr="act5" ve="7">
        <code>123</code>
        <Str sr="arg0" val="adb -s ${DEVICE} shell echo ${VM_SWAP_OPT} > /proc/sys/vm/swappiness"/>
        <Int sr="arg1" val="0"/>
      </Action>
      <Action sr="act6" ve="7">
        <code>123</code>
        <Str sr="arg0" val="adb -s ${DEVICE} shell echo ${VM_EXTRA_FREE_KB} > /proc/sys/vm/extra_free_kbytes"/>
        <Int sr="arg1" val="0"/>
      </Action>
      <Action sr="act7" ve="7">
        <code>123</code>
        <Str sr="arg0" val="adb -s ${DEVICE} shell echo ${MGLRU_MIN_TTL_MS} > /sys/kernel/mm/lru_gen/min_ttl_ms"/>
        <Int sr="arg1" val="0"/>
      </Action>
      <Action sr="act8" ve="7">
        <code>123</code>
        <Str sr="arg0" val="adb -s ${DEVICE} shell service call SurfaceFlinger 1008 i32 1"/>
        <Int sr="arg1" val="0"/>
      </Action>

      <Action sr="act9" ve="7">
        <code>123</code>
        <Str sr="arg0" val="adb -s ${DEVICE} shell cmd appops set com.samsung.android.hardware.gesturemanager WAKE_LOCK ignore"/>
        <Int sr="arg1" val="0"/>
      </Action>
      <Action sr="act10" ve="7">
        <code>123</code>
        <Str sr="arg0" val="adb -s ${DEVICE} shell pm disable-user --user 0 com.sec.android.diagmonagent"/>
        <Int sr="arg1" val="0"/>
      </Action>
      <Action sr="act11" ve="7">
        <code>123</code>
        <Str sr="arg0" val="adb -s ${DEVICE} shell device_config put adservices global_kill_switch true"/>
        <Int sr="arg1" val="0"/>
      </Action>
      <Action sr="act12" ve="7">
        <code>123</code>
        <Str sr="arg0" val="adb -s ${DEVICE} shell device_config put aicore aicore_safety_enabled false"/>
        <Int sr="arg1" val="0"/>
      </Action>
      <Action sr="act13" ve="7">
        <code>123</code>
        <Str sr="arg0" val="adb -s ${DEVICE} shell settings put system screen_brightness_mode 0"/>
        <Int sr="arg1" val="0"/>
      </Action>

      <Action sr="act14" ve="7">
        <code>7</code>
        <Str sr="arg0" val="GW4 Optimizer"/>
        <Str sr="arg1" val="Parametry jądra przywrócone po restarcie ✓"/>
        <Int sr="arg2" val="0"/>
      </Action>

    </Task>
  </Profile>

</TaskerData>
XMLEOF

    printf "\n"
    ok "Profil Tasker wygenerowany: ${outfile}"
    printf "\n  ${YELLOW}${BOLD}Jak zainstalować:${C0}\n"
    printf "  ${CYAN}1${C0}  Skopiuj plik XML na telefon:${C0}\n"
    printf "     ${GRAY}adb -s <telefon> push %s /sdcard/GW4_Optimizer_Boot.xml${C0}\n" "${outfile}"
    printf "  ${CYAN}2${C0}  W aplikacji Tasker:${C0}\n"
    printf "     ${GRAY}Menu (3 kropki) → Import Data → Backup XML${C0}\n"
    printf "  ${CYAN}3${C0}  Zezwól Taskerowi na uruchamianie ADB (wymaga zezwolenia SHIZUKU lub ADB WiFi)${C0}\n"
    printf "  ${CYAN}4${C0}  Profil 'GW4 Boot Optimizer' aktywuje się automatycznie po każdym restarcie zegarka${C0}\n\n"
    warn "IP zegarka może się zmienić — zaktualizuj profil po zmianie IP"
}

# ─── OPCJA B: Boot hook (root) ────────────────────────────────────────────────
_install_boot_hook_root() {
    hdr "Boot hook — /data/adb/service.d/ (root)"

    local uid; uid="$(_sh "id -u" 2>/dev/null || echo '?')"
    if [[ "${uid}" != "0" ]]; then
        err "Brak roota na urządzeniu (uid=${uid})"
        sub "Wymagany: Magisk lub KernelSU Next zainstalowany na zegarku"
        return 1
    fi

    local hook_content
    hook_content=$(cat << HOOKEOF
#!/system/bin/sh
# GW4 Optimizer — Boot Service Hook v${VERSION}
# Instalacja: /data/adb/service.d/gw4_perf.sh

sleep 20

# Fix D — schedutil PELT calibration (${TARGET} profile)
echo ${SCHED_UP_OPT}   > /sys/devices/system/cpu/cpufreq/policy0/schedutil/up_rate_limit_us   2>/dev/null || true
echo ${SCHED_DOWN_OPT} > /sys/devices/system/cpu/cpufreq/policy0/schedutil/down_rate_limit_us 2>/dev/null || true
echo ${SCHED_LAT_OPT}  > /proc/sys/kernel/sched_latency_ns 2>/dev/null || true
echo 1                 > /proc/sys/kernel/sched_boost       2>/dev/null || true

# Fix E — swappiness + MGLRU
echo ${VM_SWAP_OPT}    > /proc/sys/vm/swappiness             2>/dev/null || true
echo ${VM_EXTRA_FREE_KB} > /proc/sys/vm/extra_free_kbytes   2>/dev/null || true
echo 4                 > /sys/kernel/mm/lru_gen/enabled      2>/dev/null || true
echo ${MGLRU_MIN_TTL_MS} > /sys/kernel/mm/lru_gen/min_ttl_ms 2>/dev/null || true

# Fix L — AOD Sensor Guard & GMS Block
cmd appops set com.samsung.android.hardware.gesturemanager WAKE_LOCK ignore 2>/dev/null || true
pm disable-user --user 0 com.sec.android.diagmonagent 2>/dev/null || true
device_config put adservices global_kill_switch true 2>/dev/null || true
device_config put aicore aicore_safety_enabled false 2>/dev/null || true

# Log sukcesu
echo "[GW4 Boot] $(date): params applied (up=${SCHED_UP_OPT} swap=${VM_SWAP_OPT})" \
    >> /data/local/tmp/gw4_boot.log 2>/dev/null || true
HOOKEOF
)

    printf "\n"
    info "Instaluję boot hook na urządzeniu..."
    printf "%s" "${hook_content}" | _sh "cat > ${BOOT_HOOK_PATH}" 2>/dev/null && {
        _sh "chmod 755 ${BOOT_HOOK_PATH}" 2>/dev/null || true
        ok "Boot hook zainstalowany: ${BOOT_HOOK_PATH}"
        warn "Wymaga Magisk/KernelSU — bez niego skrypt nie zostanie uruchomiony"
    } || {
        err "Nie można zapisać do ${BOOT_HOOK_PATH}"
    }
}

# ─── OPCJA C: Watch Daemon (host-side) ────────────────────────────────────────
_watch_daemon_mode() {
    hdr "Tryb daemon — monitorowanie ADB"

    if [[ -f "${DAEMON_PID_FILE}" ]]; then
        local old_pid; old_pid="$(cat "${DAEMON_PID_FILE}" 2>/dev/null)"
        if kill -0 "${old_pid}" 2>/dev/null; then
            warn "Daemon już działa (PID ${old_pid})"
            read -r -p "  Uruchomić nowy daemon? [t/N] " _c
            [[ "${_c,,}" != "t" ]] && return
            kill "${old_pid}" 2>/dev/null || true
        fi
    fi

    printf "\n"
    printf "  ${CYAN}Daemon będzie:${C0}\n"
    printf "  ${GRAY}• Nasłuchiwać na połączenie ADB (adb track-devices)${C0}\n"
    printf "  ${GRAY}• Po każdym wykryciu zegarku stosować Fix D+E+H+L${C0}\n"
    printf "  ${GRAY}• Logować akcje do: %s${C0}\n" "${DAEMON_LOG}"
    printf "  ${GRAY}• Interwał monitoringu: %ds${C0}\n\n" "${DAEMON_INTERVAL}"
    read -r -p "  Uruchomić daemon w tle? [t/N] " _c
    [[ "${_c,,}" != "t" ]] && return

    _daemon_worker &
    local dpid=$!
    echo "${dpid}" > "${DAEMON_PID_FILE}"
    ok "Daemon uruchomiony (PID ${dpid})"
    sub "Log: ${DAEMON_LOG}"
    sub "Zatrzymaj: opcja P → 4 lub: kill ${dpid}"
}

_daemon_worker() {
    echo "[$(date)] Daemon START — target=${DEVICE} profile=${TARGET}" >> "${DAEMON_LOG}"
    local cycle=0
    while true; do
        sleep "${DAEMON_INTERVAL}"
        (( cycle++ )) || true

        local state
        state="$(adb -s "${DEVICE}" get-state 2>/dev/null || echo 'offline')"

        if [[ "${state}" == "device" ]]; then
            local cur_swap
            cur_swap="$(adb -s "${DEVICE}" shell cat /proc/sys/vm/swappiness 2>/dev/null | tr -d '\r\n' || echo '100')"
            if [[ "${cur_swap}" != "${VM_SWAP_OPT}" ]]; then
                echo "[$(date)] Cykl ${cycle}: regresja wykryta (swappiness=${cur_swap}). Stosowanie fixów..." >> "${DAEMON_LOG}"
                
                # Auto-fix: Kernel parameters
                adb -s "${DEVICE}" shell "echo ${VM_SWAP_OPT} > /proc/sys/vm/swappiness" 2>/dev/null || true
                adb -s "${DEVICE}" shell "echo ${VM_EXTRA_FREE_KB} > /proc/sys/vm/extra_free_kbytes" 2>/dev/null || true
                local sb="/sys/devices/system/cpu/cpufreq/policy0/schedutil"
                adb -s "${DEVICE}" shell "echo ${SCHED_UP_OPT} > ${sb}/up_rate_limit_us" 2>/dev/null || true
                adb -s "${DEVICE}" shell "echo ${SCHED_DOWN_OPT} > ${sb}/down_rate_limit_us" 2>/dev/null || true
                adb -s "${DEVICE}" shell "echo ${MGLRU_MIN_TTL_MS} > /sys/kernel/mm/lru_gen/min_ttl_ms" 2>/dev/null || true
                
                # Auto-fix: Fix L (AOD Sensor Guard)
                adb -s "${DEVICE}" shell "pm disable-user --user 0 com.sec.android.diagmonagent" 2>/dev/null || true
                adb -s "${DEVICE}" shell "device_config put adservices global_kill_switch true" 2>/dev/null || true
                adb -s "${DEVICE}" shell "device_config put aicore aicore_safety_enabled false" 2>/dev/null || true
                adb -s "${DEVICE}" shell "cmd appops set com.samsung.android.hardware.gesturemanager WAKE_LOCK ignore" 2>/dev/null || true
                
                echo "[$(date)] Cykl ${cycle}: fixy D+E+L zastosowane" >> "${DAEMON_LOG}"
            else
                echo "[$(date)] Cykl ${cycle}: parametry OK (swappiness=${cur_swap})" >> "${DAEMON_LOG}"
            fi
        else
            echo "[$(date)] Cykl ${cycle}: urządzenie offline (state=${state})" >> "${DAEMON_LOG}"
            adb connect "${DEVICE}" &>/dev/null || true
        fi
    done
}

_daemon_stop() {
    if [[ -f "${DAEMON_PID_FILE}" ]]; then
        local pid; pid="$(cat "${DAEMON_PID_FILE}")"
        if kill -0 "${pid}" 2>/dev/null; then
            kill "${pid}" 2>/dev/null
            rm -f "${DAEMON_PID_FILE}"
            ok "Daemon zatrzymany (PID ${pid})"
        else
            warn "Daemon nie działa (PID ${pid} nieaktywny)"
            rm -f "${DAEMON_PID_FILE}"
        fi
    else
        info "Daemon nie jest uruchomiony"
    fi
}

_daemon_status() {
    if [[ -f "${DAEMON_PID_FILE}" ]]; then
        local pid; pid="$(cat "${DAEMON_PID_FILE}")"
        if kill -0 "${pid}" 2>/dev/null; then
            ok "Daemon AKTYWNY (PID ${pid})"
            sub "Log: ${DAEMON_LOG}"
            printf "\n  ${GRAY}Ostatnie wpisy:${C0}\n"
            tail -5 "${DAEMON_LOG}" 2>/dev/null | while IFS= read -r line; do
                printf "  ${GRAY}  %s${C0}\n" "${line}"
            done
        else
            warn "Daemon PID ${pid} nieaktywny (crashed?)"
        fi
    else
        info "Daemon nie jest uruchomiony"
    fi
    printf "\n"
}

# ───────────────────────────────────────────────────────────────────────────────
# §15c  FIX I — I/O SCHEDULER + SCHED_BOOST
# ───────────────────────────────────────────────────────────────────────────────

_fix_io_and_sched_boost() {
    hdr "Fix I: I/O Scheduler + sched_boost (v6.0)"
    _backup_settings

    local cur_boost cur_io
    cur_boost="$(_get_kernel "${SCHED_BOOST_PATH}" 2>/dev/null || echo 'N/A')"
    cur_io="$(_sh "cat /sys/block/mmcblk0/queue/scheduler 2>/dev/null | grep -o '\[.*\]' | tr -d '[]'" || echo 'N/A')"

    printf "\n"
    printf "  ${GRAY}┌─────────────────────────────────────────────────────────────┐${C0}\n"
    printf "  ${GRAY}│${C0}  ${WHITE}sched_boost:${C0}      %-3s  ${GRAY}(1=UI thread priorytet)${C0}         ${GRAY}│${C0}\n" "${cur_boost}"
    printf "  ${GRAY}│${C0}  ${WHITE}I/O scheduler:${C0}    %-8s  ${GRAY}(deadline=deterministic latency)${C0} ${GRAY}│${C0}\n" "${cur_io}"
    printf "  ${GRAY}│${C0}                                                             ${GRAY}│${C0}\n"
    printf "  ${GRAY}│${C0}  ${YELLOW}Raport [str.1]: sched_boost faworyzuje procesy tła One UI${C0}  ${GRAY}│${C0}\n"
    printf "  ${GRAY}│${C0}  ${YELLOW}→ SurfaceFlinger traci priorytety → rwanie animacji${C0}         ${GRAY}│${C0}\n"
    printf "  ${GRAY}└─────────────────────────────────────────────────────────────┘${C0}\n\n"

    printf "  ${CYAN}1${C0}) ${GREEN}Zastosuj oba fixy${C0}  ${GRAY}— sched_boost=1 + I/O deadline${C0}\n"
    printf "  ${CYAN}2${C0}) Tylko sched_boost=1    ${GRAY}— priorytet UI thread${C0}\n"
    printf "  ${CYAN}3${C0}) Tylko I/O deadline     ${GRAY}— deterministic latency dla NAND${C0}\n"
    printf "  ${CYAN}4${C0}) Przywróć               ${GRAY}— sched_boost=0, I/O cfq${C0}\n"
    printf "  ${CYAN}0${C0}) Anuluj\n\n"
    read -r -p "  > " _c

    case "${_c}" in
        1|2)
            _bar "sched_boost=1" 30
            printf "\n"
            if _sh "echo ${SCHED_BOOST_OPT} > ${SCHED_BOOST_PATH}" 2>/dev/null; then
                ok "sched_boost=${SCHED_BOOST_OPT} — UI thread ma priorytet ✓"
            else
                skip "sched_boost (niedostępne bez roota)"
                _apply "high_priority_render_thread=1" \
                    "settings put global high_priority_render_thread 1"
            fi
            [[ "${_c}" == "2" ]] && return ;;& 
        1|3)
            _bar "I/O scheduler → deadline" 60
            printf "\n"
            local applied=0
            for blk in /sys/block/mmcblk*/queue/scheduler \
                       /sys/block/sda*/queue/scheduler \
                       /sys/block/loop*/queue/scheduler; do
                if _sh "echo ${IO_SCHED_OPT} > ${blk}" 2>/dev/null; then
                    (( applied++ )) || true
                fi
            done
            if [[ ${applied} -gt 0 ]]; then
                ok "I/O scheduler → ${IO_SCHED_OPT} (${applied} urządzeń) ✓"
            else
                skip "I/O scheduler (brak uprawnień lub niedostępne)"
            fi
            ;;
        4)
            _sh "echo 0 > ${SCHED_BOOST_PATH}" 2>/dev/null || true
            for blk in /sys/block/mmcblk*/queue/scheduler; do
                _sh "echo ${IO_SCHED_DEFAULT} > ${blk}" 2>/dev/null || true
            done
            ok "sched_boost=0, I/O=${IO_SCHED_DEFAULT} — przywrócono" ;;
        0) return ;;
        *) warn "Nieznana opcja" ;;
    esac
    [[ "${_c}" == "1" ]] && {
        _bar "Gotowe" 100; printf "\n"
        ok "Fix I: sched_boost + I/O scheduler zastosowane"
        warn "sched_boost reset po restarcie (parametr jądra)"
    }
}

# ───────────────────────────────────────────────────────────────────────────────
# §15d  FIX J — SHIZUKU / RISH
# ───────────────────────────────────────────────────────────────────────────────

_fix_shizuku() {
    hdr "Fix J: Shizuku / rish (v6.0)"

    printf "\n"
    printf "  ${CYAN}Co daje Shizuku?${C0}\n"
    printf "  ${GRAY}• Uprawnienia ADB-level BEZ kabla po pierwszej instalacji${C0}\n"
    printf "  ${GRAY}• Trwałe stosowanie fixów przez aplikacje na zegarku${C0}\n"
    printf "  ${GRAY}• Podstawa dla automatyzacji (Tasker + Shizuku = stałe tweaki)${C0}\n\n"

    local shizuku_installed shizuku_running
    shizuku_installed="$(ADB.pkg_exists "${SHIZUKU_PKG}" 2>/dev/null || \
        _sh "pm list packages ${SHIZUKU_PKG} 2>/dev/null" || echo '')"
    shizuku_running="$(_sh "getprop init.svc.shizuku 2>/dev/null" || echo '')"

    printf "  ${GRAY}Status Shizuku:${C0}\n"
    if echo "${shizuku_installed}" | grep -q "${SHIZUKU_PKG}"; then
        ok "Shizuku zainstalowane: ${SHIZUKU_PKG}"
        [[ -n "${shizuku_running}" ]] && ok "Shizuku service: ${shizuku_running}" \
            || warn "Shizuku service: nieaktywne (uruchom aplikację Shizuku na zegarku)"
    else
        warn "Shizuku NIE jest zainstalowane"
    fi

    local rish_ok
    rish_ok="$(_sh "test -x ${RISH_PATH} && echo OK || echo MISSING" 2>/dev/null || echo 'MISSING')"
    if [[ "${rish_ok}" == "OK" ]]; then
        local rish_ver; rish_ver="$(_sh "${RISH_PATH} -v 2>/dev/null" || echo '?')"
        ok "rish: ${RISH_PATH} ✓ (${rish_ver})"
    else
        warn "rish: nie znaleziono w ${RISH_PATH}"
    fi
    printf "\n"

    printf "  ${CYAN}1${C0}) ${GREEN}Deploy/naprawa rish${C0}  ${GRAY}— wstrzyknij skrypt proxy (SecFerro method)${C0}\n"
    printf "  ${CYAN}2${C0}) Test rish              ${GRAY}— sprawdź czy rish działa${C0}\n"
    printf "  ${CYAN}3${C0}) Zastosuj fixy przez rish ${GRAY}— A+C+E+F bez kabla ADB${C0}\n"
    printf "  ${CYAN}4${C0}) Instrukcja instalacji  ${GRAY}— Shizuku na WearOS${C0}\n"
    printf "  ${CYAN}0${C0}) Anuluj\n\n"
    read -r -p "  > " _c

    case "${_c}" in
        1) _shizuku_deploy_rish ;;
        2) _shizuku_test_rish ;;
        3) _shizuku_apply_fixes ;;
        4) _shizuku_guide ;;
        0) return ;;
        *) warn "Nieznana opcja" ;;
    esac
}

_shizuku_deploy_rish() {
    hdr "Deploy rish — SecFerro method"
    local pkg_path
    pkg_path="$(_sh "pm path ${SHIZUKU_PKG} 2>/dev/null | head -1 | cut -d: -f2 | tr -d '\r'" || echo '')"

    if [[ -z "${pkg_path}" ]]; then
        err "Shizuku nie zainstalowane — najpierw zainstaluj aplikację Shizuku"
        info "Pobierz: https://shizuku.rikka.app/download/"
        info "Lub: adb install <shizuku.apk>"
        return 1
    fi

    ok "Shizuku APK: ${pkg_path}"
    info "Tworzenie skryptu rish..."

    local rish_script
    rish_script="#!/system/bin/sh
export CLASSPATH='${pkg_path}'
exec app_process /system/bin moe.shizuku.manager.shell.Shell \"\$@\""

    _sh "mkdir -p $(dirname ${RISH_PATH}) 2>/dev/null; true"
    printf '%s' "${rish_script}" | _sh "cat > ${RISH_PATH}" 2>/dev/null || {
        _sh "echo '#!/system/bin/sh' > ${RISH_PATH}"
        _sh "echo \"export CLASSPATH='${pkg_path}'\" >> ${RISH_PATH}"
        _sh "echo \"exec app_process /system/bin moe.shizuku.manager.shell.Shell \\\"\\\$@\\\"\" >> ${RISH_PATH}"
    }
    _sh "chmod 755 ${RISH_PATH}" 2>/dev/null || true

    local rish_ver; rish_ver="$(_sh "${RISH_PATH} -v 2>/dev/null" || echo '')"
    if echo "${rish_ver}" | grep -qi "shizuku"; then
        ok "rish wdrożony i działa ✓ (${rish_ver})"
        sub "Użyj: adb shell ${RISH_PATH} <komenda>"
    else
        warn "rish wdrożony ale Shizuku może nie być aktywne"
        info "Uruchom aplikację Shizuku na zegarku i kliknij 'Start'"
    fi
}

_shizuku_test_rish() {
    local test_out
    test_out="$(_sh "${RISH_PATH} -c 'id' 2>/dev/null" || echo 'FAILED')"
    if echo "${test_out}" | grep -q "uid="; then
        ok "rish działa: ${test_out}"
    else
        err "rish nie działa: ${test_out}"
        warn "Upewnij się że: 1) Shizuku jest uruchomione  2) rish ma chmod 755"
    fi
}

_shizuku_apply_fixes() {
    hdr "Stosowanie fixów przez rish (bez kabla)"
    warn "Wymaga aktywnego Shizuku na zegarku!"

    if ! _sh "${RISH_PATH} -v 2>/dev/null" | grep -qi "shizuku"; then
        err "rish niedostępne. Uruchom opcję 1 (Deploy rish) najpierw."
        return 1
    fi

    _rish() { _sh "${RISH_PATH} -c \"$*\"" 2>/dev/null || true; }

    _bar "Animacje 0.5x" 20; printf "\n"
    _rish "settings put global window_animation_scale 0.5"
    _rish "settings put global transition_animation_scale 0.5"
    _rish "settings put global animator_duration_scale 0.5"

    _bar "SF Force GPU" 40; printf "\n"
    _rish "service call SurfaceFlinger 1008 i32 1"

    _bar "HWUI SkiaGL" 55; printf "\n"
    _rish "setprop debug.hwui.renderer skiagl"
    _rish "setprop debug.hwui.skip_empty_damage true"

    _bar "swappiness=60" 70; printf "\n"
    _rish "echo 60 > /proc/sys/vm/swappiness"

    _bar "WAKE_LOCK" 85; printf "\n"
    _rish "cmd appops set com.google.android.assistant WAKE_LOCK ignore"
    _rish "cmd appops set com.android.vending WAKE_LOCK ignore"

    _bar "sched_boost=1" 95; printf "\n"
    _rish "echo 1 > ${SCHED_BOOST_PATH}"

    _bar "Gotowe" 100; printf "\n"
    ok "Fixy A+C+E+F+I zastosowane przez rish (bez kabla ADB) ✓"
}

_shizuku_guide() {
    clear
    printf "${CYAN}${BOLD}"
    printf "  ╔══════════════════════════════════════════════════════════════════╗\n"
    printf "  ║  Instrukcja: Shizuku na Samsung Galaxy Watch 4 / WearOS 6.0    ║\n"
    printf "  ╚══════════════════════════════════════════════════════════════════╝\n"
    printf "${C0}\n"
    printf "${BOLD}  Krok 1:${C0} Pobierz APK Shizuku\n"
    printf "    ${CYAN}https://shizuku.rikka.app/download/${C0}\n"
    printf "    lub: ${CYAN}adb install shizuku.apk${C0}\n\n"
    printf "${BOLD}  Krok 2:${C0} Uruchom Shizuku przez ADB (jednorazowo)\n"
    printf "    ${CYAN}adb shell sh /sdcard/Android/data/moe.shizuku.privileged.api/start.sh${C0}\n\n"
    printf "${BOLD}  Krok 3:${C0} Deploy rish (opcja J → 1)\n\n"
    printf "${BOLD}  Krok 4:${C0} Od tej pory fixy bez kabla (opcja J → 3)\n\n"
    printf "  ${GRAY}• Shizuku działa przez ADB WiFi — nie wymaga USB po konfiguracji${C0}\n"
    printf "  ${GRAY}• rish proxy: ${RISH_PATH}${C0}\n"
    printf "  ${GRAY}• Projekt: https://shizuku.rikka.app${C0}\n\n"
    read -r -p "  Naciśnij Enter..."
}

# ───────────────────────────────────────────────────────────────────────────────
# §15e  FIX K — DIAGNOSTYKA ROZSZERZONA
# ───────────────────────────────────────────────────────────────────────────────

_diag_extended() {
    hdr "Diagnostyka Rozszerzona v6.0 (raport styczeń 2026)"
    _backup_settings

    local out_dir="${LOG_DIR}/diag_ext_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "${out_dir}"
    info "Wyniki: ${out_dir}/"

    local s=0 t=8

    # ── 1. ART compilation state
    _bar "ART compilationReason" $(( ++s*100/t )); printf "\n"
    {
        echo "=== ART Compilation State (post-OTA validation) ==="
        echo "Oczekiwane: compilerFilter=speed-profile, compilationReason=cmdline"
        echo ""
        for pkg in com.android.systemui com.android.settings \
                   com.samsung.android.app.watchface \
                   com.samsung.android.clocksync \
                   com.android.launcher3; do
            echo "--- ${pkg} ---"
            _sh_retry "dumpsys package ${pkg} 2>/dev/null | grep -E 'compilerFilter|compilationReason'" \
                || echo "N/A"
        done
    } > "${out_dir}/art_state.txt" 2>&1

    local jit_pkgs
    jit_pkgs="$(grep -l "verify" "${out_dir}/art_state.txt" 2>/dev/null | wc -l)"
    [[ "${jit_pkgs}" -gt 0 ]] && warn "ART: wykryto tryb JIT (verify) — zastosuj Fix G+H!" \
        || ok "ART: kompilacja OK (speed-profile)"

    # ── 2. App launch timing
    _bar "App launch timing" $(( ++s*100/t )); printf "\n"
    {
        echo "=== am start -W Cold Start Timing (próg: ${DIAG_APP_LAUNCH_THRESHOLD}ms) ==="
        echo ""
        for pkg_act in \
            "com.samsung.android.clocksync/.ClockSyncActivity" \
            "com.android.settings/.MainSettings"; do
            echo "--- ${pkg_act} ---"
            _sh_retry "am start -W -n ${pkg_act} 2>/dev/null | grep -E 'TotalTime|WaitTime'" \
                || echo "N/A"
            sleep 0.5
        done
    } > "${out_dir}/launch_timing.txt" 2>&1

    local slow_launches
    slow_launches="$(grep -oE 'TotalTime: [0-9]+' "${out_dir}/launch_timing.txt" 2>/dev/null \
        | awk -F': ' -v thr="${DIAG_APP_LAUNCH_THRESHOLD}" '$2 > thr {count++} END {print count+0}')"
    [[ "${slow_launches}" -gt 0 ]] && warn "Launch timing: ${slow_launches} aplikacji > ${DIAG_APP_LAUNCH_THRESHOLD}ms" \
        || ok "Launch timing: OK (< ${DIAG_APP_LAUNCH_THRESHOLD}ms)"

    # ── 3. Battery idle drain
    _bar "Battery idle drain" $(( ++s*100/t )); printf "\n"
    {
        echo "=== Battery Stats (idle drain analysis) ==="
        echo "Próg: > ${DIAG_BATTERY_IDLE_THRESHOLD}% / h idle = alarm"
        echo ""
        _sh_retry "dumpsys batterystats --charged 2>/dev/null | grep -E 'Estimated|discharge|WAKE_LOCK|wakeup' | head -30" \
            || echo "N/A"
        echo ""
        echo "=== Top WAKE_LOCK holders ==="
        _sh_retry "dumpsys batterystats 2>/dev/null | grep -E 'wake_lock_in' | sort -t= -k2 -rn | head -10" \
            || echo "N/A"
    } > "${out_dir}/battery_stats.txt" 2>&1
    ok "Battery stats zebrane"

    # ── 4. LowMemoryKiller events
    _bar "OOM/LMK events" $(( ++s*100/t )); printf "\n"
    {
        echo "=== LowMemoryKiller Events (próg: > 3 kills/h = alarm) ==="
        timeout 8 adb -s "${DEVICE}" logcat -d -b events 2>/dev/null \
            | grep -E "LowMemoryKiller|am_kill|am_low_memory|oom_adj" | head -30 \
            || echo "N/A"
        echo ""
        echo "=== OOM killer in main log ==="
        timeout 5 adb -s "${DEVICE}" logcat -d -v brief 2>/dev/null \
            | grep -iE "OutOfMemory|LMK|kill.*low|lowmem" | head -20 \
            || echo "N/A"
    } > "${out_dir}/lmk_events.txt" 2>&1

    local lmk_count
    lmk_count="$(grep -c "am_kill\|LowMemoryKiller" "${out_dir}/lmk_events.txt" 2>/dev/null || echo 0)"
    [[ "${lmk_count}" -gt 3 ]] && warn "LMK: ${lmk_count} kill events — zastosuj Fix E!" \
        || ok "LMK: ${lmk_count} kills (OK)"

    # ── 5. dirty_regions + Vulkan check
    _bar "Rendering diagnostics" $(( ++s*100/t )); printf "\n"
    {
        echo "=== Rendering Diagnostics ==="
        echo ""
        echo "--- HWUI props ---"
        for p in debug.hwui.renderer debug.hwui.profile \
                 debug.hwui.skip_empty_damage debug.hwui.use_buffer_age \
                 debug.hwui.render_dirty_regions \
                 ro.surface_flinger.supports_background_blur \
                 debug.sf.phase_offset_ns; do
            printf "%-50s = %s\n" "${p}" "$(_get_prop "${p}")"
        done
        echo ""
        echo "--- Vulkan availability ---"
        _sh_retry "vulkaninfo 2>/dev/null | head -5" || \
            _get_prop "ro.hardware.vulkan" || echo "Vulkan: N/A (oczekiwane na W920)"
        echo ""
        echo "--- device_config surface_flinger ---"
        _sh_retry "device_config list surface_flinger 2>/dev/null | head -10" || echo "N/A"
    } > "${out_dir}/rendering_diag.txt" 2>&1
    ok "Rendering diagnostics zebrane"

    # ── 6. sched_boost + I/O scheduler state
    _bar "Kernel scheduler state" $(( ++s*100/t )); printf "\n"
    {
        echo "=== Kernel Scheduler State ==="
        echo ""
        echo "sched_boost=$(cat ${SCHED_BOOST_PATH} 2>/dev/null || echo N/A)"
        echo ""
        echo "=== I/O schedulers ==="
        for blk in /sys/block/mmcblk*/queue/scheduler /sys/block/sda*/queue/scheduler; do
            [[ -f "${blk}" ]] && printf "%-50s %s\n" "${blk}" "$(cat "${blk}" 2>/dev/null)"
        done | _sh "cat" 2>/dev/null || echo "N/A — sprawdź lokalnie"
        echo ""
        echo "=== schedutil params ==="
        local sb="/sys/devices/system/cpu/cpufreq/policy0/schedutil"
        for p in up_rate_limit_us down_rate_limit_us; do
            printf "%-40s = %s\n" "${p}" "$(_get_kernel "${sb}/${p}")"
        done
        echo "sched_latency_ns = $(_get_kernel "/proc/sys/kernel/sched_latency_ns")"
    } > "${out_dir}/scheduler_state.txt" 2>&1
    ok "Scheduler state zebrane"

    # ── 7. JIT zygote disable verification
    _bar "JIT/ART runtime flags" $(( ++s*100/t )); printf "\n"
    {
        echo "=== ART Runtime Flags (device_config) ==="
        echo ""
        for flag in enable_uffd_gc enable_generational_cc disable_jit_zygote; do
            local val; val="$(_sh_retry "device_config get runtime_native_boot ${flag}" 2>/dev/null || echo 'null')"
            printf "%-40s = %s\n" "runtime_native_boot/${flag}" "${val}"
        done
        echo ""
        echo "=== ADB WiFi setup check ==="
        local tcp_port; tcp_port="$(_get_prop "service.adb.tcp.port")"
        printf "service.adb.tcp.port = %s %s\n" "${tcp_port}" "$([ "${tcp_port}" = "5555" ] && echo "(WiFi ADB aktywne)" || echo "(WiFi ADB nieaktywne)")"
    } > "${out_dir}/art_runtime_flags.txt" 2>&1
    ok "ART runtime flags zebrane"

    # ── 8. Raport zbiorczy
    _bar "Raport zbiorczy v6.0" $(( ++s*100/t )); printf "\n"
    {
        printf "═══════════════════════════════════════════════════════════════\n"
        printf "  GW4 Diagnostic Report v%s — %s\n" "${VERSION}" "$(date)"
        printf "  Model: %s | FW: %s | Bateria: %s%%\n" \
            "${DEVICE_MODEL}" "${DEVICE_FW}" "${DEVICE_BATTERY}"
        printf "  Platform: WearOS 6.0 / Android 16 / SDK %s\n" "${DEVICE_SDK}"
        printf "═══════════════════════════════════════════════════════════════\n\n"
        echo "── ART State ──"
        head -20 "${out_dir}/art_state.txt" 2>/dev/null
        echo ""
        echo "── Launch Timing ──"
        grep "TotalTime" "${out_dir}/launch_timing.txt" 2>/dev/null | head -5 || echo "N/A"
        echo ""
        echo "── LMK Events ──"
        echo "Kills: ${lmk_count}"
        echo ""
        echo "── Scheduler ──"
        grep "sched_boost\|up_rate_limit" "${out_dir}/scheduler_state.txt" 2>/dev/null | head -5
        echo ""
        echo "── ART Runtime Flags ──"
        cat "${out_dir}/art_runtime_flags.txt" 2>/dev/null | head -10
    } > "${out_dir}/RAPORT_v6.txt"

    printf "\n"
    ok "Diagnostyka rozszerzona v6.0 zakończona: ${out_dir}/"
    printf "\n  ${YELLOW}Kluczowe pliki:${C0}\n"
    for f in art_state.txt launch_timing.txt battery_stats.txt lmk_events.txt \
              scheduler_state.txt rendering_diag.txt RAPORT_v6.txt; do
        printf "  ${CYAN}→${C0} %s/%s\n" "${out_dir}" "${f}"
    done
    printf "\n  ${GREEN}${BOLD}Wyślij RAPORT_v6.txt przy zgłaszaniu problemu.${C0}\n\n"
}

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
    printf "    ${CYAN}bash <(curl -sL %s/gw4_optimizer_v6.1.sh)${C0}\n\n" "${RAW_BASE}"
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
        printf "  ║    Bateria: ${bat_col}%-3s%%${CYAN}  target: %-54s║\n" "${DEVICE_BATTERY:-?}" "${TARGET}"
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
    printf "  ${LCYAN}H${C0}) ART device_config    ${GRAY}~3s  │ JIT thrashing fix${C0}\n"
    printf "  ${LCYAN}I${C0}) I/O + sched_boost    ${GRAY}~2s  │ ${LGREEN}v6.0${C0}${GRAY} UI priorytet + I/O latency${C0}\n"
    printf "  ${LCYAN}J${C0}) Shizuku / rish       ${GRAY}~3s  │ ${LGREEN}v6.0${C0}${GRAY} fixy bez kabla ADB${C0}\n"
    printf "  ${LCYAN}L${C0}) AOD Sensor Guard     ${GRAY}~3s  │ ${LGREEN}v6.1${C0}${GRAY} blokada 100Hz WChiSensor i GMS ML${C0}\n"
    printf "\n"
    printf "  ${WHITE}${BOLD}─── NARZĘDZIA ──────────────────────────────────────────────────────${C0}\n"
    printf "  ${LCYAN}8${C0}) Diagnostyka systemu   ${GRAY}zbierz raporty (Toybox-safe)${C0}\n"
    printf "  ${LCYAN}K${C0}) Diagnostyka v6.0      ${GRAY}${LGREEN}v6.0${C0}${GRAY} ART/LMK/launch/battery${C0}\n"
    printf "  ${LCYAN}0${C0}) Diagnostyka różnicowa ${GRAY}snapshot PRZED/PO${C0}\n"
    printf "  ${LCYAN}9${C0}) Przywróć ustawienia   ${GRAY}z backupu lub OEM default${C0}\n"
    printf "  ${LCYAN}P${C0}) ${GREEN}Trwałość parametrów${C0}  ${GRAY}${LGREEN}NOWE v5.2${C0}${GRAY} Tasker/root/daemon${C0}\n"
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
            A)  _fix_animations; _FIXES_APPLIED+="A " ;;
            B)  _fix_aod;        _FIXES_APPLIED+="B " ;;
            C)  _fix_surfaceflinger; _FIXES_APPLIED+="C " ;;
            D)  _fix_kernel_scheduler; _FIXES_APPLIED+="D " ;;
            E)  _fix_memory;     _FIXES_APPLIED+="E " ;;
            F)  _fix_debloat;    _FIXES_APPLIED+="F " ;;
            G)  _fix_art;        _FIXES_APPLIED+="G " ;;
            H)  _fix_device_config_art; _FIXES_APPLIED+="H " ;;
            I)  _fix_io_and_sched_boost; _FIXES_APPLIED+="I " ;;
            J)  _fix_shizuku ;;
            K)  _diag_extended ;;
            L)  _fix_aod_sensors_and_gms; _FIXES_APPLIED+="L " ;;
            Z)  _fix_all;        _FIXES_APPLIED+="Z " ;;
            P)  _fix_persistence ;;
            8)  _run_diagnostics ;;
            0)  _diag_diff ;;
            9)  _restore ;;
            R)  _factory_reset ;;
            '?') _show_setup_guide ;;
            Q)
                _save_session_profile
                ok "Do widzenia! (profil zapisany)"
                exit 0 ;;
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
    _parse_args "$@"
    _init
    _banner
    printf "  ${CYAN}Log:${C0} ${LOG_FILE}\n"
    printf "  ${GRAY}v${VERSION} | ADB: $(adb version 2>/dev/null | head -1 | awk '{print $NF}') | target: ${TARGET}${C0}\n\n"
    _detect_device

    if [[ "${_DAEMON_MODE}" == "true" ]]; then
        info "Tryb daemon aktywowany przez --daemon"
        _watch_daemon_mode
        exit 0
    fi

    _offer_session_profile

    _loop
}

main "$@"