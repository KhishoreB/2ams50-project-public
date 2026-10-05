#!/usr/bin/env python3
"""
Runs the baseline Cost-Minimizing Line Planning MIP on LinTim datasets.
Tests both the pre-existing pool (toy) and the dynamically generated pool (mandl),
and writes machine-readable handoff artifacts for Student 3's column generation.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser import load_ptn
from src.pool_generator import generate_line_pool
from src.validator import evaluate_line_plan
from src.models.cost_mip import solve_cost_mip
from src.reporting import build_result_record, write_result_json


def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    base_dir = os.path.join(repo_root, "data")
    results_dir = os.path.join(repo_root, "results")
    global_cfg = os.path.join(base_dir, "Global-Config.cnf")

    def solve_and_report(label, ptn, pool, out_name):
        print(f"\n{'=' * 60}")
        print(f"{label}")
        print("=" * 60)
        print(f"Loaded {ptn.name}: {ptn.num_stops} stops, {ptn.num_edges} edges, {len(pool)} lines.")
        freqs, obj, elapsed, status, gap = solve_cost_mip(ptn, pool, integer=True)
        print(f"Solver Status: {status} in {elapsed:.4f}s. Objective Cost: {obj:.2f}, MIP gap: {gap:.2%}")
        print(f"Selected Line Frequencies: {freqs}")
        report = evaluate_line_plan(ptn, pool, freqs)
        print(report.summary())
        record = build_result_record(ptn, pool, freqs, obj, elapsed, status, gap, report)
        print(f"Handoff artifact: {write_result_json(os.path.join(results_dir, out_name), record)}")
        return record

    # 1. Test on TOY with LinTim's given pool
    toy_ptn = load_ptn(os.path.join(base_dir, "toy"), global_cfg)
    solve_and_report(
        "TEST 1: Toy Network with Given LinTim Line Pool",
        toy_ptn, toy_ptn.pool, "baseline_toy.json",
    )

    # 2. Test on MANDL with Generated Pool
    mandl_ptn = load_ptn(os.path.join(base_dir, "mandl"), global_cfg)
    mandl_pool = generate_line_pool(mandl_ptn, min_edges=2, max_edges=6, k_paths_per_pair=2)
    solve_and_report(
        "TEST 2: Mandl Benchmark Network with Generated Pool",
        mandl_ptn, mandl_pool, "baseline_mandl.json",
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
