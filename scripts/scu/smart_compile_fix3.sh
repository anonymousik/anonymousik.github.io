#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════╗
# ║  GITHUB SYNC FIXER                                       ║
# ║  Rozwiązuje konflikty "unrelated histories"              ║
# ╚══════════════════════════════════════════════════════════╝

C_CYAN='\e[1;36m'
C_GREEN='\e[1;32m'
C_YELLOW='\e[1;33m'
C_RED='\e[1;31m'
C_RESET='\e[0m'

echo -e "${C_CYAN}[FIXER] Rozwiązywanie konfliktów synchronizacji z GitHub...${C_RESET}\n"

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo -e "${C_YELLOW}[1/3] Pobieranie zmian z serwera GitHub...${C_RESET}"
git fetch origin "$CURRENT_BRANCH"

echo -e "${C_YELLOW}[2/3] Łączenie (scalanie) historii w chmurze z lokalnym folderem...${C_RESET}"
# Flag "--allow-unrelated-histories" zmusza Git do połączenia dwóch różnych repozytoriów.
# "-X ours" sprawia, że jeśli pliki o tej samej nazwie różnią się, Git zachowa Twoją wersję z Termuxa.
git merge FETCH_HEAD --allow-unrelated-histories -X ours -m "Auto-merge: Połączenie historii lokalnej z GitHubem"

echo -e "${C_YELLOW}[3/3] Wypychanie zsynchronizowanego kodu na serwer...${C_RESET}"
if git push -u origin "$CURRENT_BRANCH"; then
    echo -e "\n${C_GREEN}====================================================${C_RESET}"
    echo -e "${C_GREEN}SUKCES! Konflikt rozwiązany, a kod znajduje się na GitHubie.${C_RESET}"
    echo -e "${C_CYAN}Teraz możesz powrócić do swojego narzędzia:${C_RESET}"
    echo -e "  scu --yes"
    echo -e "${C_GREEN}====================================================${C_RESET}"
else
    echo -e "\n${C_RED}[BŁĄD] Wypychanie kodu nadal się nie udaje. Sprawdź logi powyżej.${C_RESET}"
fi
