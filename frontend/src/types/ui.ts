export type Status = 'investigating' | 'monitoring' | 'resolved' | 'failed'
export type Severity = 'critical' | 'warning' | 'info'

export interface TimelineEvent {
  id: string
  timestamp: string
  description: string
  type: 'alert' | 'action' | 'info' | 'success'
}

export interface EvidenceItem {
  id: string
  label: string
  type: 'log' | 'metric'
  content: string
}

export interface RemediationPlan {
  description: string
  codeDiff: {
    filename: string
    oldLine?: string
    newLine: string
  }
  approvalStatus: 'pending' | 'approved' | 'not_required'
  prStatus: 'not_created' | 'pending_ci' | 'ci_passed' | 'merged'
  prUrl?: string | null
  jiraUrl?: string | null
  jiraKey?: string | null
}

export interface IncidentSummary {
  id: string
  title: string
  service: string
  status: Status
  severity: Severity
  timestamp: string
  timeAgo: string
}

export interface Incident extends IncidentSummary {
  timeline: TimelineEvent[]
  evidence: EvidenceItem[]
  remediation: RemediationPlan
}

export const MOCK_INCIDENTS: Incident[] = [
  {
    id: 'inc-001',
    title: 'Database connection pool exhaustion',
    service: 'payments-service',
    status: 'investigating',
    severity: 'critical',
    timestamp: '2023-10-24T14:30:00Z',
    timeAgo: '12m ago',
    timeline: [
      {
        id: 't1',
        timestamp: '14:30:05',
        description: 'Alert triggered: Connection pool usage > 95%',
        type: 'alert',
      },
      {
        id: 't2',
        timestamp: '14:31:12',
        description: 'On-call engineer paged via PagerDuty',
        type: 'info',
      },
      {
        id: 't3',
        timestamp: '14:33:45',
        description: 'Connection spike detected from checkout-api',
        type: 'info',
      },
      {
        id: 't4',
        timestamp: '14:35:00',
        description: 'Pool limit reached (50/50 connections)',
        type: 'alert',
      },
    ],
    evidence: [
      {
        id: 'e1',
        label: 'Postgres Connection Logs',
        type: 'log',
        content: `[ERROR] FATAL: remaining connection slots are reserved for non-replication superuser connections
[ERROR] pq: sorry, too many clients already
[INFO]  Connection attempt from 10.0.2.45 rejected`,
      },
      {
        id: 'e2',
        label: 'Pool Utilization Metric',
        type: 'metric',
        content: `metric: pg_stat_activity_count
value: 50
threshold: 50
status: CRITICAL`,
      },
    ],
    remediation: {
      description:
        'Increase connection pool size and add connection timeout to prevent hanging connections.',
      codeDiff: {
        filename: 'config/database.yml',
        oldLine: 'pool_size: 50',
        newLine: 'pool_size: 100\nconnect_timeout: 5000',
      },
      approvalStatus: 'pending',
      prStatus: 'pending_ci',
      prUrl: null,
      jiraUrl: null,
      jiraKey: null,
    },
  },
  {
    id: 'inc-002',
    title: 'Elevated P99 latency on API gateway',
    service: 'api-gateway',
    status: 'monitoring',
    severity: 'warning',
    timestamp: '2023-10-24T14:08:00Z',
    timeAgo: '34m ago',
    timeline: [
      {
        id: 't1',
        timestamp: '14:08:22',
        description: 'Latency threshold breached (P99 > 500ms)',
        type: 'alert',
      },
      {
        id: 't2',
        timestamp: '14:09:00',
        description: 'Auto-scaling triggered: +2 replicas added',
        type: 'action',
      },
      {
        id: 't3',
        timestamp: '14:15:30',
        description: 'Partial recovery observed, latency stabilizing at 300ms',
        type: 'success',
      },
    ],
    evidence: [
      {
        id: 'e1',
        label: 'Latency Percentiles',
        type: 'metric',
        content: `p50: 45ms
p95: 120ms
p99: 650ms (THRESHOLD > 500ms)
request_count: 12,450 req/s`,
      },
    ],
    remediation: {
      description:
        'Deploy cached response layer for high-frequency read endpoints.',
      codeDiff: {
        filename: 'middleware/cache.ts',
        newLine: 'app.use("/api/v1/products", cacheMiddleware({ ttl: 60 }));',
      },
      approvalStatus: 'not_required',
      prStatus: 'merged',
      prUrl: null,
      jiraUrl: null,
      jiraKey: null,
    },
  },
  {
    id: 'inc-003',
    title: 'Memory leak in batch processor',
    service: 'batch-processor',
    status: 'resolved',
    severity: 'info',
    timestamp: '2023-10-24T12:30:00Z',
    timeAgo: '2h ago',
    timeline: [
      {
        id: 't1',
        timestamp: '12:30:00',
        description: 'Memory usage alert: Heap > 90%',
        type: 'alert',
      },
      {
        id: 't2',
        timestamp: '12:35:00',
        description: 'Heap dump captured automatically',
        type: 'info',
      },
      {
        id: 't3',
        timestamp: '12:45:00',
        description: 'Leak identified in image-processing module',
        type: 'info',
      },
      {
        id: 't4',
        timestamp: '13:10:00',
        description: 'Hotfix patch deployed (v2.4.1)',
        type: 'action',
      },
      {
        id: 't5',
        timestamp: '13:20:00',
        description: 'Memory usage normalized. Incident resolved.',
        type: 'success',
      },
    ],
    evidence: [
      {
        id: 'e1',
        label: 'Heap Analysis Summary',
        type: 'log',
        content: `Total Heap: 4096MB
Used: 3850MB (94%)
Largest Retainer: ImageBuffer[] @ 0x7f8a9b (2.1GB)
Status: LEAK_DETECTED`,
      },
    ],
    remediation: {
      description:
        'Object reference cleanup in processQueue() to ensure buffers are released.',
      codeDiff: {
        filename: 'workers/image_processor.js',
        oldLine: 'this.bufferCache.push(image);',
        newLine:
          '// Fixed: Explicitly clear buffer after processing\nimage.destroy();\nthis.bufferCache = null;',
      },
      approvalStatus: 'approved',
      prStatus: 'merged',
      prUrl: null,
      jiraUrl: null,
      jiraKey: null,
    },
  },
]
