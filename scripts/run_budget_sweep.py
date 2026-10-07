"""Run from the repository root: python scripts/run_budget_sweep.py --help."""

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.parser import load_ptn
from src.pool_generator import generate_line_pool
from src.heuristics.greedy_pool import PoolProblem, greedy_select
from src.heuristics.budget_sweep import run_budget_sweep
from src.heuristics.input_audit import audit_lintim_frequency_inputs
from src.utils import line_cost_params, capacity_load_mismatches


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plot_results(output, result):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for method in ("greedy", "lp_rounding"):
        rows = [r for r in result["records"] if r["method"] == method and r["best_feasible"]]
        ax.plot([r["budget"] for r in rows],
                [r["best_feasible"]["coverage_percentage"] for r in rows],
                marker="o", label=method.replace("_", " "))
    title_prefix = "DIAGNOSTIC ONLY - " if result.get("input_audit", {}).get("legacy_diagnostic") else ""
    ax.set(xlabel="Budget (team cost units)", ylabel="Direct-demand coverage (%)",
           title=f"{title_prefix}{result['dataset']}: discrete budget sweep", ylim=(-2, 102))
    ax.grid(alpha=.25)
    ax.legend()
    fig.text(.5, .015, "Coverage proxy; passenger capacity and routing are not certified.",
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .04, 1, 1))
    fig.savefig(output / "budget_coverage.png", dpi=170)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-root", type=Path, default=ROOT / "data")
    ap.add_argument("--datasets", nargs="+", default=["toy", "mandl", "sioux_falls"])
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--budgets", nargs="+", type=float, help="Explicit absolute budgets.")
    group.add_argument("--factors", nargs="+", type=float,
                       help="Multiples of a feasible greedy reference cost (not an optimum).")
    ap.add_argument("--solver", choices=["scipy", "gurobi", "scip", "auto"], default="scipy")
    ap.add_argument("--time-limit", type=float, default=60)
    ap.add_argument("--pool-source", choices=["generate", "existing"], default="generate")
    ap.add_argument("--max-edges", type=int, default=12)
    ap.add_argument("--min-edges", type=int, default=2)
    ap.add_argument("--k-paths", type=int, default=3)
    ap.add_argument("--reference-cost", type=float,
                    help="Reference cost for factors, e.g. a same-pool baseline incumbent; not a claim of optimality.")
    ap.add_argument("--allow-legacy-frequency-bounds", action="store_true",
                    help="Diagnostic only: reproduce the team's erroneous fallback to Edge travel times.")
    ap.add_argument("--output", type=Path, default=ROOT / "results" / "heuristics")
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()
    if args.min_edges < 1 or args.max_edges < args.min_edges or args.k_paths < 1:
        ap.error("Require 1 <= min-edges <= max-edges and k-paths >= 1.")
    if args.reference_cost is not None:
        from math import isfinite
        if not isfinite(args.reference_cost) or args.reference_cost <= 0 or args.budgets is not None:
            ap.error("--reference-cost must be positive and finite and cannot be used with --budgets.")
    print("Metric: direct-demand coverage, without passenger capacity assignment.")
    print("Constraints and costs follow the uploaded team's utils.py; see README limitations.")
    failures = 0
    for dataset in args.datasets:
        try:
            directory = args.data_root / dataset
            for name in ("Stop.giv", "Edge.giv", "OD.giv", "Config.cnf"):
                if not (directory / "basis" / name).is_file():
                    raise FileNotFoundError(f"Missing {directory / 'basis' / name}")
            ptn = load_ptn(str(directory), str(args.data_root / "Global-Config.cnf"))
            audit = audit_lintim_frequency_inputs(ptn, args.allow_legacy_frequency_bounds)
            if audit["legacy_diagnostic"]:
                print(f"{dataset}: DIAGNOSTIC ONLY: travel-time bounds are being used as frequencies.")
            # The metric does not consume capacity, but fail early if input
            # configuration is incomplete rather than treating it as verified.
            capacity = ptn.vehicle_capacity
            started = perf_counter()
            pool = (generate_line_pool(ptn, min_edges=args.min_edges, max_edges=args.max_edges, k_paths_per_pair=args.k_paths)
                    if args.pool_source == "generate" else ptn.pool)
            if not pool:
                raise ValueError("Empty candidate pool.")
            # Existing generator's first Yen path can exceed max_edges. Do not
            # silently change a shared pool: stop and expose the mismatch.
            overlong = [lid for lid, line in pool.items() if len(line.edges) > args.max_edges] if args.pool_source == "generate" else []
            if overlong:
                if not args.allow_legacy_frequency_bounds:
                    raise ValueError("Generated pool exceeds --max-edges. Review pool_generator.py's first-path handling.")
                audit["issues"].append(f"Legacy pool contains {len(overlong)} lines longer than requested max-edges.")
                audit["legacy_diagnostic"] = True
                print(f"{dataset}: DIAGNOSTIC ONLY: retained {len(overlong)} overlong lines to reproduce the same baseline pool.")
            pool = PoolProblem(ptn, pool).pool
            pool_seconds = perf_counter() - started
            reference = None
            if args.budgets is not None:
                budgets = args.budgets
            else:
                factors = args.factors or [1.0, 1.25, 1.5, 1.75, 2.0]
                from math import isfinite
                if any(not isfinite(f) or f < 0 for f in factors):
                    raise ValueError("Budget factors must be finite and nonnegative.")
                if args.reference_cost is not None:
                    reference_cost = args.reference_cost
                else:
                    max_lower = max(lo for lo, _ in PoolProblem(ptn, pool).bounds.values())
                    generous_budget = (max_lower + 1) * sum(l.cost for l in pool.values())
                    reference = greedy_select(ptn, pool, generous_budget, improve_service=False)
                    if not reference.feasible or reference.cost == 0:
                        raise ValueError("No positive-cost greedy reference; supply --budgets or --reference-cost explicitly.")
                    reference_cost = reference.cost
                budgets = [reference_cost * f for f in factors]
            result = run_budget_sweep(ptn, pool, budgets, args.solver, args.time_limit)
            inputs = [p for p in (directory / "basis").iterdir() if p.is_file()]
            global_config = args.data_root / "Global-Config.cnf"
            if global_config.is_file():
                inputs.append(global_config)
            result.update({
                "dataset": dataset, "pool": [asdict(l) for l in pool.values()],
                "input_audit": audit,
                "pool_length_limit_violations": overlong,
                "pool_generation_seconds": pool_seconds,
                "reference": asdict(reference) if reference else None,
                "reference_kind": ("feasible_greedy_cost_not_exact_optimum" if reference else
                                   "user_supplied_reference_cost" if args.reference_cost is not None else "explicit_budgets"),
                "vehicle_capacity": capacity,
                "capacity_load_mismatches": capacity_load_mismatches(ptn),
                "cost_parameters": dict(zip(["fixed_per_frequency", "per_length", "per_edge"], line_cost_params(ptn.config))),
                "effective_frequency_bounds": PoolProblem(ptn, pool).bounds,
                "input_sha256": {str(p.relative_to(args.data_root)): file_hash(p) for p in sorted(inputs)},
                "source_sha256": {str(p.relative_to(ROOT)): file_hash(p) for p in sorted((ROOT / "src").rglob("*.py"))},
                "arguments": {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
                "python_version": sys.version,
            })
            output = args.output / dataset
            output.mkdir(parents=True, exist_ok=True)
            (output / "budget_sweep.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
            with (output / "budget_sweep.csv").open("w", newline="") as handle:
                fields = ["dataset", "legacy_diagnostic", "method", "budget", "raw_status", "raw_feasible", "raw_cost",
                          "raw_direct_demand_coverage", "selected_feasible", "selected_cost", "selected_coverage_percent",
                          "selected_from_budget", "carried_forward", "trial_seconds", "shared_lp_seconds", "lp_cost_lower_bound"]
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for row in result["records"]:
                    raw, best = row["raw"], row["best_feasible"]
                    writer.writerow(dict(
                        dataset=dataset, legacy_diagnostic=audit["legacy_diagnostic"], method=row["method"], budget=row["budget"],
                        raw_status=raw["status"], raw_feasible=raw["frequency_feasible"] and raw["budget_feasible"],
                        raw_cost=raw["cost"], raw_direct_demand_coverage=raw["direct_demand_coverage"],
                        selected_feasible=best is not None, selected_cost=best["cost"] if best else "",
                        selected_coverage_percent=best["coverage_percentage"] if best else "",
                        selected_from_budget=row["selected_from_budget"], carried_forward=row["carried_forward"],
                        trial_seconds=raw["runtime_seconds"], shared_lp_seconds=result["lp"]["runtime_seconds"],
                        lp_cost_lower_bound=result["lp"]["cost_lower_bound"]))
            if args.plot:
                plot_results(output, result)
            feasible_count = sum(r["best_feasible"] is not None for r in result["records"])
            print(f"{dataset}: {len(pool)} lines; {feasible_count}/{len(result['records'])} feasible method/budget results -> {output}")
        except (ValueError, FileNotFoundError, KeyError, ImportError, RuntimeError) as exc:
            failures += 1
            print(f"{dataset}: ERROR: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
