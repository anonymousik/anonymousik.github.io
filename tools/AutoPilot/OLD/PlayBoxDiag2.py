#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
# PLAYBOX DIAGNOSTIC PROFILER - TIME-FILTERED EDITION
# Ekstrakcja logów awarii (Hang/Starvation) w przedziale czasowym
# ==============================================================================

import subprocess
import sys
import re

def run_adb(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        return e.output

def print_header(title):
    print(f"\n\033[95m{'='*70}")
    print(f" ⏱️  {title}")
    print(f"{'='*70}\033[0m")

def run_diagnostics():
    print("\033[93m[*] Rozpoczynam kierunkowy zrzut logów z przedziału 05:20 - 05:25...\033[0m")
    
    # Krok 1: Zrzut gigantycznej ilości logów, filtrowanie po czasie (05:20:xx do 05:25:xx)
    # Następnie wyciąganie krytycznych słów kluczowych dla błędu zamrożenia OMX.
    print_header("ANALIZA AWARII BROADCOM OMX (05:20 - 05:25)")
    
    # Wyjaśnienie Regexu: Szuka logów zaczynających się od 05:20, 05:21, 05:22, 05:23, 05:24, 05:25
    time_regex = "05:2[0-5]:"
    error_keywords = "OMX|Broadcom|ExoPlayer|V3D|timeout|starvation|stuck|fatal|codec|underrun|stall"
    
    logcat_cmd = f'adb shell "logcat -d -v time | grep -E \'{time_regex}\' | grep -iE \'{error_keywords}\'"'
    logs = run_adb(logcat_cmd)
    
    found_errors = False
    if logs.strip():
        for line in logs.splitlines():
            # Kolorowanie wyjścia na podstawie powagi (Severity)
            if re.search(r" E | F |Fatal|timeout|stuck", line, re.IGNORECASE):
                print(f"\033[91m{line}\033[0m") # Czerwony dla błędów krytycznych
                found_errors = True
            elif re.search(r" W |warning|starvation|underrun", line, re.IGNORECASE):
                print(f"\033[93m{line}\033[0m") # Żółty dla ostrzeżeń o buforze
                found_errors = True
            else:
                print(f"\033[90m{line}\033[0m") # Szary dla kontekstowego info (OMX state)
    
    if not found_errors:
        print("\033[92mBrak zrzutów timeout'u OMX w zadanym oknie czasowym.\033[0m")
        print("\033[90mMożliwe, że bufor logcat został już nadpisany (wymaga zrzutu zaraz po awarii) lub błąd był nierejestrowany przez kernel.\033[0m")

    # Krok 2: Zrzut aktualnego statusu pamięci ExoPlayera na urządzeniu
    print_header("STATUS ALOKACJI PAMIĘCI (ExoPlayer Limits)")
    mem_cmd = 'adb shell settings get global exoplayer_buffer_limit'
    buffer_limit = run_adb(mem_cmd).strip()
    
    chunk_cmd = 'adb shell settings get global exoplayer_dash_chunk_size'
    chunk_size = run_adb(chunk_cmd).strip()
    
    print(f"\033[97mAktywny limit bufora: \033[96m{buffer_limit} bajtów\033[0m")
    print(f"\033[97mAktywny rozmiar paczki DASH: \033[96m{chunk_size} bajtów\033[0m")
    
    print("\n\033[92m[✓] Skanowanie celowane zakończone.\033[0m")

if __name__ == "__main__":
    devices = run_adb("adb devices")
    if "device\n" not in devices and "\tdevice" not in devices:
        print("\033[91m[!] Brak połączenia ADB. Najpierw podłącz urządzenie.\033[0m")
        sys.exit(1)
        
    run_diagnostics()