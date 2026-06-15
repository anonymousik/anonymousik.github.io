import React, { useState, useMemo, useEffect } from 'react';
import { 
  Gamepad2, Crosshair, Monitor, Headphones, Info, Zap, Target, 
  Activity, SlidersHorizontal, AlertTriangle, MapPin, Laptop, 
  Tv, Sparkles, Check, ChevronDown, ChevronUp, Share2, Copy, 
  RefreshCw, ClipboardCheck, ArrowRight, User, MousePointerClick, 
  Sliders, ShieldAlert
} from 'lucide-react';

// --- INITIAL FLAT CONFIG STATE (DEFAULT VALUES) ---
const INITIAL_VALUES = {
  layout: 'Domyślny',
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
  armor: 'Zelementowany', // Zastosuj jeden
  interact: 'Priorytet interakcji',
  fov: 110,
  ads_fov: 'Zależne (Affected)',
  w_fov: 'Szerokie (Wide)',
  cas: 90,
  blur: false,
  shake: 50, // Minimalny 50%
  filter: 'Filtr 2 (Oba)',
  hud: 'Minimalne (Środek)',
  cross: 'Większa / Żółta',
  radar: 'Kwadrat / Kontury Wł.',
  audio: 'Sucker Punch',
  mono: false
};

// --- PRESETS DICTIONARY ---
const PRESETS = {
  performance: {
    id: 'performance',
    name: 'Turniejowy (Input Lag Cut)',
    desc: 'Najniższe możliwe opóźnienia sprzętowe, zrównoważone progi deadzone dla szybkiego celowania.',
    badge: 'PRO PERFORMANCE',
    color: 'border-red-500/50 bg-red-950/20 text-red-400',
    metrics: { fps: '60 (Locked)', lag: '35ms', cpu: 'Minimalne', fov: '105-110 FOV' },
    overrides: {
      vib: false, trig: false, sens: 1.8, dz_l_min: 2, dz_l_max: 45, dz_trig: 0,
      ads_low: 0.75, ads_high: 0.90, curve: 'Dynamiczny', assist: true,
      sprint: 'Auto. Sprint Taktyczny', sprint_del: 0, slide: 'Hybrydowe', fov: 110, ads_fov: 'Zależne (Affected)'
    }
  },
  balanced: {
    id: 'balanced',
    name: 'Zbalansowany (PS4 Pro / 4K)',
    desc: 'Ustawienia gwarantujące najwyższą ostrość obrazu FidelityFX CAS oraz stabilną płynność wokół 55-60 FPS.',
    badge: 'BALANCED PRO',
    color: 'border-amber-500/50 bg-amber-950/20 text-amber-400',
    metrics: { fps: '55-60 FPS', lag: '45ms', cpu: 'Średnie', fov: '115 FOV' },
    overrides: {
      vib: false, trig: false, sens: 1.6, dz_l_min: 4, dz_l_max: 50, dz_trig: 0,
      ads_low: 0.80, ads_high: 1.00, curve: 'Dynamiczny', assist: true,
      sprint: 'Auto. Sprint Taktyczny', slide: 'Hybrydowe', fov: 115, ads_fov: 'Zależne (Affected)', cas: 90
    }
  },
  movement: {
    id: 'movement',
    name: 'Agresywny Ruch (CQC)',
    desc: 'Ekstremalna czułość obrotu gałek oraz skrócone do minimum animacje ruchowe ułatwiające slide cancel.',
    badge: 'AGILE MOVE',
    color: 'border-cyan-500/50 bg-cyan-950/20 text-cyan-400',
    metrics: { fps: '50-60 FPS', lag: '42ms', cpu: 'Wysokie', fov: '120 FOV' },
    overrides: {
      vib: false, trig: false, sens: 2.2, dz_l_min: 3, dz_l_max: 30, dz_trig: 0,
      ads_low: 0.85, ads_high: 1.00, curve: 'Dynamiczny', assist: true,
      sprint: 'Auto. Sprint Taktyczny', slide: 'Hybrydowe', fov: 120, ads_fov: 'Zależne (Affected)'
    }
  }
};

