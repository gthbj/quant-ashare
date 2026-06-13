"""Plan-layer helpers for Strategy1 annual rolling selection."""

from __future__ import annotations

import argparse
import base64
import dataclasses
import sys
from datetime import date
from types import SimpleNamespace
from typing import Any

from .bq_io import json_dumps_strict
from .config import Experiment, experiment_to_b64
from .dataset_roles import output_dataset_role_cli_args
from .pipeline_control import build_task_fanout_steps, gcloud_execute_command
from .task_fanout import default_matrix_id, matrix_artifact_uri
from .training_panel import build_training_panel_params


DEFAULT_CONFIG_PATH = "configs/strategy1/annual_rolling_lgbm_regression_v0.yml"
DEFAULT_CANDIDATE_SET_ID = "strategy1_annual_rolling_lgbm_regression_11_v0"
DEFAULT_FEATURE_SET_ID = "strategy1_pv_fin_risk_v0_20260606"
DEFAULT_AS_OF_DATE = "2026-06-09"
DEFAULT_STAGE_ID = "annual_rolling_selection"
DEFAULT_EXPERIMENT_GROUP = "strategy1_annual_rolling_selection"
DEFAULT_RESUME_POLICY_ID = "cloudrun_lot100_resume_v1"
DEFAULT_FINAL_REFIT_RUN_SUFFIX = "__refit01"

FIRST_TRADING_DAY_BY_YEAR = {
    2015: "2015-04-01",
    2016: "2016-01-04",
    2017: "2017-01-03",
    2018: "2018-01-02",
    2019: "2019-01-02",
    2020: "2020-01-02",
    2021: "2021-01-04",
    2022: "2022-01-04",
    2023: "2023-01-03",
    2024: "2024-01-02",
    2025: "2025-01-02",
    2026: "2026-01-05",
}

LAST_TRADING_DAY_BY_YEAR = {
    2015: "2015-12-31",
    2016: "2016-12-30",
    2017: "2017-12-29",
    2018: "2018-12-28",
    2019: "2019-12-31",
    2020: "2020-12-31",
    2021: "2021-12-31",
    2022: "2022-12-30",
    2023: "2023-12-29",
    2024: "2024-12-31",
    2025: "2025-12-31",
}

# Current production DWS/panel coverage has internal trainable-row gaps before
# this date: historical valuation rows are sparse before 2018 and
# has_full_history_60d is false through 2019-04-02.
FINAL_REFIT_MIN_TRAINING_DAY = "2019-04-03"

# label-safe 年末截断口径（PRD_06 owner 指示：真实交易日历，retire 旧 subtract_weekdays 工作日近似）：
# label_safe_end(Y, h) = dim_trade_calendar(exchange='SSE', is_open=1) 中
#   trade_date_seq = (Y 年最后开市日 seq) - h 对应的开市日；与 dws_stock_label_daily 算 t+h 出场同一份日历同一 seq。
# 下表为真实交易日历冻结派生，覆盖 2015-2025 × h∈{5,10,20}；重新派生 / 对账查询见
# tests/strategy1/test_label_safe_calendar.py（BQ 可达时对账 dim_trade_calendar）。
# A 股 12 月无休市，故这些值恰与旧工作日近似一致，但口径已改为真实交易日历、单一事实来源。
LABEL_SAFE_YEAR_END_BY_HORIZON: dict[int, dict[int, str]] = {
    5: {
        2015: "2015-12-24", 2016: "2016-12-23", 2017: "2017-12-22", 2018: "2018-12-21",
        2019: "2019-12-24", 2020: "2020-12-24", 2021: "2021-12-24", 2022: "2022-12-23",
        2023: "2023-12-22", 2024: "2024-12-24", 2025: "2025-12-24",
    },
    10: {
        2015: "2015-12-17", 2016: "2016-12-16", 2017: "2017-12-15", 2018: "2018-12-14",
        2019: "2019-12-17", 2020: "2020-12-17", 2021: "2021-12-17", 2022: "2022-12-16",
        2023: "2023-12-15", 2024: "2024-12-17", 2025: "2025-12-17",
    },
    20: {
        2015: "2015-12-03", 2016: "2016-12-02", 2017: "2017-12-01", 2018: "2018-11-30",
        2019: "2019-12-03", 2020: "2020-12-03", 2021: "2021-12-03", 2022: "2022-12-02",
        2023: "2023-12-01", 2024: "2024-12-03", 2025: "2025-12-03",
    },
}


