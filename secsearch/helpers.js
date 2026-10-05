        // --- SECURITY HELPERS (CWE-20/79/95/601/918) ---
        const LIMITS = Object.freeze({ query: 256, field: 2000, items: 50, body: 1000000 });
        const SEARCH_TYPES = new Set(['web', 'news', 'images', 'videos', 'social', 'shopping']);
        const SAFE_COLORS = new Set(['neoncyan', 'neonpurple', 'searxgreen', 'accentamber', 'slate-300']);
        const SAFE_FETCH = Object.freeze({ credentials: 'omit', referrerPolicy: 'no-referrer', cache: 'no-store' });
        let searchSeq = 0;

        function readStore(key) {
            try { return localStorage.getItem(key) || ''; } catch (_) { return ''; }
        }
        function writeStore(key, value) {
            try { localStorage.setItem(key, value); } catch (_) { /* storage unavailable */ }
        }
        function clip(v, n = LIMITS.field) { return typeof v === 'string' ? v.slice(0, n) : ''; }
        function safeColor(c) { return SAFE_COLORS.has(c) ? c : 'neoncyan'; }

        function safeUrl(raw, httpsOnly = false) {
            try {
                const u = new URL(String(raw));
                if (u.protocol === 'https:' || (!httpsOnly && u.protocol === 'http:')) return u.href;
            } catch (_) { /* invalid or relative URL */ }
            return null;
        }

        function normalizeItem(raw, sourceName, color) {
            if (!raw || typeof raw !== 'object') return null;
            const url = safeUrl(raw.url);
            if (!url) return null;
            return {
                title: clip(raw.title) || extractDomain(url),
                url,
                desc: clip(raw.desc),
                favicon: safeUrl(raw.favicon, true),
                sourceName,
                color: safeColor(color)
            };
        }

        function normalizeQuery(raw) {
            return String(raw ?? '')
                .replace(/[\u0000-\u001F\u007F-\u009F]/g, ' ')
                .replace(/\s+/g, ' ')
                .trim()
                .slice(0, LIMITS.query);
        }

        // Returns '' (unset), normalized origin+path, or null (rejected).
        function validateEndpoint(raw) {
            if (!raw) return '';
            let u;
            try { u = new URL(raw); } catch (_) { return null; }
            if (u.protocol !== 'https:' || u.username || u.password || u.search || u.hash) return null;
            const h = u.hostname.toLowerCase();
            if (h === 'localhost' || h.endsWith('.localhost') || h.endsWith('.local') || h.endsWith('.internal')) return null;
            if (h.startsWith('[') && (h === '[::1]' || h === '[::]' || /^\[(fc|fd|fe[89ab])/.test(h))) return null;
            const v4 = h.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
            if (v4) {
                const a = +v4[1], b = +v4[2];
                if (a === 0 || a === 10 || a === 127 || (a === 169 && b === 254) ||
                    (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168)) return null;
            }
            return u.origin + u.pathname.replace(/\/+$/, '');
        }

        async function readJsonLimited(res) {
            if (!(res.headers.get('content-type') || '').includes('json')) throw new Error('Unexpected content-type');
            if (Number(res.headers.get('content-length')) > LIMITS.body) throw new Error('Response too large');
            const text = await res.text();
            if (text.length > LIMITS.body) throw new Error('Response too large');
            return JSON.parse(text);
        }

        function renderE2eeLabel() {
            document.getElementById('e2eeStatusLabel').textContent = state.useE2EE ? 'AES-GCM PoC' : 'TLS';
        }

        // Safe arithmetic evaluator: recursive descent, whitelist of functions, no dynamic code execution.
        const MathSolver = {
            FUNCS: Object.freeze({
                sqrt: Math.sqrt, sin: Math.sin, cos: Math.cos, tan: Math.tan,
                log: Math.log10, log2: Math.log2, ln: Math.log, abs: Math.abs, pow: Math.pow
            }),
            CONSTS: Object.freeze({ pi: Math.PI, e: Math.E }),
            tokenize(src) {
                const re = /\s*(?:(\d+(?:\.\d+)?|\.\d+)|(\*\*|[-+*\/^(),])|([a-z][a-z0-9]*))/iy;
                const out = [];
                let pos = 0;
                while (pos < src.length) {
                    re.lastIndex = pos;
                    const m = re.exec(src);
                    if (!m) return null;
                    pos = re.lastIndex;
                    if (m[1] !== undefined) out.push({ t: 'num', v: parseFloat(m[1]) });
                    else if (m[2] !== undefined) out.push({ t: 'op', v: m[2] === '**' ? '^' : m[2] });
                    else out.push({ t: 'id', v: m[3].toLowerCase() });
                    if (out.length > 200) return null;
                }
                return out;
            },
            evaluate(input) {
                if (typeof input !== 'string' || input.length > 200) return null;
                const toks = this.tokenize(input.trim());
                if (!toks || !toks.length) return null;
                const self = this;
                let i = 0, depth = 0;
                const fail = () => { throw new SyntaxError('math'); };
                const eat = (v) => {
                    const t = toks[i];
                    if (t && t.t === 'op' && t.v === v) { i++; return true; }
                    return false;
                };
                const expr = () => { let v = term(); for (;;) { if (eat('+')) v += term(); else if (eat('-')) v -= term(); else return v; } };
                const term = () => { let v = unary(); for (;;) { if (eat('*')) v *= unary(); else if (eat('/')) v /= unary(); else return v; } };
                const unary = () => { if (eat('-')) return -unary(); if (eat('+')) return unary(); return power(); };
                const power = () => { const b = primary(); return eat('^') ? Math.pow(b, unary()) : b; };
                const primary = () => {
                    if (++depth > 32) fail();
                    try {
                        const t = toks[i++];
                        if (!t) fail();
                        if (t.t === 'num') return t.v;
                        if (t.t === 'id') {
                            if (Object.hasOwn(self.CONSTS, t.v)) return self.CONSTS[t.v];
                            if (!Object.hasOwn(self.FUNCS, t.v) || !eat('(')) fail();
                            const args = [];
                            if (!eat(')')) {
                                do { args.push(expr()); } while (eat(','));
                                if (!eat(')')) fail();
                            }
                            const fn = self.FUNCS[t.v];
                            if (args.length !== fn.length) fail();
                            return fn(...args);
                        }
                        if (t.v === '(') { const v = expr(); if (!eat(')')) fail(); return v; }
                        return fail();
                    } finally { depth--; }
                };
                try {
                    const r = expr();
                    if (i !== toks.length) return null;
                    return Number.isFinite(r) ? r : null;
                } catch (_) { return null; }
            }
        };

