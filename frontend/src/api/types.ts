/** Types aligned with backend schemas (Issue, IssueOverview, AgentRun, Decision, AuditEvent, etc.). */

export type IssueStatus = 'open' | 'triaged' | 'closed'
export type IssueSource = 'manual' | 'edit_check' | 'listing'
export type IssueDomain = string
export type IssueType = 'deterministic' | 'llm_required'

export interface Issue {
  issue_id: string
  source: IssueSource
  domain: IssueDomain
  subject_id: string
  fields: string[]
  description: string
  issue_type: IssueType
  evidence_payload: Record<string, unknown>
  status: IssueStatus
  created_at: string
}

export type Action = 'QUERY_SITE' | 'DATA_FIX' | 'MEDICAL_REVIEW' | 'IGNORE' | 'OTHER'
export type Severity = 'LOW' | 'MEDIUM' | 'HIGH'

export interface AgentRunSummary {
  run_id: string
  created_at: string
  severity: Severity
  action: Action
  confidence: number
}

export interface AgentRecommendation {
  severity: Severity
  action: Action
  confidence: number
  rationale: string
  missing_info: string[]
  citations: string[]
  tool_results: Record<string, unknown>
  draft_message: string | null
}

export interface AgentRun {
  run_id: string
  issue_id: string
  created_at: string
  rules_version: string
  recommendation: AgentRecommendation
}

export type DecisionType = 'APPROVE' | 'OVERRIDE' | 'EDIT'

export interface Decision {
  decision_id: string
  issue_id: string
  run_id: string
  decision_type: DecisionType
  final_action: Action
  final_text: string
  reviewer: string
  reason: string | null
  specify: string | null
  timestamp: string
}

export interface DecisionCreate {
  run_id: string
  decision_type: DecisionType
  final_action: Action
  final_text: string
  reviewer: string
  reason?: string | null
  specify?: string | null
}

export interface IssueOverview {
  issue: Issue
  latest_run: AgentRunSummary | null
  latest_decision: Decision | null
  recent_audit_events: AuditEvent[]
  runs_count: number
  decisions_count: number
}

export interface AuditEvent {
  event_id: string
  correlation_id: string
  event_type: string
  actor: string
  issue_id: string | null
  run_id: string | null
  payload: Record<string, unknown>
  created_at: string
}

export interface IngestResponse {
  created: number
  issue_ids: string[]
  errors: string[]
}
