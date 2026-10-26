#!/usr/bin/env bash
# Writes docs/tasks/<feature>/plan-pr-body.md for /feature-plan's plan PR.
# Usage: bash <plugin root>/loop/feature-plan/plan-pr-body.sh <feature> "<pull request attribution lines>"
#
# It lives outside SKILL.md because skill loading substitutes $0, $1, ... in the skill's text,
# which turned the awk's $0 into the feature name.
set -euo pipefail

feature=${1:?usage: plan-pr-body.sh <feature> "<attribution lines>"}
attribution=${2:?usage: plan-pr-body.sh <feature> "<attribution lines>"}
d=docs/tasks/$feature

{
  echo "Plan for \`$feature\`: spec \`docs/designs/$feature.md\`, decisions \`$d/DECISIONS.md\`, every planning step in \`$d/plan-log.md\`."
  echo; echo "## Order"; awk '/^## Order and dependencies/{f=1;next} /^## /{f=0} f' "$d/00-overview.md"
  echo; echo "## Evaluation"; sed -n '3,5p' "$d/EVALUATION.md"
  echo; echo "## Decisions"
  echo "$(grep -c '^### D[0-9]' "$d/DECISIONS.md") owner, $(grep -c '^### E[0-9]' "$d/DECISIONS.md") adopted amendments, $(grep -c '^### P[0-9]' "$d/DECISIONS.md") planner."
  echo; echo "## Size estimates"; echo; echo "| Task | Scout | Largest cycle | Validation |"; echo "|---|---|---|---|"
  for f in "$d"/readiness/*.md; do
    n=$(basename "$f" .md)
    # Reviewers copy the three size lines either flush or indented as a code block.
    awk -v n="$n" '
      /^## Size/ { f = 1; next }
      /^## /     { f = 0 }
      f && /^[ \t]*(Scout|Largest cycle|Validation):/ { sub(/^[ \t]*[^:]*: /, ""); a[++i] = $0 }
      END { printf "| %s | %s | %s | %s |\n", n, a[1], a[2], a[3] }
    ' "$f"
  done
  echo; echo "Merging this PR hands the feature to \`/feature-loop docs/tasks/$feature\`."
  echo; echo "$attribution"
} > "$d/plan-pr-body.md"
