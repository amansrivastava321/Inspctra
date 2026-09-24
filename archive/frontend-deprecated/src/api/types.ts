/** TypeScript interfaces matching qa_ai/product_backend/models.py exactly. */

export interface Project {
  id: string;
  name: string;
  description: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  tags?: string[];
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  tags?: string[];
}

export interface AppTarget {
  id: string;
  project_id: string;
  name: string;
  app_type: string;
  base_url?: string | null;
  description: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface AppTargetCreate {
  project_id: string;
  name: string;
  app_type: string;
  base_url?: string | null;
  description?: string;
  tags?: string[];
}

export interface AppTargetUpdate {
  name?: string;
  app_type?: string;
  base_url?: string | null;
  description?: string;
  tags?: string[];
}

export interface ValidationStep {
  step_id: string;
  order: number;
  description: string;
  action_type: string;
  target?: string | null;
  input_value?: string | null;
  expected_result?: string | null;
  timeout_seconds: number;
}

export interface ValidationStepCreate {
  description: string;
  action_type?: string;
  target?: string | null;
  input_value?: string | null;
  expected_result?: string | null;
  timeout_seconds?: number;
}

export interface ValidationPack {
  id: string;
  project_id: string;
  name: string;
  description: string;
  steps: ValidationStep[];
  created_at: string;
  updated_at: string;
}

export interface ValidationPackCreate {
  project_id: string;
  name: string;
  description?: string;
  steps?: ValidationStepCreate[];
}

export interface ValidationPackUpdate {
  name?: string;
  description?: string;
  steps?: ValidationStepCreate[];
}

export interface LiveRunRecord {
  id: string;
  pack_id: string;
  app_target_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  started_at?: string | null;
  completed_at?: string | null;
  step_results: StepResult[];
  error?: string | null;
  created_at: string;
}

export interface StepResult {
  step: number;
  status: string;
  notes?: string;
  action_type?: string;
  mode?: string;
}

export interface PermissionRecord {
  id: string;
  run_id: string;
  action: string;
  description: string;
  risk: string;
  status: 'pending' | 'approved' | 'denied';
  requested_at: string;
  resolved_at?: string | null;
  reason?: string | null;
}

export interface EvidenceFile {
  id: string;
  run_id: string;
  name: string;
  relative_path: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
}

export interface ReportRecord {
  id: string;
  run_id: string;
  name: string;
  format: string;
  relative_path: string;
  created_at: string;
}

export interface ConnectorInfo {
  connector_id: string;
  connector_type: string;
  ready: boolean;
  details: string;
  checked_at?: string;
}

export interface ConnectorsResponse {
  checked_at: string;
  connectors: ConnectorInfo[];
  total: number;
  ready: number;
}

export interface ProductSetting {
  key: string;
  value: string;
  updated_at: string;
}

export interface DashboardSummary {
  project_count: number;
  app_target_count: number;
  validation_pack_count: number;
  total_runs: number;
  runs_completed: number;
  runs_failed: number;
  runs_running: number;
  recent_runs: LiveRunRecord[];
  generated_at: string;
}

export interface RuntimeDoctorReport {
  generated_at?: string;
  platform?: string;
  python_version?: string;
  playwright_installed?: boolean;
  playwright_browsers_installed?: boolean;
  appium_client_installed?: boolean;
  npm_available?: boolean;
  appium_command_available?: boolean;
  appium_uiautomator2_installed?: boolean;
  appium_xcuitest_installed?: boolean;
  ollama_reachable?: boolean;
  ollama_models?: string[];
  ollama_configured_model?: string;
  ollama_vision_model_available?: boolean;
  appium_server_reachable?: boolean;
  appium_server_url?: string;
  readiness_score?: number;
  readiness_label?: string;
  missing_items?: string[];
  recommended_actions?: string[];
  driver_readiness?: DriverReadiness[];
  error?: string;
}

export interface DriverReadiness {
  app_type: string;
  driver_type: string;
  status: string;
  missing_deps: string[];
  setup_instructions: string[];
}

// SSE event shapes
export interface SSEStatusEvent {
  run_id: string;
  status: string;
  total_steps?: number;
  steps_passed?: number;
  steps_failed?: number;
  steps_total?: number;
  completed_at?: string;
}

export interface SSEStepStartEvent {
  run_id: string;
  step: number;
  total: number;
  description: string;
}

export interface SSEStepResultEvent {
  run_id: string;
  step: number;
  total: number;
  status: string;
  description: string;
  notes: string;
}
