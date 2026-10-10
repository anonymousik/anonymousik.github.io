#!/usr/bin/env bash
# osint_fraud_analyzer.sh
# Advanced IP/Domain fraud intelligence aggregator
# Sources: ipinfo.io, ip-api.com, AbuseIPDB, Shodan, VirusTotal, StopForum Spam
# Legal use: evidence gathering for law enforcement reports
## (If you don't use termux - uncomment!⤵️
#set -euo pipefail

# --- Config (set via environment variables) ---
ABUSEIPDB_KEY="${ABUSEIPDB_KEY:-}"
VIRUSTOTAL_KEY="${VIRUSTOTAL_KEY:-}"
SHODAN_KEY="${SHODAN_KEY:-}"
IPINFO_TOKEN="${IPINFO_TOKEN:-}"
OUTPUT_DIR="${OUTPUT_DIR:-./fraud_reports}"
REPORT_FILE=""

# --- Colors ---
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

# --- Dependency check ---
for cmd in curl jq date; do
    command -v "$cmd" &>/dev/null || { echo "[!] Brak: $cmd" >&2; exit 1; }
done

# --- Input validation ---
TARGET="${1:-}"
[[ -z "$TARGET" ]] && { echo "Użycie: $0 <ip|domena>" >&2; exit 1; }

# Sanitize: allow only IP/domain-safe chars
if ! [[ "$TARGET" =~ ^[a-zA-Z0-9._:-]+$ ]]; then
    echo "[!] Nieprawidłowy format celu: '${TARGET}'" >&2; exit 1
fi

# --- Helpers ---
safe_curl() {
    local url="$1"
    local response http_code body
    response=$(curl -sS -w "\n%{http_code}" --max-time 15 \
        -H "User-Agent: FraudAnalyzer/2.0" "$url" 2>/dev/null) || return 1
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n -1)
    [[ "$http_code" == "200" ]] || return 1
    echo "$body" | jq empty 2>/dev/null || return 1
    echo "$body"
}

log_section() { echo -e "\n${CYAN}${BOLD}══════════════════════════════${NC}"; \
                echo -e "${CYAN}${BOLD}  $1${NC}"; \
                echo -e "${CYAN}${BOLD}══════════════════════════════${NC}"; }

append_report() { echo "$1" >> "$REPORT_FILE"; }

# --- Setup output ---
mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="${OUTPUT_DIR}/fraud_report_${TARGET//\//_}_${TIMESTAMP}.txt"
{
    echo "======================================"
    echo "  FRAUD INTELLIGENCE REPORT"
    echo "  Target : $TARGET"
    echo "  Date   : $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo "======================================"
} > "$REPORT_FILE"

echo -e "${BOLD}[*] Cel analizy: ${YELLOW}${TARGET}${NC}"
echo -e "[*] Raport: ${REPORT_FILE}"

# ════════════════════════════════
# MODULE 1: Basic Geo + ASN (ipinfo.io)
# ════════════════════════════════
log_section "1/6 GEO + ASN — ipinfo.io"
append_report $'\n[MODULE 1] GEO + ASN'

API_URL="https://ipinfo.io/${TARGET}/json"
[[ -n "$IPINFO_TOKEN" ]] && API_URL+="?token=${IPINFO_TOKEN}"

