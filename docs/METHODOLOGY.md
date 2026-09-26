# Methodology

DrainCast is a **screening model**. For every street segment in a ward it estimates standing water on a 5-minute step over the next three hours. It does this by coupling three things that rainfall-only forecasts treat separately:

1. how much rain falls,
2. how much of it the storm-drain network can take away, and
3. where the ground sends whatever is left.

It is not a hydraulic solver such as SWMM or HEC-RAS 2D. It trades physical detail for speed: a full run for a 1,000-segment ward takes 50–170 ms in pure Python. That speed is what lets the dashboard re-run on every slider move.

## 1. Inputs per ward

Built by `tools/build_ward_data.py`.

| Item | How it is derived |
|---|---|
| Street segments | OSM ways (trunk down to residential), clipped to the ward box and split at junctions. Only the largest connected component is kept, so routing is coherent. |
| Width, frontage | Width comes from the OSM `width` tag or a per-class default (trunk 20 m … lane 4 m). Frontage is the strip of plots on each side that drains to the road: 12–30 m per side by class. |
| Catchment area | `length × (width + 2 × frontage)` |
| Gully inlets | One every 30 m, both sides on roads 9 m wide or more. Each takes 12 L/s × the ward condition factor. |
| Elevation | SRTM 30 m at every junction and segment midpoint, with one smoothing pass over neighbouring junctions. |
| Manholes | Junctions grouped on a 110 m grid; one manhole per group, at its lowest point. |
| Outfalls | The lowest ~10% of manholes on the ward edge, plus the two lowest manholes overall (lakes and nallahs inside the ward). |
| Pipes | A multi-source Dijkstra from the outfalls over the street-adjacency graph, with uphill runs penalised. This gives every manhole one downstream neighbour, so the network is a tree. |
| Pipe size | Design flow `Q = C · i_design · A_upstream`, then the smallest standard diameter (300–2400 mm) whose Manning full-bore capacity (n = 0.015, gradient ≥ 1:1000) carries it. |
| Pipe condition | The ward siltation factor (0.60–0.70) × U(0.85, 1.15). About 12% of pipes are stepped down one size and de-rated further, to represent legacy or undersized drains. The build is seeded, so it is reproducible. |

### Ward parameters

| Ward | Runoff C | Design intensity | Condition | Basis |
|---|---|---|---|---|
| Kurla East | 0.90 | 25 mm/h | 0.70 | Legacy BMC standard of 25 mm/h at low tide |
| T. Nagar | 0.90 | 35 mm/h | 0.65 | Assumed |
| Velachery | 0.85 | 35 mm/h | 0.60 | Assumed; heavy siltation reported |
| Saidapet | 0.88 | 35 mm/h | 0.65 | Assumed |
| West Tambaram | 0.80 | 30 mm/h | 0.60 | Assumed; less dense |

The Chennai design intensities are assumptions. Replacing them with Greater Chennai Corporation and Tambaram Corporation design figures is the first thing to do with real data.

## 2. Terrain conditioning

SRTM in dense cities includes building heights and 1–2 m of noise. Used raw, it creates pits several metres deep that trap water forever. Before simulating, we therefore run a **priority-flood** from the ward edge over the street graph. Every pit is filled up to its spill level, but at most **0.6 m** deep. Real sags such as subways and low junctions survive; SRTM noise does not.

Low segments on the ward edge (the lowest 30% by elevation) are **overland outlets**. Water above kerb height there leaves the study area.

## 3. Time step (Δt = 5 min)

The run starts **30 minutes before now** (warm-up), so the network is already carrying water when the forecast window opens.

For each segment *s* with ponded volume *Vₛ*:

1. **Runoff**
   `Vₛ += C · i(t) · A_catch,s · Δt`

2. **Inlet demand**
   `dₛ = min(Vₛ / Δt, inlet_capₛ)`

