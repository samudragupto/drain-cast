import { useMemo } from 'react';
import { RISK_LEVELS, riskColor, riskOf, roadName } from '../utils/mapStyles';
import { clockAt, cm, inLabel, offsetLabel } from '../utils/format';

function groupByName(indices, roads, depthOf) {
  const groups = new Map();
  indices.forEach((i) => {
    const road = roads[i];
    const key = road.name || road.label || road.id;
    const d = depthOf(i);
    const cur = groups.get(key);
    if (!cur || d > cur.depth) groups.set(key, { idx: i, depth: d, road, count: (cur?.count || 0) + 1 });
    else cur.count += 1;
  });
  return [...groups.values()];
}

export default function SummaryPanel({ ward, sim, frame, onPickRoad, selectedId }) {
  const stats = sim?.stats[frame];
  const t = sim?.frames[frame]?.t ?? 0;
  const depths = sim?.frames[frame]?.depth;

  const { hotspots, upcoming } = useMemo(() => {
    if (!sim || !ward || !depths) return { hotspots: [], upcoming: [] };
    const wet = [];
    const next = [];
    depths.forEach((d, i) => {
      if (d >= 5) wet.push(i);
      const t15 = sim.roads[i].t15;
      if (d < 15 && t15 !== null && t15 > t) next.push(i);
    });
    const hot = groupByName(wet, ward.roads, (i) => depths[i]).sort((a, b) => b.depth - a.depth).slice(0, 6);
    const soon = groupByName(next, ward.roads, (i) => -sim.roads[i].t15)
      .map((g) => ({ ...g, t15: sim.roads[g.idx].t15 }))
      .sort((a, b) => a.t15 - b.t15)
      .slice(0, 4);
    return { hotspots: hot, upcoming: soon };
  }, [sim, ward, depths, t]);

  if (!stats || !ward) return null;
  const total = ward.roads.length;
  const unsafe = stats.counts.high + stats.counts.critical;

  return (
    <section className="card panel">
      <div className="panel-head">
        <h2>Situation at {offsetLabel(t)}</h2>
        <span className="muted mono">{clockAt(sim.start_time, t)} IST</span>
      </div>

      <div className="kpis">
        <div className="kpi">
          <span className="kpi-value mono" style={{ color: unsafe ? '#c2410c' : undefined }}>{unsafe}</span>
          <span className="kpi-label">road segments ≥ 15 cm</span>
        </div>
        <div className="kpi">
          <span className="kpi-value mono">{stats.flooded_km.toFixed(1)}<small> km</small></span>
          <span className="kpi-label">flooded length</span>
        </div>
        <div className="kpi">
          <span className="kpi-value mono">{Math.round(stats.max_depth)}<small> cm</small></span>
          <span className="kpi-label">deepest point</span>
        </div>
        <div className="kpi">
          <span className="kpi-value mono">{stats.surcharged}<small> / {ward.drainage_nodes.length}</small></span>
          <span className="kpi-label">drains overloaded</span>
        </div>
      </div>

      <div className="risk-bar" aria-label="Road segments by risk level">
        {RISK_LEVELS.map((r) => (
          <span
            key={r.key}
            style={{ width: `${(stats.counts[r.key] / total) * 100}%`, background: r.color }}
            title={`${r.label}: ${stats.counts[r.key]} segments`}
          />
        ))}
      </div>
      <div className="risk-bar-legend">
        {RISK_LEVELS.map((r) => (
          <span key={r.key}><i style={{ background: r.color }} />{r.label} <b className="mono">{stats.counts[r.key]}</b></span>
        ))}
      </div>

      <h3 className="sub-head">Worst-hit streets</h3>
      {hotspots.length === 0 ? (
        <p className="hint">No street has more than 5 cm of standing water at this time.</p>
      ) : (
        <ul className="hot-list">
          {hotspots.map((h) => (
            <li key={h.idx}>
              <button
                type="button"
                className={ward.roads[h.idx].id === selectedId ? 'active' : ''}
                onClick={() => onPickRoad(ward.roads[h.idx].id)}
              >
                <i style={{ background: riskColor(riskOf(h.depth)) }} />
                <span className="hot-name">
                  {roadName(h.road)}
                  {h.count > 1 && <span className="muted"> · {h.count} segments</span>}
                </span>
                <span className="mono hot-depth">{cm(h.depth)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {upcoming.length > 0 && (
        <>
          <h3 className="sub-head">Next to cross 15 cm</h3>
          <ul className="hot-list compact">
            {upcoming.map((u) => (
              <li key={u.idx}>
                <button type="button" onClick={() => onPickRoad(ward.roads[u.idx].id)}>
                  <i style={{ background: riskColor('high') }} />
                  <span className="hot-name">{roadName(u.road)}</span>
                  <span className="mono hot-depth">{inLabel(u.t15 - t)}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
