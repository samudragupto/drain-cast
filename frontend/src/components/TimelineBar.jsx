import { clockAt, offsetLabel } from '../utils/format';

const SPEEDS = [1, 2, 4];
const JUMPS = [0, 60, 120, 180];

function PlayIcon({ playing }) {
  return playing ? (
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
      <rect x="3" y="2" width="3.5" height="12" rx="1" fill="currentColor" />
      <rect x="9.5" y="2" width="3.5" height="12" rx="1" fill="currentColor" />
    </svg>
  ) : (
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
      <path d="M4 2.5v11a.8.8 0 0 0 1.2.7l9-5.5a.8.8 0 0 0 0-1.4l-9-5.5A.8.8 0 0 0 4 2.5z" fill="currentColor" />
    </svg>
  );
}

export default function TimelineBar({
  times, frame, onFrame, playing, onTogglePlay, speed, onSpeed, loop, onLoop, startTime, busy,
}) {
  if (!times.length) return null;
  const t = times[frame] ?? 0;
  const last = times.length - 1;
  const stepMin = times[1] - times[0] || 5;

  return (
    <div className="timeline card">
      <button type="button" className="play-btn" onClick={onTogglePlay} title="Play / pause (Space)">
        <PlayIcon playing={playing} />
        <span>{playing ? 'Pause' : 'Play'}</span>
      </button>

      <div className="timeline-main">
        <div className="timeline-head">
          <span className="timeline-offset mono">{offsetLabel(t)}</span>
          <span className="timeline-clock mono">{clockAt(startTime, t)} IST</span>
          {busy && <span className="timeline-busy">updating…</span>}
        </div>
        <input
          type="range"
          className="timeline-range"
          min={0}
          max={last}
          step={1}
          value={frame}
          onChange={(e) => onFrame(Number(e.target.value))}
          aria-label="Forecast time"
          style={{ '--fill': `${(frame / last) * 100}%` }}
        />
        <div className="timeline-jumps">
          {JUMPS.map((m) => {
            const idx = Math.round(m / stepMin);
            return (
              <button
                key={m}
                type="button"
                className={`jump${frame === idx ? ' active' : ''}`}
                onClick={() => onFrame(idx)}
              >
                {m === 0 ? 'Now' : `+${m / 60} h`}
              </button>
            );
          })}
        </div>
      </div>

      <div className="timeline-side">
        <div className="seg-control small" role="group" aria-label="Playback speed">
          {SPEEDS.map((s) => (
            <button key={s} type="button" className={speed === s ? 'active' : ''} onClick={() => onSpeed(s)}>
              {s}×
            </button>
          ))}
        </div>
        <label className="check small">
          <input type="checkbox" checked={loop} onChange={(e) => onLoop(e.target.checked)} />
          Loop
        </label>
      </div>
    </div>
  );
}
