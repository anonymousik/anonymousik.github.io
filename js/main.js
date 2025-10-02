
document.addEventListener('DOMContentLoaded', function() {
    const terminalOutput = document.getElementById('terminal-output');
    const lines = [
        { text: 'SECFERRO DIVISION :: TACTICAL INTERFACE v3.0', speed: 50 },
        { text: 'AUTHENTICATION SUCCESSFUL. WELCOME, OPERATOR.', speed: 50, delay: 500 },
        { text: '--------------------------------------------------', speed: 20 },
        { text: 'SYSTEM STATUS: <span class="status-ok">ALL SYSTEMS NOMINAL</span>', speed: 50, delay: 200 },
        { text: 'THREAT LEVEL: <span class="status-warn">ELEVATED</span>', speed: 50, delay: 200 },
        { text: 'AWAITING COMMAND...', speed: 50, delay: 500 }
    ];

    let lineIndex = 0;

    function typeLine() {
        if (lineIndex < lines.length) {
            const line = lines[lineIndex];
            const p = document.createElement('p');
            terminalOutput.appendChild(p);

            let charIndex = 0;
            const typingInterval = setInterval(() => {
                if (charIndex < line.text.length) {
                    p.innerHTML += line.text.charAt(charIndex);
                    charIndex++;
                } else {
                    clearInterval(typingInterval);
                    if (line.delay) {
                        setTimeout(typeLine, line.delay);
                    } else {
                        typeLine();
                    }
                }
            }, line.speed);
            lineIndex++;
        }
    }

    typeLine();
});
