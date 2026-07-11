"use strict";

/**
 * Konfiguracja środowiska WebTerm (Frontend)
 * Autor modyfikacji: Ekspert ds. SecOps / DevOps
 */

// Object.freeze() to krytyczna praktyka SecOps.
// Zapobiega modyfikacji adresów URL przez złośliwe skrypty (np. wstrzyknięte przez XSS),
// które mogłyby przekierować poświadczenia SSH na serwer atakującego.
window.__WEBTERM_CONFIG__ = Object.freeze({
  // Bazowy adres HTTP (usunięto końcowy ukośnik '/' dla spójności ścieżek)
  backendUrl: "https://anonymousik-github-io-8mj1.onrender.com",
  
  // KRYTYCZNA POPRAWKA: Uzupełniono brakujący rdzeń "-8mj1".
  // Protokół to wss:// (WebSocket Secure) - szyfrowany TLS/SSL.
  wsUrl: "wss://anonymousik-github-io-8mj1.onrender.com"
});
