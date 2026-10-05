# SecSearch Pro v6.0 — Technical Documentation & Architecture Specification

## 1. Executive Summary & Overview
**SecSearch Pro** is a modern, zero-knowledge, client-side privacy search engine. Built with a single-file architecture (`index.html`), it blends the minimalist privacy-first aesthetic of Qwant with the rich, widget-driven layout of modern search engines like Bing. The application operates on a **Zero-Knowledge Client** paradigm: all credentials, search tokens, and custom API endpoints are stored exclusively within the user's local browser environment (`localStorage`), ensuring zero server-side logging or telemetry.

---

## 2. Core Architecture & Design Patterns

### 2.1. The Single-File Mandate & PWA Integration
*   **Single-File Architecture:** To maximize portability and ease of deployment (e.g., on GitHub Pages under `Anonymousik.is-a.dev/secsearch`), the entire frontend, CSS styling (Tailwind CSS via CDN), client-side reasoning logic, and Web Crypto API wrappers reside in a single `index.html` file.
*   **Progressive Web App (PWA):** A dynamic Service Worker is instantiated via a Blob URL (`sw.js`). It implements a **Cache-First** strategy for static application assets (UI shell, icons, stylesheets) and a **Network-Only** policy for dynamic API queries and E2EE payloads to protect user privacy.
*   **System Integration:** Supports native PWA installation prompts (`beforeinstallprompt`) and provides instructional modals for setting the app as the browser homepage.

### 2.2. Network & API Specification Compliance
SecSearch Pro natively adheres to the official SecSearch REST API documentation specifications:
*   **Endpoint Structure:** `/api/search/{type}` where `{type}` can be `web`, `news`, `images`, `videos`, `social`, or `shopping`.
*   **Required Query Parameters:**
    *   `uiv`: Hardcoded to `4` (protocol version requirement).
    *   `t`: Search type (`web`, `news`, etc.).
    *   `q`: Sanitized search keyword string.
*   **Fallback Aggregation:** If no custom API endpoint is configured by the user, the engine gracefully falls back to querying public, privacy-respecting nodes (SearXNG, Wikipedia API) using parallel asynchronous requests (`Promise.allSettled`).

---

## 3. Cryptography & End-to-End Encryption (E2EE)

SecSearch Pro includes an optional **End-to-End Encryption (E2EE)** transport layer utilizing native browser cryptographic primitives (`Web Crypto API`).

```
[ User Input ] ---> [ Web Crypto API (AES-256-GCM) ] ---> [ Encrypted Payload Hex ] ---> [ Custom API Node ]
```

1.  **Ephemeral Key Generation:** When E2EE is enabled in settings, the application generates a temporary 256-bit symmetric key using `crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"])`.
2.  **Payload Encryption:** The user's search query is encoded to UTF-8 and encrypted with a randomly generated 12-byte initialization vector (IV).
3.  **Visual Transparency:** The resulting ciphertext is converted to hexadecimal format and displayed in real-time within the UI's reasoning console, proving zero-knowledge transport compliance before the query hits the network.
4.  **Credential Isolation:** All API fetch operations enforce `credentials: 'omit'` to prevent cross-site cookie leakage or session tracking.

---

## 4. Advanced Client-Side Reasoning Engine (CoT)

The application features a multi-stage **Chain-of-Thought (CoT)** pipeline executing locally within the browser:

### Stage 1: Intent Classification & XSS Sanitization
*   **Mathematical Solver:** Detects expressions (e.g., arithmetic, square roots, trigonometric functions) and evaluates them safely using a controlled parser, rendering immediate inline solution boxes with KaTeX math formatting.
*   **Input Sanitization:** Strips malicious scripts and validates query boundaries.

### Stage 2: Named Entity Recognition (NER)
*   Scans retrieved result snippets for structured data entities:
    *   **Dates & Years:** Regex matching $\\b(19|20)\\d{2}\\b$
    *   **Percentages & Currencies:** Extraction of financial and statistical data points.
    *   **Capitalized Entities:** Frequency analysis of proper nouns to build dynamic tag filters.

### Stage 3: BM25 Lexical Re-Ranking ($BM25$)
Instead of relying solely on raw API ranking, SecSearch Pro calculates document relevance locally using the Okapi BM25 scoring formula:

$$score(D, Q) = \\sum_{i=1}^{n} IDF(q_i) \\cdot \\frac{f(q_i, D) \\cdot (k_1 + 1)}{f(q_i, D) + k_1 \\cdot \\left(1 - b + b \\cdot \\frac{|D|}{avgdl}\\right)}$$

Where:
*   $f(q_i, D)$ is the term frequency of query term $q_i$ in document $D$.
*   $|D|$ is document length, and $avgdl$ is the average document length across all fetched results.
*   $k_1 = 1.2$ and $b = 0.75$ serve as tuning parameters.

---

## 5. Security Hardening & XSS Defense

To completely mitigate Cross-Site Scripting (XSS) vulnerabilities (both stored and reflected):
1.  **Strict HTML Escaping:** All incoming strings from API responses (`title`, `desc`, `url`) pass through an escaping function converting special characters (`&`, `<`, `>`, `"`, `'`) to safe HTML entities.
2.  **Controlled Highlight Restoration:** The SecSearch API returns highlighted keywords wrapped in `<b>` tags. A secondary safe parser replaces only `&lt;b&gt;` and `&lt;/b&gt;` with styled span/b elements (`<b class="text-neoncyan bg-neoncyan/10 px-0.5 rounded">`), ignoring all other injected markup.
3.  **Outbound Link Protection:** Every external link generated in the search feed automatically receives hardening attributes: `target="_blank" rel="noopener noreferrer nofollow"`.

---

## 6. Author & Attribution
*   **Author / Creator:** [Anonymousik.is-a.dev/secsearch](https://Anonymousik.is-a.dev/secsearch)
*   **License:** MIT / Open Source Privacy Architecture