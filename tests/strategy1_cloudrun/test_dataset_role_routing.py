from __future__ import annotations

import argparse

from google.cloud import bigquery

from quant_ashare.strategy1.backtest_report import (
    build_ledger_params,
    diagnosis_command,
    report_command,
    tail_risk_command,
)
from scripts.strategy1_cloudrun.acceptance import load_acceptance_contract
from scripts.strategy1_cloudrun.config import (
    Experiment,
    RunnerConfig,
    add_common_args,
    apply_cli_overrides,
)
from scripts.strategy1_cloudrun.dataset_roles import (
    DEFAULT_OUTPUT_DATASET_ROLE,
    TableResolver,
    output_dataset_role_cli_args,
    rewrite_sql_dataset_role,
)
from quant_ashare.strategy1.pipeline_control import build_chain_steps
from scripts.strategy1_cloudrun.orchestrate_sklearn_native_search import (
    build_search_qa_params,
    common_job_flags,
    dataset_role_query_job,
    maybe_run_next_wave,
    patch_native_acceptance,
    run_topk_candidate,
)
from scripts.strategy1_cloudrun.orchestrate_annual_rolling_selection import (
    build_year_experiment,
    command_plan as annual_command_plan,
    continuous_backtest_id_for,
    parse_iso_date,
    year_plan,
)
from scripts.strategy1_cloudrun.state import LockConfig, OrchestratorStatusTable, status_table_ref
from scripts.strategy1_cloudrun.ledger import (
    CASH_REDISTRIBUTION_NONE_V1,
    CASH_REDISTRIBUTION_TOPDOWN_WHOLE_ORDER_SKIP_V2,
    LEDGER_VERSION_LOT100,
    LEDGER_VERSION_TOPDOWN_LOT100,
)
from quant_ashare.strategy1.ledger import CORPORATE_ACTIONS_CASH_DIV_AND_SPLIT, DIVIDEND_TAX_FLAT_10PCT
from quant_ashare.strategy1.train_predict import CandidateResult, write_registry
from quant_ashare.strategy1.catalog import load_step_catalog


def _experiment() -> Experiment:
    return Experiment(
        experiment_id="unit_exp",
        run_id="unit_run",
        prediction_run_id="unit_pred",
        backtest_id="unit_bt",
        predict_start="2024-01-02",
        predict_end="2024-01-31",
    )


def test_runner_config_defaults_to_research_and_cli_can_fallback_to_ads() -> None:
    parser = argparse.ArgumentParser()
    add_common_args(parser)
    args = parser.parse_args(["--output-dataset-role", "ads"])

    assert DEFAULT_OUTPUT_DATASET_ROLE == "research"
    assert RunnerConfig().output_dataset_role == "research"
    assert apply_cli_overrides(RunnerConfig(), args).output_dataset_role == "ads"


def test_output_dataset_role_cli_args_propagate_all_roles_explicitly() -> None:
    assert output_dataset_role_cli_args(None) == ["--output-dataset-role", "research"]
    assert output_dataset_role_cli_args("research") == ["--output-dataset-role", "research"]
    assert output_dataset_role_cli_args("research", equals=True) == ["--output-dataset-role=research"]
    assert output_dataset_role_cli_args("ads") == ["--output-dataset-role", "ads"]
    assert output_dataset_role_cli_args("ads", equals=True) == ["--output-dataset-role=ads"]


def test_table_resolver_and_sql_rewrite_route_research_tables() -> None:
    resolver = TableResolver(dataset_role="research", project="data-aquarium")

    assert resolver.fqn("model_registry") == "data-aquarium.ashare_research.research_model_registry"

    sql = rewrite_sql_dataset_role(
        "SELECT * FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily`",
        dataset_role="research",
        project="data-aquarium",
    )

    assert sql == "SELECT * FROM `data-aquarium.ashare_research.research_backtest_nav_daily`"


