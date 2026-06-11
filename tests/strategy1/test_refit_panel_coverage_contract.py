from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from quant_ashare.strategy1.catalog import repo_path
from quant_ashare.strategy1.refit_register_predict import _assert_panel_covers_open_dates


def test_refit_panel_coverage_helper_rejects_internal_open_day_gap() -> None:
    panel_dates = pd.Series([date(2019, 1, 2), date(2019, 1, 4)])
    open_dates = [date(2019, 1, 2), date(2019, 1, 3), date(2019, 1, 4)]

    with pytest.raises(RuntimeError, match="missing 1 SSE open dates"):
        _assert_panel_covers_open_dates(
            panel_dates=panel_dates,
            open_dates=open_dates,
            context="source panel refit train window",
        )


def test_refit_panel_coverage_helper_accepts_complete_open_days() -> None:
    panel_dates = pd.Series([date(2019, 1, 2), date(2019, 1, 3), date(2019, 1, 4)])
    open_dates = [date(2019, 1, 2), date(2019, 1, 3), date(2019, 1, 4)]

    _assert_panel_covers_open_dates(
        panel_dates=panel_dates,
        open_dates=open_dates,
        context="source panel refit train window",
    )


def test_refit_qa_sql_checks_internal_open_day_coverage() -> None:
    sql = repo_path("sql/strategy1/qa/qa_refit_register_predict_outputs.sql").read_text(encoding="utf-8")

    assert "QA-REFIT-4: source panel must have labeled rows for every SSE open day" in sql
    assert "QA-REFIT-5: refit predictions must have rows for every SSE open day" in sql
    assert "data-aquarium.ashare_dim.dim_trade_calendar" in sql
    assert "COUNTIF(source_panel_days.trade_date IS NULL) = 0" in sql
    assert "AND tp.target_label IS NOT NULL" in sql
    assert "COUNTIF(prediction_days.predict_date IS NULL) = 0" in sql
