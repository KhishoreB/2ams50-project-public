"""Greedy construction for the uploaded team's frequency/coverage model.

Service means OD demand with an active line containing both endpoints, exactly
as in src.validator. It is NOT a capacity-constrained passenger assignment.
The heuristic may fail even when a feasible integer line concept exists.
"""

from dataclasses import dataclass, field
from math import isfinite
from time import perf_counter
from typing import Dict, Optional

from ..parser import Line, PTNInstance
from ..utils import effective_frequency_bounds, resolve_line_nodes
from ..validator import evaluate_line_plan

TOL = 1e-7


@dataclass
class HeuristicResult:
    method: str
    status: str
    frequencies: Dict[int, int]
    cost: float
    direct_demand_coverage: float
    coverage_percentage: float
    frequency_feasible: bool
    budget_feasible: bool
    runtime_seconds: float
    message: str = ""
    details: dict = field(default_factory=dict)

    @property
    def feasible(self):
        return self.frequency_feasible and self.budget_feasible


class PoolProblem:
    """Validated, deterministic views of the team's dataclasses.

    Copies lines rather than mutating a caller's pool. Bounds deliberately come
    from effective_frequency_bounds so exact and heuristic runs are comparable.
    """

    def __init__(self, ptn: PTNInstance, pool: Dict[int, Line]):
        if not ptn.stops or not ptn.edges:
            raise ValueError("Empty network: check the dataset path and basis files.")
        undirected = str(ptn.config.get("ptn_is_undirected",
                         ptn.config.get("gen_ptn_is_undirected", "true"))).lower()
        if undirected in ("false", "0"):
            raise ValueError("The uploaded pipeline and this implementation require an undirected PTN.")
        self.ptn = ptn
        self.demand = dict(sorted(ptn.od_matrix.items()))
        for (u, v), demand in self.demand.items():
            if u not in ptn.stops or v not in ptn.stops or not isfinite(demand) or demand < 0:
                raise ValueError(f"Invalid OD entry {(u, v)}: {demand}")
        self.pool = {}
        self.cover = {}
        for key, line in sorted(pool.items()):
            if key != line.id or not line.edges or any(e not in ptn.edges for e in line.edges):
                raise ValueError(f"Line {key}: invalid ID or edge sequence.")
            nodes = resolve_line_nodes(line.edges, ptn)
            if len(nodes) != len(line.edges) + 1 or len(set(nodes)) != len(nodes):
                raise ValueError(f"Line {key}: expected a contiguous simple path.")
            if any(v not in ptn.stops for v in nodes):
                raise ValueError(f"Line {key}: unknown stop.")
            if not isfinite(line.cost) or line.cost < 0:
                raise ValueError(f"Line {key}: cost must be finite and nonnegative.")
            self.pool[key] = Line(key, list(line.edges), line.length, line.cost, nodes)
            node_set = set(nodes)
            self.cover[key] = {od for od, d in self.demand.items()
                               if d > 0 and od[0] in node_set and od[1] in node_set}
        self.bounds = {}
        for eid, edge in sorted(ptn.edges.items()):
            lo, hi = effective_frequency_bounds(edge, ptn.loads.get(eid))
            if not isfinite(lo) or not isfinite(hi) or lo < 0 or hi < 0 or int(lo) != lo or int(hi) != hi:
                raise ValueError(f"Edge {eid}: invalid effective frequency bounds {(lo, hi)}.")
            if hi > 0 and hi < lo:
                raise ValueError(f"Edge {eid}: lower frequency exceeds upper frequency.")
            self.bounds[eid] = (int(lo), int(hi))

    def check_seed(self, frequencies):
        unknown = set(frequencies) - set(self.pool)
        if unknown:
            raise ValueError(f"Unknown line IDs: {sorted(unknown)}")
        result = {}
        for lid, value in frequencies.items():
            if not isfinite(value) or value < 0 or int(value) != value:
                raise ValueError(f"Line {lid}: frequency must be a nonnegative integer.")
            if value:
                result[lid] = int(value)
        return result

    def edge_frequencies(self, frequencies):
        result = {eid: 0 for eid in self.bounds}
        for lid, value in frequencies.items():
            for eid in self.pool[lid].edges:
                result[eid] += value
        return result

    def cost(self, frequencies):
        return sum(self.pool[lid].cost * value for lid, value in frequencies.items())

    def covered(self, frequencies):
        result = set()
        for lid, value in frequencies.items():
            if value > 0:
                result.update(self.cover[lid])
        return result


def _ratio(gain, cost):
    return float("inf") if cost == 0 and gain > 0 else gain / cost if cost else 0.0


