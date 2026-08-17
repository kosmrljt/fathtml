#!/bin/bash
# render.sh — Render .py with Quarto and embed all resources into the HTML
#
# Usage:
#   ./render.sh test_doc.py                                    # basic
#   ./render.sh test_doc.py --fetch-external                   # + CDN libs
#   ./render.sh test_doc.py --fetch-external --minify          # + CSS minification
#   ./render.sh test_doc.py --compress                         # + compression
#   ./render.sh test_doc.py --password secret                  # + encryption
#   ./render.sh test_doc.py --password secret --expires 3d     # + expiry
#   ./render.sh test_doc.py --compress --password secret --expires 2025-07-01

set -e

FILE="${1:?Usage: $0 <file.py> [options for solidhtml.py]}"
shift
BASE="${FILE%.*}"

echo "=== 1/2: Quarto render ==="
quarto render "$FILE"

echo ""
echo "=== 2/2: Embedding resources into HTML ==="
python3 fathtml.py "${BASE}.html" "$@"

echo ""
if [ -d "${BASE}_files" ]; then
    echo "Cleanup: removing ${BASE}_files/"
    rm -rf "${BASE}_files"
fi
echo "✓ Done: ${BASE}.html"
