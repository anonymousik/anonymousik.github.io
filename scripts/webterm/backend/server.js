"use strict";
const http = require("http");
const { WebSocketServer } = require("ws");
const { Client } = require("ssh2");

const PORT = process.env.PORT || 8080;
const ALLOWED_ORIGIN = process.env.ALLOWED_ORIGIN || "";

if (!ALLOWED_ORIGIN) {
  console.error("FATAL: ALLOWED_ORIGIN env var is not set. Refusing to start.");
  process.exit(1);
}

const server = http.createServer((req, res) => {
  if (req.url === "/healthz") {
    res.writeHead(200, { "Content-Type": "text/plain" });
    res.end("ok");
    return;
  }
  res.writeHead(404);
  res.end();
});

const wss = new WebSocketServer({ noServer: true });

server.on("upgrade", (req, socket, head) => {
  const origin = req.headers.origin || "";
server.on("upgrade", (req, socket, head) => {
  const origin = req.headers.origin || "";
  
  console.log("DEBUG: Incoming Origin Header:", origin);
  console.log("DEBUG: Allowed Origins List:", ALLOWED_ORIGINS);
  // -----------------
  
  if (!ALLOWED_ORIGINS.includes(origin)) {
    // ... reszta kodu
    
  if (origin !== ALLOWED_ORIGIN) {
    socket.write("HTTP/1.1 403 Forbidden\r\n\r\n");
    socket.destroy();
    return;
  }
  wss.handleUpgrade(req, socket, head, (ws) => {
    wss.emit("connection", ws, req);
  });
});

wss.on("connection", (ws) => {
  const conn = new Client();
  let shellStream = null;

  ws.on("message", (data) => {
    if (shellStream) {
      shellStream.write(data);
      return;
    }
    let creds;
    try {
      creds = JSON.parse(data.toString());
    } catch {
      ws.close(1002, "invalid auth payload");
      return;
    }
    conn
      .on("ready", () => {
        conn.shell((err, stream) => {
          if (err) {
            ws.close(1011, "shell error");
            return;
          }
          shellStream = stream;
          stream.on("data", (chunk) => ws.readyState === ws.OPEN && ws.send(chunk));
          stream.on("close", () => conn.end());
        });
      })
      .on("error", () => ws.close(1011, "ssh connection error"))
      .connect({
        host: creds.host,
        port: creds.port || 22,
        username: creds.username,
        password: creds.password,
        readyTimeout: 15000,
      });
  });

  ws.on("close", () => {
    if (shellStream) shellStream.end();
    conn.end();
  });
});

server.listen(PORT, () => console.log("webterm-backend listening on " + PORT));
