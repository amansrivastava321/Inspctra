/** Deterministic sample data used only by the explicit /demo workspace. */
import type {
  DashboardSummary, LiveRunRecord, Project, AppTarget, ValidationPack,
  RuntimeDoctorReport, ConnectorsResponse, ReportRecord, EvidenceFile,
  MemoryStats, ModelProvider, ModelProfile, HardwareProfile, HealthStatus, ProductSetting,
} from '../types/api';

const DEMO_CREATED_AT = '2026-08-14T12:00:00.000Z';
const DEMO_RUN_ONE_AT = '2026-08-14T11:46:00.000Z';
const DEMO_RUN_TWO_AT = '2026-08-14T10:00:00.000Z';
const DEMO_PROVENANCE = 'DEMO_EXAMPLE' as const;

export const MOCK_RUNS: LiveRunRecord[] = [
  { id: 'run-001', pack_id: 'pack-001', pack_name: 'Daily smoke', app_name: 'FlowBook',
    platform: 'macOS', status: 'completed', verdict: 'pass', confidence: 94,
    elapsed_ms: 134_000, started_at: DEMO_RUN_ONE_AT, provenance: DEMO_PROVENANCE,
    operator: 'local-user',permission_scope: 8,
    step_results: [
      { id: 's1', index: 1, name: 'Open FlowBook', status: 'passed', confidence: 98, duration_ms: 4200, evidence_count: 3, provenance: DEMO_PROVENANCE },
      { id: 's2', index: 2, name: 'Sign in (macOS)', status: 'passed', confidence: 96, duration_ms: 1300, evidence_count: 4, provenance: DEMO_PROVENANCE },
      { id: 's3', index: 3, name: 'Create new ledger', status: 'passed', confidence: 92, duration_ms: 800, evidence_count: 5, provenance: DEMO_PROVENANCE },
      { id: 's4', index: 4, name: 'Add entry — debit', status: 'passed', confidence: 94, duration_ms: 950, evidence_count: 4, provenance: DEMO_PROVENANCE },
      { id: 's5', index: 5, name: 'Add entry — credit', status: 'passed', confidence: 90, duration_ms: 880, evidence_count: 4, provenance: DEMO_PROVENANCE },
      { id: 's6', index: 6, name: 'Export PDF', status: 'unclear', confidence: 62, duration_ms: 3400, evidence_count: 3, provenance: DEMO_PROVENANCE },
      { id: 's7', index: 7, name: 'Sign in (web)', status: 'passed', confidence: 97, duration_ms: 1100, evidence_count: 4, provenance: DEMO_PROVENANCE },
      { id: 's8', index: 8, name: 'Upload source video', status: 'passed', confidence: 90, duration_ms: 5800, evidence_count: 4, provenance: DEMO_PROVENANCE },
      { id: 's9', index: 9, name: 'Generate AI story', status: 'failed', confidence: 38, duration_ms: 7200, evidence_count: 7, provenance: DEMO_PROVENANCE },
    ] },
  { id: 'run-002', pack_id: 'pack-002', pack_name: 'Full regression', app_name: 'Videomation',
    platform: 'web', status: 'failed', verdict: 'fail', confidence: 68,
    elapsed_ms: 280_000, started_at: DEMO_RUN_TWO_AT, provenance: DEMO_PROVENANCE,
    step_results: Array.from({ length: 6 }, (_, i) => ({
      id: `s-r2-${i}`, index: i + 1, name: `Step ${i + 1}`,
      status: i < 4 ? 'passed' : 'failed', confidence: i < 4 ? 90 : 30,
      duration_ms: 1200, evidence_count: 3, provenance: DEMO_PROVENANCE,
    })) },
];

