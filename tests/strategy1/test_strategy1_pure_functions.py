from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from quant_ashare.strategy1.acceptance import (
    _failed_reasons,
    _hard_reject_reasons,
    _needs_more_evidence_reasons,
    _unmatched_input_state_reasons,
    decide_acceptance,
    derive_final_holdout_status,
    load_acceptance_contract,
)
from quant_ashare.strategy1.select_register_predict import (
    rank_candidates,
    ranking_sort_key,
    select_candidate,
)
from quant_ashare.strategy1.train_predict import (
    CandidateResult,
    classify_valid_signal,
    decide_orientation,
    evaluate_cv_folds,
    model_complexity_rank,
)
from scripts.strategy1_cloudrun.config import RunnerConfig


def _accepted_v3_row(**overrides) -> dict[str, object]:
    row = {
        "execution_status": "succeeded",
        "qa_status": "succeeded",
        "report_uri": "gs://unit/report.md",
        "model_diagnosis_uri": "gs://unit/diagnosis.json",
        "v3_acceptance_status": "accepted",
        "v3_acceptance_reasons": [],
        "v3_final_holdout_gate_status": "diagnostic_pass",
    }
    row.update(overrides)
    return row


def _legacy_threshold_row(**overrides) -> dict[str, object]:
    row = {
        "valid_rank_ic_mean": 0.01,
        "valid_top_minus_bottom_fwd_ret_mean": 0.01,
        "test_rank_ic_mean": 0.01,
        "test_top_minus_bottom_fwd_ret_mean": 0.01,
        "test_year_excess_return_vs_primary_benchmark": 0.01,
        "overall_excess_return_vs_primary_benchmark": 0.01,
        "total_return": 0.01,
        "sharpe": 0.70,
        "max_drawdown": -0.25,
        "final_holdout_excess_return_vs_primary_benchmark": 0.0,
        "final_holdout_total_return": 0.0,
        "final_holdout_trading_days": 40,
        "cv_confirmation_status": "passed",
        "score_orientation": "identity",
        "valid_signal_status": "stable",
        "acceptance_contract_version": "model_acceptance_contract_v3",
        "test_reuse_wave_no": 1,
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    ("row", "expected_status", "expected_reason"),
    [
        (_accepted_v3_row(), "accepted", "all_acceptance_contract_gates_passed"),
        (
            _accepted_v3_row(
                v3_acceptance_status="rejected",
                v3_acceptance_reasons=["v3_sharpe_ratio<0.7"],
            ),
            "rejected",
            "v3_sharpe_ratio<0.7",
        ),
        (
            _accepted_v3_row(v3_acceptance_status=None, v3_acceptance_reasons=None),
            "rejected",
            "v3_acceptance_metrics=missing",
        ),
    ],
)
def test_decide_acceptance_v3_status_matrix(
    row: dict[str, object],
    expected_status: str,
    expected_reason: str,
) -> None:
    contract = load_acceptance_contract()

    status, reason, derived = decide_acceptance(row, contract)

    assert status == expected_status
    assert reason == expected_reason
    assert derived["v3_acceptance_status"] == expected_status


def test_decide_acceptance_v3_sets_holdout_watch_flag_on_diagnostic_warn() -> None:
    contract = load_acceptance_contract()

    status, _, derived = decide_acceptance(
        _accepted_v3_row(v3_final_holdout_gate_status="diagnostic_warn"),
        contract,
    )

    assert status == "accepted"
    assert derived["holdout_watch_flag"] is True


def test_v3_contract_routes_missing_v3_metrics_before_legacy_acceptance_path() -> None:
    contract = load_acceptance_contract()
    row = _legacy_threshold_row(
        execution_status="succeeded",
        qa_status="succeeded",
        report_uri="gs://unit/report.md",
        model_diagnosis_uri="gs://unit/diagnosis.json",
    )

    status, reason, derived = decide_acceptance(row, contract)

    assert status == "rejected"
    assert reason == "v3_acceptance_metrics=missing"
    assert derived["v3_acceptance_status"] == "rejected"


def test_failed_reasons_cover_execution_qa_and_required_artifacts() -> None:
    assert _failed_reasons(
        {
            "execution_status": "failed",
            "qa_status": "failed",
            "report_uri": None,
            "model_diagnosis_uri": None,
        }
    ) == [
        "execution_status=failed",
        "qa_status=failed",
        "report_uri=missing",
        "model_diagnosis_uri=missing",
    ]


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (_legacy_threshold_row(final_holdout_status="owner_override"), "owner_override"),
        (_legacy_threshold_row(), "passed"),
        (_legacy_threshold_row(final_holdout_trading_days=39), "failed"),
        (_legacy_threshold_row(final_holdout_total_return=-0.08), "failed"),
        (_legacy_threshold_row(final_holdout_total_return=None), None),
    ],
)
def test_derive_final_holdout_status_boundaries(row: dict[str, object], expected: str | None) -> None:
    assert derive_final_holdout_status(row, load_acceptance_contract()) == expected


