"use strict";
/**
 * WebTerm Backend — WebSocket-to-SSH bridge.
 *
 * SECURITY MODEL (read before deploying):
 * - This endpoint accepts an unauthenticated WebSocket upgrade, then expects
 *   {host, port, username, password} as the first message and attempts an
 *   SSH connection to whatever host/port the client supplies.
 * - Anyone who can reach this WS endpoint can make the backend originate
 *   outbound TCP connections to arbitrary host:port (SSRF / port-scan
 *   surface), even without valid SSH credentials — the TCP connect + SSH
 *   banner exchange happens before auth is checked. Origin-checking (below)
 *   only restricts which *web pages* can open the socket in a browser; it
 *   does NOT stop a direct client (curl/websocat/script) with no Origin
 *   header from a machine that isn't a browser, since such a client can
 *   simply omit or forge the Origin header. If the target device is only
 *   reachable via a private tunnel (Cloudflare Tunnel / reverse SSH), the
 *   blast radius is limited to that reachable network. Do not expose this
 *   service to reach production infrastructure without adding real
 *   authentication (e.g. a server-side session/JWT check before allowing
 *   the "connect" message) or a network-level access layer (Cloudflare
 *   Access, IP allowlist) in front of it.
 */
const http = require("http");
const { WebSocketServer } = require("ws");
const { Client } = require("ssh2");

const PORT = process.env.PORT || 8080;
const RAW_ALLOWED_ORIGIN = process.env.ALLOWED_ORIGIN || "";
const DEBUG = process.env.DEBUG === "true";
const SSH_CONNECT_TIMEOUT_MS = Number(process.env.SSH_CONNECT_TIMEOUT_MS) || 15000;
const MAX_CONCURRENT_SESSIONS = Number(process.env.MAX_CONCURRENT_SESSIONS) || 50;

// --- Fail-fast config validation -----------------------------------------
if (!RAW_ALLOWED_ORIGIN) {
  console.error("FATAL: ALLOWED_ORIGIN env var is not set. Refusing to start.");
  process.exit(1);
}

let ALLOWED_ORIGIN;
try {
  // new URL(...).origin normalizes away any accidental path/trailing slash,
  // e.g. "https://host/some/path" -> "https://host". Prevents the exact
  // mismatch class that caused the earlier 1006 (Abnormal Closure) bug.
  ALLOWED_ORIGIN = new URL(RAW_ALLOWED_ORIGIN).origin;
} catch {
  console.error(`FATAL: ALLOWED_ORIGIN "${RAW_ALLOWED_ORIGIN}" is not a valid URL.`);
  process.exit(1);
}

function log(...args) {
  if (DEBUG) console.log("[DEBUG]", ...args);
}

// --- HTTP surface: health check only -------------------------------------
const server = http.createServer((req, res) => {
  if (req.url === "/healthz") {
    res.writeHead(200, { "Content-Type": "text/plain" });
    res.end("ok");
    return;
  }
  res.writeHead(404, { "Content-Type": "text/plain" });
  res.end("not found");
});

const wss = new WebSocketServer({ noServer: true });

let activeSessions = 0;

server.on("upgrade", (req, socket, head) => {
  const origin = req.headers.origin || "";
  log("incoming Origin:", origin, "| expected:", ALLOWED_ORIGIN);

  if (origin !== ALLOWED_ORIGIN) {
    socket.write("HTTP/1.1 403 Forbidden\r\n\r\n");
    socket.destroy();
    return;
  }

  if (activeSessions >= MAX_CONCURRENT_SESSIONS) {
    socket.write("HTTP/1.1 503 Service Unavailable\r\n\r\n");
    socket.destroy();
    return;
  }

  wss.handleUpgrade(req, socket, head, (ws) => {
    wss.emit("connection", ws, req);
  });
});

// --- Basic shape validation for the first (auth) message ------------------
function validateCreds(raw) {
  let creds;
  try {
    creds = JSON.parse(raw.toString());
  } catch {
    return { error: "invalid_json" };
  }

  const { host, port, username, password } = creds || {};

  if (typeof host !== "string" || host.trim().length === 0 || host.length > 255) {
    return { error: "invalid_host" };
  }
  if (typeof username !== "string" || username.trim().length === 0 || username.length > 255) {
    return { error: "invalid_username" };
  }
  if (typeof password !== "string" || password.length === 0) {
    return { error: "invalid_password" };
  }
  const parsedPort = Number.isInteger(port) ? port : parseInt(port, 10);
  if (!Number.isInteger(parsedPort) || parsedPort < 1 || parsedPort > 65535) {
    return { error: "invalid_port" };
  }

  return {
    creds: {
      host: host.trim(),
      port: parsedPort,
      username: username.trim(),
      password,
    },
  };
}

wss.on("connection", (ws, req) => {
  activeSessions += 1;
  log("session opened, active:", activeSessions, "from:", req.socket.remoteAddress);

  const conn = new Client();
  let shellStream = null;
  let authenticated = false;
  let closed = false;

  function cleanup() {
    if (closed) return;
    closed = true;
    activeSessions = Math.max(0, activeSessions - 1);
    if (shellStream) {
      try { shellStream.end(); } catch { /* already closed */ }
    }
    try { conn.end(); } catch { /* already closed */ }
  }

  ws.on("message", (data) => {
    if (authenticated) {
      if (shellStream) shellStream.write(data);
      return;
    }

    authenticated = true; // first message consumed as auth regardless of outcome
    const result = validateCreds(data);
    if (result.error) {
      ws.close(1002, result.error);
      cleanup();
      return;
    }

    const { creds } = result;

    conn
      .on("ready", () => {
        conn.shell((err, stream) => {
          if (err) {
            log("shell error:", err.message);
            ws.close(1011, "shell_error");
            cleanup();
            return;
          }
          shellStream = stream;
          stream.on("data", (chunk) => {
            if (ws.readyState === ws.OPEN) ws.send(chunk);
          });
          stream.on("close", () => {
            ws.close(1000, "shell_closed");
            cleanup();
          });
        });
      })
      .on("error", (err) => {
        log("ssh connection error:", err.message);
        ws.close(1011, "ssh_connection_error");
        cleanup();
      })
      .connect({
        host: creds.host,
        port: creds.port,
        username: creds.username,
        password: creds.password,
        readyTimeout: SSH_CONNECT_TIMEOUT_MS,
      });
  });

  ws.on("close", cleanup);
  ws.on("error", (err) => {
    log("ws error:", err.message);
    cleanup();
  });
});

// --- Defensive process-level guards ---------------------------------------
process.on("uncaughtException", (err) => {
  console.error("FATAL: uncaughtException:", err);
  process.exit(1);
});
process.on("unhandledRejection", (reason) => {
  console.error("FATAL: unhandledRejection:", reason);
  process.exit(1);
});

server.listen(PORT, () => {
  console.log(`webterm-backend listening on ${PORT} | ALLOWED_ORIGIN=${ALLOWED_ORIGIN}`);
});
