
## OSINT FRAUD ANALYZER
Rozbudowany skrypt łączący **6 źródeł danych** + automatyczne raportowanie do organów:
 
Ver: V1.0.0(08.03.2026)
(SecFERRO DIVISION Series)
---

## Jak uruchomić

```bash
# Ustaw klucze API (wszystkie opcjonalne poza podstawowym działaniem)
export ABUSEIPDB_KEY="twój_klucz"
export VIRUSTOTAL_KEY="twój_klucz"
export SHODAN_KEY="twój_klucz"
export IPINFO_TOKEN="twój_token"

chmod +x osint_fraud_analyzer.sh
./osint_fraud_analyzer.sh 185.220.101.45
```

---

## Legalna ścieżka neutralizacji oszustów

| Etap | Działanie | Narzędzie |
|---|---|---|
| 1. Dokumentuj | Zbierz logi, screenshoty, IP | Ten skrypt |
| 2. Zgłoś | CERT.PL / Policja | `incydent.cert.pl` |
| 3. Zablokuj | AbuseIPDB community report | `abuseipdb.com/report` |
| 4. Phishing | Google/Microsoft takedown | Safe Browsing Report |
| 5. Hosting | Abuse email do ISP/hosta | `abuse@[isp]` |

To jest realna i **skuteczna** neutralizacja — przez kanały z uprawnieniami prawnymi.
