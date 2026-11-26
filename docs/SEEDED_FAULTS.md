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

## 2. The `.shift(1)` deleted from `cnt_roll_7`

**The change** (seeded by the agent):

```diff
diff --git a/src/features.py b/src/features.py
index df9b4cf..5f969ac 100644
--- a/src/features.py
+++ b/src/features.py
@@ -78,7 +78,7 @@ def build_features(df: pd.DataFrame) -> pd.DataFrame:
     # If you add a longer lag, raise LAG_WARMUP in src/config.py.
     out["cnt_lag_1"] = out[TARGET].shift(1)
     out["cnt_lag_7"] = out[TARGET].shift(WEEK)
-    out["cnt_roll_7"] = out[TARGET].shift(1).rolling(WEEK).mean()
+    out["cnt_roll_7"] = out[TARGET].rolling(WEEK).mean()
     # Four-week level: smooths the weekly cycle that cnt_roll_7 still carries.
     out["cnt_roll_28"] = out[TARGET].shift(1).rolling(FOUR_WEEKS).mean()
     assert FOUR_WEEKS <= LAG_WARMUP, "raise LAG_WARMUP in src/config.py"
```

**Hook stderr** (exit code 2; pytest wrote it in cp1252, decoded here so
`±` survives):

```text
Leakage tests failed after editing C:/Users/jerem/Documents/GitHub/bikeshare-open/src/features.py:
[672 rows x 29 columns]

    def test_rolling_mean_excludes_today(feats):
        """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
        by_date = feats.set_index("dteday")[TARGET]
        date = feats.dteday.iloc[200]
        window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
        if all(d in by_date.index for d in window):
            expected = sum(by_date[d] for d in window) / 7
>           assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E           assert np.float64(4605.285714285715) == 4724.428571428572 ± 0.00472443
E             
E             comparison failed
E             Obtained: 4605.285714285715
E             Expected: 4724.428571428572 ± 0.00472443

tests\test_leakage.py:57: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 8 passed in 0.55s
```

**`make test`:**

```text
python -m pytest tests/ -q
.........F.......                                                        [100%]
================================== FAILURES ===================================
______________________ test_rolling_mean_excludes_today _______________________

feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7  cnt_roll_28
0   2011-01-31     31.0  WINTER  ...     141....428571  4071.321429
671 2012-12-31    731.0  WINTER  ...      920.0  1789.857143  3969.428571

[672 rows x 29 columns]

    def test_rolling_mean_excludes_today(feats):
        """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
        by_date = feats.set_index("dteday")[TARGET]
        date = feats.dteday.iloc[200]
        window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
        if all(d in by_date.index for d in window):
            expected = sum(by_date[d] for d in window) / 7
>           assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E           assert np.float64(4605.285714285715) == 4724.428571428572 ± 0.00472443
E             
E             comparison failed
E             Obtained: 4605.285714285715
E             Expected: 4724.428571428572 ± 0.00472443

tests\test_leakage.py:57: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 16 passed in 1.40s
make: *** [Makefile:16: test] Error 1
```

**What the leak would have been worth** (seeded state, features built in
memory, validation only, test split discarded):

```text
seeded fault 2, ridge: valid R2 0.7541, MAE 680.3
seeded fault 2, hgb: valid R2 0.2962, MAE 1211.2
```

Honest pipeline: ridge 0.6839 / MAE 777.5, hgb 0.2415 / MAE 1296.6. Today's
count inside its own rolling mean lifts ridge by +0.07 validation R^2, the
kind of gain that would be kept on sight without the test.

