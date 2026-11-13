#!/usr/bin/env bash
# Tests previous-release-tag.sh, check-release-breaking.sh and
# check-coverage-exclusions.sh against throwaway git repositories.
#
# Usage: scripts/test-release-scripts.sh

set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
failures=0

fail() {
  echo "FAIL: $*" >&2
  failures=$((failures + 1))
}

export GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@example.com
export GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=test@example.com
export GIT_CONFIG_NOSYSTEM=1 HOME="$work"

repo="$work/repo"
git init -q -b main "$repo"
mkdir -p "$repo/scripts"
cp "$here/previous-release-tag.sh" "$here/check-release-breaking.sh" \
  "$here/check-coverage-exclusions.sh" "$repo/scripts/"
cd "$repo"

commit() {
  git commit -q --allow-empty -m "$1"
  git rev-parse HEAD
}

#   main:   c0 v0.9.0 - c1 v1.0.0 - c2 (#2 breaking) - c3 v2.0.0 (#3 breaking)
#           - c4 v2.0.1, v2.1.0rc1 - c5 (#5 breaking) v2.2.0 - c6 v3.0.0
#   branch: c1 - b1 v1.0.1
git add scripts && c0=$(commit c0) && git tag v0.9.0
c1=$(commit c1) && git tag v1.0.0
c2=$(commit c2)
c3=$(commit c3) && git tag v2.0.0
commit c4 >/dev/null && git tag v2.0.1 && git tag v2.1.0rc1
c5=$(commit c5) && git tag v2.2.0
commit c6 >/dev/null && git tag v3.0.0
git checkout -q -b backport "$c1"
commit b1 >/dev/null && git tag v1.0.1
git checkout -q main

prs="$work/prs.tsv"
printf '%s\t#2 Break two\n%s\t#3 Break three\n%s\t#5 Break five\n\t#9 Unmerged\n' \
  "$c2" "$c3" "$c5" >"$prs"
export BREAKING_PRS_FILE="$prs"

expect_prev() {
  local ref="$1" want="$2" got
  got=$(scripts/previous-release-tag.sh "$ref")
  [ "$got" = "$want" ] || fail "previous-release-tag $ref: got '$got', want '$want'"
}
expect_prev "$c0^{commit}" v0.9.0
expect_prev v1.0.0^ v0.9.0
expect_prev v2.1.0rc1 v2.0.1 # skips the pre-release
expect_prev v2.0.1^ v2.0.0
expect_prev v1.0.1^ v1.0.0
expect_prev v1.0.1 v1.0.1 # the backport line never sees v2
[ -z "$(git checkout -q --orphan empty && git commit -q --allow-empty -m e &&
  scripts/previous-release-tag.sh HEAD)" ] || fail "previous-release-tag: expected nothing with no tags"
git checkout -q main

expect_release() {
  local tag="$1" want="$2" rc=0
  scripts/check-release-breaking.sh "$tag" >"$work/out" 2>&1 || rc=$?
  if [ "$want" = pass ] && [ "$rc" -ne 0 ]; then
    fail "check-release-breaking $tag: expected pass"
    cat "$work/out" >&2
  elif [ "$want" = fail ] && [ "$rc" -eq 0 ]; then
    fail "check-release-breaking $tag: expected failure"
    cat "$work/out" >&2
  fi
}
expect_release v0.9.0 pass # no previous release
expect_release v1.0.0 pass # 0.x to 1.0.0 needs no breaking PR
expect_release v2.0.0 pass # ships #2 and #3
expect_release v2.0.1 pass # #3 is the previous tag's commit, #5 merged later
expect_release v2.2.0 fail # ships #5 without a major bump
expect_release v3.0.0 fail # major bump with nothing breaking since v2.2.0
expect_release v1.0.1 pass # backport only sees its own commits

# check-coverage-exclusions.sh: an added line that starts with "++ " shows as
# "+++ " in the diff and must not be read as a new file header.
printf 'line one\n-- removed later\n' >notes.txt
git add notes.txt && commit notes >/dev/null
base=$(git rev-parse HEAD)
# Built at run time so this script doesn't itself contain an exclusion marker.
printf 'line one\n++ not-a-file.py\nx = 1  # pragma: no %s\n' cover >notes.txt
git add notes.txt && commit marker >/dev/null
out=$(scripts/check-coverage-exclusions.sh "$base" 2>&1) && fail "exclusions: expected failure"
case "$out" in
  *"notes.txt:3: coverage exclusion comment"*) ;;
  *) fail "exclusions: expected a hit at notes.txt:3, got: $out" ;;
esac
scripts/check-coverage-exclusions.sh HEAD >/dev/null || fail "exclusions: empty diff should pass"

if [ "$failures" -ne 0 ]; then
  echo "$failures release script test(s) failed" >&2
  exit 1
fi
echo "release script tests passed"
