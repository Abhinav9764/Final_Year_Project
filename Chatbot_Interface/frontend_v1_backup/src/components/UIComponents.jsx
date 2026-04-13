import React, { useState, useEffect } from 'react'

/**
 * Enhanced Loading Component with multiple variants
 */
export function LoadingSpinner({ size = 24, color = 'var(--violet)' }) {
  return (
    <div
      style={{
        display: 'inline-block',
        width: size,
        height: size,
        border: `2px solid rgba(124,109,250,0.2)`,
        borderTopColor: color,
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
      }}
    />
  )
}

/**
 * Loading dots animation
 */
export function LoadingDots({ color = 'var(--violet)' }) {
  return (
    <div style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
      {[0, 1, 2].map(i => (
        <div
          key={i}
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: color,
            animation: `blink 1.2s ease-in-out ${i * 0.2}s infinite`,
          }}
        />
      ))}
    </div>
  )
}

/**
 * Skeleton loader for content placeholders
 */
export function SkeletonLoader({ width = '100%', height = 16, style = {}, count = 1 }) {
  return (
    <div style={{ ...style }}>
      {Array(count).fill().map((_, i) => (
        <div
          key={i}
          className="skeleton"
          style={{
            width: width instanceof Array ? width[i] : width,
            height,
            marginBottom: i < count - 1 ? 12 : 0,
            borderRadius: 8,
          }}
        />
      ))}
    </div>
  )
}

/**
 * Enhanced Loading state with message and progress
 */
export function LoadingState({ message, subMessage, progress, variant = 'default' }) {
  const [dots, setDots] = useState('')
  
  useEffect(() => {
    let interval
    if (variant === 'dots') {
      interval = setInterval(() => {
        setDots(d => (d.length >= 3 ? '' : d + '.'))
      }, 500)
    }
    return () => clearInterval(interval)
  }, [variant])

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 16,
      padding: '32px',
    }}>
      {variant === 'default' && <LoadingSpinner size={32} />}
      {variant === 'dots' && <LoadingDots />}
      {variant === 'circle' && (
        <div style={{
          width: 40,
          height: 40,
          borderRadius: '50%',
          background: 'linear-gradient(135deg, var(--violet), var(--cyan))',
          animation: 'spin 2s linear infinite',
          opacity: 0.7,
        }} />
      )}

      {message && (
        <div style={{
          fontSize: 14,
          fontWeight: 600,
          color: 'var(--text)',
          textAlign: 'center',
        }}>
          {message}{variant === 'dots' ? dots : ''}
        </div>
      )}

      {subMessage && (
        <div style={{
          fontSize: 12,
          color: 'var(--text3)',
          textAlign: 'center',
          maxWidth: 300,
        }}>
          {subMessage}
        </div>
      )}

      {progress !== undefined && (
        <div style={{
          width: 200,
          height: 4,
          background: 'var(--border)',
          borderRadius: 2,
          overflow: 'hidden',
        }}>
          <div
            style={{
              height: '100%',
              background: 'linear-gradient(90deg, var(--violet), var(--cyan))',
              width: `${Math.min(progress, 100)}%`,
              transition: 'width 0.3s ease',
            }}
          />
        </div>
      )}
    </div>
  )
}

/**
 * Enhanced Button Component
 */
