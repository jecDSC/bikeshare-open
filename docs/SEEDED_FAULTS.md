# Seeded faults

Exercise 2: break the pipeline on purpose and record which check goes red.
Every block below is real output, pasted verbatim from the run, not a
description of it. Environment: Windows 11, Git Bash, Python 3.14 venv,
agent Claude Opus 5.5 in Claude Code (see REPORT.md, Attribution).

**Method, the same for every fault.**

1. The agent seeds the fault with an `Edit` on `src/`, so the PostToolUse
   hook (`.claude/hooks/check_leakage.sh`, runs `tests/test_leakage.py`) fires live.
2. The hook's stderr is captured byte-for-byte by re-running the hook
   script with the same JSON payload Claude Code sends
   (`{"tool_name": "Edit", "tool_input": {"file_path": "...\\src\\features.py"}}`).
3. `make test` (the full suite) is run and captured.
4. The fix is made by a **fresh subagent with no context**: it is told only
   "`make test` is red; find the cause in `src/` and fix it; do not touch
   tests/, data/, .claude/, reports/, docs/". The agent that seeded a fault
   knows the answer, so its own turn count would be meaningless. "Turns" =
   the subagent's tool calls until `make test` was green, as it reported them.
5. `git diff src/` is checked empty after the fix: the fix is an exact revert.

Each fault is one commit containing this file's section, with the code
restored; the commit message names the fault and the fix.

## 0. The feature test, written before the feature (Exercise 1)

`tests/test_leakage.py::test_roll_28_on_named_date` and
`test_roll_28_respects_the_calendar_gap`, committed in `9ae65bd` before
`cnt_roll_28` existed. `make test` at that commit:

```text
python -m pytest tests/ -q
.........FF.....                                                         [100%]
================================== FAILURES ===================================
_________________________ test_roll_28_on_named_date __________________________

feats =         dteday  instant  season  ...  cnt_lag_1 cnt_lag_7   cnt_roll_7
0   2011-01-10     10.0  WINTER  ...      822.0...    1787.0  1530.142857
713 2012-12-31    731.0  WINTER  ...     1796.0     920.0  1531.428571

[714 rows x 28 columns]

    def test_roll_28_on_named_date(feats):
        """cnt_roll_28 on 2012-03-15 is the mean cnt of the 28 calendar days
        strictly before it: 2012-02-16 .. 2012-03-14, all present in the raw CSV.
        Hand-computed from data/raw/bike_daily.csv with the csv module: those 28
        counts sum to 115349. Including the day itself (cnt 6192) instead of
        2012-02-16 (cnt 3005) would give 4233.71, so a missing shift(1) fails."""
>       assert "cnt_roll_28" in feats.columns, "cnt_roll_28 not built"
E       AssertionError: cnt_roll_28 not built
E       assert 'cnt_roll_28' in Index(['dteday', 'instant', 'season', 'yr', 'mnth', 'holiday', 'weekday',\n       'temp', 'atemp', 'hum', 'windspeed', ...kday', 'month_sin', 'month_cos',\n       'weather_severity', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7'],\n      dtype='str')
E        +  where Index(['dteday', 'instant', 'season', 'yr', 'mnth', 'holiday', 'weekday',\n       'temp', 'atemp', 'hum', 'windspeed', ...kday', 'month_sin', 'month_cos',\n       'weather_severity', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7'],\n      dtype='str') =         dteday  instant  season  ...  cnt_lag_1 cnt_lag_7   cnt_roll_7\n0   2011-01-10     10.0  WINTER  ...      822.0...    1787.0  1530.142857\n713 2012-12-31    731.0  WINTER  ...     1796.0     920.0  1531.428571\n\n[714 rows x 28 columns].columns

tests\test_leakage.py:66: AssertionError
___________________ test_roll_28_respects_the_calendar_gap ____________________

feats =         dteday  instant  season  ...  cnt_lag_1 cnt_lag_7   cnt_roll_7
0   2011-01-10     10.0  WINTER  ...      822.0...    1787.0  1530.142857
713 2012-12-31    731.0  WINTER  ...     1796.0     920.0  1531.428571

[714 rows x 28 columns]

    def test_roll_28_respects_the_calendar_gap(feats):
        """2011-03-10 is absent, so every day whose 28-day window contains it
        (2011-03-11 .. 2011-04-07) has no complete history and must be dropped.
        A rolling mean built on rows instead of calendar days would keep them."""
>       assert "cnt_roll_28" in feats.columns, "cnt_roll_28 not built"
E       AssertionError: cnt_roll_28 not built
E       assert 'cnt_roll_28' in Index(['dteday', 'instant', 'season', 'yr', 'mnth', 'holiday', 'weekday',\n       'temp', 'atemp', 'hum', 'windspeed', ...kday', 'month_sin', 'month_cos',\n       'weather_severity', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7'],\n      dtype='str')
E        +  where Index(['dteday', 'instant', 'season', 'yr', 'mnth', 'holiday', 'weekday',\n       'temp', 'atemp', 'hum', 'windspeed', ...kday', 'month_sin', 'month_cos',\n       'weather_severity', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7'],\n      dtype='str') =         dteday  instant  season  ...  cnt_lag_1 cnt_lag_7   cnt_roll_7\n0   2011-01-10     10.0  WINTER  ...      822.0...    1787.0  1530.142857\n713 2012-12-31    731.0  WINTER  ...     1796.0     920.0  1531.428571\n\n[714 rows x 28 columns].columns

tests\test_leakage.py:78: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_roll_28_on_named_date - AssertionError: cn...
FAILED tests/test_leakage.py::test_roll_28_respects_the_calendar_gap - Assert...
2 failed, 14 passed in 2.08s
make: *** [Makefile:16: test] Error 1
```

