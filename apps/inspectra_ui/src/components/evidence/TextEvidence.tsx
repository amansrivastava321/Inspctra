import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { evidenceDownloadUrl } from '../../api/client';
import { F, P } from '../../design/tokens';
import type { EvidenceFile } from '../../types/api';

interface TextEvidenceProps {
  evidence: EvidenceFile;
  label: string;
}

export function TextEvidence({ evidence, label }: TextEvidenceProps) {
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (!next || content || loading) return;
    setLoading(true);
    setError('');
    try {
      const response = await fetch(evidenceDownloadUrl(evidence.id));
      if (!response.ok) throw new Error(`Artifact returned ${response.status}`);
      setContent(await response.text());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Artifact unavailable');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section style={{ borderTop: `1px solid ${P.border}`, paddingTop: 10 }}>
      <button type="button" onClick={toggle} aria-expanded={open} style={{ width: '100%', padding: 0, display: 'flex', alignItems: 'center', gap: 6, border: 0, background: 'transparent', color: P.textDim, cursor: 'pointer', textAlign: 'left' }}>
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        <span style={{ fontSize: 11, fontWeight: 600 }}>{label}</span>
      </button>
      {open && (
        <div style={{ marginTop: 8 }}>
          {loading && <div style={{ fontSize: 11, color: P.textMute }}>Loading artifact…</div>}
          {error && <div role="alert" style={{ fontSize: 11, color: P.fail }}>{error}</div>}
          {content && (
            <pre style={{ margin: 0, maxHeight: 320, overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word', padding: 12, borderRadius: 8, border: `1px solid ${P.border}`, background: P.bg, color: P.textDim, fontFamily: F.mono, fontSize: 10, lineHeight: 1.55 }}>
              {content}
            </pre>
          )}
        </div>
      )}
    </section>
  );
}
