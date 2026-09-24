import { useState, useCallback, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Play,
  Trash2,
  RefreshCw,
  Zap,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  Copy,
  Plus,
  ArrowUp,
  ArrowDown,
  Edit2,
  X,
  Check,
  Sparkles,
} from 'lucide-react';
import { P, F } from '../design/tokens';
import { AppShell, PageHeader, Card, Btn, StatCard } from '../components/layout/AppShell';
import { StatusBadge } from '../components/status/StatusBadge';
import { LoadingSkeleton, ErrorState, OfflineState, PartialConfigBanner } from '../components/common/EmptyState';
import { StartRunModal } from '../components/modals/StartRunModal';
import { useApi } from '../hooks/useApi';
import { useWorkspaceNavigate } from '../state/WorkspaceModeContext';
import { get, post, del, patch } from '../api/client';
import {
  getTestPlan,
  generateTestPlan,
  listTestCases,
  updateTestCase,
  deleteTestCase,
  duplicateTestCase,
  addTestCaseStep,
  updateTestCaseStep,
  deleteTestCaseStep,
  reorderTestCaseSteps,
  generateAiTestPlan,
  acceptAiTestPlan,
} from '../api/validationPacks';
import type {
  LiveRunRecord,
  TestCase,
  TestPlan,
  TestCaseStep,
  TestCaseStepCreate,
  AITestPlanPreview,
  AIProposedTestCase,
  AIProposedTestStep,
  Provenance,
} from '../types/api';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { PreviewBadge } from '../components/PreviewBadge';
import { CapabilityTypeSelector } from '../components/validation/CapabilityTypeSelector';
import {
  hasPreviewSteps,
  isPreviewAction,
  isPreviewAppType,
  isPreviewStep,
  PREVIEW_RUN_TOOLTIP,
  PREVIEW_TOOLTIP,
  testCaseContainsPreview,
} from '../config/capabilities';

// Backend ValidationPack shape (simpler than frontend type)
interface BackendPack {
  id: string;
  name: string;
  description?: string;
  project_id: string;
  app_id?: string;   // linked app target (null = generic pack)
  target_app_ids?: string[];
  target_names?: string[];
  steps: Record<string, unknown>[];
  created_at: string;
  updated_at: string;
  provenance?: Provenance;
  schedule?: string;
  schedule_enabled?: boolean;
  next_run_at?: string;
  last_scheduled_run_at?: string;
}

// ── color maps ─────────────────────────────────────────────────────────────────

const TYPE_COLOR: Record<string, string> = {
  positive:       P.pass,
  negative:       P.fail,
  edge_case:      P.unclear,
  security:       '#f472b6',
  performance:    P.accent,
  ai_behavior:    '#a78bfa',
  accessibility:  '#38bdf8',
  regression:     P.textDim,
  data_integrity: P.unclear,
  permission:     P.blocked,
  sync_offline:   P.textDim,
  api_contract:   P.accent,
  visual:         '#e879f9',
};

const SAFETY_COLOR: Record<string, string> = {
  safe:             P.pass,
  caution:          P.unclear,
  destructive:      P.fail,
  external_cost:    '#f97316',
  real_user_impact: P.fail,
};

const AUTOMATION_LABEL: Record<string, string> = {
  ready:             'READY',
  needs_selector:    'NEEDS SELECTOR',
  needs_credentials: 'NEEDS CREDS',
  needs_permission:  'NEEDS PERM',
  blocked:           'BLOCKED',
  manual_only:       'MANUAL',
  capability_gap:    'GAP',
};

// ── tab config ─────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'all',         label: 'All' },
  { id: 'positive',    label: 'Positive' },
  { id: 'negative',    label: 'Negative' },
  { id: 'edge_case',   label: 'Edge Cases' },
  { id: 'security',    label: 'Security' },
  { id: 'performance', label: 'Performance' },
  { id: 'blocked',     label: 'Blocked' },
];

// ── sub-components ─────────────────────────────────────────────────────────────

function TypeBadge({ type }: { type: string }) {
  const c = TYPE_COLOR[type] ?? P.textDim;
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, letterSpacing: '0.06em', fontFamily: F.mono,
      background: `${c}18`, border: `1px solid ${c}33`, borderRadius: 4,
      padding: '2px 5px', color: c, textTransform: 'uppercase',
    }}>
      {type.replace(/_/g, ' ')}
    </span>
  );
}

function SafetyBadge({ level }: { level: string }) {
  if (level === 'safe') return null;
  const c = SAFETY_COLOR[level] ?? P.fail;
  return (
    <span data-testid={`safety-badge-${level}`} style={{
      fontSize: 9, fontWeight: 700, letterSpacing: '0.06em', fontFamily: F.mono,
      background: `${c}18`, border: `1px solid ${c}44`, borderRadius: 4,
      padding: '2px 5px', color: c, textTransform: 'uppercase',
    }}>
      ⚠ {level.replace(/_/g, ' ')}
    </span>
  );
}

function AutoBadge({ status }: { status: string }) {
  const ready = status === 'ready';
  const c = ready ? P.pass : P.textMute;
  return (
    <span style={{
      fontSize: 9, fontWeight: 600, letterSpacing: '0.04em', fontFamily: F.mono,
      background: `${c}12`, border: `1px solid ${c}22`, borderRadius: 4,
      padding: '2px 5px', color: c, textTransform: 'uppercase',
    }}>
      {AUTOMATION_LABEL[status] ?? status}
    </span>
  );
}

const ACTION_TYPES = [
  'navigate',
  'screenshot',
  'click',
  'type',
  'select',
  'press',
  'wait_for_selector',
  'assert_visible',
  'assert_text_contains',
  'assert_url_contains',
  'assert_title_contains',
  'check_accessibility',
  'assert_accessibility',
  'accessibility_scan',
  'assert_no_critical_a11y_violations',
  'assert_no_a11y_violations',
  'api_request',
  'assert_status',
  'assert_json_path',
  'assert_header_contains',
  'assert_body_contains',
  'assert_response_time_under',
  'measure_page_load',
  'assert_page_load_under',
  'assert_api_response_time_under',
  'assert_visual_match',
  'visual_capture',
  'visual_compare',
  'passive_security_check',
  'assert_no_critical_security_findings',
  'assert_security_headers_present',
  'assert_cookie_flags_secure',
];

const HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'];
const isApiAction = (action: string) =>
  ['api_request', 'assert_status', 'assert_json_path', 'assert_header_contains', 'assert_body_contains', 'assert_response_time_under', 'assert_api_response_time_under'].includes(action);
const isApiRequestAction = (action: string) => action === 'api_request';
const isJsonPathAction = (action: string) => action === 'assert_json_path';
const isHeaderAssertAction = (action: string) => action === 'assert_header_contains';
const isBodyAssertAction = (action: string) => action === 'assert_body_contains';
const isResponseTimeAssertAction = (action: string) => ['assert_response_time_under', 'assert_api_response_time_under'].includes(action);
const isStatusAssertAction = (action: string) => action === 'assert_status';
const isPerformanceAction = (action: string) =>
  ['measure_page_load', 'assert_page_load_under', 'assert_api_response_time_under', 'assert_response_time_under'].includes(action);
const isA11yAction = (action: string) =>
  ['check_accessibility', 'assert_accessibility', 'accessibility_scan', 'assert_no_critical_a11y_violations', 'assert_no_a11y_violations'].includes(action);
const isVisualAction = (action: string) =>
  ['assert_visual_match', 'visual_capture', 'visual_compare'].includes(action);
const isSecurityAction = (action: string) =>
  ['passive_security_check', 'assert_no_critical_security_findings', 'assert_security_headers_present', 'assert_cookie_flags_secure'].includes(action);

const isTargetNeeded = (action: string) =>
  ['navigate', 'click', 'type', 'select', 'press', 'wait_for_selector', 'assert_visible', 'assert_text_contains', 'check_accessibility', 'assert_accessibility', 'accessibility_scan', 'assert_no_critical_a11y_violations', 'assert_no_a11y_violations', 'assert_visual_match', 'visual_capture', 'visual_compare', 'passive_security_check', 'assert_no_critical_security_findings', 'assert_security_headers_present', 'assert_cookie_flags_secure'].includes(action) || isHeaderAssertAction(action);

const isValueNeeded = (action: string) =>
  ['type', 'select', 'press', 'assert_visual_match', 'visual_capture', 'visual_compare', 'passive_security_check', 'assert_no_critical_security_findings', 'assert_security_headers_present', 'assert_cookie_flags_secure'].includes(action);

const isExpectedNeeded = (action: string) =>
  ['assert_text_contains', 'assert_url_contains', 'assert_title_contains', 'assert_visual_match', 'visual_compare', 'passive_security_check', 'assert_no_critical_security_findings', 'assert_security_headers_present', 'assert_cookie_flags_secure'].includes(action);

function safeParseJson(raw: string, label: string) {
  if (!raw.trim()) return undefined;
  try {
    return JSON.parse(raw);
  } catch {
    throw new Error(`${label} must be valid JSON.`);
  }
}

export function normalizeStepPayload(form: Record<string, any>) {
  return {
    action_type: form.action_type,
    target: form.target || undefined,
    value: form.value || undefined,
    expected: form.expected || undefined,
    method: form.method || undefined,
    url: form.url || undefined,
    headers: safeParseJson(form.headers_text || '', 'Headers JSON'),
    query_params: safeParseJson(form.query_params_text || '', 'Query Params JSON'),
    body_json: safeParseJson(form.body_json_text || '', 'Body JSON'),
    expected_status: form.expected_status ? Number(form.expected_status) : undefined,
    expected_json_path: form.expected_json_path || undefined,
    expected_value: form.expected_value || undefined,
    timeout_ms: Number(form.timeout_ms) || 30000,
    optional: Boolean(form.optional),
    notes: form.notes || undefined,
    budget_ms: (form.budget_ms !== undefined && form.budget_ms !== '' && form.budget_ms !== null) ? Number(form.budget_ms) : undefined,
    warn_ms: (form.warn_ms !== undefined && form.warn_ms !== '' && form.warn_ms !== null) ? Number(form.warn_ms) : undefined,
    metric_name: form.metric_name || undefined,
    approve_baseline: form.approve_baseline === undefined ? undefined : Boolean(form.approve_baseline),
  };
}

export function getStepValidationErrors(form: Record<string, any>): string[] {
  const errs: string[] = [];
  if (form.target && String(form.target).length > 500) errs.push('Selector/Target length cannot exceed 500 characters.');
  if (form.value && String(form.value).length > 1000) errs.push('Value length cannot exceed 1000 characters.');
  if (form.url && String(form.url).length > 2000) errs.push('URL length cannot exceed 2000 characters.');
  if ((Number(form.timeout_ms) || 0) <= 0) errs.push('Timeout must be greater than 0.');
  if (Number(form.timeout_ms) > 300000) errs.push('Timeout cannot exceed 300000 ms (5 minutes).');
  if (form.budget_ms !== undefined && form.budget_ms !== '' && form.budget_ms !== null) {
    const bNum = Number(form.budget_ms);
    if (isA11yAction(form.action_type)) {
      if (bNum < 0) errs.push('Budget (violations) cannot be negative.');
    } else {
      if (bNum <= 0) errs.push('Budget (ms) must be a positive number.');
    }
  }
  if (isApiRequestAction(form.action_type)) {
    if (!HTTP_METHODS.includes(String(form.method || '').toUpperCase())) errs.push('HTTP method must be one of GET, POST, PUT, PATCH, DELETE.');
    if (!String(form.url || '').trim()) errs.push('API URL required.');
  }
  if (isStatusAssertAction(form.action_type) && !Number.isFinite(Number(form.expected_status))) {
    errs.push('Expected status must be a valid number.');
  }
  if (isJsonPathAction(form.action_type) && !String(form.expected_json_path || '').trim()) {
    errs.push('JSON path is required for JSON path assertions.');
  }
  if (isHeaderAssertAction(form.action_type) && !String(form.target || '').trim()) {
    errs.push('Header name is required for header assertions.');
  }
  try { safeParseJson(form.headers_text || '', 'Headers JSON'); } catch (err) { errs.push(String((err as Error).message)); }
  try { safeParseJson(form.query_params_text || '', 'Query Params JSON'); } catch (err) { errs.push(String((err as Error).message)); }
  try { safeParseJson(form.body_json_text || '', 'Body JSON'); } catch (err) { errs.push(String((err as Error).message)); }
  return errs;
}

