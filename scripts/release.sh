#!/usr/bin/env bash
#
# Tag, build and publish a release.
#
#   ./scripts/release.sh 1.0.0            # build + tag only
#   ./scripts/release.sh 1.0.0 --upload   # also upload to PyPI
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="${1:-}"
UPLOAD="no"
for arg in "$@"; do
    [ "$arg" = "--upload" ] && UPLOAD="yes"
done

if [ -z "$VERSION" ]; then
    echo "usage: $0 <version> [--upload]" >&2
    exit 2
fi

# Strip a leading 'v' so both `1.2.0` and `v1.2.0` work.
VERSION="${VERSION#v}"

echo "==> checking that the tree is clean"
if [ -n "$(git status --porcelain)" ]; then
    echo "✖ working tree is dirty - commit or stash first" >&2
    git status --short
    exit 1
fi

echo "==> bumping version to $VERSION"
# pyproject.toml
python3 - "$VERSION" <<'PY'
import re, sys, pathlib
version = sys.argv[1]
p = pathlib.Path("pyproject.toml")
text = p.read_text(encoding="utf-8")
text, n = re.subn(r'^version\s*=\s*"[^"]*"', f'version = "{version}"', text,
                  count=1, flags=re.M)
assert n == 1, "could not find the version field in pyproject.toml"
p.write_text(text, encoding="utf-8")

p = pathlib.Path("nginxforge/__init__.py")
text = p.read_text(encoding="utf-8")
text, n = re.subn(r'^__version__\s*=\s*"[^"]*"', f'__version__ = "{version}"', text,
                  count=1, flags=re.M)
assert n == 1, "could not find __version__ in nginxforge/__init__.py"
p.write_text(text, encoding="utf-8")
print("   pyproject.toml + nginxforge/__init__.py updated")
PY

echo "==> running the test suite"
python3 -m unittest discover -s tests -p "test_*.py"

echo "==> building"
./scripts/build.sh

echo "==> committing the version bump"
git add pyproject.toml nginxforge/__init__.py
git commit -m "chore(release): bump version to v$VERSION"

echo "==> tagging v$VERSION"
git tag -a "v$VERSION" -m "Release v$VERSION"

if [ "$UPLOAD" = "yes" ]; then
    echo "==> uploading to PyPI"
    python3 -m twine upload dist/*
else
    echo "==> skipping upload (pass --upload to publish)"
    echo "    python3 -m twine upload dist/*"
fi

echo "==> pushing"
git push origin HEAD --tags

echo
echo "✔ release v$VERSION ready"
