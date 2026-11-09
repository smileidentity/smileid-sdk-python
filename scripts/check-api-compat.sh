#!/usr/bin/env bash
# Compares the public API of the working tree with the latest release.
#
# Usage: scripts/check-api-compat.sh <base-ref>
#
# The release is the newest stable vX.Y.Z tag reachable from <base-ref>. Breaks
# that <base-ref> already has were judged when they merged, so they only warn.
# Breaks this change adds fail, unless HAS_BREAKING_LABEL=true. Needs griffe.

set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <base-ref>" >&2
  exit 2
fi
base="$1"
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/.." && pwd)"

tag=$("$here/previous-release-tag.sh" "$base")
if [ -z "$tag" ]; then
  echo "::notice::No stable v* release tag yet, so there is no released API to compare against."
  exit 0
fi
echo "Comparing the public API with $tag"

# Prints breaks as "file: object: change", without the line number, so the
# two lists compare even when code moves. griffe exits 1 when it finds breaks,
# and with no breaks the filter matches nothing, so neither is an error here.
breaks() {
  local out rc=0
  out=$(cd "$root" && griffe check usesmileid --search . --against "$tag" --no-color "$@" 2>&1) || rc=$?
  local found
  found=$(printf '%s\n' "$out" | { grep -E '^[^ ]+:[0-9]+: ' || true; })
  if [ "$rc" -ne 0 ] && [ -z "$found" ]; then
    printf '%s\n' "$out" >&2
    echo "::error::griffe failed to load the package"
    exit 1
  fi
  [ -n "$found" ] || return 0
  printf '%s\n' "$found" | sed -E 's/^([^ ]+):[0-9]+: /\1: /' | sort -u
}

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
breaks >"$work/head"
breaks --base-ref "$base" >"$work/base"
comm -12 "$work/base" "$work/head" >"$work/existing"
comm -13 "$work/base" "$work/head" >"$work/new"

if [ -s "$work/existing" ]; then
  echo "::warning::$base already breaks the public API of $tag. The next release needs a major version."
  sed 's/^/  /' "$work/existing"
fi
if [ ! -s "$work/new" ]; then
  echo "This change does not break the public API of $tag."
  exit 0
fi

echo "This change breaks the public API of $tag:"
level=error
[ "${HAS_BREAKING_LABEL:-false}" = "true" ] && level=warning
while IFS= read -r line; do
  echo "::$level::$line"
done <"$work/new"
if [ "$level" = "error" ]; then
  echo "Add the 'breaking' label if this break is intended. The release then needs a major version."
  exit 1
fi
