export const RISK_LEVELS = [
  { key: 'low', label: 'Low', range: '< 5 cm', color: '#10b981', min: 0 },
  { key: 'moderate', label: 'Moderate', range: '5–15 cm', color: '#fbbf24', min: 5 },
  { key: 'high', label: 'High', range: '15–30 cm', color: '#f97316', min: 15 },
  { key: 'critical', label: 'Critical', range: '> 30 cm', color: '#ef4444', min: 30 },
];

const BY_KEY = Object.fromEntries(RISK_LEVELS.map((r) => [r.key, r]));

export function riskOf(depthCm) {
  if (depthCm >= 30) return 'critical';
  if (depthCm >= 15) return 'high';
  if (depthCm >= 5) return 'moderate';
  return 'low';
}

export const riskColor = (key) => BY_KEY[key]?.color ?? '#94a3b8';
export const riskLabel = (key) => BY_KEY[key]?.label ?? key;

const CLASS_WEIGHT = {
  trunk: 6, primary: 5.5, secondary: 4.5, tertiary: 3.8,
  trunk_link: 3.5, primary_link: 3.5, secondary_link: 3.2, tertiary_link: 3,
};

export function roadStyle(highway, risk, selected = false) {
  const base = CLASS_WEIGHT[highway] ?? 2.6;
  const dry = risk === 'low';
  return {
    color: riskColor(risk),
    weight: selected ? base + 3 : dry ? base : base + 1,
    opacity: dry ? 0.55 : 0.95,
    lineCap: 'round',
    lineJoin: 'round',
  };
}

export function drainState(node, load) {
  if (node.type === 'outfall') return load > 1 ? 'outfall-over' : 'outfall';
  if (load > 1) return 'surcharged';
  if (load > 0.8) return 'near';
  return 'normal';
}

export const DRAIN_STYLES = {
  normal: { fillColor: '#2563eb', color: '#ffffff', label: 'Manhole' },
  near: { fillColor: '#f59e0b', color: '#ffffff', label: 'Near capacity (> 80%)' },
  surcharged: { fillColor: '#b91c1c', color: '#ffffff', label: 'Surcharged (overflowing)' },
  outfall: { fillColor: '#0f766e', color: '#ffffff', label: 'Outfall' },
  'outfall-over': { fillColor: '#0f766e', color: '#b91c1c', label: 'Outfall over capacity' },
};

export const HIGHWAY_LABELS = {
  trunk: 'Arterial road', primary: 'Main road', secondary: 'Secondary road', tertiary: 'Connector road',
  residential: 'Residential street', unclassified: 'Local street', living_street: 'Lane',
  trunk_link: 'Slip road', primary_link: 'Slip road', secondary_link: 'Slip road', tertiary_link: 'Slip road',
};

export const roadName = (road) =>
  road?.name || road?.label || `Unnamed ${(HIGHWAY_LABELS[road?.highway] || 'road').toLowerCase()}`;

/**
 * Field crews can't act on "unnamed street". Label each unnamed segment by the
 * nearest named road reachable through the street network (breadth-first, 3 hops).
 */
export function labelUnnamedRoads(roads) {
  const byNode = new Map();
  roads.forEach((r, i) => {
    [r.from_node, r.to_node].forEach((n) => {
      if (!byNode.has(n)) byNode.set(n, []);
      byNode.get(n).push(i);
    });
  });
  const neighbours = (i) => [...byNode.get(roads[i].from_node), ...byNode.get(roads[i].to_node)];
  roads.forEach((road, i) => {
    if (road.name) return;
    const seen = new Set([i]);
    let frontier = [i];
    for (let hop = 0; hop < 3 && !road.label; hop += 1) {
      const next = [];
      for (const cur of frontier) {
        for (const nb of neighbours(cur)) {
          if (seen.has(nb)) continue;
          seen.add(nb);
          if (roads[nb].name) {
            road.label = `Lane off ${roads[nb].name}`;
            break;
          }
          next.push(nb);
        }
        if (road.label) break;
      }
      frontier = next;
    }
  });
  return roads;
}
