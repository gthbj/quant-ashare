"""label-safe 年末截断（真实交易日历，PRD_06）的结构性 + 可选 BQ 对账测试。

冻结派生表 LABEL_SAFE_YEAR_END_BY_HORIZON 取自 dim_trade_calendar（SSE 开市日 + trade_date_seq）。
离线结构性测试恒跑；与 dim_trade_calendar 的逐值对账需 `RUN_BQ_RECON=1` + BQ 凭据时才跑。
"""

from __future__ import annotations

import datetime as dt
import os

import pytest

from quant_ashare.strategy1.annual_rolling_plan import (
    LABEL_SAFE_YEAR_END_BY_HORIZON,
    LAST_TRADING_DAY_BY_YEAR,
    label_safe_year_end,
)


def test_label_safe_year_end_returns_frozen_values() -> None:
    for horizon, by_year in LABEL_SAFE_YEAR_END_BY_HORIZON.items():
        for year, expected in by_year.items():
            assert label_safe_year_end(year, horizon) == expected


def test_label_safe_year_end_structural_invariants() -> None:
    # horizon 越大、截断越早；都落在年末（11/12 月）且严格早于该年最后开市日。
    for year in LABEL_SAFE_YEAR_END_BY_HORIZON[5]:
        d5 = dt.date.fromisoformat(LABEL_SAFE_YEAR_END_BY_HORIZON[5][year])
        d10 = dt.date.fromisoformat(LABEL_SAFE_YEAR_END_BY_HORIZON[10][year])
        d20 = dt.date.fromisoformat(LABEL_SAFE_YEAR_END_BY_HORIZON[20][year])
        assert d5 > d10 > d20, (year, d5, d10, d20)
        assert d5.year == year and d5.month == 12
        assert d20.month in (11, 12)
        assert d5 < dt.date.fromisoformat(LAST_TRADING_DAY_BY_YEAR[year])


def test_label_safe_year_end_fail_fast_on_uncovered() -> None:
    with pytest.raises(ValueError):
        label_safe_year_end(2026, 5)  # 2026 无完整年末，未派生
    with pytest.raises(ValueError):
        label_safe_year_end(2021, 7)  # 仅冻结派生了 5/10/20


@pytest.mark.skipif(
    os.environ.get("RUN_BQ_RECON") != "1",
    reason="dim_trade_calendar 对账需显式 RUN_BQ_RECON=1 + BQ 凭据",
)
def test_label_safe_year_end_reconciles_with_dim_trade_calendar() -> None:
    from google.cloud import bigquery

    client = bigquery.Client(project="data-aquarium")
    sql = """
    WITH cal AS (
      SELECT cal_date, trade_date_seq
      FROM `data-aquarium.ashare_dim.dim_trade_calendar`
      WHERE exchange='SSE' AND is_open=1 AND cal_date BETWEEN '2014-10-01' AND '2025-12-31'
    ), lastd AS (
      SELECT EXTRACT(YEAR FROM cal_date) AS y, MAX(trade_date_seq) AS last_seq
      FROM cal GROUP BY 1
    )
    SELECT l.y AS year, h AS horizon, c.cal_date AS safe_end
    FROM lastd l, UNNEST([5, 10, 20]) AS h
    JOIN cal c ON c.trade_date_seq = l.last_seq - h
    WHERE l.y BETWEEN 2015 AND 2025
    """
    rows = list(client.query(sql, location="asia-east2").result())
    assert rows, "dim_trade_calendar 对账查询无结果"
    for row in rows:
        year, horizon, safe_end = int(row["year"]), int(row["horizon"]), row["safe_end"].isoformat()
        assert LABEL_SAFE_YEAR_END_BY_HORIZON[horizon][year] == safe_end, (year, horizon)
        assert label_safe_year_end(year, horizon) == safe_end
