#!/usr/bin/env python3
"""
bathtml.py — Make any HTML file fully self-contained.

Embeds local resources (_files/), downloads CDN libraries, compresses,
encrypts with AES-256-GCM, and adds expiry dates.

Works with Quarto, Jupyter, R Markdown, or any HTML file.

Usage:
    python bathtml.py report.html                                # embed local _files
    python bathtml.py report.html --fetch-external               # + CDN libraries
    python bathtml.py report.html --fetch-external --minify      # + CSS minification
    python bathtml.py report.html --compress                     # + gzip compression
    python bathtml.py report.html --password secret              # + AES-256-GCM encryption
    python bathtml.py report.html --password s --compress        # + encryption + compression
    python bathtml.py report.html --password s --expires 7d      # + expiry (requires password)

Options:
    --fetch-external   Download external JS/CSS from CDN and embed inline
    --minify           Minify CSS (remove comments/whitespace). JS is left untouched
    --compress         Compress with gzip + base64 (typically 50-70% smaller)
    --password PASS    Encrypt with AES-256-GCM. Opens with password or URL ?key=PASS
    --expires WHEN     Expiry date (requires --password). YYYY-MM-DD or Nd/Nh/Nm
    --no-print         Disable browser printing via CSS
    --keep-backup      Save original as .html.bak before overwriting

Requirements:
    Python 3.10+
    For --password: pip install cryptography  (or pycryptodome)

"""

import sys
import os
import re
import base64
import gzip
import json
import mimetypes
import argparse
import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timedelta, timezone


# =============================================================================
#  UTILITY FUNCTIONS
# =============================================================================

def file_to_data_uri(filepath: Path) -> str:
    """
    Convert any file to a base64 data: URI.

    Used to inline images, fonts, and other binary assets directly into HTML.
    Example: image.png → data:image/png;base64,iVBOR...
    """
    # Guess MIME type from extension
    mime, _ = mimetypes.guess_type(str(filepath))

    # Fallback for types Python doesn't know about
    if mime is None:
        mime = {
            '.woff2': 'font/woff2',
            '.woff':  'font/woff',
            '.ttf':   'font/ttf',
            '.eot':   'application/vnd.ms-fontobject',
            '.ico':   'image/x-icon',
            '.map':   'application/json',
        }.get(filepath.suffix, 'application/octet-stream')

    data = filepath.read_bytes()
    b64 = base64.b64encode(data).decode('ascii')
    return f"data:{mime};base64,{b64}"


def read_text(filepath: Path) -> str:
    """Read a text file with UTF-8 encoding, replacing invalid bytes."""
    return filepath.read_text(encoding='utf-8', errors='replace')


def fetch_url(url: str, timeout: int = 60) -> str | None:
    """
    Download text content from a URL.

    Returns None on any error (timeout, DNS, HTTP error, etc.)
    Used by --fetch-external to download CDN libraries.
    """
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 bathtml.py',
            'Accept-Encoding': 'identity',  # Don't ask for gzip — we want raw text
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        print(f"  ⚠ Could not fetch: {url}\n    {e}")
        return None


def process_css_urls(css_text: str, css_dir: Path) -> str:
    """
    Replace relative url() references inside CSS with inline data: URIs.

    Example: url(../fonts/icon.woff2) → url(data:font/woff2;base64,...)

    Only processes local file references. Skips http:// and data: URLs.
    """
    def replace_url(match):
        url = match.group(1).strip('\'"')

        # Skip URLs that are already absolute or data URIs
        if url.startswith('data:') or url.startswith('http'):
            return match.group(0)

        # Resolve relative path from the CSS file's directory
        ref_path = (css_dir / url).resolve()
        if ref_path.is_file():
            return f"url({file_to_data_uri(ref_path)})"

        return match.group(0)  # File not found — leave as is

    return re.sub(r'url\(([^)]+)\)', replace_url, css_text)


