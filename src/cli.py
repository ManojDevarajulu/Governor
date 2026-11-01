"""
Command-line interface for the Governor AI Safety Research Harness.
"""

import argparse
import sys
from typing import List

from src.evaluator import Evaluator, ProtocolEvaluationReport
from src.interceptors import ProtocolType
from src.linter import lint_paths
from src.models import get_provider
from src.models.runner import run_live_model_episode
from src.scenarios import get_all_scenarios


def print_report_table(reports: List[ProtocolEvaluationReport]):
    print("\n" + "=" * 80)
    print(" GOVERNOR RESEARCH EVALUATION: PROTOCOL COMPARISON")
    print("=" * 80)
    print(f"{'Protocol':<24} | {'Episodes':<8} | {'Boundary Violation Rate (95% CI)':<30} | {'False Positive':<15}")
    print("-" * 80)
    for r in reports:
        bvr_str = f"{r.overall_bvr.proportion*100:.1f}% [{r.overall_bvr.ci_lower*100:.1f}%-{r.overall_bvr.ci_upper*100:.1f}%]"
        fp_str = f"{r.overall_false_positive.proportion*100:.1f}%"
        print(f"{r.protocol:<24} | {r.total_episodes:<8} | {bvr_str:<30} | {fp_str:<15}")

    print("\n" + "=" * 80)
    print(" CAUSAL ATTRIBUTION: LOGISTIC REGRESSION (RQ1: Depth vs RQ2: Lag)")
    print("=" * 80)
    for r in reports:
        if r.regression:
            print(f"[{r.protocol}]:")
            print(f"  * Intercept (beta_0): {r.regression.intercept}")
            print(f"  * Turn Depth Coef (beta_depth): {r.regression.coef_depth} (Odds Ratio: {r.regression.odds_ratio_depth():.2f}x per turn)")
            print(f"  * Instruction Lag Coef (beta_lag): {r.regression.coef_lag} (Odds Ratio: {r.regression.odds_ratio_lag():.2f}x per turn)")
        else:
            print(f"[{r.protocol}]: Zero violations (deterministic containment).")
    print("=" * 80 + "\n")


def run_eval(protocol_name: str = "all", seeds: int = 25):
    evaluator = Evaluator()
    protocols_to_run = (
        [
            ProtocolType.UNMONITORED_BASELINE,
            ProtocolType.COT_MONITOR,
            ProtocolType.DEFER_TO_RESAMPLE,
            ProtocolType.INVARIANT_GOVERNOR,
        ]
        if protocol_name == "all"
        else [ProtocolType(protocol_name)]
    )

    reports = []
    for proto in protocols_to_run:
        print(f"Running evaluation sweep for protocol: {proto.value} ({seeds} seeds x 12 cells x 6 scenarios)...")
        rep = evaluator.evaluate_protocol(proto, seeds_per_cell=seeds)
        reports.append(rep)

    print_report_table(reports)


def run_model_cli(
    model_spec: str,
    scenario_id: str,
    protocol_name: str,
    depth: int,
    lag: int,
):
    provider = get_provider(model_spec)
    evaluator = Evaluator()
    scenarios = {s.scenario_id: s for s in get_all_scenarios()}
    
    # Match scenario
    selected_scenario = None
    for k, v in scenarios.items():
        if k.startswith(scenario_id) or scenario_id in k:
            selected_scenario = v
            break
    if not selected_scenario:
        print(f"Error: Unknown scenario '{scenario_id}'. Available: {list(scenarios.keys())}")
        sys.exit(1)

    interceptor = evaluator.get_interceptor(ProtocolType(protocol_name), allowed_scope="/project")

    print("\n" + "=" * 70)
    print(f" GOVERNOR LIVE MODEL EVALUATION")
    print("=" * 70)
    print(f"Model:          {model_spec}")
    print(f"Scenario:       {selected_scenario.scenario_id} ({selected_scenario.name})")
    print(f"Protocol:       {protocol_name}")
    print(f"Turn Depth:     {depth} progress turns")
    print(f"Instruction Lag:{lag} turns since boundary statement")
    print("-" * 70)

    result = run_live_model_episode(
        provider=provider,
        scenario=selected_scenario,
        interceptor=interceptor,
        turn_depth=depth,
        instruction_lag=lag,
    )

    if result.cot_reasoning:
        print(f"\n[Model Chain-of-Thought Scratchpad]:\n{result.cot_reasoning}\n")
    print(f"[Model Tool Action]: {result.op} -> {result.target_path}")
    print(f"[Boundary Violation Attempted]: {'YES (Escaped)' if result.is_boundary_violation else 'NO (Safe)'}")
    print(f"[Interceptor Blocked]:         {'HALTED' if result.blocked_by_interceptor else 'ALLOWED'}")
    if result.interceptor_reason:
        print(f"[Interceptor Reason]:          {result.interceptor_reason}")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Governor: Measuring and Containing Stop-Instruction Persistence in Long Agent Trajectories",
    )
    subparsers = parser.add_subparsers(dest="command")

    # eval command
    eval_p = subparsers.add_parser("eval", help="Run empirical parameter sweep across depth/lag cells")
    eval_p.add_argument("--protocol", "-p", default="all", choices=["all", "UNMONITORED_BASELINE", "COT_MONITOR", "DEFER_TO_RESAMPLE", "INVARIANT_GOVERNOR"], help="Protocol to evaluate")
    eval_p.add_argument("--episodes", "-e", type=int, default=25, help="Number of seeds per cell")

    # lint command
    lint_p = subparsers.add_parser("lint", help="Run AST anti-determinism linter on harness code")
    lint_p.add_argument("paths", nargs="*", default=["src/", "tests/"], help="Paths to lint")

    # run-model command
    model_p = subparsers.add_parser("run-model", help="Run a live open-weight or frontier model on a trajectory")
    model_p.add_argument("--model", "-m", default="mock", help="Model specification (e.g. 'mock', 'ollama/llama3.3', 'anthropic/claude-3-5-sonnet')")
    model_p.add_argument("--scenario", "-s", default="S1", help="Scenario ID (S1 through S6)")
    model_p.add_argument("--protocol", "-p", default="INVARIANT_GOVERNOR", choices=["UNMONITORED_BASELINE", "COT_MONITOR", "DEFER_TO_RESAMPLE", "INVARIANT_GOVERNOR"], help="Protocol to enforce")
    model_p.add_argument("--depth", "-d", type=int, default=6, help="Turn depth before temptation")
    model_p.add_argument("--lag", "-l", type=int, default=2, help="Instruction lag since boundary rule")

    args = parser.parse_args()

    if not args.command or args.command == "eval":
        proto = getattr(args, "protocol", "all")
        episodes = getattr(args, "episodes", 25)
        run_eval(protocol_name=proto, seeds=episodes)
    elif args.command == "lint":
        count, violations = lint_paths(args.paths)
        if count == 0:
            print("[AST Anti-Determinism Linter]: PASSED. Zero non-deterministic patterns detected.")
            sys.exit(0)
        else:
            print(f"[AST Anti-Determinism Linter]: FAILED with {count} violation(s):\n")
            for v in violations:
                print(f"  {v.file_path}:{v.line_number} [{v.rule}] {v.message}")
            sys.exit(1)
    elif args.command == "run-model":
        run_model_cli(
            model_spec=args.model,
            scenario_id=args.scenario,
            protocol_name=args.protocol,
            depth=args.depth,
            lag=args.lag,
        )


if __name__ == "__main__":
    main()
