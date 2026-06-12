"""Compatibility wrapper for Strategy1 BigQuery/GCS helpers."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists() and str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from quant_ashare.strategy1.bq_io import *  # noqa: E402,F401,F403
from quant_ashare.strategy1.bq_io import (  # noqa: E402,F401
    ADS,
    bq_label_value,
    download_gcs_file,
    download_gcs_prefix,
    env_container_image,
    execute_query,
    get_git_commit,
    job_audit_dict,
    join_gs_uri,
    json_dumps_strict,
    load_dataframe,
    make_client,
    parse_gs_uri,
    query_dataframe,
    query_dataframe_with_job,
    run_safe,
    upload_directory_to_gcs,
    write_json,
    write_text,
)
