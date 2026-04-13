/**
 * VM-ERA Risk Gauge Component
 * ============================
 * Animated SVG gauge showing malware risk score (0-100).
 * Features:
 * - Color-coded risk levels (green/yellow/red)
 * - Smooth animated needle
 * - Digital readout display
 */
import React, { useEffect, useState } from 'react';

export default function RiskGauge({ score = 0, verdict = 'unknown', size = 200 }) {
  const [displayScore, setDisplayScore] = useState(0);
  const [animatedVerdict, setAnimatedVerdict] = useState('Scanning...');

  // Animate score on mount/change
  useEffect(() => {
    const targetScore = Math.round(score);
    const duration = 1500;
    const startTime = Date.now();

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const currentScore = Math.round(eased * targetScore);

      setDisplayScore(currentScore);

      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        // Set final verdict after animation
        setTimeout(() => {
          setAnimatedVerdict(verdict);
        }, 300);
      }
    };

    requestAnimationFrame(animate);
  }, [score, verdict]);

  // Calculate gauge colors based on score
  const getGaugeColors = () => {
    if (score >= 70) {
      return {
        primary: '#ff5070',    // Red - Malware
        secondary: '#ff8094',
        glow: 'rgba(255, 80, 112, 0.4)',
        gradient: 'url(#gradient-danger)'
      };
    } else if (score >= 40) {
      return {
        primary: '#ffb54a',    // Yellow - Suspicious
        secondary: '#ffd48a',
        glow: 'rgba(255, 181, 74, 0.4)',
        gradient: 'url(#gradient-warning)'
      };
    } else {
      return {
        primary: '#00e8c8',    // Cyan - Benign
        secondary: '#4ff5dc',
        glow: 'rgba(0, 232, 200, 0.4)',
        gradient: 'url(#gradient-safe)'
      };
    }
  };

  const colors = getGaugeColors();

  // Calculate needle rotation (-90 to 90 degrees)
  const needleRotation = (score / 100) * 180 - 90;

  const viewBox = size;
  const centerX = size / 2;
  const centerY = size / 2 - 20;
  const radius = size * 0.38;

  return (
    <div className="risk-gauge" style={{ width: size, height: size * 1.1 }}>
      <svg viewBox={`0 0 ${viewBox} ${viewBox}`} className="gauge-svg">
        <defs>
          {/* Gradients */}
          <linearGradient id="gradient-safe" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#00e8c8" />
            <stop offset="100%" stopColor="#4ff5dc" />
          </linearGradient>
          <linearGradient id="gradient-warning" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#ffb54a" />
            <stop offset="100%" stopColor="#ffd48a" />
          </linearGradient>
          <linearGradient id="gradient-danger" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#ff8094" />
            <stop offset="100%" stopColor="#ff5070" />
          </linearGradient>

          {/* Glow filter */}
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Background arc */}
        <path
          d={describeArc(centerX, centerY, radius, -90, 90, 24)}
          fill="none"
          stroke="rgba(255,255,255,0.05)"
          strokeWidth="24"
          strokeLinecap="round"
        />

        {/* Colored arc - animated */}
        <path
          d={describeArc(centerX, centerY, radius, -90, 90, 24)}
          fill="none"
          stroke={colors.gradient}
          strokeWidth="24"
          strokeLinecap="round"
          className="gauge-arc"
          style={{
            strokeDasharray: Math.PI * radius,
            strokeDashoffset: Math.PI * radius * (1 - score / 100),
            transition: 'stroke-dashoffset 1.5s cubic-bezier(0.4, 0, 0.2, 1)',
            filter: 'url(#glow)'
          }}
        />

        {/* Tick marks */}
        {[-90, -45, 0, 45, 90].map((angle, i) => {
          const tickStart = polarToCartesian(centerX, centerY, radius - 35, angle);
          const tickEnd = polarToCartesian(centerX, centerY, radius - 20, angle);
          const isMajor = angle % 45 === 0;
          return (
            <line
              key={i}
              x1={tickStart.x}
              y1={tickStart.y}
              x2={tickEnd.x}
              y2={tickEnd.y}
              stroke="rgba(255,255,255,0.3)"
              strokeWidth={isMajor ? 2 : 1}
              strokeLinecap="round"
            />
          );
        })}

        {/* Labels */}
        <text x={centerX - 45} y={centerY + radius - 5} fill="rgba(255,255,255,0.5)" fontSize="10" fontFamily="var(--font-mono)">0</text>
        <text x={centerX - 8} y={centerY + radius - 5} fill="rgba(255,255,255,0.5)" fontSize="10" fontFamily="var(--font-mono)" textAnchor="middle">50</text>
        <text x={centerX + 35} y={centerY + radius - 5} fill="rgba(255,255,255,0.5)" fontSize="10" fontFamily="var(--font-mono)">100</text>

        {/* Needle */}
        <g
          style={{
            transformOrigin: `${centerX}px ${centerY}px`,
            transform: `rotate(${needleRotation}deg)`,
            transition: 'transform 1.5s cubic-bezier(0.4, 0, 0.2, 1)'
          }}
        >
          <line
            x1={centerX}
            y1={centerY}
            x2={centerX}
            y2={centerY - radius + 10}
            stroke={colors.primary}
            strokeWidth="3"
            strokeLinecap="round"
            filter="url(#glow)"
          />
          <circle
            cx={centerX}
            cy={centerY}
            r="8"
            fill={colors.primary}
            filter="url(#glow)"
          />
        </g>

        {/* Center display */}
        <g>
          {/* Score circle background */}
          <circle
            cx={centerX}
            cy={centerY + 15}
            r="35"
            fill="rgba(10, 10, 20, 0.8)"
            stroke="rgba(255,255,255,0.1)"
            strokeWidth="1"
          />

          {/* Score value */}
          <text
            x={centerX}
            y={centerY + 5}
            fill={colors.primary}
            fontSize="28"
            fontWeight="800"
            fontFamily="var(--font-display)"
            textAnchor="middle"
            filter="url(#glow)"
          >
            {displayScore}
          </text>

          {/* Percent sign */}
          <text
            x={centerX + 18}
            y={centerY - 5}
            fill="rgba(255,255,255,0.5)"
            fontSize="12"
            fontFamily="var(--font-mono)"
          >
            %
          </text>
        </g>
      </svg>

      {/* Verdict label below gauge */}
      <div
        className="risk-verdict"
        style={{
          color: colors.primary,
          textShadow: `0 0 20px ${colors.glow}`
        }}
      >
        {animatedVerdict.toUpperCase()}
      </div>
    </div>
  );
}

/**
 * Helper functions for arc drawing
 */
function polarToCartesian(centerX, centerY, radius, angleInDegrees) {
  const angleInRadians = (angleInDegrees - 90) * Math.PI / 180;
  return {
    x: centerX + radius * Math.cos(angleInRadians),
    y: centerY + radius * Math.sin(angleInRadians)
  };
}

function describeArc(x, y, radius, startAngle, endAngle, strokeWidth) {
  const start = polarToCartesian(x, y, radius, endAngle);
  const end = polarToCartesian(x, y, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? 0 : 1;

  return [
    'M', start.x, start.y,
    'A', radius, radius, 0, largeArcFlag, 0, end.x, end.y
  ].join(' ');
}
