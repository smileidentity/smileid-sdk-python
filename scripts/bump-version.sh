#!/usr/bin/env bash
# Bumps the SDK version and cuts a CHANGELOG release section.
#
# Usage: scripts/bump-version.sh <major|minor|patch>
#
# Updates the version in pyproject.toml (which release.yml checks the tag
# against) and usesmileid/_version.py, then moves the CHANGELOG.md
# `## [Unreleased]` section under a new `## [x.y.z] - YYYY-MM-DD` heading,
# leaving an empty Unreleased section. Prints the new version.
#
# Every check runs before any file is written, so a failure leaves the tree
# untouched. Set RELEASE_DATE=YYYY-MM-DD to override today's (UTC) date.

set -euo pipefail

die() {
  echo "bump-version: $*" >&2
  exit 1
}

[ "$#" -eq 1 ] || die "usage: $0 <major|minor|patch>"
part="$1"
case "$part" in
  major | minor | patch) ;;
  *) die "unknown part '$part'; expected major, minor or patch" ;;
esac

root="$(cd "$(dirname "$0")/.." && pwd)"
pyproject="$root/pyproject.toml"
version_py="$root/usesmileid/_version.py"
changelog="$root/CHANGELOG.md"
for f in "$pyproject" "$version_py" "$changelog"; do
  [ -f "$f" ] || die "missing $f"
done

semver='[0-9]+\.[0-9]+\.[0-9]+'

count=$(grep -cE "^version = \"$semver\"$" "$pyproject" || true)
[ "$count" -eq 1 ] || die "expected one 'version = \"x.y.z\"' line in pyproject.toml, found $count"
current=$(sed -nE "s/^version = \"($semver)\"$/\\1/p" "$pyproject")

count=$(grep -cE "^__version__ = \"$semver\"$" "$version_py" || true)
[ "$count" -eq 1 ] || die "expected one '__version__ = \"x.y.z\"' line in _version.py, found $count"
module_version=$(sed -nE "s/^__version__ = \"($semver)\"$/\\1/p" "$version_py")
[ "$current" = "$module_version" ] ||
  die "pyproject.toml ($current) and _version.py ($module_version) disagree"

IFS=. read -r major minor patch <<EOF
$current
EOF
case "$part" in
  major) next="$((major + 1)).0.0" ;;
  minor) next="$major.$((minor + 1)).0" ;;
  patch) next="$major.$minor.$((patch + 1))" ;;
esac

count=$(grep -cxF '## [Unreleased]' "$changelog" || true)
[ "$count" -eq 1 ] || die "expected one '## [Unreleased]' heading in CHANGELOG.md, found $count"
if grep -qF "## [$next]" "$changelog"; then
  die "CHANGELOG.md already has a '## [$next]' section"
fi

# Lines between the Unreleased heading and the next `## ` heading or the link
# reference block. Anything non-blank there is unreleased content.
unreleased=$(awk '
  $0 == "## [Unreleased]" { inside = 1; next }
  inside && (/^## / || /^\[[^]]+\]: /) { exit }
  inside && NF { print }
' "$changelog")
[ -n "$unreleased" ] || die "the Unreleased section in CHANGELOG.md is empty; nothing to release"

release_date="${RELEASE_DATE:-$(date -u +%Y-%m-%d)}"
echo "$release_date" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' ||
  die "RELEASE_DATE must be YYYY-MM-DD, got '$release_date'"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

sed -E "s/^version = \"$semver\"$/version = \"$next\"/" "$pyproject" >"$tmp/pyproject.toml"
sed -E "s/^__version__ = \"$semver\"$/__version__ = \"$next\"/" "$version_py" >"$tmp/_version.py"

# Also move the compare links when they follow Keep a Changelog's shape:
#   [Unreleased]: <repo>/compare/vOLD...HEAD
# becomes
#   [Unreleased]: <repo>/compare/vNEW...HEAD
#   [NEW]: <repo>/compare/vOLD...vNEW
awk -v next_version="$next" -v release_date="$release_date" '
  $0 == "## [Unreleased]" {
    print
    print ""
    print "## [" next_version "] - " release_date
    next
  }
  /^\[Unreleased\]: .*\/compare\/v[^.]+\.[^.]+\.[^.]+\.\.\.HEAD$/ {
    base = $0
    sub(/^\[Unreleased\]: /, "", base)
    sub(/\/compare\/.*$/, "", base)
    old = $0
    sub(/^.*\/compare\//, "", old)
    sub(/\.\.\.HEAD$/, "", old)
    print "[Unreleased]: " base "/compare/v" next_version "...HEAD"
    print "[" next_version "]: " base "/compare/" old "...v" next_version
    next
  }
  { print }
' "$changelog" >"$tmp/CHANGELOG.md"

cp "$tmp/pyproject.toml" "$pyproject"
cp "$tmp/_version.py" "$version_py"
cp "$tmp/CHANGELOG.md" "$changelog"

echo "$next"
