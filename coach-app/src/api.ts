import type {
  Briefing,
  DebriefSuggestion,
  Derive,
  EntretienPanel,
  Interview,
  ProgressionPanel,
  SeasonReport,
  SeasonState,
  GardesPanel,
  HomeState,
  JournalEntry,
  ProjectDetail,
  ProjectImportResult,
  ProjectPreview,
  Revue,
  RoutineCheckResult,
  SessionResult,
  WeeklyPanel,
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

  briefing: () => request<Briefing>('/briefing'),

  progression: () => request<ProgressionPanel>('/progression'),

  seasonState: () => request<SeasonState>('/season'),

  /** `early` clôt une saison **en cours** au titre du §14 : au-delà de cinq
   *  jours d'arrêt, repartir à neuf vaut mieux que traîner un retard
   *  irrattrapable. Explicite, parce que ce chemin perd la mise. */
  closeSeason: (early = false) =>
    request<SeasonReport>('/season/close', {
      method: 'POST',
      body: JSON.stringify({ early }),
    }),

  openSeason: (body: { modifier: string; phantom: string; stake: number }) =>
    request<{ index: number; name: string }>('/season/open', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  equipCard: (key: string) =>
    request<{ equipped: Record<string, string> }>(`/loot/${key}/equip`, { method: 'POST' }),

  toggleRelic: (key: string) =>
    request<ProgressionPanel['relics']>(`/relics/${key}/toggle`, { method: 'POST' }),

  startInterview: () => request<Interview>('/interviews', { method: 'POST' }),

  replyInterview: (id: number, answer: string) =>
    request<Interview>(`/interviews/${id}`, {
      method: 'POST',
      body: JSON.stringify({ answer }),
    }),

  importInterview: (id: number) =>
    request<{ id: number; name: string; slot: number | null }>(`/interviews/${id}/import`, {
      method: 'POST',
    }),

  debrief: (id: number, note: string) =>
    request<DebriefSuggestion>(`/sessions/${id}/debrief`, {
      method: 'POST',
      body: JSON.stringify({ note }),
    }),

  journal: () => request<JournalEntry[]>('/journal'),

  /** Les sept constats du §13.5, déjà faits, du plus urgent au moins urgent. */
  detections: () => request<Derive[]>('/detections'),

  weekly: () => request<WeeklyPanel>('/weekly'),

  /** Ouvre la revue de la semaine si elle n'existe pas — les questions sont
   *  calculées à ce moment-là, depuis les constats du §13.5. */
  review: () => request<Revue>('/review'),

  answerReview: (index: number, texte: string) =>
    request<Revue>('/review/answer', {
      method: 'POST',
      body: JSON.stringify({ index, texte }),
    }),

  closeReview: () => request<Revue>('/review', { method: 'POST' }),

  /** Applique le contrat proposé. Jamais automatique (§17). */
  applyContract: () =>
    request<{ changes: { projet: string; avant: number; apres: number }[]; revue: Revue }>(
      '/review/contract',
      { method: 'POST' },
    ),

  /** Demande l'arrêt du bilan. Ne coupe rien avant 24 h (§4.7). */
  requestWeeklyStop: () =>
    request<{ actif: boolean; effective_le: string | null; detail: string }>('/weekly/disable', {
      method: 'POST',
    }),

  /** Annule la demande. Immédiat : seul l'arrêt coûte du temps. */
  cancelWeeklyStop: () =>
    request<{ actif: boolean }>('/weekly/disable', { method: 'DELETE' }),

  /** Un lien signé à épingler — le frigo alimentable sans ouvrir l'app (§11.7). */
  issueLink: (kind: 'frigo') =>
    request<{ id: number; kind: string; url: string }>('/links', {
      method: 'POST',
      body: JSON.stringify({ kind }),
    }),

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

  previewProject: (markdown: string) =>
    request<ProjectPreview>('/projects/preview', {
      method: 'POST',
      body: JSON.stringify({ markdown }),
    }),

  importProject: (markdown: string) =>
    request<ProjectImportResult>('/projects/import', {
      method: 'POST',
      body: JSON.stringify({ markdown }),
    }),

  gardes: () => request<GardesPanel>('/gardes'),

  declareGarde: (id: number, occurred: boolean) =>
    request<GardesPanel>(`/gardes/${id}/declare`, {
      method: 'POST',
      body: JSON.stringify({ occurred }),
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
