import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

const PROFILE_FIELDS = [
  ['legal_name', 'Legal name'],
  ['spin', 'SPIN #'],
  ['fcc_rn', 'FCC Registration Number'],
  ['address', 'Address'],
  ['contact_name', 'Primary contact name'],
  ['contact_email', 'Primary contact email'],
  ['contact_phone', 'Primary contact phone'],
  ['w9_tin', 'W-9 TIN (last 4 shown in drafts only if you enter it)'],
]

export default function Uploads() {
  const [pricelist, setPricelist] = useState(null)
  const [uploadResult, setUploadResult] = useState(null)
  const [mapping, setMapping] = useState(null)
  const [pendingFile, setPendingFile] = useState(null)
  const [profile, setProfile] = useState({})
  const [documents, setDocuments] = useState([])
  const [references, setReferences] = useState('')
  const [capability, setCapability] = useState('')
  const [savedMsg, setSavedMsg] = useState('')

  useEffect(() => {
    api.pricelist().then(setPricelist)
    api.profile().then((d) => {
      setProfile(d.profile || {})
      setDocuments(d.documents || [])
      setReferences((d.profile?.references || []).join('\n'))
      setCapability(d.profile?.capability_statement || '')
    })
  }, [])

  const onFile = (file, m = null) => {
    setUploadResult(null)
    api.uploadPricelist(file, m).then((r) => {
      setUploadResult(r)
      if (r.needs_mapping) { setPendingFile(file); setMapping(r) }
      else { setMapping(null); setPendingFile(null); api.pricelist().then(setPricelist) }
    })
  }

  const applyMapping = () => {
    const m = {}
    for (const field of ['sku', 'description', 'category', 'unit',
      'unit_price', 'term_months']) {
      const sel = document.getElementById(`map-${field}`)
      if (sel && sel.value !== '') m[field] = Number(sel.value)
    }
    onFile(pendingFile, m)
  }

  const saveProfile = () => {
    const p = { ...profile,
      references: references.split('\n').map((s) => s.trim()).filter(Boolean),
      capability_statement: capability }
    api.saveProfile(p).then(() => {
      setSavedMsg('Saved.'); setTimeout(() => setSavedMsg(''), 2000)
    })
  }

  const onProfileDoc = (file) => api.uploadProfileDoc(file).then(() =>
    api.profile().then((d) => setDocuments(d.documents || [])))

  return (
    <div className="grid2">
      <div className="card">
        <h3>Price list</h3>
        <p className="small">CSV or XLSX with SKU, description, service
          category, unit, unit price, term. Drives pricing tables and
          service-match scoring. Uploading replaces the previous list.</p>
        <input type="file" accept=".csv,.xlsx,.xlsm"
          onChange={(e) => e.target.files[0] && onFile(e.target.files[0])} />
        {uploadResult?.ok && (
          <p className="ok">Imported {uploadResult.imported} items.
            {uploadResult.row_errors?.length > 0 &&
              ` ${uploadResult.row_errors.length} rows skipped.`}</p>)}
        {uploadResult && !uploadResult.ok && !uploadResult.needs_mapping && (
          <p className="err">{uploadResult.error}</p>)}
        {mapping?.needs_mapping && (
          <div>
            <p className="warn">Headers not recognized — map the columns:</p>
            {['sku', 'description', 'category', 'unit', 'unit_price',
              'term_months'].map((field) => (
              <div className="formrow" key={field}>
                <label>{field}{['description', 'unit_price'].includes(field)
                  ? ' (required)' : ''}</label>
                <select id={`map-${field}`}
                  defaultValue={mapping.sniffed?.[field] ?? ''}>
                  <option value="">— not present —</option>
                  {mapping.headers.map((h, i) => (
                    <option key={i} value={i}>{h}</option>))}
                </select>
              </div>))}
            <button className="primary" onClick={applyMapping}>
              Import with this mapping</button>
          </div>)}
        {pricelist?.count > 0 && (
          <p className="small ok">{pricelist.count} price items loaded.</p>)}
        {pricelist && pricelist.count === 0 && (
          <p className="small warn">No price list loaded yet — response
            pricing tables will be all [NEEDS INPUT].</p>)}
      </div>

      <div className="card">
        <h3>Company profile</h3>
        <p className="small">Used verbatim in draft responses. Anything left
          blank appears as [NEEDS INPUT] — the generator never invents company
          facts.</p>
        {PROFILE_FIELDS.map(([key, label]) => (
          <div className="formrow" key={key}>
            <label>{label}</label>
            <input value={profile[key] || ''}
              onChange={(e) => setProfile({ ...profile, [key]: e.target.value })} />
          </div>))}
        <div className="formrow">
          <label>Standard references (one per line: org — contact — phone/email)</label>
          <textarea rows={4} value={references}
            onChange={(e) => setReferences(e.target.value)} />
        </div>
        <div className="formrow">
          <label>Boilerplate capability statement</label>
          <textarea rows={6} value={capability}
            onChange={(e) => setCapability(e.target.value)} />
        </div>
        <button className="primary" onClick={saveProfile}>Save profile</button>
        {' '}<span className="ok">{savedMsg}</span>
        <h4>Supporting documents (insurance certs, W-9, etc.)</h4>
        <input type="file" onChange={(e) =>
          e.target.files[0] && onProfileDoc(e.target.files[0])} />
        <ul>{documents.map((d) => <li key={d} className="small">{d}</li>)}</ul>
      </div>
    </div>
  )
}