def minify_css(css: str) -> str:
    """
    Basic CSS minification — no external dependencies needed.

    Removes comments, collapses whitespace, strips spaces around
    punctuation. NOT used on JS (regex-based minification breaks
    minified libraries like Plotly that contain URL strings).
    """
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)   # Remove /* comments */
    css = re.sub(r'\s+', ' ', css)                          # Collapse whitespace
    css = re.sub(r'\s*([{}:;,>+~])\s*', r'\1', css)        # Strip around punctuation
    css = re.sub(r';}', '}', css)                           # Remove trailing semicolons
    return css.strip()


# =============================================================================
#  COMPRESSION — gzip + base64 bootstrap loader
# =============================================================================

def make_compressed_html(html: str, no_print: bool = False) -> str:
    """
    Compress HTML with gzip and wrap in a bootstrap loader.

    The output HTML contains:
    1. A small loading spinner
    2. The gzip-compressed, base64-encoded original HTML
    3. JS that decompresses and renders via document.write()

    Browser support: Chrome 80+, Firefox 113+, Safari 16.4+ (DecompressionStream API)
    """
    compressed = gzip.compress(html.encode('utf-8'), compresslevel=9)
    b64 = base64.b64encode(compressed).decode('ascii')

    original_kb = len(html.encode('utf-8')) / 1024
    compressed_kb = len(compressed) / 1024
    print(f"  Compression: {original_kb:.0f} KB → {compressed_kb:.0f} KB "
          f"({(1 - compressed_kb / original_kb) * 100:.0f}% saved)")

    no_print_css = '<style>@media print { body * { display: none !important; } }</style>' if no_print else ''

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Loading...</title>
  {no_print_css}
  <style>
    body {{ display: flex; justify-content: center; align-items: center;
           height: 100vh; margin: 0; font-family: system-ui; background: #f5f5f5; }}
    #loader {{ text-align: center; color: #666; }}
    .spinner {{ width: 40px; height: 40px; margin: 0 auto 16px;
               border: 4px solid #e0e0e0; border-top: 4px solid #666;
               border-radius: 50%; animation: spin 0.8s linear infinite; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  </style>
</head>
<body>
  <div id="loader">
    <div class="spinner"></div>
    <div>Decompressing...</div>
  </div>

  <script>
    (async () => {{
      // 1. Decode base64 → binary
      const raw = atob("{b64}");
      const bytes = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);

      // 2. Decompress gzip using browser's DecompressionStream
      const stream = new DecompressionStream('gzip');
      const writer = stream.writable.getWriter();
      writer.write(bytes);
      writer.close();

      // 3. Read decompressed chunks
      const reader = stream.readable.getReader();
      const chunks = [];
      while (true) {{
        const {{ done, value }} = await reader.read();
        if (done) break;
        chunks.push(value);
      }}

      // 4. Decode UTF-8 and render
      const html = new TextDecoder().decode(await new Blob(chunks).arrayBuffer());
      document.open();
      document.write(html);
      document.close();
    }})();
  </script>
</body>
</html>"""


# =============================================================================
#  ENCRYPTION — AES-256-GCM with password prompt
# =============================================================================

def make_encrypted_html(html: str, password: str,
                        expires_iso: str | None = None,
                        do_compress: bool = False,
                        no_print: bool = False) -> str:
    """
    Encrypt HTML with AES-256-GCM and wrap in a password-prompt page.

    Encryption pipeline:
    1. Optionally gzip the HTML (--compress)
    2. Prepend metadata JSON (expiry date, etc.)
    3. Derive 256-bit key from password using PBKDF2 (100k iterations)
    4. Encrypt with AES-256-GCM (random salt + IV each time)
    5. Base64 encode: salt(16) + iv(12) + tag(16) + ciphertext

    Decryption happens in the browser using Web Crypto API.
    Password can be entered manually or passed via URL: file.html?key=secret
    """

    # --- Step 1: Optionally compress ---
    if do_compress:
        raw = gzip.compress(html.encode('utf-8'), compresslevel=9)
        print(f"  Pre-compression: {len(html) // 1024} KB → {len(raw) // 1024} KB")
    else:
        raw = html.encode('utf-8')

    # --- Step 2: Prepend metadata ---
    # Format: [4 bytes meta length][JSON metadata][content]
    # Metadata is checked AFTER decryption, so it can't be tampered with
    meta = {}
    if expires_iso:
        meta['expires'] = expires_iso
    meta_json = json.dumps(meta).encode('utf-8')
    payload = len(meta_json).to_bytes(4, 'big') + meta_json + raw

    # --- Step 3: Derive key with PBKDF2 ---
    salt = secrets.token_bytes(16)  # Random salt — different each time
    iv = secrets.token_bytes(12)    # Random IV — different each time
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000, dklen=32)

    # --- Step 4: Encrypt with AES-256-GCM ---
    ciphertext, tag = _aes_gcm_encrypt(key, iv, payload)

    # --- Step 5: Pack and base64 encode ---
    # Layout: salt(16) | iv(12) | tag(16) | ciphertext(...)
    encrypted = salt + iv + tag + ciphertext
    b64 = base64.b64encode(encrypted).decode('ascii')
    print(f"  Encrypted: {len(b64) // 1024} KB (base64)")

    # --- Build the JS decryption code ---

    # Expiry check (runs after successful decryption)
    if expires_iso:
        expires_check_js = f"""
        // Check expiry date (embedded inside encrypted payload — tamper-proof)
        const metaLen = new DataView(decrypted.slice(0, 4)).getUint32(0);
        const meta = JSON.parse(new TextDecoder().decode(decrypted.slice(4, 4 + metaLen)));
        if (meta.expires && new Date() > new Date(meta.expires)) {{
          showError('This document has expired (' + new Date(meta.expires).toLocaleDateString() + ').');
          return;
        }}
        const content = decrypted.slice(4 + metaLen);"""
        expires_msg_html = f'<div style="font-size:12px; color:#999; margin-top:8px;">Valid until: {expires_iso}</div>'
    else:
        expires_check_js = """
        const metaLen = new DataView(decrypted.slice(0, 4)).getUint32(0);
        const content = decrypted.slice(4 + metaLen);"""
        expires_msg_html = ''

    # Decompression step (if --compress was used)
    if do_compress:
        decode_step_js = """
        // Decompress gzip
        const decompStream = new DecompressionStream('gzip');
        const decompWriter = decompStream.writable.getWriter();
        decompWriter.write(new Uint8Array(content));
        decompWriter.close();
        const decompReader = decompStream.readable.getReader();
        const chunks = [];
        while (true) {
          const { done, value } = await decompReader.read();
          if (done) break;
          chunks.push(value);
        }
        const html = new TextDecoder().decode(await new Blob(chunks).arrayBuffer());"""
    else:
        decode_step_js = """
        const html = new TextDecoder().decode(content);"""

    no_print_css = '<style>@media print {{ body * {{ display: none !important; }} }}</style>' if no_print else ''

    # --- The complete encrypted HTML document ---
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Protected Document</title>
  {no_print_css}
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      display: flex; justify-content: center; align-items: center;
      min-height: 100vh; font-family: system-ui, -apple-system, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }}
    .card {{
      background: #fff; border-radius: 16px; padding: 40px;
      max-width: 420px; width: 90%;
      box-shadow: 0 20px 60px rgba(0,0,0,0.3); text-align: center;
    }}
    .card h2 {{ margin-bottom: 8px; color: #333; font-size: 20px; }}
    .card .subtitle {{ color: #888; font-size: 13px; margin-bottom: 24px; }}
    .card input {{
      width: 100%; padding: 12px 16px; border: 2px solid #e0e0e0;
      border-radius: 8px; font-size: 16px; outline: none; transition: border-color 0.2s;
    }}
    .card input:focus {{ border-color: #667eea; }}
    .card button {{
      width: 100%; padding: 12px; margin-top: 12px; border: none;
      border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer;
      background: linear-gradient(135deg, #667eea, #764ba2);
      color: #fff; transition: opacity 0.2s;
    }}
    .card button:hover {{ opacity: 0.9; }}
    .card .error {{ color: #e53e3e; font-size: 13px; margin-top: 12px; display: none; }}
    .card .spinner {{
      display: none; width: 24px; height: 24px; margin: 12px auto 0;
      border: 3px solid #e0e0e0; border-top: 3px solid #667eea;
      border-radius: 50%; animation: spin 0.7s linear infinite;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  </style>
</head>
<body>

  <!-- Password prompt card -->
  <div class="card" id="loginCard">
    <h2>🔒 Protected Document</h2>
    <div class="subtitle">Enter password to access</div>
    {expires_msg_html}
    <input type="password" id="pwd" placeholder="Password" autofocus
           onkeydown="if (event.key === 'Enter') decrypt()">
    <button onclick="decrypt()">Unlock</button>
    <div class="error" id="err"></div>
    <div class="spinner" id="spinner"></div>
  </div>

  <script>
    // Encrypted payload (base64): salt + iv + tag + ciphertext
    const ENCRYPTED = "{b64}";

    function showError(message) {{
      document.getElementById('err').textContent = message;
      document.getElementById('err').style.display = 'block';
      document.getElementById('spinner').style.display = 'none';
    }}

    async function decrypt() {{
      // Get password from input field or URL parameter ?key=...
      const password = document.getElementById('pwd').value
        || new URLSearchParams(location.search).get('key')
        || '';

      if (!password) {{
        showError('Please enter a password.');
        return;
      }}

      // Show spinner
      document.getElementById('err').style.display = 'none';
      document.getElementById('spinner').style.display = 'block';
      await new Promise(resolve => setTimeout(resolve, 50));  // Let spinner render

      try {{
        // --- Decode base64 to bytes ---
        const raw = atob(ENCRYPTED);
        const bytes = new Uint8Array(raw.length);
        for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);

        // --- Parse binary layout: salt(16) + iv(12) + tag(16) + ciphertext ---
        const salt       = bytes.slice(0, 16);
        const iv         = bytes.slice(16, 28);
        const tag        = bytes.slice(28, 44);
        const ciphertext = bytes.slice(44);

        // --- Derive decryption key using PBKDF2 (must match Python side) ---
        const keyMaterial = await crypto.subtle.importKey(
          'raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveKey']
        );
        const key = await crypto.subtle.deriveKey(
          {{ name: 'PBKDF2', salt: salt, iterations: 100000, hash: 'SHA-256' }},
          keyMaterial,
          {{ name: 'AES-GCM', length: 256 }},
          false,
          ['decrypt']
        );

        // --- Decrypt (WebCrypto expects tag appended to ciphertext) ---
        const combined = new Uint8Array(ciphertext.length + 16);
        combined.set(ciphertext);
        combined.set(tag, ciphertext.length);

        const decrypted = await crypto.subtle.decrypt(
          {{ name: 'AES-GCM', iv: iv }}, key, combined
        );

        // --- Check expiry + extract content ---
        {expires_check_js}

        // --- Decode (and optionally decompress) ---
        {decode_step_js}

        // --- Render the decrypted HTML ---
        document.open();
        document.write(html);
        document.close();

      }} catch (error) {{
        if (error.name === 'OperationError') {{
          showError('Incorrect password.');
        }} else {{
          showError('Error: ' + error.message);
        }}
        document.getElementById('spinner').style.display = 'none';
      }}
    }}

    // Auto-decrypt if password is provided via URL: file.html?key=secret
    (() => {{
      const urlKey = new URLSearchParams(location.search).get('key');
      if (urlKey) {{
        document.getElementById('pwd').value = urlKey;
        decrypt();
      }}
    }})();
  </script>
</body>
</html>"""


def _aes_gcm_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    """
    Encrypt with AES-256-GCM. Returns (ciphertext, tag).

    Tries two libraries in order:
    1. cryptography (recommended, pip install cryptography)
    2. pycryptodome  (alternative, pip install pycryptodome)
    """
    # Try: cryptography library
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        result = AESGCM(key).encrypt(iv, plaintext, None)
        return result[:-16], result[-16:]  # Last 16 bytes are the GCM tag
    except ImportError:
        pass

    # Try: pycryptodome library
    try:
        from Crypto.Cipher import AES
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        return cipher.encrypt_and_digest(plaintext)
    except ImportError:
        pass

    # Neither library available
    print("\n  ⚠ Encryption requires one of these Python packages:")
    print("    pip install cryptography     (recommended)")
    print("    pip install pycryptodome      (alternative)")
    sys.exit(1)


# =============================================================================
#  EXPIRY DATE PARSING
# =============================================================================

def parse_expires(value: str) -> str:
    """
    Parse --expires value into an ISO 8601 date string.

    Accepts:
      Relative:  3d (3 days), 12h (12 hours), 30m (30 minutes)
      Absolute:  2025-07-01 or 2025-07-01T12:00:00
    """
    # Relative format: 3d, 12h, 30m
    match = re.match(r'^(\d+)([dhm])$', value)
    if match:
        num = int(match.group(1))
        unit = match.group(2)
        delta = {
            'd': timedelta(days=num),
            'h': timedelta(hours=num),
            'm': timedelta(minutes=num),
        }[unit]
        return (datetime.now(timezone.utc) + delta).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Absolute: YYYY-MM-DD
    try:
        dt = datetime.strptime(value, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    except ValueError:
        pass

    # Full ISO format
    try:
        return datetime.fromisoformat(value).isoformat()
    except ValueError:
        print(f"ERROR: Invalid --expires format: {value}")
        print("  Expected: YYYY-MM-DD, 3d, 12h, or 30m")
        sys.exit(1)


# =============================================================================
#  MAIN PROCESSING PIPELINE
# =============================================================================

def embed_resources(html_path: str, fetch_external: bool = False,
                    do_minify: bool = False, do_compress: bool = False,
                    password: str | None = None, expires: str | None = None,
                    no_print: bool = False, keep_backup: bool = False):
    """
    Main processing pipeline. Runs 4 phases:

    Phase 1: Embed local resources (CSS, JS, images from _files/ directory)
    Phase 2: Download and embed external CDN resources (--fetch-external)
    Phase 3: Minify CSS (--minify)
    Phase 4: Encrypt (--password) or compress (--compress)
    """
    html_file = Path(html_path)
    if not html_file.is_file():
        print(f"ERROR: {html_file} does not exist!")
        sys.exit(1)

    base_name = html_file.stem
    files_dir = html_file.parent / f"{base_name}_files"

    # Save backup before modifying
    if keep_backup:
        import shutil
        backup_path = html_file.with_suffix('.html.bak')
        shutil.copy2(html_file, backup_path)
        print(f"  Backup saved: {backup_path}")

    html = html_file.read_text(encoding='utf-8')
    local_count = 0
    external_count = 0

    # ==================================================================
    #  PHASE 1: Embed local _files resources
    # ==================================================================
    # Quarto/Jupyter generate a _files/ directory with CSS, JS, images.
    # We inline everything so the HTML works without that directory.
    # ==================================================================
    print(f"\n📁 Phase 1: Local resources ({files_dir.name})")

    # --- 1a: CSS <link> tags → inline <style> ---
    def replace_local_link(match):
        nonlocal local_count
        full_tag = match.group(0)
        href_match = re.search(r'href="([^"]*)"', full_tag)
        if not href_match:
            return full_tag
        href = href_match.group(1)
        if f'{base_name}_files' not in href:
            return full_tag  # Not a local resource
        css_path = (html_file.parent / href).resolve()
        if css_path.is_file():
            css_text = process_css_urls(read_text(css_path), css_path.parent)
            if do_minify:
                css_text = minify_css(css_text)
            local_count += 1
            return f"<style>/* {css_path.name} */\n{css_text}\n</style>"
        return full_tag

    html = re.sub(r'<link\b[^>]*>', replace_local_link, html)

    # --- 1b: JS <script src="..."> → inline <script> ---
    def replace_local_script(match):
        nonlocal local_count
        full_tag = match.group(0)
        src_match = re.search(r'src="([^"]*)"', full_tag)
        if not src_match:
            return full_tag
        src = src_match.group(1)
        if f'{base_name}_files' not in src:
            return full_tag
        js_path = (html_file.parent / src).resolve()
        if js_path.is_file():
            local_count += 1
            return f"<script>/* {js_path.name} */\n{read_text(js_path)}\n</script>"
        return full_tag

    html = re.sub(r'<script\b[^>]*src="[^"]*"[^>]*>\s*</script>', replace_local_script, html)

    # --- 1c: <img src="..."> → inline data: URI ---
    def replace_local_img(match):
        nonlocal local_count
        full_tag = match.group(0)
        src_match = re.search(r'src="([^"]*)"', full_tag)
        if not src_match:
            return full_tag
        src = src_match.group(1)
        if f'{base_name}_files' not in src:
            return full_tag
        img_path = (html_file.parent / src).resolve()
        if img_path.is_file():
            local_count += 1
            return full_tag.replace(f'src="{src}"', f'src="{file_to_data_uri(img_path)}"')
        return full_tag

    html = re.sub(r'<img\b[^>]*>', replace_local_img, html)

    # --- 1d: CSS url("..._files/...") → inline data: URI ---
    def replace_inline_url(match):
        nonlocal local_count
        url = match.group(1)
        if f'{base_name}_files' not in url:
            return match.group(0)
        res_path = (html_file.parent / url).resolve()
        if res_path.is_file():
            local_count += 1
            return f'url("{file_to_data_uri(res_path)}")'
        return match.group(0)

    html = re.sub(
        r'url\("([^"]*' + re.escape(base_name) + r'_files[^"]*)"\)',
        replace_inline_url, html
    )

    print(f"  ✓ Embedded {local_count} local resources")

    # ==================================================================
    #  PHASE 2: Embed external CDN resources (--fetch-external)
    # ==================================================================
    # Downloads JS/CSS from CDN URLs (jQuery, DataTables, Plotly, etc.)
    # and inlines them. Makes the HTML work completely offline.
    #
    # Note: JS is NOT minified (regex minification breaks libraries).
    #       CSS IS minified if --minify is also set.
    # Timeout is 120s to handle large libraries (Plotly ~3.5 MB).
    # ==================================================================
    if fetch_external:
        print(f"\n🌐 Phase 2: External resources (CDN)")
        cache: dict[str, str | None] = {}

        def fetch_cached(url: str) -> str | None:
            """Download with caching — each URL is fetched only once."""
            if url not in cache:
                print(f"  ↓ {url[:90]}...")
                cache[url] = fetch_url(url, timeout=120)
            return cache[url]

        # --- 2a: External CSS → inline <style> ---
        def replace_ext_link(match):
            nonlocal external_count
            full_tag = match.group(0)
            href_match = re.search(r'href="(https?://[^"]*)"', full_tag)
            if not href_match:
                return full_tag
            href = href_match.group(1)
            # Only process stylesheet links
            if 'stylesheet' not in full_tag and '.css' not in href:
                return full_tag
            content = fetch_cached(href)
            if content is not None:
                if do_minify:
                    content = minify_css(content)
                external_count += 1
                short_name = href.split('/')[-1][:50]
                return f"<style>/* {short_name} */\n{content}\n</style>"
            return full_tag

        html = re.sub(r'<link\b[^>]*href="https?://[^"]*"[^>]*/?\s*>', replace_ext_link, html)

        # --- 2b: External JS → inline <script> ---
        def replace_ext_script(match):
            nonlocal external_count
            full_tag = match.group(0)
            src_match = re.search(r'src="(https?://[^"]*)"', full_tag)
            if not src_match:
                return full_tag
            src = src_match.group(1)
            content = fetch_cached(src)
            if content is not None:
                external_count += 1
                short_name = src.split('/')[-1][:50]
                return f"<script>/* {short_name} */\n{content}\n</script>"
            return full_tag

        html = re.sub(
            r'<script\b[^>]*src="https?://[^"]*"[^>]*>\s*</script>',
            replace_ext_script, html
        )

        print(f"  ✓ Embedded {external_count} external resources")

    # ==================================================================
    #  PHASE 3: CSS minification (--minify)
    # ==================================================================
    if do_minify:
        print(f"\n✂️  Phase 3: CSS minification")
        before = len(html)
        html = re.sub(
            r'<style>(.*?)</style>',
            lambda m: f"<style>{minify_css(m.group(1))}</style>",
            html, flags=re.DOTALL
        )
        saved_kb = (before - len(html)) / 1024
        print(f"  ✓ Saved {saved_kb:.0f} KB")

    # ==================================================================
    #  PHASE 4: Encryption or compression
    # ==================================================================
    expires_iso = parse_expires(expires) if expires else None

    # --expires without --password makes no sense (trivially bypassed)
    if expires_iso and not password:
        print(f"\n  ERROR: --expires requires --password")
        print(f"  Without encryption, expiry is trivially bypassed (visible in page source).")
        print(f"  Use: python bathtml.py {html_path} --password YOUR_PASSWORD --expires {expires}")
        sys.exit(1)

    if password:
        print(f"\n🔒 Phase 4: Encryption (AES-256-GCM)")
        if expires_iso:
            print(f"  Expires: {expires_iso}")
        html = make_encrypted_html(html, password, expires_iso, do_compress, no_print)

    elif do_compress:
        print(f"\n🗜️  Phase 4: Compression (gzip + base64)")
        html = make_compressed_html(html, no_print)

    # ==================================================================
    #  WRITE RESULT
    # ==================================================================
    html_file.write_text(html, encoding='utf-8')
    size_kb = html_file.stat().st_size / 1024

    # --- Summary ---
    print(f"\n{'=' * 50}")
    print(f"✓ Done: {html_file}")
    print(f"  Size: {size_kb / 1024:.1f} MB" if size_kb > 1024 else f"  Size: {size_kb:.0f} KB")
    print(f"  Local resources:    {local_count}")
    if fetch_external:
        print(f"  External resources: {external_count}")
    if password:
        print(f"  🔒 Password protected")
        print(f"     Open in browser → enter password")
        print(f"     Or use URL: ...file.html?key={password}")
    if expires_iso:
        print(f"  ⏰ Expires: {expires_iso}")
    if no_print:
        print(f"  🖨️  Printing disabled")
    if files_dir.is_dir():
        print(f"  You can now delete: rm -rf {files_dir}")


# =============================================================================
#  COMMAND LINE INTERFACE
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Make any HTML file fully self-contained. Embed resources, compress, encrypt.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bathtml.py report.html                                   # embed local _files
  python bathtml.py report.html --fetch-external                  # + download CDN libs
  python bathtml.py report.html --fetch-external --minify         # + minify CSS
  python bathtml.py report.html --compress                        # + gzip compression
  python bathtml.py report.html --password secret                 # + AES encryption
  python bathtml.py report.html --password secret --compress      # + encryption + compression
  python bathtml.py report.html --password s --expires 7d         # + expires in 7 days
  python bathtml.py report.html --password s --compress --expires 7d --no-print  # all options
        """)

    parser.add_argument('html_file',
        help='Path to the HTML file to process')

    parser.add_argument('--fetch-external', action='store_true',
        help='Download and embed external JS/CSS from CDN URLs')

    parser.add_argument('--minify', action='store_true',
        help='Minify CSS (JS is left untouched to avoid breaking libraries)')

    parser.add_argument('--compress', action='store_true',
        help='Compress HTML with gzip (typically 50-70%% smaller)')

    parser.add_argument('--password', type=str, default=None,
        help='Encrypt with AES-256-GCM. Requires: pip install cryptography')

    parser.add_argument('--expires', type=str, default=None,
        help='Expiry date (requires --password). Format: YYYY-MM-DD, 3d, 12h, 30m')

    parser.add_argument('--no-print', action='store_true',
        help='Disable browser printing (CSS @media print rule)')

    parser.add_argument('--keep-backup', action='store_true',
        help='Save original file as .html.bak before overwriting')

    args = parser.parse_args()

    embed_resources(
        html_path=args.html_file,
        fetch_external=args.fetch_external,
        do_minify=args.minify,
        do_compress=args.compress,
        password=args.password,
        expires=args.expires,
        no_print=args.no_print,
        keep_backup=args.keep_backup,
    )


if __name__ == '__main__':
    main()
