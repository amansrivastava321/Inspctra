import { ArrowUpRight } from 'lucide-react';
import { P, F } from '../../design/tokens';
import type { DashboardDailyBucket, DashboardFailureReason, Provenance } from '../../types/api';
import { Card } from '../layout/AppShell';
import { ProvenanceBadge } from '../ProvenanceBadge';

interface FailureContextProps {
  reasons: DashboardFailureReason[];
  days: DashboardDailyBucket[];
  provenance?: Provenance | null;
  onNavigate: (path: string) => void;
}

function dayLabel(day: DashboardDailyBucket): string {
  if (day.total === 0) return `${day.date}: No runs`;
  const rate = day.pass_rate == null ? 'Unavailable' : `${day.pass_rate}% pass rate`;
  return `${day.date}: ${rate}, ${day.passed} passed, ${day.failed} failed`;
}

export function FailureContext({ reasons, days, provenance, onNavigate }: FailureContextProps) {
  return (
    <section aria-labelledby="dashboard-why-heading">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <h2 id="dashboard-why-heading" style={{ margin: 0, fontSize: 18, color: P.text }}>Why?</h2>
        <ProvenanceBadge provenance={provenance} source="Dashboard failure context" />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(300px, 0.9fr) minmax(420px, 1.35fr)', gap: 14 }}>
        <Card pad={0}>
          <div style={{ padding: '14px 16px', borderBottom: `1px solid ${P.border}` }}>
            <div style={{ fontFamily: F.mono, color: P.textMute, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Failure breakdown
            </div>
          </div>
          {reasons.map((reason, index) => (
            <div key={reason.category} style={{
              display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto auto', gap: 12,
              alignItems: 'center', padding: '13px 16px',
              borderBottom: index < reasons.length - 1 ? `1px solid ${P.border}` : undefined,
            }}>
              <div>
                <div style={{ color: P.text, fontSize: 13, fontWeight: 600 }}>{reason.category}</div>
                <ProvenanceBadge provenance={reason.provenance} source="Dashboard failure reason" style={{ marginTop: 5 }} />
              </div>
              <span style={{ color: P.textDim, fontFamily: F.mono, fontSize: 12 }}>
                {reason.count} {reason.count === 1 ? 'time' : 'times'}
              </span>
              <button
                type="button"
                onClick={() => onNavigate(`/runs?failure_category=${encodeURIComponent(reason.category)}`)}
                style={{ border: 0, background: 'transparent', color: P.accent, cursor: 'pointer', fontSize: 12, display: 'flex', gap: 4, alignItems: 'center' }}
              >View <ArrowUpRight size={11} /></button>
            </div>
          ))}
        </Card>

        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 18 }}>
            <div>
              <div style={{ fontFamily: F.mono, color: P.textMute, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Pass rate · last 7 days
              </div>
              <div style={{ marginTop: 5, color: P.textDim, fontSize: 12 }}>Persisted terminal runs only</div>
            </div>
          </div>
          <div style={{ height: 126, display: 'grid', gridTemplateColumns: `repeat(${Math.max(days.length, 1)}, 1fr)`, alignItems: 'end', gap: 10 }}>
            {days.map(day => {
              const classified = day.passed + day.failed;
              const passShare = classified ? day.passed / classified * 100 : 0;
              const failShare = classified ? day.failed / classified * 100 : 0;
              return (
                <div
                  key={day.date}
                  data-testid="pass-rate-day"
                  aria-label={dayLabel(day)}
                  style={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', alignItems: 'stretch', gap: 6 }}
                >
                  <div style={{
                    height: 92, borderRadius: 6, overflow: 'hidden', background: P.cardHi,
                    border: `1px solid ${P.border}`, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end',
                  }}>
                    {day.total === 0 ? (
                      <div style={{ height: '100%', background: P.cardHi }} />
                    ) : (
                      <>
                        {passShare > 0 && <div style={{ height: `${passShare}%`, background: P.pass }} />}
                        {failShare > 0 && <div style={{ height: `${failShare}%`, background: P.fail }} />}
                      </>
                    )}
                  </div>
                  <span style={{ fontSize: 10, color: P.textMute, textAlign: 'center', fontFamily: F.mono }}>
                    {new Date(`${day.date}T00:00:00Z`).toLocaleDateString([], { weekday: 'short' })}
                  </span>
                </div>
              );
            })}
          </div>
        </Card>
      </div>
    </section>
  );
}
