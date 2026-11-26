---
name: seed-fault
description: Break the pipeline on purpose with one described fault in src/, record which check catches it (hook stderr, make test), have a fresh no-context subagent fix it, verify the fix is an exact revert, and append the evidence to docs/SEEDED_FAULTS.md. Use when asked to seed, inject, or test a fault.
allowed-tools: Read, Grep, Glob, Edit, Agent, Bash(make test*), Bash(git diff*), Bash(git status*), Bash(python*), Bash(bash .claude/hooks/*)
---

# Working tree right now

!`git status --short src/ tests/ data/`

# Faults already recorded

!`grep -E "^## [0-9]+\." docs/SEEDED_FAULTS.md`

# Seeding a fault: $ARGUMENTS

If `$ARGUMENTS` is empty, ask which fault to seed and stop.
Use the project's `.venv` Python for every command (on Windows Git Bash,
prefix `export PATH="$PWD/.venv/Scripts:$PATH";`). Never run `make train`
or `make all` here: they rewrite `reports/metrics.json`. Never commit.

## 0. Gate

Stop and say why, without editing anything, if:

- `git status` above lists anything under `src/` or `tests/`: the exact-revert
  check in step 5 is only meaningful from a clean tree.
- the fault writes to `data/raw/`. That one is the human's to run (raw data is
  immutable and the agent is denied it); say that `load_raw()`'s `RAW_SHA256`
  check and `test_raw_file_is_unmodified` should catch it, and stop.
- the fault would edit `tests/`, `.claude/` or `Makefile`. Faults go in `src/`;
  a weakened test is not a seeded fault, it is a broken suite.

## 1. Predict, then seed

Before touching anything, write one line: the exact change, and which test
(by name) you expect to go red, or "none" if you expect the suite to miss it.
Then make the change with **one** `Edit` to a file under `src/`, so the
PostToolUse hook fires live. Note whether its exit-2 message reached you.

## 2. Capture, verbatim

Run and keep the full output of each; paste, never paraphrase:

1. `git diff src/`
2. the hook, re-run with the payload Claude Code sends, replacing PATH with
   the absolute path of the file you edited:
   `python -c "import json,sys; print(json.dumps({'tool_name': 'Edit', 'tool_input': {'file_path': sys.argv[1]}}))" "PATH" | CLAUDE_PROJECT_DIR="$PWD" bash .claude/hooks/check_leakage.sh; echo "hook exit: $?"`
3. `make test`

If the hook exited 0 **and** `make test` passed, the suite cannot see this
fault. That is the finding: skip step 3, restore the original yourself with
one `Edit`, propose (do not write) the test that would catch it, and go to
step 5.

## 3. Fix, by someone who does not know the answer

You seeded the fault, so your own fix would prove nothing. Spawn a fresh
`general-purpose` subagent with exactly this prompt, and nothing that hints
at the fault:

> `make test` is currently red in this repo. Find the cause in `src/` and fix
> it. Use the project's .venv Python. Do not edit anything under tests/,
> data/, .claude/, reports/, docs/; do not weaken or skip a test; do not run
> git commit, checkout, stash, reset or restore. You are done only when
> `make test` passes. Report: the cause in one sentence; your diff; your tool
> calls, split into reads/searches, Bash runs, edits; the final `make test`
> summary line.

"Turns" = its tool calls until green, from its report and the tool-use count.

## 4. Verify, do not trust

- `git diff src/` must be empty: the fix is an exact revert. If not, say so,
  show the diff, and restore the original yourself.
- `make test` must pass. Show the summary line.
- `git status --short data/` must be empty.

## 5. Record

Append one section to `docs/SEEDED_FAULTS.md`, numbered after the last
`## N.` heading listed above:

~~~
## N. <the fault, in a few words>

**The change:** the step 2.1 diff, in a ```diff block.
**Prediction:** your step 1 line, and whether it held.
**Hook:** exit code and stderr (step 2.2), in a ```text block.
**make test:** step 2.3, in a ```text block. If longer than ~60 lines,
paste the first failure and the full short-summary section, and say so.
**Fix:** N turns (reads / Bash / edits), the subagent's one-line cause,
exact revert yes/no, final summary line.
**What caught it:** the hook, which test, or nothing (and the proposed test).
~~~

Then report in two lines: what went red (or that nothing did), and the fix
turn count. Leave the commit to the human.
