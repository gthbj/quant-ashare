"""Shared Strategy 1 training-panel SQL parameter helpers."""

from __future__ import annotations

from typing import Any

from scripts.strategy1_cloudrun.config import Experiment


def build_training_panel_params(exp: Experiment, *, force_replace: bool) -> dict[str, Any]:
    return {
        "p_run_id": exp.run_id,
        "p_strategy_id": "ml_pv_clf_v0",
        "p_experiment_id": exp.experiment_id,
        "p_experiment_group": exp.experiment_group,
        "p_baseline_experiment_id": exp.baseline_experiment_id,
        "p_parent_experiment_id": exp.parent_experiment_id,
        "p_parent_run_id": exp.parent_run_id,
        "p_preprocess_version": "raw_v0",
        "p_feature_version": exp.feature_version,
        "p_feature_set_id": exp.feature_set_id,
        "p_fin_feature_version": exp.fin_feature_version,
        "p_market_state_version": exp.market_state_version,
        "p_market_state_ffill_max_trade_days": 5,
        "p_label_version": "open_to_close_h1_5_10_20_v20260601",
        "p_label_horizon": exp.label_horizon,
        "p_rebalance_frequency": exp.rebalance_frequency,
        "p_target_holdings": exp.target_holdings,
        "p_max_single_weight": exp.max_single_weight,
        "p_horizon_natural_frequency": exp.horizon_natural_frequency,
        "p_train_start": exp.train_start,
        "p_train_end": exp.train_end,
        "p_valid_start": exp.valid_start,
        "p_valid_end": exp.valid_end,
        "p_test_start": exp.test_start,
        "p_test_end": exp.test_end,
        "p_final_holdout_start": exp.final_holdout_start,
        "p_final_holdout_end": exp.final_holdout_end,
        "p_force_replace": force_replace,
    }
