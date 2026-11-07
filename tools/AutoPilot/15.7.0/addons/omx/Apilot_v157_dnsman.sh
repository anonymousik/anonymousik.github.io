#!/usr/bin/env bash
# ==============================================================================
# SecFERRO_DNSManager_v2.sh
# Quad-Doc: Execution Module (Android TV 9 - Client Side).
# ==============================================================================

# --- SecFERRO Brand Colors ---
C_ACCENT="\033[38;2;191;0;255m" # Electric Purple
C_DIM="\033[90m"                # Obsidian Gray
C_ERR="\033[38;2;255;0;0m"      # Error Red
C_RESET="\033[0m"

CONFIG_FILE="SecFERRO_DNS.conf"

# --- Visual Rigor ---
print_banner() {
    local title="==[ $1 ]"
    local len=${#title}
    local rem=$((80 - len))
    local line=""
    for ((i=0; i<rem; i++)); do line="${line}="; done
    echo -e "\n${C_ACCENT}${title}${line}${C_RESET}"
}

# --- Core ADB & State ---
check_adb_connection() {
    echo -e "${C_DIM}[*] Autoryzacja sesji ADB...${C_RESET}"
    local status=$(adb devices | awk 'NR>1 {print $2}' | head -n 1)
    if [[ "$status" != "device" ]]; then
        echo -e "${C_ERR}[!] Brak autoryzowanej sesji ADB. Przerwanie.${C_RESET}"
        exit 1
    fi
    echo -e "${C_DIM}[+] Łącze zabezpieczone.${C_RESET}"
}

# --- Atomic Operations (Power Failure Resilience) ---
atomic_add_profile() {
    local entry="$1"
    touch "$CONFIG_FILE"
    cp "$CONFIG_FILE" "${CONFIG_FILE}.tmp"
    echo "$entry" >> "${CONFIG_FILE}.tmp"
    mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
    echo -e "${C_DIM}[+] Profil zrzucony atomowo do Pamięci Trwałej.${C_RESET}"
}

atomic_del_profile() {
    local target_id="$1"
    cp "$CONFIG_FILE" "${CONFIG_FILE}.tmp"
    sed -i.bak "${target_id}d" "${CONFIG_FILE}.tmp" 2>/dev/null || sed -i "" "${target_id}d" "${CONFIG_FILE}.tmp"
    mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
    rm -f "${CONFIG_FILE}.tmp.bak"
    echo -e "${C_DIM}[+] Profil usunięty.${C_RESET}"
}

load_profiles() {
    CUSTOM_SERVERS=()
    [[ ! -f "$CONFIG_FILE" ]] && return
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ -z "$line" || "$line" =~ ^# ]] && continue
        CUSTOM_SERVERS+=("$line")
    done < "$CONFIG_FILE"
}

# --- Profile Management ---
list_profiles() {
    load_profiles
    if [[ ${#CUSTOM_SERVERS[@]} -eq 0 ]]; then
        echo -e "${C_DIM}Brak zdefiniowanych profili (Stos Pusty).${C_RESET}"
        return 1
    fi
    printf "${C_DIM}%-3s | %-25s | %-15s | %-30s${C_RESET}\n" "ID" "NAZWA" "TEST IP" "DOMENA DoT"
    for i in "${!CUSTOM_SERVERS[@]}"; do
        IFS="|" read -r name ip dot <<< "${CUSTOM_SERVERS[$i]}"
        printf "%-3s | %-25s | %-15s | %-30s\n" "$((i+1))" "$name" "$ip" "$dot"
    done
    return 0
}

add_new_profile() {
    read -p "Nazwa węzła (np. NextDNS): " c_name
    read -p "Adres IP do testu (np. 45.90.28.0): " c_ip
    read -p "Domena DoT (np. dns.nextdns.io): " c_dot
    
    if [[ -n "$c_name" && -n "$c_ip" && -n "$c_dot" ]]; then
        atomic_add_profile "$c_name|$c_ip|$c_dot"
    else
        echo -e "${C_ERR}[!] Naruszenie integralności danych. Odrzucono.${C_RESET}"
    fi
}

menu_profiles() {
    while true; do
        print_banner "PROFILE MANAGEMENT"
        echo "1. Analiza Stosu (Wyświetl)"
        echo "2. Iniekcja Nowego Węzła (Dodaj)"
        echo "3. Destrukcja Węzła (Usuń)"
        echo "4. Powrót"
        read -p "Rozkaz: " choice
        
        case $choice in
            1) list_profiles ;;
            2) add_new_profile ;;
            3) list_profiles && read -p "ID do usunięcia: " did && atomic_del_profile "$did" ;;
            4) break ;;
        esac
    done
}

