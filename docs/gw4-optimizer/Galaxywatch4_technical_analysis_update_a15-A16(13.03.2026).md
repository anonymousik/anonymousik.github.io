DOSSIER INŻYNIERYJNE: Analiza Krytyczna Aktualizacji OTA (Android 15 -> 16 / One UI 16)

Autor: ƑERRට | Senior Systems Engineer
Status Dokumentu: JAWNY / DO UŻYTKU WEWNĘTRZNEGO
Data Analizy: Marzec 2026

1. WPROWADZENIE I DEFINICJA PROBLEMU
Aktualizacja OTA (Over-The-Air) migrująca urządzenia z Androida 15 (One UI 15) do Androida 16 (One UI 16) spowodowała masową degradację wydajności (tzw. performance regression) na urządzeniach z układami starszej generacji (np. Exynos W920 w smartwatchach lub Exynos 2100/2200 w smartfonach).
Objawy to:
 * Zacina się interfejs (mikro-zacięcia, stuttering).
 * Opóźniona reakcja wybudzania ekranu.
 * Wysoki drenaż baterii w stanie spoczynku (Idle Drain).
 * Zabijanie aplikacji w tle (agresywny OOM Killer).
2. ROZKŁAD NA CZYNNIKI PIERWSZE (FIRST PRINCIPLES ANALYSIS)
Aby zrozumieć problem, musimy odseparować warstwy systemu.
A. Warstwa Kompilatora (Błąd ART i JIT Thrashing)
Fakt logiczny: Android używa środowiska ART (Android Runtime). Aplikacje muszą zostać skompilowane z kodu bajtowego na kod maszynowy zrozumiały dla procesora.
Co poszło nie tak: W Androidzie 16 wprowadzono nowy, agresywniejszy profil kompilacji Ahead-Of-Time (AOT). Jednak paczka OTA z One UI 16 posiada błąd w skrypcie post-install. Nie wymusza ona pełnej kompilacji dex2oat po restarcie (prawdopodobnie, aby skrócić czas pierwszego uruchomienia tzw. boot time).
Wniosek: Urządzenie działa w trybie JIT (Just-In-Time). Za każdym razem, gdy otwierasz aplikację lub menu, procesor (Exynos) musi kompilować kod w locie. To powoduje skoki zużycia CPU do 100% i drastycznie pożera baterię.
B. Warstwa Renderowania (SurfaceFlinger i One UI 16 Compositor)
Fakt logiczny: One UI 16 wprowadził nowy silnik fizyki animacji i wielowarstwowe efekty rozmycia (Gaussian Blur) w czasie rzeczywistym, renderowane przez GPU za pomocą API Vulkan.
Co poszło nie tak: Skia (silnik renderujący 2D) w Androidzie 16 wymaga większej przepustowości pamięci (Memory Bandwidth). Starsze układy mają wspólną szynę pamięci dla CPU i GPU. Gdy One UI 16 próbuje nałożyć rozmycie na powiadomienia, przepustowość pamięci się dławi (tzw. Memory Bottleneck). GPU musi czekać na dane, co gubi klatki (spadek poniżej 60 FPS).
Wniosek: Nowe, "ciężkie" efekty wizualne One UI 16 nie są skalowane w dół dla słabszego sprzętu. Zostały nałożone "na sztywno".
C. Zarządzanie Pamięcią (MGLRU vs. zRAM)
Fakt logiczny: Android używa zRAM (kompresja danych w pamięci RAM), aby wcisnąć więcej aplikacji do ograniczonej pamięci (np. 1.5 GB lub 8 GB).
Co poszło nie tak: Android 16 domyślnie opiera się na MGLRU (Multi-Generational Least Recently Used) do zarządzania stronami pamięci. W One UI 16 parametr swappiness (określający, jak chętnie system pakuje dane do zRAM) został ustawiony zbyt agresywnie. Procesor traci cykle zegara na nieustanne kompresowanie i dekompresowanie tych samych bloków pamięci. To zjawisko nazywa się Memory Thrashing.
3. ROZWIĄZANIE PROBLEMU / INŻYNIERIA ODWROTNA (REVERSE ENGINEERING FIXES)
Skoro wiemy, że błędy leżą w ART, SurfaceFlingerze i zRAM, samo wyłączenie animacji z poziomu interfejsu (Ustawienia -> Opcje programisty) to tylko "plaster na złamanie otwarte". Musimy zaingerować głębiej.
Jako inżynier proponuję rozwiązanie systemowe, modyfikując ukryte flagi systemowe (device_config oraz setprop), do których mamy dostęp bez roota (przez ADB).
Krok 1: Naprawa środowiska ART (Eliminacja JIT Thrashingu)
Musimy wymusić na systemie, aby w trakcie bezczynności i podłączenia do ładowarki przekompilował WSZYSTKO (od frameworka po aplikacje użytkownika) do natywnego kodu (AOT).
# Wymuszenie pełnej optymalizacji tła (naprawia błąd skryptu OTA)
adb shell cmd package bg-dexopt-job

# Wymuszenie optymalizacji specyficznej dla "speed" (najwyższa wydajność, ignoruj rozmiar pliku)
adb shell "pm list packages | cut -d':' -f2 | while read package; do cmd package compile -m speed -f \$package; done"

Krok 2: Degradacja Compositora i wyłączenie sprzętowego Blura
Nie chcemy wyłączać wszystkich animacji (bo system traci estetykę). Chcemy wyłączyć tylko ten element, który dławi GPU – rozmycia okien w czasie rzeczywistym.
# Wyłączenie rozmycia tła na poziomie okien (SurfaceFlinger)
adb shell settings put global disable_window_blurs 1

# Wymuszenie sprzętowego wspomagania renderowania 2D bez obciążania szyny
adb shell setprop debug.hwui.renderer opengl
# lub w nowszych wersjach
adb shell setprop debug.hwui.use_vulkan false

Krok 3: Tuning Zarządzania Pamięcią (Ograniczenie procesów w tle)
Skoro zRAM dławi Exynosa, musimy ograniczyć ilość procesów, które są w ogóle dopuszczane do buforowania, co zmniejszy kompresję w locie. Zmodyfikujemy parametry ActivityManager i narzędzia śledzącego aplikacje w tle.
# Modyfikacja ustawień Phantom Process Killer'a w Androidzie 16
adb shell device_config put activity_manager max_phantom_processes 16

# Zmniejszenie limitu ukrytych procesów (cached processes)
adb shell device_config put activity_manager max_cached_processes 24

# Restrykcyjny tryb Doze (usypiania) by zapobiec wybudzaniu procesora przez One UI
adb shell dumpsys deviceidle force-idle

4. WNIOSKI KOŃCOWE
 * Zawinęła standaryzacja: Samsung, budując One UI 16 (Android 16), zoptymalizował system pod najnowszą, wydajną architekturę (np. Exynos W1000 lub Snapdragon Gen 4), zakładając, że przepustowość pamięci i wydajność kompresji jest darmowa. Na starszym krzemie to założenie upadło.
 * Brak skryptu Fallback: Największym błędem programistycznym tej aktualizacji OTA jest brak weryfikacji sprzętowej przed uruchomieniem compositora. System powinien automatycznie rozpoznać słabszy układ i wyłączyć window_blurs oraz zredukować max_cached_processes.
Dzięki powyższym modyfikacjom dokonanym przez ADB, naprawiamy błędy deweloperów Samsunga/Google, ręcznie adaptując ciężki system operacyjny do możliwości warstwy sprzętowej. Osiągamy stan balansu między nowym API Androida 16 a surowymi możliwościami krzemu.
