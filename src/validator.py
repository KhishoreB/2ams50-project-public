"""
Solution Validator and Evaluation Engine for Line Planning.
Evaluates line plans on edge coverage, capacity constraints, operating cost,
and passenger direct-connectivity service levels.
"""

from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
from .parser import PTNInstance, Line
from .utils import effective_frequency_bounds


@dataclass
class ValidationReport:
    is_feasible: bool
    total_cost: float
    num_active_lines: int
    total_line_frequencies: int
    min_frequency_violations: List[Tuple[int, int, int]]  # (edge_id, actual_f, min_f)
    max_frequency_violations: List[Tuple[int, int, int]]  # (edge_id, actual_f, max_f)
    direct_travelers: float
    total_demand: float
    direct_traveler_percentage: float

    def summary(self) -> str:
        status = "FEASIBLE" if self.is_feasible else "INFEASIBLE"
        lines = [
            f"=== Line Plan Evaluation ({status}) ===",
            f"  Total Cost:                 {self.total_cost:.2f}",
            f"  Active Lines:               {self.num_active_lines}",
            f"  Total Line Frequencies:     {self.total_line_frequencies}",
            f"  Direct Travelers:           {self.direct_travelers:.1f} / {self.total_demand:.1f} ({self.direct_traveler_percentage:.2f}%)",
        ]
        if self.min_frequency_violations:
            lines.append(f"  [!] Under-served Edges ({len(self.min_frequency_violations)}): {self.min_frequency_violations[:5]}...")
        if self.max_frequency_violations:
            lines.append(f"  [!] Over-capacity Edges ({len(self.max_frequency_violations)}): {self.max_frequency_violations[:5]}...")
        return "\n".join(lines)


def evaluate_line_plan(
    ptn: PTNInstance,
    pool: Dict[int, Line],
    frequencies: Dict[int, int],
    enforce_upper_bounds: bool = True
) -> ValidationReport:
    """
    Evaluates a solution given as line_id -> integer frequency.
    """
    unknown = sorted(set(frequencies) - set(pool))
    if unknown:
        shown = unknown[:10]
        suffix = "..." if len(unknown) > len(shown) else ""
        raise ValueError(
            f"frequencies reference {len(unknown)} line id(s) not in the supplied "
            f"pool: {shown}{suffix}"
        )

    active_lines = {l_id: f for l_id, f in frequencies.items() if f > 0}
    total_cost = sum(pool[l_id].cost * f for l_id, f in active_lines.items())
    total_freq = sum(active_lines.values())

    # 1. Edge frequency coverage
    edge_freq: Dict[int, int] = {e_id: 0 for e_id in ptn.edges}
    for l_id, f in active_lines.items():
        for e_id in pool[l_id].edges:
            if e_id in edge_freq:
                edge_freq[e_id] += f

    min_violations = []
    max_violations = []
    for e_id, edge in ptn.edges.items():
        act_f = edge_freq[e_id]
        # Same source of truth as the MIP: infra bounds (Edge.giv) + demand bounds (Load.giv)
        min_f, max_f = effective_frequency_bounds(edge, ptn.loads.get(e_id))
        if act_f < min_f:
            min_violations.append((e_id, act_f, min_f))
        if enforce_upper_bounds and max_f > 0 and act_f > max_f:
            max_violations.append((e_id, act_f, max_f))

    is_feasible = (len(min_violations) == 0 and len(max_violations) == 0)

    # 2. Direct travelers calculation
    # A pair (u, v) is direct if there exists an active line whose node sequence contains both u and v
    active_line_nodes = [set(pool[l_id].nodes) for l_id in active_lines]
    
    direct_demand = 0.0
    total_demand = ptn.total_demand

    for (orig, dest), demand in ptn.od_matrix.items():
        if demand <= 0:
            continue
        # Check if orig and dest are in any active line's node set
        if any(orig in n_set and dest in n_set for n_set in active_line_nodes):
            direct_demand += demand

    pct = (direct_demand / total_demand * 100.0) if total_demand > 0 else 0.0

    return ValidationReport(
        is_feasible=is_feasible,
        total_cost=total_cost,
        num_active_lines=len(active_lines),
        total_line_frequencies=total_freq,
        min_frequency_violations=min_violations,
        max_frequency_violations=max_violations,
        direct_travelers=direct_demand,
        total_demand=total_demand,
        direct_traveler_percentage=pct
    )
