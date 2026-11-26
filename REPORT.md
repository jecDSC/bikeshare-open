# Bikeshare demand: methodology report

Daily Capital Bikeshare counts, 2011-2012 (the Molnar mirror of the UCI
data: 728 rows, 2011-03-10 absent). Target `cnt`; train 2011, validate
H1 2012, test H2 2012. Every number below is reproduced by `make all`
from a clean checkout unless it says otherwise.

## Results

Validation and test R^2 and MAE for both baselines and both models, before
and after the feature added in Exercise 1. **Before** is the unmodified
starter's output (`reports/metrics_starter.json`, commit `756a72b`);
**after** is `reports/metrics.json` from `make all` on the final code, with
`cnt_roll_28` added. The rows are generated from those two files, so they
match them to the printed digit.

| model | version | valid R^2 | valid MAE | test R^2 | test MAE |
|---|---|---|---|---|---|
| baseline_mean | before (starter) | -0.9318 | 2002.2 | -2.1441 | 2847.7 |
| baseline_mean | after (+ cnt_roll_28) | -0.6894 | 1877.3 | -1.7717 | 2659.6 |
| baseline_persistence | before (starter) | 0.4507 | 900.6 | 0.5099 | 840.1 |
| baseline_persistence | after (+ cnt_roll_28) | 0.4507 | 900.6 | 0.5099 | 840.1 |
| ridge | before (starter) | 0.6475 | 832.9 | 0.5833 | 947.1 |
| ridge | after (+ cnt_roll_28) | 0.6839 | 777.5 | 0.6239 | 879.3 |
| hgb | before (starter) | 0.2185 | 1296.6 | -0.4975 | 1972.6 |
| hgb | after (+ cnt_roll_28) | 0.2415 | 1296.6 | -0.46 | 1952.4 |

Two things move that are not the feature. Raising `LAG_WARMUP` from 7 to 28
drops 42 more training rows (348 -> 306, the earliest and the post-gap days of
2011), which is why the mean baseline, which uses no features, improves.
On identical 306 training rows, `cnt_roll_28` alone adds +0.038 validation
R^2 to ridge and +0.049 to hgb (`docs/DECISIONS.md`). Persistence does not
train, so it does not move.

One assumption sits under every row, flagged by `agent/audit.py`
(`reports/audit.jsonl`, 0 flagged, 3 findings): the weather features are
same-day *measured* values. A real day-ahead forecaster would have a weather
forecast instead, so every model score here is somewhat optimistic. This is
the starter's framing and is kept; it is not target leakage
(`check_identity` finds no restatement of `cnt`).

## Headline finding

The naive model, a linear regression handed `casual`, `registered`, `temp`
and `hum`, scores test R^2 = 1.000 even under the temporal split
(`python -m src.leakage_demo`), and is invalid: `casual + registered == cnt`
exactly, so it has learned addition. With those columns forbidden,
predicting the 2011 mean scores test R^2
-1.7717, because ridership grew from 3725 to 5600 rides a day on average;
persistence ("yesterday again") scores 0.5099; ridge reaches 0.6239, only
0.11 better than persistence on R^2 and worse on MAE (879.3 vs 840.1 rides);
and gradient boosting scores -0.46. hgb's negative R^2 is a different failure
from the mean baseline's: it still beats that baseline comfortably, but a
tree cannot predict above the largest count it trained on, and 57% of test
days (104 of 184) are above the 2011 maximum of 6043. Re-targeting hgb to
demand relative to its recent level (Exercise 4) lets it compete, at 0.6392.
My feature, `cnt_roll_28` (the mean count over the 28 days before d), raised
ridge's validation R^2 from 0.6475 to 0.6839, above the 0.01 floor, so I kept
it.

## Exercise 4: target transformation

**Why hgb fails.** A tree predicts by averaging training targets in a leaf,
so its ceiling is the 2011 maximum, 6043 rides; 39% of validation days and
57% of test days are above it. The fix has to make the tree predict
something that does not grow, then convert back to rides with a level that
is known at prediction time.

**What was tried, on validation only.** Two transforms, applied to ridge and
hgb (baselines unchanged), behind a flag in `src/train.py`
(`python -m src.train --target <name> --valid-only`; `make train` and
`reports/metrics.json` stay untransformed):

- `ratio28`: predict `cnt / cnt_roll_28`, multiply back by `cnt_roll_28`.
- `diff1`: predict `cnt - cnt_lag_1`, add `cnt_lag_1` back.

A test checks that each inverse reconstructs `cnt` from the feature matrix
alone, which excludes `cnt`, so neither can use the day's own count.

| validation | R^2 none | R^2 ratio28 | R^2 diff1 | MAE none | MAE ratio28 | MAE diff1 |
|---|---|---|---|---|---|---|
| ridge | 0.6839 | 0.4039 | 0.6837 | 777.5 | 1069.0 | 776.9 |
| hgb | 0.2415 | 0.6754 | 0.6138 | 1296.6 | 732.4 | 829.9 |

**The test set, touched once.** `ratio28` was chosen on these numbers and
the choice committed (`73b3fb3`) before any test score for a transform
existed; then one run scored it on test (`af90030`):
hgb test R^2 **0.6392**, MAE **744.2** (untransformed: -0.46, 1952.4),
against untransformed ridge 0.6239 / 879.3 and persistence 0.5099 / 840.1.
Under the same transform ridge collapses to -0.5069. One disclosure: test
scores of the *untransformed* models had already appeared once, quoted in
an `agent/audit.py` finding, after all feature work was committed and before
Exercise 4 began (`docs/DECISIONS.md`).

