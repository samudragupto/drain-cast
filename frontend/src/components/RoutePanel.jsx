import { cm, offsetLabel } from '../utils/format';

function RouteStats({ label, route, tone }) {
  return (
    <div className={`route-col ${tone}`}>
      <span className="route-label"><i />{label}</span>
      <span className="route-big mono">{route.length_km.toFixed(2)} km</span>
      <span className="mono">~{Math.round(route.minutes)} min</span>
      <span className={route.flooded_segments ? 'bad' : 'good'}>
        {route.flooded_segments ? `${route.flooded_segments} flooded segments` : 'no segment ≥ 15 cm'}
      </span>
      <span className="muted">max depth <span className="mono">{cm(route.max_depth)}</span></span>
    </div>
  );
}

export default function RoutePanel({ state, onPick, onClear, t }) {
  const { start, end, pick, result, loading, error } = state;
  const { normal, safe } = result || {};

  return (
    <section className="card panel">
      <div className="panel-head">
        <h2>Flood-aware routing</h2>
        {(start || end) && (
          <button type="button" className="btn ghost small" onClick={onClear}>Clear</button>
        )}
      </div>
      <p className="hint">
        For ambulances, fire tenders and patrol vehicles. Roads over 30 cm are treated as closed; 15–30 cm is
        heavily penalised.
      </p>

      <div className="pick-row">
        <button type="button" className={`btn pick${pick === 'start' ? ' active' : ''}`} onClick={() => onPick(pick === 'start' ? null : 'start')}>
          <span className="pin pin-a small">A</span>
          {start ? 'Move start' : 'Set start'}
        </button>
        <button type="button" className={`btn pick${pick === 'end' ? ' active' : ''}`} onClick={() => onPick(pick === 'end' ? null : 'end')}>
          <span className="pin pin-b small">B</span>
          {end ? 'Move destination' : 'Set destination'}
        </button>
      </div>

      {loading && <p className="hint">Routing at {offsetLabel(t)}…</p>}
      {error && <p className="callout warn">{error}</p>}

      {normal && (
        <>
          <div className="route-compare">
            <RouteStats label="Shortest" route={normal} tone="plain" />
            {safe ? (
              <RouteStats label="Flood-aware" route={safe} tone="safe" />
            ) : (
              <div className="route-col blocked">
                <span className="route-label">Flood-aware</span>
                <span className="bad">No route below 30 cm exists at {offsetLabel(t)}.</span>
                <span className="muted">Scrub the timeline to find when the corridor reopens.</span>
              </div>
            )}
          </div>
          {result.same_route && <p className="callout">The shortest route is already the safest at this time.</p>}
          {safe && !result.same_route && normal.flooded_roads.length > 0 && (
            <div className="avoided">
              <span className="sub-head">Avoids</span>
              <ul>
                {normal.flooded_roads.slice(0, 5).map((r) => (
                  <li key={r.name}><span>{r.name}</span><span className="mono">{cm(r.depth)}</span></li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
      {!normal && !loading && !error && (start || end) && (
        <p className="hint">Now set {start ? 'the destination (B)' : 'the start (A)'} on the map.</p>
      )}
    </section>
  );
}