export const MOCK_DASHBOARD: DashboardSummary = {
  project_count: 2, app_target_count: 5, validation_pack_count: 6,
  total_runs: 142, runs_completed: 134, runs_failed: 6, runs_running: 0,
  workspace_health: 84, latest_verdict: 'pass', evidence_strength: 'strong',
  open_issues: 7,
  provenance: DEMO_PROVENANCE,
  recent_runs: MOCK_RUNS,
  projects_count: 2,
  apps_count: 5,
  packs_count: 6,
  total_runs_7d: 12,
  passed_runs_7d: 9,
  recent_failed_run: {
    id: 'run-002',
    pack_id: 'pack-002',
    app_target_id: 'a2',
    app_name: 'Videomation',
    pack_name: 'Full regression',
    failure_reason: 'Assertion failed: generated story did not match the expected format',
    failed_at: DEMO_RUN_TWO_AT,
    provenance: DEMO_PROVENANCE,
    screenshot_evidence_id: null,
    screenshot_provenance: DEMO_PROVENANCE,
  },
  failure_reasons: [
    { category: 'Assertion failed', count: 3, run_ids: ['run-002'], provenance: DEMO_PROVENANCE },
    { category: 'Timeout', count: 2, run_ids: ['run-003', 'run-004'], provenance: DEMO_PROVENANCE },
    { category: 'HTTP 5xx', count: 1, run_ids: ['run-005'], provenance: DEMO_PROVENANCE },
  ],
  pass_rate_7d: [
    { date: '2026-08-08', passed: 0, failed: 0, total: 0, pass_rate: null, provenance: DEMO_PROVENANCE },
    { date: '2026-08-09', passed: 2, failed: 0, total: 2, pass_rate: 100, provenance: DEMO_PROVENANCE },
    { date: '2026-08-10', passed: 1, failed: 1, total: 2, pass_rate: 50, provenance: DEMO_PROVENANCE },
    { date: '2026-08-11', passed: 2, failed: 0, total: 2, pass_rate: 100, provenance: DEMO_PROVENANCE },
    { date: '2026-08-12', passed: 1, failed: 0, total: 1, pass_rate: 100, provenance: DEMO_PROVENANCE },
    { date: '2026-08-13', passed: 2, failed: 1, total: 3, pass_rate: 66.7, provenance: DEMO_PROVENANCE },
    { date: '2026-08-14', passed: 1, failed: 1, total: 2, pass_rate: 50, provenance: DEMO_PROVENANCE },
  ],
  coverage: {
    with_packs: 4,
    total: 5,
    percentage: 80,
    last_pack_created_at: DEMO_CREATED_AT,
    provenance: DEMO_PROVENANCE,
  },
  last_run_at: DEMO_RUN_ONE_AT,
  last_run_provenance: DEMO_PROVENANCE,
  generated_at: DEMO_CREATED_AT,
  capability_gaps: [
    { id: 'g1', title: 'Mobile testing requires Appium', description: '1 Android app blocked. Install Appium + driver in ~90s.', severity: 'high', action_label: 'Install for me' },
    { id: 'g2', title: 'iOS coverage paused', description: 'XCUITest setup pending', severity: 'medium' },
  ],
  runtime_readiness: [
    { name: 'Playwright', status: 'ready' },
    { name: 'Backend service', status: 'ready' },
    { name: 'Postgres', status: 'ready' },
    { name: 'Ollama (llama3.1)', status: 'ready' },
    { name: 'macOS Accessibility', status: 'perm' },
    { name: 'Appium server', status: 'missing' },
    { name: 'Docker', status: 'skipped' },
  ],
  pass_rate_history: [
    { date: '1/2/2026', rate: 68 }, { date: '1/3/2026', rate: 72 },
    { date: '1/4/2026', rate: 70 }, { date: '1/5/2026', rate: 76 },
    { date: '1/6/2026', rate: 79 }, { date: '1/7/2026', rate: 77 },
    { date: '1/8/2026', rate: 81 }, { date: '1/9/2026', rate: 83 },
    { date: '1/10/2026', rate: 80 }, { date: '1/11/2026', rate: 85 },
    { date: '1/12/2026', rate: 84 }, { date: '1/13/2026', rate: 87 },
    { date: '1/14/2026', rate: 86 }, { date: '1/15/2026', rate: 88 },
  ],
};

export const MOCK_PROJECTS: Project[] = [
  { id: 'p1', name: 'FlowBook', description: 'Desktop finance app', created_at: DEMO_CREATED_AT, provenance: DEMO_PROVENANCE },
  { id: 'p2', name: 'Videomation', description: 'AI video platform', created_at: DEMO_CREATED_AT, provenance: DEMO_PROVENANCE },
];

