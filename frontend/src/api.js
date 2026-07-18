// --- team auth token (shared password gate) -----------------------------
let token = localStorage.getItem('mtrfp_token') || ''

export const auth = {
  token: () => token,
  isSet: () => !!token,
  set(t) {
    token = t || ''
    if (t) localStorage.setItem('mtrfp_token', t)
    else localStorage.removeItem('mtrfp_token')
  },
  login: (password) =>
    fetch('/api/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    }).then((r) => {
      if (!r.ok) throw new Error('Incorrect team password')
      return r.json()
    }).then((d) => { auth.set(d.token); return d }),
  logout() { auth.set('') },
}

// fetch wrapper that attaches the token and signals when the session lapses.
export function authFetch(url, opts = {}) {
  const headers = { ...(opts.headers || {}) }
  if (token) headers.Authorization = `Bearer ${token}`
  return fetch(url, { ...opts, headers }).then((r) => {
    if (r.status === 401) {
      auth.set('')
      window.dispatchEvent(new Event('mtrfp:unauthorized'))
    }
    return r
  })
}

const json = (r) => {
  if (!r.ok) return r.json().then((b) => { throw new Error(b.detail || r.statusText) })
  return r.json()
}

export const api = {
  rfps: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v != null))
    return authFetch(`/api/rfps?${qs}`).then(json)
  },
  facets: () => authFetch('/api/rfps-facets').then(json),
  rfp: (an) => authFetch(`/api/rfps/${an}`).then(json),
  analyze: (an) => authFetch(`/api/rfps/${an}/analyze`, { method: 'POST' }).then(json),
  generateResponse: (an) =>
    authFetch(`/api/rfps/${an}/generate-response`, { method: 'POST' }).then(json),
  sync: () => authFetch('/api/sync', { method: 'POST' }).then(json),
  syncStatus: () => authFetch('/api/sync/status').then(json),
  settings: () => authFetch('/api/settings').then(json),
  saveSettings: (s) => authFetch('/api/settings', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(s),
  }).then(json),
  pricelist: () => authFetch('/api/pricelist').then(json),
  uploadPricelist: (file, mapping) => {
    const fd = new FormData()
    fd.append('file', file)
    if (mapping) fd.append('mapping', JSON.stringify(mapping))
    return authFetch('/api/pricelist', { method: 'POST', body: fd }).then(json)
  },
  profile: () => authFetch('/api/profile').then(json),
  saveProfile: (p) => authFetch('/api/profile', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(p),
  }).then(json),
  uploadProfileDoc: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return authFetch('/api/profile/documents', { method: 'POST', body: fd }).then(json)
  },
  health: () => fetch('/api/health').then(json),   // open (no token)
  keepAwake: () => authFetch('/api/keepawake').then(json),
  setKeepAwake: (on) => authFetch('/api/keepawake', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ on }),
  }).then(json),
}
