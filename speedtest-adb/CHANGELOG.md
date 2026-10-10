#### 📄 `CHANGELOG.md`

# Changelog
Wszystkie znaczące zmiany w projekcie są dokumentowane zgodnie ze standardami.

## [1.2.0] - 2026-09-05
### Added
- Nowoczesny, modułowy interfejs TUI z autorskim "Anonymousik" ANSI ASCII Art Banner.
- Moduł `run_ping_test` zapewniający analizę opóźnień do węzłów Cloudflare.
- Asynchroniczny i bezpieczny test wgrywania (`run_upload_test`), generujący paczkę danych przy pomocy systemowego `dd if=/dev/urandom`.

### Fixed
- Normalizacja ścieżek instalacyjnych w powłoce docelowej (poprawiono błąd względnej deklaracji `.$REMOTE_DIR`).
- Standaryzacja obliczeń ułamkowych całkowicie za pomocą wysoce kompatybilnego polecenia `awk`, zmniejszająca bazowe wymagania względem maszyny sterującej.

### Changed
- Koncepcja usuwania pliku (cleanup) została zmodyfikowana na interaktywne żądanie w standardowym strumieniu wyjścia (prompt T/N).


## [1.1.0] - 2026-09-05
### Added
- Inteligentny fallback pobierania w oparciu o sztywny link: pobiera binarkę ze zdalnego endpointu `Anonymousik.is-a.dev/scripts/adb-speedtest/curl` wyłącznie, gdy nie znajdzie pliku `./curl` w katalogu ze skryptem.
- Nowy moduł `confirm_cleanup` umożliwiający ręczną, świadomą decyzję o zatarciu śladów (`rm -rf`) po pliku wykonywalnym na urządzeniu brzegowym.

### Changed
- Przekonstruowano wywołania ADB pod kątem spójności ścieżek bezwzględnych (`/data/local/tmp/curl`).
- Zmiana mechanizmu wymuszonego auto-czyszczenia (trap) w celu spełnienia wymogów użytkownika końcowego. Operacja czyszczenia dokonywana jest tylko po zaakceptowaniu na standardowym wejściu.


## [1.0.0] - 2026-09-05
### Added
- Wdrożono interaktywny i kolorowy interfejs ANSI.
- Mechanizm provisioning'u dla statycznego binarium `curl` (AArch64), zapewniający stabilne środowisko na urządzeniach bez nowoczesnych narzędzi sieciowych (Toybox).
- Pełna obsługa testów Ping, Download oraz Upload dla architektury Anycast (Cloudflare).
- Pułapki na zdarzenia (trap) z bezpiecznym czyszczeniem katalogu `/data/local/tmp`.
- Tryb `--cli` wspierający działania bezobsługowe (skrypty DevOps).