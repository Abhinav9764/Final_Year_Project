import React, { useEffect, useRef, useState } from 'react'

/* ── Step metadata ─────────────────────────────────────────────────────────── */
const STEPS = {
  parse:      { color: '#7c6dfa', icon: '🔍', label: 'Parse' },
  search:     { color: '#00b4d8', icon: '🔎', label: 'Search' },
  score:      { color: '#00e8c8', icon: '⭐', label: 'Score' },
  download:   { color: '#48cae4', icon: '📥', label: 'Download' },
  merge:      { color: '#90e0ef', icon: '🔗', label: 'Merge' },
  upload:     { color: '#ffb54a', icon: '☁️',  label: 'Upload' },
  preprocess: { color: '#c084fc', icon: '⚙️',  label: 'Preprocess' },
  sagemaker:  { color: '#f065ad', icon: '🤖', label: 'SageMaker' },
  understand: { color: '#a78bfa', icon: '🧠', label: 'Understand' },
  plan:       { color: '#60a5fa', icon: '📐', label: 'Plan' },
  codegen:    { color: '#fb923c', icon: '💻', label: 'CodeGen' },
  validate:   { color: '#34d399', icon: '✅', label: 'Validate' },
  repair:     { color: '#fbbf24', icon: '🔧', label: 'Repair' },
  collection: { color: '#74b9ff', icon: '📦', label: 'Collect' },
  done:       { color: '#00e8c8', icon: '🎉', label: 'Done' },
  error:      { color: '#ff5070', icon: '❌', label: 'Error' },
  debug:      { color: '#6b7280', icon: '🔬', label: 'Debug' },
  info:       { color: '#5a5a80', icon: '·',  label: 'Info' },
}
const DEFAULT_STEP = { color: '#5a5a80', icon: '·', label: 'Log' }

const PIPELINE_STAGES = [
  { key: 'parse',      label: 'Parse'      },
  { key: 'search',     label: 'Search'     },
  { key: 'download',   label: 'Download'   },
  { key: 'merge',      label: 'Merge'      },
  { key: 'upload',     label: 'Upload'     },
  { key: 'preprocess', label: 'Preprocess' },
  { key: 'sagemaker',  label: 'Train'      },
  { key: 'understand', label: 'Understand' },
  { key: 'plan',       label: 'Plan'       },
  { key: 'codegen',    label: 'Generate'   },
  { key: 'validate',   label: 'Validate'   },
]

/* ── Parse an "Intent classified →" message into structured fields ────────── */
function parseIntentLine(msg) {
  if (!msg.includes('Intent classified')) return null
  const intent   = msg.match(/intent=(\S+)/i)?.[1]?.replace(/[^A-Z_a-z]/g, '')
  const task     = msg.match(/task=(\S+)/i)?.[1]?.replace(/[^A-Z_a-z]/g, '')
  const domain   = msg.match(/domain='([^']+)'/i)?.[1]
  return intent && task ? { intent, task, domain } : null
}

const TASK_COLORS = {
  REGRESSION:     '#fb923c',
  CLASSIFICATION: '#34d399',
  CLUSTERING:     '#a78bfa',
  CHATBOT:        '#00b4d8',
}
const INTENT_COLORS = {
  ML_MODEL: '#7c6dfa',
  CHATBOT:  '#00b4d8',
}

/* ── Intent Classification Card ──────────────────────────────────────────── */
function IntentCard({ intent, task, domain }) {
  const tc = TASK_COLORS[task]   || '#e4e4f0'
  const ic = INTENT_COLORS[intent] || '#7c6dfa'
  return (
    <div style={{
      margin: '8px 18px', padding: '10px 14px',
      background: 'rgba(124,109,250,0.07)',
      border: '1px solid rgba(124,109,250,0.25)',
      borderRadius: 10,
      display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center',
    }}>
      <span style={{ fontSize: 11, color: '#a78bfa', fontWeight: 700,
                     fontFamily: 'var(--font-mono)', letterSpacing: 0.5 }}>
        🧠 INTENT CLASSIFIED
      </span>
      <Badge label="Intent" value={intent} color={ic} />
      <Badge label="Task"   value={task}   color={tc} />
      {domain && <Badge label="Domain" value={domain} color="#e4e4f0" />}
    </div>
  )
}

