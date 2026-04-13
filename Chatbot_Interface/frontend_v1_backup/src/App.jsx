import React, { useEffect, useState, useCallback } from 'react'
import { AuthContext, useAuthProvider } from './hooks/useAuth.js'
import { usePipeline }   from './hooks/usePipeline.js'
import { ToastProvider } from './components/Toast.jsx'
import AuthPage          from './components/AuthPage.jsx'
import Sidebar           from './components/Sidebar.jsx'
import PromptComposer    from './components/PromptComposer.jsx'
import LiveLog           from './components/LiveLog.jsx'
import ResultCard        from './components/ResultCard.jsx'
import DebugPanel        from './components/DebugPanel.jsx'

/* ─────────────────────────────────────────────────────────────────────────────
   Root — wraps everything in AuthContext and ToastProvider
───────────────────────────────────────────────────────────────────────────── */
export default function Root() {
  const auth = useAuthProvider()
  return (
    <AuthContext.Provider value={auth}>
      <ToastProvider>
        <App />
      </ToastProvider>
    </AuthContext.Provider>
  )
}

/* ─────────────────────────────────────────────────────────────────────────────
   App — shows AuthPage OR ChatApp depending on auth state
───────────────────────────────────────────────────────────────────────────── */
function App() {
  const { user, loading, logout, getToken } = React.useContext(AuthContext)

  if (loading) return <SplashScreen />
  if (!user)   return <AuthPage />
  return <ChatApp user={user} logout={logout} getToken={getToken} />
}

