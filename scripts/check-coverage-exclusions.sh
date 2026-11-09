#!/usr/bin/env bash
# Blocks new coverage exclusions.
#
# Usage: scripts/check-coverage-exclusions.sh <base-ref>
#
# Scans the lines added in `git diff <base-ref>...HEAD` for markers that hide
# code from coverage: inline exclusion comments for every SDK language, new
# coverage.py exclusion settings, `@Generated` on code outside a generated/
# directory, and new JaCoCo excludes. Prints each hit as file:line and exits 1
# if there are any.

set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <base-ref>" >&2
  exit 2
fi
base="$1"
self="scripts/check-coverage-exclusions.sh"

git diff --unified=0 --no-color --no-ext-diff "$base...HEAD" | awk -v self="$self" '
  # Inline markers. Patterns are built from pieces so this file does not
  # flag itself when someone greps the repo.
  BEGIN {
    inline = "(no" "cov|pragma: no (cover|branch)|c8 " "ignore|istanbul " "ignore|@codeCoverage" "Ignore|#\\[coverage\\(off\\)\\])"
  }
  /^\+\+\+ / {
    file = $0
    sub(/^\+\+\+ (b\/)?/, "", file)
    next
  }
  /^@@ / {
    # @@ -a,b +c,d @@: c is the first new line number.
    spec = $3
    sub(/^\+/, "", spec)
    split(spec, parts, ",")
    line = parts[1] + 0
    next
  }
  /^\+/ {
    text = substr($0, 2)
    reason = ""
    if (file == self || file == "/dev/null") {
      # The checker itself names every marker.
    } else if (text ~ inline) {
      reason = "coverage exclusion comment"
    } else if (text ~ /@Generated/ && file !~ /(^|\/)generated\//) {
      reason = "@Generated outside generated/"
    } else if (file ~ /(^|\/)(pom\.xml|build\.gradle(\.kts)?)$/ && text ~ /<excludes?>|excludes?[[:space:]]*(\+?=|\()/) {
      reason = "JaCoCo exclude"
    } else if (file ~ /(^|\/)(pyproject\.toml|setup\.cfg|\.coveragerc|tox\.ini)$/ && text ~ /^[[:space:]]*(exclude_lines|exclude_also|omit|partial_branches)[[:space:]]*=/) {
      reason = "coverage.py exclusion setting"
    }
    if (reason != "") {
      printf "%s:%d: %s: %s\n", file, line, reason, text
      hits++
    }
    line++
  }
  END {
    if (hits) {
      printf "\n%d new coverage exclusion(s) found. Write tests instead.\n", hits
      exit 1
    }
    print "No new coverage exclusions."
  }
'