// --- DICTIONARY FOR METADATA AND DESCRIPTIONS ---
const METADATA = {
  controller: {
    title: 'Kontroler & Ruch',
    icon: Gamepad2,
    warning: "Aby uzyskać pełną precyzję, połącz kontroler kablem USB i w opcjach systemu PS4/PS5 zmień 'Metodę komunikacji' na 'Użyj kabla USB'.",
    items: [
      { id: 'layout', name: 'Układ przycisków', isToggle: false, isSelect: true, options: ['Domyślny', 'Taktyczny', 'Weteran taktyczny'], paths: { PS4: 'Kontroler -> Układ przycisków', PS5: 'Kontroler -> Układ przycisków', PC: 'Controller -> Button Layout' }, beg: 'Standardowy układ. Użyj "Taktyczny" jeśli nie masz łopatek.', adv: 'Default/Tactical. Umożliwia slide-cancel prawym analogiem bez puszczania gałki celowania.' },
      { id: 'vib', name: 'Wibracje kontrolera', isToggle: true, paths: { PS4: 'Ustawienia -> Urządzenia -> Kontrolery -> Wibracje', PS5: 'Akcesoria -> Kontrolery -> Siła wibracji -> Wyłącz', PC: 'Controller -> Vibration -> Off' }, beg: 'Drżenie rąk utrudnia celowanie na dystans. Wyłącz to.', adv: 'Niszczy mikrokorektę odrzutu. Wymagane bezwzględne wyłączenie w celu budowania pamięci mięśniowej.' },
      { id: 'trig', name: 'Efekt triggerów (L2/R2)', isToggle: true, paths: { PS4: 'Niedostępne na PS4 (Zawsze wyłączone)', PS5: 'Akcesoria -> Kontrolery -> Efekt Triggerów -> Wyłącz', PC: 'Controller -> Trigger Effect -> Off' }, beg: 'Usuwa fizyczny opór spustów, strzelasz ułamek sekundy szybciej.', adv: 'Eliminuje opóźnienie mechaniczne sygnału wejściowego do 0ms.' },
      { id: 'sens', name: 'Czułość drążków (Pion/Poziom)', isToggle: false, visual: 'slider', min: 0.5, max: 4.0, step: 0.1, paths: { PS4: 'Kontroler -> Czułość drążków', PS5: 'Kontroler -> Czułość drążków', PC: 'Controller -> Stick Sensitivity' }, beg: 'Szybkość obrotu kamery. 1.6 odpowiada klasycznemu ustawieniu 7/7.', adv: 'Złoty środek pod Rotational Aim Assist. Wyższe wartości wymagają doskonałej kontroli centrowania.' },
      { id: 'dz_l_min', name: 'Minimalna strefa martwa lewej gałki', isToggle: false, visual: 'slider', min: 0, max: 20, step: 1, paths: { PS4: 'Kontroler -> Strefy Martwe -> Min. Lewa', PS5: 'Kontroler -> Strefy Martwe -> Min. Lewa', PC: 'Inputs Deadzone -> Left Stick Min' }, beg: 'Minimalne wychylenie potrzebne do ruchu postaci. Ustaw na najmniejszą wartość bez samoczynnego ruchu (stick drift).', adv: 'Redukcja fizycznego opóźnienia analogu. Przyspiesza strafing pod aktywację asysty.' },
      { id: 'dz_l_max', name: 'Maksymalna strefa martwa lewej gałki', isToggle: false, visual: 'slider', min: 10, max: 100, step: 5, paths: { PS4: 'Kontroler -> Strefy Martwe -> Max Lewa', PS5: 'Kontroler -> Strefy Martwe -> Max Lewa', PC: 'Inputs Deadzone -> Left Stick Max' }, beg: 'Jak mocno musisz wychylić gałkę, by uzyskać pełny bieg.', adv: 'Wartość 50 wymusza natychmiastowe przejście w sprint przy minimalnym ruchu dłoni.' },
      { id: 'dz_r_max', name: 'Maksymalna strefa martwa prawej gałki', isToggle: false, visual: 'slider', min: 50, max: 100, step: 1, paths: { PS4: 'Kontroler -> Strefy Martwe -> Max Prawa', PS5: 'Kontroler -> Strefy Martwe -> Max Prawa', PC: 'Inputs Deadzone -> Right Stick Max' }, beg: 'Zapewnia pełną prędkość obrotu na skrajnej krawędzi analogu.', adv: '99 gwarantuje liniowe i maksymalne przeniesienie wektora obrotu na granicy fizycznej muszli analogu.' },
      { id: 'dz_trig', name: 'Strefa martwa L2 / R2', isToggle: false, visual: 'slider', min: 0, max: 10, step: 1, paths: { PS4: 'Kontroler -> Strefy Martwe -> Spusty', PS5: 'Kontroler -> Strefy Martwe -> Spusty', PC: 'Inputs Deadzone -> L2/R2' }, beg: 'Szybkość reakcji na wciśnięcie strzału.', adv: 'Wartość 0 aktywuje strzał i celowanie natychmiast po pokonaniu mikro-progów mechanicznych padów DualShock/DualSense.' }
    ]
  },
  aiming: {
    title: 'Celowanie',
    icon: Crosshair,
    items: [
      { id: 'ads_low', name: 'Mnożnik ADS (Niskie powiększenie)', isToggle: false, visual: 'slider', min: 0.50, max: 1.50, step: 0.05, paths: { PS4: 'Celowanie -> Mnożnik ADS (Niski)', PS5: 'Celowanie -> Mnożnik ADS (Niski)', PC: 'Aiming -> ADS Sensitivity Multiplier (Low Zoom)' }, beg: 'Czułość przy celowaniu z kolimatorów. Niższa ułatwia utrzymanie broni na celu.', adv: 'Mnożnik 0.80 redukuje błędy pozycjonowania podczas szybkich starć na średnim dystansie.' },
      { id: 'ads_high', name: 'Mnożnik ADS (Wysokie powiększenie)', isToggle: false, visual: 'slider', min: 0.50, max: 1.50, step: 0.05, paths: { PS4: 'Celowanie -> Mnożnik ADS (Wysoki)', PS5: 'Celowanie -> Mnożnik ADS (Wysoki)', PC: 'Aiming -> ADS Sensitivity Multiplier (High Zoom)' }, beg: 'Szybkość ruchu celownika snajperskiego.', adv: 'Pozostawienie wartości 1.00 ułatwia flick-shoty i zachowuje stałą pamięć mięśniową przy zoomie snajperskim.' },
      { id: 'trans', name: 'Czas przejścia czułości celownika', isToggle: false, isSelect: true, options: ['Natychmiastowy', 'Po przybliżeniu', 'Stopniowy'], paths: { PS4: 'Celowanie -> Czas przejścia czułości', PS5: 'Celowanie -> Czas przejścia czułości', PC: 'Aiming -> ADS Sensitivity Transition Timing' }, beg: 'Kiedy ma nastąpić spowolnienie celownika. Najlepiej od razu (Natychmiastowy).', adv: 'Instant. Eliminuje nieliniową krzywą czułości w trakcie trwania animacji celowania (ADS).' },
      { id: 'curve', name: 'Krzywa reakcji celowania', isToggle: false, isSelect: true, options: ['Standardowa', 'Liniowa', 'Dynamiczna'], paths: { PS4: 'Celowanie -> Typ krzywej reakcji', PS5: 'Celowanie -> Typ krzywej reakcji', PC: 'Aiming -> Aim Response Curve Type' }, beg: 'Profil zachowania drążka. Dynamiczna to najlepszy wybór dla graczy kontrolerów.', adv: 'Krzywa S-Shape (Dynamic) daje precyzyjną mikro-kontrolę wokół osi środkowej i natychmiastowe przyspieszenie na brzegach.' },
      { id: 'assist', name: 'Asysta celowania (Aim Assist)', isToggle: true, paths: { PS4: 'Celowanie -> Asysta celowania', PS5: 'Celowanie -> Asysta celowania', PC: 'Aiming -> Target Aim Assist' }, beg: 'Pomoc celowania wbudowana w grę. Zawsze włączona.', adv: 'Klucz do wygrywania starć. Wymaga nieustannego dryfu lewej gałki (RAA - Rotational Aim Assist) w celu aktywacji magnetyzmu.' }
    ]
  },
  movement: {
    title: 'Mechanika Ruchu',
    icon: Activity,
    items: [
      { id: 'sprint', name: 'Zachowanie sprintu', isToggle: false, isSelect: true, options: ['Ręczny', 'Automatyczny', 'Auto. Sprint Taktyczny'], paths: { PS4: 'Rozgrywka -> Automatyczny sprint', PS5: 'Rozgrywka -> Automatyczny sprint', PC: 'Gameplay -> Automatic Sprint' }, beg: 'Uruchamia najszybszy bieg od razu po wychyleniu gałki. Oszczędza kontroler.', adv: 'Auto Tac Sprint. Minimalizuje wejściowe opóźnienie animacji biegu, ułatwiając natychmiastowy unik.' },
      { id: 'sprint_del', name: 'Opóźnienie sprintu', isToggle: false, visual: 'slider', min: 0, max: 10, step: 1, paths: { PS4: 'Rozgrywka -> Opóźnienie sprintu taktycznego', PS5: 'Rozgrywka -> Opóźnienie sprintu taktycznego', PC: 'Gameplay -> Tactical Sprint Delay' }, beg: 'Brak opóźnienia gwarantuje natychmiastowy bieg.', adv: '0ms. Usuwa sztuczny bufor wejściowy silnika gry.' },
      { id: 'slide', name: 'Wślizg i Padanie', isToggle: false, isSelect: true, options: ['Tapnięcie', 'Przytrzymanie', 'Hybrydowe'], paths: { PS4: 'Rozgrywka -> Zachowanie wślizgu', PS5: 'Rozgrywka -> Zachowanie wślizgu', PC: 'Gameplay -> Slide/Dive Behavior' }, beg: 'Ułatwia robienie wślizgów poprzez pojedyncze, szybkie tapnięcie przycisku.', adv: 'Hybrid. Najszybsza rejestracja wślizgu bez opóźnienia wynikającego z czasu rejestracji przytrzymania przycisku.' },
      { id: 'para', name: 'Automatyczny spadochron', isToggle: true, paths: { PS4: 'Rozgrywka -> Spadochron', PS5: 'Rozgrywka -> Spadochron', PC: 'Gameplay -> Auto Parachute Deploy' }, beg: 'Wyłącz to, by lądować szybciej niż inni gracze, ale pamiętaj o ręcznym otwarciu!', adv: 'Wyłączenie zapobiega przypadkowym animacjom otwarcia spadochronu blisko dachów i obiektów.' },
      { id: 'mantle', name: 'Asysta wspinania', isToggle: true, paths: { PS4: 'Rozgrywka -> Autowspinanie', PS5: 'Rozgrywka -> Autowspinanie', PC: 'Gameplay -> Ground Mantle' }, beg: 'Wyłącz, aby postać nie wspinała się sama na przeszkody w trakcie strzelania.', adv: 'Zapobiega "Mantle Lock" - animacji blokującej broń podczas walk blisko niskich murków.' },
      { id: 'armor', name: 'Zachowanie płyt pancerza', isToggle: false, isSelect: true, options: ['Zastosuj jedną', 'Zastosuj wszystkie'], paths: { PS4: 'Rozgrywka -> Zachowanie pancerza', PS5: 'Rozgrywka -> Zachowanie pancerza', PC: 'Gameplay -> Armor Plate Behavior' }, beg: 'Zastosowanie pojedynczej płyty pozwala na szybkie przerwanie animacji w razie ataku.', adv: 'Zastosuj Jedną (Apply One). Maksymalna elastyczność i kontrola nad przerwaniem "platingu" sprintem.' },
      { id: 'interact', name: 'Interakcja i przeładowanie', isToggle: false, isSelect: true, options: ['Domyślne', 'Priorytet przeładowania', 'Priorytet interakcji'], paths: { PS4: 'Rozgrywka -> Interakcja / Przeładowanie', PS5: 'Rozgrywka -> Interakcja / Przeładowanie', PC: 'Gameplay -> Interact/Reload Behavior' }, beg: 'Umożliwia błyskawiczne zbieranie broni i skrzyń pojedynczym dotknięciem przycisku.', adv: 'Prioritize Interact. Klucz do ultra-szybkiego zbierania lootu z ziemi podczas startu meczu.' }
    ]
  },
  graphics: {
    title: 'Grafika i Widok',
    icon: Monitor,
    warning: "PS4 Pro na dużych mapach Warzone miewa problemy ze spadkiem wydajności. Poniższa konfiguracja optymalizuje czas renderowania klatek (GPU/CPU frame-times).",
    items: [
      { id: 'fov', name: 'Pole widzenia (FOV)', isToggle: false, visual: 'slider', min: 80, max: 120, step: 5, paths: { PS4: 'Grafika -> Widok -> Pole widzenia', PS5: 'Grafika -> Widok -> Pole widzenia', PC: 'Graphics -> View -> Field of View' }, beg: 'Szerokość obrazu. Na PS4 Pro zalecane stabilne 110. 120 może lekko obciążać procesor.', adv: 'Większe pole widzenia to mniejszy odczuwalny odrzut wizualny (visual recoil). Optymalna strefa wydajnościowa dla PS4 Pro to 108-112 FOV.' },
      { id: 'ads_fov', name: 'Pole widzenia celownika', isToggle: false, isSelect: true, options: ['Niezależne (Independent)', 'Zależne (Affected)'], paths: { PS4: 'Grafika -> Widok -> ADS FOV', PS5: 'Grafika -> Widok -> ADS FOV', PC: 'Graphics -> View -> ADS Field of View' }, beg: 'Affected zapobiega gwałtownemu przybliżaniu kamery podczas celowania, broń prawie nie skacze.', adv: 'Affected. Skaluje odrzut wizualny do globalnego FOV. Zapewnia kolosalne ułatwienie kontroli odrzutu.' },
      { id: 'w_fov', name: 'Pole widzenia broni', isToggle: false, isSelect: true, options: ['Domyślne', 'Wąskie', 'Szerokie (Wide)'], paths: { PS4: 'Grafika -> Widok -> Pole broni', PS5: 'Grafika -> Widok -> Pole broni', PC: 'Graphics -> View -> Weapon Field of View' }, beg: 'Broń wydaje się mniejsza na ekranie, co odsłania więcej otoczenia.', adv: 'Wide. Maksymalizuje widoczność krawędzi ekranu przy korzystaniu z masywnych rusznikarskich konfiguracji.' },
      { id: 'cas', name: 'FidelityFX CAS Wyostrzanie', isToggle: false, visual: 'slider', min: 0, max: 100, step: 5, paths: { PS4: 'Grafika -> Jakość -> Skalowanie i wyostrzanie', PS5: 'Grafika -> Jakość -> Skalowanie i wyostrzanie', PC: 'Graphics -> Quality -> Upscaling/Sharpening' }, beg: 'Usuwa rozmycie konsolowego obrazu. Wrogowie stają się ostrzy.', adv: 'Strength 90. Fantastyczny algorytm wyostrzający kontrast, niwelujący artefakty rozmycia przy antyaliasingu.' },
      { id: 'blur', name: 'Motion Blur (Świat / Broń)', isToggle: true, paths: { PS4: 'Grafika -> Rozmycie świata / broni', PS5: 'Grafika -> Rozmycie świata / broni', PC: 'Graphics -> Post Processing -> Motion Blur' }, beg: 'Wyłącz to, aby obraz był czytelny i ostry podczas gwałtownych obrotów kamery.', adv: 'Wyłączenie rozmycia uwalnia cykle procesora graficznego na architekturze Jaguar (PS4 Pro).' },
      { id: 'shake', name: 'Ruch kamery pierwszoosobowej', isToggle: false, visual: 'slider', min: 50, max: 100, step: 10, paths: { PS4: 'Grafika -> Widok -> Ruch kamery', PS5: 'Grafika -> Widok -> Ruch kamery', PC: 'Graphics -> View -> Camera Movement' }, beg: 'Trzęsienie kamery przy wybuchach i nalotach. Zmniejsz do minimalnych 50%.', adv: '50% (Least). Drastycznie zwiększa klarowność celowania w sytuacjach kryzysowych pod ostrzałem artylerii.' }
    ]
  },
  ui_audio: {
    title: 'Interfejs & Dźwięk',
    icon: Headphones,
    items: [
      { id: 'filter', name: 'Filtr kolorów', isToggle: false, isSelect: true, options: ['Brak', 'Filtr 1', 'Filtr 2 (Oba)', 'Filtr 3'], paths: { PS4: 'Interfejs -> Dostosowanie kolorów', PS5: 'Interfejs -> Dostosowanie kolorów', PC: 'Interface -> Color Customization -> Filter' }, beg: 'Filtr 2 niesamowicie ożywia i nasyca kolory w grze bez używania opcji monitora.', adv: 'Filter 2 + Target: Both + Intensity: 100%. Zwiększa luminancję barw, ułatwiając szybką identyfikację wrogów w cieniach.' },
      { id: 'hud', name: 'Marginesy bezpieczne HUD', isToggle: false, isSelect: true, options: ['Szerokie', 'Średnie', 'Minimalne (Środek)'], paths: { PS4: 'Interfejs -> HUD -> Bezpieczna strefa', PS5: 'Interfejs -> HUD -> Bezpieczna strefa', PC: 'Interface -> HUD -> Safe Area' }, beg: 'Przesuwa minimapę i informacje o amunicji bliżej środka, oszczędzając ruch oczu.', adv: 'Maksymalnie ściśnięty HUD skraca drogę sakkadową oka o kilkadziesiąt pikseli przy każdym spojrzeniu na radar.' },
      { id: 'cross', name: 'Środkowa kropka celownika', isToggle: false, isSelect: true, options: ['Wyłączona', 'Domyślna', 'Większa / Żółta'], paths: { PS4: 'Interfejs -> HUD -> Środkowa kropka', PS5: 'Interfejs -> HUD -> Środkowa kropka', PC: 'Interface -> HUD -> Center Dot' }, beg: 'Duża, jaskrawożółta kropka pośrodku ekranu ułatwia natychmiastowe namierzenie wroga przed celowaniem.', adv: 'Zapewnia stały i niezawodny punkt odniesienia do centrowania ekranu (Crosshair Centering).' },
      { id: 'radar', name: 'Minimapa', isToggle: false, isSelect: true, options: ['Okrągła', 'Kwadrat / Kontury Wł.'], paths: { PS4: 'Interfejs -> HUD -> Kształt minimapy', PS5: 'Interfejs -> HUD -> Kształt minimapy', PC: 'Interface -> HUD -> Minimap Shape' }, beg: 'Kwadratowa minimapa pokazuje o 20% większy wycinek terenu niż okrągła.', adv: 'Kwadratowy radar to absolutny wymóg taktyczny do śledzenia aktywności wrogich UAV.' },
      { id: 'audio', name: 'Miks audio', isToggle: false, isSelect: true, options: ['Kino domowe', 'Słuchawki', 'Sucker Punch', 'Wzmocnienie basów'], paths: { PS4: 'Audio -> Miks dźwięku', PS5: 'Audio -> Miks dźwięku', PC: 'Audio -> Volumes -> Audio Mix' }, beg: 'Ustawienie Sucker Punch oferuje najlepsze pozycjonowanie przestrzenne kroków przeciwnika.', adv: 'Sucker Punch (lub alternatywnie Boost Low) wygładza pasmo przenoszenia dla kluczowych odgłosów kroków na średnim dystansie.' },
      { id: 'mono', name: 'Dźwięk Mono', isToggle: true, paths: { PS4: 'Audio -> Dźwięk Mono -> Wyłącz', PS5: 'Audio -> Dźwięk Mono -> Wyłącz', PC: 'Audio -> Audio -> Mono Audio -> Off' }, beg: 'Zostaw wyłączone! Włączenie tej opcji psuje lokalizację wrogów (lewo/prawo).', adv: 'Bezwzględnie wyłączone. Łączenie kanałów stereo do jednego niszczy kierunkową percepcję akustyczną 3D.' }
    ]
  }
};