def test_default_sql_rewrite_treats_ads_model_registry_as_registry_not_acceptance_result() -> None:
    sql = rewrite_sql_dataset_role(
        "SELECT * FROM `data-aquarium.ashare_ads.ads_model_registry`",
        dataset_role="research",
        project="data-aquarium",
    )

    assert sql == "SELECT * FROM `data-aquarium.ashare_research.research_model_registry`"
    assert "research_acceptance_result" not in sql


def test_backtest_report_subcommands_propagate_explicit_ads_output_dataset_role() -> None:
    config = RunnerConfig(output_dataset_role="ads")
    exp = _experiment()

    for cmd in (
        report_command(config, exp, skip_gcs_upload=False),
        diagnosis_command(config, exp, skip_gcs_upload=False),
        tail_risk_command(config, exp, skip_gcs_upload=False, search_id=None),
    ):
        assert "--output-dataset-role" in cmd
        assert cmd[cmd.index("--output-dataset-role") + 1] == "ads"


def test_backtest_report_subcommands_propagate_default_research_output_dataset_role() -> None:
    config = RunnerConfig()
    exp = _experiment()

    for cmd in (
        report_command(config, exp, skip_gcs_upload=False),
        diagnosis_command(config, exp, skip_gcs_upload=False),
        tail_risk_command(config, exp, skip_gcs_upload=False, search_id=None),
    ):
        assert "--output-dataset-role" in cmd
        assert cmd[cmd.index("--output-dataset-role") + 1] == "research"


def test_build_ledger_params_keeps_output_dataset_role_out_of_semantic_defaults() -> None:
    args = argparse.Namespace(lot_size=100, min_buy_lot=1)
    exp = Experiment(
        experiment_id="unit_exp",
        run_id="unit_run",
        prediction_run_id="unit_pred",
        backtest_id="unit_bt",
        predict_start="2024-01-02",
        predict_end="2024-01-31",
        corporate_actions=CORPORATE_ACTIONS_CASH_DIV_AND_SPLIT,
        dividend_tax_mode=DIVIDEND_TAX_FLAT_10PCT,
    )
    params = build_ledger_params(
        RunnerConfig(output_dataset_role="research"),
        exp,
        force_replace=True,
        ledger_version=LEDGER_VERSION_LOT100,
        args=args,
    )

    assert params.output_dataset_role == "research"
    assert params.ledger_version == LEDGER_VERSION_LOT100
    assert params.cash_redistribution == CASH_REDISTRIBUTION_NONE_V1
    assert params.corporate_actions == CORPORATE_ACTIONS_CASH_DIV_AND_SPLIT
    assert params.dividend_tax_mode == DIVIDEND_TAX_FLAT_10PCT

def test_build_ledger_params_records_topdown_cash_redistribution() -> None:
    args = argparse.Namespace(
        lot_size=100,
        min_buy_lot=1,
        position_floor_count=20,
        min_position_weight=None,
        walk_depth=50,
    )

    params = build_ledger_params(
        RunnerConfig(output_dataset_role="research"),
        _experiment(),
        force_replace=True,
        ledger_version=LEDGER_VERSION_TOPDOWN_LOT100,
        args=args,
    )

    assert params.ledger_version == LEDGER_VERSION_TOPDOWN_LOT100
    assert params.cash_redistribution == CASH_REDISTRIBUTION_TOPDOWN_WHOLE_ORDER_SKIP_V2


def test_orchestrator_cloud_run_commands_propagate_explicit_ads_output_dataset_role() -> None:
    config = RunnerConfig(output_dataset_role="ads")
    args = argparse.Namespace(
        config="configs/strategy1/cloudrun_runner_default.yml",
        manifest="configs/strategy1/oq010_experiments_v0.json",
        force_replace=False,
        skip_gcs_upload=False,
        train_mode="train_predict",
        skip_diagnosis=False,
        skip_qa=False,
    )

    commands = [step.command for step in build_chain_steps(config, _experiment(), args)]
    joined = "\n".join(" ".join(command) for command in commands)

    assert "--output-dataset-role=ads" in joined