function Badge({ label, value, color }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '2px 9px', borderRadius: 20, fontSize: 11,
      background: `${color}18`, border: `1px solid ${color}44`,
      fontFamily: 'var(--font-mono)',
    }}>
      <span style={{ color: '#9094b0', fontSize: 10 }}>{label}:</span>
      <span style={{ color, fontWeight: 700 }}>{value}</span>
    </span>
  )
}

/* ── Main component ───────────────────────────────────────────────────────── */
export default function LiveLog({ logs = [], status }) {
  const bottomRef = useRef(null)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs.length])

  const reachedSteps = new Set(logs.map(l => l.step))
  const currentStep  = logs.length > 0 ? logs[logs.length - 1].step : null

  const filtered = filter === 'all' ? logs : logs.filter(l => l.step === filter)

  const stepCounts = {}
  logs.forEach(l => { stepCounts[l.step] = (stepCounts[l.step] || 0) + 1 })

  // Extract the intent classification from parse logs
  let intentInfo = null
  for (const log of logs) {
    if (log.step === 'parse') {
      intentInfo = parseIntentLine(log.message)
      if (intentInfo) break
    }
  }

  return (
    <div style={{
      background: 'rgba(18, 18, 26, 0.45)', backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)', border: '1px solid rgba(42, 42, 62, 0.6)',
      borderRadius: 16, overflow: 'hidden',
      boxShadow: '0 4px 24px rgba(0,0,0,0.3)',
    }}>
      {/* ── Header ── */}
      <div style={{
        padding: '12px 18px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 10,
        background: 'linear-gradient(90deg,var(--surface2) 0%,var(--surface) 100%)',
      }}>
        <PipelineDot status={status} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11,
                       color: 'var(--text2)', letterSpacing: 1 }}>PIPELINE LOG</span>
        <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)',
                       fontSize: 11, color: 'var(--text3)' }}>
          {logs.length} events
        </span>
      </div>

      {/* ── Progress stepper ── */}
      <div style={{ padding: '10px 18px', borderBottom: '1px solid var(--border)', overflowX: 'auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 0, minWidth: 'max-content' }}>
          {PIPELINE_STAGES.map((stage, i) => {
            const reached = reachedSteps.has(stage.key)
            const active  = currentStep === stage.key && status === 'running'
            const isDone  = status === 'done'
            const meta    = STEPS[stage.key] || DEFAULT_STEP
            return (
              <React.Fragment key={stage.key}>
                <button
                  onClick={() => setFilter(filter === stage.key ? 'all' : stage.key)}
                  style={{
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
                    padding: '4px 8px', borderRadius: 8, border: 'none',
                    background: 'none', cursor: 'pointer',
                    opacity: reached || isDone ? 1 : 0.3,
                    transform: active ? 'translateY(-1px)' : 'none', transition: 'opacity 0.2s,transform 0.15s',
                  }}
                >
                  <div style={{
                    width: 28, height: 28, borderRadius: '50%',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13,
                    background: reached || isDone ? `${meta.color}22` : 'var(--border)',
                    border: `2px solid ${active ? meta.color : reached ? `${meta.color}66` : 'transparent'}`,
                    boxShadow: active ? `0 0 10px ${meta.color}66` : 'none',
                    transition: 'all 0.3s', animation: active ? 'pulse-ring 2s infinite' : 'none',
                  }}>{meta.icon}</div>
                  <span style={{
                    fontSize: 9, fontFamily: 'var(--font-mono)',
                    color: reached || isDone ? meta.color : 'var(--text3)',
                    whiteSpace: 'nowrap', fontWeight: active ? 700 : 400,
                  }}>{stage.label}</span>
                </button>
                {i < PIPELINE_STAGES.length - 1 && (
                  <div style={{
                    height: 1, width: 16, flexShrink: 0, marginBottom: 20,
                    background: reachedSteps.has(PIPELINE_STAGES[i+1]?.key)
                      ? 'var(--violet)' : 'var(--border)',
                    transition: 'background 0.5s',
                  }} />
                )}
              </React.Fragment>
            )
          })}
        </div>
      </div>

      {/* ── Intent Classification Card (appears after parse step) ── */}
      {intentInfo && <IntentCard {...intentInfo} />}

      {/* ── Filter bar ── */}
      {logs.length > 0 && (
        <div style={{
          padding: '6px 18px', borderBottom: '1px solid var(--border)',
          display: 'flex', gap: 6, overflowX: 'auto', background: 'var(--bg)',
        }}>
          <FilterChip label="All" count={logs.length} active={filter === 'all'}
            color="var(--text2)" onClick={() => setFilter('all')} />
          {Object.entries(stepCounts).map(([step, count]) => {
            const meta = STEPS[step] || DEFAULT_STEP
            return (
              <FilterChip key={step} label={meta.label} count={count}
                active={filter === step} color={meta.color}
                onClick={() => setFilter(filter === step ? 'all' : step)} />
            )
          })}
        </div>
      )}

      {/* ── Log entries ── */}
      <div style={{
        height: 300, overflowY: 'auto', padding: '8px 0',
        fontFamily: 'var(--font-mono)', fontSize: 12.5, lineHeight: 1.7,
      }}>
        {logs.length === 0 ? (
          <div style={{ padding: '32px 18px', color: 'var(--text3)', textAlign: 'center' }}>
            <div style={{ fontSize: 24, marginBottom: 8, opacity: 0.4 }}>⏳</div>
            <div>Waiting for pipeline to start…</div>
          </div>
        ) : filtered.map((log, i) => {
          const meta   = STEPS[log.step] || DEFAULT_STEP
          const isLast = i === filtered.length - 1 && status === 'running'
          // Skip the verbose intent line (we show it as a card above)
          const isIntentLine = log.step === 'parse' && log.message.includes('Intent classified')
          return (
            <div key={i} style={{
              display: 'flex', gap: 10, padding: '2px 18px', alignItems: 'flex-start',
              background: isLast ? 'rgba(124,109,250,0.04)' : 'transparent',
              animation: i === logs.length - 1 ? 'fadeIn 0.2s ease' : 'none',
              opacity: isIntentLine ? 0.4 : 1,
            }}>
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700,
                letterSpacing: 0.5, color: meta.color, flexShrink: 0,
                minWidth: 72, paddingTop: 3, textTransform: 'uppercase',
              }}>{meta.label}</span>
              <span style={{
                color: log.step === 'error' ? 'var(--error)' :
                       log.step === 'done'  ? 'var(--success)' : 'var(--text2)',
                wordBreak: 'break-all', flex: 1, fontSize: 12,
              }}>
                {log.message}
                {isLast && <BlinkCursor />}
              </span>
            </div>
          )
        })}
        <div ref={bottomRef} />
      </div>

      {/* ── Status bar ── */}
      <div style={{
        padding: '8px 18px', borderTop: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 8, background: 'var(--bg)',
      }}>
        <PipelineDot status={status} />
        <span style={{ fontSize: 11, color: 'var(--text3)', fontFamily: 'var(--font-mono)' }}>
          {status === 'running' ? 'Pipeline running…'       :
           status === 'done'    ? 'Completed successfully'  :
           status === 'error'   ? 'Failed — see error above' : 'Idle'}
        </span>
        {status === 'running' && (
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 3, alignItems: 'center' }}>
            {[0,1,2].map(n => (
              <div key={n} style={{
                width: 4, height: 4, borderRadius: '50%', background: 'var(--violet)',
                animation: `blink 1.2s ${n * 0.2}s infinite`,
              }} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function PipelineDot({ status }) {
  const map = { running: '#ffb54a', done: '#00e8c8', error: '#ff5070', queued: '#5a5a80' }
  const c   = map[status] || '#5a5a80'
  return (
    <span style={{
      width: 7, height: 7, borderRadius: '50%', background: c,
      display: 'inline-block', flexShrink: 0,
      boxShadow: status === 'running' ? `0 0 8px ${c}` : 'none',
    }} />
  )
}

function FilterChip({ label, count, active, color, onClick }) {
  return (
    <button onClick={onClick} style={{
      padding: '2px 10px', borderRadius: 20, cursor: 'pointer',
      background: active ? `${color}22` : 'transparent',
      color:      active ? color : 'var(--text3)',
      border:     `1px solid ${active ? `${color}44` : 'transparent'}`,
      fontSize: 10, fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap',
      transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: 4,
    }}>
      {label}
      <span style={{
        background: active ? `${color}33` : 'var(--border)',
        borderRadius: 20, padding: '0 5px', fontSize: 9,
        color: active ? color : 'var(--text3)',
      }}>{count}</span>
    </button>
  )
}

function BlinkCursor() {
  return (
    <span style={{
      display: 'inline-block', width: 7, height: 12,
      background: 'var(--violet)', marginLeft: 3,
      verticalAlign: 'text-bottom', animation: 'blink 1s step-end infinite',
    }} />
  )
}

