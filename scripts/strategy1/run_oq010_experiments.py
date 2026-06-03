#!/usr/bin/env python3
"""
OQ-010: 策略 1 实验并发调度器

读取 oq010_experiments_v0.json manifest，解析依赖图，按 GCS 原子锁和
BigQuery 状态表调度实验。支持 dry-run 展开完整计划、resume 失败实验、
force-replace 清理重跑、max-parallel 和 max-parallel-backtest 并发控制。

使用方式：
  python scripts/strategy1/run_oq010_experiments.py --dry-run
  python scripts/strategy1/run_oq010_experiments.py --stage-id stage_a
  python scripts/strategy1/run_oq010_experiments.py --experiment-id oq010_a1_n10_w10 --dry-run

文档维护：DeepSeek V4（最近更新 2026-06-03）
"""

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

DEFAULT_MANIFEST = "configs/strategy1/oq010_experiments_v0.json"
DEFAULT_LOG_DIR = "logs/strategy1/oq010_experiments"
DEFAULT_LOCK_TTL_MINUTES = 30
DEFAULT_LOCK_BUCKET = "ashare-artifacts"
LOCK_BASE_PREFIX = "locks/strategy1/oq010"
HEARTBEAT_INTERVAL_SECONDS = 60
PROJECT = "data-aquarium"
LOCATION = "asia-east2"
BQ_STATUS_TABLE = "`data-aquarium.ashare_meta.strategy1_experiment_run_status`"
DEFAULT_SQL_WINDOWS = {
    "train_start": "2019-04-03",
    "train_end": "2023-12-31",
    "valid_start": "2024-01-01",
    "valid_end": "2024-12-31",
    "test_start": "2025-01-01",
    "test_end": "2025-12-31",
    "predict_start": "2024-01-01",
    "predict_end": "2025-12-31",
}
SQL_DECLARE_RE = re.compile(
    r"(?im)^\s*DECLARE\s+(p_[A-Za-z0-9_]+)\s+"
    r"(STRING|INT64|FLOAT64|BOOL|DATE|TIMESTAMP)\s+DEFAULT\s+([^;]*?);"
)
BROAD_SQL_DECLARE_RE = re.compile(
    r"(?im)^\s*DECLARE\s+(p_[A-Za-z0-9_]+)\b(?P<body>[^;]*);"
)

# step 定义：step_id -> (display_name, lock_key_template, ads_tables)
# lock_key_template: 用 {run_id}, {backtest_id}, {prediction_run_id} 替换
STEP_DEFS: Dict[str, Dict[str, Any]] = {
    "01_build_training_panel": {
        "display_name": "训练面板",
        "lock_key_template": "train:{prediction_run_id}",
        "ads_tables": ["ads_ml_training_panel_daily"],
        "bq_script": "sql/ml/strategy1/01_build_training_panel.sql",
        "requires_retrain": True,
    },
    "02_train_bqml_logistic_candidates": {
        "display_name": "BQML 训练候选模型",
        "lock_key_template": "train:{prediction_run_id}",
        "ads_tables": ["ads_model_registry", "BQML model objects"],
        "bq_script": "sql/ml/strategy1/02_train_bqml_logistic_candidates.sql",
        "requires_retrain": True,
    },
    "03_select_model_and_register": {
        "display_name": "选型与注册",
        "lock_key_template": "train:{prediction_run_id}",
        "ads_tables": ["ads_model_registry"],
        "bq_script": "sql/ml/strategy1/03_select_model_and_register.sql",
        "requires_retrain": True,
    },
    "04_predict_daily": {
        "display_name": "预测",
        "lock_key_template": "predict:{prediction_run_id}",
        "ads_tables": ["ads_model_prediction_daily"],
        "bq_script": "sql/ml/strategy1/04_predict_daily.sql",
        "requires_retrain": True,
    },
    "05_build_candidates": {
        "display_name": "候选池",
        "lock_key_template": "portfolio:{run_id}",
        "ads_tables": ["ads_stock_candidate_daily"],
        "bq_script": "sql/ml/strategy1/05_build_candidates.sql",
    },
    "06_build_portfolio_targets": {
        "display_name": "组合目标",
        "lock_key_template": "portfolio:{run_id}",
        "ads_tables": ["ads_portfolio_target_daily"],
        "bq_script": "sql/ml/strategy1/06_build_portfolio_targets.sql",
    },
    "07_build_order_plan": {
        "display_name": "订单计划",
        "lock_key_template": "portfolio:{run_id}",
        "ads_tables": ["ads_order_plan_daily"],
        "bq_script": "sql/ml/strategy1/07_build_order_plan.sql",
    },
    "08_run_backtest": {
        "display_name": "回测（ledger）",
        "lock_key_template": "backtest:{backtest_id}",
        "ads_tables": [
            "ads_backtest_trade_daily",
            "ads_backtest_position_daily",
            "ads_backtest_nav_daily",
            "ads_backtest_summary",
        ],
        "bq_script": "sql/ml/strategy1/08_run_backtest.sql",
    },
    "09_build_metrics_and_report_inputs": {
        "display_name": "指标与报告输入",
        "lock_key_template": "summary:{run_id}:{backtest_id}",
        "ads_tables": ["ads_backtest_summary", "ads_signal_monitor_daily"],
        "bq_script": "sql/ml/strategy1/09_build_metrics_and_report_inputs.sql",
    },
    "10_qa_runner_outputs": {
        "display_name": "Runner QA",
        "lock_key_template": "summary:{run_id}:{backtest_id}",
        "ads_tables": ["ads_backtest_summary"],
        "bq_script": "sql/ml/strategy1/10_qa_runner_outputs.sql",
    },
    "10_render_report": {
        "display_name": "渲染报告",
        "lock_key_template": "summary:{run_id}:{backtest_id}",
        "ads_tables": ["ads_backtest_summary"],
        "python_script": "scripts/strategy1/render_report.py",
    },
    "11_model_quality_diagnostics": {
        "display_name": "模型质量诊断 SQL",
        "lock_key_template": "diagnosis:{run_id}:{backtest_id}",
        "ads_tables": ["ads_backtest_summary"],
        "bq_script": "sql/ml/strategy1/11_model_quality_diagnostics.sql",
    },
    "11_diagnose_python": {
        "display_name": "模型质量诊断 Python",
        "lock_key_template": "diagnosis:{run_id}:{backtest_id}",
        "ads_tables": ["ads_backtest_summary"],
        "python_script": "scripts/strategy1/diagnose_model_quality.py",
    },
    "12_qa_model_diagnosis_outputs": {
        "display_name": "诊断 QA",
        "lock_key_template": "diagnosis:{run_id}:{backtest_id}",
        "ads_tables": ["ads_backtest_summary"],
        "bq_script": "sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql",
    },
}

# portfolio-only 实验从 05 开始
PORTFOLIO_ONLY_START_STEP = "05_build_candidates"
# retrain 实验从 01 开始
RETRAIN_START_STEP = "01_build_training_panel"
# backtest step 受 max_parallel_backtest 控制
BACKTEST_STEP = "08_run_backtest"

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

logger = logging.getLogger("run_oq010_experiments")


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f+00")


def _now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_instance_id() -> str:
    hostname = os.uname().nodename
    pid = os.getpid()
    ts = int(time.time())
    return f"{hostname}-{pid}-{ts}"


