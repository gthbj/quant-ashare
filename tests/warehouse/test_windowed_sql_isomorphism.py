from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class RegexSubstitution:
    pattern: str
    replacement: str
    reason: str


@dataclass(frozen=True)
class SqlPair:
    name: str
    canonical_path: str
    incremental_path: str
    incremental_marker: str
    token_map: dict[str, str]
    regex_substitutions: tuple[RegexSubstitution, ...] = ()
    incremental_source_kind: str = "insert"


VERSION_NORMALIZATIONS = (
    RegexSubstitution(
        r"__FEATURE_VERSION__ AS __FEATURE_VERSION__",
        "__FEATURE_VERSION__",
        "incremental SQL injects feature_version through DECLARE parameter",
    ),
    RegexSubstitution(
        r"__LABEL_VERSION__ AS __LABEL_VERSION__",
        "__LABEL_VERSION__",
        "incremental SQL injects label_version through DECLARE parameter",
    ),
    RegexSubstitution(
        r"__UNIVERSE_VERSION__ AS __UNIVERSE_VERSION__",
        "__UNIVERSE_VERSION__",
        "incremental SQL injects universe_version through DECLARE parameter",
    ),
)

SQL_PAIRS = (
    SqlPair(
        name="dwd_stock_eod_price",
        canonical_path="sql/dwd/01_dwd_stock_eod_price.sql",
        incremental_path="sql/incremental/01_refresh_stock_dwd_dws_window.sql",
        incremental_marker="INSERT INTO `data-aquarium.ashare_dwd.dwd_stock_eod_price`",
        token_map={
            "dwd_start_date": "__DWD_WRITE_START__",
            "p_dwd_write_start_date": "__DWD_READ_START__",
            "lookback_start_date": "__DWD_READ_START__",
            "dwd_end_date": "__END__",
            "p_write_end_date": "__END__",
            "p_write_floor_date": "__PREV_CLOSE_FLOOR__",
        },
        regex_substitutions=(
            RegexSubstitution(
                r" AND SAFE\.PARSE_DATE\('%Y%m%d', trade_date\) BETWEEN __DWD_READ_START__ AND __END__",
                "",
                "window refresh adds parsed trade_date pruning alongside ODS partition pruning",
            ),
            RegexSubstitution(
                r" AND trade_date IS NOT NULL",
                "",
                "window refresh replaces null checks with parsed trade_date pruning",
            ),
            RegexSubstitution(
                r", prev_close AS \(SELECT sec_code, ARRAY_AGG\(close_hfq IGNORE NULLS ORDER BY trade_date DESC LIMIT 1\)\[SAFE_OFFSET\(0\)\] AS prev_close_hfq FROM `data-aquarium\.ashare_dwd\.dwd_stock_eod_price` WHERE trade_date BETWEEN __PREV_CLOSE_FLOOR__ AND DATE_SUB\(__DWD_READ_START__, INTERVAL 1 DAY\) GROUP BY sec_code\)",
                "",
                "window refresh reads previous persisted close_hfq to compute first refreshed ret_1d",
            ),
            RegexSubstitution(
                r", d\.ingested_at, p\.prev_close_hfq",
                ", d.ingested_at",
                "prev_close_hfq is a window-boundary helper, not an output semantic",
            ),
            RegexSubstitution(
                r" LEFT JOIN prev_close AS p ON u\.sec_code = p\.sec_code",
                "",
                "prev_close_hfq is a window-boundary helper, not a source semantic",
            ),
            RegexSubstitution(
                r"SAFE_DIVIDE\(close_hfq, COALESCE\(LAST_VALUE\(close_hfq IGNORE NULLS\) OVER \(PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING\), prev_close_hfq\)\) - 1\.0 AS ret_1d",
                "__RET_1D__ AS ret_1d",
                "window refresh preserves ret_1d across the write-window boundary",
            ),
            RegexSubstitution(
                r"SAFE_DIVIDE\(close_hfq, LAST_VALUE\(close_hfq IGNORE NULLS\) OVER \(PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING\)\) - 1\.0 AS ret_1d",
                "__RET_1D__ AS ret_1d",
                "full rebuild computes ret_1d inside one continuous CTAS window",
            ),
            RegexSubstitution(
                r" WHERE trade_date BETWEEN __DWD_WRITE_START__ AND __END__$",
                "",
                "incremental DML target already scopes the write window",
            ),
        ),
    ),
    SqlPair(
        name="dwd_stock_eod_valuation",
        canonical_path="sql/dwd/02_dwd_stock_eod_valuation.sql",
        incremental_path="sql/incremental/01_refresh_stock_dwd_dws_window.sql",
        incremental_marker="INSERT INTO `data-aquarium.ashare_dwd.dwd_stock_eod_valuation`",
        token_map={
            "dwd_start_date": "__START__",
            "p_dwd_write_start_date": "__START__",
            "dwd_end_date": "__END__",
            "p_write_end_date": "__END__",
        },
        regex_substitutions=(
            RegexSubstitution(
                r" AND SAFE\.PARSE_DATE\('%Y%m%d', trade_date\) BETWEEN __START__ AND __END__",
                "",
                "window refresh adds parsed trade_date pruning alongside ODS partition pruning",
            ),
        ),
    ),
    SqlPair(
        name="dws_stock_universe_daily",
        canonical_path="sql/dws/01_dws_stock_universe_daily.sql",
        incremental_path="sql/incremental/01_refresh_stock_dwd_dws_window.sql",
        incremental_marker="INSERT INTO `data-aquarium.ashare_dws.dws_stock_universe_daily`",
        token_map={
            "dws_start_date": "__READ_START__",
            "p_feature_read_start_date": "__READ_START__",
            "p_dwd_write_start_date": "__WRITE_START__",
            "dws_end_date": "__END__",
            "p_write_end_date": "__END__",
            "board_allowlist": "__BOARD_ALLOWLIST__",
            "p_board_allowlist": "__BOARD_ALLOWLIST__",
            "min_list_age_td": "__MIN_LIST_AGE__",
            "p_min_list_age_td": "__MIN_LIST_AGE__",
            "min_amount_ma20_cny": "__MIN_AMOUNT__",
            "p_min_amount_ma20_cny": "__MIN_AMOUNT__",
            "min_close_price": "__MIN_CLOSE__",
            "p_min_close_price": "__MIN_CLOSE__",
            "universe_version": "__UNIVERSE_VERSION__",
            "p_universe_version": "__UNIVERSE_VERSION__",
        },
        regex_substitutions=VERSION_NORMALIZATIONS
        + (
            RegexSubstitution(
                r" WHERE trade_date BETWEEN __WRITE_START__ AND __END__$",
                "",
                "incremental DML target already scopes the write window after lookback reads",
            ),
        ),
    ),
    SqlPair(
        name="dws_stock_feature_price_daily",
        canonical_path="sql/dws/02_dws_stock_feature_price_daily.sql",
        incremental_path="sql/incremental/01_refresh_stock_dwd_dws_window.sql",
        incremental_marker="INSERT INTO `data-aquarium.ashare_dws.dws_stock_feature_price_daily`",
        token_map={
            "dws_start_date": "__READ_START__",
            "p_feature_read_start_date": "__READ_START__",
            "dws_end_date": "__END__",
            "p_write_end_date": "__END__",
            "feature_version": "__FEATURE_VERSION__",
            "p_feature_version": "__FEATURE_VERSION__",
            "p_dwd_write_start_date": "__WRITE_START__",
        },
        regex_substitutions=VERSION_NORMALIZATIONS
        + (
            RegexSubstitution(
                r" WHERE trade_date BETWEEN __WRITE_START__ AND __END__$",
                "",
                "incremental DML target already scopes the write window after lookback reads",
            ),
        ),
    ),
    SqlPair(
        name="dws_stock_feature_valuation_daily",
        canonical_path="sql/dws/03_dws_stock_feature_valuation_daily.sql",
        incremental_path="sql/incremental/01_refresh_stock_dwd_dws_window.sql",
        incremental_marker="INSERT INTO `data-aquarium.ashare_dws.dws_stock_feature_valuation_daily`",
        token_map={
            "dws_start_date": "__READ_START__",
            "p_valuation_feature_read_start_date": "__READ_START__",
            "dws_end_date": "__END__",
            "p_write_end_date": "__END__",
            "feature_version": "__FEATURE_VERSION__",
            "p_feature_version": "__FEATURE_VERSION__",
            "p_dwd_write_start_date": "__WRITE_START__",
            "p_valuation_observation_window": "__OBS_WINDOW__",
        },
        regex_substitutions=VERSION_NORMALIZATIONS
        + (
            RegexSubstitution(
                r"WITH base AS \(WITH first_write AS \(SELECT sec_code, MIN\(trade_date\) AS first_write_trade_date FROM `data-aquarium\.ashare_dwd\.dwd_stock_eod_valuation` WHERE trade_date BETWEEN __WRITE_START__ AND __END__ GROUP BY sec_code\), ranked AS \(SELECT v\.sec_code, v\.trade_date, ROW_NUMBER\(\) OVER \(PARTITION BY v\.sec_code ORDER BY v\.trade_date DESC\) AS obs_rank_desc FROM `data-aquarium\.ashare_dwd\.dwd_stock_eod_valuation` AS v JOIN first_write AS f ON v\.sec_code = f\.sec_code AND v\.trade_date <= f\.first_write_trade_date WHERE v\.trade_date BETWEEN __READ_START__ AND __END__\), read_bounds AS \(SELECT sec_code, MIN\(trade_date\) AS read_start_date FROM ranked WHERE obs_rank_desc <= __OBS_WINDOW__ GROUP BY sec_code\) SELECT v\.trade_date, v\.sec_code, v\.turnover_rate, v\.turnover_rate_free_float, v\.volume_ratio, v\.pe, v\.pe_ttm, v\.pb, v\.ps, v\.ps_ttm, v\.dividend_yield, v\.dividend_yield_ttm, v\.total_share, v\.float_share, v\.free_share, v\.total_mv_cny, v\.circ_mv_cny FROM `data-aquarium\.ashare_dwd\.dwd_stock_eod_valuation` AS v JOIN read_bounds AS b ON v\.sec_code = b\.sec_code AND v\.trade_date >= b\.read_start_date WHERE v\.trade_date BETWEEN __READ_START__ AND __END__\), windowed AS",
                "WITH base AS (SELECT trade_date, sec_code, turnover_rate, turnover_rate_free_float, volume_ratio, pe, pe_ttm, pb, ps, ps_ttm, dividend_yield, dividend_yield_ttm, total_share, float_share, free_share, total_mv_cny, circ_mv_cny FROM `data-aquarium.ashare_dwd.dwd_stock_eod_valuation` WHERE trade_date BETWEEN __READ_START__ AND __END__), windowed AS",
                "window refresh computes per-stock valuation read bounds by actual observation count",
            ),
            RegexSubstitution(
                r" WHERE trade_date BETWEEN __WRITE_START__ AND __END__$",
                "",
                "incremental DML target already scopes the write window after valuation lookback reads",
            ),
        ),
    ),
    SqlPair(
        name="dws_stock_feature_fin_daily",
        canonical_path="sql/dws/07_dws_stock_feature_fin_daily.sql",
        incremental_path="sql/incremental/01_refresh_stock_dwd_dws_window.sql",
        incremental_marker="INSERT INTO `data-aquarium.ashare_dws.dws_stock_feature_fin_daily`",
        token_map={
            "dws_start_date": "__START__",
            "p_dwd_write_start_date": "__START__",
            "dws_end_date": "__END__",
            "p_write_end_date": "__END__",
            "feature_version": "__FEATURE_VERSION__",
            "p_fin_feature_version": "__FEATURE_VERSION__",
            "asof_lookback_days": "__ASOF_DAYS__",
            "p_asof_lookback_days": "__ASOF_DAYS__",
        },
        regex_substitutions=VERSION_NORMALIZATIONS,
    ),
    SqlPair(
        name="dws_stock_label_daily",
        canonical_path="sql/dws/04_dws_stock_label_daily.sql",
        incremental_path="sql/incremental/01_refresh_stock_dwd_dws_window.sql",
        incremental_marker="INSERT INTO `data-aquarium.ashare_dws.dws_stock_label_daily`",
        token_map={
            "dws_start_date": "__LABEL_WRITE_START__",
            "p_label_read_start_date": "__LABEL_READ_START__",
            "p_label_write_start_date": "__LABEL_WRITE_START__",
            "dws_end_date": "__LABEL_WRITE_END__",
            "p_label_read_end_date": "__LABEL_READ_END__",
            "p_write_end_date": "__LABEL_WRITE_END__",
            "label_version": "__LABEL_VERSION__",
            "p_label_version": "__LABEL_VERSION__",
        },
        regex_substitutions=VERSION_NORMALIZATIONS
        + (
            RegexSubstitution(
                r"DATE_ADD\(__LABEL_WRITE_END__, INTERVAL 45 DAY\)",
                "__LABEL_WRITE_END__",
                "window refresh reads forward label exits beyond the output write window",
            ),
            RegexSubstitution(
                r" WHERE b\.trade_date BETWEEN __LABEL_WRITE_START__ AND __LABEL_WRITE_END__",
                "",
                "incremental DML target scopes label output dates after forward-look reads",
            ),
        ),
    ),
    SqlPair(
        name="dws_stock_feature_daily_v0",
        canonical_path="sql/dws/05_dws_stock_feature_daily_v0.sql",
        incremental_path="sql/incremental/01_refresh_stock_dwd_dws_window.sql",
        incremental_marker="INSERT INTO `data-aquarium.ashare_dws.dws_stock_feature_daily_v0`",
        token_map={
            "dws_start_date": "__START__",
            "p_label_write_start_date": "__START__",
            "p_dwd_write_start_date": "__START__",
            "dws_end_date": "__END__",
            "p_write_end_date": "__END__",
            "target_feature_version": "__FEATURE_VERSION__",
            "feature_version": "__FEATURE_VERSION__",
            "p_feature_version": "__FEATURE_VERSION__",
        },
        regex_substitutions=VERSION_NORMALIZATIONS,
    ),
    SqlPair(
        name="dws_stock_sample_daily",
        canonical_path="sql/dws/06_dws_stock_sample_daily.sql",
        incremental_path="sql/incremental/01_refresh_stock_dwd_dws_window.sql",
        incremental_marker="INSERT INTO `data-aquarium.ashare_dws.dws_stock_sample_daily`",
        token_map={
            "dws_start_date": "__START__",
            "p_label_write_start_date": "__START__",
            "p_dwd_write_start_date": "__START__",
            "dws_end_date": "__END__",
            "p_write_end_date": "__END__",
            "target_feature_version": "__FEATURE_VERSION__",
            "p_feature_version": "__FEATURE_VERSION__",
            "target_label_version": "__LABEL_VERSION__",
            "p_label_version": "__LABEL_VERSION__",
        },
        regex_substitutions=VERSION_NORMALIZATIONS,
    ),
    SqlPair(
        name="dwd_index_eod",
        canonical_path="sql/dwd/04_dwd_index_eod.sql",
        incremental_path="sql/incremental/02_refresh_index_dwd_window.sql",
        incremental_marker="INSERT INTO `data-aquarium.ashare_dwd.dwd_index_eod`",
        token_map={
            "dwd_start_date": "__START__",
            "p_write_start_date": "__START__",
            "dwd_end_date": "__END__",
            "p_write_end_date": "__END__",
        },
        regex_substitutions=(
            RegexSubstitution(
                r"SAFE\.PARSE_DATE\('%Y%m%d', trade_date\)",
                "SAFE.PARSE_DATE('%Y%m%d', d.trade_date)",
                "incremental SQL qualifies index_daily.trade_date in the joined query",
            ),
        ),
    ),
    SqlPair(
        name="dws_market_state_daily",
        canonical_path="sql/dws/08_dws_market_state_daily.sql",
        incremental_path="sql/incremental/03_refresh_market_state_window.sql",
        incremental_marker="MERGE `data-aquarium.ashare_dws.dws_market_state_daily`",
        incremental_source_kind="merge_source",
        token_map={
            "dws_start_date": "__WRITE_START__",
            "p_write_start_date": "__WRITE_START__",
            "lookback_start_date": "__READ_START__",
            "p_read_start_date": "__READ_START__",
            "dws_end_date": "__END__",
            "p_write_end_date": "__END__",
            "feature_version": "__FEATURE_VERSION__",
            "p_feature_version": "__FEATURE_VERSION__",
            "market_state_versions": "__MARKET_STATE_VERSIONS__",
            "p_market_state_versions": "__MARKET_STATE_VERSIONS__",
        },
        regex_substitutions=VERSION_NORMALIZATIONS,
    ),
)


