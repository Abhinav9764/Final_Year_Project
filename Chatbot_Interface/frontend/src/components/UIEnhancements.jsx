// ErrorBoundary.jsx — Enhanced Error Handling Component
// Catches errors and displays user-friendly messages with retry options

import React from 'react'

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  resetError = () => {
    this.setState({ hasError: false, error: null })
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          minHeight: '400px', padding: 40, textAlign: 'center',
          background: 'var(--surface)', borderRadius: 16,
        }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
          <h2 style={{ color: 'var(--text)', marginBottom: 8 }}>Something went wrong</h2>
          <p style={{ color: 'var(--text2)', marginBottom: 20, maxWidth: 400 }}>
            We encountered an unexpected error. Try refreshing the page or clearing your draft.
          </p>
          <p style={{ color: 'var(--text3)', fontSize: 12, fontFamily: 'var(--font-mono)', marginBottom: 20 }}>
            {this.state.error?.message}
          </p>
          <button
            onClick={this.resetError}
            style={{
              background: 'linear-gradient(135deg, var(--violet), #5a4fd4)',
              border: 'none', borderRadius: 10, padding: '10px 24px',
              color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer',
              transition: 'all 0.2s',
              boxShadow: '0 2px 12px rgba(124,109,250,0.4)',
            }}
            onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-2px)'}
            onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
          >
            Try Again
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

// ─────────────────────────────────────────────────────────────────
// LoadingSkeletonCard — Shimmer skeleton for loading states
// ─────────────────────────────────────────────────────────────────

export function LoadingSkeletonCard() {
  const shimmer = 'linear-gradient(90deg, var(--border) 25%, var(--surface) 50%, var(--border) 75%)'
  const shimmerBg = 'background-image: ' + shimmer + '; background-size: 200% 100%; animation: shimmer 2s infinite;'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{
        height: 20, borderRadius: 4,
        background: 'var(--border)', animation: 'shimmer 2s infinite',
        backgroundImage: shimmer, backgroundSize: '200% 100%',
      }} />
      <div style={{
        height: 16, borderRadius: 4, width: '80%',
        background: 'var(--border)', animation: 'shimmer 2s infinite',
        backgroundImage: shimmer, backgroundSize: '200% 100%',
      }} />
      <div style={{
        height: 16, borderRadius: 4, width: '60%',
        background: 'var(--border)', animation: 'shimmer 2s infinite',
        backgroundImage: shimmer, backgroundSize: '200% 100%',
      }} />
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// ErrorMessageCard — Display errors with retry option
// ─────────────────────────────────────────────────────────────────