**Fix: 4 turns** (fresh subagent: 1 read/search, 2 Bash runs, 1 edit). It
identified the cause unprompted ("the 7-day rolling mean included today's
`cnt`. That leaks the target") and restored `.shift(1)`. `git diff src/`
empty afterwards; `make test`: `17 passed in 1.20s`.

**What caught it:** the hook, on the seeding edit, and
`test_rolling_mean_excludes_today` in `make test`. `cnt_roll_28`'s own test
(`test_roll_28_on_named_date`) stayed green, correctly: that feature still
shifts.

**Weakness noticed.** `test_rolling_mean_excludes_today` checks one row
(`feats.dteday.iloc[200]`) and wraps its assert in
`if all(d in by_date.index for d in window):`. If that row's window ever
touched a gap, the test would assert nothing and still pass. It caught this
fault, but only because row 200 happens to have a complete window.

## 3. The `raise` removed from `encode_weather`

**The change** (seeded by the agent, identical in both runs below):

```diff
diff --git a/src/features.py b/src/features.py
index df9b4cf..9dc5dfb 100644
--- a/src/features.py
+++ b/src/features.py
@@ -31,8 +31,6 @@ def encode_weather(series: pd.Series) -> pd.Series:
     """
     known = series.dropna()
     unknown = set(known.unique()) - set(WEATHER_ORDER)
-    if unknown:
-        raise ValueError(f"unmapped weather labels: {sorted(unknown)}")
     return series.map(WEATHER_ORDER).astype(float)
 
 
```

### Run (a): the starter's suite cannot see it

Hook result for the seeding edit (re-run with the same payload):

```text
hook exit code: 0
hook stderr bytes: 0
```

**`make test`:**

```text
python -m pytest tests/ -q
.................                                                        [100%]
17 passed in 1.20s
```

Green. The raise only fires on a label outside `WEATHER_ORDER`, and the raw
data has none, so no test ever executes it. This is the lesson's own Bug 2
waiting to happen again: the day the mirror adds a label, every such day
maps to NaN and `dropna()` deletes it without a word. (`test_only_expected_rows_are_dropped`
would then go red in `make test`, but only *after* bad data arrives, and the
hook does not run `tests/test_contract.py`.)

### The fix to the suite: a test for the guard itself

Code reverted exactly (`git diff src/` empty), then this test added to
`tests/test_leakage.py`, where the hook runs it. It passed on correct code
(`18 passed`) before the fault was seeded again:

```diff
diff --git a/tests/test_leakage.py b/tests/test_leakage.py
index 6b37639..ec4d287 100644
--- a/tests/test_leakage.py
+++ b/tests/test_leakage.py
@@ -8,7 +8,7 @@ import pandas as pd
 import pytest
 
 from src.config import FORBIDDEN, TARGET
-from src.features import build_features, feature_columns
+from src.features import build_features, encode_weather, feature_columns
 from src.ingest import load_raw
 
 
@@ -81,6 +81,17 @@ def test_roll_28_respects_the_calendar_gap(feats):
     assert not kept, f"{len(kept)} rows kept whose window spans 2011-03-10"
 
 
+def test_encode_weather_rejects_unknown_labels():
+    """The raw data has no unknown labels, so nothing else in the suite ever
+    exercises the encoder's raise: delete it and every other test stays
+    green, until a new label arrives and its days vanish in dropna(). The
+    NaN is a reindexed calendar gap and must not trigger the error."""
+    known = encode_weather(pd.Series(["GOOD", "MISTY", "BAD", None]))
+    assert known.iloc[:3].tolist() == [0.0, 1.0, 2.0] and known.isna().iloc[3]
+    with pytest.raises(ValueError, match="SNOW"):
+        encode_weather(pd.Series(["GOOD", "SNOW", None]))
+
+
 def test_no_missing_values(feats):
     assert feats[feature_columns(feats)].isna().sum().sum() == 0
 
```

### Run (b): the same fault, seeded again

**Hook stderr** (exit code 2):

```text
Leakage tests failed after editing C:/Users/jerem/Documents/GitHub/bikeshare-open/src/features.py:
.......F..                                                               [100%]
================================== FAILURES ===================================
_________________ test_encode_weather_rejects_unknown_labels __________________

    def test_encode_weather_rejects_unknown_labels():
        """The raw data has no unknown labels, so nothing else in the suite ever
        exercises the encoder's raise: delete it and every other test stays
        green, until a new label arrives and its days vanish in dropna(). The
        NaN is a reindexed calendar gap and must not trigger the error."""
        known = encode_weather(pd.Series(["GOOD", "MISTY", "BAD", None]))
        assert known.iloc[:3].tolist() == [0.0, 1.0, 2.0] and known.isna().iloc[3]
>       with pytest.raises(ValueError, match="SNOW"):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE ValueError

tests\test_leakage.py:91: Failed
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_encode_weather_rejects_unknown_labels - Fa...
1 failed, 9 passed in 0.52s
```

**`make test`:**

```text
python -m pytest tests/ -q
............F.....                                                       [100%]
================================== FAILURES ===================================
_________________ test_encode_weather_rejects_unknown_labels __________________

    def test_encode_weather_rejects_unknown_labels():
        """The raw data has no unknown labels, so nothing else in the suite ever
        exercises the encoder's raise: delete it and every other test stays
        green, until a new label arrives and its days vanish in dropna(). The
        NaN is a reindexed calendar gap and must not trigger the error."""
        known = encode_weather(pd.Series(["GOOD", "MISTY", "BAD", None]))
        assert known.iloc[:3].tolist() == [0.0, 1.0, 2.0] and known.isna().iloc[3]
>       with pytest.raises(ValueError, match="SNOW"):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE ValueError

tests\test_leakage.py:91: Failed
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_encode_weather_rejects_unknown_labels - Fa...
1 failed, 17 passed in 1.38s
make: *** [Makefile:16: test] Error 1
```

**Fix: 5 turns** (fresh subagent: 1 read/search, 3 Bash runs, 1 edit; it
noted its one Read came after the edit and added nothing). It named the
cause ("labels other than GOOD/MISTY/BAD ... became NaN silently instead of
raising `ValueError`") and restored the two lines. `git diff src/` empty
afterwards; `make test`: `18 passed in 1.10s`. It left the then-uncommitted
test untouched, as instructed.

**What caught it:** in run (a), nothing: hook exit 0, `make test` green.
In run (b), the hook on the seeding edit and
`test_encode_weather_rejects_unknown_labels` in `make test`. Lesson: a guard
that the data never triggers needs a test that triggers it on purpose, or
deleting it is invisible.

## 4. A `cp` into `data/raw/` from a shell: the fault the hook cannot see

**What was done.** The agent's first attempt, a Bash command that only
*read* from `data/raw/` (copying the CSV out to a backup), was denied in this
session, so the fault was run by the human in PowerShell. `<notes>` is a
scratch folder outside the repo. `tamper.py` scales one training day's
`casual`, `registered` and `cnt` by 1.5, keeping `casual + registered == cnt`,
so the identity test cannot notice. 2011-07-04 happens to be the 2011
maximum, the ceiling the hgb headline depends on.

```text
PS> Copy-Item data\raw\bike_daily.csv <notes>\faults\bike_daily.BACKUP.csv
PS> .venv\Scripts\python.exe <notes>\faults\tamper.py
2011-07-04 casual/registered/cnt: 3065/2978/6043 -> 4598/4467/9065
OK wrote bike_daily.TAMPERED.csv: 86325 bytes (backup 86325)
PS> cp <notes>\faults\bike_daily.TAMPERED.csv data\raw\bike_daily.csv
PS> (Get-FileHash data\raw\bike_daily.csv).Hash
D138851D8CA3BC927235D6753851B30DA5C350C482FF7D93B743A55A9311194A
```

### Run (a): the starter's protections

Nothing fired. The PostToolUse hook matches only `Edit|Write`; the
`Edit(./data/raw/**)` / `Write(./data/raw/**)` deny rules bind only those
tools; and every test still passes:

```text
$ sha256sum data/raw/bike_daily.csv
d138851d8ca3bc927235d6753851b30da5c350c482ff7d93b743a55a9311194a *data/raw/bike_daily.csv
$ git status --short
 M data/raw/bike_daily.csv
$ make data
python -m src.ingest
OK ingest: 728 rows, 2011-01-03 -> 2012-12-31
(exit 0)
$ make test
python -m pytest tests/ -q
..................                                                       [100%]
18 passed in 1.58s
(exit 0)
```

The pipeline ran on the tampered file and every model moved (validation
only, features built in memory, test split discarded):

```text
train max cnt: 9065.0
tampered raw, baseline_mean: valid R2 -0.6799, MAE 1872.1
tampered raw, ridge: valid R2 0.6589, MAE 821.0
tampered raw, hgb: valid R2 0.2882, MAE 1256.8
```

Honest values: mean -0.6894, ridge 0.6839, hgb 0.2415. One silently edited
row costs ridge 0.025 R^2 and *gains* hgb 0.047, because the tree's ceiling
rose from 6043 to 9065: the edit blurs exactly the result the report rests on.

### What would have caught it

- **The PostToolUse hook: no.** It fires on Edit/Write only, and runs only
  `tests/test_leakage.py`.
- **The permission deny rules: no.** They bind the agent's Edit/Write tools,
  not Bash and not a human shell. (Here the agent's Bash read was stopped at
  the permission prompt, but that was the session's approval mode, not a rule
  in `settings.json`.)
- **A Stop hook running `make test`: no, not on its own.** This edit kept
  every invariant the suite checks: run (a) is 18 passed.
- **A PreToolUse hook on Bash:** can refuse agent commands that name
  `data/raw`, before they run. Prevention, but only for the agent, and a
  regex over shell text is easy to evade (`python -c`, variables, a script).
- **A filesystem permission** (`attrib +R` / `chmod -w data/raw`): stops a
  casual `cp` by anyone, but is not versioned, so a fresh clone does not have it.
- **A hash check: yes.** It does not care who changed the bytes or how.
  Implemented below, in `load_raw()` so `make data`, `make features` and every
  test refuse the file. `git status` also showed `M data/raw/bike_daily.csv`
  in run (a), but only to someone who looked.

### The guard (implemented)

`RAW_SHA256` in `src/config.py`; `load_raw()` raises on a mismatch; two tests,
one on the real file and one that flips a byte in a `tmp_path` copy so
deleting the guard goes red; and `data/raw/** -text` in `.gitattributes`,
because `core.autocrlf=true` on this machine and a CRLF checkout would
otherwise change the hash on a Windows clone.

```diff
diff --git a/.gitattributes b/.gitattributes
index b250910..2a29e19 100644
--- a/.gitattributes
+++ b/.gitattributes
@@ -1,2 +1,5 @@
 # Hook scripts run under bash; CRLF line endings break them on Windows checkouts.
 *.sh text eol=lf
+
+# Raw data is hashed (src/config.py RAW_SHA256): never convert its line endings.
+data/raw/** -text
diff --git a/src/config.py b/src/config.py
index a5f6e7f..4d607de 100644
--- a/src/config.py
+++ b/src/config.py
@@ -20,6 +20,13 @@ DATA_URL = (
     "interpretable-ml-book/master/data/bike.csv"
 )
 
+# Raw data is immutable. src.ingest.load_raw() refuses any file whose bytes
+# differ from these, however the change was made (an editor, a Bash `cp`,
+# a re-download from a mirror that changed). The settings.json deny rules
+# only bind the Edit/Write tools; this binds everything that reads the data.
+# .gitattributes marks data/raw/ -text so a CRLF checkout cannot break it.
+RAW_SHA256 = "a6bed1577f6e4de56dcfae6d8315985073cc0ad3446c8c99ed60c86a0b5ad9dc"
+
 TARGET = "cnt"
 
 # --- Three reasons a column is kept out of the feature set --------------
diff --git a/src/ingest.py b/src/ingest.py
index 6654075..690ca89 100644
--- a/src/ingest.py
+++ b/src/ingest.py
@@ -2,12 +2,14 @@
 
 Run: python -m src.ingest
 """
+import hashlib
 import sys
 import urllib.request
+from pathlib import Path
 
 import pandas as pd
 
-from src.config import DATA_URL, RAW
+from src.config import DATA_URL, RAW, RAW_SHA256
 
 EXPECTED_MIN_ROWS = 700
 REQUIRED_COLS = {"dteday", "cnt", "casual", "registered", "temp", "hum", "windspeed"}
@@ -20,8 +22,19 @@ def download(force: bool = False) -> None:
     urllib.request.urlretrieve(DATA_URL, RAW)
 
 
-def load_raw() -> pd.DataFrame:
-    df = pd.read_csv(RAW, parse_dates=["dteday"])
+def raw_sha256(path: Path = RAW) -> str:
+    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
+
+
+def load_raw(path: Path = RAW) -> pd.DataFrame:
+    digest = raw_sha256(path)
+    if digest != RAW_SHA256:
+        raise ValueError(
+            f"{Path(path).name} has sha256 {digest[:16]}..., expected "
+            f"{RAW_SHA256[:16]}...: raw data is immutable. Restore it from git "
+            "and make any change downstream, in code."
+        )
+    df = pd.read_csv(path, parse_dates=["dteday"])
     missing = REQUIRED_COLS - set(df.columns)
     if missing:
         raise ValueError(f"raw data is missing required columns: {sorted(missing)}")
diff --git a/tests/test_contract.py b/tests/test_contract.py
index 0f79920..27c77c2 100644
--- a/tests/test_contract.py
+++ b/tests/test_contract.py
@@ -3,9 +3,9 @@ import pandas as pd
 import pytest
 from sklearn.metrics import r2_score
 
-from src.config import FEATURE_SOURCES, FORBIDDEN, LAG_WARMUP, RAW, TARGET
+from src.config import FEATURE_SOURCES, FORBIDDEN, LAG_WARMUP, RAW, RAW_SHA256, TARGET
 from src.features import build_features, feature_columns, reindex_to_calendar
-from src.ingest import load_raw
+from src.ingest import load_raw, raw_sha256
 from src.train import MODELS, temporal_split
 
 
@@ -44,6 +44,25 @@ def test_only_expected_rows_are_dropped(raw, feats):
     assert lost <= allowed_loss, f"lost {lost} rows; expected at most {allowed_loss}"
 
 
+def test_raw_file_is_unmodified():
+    """The permission deny rules bind only the Edit/Write tools, and the
+    PostToolUse hook fires only on them, so a `cp` into data/raw/ from Bash
+    passes both. A consistent edit (casual, registered and cnt scaled
+    together) passes every other test too. Only the bytes can tell."""
+    assert raw_sha256() == RAW_SHA256, "data/raw/bike_daily.csv was modified"
+
+
+def test_load_raw_rejects_a_modified_file(tmp_path):
+    """Tests the guard itself, so deleting the check in load_raw() goes red.
+    One byte changed in a copy under tmp_path; data/raw/ is never written."""
+    tampered = bytearray(RAW.read_bytes())
+    tampered[-2] ^= 1
+    copy = tmp_path / "bike_daily.csv"
+    copy.write_bytes(bytes(tampered))
+    with pytest.raises(ValueError, match="raw data is immutable"):
+        load_raw(copy)
+
+
 def test_every_raw_column_is_classified():
     """feature_columns() is a denylist, so a new numeric column in the raw
     CSV would reach the model without anyone deciding it should. Every raw
```

### Run (b): the same tampered file, with the guard

The hook fired live (exit 2) on the agent's edit to `src/ingest.py`, since
`tests/test_leakage.py` loads the raw file. `make data`:

```text
$ sha256sum data/raw/bike_daily.csv
d138851d8ca3bc927235d6753851b30da5c350c482ff7d93b743a55a9311194a *data/raw/bike_daily.csv
$ make data
    )
ValueError: bike_daily.csv has sha256 d138851d8ca3bc92..., expected a6bed1577f6e4de5...: raw data is immutable. Restore it from git and make any change downstream, in code.
make: *** [Makefile:7: data] Error 1
(exit 2)
```

`make test` (excerpt: the first error line and the full summary; 384 lines in all):

```text
E           ValueError: bike_daily.csv has sha256 d138851d8ca3bc92..., expected a6bed1577f6e4de5...: raw data is immutable. Restore it from git and make any change downstream, in code.
...
=========================== short test summary info ===========================
FAILED tests/test_contract.py::test_raw_file_is_unmodified - AssertionError: ...
ERROR tests/test_contract.py::test_calendar_is_complete_before_lagging - Valu...
ERROR tests/test_contract.py::test_only_expected_rows_are_dropped - ValueErro...
ERROR tests/test_contract.py::test_beats_the_mean_baseline - ValueError: bike...
ERROR tests/test_leakage.py::test_leakage_identity_holds - ValueError: bike_d...
ERROR tests/test_leakage.py::test_no_forbidden_features - ValueError: bike_da...
ERROR tests/test_leakage.py::test_lags_are_true_calendar_lags - ValueError: b...
ERROR tests/test_leakage.py::test_lag_is_not_the_target - ValueError: bike_da...
ERROR tests/test_leakage.py::test_rolling_mean_excludes_today - ValueError: b...
ERROR tests/test_leakage.py::test_roll_28_on_named_date - ValueError: bike_da...
ERROR tests/test_leakage.py::test_roll_28_respects_the_calendar_gap - ValueEr...
ERROR tests/test_leakage.py::test_no_missing_values - ValueError: bike_daily....
ERROR tests/test_leakage.py::test_dates_are_sorted_and_unique - ValueError: b...
ERROR tests/test_split.py::test_splits_non_empty - ValueError: bike_daily.csv...
ERROR tests/test_split.py::test_splits_are_ordered_in_time - ValueError: bike...
ERROR tests/test_split.py::test_no_overlapping_dates - ValueError: bike_daily...
1 failed, 4 passed, 15 errors in 1.28s
make: *** [Makefile:16: test] Error 1
```

The four that pass do not read the raw file; one of them is
`test_load_raw_rejects_a_modified_file`, which passes because the guard works.

### Restored

The human copied the backup back (`Get-FileHash` printed
`A6BED1577F6E4DE56DCFAE6D8315985073CC0AD3446C8C99ED60C86A0B5AD9DC`):

```text
$ sha256sum data/raw/bike_daily.csv
a6bed1577f6e4de56dcfae6d8315985073cc0ad3446c8c99ed60c86a0b5ad9dc *data/raw/bike_daily.csv
$ git status --short data/
$ make all
OK ingest: 728 rows, 2011-01-03 -> 2012-12-31
OK features: 672 rows, 15 features -> features.parquet
$ git diff --stat reports/metrics.json   (no output: byte-identical)
$ make test
20 passed in 1.17s
```

**Turns:** none for the agent to fix, by design: the guard does not repair
bad data, it refuses it. Restoring took one human command.

## 5. The `reindex_to_calendar` call removed from `build_features`

First run of the `seed-fault` skill (`.claude/skills/seed-fault/SKILL.md`),
invoked as `/seed-fault remove the reindex_to_calendar call from build_features`.
This is the lesson's Bug 1 put back.

**The change:**

```diff
diff --git a/src/features.py b/src/features.py
index df9b4cf..d872818 100644
--- a/src/features.py
+++ b/src/features.py
@@ -56,7 +56,7 @@ def reindex_to_calendar(df: pd.DataFrame) -> pd.DataFrame:
 
 
 def build_features(df: pd.DataFrame) -> pd.DataFrame:
-    out = reindex_to_calendar(df.sort_values("dteday").reset_index(drop=True)).copy()
+    out = df.sort_values("dteday").reset_index(drop=True).copy()
 
     # --- Calendar: known in advance, so it cannot leak -------------------
     out["dayofweek"] = out.dteday.dt.dayofweek
```

**Prediction** (written before seeding): `test_lags_are_true_calendar_lags`
and `test_roll_28_respects_the_calendar_gap` go red, so the hook exits 2;
`test_calendar_is_complete_before_lagging` and
`test_only_expected_rows_are_dropped` stay green. **Half right.** The gap
test went red; the lag test stayed green. It skips every date whose calendar
day d-1 is not in the table, and 2011-03-11, the one row whose `cnt_lag_1` is
wrong (it holds 2011-03-09's count), is exactly such a date. The starter's
calendar-lag test cannot see the bug it was written for. The row-loss test
stayed green as predicted: without the reindex only 28 rows are lost
(700 left), under the 56-row upper bound.

**Hook** (re-run with the real payload):

```text
Leakage tests failed after editing C:/Users/jerem/Documents/GitHub/bikeshare-open/src/features.py:
0         31 2011-01-31  WINTER  ...     141....142857  4071.321429
699      731 2012-12-31  WINTER  ...      920.0  1531.428571  3969.428571

[700 rows x 29 columns]

    def test_roll_28_respects_the_calendar_gap(feats):
        """2011-03-10 is absent, so every day whose 28-day window contains it
        (2011-03-11 .. 2011-04-07) has no complete history and must be dropped.
        A rolling mean built on rows instead of calendar days would keep them."""
        assert "cnt_roll_28" in feats.columns, "cnt_roll_28 not built"
        blind = pd.date_range("2011-03-11", "2011-04-07", freq="D")
        kept = sorted(set(feats.dteday) & set(blind))
>       assert not kept, f"{len(kept)} rows kept whose window spans 2011-03-10"
E       AssertionError: 28 rows kept whose window spans 2011-03-10
E       assert not [Timestamp('2011-03-11 00:00:00'), Timestamp('2011-03-12 00:00:00'), Timestamp('2011-03-13 00:00:00'), Timestamp('2011-03-14 00:00:00'), Timestamp('2011-03-15 00:00:00'), Timestamp('2011-03-16 00:00:00'), ...]

tests\test_leakage.py:81: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_roll_28_respects_the_calendar_gap - Assert...
1 failed, 9 passed in 0.55s
hook exit: 2
```

**`make test`:**

```text
python -m pytest tests/ -q
................F......                                                  [100%]
================================== FAILURES ===================================
___________________ test_roll_28_respects_the_calendar_gap ____________________

feats =      instant     dteday  season  ...  cnt_lag_7   cnt_roll_7  cnt_roll_28
0         31 2011-01-31  WINTER  ...     141....142857  4071.321429
699      731 2012-12-31  WINTER  ...      920.0  1531.428571  3969.428571

[700 rows x 29 columns]

    def test_roll_28_respects_the_calendar_gap(feats):
        """2011-03-10 is absent, so every day whose 28-day window contains it
        (2011-03-11 .. 2011-04-07) has no complete history and must be dropped.
        A rolling mean built on rows instead of calendar days would keep them."""
        assert "cnt_roll_28" in feats.columns, "cnt_roll_28 not built"
        blind = pd.date_range("2011-03-11", "2011-04-07", freq="D")
        kept = sorted(set(feats.dteday) & set(blind))
>       assert not kept, f"{len(kept)} rows kept whose window spans 2011-03-10"
E       AssertionError: 28 rows kept whose window spans 2011-03-10
E       assert not [Timestamp('2011-03-11 00:00:00'), Timestamp('2011-03-12 00:00:00'), Timestamp('2011-03-13 00:00:00'), Timestamp('2011-03-14 00:00:00'), Timestamp('2011-03-15 00:00:00'), Timestamp('2011-03-16 00:00:00'), ...]

tests\test_leakage.py:81: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_roll_28_respects_the_calendar_gap - Assert...
1 failed, 22 passed in 1.42s
make: *** [Makefile:16: test] Error 1
```

**Fix: 4 turns** (fresh subagent: 1 read, 2 Bash runs, 1 edit; its report
said "5 in total" but listed four, and the harness counted 4 tool uses). Its
cause: "dropped the `reindex_to_calendar(...)` call, so the lag and rolling
features were computed over rows instead of calendar days". Exact revert: yes.

```text
$ git diff src/   (empty = exact revert)
$ make test
23 passed in 1.18s
$ git status --short data/   (empty = untouched)
```

**What caught it:** the hook and `make test`, through
`test_roll_28_respects_the_calendar_gap` only, the test written with
`cnt_roll_28` in Exercise 1. Without it, removing the reindex would have
passed every test. Proposed (not written): make `test_lags_are_true_calendar_lags`
compare against the raw calendar (`load_raw()`), not the feature table, so
2011-03-11 must be either dropped or correct.
