"use strict";

/**
 * WebTerm Frontend Application
 * Funkcje: Dynamiczna autoryzacja, RWD (FitAddon), bezpieczna komunikacja WSS
 */

(function () {
  // 1. Walidacja środowiska i konfiguracji (Fail-Fast)
  const cfg = window.__WEBTERM_CONFIG__;
  if (!cfg || !cfg.wsUrl) {
    document.body.innerHTML = '<h2 style="color:red;text-align:center;font-family:sans-serif;">Błąd Krytyczny: Brak konfiguracji środowiskowej (config.js)</h2>';
    console.error("FATAL: window.__WEBTERM_CONFIG__ is missing or invalid.");
    return;
  }

  if (typeof Terminal === "undefined" || typeof FitAddon === "undefined") {
    document.body.innerHTML = '<h2 style="color:red;text-align:center;font-family:sans-serif;">Błąd Krytyczny: Biblioteki xterm.js nie zostały poprawnie załadowane z CDN.</h2>';
    console.error("FATAL: xterm.js libraries failed to load from CDN.");
    return;
  }

  // 2. Inicjalizacja instancji Xterm.js
  const term = new Terminal({
    cursorBlink: true,
    fontFamily: 'Consolas, "Courier New", monospace',
    fontSize: 15,
    theme: {
      background: "#0d1117",
      foreground: "#c9d1d9",
      cursor: "#58a6ff",
    },
  });

  const fitAddon = new FitAddon.FitAddon();
  term.loadAddon(fitAddon);

  const terminalContainer = document.getElementById("terminal");
  term.open(terminalContainer);
  fitAddon.fit();

  window.addEventListener("resize", () => {
    requestAnimationFrame(() => fitAddon.fit());
  });

  term.writeln("\x1b[1;36m[ WebTerm Frontend v1.2.0 ]\x1b[0m");
  term.writeln("Backend: " + cfg.wsUrl);
  term.writeln("Oczekiwanie na poświadczenia SSH...\r\n");

  // 3. Budowa interfejsu logowania (bezpieczny DOM, brak innerHTML z danych użytkownika)
  function createLoginOverlay(onSubmit) {
    const overlay = document.createElement("div");
    Object.assign(overlay.style, {
      position: "absolute", top: "0", left: "0", width: "100%", height: "100%",
      backgroundColor: "rgba(13, 17, 23, 0.85)", display: "flex",
      justifyContent: "center", alignItems: "center", zIndex: "1000",
      fontFamily: "sans-serif",
    });

    const form = document.createElement("form");
    Object.assign(form.style, {
      background: "#161b22", padding: "2rem", borderRadius: "8px",
      border: "1px solid #30363d", display: "flex", flexDirection: "column",
      gap: "1rem", width: "300px", boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
    });

    const title = document.createElement("h3");
    title.textContent = "Połączenie SSH";
    title.style.color = "#c9d1d9";
    title.style.margin = "0 0 10px 0";
    form.appendChild(title);

    const errorBox = document.createElement("div");
    Object.assign(errorBox.style, {
      color: "#f85149", fontSize: "0.85rem", minHeight: "1em", display: "none",
    });
    form.appendChild(errorBox);

    const inputs = {};
    const fields = [
      { id: "host", type: "text", placeholder: "Host (np. 192.168.1.10)", required: true },
      { id: "port", type: "number", placeholder: "Port (domyślnie 22)", value: "22" },
      { id: "username", type: "text", placeholder: "Użytkownik", required: true },
      { id: "password", type: "password", placeholder: "Hasło", required: true },
    ];

    fields.forEach((f) => {
      const input = document.createElement("input");
      input.type = f.type;
      input.placeholder = f.placeholder;
      if (f.value) input.value = f.value;
      if (f.required) input.required = true;
      if (f.id === "port") { input.min = "1"; input.max = "65535"; }
      Object.assign(input.style, {
        padding: "10px", borderRadius: "4px", border: "1px solid #30363d",
        background: "#0d1117", color: "#c9d1d9", outline: "none",
      });
      input.addEventListener("focus", () => { input.style.borderColor = "#58a6ff"; });
      input.addEventListener("blur", () => { input.style.borderColor = "#30363d"; });
      inputs[f.id] = input;
      form.appendChild(input);
    });

    const btn = document.createElement("button");
    btn.type = "submit";
    btn.textContent = "Połącz";
    Object.assign(btn.style, {
      padding: "10px", borderRadius: "4px", border: "none",
      background: "#238636", color: "#ffffff", fontWeight: "bold",
      cursor: "pointer", marginTop: "10px",
    });
    btn.addEventListener("mouseover", () => { btn.style.background = "#2ea043"; });
    btn.addEventListener("mouseout", () => { btn.style.background = "#238636"; });
    form.appendChild(btn);

    function showError(msg) {
      errorBox.textContent = msg;
      errorBox.style.display = "block";
    }

    let submitted = false; // guards against double-submit while awaiting connect
    form.onsubmit = (e) => {
      e.preventDefault();
      if (submitted) return;

      const host = inputs.host.value.trim();
      const username = inputs.username.value.trim();
      const password = inputs.password.value;
      const port = parseInt(inputs.port.value, 10) || 22;

      if (!host || !username || !password) {
        showError("Wszystkie pola (poza portem) są wymagane.");
        return;
      }
      if (port < 1 || port > 65535) {
        showError("Port musi być w zakresie 1-65535.");
        return;
      }

      submitted = true;
      btn.disabled = true;
      btn.textContent = "Łączenie...";

      const creds = { host, port, username, password };
      document.body.removeChild(overlay);
      onSubmit(creds);
      // Best-effort clear of the in-memory reference; the string itself
      // may still live in engine memory until GC, but this removes the
      // most obvious lingering reference.
      inputs.password.value = "";
    };

    overlay.appendChild(form);
    document.body.appendChild(overlay);
    inputs.host.focus();
  }

  // 4. Logika mostu WebSocket (WSS)
  function connectSSH(creds) {
    term.clear();
    term.writeln(`\x1b[33m[SYS]\x1b[0m Łączenie z ${cfg.wsUrl} jako ${creds.username}@${creds.host}:${creds.port}...`);

    let socket;
    try {
      socket = new WebSocket(cfg.wsUrl);
    } catch (err) {
      term.writeln(`\r\n\x1b[1;31m[BŁĄD]\x1b[0m Nie udało się utworzyć gniazda WS: ${err.message}`);
      offerReconnect(creds);
      return;
    }

    let isSessionEstablished = false;

    socket.addEventListener("open", () => {
      term.writeln(`\x1b[32m[Połączono z mostem WS]\x1b[0m Wysyłanie poświadczeń SSH...`);
      socket.send(JSON.stringify(creds));
    });

    socket.addEventListener("message", (evt) => {
      if (!isSessionEstablished) {
        term.clear();
        isSessionEstablished = true;
      }
      term.write(evt.data);
    });

    socket.addEventListener("close", (evt) => {
      term.writeln(`\r\n\x1b[1;31m[Rozłączono]\x1b[0m Kod: ${evt.code}, Powód: ${evt.reason || "brak powiadomienia"}`);
      isSessionEstablished = false;
      offerReconnect(creds);
    });

    socket.addEventListener("error", () => {
      term.writeln("\r\n\x1b[1;31m[Błąd sieci]\x1b[0m Połączenie z backendem zostało zerwane.");
    });

    term.onData((data) => {
      if (socket.readyState === WebSocket.OPEN && isSessionEstablished) {
        socket.send(data);
      }
    });
  }

  function offerReconnect(prevCreds) {
    term.writeln("\r\n\x1b[33m[SYS]\x1b[0m Naciśnij dowolny klawisz, aby spróbować ponownie, lub odśwież stronę, by zmienić dane logowania.");
    const handler = (data) => {
      term.onData(() => {}); // detach this one-shot listener
      connectSSH(prevCreds);
    };
    term.onData(handler);
  }

  createLoginOverlay(connectSSH);
})();