def _manifest_hash(manifest_path: str) -> str:
    with open(manifest_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def _build_lock_key(template: str, exp: Dict[str, Any]) -> str:
    return template.format(
        run_id=exp.get("run_id", "unknown"),
        prediction_run_id=exp.get("prediction_run_id", exp.get("run_id", "unknown")),
        backtest_id=exp.get("backtest_id", "unknown"),
    )


def _build_gcs_lock_path(lock_key: str) -> str:
    return f"{LOCK_BASE_PREFIX}/{lock_key}.lock"


def _step_display_name(step_id: str, step_def: Dict[str, Any]) -> str:
    return step_def.get("display_name", step_id)


# ---------------------------------------------------------------------------
# GCS 原子锁
# ---------------------------------------------------------------------------

class GcsLock:
    """GCS object create-if-not-exists 原子锁。

    锁对象路径: gs://<bucket>/locks/strategy1/oq010/<lock_key>.lock
    获取条件: ifGenerationMatch=0（对象不存在时才创建成功）
    """

    def __init__(
        self,
        lock_key: str,
        experiment: Dict[str, Any],
        step_id: str,
        scheduler_instance_id: str,
        ttl_minutes: int = DEFAULT_LOCK_TTL_MINUTES,
        bucket: str = DEFAULT_LOCK_BUCKET,
        dry_run: bool = False,
    ):
        self.lock_key = lock_key
        self.experiment = experiment
        self.step_id = step_id
        self.scheduler_instance_id = scheduler_instance_id
        self.ttl_minutes = ttl_minutes
        self.bucket = bucket
        self.dry_run = dry_run
        self._blob = None
        self._client = None
        self._lock_path = _build_gcs_lock_path(lock_key)
        self.acquired_at: Optional[datetime] = None
        self.lease_expires_at: Optional[datetime] = None
        self._lock_generation: Optional[int] = None

    def _get_client(self):
        if self._client is None and not self.dry_run:
            from google.cloud import storage
            self._client = storage.Client(project=PROJECT)
        return self._client

    def acquire(self) -> bool:
        """尝试获取锁。返回 True 表示获取成功。

        流程: ifGenerationMatch=0 原子创建 → 失败时检查 stale → stale 则删除并重试一次。
        """
        acquired_at_dt = datetime.now(timezone.utc)
        expires_at_dt = acquired_at_dt + timedelta(minutes=self.ttl_minutes)
        acquired_at = acquired_at_dt.isoformat()
        expires_at = expires_at_dt.isoformat()
        if self.dry_run:
            logger.info("[DRY-RUN] acquire lock: %s", self._lock_path)
            return True

        client = self._get_client()
        if client is None:
            return False

        bucket = client.bucket(self.bucket)

        for attempt in range(2):
            blob = bucket.blob(self._lock_path)
            lock_content = {
                "lock_key": self.lock_key,
                "experiment_id": self.experiment.get("experiment_id"),
                "run_id": self.experiment.get("run_id"),
                "prediction_run_id": self.experiment.get("prediction_run_id"),
                "backtest_id": self.experiment.get("backtest_id"),
                "stage_id": self.experiment.get("stage_id"),
                "step_id": self.step_id,
                "lock_owner": self.scheduler_instance_id,
                "acquired_at": acquired_at,
                "lease_expires_at": expires_at,
            }

            try:
                blob.upload_from_string(
                    json.dumps(lock_content, ensure_ascii=False),
                    content_type="application/json",
                    if_generation_match=0,
                )
                if blob.generation is None:
                    blob.reload()
                self._blob = blob
                self.acquired_at = acquired_at_dt
                self.lease_expires_at = expires_at_dt
                self._lock_generation = blob.generation
                logger.info("lock acquired: %s (owner=%s)", self._lock_path, self.scheduler_instance_id)
                return True
            except Exception as e:
                err_msg = str(e)
                if "conditionNotMet" in err_msg or "PreconditionFailed" in err_msg or "GenerationDoesNotMatch" in err_msg:
                    if attempt == 0:
                        # Lock held — check if stale
                        if self._reclaim_if_stale(bucket, blob):
                            logger.info("stale lock reclaimed, retrying: %s", self._lock_path)
                            continue
                        else:
                            logger.info("lock held and not stale: %s", self._lock_path)
                            return False
                    else:
                        logger.info("lock still held after reclaim attempt: %s", self._lock_path)
                        return False
                else:
                    logger.warning("lock acquire error: %s: %s", self._lock_path, err_msg)
                    return False
        return False

    def _reclaim_if_stale(self, bucket, blob) -> bool:
        """检查锁是否过期，过期则按同一 generation 条件删除。"""
        try:
            try:
                blob.reload()
            except Exception as e:
                err_msg = str(e)
                if "NotFound" in err_msg or "404" in err_msg:
                    return False
                raise

            generation = blob.generation
            if generation is None:
                return False

            content = json.loads(blob.download_as_bytes(if_generation_match=generation))
            expires_at = content.get("lease_expires_at", "")
            if not expires_at:
                return False
            expires = datetime.fromisoformat(expires_at)
            if datetime.now(timezone.utc) > expires:
                old_owner = content.get("lock_owner", "unknown")
                logger.warning(
                    "stale lock detected: %s (old_owner=%s, expired=%s), reclaiming",
                    self._lock_path, old_owner, expires_at,
                )
                blob.delete(if_generation_match=generation)
                return True
            return False
        except Exception as e:
            logger.warning("stale check failed: %s: %s", self._lock_path, e)
            return False

    def heartbeat(self):
        """刷新锁 lease。"""
        if self.dry_run or self._blob is None:
            return
        if self._lock_generation is None:
            logger.warning("lock heartbeat skipped without generation: %s", self._lock_path)
            return None
        try:
            blob = self._blob.bucket.blob(self._blob.name)
            existing = blob.download_as_bytes(if_generation_match=self._lock_generation)
            data = json.loads(existing)
            lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.ttl_minutes)
            data["last_heartbeat_at"] = _now_rfc3339()
            data["lease_expires_at"] = lease_expires_at.isoformat()
            blob.upload_from_string(
                json.dumps(data, ensure_ascii=False),
                content_type="application/json",
                if_generation_match=self._lock_generation,
            )
            blob.reload()
            self._blob = blob
            self.lease_expires_at = lease_expires_at
            self._lock_generation = blob.generation
            return lease_expires_at
        except Exception as e:
            logger.warning("lock heartbeat failed: %s: %s", self._lock_path, e)
            return None

    def release(self):
        """释放锁（删除 lock object）。"""
        if self.dry_run:
            logger.info("[DRY-RUN] release lock: %s", self._lock_path)
            return
        if self._blob is None:
            return
        try:
            if self._lock_generation is not None:
                self._blob.delete(if_generation_match=self._lock_generation)
            else:
                self._blob.delete()
            logger.info("lock released: %s", self._lock_path)
        except Exception as e:
            logger.warning("lock release error: %s: %s", self._lock_path, e)

    def is_stale(self) -> bool:
        """检查锁是否过期。"""
        if self.dry_run:
            return False
        try:
            client = self._get_client()
            if client is None:
                return False
            bucket = client.bucket(self.bucket)
            blob = bucket.blob(self._lock_path)
            if not blob.exists():
                return False
            content = json.loads(blob.download_as_string())
            expires_at = content.get("lease_expires_at", "")
            if not expires_at:
                return False
            expires = datetime.fromisoformat(expires_at)
            return datetime.now(timezone.utc) > expires
        except Exception:
            return False


# ---------------------------------------------------------------------------
# BigQuery 状态表操作
# ---------------------------------------------------------------------------

