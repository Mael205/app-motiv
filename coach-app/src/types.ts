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

/** Le prix du décrochage (SPEC §14).
 *
 * Tout est décidé côté serveur, libellés compris : un texte de sanction
 * réécrit ici serait un texte que le test du ton ne surveille plus. Le front
 * ne fait qu'éteindre ce que `showcase_locked` et `comeback` lui désignent.
 */
export interface Sanctions {
  level: number
  active: boolean
  showcase_locked: boolean
  relax_revoked: boolean
  slots_frozen: boolean
  frozen_slots: number
  early_block: boolean
  title_reprieve: boolean
  comeback: boolean
  season_exit_offered: boolean
  debt_minutes: number
  day_validated: boolean
  boss_regen_minutes: number
  shards_forfeited: number
  lines: string[]
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
  stake_forfeited: number
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

export interface InterviewMessage {
  role: 'assistant' | 'user'
  content: string
}

/** L'entretien du §4.5. `markdown` reste vide tant que le statut est en_cours. */
export interface Interview {
  id: number
  status: 'en_cours' | 'propose' | 'importe' | 'abandonne'
  messages: InterviewMessage[]
  markdown: string
  questions_posees: number
  max_questions: number
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
  sanctions: Sanctions
  progression: Progression
  rank: RankState
  season: SeasonState | null
  boss: BossState | null
  evening: Evening
  running_session: RunningSession | null
  proposal: Proposal | null
  momentum: Momentum
  skills: SkillBranch[]
  phantom: Phantom | null
  modifier: SeasonModifier | null
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

