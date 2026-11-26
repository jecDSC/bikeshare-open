"""Stage 3: temporal split, fit, evaluate, write metrics.

Two baselines and two models, on purpose.

  baseline_mean         predict the 2011 average for every day
  baseline_persistence  predict yesterday's count (cnt_lag_1)
  ridge                 standardised linear model on the audited features
  hgb                   gradient-boosted trees on the same features

The mean baseline shows what "the distribution moved" costs. Persistence
is the baseline that actually matters: ridge's features are dominated by
lagged demand, so if it cannot beat "yesterday again" it has learned
nothing worth reporting. The booster is there because it fails, and the
reason it fails is the headline result.

Run: python -m src.train
"""
import argparse
import json

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.config import METRICS, PROCESSED, TARGET, TRAIN_END, VALID_END
from src.features import feature_columns


class PersistenceBaseline(BaseEstimator, RegressorMixin):
    """Predict a single lagged column unchanged. Nothing is fit."""

    def __init__(self, column: str = "cnt_lag_1"):
        self.column = column

    def fit(self, X, y=None):
        if self.column not in X.columns:
            raise ValueError(f"persistence baseline needs column {self.column!r}")
        return self

    def predict(self, X):
        return X[self.column].to_numpy(dtype=float)


MODELS = {
    "baseline_mean": DummyRegressor(strategy="mean"),
    "baseline_persistence": PersistenceBaseline("cnt_lag_1"),
    "ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
    "hgb": HistGradientBoostingRegressor(random_state=0, max_iter=300),
}


# --- Exercise 4: target transformations, OFF by default -------------------
# A tree cannot predict above the largest target it was trained on, and
# 2012 demand runs past the 2011 maximum. Each transform below makes the
# model predict something closer to stationary, relative to a level that is
# a lagged feature (known at prediction time), and maps back to rides
# before scoring. `make train` never uses them; reports/metrics.json is the
# untransformed pipeline.


def _ratio28(y, X):
    level = X["cnt_roll_28"].to_numpy(dtype=float)
    assert (level > 0).all(), "cnt_roll_28 must be positive to divide by it"
    return np.asarray(y, dtype=float) / level


def _unratio28(z, X):
    return np.asarray(z, dtype=float) * X["cnt_roll_28"].to_numpy(dtype=float)


def _diff1(y, X):
    return np.asarray(y, dtype=float) - X["cnt_lag_1"].to_numpy(dtype=float)


def _undiff1(z, X):
    return np.asarray(z, dtype=float) + X["cnt_lag_1"].to_numpy(dtype=float)


TARGET_TRANSFORMS = {
    "ratio28": (_ratio28, _unratio28),  # cnt / cnt_roll_28
    "diff1": (_diff1, _undiff1),        # cnt - cnt_lag_1
}


class OnTransformedTarget(BaseEstimator, RegressorMixin):
    """Fit `model` on a transformed target; predict back in rides.

    sklearn's TransformedTargetRegressor cannot do this: its function sees
    only y, and these transforms need a lagged feature from X."""

    def __init__(self, model, transform: str):
        self.model = model
        self.transform = transform

    def fit(self, X, y):
        forward, _ = TARGET_TRANSFORMS[self.transform]
        self.model_ = clone(self.model).fit(X, forward(y, X))
        return self

    def predict(self, X):
        _, inverse = TARGET_TRANSFORMS[self.transform]
        return inverse(self.model_.predict(X), X)


def models_for(target: str = "none") -> dict:
    """The baselines never change; ridge and hgb get the transform."""
    if target == "none":
        return MODELS
    return {
        name: m if name.startswith("baseline") else OnTransformedTarget(m, target)
        for name, m in MODELS.items()
    }


def temporal_split(df: pd.DataFrame):
    """Split by date, never at random. A random split on a time series
    puts tomorrow in train and today in test."""
    train = df[df.dteday <= TRAIN_END]
    valid = df[(df.dteday > TRAIN_END) & (df.dteday <= VALID_END)]
    test = df[df.dteday > VALID_END]
    return train, valid, test


def fit_and_score(target: str = "none", valid_only: bool = False) -> dict:
    """With the defaults this is exactly the committed pipeline. valid_only
    never scores the test split: that is how transforms are compared."""
    df = pd.read_parquet(PROCESSED)
    cols = feature_columns(df)
    train, valid, test = temporal_split(df)
    splits = [("valid", valid)] if valid_only else [("valid", valid), ("test", test)]

    results = {} if target == "none" else {"target": target}
    results.update({
        "n_features": len(cols),
        "features": cols,
        "n_train": len(train),
        "n_valid": len(valid),
        "n_test": len(test),
    })
    for name, model in models_for(target).items():
        model.fit(train[cols], train[TARGET])
        results[name] = {
            split: {
                "r2": round(float(r2_score(part[TARGET], model.predict(part[cols]))), 4),
                "mae": round(float(mean_absolute_error(part[TARGET], model.predict(part[cols]))), 1),
            }
            for split, part in splits
        }
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", choices=["none", *TARGET_TRANSFORMS], default="none",
                    help="Exercise 4 target transform (default: none = the committed pipeline)")
    ap.add_argument("--valid-only", action="store_true",
                    help="score validation only; the test split is never predicted")
    ns = ap.parse_args()
    res = fit_and_score(ns.target, ns.valid_only)
    # Only the untransformed, both-split run may write reports/metrics.json.
    out = (METRICS if ns.target == "none" and not ns.valid_only
           else METRICS.with_name(f"metrics_target_{ns.target}.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2))
    print(json.dumps({k: v for k, v in res.items() if k != "features"}, indent=2))
