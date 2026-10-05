"""
Graph and Metric Utilities for Public Transport Line Planning.
"""

from typing import Dict, List, Tuple, Set, Optional
import math
from .parser import PTNInstance, Line, Edge


class IncompletePoolError(Exception):
    """
    Raised when the candidate pool cannot serve every edge that has a positive
    minimum frequency requirement: such an edge has no covering line, so no
    feasible line plan can be built from the pool.
    """

    def __init__(self, uncovered: List[Tuple[int, int]]):
        self.uncovered = list(uncovered)
        detail = ", ".join(f"edge {e} (min_f={m})" for e, m in self.uncovered)
        super().__init__(
            f"pool leaves {len(self.uncovered)} required edge(s) uncovered: {detail}"
        )


def uncovered_required_edges(
    ptn: PTNInstance, pool: Dict[int, Line]
) -> List[Tuple[int, int]]:
    """
    Returns [(edge_id, min_f)] for every edge whose minimum frequency is positive
    but which is not contained in any line of the pool. Empty if the pool can
    serve all required edges.
    """
    uncovered: List[Tuple[int, int]] = []
    for e_id, edge in ptn.edges.items():
        min_f, _ = effective_frequency_bounds(edge, ptn.loads.get(e_id))
        if min_f > 0 and not any(e_id in l.edges for l in pool.values()):
            uncovered.append((e_id, min_f))
    return uncovered


def effective_frequency_bounds(edge: Edge, load: Optional[Tuple[float, int, int]] = None) -> Tuple[int, int]:
    """
    Single source of truth for the frequency interval an edge must respect.

    Policy (matches how LinTim generates the files):
    - Load.giv, when present, is the current demand computation (with the dataset's
      vehicle capacity) and supersedes the demand-derived lower bound in Edge.giv.
    - Edge.giv upper is a track-capacity ceiling and is enforced only when it
      exceeds the lower bound. When upper == lower (all Mandl edges), the upper
      column repeats the demand requirement instead of giving independent
      capacity information, so no ceiling is enforced. This matches the standard
      cost-oriented line planning model (Schöbel 2012), which uses lower bounds
      only.

    load is (passenger_load, demand_min, demand_max) or None. A max of 0 means
    "no ceiling".
    """
    if load:
        demand_min, demand_max = load[1], load[2]
    else:
        demand_min, demand_max = 0, 0

    min_f = demand_min if demand_min > 0 else edge.lower_bound

    if demand_max > 0:
        max_f = demand_max
    elif edge.upper_bound > edge.lower_bound:
        max_f = edge.upper_bound
    else:
        max_f = 0  # upper == lower: demand requirement, no capacity information

    return min_f, max_f


def demand_min_frequency(passenger_load: float, capacity: int) -> int:
    """
    Vehicles needed to carry `passenger_load` passengers with `capacity`
    passengers per vehicle: ceil(load / capacity), or 0 for a zero/negative load.
    This is the demand-derived lower bound LinTim records in Load.giv.
    """
    if capacity <= 0:
        raise ValueError(f"vehicle capacity must be positive, got {capacity}")
    if passenger_load <= 0:
        return 0
    return math.ceil(passenger_load / capacity)


def capacity_load_mismatches(ptn: PTNInstance) -> List[Tuple[int, float, int, int]]:
    """
    Cross-check Load.giv against the dataset's vehicle capacity. For every edge
    the recorded demand minimum should equal ceil(load / capacity). Returns
    (edge_id, load, recorded_min, implied_min) for discrepancies; empty if all
    rows agree (or the dataset has no Load.giv).
    """
    if not ptn.loads:
        return []
    capacity = ptn.vehicle_capacity
    mismatches: List[Tuple[int, float, int, int]] = []
    for e_id, (load, recorded_min, _max_f) in ptn.loads.items():
        implied_min = demand_min_frequency(load, capacity)
        if implied_min != recorded_min:
            mismatches.append((e_id, load, recorded_min, implied_min))
    return mismatches


DEFAULT_LINE_COST_FIXED = 50.0
DEFAULT_LINE_COST_PER_LENGTH = 0.05
DEFAULT_LINE_COST_PER_EDGE = 0.05


