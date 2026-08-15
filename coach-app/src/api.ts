import type {
  EntretienPanel,
  HomeState,
  JournalEntry,
  ProjectDetail,
  RoutineCheckResult,
  SessionResult,
} from './types'

const TOKEN_KEY = 'coach.access'
const REFRESH_KEY = 'coach.refresh'

export function storedToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = storedToken()
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  })

  if (response.status === 401) {
    const refreshed = await refresh()
    if (refreshed) return request<T>(path, init)
    throw new ApiError('Session expirée. Reconnecte-toi.', 401)
  }

  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: 'Erreur inconnue.' }))
    throw new ApiError(detail.detail ?? 'Erreur inconnue.', response.status)
  }

  if (response.status === 204) return undefined as T
  return response.json()
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function refresh(): Promise<boolean> {
  const token = localStorage.getItem(REFRESH_KEY)
  if (!token) return false
  const response = await fetch('/api/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh: token }),
  })
  if (!response.ok) return false
  const data = await response.json()
  localStorage.setItem(TOKEN_KEY, data.access)
  if (data.refresh) localStorage.setItem(REFRESH_KEY, data.refresh)
  return true
}

export async function login(username: string, password: string): Promise<void> {
  const response = await fetch('/api/auth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) throw new ApiError('Identifiants refusés.', response.status)
  const data = await response.json()
  localStorage.setItem(TOKEN_KEY, data.access)
  localStorage.setItem(REFRESH_KEY, data.refresh)
}

export function logout(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

export const api = {
  home: () => request<HomeState>('/home'),

  projects: () => request<ProjectDetail[]>('/projects'),

  journal: () => request<JournalEntry[]>('/journal'),

  fridge: () => request<{ id: number; text: string; created_at: string }[]>('/fridge'),

  startSession: (projectId: number, minutes: number) =>
    request<RunningSessionResponse>('/sessions/start', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId, minutes }),
    }),

  endSession: (id: number, note: string, nextAction: string) =>
    request<SessionResult>(`/sessions/${id}/end`, {
      method: 'POST',
      body: JSON.stringify({ note, next_action: nextAction }),
    }),

  abandonSession: (id: number) =>
    request<{ status: string }>(`/sessions/${id}/abandon`, { method: 'POST' }),

  completeStep: (id: number) =>
    request<{ id: number; state: string; boss_damage: number }>(`/steps/${id}/complete`, {
      method: 'POST',
    }),

  addIdea: (text: string) =>
    request<{ id: number; text: string }>('/fridge', {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),

  routines: () => request<EntretienPanel>('/routines'),

  checkRoutine: (id: number) =>
    request<RoutineCheckResult>(`/routines/${id}/check`, { method: 'POST' }),

  uncheckRoutine: (id: number) =>
    request<RoutineCheckResult>(`/routines/${id}/check`, { method: 'DELETE' }),

  startRelax: () =>
    request<{ started_at: string; ends_at: string }>('/relax/start', { method: 'POST' }),

  declareDayOff: (day: string) =>
    request<{ date: string; detail: string }>('/days-off', {
      method: 'POST',
      body: JSON.stringify({ date: day }),
    }),

  pushKey: () => request<{ public_key: string }>('/push/key'),

  subscribePush: (subscription: PushSubscriptionJSON, name: string, kind: 'pc' | 'phone') =>
    request<{ id: number; name: string }>('/push/subscribe', {
      method: 'POST',
      body: JSON.stringify({ subscription, name, kind }),
    }),
}

export interface RunningSessionResponse {
  id: number
  project: string
  color: string
  started_at: string
  planned_minutes: number
  mode: string
}