export const MOCK_APPS: AppTarget[] = [
  { id: 'a1', project_id: 'p1', name: 'FlowBook', app_type: 'desktop', platform: 'macos',
    status: 'ready', pass_rate: 92, total_runs: 142, open_issues: 1, last_run_at: MOCK_RUNS[0].started_at,
    working_directory: '~/code/flowbook', launch_command: 'flutter run -d macos --profile', tags: ['desktop', 'finance'],
    created_at: DEMO_CREATED_AT, updated_at: DEMO_CREATED_AT, provenance: DEMO_PROVENANCE },
  { id: 'a2', project_id: 'p2', name: 'Videomation', app_type: 'web', platform: 'web',
    status: 'ready', pass_rate: 78, total_runs: 64, open_issues: 3, last_run_at: MOCK_RUNS[1].started_at,
    tags: ['web', 'ai'], created_at: DEMO_CREATED_AT, updated_at: DEMO_CREATED_AT, provenance: DEMO_PROVENANCE },
  { id: 'a3', project_id: 'p1', name: 'Android demo', app_type: 'mobile', platform: 'android',
    status: 'missing', pass_rate: 0, total_runs: 0, open_issues: 2, tags: ['mobile'],
    created_at: DEMO_CREATED_AT, updated_at: DEMO_CREATED_AT, provenance: DEMO_PROVENANCE },
  { id: 'a4', project_id: 'p2', name: 'iOS app', app_type: 'mobile', platform: 'ios',
    status: 'perm', pass_rate: 0, total_runs: 3, open_issues: 2, tags: ['mobile'],
    created_at: DEMO_CREATED_AT, updated_at: DEMO_CREATED_AT, provenance: DEMO_PROVENANCE },
];

export const MOCK_PACKS: ValidationPack[] = [
  { id: 'pack-001', name: 'Daily smoke', total_flows: 12, target_names: ['FlowBook', 'Videomation'],
    target_app_ids: ['a1', 'a2'],
    schedule: 'weekdays 09:00', readiness: 'ready', last_verdict: 'pass', avg_pass_rate: 94,
    last_run_at: MOCK_RUNS[0].started_at, coverage: 83,
    history: [true,true,true,false,true,true,true,true,true,true], provenance: DEMO_PROVENANCE },
  { id: 'pack-002', name: 'Full regression', total_flows: 47, target_names: ['Videomation web'],
    target_app_ids: ['a2'],
    schedule: 'nightly', readiness: 'ready', last_verdict: 'fail', avg_pass_rate: 68,
    last_run_at: MOCK_RUNS[1].started_at, provenance: DEMO_PROVENANCE },
  { id: 'pack-003', name: 'Onboarding cohort', total_flows: 8, target_names: ['Android demo'],
    target_app_ids: ['a3'],
    schedule: 'manual', readiness: 'missing', last_verdict: 'blocked', avg_pass_rate: 0, provenance: DEMO_PROVENANCE },
  { id: 'pack-004', name: 'Contract — payments', total_flows: 23, target_names: ['Generic API'],
    schedule: 'on PR', readiness: 'ready', last_verdict: 'pass', avg_pass_rate: 98, provenance: DEMO_PROVENANCE },
  { id: 'pack-005', name: 'iOS quick check', total_flows: 6, target_names: ['iOS app'],
    target_app_ids: ['a4'],
    schedule: 'manual', readiness: 'perm', last_verdict: 'skipped', avg_pass_rate: 0, provenance: DEMO_PROVENANCE },
  { id: 'pack-006', name: 'Auth & permissions', total_flows: 14, target_names: ['FlowBook', 'web'],
    target_app_ids: ['a1', 'a2'],
    schedule: 'weekly', readiness: 'ready', last_verdict: 'unclear', avg_pass_rate: 88, provenance: DEMO_PROVENANCE },
];