def test_orchestrator_cloud_run_commands_propagate_default_research_output_dataset_role() -> None:
    config = RunnerConfig()
    args = argparse.Namespace(
        config="configs/strategy1/cloudrun_runner_default.yml",
        manifest="configs/strategy1/oq010_experiments_v0.json",
        force_replace=False,
        skip_gcs_upload=False,
        train_mode="train_predict",
        skip_diagnosis=False,
        skip_qa=False,
    )

    commands = [step.command for step in build_chain_steps(config, _experiment(), args)]
    joined = "\n".join(" ".join(command) for command in commands)

    assert "--output-dataset-role=research" in joined


def test_orchestrator_cloud_run_commands_use_package_entrypoints() -> None:
    args = argparse.Namespace(
        config="configs/strategy1/cloudrun_runner_default.yml",
        manifest="configs/strategy1/oq010_experiments_v0.json",
        force_replace=False,
        skip_gcs_upload=False,
        train_mode="train_predict",
        skip_diagnosis=False,
        skip_qa=False,
    )

    joined = "\n".join(
        " ".join(step.command)
        for step in build_chain_steps(RunnerConfig(), _experiment(), args)
    )

    assert "quant_ashare.strategy1.train_predict" in joined
    assert "quant_ashare.strategy1.backtest_report" in joined
    assert "scripts.strategy1_cloudrun.train_predict" not in joined
    assert "scripts.strategy1_cloudrun.backtest_report" not in joined


def test_orchestrator_candidate_fanout_propagates_output_dataset_role() -> None:
    args = argparse.Namespace(
        config="configs/strategy1/cloudrun_runner_default.yml",
        manifest="configs/strategy1/oq010_experiments_v0.json",
        force_replace=False,
        skip_gcs_upload=False,
        train_mode="task_fanout",
        candidate_parallelism=0,
        skip_diagnosis=False,
        skip_qa=False,
    )

    for role in ("research", "ads"):
        config = RunnerConfig(output_dataset_role=role)
        steps = build_chain_steps(config, _experiment(), args)
        fanout_command = next(step.command for step in steps if step.step_id == "cloudrun_train_candidate_fanout")
        joined = "\n".join(" ".join(step.command) for step in steps)

        assert "quant_ashare.strategy1.prepare_matrix" in joined
        assert "quant_ashare.strategy1.train_candidate_task" in joined
        assert "quant_ashare.strategy1.select_register_predict" in joined
        assert "scripts.strategy1_cloudrun.prepare_matrix" not in joined
        assert "scripts.strategy1_cloudrun.train_candidate_task" not in joined
        assert "scripts.strategy1_cloudrun.select_register_predict" not in joined
        assert fanout_command
        assert f"--output-dataset-role={role}" in joined


def test_native_search_cloud_run_flags_propagate_default_research_and_explicit_ads() -> None:
    args = argparse.Namespace(
        config="configs/strategy1/cloudrun_runner_default.yml",
        manifest="configs/strategy1/sklearn_native_baseline_search.yml",
        force_replace=False,
        skip_gcs_upload=False,
    )

    research_flags = common_job_flags(RunnerConfig(), args, _experiment())
    ads_flags = common_job_flags(RunnerConfig(output_dataset_role="ads"), args, _experiment())

    assert "--output-dataset-role=research" in research_flags
    assert "--output-dataset-role=ads" in ads_flags


