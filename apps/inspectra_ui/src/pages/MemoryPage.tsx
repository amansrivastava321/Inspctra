import { useState, useCallback } from 'react';
import { RefreshCw, Search } from 'lucide-react';
import { P, F } from '../design/tokens';
import { AppShell, PageHeader, Card, Btn } from '../components/layout/AppShell';
import { LoadingSkeleton, EmptyState, OfflineState } from '../components/common/EmptyState';
import { useApi } from '../hooks/useApi';
import { get, post } from '../api/client';
import type { MemoryStats, MemoryPattern } from '../types/api';

// Backend wraps stats in {status, stats: {...}} — must unwrap
interface StatsWrapper { status: string; stats: MemoryStats; }

function getRawStats() { return get<StatsWrapper>('/memory/scopes/default/stats'); }
// Patterns endpoint returns a dict from service — adapt to array if needed
function getRawPatterns() { return get<unknown>('/memory/scopes/default/patterns'); }

function toPatternArray(raw: unknown): MemoryPattern[] {
  if (Array.isArray(raw)) return raw as MemoryPattern[];
  // Backend may return {patterns: [...]} or similar
  if (raw && typeof raw === 'object') {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj['patterns'])) return obj['patterns'] as MemoryPattern[];
  }
  return [];
}

export default function MemoryPage() {
  const statsFn = useCallback(getRawStats, []);
  const patternsFn = useCallback(getRawPatterns, []);

  const { data: statsRaw, loading, isOffline, refetch: refetchStats, isMock } =
    useApi(statsFn, { demo: workspace => ({ status: 'ok', stats: workspace.memory } as StatsWrapper) });
  const { data: patternsRaw } =
    useApi(patternsFn, { demo: [] as unknown });

  const stats: MemoryStats | null = isMock
    ? statsRaw?.stats ?? null
    : statsRaw?.stats ?? null;
  const patterns: MemoryPattern[] = toPatternArray(patternsRaw);

  const [query, setQuery] = useState('');
  const [recallResult, setRecallResult] = useState<string | null>(null);
  const [recalling, setRecalling] = useState(false);
  const [retentionRunning, setRetentionRunning] = useState(false);
  const [retentionResult, setRetentionResult] = useState('');

  const handleRetention = async () => {
    setRetentionRunning(true);
    setRetentionResult('');
    try {
      const res = await post<{ status: string; deleted?: number; kept?: number }>(
        '/memory/scopes/default/retention', { dry_run: true }
      );
      setRetentionResult(`Dry-run: ${res.deleted ?? 0} records would be pruned, ${res.kept ?? 0} kept.`);
    } catch {
      setRetentionResult('Retention check unavailable.');
    } finally {
      setRetentionRunning(false);
    }
  };

  const handleRecall = async () => {
    if (!query.trim()) return;
    setRecalling(true);
    try {
      const res = await post<{ results: Array<{ text: string; score: number }> }>(
        '/memory/scopes/default/recall', { query, top_k: 5 }
      );
      setRecallResult(res.results.map(r => `[${r.score.toFixed(2)}] ${r.text}`).join('\n\n'));
    } catch {
      setRecallResult('Backend offline — memory recall unavailable in demo mode.');
    } finally { setRecalling(false); }
  };

  return (
    <AppShell section="10" title="Memory">
      <PageHeader
        title="Memory"
        subtitle="Golden baseline · learned patterns · reasoning trajectories"
        actions={
          <Btn variant="ghost" size="sm" onClick={handleRetention} disabled={retentionRunning}>
            <RefreshCw size={12} />{retentionRunning ? 'Checking…' : 'Run retention'}
          </Btn>
        }
      />

      {retentionResult && (
        <div style={{ padding: '8px 12px', borderRadius: 7, marginBottom: 12,
          background: `${P.accent}18`, border: `1px solid ${P.accent}33`,
          fontSize: 12, color: P.textDim }}>{retentionResult}</div>
      )}
      {loading ? <LoadingSkeleton /> : isOffline ? <OfflineState onRetry={refetchStats} /> : (
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {/* Stats */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, flex: '0 0 320px' }}>
            {[
              { label: 'Fingerprints', value: stats?.fingerprint_count ?? 0 },
              { label: 'Patterns', value: stats?.pattern_count ?? 0 },
              { label: 'Trajectories', value: stats?.trajectory_count ?? 0 },
              { label: 'Embeddings', value: stats?.embedding_count ?? 0 },
            ].map(({ label, value }) => (
              <Card key={label}>
                <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                  textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>{label}</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: P.text }}>{value}</div>
              </Card>
            ))}
          </div>

          <div style={{ flex: 1, minWidth: 280, display: 'flex', flexDirection: 'column', gap: 12 }}>
            {/* Semantic recall */}
            <Card>
              <div style={{ fontSize: 12, fontWeight: 600, color: P.text, marginBottom: 10 }}>
                Semantic Recall
              </div>
              <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                <input
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleRecall()}
                  placeholder="What caused the export PDF failure?"
                  maxLength={500}
                  style={{
                    flex: 1, padding: '7px 10px', borderRadius: 7,
                    background: P.bg, border: `1px solid ${P.border}`,
                    color: P.text, fontSize: 12, outline: 'none',
                  }}
                />
                <Btn variant="primary" onClick={handleRecall} disabled={recalling || !query.trim()}>
                  <Search size={12} />{recalling ? '…' : 'Recall'}
                </Btn>
              </div>
              {recallResult && (
                <div style={{ padding: '10px 12px', borderRadius: 7, background: P.cardHi,
                  border: `1px solid ${P.border}`, fontFamily: F.mono, fontSize: 11,
                  color: P.textDim, whiteSpace: 'pre-wrap', lineHeight: 1.6, maxHeight: 200, overflowY: 'auto' }}>
                  {recallResult}
                </div>
              )}
            </Card>

            {/* Patterns */}
            <Card pad={0}>
              <div style={{ padding: '12px 14px', borderBottom: `1px solid ${P.border}` }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: P.text }}>Learned Patterns</div>
              </div>
              {!patterns?.length ? (
                <EmptyState title="No patterns yet" description="Patterns are learned after multiple runs." />
              ) : (
                (patterns ?? []).slice(0, 8).map((p, i) => (
                  <div key={p.id} style={{ padding: '9px 14px',
                    borderBottom: i < Math.min(7, (patterns?.length ?? 0) - 1) ? `1px solid ${P.border}` : 'none',
                    display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, color: P.text,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {p.canonical_template}
                      </div>
                      {p.pattern_type && (
                        <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono }}>{p.pattern_type}</div>
                      )}
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <div style={{ fontSize: 11, color: P.textMute }}>×{p.frequency}</div>
                      <div style={{ fontSize: 10, color: P.textFaint, fontFamily: F.mono }}>
                        {(p.confidence * 100).toFixed(0)}%
                      </div>
                    </div>
                  </div>
                ))
              )}
            </Card>
          </div>
        </div>
      )}
    </AppShell>
  );
}
