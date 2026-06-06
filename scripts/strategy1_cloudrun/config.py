"""Manifest and runtime configuration helpers for Strategy 1 Cloud Run jobs."""

from __future__ import annotations

import argparse
import base64
import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is optional for JSON-only callers.
    yaml = None

from scripts.strategy1_cloudrun.bq_io import json_dumps_strict


DEFAULT_CONFIG_PATH = "configs/strategy1/cloudrun_runner_default.yml"
DEFAULT_MANIFEST_PATH = "configs/strategy1/oq010_experiments_v0.json"
DEFAULT_PROJECT = "data-aquarium"
DEFAULT_REGION = "asia-east2"
DEFAULT_STRATEGY_ID = "ml_pv_clf_v0"
DEFAULT_ARTIFACT_BASE_URI = "gs://ashare-artifacts/reports/strategy1"
DEFAULT_MODEL_ARTIFACT_BASE_URI = "gs://ashare-artifacts/models/strategy1"
DEFAULT_LOCAL_MIRROR_ROOT = "reports/strategy1_cloudrun"
DEFAULT_EXECUTION_BACKEND = "cloud_run_sklearn_ledger_v1"
DEFAULT_LOCK_BUCKET = "ashare-artifacts"
DEFAULT_LOCK_PREFIX = "locks/strategy1/cloudrun"
DEFAULT_ACCEPTANCE_CONTRACT_PATH = "configs/strategy1/model_acceptance_contract_v1.yml"


@dataclasses.dataclass(frozen=True)
class RunnerConfig:
    project: str = DEFAULT_PROJECT
    region: str = DEFAULT_REGION
    strategy_id: str = DEFAULT_STRATEGY_ID
    artifact_base_uri: str = DEFAULT_ARTIFACT_BASE_URI
    model_artifact_base_uri: str = DEFAULT_MODEL_ARTIFACT_BASE_URI
    local_mirror_root: str = DEFAULT_LOCAL_MIRROR_ROOT
    execution_backend: str = DEFAULT_EXECUTION_BACKEND
    train_predict_job: str = "strategy1-train-predict-job"
    prepare_matrix_job: str = "strategy1-prepare-matrix-job"
    train_candidate_fanout_job: str = "strategy1-train-candidate-fanout-job"
    select_register_predict_job: str = "strategy1-select-register-predict-job"
    backtest_report_job: str = "strategy1-backtest-report-job"
    lock_bucket: str = DEFAULT_LOCK_BUCKET
    lock_prefix: str = DEFAULT_LOCK_PREFIX
    lock_ttl_minutes: int = 30
    heartbeat_interval_seconds: int = 60
    candidate_grid: tuple[dict[str, Any], ...] = (
        {"candidate_id": "l2_c_0_1", "penalty": "l2", "C": 0.1, "l1_ratio": None},
        {"candidate_id": "l2_c_1", "penalty": "l2", "C": 1.0, "l1_ratio": None},
        {"candidate_id": "l2_c_10", "penalty": "l2", "C": 10.0, "l1_ratio": None},
        {
            "candidate_id": "elastic_c_1_l1_0_15",
            "penalty": "elasticnet",
            "C": 1.0,
            "l1_ratio": 0.15,
        },
        {
            "candidate_id": "elastic_c_1_l1_0_5",
            "penalty": "elasticnet",
            "C": 1.0,
            "l1_ratio": 0.5,
        },
    )
    preprocess_version: str = "sklearn_median_winsor_zscore_v1"
    winsor_lower: float = 0.01
    winsor_upper: float = 0.99
    logistic_solver: str = "saga"
    logistic_max_iter: int = 200
    logistic_class_weight: str | None = None
    random_state: int = 20260604
    bqml_reference_run_id: str = "s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01"
    acceptance_contract_path: str = DEFAULT_ACCEPTANCE_CONTRACT_PATH
    candidate_parallelism: int = 0
    candidate_task_cpu: int | None = None
    candidate_task_memory: str | None = None


