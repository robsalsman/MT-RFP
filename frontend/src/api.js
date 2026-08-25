// --- per-user auth (name + 4-digit PIN) ----------------------------------
let token = localStorage.getItem('mtrfp_token') || ''
let displayName = localStorage.getItem('mtrfp_name') || ''

export const auth = {
  token: () => token,
  isSet: () => !!token,
  name: () => displayName,
  set(t, name) {
    token = t || ''
    if (t) localStorage.setItem('mtrfp_token', t)
    else localStorage.removeItem('mtrfp_token')
    if (name !== undefined) {
      displayName = name || ''
      if (name) localStorage.setItem('mtrfp_name', name)
      else localStorage.removeItem('mtrfp_name')
    }
  },
  login: (username, pin) =>
    fetch('/api/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, pin }),
    }).then((r) => {
      if (!r.ok) throw new Error('Incorrect name or PIN')
      return r.json()
    }).then((d) => { auth.set(d.token, d.display_name); return d }),
  logout() { auth.set('', '') },
}

// fetch wrapper that attaches the token and signals when the session lapses.
export function authFetch(url, opts = {}) {
  const headers = { ...(opts.headers || {}) }
  const sent = token          // the token THIS request goes out with
  if (sent) headers.Authorization = `Bearer ${sent}`
  return fetch(url, { ...opts, headers }).then((r) => {
    // Only treat a 401 as "session lapsed" if this request carried the
    // CURRENT token. A stale in-flight request from before login must
    // not wipe the token login just stored (that made sign-in loop).
    if (r.status === 401 && sent && sent === token) {
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
  competitorLeads: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v != null))
    return authFetch(`/api/competitor-leads?${qs}`).then(json)
  },
  competitorSweep: () =>
    authFetch('/api/competitor-leads/sweep', { method: 'POST' }).then(json),
  competitorDraft: (id) =>
    authFetch(`/api/competitor-leads/${id}/draft`, { method: 'POST' }).then(json),
  competitorContacts: (id) =>
    authFetch(`/api/competitor-leads/${id}/contacts`, { method: 'POST' }).then(json),
  consultants: (limit = 25) =>
    authFetch(`/api/consultants?limit=${limit}`).then(json),
  consultantPitch: (name) =>
    authFetch('/api/consultants/pitch', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }).then(json),
  getVibe: () => authFetch('/api/me/vibe').then(json),
  setVibe: (vibe) => authFetch('/api/me/vibe', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ vibe }),
  }).then(json),
  runFocus: () => authFetch('/api/daily-run/focus').then(json),
  setRunFocus: (focus) => authFetch('/api/daily-run/focus', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ focus }),
  }).then(json),
  dailyRun: () => authFetch('/api/daily-run').then(json),
  dailyRunBuild: (n = 20) => authFetch('/api/daily-run/build', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ n }),
  }).then(json),
  dailyRunAction: (leadId, action) =>
    authFetch(`/api/daily-run/${leadId}/action`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    }).then(json),
  vaultNotes: (section) =>
    authFetch(`/api/vault/notes${section ? `?section=${section}` : ''}`)
      .then(json),
  vaultNote: (path) =>
    authFetch(`/api/vault/note?path=${encodeURIComponent(path)}`).then(json),
  vaultSave: (path, content) => authFetch('/api/vault/note', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, content }),
  }).then(json),
  vaultDelete: (path) =>
    authFetch(`/api/vault/note?path=${encodeURIComponent(path)}`,
      { method: 'DELETE' }).then(json),
  vaultSearch: (q) =>
    authFetch(`/api/vault/search?q=${encodeURIComponent(q)}`).then(json),
  vaultSticky: (text) => authFetch('/api/vault/sticky', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  }).then(json),
  vaultUrl: (url) => authFetch('/api/vault/url', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  }).then(json),
  vaultUpload: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return authFetch('/api/vault/upload', { method: 'POST', body: fd })
      .then(json)
  },
  alerts: () => authFetch('/api/alerts').then(json),
  alertsSeen: (ids) => authFetch('/api/alerts/seen', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids }),
  }).then(json),
  leadLinkedIn: (id) =>
    authFetch(`/api/competitor-leads/${id}/linkedin`).then(json),
  liQueue: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v != null))
    return authFetch(`/api/linkedin/queue?${qs}`).then(json)
  },
  liBuildTop: (n = 8) => authFetch('/api/linkedin/build-top', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ n }),
  }).then(json),
  liStep: (target_id, step) => authFetch('/api/linkedin/step', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_id, step }),
  }).then(json),
  leadNote: (id, text) =>
    authFetch(`/api/competitor-leads/${id}/notes`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }).then(json),
  competitorStatus: (id, status) =>
    authFetch(`/api/competitor-leads/${id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    }).then(json),
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
