#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Fails if any source file lacks "SPDX-License-Identifier: Apache-2.0" in its first 3 lines
# (Constitution Art. XVII.A.4). Runs on tracked + untracked (not ignored) files.
set -eu
cd "$(dirname "$0")/.."

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  files=$(git ls-files -co --exclude-standard)
else
  files=$(find . -type f -not -path './.git/*' -not -path './node_modules/*' -not -path './.venv/*' | sed 's|^\./||')
fi

files=$(printf '%s\n' "$files" | grep -E '(\.(py|ts|tsx|js|css|yml|yaml|sh)$|(^|/)Dockerfile$|(^|/)Makefile$)' || true)

missing=0
count=0
for f in $files; do
  case "$f" in
    web/dist/*|node_modules/*|.venv/*|*/node_modules/*) continue ;;
  esac
  [ -f "$f" ] || continue
  count=$((count + 1))
  if ! head -n 3 "$f" | grep -q 'SPDX-License-Identifier: Apache-2.0'; then
    echo "missing SPDX header: $f"
    missing=$((missing + 1))
  fi
done

if [ "$missing" -gt 0 ]; then
  echo "spdx-check: FAIL — $missing of $count file(s) missing the header"
  exit 1
fi
echo "spdx-check: OK ($count files)"
