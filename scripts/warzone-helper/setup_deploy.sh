#!/bin/bash

# --- AUTOMATYCZNY INSTALATOR WARZONE HQ ---
# Autor: Anonymousik (FerroART)
# Domena docelowa: anonymousik.is-a.dev/scripts/warzone-helper
# wersja: v0.0.1beta(15.06.2026)

set -e # Zatrzymaj skrypt przy jakimkolwiek błędzie

echo "=========================================================="
echo "    ROZPOCZYNAM AUTOMATYCZNE WDROŻENIE WARZONE HQ         "
echo "=========================================================="

# 1. Pobieranie danych uwierzytelniających
read -p "Podaj swoją nazwę użytkownika na GitHub: " GH_USER
if [ -z "$GH_USER" ]; then
    echo "Błąd: Nazwa użytkownika nie może być pusta!"
    exit 1
fi

# Domyślna nazwa repozytorium odpowiadająca strukturze folderów /scripts/warz
REPO_NAME="anonymousik.is-a.dev"

echo "-> Tworzenie projektu Vite + React..."
npm create vite@latest warzone-helper -- --template react

echo "-> Przechodzenie do katalogu projektu..."
cd warzone-helper

echo "-> Instalacja zależności (React, Tailwind, Lucide, gh-pages)..."
npm install
npm install -D tailwindcss postcss autoprefixer
npm install lucide-react
npm install gh-pages --save-dev

echo "-> Inicjalizacja konfiguracji Tailwind CSS..."
npx tailwindcss init -p

# Konfiguracja tailwind.config.js
cat << 'EOF' > tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
EOF

# Czyszczenie i nadpisywanie stylów index.css
cat << 'EOF' > src/index.css
@tailwind base;
@tailwind components;
@tailwind utilities;
EOF

# Usuwanie zbędnego pliku App.css
rm -f src/App.css

echo "-> Implementacja kodu Asystenta Taktycznego do src/App.jsx..."
cat << 'EOF' > src/App.jsx
import React, { useState, useMemo, useEffect } from 'react';
import { 
  Gamepad2, Crosshair, Monitor, Headphones, Info, Zap, Target, 
  Activity, AlertTriangle, MapPin, Laptop, 
  Tv, Sparkles, Check, ChevronDown, ChevronUp, Share2, Copy, 
  RefreshCw, Download, Search, CheckCircle2, AlertCircle, ExternalLink
} from 'lucide-react';

const INITIAL_VALUES = {
  layout: 'Taktyczny',
  vib: false,
  trig: false,
  sens: 1.6,
  dz_l_min: 3,
  dz_l_max: 50,
  dz_r_max: 99,
  dz_trig: 0,
  ads_low: 0.80,
  ads_high: 1.00,
  trans: 'Natychmiastowy',
  curve: 'Dynamiczny',
  assist: true,
  sprint: 'Auto. Sprint Taktyczny',
  sprint_del: 0,
  slide: 'Hybrydowe',
  para: false,
  mantle: false,
  armor: 'Zastosuj wszystkie',
  interact: 'Priorytet interakcji',
  fov: 110,
  ads_fov: 'Zależne (Affected)',
  w_fov: 'Szerokie (Wide)',
  cas: 90,
  blur: false,
  shake: 50,
  filter: 'Filtr 2 (Oba)',
  hud: 'Minimalne (Środek)',
  cross: 'Większa / Żółta',
  radar: 'Kwadrat / Kontury Wł.',
  audio: 'Sucker Punch',
  mono: false
};

const PRESETS = {
  performance: {
    id: 'performance',
    name: 'Turniejowy (Input Lag Cut)',
    desc: 'Najniższe możliwe opóźnienia sprzętowe, zoptymalizowane strefy martwe do agresywnej kontroli odrzutu i walki wręcz.',
    badge: 'PRO PERFORMANCE',
    color: 'border-red-500/50 bg-red-950/40 text-red-400',
    metrics: { fps: '120 FPS (Locked)', lag: '2.8ms', cpu: 'Niskie', fov: '110 FOV' },
    overrides: {
      vib: false, trig: false, sens: 1.8, dz_l_min: 2, dz_l_max: 45, dz_trig: 0,
      ads_low: 0.75, ads_high: 0.90, curve: 'Dynamiczny', assist: true,
      sprint: 'Auto. Sprint Taktyczny', sprint_del: 0, slide: 'Hybrydowe', fov: 110, ads_fov: 'Zależne (Affected)'
    }
  },
  balanced: {
    id: 'balanced',
    name: 'Zbalansowany (Meta-Play)',
    desc: 'Ustawienia gwarantujące najwyższą stabilność celowania, doskonałą widoczność celów i zbalansowane opóźnienia ruchowe.',
    badge: 'BALANCED META',
    color: 'border-amber-500/50 bg-amber-950/40 text-amber-400',
    metrics: { fps: '60-120 FPS', lag: '4.2ms', cpu: 'Średnie', fov: '115 FOV' },
    overrides: {
      vib: false, trig: false, sens: 1.6, dz_l_min: 4, dz_l_max: 50, dz_trig: 0,
      ads_low: 0.80, ads_high: 1.00, curve: 'Dynamiczny', assist: true,
      sprint: 'Auto. Sprint Taktyczny', slide: 'Hybrydowe', fov: 115, ads_fov: 'Zależne (Affected)', cas: 90
    }
  },
  movement: {
    id: 'movement',
    name: 'Ruch i Demon Slide',
    desc: 'Konfiguracja pod maksymalną zwrotność, natychmiastowe slajdy i łamanie kamer przeciwników na bliskim dystansie.',
    badge: 'AGILE DEMON',
    color: 'border-cyan-500/50 bg-cyan-950/40 text-cyan-400',
    metrics: { fps: '120 FPS', lag: '3.1ms', cpu: 'Wysokie', fov: '120 FOV' },
    overrides: {
      vib: false, trig: false, sens: 2.2, dz_l_min: 3, dz_l_max: 30, dz_trig: 0,
      ads_low: 0.85, ads_high: 1.00, curve: 'Dynamiczny', assist: true,
      sprint: 'Auto. Sprint Taktyczny', slide: 'Hybrydowe', fov: 120, ads_fov: 'Zależne (Affected)'
    }
  }
};

