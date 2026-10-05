"""
Column generation test for every dataset (replaces the separate toy and
Mandl test scripts).

For each dataset it:

1. seeds the RMP with the active lines of the baseline MIP,
2. runs column generation and prints the result,
3. checks the result:
   - CG stopped because pricing found no negative reduced cost,
   - the RMP objective never increased,
   - CG's LP value equals the LP over EVERY simple path (the full line set),
     an independent check, skipped when there are too many paths,
4. builds an integer line plan from the generated lines (price-and-branch),
   validates it, and compares it with the baseline MIP,
5. saves results/cg_<dataset>.json (same format as the baseline records,
   plus a "column_generation" block), then rewrites
   results/cg_results_table.tex with every dataset saved so far.

Lives in scripts/ and runs directly (or with your editor's Run button):
    python scripts/test_column_generation.py                  # all five datasets
    python scripts/test_column_generation.py mandl            # one dataset
    python scripts/test_column_generation.py sioux_falls grid athens
"""

import json
import os
import sys
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

from src.parser import load_ptn, Line
from src.utils import build_network_graph
from src.models.rmp import solve_cost_rmp
from src.models.cost_mip import solve_cost_mip
from src.models.column_generation import (
    column_generation,
    create_line_from_path,
)
from src.validator import evaluate_line_plan
from src.reporting import build_result_record, write_result_json


TOL = 1e-6
MAX_FULL_POOL_PATHS = 200_000


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def load_seed_pool(name):
    """
    Active lines of the baseline MIP: results/baseline_<name>.json when it
    exists, otherwise the dataset's record in results/benchmarks.json.
    """

    path = os.path.join(REPO_ROOT, "results", f"baseline_{name}.json")

    if os.path.exists(path):
        with open(path, "r") as f:
            record = json.load(f)
    else:
        with open(os.path.join(REPO_ROOT, "results", "benchmarks.json"), "r") as f:
            records = json.load(f)["datasets"]
        record = next(r for r in records if r["dataset"] == name)

    pool = {
        item["id"]: Line(
            id=item["id"],
            edges=item["edges"],
            length=item["length"],
            cost=item["cost"],
            nodes=item["nodes"],
        )
        for item in record["lines"]
    }

    return pool, record["solver"]["objective"]


class TooManyPaths(Exception):
    pass


def all_simple_paths(ptn, limit=MAX_FULL_POOL_PATHS):
    """
    Every simple path with at least one edge, each undirected path once.
    This is the full line set that column generation searches implicitly.
    """

    graph = build_network_graph(ptn)
    seen = {}

    def dfs(node, visited, path):
        for next_node, edge_id, _length in graph[node]:
            if next_node in visited:
                continue
            visited.add(next_node)
            path.append(edge_id)
            seen.setdefault(frozenset(path), list(path))
            if len(seen) > limit:
                raise TooManyPaths
            dfs(next_node, visited, path)
            path.pop()
            visited.remove(next_node)

    for start in graph:
        dfs(start, {start}, [])

    return list(seen.values())


def print_cg_result(result):
    print("Status:", result["status"])
    print("Iterations:", result["iterations"])
    print("Objective:", result["objective"])

    print("\nFinal frequencies:")
    for line_id, frequency in result["frequencies"].items():
        if frequency > 1e-8:
            print(f"  Line {line_id}: {frequency}")

    print("\nIteration history:")
    for item in result["history"]:
        print(
            f"Iteration {item['iteration']}: "
            f"RMP={item['rmp_objective']:.4f}, "
            f"candidate={item['candidate_edges']}, "
            f"reduced_cost={item['candidate_reduced_cost']:.6f}"
        )

    print("\nFinal pool:")
    for line_id, line in result["pool"].items():
        print(
            f"  Line {line_id}: "
            f"edges={line.edges}, "
            f"nodes={line.nodes}, "
            f"length={line.length}, "
            f"cost={line.cost}"
        )


