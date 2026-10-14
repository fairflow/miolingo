#!/bin/sh
# Run the Neolingo host from this folder:  ./run.sh [--port 8810]
cd "$(dirname "$0")" || exit 1
# The voice per language (the owner's choice by ear, 14 October): British English Serena (Premium), German Petra (Premium), French Google.
export NEOLINGO_TTS="${NEOLINGO_TTS:-en-gb=say,de=say}"
exec "${NEOLINGO_PYTHON:-$HOME/Software/working/miolingo/venv/bin/python}" -m host.serve --preload "$@"
