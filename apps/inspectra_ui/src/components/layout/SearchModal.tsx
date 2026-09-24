/**
 * Global search modal — opened by ⌘K or clicking the topbar search button.
 * Queries apps, runs, packs, and reports from real API.
 * Keyboard: ArrowUp/Down to navigate, Enter to open, Escape to close.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { Search, X, Layers, Play, Package, FileText, type LucideIcon } from 'lucide-react';
import { P, F } from '../../design/tokens';
import type { StatusKind } from '../../design/tokens';
import { StatusBadge } from '../status/StatusBadge';
import { get } from '../../api/client';
import type { AppTarget, LiveRunRecord, ValidationPack, ReportRecord } from '../../types/api';
import { useWorkspaceMode, useWorkspaceNavigate } from '../../state/WorkspaceModeContext';
import type { DemoWorkspace } from '../../mocks/sampleData';

// ── Types ─────────────────────────────────────────────────────────────────────

type ResultGroup = 'Apps' | 'Runs' | 'Packs' | 'Reports';

interface SearchResult {
  id: string;
  group: ResultGroup;
  label: string;
  sub?: string;
  status?: string;
  path: string;
}

// ── Fetchers — called once on mount ──────────────────────────────────────────

function buildDemoResults(workspace: DemoWorkspace): SearchResult[] {
  return [
    ...workspace.apps.map(a => ({
      id: `app-${a.id}`, group: 'Apps' as const, label: a.name,
      sub: `${a.app_type} · ${a.platform ?? '—'}`, status: a.status, path: `/apps/${a.id}`,
    })),
    ...workspace.liveRuns.map(r => ({
      id: `run-${r.id}`, group: 'Runs' as const, label: r.app_name ?? r.pack_id ?? r.id,
      sub: r.pack_name ?? r.status, status: r.verdict ?? r.status, path: `/runs/${r.id}`,
    })),
    ...workspace.validationPacks.map(p => ({
      id: `pack-${p.id}`, group: 'Packs' as const, label: p.name,
      sub: `${p.total_flows} flows · ${p.schedule ?? 'manual'}`, status: p.readiness,
      path: `/packs/${p.id}`,
    })),
    ...workspace.reports.map(r => ({
      id: `rep-${r.id}`, group: 'Reports' as const, label: `${r.app_name} — ${r.pack_name}`,
      sub: r.verdict ?? '—', status: r.verdict, path: `/reports/${r.id}`,
    })),
  ];
}

async function fetchAll(): Promise<SearchResult[]> {
  const results: SearchResult[] = [];

  try {
    const apps = await get<AppTarget[]>('/apps');
    for (const a of apps) {
      results.push({
        id: `app-${a.id}`, group: 'Apps',
        label: a.name, sub: `${a.app_type} · ${a.platform ?? '—'}`,
        status: a.status, path: '/projects',
      });
    }
  } catch { /* offline — skip */ }

  try {
    const runs = await get<LiveRunRecord[]>('/runs');
    for (const r of runs) {
      results.push({
        id: `run-${r.id}`, group: 'Runs',
        label: r.app_name ?? r.pack_id ?? r.id,
        sub: r.pack_name ?? r.status,
        status: r.verdict ?? r.status,
        path: `/runs/${r.id}`,
      });
    }
  } catch { /* offline — skip */ }

  try {
    const packs = await get<ValidationPack[]>('/validation-packs');
    for (const p of packs) {
      results.push({
        id: `pack-${p.id}`, group: 'Packs',
        label: p.name,
        sub: `${p.total_flows} flows · ${p.schedule ?? 'manual'}`,
        status: p.readiness,
        path: '/packs',
      });
    }
  } catch { /* offline — skip */ }

  try {
    const reports = await get<ReportRecord[]>('/reports');
    for (const r of reports) {
      results.push({
        id: `rep-${r.id}`, group: 'Reports',
        label: `${r.app_name} — ${r.pack_name}`,
        sub: r.verdict ?? '—',
        status: r.verdict,
        path: `/reports/${r.id}`,
      });
    }
  } catch { /* offline — skip */ }

  return results;
}

const GROUP_ICONS: Record<ResultGroup, LucideIcon> = {
  Apps:    Layers,
  Runs:    Play,
  Packs:   Package,
  Reports: FileText,
};

const GROUP_ORDER: ResultGroup[] = ['Apps', 'Runs', 'Packs', 'Reports'];

// ── Component ─────────────────────────────────────────────────────────────────

interface SearchModalProps {
  onClose: () => void;
}

