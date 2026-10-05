"""
LinTim Data Parser
Parses PTN network files (.giv, .cnf) from the LinTim benchmark suite into structured Python objects.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import os
import re


@dataclass
class Stop:
    id: int
    short_name: str
    long_name: str
    x: float
    y: float


@dataclass
class Edge:
    id: int
    u: int  # left-stop-id
    v: int  # right-stop-id
    length: float
    lower_bound: int  # min frequency/load infra
    upper_bound: int  # max frequency/capacity infra


@dataclass
class ODRecord:
    origin: int
    destination: int
    passengers: float


@dataclass
class Line:
    id: int
    edges: List[int]  # Sequence of edge IDs in traversal order
    length: float = 0.0
    cost: float = 0.0
    nodes: List[int] = field(default_factory=list)  # Sequence of stop IDs if resolved


@dataclass
class PTNInstance:
    name: str
    stops: Dict[int, Stop]
    edges: Dict[int, Edge]
    od_matrix: Dict[Tuple[int, int], float]
    config: Dict[str, str]
    loads: Dict[int, Tuple[float, int, int]] = field(default_factory=dict)  # edge_id -> (load, min_f, max_f)
    pool: Dict[int, Line] = field(default_factory=dict)

    @property
    def lines(self) -> List[Line]:
        return list(self.pool.values())

    @property
    def num_stops(self) -> int:
        return len(self.stops)

    @property
    def num_edges(self) -> int:
        return len(self.edges)

    @property
    def total_demand(self) -> float:
        return sum(self.od_matrix.values())

    @property
    def vehicle_capacity(self) -> int:
        """
        Passengers per vehicle for this dataset, read from its Config.cnf
        (gen_passengers_per_vehicle). Raises instead of falling back to a
        hard-coded default: a missing or malformed capacity would silently
        corrupt every frequency and capacity computation built on it.
        """
        key = "gen_passengers_per_vehicle"
        raw = self.config.get(key)
        if raw is None:
            raise KeyError(
                f"{self.name}: Config.cnf has no '{key}' entry, so the vehicle "
                "capacity is unknown"
            )
        try:
            capacity = int(float(raw))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{self.name}: invalid {key}={raw!r} in Config.cnf"
            ) from exc
        if capacity <= 0:
            raise ValueError(
                f"{self.name}: {key} must be positive, got {capacity}"
            )
        return capacity


def _parse_csv_lines(filepath: str) -> List[List[str]]:
    """Helper to parse LinTim semicolon-delimited files, ignoring comments and whitespace."""
    rows = []
    if not os.path.exists(filepath):
        return rows
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Drop trailing inline comments ("value  # note") so numeric settings
            # like "lpool_costs_fixed; 50 # default" parse cleanly. Splitting on a
            # '#' preceded by whitespace leaves quoted values untouched.
            line = re.split(r"\s+#", line, maxsplit=1)[0].strip()
            if not line:
                continue
            parts = [p.strip().strip('"') for p in line.split(";")]
            rows.append(parts)
    return rows


def load_config(config_path: str, global_config_path: Optional[str] = None) -> Dict[str, str]:
    """Loads configuration key-values, handling include statements."""
    config: Dict[str, str] = {}
    
    if global_config_path and os.path.exists(global_config_path):
        for parts in _parse_csv_lines(global_config_path):
            if len(parts) >= 2:
                config[parts[0]] = parts[1]

    if os.path.exists(config_path):
        for parts in _parse_csv_lines(config_path):
            if len(parts) >= 2:
                config[parts[0]] = parts[1]

    return config


def load_ptn(dataset_dir: str, global_config_path: Optional[str] = None) -> PTNInstance:
    """
    Loads a full LinTim dataset directory into a PTNInstance object.
    
    Expected files under dataset_dir/basis/:
    - Stop.giv
    - Edge.giv
    - OD.giv
    - Config.cnf
    Optional:
    - Load.giv
    - Pool.giv & Pool-Cost.giv
    """
    name = os.path.basename(os.path.normpath(dataset_dir))
    basis_dir = os.path.join(dataset_dir, "basis")

    # 1. Config
    config_file = os.path.join(basis_dir, "Config.cnf")
    config = load_config(config_file, global_config_path)

    # 2. Stops
    stops: Dict[int, Stop] = {}
    stop_rows = _parse_csv_lines(os.path.join(basis_dir, "Stop.giv"))
    for row in stop_rows:
        if len(row) >= 5:
            s_id = int(row[0])
            stops[s_id] = Stop(
                id=s_id,
                short_name=row[1],
                long_name=row[2],
                x=float(row[3]),
                y=float(row[4])
            )

    # 3. Edges
    edges: Dict[int, Edge] = {}
    edge_rows = _parse_csv_lines(os.path.join(basis_dir, "Edge.giv"))
    for row in edge_rows:
        if len(row) >= 6:
            e_id = int(row[0])
            edges[e_id] = Edge(
                id=e_id,
                u=int(row[1]),
                v=int(row[2]),
                length=float(row[3]),
                lower_bound=int(float(row[4])),
                upper_bound=int(float(row[5]))
            )

    # 4. OD Matrix
    od_matrix: Dict[Tuple[int, int], float] = {}
    od_rows = _parse_csv_lines(os.path.join(basis_dir, "OD.giv"))
    for row in od_rows:
        if len(row) >= 3:
            u, v, demand = int(row[0]), int(row[1]), float(row[2])
            if demand > 0:
                od_matrix[(u, v)] = demand

    # 5. Loads (optional)
    loads: Dict[int, Tuple[float, int, int]] = {}
    load_rows = _parse_csv_lines(os.path.join(basis_dir, "Load.giv"))
    for row in load_rows:
        if len(row) >= 4:
            e_id = int(row[0])
            load = float(row[1])
            min_f = int(float(row[2]))
            max_f = int(float(row[3]))
            loads[e_id] = (load, min_f, max_f)
            # Load.giv bounds stay in `loads`; Edge fields keep the infrastructure limits.

    # 6. Pre-existing Line Pool (optional)
    pool: Dict[int, Line] = {}
    pool_rows = _parse_csv_lines(os.path.join(basis_dir, "Pool.giv"))
    for row in pool_rows:
        if len(row) >= 3:
            l_id = int(row[0])
            # row[1] is edge-order
            e_id = int(row[2])
            if l_id not in pool:
                pool[l_id] = Line(id=l_id, edges=[])
            pool[l_id].edges.append(e_id)

    cost_rows = _parse_csv_lines(os.path.join(basis_dir, "Pool-Cost.giv"))
    for row in cost_rows:
        if len(row) >= 3:
            l_id = int(row[0])
            if l_id in pool:
                pool[l_id].length = float(row[1])
                pool[l_id].cost = float(row[2])

    # Resolve node sequences for pool lines
    from .utils import resolve_line_nodes, apply_line_costs
    temp_ptn = PTNInstance(
        name=name,
        stops=stops,
        edges=edges,
        od_matrix=od_matrix,
        config=config,
        loads=loads,
        pool=pool
    )
    for l in pool.values():
        if not l.nodes:
            l.nodes = resolve_line_nodes(l.edges, temp_ptn)

    # One cost convention for every pool: recompute from instance geometry and
    # this dataset's Config.cnf lpool_costs_* settings, ignoring the stored
    # Pool-Cost.giv cost (which uses a different, dataset-specific convention).
    apply_line_costs(temp_ptn)

    return temp_ptn
