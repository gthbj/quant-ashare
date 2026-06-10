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
    rows = [
        {"trade_date": "2019-04-03", "split_tag": "train"},
        {"trade_date": "2019-12-31", "split_tag": "train"},
    ]
    for year in range(2020, 2024):
        rows.extend([
            {"trade_date": f"{year}-01-01", "split_tag": "train"},
            {"trade_date": f"{year}-12-31", "split_tag": "train"},
        ])
    rows.append({"trade_date": "2024-01-02", "split_tag": "valid"})

    folds = dynamic_cv_folds(pd.DataFrame(rows))

    assert folds == [
        ("cv_2021", "2019-04-03", "2020-12-31", "2021-01-01", "2021-12-31"),
        ("cv_2022", "2019-04-03", "2021-12-31", "2022-01-01", "2022-12-31"),
        ("cv_2023", "2019-04-03", "2022-12-31", "2023-01-01", "2023-12-31"),
    ]
