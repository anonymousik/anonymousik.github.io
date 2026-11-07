#!/system/bin/sh
# ==============================================================================
# Inicjalizacja środowiska wykonawczego dla operacji uprzywilejowanych
# ==============================================================================

RISH_BIN="/data/local/tmp/rish"

if [ -x "$RISH_BIN" ] && $RISH_BIN -c 'id' 2>/dev/null | grep -q 'uid=2000'; then
    export EXEC="$RISH_BIN -c"
    export LAYER="RISH (Shizuku API)"
elif su -c 'id' 2>/dev/null | grep -q 'uid=0'; then
    export EXEC="su -c"
    export LAYER="ROOT (su)"
else
    export EXEC="sh -c"
    export LAYER="ADB Shell (Ograniczony)"
fi

# Inteligentna funkcja modyfikująca właściwości z weryfikacją stanu
apply_prop() {
    local key="$1"
    local target_val="$2"
    local current_val=$($EXEC "getprop $key" 2>/dev/null)
    
    if [ "$current_val" != "$target_val" ]; then
        $EXEC "setprop $key $target_val"
        echo "[+] Zaktualizowano prop: $key ($current_val -> $target_val)"
    fi
}

# Weryfikacja i zapis do bazy ustawień globalnych
apply_global() {
    local key="$1"
    local target_val="$2"
    local current_val=$($EXEC "settings get global $key" 2>/dev/null)
    
    if [ "$current_val" != "$target_val" ]; then
        $EXEC "settings put global $key $target_val"
        echo "[+] Zaktualizowano global: $key ($current_val -> $target_val)"
    fi
}