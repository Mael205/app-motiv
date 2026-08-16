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

/** Le rang mesure la fiabilité, pas le volume (SPEC §4.4). */
export interface RankState {
  code: string
  weeks_kept: number
  slots: number
  extra_shields: number
  extra_days_off: number
  next: { code: string; weeks_left: number } | null
  next_unlock: string | null
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
  domain: string
  domain_label: string
  verification: string
  verification_label: string
  repos: number
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

/** Le briefing du §5.1 : la meme proposition, avec l'origine de la decision.
 *
 * C'est volontairement une extension de `Proposal` et pas un type a part. Le
 * serveur garantit qu'un briefing a toujours la forme d'une proposition
 * complete, meme quand le modele n'a pas repondu — sans quoi l'ecran aurait
 * deux etats a gerer au lieu d'un, et le §0.9 serait a la merci d'un `if`.
 */
export interface Briefing extends Proposal {
  source: 'modele' | 'deterministe'
  ai_note: string
  model?: string
  definition_de_fini?: string
}

export interface DebriefSuggestion {
  resume: string
  amorce: string
  blocages: string[]
  source: 'modele' | 'deterministe'
  ai_note: string
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

/** Une étape lue dans le markdown collé, pas encore écrite en base (SPEC §4.5). */
export interface ParsedStep {
  label: string
  state: string
  estimated_sessions: number
  needs_split: boolean
}

export interface ProjectPreview {
  valid: boolean
  name: string
  branch: string
  domain: string
  domain_label: string
  verification: string
  verification_label: string
  repo_path: string
  color: string
  emblem: string
  weekly_commitment: number
  open_steps: number
  steps: ParsedStep[]
  warnings: string[]
}

export interface ProjectImportResult {
  id: number
  name: string
  status: string
  slot: number | null
  steps: number
  detail: string
}

/** Une garde : un comportement à réduire, mesuré par un budget hebdomadaire (SPEC §11.10). */
export interface GardeEntry {
  id: number
  name: string
  budget: number
  declared_today: boolean
  occurred_today: boolean
  week_marked: number
  week_label: string
  week_held: boolean
  week_left: number
  held_days: number
  held_weeks: number
  message: string
}

export interface GardesPanel {
  day: string
  gardes: GardeEntry[]
  to_declare: number
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
  rank: RankState
  season: SeasonState | null
  boss: BossState | null
  evening: Evening
  running_session: RunningSession | null
  proposal: Proposal | null
  quests: Quest[]
  entretien: EntretienPanel
  gardes: GardesPanel
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
