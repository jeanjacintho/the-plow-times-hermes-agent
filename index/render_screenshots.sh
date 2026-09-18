#!/bin/sh
# Rasterize index/edition.json into the Agent Index listing JPGs.
# Prefers a local WeasyPrint; otherwise uses this repo's agent image.
# Needs poppler's pdftoppm on the host.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
INDEX="$ROOT/index"
PDF="$INDEX/.edition.pdf"
IMAGE="${PT_SCREENSHOT_IMAGE:-the-plow-times-hermes-agent-agent:latest}"

rm -f "$INDEX"/edition-page-*.jpg "$PDF"

render_pdf() {
  if python3 -c "from weasyprint import HTML" >/dev/null 2>&1; then
    python3 "$ROOT/pt-edition/scripts/render_edition.py" \
      "$INDEX/edition.json" --pdf "$PDF" --config /dev/null
    return
  fi
  docker run --rm \
    -v "$ROOT:/work" \
    -w /work \
    "$IMAGE" \
    /opt/hermes/.venv/bin/python3 pt-edition/scripts/render_edition.py \
      index/edition.json --pdf index/.edition.pdf --config /dev/null
}

export DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}"
export DYLD_LIBRARY_PATH="${DYLD_LIBRARY_PATH:-/opt/homebrew/lib}"
render_pdf
pdftoppm -jpeg -r 96 -jpegopt quality=85 "$PDF" "$INDEX/edition-page"
rm -f "$PDF"

found=0
for src in "$INDEX"/edition-page-*.jpg; do
  [ -f "$src" ]
  sips -z 1024 783 "$src" >/dev/null
  found=1
done
[ "$found" = 1 ]
echo "wrote $INDEX/edition-page-*.jpg"
