import React, { useState, useRef, useEffect } from 'react'
import { useAuth } from '../hooks/useAuth.js'

/* ── Animated background particles ────────────────────────────────────────── */
function Particles() {
  const canvasRef = useRef(null)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let raf, w, h
    const pts = []
    const resize = () => { w = canvas.width = window.innerWidth; h = canvas.height = window.innerHeight }
    resize()
    window.addEventListener('resize', resize)
    for (let i = 0; i < 55; i++) pts.push({
      x: Math.random() * w, y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3,
      r: Math.random() * 1.5 + 0.5, a: Math.random(),
    })
    const draw = () => {
      ctx.clearRect(0, 0, w, h)
      pts.forEach(p => {
        p.x += p.vx; p.y += p.vy
        if (p.x < 0) p.x = w; if (p.x > w) p.x = 0
        if (p.y < 0) p.y = h; if (p.y > h) p.y = 0
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(124,109,250,${p.a * 0.6})`; ctx.fill()
      })
      for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) {
        const dx = pts[i].x - pts[j].x, dy = pts[i].y - pts[j].y
        const d = Math.sqrt(dx * dx + dy * dy)
        if (d < 120) {
          ctx.beginPath(); ctx.moveTo(pts[i].x, pts[i].y); ctx.lineTo(pts[j].x, pts[j].y)
          ctx.strokeStyle = `rgba(124,109,250,${(1 - d / 120) * 0.12})`; ctx.lineWidth = 0.5; ctx.stroke()
        }
      }
      raf = requestAnimationFrame(draw)
    }
    draw()
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize) }
  }, [])
  return <canvas ref={canvasRef} style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0 }} />
}

/* ── Main AuthPage ─────────────────────────────────────────────────────────── */
export default function AuthPage() {
  const { login, register } = useAuth()
  const [mode, setMode]     = useState('login')
  const [form, setForm]     = useState({ username: '', password: '', email: '' })
  const [error, setError]   = useState('')
  const [loading, setLoading] = useState(false)
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const isLogin = mode === 'login'

  const handleSubmit = async (e) => {
    e.preventDefault(); setError(''); setLoading(true)
    try {
      if (isLogin) await login(form.username, form.password)
      else await register(form.username, form.password, form.email)
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'radial-gradient(ellipse 80% 60% at 50% 0%, #1a1040 0%, var(--bg) 70%)',
      position: 'relative', overflow: 'hidden',
    }}>
      <Particles />
      <div style={{
        position: 'absolute', width: 500, height: 500, borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(124,109,250,0.07) 0%, transparent 70%)',
        top: '-100px', left: '50%', transform: 'translateX(-50%)',
        pointerEvents: 'none', zIndex: 0,
      }} />

      <div style={{ position: 'relative', zIndex: 1, width: '100%', maxWidth: 420, margin: '24px', animation: 'fadeSlideUp 0.5s ease both' }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <div style={{
              width: 42, height: 42,
              background: 'linear-gradient(135deg, #7c6dfa, #00e8c8)',
              borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 32px rgba(124,109,250,0.4)',
            }}>
              <span style={{ fontFamily: 'var(--font-display)', fontWeight: 800, color: '#fff', fontSize: 18 }}>R</span>
            </div>
            <span style={{
              fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 26, letterSpacing: -0.5,
              background: 'linear-gradient(135deg, #7c6dfa, #00e8c8)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            }}>RAD-ML</span>
          </div>
          <p style={{ color: 'var(--text2)', fontSize: 13 }}>Rapid Adaptive Data · Machine Learning</p>
        </div>

        {/* Form card */}
        <div style={{
          background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 20,
          padding: '32px 32px 28px', backdropFilter: 'blur(12px)',
          boxShadow: '0 24px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(124,109,250,0.08)',
        }}>
          {/* Tab switcher */}
          <div style={{ display: 'flex', gap: 2, background: 'var(--bg)', borderRadius: 10, padding: 3, marginBottom: 28 }}>
            {['login', 'register'].map(m => (
              <button key={m} onClick={() => { setMode(m); setError('') }} style={{
                flex: 1, padding: '9px 0', borderRadius: 8, border: 'none', cursor: 'pointer',
                fontSize: 13, fontWeight: 500, transition: 'all 0.2s',
                background: mode === m ? 'linear-gradient(135deg, rgba(124,109,250,0.25), rgba(0,232,200,0.12))' : 'transparent',
                color: mode === m ? 'var(--text)' : 'var(--text3)',
                borderBottom: mode === m ? '1px solid var(--violet)' : 'none',
              }}>{m === 'login' ? 'Sign in' : 'Create account'}</button>
            ))}
          </div>

          <form onSubmit={handleSubmit}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <Field label="Username" id="username" type="text" value={form.username} onChange={v => set('username', v)} placeholder="your_username" autoFocus />
              {!isLogin && <Field label="Email (optional)" id="email" type="email" value={form.email} onChange={v => set('email', v)} placeholder="you@example.com" />}
              <Field label="Password" id="password" type="password" value={form.password} onChange={v => set('password', v)} placeholder={isLogin ? '••••••••' : 'at least 6 characters'} />
            </div>

            {error && (
              <div style={{
                marginTop: 16, padding: '10px 14px',
                background: 'rgba(255,80,112,0.08)', border: '1px solid rgba(255,80,112,0.25)',
                borderRadius: 8, color: 'var(--error)', fontSize: 13, animation: 'fadeIn 0.2s ease',
              }}>{error}</div>
            )}

            <button type="submit" disabled={loading} style={{
              width: '100%', marginTop: 22, padding: '13px 0',
              background: loading ? 'var(--border2)' : 'linear-gradient(135deg, #7c6dfa 0%, #5a4fd4 50%, #00e8c8 100%)',
              backgroundSize: '200% auto', border: 'none', borderRadius: 10,
              cursor: loading ? 'not-allowed' : 'pointer', color: '#fff', fontWeight: 600, fontSize: 14,
              fontFamily: 'var(--font-display)', letterSpacing: 0.3, transition: 'all 0.3s',
              boxShadow: loading ? 'none' : '0 4px 20px rgba(124,109,250,0.35)',
            }}
              onMouseEnter={e => !loading && (e.currentTarget.style.backgroundPosition = 'right center')}
              onMouseLeave={e => e.currentTarget.style.backgroundPosition = 'left center'}
            >
              {loading
                ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><Spinner /> {isLogin ? 'Signing in…' : 'Creating account…'}</span>
                : isLogin ? 'Sign in →' : 'Create account →'}
            </button>


          </form>
        </div>

        <p style={{ textAlign: 'center', marginTop: 16, color: 'var(--text3)', fontSize: 12 }}>
          By continuing, you agree to RAD-ML's terms of service.
        </p>
      </div>
    </div>
  )
}

/* ── Field ────────────────────────────────────────────────────────────────── */
function Field({ label, id, type, value, onChange, placeholder, autoFocus }) {
  const [focused, setFocused] = useState(false)
  return (
    <div>
      <label htmlFor={id} style={{ display: 'block', fontSize: 12, fontWeight: 500, color: focused ? 'var(--violet)' : 'var(--text2)', marginBottom: 6, transition: 'color 0.15s' }}>{label}</label>
      <input id={id} type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} autoFocus={autoFocus}
        onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
        style={{
          width: '100%', padding: '11px 14px', background: 'var(--bg)', color: 'var(--text)',
          border: `1px solid ${focused ? 'var(--violet)' : 'var(--border)'}`, borderRadius: 8,
          fontSize: 14, outline: 'none', transition: 'border-color 0.15s',
          boxShadow: focused ? '0 0 0 3px rgba(124,109,250,0.12)' : 'none',
        }} />
    </div>
  )
}



function Spinner() {
  return <span style={{
    display: 'inline-block', width: 14, height: 14,
    border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff',
    borderRadius: '50%', animation: 'spin 0.8s linear infinite',
  }} />
}
