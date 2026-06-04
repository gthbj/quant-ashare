"""Preprocessing for the sklearn Strategy 1 runner."""

from __future__ import annotations

import dataclasses
import json
from typing import Iterable

import numpy as np
import pandas as pd


@dataclasses.dataclass
class MedianWinsorZScorePreprocessor:
    """Train-split-only median fill, winsorization and z-score scaling."""

    feature_columns: list[str]
    winsor_lower: float = 0.01
    winsor_upper: float = 0.99
    medians_: dict[str, float] = dataclasses.field(default_factory=dict)
    lower_: dict[str, float] = dataclasses.field(default_factory=dict)
    upper_: dict[str, float] = dataclasses.field(default_factory=dict)
    means_: dict[str, float] = dataclasses.field(default_factory=dict)
    stds_: dict[str, float] = dataclasses.field(default_factory=dict)

    def fit(self, frame: pd.DataFrame) -> "MedianWinsorZScorePreprocessor":
        numeric = _coerce_numeric(frame, self.feature_columns)
        for col in self.feature_columns:
            series = numeric[col].astype("float64")
            median = float(np.nanmedian(series)) if series.notna().any() else 0.0
            filled = series.fillna(median)
            lower = float(filled.quantile(self.winsor_lower))
            upper = float(filled.quantile(self.winsor_upper))
            clipped = filled.clip(lower=lower, upper=upper)
            mean = float(clipped.mean())
            std = float(clipped.std(ddof=0))
            if not np.isfinite(std) or std <= 1e-12:
                std = 1.0
            self.medians_[col] = median
            self.lower_[col] = lower
            self.upper_[col] = upper
            self.means_[col] = mean
            self.stds_[col] = std
        return self

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        numeric = _coerce_numeric(frame, self.feature_columns)
        cols = []
        for col in self.feature_columns:
            series = numeric[col].astype("float64")
            series = series.fillna(self.medians_.get(col, 0.0))
            series = series.clip(
                lower=self.lower_.get(col, -np.inf),
                upper=self.upper_.get(col, np.inf),
            )
            series = (series - self.means_.get(col, 0.0)) / self.stds_.get(col, 1.0)
            cols.append(series.to_numpy(dtype=np.float32))
        return np.column_stack(cols).astype(np.float32)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "preprocess_version": "sklearn_median_winsor_zscore_v1",
            "feature_columns": self.feature_columns,
            "winsor_lower": self.winsor_lower,
            "winsor_upper": self.winsor_upper,
            "medians": self.medians_,
            "lower": self.lower_,
            "upper": self.upper_,
            "means": self.means_,
            "stds": self.stds_,
        }


def feature_frame_from_panel(panel: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Expand ADS feature JSON into a numeric feature frame.

    `ads_ml_training_panel_daily.feature_column_list` is the contract for feature
    order. The JSON can contain extra diagnostic fields such as `board`; those
    are ignored unless listed in `feature_column_list`.
    """
    if panel.empty:
        raise ValueError("training panel is empty")
    feature_columns = _first_feature_columns(panel["feature_column_list"])
    records = []
    for payload in panel["feature_values_json"]:
        parsed = json.loads(payload or "{}")
        records.append({col: parsed.get(col) for col in feature_columns})
    return pd.DataFrame.from_records(records, columns=feature_columns), feature_columns


def _first_feature_columns(values: Iterable[object]) -> list[str]:
    for value in values:
        if isinstance(value, list):
            return [str(v) for v in value]
        if isinstance(value, tuple):
            return [str(v) for v in value]
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(v) for v in parsed]
            except json.JSONDecodeError:
                continue
    raise ValueError("feature_column_list is empty or unparseable")


def _coerce_numeric(frame: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    for col in feature_columns:
        series = frame[col] if col in frame.columns else pd.Series(np.nan, index=frame.index)
        if series.dtype == bool:
            out[col] = series.astype("float64")
        else:
            out[col] = pd.to_numeric(series, errors="coerce")
    return out
