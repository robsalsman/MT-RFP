import React from 'react'

// The manual: every feature, where it lives, and how to use it — written
// for the sales workflow, not the codebase. "Try:" lines are literal
// things to say to Matt.
const SECTIONS = [
  {
    icon: '🎸', title: 'Matt, your sidekick',
    items: [
      ['Talk to him', 'Hold the 🎤 button (or hold SPACE on desktop), speak, release. He answers out loud — 🔊 mutes him.'],
      ['Type instead', '💬 Chat opens the text panel. Same brain, same powers.'],
      ['Video-call mode', '📹 Call goes full screen — his face, lip-synced. ⤢ exits.'],
      ['His closet', 'The 🚪 button on his card: hand him a guitar, coffee, trophy… He also shows things off on his own when idle.'],
      ['Every morning', 'He greets you with the best targets and any urgent alerts. Tap a button in his bubble to act on one.'],
    ],
  },
  {
    icon: '🔎', title: 'Finding opportunities',
    items: [
      ['Open RFPs (Dashboard tab)', 'Every live E-Rate Form 470, scored 0–100 for Mission fit. Filter by state/type/status; click one for details and a draft response.'],
      ['Ask instead of filter', 'Try: "best RFPs right now" · "open library RFPs in Michigan" · "search the DFW area for good targets"'],
      ['Library hit list', 'Try: "which Texas libraries need hotspot lending most?" — every US library ranked by families who lost the ACP subsidy. Greenfield = Project: Volume Up pitch.'],
      ['Denied funding', 'Try: "who got denied E-Rate funding in Ohio?" — documented need, no money; our nonprofit pricing works without E-Rate. A bidding-violation denial means a new RFP is coming.'],
      ['Outside E-Rate', 'Try: "find open cellular bids outside E-Rate" (procurement portals) · "any news about Kajeet?" (fresh articles + board minutes).'],
      ['Local need stat', 'Try: "how many households lost ACP in 76013?" — a citable number for any pitch. Matt adds it to outreach drafts automatically.'],
    ],
  },
  {
    icon: '⚔️', title: 'The competitor board (Leads tab)',
    items: [
      ['What it is', 'Every school/library in America paying a competitor for mobile broadband — 9 competitors tracked, real spend from public USAC filings.'],
      ['Reading a row', 'Spend /yr = current E-Rate contract. "ECF total" badge = they bought hotspots with covid money that\'s now GONE — a win-back. "exp" date = when their contract ends (your timing).'],
      ['Slicing it', 'Click a competitor card to filter. Dropdowns: state, stage, minimum $. Click column headers to sort — "Contract ends" ascending is the hottest list in the app.'],
      ['Consultants view', 'The 🤝 card: E-Rate consultants ranked by client reach. One partnership = every door on their roster. "Draft partnership pitch" writes the email.'],
      ['Ask instead', 'Try: "biggest Kajeet accounts" · "Verizon accounts in Texas expiring soon" · "who are the top consultants?"'],
    ],
  },
  {
    icon: '📈', title: 'Working a deal (open any lead on the board)',
    items: [
      ['1. Find contacts', '🔎 crawls the district\'s own website for the tech director / superintendent — real names beat filing emails.'],
      ['2. Draft the outreach', '✍️ writes the cold email from their real numbers (spend, incumbent, contract date, ACP need). Copy or Open-in-mail. You always send — Matt never does.'],
      ['3. Set the stage', 'The Stage dropdown: contacted → replied → meeting → quote → verbal → won. Or just tell Matt: "Newark replied!" — he\'ll move it. Staged deals get watched (see Alerts).'],
      ['4. Log what happens', 'After a call, tell Matt: "debrief for lead 8: they want pilot pricing for 500 units…" — he logs it and drafts the recap email to send within the hour.'],
    ],
  },
  {
    icon: '💼', title: 'LinkedIn / Sales Navigator',
    items: [
      ['The play', 'Open any lead → 💼 LinkedIn play. Matt picks the right titles for that org (tech director, superintendent, library director…), builds one-click searches that open in YOUR logged-in Sales Navigator, and writes the whole message sequence.'],
      ['The messages', 'Connect note (under 260 chars, no pitch) → DM 1 on accept (one genuine question, zero selling) → DM 2 at day 3 (one real number as a give + soft 15-min ask) → DM 3 breakup → InMail if they never accept. Copy, personalize one line, send.'],
      ['The cadence', 'Day 0 connect + like one of their posts. DM 1 on accept. Day +3 DM 2. Day +10 breakup. Tell Matt each touch ("DM\'d the Newark tech director") so the nudges track it.'],
      ['Ask instead', 'Try: "run the LinkedIn play for lead 8" — same thing in chat.'],
      ['Why Matt doesn\'t send them', 'Automating a LinkedIn account breaks their rules and risks your Navigator subscription. Matt aims, you pull the trigger — that\'s also what actually works.'],
    ],
  },
  {
    icon: '🏁', title: 'Closing the deal',
    items: [
      ['💰 Savings sheet', 'Button on the lead. One page: their spend vs Mission pricing, savings range, E-Rate timing. THE document your contact forwards to their boss. Word file — tweak before sending.'],
      ['🏛️ Board kit', 'Button on the lead. A briefing your CONTACT presents internally: situation, savings, community need, compliance, recommendation. Arms your champion for the rooms you\'re not in.'],
      ['Handle any objection', 'Paste their reply to Matt: "Newark said: we\'re locked into Kajeet till 2028…" — he classifies the objection and drafts the counter using their real numbers.'],
      ['Follow-ups', 'When a deal goes quiet, Matt nudges you at login. Or ask: "draft a follow-up for lead 8" — stage-aware (2nd touch vs quote-nudge vs get-it-signed).'],
      ['🏆 Case study', 'Appears when a deal is marked won — drafts the story that closes the next three.'],
      ['The E-Rate clock', 'Honest urgency in every doc: act this cycle = funded service next July; waiting costs a year.'],
    ],
  },
  {
    icon: '🚨', title: 'Alerts — what Matt watches while you sleep',
    items: [
      ['The buying signal', 'Every staged deal is watched at USAC. The moment that district posts a Form 470, Matt opens with "drop everything — their 28-day window is open NOW." That\'s the day you clear your calendar.'],
      ['Stale deals', 'A quote sitting 7 days, a reply unanswered 4 — Matt resurfaces it once with a follow-up draft one tap away.'],
      ['On demand', 'Try: "what needs my attention?"'],
    ],
  },
]

export default function Guide() {
  return (
    <div className="guide-page">
      <p className="guide-intro">Everything RFP Rockstar can do, in the
        order a deal actually happens. Lines starting with “Try:” are
        literal — say or type them to Matt.</p>
      {SECTIONS.map((s) => (
        <div key={s.title} className="guide-card">
          <h2>{s.icon} {s.title}</h2>
          <dl>
            {s.items.map(([term, def]) => (
              <React.Fragment key={term}>
                <dt>{term}</dt>
                <dd>{def}</dd>
              </React.Fragment>
            ))}
          </dl>
        </div>
      ))}
      <p className="guide-foot">Lost? Just ask Matt “what can you do?” —
        he’ll walk you through it.</p>
    </div>
  )
}
