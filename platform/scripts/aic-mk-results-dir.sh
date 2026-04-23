#!/usr/bin/env bash
set -euo pipefail

label="${1:-run}"
root="${AIC_RESULTS_ROOT:-$HOME/aic_results}"
user_name="${AIC_RUN_USER:-$(id -un)}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"

if git_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  branch="$(git -C "${git_root}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo detached)"
  sha="$(git -C "${git_root}" rev-parse --short HEAD 2>/dev/null || echo nosha)"
else
  branch="norepo"
  sha="nosha"
fi

branch_slug="${branch//\//-}"
dir="${root}/${user_name}/${label}/${timestamp}_${branch_slug}_${sha}"

mkdir -p "${dir}"
printf '%s\n' "${dir}"