export function Button({
  children,
  onClick,
  disabled = false,
  loading = false,
  variant = 'primary',
  size = 'md',
  icon,
  style = {},
  ...props
}) {
  const variants = {
    primary: {
      background: 'linear-gradient(135deg, var(--violet), #5a4fd4)',
      color: '#fff',
      boxShadow: '0 4px 16px rgba(124,109,250,0.35)',
    },
    secondary: {
      background: 'transparent',
      color: 'var(--text)',
      border: '1px solid var(--border)',
    },
    success: {
      background: 'rgba(0,232,200,0.15)',
      color: 'var(--success)',
      border: '1px solid rgba(0,232,200,0.3)',
    },
    error: {
      background: 'rgba(255,80,112,0.15)',
      color: 'var(--error)',
      border: '1px solid rgba(255,80,112,0.3)',
    },
  }

  const sizes = {
    sm: { padding: '8px 12px', fontSize: 12 },
    md: { padding: '10px 16px', fontSize: 14 },
    lg: { padding: '12px 20px', fontSize: 15 },
  }

  const baseStyle = {
    border: 'none',
    borderRadius: 10,
    cursor: disabled ? 'not-allowed' : 'pointer',
    fontWeight: 600,
    transition: 'all 0.2s ease',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    opacity: disabled ? 0.5 : 1,
    ...variants[variant],
    ...sizes[size],
    ...style,
  }

  return (
    <button
      style={baseStyle}
      disabled={disabled || loading}
      onClick={onClick}
      onMouseEnter={e => {
        if (!disabled && !loading) {
          e.currentTarget.style.transform = 'translateY(-1px)'
          if (variant === 'primary') {
            e.currentTarget.style.boxShadow = '0 6px 20px rgba(124,109,250,0.45)'
          }
        }
      }}
      onMouseLeave={e => {
        e.currentTarget.style.transform = 'none'
        if (variant === 'primary') {
          e.currentTarget.style.boxShadow = '0 4px 16px rgba(124,109,250,0.35)'
        }
      }}
      {...props}
    >
      {icon && <span style={{ fontSize: 16 }}>{icon}</span>}
      {loading ? <LoadingSpinner size={14} color="currentColor" /> : null}
      <span>{children}</span>
    </button>
  )
}

/**
 * Enhanced Input Component with validation feedback
 */
export function Input({
  label,
  error,
  success,
  hint,
  icon,
  type = 'text',
  required = false,
  style = {},
  ...props
}) {
  const [focused, setFocused] = useState(false)

  return (
    <div style={{ marginBottom: 14 }}>
      {label && (
        <label style={{
          display: 'block',
          fontSize: 13,
          fontWeight: 600,
          color: 'var(--text)',
          marginBottom: 6,
        }}>
          {label}
          {required && <span style={{ color: 'var(--error)' }}>*</span>}
        </label>
      )}

      <div style={{ position: 'relative' }}>
        {icon && (
          <span style={{
            position: 'absolute',
            left: 12,
            top: '50%',
            transform: 'translateY(-50%)',
            fontSize: 16,
            color: 'var(--text3)',
            pointerEvents: 'none',
          }}>
            {icon}
          </span>
        )}

        <input
          type={type}
          style={{
            width: '100%',
            paddingLeft: icon ? 36 : 14,
            paddingRight: 14,
            borderColor: error ? 'var(--error)' : success ? 'var(--success)' : focused ? 'var(--violet)' : 'var(--border)',
            backgroundColor: error ? 'rgba(255,80,112,0.04)' : success ? 'rgba(0,232,200,0.04)' : 'var(--surface2)',
            ...style,
          }}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          {...props}
        />

        {(success || error) && (
          <span style={{
            position: 'absolute',
            right: 12,
            top: '50%',
            transform: 'translateY(-50%)',
            fontSize: 16,
            color: error ? 'var(--error)' : 'var(--success)',
          }}>
            {error ? '✕' : '✓'}
          </span>
        )}
      </div>

      {error && (
        <div style={{
          fontSize: 12,
          color: 'var(--error)',
          marginTop: 6,
          animation: 'slideDown 0.2s ease',
        }}>
          {error}
        </div>
      )}

      {success && (
        <div style={{
          fontSize: 12,
          color: 'var(--success)',
          marginTop: 6,
          animation: 'slideDown 0.2s ease',
        }}>
          {success}
        </div>
      )}

      {hint && !error && !success && (
        <div style={{
          fontSize: 12,
          color: 'var(--text3)',
          marginTop: 6,
        }}>
          {hint}
        </div>
      )}
    </div>
  )
}