const METADATA = {
  controller: {
    title: 'Kontroler & Ruch',
    icon: Gamepad2,
    warning: "Aby zredukować Input Lag na konsoli do minimum, zawsze łącz kontroler kablem USB i w opcjach systemu zmień 'Metodę komunikacji' na 'Kabel USB'.",
    items: [
      { id: 'layout', name: 'Układ przycisków', isToggle: false, isSelect: true, options: ['Domyślny', 'Taktyczny', 'Weteran taktyczny'], paths: { PS4: 'Kontroler -> Układ przycisków', PS5: 'Kontroler -> Układ przycisków', PC: 'Controller -> Button Layout' }, beg: 'Standardowy układ. Wybierz "Taktyczny", jeśli nie posiadasz łopatek z tyłu kontrolera.', adv: 'Układ Taktyczny przenosi wślizg i kucanie pod prawy analog (R3). Pozwala to na ciągły ruch i celowanie podczas "slide cancel" bez odrywania kciuka.' },
      { id: 'vib', name: 'Wibracje kontrolera', isToggle: true, paths: { PS4: 'Ustawienia -> Urządzenia -> Kontrolery -> Wibracje', PS5: 'Akcesoria -> Kontrolery -> Siła wibracji -> Wyłącz', PC: 'Controller -> Vibration -> Off' }, beg: 'Ciągłe wibracje drastycznie utrudniają mikrokorektę celownika. Wyłącz je.', adv: 'Wibracje destabilizują pamięć mięśniową dłoni. Profesjonalni gracze całkowicie usuwają moduły wibracyjne z gamepadów.' },
      { id: 'trig', name: 'Efekt triggerów (L2/R2)', isToggle: true, paths: { PS4: 'Niedostępne na PS4', PS5: 'Akcesoria -> Kontrolery -> Efekt Triggerów -> Wyłącz', PC: 'Controller -> Trigger Effect -> Off' }, beg: 'Usuwa fizyczny opór spustów, co pozwala na szybszą inicjację strzału.', adv: 'Eliminuje sztuczny opór mechaniczny, skracając czas reakcji (L2/R2 Deadzone) do absolutnego zera.' },
      { id: 'sens', name: 'Czułość drążków (Pion/Poziom)', isToggle: false, visual: 'slider', min: 0.5, max: 4.0, step: 0.1, paths: { PS4: 'Kontroler -> Czułość drążków', PS5: 'Kontroler -> Czułość drążków', PC: 'Controller -> Stick Sensitivity' }, beg: 'Szybkość kamery. Wartość 1.6 to stabilne i precyzyjne tempo obrotu odpowiadające klasycznemu 7/7.', adv: 'Zapewnia idealny kompromis między dynamicznym obrotem (flick) a stabilnym śledzeniem celu (tracking) pod asystę rotacyjną.' },
      { id: 'dz_l_min', name: 'Minimalna strefa martwa lewej gałki', isToggle: false, visual: 'slider', min: 0, max: 20, step: 1, paths: { PS4: 'Kontroler -> Strefy Martwe -> Min. Lewa', PS5: 'Kontroler -> Strefy Martwe -> Min. Lewa', PC: 'Inputs Deadzone -> Left Stick Min' }, beg: 'Margines ruchu potrzebny do poruszenia postaci. Ustaw tak nisko, jak to możliwe, bez samoczynnego ruchu (driftu).', adv: 'Ultra niska wartość pozwala na błyskawiczne rozpoczęcie strafe\'owania, co automatycznie aktywuje Rotational Aim Assist.' },
      { id: 'dz_l_max', name: 'Maksymalna strefa martwa lewej gałki', isToggle: false, visual: 'slider', min: 10, max: 100, step: 5, paths: { PS4: 'Kontroler -> Strefy Martwe -> Max Lewa', PS5: 'Kontroler -> Strefy Martwe -> Max Lewa', PC: 'Inputs Deadzone -> Left Stick Max' }, beg: 'Głębokość wychylenia gałki wymagana do pełnego sprintu.', adv: 'Wartość 50-60 przyspiesza inicjację sprintu taktycznego o cenne milisekundy przy minimalnym ruchu kciuka.' },
      { id: 'dz_r_max', name: 'Maksymalna strefa martwa prawej gałki', isToggle: false, visual: 'slider', min: 50, max: 100, step: 1, paths: { PS4: 'Kontroler -> Strefy Martwe -> Max Prawa', PS5: 'Kontroler -> Strefy Martwe -> Max Prawa', PC: 'Inputs Deadzone -> Right Stick Max' }, beg: 'Zapewnia osiągnięcie maksymalnej prędkości obrotu przy krawędzi analogu.', adv: 'Ustawienie na 99 gwarantuje, że lekki nacisk na obudowę gałki nie zablokuje maksymalnego wektora prędkości kamery.' },
      { id: 'dz_trig', name: 'Strefa martwa L2 / R2', isToggle: false, visual: 'slider', min: 0, max: 10, step: 1, paths: { PS4: 'Kontroler -> Strefy Martwe -> Spusty', PS5: 'Kontroler -> Strefy Martwe -> Spusty', PC: 'Inputs Deadzone -> L2/R2' }, beg: 'Próg wciśnięcia wymagany do rejestracji celowania i strzału.', adv: 'Wartość 0 aktywuje akcję przy najmniejszym kontakcie ze spustem, emulując fizyczne przyciski typu "clicky trigger".' }
    ]
  },
  aiming: {
    title: 'Celowanie',
    icon: Crosshair,
    items: [
      { id: 'ads_low', name: 'Mnożnik ADS (Niskie powiększenie)', isToggle: false, visual: 'slider', min: 0.50, max: 1.50, step: 0.05, paths: { PS4: 'Celowanie -> Mnożnik ADS (Niski)', PS5: 'Celowanie -> Mnożnik ADS (Niski)', PC: 'Aiming -> ADS Sensitivity Multiplier (Low Zoom)' }, beg: 'Czułość przy celowaniu z kolimatorów i celowników mechanicznych.', adv: 'Mnożnik 0.80 pozwala na łatwiejsze korygowanie celownika na dalekim dystansie i wybacza drobne błędy motoryczne.' },
      { id: 'ads_high', name: 'Mnożnik ADS (Wysokie powiększenie)', isToggle: false, visual: 'slider', min: 0.50, max: 1.50, step: 0.05, paths: { PS4: 'Celowanie -> Mnożnik ADS (Wysoki)', PS5: 'Celowanie -> Mnożnik ADS (Wysoki)', PC: 'Aiming -> ADS Sensitivity Multiplier (High Zoom)' }, beg: 'Szybkość ruchu celownika podczas używania lunet snajperskich.', adv: 'Utrzymanie wartości zbliżonej do 1.00 pozwala zachować spójność pamięci mięśniowej podczas tzw. "quick scoping".' },
      { id: 'trans', name: 'Czas przejścia czułości celownika', isToggle: false, isSelect: true, options: ['Natychmiastowy', 'Po przybliżeniu', 'Stopniowy'], paths: { PS4: 'Celowanie -> Czas przejścia czułości', PS5: 'Celowanie -> Czas przejścia czułości', PC: 'Aiming -> ADS Sensitivity Transition Timing' }, beg: 'Moment, w którym czułość kamery ulega zmniejszeniu podczas celowania.', adv: 'Ustawienie "Natychmiastowy" eliminuje nieliniowe zmiany prędkości kamery w trakcie animacji podnoszenia broni.' },
      { id: 'curve', name: 'Krzywa reakcji celowania', isToggle: false, isSelect: true, options: ['Standardowa', 'Liniowa', 'Dynamiczna'], paths: { PS4: 'Celowanie -> Typ krzywej reakcji', PS5: 'Celowanie -> Typ krzywej reakcji', PC: 'Aiming -> Aim Response Curve Type' }, beg: 'Sposób, w jaki gra przelicza wychylenie gałki na prędkość obrotu.', adv: 'Dynamiczna krzywa (S-Shape) oferuje ekstremalną precyzję w centrum i błyskawiczne przyspieszenie przy skrajnym wychyleniu.' },
      { id: 'assist', name: 'Asysta celowania (Aim Assist)', isToggle: true, paths: { PS4: 'Celowanie -> Asysta celowania', PS5: 'Celowanie -> Asysta celowania', PC: 'Aiming -> Target Aim Assist' }, beg: 'Wbudowana pomoc w celowaniu. Nigdy jej nie wyłączaj.', adv: 'Kluczowy element gry na kontrolerze. Aktywuje tzw. "Rotational Aim Assist" (magnetyzm) podczas ciągłego mikro-poruszania lewą gałką.' }
    ]
  },
  movement: {
    title: 'Mechanika Ruchu',
    icon: Activity,
    items: [
      { id: 'sprint', name: 'Zachowanie sprintu', isToggle: false, isSelect: true, options: ['Ręczny', 'Automatyczny', 'Auto. Sprint Taktyczny'], paths: { PS4: 'Rozgrywka -> Automatyczny sprint', PS5: 'Rozgrywka -> Automatyczny sprint', PC: 'Gameplay -> Automatic Sprint' }, beg: 'Automatycznie uruchamia najszybszy bieg postaci. Oszczędza stawy kontrolera.', adv: 'Automatyczny Sprint Taktyczny minimalizuje opóźnienie przed wślizgiem i pozwala na natychmiastową ucieczkę.' },
      { id: 'sprint_del', name: 'Opóźnienie sprintu', isToggle: false, visual: 'slider', min: 0, max: 10, step: 1, paths: { PS4: 'Rozgrywka -> Opóźnienie sprintu taktycznego', PS5: 'Rozgrywka -> Opóźnienie sprintu taktycznego', PC: 'Gameplay -> Tactical Sprint Delay' }, beg: 'Usuwa bufor czasowy przed rozpoczęciem pełnego sprintu.', adv: '0ms. Gwarantuje całkowity brak opóźnień między intencją ruchu a reakcją silnika gry.' },
      { id: 'slide', name: 'Wślizg i Padanie', isToggle: false, isSelect: true, options: ['Tapnięcie', 'Przytrzymanie', 'Hybrydowe'], paths: { PS4: 'Rozgrywka -> Zachowanie wślizgu', PS5: 'Rozgrywka -> Zachowanie wślizgu', PC: 'Gameplay -> Slide/Dive Behavior' }, beg: 'Wpływa na to, jak szybko postać zaczyna robić wślizg po kliknięciu przycisku.', adv: 'Hybrydowe/Tapnięcie drastycznie skraca czas reakcji, eliminując potrzebę przytrzymywania przycisku i opóźnienie animacji.' },
      { id: 'para', name: 'Automatyczny spadochron', isToggle: true, paths: { PS4: 'Rozgrywka -> Spadochron', PS5: 'Rozgrywka -> Spadochron', PC: 'Gameplay -> Auto Parachute Deploy' }, beg: 'Wyłącz, aby lądować tuż nad ziemią i ubiec przeciwników lądujących obok.', adv: 'Zapobiega niechcianej animacji otwarcia spadochronu w pobliżu wysokich przeszkód i dachów budynków.' },
      { id: 'mantle', name: 'Asysta wspinania', isToggle: true, paths: { PS4: 'Rozgrywka -> Autowspinanie', PS5: 'Rozgrywka -> Autowspinanie', PC: 'Gameplay -> Ground Mantle' }, beg: 'Blokuje samoczynne wspinanie się na obiekty podczas walki z bliska.', adv: 'Wyłączenie zapobiega przypadkowemu utknięciu w animacji wspinania ("Mantle Lock") w trakcie wymiany ognia przy osłonach.' },
      { id: 'armor', name: 'Zachowanie płyt pancerza', isToggle: false, isSelect: true, options: ['Zastosuj jedną', 'Zastosuj wszystkie'], paths: { PS4: 'Rozgrywka -> Zachowanie pancerza', PS5: 'Rozgrywka -> Zachowanie pancerza', PC: 'Gameplay -> Armor Plate Behavior' }, beg: 'Pozwala na automatyczne wkładanie kolejnych płyt pancerza bez klikania.', adv: 'Ustawienie "Zastosuj wszystkie" pozwala skupić się na poruszaniu i obserwowaniu otoczenia podczas regeneracji pancerza.' },
      { id: 'interact', name: 'Interakcja i przeładowanie', isToggle: false, isSelect: true, options: ['Domyślne', 'Priorytet przeładowania', 'Priorytet interakcji'], paths: { PS4: 'Rozgrywka -> Interakcja / Przeładowanie', PS5: 'Rozgrywka -> Interakcja / Przeładowanie', PC: 'Gameplay -> Interact/Reload Behavior' }, beg: 'Zmienia zachowanie przycisku przy otwieraniu skrzyń i podnoszeniu przedmiotów.', adv: 'Priorytet Interakcji pozwala na błyskawiczne zbieranie łupu pojedynczym dotknięciem, bez konieczności przytrzymywania.' }
    ]
  },
  graphics: {
    title: 'Grafika i Widok',
    icon: Monitor,
    warning: "Odpowiednie ustawienia graficzne poprawiają nie tylko widoczność wrogów w cieniu, ale mogą również zwiększyć płynność i zredukować Input Lag.",
    items: [
      { id: 'fov', name: 'Pole widzenia (FOV)', isToggle: false, visual: 'slider', min: 80, max: 120, step: 5, paths: { PS4: 'Grafika -> Widok -> Pole widzenia', PS5: 'Grafika -> Widok -> Pole widzenia', PC: 'Graphics -> View -> Field of View' }, beg: 'Szerokość obrazu. Wyższa wartość pozwala zauważyć wrogów na krawędziach ekranu.', adv: 'Szeroki FOV (110-120) optycznie zmniejsza odrzut broni (visual recoil) i poprawia percepcję przestrzeni wokół postaci.' },
      { id: 'ads_fov', name: 'Pole widzenia celownika', isToggle: false, isSelect: true, options: ['Niezależne (Independent)', 'Zależne (Affected)'], paths: { PS4: 'Grafika -> Widok -> ADS FOV', PS5: 'Grafika -> Widok -> ADS FOV', PC: 'Graphics -> View -> ADS Field of View' }, beg: 'Zależne (Affected) sprawia, że broń zachowuje stałą proporcję wielkości przy przybliżeniu.', adv: 'Affected wiąże pole widzenia ADS z Twoim globalnym FOV. Drastycznie redukuje wizualne trzęsienie celownika.' },
      { id: 'w_fov', name: 'Pole widzenia broni', isToggle: false, isSelect: true, options: ['Domyślne', 'Wąskie', 'Szerokie (Wide)'], paths: { PS4: 'Grafika -> Widok -> Pole broni', PS5: 'Grafika -> Widok -> Pole broni', PC: 'Graphics -> View -> Weapon Field of View' }, beg: 'Określa, jak duża wydaje się trzymana w rękach broń.', adv: 'Ustawienie "Szerokie" sprawia, że broń zajmuje znacznie mniej miejsca na ekranie, odsłaniając dolną strefę wizualną.' },
      { id: 'cas', name: 'FidelityFX CAS Wyostrzanie', isToggle: false, visual: 'slider', min: 0, max: 100, step: 5, paths: { PS4: 'Grafika -> Jakość -> Skalowanie i wyostrzanie', PS5: 'Grafika -> Jakość -> Skalowanie i wyostrzanie', PC: 'Graphics -> Quality -> Upscaling/Sharpening' }, beg: 'Zaawansowany filtr wyostrzający krawędzie bez utraty wydajności.', adv: 'Wartość 80-100% całkowicie eliminuje rozmycie powodowane przez antyaliasing (TAA) i uwydatnia sylwetki przeciwników.' },
      { id: 'blur', name: 'Motion Blur (Świat / Broń)', isToggle: true, paths: { PS4: 'Grafika -> Rozmycie świata / broni', PS5: 'Grafika -> Rozmycie świata / broni', PC: 'Graphics -> Post Processing -> Motion Blur' }, beg: 'Efekt rozmycia podczas obrotu kamery. Zawsze wyłącz.', adv: 'Wyłączenie rozmycia poprawia klarowność obrazu podczas dynamicznych uników i odciąża układ graficzny.' },
      { id: 'shake', name: 'Ruch kamery pierwszoosobowej', isToggle: false, visual: 'slider', min: 50, max: 100, step: 10, paths: { PS4: 'Grafika -> Widok -> Ruch kamery', PS5: 'Grafika -> Widok -> Ruch kamery', PC: 'Graphics -> View -> Camera Movement' }, beg: 'Intensywność trzęsienia obrazu podczas wybuchów i nalotów artyleryjskich.', adv: 'Zmniejszenie do minimalnych 50% jest krytyczne dla utrzymania ostrości celowania w chaotycznych sytuacjach.' }
    ]
  },
  ui_audio: {
    title: 'Interfejs & Dźwięk',
    icon: Headphones,
    items: [
      { id: 'filter', name: 'Filtr kolorów', isToggle: false, isSelect: true, options: ['Brak', 'Filtr 1', 'Filtr 2 (Oba)', 'Filtr 3'], paths: { PS4: 'Interfejs -> Dostosowanie kolorów', PS5: 'Interfejs -> Dostosowanie kolorów', PC: 'Interface -> Color Customization -> Filter' }, beg: 'Filtr podbija nasycenie i kontrast, ułatwiając dostrzeżenie przeciwników.', adv: 'Zastosowanie Filtru 2 z celem "Oba" (Both) i intensywnością 100% wyciąga wrogów z głębokich, ciemnych cieni.' },
      { id: 'hud', name: 'Marginesy bezpieczne HUD', isToggle: false, isSelect: true, options: ['Szerokie', 'Średnie', 'Minimalne (Środek)'], paths: { PS4: 'Interfejs -> HUD -> Bezpieczna strefa', PS5: 'Interfejs -> HUD -> Bezpieczna strefa', PC: 'Interface -> HUD -> Safe Area' }, beg: 'Przesuwa minimapę i stan zdrowia bliżej środka ekranu.', adv: 'Maksymalnie ściśnięty HUD drastycznie skraca czas potrzebny na zerknięcie na minimapę w trakcie dynamicznego starcia.' },
      { id: 'cross', name: 'Środkowa kropka celownika', isToggle: false, isSelect: true, options: ['Wyłączona', 'Domyślna', 'Większa / Żółta'], paths: { PS4: 'Interfejs -> HUD -> Środkowa kropka', PS5: 'Interfejs -> HUD -> Środkowa kropka', PC: 'Interface -> HUD -> Center Dot' }, beg: 'Jasna, stała kropka pomagająca w orientacji, gdzie celujesz przed przybliżeniem.', adv: 'Klucz do mistrzowskiego pozycjonowania celownika (Centering). Żółty kolor jest najbardziej kontrastowy na większości map.' },
      { id: 'radar', name: 'Minimapa', isToggle: false, isSelect: true, options: ['Okrągła', 'Kwadrat / Kontury Wł.'], paths: { PS4: 'Interfejs -> HUD -> Kształt minimapy', PS5: 'Interfejs -> HUD -> Kształt minimapy', PC: 'Interface -> HUD -> Minimap Shape' }, beg: 'Kształt radaru w rogu ekranu.', adv: 'Kwadratowa minimapa wyświetla o ponad 20% więcej obszaru gry niż okrągła, co pozwala szybciej namierzyć wrogów z UAV.' },
      { id: 'audio', name: 'Miks audio', isToggle: false, isSelect: true, options: ['Kino domowe', 'Słuchawki', 'Sucker Punch', 'Wzmocnienie basów'], paths: { PS4: 'Audio -> Miks dźwięku', PS5: 'Audio -> Miks dźwięku', PC: 'Audio -> Volumes -> Audio Mix' }, beg: 'Wpływa na częstotliwości dźwiękowe odpowiedzialne za kroki.', adv: 'Sucker Punch (lub alternatywnie Boost Low / Home Theater) kompresuje pasmo akustyczne tak, by kroki były słyszalne ponad wybuchami.' },
      { id: 'mono', name: 'Dźwięk Mono', isToggle: true, paths: { PS4: 'Audio -> Dźwięk Mono -> Wyłącz', PS5: 'Audio -> Dźwięk Mono -> Wyłącz', PC: 'Audio -> Audio -> Mono Audio -> Off' }, beg: 'Łączy oba kanały w jeden. Zostaw absolutnie WYŁĄCZONE.', adv: 'Włączenie dźwięku mono uniemożliwia jakąkolwiek lokalizację kierunkową wrogów (lewo-prawo).' }
    ]
  }
};

