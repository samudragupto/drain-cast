"""Load a ward's datasets and build its road graph and drainage graph."""

import json
import logging
import math
from dataclasses import dataclass
from functools import cache, lru_cache
from pathlib import Path

import networkx as nx

from terrain_processor import (
    adjacency_pairs,
    boundary_segments,
    condition_elevations,
    find_sags,
    overland_outlets,
    segment_adjacency,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass
class Ward:
    meta: dict
    roads: dict                     # GeoJSON FeatureCollection as served to the map
    segments: list                  # per-road dicts, index-aligned with roads["features"]
    drain_nodes: list
    drain_edges: list
    boundary: dict
    drainage: nx.DiGraph            # manhole -> downstream manhole
    road_graph: nx.MultiGraph       # junction -- junction, one edge per road segment
    manhole_order: list             # topological, upstream first
    segs_by_manhole: dict           # manhole id -> [segment index] draining into it
    spill_segs: dict                # manhole id -> [segment index] that receive surcharge
    pairs: list                     # (i, j) road pairs that share a junction
    degree: list                    # seg index -> number of connected roads
    outlets: list                   # seg index -> bool, surface water can leave the ward here
    sag: list                       # seg index -> bool, local low point


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _read(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def load_index() -> dict:
    return _read(DATA_DIR / "wards.json")


def ward_ids() -> list:
    return [w["id"] for w in load_index()["wards"]]


@cache
def load_ward(ward_id: str) -> Ward:
    meta = next((w for w in load_index()["wards"] if w["id"] == ward_id), None)
    if meta is None:
        raise KeyError(ward_id)
    folder = DATA_DIR / "wards" / ward_id
    roads = _read(folder / "roads.geojson")
    elevation = _read(folder / "elevation.json")
    drain_nodes = _read(folder / "drainage_nodes.json")
    drain_edges = _read(folder / "drainage_edges.json")
    boundary = _read(folder / "boundary.geojson")

    segments = []
    for feature in roads["features"]:
        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]
        mid = coords[len(coords) // 2]
        elev = elevation.get(props["id"], {})
        segments.append({
            **props,
            "coords": coords,
            "mid": (mid[1], mid[0]),
            "elevation_raw": elev.get("avg_elevation", 0.0),
            "slope": elev.get("slope", 0.0),
        })

    drainage = build_drainage_graph(drain_nodes, drain_edges)
    road_graph = build_road_graph(segments)
    adjacency = segment_adjacency(segments)
    edge_flags = boundary_segments(segments, meta["bbox"])
    conditioned = condition_elevations([s["elevation_raw"] for s in segments], adjacency, edge_flags)
    for seg, z in zip(segments, conditioned):
        seg["elevation"] = round(z, 2)

    segs_by_manhole = {n["id"]: [] for n in drain_nodes}
    for idx, seg in enumerate(segments):
        segs_by_manhole.setdefault(seg["nearest_drain"], []).append(idx)

    spill_segs = {}
    for node in drain_nodes:
        attached = segs_by_manhole.get(node["id"], [])
        if attached:
            spill_segs[node["id"]] = attached
        else:
            lon, lat = node["location"]
            nearest = sorted(range(len(segments)), key=lambda i: haversine_m(lat, lon, *segments[i]["mid"]))
            spill_segs[node["id"]] = nearest[:2]

    ward = Ward(
        meta=meta,
        roads=roads,
        segments=segments,
        drain_nodes=drain_nodes,
        drain_edges=drain_edges,
        boundary=boundary,
        drainage=drainage,
        road_graph=road_graph,
        manhole_order=list(nx.topological_sort(drainage)),
        segs_by_manhole=segs_by_manhole,
        spill_segs=spill_segs,
        pairs=adjacency_pairs(adjacency),
        degree=[len(nbs) for nbs in adjacency],
        outlets=overland_outlets(conditioned, edge_flags),
        sag=find_sags(conditioned, adjacency),
    )
    logger.info("Loaded %s: %d roads, %d manholes, %d pipes",
                ward_id, len(segments), drainage.number_of_nodes(), drainage.number_of_edges())
    return ward


def build_drainage_graph(nodes: list, edges: list) -> nx.DiGraph:
    """Directed drainage graph. Edge u -> v is a pipe carrying flow from u down to v."""
    graph = nx.DiGraph()
    for node in nodes:
        graph.add_node(
            node["id"],
            kind=node["type"],
            location=tuple(node["location"]),
            elevation=node["elevation"],
            capacity=node["capacity"],
        )
    for edge in edges:
        graph.add_edge(
            edge["from"], edge["to"],
            capacity=edge["capacity"],
            diameter=edge["pipe_diameter"],
            length=edge["length"],
            legacy=edge.get("legacy", False),
        )
    if not nx.is_directed_acyclic_graph(graph):
        raise ValueError("drainage network contains a cycle")
    return graph


def build_road_graph(segments: list) -> nx.MultiGraph:
    graph = nx.MultiGraph()
    for idx, seg in enumerate(segments):
        start, end = seg["coords"][0], seg["coords"][-1]
        graph.add_node(seg["from_node"], lat=start[1], lon=start[0])
        graph.add_node(seg["to_node"], lat=end[1], lon=end[0])
        graph.add_edge(seg["from_node"], seg["to_node"], key=idx, idx=idx, length=seg["length_m"])
    return graph


def downstream_path(ward: Ward, node_id: str) -> list:
    """Manholes from node_id to its outfall, inclusive."""
    path = [node_id]
    while True:
        nxt = list(ward.drainage.successors(path[-1]))
        if not nxt:
            return path
        path.append(nxt[0])