def validate_config(config, args: argparse.Namespace) -> None:
    if args.candidate_set_id != DEFAULT_CANDIDATE_SET_ID:
        raise ValueError(f"unsupported candidate_set_id: {args.candidate_set_id}")
    if len(config.candidate_grid) != 11:
        raise ValueError(
            f"{args.candidate_set_id} must contain exactly 11 candidates, got {len(config.candidate_grid)}"
        )
    families = {str(item.get("model_family") or "logistic_regression") for item in config.candidate_grid}
    if families != {"lightgbm_regression"}:
        raise ValueError(f"{args.candidate_set_id} must contain only lightgbm_regression candidates, got {sorted(families)}")
    if args.rebalance_frequency != "biweekly":
        raise ValueError("annual rolling P0 requires --rebalance-frequency=biweekly")
    if args.target_holdings <= 0:
        raise ValueError("--target-holdings must be positive")
    if args.max_single_weight <= 0:
        raise ValueError("--max-single-weight must be positive")


def build_year_experiment(
    *,
    backtest_year: int,
    args: argparse.Namespace,
    version: str,
    as_of: date,
    continuous_anchor_start: str,
    final_refit_min_training_day: str | None = FINAL_REFIT_MIN_TRAINING_DAY,
    final_refit_run_suffix: str = DEFAULT_FINAL_REFIT_RUN_SUFFIX,
    true_five_year_refit: bool = False,
) -> Experiment:
    selection_train_start_year = backtest_year - 6
    selection_train_end_year = backtest_year - 2
    valid_year = backtest_year - 1
    final_refit_start_year = backtest_year - 5
    final_refit_end_year = backtest_year - 1
    weight_code = max_weight_code(args.max_single_weight)
    horizon = int(getattr(args, "label_horizon", 5))
    weight_version = getattr(args, "weight_version", "constant_1p0_v0")
    # arm 标识：仅当 horizon / weight_version 非 v1 默认(h5 + constant_1p0_v0)时追加，
    # 保持 v1 run_id 格式与复现不变；feature_set 身份由 --run-version 承载。
    arm_suffix = ""
    if horizon != 5:
        arm_suffix += f"_h{horizon}"
    if weight_version != "constant_1p0_v0":
        arm_suffix += f"_{weight_version_code(weight_version)}"
    run_id = (
        f"s1_annual_roll_y{backtest_year}_"
        f"train{selection_train_start_year}_{selection_train_end_year}_"
        f"valid{valid_year}_n{args.target_holdings}_w{weight_code}{arm_suffix}_{version}"
    )
    experiment_id = (
        f"annual_roll_y{backtest_year}_"
        f"train{selection_train_start_year}_{selection_train_end_year}_"
        f"valid{valid_year}_n{args.target_holdings}_w{weight_code}{arm_suffix}_{version}"
    )
    backtest_id = (
        f"bt_s1_annual_roll_y{backtest_year}_"
        f"train{selection_train_start_year}_{selection_train_end_year}_"
        f"valid{valid_year}_n{args.target_holdings}_w{weight_code}{arm_suffix}_{version}"
    )
    selection_train_start = (
        "2015-04-01"
        if selection_train_start_year == 2015
        else actual_first_trading_day(selection_train_start_year)
    )
    backtest_end = bounded_year_end(backtest_year, as_of)
    selection_train_end = label_safe_year_end(selection_train_end_year, horizon)
    valid_start = actual_first_trading_day(valid_year)
    valid_end = label_safe_year_end(valid_year, horizon)
    backtest_start = actual_first_trading_day(backtest_year)
    final_refit_start = final_refit_first_training_day(
        final_refit_start_year,
        min_training_day=final_refit_min_training_day,
    )
    final_refit_end = label_safe_year_end(final_refit_end_year, horizon)
    return Experiment(
        experiment_id=experiment_id,
        run_id=run_id,
        backtest_id=backtest_id,
        prediction_run_id=run_id,
        stage_id=DEFAULT_STAGE_ID,
        experiment_group=DEFAULT_EXPERIMENT_GROUP,
        baseline_experiment_id="strategy1_annual_rolling_selection_p0",
        parent_experiment_id=None,
        parent_run_id=None,
        rebalance_frequency=args.rebalance_frequency,
        target_holdings=args.target_holdings,
        max_single_weight=args.max_single_weight,
        label_horizon=horizon,
        horizon_natural_frequency=horizon_natural_frequency_for(horizon),
        initial_state_mode="fresh",
        parent_backtest_id=None,
        state_as_of_date=None,
        resume_policy_id=DEFAULT_RESUME_POLICY_ID,
        rebalance_anchor_start=continuous_anchor_start,
        feature_set_id=args.feature_set_id,
        feature_version=args.feature_version,
        fin_feature_version=args.fin_feature_version,
        tail_risk_profile_id=args.tail_risk_profile_id,
        market_state_version=args.market_state_version,
        weight_version=weight_version,
        requires_retrain=True,
        status="planned",
        train_start=selection_train_start,
        train_end=selection_train_end,
        valid_start=valid_start,
        valid_end=valid_end,
        test_start=backtest_start,
        test_end=backtest_end,
        final_holdout_start=None,
        final_holdout_end=None,
        predict_start=backtest_start,
        predict_end=backtest_end,
        raw={
            "selection_train_start_year": selection_train_start_year,
            "selection_train_end_year": selection_train_end_year,
            "valid_year": valid_year,
            "nominal_selection_train_start": "2015-04-01" if selection_train_start_year == 2015 else f"{selection_train_start_year}-01-01",
            "nominal_selection_train_end": f"{selection_train_end_year}-12-31",
            "actual_selection_train_start": selection_train_start,
            "actual_selection_train_end": selection_train_end,
            "nominal_valid_start": f"{valid_year}-01-01",
            "nominal_valid_end": f"{valid_year}-12-31",
            "actual_valid_start": valid_start,
            "actual_valid_end": valid_end,
            "final_refit_train_start": final_refit_start,
            "final_refit_train_end": final_refit_end,
            "nominal_final_refit_train_start": f"{final_refit_start_year}-01-01",
            "nominal_final_refit_train_end": f"{final_refit_end_year}-12-31",
            "actual_final_refit_train_start": final_refit_start,
            "actual_final_refit_train_end": final_refit_end,
            "effective_final_refit_min_train_start": final_refit_min_training_day,
            "final_refit_window_mode": "true_five_year_nominal" if true_five_year_refit else "effective_coverage_floor",
            "final_refit_run_suffix": final_refit_run_suffix,
            "true_five_year_refit": true_five_year_refit,
            "nominal_backtest_start": f"{backtest_year}-01-01",
            "nominal_backtest_end": args.as_of_date if backtest_year == as_of.year else f"{backtest_year}-12-31",
            "actual_backtest_start": backtest_start,
            "actual_backtest_end": backtest_end,
            "backtest_year": backtest_year,
        },
    )


