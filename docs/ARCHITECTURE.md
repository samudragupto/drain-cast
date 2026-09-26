# Architecture

```
frontend/ (React 18, Leaflet)            backend/ (Flask, NetworkX)                 data/
┌──────────────────────────────┐  JSON   ┌───────────────────────────────┐  read   ┌─────────────────────────┐
│ App.jsx  state + playback    │ ──────▶ │ app.py            endpoints   │ ──────▶ │ wards.json   index      │
│ Map.jsx  Leaflet, canvas     │ ◀────── │ graph_builder.py  load ward,  │         │ wards/<id>/             │
│ TimelineBar / ControlPanel   │  gzip   │                   build graphs│         │   roads.geojson         │
│ SummaryPanel / InfoPanel     │         │ terrain_processor conditioning│         │   drainage_nodes.json   │
│ RoutePanel / Legend / Header │         │ coupling_engine   simulation  │         │   drainage_edges.json   │
└──────────────────────────────┘         │ nowcast_simulator rain series │         │   elevation.json        │
                                         │ routing.py        paths       │         │   boundary.geojson      │
                                         └───────────────────────────────┘         └─────────────────────────┘
                                                        ▲                                      ▲
                                             Open-Meteo (live mode)          tools/build_ward_data.py
                                                                             (OSM Overpass + SRTM, offline)
```

## Backend

| Module | Responsibility |
|---|---|
| `graph_builder.py` | Loads a ward once (`lru_cache`). It builds the drainage `DiGraph`, checked to be acyclic with manholes kept in topological order, and the road `MultiGraph`, with junctions as nodes and segments as edges. It also precomputes the engine's lookup tables. |
| `terrain_processor.py` | Segment adjacency, pit conditioning (priority-flood capped at 0.6 m), sags, overland outlets and relative elevation. |
| `nowcast_simulator.py` | Design hyetographs on the 5-minute grid, and the Open-Meteo fetch with a 10-minute cache. |
| `coupling_engine.py` | The time-stepped mass balance. Returns per-frame depths, manhole loads and statistics, plus per-street summaries (peak depth and time, time to cross 5/15/30 cm). |
| `routing.py` | Snaps points to junctions and compares the shortest and flood-aware paths at a given frame. |
| `app.py` | HTTP layer with input validation and gzip for large responses. Simulation results are memoised on `(ward, rain series, backwater)`, so routing and repeated requests reuse them. |

The API is stateless apart from these caches, so any number of gunicorn workers can serve it.

## Frontend

- **One simulation request per input change.** `POST /api/simulate` returns all 37 frames (0–180 min) in one response, and the timeline and autoplay then work entirely client-side. The request is debounced by 200 ms and cancelled with `AbortController` when a newer one starts.
- **Leaflet layers are built once per ward.** Frame changes only call `setStyle` on segments whose risk band changed, and the map uses canvas renderers. That keeps 1,000+ polylines smooth at 4× playback. The view is fitted to the ward only when the ward changes, so playing the timeline never moves the map.
- **Routing follows the timeline.** When A and B are set, each frame change re-requests `/api/route`, debounced by 150 ms.
- **Unnamed OSM lanes are labelled** by the nearest named street within three hops ("Lane off SG Barve Marg"), so hotspot lists are usable in the field.
- The chosen ward and scenario persist in `localStorage`.

## Payload sizes

For Velachery, with 1,099 segments and 214 manholes:
- ward geometry is about 710 KB of raw JSON;
- a simulation is about 860 KB raw.

Both are gzipped by the API.

## Adding a ward

1. Add an entry to `WARDS` in `tools/build_ward_data.py`: bounding box, runoff coefficient, design intensity, condition factor and notes.
2. Run `python tools/build_ward_data.py <id>`.
3. Restart the API. The ward appears in the selector, grouped by city.