# ---------------------------------------------------------
# Test one dataset
# ---------------------------------------------------------

def run(name):

    print("\n" + "=" * 60)
    print(f"  {name.upper()}")
    print("=" * 60)

    ptn = load_ptn(
        os.path.join(REPO_ROOT, "data", name),
        os.path.join(REPO_ROOT, "data", "Global-Config.cnf"),
    )
    seed_pool, baseline_objective = load_seed_pool(name)

    print("Initial pool IDs:", list(seed_pool.keys()))

    # 1. Column generation
    start = time.perf_counter()
    result = column_generation(ptn, seed_pool)
    cg_seconds = time.perf_counter() - start

    print("\n=== Column Generation Result ===")
    print_cg_result(result)
    print(f"\nCG time: {cg_seconds:.1f} s")

    checks = {}

    # 2. Convergence: pricing found no negative reduced cost
    checks["CG stopped with no negative reduced cost"] = (
        result["status"] == "optimal_no_negative_reduced_cost"
    )

    # 3. Adding columns can only improve the RMP
    objectives = [item["rmp_objective"] for item in result["history"]]
    checks["RMP objective never increases"] = all(
        later <= earlier + TOL
        for earlier, later in zip(objectives, objectives[1:])
    )

    # 4. Independent check: LP over the full line set
    full_lp_record = None
    print("\n=== Full LP Over Every Simple Path ===")
    try:
        paths = all_simple_paths(ptn)
    except TooManyPaths:
        print(f"Skipped: more than {MAX_FULL_POOL_PATHS} simple paths.")
    else:
        full_pool = {
            i: create_line_from_path(ptn, i, p)
            for i, p in enumerate(paths, start=1)
        }
        _, full_lp, _, _, status = solve_cost_rmp(ptn, full_pool)
        difference = result["objective"] - full_lp
        print(f"Simple paths: {len(full_pool)}")
        print(f"Full LP objective: {full_lp:.6f} ({status})")
        print(f"CG LP - full LP: {difference:.2e}")
        checks["CG LP equals full LP over every simple path"] = (
            abs(difference) <= TOL * max(1.0, abs(full_lp))
        )
        full_lp_record = {
            "simple_paths": len(full_pool),
            "objective": full_lp,
            "difference": difference,
        }

    # 5. Integer line plan from the generated lines (price-and-branch)
    print("\n=== Integer Line Plan From CG Lines ===")
    frequencies, ip_objective, ip_seconds, ip_status, ip_gap = solve_cost_mip(
        ptn,
        result["pool"],
    )
    validation = evaluate_line_plan(ptn, result["pool"], frequencies)
    gap_to_lp = ip_objective - result["objective"]

    print(f"Status: {ip_status}")
    print(f"Objective: {ip_objective:.4f}")
    print(f"Gap to CG LP bound: {gap_to_lp:.4f}")
    print(f"Baseline MIP (static pool): {baseline_objective:.4f}")
    print("Lines used:")
    for line_id, frequency in sorted(frequencies.items()):
        print(f"  Line {line_id}: f={frequency}, edges={result['pool'][line_id].edges}")
    print(validation)

    checks["Integer plan is feasible"] = validation.is_feasible
    checks["Integer plan is not below the LP bound"] = (
        ip_objective >= result["objective"] - TOL
    )

    # Summary
    print("\n=== Checks ===")
    for description, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {description}")

    # 6. Save: same record format as the baseline results, plus a CG block
    record = build_result_record(
        ptn,
        result["pool"],
        frequencies,
        ip_objective,
        ip_seconds,
        ip_status,
        ip_gap,
        validation,
        solver="column_generation",
    )
    record["column_generation"] = {
        "status": result["status"],
        "iterations": result["iterations"],
        "lp_objective": result["objective"],
        "time_seconds": cg_seconds,
        "seed_pool_size": len(seed_pool),
        "lines_generated": len(result["pool"]) - len(seed_pool),
        "lp_frequencies": {
            str(line_id): frequency
            for line_id, frequency in result["frequencies"].items()
            if frequency > 1e-8
        },
        "history": result["history"],
        "full_lp_check": full_lp_record,
        "gap_to_lp_bound": gap_to_lp,
        "baseline_mip_objective": baseline_objective,
        "checks": checks,
    }
    saved = write_result_json(
        os.path.join(REPO_ROOT, "results", f"cg_{name}.json"),
        record,
    )
    print(f"\nSaved: {saved}")

    return all(checks.values())


