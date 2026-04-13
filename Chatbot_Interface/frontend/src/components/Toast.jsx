import React, { useState, useCallback, useRef, useEffect } from 'react'

const toastContextValue = {
  show: () => {},
}

/**
 * Toast Context — store the show function so any component can trigger toasts
 */
export const ToastContext = React.createContext(toastContextValue)

/**
 * Hook to use toast notifications
 */
export function useToast() {
  const ctx = React.useContext(ToastContext)
  if (!ctx) {
    console.warn('useToast called outside ToastProvider')
    return {
      success: () => {},
      error: () => {},
      warning: () => {},
      info: () => {},
      show: () => {},
    }
  }
  return {
    success: (msg, duration) => ctx.show(msg, 'success', duration),
    error: (msg, duration) => ctx.show(msg, 'error', duration),
    warning: (msg, duration) => ctx.show(msg, 'warning', duration),
    info: (msg, duration) => ctx.show(msg, 'info', duration),
    show: ctx.show,
  }
}

const ICON_MAP = {
  success: '✓',
  error: '✕',
  warning: '⚠',
  info: 'ⓘ',
}

/**
 * Toast Provider — manages toast notifications with enhanced UX
 */
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const toastIdRef = useRef(0)

  const show = useCallback((message, type = 'info', duration = 3000) => {
    const id = toastIdRef.current++
    const toast = { id, message, type }

    setToasts(prev => [...prev, toast])

    if (duration > 0) {
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id))
      }, duration)
    }

    return id
  }, [])

  const remove = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 1001, pointerEvents: 'none' }}>
        {toasts.map(toast => (
          <Toast
            key={toast.id}
            message={toast.message}
            type={toast.type}
            onDismiss={() => remove(toast.id)}
          />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

/**
 * Individual Toast Component
 */
function Toast({ message, type, onDismiss }) {
  const [isExiting, setIsExiting] = useState(false)
  const dismissTimeoutRef = useRef(null)

  useEffect(() => {
    dismissTimeoutRef.current = setTimeout(() => {
      setIsExiting(true)
      setTimeout(onDismiss, 150)
    }, 2850)

    return () => clearTimeout(dismissTimeoutRef.current)
  }, [onDismiss])

  const handleDismiss = () => {
    setIsExiting(true)
    setTimeout(onDismiss, 150)
    clearTimeout(dismissTimeoutRef.current)
  }

  return (
    <div
      className={`toast ${type}`}
      style={{
        animation: isExiting ? 'slideDown 0.15s ease forwards' : 'slideUp 0.3s ease',
        pointerEvents: 'auto',
        marginBottom: 8,
      }}
    >
      <span style={{ fontSize: 16, flexShrink: 0 }}>
        {ICON_MAP[type] || '✓'}
      </span>
      <span style={{ flex: 1, fontSize: 13 }}>
        {message}
      </span>
      <button
        onClick={handleDismiss}
        style={{
          background: 'none',
          border: 'none',
          color: 'inherit',
          cursor: 'pointer',
          padding: '4px 6px',
          opacity: 0.7,
          transition: 'opacity 0.2s',
          fontSize: 16,
          flexShrink: 0,
        }}
        onMouseEnter={e => e.currentTarget.style.opacity = '1'}
        onMouseLeave={e => e.currentTarget.style.opacity = '0.7'}
      >
        ✕
      </button>
    </div>
  )
}
