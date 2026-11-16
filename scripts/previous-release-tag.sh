#!/usr/bin/env bash
# Prints the newest stable release tag (vX.Y.Z, no pre-release suffix) that is
# reachable from a commit. Prints nothing if there is none.
#
# Usage: scripts/previous-release-tag.sh <ref>
#
# Pass "<tag>^" to find the release before <tag>. Only ancestors count, so a
# backport tag such as v11.4.1 finds v11.4.0, not a newer v12 tag.

set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <ref>" >&2
  exit 2
fi

# Collect the list first, so no pipe can be cut short.
tags=$(git tag --merged "$1" --list 'v*' --sort=-v:refname)
while IFS= read -r tag; do
  if [[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "$tag"
    exit 0
  fi
done <<EOF
$tags
EOF
