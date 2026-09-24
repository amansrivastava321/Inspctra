/**
 * LocalFolderBridge.tsx — Hybrid folder selection bridge.
 *
 * Replaces the browse/drop/hint inline section in AddAppPage for the local_folder tab.
 *
 * Flow:
 * 1. On mount: GET /api/local-environment/mode → detect mode, load tiered roots.
 * 2. Browse/drop → capture folder name (not path).
 * 3. "Where should Inspectra search?" — user selects approved roots.
 *    - Recommended roots (narrow project folders) are preselected.
 *    - Optional roots (Documents, Desktop) are shown collapsed, NOT preselected.
 *    - User can add a custom root (must be inside home directory per backend).
 * 4. POST /api/local-folder-search → get candidate paths.
 * 5. User picks candidate → onPathConfirmed(path) called.
 *
 * Security:
 * - Never claims an absolute path from the browser picker.
 * - Path only filled when user explicitly clicks "Use this folder".
 * - No Downloads shown. No full home directory offered.
 * - Does not call persistRecentFolder — AddAppPage handles that on scan success.
 */
import { useState, useEffect, useCallback } from 'react';
import { get, post } from '../../api/client';
import { P, F } from '../../design/tokens';

// ── Types ─────────────────────────────────────────────────────────────────────

interface EnvironmentMode {
  mode: 'local_web' | 'cloud';
  local_backend: boolean;
  native_picker_available: boolean;
  folder_search_available: boolean;
  allowed_roots: string[];          // backward-compat alias for recommended_roots
  recommended_roots?: string[];     // preselected in UI — narrow project folders
  optional_roots?: string[];        // shown collapsed, NOT preselected by default
}

interface FolderCandidate {
  path: string;
  label: string;
  matched_root: string;
  confidence: number;
  matched_fingerprints: string[];
  reason: string;
}

interface FolderSearchResponse {
  status: 'matched' | 'multiple_matches' | 'not_found' | 'too_broad' | 'unavailable';
  candidates: FolderCandidate[];
  message: string;
}

type BridgeState =
  | 'loading'
  | 'idle'
  | 'has_name'
  | 'searching'
  | 'candidates'
  | 'not_found'
  | 'cloud_disabled'
  | 'confirmed';

export interface LocalFolderBridgeProps {
  onPathConfirmed: (path: string) => void;
  currentPath: string;
}

// ── Tauri detection (read-only, no side effects) ──────────────────────────────
const _isTauri = () =>
  typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;

// ── Component ─────────────────────────────────────────────────────────────────

