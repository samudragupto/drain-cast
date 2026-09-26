import { labelUnnamedRoads, riskOf, roadName } from './mapStyles';
import { clockAt, inLabel, offsetLabel, volume } from './format';

describe('riskOf', () => {
  it('uses the 5 / 15 / 30 cm bands', () => {
    expect(riskOf(0)).toBe('low');
    expect(riskOf(4.9)).toBe('low');
    expect(riskOf(5)).toBe('moderate');
    expect(riskOf(15)).toBe('high');
    expect(riskOf(30)).toBe('critical');
  });
});

describe('time labels', () => {
  it('formats offsets from now', () => {
    expect(offsetLabel(0)).toBe('Now');
    expect(offsetLabel(85)).toBe('+1:25');
    expect(offsetLabel(-30)).toBe('−0:30');
  });

  it('formats lead times', () => {
    expect(inLabel(0)).toBe('now');
    expect(inLabel(25)).toBe('in 25 min');
    expect(inLabel(120)).toBe('in 2 h');
    expect(inLabel(95)).toBe('in 1 h 35 min');
  });

  it('shows IST clock time', () => {
    expect(clockAt('2026-09-27T00:30:00+05:30', 90)).toBe('02:00');
  });

  it('formats volumes', () => {
    expect(volume(420)).toBe('420 m³');
    expect(volume(2500)).toBe('2.5 ML');
  });
});

describe('labelUnnamedRoads', () => {
  it('names an unnamed lane after the nearest named road', () => {
    const roads = labelUnnamedRoads([
      { id: 'a', name: 'SG Barve Marg', highway: 'primary', from_node: 'J1', to_node: 'J2' },
      { id: 'b', name: null, highway: 'residential', from_node: 'J2', to_node: 'J3' },
      { id: 'c', name: null, highway: 'residential', from_node: 'J3', to_node: 'J4' },
      { id: 'd', name: null, highway: 'residential', from_node: 'J8', to_node: 'J9' },
    ]);
    expect(roadName(roads[1])).toBe('Lane off SG Barve Marg');
    expect(roadName(roads[2])).toBe('Lane off SG Barve Marg');
    expect(roadName(roads[3])).toBe('Unnamed residential street');
  });
});
