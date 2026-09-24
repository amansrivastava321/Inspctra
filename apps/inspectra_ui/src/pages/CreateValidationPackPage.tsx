import { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Zap } from 'lucide-react';
import { P, F } from '../design/tokens';
import { AppShell, Card, Btn } from '../components/layout/AppShell';
import { LoadingSkeleton, OfflineState } from '../components/common/EmptyState';
import { useApi } from '../hooks/useApi';
import { get, post } from '../api/client';
import { generateTestPlan } from '../api/validationPacks';
import type { Project } from '../types/api';
import { useWorkspaceNavigate } from '../state/WorkspaceModeContext';

function getProjects() { return get<Project[]>('/projects'); }

interface BackendApp { id: string; name: string; app_type: string; project_id: string; }

function Field({ label, value, onChange, note, required, placeholder, as: Tag = 'input' }:
  { label: string; value: string; onChange: (v: string) => void;
    note?: string; required?: boolean; placeholder?: string; as?: 'input' | 'textarea' }) {
  const base = {
    width: '100%', padding: '7px 10px', borderRadius: 7, boxSizing: 'border-box' as const,
    background: P.bg, border: `1px solid ${P.border}`,
    color: P.text, fontSize: 12, outline: 'none', fontFamily: 'inherit',
    ...(Tag === 'textarea' ? { minHeight: 80, resize: 'vertical' as const } : {}),
  };
  return (
    <div>
      <label style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
        letterSpacing: '0.06em', textTransform: 'uppercase', display: 'block', marginBottom: 4 }}>
        {label}{required && <span style={{ color: P.fail }}> *</span>}
      </label>
      {Tag === 'textarea'
        ? <textarea value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} style={base} />
        : <input value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} style={base} />
      }
      {note && <div style={{ fontSize: 10, color: P.textFaint, marginTop: 3 }}>{note}</div>}
    </div>
  );
}

