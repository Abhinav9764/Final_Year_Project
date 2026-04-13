import React, { useState } from 'react'
import ExplainPanel from './ExplainPanel.jsx'

const TABS = [
  { id: 'summary',  label: '📊 Summary' },
  { id: 'dataset',  label: '🗃 Dataset' },
  { id: 'model',    label: '🤖 Model' },
  { id: 'files',    label: '📁 Files' },
  { id: 'explain',  label: '🔍 Explain' },
]

export default function ResultCard({ result, jobId, getToken }) {
  const [tab, setTab] = useState('summary')
  if (!result || !result.deploy_url) return null

  const {
    deploy_url, dataset = {}, model = {},
    input_params = [], target_param,
    sm_meta = {}, generated_files = {},
    validation_summary = '',
  } = result

  return (
    <div style={{
      marginTop: 20,
      border: '1px solid rgba(0,232,200,0.25)',
      borderRadius: 18,
      overflow: 'hidden',
      background: 'var(--surface)',
      boxShadow: '0 0 40px rgba(0,232,200,0.06), 0 12px 40px rgba(0,0,0,0.4)',
      animation: 'fadeSlideUp 0.4s ease both',
    }}>
      {/* ── Success header ── */}
      <div style={{
        padding: '16px 22px',
        borderBottom: '1px solid var(--border)',
        background: 'linear-gradient(135deg, rgba(0,232,200,0.06) 0%, rgba(124,109,250,0.06) 100%)',
        display: 'flex', alignItems: 'center', gap: 14,
      }}>
        {/* Animated success ring */}
        <div style={{
          width: 36, height: 36, borderRadius: '50%',
          background: 'rgba(0,232,200,0.12)',
          border: '2px solid var(--cyan)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 16, flexShrink: 0,
          boxShadow: '0 0 20px rgba(0,232,200,0.3)',
        }}>✓</div>

        <div style={{ flex: 1 }}>
          <div style={{
            fontFamily: 'var(--font-display)', fontWeight: 700,
            fontSize: 15, color: 'var(--text)',
          }}>Pipeline Complete</div>
          {validation_summary && (
            <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 1 }}>
              {validation_summary}
            </div>
          )}
        </div>

        {/* Open App CTA */}
        <a href={deploy_url} target="_blank" rel="noreferrer" style={{
          padding: '9px 20px',
          background: 'linear-gradient(135deg, var(--violet), #5a4fd4)',
          color: '#fff', textDecoration: 'none',
          borderRadius: 10, fontSize: 13, fontWeight: 700,
          fontFamily: 'var(--font-display)',
          display: 'flex', alignItems: 'center', gap: 6,
          boxShadow: '0 4px 16px rgba(124,109,250,0.4)',
          transition: 'all 0.2s', flexShrink: 0,
          whiteSpace: 'nowrap',
        }}
          onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-1px)'}
          onMouseLeave={e => e.currentTarget.style.transform = 'none'}
        >
          Open App <span style={{ fontSize: 16 }}>→</span>
        </a>
      </div>

      {/* ── Tabs ── */}
      <div style={{
        display: 'flex', borderBottom: '1px solid var(--border)',
        background: 'var(--bg)', overflowX: 'auto',
      }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: '10px 18px', border: 'none', background: 'none',
            cursor: 'pointer', fontSize: 12.5, whiteSpace: 'nowrap',
            color: tab === t.id ? 'var(--cyan)' : 'var(--text3)',
            borderBottom: `2px solid ${tab === t.id ? 'var(--cyan)' : 'transparent'}`,
            fontFamily: 'var(--font-body)', fontWeight: tab === t.id ? 600 : 400,
            transition: 'all 0.15s',
          }}>{t.label}</button>
        ))}
      </div>

      {/* ── Tab content ── */}
      <div style={{ padding: '20px 22px' }}>
        {tab === 'summary' && (
          <SummaryTab
            deploy_url={deploy_url} input_params={input_params}
            target_param={target_param} sm_meta={sm_meta}
            dataset={dataset} model={model}
          />
        )}
        {tab === 'dataset' && <DatasetTab dataset={dataset} />}
        {tab === 'model'   && <ModelTab model={model} sm_meta={sm_meta} />}
        {tab === 'files'   && <FilesTab files={generated_files} />}
        {tab === 'explain' && (
          <ExplainPanel
            jobId={jobId}
            result={result}
            getToken={getToken}
          />
        )}
      </div>
    </div>
  )
}

