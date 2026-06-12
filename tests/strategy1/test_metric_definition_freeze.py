from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

SCAN_ROOTS = (
    "scripts/strategy1",
    "scripts/strategy1_cloudrun",
    "src/quant_ashare/strategy1",
)
FROZEN_NAME_PATTERNS = (
    "max_drawdown",
    "compound_annualized_return",
    "compound_annual_return",
    "cumulative_return",
    "sharpe",
    "annualized_vol",
    "calmar",
    "safe_ratio",
    "fmt_pct",
    "fmt_pp",
    "fmt_num",
    "markdown_table",
)
ALLOWED_DEFINITIONS = {
    "scripts/strategy1/analyze_official_adj_leak.py:compound_annualized_return",
    "scripts/strategy1/analyze_official_adj_leak.py:cumulative_return",
    "scripts/strategy1/analyze_official_adj_leak.py:fmt_num",
    "scripts/strategy1/analyze_official_adj_leak.py:fmt_pct",
    "scripts/strategy1/analyze_official_adj_leak.py:fmt_pp",
    "scripts/strategy1/analyze_official_adj_leak.py:markdown_table",
    "scripts/strategy1/analyze_official_adj_leak.py:max_drawdown",
    "scripts/strategy1/analyze_official_adj_leak.py:safe_ratio",
    "scripts/strategy1/analyze_signal_ic_decomposition.py:compound_annual_return",
    "scripts/strategy1/analyze_signal_ic_decomposition.py:fmt_pct",
    "scripts/strategy1/analyze_signal_ic_decomposition.py:markdown_table",
    "scripts/strategy1/analyze_signal_ic_decomposition.py:max_drawdown",
    "scripts/strategy1/analyze_signal_ic_decomposition.py:safe_ratio",
    "scripts/strategy1/analyze_tail_risk.py:fmt_pct",
    "scripts/strategy1/analyze_tail_risk.py:validate_max_drawdown",
    "scripts/strategy1/analyze_topdown_lot_phase0.py:compound_annual_return",
    "scripts/strategy1/render_report.py:compound_annualized_return",
    "scripts/strategy1/replay_acceptance_gate_v3.py:annualized_volatility_from_daily_returns",
    "scripts/strategy1/replay_acceptance_gate_v3.py:compound_annualized_return",
    "scripts/strategy1/replay_acceptance_gate_v3.py:compound_annualized_return_from_gross",
    "scripts/strategy1/replay_acceptance_gate_v3.py:evaluate_excess_calmar_branch",
    "scripts/strategy1/replay_acceptance_gate_v3.py:max_drawdown_window",
    "scripts/strategy1/replay_acceptance_gate_v3.py:signed_zero_safe_ratio",
    "scripts/strategy1/simulate_exposure_overlay_upper_bound.py:compound_annualized_return",
    "scripts/strategy1/simulate_exposure_overlay_upper_bound.py:cumulative_return",
    "scripts/strategy1/simulate_exposure_overlay_upper_bound.py:fmt_num",
    "scripts/strategy1/simulate_exposure_overlay_upper_bound.py:fmt_pct",
    "scripts/strategy1/simulate_exposure_overlay_upper_bound.py:markdown_table",
    "scripts/strategy1/simulate_exposure_overlay_upper_bound.py:max_drawdown",
    "scripts/strategy1/simulate_exposure_overlay_upper_bound.py:safe_ratio",
    "scripts/strategy1/simulate_exposure_overlay_upper_bound.py:verdict_for_calmar",
    "src/quant_ashare/strategy1/acceptance.py:full_period_max_drawdown_threshold",
    "src/quant_ashare/strategy1/acceptance.py:risk_feature_max_drawdown_target",
    "src/quant_ashare/strategy1/train_candidate_task.py:safe_ratio",
}


def test_metric_and_formatting_definitions_stay_on_explicit_allowlist() -> None:
    discovered = set()
    for root in SCAN_ROOTS:
        for path in sorted((REPO_ROOT / root).glob("**/*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
            rel_path = path.relative_to(REPO_ROOT).as_posix()
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if any(pattern in node.name for pattern in FROZEN_NAME_PATTERNS):
                    discovered.add(f"{rel_path}:{node.name}")

    unexpected = sorted(discovered - ALLOWED_DEFINITIONS)
    missing = sorted(ALLOWED_DEFINITIONS - discovered)
    assert unexpected == [], (
        "New local metric/formatting definitions are frozen. Reuse an existing "
        "implementation or extract a shared module before updating the allowlist: "
        f"{unexpected}"
    )
    assert missing == []