3. **Network routing.** Manholes are visited in topological order, upstream first. For manhole *m* with upstream pipe inflow *U* and outgoing capacity *Q_m*:
   - If `U ≥ Q_m`: no local inflow is accepted, and `(U − Q_m)·Δt` **surcharges** back onto the streets attached to *m*.
   - Otherwise: local inlets are accepted up to `Q_m − U`, pro rata.
   - The outflow `min(U + accepted, Q_m)` goes to the downstream manhole, or leaves through the outfall.
   - The load `(U + Σd) / Q_m` is recorded for the map.

   With *outfalls blocked* on (high tide, or a river or canal in spate), outfall capacity is multiplied by 0.5.

4. **Overland flow.** For every pair of segments sharing a junction, the water-surface levels `zᵢ + hᵢ` are compared. A volume `0.5 × Δh / (1/Aᵢ + 1/Aⱼ) / max(degree)` moves from the higher surface to the lower one. It is limited to what the donor holds above a 3 mm detention depth, divided among its neighbours. Water therefore runs downhill, fills low junctions and spills over once they are full.

5. **Depth (stage–storage)**
   - `h = V / A_road` while `h ≤ 0.15 m` (inside the kerbs)
   - `h = 0.15 + (V − 0.15·A_road) / A_catch` above that (spreading over footpaths and frontage)

**Mass balance.** Rain = water to outfalls + water on streets + water that left overland. `tests/test_engine.py` checks this to within rounding.

## 4. Risk bands

| Depth | Band | Why this threshold |
|---|---|---|
| < 5 cm | Low | Kerb-side ponding only |
| 5–15 cm | Moderate | Slows traffic; gully gratings hidden |
| 15–30 cm | High | Two-wheelers and small-car exhausts stall |
| > 30 cm | Critical | Cars stall; open manholes are invisible |

## 5. Routing

The street graph is a NetworkX `MultiGraph`: junctions are nodes and segments are edges. At the chosen time step:

- **Shortest route:** plain length.
- **Flood-aware route:** length × 2 for 5–15 cm, × 10 for 15–30 cm, and removed entirely at 30 cm or more.

Travel time assumes 22 km/h dry, 14 km/h at 5–15 cm and 6 km/h at 15–30 cm. If no route stays below 30 cm, the dashboard says so rather than inventing one.

## 6. Rainfall

**Design storms** are built on the 5-minute grid:
- *Steady*: constant.
- *Building*: ramps from 25% to 100% over the first two hours.
- *Cloudburst*: an asymmetric triangle peaking about 45 minutes from now.
- *Passing*: exponential decay with τ = 70 min.

**Live mode** uses Open-Meteo `minutely_15` precipitation (the preceding 15-minute sum × 4 = mm/h) for the ward centre. It is interpolated model output, not radar, and it refreshes every 10 minutes. An IMD Doppler nowcast would be a drop-in replacement for `fetch_live_rainfall`.

## 7. What this model does not do

- **No real drain survey.** The network is synthesised. Depths depend strongly on pipe sizes, so treat them as relative.
- **No validation yet** against observed depths, such as BMC or GCC waterlogging-point logs or crowd reports from 2023–25 events.
- **No pipe storage and no backwater along pipes.** Surcharge appears at the first bottleneck only.
- **No infiltration.** It is small in these wards but not zero: Velachery and Tambaram have open plots.
- **Dry start.** The network is empty at −30 min. Antecedent rain from earlier in the day is ignored.
- **The ward box is the domain.** Water from uphill areas outside the box is not added.

## 8. Next steps with real data

1. Load the corporation's SWD GIS layers (nodes, pipe sizes, invert levels) in place of the synthesised network.
2. Calibrate C, the condition factors and the inlet capacity against logged waterlogging points for two or three past events per ward.
3. Replace SRTM with the corporation's LiDAR or total-station levels for the carriageway.
4. Feed IMD radar nowcasts and tide tables (Mumbai) or river gauges (Adyar) in place of the scenario toggles.
