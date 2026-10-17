# |SC-AR| Screen-Calibrate-AR
> **Inżynieryjna Aplikacja Webowa (SPA) do Interaktywnej Weryfikacji, Diagnostyki i Kalibracji Parametrów Obrazu w Telewizorach LCD**  
> *Dedykowana dla matryc CCFL/Edge-LED z płytami głównymi Vestel (MB90/MB95/MB100/MB120) oraz Toshiba Regza.*

[![Version](https://img.shields.io/badge/version-2.5.0-06b6d4.svg?style=flat-square)](https://anonymousik.is-a.dev)
[![License](https://img.shields.io/badge/license-MIT-10b981.svg?style=flat-square)](LICENSE)
[![Status](https://img.shields.io/badge/status-production--ready-10b981.svg?style=flat-square)](#)

---

## 📌 Spis Treści
- [Przegląd Projektu](#-przegląd-projektu)
- [Główne Moduły Systemowe](#-główne-moduły-systemowe)
- [Wymagania i Zależności Systemowe](#-wymagania-i-zależności-systemowe)
- [Przewodnik Instalacji i Uruchomienia](#-przewodnik-instalacji-i-uruchomienia)
- [Integracja Hybrydowa: ADB Shell / Termux REST API](#-integracja-hybrydowa-adb-shell--termux-rest-api)
- [Standardy Dostępności i Zgodność](#-standardy-dostępności-i-zgodność)
- [Prawa Autorskie](#-prawa-autorskie)

---

## 🛠 Przegląd Projektu

**|SC-AR| Screen-Calibrate-AR** to zaawansowana aplikacja webowa typu Single Page Application (SPA) działająca całkowicie po stronie klienta (Client-Side). Łączy nowoczesny interfejs inspirowany oprogramowaniem routerów sieciowych (np. OpenWRT Dashboard) z estetyką **Cyberpunk Dark Mode**.

Aplikacja rozwiązuje problem błędnych fabrycznych ustawień obrazu (np. trybów *Vivid/Dynamic*, nieprawidłowej temperatury barwowej >9500K czy zjawiska *Ringing/Overshooting*) w telewizorach LCD z lat 2011–2015, oferując użytkownikom kompleksowe wsparcie diagnostyczno-kalibracyjne.

---

## 🧩 Główne Moduły Systemowe

1. **Moduł Aparatu (AP) & AR Overlay:**
   - Wykorzystuje natywne WebRTC API (`getUserMedia()`) do obsługi tylnej kamery smartfona.
   - Nakłada interaktywną ramkę pomocniczą AR ze wskaźnikami kadrów.
   - Symuluje zaimplementowane filtry obrazu (Jasność, Kontrast, Temperatura barwowa 3000K–10000K Kelvinów, Ostrość, DNR) w czasie rzeczywistym na podglądzie kamery.

2. **Proaktywny Test Interaktywny (Gamified Quiz):**
   - 5-etapowy, proaktywny mechanizm diagnostyczny weryfikujący: Tryb Obrazu, Ostrość/Ringing, Podświetlenie, Temperaturę D65 oraz Redukcję Szumów (DNR).
   - Generuje natychmiastowe, inżynieryjne uzasadnienia dla każdej opcji, objaśniające fizyczny wpływ ustawień na panele LCD.

3. **Generator Plansz Testowych 4K (Canvas Engine) & Dual Cast Controller:**
   - Silnik HTML5 Canvas do dynamicznego renderowania w czasie rzeczywistym plansz referencyjnych w dowolnej rozdzielczości (do 4K UHD):
     * *Gamma 2.2 / 2.4* (pasy poziomu szarości).
     * *White Clipping / Kontrast* (zakres bieli RGB 235–255).
     * *Black Pluge / Jasność* (zakres czerni RGB 0–25).
     * *High-Frequency Sharpness Grid* (testy interfejsu i overshooting).
     * *SMPTE BT.709 Color Bars* (referencja saturacji i odcieni).
   - **Podwójny silnik wysyłania obrazu:**
     * **Główny:** Łącze ADB Shell / Termux REST API do bezpośredniego sterowania telewizorem z pominięciem usług chmurowych.
     * **Awaryjny:** Google Cast Sender API oraz W3C Presentation API z automatycznym fallbackiem pełnoekranowym.

4. **Kreator Raportu i Dashboard Diagnostyczny:**
   - Wylicza **Wskaźnik Wierności Obrazu (WWO %)**.
   - Generuje wykres radarowy w technologii SVG (5 osi diagnostycznych).
   - Tworzy zestawienie rekomendacji parametrów OSD dopasowanych do profili użytkowych (*Dzień* vs *Noc*) dla płyt Toshiba/Vestel MB90/MB95/MB100/MB120.
   - Omówienie opcji eksportu raportu do pliku JSON oraz druku/PDF.

---

## 💻 Wymagania i Zależności Systemowe

### Wymagania po stronie klienta (Przeglądarka)
- Przeglądarka z obsługą HTML5 Canvas, WebRTC, Flexbox/Grid (Google Chrome 90+, Mozilla Firefox 88+, Safari 14+, Microsoft Edge 90+).
- Dostęp do interfejsu kamery (wymagany bezpieczny kontekst `https://` lub `http://localhost`).

### Wymagania dla integracji sterowania ADB / Termux (Opcjonalnie)
- **Środowisko docelowe:** Android z aplikacją Termux lub dowolny system Linux/macOS.
- **Narzędzia systemowe:** `android-tools` (w tym `adb`), `python3` (dla lokalnego serwera HTTP / REST bridge).

---

## 🚀 Przewodnik Instalacji i Uruchomienia

### Krok 1: Klonowanie repozytorium lub pobranie kodu

```bash
git clone [https://github.com/Anonymousik/screen-calibrate-ar.git](https://github.com/Anonymousik/screen-calibrate-ar.git)
cd screen-calibrate-ar