@dataclasses.dataclass(frozen=True)
class Experiment:
    experiment_id: str
    run_id: str
    backtest_id: str | None
    prediction_run_id: str
    stage_id: str | None = None
    experiment_group: str | None = None
    baseline_experiment_id: str | None = None
    parent_experiment_id: str | None = None
    parent_run_id: str | None = None
    rebalance_frequency: str = "weekly"
    target_holdings: int = 5
    max_single_weight: float = 0.20
    label_horizon: int = 5
    horizon_natural_frequency: str = "weekly"
    feature_set_id: str = "strategy1_pv_v0_20260601"
    feature_version: str = "strategy1_pv_v0_20260601"
    fin_feature_version: str = "fin_default_v0_20260602"
    tail_risk_profile_id: str = "diagnostic_only"
    market_state_version: str = "market_state_v0_20260606"
    requires_retrain: bool = True
    status: str = "planned"
    train_start: str = "2019-04-03"
    train_end: str = "2023-12-31"
    valid_start: str = "2024-01-02"
    valid_end: str = "2024-12-31"
    test_start: str = "2025-01-02"
    test_end: str = "2025-12-31"
    final_holdout_start: str | None = None
    final_holdout_end: str | None = None
    predict_start: str = "2024-01-02"
    predict_end: str = "2025-12-31"
    raw: dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def experiment_type(self) -> str:
        return "retrain" if self.requires_retrain else "portfolio_only"

    @property
    def is_executable(self) -> bool:
        if self.status.startswith("blocked_"):
            return False
        return not _has_unresolved_placeholder(dataclasses.asdict(self))

    def to_params(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "prediction_run_id": self.prediction_run_id,
            "backtest_id": self.backtest_id,
            "stage_id": self.stage_id,
            "experiment_group": self.experiment_group,
            "experiment_type": self.experiment_type,
            "baseline_experiment_id": self.baseline_experiment_id,
            "parent_experiment_id": self.parent_experiment_id,
            "parent_run_id": self.parent_run_id,
            "rebalance_frequency": self.rebalance_frequency,
            "target_holdings": self.target_holdings,
            "max_single_weight": self.max_single_weight,
            "label_horizon": self.label_horizon,
            "horizon_natural_frequency": self.horizon_natural_frequency,
            "feature_set_id": self.feature_set_id,
            "feature_version": self.feature_version,
            "fin_feature_version": self.fin_feature_version,
            "tail_risk_profile_id": self.tail_risk_profile_id,
            "market_state_version": self.market_state_version,
            "requires_retrain": self.requires_retrain,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "valid_start": self.valid_start,
            "valid_end": self.valid_end,
            "test_start": self.test_start,
            "test_end": self.test_end,
            "final_holdout_start": self.final_holdout_start,
            "final_holdout_end": self.final_holdout_end,
            "predict_start": self.predict_start,
            "predict_end": self.predict_end,
        }


