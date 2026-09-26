"""Terrain helpers: which roads touch, where water pools, where it can leave.

Elevations are SRTM 30 m samples along each road, lightly smoothed at build
time. SRTM in dense cities carries building-height bias and 1-2 m of noise,
which shows up as false pits several metres deep. Before use, the road-level
surface is hydrologically conditioned: pits are filled (priority-flood from
the ward edge) but only down to MAX_PIT_DEPTH_M, so genuine sags such as
subways and low junctions survive while noise does not trap water forever.
"""

import heapq
import math
from collections import defaultdict

MAX_PIT_DEPTH_M = 0.6
EDGE_MARGIN_M = 60.0
OUTLET_PERCENTILE = 0.3


def segment_adjacency(segments: list) -> list:
    """seg index -> set of seg indices sharing a junction."""
    by_junction = defaultdict(list)
    for idx, seg in enumerate(segments):
        by_junction[seg["from_node"]].append(idx)
        by_junction[seg["to_node"]].append(idx)
    adjacency = [set() for _ in segments]
    for members in by_junction.values():
        for a in members:
            adjacency[a].update(m for m in members if m != a)
    return adjacency


def adjacency_pairs(adjacency: list) -> list:
    return [(i, j) for i, nbs in enumerate(adjacency) for j in nbs if i < j]


def boundary_segments(segments: list, bbox: list) -> list:
    s, w, n, e = bbox
    lat0 = math.radians((s + n) / 2)
    flags = []
    for seg in segments:
        lat, lon = seg["mid"]
        dist = min((lat - s) * 111320, (n - lat) * 111320,
                   (lon - w) * 111320 * math.cos(lat0), (e - lon) * 111320 * math.cos(lat0))
        flags.append(dist < EDGE_MARGIN_M)
    return flags


def condition_elevations(raw: list, adjacency: list, boundary: list) -> list:
    """Priority-flood pit filling, limited to MAX_PIT_DEPTH_M."""
    n = len(raw)
    filled = [None] * n
    heap = [(raw[i], i) for i in range(n) if boundary[i]]
    if not heap:
        lowest = min(range(n), key=lambda i: raw[i])
        heap = [(raw[lowest], lowest)]
    heapq.heapify(heap)
    for level, i in heap:
        filled[i] = level
    while heap:
        level, i = heapq.heappop(heap)
        for j in adjacency[i]:
            if filled[j] is None:
                filled[j] = max(raw[j], level)
                heapq.heappush(heap, (filled[j], j))
    return [max(raw[i], (filled[i] if filled[i] is not None else raw[i]) - MAX_PIT_DEPTH_M) for i in range(n)]


def overland_outlets(elevations: list, boundary: list) -> list:
    """Low roads on the ward edge where surface water can run out of the study area."""
    ordered = sorted(elevations)
    cutoff = ordered[int(len(ordered) * OUTLET_PERCENTILE)] if ordered else 0.0
    return [b and z <= cutoff for b, z in zip(boundary, elevations)]


def find_sags(elevations: list, adjacency: list) -> list:
    """A sag is a road lower than every road it connects to."""
    return [bool(nbs) and all(elevations[j] > elevations[i] for j in nbs)
            for i, nbs in enumerate(adjacency)]


def relative_elevation(elevations: list) -> list:
    """Elevation relative to the ward median, in metres."""
    ordered = sorted(elevations)
    median = ordered[len(ordered) // 2] if ordered else 0.0
    return [round(z - median, 2) for z in elevations]
