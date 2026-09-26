import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Header from './components/Header';
import FloodMap from './components/Map';
import TimelineBar from './components/TimelineBar';
import Legend from './components/Legend';
import ControlPanel from './components/ControlPanel';
import SummaryPanel from './components/SummaryPanel';
import InfoPanel from './components/InfoPanel';
import RoutePanel from './components/RoutePanel';
import { api } from './utils/api';
import { labelUnnamedRoads } from './utils/mapStyles';

const DEFAULT_SCENARIO = { mode: 'scenario', pattern: 'burst', intensity: 75, backwater: false };
const FRAME_MS = 650;
const LIVE_REFRESH_MS = 10 * 60 * 1000;
const EMPTY_ROUTE = { start: null, end: null, pick: null, result: null, loading: false, error: null };

function readStored(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function writeStored(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // storage unavailable (private mode); preferences just won't persist
  }
}

export default function App() {
  const [index, setIndex] = useState(null);
  const [apiState, setApiState] = useState('connecting');
  const [retry, setRetry] = useState(0);
  const [wardId, setWardId] = useState(() => readStored('draincast.ward', null));
  const [ward, setWard] = useState(null);
  const [scenario, setScenario] = useState(() => ({ ...DEFAULT_SCENARIO, ...readStored('draincast.scenario', {}) }));
  const [sim, setSim] = useState(null);
  const [simBusy, setSimBusy] = useState(false);
  const [error, setError] = useState(null);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [loop, setLoop] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [focus, setFocus] = useState(null);
  const [showDrains, setShowDrains] = useState(true);
  const [showPipes, setShowPipes] = useState(false);
  const [routeState, setRouteState] = useState(EMPTY_ROUTE);
  const [liveTick, setLiveTick] = useState(0);
  const sidebarRef = useRef(null);

  // ward list; keeps retrying while the backend is down
  useEffect(() => {
    let cancelled = false;
    let timer;
    api.wards()
      .then((data) => {
        if (cancelled) return;
        setIndex(data);
        setApiState('ok');
        setError(null);
        setWardId((cur) => (data.wards.some((w) => w.id === cur) ? cur : data.wards[0]?.id));
      })
      .catch((err) => {
        if (cancelled) return;
        setApiState('down');
        setError(err.message);
        timer = setTimeout(() => setRetry((r) => r + 1), 5000);
      });
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [retry]);

  // ward geometry
  useEffect(() => {
    if (!wardId || !index) return undefined;
    writeStored('draincast.ward', wardId);
    const ctrl = new AbortController();
    setSim(null);
    setSelectedId(null);
    setRouteState(EMPTY_ROUTE);
    api.ward(wardId, ctrl.signal)
      .then((data) => setWard({ ...data, roads: labelUnnamedRoads(data.roads) }))
      .catch((err) => err.name !== 'AbortError' && setError(err.message));
    return () => ctrl.abort();
  }, [wardId, index]);

  useEffect(() => writeStored('draincast.scenario', scenario), [scenario]);

  // re-run the model whenever the ward or rainfall input changes (debounced for the slider)
  useEffect(() => {
    if (!ward) return undefined;
    const ctrl = new AbortController();
    const timer = setTimeout(async () => {
      setSimBusy(true);
      try {
        const data = await api.simulate({ ward: ward.meta.id, ...scenario }, ctrl.signal);
        setSim(data);
        setError(null);
        setApiState('ok');
      } catch (err) {
        if (err.name === 'AbortError') return;
        setError(err.message);
        if (scenario.mode === 'live') setScenario((s) => ({ ...s, mode: 'scenario' }));
      } finally {
        if (!ctrl.signal.aborted) setSimBusy(false);
      }
    }, 200);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [ward, scenario, liveTick]);

  useEffect(() => {
    if (scenario.mode !== 'live') return undefined;
    const timer = setInterval(() => setLiveTick((n) => n + 1), LIVE_REFRESH_MS);
    return () => clearInterval(timer);
  }, [scenario.mode]);

  const lastFrame = sim ? sim.frames.length - 1 : 0;
  useEffect(() => setFrame((f) => Math.min(f, lastFrame)), [lastFrame]);

  // automatic time stepping
  useEffect(() => {
    if (!playing || !sim) return undefined;
    const timer = setInterval(() => {
      setFrame((f) => (f >= lastFrame ? (loop ? 0 : f) : f + 1));
    }, FRAME_MS / speed);
    return () => clearInterval(timer);
  }, [playing, speed, loop, sim, lastFrame]);

  useEffect(() => {
    if (playing && !loop && frame >= lastFrame) setPlaying(false);
  }, [playing, loop, frame, lastFrame]);

  const togglePlay = useCallback(() => {
    if (!playing && frame >= lastFrame) setFrame(0);
    setPlaying((p) => !p);
  }, [playing, frame, lastFrame]);

  useEffect(() => {
    const onKey = (e) => {
      if (['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(e.target.tagName)) return;
      if (e.code === 'Space') {
        e.preventDefault();
        togglePlay();
      } else if (e.key === 'ArrowRight') {
        setFrame((f) => Math.min(lastFrame, f + 1));
      } else if (e.key === 'ArrowLeft') {
        setFrame((f) => Math.max(0, f - 1));
      } else if (e.key === 'Escape') {
        setSelectedId(null);
        setRouteState((r) => ({ ...r, pick: null }));
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [togglePlay, lastFrame]);

  // routing follows the timeline: the answer changes as streets flood and drain
  const { start, end } = routeState;
  useEffect(() => {
    if (!start || !end || !sim || !ward) return undefined;
    const ctrl = new AbortController();
    const timer = setTimeout(async () => {
      setRouteState((r) => ({ ...r, loading: true, error: null }));
      try {
        const result = await api.route({ ward: ward.meta.id, ...scenario, start, end, frame }, ctrl.signal);
        setRouteState((r) => ({ ...r, result, loading: false }));
      } catch (err) {
        if (err.name !== 'AbortError') setRouteState((r) => ({ ...r, result: null, loading: false, error: err.message }));
      }
    }, 150);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
    // scenario is captured through sim, which changes whenever the scenario does
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [start, end, frame, sim, ward]);

  const handlePick = useCallback((latlng) => {
    setRouteState((r) => {
      if (r.pick === 'start') return { ...r, start: latlng, pick: r.end ? null : 'end', result: r.end ? r.result : null };
      if (r.pick === 'end') return { ...r, end: latlng, pick: null };
      return r;
    });
  }, []);

  const selectRoad = useCallback((id, zoom = false) => {
    setSelectedId(id);
    if (zoom) setFocus({ id, at: Date.now() });
    sidebarRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  const routePoints = useMemo(() => ({ start, end }), [start, end]);
  const meta = ward?.meta;
  const current = sim?.frames[frame];
  const t = current?.t ?? 0;

  return (
    <div className="app">
      <Header
        wards={index?.wards || []}
        wardId={wardId}
        onWard={setWardId}
        apiState={apiState}
        meta={meta}
      />

      {error && (
        <div className="banner" role="alert">
          <span>{error}</span>
          <button type="button" className="btn ghost small" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      <main className="layout">
        <div className="map-area">
          <FloodMap
            ward={ward}
            depths={current?.depth}
            loads={current?.load}
            selectedId={selectedId}
            onSelectRoad={selectRoad}
            focus={focus}
            showDrains={showDrains}
            showPipes={showPipes}
            route={routeState.result}
            routePoints={routePoints}
            pickMode={routeState.pick}
            onPick={handlePick}
          />
          <Legend
            showDrains={showDrains}
            showPipes={showPipes}
            onToggleDrains={setShowDrains}
            onTogglePipes={setShowPipes}
          />
          {sim && (
            <TimelineBar
              times={sim.frames.map((f) => f.t)}
              frame={frame}
              onFrame={(f) => {
                setFrame(f);
                setPlaying(false);
              }}
              playing={playing}
              onTogglePlay={togglePlay}
              speed={speed}
              onSpeed={setSpeed}
              loop={loop}
              onLoop={setLoop}
              startTime={sim.start_time}
              busy={simBusy}
            />
          )}
          {(!ward || (!sim && simBusy)) && apiState !== 'down' && (
            <div className="map-loading">{ward ? `Running model for ${ward.meta.name}…` : 'Loading ward…'}</div>
          )}
        </div>

        <aside className="sidebar" ref={sidebarRef}>
          {selectedId && ward && sim && (
            <InfoPanel ward={ward} sim={sim} frame={frame} roadId={selectedId} onClose={() => setSelectedId(null)} />
          )}
          <ControlPanel
            scenario={scenario}
            onChange={setScenario}
            patterns={index?.patterns || {}}
            meta={meta}
            rain={sim?.rain}
            currentT={t}
            onRefreshLive={() => setLiveTick((n) => n + 1)}
          />
          <SummaryPanel ward={ward} sim={sim} frame={frame} selectedId={selectedId} onPickRoad={(id) => selectRoad(id, true)} />
          <RoutePanel
            state={routeState}
            t={t}
            onPick={(pick) => setRouteState((r) => ({ ...r, pick }))}
            onClear={() => setRouteState(EMPTY_ROUTE)}
          />
          <section className="card panel about">
            <h2>About this model</h2>
            {meta && <p>{meta.notes}</p>}
            <p>
              Roads: OpenStreetMap. Terrain: SRTM 30 m. Rain: design storms or Open-Meteo. Municipal drain maps are
              not public, so the drain network is synthesised along the streets and sized to the ward&apos;s design
              standard, then de-rated for silt. Treat depths as a ranking of risk, not a survey.
            </p>
            <p className="muted">Keys: Space play/pause · ← → step 5 min · Esc clear selection</p>
          </section>
        </aside>
      </main>
    </div>
  );
}
