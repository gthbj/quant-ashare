from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from quant_ashare.strategy1 import tail_risk_overlay_ab
from quant_ashare.strategy1.catalog import load_step_catalog
from quant_ashare.strategy1.sql_render import render_sql_step


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_tail_risk_overlay_ab_dry_run_uses_three_research_arms(run_module) -> None:
    proc = run_module(
        "quant_ashare.strategy1.tail_risk_overlay_ab",
        [
            "--dry-run",
            "--run-version",
            "vunit",
            "--prediction-run-id",
            "unit_synth",
            "--synthetic-model-id",
            "unit_model",
            "--manifest-sha256",
            "unit_manifest_sha",
            "--baseline-run-id",
            "unit_synth",
            "--baseline-backtest-id",
            "bt_unit_synth",
        ],
    )

    assert proc.returncode == 0, proc.stderr
    plan = json.loads(proc.stdout)
    assert plan["output_dataset_role"] == "research"
    assert plan["prediction_source"]["prediction_run_id"] == "unit_synth"
    assert [arm["arm"] for arm in plan["arms"]] == ["A1", "A2", "A3"]
    assert [arm["tail_risk_profile_id"] for arm in plan["arms"]] == [
        "individual_risk_guard_v0",
        "market_risk_off_v0",
        "individual_and_market_risk_guard_v0",
    ]
    joined_commands = [" ".join(arm["command"]) for arm in plan["arms"]]
    assert all("quant_ashare.strategy1.backtest_report" in command for command in joined_commands)
    assert all("--skip-tail-risk" in command for command in joined_commands)
    assert all("--skip-qa" in command for command in joined_commands)


def test_tail_risk_overlay_ab_rejects_ads_role_offline(run_module) -> None:
    proc = run_module(
        "quant_ashare.strategy1.tail_risk_overlay_ab",
        [
            "--dry-run",
            "--run-version",
            "vunit",
            "--prediction-run-id",
            "unit_synth",
            "--synthetic-model-id",
            "unit_model",
            "--manifest-sha256",
            "unit_manifest_sha",
            "--baseline-backtest-id",
            "bt_unit_synth",
            "--output-dataset-role",
            "ads",
        ],
    )

    assert proc.returncode != 0
    assert "research-only" in proc.stderr


def test_tail_risk_overlay_ab_qa_catalog_contract_and_research_rendering() -> None:
    catalog = load_step_catalog()
    step = catalog["steps"]["qa_tail_risk_overlay_ab_outputs"]

    assert step["execution_mode"] == "manual_tail_risk_overlay_ab_qa"
    assert step["caller"] == ["quant_ashare.strategy1.tail_risk_overlay_ab"]
    assert set(step["inputs"]) >= {
        "model_registry",
        "model_prediction_daily",
        "stock_universe_daily",
        "stock_candidate_daily",
        "portfolio_target_daily",
        "backtest_trade_daily",
        "backtest_nav_daily",
        "backtest_summary",
    }
    rendered = render_sql_step(
        "qa_tail_risk_overlay_ab_outputs",
        {
            "p_baseline_run_id": "unit_synth",
            "p_baseline_backtest_id": "bt_unit_synth",
            "p_prediction_run_id": "unit_synth",
            "p_strategy_id": "ml_pv_clf_v0",
            "p_synthetic_model_id": "unit_model",
            "p_manifest_sha256": "unit_manifest_sha",
            "p_predict_start": "2021-01-04",
            "p_predict_end": "2026-06-09",
            "p_rebalance_anchor_start": "2021-01-04",
            "p_feature_version": "strategy1_pv_v0_20260601",
            "p_market_state_version": "market_state_v1_20260607",
            "p_a1_run_id": "unit_p1",
            "p_a1_backtest_id": "bt_unit_p1",
            "p_a2_run_id": "unit_p2",
            "p_a2_backtest_id": "bt_unit_p2",
            "p_a3_run_id": "unit_p1p2",
            "p_a3_backtest_id": "bt_unit_p1p2",
            "p_min_tail_risk_skips": 1,
            "p_min_tail_risk_crunch_skips": 1,
            "p_crunch_start": "2024-01-01",
            "p_crunch_end": "2024-02-07",
            "p_preflight_only": True,
        },
        dataset_role="research",
        allow_future_research=True,
    )

    assert "data-aquarium.ashare_ads." not in rendered
    assert "data-aquarium.ashare_research.research_backtest_trade_daily" in rendered
    assert "QA-OVERLAY-2: market state must cover every SSE open date" in rendered
    assert "QA-OVERLAY-9: BUY_SKIPPED_MARKET_RISK_OFF" in rendered
    assert "crunch_excess_return_vs_000852" in rendered


def test_tail_risk_overlay_ab_sql_contains_pre_guard_a2_checks() -> None:
    sql = (REPO_ROOT / "sql/strategy1/qa/qa_tail_risk_overlay_ab_outputs.sql").read_text(encoding="utf-8")

    assert "p_preflight_only" in sql
    assert "LEFT JOIN market_state" in sql
    assert "feat.feature_version = p_feature_version" in sql
    assert "cal_date BETWEEN p_rebalance_anchor_start AND p_predict_end" in sql
    assert "LOGICAL_AND(skip_count >= p_min_tail_risk_skips)" in sql
    assert "LOGICAL_AND(skip_count > 0)" in sql
    assert "QA-OVERLAY-4A: CSI1000 crunch benchmark" in sql
    assert "A2 market-only arm must match baseline candidate rows before ledger guard" in sql
    assert "A2 market-only arm must match baseline portfolio targets before ledger guard" in sql
    assert "contract_sharpe" in sql
    assert "max_drawdown_peak_date" in sql
    assert "buy_skipped_yearly_json" in sql
    assert "crunch_excess_return_vs_000852" in sql


def test_tail_risk_overlay_ab_accepts_gcloud_wait_nonzero_when_execution_succeeded(monkeypatch) -> None:
    monkeypatch.setattr(
        tail_risk_overlay_ab,
        "extract_cloud_run_execution_id",
        lambda stdout, stderr: "strategy1-backtest-report-job-unit",
    )
    monkeypatch.setattr(
        tail_risk_overlay_ab,
        "describe_cloud_run_execution",
        lambda project, region, execution_id: {
            "status": {"conditions": [{"type": "Completed", "state": "True"}]}
        },
    )

    result = tail_risk_overlay_ab.cloud_run_result(
        SimpleNamespace(project="data-aquarium", region="asia-east2"),
        SimpleNamespace(raw={"arm": "A1"}, run_id="unit_run", backtest_id="bt_unit_run"),
        1,
        "Execution [strategy1-backtest-report-job-unit] has completed successfully",
        "gcloud wait returned non-zero after completion",
    )

    assert result["status"] == "succeeded"
    assert result["cloud_run_execution_state"] == "succeeded"
    assert result["wait_returncode_ignored"] is True