const SURVEY_QUESTIONS = [
  {
    id: 'platform',
    question: 'Na jakiej platformie grasz najczęściej?',
    options: [
      { val: 'PS4', label: 'PlayStation 4 / Slim', desc: 'Wymaga maksymalnej optymalizacji stabilności klatek na sekundę.' },
      { val: 'PS4 Pro', label: 'PlayStation 4 Pro', desc: 'Możliwe skalowanie rozdzielczości i użycie FidelityFX CAS.' },
      { val: 'PS5', label: 'PlayStation 5', desc: 'Obsługuje ultra-płynne 120 FPS, natychmiastowe reakcje i szeroki FOV.' },
      { val: 'PC', label: 'Komputer osobisty (PC)', desc: 'Maksymalny potencjał graficzny oraz dedykowane skróty ustawień.' }
    ]
  },
  {
    id: 'playstyle',
    question: 'Jaki styl gry najbardziej Ci odpowiada?',
    options: [
      { val: 'cqc', label: 'Agresywny Rusher (CQC)', desc: 'Ciągła walka z bliska, slajdy, skoki i maksymalna dynamika ruchu.', icon: Zap },
      { val: 'balanced', label: 'Zbalansowany / Taktyczny', desc: 'Wycieranie stref, flandry i kontrola odrzutu na średni dystans.', icon: Target },
      { val: 'sniper', label: 'Snajper dystansowy', desc: 'Precyzyjna kontrola oddechu, wolniejsza i dokładniejsza czułość ADS.', icon: Monitor }
    ]
  },
  {
    id: 'display',
    question: 'Z jakiego ekranu korzystasz?',
    options: [
      { val: 'tv_standard', label: 'Zwykły Telewizor TV', desc: 'Może posiadać wyższy Input Lag. Zalecane ułatwienia stabilności wizualnej.' },
      { val: 'tv_game', label: 'TV z dedykowanym "Trybem Gry"', desc: 'Niski czas reakcji matrycy i dobra widoczność szczegółów w cieniach.' },
      { val: 'monitor', label: 'Monitor Gamingowy (niski Input Lag)', desc: 'Maksymalny czas reakcji (1ms/0.5ms). Pozwala na najmniejsze strefy martwe.' }
    ]
  },
  {
    id: 'controller',
    question: 'Jakiego typu kontrolera używasz?',
    options: [
      { val: 'standard', label: 'Standardowy kontroler fabryczny', desc: 'Brak łopatek z tyłu. Zostanie ustawiony układ Taktyczny.' },
      { val: 'pro', label: 'Pad Wyczynowy (Łopatki / DualSense Edge)', desc: 'Posiadasz łopatki z tyłu. Zostawiamy domyślne mapowanie.' }
    ]
  }
];

