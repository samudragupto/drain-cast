"""Rainfall - drainage - terrain coupling.

A lumped, time-stepped mass balance per road segment (5-minute steps):

  1. Runoff      q = C * i * A_catchment                    (rational method)
  2. Inlet       gullies take min(ponded water, inlet capacity)
  3. Network     manholes are processed upstream -> downstream; each passes at
                 most its outgoing pipe capacity. Flow arriving from upstream
                 beyond that capacity surcharges out of the manhole onto its
                 streets, and local inlets are throttled to the room left.
  4. Overland    water surfaces (ground + depth) of connected roads relax
                 towards each other, so water runs downhill, fills low spots
                 and spills over their lip (terrain coupling). Low roads on the
                 ward edge shed water above kerb height out of the area.
  5. Depth       stage-storage: water fills the carriageway up to kerb height,
                 then spills across footpaths and plot frontage.

It is a screening model, not a hydraulic solver: no pipe storage, no
backwater along pipes, no momentum. Its job is to rank streets by when and
how deep they flood, fast enough to re-run on every slider move.
"""

from dataclasses import dataclass

from graph_builder import Ward

KERB_HEIGHT_M = 0.15
DETENTION_M = 0.003
OVERLAND_RELAX = 0.5
OUTLET_FRACTION = 0.3
BACKWATER_OUTFALL_FACTOR = 0.5
RISK_THRESHOLDS_CM = (5.0, 15.0, 30.0)
RISK_LEVELS = ("low", "moderate", "high", "critical")


def classify_risk(depth_cm: float) -> str:
    if depth_cm < RISK_THRESHOLDS_CM[0]:
        return "low"
    if depth_cm < RISK_THRESHOLDS_CM[1]:
        return "moderate"
    if depth_cm < RISK_THRESHOLDS_CM[2]:
        return "high"
    return "critical"


def stage_depth_m(volume_m3: float, road_area_m2: float, spill_area_m2: float) -> float:
    kerb_volume = KERB_HEIGHT_M * road_area_m2
    if volume_m3 <= kerb_volume:
        return volume_m3 / road_area_m2
    return KERB_HEIGHT_M + (volume_m3 - kerb_volume) / spill_area_m2


@dataclass
class _Static:
    c: float
    catchment: list
    road_area: list
    spill_area: list
    ground: list         # conditioned road elevation, m
    inlet: list          # m3/s
    capacity: dict       # manhole -> m3/s
    downstream: dict


def _prepare(ward: Ward, backwater: bool) -> _Static:
    segs = ward.segments
    capacity, downstream = {}, {}
    for node in ward.drain_nodes:
        cap = node["capacity"] / 1000.0
        if node["type"] == "outfall" and backwater:
            cap *= BACKWATER_OUTFALL_FACTOR
        capacity[node["id"]] = max(cap, 1e-4)
        downstream[node["id"]] = node.get("downstream")
    return _Static(
        c=ward.meta["runoff_coeff"],
        catchment=[s["catchment_m2"] for s in segs],
        road_area=[max(s["surface_area"], 1.0) for s in segs],
        spill_area=[max(s["catchment_m2"], s["surface_area"], 1.0) for s in segs],
        ground=[s["elevation"] for s in segs],
        inlet=[s["inlet_capacity_lps"] / 1000.0 for s in segs],
        capacity=capacity,
        downstream=downstream,
    )