// --- SURVEY QUESTIONS DATA ---
const SURVEY_QUESTIONS = [
  {
    id: 'platform',
    question: 'Na jakiej platformie grasz najczęściej?',
    options: [
      { val: 'PS4', label: 'PlayStation 4 / Slim', desc: 'Wydajność krytyczna, staraj się oszczędzać każdą klatkę.' },
      { val: 'PS4 Pro', label: 'PlayStation 4 Pro', desc: 'Możliwe skalowanie 4K i wyższa ostrość z FidelityFX.' },
      { val: 'PS5', label: 'PlayStation 5', desc: 'Możliwość gry w 120 FPS, wysoka czułość i szeroki FOV.' },
      { val: 'PC', label: 'Komputer osobisty (PC)', desc: 'Maksymalna wydajność, specyficzne ścieżki i skróty klawiszowe.' }
    ]
  },
  {
    id: 'playstyle',
    question: 'Jaki jest Twój ulubiony styl rozgrywki?',
    options: [
      { val: 'cqc', label: 'Agresywny (CQC / Rusher)', desc: 'Walka w zwarciu, szybkie slajdy, wysoka czułość reakcji.', icon: Zap },
      { val: 'balanced', label: 'Zbalansowany / Taktyczny', desc: 'Kontrola stref, flankowanie, precyzja na średnim dystansie.', icon: Target },
      { val: 'sniper', label: 'Snajper / Długi dystans', desc: 'Snajperki, kontrola odrzutu, niższy mnożnik czułości ADS.', icon: Monitor }
    ]
  },
  {
    id: 'display',
    question: 'Do jakiego ekranu masz podłączoną konsolę/PC?',
    options: [
      { val: 'tv_standard', label: 'Zwykły Telewizor TV', desc: 'Możliwy wyższy Input Lag. Zalecane dynamiczne ułatwienia ruchu.' },
      { val: 'tv_game', label: 'TV z Trybem Gry (Game Mode)', desc: 'Zbalansowany czas reakcji, dobra widoczność w cieniach.' },
      { val: 'monitor', label: 'Monitor dla graczy (Niski Input Lag)', desc: 'Maksymalny odczyt klatek, precyzyjne strefy martwe (Deadzone: 3 lub mniej).' }
    ]
  },
  {
    id: 'controller',
    question: 'Jakiego rodzaju kontrolera (pada) używasz?',
    options: [
      { val: 'standard', label: 'Standardowy kontroler', desc: 'Brak łopatek. Układ przycisków zostanie dostosowany taktycznie.' },
      { val: 'pro', label: 'Pad Wyczynowy (SCUF / Edge / Łopatki)', desc: 'Dodatkowe przyciski z tyłu. Zostawimy domyślne mapowanie.' }
    ]
  }
];

