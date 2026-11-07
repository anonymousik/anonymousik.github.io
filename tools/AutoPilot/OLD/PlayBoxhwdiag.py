#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
# PLAYBOX HARDWARE & SYSTEM DIAGNOSTICS
# Kompleksowa ekstrakcja metryk CPU, pamięci, temperatur i błędów dekodera.
# ==============================================================================

import subprocess

def run_adb(cmd):
    """Wykonuje komendę ADB i zwraca sformatowany tekst (ignorując błędy stderr w wyniku)."""
    try:
        # Przechwytujemy też stderr, by wyłapać "Permission denied" jako tekst, a nie błąd basha.
        res = subprocess.run(f"adb shell \"{cmd}\"", shell=True, capture_output=True, text=True, timeout=10)
        output = res.stdout.strip()
        error = res.stderr.strip()
        if output:
            return output
        elif error:
            return f"BŁĄD: {error}"
        else:
            return "Brak danych (pusta odpowiedź)."
    except Exception as e:
        return f"Wyjątek wywołania: {e}"

def print_header(title):
    print(f"\n\033[96m{'='*60}")
    print(f" 🔍 {title}")
    print(f"{'='*60}\033[0m")

def diagnostics_suite():
    # ---------------------------------------------------------
    # 1. PARAMETRY PROCESORA (CPU FREQ) I THROTTLING
    # ---------------------------------------------------------
    print_header("TAKTOWANIE CPU (THROTTLING CHECK)")
    freq_cur = run_adb("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
    freq_max = run_adb("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq")
    freq_gov = run_adb("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    
    print(f"Zarządca (Governor): {freq_gov}")
    try:
        cur_mhz = int(freq_cur) / 1000
        max_mhz = int(freq_max) / 1000
        print(f"Bieżące taktowanie:  {cur_mhz:.0f} MHz")
        print(f"Maksymalne:          {max_mhz:.0f} MHz")
        if cur_mhz < (max_mhz * 0.7):
            print("\033[93m[UWAGA] Prawdopodobny Throttling. Częstotliwość obcięta o >30%.\033[0m")
        else:
            print("\033[92m[OK] CPU pracuje bez dławienia termicznego.\033[0m")
    except ValueError:
        print(f"Błąd odczytu: Cur: '{freq_cur}' / Max: '{freq_max}'")

    # ---------------------------------------------------------
    # 2. STATUS CIEPLNY (THERMAL API)
    # ---------------------------------------------------------
    print_header("CZUJNIKI TERMICZNE (THERMALSERVICE)")
    # Używamy dumpsys, bo /sys/class/thermal/... jest zablokowane
    thermal_data = run_adb("dumpsys thermalservice | grep -iE 'mIsThrottling|temperature|warning'")
    print(thermal_data)
    
    # ---------------------------------------------------------
    # 3. ZUŻYCIE PAMIĘCI STERTY (HEAP) I WYCIEKI VRAM
    # ---------------------------------------------------------
    print_header("PAMIĘĆ PODRĘCZNA I RAM (OOM CHECK)")
    meminfo_slim = run_adb("dumpsys meminfo | grep -E 'Free RAM:|Used RAM:|Lost RAM:'")
    print(meminfo_slim)
    
    print("\n\033[90m[*] Sprawdzanie procesu aplikacji SmartTube...\033[0m")
    # Zrzucamy szczegółowe statystyki zrzutu graficznego tylko dla SmartTube, jeśli jest uruchomiony.
    smarttube_mem = run_adb("dumpsys meminfo org.smarttube.stable | grep -E 'Graphics:|TOTAL:'")
    if "TOTAL:" in smarttube_mem:
        print(smarttube_mem)
    else:
        print("SmartTube nie jest aktualnie aktywny/w pamięci.")

    # ---------------------------------------------------------
    # 4. DIAGNOSTYKA SYSTEMU PLIKÓW I KERNELA (DMESG)
    # ---------------------------------------------------------
    print_header("KRYTYCZNE BŁĘDY KERNELA (DMESG/OOM)")
    # dmesg często wymaga roota, ale sprawdzimy, co pozwoli odczytać system operacyjny.
    # Szukamy zabójcy procesów (OOM Killer) i błędów broadcoma (brcm/v3d/omx).
    dmesg_errors = run_adb("dmesg | tail -n 200 | grep -iE 'Out of memory|oom-killer|v3d|brcm|omx|timeout|starved'")
    if "Permission denied" in dmesg_errors or "klogctl" in dmesg_errors:
         print("\033[90m[INFO] Odczyt dmesg (log jądra) zablokowany bez roota. Przechodzę do logcat.\033[0m")
    elif dmesg_errors and dmesg_errors != "Brak danych (pusta odpowiedź).":
         print(f"\033[91m{dmesg_errors}\033[0m")
    else:
         print("\033[92m[OK] Brak błędów kernela w ostatnich 200 liniach.\033[0m")

    # ---------------------------------------------------------
    # 5. DIAGNOSTYKA MEDIA CODEC (WYCIEKI STAGEFRIGHT)
    # ---------------------------------------------------------
    print_header("STATUS DEKODERA (MEDIA CODEC / STAGEFRIGHT)")
    media_metrics = run_adb("dumpsys media.metrics | grep -iE 'broadcom|omx|dropped|stall' | tail -n 10")
    if media_metrics and media_metrics != "Brak danych (pusta odpowiedź).":
        print(media_metrics)
    else:
        print("\033[90m[INFO] Brak wycieków w metrykach MediaCodec w ostatniej sesji.\033[0m")

if __name__ == "__main__":
    print("\033[93m[*] Rozpoczynam ekstrakcję pełnego zrzutu z maszyny...\033[0m")
    # Szybki test połączenia
    res = subprocess.run("adb devices", shell=True, capture_output=True, text=True)
    if "device\n" not in res.stdout and "\tdevice" not in res.stdout:
        print("\033[91m[!] Brak połączenia ADB. Sprawdź kabel/WiFi.\033[0m")
    else:
        diagnostics_suite()
        print("\n\033[92m[✓] Ekstrakcja zakończona pomyślnie.\033[0m")