def simulate(ward: Ward, rain_series: list, step_min: int, warmup_steps: int, backwater: bool = False) -> dict:
    """Run the coupled model. Frames are recorded from the end of the warm-up (t = 0) onwards."""
    st = _prepare(ward, backwater)
    n = len(ward.segments)
    dt = step_min * 60.0
    order = ward.manhole_order

    storage = [0.0] * n
    runoff_total = [0.0] * n
    drained_total = [0.0] * n
    peak_depth = [0.0] * n
    peak_t = [None] * n
    first_cross = [[None, None, None] for _ in range(n)]
    node_peak_load = {m: 0.0 for m in order}
    node_first_surcharge = {m: None for m in order}
    node_surcharge_m3 = {m: 0.0 for m in order}
    outfall_m3 = 0.0
    rain_m3 = 0.0
    left_overland_m3 = 0.0

    frames, stats = [], []

    def record(t_min, loads, surcharged):
        depths = []
        counts = dict.fromkeys(RISK_LEVELS, 0)
        flooded_m = 0.0
        for i in range(n):
            d = stage_depth_m(storage[i], st.road_area[i], st.spill_area[i]) * 100.0
            depths.append(round(d, 1))
            counts[classify_risk(d)] += 1
            if d >= RISK_THRESHOLDS_CM[1]:
                flooded_m += ward.segments[i]["length_m"]
            if t_min >= 0:
                if d > peak_depth[i]:
                    peak_depth[i], peak_t[i] = d, t_min
                for k, thr in enumerate(RISK_THRESHOLDS_CM):
                    if first_cross[i][k] is None and d >= thr:
                        first_cross[i][k] = t_min
        if t_min < 0:
            return
        frames.append({
            "t": t_min,
            "depth": depths,
            "load": [round(loads.get(node["id"], 0.0), 2) for node in ward.drain_nodes],
        })
        stats.append({
            "t": t_min,
            "counts": counts,
            "flooded_km": round(flooded_m / 1000.0, 2),
            "max_depth": max(depths) if depths else 0.0,
            "surcharged": surcharged,
        })

    total_steps = len(rain_series)
    record(-warmup_steps * step_min, {}, 0)
    for k, intensity in enumerate(rain_series):
        t_end = (k + 1 - warmup_steps) * step_min

        # 1. runoff onto each road
        rate = st.c * intensity / 3.6e6
        for i in range(n):
            vol = rate * st.catchment[i] * dt
            storage[i] += vol
            runoff_total[i] += vol
            rain_m3 += vol

        # 2 + 3. inlets and pipe network, upstream first
        demand = [min(storage[i] / dt, st.inlet[i]) for i in range(n)]
        pipe_in = {}
        loads = {}
        surcharged = 0
        for m in order:
            upstream = pipe_in.get(m, 0.0)
            cap = st.capacity[m]
            segs = ward.segs_by_manhole.get(m, [])
            wanted = sum(demand[i] for i in segs)
            loads[m] = (upstream + wanted) / cap
            if upstream >= cap:
                accepted, out = 0.0, cap
                spill = (upstream - cap) * dt
            else:
                accepted = min(wanted, cap - upstream)
                out = upstream + accepted
                spill = 0.0
            if wanted > 0 and accepted > 0:
                frac = accepted / wanted
                for i in segs:
                    take = demand[i] * frac * dt
                    storage[i] -= take
                    drained_total[i] += take
            if spill > 0 or wanted > accepted + 1e-9:
                surcharged += 1
                if node_first_surcharge[m] is None and t_end > 0:
                    node_first_surcharge[m] = t_end
            if spill > 0:
                node_surcharge_m3[m] += spill
                targets = ward.spill_segs[m]
                area = sum(st.road_area[i] for i in targets)
                for i in targets:
                    storage[i] += spill * st.road_area[i] / area
            if t_end > 0:
                node_peak_load[m] = max(node_peak_load[m], loads[m])
            nxt = st.downstream.get(m)
            if nxt:
                pipe_in[nxt] = pipe_in.get(nxt, 0.0) + out
            else:
                outfall_m3 += out * dt

        # 4. overland: water surfaces of connected roads relax towards each other
        head, pond_area, avail = [], [], []
        for i in range(n):
            h = stage_depth_m(storage[i], st.road_area[i], st.spill_area[i])
            head.append(st.ground[i] + h)
            pond_area.append(st.road_area[i] if h <= KERB_HEIGHT_M else st.spill_area[i])
            avail.append(max(0.0, storage[i] - DETENTION_M * st.road_area[i]) * 0.9 / max(1, ward.degree[i]))
        moves = [0.0] * n
        for i, j in ward.pairs:
            diff = head[i] - head[j]
            if diff < 0:
                i, j, diff = j, i, -diff
            if diff < 0.005 or avail[i] <= 0:
                continue
            equalise = diff / (1 / pond_area[i] + 1 / pond_area[j])
            vol = min(OVERLAND_RELAX * equalise / max(ward.degree[i], ward.degree[j]), avail[i])
            moves[i] -= vol
            moves[j] += vol
        for i in range(n):
            storage[i] = max(0.0, storage[i] + moves[i])
            if ward.outlets[i]:
                above_kerb = storage[i] - KERB_HEIGHT_M * st.road_area[i]
                if above_kerb > 0:
                    leaving = above_kerb * OUTLET_FRACTION
                    storage[i] -= leaving
                    left_overland_m3 += leaving

        record(t_end, loads, surcharged)

    roads = []
    for i, seg in enumerate(ward.segments):
        t5, t15, t30 = first_cross[i]
        roads.append({
            "id": seg["id"],
            "peak_depth": round(peak_depth[i], 1),
            "peak_t": peak_t[i],
            "t5": t5,
            "t15": t15,
            "t30": t30,
            "runoff_m3": round(runoff_total[i], 1),
            "drained_m3": round(drained_total[i], 1),
        })
    nodes = [
        {
            "id": node["id"],
            "peak_load": round(node_peak_load[node["id"]], 2),
            "first_surcharge": node_first_surcharge[node["id"]],
            "surcharge_m3": round(node_surcharge_m3[node["id"]], 1),
        }
        for node in ward.drain_nodes
    ]
    balance = {
        "rain_m3": round(rain_m3, 1),
        "to_outfalls_m3": round(outfall_m3, 1),
        "left_overland_m3": round(left_overland_m3, 1),
        "on_streets_m3": round(sum(storage), 1),
    }
    return {"frames": frames, "stats": stats, "roads": roads, "nodes": nodes,
            "balance": balance, "steps": total_steps}
