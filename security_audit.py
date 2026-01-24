import requests
import sys
from datetime import datetime

########################################
## SECFERRO WWW SECURITY AUDIT ########
########################################
## TEN SKRYPT:
## ✓ SPRAWDZA DOMENĘ⤵️:
## (Anonymousik.is-a.dev) 
## ✓ OBECNOŚĆ NAGŁÓWKÓW⤵️:
## (HSTS, CSP, Permissions-Policy)
## NASTĘPNIE GENERUJĘ PLIK (index.html)
## ZGODNIE Z ZASADAMI BEZPIECZEŃSTWA 2026
#######################################
# KONFIGURACJA AUDYTU

########################################
## SECFERRO WWW SECURITY AUDIT ########
########################################
## TEN SKRYPT:
## ✓ SPRAWDZA DOMENĘ⤵️:
## (Anonymousik.is-a.dev) 
## ✓ OBECNOŚĆ NAGŁÓWKÓW⤵️:
## (HSTS, CSP, Permissions-Policy)
## NASTĘPNIE GENERUJĘ PLIK (index.html)
## ZGODNIE Z ZASADAMI BEZPIECZEŃSTWA 2026
#######################################
TARGET_URL = "https://anonymousik.is-a.dev"
# Lista nagłówków
REQUIRED_HEADERS = {
    "Strict-Transport-Security": "Wymusza HTTPS (HSTS)",
    "X-Content-Type-Options": "Chroni przed MIME-sniffing",
    "X-Frame-Options": "Blokuje Clickjacking",
    "Referrer-Policy": "Chroni prywatność danych o źródle",
    "Permissions-Policy": "Blokuje kamerę/mikrofon/geo",
    "Content-Security-Policy": "Ochrona przed XSS/Injections"
}

def scan_headers():
    try:
        user_agent = {'User-Agent': 'SecOps-Monitor/1.0'}
        response = requests.get(TARGET_URL, headers=user_agent, timeout=10)
        headers = response.headers
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="pl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Raport Bezpieczeństwa SECFERRO DIVISION: {TARGET_URL}</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1a1a1a; color: #e0e0e0; padding: 20px; }}
                .container {{ max-width: 800px; margin: 0 auto; background: #2d2d2d; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
                h1 {{ color: #4db8ff; border-bottom: 1px solid #444; padding-bottom: 10px; }}
                .status {{ font-weight: bold; padding: 5px 10px; border-radius: 4px; }}
                .pass {{ background: #28a745; color: white; }}
                .fail {{ background: #dc3545; color: white; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ text-align: left; padding: 12px; border-bottom: 1px solid #444; }}
                th {{ color: #bbb; }}
                .timestamp {{ text-align: right; color: #777; font-size: 0.8em; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🛡️ Audyt Nagłówków Bezpieczeństwa</h1>
                <p>Cel: <strong>{TARGET_URL}</strong></p>
                <table>
                    <thead>
                        <tr>
                            <th>Nagłówek</th>
                            <th>Opis</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
        """

        all_passed = True
        
        for header, description in REQUIRED_HEADERS.items():
            if header in headers:
                status_class = "pass"
                status_text = "OK"
            else:
                status_class = "fail"
                status_text = "BRAK"
                all_passed = False
            
            html_content += f"""
                        <tr>
                            <td>{header}</td>
                            <td>{description}</td>
                            <td><span class="status {status_class}">{status_text}</span></td>
                        </tr>
            """

        html_content += f"""
                    </tbody>
                </table>
                <div class="timestamp">
                    Ostatnia aktualizacja: {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")} <br>
                    Status serwera: {response.status_code}
                </div>
            </div>
        </body>
        </html>
        """
        
        # Zapis wyniku do index.html
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print("Audyt zakończony. Wygenerowano raport.")

    except Exception as e:
        print(f"Błąd krytyczny skanera: {e}")
        sys.exit(1)

if __name__ == "__main__":
    scan_headers()
