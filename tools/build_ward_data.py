"""Build per-ward datasets for DrainCast from open data.

Roads come from OpenStreetMap (Overpass API), elevations from SRTM 30 m
(OpenTopoData). Municipal storm-water drain (SWD) layouts are not public, so
the drainage network is synthesised: manholes at road junction clusters, pipes
laid along the street network towards the lowest outfalls, and each pipe sized
with the rational method for the ward's design intensity, then de-rated for
siltation. See docs/METHODOLOGY.md for the assumptions.

Usage:
    python tools/build_ward_data.py            # all wards
    python tools/build_ward_data.py velachery  # one ward (substring match)
"""

import heapq
import json
import math
import random
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "tools" / ".cache"

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
]
ELEVATION_API = "https://api.opentopodata.org/v1/srtm30m"
USER_AGENT = "DrainCast/1.0 (SIH 2026 prototype)"

# bbox = (south, west, north, east)
WARDS = [
    {
        "id": "mumbai-kurla-east",
        "name": "Kurla East",
        "city": "Mumbai",
        "bbox": (19.0600, 72.8800, 19.0760, 72.8960),
        "runoff_coeff": 0.90,
        "design_intensity": 25,
        "condition": 0.70,
        "outfall_kind": "tidal creek outfall",
        "notes": "L-Ward. Legacy BMC storm drains were designed for 25 mm/h at low tide; "
                 "outfalls are tide-locked at high tide.",
    },
    {
        "id": "chennai-t-nagar",
        "name": "T. Nagar",
        "city": "Chennai",
        "bbox": (13.0330, 80.2270, 13.0470, 80.2410),
        "runoff_coeff": 0.90,
        "design_intensity": 35,
        "condition": 0.65,
        "outfall_kind": "canal outfall",
        "notes": "Dense commercial core; drains discharge towards the Mambalam canal.",
    },
    {
        "id": "chennai-velachery",
        "name": "Velachery",
        "city": "Chennai",
        "bbox": (12.9730, 80.2100, 12.9880, 80.2250),
        "runoff_coeff": 0.85,
        "design_intensity": 35,
        "condition": 0.60,
        "outfall_kind": "lake / marsh outfall",
        "notes": "Built over the Velachery lake catchment next to Pallikaranai marsh; "
                 "one of the worst-hit areas in 2015 and 2023.",
    },
    {
        "id": "chennai-saidapet",
        "name": "Saidapet",
        "city": "Chennai",
        "bbox": (13.0150, 80.2160, 13.0300, 80.2310),
        "runoff_coeff": 0.88,
        "design_intensity": 35,
        "condition": 0.65,
        "outfall_kind": "Adyar river outfall",
        "notes": "On the Adyar river; outfalls back up when the river is in spate.",
    },
    {
        "id": "chennai-west-tambaram",
        "name": "West Tambaram",
        "city": "Chennai",
        "bbox": (12.9200, 80.0860, 12.9340, 80.1000),
        "runoff_coeff": 0.80,
        "design_intensity": 30,
        "condition": 0.60,
        "outfall_kind": "lake / channel outfall",
        "notes": "Tambaram Corporation. Low-lying layouts near the Adyar headwaters.",
    },
]

HIGHWAY_CLASSES = {
    # class: (carriageway width m, frontage draining to the road per side m)
    "trunk": (20.0, 30.0), "trunk_link": (8.0, 10.0),
    "primary": (16.0, 30.0), "primary_link": (7.0, 10.0),
    "secondary": (12.0, 25.0), "secondary_link": (7.0, 10.0),
    "tertiary": (9.0, 20.0), "tertiary_link": (6.0, 10.0),
    "unclassified": (6.0, 15.0), "residential": (6.0, 15.0), "living_street": (4.0, 12.0),
}

MANHOLE_GRID_M = 110.0
GULLY_SPACING_M = 30.0
GULLY_CAPACITY_LPS = 12.0
MANNING_N = 0.015
MIN_PIPE_GRADIENT = 0.001
PIPE_DIAMETERS_MM = [300, 450, 600, 750, 900, 1050, 1200, 1500, 1800, 2100, 2400]


# --------------------------------------------------------------------------- geo helpers

def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def polyline_length(coords):
    return sum(haversine_m(a[0], a[1], b[0], b[1]) for a, b in zip(coords, coords[1:]))


