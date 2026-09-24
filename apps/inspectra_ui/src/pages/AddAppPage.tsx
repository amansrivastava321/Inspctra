import { useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Check, Trash2 } from 'lucide-react';
import { P, F } from '../design/tokens';
import { AppShell, Card, Btn } from '../components/layout/AppShell';
import { LoadingSkeleton, OfflineState } from '../components/common/EmptyState';
import { useApi } from '../hooks/useApi';
import { get, post, del } from '../api/client';
import type {
  Project, AppTarget, DiscoveryResult, SourceType, AppMapDraft,
} from '../types/api';
import LocalFolderBridge from '../components/local/LocalFolderBridge';
import { useWorkspaceNavigate } from '../state/WorkspaceModeContext';
import { PreviewBadge } from '../components/PreviewBadge';
import { isPreviewAppType, PREVIEW_TOOLTIP } from '../config/capabilities';

// ── Recent source folders (localStorage) ─────────────────────────────────────

const RECENT_FOLDERS_KEY = 'inspectra.recentSourceFolders';
const RECENT_FOLDERS_MAX = 10;

interface RecentFolder {
  path: string;
  label: string;       // last segment of path, for display
  last_used_at: string; // ISO date
}

function loadRecentFolders(): RecentFolder[] {
  try {
    const raw = localStorage.getItem(RECENT_FOLDERS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (f: unknown): f is RecentFolder =>
        !!f && typeof f === 'object' &&
        typeof (f as RecentFolder).path === 'string' &&
        (f as RecentFolder).path.trim() !== '',
    );
  } catch {
    return [];
  }
}

function persistRecentFolder(path: string): RecentFolder[] {
  const label = path.split(/[\\/]/).filter(Boolean).pop() ?? path;
  const item: RecentFolder = { path, label, last_used_at: new Date().toISOString() };
  // Deduplicate by path, move to top, cap at max
  const existing = loadRecentFolders().filter(f => f.path !== path);
  const updated = [item, ...existing].slice(0, RECENT_FOLDERS_MAX);
  try { localStorage.setItem(RECENT_FOLDERS_KEY, JSON.stringify(updated)); } catch { /* full */ }
  return updated;
}

function eraseRecentFolder(path: string): RecentFolder[] {
  const updated = loadRecentFolders().filter(f => f.path !== path);
  try { localStorage.setItem(RECENT_FOLDERS_KEY, JSON.stringify(updated)); } catch { /* ignore */ }
  return updated;
}

// 4-step wizard
const STEPS = ['Select project', 'Source', 'Review & confirm', 'Done'];

const APP_TYPES = [
  { id: 'web',     label: 'Web',           sub: 'Browser-based app',    icon: '🌐' },
  { id: 'desktop', label: 'Desktop',       sub: 'macOS, Windows, Linux', icon: '💻' },
  { id: 'mobile',  label: 'Mobile',        sub: 'iOS or Android app',   icon: '📱' },
  { id: 'api',     label: 'API / Service', sub: 'REST, GraphQL, gRPC',  icon: '🔌' },
];

const SOURCE_TABS: { id: SourceType; label: string; testId: string }[] = [
  { id: 'manual',       label: 'Manual',        testId: 'source-tab-manual' },
  { id: 'local_folder', label: 'Local folder',  testId: 'source-tab-local' },
  { id: 'web_url',      label: 'Web URL',        testId: 'source-tab-web' },
  { id: 'api_base_url', label: 'API URL',        testId: 'source-tab-api' },
  { id: 'github_url',   label: 'GitHub',         testId: 'source-tab-github' },
];

function getProjects() { return get<Project[]>('/projects'); }

/** Minimal field input */
function Field({ label, value, onChange, note, mono, required, placeholder, helpText }:
  { label: string; value: string; onChange: (v: string) => void;
    note?: string; mono?: boolean; required?: boolean; placeholder?: string; helpText?: string }) {
  return (
    <div>
      <label style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
        letterSpacing: '0.06em', textTransform: 'uppercase', display: 'block', marginBottom: 4 }}>
        {label}{required && <span style={{ color: P.fail }}> *</span>}
      </label>
      <input
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          width: '100%', padding: '7px 10px', borderRadius: 7, boxSizing: 'border-box',
          background: P.bg, border: `1px solid ${P.border}`,
          color: P.text, fontSize: 12,
          fontFamily: mono ? F.mono : 'inherit', outline: 'none',
        }}
      />
      {note && <div style={{ fontSize: 10, color: P.textFaint, marginTop: 3 }}>{note}</div>}
      {helpText && <div style={{ fontSize: 10, color: P.textFaint, marginTop: 3 }}>{helpText}</div>}
    </div>
  );
}

/** Confidence badge */
function ConfBadge({ conf }: { conf: string }) {
  const color = conf === 'high' ? P.pass : conf === 'medium' ? P.unclear : P.textMute;
  return (
    <span style={{
      fontSize: 9, fontFamily: F.mono, color, border: `1px solid ${color}33`,
      borderRadius: 4, padding: '1px 5px', marginLeft: 6, textTransform: 'uppercase', letterSpacing: '0.04em',
    }}>
      {conf}
    </span>
  );
}

