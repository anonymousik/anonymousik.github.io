Warzone Helper to proste narzędzie pomagające znaleźć idealną konfigurację e grze COD.WARZONE, niezależnie na jakiej grasz platformie! 

Narzędzie dostępne pod adresem: 
https://Anonymousik.is-a.dev/scripts/warzone-helper

Wersja testowa:
https://Anonymousik.is-a.dev/scripts/warzone-helper/beta

Changelog:
https://anonymousik.github.io/anonymousik.is-a.dev/scripts/warzone-helper/changelog.md (już wkrótce)


# Instrukcja wdrożenia na GitHub Pages
Najnowszy build (aktualnie v5.1.0)

> **Czas wdrożenia: ~5 minut.**(Brak Node.js, npm) Projekt to czysty HTML/JS działający w przeglądarce.

---

## Struktura projektu

```
warzone-asystent/
├── index.html      ← aplikacja (React via CDN, Tailwind via CDN)
├── 404.html        ← redirect dla GitHub Pages (SPA routing + ?config= share links)
├── favicon.svg     ← taktyczna ikona celownika
└── README.md       ← ten plik
```

---

## Metoda 1 — Ręczne wdrożenie przez interfejs GitHub (zalecane dla początkujących)

### Krok 1 — Utwórz repozytorium

1. Wejdź na **https://github.com/new**
2. Wypełnij pola:
   - **Repository name:** `warzone-config` (lub dowolna nazwa)
   - **Visibility:** Public ✅ *(GitHub Pages działa bezpłatnie tylko dla publicznych repozytoriów na Free planie)*
   - **Add a README file:** ✅ (opcjonalnie)
3. Kliknij **Create repository**

### Krok 2 — Wgraj pliki

1. Na stronie repozytorium kliknij **Add file → Upload files**
2. Przeciągnij lub wybierz wszystkie pliki projektu:
   - `index.html`
   - `404.html`
   - `favicon.svg`
3. W polu **Commit changes** wpisz np. `feat: initial deploy`
4. Kliknij **Commit changes**

### Krok 3 — Włącz GitHub Pages

1. Wejdź w **Settings** (zakładka u góry repozytorium)
2. W lewym menu kliknij **Pages**
3. W sekcji **Build and deployment** ustaw:
   - **Source:** `Deploy from a branch`
   - **Branch:** `main` / `master` → folder `/` (root)
4. Kliknij **Save**

### Krok 4 — Sprawdź wdrożenie

Po ~60–90 sekundach na stronie Settings → Pages pojawi się adres:

```
https://<twój-login>.github.io/<nazwa-repo>/
```

Przykład: `https://sekferro.github.io/warzone-config/`

> **Uwaga:** Jeśli repozytorium ma nazwę `<login>.github.io`, aplikacja będzie dostępna pod adresem `https://<login>.github.io/` (bez podkatalogu).

---

## Metoda 2 — Wdrożenie przez terminal (Git CLI)

### Wymagania

- Git zainstalowany lokalnie (`git --version`)
- Konto GitHub z skonfigurowanym SSH lub tokenem HTTPS

```bash
# 1. Sklonuj lub utwórz lokalne repo
git clone https://github.com/<twój-login>/warzone-config.git
cd warzone-config

# 2. Skopiuj pliki projektu do katalogu repo
cp /ścieżka/do/projektu/{index.html,404.html,favicon.svg} .

# 3. Zatwierdź i wypchnij
git add .
git commit -m "feat: deploy WZ Operator Config v5.0"
git push origin main

# 4. Włącz GitHub Pages (jednorazowo przez API lub UI)
# GitHub CLI:
gh repo edit --enable-pages --pages-branch main
```

---

## Metoda 3 — GitHub Actions (CI/CD, auto-deploy przy każdym push)

Utwórz plik `.github/workflows/deploy.yml`:

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [ main ]

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Pages
        uses: actions/configure-pages@v5

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: '.'  # cały root — index.html, 404.html, favicon.svg

      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

Po dodaniu tego pliku do repo — każdy `git push` automatycznie aktualizuje stronę.

---

## Własna domena (opcjonalnie)

### Konfiguracja CNAME

1. Utwórz plik `CNAME` w root projektu z treścią:
   ```
   config.twojadomena.pl
   ```
2. W panelu DNS domeny dodaj rekord:
   ```
   Type: CNAME
   Name: config
   Value: <twój-login>.github.io
   TTL: 3600
   ```
3. W GitHub Settings → Pages zaznacz **Enforce HTTPS** ✅

> DNS propaguje się w ciągu 15 minut do 48 godzin.

---

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---|---|
| Strona pokazuje 404 | Odczekaj 2–3 min po pierwszym deploy; sprawdź czy `index.html` jest w root, nie w podfolderze |
| Link `?config=...` nie działa po odświeżeniu | Sprawdź czy `404.html` jest wgrany — to on obsługuje SPA redirect |
| Ikona nie ładuje się | Sprawdź czy `favicon.svg` jest w tym samym katalogu co `index.html` |
| Strona ładuje się bez stylów | CDN Tailwind / React wymaga połączenia z internetem; nie działa offline |
| `gh-pages` branch pojawia się zamiast `main` | W Settings → Pages zmień source branch na `main` |

---

## Aktualizacja aplikacji

```bash
# Po każdej modyfikacji index.html:
git add index.html
git commit -m "fix: opis zmiany"
git push origin main
# GitHub Pages zaktualizuje się automatycznie w ciągu ~60 sekund
```

---

## Weryfikacja dostępności i wydajności

Po wdrożeniu możesz sprawdzić jakość strony w Chrome DevTools:

```
F12 → Lighthouse → Analyze page load
```

Oczekiwane wyniki:
- **Performance:** 90+
- **Accessibility:** 95+ (ARIA labels, keyboard nav, focus visible, skip link, reduced motion)
- **Best Practices:** 95+
- **SEO:** 90+

---

## Technologia

| Warstwa | Technologia |
|---|---|
| Framework UI | React 18 (UMD via unpkg CDN) |
| JSX transpiler | Babel Standalone (browser-side) |
| Style | Tailwind CSS (JIT CDN) + Custom CSS (design tokens) |
| Ikony | Lucide Icons (UMD) |
| Czcionki | Teko (display) + JetBrains Mono (HUD) + Inter (body) |
| Hosting | GitHub Pages (static) |
| Build step | **Brak** — zero konfiguracji |
| State | React useState / useMemo |
| Persist | URL query string (`?config=base64`) |

---

*Warzone Helper v5.1.0 — zbudowane bez frameworków, bez modułów nodejs, bez lokalnych zależności*