  /* Le §7 met en scene ce qui vient de CHANGER, pas l'etat courant : c'est le
     franchissement qui se fete. Le serveur rend donc des deltas, calcules une
     seule fois a la cloture, pour que la sequence n'ait pas a redemander
     l'etat et a deviner ce qui est nouveau. */
  level_before: number
  level_after: number
  levelled_up: boolean
  total_xp: number
  rank?: string
  progression: { level: number; into_level: number; needed: number; ratio: number }
  momentum: Momentum
  branch_tier: BranchTier | null
  boss_killed: BossKill | null
  cards: LootCardDrawn[]
  relics: RelicGranted[]
}

export interface SeasonReport {
  season: { index: number; name: string; accent: string; baseline: string; days: number }
  score: number
  hours: number
  title: string
  won: boolean
  boss: { name: string; ratio_killed: number; is_dead: boolean }
  stake: number
  stake_forfeited: number
  stake_delta: number
  modifier: SeasonModifier
  phantom: {
    line: string
    available: boolean
    ahead: boolean
    delta: number
    reference: string
    series: { day: number; mine: number | null; phantom: number | null }[]
  }
  already_closed: boolean
  cards: LootCardDrawn[]
  offer?: SeasonOffer
  /** Le bilan comparé du §13.4. Absent tant qu'il n'y a pas de saison passée. */
  comparaison: {
    saisons: {
      index: number
      nom: string
      heures: number
      sessions: number
      regularite: number
      etapes: number
      engagements: string
      fuite_minutes: number
    }[]
    evolutions: {
      mesure: string
      valeur: number
      reference: number
      sens: 'progression' | 'regression' | 'stable'
      phrase: string
    }[]
    causes: string[]
    question: string
    rupture: { jour: string; jours: number } | null
    part_du_coach: number
    premiere: boolean
  }
}

export interface SeasonOffer {
  index: number
  name: string
  accent: string
  baseline: string
  starts_on: string
  ends_on: string
  boss: { name: string; hp: number }
  modifiers: {
    key: string
    name: string
    effet: string
    boss_hp: number
    stake_multiplier: number
    hard: boolean
  }[]
  phantoms: { key: string; label: string; available: boolean; reference: string; hours: number }[]
  shards: number
}

export interface SeasonState {
  pending_close: boolean
  running: boolean
  /** La porte de sortie du palier 3 (§14). Proposée, jamais prise d'office. */
  exit_offer: { season: string; days_left: number; stake_at_risk: number } | null
  offer: SeasonOffer | null
}

export interface Phantom {
  line: string
  available: boolean
  ahead: boolean
  delta: number
  mine: number
  theirs: number
  reference: string
  choice: 'meilleure' | 'derniere' | 'moyenne'
  choice_label: string
  series: { day: number; mine: number | null; phantom: number | null }[]
  day_index: number
  days_total: number
}

export interface SeasonModifier {
  key: string
  name: string
  effet: string
  line: string
  active: boolean
}

export interface Momentum {
  level: number
  percent: number
  multiplier: number
  label: string
  detail: string
  days_worked: number
  cooling: boolean
  days: boolean[]
}

export interface SkillBranch {
  key: string
  label: string
  color: string
  minutes: number
  hours: number
  tier: number
  title: string
  emblem: string
  next_hours: number | null
  progress: number
  maxed: boolean
}

export interface BossKill {
  name: string
  max_hp: number
  season: string
  days_left: number
}

export interface BranchTier {
  branch: string
  label: string
  color: string
  tier: number
  title: string
  emblem: string
  hours: number
}

export interface LootCardDrawn {
  key: string
  label: string
  rarity: 'commun' | 'rare' | 'epique' | 'legendaire'
  rarity_label: string
  color: string
  kind: string
  payload: string
  duplicate: boolean
  shards: number
  reason: string
  reason_label: string
}

export interface RelicGranted {
  key: string
  label: string
  lore: string
  emblem: string
  effect: string
  value: number
}

export interface OwnedCard extends Omit<LootCardDrawn, 'duplicate' | 'shards' | 'reason' | 'reason_label'> {
  owned: boolean
  copies: number
  equipped: boolean
}

export interface RelicEntry {
  key: string
  label: string
  lore: string
  emblem: string
  effect: string
  value: number
  owned: boolean
  equipped: boolean
  achievement: string
}

export interface ProgressionPanel {
  /** Vitrine fermée (§14, palier 1) : le serveur refuse en 423 et les panneaux
   *  arrivent vides. On ne consulte pas ses trophées un soir sans session. */
  showcase_locked: boolean
  skills: { branches: SkillBranch[]; shape: TreeShape; tiers: number[] }
  momentum: Momentum
  relics: {
    max: number
    equipped_count: number
    relics: RelicEntry[]
    bonuses: Record<string, number>
  }
  collection: {
    slots: Record<string, OwnedCard[]>
    owned: number
    total: number
    shards: number
    equipped: Record<string, string>
  }
  pending_cards: LootCardDrawn[]
}

export interface TreeShape {
  total_minutes: number
  branches_actives: number
  dominante: string | null
  a_l_arret: string[]
  concentration: number
}

/** Un constat du §13.5. Il ne décide rien : `proposition` attend un geste. */
export interface Derive {
  kind:
    | 'projet_mort'
    | 'etape_figee'
    | 'engagement_irrealiste'
    | 'concentration'
    | 'fin_de_soiree'
    | 'migration_scroll'
    | 'sur_regime'
  constat: string
  proposition: string
  donnees: Record<string, unknown>
}

/** Ce qui est parti à l'ami, et ce qu'il en a fait (§4.7). */
export interface WeeklyPanel {
  actif: boolean
  destinataire_configure: boolean
  desactivation_demandee_le: string | null
  desactivation_effective_le: string | null
  non_lus: number
  seuil_non_lus: number
  rapports: {
    week_start: string
    body: string
    sent_at: string | null
    read_at: string | null
  }[]
}

/** La revue du dimanche (§5.3, §13.3). */
export interface Revue {
  week_start: string
  questions: { fait: string; question: string; reponse: string }[]
  answered: number
  report: {
    a_marche?: string
    n_a_pas_marche?: string
    seule_chose?: string
    dialogue?: boolean
    note?: string
  }
  contract: { projet: string; actuel: number; propose: number; raison: string }[]
  contract_applied: boolean
  closed: boolean
}

/** Le rapport de fuite de temps (§13.2). Strictement local. */
export interface RapportDeFuite {
  depuis: string
  tranches: { debut: number; libelle: string; minutes: number }[]
  charniere: { libelle: string; minutes: number } | null
  cout_semaine: { minutes: number; sessions: number; part_du_boss: number; phrase: string }
  cout_total: { minutes: number; sessions: number; part_du_boss: number; phrase: string }
  par_surface: {
    pc: { semaine: number; avant: number }
    mobile: { semaine: number; avant: number }
  }
  declencheurs: { quoi: string; occurrences: number; part: number }[]
  sans_horodatage: number
}