/* ─────────────────────────────────────────────────────────────────────────────
   ChatApp — the main experience after login
───────────────────────────────────────────────────────────────────────────── */
function ChatApp({ user, logout, getToken }) {
  const [sidebarOpen, setSidebar] = useState(true)
  const [showDebug,   setShowDebug] = useState(false)
  const {
    jobs, activeJob,
    runPipeline, runPipelineWithFile, stopPipeline,
    loadHistory, selectJob, deleteJob, deleteAllHistory,
  } = usePipeline(getToken)

  useEffect(() => {
    loadHistory()
  }, [loadHistory, user?.id])

  useEffect(() => {
    const intervalId = setInterval(() => {
      loadHistory()
    }, 10000)
    return () => clearInterval(intervalId)
  }, [loadHistory])

  const hasActive = Boolean(activeJob)
  const isRunning = activeJob?.status === 'running' || activeJob?.status === 'queued'
  const SW        = sidebarOpen ? 'var(--sidebar-w)' : '0px'

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg)' }}>

      {/* ── Sidebar ── */}
      <Sidebar
        user={user}
        jobs={jobs}
        activeId={activeJob?.id || activeJob?.job_id}
        onSelect={selectJob}
        onDelete={deleteJob}
        onDeleteAll={deleteAllHistory}
        onLogout={logout}
        open={sidebarOpen}
      />

      {/* ── Backdrop for mobile ── */}
      {sidebarOpen && (
        <div
          onClick={() => setSidebar(false)}
          style={{
            display: 'none',
            position: 'fixed', inset: 0,
            background: 'rgba(0,0,0,0.5)', zIndex: 15,
          }}
          className="mobile-backdrop"
        />
      )}

      {/* ── Main ── */}
      <main style={{
        flex: 1,
        marginLeft: SW,
        transition: 'margin-left 0.28s cubic-bezier(0.4,0,0.2,1)',
        display: 'flex', flexDirection: 'column',
        minHeight: '100vh', position: 'relative',
      }}>

        {/* ── Topbar ── */}
        <header style={{
          padding: '0 22px',
          height: 56,
          display: 'flex', alignItems: 'center', gap: 14,
          borderBottom: '1px solid var(--border)',
          background: 'rgba(8,8,16,0.85)',
          backdropFilter: 'blur(16px)',
          position: 'sticky', top: 0, zIndex: 10,
          WebkitBackdropFilter: 'blur(16px)',
        }}>
          {/* Hamburger */}
          <button
            onClick={() => setSidebar(v => !v)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--text3)', padding: 6, borderRadius: 8,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'color 0.15s, background 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = 'var(--text)'; e.currentTarget.style.background = 'var(--border)' }}
            onMouseLeave={e => { e.currentTarget.style.color = 'var(--text3)'; e.currentTarget.style.background = 'none' }}
          >
            <HamburgerIcon open={sidebarOpen} />
          </button>

          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 26, height: 26,
              background: 'linear-gradient(135deg, var(--violet), var(--cyan))',
              borderRadius: 7, display: 'flex', alignItems: 'center',
              justifyContent: 'center', flexShrink: 0,
            }}>
              <span style={{
                fontFamily: 'var(--font-display)', fontWeight: 800,
                color: '#fff', fontSize: 12,
              }}>R</span>
            </div>
            <span style={{
              fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 16,
              background: 'linear-gradient(135deg, var(--violet), var(--cyan))',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              letterSpacing: -0.3,
            }}>RAD-ML</span>
          </div>

          {/* Greeting */}
          {!hasActive && (
            <span style={{
              fontSize: 13, color: 'var(--text3)',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <span style={{ display: 'none' }}>·</span>
            </span>
          )}

          {/* Active job status */}
          {hasActive && activeJob && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              marginLeft: 8, overflow: 'hidden',
            }}>
              <StatusPill status={activeJob.status} />
              <span style={{
                fontSize: 12, color: 'var(--text3)',
                maxWidth: 260, overflow: 'hidden',
                textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>{activeJob.prompt}</span>
            </div>
          )}

          {/* New conversation button */}
          {/* Debug button */}
          <button
            onClick={() => setShowDebug(v => !v)}
            title="System Diagnostics"
            style={{
              marginLeft: hasActive ? 8 : 'auto',
              padding: '5px 12px',
              background: showDebug ? '#2d1b6e' : 'var(--surface)',
              border: `1px solid ${showDebug ? 'var(--violet)' : 'var(--border)'}`,
              borderRadius: 8, cursor: 'pointer',
              color: showDebug ? '#a78bfa' : 'var(--text3)',
              fontSize: 12, fontWeight: 600, transition: 'all 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--violet)'; e.currentTarget.style.color = '#a78bfa' }}
            onMouseLeave={e => {
              if (!showDebug) {
                e.currentTarget.style.borderColor = 'var(--border)';
                e.currentTarget.style.color = 'var(--text3)';
              }
            }}
          >
            🔬 Debug
          </button>
          {hasActive && (
            <button
              onClick={() => selectJob(null)}
              style={{
                marginLeft: 8, padding: '6px 16px',
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: 8, cursor: 'pointer',
                color: 'var(--text2)', fontSize: 12, fontWeight: 500,
                transition: 'all 0.15s', flexShrink: 0,
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--violet)'; e.currentTarget.style.color = 'var(--text)' }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text2)' }}
            >
              + New
            </button>
          )}
        </header>

        {/* ── Body ── */}
        <div style={{
          flex: 1,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center',
          justifyContent: hasActive ? 'flex-start' : 'center',
          padding: hasActive ? '28px 24px 160px' : '0 24px 80px',
          maxWidth: 860, width: '100%', margin: '0 auto',
          boxSizing: 'border-box',
        }}>

          {/* ── Welcome state ── */}
          {!hasActive && (
            <div style={{ width: '100%', animation: 'fadeSlideUp 0.4s ease both' }}>
              {/* Greeting */}
              <div style={{ textAlign: 'center', marginBottom: 48 }}>
                <div style={{
                  fontSize: 48, marginBottom: 6,
                  animation: 'float 4s ease-in-out infinite',
                }}>👋</div>
                <h1 style={{
                  fontFamily: 'var(--font-display)', fontWeight: 800,
                  fontSize: 'clamp(28px, 5vw, 40px)',
                  lineHeight: 1.15, marginBottom: 10,
                  background: 'linear-gradient(135deg, var(--text) 0%, var(--violet) 50%, var(--cyan) 100%)',
                  WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
                  backgroundSize: '200% auto',
                  animation: 'shimmer 4s linear infinite',
                }}>
                  Hello, {user?.username}!
                </h1>
                <p style={{
                  color: 'var(--text2)', fontSize: 15,
                  maxWidth: 480, margin: '0 auto', lineHeight: 1.7,
                }}>
                  Describe an ML problem in plain English. I'll find the data,
                  train the model on AWS, and deploy a live app — automatically.
                </p>
              </div>

              <PromptComposer
                onSubmit={runPipeline}
                onSubmitWithFile={runPipelineWithFile}
                onStop={stopPipeline}
                disabled={isRunning}
                pinned={false}
                activeJobId={activeJob?.id || activeJob?.job_id}
              />
              {showDebug && <DebugPanel token={getToken ? getToken() : null} />}
            </div>
          )}
          {/* Debug panel in active state */}
          {showDebug && hasActive && (
            <div style={{ width: '100%', marginBottom: 16 }}>
              <DebugPanel token={getToken ? getToken() : null} />
            </div>
          )}

          {/* ── Active job view ── */}
          {hasActive && activeJob && (
            <div style={{ width: '100%', animation: 'fadeSlideUp 0.3s ease both' }}>

              {/* Prompt bubble */}
              <div style={{
                background: 'linear-gradient(135deg, rgba(124,109,250,0.08), rgba(0,232,200,0.04))',
                border: '1px solid rgba(124,109,250,0.2)',
                borderRadius: 14, padding: '14px 18px', marginBottom: 18,
                display: 'flex', alignItems: 'flex-start', gap: 12,
              }}>
                <div style={{
                  width: 28, height: 28, borderRadius: '50%',
                  background: 'linear-gradient(135deg, var(--violet), var(--cyan))',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 12, fontFamily: 'var(--font-display)',
                  fontWeight: 800, color: '#fff', flexShrink: 0,
                }}>
                  {user?.username?.[0]?.toUpperCase() || 'U'}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontSize: 11, color: 'var(--violet)',
                    fontFamily: 'var(--font-mono)', marginBottom: 4,
                    letterSpacing: 0.5,
                  }}>YOU</div>
                  <div style={{ fontSize: 14, color: 'var(--text)', lineHeight: 1.6 }}>
                    {activeJob.prompt}
                  </div>
                </div>
              </div>

              {/* RAD-ML response */}
              <div style={{
                display: 'flex', alignItems: 'flex-start', gap: 12,
                marginBottom: 16,
              }}>
                <div style={{
                  width: 28, height: 28, borderRadius: '50%',
                  background: 'linear-gradient(135deg, var(--violet), var(--cyan))',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 14, flexShrink: 0,
                }}>🤖</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 11, color: 'var(--cyan)',
                    fontFamily: 'var(--font-mono)', marginBottom: 8,
                    letterSpacing: 0.5,
                  }}>RAD-ML</div>

                  {/* Live log */}
                  <LiveLog logs={activeJob.logs || []} status={activeJob.status} />

                  {/* Error */}
                  {activeJob.status === 'error' && activeJob.error && (
                    <div style={{
                      marginTop: 14,
                      background: 'rgba(255,80,112,0.06)',
                      border: '1px solid rgba(255,80,112,0.25)',
                      borderRadius: 12, padding: '14px 16px',
                    }}>
                      <div style={{
                        fontFamily: 'var(--font-mono)', fontSize: 11,
                        color: 'var(--error)', marginBottom: 6,
                        letterSpacing: 0.5,
                      }}>ERROR</div>
                      <div style={{
                        color: 'var(--error)', fontSize: 13,
                        fontFamily: 'var(--font-mono)', wordBreak: 'break-word',
                        lineHeight: 1.6,
                      }}>{activeJob.error}</div>
                    </div>
                  )}

                  {/* Result card */}
                  {activeJob.status === 'done' && activeJob.result && (
                    <ResultCard
                      result={activeJob.result}
                      jobId={activeJob.id || activeJob.job_id}
                      getToken={getToken}
                    />
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── Bottom-pinned composer ── */}
        <div style={{
          position: 'fixed', bottom: 0,
          left: sidebarOpen ? 'var(--sidebar-w)' : '0px',
          right: 0,
          padding: '10px 24px 20px',
          background: 'linear-gradient(to top, var(--bg) 55%, transparent)',
          display: 'flex', justifyContent: 'center',
          transition: 'left 0.28s cubic-bezier(0.4,0,0.2,1)',
          pointerEvents: hasActive ? 'auto' : 'none',
          opacity: hasActive ? 1 : 0,
        }}>
          <PromptComposer onSubmit={runPipeline} disabled={isRunning} pinned />
        </div>
      </main>
    </div>
  )
}

