export type Status = 'processing' | 'awaiting_approval' | 'merging' | 'resolved' | 'failed'
export type Severity = 'critical' | 'high' | 'medium' | 'low'
export type ApprovalStatus = 'pending' | 'approved' | 'not_required'
export type PrStatus = 'not_created' | 'pending_ci' | 'ci_passed' | 'merged'

export interface IncidentSummary {
  incident_id: string
  status: Status
  severity: Severity
  service_name: string
  created_at: string
  mttr_seconds?: number | null
  approval_status: ApprovalStatus
  pr_status: PrStatus
}

export interface TimelineEvent {
  event_type: string
  timestamp: string
  agent?: string | null
  details?: Record<string, unknown>
  duration_ms?: number | null
}

export interface ValidatedAlert {
  alert_id: string
  is_actionable: boolean
  severity: Severity
  service_name: string
  error_type: string
  error_rate: number
  affected_endpoints: string[]
  triggered_at: string
  enrichment?: Record<string, unknown>
  triage_reason: string
}

export interface Evidence {
  source: string
  timestamp: string
  content: string
  relevance: string
}

export interface ThoughtSignature {
  incident_id: string
  root_cause: string
  root_cause_category: string
  evidence_chain: Evidence[]
  affected_services: string[]
  confidence_score: number
  recommended_action: string
  target_repository?: string | null
  target_file?: string | null
  target_line?: number | null
  related_commits?: string[]
  investigation_summary: string
  investigation_duration_seconds: number
}

export interface JiraTicketResult {
  ticket_key: string
  ticket_url: string
  summary: string
  priority: string
  status: string
  created_at: string
}

export interface RemediationResult {
  success: boolean
  action_taken: string
  branch_name?: string | null
  pr_number?: number | null
  pr_url?: string | null
  pr_merged: boolean
  target_file?: string | null
  diff_old_line?: string | null
  diff_new_line?: string | null
  execution_time_seconds: number
  error_message?: string | null
}

export interface IncidentDetail extends IncidentSummary {
  resolved_at?: string | null
  validated_alert?: ValidatedAlert | null
  thought_signature?: ThoughtSignature | null
  jira_ticket?: JiraTicketResult | null
  remediation_result?: RemediationResult | null
  timeline: TimelineEvent[]
}

export interface IncidentListResponse {
  items: IncidentSummary[]
}

export interface HealthResponse {
  status: string
  app_version?: string | null
  build_sha?: string | null
  frontend_served?: boolean
}
