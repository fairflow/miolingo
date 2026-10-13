#!/bin/sh
# Update the page from the locus repository: copies index.html and CHANGES from docs/neolingo-page/ and writes
# page/SOURCE (the locus short hash).  Restart is not needed for the page; /version reads CHANGES and SOURCE each time.
set -e
LOCUS="${NEOLINGO_LOCUS:-/Users/matthew/Lean/locus}"
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$LOCUS/docs/neolingo-page"
[ -f "$SRC/index.html" ] && [ -f "$SRC/CHANGES" ] || { echo "no page in $SRC" >&2; exit 1; }
if [ -n "$(git -C "$LOCUS" status --porcelain -- docs/neolingo-page)" ]; then
  echo "warning: $SRC has uncommitted changes; SOURCE names the last commit, not these files" >&2
fi
cp "$SRC/index.html" "$HERE/page/index.html"
cp "$SRC/CHANGES" "$HERE/page/CHANGES"
git -C "$LOCUS" rev-parse --short HEAD > "$HERE/page/SOURCE"
echo "page $(head -1 "$HERE/page/CHANGES" | cut -f1) from locus $(cat "$HERE/page/SOURCE")"
git -C "$HERE" status --short -- page
