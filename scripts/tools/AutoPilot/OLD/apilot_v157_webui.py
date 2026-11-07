#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  PLAYBOX TITANIUM v16.0 — ADVANCED NETWORK CONTROLLER (OpenWrt Style)        ║
║  Target : Sagemcom DCTIW362P | Android TV 9 API 28 | Cortex-A15              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Opis: Pythonowy Backend/Gateway dla panelu webowego "Zarządzanie Routerem". ║
║  Zarządza iptables, routingiem i usługami na Android TV poprzez ADB Shell.   ║
║  Przystosowany do współpracy z autorską bramką JS (ADB Web-Bridge).          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path

# --- KONFIGURACJA ---
TARGET_DEVICE = "192.168.1.3:5555"
CONFIG_FILE = Path.home() / ".playbox_network_config.json"

class Style:
    C = '\033[96m'  # Cyan
    G = '\033[92m'  # Green
    Y = '\033[93m'  # Yellow
    R = '\033[91m'  # Red
    W = '\033[1m'   # Bold
    O = '\033[0m'   # Reset

def log(tag: str, msg: str, color: str = Style.C):
    print(f"{Style.W}[{time.strftime('%H:%M:%S')}] {color}[{tag}]{Style.O} {msg}")

# ==============================================================================
# BRAMKA ADB (Execution Engine)
# ==============================================================================
class AdbGateway:
    """Wrapper obsługujący połączenie i wykonanie komend z uprawnieniami root/rish."""
    def __init__(self, target=TARGET_DEVICE):
        self.target = target
        self.use_rish = self._check_rish()

    def _check_rish(self) -> bool:
        cmd = f"adb -s {self.target} shell ls /data/local/tmp/rish"
        res = subprocess.getoutput(cmd)
        return "No such file" not in res

    def run(self, cmd: str, silent: bool = False) -> str:
        """Wykonuje komendę. Używa rish/su w zależności od dostępności."""
        safe_cmd = cmd.replace("'", "'\\''")
        if self.use_rish:
            full_cmd = f"adb -s {self.target} shell sh /data/local/tmp/rish -c '{safe_cmd}'"
        else:
            # Fallback for engineering root
            full_cmd = f"adb -s {self.target} shell su -c '{safe_cmd}'"
            
        try:
            res = subprocess.check_output(full_cmd, shell=True, stderr=subprocess.STDOUT, text=True).strip()
            if not silent: log("ADB", f"EXEC: {cmd[:50]}...", Style.C)
            return res
        except subprocess.CalledProcessError as e:
            if not silent: log("ADB_ERR", f"Kod {e.returncode}: {e.output.strip()}", Style.R)
            return ""

# ==============================================================================
# ZARZĄDZANIE STANEM (State Management)
# ==============================================================================
class NetworkState:
    """Zarządza bazą danych konfiguracji na wzór UCI z OpenWrt."""
    def __init__(self):
        self.db = {
            "ip_rules": [],
            "mac_rules": [],
            "port_rules": [],
            "parental": {"enabled": False, "blocked_domains": []},
            "vpn": {"enabled": False, "type": "wireguard", "config": ""},
            "ddns": {"enabled": False, "provider": "No-IP", "user": "", "pass": "", "host": ""}
        }
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                self.db.update(json.load(f))
    
    def save(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.db, f, indent=4)

# ==============================================================================
# MODUŁY FUNKCJONALNE (Mapowanie na iptables/Android API)
# ==============================================================================
class NetFilterEngine:
    """Tłumaczy obiekty JSON na natywne reguły zapory iptables."""
    
    CHAIN_NAME = "PLAYBOX_FILTER"

    def __init__(self, adb: AdbGateway, state: NetworkState):
        self.adb = adb
        self.state = state

    def init_chain(self):
        """Tworzy dedykowany łańcuch iptables dla reguł panelu (jak w OpenWrt)."""
        log("FIREWALL", "Inicjalizacja łańcucha PLAYBOX_FILTER...", Style.Y)
        self.adb.run("iptables -D INPUT -j PLAYBOX_FILTER", silent=True)
        self.adb.run("iptables -D FORWARD -j PLAYBOX_FILTER", silent=True)
        self.adb.run(f"iptables -F {self.CHAIN_NAME}", silent=True)
        self.adb.run(f"iptables -X {self.CHAIN_NAME}", silent=True)
        
        self.adb.run(f"iptables -N {self.CHAIN_NAME}")
        self.adb.run(f"iptables -A INPUT -j {self.CHAIN_NAME}")
        self.adb.run(f"iptables -A FORWARD -j {self.CHAIN_NAME}")

    def apply_ip_rules(self):
        """Tłumaczy zakładkę 'Filtrowanie IP' na reguły."""
        log("FIREWALL", "Aplikowanie reguł IP/Port...", Style.C)
        for rule in self.state.db["ip_rules"]:
            cmd = f"iptables -A {self.CHAIN_NAME}"
            
            # Kierunek
            if rule.get("direction") == "in": pass
            
            # Protokoły
            proto = rule.get("protocol", "tcpudp")
            if proto == "tcpudp":
                cmd_tcp = cmd + " -p tcp"
                cmd_udp = cmd + " -p udp"
            else:
                cmd_tcp = f"{cmd} -p {proto}"
                cmd_udp = None

            def add_params(base_cmd):
                c = base_cmd
                if rule.get("srcIp"): c += f" -s {rule['srcIp']}"
                if rule.get("dstIp"): c += f" -d {rule['dstIp']}"
                if rule.get("srcPort") and "-p" in c: c += f" --sport {rule['srcPort'].replace('-', ':')}"
                if rule.get("dstPort") and "-p" in c: c += f" --dport {rule['dstPort'].replace('-', ':')}"
                c += " -j DROP" # Domyślna akcja panelu to blokowanie
                return c

            self.adb.run(add_params(cmd_tcp))
            if cmd_udp: self.adb.run(add_params(cmd_udp))

    def apply_parental_control(self):
        """Zakładka 'Kontrola rodzicielska' (Modyfikacja /etc/hosts lub iptables string match)."""
        parental = self.state.db["parental"]
        if not parental.get("enabled"): return
        
        log("PARENTAL", "Aktywacja blokad domenowych...", Style.Y)
        for domain in parental.get("blocked_domains", []):
            # Użycie modułu string match (wymaga wsparcia w kernelu) 
            # lub DNS poisoning poprzez /etc/hosts w Androidzie.
            # Tu wariant iptables hex-string dla ruchu portu 53:
            hex_domain = domain.encode('utf-8').hex()
            self.adb.run(f"iptables -A {self.CHAIN_NAME} -p udp --dport 53 -m string --hex-string '|{hex_domain}|' --algo bm -j DROP")

