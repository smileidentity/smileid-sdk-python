#!/usr/bin/env bash
# Runs the release guards for a version tag:
#
# - the tag matches the version in pyproject.toml
# - CHANGELOG.md has a dated "## [X.Y.Z] - YYYY-MM-DD" heading for it
# - the major version matches the PRs labelled `breaking` that the release
#   ships (check-release-breaking.sh)
#
# Usage: scripts/check-release.sh <tag> [<commit>]
#
# release.yml runs it on the pushed tag. Pull requests labelled `release` run
# it before the tag exists, passing the commit the tag will point to. A pushed
# tag can't be moved or reused, so in that case the tag must not exist yet.
#
# Reads pyproject.toml and CHANGELOG.md from the working tree, so check out
# <commit> (or the tag) first. Needs Python 3.11 or later, full history and
# tags, and what check-release-breaking.sh needs.

set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "usage: $0 <tag> [<commit>]" >&2
  exit 2
fi
tag="$1"
here="$(cd "$(dirname "$0")" && pwd)"
version="${tag#v}"
failed=0

if [ "$#" -eq 2 ] && git rev-parse --quiet --verify "refs/tags/$tag" >/dev/null; then
  echo "::error::Tag $tag already exists. Bump the version in pyproject.toml and CHANGELOG.md."
  failed=1
fi

pkg_version=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
if [ "$version" != "$pkg_version" ]; then
  echo "::error::Tag $tag does not match pyproject.toml version $pkg_version"
  failed=1
fi

if ! grep -qE "^## \[${version//./\\.}\] - [0-9]{4}-[0-9]{2}-[0-9]{2}" CHANGELOG.md; then
  echo "::error::CHANGELOG.md has no dated '## [$version] - YYYY-MM-DD' heading for tag $tag"
  failed=1
fi

if ! "$here/check-release-breaking.sh" "$@"; then
  failed=1
fi

if [ "$failed" -ne 0 ]; then
  exit 1
fi
echo "$tag passes the release checks."
