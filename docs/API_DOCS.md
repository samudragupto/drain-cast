# API

Base path: `/api`. All bodies are JSON. Errors return `{"error": "..."}` with status 400 or 404.

## Scenario parameters

These are shared by `/simulate` and `/route`.

| Field | Type | Default | Notes |
|---|---|---|---|
| `ward` | string | first ward | e.g. `chennai-velachery` |
| `mode` | `"scenario"` \| `"live"` | `"scenario"` | `live` uses the Open-Meteo forecast |
| `pattern` | `steady` \| `building` \| `burst` \| `passing` | `steady` | Ignored in live mode |
| `intensity` | number, mm/h | 50 | Peak intensity, clamped to 0–200 |
| `backwater` | boolean | false | Outfalls pass 50% of capacity |

## `GET /api/wards`

```json
{
  "wards": [{ "id": "chennai-velachery", "name": "Velachery", "city": "Chennai",
              "bbox": [12.973, 80.21, 12.988, 80.225], "center": [12.9805, 80.2175],
              "runoff_coeff": 0.85, "design_intensity": 35, "condition": 0.6,
              "outfall_kind": "lake / marsh outfall", "road_count": 1083, "drain_count": 214, "notes": "..." }],
  "patterns": { "steady": "Constant intensity for the whole window", "...": "..." },
  "sources": { "roads": "...", "elevation": "...", "drainage": "..." }
}
```

## `GET /api/wards/<id>`

Static geometry. Road coordinates are `[lon, lat]`.

```json
{
  "meta": { "...": "as above" },
  "boundary": { "type": "FeatureCollection", "features": ["..."] },
  "roads": [{ "id": "R0001", "name": "Velachery Main Road", "highway": "primary",
              "from_node": "J123", "to_node": "J456", "coordinates": [[80.21, 12.98], "..."],
              "length_m": 84.2, "width_m": 16, "surface_area": 1347, "catchment_m2": 6399,
              "inlet_capacity_lps": 43.2, "nearest_drain": "MH-042",
              "elevation": 5.8, "relative_elevation": -0.7, "slope": 0.004, "sag": false }],
  "drainage_nodes": [{ "id": "MH-042", "type": "manhole", "location": [80.21, 12.98],
                       "elevation": 5.1, "capacity": 412.6, "downstream": "MH-051",
                       "upstream_catchment_m2": 88000 }],
  "drainage_edges": [{ "from": "MH-042", "to": "MH-051", "pipe_diameter": 750, "length": 118,
                       "gradient": 0.004, "condition": 0.62, "legacy": false, "capacity": 412.6 }]
}
```

Capacities are in L/s.

## `POST /api/simulate`

```json
{ "ward": "chennai-velachery", "mode": "scenario", "pattern": "burst", "intensity": 75, "backwater": false }
```

Response (abridged):

```json
{
  "params": { "...": "echo" },
  "start_time": "2026-09-27T00:30:00+05:30",
  "step_minutes": 5,
  "warmup_minutes": 30,
  "rain": { "times": [-30, -25, "...", 175], "intensity": [6.0, "..."], "source": "Design storm" },
  "frames": [{ "t": 0, "depth": [0.0, 1.2, "..."], "load": [0.4, "..."] }],
  "stats":  [{ "t": 0, "counts": { "low": 1083, "moderate": 0, "high": 0, "critical": 0 },
               "flooded_km": 0.0, "max_depth": 0.0, "surcharged": 0 }],
  "roads":  [{ "id": "R0001", "peak_depth": 22.4, "peak_t": 70, "t5": 35, "t15": 55, "t30": null,
               "runoff_m3": 180.2, "drained_m3": 121.9 }],
  "nodes":  [{ "id": "MH-001", "peak_load": 1.42, "first_surcharge": 40, "surcharge_m3": 311.0 }],
  "balance": { "rain_m3": 51234.1, "to_outfalls_m3": 30122.4, "left_overland_m3": 2101.3, "on_streets_m3": 19010.4 }
}
```

- `frames` runs every 5 minutes from `t = 0` to `t = 180`. `depth` is in cm, indexed like `roads` in the ward detail. `load` is inflow ÷ capacity, indexed like `drainage_nodes`.
- Times (`t`, `peak_t`, `t5`, `t15`, `t30`, `first_surcharge`) are minutes after `start_time`. `null` means the event does not happen within the window.

## `POST /api/predict`

A compatibility endpoint: a per-street snapshot at a whole-hour lead time.

```json
{ "ward": "mumbai-kurla-east", "rainfall_intensity": 60, "timeline": 2 }
```

It returns `roads[]` with `flood_risk`, `water_depth` (cm), `runoff_volume` (L, cumulative), `drain_capacity` (gully inlet L/s) and `coordinates` as `[lat, lon]`.

## `POST /api/route`

The scenario parameters, plus:

```json
{ "start": [12.978, 80.214], "end": [12.986, 80.222], "frame": 12 }
```

```json
{
  "frame": 12, "t": 60,
  "normal": { "coordinates": [[12.978, 80.214], "..."], "length_km": 2.12, "minutes": 12.4,
              "max_depth": 28.8, "flooded_segments": 13,
              "flooded_roads": [{ "name": "Sarathy Nagar 3rd Street", "depth": 28.8 }], "segment_ids": ["..."] },
  "safe":   { "...": "same shape, or null when no route stays below 30 cm" },
  "same_route": false,
  "snap_m": [18, 42]
}
```

Points more than 500 m from any junction are rejected.

## `GET /api/ward-info?ward=<id>`

Returns ward metadata plus `total_road_km`, `outfalls`, `pipes`, `legacy_pipes` and `low_points`.

## `GET /api/rainfall/live?ward=<id>`

Returns the Open-Meteo series used in live mode: `times`, `series` (mm/h), `source`, `issued` and `current_mm`.