def _fits(problem, lid, edge_freq, cost, budget):
    line = problem.pool[lid]
    return (cost + line.cost <= budget + TOL and
            all(problem.bounds[e][1] == 0 or edge_freq[e] + 1 <= problem.bounds[e][1]
                for e in line.edges))


def _add(problem, frequencies, edge_freq, lid):
    frequencies[lid] = frequencies.get(lid, 0) + 1
    for eid in problem.pool[lid].edges:
        edge_freq[eid] += 1


def make_result(problem, frequencies, budget, method, status, started,
                message="", details=None):
    report = evaluate_line_plan(problem.ptn, problem.pool, frequencies)
    return HeuristicResult(
        method=method, status=status, frequencies=dict(sorted(frequencies.items())),
        cost=report.total_cost, direct_demand_coverage=report.direct_travelers,
        coverage_percentage=report.direct_traveler_percentage,
        frequency_feasible=report.is_feasible,
        budget_feasible=report.total_cost <= budget + TOL,
        runtime_seconds=perf_counter() - started, message=message,
        details=details or {})


def greedy_select(ptn: PTNInstance, pool: Dict[int, Line], budget: float,
                  initial_frequencies: Optional[Dict[int, int]] = None,
                  improve_service: bool = True) -> HeuristicResult:
    """Repair minimum frequencies, then buy marginal direct coverage.

    Repair ranks one-frequency increments by deficient-edge gain / cost;
    ties prefer uncovered OD demand, lower cost, then lower line ID.
    Service ranks inactive lines by additional covered OD demand / cost.
    Every increment respects the budget and effective upper bounds.
    No approximation guarantee is claimed with mandatory service/upper bounds.
    """
    started = perf_counter()
    if not isfinite(budget) or budget < 0:
        raise ValueError("Budget must be finite and nonnegative.")
    problem = PoolProblem(ptn, pool)
    frequencies = problem.check_seed(initial_frequencies or {})
    edge_freq = problem.edge_frequencies(frequencies)
    cost = problem.cost(frequencies)
    if cost > budget + TOL or any(hi > 0 and edge_freq[e] > hi
                                  for e, (_, hi) in problem.bounds.items()):
        raise ValueError("Initial frequencies violate budget or effective upper bounds.")
    uncovered = [e for e, (lo, _) in problem.bounds.items()
                 if lo > 0 and not any(e in line.edges for line in problem.pool.values())]
    if uncovered:
        return make_result(problem, frequencies, budget, "greedy", "pool_infeasible", started,
                           f"No line covers required edges {uncovered}.")
    covered = problem.covered(frequencies)
    while any(edge_freq[e] < lo for e, (lo, _) in problem.bounds.items()):
        candidates = []
        for lid, line in problem.pool.items():
            gain = sum(edge_freq[e] < problem.bounds[e][0] for e in line.edges)
            if gain and _fits(problem, lid, edge_freq, cost, budget):
                demand_gain = sum(problem.demand[od] for od in problem.cover[lid] - covered)
                candidates.append((_ratio(gain, line.cost), demand_gain, -line.cost, -lid, lid))
        if not candidates:
            return make_result(problem, frequencies, budget, "greedy", "construction_failed", started,
                               "No admissible increment repairs a deficit; this is not an infeasibility proof.")
        lid = max(candidates)[-1]
        _add(problem, frequencies, edge_freq, lid)
        cost += problem.pool[lid].cost
        covered.update(problem.cover[lid])

    # Delete redundant frequency units while preserving all current coverage.
    # At least one copy of each active line remains; service is monotone.
    for lid in sorted(frequencies, key=lambda i: (-problem.pool[i].cost, i)):
        while frequencies[lid] > 1 and all(edge_freq[e] - 1 >= problem.bounds[e][0]
                                          for e in problem.pool[lid].edges):
            frequencies[lid] -= 1
            cost -= problem.pool[lid].cost
            for eid in problem.pool[lid].edges:
                edge_freq[eid] -= 1

    if improve_service:
        while True:
            candidates = []
            for lid, line in problem.pool.items():
                if frequencies.get(lid, 0) or not _fits(problem, lid, edge_freq, cost, budget):
                    continue
                gain = sum(problem.demand[od] for od in problem.cover[lid] - covered)
                if gain > 0:
                    candidates.append((_ratio(gain, line.cost), gain, -line.cost, -lid, lid))
            if not candidates:
                break
            lid = max(candidates)[-1]
            _add(problem, frequencies, edge_freq, lid)
            cost += problem.pool[lid].cost
            covered.update(problem.cover[lid])

    return make_result(problem, frequencies, budget, "greedy", "feasible", started,
                       "Feasible under the shared edge-frequency model; service is a coverage proxy.")
