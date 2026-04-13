// CodeHighlight.jsx — Simple syntax highlighting for code preview
// Display generated code with proper formatting

import React from 'react'

const keywords = ['import', 'from', 'def', 'class', 'return', 'if', 'else', 'for', 'while', 'try', 'except', 'with', 'as', 'lambda', 'async', 'await']
const builtins = ['print', 'len', 'range', 'enumerate', 'zip', 'map', 'filter', 'sum', 'min', 'max', 'sorted', 'pd', 'np', 'sklearn']

export function CodeHighlight({ children, language = 'python' }) {
  if (!children) return null

  const code = String(children)
  const lines = code.split('\n')

  return (
    <pre style={{
      background: 'var(--bg)', border: '1px solid var(--border)',
      borderRadius: 10, padding: 16, overflowX: 'auto',
      fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text)',
      lineHeight: 1.6, margin: 0,
    }}>
      {lines.map((line, i) => (
        <div key={i} style={{ display: 'flex', lineHeight: 1.6 }}>
          <span style={{
            color: 'var(--text3)', minWidth: 30, textAlign: 'right',
            paddingRight: 12, userSelect: 'none', opacity: 0.6,
          }}>
            {i + 1}
          </span>
          <span style={{ flex: 1, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {highlightSyntax(line, language)}
          </span>
        </div>
      ))}
    </pre>
  )
}

function highlightSyntax(line, language) {
  if (!line) return line

  const parts = []
  let lastIndex = 0

  // Match strings first (to avoid matching inside strings)
  const stringRegex = /(['"`])(.*?)\1/g
  const matches = [...line.matchAll(stringRegex)]

  if (matches.length === 0) {
    // No strings, do keyword highlighting
    return highlightKeywords(line)
  }

  matches.forEach(match => {
    const before = line.substring(lastIndex, match.index)
    if (before) {
      parts.push(highlightKeywords(before))
    }

    parts.push(
      <span key={`str-${match.index}`} style={{ color: 'var(--cyan)' }}>
        {match[0]}
      </span>
    )

    lastIndex = match.index + match[0].length
  })

  const remainder = line.substring(lastIndex)
  if (remainder) {
    parts.push(highlightKeywords(remainder))
  }

  return parts
}

function highlightKeywords(text) {
  const keywordRegex = new RegExp(`\\b(${keywords.join('|')})\\b`, 'g')
  const builtinRegex = new RegExp(`\\b(${builtins.join('|')})\\b`, 'g')

  let lastIndex = 0
  const parts = []

  const keywordMatches = [...text.matchAll(keywordRegex)]
  const builtinMatches = [...text.matchAll(builtinRegex)]
  const allMatches = [...keywordMatches, ...builtinMatches].sort((a, b) => a.index - b.index)

  allMatches.forEach(match => {
    const before = text.substring(lastIndex, match.index)
    if (before) parts.push(before)

    const isKeyword = keywords.includes(match[0])
    parts.push(
      <span key={`kw-${match.index}`} style={{ color: isKeyword ? 'var(--violet)' : 'var(--cyan)' }}>
        {match[0]}
      </span>
    )

    lastIndex = match.index + match[0].length
  })

  const remainder = text.substring(lastIndex)
  if (remainder) parts.push(remainder)

  return parts.length > 0 ? parts : text
}

// ─────────────────────────────────────────────────────────────────
// CodePreviewTab — Display generated code files
// ─────────────────────────────────────────────────────────────────

export function CodePreviewTab({ files = {} }) {
  const [selectedFile, setSelectedFile] = React.useState(null)

  const fileEntries = Object.entries(files || {})
  
  if (fileEntries.length === 0) {
    return (
      <div style={{ padding: 20, textAlign: 'center' }}>
        <p style={{ color: 'var(--text3)', fontSize: 13 }}>No code files generated yet</p>
      </div>
    )
  }

  const active = selectedFile || fileEntries[0]?.[0]
  const activeContent = files[active]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* File tabs */}
      <div style={{
        display: 'flex', gap: 0, borderBottom: '1px solid var(--border)',
        overflowX: 'auto', padding: '0 8px',
      }}>
        {fileEntries.map(([name]) => (
          <button
            key={name}
            onClick={() => setSelectedFile(name)}
            style={{
              padding: '10px 14px', fontSize: 12, fontFamily: 'var(--font-mono)',
              border: 'none', background: 'none', cursor: 'pointer',
              color: active === name ? 'var(--violet)' : 'var(--text3)',
              borderBottom: active === name ? '2px solid var(--violet)' : 'none',
              transition: 'all 0.2s',
              whiteSpace: 'nowrap',
            }}
            onMouseEnter={e => {
              if (active !== name) e.currentTarget.style.color = 'var(--text2)'
            }}
            onMouseLeave={e => {
              if (active !== name) e.currentTarget.style.color = 'var(--text3)'
            }}
          >
            📄 {name}
          </button>
        ))}
      </div>

      {/* Code content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 16, background: 'var(--bg)' }}>
        {activeContent ? (
          <CodeHighlight language={getLanguage(active)}>
            {activeContent}
          </CodeHighlight>
        ) : (
          <div style={{ color: 'var(--text3)', textAlign: 'center', padding: 40 }}>
            No content
          </div>
        )}
      </div>

      {/* Copy button */}
      {activeContent && (
        <div style={{ padding: 12, borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end' }}>
          <button
            onClick={() => {
              navigator.clipboard.writeText(activeContent)
              alert('Copied to clipboard!')
            }}
            style={{
              background: 'linear-gradient(135deg, var(--violet), #5a4fd4)',
              border: 'none', borderRadius: 6, padding: '6px 12px',
              color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer',
              transition: 'all 0.2s',
            }}
            onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.05)'}
            onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
          >
            📋 Copy Code
          </button>
        </div>
      )}
    </div>
  )
}

function getLanguage(filename) {
  if (filename.endsWith('.py')) return 'python'
  if (filename.endsWith('.js') || filename.endsWith('.jsx')) return 'javascript'
  if (filename.endsWith('.json')) return 'json'
  if (filename.endsWith('.yaml') || filename.endsWith('.yml')) return 'yaml'
  return 'text'
}
