"""
Candidate Line Pool Generator
Generates feasible simple paths (candidate transit lines) on a PTN using shortest-path
and k-shortest-path heuristics, ensuring adequate edge coverage and path length limits.
"""

from typing import List, Dict, Set, Tuple, Optional
import heapq
from .parser import PTNInstance, Line
from .utils import (
    build_network_graph,
    compute_line_cost,
    line_cost_params,
    resolve_line_nodes,
    uncovered_required_edges,
    IncompletePoolError,
)


def find_all_simple_paths_bfs(
    adj: Dict[int, List[Tuple[int, int, float]]],
    start: int,
    max_hops: int = 10,
    max_paths_per_node: int = 50
) -> List[Tuple[List[int], List[int], float]]:
    """
    Finds simple paths starting at `start` up to `max_hops`.
    Returns list of (node_path, edge_path, total_length).
    """
    # queue of (current_node, visited_nodes_set, node_path, edge_path, current_length)
    queue = [(start, {start}, [start], [], 0.0)]
    results = []

    while queue and len(results) < max_paths_per_node:
        curr, visited, n_path, e_path, length = queue.pop(0)

        if len(e_path) >= 2:  # Lines should have at least 2 edges
            results.append((n_path, e_path, length))

        if len(e_path) >= max_hops:
            continue

        for neighbor, e_id, e_len in adj[curr]:
            if neighbor not in visited:
                new_visited = visited | {neighbor}
                new_n_path = n_path + [neighbor]
                new_e_path = e_path + [e_id]
                queue.append((neighbor, new_visited, new_n_path, new_e_path, length + e_len))

    return results


def find_k_best_paths_yen(
    adj: Dict[int, List[Tuple[int, int, float]]],
    start: int,
    end: int,
    k: int = 3,
    max_hops: int = 10
) -> List[Tuple[List[int], List[int], float]]:
    """
    Finds up to k best simple paths from start to end using Yen's algorithm.
    Returns list of (node_path, edge_path, total_length), sorted by length.
    """
    # Edge lengths indexed by edge_id, for cheap path-length lookups
    edge_len = {e_id: length for neighbors in adj.values() for (_, e_id, length) in neighbors}

    def dijkstra_path(
        s: int,
        t: int,
        banned_nodes: Set[int],
        banned_edges: Set[int]
    ) -> Optional[Tuple[List[int], List[int], float]]:
        heap = [(0.0, s, [s], [])]  # (cost, current_node, node_path, edge_path)
        visited: Set[int] = set()

        while heap:
            cost, curr, n_path, e_path = heapq.heappop(heap)
            if curr == t:
                return (n_path, e_path, cost)
            if curr in visited:
                continue
            visited.add(curr)

            for neighbor, e_id, e_len in adj[curr]:
                if neighbor in visited or neighbor in banned_nodes or e_id in banned_edges:
                    continue
                heapq.heappush(heap, (cost + e_len, neighbor, n_path + [neighbor], e_path + [e_id]))

        return None

    A: List[Tuple[List[int], List[int], float]] = []
    B: List[Tuple[float, List[int], List[int]]] = []  # candidate paths, (length, nodes, edges)
    seen_edge_sets: Set[Tuple[int, ...]] = set()

    first_path = dijkstra_path(start, end, {start}, set())
    if first_path is None:
        return A
    A.append(first_path)
    seen_edge_sets.add(tuple(sorted(first_path[1])))

    while len(A) < k:
        prev_path = A[-1]

        # Generate spur candidates from the most recently accepted path
        for i in range(len(prev_path[0]) - 1):
            spur_node = prev_path[0][i]
            root_nodes = prev_path[0][:i + 1]
            root_edges = prev_path[1][:i]

            # Remove the edge leaving the spur node along every accepted path sharing the root
            banned_edges = set()
            for path in A:
                if len(path[0]) > i and path[0][:i + 1] == root_nodes and len(path[1]) > i:
                    banned_edges.add(path[1][i])

            # Root path nodes (except the spur node) must not reappear: keeps paths simple
            banned_nodes = set(root_nodes[:-1])

            spur_path = dijkstra_path(spur_node, end, banned_nodes, banned_edges)
            if spur_path is None:
                continue

            total_nodes = root_nodes[:-1] + spur_path[0]
            total_edges = root_edges + spur_path[1]
            if len(total_edges) > max_hops:
                continue

            canon = tuple(sorted(total_edges))
            if canon in seen_edge_sets:
                continue
            seen_edge_sets.add(canon)

            total_length = sum(edge_len[e_id] for e_id in total_edges)
            B.append((total_length, total_nodes, total_edges))

        if not B:
            break

        B.sort(key=lambda t: t[0])
        best_length, best_nodes, best_edges = B.pop(0)
        A.append((best_nodes, best_edges, best_length))

    return A


