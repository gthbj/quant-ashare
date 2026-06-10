from __future__ import annotations

import pandas as pd

from scripts.strategy1_cloudrun.train_predict import dynamic_cv_folds


def test_dynamic_cv_folds_use_train_years_and_exclude_valid_year() -> None:
    rows = []
    for year in range(2015, 2020):
        rows.extend([
            {"trade_date": f"{year}-01-03", "split_tag": "train"},
            {"trade_date": f"{year}-12-29", "split_tag": "train"},
        ])
    rows.extend([
        {"trade_date": "2020-01-02", "split_tag": "valid"},
        {"trade_date": "2020-12-24", "split_tag": "valid"},
    ])

    folds = dynamic_cv_folds(pd.DataFrame(rows))

    assert [fold[0] for fold in folds] == ["cv_2017", "cv_2018", "cv_2019"]
    assert folds[-1] == ("cv_2019", "2015-01-03", "2018-12-29", "2019-01-03", "2019-12-29")


def test_dynamic_cv_folds_preserve_existing_2019_to_2023_search_shape() -> None:
    rows = []
    for year in range(2019, 2024):
        rows.extend([
            {"trade_date": f"{year}-01-03", "split_tag": "train"},
            {"trade_date": f"{year}-12-29", "split_tag": "train"},
        ])
    rows.append({"trade_date": "2024-01-02", "split_tag": "valid"})

    folds = dynamic_cv_folds(pd.DataFrame(rows))

    assert [fold[0] for fold in folds] == ["cv_2021", "cv_2022", "cv_2023"]
