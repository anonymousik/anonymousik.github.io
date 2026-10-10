#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════╗
# ║  GITHUB REMOTE FIXER                                     ║
# ║  Łączy lokalne repozytorium z serwerami GitHub           ║
# ╚══════════════════════════════════════════════════════════╝

C_CYAN='\e[1;36m'
C_GREEN='\e[1;32m'
C_YELLOW='\e[1;33m'
C_RED='\e[1;31m'
C_RESET='\e[0m'

echo -e "${C_CYAN}[FIXER] Konfiguracja połączenia z GitHub (Remote)...${C_RESET}\n"

# Nazwa docelowego repozytorium (odczytana z Twoich logów)
REPO_OWNER="anonymousik"
REPO_NAME="neurosync-ai-private"
FULL_REPO="$REPO_OWNER/$REPO_NAME"

# 1. Czyszczenie starych powiązań (na wszelki wypadek)
if git remote -v | grep -q "origin"; then
    echo -e "${C_YELLOW}[1/3] Usuwanie starego powiązania 'origin'...${C_RESET}"
    git remote remove origin
else
    echo -e "${C_YELLOW}[1/3] Brak przypisanego adresu. Przechodzę dalej...${C_RESET}"
fi

# 2. Weryfikacja / Tworzenie repo na GitHubie
echo -e "${C_YELLOW}[2/3] Sprawdzanie dostępności repozytorium w chmurze GitHub...${C_RESET}"

if gh repo view "$FULL_REPO" >/dev/null 2>&1; then
    echo -e "${C_GREEN}  -> Repozytorium $FULL_REPO istnieje na Twoim koncie.${C_RESET}"
    echo -e "  -> Dodaję adres zdalny (remote origin)..."
    git remote add origin "https://github.com/${FULL_REPO}.git"
else
    echo -e "${C_RED}  -> Repozytorium $FULL_REPO nie istnieje na koncie GitHub!${C_RESET}"
    echo -e "${C_YELLOW}  -> Tworzę nowe prywatne repozytorium...${C_RESET}"
    gh repo create "$FULL_REPO" --private --source=. --remote=origin
    echo -e "${C_GREEN}  -> Repozytorium utworzone!${C_RESET}"
fi

# 3. Synchronizacja kodu
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo -e "${C_YELLOW}[3/3] Wypychanie lokalnego kodu do GitHuba (gałąź: $CURRENT_BRANCH)...${C_RESET}"

if git push -u origin "$CURRENT_BRANCH"; then
    echo -e "\n${C_GREEN}====================================================${C_RESET}"
    echo -e "${C_GREEN}SUKCES! Repozytorium jest poprawnie podłączone.${C_RESET}"
    echo -e "${C_CYAN}Teraz możesz włączyć swoje narzędzie:${C_RESET}"
    echo -e "  scu"
    echo -e "${C_GREEN}====================================================${C_RESET}"
else
    echo -e "\n${C_RED}[BŁĄD] Wypychanie kodu nie powiodło się. Upewnij się, że masz połączenie z internetem.${C_RESET}"
fi