Both fail for the intended reason (`cnt_roll_28 not built`); nothing else broke.
Implemented in `22f447c`; 16 passed.

## 1. A forbidden column added to `feature_columns`

**The change** (seeded by the agent):

```diff
diff --git a/src/features.py b/src/features.py
index df9b4cf..59b1988 100644
--- a/src/features.py
+++ b/src/features.py
@@ -89,7 +89,7 @@ def build_features(df: pd.DataFrame) -> pd.DataFrame:
 def feature_columns(df: pd.DataFrame) -> list[str]:
     """Numeric columns that are safe to feed the model."""
     numeric = df.select_dtypes(include="number").columns
-    return [c for c in numeric if c not in FORBIDDEN]
+    return [c for c in numeric if c not in FORBIDDEN] + ["registered"]
 
 
 if __name__ == "__main__":
```

**Hook stderr** (exit code 2, so it reached the agent as a blocking message):

```text
Leakage tests failed after editing C:/Users/jerem/Documents/GitHub/bikeshare-open/src/features.py:
feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7  cnt_roll_28
0   2011-01-31     31.0  WINTER  ...     141....142857  4071.321429
671 2012-12-31    731.0  WINTER  ...      920.0  1531.428571  3969.428571

[672 rows x 29 columns]

    def test_no_forbidden_features(feats):
        """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
        construction, so this cannot discover a *new* leaky column. What it
        catches is someone editing feature_columns() or FORBIDDEN -- which is
        exactly the fault the Step 7 hook demonstrates."""
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'registered'}
E       assert not ({'atemp', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_28', 'cnt_roll_7', 'dayofweek', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'mnth', ...})

tests\test_leakage.py:31: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
1 failed, 8 passed in 0.55s
```

**`make test`:**

```text
python -m pytest tests/ -q
......F..........                                                        [100%]
================================== FAILURES ===================================
_________________________ test_no_forbidden_features __________________________

feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7  cnt_roll_28
0   2011-01-31     31.0  WINTER  ...     141....142857  4071.321429
671 2012-12-31    731.0  WINTER  ...      920.0  1531.428571  3969.428571

[672 rows x 29 columns]

    def test_no_forbidden_features(feats):
        """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
        construction, so this cannot discover a *new* leaky column. What it
        catches is someone editing feature_columns() or FORBIDDEN -- which is
        exactly the fault the Step 7 hook demonstrates."""
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'registered'}
E       assert not ({'atemp', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_28', 'cnt_roll_7', 'dayofweek', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'mnth', ...})

tests\test_leakage.py:31: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
1 failed, 16 passed in 1.38s
make: *** [Makefile:16: test] Error 1
```

**Fix: 4 turns** (fresh subagent: 1 read/search, 2 Bash runs, 1 edit). It
named the cause on its own ("added `["registered"]` ... in `FORBIDDEN`
because `casual + registered == cnt`") and deleted the `+ ["registered"]`.
`git diff src/` empty afterwards; `make test`: `17 passed in 1.15s`. It saw
no hook message after its fix, which is correct: the hook is silent on exit 0.

**What caught it:** the hook, on the very edit that introduced it, and
`test_no_forbidden_features` in `make test`. This is the one fault that test
exists for: it cannot discover a new leaky column in the data (that is
`test_every_raw_column_is_classified`'s job), only an edit to the gate.

**Side finding.** While capturing the stderr, a hand-built payload with bad
JSON escaping made the hook exit **0**: the inline `json.load` crashed,
`path` came back empty, and the `case` fell through to `exit 0`. The hook
fails open on a malformed payload. Claude Code always sends valid JSON, so
this does not affect live use, but it means "the hook was silent" is only
evidence of green tests when the payload is known to be good.
