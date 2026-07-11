"use strict";

/**
 * Konfiguracja środowiska WebTerm (Frontend)
 *
 * Object.freeze() zapobiega nadpisaniu tych wartości przez wstrzyknięty
 * skrypt (XSS) próbujący przekierować ruch WS na serwer atakującego.
 * To druga warstwa obrony — pierwszą jest Content-Security-Policy
 * w index.html (connect-src ogranicza dozwolone hosty na poziomie
 * przeglądarki, więc nawet nadpisanie tych pól i tak nie pozwoli
 * połączyć się z innym originem).
 */
window.__WEBTERM_CONFIG__ = Object.freeze({
  backendUrl: "https://anonymousik-github-io-8mj1.onrender.com",
  wsUrl: "wss://anonymousik-github-io-8mj1.onrender.com",
});
