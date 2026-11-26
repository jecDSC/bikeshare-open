# Decisions

One line per methodological decision: what you chose, why, and what it changed.
Agents append here via the `/new-feature` skill; you append here by hand.

- Exclude `casual`, `registered`: they sum to `cnt` exactly. Leaky model R^2 1.000 -> honest ridge 0.583.
- Exclude `cnt_2d_bfr`: a shipped 2-day lag we cannot test the alignment of. Build our own lags instead.
- Exclude `instant`, `yr`, `days_since_2011`: time indexes let a tree predict a flat constant past 2011 and a linear model extrapolate a trend we have no grounds for.
- Split 2011 / H1 2012 / H2 2012 by date. Test set touched once, after all feature work.
- Report mean and persistence baselines with every score. Persistence (test R^2 0.510, MAE 840) is within 0.07 R^2 of ridge and beats it on MAE; that caveat goes in the report.
- 2026-11-25 · Run on Python 3.14, not 3.15: pinned pandas 3.0.5 has no 3.15 wheel and fails to build. All pins kept unchanged; `make all` reproduces the lesson's metrics to the printed digit.
- 2026-11-25 · Fixed `.claude/hooks/check_leakage.sh` for Windows: it matched only `*src/*.py`, but Claude Code sends backslash paths, so the hook exited 0 without running a test on every edit. Now normalises `\` to `/` and uses the project `.venv` Python (the system Python has no pytest). Verified three ways: src edit + passing tests -> exit 0 after running pytest; non-src edit -> exit 0 immediately; src edit with `casual` forced into `feature_columns` -> exit 2 with the failing assertion on stderr. Added `.gitattributes` so `*.sh` stays LF (CRLF breaks bash).
- 2026-11-25 · Removed `reports/` and `audit.jsonl` from `.gitignore` so `reports/metrics.json` and `reports/audit.jsonl` are tracked. `reports/metrics_starter.json` is the untouched starter's output, kept as the "before" row source.
- 2026-11-25 · Added the venv to PATH at the start of each Bash command. No restarts, no change to graded files, and the grader's plain `make all` isn't affected.