# DrainCast Methodology

## Flood Prediction Approach

DrainCast uses a **coupled physical model** that integrates rainfall, terrain, and drainage infrastructure to predict street-level flooding. This document explains the scientific foundation.

## Three Coupling Factors

### 1. Rainfall-Runoff Coupling

**Problem:** Rain doesn't immediately disappear—it runs off impervious surfaces (roads, roofs) toward drains.

**Solution:** Calculate surface runoff volume using:

```
Runoff Volume (m³) = Rainfall Intensity (mm/hr) × Road Area (m²) × Impervious Coefficient
                   = (I mm/hr) × (A m²) × 0.85
```

**Why 0.85?**
- Asphalt/concrete: 85% of rain becomes runoff
- Some water is retained in surface irregularities
- Typical urban impervious coefficient range: 0.75-0.95

**Timeline Adjustment:**
As time progresses, rainfall accumulates non-linearly:
```
Adjusted Runoff = Base Runoff × (1 + 0.15 × Timeline)
```
This models the observation that storm intensity often increases over the first 1-2 hours.

### 2. Drainage-Runoff Coupling

**Problem:** Runoff must flow through drainage networks with finite capacity.

**Solution:** Model drainage system as directed graph:

```
Drainage Network = {Nodes, Edges}

Node = Manhole or inlet point
  - Attributes: location, elevation, capacity (L/s)
  
Edge = Underground pipe
  - Attributes: diameter, length, capacity, slope
```

**Capacity Analysis:**
```
Available Capacity = Node Capacity - Incoming Flow
Available Capacity = min(node_capacity, downstream_capacity)
```

For bottleneck detection, use BFS to find minimum capacity in downstream path:

```python
def analyze_bottleneck(node):
    min_cap = node.capacity
    for successor in graph.successors(node):
        downstream = analyze_bottleneck(successor)  # Recursive
        min_cap = min(min_cap, downstream)
    return min_cap
```

**Why Drainage Matters:**
- Total runoff > Available capacity = Water overflow
- Overflow occurs at weakest link (bottleneck)
- Simple sum of capacities is insufficient

### 3. Terrain-Flooding Coupling

**Problem:** Water doesn't accumulate uniformly—it pools in low-lying areas.

**Solution:** Calculate slope factor:

```
Slope Factor = f(elevation_gradient)

  Strong depression    (slope < -0.05): factor = 1.4  (water accumulates)
  Mild depression      (slope < -0.02): factor = 1.2
  Slight depression    (slope < -0.01): factor = 1.1
  Flat terrain         (slope ≈ 0.00):  factor = 1.0  (neutral)
  Slight elevation     (slope < 0.01):  factor = 1.0
  Mild elevation       (slope < 0.02):  factor = 0.9  (water drains)
  Steep elevation      (slope > 0.05):  factor = 0.8  (fast drainage)
```

**Physics:**
- Negative slope = gravity accumulates water
- Positive slope = gravity helps drainage
- Slope derived from DEM or survey data

## Water Depth Estimation

### Core Formula

```
Water Depth (cm) = (Excess Volume in Liters) / (Road Area in m²) × 10
                 = (Runoff - Drain Capacity) / Area × 10
```

**Steps:**

1. **Calculate runoff volume (liters):**
   ```
   V_runoff = (60 mm/hr) × (2400 m²) × 0.85 × 2 hours
            = 60 × 2400 × 0.85 × 2 / 1000  [convert mm to m]
            = 244.8 m³ = 244,800 liters
   ```

2. **Get drainage capacity for timeline:**
   ```
   Capacity = 1200 L/s × 3600 s/hr × 2 hr = 8,640,000 liters
   (Actually, capacity per hour: 1200 × 3600 = 4,320,000 L/hr)
   ```

3. **Calculate excess:**
   ```
   Excess = max(0, 244,800 - 4,320,000) = 0 liters
   Depth = 0 / 2400 × 10 = 0 cm  (No flood in this case)
   ```

4. **Apply terrain factor:**
   ```
   Depth_adjusted = Depth × Slope Factor
   If slope = -0.015 (mild depression): factor = 1.1
   Depth = 0 × 1.1 = 0 cm
   ```

## Risk Classification

```
Water Depth (cm)     │ Classification │ Color │ Vehicle Impact
─────────────────────┼─────────────────┼───────┼──────────────────────
< 5                  │ Low Risk        │ Green │ Safe passage
5 - 15               │ Moderate Risk   │ Yellow│ Caution; slow down
15 - 30              │ High Risk       │ Orange│ Avoid; high water
> 30                 │ Critical        │ Red   │ IMPASSABLE; 2-wheeler dies
```

**Why These Thresholds?**
- 5 cm: Normal vehicle undercarriage clearance
- 15 cm: Two-wheeler stability issues
- 30 cm: Water enters engine; vehicle stalling
- 45+ cm: Amphibious vehicles only

## Nowcasting (0-3 Hour Prediction)

### Rainfall Pattern Simulation

DrainCast simulates four common rainfall patterns:

#### 1. **Light Buildup** (< 30 mm/hr)
- Hour 0: 100% intensity
- Hour 1: 115% (storm intensifying)
- Hour 2: 125% (peak)
- Hour 3: 120% (maintaining)

#### 2. **Moderate Steady** (30-60 mm/hr)
- Hours 0-3: Near-constant intensity (±5% variation)
- Models continuous moderate rainfall

#### 3. **Heavy Decay** (> 60 mm/hr)
- Hour 0: 100% intensity
- Hour 1: 95% (beginning to diminish)
- Hour 2: 85%
- Hour 3: 70% (moving out)

#### 4. **Convective Peak** (Thunderstorm)
- Hour 0: 100%
- Hour 1: 140% (peak intensity)
- Hour 2: 130% (still strong)
- Hour 3: 50% (rapid decay)

### Pattern Selection

```python
if rainfall_intensity < 30:
    pattern = "light_buildup"
elif rainfall_intensity < 60:
    pattern = "moderate_steady"
elif rainfall_intensity < 75:
    pattern = "heavy_decay"
else:
    pattern = "convective_peak"  # Very rare locally
```

### Prediction Confidence

Confidence decreases exponentially with time:

```
Confidence = Base × e^(-0.5 × Hours)

Hour 0: 85% confidence (now)
Hour 1: 52% confidence
Hour 2: 32% confidence
Hour 3: 20% confidence
```

**Why?** Weather is chaotic; longer forecasts are inherently less certain.

## Flood-Safe Routing

### Pathfinding Algorithm

Uses **Dijkstra's algorithm** with weighted edges:

```
Base Weight = Road Distance (km)

Final Weight = {
  Base × 1.0,  if risk = LOW or MODERATE
  Base × 10.0, if risk = HIGH
  Base × 100.0 if risk = CRITICAL  (avoid at all costs)
}
```

### Route Comparison

**Normal Route:** Shortest distance (ignores flood risk)
**Safe Route:** Highest weight but most flood-free

**Trade-off Metrics:**
- Distance difference (km)
- Time difference (minutes) ≈ Distance / 40 km/h

### Example
```
Normal Route: 5 km, but passes through CRITICAL area
Safe Route:   6.8 km, completely avoids flooding
Trade-off:    +1.8 km, +2.7 minutes for safety
```

## Model Limitations & Caveats

### Current Assumptions

1. **Runoff coefficient is constant**
   - Reality: Changes with soil saturation, season
   - Recommendation: Use satellite-derived impervious maps

2. **Linear capacity-flow relationship**
   - Reality: Pipe capacity varies with sediment, age
   - Recommendation: Integrate IoT sensor data

3. **No surface roughness**
   - Reality: Rough surfaces slow water, increase retention
   - Recommendation: Add Manning's coefficient by road type

4. **Instantaneous drainage response**
   - Reality: Pipes have inertia, backflow delays
   - Recommendation: Add dynamic delay models

5. **No lateral flow between streets**
   - Reality: Water spreads sideways on flat terrain
   - Recommendation: Use 2D hydraulic model (HEC-RAS)

### When Model Fails

- **Monsoon onset:** First heavy rain overwhelms calibration
- **Coastal storm surge:** Tidal backflow not modeled
- **Infrastructure failure:** Blocked drains assumed open
- **Extreme events:** >100mm/hr outside training range

## Validation Against Reality

### Ideal Verification Workflow

1. **Historical rainfall data** from IMD weather stations
2. **Observed flooding** from citizen reports or satellite
3. **Hindcast:** Run model on past events
4. **Compare:** Predicted depth vs. reported depth
5. **Calibrate:** Adjust coefficients

### Current Status

✓ Physically reasonable model  
✓ Passes sensitivity analysis  
⚠ Awaiting real validation data  
⚠ Coefficients from literature (not field-tuned)

## Enhancement Roadmap

### Phase 1 (Now): Hackathon
- Rule-based coupling logic
- Sample data for demo ward
- Simplified terrain model

### Phase 2 (6 months): Production
- Real municipal drainage data
- Live IMD weather integration
- Calibrated coefficients
- Historical validation

### Phase 3 (1 year): Advanced
- Machine learning for capacity prediction
- 2D shallow-water equations (hydraulics)
- Coupled storm-surge model
- Real-time sensor fusion

### Phase 4 (2+ years): Operations
- Multi-city deployment
- IoT drain monitoring
- Emergency service integration
- Public mobile app

## References

### Physics
- Manning's Equation (flow velocity)
- Shallow water equations (hydraulics)
- Conservation of mass (continuity)

### Urban Flood Science
- EPA Stormwater Manual
- FEMA Flood Map Technical Reference
- World Bank Urban Flooding Guidelines

### Data Sources
- USGS SRTM DEM (elevation)
- OpenStreetMap (road network)
- Municipal Records (drainage data)

---

**Disclaimer:** This model is simplified for hackathon demonstration. Production use requires:
- Professional hydraulic engineer review
- Real field data calibration
- Peer-reviewed validation
- Regular recalibration with observed data

**Last Updated:** January 2026
