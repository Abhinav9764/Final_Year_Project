import React, { useState } from 'react'

const STATUS = {
  queued:  { color: '#5a5a80', label: 'Queued' },
  running: { color: '#ffb54a', label: 'Running' },
  done:    { color: '#00e8c8', label: 'Done' },
  error:   { color: '#ff5070', label: 'Error' },
}

export default function Sidebar({ user, jobs, activeId, onSelect, onDelete, onDeleteAll, onLogout, open }) {
  const [confirmClear, setConfirmClear] = useState(false)

  const handleClearAll = () => {
    if (confirmClear) { onDeleteAll(); setConfirmClear(false) }
    else { setConfirmClear(true); setTimeout(() => setConfirmClear(false), 3000) }
  }

  return (
    <aside style={{
      width: open ? 'var(--sidebar-w)' : 0,
      minWidth: open ? 'var(--sidebar-w)' : 0,
      overflow: 'hidden',
      transition: 'width 0.28s cubic-bezier(0.4,0,0.2,1), min-width 0.28s cubic-bezier(0.4,0,0.2,1)',
      background: 'var(--surface)',
      borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column',
      height: '100vh',
      position: 'fixed', top: 0, left: 0, zIndex: 20,
    }}>
      {/* ── User profile ── */}
      <div style={{
        padding: '20px 16px 14px',
        borderBottom: '1px solid var(--border)',
        background: 'linear-gradient(180deg, var(--surface2) 0%, var(--surface) 100%)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
          <Avatar user={user} size={36} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontFamily: 'var(--font-display)', fontWeight: 700,
              fontSize: 14, color: 'var(--text)',
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            }}>
              {user?.username || 'User'}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 1 }}>
              {user?.email || 'Signed in'}
            </div>
          </div>
          <button onClick={onLogout} title="Sign out"
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--text3)', padding: 4, borderRadius: 6,
              transition: 'color 0.15s, background 0.15s', flexShrink: 0,
            }}
            onMouseEnter={e => { e.currentTarget.style.color = 'var(--error)'; e.currentTarget.style.background = 'rgba(255,80,112,0.08)' }}
            onMouseLeave={e => { e.currentTarget.style.color = 'var(--text3)'; e.currentTarget.style.background = 'none' }}
          >
            <LogoutIcon />
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 10,
            color: 'var(--text2)', letterSpacing: 1,
            textTransform: 'uppercase',
          }}>Chat History</span>
          {jobs.length > 0 && (
            <button onClick={handleClearAll} style={{
              background: confirmClear ? 'rgba(255,80,112,0.12)' : 'none',
              border: `1px solid ${confirmClear ? 'rgba(255,80,112,0.3)' : 'transparent'}`,
              cursor: 'pointer', borderRadius: 6, padding: '3px 8px',
              fontSize: 10, fontWeight: 500,
              color: confirmClear ? 'var(--error)' : 'var(--text3)',
              transition: 'all 0.15s',
            }}>
              {confirmClear ? 'Confirm clear' : 'Clear all'}
            </button>
          )}
        </div>
      </div>

      {/* ── History list ── */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '6px 0' }}>
        {jobs.length === 0 ? (
          <div style={{ padding: '32px 16px', textAlign: 'center' }}>
            <div style={{ fontSize: 28, marginBottom: 8, opacity: 0.3 }}>💬</div>
            <div style={{ color: 'var(--text2)', fontSize: 12, lineHeight: 1.5 }}>
              No conversations yet.<br />Start by entering a prompt below.
            </div>
          </div>
        ) : jobs.map((job, i) => (
          <HistoryItem
            key={job.id || job.job_id || i}
            job={job}
            active={activeId === (job.id || job.job_id)}
            onSelect={() => onSelect(job.id || job.job_id)}
            onDelete={() => onDelete(job.id || job.job_id)}
          />
        ))}
      </div>

      {/* ── Footer ── */}
      <div style={{
        padding: '10px 14px',
        borderTop: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 10,
          color: 'var(--text2)', letterSpacing: 0.5,
        }}>RAD-ML v2.0</span>
        <span style={{
          width: 6, height: 6, borderRadius: '50%',
          background: 'var(--success)',
          boxShadow: '0 0 6px var(--success)',
          display: 'inline-block',
        }} title="Backend connected" />
      </div>
    </aside>
  )
}

function HistoryItem({ job, active, onSelect, onDelete }) {
  const st = STATUS[job.status] || STATUS.queued
  const isRunning = job.status === 'running'
  return (
    <div
      onClick={onSelect}
      style={{
        padding: '10px 14px',
        cursor: 'pointer',
        background: active
          ? 'linear-gradient(90deg, rgba(124,109,250,0.12), transparent)'
          : 'transparent',
        borderLeft: `2px solid ${active ? 'var(--violet)' : 'transparent'}`,
        display: 'flex', alignItems: 'flex-start', gap: 10,
        transition: 'background 0.15s',
        position: 'relative',
      }}
      onMouseEnter={e => !active && (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
      onMouseLeave={e => !active && (e.currentTarget.style.background = 'transparent')}
    >
      {/* Status indicator */}
      <div style={{
        width: 7, height: 7, borderRadius: '50%', marginTop: 5,
        background: st.color, flexShrink: 0,
        boxShadow: isRunning ? `0 0 6px ${st.color}` : 'none',
        animation: isRunning ? 'pulse-ring 2s infinite' : 'none',
      }} />

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 12.5, color: active ? '#ffffff' : 'var(--text)',
          fontWeight: active ? 600 : 500,
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          lineHeight: 1.4,
        }}>
          {job.prompt || job.id || job.job_id}
        </div>
        <div style={{ fontSize: 10.5, color: 'var(--text2)', marginTop: 3 }}>
          {st.label}
          {job.created && ` · ${_relTime(job.created)}`}
        </div>
      </div>

      <button
        onClick={e => { e.stopPropagation(); onDelete() }}
        style={{
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--text3)', fontSize: 15, lineHeight: 1,
          padding: '1px 3px', flexShrink: 0, borderRadius: 4,
          opacity: 0, transition: 'opacity 0.15s, color 0.15s',
        }}
        className="del-btn"
        onMouseEnter={e => e.currentTarget.style.color = 'var(--error)'}
        onMouseLeave={e => e.currentTarget.style.color = 'var(--text3)'}
      >×</button>

      <style>{`.del-btn{opacity:0}.${active ? '' : 'history-item'}:hover .del-btn,div:hover>.del-btn{opacity:1!important}`}</style>
    </div>
  )
}

function Avatar({ user, size = 36 }) {
  const letter = (user?.username || 'U')[0].toUpperCase()
  if (user?.avatar_url) {
    return <img src={user.avatar_url} alt={letter}
      style={{ width: size, height: size, borderRadius: '50%', objectFit: 'cover',
               border: '2px solid var(--border2)' }} />
  }
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: 'linear-gradient(135deg, var(--violet), var(--cyan))',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'var(--font-display)', fontWeight: 800,
      fontSize: size * 0.42, color: '#fff', flexShrink: 0,
    }}>{letter}</div>
  )
}

function LogoutIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
      <polyline points="16 17 21 12 16 7"/>
      <line x1="21" y1="12" x2="9" y2="12"/>
    </svg>
  )
}

function _relTime(ts) {
  const d = Date.now() - (typeof ts === 'number' ? ts * 1000 : new Date(ts).getTime())
  if (d < 60000) return 'just now'
  if (d < 3600000) return `${Math.floor(d / 60000)}m ago`
  if (d < 86400000) return `${Math.floor(d / 3600000)}h ago`
  return `${Math.floor(d / 86400000)}d ago`
}
