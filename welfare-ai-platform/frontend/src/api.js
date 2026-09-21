const API = import.meta.env.VITE_API_BASE_URL || '/api/v1';
let accessToken = null;
let refreshPending = null;
const REFRESH_KEY = 'sahaay.refresh';
export class ApiError extends Error { constructor(message, status, detail) { super(message); this.status = status; this.detail = detail; } }
export function setSession(data) { accessToken = data.access_token; sessionStorage.setItem(REFRESH_KEY, data.refresh_token); }
export function clearSession() { accessToken = null; sessionStorage.removeItem(REFRESH_KEY); }
export function hasSession() { return !!sessionStorage.getItem(REFRESH_KEY); }
export function formatError(detail) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(e => `${e.loc?.filter(x => x !== 'body').join(' ') || 'Input'}: ${e.msg || 'invalid value'}`).join('; ');
  return detail?.message || 'The request could not be completed. Please try again.';
}
async function refresh() {
  if (!refreshPending) refreshPending = (async () => {
    const token = sessionStorage.getItem(REFRESH_KEY);
    if (!token) throw new ApiError('Please sign in to continue.', 401);
    const result = await fetch(`${API}/auth/refresh`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: token }) });
    if (!result.ok) { clearSession(); throw new ApiError('Your session ended. Please sign in again.', 401); }
    const data = await result.json(); setSession(data); return data;
  })().finally(() => { refreshPending = null; });
  return refreshPending;
}
export async function restoreSession() { return await refresh(); }
export async function api(path, options = {}, retry = true) {
  const { body, raw = false, ...rest } = options;
  let response;
  try {
    response = await fetch(`${API}${path}`, {
      ...rest,
      headers: { ...(body && !(body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}), ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}), ...rest.headers },
      body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) { if (e.name === 'AbortError') throw e; throw new ApiError('Cannot reach the service. Check that the backend is running, then try again.', 0); }
  if (response.status === 401 && retry && hasSession() && !path.startsWith('/auth/')) { await refresh(); return api(path, options, false); }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if (response.status === 401 && !path.startsWith('/auth/')) { clearSession(); window.dispatchEvent(new Event('session-expired')); }
    throw new ApiError(formatError(data.detail), response.status, data.detail);
  }
  if (raw) return response;
  return response.status === 204 ? null : response.json();
}
export async function download(path, name) {
  const response = await api(path, { raw: true }); const blob = await response.blob();
  const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function safeUrl(url) { try { const value = new URL(url); return ['http:', 'https:'].includes(value.protocol) ? value.href : null; } catch { return null; } }
