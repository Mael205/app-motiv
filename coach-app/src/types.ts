/** Contrats de l'API. Le front n'invente aucune règle : il affiche l'état
 *  que le serveur a déjà décidé. */

export interface Streak {
  current: number
  best: number
  shields: number
  to_next_shield: number
  sanction_level: number
  message: string
}

export interface Progression {
  total_xp: number
  level: number
  rank: string
  level_floor_xp: number
  next_level_xp: number
  into_level: number
  ratio: number
}

export interface RoadmapStepView {
  id: number
  label: string
  state: 'todo' | 'doing' | 'done'
  estimated_sessions: number
  needs_split: boolean
}

export interface ProjectDetail {
  id: number
  name: string
  status: string
  slot: number | null
  color: string
  emblem: string
  track: string
  completion: number
  weekly_commitment: number
  is_coach_project: boolean
  current_step: { id: number; label: string; needs_split: boolean } | null
  steps: RoadmapStepView[]
}

export interface JournalEntry {
  id: number
  project: string
  color: string
  day: string
  minutes: number
  note: string
  next_action: string
}

export interface SeasonState {
  index: number
  key: string
  name: string
  accent: string
  baseline: string
  day_index: number
  days_total: number
  days_left: number
  modifier: string
  stake: number
}

export interface BossState {
  name: string
  max_hp: number
  current_hp: number
  ratio: number
  is_dead: boolean
}

export interface EveningBlock {
  project: string
  color: string
  start_ratio: number
  end_ratio: number
  minutes: number
  running: boolean
}

export interface Evening {
  start: string
  end: string
  total_minutes: number
  elapsed_ratio: number
  blocks: EveningBlock[]
}

export interface Proposal {
  project: { id: number; name: string; color: string; emblem: string; completion: number }
  minutes: number
  step: { id: number; label: string; needs_split: boolean } | null
  amorce: string
  reason: string
}

export interface RunningSession {
  id: number
  project: string
  color: string
  started_at: string
  planned_minutes: number
}

export interface Quest {
  kind: string
  label: string
  progress: number
  target: number
  done: boolean
}

/** Une routine de la piste Entretien, telle que le panneau du jour l'affiche. */
export interface RoutineEntry {
  id: number
  name: string
  checked: boolean
  week_done: number
  week_target: number
  week_label: string
  week_held: boolean
  slack: number
  shards_if_checked: number
}

export interface RoutineGroup {
  anchor: string
  label: string
  routines: RoutineEntry[]
}

/** Piste Entretien (SPEC §11.9). Aucun streak ici : la semaine et le cumul, rien d'autre. */
export interface EntretienPanel {
  day: string
  held_weeks: number
  week_held: boolean
  due_today: number
  done_today: number
  groups: RoutineGroup[]
}

export interface RoutineCheckResult {
  created?: boolean
  removed?: boolean
  shards: number
  panel: EntretienPanel
}

export interface HomeState {
  day: string
  now: string
  validated_today: boolean
  required_minutes: number
  minutes_today: number
  streak: Streak
  progression: Progression
  season: SeasonState | null
  boss: BossState | null
  evening: Evening
  running_session: RunningSession | null
  proposal: Proposal | null
  quests: Quest[]
  entretien: EntretienPanel
  relax_used: boolean
}

export interface SessionResult {
  session_id: number
  minutes: number
  xp: number
  breakdown: {
    base: number
    first_of_day: number
    early: number
    streak_multiplier: number
    momentum_multiplier: number
    degressivity: number
    total: number
    notes: string[]
  }
  boss_damage: number
  achievements: { key: string; label: string; description: string }[]
}
