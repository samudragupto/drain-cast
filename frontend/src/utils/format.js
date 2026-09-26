const clockFmt = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

export function clockAt(startIso, minutes) {
  if (!startIso) return '--:--';
  const t = new Date(new Date(startIso).getTime() + minutes * 60000);
  return clockFmt.format(t);
}

export function offsetLabel(minutes) {
  if (minutes === 0) return 'Now';
  const sign = minutes < 0 ? '−' : '+';
  const m = Math.abs(minutes);
  return `${sign}${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}`;
}

export function inLabel(minutes) {
  if (minutes <= 0) return 'now';
  if (minutes < 60) return `in ${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `in ${h} h ${m} min` : `in ${h} h`;
}

export const cm = (v) => `${Number(v).toFixed(1)} cm`;

export function volume(m3) {
  if (m3 >= 1000) return `${(m3 / 1000).toFixed(1)} ML`;
  return `${Math.round(m3).toLocaleString('en-IN')} m³`;
}

export const lps = (v) => `${Math.round(v).toLocaleString('en-IN')} L/s`;
