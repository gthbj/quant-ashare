"""Owner-approved Strategy1 research-to-ADS promotion."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Iterable

from google.cloud import bigquery

from quant_ashare.strategy1.table_roles import resolve_table_role


PROMOTION_CODE_VERSION = "strategy1_research_promotion_v1"
DEFAULT_PROJECT = "data-aquarium"
DEFAULT_LOCATION = "asia-east2"


@dataclasses.dataclass(frozen=True)
class PromotionTableSpec:
    role: str
    columns: tuple[str, ...]
    source_predicate: str
    target_predicate: str
    lifecycle_predicate: str
    source_row_assertion: str | None = None
    lifecycle_set_sql: str = "research_status = 'accepted', promotion_status = 'promoted'"


TRAINING_PANEL_COLUMNS = (
    "run_id", "strategy_id", "model_id", "preprocess_version", "feature_version",
    "label_version", "universe_version", "trade_date", "sec_code", "horizon",
    "split_fold", "split_tag", "sample_weight", "target_label", "target_return",
    "feature_values_json", "feature_column_list", "created_at",
)
MODEL_REGISTRY_COLUMNS = (
    "model_id", "strategy_id", "model_family", "horizon", "feature_version",
    "label_version", "preprocess_version", "train_start_date", "train_end_date",
    "valid_start_date", "valid_end_date", "model_params_json", "metrics_json",
    "model_uri", "git_commit", "status", "created_at",
)
PREDICTION_COLUMNS = (
    "model_id", "predict_date", "horizon", "sec_code", "score", "raw_score",
    "score_orientation", "rank_raw", "rank_pct", "feature_version", "run_id", "created_at",
)
CANDIDATE_COLUMNS = (
    "strategy_id", "rebalance_date", "sec_code", "model_id", "horizon", "score",
    "rank_raw", "rank_pct", "in_universe_default", "is_selected_candidate",
    "filter_reason", "run_id", "created_at",
)
TARGET_COLUMNS = (
    "strategy_id", "rebalance_date", "sec_code", "target_weight", "target_shares",
    "target_amount_cny", "model_id", "horizon", "run_id", "created_at",
)
ORDER_COLUMNS = (
    "strategy_id", "rebalance_date", "sec_code", "side", "order_weight_delta",
    "order_shares", "expected_price", "expected_amount_cny", "order_reason",
    "run_id", "created_at",
)
TRADE_COLUMNS = (
    "backtest_id", "trade_date", "sec_code", "side", "planned_shares",
    "filled_shares", "fill_price", "turnover_cny", "fee_cny", "tax_cny",
    "slippage_cny", "cash_effect_cny", "fill_status", "run_id", "created_at",
)
POSITION_COLUMNS = (
    "backtest_id", "trade_date", "sec_code", "shares", "close",
    "market_value_cny", "weight", "unrealized_pnl_cny", "run_id", "created_at",
)
NAV_COLUMNS = (
    "backtest_id", "trade_date", "nav", "cash_cny", "net_value_cny",
    "gross_exposure", "turnover_cny", "cost_cny", "daily_return",
    "benchmark_sec_code", "benchmark_return", "excess_return", "run_id", "created_at",
)
LEDGER_STATE_COLUMNS = (
    "backtest_id", "trade_date", "cash_cny", "net_value_cny", "nav",
    "pending_sell_sec_codes_json", "active_signal_date", "active_target_weights_json",
    "holdings_hash", "ledger_version", "ledger_params_hash", "resume_policy_id",
    "rebalance_anchor_start", "run_id", "created_at",
)
SUMMARY_COLUMNS = (
    "backtest_id", "strategy_id", "model_id", "start_date", "end_date",
    "total_return", "annual_return", "compound_annual_return", "return_period_count",
    "annualization_target_period_count", "annualization_method", "annual_vol",
    "sharpe", "max_drawdown", "turnover_annual", "benchmark_sec_code",
    "excess_return", "information_ratio", "cost_bps", "metrics_json", "created_at",
)
SIGNAL_MONITOR_COLUMNS = (
    "strategy_id", "model_id", "trade_date", "sample_count", "prediction_count",
    "candidate_count", "avg_score", "score_std", "not_tradable_entry_count",
    "metrics_json", "run_id", "created_at",
)


PROMOTION_TABLE_SPECS: dict[str, PromotionTableSpec] = {
    "training_panel": PromotionTableSpec(
        role="training_panel",
        columns=TRAINING_PANEL_COLUMNS,
        source_predicate=(
            "run_id = @source_run_id AND trade_date BETWEEN @window_start AND @window_end"
        ),
        target_predicate=(
            "run_id = @source_run_id AND trade_date BETWEEN @window_start AND @window_end"
        ),
        lifecycle_predicate=(
            "run_id = @source_run_id AND trade_date BETWEEN @window_start AND @window_end"
        ),
        source_row_assertion="training panel source rows are missing",
    ),
    "model_registry": PromotionTableSpec(
        role="model_registry",
        columns=MODEL_REGISTRY_COLUMNS,
        source_predicate="run_id = @source_run_id AND model_id = @source_model_id",
        target_predicate="model_id = @source_model_id",
        lifecycle_predicate="run_id = @source_run_id AND model_id = @source_model_id",
        source_row_assertion="model registry source row is missing",
        lifecycle_set_sql=(
            "acceptance_status = 'accepted', promotion_status = 'promoted', "
            "promotion_id = @promotion_id, approval_ref = @approval_ref"
        ),
    ),
    "model_prediction_daily": PromotionTableSpec(
        role="model_prediction_daily",
        columns=PREDICTION_COLUMNS,
        source_predicate=(
            "run_id = @source_run_id AND model_id = @source_model_id "
            "AND predict_date BETWEEN @window_start AND @window_end"
        ),
        target_predicate=(
            "run_id = @source_run_id AND model_id = @source_model_id "
            "AND predict_date BETWEEN @window_start AND @window_end"
        ),
        lifecycle_predicate=(
            "run_id = @source_run_id AND model_id = @source_model_id "
            "AND predict_date BETWEEN @window_start AND @window_end"
        ),
        source_row_assertion="prediction source rows are missing",
    ),
    "stock_candidate_daily": PromotionTableSpec(
        role="stock_candidate_daily",
        columns=CANDIDATE_COLUMNS,
        source_predicate=(
            "run_id = @source_run_id AND model_id = @source_model_id "
            "AND rebalance_date BETWEEN @window_start AND @window_end"
        ),
        target_predicate=(
            "run_id = @source_run_id AND model_id = @source_model_id "
            "AND rebalance_date BETWEEN @window_start AND @window_end"
        ),
        lifecycle_predicate=(
            "run_id = @source_run_id AND model_id = @source_model_id "
            "AND rebalance_date BETWEEN @window_start AND @window_end"
        ),
        source_row_assertion="candidate source rows are missing",
    ),
    "portfolio_target_daily": PromotionTableSpec(
        role="portfolio_target_daily",
        columns=TARGET_COLUMNS,
        source_predicate=(
            "run_id = @source_run_id AND model_id = @source_model_id "
            "AND rebalance_date BETWEEN @window_start AND @window_end"
        ),
        target_predicate=(
            "run_id = @source_run_id AND model_id = @source_model_id "
            "AND rebalance_date BETWEEN @window_start AND @window_end"
        ),
        lifecycle_predicate=(
            "run_id = @source_run_id AND model_id = @source_model_id "
            "AND rebalance_date BETWEEN @window_start AND @window_end"
        ),
        source_row_assertion="portfolio target source rows are missing",
    ),
    "order_plan_daily": PromotionTableSpec(
        role="order_plan_daily",
        columns=ORDER_COLUMNS,
        source_predicate=(
            "run_id = @source_run_id AND rebalance_date BETWEEN @window_start AND @window_end"
        ),
        target_predicate=(
            "run_id = @source_run_id AND rebalance_date BETWEEN @window_start AND @window_end"
        ),
        lifecycle_predicate=(
            "run_id = @source_run_id AND rebalance_date BETWEEN @window_start AND @window_end"
        ),
        source_row_assertion="order plan source rows are missing",
    ),
    "backtest_trade_daily": PromotionTableSpec(
        role="backtest_trade_daily",
        columns=TRADE_COLUMNS,
        source_predicate=(
            "backtest_id = @source_backtest_id AND trade_date BETWEEN @window_start AND @window_end"
        ),
        target_predicate=(
            "backtest_id = @source_backtest_id AND trade_date BETWEEN @window_start AND @window_end"
        ),
        lifecycle_predicate=(
            "backtest_id = @source_backtest_id AND trade_date BETWEEN @window_start AND @window_end"
        ),
        source_row_assertion="backtest trade source rows are missing",
    ),
    "backtest_position_daily": PromotionTableSpec(
        role="backtest_position_daily",
        columns=POSITION_COLUMNS,
        source_predicate=(
            "backtest_id = @source_backtest_id AND trade_date BETWEEN @window_start AND @window_end"
        ),
        target_predicate=(
            "backtest_id = @source_backtest_id AND trade_date BETWEEN @window_start AND @window_end"
        ),
        lifecycle_predicate=(
            "backtest_id = @source_backtest_id AND trade_date BETWEEN @window_start AND @window_end"
        ),
        source_row_assertion="backtest position source rows are missing",
    ),
    "backtest_nav_daily": PromotionTableSpec(
        role="backtest_nav_daily",
        columns=NAV_COLUMNS,
        source_predicate=(
            "backtest_id = @source_backtest_id AND trade_date BETWEEN @window_start AND @window_end"
        ),
        target_predicate=(
            "backtest_id = @source_backtest_id AND trade_date BETWEEN @window_start AND @window_end"
        ),
        lifecycle_predicate=(
            "backtest_id = @source_backtest_id AND trade_date BETWEEN @window_start AND @window_end"
        ),
        source_row_assertion="backtest NAV source rows are missing",
    ),
    "backtest_ledger_state_daily": PromotionTableSpec(
        role="backtest_ledger_state_daily",
        columns=LEDGER_STATE_COLUMNS,
        source_predicate=(
            "backtest_id = @source_backtest_id AND trade_date BETWEEN @window_start AND @window_end"
        ),
        target_predicate=(
            "backtest_id = @source_backtest_id AND trade_date BETWEEN @window_start AND @window_end"
        ),
        lifecycle_predicate=(
            "backtest_id = @source_backtest_id AND trade_date BETWEEN @window_start AND @window_end"
        ),
        source_row_assertion="backtest ledger state source rows are missing",
    ),
    "backtest_summary": PromotionTableSpec(
        role="backtest_summary",
        columns=SUMMARY_COLUMNS,
        source_predicate=(
            "run_id = @source_run_id AND backtest_id = @source_backtest_id "
            "AND model_id = @source_model_id"
        ),
        target_predicate="backtest_id = @source_backtest_id",
        lifecycle_predicate=(
            "run_id = @source_run_id AND backtest_id = @source_backtest_id "
            "AND model_id = @source_model_id"
        ),
        source_row_assertion="backtest summary source row is missing",
        lifecycle_set_sql=(
            "acceptance_status = 'accepted', promotion_status = 'promoted', "
            "promotion_id = @promotion_id, approval_ref = @approval_ref"
        ),
    ),
    "signal_monitor_daily": PromotionTableSpec(
        role="signal_monitor_daily",
        columns=SIGNAL_MONITOR_COLUMNS,
        source_predicate=(
            "run_id = @source_run_id AND model_id = @source_model_id "
            "AND trade_date BETWEEN @window_start AND @window_end"
        ),
        target_predicate=(
            "run_id = @source_run_id AND model_id = @source_model_id "
            "AND trade_date BETWEEN @window_start AND @window_end"
        ),
        lifecycle_predicate=(
            "run_id = @source_run_id AND model_id = @source_model_id "
            "AND trade_date BETWEEN @window_start AND @window_end"
        ),
        source_row_assertion="signal monitor source rows are missing",
    ),
}

DEFAULT_PROMOTION_ROLES = (
    "model_registry",
    "model_prediction_daily",
    "stock_candidate_daily",
    "portfolio_target_daily",
    "order_plan_daily",
    "backtest_trade_daily",
    "backtest_position_daily",
    "backtest_nav_daily",
    "backtest_ledger_state_daily",
    "backtest_summary",
    "signal_monitor_daily",
)


@dataclasses.dataclass(frozen=True)
class PromotionRequest:
    promotion_id: str
    source_run_id: str
    source_backtest_id: str
    source_model_id: str
    window_start: str
    window_end: str
    approval_ref: str
    approved_by: str
    acceptance_contract_version: str
    acceptance_contract_sha256: str
    project: str = DEFAULT_PROJECT
    approved_at: datetime | str | None = None
    source_artifact_uri: str | None = None
    source_git_commit: str | None = None
    promotion_code_version: str = PROMOTION_CODE_VERSION
    target_roles: tuple[str, ...] = DEFAULT_PROMOTION_ROLES
    allow_unaccepted: bool = False
    force_replace: bool = False


@dataclasses.dataclass(frozen=True)
class PromotionPlan:
    request: PromotionRequest
    sql: str
    parameters: tuple[
        bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter,
        ...,
    ]
    target_ads_tables: tuple[str, ...]


def build_promotion_plan(request: PromotionRequest) -> PromotionPlan:
    request = normalize_request(request)
    target_ads_tables = tuple(_ads_table_id(role, request.project) for role in request.target_roles)
    sql = build_promotion_sql(request, target_ads_tables)
    return PromotionPlan(
        request=request,
        sql=sql,
        parameters=tuple(promotion_query_parameters(request, target_ads_tables)),
        target_ads_tables=target_ads_tables,
    )


def run_promotion(
    client: bigquery.Client,
    request: PromotionRequest,
    *,
    labels: dict[str, str] | None = None,
) -> bigquery.QueryJob:
    plan = build_promotion_plan(request)
    job_config = bigquery.QueryJobConfig(
        query_parameters=list(plan.parameters),
        labels=labels or {"strategy": "strategy1", "step": "promotion"},
    )
    job = client.query(plan.sql, job_config=job_config)
    job.result()
    return job


def normalize_request(request: PromotionRequest) -> PromotionRequest:
    required = {
        "promotion_id": request.promotion_id,
        "source_run_id": request.source_run_id,
        "source_backtest_id": request.source_backtest_id,
        "source_model_id": request.source_model_id,
        "window_start": request.window_start,
        "window_end": request.window_end,
        "approval_ref": request.approval_ref,
        "approved_by": request.approved_by,
        "acceptance_contract_version": request.acceptance_contract_version,
        "acceptance_contract_sha256": request.acceptance_contract_sha256,
    }
    missing = sorted(name for name, value in required.items() if value in {None, ""})
    if missing:
        raise ValueError(f"missing required promotion fields: {missing}")
    target_roles = tuple(request.target_roles or DEFAULT_PROMOTION_ROLES)
    unknown_roles = sorted(set(target_roles) - set(PROMOTION_TABLE_SPECS))
    if unknown_roles:
        raise ValueError(f"unknown promotion target roles: {unknown_roles}")
    duplicate_roles = sorted({role for role in target_roles if target_roles.count(role) > 1})
    if duplicate_roles:
        raise ValueError(f"duplicate promotion target roles: {duplicate_roles}")
    approved_at = request.approved_at or datetime.now(timezone.utc)
    return dataclasses.replace(request, approved_at=approved_at, target_roles=target_roles)


def promotion_query_parameters(
    request: PromotionRequest,
    target_ads_tables: Iterable[str],
) -> list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter]:
    return [
        bigquery.ScalarQueryParameter("promotion_id", "STRING", request.promotion_id),
        bigquery.ScalarQueryParameter("source_run_id", "STRING", request.source_run_id),
        bigquery.ScalarQueryParameter("source_backtest_id", "STRING", request.source_backtest_id),
        bigquery.ScalarQueryParameter("source_model_id", "STRING", request.source_model_id),
        bigquery.ScalarQueryParameter("window_start", "DATE", request.window_start),
        bigquery.ScalarQueryParameter("window_end", "DATE", request.window_end),
        bigquery.ScalarQueryParameter("approval_ref", "STRING", request.approval_ref),
        bigquery.ScalarQueryParameter("approved_by", "STRING", request.approved_by),
        bigquery.ScalarQueryParameter("approved_at", "TIMESTAMP", request.approved_at),
        bigquery.ScalarQueryParameter("source_artifact_uri", "STRING", request.source_artifact_uri),
        bigquery.ScalarQueryParameter("source_git_commit", "STRING", request.source_git_commit),
        bigquery.ScalarQueryParameter(
            "acceptance_contract_version",
            "STRING",
            request.acceptance_contract_version,
        ),
        bigquery.ScalarQueryParameter(
            "acceptance_contract_sha256",
            "STRING",
            request.acceptance_contract_sha256,
        ),
        bigquery.ScalarQueryParameter(
            "promotion_code_version",
            "STRING",
            request.promotion_code_version,
        ),
        bigquery.ScalarQueryParameter("allow_unaccepted", "BOOL", request.allow_unaccepted),
        bigquery.ScalarQueryParameter("force_replace", "BOOL", request.force_replace),
        bigquery.ArrayQueryParameter("target_ads_tables", "STRING", list(target_ads_tables)),
    ]


def build_promotion_sql(request: PromotionRequest, target_ads_tables: tuple[str, ...]) -> str:
    manifest_table = _research_table_id("promotion_manifest", request.project)
    registry_table = _research_table_id("model_registry", request.project)
    acceptance_table = _research_table_id("acceptance_result", request.project)
    statements = [
        "DECLARE v_promoted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP();",
        "DECLARE v_created_date DATE DEFAULT CURRENT_DATE();",
        "BEGIN TRANSACTION;",
        _manifest_id_guard(manifest_table),
        _accepted_source_guard(registry_table, acceptance_table),
    ]
    for role in request.target_roles:
        statements.extend(_table_copy_statements(PROMOTION_TABLE_SPECS[role], request.project))
    statements.extend([
        _acceptance_lifecycle_update(acceptance_table),
        _manifest_insert(manifest_table, registry_table, acceptance_table),
        "COMMIT TRANSACTION;",
    ])
    return "\n\n".join(statements) + "\n"


def _table_copy_statements(spec: PromotionTableSpec, project: str) -> list[str]:
    source = _research_table_id(spec.role, project)
    target = _ads_table_id(spec.role, project)
    column_list = ", ".join(spec.columns)
    source_select = ", ".join(spec.columns)
    statements = []
    if spec.source_row_assertion:
        statements.append(
            f"""ASSERT (
  SELECT COUNT(*) > 0
  FROM `{source}`
  WHERE {spec.source_predicate}
) AS '{spec.source_row_assertion}';"""
        )
    statements.extend([
        f"""IF NOT @force_replace THEN
  ASSERT (
    SELECT COUNT(*) = 0
    FROM `{target}`
    WHERE {spec.target_predicate}
  ) AS 'target ADS rows already exist for {spec.role}; rerun with force_replace only after owner approval';
