import React, { useState, useEffect } from 'react'
import { apiUrl } from '../lib/api.js'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'


const TABS = [
  { id: 'narrative',  label: '📖 Explanation',  desc: 'Plain-English summary' },
  { id: 'algorithm',  label: '🧠 Algorithm',    desc: 'Why XGBoost?' },
  { id: 'data',       label: '🗃 Data Story',    desc: 'How data was collected' },
  { id: 'usage',      label: '🚀 How to Use',   desc: 'Step-by-step guide' },
  { id: 'code',       label: '💻 Generated Code', desc: 'View generated files' },
  { id: 'diagram',    label: '🏗 Architecture',  desc: 'Pipeline diagram' },
]

export default function ExplainPanel({ jobId, result, getToken }) {
  const [tab, setTab]         = useState('narrative')
  const [expl, setExpl]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  // Use explanation embedded in result first; fall back to API
  useEffect(() => {
    if (result?.explanation && Object.keys(result.explanation).length > 0) {
      setExpl(result.explanation)
      return
    }
    if (!jobId) return
    setLoading(true)
    fetch(apiUrl(`/explain/${jobId}`), {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
      .then(r => r.json())
      .then(data => {
        if (data.error) setError(data.error)
        else setExpl(data)
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [jobId, result])

  if (loading) return <LoadingCard />
  if (error)   return <ErrorCard msg={error} />
  if (!expl)   return null

  return (
    <div style={{
      marginTop: 20,
      border: '1px solid rgba(124,109,250,0.2)',
      borderRadius: 18,
      overflow: 'hidden',
      background: 'var(--surface)',
      boxShadow: '0 8px 40px rgba(0,0,0,0.4)',
      animation: 'fadeSlideUp 0.4s ease both 0.2s both',
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 22px',
        borderBottom: '1px solid var(--border)',
        background: 'linear-gradient(135deg, rgba(124,109,250,0.08), rgba(0,232,200,0.04))',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <span style={{ fontSize: 22 }}>🔍</span>
        <div>
          <div style={{
            fontFamily: 'var(--font-display)', fontWeight: 700,
            fontSize: 15, color: 'var(--text)',
          }}>Pipeline Explainability Report</div>
          <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 1 }}>
            Full breakdown of what the agent did, why, and how to use your model
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <div style={{
        display: 'flex', overflowX: 'auto',
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg)',
        scrollbarWidth: 'none',
      }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: '10px 16px', border: 'none', background: 'none',
            cursor: 'pointer', whiteSpace: 'nowrap',
            color: tab === t.id ? 'var(--violet)' : 'var(--text3)',
            borderBottom: `2px solid ${tab === t.id ? 'var(--violet)' : 'transparent'}`,
            fontSize: 12.5, fontWeight: tab === t.id ? 600 : 400,
            fontFamily: 'var(--font-body)',
            transition: 'all 0.15s',
            display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'flex-start',
          }}>
            <span>{t.label}</span>
            <span style={{ fontSize: 9, color: 'var(--text3)', fontWeight: 400 }}>{t.desc}</span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ padding: '22px', maxHeight: 520, overflowY: 'auto' }}>
        {tab === 'narrative' && <NarrativeTab text={expl.narrative} />}
        {tab === 'algorithm' && <AlgorithmTab card={expl.algorithm_card} />}
        {tab === 'data'      && <DataStoryTab story={expl.data_story} />}
        {tab === 'usage'     && <UsageTab guide={expl.usage_guide} deployUrl={result?.deploy_url} />}
        {tab === 'code'      && <CodeTab preview={expl.code_preview} />}
        {tab === 'diagram'   && <DiagramTab b64={expl.architecture_diagram_b64} />}
      </div>
    </div>
  )
}

/* ── Narrative Tab ────────────────────────────────────────────────────────── */
function NarrativeTab({ text }) {
  if (!text) return <Empty msg="Narrative not available." />
  // Simple markdown-like renderer
  const lines = text.split('\n')
  return (
    <div style={{ lineHeight: 1.75, fontSize: 14, color: 'var(--text)' }}>
      {lines.map((line, i) => {
        if (line.startsWith('## ')) return (
          <h3 key={i} style={{
            fontFamily: 'var(--font-display)', fontWeight: 700,
            fontSize: 16, color: 'var(--text)',
            marginTop: 20, marginBottom: 8, paddingBottom: 6,
            borderBottom: '1px solid var(--border)',
          }}>{line.slice(3)}</h3>
        )
        if (line.startsWith('### ')) return (
          <h4 key={i} style={{
            fontFamily: 'var(--font-display)', fontWeight: 600,
            fontSize: 14, color: 'var(--cyan)', marginTop: 14, marginBottom: 6,
          }}>{line.slice(4)}</h4>
        )
        if (line.startsWith('- ') || line.startsWith('* ')) return (
          <div key={i} style={{
            display: 'flex', gap: 8, alignItems: 'flex-start',
            marginBottom: 4, color: 'var(--text2)',
          }}>
            <span style={{ color: 'var(--violet)', flexShrink: 0, marginTop: 2 }}>›</span>
            <span dangerouslySetInnerHTML={{ __html: _md(line.slice(2)) }} />
          </div>
        )
        if (line.trim() === '') return <div key={i} style={{ height: 8 }} />
        return (
          <p key={i} style={{ marginBottom: 6, color: 'var(--text2)' }}
            dangerouslySetInnerHTML={{ __html: _md(line) }} />
        )
      })}
    </div>
  )
}

/* ── Algorithm Tab ────────────────────────────────────────────────────────── */
function AlgorithmTab({ card }) {
  if (!card) return <Empty msg="Algorithm card not available." />
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header card */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(124,109,250,0.1), rgba(0,232,200,0.05))',
        border: '1px solid rgba(124,109,250,0.2)',
        borderRadius: 12, padding: '16px 18px',
      }}>
        <div style={{
          fontFamily: 'var(--font-display)', fontWeight: 800,
          fontSize: 18, color: 'var(--violet)', marginBottom: 4,
        }}>{card.name}</div>
        <div style={{
          fontSize: 12, color: 'var(--text3)',
          fontFamily: 'var(--font-mono)',
        }}>{card.family}</div>
      </div>

      {/* Why chosen */}
      <Section title="Why this algorithm?" icon="🎯">
        <p style={{ color: 'var(--text2)', lineHeight: 1.7, fontSize: 13 }}>{card.why_chosen}</p>
      </Section>

      {/* How it works */}
      <Section title="How it works" icon="⚙️">
        <p style={{ color: 'var(--text2)', lineHeight: 1.7, fontSize: 13 }}>{card.how_it_works}</p>
      </Section>

      {/* Strengths & Limitations */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Section title="Strengths" icon="✅">
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {(card.strengths || []).map((s, i) => (
              <li key={i} style={{
                display: 'flex', gap: 8, marginBottom: 5,
                fontSize: 12.5, color: 'var(--text2)',
              }}>
                <span style={{ color: 'var(--success)', flexShrink: 0 }}>✓</span>
                {s}
              </li>
            ))}
          </ul>
        </Section>
        <Section title="Limitations" icon="⚠️">
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {(card.limitations || []).map((l, i) => (
              <li key={i} style={{
                display: 'flex', gap: 8, marginBottom: 5,
                fontSize: 12.5, color: 'var(--text2)',
              }}>
                <span style={{ color: 'var(--warning)', flexShrink: 0 }}>!</span>
                {l}
              </li>
            ))}
          </ul>
        </Section>
      </div>

      {/* Metrics */}
      <Section title="Evaluation metrics" icon="📐">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {(card.metrics || []).map(m => (
            <span key={m} style={{
              background: 'rgba(0,232,200,0.08)',
              border: '1px solid rgba(0,232,200,0.2)',
              color: 'var(--cyan)', borderRadius: 8,
              padding: '4px 12px', fontSize: 12,
              fontFamily: 'var(--font-mono)',
            }}>{m}</span>
          ))}
        </div>
      </Section>
    </div>
  )
}