def point_along(coords, fraction):
    target = polyline_length(coords) * fraction
    run = 0.0
    for a, b in zip(coords, coords[1:]):
        seg = haversine_m(a[0], a[1], b[0], b[1])
        if run + seg >= target and seg > 0:
            t = (target - run) / seg
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        run += seg
    return coords[-1]


# --------------------------------------------------------------------------- fetching

def http_post(url, data, timeout=120):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_osm(ward):
    cache = CACHE_DIR / f"{ward['id']}.osm.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    s, w, n, e = ward["bbox"]
    classes = "|".join(HIGHWAY_CLASSES)
    query = (
        f'[out:json][timeout:120];'
        f'way["highway"~"^({classes})$"]({s},{w},{n},{e});'
        f'out body;>;out skel qt;'
    )
    body = urllib.parse.urlencode({"data": query}).encode()
    last_err = None
    for attempt in range(3):
        for mirror in OVERPASS_MIRRORS:
            try:
                result = http_post(mirror, body)
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps(result), encoding="utf-8")
                return result
            except Exception as err:  # network flakiness: try next mirror
                last_err = err
                print(f"    overpass {mirror} failed: {err}")
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Overpass unavailable: {last_err}")


def fetch_elevations(ward, points):
    """points: list of (lat, lon). Returns list of metres (SRTM 30 m)."""
    cache_path = CACHE_DIR / f"{ward['id']}.elev.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    keys = [f"{lat:.5f},{lon:.5f}" for lat, lon in points]
    missing = sorted({k for k in keys if k not in cache})
    for i in range(0, len(missing), 100):
        batch = missing[i:i + 100]
        url = ELEVATION_API + "?locations=" + "|".join(batch)
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                for key, res in zip(batch, payload["results"]):
                    cache[key] = res["elevation"] if res["elevation"] is not None else 0.0
                break
            except Exception as err:
                print(f"    elevation batch failed ({err}), retrying")
                time.sleep(2 + 2 * attempt)
        else:
            raise RuntimeError("OpenTopoData unavailable")
        time.sleep(1.1)  # public API allows 1 request / second
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    return [cache[k] for k in keys]


# --------------------------------------------------------------------------- road network

def build_segments(ward, osm):
    s, w, n, e = ward["bbox"]
    nodes = {el["id"]: (el["lat"], el["lon"]) for el in osm["elements"] if el["type"] == "node"}
    ways = [el for el in osm["elements"] if el["type"] == "way"]

    def inside(nid):
        lat, lon = nodes[nid]
        return s <= lat <= n and w <= lon <= e

    runs = []
    for way in ways:
        current = []
        for nid in way["nodes"]:
            if nid in nodes and inside(nid):
                current.append(nid)
            else:
                if len(current) >= 2:
                    runs.append((way, current))
                current = []
        if len(current) >= 2:
            runs.append((way, current))

    usage = defaultdict(int)
    for _, run in runs:
        for nid in run:
            usage[nid] += 1
        usage[run[0]] += 1
        usage[run[-1]] += 1

    segments = []
    for way, run in runs:
        start = 0
        for i in range(1, len(run)):
            if usage[run[i]] >= 2 or i == len(run) - 1:
                piece = run[start:i + 1]
                if len(piece) >= 2 and piece[0] != piece[-1]:
                    segments.append((way, piece))
                start = i

    out = []
    for way, piece in segments:
        tags = way.get("tags", {})
        hw = tags.get("highway", "residential")
        width, frontage = HIGHWAY_CLASSES.get(hw, (6.0, 15.0))
        if "width" in tags:
            try:
                width = max(3.0, min(40.0, float(tags["width"].split()[0])))
            except ValueError:
                pass
        coords = [nodes[nid] for nid in piece]
        length = polyline_length(coords)
        if length < 0.5:
            continue
        name = tags.get("name:en") or tags.get("name") or tags.get("ref")
        out.append({
            "way_id": way["id"],
            "name": name,
            "highway": hw,
            "width": width,
            "frontage": frontage,
            "coords": coords,
            "length": length,
            "a": piece[0],
            "b": piece[-1],
        })

    # keep only the largest connected component so every pair of points is routable
    adj = defaultdict(set)
    for seg in out:
        adj[seg["a"]].add(seg["b"])
        adj[seg["b"]].add(seg["a"])
    seen, best = set(), set()
    for start in adj:
        if start in seen:
            continue
        comp, stack = set(), [start]
        while stack:
            cur = stack.pop()
            if cur in comp:
                continue
            comp.add(cur)
            stack.extend(adj[cur] - comp)
        seen |= comp
        if len(comp) > len(best):
            best = comp
    return [seg for seg in out if seg["a"] in best], nodes


