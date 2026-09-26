import { useEffect, useState } from 'react';

const clock = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata', weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false,
});

function Mark() {
  return (
    <svg viewBox="0 0 28 28" width="28" height="28" aria-hidden="true">
      <rect width="28" height="28" rx="6" fill="#2563eb" />
      <path d="M6 10h16M6 14h16M6 18h16" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" opacity=".35" />
      <path d="M6 18c2.5-2 5-2 8 0s5.5 2 8 0" stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round" />
    </svg>
  );
}

export default function Header({ wards, wardId, onWard, apiState, meta }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 15000);
    return () => clearInterval(timer);
  }, []);

  const cities = [...new Set(wards.map((w) => w.city))];

  return (
    <header className="header">
      <div className="brand">
        <Mark />
        <div>
          <div className="brand-name">DrainCast</div>
          <div className="brand-sub">Street-level urban flood nowcasting</div>
        </div>
      </div>

      <div className="header-center">
        <label className="ward-picker">
          <span className="sr-only">Ward</span>
          <select value={wardId || ''} onChange={(e) => onWard(e.target.value)} disabled={!wards.length}>
            {cities.map((city) => (
              <optgroup key={city} label={city}>
                {wards.filter((w) => w.city === city).map((w) => (
                  <option key={w.id} value={w.id}>{w.name}, {w.city}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        {meta && (
          <span className="header-meta">
            <span className="mono">{meta.road_count}</span> road segments · <span className="mono">{meta.drain_count}</span> manholes ·
            drains designed for <span className="mono">{meta.design_intensity} mm/h</span>
          </span>
        )}
      </div>

      <div className="header-right">
        <span className={`status status-${apiState}`}>
          <i />
          {apiState === 'ok' ? 'Model online' : apiState === 'down' ? 'Backend offline' : 'Connecting'}
        </span>
        <span className="header-clock mono">{clock.format(now)} IST</span>
      </div>
    </header>
  );
}
