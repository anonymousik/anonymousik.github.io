/**
 * SECFERRO DIVISION :: TACTICAL INTERFACE
 * Terminal Typing Engine v3.1 (Hardened Version)
 */

document.addEventListener('DOMContentLoaded', () => {
    const terminalOutput = document.getElementById('terminal-output');
    
    const COMMAND_LOGS = [
        { text: 'SECFERRO DIVISION :: TACTICAL INTERFACE v3.1', speed: 30 },
        { text: 'AUTHENTICATION SUCCESSFUL. WELCOME, OPERATOR.', speed: 30, delay: 500 },
        { text: '--------------------------------------------------', speed: 10 },
        { text: 'ENCRYPTION KEY: <span class="status-ok">AES-256-GCM ACTIVE</span>', speed: 30, delay: 200 },
        { text: 'SYSTEM STATUS: <span class="status-ok">ALL SYSTEMS NOMINAL</span>', speed: 30, delay: 200 },
        { text: 'THREAT LEVEL: <span class="status-warn">ELEVATED</span>', speed: 30, delay: 200 },
        { text: 'INTEGRITY CHECK: <span class="status-ok">PASSED</span>', speed: 30, delay: 100 },
        { text: 'AWAITING COMMAND...', speed: 50, delay: 500 }
    ];

    let lineIndex = 0;

    /**
     * Bezpieczne pisanie linii z obsługą tagów HTML.
     * Metoda ta pozwala uniknąć renderowania surowych tagów <span...
     */
    async function typeEffect(element, cfg) {
        const fullText = cfg.text;
        let currentText = "";
        let isTag = false;
        let tagBuffer = "";

        for (let i = 0; i < fullText.length; i++) {
            const char = fullText[i];

            // Wykrywanie początku i końca tagu HTML (np. <span>)
            if (char === '<') isTag = true;
            
            if (isTag) {
                tagBuffer += char;
                if (char === '>') {
                    isTag = false;
                    currentText += tagBuffer;
                    tagBuffer = "";
                }
                // Tag dodajemy natychmiastowo, by nie "migał" jako tekst
                continue; 
            }

            currentText += char;
            element.innerHTML = currentText; // Bezpieczne przy hardkodowanych danych w CSP 'self'
            
            await new Promise(res => setTimeout(res, cfg.speed));
        }
    }

    async function runTerminal() {
        for (const log of COMMAND_LOGS) {
            const p = document.createElement('p');
            terminalOutput.appendChild(p);
            
            await typeEffect(p, log);
            
            if (log.delay) {
                await new Promise(res => setTimeout(res, log.delay));
            }
        }
    }

    // Inicjalizacja systemu
    runTerminal().catch(err => {
        console.error("Critical Terminal Error:", err);
    });
});