// --- MAIN COMPONENT ---
const App = () => {
  const [activeTab, setActiveTab] = useState('controller');
  const [isAdvanced, setIsAdvanced] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState('balanced');
  const [activePlatform, setActivePlatform] = useState('PS4');
  const [expandedOptionId, setExpandedOptionId] = useState(null);

  // Core configurable settings state initialized with defaults
  const [settings, setSettings] = useState(INITIAL_VALUES);

  // Survey system states
  const [showSurvey, setShowSurvey] = useState(true);
  const [surveyStep, setSurveyStep] = useState(0);
  const [surveyAnswers, setSurveyAnswers] = useState({
    platform: 'PS4 Pro',
    playstyle: 'balanced',
    display: 'tv_game',
    controller: 'standard'
  });

  // Sharing System states
  const [shareSuccess, setShareSuccess] = useState(false);
  const [importedStatus, setImportedStatus] = useState(null); // 'success' | 'error'
  const [customCodeInput, setCustomCodeInput] = useState('');

  const categories = Object.keys(METADATA);
  const activeCategoryData = METADATA[activeTab];

  // Try to load state from URL parameters on mount (ZSSP Implementation)
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const encodedConfig = params.get('config');
      if (encodedConfig) {
        const decoded = JSON.parse(atob(encodedConfig));
        // Validate decoded object keys to prevent prototype pollution or crashed states
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
        setImportedStatus('success');
        setTimeout(() => setImportedStatus(null), 4000);
      }
    } catch (e) {
      // Quiet fail if URL parsing fails
    }
  }, []);

  // Update dynamic telemetry metrics based on selected Preset & Current settings
  const liveMetrics = useMemo(() => {
    if (selectedPreset === 'custom') {
      // Calculate dynamic values based on settings state
      const isUltraFov = settings.fov > 115;
      const lowDeadzone = settings.dz_l_min < 3;
      return {
        fps: isUltraFov ? '48-55 FPS (PS4 Pro)' : '58-60 FPS (PS4 Pro)',
        lag: lowDeadzone ? '36ms (Optimized)' : '45ms (Safe)',
        cpu: isUltraFov ? 'Wysokie' : 'Średnie',
        fov: `${settings.fov} FOV`
      };
    }
    return PRESETS[selectedPreset]?.metrics || PRESETS.balanced.metrics;
  }, [selectedPreset, settings.fov, settings.dz_l_min]);

  // Handle Preset applying
  const handlePresetChange = (presetId) => {
    setSelectedPreset(presetId);
    if (PRESETS[presetId]) {
      setSettings(prev => ({
        ...prev,
        ...PRESETS[presetId].overrides
      }));
    }
  };

  // Modify individual configuration field
  const updateSetting = (key, val) => {
    setSelectedPreset('custom'); // Any manual adjustment makes config custom
    setSettings(prev => ({
      ...prev,
      [key]: val
    }));
  };

  // Toggle standard boolean switches
  const toggleSetting = (key) => {
    setSelectedPreset('custom');
    setSettings(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  // Help Options Finder Accordion trigger
  const toggleOptionFinder = (id) => {
    setExpandedOptionId(expandedOptionId === id ? null : id);
  };

  // Survey Answer Processing -> Adaptive Config Engine
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
    // Generate an optimized configuration matching player profile
    let adapted = { ...INITIAL_VALUES };
    
    // 1. Platform influence
    setActivePlatform(surveyAnswers.platform);
    if (surveyAnswers.platform === 'PS4') {
      adapted.fov = 105; // Lower FOV to protect CPU performance on old hardware
      adapted.cas = 80;
    } else if (surveyAnswers.platform === 'PS4 Pro') {
      adapted.fov = 110;
      adapted.cas = 90;
    } else { // PS5 / PC
      adapted.fov = 120;
      adapted.cas = 100;
    }

    // 2. Playstyle adjustments
    if (surveyAnswers.playstyle === 'cqc') {
      adapted.sens = 2.0; // Higher speed
      adapted.dz_l_max = 30; // Quick reaction for movement breaking
      adapted.sprint = 'Auto. Sprint Taktyczny';
      adapted.slide = 'Hybrydowe';
    } else if (surveyAnswers.playstyle === 'sniper') {
      adapted.sens = 1.4; // Controlled aiming
      adapted.ads_low = 0.70;
      adapted.ads_high = 0.95;
      adapted.curve = 'Standardowa';
    } else {
      adapted.sens = 1.6;
      adapted.ads_low = 0.80;
      adapted.ads_high = 1.00;
    }

    // 3. Screen Type influence on deadzones & vision
    if (surveyAnswers.display === 'tv_standard') {
      adapted.dz_l_min = 5; // Prevent stick drift on generic controller setups
      adapted.filter = 'Filtr 2 (Oba)'; // Ożywij szary TV
    } else if (surveyAnswers.display === 'monitor') {
      adapted.dz_l_min = 2; // Elite response on zero lag monitor
    }

    // 4. Controller types
    if (surveyAnswers.controller === 'standard') {
      adapted.layout = 'Taktyczny'; // Tactical allows slide cancel easily
    } else {
      adapted.layout = 'Domyślny'; // Paddles handle slides
    }

    setSettings(adapted);
    setSelectedPreset('custom');
    setShowSurvey(false);
  };

  // ZSSP Share Config: Encode to Base64 and write to clipboard
  const generateShareLink = () => {
    try {
      const configStr = btoa(JSON.stringify(settings));
      const shareUrl = `${window.location.origin}${window.location.pathname}?config=${configStr}`;
      
      // Clipboard copy utilizing frame-safe fallback
      const textArea = document.createElement("textarea");
      textArea.value = shareUrl;
      textArea.style.position = "fixed"; 
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      
      const success = document.execCommand('copy');
      document.body.removeChild(textArea);

      if (success) {
        setShareSuccess(true);
        setTimeout(() => setShareSuccess(false), 3000);
      }
    } catch (e) {
      setImportedStatus('error');
      setTimeout(() => setImportedStatus(null), 3000);
    }
  };

  // Import configuration manually via pasted base64 string
  const handleImportConfig = () => {
    try {
      if (!customCodeInput) return;
      const decoded = JSON.parse(atob(customCodeInput.trim()));
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
      setImportedStatus('success');
      setCustomCodeInput('');
      setTimeout(() => setImportedStatus(null), 4000);
    } catch (e) {
      setImportedStatus('error');
      setTimeout(() => setImportedStatus(null), 4000);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-300 font-sans selection:bg-amber-500/30 pb-16">
      
      {/* HEADER TACTICAL */}
      <header className="border-b border-zinc-800/80 bg-zinc-900/50 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 py-4 flex flex-col sm:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-3">
            <Target className="w-8 h-8 text-amber-500 animate-pulse" />
            <div>
              <h1 className="text-xl md:text-2xl font-bold text-white tracking-widest uppercase flex items-center gap-2">
                Warzone <span className="text-amber-500 font-black">PS4 PRO</span>
              </h1>
              <p className="text-xs text-zinc-500 uppercase tracking-widest">Tactical Configurator v4.0</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button 
              onClick={() => {
                setSurveyStep(0);
                setShowSurvey(true);
              }}
              className="px-3 py-1.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-xs font-bold rounded-md flex items-center gap-1.5 transition-all text-zinc-400 hover:text-white"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Resetuj i Włącz Ankietę
            </button>

            {/* TOGGLE LEVEL */}
            <div className="flex items-center bg-zinc-950/80 p-1 rounded-lg border border-zinc-800">
              <button 
                onClick={() => setIsAdvanced(false)}
                className={`px-3 py-1.5 text-[11px] md:text-xs font-semibold rounded-md transition-all duration-200 ${!isAdvanced ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-500 hover:text-zinc-300'}`}
              >
                Początkujący
              </button>
              <button 
                onClick={() => setIsAdvanced(true)}
                className={`px-3 py-1.5 text-[11px] md:text-xs font-semibold rounded-md transition-all duration-200 flex items-center gap-1 ${isAdvanced ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20 shadow-sm' : 'text-zinc-500 hover:text-zinc-300'}`}
              >
                <Zap className="w-3 h-3" />
                Zaawansowany
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* ADAPTIVE SURVEY WIZARD SCREEN */}
      {showSurvey ? (
        <section className="max-w-3xl mx-auto px-4 py-12">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 md:p-8 shadow-2xl relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1.5 bg-zinc-800">
              <div 
                className="h-full bg-amber-500 transition-all duration-300"
                style={{ width: `${((surveyStep + 1) / SURVEY_QUESTIONS.length) * 100}%` }}
              />
            </div>

            <div className="flex justify-between items-center mb-6">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-amber-500" />
                <span className="text-xs uppercase font-mono tracking-widest text-amber-500 font-bold">Kreator Adaptacyjny</span>
              </div>
              <span className="text-xs font-mono text-zinc-500">Krok {surveyStep + 1} z {SURVEY_QUESTIONS.length}</span>
            </div>

            <h2 className="text-xl md:text-2xl font-black text-white mb-6 uppercase tracking-tight">
              {SURVEY_QUESTIONS[surveyStep].question}
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
              {SURVEY_QUESTIONS[surveyStep].options.map((option) => {
                const currentKey = SURVEY_QUESTIONS[surveyStep].id;
                const isSelected = surveyAnswers[currentKey] === option.val;
                return (
                  <button
                    key={option.val}
                    onClick={() => handleSurveyOptionSelect(currentKey, option.val)}
                    className={`p-4 rounded-xl text-left border transition-all duration-200 flex flex-col justify-between ${
                      isSelected 
                        ? 'bg-amber-500/10 border-amber-500 text-white shadow-[0_0_15px_rgba(245,158,11,0.1)]' 
                        : 'bg-zinc-950/50 border-zinc-800 hover:bg-zinc-900/40 hover:border-zinc-700 text-zinc-400'
                    }`}
                  >
                    <div className="flex justify-between items-center w-full mb-2">
                      <span className="font-bold text-sm text-zinc-200">{option.label}</span>
                      <div className={`w-4 h-4 rounded-full border flex items-center justify-center ${isSelected ? 'border-amber-500 bg-amber-500' : 'border-zinc-600'}`}>
                        {isSelected && <Check className="w-3 h-3 text-zinc-950 stroke-[3px]" />}
                      </div>
                    </div>
                    <p className="text-xs text-zinc-500 leading-relaxed">{option.desc}</p>
                  </button>
                );
              })}
            </div>

            <div className="flex justify-between items-center border-t border-zinc-800/80 pt-6">
              <button 
                onClick={() => setShowSurvey(false)}
                className="text-xs font-bold text-zinc-500 hover:text-zinc-300 transition-colors uppercase tracking-wider"
              >
                Pomiń kreator (Domyślne)
              </button>
              
              <button
                onClick={nextSurveyStep}
                className="px-6 py-3 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-black text-xs uppercase tracking-widest rounded-lg flex items-center gap-2 transition-all shadow-[0_4px_14px_rgba(245,158,11,0.2)]"
              >
                {surveyStep === SURVEY_QUESTIONS.length - 1 ? 'Generuj Profil' : 'Następny'}
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </section>
      ) : null}

      {/* MAIN CONFIGURATION DASHBOARD */}
      <main className={`max-w-6xl mx-auto px-4 py-8 transition-opacity duration-300 ${showSurvey ? 'opacity-20 pointer-events-none' : 'opacity-100'}`}>
        
        {/* TOP STATUS AND DYNAMIC ACTIONS ZONE */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 mb-8">
          
          {/* PRESET SELECTOR (9 cols) */}
          <section className="lg:col-span-8 p-6 bg-zinc-900/40 border border-zinc-800/80 rounded-2xl space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-500" />
                <h2 className="text-xs font-bold uppercase text-zinc-400 tracking-wider">Wybierz Szablon Główny</h2>
              </div>
              {selectedPreset === 'custom' && (
                <span className="text-[10px] bg-amber-500/10 text-amber-500 border border-amber-500/20 px-2 py-0.5 rounded font-black tracking-widest uppercase">
                  Własna Modyfikacja
                </span>
              )}
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {Object.values(PRESETS).map((p) => {
                const isSelected = selectedPreset === p.id;
                return (
                  <button
                    key={p.id}
                    onClick={() => handlePresetChange(p.id)}
                    className={`text-left p-3.5 rounded-xl border transition-all duration-300 ${
                      isSelected 
                        ? 'bg-zinc-900 border-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.15)] text-white' 
                        : 'bg-zinc-950/50 border-zinc-800/60 hover:border-zinc-700'
                    }`}
                  >
                    <div className="flex justify-between items-start mb-1.5">
                      <span className="text-[9px] font-mono font-bold uppercase tracking-wider text-zinc-500">Preset</span>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded font-black tracking-widest ${p.color}`}>
                        {p.badge}
                      </span>
                    </div>
                    <h3 className="font-bold text-sm flex items-center gap-1.5">
                      {p.name}
                      {isSelected && <Check className="w-3.5 h-3.5 text-amber-500" />}
                    </h3>
                  </button>
                );
              })}
            </div>
          </section>

          {/* SHARE & IMPORT PANEL (4 cols) */}
          <section className="lg:col-span-4 p-6 bg-zinc-900/40 border border-zinc-800/80 rounded-2xl flex flex-col justify-between space-y-4">
            <div>
              <h2 className="text-xs font-bold uppercase text-zinc-400 tracking-wider mb-2 flex items-center gap-1.5">
                <Share2 className="w-3.5 h-3.5 text-amber-500" /> Udostępnianie & Import
              </h2>
              <p className="text-[11px] text-zinc-500 leading-normal">
                Generuj natychmiastowe linki dla innych graczy lub wklej wygenerowany klucz konfiguracji.
              </p>
            </div>

            <div className="flex gap-2">
              <button
                onClick={generateShareLink}
                className="flex-1 py-2 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-black text-xs uppercase tracking-wider rounded-lg flex items-center justify-center gap-2 transition-all shadow-md"
              >
                {shareSuccess ? <ClipboardCheck className="w-4 h-4 animate-scaleUp" /> : <Copy className="w-4 h-4" />}
                {shareSuccess ? 'Skopiowano!' : 'Kopiuj Link'}
              </button>
            </div>

            <div className="flex items-center gap-2 bg-zinc-950/80 border border-zinc-800 p-1 rounded-lg">
              <input 
                type="text" 
                placeholder="Wklej klucz konfiguracji..."
                value={customCodeInput}
                onChange={(e) => setCustomCodeInput(e.target.value)}
                className="bg-transparent text-[11px] text-zinc-300 placeholder-zinc-600 px-2 py-1 w-full focus:outline-none font-mono"
              />
              <button 
                onClick={handleImportConfig}
                className="bg-zinc-800 text-white font-bold text-xs uppercase px-3 py-1 rounded hover:bg-zinc-700 transition-all"
              >
                Import
              </button>
            </div>

            {/* Error/Success Feedbacks */}
            {importedStatus && (
              <div className={`text-[11px] font-mono px-2 py-1 rounded text-center font-bold ${
                importedStatus === 'success' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'
              }`}>
                {importedStatus === 'success' ? '✓ Wczytano nową konfigurację!' : '✗ Błędny klucz konfiguracji.'}
              </div>
            )}
          </section>

        </div>

        {/* WORKSPACE AREA */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* SIDEBAR NAVIGATION (3 cols) */}
          <aside className="lg:col-span-3 space-y-4">
            <div className="bg-zinc-950 p-2 rounded-xl border border-zinc-800">
              <p className="text-[10px] font-bold text-zinc-600 uppercase tracking-widest mb-2 px-3">Kategorie opcji</p>
              <nav className="flex flex-row lg:flex-col gap-1 overflow-x-auto lg:overflow-visible pb-2 lg:pb-0 hide-scrollbar">
                {categories.map((key) => {
                  const cat = METADATA[key];
                  const Icon = cat.icon;
                  const isActive = activeTab === key;
                  return (
                    <button
                      key={key}
                      onClick={() => {
                        setActiveTab(key);
                        setExpandedOptionId(null);
                      }}
                      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all duration-200 whitespace-nowrap lg:whitespace-normal border ${
                        isActive 
                        ? 'bg-zinc-900 border-amber-500/30 text-amber-500 shadow-[inset_3px_0_0_0_rgba(245,158,11,1)]' 
                        : 'bg-transparent border-transparent text-zinc-400 hover:bg-zinc-900/50 hover:text-zinc-200'
                      }`}
                    >
                      <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? 'text-amber-500' : 'text-zinc-500'}`} />
                      <span className="font-bold uppercase text-xs tracking-wider">{cat.title}</span>
                    </button>
                  );
                })}
              </nav>
            </div>

            {/* TELEMETRY INFO PANEL */}
            <div className="p-4 bg-zinc-900/50 border border-zinc-800 rounded-xl space-y-4">
              <h3 className="text-xs uppercase text-zinc-500 font-bold flex items-center gap-2">
                <Activity className="w-4 h-4 text-amber-500" /> Status Wydajności (Est.)
              </h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between items-center border-b border-zinc-800/50 pb-2">
                  <span className="text-zinc-500 text-xs uppercase">Stabilność FPS:</span>
                  <span className="text-emerald-400 font-mono font-bold text-xs">{liveMetrics.fps}</span>
                </div>
                <div className="flex justify-between items-center border-b border-zinc-800/50 pb-2">
                  <span className="text-zinc-500 text-xs uppercase">Input Lag:</span>
                  <span className="text-amber-400 font-mono font-bold text-xs">{liveMetrics.lag}</span>
                </div>
                <div className="flex justify-between items-center border-b border-zinc-800/50 pb-2">
                  <span className="text-zinc-500 text-xs uppercase">Obciążenie CPU:</span>
                  <span className="text-zinc-300 font-mono font-bold text-xs">{liveMetrics.cpu}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-zinc-500 text-xs uppercase">Zalecany FOV:</span>
                  <span className="text-cyan-400 font-mono font-bold text-xs">{liveMetrics.fov}</span>
                </div>
              </div>
            </div>
          </aside>

          {/* EDITABLE SETTINGS CONTENT (9 cols) */}
          <section className="lg:col-span-9 space-y-6">
            
            <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4 border-b border-zinc-800/80 pb-4">
               <div className="flex items-center gap-3">
                 <activeCategoryData.icon className="w-6 h-6 text-amber-500" />
                 <h2 className="text-xl md:text-2xl font-black uppercase tracking-wider text-white">
                   {activeCategoryData.title}
                 </h2>
               </div>
               
               {/* PLATFORM SELECTOR */}
               <div className="flex items-center gap-2 bg-zinc-900 p-1 rounded-lg border border-zinc-800">
                 <span className="text-[10px] uppercase font-bold text-zinc-500 px-2">Ścieżka dla:</span>
                 {['PS4', 'PS5', 'PC'].map((p) => (
                   <button
                     key={p}
                     onClick={() => setActivePlatform(p)}
                     className={`px-2.5 py-1 text-xs font-mono font-bold rounded transition-all duration-150 ${
                       activePlatform === p 
                         ? 'bg-amber-500 text-zinc-950' 
                         : 'text-zinc-400 hover:text-white'
                     }`}
                   >
                     {p}
                   </button>
                 ))}
               </div>
            </div>

            {activeCategoryData.warning && (
              <div className="p-4 bg-amber-500/5 border-l-4 border-amber-500 rounded-r-lg flex items-start gap-3">
                <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-amber-200/90 leading-relaxed font-medium">
                  {activeCategoryData.warning}
                </p>
              </div>
            )}

            {/* TUNING PANEL GRID */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {activeCategoryData.items.map((item) => {
                const currentValue = settings[item.id];
                const isExpanded = expandedOptionId === item.id;
                
                return (
                  <div 
                    key={item.id} 
                    className={`relative p-5 rounded-xl border transition-all duration-300 flex flex-col justify-between ${
                      item.highlight 
                        ? 'bg-zinc-900/50 border-amber-500/30 hover:border-amber-500/50 shadow-md' 
                        : 'bg-zinc-900/10 border-zinc-800/80 hover:border-zinc-700'
                    }`}
                  >
                    
                    <div>
                      <div className="flex justify-between items-start mb-3">
                        <h3 className="font-bold text-zinc-100 uppercase text-xs tracking-wider pr-4">
                          {item.name}
                        </h3>
                        
                        {/* Interactive UI Binder representation */}
                        {item.isToggle ? (
                          <button onClick={() => toggleSetting(item.id)}>
                            <VisualToggle isActive={currentValue} />
                          </button>
                        ) : item.isSelect ? (
                          <div className="relative inline-block text-left">
                            <select 
                              value={currentValue}
                              onChange={(e) => updateSetting(item.id, e.target.value)}
                              className="bg-zinc-950 border border-zinc-800 text-amber-500 font-mono text-xs px-2 py-1 rounded focus:outline-none appearance-none cursor-pointer"
                            >
                              {item.options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                            </select>
                          </div>
                        ) : (
                          <span className="inline-block bg-zinc-950 border border-zinc-800 text-amber-500 font-mono text-xs px-2 py-1 rounded shadow-inner">
                            {currentValue}
                          </span>
                        )}
                      </div>

                      {/* Interactive Sliders */}
                      {item.visual === 'slider' && (
                        <div className="mb-4">
                          <input 
                            type="range"
                            min={item.min}
                            max={item.max}
                            step={item.step}
                            value={currentValue}
                            onChange={(e) => updateSetting(item.id, parseFloat(e.target.value))}
                            className="w-full accent-amber-500 bg-zinc-800 h-1 rounded-lg cursor-pointer"
                          />
                          <div className="flex justify-between text-[9px] text-zinc-600 font-mono mt-1">
                            <span>MIN: {item.min}</span>
                            <span>MAX: {item.max}</span>
                          </div>
                        </div>
                      )}

                      <div className="mt-3 pt-3 border-t border-zinc-800/50 flex items-start gap-2.5">
                        <Info className={`w-4 h-4 mt-0.5 flex-shrink-0 ${isAdvanced ? 'text-amber-500' : 'text-emerald-500'}`} />
                        <p className={`text-xs leading-relaxed ${isAdvanced ? 'text-zinc-400 font-mono text-[11px]' : 'text-zinc-300'}`}>
                          {isAdvanced ? item.adv : item.beg}
                        </p>
                      </div>
                    </div>

                    {/* INTERACTIVE OPTION FINDER PANEL */}
                    <div className="mt-4">
                      <button
                        onClick={() => toggleOptionFinder(item.id)}
                        className={`w-full flex items-center justify-between px-3 py-1.5 rounded text-xs transition-all duration-200 ${
                          isExpanded 
                            ? 'bg-amber-500 text-zinc-950 font-bold shadow-md' 
                            : 'bg-zinc-950/80 border border-zinc-800/50 text-zinc-400 hover:text-white hover:border-zinc-700'
                        }`}
                      >
                        <span className="flex items-center gap-1.5">
                          <MapPin className="w-3.5 h-3.5" />
                          Gdzie to jest?
                        </span>
                        {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      </button>

                      {/* Sliding Dropdown Info */}
                      {isExpanded && (
                        <div className="mt-2 p-3 bg-zinc-950/90 border border-zinc-800 rounded-lg text-xs space-y-2 animate-fadeIn">
                          <div className="flex items-center gap-1.5 border-b border-zinc-800 pb-1.5 text-zinc-400 font-mono">
                            {activePlatform === 'PC' ? <Laptop className="w-3.5 h-3.5" /> : <Tv className="w-3.5 h-3.5" />}
                            <span>Ścieżka ({activePlatform}):</span>
                          </div>
                          <p className="text-amber-400 font-semibold leading-relaxed">
                            {item.paths[activePlatform] || item.paths['PS4']}
                          </p>
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
          from { opacity: 0; transform: translateY(-5px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fadeIn {
          animation: fadeIn 0.25s ease-out forwards;
        }
        @keyframes scaleUp {
          0% { transform: scale(0.9); }
          100% { transform: scale(1); }
        }
        .animate-scaleUp {
          animation: scaleUp 0.2s ease-out forwards;
        }
      `}} />
    </div>
  );
};

export default App;
