import React from 'react';
import { Camera, Check, Eye, AlertTriangle, Loader2 } from 'lucide-react';
import { P, F } from '../../design/tokens';

interface VisualRegressionCardProps {
  baselineUrl?: string;
  currentUrl?: string;
  diffUrl?: string;
  diffRatio?: number;
  threshold?: number;
  onApprove: () => void;
  isApproving: boolean;
  isApproved: boolean;
}

export function VisualRegressionCard({
  baselineUrl,
  currentUrl,
  diffUrl,
  diffRatio,
  threshold,
  onApprove,
  isApproving,
  isApproved,
}: VisualRegressionCardProps) {
  const isMismatch = diffRatio !== undefined && threshold !== undefined && diffRatio > threshold;
  
  return (
    <div style={{
      background: P.card, border: `1px solid ${isMismatch ? P.fail : P.border}`,
      borderRadius: 10, display: 'flex', flexDirection: 'column',
      overflow: 'hidden', position: 'relative', minHeight: 360,
      boxShadow: P.shadowCard,
    }}>
      {/* Header bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '10px 14px', borderBottom: `1px solid ${P.border}`,
        background: P.cardHi,
      }}>
        <Camera size={14} color={isMismatch ? P.fail : P.accent} />
        <span style={{ fontSize: 12, fontWeight: 600, color: P.text }}>
          Visual Comparison
        </span>

        {diffRatio !== undefined && threshold !== undefined && (
          <span style={{
            fontSize: 10, fontFamily: F.mono, fontWeight: 600,
            background: isMismatch ? P.failSoft : P.passSoft,
            border: `1px solid ${isMismatch ? P.fail : P.pass}33`,
            color: isMismatch ? P.fail : P.pass,
            borderRadius: 4, padding: '2px 6px', marginLeft: 8,
          }}>
            Diff: {(diffRatio * 100).toFixed(2)}% (Max: {(threshold * 100).toFixed(2)}%)
          </span>
        )}

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button
            onClick={onApprove}
            disabled={isApproving || isApproved}
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              fontSize: 11, fontWeight: 600, fontFamily: F.ui,
              background: isApproved 
                ? `${P.pass}18` 
                : isApproving 
                  ? P.cardHi 
                  : `linear-gradient(135deg, ${P.accent}, #4f46e5)`,
              border: `1px solid ${isApproved ? P.pass : isApproving ? P.border : '#4f46e5'}`,
              borderRadius: 6, padding: '4px 10px',
              color: isApproved ? P.pass : '#ffffff',
              cursor: (isApproving || isApproved) ? 'default' : 'pointer',
              transition: 'opacity 0.1s',
            }}
            onMouseEnter={e => { if (!isApproving && !isApproved) e.currentTarget.style.opacity = '0.9'; }}
            onMouseLeave={e => { if (!isApproving && !isApproved) e.currentTarget.style.opacity = '1'; }}
          >
            {isApproving ? (
              <Loader2 size={12} className="animate-spin" style={{ animation: 'spin 1s linear infinite' }} />
            ) : isApproved ? (
              <Check size={12} />
            ) : (
              <Eye size={12} />
            )}
            {isApproving ? 'Approving...' : isApproved ? 'Baseline Approved' : 'Approve Baseline'}
          </button>
        </div>
      </div>

      {/* Main layout: 3 Columns side-by-side */}
      <div style={{ flex: 1, padding: 16, display: 'flex', gap: 16, overflowX: 'auto', background: P.bg }}>
        {/* Baseline Column */}
        <div style={{ flex: 1, minWidth: 200, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono, letterSpacing: '0.04em' }}>
            BASELINE IMAGE
          </div>
          <div style={{
            flex: 1, border: `1px solid ${P.border}`, borderRadius: 6,
            background: P.cardHi, display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 8, minHeight: 220, position: 'relative', overflow: 'hidden'
          }}>
            {baselineUrl ? (
              <img src={baselineUrl} alt="Baseline" style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
            ) : (
              <div style={{ textAlign: 'center', padding: 12 }}>
                <Camera size={24} color={P.textFaint} style={{ marginBottom: 8 }} />
                <div style={{ fontSize: 11, color: P.textMute }}>No baseline found</div>
                <div style={{ fontSize: 9, color: P.textFaint, marginTop: 4 }}>This screenshot will initialize it</div>
              </div>
            )}
          </div>
        </div>

        {/* Current Column */}
        <div style={{ flex: 1, minWidth: 200, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono, letterSpacing: '0.04em' }}>
            CURRENT SCREENSHOT
          </div>
          <div style={{
            flex: 1, border: `1px solid ${P.border}`, borderRadius: 6,
            background: P.cardHi, display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 8, minHeight: 220, position: 'relative', overflow: 'hidden'
          }}>
            {currentUrl ? (
              <img src={currentUrl} alt="Current" style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
            ) : (
              <div style={{ fontSize: 11, color: P.textMute }}>No current screenshot</div>
            )}
          </div>
        </div>

        {/* Diff Column (only if diff exists) */}
        {diffUrl && (
          <div style={{ flex: 1, minWidth: 200, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono, letterSpacing: '0.04em' }}>
              VISUAL DIFFERENCE
            </div>
            <div style={{
              flex: 1, border: `1px solid ${isMismatch ? P.fail : P.border}33`, borderRadius: 6,
              background: P.cardHi, display: 'flex', alignItems: 'center', justifyContent: 'center',
              padding: 8, minHeight: 220, position: 'relative', overflow: 'hidden'
            }}>
              <img src={diffUrl} alt="Visual Diff" style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
            </div>
          </div>
        )}
      </div>

      {/* Warning Banner if Mismatch */}
      {isMismatch && (
        <div style={{
          background: `${P.fail}10`, borderTop: `1px solid ${P.fail}33`,
          padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 8,
          fontSize: 11, color: P.fail
        }}>
          <AlertTriangle size={14} />
          <span>Visual mismatch detected! Difference ratio exceeds the specified threshold. Approve the baseline if this change is intentional.</span>
        </div>
      )}
    </div>
  );
}
