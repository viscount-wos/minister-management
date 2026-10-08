#!/usr/bin/env bash
# Bootstrap (idempotent) and run the smoke suite. Extra args go to pytest.
#   e2e/run.sh                         # against http://127.0.0.1:8091
#   BASE_URL=http://127.0.0.1:8092 e2e/run.sh -k i18n --headed
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
.venv/bin/python -m playwright install chromium >/dev/null
exec .venv/bin/python -m pytest "$@"
