"""The tests that make the agent honest.

test_no_forbidden_features is the single most valuable test in this repo:
casual + registered == cnt exactly, so any model handed those columns
scores R^2 = 1.0 and looks brilliant while having learned nothing.
"""
import pandas as pd
import pytest

from src.config import FORBIDDEN, TARGET
from src.features import build_features, encode_weather, feature_columns
from src.ingest import load_raw


@pytest.fixture(scope="module")
def feats():
    return build_features(load_raw())


def test_leakage_identity_holds(feats):
    """Documents *why* casual and registered are forbidden."""
    assert (feats.casual + feats.registered == feats[TARGET]).all()


def test_no_forbidden_features(feats):
    """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
    construction, so this cannot discover a *new* leaky column. What it
    catches is someone editing feature_columns() or FORBIDDEN -- which is
    exactly the fault the Step 7 hook demonstrates."""
    cols = set(feature_columns(feats))
    assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"


def test_lags_are_true_calendar_lags(feats):
    """cnt_lag_1 for date d must equal cnt on d-1, in calendar days."""
    by_date = feats.set_index("dteday")[TARGET]
    checked = 0
    for date, lag in feats.set_index("dteday").cnt_lag_1.items():
        prev = date - pd.Timedelta(days=1)
        if prev in by_date.index:
            assert lag == pytest.approx(by_date[prev]), f"bad lag at {date.date()}"
            checked += 1
    assert checked > 600, "too few rows actually verified"


def test_lag_is_not_the_target(feats):
    assert not (feats.cnt_lag_1 == feats[TARGET]).all()


def test_rolling_mean_excludes_today(feats):
    """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
    by_date = feats.set_index("dteday")[TARGET]
    date = feats.dteday.iloc[200]
    window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
    if all(d in by_date.index for d in window):
        expected = sum(by_date[d] for d in window) / 7
        assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)


def test_roll_28_on_named_date(feats):
    """cnt_roll_28 on 2012-03-15 is the mean cnt of the 28 calendar days
    strictly before it: 2012-02-16 .. 2012-03-14, all present in the raw CSV.
    Hand-computed from data/raw/bike_daily.csv with the csv module: those 28
    counts sum to 115349. Including the day itself (cnt 6192) instead of
    2012-02-16 (cnt 3005) would give 4233.71, so a missing shift(1) fails."""
    assert "cnt_roll_28" in feats.columns, "cnt_roll_28 not built"
    date = pd.Timestamp("2012-03-15")
    raw = load_raw().set_index("dteday")[TARGET]
    window = [date - pd.Timedelta(days=k) for k in range(1, 29)]
    assert sum(raw[d] for d in window) == 115349  # the hand computation
    assert feats.set_index("dteday").cnt_roll_28[date] == pytest.approx(115349 / 28)


def test_roll_28_respects_the_calendar_gap(feats):
    """2011-03-10 is absent, so every day whose 28-day window contains it
    (2011-03-11 .. 2011-04-07) has no complete history and must be dropped.
    A rolling mean built on rows instead of calendar days would keep them."""
    assert "cnt_roll_28" in feats.columns, "cnt_roll_28 not built"
    blind = pd.date_range("2011-03-11", "2011-04-07", freq="D")
    kept = sorted(set(feats.dteday) & set(blind))
    assert not kept, f"{len(kept)} rows kept whose window spans 2011-03-10"


def test_encode_weather_rejects_unknown_labels():
    """The raw data has no unknown labels, so nothing else in the suite ever
    exercises the encoder's raise: delete it and every other test stays
    green, until a new label arrives and its days vanish in dropna(). The
    NaN is a reindexed calendar gap and must not trigger the error."""
    known = encode_weather(pd.Series(["GOOD", "MISTY", "BAD", None]))
    assert known.iloc[:3].tolist() == [0.0, 1.0, 2.0] and known.isna().iloc[3]
    with pytest.raises(ValueError, match="SNOW"):
        encode_weather(pd.Series(["GOOD", "SNOW", None]))


def test_no_missing_values(feats):
    assert feats[feature_columns(feats)].isna().sum().sum() == 0


def test_dates_are_sorted_and_unique(feats):
    assert feats.dteday.is_monotonic_increasing
    assert feats.dteday.is_unique
