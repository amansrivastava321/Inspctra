import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { EvidenceCard } from '../components/evidence/EvidenceCard';
import type { EvidenceFile } from '../types/api';

const MOCK_EV: EvidenceFile = {
  id: 'ev-001',
  run_id: 'run-001',
  evidence_type: 'screenshot',
  strength: 'strong',
  title: 'Screenshot diff',
  description: 'Before/after differ by 12.4%',
  content_preview: '<script>alert("xss")</script>',
  provenance: 'REAL_EXECUTION',
};

describe('EvidenceCard', () => {
  it('renders title safely', () => {
    render(<EvidenceCard ev={MOCK_EV} />);
    expect(screen.getByText('Screenshot diff')).toBeInTheDocument();
  });

  it('does not inject HTML from content_preview', () => {
    const { container } = render(<EvidenceCard ev={MOCK_EV} />);
    // script tag must not execute — no alert in DOM
    expect(container.querySelector('script')).toBeNull();
  });

  it('shows evidence type label', () => {
    render(<EvidenceCard ev={MOCK_EV} />);
    expect(screen.getByText('SCREENSHOT DIFF')).toBeInTheDocument();
  });

  it('shows the evidence provenance on the card', () => {
    render(<EvidenceCard ev={MOCK_EV} />);
    expect(screen.getByLabelText('Provenance: Real')).toBeInTheDocument();
  });
});
