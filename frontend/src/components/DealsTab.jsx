import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

// Deals & Docs: every engaged deal grouped by stage, with one-tap asks to
// Matt for the closing paperwork (savings sheet, champion kit, follow-up).

const askMatt = (text) =>
  window.dispatchEvent(new CustomEvent('mtrfp:ask', { detail: { text } }))

const STAGES = [
  ['replied', '💬 Replied', 'They answered — keep the momentum'],
  ['meeting', '📅 Meeting', 'On the calendar — arm yourself'],
  ['quote', '💲 Quote out', 'The number is in their hands'],
  ['verbal', '🤝 Verbal yes', 'Make signing trivial'],
  ['contacted', '📤 Contacted', 'First touch made — nudge on schedule'],
  ['won', '🏆 Won', 'Signed! Case-study material'],
]

const fmtUsd = (n) => n ? `$${Math.round(n).toLocaleString()}` : '—'

export default function DealsTab() {
  const [groups, setGroups] = useState(null)

  useEffect(() => {
    Promise.all(STAGES.map(([s]) =>
      api.competitorLeads({ status: s, limit: 40 })
        .then((d) => [s, d.leads || d.items || []])
        .catch(() => [s, []])))
      .then((pairs) => setGroups(Object.fromEntries(pairs)))
  }, [])

  if (groups === null) return <div>Loading…</div>
  const totalDeals = Object.values(groups).flat().length

  return (
    <div>
      <div className="card">
        <h3>🤝 Deals &amp; Docs — from lead to signature</h3>
        <p className="small">Every engaged deal, grouped by stage. The
          buttons ask Matt for the right artifact at the right moment:
          savings sheet to make the case, champion kit so your contact can
          sell it to their board, follow-ups when things go quiet.
          {totalDeals === 0 && ' Nothing engaged yet — clear a Daily Run '
            + 'and this board fills up.'}</p>
      </div>
      {STAGES.map(([stage, label, hint]) => {
        const leads = groups[stage] || []
        if (!leads.length) return null
        return (
          <div className="card" key={stage}>
            <h3>{label} <span className="small">· {leads.length} ·
              {' '}{hint}</span></h3>
            <table className="rfps"><tbody>
              {leads.map((l) => (
                <tr key={l.id}>
                  <td><b>{l.org}</b> <span className="small">{l.state}
                    {l.competitor_label ? ` · ${l.competitor_label}` : ''}
                  </span></td>
                  <td className="small">{l.competitor === 'greenfield'
                    ? `${fmtUsd(l.budget)} budget`
                    : `${fmtUsd(l.spend)}/yr`}</td>
                  <td className="deal-actions">
                    <button onClick={() => askMatt(
                      `Make the savings sheet for ${l.org}`)}>📄 Savings
                      sheet</button>
                    <button onClick={() => askMatt(
                      `Build the board champion kit for ${l.org}`)}>🏅
                      Champion kit</button>
                    <button onClick={() => askMatt(
                      `Draft a follow-up for ${l.org}`)}>✉️ Follow-up
                    </button>
                  </td>
                </tr>
              ))}
            </tbody></table>
          </div>
        )
      })}
    </div>
  )
}
