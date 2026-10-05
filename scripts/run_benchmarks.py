#!/usr/bin/env python3
"""
Unified Benchmark Suite for Line Planning.
Runs the baseline solver across all 5 benchmark datasets and outputs
a LaTeX/Markdown comparison table of computational results.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser import load_ptn
from src.pool_generator import generate_line_pool
from src.validator import evaluate_line_plan
from src.models.cost_mip import solve_cost_mip
from src.utils import IncompletePoolError
from src.reporting import build_result_record, write_result_json

DATASETS = [
    ("toy", 2, 6, 2),
    ("mandl", 2, 6, 2),
    # min_edges=1 is required for sioux_falls: edge 1 (stops 1-2) demands 16
    # vehicles, while its two neighbor edges cap at 5 and 5 (sum 10). Any line
    # with >= 2 edges covering edge 1 also consumes one unit of neighbor
    # capacity, so the corridor is infeasible without single-edge lines.
    ("sioux_falls", 1, 8, 2),
    ("grid", 2, 8, 2),
    ("athens", 2, 10, 2),
]

def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    base_dir = os.path.join(repo_root, "data")
    results_dir = os.path.join(repo_root, "results")
    global_cfg = os.path.join(base_dir, "Global-Config.cnf")

    results = []
    records = []

    print("=" * 122)
    print(f"{'Dataset':<12} | {'|V|':<4} | {'|E|':<4} | {'Pool':<6} | {'Status':<9} | {'Cost':<10} | {'Gap':<8} | {'Lines':<6} | {'Direct %':<9} | {'Time (s)':<8}")
    print("=" * 122)

    for ds_name, min_e, max_e, k_p in DATASETS:
        ds_dir = os.path.join(base_dir, ds_name)
        if not os.path.exists(ds_dir):
            continue

        ptn = load_ptn(ds_dir, global_cfg)

        pool_size = 0
        cost = float("inf")
        solve_time = 0.0
        gap = float("nan")
        status = "error"
        feasible = False
        active_lines = 0
        direct_pct = 0.0

        try:
            # If PTN already has a pre-computed pool with lines, use it; otherwise generate
            if len(ptn.pool) > 0:
                pool = ptn.pool
            else:
                pool = generate_line_pool(ptn, min_edges=min_e, max_edges=max_e, k_paths_per_pair=k_p)
            pool_size = len(pool)

            freqs, cost, solve_time, status, gap = solve_cost_mip(ptn, pool, integer=True, time_limit=30.0)
            report = evaluate_line_plan(ptn, pool, freqs)
            feasible = report.is_feasible
            active_lines = report.num_active_lines
            direct_pct = report.direct_traveler_percentage
            records.append(build_result_record(ptn, pool, freqs, cost, solve_time, status, gap, report))
        except IncompletePoolError as exc:
            print(f"[warn] {ds_name}: {exc}")

        results.append({
            "name": ds_name,
            "stops": ptn.num_stops,
            "edges": ptn.num_edges,
            "pool": pool_size,
            "status": "FEAS" if feasible else "INFEAS",
            "cost": cost,
            "gap": gap,
            "active_lines": active_lines,
            "direct_pct": direct_pct,
            "time": solve_time
        })

        cost_display = f"{cost:.2f}" if cost < float('inf') else "inf"
        gap_display = f"{gap:.4f}" if gap == gap else "n/a"
        print(f"{ds_name:<12} | {ptn.num_stops:<4} | {ptn.num_edges:<4} | {pool_size:<6} | {status:<9} | {cost_display:<10} | {gap_display:<8} | {active_lines:<6} | {direct_pct:<8.2f}% | {solve_time:<8.4f}")

    print("=" * 122)

    # Print LaTeX table snippet
    print("\n% LaTeX Table snippet for report:")
    print(r"\begin{table}[htbp]")
    print(r"  \centering")
    print(r"  \caption{Baseline Cost-Minimizing Line Planning Performance across LinTim Benchmarks}")
    print(r"  \label{tab:baseline_results}")
    print(r"  \begin{tabular}{lrrrrrrrrr}")
    print(r"    \toprule")
    print(r"    Dataset & $|V|$ & $|E|$ & $|\mathcal{L}|$ & Status & Cost & MIP Gap & Active Lines & Direct (\%) & CPU (s) \\")
    print(r"    \midrule")
    for r in results:
        cost_str = f"{r['cost']:.2f}" if r['cost'] < float('inf') else r"\infty"
        gap_str = f"{r['gap']:.4f}" if r['gap'] == r['gap'] else r"\text{n/a}"
        print(f"    {r['name']} & {r['stops']} & {r['edges']} & {r['pool']} & {r['status']} & {cost_str} & {gap_str} & {r['active_lines']} & {r['direct_pct']:.1f}\\% & {r['time']:.4f} \\\\")
    print(r"    \bottomrule")
    print(r"  \end{tabular}")
    print(r"\end{table}")

    if records:
        path = write_result_json(os.path.join(results_dir, "benchmarks.json"), {"datasets": records})
        print(f"\nBenchmark records written to: {path}")

if __name__ == "__main__":
    main()
