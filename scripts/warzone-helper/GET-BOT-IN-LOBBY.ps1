<#
.SYNOPSIS
    WARZONE-GET-BOT-IN-LOBBY - Automatyzator Geo-Fencingu (SBMM) z auto-instalatorem
.DESCRIPTION
    Kompletne, bezobsługowe narzędzie realizujące blokadę regionalnych serwerów (UE/US).
    Wersja 5.0.0 zawiera wbudowany interaktywny instalator, omijanie ExecutionPolicy,
    oraz generowanie skrótów na pulpicie.
.AUTHOR
    Anonymousik
.LINK
    https://anonymousik.is-a.dev/scripts/warzone-helper/bot-in-lobby
#>

[CmdletBinding()]
param (
    [switch]$Daemon
)

$ErrorActionPreference = "Stop"

# ==============================================================================
# 1. KONFIGURACJA GLOBALNA ŚRODOWISKA
# ==============================================================================
$Global:ToolName    = "WARZONE-GET-BOT-IN-LOBBY"
$Global:Version     = "5.0.0"
$Global:RulePrefix  = "WGBIL_Rule"
$Global:TaskName    = "WarzoneHelper_Daemon"
$Global:URL         = "https://anonymousik.is-a.dev/scripts/warzone-helper/GET-BOT-IN-LOBBY.ps1"

$Global:InstallDir  = "$env:ProgramData\WARZONE-GET-BOT-IN-LOBBY"
$Global:InstallPath = "$Global:InstallDir\GET-BOT-IN-LOBBY.ps1"

$Global:Servers_EU  = @("185.34.104.0/24", "185.34.105.0/24", "185.34.106.0/24", "185.34.107.0/24", "185.225.208.0/22")
$Global:Servers_US  = @("66.43.0.0/16", "24.105.0.0/16")
$Global:CheckNodes  = @{
    "Afryka (ZA)" = "102.130.112.1"
    "Brazylia (SA)" = "177.54.144.1"
}

# ==============================================================================
# 2. AUTO-ELEWACJA UPRAWNIEŃ & BYPASS (SMART BOOTSTRAPPER)
# ==============================================================================
function Assert-Administrator {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        if ($Daemon) { exit }
        Write-Host "[!] Wymagane uprawnienia administratora. Następuje automatyczna elewacja..." -ForegroundColor Yellow
        # Automatyczne ominięcie ExecutionPolicy przy restarcie z uprawnieniami Admina
        Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Normal -File `"$PSCommandPath`"" -Verb RunAs
        exit
    }
}

Assert-Administrator

# ==============================================================================
# 3. INTERFEJS WIZUALNY (MOTD)
# ==============================================================================
function Show-MOTD {
    Clear-Host
    Write-Host "================================================================" -ForegroundColor DarkGray
    Write-Host "   __      __   _  ___  ____  ___  _  _  ____    _  _  ____    " -ForegroundColor Cyan
    Write-Host "   \ \    / /  / \| _ \|_  / / _ \| \| || __|  | || || __|   " -ForegroundColor Cyan
    Write-Host "    \ \/\/ /  / _ \   / / / | (_) | .` || _|   | __ || _|    " -ForegroundColor Cyan
    Write-Host "     \_/\_/  /_/ \_\_\|/___| \___/|_|\_||___|  |_||_||___|   " -ForegroundColor Cyan
    Write-Host "                                                                "
    Write-Host "               WARZONE HELPER : BOT IN LOBBY                    " -ForegroundColor Green
    Write-Host "               AUTOR: Anonymousik | v$Global:Version                  " -ForegroundColor Yellow
    Write-Host "      $Global:URL       " -ForegroundColor DarkCyan
    Write-Host "================================================================" -ForegroundColor DarkGray
    Write-Host ""
}