def test_native_search_topk_commands_use_package_entrypoints(monkeypatch) -> None:
    captured_commands: list[list[str]] = []

    def fake_run_step(**kwargs: object) -> dict[str, str]:
        step = kwargs["step"]
        captured_commands.append(step.command)
        return {"step_id": step.step_id, "status": "captured"}

    monkeypatch.setattr("scripts.strategy1_cloudrun.orchestrate_sklearn_native_search.run_step", fake_run_step)
    args = argparse.Namespace(
        config="configs/strategy1/cloudrun_runner_default.yml",
        manifest="configs/strategy1/sklearn_native_baseline_search.yml",
        force_replace=False,
        skip_gcs_upload=False,
        skip_diagnosis=False,
        skip_qa=False,
        resume=False,
    )

    result = run_topk_candidate(
        config=RunnerConfig(output_dataset_role="research"),
        args=args,
        lock_config=LockConfig(project="data-aquarium", region="asia-east2", dry_run=True),
        scheduler_id="unit-scheduler",
        manifest_hash_value="unit-hash",
        search_exp=_experiment(),
        search_id="unit_search",
        matrix_uri="gs://unit/matrix",
        row={"candidate_id": "candidate_a", "shortlist_rank_valid_only": 1},
        test_reuse_wave_no=1,
        test_reuse_approval_ref=None,
        final_holdout_status=None,
    )
    joined = "\n".join(" ".join(command) for command in captured_commands)

    assert result["status"] == "succeeded"
    assert "quant_ashare.strategy1.select_register_predict" in joined
    assert "quant_ashare.strategy1.backtest_report" in joined
    assert "scripts.strategy1_cloudrun.select_register_predict" not in joined
    assert "scripts.strategy1_cloudrun.backtest_report" not in joined


def test_annual_rolling_command_plan_uses_package_entrypoints() -> None:
    args = argparse.Namespace(
        config="configs/strategy1/annual_rolling_lgbm_regression_v0.yml",
        manifest="configs/strategy1/annual_rolling_lgbm_regression_v0.yml",
        force_replace=False,
        skip_gcs_upload=False,
        candidate_parallelism=0,
        skip_diagnosis=False,
        skip_qa=False,
    )

    plan = annual_command_plan(
        config=RunnerConfig(
            output_dataset_role="research",
            training_panel_step="build_training_panel_risk_feature",
        ),
        exp=_experiment(),
        args=args,
        include_backtest=True,
    )
    joined = "\n".join(" ".join(step["command"]) for step in plan)

    assert [step["step_id"] for step in plan[:4]] == [
        "build_training_panel",
        "cloudrun_prepare_matrix",
        "cloudrun_train_candidate_fanout",
        "cloudrun_select_register_predict",
    ]
    assert [step["step_id"] for step in plan[-3:]] == [
        "build_refit_training_panel",
        "cloudrun_refit_register_predict",
        "cloudrun_backtest_report",
    ]
    assert plan[0]["sql_step"] == "build_training_panel_risk_feature"
    assert plan[0]["params"]["p_run_id"] == "unit_run"
    assert plan[0]["params"]["p_feature_set_id"] == _experiment().feature_set_id
    refit_panel = next(step for step in plan if step["step_id"] == "build_refit_training_panel")
    assert refit_panel["sql_step"] == "build_training_panel_risk_feature"
    assert refit_panel["params"]["p_run_id"] == "unit_run__refit01"
    assert refit_panel["params"]["p_train_start"] == "2019-04-03"
    assert refit_panel["params"]["p_train_end"] == "2023-12-31"
    assert "quant_ashare.strategy1.sql_runner" in joined
    assert "scripts.strategy1_cloudrun.sql_runner" not in joined
    assert "--step=build_training_panel_risk_feature" in joined
    assert "--output-dataset-role=research" in joined
    catalog = load_step_catalog()
    assert "scripts.strategy1_cloudrun.orchestrate_annual_rolling_selection" not in (
        catalog["steps"]["build_training_panel_base"]["caller"]
    )
    assert "scripts.strategy1_cloudrun.orchestrate_annual_rolling_selection" in (
        catalog["steps"]["build_training_panel_risk_feature"]["caller"]
    )
    assert "quant_ashare.strategy1.annual_pipeline_scheduler" in (
        catalog["steps"]["build_training_panel_risk_feature"]["caller"]
    )
    assert "quant_ashare.strategy1.prepare_matrix" in joined
    assert "quant_ashare.strategy1.train_candidate_task" in joined
    assert "quant_ashare.strategy1.select_register_predict" in joined
    assert "quant_ashare.strategy1.refit_register_predict" in joined
    assert "quant_ashare.strategy1.backtest_report" in joined
    assert "scripts.strategy1_cloudrun.prepare_matrix" not in joined
    assert "scripts.strategy1_cloudrun.train_candidate_task" not in joined
    assert "scripts.strategy1_cloudrun.select_register_predict" not in joined
    assert "scripts.strategy1_cloudrun.refit_register_predict" not in joined
    assert "scripts.strategy1_cloudrun.backtest_report" not in joined
    assert "--source-run-id=unit_run" in joined
    assert "--source-panel-run-id=unit_run__refit01" in joined
    assert "--run-id=unit_run__refit01" in joined
    assert "--prediction-run-id=unit_run__refit01" in joined
    assert "--backtest-id=unit_bt__refit01" in joined
    assert "--skip-diagnosis" in joined
    assert "--skip-tail-risk" in joined
    assert "--skip-qa" in joined


