"""Guard rails on the ingest contract and the trained model's behaviour."""
import pandas as pd
import pytest
from sklearn.metrics import r2_score

from src.config import FEATURE_SOURCES, FORBIDDEN, LAG_WARMUP, RAW, TARGET
from src.features import build_features, feature_columns, reindex_to_calendar
from src.ingest import load_raw
from src.train import MODELS, temporal_split


@pytest.fixture(scope="module")
def raw():
    return load_raw().sort_values("dteday").reset_index(drop=True)


@pytest.fixture(scope="module")
def feats(raw):
    return build_features(raw)


def test_calendar_is_complete_before_lagging(raw):
    """The reindexed frame must have no gaps, or the lags are wrong."""
    grid = reindex_to_calendar(raw)
    assert set(grid.dteday.diff().dropna().dt.days.unique()) == {1}


def test_only_expected_rows_are_dropped(raw, feats):
    """Rows may only vanish for the lag warm-up or downstream of a genuinely
    absent day -- never because an encoder produced a silent NaN.

    Accounting: the first LAG_WARMUP days have no complete history. Each
    absent calendar day m costs the LAG_WARMUP rows after it (cnt_lag_1 is
    NaN on m+1, cnt_lag_7 on m+7, cnt_roll_7 on m+1..m+7, cnt_roll_28 on
    m+1..m+28; their union is 28 rows). Day m itself was never in `raw`, so
    it is not a loss. With LAG_WARMUP = 28 and one absent day (2011-03-10):
    28 + 28 * 1 = 56, so 728 raw rows -> 672. The bound is exact for the
    current feature set; add a longer lag and LAG_WARMUP must grow with it.
    """
    full = pd.date_range(raw.dteday.min(), raw.dteday.max(), freq="D")
    missing_days = len(full) - len(raw)
    allowed_loss = LAG_WARMUP + LAG_WARMUP * missing_days
    lost = len(raw) - len(feats)
    assert lost <= allowed_loss, f"lost {lost} rows; expected at most {allowed_loss}"


def test_every_raw_column_is_classified():
    """feature_columns() is a denylist, so a new numeric column in the raw
    CSV would reach the model without anyone deciding it should. Every raw
    column must be FORBIDDEN (with a reason in src/config.py), a declared
    FEATURE_SOURCE, or `dteday`. Reads the file directly, not load_raw(),
    so nothing upstream can filter a column out before it is checked."""
    columns = set(pd.read_csv(RAW, nrows=0).columns)
    unclassified = columns - FORBIDDEN - FEATURE_SOURCES - {"dteday"}
    assert not unclassified, (
        f"unclassified raw columns {sorted(unclassified)}: add each to "
        "FORBIDDEN (with its reason) or FEATURE_SOURCES in src/config.py"
    )
    stale = FEATURE_SOURCES - columns
    assert not stale, f"FEATURE_SOURCES names columns not in the raw CSV: {sorted(stale)}"


def test_beats_the_mean_baseline(feats):
    """A model that cannot beat predicting the training mean is not a result."""
    cols = feature_columns(feats)
    train, _, test = temporal_split(feats)
    ridge = MODELS["ridge"]
    ridge.fit(train[cols], train[TARGET])
    assert r2_score(test[TARGET], ridge.predict(test[cols])) > 0.4


def test_persistence_baseline_is_reported():
    """The baseline that matters for a lag-driven model is 'yesterday again'.
    It must be in the comparison, whatever its score."""
    assert "baseline_persistence" in MODELS