def _config_float(config: Dict[str, str], key: str, default: float) -> float:
    """Reads a float setting, tolerating quotes, whitespace and inline comments."""
    raw = config.get(key)
    if raw is None:
        return default
    raw = raw.split("#", 1)[0].strip().strip('"')
    if not raw:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def line_cost_params(config: Dict[str, str]) -> Tuple[float, float, float]:
    """
    Returns (fixed, per_length, per_edge) from the instance configuration,
    falling back to the LinTim Global-Config defaults. Every pool (given or
    generated) must use these so costs are comparable across datasets.
    """
    return (
        _config_float(config, "lpool_costs_fixed", DEFAULT_LINE_COST_FIXED),
        _config_float(config, "lpool_costs_length", DEFAULT_LINE_COST_PER_LENGTH),
        _config_float(config, "lpool_costs_edges", DEFAULT_LINE_COST_PER_EDGE),
    )


def compute_line_cost(
    length: float,
    num_edges: int,
    fixed_cost: float = DEFAULT_LINE_COST_FIXED,
    cost_per_length: float = DEFAULT_LINE_COST_PER_LENGTH,
    cost_per_edge: float = DEFAULT_LINE_COST_PER_EDGE
) -> float:
    """
    Computes line operating cost using LinTim standard formula:
    Cost(l) = Fixed + cost_length * length + cost_edge * num_edges
    """
    return fixed_cost + (cost_per_length * length) + (cost_per_edge * num_edges)


def apply_line_costs(ptn: PTNInstance) -> None:
    """
    Rewrites length and cost of every pooled line from the instance geometry and
    its own Config.cnf cost parameters. Given pools (toy, athens) ship a
    Pool-Cost.giv produced with a different convention than the generated pools;
    recomputing both with one formula is what makes the benchmark table
    comparable. Length is always the sum of the traversed edge lengths.
    """
    fixed, per_length, per_edge = line_cost_params(ptn.config)
    for line in ptn.pool.values():
        known = [ptn.edges[e].length for e in line.edges if e in ptn.edges]
        if known:
            line.length = sum(known)
        line.cost = compute_line_cost(line.length, len(line.edges), fixed, per_length, per_edge)


def build_network_graph(ptn: PTNInstance) -> Dict[int, List[Tuple[int, int, float]]]:
    """
    Builds an undirected adjacency list:
    node -> list of (neighbor_node, edge_id, length)
    """
    adj: Dict[int, List[Tuple[int, int, float]]] = {s: [] for s in ptn.stops}
    for e_id, edge in ptn.edges.items():
        adj[edge.u].append((edge.v, e_id, edge.length))
        adj[edge.v].append((edge.u, e_id, edge.length))
    return adj


def get_edge_endpoints(ptn: PTNInstance) -> Dict[int, Tuple[int, int]]:
    """Maps edge_id -> (u, v)."""
    return {e_id: (edge.u, edge.v) for e_id, edge in ptn.edges.items()}


def resolve_line_nodes(line_edges: List[int], ptn: PTNInstance) -> List[int]:
    """
    Given a list of ordered edge IDs, resolves the sequence of traversed node IDs.
    Returns empty list if edges are not contiguous.
    """
    if not line_edges:
        return []
    
    e0 = ptn.edges[line_edges[0]]
    if len(line_edges) == 1:
        return [e0.u, e0.v]
    
    e1 = ptn.edges[line_edges[1]]
    # Determine direction of e0
    if e0.v in (e1.u, e1.v):
        curr_node = e0.v
        nodes = [e0.u, e0.v]
    elif e0.u in (e1.u, e1.v):
        curr_node = e0.u
        nodes = [e0.v, e0.u]
    else:
        return []  # Not contiguous

    for e_id in line_edges[1:]:
        edge = ptn.edges[e_id]
        if edge.u == curr_node:
            curr_node = edge.v
            nodes.append(curr_node)
        elif edge.v == curr_node:
            curr_node = edge.u
            nodes.append(curr_node)
        else:
            return []  # Not contiguous

    return nodes