def test_annual_year_plan_continuous_contract_uses_refit_run_id() -> None:
    args = argparse.Namespace(
        as_of_date="2026-06-09",
        target_holdings=20,
        max_single_weight=0.075,
        rebalance_frequency="biweekly",
        feature_set_id="strategy1_pv_fin_risk_v0_20260606",
        feature_version="strategy1_pv_v0_20260601",
        fin_feature_version="fin_default_v0_20260602",
        market_state_version="market_state_v0_20260606",
        tail_risk_profile_id="diagnostic_only",
        config="configs/strategy1/annual_rolling_lgbm_regression_v0.yml",
        manifest="configs/strategy1/annual_rolling_lgbm_regression_v0.yml",
        force_replace=False,
        skip_gcs_upload=False,
        candidate_parallelism=0,
        skip_diagnosis=False,
        skip_qa=False,
        include_yearly_backtest_commands=True,
    )
    exp = build_year_experiment(
        backtest_year=2026,
        args=args,
        version="v20260611_test",
        as_of=parse_iso_date(args.as_of_date),
        continuous_anchor_start="2021-01-04",
    )
    plan = year_plan(
        config=RunnerConfig(
            output_dataset_role="research",
            training_panel_step="build_training_panel_risk_feature",
        ),
        exp=exp,
        args=args,
        continuous_backtest_id=continuous_backtest_id_for(
            start_year=2021,
            end_year=2026,
            target_holdings=args.target_holdings,
            max_single_weight=args.max_single_weight,
            version="v20260611_test",
        ),
    )

    assert plan["final_refit"]["run_id"].endswith("__refit01")
    assert plan["final_refit"]["source_run_id"] == exp.run_id
    assert plan["final_refit"]["source_panel_run_id"] == plan["final_refit"]["run_id"]
    assert plan["final_refit"]["train_start"] == "2021-01-04"
    assert plan["final_refit"]["train_end"] == "2025-12-24"
    assert plan["single_year_backtest"]["backtest_id"].endswith("__refit01")

    year_2024 = build_year_experiment(
        backtest_year=2024,
        args=args,
        version="v20260611_test",
        as_of=parse_iso_date(args.as_of_date),
        continuous_anchor_start="2021-01-04",
    )
    assert year_2024.raw["final_refit_train_start"] == "2019-04-03"
    year_2021 = build_year_experiment(
        backtest_year=2021,
        args=args,
        version="v20260611_test",
        as_of=parse_iso_date(args.as_of_date),
        continuous_anchor_start="2021-01-04",
    )
    assert year_2021.raw["nominal_final_refit_train_start"] == "2016-01-01"
    assert year_2021.raw["final_refit_train_start"] == "2019-04-03"
    assert year_2021.raw["effective_final_refit_min_train_start"] == "2019-04-03"


