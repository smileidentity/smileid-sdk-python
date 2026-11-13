#!/usr/bin/env bash
# Tests scripts/bump-version.sh against throwaway copies of the version files.
#
# Usage: scripts/test-bump-version.sh

set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
script="$here/bump-version.sh"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
failures=0

fail() {
  echo "FAIL: $*" >&2
  failures=$((failures + 1))
}

# Builds a fixture repo at $work/<name> with version 1.2.3.
fixture() {
  local dir="$work/$1"
  mkdir -p "$dir/scripts" "$dir/usesmileid"
  cp "$script" "$dir/scripts/bump-version.sh"
  cat >"$dir/pyproject.toml" <<'EOF'
[project]
name = "usesmileid"
version = "1.2.3"
EOF
  cat >"$dir/usesmileid/_version.py" <<'EOF'
"""Single source of truth for the package version."""

__version__ = "1.2.3"
EOF
  cat >"$dir/CHANGELOG.md" <<'EOF'
# Changelog

## [Unreleased]

### Added

- A new thing.

## [1.2.3] - 2026-01-01

### Fixed

- An old thing.

[Unreleased]: https://github.com/smileidentity/smileid-sdk-python/compare/v1.2.3...HEAD
[1.2.3]: https://github.com/smileidentity/smileid-sdk-python/compare/v1.2.2...v1.2.3
EOF
  echo "$dir"
}

expect_version() {
  local part="$1" want="$2" dir got
  dir="$(fixture "$part")"
  got="$(RELEASE_DATE=2026-02-03 "$dir/scripts/bump-version.sh" "$part")" ||
    { fail "$part: script exited non-zero"; return; }
  [ "$got" = "$want" ] || fail "$part: printed '$got', want '$want'"
  grep -qx "version = \"$want\"" "$dir/pyproject.toml" || fail "$part: pyproject.toml not updated"
  grep -qx "__version__ = \"$want\"" "$dir/usesmileid/_version.py" ||
    fail "$part: _version.py not updated"
}

expect_version major 2.0.0
expect_version minor 1.3.0
expect_version patch 1.2.4

# The changelog is cut under a dated heading with an empty Unreleased section.
dir="$(fixture changelog)"
RELEASE_DATE=2026-02-03 "$dir/scripts/bump-version.sh" minor >/dev/null
expected="$work/expected-changelog.md"
cat >"$expected" <<'EOF'
# Changelog

## [Unreleased]

## [1.3.0] - 2026-02-03

### Added

- A new thing.

## [1.2.3] - 2026-01-01

### Fixed

- An old thing.

[Unreleased]: https://github.com/smileidentity/smileid-sdk-python/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/smileidentity/smileid-sdk-python/compare/v1.2.3...v1.3.0
[1.2.3]: https://github.com/smileidentity/smileid-sdk-python/compare/v1.2.2...v1.2.3
EOF
diff -u "$expected" "$dir/CHANGELOG.md" || fail "changelog: unexpected output"

# Running it again has nothing unreleased, so it must fail and change nothing.
cp -R "$dir" "$work/changelog-before"
if RELEASE_DATE=2026-02-03 "$dir/scripts/bump-version.sh" minor >/dev/null 2>&1; then
  fail "second run: expected failure with an empty Unreleased section"
fi
diff -r "$work/changelog-before" "$dir" >/dev/null || fail "second run: files changed on failure"

# Bad input and unexpected file shapes fail without touching anything.
expect_failure() {
  local name="$1" part="$2" mutate="$3" dir
  dir="$(fixture "$name")"
  (cd "$dir" && eval "$mutate")
  cp -R "$dir" "$work/$name-before"
  if "$dir/scripts/bump-version.sh" "$part" >/dev/null 2>&1; then
    fail "$name: expected failure"
  fi
  diff -r "$work/$name-before" "$dir" >/dev/null || fail "$name: files changed on failure"
}

expect_failure bad-part huge ':'
expect_failure empty-part '' ':'
expect_failure mismatch minor "sed 's/1.2.3/9.9.9/' usesmileid/_version.py >v && mv v usesmileid/_version.py"
expect_failure no-unreleased minor "grep -v '^## \\[Unreleased\\]' CHANGELOG.md >c && mv c CHANGELOG.md"
expect_failure already-cut patch "printf '## [1.2.4] - 2026-01-02\n' >>CHANGELOG.md"

if [ "$failures" -ne 0 ]; then
  echo "$failures bump-version test(s) failed" >&2
  exit 1
fi
echo "bump-version tests passed"