def test_legacy_hard_reject_helper_treats_sharpe_and_drawdown_thresholds_as_inclusive() -> None:
    contract = load_acceptance_contract()

    assert _hard_reject_reasons(_legacy_threshold_row(), contract) == []
    assert "sharpe<0.7" in _hard_reject_reasons(_legacy_threshold_row(sharpe=0.69), contract)
    assert "max_drawdown<-0.25" in _hard_reject_reasons(_legacy_threshold_row(max_drawdown=-0.251), contract)
    assert "valid_rank_ic_mean=missing" in _hard_reject_reasons(_legacy_threshold_row(valid_rank_ic_mean=None), contract)


@pytest.mark.parametrize(
    ("overrides", "expected_reason"),
    [
        ({"valid_rank_ic_mean": 0.0}, "valid_rank_ic_mean<=0.0"),
        ({"valid_top_minus_bottom_fwd_ret_mean": 0.0}, "valid_top_minus_bottom_fwd_ret_mean<=0.0"),
        ({"test_rank_ic_mean": 0.0}, "test_rank_ic_mean<=0.0"),
        ({"test_top_minus_bottom_fwd_ret_mean": 0.0}, "test_top_minus_bottom_fwd_ret_mean<=0.0"),
        ({"test_year_excess_return_vs_primary_benchmark": 0.0}, "test_year_excess_return_vs_primary_benchmark<=0.0"),
        ({"overall_excess_return_vs_primary_benchmark": 0.0}, "overall_excess_return_vs_primary_benchmark<=0.0"),
        ({"total_return": 0.0}, "total_return<=0.0"),
        ({"sharpe": 0.69}, "sharpe<0.7"),
        ({"max_drawdown": -0.251}, "max_drawdown<-0.25"),
        ({"final_holdout_excess_return_vs_primary_benchmark": -0.05}, "final_holdout_excess_return_vs_primary_benchmark<=-0.05"),
        ({"final_holdout_total_return": -0.08}, "final_holdout_total_return<=-0.08"),
        ({"score_orientation": "sideways"}, "score_orientation=sideways"),
        ({"valid_signal_status": "weak"}, "valid_signal_status=weak"),
        ({"model_diagnosis_primary_diagnosis": "signal_inverted"}, "primary_diagnosis=signal_inverted"),
        (
            {"model_diagnosis_primary_diagnosis": "sample_filter_risk", "model_diagnosis_confidence": "high"},
            "primary_diagnosis=sample_filter_risk:high",
        ),
    ],
)
def test_legacy_hard_reject_helper_covers_each_gate(
    overrides: dict[str, object],
    expected_reason: str,
) -> None:
    reasons = _hard_reject_reasons(_legacy_threshold_row(**overrides), load_acceptance_contract())

    assert expected_reason in reasons


def test_legacy_needs_more_evidence_and_unmatched_state_helpers_are_table_driven() -> None:
    contract = load_acceptance_contract()

    evidence = _needs_more_evidence_reasons(
        _legacy_threshold_row(
            cv_confirmation_status="missing",
            final_holdout_trading_days=12,
            final_holdout_total_return=None,
            acceptance_contract_version=None,
            test_reuse_wave_no=4,
            final_holdout_status="failed",
        ),
        contract,
    )
    assert evidence == [
        "cv_confirmation_status=missing",
        "final_holdout_trading_days<40",
        "final_holdout_metrics=missing",
        "test_reuse_wave_no_gt_final_holdout_threshold_without_passed_holdout",
        "acceptance_contract_version=missing",
    ]

    assert _unmatched_input_state_reasons(
        {
            "score_orientation": "sideways",
            "valid_signal_status": "unknown",
            "cv_confirmation_status": "retrying",
        },
        contract,
    ) == [
        "score_orientation=sideways",
        "valid_signal_status=unknown",
        "cv_confirmation_status=retrying",
    ]


