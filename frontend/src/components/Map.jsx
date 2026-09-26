import { useEffect, useRef } from 'react';
import L from 'leaflet';
import {
  DRAIN_STYLES, drainState, riskColor, riskLabel, riskOf, roadName, roadStyle,
} from '../utils/mapStyles';
import { cm } from '../utils/format';

const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services';
const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

function basemaps() {
  const light = L.layerGroup([
    L.tileLayer(`${ESRI}/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}`, {
      maxNativeZoom: 16, maxZoom: 20, attribution: 'Basemap &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors',
    }),
    L.tileLayer(`${ESRI}/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}`, {
      maxNativeZoom: 16, maxZoom: 20,
    }),
  ]);
  const streets = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxNativeZoom: 19, maxZoom: 20, attribution: OSM_ATTRIBUTION,
  });
  return { 'Light (data first)': light, 'Streets (OSM)': streets };
}

const escapeHtml = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function wardBounds(meta) {
  const [s, w, n, e] = meta.bbox;
  return L.latLngBounds([s, w], [n, e]);
}

export default function FloodMap({
  ward, depths, loads, selectedId, onSelectRoad, focus,
  showDrains, showPipes, route, routePoints, pickMode, onPick,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const layers = useRef({ roads: new Map(), drains: [] });
  const latest = useRef({});
  latest.current = { depths, loads, onSelectRoad, onPick, pickMode, ward };

  // map instance, created once
  useEffect(() => {
    const map = L.map(containerRef.current, {
      zoomControl: false,
      preferCanvas: true,
      minZoom: 11,
      maxZoom: 19,
      zoomSnap: 0.25,
    });
    map.setView([16.5, 76.5], 6);
    L.control.zoom({ position: 'topright' }).addTo(map);
    L.control.scale({ imperial: false, position: 'bottomright' }).addTo(map);
    const bases = basemaps();
    bases['Light (data first)'].addTo(map);
    L.control.layers(bases, null, { position: 'topright' }).addTo(map);
    map.attributionControl.addAttribution('Roads: ' + OSM_ATTRIBUTION + ' · Terrain: SRTM');

    map.createPane('pipes').style.zIndex = 420;
    map.createPane('route').style.zIndex = 440;
    map.createPane('drains').style.zIndex = 450;

    map.on('click', (e) => {
      const { pickMode: mode, onPick: pick } = latest.current;
      if (mode) pick([e.latlng.lat, e.latlng.lng]);
    });

    const observer = new ResizeObserver(() => map.invalidateSize({ pan: false }));
    observer.observe(containerRef.current);
    mapRef.current = map;
    return () => {
      observer.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // static ward geometry: rebuilt only when the ward changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ward) return undefined;
    const store = layers.current;

    const roadRenderer = L.canvas({ padding: 0.4, tolerance: 5 });
    const roadGroup = L.layerGroup();
    const roads = new Map();
    ward.roads.forEach((road, idx) => {
      const line = L.polyline(
        road.coordinates.map(([lon, lat]) => [lat, lon]),
        { ...roadStyle(road.highway, 'low'), renderer: roadRenderer },
      );
      line.meta = { idx, id: road.id, highway: road.highway, risk: 'low', selected: false };
      line.bindTooltip(() => {
        const d = latest.current.depths?.[idx] ?? 0;
        const risk = riskOf(d);
        return `<div class="tip-name">${escapeHtml(roadName(road))}</div>
          <div class="tip-row"><span class="tip-dot" style="background:${riskColor(risk)}"></span>
          <span class="mono">${cm(d)}</span> &middot; ${riskLabel(risk)}</div>`;
      }, { sticky: true, direction: 'top', offset: [0, -8], className: 'map-tip' });
      line.on('click', (e) => {
        if (latest.current.pickMode) return;
        L.DomEvent.stopPropagation(e);
        latest.current.onSelectRoad(road.id);
      });
      roadGroup.addLayer(line);
      roads.set(road.id, line);
    });
    roadGroup.addTo(map);

    const pipeGroup = L.layerGroup();
    const nodeById = Object.fromEntries(ward.drainage_nodes.map((n) => [n.id, n]));
    const pipeRenderer = L.canvas({ pane: 'pipes' });
    ward.drainage_edges.forEach((edge) => {
      const a = nodeById[edge.from];
      const b = nodeById[edge.to];
      if (!a || !b) return;
      L.polyline([[a.location[1], a.location[0]], [b.location[1], b.location[0]]], {
        renderer: pipeRenderer,
        color: edge.legacy ? '#7c3aed' : '#1d4ed8',
        weight: 1 + edge.pipe_diameter / 700,
        opacity: 0.55,
        dashArray: edge.legacy ? '4 4' : null,
        interactive: false,
      }).addTo(pipeGroup);
    });

    const drainGroup = L.layerGroup();
    const drainRenderer = L.canvas({ pane: 'drains', tolerance: 4 });
    const drains = ward.drainage_nodes.map((node, i) => {
      const style = DRAIN_STYLES[node.type === 'outfall' ? 'outfall' : 'normal'];
      const marker = L.circleMarker([node.location[1], node.location[0]], {
        renderer: drainRenderer,
        radius: node.type === 'outfall' ? 6 : 3.6,
        weight: 1.2,
        fillOpacity: 0.95,
        ...style,
      });
      marker.state = node.type === 'outfall' ? 'outfall' : 'normal';
      marker.bindTooltip(() => {
        const load = latest.current.loads?.[i] ?? 0;
        const state = DRAIN_STYLES[drainState(node, load)].label;
        return `<div class="tip-name">${node.id} &middot; ${node.type}</div>
          <div class="tip-row">Pipe capacity <span class="mono">${Math.round(node.capacity)} L/s</span></div>
          <div class="tip-row">Load <span class="mono">${Math.round(load * 100)}%</span> &middot; ${state}</div>`;
      }, { direction: 'top', offset: [0, -4], className: 'map-tip' });
      marker.on('click', (e) => {
        if (!latest.current.pickMode) L.DomEvent.stopPropagation(e);
      });
      drainGroup.addLayer(marker);
      return marker;
    });

    const boundary = L.rectangle(wardBounds(ward.meta), {
      color: '#334155', weight: 1.5, dashArray: '6 6', fill: false, interactive: false,
    }).addTo(map);

    const halo = L.layerGroup().addTo(map);

    Object.assign(store, { roadGroup, roads, pipeGroup, drainGroup, drains, boundary, halo });

    const bounds = wardBounds(ward.meta);
    map.setMaxBounds(bounds.pad(1.2));
    if (store.fitted) {
      map.flyToBounds(bounds, { padding: [24, 24], duration: 0.8 });
    } else {
      map.fitBounds(bounds, { padding: [24, 24], animate: false });
      store.fitted = true;
    }

    return () => {
      [roadGroup, pipeGroup, drainGroup, boundary, halo].forEach((layer) => map.removeLayer(layer));
      store.roads = new Map();
      store.drains = [];
    };
  }, [ward]);

  // road colours follow the current frame
  useEffect(() => {
    const { roads } = layers.current;
    if (!roads) return;
    roads.forEach((line) => {
      const { idx, highway } = line.meta;
      const risk = riskOf(depths?.[idx] ?? 0);
      const selected = line.meta.id === selectedId;
      if (risk !== line.meta.risk || selected !== line.meta.selected) {
        line.setStyle(roadStyle(highway, risk, selected));
        line.meta.risk = risk;
        line.meta.selected = selected;
        if (risk !== 'low' || selected) line.bringToFront();
      }
    });
  }, [depths, selectedId, ward]);

  // selection halo
  useEffect(() => {
    const { halo, roads } = layers.current;
    if (!halo) return;
    halo.clearLayers();
    const line = selectedId && roads.get(selectedId);
    if (line) {
      L.polyline(line.getLatLngs(), {
        color: '#0f172a', weight: line.options.weight + 6, opacity: 0.25, interactive: false,
      }).addTo(halo);
      line.bringToFront();
    }
  }, [selectedId, ward]);

  // manhole states follow the current frame
  useEffect(() => {
    const { drains } = layers.current;
    if (!drains || !ward) return;
    drains.forEach((marker, i) => {
      const state = drainState(ward.drainage_nodes[i], loads?.[i] ?? 0);
      if (state !== marker.state) {
        marker.setStyle(DRAIN_STYLES[state]);
        marker.setRadius(ward.drainage_nodes[i].type === 'outfall' ? 6 : state === 'surcharged' ? 5 : 3.6);
        marker.state = state;
      }
    });
  }, [loads, ward]);

  // layer toggles
  useEffect(() => {
    const map = mapRef.current;
    const { drainGroup, pipeGroup } = layers.current;
    if (!map || !drainGroup) return;
    if (showDrains) drainGroup.addTo(map); else map.removeLayer(drainGroup);
    if (showPipes) pipeGroup.addTo(map); else map.removeLayer(pipeGroup);
  }, [showDrains, showPipes, ward]);

  // zoom to a road when asked (hotspot list, search)
  useEffect(() => {
    const map = mapRef.current;
    const line = focus && layers.current.roads.get(focus.id);
    if (map && line) map.flyToBounds(line.getBounds(), { maxZoom: 17, padding: [120, 120], duration: 0.6 });
  }, [focus]);

  // routes and A/B pins
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return undefined;
    const group = L.layerGroup().addTo(map);
    if (route?.normal && !route.same_route) {
      L.polyline(route.normal.coordinates, {
        pane: 'route', color: '#334155', weight: 4, opacity: 0.85, dashArray: '2 9', lineCap: 'round',
      }).bindTooltip('Shortest route', { sticky: true, className: 'map-tip' }).addTo(group);
    }
    const best = route?.safe || (route?.same_route ? route.normal : null);
    if (best) {
      L.polyline(best.coordinates, { pane: 'route', color: '#ffffff', weight: 10, opacity: 0.9, interactive: false }).addTo(group);
      L.polyline(best.coordinates, { pane: 'route', color: '#2563eb', weight: 5.5, opacity: 1 })
        .bindTooltip('Flood-aware route', { sticky: true, className: 'map-tip' })
        .addTo(group);
    }
    [['start', 'A'], ['end', 'B']].forEach(([key, label]) => {
      const p = routePoints?.[key];
      if (!p) return;
      L.marker(p, {
        icon: L.divIcon({ className: '', html: `<div class="pin pin-${label.toLowerCase()}">${label}</div>`, iconSize: [26, 26], iconAnchor: [13, 13] }),
        keyboard: false,
        interactive: false,
      }).addTo(group);
    });
    return () => map.removeLayer(group);
  }, [route, routePoints]);

  const fitWard = () => {
    const map = mapRef.current;
    if (map && ward) map.flyToBounds(wardBounds(ward.meta), { padding: [24, 24], duration: 0.6 });
  };

  return (
    <div className={`map-wrap${pickMode ? ' picking' : ''}`}>
      <div ref={containerRef} className="map" />
      <button type="button" className="map-btn fit-btn" onClick={fitWard} title="Fit the whole ward in view">
        Fit ward
      </button>
      {pickMode && (
        <div className="pick-hint">
          Click the map to place <strong>{pickMode === 'start' ? 'A (start)' : 'B (destination)'}</strong>
        </div>
      )}
    </div>
  );
}
