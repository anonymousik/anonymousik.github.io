#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════╗
# ║  SCU AUTO-FIXER & ENVIRONMENT REPAIR                     ║
# ║  Naprawia błędy składni SCU i konfiguruje repozytorium   ║
# ╚══════════════════════════════════════════════════════════╝

C_CYAN='\e[1;36m'
C_GREEN='\e[1;32m'
C_YELLOW='\e[1;33m'
C_RED='\e[1;31m'
C_RESET='\e[0m'

echo -e "${C_CYAN}[FIXER] Rozpoczynam naprawę środowiska SCU...${C_RESET}\n"

# 1. Czyszczenie błędnych zmiennych środowiskowych
echo -e "${C_YELLOW}[1/4] Usuwanie błędnych zmiennych środowiskowych Git...${C_RESET}"
unset GIT_DISCOVERY_ACROSS_FILESYSTEM
# Jeśli użytkownik dodał to do ~/.bashrc, usuwamy to
if grep -q "GIT_DISCOVERY_ACROSS_FILESYSTEM" ~/.bashrc 2>/dev/null; then
    sed -i '/GIT_DISCOVERY_ACROSS_FILESYSTEM/d' ~/.bashrc
    echo -e "${C_GREEN}  -> Usunięto z ~/.bashrc${C_RESET}"
fi

# 2. Naprawa pliku wykonywalnego SCU (Usunięcie artefaktów "???")
SCU_BIN_PATH="$HOME/bin/scu.sh"
echo -e "${C_YELLOW}[2/4] Naprawa kodu źródłowego SCU ($SCU_BIN_PATH)...${C_RESET}"

if [ -f "$SCU_BIN_PATH" ]; then
    # Usunięcie linii zawierających znaczniki błędów wklejania "???"
    sed -i '/???/d' "$SCU_BIN_PATH"
    echo -e "${C_GREEN}  -> Usunięto nieprawidłowe bloki kodu ze skryptu.${C_RESET}"
    
    # Dodanie zabezpieczenia, aby SCU sprawdzało czy jest w repo Git przed uruchomieniem komend
    if ! grep -q "git rev-parse --is-inside-work-tree" "$SCU_BIN_PATH"; then
        # Wstrzykujemy sprawdzanie gita na początek skryptu (zaraz po logowaniu)
        sed -i '/_load_conf/a \
        if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then \
            echo -e "\\e[1;31m[FATAL] Ten folder nie jest repozytorium Git! Uruchom: git init\\e[0m"; \
            exit 1; \
        fi' "$SCU_BIN_PATH"
        echo -e "${C_GREEN}  -> Zaimplementowano weryfikację zabezpieczającą Git.${C_RESET}"
    fi
else
    echo -e "${C_RED}  -> Nie znaleziono $SCU_BIN_PATH. Pomiń...${C_RESET}"
fi

# 3. Naprawa obecnego katalogu roboczego (Inicjalizacja Git)
echo -e "${C_YELLOW}[3/4] Inicjalizacja repozytorium w bieżącym katalogu ($(pwd))...${C_RESET}"
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git init
    git branch -M main 2>/dev/null || git branch -M master 2>/dev/null
    echo -e "${C_GREEN}  -> Repozytorium zainicjowane (git init).${C_RESET}"
else
    echo -e "${C_GREEN}  -> To już jest repozytorium Git.${C_RESET}"
fi

# 4. Automatyczny pierwszy commit, by "git push" miało punkt odniesienia
echo -e "${C_YELLOW}[4/4] Tworzenie początkowego commita...${C_RESET}"
git add -A
# Wyciszamy błąd, jeśli commit już istnieje (nothing to commit)
git commit -m "Auto-fix: Inicjalizacja projektu dla SCU" >/dev/null 2>&1 || true
echo -e "${C_GREEN}  -> Gotowe. Pliki dodane do repozytorium.${C_RESET}"

echo -e "\n${C_CYAN}====================================================${C_RESET}"
echo -e "${C_GREEN}Naprawa zakończona sukcesem!${C_RESET}"
echo -e "${C_CYAN}Teraz możesz poprawnie uruchomić SCU poleceniem:${C_RESET}"
echo -e "  scu --yes"
echo -e "${C_CYAN}====================================================${C_RESET}"
