import React from 'react'
import { Incident } from '../types/ui'
import { Timeline } from './Timeline'
import { EvidenceSection } from './EvidenceSection'
import { RemediationSection } from './RemediationSection'
import { motion } from 'framer-motion'
import { AlertOctagon, Clock, Server } from 'lucide-react'
import { formatUtcTimestamp } from '../lib/format'

interface IncidentDetailProps {
  incident: Incident | null
  isLoading: boolean
  onApproveMerge: () => void
  isApproving: boolean
}

export function IncidentDetail({ incident, isLoading, onApproveMerge, isApproving }: IncidentDetailProps) {
  if (isLoading && !incident) {
    return <div className="flex items-center justify-center h-full text-sm text-gray-400">Loading incident...</div>
  }

  if (!incident) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400">
        Select an incident to view details.
      </div>
    )
  }

  return (
    <motion.div
      key={incident.id}
      initial={{
        opacity: 0,
        y: 10,
      }}
      animate={{
        opacity: 1,
        y: 0,
      }}
      transition={{
        duration: 0.3,
        ease: 'easeOut',
      }}
      className="flex-1 h-full overflow-y-auto bg-white"
    >
      <div className="max-w-4xl mx-auto p-8 pb-20">
        <header className="mb-10">
          <div className="flex items-center gap-3 mb-4">
            <span
              className={`
              px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wide border
              ${getSeverityStyles(incident.severity)}
            `}
            >
              {incident.severity}
            </span>
            <span className="text-gray-300">|</span>
            <div className="flex items-center gap-1.5 text-gray-500 text-sm">
              <Server className="w-4 h-4" />
              <span className="font-medium">{incident.service}</span>
            </div>
            <span className="text-gray-300">|</span>
            <div className="flex items-center gap-1.5 text-gray-400 text-sm">
              <Clock className="w-4 h-4" />
              <span>{formatUtcTimestamp(incident.timestamp)}</span>
            </div>
          </div>

          <h1 className="text-2xl font-bold text-gray-900 mb-2 leading-tight">{incident.title}</h1>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span>Incident ID:</span>
            <code className="bg-gray-100 px-1.5 py-0.5 rounded text-gray-700 font-mono text-xs">{incident.id}</code>
            <span className="text-gray-300">|</span>
            <span className="inline-flex items-center gap-1 text-gray-500">
              <AlertOctagon className="h-4 w-4" />
              {incident.status}
            </span>
          </div>
        </header>

        <div className="space-y-10">
          <section>
            <SectionHeader title="Timeline" />
            <Timeline events={incident.timeline} />
          </section>

          <section>
            <SectionHeader title="Evidence & Logs" />
            <EvidenceSection evidence={incident.evidence} />
          </section>

          <section>
            <SectionHeader title="Remediation Plan" />
            <RemediationSection plan={incident.remediation} onApproveMerge={onApproveMerge} isApproving={isApproving} />
          </section>
        </div>
      </div>
    </motion.div>
  )
}

function SectionHeader({ title }: { title: string }) {
  return (
    <div className="flex items-center gap-4 mb-6">
      <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider bg-gray-50 px-3 py-1 rounded-full border border-gray-100">
        {title}
      </h2>
      <div className="h-px bg-gray-100 flex-1" />
    </div>
  )
}

function getSeverityStyles(severity: Incident['severity']) {
  switch (severity) {
    case 'critical':
      return 'bg-red-50 text-red-700 border-red-100'
    case 'warning':
      return 'bg-amber-50 text-amber-700 border-amber-100'
    case 'info':
      return 'bg-blue-50 text-blue-700 border-blue-100'
  }
}
