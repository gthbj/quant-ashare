from __future__ import annotations

import pytest

from quant_ashare.strategy1.promotion import (
    DEFAULT_PROMOTION_ROLES,
    PROMOTION_CODE_VERSION,
    PromotionRequest,
    build_promotion_plan,
)


def _request(**overrides: object) -> PromotionRequest:
    base = {
        "promotion_id": "promo_unit_20260610",
        "source_run_id": "unit_run",
        "source_backtest_id": "unit_bt",
        "source_model_id": "unit_model",
        "window_start": "2024-01-02",
        "window_end": "2024-01-31",
        "approval_ref": "PR-UNIT",
        "approved_by": "owner",
        "approved_at": "2026-06-10T00:00:00Z",
        "acceptance_contract_version": "model_acceptance_contract_v3",
        "acceptance_contract_sha256": "abc123",
        "source_git_commit": "deadbeef",
    }
    base.update(overrides)
    return PromotionRequest(**base)


def test_promotion_plan_defaults_to_publishable_research_outputs() -> None:
    plan = build_promotion_plan(_request())

    assert plan.request.target_roles == DEFAULT_PROMOTION_ROLES
    assert "training_panel" not in plan.request.target_roles
    assert "data-aquarium.ashare_ads.ads_model_registry" in plan.target_ads_tables
    assert "data-aquarium.ashare_ads.ads_backtest_performance_summary" in plan.target_ads_tables
    assert "data-aquarium.ashare_ads.ads_ml_training_panel_daily" not in plan.target_ads_tables
    assert PROMOTION_CODE_VERSION in {p.value for p in plan.parameters if p.name == "promotion_code_version"}


def test_promotion_sql_has_explicit_accepted_guard_and_manifest_insert() -> None:
    plan = build_promotion_plan(_request())
    sql = plan.sql

    assert "source research result is not accepted" in sql
    assert "@allow_unaccepted" in sql
    assert "INSERT INTO `data-aquarium.ashare_research.research_promotion_manifest`" in sql
    assert "'succeeded'" in sql
    assert "UPDATE `data-aquarium.ashare_research.research_acceptance_result`" in sql
    assert "promotion_manifest_id = @promotion_id" in sql
    assert "COMMIT TRANSACTION" in sql


def test_promotion_sql_does_not_rewrite_acceptance_state() -> None:
    sql = build_promotion_plan(_request(allow_unaccepted=True)).sql

    assert "SET acceptance_status = 'accepted'" not in sql
    assert "SET research_status = 'accepted'" not in sql
    assert "research_status = 'accepted'" not in sql
    assert "SET promotion_status = 'promoted'" in sql
    assert "promotion_id = @promotion_id" in sql
    assert "approval_ref = @approval_ref" in sql


def test_promotion_sql_uses_ads_columns_only_and_partition_filters() -> None:
    sql = build_promotion_plan(_request()).sql

    registry_insert = sql.split("INSERT INTO `data-aquarium.ashare_ads.ads_model_registry`", 1)[1]
    registry_insert = registry_insert.split(";", 1)[0]
    assert "acceptance_status" not in registry_insert
    assert "promotion_status" not in registry_insert
    assert "promotion_id" not in registry_insert

    assert "predict_date BETWEEN @window_start AND @window_end" in sql
    assert "rebalance_date BETWEEN @window_start AND @window_end" in sql
    assert "trade_date BETWEEN @window_start AND @window_end" in sql
    assert "promotion window does not cover source backtest summary start_date/end_date" in sql
    assert "source backtest_trade_daily has rows after promotion window" in sql
    assert "source backtest_nav_daily has rows after promotion window" in sql


def test_promotion_plan_validates_approval_and_target_roles() -> None:
    with pytest.raises(ValueError, match="missing required promotion fields"):
        build_promotion_plan(_request(approval_ref=""))

    with pytest.raises(ValueError, match="unknown promotion target roles"):
        build_promotion_plan(_request(target_roles=("not_a_role",)))

    with pytest.raises(ValueError, match="duplicate promotion target roles"):
        build_promotion_plan(_request(target_roles=("model_registry", "model_registry")))


def test_promotion_cli_dry_run_prints_plan_without_bigquery_execution(run_module) -> None:
    result = run_module(
        "scripts.strategy1.promote_research_to_ads",
        [
            "--promotion-id",
            "promo_unit_20260610",
            "--source-run-id",
            "unit_run",
            "--source-backtest-id",
            "unit_bt",
            "--source-model-id",
            "unit_model",
            "--window-start",
            "2024-01-02",
            "--window-end",
            "2024-01-31",
            "--approval-ref",
            "PR-UNIT",
            "--approved-by",
            "owner",
            "--acceptance-contract-version",
            "model_acceptance_contract_v3",
            "--acceptance-contract-sha256",
            "abc123",
            "--dry-run",
        ],
        check=True,
    )

    assert '"promotion_id": "promo_unit_20260610"' in result.stdout
    assert "ads_model_registry" in result.stdout
    assert "ads_ml_training_panel_daily" not in result.stdout
    assert "Review-only mode" in result.stdout


def test_promotion_cli_print_sql_is_review_only_without_execute(run_module) -> None:
    result = run_module(
        "scripts.strategy1.promote_research_to_ads",
        [
            "--promotion-id",
            "promo_unit_20260610",
            "--source-run-id",
            "unit_run",
            "--source-backtest-id",
            "unit_bt",
            "--source-model-id",
            "unit_model",
            "--window-start",
            "2024-01-02",
            "--window-end",
            "2024-01-31",
            "--approval-ref",
            "PR-UNIT",
            "--approved-by",
            "owner",
            "--acceptance-contract-version",
            "model_acceptance_contract_v3",
            "--acceptance-contract-sha256",
            "abc123",
            "--print-sql",
        ],
        check=True,
    )

    assert "--- SQL ---" in result.stdout
    assert "BEGIN TRANSACTION" in result.stdout
    assert "Review-only mode" in result.stdout
