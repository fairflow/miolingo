#!/bin/sh
# Run the Neolingo host from this folder:  ./run.sh [--port 8810]
cd "$(dirname "$0")" || exit 1
exec "${NEOLINGO_PYTHON:-$HOME/Software/working/miolingo/venv/bin/python}" -m host.serve --preload "$@"