def _candidate(candidate_id: str, **metric_overrides) -> CandidateResult:
    metrics = {
        "valid_eval_coverage": 0.90,
        "oriented_valid_rank_ic_mean": 0.03,
        "oriented_valid_rank_ic_icir": 1.2,
        "valid_topn_fwd_ret_mean": 0.004,
        "valid_top_minus_bottom_fwd_ret_mean": 0.012,
        "roc_auc": 0.56,
        "cv_confirmation_status": "passed",
        "cv_rank_ic_mean": 0.04,
        "cv_top_minus_bottom_fwd_ret_mean": 0.015,
        "cv_fold_count": 3,
        "score_orientation": "identity",
        "convergence_status": "converged",
        "model_family": "logistic_regression",
        "penalty": "l2",
        "C": 1.0,
        "l1_ratio": None,
    }
    metrics.update(metric_overrides)
    return CandidateResult(
        candidate_id=candidate_id,
        model=None,
        score_orientation=str(metrics.get("score_orientation")),
        orientation_reason="unit",
        raw_valid_scores=np.array([], dtype=float),
        oriented_valid_scores=np.array([], dtype=float),
        metrics=metrics,
        model_params={"candidate_id": candidate_id},
    )


def test_rank_candidates_orders_shortlist_and_respects_top_k() -> None:
    rows = rank_candidates(
        [
            _candidate("runner_up", cv_rank_ic_mean=0.04),
            _candidate("winner", cv_rank_ic_mean=0.05),
            _candidate("third", cv_rank_ic_mean=0.03),
        ],
        top_k=2,
    )

    assert [row["candidate_id"] for row in rows] == ["winner", "runner_up", "third"]
    assert [row["shortlist_rank_valid_only"] for row in rows] == [1, 2, None]
    assert all(row["eligible_for_shortlist"] for row in rows)


def test_rank_candidates_uses_stable_order_for_exact_ties() -> None:
    rows = rank_candidates([_candidate("b"), _candidate("a")], top_k=5)

    assert [row["candidate_id"] for row in rows] == ["b", "a"]


def test_rank_candidates_handles_nan_and_all_nonpositive_valid_signal_fallback() -> None:
    rows = rank_candidates(
        [
            _candidate("zero", oriented_valid_rank_ic_mean=0.0, valid_eval_coverage=math.nan),
            _candidate("negative", oriented_valid_rank_ic_mean=-0.01),
        ],
        top_k=1,
    )

    assert rows[0]["shortlist_rank_valid_only"] == 1
    assert rows[0]["search_failure_status"] == "failed_no_positive_valid_signal"
    assert rows[1]["shortlist_rank_valid_only"] is None


def test_ranking_sort_key_puts_ineligible_rows_after_eligible_rows() -> None:
    eligible = {
        "eligible_for_shortlist": True,
        "cv_rank_ic_mean": math.nan,
        "cv_top_minus_bottom_fwd_ret_mean": math.nan,
        "valid_oriented_rank_ic_mean": math.nan,
        "valid_top_minus_bottom_fwd_ret_mean": math.nan,
        "valid_topn_fwd_ret_mean": math.nan,
        "valid_roc_auc": math.nan,
        "model_complexity_rank": 9,
    }
    ineligible = {**eligible, "eligible_for_shortlist": False, "model_complexity_rank": 0}

    assert ranking_sort_key(eligible) > ranking_sort_key(ineligible)


def test_select_candidate_respects_forced_candidate_and_current_empty_input_behavior() -> None:
    candidates = [_candidate("a"), _candidate("b")]
    ranking = rank_candidates(candidates)

    assert select_candidate(candidates, ranking, "b").candidate_id == "b"
    with pytest.raises(ValueError, match="candidate_id 'missing' not found"):
        select_candidate(candidates, ranking, "missing")
    with pytest.raises(IndexError):
        select_candidate([], [], None)


@pytest.mark.parametrize(
    ("metrics", "expected"),
    [
        ({"oriented_valid_rank_ic_mean": -0.001}, "failed"),
        (
            {
                "oriented_valid_rank_ic_mean": 0.005,
                "oriented_valid_rank_ic_icir": 1.0,
                "valid_topn_fwd_ret_mean": 0.01,
            },
            "weak",
        ),
        (
            {
                "oriented_valid_rank_ic_mean": 0.02,
                "oriented_valid_rank_ic_icir": 1.0,
                "valid_top_minus_bottom_fwd_ret_mean": 0.01,
            },
            "stable",
        ),
        (
            {
                "oriented_valid_rank_ic_mean": 0.02,
                "oriented_valid_rank_ic_icir": -0.1,
                "valid_top_minus_bottom_fwd_ret_mean": 0.01,
            },
            "weak",
        ),
    ],
)
def test_classify_valid_signal_matrix(metrics: dict[str, float], expected: str) -> None:
    assert classify_valid_signal(metrics) == expected


