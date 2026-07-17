const json = (r) => {
  if (!r.ok) return r.json().then((b) => { throw new Error(b.detail || r.statusText) })
  return r.json()
}

export const api = {
  rfps: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v != null))
    return fetch(`/api/rfps?${qs}`).then(json)
  },
  rfp: (an) => fetch(`/api/rfps/${an}`).then(json),
  analyze: (an) => fetch(`/api/rfps/${an}/analyze`, { method: 'POST' }).then(json),
  generateResponse: (an) =>
    fetch(`/api/rfps/${an}/generate-response`, { method: 'POST' }).then(json),
  sync: () => fetch('/api/sync', { method: 'POST' }).then(json),
  syncStatus: () => fetch('/api/sync/status').then(json),
  settings: () => fetch('/api/settings').then(json),
  saveSettings: (s) => fetch('/api/settings', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(s),
  }).then(json),
  pricelist: () => fetch('/api/pricelist').then(json),
  uploadPricelist: (file, mapping) => {
    const fd = new FormData()
    fd.append('file', file)
    if (mapping) fd.append('mapping', JSON.stringify(mapping))
    return fetch('/api/pricelist', { method: 'POST', body: fd }).then(json)
  },
  profile: () => fetch('/api/profile').then(json),
  saveProfile: (p) => fetch('/api/profile', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(p),
  }).then(json),
  uploadProfileDoc: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return fetch('/api/profile/documents', { method: 'POST', body: fd }).then(json)
  },
  health: () => fetch('/api/health').then(json),
}
