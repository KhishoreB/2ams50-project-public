"""
Column Generation for the Public Transport Line Planning problem.

Student 3:
- Restricted Master Problem (RMP)
- Pricing problem
- Reduced-cost calculation
- Column generation loop
"""

from src.models.rmp import solve_cost_rmp, reduced_cost
from src.utils import (
    build_network_graph,
    compute_line_cost,
    line_cost_params,
    resolve_line_nodes,
)
from src.parser import Line


def compute_pricing_edge_weights(ptn, service_duals, capacity_duals):
    """
    Compute the modified edge weight used by the pricing problem.

    For an edge e:

        weight_e =
            variable_cost_e
            - service_dual_e
            + capacity_dual_e

    The fixed line cost is added separately when evaluating
    the complete candidate line.
    """

    fixed_cost, per_length, per_edge = line_cost_params(ptn.config)

    weights = {}

    for edge_id, edge in ptn.edges.items():
        service_price = service_duals.get(edge_id, 0.0)
        capacity_price = capacity_duals.get(edge_id, 0.0)

        variable_cost = (
            per_length * edge.length
            + per_edge
        )

        weights[edge_id] = (
            variable_cost
            - service_price
            + capacity_price
        )

    return weights


def _path_cost_from_weights(edge_ids, edge_weights, fixed_cost):
    """
    Calculate the reduced-cost expression for a candidate path.
    """

    return fixed_cost + sum(edge_weights[e] for e in edge_ids)


def find_min_reduced_cost_path(
    ptn,
    service_duals,
    capacity_duals,
):
    """
    Pricing problem.

    Search for a simple path with minimum reduced cost.
    Every simple path is enumerated, so the pricing is exact.

    Returns:
        edge_ids, reduced_cost

    If no path exists:
        (None, None)
    """

    graph = build_network_graph(ptn)

    edge_weights = compute_pricing_edge_weights(
        ptn,
        service_duals,
        capacity_duals,
    )

    fixed_cost, _, _ = line_cost_params(ptn.config)

    best_path = None
    best_reduced_cost = float("inf")

    # Search from every node because a line can start anywhere.
    for start_node in graph:

        visited_nodes = {start_node}
        current_path = []

        def dfs(current_node):
            nonlocal best_path, best_reduced_cost

            # A path containing at least one edge is a candidate.
            if current_path:

                candidate_rc = _path_cost_from_weights(
                    current_path,
                    edge_weights,
                    fixed_cost,
                )

                if candidate_rc < best_reduced_cost:
                    best_reduced_cost = candidate_rc
                    best_path = current_path.copy()

            # Extend the path using unused nodes.
            for next_node, edge_id, _length in graph.get(
                current_node,
                []
            ):

                if next_node in visited_nodes:
                    continue

                visited_nodes.add(next_node)
                current_path.append(edge_id)

                dfs(next_node)

                current_path.pop()
                visited_nodes.remove(next_node)

        dfs(start_node)

    if best_path is None:
        return None, None

    return best_path, best_reduced_cost


def create_line_from_path(ptn, line_id, edge_ids):
    """
    Convert a sequence of edge IDs into the project's Line object.
    """

    nodes = resolve_line_nodes(edge_ids, ptn)

    length = sum(
        ptn.edges[e_id].length
        for e_id in edge_ids
    )

    fixed_cost, per_length, per_edge = line_cost_params(ptn.config)

    cost = compute_line_cost(
        length,
        len(edge_ids),
        fixed_cost,
        per_length,
        per_edge,
    )

    return Line(
        id=line_id,
        edges=edge_ids,
        length=length,
        cost=cost,
        nodes=nodes,
    )


def _line_key(edge_ids):
    """
    Direction-independent identity of a line.

    A simple path is fixed by its set of edges, so [1, 3, 4] and
    [4, 3, 1] are the same line driven in opposite directions.
    """

    return frozenset(edge_ids)


def column_generation(
    ptn,
    initial_pool,
    max_iterations=100,
    time_limit=60,
    rc_tolerance=1e-6,
):
    """
    Run the complete Column Generation algorithm.

    Steps:

    1. Solve the Restricted Master Problem.
    2. Obtain service and capacity dual prices.
    3. Solve the pricing problem.
    4. If a negative reduced-cost line exists, add it.
    5. Repeat.
    6. Stop when no reduced cost is below -rc_tolerance.

    rc_tolerance matches the LP solver's own feasibility tolerance:
    reduced costs closer to zero than this are numerical noise.

    Returns:
        pool
        frequencies
        objective
        iterations
        history
        status
    """

    pool = dict(initial_pool)

    history = []

    next_line_id = (
        max(pool.keys()) + 1
        if pool
        else 1
    )

    for iteration in range(1, max_iterations + 1):

        (
            frequencies,
            objective,
            service_duals,
            capacity_duals,
            rmp_status,
        ) = solve_cost_rmp(
            ptn,
            pool,
            enforce_upper_bounds=True,
            time_limit=time_limit,
        )

        if rmp_status != "optimal":
            return {
                "pool": pool,
                "frequencies": frequencies,
                "objective": objective,
                "iterations": iteration,
                "history": history,
                "status": f"RMP_{rmp_status}",
            }

        (
            candidate_edges,
            candidate_rc,
        ) = find_min_reduced_cost_path(
            ptn,
            service_duals,
            capacity_duals,
        )

        history.append(
            {
                "iteration": iteration,
                "rmp_objective": objective,
                "candidate_edges": candidate_edges,
                "candidate_reduced_cost": candidate_rc,
            }
        )

        # No candidate path.
        if candidate_edges is None:
            return {
                "pool": pool,
                "frequencies": frequencies,
                "objective": objective,
                "iterations": iteration,
                "history": history,
                "status": "optimal_no_pricing_column",
            }

        # Column generation termination condition.
        if candidate_rc >= -rc_tolerance:
            return {
                "pool": pool,
                "frequencies": frequencies,
                "objective": objective,
                "iterations": iteration,
                "history": history,
                "status": "optimal_no_negative_reduced_cost",
            }

        # Do not add duplicate columns (in either direction).
        candidate_key = _line_key(candidate_edges)

        duplicate = any(
            _line_key(line.edges) == candidate_key
            for line in pool.values()
        )

        if duplicate:
            return {
                "pool": pool,
                "frequencies": frequencies,
                "objective": objective,
                "iterations": iteration,
                "history": history,
                "status": "stopped_duplicate_column",
            }

        # Create and add the new line.
        new_line = create_line_from_path(
            ptn,
            next_line_id,
            candidate_edges,
        )

        # Safety check: the pricing weights and the RMP's reduced-cost
        # formula must give the same value for the new line.
        rmp_rc = reduced_cost(
            new_line,
            service_duals,
            capacity_duals,
        )

        if abs(rmp_rc - candidate_rc) > 1e-6 * max(1.0, abs(rmp_rc)):
            raise RuntimeError(
                f"pricing reduced cost {candidate_rc} does not match "
                f"reduced_cost() {rmp_rc} for line {candidate_edges}"
            )

        pool[next_line_id] = new_line
        next_line_id += 1

    return {
        "pool": pool,
        "frequencies": frequencies,
        "objective": objective,
        "iterations": max_iterations,
        "history": history,
        "status": "max_iterations_reached",
    }