/* ─────────────────────────────────────────────────────────────────────────────
   Small atoms
───────────────────────────────────────────────────────────────────────────── */
function SplashScreen() {
  return (
    <div style={{
      minHeight: '100vh', display: 'flex',
      alignItems: 'center', justifyContent: 'center',
      flexDirection: 'column', gap: 16, background: 'var(--bg)',
    }}>
      <div style={{
        width: 48, height: 48,
        background: 'linear-gradient(135deg, var(--violet), var(--cyan))',
        borderRadius: 14, display: 'flex', alignItems: 'center',
        justifyContent: 'center', animation: 'float 2s ease-in-out infinite',
      }}>
        <span style={{
          fontFamily: 'var(--font-display)', fontWeight: 800,
          color: '#fff', fontSize: 22,
        }}>R</span>
      </div>
      <div style={{
        display: 'flex', gap: 5, alignItems: 'center',
      }}>
        {[0,1,2].map(i => (
          <div key={i} style={{
            width: 6, height: 6, borderRadius: '50%',
            background: 'var(--violet)',
            animation: `blink 1.2s ${i * 0.2}s infinite`,
          }} />
        ))}
      </div>
    </div>
  )
}

function StatusPill({ status }) {
  const map = {
    running: { bg: 'rgba(255,181,74,0.12)', border: 'rgba(255,181,74,0.3)',  color: '#ffb54a', label: 'Running' },
    done:    { bg: 'rgba(0,232,200,0.10)',  border: 'rgba(0,232,200,0.3)',   color: '#00e8c8', label: 'Done' },
    error:   { bg: 'rgba(255,80,112,0.10)', border: 'rgba(255,80,112,0.3)', color: '#ff5070', label: 'Error' },
    queued:  { bg: 'rgba(90,90,128,0.12)',  border: 'rgba(90,90,128,0.3)',  color: '#5a5a80', label: 'Queued' },
  }
  const s = map[status] || map.queued
  return (
    <span style={{
      background: s.bg, border: `1px solid ${s.border}`, color: s.color,
      borderRadius: 20, padding: '2px 10px', fontSize: 10,
      fontWeight: 700, fontFamily: 'var(--font-mono)',
      letterSpacing: 0.5, flexShrink: 0,
    }}>{s.label}</span>
  )
}

function HamburgerIcon({ open }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <line x1="2" y1="4.5"  x2="16" y2="4.5"  stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"
        style={{ transition: 'all 0.2s', transformOrigin: '9px 4.5px',
          transform: open ? 'rotate(45deg) translate(0px, 4.5px)' : 'none' }} />
      <line x1="2" y1="9"    x2="16" y2="9"     stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"
        style={{ opacity: open ? 0 : 1, transition: 'opacity 0.15s' }} />
      <line x1="2" y1="13.5" x2="16" y2="13.5"  stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"
        style={{ transition: 'all 0.2s', transformOrigin: '9px 13.5px',
          transform: open ? 'rotate(-45deg) translate(0px, -4.5px)' : 'none' }} />
    </svg>
  )
}
