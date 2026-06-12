from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for path in (REPO_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture
def run_module():
    def _run_module(
        module: str,
        args: list[str] | None = None,
        *,
        cwd: Path | str = REPO_ROOT,
        env_extra: dict[str, str] | None = None,
        timeout: int = 60,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        paths = [str(REPO_ROOT), str(SRC_ROOT)]
        existing = env.get("PYTHONPATH")
        env["PYTHONPATH"] = os.pathsep.join(paths + ([existing] if existing else []))
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, "-m", module, *(args or [])],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=check,
            timeout=timeout,
        )

    return _run_module
