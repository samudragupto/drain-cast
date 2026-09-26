"""DrainCast API."""

import gzip
import logging
import os
from functools import lru_cache

from flask import Flask, jsonify, request
from flask_cors import CORS

import coupling_engine as engine
import nowcast_simulator as nowcast
from graph_builder import load_index, load_ward, ward_ids
from routing import plan_routes
from terrain_processor import relative_elevation

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("draincast")

app = Flask(__name__)
CORS(app)


class BadRequest(Exception):
    pass


@app.errorhandler(BadRequest)
def _bad_request(err):
    return jsonify({"error": str(err)}), 400


@app.errorhandler(404)
def _not_found(_):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def _server_error(err):
    logger.exception("Unhandled error: %s", err)
    return jsonify({"error": "Internal server error"}), 500


@app.after_request
def _compress(resp):
    """Simulation payloads are large, highly repetitive JSON; gzip cuts them ~8x."""
    if (
        resp.direct_passthrough
        or resp.status_code != 200
        or "gzip" not in request.headers.get("Accept-Encoding", "")
        or resp.headers.get("Content-Encoding")
        or (resp.content_length or 0) < 2048
    ):
        return resp
    data = gzip.compress(resp.get_data(), compresslevel=5)
    resp.set_data(data)
    resp.headers["Content-Encoding"] = "gzip"
    resp.headers["Content-Length"] = str(len(data))
    resp.headers.add("Vary", "Accept-Encoding")
    return resp


def _ward(ward_id):
    if ward_id not in ward_ids():
        raise BadRequest(f"Unknown ward '{ward_id}'")
    return load_ward(ward_id)


def _scenario(body: dict) -> dict:
    mode = body.get("mode", "scenario")
    if mode not in ("scenario", "live"):
        raise BadRequest("mode must be 'scenario' or 'live'")
    pattern = body.get("pattern", "steady")
    if pattern not in nowcast.PATTERNS:
        raise BadRequest(f"pattern must be one of {sorted(nowcast.PATTERNS)}")
    try:
        intensity = float(body.get("intensity", 50))
    except (TypeError, ValueError):
        raise BadRequest("intensity must be a number (mm/h)") from None
    return {
        "ward": body.get("ward") or ward_ids()[0],
        "mode": mode,
        "pattern": pattern,
        "intensity": max(0.0, min(200.0, round(intensity, 1))),
        "backwater": bool(body.get("backwater", False)),
    }


def _rain_series(params: dict):
    ward = _ward(params["ward"])
    if params["mode"] == "live":
        lat, lon = ward.meta["center"]
        try:
            live = nowcast.fetch_live_rainfall(lat, lon)
        except Exception as err:
            logger.warning("Live rainfall unavailable: %s", err)
            raise BadRequest("Live forecast is unavailable right now (no connection to Open-Meteo). "
                             "Use a scenario instead.") from err
        return tuple(live["series"]), {k: v for k, v in live.items() if k != "series"}
    series = nowcast.design_hyetograph(params["pattern"], params["intensity"])
    return tuple(series), {"source": "Design storm", "description": nowcast.PATTERNS[params["pattern"]]}


@lru_cache(maxsize=64)
def _run(ward_id: str, series: tuple, backwater: bool) -> dict:
    ward = load_ward(ward_id)
    warmup = nowcast.WARMUP_MIN // nowcast.STEP_MIN
    return engine.simulate(ward, list(series), nowcast.STEP_MIN, warmup, backwater)


def _simulate(params: dict):
    series, rain_meta = _rain_series(params)
    return _run(params["ward"], series, params["backwater"]), series, rain_meta


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "time": nowcast.now_ist().isoformat()})


@app.get("/api/wards")
def wards():
    index = load_index()
    return jsonify({"wards": index["wards"], "sources": index["sources"], "patterns": nowcast.PATTERNS})


@app.get("/api/wards/<ward_id>")
def ward_detail(ward_id):
    ward = _ward(ward_id)
    rel = relative_elevation([s["elevation"] for s in ward.segments])
    roads = []
    for seg, rel_e, sag in zip(ward.segments, rel, ward.sag):
        roads.append({
            "id": seg["id"],
            "name": seg["name"],
            "highway": seg["highway"],
            "from_node": seg["from_node"],
            "to_node": seg["to_node"],
            "coordinates": seg["coords"],
            "length_m": seg["length_m"],
            "width_m": seg["width_m"],
            "surface_area": seg["surface_area"],
            "catchment_m2": seg["catchment_m2"],
            "inlet_capacity_lps": seg["inlet_capacity_lps"],
            "nearest_drain": seg["nearest_drain"],
            "elevation": seg["elevation"],
            "relative_elevation": rel_e,
            "slope": seg["slope"],
            "sag": sag,
        })
    return jsonify({
        "meta": ward.meta,
        "boundary": ward.boundary,
        "roads": roads,
        "drainage_nodes": ward.drain_nodes,
        "drainage_edges": ward.drain_edges,
    })