class DDNSManager:
    """Implementuje zakładkę DDNS."""
    def __init__(self, adb: AdbGateway, state: NetworkState):
        self.adb = adb
        self.state = state

    def update(self):
        ddns = self.state.db["ddns"]
        if not ddns.get("enabled"):
            log("DDNS", "Usługa wyłączona w konfiguracji.", Style.Y)
            return

        user = ddns["user"]
        pwd = ddns["pass"]
        host = ddns["host"]
        
        log("DDNS", f"Aktualizacja IP dla hosta: {host}", Style.G)
        # Użycie wbudowanego wget lub curl w Androidzie
        url = f"https://{user}:{pwd}@dynupdate.no-ip.com/nic/update?hostname={host}"
        res = self.adb.run(f"wget -qO- \"{url}\"")
        log("DDNS", f"Odpowiedź serwera: {res}", Style.C)


# ==============================================================================
# ORKIESTRATOR (Główna klasa zarządzająca)
# ==============================================================================
class WebPanelController:
    """Interfejs łączący panel Web (dane w State) z urządzeniem (AdbGateway)."""
    def __init__(self):
        self.adb = AdbGateway()
        self.state = NetworkState()
        self.firewall = NetFilterEngine(self.adb, self.state)
        self.ddns = DDNSManager(self.adb, self.state)

    def synchronize_device(self):
        """Wysyła całą konfigurację na urządzenie - odpowiednik 'Zastosuj' z OpenWrt."""
        print(f"\n{Style.W}{Style.C}=== INICJALIZACJA PLAYBOX NETWORK ENGINE ==={Style.O}")
        self.firewall.init_chain()
        self.firewall.apply_ip_rules()
        self.firewall.apply_parental_control()
        self.ddns.update()
        print(f"{Style.W}{Style.G}=== SYNCHRONIZACJA ZAKOŃCZONA SUKCESEM ==={Style.O}\n")

    def add_ip_rule(self, name, direction, src_ip, src_port, dst_ip, dst_port, proto):
        """Metoda dla bramki JS (API endpoint)."""
        rule = {
            "id": int(time.time()),
            "name": name, "direction": direction,
            "srcIp": src_ip, "srcPort": src_port,
            "dstIp": dst_ip, "dstPort": dst_port,
            "protocol": proto
        }
        self.state.db["ip_rules"].append(rule)
        self.state.save()
        log("API", f"Dodano regułę IP: {name}", Style.G)

    def interactive_cli(self):
        """Proste TUI do testowania logiki backendu (symulacja panelu WEB)."""
        while True:
            print(f"{Style.W}--- PANEL ZARZĄDZANIA ROUTEREM (BACKEND CLI) ---{Style.O}")
            print("1. Synchronizuj konfigurację (Apply)")
            print("2. Pokaż obecne reguły IP")
            print("3. Dodaj nową regułę IP (Test: xmmpoutge)")
            print("4. Wymuś aktualizację DDNS")
            print("0. Wyjście")
            
            choice = input(f"Wybierz opcję > ")
            
            if choice == '1':
                self.synchronize_device()
            elif choice == '2':
                print(json.dumps(self.state.db["ip_rules"], indent=2))
            elif choice == '3':
                self.add_ip_rule("xmmpoutge", "in", "193.47.158.22", "5269", "", "", "tcpudp")
                self.synchronize_device()
            elif choice == '4':
                self.ddns.update()
            elif choice == '0':
                break
            else:
                print("Zły wybór.")

if __name__ == "__main__":
    controller = WebPanelController()
    
    # Tryb działania: jeśli argument CLI, działaj jako API. W przeciwnym razie odpal TUI.
    if len(sys.argv) > 1 and sys.argv[1] == "--sync":
        controller.synchronize_device()
    else:
        # Odczytaj testowe zasoby ze zrzutów web panelu, jeśli baza jest pusta
        if not controller.state.db["ip_rules"]:
            log("SYS", "Brak reguł. Ładowanie danych inicjalnych (Demo Panelu)...", Style.Y)
            controller.add_ip_rule("53443out", "out", "10.14.0.1", "", "192.168.1.1", "21-22", "tcpudp")
            controller.add_ip_rule("BlockTelnetLan", "in", "10.14.0.1", "", "192.168.1.1", "23", "tcpudp")
            
        controller.interactive_cli()
eof