def year_plan(*, config, exp: Experiment, args: argparse.Namespace, continuous_backtest_id: str) -> dict[str, Any]:
    matrix_id = default_matrix_id(config, exp)
    matrix_uri = matrix_artifact_uri(config, exp, matrix_id)
    refit_exp = final_refit_experiment(exp)
    selection_commands = command_plan(config=config, exp=exp, args=args, include_backtest=args.include_yearly_backtest_commands)
    return {
        "backtest_year": int(exp.raw["backtest_year"]),
        "experiment": exp.to_params(),
        "experiment_json": experiment_to_b64(exp),
        "refit_experiment": refit_exp.to_params(),
        "refit_experiment_json": experiment_to_b64(refit_exp),
        "matrix_id": matrix_id,
        "matrix_uri": matrix_uri,
        "selected_candidate_id": None,
        "selected_candidate_source": "select_register_predict output",
        "command_scope": "refit_only" if getattr(args, "emit_refit_only", False) else "selection_refit",
        "window_contract": {
            key: value
            for key, value in exp.raw.items()
            if key.startswith("nominal_") or key.startswith("actual_")
        },
        "final_refit": {
            "experiment_id": refit_exp.experiment_id,
            "run_id": refit_exp.run_id,
            "prediction_run_id": refit_exp.prediction_run_id,
            "backtest_id": refit_exp.backtest_id,
            "source_run_id": exp.run_id,
            "source_panel_run_id": refit_exp.run_id,
            "train_start": exp.raw["final_refit_train_start"],
            "train_end": exp.raw["final_refit_train_end"],
            "window_mode": exp.raw.get("final_refit_window_mode"),
            "effective_final_refit_min_train_start": exp.raw.get("effective_final_refit_min_train_start"),
            "predict_start": refit_exp.predict_start,
            "predict_end": refit_exp.predict_end,
            "selected_candidate_required": True,
            "status": "executable_after_candidate_selection",
        },
        "single_year_backtest": {
            "backtest_id": refit_exp.backtest_id,
            "diagnostic_only": True,
            "official_continuous_backtest_id": continuous_backtest_id,
        },
        "commands": selection_commands,
    }