def smooth_junction_elevations(segments, junction_elev):
    neighbours = defaultdict(set)
    for seg in segments:
        neighbours[seg["a"]].add(seg["b"])
        neighbours[seg["b"]].add(seg["a"])
    smoothed = {}
    for nid, elev in junction_elev.items():
        nb = [junction_elev[m] for m in neighbours[nid] if m in junction_elev]
        smoothed[nid] = 0.5 * elev + 0.5 * (sum(nb) / len(nb)) if nb else elev
    return smoothed


# --------------------------------------------------------------------------- drainage network

def manning_capacity_m3s(diameter_mm, gradient):
    d = diameter_mm / 1000.0
    area = math.pi * d * d / 4
    radius = d / 4
    return (1 / MANNING_N) * area * radius ** (2 / 3) * math.sqrt(gradient)


def size_pipe(design_q, gradient):
    for dia in PIPE_DIAMETERS_MM:
        if manning_capacity_m3s(dia, gradient) >= design_q:
            return dia
    return PIPE_DIAMETERS_MM[-1]


def build_drainage(ward, segments, junction_elev, rng):
    s, w, n, e = ward["bbox"]
    lat0 = (s + n) / 2
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * math.cos(math.radians(lat0))

    junction_pos = {}
    for seg in segments:
        junction_pos[seg["a"]] = seg["coords"][0]
        junction_pos[seg["b"]] = seg["coords"][-1]

    clusters = defaultdict(list)
    for nid, (lat, lon) in junction_pos.items():
        key = (int((lat - s) * m_per_deg_lat // MANHOLE_GRID_M), int((lon - w) * m_per_deg_lon // MANHOLE_GRID_M))
        clusters[key].append(nid)

    manholes = {}
    junction_to_mh = {}
    for idx, (_, members) in enumerate(sorted(clusters.items())):
        clat = sum(junction_pos[m][0] for m in members) / len(members)
        clon = sum(junction_pos[m][1] for m in members) / len(members)
        rep = min(members, key=lambda m: haversine_m(clat, clon, *junction_pos[m]))
        mh_id = f"MH-{idx + 1:03d}"
        manholes[mh_id] = {
            "id": mh_id,
            "lat": junction_pos[rep][0],
            "lon": junction_pos[rep][1],
            "elevation": min(junction_elev[m] for m in members),
            "own_catchment": 0.0,
        }
        for m in members:
            junction_to_mh[m] = mh_id

    adjacency = defaultdict(dict)
    for seg in segments:
        low = seg["a"] if junction_elev[seg["a"]] <= junction_elev[seg["b"]] else seg["b"]
        seg["manhole"] = junction_to_mh[low]
        manholes[seg["manhole"]]["own_catchment"] += seg["catchment"]
        ma, mb = junction_to_mh[seg["a"]], junction_to_mh[seg["b"]]
        if ma != mb:
            length = max(seg["length"], 20.0)
            if length < adjacency[ma].get(mb, 1e12):
                adjacency[ma][mb] = length
                adjacency[mb][ma] = length

    def near_edge(mh):
        margin = 150.0
        return min(
            (mh["lat"] - s) * m_per_deg_lat, (n - mh["lat"]) * m_per_deg_lat,
            (mh["lon"] - w) * m_per_deg_lon, (e - mh["lon"]) * m_per_deg_lon,
        ) < margin

    boundary = sorted((m for m in manholes.values() if near_edge(m)), key=lambda m: m["elevation"])
    n_out = max(2, round(len(boundary) * 0.10))
    outfalls = {m["id"] for m in boundary[:n_out]}
    lowest = sorted(manholes.values(), key=lambda m: m["elevation"])[:2]
    outfalls |= {m["id"] for m in lowest}

    # multi-source Dijkstra from outfalls: parent pointer = downstream manhole
    dist = {mid: 0.0 for mid in outfalls}
    parent = {}
    heap = [(0.0, mid) for mid in outfalls]
    heapq.heapify(heap)
    while heap:
        d, v = heapq.heappop(heap)
        if d > dist.get(v, 1e18):
            continue
        for u, length in adjacency[v].items():
            uphill = max(0.0, manholes[v]["elevation"] - manholes[u]["elevation"])
            cost = d + length * (1 + 25 * uphill / length)
            if cost < dist.get(u, 1e18):
                dist[u] = cost
                parent[u] = v
                heapq.heappush(heap, (cost, u))

    # manholes not reached (should be rare): attach to nearest reached manhole
    for mid, mh in manholes.items():
        if mid not in dist:
            target = min(dist, key=lambda o: haversine_m(mh["lat"], mh["lon"], manholes[o]["lat"], manholes[o]["lon"]))
            parent[mid] = target
            dist[mid] = dist[target] + 1

    order = sorted(manholes, key=lambda mid: -dist[mid])  # upstream first
    upstream_area = {mid: manholes[mid]["own_catchment"] for mid in manholes}
    for mid in order:
        if mid in parent:
            upstream_area[parent[mid]] += upstream_area[mid]

    c = ward["runoff_coeff"]
    i_design = ward["design_intensity"]
    edges = []
    for mid in order:
        mh = manholes[mid]
        area = upstream_area[mid]
        design_q = c * i_design * area / 3.6e6
        condition = max(0.35, min(1.0, ward["condition"] * rng.uniform(0.85, 1.15)))
        legacy = False
        if mid in parent:
            down = manholes[parent[mid]]
            length = max(20.0, haversine_m(mh["lat"], mh["lon"], down["lat"], down["lon"]))
            gradient = max(MIN_PIPE_GRADIENT, (mh["elevation"] - down["elevation"]) / length)
            gradient = min(gradient, 0.02)
            dia = size_pipe(design_q, gradient)
            if rng.random() < 0.12 and dia > PIPE_DIAMETERS_MM[0]:
                dia = PIPE_DIAMETERS_MM[PIPE_DIAMETERS_MM.index(dia) - 1]
                condition *= 0.8
                legacy = True
            cap = manning_capacity_m3s(dia, gradient) * condition
            edges.append({
                "from": mid,
                "to": parent[mid],
                "pipe_diameter": dia,
                "length": round(length, 1),
                "gradient": round(gradient, 4),
                "condition": round(condition, 2),
                "legacy": legacy,
                "capacity": round(cap * 1000, 1),
            })
            mh["type"] = "manhole"
            mh["downstream"] = parent[mid]
            mh["capacity"] = round(cap * 1000, 1)
        else:
            # outfall structure sized for its catchment, then de-rated
            gradient = 0.002
            dia = size_pipe(design_q, gradient)
            cap = max(manning_capacity_m3s(dia, gradient), design_q) * condition
            mh["type"] = "outfall"
            mh["downstream"] = None
            mh["capacity"] = round(cap * 1000, 1)
        mh["upstream_catchment"] = round(area, 0)

    nodes_out = [
        {
            "id": mh["id"],
            "type": mh["type"],
            "location": [round(mh["lon"], 6), round(mh["lat"], 6)],
            "elevation": round(mh["elevation"], 2),
            "capacity": mh["capacity"],
            "downstream": mh["downstream"],
            "upstream_catchment_m2": mh["upstream_catchment"],
        }
        for mh in sorted(manholes.values(), key=lambda m: m["id"])
    ]
    return nodes_out, edges


# --------------------------------------------------------------------------- main

def build_ward(ward):
    print(f"[{ward['id']}] fetching OSM roads")
    osm = fetch_osm(ward)
    segments, _ = build_segments(ward, osm)
    print(f"    {len(segments)} road segments")

    junctions = {}
    for seg in segments:
        junctions[seg["a"]] = seg["coords"][0]
        junctions[seg["b"]] = seg["coords"][-1]
    junction_ids = sorted(junctions)
    mids = [point_along(seg["coords"], 0.5) for seg in segments]
    print(f"    sampling SRTM elevation at {len(junction_ids) + len(mids)} points")
    elev = fetch_elevations(ward, [junctions[j] for j in junction_ids] + mids)
    raw_junction = dict(zip(junction_ids, elev[:len(junction_ids)]))
    junction_elev = smooth_junction_elevations(segments, raw_junction)
    mid_elev = elev[len(junction_ids):]

    for seg, me in zip(segments, mid_elev):
        ea, eb = junction_elev[seg["a"]], junction_elev[seg["b"]]
        seg["elevation"] = (ea + eb + me) / 3
        seg["slope"] = abs(ea - eb) / seg["length"]
        seg["road_area"] = seg["length"] * seg["width"]
        seg["catchment"] = seg["length"] * (seg["width"] + 2 * seg["frontage"])
        sides = 2 if seg["width"] >= 9 else 1
        gullies = max(1, round(seg["length"] / GULLY_SPACING_M)) * sides
        seg["inlet_capacity"] = gullies * GULLY_CAPACITY_LPS * ward["condition"]

    rng = random.Random(ward["id"])
    drain_nodes, drain_edges = build_drainage(ward, segments, junction_elev, rng)

    segments.sort(key=lambda sg: (-HIGHWAY_CLASSES_ORDER.get(sg["highway"], 9), sg["name"] or "~", sg["a"]))
    features, elevation = [], {}
    for idx, seg in enumerate(segments):
        rid = f"R{idx + 1:04d}"
        features.append({
            "type": "Feature",
            "properties": {
                "id": rid,
                "name": seg["name"],
                "highway": seg["highway"],
                "osm_way": seg["way_id"],
                "width_m": seg["width"],
                "length_m": round(seg["length"], 1),
                "surface_area": round(seg["road_area"], 1),
                "catchment_m2": round(seg["catchment"], 1),
                "inlet_capacity_lps": round(seg["inlet_capacity"], 1),
                "nearest_drain": seg["manhole"],
                "from_node": f"J{seg['a']}",
                "to_node": f"J{seg['b']}",
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [[round(lon, 6), round(lat, 6)] for lat, lon in seg["coords"]],
            },
        })
        elevation[rid] = {"avg_elevation": round(seg["elevation"], 2), "slope": round(seg["slope"], 4)}

    out_dir = DATA_DIR / "wards" / ward["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    s, w, n, e = ward["bbox"]
    boundary = {"type": "FeatureCollection", "features": [{
        "type": "Feature",
        "properties": {"id": ward["id"], "name": ward["name"], "kind": "study area"},
        "geometry": {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]},
    }]}
    write_json(out_dir / "roads.geojson", {"type": "FeatureCollection", "features": features})
    write_json(out_dir / "drainage_nodes.json", drain_nodes)
    write_json(out_dir / "drainage_edges.json", drain_edges)
    write_json(out_dir / "elevation.json", elevation)
    write_json(out_dir / "boundary.geojson", boundary)

    elevs = [seg["elevation"] for seg in segments]
    print(f"    {len(drain_nodes)} manholes ({sum(1 for d in drain_nodes if d['type'] == 'outfall')} outfalls), "
          f"{len(drain_edges)} pipes, elevation {min(elevs):.1f}-{max(elevs):.1f} m")
    return {
        "id": ward["id"],
        "name": ward["name"],
        "city": ward["city"],
        "bbox": list(ward["bbox"]),
        "center": [round((s + n) / 2, 5), round((w + e) / 2, 5)],
        "runoff_coeff": ward["runoff_coeff"],
        "design_intensity": ward["design_intensity"],
        "condition": ward["condition"],
        "outfall_kind": ward["outfall_kind"],
        "notes": ward["notes"],
        "road_count": len(features),
        "drain_count": len(drain_nodes),
    }


HIGHWAY_CLASSES_ORDER = {k: len(HIGHWAY_CLASSES) - i for i, k in enumerate(HIGHWAY_CLASSES)}


def write_json(path, payload):
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    index_path = DATA_DIR / "wards.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"wards": []}
    by_id = {w["id"]: w for w in index["wards"]}
    for ward in WARDS:
        if only and only not in ward["id"]:
            continue
        by_id[ward["id"]] = build_ward(ward)
    index = {
        "sources": {
            "roads": "OpenStreetMap contributors (ODbL), via Overpass API",
            "elevation": "SRTM 30 m via OpenTopoData",
            "drainage": "Synthesised from road network; see docs/METHODOLOGY.md",
        },
        "wards": [by_id[w["id"]] for w in WARDS if w["id"] in by_id],
    }
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