function TestCaseRow({
  tc,
  expanded,
  onToggle,
  onRefresh,
  packId,
}: {
  tc: TestCase;
  expanded: boolean;
  onToggle: () => void;
  onRefresh: () => void;
  packId: string;
}) {
  const dimmed = !tc.enabled;
  const containsPreview = testCaseContainsPreview(tc);
  const [editingStepId, setEditingStepId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Record<string, any>>({});
  const [isAdding, setIsAdding] = useState(false);
  const [rationaleExpanded, setRationaleExpanded] = useState(false);
  const [newForm, setNewForm] = useState<Record<string, any>>({
    action_type: 'navigate',
    target: '',
    value: '',
    expected: '',
    method: 'GET',
    url: '',
    headers_text: '',
    query_params_text: '',
    body_json_text: '',
    expected_status: 200,
    expected_json_path: '',
    expected_value: '',
    timeout_ms: 30000,
    optional: false,
    notes: '',
    budget_ms: '',
    warn_ms: '',
    metric_name: '',
    approve_baseline: false,
  });

  const handleToggleEnabled = async () => {
    if (containsPreview) return;
    try {
      await updateTestCase(packId, tc.test_case_id, { enabled: !tc.enabled });
      onRefresh();
    } catch (err) {
      alert(String(err));
    }
  };

  const handleDuplicate = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (containsPreview) return;
    try {
      await duplicateTestCase(tc.test_case_id);
      onRefresh();
    } catch (err) {
      alert(String(err));
    }
  };

  const handleDeleteCase = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (containsPreview) return;
    if (!window.confirm(`Delete test case "${tc.title}"?`)) return;
    try {
      await deleteTestCase(packId, tc.test_case_id);
      onRefresh();
    } catch (err) {
      alert(String(err));
    }
  };

  const startEditStep = (step: TestCaseStep) => {
    if (containsPreview) return;
    setEditingStepId(step.step_id);
    setEditForm({
      ...step,
      headers_text: step.headers ? JSON.stringify(step.headers, null, 2) : '',
      query_params_text: step.query_params ? JSON.stringify(step.query_params, null, 2) : '',
      body_json_text: step.body_json ? JSON.stringify(step.body_json, null, 2) : '',
      expected_status: step.expected_status ?? '',
      expected_json_path: step.expected_json_path ?? '',
      expected_value: step.expected_value ?? '',
      budget_ms: step.budget_ms ?? '',
      warn_ms: step.warn_ms ?? '',
      metric_name: step.metric_name ?? '',
      approve_baseline: step.approve_baseline ?? false,
    });
  };

  const handleSaveNewStep = async () => {
    try {
      const errors = getStepValidationErrors(newForm);
      if (errors.length > 0) {
        alert(errors[0]);
        return;
      }
      await addTestCaseStep(tc.test_case_id, normalizeStepPayload(newForm) as TestCaseStepCreate);
      setIsAdding(false);
      setNewForm({
        action_type: 'navigate',
        target: '',
        value: '',
        expected: '',
        method: 'GET',
        url: '',
        headers_text: '',
        query_params_text: '',
        body_json_text: '',
        expected_status: 200,
        expected_json_path: '',
        expected_value: '',
        timeout_ms: 30000,
        optional: false,
        notes: '',
        budget_ms: '',
        warn_ms: '',
        metric_name: '',
        approve_baseline: false,
      });
      onRefresh();
    } catch (err) {
      alert(String(err));
    }
  };

  const handleSaveEditStep = async (stepId: string) => {
    try {
      const errors = getStepValidationErrors(editForm);
      if (errors.length > 0) {
        alert(errors[0]);
        return;
      }
      await updateTestCaseStep(stepId, normalizeStepPayload(editForm));
      setEditingStepId(null);
      onRefresh();
    } catch (err) {
      alert(String(err));
    }
  };

  const handleDeleteStep = async (stepId: string) => {
    if (containsPreview) return;
    if (!window.confirm("Delete this step?")) return;
    try {
      await deleteTestCaseStep(stepId);
      onRefresh();
    } catch (err) {
      alert(String(err));
    }
  };

  const handleMoveStep = async (index: number, direction: 'up' | 'down') => {
    if (containsPreview) return;
    const stepsList = [...(tc.test_steps || [])].sort((a, b) => a.step_order - b.step_order);
    if (direction === 'up' && index === 0) return;
    if (direction === 'down' && index === stepsList.length - 1) return;

    const swapIdx = direction === 'up' ? index - 1 : index + 1;
    const temp = stepsList[index];
    stepsList[index] = stepsList[swapIdx];
    stepsList[swapIdx] = temp;

    const ids = stepsList.map(s => s.step_id);
    try {
      await reorderTestCaseSteps(tc.test_case_id, ids);
      onRefresh();
    } catch (err) {
      alert(String(err));
    }
  };

  return (
    <div style={{
      borderBottom: `1px solid ${P.border}`,
      opacity: dimmed ? 0.6 : 1,
    }}>
      {/* Summary row */}
      <div
        onClick={onToggle}
        data-testid={`test-case-row-${tc.test_case_id}`}
        style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 14px', cursor: 'pointer',
          transition: 'background 0.1s',
        }}
        onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = P.cardHi}
        onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'transparent'}
      >
        <span style={{ color: P.textFaint, flexShrink: 0 }}>
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>

        {/* Enabled checkbox */}
        <input
          type="checkbox"
          checked={tc.enabled}
          disabled={containsPreview}
          title={containsPreview ? PREVIEW_TOOLTIP : undefined}
          onClick={e => e.stopPropagation()}
          onChange={handleToggleEnabled}
          style={{ cursor: 'pointer' }}
        />

        {/* Priority pill */}
        <span style={{
          fontSize: 9, fontWeight: 700, fontFamily: F.mono,
          color: tc.priority === 'P0' ? P.fail : tc.priority === 'P1' ? P.unclear : P.textMute,
          minWidth: 20,
        }}>
          {tc.priority}
        </span>

        {/* Title */}
        <span style={{ flex: 1, fontSize: 12, color: P.textDim, minWidth: 0,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {tc.title}
        </span>

        {/* Flow */}
        {tc.flow_name && (
          <span style={{ fontSize: 10, color: P.textFaint, fontFamily: F.mono }}>
            {tc.flow_name}
          </span>
        )}

        <TypeBadge type={tc.test_type} />
        {containsPreview && <PreviewBadge />}
        <SafetyBadge level={tc.safety_level} />
        <AutoBadge status={tc.automation_status} />

        {tc.confidence !== undefined && (
          <span
            data-testid="ai-sparkles-badge"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 3,
              fontSize: 9, fontWeight: 700, fontFamily: F.mono,
              background: '#a78bfa18', border: `1px solid #a78bfa33`, borderRadius: 4,
              padding: '2px 5px', color: '#a78bfa',
            }}
          >
            <Sparkles size={10} /> AI
          </span>
        )}
        {tc.generation_source === 'local_fallback' && (
          <span
            data-testid="local-fallback-badge"
            style={{
              fontSize: 9, fontWeight: 700, fontFamily: F.mono,
              background: `${P.unclear}18`, border: `1px solid ${P.unclear}33`, borderRadius: 4,
              padding: '2px 5px', color: P.unclear, textTransform: 'uppercase',
            }}
          >
            local fallback
          </span>
        )}

        {/* Duplicate & Delete Case Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginLeft: 8 }}>
          <button
            onClick={handleDuplicate}
            disabled={containsPreview}
            title={containsPreview ? PREVIEW_TOOLTIP : 'Duplicate Test Case'}
            style={{
              background: 'transparent', border: 'none', cursor: 'pointer',
              color: P.textDim, padding: 4, borderRadius: 4, display: 'flex', alignItems: 'center',
            }}
            onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = P.cardHi}
            onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'transparent'}
          >
            <Copy size={11} />
          </button>
          <button
            onClick={handleDeleteCase}
            disabled={containsPreview}
            title={containsPreview ? PREVIEW_TOOLTIP : 'Delete Test Case'}
            style={{
              background: 'transparent', border: 'none', cursor: 'pointer',
              color: P.fail, padding: 4, borderRadius: 4, display: 'flex', alignItems: 'center',
            }}
            onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = P.cardHi}
            onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'transparent'}
          >
            <Trash2 size={11} />
          </button>
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div
          data-testid={`test-case-detail-${tc.test_case_id}`}
          style={{
            padding: '0 14px 14px 36px',
            display: 'flex', flexDirection: 'column', gap: 12,
          }}
        >
          {tc.description && (
            <div style={{ fontSize: 12, color: P.textDim }}>{tc.description}</div>
          )}

          {tc.confidence !== undefined && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: P.textDim }}>
              <span style={{ fontWeight: 600, color: P.textMute }}>AI Confidence:</span>
              <span style={{
                color: tc.confidence >= 0.8 ? P.pass : tc.confidence >= 0.5 ? P.unclear : P.fail,
                fontWeight: 'bold'
              }}>
                {Math.round(tc.confidence * 100)}%
              </span>
            </div>
          )}
          {tc.rationale && (
            <div style={{
              fontSize: 11, background: `${P.border}15`, border: `1px solid ${P.border}`,
              borderRadius: 6, padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 4
            }}>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setRationaleExpanded(!rationaleExpanded);
                }}
                style={{
                  background: 'none', border: 'none', color: P.accent, cursor: 'pointer',
                  fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4, padding: 0,
                  fontSize: 11, textAlign: 'left'
                }}
              >
                {rationaleExpanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                AI Rationale
              </button>
              {rationaleExpanded && (
                <div style={{ color: P.textDim, marginTop: 4, whiteSpace: 'pre-wrap', lineHeight: '1.4' }}>
                  {tc.rationale}
                </div>
              )}
            </div>
          )}

          {tc.preconditions.length > 0 && (
            <Section label="Preconditions">
              <ul style={{ margin: 0, paddingLeft: 16 }}>
                {tc.preconditions.map((p, i) => (
                  <li key={i} style={{ fontSize: 11, color: P.textDim, marginBottom: 2 }}>{p}</li>
                ))}
              </ul>
            </Section>
          )}

          {/* Interactive Steps Editor */}
          <Section label="Execution Steps">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
              {(!tc.test_steps || tc.test_steps.length === 0) ? (
                <div style={{ fontSize: 11, color: P.textMute, fontStyle: 'italic', padding: '4px 0' }}>
                  No structured steps defined yet.
                </div>
              ) : (
                [...tc.test_steps].sort((a, b) => a.step_order - b.step_order).map((step, idx, arr) => {
                  const isEditing = editingStepId === step.step_id;
                  const previewStep = isPreviewStep(step);
                  return (
                    <div key={step.step_id} style={{
                      padding: 10, borderRadius: 6, background: P.cardHi,
                      border: `1px solid ${P.border}`, display: 'flex', flexDirection: 'column', gap: 8,
                    }}>
                      {isEditing ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                            <div>
                              <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>ACTION TYPE</label>
                              <select
                                value={editForm.action_type || ''}
                                onChange={e => {
                                  const act = e.target.value;
                                  setEditForm(prev => ({ ...prev, action_type: act }));
                                }}
                                style={{
                                  width: '100%', background: P.card, border: `1px solid ${P.border}`,
                                  borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                                }}
                              >
                                {ACTION_TYPES.map(at => <option key={at} value={at}>{at}</option>)}
                              </select>
                            </div>
                            <div>
                              <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>TIMEOUT (MS)</label>
                              <input
                                type="number"
                                min={1}
                                max={300000}
                                aria-label="Edit step timeout in milliseconds"
                                value={editForm.timeout_ms ?? 30000}
                                onChange={e => setEditForm(prev => ({ ...prev, timeout_ms: Number(e.target.value) }))}
                                style={{
                                  width: '100%', background: P.card, border: `1px solid ${P.border}`,
                                  borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                                }}
                              />
                              <div style={{ fontSize: 9, color: P.textMute, marginTop: 3 }}>1–300000 ms · default 30000 ms</div>
                            </div>
                          </div>

                          {isApiRequestAction(editForm.action_type || '') && (
                            <>
                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                                <div>
                                  <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>HTTP METHOD</label>
                                  <select
                                    value={editForm.method || 'GET'}
                                    onChange={e => setEditForm(prev => ({ ...prev, method: e.target.value }))}
                                    style={{ width: '100%', background: P.card, border: `1px solid ${P.border}`, borderRadius: 4, padding: 4, color: P.text, fontSize: 11 }}
                                  >
                                    {HTTP_METHODS.map(method => <option key={method} value={method}>{method}</option>)}
                                  </select>
                                </div>
                                <div>
                                  <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>REQUEST URL</label>
                                  <input
                                    type="text"
                                    value={editForm.url || ''}
                                    onChange={e => setEditForm(prev => ({ ...prev, url: e.target.value }))}
                                    style={{ width: '100%', background: P.card, border: `1px solid ${P.border}`, borderRadius: 4, padding: 4, color: P.text, fontSize: 11 }}
                                  />
                                </div>
                              </div>
                              <div>
                                <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>HEADERS JSON</label>
                                <textarea value={editForm.headers_text || ''} onChange={e => setEditForm(prev => ({ ...prev, headers_text: e.target.value }))} rows={3} style={{ width: '100%', background: P.card, border: `1px solid ${P.border}`, borderRadius: 4, padding: 4, color: P.text, fontSize: 11, fontFamily: F.mono }} />
                              </div>
                              <div>
                                <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>QUERY PARAMS JSON</label>
                                <textarea value={editForm.query_params_text || ''} onChange={e => setEditForm(prev => ({ ...prev, query_params_text: e.target.value }))} rows={3} style={{ width: '100%', background: P.card, border: `1px solid ${P.border}`, borderRadius: 4, padding: 4, color: P.text, fontSize: 11, fontFamily: F.mono }} />
                              </div>
                              <div>
                                <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>BODY JSON</label>
                                <textarea value={editForm.body_json_text || ''} onChange={e => setEditForm(prev => ({ ...prev, body_json_text: e.target.value }))} rows={4} style={{ width: '100%', background: P.card, border: `1px solid ${P.border}`, borderRadius: 4, padding: 4, color: P.text, fontSize: 11, fontFamily: F.mono }} />
                              </div>
                            </>
                          )}

                          {isTargetNeeded(editForm.action_type || '') && (
                            <div>
                              <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>
                                {isHeaderAssertAction(editForm.action_type || '') ? 'HEADER NAME' : (['navigate', 'check_accessibility', 'assert_accessibility', 'accessibility_scan', 'assert_no_critical_a11y_violations', 'assert_no_a11y_violations'].includes(editForm.action_type || '') || isSecurityAction(editForm.action_type || '')) ? 'URL / PATH (OPTIONAL)' : isVisualAction(editForm.action_type || '') ? 'CSS SELECTOR (OPTIONAL)' : 'SELECTOR'}
                              </label>
                              <input
                                type="text"
                                value={editForm.target || ''}
                                onChange={e => setEditForm(prev => ({ ...prev, target: e.target.value }))}
                                style={{
                                  width: '100%', background: P.card, border: `1px solid ${P.border}`,
                                  borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                                }}
                              />
                            </div>
                          )}

                          {isValueNeeded(editForm.action_type || '') && (
                            <div>
                              <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>
                                {isVisualAction(editForm.action_type || '') ? 'BASELINE KEY / NAME' : isSecurityAction(editForm.action_type || '') ? 'SEVERITY THRESHOLD (OPTIONAL)' : 'VALUE / KEY'}
                              </label>
                              <input
                                type="text"
                                value={editForm.value || ''}
                                onChange={e => setEditForm(prev => ({ ...prev, value: e.target.value }))}
                                style={{
                                  width: '100%', background: P.card, border: `1px solid ${P.border}`,
                                  borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                                }}
                              />
                            </div>
                          )}

                          {isExpectedNeeded(editForm.action_type || '') && (
                            <div>
                              <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>
                                {isVisualAction(editForm.action_type || '') ? 'MAX DIFF THRESHOLD (0.01 - 1.00)' : isSecurityAction(editForm.action_type || '') ? 'EXPECTED HEADERS (COMMA SEPARATED)' : 'EXPECTED SUBSTRING'}
                              </label>
                              <input
                                type="text"
                                value={editForm.expected || ''}
                                onChange={e => setEditForm(prev => ({ ...prev, expected: e.target.value }))}
                                style={{
                                  width: '100%', background: P.card, border: `1px solid ${P.border}`,
                                  borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                                }}
                              />
                            </div>
                          )}

                          {isStatusAssertAction(editForm.action_type || '') && (
                            <div>
                              <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>EXPECTED STATUS</label>
                              <input type="number" value={editForm.expected_status || ''} onChange={e => setEditForm(prev => ({ ...prev, expected_status: e.target.value }))} style={{ width: '100%', background: P.card, border: `1px solid ${P.border}`, borderRadius: 4, padding: 4, color: P.text, fontSize: 11 }} />
                            </div>
                          )}

                          {isJsonPathAction(editForm.action_type || '') && (
                            <>
                              <div>
                                <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>JSON PATH</label>
                                <input type="text" value={editForm.expected_json_path || ''} onChange={e => setEditForm(prev => ({ ...prev, expected_json_path: e.target.value }))} style={{ width: '100%', background: P.card, border: `1px solid ${P.border}`, borderRadius: 4, padding: 4, color: P.text, fontSize: 11 }} />
                              </div>
                              <div>
                                <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>EXPECTED VALUE</label>
                                <input type="text" value={editForm.expected_value || ''} onChange={e => setEditForm(prev => ({ ...prev, expected_value: e.target.value }))} style={{ width: '100%', background: P.card, border: `1px solid ${P.border}`, borderRadius: 4, padding: 4, color: P.text, fontSize: 11 }} />
                              </div>
                            </>
                          )}

                          {(isHeaderAssertAction(editForm.action_type || '') || isBodyAssertAction(editForm.action_type || '') || isResponseTimeAssertAction(editForm.action_type || '')) && (
                            <div>
                              <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>
                                {isResponseTimeAssertAction(editForm.action_type || '') ? 'MAX RESPONSE TIME (MS)' : 'EXPECTED VALUE'}
                              </label>
                              <input type="text" value={editForm.expected_value || ''} onChange={e => setEditForm(prev => ({ ...prev, expected_value: e.target.value }))} style={{ width: '100%', background: P.card, border: `1px solid ${P.border}`, borderRadius: 4, padding: 4, color: P.text, fontSize: 11 }} />
                            </div>
                          )}

                          {isPerformanceAction(editForm.action_type || '') && (
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                              <div>
                                <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>BUDGET (MS)</label>
                                <input
                                  type="number"
                                  placeholder="e.g. 1500"
                                  value={editForm.budget_ms || ''}
                                  onChange={e => setEditForm(prev => ({ ...prev, budget_ms: e.target.value }))}
                                  style={{
                                    width: '100%', background: P.card, border: `1px solid ${P.border}`,
                                    borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                                  }}
                                />
                              </div>
                              <div>
                                <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>WARN (MS)</label>
                                <input
                                  type="number"
                                  placeholder="e.g. 1000"
                                  value={editForm.warn_ms || ''}
                                  onChange={e => setEditForm(prev => ({ ...prev, warn_ms: e.target.value }))}
                                  style={{
                                    width: '100%', background: P.card, border: `1px solid ${P.border}`,
                                    borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                                  }}
                                />
                              </div>
                              <div>
                                <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>METRIC NAME</label>
                                <input
                                  type="text"
                                  placeholder="e.g. home_load"
                                  value={editForm.metric_name || ''}
                                  onChange={e => setEditForm(prev => ({ ...prev, metric_name: e.target.value }))}
                                  style={{
                                    width: '100%', background: P.card, border: `1px solid ${P.border}`,
                                    borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                                  }}
                                />
                              </div>
                            </div>
                          )}

                          {isA11yAction(editForm.action_type || '') && (
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                              <div>
                                <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>BUDGET (MAX VIOLATIONS)</label>
                                <input
                                  type="number"
                                  placeholder="e.g. 0"
                                  value={editForm.budget_ms === undefined || editForm.budget_ms === null ? '' : editForm.budget_ms}
                                  onChange={e => setEditForm(prev => ({ ...prev, budget_ms: e.target.value }))}
                                  style={{
                                    width: '100%', background: P.card, border: `1px solid ${P.border}`,
                                    borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                                  }}
                                />
                              </div>
                              <div>
                                <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>WARN (VIOLATIONS)</label>
                                <input
                                  type="number"
                                  placeholder="e.g. 0"
                                  value={editForm.warn_ms === undefined || editForm.warn_ms === null ? '' : editForm.warn_ms}
                                  onChange={e => setEditForm(prev => ({ ...prev, warn_ms: e.target.value }))}
                                  style={{
                                    width: '100%', background: P.card, border: `1px solid ${P.border}`,
                                    borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                                  }}
                                />
                              </div>
                            </div>
                          )}

                          <div>
                            <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>NOTES</label>
                            <input
                              type="text"
                              value={editForm.notes || ''}
                              onChange={e => setEditForm(prev => ({ ...prev, notes: e.target.value }))}
                              style={{
                                width: '100%', background: P.card, border: `1px solid ${P.border}`,
                                borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                              }}
                            />
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: P.textDim, cursor: 'pointer' }}>
                              <input
                                type="checkbox"
                                checked={editForm.optional || false}
                                onChange={e => setEditForm(prev => ({ ...prev, optional: e.target.checked }))}
                              />
                              Optional step (do not abort run on failure)
                            </label>
                          </div>

                          {editForm.action_type === 'visual_capture' && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                              <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: P.textDim, cursor: 'pointer' }}>
                                <input
                                  type="checkbox"
                                  checked={editForm.approve_baseline || false}
                                  onChange={e => setEditForm(prev => ({ ...prev, approve_baseline: e.target.checked }))}
                                />
                                Approve baseline immediately
                              </label>
                            </div>
                          )}

                          {getStepValidationErrors(editForm).length > 0 && (
                            <div style={{ fontSize: 10, color: P.fail }}>
                              {getStepValidationErrors(editForm)[0]}
                            </div>
                          )}

                          <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                            <Btn size="sm" variant="ghost" onClick={() => setEditingStepId(null)}>
                              Cancel
                            </Btn>
                            <Btn size="sm" variant="primary" onClick={() => handleSaveEditStep(step.step_id)}>
                              Save
                            </Btn>
                          </div>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                              <span style={{ fontSize: 11, fontWeight: 600, color: P.textFaint, fontFamily: F.mono }}>
                                #{idx + 1}
                              </span>
                              <span style={{
                                fontSize: 9, fontWeight: 700, letterSpacing: '0.04em', fontFamily: F.mono,
                                background: `${P.accent}18`, border: `1px solid ${P.accent}33`, borderRadius: 4,
                                padding: '1px 4px', color: P.accent, textTransform: 'uppercase'
                              }}>
                                {step.action_type}
                              </span>
                              {previewStep && <PreviewBadge />}
                              {step.optional && (
                                <span style={{
                                  fontSize: 8, fontWeight: 700, background: `${P.unclear}18`,
                                  color: P.unclear, border: `1px solid ${P.unclear}33`, borderRadius: 3, padding: '1px 3px'
                                }}>
                                  OPTIONAL
                                </span>
                              )}
                            </div>

                            <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginTop: 4 }}>
                              {step.target && (
                                <div style={{ fontSize: 11, color: P.textDim }}>
                                  <span style={{ color: P.textMute, fontFamily: F.mono, fontSize: 9 }}>target:</span>{' '}
                                  <code style={{ fontFamily: F.mono }}>{step.target}</code>
                                </div>
                              )}
                              {step.method && (
                                <div style={{ fontSize: 11, color: P.textDim }}>
                                  <span style={{ color: P.textMute, fontFamily: F.mono, fontSize: 9 }}>method:</span>{' '}
                                  <code style={{ fontFamily: F.mono }}>{step.method}</code>
                                </div>
                              )}
                              {step.url && (
                                <div style={{ fontSize: 11, color: P.textDim }}>
                                  <span style={{ color: P.textMute, fontFamily: F.mono, fontSize: 9 }}>url:</span>{' '}
                                  <code style={{ fontFamily: F.mono }}>{step.url}</code>
                                </div>
                              )}
                              {step.value && (
                                <div style={{ fontSize: 11, color: P.textDim }}>
                                  <span style={{ color: P.textMute, fontFamily: F.mono, fontSize: 9 }}>
                                    {isSecurityAction(step.action_type) ? 'severity_threshold:' : 'value:'}
                                  </span>{' '}
                                  <code style={{ fontFamily: F.mono }}>{step.value}</code>
                                </div>
                              )}
                              {step.expected_status !== undefined && (
                                <div style={{ fontSize: 11, color: P.textDim }}>
                                  <span style={{ color: P.textMute, fontFamily: F.mono, fontSize: 9 }}>expected_status:</span>{' '}
                                  <code style={{ fontFamily: F.mono }}>{step.expected_status}</code>
                                </div>
                              )}
                              {step.expected && (
                                <div style={{ fontSize: 11, color: P.textDim }}>
                                  <span style={{ color: P.textMute, fontFamily: F.mono, fontSize: 9 }}>
                                    {isSecurityAction(step.action_type) ? 'expected_headers:' : 'expected:'}
                                  </span>{' '}
                                  <code style={{ fontFamily: F.mono }}>{step.expected}</code>
                                </div>
                              )}
                              {step.budget_ms !== undefined && step.budget_ms !== null && (
                                <div style={{ fontSize: 11, color: P.textDim }}>
                                  <span style={{ color: P.textMute, fontFamily: F.mono, fontSize: 9 }}>
                                    {isA11yAction(step.action_type) ? 'max_violations:' : 'budget_ms:'}
                                  </span>{' '}
                                  <code style={{ fontFamily: F.mono }}>{step.budget_ms}</code>
                                </div>
                              )}
                              {step.warn_ms !== undefined && step.warn_ms !== null && (
                                <div style={{ fontSize: 11, color: P.textDim }}>
                                  <span style={{ color: P.textMute, fontFamily: F.mono, fontSize: 9 }}>
                                    {isA11yAction(step.action_type) ? 'warn_violations:' : 'warn_ms:'}
                                  </span>{' '}
                                  <code style={{ fontFamily: F.mono }}>{step.warn_ms}</code>
                                </div>
                              )}
                              {step.metric_name && (
                                <div style={{ fontSize: 11, color: P.textDim }}>
                                  <span style={{ color: P.textMute, fontFamily: F.mono, fontSize: 9 }}>metric_name:</span>{' '}
                                  <code style={{ fontFamily: F.mono }}>{step.metric_name}</code>
                                </div>
                              )}
                              {step.notes && (
                                <div style={{ fontSize: 11, color: P.textMute, fontStyle: 'italic' }}>
                                  {step.notes}
                                </div>
                              )}
                            </div>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                            <button
                              disabled={idx === 0 || containsPreview}
                              title={containsPreview ? PREVIEW_TOOLTIP : 'Move step up'}
                              onClick={() => handleMoveStep(idx, 'up')}
                              style={{
                                background: 'transparent', border: 'none', cursor: idx === 0 ? 'not-allowed' : 'pointer',
                                color: idx === 0 ? P.textFaint : P.textDim, padding: 2,
                              }}
                            >
                              <ArrowUp size={12} />
                            </button>
                            <button
                              disabled={idx === arr.length - 1 || containsPreview}
                              title={containsPreview ? PREVIEW_TOOLTIP : 'Move step down'}
                              onClick={() => handleMoveStep(idx, 'down')}
                              style={{
                                background: 'transparent', border: 'none', cursor: idx === arr.length - 1 ? 'not-allowed' : 'pointer',
                                color: idx === arr.length - 1 ? P.textFaint : P.textDim, padding: 2,
                              }}
                            >
                              <ArrowDown size={12} />
                            </button>

                            <button
                              disabled={containsPreview}
                              title={containsPreview ? PREVIEW_TOOLTIP : 'Edit step'}
                              onClick={() => startEditStep(step)}
                              style={{
                                background: 'transparent', border: 'none', cursor: 'pointer',
                                color: P.textDim, padding: 2, marginLeft: 4,
                              }}
                            >
                              <Edit2 size={12} />
                            </button>
                            <button
                              disabled={containsPreview}
                              title={containsPreview ? PREVIEW_TOOLTIP : 'Delete step'}
                              onClick={() => handleDeleteStep(step.step_id)}
                              style={{
                                background: 'transparent', border: 'none', cursor: 'pointer',
                                color: P.fail, padding: 2,
                              }}
                            >
                              <Trash2 size={12} />
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })
              )}

              {isAdding ? (
                <div style={{
                  padding: 10, borderRadius: 6, background: P.card,
                  border: `1px solid ${P.accent}44`, display: 'flex', flexDirection: 'column', gap: 8,
                }}>
                  <div style={{ fontSize: 10, fontWeight: 600, color: P.accent, fontFamily: F.mono }}>
                    ADD NEW STEP
                  </div>

                  <CapabilityTypeSelector
                    actionType={newForm.action_type}
                    onSelectAction={action_type => setNewForm(prev => ({ ...prev, action_type }))}
                  />

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    <div>
                      <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>ACTION TYPE</label>
                      <select
                        value={newForm.action_type || 'navigate'}
                        onChange={e => setNewForm(prev => ({ ...prev, action_type: e.target.value }))}
                        style={{
                          width: '100%', background: P.card, border: `1px solid ${P.border}`,
                          borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                        }}
                      >
                        {ACTION_TYPES.map(at => <option key={at} value={at}>{at}</option>)}
                      </select>
                    </div>
                    <div>
                      <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>TIMEOUT (MS)</label>
                      <input
                        type="number"
                        min={1}
                        max={300000}
                        aria-label="New step timeout in milliseconds"
                        value={newForm.timeout_ms ?? 30000}
                        onChange={e => setNewForm(prev => ({ ...prev, timeout_ms: Number(e.target.value) }))}
                        style={{
                          width: '100%', background: P.card, border: `1px solid ${P.border}`,
                          borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                        }}
                      />
                      <div style={{ fontSize: 9, color: P.textMute, marginTop: 3 }}>1–300000 ms · default 30000 ms</div>
                    </div>
                  </div>

                  {isApiRequestAction(newForm.action_type || 'navigate') && (
                    <>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                        <div>
                          <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>HTTP METHOD</label>
                          <select
                            value={newForm.method || 'GET'}
                            onChange={e => setNewForm(prev => ({ ...prev, method: e.target.value }))}
                            style={{
                              width: '100%', background: P.card, border: `1px solid ${P.border}`,
                              borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                            }}
                          >
                            {HTTP_METHODS.map(method => <option key={method} value={method}>{method}</option>)}
                          </select>
                        </div>
                        <div>
                          <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>REQUEST URL</label>
                          <input
                            type="text"
                            placeholder="http://127.0.0.1:8765/api/health"
                            value={newForm.url || ''}
                            onChange={e => setNewForm(prev => ({ ...prev, url: e.target.value }))}
                            style={{
                              width: '100%', background: P.card, border: `1px solid ${P.border}`,
                              borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                            }}
                          />
                        </div>
                      </div>
                      <div>
                        <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>HEADERS JSON</label>
                        <textarea
                          value={newForm.headers_text || ''}
                          onChange={e => setNewForm(prev => ({ ...prev, headers_text: e.target.value }))}
                          rows={3}
                          style={{
                            width: '100%', background: P.card, border: `1px solid ${P.border}`,
                            borderRadius: 4, padding: 4, color: P.text, fontSize: 11, fontFamily: F.mono,
                          }}
                        />
                      </div>
                      <div>
                        <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>QUERY PARAMS JSON</label>
                        <textarea
                          value={newForm.query_params_text || ''}
                          onChange={e => setNewForm(prev => ({ ...prev, query_params_text: e.target.value }))}
                          rows={3}
                          style={{
                            width: '100%', background: P.card, border: `1px solid ${P.border}`,
                            borderRadius: 4, padding: 4, color: P.text, fontSize: 11, fontFamily: F.mono,
                          }}
                        />
                      </div>
                      <div>
                        <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>BODY JSON</label>
                        <textarea
                          value={newForm.body_json_text || ''}
                          onChange={e => setNewForm(prev => ({ ...prev, body_json_text: e.target.value }))}
                          rows={4}
                          style={{
                            width: '100%', background: P.card, border: `1px solid ${P.border}`,
                            borderRadius: 4, padding: 4, color: P.text, fontSize: 11, fontFamily: F.mono,
                          }}
                        />
                      </div>
                    </>
                  )}

                  {isTargetNeeded(newForm.action_type || 'navigate') && (
                    <div>
                      <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>
                        {isHeaderAssertAction(newForm.action_type || 'navigate')
                          ? 'HEADER NAME'
                          : (['navigate', 'check_accessibility', 'assert_accessibility', 'accessibility_scan', 'assert_no_critical_a11y_violations', 'assert_no_a11y_violations'].includes(newForm.action_type || '') || isSecurityAction(newForm.action_type || '')) ? 'URL / PATH (OPTIONAL)' : isVisualAction(newForm.action_type || '') ? 'CSS SELECTOR (OPTIONAL)' : 'SELECTOR'}
                      </label>
                      <input
                        type="text"
                        placeholder={isHeaderAssertAction(newForm.action_type || 'navigate')
                          ? 'e.g. content-type'
                          : (['navigate', 'check_accessibility', 'assert_accessibility', 'accessibility_scan', 'assert_no_critical_a11y_violations', 'assert_no_a11y_violations'].includes(newForm.action_type || '') || isSecurityAction(newForm.action_type || '')) ? 'e.g. /login' : isVisualAction(newForm.action_type || '') ? 'e.g. #hero-section' : 'e.g. #submit-btn'}
                        value={newForm.target || ''}
                        onChange={e => setNewForm(prev => ({ ...prev, target: e.target.value }))}
                        style={{
                          width: '100%', background: P.card, border: `1px solid ${P.border}`,
                          borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                        }}
                      />
                    </div>
                  )}

                  {isValueNeeded(newForm.action_type || 'navigate') && (
                    <div>
                      <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>
                        {isVisualAction(newForm.action_type || '') ? 'BASELINE KEY / NAME' : isSecurityAction(newForm.action_type || '') ? 'SEVERITY THRESHOLD (OPTIONAL)' : 'VALUE / KEY'}
                      </label>
                      <input
                        type="text"
                        placeholder={isVisualAction(newForm.action_type || '') ? 'e.g. homepage_hero' : isSecurityAction(newForm.action_type || '') ? 'e.g. critical' : 'e.g. my-username'}
                        value={newForm.value || ''}
                        onChange={e => setNewForm(prev => ({ ...prev, value: e.target.value }))}
                        style={{
                          width: '100%', background: P.card, border: `1px solid ${P.border}`,
                          borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                        }}
                      />
                    </div>
                  )}

                  {isStatusAssertAction(newForm.action_type || 'navigate') && (
                    <div>
                      <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>EXPECTED STATUS</label>
                      <input
                        type="number"
                        value={newForm.expected_status || ''}
                        onChange={e => setNewForm(prev => ({ ...prev, expected_status: e.target.value }))}
                        style={{
                          width: '100%', background: P.card, border: `1px solid ${P.border}`,
                          borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                        }}
                      />
                    </div>
                  )}

                  {isJsonPathAction(newForm.action_type || 'navigate') && (
                    <>
                      <div>
                        <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>JSON PATH</label>
                        <input
                          type="text"
                          placeholder="e.g. status"
                          value={newForm.expected_json_path || ''}
                          onChange={e => setNewForm(prev => ({ ...prev, expected_json_path: e.target.value }))}
                          style={{
                            width: '100%', background: P.card, border: `1px solid ${P.border}`,
                            borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                          }}
                        />
                      </div>
                      <div>
                        <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>EXPECTED VALUE</label>
                        <input
                          type="text"
                          placeholder="e.g. ok"
                          value={newForm.expected_value || ''}
                          onChange={e => setNewForm(prev => ({ ...prev, expected_value: e.target.value }))}
                          style={{
                            width: '100%', background: P.card, border: `1px solid ${P.border}`,
                            borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                          }}
                        />
                      </div>
                    </>
                  )}

                  {(isHeaderAssertAction(newForm.action_type || 'navigate') || isBodyAssertAction(newForm.action_type || 'navigate') || isResponseTimeAssertAction(newForm.action_type || 'navigate')) && (
                    <div>
                      <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>
                        {isResponseTimeAssertAction(newForm.action_type || 'navigate') ? 'MAX RESPONSE TIME (MS)' : 'EXPECTED VALUE'}
                      </label>
                      <input
                        type="text"
                        placeholder={isResponseTimeAssertAction(newForm.action_type || 'navigate') ? 'e.g. 500' : 'e.g. application/json'}
                        onChange={e => setNewForm(prev => ({ ...prev, expected_value: e.target.value }))}
                        style={{
                          width: '100%', background: P.card, border: `1px solid ${P.border}`,
                          borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                        }}
                      />
                    </div>
                  )}

                  {isExpectedNeeded(newForm.action_type || 'navigate') && (
                    <div>
                      <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>
                        {isVisualAction(newForm.action_type || '') ? 'MAX DIFF THRESHOLD (0.01 - 1.00)' : isSecurityAction(newForm.action_type || '') ? 'EXPECTED HEADERS (COMMA SEPARATED)' : 'EXPECTED SUBSTRING'}
                      </label>
                      <input
                        type="text"
                        placeholder={isVisualAction(newForm.action_type || '') ? 'e.g. 0.05' : isSecurityAction(newForm.action_type || '') ? 'e.g. Content-Security-Policy' : 'e.g. Welcome back'}
                        value={newForm.expected || ''}
                        onChange={e => setNewForm(prev => ({ ...prev, expected: e.target.value }))}
                        style={{
                          width: '100%', background: P.card, border: `1px solid ${P.border}`,
                          borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                        }}
                      />
                    </div>
                  )}

                  {getStepValidationErrors(newForm).length > 0 && (
                    <div style={{ fontSize: 10, color: P.fail }}>
                      {getStepValidationErrors(newForm)[0]}
                    </div>
                  )}

                  {isPerformanceAction(newForm.action_type || 'navigate') && (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                      <div>
                        <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>BUDGET (MS)</label>
                        <input
                          type="number"
                          placeholder="e.g. 1500"
                          value={newForm.budget_ms || ''}
                          onChange={e => setNewForm(prev => ({ ...prev, budget_ms: e.target.value }))}
                          style={{
                            width: '100%', background: P.card, border: `1px solid ${P.border}`,
                            borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                          }}
                        />
                      </div>
                      <div>
                        <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>WARN (MS)</label>
                        <input
                          type="number"
                          placeholder="e.g. 1000"
                          value={newForm.warn_ms || ''}
                          onChange={e => setNewForm(prev => ({ ...prev, warn_ms: e.target.value }))}
                          style={{
                            width: '100%', background: P.card, border: `1px solid ${P.border}`,
                            borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                          }}
                        />
                      </div>
                      <div>
                        <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>METRIC NAME</label>
                        <input
                          type="text"
                          placeholder="e.g. home_load"
                          value={newForm.metric_name || ''}
                          onChange={e => setNewForm(prev => ({ ...prev, metric_name: e.target.value }))}
                          style={{
                            width: '100%', background: P.card, border: `1px solid ${P.border}`,
                            borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                          }}
                        />
                      </div>
                    </div>
                  )}

                  {isA11yAction(newForm.action_type || 'navigate') && (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                      <div>
                        <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>BUDGET (MAX VIOLATIONS)</label>
                        <input
                          type="number"
                          placeholder="e.g. 0"
                          value={newForm.budget_ms === undefined || newForm.budget_ms === null ? '' : newForm.budget_ms}
                          onChange={e => setNewForm(prev => ({ ...prev, budget_ms: e.target.value }))}
                          style={{
                            width: '100%', background: P.card, border: `1px solid ${P.border}`,
                            borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                          }}
                        />
                      </div>
                      <div>
                        <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>WARN (VIOLATIONS)</label>
                        <input
                          type="number"
                          placeholder="e.g. 0"
                          value={newForm.warn_ms === undefined || newForm.warn_ms === null ? '' : newForm.warn_ms}
                          onChange={e => setNewForm(prev => ({ ...prev, warn_ms: e.target.value }))}
                          style={{
                            width: '100%', background: P.card, border: `1px solid ${P.border}`,
                            borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                          }}
                        />
                      </div>
                    </div>
                  )}

                  <div>
                    <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>NOTES</label>
                    <input
                      type="text"
                      placeholder="e.g. Wait for dashboard page to load"
                      value={newForm.notes || ''}
                      onChange={e => setNewForm(prev => ({ ...prev, notes: e.target.value }))}
                      style={{
                        width: '100%', background: P.card, border: `1px solid ${P.border}`,
                        borderRadius: 4, padding: 4, color: P.text, fontSize: 11,
                      }}
                    />
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: P.textDim, cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={newForm.optional || false}
                        onChange={e => setNewForm(prev => ({ ...prev, optional: e.target.checked }))}
                      />
                      Optional step (do not abort run on failure)
                    </label>
                  </div>

                  {newForm.action_type === 'visual_capture' && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: P.textDim, cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={newForm.approve_baseline || false}
                          onChange={e => setNewForm(prev => ({ ...prev, approve_baseline: e.target.checked }))}
                        />
                        Approve baseline immediately
                      </label>
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                    <Btn size="sm" variant="ghost" onClick={() => setIsAdding(false)}>
                      Cancel
                    </Btn>
                    <Btn size="sm" variant="primary" onClick={handleSaveNewStep}>
                      Add Step
                    </Btn>
                  </div>
                </div>
              ) : (
                <Btn
                  size="sm"
                  variant="ghost"
                  disabled={containsPreview}
                  title={containsPreview ? PREVIEW_TOOLTIP : undefined}
                  onClick={() => setIsAdding(true)}
                  style={{ alignSelf: 'flex-start' }}
                >
                  <Plus size={11} /> Add Step
                </Btn>
              )}
            </div>
          </Section>

          {tc.steps && tc.steps.length > 0 && (
            <Section label="Steps Reference">
              <ol style={{ margin: 0, paddingLeft: 16 }}>
                {tc.steps.map((s, i) => (
                  <li key={i} style={{ fontSize: 11, color: P.textDim, marginBottom: 2 }}>{s}</li>
                ))}
              </ol>
            </Section>
          )}

          {tc.expected_result && (
            <Section label="Expected result">
              <div style={{ fontSize: 11, color: P.textDim }}>{tc.expected_result}</div>
            </Section>
          )}

          {tc.expected_evidence.length > 0 && (
            <Section label="Expected evidence">
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {tc.expected_evidence.map((e, i) => (
                  <span key={i} style={{
                    fontSize: 10, padding: '2px 6px', borderRadius: 4,
                    background: P.accentSoft, color: P.accent, fontFamily: F.mono,
                  }}>{e}</span>
                ))}
              </div>
            </Section>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {tc.pass_criteria && (
              <Section label="Pass criteria">
                <div style={{ fontSize: 11, color: P.pass }}>{tc.pass_criteria}</div>
              </Section>
            )}
            {tc.fail_criteria && (
              <Section label="Fail criteria">
                <div style={{ fontSize: 11, color: P.fail }}>{tc.fail_criteria}</div>
              </Section>
            )}
          </div>

          {tc.requires_permission && (
            <div style={{ fontSize: 11, color: P.unclear, padding: '4px 8px',
              background: P.unclearSoft, borderRadius: 4, border: `1px solid ${P.unclear}33` }}>
              ⚠ Requires explicit permission before running
            </div>
          )}

          {tc.safety_level !== 'safe' && (
            <div style={{ fontSize: 11, color: SAFETY_COLOR[tc.safety_level] ?? P.fail,
              padding: '4px 8px', background: `${SAFETY_COLOR[tc.safety_level] ?? P.fail}12`,
              borderRadius: 4, border: `1px solid ${SAFETY_COLOR[tc.safety_level] ?? P.fail}33` }}>
              Safety: {tc.safety_level.replace(/_/g, ' ')}
              {tc.safety_level === 'destructive' && ' — disabled by default, requires approval'}
            </div>
          )}

          {tc.tags.length > 0 && (
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {tc.tags.map(tag => (
                <span key={tag} style={{
                  fontSize: 9, padding: '2px 5px', borderRadius: 3,
                  background: P.cardHi, color: P.textFaint, fontFamily: F.mono,
                }}>{tag}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 9, color: P.textFaint, fontFamily: F.mono,
        textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>{label}</div>
      {children}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function PackDetailPage() {
  const { packId } = useParams<{ packId: string }>();
  const nav = useWorkspaceNavigate();
  const [showRunModal, setShowRunModal] = useState(false);
  const [showManualRunModal, setShowManualRunModal] = useState(false);
  const [showRunReview, setShowRunReview] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const [testPlanTab, setTestPlanTab] = useState('all');
  const [expandedCaseId, setExpandedCaseId] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState('');
  const [aiGenerating, setAiGenerating] = useState(false);
  const [aiGenError, setAiGenError] = useState('');
  const [aiPreview, setAiPreview] = useState<AITestPlanPreview | null>(null);
  const [scheduleEnabled, setScheduleEnabled] = useState(false);
  const [scheduleUpdating, setScheduleUpdating] = useState(false);

  const handleGenerateAi = async () => {
    if (!packId) return;
    setAiGenerating(true);
    setAiGenError('');
    try {
      const preview = await generateAiTestPlan(packId, pack?.app_id ?? undefined);
      setAiPreview(preview);
    } catch (err) {
      setAiGenError(String(err instanceof Error ? err.message : err));
    } finally {
      setAiGenerating(false);
    }
  };

  const getPack = useCallback(() => get<BackendPack>(`/validation-packs/${packId}`), [packId]);
  const getRuns = useCallback(() => get<LiveRunRecord[]>(`/runs?pack_id=${packId}&limit=20`), [packId]);
  const getTestPlanFn = useCallback(() => getTestPlan(packId!), [packId]);
  const getTestCasesFn = useCallback(() => listTestCases(packId!), [packId]);
  const getAppsFn = useCallback(() => get<Array<{ id: string; app_type: string }>>('/apps'), []);

  const { data: pack, loading: packLoading, error: packError, refetch: refetchPack, isOffline } =
    useApi(getPack, {
      demo: workspace => {
        const sample = workspace.validationPacks.find(item => item.id === packId);
        if (!sample) return null as unknown as BackendPack;
        return {
          ...sample,
          project_id: sample.project_id ?? 'p1',
          steps: sample.steps ?? [],
          created_at: sample.created_at ?? '2026-01-15T12:00:00.000Z',
          updated_at: sample.updated_at ?? '2026-01-15T12:00:00.000Z',
        } as BackendPack;
      },
    });
  const { data: runs, loading: runsLoading, refetch: refetchRuns } = useApi(getRuns, {
    demo: workspace => workspace.liveRuns.filter(run => run.pack_id === packId),
  });
  const { data: testPlan, loading: planLoading, refetch: refetchPlan } = useApi(getTestPlanFn, {
    demo: null as unknown as TestPlan,
  });
  const { data: testCases, loading: casesLoading, error: casesError, refetch: refetchCases } = useApi(getTestCasesFn, {
    demo: [] as TestCase[],
  });
  const { data: apps, loading: appsLoading, error: appsError, refetch: refetchApps } = useApi(getAppsFn, { demo: workspace => workspace.apps });
  const targetAppIds = [pack?.app_id, ...(pack?.target_app_ids ?? [])].filter(Boolean);
  const targetNames = pack?.target_names ?? [];
  const hasTargetMetadata = targetAppIds.length > 0 || targetNames.length > 0;
  const linkedPreviewApp = (apps ?? []).some(app =>
    (targetAppIds.includes(app.id) || targetNames.includes((app as { name?: string }).name ?? ''))
    && isPreviewAppType(app.app_type)
  );
  const containsPreviewSteps = hasPreviewSteps(pack?.steps ?? [], testCases ?? [])
    || linkedPreviewApp;
  const runCheckInProgress = casesLoading || appsLoading;
  const runMetadataUnavailable = Boolean(casesError || (hasTargetMetadata && appsError))
    || testCases === null || (hasTargetMetadata && apps === null);
  const runBlocked = runCheckInProgress || runMetadataUnavailable || containsPreviewSteps;
  const runBlockTitle = containsPreviewSteps
    ? PREVIEW_RUN_TOOLTIP
    : runMetadataUnavailable
      ? 'Could not verify pack capabilities. Refresh to retry.'
      : runCheckInProgress
        ? 'Checking pack capabilities…'
        : undefined;

  useEffect(() => {
    if (containsPreviewSteps) {
      setShowRunModal(false);
      setShowManualRunModal(false);
      setShowRunReview(false);
    }
  }, [containsPreviewSteps]);

  useEffect(() => {
    if (pack) setScheduleEnabled(pack.schedule_enabled ?? false);
  }, [pack]);

  const handleDelete = async () => {
    if (!packId) return;
    if (!window.confirm(`Delete pack "${pack?.name}"? This cannot be undone.`)) return;
    setDeleting(true);
    setDeleteError('');
    try {
      await del(`/validation-packs/${packId}`);
      nav('/packs');
    } catch (err) {
      setDeleteError(String(err instanceof Error ? err.message : 'Delete failed'));
    } finally {
      setDeleting(false);
    }
  };

  const handleGenerate = async (force = false) => {
    if (!packId) return;
    setGenerating(true);
    setGenError('');
    try {
      // Pass pack.app_id so backend can load app_map for enrichment (GAP 9 fix)
      await generateTestPlan(packId, force, pack?.app_id ?? undefined);
      refetchPlan();
      refetchCases();
    } catch (err) {
      setGenError(String(err instanceof Error ? err.message : err));
    } finally {
      setGenerating(false);
    }
  };

  const handleRunClick = () => {
    if (runBlocked) return;
    const hasDangerous = (testCases ?? []).some(
      tc => tc.enabled && (tc.safety_level === 'destructive' || tc.safety_level === 'external_cost')
    );
    const noTestCases = !planLoading && !casesLoading && (testCases ?? []).length === 0;
    if (hasDangerous || noTestCases) {
      setShowRunReview(true);
    } else {
      setShowRunModal(true);
    }
  };

  const handleManualRunClick = () => {
    if (runBlocked) return;
    setShowManualRunModal(true);
  };

  if (packLoading) return <AppShell title="Loading…"><LoadingSkeleton /></AppShell>;
  if (isOffline) return <AppShell title="Connectors"><OfflineState onRetry={refetchPack} /></AppShell>;
  if (packError && !pack) return <AppShell title="Error"><ErrorState message={packError} onRetry={refetchPack} /></AppShell>;
  if (!pack) return <AppShell title="Pack not found"><ErrorState message="This validation pack does not exist in this workspace." /></AppShell>;

  const recentRuns = runs ?? [];
  const passedRuns = recentRuns.filter(r => r.verdict === 'pass').length;
  const passRate = recentRuns.length > 0 ? Math.round((passedRuns / recentRuns.length) * 100) : null;

  const allCases = testCases ?? [];
  const filteredCases = allCases.filter(tc => {
    if (testPlanTab === 'all') return true;
    if (testPlanTab === 'blocked') {
      return tc.automation_status === 'blocked'
        || tc.automation_status === 'manual_only'
        || tc.automation_status === 'capability_gap';
    }
    return tc.test_type === testPlanTab;
  });

  const destructiveCount = allCases.filter(tc => tc.safety_level === 'destructive' && tc.enabled).length;
  const cautionCount = allCases.filter(tc => tc.safety_level === 'caution' && tc.enabled).length;

  const isGeneric = testPlan?.generated_from === 'generic_app_type_template';

  return (
    <AppShell section="03" title={pack.name}>
      {showRunModal && (
        <StartRunModal
          packId={pack.id}
          packName={pack.name}
          onClose={() => setShowRunModal(false)}
        />
      )}
      {showManualRunModal && (
        <StartRunModal
          packId={pack.id}
          packName={pack.name}
          isManual={true}
          onClose={() => setShowManualRunModal(false)}
        />
      )}
      {aiPreview && (
        <AiTestPlanPreviewModal
          packId={pack.id}
          preview={aiPreview}
          onClose={() => setAiPreview(null)}
          onAcceptSuccess={() => {
            setAiPreview(null);
            refetchPlan();
            refetchCases();
          }}
        />
      )}

      <PageHeader
        title={pack.name}
        subtitle={pack.description ?? `Pack ID: ${pack.id}`}
        provenance={pack.provenance}
        provenanceSource="Validation pack detail"
        actions={
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn size="sm" variant="ghost" onClick={() => nav('/packs')}>
              <ArrowLeft size={12} />All packs
            </Btn>
            <Btn size="sm" variant="ghost" onClick={() => { refetchPack(); refetchRuns(); refetchPlan(); refetchCases(); refetchApps(); }}>
              <RefreshCw size={12} />
            </Btn>
            <Btn size="sm" variant="danger" demoWrite onClick={handleDelete} disabled={deleting}>
              <Trash2 size={12} />{deleting ? 'Deleting…' : 'Delete'}
            </Btn>
            <Btn
              size="sm"
              variant="ghost"
              demoWrite
              disabled={runBlocked}
              title={runBlockTitle}
              onClick={handleManualRunClick}
              data-testid="start-manual-run"
            >
              <Play size={12} />Start manual run
            </Btn>
            <Btn
              size="sm"
              variant="primary"
              demoWrite
              disabled={runBlocked}
              title={runBlockTitle}
              onClick={handleRunClick}
            >
              <Play size={12} />Run pack
            </Btn>
          </div>
        }
      />

      {deleteError && (
        <div style={{ marginBottom: 16, padding: '8px 12px', borderRadius: 7,
          background: P.failSoft, border: `1px solid ${P.fail}33`, fontSize: 12, color: P.fail }}>
          {deleteError}
        </div>
      )}

      {containsPreviewSteps && (
        <div
          data-testid="preview-pack-warning"
          style={{
            display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16,
            padding: '9px 12px', borderRadius: 7, background: `${P.textMute}12`,
            border: `1px solid ${P.textMute}33`, fontSize: 12, color: P.textDim,
          }}
        >
          <PreviewBadge />
          Contains preview steps. They are read-only and cannot be run until the capability is available.
        </div>
      )}

      {/* Run review modal — shown when destructive cases exist or no test cases */}
      {showRunReview && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
        }}>
          <div data-testid="run-review-modal" style={{
            background: P.card, border: `1px solid ${P.border}`, borderRadius: 12,
            padding: 24, maxWidth: 460, width: '90%', boxShadow: P.shadowCard,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <AlertTriangle size={18} color={P.unclear} />
              <div style={{ fontSize: 15, fontWeight: 600, color: P.text }}>Review before running</div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 20,
              fontSize: 12, color: P.textDim }}>
              <div>Test cases: <strong style={{ color: P.text }}>{allCases.length}</strong></div>
              {cautionCount > 0 && (
                <div style={{ color: P.unclear }}>⚠ {cautionCount} caution case{cautionCount !== 1 ? 's' : ''}</div>
              )}
              {destructiveCount > 0 && (
                <div data-testid="destructive-warning" style={{ color: P.fail }}>
                  ⚠ {destructiveCount} destructive case{destructiveCount !== 1 ? 's' : ''} enabled
                </div>
              )}
              {allCases.length === 0 && (
                <div data-testid="no-test-cases-warning" style={{ color: P.unclear }}>
                  No test plan generated yet. The run will execute pack steps without a test plan.
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <Btn variant="ghost" size="sm" onClick={() => setShowRunReview(false)}>Cancel</Btn>
              <Btn variant="primary" size="sm" onClick={() => { setShowRunReview(false); setShowRunModal(true); }}>
                Proceed with run
              </Btn>
            </div>
          </div>
        </div>
      )}

      {/* Stats row */}
      <div className="resp-stats-row" style={{ marginBottom: 20 }}>
        <StatCard label="Total runs" value={recentRuns.length}
          provenance={pack.provenance} provenanceSource="Validation pack metric" />
        <StatCard label="Pass rate" value={passRate !== null ? `${passRate}%` : '—'}
          provenance={pack.provenance} provenanceSource="Validation pack metric" />
        <StatCard label="Steps defined" value={pack.steps.length}
          provenance={pack.provenance} provenanceSource="Validation pack metric" />
        <StatCard label="Test cases" value={planLoading || casesLoading ? '…' : allCases.length}
          provenance={pack.provenance} provenanceSource="Validation pack metric" />
      </div>

      {/* Schedule panel */}
      {pack.schedule && pack.schedule !== 'none' && (
        <Card style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
                textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                Schedule
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>
                  {pack.schedule}
                </span>
                {pack.next_run_at && scheduleEnabled && (
                  <span style={{ fontSize: 12, color: P.textMute }}>
                    Next run: {new Date(pack.next_run_at).toLocaleString()}
                  </span>
                )}
                {pack.last_scheduled_run_at && (
                  <span style={{ fontSize: 12, color: P.textMute }}>
                    Last: {new Date(pack.last_scheduled_run_at).toLocaleString()}
                  </span>
                )}
              </div>
            </div>
            <button
              disabled={scheduleUpdating}
              aria-label={scheduleEnabled ? 'Disable schedule' : 'Enable schedule'}
              onClick={async () => {
                if (!packId) return;
                const next = !scheduleEnabled;
                setScheduleEnabled(next);
                setScheduleUpdating(true);
                try {
                  await patch(`/validation-packs/${packId}`, { schedule_enabled: next });
                  refetchPack();
                } catch {
                  setScheduleEnabled(!next);
                } finally {
                  setScheduleUpdating(false);
                }
              }}
              style={{
                padding: '6px 14px',
                borderRadius: 6,
                border: `1px solid ${scheduleEnabled ? P.pass : P.border}`,
                background: scheduleEnabled ? P.pass : 'transparent',
                color: scheduleEnabled ? '#fff' : P.text,
                cursor: scheduleUpdating ? 'not-allowed' : 'pointer',
                fontWeight: 600,
                fontSize: 13,
                opacity: scheduleUpdating ? 0.6 : 1,
              }}
            >
              {scheduleEnabled ? 'Enabled' : 'Disabled'}
            </button>
          </div>
        </Card>
      )}

      <div className="resp-detail-grid">
        {/* Steps */}
        <Card>
          <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
            textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
            STEPS · {pack.steps.length}
          </div>
          {pack.steps.length === 0 ? (
            <PartialConfigBanner
              message="This pack has no steps configured. Steps are defined via the Inspectra SDK or by generating a test plan in the section below."
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {pack.steps.map((step: any, i) => (
                <div key={step.step_id || i} style={{
                  padding: '8px 12px', borderRadius: 7, background: P.cardHi,
                  border: `1px solid ${P.border}`,
                }}>
                  <div style={{ fontSize: 12, color: P.text, fontWeight: 500 }}>
                    {step.description || `Step ${i + 1}`}
                  </div>
                  {isPreviewStep(step) && <PreviewBadge style={{ marginTop: 5 }} />}
                  <ProvenanceBadge provenance={pack.provenance} source="Validation pack step" style={{ marginTop: 5 }} />
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 4, flexWrap: 'wrap' }}>
                    <span style={{
                      fontSize: 9, fontWeight: 700, letterSpacing: '0.04em', fontFamily: F.mono,
                      background: `${P.accent}18`, border: `1px solid ${P.accent}33`, borderRadius: 4,
                      padding: '1px 4px', color: P.accent, textTransform: 'uppercase'
                    }}>
                      {step.action_type || 'interact'}
                    </span>
                    {step.target && (
                      <span style={{ fontSize: 10, color: P.textDim, fontFamily: F.mono }}>
                        target: {step.target}
                      </span>
                    )}
                    {(step.input_value || step.expected_result) && (
                      <span style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono }}>
                        value: {step.input_value || step.expected_result}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Recent runs */}
        <Card pad={0}>
          <div style={{ padding: '12px 16px', borderBottom: `1px solid ${P.border}` }}>
            <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
              textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              RECENT RUNS
            </div>
          </div>
          {runsLoading ? (
            <div style={{ padding: 16 }}><LoadingSkeleton rows={3} /></div>
          ) : recentRuns.length === 0 ? (
            <div style={{ padding: '20px 16px', fontSize: 12, color: P.textMute, textAlign: 'center' }}>
              No runs yet.{' '}
              <span style={{ color: P.accent, cursor: 'pointer' }} onClick={handleRunClick}>
                Start one
              </span>.
            </div>
          ) : (
            recentRuns.map((run, i) => (
              <div
                key={run.id}
                onClick={() => nav(`/runs/${run.id}`)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px',
                  borderBottom: i < recentRuns.length - 1 ? `1px solid ${P.border}` : 'none',
                  cursor: 'pointer', transition: 'background 0.1s',
                }}
                onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = P.cardHi}
                onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'transparent'}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: P.text, fontFamily: F.mono }}>
                    {run.id.slice(0, 12)}…
                  </div>
                  <div style={{ fontSize: 11, color: P.textMute }}>
                    {run.started_at ? new Date(run.started_at).toLocaleString() : run.created_at
                      ? new Date(run.created_at).toLocaleString() : '—'}
                  </div>
                </div>
                <StatusBadge kind={
                  run.status === 'running' ? 'partial'
                  : run.status === 'failed' ? 'missing'
                  : run.status === 'completed' && run.verdict
                    ? (run.verdict === 'pending' ? 'skipped' : run.verdict as never)
                  : 'skipped'
                } small />
                <ProvenanceBadge provenance={run.provenance} source="Validation pack recent run" />
              </div>
            ))
          )}
        </Card>
      </div>

      {/* ── Test Plan section ─────────────────────────────────────────────────── */}
      <div style={{ marginTop: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: P.text }}>Test Plan</div>
            {allCases.length > 0 && (
              <span style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono }}>
                {allCases.length} cases
              </span>
            )}
            {isGeneric && allCases.length > 0 && (
              <span data-testid="generic-draft-badge" style={{
                fontSize: 9, fontWeight: 700, fontFamily: F.mono,
                background: P.unclearSoft, border: `1px solid ${P.unclear}33`,
                borderRadius: 4, padding: '2px 6px', color: P.unclear,
              }}>
                GENERIC DRAFT
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn
              data-testid="generate-ai-test-plan-btn"
              size="sm"
              variant="primary"
              demoWrite
              onClick={handleGenerateAi}
              disabled={aiGenerating}
            >
              <Sparkles size={11} />{aiGenerating ? 'AI Generating…' : 'Generate with AI'}
            </Btn>
            {testPlan && (
              <Btn size="sm" variant="ghost" demoWrite onClick={() => handleGenerate(true)} disabled={generating}>
                <RefreshCw size={11} />Regenerate
              </Btn>
            )}
            <Btn
              data-testid="generate-test-plan-btn"
              size="sm"
              variant={testPlan ? 'ghost' : 'primary'}
              demoWrite
              onClick={() => handleGenerate(false)}
              disabled={generating || !!testPlan}
            >
              <Zap size={11} />{generating ? 'Generating…' : testPlan ? 'Plan ready' : 'Generate test plan'}
            </Btn>
          </div>
        </div>

        {genError && (
          <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 7,
            background: P.failSoft, border: `1px solid ${P.fail}33`, fontSize: 12, color: P.fail }}>
            {genError}
          </div>
        )}

        {aiGenError && (
          <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 7,
            background: P.failSoft, border: `1px solid ${P.fail}33`, fontSize: 12, color: P.fail }}>
            {aiGenError}
          </div>
        )}

        {planLoading || casesLoading ? (
          <Card><LoadingSkeleton rows={4} /></Card>
        ) : !testPlan && allCases.length === 0 ? (
          /* Empty state */
          <Card>
            <div data-testid="no-test-plan-empty-state"
              style={{ textAlign: 'center', padding: '32px 0' }}>
              <div style={{ fontSize: 28, marginBottom: 10 }}>📋</div>
              <div style={{ fontSize: 14, fontWeight: 500, color: P.textDim, marginBottom: 6 }}>
                No test plan generated yet
              </div>
              <div style={{ fontSize: 12, color: P.textMute, marginBottom: 16, maxWidth: 340, margin: '0 auto 16px' }}>
                Generate a generic test plan to see what Inspectra will test.
                Connect an app for app-specific cases.
              </div>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
                <Btn data-testid="generate-ai-test-plan-empty-state-btn" variant="primary" demoWrite onClick={handleGenerateAi} disabled={aiGenerating}>
                  <Sparkles size={12} />{aiGenerating ? 'AI Generating…' : 'Generate with AI'}
                </Btn>
                <Btn variant="ghost" demoWrite onClick={() => handleGenerate(false)} disabled={generating}>
                  <Zap size={12} />{generating ? 'Generating…' : 'Generate test plan'}
                </Btn>
              </div>
            </div>
          </Card>
        ) : (
          /* Test cases table */
          <Card pad={0}>
            {/* Tab bar */}
            <div style={{
              display: 'flex', gap: 0, borderBottom: `1px solid ${P.border}`,
              padding: '0 14px', overflowX: 'auto',
            }}>
              {TABS.map(tab => {
                const count = tab.id === 'all'
                  ? allCases.length
                  : tab.id === 'blocked'
                  ? allCases.filter(tc =>
                      tc.automation_status === 'blocked' ||
                      tc.automation_status === 'manual_only' ||
                      tc.automation_status === 'capability_gap').length
                  : allCases.filter(tc => tc.test_type === tab.id).length;
                if (tab.id !== 'all' && count === 0) return null;
                const active = testPlanTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    data-testid={`tab-${tab.id}`}
                    onClick={() => { setTestPlanTab(tab.id); setExpandedCaseId(null); }}
                    style={{
                      padding: '9px 12px', fontSize: 11, fontWeight: active ? 600 : 400,
                      color: active ? P.accent : P.textMute,
                      borderBottom: active ? `2px solid ${P.accent}` : '2px solid transparent',
                      background: 'transparent', cursor: 'pointer', whiteSpace: 'nowrap',
                      marginBottom: -1,
                    }}
                  >
                    {tab.label}
                    {count > 0 && (
                      <span style={{ marginLeft: 5, fontSize: 9, color: active ? P.accent : P.textFaint,
                        fontFamily: F.mono }}>{count}</span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Case rows */}
            {filteredCases.length === 0 ? (
              <div style={{ padding: '20px 14px', fontSize: 12, color: P.textMute, textAlign: 'center' }}>
                No test cases in this category.
              </div>
            ) : (
              filteredCases.map(tc => (
                <TestCaseRow
                  key={tc.test_case_id}
                  tc={tc}
                  expanded={expandedCaseId === tc.test_case_id}
                  onToggle={() =>
                    setExpandedCaseId(expandedCaseId === tc.test_case_id ? null : tc.test_case_id)
                  }
                  onRefresh={() => { refetchCases(); refetchPlan(); }}
                  packId={packId!}
                />
              ))
            )}
          </Card>
        )}
      </div>

      {/* Pack metadata */}
      <div style={{ marginTop: 20 }}>
        <Card>
          <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
            textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
            METADATA
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 12 }}>
            <div>
              <span style={{ color: P.textMute }}>Pack ID: </span>
              <code style={{ fontFamily: F.mono, fontSize: 11, color: P.textDim }}>{pack.id}</code>
            </div>
            <div>
              <span style={{ color: P.textMute }}>Project ID: </span>
              <code style={{ fontFamily: F.mono, fontSize: 11, color: P.textDim }}>{pack.project_id}</code>
            </div>
            <div>
              <span style={{ color: P.textMute }}>Created: </span>
              <span style={{ color: P.text }}>{new Date(pack.created_at).toLocaleString()}</span>
            </div>
            <div>
              <span style={{ color: P.textMute }}>Updated: </span>
              <span style={{ color: P.text }}>{new Date(pack.updated_at).toLocaleString()}</span>
            </div>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}

interface AiTestPlanPreviewModalProps {
  packId: string;
  preview: AITestPlanPreview;
  onClose: () => void;
  onAcceptSuccess: () => void;
}

export function AiTestPlanPreviewModal({
  packId,
  preview: initialPreview,
  onClose,
  onAcceptSuccess,
}: AiTestPlanPreviewModalProps) {
  const [previewData, setPreviewData] = useState<AITestPlanPreview>(initialPreview);
  const [selectedIndices, setSelectedIndices] = useState<Set<number>>(new Set());
  const [accepting, setAccepting] = useState(false);
  const [acceptError, setAcceptError] = useState('');

  useEffect(() => {
    setSelectedIndices(new Set(
      initialPreview.test_cases.flatMap((testCase, index) =>
        testCaseContainsPreview(testCase) ? [] : [index]
      ),
    ));
  }, [initialPreview]);

  const handleToggleSelect = (index: number) => {
    if (testCaseContainsPreview(previewData.test_cases[index])) return;
    const next = new Set(selectedIndices);
    if (next.has(index)) {
      next.delete(index);
    } else {
      next.add(index);
    }
    setSelectedIndices(next);
  };

  const handleUpdateTestCase = (index: number, updatedFields: Partial<AIProposedTestCase>) => {
    const nextCases = [...previewData.test_cases];
    nextCases[index] = { ...nextCases[index], ...updatedFields };
    setPreviewData({ ...previewData, test_cases: nextCases });
  };

  const handleUpdateTestStep = (
    tcIndex: number,
    stepIndex: number,
    updatedStepFields: Partial<AIProposedTestStep>
  ) => {
    const nextCases = [...previewData.test_cases];
    const nextSteps = [...(nextCases[tcIndex].test_steps || [])];
    nextSteps[stepIndex] = { ...nextSteps[stepIndex], ...updatedStepFields };
    nextCases[tcIndex] = { ...nextCases[tcIndex], test_steps: nextSteps };
    setPreviewData({ ...previewData, test_cases: nextCases });
  };

  const handleAccept = async () => {
    const selectedCases = previewData.test_cases.filter((_, i) => selectedIndices.has(i));
    if (selectedCases.length === 0) {
      alert('Please select at least one test case to accept.');
      return;
    }
    setAccepting(true);
    setAcceptError('');
    try {
      await acceptAiTestPlan(packId, selectedCases);
      onAcceptSuccess();
    } catch (err) {
      setAcceptError(String(err instanceof Error ? err.message : err));
    } finally {
      setAccepting(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    background: P.card,
    border: `1px solid ${P.border}`,
    borderRadius: 4,
    padding: '4px 6px',
    color: P.text,
    fontSize: 11,
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
      style={{
        position: 'fixed', inset: 0, zIndex: 300,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div style={{
        background: P.card, border: `1px solid ${P.border}`, borderRadius: 12,
        width: 800, maxWidth: '95vw', maxHeight: '90vh', padding: 24,
        display: 'flex', flexDirection: 'column', gap: 16,
        boxShadow: P.shadowCard,
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: `1px solid ${P.border}`, paddingBottom: 12 }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: P.text, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Sparkles size={16} color="#a78bfa" />
              AI Proposed Test Plan Preview
            </div>
            <div style={{ fontSize: 11, color: P.textMute, marginTop: 2 }}>
              Source: <span style={{ fontWeight: 600, color: P.textDim }}>{previewData.generation_source}</span>
              {previewData.generation_source === 'local_fallback' && (
                <span data-testid="modal-local-fallback-badge" style={{ marginLeft: 6, fontSize: 8, padding: '1px 4px', borderRadius: 3, background: `${P.unclear}18`, color: P.unclear, border: `1px solid ${P.unclear}33` }}>
                  LOCAL FALLBACK
                </span>
              )}
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: P.textMute, padding: 4 }}>
            <X size={18} />
          </button>
        </div>

        {/* Content list */}
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 16, paddingRight: 4 }}>
          {previewData.test_cases.map((tc, tcIdx) => {
            const isSelected = selectedIndices.has(tcIdx);
            const previewCase = testCaseContainsPreview(tc);
            return (
              <div
                key={tcIdx}
                data-testid={`proposed-case-${tcIdx}`}
                style={{
                  border: `1px solid ${isSelected ? P.accent : P.border}`,
                  background: isSelected ? 'transparent' : `${P.border}22`,
                  borderRadius: 8, padding: 14, display: 'flex', flexDirection: 'column', gap: 10,
                  opacity: isSelected ? 1 : 0.75, transition: 'all 0.12s',
                }}
              >
                {/* Case Header: Checkbox + Title Input */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <input
                    type="checkbox"
                    checked={isSelected}
                    disabled={previewCase}
                    title={previewCase ? PREVIEW_TOOLTIP : undefined}
                    onChange={() => handleToggleSelect(tcIdx)}
                    style={{ cursor: 'pointer', width: 15, height: 15 }}
                  />
                  <div style={{ flex: 1 }}>
                    <input
                      style={{ ...inputStyle, fontSize: 12, fontWeight: 600 }}
                      value={tc.title}
                      readOnly={previewCase}
                      onChange={e => handleUpdateTestCase(tcIdx, { title: e.target.value })}
                      placeholder="Case Title"
                    />
                  </div>
                  {previewCase && <PreviewBadge />}
                  <span style={{ fontSize: 10, fontFamily: F.mono, fontWeight: 700, color: tc.confidence >= 0.8 ? P.pass : tc.confidence >= 0.5 ? P.unclear : P.fail }}>
                    {Math.round(tc.confidence * 100)}% Match
                  </span>
                </div>

                {/* Case description/objective */}
                <div>
                  <label style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>OBJECTIVE / DESCRIPTION</label>
                  <input
                    style={inputStyle}
                    value={tc.objective || tc.description || ''}
                    readOnly={previewCase}
                    onChange={e => handleUpdateTestCase(tcIdx, { objective: e.target.value, description: e.target.value })}
                    placeholder="Describe what this test case verifies"
                  />
                </div>

                {/* Rationale */}
                {tc.rationale && (
                  <div style={{ fontSize: 11, color: P.textMute, fontStyle: 'italic', background: `${P.border}15`, padding: '6px 8px', borderRadius: 4 }}>
                    <strong style={{ fontStyle: 'normal' }}>Rationale:</strong> {tc.rationale}
                  </div>
                )}

                {/* Steps list */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, borderLeft: `2px solid ${P.border}`, paddingLeft: 10 }}>
                  <div style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono, fontWeight: 600 }}>PROPOSED STEPS</div>
                  {(tc.test_steps || []).map((step, stepIdx) => {
                    const isUnsupported = !ACTION_TYPES.includes(step.action_type);
                    const previewStep = isPreviewAction(step.action_type);
                    return (
                      <div key={stepIdx} style={{ background: P.cardHi, border: `1px solid ${P.border}`, borderRadius: 6, padding: 8 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span style={{ fontSize: 10, fontWeight: 600, fontFamily: F.mono, color: P.accent }}>
                            #{stepIdx + 1}: {step.action_type}
                          </span>
                          {previewStep ? (
                            <PreviewBadge />
                          ) : isUnsupported && (
                            <span style={{ fontSize: 9, fontWeight: 700, color: P.fail, background: `${P.fail}18`, border: `1px solid ${P.fail}33`, borderRadius: 4, padding: '1px 4px' }}>
                              UNSUPPORTED ACTION
                            </span>
                          )}
                        </div>

                        {/* Inline step editing */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginTop: 6 }}>
                          <div>
                            <label style={{ fontSize: 8, color: P.textMute }}>Target</label>
                            <input
                              style={inputStyle}
                              value={step.target || ''}
                              readOnly={previewStep}
                              onChange={e => handleUpdateTestStep(tcIdx, stepIdx, { target: e.target.value })}
                              placeholder="Selector / URL"
                            />
                          </div>
                          <div>
                            <label style={{ fontSize: 8, color: P.textMute }}>Value</label>
                            <input
                              style={inputStyle}
                              value={step.value || ''}
                              readOnly={previewStep}
                              onChange={e => handleUpdateTestStep(tcIdx, stepIdx, { value: e.target.value })}
                              placeholder="Input value"
                            />
                          </div>
                          <div>
                            <label style={{ fontSize: 8, color: P.textMute }}>Expected</label>
                            <input
                              style={inputStyle}
                              value={step.expected || ''}
                              readOnly={previewStep}
                              onChange={e => handleUpdateTestStep(tcIdx, stepIdx, { expected: e.target.value })}
                              placeholder="Expected substring"
                            />
                          </div>
                        </div>
                        {previewStep ? (
                          <div style={{ fontSize: 9, color: P.textMute, marginTop: 4, fontWeight: 500 }}>
                            Preview steps are read-only and will not be accepted into an executable pack.
                          </div>
                        ) : isUnsupported && (
                          <div style={{ fontSize: 9, color: P.fail, marginTop: 4, fontWeight: 500 }}>
                            ⚠ Warning: Action type "{step.action_type}" is not supported by the runner and may fail or be skipped.
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {acceptError && (
          <div style={{ padding: '8px 12px', borderRadius: 7, background: P.failSoft, border: `1px solid ${P.fail}33`, fontSize: 12, color: P.fail }}>
            Accept failed: {acceptError}
          </div>
        )}

        {/* Footer Actions */}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', borderTop: `1px solid ${P.border}`, paddingTop: 12 }}>
          <Btn variant="ghost" onClick={onClose} disabled={accepting}>Cancel</Btn>
          <Btn
            variant="primary"
            onClick={handleAccept}
            disabled={accepting || selectedIndices.size === 0}
          >
            <Check size={12} />
            {accepting ? 'Accepting…' : `Accept Selected (${selectedIndices.size})`}
          </Btn>
        </div>
      </div>
    </div>
  );
}
