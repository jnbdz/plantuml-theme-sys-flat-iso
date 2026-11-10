#!/usr/bin/env bash
# Render every example in four variants: flat-light, flat-dark, iso-light, iso-dark.
# Needs podman (or docker) and python3; rsvg-convert for the PNG previews.
set -euo pipefail
cd "$(dirname "$0")/.."
IMAGE=${PLANTUML_IMAGE:-docker.io/plantuml/plantuml:1.2026.9}
RUNNER=${CONTAINER_RUNNER:-podman}
FONTS=${FONTS_DIR:-/usr/share/fonts/truetype/noto}
rm -rf build && mkdir -p build/flat-light build/flat-dark && cp -r themes build/themes
cp examples/*.puml build/flat-light/
for f in examples/*.puml; do
  sed 's/!theme sys-flat from/!theme sys-flat-dark from/' "$f" > "build/flat-dark/$(basename "$f")"
done
for variant in flat-light flat-dark; do
  "$RUNNER" run --rm --userns keep-id -v "$PWD:/work:Z" -v "$FONTS:/usr/share/fonts/noto:ro,Z" "$IMAGE" \
    -tsvg -o "/work/build/$variant/out" "/work/build/$variant/"*.puml
done
mkdir -p gallery/flat-light gallery/flat-dark gallery/iso-light gallery/iso-dark
for variant in flat-light flat-dark; do
  for s in build/$variant/out/*.svg; do
    n=$(basename "$s" .svg)
    cp "$s" "gallery/$variant/$n.svg"
    iso=${variant/flat/iso}
    python3 -I tools/iso.py --variant "${variant#flat-}" "$s" "gallery/$iso/$n.svg"
  done
done
if command -v rsvg-convert >/dev/null; then
  for d in gallery/*/; do
    bg=white; case "$d" in *dark*) bg='#121212';; esac
    for s in "$d"*.svg; do rsvg-convert -w 1400 -b "$bg" "$s" -o "${s%.svg}.png"; done
  done
fi
echo "rendered: $(ls gallery/*/*.svg | wc -l) SVG files"
