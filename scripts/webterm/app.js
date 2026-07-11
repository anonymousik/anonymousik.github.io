"use strict";

/**
 * WebTerm Frontend Application
 * Restyled to match the SecFerro Division visual language (ferro-theme.css)
 * used across anonymousik.is-a.dev, instead of a generic GitHub-dark theme.
 */

(function () {
  const cfg = window.__WEBTERM_CONFIG__;
  if (!cfg || !cfg.wsUrl) {
    document.body.innerHTML = '<h2 style="color:#ff5f57;text-align:center;font-family:monospace;">Błąd Krytyczny: Brak konfiguracji środowiskowej (config.js)</h2>';
    console.error("FATAL: window.__WEBTERM_CONFIG__ is missing or invalid.");
    return;
  }

  if (typeof Terminal === "undefined" || typeof FitAddon === "undefined") {
    document.body.innerHTML = '<h2 style="color:#ff5f57;text-align:center;font-family:monospace;">Błąd Krytyczny: Biblioteki xterm.js nie zostały poprawnie załadowane z CDN.</h2>';
    console.error("FATAL: xterm.js libraries failed to load from CDN.");
    return;
  }

  const term = new Terminal({
    cursorBlink: true,
    fontFamily: "'JetBrains Mono', 'Fira Code', ui-monospace, Consolas, monospace",
    fontSize: 14,
    theme: {
      background: "#0b0f0e",
      foreground: "#c9d1d9",
      cursor: "#33d17a",
      cursorAccent: "#0b0f0e",
      green: "#33d17a",
      brightGreen: "#33d17a",
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

  // Boot sequence mirrors the identity block shown on the homepage's own
  // terminal panel, for the same "$ whoami" / "$ cat /etc/identity" feel.
  const BOOT_LINES = [
    "\x1b[1;32m[ WebTerm · SecFerro Division ]\x1b[0m",
    "Backend: " + cfg.wsUrl,
    "",
    "$ whoami",
    "anonymousik :: hybrid_engineer",
    "$ cat /etc/identity",
    "hybrid_engineer :: cyber_security | audio_visual | systems_design",
    "status :: operational | projects :: 4_active | division :: SECFERRO",
    "",
    "Oczekiwanie na poświadczenia SSH...",
    "",
  ];
  BOOT_LINES.forEach((line) => term.writeln(line));

  // 3. Login overlay — DOM built programmatically (no innerHTML from user
  // input), styled via ferro-theme.css classes instead of inline JS styles.
  function createLoginOverlay(onSubmit) {
    const overlay = document.createElement("div");
    overlay.className = "ferro-login-overlay";

    const form = document.createElement("form");
    form.className = "ferro-login-form";

    const title = document.createElement("h3");
    title.textContent = "Połączenie SSH";
    form.appendChild(title);

    const errorBox = document.createElement("div");
    errorBox.className = "ferro-login-error";
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
      inputs[f.id] = input;
      form.appendChild(input);
    });

    const btn = document.createElement("button");
    btn.type = "submit";
    btn.textContent = "Połącz";
    form.appendChild(btn);

    function showError(msg) {
      errorBox.textContent = msg;
      errorBox.style.display = "block";
    }

    let submitted = false;
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
      inputs.password.value = "";
    };

    overlay.appendChild(form);
    document.body.appendChild(overlay);
    inputs.host.focus();
  }

  // 4. WebSocket bridge
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
    term.onData(() => {
      term.onData(() => {}); // detach one-shot listener
      connectSSH(prevCreds);
    });
  }

  createLoginOverlay(connectSSH);
})();
