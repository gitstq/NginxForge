#!/usr/bin/env bash
#
# Build NginxForge distributions (sdist + wheel) and smoke-test them.
#
#   ./scripts/build.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> 1/5 clean previous artefacts"
rm -rf dist build ./*.egg-info

echo "==> 2/5 run the test suite"
python3 -m unittest discover -s tests -p "test_*.py"

echo "==> 3/5 build sdist + wheel"
python3 -m build

echo "==> 4/5 twine check"
python3 -m twine check dist/*

echo "==> 5/5 smoke test the wheel in a throwaway venv"
TMP_VENV="$(mktemp -d)"
python3 -m venv "$TMP_VENV"
# shellcheck disable=SC1091
source "$TMP_VENV/bin/activate"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet dist/*.whl
nginxforge --version
nginxforge rules | head -3
nginxforge gen --template reverse-proxy --domain smoke.test --upstream 127.0.0.1:8080 --audit
deactivate
rm -rf "$TMP_VENV"

echo
echo "✔ build complete — artefacts in ./dist"
ls -1 dist
