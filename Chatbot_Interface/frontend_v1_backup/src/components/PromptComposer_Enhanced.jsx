// PromptComposer.jsx — ENHANCED VERSION
// Features: Draft saving, keyboard shortcuts, better UX

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
const DRAFT_KEY = 'radml_prompt_draft'
const DRAFT_FILE_KEY = 'radml_draft_file'

export default function PromptComposer({ onSubmit, onSubmitWithFile, onStop, disabled, pinned, activeJobId }) {
  const [text, setText]       = useState('')
  const [focused, setFocused] = useState(false)
  const [file, setFile]       = useState(null)
  const [fileErr, setFileErr] = useState('')
  const [stopping, setStopping] = useState(false)
  const [draftRestored, setDraftRestored] = useState(false)
  const [showDraftNotice, setShowDraftNotice] = useState(false)
  const textareaRef            = useRef(null)
  const fileInputRef           = useRef(null)

  // ─────────────────────────────────────────────────────────────────
  // Draft Saving: Save to localStorage on change
  // ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!draftRestored) return
    const timer = setTimeout(() => {
      localStorage.setItem(DRAFT_KEY, text)
    }, 500) // debounce
    return () => clearTimeout(timer)
  }, [text, draftRestored])

  // ─────────────────────────────────────────────────────────────────
  // Restore Draft on Mount
  // ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    const draft = localStorage.getItem(DRAFT_KEY)
    if (draft && !disabled && !pinned) {
      setText(draft)
      setShowDraftNotice(true)
      setDraftRestored(true)
      // Hide notice after 4 seconds
      setTimeout(() => setShowDraftNotice(false), 4000)
    } else {
      setDraftRestored(true)
    }
  }, [])

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current; if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }, [text])

  useEffect(() => { if (!disabled && !pinned) textareaRef.current?.focus() }, [disabled, pinned])

  // ─────────────────────────────────────────────────────────────────
  // Clear Draft
  // ─────────────────────────────────────────────────────────────────
  const clearDraft = () => {
    setText('')
    localStorage.removeItem(DRAFT_KEY)
    setShowDraftNotice(false)
  }

  const handleSubmit = () => {
    const t = text.trim(); if (!t || disabled) return
    if (file) {
      onSubmitWithFile?.(t, file)
    } else {
      onSubmit(t)
    }
    setText(''); setFile(null)
    clearDraft()
  }

  const handleKey = (e) => {
    // Enter to submit (unless Shift+Enter for newline)
    if (e.key === 'Enter' && !e.shiftKey) { 
      e.preventDefault()
      handleSubmit() 
    }
    // Cmd/Ctrl+K to clear
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault()
      clearDraft()
    }
    // Escape to blur
    if (e.key === 'Escape') {
      setFocused(false)
      textareaRef.current?.blur()
    }
  }

  const handleFileChange = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    if (!f.name.toLowerCase().endsWith('.csv')) {
      setFileErr('Only CSV files are supported.')
      setFile(null)
      return
    }
    if (f.size > 50 * 1024 * 1024) {
      setFileErr('File too large. Max 50 MB.')
      setFile(null)
      return
    }
    setFileErr('')
    setFile(f)
    if (!text.trim()) {
      setText(`Build an ML model using the uploaded dataset: ${f.name.replace('.csv','')}`)
    }
    e.target.value = ''
  }

  const handleStop = async () => {
    if (!activeJobId || stopping) return
    setStopping(true)
    await onStop?.(activeJobId)
    setStopping(false)
  }

  const removeFile = () => { 
    setFile(null)
    setFileErr('') 
  }

  return (
    <div style={{ width: '100%', maxWidth: 760 }}>
      {/* Draft Restore Notice */}
      {showDraftNotice && text && (
        <div style={{
          marginBottom: 12, padding: '8px 12px', borderRadius: 8, fontSize: 12,
          background: 'rgba(0,232,200,0.08)', border: '1px solid rgba(0,232,200,0.2)',
          color: 'var(--cyan)', display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <span>💾</span>
          <span>Draft restored from last session</span>
          <button 
            onClick={clearDraft}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--cyan)', fontSize: 11, marginLeft: 'auto',
              textDecoration: 'underline',
            }}
          >
            Clear
          </button>
        </div>
      )}

      {/* Starter prompts */}
      {!pinned && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8, marginBottom: 20 }}>
          {STARTERS.map(s => (
            <button 
              key={s.text} 
              onClick={() => { setText(s.text); textareaRef.current?.focus() }}
              title="Click to use this starter prompt"
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
          <button 
            onClick={removeFile} 
            title="Remove file"
            style={{
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
          color: 'var(--error)', display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <span>⚠️</span> {fileErr}
        </div>
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
          ref={textareaRef} 
          value={text}
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
          aria-label="ML model description"
          title="Enter your ML model description. Shift+Enter for newline, Cmd/Ctrl+K to clear draft"
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

          {/* ── Upload CSV button ── */}
          <input
            ref={fileInputRef} type="file" accept={ACCEPTED_TYPES}
            onChange={handleFileChange} style={{ display: 'none' }}
            aria-hidden="true"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled}
            title="Upload your own CSV dataset (skips data collection)"
            aria-label="Upload CSV file"
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
             '↵ Send · ⇧↵ Newline · 📎 Upload CSV · ⌘K Clear'}
          </span>

          {/* ── Stop button ── */}
          {disabled && (
            <button
              type="button"
              onClick={handleStop}
              disabled={stopping}
              title="Stop the current pipeline"
              aria-label="Stop pipeline"
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
              {stopping ? <span>⏹</span> : <StopIcon />}
            </button>
          )}

          {/* ── Send / Run button ── */}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!text.trim() || disabled}
            title={file ? 'Run with uploaded dataset (skips data collection)' : 'Run pipeline (↵)'}
            aria-label={file ? 'Run with dataset' : 'Run pipeline'}
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

function UploadIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
}

function StopIcon() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><rect x="6" y="6" width="12" height="12"/></svg>
}

function SmallSpinner() {
  return <div style={{ width: 14, height: 14, border: '2px solid rgba(255,255,255,0.2)', borderTop: '2px solid white', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
}
