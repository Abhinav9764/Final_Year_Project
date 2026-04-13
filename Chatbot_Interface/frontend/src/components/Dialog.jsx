import React, { useEffect, useState } from 'react'

/**
 * Modal Component with smooth transitions and accessibility
 */
export function Modal({ isOpen, onClose, title, children, size = 'md', footer }) {
  const [isExiting, setIsExiting] = useState(false)

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  const handleClose = () => {
    setIsExiting(true)
    setTimeout(() => {
      setIsExiting(false)
      onClose?.()
    }, 150)
  }

  if (!isOpen && !isExiting) return null

  const sizes = {
    sm: '400px',
    md: '600px',
    lg: '800px',
    xl: '1000px',
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: isExiting ? 'rgba(0,0,0,0)' : 'rgba(0,0,0,0.4)',
        backdropFilter: isExiting ? 'blur(0px)' : 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 999,
        transition: 'all 0.15s ease',
        padding: 16,
      }}
      onClick={handleClose}
    >
      <div
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 16,
          maxWidth: sizes[size],
          width: '100%',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
          animation: isExiting ? 'scaleIn 0.15s ease reverse' : 'scaleIn 0.2s ease',
          transform: isExiting ? 'scale(0.95)' : 'scale(1)',
          opacity: isExiting ? 0 : 1,
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        {title && (
          <div
            style={{
              padding: '20px 24px',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 16,
            }}
          >
            <h2 style={{
              fontSize: 18,
              fontWeight: 700,
              color: 'var(--text)',
              margin: 0,
              fontFamily: 'var(--font-display)',
            }}>
              {title}
            </h2>
            <button
              onClick={handleClose}
              style={{
                background: 'none',
                border: 'none',
                fontSize: 20,
                color: 'var(--text3)',
                cursor: 'pointer',
                padding: '4px 8px',
                transition: 'color 0.2s',
              }}
              onMouseEnter={e => e.currentTarget.style.color = 'var(--text)'}
              onMouseLeave={e => e.currentTarget.style.color = 'var(--text3)'}
            >
              ✕
            </button>
          </div>
        )}

        {/* Content */}
        <div style={{
          flex: 1,
          overflow: 'auto',
          padding: '24px',
        }}>
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div
            style={{
              padding: '20px 24px',
              borderTop: '1px solid var(--border)',
              display: 'flex',
              gap: 10,
              justifyContent: 'flex-end',
            }}
          >
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * Alert/Confirmation Dialog
 */
export function AlertDialog({
  isOpen,
  onClose,
  title,
  message,
  action,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  isDangerous = false,
}) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      size="sm"
      footer={
        <>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '9px 18px',
              color: 'var(--text)',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 600,
              transition: 'all 0.2s',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = 'var(--text2)'
              e.currentTarget.style.background = 'var(--surface2)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = 'var(--border)'
              e.currentTarget.style.background = 'transparent'
            }}
          >
            {cancelText}
          </button>
          <button
            onClick={() => {
              action?.()
              onClose()
            }}
            style={{
              background: isDangerous
                ? 'linear-gradient(135deg, #ff5070, #ff3d5b)'
                : 'linear-gradient(135deg, var(--violet), #5a4fd4)',
              border: 'none',
              borderRadius: 8,
              padding: '9px 18px',
              color: '#fff',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 600,
              transition: 'all 0.2s',
              boxShadow: isDangerous
                ? '0 2px 12px rgba(255,80,112,0.3)'
                : '0 2px 12px rgba(124,109,250,0.3)',
            }}
            onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-1px)'}
            onMouseLeave={e => e.currentTarget.style.transform = 'none'}
          >
            {confirmText}
          </button>
        </>
      }
    >
      <p style={{
        fontSize: 14,
        color: 'var(--text)',
        lineHeight: 1.6,
        margin: 0,
      }}>
        {message}
      </p>
    </Modal>
  )
}

/**
 * Drawer/Sidebar component
 */
export function Drawer({ isOpen, onClose, title, children, position = 'right' }) {
  const [isExiting, setIsExiting] = useState(false)

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  const handleClose = () => {
    setIsExiting(true)
    setTimeout(() => {
      setIsExiting(false)
      onClose?.()
    }, 200)
  }

  if (!isOpen && !isExiting) return null

  const slideDir = position === 'right'
    ? isExiting ? 'translateX(400px)' : 'translateX(0)'
    : isExiting ? 'translateX(-400px)' : 'translateX(0)'

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 998,
      }}
    >
      {/* Backdrop */}
      <div
        onClick={handleClose}
        style={{
          position: 'absolute',
          inset: 0,
          background: isExiting ? 'rgba(0,0,0,0)' : 'rgba(0,0,0,0.3)',
          backdropFilter: isExiting ? 'blur(0px)' : 'blur(3px)',
          transition: 'all 0.2s ease',
        }}
      />

      {/* Drawer */}
      <div
        style={{
          position: 'absolute',
          [position]: 0,
          top: 0,
          bottom: 0,
          width: 400,
          background: 'var(--surface)',
          borderLeft: position === 'right' ? '1px solid var(--border)' : 'none',
          borderRight: position === 'left' ? '1px solid var(--border)' : 'none',
          boxShadow: position === 'right'
            ? '-8px 0 32px rgba(0,0,0,0.3)'
            : '8px 0 32px rgba(0,0,0,0.3)',
          transform: slideDir,
          transition: 'transform 0.2s ease',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 999,
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '20px 24px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <h2 style={{
            fontSize: 16,
            fontWeight: 700,
            color: 'var(--text)',
            margin: 0,
            fontFamily: 'var(--font-display)',
          }}>
            {title}
          </h2>
          <button
            onClick={handleClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: 20,
              color: 'var(--text3)',
              cursor: 'pointer',
              padding: '4px 8px',
              transition: 'color 0.2s',
            }}
            onMouseEnter={e => e.currentTarget.style.color = 'var(--text)'}
            onMouseLeave={e => e.currentTarget.style.color = 'var(--text3)'}
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div style={{
          flex: 1,
          overflow: 'auto',
          padding: '24px',
        }}>
          {children}
        </div>
      </div>
    </div>
  )
}

/**
 * Tooltip component (wrap content with this)
 */
export function Tooltip({ text, children, position = 'top' }) {
  const positions = {
    top: { bottom: '100%', left: '50%', transform: 'translateX(-50%) translateY(-8px)', marginBottom: 8 },
    bottom: { top: '100%', left: '50%', transform: 'translateX(-50%) translateY(8px)', marginTop: 8 },
    left: { right: '100%', top: '50%', transform: 'translateY(-50%) translateX(-8px)', marginRight: 8 },
    right: { left: '100%', top: '50%', transform: 'translateY(-50%) translateX(8px)', marginLeft: 8 },
  }

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      {children}
      <div
        className="tooltip"
        data-tooltip={text}
        style={{
          position: 'absolute',
          ...positions[position],
          background: 'var(--surface)',
          color: 'var(--text)',
          padding: '6px 12px',
          borderRadius: 6,
          fontSize: 12,
          border: '1px solid var(--border)',
          whiteSpace: 'nowrap',
          zIndex: 1000,
          opacity: 0,
          pointerEvents: 'none',
          transition: 'opacity 0.2s ease',
        }}
      />
    </div>
  )
}