def read_mapping(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yml", ".yaml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is required to read YAML configuration")
        loaded = yaml.safe_load(text)
    else:
        loaded = json.loads(text)
    return loaded or {}


def load_runner_config(path: str | Path | None = None) -> RunnerConfig:
    cfg_path = Path(path or DEFAULT_CONFIG_PATH)
    if not cfg_path.exists():
        return RunnerConfig()
    raw = read_mapping(cfg_path)
    grid = tuple(raw.pop("candidate_grid", RunnerConfig().candidate_grid))
    valid_fields = {field.name for field in dataclasses.fields(RunnerConfig)}
    kwargs = {k: v for k, v in raw.items() if k in valid_fields}
    return RunnerConfig(candidate_grid=grid, **kwargs)


def load_manifest(path: str | Path) -> tuple[dict[str, Any], list[Experiment]]:
    manifest = read_mapping(path)
    windows = manifest.get("default_windows", {})
    experiments = []
    for raw_exp in manifest.get("experiments", []):
        exp = _experiment_from_mapping(raw_exp, manifest, windows)
        experiments.append(exp)
    return manifest, experiments


def filter_experiments(
    experiments: Iterable[Experiment],
    *,
    stage_id: str | None = None,
    experiment_id: str | None = None,
    include_blocked: bool = False,
) -> list[Experiment]:
    selected = []
    for exp in experiments:
        if stage_id and exp.stage_id != stage_id:
            continue
        if experiment_id and exp.experiment_id != experiment_id:
            continue
        if not include_blocked and not exp.is_executable:
            continue
        selected.append(exp)
    return selected


def resolve_parallel_count(
    selected_count: int,
    max_parallel_experiments: int | None,
) -> int:
    if selected_count < 0:
        raise ValueError("selected_count must be non-negative")
    if max_parallel_experiments is None or max_parallel_experiments == 0:
        return selected_count
    if max_parallel_experiments < 0:
        raise ValueError("--max-parallel-experiments must be >= 0")
    return min(max_parallel_experiments, selected_count)


def effective_candidate_parallelism(config: RunnerConfig, cli_value: int | None) -> int:
    if cli_value is not None and cli_value != 0:
        if cli_value < 0:
            raise ValueError("--candidate-parallelism must be >= 0")
        return cli_value
    if config.candidate_parallelism < 0:
        raise ValueError("candidate_parallelism in config must be >= 0")
    return config.candidate_parallelism


def manifest_hash(path: str | Path) -> str:
    data = Path(path).read_bytes()
    return hashlib.sha256(data).hexdigest()[:16]


def dump_resolved_manifest(
    path: str | Path,
    *,
    manifest_path: str,
    manifest_hash_value: str,
    config: RunnerConfig,
    experiments: Iterable[Experiment],
    resolved_parallel: int,
) -> None:
    payload = {
        "manifest_path": manifest_path,
        "manifest_hash": manifest_hash_value,
        "execution_backend": config.execution_backend,
        "project": config.project,
        "region": config.region,
        "max_parallel_experiments": resolved_parallel,
        "experiments": [exp.to_params() for exp in experiments],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json_dumps_strict(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", default=None)
    parser.add_argument("--region", default=None)
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--strategy-id", default=None)
    parser.add_argument("--artifact-base-uri", default=None)
    parser.add_argument("--model-artifact-base-uri", default=None)
    parser.add_argument("--local-mirror-root", default=None)
    parser.add_argument("--dry-run", action="store_true")


def experiment_to_b64(experiment: Experiment) -> str:
    payload = json_dumps_strict(experiment.to_params(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def experiment_from_b64(value: str) -> Experiment:
    raw = json.loads(base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8"))
    raw.setdefault("status", "planned")
    raw.setdefault("requires_retrain", raw.get("experiment_type") == "retrain")
    return Experiment(
        experiment_id=raw["experiment_id"],
        run_id=raw["run_id"],
        backtest_id=raw.get("backtest_id"),
        prediction_run_id=raw.get("prediction_run_id") or raw["run_id"],
        stage_id=raw.get("stage_id"),
        experiment_group=raw.get("experiment_group"),
        baseline_experiment_id=raw.get("baseline_experiment_id"),
        parent_experiment_id=raw.get("parent_experiment_id"),
        parent_run_id=raw.get("parent_run_id"),
        rebalance_frequency=raw.get("rebalance_frequency", "weekly"),
        target_holdings=_coerce_int(raw.get("target_holdings", 5), "target_holdings"),
        max_single_weight=_coerce_float(raw.get("max_single_weight", 0.20), "max_single_weight"),
        label_horizon=_coerce_int(raw.get("label_horizon", 5), "label_horizon"),
        horizon_natural_frequency=raw.get("horizon_natural_frequency", "weekly"),
        feature_set_id=raw.get("feature_set_id", "strategy1_pv_v0_20260601"),
        feature_version=raw.get("feature_version", "strategy1_pv_v0_20260601"),
        fin_feature_version=raw.get("fin_feature_version", "fin_default_v0_20260602"),
        tail_risk_profile_id=raw.get("tail_risk_profile_id", "diagnostic_only"),
        market_state_version=raw.get("market_state_version", "market_state_v0_20260606"),
        requires_retrain=bool(raw.get("requires_retrain", True)),
        status=raw.get("status", "planned"),
        train_start=raw.get("train_start", "2019-04-03"),
        train_end=raw.get("train_end", "2023-12-31"),
        valid_start=raw.get("valid_start", "2024-01-02"),
        valid_end=raw.get("valid_end", "2024-12-31"),
        test_start=raw.get("test_start", "2025-01-02"),
        test_end=raw.get("test_end", "2025-12-31"),
        final_holdout_start=raw.get("final_holdout_start"),
        final_holdout_end=raw.get("final_holdout_end"),
        predict_start=raw.get("predict_start", "2024-01-02"),
        predict_end=raw.get("predict_end", "2025-12-31"),
        raw=raw,
    )


def apply_cli_overrides(config: RunnerConfig, args: argparse.Namespace) -> RunnerConfig:
    updates = {}
    for field in ("project", "region", "strategy_id", "artifact_base_uri",
                  "model_artifact_base_uri", "local_mirror_root"):
        value = getattr(args, field, None)
        if value is not None:
            updates[field] = value
    return dataclasses.replace(config, **updates)


def _experiment_from_mapping(
    raw_exp: dict[str, Any],
    manifest: dict[str, Any],
    windows: dict[str, Any],
) -> Experiment:
    def value(key: str, default: Any = None) -> Any:
        return raw_exp.get(key, manifest.get(key, windows.get(key, default)))

    run_id = value("run_id")
    if not run_id:
        raise ValueError(f"experiment {raw_exp.get('experiment_id')} missing run_id")
    prediction_run_id = value("prediction_run_id", run_id)
    return Experiment(
        experiment_id=value("experiment_id"),
        run_id=run_id,
        backtest_id=value("backtest_id"),
        prediction_run_id=prediction_run_id,
        stage_id=value("stage_id"),
        experiment_group=value("experiment_group"),
        baseline_experiment_id=value("baseline_experiment_id"),
        parent_experiment_id=value("parent_experiment_id"),
        parent_run_id=value("parent_run_id"),
        rebalance_frequency=value("rebalance_frequency", "weekly"),
        target_holdings=_coerce_int(value("target_holdings", 5), "target_holdings"),
        max_single_weight=_coerce_float(value("max_single_weight", 0.20), "max_single_weight"),
        label_horizon=_coerce_int(value("label_horizon", 5), "label_horizon"),
        horizon_natural_frequency=value("horizon_natural_frequency", "weekly"),
        feature_set_id=value("feature_set_id", "strategy1_pv_v0_20260601"),
        feature_version=value("feature_version", "strategy1_pv_v0_20260601"),
        fin_feature_version=value("fin_feature_version", "fin_default_v0_20260602"),
        tail_risk_profile_id=value("tail_risk_profile_id", "diagnostic_only"),
        market_state_version=value("market_state_version", "market_state_v0_20260606"),
        requires_retrain=bool(value("requires_retrain", True)),
        status=value("status", "planned"),
        train_start=value("train_start", "2019-04-03"),
        train_end=value("train_end", "2023-12-31"),
        valid_start=value("valid_start", "2024-01-02"),
        valid_end=value("valid_end", "2024-12-31"),
        test_start=value("test_start", "2025-01-02"),
        test_end=value("test_end", "2025-12-31"),
        final_holdout_start=value("final_holdout_start"),
        final_holdout_end=value("final_holdout_end"),
        predict_start=value("predict_start", "2024-01-02"),
        predict_end=value("predict_end", "2025-12-31"),
        raw=dict(raw_exp),
    )


def _coerce_int(value: Any, field: str) -> int:
    if isinstance(value, str) and value.startswith("selected_"):
        return 0
    if isinstance(value, bool):
        raise ValueError(f"{field} cannot be bool")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise ValueError(f"{field} must be a resolved integer, got {value!r}")


def _coerce_float(value: Any, field: str) -> float:
    if isinstance(value, str) and value.startswith("selected_"):
        return 0.0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a resolved float, got {value!r}") from exc


def _has_unresolved_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return value.startswith("selected_")
    if isinstance(value, dict):
        return any(_has_unresolved_placeholder(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_unresolved_placeholder(v) for v in value)
    return False
