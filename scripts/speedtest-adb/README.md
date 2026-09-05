speedtest-adb

**Wersja:** 1.2.0
**Autor:** Anonymousik

Narzędzie przeznaczone do precyzyjnego pomiaru parametrów sieciowych (Latency, Download, Upload) bezpośrednio na urządzeniach z systemem **Android TV 9 (ATV9)**. Rozwiązanie to omija ograniczenia wbudowanej powłoki `Toybox`, automatycznie dostarczając (provisioning) statycznie skompilowane narzędzia sieciowe poprzez tunel ADB.

## Główne cechy
* **Nowoczesny UI:** Interfejs konsolowy oparty o ANSI Escape Codes.
* **Toybox Bypass:** Cała zaawansowana logika obliczeniowa (AWK, RegExp) wykonywana jest na hoście.
* **Zero-Trust Cleanup:** Automatyczne czyszczenie plików tymczasowych (binariów, pakietów testowych) po zrzuceniu sygnału `SIGINT` (Ctrl+C).
* **Cloudflare Anycast:** Wykorzystanie brzegowych serwerów CF do rzetelnego pomiaru z ominięciem cache ISP.

## Kompatybilność
* **Host:** Linux, macOS, WSL2, Termux (Wymaga `bash`, `adb`, `bc`, `curl`).
* **Target:** Dowolne urządzenie z ADB (optymalizowane pod Android TV 9).