class BqStatusTable:
    """操作 BigQuery 状态表。

    该表只用于审计 / resume 输入，不承担锁管理职责。
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._client = None

    def _get_client(self):
        if self._client is None and not self.dry_run:
            from google.cloud import bigquery
            self._client = bigquery.Client(project=PROJECT, location=LOCATION)
        return self._client

    def upsert_step_status(
        self,
        experiment: Dict[str, Any],
        step_id: str,
        status: str,
        lock_key: Optional[str] = None,
        lock_owner: Optional[str] = None,
        job_id: Optional[str] = None,
        error_message: Optional[str] = None,
        attempt: Optional[int] = None,
        params_json: Optional[str] = None,
        manifest_path: Optional[str] = None,
        manifest_hash: Optional[str] = None,
        scheduler_instance_id: Optional[str] = None,
        log_dir: Optional[str] = None,
        force_replace: bool = False,
        lock_acquired_at: Optional[datetime] = None,
        lock_expires_at: Optional[datetime] = None,
        last_heartbeat_at: Optional[datetime] = None,
    ) -> bool:
        """插入或更新 step 状态行。"""
        if self.dry_run:
            logger.info("[DRY-RUN] upsert status: %s/%s -> %s", experiment.get("experiment_id"), step_id, status)
            return True

        client = self._get_client()
        if client is None:
            return False

        now_ts = _now_ts()
        run_id = experiment.get("run_id", "")
        backtest_id = experiment.get("backtest_id")

        if status in ("running",):
            started_at = now_ts
            finished_at = None
            created_at = now_ts
            updated_at = now_ts
        elif status in ("succeeded", "failed", "cancelled"):
            started_at = None
            finished_at = now_ts
            created_at = now_ts
            updated_at = now_ts
        else:
            started_at = None
            finished_at = None
            created_at = now_ts
            updated_at = now_ts

        sql = f"""
        MERGE {BQ_STATUS_TABLE} T
        USING (
          SELECT
            @experiment_id AS experiment_id,
            @run_id AS run_id,
            @step_id AS step_id
        ) S
        ON T.experiment_id = S.experiment_id
           AND T.run_id = S.run_id
           AND T.step_id = S.step_id
        WHEN MATCHED THEN
          UPDATE SET
            status = @status,
            finished_at = @finished_at,
            updated_at = @updated_at,
            job_id = IFNULL(@job_id, T.job_id),
            error_message = @error_message,
            attempt = IFNULL(@attempt, T.attempt),
            lock_key = IFNULL(@lock_key, T.lock_key),
            lock_owner = IFNULL(@lock_owner, T.lock_owner),
            lock_acquired_at = IF(@status = 'running', IFNULL(@lock_acquired_at, T.lock_acquired_at), T.lock_acquired_at),
            lock_expires_at = IF(@status = 'running', IFNULL(@lock_expires_at, T.lock_expires_at), T.lock_expires_at),
            last_heartbeat_at = IF(@status = 'running', IFNULL(@last_heartbeat_at, T.last_heartbeat_at), T.last_heartbeat_at),
            artifact_uri = @artifact_uri,
            report_uri = @report_uri,
            diagnosis_uri = @diagnosis_uri,
            qa_status = @qa_status,
            params_json = IFNULL(@params_json, T.params_json),
            log_dir = IFNULL(@log_dir, T.log_dir),
            status_reason = @status_reason
        WHEN NOT MATCHED THEN
          INSERT (
            experiment_id, run_id, prediction_run_id, backtest_id, stage_id,
            experiment_group, experiment_type, step_id, step_display_name,
            status, status_reason, started_at, finished_at, created_at, updated_at,
            job_id, attempt, force_replace, lock_key, lock_owner,
            lock_acquired_at, lock_expires_at, last_heartbeat_at,
            artifact_uri, report_uri, diagnosis_uri, diagnosis_status,
            qa_status, manifest_path, manifest_hash, params_json,
            runner_version, scheduler_instance_id, log_dir, error_message
          ) VALUES (
            @experiment_id, @run_id, @prediction_run_id, @backtest_id, @stage_id,
            @experiment_group, @experiment_type, @step_id, @step_display_name,
            @status, @status_reason, @started_at, @finished_at, @created_at, @updated_at,
            @job_id, @attempt, @force_replace, @lock_key, @lock_owner,
            @lock_acquired_at, @lock_expires_at, @last_heartbeat_at,
            @artifact_uri, @report_uri, @diagnosis_uri, @diagnosis_status,
            @qa_status, @manifest_path, @manifest_hash, @params_json,
            @runner_version, @scheduler_instance_id, @log_dir, @error_message
          )
        """

        lock_acquired_at_param = None
        lock_expires_at_param = None
        last_heartbeat_at_param = None
        if status == "running":
            lock_acquired_at_param = lock_acquired_at or now_ts
            lock_expires_at_param = lock_expires_at
            last_heartbeat_at_param = last_heartbeat_at or now_ts

        step_display_name = STEP_DEFS.get(step_id, {}).get("display_name", step_id)

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("experiment_id", "STRING", experiment.get("experiment_id")),
                bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
                bigquery.ScalarQueryParameter("prediction_run_id", "STRING", experiment.get("prediction_run_id")),
                bigquery.ScalarQueryParameter("backtest_id", "STRING", backtest_id),
                bigquery.ScalarQueryParameter("stage_id", "STRING", experiment.get("stage_id")),
                bigquery.ScalarQueryParameter("experiment_group", "STRING", experiment.get("experiment_group")),
                bigquery.ScalarQueryParameter("experiment_type", "STRING", experiment.get("experiment_type", "portfolio_only")),
                bigquery.ScalarQueryParameter("step_id", "STRING", step_id),
                bigquery.ScalarQueryParameter("step_display_name", "STRING", step_display_name),
                bigquery.ScalarQueryParameter("status", "STRING", status),
                bigquery.ScalarQueryParameter("status_reason", "STRING", error_message or ""),
                bigquery.ScalarQueryParameter("started_at", "TIMESTAMP", started_at),
                bigquery.ScalarQueryParameter("finished_at", "TIMESTAMP", finished_at),
                bigquery.ScalarQueryParameter("created_at", "TIMESTAMP", created_at),
                bigquery.ScalarQueryParameter("updated_at", "TIMESTAMP", updated_at),
                bigquery.ScalarQueryParameter("job_id", "STRING", job_id or ""),
                bigquery.ScalarQueryParameter("attempt", "INT64", attempt or 1),
                bigquery.ScalarQueryParameter("force_replace", "BOOL", force_replace),
                bigquery.ScalarQueryParameter("lock_key", "STRING", lock_key or ""),
                bigquery.ScalarQueryParameter("lock_owner", "STRING", lock_owner or ""),
                bigquery.ScalarQueryParameter("lock_acquired_at", "TIMESTAMP", lock_acquired_at_param),
                bigquery.ScalarQueryParameter("lock_expires_at", "TIMESTAMP", lock_expires_at_param),
                bigquery.ScalarQueryParameter("last_heartbeat_at", "TIMESTAMP", last_heartbeat_at_param),
                bigquery.ScalarQueryParameter("artifact_uri", "STRING", ""),
                bigquery.ScalarQueryParameter("report_uri", "STRING", ""),
                bigquery.ScalarQueryParameter("diagnosis_uri", "STRING", ""),
                bigquery.ScalarQueryParameter("diagnosis_status", "STRING", ""),
                bigquery.ScalarQueryParameter("qa_status", "STRING", ""),
                bigquery.ScalarQueryParameter("manifest_path", "STRING", manifest_path or ""),
                bigquery.ScalarQueryParameter("manifest_hash", "STRING", manifest_hash or ""),
                bigquery.ScalarQueryParameter("params_json", "STRING", params_json or ""),
                bigquery.ScalarQueryParameter("runner_version", "STRING", "run_oq010_experiments.py"),
                bigquery.ScalarQueryParameter("scheduler_instance_id", "STRING", scheduler_instance_id or ""),
                bigquery.ScalarQueryParameter("log_dir", "STRING", log_dir or ""),
                bigquery.ScalarQueryParameter("error_message", "STRING", error_message or ""),
            ]
        )
        try:
            client.query(sql, job_config=job_config).result()
            return True
        except Exception as e:
            logger.error("status table upsert failed: %s", e)
            return False

    def get_step_status(self, experiment_id: str, step_id: str) -> Optional[str]:
        """查询 step 状态。"""
        if self.dry_run:
            return None
        client = self._get_client()
        if client is None:
            return None
        sql = f"""
        SELECT status FROM {BQ_STATUS_TABLE}
        WHERE experiment_id = @experiment_id AND step_id = @step_id
        ORDER BY updated_at DESC LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("experiment_id", "STRING", experiment_id),
                bigquery.ScalarQueryParameter("step_id", "STRING", step_id),
            ]
        )
        try:
            rows = list(client.query(sql, job_config=job_config).result())
            if rows:
                return rows[0].get("status")
        except Exception as e:
            logger.warning("status query failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Manifest 解析与依赖解析
# ---------------------------------------------------------------------------

def load_manifest(manifest_path: str) -> Dict[str, Any]:
    """加载并校验 manifest JSON。"""
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    required_keys = ["manifest_version", "strategy_id", "experiments"]
    for k in required_keys:
        if k not in manifest:
            raise ValueError(f"manifest 缺少必要字段: {k}")

    exp_ids = set()
    for exp in manifest["experiments"]:
        eid = exp.get("experiment_id")
        if not eid:
            raise ValueError("experiment 缺少 experiment_id")
        if eid in exp_ids:
            raise ValueError(f"experiment_id 重复: {eid}")
        exp_ids.add(eid)

        rid = exp.get("run_id")
        if not rid:
            raise ValueError(f"experiment {eid} 缺少 run_id")

    return manifest


def resolve_experiments(
    manifest: Dict[str, Any],
    stage_id: Optional[str] = None,
    experiment_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """解析实验列表，按依赖排序。"""
    all_exps = manifest["experiments"]

    # filter by stage
    if stage_id:
        all_exps = [e for e in all_exps if e.get("stage_id") == stage_id]

    # filter by experiment_id
    if experiment_ids:
        exp_ids_set = set(experiment_ids)
        all_exps = [e for e in all_exps if e.get("experiment_id") in exp_ids_set]

    # 拓扑排序（按 depends_on_experiment_id）
    exp_map = {e["experiment_id"]: e for e in all_exps}
    ordered = []
    visited = set()

    def visit(eid: str):
        if eid in visited:
            return
        visited.add(eid)
        exp = exp_map.get(eid)
        if exp is None:
            return
        dep_id = exp.get("depends_on_experiment_id")
        if dep_id and dep_id in exp_map:
            visit(dep_id)
        ordered.append(exp)

    for exp in all_exps:
        visit(exp["experiment_id"])

    return ordered


def get_experiment_steps(exp: Dict[str, Any], max_parallel_backtest: int) -> List[str]:
    """获取实验的 step 列表。"""
    requires_retrain = exp.get("requires_retrain", False)
    start_step = exp.get("start_step")
    end_step = exp.get("end_step")

    if requires_retrain:
        all_steps = [
            "01_build_training_panel",
            "02_train_bqml_logistic_candidates",
            "03_select_model_and_register",
            "04_predict_daily",
            "05_build_candidates",
            "06_build_portfolio_targets",
            "07_build_order_plan",
            "08_run_backtest",
            "09_build_metrics_and_report_inputs",
            "10_qa_runner_outputs",
            "10_render_report",
            "11_model_quality_diagnostics",
            "11_diagnose_python",
            "12_qa_model_diagnosis_outputs",
        ]
    else:
        all_steps = [
            "05_build_candidates",
            "06_build_portfolio_targets",
            "07_build_order_plan",
            "08_run_backtest",
            "09_build_metrics_and_report_inputs",
            "10_qa_runner_outputs",
            "10_render_report",
            "11_model_quality_diagnostics",
            "11_diagnose_python",
            "12_qa_model_diagnosis_outputs",
        ]

    # trim step range
    if start_step:
        try:
            idx = all_steps.index(start_step)
            all_steps = all_steps[idx:]
        except ValueError:
            pass
    if end_step:
        try:
            idx = all_steps.index(end_step)
            all_steps = all_steps[: idx + 1]
        except ValueError:
            pass

    return all_steps


# ---------------------------------------------------------------------------
# 执行器
# ---------------------------------------------------------------------------

class ExperimentExecutor:
    """执行单个实验的 step 序列。"""

    def __init__(
        self,
        experiment: Dict[str, Any],
        manifest_path: str,
        manifest_hash: str,
        scheduler_instance_id: str,
        lock_ttl_minutes: int,
        force_replace: bool,
        resume: bool,
        resume_from_step: Optional[str],
        dry_run: bool,
        log_dir_base: str,
        max_parallel_backtest: int,
        backtest_semaphore: Any,
    ):
        self.experiment = experiment
        self.manifest_path = manifest_path
        self.manifest_hash = manifest_hash
        self.scheduler_instance_id = scheduler_instance_id
        self.lock_ttl_minutes = lock_ttl_minutes
        self.force_replace = force_replace
        self.resume = resume
        self.resume_from_step = resume_from_step
        self.dry_run = dry_run
        self.log_dir_base = log_dir_base
        self.max_parallel_backtest = max_parallel_backtest
        self.backtest_semaphore = backtest_semaphore

        self.bq_status = BqStatusTable(dry_run=dry_run)
        self._params_json = json.dumps(experiment, ensure_ascii=False)
        self._step_logger = None

    @property
    def experiment_id(self) -> str:
        return self.experiment.get("experiment_id", "unknown")

    @property
    def run_id(self) -> str:
        return self.experiment.get("run_id", "unknown")

    @property
    def backtest_id(self) -> Optional[str]:
        return self.experiment.get("backtest_id")

    def _log_dir(self) -> str:
        stage = self.experiment.get("stage_id", "unknown")
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.log_dir_base, f"stage={stage}", f"run_at={ts}", self.experiment_id)

    def run(self) -> Dict[str, Any]:
        """执行实验所有 step。返回实验结果摘要。"""
        steps = get_experiment_steps(self.experiment, self.max_parallel_backtest)
        log_dir = self._log_dir()
        os.makedirs(log_dir, exist_ok=True)

        result = {
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "backtest_id": self.backtest_id,
            "status": "planned",
            "completed_steps": [],
            "failed_step": None,
            "error": None,
        }

        for step_id in steps:
            step_def = STEP_DEFS.get(step_id)
            if step_def is None:
                logger.warning("[%s] unknown step: %s, skipping", self.experiment_id, step_id)
                continue

            # resume: 检查是否已成功
            if self.resume or self.resume_from_step:
                existing_status = self.bq_status.get_step_status(self.experiment_id, step_id)
                if existing_status == "succeeded":
                    logger.info("[%s] step %s already succeeded, skipping", self.experiment_id, step_id)
                    result["completed_steps"].append(step_id)
                    continue
                if self.resume_from_step and step_id != self.resume_from_step:
                    continue
                if self.resume_from_step and step_id == self.resume_from_step:
                    pass

            step_log_path = os.path.join(log_dir, f"{step_id}.log")
            step_display = _step_display_name(step_id, step_def)

            logger.info("[%s] step %s (%s) starting...", self.experiment_id, step_id, step_display)

            # 构建 lock key
            lock_key = _build_lock_key(step_def["lock_key_template"], self.experiment)

            # 08 backtest 需要 semaphore
            if step_id == BACKTEST_STEP and self.backtest_semaphore is not None:
                logger.info("[%s] waiting for backtest semaphore...", self.experiment_id)
                self.backtest_semaphore.acquire()

            try:
                import threading

                gcs_lock = GcsLock(
                    lock_key=lock_key,
                    experiment=self.experiment,
                    step_id=step_id,
                    scheduler_instance_id=self.scheduler_instance_id,
                    ttl_minutes=self.lock_ttl_minutes,
                    dry_run=self.dry_run,
                )
                lock_acquired = False
                heartbeat_stop = None
                heartbeat_thread = None

                try:
                    if not gcs_lock.acquire():
                        self.bq_status.upsert_step_status(
                            self.experiment, step_id, "cancelled",
                            error_message="lock busy or acquire error",
                            attempt=1,
                            params_json=self._params_json,
                            manifest_path=self.manifest_path,
                            manifest_hash=self.manifest_hash,
                            scheduler_instance_id=self.scheduler_instance_id,
                            log_dir=log_dir,
                            force_replace=self.force_replace,
                        )
                        result["status"] = "cancelled"
                        result["failed_step"] = step_id
                        result["error"] = f"lock busy or acquire error: {lock_key}"
                        logger.warning("[%s] step %s lock busy, cancelled", self.experiment_id, step_id)
                        return result
                    lock_acquired = True

                    if not self.bq_status.upsert_step_status(
                        self.experiment, step_id, "running",
                        lock_key=lock_key,
                        lock_owner=self.scheduler_instance_id,
                        attempt=1,
                        params_json=self._params_json,
                        manifest_path=self.manifest_path,
                        manifest_hash=self.manifest_hash,
                        scheduler_instance_id=self.scheduler_instance_id,
                        log_dir=log_dir,
                        force_replace=self.force_replace,
                        lock_acquired_at=gcs_lock.acquired_at,
                        lock_expires_at=gcs_lock.lease_expires_at,
                    ):
                        logger.error("[%s] step %s status write failed", self.experiment_id, step_id)
                        result["status"] = "cancelled"
                        result["failed_step"] = step_id
                        result["error"] = f"status table write failed: {step_id}"
                        return result

                    heartbeat_stop = threading.Event()
                    heartbeat_thread = threading.Thread(
                        target=self._heartbeat_loop,
                        args=(gcs_lock, heartbeat_stop, step_id, lock_key, log_dir),
                        daemon=False,
                    )
                    heartbeat_thread.start()
                    try:
                        success = self._execute_step(step_id, step_def, step_log_path)
                    except Exception as e:
                        success = False
                        logger.error("[%s] step %s executor exception: %s", self.experiment_id, step_id, e)
                    finally:
                        heartbeat_stop.set()
                        heartbeat_thread.join()

                    if success:
                        if not self.bq_status.upsert_step_status(
                            self.experiment, step_id, "succeeded",
                            attempt=1,
                            params_json=self._params_json,
                            manifest_path=self.manifest_path,
                            manifest_hash=self.manifest_hash,
                            scheduler_instance_id=self.scheduler_instance_id,
                            log_dir=log_dir,
                            force_replace=self.force_replace,
                        ):
                            result["status"] = "failed"
                            result["failed_step"] = step_id
                            result["error"] = f"terminal status table write failed: {step_id}"
                            logger.error("[%s] step %s terminal status write failed", self.experiment_id, step_id)
                            return result
                        logger.info("[%s] step %s succeeded", self.experiment_id, step_id)
                        result["completed_steps"].append(step_id)
                    else:
                        if not self.bq_status.upsert_step_status(
                            self.experiment, step_id, "failed",
                            error_message="see log for details",
                            attempt=1,
                            params_json=self._params_json,
                            manifest_path=self.manifest_path,
                            manifest_hash=self.manifest_hash,
                            scheduler_instance_id=self.scheduler_instance_id,
                            log_dir=log_dir,
                            force_replace=self.force_replace,
                        ):
                            logger.error("[%s] step %s failed and terminal status write also failed", self.experiment_id, step_id)
                        result["status"] = "failed"
                        result["failed_step"] = step_id
                        result["error"] = f"step {step_id} failed"
                        logger.error("[%s] step %s failed", self.experiment_id, step_id)
                        return result
                finally:
                    if heartbeat_stop is not None:
                        heartbeat_stop.set()
                    if heartbeat_thread is not None and heartbeat_thread.is_alive():
                        heartbeat_thread.join()
                    if lock_acquired:
                        gcs_lock.release()

            finally:
                if step_id == BACKTEST_STEP and self.backtest_semaphore is not None:
                    self.backtest_semaphore.release()

        result["status"] = "succeeded"
        logger.info("[%s] all steps completed: %s", self.experiment_id, result["status"])
        return result

    def _execute_step(self, step_id: str, step_def: Dict[str, Any], log_path: str) -> bool:
        """执行单个 step。返回执行是否成功。"""
        bq_script = step_def.get("bq_script")
        python_script = step_def.get("python_script")

        if self.dry_run:
            logger.info("[DRY-RUN] execute step: %s", step_id)
            if bq_script:
                return self._preflight_bq_script(bq_script)
            if python_script:
                return self._preflight_python_script(python_script)
            return False

        if bq_script:
            return self._run_bq_script(bq_script, log_path)
        elif python_script:
            return self._run_python_script(python_script, log_path)
        else:
            logger.warning("[%s] no executor for step: %s", self.experiment_id, step_id)
            return False

    def _heartbeat_loop(self, lock: GcsLock, stop_event, step_id: str, lock_key: str, log_dir: str):
        """后台心跳线程：每 HEARTBEAT_INTERVAL_SECONDS 刷新锁 lease。"""
        while not stop_event.is_set():
            stop_event.wait(timeout=HEARTBEAT_INTERVAL_SECONDS)
            if not stop_event.is_set():
                try:
                    lease_expires_at = lock.heartbeat()
                    if stop_event.is_set():
                        break
                    if lease_expires_at is not None:
                        self.bq_status.upsert_step_status(
                            self.experiment, step_id, "running",
                            lock_key=lock_key,
                            lock_owner=self.scheduler_instance_id,
                            attempt=1,
                            params_json=self._params_json,
                            manifest_path=self.manifest_path,
                            manifest_hash=self.manifest_hash,
                            scheduler_instance_id=self.scheduler_instance_id,
                            log_dir=log_dir,
                            force_replace=self.force_replace,
                            lock_acquired_at=lock.acquired_at,
                            lock_expires_at=lease_expires_at,
                            last_heartbeat_at=datetime.now(timezone.utc),
                        )
                except Exception as e:
                    logger.warning("[%s] heartbeat error: %s", self.experiment_id, e)

    def _run_bq_script(self, script_path: str, log_path: str) -> bool:
        """运行 BigQuery SQL 脚本。"""
        sql = self._prepare_bq_sql(script_path)
        if sql is None:
            return False

        # 写入临时 SQL 文件
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sql", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(sql)
            tmp_path = tmp.name

        cmd = [
            "bq", "query",
            "--use_legacy_sql=false",
            f"--location={LOCATION}",
            f"--project_id={PROJECT}",
        ]
        if LOG_LEVEL == "DEBUG":
            cmd.append("--apilog=stdout")

        try:
            with open(log_path, "w", encoding="utf-8") as log_f:
                result = subprocess.run(
                    cmd,
                    stdin=open(tmp_path, "r", encoding="utf-8"),
                    capture_output=True,
                    text=True,
                    timeout=3600,
                )
                log_f.write("--- STDOUT ---\n")
                log_f.write(result.stdout)
                log_f.write("\n--- STDERR ---\n")
                log_f.write(result.stderr)

            if result.returncode != 0:
                logger.error(
                    "[%s] BQ script failed (rc=%d): %s",
                    self.experiment_id, result.returncode, script_path,
                )
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.error("[%s] BQ script timeout: %s", self.experiment_id, script_path)
            return False
        except Exception as e:
            logger.error("[%s] BQ script error: %s: %s", self.experiment_id, script_path, e)
            return False
        finally:
            os.unlink(tmp_path)

    def _preflight_bq_script(self, script_path: str) -> bool:
        """dry-run 预检 BigQuery 脚本参数注入是否完整。"""
        sql = self._prepare_bq_sql(script_path)
        if sql is None:
            return False
        logger.info("[%s] BQ script preflight passed: %s", self.experiment_id, script_path)
        return True

    def _preflight_python_script(self, script_path: str) -> bool:
        """dry-run 预检 Python step 的脚本路径。"""
        if not os.path.isfile(script_path):
            logger.error("Python script not found: %s", script_path)
            return False
        return True

    def _prepare_bq_sql(self, script_path: str) -> Optional[str]:
        """读取 SQL 并强校验所有 DECLARE p_* DEFAULT 参数均已注入。"""
        if not os.path.isfile(script_path):
            logger.error("BQ script not found: %s", script_path)
            return None

        with open(script_path, "r", encoding="utf-8") as f:
            sql = f.read()

        declared_params = self._declared_default_parameters(sql, script_path)
        if declared_params is None:
            return None

        parameter_values = self._bq_parameter_values()
        missing_values = sorted(set(declared_params) - set(parameter_values))
        if missing_values:
            logger.error(
                "[%s] BQ parameter values missing for %s: %s",
                self.experiment_id, script_path, ", ".join(missing_values),
            )
            return None

        injected_params: Set[str] = set()
        for param_name in declared_params:
            try:
                sql, injected = self._inject_parameter(sql, param_name, parameter_values[param_name])
            except ValueError as e:
                logger.error("[%s] BQ parameter injection failed for %s: %s", self.experiment_id, script_path, e)
                return None
            if not injected:
                logger.error(
                    "[%s] BQ parameter declaration not replaced for %s: %s",
                    self.experiment_id, script_path, param_name,
                )
                return None
            injected_params.add(param_name)

        missing_required = self._required_bq_parameters(script_path) - injected_params
        if missing_required:
            logger.error(
                "[%s] BQ script missing required experiment parameters for %s: %s",
                self.experiment_id, script_path, ", ".join(sorted(missing_required)),
            )
            return None

        logger.info(
            "[%s] injected %d BQ parameters for %s",
            self.experiment_id, len(injected_params), script_path,
        )
        return sql

    def _declared_default_parameters(self, sql: str, script_path: str) -> Optional[Dict[str, str]]:
        """返回所有可注入的 DECLARE p_* DEFAULT 参数；格式异常直接阻断。"""
        declared = {m.group(1): m.group(2).upper() for m in SQL_DECLARE_RE.finditer(sql)}
        malformed = []
        for m in BROAD_SQL_DECLARE_RE.finditer(sql):
            name = m.group(1)
            body = m.group("body")
            if re.search(r"\bDEFAULT\b", body, flags=re.IGNORECASE) and name not in declared:
                malformed.append(m.group(0).strip())

        if malformed:
            logger.error(
                "[%s] unsupported DECLARE DEFAULT format in %s: %s",
                self.experiment_id, script_path, " | ".join(malformed),
            )
            return None
        return declared

    def _required_bq_parameters(self, script_path: str) -> Set[str]:
        """当前 runner 中所有 BigQuery step 至少必须带 run/strategy 隔离参数。"""
        required = {"p_run_id", "p_strategy_id"}
        basename = os.path.basename(script_path)
        if basename in {
            "08_run_backtest.sql",
            "09_build_metrics_and_report_inputs.sql",
            "10_qa_runner_outputs.sql",
            "11_model_quality_diagnostics.sql",
            "12_qa_model_diagnosis_outputs.sql",
        }:
            required.add("p_backtest_id")
        if basename in {
            "05_build_candidates.sql",
            "09_build_metrics_and_report_inputs.sql",
            "10_qa_runner_outputs.sql",
            "11_model_quality_diagnostics.sql",
            "12_qa_model_diagnosis_outputs.sql",
        }:
            required.add("p_prediction_run_id")
        return required

    def _bq_parameter_values(self) -> Dict[str, Any]:
        """从 manifest experiment 合成 SQL DECLARE 参数值。"""
        exp = self.experiment
        run_id = exp.get("run_id", "")
        prediction_run_id = exp.get("prediction_run_id") or run_id
        target_holdings = exp.get("target_holdings", 5)

        return {
            "p_run_id": run_id,
            "p_prediction_run_id": prediction_run_id,
            "p_backtest_id": exp.get("backtest_id", ""),
            "p_strategy_id": exp.get("strategy_id", "ml_pv_clf_v0"),
            "p_experiment_id": exp.get("experiment_id", ""),
            "p_experiment_group": exp.get("experiment_group", ""),
            "p_stage_id": exp.get("stage_id", ""),
            "p_force_replace": self.force_replace,
            "p_feature_version": exp.get("feature_version", "strategy1_pv_v0_20260601"),
            "p_feature_set_id": exp.get("feature_set_id", "strategy1_pv_v0_20260601"),
            "p_fin_feature_version": exp.get("fin_feature_version", "fin_default_v0_20260602"),
            "p_label_version": exp.get("label_version", "open_to_close_h1_5_10_20_v20260601"),
            "p_preprocess_version": exp.get("preprocess_version", "raw_v0"),
            "p_label_horizon": exp.get("label_horizon", 5),
            "p_rebalance_frequency": exp.get("rebalance_frequency", "weekly"),
            "p_target_holdings": target_holdings,
            "p_topn": target_holdings,
            "p_max_single_weight": exp.get("max_single_weight", 0.2),
            "p_horizon_natural_frequency": exp.get("horizon_natural_frequency", "weekly"),
            "p_baseline_experiment_id": exp.get("baseline_experiment_id", ""),
            "p_parent_experiment_id": exp.get("parent_experiment_id", ""),
            "p_parent_run_id": exp.get("parent_run_id", ""),
            "p_train_start": exp.get("train_start", DEFAULT_SQL_WINDOWS["train_start"]),
            "p_train_end": exp.get("train_end", DEFAULT_SQL_WINDOWS["train_end"]),
            "p_valid_start": exp.get("valid_start", DEFAULT_SQL_WINDOWS["valid_start"]),
            "p_valid_end": exp.get("valid_end", DEFAULT_SQL_WINDOWS["valid_end"]),
            "p_test_start": exp.get("test_start", DEFAULT_SQL_WINDOWS["test_start"]),
            "p_test_end": exp.get("test_end", DEFAULT_SQL_WINDOWS["test_end"]),
            "p_predict_start": exp.get("predict_start", DEFAULT_SQL_WINDOWS["predict_start"]),
            "p_predict_end": exp.get("predict_end", DEFAULT_SQL_WINDOWS["predict_end"]),
            "p_initial_capital": exp.get("initial_capital", 100000.0),
            "p_cost_profile_id": exp.get("cost_profile_id", "cn_a_share_wanyi_no_min_slip5_v20260602"),
            "p_commission_bps": exp.get("commission_bps", 1.0),
            "p_min_commission_cny": exp.get("min_commission_cny", 0.0),
            "p_stamp_tax_buy_bps": exp.get("stamp_tax_buy_bps", 0.0),
            "p_stamp_tax_sell_bps": exp.get("stamp_tax_sell_bps", 5.0),
            "p_slippage_buy_bps": exp.get("slippage_buy_bps", 5.0),
            "p_slippage_sell_bps": exp.get("slippage_sell_bps", 5.0),
            "p_cost_bps": exp.get("cost_bps", 30.0),
            "p_benchmark": exp.get("benchmark", "000852.SH"),
        }

    def _run_python_script(self, script_path: str, log_path: str) -> bool:
        """运行 Python 脚本。"""
        if not os.path.isfile(script_path):
            logger.error("Python script not found: %s", script_path)
            return False

        exp = self.experiment
        run_id = exp.get("run_id", "")
        prediction_run_id = exp.get("prediction_run_id", run_id)
        backtest_id = exp.get("backtest_id", "")
        label_horizon = exp.get("label_horizon", 5)

        cmd = [
            sys.executable, script_path,
            "--project", PROJECT,
            "--run-id", run_id,
            "--backtest-id", backtest_id,
        ]

        if "render_report" in script_path:
            strategy_id = exp.get("strategy_id", "ml_pv_clf_v0")
            cmd.extend([
                "--strategy-id", strategy_id,
                "--artifact-base-uri", f"gs://{DEFAULT_LOCK_BUCKET}/reports/strategy1",
                "--local-mirror-root", "reports/strategy1",
            ])
            if not self.force_replace:
                cmd.append("--skip-gcs-upload")
        elif "diagnose" in script_path:
            cmd.extend([
                "--artifact-base-uri", f"gs://{DEFAULT_LOCK_BUCKET}/reports/strategy1",
                "--local-mirror-root", "reports/strategy1",
                "--prediction-run-id", prediction_run_id,
                "--p-target-holdings", str(exp.get("target_holdings", 5)),
                "--p-label-horizon", str(label_horizon),
            ])
            if not self.force_replace:
                cmd.append("--skip-gcs-upload")

        try:
            with open(log_path, "w", encoding="utf-8") as log_f:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=7200,
                )
                log_f.write("--- STDOUT ---\n")
                log_f.write(result.stdout)
                log_f.write("\n--- STDERR ---\n")
                log_f.write(result.stderr)

            if result.returncode != 0:
                logger.error(
                    "[%s] Python script failed (rc=%d): %s",
                    self.experiment_id, result.returncode, script_path,
                )
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.error("[%s] Python script timeout: %s", self.experiment_id, script_path)
            return False
        except Exception as e:
            logger.error("[%s] Python script error: %s: %s", self.experiment_id, script_path, e)
            return False

    def _inject_parameter(self, sql: str, param_name: str, value: Any) -> Tuple[str, bool]:
        """替换 SQL 中的 DECLARE 语句默认值，并返回是否命中。"""
        pattern = re.compile(
            rf"(?im)^(\s*DECLARE\s+{re.escape(param_name)}\s+)"
            r"(STRING|INT64|FLOAT64|BOOL|DATE|TIMESTAMP)"
            r"(\s+DEFAULT\s+)([^;]*?)(;)"
        )
        m = pattern.search(sql)
        if not m:
            return sql, False

        prefix = m.group(1)
        dtype = m.group(2)
        sep = m.group(3)
        suffix = m.group(5)
        literal = self._format_sql_literal(dtype, value, param_name)
        new_decl = f"{prefix}{dtype}{sep}{literal}{suffix}"
        return sql[:m.start()] + new_decl + sql[m.end():], True

    def _format_sql_literal(self, dtype: str, value: Any, param_name: str) -> str:
        """把 manifest 值转成对应 BigQuery DECLARE literal。"""
        dtype_upper = dtype.upper()
        if value is None:
            return "NULL"

        if dtype_upper == "STRING":
            escaped = str(value).replace("'", "''")
            return f"'{escaped}'"

        if dtype_upper == "BOOL":
            if isinstance(value, bool):
                return "TRUE" if value else "FALSE"
            text = str(value).strip().upper()
            if text in {"TRUE", "FALSE"}:
                return text
            raise ValueError(f"{param_name} expects BOOL, got {value!r}")

        if dtype_upper == "INT64":
            if isinstance(value, bool):
                raise ValueError(f"{param_name} expects INT64, got bool")
            try:
                return str(int(value))
            except (TypeError, ValueError) as e:
                raise ValueError(f"{param_name} expects INT64, got {value!r}") from e

        if dtype_upper == "FLOAT64":
            if isinstance(value, bool):
                raise ValueError(f"{param_name} expects FLOAT64, got bool")
            try:
                return repr(float(value))
            except (TypeError, ValueError) as e:
                raise ValueError(f"{param_name} expects FLOAT64, got {value!r}") from e

        if dtype_upper == "DATE":
            return f"DATE '{value}'"

        if dtype_upper == "TIMESTAMP":
            return f"TIMESTAMP '{value}'"

        raise ValueError(f"{param_name} has unsupported type {dtype}")


