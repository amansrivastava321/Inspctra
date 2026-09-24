/**
 * GlobalSearch — Cmd+K modal search across projects, apps, packs, runs, reports.
 *
 * Client-side search over data fetched from backend.
 * No secrets stored. No unsafe innerHTML. Input length capped.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, X, Folder, Monitor, Package, Play, FileText } from 'lucide-react';
import { P, F } from '../../design/tokens';
import { get } from '../../api/client';
import { useWorkspaceMode, useWorkspaceNavigate } from '../../state/WorkspaceModeContext';

interface SearchResult {
  id: string;
  label: string;
  sub?: string;
  path: string;
  icon: React.ReactNode;
  kind: string;
}

function normalize(s: string) { return s.toLowerCase().replace(/[-_]/g, ' '); }

function matchScore(query: string, label: string, sub = ''): number {
  const q = normalize(query);
  const l = normalize(label);
  const s = normalize(sub);
  if (l.startsWith(q)) return 3;
  if (l.includes(q)) return 2;
  if (s.includes(q)) return 1;
  return 0;
}

export function GlobalSearch({ open, onClose }: { open: boolean; onClose: () => void }) {
  const nav = useWorkspaceNavigate();
  const { isDemo, demoWorkspace } = useWorkspaceMode();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fetch and cache index on first open
  const indexRef = useRef<SearchResult[]>([]);
  const fetchedRef = useRef(false);

  const buildIndex = useCallback(async () => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    setLoading(true);
    try {
      if (isDemo && demoWorkspace) {
        indexRef.current = [
          ...demoWorkspace.projects.map(p => ({
            id: p.id, label: p.name, sub: p.description ?? 'project', path: '/projects',
            kind: 'Project', icon: <Folder size={13} />,
          })),
          ...demoWorkspace.apps.map(a => ({
            id: a.id, label: a.name, sub: a.app_type ?? 'app', path: `/apps/${a.id}`,
            kind: 'App', icon: <Monitor size={13} />,
          })),
          ...demoWorkspace.validationPacks.map(p => ({
            id: p.id, label: p.name, sub: 'validation pack', path: `/packs/${p.id}`,
            kind: 'Pack', icon: <Package size={13} />,
          })),
          ...demoWorkspace.liveRuns.map(r => ({
            id: r.id, label: r.id.slice(0, 12), sub: `${r.pack_name ?? '—'} · ${r.status}`,
            path: `/runs/${r.id}`, kind: 'Run', icon: <Play size={13} />,
          })),
          ...demoWorkspace.reports.map(rep => ({
            id: rep.id, label: rep.app_name ?? rep.id.slice(0, 12),
            sub: `${rep.pack_name ?? '—'} · ${rep.verdict ?? '—'}`,
            path: `/reports/${rep.id}`, kind: 'Report', icon: <FileText size={13} />,
          })),
        ];
        return;
      }

      const [projects, apps, packs, runs, reports] = await Promise.allSettled([
        get<Array<{id: string; name: string; description?: string}>>('/projects'),
        get<Array<{id: string; name: string; app_type?: string}>>('/apps'),
        get<Array<{id: string; name: string; description?: string}>>('/validation-packs'),
        get<Array<{id: string; status: string; pack_name?: string; app_name?: string}>>('/runs?limit=50'),
        get<Array<{id: string; name?: string; verdict?: string; app_name?: string}>>('/reports'),
      ]);

      const items: SearchResult[] = [];

      if (projects.status === 'fulfilled') {
        for (const p of projects.value ?? []) {
          items.push({
            id: p.id, label: p.name, sub: p.description ?? 'project',
            path: `/projects`, kind: 'Project',
            icon: <Folder size={13} />,
          });
        }
      }
      if (apps.status === 'fulfilled') {
        for (const a of apps.value ?? []) {
          items.push({
            id: a.id, label: a.name, sub: a.app_type ?? 'app',
            path: `/apps/${a.id}`, kind: 'App',
            icon: <Monitor size={13} />,
          });
        }
      }
      if (packs.status === 'fulfilled') {
        for (const p of packs.value ?? []) {
          items.push({
            id: p.id, label: p.name, sub: p.description ?? 'pack',
            path: `/packs/${p.id}`, kind: 'Pack',
            icon: <Package size={13} />,
          });
        }
      }
      if (runs.status === 'fulfilled') {
        for (const r of runs.value ?? []) {
          items.push({
            id: r.id, label: r.id.slice(0, 12),
            sub: `${r.pack_name ?? '—'} · ${r.status}`,
            path: `/runs/${r.id}`, kind: 'Run',
            icon: <Play size={13} />,
          });
        }
      }
      if (reports.status === 'fulfilled') {
        for (const rep of reports.value ?? []) {
          items.push({
            id: rep.id, label: rep.name ?? rep.id.slice(0, 12),
            sub: `${rep.app_name ?? '—'} · ${rep.verdict ?? '—'}`,
            path: `/reports/${rep.id}`, kind: 'Report',
            icon: <FileText size={13} />,
          });
        }
      }

      indexRef.current = items;
    } finally {
      setLoading(false);
    }
  }, [demoWorkspace, isDemo]);

  useEffect(() => {
    if (open) {
      buildIndex();
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery('');
      setResults([]);
      setSelected(0);
    }
  }, [open, buildIndex]);

  // Global Escape handler — closes overlay regardless of which element has focus.
  // handleKey only fires when input is focused; this covers backdrop clicks, Tab-away, etc.
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); onClose(); }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  useEffect(() => {
    if (!query.trim()) { setResults([]); return; }
    const q = query.slice(0, 200);
    const scored = indexRef.current
      .map(item => ({ item, score: matchScore(q, item.label, item.sub) }))
      .filter(x => x.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 12)
      .map(x => x.item);
    setResults(scored);
    setSelected(0);
  }, [query]);

  const go = useCallback((path: string) => {
    nav(path);
    onClose();
  }, [nav, onClose]);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { onClose(); return; }
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelected(s => Math.min(s + 1, results.length - 1)); }
    if (e.key === 'ArrowUp')   { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)); }
    if (e.key === 'Enter' && results[selected]) go(results[selected].path);
  };

  if (!open) return null;

  const empty = query.length > 0 && results.length === 0 && !loading;

  return (
    <div
      data-testid="global-search-overlay"
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0,0,0,0.6)', display: 'flex',
        alignItems: 'flex-start', justifyContent: 'center', paddingTop: 120,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: '100%', maxWidth: 560,
          background: P.card, borderRadius: 12,
          border: `1px solid ${P.border}`,
          boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
          overflow: 'hidden',
        }}
      >
        {/* Input row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px',
          borderBottom: `1px solid ${P.border}` }}>
          <Search size={15} style={{ color: P.textMute, flexShrink: 0 }} />
          <input
            ref={inputRef}
            data-testid="global-search-input"
            disabled={isDemo}
            title={isDemo ? 'Available in your real workspace. Leave demo to get started.' : undefined}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Search projects, apps, packs, runs, reports…"
            maxLength={200}
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              color: P.text, fontSize: 14, fontFamily: 'inherit',
            }}
          />
          {query && (
            <button onClick={() => setQuery('')} style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: P.textMute, padding: 2, display: 'flex',
            }}>
              <X size={13} />
            </button>
          )}
        </div>

        {/* Results */}
        {loading && (
          <div style={{ padding: '14px 16px', fontSize: 12, color: P.textMute }}>Loading index…</div>
        )}
        {empty && (
          <div style={{ padding: '14px 16px', fontSize: 12, color: P.textMute }}>
            No results for "{query.slice(0, 50)}"
          </div>
        )}
        {!query && !loading && (
          <div style={{ padding: '14px 16px', fontSize: 12, color: P.textFaint }}>
            Type to search across projects, apps, packs, runs, and reports.
          </div>
        )}
        {results.length > 0 && (
          <div style={{ maxHeight: 360, overflowY: 'auto' }}>
            {results.map((r, i) => (
              <div
                key={r.id}
                data-testid={`search-result-${r.kind.toLowerCase()}`}
                onClick={() => go(r.path)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 16px', cursor: 'pointer',
                  background: i === selected ? P.cardHi : 'transparent',
                  borderBottom: `1px solid ${P.border}`,
                  transition: 'background 0.1s',
                }}
                onMouseEnter={() => setSelected(i)}
              >
                <span style={{ color: P.textMute, flexShrink: 0 }}>{r.icon}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: P.text,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {r.label}
                  </div>
                  {r.sub && (
                    <div style={{ fontSize: 11, color: P.textMute,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {r.sub}
                    </div>
                  )}
                </div>
                <span style={{ fontSize: 10, color: P.textFaint, fontFamily: F.mono,
                  flexShrink: 0, letterSpacing: '0.05em' }}>{r.kind}</span>
              </div>
            ))}
          </div>
        )}

        {/* Footer */}
        <div style={{ padding: '8px 16px', borderTop: `1px solid ${P.border}`,
          display: 'flex', gap: 16, fontSize: 10, color: P.textFaint, fontFamily: F.mono }}>
          <span>↑↓ navigate</span>
          <span>↵ open</span>
          <span>Esc close</span>
        </div>
      </div>
    </div>
  );
}

/** Hook to mount global Cmd+K shortcut. Returns open state + closer. */
export function useGlobalSearch() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen(s => !s);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return { open, close: () => setOpen(false), toggle: () => setOpen(s => !s) };
}