END IF;""",
        f"""IF @force_replace THEN
  DELETE FROM `{target}`
  WHERE {spec.target_predicate};
END IF;""",
        f"""INSERT INTO `{target}` ({column_list})
SELECT {source_select}
FROM `{source}`
WHERE {spec.source_predicate};""",
        f"""UPDATE `{source}`
SET {spec.lifecycle_set_sql}
WHERE {spec.lifecycle_predicate};""",
    ])
    return statements


def _manifest_id_guard(manifest_table: str) -> str:
    return f"""ASSERT (
  SELECT COUNT(*) = 0
  FROM `{manifest_table}`
  WHERE promotion_id = @promotion_id
) AS 'promotion_id already exists in research_promotion_manifest';"""


def _accepted_source_guard(registry_table: str, acceptance_table: str) -> str:
    return f"""ASSERT (
  @allow_unaccepted
  OR EXISTS (
    SELECT 1
    FROM `{registry_table}`
    WHERE run_id = @source_run_id
      AND model_id = @source_model_id
      AND acceptance_status = 'accepted'
  )
  OR EXISTS (
    SELECT 1
    FROM `{acceptance_table}`
    WHERE run_id = @source_run_id
      AND backtest_id = @source_backtest_id
      AND model_id = @source_model_id
      AND accepted IS TRUE
      AND acceptance_status = 'accepted'
  )
) AS 'source research result is not accepted; owner-approved promotion requires accepted research unless allow_unaccepted is explicit';"""


def _acceptance_lifecycle_update(acceptance_table: str) -> str:
    return f"""UPDATE `{acceptance_table}`
