#!/usr/bin/env python3
"""
Verifies that all downloaded LinTim datasets parse correctly and prints summary statistics.
"""

import os
import sys

# Ensure src is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser import load_ptn
from src.utils import capacity_load_mismatches

DATASETS = ["toy", "mandl", "grid", "sioux_falls", "athens"]

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    global_cfg = os.path.join(base_dir, "Global-Config.cnf")
    
    print("=" * 108)
    print(f"{'Dataset':<15} | {'Stops':<6} | {'Edges':<6} | {'OD Pairs':<9} | {'Total Demand':<12} | {'Pool Lines':<10} | {'Capacity':<8} | {'Load/Config':<11}")
    print("=" * 108)

    for ds_name in DATASETS:
        ds_dir = os.path.join(base_dir, ds_name)
        if not os.path.exists(ds_dir):
            print(f"Skipping {ds_name} (directory not found)")
            continue
        try:
            ptn = load_ptn(ds_dir, global_cfg)
            pool_count = len(ptn.pool)
            capacity = ptn.vehicle_capacity
            mismatches = capacity_load_mismatches(ptn)
            if not ptn.loads:
                check = "n/a"
            else:
                check = "ok" if not mismatches else f"MISMATCH x{len(mismatches)}"
            print(f"{ptn.name:<15} | {ptn.num_stops:<6} | {ptn.num_edges:<6} | {len(ptn.od_matrix):<9} | {ptn.total_demand:<12.1f} | {pool_count:<10} | {capacity:<8} | {check:<11}")
            for e_id, load, recorded, implied in mismatches[:5]:
                print(f"  [!] edge {e_id}: load={load:g} -> ceil(load/cap)={implied} but Load.giv says {recorded}")
        except Exception as e:
            print(f"{ds_name:<15} | ERROR: {e}")

    print("=" * 108)

if __name__ == "__main__":
    main()