def test_annual_true_five_year_refit_plan_uses_nominal_window_and_suffix() -> None:
    args = argparse.Namespace(
        as_of_date="2026-06-09",
        target_holdings=20,
        max_single_weight=0.075,
        rebalance_frequency="biweekly",
        feature_set_id="strategy1_pv_fin_risk_v0_20260606",
        feature_version="strategy1_pv_v0_20260601",
        fin_feature_version="fin_default_v0_20260602",
        market_state_version="market_state_v0_20260606",
        tail_risk_profile_id="diagnostic_only",
        config="configs/strategy1/annual_rolling_lgbm_regression_v0.yml",
        manifest="configs/strategy1/annual_rolling_lgbm_regression_v0.yml",
        force_replace=False,
        skip_gcs_upload=False,
        candidate_parallelism=0,
        skip_diagnosis=False,
        skip_qa=False,
        include_yearly_backtest_commands=False,
        emit_refit_only=True,
    )
    exp = build_year_experiment(
        backtest_year=2021,
        args=args,
        version="v20260611_true5y",
        as_of=parse_iso_date(args.as_of_date),
        continuous_anchor_start="2021-01-04",
        final_refit_min_training_day=None,
        final_refit_run_suffix="__true5y01",
        true_five_year_refit=True,
    )
    plan = year_plan(
        config=RunnerConfig(
            output_dataset_role="research",
            training_panel_step="build_training_panel_risk_feature",
        ),
        exp=exp,
        args=args,
        continuous_backtest_id=continuous_backtest_id_for(
            start_year=2021,
            end_year=2026,
            target_holdings=args.target_holdings,
            max_single_weight=args.max_single_weight,
            version="v20260611_true5y",
        ),
    )

    assert exp.raw["nominal_final_refit_train_start"] == "2016-01-01"
    assert exp.raw["final_refit_train_start"] == "2016-01-04"
    assert exp.raw["effective_final_refit_min_train_start"] is None
    assert exp.raw["final_refit_window_mode"] == "true_five_year_nominal"
    assert plan["final_refit"]["run_id"].endswith("__true5y01")
    assert plan["final_refit"]["train_start"] == "2016-01-04"
    assert plan["final_refit"]["effective_final_refit_min_train_start"] is None
    assert plan["command_scope"] == "refit_only"
    assert [step["step_id"] for step in plan["commands"]] == [
        "build_refit_training_panel",
        "cloudrun_refit_register_predict",
    ]
    joined = "\n".join(" ".join(step["command"]) for step in plan["commands"])
    assert "--refit-train-start=2016-01-04" in joined
    assert "--source-run-id=s1_annual_roll_y2021_train2015_2019_valid2020_n20_w075_v20260611_true5y" in joined
    assert "--source-panel-run-id=s1_annual_roll_y2021_train2015_2019_valid2020_n20_w075_v20260611_true5y__true5y01" in joined


def test_native_search_qa_params_cover_catalog_required_params() -> None:
    config = RunnerConfig(output_dataset_role="research")
    args = argparse.Namespace(candidate_parallelism=5)
    contract = load_acceptance_contract(config.acceptance_contract_path)
    params = build_search_qa_params(
        config=config,
        args=args,
        search_exp=_experiment(),
        search_id="sklearn_native_unit",
        top_k=1,
        test_reuse_wave_no=1,
        expected_model_family="logistic_regression",
        expected_model_search_wave_no=1,
        contract=contract,
    )
    catalog = load_step_catalog()

    for step_name in (
        "qa_sklearn_native_search_outputs",
        "qa_cloudrun_python_baseline_search_outputs",
    ):
        required = set(catalog["steps"][step_name]["required_params"])
        assert required <= set(params), step_name

    assert params["p_strategy_id"] == config.strategy_id


