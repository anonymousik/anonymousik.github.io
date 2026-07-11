(function () {                                                                   
  "use strict";
  const cfg = window.__WEBTERM_CONFIG__;                                         
  const term = new Terminal({ cursorBlink: true, theme: { background: "#0d1117" }
 });
  term.open(document.getElementById("terminal"));                                
  term.writeln("Connecting to " + cfg.wsUrl + " ...");

  const socket = new WebSocket(cfg.wsUrl + "/ssh");

  socket.addEventListener("open", () => term.writeln("[connected]"));
  socket.addEventListener("close", () => term.writeln("\r\n[disconnected]"));
  socket.addEventListener("error", () => term.writeln("\r\n[connection error]"));
  socket.addEventListener("message", (evt) => term.write(evt.data));

  term.onData((data) => {
    if (socket.readyState === WebSocket.OPEN) socket.send(data);                 
  });
})();
