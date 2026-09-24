import { useEffect } from 'react';
import type { CSSProperties } from 'react';
import { P } from '../design/tokens';
import type { Provenance } from '../types/api';

interface ProvenanceDisplay {
  label: string;
  tooltip: string;
  color: string;
  background: string;
}

const PROVENANCE_DISPLAY: Record<Provenance, ProvenanceDisplay> = {
  REAL_EXECUTION: {
    label: 'Real',
    tooltip: 'This result came from an actual execution.',
    color: '#10b981',
    background: 'rgba(16,185,129,0.12)',
  },
  DRY_RUN: {
    label: 'Dry Run',
    tooltip: 'This result was simulated without side effects.',
    color: '#f59e0b',
    background: 'rgba(245,158,11,0.12)',
  },
  MIXED: {
    label: 'Mixed',
    tooltip: 'Some steps ran for real, others were simulated.',
    color: '#f97316',
    background: 'rgba(249,115,22,0.12)',
  },
  SIMULATED: {
    label: 'Simulated',
    tooltip: 'This is simulated data.',
    color: '#3b82f6',
    background: 'rgba(59,130,246,0.12)',
  },
  DEMO_EXAMPLE: {
    label: 'Demo',
    tooltip: 'Sample data for exploration.',
    color: '#a855f7',
    background: 'rgba(168,85,247,0.12)',
  },
  UNAVAILABLE: {
    label: 'Unavailable',
    tooltip: 'This data could not be verified.',
    color: '#6b7280',
    background: 'rgba(107,114,128,0.12)',
  },
};

export interface ProvenanceBadgeProps {
  provenance?: Provenance | null;
  source: string;
  style?: CSSProperties;
}

export function ProvenanceBadge({ provenance, source, style }: ProvenanceBadgeProps) {
  const normalized = provenance && provenance in PROVENANCE_DISPLAY
    ? provenance
    : 'UNAVAILABLE';
  const display = PROVENANCE_DISPLAY[normalized];

  useEffect(() => {
    if (!provenance && import.meta.env.DEV) {
      console.warn(`Missing provenance for ${source}`);
    }
  }, [provenance, source]);

  return (
    <span
      data-testid="provenance-badge"
      data-provenance-source={source}
      title={display.tooltip}
      aria-label={`Provenance: ${display.label}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '2px 8px',
        borderRadius: 999,
        background: display.background,
        color: P.textDim,
        fontSize: 11,
        fontWeight: 500,
        lineHeight: '16px',
        whiteSpace: 'nowrap',
        flexShrink: 0,
        ...style,
      }}
    >
      <span
        data-testid="provenance-dot"
        aria-hidden="true"
        style={{
          display: 'inline-block',
          width: 6,
          height: 6,
          borderRadius: '50%',
          backgroundColor: display.color,
        }}
      />
      {display.label}
    </span>
  );
}
