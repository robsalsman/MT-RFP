import React, { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { useIsMobile } from '../useMediaQuery.js'
import Detail from './Detail.jsx'

const SORT_OPTIONS = [
  ['fit_score', 'Fit score'],
  ['days_left', 'Days left'],
  ['est_prior_spend', 'Est. prior spend'],
  ['state', 'State'],
  ['billed_entity_name', 'Entity'],
]

const COLS = [
  ['fit_score', 'Fit'],
  ['state', 'State'],
  ['billed_entity_name', 'Entity'],
  ['applicant_type', 'Type'],
  ['service_types', 'Services'],
  ['est_prior_spend', 'Est. Prior Spend'],
  ['certified_date', 'Certified'],
  ['bid_deadline', 'Bid Deadline'],
  ['status', 'Status'],
  ['days_left', 'Days Left'],
]

const fmtMoney = (v) => (v == null ? '—' :
  v.toLocaleString('en-US', { style: 'currency', currency: 'USD',
    maximumFractionDigits: 0 }))
const fmtDate = (v) => (v ? String(v).slice(0, 10) : '—')

export default function Dashboard() {
  const [rows, setRows] = useState([])
  const [statusFilter, setStatusFilter] = useState('OPEN')
  const [stateFilter, setStateFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [missionOnly, setMissionOnly] = useState(true)
  const [facets, setFacets] = useState({ applicant_types: [], states: [] })
  const [q, setQ] = useState('')
  const [sort, setSort] = useState({ key: 'fit_score', dir: -1 })
  const [selected, setSelected] = useState(null)
  const [sync, setSync] = useState(null)
  const [loading, setLoading] = useState(false)
  const pollRef = useRef(null)
  const isMobile = useIsMobile()

  const load = useCallback(() => {
    setLoading(true)
    api.rfps({ status: statusFilter, state: stateFilter,
      applicant_type: typeFilter, mission_only: missionOnly, q })
      .then((d) => setRows(d.rfps))
      .finally(() => setLoading(false))
  }, [statusFilter, stateFilter, typeFilter, missionOnly, q])

  useEffect(() => { load() }, [load])
  useEffect(() => { api.syncStatus().then(setSync).catch(() => {}) }, [])
  useEffect(() => { api.facets().then(setFacets).catch(() => {}) }, [])

  // assistant-driven navigation: filters + open a specific RFP
  useEffect(() => {
    const onNav = (e) => {
      const d = e.detail || {}
      if (d.status_filter) setStatusFilter(d.status_filter === 'ALL' ? ''
        : d.status_filter)
      if (d.state_filter !== undefined) setStateFilter(d.state_filter || '')
      if (d.applicant_type !== undefined) setTypeFilter(d.applicant_type || '')
      if (d.search !== undefined) setQ(d.search || '')
      if (d.open_application_number) setSelected(d.open_application_number)
    }
    window.addEventListener('mtrfp:navigate', onNav)
    return () => window.removeEventListener('mtrfp:navigate', onNav)
  }, [])

  const refresh = () => {
    api.sync().then(() => {
      clearInterval(pollRef.current)
      pollRef.current = setInterval(() => {
        api.syncStatus().then((s) => {
          setSync(s)
          if (!s.running) { clearInterval(pollRef.current); load() }
        })
      }, 3000)
    })
  }
  useEffect(() => () => clearInterval(pollRef.current), [])

  const sorted = [...rows].sort((a, b) => {
    const va = a[sort.key], vb = b[sort.key]
    if (va == null) return 1
    if (vb == null) return -1
    return (va < vb ? -1 : va > vb ? 1 : 0) * sort.dir
  })
  const clickSort = (key) => setSort((s) =>
    s.key === key ? { key, dir: -s.dir } : { key, dir: -1 })

  const states = facets.states?.length
    ? facets.states
    : [...new Set(rows.map((r) => r.state).filter(Boolean))].sort()
  const types = facets.applicant_types || []

  const syncNote = sync?.running ? 'Sync running…'
    : sync?.last_sync
      ? `Last sync ${fmtDate(sync.last_sync.finished_at)} (${sync.last_sync.status})`
      : ''
  const empty = !sorted.length && !loading

  return (
    <>
      <div className="filters">
        <select value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option>OPEN</option>
          <option value="CLOSING SOON">CLOSING SOON</option>
          <option>CLOSED</option>
        </select>
        <select value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value)}>
          <option value="">All states</option>
          {states.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">All types</option>
          {types.map((t) => <option key={t}>{t}</option>)}
        </select>
        <label className="mission-toggle" title="Show only RFPs Mission Telecom can bid on and deliver (Category 1 wireless-serviceable internet access; excludes fiber builds and LAN hardware)">
          <input type="checkbox" checked={missionOnly}
            onChange={(e) => setMissionOnly(e.target.checked)} />
          Mission fit only
        </label>
        {/* mobile has no sortable column headers, so expose sort here */}
        {isMobile && (
          <select value={sort.key} onChange={(e) =>
            setSort({ key: e.target.value, dir: -1 })}>
            {SORT_OPTIONS.map(([k, label]) => (
              <option key={k} value={k}>Sort: {label}</option>))}
          </select>
        )}
        <input className="search" placeholder="Search entity or 470 #"
          value={q} onChange={(e) => setQ(e.target.value)} />
        <span className="spacer" />
        <span className="syncnote">{syncNote}</span>
        <button className="primary" onClick={refresh}
          disabled={sync?.running}>Refresh Now</button>
      </div>

      {isMobile ? (
        <div className="rfp-cards">
          {sorted.map((r) => (
            <button key={r.application_number} className="rfp-card"
              onClick={() => setSelected(r.application_number)}>
              <div className="rfp-card-top">
                <span className="score">{r.fit_score ?? '—'}</span>
                <span className={`badge ${r.status.split(' ')[0]}`}>
                  {r.status}{r.days_left != null
                    ? ` · ${r.days_left}d left` : ''}</span>
                <span className="rfp-card-state">{r.state}</span>
              </div>
              <div className="rfp-card-entity">{r.billed_entity_name}
                {r.mission_biddable === 0 && (
                  <span className="notfit" title={(r.mission_blockers
                    || []).join('; ')}>not a fit</span>)}
              </div>
              <div className="svc">{r.applicant_type}
                {r.service_types?.length
                  ? ` · ${r.service_types.join(', ')}` : ''}</div>
              <div className="rfp-card-facts">
                <span>{fmtMoney(r.est_prior_spend)} prior</span>
                <span>Due {fmtDate(r.bid_deadline)}</span>
              </div>
              {r.score_rationale && (
                <div className="rationale">{r.score_rationale}</div>)}
            </button>
          ))}
          {empty && <div className="card">No RFPs match. Try Refresh Now
            or clear filters.</div>}
        </div>
      ) : (
        <table className="rfps">
          <thead>
            <tr>{COLS.map(([key, label]) => (
              <th key={key} onClick={() => clickSort(key)}
                className={sort.key === key ? 'sorted' : ''}>
                {label}{sort.key === key ? (sort.dir < 0 ? ' ▾' : ' ▴') : ''}
              </th>))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={r.application_number} className="row"
                onClick={() => setSelected(r.application_number)}>
                <td className="score">{r.fit_score ?? '—'}</td>
                <td>{r.state}</td>
                <td>
                  <div>{r.billed_entity_name}
                    {r.mission_biddable === 0 && (
                      <span className="notfit" title={(r.mission_blockers
                        || []).join('; ')}>not a fit</span>)}
                  </div>
                  <div className="rationale">{r.score_rationale}</div>
                </td>
                <td>{r.applicant_type}</td>
                <td className="svc">{(r.service_types || []).join(', ')}</td>
                <td>{fmtMoney(r.est_prior_spend)}</td>
                <td>{fmtDate(r.certified_date)}</td>
                <td>{fmtDate(r.bid_deadline)}<div className="small">
                  {r.bid_deadline_eastern}</div></td>
                <td><span className={`badge ${r.status.split(' ')[0]}`}>
                  {r.status}</span></td>
                <td>{r.days_left ?? '—'}</td>
              </tr>
            ))}
            {empty && (
              <tr><td colSpan={COLS.length}>No RFPs match. Try Refresh Now or
                clear filters.</td></tr>)}
          </tbody>
        </table>
      )}
      {selected && (
        <Detail applicationNumber={selected}
          onClose={() => setSelected(null)} />
      )}
    </>
  )
}
