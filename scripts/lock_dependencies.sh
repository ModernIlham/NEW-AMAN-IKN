#!/usr/bin/env bash
# Regenerate both reviewed lock files; this does not install into a runtime.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uv --version)" != uv\ 0.12.23* ]]; then
  echo "Gunakan uv 0.12.23 agar format/resolusi lock konsisten." >&2
  exit 2
fi
uv pip compile backend/requirements-runtime.in --generate-hashes \
  --python-version 3.11 --index-url https://pypi.org/simple \
  --output-file backend/requirements-runtime.lock --quiet
uv pip compile backend/requirements-dev.in --generate-hashes \
  --python-version 3.11 --index-url https://pypi.org/simple \
  --output-file backend/requirements-dev.lock --quiet
