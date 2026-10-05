"""
Restricted Master Problem (RMP) LP and edge-price extraction for column generation.

Infrastructure for Student 3's Dantzig-Wolfe / column-generation work. It solves
the LP relaxation of the cost MIP over a candidate pool and returns the edge
prices that the pricing subproblem needs.

Why an explicit dual LP: with presolve on, SCIP 10 removes most LP rows and the
solved constraint handles no longer carry duals (getDualsolLinear returns
nothing or a dangling pointer). Following cg_ex_301.py in this workspace, we
solve the dual LP as a model of its own; by strong duality its optimum *is* the
RMP dual solution, so the two objectives must agree.
"""

from typing import Dict, Tuple
from ..parser import PTNInstance, Line
from ..utils import (
    effective_frequency_bounds,
    uncovered_required_edges,
    IncompletePoolError,
)


def reduced_cost(
    line: Line,
    service_duals: Dict[int, float],
    capacity_duals: Dict[int, float],
) -> float:
    """
    Reduced cost of a candidate line under the current RMP prices:

        c_l - sum_{e in l} (pi_e - sigma_e)

    where pi_e >= 0 prices the service (>=) constraint and sigma_e >= 0 prices
    the capacity (<=) constraint. A negative value means the line can improve
    the RMP and should be added to the pool.
    """
    price = sum(
        service_duals.get(e, 0.0) - capacity_duals.get(e, 0.0) for e in line.edges
    )
    return line.cost - price


def solve_cost_rmp(
    ptn: PTNInstance,
    pool: Dict[int, Line],
    enforce_upper_bounds: bool = True,
    time_limit: float = 60.0,
) -> Tuple[Dict[int, float], float, Dict[int, float], Dict[int, float], str]:
    """
    Solve the LP relaxation of the cost-minimizing line planning master problem:

        min  sum_l c_l f_l
        s.t. sum_{l: e in l} f_l >= min_f_e     (service,  dual pi_e >= 0)
             sum_{l: e in l} f_l <= max_f_e     (capacity, dual -sigma_e <= 0)
             f_l >= 0

    Returns (freqs, objective, service_duals, capacity_duals, status):
      - freqs:          line_id -> f_l (LP relaxation, may be fractional)
      - objective:      optimal LP value (minimization)
      - service_duals:  edge_id -> pi_e >= 0
      - capacity_duals: edge_id -> sigma_e >= 0
      - status:         solver status string ("optimal" on success)
    """
    uncovered = uncovered_required_edges(ptn, pool)
    if uncovered:
        raise IncompletePoolError(uncovered)
    if not pool:
        raise ValueError("cannot solve an RMP with an empty pool")

    from pyscipopt import Model, quicksum

    service: Dict[int, int] = {}   # edge_id -> min_f
    capacity: Dict[int, int] = {}  # edge_id -> max_f
    for e_id, edge in ptn.edges.items():
        min_f, max_f = effective_frequency_bounds(edge, ptn.loads.get(e_id))
        if min_f > 0:
            service[e_id] = min_f
        if enforce_upper_bounds and max_f > 0:
            capacity[e_id] = max_f

    # ------------------------------- primal RMP -------------------------------
    mp = Model("RMP_primal")
    mp.hideOutput()
    mp.setRealParam("limits/time", time_limit)
    f = {
        l_id: mp.addVar(name=f"f_{l_id}", vtype="C", lb=0.0, obj=line.cost)
        for l_id, line in pool.items()
    }
    for e_id, min_f in service.items():
        mp.addCons(
            quicksum(f[l_id] for l_id, line in pool.items() if e_id in line.edges) >= min_f,
            name=f"service_e{e_id}",
        )
    for e_id, max_f in capacity.items():
        mp.addCons(
            quicksum(f[l_id] for l_id, line in pool.items() if e_id in line.edges) <= max_f,
            name=f"capacity_e{e_id}",
        )
    mp.setMinimize()
    mp.optimize()
    if mp.getStatus() != "optimal":
        return {}, float("nan"), {}, {}, mp.getStatus()

    primal_obj = mp.getObjVal()
    freqs = {l_id: mp.getVal(var) for l_id, var in f.items()}

    # ------------------------------- dual RMP ---------------------------------
    # max sum_e min_f_e pi_e - sum_e max_f_e sigma_e
    # s.t. sum_{e in l} pi_e - sum_{e in l} sigma_e <= c_l   for every line l
    md = Model("RMP_dual")
    md.hideOutput()
    md.setRealParam("limits/time", time_limit)
    pi = {e_id: md.addVar(name=f"pi_{e_id}", vtype="C", lb=0.0) for e_id in service}
    sigma = {e_id: md.addVar(name=f"sigma_{e_id}", vtype="C", lb=0.0) for e_id in capacity}
    for l_id, line in pool.items():
        service_terms = [pi[e] for e in line.edges if e in service]
        capacity_terms = [sigma[e] for e in line.edges if e in capacity]
        if not service_terms and not capacity_terms:
            continue
        md.addCons(
            quicksum(service_terms) - quicksum(capacity_terms) <= line.cost,
            name=f"dual_l{l_id}",
        )
    md.setObjective(
        quicksum(pi[e] * b for e, b in service.items())
        - quicksum(sigma[e] * u for e, u in capacity.items()),
        sense="maximize",
    )
    md.optimize()
    if md.getStatus() != "optimal":
        return freqs, primal_obj, {}, {}, md.getStatus()

    dual_obj = md.getObjVal()
    if abs(primal_obj - dual_obj) > 1e-6 * max(1.0, abs(primal_obj)):
        raise RuntimeError(
            f"strong duality violated: primal {primal_obj}, dual {dual_obj}"
        )

    service_duals = {e_id: md.getVal(var) for e_id, var in pi.items()}
    capacity_duals = {e_id: md.getVal(var) for e_id, var in sigma.items()}
    return freqs, primal_obj, service_duals, capacity_duals, mp.getStatus()
