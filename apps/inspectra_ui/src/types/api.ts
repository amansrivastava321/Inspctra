// ─── Shared ───────────────────────────────────────────────────────────────────

export type Verdict = 'pass' | 'fail' | 'unclear' | 'blocked' | 'skipped' | 'running' | 'pending' | 'dry_run' | 'capability_gap';
export type ReadinessState = 'ready' | 'missing' | 'perm' | 'skipped' | 'partial' | 'usable';
export type EvidenceStrength = 'strong' | 'medium' | 'weak' | 'missing';
export type Provenance =
  | 'REAL_EXECUTION'
  | 'DRY_RUN'
  | 'MIXED'
  | 'SIMULATED'
  | 'DEMO_EXAMPLE'
  | 'UNAVAILABLE';

export interface HealthStatus {
  status: string;
  provenance: Provenance;
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

export interface DashboardSummary {
  project_count: number;
  app_target_count: number;
  validation_pack_count: number;
  total_runs: number;
  runs_completed: number;
  runs_failed: number;
  runs_running: number;
  recent_runs: LiveRunRecord[];
  projects_count?: number;
  apps_count?: number;
  packs_count?: number;
  total_runs_7d?: number;
  passed_runs_7d?: number;
  recent_failed_run?: DashboardFailedRun | null;
  failure_reasons?: DashboardFailureReason[];
  pass_rate_7d?: DashboardDailyBucket[];
  coverage?: DashboardCoverage;
  last_run_at?: string | null;
  last_run_provenance?: Provenance;
  generated_at?: string;
  workspace_health?: number;
  latest_verdict?: Verdict;
  evidence_strength?: EvidenceStrength;
  open_issues?: number;
  capability_gaps?: CapabilityGap[];
  runtime_readiness?: RuntimeReadinessItem[];
  pass_rate_history?: PassRatePoint[];
  provenance?: Provenance;
}

export interface DashboardDailyBucket {
  date: string;
  passed: number;
  failed: number;
  total: number;
  pass_rate: number | null;
  provenance?: Provenance;
}

export interface DashboardFailureReason {
  category: string;
  count: number;
  run_ids: string[];
  provenance?: Provenance;
}

export interface DashboardCoverage {
  with_packs: number;
  total: number;
  percentage: number | null;
  last_pack_created_at?: string | null;
  provenance?: Provenance;
}

export interface DashboardFailedRun {
  id: string;
  pack_id: string;
  app_target_id: string;
  app_name?: string | null;
  pack_name?: string | null;
  failure_reason: string;
  failed_at: string;
  provenance?: Provenance;
  screenshot_evidence_id?: string | null;
  screenshot_provenance?: Provenance;
}

export interface CapabilityGap {
  id: string;
  title: string;
  description: string;
  severity: 'high' | 'medium' | 'low';
  action?: string;
  action_label?: string;
}

export interface RuntimeReadinessItem {
  name: string;
  status: ReadinessState;
}

export interface PassRatePoint {
  date: string;
  rate: number;
}

// ─── Projects ─────────────────────────────────────────────────────────────────

export interface Project {
  id: string;
  name: string;
  description?: string;
  created_at?: string;
  updated_at?: string;
  provenance?: Provenance;
}

export interface ProjectCreate { name: string; description?: string; }
export interface ProjectUpdate { name?: string; description?: string; }

// ─── App Targets ──────────────────────────────────────────────────────────────

export type AppType = 'web' | 'mobile' | 'desktop' | 'api' | 'ai_app' | '3rd_party';
export type PlatformType = 'macos' | 'windows' | 'linux' | 'ios' | 'android' | 'web';

export interface AppTarget {
  id: string;
  project_id?: string;
  name: string;
  app_type: AppType;
  platform?: PlatformType;
  working_directory?: string;
  launch_command?: string;
  window_title?: string;
  bundle_id?: string;
  app_url?: string;
  base_url?: string;
  description?: string;
  tags?: string[];
  status?: ReadinessState;
  pass_rate?: number;
  total_runs?: number;
  open_issues?: number;
  last_run_at?: string;
  created_at?: string;
  updated_at?: string;
  // Source / discovery fields
  source_type?: SourceType;
  source_path?: string;
  source_url?: string;
  discovery_id?: string;
  detected_stack?: string;
  provenance?: Provenance;
}

// ─── Discovery ────────────────────────────────────────────────────────────────

export type SourceType = 'local_folder' | 'web_url' | 'api_base_url' | 'github_url' | 'manual';
export type DiscoveryStatus = 'pending' | 'scanning' | 'complete' | 'failed' | 'unsupported';
export type Confidence = 'high' | 'medium' | 'low' | 'unknown';

export interface DetectedValue {
  value: string;
  confidence: Confidence;
  source: string;
}

export interface DetectedLaunchCommand {
  command: string;
  confidence: Confidence;
  source: string;
}

export interface AuditStrategySuggestion {
  strategy: string;
  confidence: Confidence;
  reason: string;
}

export interface AppFingerprint {
  files_scanned: number;
  depth_reached: number;
  detected_files: string[];
  package_name?: string;
  package_scripts?: Record<string, string>;
  has_node_modules: boolean;
  has_git: boolean;
  truncated: boolean;
}

export interface DiscoveryResult {
  id: string;
  project_id: string;
  source_type: SourceType;
  local_path?: string;
  url?: string;
  status: DiscoveryStatus;
  suggested_name?: DetectedValue;
  suggested_app_type?: DetectedValue;
  suggested_platform?: DetectedValue;
  suggested_launch_command?: DetectedLaunchCommand;
  suggested_base_url?: DetectedValue;
  detected_stack: DetectedValue[];
  audit_strategy?: AuditStrategySuggestion;
  fingerprint?: AppFingerprint;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface AppSourceInput {
  project_id: string;
  source_type: SourceType;
  local_path?: string;
  url?: string;
}

// ─── App Map ──────────────────────────────────────────────────────────────────

export interface EntryPoint {
  label: string;
  command?: string;
  url?: string;
  confidence: Confidence;
  source: string;
}

export interface RuntimeConnector {
  connector_type: string;
  tool: string;
  confidence: Confidence;
  note: string;
}

export interface TestableSurface {
  name: string;
  surface_type: string;
  confidence: Confidence;
  note: string;
}

export interface AppMapRiskArea {
  label: string;
  risk_level: 'critical' | 'high' | 'medium' | 'low';
  description: string;
  detection_basis: string;
}

export interface AppMapCapabilityGap {
  id: string;
  title: string;
  description: string;
  resolution: string;
  severity: 'high' | 'medium' | 'low';
}

export interface AppMapDraft {
  app_map_id: string;
  app_id: string;
  discovery_id?: string;
  app_name: string;
  app_type: string;
  map_type: 'fingerprint_based_draft';   // always this — never claim deep analysis
  confidence: Confidence;
  detected_stack: string[];
  source_type?: string;
  source_path?: string;
  source_url?: string;
  entry_points: EntryPoint[];
  launch_commands: string[];
  runtime_connectors: RuntimeConnector[];
  testable_surfaces: TestableSurface[];
  risk_areas: AppMapRiskArea[];
  capability_gaps: AppMapCapabilityGap[];
  created_at: string;
  updated_at: string;
}

export interface AppCreateFromDiscoveryRequest {
  discovery_id: string;
  name: string;
  app_type: string;
  platform?: string;
  base_url?: string;
  launch_command?: string;
  description?: string;
  tags?: string[];
  working_directory?: string;
}

export interface AppTargetCreate {
  project_id?: string;
  name: string;
  app_type: AppType;
  platform?: PlatformType;
  working_directory?: string;
  launch_command?: string;
  window_title?: string;
  bundle_id?: string;
  app_url?: string;
}

export interface AppTargetUpdate extends Partial<AppTargetCreate> {}

// ─── Validation Packs ─────────────────────────────────────────────────────────

export interface ValidationPack {
  id: string;
  name: string;
  description?: string;
  project_id?: string;
  app_id?: string;          // linked app target (null = generic pack)
  target_app_ids?: string[];
  target_names?: string[];
  schedule?: string;
  readiness?: ReadinessState;
  last_run_at?: string;
  last_verdict?: Verdict;
  avg_pass_rate?: number;
  total_flows?: number;
  flows?: PackFlow[];
  coverage?: number;
  history?: boolean[];  // last 10 runs: true=pass
  created_at?: string;
  updated_at?: string;
  steps?: Record<string, unknown>[];  // backend pack steps
  provenance?: Provenance;
}

export interface PackFlow {
  id: string;
  name: string;
  platform?: string;
  evidence_count?: number;
  confidence?: number;
  verdict?: Verdict;
}

export interface ValidationPackCreate {
  name: string;
  description?: string;
  project_id?: string;
  target_app_ids?: string[];
}

export interface ValidationPackUpdate extends Partial<ValidationPackCreate> {}

// ─── Live Runs ────────────────────────────────────────────────────────────────

// Mirrors the read-only comparison response, including explicit nullable fields.
export type RunComparisonProvenanceBasis = 'stored' | 'inferred' | 'unavailable';
export interface RunComparisonScope { pack_id: string; app_target_id: string; }
export interface RunComparisonObservation {
  run_id: string;
  status: string;
  execution_mode: string | null;
  provenance: Provenance;
  provenance_basis: RunComparisonProvenanceBasis;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  retest_of: string | null;
}
export interface RunComparisonChronology {
  state: 'forward' | 'reverse' | 'same_time' | 'unavailable';
  basis: 'completed_at' | 'started_at' | 'created_at' | 'unavailable';
  baseline_time: string | null;
  comparison_time: string | null;
}
export interface RunComparisonCitation {
  run_id: string;
  step_id: string | null;
  provenance: Provenance;
  provenance_basis: RunComparisonProvenanceBasis;
  evidence_ids: string[];
}
export interface RunComparisonMetric {
  key: 'duration_ms' | 'response_time_ms' | 'status_code';
  unit: 'ms' | 'http_status';
  baseline_value: number | null;
  comparison_value: number | null;
  delta: number | null;
  reason: string | null;
}
export interface RunComparisonEvidenceSummary {
  complete: boolean;
  baseline_count: number | null;
  comparison_count: number | null;
  baseline_type_counts: Record<string, number>;
  comparison_type_counts: Record<string, number>;
  hash_comparison: 'same_hash' | 'different_hash' | 'unavailable';
}
export interface RunComparisonFailureSignature {
  algorithm: 'history_v1';
  state: 'same_signature' | 'different_signature' | 'unavailable';
  reason: string | null;
}
export interface RunComparisonDisplay {
  error: string | null;
  failure_reason: string | null;
  notes: string | null;
  expected: string | null;
  actual: string | null;
}
export interface RunStepComparison {
  step_id: string | null;
  identity_state: 'matched' | 'baseline_only' | 'comparison_only' | 'identity_unavailable' | 'identity_conflict';
  comparison_state: 'factual' | 'informational' | 'unavailable';
  reason_codes: string[];
  baseline_status: string | null;
  comparison_status: string | null;
  baseline_provenance: Provenance | null;
  comparison_provenance: Provenance | null;
  transition: 'passed_to_failed' | 'failed_to_passed' | 'passed_to_passed' | 'failed_to_failed'
    | 'passed_to_inconclusive' | 'failed_to_inconclusive' | 'inconclusive_to_passed'
    | 'inconclusive_to_failed' | 'inconclusive_to_inconclusive' | 'not_comparable';
  baseline_citation: RunComparisonCitation | null;
  comparison_citation: RunComparisonCitation | null;
  baseline_display: RunComparisonDisplay | null;
  comparison_display: RunComparisonDisplay | null;
  metric_comparisons: RunComparisonMetric[];
  evidence_comparison: RunComparisonEvidenceSummary;
  failure_signature_comparison: RunComparisonFailureSignature;
}
export interface RunComparisonSummaryCounts {
  matched: number;
  passed_to_failed: number;
  failed_to_passed: number;
  passed_to_passed: number;
  failed_to_failed: number;
  inconclusive_transitions: number;
  baseline_only: number;
  comparison_only: number;
  identity_unavailable: number;
  identity_conflict: number;
  not_comparable: number;
}
export interface RunComparisonCoverage {
  complete: boolean;
  evidence_limit_per_run: number;
  step_limit_per_run: number;
  result_bytes_limit_per_run: number;
  omissions: string[];
}
export interface RunComparisonComparability {
  state: 'partial' | 'unavailable';
  configuration_snapshot_available: false;
  reason_codes: string[];
}
export interface RunComparisonResponse {
  schema_version: '1';
  baseline_run_id: string;
  comparison_run_id: string;
  selection_mode: 'explicit';
  scope: RunComparisonScope;
  baseline: RunComparisonObservation;
  comparison: RunComparisonObservation;
  chronology: RunComparisonChronology;
  provenance_compatibility: 'compatible' | 'partial' | 'informational' | 'unavailable';
  comparability: RunComparisonComparability;
  comparability_warnings: string[];
  coverage: RunComparisonCoverage;
  summary_counts: RunComparisonSummaryCounts;
  step_comparisons: RunStepComparison[];
}

export interface LiveRunRecord {
  id: string;
  pack_id?: string;
  pack_name?: string;
  app_id?: string;
  app_name?: string;
  app_target_id?: string;
  platform?: string;
  status: 'running' | 'completed' | 'failed' | 'cancelled' | 'pending' | 'blocked';
  error?: string | null;
  verdict?: Verdict;
  confidence?: number;
  elapsed_ms?: number;
  started_at?: string;
  created_at?: string;
  finished_at?: string;
  completed_at?: string;
  operator?: string;
  step_results: StepResult[];
  evidence_count?: number;
  permission_scope?: number;
  retest_of?: string;
  execution_mode?: 'manual' | 'automated';
  steps?: ValidationRunStep[];
  provenance?: Provenance;
}

export interface ValidationRunStep {
  step_id: string;
  action_type: string;
  description?: string;
  target?: string;
  value?: string;
  expected?: string;
  method?: string;
  url?: string;
  headers?: Record<string, unknown>;
  query_params?: Record<string, unknown>;
  body_json?: unknown;
  expected_status?: number;
  expected_json_path?: string;
  expected_value?: unknown;
  optional?: boolean;
  budget_ms?: number;
  warn_ms?: number;
  metric_name?: string;
}

export interface StepResult {
  id?: string;
  index: number;
  name: string;
  status: 'passed' | 'failed' | 'error' | 'unclear' | 'blocked' | 'running' | 'pending' | 'skipped' | 'dry_run_only' | 'capability_gap';
  confidence?: number;
  duration_ms?: number;
  evidence_count?: number;
  error?: string;
  expected?: unknown;
  actual?: unknown;
  step?: number;
  step_id?: string;
  action_type?: string;
  method?: string;
  url?: string;
  status_code?: number;
  response_time_ms?: number;
  assertion_result?: boolean | null;
  optional?: boolean;
  actual_result?: string;
  notes?: string;
  failure_reason?: string;
  tester_name?: string;
  evidence_ids?: string[];
  completed_at?: string;
  started_at?: string;
  budget_ms?: number;
  warn_ms?: number;
  metric_name?: string;
  warning?: boolean;
  security_findings?: any[];
  provenance?: Provenance;
}

// ─── Events (SSE) ─────────────────────────────────────────────────────────────

export interface RunEvent {
  type: 'step_start' | 'step_end' | 'screenshot' | 'log' | 'api_call' | 'db_delta'
      | 'ai_oracle' | 'permission_request' | 'verdict' | 'heartbeat' | 'error';
  step_id?: string;
  step?: number;
  step_name?: string;
  status?: string;
  confidence?: number;
  evidence_id?: string;
  message?: string;
  ts: string;
}

export interface DurableRunEvent {
  id: number;
  run_id: string;
  step_index?: number;
  step_id?: string;
  event_type: 'step_started' | 'step_completed' | 'evidence_captured' | 'error';
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}

// ─── Deterministic Run History ───────────────────────────────────────────────

export interface RunHistoryCitation {
  run_id: string;
  step_id: string | null;
  completed_at: string | null;
  provenance: Provenance;
  evidence_ids: string[];
}

export interface RunHistoryScope {
  pack_id: string;
  app_target_id: string;
  terminal_statuses: string[];
  exact_match: boolean;
  configuration_snapshot_available: boolean;
}

export interface RunHistoryItem {
  run_id: string;
  status: string;
  outcome: string | null;
  execution_mode: string;
  provenance: Provenance;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  included_in_failure_rate: boolean;
  exclusion_reason: string | null;
  citation: RunHistoryCitation;
}

export interface RunHistoryFailureRate {
  failed: number;
  total: number;
  value: number;
  citations: RunHistoryCitation[];
}

export interface RunStepHistory {
  step_id: string | null;
  passed: number;
  failed: number;
  inconclusive: number;
  total: number;
  citations: RunHistoryCitation[];
  insufficient_identity: boolean;
}

export interface RepeatedFailureSignature {
  signature: string;
  step_id: string;
  category: string;
  error_code: string;
  error: string;
  failure_reason: string;
  notes: string;
  occurrences: number;
  citations: RunHistoryCitation[];
}

export interface RunHistoryResponse {
  run_id: string;
  scope: RunHistoryScope;
  considered_runs: number;
  excluded_runs: number;
  exclusions_by_reason: Record<string, number>;
  insufficient_history: boolean;
  comparability_warnings: string[];
  last_passed: RunHistoryItem | null;
  last_failed: RunHistoryItem | null;
  failure_rate: RunHistoryFailureRate;
  step_history: RunStepHistory[];
  repeated_failure_signatures: RepeatedFailureSignature[];
  recent_runs: RunHistoryItem[];
  manual_observations: RunHistoryItem[];
}

// ─── Permissions ──────────────────────────────────────────────────────────────

export interface PermissionRecord {
  id: string;
  run_id: string;
  action_type: string;
  description: string;
  what_will_happen?: string[];
  what_will_not?: string;
  risk_level?: 'low' | 'medium' | 'high';
  status: 'pending' | 'approved' | 'denied';
  created_at?: string;
}

// ─── Evidence ─────────────────────────────────────────────────────────────────

export type EvidenceType =
  | 'screenshot' | 'log' | 'api' | 'db' | 'ai' | 'trace'
  | 'console' | 'network' | 'page_html' | 'manual_confirmation'
  | 'api_request' | 'api_response' | 'api_assertion'
  | 'performance_summary' | 'web_timing' | 'api_timing'
  | 'accessibility_summary' | 'accessibility_violations'
  | 'visual_diff'
  | 'security_findings';

export interface EvidenceFile {
  id: string;
  run_id: string;
  step_id?: string;
  evidence_type: EvidenceType;
  type?: EvidenceType;
  strength?: EvidenceStrength;
  name?: string;
  title?: string;
  description?: string;
  path?: string;
  relative_path?: string;
  file_path?: string;
  mime_type?: string;
  size_bytes?: number;
  sha256?: string;
  metadata_json?: Record<string, unknown>;
  content_preview?: string;
  created_at?: string;
  provenance?: Provenance;
}

export interface AIEvaluationNote {
  evaluation_id: string;
  run_id: string;
  step_id?: string;
  verdict_assessment: string;
  suggested_verdict?: string | null;
  confidence?: number | null;
  summary?: string | null;
  evidence_used?: string[];
  missing_evidence?: string[];
  risk_flags?: string[];
  rationale?: string | null;
  generation_source?: string | null;
  generation_metadata?: Record<string, unknown> | null;
  created_at?: string;
}

export interface AIRootCauseEvidenceRef {
  type: string;
  id: string;
  field: string;
  provenance: Provenance;
}

export interface AIRootCauseSuggestion {
  suggestion_id: string;
  analysis_id: string;
  run_id: string;
  step_id?: string | null;
  rank: number;
  title: string;
  possible_cause: string;
  category: string;
  confidence: number;
  evidence_refs: AIRootCauseEvidenceRef[];
  supporting_signals: string[];
  contradicting_signals: string[];
  missing_evidence: string[];
  recommended_verification: string[];
  suggested_owner_area: string;
  source_provenance: Provenance;
  generation_source: string;
  generation_metadata: Record<string, unknown>;
  authoritative: boolean;
  created_at: string;
}

export interface AIRootCauseSuggestionBatch {
  analysis_id: string;
  run_id: string;
  status: 'suggested' | 'inconclusive';
  authoritative: boolean;
  source_provenance: Provenance;
  generation_source: string;
  generation_metadata: Record<string, unknown>;
  missing_evidence: string[];
  suggestions: AIRootCauseSuggestion[];
  created_at: string;
}

export interface AIRootCauseRequest {
  step_id?: string;
}

// ─── Reports ──────────────────────────────────────────────────────────────────

export interface ReportRecord {
  id: string;
  run_id: string;
  name?: string;
  format?: string;
  relative_path?: string;
  app_name?: string;
  pack_name?: string;
  verdict?: Verdict | 'pending';
  summary?: string;
  findings?: ReportFinding[];
  pass_count?: number;
  fail_count?: number;
  unclear_count?: number;
  evidence_count?: number;
  api_step_count?: number;
  api_pass_count?: number;
  api_fail_count?: number;
  api_avg_response_time_ms?: number;
  perf_total_checks?: number;
  perf_passed_budgets?: number;
  perf_failed_budgets?: number;
  perf_avg_page_load_ms?: number;
  perf_avg_api_response_time_ms?: number;
  perf_slowest_check_ms?: number;
  a11y_total_checks?: number;
  a11y_passed_checks?: number;
  a11y_failed_checks?: number;
  a11y_total_violations?: number;
  visual_total_checks?: number;
  visual_passed_checks?: number;
  visual_failed_checks?: number;
  visual_avg_diff_percent?: number;
  visual_worst_diff_percent?: number;
  security_total_checks?: number;
  security_passed_checks?: number;
  security_failed_checks?: number;
  security_total_findings?: number;
  security_critical_findings?: number;
  security_warning_findings?: number;
  created_at?: string;
  provenance?: Provenance;
}

export interface ReportFinding {
  id: string;
  title: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  status?: Verdict;
  description?: string;
  step_name?: string;
}

// ─── Connectors ───────────────────────────────────────────────────────────────

export type ConnectorStatus = 'ready' | 'missing' | 'perm' | 'skipped' | 'partial';

export interface Connector {
  id: string;
  name: string;
  connector_type: string;
  status: ConnectorStatus;
  detail?: string;
  host?: string;
  port?: number;
  last_checked_at?: string;
  provenance?: Provenance;
}

export interface ConnectorsResponse {
  connectors: Connector[];
  app_name?: string;
  app_id?: string;
  provenance?: Provenance;
}

// ─── Runtime Doctor ───────────────────────────────────────────────────────────

export interface RuntimeDoctorReport {
  readiness_score: number;
  readiness_band: ReadinessState;
  components: DoctorComponent[];
  things_to_fix?: DoctorFix[];
  summary: { ready: number; missing: number; perm: number; skipped: number };
  needs_mobile?: boolean; // false = global mode (no app connected / no mobile target)
  provenance?: Provenance;
}

export interface DoctorComponent {
  name: string;
  status: ReadinessState | 'skipped';
  version?: string;
  detail?: string;
  provenance?: Provenance;
}

export interface DoctorFix {
  id: string;
  title: string;
  status: 'missing' | 'perm' | 'partial';
  description?: string;
  commands?: string[];
  action_label?: string;
  risk?: 'low' | 'medium' | 'high';
  time_estimate?: string;
  disk_estimate?: string;
  provenance?: Provenance;
}

export interface DoctorSetupAction {
  id: string;
  title: string;
  commands: string[];
  time_estimate?: string;
  disk_estimate?: string;
  network?: string;
  risk?: string;
}

// ─── Models ───────────────────────────────────────────────────────────────────

export interface ModelProvider {
  id: string;
  name: string;
  status: 'ready' | 'missing' | 'partial';
  models?: InstalledModel[];
}

export interface InstalledModel {
  id: string;
  name: string;
  provider: string;
  size_gb?: number;
  status: 'ready' | 'missing' | 'downloading';
}

export interface ModelRoute {
  task: string;
  model_id: string;
  provider: string;
  latency_p50_ms?: number;
  cost_per_call?: number;
}

export interface ModelProfile {
  id: string;
  name: string;
  description?: string;
  routes: ModelRoute[];
}

export interface HardwareProfile {
  platform: string;
  cpu_cores: number;
  ram_gb: number;
  gpu?: string;
  vram_gb?: number;
  recommended_profile?: string;
}

// ─── Memory ───────────────────────────────────────────────────────────────────

export interface MemoryStats {
  scope_id: string;
  fingerprint_count: number;
  pattern_count: number;
  trajectory_count: number;
  embedding_count: number;
  baseline_id?: string;
  last_ingested_at?: string;
}

export interface MemoryPattern {
  id: string;
  canonical_template: string;
  pattern_type?: string;
  frequency: number;
  confidence: number;
  last_seen?: string;
}

// ─── Settings ─────────────────────────────────────────────────────────────────

export interface ProductSetting {
  key: string;
  value: string;
  description?: string;
  category?: string;
}

// ─── Test Plans ───────────────────────────────────────────────────────────────

export type TestType =
  | 'positive' | 'negative' | 'edge_case' | 'regression'
  | 'security' | 'accessibility' | 'performance' | 'data_integrity'
  | 'permission' | 'sync_offline' | 'api_contract' | 'visual' | 'ai_behavior';

export type AutomationStatus =
  | 'ready' | 'needs_selector' | 'needs_credentials' | 'needs_permission'
  | 'blocked' | 'manual_only' | 'capability_gap';

export type SafetyLevel = 'safe' | 'caution' | 'destructive' | 'external_cost' | 'real_user_impact';

export type TestPriority = 'P0' | 'P1' | 'P2';
export type TestRisk = 'critical' | 'high' | 'medium' | 'low';

export interface TestCase {
  test_case_id: string;
  plan_id: string;
  pack_id: string;
  app_id?: string;
  flow_name: string;
  title: string;
  description?: string;
  test_type: TestType;
  priority: TestPriority;
  risk_level: TestRisk;
  preconditions: string[];
  steps: string[];
  expected_result: string;
  expected_evidence: string[];
  pass_criteria: string;
  fail_criteria: string;
  automation_status: AutomationStatus;
  safety_level: SafetyLevel;
  requires_permission: boolean;
  tags: string[];
  enabled: boolean;
  confidence?: number;
  rationale?: string;
  generation_source?: string;
  created_at?: string;
  updated_at?: string;
  test_steps?: TestCaseStep[];
}

export interface TestCaseStep {
  step_id: string;
  case_id: string;
  step_order: number;
  action_type: string;
  target?: string;
  value?: string;
  expected?: string;
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  url?: string;
  headers?: Record<string, unknown>;
  query_params?: Record<string, unknown>;
  body_json?: unknown;
  expected_status?: number;
  expected_json_path?: string;
  expected_value?: unknown;
  timeout_ms: number;
  optional: boolean;
  notes?: string;
  budget_ms?: number;
  warn_ms?: number;
  metric_name?: string;
  approve_baseline?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface TestCaseStepCreate {
  action_type: string;
  target?: string;
  value?: string;
  expected?: string;
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  url?: string;
  headers?: Record<string, unknown>;
  query_params?: Record<string, unknown>;
  body_json?: unknown;
  expected_status?: number;
  expected_json_path?: string;
  expected_value?: unknown;
  timeout_ms?: number;
  optional?: boolean;
  notes?: string;
  budget_ms?: number;
  warn_ms?: number;
  metric_name?: string;
  approve_baseline?: boolean;
}

export interface TestCaseStepUpdate extends Partial<TestCaseStepCreate> {}

export interface TestPlan {
  plan_id: string;
  pack_id: string;
  app_id?: string;
  generated_from: string;
  coverage_summary: Record<string, number>;
  risk_summary: Record<string, number>;
  test_cases: TestCase[];
  created_at: string;
  updated_at: string;
}

export interface TestCaseCreate {
  flow_name?: string;
  title: string;
  description?: string;
  test_type?: TestType;
  priority?: TestPriority;
  risk_level?: TestRisk;
  preconditions?: string[];
  steps?: string[];
  expected_result?: string;
  expected_evidence?: string[];
  pass_criteria?: string;
  fail_criteria?: string;
  automation_status?: AutomationStatus;
  safety_level?: SafetyLevel;
  requires_permission?: boolean;
  tags?: string[];
}

export interface TestCaseUpdate extends Partial<TestCaseCreate> {
  enabled?: boolean;
}

// ─── Backend Status ───────────────────────────────────────────────────────────

export type BackendStatus = 'online' | 'offline' | 'degraded';

// ─── AI Test Plan Generation ──────────────────────────────────────────────────

export interface AIProposedTestStep {
  step_id?: string;
  action_type: string;
  target?: string;
  value?: string;
  expected?: string;
  timeout_ms?: number;
  optional?: boolean;
  notes?: string;
  confidence?: number;
  rationale?: string;
  method?: string;
  url?: string;
  headers?: Record<string, any>;
  query_params?: Record<string, any>;
  body_json?: any;
  expected_status?: number;
  expected_json_path?: string;
  expected_value?: any;
  budget_ms?: number;
  warn_ms?: number;
  metric_name?: string;
}

export interface AIProposedTestCase {
  test_case_id?: string;
  flow_name?: string;
  title: string;
  objective?: string;
  description?: string;
  priority?: string;
  type?: string;
  test_type?: string;
  risk_level?: string;
  preconditions?: string[];
  steps?: string[];
  expected_result?: string;
  expected_evidence?: string[];
  pass_criteria?: string;
  fail_criteria?: string;
  automation_status?: string;
  safety_level?: string;
  requires_permission?: boolean;
  tags?: string[];
  enabled?: boolean;
  confidence: number;
  rationale: string;
  test_steps?: AIProposedTestStep[];
}

export interface AITestPlanPreview {
  preview_id?: string;
  pack_id: string;
  app_id?: string | null;
  generated_from?: string;
  generation_source: string;
  generation_metadata?: Record<string, any>;
  coverage_summary?: Record<string, number>;
  risk_summary?: Record<string, number>;
  test_cases: AIProposedTestCase[];
  created_at?: string;
  updated_at?: string;
  safety_redaction_metadata?: Record<string, any>;
}

export interface AITestPlanAcceptRequest {
  test_cases: AIProposedTestCase[];
  force?: boolean;
}
