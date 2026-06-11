"""Run Strategy1 tail-risk overlay A/B arms on a synthetic continuous stream."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any

from google.cloud import bigquery

from scripts.strategy1_cloudrun.bq_io import make_client, query_dataframe
from scripts.strategy1_cloudrun.config import (
    Experiment,
    add_common_args,
    apply_cli_overrides,
    experiment_to_b64,
    load_runner_config,
)
from quant_ashare.strategy1.dataset_roles import (
    allow_future_research,
    output_dataset_role_cli_args,
    validate_output_dataset_role,
)
from quant_ashare.strategy1.pipeline_control import gcloud_execute_command
from quant_ashare.strategy1.sql_runner import run_sql_step
from scripts.strategy1_cloudrun.dataset_roles import TableResolver
from scripts.strategy1_cloudrun.state import (
    cloud_run_execution_state,
    describe_cloud_run_execution,
    extract_cloud_run_execution_id,
)


PREDICT_START = "2021-01-04"
PREDICT_END = "2026-06-09"
REBALANCE_FREQUENCY = "biweekly"
TARGET_HOLDINGS = 20
MAX_SINGLE_WEIGHT = 0.075
LABEL_HORIZON = 5
FEATURE_VERSION = "strategy1_pv_v0_20260601"
FEATURE_SET_ID = "strategy1_pv_fin_risk_v0_20260606"
MARKET_STATE_VERSION = "market_state_v1_20260607"
LEDGER_VERSION = "ledger_exec_v1_lot100"
RESUME_POLICY_ID = "cloudrun_lot100_resume_v1"
EXPERIMENT_GROUP = "strategy1_tail_risk_overlay_ab"


TAIL_RISK_ARMS = (
    {
        "arm": "A1",
        "suffix": "p1",
        "profile": "individual_risk_guard_v0",
        "description": "individual tail-risk buy guard",
    },
    {
        "arm": "A2",
        "suffix": "p2",
        "profile": "market_risk_off_v0",
        "description": "market risk-off buy guard",
    },
    {
        "arm": "A3",
        "suffix": "p1p2",
        "profile": "individual_and_market_risk_guard_v0",
        "description": "individual + market risk-off buy guards",
    },
)


def main() -> int:
    args = parse_args()
    config = apply_cli_overrides(load_runner_config(args.config), args)
    if validate_output_dataset_role(config.output_dataset_role) != "research":
        raise ValueError("tail-risk overlay A/B is research-only; promotion is a separate owner-approved flow")
    client = None if can_resolve_plan_offline(args) else make_client(config.project, config.region)
    source = resolve_synthetic_source(client, config, args)
    baseline = resolve_baseline(client, config, args, source)
    arms = build_arm_experiments(args, source, baseline)
    plan = build_plan(config, args, source, baseline, arms)
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2, default=str))
        return 0
    if client is None:
        client = make_client(config.project, config.region)
    if args.preflight_only:
        result = run_preflight(config, client, args, source)
        print(json.dumps({"status": "succeeded", "preflight": result, "plan": plan}, ensure_ascii=False, indent=2, default=str))
        return 0
    results: list[dict[str, Any]] = [{"step": "preflight", **run_preflight(config, client, args, source)}]
    if not args.execute_cloud_run:
        print(json.dumps({"status": "planned", "source": source, "baseline": baseline, "arms": [a.to_params() for a in arms], "steps": results, "plan": plan}, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.parallel_arms:
        results.extend(run_arms_parallel(config, args, arms))
        if not args.skip_overlay_qa:
            for arm in arms:
                results.extend(run_standard_arm_qa(config, client, args, source, arm))
    else:
        for arm in arms:
            results.append(run_arm(config, args, arm))
            if not args.skip_overlay_qa:
                results.extend(run_standard_arm_qa(config, client, args, source, arm))
    if not args.skip_overlay_qa:
        results.append(run_overlay_qa(config, client, args, source, baseline, arms))
    print(json.dumps({"status": "succeeded", "source": source, "baseline": baseline, "arms": [a.to_params() for a in arms], "steps": results}, ensure_ascii=False, indent=2, default=str))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategy1 tail-risk overlay A/B runner")
    add_common_args(parser)
    parser.add_argument("--prediction-run-id", default=None, help="Synthetic continuous prediction run id. If omitted, discover the latest refit-backed synthetic run.")
    parser.add_argument("--synthetic-model-id", default=None)
    parser.add_argument("--manifest-sha256", default=None)
    parser.add_argument("--baseline-run-id", default=None)
    parser.add_argument("--baseline-backtest-id", default=None)
    parser.add_argument("--run-version", required=True, help="Version suffix for the three A/B arm run ids, e.g. v20260611_01")
    parser.add_argument("--force-replace", action="store_true")
    parser.add_argument("--execute-cloud-run", action="store_true", help="Submit each arm to the configured backtest-report Cloud Run job.")
    parser.add_argument("--parallel-arms", action="store_true", help="Submit the three independent arm Cloud Run executions concurrently.")
    parser.add_argument("--wait", action="store_true", help="Append --wait to Cloud Run execution commands.")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--skip-report", action="store_true")
    parser.add_argument("--skip-gcs-upload", action="store_true")
    parser.add_argument("--skip-overlay-qa", action="store_true")
    parser.add_argument("--predict-start", default=PREDICT_START)
    parser.add_argument("--predict-end", default=PREDICT_END)
    parser.add_argument("--market-state-version", default=MARKET_STATE_VERSION)
    parser.add_argument("--min-tail-risk-skips", type=int, default=1)
    parser.add_argument("--min-tail-risk-crunch-skips", type=int, default=1)
    parser.add_argument("--crunch-start", default="2024-01-01")
    parser.add_argument("--crunch-end", default="2024-02-07")
    return parser.parse_args()


def can_resolve_plan_offline(args: argparse.Namespace) -> bool:
    return bool(args.prediction_run_id and args.synthetic_model_id and args.manifest_sha256 and args.baseline_backtest_id)


def resolve_synthetic_source(client: bigquery.Client | None, config, args: argparse.Namespace) -> dict[str, Any]:
    if args.prediction_run_id and args.synthetic_model_id and args.manifest_sha256:
        return {
            "prediction_run_id": args.prediction_run_id,
            "synthetic_model_id": args.synthetic_model_id,
            "input_manifest_sha256": args.manifest_sha256,
            "resolved_manifest_sha256": None,
            "manifest_sha256": args.manifest_sha256,
            "predict_start": args.predict_start,
            "predict_end": args.predict_end,
            "created_at": None,
        }
    resolver = TableResolver(dataset_role=config.output_dataset_role, project=config.project)
    registry_table = resolver.fqn("model_registry")
    filters = [
        "reg.strategy_id = @strategy_id",
        "reg.status = 'selected'",
        "JSON_VALUE(reg.model_params_json, '$.synthetic_continuous') = 'true'",
        "JSON_VALUE(reg.model_params_json, '$.source_all_refit') = 'true'",
    ]
    params: list[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("strategy_id", "STRING", config.strategy_id),
    ]
    if args.prediction_run_id:
        filters.append("JSON_VALUE(reg.model_params_json, '$.run_id') = @prediction_run_id")
        params.append(bigquery.ScalarQueryParameter("prediction_run_id", "STRING", args.prediction_run_id))
    sql = f"""
    SELECT
      JSON_VALUE(reg.model_params_json, '$.run_id') AS prediction_run_id,
      reg.model_id AS synthetic_model_id,
      JSON_VALUE(reg.metrics_json, '$.input_manifest_sha256') AS input_manifest_sha256,
      JSON_VALUE(reg.metrics_json, '$.resolved_manifest_sha256') AS resolved_manifest_sha256,
      JSON_VALUE(reg.model_params_json, '$.predict_start_date') AS predict_start,
      JSON_VALUE(reg.model_params_json, '$.predict_end_date') AS predict_end,
      reg.created_at
    FROM `{registry_table}` AS reg
    WHERE {" AND ".join(filters)}
    ORDER BY reg.created_at DESC
    LIMIT 1
    """
    rows = query_dataframe(client, sql, params, labels={"pipeline_step": "tailrisk_ab_source"})
    if rows.empty:
        raise ValueError("no refit-backed synthetic continuous selected registry row found")
    row = rows.iloc[0].to_dict()
    if args.synthetic_model_id and row["synthetic_model_id"] != args.synthetic_model_id:
        raise ValueError(f"synthetic model mismatch: expected {args.synthetic_model_id}, got {row['synthetic_model_id']}")
    return {
        "prediction_run_id": row["prediction_run_id"],
        "synthetic_model_id": row["synthetic_model_id"],
        "input_manifest_sha256": row["input_manifest_sha256"],
        "resolved_manifest_sha256": row["resolved_manifest_sha256"],
        "manifest_sha256": row["input_manifest_sha256"],
        "predict_start": args.predict_start or row["predict_start"],
        "predict_end": args.predict_end or row["predict_end"],
        "created_at": str(row["created_at"]),
    }


def resolve_baseline(client: bigquery.Client | None, config, args: argparse.Namespace, source: dict[str, Any]) -> dict[str, Any]:
    baseline_run_id = args.baseline_run_id or source["prediction_run_id"]
    baseline_backtest_id = args.baseline_backtest_id
    if baseline_backtest_id:
        return {"run_id": baseline_run_id, "backtest_id": baseline_backtest_id}
    if client is None:
        raise ValueError("baseline discovery requires BigQuery client; pass --baseline-backtest-id for offline dry-run")
    resolver = TableResolver(dataset_role=config.output_dataset_role, project=config.project)
    summary_table = resolver.fqn("backtest_summary")
    sql = f"""
    SELECT bs.backtest_id, bs.run_id
    FROM `{summary_table}` AS bs
    WHERE bs.run_id = @run_id
      AND bs.start_date = @predict_start
      AND bs.end_date = @predict_end
      AND JSON_VALUE(bs.metrics_json, '$.prediction_run_id') = @prediction_run_id
      AND JSON_VALUE(bs.metrics_json, '$.tail_risk_profile_id') = 'diagnostic_only'
      AND bs.created_date BETWEEN @predict_start AND CURRENT_DATE()
    ORDER BY bs.created_at DESC
    LIMIT 1
    """
    rows = query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("run_id", "STRING", baseline_run_id),
            bigquery.ScalarQueryParameter("prediction_run_id", "STRING", source["prediction_run_id"]),
            bigquery.ScalarQueryParameter("predict_start", "DATE", source["predict_start"]),
            bigquery.ScalarQueryParameter("predict_end", "DATE", source["predict_end"]),
        ],
        labels={"pipeline_step": "tailrisk_ab_baseline"},
    )
    if rows.empty:
        raise ValueError("baseline diagnostic continuous summary not found; pass --baseline-backtest-id explicitly")
    row = rows.iloc[0].to_dict()
    return {"run_id": row["run_id"], "backtest_id": row["backtest_id"]}


def build_arm_experiments(args: argparse.Namespace, source: dict[str, Any], baseline: dict[str, Any]) -> list[Experiment]:
    experiments = []
    for arm in TAIL_RISK_ARMS:
        base = f"s1_tailrisk_overlay_ab_continuous_2021_2026_n20_w075_{arm['suffix']}_{args.run_version}"
        experiments.append(
            Experiment(
                experiment_id=base,
                run_id=base,
                backtest_id=f"bt_{base}",
                prediction_run_id=source["prediction_run_id"],
                stage_id="tail_risk_overlay_ab",
                experiment_group=EXPERIMENT_GROUP,
                baseline_experiment_id=baseline["run_id"],
                parent_run_id=source["prediction_run_id"],
                rebalance_frequency=REBALANCE_FREQUENCY,
                target_holdings=TARGET_HOLDINGS,
                max_single_weight=MAX_SINGLE_WEIGHT,
                label_horizon=LABEL_HORIZON,
                horizon_natural_frequency="weekly",
                initial_state_mode="fresh",
                resume_policy_id=RESUME_POLICY_ID,
                rebalance_anchor_start=args.predict_start,
                feature_set_id=FEATURE_SET_ID,
                feature_version=FEATURE_VERSION,
                tail_risk_profile_id=arm["profile"],
                market_state_version=args.market_state_version,
                requires_retrain=False,
                train_start=args.predict_start,
                train_end=args.predict_end,
                valid_start=args.predict_start,
                valid_end=args.predict_end,
                test_start=args.predict_start,
                test_end=args.predict_end,
                predict_start=args.predict_start,
                predict_end=args.predict_end,
                raw={"arm": arm["arm"], "description": arm["description"], "baseline_backtest_id": baseline["backtest_id"]},
            )
        )
    return experiments


def build_plan(config, args: argparse.Namespace, source: dict[str, Any], baseline: dict[str, Any], arms: list[Experiment]) -> dict[str, Any]:
    return {
        "entrypoint": "tail_risk_overlay_ab",
        "project": config.project,
        "region": config.region,
        "output_dataset_role": config.output_dataset_role,
        "prediction_source": source,
        "baseline": baseline,
        "run_version": args.run_version,
        "force_replace": args.force_replace,
        "execute_cloud_run": args.execute_cloud_run,
        "preflight": {
            "market_state_version": args.market_state_version,
            "predict_start": args.predict_start,
            "predict_end": args.predict_end,
            "rebalance_anchor_start": args.predict_start,
            "feature_version": FEATURE_VERSION,
        },
        "arms": [
            {
                "arm": exp.raw["arm"],
                "tail_risk_profile_id": exp.tail_risk_profile_id,
                "run_id": exp.run_id,
                "backtest_id": exp.backtest_id,
                "command": backtest_command(config, args, exp),
            }
            for exp in arms
        ],
    }


def backtest_command(config, args: argparse.Namespace, exp: Experiment) -> list[str]:
    flags = [
        f"--project={config.project}",
        f"--region={config.region}",
        f"--config={args.config}",
        f"--manifest={args.manifest}",
        *output_dataset_role_cli_args(config.output_dataset_role, equals=True),
        f"--experiment-id={exp.experiment_id}",
        f"--experiment-json={experiment_to_b64(exp)}",
        f"--run-id={exp.run_id}",
        f"--prediction-run-id={exp.prediction_run_id}",
        f"--backtest-id={exp.backtest_id}",
        "--skip-diagnosis",
        "--skip-tail-risk",
        "--skip-qa",
    ]
    if args.skip_report:
        flags.append("--skip-report")
    if args.skip_gcs_upload:
        flags.append("--skip-gcs-upload")
    if args.force_replace:
        flags.append("--force-replace")
    command = gcloud_execute_command(
        config.project,
        config.region,
        config.backtest_report_job,
        "quant_ashare.strategy1.backtest_report",
        flags,
    )
    if args.wait:
        command.append("--wait")
    return command


def run_preflight(config, client: bigquery.Client, args: argparse.Namespace, source: dict[str, Any]) -> dict[str, Any]:
    params = {
        "p_baseline_run_id": source["prediction_run_id"],
        "p_baseline_backtest_id": "__preflight_only__",
        "p_prediction_run_id": source["prediction_run_id"],
        "p_strategy_id": config.strategy_id,
        "p_synthetic_model_id": source["synthetic_model_id"],
        "p_manifest_sha256": args.manifest_sha256 or source["manifest_sha256"],
        "p_predict_start": args.predict_start,
        "p_predict_end": args.predict_end,
        "p_rebalance_anchor_start": args.predict_start,
        "p_feature_version": FEATURE_VERSION,
        "p_market_state_version": args.market_state_version,
        "p_a1_run_id": "__preflight_a1__",
        "p_a1_backtest_id": "__preflight_a1__",
        "p_a2_run_id": "__preflight_a2__",
        "p_a2_backtest_id": "__preflight_a2__",
        "p_a3_run_id": "__preflight_a3__",
        "p_a3_backtest_id": "__preflight_a3__",
        "p_min_tail_risk_skips": args.min_tail_risk_skips,
        "p_min_tail_risk_crunch_skips": args.min_tail_risk_crunch_skips,
        "p_crunch_start": args.crunch_start,
        "p_crunch_end": args.crunch_end,
        "p_preflight_only": True,
    }
    job_id = run_sql_step(
        client,
        "qa_tail_risk_overlay_ab_outputs",
        params,
        dataset_role=config.output_dataset_role,
        allow_future_research=allow_future_research(config.output_dataset_role),
    )
    return {"status": "succeeded", "step": "qa_tail_risk_overlay_ab_outputs", "mode": "preflight", "job_id": job_id}


def run_arm(config, args: argparse.Namespace, exp: Experiment) -> dict[str, Any]:
    command = backtest_command(config, args, exp)
    if not args.execute_cloud_run:
        return {"status": "planned", "arm": exp.raw["arm"], "run_id": exp.run_id, "backtest_id": exp.backtest_id, "command": command}
    proc = subprocess.run(command, text=True, capture_output=True)
    result = cloud_run_result(config, exp, proc.returncode, proc.stdout, proc.stderr)
    if result["status"] != "succeeded":
        raise subprocess.CalledProcessError(proc.returncode, command, output=proc.stdout, stderr=proc.stderr)
    return result


def run_arms_parallel(config, args: argparse.Namespace, arms: list[Experiment]) -> list[dict[str, Any]]:
    processes = []
    for exp in arms:
        command = backtest_command(config, args, exp)
        processes.append((exp, command, subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)))
    results = []
    failures = []
    for exp, command, proc in processes:
        stdout, stderr = proc.communicate()
        result = cloud_run_result(config, exp, proc.returncode, stdout or "", stderr or "")
        results.append(result)
        if result["status"] != "succeeded":
            failures.append((command, proc.returncode, stdout, stderr, result))
    if failures:
        command, returncode, stdout, stderr, result = failures[0]
        raise subprocess.CalledProcessError(returncode, command, output=stdout, stderr=json.dumps(result, ensure_ascii=False))
    return results


def cloud_run_result(config, exp: Experiment, returncode: int, stdout: str, stderr: str) -> dict[str, Any]:
    execution_id = extract_cloud_run_execution_id(stdout, stderr)
    execution_state = None
    wait_returncode_ignored = False
    if returncode != 0 and execution_id:
        execution_state = cloud_run_execution_state(
            describe_cloud_run_execution(config.project, config.region, execution_id)
        )
        wait_returncode_ignored = execution_state == "succeeded"
    status = "succeeded" if returncode == 0 or wait_returncode_ignored else "failed"
    return {
        "status": status,
        "arm": exp.raw["arm"],
        "run_id": exp.run_id,
        "backtest_id": exp.backtest_id,
        "returncode": returncode,
        "cloud_run_execution_id": execution_id,
        "cloud_run_execution_state": execution_state,
        "wait_returncode_ignored": wait_returncode_ignored,
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-4000:],
    }


def run_standard_arm_qa(
    config,
    client: bigquery.Client,
    args: argparse.Namespace,
    source: dict[str, Any],
    arm: Experiment,
) -> list[dict[str, Any]]:
    continuous_params = {
        "p_run_id": arm.run_id,
        "p_prediction_run_id": source["prediction_run_id"],
        "p_strategy_id": config.strategy_id,
        "p_backtest_id": arm.backtest_id,
        "p_synthetic_model_id": source["synthetic_model_id"],
        "p_predict_start": args.predict_start,
        "p_predict_end": args.predict_end,
        "p_expected_year_count": 6,
        "p_manifest_sha256": args.manifest_sha256 or source["manifest_sha256"],
        "p_require_source_refit": True,
        "p_expected_ledger_version": LEDGER_VERSION,
        "p_resume_policy_id": RESUME_POLICY_ID,
    }
    lot_params = {
        "p_backtest_id": arm.backtest_id,
        "p_run_id": arm.run_id,
        "p_predict_start": args.predict_start,
        "p_predict_end": args.predict_end,
        "p_ledger_version": LEDGER_VERSION,
        "p_lot_size": 100,
        "p_min_buy_lot": 1,
        "p_min_buy_shares": 100,
        "p_resume_policy_id": RESUME_POLICY_ID,
    }
    outputs = []
    for step, params in (
        ("qa_continuous_backtest_outputs", continuous_params),
        ("qa_lot_aware_ledger_outputs", lot_params),
    ):
        job_id = run_sql_step(
            client,
            step,
            params,
            dataset_role=config.output_dataset_role,
            allow_future_research=allow_future_research(config.output_dataset_role),
        )
        outputs.append({"status": "succeeded", "arm": arm.raw["arm"], "step": step, "job_id": job_id})
    return outputs


def run_overlay_qa(
    config,
    client: bigquery.Client,
    args: argparse.Namespace,
    source: dict[str, Any],
    baseline: dict[str, Any],
    arms: list[Experiment],
) -> dict[str, Any]:
    arm_by_suffix = {exp.raw["arm"]: exp for exp in arms}
    params = {
        "p_baseline_run_id": baseline["run_id"],
        "p_baseline_backtest_id": baseline["backtest_id"],
        "p_prediction_run_id": source["prediction_run_id"],
        "p_strategy_id": config.strategy_id,
        "p_synthetic_model_id": source["synthetic_model_id"],
        "p_manifest_sha256": args.manifest_sha256 or source["manifest_sha256"],
        "p_predict_start": args.predict_start,
        "p_predict_end": args.predict_end,
        "p_rebalance_anchor_start": args.predict_start,
        "p_feature_version": FEATURE_VERSION,
        "p_market_state_version": args.market_state_version,
        "p_a1_run_id": arm_by_suffix["A1"].run_id,
        "p_a1_backtest_id": arm_by_suffix["A1"].backtest_id,
        "p_a2_run_id": arm_by_suffix["A2"].run_id,
        "p_a2_backtest_id": arm_by_suffix["A2"].backtest_id,
        "p_a3_run_id": arm_by_suffix["A3"].run_id,
        "p_a3_backtest_id": arm_by_suffix["A3"].backtest_id,
        "p_min_tail_risk_skips": args.min_tail_risk_skips,
        "p_min_tail_risk_crunch_skips": args.min_tail_risk_crunch_skips,
        "p_crunch_start": args.crunch_start,
        "p_crunch_end": args.crunch_end,
        "p_preflight_only": False,
    }
    job_id = run_sql_step(
        client,
        "qa_tail_risk_overlay_ab_outputs",
        params,
        dataset_role=config.output_dataset_role,
        allow_future_research=allow_future_research(config.output_dataset_role),
    )
    return {
        "status": "succeeded",
        "step": "qa_tail_risk_overlay_ab_outputs",
        "mode": "all_arms",
        "job_id": job_id,
    }


if __name__ == "__main__":
    raise SystemExit(main())