if GEO=$(safe_curl "$API_URL"); then
    echo "$GEO" | jq '{
        IP:          .ip,
        Hostname:    (.hostname // "N/A"),
        Org:         (.org // "N/A"),
        City:        (.city // "N/A"),
        Region:      (.region // "N/A"),
        Country:     .country,
        Location:    .loc,
        Timezone:    (.timezone // "N/A"),
        Bogon:       (.bogon // false)
    }'
    append_report "$(echo "$GEO" | jq .)"
else
    echo -e "${YELLOW}[!] ipinfo.io niedostępne lub limit API${NC}"
fi

# ════════════════════════════════
# MODULE 2: Fraud Score + Proxy/VPN/Tor (ip-api.com)
# ════════════════════════════════
log_section "2/6 VPN/TOR/PROXY DETECTION — ip-api.com"
append_report $'\n[MODULE 2] VPN/TOR/PROXY'

FIELDS="status,message,country,countryCode,regionName,city,isp,org,as,proxy,hosting,query"
if IPAPI=$(safe_curl "http://ip-api.com/json/${TARGET}?fields=${FIELDS}"); then
    IS_PROXY=$(echo "$IPAPI" | jq -r '.proxy')
    IS_HOST=$(echo "$IPAPI" | jq -r '.hosting')
    echo "$IPAPI" | jq '{
        ISP:          .isp,
        Org:          .org,
        AS:           .as,
        Is_Proxy_VPN: .proxy,
        Is_Datacenter: .hosting,
        Country:      .country
    }'
    [[ "$IS_PROXY" == "true" ]] && \
        echo -e "${RED}[!] UWAGA: Wykryto PROXY/VPN!${NC}"
    [[ "$IS_HOST" == "true" ]] && \
        echo -e "${YELLOW}[!] IP należy do DATACENTER/HOSTING${NC}"
    append_report "$(echo "$IPAPI" | jq .)"
else
    echo -e "${YELLOW}[!] ip-api.com niedostępne${NC}"
fi

# ════════════════════════════════
# MODULE 3: Abuse Reports (AbuseIPDB)
# ════════════════════════════════
log_section "3/6 ABUSE HISTORY — AbuseIPDB"
append_report $'\n[MODULE 3] ABUSE REPORTS'

if [[ -z "$ABUSEIPDB_KEY" ]]; then
    echo -e "${YELLOW}[!] Brak ABUSEIPDB_KEY — pomiń lub ustaw zmienną env${NC}"
else
    if ABUSE=$(curl -sS --max-time 15 \
        -H "Key: ${ABUSEIPDB_KEY}" \
        -H "Accept: application/json" \
        "https://api.abuseipdb.com/api/v2/check?ipAddress=${TARGET}&maxAgeInDays=90&verbose" \
        2>/dev/null); then

        SCORE=$(echo "$ABUSE" | jq -r '.data.abuseConfidenceScore // 0')
        REPORTS=$(echo "$ABUSE" | jq -r '.data.totalReports // 0')

        echo "$ABUSE" | jq '.data | {
            Abuse_Score:     .abuseConfidenceScore,
            Total_Reports:   .totalReports,
            Last_Reported:   .lastReportedAt,
            ISP:             .isp,
            Domain:          .domain,
            Is_Whitelisted:  .isWhitelisted,
            Usage_Type:      .usageType
        }'

        # Risk level indicator
        if (( SCORE >= 80 )); then
            echo -e "${RED}[!!!] WYSOKI RISK SCORE: ${SCORE}/100 (${REPORTS} zgłoszeń)${NC}"
        elif (( SCORE >= 30 )); then
            echo -e "${YELLOW}[!] ŚREDNI RISK SCORE: ${SCORE}/100${NC}"
        else
            echo -e "${GREEN}[+] Niski risk score: ${SCORE}/100${NC}"
        fi
        append_report "$(echo "$ABUSE" | jq .)"
    fi
fi

# ════════════════════════════════
# MODULE 4: Open Ports / Banner (Shodan)
# ════════════════════════════════
log_section "4/6 OPEN PORTS / SERVICES — Shodan"
append_report $'\n[MODULE 4] SHODAN INTEL'

if [[ -z "$SHODAN_KEY" ]]; then
    echo -e "${YELLOW}[!] Brak SHODAN_KEY — pomiń lub ustaw zmienną env${NC}"
else
    if SHODAN=$(safe_curl \
        "https://api.shodan.io/shodan/host/${TARGET}?key=${SHODAN_KEY}"); then
        echo "$SHODAN" | jq '{
            OS:           (.os // "unknown"),
            Open_Ports:   .ports,
            Tags:         .tags,
            Vulns:        (.vulns | keys? // []),
            Last_Update:  .last_update,
            Hostnames:    .hostnames
        }'
        append_report "$(echo "$SHODAN" | jq .)"
    else
        echo -e "${YELLOW}[!] Shodan: brak danych dla tego IP${NC}"
    fi
fi

# ════════════════════════════════
# MODULE 5: Malware / Phishing (VirusTotal)
# ════════════════════════════════
log_section "5/6 MALWARE/PHISHING — VirusTotal"
append_report $'\n[MODULE 5] VIRUSTOTAL'

if [[ -z "$VIRUSTOTAL_KEY" ]]; then
    echo -e "${YELLOW}[!] Brak VIRUSTOTAL_KEY — pomiń lub ustaw zmienną env${NC}"
else
    if VT=$(curl -sS --max-time 15 \
        -H "x-apikey: ${VIRUSTOTAL_KEY}" \
        "https://www.virustotal.com/api/v3/ip_addresses/${TARGET}" \
        2>/dev/null); then
        echo "$VT" | jq '.data.attributes | {
            Malicious:    .last_analysis_stats.malicious,
            Suspicious:   .last_analysis_stats.suspicious,
            Harmless:     .last_analysis_stats.harmless,
            Network:      .network,
            Country:      .country,
            AS_Owner:     .as_owner
        }'
        MAL=$(echo "$VT" | jq -r '.data.attributes.last_analysis_stats.malicious // 0')
        (( MAL > 0 )) && \
            echo -e "${RED}[!!!] ${MAL} silników AV oznaczyło IP jako ZŁOŚLIWE${NC}"
        append_report "$(echo "$VT" | jq .)"
    fi
fi

# ════════════════════════════════
# MODULE 6: SpamHaus + StopForumSpam
# ════════════════════════════════
log_section "6/6 SPAM REPUTATION — StopForumSpam"
append_report $'\n[MODULE 6] SPAM REPUTATION'

if SFS=$(safe_curl \
    "https://api.stopforumspam.org/api?ip=${TARGET}&json"); then
    echo "$SFS" | jq '{
        IP_Listed:    .ip.appears,
        Frequency:    .ip.frequency,
        Last_Seen:    .ip.lastseen,
        Confidence:   .ip.confidence
    }'
    LISTED=$(echo "$SFS" | jq -r '.ip.appears // 0')
    (( LISTED > 0 )) && \
        echo -e "${RED}[!!!] IP figuruje w bazie SPAM/FRAUD!${NC}"
    append_report "$(echo "$SFS" | jq .)"
fi

# ════════════════════════════════
# SUMMARY + REPORTING GUIDANCE
# ════════════════════════════════
log_section "PODSUMOWANIE I ZGŁASZANIE"

{
    echo ""
    echo "======================================"
    echo "  LEGAL REPORTING CHANNELS"
    echo "======================================"
    echo "PL - CERT Polska:        https://incydent.cert.pl"
    echo "PL - Policja Cybercrime: https://www.policja.pl/pol/aktualnosci/cyberprzestepczosc"
    echo "EU - Europol EC3:        https://www.europol.europa.eu/report-a-crime"
    echo "AbuseIPDB Report:        https://www.abuseipdb.com/report"
    echo "Google Safe Browsing:    https://safebrowsing.google.com/safebrowsing/report_phish/"
    echo ""
    echo "Evidence file: $REPORT_FILE"
} | tee -a "$REPORT_FILE"

echo -e "\n${GREEN}${BOLD}[+] Analiza zakończona. Raport: ${REPORT_FILE}${NC}"