export function ErrorMessageCard({ error, onRetry, title = 'Error occurred' }) {
  return (
    <div style={{
      padding: 20, borderRadius: 12,
      background: 'rgba(255,80,112,0.08)', border: '1px solid rgba(255,80,112,0.2)',
      display: 'flex', alignItems: 'flex-start', gap: 14,
    }}>
      <div style={{ fontSize: 20, flexShrink: 0 }}>🚨</div>
      <div style={{ flex: 1 }}>
        <h3 style={{ color: 'var(--error)', margin: '0 0 6px', fontSize: 14, fontWeight: 600 }}>
          {title}
        </h3>
        <p style={{ color: 'var(--text2)', fontSize: 13, margin: '0 0 12px', lineHeight: 1.5 }}>
          {error?.message || 'Something unexpected happened. Please try again.'}
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            style={{
              background: 'rgba(255,80,112,0.2)', border: '1px solid rgba(255,80,112,0.4)',
              borderRadius: 6, padding: '6px 14px', fontSize: 12, fontWeight: 600,
              color: 'var(--error)', cursor: 'pointer', transition: 'all 0.2s',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'rgba(255,80,112,0.3)'
              e.currentTarget.style.borderColor = 'rgba(255,80,112,0.6)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'rgba(255,80,112,0.2)'
              e.currentTarget.style.borderColor = 'rgba(255,80,112,0.4)'
            }}
          >
            ↻ Try Again
          </button>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Toast Notification — Bottom-right notification system
// ─────────────────────────────────────────────────────────────────

let toastId = 0

export const useToast = () => {
  const [toasts, setToasts] = React.useState([])

  const addToast = (message, type = 'info', duration = 3000) => {
    const id = toastId++
    setToasts(prev => [...prev, { id, message, type }])
    
    if (duration > 0) {
      setTimeout(() => {
        removeToast(id)
      }, duration)
    }
    
    return id
  }

  const removeToast = (id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }

  return { toasts, addToast, removeToast }
}

export function ToastContainer({ toasts, onRemove }) {
  return (
    <div style={{
      position: 'fixed', bottom: 20, right: 20, zIndex: 1000,
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      {toasts.map(toast => (
        <Toast key={toast.id} toast={toast} onClose={() => onRemove(toast.id)} />
      ))}
    </div>
  )
}

function Toast({ toast, onClose }) {
  const bgColor = {
    success: 'rgba(0,232,200,0.1)',
    error: 'rgba(255,80,112,0.1)',
    warning: 'rgba(255,200,0,0.1)',
    info: 'rgba(124,109,250,0.1)',
  }[toast.type] || 'var(--surface)'

  const borderColor = {
    success: 'rgba(0,232,200,0.3)',
    error: 'rgba(255,80,112,0.3)',
    warning: 'rgba(255,200,0,0.3)',
    info: 'rgba(124,109,250,0.3)',
  }[toast.type] || 'var(--border)'

  const textColor = {
    success: 'var(--cyan)',
    error: 'var(--error)',
    warning: '#ffc800',
    info: 'var(--violet)',
  }[toast.type] || 'var(--text)'

  const icon = {
    success: '✓',
    error: '✕',
    warning: '⚠',
    info: 'ℹ',
  }[toast.type] || '•'

  return (
    <div style={{
      background: bgColor, border: `1px solid ${borderColor}`,
      borderRadius: 10, padding: '12px 16px',
      display: 'flex', alignItems: 'center', gap: 10,
      animation: 'slideInRight 0.3s ease both',
      maxWidth: 300,
    }}>
      <span style={{ fontSize: 14, color: textColor, flexShrink: 0 }}>{icon}</span>
      <span style={{ fontSize: 13, color: 'var(--text)', flex: 1 }}>{toast.message}</span>
      <button
        onClick={onClose}
        style={{
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--text3)', fontSize: 14, padding: 0,
          transition: 'color 0.2s',
        }}
        onMouseEnter={e => e.currentTarget.style.color = 'var(--text)'}
        onMouseLeave={e => e.currentTarget.style.color = 'var(--text3)'}
      >
        ×
      </button>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Tooltip — Hover tooltip component
// ─────────────────────────────────────────────────────────────────

export function Tooltip({ children, title, placement = 'top' }) {
  const [show, setShow] = React.useState(false)

  const placementStyles = {
    top: { bottom: '100%', left: '50%', transform: 'translateX(-50%)', marginBottom: 8 },
    bottom: { top: '100%', left: '50%', transform: 'translateX(-50%)', marginTop: 8 },
    left: { right: '100%', top: '50%', transform: 'translateY(-50%)', marginRight: 8 },
    right: { left: '100%', top: '50%', transform: 'translateY(-50%)', marginLeft: 8 },
  }

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <div
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
      >
        {children}
      </div>
      {show && (
        <div style={{
          position: 'absolute',
          ...placementStyles[placement],
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 6, padding: '6px 10px', fontSize: 12,
          color: 'var(--text2)', whiteSpace: 'nowrap', zIndex: 999,
          boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
          animation: 'fadeIn 0.2s ease both',
        }}>
          {title}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// ProgressRing — Circular progress indicator
// ─────────────────────────────────────────────────────────────────

export function ProgressRing({ progress = 0 }) {
  const circumference = 2 * Math.PI * 45
  const offset = circumference - (progress / 100) * circumference

  return (
    <svg width="100" height="100" style={{ transform: 'rotate(-90deg)' }}>
      <circle cx="50" cy="50" r="45" fill="none" stroke="var(--border)" strokeWidth="2" />
      <circle
        cx="50" cy="50" r="45" fill="none" stroke="var(--violet)" strokeWidth="2"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        style={{ transition: 'stroke-dashoffset 0.3s ease' }}
      />
      <text x="50" y="50" textAnchor="middle" dy="0.3em" fontSize="18" fontWeight="600" fill="var(--text)">
        {Math.round(progress)}%
      </text>
    </svg>
  )
}
