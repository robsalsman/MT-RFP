import React, { useEffect, useRef, useState } from 'react'

const WELCOME = {
  role: 'assistant',
  content: "Hi — I'm the MT-RFP Assistant. Ask me anything about the app or " +
    'your RFP pipeline, or tell me what to do: "show open RFPs in Ohio", ' +
    '"which deals close this week?", "generate a draft for Shaker Heights", ' +
    '"make Texas a priority state", "take me to the price list upload".',
}

export default function ChatBot() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([WELCOME])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const bodyRef = useRef(null)

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [messages, open, busy])

  const send = async () => {
    const text = input.trim()
    if (!text || busy) return
    const next = [...messages, { role: 'user', content: text }]
    setMessages(next)
    setInput('')
    setBusy(true)
    try {
      const r = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: next.filter((m) => m !== WELCOME)
            .map(({ role, content }) => ({ role, content })),
        }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail || 'request failed')
      setMessages((m) => [...m, {
        role: 'assistant', content: d.reply, toolLog: d.tool_log,
      }])
      if (d.navigate) {
        window.dispatchEvent(new CustomEvent('mtrfp:navigate',
          { detail: d.navigate }))
      }
    } catch (e) {
      setMessages((m) => [...m, {
        role: 'assistant', content: `Something went wrong: ${e.message}`,
      }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button className="chat-fab" onClick={() => setOpen(!open)}
        title="MT-RFP Assistant">
        {open ? '✕' : '💬'}
      </button>
      {open && (
        <div className="chat-panel">
          <div className="chat-head">
            MT-RFP Assistant
            <span className="small"> — natural-language help & actions</span>
          </div>
          <div className="chat-body" ref={bodyRef}>
            {messages.map((m, i) => (
              <div key={i} className={`chat-msg ${m.role}`}>
                {m.content}
                {m.toolLog?.length > 0 && (
                  <div className="chat-tools">
                    {m.toolLog.map((t, j) => (
                      <span key={j} className={t.ok ? '' : 'err'}>
                        ⚙ {t.tool}
                      </span>))}
                  </div>
                )}
              </div>
            ))}
            {busy && <div className="chat-msg assistant">Working…</div>}
          </div>
          <div className="chat-input">
            <input value={input} disabled={busy}
              placeholder='e.g. "what closes this week?"'
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && send()} />
            <button className="primary" onClick={send}
              disabled={busy || !input.trim()}>Send</button>
          </div>
        </div>
      )}
    </>
  )
}
