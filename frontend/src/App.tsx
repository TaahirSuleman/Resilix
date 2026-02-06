import React, { useEffect, useMemo, useState } from 'react'
import { SystemHealthStrip } from './components/SystemHealthStrip'
import { IncidentFeed } from './components/IncidentFeed'
import { IncidentDetail } from './components/IncidentDetail'
import { MOCK_INCIDENTS } from './types/ui'
import type { Incident, IncidentSummary } from './types/ui'
import { approveMerge, getIncidentDetail, listIncidents } from './lib/api'
import { mapIncidentDetail, mapIncidentSummary } from './lib/mapper'

const POLL_INTERVAL = 5000

export function App() {
  const [incidents, setIncidents] = useState<IncidentSummary[]>([])
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null)
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [useMock, setUseMock] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isApproving, setIsApproving] = useState(false)

  const usingMock = useMock || Boolean(error)

  const activeIncidentCount = useMemo(() => {
    return incidents.filter((incident) => incident.status !== 'resolved' && incident.status !== 'failed').length
  }, [incidents])

  useEffect(() => {
    let active = true

    const loadIncidents = async () => {
      if (useMock) {
        setIncidents(MOCK_INCIDENTS)
        setIsLoading(false)
        if (!selectedIncidentId) {
          setSelectedIncidentId(MOCK_INCIDENTS[0]?.id ?? null)
        }
        return
      }

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
        setError('API unreachable. Showing mock data.')
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
  }, [selectedIncidentId, useMock])

  useEffect(() => {
    if (!selectedIncidentId) {
      setSelectedIncident(null)
      return
    }

    let active = true

    const loadDetail = async () => {
      if (usingMock) {
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
        setError('Unable to load incident detail. Using mock data.')
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
  }, [selectedIncidentId, usingMock])

  const handleApproveMerge = async () => {
    if (!selectedIncidentId || usingMock) return
    setIsApproving(true)
    try {
      const detail = await approveMerge(selectedIncidentId)
      setSelectedIncident(mapIncidentDetail(detail))
      const list = await listIncidents()
      setIncidents(list.items.map(mapIncidentSummary))
    } catch (err) {
      setError('Approval failed. Check the API response and try again.')
    } finally {
      setIsApproving(false)
    }
  }

  const handleUseMock = () => {
    setUseMock(true)
    setError('Showing demo data.')
    setIncidents(MOCK_INCIDENTS)
    setSelectedIncidentId(MOCK_INCIDENTS[0]?.id ?? null)
  }

  const handleUseLive = () => {
    setUseMock(false)
    setError(null)
  }

  return (
    <div className="h-screen w-full bg-gray-50 flex flex-col overflow-hidden font-sans text-gray-900">
      <SystemHealthStrip activeIncidents={activeIncidentCount} />

      <div className="flex-1 flex mt-12 overflow-hidden">
        {error ? (
          <div className="absolute top-16 right-6 z-20 rounded-md border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800 shadow-sm flex items-center gap-3">
            <span>{error}</span>
            {useMock ? (
              <button className="text-xs font-semibold text-amber-900" onClick={handleUseLive}>
                Return to live
              </button>
            ) : null}
          </div>
        ) : null}

        <IncidentFeed
          incidents={incidents}
          selectedId={selectedIncidentId ?? ''}
          onSelect={setSelectedIncidentId}
          isLoading={isLoading}
          onUseMock={handleUseMock}
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
