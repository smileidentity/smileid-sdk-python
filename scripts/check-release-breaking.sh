#!/usr/bin/env bash
# Ties a release's major version to the PRs labelled `breaking` that it ships.
#
# Usage: scripts/check-release-breaking.sh <tag>
#
# A release ships the commits in <previous stable tag>..<tag>. If any PR
# labelled `breaking` was merged within that range, the major version must
# increase. If the major version increases, at least one such PR must exist,
# except for the move from 0.x to 1.0.0, which stabilises the API.
#
# The same rule applies to pre-release tags such as v14.0.0rc1: the previous
# stable tag is the comparison point, so a pre-release of a major version
# needs a merged `breaking` PR, and one of a minor or patch version must not
# ship one.
#
# Needs GITHUB_REPOSITORY and a token for `gh`. For tests, set
# BREAKING_PRS_FILE to a file of "<merge commit sha><TAB>#<n> <title>" lines
# to use instead of asking GitHub.

set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <tag>" >&2
  exit 2
fi
tag="$1"
here="$(cd "$(dirname "$0")" && pwd)"

prev=""
if git rev-parse --quiet --verify "$tag^{commit}^" >/dev/null; then
  prev=$("$here/previous-release-tag.sh" "$tag^")
fi
if [ -z "$prev" ]; then
  echo "::notice::No previous stable v* tag before $tag, so there is nothing to compare against."
  exit 0
fi
echo "Previous release: $prev"

if [ -n "${BREAKING_PRS_FILE:-}" ]; then
  candidates=$(cat "$BREAKING_PRS_FILE")
else
  candidates=$(gh pr list --repo "$GITHUB_REPOSITORY" --state merged --label breaking \
    --limit 1000 --json number,title,mergeCommit \
    --jq '.[] | "\(.mergeCommit.oid // "")\t#\(.number) \(.title)"')
fi

# Keep only PRs whose merge commit this release ships: reachable from the tag
# but not from the previous release.
breaking=""
while IFS=$'\t' read -r oid label; do
  [ -n "$oid" ] || continue
  if git merge-base --is-ancestor "$oid" "$tag" 2>/dev/null &&
    ! git merge-base --is-ancestor "$oid" "$prev" 2>/dev/null; then
    breaking="${breaking:+$breaking$'\n'}$label"
  fi
done <<EOF
$candidates
EOF

prev_major="${prev#v}"
prev_major="${prev_major%%.*}"
new_major="${tag#v}"
new_major="${new_major%%.*}"

if [ -n "$breaking" ]; then
  echo "PRs labelled 'breaking' in $prev..$tag:"
  echo "$breaking"
fi
if [ -n "$breaking" ] && [ "$new_major" -le "$prev_major" ]; then
  echo "::error::$tag ships PRs labelled 'breaking' but does not increase the major version from $prev."
  exit 1
fi
if [ -z "$breaking" ] && [ "$new_major" -gt "$prev_major" ] &&
  ! { [ "$prev_major" -eq 0 ] && [ "$new_major" -eq 1 ]; }; then
  echo "::error::$tag increases the major version, but ships no PR labelled 'breaking' since $prev."
  exit 1
fi
echo "The major version of $tag matches the breaking changes it ships."
