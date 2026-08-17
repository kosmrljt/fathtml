# fathtml

**One HTML file. Everything inside. Nothing else needed.**

Embed all resources, compress, encrypt, and share — as a single `.html` file.

## The Problem

You render an HTML report (Quarto, Jupyter, R Markdown) and get a directory full of dependencies:

```
report.html
report_files/
  ├── libs/
  │   ├── bootstrap/
  │   └── quarto-html/
  └── figure-output/
      ├── plot1.png
      └── plot2.png
```

Sharing this requires zipping, and if one file is missing the page breaks. Quarto's `embed-resources: true` option doesn't always produce fully self-contained output ([quarto-cli#12315](https://github.com/quarto-dev/quarto-cli/discussions/12315)). PDF loses interactivity — no hovering over data points, no sortable tables.

## The Solution

```
python fathtml.py report.html
```

One file. Everything embedded. Send by email, Slack, Teams. Opens in any browser, works offline.

## Features

**Single-file embedding** —
All CSS, JavaScript, images, and fonts are embedded using inline `<style>`, `<script>`, and `data:` URIs. No `_files/` directory, no broken links.

**Compression** —
HTML with embedded Plotly.js can reach 5-10 MB. Gzip compression shrinks by 50-70%, making files practical for email.

**Encryption** —
AES-256-GCM with PBKDF2 key derivation (100,000 iterations). Decryption happens in the browser using the Web Crypto API — the recipient needs only a browser. Unlike PDF password protection, which relies on viewer compliance, this is cryptographic — without the password the content is inaccessible.

**Expiry dates** —
Documents can expire after a date or time period. The expiry is inside the encrypted payload, so it cannot be modified without the password. Requires `--password`.

**Works with any HTML** —
Not limited to Quarto. Jupyter exports, R Markdown, hand-written HTML, static site generators — any HTML with external dependencies.

## Quick Start

### Installation

```bash
# Single file — download and use
curl -O https://raw.githubusercontent.com/kosmrljt/fathtml/main/fathtml.py

# Or clone
git clone https://github.com/kosmrljt/fathtml.git
```

### Requirements

**Python 3.10+**

Core functionality needs no extra packages. For encryption (`--password`):

```bash
pip install cryptography      # or: pip install pycryptodome
```

For Quarto workflow (optional):

```bash
pip install matplotlib plotly pandas jupyter
# Quarto: https://quarto.org/docs/get-started/
```

### Usage

```bash
# Embed local _files/ resources
python fathtml.py report.html

# Also embed CDN libraries (jQuery, Plotly, DataTables...)
python fathtml.py report.html --fetch-external

# Compress (50-70% smaller)
python fathtml.py report.html --compress

# Encrypt
python fathtml.py report.html --password secret123

# Encrypt + compress + expire in 7 days
python fathtml.py report.html --password secret123 --compress --expires 7d

# All options
python fathtml.py report.html --fetch-external --minify --compress \
    --password secret123 --expires 7d --no-print
```

### Quarto Workflow

For `.py` or `.qmd` files, the included `render.sh` runs Quarto and fathtml in one step:

```bash
./render.sh report.py
./render.sh report.py --password secret123 --compress --expires 7d
```

## Options

| Option             | Description                                                                              |
| ------------------ | ---------------------------------------------------------------------------------------- |
| `--fetch-external` | Download external JS/CSS from CDN URLs and embed inline                                  |
| `--minify`         | Minify CSS (JS is left untouched to avoid breaking minified libraries)                   |
| `--compress`       | Gzip compress + base64, wrapped in a bootstrap page that decompresses in the browser     |
| `--password PASS`  | AES-256-GCM encryption. Password can also be passed via URL: `file.html?key=secret`     |
| `--expires WHEN`   | Set expiry. Requires `--password`. Formats: `7d`, `12h`, `30m`, `2025-12-31`             |
| `--no-print`       | Hide content when printing (CSS `@media print`)                                          |
| `--keep-backup`    | Save original as `.html.bak` before overwriting                                          |

## How It Works

fathtml processes HTML in up to 4 phases:

### Phase 1: Embed Local Resources

Scans for references to `_files/` and replaces them:

| Type         | Before                                          | After                                   |
| ------------ | ----------------------------------------------- | --------------------------------------- |
| CSS          | `<link href="report_files/libs/bootstrap.css">` | `<style>...inline CSS...</style>`       |
| JavaScript   | `<script src="report_files/libs/quarto.js">`    | `<script>...inline JS...</script>`      |
| Images       | `<img src="report_files/figure/plot.png">`      | `<img src="data:image/png;base64,...">` |
| Fonts in CSS | `url(../fonts/icon.woff2)`                      | `url(data:font/woff2;base64,...)`       |

### Phase 2: External Resources (`--fetch-external`)

Downloads CSS/JS from CDN URLs and embeds inline. Each URL is fetched once and cached. Timeout is 120s to handle large libraries like Plotly.js (~3.5 MB).

### Phase 3: Minification (`--minify`)

Removes CSS comments and collapses whitespace. JavaScript is not minified — regex-based minification breaks already-minified libraries.

### Phase 4: Compression or Encryption

**Compression** uses the browser's native [DecompressionStream API](https://developer.mozilla.org/en-US/docs/Web/API/DecompressionStream).

**Encryption** derives a key with PBKDF2 (100k iterations, SHA-256), encrypts with AES-256-GCM, and wraps the result in an HTML page with a password prompt. Decryption uses the browser's [Web Crypto API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Crypto_API).

## Examples

### Client report with encryption and expiry

```bash
quarto render quarterly_analysis.py
python fathtml.py quarterly_analysis.html \
    --fetch-external --compress --password Q3-Report-2025 --expires 30d
# Send by email, share password via separate channel
```

### Portable dashboard

```bash
python fathtml.py dashboard.html --fetch-external --compress
# 8 MB → 2.5 MB, works offline
```

### Standalone fix for Quarto output

```bash
python fathtml.py report.html
rm -rf report_files/
```

## How is this different from SingleFile / Monolith?

Tools like [SingleFile](https://github.com/gildas-lormeau/SingleFile) (browser extension) and [Monolith](https://github.com/Y2Z/monolith) (CLI) capture existing web pages as single HTML files. They are designed to archive pages you visit.

fathtml solves a different problem — it processes HTML that you generate yourself (Quarto, Jupyter, R Markdown) and makes it truly self-contained. On top of resource embedding, it adds gzip compression, AES-256 encryption, and document expiry — features that archiving tools don't provide.

| | fathtml | SingleFile / Monolith |
|---|---|---|
| Purpose | Post-process your own HTML output | Archive any web page |
| Compression | Yes (gzip, 50-70% reduction) | No |
| Encryption | Yes (AES-256-GCM) | No |
| Expiry dates | Yes (tamper-proof) | No |
| Input | Local HTML files you generate | Live web pages |

## Browser Compatibility

| Feature     | Chrome | Firefox | Safari | Edge  |
| ----------- | ------ | ------- | ------ | ----- |
| Embed only  | All    | All     | All    | All   |
| Compression | 80+    | 113+    | 16.4+  | 80+   |
| Encryption  | 37+    | 34+     | 11+    | 79+   |

## Security Notes

- Encryption uses AES-256-GCM with PBKDF2 — standard cryptographic primitives.
- Expiry dates are inside the encrypted payload and cannot be modified without the password.
- No server is contacted. Everything runs in the browser.
- Once decrypted, content is visible in the browser and can be saved. The protection covers the file at rest and during transmission.
- The URL key parameter (`?key=secret`) is convenient but appears in browser history.

## Project

This project started as a practical solution for sharing self-contained HTML reports and evolved into a more general-purpose tool through iterative development with Claude (Anthropic).

- **Author**: Tomaž Košmrlj
- **License**: MIT
- **Contributions**: Issues, PRs, and ideas are welcome.
