#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
PYTHON=${VIVA_TEST_PYTHON:-.venv/bin/python}
if [ ! -x "$PYTHON" ]; then
  printf '%s\n' 'Create .venv and install backend/requirements.txt first.' >&2
  exit 1
fi
"$PYTHON" -m pytest backend/tests -q
(cd frontend && npm run typecheck && npm test && npm run build)
git diff --check
