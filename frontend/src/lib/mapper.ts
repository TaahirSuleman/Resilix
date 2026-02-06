import type {
  IncidentDetail,
  IncidentSummary,
  Severity as ApiSeverity,
  Status as ApiStatus,
} from '../types/api'
import type {
  EvidenceItem,
  Incident,
  IncidentSummary as UiIncidentSummary,
  Severity as UiSeverity,
  Status as UiStatus,
  TimelineEvent as UiTimelineEvent,
} from '../types/ui'
import { formatTimeAgo, formatTime } from './format'

const EVENT_LABELS: Record<string, string> = {
  incident_created: 'Alert triggered',
  alert_validated: 'Alert validated',
  investigation_started: 'Investigation started',
  evidence_collected: 'Evidence collected',
  root_cause_identified: 'Root cause identified',
  ticket_created: 'Jira ticket created',
  fix_generated: 'Fix generated',
  pr_created: 'Pull request created',
  pr_merged: 'Pull request merged',
  incident_resolved: 'Incident resolved',
  escalated_to_human: 'Escalated to human',
}

const EVENT_KIND: Record<string, UiTimelineEvent['type']> = {
  incident_created: 'alert',
  alert_validated: 'alert',
  investigation_started: 'info',
  evidence_collected: 'info',
  root_cause_identified: 'info',
  ticket_created: 'action',
  fix_generated: 'action',
  pr_created: 'action',
  pr_merged: 'success',
  incident_resolved: 'success',
  escalated_to_human: 'alert',
}

function toUiSeverity(value: ApiSeverity): UiSeverity {
  switch (value) {
    case 'critical':
      return 'critical'
    case 'high':
    case 'medium':
      return 'warning'
    case 'low':
    default:
      return 'info'
  }
}

function toUiStatus(value: ApiStatus): UiStatus {
  switch (value) {
    case 'processing':
      return 'investigating'
    case 'awaiting_approval':
    case 'merging':
      return 'monitoring'
    case 'resolved':
      return 'resolved'
    case 'failed':
    default:
      return 'failed'
  }
}

function buildTitle(detail: IncidentDetail | IncidentSummary) {
  const alert = (detail as IncidentDetail).validated_alert
  const signature = (detail as IncidentDetail).thought_signature
  if (alert?.error_type) return alert.error_type
  if (signature?.root_cause) return signature.root_cause
  return detail.incident_id
}

function buildTimeline(detail: IncidentDetail): UiTimelineEvent[] {
  if (!detail.timeline || detail.timeline.length === 0) return []
  return detail.timeline.map((event, index) => {
    const label = EVENT_LABELS[event.event_type] ?? event.event_type
    const agent = event.agent ? ` (${event.agent})` : ''
    const extra = event.details ? Object.entries(event.details).slice(0, 1) : []
    const detailText = extra.length ? ` — ${extra.map(([key, value]) => `${key}: ${String(value)}`).join(', ')}` : ''
    return {
      id: `${event.event_type}-${index}`,
      timestamp: formatTime(event.timestamp),
      description: `${label}${agent}${detailText}`,
      type: EVENT_KIND[event.event_type] ?? 'info',
    }
  })
}

function buildEvidence(detail: IncidentDetail): EvidenceItem[] {
  const signature = detail.thought_signature
  if (!signature || !signature.evidence_chain) return []

  return signature.evidence_chain.map((item, index) => ({
    id: `${item.source}-${index}`,
    label: `${item.source.toUpperCase()} Evidence`,
    type: item.source === 'logs' ? 'log' : 'metric',
    content: item.content,
  }))
}

export function mapIncidentSummary(summary: IncidentSummary): UiIncidentSummary {
  return {
    id: summary.incident_id,
    title: summary.incident_id,
    service: summary.service_name,
    status: toUiStatus(summary.status),
    severity: toUiSeverity(summary.severity),
    timestamp: summary.created_at,
    timeAgo: formatTimeAgo(summary.created_at),
  }
}

export function mapIncidentDetail(detail: IncidentDetail): Incident {
  const title = buildTitle(detail)
  const targetFile = detail.thought_signature?.target_file ?? 'unknown'
  const action = detail.remediation_result?.action_taken ?? detail.thought_signature?.recommended_action ?? 'pending'
  const remediationDescription = detail.remediation_result?.success
    ? `Action executed: ${action}.`
    : detail.remediation_result?.error_message
      ? `Action failed: ${detail.remediation_result.error_message}`
      : `Action planned: ${action}.`

  return {
    id: detail.incident_id,
    title,
    service: detail.service_name,
    status: toUiStatus(detail.status),
    severity: toUiSeverity(detail.severity),
    timestamp: detail.created_at,
    timeAgo: formatTimeAgo(detail.created_at),
    timeline: buildTimeline(detail),
    evidence: buildEvidence(detail),
    remediation: {
      description: remediationDescription,
      codeDiff: {
        filename: targetFile,
        newLine: `// ${action}`,
      },
      approvalStatus: detail.approval_status,
      prStatus: detail.pr_status,
      prUrl: detail.remediation_result?.pr_url ?? null,
      jiraUrl: detail.jira_ticket?.ticket_url ?? null,
      jiraKey: detail.jira_ticket?.ticket_key ?? null,
    },
  }
}