SET promotion_status = 'promoted',
    promoted = TRUE,
    promotion_manifest_id = @promotion_id,
    approval_ref = @approval_ref
WHERE run_id = @source_run_id
  AND backtest_id = @source_backtest_id
  AND model_id = @source_model_id
  AND accepted IS TRUE
  AND acceptance_status = 'accepted';"""


def _manifest_insert(manifest_table: str, registry_table: str, acceptance_table: str) -> str:
    return f"""INSERT INTO `{manifest_table}` (
  promotion_id,
  source_dataset,
  source_run_id,
  source_backtest_id,
  source_model_id,
  source_artifact_uri,
  target_dataset,
  target_ads_tables,
  acceptance_contract_version,
  acceptance_contract_sha256,
  approval_ref,
  approved_by,
  approved_at,
  source_git_commit,
  promotion_code_version,
  promotion_status,
  promoted_at,
  created_date,
  created_at
)
VALUES (
  @promotion_id,
  'ashare_research',
  @source_run_id,
  @source_backtest_id,
  @source_model_id,
  COALESCE(
    @source_artifact_uri,
    (SELECT ANY_VALUE(artifact_uri) FROM `{registry_table}` WHERE run_id = @source_run_id AND model_id = @source_model_id),
    (SELECT ANY_VALUE(artifact_uri) FROM `{acceptance_table}` WHERE run_id = @source_run_id AND backtest_id = @source_backtest_id AND model_id = @source_model_id)
  ),
  'ashare_ads',
  @target_ads_tables,
  @acceptance_contract_version,
  @acceptance_contract_sha256,
  @approval_ref,
  @approved_by,
  @approved_at,
  COALESCE(
    @source_git_commit,
    (SELECT ANY_VALUE(git_commit) FROM `{registry_table}` WHERE run_id = @source_run_id AND model_id = @source_model_id)
  ),
  @promotion_code_version,
  'succeeded',
  v_promoted_at,
  v_created_date,
  v_promoted_at
);"""


def _research_table_id(role: str, project: str) -> str:
    if role == "promotion_manifest":
        return f"{project}.ashare_research.research_promotion_manifest"
    return resolve_table_role(
        role,
        dataset_role="research",
        project=project,
        allow_future_research=True,
    )


def _ads_table_id(role: str, project: str) -> str:
    return resolve_table_role(role, dataset_role="ads", project=project)