# ==============================================================================
# 4. INTERAKTYWNY KREATOR INSTALACJI (WIZARD)
# ==============================================================================
function Invoke-Installer {
    if ($PSCommandPath -eq $Global:InstallPath -or $Daemon) {
        return # Skrypt jest już zainstalowany w docelowej ścieżce lub działa jako Demon
    }

    Show-MOTD
    Write-Host "[!] WYKRYTO URUCHOMIENIE Z LOKALIZACJI TYMCZASOWEJ" -ForegroundColor Yellow
    Write-Host "Zalecana jest instalacja narzędzia w bezpiecznym środowisku systemowym ($Global:InstallDir)." -ForegroundColor White
    Write-Host ""
    $installChoice = Read-Host "Czy chcesz zainstalować narzędzie teraz? (T/N)"
    
    if ($installChoice -match "^[TtYy]$") {
        Write-Host "`n[*] Rozpoczynanie procesu instalacji..." -ForegroundColor Cyan
        
        # Tworzenie katalogu
        Write-Host "  -> Tworzenie struktury katalogów..." -NoNewline
        if (-not (Test-Path $Global:InstallDir)) {
            New-Item -ItemType Directory -Path $Global:InstallDir -Force | Out-Null
        }
        Start-Sleep -Milliseconds 400
        Write-Host " [OK]" -ForegroundColor Green
        
        # Kopiowanie pliku
        Write-Host "  -> Wdrażanie silnika zapory..." -NoNewline
        Copy-Item -Path $PSCommandPath -Destination $Global:InstallPath -Force
        Start-Sleep -Milliseconds 400
        Write-Host " [OK]" -ForegroundColor Green

        # Globalne odblokowanie wykonywania skryptów dla spójności środowiska
        Write-Host "  -> Konfiguracja ExecutionPolicy..." -NoNewline
        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 400
        Write-Host " [OK]" -ForegroundColor Green

        # Tworzenie skrótu na pulpicie
        Write-Host "  -> Generowanie skrótu na pulpicie..." -NoNewline
        try {
            $WshShell = New-Object -ComObject WScript.Shell
            $Shortcut = $WshShell.CreateShortcut("$env:PUBLIC\Desktop\Warzone Bot Lobby.lnk")
            $Shortcut.TargetPath = "powershell.exe"
            $Shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$Global:InstallPath`""
            $Shortcut.IconLocation = "shell32.dll,262" # Ikona tarczy sieciowej
            $Shortcut.Description = "Warzone Helper: Bot in Lobby"
            $Shortcut.Save()
            Write-Host " [OK]" -ForegroundColor Green
        } catch {
            Write-Host " [BŁĄD SKRÓTU]" -ForegroundColor Red
        }

        Write-Host "`n[+] Instalacja zakończona sukcesem!" -ForegroundColor Green
        Write-Host "[*] Uruchamianie zintegrowanego środowiska za 3 sekundy..." -ForegroundColor Cyan
        Start-Sleep -Seconds 3
        
        # Uruchomienie nowej, zainstalowanej instancji i zamknięcie obecnej
        Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Normal -File `"$Global:InstallPath`""
        exit
    }
}

# ==============================================================================
# 5. SILNIK ZAPORY (FIREWALL ENGINE)
# ==============================================================================
function Set-GeoFenceRules {
    param([string[]]$IPRanges, [string]$Tag, [switch]$Quiet)
    
    $index = 1
    foreach ($IP in $IPRanges) {
        $ruleName = "${Global:RulePrefix}_${Tag}_$index"
        $rule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
        if (-not $rule) {
            New-NetFirewallRule -DisplayName $ruleName -Direction Outbound -Action Block -RemoteAddress $IP -Protocol UDP -Profile Any -Enabled True | Out-Null
        } else {
            Set-NetFirewallRule -DisplayName $ruleName -Enabled True | Out-Null
        }
        $index++
    }
    if (-not $Quiet) { Write-Host "[+] Wdrożono rygor zaporowy ($Tag)" -ForegroundColor Green }
}

function Clear-GeoFenceRules {
    param([switch]$Quiet)
    $rules = Get-NetFirewallRule | Where-Object { $_.DisplayName -like "$($Global:RulePrefix)*" } -ErrorAction SilentlyContinue
    if ($rules) {
        $rules | Remove-NetFirewallRule
        if (-not $Quiet) { Write-Host "[-] Zdemontowano filtry zapory (Open-NAT Przywrócony)." -ForegroundColor Red }
    }
}

# ==============================================================================
# 6. DIAGNOSTYKA PROAKTYWNA (PRE-FLIGHT)
# ==============================================================================
function Start-PreFlightChecks {
    param([switch]$Quiet)
    if (-not $Quiet) { Write-Host "[*] Wykonywanie procesów przygotowawczych (Pre-Flight)..." -ForegroundColor Cyan }
    
    try { Clear-DnsClientCache } catch { ipconfig /flushdns > $null }
    netsh int tcp set global autotuninglevel=normal > $null
    
    if (-not $Quiet) {
        foreach ($node in $Global:CheckNodes.GetEnumerator()) {
            $ping = Test-Connection -ComputerName $node.Value -Count 1 -ErrorAction SilentlyContinue
            if ($ping) { Write-Host "    -> Latencja $($node.Name) : $($ping.ResponseTime) ms" -ForegroundColor DarkGray }
        }
    }
}

# ==============================================================================
# 7. ADAPTACYJNY SILNIK OPTYMALIZACJI
# ==============================================================================
function Invoke-AdaptiveOptimization {
    param([switch]$Quiet)
    Start-PreFlightChecks -Quiet:$Quiet
    $hour = (Get-Date).Hour
    Clear-GeoFenceRules -Quiet:$Quiet

    if ($hour -ge 1 -and $hour -le 8) {
        if (-not $Quiet) { Write-Host "[+] Tryb NOCNY (1:00-8:00) -> Cel: Afryka / Bliski Wschód" -ForegroundColor Green }
        Set-GeoFenceRules -IPRanges $Global:Servers_EU -Tag "EU_NIGHT" -Quiet:$Quiet
    } elseif ($hour -gt 8 -and $hour -le 15) {
        if (-not $Quiet) { Write-Host "[+] Tryb DZIENNY (8:00-15:00) -> Cel: Ameryka Południowa" -ForegroundColor Green }
        Set-GeoFenceRules -IPRanges $Global:Servers_EU -Tag "EU_DAY" -Quiet:$Quiet
        Set-GeoFenceRules -IPRanges $Global:Servers_US -Tag "US_DAY" -Quiet:$Quiet
    } else {
        if (-not $Quiet) { Write-Host "[+] Tryb SZCZYTOWY (15:00-1:00) -> Ekstremalny Geo-Fencing (Block EU+US)" -ForegroundColor Green }
        Set-GeoFenceRules -IPRanges $Global:Servers_EU -Tag "EU_PEAK" -Quiet:$Quiet
        Set-GeoFenceRules -IPRanges $Global:Servers_US -Tag "US_PEAK" -Quiet:$Quiet
    }
}

# ==============================================================================
# 8. INTEGRACJA SYSTEMOWA (TASK SCHEDULER & DEMON)
# ==============================================================================
function Register-SystemIntegration {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Global:InstallPath`" -Daemon"
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    Register-ScheduledTask -TaskName $Global:TaskName -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null
    Write-Host "[+] Pomyślnie zarejestrowano usługę tła. Narzędzie uruchomi się z systemem." -ForegroundColor Green
}

function Unregister-SystemIntegration {
    if (Get-ScheduledTask -TaskName $Global:TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Global:TaskName -Confirm:$false
        Write-Host "[-] Usługa tła wyrejestrowana." -ForegroundColor Yellow
    } else {
        Write-Host "[!] Usługa tła nie jest zainstalowana." -ForegroundColor DarkGray
    }
}

function Start-Daemon {
    $locked = $false
    while ($true) {
        $process = Get-Process -Name "Cod", "bootstrapper" -ErrorAction SilentlyContinue
        if ($process -and -not $locked) {
            Invoke-AdaptiveOptimization -Quiet
            $locked = $true
        } elseif (-not $process -and $locked) {
            Clear-GeoFenceRules -Quiet
            $locked = $false
        }
        Start-Sleep -Seconds 15
    }
}

# ==============================================================================
# KONTROLER GŁÓWNY (MAIN CONTROLLER)
# ==============================================================================

if ($Daemon) {
    Start-Daemon
    exit
}

# Uruchom Instalator jeśli włączone z nietypowej lokalizacji
Invoke-Installer

# Główne Menu TUI
do {
    Show-MOTD
    Write-Host "WYBIERZ AKCJĘ OPERACYJNĄ:" -ForegroundColor White
    Write-Host " [1] Uruchom jednorazową optymalizację adaptacyjną" -ForegroundColor Green
    Write-Host " [2] Wyczyść blokady i przywróć fabryczne reguły sieci" -ForegroundColor Yellow
    Write-Host " [3] Zainstaluj narzędzie w systemie (Automatyzacja Tła / Autostart)" -ForegroundColor Cyan
    Write-Host " [4] Odinstaluj automatyzację z systemu" -ForegroundColor Red
    Write-Host " [0] Wyjście" -ForegroundColor Gray
    Write-Host ""
    
    $choice = Read-Host "Wybór"
    
    switch ($choice) {
        '1' { Invoke-AdaptiveOptimization }
        '2' { Clear-GeoFenceRules }
        '3' { Register-SystemIntegration }
        '4' { Unregister-SystemIntegration }
        '0' { Write-Host "[*] Zamykanie..."; break }
        default { Write-Host "[!] Nieprawidłowy wybór!" -ForegroundColor Red }
    }
    
    if ($choice -ne '0') {
        Write-Host "`nNaciśnij Enter, aby kontynuować..." -ForegroundColor DarkGray
        Read-Host
    }
} while ($choice -ne '0')