export function SearchModal({ onClose }: SearchModalProps) {
  const nav = useWorkspaceNavigate();
  const { isDemo, demoWorkspace } = useWorkspaceMode();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [allResults, setAllResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeIdx, setActiveIdx] = useState(0);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Load all data once
  useEffect(() => {
    setLoading(true);
    if (isDemo && demoWorkspace) {
      setAllResults(buildDemoResults(demoWorkspace));
      setLoading(false);
      return;
    }
    fetchAll().then(r => {
      setAllResults(r);
      setLoading(false);
    });
  }, [demoWorkspace, isDemo]);

  // Filter by query
  const filtered = query.trim().length === 0
    ? allResults
    : allResults.filter(r =>
        r.label.toLowerCase().includes(query.toLowerCase()) ||
        (r.sub ?? '').toLowerCase().includes(query.toLowerCase())
      );

  // Group results
  const grouped: Partial<Record<ResultGroup, SearchResult[]>> = {};
  for (const r of filtered) {
    if (!grouped[r.group]) grouped[r.group] = [];
    grouped[r.group]!.push(r);
  }

  // Flat list for keyboard navigation
  const flat: SearchResult[] = GROUP_ORDER.flatMap(g => grouped[g] ?? []);

  // Clamp activeIdx when results change
  useEffect(() => {
    setActiveIdx(i => Math.min(i, Math.max(flat.length - 1, 0)));
  }, [flat.length]);

  const navigate = useCallback((result: SearchResult) => {
    nav(result.path);
    onClose();
  }, [nav, onClose]);

  // Keyboard handling
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === 'Escape') { onClose(); return; }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIdx(i => Math.min(i + 1, flat.length - 1));
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIdx(i => Math.max(i - 1, 0));
      }
      if (e.key === 'Enter' && flat[activeIdx]) {
        navigate(flat[activeIdx]);
      }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [flat, activeIdx, navigate, onClose]);

  let flatCursor = 0;

  return (
    // Backdrop
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
        paddingTop: 80,
      }}
    >
      {/* Panel */}
      <div
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Search"
        style={{
          width: 560, maxHeight: '70vh',
          background: P.card, border: `1px solid ${P.border}`,
          borderRadius: 12, boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}
      >
        {/* Input row */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '12px 16px', borderBottom: `1px solid ${P.border}`,
        }}>
          <Search size={16} color={P.textMute} style={{ flexShrink: 0 }} />
          <input
            ref={inputRef}
            disabled={isDemo}
            title={isDemo ? 'Available in your real workspace. Leave demo to get started.' : undefined}
            value={query}
            onChange={e => { setQuery(e.target.value); setActiveIdx(0); }}
            placeholder="Search apps, runs, packs, reports…"
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              fontSize: 14, color: P.text, fontFamily: 'inherit',
            }}
          />
          {query && (
            <button onClick={() => setQuery('')} style={{
              background: 'transparent', border: 'none', cursor: 'pointer',
              padding: 2, color: P.textMute, display: 'flex',
            }}>
              <X size={14} />
            </button>
          )}
          <kbd style={{
            padding: '2px 6px', borderRadius: 4, fontSize: 10,
            background: P.cardHi, border: `1px solid ${P.border}`,
            color: P.textFaint, fontFamily: F.mono,
          }}>ESC</kbd>
        </div>

        {/* Results */}
        <div style={{ overflowY: 'auto', flex: 1 }}>
          {loading ? (
            <div style={{ padding: '20px 16px', fontSize: 13, color: P.textMute, textAlign: 'center' }}>
              Loading…
            </div>
          ) : flat.length === 0 ? (
            <div style={{ padding: '32px 16px', fontSize: 13, color: P.textMute, textAlign: 'center' }}>
              {query ? `No results for "${query}"` : 'No data available — backend may be offline'}
            </div>
          ) : (
            GROUP_ORDER.map(group => {
              const items = grouped[group];
              if (!items || items.length === 0) return null;
              const Icon = GROUP_ICONS[group];
              return (
                <div key={group}>
                  {/* Group header */}
                  <div style={{
                    padding: '8px 16px 4px',
                    display: 'flex', alignItems: 'center', gap: 6,
                  }}>
                    <Icon size={11} style={{ color: P.textFaint }} />
                    <span style={{ fontSize: 10, color: P.textFaint, fontFamily: F.mono,
                      textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                      {group}
                    </span>
                  </div>
                  {/* Items */}
                  {items.map(item => {
                    const idx = flatCursor++;
                    const active = idx === activeIdx;
                    return (
                      <button
                        key={item.id}
                        onClick={() => navigate(item)}
                        onMouseEnter={() => setActiveIdx(idx)}
                        style={{
                          width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                          padding: '8px 16px', textAlign: 'left', border: 'none',
                          background: active ? P.accentSoft : 'transparent',
                          cursor: 'pointer', transition: 'background 0.1s',
                        }}
                      >
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 13, fontWeight: 500,
                            color: active ? P.accent : P.text,
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {item.label}
                          </div>
                          {item.sub && (
                            <div style={{ fontSize: 11, color: P.textMute, marginTop: 1 }}>
                              {item.sub}
                            </div>
                          )}
                        </div>
                        {item.status && (
                          <StatusBadge kind={item.status as StatusKind} small />
                        )}
                      </button>
                    );
                  })}
                </div>
              );
            })
          )}
        </div>

        {/* Footer hint */}
        <div style={{
          padding: '6px 16px', borderTop: `1px solid ${P.border}`,
          display: 'flex', gap: 12, alignItems: 'center',
        }}>
          {[['↑↓', 'navigate'], ['↵', 'open'], ['esc', 'close']].map(([key, label]) => (
            <span key={key} style={{ fontSize: 11, color: P.textFaint, display: 'flex', gap: 4 }}>
              <kbd style={{ fontFamily: F.mono, fontSize: 10 }}>{key}</kbd>
              {label}
            </span>
          ))}
          {!loading && (
            <span style={{ marginLeft: 'auto', fontSize: 11, color: P.textFaint }}>
              {flat.length} result{flat.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
