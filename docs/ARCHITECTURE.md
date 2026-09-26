# DrainCast Architecture

## System Overview

DrainCast is a full-stack web application designed for real-time urban flood nowcasting. The architecture follows a separation of concerns with independent frontend and backend services.

## Frontend Architecture (React.js)

### Component Hierarchy
```
App (Main container)
├── Header (Navigation & stats)
├── Main Content
│   ├── Map (Leaflet component)
│   └── Sidebar
│       ├── ControlPanel (Rainfall & timeline)
│       ├── InfoPanel (Dynamic - shows on road click)
│       ├── RoutePanel (Routing interface)
│       └── Legend (Color coding)
└── ErrorBanner (Error notifications)
```

### Data Flow

1. **User Input** → ControlPanel collects rainfall & timeline
2. **API Call** → axios sends request to /api/predict
3. **Prediction Data** → Received and stored in App state
4. **Map Update** → Leaflet layer refreshes with road colors
5. **User Click** → onRoadSelect triggers InfoPanel display
6. **Info Display** → Selected road details shown

### Component Responsibilities

| Component | Purpose | Dependencies |
|-----------|---------|--------------|
| Map | Leaflet visualization | leaflet, react-leaflet |
| ControlPanel | Rainfall/timeline input | None (pure UI) |
| InfoPanel | Road details display | None (receives props) |
| RoutePanel | Route calculation UI | API utility |
| Legend | Color code reference | mapStyles utility |
| Header | Navigation & branding | None |

### Styling Strategy

- **Utility-First CSS** with custom properties
- **Dark mode support** via CSS variables
- **Responsive design** - Mobile-first approach
- **No CSS-in-JS** - Better performance
- **Accessibility** - WCAG 2.1 compliance

## Backend Architecture (Flask)

### Module Structure

```
backend/
├── app.py                 # Flask entry point, routes
├── coupling_engine.py     # Flood prediction logic
├── graph_builder.py       # Drainage network modeling
├── terrain_processor.py   # Elevation & slope analysis
├── routing.py             # Pathfinding algorithm
└── nowcast_simulator.py   # Rainfall timeline simulation
```

### Request Flow

```
POST /api/predict
    ↓
[app.py::predict()]
    ↓
[coupling_engine.calculate_flood_risk() for each road]
    ↓
[graph_builder.get_drainage_capacity()]
[terrain_processor.apply_terrain_factor()]
    ↓
[Format response with road colors & depths]
    ↓
JSON Response → Frontend
```

### Core Logic Modules

#### 1. **coupling_engine.py**
Couples three physical phenomena:

```python
def calculate_flood_risk(road_id, rainfall_intensity, surface_area, timeline, ...):
    # Step 1: Calculate runoff
    runoff = rainfall_intensity × surface_area × 0.85 × (timeline + 1)
    
    # Step 2: Get drainage capacity
    capacity = graph_builder.get_drainage_capacity(drain_id, graph)
    
    # Step 3: Calculate excess water
    excess = max(0, runoff - capacity)
    
    # Step 4: Apply terrain slope factor
    excess *= terrain_processor.apply_slope_factor(slope)
    
    # Step 5: Estimate depth
    depth = excess / surface_area × 10  # in cm
    
    # Step 6: Classify risk
    return classify_risk(depth)
```

**Key Physics:**
- Impervious coefficient: 0.85 (asphalt/concrete)
- Slope factor: Negative slopes accumulate water (×1.4)
- Positive slopes drain water (×0.8)

#### 2. **graph_builder.py**
Models drainage network as directed graph (NetworkX):

- **Nodes** = Drainage points (manholes, inlets)
- **Edges** = Pipes with capacity weights
- **Weight** = 1/capacity (resistance model)

**Key Algorithms:**
- Find nearest drainage node (Haversine distance)
- Analyze downstream bottlenecks (BFS)
- Calculate network flow (min-cost max-flow)

#### 3. **terrain_processor.py**
Simplified DEM processing:

- Calculate slope from elevation data
- Identify depression areas (high flood risk)
- Compute flow velocity using Manning's equation

**Slope Categories:**
- Steep depression (<-0.05): ×1.4 water accumulation
- Flat (0): ×1.0 neutral
- Steep elevation (>0.05): ×0.8 faster drainage

#### 4. **routing.py**
Flood-safe pathfinding using Dijkstra's algorithm:

- **Normal route** = Shortest distance (ignores floods)
- **Safe route** = 10× penalty for HIGH/CRITICAL roads
- **Metrics** = Distance difference, time difference

#### 5. **nowcast_simulator.py**
Rainfall timeline simulation:

- Patterns: light_buildup, moderate_steady, heavy_decay
- Stochastic variation: ±5%
- Future enhancement: Integrate actual weather radar

## Data Models

