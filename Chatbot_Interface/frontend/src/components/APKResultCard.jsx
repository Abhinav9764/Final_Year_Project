/**
 * VM-ERA APK Analysis Result Card
 * =================================
 * Displays complete malware analysis results including:
 * - Visual fingerprint viewer
 * - Risk gauge
 * - Ensemble model breakdown
 * - Permission security flags
 */
import React, { useState } from 'react';
import RiskGauge from './RiskGauge';

export default function APKResultCard({ result }) {
  const [activeTab, setActiveTab] = useState('overview');

  if (!result) return null;

  const {
    prediction,
    permissions,
    fingerprint,
    file_name,
    apk_size,
    dex_size
  } = result;

  const {
    final_risk_score,
    verdict,
    individual_predictions,
    confidence,
    models_used
  } = prediction || {};

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getVerdictIcon = (v) => {
    switch (v) {
      case 'malware': return '🚫';
      case 'suspicious': return '⚠️';
      case 'benign': return '✓';
      default: return '?';
    }
  };

  const getVerdictColor = (v) => {
    switch (v) {
      case 'malware': return 'var(--error)';
      case 'suspicious': return 'var(--warning)';
      case 'benign': return 'var(--success)';
      default: return 'var(--text3)';
    }
  };

  return (
    <div className="apk-result-card glass-panel">
      {/* Header */}
      <div className="apk-result-header">
        <div className="apk-file-info">
          <div className="apk-icon">📦</div>
          <div>
            <h3 className="apk-filename">{file_name}</h3>
            <p className="apk-meta">
              APK: {formatBytes(apk_size)} · DEX: {formatBytes(dex_size)}
            </p>
          </div>
        </div>
        <div className="apk-verdict-badge" style={{
          background: `${getVerdictColor(verdict)}20`,
          border: `1px solid ${getVerdictColor(verdict)}40`,
          color: getVerdictColor(verdict)
        }}>
          <span className="verdict-icon">{getVerdictIcon(verdict)}</span>
          <span className="verdict-text">{verdict?.toUpperCase()}</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="apk-tabs">
        <button
          className={`apk-tab ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button
          className={`apk-tab ${activeTab === 'fingerprint' ? 'active' : ''}`}
          onClick={() => setActiveTab('fingerprint')}
        >
          Fingerprint
        </button>
        <button
          className={`apk-tab ${activeTab === 'permissions' ? 'active' : ''}`}
          onClick={() => setActiveTab('permissions')}
        >
          Permissions ({permissions?.high_risk?.length || 0})
        </button>
      </div>

      {/* Tab Content */}
      <div className="apk-tab-content">
        {activeTab === 'overview' && (
          <OverviewTab
            prediction={prediction}
            individual_predictions={individual_predictions}
            confidence={confidence}
          />
        )}

        {activeTab === 'fingerprint' && (
          <FingerprintTab fingerprint={fingerprint} />
        )}

        {activeTab === 'permissions' && (
          <PermissionsTab permissions={permissions} />
        )}
      </div>
    </div>
  );
}

/**
 * Overview Tab - Risk gauge and model breakdown
 */
function OverviewTab({ prediction, individual_predictions, confidence }) {
  return (
    <div className="overview-tab">
      {/* Risk Gauge Section */}
      <div className="gauge-section">
        <RiskGauge score={prediction?.final_risk_score || 0} verdict={prediction?.verdict || 'unknown'} />
      </div>

      {/* Model Breakdown */}
      <div className="model-breakdown">
        <h4 className="section-title">Ensemble Analysis</h4>

        {individual_predictions && Object.entries(individual_predictions).map(([model, data]) => (
          <div key={model} className="model-row">
            <div className="model-header">
              <span className="model-name">{model.toUpperCase()}</span>
              <span className="model-prob" style={{
                color: getProbabilityColor(data.probability)
              }}>
                {(data.probability * 100).toFixed(1)}%
              </span>
            </div>
            <div className="model-bar-container">
              <div
                className="model-bar"
                style={{
                  width: `${data.probability * 100}%`,
                  background: getProbabilityGradient(data.probability)
                }}
              />
            </div>
            <div className="model-confidence">
              Confidence: {(data.confidence * 100).toFixed(0)}%
            </div>
          </div>
        ))}

        {/* Overall Confidence */}
        <div className="overall-confidence">
          <span>Overall Confidence</span>
          <span style={{ color: confidence > 0.7 ? 'var(--success)' : 'var(--warning)' }}>
            {(confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>
    </div>
  );
}

/**
 * Fingerprint Tab - Visual signature viewer
 */
function FingerprintTab({ fingerprint }) {
  return (
    <div className="fingerprint-tab">
      <div className="fingerprint-container">
        <div className="fingerprint-frame">
          {fingerprint && (
            <img
              src={`data:image/png;base64,${fingerprint}`}
              alt="APK Visual Fingerprint"
              className="fingerprint-image"
            />
          )}
          {/* Scan line animation */}
          <div className="scan-line" />
        </div>
        <div className="fingerprint-info">
          <h4>Visual Signature</h4>
          <p className="fingerprint-desc">
            This image represents the binary bytecode pattern of the APK's classes.dex file.
            Malware families often produce visually similar fingerprints.
          </p>
          <div className="fingerprint-stats">
            <div className="stat">
              <span className="stat-label">Resolution</span>
              <span className="stat-value">128×128</span>
            </div>
            <div className="stat">
              <span className="stat-label">Format</span>
              <span className="stat-value">Grayscale</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Permissions Tab - Security flags
 */
function PermissionsTab({ permissions }) {
  const { high_risk = [], all_permissions = [], risk_score = 0, categories = [] } = permissions || {};

  const getCategoryColor = (cat) => {
    const colors = {
      privacy: 'var(--violet)',
      financial: 'var(--error)',
      system: 'var(--error)',
      network: 'var(--cyan)',
      storage: 'var(--warning)',
      device: 'var(--warning)',
      persistence: 'var(--error)'
    };
    return colors[cat] || 'var(--text2)';
  };

  const getSeverityIcon = (sev) => {
    switch (sev) {
      case 'critical': return '🔴';
      case 'high': return '🟠';
      case 'medium': return '🟡';
      case 'low': return '🟢';
      default: return '⚪';
    }
  };

  return (
    <div className="permissions-tab">
      {/* Risk Score Summary */}
      <div className="permission-summary">
        <div className="summary-card">
          <span className="summary-label">Permission Risk Score</span>
          <span className={`summary-value ${risk_score >= 70 ? 'high' : risk_score >= 40 ? 'medium' : 'low'}`}>
            {risk_score}/100
          </span>
        </div>
        <div className="summary-card">
          <span className="summary-label">Total Permissions</span>
          <span className="summary-value">{all_permissions.length}</span>
        </div>
        <div className="summary-card">
          <span className="summary-label">High Risk</span>
          <span className="summary-value high">{high_risk.length}</span>
        </div>
      </div>

      {/* Categories */}
      {categories.length > 0 && (
        <div className="categories-section">
          <h4>Risk Categories</h4>
          <div className="category-tags">
            {categories.map((cat) => (
              <span
                key={cat}
                className="category-tag"
                style={{ borderColor: getCategoryColor(cat), color: getCategoryColor(cat) }}
              >
                {cat}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* High Risk Permissions List */}
      {high_risk.length > 0 && (
        <div className="high-risk-section">
          <h4>⚠️ High-Risk Permissions Detected</h4>
          <div className="permission-list">
            {high_risk.map((perm, i) => (
              <div key={i} className="permission-item">
                <div className="perm-icon">{getSeverityIcon(perm.severity)}</div>
                <div className="perm-details">
                  <div className="perm-name">{perm.permission}</div>
                  <div className="perm-meta">
                    <span className="perm-severity" style={{ color: getCategoryColor(perm.category) }}>
                      {perm.severity.toUpperCase()}
                    </span>
                    <span className="perm-category">{perm.category}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* All Permissions */}
      {all_permissions.length > 0 && (
        <div className="all-permissions-section">
          <h4>All Permissions ({all_permissions.length})</h4>
          <div className="permission-grid">
            {all_permissions.map((perm, i) => (
              <code key={i} className="permission-chip">
                {perm.replace('android.permission.', '')}
              </code>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Helper functions
 */
function getProbabilityColor(prob) {
  if (prob >= 0.7) return 'var(--error)';
  if (prob >= 0.4) return 'var(--warning)';
  return 'var(--success)';
}

function getProbabilityGradient(prob) {
  if (prob >= 0.7) return 'linear-gradient(90deg, var(--error), #ff8094)';
  if (prob >= 0.4) return 'linear-gradient(90deg, var(--warning), #ffd48a)';
  return 'linear-gradient(90deg, var(--success), #4ff5dc)';
}
