"""
Serialization helpers for benchmark results and the baseline -> Student 3 handoff.

Writes a self-contained JSON record (pool, frequencies, verified cost, cost
convention, solver statistics) so a downstream method such as column generation
can consume the exact baseline solution without re-running the pipeline.
"""

import json
import os
from typing import Any, Dict

from .parser import PTNInstance, Line
from .utils import line_cost_params
from .validator import ValidationReport


def _line_record(line: Line, frequency: int) -> Dict[str, Any]:
    return {
        "id": line.id,
        "edges": list(line.edges),
        "nodes": list(line.nodes),
        "length": line.length,
        "cost": line.cost,
        "frequency": frequency,
    }


def build_result_record(
    ptn: PTNInstance,
    pool: Dict[int, Line],
    frequencies: Dict[int, int],
    objective: float,
    solve_time: float,
    status: str,
    gap: float,
    report: ValidationReport,
    solver: str = "auto",
) -> Dict[str, Any]:
    """Builds a JSON-serializable record of one solved line-planning instance."""
    fixed, per_length, per_edge = line_cost_params(ptn.config)
    try:
        capacity = ptn.vehicle_capacity
    except (KeyError, ValueError):
        capacity = None

    active = {l_id: f for l_id, f in frequencies.items() if f > 0}
    return {
        "dataset": ptn.name,
        "num_stops": ptn.num_stops,
        "num_edges": ptn.num_edges,
        "vehicle_capacity": capacity,
        "total_demand": ptn.total_demand,
        "pool_size": len(pool),
        "cost_params": {
            "fixed": fixed,
            "per_length": per_length,
            "per_edge": per_edge,
        },
        "solver": {
            "name": solver,
            "status": status,
            "objective": objective,
            "solve_time_seconds": solve_time,
            "mip_gap": gap,
        },
        "lines": [_line_record(pool[l_id], f) for l_id, f in sorted(active.items())],
        "validation": {
            "is_feasible": report.is_feasible,
            "total_cost": report.total_cost,
            "active_lines": report.num_active_lines,
            "total_line_frequencies": report.total_line_frequencies,
            "direct_travelers": report.direct_travelers,
            "total_demand": report.total_demand,
            "direct_traveler_percentage": report.direct_traveler_percentage,
            "min_frequency_violations": report.min_frequency_violations,
            "max_frequency_violations": report.max_frequency_violations,
        },
    }


def write_result_json(path: str, record: Dict[str, Any]) -> str:
    """Writes a result record to `path`, creating parent directories as needed."""
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
    return path
