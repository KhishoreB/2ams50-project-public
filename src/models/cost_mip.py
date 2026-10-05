"""
Cost-Oriented Line Planning MIP (Baseline Formulation).
Selects line frequencies from a candidate pool to minimize total operational costs
while satisfying lower and upper edge frequency/capacity bounds.
Supports both PySCIPOpt and Gurobi solvers.
"""

from typing import Dict, Tuple, Optional
import time
from ..parser import PTNInstance, Line
from ..utils import effective_frequency_bounds, uncovered_required_edges, IncompletePoolError


def solve_cost_mip_scip(
    ptn: PTNInstance,
    pool: Dict[int, Line],
    time_limit: float = 60.0,
    integer: bool = True,
    enforce_upper_bounds: bool = True
) -> Tuple[Dict[int, int], float, float, str, float]:
    """
    Solves Cost-Minimization Line Planning using PySCIPOpt.
    Returns: (frequencies, objective_val, solve_time_seconds, status_str, mip_gap)
    """
    # An edge with a positive minimum frequency and no covering candidate line
    # makes the pool infeasible. Fail here instead of silently dropping the edge
    # from the model (which would report a bogus "optimal").
    uncovered = uncovered_required_edges(ptn, pool)
    if uncovered:
        raise IncompletePoolError(uncovered)

    from pyscipopt import Model, quicksum

    model = Model(f"CostMIP_{ptn.name}")
    model.setRealParam("limits/time", time_limit)
    model.hideOutput()

    # Decision variables: frequency f_l for each line l in pool
    var_type = "I" if integer else "C"
    f_vars = {}
    for l_id, line in pool.items():
        f_vars[l_id] = model.addVar(
            name=f"f_{l_id}",
            vtype=var_type,
            lb=0,
            ub=None,
            obj=line.cost
        )

    # Objective: Minimize total cost
    model.setMinimize()

    # Constraints for each edge e in E
    for e_id, edge in ptn.edges.items():
        covering_lines = [f_vars[l_id] for l_id, l in pool.items() if e_id in l.edges]
        if not covering_lines:
            continue

        edge_expr = quicksum(covering_lines)

        # One source of truth: infrastructure bounds (Edge.giv) + demand bounds (Load.giv)
        min_f, max_f = effective_frequency_bounds(edge, ptn.loads.get(e_id))

        # Min frequency / demand satisfaction
        if min_f > 0:
            model.addCons(edge_expr >= min_f, name=f"min_f_e{e_id}")

        # Max frequency / capacity
        if enforce_upper_bounds and max_f > 0:
            model.addCons(edge_expr <= max_f, name=f"max_f_e{e_id}")

    start_t = time.perf_counter()
    model.optimize()
    elapsed = time.perf_counter() - start_t

    status = model.getStatus()
    frequencies = {}
    obj_val = float("inf")
    gap = float("nan")

    if status in ("optimal", "bndoptimal", "timelimit"):
        if model.getNSols() > 0:
            obj_val = model.getObjVal()
            try:
                gap = float(model.getGap())
            except Exception:
                gap = float("nan")
            for l_id, var in f_vars.items():
                val = model.getVal(var)
                int_val = int(round(val)) if integer else val
                if int_val > 0:
                    frequencies[l_id] = int_val

    return frequencies, obj_val, elapsed, status, gap


def solve_cost_mip_gurobi(
    ptn: PTNInstance,
    pool: Dict[int, Line],
    time_limit: float = 60.0,
    integer: bool = True,
    enforce_upper_bounds: bool = True
) -> Tuple[Dict[int, int], float, float, str, float]:
    """
    Solves Cost-Minimization Line Planning using Gurobipy.
    Returns: (frequencies, objective_val, solve_time_seconds, status_str, mip_gap)
    """
    # See solve_cost_mip_scip: an uncovered required edge must fail loudly.
    uncovered = uncovered_required_edges(ptn, pool)
    if uncovered:
        raise IncompletePoolError(uncovered)

    import gurobipy as gp
    from gurobipy import GRB

    status_names = {
        GRB.OPTIMAL: "optimal",
        GRB.TIME_LIMIT: "timelimit",
        GRB.INFEASIBLE: "infeasible",
        GRB.INF_OR_UNBD: "inforunbd",
        GRB.UNBOUNDED: "unbounded",
        GRB.INTERRUPTED: "interrupted",
        GRB.SUBOPTIMAL: "bndoptimal",
        GRB.NODE_LIMIT: "nodelimit",
        GRB.SOLUTION_LIMIT: "sollimit",
    }

    env = gp.Env(empty=True)
    env.setParam("OutputFlag", 0)
    env.start()

    model = gp.Model(f"CostMIP_{ptn.name}", env=env)
    model.setParam("TimeLimit", time_limit)

    vtype = GRB.INTEGER if integer else GRB.CONTINUOUS
    f_vars = {}
    for l_id, line in pool.items():
        f_vars[l_id] = model.addVar(
            vtype=vtype,
            lb=0.0,
            obj=line.cost,
            name=f"f_{l_id}"
        )

    model.modelSense = GRB.MINIMIZE

    for e_id, edge in ptn.edges.items():
        covering_lines = [f_vars[l_id] for l_id, l in pool.items() if e_id in l.edges]
        if not covering_lines:
            continue

        expr = gp.quicksum(covering_lines)

        # infrastructure bounds (Edge.giv) + demand bounds (Load.giv)
        min_f, max_f = effective_frequency_bounds(edge, ptn.loads.get(e_id))

        if min_f > 0:
            model.addConstr(expr >= min_f, name=f"min_f_e{e_id}")
        if enforce_upper_bounds and max_f > 0:
            model.addConstr(expr <= max_f, name=f"max_f_e{e_id}")

    start_t = time.perf_counter()
    model.optimize()
    elapsed = time.perf_counter() - start_t

    frequencies = {}
    obj_val = float("inf")
    gap = float("nan")
    status_str = status_names.get(model.Status, str(model.Status))

    if model.SolCount > 0:
        obj_val = model.ObjVal
        try:
            gap = float(model.MIPGap)
        except Exception:
            gap = float("nan")
        for l_id, var in f_vars.items():
            val = var.X
            int_val = int(round(val)) if integer else val
            if int_val > 0:
                frequencies[l_id] = int_val

    return frequencies, obj_val, elapsed, status_str, gap


def solve_cost_mip(
    ptn: PTNInstance,
    pool: Dict[int, Line],
    solver: str = "auto",
    time_limit: float = 60.0,
    integer: bool = True,
    enforce_upper_bounds: bool = True
) -> Tuple[Dict[int, int], float, float, str, float]:
    """
    Unified entry point for solving Cost-MIP.
    `solver` can be 'auto', 'scip', or 'gurobi'.
    Returns: (frequencies, objective_val, solve_time_seconds, status_str, mip_gap)
    """
    if solver in ("auto", "scip"):
        try:
            return solve_cost_mip_scip(ptn, pool, time_limit, integer, enforce_upper_bounds)
        except ImportError:
            if solver == "scip":
                raise
    if solver in ("auto", "gurobi"):
        try:
            return solve_cost_mip_gurobi(ptn, pool, time_limit, integer, enforce_upper_bounds)
        except ImportError:
            if solver == "gurobi":
                raise
    raise RuntimeError("No compatible MIP solver found (install pyscipopt or gurobipy).")