def test_windowed_sql_select_bodies_match_canonical_sources() -> None:
    """Guard copied window-refresh SELECT bodies against silent drift.

    Any feature semantic change to the canonical DWD/DWS SQL must be mirrored in
    its window-refresh counterpart. The substitutions below are only for window
    boundaries, parameter naming, and documented refresh-only helper logic; if a
    SQL anchor or helper block changes, update the matching substitution and its
    reason in the same PR instead of widening an exemption.
    """

    assert len(SQL_PAIRS) == 11
    for pair in SQL_PAIRS:
        assert all(item.reason for item in pair.regex_substitutions), pair.name
        canonical = _normalized_canonical(pair)
        incremental = _normalized_incremental(pair)
        assert incremental == canonical, pair.name


def test_windowed_sql_guard_fails_on_seeded_mutation() -> None:
    pair = next(item for item in SQL_PAIRS if item.name == "dws_stock_feature_price_daily")
    mutated = _canonical_query(pair.canonical_path).replace("ret_20d", "ret_21d", 1)

    assert _normalize(mutated, pair) != _normalized_incremental(pair)


@pytest.mark.parametrize(
    ("pair_name", "mutation"),
    [
        (
            "dws_stock_feature_valuation_daily",
            lambda sql: sql.replace("v.pe_ttm,", "v.pe,", 1),
        ),
        (
            "dws_stock_feature_valuation_daily",
            lambda sql: sql.replace("obs_rank_desc <= p_valuation_observation_window", "obs_rank_desc <= 5", 1),
        ),
        (
            "dwd_stock_eod_price",
            lambda sql: sql.replace(
                "partition_date BETWEEN FORMAT_DATE('%Y%m%d', p_dwd_write_start_date)",
                "partition_date BETWEEN FORMAT_DATE('%Y%m%d', p_write_floor_date)",
                1,
            ),
        ),
        (
            "dws_stock_label_daily",
            lambda sql: sql.replace(
                "WHERE b.trade_date BETWEEN p_label_write_start_date AND p_write_end_date",
                "WHERE b.trade_date BETWEEN p_label_read_start_date AND p_write_end_date",
                1,
            ),
        ),
    ],
)
def test_windowed_sql_guard_fails_on_review_seeded_incremental_mutations(pair_name: str, mutation) -> None:
    pair = next(item for item in SQL_PAIRS if item.name == pair_name)
    if pair.incremental_source_kind == "merge_source":
        incremental = _incremental_merge_source(pair.incremental_path)
    else:
        incremental = _incremental_insert_query(pair.incremental_path, pair.incremental_marker)
    mutated = mutation(incremental)

    assert mutated != incremental
    assert _normalize(mutated, pair) != _normalized_canonical(pair)


