#!/bin/sh
# Run the Neolingo host from this folder:  ./run.sh [--port 8810]
cd "$(dirname "$0")" || exit 1
# The voice per language: British English by the Mac (Serena (Premium) where installed), the rest by Google.
export NEOLINGO_TTS="${NEOLINGO_TTS:-en-gb=say}"
exec "${NEOLINGO_PYTHON:-$HOME/Software/working/miolingo/venv/bin/python}" -m host.serve --preload "$@"
