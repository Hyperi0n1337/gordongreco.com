const API = '/api/v1';

function csrfToken() {
  const item = document.cookie.split('; ').find((row) => row.startsWith('gg_csrf='));
  return item ? decodeURIComponent(item.split('=').slice(1).join('=')) : '';
}

export async function api(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const headers = new Headers(options.headers || {});
  if (method !== 'GET' && method !== 'HEAD') headers.set('X-CSRF-Token', csrfToken());
  if (options.body && !(options.body instanceof Blob) && typeof options.body !== 'string') {
    headers.set('Content-Type', 'application/json');
    options.body = JSON.stringify(options.body);
  }
  const response = await fetch(`${API}${path}`, {credentials: 'same-origin', cache: 'no-store', ...options, method, headers});
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body?.detail?.detail || body?.detail?.code || body?.error?.code || `Request failed (${response.status})`);
    error.status = response.status;
    error.code = body?.detail?.code || body?.error?.code;
    throw error;
  }
  return body;
}

export function idempotency(prefix) {
  return `${prefix}:${crypto.randomUUID()}`;
}

export function fmtBytes(value) {
  if (!Number.isFinite(value)) return '';
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 ** 2).toFixed(1)} MB`;
}