def _normalized_canonical(pair: SqlPair) -> str:
    return _normalize(_canonical_query(pair.canonical_path), pair)


def _normalized_incremental(pair: SqlPair) -> str:
    if pair.incremental_source_kind == "merge_source":
        sql = _incremental_merge_source(pair.incremental_path)
    else:
        sql = _incremental_insert_query(pair.incremental_path, pair.incremental_marker)
    return _normalize(sql, pair)


def _canonical_query(path: str) -> str:
    sql = _strip_line_comments((REPO_ROOT / path).read_text(encoding="utf-8"))
    match = re.search(r"\)\s+AS\s+((?:WITH|SELECT)\b)", sql, re.S)
    assert match is not None, path
    end_match = re.search(r";\s*\n\s*ALTER TABLE\b", sql[match.start(1):], re.S)
    assert end_match is not None, path
    return sql[match.start(1):match.start(1) + end_match.start()]


def _incremental_insert_query(path: str, marker: str) -> str:
    sql = _strip_line_comments((REPO_ROOT / path).read_text(encoding="utf-8"))
    marker_index = sql.index(marker)
    match = re.search(r"\)\s+((?:WITH|SELECT)\b)", sql[marker_index:], re.S)
    assert match is not None, marker
    start = marker_index + match.start(1)
    end = sql.index(";", start)
    return sql[start:end]


def _incremental_merge_source(path: str) -> str:
    sql = _strip_line_comments((REPO_ROOT / path).read_text(encoding="utf-8"))
    match = re.search(r"USING\s*\(\s*((?:WITH|SELECT)\b.*)\)\s+AS\s+source\s+ON", sql, re.S)
    assert match is not None, path
    return match.group(1)


def _normalize(sql: str, pair: SqlPair) -> str:
    out = _compact_sql(sql)
    for source, target in sorted(pair.token_map.items(), key=lambda item: -len(item[0])):
        out = re.sub(rf"\b{re.escape(source)}\b", target, out)
    for substitution in pair.regex_substitutions:
        out = re.sub(substitution.pattern, substitution.replacement, out)
    return _compact_sql(out)


def _compact_sql(sql: str) -> str:
    out = re.sub(r"\s+", " ", sql).strip()
    out = re.sub(r"\(\s+", "(", out)
    out = re.sub(r"\s+\)", ")", out)
    out = re.sub(r"\s+,", ",", out)
    out = re.sub(r",\s+", ", ", out)
    return out


def _strip_line_comments(sql: str) -> str:
    return "\n".join(
        line.rstrip()
        for line in sql.splitlines()
        if not line.strip().startswith("--")
    )