export default function LocalFolderBridge({
  onPathConfirmed,
  currentPath,
}: LocalFolderBridgeProps) {
  // recommended = preselected, optional = collapsed by default
  const [recommendedRoots, setRecommendedRoots] = useState<string[]>([]);
  const [optionalRoots, setOptionalRoots] = useState<string[]>([]);
  const [selectedRoots, setSelectedRoots] = useState<string[]>([]);
  const [customRoots, setCustomRoots] = useState<string[]>([]);
  const [customRootInput, setCustomRootInput] = useState('');
  const [showOptional, setShowOptional] = useState(false);
  const [bridgeState, setBridgeState] = useState<BridgeState>('loading');
  const [folderName, setFolderName] = useState('');
  const [fingerprints, setFingerprints] = useState<string[]>([]);
  const [candidates, setCandidates] = useState<FolderCandidate[]>([]);
  const [searchError, setSearchError] = useState('');
  const [dragOver, setDragOver] = useState(false);

  // ── Mount: fetch mode ──────────────────────────────────────────────────────
  useEffect(() => {
    get<EnvironmentMode>('/local-environment/mode')
      .then(mode => {
        if (mode.mode === 'cloud') {
          setBridgeState('cloud_disabled');
          return;
        }
        // Prefer recommended_roots; fall back to allowed_roots for older backend
        const recommended = mode.recommended_roots ?? mode.allowed_roots ?? [];
        const optional = mode.optional_roots ?? [];
        setRecommendedRoots(recommended);
        setOptionalRoots(optional);
        // Only preselect recommended roots (NOT optional — those are broad)
        setSelectedRoots(recommended);
        setBridgeState('idle');
      })
      .catch(() => {
        // Backend not reachable — fallback to idle (manual path entry still works)
        setBridgeState('idle');
      });
  }, []);

  // ── Sync confirmed state when currentPath cleared externally ──────────────
  useEffect(() => {
    if (!currentPath && bridgeState === 'confirmed') {
      setBridgeState('idle');
    }
  }, [currentPath, bridgeState]);

  // ── Browse ────────────────────────────────────────────────────────────────
  const handleBrowse = useCallback(async () => {
    setSearchError('');

    // 1. Try backend native picker (works when running as desktop app)
    try {
      const result = await post<{
        status: string; path?: string; label?: string; message?: string;
      }>('/local-picker/folder', {});

      if (result.status === 'selected' && result.path) {
        // Native picker gave us the real path — skip the bridge entirely
        onPathConfirmed(result.path);
        setBridgeState('confirmed');
        return;
      }
      if (result.status === 'cancelled') {
        return;
      }
      // status === 'unavailable' → fall through to folder-name capture
    } catch {
      // Backend unreachable → fall through to folder-name capture
    }

    // 2. Browser showDirectoryPicker — capture folder NAME only (not path)
    if (typeof window !== 'undefined' && 'showDirectoryPicker' in window) {
      try {
        // @ts-expect-error — File System Access API not in all TS lib versions
        const handle = await window.showDirectoryPicker({ mode: 'read' });
        const name: string = handle.name ?? '';
        if (name) {
          setFolderName(name);
          setFingerprints([]);
          setBridgeState('has_name');
        }
        return;
      } catch (e: unknown) {
        if (e instanceof Error && e.name === 'AbortError') return;
        // Permission denied or other error — fall through
      }
    }

    // 3. No picker available — stay idle, user can type folder name in search
    setBridgeState(prev => prev === 'loading' ? 'idle' : prev);
  }, [onPathConfirmed]);

  // ── Drop ──────────────────────────────────────────────────────────────────
  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    setSearchError('');
    const files = Array.from(e.dataTransfer.files ?? []);
    const items = Array.from(e.dataTransfer.items ?? []);
    const name = files[0]?.name ?? items[0]?.getAsFile()?.name ?? '';
    if (name) {
      setFolderName(name);
      // Collect sibling file names as fingerprint hints (up to 10)
      const fps = files.slice(1).map(f => f.name).filter(Boolean).slice(0, 10);
      setFingerprints(fps);
      setBridgeState('has_name');
    }
  }, []);

  // ── Root selection ────────────────────────────────────────────────────────
  const toggleRoot = (root: string) => {
    setSelectedRoots(prev =>
      prev.includes(root) ? prev.filter(r => r !== root) : [...prev, root]
    );
  };

  const addCustomRoot = () => {
    const trimmed = customRootInput.trim();
    if (!trimmed) return;
    setCustomRoots(prev => prev.includes(trimmed) ? prev : [...prev, trimmed]);
    setSelectedRoots(prev => prev.includes(trimmed) ? prev : [...prev, trimmed]);
    setCustomRootInput('');
  };

  const removeCustomRoot = (root: string) => {
    setCustomRoots(prev => prev.filter(r => r !== root));
    setSelectedRoots(prev => prev.filter(r => r !== root));
  };

  // ── Search ────────────────────────────────────────────────────────────────
  const handleSearch = useCallback(async () => {
    if (!folderName.trim() || selectedRoots.length === 0) return;
    setBridgeState('searching');
    setSearchError('');

    try {
      const result = await post<FolderSearchResponse>('/local-folder-search', {
        folder_name: folderName.trim(),
        fingerprints,
        approved_roots: selectedRoots,
        max_depth: 4,
        confirm_search: true,
      });

      if (result.status === 'too_broad') {
        setSearchError(
          result.message ||
          'Search took too long. Select a narrower project root or paste the full path manually.'
        );
        setBridgeState('has_name');
        return;
      }

      if (result.status === 'not_found' || result.candidates.length === 0) {
        setBridgeState('not_found');
      } else {
        setCandidates(result.candidates);
        setBridgeState('candidates');
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Search failed';
      // Replace generic timeout with helpful message
      if (msg.toLowerCase().includes('timeout') || msg.toLowerCase().includes('timed out')) {
        setSearchError(
          'Search took too long. Select a narrower project root or paste the full path manually.'
        );
      } else {
        setSearchError(msg);
      }
      setBridgeState('has_name');
    }
  }, [folderName, fingerprints, selectedRoots]);

  // ── Confirm ───────────────────────────────────────────────────────────────
  const handleUseCandidate = (candidate: FolderCandidate) => {
    onPathConfirmed(candidate.path);
    setBridgeState('confirmed');
  };

  // ── Reset ─────────────────────────────────────────────────────────────────
  const handleReset = () => {
    setFolderName('');
    setFingerprints([]);
    setCandidates([]);
    setSearchError('');
    setBridgeState('idle');
  };

  // ── Helpers ───────────────────────────────────────────────────────────────
  const shortLabel = (root: string) => root.replace(/.*[/\\]/, '') || root;

  // ── Render ─────────────────────────────────────────────────────────────────

  if (bridgeState === 'loading') {
    return (
      <div data-testid="bridge-loading"
        style={{ fontSize: 12, color: P.textMute, padding: 8 }}>
        Loading…
      </div>
    );
  }

  if (bridgeState === 'cloud_disabled') {
    return (
      <div
        data-testid="bridge-cloud-message"
        style={{
          padding: '16px', borderRadius: 10, marginBottom: 12,
          border: `1px solid ${P.border}`, background: P.cardHi,
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 600, color: P.unclear, marginBottom: 6 }}>
          ⚠ Local folder scanning requires the desktop app or local agent.
        </div>
        <div style={{ fontSize: 12, color: P.textDim, marginBottom: 8 }}>
          Use an alternative source instead:
        </div>
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: P.textDim }}>
          <li>GitHub URL</li>
          <li>Deployed Web URL</li>
          <li>API URL</li>
        </ul>
      </div>
    );
  }

  const isTauri = _isTauri();
  const modeBadgeLabel = isTauri ? 'desktop' : 'local';
  const showSearchSection =
    bridgeState === 'has_name' ||
    bridgeState === 'searching' ||
    bridgeState === 'candidates' ||
    bridgeState === 'not_found';

  // All roots shown in the checklist: recommended + (optional if expanded) + custom
  const visibleRoots = [
    ...recommendedRoots,
    ...(showOptional ? optionalRoots : []),
    ...customRoots,
  ];

  return (
    <div>
      {/* Mode badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span
          data-testid="bridge-mode-badge"
          style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '0.06em',
            textTransform: 'uppercase', fontFamily: F.mono,
            color: P.pass, background: P.passSoft,
            padding: '2px 7px', borderRadius: 5,
          }}
        >
          {modeBadgeLabel}
        </span>
        {isTauri && (
          <span
            data-testid="bridge-tauri-gap-message"
            style={{ fontSize: 11, color: P.textDim }}
          >
            Desktop detected. Native folder picker not yet wired — using local search bridge.
          </span>
        )}
      </div>

      {/* Browse + drop zone */}
      <div
        data-testid="bridge-drop-zone"
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        style={{
          marginBottom: 12, padding: '14px 16px', borderRadius: 10, textAlign: 'center',
          border: `2px dashed ${dragOver ? P.accent : P.border}`,
          background: dragOver ? P.accentSoft : P.cardHi,
          transition: 'border-color 0.15s, background 0.15s',
        }}
      >
        <div style={{ fontSize: 12, color: P.textDim, marginBottom: 8 }}>
          Browse or drop your app folder
        </div>
        <button
          data-testid="bridge-browse-btn"
          type="button"
          onClick={handleBrowse}
          style={{
            padding: '6px 14px', borderRadius: 7, fontSize: 12, fontWeight: 600,
            border: `1px solid ${P.accent}`, background: P.accentSoft,
            color: P.accent, cursor: 'pointer',
          }}
        >
          Browse folder
        </button>
      </div>

      {/* Captured folder name */}
      {folderName && bridgeState !== 'idle' && bridgeState !== 'confirmed' && (
        <div
          data-testid="bridge-folder-name"
          style={{
            marginBottom: 10, padding: '8px 12px', borderRadius: 8,
            background: P.cardHi, border: `1px solid ${P.border}`,
            fontSize: 12, color: P.text, display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          <span>📁 <strong>{folderName}</strong></span>
          <button
            type="button"
            onClick={handleReset}
            style={{
              marginLeft: 'auto', fontSize: 11, color: P.textMute, background: 'none',
              border: 'none', cursor: 'pointer', padding: '0 4px',
            }}
          >
            ✕ Clear
          </button>
        </div>
      )}

      {/* Confirmed path */}
      {bridgeState === 'confirmed' && currentPath && (
        <div
          data-testid="bridge-confirmed-msg"
          style={{
            marginBottom: 10, padding: '8px 12px', borderRadius: 8,
            background: P.passSoft, border: `1px solid ${P.pass}33`,
            fontSize: 12, color: P.pass,
          }}
        >
          ✓ Folder linked:{' '}
          <span style={{ fontFamily: F.mono }}>{currentPath}</span>
          <button
            type="button"
            onClick={handleReset}
            style={{
              marginLeft: 8, fontSize: 11, color: P.textMute, background: 'none',
              border: 'none', cursor: 'pointer', padding: '0 4px',
            }}
          >
            Change
          </button>
        </div>
      )}

      {/* Search section */}
      {showSearchSection && (
        <div
          data-testid="approved-roots-section"
          style={{
            marginBottom: 14, padding: '12px 14px', borderRadius: 10,
            border: `1px solid ${P.border}`, background: P.cardHi,
          }}
        >
          {/* Section heading */}
          <div style={{ fontSize: 12, fontWeight: 600, color: P.text, marginBottom: 3 }}>
            Where should Inspectra search?
          </div>
          <div
            data-testid="bridge-privacy-note"
            style={{ fontSize: 11, color: P.textDim, marginBottom: 10 }}
          >
            Inspectra searches only the folders you select. It never scans your whole computer.
          </div>

          {/* Recommended roots — preselected */}
          {recommendedRoots.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <div style={{
                fontSize: 10, color: P.textMute, fontFamily: F.mono,
                textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4,
              }}>
                Recommended project folders
              </div>
              {recommendedRoots.map((root, i) => (
                <label
                  key={root}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4,
                    cursor: 'pointer', fontSize: 12, color: P.textDim,
                  }}
                >
                  <input
                    data-testid={`approved-root-checkbox-${i}`}
                    type="checkbox"
                    checked={selectedRoots.includes(root)}
                    onChange={() => toggleRoot(root)}
                    style={{ accentColor: P.accent }}
                  />
                  <span style={{ fontFamily: F.mono, fontSize: 11 }}>{shortLabel(root)}</span>
                </label>
              ))}
            </div>
          )}

          {/* Optional roots — collapsed by default, NOT preselected */}
          {optionalRoots.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <button
                data-testid="bridge-show-optional-btn"
                type="button"
                onClick={() => setShowOptional(v => !v)}
                style={{
                  fontSize: 11, color: P.textMute, background: 'none', border: 'none',
                  cursor: 'pointer', padding: 0, textDecoration: 'underline',
                  display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4,
                }}
              >
                {showOptional ? '▾' : '▸'} Optional (broader folders)
              </button>
              {showOptional && optionalRoots.map((root, i) => (
                <label
                  key={root}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4,
                    cursor: 'pointer', fontSize: 12, color: P.textMute,
                  }}
                >
                  <input
                    data-testid={`optional-root-checkbox-${i}`}
                    type="checkbox"
                    checked={selectedRoots.includes(root)}
                    onChange={() => toggleRoot(root)}
                    style={{ accentColor: P.accent }}
                  />
                  <span style={{ fontFamily: F.mono, fontSize: 11 }}>{shortLabel(root)}</span>
                </label>
              ))}
            </div>
          )}

          {/* Custom roots */}
          {customRoots.map((root, i) => (
            <label
              key={root}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4,
                cursor: 'pointer', fontSize: 12, color: P.textDim,
              }}
            >
              <input
                data-testid={`approved-root-checkbox-${recommendedRoots.length + i}`}
                type="checkbox"
                checked={selectedRoots.includes(root)}
                onChange={() => toggleRoot(root)}
                style={{ accentColor: P.accent }}
              />
              <span style={{ fontFamily: F.mono, fontSize: 11 }}>{root}</span>
              <button
                type="button"
                onClick={() => removeCustomRoot(root)}
                style={{
                  marginLeft: 'auto', fontSize: 11, color: P.textMute,
                  background: 'none', border: 'none', cursor: 'pointer',
                }}
              >
                ✕
              </button>
            </label>
          ))}

          {/* Add custom root */}
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            <input
              data-testid="approved-root-add-input"
              type="text"
              value={customRootInput}
              onChange={e => setCustomRootInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addCustomRoot()}
              placeholder="~/Documents/Projects"
              style={{
                flex: 1, padding: '5px 8px', borderRadius: 6, fontSize: 11,
                background: P.bg, border: `1px solid ${P.border}`,
                color: P.text, fontFamily: F.mono, outline: 'none',
              }}
            />
            <button
              data-testid="approved-root-add-btn"
              type="button"
              onClick={addCustomRoot}
              style={{
                padding: '5px 10px', borderRadius: 6, fontSize: 11,
                border: `1px solid ${P.border}`, background: P.cardHi,
                color: P.textDim, cursor: 'pointer',
              }}
            >
              Add
            </button>
          </div>

          {/* No roots selected warning */}
          {selectedRoots.length === 0 && (
            <div
              data-testid="bridge-no-roots-warning"
              style={{ fontSize: 11, color: P.unclear, marginTop: 6 }}
            >
              Select at least one folder to search.
            </div>
          )}

          {/* Search button */}
          <button
            data-testid="bridge-search-btn"
            type="button"
            onClick={handleSearch}
            disabled={bridgeState === 'searching' || selectedRoots.length === 0}
            style={{
              marginTop: 10, width: '100%', padding: '7px 14px', borderRadius: 7,
              fontSize: 12, fontWeight: 600, cursor: 'pointer',
              border: `1px solid ${P.accent}`, background: P.accentSoft, color: P.accent,
            }}
          >
            {bridgeState === 'searching' ? '⏳ Searching…' : 'Find matching folder'}
          </button>

          {bridgeState === 'searching' && (
            <div
              data-testid="bridge-searching-indicator"
              style={{ marginTop: 6, fontSize: 11, color: P.textMute, textAlign: 'center' }}
            >
              Searching…
            </div>
          )}

          {searchError && (
            <div
              data-testid="bridge-search-error"
              style={{ marginTop: 6, fontSize: 11, color: P.fail }}
            >
              {searchError}
            </div>
          )}
        </div>
      )}

      {/* Not found */}
      {bridgeState === 'not_found' && (
        <div
          data-testid="bridge-not-found-msg"
          style={{
            marginBottom: 10, padding: '10px 12px', borderRadius: 8,
            background: P.unclearSoft, border: `1px solid ${P.unclear}33`,
            fontSize: 12, color: P.unclear,
          }}
        >
          No matching folder found. Add a narrower root or paste the path manually below.
        </div>
      )}

      {/* Candidates */}
      {bridgeState === 'candidates' && candidates.length > 0 && (
        <div data-testid="bridge-candidates-list" style={{ marginBottom: 12 }}>
          <div style={{
            fontSize: 11, color: P.textMute, marginBottom: 6, fontFamily: F.mono,
          }}>
            {candidates.length} match{candidates.length > 1 ? 'es' : ''} found
          </div>
          {candidates.map((c, i) => (
            <div
              key={c.path}
              data-testid={`bridge-candidate-${i}`}
              style={{
                marginBottom: 8, padding: '10px 12px', borderRadius: 8,
                border: `1px solid ${P.border}`, background: P.cardHi,
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600, color: P.text, marginBottom: 2 }}>
                {c.label}
              </div>
              <div style={{
                fontSize: 11, fontFamily: F.mono, color: P.textDim, marginBottom: 4,
              }}>
                {c.path}
              </div>
              {c.matched_fingerprints.length > 0 && (
                <div style={{ fontSize: 10, color: P.pass, marginBottom: 4 }}>
                  ✓ {c.matched_fingerprints.join(', ')}
                </div>
              )}
              <div style={{ fontSize: 10, color: P.textMute, marginBottom: 6 }}>
                Confidence: {Math.round(c.confidence * 100)}%
              </div>
              <button
                data-testid={`bridge-use-candidate-${i}`}
                type="button"
                onClick={() => handleUseCandidate(c)}
                style={{
                  padding: '5px 12px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                  border: `1px solid ${P.accent}`, background: P.accentSoft,
                  color: P.accent, cursor: 'pointer',
                }}
              >
                Use this folder
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
