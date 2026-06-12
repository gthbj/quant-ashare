from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ingestion_meta_missing_alert_is_wired() -> None:
    sql = (REPO_ROOT / "sql/observability/01_pipeline_status_views.sql").read_text()
    setup = (REPO_ROOT / "scripts/alerting/setup_alerts.py").read_text()
    readme = (REPO_ROOT / "scripts/alerting/README.md").read_text()

    assert "v_ingestion_meta_missing" in sql
    assert "ingestion.ingest_current_scope_write" in sql
    assert "'ingestion_meta_missing'" in sql
    assert "ashare_pipeline_ingestion_meta_missing" in setup
    assert 'jsonPayload.alert_type="ingestion_meta_missing"' in setup
    assert "Ingestion Meta Missing" in readme