def test_next_wave_command_propagates_default_research_and_explicit_ads_output_dataset_role() -> None:
    args = argparse.Namespace(
        project="data-aquarium",
        region="asia-east2",
        output_dataset_role="research",
        candidate_parallelism=0,
        top_k_backtest=None,
        force_replace=False,
        build_training_panel=False,
        skip_diagnosis=False,
        skip_qa=False,
        auto_next_wave_on_needs_more_evidence=False,
    )

    result = maybe_run_next_wave(
        args=args,
        raw_manifest={"next_wave_manifest": "configs/strategy1/next_wave.yml"},
        comparison_rows=[{"native_acceptance_status": "needs_more_evidence"}],
    )
    command = result["command"]

    assert "--output-dataset-role=research" in command

    args.output_dataset_role = "ads"
    result = maybe_run_next_wave(
        args=args,
        raw_manifest={"next_wave_manifest": "configs/strategy1/next_wave.yml"},
        comparison_rows=[{"native_acceptance_status": "needs_more_evidence"}],
    )

    assert "--output-dataset-role=ads" in result["command"]


def test_orchestrator_status_table_routes_by_output_dataset_role() -> None:
    assert (
        status_table_ref("data-aquarium", "ads")
        == "`data-aquarium.ashare_meta.strategy1_experiment_run_status`"
    )
    assert (
        status_table_ref("data-aquarium", "research")
        == "`data-aquarium.ashare_research.research_experiment_run_status`"
    )

    table = OrchestratorStatusTable(
        "data-aquarium",
        "asia-east2",
        dry_run=True,
        output_dataset_role="research",
    )

    assert table.status_table == "`data-aquarium.ashare_research.research_experiment_run_status`"


class _FakeQueryJob:
    def __init__(self, frame: object | None = None) -> None:
        self.frame = frame

    def to_dataframe(self, *args: object, **kwargs: object) -> object:
        return self.frame

    def result(self) -> None:
        return None


class _FakeClient:
    def __init__(self) -> None:
        self.project = "data-aquarium"
        self.sql = ""
        self.queries: list[str] = []
        self.job_config = None

    def query(self, sql: str, job_config: bigquery.QueryJobConfig) -> _FakeQueryJob:
        self.sql = sql
        self.queries.append(sql)
        self.job_config = job_config
        return _FakeQueryJob()


def test_native_search_query_helper_rewrites_research_sql() -> None:
    client = _FakeClient()

    job = dataset_role_query_job(
        client,
        RunnerConfig(output_dataset_role="research"),
        "SELECT * FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` WHERE backtest_id=@bid",
        [bigquery.ScalarQueryParameter("bid", "STRING", "unit_bt")],
    )

    assert isinstance(job, _FakeQueryJob)
    assert "data-aquarium.ashare_research.research_backtest_performance_summary" in client.sql
    assert "data-aquarium.ashare_ads.ads_backtest_performance_summary" not in client.sql
    assert client.job_config.query_parameters[0].name == "bid"


def test_research_registry_rows_include_explicit_contract_columns(monkeypatch) -> None:
    captured = {}

    def fake_load_dataframe(client: object, frame: object, table_id: str) -> None:
        captured["table_id"] = table_id
        captured["frame"] = frame

    monkeypatch.setattr("quant_ashare.strategy1.train_predict.load_dataframe", fake_load_dataframe)

    exp = Experiment(
        experiment_id="unit_exp",
        run_id="unit_run",
        prediction_run_id="unit_run",
        backtest_id="unit_bt",
        experiment_group="unit_group",
        test_start="2025-01-02",
        test_end="2025-06-30",
        final_holdout_start=None,
        final_holdout_end=None,
    )
    candidate = CandidateResult(
        candidate_id="l2_c_0_1",
        model=object(),
        score_orientation="reverse_probability",
        orientation_reason="unit",
        raw_valid_scores=[],
        oriented_valid_scores=[],
        metrics={
            "model_family": "logistic_regression",
            "search_id": "unit_search",
            "native_acceptance_status": "pending_top5_backtest",
        },
        model_params={"C": 0.1},
    )

    write_registry(
        _FakeClient(),
        RunnerConfig(output_dataset_role="research"),
        exp,
        [candidate],
        candidate,
        "unit_model",
        "gs://unit/model",
        force_replace=False,
    )

    frame = captured["frame"]
    row = frame.iloc[0].to_dict()
    assert captured["table_id"] == "data-aquarium.ashare_research.research_model_registry"
    assert row["run_id"] == "unit_run"
    assert row["search_id"] == "unit_search"
    assert row["experiment_id"] == "unit_exp"
    assert row["experiment_group"] == "unit_group"
    assert row["created_date"] is not None
    assert row["promotion_status"] == "not_promoted"
    assert row["acceptance_status"] == "pending_top5_backtest"


