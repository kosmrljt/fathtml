<p align="center">
  <h1 align="center">🧊 SolidHTML</h1>
  <p align="center">
    <strong>One HTML file. Everything inside. Nothing else needed.</strong>
  </p>
  <p align="center">
    Embed all resources, compress, encrypt, and share — as a single .html file.
  </p>
</p>

---

## The Problem

You've just created a beautiful data report with interactive Plotly charts, sortable DataTables, and matplotlib visualizations. You render it to HTML and get:

```
report.html
report_files/
  ├── libs/
  │   ├── bootstrap/
  │   ├── quarto-html/
  │   └── ...
  ├── figure-output/
  │   ├── plot1.png
  │   └── plot2.png
  └── ...
```

Now try sharing that. You need to zip the whole thing, the recipient needs to unzip it into the right structure, and if one file is missing — broken page. Or you try `embed-resources: true` in Quarto, but it [doesn't actually work](https://github.com/quarto-dev/quarto-cli/discussions/12315) half the time.

**PDF?** Sure, but then you lose interactivity — no hovering over data points, no sortable tables, no expandable code blocks. Your beautiful interactive report becomes a flat screenshot.

## The Solution

```bash
python solidhtml.py report.html
```

Done. One file. Everything inside. Send it by email, Slack, Teams — just the `.html`. Open in any browser, works offline, no server needed.

## Why SolidHTML?

### 📦 True single-file HTML
All CSS, JavaScript, images, and fonts are embedded directly in the HTML using inline `<style>`, `<script>`, and `data:` URIs. No `_files/` directory, no broken links, no zip files.

### 🗜️ Compression
HTML reports with embedded Plotly.js can easily reach 5-10 MB. With `--compress`, gzip shrinks them by 50-70%, making them practical for email attachments.

### 🔒 Real encryption
AES-256-GCM encryption — the same standard used by banks and governments. Without the password, the content is mathematically inaccessible. Not "password-protected PDF" that anyone can crack in 30 seconds with free tools online.

### ⏰ Expiry dates
Set documents to expire after a specific date or time period. The expiry is embedded inside the encrypted payload, so it can't be tampered with (requires `--password`).

### 📊 Better than PDF
Your HTML is still a web page. JavaScript runs, charts are interactive, tables are sortable and searchable, code blocks are expandable. You get the portability of PDF with the functionality of a web app.

### 🌐 Works with anything
Not just Quarto — any HTML file. Jupyter notebook exports, R Markdown output, hand-written HTML, static site generator output. If it's HTML with external dependencies, SolidHTML can make it self-contained.

## Quick Start

### Installation

```bash
# Download the script (it's a single file — that's the whole point)
curl -O https://raw.githubusercontent.com/YOUR_USERNAME/solidhtml/main/solidhtml.py

# Or clone the repo
git clone https://github.com/YOUR_USERNAME/solidhtml.git
```

### Python Requirements

**Python 3.10+** (uses `X | Y` type union syntax)

**Core functionality** — no extra packages needed:
```bash
python solidhtml.py report.html                    # Just works
python solidhtml.py report.html --compress         # Just works
python solidhtml.py report.html --fetch-external   # Just works
```

**For encryption** (`--password`) — install one of these:
```bash
pip install cryptography      # Recommended (widely used, well-maintained)
# or
pip install pycryptodome      # Alternative
```

**For Quarto workflow** (optional — only if you render .py/.qmd files):
```bash
pip install matplotlib plotly pandas    # Your data science stack
pip install jupyter                     # Quarto's Jupyter engine
# Quarto itself: https://quarto.org/docs/get-started/
```

### Basic Usage

```bash
# Embed local _files/ resources into HTML
# (fixes Quarto's broken embed-resources)
python solidhtml.py report.html

# Also download and embed CDN libraries (jQuery, Plotly, DataTables...)
python solidhtml.py report.html --fetch-external

# Compress (typically 50-70% smaller)
python solidhtml.py report.html --compress

# Encrypt with password
python solidhtml.py report.html --password secret123

# Encrypt + compress + expire in 7 days
python solidhtml.py report.html --password secret123 --compress --expires 7d

# Everything at once
python solidhtml.py report.html --fetch-external --minify --compress \
    --password secret123 --expires 7d --no-print
```

### Quarto Workflow

If you use Quarto to render `.py` or `.qmd` files, use the included `render.sh`:

```bash
# Render with Quarto + embed resources in one step
./render.sh report.py

# Render + encrypt + compress
./render.sh report.py --password secret123 --compress --expires 7d
```

`render.sh` runs `quarto render`, then `solidhtml.py`, then cleans up the `_files/` directory.

## Options

| Option | Description |
|---|---|
| `--fetch-external` | Download external JS/CSS from CDN URLs and embed inline. Makes the HTML work completely offline |
| `--minify` | Minify CSS (remove comments/whitespace). JS is intentionally left untouched — regex minification breaks libraries like Plotly |
| `--compress` | Compress with gzip + base64. Output is a small bootstrap HTML that decompresses in the browser |
| `--password PASS` | Encrypt with AES-256-GCM. Output shows a password prompt. Password can also be passed via URL: `file.html?key=secret` |
| `--expires WHEN` | Set expiry date. **Requires `--password`** — without encryption, expiry is trivially bypassed. Formats: `7d`, `12h`, `30m`, `2025-12-31` |
| `--no-print` | Hide content when printing (CSS `@media print` rule) |
| `--keep-backup` | Save original file as `.html.bak` before overwriting |

## How It Works

SolidHTML processes your HTML in up to 4 phases:

### Phase 1: Embed Local Resources

Scans the HTML for references to the `_files/` directory and replaces them:

| What | Before | After |
|---|---|---|
| CSS | `<link href="report_files/libs/bootstrap.css">` | `<style>...inline CSS...</style>` |
| JavaScript | `<script src="report_files/libs/quarto.js">` | `<script>...inline JS...</script>` |
| Images | `<img src="report_files/figure/plot.png">` | `<img src="data:image/png;base64,...">` |
| Fonts in CSS | `url(../fonts/icon.woff2)` | `url(data:font/woff2;base64,...)` |

### Phase 2: Embed External CDN Resources (`--fetch-external`)

Downloads CSS/JS from URLs like `https://cdn.datatables.net/...` and embeds them inline. Each URL is fetched only once (cached). Timeout is 120 seconds to handle large libraries like Plotly.js (~3.5 MB).

### Phase 3: CSS Minification (`--minify`)

Removes CSS comments and collapses whitespace. JavaScript is **not** minified — regex-based JS minification would break already-minified libraries (e.g., `https://` looks like a `//` comment to a regex).

### Phase 4: Compression or Encryption

**Compression** (`--compress`): Gzip compresses the entire HTML, base64 encodes it, and wraps it in a minimal bootstrap page with a loading spinner. The browser decompresses using the native [DecompressionStream API](https://developer.mozilla.org/en-US/docs/Web/API/DecompressionStream).

**Encryption** (`--password`):
1. Optionally gzip the content (`--compress`)
2. Prepend JSON metadata (expiry date) to the content
3. Generate random salt (16 bytes) and IV (12 bytes)
4. Derive a 256-bit key using PBKDF2 (100,000 iterations, SHA-256)
5. Encrypt with AES-256-GCM
6. Base64-encode the result: `salt(16) | iv(12) | tag(16) | ciphertext`
7. Wrap in an HTML page with a password prompt

Decryption happens in the browser using the [Web Crypto API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Crypto_API) — the recipient needs only a browser, no software installation.

## SolidHTML vs Alternatives

| | SolidHTML | Quarto `embed-resources` | PDF | ZIP + HTML |
|---|---|---|---|---|
| Single file | ✅ Always works | ❌ Often broken | ✅ | ❌ |
| Interactive charts | ✅ Plotly, D3, etc. | ✅ | ❌ Static only | ✅ |
| Sortable tables | ✅ DataTables, etc. | ✅ | ❌ | ✅ |
| Works offline | ✅ | Partial | ✅ | ✅ |
| Compression | ✅ 50-70% | ❌ | ❌ | ✅ |
| Encryption | ✅ AES-256-GCM | ❌ | ⚠️ Easily cracked | ❌ |
| Expiry dates | ✅ Tamper-proof | ❌ | ❌ | ❌ |
| No install for viewer | ✅ Browser only | ✅ | ✅ | ❌ Need to unzip |
| Offline CDN | ✅ `--fetch-external` | ❌ | N/A | ❌ |

## Browser Compatibility

| Feature | Chrome | Firefox | Safari | Edge |
|---|---|---|---|---|
| Basic (embed only) | ✅ All | ✅ All | ✅ All | ✅ All |
| Compression (`--compress`) | ✅ 80+ | ✅ 113+ | ✅ 16.4+ | ✅ 80+ |
| Encryption (`--password`) | ✅ 37+ | ✅ 34+ | ✅ 11+ | ✅ 79+ |

## Real-World Examples

### Data Science Report for a Client
```bash
quarto render quarterly_analysis.py
python solidhtml.py quarterly_analysis.html \
    --fetch-external --compress --password Q3-Report-2025 --expires 30d
# → Send quarterly_analysis.html by email
# → Share password via separate channel (Slack, SMS, etc.)
# → Client opens in browser, enters password, sees interactive report
# → After 30 days: "This document has expired"
```

### Team Dashboard (No Encryption, Just Portable)
```bash
python solidhtml.py dashboard.html --fetch-external --compress
# → 8 MB dashboard becomes 2.5 MB
# → Attach to email or Slack — no zip needed
# → Works offline on a plane, in a meeting room, anywhere
```

### Confidential Research
```bash
python solidhtml.py research.html --fetch-external --minify --compress \
    --password "correct-horse-battery-staple" --expires 2025-12-31 --no-print
# → AES-256-GCM encrypted, compressed, expires end of year
# → Recipient opens file.html?key=correct-horse-battery-staple
```

### Quick Fix for Broken Quarto Output
```bash
# What embed-resources: true should do but doesn't
python solidhtml.py report.html
rm -rf report_files/
# → Done. report.html now actually works as a standalone file.
```

## Security Notes

- **Encryption is real**: AES-256-GCM with PBKDF2 key derivation (100k iterations). Without the password, the content is cryptographically inaccessible — not obfuscation, not encoding, real encryption.
- **Expiry is tamper-proof**: The expiry date lives inside the encrypted payload. It can't be viewed or modified without the password.
- **No server needed**: Everything happens in the browser. The HTML file never contacts any server.
- **Save As is not blocked**: Once decrypted, the content is displayed in the browser and can be saved. This is intentional — if a browser can render it, it can save it. The protection secures the file at rest and during transmission, not the displayed content.
- **URL key convenience**: `file.html?key=secret` lets you share a clickable link, but the password will appear in browser history. For sensitive data, have the recipient type the password manually.

## Project

- **Author**: Vibe-coded with [Claude](https://claude.ai) (Anthropic)
- **License**: MIT
- **Contributions**: Issues, PRs, and ideas are welcome.