@app.post("/api/simulate")
def simulate():
    params = _scenario(request.get_json(silent=True) or {})
    result, series, rain_meta = _simulate(params)
    return jsonify({
        "params": params,
        "start_time": nowcast.now_ist().isoformat(),
        "step_minutes": nowcast.STEP_MIN,
        "warmup_minutes": nowcast.WARMUP_MIN,
        "rain": {"times": nowcast.step_times(), "intensity": list(series), **rain_meta},
        **result,
    })


@app.post("/api/predict")
def predict():
    """Road-by-road prediction at one lead time (0-3 h) for a steady storm."""
    body = request.get_json(silent=True) or {}
    params = _scenario({
        "ward": body.get("ward"),
        "intensity": body.get("rainfall_intensity", 50),
        "pattern": body.get("pattern", "steady"),
        "backwater": body.get("backwater", False),
    })
    try:
        hours = max(0, min(3, int(body.get("timeline", 0))))
    except (TypeError, ValueError):
        raise BadRequest("timeline must be 0, 1, 2 or 3") from None
    result, _, _ = _simulate(params)
    ward = load_ward(params["ward"])
    frame = result["frames"][hours * 60 // nowcast.STEP_MIN]
    roads = []
    for seg, depth, summary in zip(ward.segments, frame["depth"], result["roads"]):
        roads.append({
            "id": seg["id"],
            "name": seg["name"],
            "coordinates": [[c[1], c[0]] for c in seg["coords"]],
            "flood_risk": engine.classify_risk(depth),
            "water_depth": depth,
            "runoff_volume": summary["runoff_m3"] * 1000,
            "drain_capacity": seg["inlet_capacity_lps"],
            "nearest_drain": seg["nearest_drain"],
        })
    return jsonify({
        "ward": params["ward"],
        "rainfall_intensity": params["intensity"],
        "timeline_hours": hours,
        "timestamp": nowcast.now_ist().isoformat(),
        "roads": roads,
        "drainage_nodes": ward.drain_nodes,
    })


@app.post("/api/route")
def route():
    body = request.get_json(silent=True) or {}
    params = _scenario(body)
    try:
        start = (float(body["start"][0]), float(body["start"][1]))
        end = (float(body["end"][0]), float(body["end"][1]))
    except (KeyError, TypeError, ValueError, IndexError):
        raise BadRequest("start and end must be [lat, lon]") from None
    result, _, _ = _simulate(params)
    frame_idx = max(0, min(len(result["frames"]) - 1, int(body.get("frame", 0))))
    depth = result["frames"][frame_idx]["depth"]
    try:
        routes = plan_routes(load_ward(params["ward"]), depth, start, end)
    except ValueError as err:
        raise BadRequest(str(err)) from err
    return jsonify({"frame": frame_idx, "t": result["frames"][frame_idx]["t"], **routes})


@app.get("/api/ward-info")
def ward_info():
    ward = _ward(request.args.get("ward") or ward_ids()[0])
    return jsonify({
        **ward.meta,
        "total_road_km": round(sum(s["length_m"] for s in ward.segments) / 1000, 1),
        "outfalls": sum(1 for n in ward.drain_nodes if n["type"] == "outfall"),
        "pipes": len(ward.drain_edges),
        "legacy_pipes": sum(1 for e in ward.drain_edges if e.get("legacy")),
        "low_points": sum(ward.sag),
    })


@app.get("/api/rainfall/live")
def rainfall_live():
    ward = _ward(request.args.get("ward") or ward_ids()[0])
    lat, lon = ward.meta["center"]
    try:
        live = nowcast.fetch_live_rainfall(lat, lon)
    except Exception as err:
        logger.warning("Live rainfall unavailable: %s", err)
        raise BadRequest("Live forecast is unavailable right now") from err
    return jsonify({"times": nowcast.step_times(), **live})


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