/* ── Data Story Tab ───────────────────────────────────────────────────────── */
function DataStoryTab({ story }) {
  if (!story) return <Empty msg="Data story not available." />
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Summary */}
      <div style={{
        background: 'rgba(0,232,200,0.06)',
        border: '1px solid rgba(0,232,200,0.2)',
        borderRadius: 12, padding: '14px 16px',
        fontSize: 13.5, color: 'var(--text)',
        lineHeight: 1.65,
      }} dangerouslySetInnerHTML={{ __html: _md(story.summary || '') }} />

      {/* Strategy */}
      <Section title="Search strategy" icon="🔍">
        <p style={{ color: 'var(--text2)', lineHeight: 1.7, fontSize: 13 }}
          dangerouslySetInnerHTML={{ __html: _md(story.search_strategy || '') }} />
      </Section>

      {/* Sources */}
      {story.sources && story.sources.length > 0 && (
        <Section title="Top datasets selected" icon="📦">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {story.sources.map((s, i) => (
              <div key={i} style={{
                background: 'var(--bg)', border: '1px solid var(--border)',
                borderRadius: 10, padding: '10px 14px',
                display: 'flex', alignItems: 'center', gap: 12,
              }}>
                <div style={{
                  width: 32, height: 32, borderRadius: 8,
                  background: _sourceColor(s.source),
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 10, fontWeight: 700, color: '#fff', flexShrink: 0,
                  fontFamily: 'var(--font-mono)',
                }}>{s.source?.slice(0, 3)}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 13, color: 'var(--text)', fontWeight: 500,
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  }}>{s.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>
                    {s.rows > 0 ? `${s.rows.toLocaleString()} rows` : ''} · score {s.score}
                  </div>
                </div>
                {s.url && (
                  <a href={s.url} target="_blank" rel="noreferrer" style={{
                    color: 'var(--violet)', fontSize: 11, textDecoration: 'none',
                    flexShrink: 0,
                  }}>View →</a>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Keywords */}
      {story.keywords_used && story.keywords_used.length > 0 && (
        <Section title="Search keywords used" icon="🏷">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {story.keywords_used.map(kw => (
              <span key={kw} style={{
                background: 'rgba(124,109,250,0.1)',
                border: '1px solid rgba(124,109,250,0.25)',
                color: 'var(--violet)', borderRadius: 20,
                padding: '3px 10px', fontSize: 12,
                fontFamily: 'var(--font-mono)',
              }}>{kw}</span>
            ))}
          </div>
        </Section>
      )}
    </div>
  )
}

/* ── Usage Tab ───────────────────────────────────────────────────────────── */
function UsageTab({ guide, deployUrl }) {
  if (!guide || guide.length === 0) return <Empty msg="Usage guide not available." />
  return (
    <div>
      {deployUrl && (
        <a href={deployUrl} target="_blank" rel="noreferrer" style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '12px 18px', marginBottom: 20,
          background: 'linear-gradient(135deg, var(--violet), #5a4fd4)',
          borderRadius: 12, textDecoration: 'none', color: '#fff',
          fontWeight: 700, fontSize: 14,
          fontFamily: 'var(--font-display)',
          boxShadow: '0 4px 20px rgba(124,109,250,0.4)',
        }}>
          <span style={{ fontSize: 20 }}>🚀</span>
          Open Live App
          <span style={{ marginLeft: 'auto', fontSize: 18 }}>→</span>
        </a>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {guide.map(step => (
          <div key={step.step} style={{
            display: 'flex', gap: 14, alignItems: 'flex-start',
            padding: '14px 16px',
            background: 'var(--bg)',
            border: '1px solid var(--border)',
            borderRadius: 12,
          }}>
            {/* Step number */}
            <div style={{
              width: 34, height: 34, borderRadius: '50%', flexShrink: 0,
              background: 'rgba(124,109,250,0.12)',
              border: '1px solid rgba(124,109,250,0.3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--font-display)', fontWeight: 800,
              color: 'var(--violet)', fontSize: 14,
            }}>{step.step}</div>
            <div style={{ flex: 1 }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5,
              }}>
                <span style={{ fontSize: 16 }}>{step.icon}</span>
                <span style={{
                  fontFamily: 'var(--font-display)', fontWeight: 600,
                  fontSize: 14, color: 'var(--text)',
                }}>{step.title}</span>
              </div>
              <div style={{
                fontSize: 13, color: 'var(--text2)', lineHeight: 1.65,
              }} dangerouslySetInnerHTML={{ __html: _md(step.detail) }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── Code Preview Tab ─────────────────────────────────────────────────────── */
function CodeTab({ preview }) {
  const [activeFile, setActiveFile] = useState(null)
  const files = Object.keys(preview || {})

  useEffect(() => {
    if (files.length > 0 && !activeFile) setActiveFile(files[0])
  }, [files])

  if (!preview || files.length === 0) return <Empty msg="No generated code to display." />

  const FILE_ICONS = {
    'app.py': '🌐', 'predictor.py': '🤖', 'train.py': '🚂',
    'requirements.txt': '📦', 'README.md': '📖',
    'tests/test_app.py': '🧪',
  }
  const FILE_COLORS = {
    'app.py': 'var(--violet)', 'predictor.py': 'var(--pink)',
    'train.py': 'var(--amber)', 'tests/test_app.py': 'var(--cyan)',
  }

  return (
    <div style={{ display: 'flex', gap: 12, height: 400 }}>
      {/* File list */}
      <div style={{
        width: 160, flexShrink: 0,
        display: 'flex', flexDirection: 'column', gap: 4,
      }}>
        {files.map(f => (
          <button key={f} onClick={() => setActiveFile(f)} style={{
            padding: '8px 10px', borderRadius: 8, border: 'none',
            cursor: 'pointer', textAlign: 'left',
            background: activeFile === f
              ? 'rgba(124,109,250,0.12)'
              : 'transparent',
            borderLeft: `2px solid ${activeFile === f
              ? FILE_COLORS[f] || 'var(--violet)'
              : 'transparent'}`,
            display: 'flex', alignItems: 'center', gap: 6,
            transition: 'all 0.15s',
          }}>
            <span style={{ fontSize: 14 }}>{FILE_ICONS[f] || '📄'}</span>
            <span style={{
              fontSize: 11, color: activeFile === f ? 'var(--text)' : 'var(--text3)',
              fontFamily: 'var(--font-mono)', fontWeight: activeFile === f ? 600 : 400,
              wordBreak: 'break-all',
            }}>{f}</span>
          </button>
        ))}
      </div>

      {/* Code viewer */}
      <div style={{
        flex: 1, overflow: 'hidden', borderRadius: 10,
        border: '1px solid var(--border)',
        background: 'var(--bg)',
      }}>
        {/* File header */}
        <div style={{
          padding: '8px 14px', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 8,
          background: 'var(--card)',
        }}>
          <span style={{ fontSize: 14 }}>{FILE_ICONS[activeFile] || '📄'}</span>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 12,
            color: FILE_COLORS[activeFile] || 'var(--violet)',
          }}>{activeFile}</span>
          <button
            onClick={() => navigator.clipboard?.writeText(preview[activeFile] || '')}
            style={{
              marginLeft: 'auto', background: 'none', border: '1px solid var(--border)',
              borderRadius: 6, cursor: 'pointer', padding: '2px 8px',
              color: 'var(--text3)', fontSize: 10, fontFamily: 'var(--font-mono)',
              transition: 'all 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--violet)'}
            onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
          >copy</button>
        </div>
        {/* Code content */}
        <div style={{ height: 'calc(100% - 36px)', overflowY: 'auto' }}>
          <SyntaxHighlighter
            language={activeFile?.endsWith('.py') ? 'python' : 'bash'}
            style={vscDarkPlus}
            customStyle={{ margin: 0, padding: '12px 14px', background: 'transparent', fontSize: '11.5px', fontFamily: 'var(--font-mono)' }}
            showLineNumbers={true}
          >
            {preview[activeFile] || ''}
          </SyntaxHighlighter>
        </div>
      </div>
    </div>
  )
}

/* ── Architecture Diagram Tab ─────────────────────────────────────────────── */
function DiagramTab({ b64 }) {
  const [zoom, setZoom] = useState(1)

  if (!b64) return (
    <div style={{ textAlign: 'center', padding: '40px 0' }}>
      <div style={{ fontSize: 48, marginBottom: 12, opacity: 0.3 }}>🏗</div>
      <div style={{ color: 'var(--text3)', fontSize: 13 }}>
        Architecture diagram not available.<br />
        <span style={{ fontSize: 11 }}>
          Ensure the <code style={{ fontFamily: 'var(--font-mono)' }}>diagrams</code> library and
          Graphviz are installed.
        </span>
      </div>
      <div style={{ marginTop: 16, fontSize: 11, color: 'var(--text3)', fontFamily: 'var(--font-mono)' }}>
        pip install diagrams<br />
        apt-get install graphviz
      </div>
    </div>
  )

  return (
    <div>
      {/* Controls */}
      <div style={{
        display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center',
      }}>
        <span style={{ fontSize: 12, color: 'var(--text3)' }}>Zoom:</span>
        {[0.5, 0.75, 1, 1.25, 1.5].map(z => (
          <button key={z} onClick={() => setZoom(z)} style={{
            padding: '4px 10px', borderRadius: 6,
            border: `1px solid ${zoom === z ? 'var(--violet)' : 'var(--border)'}`,
            background: zoom === z ? 'rgba(124,109,250,0.12)' : 'transparent',
            color: zoom === z ? 'var(--violet)' : 'var(--text3)',
            cursor: 'pointer', fontSize: 11,
            fontFamily: 'var(--font-mono)',
          }}>{Math.round(z * 100)}%</button>
        ))}
        <a href={`data:image/png;base64,${b64}`} download="pipeline_architecture.png"
          style={{
            marginLeft: 'auto', padding: '4px 12px',
            background: 'rgba(0,232,200,0.08)',
            border: '1px solid rgba(0,232,200,0.2)',
            borderRadius: 6, color: 'var(--cyan)', fontSize: 11,
            textDecoration: 'none', fontFamily: 'var(--font-mono)',
          }}>
          ↓ Download PNG
        </a>
      </div>

      {/* Diagram image */}
      <div style={{
        overflowAuto: 'auto', borderRadius: 10,
        border: '1px solid var(--border)',
        background: '#0d0d1a',
        textAlign: 'center', overflow: 'auto',
        maxHeight: 380,
      }}>
        <img
          src={`data:image/png;base64,${b64}`}
          alt="Pipeline Architecture Diagram"
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: 'top left',
            maxWidth: '100%',
            display: 'block',
            transition: 'transform 0.2s ease',
          }}
        />
      </div>

      {/* Legend */}
      <div style={{
        marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 14,
        fontSize: 11, color: 'var(--text3)',
        fontFamily: 'var(--font-mono)',
      }}>
        {[
          { color: '#00e8c8', label: 'Data Collection' },
          { color: '#f065ad', label: 'Code Generator' },
          { color: '#7c6dfa', label: 'Data flow' },
        ].map(l => (
          <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{
              width: 10, height: 10, borderRadius: 2,
              background: l.color, flexShrink: 0,
            }} />
            {l.label}
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── Shared atoms ─────────────────────────────────────────────────────────── */
function Section({ title, icon, children }) {
  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 7,
        marginBottom: 10,
        fontSize: 11, color: 'var(--text3)',
        fontFamily: 'var(--font-mono)',
        textTransform: 'uppercase', letterSpacing: 0.8,
      }}>
        <span style={{ fontSize: 14 }}>{icon}</span>
        {title}
      </div>
      <div style={{ paddingLeft: 4 }}>{children}</div>
    </div>
  )
}

function Empty({ msg }) {
  return (
    <div style={{
      textAlign: 'center', padding: '40px 0',
      color: 'var(--text3)', fontSize: 13,
    }}>
      <div style={{ fontSize: 32, marginBottom: 8, opacity: 0.3 }}>📭</div>
      {msg}
    </div>
  )
}

function LoadingCard() {
  return (
    <div style={{
      marginTop: 20, padding: '30px', textAlign: 'center',
      border: '1px solid var(--border)', borderRadius: 18,
      background: 'var(--surface)',
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: '50%',
        border: '3px solid rgba(124,109,250,0.2)',
        borderTopColor: 'var(--violet)',
        animation: 'spin 0.9s linear infinite',
        margin: '0 auto 12px',
      }} />
      <div style={{ color: 'var(--text3)', fontSize: 13 }}>
        Loading explainability report…
      </div>
    </div>
  )
}

function ErrorCard({ msg }) {
  return (
    <div style={{
      marginTop: 20, padding: '16px',
      border: '1px solid rgba(255,80,112,0.2)', borderRadius: 12,
      background: 'rgba(255,80,112,0.05)',
      color: 'var(--error)', fontSize: 13,
      fontFamily: 'var(--font-mono)',
    }}>
      {msg}
    </div>
  )
}

/* ── Helpers ──────────────────────────────────────────────────────────────── */
function _sourceColor(src) {
  const map = { KAGGLE: '#20beff', UCI: '#ff6b35', OPENML: '#ff0066' }
  return map[src?.toUpperCase()] || '#7c6dfa'
}

// Very basic markdown → HTML
function _md(text) {
  return (text || '')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, `<code style="font-family:var(--font-mono);font-size:0.9em;background:rgba(124,109,250,0.12);padding:1px 5px;border-radius:4px;color:var(--violet)">$1</code>`)
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color:var(--violet)">$1</a>')
}

// Extremely lightweight syntax highlight for display purposes
function _syntaxHighlight(filename, code) {
  if (filename.endsWith('.md') || filename.endsWith('.txt')) {
    return <span style={{ color: 'var(--text2)' }}>{code}</span>
  }
  // Split into lines and colour keywords
  const keywords = /\b(def|class|import|from|return|if|elif|else|for|while|try|except|with|as|and|or|not|in|is|True|False|None|pass|raise|lambda|yield|async|await)\b/g
  const strings  = /(["'])(?:(?=(\\?))\2.)*?\1/g
  const comments = /#.*/g
  const nums     = /\b\d+\.?\d*\b/g

  const lines = code.split('\n')
  return lines.map((line, i) => {
    let colored = line
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    // Apply colouring via inline span injection (simplified)
    colored = colored
      .replace(/#(.*)$/, '<span style="color:#5a8a6a">$&</span>')
      .replace(/\b(def|class|import|from|return|if|elif|else|for|while|try|except|with|as|raise|async|await)\b/g,
               '<span style="color:#c084fc">$1</span>')
      .replace(/\b(True|False|None)\b/g,
               '<span style="color:#00e8c8">$1</span>')
      .replace(/(["'])(.*?)\1/g,
               '<span style="color:#86efac">$&</span>')
      .replace(/\b(\d+\.?\d*)\b/g,
               '<span style="color:#fbbf24">$1</span>')
    return (
      <div key={i} style={{ display: 'flex', gap: 0 }}>
        <span style={{
          color: '#3a3a5a', minWidth: 36, textAlign: 'right',
          paddingRight: 12, userSelect: 'none', flexShrink: 0,
          fontSize: 10,
        }}>{i + 1}</span>
        <span dangerouslySetInnerHTML={{ __html: colored }} />
      </div>
    )
  })
}
