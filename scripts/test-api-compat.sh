#!/usr/bin/env bash
# Tests check-api-compat.sh on a release pull request: a minor version bump
# changes __version__, which must not count as a break of the public API.
#
# Usage: scripts/test-api-compat.sh
#
# Needs griffe, the full git history and at least one stable v* tag.

set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
tree="$work/tree"
cleanup() {
  git -C "$root" worktree remove --force "$tree" >/dev/null 2>&1 || true
  rm -rf "$work"
}
trap cleanup EXIT

if [ -z "$("$here/previous-release-tag.sh" HEAD)" ]; then
  echo "No stable release tag yet, so there is nothing to test against."
  exit 0
fi

base=$(git -C "$root" rev-parse HEAD)
git -C "$root" worktree add --quiet --detach "$tree" "$base"
cd "$tree"
# bump-version.sh needs something to release.
awk '{ print } /^## \[Unreleased\]/ { print ""; print "### Fixed"; print ""; print "- Test entry." }' \
  CHANGELOG.md >"$work/CHANGELOG.md" && mv "$work/CHANGELOG.md" CHANGELOG.md
RELEASE_DATE=2000-01-01 scripts/bump-version.sh minor >/dev/null
git -c user.name=test -c user.email=test@example.com commit -q -am "Release (test)"

if out=$(scripts/check-api-compat.sh "$base" 2>&1); then
  echo "api-compat tests passed"
else
  printf '%s\n' "$out" >&2
  echo "FAIL: a minor release bump was reported as a break" >&2
  exit 1
fi
