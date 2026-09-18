#!/bin/sh
# Rasterize index/edition.json into the Agent Index listing JPGs.
# Always the repo's agent image (Dockerfile pins WeasyPrint 62.3). Host
# needs poppler's pdftoppm. Does not stop a running compose stack.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
INDEX="$ROOT/index"
PDF="$INDEX/.edition.pdf"

rm -f "$INDEX"/edition-page-*.jpg "$PDF"

docker compose -f "$ROOT/compose.yml" run --no-deps --rm \
  -v "$ROOT:/work" \
  -w /work \
  agent \
  /opt/hermes/.venv/bin/python3 pt-edition/scripts/render_edition.py \
    index/edition.json --pdf index/.edition.pdf --config /dev/null

pdftoppm -jpeg -r 96 -scale-to-x 783 -scale-to-y 1024 \
  -jpegopt quality=85 "$PDF" "$INDEX/edition-page"
rm -f "$PDF"
echo "wrote $INDEX/edition-page-*.jpg"