/* ── Summary Tab ────────────────────────────────────────────────────────── */
function SummaryTab({ deploy_url, input_params, target_param, sm_meta, dataset, model }) {
  return (
    <div>
      {/* Key metrics grid */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
        gap: 10, marginBottom: 20,
      }}>
        <MetricCard icon="🎯" label="Task type" value={model.task_type || '—'} color="var(--violet)" />
        <MetricCard icon="📊" label="Dataset rows" value={(dataset.row_count || 0).toLocaleString()} color="var(--cyan)" />
        <MetricCard icon="🔢" label="Features" value={model.feature_cols?.length || 0} color="var(--pink)" />
        <MetricCard icon="🚂" label="Train rows" value={(model.stats?.train_rows || 0).toLocaleString()} color="var(--amber)" />
      </div>

      {/* Input → Output flow */}
      {input_params.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{
            fontSize: 11, color: 'var(--text3)',
            fontFamily: 'var(--font-mono)', marginBottom: 10,
            textTransform: 'uppercase', letterSpacing: 1,
          }}>Inference Flow</div>
          <div style={{
            display: 'flex', alignItems: 'center',
            gap: 10, flexWrap: 'wrap',
          }}>
            {/* Inputs */}
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {input_params.map(p => (
                <Chip key={p} label={p} color="var(--violet)" />
              ))}
            </div>
            {/* Arrow */}
            <span style={{
              fontSize: 20, color: 'var(--text3)',
              flexShrink: 0,
            }}>→</span>
            {/* Output */}
            <div style={{
              padding: '4px 14px',
              background: 'rgba(0,232,200,0.1)',
              border: '1px solid rgba(0,232,200,0.3)',
              borderRadius: 20, fontSize: 12,
              color: 'var(--cyan)', fontWeight: 600,
            }}>
              {target_param || 'prediction'}
            </div>
          </div>
        </div>
      )}

      {/* Technical details */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr',
        gap: 8,
      }}>
        <DetailRow label="Endpoint" value={sm_meta.endpoint_name} mono />
        <DetailRow label="Job name"  value={sm_meta.job_name}      mono />
        <DetailRow label="Status"    value={sm_meta.status} />
        <DetailRow label="Merged"    value={String(dataset.merged || false)} />
        {dataset.s3_uri && (
          <div style={{ gridColumn: '1 / -1' }}>
            <DetailRow label="S3 URI" value={dataset.s3_uri} mono />
          </div>
        )}
      </div>
    </div>
  )
}