def generate_line_pool(
    ptn: PTNInstance,
    min_edges: int = 2,
    max_edges: int = 12,
    k_paths_per_pair: int = 3,
    fixed_cost: Optional[float] = None,
    cost_per_length: Optional[float] = None,
    cost_per_edge: Optional[float] = None
) -> Dict[int, Line]:
    """
    Generates a candidate line pool for a PTN.
    Strategies:
    1. Rank the OD pairs by passenger demand. Make paths only for the top pairs.
    2. Edge-coverage guarantee: Ensure every edge e in E is covered by at least 2 candidate lines.
    3. Remove duplicate lines (paths with same edges regardless of traversal direction).

    Cost parameters default to this instance's Config.cnf lpool_costs_* values,
    so generated lines use the same convention as given pools (see
    utils.apply_line_costs).
    """
    cfg_fixed, cfg_length, cfg_edge = line_cost_params(ptn.config)
    fixed_cost = cfg_fixed if fixed_cost is None else fixed_cost
    cost_per_length = cfg_length if cost_per_length is None else cost_per_length
    cost_per_edge = cfg_edge if cost_per_edge is None else cost_per_edge

    adj = build_network_graph(ptn)
    candidate_lines: Dict[int, Line] = {}
    
    # Track unique edge sets (canonical undirected representation)
    seen_edge_sets: Set[Tuple[int, ...]] = set()

    # If PTN already has a pool in basis/, we can import it first
    max_total_lines = 1000  # Limit total number of candidate lines to avoid explosion
    # The coverage pass below adds at most 2 lines per edge. Reserve that budget
    # up front; otherwise the demand-driven phase can consume the whole cap and
    # leave some edges without any covering line (an incomplete, silently
    # infeasible pool).
    coverage_reserve = 2 * len(ptn.edges)
    demand_cap = max(0, max_total_lines - coverage_reserve)
    line_counter = 1
    for orig_l in ptn.pool.values():
        canon = tuple(sorted(orig_l.edges))
        if canon not in seen_edge_sets:
            seen_edge_sets.add(canon)
            candidate_lines[line_counter] = Line(
                id=line_counter,
                edges=list(orig_l.edges),
                length=orig_l.length,
                cost=orig_l.cost if orig_l.cost > 0 else compute_line_cost(orig_l.length, len(orig_l.edges), fixed_cost, cost_per_length, cost_per_edge),
                nodes=resolve_line_nodes(orig_l.edges, ptn)
            )
            line_counter += 1

    # Sort OD pairs by demand descending
    sorted_od = sorted(ptn.od_matrix.items(), key=lambda x: x[1], reverse=True)
    
    # Generate paths for OD pairs with demand
    for (orig, dest), demand in sorted_od:
        if demand <= 0:
            continue

        # Use k-shortest-paths (Yen's algorithm) for better path diversity
        k_paths = find_k_best_paths_yen(adj, orig, dest, k=k_paths_per_pair, max_hops=max_edges)
        for n_path, e_path, length in k_paths:
            if len(candidate_lines) >= demand_cap:
                break
            if len(e_path) < min_edges:
                continue
            canon = tuple(sorted(e_path))
            if canon not in seen_edge_sets:
                seen_edge_sets.add(canon)
                cost = compute_line_cost(length, len(e_path), fixed_cost, cost_per_length, cost_per_edge)
                candidate_lines[line_counter] = Line(
                    id=line_counter,
                    edges=list(e_path),
                    length=length,
                    cost=cost,
                    nodes=list(n_path)
                )
                line_counter += 1

    # Guarantee edge coverage: every edge must appear in at least one line, and
    # two where the topology allows. This pass runs on the reserved budget and
    # must never be starved by the demand cap.
    for e_id, edge in ptn.edges.items():
        covered = sum(1 for l in candidate_lines.values() if e_id in l.edges)
        needed = 2 - covered
        if needed <= 0:
            continue

        added = 0
        for start_node, end_node in [(edge.u, edge.v), (edge.v, edge.u)]:
            if added >= needed:
                break
            for neighbor, next_e, next_len in adj[end_node]:
                if neighbor == start_node:
                    continue
                path_edges = [e_id, next_e]
                canon = tuple(sorted(path_edges))
                if canon in seen_edge_sets:
                    continue
                seen_edge_sets.add(canon)
                total_len = edge.length + next_len
                cost = compute_line_cost(total_len, 2, fixed_cost, cost_per_length, cost_per_edge)
                candidate_lines[line_counter] = Line(
                    id=line_counter,
                    edges=path_edges,
                    length=total_len,
                    cost=cost,
                    nodes=[start_node, end_node, neighbor]
                )
                line_counter += 1
                added += 1
                if added >= needed:
                    break

        if added == 0 and covered == 0:
            # Isolated edge: no 2-edge extension exists, so a single-edge line is
            # the only candidate that can serve it.
            candidate_lines[line_counter] = Line(
                id=line_counter,
                edges=[e_id],
                length=edge.length,
                cost=compute_line_cost(edge.length, 1, fixed_cost, cost_per_length, cost_per_edge),
                nodes=[edge.u, edge.v]
            )
            seen_edge_sets.add((e_id,))
            line_counter += 1

    uncovered = uncovered_required_edges(ptn, candidate_lines)
    if uncovered:
        raise IncompletePoolError(uncovered)

    return candidate_lines
