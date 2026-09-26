# DrainCast

**Street-level flood prediction through rainfall–drainage–terrain coupling.**
Smart India Hackathon 2026 · Problem Statement 26085

Weather forecasts say how much it will rain. They don't say which streets will be under water, when, or how deep. DrainCast answers that for a ward, 0–3 hours ahead, so traffic police, fire and ambulance services and the ward disaster cell can act before the water arrives.

It covers five flood-prone wards: **Kurla East** (Mumbai) and **T. Nagar**, **Velachery**, **Saidapet** and **West Tambaram** (Chennai). Each ward uses real street geometry and terrain.

## What you see

- **Map:** every street segment is coloured by predicted standing water. Manholes turn amber near capacity and red when they surcharge.
- **Timeline:** scrub or auto-play from *Now* to *+3 h* in 5-minute steps. The clock shows real IST times.
- **Rainfall input:** choose a design storm (steady, building, cloudburst or passing, 5–150 mm/h) or the live Open-Meteo forecast for the ward. A toggle blocks the outfalls to model high tide or a river in spate.
- **Situation panel:** flooded length, deepest point, overloaded drains, the worst-hit streets, and the streets that will cross 15 cm next.
- **Street detail:** a depth curve over three hours, when the street crosses 15 cm and 30 cm, and *why* it floods: runoff against gully capacity, and which downstream manhole is the bottleneck.
- **Flood-aware routing:** place A and B on the map to compare the shortest route with a route that avoids deep water. Both are recomputed as the timeline moves.

## How it works

```
 rainfall (design storm / Open-Meteo)
        │  mm/h every 5 min
        ▼
 ┌──────────────┐   runoff C·i·A    ┌──────────────┐  inlet capture   ┌───────────────────┐
 │ street       │ ───────────────▶ │ ponded water │ ───────────────▶ │ manhole → pipe →  │
 │ catchments   │                   │ on each road │ ◀─────────────── │ outfall network   │
 └──────────────┘                   └──────┬───────┘   surcharge at   └───────────────────┘
                                           │           bottlenecks
                         water surfaces    │
                         equalise between  ▼
                         connected roads  depth = stage-storage (kerb, then frontage)
                         (SRTM terrain)
```

Each 5-minute step:

1. **Runoff.** Rainfall on each street's catchment (carriageway plus plot frontage) becomes runoff by the rational method, `q = C · i · A`.
2. **Inlets.** Gullies take what they can, up to a capacity de-rated for blocked gratings.
3. **Pipe network.** Manholes are processed from upstream to downstream. Each passes at most its outgoing pipe's capacity. Flow that arrives from upstream beyond that capacity *surcharges* onto the street, which is how bottlenecks flood streets whose own drains are fine.
4. **Terrain.** Water surfaces of connected streets relax towards each other, so water runs downhill, fills low junctions and spills over.
5. **Depth.** Water fills the carriageway up to kerb height (15 cm), then spreads over footpaths and frontage.

Risk bands: **< 5 cm** low · **5–15 cm** moderate · **15–30 cm** high (two-wheelers stall) · **> 30 cm** critical (cars stall; treated as closed for routing).

The full method, parameters and limitations are in [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

## Data

| Layer | Source |
|---|---|
| Streets | OpenStreetMap via Overpass. Split at junctions: 600–1,100 segments per ward |
| Terrain | SRTM 30 m via OpenTopoData, sampled along each street and pit-conditioned |
| Rainfall | Parametric design storms, or the Open-Meteo 15-minute forecast |
| Drainage | **Synthesised.** See below |

Municipal storm-water drain maps for these wards are not public. `tools/build_ward_data.py` therefore builds a plausible network:
- It places manholes at junction clusters and routes pipes along the streets towards the lowest outfalls.
- It sizes each pipe with Manning's equation for the ward's design intensity (25 mm/h for legacy BMC drains, 30–35 mm/h assumed for Chennai).
- It de-rates each pipe for siltation, and randomly marks about 12% as undersized legacy pipes.

With real SWD data, only this step needs replacing. The engine reads nodes and pipes from JSON.

## Run it locally

Requirements: Python 3.10+, Node 18+.

```bash
# terminal 1: API on :5000
cd backend
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python app.py
```

```bash
# terminal 2: dashboard on :3000 (proxies /api to :5000)
cd frontend
npm install
npm start
```

Tests: `cd backend && python -m unittest discover -s tests`. They check water conservation, monotonic response to rainfall, the effect of backwater, and that routing never uses closed roads.

To rebuild ward data, or add a ward, edit `WARDS` in `tools/build_ward_data.py` and run `python tools/build_ward_data.py <ward-id>`. Responses are cached in `tools/.cache/`.

## Deploy

- **API (Render).** `render.yaml` is included. Create a Blueprint from the repo, or a Python web service with root `backend`, build `pip install -r requirements.txt`, start `gunicorn app:app`.
- **Dashboard (Vercel).** Import the repo with root directory `frontend`; the framework preset is Create React App. Set `REACT_APP_API_URL=https://<your-api>/api`.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness |
| `GET /api/wards` | Wards, storm patterns, data sources |
| `GET /api/wards/<id>` | Street, manhole and pipe geometry for one ward |
| `POST /api/simulate` | Full 3-hour run: depth per street and load per manhole every 5 min |
| `POST /api/predict` | Per-street prediction at one lead time (0–3 h) |
| `POST /api/route` | Shortest vs flood-aware route at a given time step |
| `GET /api/ward-info?ward=` | Ward statistics |
| `GET /api/rainfall/live?ward=` | Open-Meteo series used in live mode |

Request and response shapes are in [docs/API_DOCS.md](docs/API_DOCS.md).

## Demo script (2 minutes)

1. **0:00 · Open on Velachery.** "Every line is a real street; colour is predicted standing water. The dashed line on the rain chart is what these drains were built for."
2. **0:15 · Cloudburst, 75 mm/h, press Play.** "Watch the first 45 minutes. Rain crosses the design line, manholes go amber then red, and orange spreads out from the low ground by the lake."
3. **0:45 · Pause at about +1 h and click the top hotspot.** "The panel shows when this street crosses 15 cm and why. Its own gullies can cope; a manhole downstream is over capacity and pushing water back up."
4. **1:10 · Set A and B across the ward.** "The shortest route runs through flooded segments; the flood-aware one is a little longer and stays shallow. Scrub the timeline and the route changes with the water."
5. **1:35 · Tick 'outfalls blocked' and switch to Kurla East.** "High tide in Mumbai closes the outfalls. Same rain, more flooding: that coupling is exactly what a rain-only forecast misses."
6. **1:50 · Close.** "Five wards in two cities from open data. Plug in the corporation's drain survey and the live IMD feed, and it runs on any ward."

## Limitations

This is a screening model built in hackathon time, and it has not been validated against observed flood depths. Specifically:
- Drains are synthesised.
- SRTM has metre-level noise in dense areas.
- Pipes have no storage and no backwater along their length.
- Every run starts from a dry network 30 minutes before *now*.

Use it to rank streets and time decisions, not to quote exact depths. [docs/METHODOLOGY.md](docs/METHODOLOGY.md) lists what we would do next.

## Licence

MIT. Map data © OpenStreetMap contributors (ODbL). Basemap © Esri. Elevation: NASA SRTM.
