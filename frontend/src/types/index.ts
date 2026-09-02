/** Shared types matching backend pydantic/JSON responses. */

export interface SourceInfo {
  source_id: string
  filename: string
  grain: string
  cadence: string
  uploaded_at: string
  derived_dataset_count?: number
}

export type DetectedRole = 'temporal' | 'numerical' | 'categorical' | 'identifier'

export interface ColumnProfile {
  name: string
  dtype: string
  null_count: number
  null_ratio: number
  cardinality: number
  cardinality_ratio: number
  is_unique: boolean
  detected_role: DetectedRole
  sample_values: unknown[]
}

export interface ProfileResult {
  source_id: string
  source: SourceInfo
  created_at: string
  cached: boolean
  profile: {
    row_count: number
    columns: ColumnProfile[]
  }
}

// --- Semantic contract (Phase 2) ---

export type AggregationType = 'sum' | 'avg' | 'rate' | 'count'
export type CalendarGranularity = 'day' | 'week' | 'month'

export interface KpiDefinition {
  column: string
  aggregation: AggregationType
  sliceable_by: string[]
}

export interface HierarchyPair {
  parent: string
  child: string
}

export interface SemanticContract {
  grain?: string | null
  kpi_definitions: KpiDefinition[]
  hierarchies: HierarchyPair[]
  calendar: {
    time_column: string | null
    granularity: CalendarGranularity
  }
  thresholds: {
    materiality_std_devs: number
    min_support_rows: number
  }
  access_tags: Record<string, string>
  columns_by_role?: {
    measure: string[]
    dimension: string[]
    time: string[]
    identifier: string[]
  }
}

export interface ContractResponse {
  source_id: string
  contract: SemanticContract
  updated_at: string
  built: boolean
}

// --- Data quality (Phase 3) ---

export type IssueSeverity = 'high' | 'medium' | 'low'

export interface QualityIssue {
  column: string
  issue_type: string
  severity: IssueSeverity
  affected_row_count: number
}

export interface QualityReport {
  score: number
  issues: QualityIssue[]
  row_count: number
  column_count: number
}

export interface QualityResponse {
  source_id: string
  cached: boolean
  created_at: string
  report: QualityReport
}

// --- Canonical model (Phase 4) ---

export type Json = Record<string, unknown>

export interface CanonicalDatasetInfo {
  dataset_id: string
  name?: string | null
  created_at: string
  row_count: number
  column_count: number
  columns: string[]
  preview?: Json[]
  source_ids?: string[]
  join_config?: Json | null
  page?: number
  total_pages?: number
}

// --- KPI engine (Phase 5) ---

export type KpiStatus = 'valid' | 'low-data' | 'invalid'

export interface KpiInfo {
  kpi_id: string
  dataset_id: string
  name: string
  measure: string
  aggregation: string
  slice_columns: string[]
  time_column: string | null
  status: KpiStatus
  reason: string
  materiality?: number
}

export interface TrendPoint {
  period: string
  value: number
}

export interface KpiComputation {
  value: number | null
  trend: TrendPoint[]
  baseline: number | null
  benchmark: number | null
  confidence_interval: { lower: number; upper: number } | null
  period_count: number
}

export interface KpiComputeResponse {
  kpi_id: string
  definition: KpiInfo
  cached: boolean
  computation: KpiComputation
}

export interface BatchKpiResult {
  kpi_id: string
  definition: KpiInfo
  computation: KpiComputation | null
  cached: boolean
  error: string | null
}

export interface ComputeAllResponse {
  dataset_id: string
  computed: number
  failed: number
  failures: { kpi_id: string; error: string }[]
  results: BatchKpiResult[]
}

export interface BatchAnomalyResult {
  kpi_id: string
  definition: KpiInfo
  anomalies: AnomalyDetections | null
  findings: AnomalyFinding[]
  cached: boolean
  detected_at: string | null
  error: string | null
}

export interface RunAllAnomaliesResponse {
  dataset_id: string
  processed: number
  failed: number
  failures: { kpi_id: string; error: string }[]
  results: BatchAnomalyResult[]
}

export interface BatchDriverResult {
  kpi_id: string
  definition: KpiInfo
  total_movement: number | null
  before: { period: string; value: number } | null
  after: { period: string; value: number } | null
  findings: DriverFinding[]
  error: string | null
}

export interface RunAllDriversResponse {
  dataset_id: string
  processed: number
  failed: number
  failures: { kpi_id: string; error: string }[]
  results: BatchDriverResult[]
}

export interface DatasetListEntry {
  dataset_id: string
  name?: string | null
  source_ids: string[]
  created_at: string
}

// --- Anomaly detection (Phase 6) ---

export interface AnomalyPoint {
  index: number
  period: string | null
  value: number | null
}

export interface AnomalyDetections {
  change_points: AnomalyPoint[]
  control_limit_breaches: AnomalyPoint[]
  outliers: AnomalyPoint[]
}

export interface AnomalyResponse {
  kpi_id: string
  cached: boolean
  detected_at: string
  definition: KpiInfo
  anomalies: AnomalyDetections
  findings?: AnomalyFinding[]
}

// --- Drivers & evidence (Phase 7) ---

