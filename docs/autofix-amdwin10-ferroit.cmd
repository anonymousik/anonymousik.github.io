@echo off
title Naprawa Sterowników AMD - Nieznany Nikomu Ferro
setlocal enabledelayedexpansion

echo Witaj w narzędziu naprawy sterowników przygotowanym przez Nieznanego Nikomu Ferro!
echo
:: Funkcja do pobierania i rozpakowywania DDU
echo Pobieranie narzędzia Display Driver Uninstaller (DDU)...
powershell -Command "Invoke-WebRequest -Uri 'https://www.guru3d.com/files-details/display-driver-uninstaller-download.html' -OutFile 'DDU.zip'"
powershell -Command "Expand-Archive -Path 'DDU.zip' -DestinationPath 'DDU'"
echo DDU zostało pobrane i rozpakowane.

:: Wykrywanie aktualnej wersji sterownika AMD
echo Wykrywanie aktualnej wersji sterownika AMD...
for /f "tokens=2 delims==" %%i in ('"wmic path win32_videocontroller get driverversion /value | findstr DriverVersion"') do set currentVersion=%%i
echo Aktualna wersja sterownika: !currentVersion!

:: Logika do obliczenia starszej wersji (przykład z założeniem, że wersja ma format XX.XX.XXXX.XXXX)
setlocal enabledelayedexpansion
set "version=!currentVersion!"
for /f "tokens=1,2,3,4 delims=." %%a in ("!version!") do (
    set major=%%a
    set minor=%%b
    set build=%%c
    set revision=%%d
)
:: Odejmowanie dwóch od numeru wersji
set /a minor=minor-2

:: Pobieranie starszej wersji sterownika AMD
echo Pobieranie starszej wersji sterownika AMD...
set downloadUrl=https://www.amd.com/en/support/download/driver/!major!.!minor!.!build!.!revision!
powershell -Command "Invoke-WebRequest -Uri '!downloadUrl!' -OutFile 'AMDDriver.exe'"

:: Restart do trybu awaryjnego
echo Uruchamianie systemu w trybie awaryjnym...
bcdedit /set {default} safeboot minimal
shutdown /r /f /t 0
exit

:SAFEMODE
echo Tryb awaryjny uruchomiony. Rozpoczynam czyszczenie sterowników...
cd DDU
start "" "Display Driver Uninstaller.exe"
:: Użytkownik musi wykonać kroki w DDU ręcznie, ponieważ pełna automatyzacja nie jest możliwa

echo Instalacja starszej wersji sterownika AMD...
start "" "AMDDriver.exe"

:: Resetuj do normalnego trybu
bcdedit /deletevalue {default} safeboot
echo System zostanie uruchomiony ponownie w normalnym trybie za 10 sekund...
timeout /t 10
shutdown /r /f /t 0