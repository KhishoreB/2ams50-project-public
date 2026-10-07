"""Run the supplied column generation with an external wall-clock limit.

The uploaded pricing enumerates all simple paths and has no internal timeout.
This wrapper leaves the teammate's implementation unchanged. A completed run
produces continuous LP frequencies, not an integer-feasible solution certificate.
"""

import argparse
from dataclasses import asdict
import json
import math
import multiprocessing as mp
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def worker(data_root, dataset, output, max_iterations, solve_limit, allow_legacy):
    from src.parser import load_ptn
    from src.pool_generator import generate_line_pool
    from src.models.column_generation import column_generation
    from src.heuristics.input_audit import audit_lintim_frequency_inputs
    started = perf_counter()
    try:
        basis = Path(data_root) / dataset / "basis"
        if not (basis / "Edge.giv").is_file():
            raise FileNotFoundError(f"Missing dataset: {basis}")
        ptn = load_ptn(str(basis.parent), str(Path(data_root) / "Global-Config.cnf"))
        audit = audit_lintim_frequency_inputs(ptn, allow_legacy)
        min_edges, max_edges = (1, 8) if dataset == "sioux_falls" else (2, 6)
        pool = ptn.pool or generate_line_pool(ptn, min_edges=min_edges, max_edges=max_edges, k_paths_per_pair=2)
        result = column_generation(ptn, pool, max_iterations=max_iterations, time_limit=solve_limit)
        result["pool"] = [asdict(line) for line in result["pool"].values()]
        if not math.isfinite(result["objective"]):
            result["objective"] = None
        result.update(dataset=dataset, runtime_seconds=perf_counter()-started,
                      input_audit=audit,
                      interpretation="Continuous cost LP, not an integer solution.")
    except Exception as exc:
        result = {"dataset": dataset, "status": "error", "error": str(exc),
                  "runtime_seconds": perf_counter()-started}
    Path(output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-root", type=Path, default=ROOT / "data")
    ap.add_argument("--dataset", default="sioux_falls")
    ap.add_argument("--wall-seconds", type=float, default=120)
    ap.add_argument("--solve-limit", type=float, default=30)
    ap.add_argument("--max-iterations", type=int, default=20)
    ap.add_argument("--allow-legacy-frequency-bounds", action="store_true")
    ap.add_argument("--output", type=Path, default=ROOT / "results" / "heuristics" / "column_generation_check.json")
    args = ap.parse_args()
    if not math.isfinite(args.wall_seconds) or args.wall_seconds <= 0 or args.max_iterations < 1:
        ap.error("Wall time must be finite and positive; iterations must be positive.")
    if not math.isfinite(args.solve_limit) or args.solve_limit <= 0:
        ap.error("Solve time limit must be finite and positive.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # A distinct scratch result avoids mistaking a previous run for completion.
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        scratch = Path(directory) / "result.json"
        process = mp.get_context("spawn").Process(target=worker, args=(
            str(args.data_root), args.dataset, str(scratch), args.max_iterations, args.solve_limit,
            args.allow_legacy_frequency_bounds))
        process.start()
        process.join(args.wall_seconds)
        if process.is_alive():
            process.terminate()
            process.join()
            record = {"dataset": args.dataset, "status": "wall_time_limit",
                      "legacy_diagnostic": args.allow_legacy_frequency_bounds,
                      "wall_limit_seconds": args.wall_seconds,
                      "interpretation": "Run stopped externally; no optimality claim or solution recorded."}
        elif scratch.is_file():
            record = json.loads(scratch.read_text())
        else:
            record = {"dataset": args.dataset, "status": "process_error", "exitcode": process.exitcode}
        args.output.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
    print(f"{args.dataset}: {record['status']} -> {args.output}")
    return int(record["status"] in ("error", "process_error", "wall_time_limit"))


if __name__ == "__main__":
    raise SystemExit(main())