const TacticalControllerVisualizer = ({ layout }) => {
  return (
    <div className="w-full max-w-xs mx-auto p-4 bg-zinc-950/90 rounded-2xl border border-zinc-800 flex flex-col items-center">
      <h4 className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider mb-3">Podgląd Układu: <span className="text-amber-500">{layout}</span></h4>
      
      <svg viewBox="0 0 400 280" className="w-full h-auto max-h-[160px] text-zinc-700 fill-zinc-900 stroke-zinc-700 stroke-[4]">
        <path d="M100 60 C140 40, 260 40, 300 60 C340 70, 390 140, 370 230 C360 260, 310 260, 280 220 C250 180, 150 180, 120 220 C90 260, 40 260, 30 230 C10 140, 60 70, 100 60 Z" />
        <rect x="140" y="65" width="120" height="60" rx="10" className="fill-zinc-800 stroke-zinc-700" />
        <circle cx="150" cy="170" r="28" className="fill-zinc-950 stroke-zinc-700" />
        <circle cx="150" cy="170" r="14" className="fill-zinc-800" />
        <circle cx="250" cy="170" r="28" className={`fill-zinc-950 transition-colors ${layout !== 'Domyślny' ? 'stroke-amber-500' : 'stroke-zinc-700'}`} />
        <circle cx="250" cy="170" r="14" className="fill-zinc-800" />
        <text x="250" y="215" className={`text-[10px] font-bold text-center text-xs fill-amber-500 font-sans`} textAnchor="middle">
          {layout !== 'Domyślny' ? 'R3: Wślizg' : 'R3: Walka wręcz'}
        </text>
        <path d="M70 120 H90 V140 H70 Z M80 110 H90 V150 H80 Z" className="fill-zinc-800" />
        <circle cx="320" cy="130" r="12" className={`transition-colors ${layout !== 'Domyślny' ? 'fill-red-950/40 stroke-red-500' : 'fill-zinc-800'}`} />
        <text x="320" y="134" className="text-[10px] font-bold fill-zinc-400" textAnchor="middle">○</text>
        <text x="325" y="152" className="text-[9px] fill-zinc-500" textAnchor="start">
          {layout !== 'Domyślny' ? 'Cios wręcz' : 'Kucanie'}
        </text>
        <circle cx="295" cy="155" r="12" className="fill-zinc-800" />
        <text x="295" y="159" className="text-[10px] font-bold fill-zinc-400" textAnchor="middle">×</text>
        <path d="M90 30 H130 V50 H90 Z" />
        <path d="M270 30 H310 V50 H270 Z" />
      </svg>
    </div>
  );
};

const FovSimulator = ({ fovValue, adsFov }) => {
  return (
    <div className="w-full bg-zinc-950 rounded-2xl border border-zinc-800 p-4 overflow-hidden relative">
      <div className="flex justify-between items-center mb-3">
        <h4 className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">Interaktywny Symulator Widoku (FOV)</h4>
        <span className="text-xs font-mono font-bold text-cyan-400">Ustawiono: {fovValue}° FOV</span>
      </div>

      <div className="relative aspect-video w-full bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden flex items-center justify-center">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#1f2937_1px,transparent_1px),linear-gradient(to_bottom,#1f2937_1px,transparent_1px)] bg-[size:4rem_4rem] opacity-20" />
        
        <div 
          className="absolute left-0 top-0 bottom-0 w-12 bg-zinc-800/80 border-r border-zinc-700 transition-all duration-300 flex items-center justify-center text-[10px] text-zinc-500 [writing-mode:vertical-lr]"
          style={{ transform: `translateX(${(80 - fovValue) * 1.5}px)` }}
        >
          Krawędź Drzwi L
        </div>
        
        <div 
          className="absolute right-0 top-0 bottom-0 w-12 bg-zinc-800/80 border-l border-zinc-700 transition-all duration-300 flex items-center justify-center text-[10px] text-zinc-500 [writing-mode:vertical-lr]"
          style={{ transform: `translateX(${(fovValue - 80) * 1.5}px)` }}
        >
          Krawędź Drzwi P
        </div>

        <div className="absolute w-2 h-2 bg-yellow-400 rounded-full shadow-[0_0_8px_rgba(250,204,21,0.6)] z-10" />

        <div 
          className="absolute flex flex-col items-center transition-all duration-300"
          style={{ 
            transform: `scale(${1.2 - ((fovValue - 80) / 70)})`,
            opacity: 0.9
          }}
        >
          <div className="w-8 h-8 rounded-full bg-red-600/30 border border-red-500 flex items-center justify-center relative">
            <div className="absolute w-12 h-[1px] bg-red-500" />
            <div className="absolute h-12 w-[1px] bg-red-500" />
            <span className="text-[8px] font-mono font-bold text-red-500 mt-0.5">TARGET</span>
          </div>
          <span className="text-[9px] font-mono text-zinc-400 bg-zinc-950/80 px-1.5 py-0.5 rounded border border-zinc-800 mt-1">15 METRÓW</span>
        </div>

        <div className="absolute bottom-2 left-2 right-2 flex justify-between text-[9px] font-mono text-zinc-500 bg-zinc-950/60 p-1 rounded">
          <span>Strefa Ślepa</span>
          <span className="text-amber-500 font-bold">{fovValue >= 110 ? 'Maksymalny odczyt peryferyjny' : 'Zredukowana widoczność boczna'}</span>
          <span>Strefa Ślepa</span>
        </div>
      </div>
      <p className="text-[10px] text-zinc-500 mt-2 leading-relaxed">
        Suwak wpływa na odczuwanie prędkości. Im wyższe pole widzenia (FOV), tym mniejsza wydaje się sylwetka wroga, ale ruchy postaci sprawiają wrażenie znacznie szybszych.
      </p>
    </div>
  );
};

