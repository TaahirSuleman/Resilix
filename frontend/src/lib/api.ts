import type { HealthResponse, IncidentDetail, IncidentListResponse } from '../types/api'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

function summarizeErrorBody(body: string): string {
  const text = body.trim()
  if (!text) return 'Request failed'
  try {
    const parsed = JSON.parse(text)
    if (typeof parsed?.detail === 'string') return parsed.detail
    if (typeof parsed?.message === 'string') return parsed.message
  } catch {
    // Non-JSON response.
  }
  return text.slice(0, 180)
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
    ...options,
  })

  if (!response.ok) {
    const message = summarizeErrorBody(await response.text())
    throw new Error(`HTTP ${response.status}: ${message}`)
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

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}