# ---------------------------------------------------------------------------
# 调度器
# ---------------------------------------------------------------------------

class Scheduler:
    """实验调度器入口。"""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.scheduler_instance_id = args.scheduler_instance_id or _default_instance_id()
        self.manifest_path = args.manifest or DEFAULT_MANIFEST
        self.dry_run = args.dry_run
        self.force_replace = args.force_replace
        self.resume = args.resume
        self.resume_from_step = args.resume_from_step
        self.fail_fast = args.fail_fast
        self.allow_cross_stage = args.allow_cross_stage
        self.max_parallel = args.max_parallel
        self.max_parallel_backtest = args.max_parallel_backtest
        self.lock_ttl_minutes = args.lock_ttl_minutes or DEFAULT_LOCK_TTL_MINUTES
        self.log_dir_base = args.log_dir or DEFAULT_LOG_DIR
        self.stage_id = args.stage_id
        self.experiment_ids = args.experiment_id

        self.bq_status = BqStatusTable(dry_run=self.dry_run)

    def run(self) -> int:
        """执行调度。返回退出的 rc。"""
        logger.info("=== OQ-010 实验调度器 ===")
        logger.info("manifest: %s", self.manifest_path)
        logger.info("scheduler_instance_id: %s", self.scheduler_instance_id)
        logger.info("dry_run: %s", self.dry_run)
        logger.info("force_replace: %s", self.force_replace)
        logger.info("resume: %s", self.resume)
        logger.info("resume_from_step: %s", self.resume_from_step)
        logger.info("fail_fast: %s", self.fail_fast)
        logger.info("max_parallel: %s", self.max_parallel)
        logger.info("max_parallel_backtest: %s", self.max_parallel_backtest)
        logger.info("stage_id: %s", self.stage_id)
        logger.info("experiment_ids: %s", self.experiment_ids)

        # 加载 manifest
        try:
            manifest = load_manifest(self.manifest_path)
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            logger.error("manifest load failed: %s", e)
            return 1

        mhash = _manifest_hash(self.manifest_path)

        # 解析实验
        experiments = resolve_experiments(manifest, self.stage_id, self.experiment_ids)

        if not experiments:
            logger.warning("no experiments to run")
            return 0

        logger.info("resolved %d experiments", len(experiments))

        # 构建并发批次
        batches = self._build_batches(experiments)
        logger.info("built %d batches", len(batches))

        # dry-run 输出
        if self.dry_run:
            preflight_ok = self._preflight_dry_run(experiments, mhash)
            self._print_dry_run_plan(manifest, experiments, batches)
            return 0 if preflight_ok else 1

        # 执行
        rc = self._execute_batches(batches, manifest, mhash)
        return rc

    def _build_batches(self, experiments: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """按依赖将实验分组为批次。同批次实验可并发。"""
        if self.allow_cross_stage:
            # 跨阶段时，按依赖关系分组
            return self._build_dependency_batches(experiments)
        else:
            # 同 stage 内，按 stage_id 分组
            return self._build_stage_batches(experiments)

    def _build_stage_batches(self, experiments: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """按 stage_id 分组为批次。"""
        stages: Dict[str, List[Dict[str, Any]]] = {}
        for exp in experiments:
            sid = exp.get("stage_id", "default")
            stages.setdefault(sid, []).append(exp)

        # 保持 manifest 顺序
        seen = set()
        ordered_batches = []
        for exp in experiments:
            sid = exp.get("stage_id", "default")
            if sid not in seen:
                seen.add(sid)
                ordered_batches.append(stages[sid])
        return ordered_batches

    def _build_dependency_batches(self, experiments: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """按依赖关系分组实验。"""
        dep_map = {}
        for exp in experiments:
            dep_id = exp.get("depends_on_experiment_id")
            dep_map[exp["experiment_id"]] = dep_id

        exp_by_id = {e["experiment_id"]: e for e in experiments}
        batches = []
        remaining = set(exp["experiment_id"] for exp in experiments)

        while remaining:
            batch = []
            for eid in list(remaining):
                dep = dep_map.get(eid)
                if dep is None or dep not in remaining:
                    batch.append(exp_by_id[eid])
                    remaining.remove(eid)
            if not batch:
                logger.error("dependency cycle detected: %s", remaining)
                break
            batches.append(batch)

        return batches

    def _preflight_dry_run(self, experiments: List[Dict[str, Any]], manifest_hash: str) -> bool:
        """dry-run 阶段预检可执行实验的脚本与参数注入。"""
        ok = True
        for exp in experiments:
            status = str(exp.get("status", "planned"))
            if status.startswith("blocked"):
                logger.info("[%s] dry-run preflight skipped blocked experiment: %s", exp.get("experiment_id"), status)
                continue

            executor_unit = ExperimentExecutor(
                experiment=exp,
                manifest_path=self.manifest_path,
                manifest_hash=manifest_hash,
                scheduler_instance_id=self.scheduler_instance_id,
                lock_ttl_minutes=self.lock_ttl_minutes,
                force_replace=self.force_replace,
                resume=self.resume,
                resume_from_step=self.resume_from_step,
                dry_run=True,
                log_dir_base=self.log_dir_base,
                max_parallel_backtest=self.max_parallel_backtest,
                backtest_semaphore=None,
            )
            for step_id in get_experiment_steps(exp, self.max_parallel_backtest):
                step_def = STEP_DEFS.get(step_id, {})
                bq_script = step_def.get("bq_script")
                python_script = step_def.get("python_script")
                if bq_script and not executor_unit._preflight_bq_script(bq_script):
                    ok = False
                if python_script and not executor_unit._preflight_python_script(python_script):
                    ok = False
        return ok

    def _print_dry_run_plan(
        self,
        manifest: Dict[str, Any],
        experiments: List[Dict[str, Any]],
        batches: List[List[Dict[str, Any]]],
    ):
        """打印 dry-run 计划。"""
        print("=" * 70)
        print("OQ-010 DRY RUN PLAN")
        print("=" * 70)
        print(f"Manifest version: {manifest.get('manifest_version')}")
        print(f"Strategy: {manifest.get('strategy_id')}")
        print(f"Baseline: {manifest.get('baseline_experiment_id')}")
        print()

        print("--- Config ---")
        print(f"  max_parallel: {self.max_parallel}")
        print(f"  max_parallel_backtest: {self.max_parallel_backtest}")
        print(f"  force_replace: {self.force_replace}")
        print(f"  resume: {self.resume}")
        print(f"  resume_from_step: {self.resume_from_step}")
        print(f"  allow_cross_stage: {self.allow_cross_stage}")
        print(f"  lock_ttl_minutes: {self.lock_ttl_minutes}")
        print()

        print("--- Experiments ---")
        for exp in experiments:
            eid = exp.get("experiment_id", "?")
            rid = exp.get("run_id", "?")
            prid = exp.get("prediction_run_id", rid)
            bt = exp.get("backtest_id", "?")
            st = exp.get("stage_id", "?")
            retrain = exp.get("requires_retrain", False)
            deps = exp.get("depends_on_experiment_id", "none")
            print(f"  {eid}")
            print(f"    run_id: {rid}")
            print(f"    prediction_run_id: {prid}")
            print(f"    backtest_id: {bt}")
            print(f"    stage_id: {st}")
            print(f"    requires_retrain: {retrain}")
            print(f"    depends_on: {deps}")
            print()

        print("--- Batches (concurrent groups) ---")
        for i, batch in enumerate(batches):
            print(f"  Batch {i + 1}:")
            for exp in batch:
                eid = exp.get("experiment_id", "?")
                steps = get_experiment_steps(exp, self.max_parallel_backtest)
                print(f"    {eid}: {len(steps)} steps")
                for step_id in steps:
                    step_def = STEP_DEFS.get(step_id, {})
                    lock_key = _build_lock_key(
                        step_def.get("lock_key_template", "unknown:{run_id}"), exp
                    )
                    ads_tables = step_def.get("ads_tables", [])
                    print(f"      - {step_id} ({step_def.get('display_name', step_id)})")
                    print(f"        lock_key: {lock_key}")
                    print(f"        ads_tables: {', '.join(ads_tables)}")
            print()

        print("--- Blocked experiments ---")
        # 找出被依赖阻断的实验
        dep_map = {}
        for exp in experiments:
            dep_id = exp.get("depends_on_experiment_id")
            if dep_id:
                dep_map[exp["experiment_id"]] = dep_id
        exp_ids = {e["experiment_id"] for e in experiments}
        for eid, dep in dep_map.items():
            if dep not in exp_ids:
                print(f"  {eid} is blocked until {dep} completes")
        print()
        print("=== END DRY RUN ===")

    def _execute_batches(
        self,
        batches: List[List[Dict[str, Any]]],
        manifest: Dict[str, Any],
        manifest_hash: str,
    ) -> int:
        """执行批次。"""
        import threading

        backtest_semaphore = threading.Semaphore(self.max_parallel_backtest)

        total_rc = 0
        for batch_idx, batch in enumerate(batches):
            logger.info("=== Batch %d / %d (%d experiments) ===", batch_idx + 1, len(batches), len(batch))

            with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
                futures = {}
                for exp in batch:
                    executor_unit = ExperimentExecutor(
                        experiment=exp,
                        manifest_path=self.manifest_path,
                        manifest_hash=manifest_hash,
                        scheduler_instance_id=self.scheduler_instance_id,
                        lock_ttl_minutes=self.lock_ttl_minutes,
                        force_replace=self.force_replace,
                        resume=self.resume,
                        resume_from_step=self.resume_from_step,
                        dry_run=self.dry_run,
                        log_dir_base=self.log_dir_base,
                        max_parallel_backtest=self.max_parallel_backtest,
                        backtest_semaphore=backtest_semaphore,
                    )
                    future = executor.submit(executor_unit.run)
                    futures[future] = exp["experiment_id"]

                for future in as_completed(futures):
                    eid = futures[future]
                    try:
                        result = future.result()
                        status = result.get("status", "unknown")
                        logger.info("[%s] done: status=%s", eid, status)
                        if status == "failed":
                            total_rc = 1
                            if self.fail_fast:
                                logger.error("fail-fast: stopping after %s failure", eid)
                                executor.shutdown(wait=False, cancel_futures=True)
                                return total_rc
                    except Exception as e:
                        logger.error("[%s] executor exception: %s", eid, e)
                        total_rc = 1
                        if self.fail_fast:
                            return total_rc

        logger.info("=== All batches complete ===")
        return total_rc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

LOG_LEVEL = "INFO"


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OQ-010: 策略 1 实验并发调度器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--manifest",
        default=DEFAULT_MANIFEST,
        help=f"实验 manifest 路径（默认: {DEFAULT_MANIFEST}）",
    )
    parser.add_argument(
        "--stage-id",
        help="运行阶段，如 stage_a",
    )
    parser.add_argument(
        "--experiment-id",
        action="append",
        dest="experiment_id",
        help="限定要跑的实验（可重复传入）",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=2,
        help="总并发实验数（默认 2）",
    )
    parser.add_argument(
        "--max-parallel-backtest",
        type=int,
        default=1,
        help="08 ledger 最大并发数（默认 1）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只展开计划，不执行",
    )
    parser.add_argument(
        "--force-replace",
        action="store_true",
        help="对当前实验启用清理重跑",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="从状态表恢复失败或未完成实验",
    )
    parser.add_argument(
        "--resume-from-step",
        help="从指定 step 恢复",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="任一实验失败后停止提交新实验",
    )
    parser.add_argument(
        "--allow-cross-stage",
        action="store_true",
        help="显式允许跨阶段并发（默认关闭）",
    )
    parser.add_argument(
        "--log-dir",
        default=DEFAULT_LOG_DIR,
        help=f"本地调度日志目录（默认 {DEFAULT_LOG_DIR}）",
    )
    parser.add_argument(
        "--scheduler-instance-id",
        help="调度器实例 ID（默认由 hostname+pid+timestamp 生成）",
    )
    parser.add_argument(
        "--lock-ttl-minutes",
        type=int,
        default=DEFAULT_LOCK_TTL_MINUTES,
        help=f"step lock lease TTL 分钟数（默认 {DEFAULT_LOCK_TTL_MINUTES}）",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="输出 debug 日志",
    )

    return parser.parse_args(argv)


def configure_logging(verbose: bool):
    global LOG_LEVEL
    level = logging.DEBUG if verbose else logging.INFO
    LOG_LEVEL = "DEBUG" if verbose else "INFO"
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)

    scheduler = Scheduler(args)
    rc = scheduler.run()

    logger.info("scheduler exit with rc=%d", rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