def command_plan(*, config, exp: Experiment, args: argparse.Namespace, include_backtest: bool) -> list[dict[str, Any]]:
    common_flags = [
        f"--project={config.project}",
        f"--region={config.region}",
        f"--config={args.config}",
        f"--manifest={args.manifest}",
        *output_dataset_role_cli_args(config.output_dataset_role, equals=True),
        f"--experiment-id={exp.experiment_id}",
        f"--experiment-json={experiment_to_b64(exp)}",
    ]
    if args.force_replace:
        common_flags.append("--force-replace")
    if args.skip_gcs_upload:
        common_flags.append("--skip-gcs-upload")
    task_args = SimpleNamespace(
        config=args.config,
        manifest=args.manifest,
        candidate_parallelism=args.candidate_parallelism,
        candidate_parallelism_from_cli=args.candidate_parallelism not in (None, 0),
    )
    refit_exp = final_refit_experiment(exp)
    steps = []
    if not getattr(args, "emit_refit_only", False):
        steps.append(training_panel_step(config, exp, args))
        steps.extend(build_task_fanout_steps(config, exp, task_args, common_flags))
    steps.append(training_panel_step(
        config,
        refit_exp,
        args,
        step_id="build_refit_training_panel",
        display_name="Build annual final-refit training panel",
    ))
    refit_flags = [
        f"--project={config.project}",
        f"--region={config.region}",
        f"--config={args.config}",
        f"--manifest={args.manifest}",
        *output_dataset_role_cli_args(config.output_dataset_role, equals=True),
        f"--experiment-json={experiment_to_b64(refit_exp)}",
        f"--source-run-id={exp.run_id}",
        f"--source-panel-run-id={refit_exp.run_id}",
        f"--refit-train-start={refit_exp.train_start}",
        f"--refit-train-end={refit_exp.train_end}",
    ]
    if args.force_replace:
        refit_flags.append("--force-replace")
    if args.skip_gcs_upload:
        refit_flags.append("--skip-gcs-upload")
    steps.append(SimpleNamespace(
        step_id="cloudrun_refit_register_predict",
        display_name="Cloud Run final refit/register/predict",
        job_name=config.train_predict_job,
        command=gcloud_execute_command(
            config.project,
            config.region,
            config.train_predict_job,
            "quant_ashare.strategy1.refit_register_predict",
            refit_flags,
        ),
    ))
    if include_backtest:
        backtest_flags = [
            f"--project={config.project}",
            f"--region={config.region}",
            f"--config={args.config}",
            f"--manifest={args.manifest}",
            *output_dataset_role_cli_args(config.output_dataset_role, equals=True),
            f"--experiment-id={refit_exp.experiment_id}",
            f"--experiment-json={experiment_to_b64(refit_exp)}",
            f"--run-id={refit_exp.run_id}",
            f"--prediction-run-id={refit_exp.prediction_run_id}",
            f"--backtest-id={refit_exp.backtest_id}",
            "--skip-diagnosis",
            "--skip-tail-risk",
            "--skip-qa",
        ]
        steps.append(SimpleNamespace(
            step_id="cloudrun_backtest_report",
            display_name="Cloud Run yearly diagnostic backtest/report",
            job_name=config.backtest_report_job,
            command=gcloud_execute_command(
                config.project,
                config.region,
                config.backtest_report_job,
                "quant_ashare.strategy1.backtest_report",
                backtest_flags,
            ),
        ))
    return [
        {
            "step_id": step.step_id,
            "display_name": step.display_name,
            "job_name": step.job_name,
            "command": step.command,
            **({"sql_step": step.sql_step, "params": step.params} if getattr(step, "sql_step", None) else {}),
        }
        for step in steps
    ]


