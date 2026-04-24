#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: $0 <branch> [remote]" >&2
  exit 1
fi

branch="$1"
remote="${2:-origin}"
repo_root="${AIC_REPO_ROOT:-$(git rev-parse --show-toplevel)}"
worktree_root="${AIC_WORKTREE_ROOT:-${repo_root}/.worktrees}"
user_name="${AIC_REMOTE_USER:-$(id -un)}"
branch_slug="${branch//\//-}"
target_dir="${worktree_root}/${user_name}/${branch_slug}"

mkdir -p "${worktree_root}/${user_name}"

git -C "${repo_root}" fetch "${remote}" "${branch}"

if [[ -e "${target_dir}" ]]; then
  git -C "${target_dir}" fetch "${remote}" "${branch}"
  git -C "${target_dir}" checkout "${branch}" >/dev/null 2>&1 || true
  git -C "${target_dir}" pull --ff-only "${remote}" "${branch}" >/dev/null
else
  git -C "${repo_root}" worktree add "${target_dir}" -B "${branch}" "${remote}/${branch}" >/dev/null
fi

printf '%s\n' "${target_dir}"
