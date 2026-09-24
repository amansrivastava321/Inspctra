import { useState } from 'react';
import { ImageOff, Maximize2, X } from 'lucide-react';
import { evidenceDownloadUrl } from '../../api/client';
import { P } from '../../design/tokens';
import { ProvenanceBadge } from '../ProvenanceBadge';
import type { Provenance } from '../../types/api';

interface DashboardScreenshotProps {
  evidenceId?: string | null;
  provenance?: Provenance | null;
}

export function DashboardScreenshot({ evidenceId, provenance }: DashboardScreenshotProps) {
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(false);

  if (!evidenceId || failed) {
    return (
      <div style={{
        minHeight: 176, borderRadius: 10, border: `1px dashed ${P.border}`,
        background: P.bg, display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexDirection: 'column', gap: 8, color: P.textMute,
      }}>
        <ImageOff size={22} aria-hidden="true" />
        <span style={{ fontSize: 12 }}>
          {failed ? 'Screenshot unavailable' : 'No screenshot captured'}
        </span>
        <ProvenanceBadge
          provenance={provenance}
          source="Dashboard screenshot"
        />
      </div>
    );
  }

  const src = evidenceDownloadUrl(evidenceId);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Enlarge failure screenshot"
        style={{
          position: 'relative', display: 'block', width: '100%', padding: 0,
          borderRadius: 10, overflow: 'hidden', border: `1px solid ${P.border}`,
          background: P.bg, cursor: 'zoom-in', minHeight: 176,
        }}
      >
        <img
          src={src}
          alt="Failure screenshot"
          onError={() => setFailed(true)}
          style={{ width: '100%', height: 176, objectFit: 'cover', display: 'block' }}
        />
        <span style={{
          position: 'absolute', right: 8, top: 8, width: 28, height: 28,
          borderRadius: 7, background: 'rgba(8,9,11,0.8)', color: P.text,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}><Maximize2 size={14} aria-hidden="true" /></span>
        <span style={{ position: 'absolute', left: 8, bottom: 8 }}>
          <ProvenanceBadge provenance={provenance} source="Dashboard screenshot" />
        </span>
      </button>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Failure screenshot preview"
          onClick={() => setOpen(false)}
          style={{
            position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.88)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 36,
          }}
        >
          <button
            type="button"
            aria-label="Close screenshot preview"
            onClick={() => setOpen(false)}
            style={{
              position: 'absolute', right: 24, top: 24, width: 36, height: 36,
              borderRadius: 8, border: `1px solid ${P.border}`, background: P.card,
              color: P.text, display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer',
            }}
          ><X size={18} /></button>
          <img
            src={src}
            alt="Failure screenshot enlarged"
            onClick={event => event.stopPropagation()}
            onError={() => { setFailed(true); setOpen(false); }}
            style={{ maxWidth: '94vw', maxHeight: '88vh', objectFit: 'contain', borderRadius: 10 }}
          />
        </div>
      )}
    </>
  );
}
