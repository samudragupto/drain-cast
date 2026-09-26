const BASE = (process.env.REACT_APP_API_URL || '/api').replace(/\/$/, '');

async function request(path, { method = 'GET', body, signal } = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      signal,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new Error('Cannot reach the DrainCast API. Is the backend running on port 5000?');
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    // non-JSON error page (e.g. proxy failure)
  }
  if (!res.ok) {
    throw new Error((data && data.error) || `Request failed (${res.status})`);
  }
  return data;
}

export const api = {
  health: () => request('/health'),
  wards: () => request('/wards'),
  ward: (id, signal) => request(`/wards/${encodeURIComponent(id)}`, { signal }),
  simulate: (params, signal) => request('/simulate', { method: 'POST', body: params, signal }),
  route: (payload, signal) => request('/route', { method: 'POST', body: payload, signal }),
};
