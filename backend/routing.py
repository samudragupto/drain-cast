"""Flood-aware routing on the ward's OSM street graph."""

import networkx as nx

from graph_builder import Ward, haversine_m

MAX_SNAP_M = 500.0
IMPASSABLE_CM = 30.0

# travel speeds (km/h) for an emergency / municipal vehicle in city traffic
SPEED_DRY = 22.0
SPEED_WET = 14.0        # 5-15 cm
SPEED_FLOODED = 6.0     # 15-30 cm, crawl through


def flood_penalty(depth_cm: float):
    if depth_cm >= IMPASSABLE_CM:
        return None
    if depth_cm >= 15:
        return 10.0
    if depth_cm >= 5:
        return 2.0
    return 1.0


def speed_for(depth_cm: float) -> float:
    if depth_cm >= 15:
        return SPEED_FLOODED
    if depth_cm >= 5:
        return SPEED_WET
    return SPEED_DRY


def nearest_junction(ward: Ward, lat: float, lon: float):
    best, best_d = None, float("inf")
    for node, attrs in ward.road_graph.nodes(data=True):
        d = haversine_m(lat, lon, attrs["lat"], attrs["lon"])
        if d < best_d:
            best, best_d = node, d
    if best_d > MAX_SNAP_M:
        return None, best_d
    return best, best_d


def _pick_edge(edges: dict, depth: list, flood_aware: bool):
    """Choose the cheapest parallel edge between two junctions."""
    best, best_w = None, float("inf")
    for attrs in edges.values():
        pen = flood_penalty(depth[attrs["idx"]]) if flood_aware else 1.0
        if pen is None:
            continue
        w = attrs["length"] * pen
        if w < best_w:
            best, best_w = attrs, w
    return best, best_w


def _describe(ward: Ward, path: list, depth: list, flood_aware: bool) -> dict:
    coords, used = [], []
    length_m, minutes = 0.0, 0.0
    for u, v in zip(path, path[1:]):
        attrs, _ = _pick_edge(ward.road_graph.get_edge_data(u, v), depth, flood_aware)
        seg = ward.segments[attrs["idx"]]
        line = [[c[1], c[0]] for c in seg["coords"]]
        if seg["from_node"] != u:
            line.reverse()
        coords.extend(line if not coords else line[1:])
        d = depth[attrs["idx"]]
        length_m += seg["length_m"]
        minutes += seg["length_m"] / 1000.0 / speed_for(d) * 60.0
        used.append({"id": seg["id"], "name": seg["name"], "depth": d})
    flooded = [u for u in used if u["depth"] >= 15]
    named = {}
    for u in flooded:
        key = u["name"] or "Unnamed road"
        named[key] = max(named.get(key, 0.0), u["depth"])
    return {
        "coordinates": coords,
        "length_km": round(length_m / 1000.0, 2),
        "minutes": round(minutes, 1),
        "max_depth": max((u["depth"] for u in used), default=0.0),
        "flooded_segments": len(flooded),
        "flooded_roads": [{"name": k, "depth": v} for k, v in sorted(named.items(), key=lambda kv: -kv[1])],
        "segment_ids": [u["id"] for u in used],
    }


def plan_routes(ward: Ward, depth: list, start: tuple, end: tuple) -> dict:
    """Shortest route vs. flood-aware route between two map points at one moment in time."""
    src, src_d = nearest_junction(ward, *start)
    dst, dst_d = nearest_junction(ward, *end)
    if src is None or dst is None:
        raise ValueError("Pick points on or near a road inside the ward")
    if src == dst:
        raise ValueError("Start and destination snap to the same junction")

    def plain(u, v, edges):
        return _pick_edge(edges, depth, False)[1]

    def aware(u, v, edges):
        w = _pick_edge(edges, depth, True)[1]
        return None if w == float("inf") else w

    graph = ward.road_graph
    try:
        normal_path = nx.shortest_path(graph, src, dst, weight=plain)
    except nx.NetworkXNoPath:
        raise ValueError("These points are not connected by the road network") from None

    try:
        safe_path = nx.shortest_path(graph, src, dst, weight=aware)
        safe = _describe(ward, safe_path, depth, True)
    except nx.NetworkXNoPath:
        safe = None

    normal = _describe(ward, normal_path, depth, False)
    return {
        "normal": normal,
        "safe": safe,
        "same_route": safe is not None and safe["segment_ids"] == normal["segment_ids"],
        "snap_m": [round(src_d), round(dst_d)],
    }
