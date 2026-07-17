import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

const fmtMoney = (v) => (v == null ? '—' :
  v.toLocaleString('en-US', { style: 'currency', currency: 'USD' }))

export default function Detail({ applicationNumber, onClose }) {
  const [rfp, setRfp] = useState(null)
  const [busy, setBusy] = useState('')
  const [genResult, setGenResult] = useState(null)
  const [error, setError] = useState('')

  const load = () => api.rfp(applicationNumber).then(setRfp).catch(
    (e) => setError(e.message))
  useEffect(() => { load() }, [applicationNumber])

  if (!rfp) return (
    <aside className="drawer"><button className="close"
      onClick={onClose}>✕</button>{error || 'Loading…'}</aside>)

  const a = rfp.analysis

  const analyze = () => {
    setBusy('analyze'); setError('')
    api.analyze(applicationNumber).then(load)
      .catch((e) => setError(e.message)).finally(() => setBusy(''))
  }
  const generate = () => {
    setBusy('generate'); setError('')
    api.generateResponse(applicationNumber)
      .then((r) => { setGenResult(r); load() })
      .catch((e) => setError(e.message)).finally(() => setBusy(''))
  }

  return (
    <aside className="drawer">
      <button className="close" onClick={onClose}>✕</button>
      <h2>{rfp.billed_entity_name}</h2>
      <span className={`badge ${rfp.status.split(' ')[0]}`}>{rfp.status}</span>
      {' '}<b>{rfp.fit_score ?? '—'}</b>/100 fit
      <dl className="kv">
        <dt>Form 470 #</dt><dd>{rfp.application_number} (FY{rfp.funding_year})</dd>
        <dt>Location</dt><dd>{rfp.city}, {rfp.state} {rfp.zip}</dd>
        <dt>Applicant type</dt><dd>{rfp.applicant_type}</dd>
        <dt>Contact</dt>
        <dd>{rfp.contact_name} &middot; {rfp.contact_email} &middot; {rfp.contact_phone}</dd>
        <dt>Certified</dt><dd>{(rfp.certified_date || '').slice(0, 10)}</dd>
        <dt>Bid deadline</dt>
        <dd>{rfp.bid_deadline} ({rfp.bid_deadline_eastern}) —
          {' '}{rfp.days_left} days left</dd>
        <dt>Est. prior spend</dt><dd>{fmtMoney(rfp.est_prior_spend)}
          <span className="small"> (prior-FY Form 471 total for this BEN)</span></dd>
        <dt>Services</dt><dd>{(rfp.service_types || []).join(', ')}</dd>
        <dt>Functions</dt><dd className="small">{(rfp.functions || []).join(', ')}</dd>
      </dl>

      {rfp.score_breakdown && (
        <div className="card">
          <b>Score breakdown</b>
          <dl className="kv">
            {Object.entries(rfp.score_breakdown).map(([k, v]) => (
              <React.Fragment key={k}>
                <dt>{k.replace('_', ' ')}</dt>
                <dd>{v.points} / {v.max}</dd>
              </React.Fragment>))}
          </dl>
          <div className="small">{rfp.score_rationale}</div>
        </div>
      )}

      <div className="card">
        <b>Original documents</b>
        <ul>
          {rfp.form_pdf_url && <li><a href={rfp.form_pdf_url} target="_blank"
            rel="noreferrer">Certified Form 470 PDF (USAC)</a></li>}
          {(rfp.rfp_doc_urls || []).map((u) => (
            <li key={u}><a href={u} target="_blank" rel="noreferrer">
              {decodeURIComponent(u.split('/').pop())}</a></li>))}
          {(rfp.doc_files || []).map((f) => (
            <li key={f} className="small">
              <a href={`/api/rfps/${rfp.application_number}/documents/${f}`}
                target="_blank" rel="noreferrer">local: {f}</a></li>))}
        </ul>
      </div>

      <div className="card">
        <b>AI analysis</b>{' '}
        <button onClick={analyze} disabled={busy !== ''}>
          {busy === 'analyze' ? 'Analyzing…' : a ? 'Re-analyze' : 'Analyze'}
        </button>
        {a ? (
          <>
            <dl className="kv">
              <dt>Contract term</dt><dd>{a.contract_term_years ?? '—'} years</dd>
              <dt>Question deadline</dt><dd>{a.question_deadline ?? '—'}</dd>
              <dt>Submission</dt>
              <dd>{a.submission_method ?? '—'} by {a.submission_deadline ?? '—'}</dd>
              <dt>Price primary factor</dt>
              <dd>{a.price_primary_factor == null ? '—'
                : a.price_primary_factor ? 'Yes (E-Rate compliant)' : 'Not stated'}</dd>
            </dl>
            <b>Services requested</b>
            <ul className="reqlist">{(a.services_requested || []).map((s, i) => (
              <li key={i}>{s.service}
                {s.bandwidth ? ` — ${s.bandwidth}` : ''}
                {s.quantity ? ` × ${s.quantity}` : ''}</li>))}</ul>
            <b>Mandatory requirements</b>
            <ul className="reqlist">{(a.mandatory_requirements || []).map(
              (r, i) => <li key={i}>{r}</li>)}
              {!(a.mandatory_requirements || []).length && <li>None extracted</li>}
            </ul>
            {(a.disqualifiers || []).length > 0 && (<>
              <b className="err">Potential disqualifiers</b>
              <ul className="reqlist">{a.disqualifiers.map(
                (d, i) => <li key={i} className="err">{d}</li>)}</ul>
            </>)}
            {(a.evaluation_criteria || []).length > 0 && (<>
              <b>Evaluation criteria</b>
              <ul className="reqlist">{a.evaluation_criteria.map((c, i) => (
                <li key={i}>{c.criterion}{c.weight ? ` (${c.weight})` : ''}</li>
              ))}</ul>
            </>)}
          </>
        ) : (
          <div className="small">Not analyzed yet. Requires an AI provider
            key in .env (NEMOTRON_API_KEY).</div>
        )}
      </div>

      <div className="card">
        <b>Draft response</b>
        <div className="draftflag">Every generated response is a
          <b> DRAFT</b> with a mandatory human-review checklist. Unpriced items
          are flagged in red — prices are never invented. Nothing is ever
          auto-submitted.</div>
        <button className="primary" onClick={generate}
          disabled={busy !== '' || rfp.status === 'CLOSED'}>
          {busy === 'generate' ? 'Generating…' : 'Generate Response'}
        </button>
        {rfp.status === 'CLOSED' && (
          <span className="small"> Bid window has closed.</span>)}
        {genResult && (
          <div style={{ marginTop: 10 }}>
            <div className="ok">Draft ready.</div>
            {genResult.unmatched_count > 0 && (
              <div className="err">{genResult.unmatched_count} requested
                item(s) had no price-list match — marked [NEEDS INPUT].</div>)}
            <ul>
              <li><a href={`/api/responses/${genResult.id}/download?fmt=docx`}>
                Download DOCX</a></li>
              <li><a href={`/api/responses/${genResult.id}/download?fmt=pdf`}>
                Download PDF</a></li>
            </ul>
          </div>
        )}
        {(rfp.responses || []).length > 0 && (<>
          <b className="small">Previous drafts</b>
          <ul>{rfp.responses.map((r) => (
            <li key={r.id} className="small">
              {r.created_at.slice(0, 16).replace('T', ' ')} UTC — {r.status}
              {' '}<a href={`/api/responses/${r.id}/download?fmt=docx`}>DOCX</a>
              {' '}<a href={`/api/responses/${r.id}/download?fmt=pdf`}>PDF</a>
            </li>))}</ul>
        </>)}
      </div>

      {rfp.doc_text_preview && (
        <div className="card">
          <b>Extracted document text (preview)</b>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 11,
            maxHeight: 300, overflow: 'auto' }}>{rfp.doc_text_preview}</pre>
        </div>
      )}
      {error && <div className="err">{error}</div>}
    </aside>
  )
}
