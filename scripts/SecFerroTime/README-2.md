# 🛡️ SecFerro Division — Quantum Time Terminal v5.0 FUSION

> Elite cybersecurity PWA z zegarem, Unix Timestamp, ISO 8601, systemem cząstek canvas i Visibility API

[![Version](https://img.shields.io/badge/version-5.0.0-00ff41)](https://github.com/anonymousik)
[![License](https://img.shields.io/badge/license-MIT-00d4ff)](LICENSE)
[![PWA](https://img.shields.io/badge/PWA-enabled-00ff41)](https://web.dev/pwa)
[![WCAG](https://img.shields.io/badge/WCAG-2.1_AA-00d4ff)](https://www.w3.org/WAI/WCAG21/)

---

## 🎯 Przegląd

SecFerro Division Quantum Time Terminal to progresywna aplikacja webowa (PWA) wyświetlająca czas w czasie rzeczywistym z estetyką cyberpunk. Zaimplementowana jako single-file HTML bez zewnętrznych zależności JS.

---

## ✅ Zaimplementowane Funkcje

### Zegar i Czas
- Zegar czasu rzeczywistego (HH:MM:SS), aktualizacja co 1000ms
- Wyświetlanie daty w języku polskim (`toLocaleDateString('pl-PL')`)
- ISO 8601 (pełny format z milisekundami i Z)
- Unix Timestamp (`Math.floor(Date.now() / 1000)`)
- Selektor strefy czasowej (7 stref + auto-detect przez `Intl.DateTimeFormat`)

### UI i Nawigacja
- System 4 zakładek: **Clock** | **Unix Time** | **About** | **Projects**
- Nawigacja klawiaturą: `ArrowLeft/Right` (wiersze), `Tab/Shift+Tab` (zakładki), `Spacja` (toggle auto)
- Efekt 3D na kartach projektów (`mousemove → CSS custom properties`)
- Ekran ładowania (loading overlay, 1500ms)

### Wiersze i Interakcja
- 10 wierszy po polsku z auto-rotacją co 8000ms
- Efekt fade-in/out (300ms opacity transition)
- Przyciski nawigacji: **◀ Poprzedni / ⚡ AUTO / Następny ▶**
- Toggle auto-rotacji przyciskiem lub klawiszem `Spacja`
- `aria-live="polite"` na elemencie wiersza

### Clipboard (nowość v5.0)
- Kliknięcie karty **Unix Timestamp** → kopiuje wartość do schowka
- Kliknięcie karty **ISO 8601** → kopiuje wartość do schowka
- Powiadomienie toast z potwierdzeniem kopiowania

### Easter Egg — Hacker Mode (nowość v5.0)
- Sekwencja **Konami Code**: `↑ ↑ ↓ ↓ ← → ← → B A`
- Aktywuje czerwoną paletę kolorów przez 10 sekund
- Implementacja przez dynamiczną modyfikację CSS custom properties

### Wydajność
- **Visibility API**: animacje i auto-rotacja pauzują gdy karta jest ukryta (oszczędność CPU/baterii)
- **CSS `will-change`**: GPU hints dla animowanych elementów
- System cząstek canvas (50 cząstek, rAF, połączenia < 150px) — pauzuje gdy karta ukryta
- requestAnimationFrame (nie setInterval) dla animacji canvas

### PWA (Progressive Web App)
- Service Worker z 3 strategiami cache (Network-First HTML, Cache-First czcionki, SWR pozostałe)
- manifest.json z ikonami SVG inline (192px + 512px maskable)
- Obsługa `beforeinstallprompt` → `window.quantumTime.installPWA()`
- Strona offline wbudowana w Service Worker
- Aktualizacja SW z powiadomieniem `updatefound`

### SEO (nowość v5.0)
- **Open Graph**: og:title, og:description, og:image, og:locale, og:site_name
- **Twitter Cards**: twitter:card, twitter:creator, twitter:image
- **Schema.org JSON-LD**: WebApplication, author, offers
- **Canonical link**: `<link rel="canonical">`
- **CSP**: Content Security Policy Level 3 via meta http-equiv

### Bezpieczeństwo
- X-Content-Type-Options: nosniff
- X-Frame-Options: SAMEORIGIN
- Referrer-Policy: strict-origin-when-cross-origin
- Content Security Policy (CSP): default-src 'self'
- Brak zewnętrznych trackerów (zero analytics third-party)
- Brak eval(), brak innerHTML assignments

### Dostępność (WCAG 2.1 AA)
- ARIA: `role="tab"`, `aria-selected`, `aria-controls`, `aria-hidden`, `aria-live`
- Nawigacja klawiaturą (w pełni funkcjonalna)
- `prefers-reduced-motion` (CSS)
- `prefers-color-scheme` (CSS)
- Semantyczny HTML5 (header, nav, main, footer, article)

---

## 📦 Pliki Projektu

```
SecFerro-Quantum-Time-v5.0/
├── index.html          (~100KB) — Główna aplikacja (HTML + CSS + JS)
├── manifest.json       (~4KB)   — Konfiguracja PWA
├── service-worker.js   (~8KB)   — Obsługa offline i cache
├── README.md                    — Dokumentacja użytkownika (ten plik)
└── CHANGELOG.md                 — Historia wersji
```

---

## 🚀 Instalacja

### Opcja 1: Bezpośrednie wdrożenie (zalecane)

```bash
# Netlify
netlify deploy --prod --dir=.

# Vercel
vercel --prod

# GitHub Pages
git add . && git commit -m "Deploy SecFerro v5.0" && git push origin main
```

### Opcja 2: Lokalny serwer deweloperski

```bash
# Python
python -m http.server 8000

# Node.js
npx http-server -p 8000
```

Otwórz: `http://localhost:8000`

> **Uwaga**: Service Worker wymaga HTTPS lub localhost. Na innych hostach bez SSL nie zarejestruje się.

---

## ⌨️ Skróty Klawiaturowe

| Skrót | Akcja |
|-------|-------|
| `→ / ←` | Następny / poprzedni wiersz |
| `Tab / Shift+Tab` | Przełącz zakładkę |
| `Spacja` | Toggle auto-rotacja wierszy |
| `↑↑↓↓←→←→BA` | 🔴 Konami Code → Hacker Mode |

---

## 🖱️ Interakcja Myszą

| Akcja | Efekt |
|-------|-------|
| Klik na kartę Unix Timestamp | Kopiuje wartość do schowka |
| Klik na kartę ISO 8601 | Kopiuje wartość do schowka |
| Hover na kartę projektu | Efekt 3D (parallax) |

---

## 🔧 Public API

Dostępne przez `window.quantumTime`:

```javascript
// Nawigacja wierszami
window.quantumTime.nextPoem();
window.quantumTime.prevPoem();
window.quantumTime.displayPoem(3); // konkretny wiersz (0-9)

// Auto-rotacja
window.quantumTime.toggleAutoRotate();

// Hacker Mode (lub Konami Code)
window.quantumTime.activateHackerMode();

// Instalacja PWA
window.quantumTime.installPWA();

// Przełącz zakładkę
window.quantumTime.switchTab('unix'); // clock | unix | projects | about
```

---

## 🔧 Konfiguracja

### Własne wiersze

Edytuj tablicę `this.poems` w `index.html`:

```javascript
this.poems = [
    "Twój wiersz linia 1...\nLinia 2...",
    "Inny wiersz...",
];
```

### Interwał auto-rotacji

Domyślnie 8000ms (8 sekund). Zmień w `startAutoRotate()`:

```javascript
this.autoInterval = setInterval(() => {
    if (this.isVisible) this.nextPoem();
}, 10000); // 10 sekund
```

### Schemat kolorów

Modyfikuj CSS custom properties w `:root`:

```css
:root {
    --hue-primary: 134;  /* Matrix Green */
    --hue-secondary: 340; /* Alert Red */
    --hue-accent: 193;   /* Quantum Cyan */
}
```

---

## 🔒 Bezpieczeństwo — Konfiguracja Serwera

Dla pełnej ochrony dodaj nagłówki HTTP po stronie serwera:

**Nginx:**
```nginx
add_header Content-Security-Policy "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; script-src 'self' 'unsafe-inline';";
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff";
add_header X-Frame-Options "SAMEORIGIN";
add_header Referrer-Policy "strict-origin-when-cross-origin";
```

**Apache (.htaccess):**
```apache
Header set X-Content-Type-Options "nosniff"
Header set X-Frame-Options "SAMEORIGIN"
Header set Referrer-Policy "strict-origin-when-cross-origin"
Header always set Strict-Transport-Security "max-age=31536000"
```

---

## 📊 Metryki Jakości

| Metryka | Wartość |
|---------|---------|
| Rozmiar pliku HTML | ~100 KB |
| Rozmiar Service Worker | ~8 KB |
| Zakładki | 4 |
| Wiersze | 10 |
| CSS custom properties | 56 |
| Cząstki canvas | 50 |
| Obsługiwane strefy czasowe | 7 + auto |
| Zewnętrzne zależności JS | 0 |
| Zewnętrzne trackery | 0 |

---

## 🗺️ Roadmapa

### v5.1 (Planowane)
- [ ] Wsparcie wielojęzyczne (EN, PL, DE)
- [ ] Obraz OG (1200×630px) — zastąpić placeholder
- [ ] Panel ustawień z przełącznikami (animacje, efekt glitch, tryb kompaktowy)
- [ ] Integracja Pomodoro Timer
- [ ] Eksport timestamps do CSV

### v6.0 (Przyszłość)
- [ ] WebSocket synchronizacja czasu z serwerem NTS
- [ ] Weryfikacja timestamp blockchain
- [ ] Motyw własny (color picker dla CSS hue)
- [ ] Widget dla pulpitu (PWA Window Controls Overlay)

---

## 🐛 Rozwiązywanie Problemów

### Service Worker nie rejestruje się
1. Upewnij się, że strona jest serwowana przez HTTPS (lub localhost)
2. Sprawdź, czy `service-worker.js` jest w katalogu głównym (root)
3. Otwórz DevTools → Application → Service Workers

### Czcionki się nie ładują
1. Sprawdź czy CSP pozwala na `fonts.googleapis.com` i `fonts.gstatic.com`
2. Sprawdź połączenie internetowe
3. Czcionki fallback: `monospace` (Share Tech Mono), `sans-serif` (Orbitron)

### Clipboard nie działa
1. Strona musi być serwowana przez HTTPS
2. Przeglądarka musi obsługiwać `navigator.clipboard` (Chrome 66+, Firefox 63+, Safari 13.1+)

---

## 📄 Licencja

MIT License — bezpłatny do użytku osobistego i komercyjnego.

---

## 👤 Autor

**FerroART (Anonymousik)** — SecFerro Division  
🌐 [anonymousik.is-a.dev](https://anonymousik.is-a.dev)  
🎬 [YouTube @ferroart](https://www.youtube.com/@ferroart?sub_confirmation=1)  
💻 [GitHub @anonymousik](https://github.com/anonymousik)

---

**Built with ❤️ by hackers, for hackers — SecFerro Division 2026**
