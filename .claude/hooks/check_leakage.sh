#!/usr/bin/env bash
# PostToolUse hook: re-run the leakage tests whenever src/ changes.
#
# This runs AFTER the edit has landed, so it cannot prevent the write. What
# exit 2 does is send stderr back to Claude as a system message, so the
# failure is in front of the agent immediately and it cannot carry on as if
# the edit were fine. To make "done" itself conditional on green tests, add
# a Stop hook that runs `make test` and exits 2 on failure (check
# stop_hook_active in the payload to avoid looping).
set -uo pipefail

# Windows: Claude Code sends backslash paths, so normalise them to '/'
# before matching, and use the project's venv Python (the system one may
# not have pytest). Without this the hook silently exited 0 on Windows.
proj="${CLAUDE_PROJECT_DIR:-.}"
proj="${proj//\\//}"
py=python
for cand in "$proj/.venv/Scripts/python.exe" "$proj/.venv/bin/python"; do
  if [ -x "$cand" ]; then py="$cand"; break; fi
done

payload=$(cat)
path=$(printf '%s' "$payload" | "$py" -c \
  'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))')
path="${path//\\//}"

case "$path" in
  *src/*.py) ;;
  *) exit 0 ;;
esac

cd "$proj" || exit 0
if ! out=$("$py" -m pytest tests/test_leakage.py -q 2>&1); then
  echo "Leakage tests failed after editing $path:" >&2
  echo "$out" | tail -20 >&2
  exit 2
fi
exit 0