const VisualToggle = ({ isActive }) => (
  <div className={`w-12 h-6 rounded-full p-1 cursor-pointer transition-colors duration-300 ${isActive ? 'bg-amber-500' : 'bg-zinc-800'}`}>
    <div className={`w-4 h-4 rounded-full bg-zinc-950 shadow-md transform transition-transform duration-300 ${isActive ? 'translate-x-6' : 'translate-x-0'}`} />
  </div>
);

const App = () => {
  const [activeTab, setActiveTab] = useState('controller');
  const [isAdvanced, setIsAdvanced] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState('balanced');
  const [activePlatform, setActivePlatform] = useState('PS5');
  const [expandedOptionId, setExpandedOptionId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [settings, setSettings] = useState(INITIAL_VALUES);

  const [showSurvey, setShowSurvey] = useState(true);
  const [surveyStep, setSurveyStep] = useState(0);
  const [surveyAnswers, setSurveyAnswers] = useState({
    platform: 'PS5',
    playstyle: 'balanced',
    display: 'tv_game',
    controller: 'standard'
  });

  const [toast, setToast] = useState({ show: false, message: '', type: 'success' });
  const [customCodeInput, setCustomCodeInput] = useState('');

  const categories = Object.keys(METADATA);

  useEffect(() => {
    if (toast.show) {
      const timer = setTimeout(() => setToast({ show: false, message: '', type: 'success' }), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast.show]);

  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const encodedConfig = params.get('config');
      if (encodedConfig) {
        const decoded = JSON.parse(atob(encodedConfig));
        const validated = {};
        Object.keys(INITIAL_VALUES).forEach(key => {
          if (decoded[key] !== undefined) {
            validated[key] = decoded[key];
          } else {
            validated[key] = INITIAL_VALUES[key];
          }
        });
        setSettings(validated);
        setSelectedPreset('custom');
        setShowSurvey(false);
        showNotification('✓ Wczytano konfigurację z udostępnionego linku!', 'success');
      }
    } catch (e) {}
  }, []);

  const showNotification = (message, type = 'success') => {
    setToast({ show: true, message, type });
  };

  const liveMetrics = useMemo(() => {
    if (selectedPreset === 'custom') {
      const isUltraFov = settings.fov > 115;
      const lowDeadzone = settings.dz_l_min < 3;
      return {
        fps: isUltraFov ? '110-120 FPS' : '120 FPS (Locked)',
        lag: lowDeadzone ? '1.8ms (Kabel USB)' : '4.5ms (Bezprzewodowo)',
        cpu: isUltraFov ? 'Wysokie' : 'Średnie',
        fov: `${settings.fov} FOV`
      };
    }
    return PRESETS[selectedPreset]?.metrics || PRESETS.balanced.metrics;
  }, [selectedPreset, settings.fov, settings.dz_l_min]);

  const handlePresetChange = (presetId) => {
    setSelectedPreset(presetId);
    if (PRESETS[presetId]) {
      setSettings(prev => ({
        ...prev,
        ...PRESETS[presetId].overrides
      }));
      showNotification(`Zastosowano gotowy profil: ${PRESETS[presetId].name}`, 'success');
    }
  };

  const updateSetting = (key, val) => {
    setSelectedPreset('custom');
    setSettings(prev => ({
      ...prev,
      [key]: val
    }));
  };

  const toggleSetting = (key) => {
    setSelectedPreset('custom');
    setSettings(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const toggleOptionFinder = (id) => {
    setExpandedOptionId(expandedOptionId === id ? null : id);
  };

  const handleSurveyOptionSelect = (key, value) => {
    setSurveyAnswers(prev => ({ ...prev, [key]: value }));
  };

  const nextSurveyStep = () => {
    if (surveyStep < SURVEY_QUESTIONS.length - 1) {
      setSurveyStep(prev => prev + 1);
    } else {
      processAdaptiveConfig();
    }
  };

  const processAdaptiveConfig = () => {
    let adapted = { ...INITIAL_VALUES };
    
    setActivePlatform(surveyAnswers.platform);
    if (surveyAnswers.platform === 'PS4') {
      adapted.fov = 105;
      adapted.cas = 80;
    } else if (surveyAnswers.platform === 'PS4 Pro') {
      adapted.fov = 110;
      adapted.cas = 90;
    } else {
      adapted.fov = 120;
      adapted.cas = 100;
    }

    if (surveyAnswers.playstyle === 'cqc') {
      adapted.sens = 2.0;
      adapted.dz_l_max = 30;
      adapted.sprint = 'Auto. Sprint Taktyczny';
      adapted.slide = 'Hybrydowe';
    } else if (surveyAnswers.playstyle === 'sniper') {
      adapted.sens = 1.3;
      adapted.ads_low = 0.75;
      adapted.ads_high = 0.95;
      adapted.curve = 'Standardowa';
    } else {
      adapted.sens = 1.6;
      adapted.ads_low = 0.80;
      adapted.ads_high = 1.00;
    }

    if (surveyAnswers.display === 'tv_standard') {
      adapted.dz_l_min = 5;
      adapted.filter = 'Filtr 2 (Oba)';
    } else if (surveyAnswers.display === 'monitor') {
      adapted.dz_l_min = 2;
    }

    if (surveyAnswers.controller === 'standard') {
      adapted.layout = 'Taktyczny';
    } else {
      adapted.layout = 'Domyślny';
    }

    setSettings(adapted);
    setSelectedPreset('custom');
    setShowSurvey(false);
    showNotification('✓ Profil wygenerowany automatycznie na podstawie Twoich odpowiedzi!', 'success');
  };

  const generateShareLink = () => {
    try {
      const configStr = btoa(JSON.stringify(settings));
      const baseDomain = "https://anonymousik.is-a.dev/scripts/warz";
      const shareUrl = `${baseDomain}?config=${configStr}`;
      
      const textArea = document.createElement("textarea");
      textArea.value = shareUrl;
      textArea.style.position = "fixed"; 
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      
      const success = document.execCommand('copy');
      document.body.removeChild(textArea);

      if (success) {
        showNotification('Skopiowano dedykowany link do schowka!', 'success');
      }
    } catch (e) {
      showNotification('Błąd podczas generowania linku udostępniania.', 'error');
    }
  };

  const handleImportConfig = () => {
    try {
      if (!customCodeInput) return;
      let cleanInput = customCodeInput.trim();
      if (cleanInput.includes('?config=')) {
        cleanInput = cleanInput.split('?config=')[1];
      }
      const decoded = JSON.parse(atob(cleanInput));
      const validated = {};
      Object.keys(INITIAL_VALUES).forEach(key => {
        if (decoded[key] !== undefined) {
          validated[key] = decoded[key];
        } else {
          validated[key] = INITIAL_VALUES[key];
        }
      });
      setSettings(validated);
      setSelectedPreset('custom');
      setCustomCodeInput('');
      showNotification('✓ Pomyślnie wczytano zewnętrzną konfigurację!', 'success');
    } catch (e) {
      showNotification('Niepoprawny kod konfiguracji. Spróbuj ponownie.', 'error');
    }
  };

  const exportCheatSheet = () => {
    let md = `=== WARZONE CONFIGURATION CHEAT SHEET ===\n`;
    md += `Autor projektu: Anonymousik (FerroART) | https://anonymousik.is-a.dev\n`;
    md += `Lokalizacja skryptu: https://anonymousik.is-a.dev/scripts/warz\n`;
    md += `Platforma docelowa: ${activePlatform} | Profil: ${selectedPreset}\n\n`;
    
    categories.forEach(catKey => {
      md += `[ ${METADATA[catKey].title} ]\n`;
      METADATA[catKey].items.forEach(item => {
        const val = settings[item.id];
        md += `- ${item.name}: ${val} (Ścieżka: ${item.paths[activePlatform] || item.paths['PS4']})\n`;
      });
      md += `\n`;
    });
    
    const element = document.createElement("a");
    const file = new Blob([md], {type: 'text/plain'});
    element.href = URL.createObjectURL(file);
    element.download = "Warzone_Ustawienia_Anonymousik.txt";
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
    showNotification('Ściąga tekstowa została pobrana pomyślnie!', 'success');
  };

  const filteredOptions = useMemo(() => {
    if (!searchQuery) return [];
    const query = searchQuery.toLowerCase();
    const results = [];
    
    categories.forEach(catKey => {
      METADATA[catKey].items.forEach(item => {
        if (item.name.toLowerCase().includes(query) || 
            item.beg.toLowerCase().includes(query) || 
            item.adv.toLowerCase().includes(query)) {
          results.push({ ...item, categoryKey: catKey });
        }
      });
    });
    return results;
  }, [searchQuery]);

  return (
    <div className="min-h-screen bg-[#07080c] text-zinc-300 font-sans selection:bg-amber-500/30 pb-20 relative overflow-hidden">
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1f2937_1px,transparent_1px),linear-gradient(to_bottom,#1f2937_1px,transparent_1px)] bg-[size:4rem_4rem] opacity-[0.03] pointer-events-none" />
      
      <nav className="w-full bg-black/90 border-b border-zinc-900 px-4 py-2.5 flex flex-col sm:flex-row justify-between items-center gap-3 relative z-50 text-[11px] font-mono tracking-wider">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-zinc-500">PROJEKT AUTORSTWA:</span>
          <a href="https://anonymousik.is-a.dev" target="_blank" rel="noopener noreferrer" className="text-white hover:text-amber-500 transition-colors font-extrabold flex items-center gap-1">
            ANONYMOUSIK <span className="text-zinc-600 font-medium">(FerroART)</span>
            <ExternalLink className="w-3 h-3 text-zinc-500" />
          </a>
        </div>
        
        <div className="flex items-center gap-4 text-zinc-400">
          <a href="https://anonymousik.is-a.dev" target="_blank" rel="noopener noreferrer" className="hover:text-amber-400 transition-colors">STRONA GŁÓWNA</a>
          <span className="text-zinc-800">/</span>
          <a href="https://github.com/anonymousik" target="_blank" rel="noopener noreferrer" className="hover:text-amber-400 transition-colors">GITHUB</a>
          <span className="text-zinc-800">/</span>
          <span className="text-amber-500 font-bold bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">SCRIPTS / WARZ</span>
        </div>
      </nav>

      <div className="h-1 bg-gradient-to-r from-amber-500 via-yellow-400 to-amber-600" />

      {toast.show && (
        <div className={`fixed top-6 right-6 z-50 p-4 rounded-xl shadow-2xl flex items-center gap-3 border animate-fadeIn transition-all max-w-sm ${
          toast.type === 'success' ? 'bg-zinc-900/95 border-emerald-500 text-emerald-300' : 'bg-zinc-900/95 border-red-500 text-red-300'
        }`}>
          {toast.type === 'success' ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> : <AlertCircle className="w-5 h-5 text-red-400" />}
          <span className="text-sm font-bold">{toast.message}</span>
        </div>
      )}

      <header className="border-b border-zinc-800/80 bg-zinc-900/70 backdrop-blur-md sticky top-[37px] sm:top-[33px] z-40 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-4 flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-4">
            <div className="p-2 bg-gradient-to-br from-amber-500 to-yellow-600 rounded-lg text-zinc-950 font-black flex items-center justify-center shadow-lg">
              <Target className="w-7 h-7" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl md:text-2xl font-black text-white tracking-widest uppercase">WARZONE <span className="text-amber-500">HQ</span></h1>
                <span className="bg-zinc-800 text-[9px] px-1.5 py-0.5 rounded text-amber-400 border border-zinc-700 font-mono font-bold uppercase">v4.0 ACTIVE</span>
              </div>
              <p className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">Tactical Gameplay Configuration & Optimization Hub</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button onClick={() => { setSurveyStep(0); setShowSurvey(true); }} className="px-4 py-2 bg-zinc-950/80 border border-zinc-800 hover:border-amber-500 text-xs font-bold rounded-lg flex items-center gap-2 transition-all text-zinc-400 hover:text-white">
              <RefreshCw className="w-3.5 h-3.5" /> Wykreuj Mój Profil
            </button>

            <div className="flex items-center bg-zinc-950/80 p-1 rounded-xl border border-zinc-800">
              <button onClick={() => setIsAdvanced(false)} className={`px-4 py-1.5 text-xs font-bold rounded-lg transition-all duration-200 ${!isAdvanced ? 'bg-zinc-800 text-white shadow-md' : 'text-zinc-500 hover:text-zinc-300'}`}>Początkujący</button>
              <button onClick={() => setIsAdvanced(true)} className={`px-4 py-1.5 text-xs font-bold rounded-lg transition-all duration-200 flex items-center gap-1 ${isAdvanced ? 'bg-amber-500/10 text-amber-500 border border-amber-500/30' : 'text-zinc-500 hover:text-zinc-300'}`}>
                <Zap className="w-3 h-3" /> Zaawansowany
              </button>
            </div>
          </div>
        </div>
      </header>

      {showSurvey ? (
        <section className="max-w-4xl mx-auto px-4 py-12 animate-fadeIn">
          <div className="bg-zinc-900/90 border border-zinc-800/80 rounded-3xl p-6 md:p-10 shadow-2xl relative overflow-hidden backdrop-blur-lg">
            <div className="absolute top-0 left-0 w-8 h-[2px] bg-amber-500" />
            <div className="absolute top-0 left-0 w-[2px] h-8 bg-amber-500" />
            <div className="absolute top-0 right-0 w-8 h-[2px] bg-amber-500" />
            <div className="absolute top-0 right-0 w-[2px] h-8 bg-amber-500" />

            <div className="absolute top-0 left-0 w-full h-1 bg-zinc-800">
              <div className="h-full bg-gradient-to-r from-amber-500 to-yellow-500 transition-all duration-300" style={{ width: `${((surveyStep + 1) / SURVEY_QUESTIONS.length) * 100}%` }} />
            </div>

            <div className="flex justify-between items-center mb-8">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-amber-500 animate-pulse" />
                <span className="text-xs uppercase font-mono tracking-widest text-amber-500 font-bold">Kreator Adaptacyjny</span>
              </div>
              <span className="text-xs font-mono text-zinc-500">ZAPYTANIE {surveyStep + 1} z {SURVEY_QUESTIONS.length}</span>
            </div>

            <h2 className="text-2xl md:text-3xl font-black text-white mb-8 uppercase tracking-tight">{SURVEY_QUESTIONS[surveyStep].question}</h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
              {SURVEY_QUESTIONS[surveyStep].options.map((option) => {
                const currentKey = SURVEY_QUESTIONS[surveyStep].id;
                const isSelected = surveyAnswers[currentKey] === option.val;
                return (
                  <button key={option.val} onClick={() => handleSurveyOptionSelect(currentKey, option.val)} className={`p-5 rounded-2xl text-left border transition-all duration-200 flex flex-col justify-between ${
                    isSelected ? 'bg-amber-500/10 border-amber-500 text-white shadow-[0_0_25px_rgba(245,158,11,0.15)]' : 'bg-zinc-950/40 border-zinc-800 hover:bg-zinc-900/30 hover:border-zinc-700 text-zinc-400'
                  }`}>
                    <div className="flex justify-between items-center w-full mb-3">
                      <span className="font-extrabold text-sm text-zinc-200">{option.label}</span>
                      <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${isSelected ? 'border-amber-500 bg-amber-500' : 'border-zinc-600'}`}>
                        {isSelected && <Check className="w-3.5 h-3.5 text-zinc-950 stroke-[4px]" />}
                      </div>
                    </div>
                    <p className="text-xs text-zinc-500 leading-relaxed font-medium">{option.desc}</p>
                  </button>
                );
              })}
            </div>

            <div className="flex flex-col sm:flex-row justify-between items-center gap-4 border-t border-zinc-800/80 pt-6">
              <button onClick={() => setShowSurvey(false)} className="text-xs font-bold text-zinc-500 hover:text-zinc-300 transition-colors uppercase tracking-wider font-mono">Pomiń kreator (Zostaw Domyślne)</button>
              <button onClick={nextSurveyStep} className="w-full sm:w-auto px-8 py-3.5 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-black text-xs uppercase tracking-widest rounded-xl flex items-center justify-center gap-2 transition-all shadow-[0_4px_20px_rgba(245,158,11,0.3)]">
                {surveyStep === SURVEY_QUESTIONS.length - 1 ? 'Generuj Profil Taktyczny' : 'Kontynuuj'}
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </section>
      ) : null}

      <main className={`max-w-7xl mx-auto px-4 py-8 transition-opacity duration-300 ${showSurvey ? 'opacity-20 pointer-events-none' : 'opacity-100'}`}>
        <div className="mb-8 p-4 bg-zinc-900/50 border border-zinc-800/80 rounded-2xl flex flex-col lg:flex-row gap-4 items-center justify-between">
          <div className="relative w-full lg:max-w-md">
            <Search className="absolute left-3.5 top-3 w-4 h-4 text-zinc-500" />
            <input type="text" placeholder="Wyszukaj parametr (np. deadzone, czułość, fov)..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="w-full pl-10 pr-4 py-2.5 bg-zinc-950 border border-zinc-800 focus:border-amber-500/80 rounded-xl text-sm placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-amber-500/30 text-white" />
          </div>

          <div className="flex flex-wrap gap-2 items-center w-full lg:w-auto justify-end">
            <button onClick={exportCheatSheet} className="px-4 py-2 bg-zinc-950 border border-zinc-800 hover:border-amber-500 hover:text-white rounded-xl text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-2 transition-all">
              <Download className="w-4 h-4" /> Eksportuj do pliku (.txt)
            </button>
          </div>
        </div>

        {searchQuery && (
          <div className="mb-8 p-6 bg-zinc-900 border border-amber-500/40 rounded-2xl animate-fadeIn">
            <h3 className="text-sm font-bold uppercase tracking-wider text-amber-500 mb-4 flex items-center gap-2"><Search className="w-4 h-4" /> Wyniki wyszukiwania dla "{searchQuery}":</h3>
            {filteredOptions.length === 0 ? ( <p className="text-zinc-500 text-sm font-mono">Brak dopasowań do wyszukiwanej frazy.</p> ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filteredOptions.map((item) => {
                  const currentValue = settings[item.id];
                  return (
                    <div key={item.id} onClick={() => { setActiveTab(item.categoryKey); setSearchQuery(''); setTimeout(() => { const el = document.getElementById(item.id); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' }); }, 200); }} className="p-4 bg-zinc-950/60 border border-zinc-800 hover:border-amber-500/50 rounded-xl flex justify-between items-center cursor-pointer transition-all">
                      <div>
                        <h4 className="font-bold text-xs text-zinc-200 uppercase">{item.name}</h4>
                        <span className="text-[10px] font-mono text-zinc-500 uppercase">Kategoria: {METADATA[item.categoryKey].title}</span>
                      </div>
                      <span className="bg-zinc-900 px-3 py-1 text-xs text-amber-500 font-mono rounded font-bold border border-zinc-800">{currentValue === true ? 'WŁ.' : currentValue === false ? 'WYŁ.' : currentValue}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-8">
          <section className="lg:col-span-8 p-6 bg-zinc-900/40 border border-zinc-800/80 rounded-2xl space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-500" />
                <h2 className="text-xs font-bold uppercase text-zinc-400 tracking-wider">Metoda kalibracji gotowych szablonów</h2>
              </div>
              {selectedPreset === 'custom' && ( <span className="text-[10px] bg-amber-500/10 text-amber-500 border border-amber-500/20 px-2 py-0.5 rounded font-black tracking-widest uppercase">Własna Modyfikacja</span> )}
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {Object.values(PRESETS).map((p) => {
                const isSelected = selectedPreset === p.id;
                return (
                  <button key={p.id} onClick={() => handlePresetChange(p.id)} className={`text-left p-4 rounded-xl border transition-all duration-300 flex flex-col justify-between ${
                    isSelected ? 'bg-zinc-900/80 border-amber-500 shadow-[0_0_20px_rgba(245,158,11,0.1)] text-white' : 'bg-zinc-950/40 border-zinc-800/60 hover:border-zinc-700'
                  }`}>
                    <div className="space-y-2">
                      <div className="flex justify-between items-start mb-1.5">
                        <span className="text-[9px] font-mono font-bold uppercase tracking-wider text-zinc-500">Preset</span>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded font-black tracking-widest ${p.color}`}>{p.badge}</span>
                      </div>
                      <h3 className="font-bold text-sm flex items-center gap-1.5">{p.name}{isSelected && <Check className="w-3.5 h-3.5 text-amber-500" />}</h3>
                      <p className="text-[11px] text-zinc-500 leading-relaxed font-medium">{p.desc}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="lg:col-span-4 p-6 bg-zinc-900/40 border border-zinc-800/80 rounded-2xl flex flex-col justify-between space-y-4">
            <div>
              <h2 className="text-xs font-bold uppercase text-zinc-400 tracking-wider mb-2 flex items-center gap-1.5"><Share2 className="w-3.5 h-3.5 text-amber-500" /> Klonowanie Konfiguracji</h2>
              <p className="text-[11px] text-zinc-500 leading-normal font-medium text-justify">Wygeneruj unikalny link profilu bezpośrednio skorelowany z platformą <span className="text-amber-500 font-bold">Anonymousik.is-a.dev/scripts/warz</span>.</p>
            </div>
            <button onClick={generateShareLink} className="w-full py-2.5 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-black text-xs uppercase tracking-wider rounded-xl flex items-center justify-center gap-2 transition-all shadow-md">
              <Copy className="w-4 h-4" /> Kopiuj Link Konfiguracji
            </button>
            <div className="flex items-center gap-2 bg-zinc-950/80 border border-zinc-800 p-1 rounded-xl">
              <input type="text" placeholder="Wklej klucz lub cały link..." value={customCodeInput} onChange={(e) => setCustomCodeInput(e.target.value)} className="bg-transparent text-[11px] text-zinc-300 placeholder-zinc-600 px-3 py-1.5 w-full focus:outline-none font-mono" />
              <button onClick={handleImportConfig} className="bg-zinc-800 text-white font-extrabold text-xs uppercase px-4 py-1.5 rounded-lg hover:bg-zinc-700 transition-all">Import</button>
            </div>
          </section>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          <aside className="lg:col-span-3 space-y-4">
            <div className="bg-zinc-950 p-2 rounded-2xl border border-zinc-800">
              <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-3 px-3 pt-2">Sekcje Konfiguracyjne</p>
              <nav className="flex flex-row lg:flex-col gap-1 overflow-x-auto lg:overflow-visible pb-2 lg:pb-0 hide-scrollbar">
                {categories.map((key) => {
                  const cat = METADATA[key];
                  const Icon = cat.icon;
                  const isActive = activeTab === key;
                  return (
                    <button key={key} onClick={() => { setActiveTab(key); setExpandedOptionId(null); }} className={`flex items-center gap-3 px-3.5 py-3 rounded-xl text-left transition-all duration-200 whitespace-nowrap lg:whitespace-normal border ${
                      isActive ? 'bg-zinc-900 border-amber-500/30 text-amber-500 shadow-[inset_4px_0_0_0_rgba(245,158,11,1)]' : 'bg-transparent border-transparent text-zinc-400 hover:bg-zinc-900/30 hover:text-zinc-200'
                    }`}>
                      <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? 'text-amber-500' : 'text-zinc-500'}`} />
                      <span className="font-bold uppercase text-xs tracking-wider">{cat.title}</span>
                    </button>
                  );
                })}
              </nav>
            </div>

            <div className="p-5 bg-zinc-900/50 border border-zinc-800 rounded-2xl space-y-4">
              <h3 className="text-xs uppercase text-zinc-500 font-bold flex items-center gap-2"><Activity className="w-4 h-4 text-amber-500 animate-pulse" /> Telemetria Wydajności</h3>
              <div className="space-y-3 text-sm font-mono">
                <div className="flex justify-between items-center border-b border-zinc-800/40 pb-2"><span className="text-zinc-500 text-[10px] uppercase">Płynność (FPS):</span><span className="text-emerald-400 font-bold text-xs">{liveMetrics.fps}</span></div>
                <div className="flex justify-between items-center border-b border-zinc-800/40 pb-2"><span className="text-zinc-500 text-[10px] uppercase">Czas Reakcji:</span><span className="text-amber-400 font-bold text-xs">{liveMetrics.lag}</span></div>
                <div className="flex justify-between items-center border-b border-zinc-800/40 pb-2"><span className="text-zinc-500 text-[10px] uppercase">Zużycie Mocy:</span><span className="text-zinc-300 font-bold text-xs">{liveMetrics.cpu}</span></div>
                <div className="flex justify-between items-center"><span className="text-zinc-500 text-[10px] uppercase">Zalecany FOV:</span><span className="text-cyan-400 font-bold text-xs">{liveMetrics.fov}</span></div>
              </div>
            </div>

            {activeTab === 'controller' && ( <TacticalControllerVisualizer layout={settings.layout} /> )}
            {activeTab === 'graphics' && ( <FovSimulator fovValue={settings.fov} adsFov={settings.ads_fov} /> )}
          </aside>

          <section className="lg:col-span-9 space-y-6">
            <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4 border-b border-zinc-800/80 pb-4">
               <div className="flex items-center gap-3">
                 <div className="p-2 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                   {React.createElement(METADATA[activeTab].icon, { className: "w-5 h-5 text-amber-500" })}
                 </div>
                 <h2 className="text-xl md:text-2xl font-black uppercase tracking-wider text-white">{METADATA[activeTab].title}</h2>
               </div>
               
               <div className="flex items-center gap-1.5 bg-zinc-950 p-1.5 rounded-xl border border-zinc-800">
                 <span className="text-[10px] uppercase font-bold text-zinc-500 px-2 font-mono">Ścieżka dla:</span>
                 {['PS4', 'PS5', 'PC'].map((p) => (
                   <button key={p} onClick={() => { setActivePlatform(p); showNotification(`Zmieniono widok ścieżek dostępu dla platformy: ${p}`, 'success'); }} className={`px-3 py-1 text-xs font-mono font-bold rounded-lg transition-all duration-150 ${
                     activePlatform === p ? 'bg-amber-500 text-zinc-950 shadow-md' : 'text-zinc-400 hover:text-white'
                   }`}>{p}</button>
                 ))}
               </div>
            </div>

            {METADATA[activeTab].warning && (
              <div className="p-4 bg-amber-500/5 border-l-4 border-amber-500 rounded-r-xl flex items-start gap-3">
                <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-amber-200/90 leading-relaxed font-semibold">{METADATA[activeTab].warning}</p>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {METADATA[activeTab].items.map((item) => {
                const currentValue = settings[item.id];
                const isExpanded = expandedOptionId === item.id;
                
                return (
                  <div key={item.id} id={item.id} className={`relative p-5 rounded-2xl border transition-all duration-300 flex flex-col justify-between ${
                    item.highlight ? 'bg-zinc-900/50 border-amber-500/40 hover:border-amber-500 shadow-lg' : 'bg-zinc-900/10 border-zinc-800/80 hover:border-zinc-700'
                  }`}>
                    <div>
                      <div className="flex justify-between items-start mb-4">
                        <h3 className="font-extrabold text-zinc-100 uppercase text-xs tracking-wider pr-4">{item.name}</h3>
                        {item.isToggle ? (
                          <div onClick={() => toggleSetting(item.id)}><VisualToggle isActive={currentValue} /></div>
                        ) : item.isSelect ? (
                          <div className="relative inline-block text-left">
                            <select value={currentValue} onChange={(e) => updateSetting(item.id, e.target.value)} className="bg-zinc-950 border border-zinc-800 text-amber-500 font-mono text-xs px-2.5 py-1 rounded-lg focus:outline-none appearance-none cursor-pointer hover:border-zinc-700">
                              {item.options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                            </select>
                          </div>
                        ) : (
                          <span className="inline-block bg-zinc-950 border border-zinc-800 text-amber-500 font-mono text-xs px-3 py-1 rounded-lg shadow-inner font-extrabold">{currentValue}</span>
                        )}
                      </div>

                      {item.visual === 'slider' && (
                        <div className="mb-4">
                          <input type="range" min={item.min} max={item.max} step={item.step} value={currentValue} onChange={(e) => updateSetting(item.id, parseFloat(e.target.value))} className="w-full accent-amber-500 bg-zinc-800 h-1.5 rounded-lg cursor-pointer" />
                          <div className="flex justify-between text-[9px] text-zinc-500 font-mono mt-1.5"><span>MIN: {item.min}</span><span>MAX: {item.max}</span></div>
                        </div>
                      )}

                      <div className="mt-4 pt-4 border-t border-zinc-800/60 flex items-start gap-2.5">
                        <Info className={`w-4 h-4 mt-0.5 flex-shrink-0 ${isAdvanced ? 'text-amber-500' : 'text-emerald-500'}`} />
                        <p className={`text-xs leading-relaxed ${isAdvanced ? 'text-zinc-400 font-mono text-[11px]' : 'text-zinc-300 font-medium'}`}>{isAdvanced ? item.adv : item.beg}</p>
                      </div>
                    </div>

                    <div className="mt-5">
                      <button onClick={() => toggleOptionFinder(item.id)} className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs transition-all duration-200 ${
                        isExpanded ? 'bg-amber-500 text-zinc-950 font-black shadow-md' : 'bg-zinc-950/80 border border-zinc-800 text-zinc-400 hover:text-white hover:border-zinc-700'
                      }`}>
                        <span className="flex items-center gap-2"><MapPin className="w-4 h-4" />Lokalizacja Opcji w Menu</span>
                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>

                      {isExpanded && (
                        <div className="mt-2.5 p-3.5 bg-zinc-950 border border-zinc-800 rounded-xl text-xs space-y-2 animate-fadeIn shadow-inner">
                          <div className="flex items-center gap-1.5 border-b border-zinc-800/60 pb-2 text-zinc-500 font-mono">{activePlatform === 'PC' ? <Laptop className="w-4 h-4" /> : <Tv className="w-4 h-4" />}<span>Przejdź kolejno:</span></div>
                          <p className="text-amber-400 font-extrabold leading-relaxed font-mono">{item.paths[activePlatform] || item.paths['PS4']}</p>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        </div>
      </main>

      <style dangerouslySetInnerHTML={{__html: `
        .hide-scrollbar::-webkit-scrollbar { display: none; }
        .hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fadeIn { animation: fadeIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
      `}} />
    </div>
  );
};

export default App;
EOF

echo "-> Konfiguracja parametrów kompilacji w vite.config.js..."
cat << 'EOF' > vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Konfiguracja pod katalog scripts/warz na Twojej domenie
  base: '/scripts/warzone-helper/',
})
EOF

echo "-> Konfiguracja skryptów wdrożenia w package.json..."
# Użycie node do bezpiecznej manipulacji plikiem package.json
node -e '
const fs = require("fs");
const pkg = JSON.parse(fs.readFileSync("package.json"));
pkg.scripts.predeploy = "npm run build";
pkg.scripts.deploy = "gh-pages -d dist";
fs.writeFileSync("package.json", JSON.stringify(pkg, null, 2));
'

echo "-> Przygotowywanie systemu Git..."
git init
git add .
git commit -m "Auto-instalacja asystenta przez skrypt Anonymousik (Ferro)"

# Łączenie z wybranym repozytorium na Twoim GitHubie
git branch -M main
git remote add origin "https://github.com/${GH_USER}/${REPO_NAME}.git"

echo "=========================================================="
echo " SYSTEM JEST GOTOWY DO AUTOMATYCZNEGO WDROŻENIA           "
echo "=========================================================="
echo "Za chwilę uruchomimy 'npm run deploy' w celu przesłania"
echo "kodu na Twoje repozytorium i uruchomienia GitHub Pages."
echo "Upewnij się, że na GitHub utworzyłeś puste repozytorium o nazwie: scripts"
echo "----------------------------------------------------------"
read -p "Naciśnij [ENTER] aby rozpocząć proces wdrożenia (deployment)..."

npm run deploy

echo "=========================================================="
echo "             PROCES ZAKOŃCZONY SUKCESEM!                 "
echo "=========================================================="
echo "Twoja aplikacja w ciągu kilku minut będzie dostępna pod:"
echo "👉 https://${GH_USER}.github.io/scripts/warzone-helper"
echo ""
echo "Aby podpiąć to pod Twoją domenę anonymousik.is-a.dev:"
echo "W ustawieniach repozytorium '${REPO_NAME}' -> Pages -> Custom Domain"
echo "wpisz swoją domenę główną: anonymousik.is-a.dev"
echo "Struktura folderów GitHub Pages dopasuje się automatycznie."
echo "=========================================================="