export default function CreateValidationPackPage() {
  const nav = useWorkspaceNavigate();
  const [searchParams] = useSearchParams();

  // Query params: ?app_id=...&project_id=... (from AppDetailPage CTA)
  const queryAppId = searchParams.get('app_id') ?? '';
  const queryProjectId = searchParams.get('project_id') ?? '';

  const { data: projects, loading: loadingProjects, refetch, isOffline } =
    useApi(useCallback(getProjects, []), { demo: workspace => workspace.projects });

  const [selectedProjectId, setSelectedProjectId] = useState(queryProjectId);
  const [selectedAppId, setSelectedAppId] = useState(queryAppId);
  const [linkedApp, setLinkedApp] = useState<BackendApp | null>(null);
  const [form, setForm] = useState({ name: '', description: '' });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [createdPackId, setCreatedPackId] = useState<string | null>(null);
  const [generatingPlan, setGeneratingPlan] = useState(false);

  // Preselect project from query param once projects load
  useEffect(() => {
    if (queryProjectId && projects && projects.some(p => p.id === queryProjectId)) {
      setSelectedProjectId(queryProjectId);
    }
  }, [projects, queryProjectId]);

  // Load the linked app for display if app_id passed in query
  useEffect(() => {
    if (!queryAppId) return;
    get<BackendApp>(`/apps/${queryAppId}`)
      .then(a => setLinkedApp(a))
      .catch(() => {/* app not found — clear the preselection */setSelectedAppId('');});
  }, [queryAppId]);

  const canSave = form.name.trim().length > 0 && selectedProjectId.length > 0;

  const handleSave = async () => {
    if (!canSave) return;
    setSaving(true);
    setSaveError('');
    try {
      const pack = await post<{ id: string; app_id?: string }>('/validation-packs', {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        project_id: selectedProjectId,
        steps: [],
        ...(selectedAppId ? { app_id: selectedAppId } : {}),
      });
      setCreatedPackId(pack.id);
      // Show "generate now?" prompt — do NOT auto-generate
    } catch (err) {
      setSaveError(String(err instanceof Error ? err.message : err));
    } finally {
      setSaving(false);
    }
  };

  const handleGenerateNow = async () => {
    if (!createdPackId) return;
    setGeneratingPlan(true);
    try {
      // Pass app_id if available so backend can load app_map for enrichment
      await generateTestPlan(createdPackId, false, selectedAppId || undefined);
    } catch { /* ignore — user can regenerate from pack detail */ }
    nav(`/packs/${createdPackId}`);
  };

  const handleSkipGenerate = () => {
    if (createdPackId) nav(`/packs/${createdPackId}`);
    else nav('/packs');
  };

  return (
    <AppShell section="03" title="New Validation Pack">
      <div style={{ maxWidth: 620, margin: '0 auto' }}>
        {/* Breadcrumb */}
        <div style={{ fontSize: 12, color: P.textMute, marginBottom: 16 }}>
          <span style={{ cursor: 'pointer', color: P.accent }} onClick={() => nav('/packs')}>
            Validation Packs
          </span>
          {' / '}
          <span style={{ color: P.textDim }}>New pack</span>
        </div>

        <h1 style={{ fontSize: 22, fontWeight: 600, color: P.text, marginBottom: 20 }}>
          Create validation pack
        </h1>

        <Card>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Pack name + description */}
            <Field
              label="Pack name"
              value={form.name}
              onChange={v => setForm(f => ({ ...f, name: v }))}
              required
              placeholder="Daily smoke, Regression suite, …"
            />
            <Field
              label="Description (optional)"
              value={form.description}
              onChange={v => setForm(f => ({ ...f, description: v }))}
              placeholder="What does this pack verify?"
              as="textarea"
            />

            {/* Linked app (pre-filled from query param or shown if set) */}
            {linkedApp && (
              <div data-testid="linked-app-summary" style={{ padding: '10px 14px', borderRadius: 8,
                background: P.accentSoft, border: `1px solid ${P.accent}33` }}>
                <div style={{ fontSize: 10, color: P.accent, fontFamily: F.mono,
                  textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                  Linked app
                </div>
                <div style={{ fontSize: 13, fontWeight: 500, color: P.text }}>{linkedApp.name}</div>
                <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono }}>{linkedApp.app_type}</div>
                <button
                  data-testid="unlink-app-btn"
                  onClick={() => { setSelectedAppId(''); setLinkedApp(null); }}
                  style={{ fontSize: 10, color: P.textMute, background: 'none', border: 'none',
                    cursor: 'pointer', marginTop: 6, textDecoration: 'underline' }}>
                  Remove app link (create generic pack)
                </button>
              </div>
            )}

            {/* Project selector */}
            <div>
              <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8 }}>
                Project <span style={{ color: P.fail }}>*</span>
              </div>

              {loadingProjects ? (
                <LoadingSkeleton rows={2} />
              ) : isOffline ? (
                <OfflineState onRetry={refetch} />
              ) : (projects ?? []).length === 0 ? (
                <div style={{ padding: '12px 14px', borderRadius: 8, background: P.cardHi,
                  border: `1px solid ${P.border}`, fontSize: 12, color: P.textMute }}>
                  No projects yet.{' '}
                  <span style={{ color: P.accent, cursor: 'pointer' }} onClick={() => nav('/projects/new')}>
                    Create a project first
                  </span>.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {(projects ?? []).map(p => (
                    <div key={p.id} data-testid={`project-card-${p.id}`} onClick={() => setSelectedProjectId(p.id)} style={{
                      padding: '10px 14px', borderRadius: 8, cursor: 'pointer',
                      border: `1px solid ${selectedProjectId === p.id ? P.accent : P.border}`,
                      background: selectedProjectId === p.id ? P.accentSoft : P.cardHi,
                      transition: 'border-color 0.12s, background 0.12s',
                    }}>
                      <div style={{ fontSize: 13, fontWeight: 500, color: P.text }}>{p.name}</div>
                      {p.description && (
                        <div style={{ fontSize: 11, color: P.textMute, marginTop: 2 }}>{p.description}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Info note about steps */}
            <div style={{ padding: '10px 14px', borderRadius: 8, background: P.cardHi,
              border: `1px solid ${P.border}`, fontSize: 12, color: P.textMute }}>
              Steps are added after creation. Create the pack, then open it to define validation flows.
            </div>

            {saveError && (
              <div style={{ padding: '8px 12px', borderRadius: 7,
                background: P.failSoft, border: `1px solid ${P.fail}33`,
                fontSize: 12, color: P.fail }}>
                Save failed: {saveError}
              </div>
            )}

            {/* "Generate test plan now?" prompt shown after pack is created */}
            {createdPackId ? (
              <div data-testid="generate-now-prompt"
                style={{ padding: '16px', borderRadius: 8, background: P.accentSoft,
                  border: `1px solid ${P.accent}33` }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: P.text, marginBottom: 6 }}>
                  Pack created! Generate a test plan now?
                </div>
                <div style={{ fontSize: 12, color: P.textDim, marginBottom: 14 }}>
                  {selectedAppId
                    ? 'Inspectra will generate test cases using the linked app and its app map.'
                    : 'Inspectra can generate a generic test plan based on app type. You can refine it after connecting an app.'}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <Btn variant="primary" size="sm" demoWrite onClick={handleGenerateNow} disabled={generatingPlan}>
                    <Zap size={11} />{generatingPlan ? 'Generating…' : 'Generate test plan'}
                  </Btn>
                  <Btn variant="ghost" size="sm" onClick={handleSkipGenerate}>
                    Skip for now
                  </Btn>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', gap: 8, justifyContent: 'space-between' }}>
                <Btn variant="ghost" onClick={() => nav('/packs')}>Cancel</Btn>
                <Btn variant="primary" demoWrite onClick={handleSave} disabled={!canSave || saving}>
                  {saving ? 'Creating…' : 'Create pack →'}
                </Btn>
              </div>
            )}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