export const MOCK_DOCTOR: RuntimeDoctorReport = {
  provenance: DEMO_PROVENANCE,
  readiness_score: 72,
  readiness_band: 'partial',
  components: [
    { name: 'Platform · macOS 14.4', status: 'ready' },
    { name: 'Python 3.11.7', status: 'ready' },
    { name: 'Playwright 1.44', status: 'ready' },
    { name: 'Postgres driver', status: 'ready' },
    { name: 'Ollama llama3.1', status: 'ready' },
    { name: 'Docker', status: 'skipped', detail: 'Optional — only needed if you containerise your backend' },
    { name: 'macOS Accessibility', status: 'perm', detail: 'System Settings → Privacy & Security → Accessibility' },
    { name: 'Appium + driver', status: 'missing' },
  ],
  things_to_fix: [
    { id: 'f1', title: "Appium server isn't installed", status: 'missing',
      description: 'Needed to test Android & iOS apps.',
      commands: ['npm install -g appium', 'appium driver install uiautomator2'],
      action_label: 'Install for me', risk: 'low', time_estimate: '90s', disk_estimate: '220 MB' },
    { id: 'f2', title: 'macOS Accessibility permission', status: 'perm',
      description: 'Inspectra needs this to click buttons inside native macOS apps.' },
  ],
  summary: { ready: 5, missing: 1, perm: 1, skipped: 1 },
};

export const MOCK_CONNECTORS: ConnectorsResponse = {
  app_name: 'FlowBook', app_id: 'a1',
  provenance: DEMO_PROVENANCE,
  connectors: [
    { id: 'c1', name: 'Browser', connector_type: 'playwright', status: 'ready', detail: 'Playwright', host: 'localhost' },
    { id: 'c2', name: 'macOS A11y', connector_type: 'accessibility', status: 'perm', detail: 'permission ok' },
    { id: 'c3', name: 'Backend', connector_type: 'http', status: 'ready', detail: ':8765 · uvicorn', port: 8765 },
    { id: 'c4', name: 'Stripe (test)', connector_type: 'stripe', status: 'ready', detail: 'key configured' },
    { id: 'c5', name: 'Postgres', connector_type: 'postgres', status: 'ready', detail: 'flowbook_dev' },
    { id: 'c6', name: 'Ollama', connector_type: 'ollama', status: 'ready', detail: 'llama3.1 · local', host: 'localhost', port: 11434 },
    { id: 'c7', name: 'Appium server', connector_type: 'appium', status: 'missing', detail: 'driver missing', port: 4723 },
    { id: 'c8', name: 'Docker', connector_type: 'docker', status: 'skipped', detail: 'daemon not running' },
  ],
};

export const MOCK_EVIDENCE: EvidenceFile[] = [
  { id: 'ev1', run_id: 'run-001', step_id: 's1', evidence_type: 'screenshot', strength: 'strong',
    title: 'Screenshot diff', description: 'Before/after differ by 12.4%', created_at: DEMO_CREATED_AT, provenance: DEMO_PROVENANCE },
  { id: 'ev2', run_id: 'run-001', step_id: 's3', evidence_type: 'log', strength: 'strong',
    title: 'LOG MATCH', description: 'STORY_GEN_SUCCESS · 1 hit', content_preview: 'STORY_GEN_SUCCESS', provenance: DEMO_PROVENANCE },
  { id: 'ev3', run_id: 'run-001', step_id: 's3', evidence_type: 'db', strength: 'strong',
    title: 'Database delta', description: 'stories +1 (id=4429)', content_preview: 'stories +1', provenance: DEMO_PROVENANCE },
  { id: 'ev4', run_id: 'run-001', step_id: 's7', evidence_type: 'api', strength: 'strong',
    title: 'API check', description: 'POST /api/story · 200 · 312ms', content_preview: 'POST /api/story 200', provenance: DEMO_PROVENANCE },
  { id: 'ev5', run_id: 'run-001', step_id: 's9', evidence_type: 'ai', strength: 'medium',
    title: 'AI oracle', description: '"Story appeared as expected" — llama3.1 · 91% likely', content_preview: 'Story appeared as expected', provenance: DEMO_PROVENANCE },
];

export const MOCK_REPORTS: ReportRecord[] = [
  { id: 'rep1', run_id: 'run-001', app_name: 'FlowBook', pack_name: 'Daily smoke',
    verdict: 'pass', summary: 'FlowBook is mostly working.',
    pass_count: 9, fail_count: 2, unclear_count: 1, evidence_count: 312,
    findings: [
      { id: 'f1', title: 'Export PDF fails intermittently', severity: 'medium', status: 'unclear', step_name: 'Export PDF', description: 'Preview render returns 62% confidence. Timeout likely under load.' },
      { id: 'f2', title: 'Generate AI story failure', severity: 'high', status: 'fail', step_name: 'Generate AI story', description: 'llama3.1 returned unexpected format. DB story not created.' },
    ],
    created_at: DEMO_CREATED_AT, provenance: DEMO_PROVENANCE },
];

