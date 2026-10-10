#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════╗
# ║  GITHUB WORKFLOW & SYNC FIXER                            ║
# ║  Naprawia błąd uprawnień 'workflow' i kończy sync        ║
# ╚══════════════════════════════════════════════════════════╝

C_CYAN='\e[1;36m'
C_GREEN='\e[1;32m'
C_YELLOW='\e[1;33m'
C_RED='\e[1;31m'
C_RESET='\e[0m'

echo -e "${C_CYAN}[FIXER] Rozpoczynam naprawę uprawnień GitHub...${C_RESET}\n"

# 1. Odświeżenie uprawnień GitHub CLI
echo -e "${C_YELLOW}[1/2] Musisz dodać uprawnienie 'workflow'.${C_RESET}"
echo -e "Zostaniesz poproszony o ponowne zalogowanie przez przeglądarkę lub kod."
echo -e "Upewnij się, że zaznaczysz wszystkie zgody (szczególnie Workflow).\n"

# Komenda wymuszająca dodanie brakującego zakresu uprawnień
gh auth refresh -s workflow

if [ $? -eq 0 ]; then
    echo -e "\n${C_GREEN}[OK] Uprawnienia zaktualizowane.${C_RESET}"
else
    echo -e "\n${C_RED}[BŁĄD] Nie udało się zaktualizować uprawnień. Spróbuj ręcznie: gh auth login${C_RESET}"
    exit 1
fi

# 2. Ponowna próba wypchnięcia kodu
echo -e "\n${C_YELLOW}[2/2] Ponawiam próbę wysłania kodu (git push)...${C_RESET}"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

if git push -u origin "$CURRENT_BRANCH"; then
    echo -e "\n${C_GREEN}====================================================${C_RESET}"
    echo -e "${C_GREEN}SUKCES! Kod i automatyzacja (.yml) są już na GitHubie.${C_RESET}"
    echo -e "${C_CYAN}Teraz Twoje narzędzie SCU będzie działać poprawnie:${C_RESET}"
    echo -e "  scu --yes"
    echo -e "${C_GREEN}====================================================${C_RESET}"
else
    echo -e "\n${C_RED}[BŁĄD] Push nadal odrzucony. Jeśli problem powraca, spróbuj użyć:${C_RESET}"
    echo -e "  gh auth login --with-token < Twój_Personal_Access_Token_z_zaznaczonym_workflow"
fi
