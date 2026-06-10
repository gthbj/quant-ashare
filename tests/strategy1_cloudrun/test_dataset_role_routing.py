from __future__ import annotations

import argparse

from google.cloud import bigquery

from scripts.strategy1_cloudrun.backtest_report import (
    build_ledger_params,
    diagnosis_command,
    report_command,
    tail_risk_command,
)
from scripts.strategy1_cloudrun.config import (
    Experiment,
    RunnerConfig,
    add_common_args,
    apply_cli_overrides,
)
from scripts.strategy1_cloudrun.dataset_roles import (
    TableResolver,
    rewrite_sql_dataset_role,
)
from scripts.strategy1_cloudrun.orchestrate_experiments import build_chain_steps
from scripts.strategy1_cloudrun.orchestrate_sklearn_native_search import dataset_role_query_job
from scripts.strategy1_cloudrun.state import OrchestratorStatusTable, status_table_ref
from scripts.strategy1_cloudrun.ledger import LEDGER_VERSION_LOT100


def _experiment() -> Experiment:
    return Experiment(
        experiment_id="unit_exp",
        run_id="unit_run",
        prediction_run_id="unit_pred",
        backtest_id="unit_bt",
        predict_start="2024-01-02",
        predict_end="2024-01-31",
    )


def test_runner_config_defaults_to_ads_and_cli_can_opt_into_research() -> None:
    parser = argparse.ArgumentParser()
    add_common_args(parser)
    args = parser.parse_args(["--output-dataset-role", "research"])

    assert RunnerConfig().output_dataset_role == "ads"
    assert apply_cli_overrides(RunnerConfig(), args).output_dataset_role == "research"


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


def test_backtest_report_subcommands_propagate_output_dataset_role() -> None:
    config = RunnerConfig(output_dataset_role="research")
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
    params = build_ledger_params(
        RunnerConfig(output_dataset_role="research"),
        _experiment(),
        force_replace=True,
        ledger_version=LEDGER_VERSION_LOT100,
        args=args,
    )

    assert params.output_dataset_role == "research"
    assert params.ledger_version == LEDGER_VERSION_LOT100


def test_orchestrator_cloud_run_commands_propagate_output_dataset_role() -> None:
    config = RunnerConfig(output_dataset_role="research")
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
        self.job_config = None

    def query(self, sql: str, job_config: bigquery.QueryJobConfig) -> _FakeQueryJob:
        self.sql = sql
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
