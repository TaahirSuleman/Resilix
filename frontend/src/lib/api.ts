import type { IncidentDetail, IncidentListResponse } from '../types/api'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
    ...options,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || response.statusText)
  }

  return response.json() as Promise<T>
}

export async function listIncidents(): Promise<IncidentListResponse> {
  return request<IncidentListResponse>('/incidents')
}

export async function getIncidentDetail(incidentId: string): Promise<IncidentDetail> {
  return request<IncidentDetail>(`/incidents/${incidentId}`)
}

export async function approveMerge(incidentId: string): Promise<IncidentDetail> {
  return request<IncidentDetail>(`/incidents/${incidentId}/approve-merge`, {
    method: 'POST',
  })
}
