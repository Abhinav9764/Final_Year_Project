import React, { useState, useCallback } from 'react'

/**
 * Enhanced InputField Component
 * Features:
 * - Real-time validation
 * - Error/success states
 * - Character count
 * - Password strength indicator
 */
export function InputField({
  label,
  type = 'text',
  placeholder,
  value,
  onChange,
  onBlur,
  error,
  success,
  hint,
  required = false,
  maxLength,
  minLength,
  validation,
  showStrength = false,
  disabled = false,
  autoComplete,
}) {
  const [touched, setTouched] = useState(false)
  const [focused, setFocused] = useState(false)

  const handleBlur = useCallback((e) => {
    setTouched(true)
    setFocused(false)
    onBlur?.(e)
  }, [onBlur])

  const handleFocus = () => setFocused(true)

  // Validate in real-time
  let validationError = error
  let isValid = false

  if (touched && validation && !validationError) {
    const result = validation(value)
    if (result.error) {
      validationError = result.error
    } else if (result.success) {
      isValid = true
    }
  }

  // Password strength indicator
  const getPasswordStrength = () => {
    if (!value || type !== 'password') return null

    let strength = 0
    if (value.length >= 8) strength++
    if (value.length >= 12) strength++
    if (/[a-z]/.test(value) && /[A-Z]/.test(value)) strength++
    if (/\d/.test(value)) strength++
    if (/[^a-zA-Z\d]/.test(value)) strength++

    const levels = [
      { text: 'Weak', color: '#ff5070' },
      { text: 'Fair', color: '#ffb54a' },
      { text: 'Good', color: '#00e8c8' },
      { text: 'Strong', color: '#00e8c8' },
      { text: 'Very Strong', color: '#00e8c8' },
    ]

    return levels[strength] || levels[0]
  }

  const strength = getPasswordStrength()

  const inputClass = [
    validationError && touched ? 'input-error' : '',
    isValid && touched ? 'input-success' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className="form-group" style={{ marginBottom: 16 }}>
      {label && (
        <label className={`form-label ${required ? 'required' : ''}`}>
          {label}
        </label>
      )}

      <div style={{ position: 'relative' }}>
        <input
          type={type}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={handleBlur}
          onFocus={handleFocus}
          disabled={disabled}
          maxLength={maxLength}
          autoComplete={autoComplete}
          className={inputClass}
          style={{
            width: '100%',
            padding: '11px 14px',
            paddingRight: '36px',
            fontSize: 14,
            fontFamily: 'inherit',
          }}
        />

        {/* Clear button */}
        {value && focused && (
          <button
            type="button"
            onClick={() => onChange('')}
            style={{
              position: 'absolute',
              right: 12,
              top: '50%',
              transform: 'translateY(-50%)',
              background: 'transparent',
              border: 'none',
              color: 'var(--text2)',
              cursor: 'pointer',
              fontSize: 16,
              padding: 0,
              opacity: 0.6,
              transition: 'opacity 0.2s ease',
            }}
            onMouseEnter={(e) => (e.target.style.opacity = '1')}
            onMouseLeave={(e) => (e.target.style.opacity = '0.6')}
          >
            ×
          </button>
        )}

        {/* Success checkmark */}
        {isValid && touched && !focused && (
          <div
            style={{
              position: 'absolute',
              right: 12,
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--success)',
              fontSize: 16,
            }}
          >
            ✓
          </div>
        )}
      </div>

      {/* Password strength indicator */}
      {showStrength && type === 'password' && value && (
        <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
          <div
            style={{
              flex: 1,
              height: 3,
              background: 'var(--border)',
              borderRadius: 2,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${(value.length / (maxLength || 20)) * 100}%`,
                background: strength?.color || '#ffb54a',
                transition: 'width 0.2s ease',
              }}
            />
          </div>
          <span style={{ fontSize: 11, color: strength?.color, fontWeight: 600 }}>
            {strength?.text}
          </span>
        </div>
      )}

      {/* Character count */}
      {maxLength && (
        <div
          style={{
            fontSize: 11,
            color: 'var(--text3)',
            marginTop: 4,
            textAlign: 'right',
          }}
        >
          {value.length}/{maxLength}
        </div>
      )}

      {/* Error message */}
      {validationError && touched && (
        <div
          className="form-error"
          style={{
            animation: 'slideInLeft 0.2s ease',
          }}
        >
          {validationError}
        </div>
      )}

      {/* Success message */}
      {isValid && touched && hint && (
        <div
          className="form-hint"
          style={{
            color: 'var(--success)',
            animation: 'slideInLeft 0.2s ease',
          }}
        >
          {hint}
        </div>
      )}

      {/* Hint text */}
      {hint && !isValid && !validationError && (
        <div className="form-hint">{hint}</div>
      )}
    </div>
  )
}

export default InputField
