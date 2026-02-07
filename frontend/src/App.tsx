import React, { useEffect, useMemo, useState } from 'react'
import { SystemHealthStrip } from './components/SystemHealthStrip'
import { IncidentFeed } from './components/IncidentFeed'
import { IncidentDetail } from './components/IncidentDetail'
import { MOCK_INCIDENTS } from './types/ui'
import type { Incident, IncidentSummary } from './types/ui'
import { approveMerge, getHealth, getIncidentDetail, listIncidents } from './lib/api'
import { mapIncidentDetail, mapIncidentSummary } from './lib/mapper'
import { getBuildLabel } from './lib/version'

const POLL_INTERVAL = 5000

export function App() {
  const [incidents, setIncidents] = useState<IncidentSummary[]>([])
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null)
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isApproving, setIsApproving] = useState(false)
  const [buildLabel, setBuildLabel] = useState<string>(getBuildLabel())

  const usingFallback = Boolean(error)

  const activeIncidentCount = useMemo(() => {
    return incidents.filter((incident) => incident.status !== 'resolved' && incident.status !== 'failed').length
  }, [incidents])

  useEffect(() => {
    let active = true

    const loadIncidents = async () => {
      try {
        const data = await listIncidents()
        if (!active) return
        const mapped = data.items.map(mapIncidentSummary)
        setIncidents(mapped)
        setError(null)
        setIsLoading(false)

        if (!selectedIncidentId && mapped.length) {
          setSelectedIncidentId(mapped[0].id)
        }

        if (selectedIncidentId && !mapped.find((item) => item.id === selectedIncidentId)) {
          setSelectedIncidentId(mapped[0]?.id ?? null)
        }
      } catch (err) {
        if (!active) return
        setIncidents(MOCK_INCIDENTS)
        setError('Data temporarily unavailable. Displaying fallback data.')
        setIsLoading(false)
        if (!selectedIncidentId) {
          setSelectedIncidentId(MOCK_INCIDENTS[0]?.id ?? null)
        }
      }
    }

    loadIncidents()
    const interval = window.setInterval(loadIncidents, POLL_INTERVAL)

    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [selectedIncidentId])

  useEffect(() => {
    if (!selectedIncidentId) {
      setSelectedIncident(null)
      return
    }

    let active = true

    const loadDetail = async () => {
      if (usingFallback) {
        const mock = MOCK_INCIDENTS.find((incident) => incident.id === selectedIncidentId) ?? MOCK_INCIDENTS[0]
        if (active) {
          setSelectedIncident(mock)
        }
        return
      }

      try {
        const detail = await getIncidentDetail(selectedIncidentId)
        if (!active) return
        const mappedDetail = mapIncidentDetail(detail)
        setSelectedIncident(mappedDetail)
        setIncidents((prev) =>
          prev.map((item) => (item.id === mappedDetail.id ? { ...item, title: mappedDetail.title } : item)),
        )
      } catch (err) {
        if (!active) return
        setError('Data temporarily unavailable. Displaying fallback data.')
        const mock = MOCK_INCIDENTS.find((incident) => incident.id === selectedIncidentId) ?? MOCK_INCIDENTS[0]
        setSelectedIncident(mock)
      }
    }

    loadDetail()
    const interval = window.setInterval(loadDetail, POLL_INTERVAL)

    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [selectedIncidentId, usingFallback])

  useEffect(() => {
    let active = true
    const loadHealth = async () => {
      try {
        const health = await getHealth()
        if (!active) return
        const version = health.app_version || 'dev'
        const sha = health.build_sha || 'local'
        setBuildLabel(`${version} (${sha.slice(0, 7)})`)
      } catch {
        if (!active) return
        setBuildLabel(getBuildLabel())
      }
    }
    loadHealth()
    return () => {
      active = false
    }
  }, [])

  const handleApproveMerge = async () => {
    if (!selectedIncidentId || usingFallback) return
    setIsApproving(true)
    try {
      const detail = await approveMerge(selectedIncidentId)
      setSelectedIncident(mapIncidentDetail(detail))
      const list = await listIncidents()
      setIncidents(list.items.map(mapIncidentSummary))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Request failed'
      setError(`Approval failed. ${message}`)
    } finally {
      setIsApproving(false)
    }
  }

  return (
    <div className="h-screen w-full bg-gray-50 flex flex-col overflow-hidden font-sans text-gray-900">
      <SystemHealthStrip activeIncidents={activeIncidentCount} buildLabel={buildLabel} />

      <div className="flex-1 flex mt-12 overflow-hidden">
        {error ? (
          <div className="absolute top-16 right-6 z-20 rounded-md border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800 shadow-sm flex items-center gap-3">
            <span>{error}</span>
          </div>
        ) : null}

        <IncidentFeed
          incidents={incidents}
          selectedId={selectedIncidentId ?? ''}
          onSelect={setSelectedIncidentId}
          isLoading={isLoading}
        />

        <main className="flex-1 relative bg-white shadow-sm z-0">
          <IncidentDetail
            incident={selectedIncident}
            isLoading={isLoading}
            onApproveMerge={handleApproveMerge}
            isApproving={isApproving}
          />
        </main>
      </div>
    </div>
  )
}
