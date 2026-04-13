import React, { useRef, useEffect, useState, useCallback } from 'react'

const STARTERS = [
  { icon: '🏠', text: 'Predict housing price based on bedrooms, bathrooms and location' },
  { icon: '🎬', text: 'Build a movie recommendation system using genre and rating' },
  { icon: '💰', text: 'Predict employee salary given experience, role and education' },
  { icon: '🏥', text: 'Classify diabetes risk using age, glucose and BMI' },
  { icon: '🚗', text: 'Predict car price based on engine size, mileage and fuel type' },
  { icon: '📈', text: 'Forecast stock trend using volume, open and close price' },
]

const ACCEPTED_TYPES = '.csv,text/csv,application/csv'

export default function PromptComposer({ onSubmit, onSubmitWithFile, onStop, disabled, pinned, activeJobId }) {
  const [text, setText]       = useState('')
  const [focused, setFocused] = useState(false)
  const [file, setFile]       = useState(null)       // uploaded CSV file object
  const [fileErr, setFileErr] = useState('')
  const [stopping, setStopping] = useState(false)
  const textareaRef            = useRef(null)
  const fileInputRef           = useRef(null)

  useEffect(() => { if (!disabled && !pinned) textareaRef.current?.focus() }, [disabled, pinned])

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current; if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }, [text])

  const handleSubmit = () => {
    const t = text.trim(); if (!t || disabled) return
    if (file) {
      onSubmitWithFile?.(t, file)
    } else {
      onSubmit(t)
    }
    setText(''); setFile(null)
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit() }
  }

  const handleFileChange = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    if (!f.name.toLowerCase().endsWith('.csv')) {
      setFileErr('Only CSV files are supported.'); setFile(null); return
    }
    if (f.size > 50 * 1024 * 1024) {
      setFileErr('File too large. Max 50 MB.'); setFile(null); return
    }
    setFileErr(''); setFile(f)
    // Suggest a prompt if empty
    if (!text.trim()) {
      setText(`Build an ML model using the uploaded dataset: ${f.name.replace('.csv','')}`)
    }
    e.target.value = ''   // reset so same file can be re-selected
  }

  const handleStop = async () => {
    if (!activeJobId || stopping) return
    setStopping(true)
    await onStop?.(activeJobId)
    setStopping(false)
  }

  const removeFile = () => { setFile(null); setFileErr('') }

  return (
    <div style={{ width: '100%', maxWidth: 760 }}>
      {/* Starter prompts */}
      {!pinned && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8, marginBottom: 20 }}>
          {STARTERS.map(s => (
            <button key={s.text} onClick={() => { setText(s.text); textareaRef.current?.focus() }}
              style={{
                background: 'var(--surface)', border: '1px solid var(--border)',
                borderRadius: 10, padding: '10px 14px', cursor: 'pointer', textAlign: 'left',
                fontSize: 12.5, color: 'var(--text2)', lineHeight: 1.45,
                display: 'flex', alignItems: 'flex-start', gap: 8, transition: 'all 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--violet)'; e.currentTarget.style.background = 'var(--violet-dim)'; e.currentTarget.style.color = 'var(--text)' }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'var(--surface)'; e.currentTarget.style.color = 'var(--text2)' }}
            >
              <span style={{ fontSize: 16, flexShrink: 0 }}>{s.icon}</span>
              <span>{s.text}</span>
            </button>
          ))}
        </div>
      )}

      {/* Uploaded file pill */}
      {file && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8,
          padding: '6px 12px', borderRadius: 20,
          background: 'rgba(0,232,200,0.08)', border: '1px solid rgba(0,232,200,0.2)',
          width: 'fit-content', maxWidth: '100%',
        }}>
          <span style={{ fontSize: 14 }}>📄</span>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--cyan)',
            maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>{file.name}</span>
          <span style={{ fontSize: 10, color: 'var(--text3)', flexShrink: 0 }}>
            ({(file.size / 1024).toFixed(0)} KB)
          </span>
          <button onClick={removeFile} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--text3)', fontSize: 14, lineHeight: 1, padding: '0 2px',
            flexShrink: 0, transition: 'color 0.15s',
          }}
            onMouseEnter={e => e.currentTarget.style.color = 'var(--error)'}
            onMouseLeave={e => e.currentTarget.style.color = 'var(--text3)'}
          >×</button>
          <span style={{
            fontSize: 9, color: 'var(--cyan)', fontWeight: 700,
            fontFamily: 'var(--font-mono)', marginLeft: 2,
            background: 'rgba(0,232,200,0.15)', borderRadius: 4, padding: '1px 5px',
          }}>SKIP COLLECTION</span>
        </div>
      )}

      {fileErr && (
        <div style={{
          marginBottom: 8, padding: '6px 12px', borderRadius: 8, fontSize: 12,
          background: 'rgba(255,80,112,0.08)', border: '1px solid rgba(255,80,112,0.2)',
          color: 'var(--error)',
        }}>{fileErr}</div>
      )}

      {/* Input box */}
      <div style={{
        background: 'var(--surface)',
        border: `1px solid ${focused ? 'var(--violet)' : file ? 'rgba(0,232,200,0.3)' : 'var(--border)'}`,
        borderRadius: 16, padding: '12px 16px 10px',
        transition: 'border-color 0.15s, box-shadow 0.15s',
        boxShadow: focused
          ? '0 0 0 3px rgba(124,109,250,0.12), 0 8px 32px rgba(0,0,0,0.3)'
          : file
            ? '0 0 0 2px rgba(0,232,200,0.08)'
            : '0 4px 16px rgba(0,0,0,0.2)',
      }}>
        <textarea
          ref={textareaRef} value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKey}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          disabled={disabled}
          placeholder={
            disabled ? 'Pipeline running… use ⊗ to stop' :
            file ? 'Describe the ML task for this dataset…' :
            'Describe the ML model you want to build…'
          }
          rows={1}
          style={{
            width: '100%', background: 'none', border: 'none', outline: 'none',
            color: disabled ? 'var(--text3)' : 'var(--text)',
            fontSize: 14, resize: 'none', lineHeight: 1.6,
            cursor: disabled ? 'not-allowed' : 'text', overflowY: 'hidden',
          }}
        />

        {/* Bottom action bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>

          {/* ── Upload CSV button (left) ── */}
          <input
            ref={fileInputRef} type="file" accept={ACCEPTED_TYPES}
            onChange={handleFileChange} style={{ display: 'none' }}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled}
            title="Upload your own CSV dataset (skips data collection)"
            style={{
              width: 34, height: 34, borderRadius: '50%', flexShrink: 0,
              border: `1px solid ${file ? 'rgba(0,232,200,0.4)' : 'var(--border)'}`,
              background: file ? 'rgba(0,232,200,0.1)' : 'transparent',
              cursor: disabled ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'all 0.15s', color: file ? 'var(--cyan)' : 'var(--text3)',
            }}
            onMouseEnter={e => { if (!disabled) { e.currentTarget.style.borderColor = 'var(--cyan)'; e.currentTarget.style.background = 'rgba(0,232,200,0.08)'; e.currentTarget.style.color = 'var(--cyan)' }}}
            onMouseLeave={e => {
              if (!file) { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text3)' }
              else { e.currentTarget.style.borderColor = 'rgba(0,232,200,0.4)'; e.currentTarget.style.background = 'rgba(0,232,200,0.1)'; e.currentTarget.style.color = 'var(--cyan)' }
            }}
          >
            <UploadIcon />
          </button>

          {/* Hint */}
          <span style={{ fontSize: 11, color: 'var(--text3)', flex: 1 }}>
            {disabled ? '⏳ Running' :
             file     ? `📄 ${file.name} · data collection skipped` :
             '↵ Send · ⇧↵ Newline · 📎 Upload CSV'}
          </span>

          {/* ── Stop button (shown when running) ── */}
          {disabled && (
            <button
              type="button"
              onClick={handleStop}
              disabled={stopping}
              title="Stop the current pipeline"
              style={{
                width: 34, height: 34, borderRadius: '50%', flexShrink: 0,
                border: '1px solid rgba(255,80,112,0.35)',
                background: stopping ? 'rgba(255,80,112,0.2)' : 'rgba(255,80,112,0.08)',
                cursor: stopping ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'all 0.15s',
                animation: stopping ? 'none' : 'pulse-ring 2s infinite',
              }}
              onMouseEnter={e => { if (!stopping) { e.currentTarget.style.background = 'rgba(255,80,112,0.2)'; e.currentTarget.style.borderColor = 'rgba(255,80,112,0.6)' }}}
              onMouseLeave={e => { if (!stopping) { e.currentTarget.style.background = 'rgba(255,80,112,0.08)'; e.currentTarget.style.borderColor = 'rgba(255,80,112,0.35)' }}}
            >
              {stopping ? <SmallSpinner /> : <StopIcon />}
            </button>
          )}

          {/* ── Send / Run button ── */}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!text.trim() || disabled}
            title={file ? 'Run with uploaded dataset (skips data collection)' : 'Run pipeline'}
            style={{
              background: !text.trim() || disabled
                ? 'var(--border)'
                : file
                  ? 'linear-gradient(135deg, #00b4a0, #007a6e)'
                  : 'linear-gradient(135deg, var(--violet), #5a4fd4)',
              border: 'none', borderRadius: 10, padding: '8px 18px',
              color: '#fff', fontSize: 13, fontWeight: 600,
              fontFamily: 'var(--font-display)', flexShrink: 0,
              cursor: !text.trim() || disabled ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s', display: 'flex', alignItems: 'center', gap: 6,
              boxShadow: !text.trim() || disabled ? 'none' :
                file ? '0 2px 12px rgba(0,180,160,0.4)' : '0 2px 12px rgba(124,109,250,0.4)',
            }}
          >
            {file ? <>Run <span style={{ fontSize: 12 }}>📄→</span></> : <>Run <span style={{ fontSize: 15 }}>→</span></>}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ── Icons ───────────────────────────────────────────────────────────────── */
function UploadIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="17 8 12 3 7 8"/>
      <line x1="12" y1="3" x2="12" y2="15"/>
    </svg>
  )
}

function StopIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="var(--error)" stroke="none">
      <rect x="4" y="4" width="16" height="16" rx="2"/>
    </svg>
  )
}

function SmallSpinner() {
  return <span style={{
    display: 'inline-block', width: 12, height: 12,
    border: '2px solid rgba(255,80,112,0.3)', borderTopColor: 'var(--error)',
    borderRadius: '50%', animation: 'spin 0.8s linear infinite',
  }} />
}