export interface DriverSlice {
  slice: string
  before: number
  after: number
  contribution: number
  share_pct: number
  direction: 'up' | 'down' | 'flat'
}

export interface EvidenceRecord {
  finding_type: string
  method: string
  statistic: number | null
  p_value_or_effect_size: number | null
  source_freshness: string
  lineage: string[]
  built_at: string
}

export interface DriverFinding {
  finding_id: string
  kpi_id: string
  finding_type: string
  finding: {
    key: string
    dimension: string
    total_movement: number
    before: { period: string; value: number }
    after: { period: string; value: number }
    slices: DriverSlice[]
    reconciliation_residual: number
    anomaly_context: { change_points: number; outliers: number }
  }
  evidence: EvidenceRecord
  confidence?: ConfidenceResult
  created_at: string
}

export interface DriversResponse {
  kpi_id: string
  definition: KpiInfo
  computation_summary: {
    value: number | null
    baseline: number | null
    benchmark: number | null
  }
  total_movement: number
  before: { period: string; value: number }
  after: { period: string; value: number }
  findings: DriverFinding[]
}

export interface EvidenceResponse {
  finding_id: string
  kpi_id: string
  finding_type: string
  finding: DriverFinding['finding'] | Record<string, unknown>
  evidence: EvidenceRecord
  created_at: string
}

// --- Confidence & personas (Phase 8) ---

export type ConfidenceLevel = 'high' | 'medium' | 'low' | 'abstain'

export interface ConfidenceResult {
  level: ConfidenceLevel
  reasons: string[]
  missing_evidence: string[]
}

export interface Persona {
  persona_id: string
  name: string
  access: {
    description?: string
    allowed_domains?: string[] | null
    restricted_roles?: string[]
    restricted_columns?: string[]
    max_slices?: number | null
  }
}

/** A finding whose payload was replaced by an abstain message. */
export interface AbstainPayload {
  abstained: true
  message: string
  missing_evidence: string[]
  reasons: string[]
}

export interface ConfidenceBadgeProps {
  confidence: ConfidenceResult
}

/** Per-detection finding on the anomaly page (Phase 8). */
export interface AnomalyFinding {
  kpi_id: string
  finding_type: string
  finding: {
    key: string
    method: string
    index: number
    period: string | null
    value: number | null
    direction: string
    kpi_status?: string
    period_count?: number
  }
  evidence: EvidenceRecord
  confidence: ConfidenceResult
}

// --- Insights & recommendation packages (Phase 9) ---

export interface InsightResponse {
  insight_id: string
  kpi_id: string
  kpi_name: string
  bullets: string[]
  previous_bullets: string[] | null
  deterministic: boolean
  confidence: ConfidenceResult | null
  generated_at: string
}

export interface RecommendationPackage {
  driver: {
    dimension: string
    slice: string
    direction: string
    contribution: number
    share_pct: number
    type: string
  }
  controllable_lever: string
  candidate_action: string
  expected_impact: string
  owner: string
  confidence: { level: string; reasons: string[] }
  monitoring_plan: string
  evidence_summary?: {
    method?: string | null
    finding_type?: string | null
    source_freshness?: string | null
    lineage?: string[]
  }
}

export interface RecommendationPackageResponse {
  package_id: string
  kpi_id: string
  package: RecommendationPackage
  created_at: string
  llm_call: boolean
}

// --- LLM recommendation layer (Phase 10) ---

export interface LlmCallMetadata {
  call_id: string
  kpi_id?: string
  package_hash?: string
  prompt_tokens: number
  completion_tokens: number
  latency_ms: number
  cost_usd: number
  cached: boolean
  created_at?: string
  model?: string
}

export interface RecommendationResponse {
  kpi_id: string
  recommendation_bullets: string[]
  package: RecommendationPackage
  llm_call_metadata: LlmCallMetadata
}

export interface LlmLedgerStage {
  stage: string
  llm_used: boolean
}

export interface LlmLedgerResponse {
  stages: LlmLedgerStage[]
  summary: {
    total_stages: number
    llm_stages: number
    deterministic_stages: number
  }
  last_call: LlmCallMetadata | null
  totals: { llm_calls: number; cost_usd: number }
}

// --- Feedback, telemetry & workspace (Phase 11) ---

export interface FeedbackRow {
  feedback_id: string
  target_type: 'insight' | 'recommendation'
  target_id: string
  verdict: 'confirm' | 'correct' | 'reject'
  note: string | null
  created_at: string
  driver_type?: string
}

export interface StageLatency {
  stage: string
  calls: number
  avg_latency_ms: number
  min_latency_ms: number
  max_latency_ms: number
}

export interface LlmCallOverTime {
  created_at: string
  prompt_tokens: number
  completion_tokens: number
  cost_usd: number
  cached: boolean
}

export interface TelemetrySummary {
  stage_latencies: StageLatency[]
  llm: {
    total_calls: number
    total_prompt_tokens: number
    total_completion_tokens: number
    total_cost_usd: number
    avg_latency_ms: number
    cached_calls: number
    cache_hit_rate: number
  }
  llm_calls_over_time: LlmCallOverTime[]
  feedback_adjustments: Record<string, number>
}
