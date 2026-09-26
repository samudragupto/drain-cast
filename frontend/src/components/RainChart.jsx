const W = 320;
const H = 116;
const PAD = { l: 28, r: 8, t: 10, b: 20 };

export default function RainChart({ times, intensity, currentT, designIntensity }) {
  if (!times?.length) return null;
  const step = times[1] - times[0];
  const t0 = times[0];
  const t1 = times[times.length - 1] + step;
  const top = Math.max(10, designIntensity * 1.4, ...intensity) * 1.05;
  const x = (t) => PAD.l + ((t - t0) / (t1 - t0)) * (W - PAD.l - PAD.r);
  const y = (v) => H - PAD.b - (v / top) * (H - PAD.t - PAD.b);
  const bw = Math.max(1, x(t0 + step) - x(t0) - 1);
  const ticks = [0, Math.round(top / 2), Math.round(top)];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="rain-chart" role="img" aria-label="Rainfall intensity over time">
      {ticks.map((v) => (
        <g key={v}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} className="grid" />
          <text x={PAD.l - 4} y={y(v) + 3} className="axis" textAnchor="end">{v}</text>
        </g>
      ))}
      <rect x={x(t0)} y={PAD.t} width={x(0) - x(t0)} height={H - PAD.t - PAD.b} className="past" />
      {intensity.map((v, i) => (
        <rect
          key={times[i]}
          x={x(times[i]) + 0.5}
          y={y(v)}
          width={bw}
          height={Math.max(0, H - PAD.b - y(v))}
          className={times[i] < currentT ? 'bar done' : 'bar'}
        />
      ))}
      <line x1={PAD.l} x2={W - PAD.r} y1={y(designIntensity)} y2={y(designIntensity)} className="design" />
      <text x={W - PAD.r} y={y(designIntensity) - 4} className="design-label" textAnchor="end">
        drain design {designIntensity} mm/h
      </text>
      <line x1={x(currentT)} x2={x(currentT)} y1={PAD.t - 4} y2={H - PAD.b} className="playhead" />
      {[t0, 0, 60, 120, 180].map((t) => (
        <text key={t} x={x(t)} y={H - 5} className="axis" textAnchor={t === t0 ? 'start' : t === 180 ? 'end' : 'middle'}>
          {t === 0 ? 'Now' : t < 0 ? `−${-t}m` : `+${t / 60}h`}
        </text>
      ))}
    </svg>
  );
}
