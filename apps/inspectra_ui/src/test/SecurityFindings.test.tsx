import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { EvidenceCard } from '../components/evidence/EvidenceCard';
import { SecurityFindingsCard } from '../pages/LiveRunDetailPage';
import type { EvidenceFile } from '../types/api';

const MOCK_SEC_EV: EvidenceFile = {
  id: 'ev-sec-01',
  run_id: 'run-sec-01',
  evidence_type: 'security_findings',
  strength: 'strong',
  title: 'Security Sweep Step 1',
  description: 'Passive security sweep completed.',
  metadata_json: {
    findings: [
      {
        id: 'missing-csp',
        title: 'Content Security Policy (CSP) Missing',
        severity: 'high',
        description: 'Content-Security-Policy header is missing. This exposes the app to Cross-Site Scripting (XSS).',
        recommendation: 'Implement a strong Content-Security-Policy header.',
        category: 'header',
      },
      {
        id: 'cookie-missing-secure-session',
        title: "Cookie Missing Secure Flag: 'session'",
        severity: 'medium',
        description: "The cookie 'session' is missing the Secure attribute.",
        recommendation: "Set the 'Secure' attribute.",
        category: 'cookie',
      }
    ]
  }
};

describe('Security Evidence and Findings Rendering', () => {
  it('renders security findings evidence type label in EvidenceCard', () => {
    render(<EvidenceCard ev={MOCK_SEC_EV} />);
    expect(screen.getByText('SECURITY FINDINGS')).toBeInTheDocument();
  });

  it('renders SecurityFindingsCard with correct counts and detail list', () => {
    const findings = (MOCK_SEC_EV.metadata_json as any).findings;
    render(<SecurityFindingsCard findings={findings} />);

    // Check title and passive-only sweep warning badge
    expect(screen.getByText('PASSIVE SECURITY SWEEP SUMMARY')).toBeInTheDocument();
    expect(screen.getByText('Passive check. No attack traffic sent.')).toBeInTheDocument();

    // Check total and critical/high counts
    expect(screen.getByText('TOTAL FINDINGS')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument(); // total findings
    expect(screen.getByText('CRITICAL / HIGH')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument(); // 1 critical/high

    // Check details rendering
    expect(screen.getByText('Content Security Policy (CSP) Missing')).toBeInTheDocument();
    expect(screen.getByText("Cookie Missing Secure Flag: 'session'")).toBeInTheDocument();
    expect(screen.getByText('Implement a strong Content-Security-Policy header.')).toBeInTheDocument();
    expect(screen.getByText('header')).toBeInTheDocument();
  });
});