# ---------------------------------------------------------
# Summary table of every saved CG result
# ---------------------------------------------------------

DATASET_ORDER = ["toy", "mandl", "sioux_falls", "grid", "athens"]
PRETTY_NAMES = {
    "toy": "Toy",
    "mandl": "Mandl",
    "sioux_falls": "Sioux Falls",
    "grid": "Grid",
    "athens": "Athens",
}


def saved_rows():
    """One summary row per results/cg_<dataset>.json, in dataset order."""

    rows = []

    for name in DATASET_ORDER:
        path = os.path.join(REPO_ROOT, "results", f"cg_{name}.json")
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        cg = record["column_generation"]
        lp = cg["lp_objective"]
        ip = record["solver"]["objective"]
        baseline = cg["baseline_mip_objective"]
        rows.append(
            {
                "name": name,
                "iterations": cg["iterations"],
                "time": cg["time_seconds"],
                "lp": lp,
                "ip": ip,
                "gap_pct": 100.0 * (ip - lp) / lp,
                "baseline": baseline,
                "saving_pct": 100.0 * (baseline - ip) / baseline,
                "passed": all(cg["checks"].values()),
            }
        )

    return rows


def latex_table(rows):
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{Column generation: LP bound, integer plan from the generated lines, and the static-pool baseline MIP}",
        r"  \label{tab:cg_results}",
        r"  \begin{tabular}{lrrrrrrr}",
        r"    \toprule",
        r"    Dataset & Iter. & CG time (s) & LP bound & Integer plan & Gap (\%) & Baseline MIP & Saving (\%) \\",
        r"    \midrule",
    ]
    for r in rows:
        name = PRETTY_NAMES.get(r["name"], r["name"].replace("_", r"\_"))
        lines.append(
            f"    {name} & {r['iterations']} & {r['time']:.1f} & {r['lp']:.2f} & "
            f"{r['ip']:.2f} & {r['gap_pct']:.2f} & {r['baseline']:.2f} & "
            f"{r['saving_pct']:.1f} \\\\"
        )
    lines += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}"]
    return "\n".join(lines)


if __name__ == "__main__":
    datasets = sys.argv[1:] or DATASET_ORDER
    outcomes = {name: run(name) for name in datasets}

    rows = saved_rows()

    print("\n" + "=" * 100)
    print("All saved column generation results")
    print("=" * 100)
    print(
        f"{'Dataset':<12} | {'Iter.':>5} | {'CG time (s)':>11} | {'LP bound':>10} | "
        f"{'Integer':>10} | {'Gap %':>6} | {'Baseline':>10} | {'Saving %':>8} | Checks"
    )
    print("-" * 100)
    for r in rows:
        print(
            f"{r['name']:<12} | {r['iterations']:>5} | {r['time']:>11.1f} | {r['lp']:>10.2f} | "
            f"{r['ip']:>10.2f} | {r['gap_pct']:>6.2f} | {r['baseline']:>10.2f} | "
            f"{r['saving_pct']:>8.1f} | {'PASS' if r['passed'] else 'FAIL'}"
        )

    table_path = os.path.join(REPO_ROOT, "results", "cg_results_table.tex")
    with open(table_path, "w", encoding="utf-8") as f:
        f.write(latex_table(rows) + "\n")
    print(f"\nLaTeX table saved: {table_path}")

    sys.exit(0 if all(outcomes.values()) else 1)