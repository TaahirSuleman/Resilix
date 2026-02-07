import React from 'react'
import { Activity, Server, Zap, AlertTriangle, Shield } from 'lucide-react'

interface SystemHealthStripProps {
  activeIncidents: number
  buildLabel?: string
}

export function SystemHealthStrip({ activeIncidents, buildLabel }: SystemHealthStripProps) {
  return (
    <div className="h-12 border-b border-gray-200 bg-white flex items-center px-4 justify-between fixed top-0 left-0 right-0 z-10">
      <div className="flex items-center gap-2">
        <Shield className="w-4 h-4 text-gray-900" />
        <span className="font-semibold text-gray-900 text-sm tracking-tight">Resilix</span>
      </div>
      <div className="flex items-center h-full">
        <MetricItem
          label="Uptime"
          value="99.97%"
          icon={<Activity className="w-3 h-3" />}
          status="good"
        />
        <div className="w-px h-6 bg-gray-100 mx-2" />
        <MetricItem
          label="Error Rate"
          value="0.12%"
          icon={<AlertTriangle className="w-3 h-3" />}
          status="warning"
        />
        <div className="w-px h-6 bg-gray-100 mx-2" />
        <MetricItem
          label="P99 Latency"
          value="245ms"
          icon={<Zap className="w-3 h-3" />}
          status="neutral"
        />
        <div className="w-px h-6 bg-gray-100 mx-2" />
        <MetricItem
          label="Active Incidents"
          value={String(activeIncidents)}
          icon={<Server className="w-3 h-3" />}
          status={activeIncidents > 0 ? 'critical' : 'good'}
        />
      </div>
      <div className="w-40 text-right">
        {buildLabel ? <span className="text-[10px] text-gray-400 tracking-wide">{buildLabel}</span> : null}
      </div>
    </div>
  )
}

interface MetricItemProps {
  label: string
  value: string
  icon: React.ReactNode
  status: 'good' | 'warning' | 'critical' | 'neutral'
}

function MetricItem({ label, value, icon, status }: MetricItemProps) {
  const badgeColors = {
    good: 'bg-green-50 text-green-700 border-green-100',
    warning: 'bg-amber-50 text-amber-700 border-amber-100',
    critical: 'bg-red-50 text-red-700 border-red-100',
    neutral: 'bg-gray-50 text-gray-700 border-gray-100',
  }
  return (
    <div className="flex items-center gap-3 px-2">
      <span className="text-[10px] uppercase tracking-wider font-medium text-gray-500">{label}</span>
      <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full border ${badgeColors[status]}`}>
        {icon}
        <span className="text-xs font-semibold tabular-nums">{value}</span>
      </div>
    </div>
  )
}
