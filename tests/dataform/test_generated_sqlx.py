from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_generated_dataform_sqlx_is_current() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/dataform/generate_sqlx_from_sql.py",
            "--check",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
