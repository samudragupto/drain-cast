import { useMemo } from 'react';
import { HIGHWAY_LABELS, riskColor, riskLabel, riskOf, roadName } from '../utils/mapStyles';
import { clockAt, cm, inLabel, lps, offsetLabel, volume } from '../utils/format';

function DepthSparkline({ series, times, frame }) {
  const W = 300;
  const H = 70;
  const top = Math.max(35, ...series) * 1.1;
  const x = (i) => (i / (series.length - 1)) * W;
  const y = (v) => H - (v / top) * H;
  const path = series.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('');
  return (
    <svg viewBox={`0 0 ${W} ${H + 14}`} className="sparkline" role="img" aria-label="Water depth over the next three hours">
      {[5, 15, 30].filter((v) => v < top).map((v) => (
        <g key={v}>
          <line x1="0" x2={W} y1={y(v)} y2={y(v)} className="thr" style={{ stroke: riskColor(riskOf(v)) }} />
          <text x={W - 2} y={y(v) - 2} textAnchor="end" className="axis">{v} cm</text>
        </g>
      ))}
      <path d={`${path}L${W},${H}L0,${H}Z`} className="area" />
      <path d={path} className="line" />
      <line x1={x(frame)} x2={x(frame)} y1="0" y2={H} className="playhead" />
      {[0, 60, 120, 180].map((t) => {
        const i = times.indexOf(t);
        return i < 0 ? null : (
          <text key={t} x={x(i)} y={H + 12} className="axis" textAnchor={i === 0 ? 'start' : i === times.length - 1 ? 'end' : 'middle'}>
            {t ? `+${t / 60}h` : 'Now'}
          </text>
        );
      })}
    </svg>
  );
}

function Row({ label, children, strong }) {
  return (
    <div className={`kv${strong ? ' strong' : ''}`}>
      <span>{label}</span>
      <span className="mono">{children}</span>
    </div>
  );
}

function advice(depth, summary, t, startTime) {
  const risk = riskOf(depth);
  if (risk === 'critical') return 'Close to traffic and pedestrians. Water is above the level where cars stall and manholes may be open.';
  if (risk === 'high') return 'Divert two-wheelers and small cars. Emergency vehicles only, at walking pace.';
  if (summary.t15 !== null && summary.t15 > t) {
    return `Expected to reach 15 cm at ${clockAt(startTime, summary.t15)} (${inLabel(summary.t15 - t)}). Plan the diversion before then.`;
  }
  if (risk === 'moderate') return 'Passable with care. Watch for waterlogging at the kerb and blocked gully gratings.';
  return 'No action needed within the forecast window.';
}

