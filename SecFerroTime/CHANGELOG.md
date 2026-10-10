# Changelog

Wszystkie istotne zmiany projektu SecFerro Division — Quantum Time Terminal są dokumentowane w tym pliku.

Format zgodny z [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
wersjonowanie zgodne z [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [5.0.0] — 2026-02-25

### 🚀 FUSION Edition — Major Release

#### ✅ Dodane — Nowe funkcjonalności
- **Visibility API**: animacje i auto-rotacja wierszy pauzują gdy karta przeglądarki jest ukryta → oszczędność CPU i baterii
- **Clipboard API**: kliknięcie na kartę Unix Timestamp lub ISO 8601 kopiuje wartość do schowka z powiadomieniem toast
- **Konami Code Easter Egg**: sekwencja ↑↑↓↓←→←→BA aktywuje Hacker Mode (czerwona paleta przez 10s)
- **Hacker Mode**: dynamiczna zmiana CSS custom properties przez JavaScript bez przeładowania strony
- **PWA Install Prompt**: obsługa zdarzenia `beforeinstallprompt`, API `window.quantumTime.installPWA()`
- **Auto-rotate toggle**: przyciski ◀ Poprzedni / ⚡ AUTO / Następny ▶ z aria-pressed, toggle Spacja
- **Open Graph meta tags**: og:title, og:description, og:image, og:locale, og:site_name
- **Twitter Cards**: twitter:card, twitter:site, twitter:creator, twitter:image
- **Schema.org JSON-LD**: WebApplication, author, offers — pełna strukturyzacja dla wyszukiwarek
- **Content Security Policy**: meta http-equiv CSP Level 3 z restrykcją connect-src
- **Canonical link**: `<link rel="canonical">` dla SEO
- **will-change CSS**: GPU hints dla animowanych elementów (logo, zegar, canvas, poem-text)
- **Service Worker v5.0**: zaktualizowana nazwa cache `secferro-v5.0.0`, service-worker.js w pre-cache, naprawiony fallback SWR
- **manifest.json v5.0**: orientation → "any", display_override, version field, zrzut ekranu desktop (wide)
- **Naprawa duplikatu HTML**: usunięcie 1811 linii drugiego dokumentu HTML (Cloudflare CDN artefakt)
- **Naprawa literówki**: `anonymllousik.is-a.dev` → `anonymousik.is-a.dev`

#### 🔧 Zmienione
- Wersja w tytule HTML, komentarzu JS, manifeście i service worker zsynchronizowane → v5.0
- `poemDisplay` wzbogacony o `aria-live="polite"` dla screen readerów
- Kontenery kart timestamp z `cursor:pointer` i `title` podpowiedzią
- Particle system: renderowanie pauzuje przez `document.hidden` check w pętli rAF
- Inicjalizacja SW rejestruje handler `updatefound`

#### 🐛 Naprawione
- Duplikacja całego dokumentu HTML (plik miał 3634 zamiast 1824 linii)
- Cache Service Worker wskazywał na v3.0.0 zamiast v5.0.0
- Brak SWR fallback — `staleWhileRevalidate` zwracało undefined przy błędzie sieci
- Brak `manifest.json` w tablicy `CRITICAL_ASSETS` pre-cache
- Literówka w linku social media

---

## [4.0.0] — 2025-12-01

### 🎨 FUSION UI — Redesign

#### Dodane
- System zakładek (4 zakładki): Clock | Unix Time | Projects | About
- Panel Unix Time z historią Unix Epoch, ISO 8601, problemem Y2K38
- Panel Projects z kartami projektów (mouse tracking 3D)
- Panel About z biogramem autora i siatką social media
- Klasa CSS glassmorphism (`--glass-bg`, `--glass-border`, `--glass-blur`)
- 56 CSS custom properties — kompletny design token system
- System cząstek canvas (50 cząstek, połączenia < 150px, rAF)
- Efekt 3D na kartach projektów (mousemove → --mouse-x, --mouse-y)
- Ekran ładowania (loading overlay, timeout 1500ms)
- Selektor strefy czasowej (7 stref + auto)
- Stopka z nawigacją, dokumentacją, legal i ekosystemem
- Linki social media: YouTube, TikTok, Facebook, Instagram, GitHub, Messenger
- Architektura klasy `QuantumTimeFusion` z wzorcem inicjalizacji konstruktorowej

#### Zmienione
- Tytuł HTML: `Quantum Time Terminal v5.0 FUSION 2025 | Elite Edition`
- Monolityczny CSS → 56 design tokens + moduły komponentowe
- Jedna sekcja clocku → 4 zakładki z panelami

---

## [3.0.0] — 2024-11-06

### 🛡️ Brand & PWA Edition

#### Dodane
- Integracja brandu SecFerro Division (logo tarczy SVG)
- Service Worker z 3 strategiami cache
- manifest.json (PWA)
- Ikony SVG inline (192x192, 512x512 maskable)
- Komentarz architektoniczny JS
- Dokumentacja: README.md, CHANGELOG.md, DEPLOYMENT.md, SEO-GUIDE.md
- IMPLEMENTATION_SUMMARY.md (8 faz projektu)

#### Zmienione
- Architektura modułowa klasy JS
- Rozmiar bundle: z ~450KB do ~85KB (-81%)

#### Naprawione
- Font Loading (FOIT → font-display: swap)
- iOS Safari viewport

---

## [2.0.0] — 2024-11-06

### ⚡ Pełna Implementacja JS

#### Dodane
- Kompletna klasa JavaScript (zegar, wiersze, kontrolki)
- Nagłówki bezpieczeństwa (CSP, X-Frame-Options, Referrer-Policy)
- Dostępność WCAG 2.1 AA
- Nawigacja klawiaturą (strzałki, Spacja)
- Responsywny design (mobile-first)
- Monitorowanie FPS i auto-throttling

---

## [1.0.0] — 2024-11-06

### 🎨 Struktura Początkowa

#### Dodane
- Inicjalna struktura HTML
- Stylizacja CSS cyberpunk
- Ekran ładowania w stylu 404
- Tło circuit board
- Efekty glitch
- Konfiguracja panelu UI

---

## Strategia Wersjonowania

| Zmiana | Format |
|--------|--------|
| Breaking API / duże przebudowy | X.0.0 |
| Nowe funkcje (kompatybilne wstecz) | 0.X.0 |
| Bugfixy, bezpieczeństwo, dokumentacja | 0.0.X |

---

## Autorzy

- **FerroART (Anonymousik)** — Creator & Lead Developer
- **SecFerro Division** — Security & UX Consulting
- **Claude (Anthropic)** — Code Review & v5.0 Fixes

---

**© 2026 FerroART® — SecFerro Division**
