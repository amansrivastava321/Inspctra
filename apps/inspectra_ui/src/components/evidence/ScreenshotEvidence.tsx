import { useEffect, useState } from 'react';
import { AlertTriangle, Camera, X } from 'lucide-react';
import { evidenceDownloadUrl } from '../../api/client';
import { F, P } from '../../design/tokens';
import type { EvidenceFile, StepResult } from '../../types/api';
import { ProvenanceBadge } from '../ProvenanceBadge';

interface ScreenshotEvidenceProps {
  screenshots: EvidenceFile[];
  step: StepResult | null;
}

export function ScreenshotEvidence({ screenshots, step }: ScreenshotEvidenceProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [unavailableIds, setUnavailableIds] = useState<Set<string>>(() => new Set());
  const active = screenshots[Math.min(activeIndex, screenshots.length - 1)];

  useEffect(() => {
    if (!lightboxOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setLightboxOpen(false);
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [lightboxOpen]);

  if (!active) return null;
  const source = evidenceDownloadUrl(active.id);
  const alt = `Full-page evidence for step ${step?.index ?? 'run'}`;
  const unavailable = unavailableIds.has(active.id);
  const markUnavailable = (id: string) => {
    setUnavailableIds((current) => new Set(current).add(id));
    setLightboxOpen(false);
  };

  return (
    <section aria-label="Screenshot evidence" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, color: P.text }}>
          <Camera size={14} color={P.accent} />
          <span style={{ fontSize: 11, fontFamily: F.mono, textTransform: 'uppercase' }}>Screenshot evidence</span>
        </div>
        <ProvenanceBadge provenance={active.provenance} source="Screenshot evidence" />
      </div>
      {unavailable ? (
        <div role="alert" style={{ minHeight: 180, display: 'grid', placeItems: 'center', padding: 18, border: `1px solid ${P.borderHi}`, borderRadius: 10, background: P.bg, color: P.textMute, textAlign: 'center', fontSize: 12 }}>
          <div><AlertTriangle size={20} style={{ marginBottom: 8 }} />Screenshot artifact is unavailable. Other evidence is still shown.</div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setLightboxOpen(true)}
          title={`${step?.name ?? 'Run evidence'}${active.created_at ? ` · ${new Date(active.created_at).toLocaleString()}` : ''}`}
          style={{ padding: 0, border: `1px solid ${P.borderHi}`, borderRadius: 10, overflow: 'hidden', background: P.bg, cursor: 'zoom-in' }}
        >
          <img
            src={source}
            alt={alt}
            onError={() => markUnavailable(active.id)}
            style={{ display: 'block', width: '100%', maxHeight: '52vh', minHeight: 240, objectFit: 'contain', background: P.bg }}
          />
        </button>
      )}
      {screenshots.length > 1 && (
        <div aria-label="Screenshot choices" style={{ display: 'flex', gap: 7, overflowX: 'auto' }}>
          {screenshots.map((item, index) => (
            <button
              key={item.id}
              type="button"
              aria-label={`Show screenshot ${index + 1}`}
              onClick={() => setActiveIndex(index)}
              title={`${step?.name ?? 'Run evidence'}${item.created_at ? ` · ${new Date(item.created_at).toLocaleString()}` : ''}`}
              style={{ width: 72, height: 48, padding: 0, borderRadius: 6, overflow: 'hidden', cursor: 'pointer', background: P.bg, border: `1px solid ${index === activeIndex ? P.accent : P.border}` }}
            >
              {unavailableIds.has(item.id) ? (
                <AlertTriangle size={15} color={P.textMute} />
              ) : (
                <img src={evidenceDownloadUrl(item.id)} alt="" onError={() => markUnavailable(item.id)} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              )}
            </button>
          ))}
        </div>
      )}
      {lightboxOpen && !unavailable && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Screenshot evidence"
          onClick={() => setLightboxOpen(false)}
          style={{ position: 'fixed', inset: 0, zIndex: 1200, padding: 24, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.86)', backdropFilter: 'blur(5px)' }}
        >
          <div onClick={(event) => event.stopPropagation()} style={{ position: 'relative', maxWidth: '96vw', maxHeight: '94vh' }}>
            <button
              type="button"
              aria-label="Close screenshot"
              onClick={() => setLightboxOpen(false)}
              style={{ position: 'absolute', right: 8, top: 8, zIndex: 1, width: 32, height: 32, display: 'grid', placeItems: 'center', borderRadius: 16, border: `1px solid ${P.borderHi}`, background: P.surface, color: P.text, cursor: 'pointer' }}
            >
              <X size={16} />
            </button>
            <img src={source} alt={alt} onError={() => markUnavailable(active.id)} style={{ display: 'block', maxWidth: '96vw', maxHeight: '94vh', objectFit: 'contain', borderRadius: 10 }} />
          </div>
        </div>
      )}
    </section>
  );
}