export const MOCK_MEMORY: MemoryStats = {
  scope_id: 'scope-flowbook', fingerprint_count: 312, pattern_count: 24,
  trajectory_count: 18, embedding_count: 89, baseline_id: 'baseline-001',
  last_ingested_at: DEMO_CREATED_AT,
};

export const MOCK_HARDWARE: HardwareProfile = {
  platform: 'macOS 14.4', cpu_cores: 10, ram_gb: 16, gpu: 'Apple M2 Pro', vram_gb: 16,
  recommended_profile: 'local-medium',
};

export const MOCK_PROVIDERS: ModelProvider[] = [
  { id: 'ollama', name: 'Ollama (local)', status: 'ready',
    models: [
      { id: 'm1', name: 'llama3.1', provider: 'ollama', size_gb: 4.7, status: 'ready' },
      { id: 'm2', name: 'moondream', provider: 'ollama', size_gb: 1.8, status: 'ready' },
    ] },
  { id: 'claude', name: 'Anthropic Claude', status: 'missing',
    models: [{ id: 'm3', name: 'claude-3-haiku', provider: 'claude', status: 'missing' }] },
];

export const MOCK_PROFILE: ModelProfile = {
  id: 'local-medium', name: 'Local medium',
  routes: [
    { task: 'vision', model_id: 'm1', provider: 'ollama', latency_p50_ms: 420 },
    { task: 'oracle', model_id: 'm1', provider: 'ollama', latency_p50_ms: 380 },
    { task: 'embedding', model_id: 'm2', provider: 'ollama', latency_p50_ms: 80 },
  ],
};

export const MOCK_SETTINGS: ProductSetting[] = [
  { key: 'dashboard_title', value: 'Inspectra Demo', description: 'Workspace title shown in the UI', category: 'general' },
  { key: 'artifacts_dir', value: 'demo-artifacts', description: 'Directory for run artifacts and evidence', category: 'general' },
  { key: 'theme', value: 'dark', description: 'UI theme (dark / light)', category: 'general' },
  { key: 'default_timeout_seconds', value: '60', description: 'Default timeout for each test step (seconds)', category: 'runtime' },
  { key: 'run_concurrency_limit', value: '2', description: 'Max concurrent validation runs', category: 'runtime' },
  { key: 'log_level', value: 'INFO', description: 'Backend log level (DEBUG / INFO / WARNING)', category: 'runtime' },
  { key: 'enable_runtime_doctor', value: 'true', description: 'Enable the Runtime Doctor readiness check', category: 'features' },
  { key: 'auto_index_artifacts', value: 'true', description: 'Auto-index new artifacts for search', category: 'features' },
];

export interface DemoWorkspace {
  projects: Project[];
  apps: AppTarget[];
  validationPacks: ValidationPack[];
  liveRuns: LiveRunRecord[];
  evidence: EvidenceFile[];
  reports: ReportRecord[];
  dashboard: DashboardSummary;
  health: HealthStatus;
  runtimeDoctor: RuntimeDoctorReport;
  connectors: ConnectorsResponse;
  memory: MemoryStats;
  hardware: HardwareProfile;
  providers: ModelProvider[];
  profile: ModelProfile;
  settings: ProductSetting[];
}

const DEMO_WORKSPACE: DemoWorkspace = {
  projects: MOCK_PROJECTS,
  apps: MOCK_APPS,
  validationPacks: MOCK_PACKS,
  liveRuns: MOCK_RUNS,
  evidence: MOCK_EVIDENCE,
  reports: MOCK_REPORTS,
  dashboard: MOCK_DASHBOARD,
  health: { status: 'ok', provenance: DEMO_PROVENANCE },
  runtimeDoctor: MOCK_DOCTOR,
  connectors: MOCK_CONNECTORS,
  memory: MOCK_MEMORY,
  hardware: MOCK_HARDWARE,
  providers: MOCK_PROVIDERS,
  profile: MOCK_PROFILE,
  settings: MOCK_SETTINGS,
};

/** Returns an isolated copy so callers cannot mutate the canonical demo data. */
export function generateDemoWorkspace(): DemoWorkspace {
  return JSON.parse(JSON.stringify(DEMO_WORKSPACE)) as DemoWorkspace;
}
