import { Monitor, Smartphone } from 'lucide-react';
import { P, F } from '../../design/tokens';
import type { StepResult } from '../../types/api';

interface LiveAppFrameProps {
  screenshotUrl?: string;
  platform?: string;
  activeStep?: StepResult | null;
  isRunning?: boolean;
}

export function LiveAppFrame({ screenshotUrl, platform, activeStep, isRunning }: LiveAppFrameProps) {
  const isMobile = platform === 'ios' || platform === 'android';
  const Icon = isMobile ? Smartphone : Monitor;

  return (
    <div style={{
      flex: 1, background: P.card, border: `1px solid ${P.border}`,
      borderRadius: 10, display: 'flex', flexDirection: 'column',
      overflow: 'hidden', position: 'relative', minHeight: 320,
    }}>
      {/* Header bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 14px', borderBottom: `1px solid ${P.border}`,
        background: P.cardHi,
      }}>
        <Icon size={13} color={P.textMute} />
        <span style={{ fontSize: 11, color: P.textMute }}>
          {platform ?? 'App Screen'}
          {activeStep && ` · ${activeStep.name}`}
        </span>
        {isRunning && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 6, height: 6, borderRadius: 99, background: P.accent,
              animation: 'pulse 1s ease-in-out infinite' }} />
            <span style={{ fontSize: 10, color: P.accent, fontFamily: F.mono }}>LIVE</span>
          </div>
        )}
      </div>

      {/* Content */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        position: 'relative', background: P.bg }}>
        {screenshotUrl ? (
          // Safe: src from backend URL, no innerHTML
          <img
            src={screenshotUrl}
            alt="App screenshot"
            style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
          />
        ) : (
          <div style={{ textAlign: 'center' }}>
            <Icon size={40} color={P.textFaint} style={{ marginBottom: 12 }} />
            {isRunning ? (
              <>
                <div style={{ fontSize: 13, color: P.textDim, marginBottom: 4 }}>
                  {activeStep ? `Running: ${activeStep.name}` : 'Awaiting screenshot…'}
                </div>
                <div style={{ fontSize: 11, color: P.textMute }}>
                  Screenshots appear as each step executes
                </div>
              </>
            ) : (
              <>
                <div style={{ fontSize: 13, color: P.textDim, marginBottom: 4 }}>No screenshot</div>
                <div style={{ fontSize: 11, color: P.textMute }}>
                  Screenshots captured per step
                </div>
              </>
            )}
          </div>
        )}

        {/* Scanning overlay when running */}
        {isRunning && !screenshotUrl && (
          <div style={{
            position: 'absolute', inset: 0,
            background: `repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(91,140,255,0.02) 3px, rgba(91,140,255,0.02) 4px)`,
            pointerEvents: 'none',
          }} />
        )}
      </div>
    </div>
  );
}
