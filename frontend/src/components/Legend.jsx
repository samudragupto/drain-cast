import { useState } from 'react';
import { DRAIN_STYLES, RISK_LEVELS } from '../utils/mapStyles';

export default function Legend({ showDrains, showPipes, onToggleDrains, onTogglePipes }) {
  const [open, setOpen] = useState(() => window.innerWidth >= 1200);

  return (
    <div className={`legend card${open ? '' : ' closed'}`}>
      <button type="button" className="legend-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
        Legend <span aria-hidden="true">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="legend-body">
          <div className="legend-title">Standing water</div>
          {RISK_LEVELS.map((r) => (
            <div key={r.key} className="legend-row">
              <i className="swatch-line" style={{ background: r.color }} />
              <span>{r.label}</span>
              <span className="mono muted">{r.range}</span>
            </div>
          ))}

          <div className="legend-title">Drainage</div>
          {['normal', 'near', 'surcharged', 'outfall'].map((key) => (
            <div key={key} className="legend-row">
              <i className="swatch-dot" style={{ background: DRAIN_STYLES[key].fillColor }} />
              <span>{DRAIN_STYLES[key].label}</span>
            </div>
          ))}

          <div className="legend-title">Routes</div>
          <div className="legend-row"><i className="swatch-route safe" /><span>Flood-aware</span></div>
          <div className="legend-row"><i className="swatch-route plain" /><span>Shortest</span></div>

          <div className="legend-toggles">
            <label className="check small">
              <input type="checkbox" checked={showDrains} onChange={(e) => onToggleDrains(e.target.checked)} /> Manholes
            </label>
            <label className="check small">
              <input type="checkbox" checked={showPipes} onChange={(e) => onTogglePipes(e.target.checked)} /> Pipe network
            </label>
          </div>
        </div>
      )}
    </div>
  );
}