# --- Benchmark Engine ---
get_ping_time() {
    local ip="$1"
    local res=$(adb shell ping -c 3 -W 2 "$ip" 2>/dev/null | tail -n 1 | awk -F '/' '{print $5}')
    [[ -z "$res" || "$res" == "0" ]] && res=$(adb shell ping -c 3 -W 2 "$ip" 2>/dev/null | grep "rtt" | cut -d'/' -f5)
    echo "$res"
}

run_benchmark() {
    print_banner "LATENCY BENCHMARK ENGINE"
    local tmp_res=$(mktemp)
    local BASE_SERVERS=(
        "Cloudflare Security|1.1.1.2|1dot1dot1dot1.cloudflare-dns.com"
        "uBlockDNS Hybryda|104.244.42.1|ublockdns.com"
        "AdGuard DNS|94.140.14.14|dns.adguard.com"
    )
    load_profiles
    local ALL_SERVERS=("${BASE_SERVERS[@]}" "${CUSTOM_SERVERS[@]}")

    printf "${C_DIM}%-35s | %-12s${C_RESET}\n" "WĘZEŁ" "OPÓŹNIENIE (ms)"
    for srv in "${ALL_SERVERS[@]}"; do
        IFS="|" read -r name ip dot <<< "$srv"
        local ping_time=$(get_ping_time "$ip")
        
        if [[ -n "$ping_time" ]]; then
            local prefix="${C_ACCENT}[O]${C_RESET}"
            [[ " ${CUSTOM_SERVERS[*]} " == *"$srv"* ]] && prefix="${C_ACCENT}[P]${C_RESET}"
            printf "%-35s | %-12s\n" "$prefix $name" "$ping_time"
            echo "$ping_time|$name|$dot" >> "$tmp_res"
        else
            printf "%-35s | ${C_ERR}TIMEOUT${C_RESET}\n" "[X] $name"
        fi
    done

    echo -e "\n${C_DIM}Ranking Węzłów (TOP):${C_RESET}"
    sort -n "$tmp_res" | awk -F '|' 'BEGIN {r=1} {print r". " $2 " (" $1 " ms) -> " $3; r++}'
    rm -f "$tmp_res"
}

# --- DNS Injection ---
apply_dns() {
    local dot="$1"
    if [[ -z "$dot" || "$dot" == "off" ]]; then
        adb shell settings put global private_dns_mode off
        adb shell settings put global private_dns_specifier ""
        echo -e "${C_DIM}[+] Prywatny DNS dezaktywowany.${C_RESET}"
    else
        adb shell settings put global private_dns_mode hostname
        adb shell settings put global private_dns_specifier "$dot"
        echo -e "${C_ACCENT}[+] Zastosowano wektor: $dot${C_RESET}"
    fi
}

show_dns_status() {
    local mode=$(adb shell settings get global private_dns_mode 2>/dev/null | tr -d '\r')
    local spec=$(adb shell settings get global private_dns_specifier 2>/dev/null | tr -d '\r')
    
    echo -e "${C_DIM}Tryb Operacyjny: ${C_RESET}$mode"
    if [[ "$mode" == "hostname" ]]; then
        echo -e "${C_DIM}Cel (Target): ${C_ACCENT}$spec${C_RESET}"
    fi
}

menu_dns() {
    while true; do
        print_banner "ANDROID DNS INJECTION"
        echo "1. Status Bieżący"
        echo "2. Iniekcja Profilu Personalnego"
        echo "3. Iniekcja Cloudflare Security"
        echo "4. Wyłączenie (Bypass to DHCP)"
        echo "5. Powrót"
        read -p "Rozkaz: " choice
        
        case $choice in
            1) show_dns_status ;;
            2) 
                list_profiles || continue
                read -p "ID Węzła: " tid
                IFS="|" read -r name ip dot <<< "${CUSTOM_SERVERS[$((tid-1))]}"
                apply_dns "$dot"
                ;;
            3) apply_dns "1dot1dot1dot1.cloudflare-dns.com" ;;
            4) apply_dns "off" ;;
            5) break ;;
        esac
    done
}

# --- Main Engine Loop ---
main() {
    check_adb_connection
    while true; do
        print_banner "SecFERRO ADVANCED DNS SYSTEM"
        echo "1. Analiza Opóźnień (Benchmark)"
        echo "2. Zarządzanie Wektorami (Ustaw DNS)"
        echo "3. Baza Profili (Zarządzaj)"
        echo "4. Zakończ Sesję"
        read -p "Wprowadź kod operacji: " mc
        
        case $mc in
            1) run_benchmark ;;
            2) menu_dns ;;
            3) menu_profiles ;;
            4) echo -e "${C_DIM}[*] Zamykanie strumienia...${C_RESET}"; exit 0 ;;
            *) echo -e "${C_ERR}[!] Nieznana instrukcja.${C_RESET}" ;;
        esac
    done
}

main