def test_research_native_acceptance_patch_updates_registry_status_column() -> None:
    client = _FakeClient()

    patch_native_acceptance(
        client,
        RunnerConfig(output_dataset_role="research"),
        {
            "run_id": "unit_run",
            "model_id": "unit_model",
            "backtest_id": "unit_bt",
            "candidate_id": "l2_c_0_1",
            "shortlist_rank_valid_only": 1,
        },
        "rejected",
        "unit_reason",
        {
            "acceptance_contract_version": "model_acceptance_contract_v3",
            "acceptance_gate_version": "strategy1_acceptance_gate_v3",
            "acceptance_contract_sha256": "abc",
        },
    )

    registry_sql = client.queries[0]
    assert "data-aquarium.ashare_research.research_model_registry" in registry_sql
    assert "reg.acceptance_status = @status" in registry_sql
    assert "data-aquarium.ashare_ads.ads_model_registry" not in registry_sql


def test_acceptance_diagnostic_query_helpers_rewrite_research_sql(monkeypatch) -> None:
    from scripts.strategy1 import diagnose_acceptance_gate_v2 as gate_v2
    from scripts.strategy1 import diagnose_acceptance_window as window

    captured: list[tuple[str, list[bigquery.ScalarQueryParameter], dict[str, str] | None]] = []

    def fake_query_dataframe(
        client: _FakeClient,
        sql: str,
        params: list[bigquery.ScalarQueryParameter],
        *,
        labels: dict[str, str] | None = None,
    ) -> object:
        captured.append((sql, params, labels))
        return object()

    for module in (gate_v2, window):
        monkeypatch.setattr(module, "bq_query_dataframe", fake_query_dataframe)
        module.set_output_dataset_role("research")

        params = [bigquery.ScalarQueryParameter("bid", "STRING", "unit_bt")]
        module.query_dataframe(
            _FakeClient(),
            "SELECT * FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` WHERE backtest_id=@bid",
            params,
            labels={"step": "unit"},
        )

        assert "data-aquarium.ashare_research.research_backtest_nav_daily" in captured[-1][0]
        assert "data-aquarium.ashare_ads.ads_backtest_nav_daily" not in captured[-1][0]
        assert captured[-1][1] == params
        assert captured[-1][2] == {"step": "unit"}
        module.set_output_dataset_role("ads")


def test_factor_attribution_rewrites_research_reads_and_summary_update(monkeypatch) -> None:
    from scripts.strategy1 import attribute_factor_contribution as attribution

    client = _FakeClient()
    monkeypatch.setattr(attribution, "make_bqstorage_client", lambda project: None)
    attribution.OUTPUT_DATASET_ROLE = "research"

    params = [bigquery.ScalarQueryParameter("bid", "STRING", "unit_bt")]
    attribution.bq_query(
        client,
        "SELECT * FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` WHERE backtest_id=@bid",
        params,
    )

    assert "data-aquarium.ashare_research.research_backtest_performance_summary" in client.sql
    assert "data-aquarium.ashare_ads.ads_backtest_performance_summary" not in client.sql
    assert client.job_config.query_parameters == params

    attribution.write_attribution_status(
        client,
        "data-aquarium",
        "unit_bt",
        {"factor_attribution_status": "completed"},
    )

    assert "UPDATE `data-aquarium.ashare_research.research_backtest_performance_summary`" in client.sql
    assert "data-aquarium.ashare_ads.ads_backtest_performance_summary" not in client.sql
    attribution.OUTPUT_DATASET_ROLE = "ads"
