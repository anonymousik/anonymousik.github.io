#!/usr/bin/env bash

# GALAXY WATCH 4 - SAFE DEBLOAT SUITE (Android 16 / One UI 8.0)
# Cel: Redukcja procesów w tle bez utraty powiadomień i funkcji zdrowotnych.

echo "🚀 Inicjowanie bezpiecznego debloatu..."

# 1. BIXBY & GŁOS (Zwalnia zasoby mikrofonu i CPU)
adb shell pm disable-user --user 0 com.samsung.android.bixby.agent
adb shell pm disable-user --user 0 com.samsung.android.bixby.wakeup
adb shell pm disable-user --user 0 com.samsung.android.intellivoiceservice

# 2. RETAIL & DEMO (Całkowicie zbędne dla użytkownika)
adb shell pm disable-user --user 0 com.google.android.apps.wearable.retailattractloop

# 3. CZCIONKI (Pozostawia systemową, wyłącza zbędne style)
adb shell pm disable-user --user 0 com.monotype.android.font.rosemary
adb shell pm disable-user --user 0 com.monotype.android.font.cooljazz
adb shell pm disable-user --user 0 com.monotype.android.font.chococooky
adb shell pm disable-user --user 0 com.monotype.android.font.foundation

# 4. DODATKI SAMSUNG (Wyłącz jeśli nie używasz)
adb shell pm disable-user --user 0 com.samsung.android.app.reminder
adb shell pm disable-user --user 0 com.samsung.android.app.routines
adb shell pm disable-user --user 0 com.samsung.android.watch.cameracontroller

# 5. TARCZE ANALOGOWE I DODATKOWE (Bezpieczne wyłączenie nieużywanych grafik)
# Zostawiamy 'basic' i 'digital', wyłączamy te najbardziej obciążające RAM:
adb shell pm disable-user --user 0 com.samsung.android.watch.watchface.animal
adb shell pm disable-user --user 0 com.samsung.android.watch.watchface.aremoji
adb shell pm disable-user --user 0 com.samsung.android.watch.watchface.bitmoji
adb shell pm disable-user --user 0 com.samsung.android.watch.watchface.endangeredanimal

# 6. DOSTĘPNOŚĆ (Tylko jeśli nie używasz czytnika ekranu TalkBack)
# adb shell pm disable-user --user 0 com.google.android.marvin.talkback

echo "✅ Operacja zakończona. Zalecany restart zegarka!"