@pytest.mark.parametrize(
    ("raw", "rev", "expected_orientation", "reason_fragment"),
    [
        (
            {"rank_ic_mean": -0.04, "top_minus_bottom": -0.01},
            {"rank_ic_mean": 0.04, "top_minus_bottom": 0.02},
            "reverse_probability",
            "reversed bucket lift better",
        ),
        (
            {"rank_ic_mean": -0.04, "top_minus_bottom": 0.03},
            {"rank_ic_mean": 0.04, "top_minus_bottom": 0.02},
            "identity",
            "bucket lift not better",
        ),
        (
            {"rank_ic_mean": 0.01, "top_minus_bottom": 0.0},
            {"rank_ic_mean": -0.01, "top_minus_bottom": 0.0},
            "identity",
            "near zero",
        ),
        (
            {"rank_ic_mean": 0.04, "top_minus_bottom": 0.01},
            {"rank_ic_mean": -0.04, "top_minus_bottom": -0.01},
            "identity",
            "raw_rank_ic non-negative",
        ),
    ],
)
def test_decide_orientation_matrix(
    raw: dict[str, float],
    rev: dict[str, float],
    expected_orientation: str,
    reason_fragment: str,
) -> None:
    orientation, reason = decide_orientation(raw, rev)

    assert orientation == expected_orientation
    assert reason_fragment in reason


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"model_family": "logistic_regression", "penalty": None}, 0),
        ({"model_family": "logistic_regression", "penalty": "l2"}, 1),
        ({"model_family": "logistic_regression", "penalty": "l1"}, 2),
        ({"model_family": "logistic_regression", "penalty": "elasticnet"}, 3),
        ({"model_family": "logistic_regression", "penalty": "custom"}, 9),
        ({"model_family": "lightgbm_gbdt", "num_leaves": 31, "n_estimators": 300}, 44),
        ({"model_family": "lightgbm_regression", "num_leaves": 31, "n_estimators": 300}, 54),
    ],
)
def test_model_complexity_rank_matrix(params: dict[str, object], expected: int) -> None:
    assert model_complexity_rank(params) == expected


@pytest.mark.parametrize(
    ("cv_panel", "x_cv", "expected_status"),
    [
        (None, None, "missing"),
        (pd.DataFrame(), np.empty((0, 0)), "missing"),
        (
            pd.DataFrame(
                {
                    "trade_date": [pd.Timestamp("2021-01-04")],
                    "split_tag": ["train"],
                    "target_label": [1],
                    "target_return": [0.01],
                    "sample_weight": [1.0],
                    "sec_code": ["000001.SZ"],
                }
            ),
            np.zeros((1, 1)),
            "failed",
        ),
    ],
)
def test_evaluate_cv_folds_missing_and_no_fold_paths(
    cv_panel: pd.DataFrame | None,
    x_cv: np.ndarray | None,
    expected_status: str,
) -> None:
    result = evaluate_cv_folds(
        config=RunnerConfig(),
        candidate_cfg={"label_horizon": 5, "candidate_id": "unit"},
        model_family="logistic_regression",
        cv_panel=cv_panel,
        x_cv=x_cv,
        random_state=7,
        score_source="predict_proba_positive",
        reverse_method="probability_complement",
    )

    assert result["cv_confirmation_status"] == expected_status
    assert result["cv_fold_count"] == 0


def test_evaluate_cv_folds_success_path_trains_three_dynamic_folds() -> None:
    rows = []
    features = []
    for year in range(2019, 2024):
        for idx, sec_code in enumerate(["000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ"]):
            rows.append(
                {
                    "trade_date": pd.Timestamp(year=year, month=1, day=4),
                    "split_tag": "train",
                    "target_label": 1 if idx >= 2 else 0,
                    "target_return": [-0.02, -0.01, 0.01, 0.02][idx],
                    "sample_weight": 1.0,
                    "sec_code": sec_code,
                }
            )
            features.append([float(idx), float(year - 2019)])
    cv_panel = pd.DataFrame(rows)
    x_cv = np.asarray(features, dtype=float)

    result = evaluate_cv_folds(
        config=RunnerConfig(logistic_solver="liblinear", logistic_max_iter=100),
        candidate_cfg={"candidate_id": "unit", "penalty": "l2", "C": 1.0, "label_horizon": 1},
        model_family="logistic_regression",
        cv_panel=cv_panel,
        x_cv=x_cv,
        random_state=7,
        score_source="sklearn_predict_proba_label_1",
        reverse_method="probability_complement",
    )

    assert result["cv_confirmation_status"] == "passed"
    assert result["cv_fold_count"] == 3
    assert [row["status"] for row in result["cv_fold_metrics"]] == ["succeeded", "succeeded", "succeeded"]