export default function InfoPanel({ ward, sim, frame, roadId, onClose }) {
  const idx = useMemo(() => ward.roads.findIndex((r) => r.id === roadId), [ward, roadId]);
  const road = ward.roads[idx];
  const series = useMemo(() => (sim && idx >= 0 ? sim.frames.map((f) => f.depth[idx]) : []), [sim, idx]);
  if (!road || !sim) return null;

  const t = sim.frames[frame].t;
  const times = sim.frames.map((f) => f.t);
  const depth = series[frame];
  const risk = riskOf(depth);
  const summary = sim.roads[idx];
  const c = ward.meta.runoff_coeff;

  const stepH = sim.step_minutes / 60;
  const rainIdx = sim.rain.times.findIndex((rt) => rt >= t);
  const iNow = sim.rain.intensity[Math.max(0, rainIdx - 1)] ?? 0;
  const fallen = sim.rain.intensity
    .filter((_, i) => sim.rain.times[i] < t)
    .reduce((sum, v) => sum + v * stepH, 0);
  const runoffSoFar = (c * fallen / 1000) * road.catchment_m2;
  const runoffRate = (c * iNow / 3.6e6) * road.catchment_m2 * 1000;

  const nodes = ward.drainage_nodes;
  const nodeIndex = Object.fromEntries(nodes.map((n, i) => [n.id, i]));
  const loads = sim.frames[frame].load;
  const path = [];
  for (let id = road.nearest_drain; id && path.length < 60; id = nodes[nodeIndex[id]]?.downstream) path.push(id);
  const bottleneck = path.find((id) => loads[nodeIndex[id]] > 1);
  const bottleneckPipe = bottleneck && ward.drainage_edges.find((e) => e.from === bottleneck);
  const ownLoad = loads[nodeIndex[road.nearest_drain]] ?? 0;

  return (
    <section className="card panel info-panel">
      <div className="panel-head">
        <div>
          <h2 className="road-title">{roadName(road)}</h2>
          <span className="muted">
            {HIGHWAY_LABELS[road.highway] || road.highway} · {Math.round(road.length_m)} m · {road.width_m} m wide
          </span>
        </div>
        <button type="button" className="icon-btn" onClick={onClose} aria-label="Close road details">×</button>
      </div>

      <div className="depth-now">
        <span className="depth-value mono" style={{ color: riskColor(risk) }}>{cm(depth)}</span>
        <span className={`badge badge-${risk}`}>{riskLabel(risk)}</span>
        <span className="muted">at {offsetLabel(t)} · {clockAt(sim.start_time, t)}</span>
      </div>

      <DepthSparkline series={series} times={times} frame={frame} />

      <p className="advice">{advice(depth, summary, t, sim.start_time)}</p>

      <div className="kv-group">
        <Row label="Peak in window" strong>
          {summary.peak_t === null || summary.peak_depth < 0.5 ? 'dry' : `${cm(summary.peak_depth)} at ${clockAt(sim.start_time, summary.peak_t)}`}
        </Row>
        <Row label="Reaches 15 cm">{summary.t15 === null ? 'not in 3 h' : clockAt(sim.start_time, summary.t15)}</Row>
        <Row label="Reaches 30 cm">{summary.t30 === null ? 'not in 3 h' : clockAt(sim.start_time, summary.t30)}</Row>
      </div>

      <h3 className="sub-head">Why: runoff vs. drainage</h3>
      <div className="kv-group">
        <Row label="Rain right now">{iNow.toFixed(1)} mm/h</Row>
        <Row label="Runoff arriving">{lps(runoffRate)}</Row>
        <Row label="Gully inlet capacity">{lps(road.inlet_capacity_lps)}</Row>
        <Row label="Runoff generated so far">{volume(runoffSoFar)}</Row>
        <Row label="Contributing area">{Math.round(road.catchment_m2).toLocaleString('en-IN')} m²</Row>
        <Row label={`Drains to ${road.nearest_drain}`}>{Math.round(ownLoad * 100)}% loaded</Row>
      </div>
      {bottleneck ? (
        <p className="callout warn">
          Bottleneck downstream at <b>{bottleneck}</b>: {Math.round(loads[nodeIndex[bottleneck]] * 100)}% of capacity
          {bottleneckPipe && ` (${bottleneckPipe.pipe_diameter} mm pipe${bottleneckPipe.legacy ? ', legacy / undersized' : ''}, ${Math.round(bottleneckPipe.condition * 100)}% condition)`}.
          Water backs up and surcharges onto the street.
        </p>
      ) : (
        <p className="callout">
          The pipes between here and the outfall ({path.length} manholes) have spare capacity at this time.
        </p>
      )}

      <h3 className="sub-head">Terrain</h3>
      <div className="kv-group">
        <Row label="Ground level (SRTM)">{road.elevation.toFixed(1)} m</Row>
        <Row label="Relative to ward median">{road.relative_elevation > 0 ? '+' : ''}{road.relative_elevation.toFixed(1)} m</Row>
        <Row label="Gradient">{(road.slope * 100).toFixed(2)}%</Row>
      </div>
      {road.sag && <p className="callout">Local low point: lower than every connecting street, so surface water collects here.</p>}
    </section>
  );
}