### Road Feature (GeoJSON)
```json
{
  "id": "road_001",
  "name": "Station Road",
  "surface_area": 2400,          // m²
  "nearest_drain": "node_001",
  "coordinates": [[lat, lon], ...]
}
```

### Drainage Node
```json
{
  "id": "node_001",
  "type": "manhole",
  "location": [lat, lon],
  "elevation": 12.5,              // meters
  "capacity": 1500                // L/s
}
```

### Drainage Edge (Pipe)
```json
{
  "from": "node_001",
  "to": "node_002",
  "pipe_diameter": 600,           // mm
  "capacity": 1200,               // L/s
  "length": 150                   // meters
}
```

### Elevation Data
```json
{
  "road_001": {
    "avg_elevation": 12.5,        // meters
    "slope": -0.008               // negative = depression
  }
}
```

## API Contract

### Request: POST /api/predict
```json
{
  "rainfall_intensity": 60,       // 10-100 mm/hr
  "timeline": 2                   // 0-3 hours
}
```

### Response
```json
{
  "roads": [
    {
      "id": "road_001",
      "name": "Station Road",
      "flood_risk": "high",       // low|moderate|high|critical
      "water_depth": 18.5,        // cm
      "runoff_volume": 1200,      // liters
      "drain_capacity": 800,      // liters
      "coordinates": [[lat, lon], ...]
    }
  ],
  "drainage_nodes": [...],
  "timestamp": "2026-01-15T14:30:00"
}
```

## Performance Optimization

### Frontend
- Lazy load Leaflet tiles
- Memoize component renders
- Debounce slider input (200ms)
- Use CSS transforms for animations

### Backend
- Cache drainage graph after loading
- Pre-compute elevation factors
- Use vectorized calculations (NumPy ready)
- Connection pooling for DB (future)

## Scalability Considerations

### Current (Hackathon Demo)
- Single ward: 30 road segments
- 8 drainage nodes
- Response time: ~800ms

### Medium Scale (City-wide)
- 50,000+ road segments
- 2,000+ drainage nodes
- Recommendations:
  - Cache predictions (5-minute TTL)
  - Implement vector tile server
  - Use PostGIS for spatial queries

### Large Scale (Multi-city)
- Microservices architecture
- Kafka for event streaming
- Redis for prediction caching
- Separate compute workers for heavy lifting

## Security Considerations

### Currently Implemented
- CORS enabled for frontend
- Input validation (rainfall 10-100, timeline 0-3)
- Error handling with try/except

### Recommended for Production
- API key authentication
- Rate limiting (100 req/min per IP)
- HTTPS enforcement
- SQL injection protection (if using DB)
- XSS prevention (React automatic)

## Testing Strategy

### Unit Tests (Recommended)
```python
test_coupling_engine.py
- test_runoff_calculation()
- test_water_depth_estimation()
- test_risk_classification()

test_graph_builder.py
- test_nearest_node_finding()
- test_bottleneck_detection()

test_terrain_processor.py
- test_slope_factor_application()
```

### Integration Tests
```
test_full_prediction_workflow()
- Mock API request
- Verify response structure
- Check flood depth ranges
```

### Frontend Tests
```javascript
test_map_rendering.test.js
- Verify roads display with correct colors
- Check drainage nodes appear

test_components.test.js
- InfoPanel displays selected road
- Timeline buttons update predictions
```

## Deployment Architecture

```
DNS
 ↓
Vercel CDN (Frontend)     Railway/Render (Backend)
    ↓                              ↓
React App                    Flask + Gunicorn
  (Build: npm run build)      (Python 3.9+)
                              (3-4 dyno hours)
```

### Environment Variables

**Frontend (.env.local)**
```
REACT_APP_API_URL=https://draincast-api.railway.app/api
```

**Backend (.env)**
```
FLASK_ENV=production
LOG_LEVEL=INFO
```

## Monitoring & Logging

### Current
- Backend: Python logging module
- Frontend: Browser console

### Recommended for Production
- Error tracking: Sentry
- Monitoring: Datadog or New Relic
- Logging: CloudWatch or ELK stack
- Alerting: PagerDuty for critical issues

## Technology Choices & Rationale

| Choice | Reason |
|--------|--------|
| Flask | Lightweight, perfect for small API |
| React | Component-based, large ecosystem |
| NetworkX | Graph algorithms without reinventing |
| Leaflet | Lightweight, offline-capable maps |
| JSON files | No DB setup needed for hackathon |

## Future Architectural Changes

1. **Database Migration** → PostgreSQL + PostGIS for spatial queries
2. **Caching Layer** → Redis for prediction memoization
3. **Async Tasks** → Celery for long-running calculations
4. **Event Bus** → Kafka for real-time updates
5. **Microservices** → Separate prediction, routing, notification services

---

**Last Updated:** January 2026  
**Version:** 1.0.0
