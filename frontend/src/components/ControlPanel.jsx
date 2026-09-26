import RainChart from './RainChart';

const PATTERN_LABELS = {
  steady: 'Steady',
  building: 'Building',
  burst: 'Cloudburst',
  passing: 'Passing',
};

const PRESETS = [
  { label: 'Moderate', value: 20 },
  { label: 'Heavy', value: 45 },
  { label: 'Very heavy', value: 75 },
  { label: 'Extreme', value: 120 },
];

export default function ControlPanel({
  scenario, onChange, patterns, meta, rain, currentT, onRefreshLive,
}) {
  const set = (patch) => onChange({ ...scenario, ...patch });
  const live = scenario.mode === 'live';
  const upcoming = rain ? rain.intensity.filter((_, i) => rain.times[i] >= 0) : [];
  const livePeak = upcoming.length ? Math.max(...upcoming) : 0;

  return (
    <section className="card panel">
      <div className="panel-head">
        <h2>Rainfall input</h2>
        <div className="seg-control" role="tablist" aria-label="Rainfall source">
          <button type="button" className={!live ? 'active' : ''} onClick={() => set({ mode: 'scenario' })}>
            Design storm
          </button>
          <button type="button" className={live ? 'active' : ''} onClick={() => set({ mode: 'live' })}>
            Live forecast
          </button>
        </div>
      </div>

      {!live && (
        <>
          <div className="field">
            <span className="field-label">Storm shape</span>
            <div className="seg-control full">
              {Object.keys(patterns).map((p) => (
                <button
                  key={p}
                  type="button"
                  title={patterns[p]}
                  className={scenario.pattern === p ? 'active' : ''}
                  onClick={() => set({ pattern: p })}
                >
                  {PATTERN_LABELS[p] || p}
                </button>
              ))}
            </div>
            <p className="hint">{patterns[scenario.pattern]}</p>
          </div>

          <div className="field">
            <div className="field-row">
              <span className="field-label">{scenario.pattern === 'steady' ? 'Intensity' : 'Peak intensity'}</span>
              <span className="value mono">{scenario.intensity} mm/h</span>
            </div>
            <input
              type="range"
              min={5}
              max={150}
              step={5}
              value={scenario.intensity}
              onChange={(e) => set({ intensity: Number(e.target.value) })}
              style={{ '--fill': `${((scenario.intensity - 5) / 145) * 100}%` }}
              aria-label="Rainfall intensity in millimetres per hour"
            />
            <div className="chips">
              {PRESETS.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  className={`chip${scenario.intensity === p.value ? ' active' : ''}`}
                  onClick={() => set({ intensity: p.value })}
                >
                  {p.label} <span className="mono">{p.value}</span>
                </button>
              ))}
            </div>
          </div>
        </>
      )}

      {live && (
        <div className="live-box">
          {rain?.source ? (
            <>
              <div className="field-row">
                <span className="field-label">Peak in next 3 h</span>
                <span className="value mono">{livePeak.toFixed(1)} mm/h</span>
              </div>
              <p className="hint">
                {rain.source}. Issued {rain.issued?.slice(11, 16)} IST. Model output rather than radar,
                so treat short bursts with caution. Refreshes every 10 minutes.
              </p>
              {livePeak < 1 && (
                <p className="notice">
                  No meaningful rain is forecast for {meta?.name} right now. Switch to a design storm to explore
                  how the ward responds.
                </p>
              )}
              <button type="button" className="btn ghost small" onClick={onRefreshLive}>Refresh now</button>
            </>
          ) : (
            <p className="hint">Fetching Open-Meteo forecast…</p>
          )}
        </div>
      )}

      <label className="check" title="Outfalls discharge at half capacity">
        <input type="checkbox" checked={scenario.backwater} onChange={(e) => set({ backwater: e.target.checked })} />
        <span>
          Outfalls blocked by {meta?.city === 'Mumbai' ? 'high tide' : 'high river / canal level'}
          <span className="hint block">Outfalls pass only 50% of capacity ({meta?.outfall_kind})</span>
        </span>
      </label>

      {rain && meta && (
        <RainChart
          times={rain.times}
          intensity={rain.intensity}
          currentT={currentT}
          designIntensity={meta.design_intensity}
        />
      )}
    </section>
  );
}