/** Step indicator strip */
function StepStrip({ step, total }: { step: number; total: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginBottom: 24 }}>
      {STEPS.map((s, i) => {
        const n = i + 1;
        const done = step > n;
        const active = step === n;
        return (
          <div key={s} style={{ display: 'flex', alignItems: 'center', flex: i < total - 1 ? 1 : 0 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
              <div style={{
                width: 28, height: 28, borderRadius: 99,
                border: `2px solid ${done || active ? P.accent : P.border}`,
                background: done ? P.accent : active ? P.accentSoft : P.card,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 12, fontWeight: 700,
                color: done ? '#fff' : active ? P.accent : P.textMute,
              }}>
                {done ? <Check size={12} /> : n}
              </div>
              <span style={{ fontSize: 10, color: active ? P.accent : P.textMute,
                fontFamily: F.mono, textTransform: 'uppercase', textAlign: 'center',
                whiteSpace: 'nowrap' }}>
                STEP {n}<br />{s}
              </span>
            </div>
            {i < total - 1 && (
              <div style={{
                flex: 1, height: 1,
                background: done ? P.accent : P.border,
                margin: '0 8px', marginBottom: 24,
              }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

const SOURCE_TYPES: SourceType[] = ['manual', 'local_folder', 'web_url', 'api_base_url', 'github_url'];

export default function AddAppPage() {
  const nav = useWorkspaceNavigate();
  const [searchParams] = useSearchParams();
  const [step, setStep] = useState(1);

  // ── Step 1: Project ───────────────────────────────────────────────────────────
  const { data: projects, loading: loadingProjects, refetch: refetchProjects, isOffline } =
    useApi(useCallback(getProjects, []), { demo: workspace => workspace.projects });
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [newProjectName, setNewProjectName] = useState('');
  const [creatingProject, setCreatingProject] = useState(false);
  const [createProjectError, setCreateProjectError] = useState('');
  const [showTestProjects, setShowTestProjects] = useState(false);
  const [projectSearch, setProjectSearch] = useState('');
  const [deletingProjectId, setDeletingProjectId] = useState<string | null>(null);

  // ── Step 2: Source ────────────────────────────────────────────────────────────
  const sourceFromUrl = searchParams.get('source') as SourceType | null;
  const [sourceTab, setSourceTab] = useState<SourceType>(
    sourceFromUrl && SOURCE_TYPES.includes(sourceFromUrl) ? sourceFromUrl : 'manual',
  );
  const [localPath, setLocalPath] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState('');
  const [discoveryResult, setDiscoveryResult] = useState<DiscoveryResult | null>(null);
  // Local folder UX
  const [permissionChecked, setPermissionChecked] = useState(false);
  const [recentFolders, setRecentFolders] = useState<RecentFolder[]>(() => loadRecentFolders());

  // ── Step 3: Confirm ───────────────────────────────────────────────────────────
  const [appType, setAppType] = useState('');
  const [form, setForm] = useState({
    name: '', base_url: '', launch_command: '', description: '',
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [savedApp, setSavedApp] = useState<AppTarget | null>(null);
  const [dupWarning, setDupWarning] = useState('');

  // ── Step 4: Next actions ──────────────────────────────────────────────────────
  const [generatingMap, setGeneratingMap] = useState(false);
  const [appMap, setAppMap] = useState<AppMapDraft | null>(null);
  const [appMapError, setAppMapError] = useState('');

  // ── Helpers ───────────────────────────────────────────────────────────────────

  const isTestProject = (name: string) => /^E2E-/i.test(name);

  const visibleProjects = (projects ?? []).filter(p => {
    const matchSearch = !projectSearch || p.name.toLowerCase().includes(projectSearch.toLowerCase());
    const matchFilter = showTestProjects || !isTestProject(p.name);
    return matchSearch && matchFilter;
  });

  const testProjectCount = (projects ?? []).filter(p => isTestProject(p.name)).length;
  const normalProjectCount = (projects ?? []).filter(p => !isTestProject(p.name)).length;

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) return;
    setCreatingProject(true);
    setCreateProjectError('');
    try {
      const proj = await post<Project>('/projects', { name: newProjectName.trim() });
      await refetchProjects();
      setSelectedProjectId(proj.id);
      setNewProjectName('');
      window.dispatchEvent(new CustomEvent('inspectra:projects-updated'));
    } catch (err) {
      setCreateProjectError(String(err instanceof Error ? err.message : err));
    } finally {
      setCreatingProject(false);
    }
  };

  const handleDeleteProject = async (proj: Project) => {
    if (!window.confirm(`Delete project "${proj.name}"? This cannot be undone.`)) return;
    setDeletingProjectId(proj.id);
    try {
      await del(`/projects/${proj.id}`);
      if (selectedProjectId === proj.id) setSelectedProjectId('');
      await refetchProjects();
      window.dispatchEvent(new CustomEvent('inspectra:projects-updated'));
    } catch (err) {
      window.alert(`Delete failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setDeletingProjectId(null);
    }
  };

  // Step 2 → Step 3: run scan or skip (manual)
  const handleScanOrSkip = async () => {
    setScanError('');
    if (sourceTab === 'manual') {
      setDiscoveryResult(null);
      setStep(3);
      return;
    }
    if (sourceTab === 'github_url') {
      // Scan to get the unsupported message, then still proceed to manual form
      setScanning(true);
      try {
        const result = await post<DiscoveryResult>('/discovery/scan', {
          project_id: selectedProjectId,
          source_type: sourceTab,
          url: sourceUrl,
        });
        setDiscoveryResult(result);
        setStep(3);
      } catch (err) {
        setScanError(String(err instanceof Error ? err.message : err));
      } finally {
        setScanning(false);
      }
      return;
    }
    setScanning(true);
    try {
      const payload: Record<string, unknown> = {
        project_id: selectedProjectId,
        source_type: sourceTab,
      };
      if (sourceTab === 'local_folder') {
        if (!localPath.trim()) { setScanError('Enter a folder path.'); setScanning(false); return; }
        if (!permissionChecked) { setScanError('Check the permission checkbox before scanning.'); setScanning(false); return; }
        payload.local_path = localPath.trim();
        payload.permission_to_scan = true;
      } else {
        if (!sourceUrl.trim()) { setScanError('Enter a URL.'); setScanning(false); return; }
        payload.url = sourceUrl.trim();
      }
      const result = await post<DiscoveryResult>('/discovery/scan', payload);
      setDiscoveryResult(result);
      // Pre-fill form from detected values
      if (result.suggested_name) {
        setForm(f => ({ ...f, name: f.name || result.suggested_name!.value }));
      }
      if (result.suggested_base_url) {
        setForm(f => ({ ...f, base_url: f.base_url || result.suggested_base_url!.value }));
      }
      if (result.suggested_launch_command) {
        setForm(f => ({ ...f, launch_command: f.launch_command || result.suggested_launch_command!.command }));
      }
      if (result.suggested_app_type) {
        if (!appType && !isPreviewAppType(result.suggested_app_type.value)) {
          setAppType(result.suggested_app_type.value);
        }
      }
      // Save successful local folder path to recent folders
      if (sourceTab === 'local_folder' && result.status === 'complete') {
        setRecentFolders(persistRecentFolder(localPath.trim()));
      }
      setStep(3);
    } catch (err) {
      setScanError(String(err instanceof Error ? err.message : err));
      // Do NOT save on failure
    } finally {
      setScanning(false);
    }
  };

  // Step 3: Save app
  const doPost = async () => {
    setSaving(true);
    setSaveError('');
    try {
      let app: AppTarget;
      if (discoveryResult?.id && discoveryResult.status !== 'unsupported') {
        // Create via discovery endpoint (records source info)
        const payload: Record<string, unknown> = {
          discovery_id: discoveryResult.id,
          name: form.name.trim(),
          app_type: appType,
          description: form.description.trim(),
        };
        if (form.base_url.trim()) payload.base_url = form.base_url.trim();
        if (form.launch_command.trim()) payload.launch_command = form.launch_command.trim();
        app = await post<AppTarget>(`/discovery/${discoveryResult.id}/create-app`, payload);
      } else {
        // Manual path — direct /apps POST
        const payload: Record<string, unknown> = {
          project_id: selectedProjectId,
          name: form.name.trim(),
          app_type: appType,
          description: form.description.trim(),
        };
        if (form.base_url.trim()) payload.base_url = form.base_url.trim();
        app = await post<AppTarget>('/apps', payload);
      }
      setSavedApp(app);
      setStep(4);
    } catch (err) {
      setSaveError(String(err instanceof Error ? err.message : err));
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    if (!selectedProjectId || !form.name.trim() || !appType) return;
    setDupWarning('');
    try {
      const existing = await get<AppTarget[]>(`/apps?project_id=${selectedProjectId}`);
      const dup = (existing ?? []).find(a =>
        a.name.trim().toLowerCase() === form.name.trim().toLowerCase() && a.app_type === appType
      );
      if (dup) {
        setDupWarning(`An app named "${dup.name}" (${dup.app_type}) already exists in this project.`);
        return;
      }
    } catch {
      // Duplicate check failure — proceed
    }
    await doPost();
  };

  const handleGenerateMap = async () => {
    if (!savedApp) return;
    setGeneratingMap(true);
    setAppMapError('');
    try {
      const map = await post<AppMapDraft>(`/apps/${savedApp.id}/app-map/generate`, {});
      setAppMap(map);
    } catch (err) {
      setAppMapError(String(err instanceof Error ? err.message : err));
    } finally {
      setGeneratingMap(false);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <AppShell section="onboarding" title={`Add App · step ${step} of ${STEPS.length}`}>
      <div style={{ maxWidth: 680, margin: '0 auto' }}>
        <div style={{ fontSize: 12, color: P.textMute, marginBottom: 16 }}>
          <span style={{ cursor: 'pointer', color: P.accent }} onClick={() => nav('/projects')}>
            Projects
          </span>
          {' / '}
          <span style={{ color: P.textDim }}>New app</span>
        </div>
        <h1 style={{ fontSize: 22, fontWeight: 600, color: P.text, marginBottom: 20 }}>
          Connect a new app
        </h1>

        <StepStrip step={step} total={STEPS.length} />

        {/* ── Step 1: Select / create project ─────────────────────────────── */}
        {step === 1 && (
          <Card>
            <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
              marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              STEP 1 OF {STEPS.length}
            </div>
            <h2 style={{ fontSize: 18, fontWeight: 600, color: P.text, marginBottom: 4 }}>
              Select a project
            </h2>
            <p style={{ fontSize: 13, color: P.textDim, marginBottom: 20 }}>
              Apps belong to a project. Projects group apps, validation packs, runs, evidence, and reports.
            </p>

            {loadingProjects ? (
              <LoadingSkeleton rows={3} />
            ) : isOffline ? (
              <OfflineState onRetry={refetchProjects} />
            ) : (
              <>
                {/* ── Create new project ── */}
                <div style={{ marginBottom: 20 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: P.text, marginBottom: 6 }}>
                    Create a new project
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input
                      data-testid="new-project-name-input"
                      value={newProjectName}
                      onChange={e => setNewProjectName(e.target.value)}
                      placeholder="Project name"
                      onKeyDown={e => e.key === 'Enter' && handleCreateProject()}
                      style={{
                        flex: 1, padding: '7px 10px', borderRadius: 7,
                        background: P.bg, border: `1px solid ${P.border}`,
                        color: P.text, fontSize: 12, outline: 'none',
                      }}
                    />
                    <Btn variant="secondary" demoWrite onClick={handleCreateProject}
                      disabled={!newProjectName.trim() || creatingProject}>
                      {creatingProject ? 'Creating…' : 'Create project'}
                    </Btn>
                  </div>
                  {!newProjectName.trim() && (
                    <div style={{ fontSize: 10, color: P.textFaint, marginTop: 4 }}>
                      Enter a project name to create one.
                    </div>
                  )}
                  {createProjectError && (
                    <div style={{ fontSize: 11, color: P.fail, marginTop: 6 }}>
                      Error: {createProjectError}
                    </div>
                  )}
                </div>

                {/* ── Existing projects ── */}
                {(projects ?? []).length > 0 && (
                  <>
                    <div style={{ borderTop: `1px solid ${P.border}`, paddingTop: 16, marginBottom: 10 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: P.text, marginBottom: 8 }}>
                        Choose an existing project
                      </div>
                      <input
                        data-testid="project-search"
                        value={projectSearch}
                        onChange={e => setProjectSearch(e.target.value)}
                        placeholder="Search projects by name"
                        style={{
                          width: '100%', boxSizing: 'border-box',
                          padding: '6px 10px', borderRadius: 7, marginBottom: 8,
                          background: P.bg, border: `1px solid ${P.border}`,
                          color: P.text, fontSize: 12, outline: 'none',
                        }}
                      />
                      {testProjectCount > 0 && (
                        <>
                          <button
                            data-testid="show-test-projects-toggle"
                            onClick={() => setShowTestProjects(v => !v)}
                            style={{
                              background: showTestProjects ? P.accentSoft : P.cardHi,
                              border: `1px solid ${showTestProjects ? P.accent : P.border}`,
                              borderRadius: 6, cursor: 'pointer',
                              fontSize: 11, color: showTestProjects ? P.accent : P.textDim,
                              padding: '5px 10px', marginBottom: 6,
                              display: 'inline-flex', alignItems: 'center', gap: 5,
                            }}>
                            {showTestProjects
                              ? '▾ Hide test projects'
                              : `▸ Show ${testProjectCount} test project${testProjectCount !== 1 ? 's' : ''}`}
                          </button>
                          {!showTestProjects && (
                            <div style={{ fontSize: 10, color: P.textFaint, marginBottom: 8 }}>
                              E2E test projects are hidden to keep normal workflows clean.
                            </div>
                          )}
                        </>
                      )}
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 16 }}>
                      {visibleProjects.map(p => (
                        <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <div
                            data-testid="project-item"
                            onClick={() => setSelectedProjectId(p.id)}
                            style={{
                              flex: 1, padding: '10px 14px', borderRadius: 8, cursor: 'pointer',
                              border: `2px solid ${selectedProjectId === p.id ? P.accent : P.border}`,
                              background: selectedProjectId === p.id ? P.accentSoft : P.cardHi,
                              transition: 'border-color 0.12s, background 0.12s',
                            }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                              <div style={{ fontSize: 13, fontWeight: 500, color: P.text }}>{p.name}</div>
                              {selectedProjectId === p.id && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 4,
                                  fontSize: 10, color: P.accent, fontWeight: 600 }}>
                                  <Check size={12} />Selected
                                </div>
                              )}
                            </div>
                            {p.description && (
                              <div style={{ fontSize: 11, color: P.textMute, marginTop: 2 }}>
                                {p.description}
                              </div>
                            )}
                          </div>
                          <button
                            data-testid={`delete-project-${p.id}`}
                            title="Delete project"
                            disabled={deletingProjectId === p.id}
                            onClick={() => handleDeleteProject(p)}
                            style={{
                              background: 'none', border: 'none',
                              cursor: deletingProjectId === p.id ? 'not-allowed' : 'pointer',
                              color: P.fail, padding: '6px', borderRadius: 6,
                              opacity: deletingProjectId === p.id ? 0.4 : 0.6,
                              display: 'flex', alignItems: 'center', flexShrink: 0,
                            }}>
                            <Trash2 size={12} />
                          </button>
                        </div>
                      ))}

                      {visibleProjects.length === 0 && (
                        <div style={{ fontSize: 12, color: P.textMute, padding: '10px 0' }}>
                          {projectSearch
                            ? 'No matching projects.'
                            : normalProjectCount === 0 && testProjectCount > 0
                              ? `No normal projects found. Use the toggle above to show ${testProjectCount} test project${testProjectCount !== 1 ? 's' : ''}.`
                              : 'No projects match.'
                          }
                        </div>
                      )}
                    </div>
                  </>
                )}

                {(projects ?? []).length === 0 && (
                  <div style={{ fontSize: 12, color: P.textMute, padding: '8px 0 16px' }}>
                    No projects yet — create one above to continue.
                  </div>
                )}
              </>
            )}

            {/* Selected project summary */}
            <div
              data-testid="selected-project-summary"
              style={{
                marginTop: 16, padding: '10px 14px', borderRadius: 8,
                background: selectedProjectId ? P.accentSoft : P.cardHi,
                border: `1px solid ${selectedProjectId ? P.accent + '66' : P.border}`,
                fontSize: 12, display: 'flex', alignItems: 'center', gap: 8,
                marginBottom: 10,
              }}>
              {selectedProjectId ? (
                <>
                  <Check size={14} style={{ color: P.accent, flexShrink: 0 }} />
                  <span style={{ color: P.textDim }}>
                    Selected project:{' '}
                    <strong style={{ color: P.text }}>
                      {(projects ?? []).find(p => p.id === selectedProjectId)?.name ?? selectedProjectId}
                    </strong>
                  </span>
                </>
              ) : (
                <span style={{ color: P.textMute }}>No project selected yet.</span>
              )}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
              {!selectedProjectId && (
                <div style={{ fontSize: 11, color: P.textMute }}>
                  Select or create a project to continue.
                </div>
              )}
              <Btn variant="primary" onClick={() => setStep(2)} disabled={!selectedProjectId}>
                Next: Choose source →
              </Btn>
            </div>
          </Card>
        )}

        {/* ── Step 2: Source input ─────────────────────────────────────────── */}
        {step === 2 && (
          <Card>
            <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
              marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              STEP 2 OF {STEPS.length}
            </div>
            <h2 style={{ fontSize: 18, fontWeight: 600, color: P.text, marginBottom: 4 }}>
              Where is your app?
            </h2>
            <p style={{ fontSize: 13, color: P.textDim, marginBottom: 16 }}>
              Inspectra reads safe fingerprints (file existence only) to detect your stack.
              No source code is read. No commands are run.
            </p>

            {/* Source tab strip */}
            <div style={{ display: 'flex', gap: 4, marginBottom: 20, flexWrap: 'wrap' }}>
              {SOURCE_TABS.map(t => (
                <button
                  key={t.id}
                  data-testid={t.testId}
                  onClick={() => { setSourceTab(t.id); setScanError(''); }}
                  style={{
                    padding: '6px 12px', borderRadius: 6, cursor: 'pointer',
                    border: `1px solid ${sourceTab === t.id ? P.accent : P.border}`,
                    background: sourceTab === t.id ? P.accentSoft : P.cardHi,
                    color: sourceTab === t.id ? P.accent : P.textDim,
                    fontSize: 12, fontWeight: sourceTab === t.id ? 600 : 400,
                  }}>
                  {t.label}
                  {t.id === 'github_url' && (
                    <span style={{ fontSize: 9, marginLeft: 4, color: P.textMute,
                      border: `1px solid ${P.border}`, borderRadius: 3, padding: '1px 3px' }}>
                      limited
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* Manual */}
            {sourceTab === 'manual' && (
              <div style={{ padding: '16px', borderRadius: 8, background: P.cardHi,
                border: `1px solid ${P.border}`, marginBottom: 16 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: P.text, marginBottom: 6 }}>
                  Manual — enter app details yourself
                </div>
                <div style={{ fontSize: 12, color: P.textDim }}>
                  Skip auto-detection and fill in all fields manually.
                  Best when your app is already running and you know its URL or path.
                </div>
              </div>
            )}

            {/* Local folder — Hybrid Bridge */}
            {sourceTab === 'local_folder' && (
              <div style={{ marginBottom: 16 }}>

                {/* Recent folders (unchanged) */}
                <div data-testid="recent-folders-section" style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                    textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                    Recent folders
                  </div>
                  {recentFolders.length === 0 ? (
                    <div
                      data-testid="recent-folders-empty"
                      style={{ fontSize: 12, color: P.textFaint, padding: '8px 10px',
                        borderRadius: 7, background: P.cardHi, border: `1px solid ${P.border}` }}>
                      No recent folders yet.
                      Paste a path once and Inspectra will remember it here.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                      {recentFolders.map((rf, i) => {
                        const isSelected = localPath === rf.path;
                        const shortPath = rf.path.length > 52
                          ? '…' + rf.path.slice(-(49))
                          : rf.path;
                        return (
                          <div
                            key={rf.path}
                            data-testid={`recent-folder-item-${i}`}
                            style={{ display: 'flex', alignItems: 'center', gap: 4 }}
                          >
                            <button
                              data-testid={`recent-folder-select-${i}`}
                              type="button"
                              onClick={() => setLocalPath(rf.path)}
                              style={{
                                flex: 1, textAlign: 'left', padding: '7px 10px',
                                borderRadius: 7, cursor: 'pointer',
                                border: `1px solid ${isSelected ? P.accent : P.border}`,
                                background: isSelected ? P.accentSoft : P.cardHi,
                              }}
                            >
                              <div style={{ fontSize: 12, fontWeight: 500,
                                color: isSelected ? P.accent : P.text }}>
                                {rf.label}
                              </div>
                              <div style={{ fontSize: 10, color: P.textFaint,
                                fontFamily: F.mono, marginTop: 1 }}>
                                {shortPath}
                              </div>
                            </button>
                            <button
                              data-testid={`recent-folder-remove-${i}`}
                              type="button"
                              title="Remove from recent folders"
                              onClick={() => {
                                const updated = eraseRecentFolder(rf.path);
                                setRecentFolders(updated);
                                if (localPath === rf.path) setLocalPath('');
                              }}
                              style={{
                                padding: '4px 8px', borderRadius: 6, fontSize: 13,
                                border: `1px solid ${P.border}`, background: P.cardHi,
                                color: P.textMute, cursor: 'pointer', flexShrink: 0,
                              }}
                            >×</button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Hybrid Bridge — browse, drop, search, candidate confirmation */}
                <LocalFolderBridge
                  onPathConfirmed={setLocalPath}
                  currentPath={localPath}
                />

                {/* Full local folder path — manual input (always visible) */}
                <div style={{ marginBottom: 12 }}>
                  <label style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                    letterSpacing: '0.06em', textTransform: 'uppercase',
                    display: 'block', marginBottom: 4 }}>
                    Full local folder path <span style={{ color: P.fail }}>*</span>
                  </label>
                  <input
                    data-testid="local-path-input"
                    value={localPath}
                    onChange={e => setLocalPath(e.target.value)}
                    placeholder="/Users/aman/Documents/Projects/my-app"
                    style={{
                      width: '100%', padding: '7px 10px', borderRadius: 7,
                      boxSizing: 'border-box', background: P.bg,
                      border: `1px solid ${localPath.trim() ? P.accent : P.border}`,
                      color: P.text, fontSize: 12, fontFamily: F.mono, outline: 'none',
                    }}
                  />
                  <div style={{ fontSize: 10, color: P.textFaint, marginTop: 3 }}>
                    Use Browse or Find above, or paste the path here directly.
                    Inspectra remembers approved paths as recent folders after a successful scan.
                  </div>
                </div>

                {/* Permission checkbox */}
                <label
                  data-testid="permission-label"
                  style={{ display: 'flex', alignItems: 'flex-start', gap: 8, cursor: 'pointer',
                    padding: '10px 12px', borderRadius: 8, border: `1px solid ${P.border}`,
                    background: P.cardHi }}>
                  <input
                    data-testid="permission-checkbox"
                    type="checkbox"
                    checked={permissionChecked}
                    onChange={e => setPermissionChecked(e.target.checked)}
                    style={{ marginTop: 2, flexShrink: 0, accentColor: P.accent }}
                  />
                  <span style={{ fontSize: 12, color: P.textDim, lineHeight: 1.5 }}>
                    I allow Inspectra to scan safe project fingerprints in this folder.
                    <span style={{ display: 'block', fontSize: 10, color: P.textFaint, marginTop: 2 }}>
                      Only file names and package.json metadata are read.
                      No source code, no secrets, no commands are executed.
                    </span>
                  </span>
                </label>
              </div>
            )}

            {/* Web URL */}
            {sourceTab === 'web_url' && (
              <div style={{ marginBottom: 16 }}>
                <Field
                  label="Web app URL"
                  value={sourceUrl}
                  onChange={setSourceUrl}
                  mono
                  placeholder="https://myapp.example.com"
                  note="http:// or https:// only. No network request is made — just URL validation."
                />
              </div>
            )}

            {/* API URL */}
            {sourceTab === 'api_base_url' && (
              <div style={{ marginBottom: 16 }}>
                <Field
                  label="API base URL"
                  value={sourceUrl}
                  onChange={setSourceUrl}
                  mono
                  placeholder="http://localhost:8000"
                  note="http:// or https:// only. No requests are made — just URL validation."
                />
              </div>
            )}

            {/* GitHub */}
            {sourceTab === 'github_url' && (
              <div style={{ padding: '16px', borderRadius: 8, background: P.unclearSoft,
                border: `1px solid ${P.unclear}33`, marginBottom: 16 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: P.unclear, marginBottom: 6 }}>
                  GitHub URL — limited support
                </div>
                <div style={{ fontSize: 12, color: P.textDim, marginBottom: 10 }}>
                  Inspectra cannot clone or read GitHub repositories in this version.
                  Clone the repo locally and use <strong>Local folder</strong> instead.
                </div>
                <Field
                  label="GitHub URL (recorded for reference)"
                  value={sourceUrl}
                  onChange={setSourceUrl}
                  mono
                  placeholder="https://github.com/org/repo"
                />
              </div>
            )}

            {scanError && (
              <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 7,
                background: P.failSoft, border: `1px solid ${P.fail}33`,
                fontSize: 12, color: P.fail }}>
                {scanError}
              </div>
            )}

            <div style={{ display: 'flex', gap: 8, justifyContent: 'space-between', marginTop: 8 }}>
              <Btn variant="ghost" onClick={() => setStep(1)}>← Back</Btn>
              <Btn demoWrite
                variant="primary"
                onClick={handleScanOrSkip}
                disabled={scanning
                  || (sourceTab === 'local_folder' && (!localPath.trim() || !permissionChecked))
                  || (['web_url', 'api_base_url', 'github_url'].includes(sourceTab) && !sourceUrl.trim())}
              >
                {scanning
                  ? 'Scanning…'
                  : sourceTab === 'manual'
                    ? 'Next: App details →'
                    : 'Scan & detect →'}
              </Btn>
            </div>
          </Card>
        )}

        {/* ── Step 3: Review & confirm ─────────────────────────────────────── */}
        {step === 3 && (
          <Card>
            <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
              marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              STEP 3 OF {STEPS.length}
            </div>
            <h2 style={{ fontSize: 18, fontWeight: 600, color: P.text, marginBottom: 4 }}>
              Review & confirm
            </h2>
            <p style={{ fontSize: 12, color: P.textDim, marginBottom: 20 }}>
              {discoveryResult?.status === 'complete'
                ? 'Inspectra detected the following. Review and edit before creating the app.'
                : discoveryResult?.status === 'unsupported'
                  ? 'Auto-detection was not possible for this source. Enter details manually.'
                  : 'Enter app details below.'}
            </p>

            {/* Discovery result — stack info (complete only) */}
            {discoveryResult?.status === 'complete' && discoveryResult.detected_stack.length > 0 && (
              <div style={{ marginBottom: 16, padding: '10px 14px', borderRadius: 8,
                background: P.cardHi, border: `1px solid ${P.border}` }}>
                <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                  textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                  Detected stack
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {discoveryResult.detected_stack.map((s, i) => (
                    <span key={i} style={{
                      fontSize: 11, padding: '3px 8px', borderRadius: 5,
                      background: P.accentSoft, color: P.accent,
                      border: `1px solid ${P.accent}33`,
                    }}>
                      {s.value}
                      <ConfBadge conf={s.confidence} />
                    </span>
                  ))}
                </div>
                {discoveryResult.fingerprint && (
                  <div style={{ fontSize: 10, color: P.textFaint, marginTop: 6 }}>
                    Scanned {discoveryResult.fingerprint.files_scanned} files
                    {discoveryResult.fingerprint.truncated ? ' (truncated)' : ''}
                  </div>
                )}
              </div>
            )}

            {/* Source path / URL display (complete or failed) */}
            {discoveryResult && (discoveryResult.local_path || discoveryResult.url) && (
              <div style={{ marginBottom: 12, fontSize: 11, color: P.textMute,
                fontFamily: F.mono, padding: '6px 10px', borderRadius: 6,
                background: P.cardHi, border: `1px solid ${P.border}` }}>
                {discoveryResult.local_path
                  ? <>📁 {discoveryResult.local_path}</>
                  : <>🔗 {discoveryResult.url}</>}
              </div>
            )}

            {/* Audit strategy */}
            {discoveryResult?.audit_strategy && (
              <div style={{ marginBottom: 14, padding: '10px 14px', borderRadius: 8,
                background: P.cardHi, border: `1px solid ${P.border}` }}>
                <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                  textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                  Suggested audit strategy
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: P.text, marginBottom: 4 }}>
                  {discoveryResult.audit_strategy.strategy}
                  <ConfBadge conf={discoveryResult.audit_strategy.confidence} />
                </div>
                <div style={{ fontSize: 11, color: P.textDim }}>
                  {discoveryResult.audit_strategy.reason}
                </div>
              </div>
            )}

            {/* Unsupported notice */}
            {discoveryResult?.status === 'unsupported' && (
              <div style={{ marginBottom: 16, padding: '10px 14px', borderRadius: 8,
                background: P.unclearSoft, border: `1px solid ${P.unclear}33`,
                fontSize: 12, color: P.unclear }}>
                ⚠ {discoveryResult.error_message}
              </div>
            )}

            {/* App type selector */}
            <div style={{ fontSize: 13, fontWeight: 600, color: P.text, marginBottom: 8 }}>
              App type
              {discoveryResult?.suggested_app_type && (
                <ConfBadge conf={discoveryResult.suggested_app_type.confidence} />
              )}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 20 }}>
              {APP_TYPES.map(t => {
                const preview = isPreviewAppType(t.id);
                return (
                <button
                  key={t.id}
                  type="button"
                  aria-label={`${t.label}${preview ? ' Preview' : ''}`}
                  disabled={preview}
                  title={preview ? PREVIEW_TOOLTIP : undefined}
                  onClick={() => setAppType(t.id)}
                  style={{
                  padding: '12px 14px', borderRadius: 9, cursor: preview ? 'not-allowed' : 'pointer',
                  border: `1px solid ${appType === t.id ? P.accent : P.border}`,
                  background: appType === t.id ? P.accentSoft : P.cardHi,
                  transition: 'border-color 0.12s, background 0.12s',
                  textAlign: 'left', opacity: preview ? 0.72 : 1,
                }}>
                  <div style={{ fontSize: 20, marginBottom: 4 }}>{t.icon}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 600, color: P.text, marginBottom: 2 }}>
                    {t.label}
                    {preview && <PreviewBadge />}
                  </div>
                  <div style={{ fontSize: 11, color: P.textMute }}>{t.sub}</div>
                </button>
              );})}
            </div>

            {/* App details form */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <Field
                label="App name"
                value={form.name}
                onChange={v => setForm(f => ({ ...f, name: v }))}
                required
                placeholder="My App"
              />
              {(appType === 'web' || appType === 'api') && (
                <Field
                  label={appType === 'api' ? 'Base URL (API)' : 'App URL'}
                  value={form.base_url}
                  onChange={v => setForm(f => ({ ...f, base_url: v }))}
                  placeholder="http://localhost:3000"
                  note="http:// or https:// only"
                  mono
                />
              )}
              {discoveryResult?.status === 'complete' && (
                <Field
                  label="Launch command"
                  value={form.launch_command}
                  onChange={v => setForm(f => ({ ...f, launch_command: v }))}
                  placeholder="npm run dev"
                  mono
                  note="How to start the app locally. Optional."
                />
              )}
              <Field
                label="Description (optional)"
                value={form.description}
                onChange={v => setForm(f => ({ ...f, description: v }))}
                placeholder="Short description of this app"
              />
            </div>

            {/* Duplicate warning */}
            {dupWarning && (
              <div data-testid="dup-warning" style={{ marginTop: 12, padding: '10px 12px', borderRadius: 7,
                background: P.unclearSoft, border: `1px solid ${P.unclear}33`,
                fontSize: 12, color: P.unclear }}>
                ⚠ {dupWarning}
                <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                  <Btn size="sm" variant="ghost" onClick={() => setDupWarning('')}>Cancel</Btn>
                  <Btn size="sm" variant="secondary" onClick={() => { setDupWarning(''); doPost(); }}>
                    Create anyway
                  </Btn>
                </div>
              </div>
            )}

            {saveError && (
              <div style={{ marginTop: 12, padding: '8px 12px', borderRadius: 7,
                background: P.failSoft, border: `1px solid ${P.fail}33`,
                fontSize: 12, color: P.fail }}>
                Save failed: {saveError}
              </div>
            )}

            <div style={{ display: 'flex', gap: 8, justifyContent: 'space-between', marginTop: 20 }}>
              <div style={{ display: 'flex', gap: 8 }}>
                <Btn variant="ghost" onClick={() => setStep(2)}>← Back</Btn>
                {discoveryResult && sourceTab !== 'manual' && (
                  <button
                    data-testid="rescan-btn"
                    onClick={() => { setDiscoveryResult(null); setStep(2); }}
                    style={{ padding: '6px 12px', borderRadius: 7, fontSize: 12,
                      border: `1px solid ${P.border}`, background: P.cardHi,
                      color: P.textDim, cursor: 'pointer' }}
                  >
                    ↺ Re-scan
                  </button>
                )}
              </div>
              <Btn
                variant="primary"
                onClick={handleSave}
                disabled={!form.name.trim() || !appType || saving}
              >
                {saving ? 'Saving…' : 'Save & connect →'}
              </Btn>
            </div>
          </Card>
        )}

        {/* ── Step 4: Done + next actions ──────────────────────────────────── */}
        {step === 4 && savedApp && (
          <Card>
            {/* Success header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
              <div style={{
                width: 44, height: 44, borderRadius: 99,
                background: P.passSoft, border: `2px solid ${P.pass}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 22, flexShrink: 0,
              }}>✓</div>
              <div>
                <h2 style={{ fontSize: 18, fontWeight: 700, color: P.pass, marginBottom: 2 }}>
                  {savedApp.name} connected!
                </h2>
                <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono }}>
                  {savedApp.id}
                </div>
              </div>
            </div>

            {/* App summary row */}
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 20,
              padding: '10px 14px', borderRadius: 8, background: P.cardHi, border: `1px solid ${P.border}` }}>
              <div style={{ fontSize: 12, color: P.textDim }}>
                Type: <strong style={{ color: P.text }}>{savedApp.app_type}</strong>
              </div>
              {savedApp.source_type && savedApp.source_type !== 'manual' && (
                <div style={{ fontSize: 12, color: P.textDim }}>
                  Source: <strong style={{ color: P.text }}>
                    {savedApp.source_type.replace(/_/g, ' ')}
                  </strong>
                </div>
              )}
              {savedApp.detected_stack && (
                <div style={{ fontSize: 12, color: P.textDim }}>
                  Stack: <strong style={{ color: P.text }}>
                    {savedApp.detected_stack.split(',').join(', ')}
                  </strong>
                </div>
              )}
            </div>

            {/* Next recommended actions */}
            <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
              textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
              Recommended next steps
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 20 }}>

              {/* 1. Generate app map */}
              <div style={{ padding: '12px 14px', borderRadius: 9,
                border: `1px solid ${appMap ? P.pass : P.border}`,
                background: appMap ? P.passSoft : P.cardHi }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <div style={{ fontSize: 18, flexShrink: 0 }}>🗺</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: P.text, marginBottom: 2 }}>
                      Generate app map
                    </div>
                    <div style={{ fontSize: 11, color: P.textDim, marginBottom: 8 }}>
                      Builds a fingerprint-based draft of entry points, surfaces, and risk areas.
                    </div>

                    {/* App map summary (post-generate) */}
                    {appMap && (
                      <div style={{ marginBottom: 8, fontSize: 11, color: P.textDim }}>
                        <span style={{ marginRight: 10 }}>
                          Type: <code style={{ fontFamily: F.mono, color: P.textMute }}>{appMap.map_type}</code>
                        </span>
                        <span style={{ marginRight: 10 }}>
                          Confidence: <ConfBadge conf={appMap.confidence} />
                        </span>
                        <span style={{ marginRight: 10 }}>
                          Surfaces: <strong>{appMap.testable_surfaces.length}</strong>
                        </span>
                        <span style={{ marginRight: 10 }}>
                          Risks: <strong>{appMap.risk_areas.length}</strong>
                        </span>
                        {appMap.capability_gaps.length > 0 && (
                          <span style={{ color: P.unclear }}>
                            ⚠ {appMap.capability_gaps.length} gap{appMap.capability_gaps.length !== 1 ? 's' : ''}
                          </span>
                        )}
                      </div>
                    )}

                    {/* Error */}
                    {appMapError && !appMap && (
                      <div style={{ marginBottom: 8, fontSize: 11, color: P.fail,
                        padding: '6px 10px', borderRadius: 6, background: P.failSoft }}>
                        ⚠ {appMapError}
                        <div style={{ marginTop: 4, color: P.textDim }}>
                          Map generation unavailable — capability gap recorded. You can still create a test plan manually.
                        </div>
                      </div>
                    )}

                    {!appMap && (
                      <button
                        data-testid="generate-app-map-btn"
                        onClick={handleGenerateMap}
                        disabled={generatingMap}
                        style={{
                          padding: '6px 14px', borderRadius: 7, fontSize: 12, fontWeight: 600,
                          border: `1px solid ${P.accent}`, background: P.accentSoft,
                          color: P.accent, cursor: generatingMap ? 'not-allowed' : 'pointer',
                          opacity: generatingMap ? 0.6 : 1,
                        }}
                      >
                        {generatingMap ? 'Generating…' : 'Generate app map'}
                      </button>
                    )}
                    {appMap && (
                      <div style={{ fontSize: 11, color: P.pass, fontWeight: 600 }}>✓ App map ready</div>
                    )}
                  </div>
                </div>
              </div>

              {/* 2. Create validation pack + test plan */}
              <div style={{ padding: '12px 14px', borderRadius: 9,
                border: `1px solid ${P.border}`, background: P.cardHi }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <div style={{ fontSize: 18, flexShrink: 0 }}>📋</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: P.text, marginBottom: 2 }}>
                      Create validation pack &amp; test plan
                    </div>
                    <div style={{ fontSize: 11, color: P.textDim, marginBottom: 8 }}>
                      Group test cases and generate a tailored plan for {savedApp.name}.
                    </div>
                    <button
                      data-testid="create-pack-btn"
                      onClick={() => nav('/packs/new')}
                      style={{
                        padding: '6px 14px', borderRadius: 7, fontSize: 12, fontWeight: 600,
                        border: `1px solid ${P.border}`, background: P.card,
                        color: P.text, cursor: 'pointer',
                      }}
                    >
                      Create validation pack
                    </button>
                  </div>
                </div>
              </div>

              {/* 3. Run Runtime Doctor */}
              <div style={{ padding: '12px 14px', borderRadius: 9,
                border: `1px solid ${P.border}`, background: P.cardHi }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <div style={{ fontSize: 18, flexShrink: 0 }}>🩺</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: P.text, marginBottom: 2 }}>
                      Run Runtime Doctor
                    </div>
                    <div style={{ fontSize: 11, color: P.textDim, marginBottom: 8 }}>
                      Verify Inspectra can reach and interact with this app.
                    </div>
                    <button
                      data-testid="run-doctor-btn"
                      onClick={() => nav('/doctor')}
                      style={{
                        padding: '6px 14px', borderRadius: 7, fontSize: 12, fontWeight: 600,
                        border: `1px solid ${P.border}`, background: P.card,
                        color: P.text, cursor: 'pointer',
                      }}
                    >
                      Run Runtime Doctor
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer nav */}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'space-between', borderTop: `1px solid ${P.border}`, paddingTop: 16 }}>
              <Btn variant="ghost" onClick={() => nav('/projects')}>Back to Projects</Btn>
              <button
                data-testid="open-app-detail-btn"
                onClick={() => nav(`/apps/${savedApp.id}`)}
                style={{
                  padding: '8px 18px', borderRadius: 8, fontSize: 13, fontWeight: 600,
                  border: 'none', background: P.accent, color: '#fff', cursor: 'pointer',
                }}
              >
                Open App Detail →
              </button>
            </div>
          </Card>
        )}

        {step === 4 && !savedApp && (
          <Card>
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <div style={{ fontSize: 13, color: P.fail, marginBottom: 12 }}>App was not saved.</div>
              <Btn variant="ghost" onClick={() => setStep(3)}>← Back to details</Btn>
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