**Is it defensible?** Yes, as a framing; and the claim is that hgb
*competes*, not that it wins. Defensible because the level it divides by is
a lagged feature, the inverse provably needs only features, the choice was
fixed on validation before the test run, and it held up out of sample
(validation 0.6754, test 0.6392) instead of collapsing. "Demand scales with
its recent level" is a real assumption about a growing system, not a quirk
of these 184 days. Not a win, because it was picked from two candidates to
suit the tree, it hurts the linear model badly, and a 0.015 R^2 margin over
ridge is inside the noise of a 184-day test set.

## Exercise 5: ridge vs persistence

Ridge is worth deploying despite the loss on test MAE, because it has a much lower MAE on the days with the biggest day-to-day swings: on the 20% of test days with the largest swings, ridge's MAE is 1309 rides against persistence's 2281. Those are the days that matter, since a 2000-ride miss costs far more (empty docks, wrong staffing) than several small ones, which is what R^2 and RMSE penalise and MAE does not; on R^2 ridge wins, 0.624 to 0.510. However, on calm days persistence has the lower MAE (477 against ridge's 771), and it also has the lower MAE overall (840.1 against 879.3). Ridge is closer on only 43% of test days. That said, much of ridge's MAE loss is a level bias of -427 rides a day, a result of learning 2011's level while demand kept growing. This can be fixed by retraining or recalibrating on recent data, and does not necessarily mean a lack of skill. Also, ridge won on MAE on validation (777.5 against 900.6), so the MAE loss was only on the test set. Part of ridge's swing-day edge comes from same-day measured weather, which a day-ahead forecaster would not have, so its advantage is somewhat overstated. If, for example, with forecast weather instead of measured weather, ridge no longer beat persistence on swing days, it would not be worth deploying.

(Evidence: test errors of the committed ridge and persistence models;
"swing days" are the 20% of days with the largest |cnt - cnt_lag_1|. RMSE
1067.8 vs 1219.0; median absolute error 806.5 vs 506.5. On validation the
same split holds: swing days 1209.5 vs 2341.1, calm days 667.2 vs 533.0.)

## Attribution

**Model:** Claude Opus 5.5 (`claude-opus-5-5`, hosted by Anthropic) driving
Claude Code, used with my professor's approval and disclosed here instead of
the starter's local model. I switched once, before any committed work: I
first tried qwen3.5:27b via Ollama (`make model BASE=qwen3.5:27b`, 64k
context), which took about 10 minutes per prompt on my laptop. Every commit
after the unmodified starter was produced with Claude Opus 5.5.

**What the agent generated** (code it wrote, commands it ran, at my direction):

- `src/features.py`: `cnt_roll_28`, and the `WEEK` / `FOUR_WEEKS` window
  constants that separate the 7-day features from `LAG_WARMUP`.
- `src/config.py`: `LAG_WARMUP = 28`, `REDUNDANT_COLS`, `FEATURE_SOURCES`,
  `RAW_SHA256`. `src/ingest.py`: `raw_sha256()` and the hash check in
  `load_raw()`. `.gitattributes`: `data/raw/** -text`.
- `src/train.py`: `TARGET_TRANSFORMS`, `OnTransformedTarget`, `models_for`,
  the `--target` / `--valid-only` flags.
- Tests: `test_roll_28_on_named_date`, `test_roll_28_respects_the_calendar_gap`,
  `test_encode_weather_rejects_unknown_labels`, `test_lag_7_is_seven_calendar_days`,
  the rewritten `test_lags_are_true_calendar_lags` and
  `test_rolling_mean_excludes_today`, `test_every_raw_column_is_classified`,
  `test_raw_file_is_unmodified`, `test_load_raw_rejects_a_modified_file`,
  and the two transform tests.
- `.claude/hooks/check_leakage.sh` (Windows path and venv fix) and
  `.claude/skills/seed-fault/SKILL.md` (written to my choice of workflow).
- `docs/SEEDED_FAULTS.md`, `docs/AUDIT.md` (except my verdict), most lines
  of `docs/DECISIONS.md` as drafts I approved or reworded, this report's
  draft, and the README test-count line.
- Runs: every `make` run; the seeded faults (1-3 and 5 seeded by the agent,
  each fixed by a fresh no-context subagent whose tool calls are the
  recorded turn counts); the `leakage-auditor` subagent on the teammate
  repo and my re-check of its claims; `agent/audit.py` on this repo; the
  validation-only comparisons and the Exercise 5 error breakdown.

**The decisions that were mine** (each traces to a line in `docs/DECISIONS.md`):

- What to predict, what counts as leakage, how to split, and which
  baselines: kept the starter's `cnt` target, `FORBIDDEN` sets, 2011 / H1 /
  H2 split and the mean + persistence baselines; added `REDUNDANT_COLS` as a
  fourth exclusion reason.
- The feature: `cnt_roll_28`, and keeping it on its validation delta.
- That raw data is immutable and guarded by a hash; I ran the fourth fault's
  `cp` myself.
- Which repo to audit, and the verdict that nothing in it changes a number.
- Which repeated workflow to package as my skill (`seed-fault`), and that
  fix turns are measured by a fresh subagent, not by the agent that seeded
  the fault.
- How to run `agent/audit.py` (Opus via `AUDIT_MODEL`, no code change).
- The Exercise 4 transform, chosen before the test run, and the verdict
  that it is defensible but shows hgb competing, not winning.
- That ridge is worth deploying over persistence (Exercise 5).
- Whether the answer is believable: the headline is stated against both
  baselines, with the same-day-weather assumption and the test-set
  exposure disclosed.
