import React from 'react'
import { IncidentSummary } from '../types/ui'
import { motion } from 'framer-motion'
import { AlertCircle, Clock, CheckCircle2 } from 'lucide-react'

interface IncidentFeedProps {
  incidents: IncidentSummary[]
  selectedId: string
  onSelect: (id: string) => void
  isLoading: boolean
  onUseMock: () => void
}

export function IncidentFeed({ incidents, selectedId, onSelect, isLoading, onUseMock }: IncidentFeedProps) {
  return (
    <div className="w-80 border-r border-gray-200 bg-white h-full overflow-y-auto flex flex-col">
      <div className="p-4 border-b border-gray-100 flex items-center justify-between sticky top-0 bg-white/95 backdrop-blur-sm z-10">
        <h2 className="text-sm font-semibold text-gray-900">Incidents</h2>
        <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full text-xs font-medium">
          {incidents.length}
        </span>
      </div>

      <div className="flex-1 p-2 space-y-1">
        {isLoading && incidents.length === 0 ? (
          <div className="text-xs text-gray-400 px-3 py-2">Loading incidents...</div>
        ) : null}
        {!isLoading && incidents.length === 0 ? (
          <div className="text-xs text-gray-500 px-3 py-4 space-y-3">
            <p>No incidents yet. Trigger a webhook or load demo data.</p>
            <button
              className="text-xs font-semibold text-blue-600 hover:text-blue-700"
              onClick={onUseMock}
            >
              Load demo incidents
            </button>
          </div>
        ) : null}
        {incidents.map((incident) => (
          <IncidentItem
            key={incident.id}
            incident={incident}
            isSelected={selectedId === incident.id}
            onClick={() => onSelect(incident.id)}
          />
        ))}
      </div>
    </div>
  )
}

function IncidentItem({
  incident,
  isSelected,
  onClick,
}: {
  incident: IncidentSummary
  isSelected: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`
        relative w-full text-left p-3 rounded-md transition-all duration-200 outline-none group
        ${isSelected ? 'bg-blue-50/50' : 'hover:bg-gray-50'}
      `}
    >
      {isSelected && (
        <motion.div
          layoutId="active-incident"
          className="absolute left-0 top-0 bottom-0 w-[3px] bg-blue-600 rounded-l-md"
          initial={{
            opacity: 0,
          }}
          animate={{
            opacity: 1,
          }}
          transition={{
            duration: 0.2,
          }}
        />
      )}

      {!isSelected && (
        <div className={`absolute left-0 top-3 bottom-3 w-[3px] rounded-r-full ${getStatusColor(incident.severity)}`} />
      )}

      <div className="pl-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-medium text-gray-500">{incident.service}</span>
          <span className="text-[10px] text-gray-400 flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {incident.timeAgo}
          </span>
        </div>

        <h3 className={`text-sm font-medium mb-2 line-clamp-2 ${isSelected ? 'text-blue-900' : 'text-gray-900'}`}>
          {incident.title}
        </h3>

        <div className="flex items-center gap-2">
          <StatusBadge status={incident.status} />
        </div>
      </div>
    </button>
  )
}

function getStatusColor(severity: IncidentSummary['severity']) {
  switch (severity) {
    case 'critical':
      return 'bg-red-500'
    case 'warning':
      return 'bg-amber-500'
    case 'info':
      return 'bg-blue-500'
    default:
      return 'bg-gray-300'
  }
}

function StatusBadge({ status }: { status: IncidentSummary['status'] }) {
  const styles = {
    investigating: 'bg-red-100 text-red-700',
    monitoring: 'bg-amber-100 text-amber-700',
    resolved: 'bg-green-100 text-green-700',
    failed: 'bg-gray-200 text-gray-700',
  }
  const icons = {
    investigating: <AlertCircle className="w-3 h-3" />,
    monitoring: <Clock className="w-3 h-3" />,
    resolved: <CheckCircle2 className="w-3 h-3" />,
    failed: <AlertCircle className="w-3 h-3" />,
  }
  return (
    <span
      className={`
      inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide
      ${styles[status]}
    `}
    >
      {icons[status]}
      {status}
    </span>
  )
}