def final_refit_run_id(exp: Experiment) -> str:
    suffix = str(exp.raw.get("final_refit_run_suffix") or DEFAULT_FINAL_REFIT_RUN_SUFFIX)
    return f"{exp.run_id}{suffix}"


def final_refit_backtest_id(exp: Experiment) -> str | None:
    if not exp.backtest_id:
        return None
    return f"{exp.backtest_id}__refit01"


def final_refit_experiment(exp: Experiment) -> Experiment:
    refit_train_start = str(exp.raw.get("final_refit_train_start") or exp.train_start)
    refit_train_end = str(exp.raw.get("final_refit_train_end") or exp.train_end)
    raw = dict(exp.raw)
    raw.update({
        "source_run_id": exp.run_id,
        "source_panel_run_id": final_refit_run_id(exp),
        "selection_run_id": exp.run_id,
        "selection_experiment_id": exp.experiment_id,
        "selection_backtest_id": exp.backtest_id,
        "selection_prediction_run_id": exp.prediction_run_id,
        "final_refit_train_start": refit_train_start,
        "final_refit_train_end": refit_train_end,
        "refit": True,
    })
    return dataclasses.replace(
        exp,
        experiment_id=f"{exp.experiment_id}__final_refit",
        run_id=final_refit_run_id(exp),
        backtest_id=final_refit_backtest_id(exp),
        prediction_run_id=final_refit_run_id(exp),
        parent_experiment_id=exp.experiment_id,
        parent_run_id=exp.run_id,
        requires_retrain=True,
        status="planned",
        train_start=refit_train_start,
        train_end=refit_train_end,
        valid_start=refit_train_start,
        valid_end=refit_train_end,
        raw=raw,
    )


