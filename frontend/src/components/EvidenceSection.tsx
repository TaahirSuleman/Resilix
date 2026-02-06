import React from 'react'
import { EvidenceItem } from '../types/ui'
import { FileText, BarChart2 } from 'lucide-react'

interface EvidenceSectionProps {
  evidence: EvidenceItem[]
}

export function EvidenceSection({ evidence }: EvidenceSectionProps) {
  if (!evidence.length) {
    return <div className="text-xs text-gray-400">No evidence collected yet.</div>
  }

  return (
    <div className="space-y-4">
      {evidence.map((item) => (
        <div key={item.id} className="group">
          <div className="flex items-center gap-2 mb-2 text-xs font-medium text-gray-500 uppercase tracking-wide">
            {item.type === 'log' ? <FileText className="w-3 h-3" /> : <BarChart2 className="w-3 h-3" />}
            {item.label}
          </div>
          <div className="bg-gray-50 border border-gray-200 rounded-md p-3 overflow-x-auto">
            <pre className="text-xs font-mono text-gray-700 whitespace-pre-wrap leading-relaxed">{item.content}</pre>
          </div>
        </div>
      ))}
    </div>
  )
}
