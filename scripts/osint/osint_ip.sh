#!/usr/bin/env bash
# osint_ip.sh — IP metadata lookup via ipinfo.io
# Requires: curl, jq
# Note: Free tier limit = 50k req/month. Set IPINFO_TOKEN env var for higher limits.
# Usage: ./osint_ip.sh <ipv4_or_ipv6_address>
set -euo pipefail

# --- Dependency check ---
for cmd in curl jq; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "[!] Brakująca zależność: '${cmd}'. Zainstaluj przed uruchomieniem." >&2
        exit 1
    fi
done

# --- Input validation ---
TARGET_IP="${1:-}"

if [[ -z "$TARGET_IP" ]]; then
    echo "[!] Użycie: ./osint_ip.sh <adres_ip>" >&2
    exit 1
fi

# Basic IP format guard (IPv4 + IPv6) — prevents URL injection
if ! [[ "$TARGET_IP" =~ ^[a-fA-F0-9:.]+$ ]]; then
    echo "[!] Nieprawidłowy format adresu IP: '${TARGET_IP}'" >&2
    exit 1
fi

# --- Token (optional) ---
IPINFO_TOKEN="${IPINFO_TOKEN:-}"
API_URL="https://ipinfo.io/${TARGET_IP}/json"
[[ -n "$IPINFO_TOKEN" ]] && API_URL="${API_URL}?token=${IPINFO_TOKEN}"

echo "[*] Pobieranie metadanych dla IP: ${TARGET_IP}"

# --- Fetch with error handling ---
HTTP_RESPONSE=$(curl -s -w "\n%{http_code}" --max-time 10 "$API_URL")
HTTP_BODY=$(echo "$HTTP_RESPONSE" | head -n -1)
HTTP_CODE=$(echo "$HTTP_RESPONSE" | tail -n 1)

if [[ "$HTTP_CODE" != "200" ]]; then
    echo "[!] Błąd HTTP ${HTTP_CODE} od ipinfo.io. Sprawdź limit lub token." >&2
    exit 1
fi

# Validate JSON before parsing (guards against HTML error pages)
if ! echo "$HTTP_BODY" | jq empty 2>/dev/null; then
    echo "[!] Odpowiedź nie jest prawidłowym JSON. Możliwe przekroczenie limitu API." >&2
    exit 1
fi

# --- Output ---
# NOTE: .bogon = private/reserved IP range (RFC1918), NOT a VPN/proxy indicator.
# For VPN/proxy detection use: ipinfo.io/privacy (paid) or ip-api.com (free tier).
echo "$HTTP_BODY" | jq '{
  IP:           .ip,
  Hostname:     (.hostname // "brak"),
  Organizacja:  (.org // "brak"),
  ASN:          (.asn // "brak"),
  Miasto:       (.city // "brak"),
  Region:       (.region // "brak"),
  Kraj:         .country,
  Lokalizacja:  .loc,
  Bogon_RFC1918: (.bogon // false)
}'

echo "[+] Analiza zakończona."