def training_panel_step(
    config,
    exp: Experiment,
    args: argparse.Namespace,
    *,
    step_id: str = "build_training_panel",
    display_name: str = "Build annual rolling training panel",
) -> SimpleNamespace:
    params = build_training_panel_params(exp, force_replace=args.force_replace)
    encoded = base64.urlsafe_b64encode(
        json_dumps_strict(params, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).decode("ascii")
    return SimpleNamespace(
        step_id=step_id,
        display_name=display_name,
        job_name=None,
        sql_step=config.training_panel_step,
        params=params,
        command=[
            sys.executable,
            "-m",
            "quant_ashare.strategy1.sql_runner",
            f"--project={config.project}",
            f"--region={config.region}",
            f"--step={config.training_panel_step}",
            f"--params-json-b64={encoded}",
            *output_dataset_role_cli_args(config.output_dataset_role, equals=True),
        ],
    )


def continuous_backtest_id_for(
    *,
    start_year: int,
    end_year: int,
    target_holdings: int,
    max_single_weight: float,
    version: str,
) -> str:
    return (
        f"bt_s1_annual_roll_continuous_{start_year}_{end_year}_"
        f"n{target_holdings}_w{max_weight_code(max_single_weight)}_{version}"
    )


def b26_reference_plan(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "reference_id": "b26_baseline_binary_ref",
        "status": "diagnostic_only_reference_not_scheduled",
        "participates_in_candidate_ranking": False,
        "participates_in_selected_candidate_id": False,
        "participates_in_acceptance": False,
        "target_holdings": args.target_holdings,
        "max_single_weight": args.max_single_weight,
    }


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def actual_first_trading_day(year: int) -> str:
    try:
        return FIRST_TRADING_DAY_BY_YEAR[year]
    except KeyError as exc:
        raise ValueError(f"missing first trading day mapping for year {year}") from exc


def final_refit_first_training_day(
    year: int,
    *,
    min_training_day: str | None = FINAL_REFIT_MIN_TRAINING_DAY,
) -> str:
    first_trading_day = parse_iso_date(actual_first_trading_day(year))
    if min_training_day is None:
        return first_trading_day.isoformat()
    coverage_floor = parse_iso_date(min_training_day)
    return max(first_trading_day, coverage_floor).isoformat()


def actual_last_trading_day(year: int) -> str:
    try:
        return LAST_TRADING_DAY_BY_YEAR[year]
    except KeyError as exc:
        raise ValueError(f"missing last trading day mapping for year {year}") from exc


def bounded_year_end(year: int, as_of: date) -> str:
    if year == as_of.year:
        return as_of.isoformat()
    if year > as_of.year:
        raise ValueError(f"backtest year {year} is after as_of_date {as_of.isoformat()}")
    return actual_last_trading_day(year)


def label_safe_year_end(year: int, label_horizon: int) -> str:
    """年末 label-safe 截断（真实交易日历，PRD_06 owner 指示）：返回 dim_trade_calendar 中
    trade_date_seq = last_open_seq(year) - label_horizon 的 SSE 开市日，值取自冻结派生表
    LABEL_SAFE_YEAR_END_BY_HORIZON。未覆盖的 (year, label_horizon) fail-fast，提示按表顶注释重新派生。
    （retire 旧 subtract_weekdays 工作日近似：只数周一~五、跨节假日会静默错算。）"""
    by_year = LABEL_SAFE_YEAR_END_BY_HORIZON.get(int(label_horizon))
    if by_year is None:
        raise ValueError(
            f"label_safe_year_end 不支持 label_horizon={label_horizon}（仅冻结派生了 "
            f"{sorted(LABEL_SAFE_YEAR_END_BY_HORIZON)}）"
        )
    safe_end = by_year.get(int(year))
    if safe_end is None:
        raise ValueError(
            f"label_safe_year_end 未覆盖 year={year}（label_horizon={label_horizon}）；"
            "按 LABEL_SAFE_YEAR_END_BY_HORIZON 顶部注释的 dim_trade_calendar 查询重新派生并补表。"
        )
    return safe_end


def max_weight_code(value: float) -> str:
    return f"{int(round(value * 1000)):03d}"


def weight_version_code(weight_version: str) -> str:
    """run_id 里的短 arm 标识；未知版本退化为字母数字前缀，避免碰撞。"""
    known = {
        "constant_1p0_v0": "wvc1",
        "logmv_xs_monotone_v0": "wvlmv",
    }
    if weight_version in known:
        return known[weight_version]
    return "wv" + "".join(ch for ch in weight_version if ch.isalnum())[:6]


def horizon_natural_frequency_for(label_horizon: int) -> str:
    """标签 horizon 的自然频率(provenance 元数据，非硬约束)：5→weekly / 10→biweekly / 20→monthly。"""
    return {5: "weekly", 10: "biweekly", 20: "monthly"}.get(int(label_horizon), "weekly")
