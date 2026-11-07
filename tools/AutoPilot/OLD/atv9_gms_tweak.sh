#!/bin/bash
# Zestaw poleceń optymalizacyjnych dla GMS na środowisku produkcyjnym

echo "[*] Usuwanie GMS z białej listy optymalizacji energetycznej (Doze)..."
adb shell dumpsys deviceidle whitelist -com.google.android.gms

echo "[*] Odbieranie uprawnień do nielimitowanego działania w tle (AppOps)..."
adb shell cmd appops set com.google.android.gms RUN_IN_BACKGROUND ignore
adb shell cmd appops set com.google.android.gms RUN_ANY_IN_BACKGROUND ignore

echo "[*] Wymuszanie koszyka App Standby na RESTRICTED (Bucket 40)..."
adb shell am set-standby-bucket com.google.android.gms 40

echo "[*] Wyłączanie modułu Partner Setup (częste źródło wycieków PSS telemetrii)..."
adb shell pm disable-user --user 0 com.google.android.partnersetup

echo "[*] Optymalizacja zakończona. Restart demona aktywności..."
adb shell am kill com.google.android.gms
