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

export interface SeasonState {
  index: number
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