/* ── Dataset Tab ────────────────────────────────────────────────────────── */
function DatasetTab({ dataset }) {
  const { row_count = 0, columns = [], preview_rows = [], source_count, merged, s3_uri } = dataset

  return (
    <div>
      {/* Stats row */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 18, flexWrap: 'wrap' }}>
        <StatBadge label="Rows"    value={(row_count).toLocaleString()} />
        <StatBadge label="Columns" value={columns.length} />
        <StatBadge label="Sources" value={source_count || 1} />
        <StatBadge label="Merged"  value={merged ? 'Yes' : 'No'} />
      </div>

      {/* Column list */}
      {columns.length > 0 && (
        <div style={{ marginBottom: 18 }}>
          <div style={{
            fontSize: 11, color: 'var(--text3)',
            fontFamily: 'var(--font-mono)', marginBottom: 8,
            textTransform: 'uppercase', letterSpacing: 1,
          }}>Columns ({columns.length})</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {columns.map(c => (
              <span key={c} style={{
                fontFamily: 'var(--font-mono)', fontSize: 11,
                background: 'var(--card)', border: '1px solid var(--border)',
                borderRadius: 6, padding: '2px 8px', color: 'var(--text2)',
              }}>{c}</span>
            ))}
          </div>
        </div>
      )}

      {/* Data preview table */}
      {preview_rows.length > 0 && (
        <>
          <div style={{
            fontSize: 11, color: 'var(--text3)',
            fontFamily: 'var(--font-mono)', marginBottom: 8,
            textTransform: 'uppercase', letterSpacing: 1,
          }}>Preview — first 10 rows</div>
          <div style={{
            overflowX: 'auto', borderRadius: 10,
            border: '1px solid var(--border)',
          }}>
            <table style={{
              borderCollapse: 'collapse', width: '100%',
              fontSize: 11.5, fontFamily: 'var(--font-mono)',
            }}>
              <thead>
                <tr style={{ background: 'var(--card)' }}>
                  {Object.keys(preview_rows[0]).map(col => (
                    <th key={col} style={{
                      padding: '8px 12px', textAlign: 'left',
                      color: 'var(--cyan)', fontWeight: 600,
                      borderBottom: '1px solid var(--border)',
                      whiteSpace: 'nowrap', fontSize: 11,
                    }}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview_rows.map((row, i) => (
                  <tr key={i} style={{
                    background: i % 2 ? 'rgba(255,255,255,0.015)' : 'transparent',
                  }}>
                    {Object.values(row).map((v, j) => (
                      <td key={j} style={{
                        padding: '6px 12px', color: 'var(--text2)',
                        borderBottom: '1px solid rgba(37,37,64,0.5)',
                        whiteSpace: 'nowrap', maxWidth: 160,
                        overflow: 'hidden', textOverflow: 'ellipsis',
                        fontSize: 11,
                      }}>
                        {v == null ? <span style={{ color: 'var(--text3)' }}>null</span> : String(v)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

/* ── Model Tab ────────────────────────────────────────────────────────── */
function ModelTab({ model, sm_meta }) {
  const { feature_cols = [], target_col, task_type, stats = {} } = model
  return (
    <div>
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
        gap: 10, marginBottom: 20,
      }}>
        <MetricCard icon="🎯" label="Task type"   value={task_type || '—'}           color="var(--violet)" />
        <MetricCard icon="🏆" label="Target"      value={target_col || '—'}           color="var(--cyan)" />
        <MetricCard icon="🚂" label="Train rows"  value={(stats.train_rows || 0).toLocaleString()} color="var(--pink)" />
        <MetricCard icon="🧪" label="Val rows"    value={(stats.val_rows || 0).toLocaleString()} color="var(--amber)" />
        <MetricCard icon="🔢" label="Features"    value={stats.num_features || feature_cols.length} color="var(--violet)" />
      </div>

      {feature_cols.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{
            fontSize: 11, color: 'var(--text3)',
            fontFamily: 'var(--font-mono)', marginBottom: 8,
            textTransform: 'uppercase', letterSpacing: 1,
          }}>Feature columns (SageMaker CSV order)</div>
          <div style={{
            background: 'var(--bg)', borderRadius: 10,
            border: '1px solid var(--border)', padding: '12px 14px',
            fontFamily: 'var(--font-mono)', fontSize: 12,
          }}>
            {feature_cols.map((f, i) => (
              <div key={f} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '3px 0',
                borderBottom: i < feature_cols.length - 1
                  ? '1px solid rgba(37,37,64,0.4)' : 'none',
              }}>
                <span style={{
                  color: 'var(--text3)', minWidth: 24,
                  textAlign: 'right', fontSize: 10,
                }}>{i}</span>
                <span style={{ color: 'var(--violet)' }}>{f}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SageMaker details */}
      {sm_meta.endpoint_name && (
        <div style={{
          background: 'var(--bg)', borderRadius: 10,
          border: '1px solid var(--border)', padding: '14px',
        }}>
          <div style={{
            fontSize: 11, color: 'var(--text3)',
            fontFamily: 'var(--font-mono)', marginBottom: 10,
            textTransform: 'uppercase', letterSpacing: 1,
          }}>SageMaker Details</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <DetailRow label="Endpoint"  value={sm_meta.endpoint_name} mono />
            <DetailRow label="Job"       value={sm_meta.job_name}      mono />
            <DetailRow label="Status"    value={sm_meta.status} />
            <DetailRow label="Framework" value={sm_meta.framework || 'XGBoost'} />
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Files Tab ────────────────────────────────────────────────────────── */
function FilesTab({ files }) {
  const entries = Object.entries(files || {})
  if (entries.length === 0) {
    return (
      <div style={{ color: 'var(--text3)', fontSize: 13, padding: '20px 0', textAlign: 'center' }}>
        No generated files to display.
      </div>
    )
  }
  const fileIcons = {
    'app.py': '🌐', 'predictor.py': '🤖', 'train.py': '🚂',
    'requirements.txt': '📦', 'README.md': '📖',
    'tests/test_app.py': '🧪',
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{
        fontSize: 11, color: 'var(--text3)',
        fontFamily: 'var(--font-mono)', marginBottom: 4,
        textTransform: 'uppercase', letterSpacing: 1,
      }}>Generated workspace files</div>
      {entries.map(([name, path]) => (
        <div key={name} style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '10px 14px',
          background: 'var(--bg)', borderRadius: 8,
          border: '1px solid var(--border)',
        }}>
          <span style={{ fontSize: 18, flexShrink: 0 }}>{fileIcons[name] || '📄'}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontFamily: 'var(--font-mono)', fontSize: 12,
              color: 'var(--text)', fontWeight: 600,
            }}>{name}</div>
            <div style={{
              fontFamily: 'var(--font-mono)', fontSize: 10,
              color: 'var(--text3)', marginTop: 2,
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            }}>{path}</div>
          </div>
          <span style={{
            background: 'rgba(0,232,200,0.08)',
            border: '1px solid rgba(0,232,200,0.2)',
            color: 'var(--cyan)', borderRadius: 6,
            padding: '2px 8px', fontSize: 10,
            fontFamily: 'var(--font-mono)',
          }}>generated</span>
        </div>
      ))}
    </div>
  )
}

/* ── Shared atoms ────────────────────────────────────────────────────────── */
function MetricCard({ icon, label, value, color }) {
  return (
    <div style={{
      background: 'var(--bg)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '12px 14px',
    }}>
      <div style={{ fontSize: 18, marginBottom: 6 }}>{icon}</div>
      <div style={{
        fontSize: 18, fontWeight: 700, color: color || 'var(--text)',
        fontFamily: 'var(--font-display)', lineHeight: 1,
      }}>{value}</div>
      <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 4 }}>{label}</div>
    </div>
  )
}

function StatBadge({ label, value }) {
  return (
    <div style={{
      background: 'var(--bg)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '6px 14px',
      display: 'flex', alignItems: 'center', gap: 6,
    }}>
      <span style={{ fontSize: 11, color: 'var(--text3)' }}>{label}:</span>
      <span style={{ fontSize: 12, color: 'var(--cyan)', fontWeight: 600 }}>{value}</span>
    </div>
  )
}

function DetailRow({ label, value, mono }) {
  return (
    <div style={{
      background: 'var(--card)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '8px 12px',
    }}>
      <div style={{ fontSize: 10, color: 'var(--text3)', marginBottom: 3 }}>{label}</div>
      <div style={{
        fontSize: 12, color: 'var(--text)',
        fontFamily: mono ? 'var(--font-mono)' : 'var(--font-body)',
        wordBreak: 'break-all', lineHeight: 1.4,
      }}>{value || '—'}</div>
    </div>
  )
}

function Chip({ label, color }) {
  return (
    <span style={{
      padding: '3px 12px',
      background: `${color}18`, border: `1px solid ${color}44`,
      borderRadius: 20, fontSize: 12, color: color,
      fontFamily: 'var(--font-mono)',
    }}>{label}</span>
  )
}
