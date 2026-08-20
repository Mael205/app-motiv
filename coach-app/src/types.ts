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
  /** Ce qui rend l'étape exécutable sans réfléchir (§4.5). Tous facultatifs :
   *  « appeler le plombier » n'a ni ressource ni charge. Le critère de sortie
   *  est le seul qui manque vraiment quand il manque — sans lui, on ne sait pas
   *  quand l'étape est finie. */
  resource: string
  url: string
  scope: string
  load: string
  exit_criterion: string
}

/** Un bloc du parcours : l'échelle des mois, pas celle de la soirée (§4.5). */
export interface ProjectBlocView {
  id: number
  name: string
  outcome: string
  resource: string
  url: string
  load: string
  cost: string
  optional: boolean
  exit_criterion: string
}

/** Une ressource écartée, et pourquoi. Évite de refaire l'arbitrage. */
export interface DiscardedResourceView {
  id: number
  name: string
  reason: string
}

/** Un projet bloqué par un tiers ou du matériel (§13.5 étendu).
 *
 * L'attente fait taire la détection « projet mort » et lève l'engagement de la
 * semaine. Elle ne libère **pas** le slot : c'est ce qui la distingue du frigo,
 * et le front ne doit jamais laisser croire l'inverse.
 */
export interface ProjectHold {
  starts_on: string
  ends_on: string
  reason: string
  days_left: number
  line: string
}

/** Ce que rend la fin d'une étape. La carte est garantie (§12.6) — sauf sur une
 *  étape déjà terminée, qui ne repaie rien. */
export interface StepCompleted {
  id: number
  state: string
  boss_damage: number
  card: LootCardDrawn | null
  boss_phase: BossPhaseCrossed | null
  achievements: { key: string; label: string; description: string }[]
  relics: RelicGranted[]
  already_done: boolean
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
  objective: string
  frame: string
  hold: ProjectHold | null
  current_step: { id: number; label: string; needs_split: boolean; exit_criterion: string } | null
  steps: RoadmapStepView[]
  parcours: ProjectBlocView[]
  ecartees: DiscardedResourceView[]
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

/** Où l'on se tient dans la trame du §12.2 : quelle voie, quel acte.
 *
 * La voie descend du résultat de la saison précédente — tenue, on monte ; ratée,
 * on descend aux braises. Elle ne change **aucune règle** : même mise, même
 * boss. Elle change ce que la saison raconte, et un mois raté raconté comme une
 * descente aux forges est plus tenable qu'un mois raté raconté avec les mots
 * d'un sommet.
 */
export interface ActeDeSaison {
  numero: number
  nom: string
  total: number
  voie: 'cimes' | 'braises'
  voie_nom: string
  voie_ligne: string
}

export interface SeasonState {
  index: number
  key: string
  name: string
  accent: string
  /** La seconde couleur de la saison. Elle tient l'atmosphère — halo de fond,
   *  braises, rais de lumière — là où `accent` tient le texte et les jauges.
   *  Une seule couleur donnait vingt-quatre saisons de même forme repeintes. */
  accent2: string
  /** Le traitement de fond que le client sait dessiner : `lave`, `ailes`,
   *  `abysse`… Neuf familles pour vingt-quatre saisons, croisées avec la paire
   *  de couleurs, le sceau et la frise. */
  ambiance: string
  baseline: string
  acte: ActeDeSaison
  day_index: number
  days_total: number
  days_left: number
  modifier: string
  stake: number
  stake_forfeited: number
  contract: SeasonContract | null
  /** L'année : douze saisons, et le compte à rebours qui va avec. Sans lui, la
   *  douzième arrive sans prévenir, et une ascendance qu'on n'a pas vue venir
   *  n'est pas un événement. */
  year: number
  rank_in_year: number
  seasons_per_year: number
  seasons_left_in_year: number
  closes_the_year: boolean
}

export interface BossState {
  name: string
  max_hp: number
  current_hp: number
  ratio: number
  is_dead: boolean
  /** La phase courante (§12.4). Le boss change de nom à 50 % et 25 % de vie.
   *  Aucune règle ne change avec elle : `intensity` ne pilote que l'affichage. */
  phase: BossPhase
  /** Les trois derniers jours seulement, `null` le reste du temps. */
  final_round: FinalRound | null
}

export interface BossPhase {
  index: number
  name: string
  line: string
  intensity: number
  final: boolean
  total: number
}

/** La vie du boss en sessions, les trois derniers jours (§12.4).
 *
 * Informatif et rien d'autre : le serveur n'y met aucun multiplicateur, et le
 * front n'en invente pas. Un bonus de fin encouragerait le sur-régime du §0.2
 * exactement là où il fait le plus de dégâts.
 */
export interface FinalRound {
  active: boolean
  days_left: number
  sessions_left: number
  session_minutes: number
  reachable: boolean
  line: string
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
  /** La bande dessinée. Elle **s'élargit** à ce qui a réellement eu lieu :
   *  depuis qu'une séance compte à n'importe quelle heure, une session de 10h
   *  était dessinée collée au bord gauche, donc à 18h. Une jauge qui affirme
   *  une heure fausse est pire qu'une jauge absente. */
  start: string
  end: string
  /** La fenêtre du soir elle-même — quand la soirée se ferme, et quand le
   *  gardien parlera. Identique aux bornes ci-dessus le plus souvent. */
  window_start: string
  window_end: string
  widened: boolean
  total_minutes: number
  elapsed_ratio: number
  blocks: EveningBlock[]
}

/** Un morceau de soirée passé sur une étape (§4.1). */
export interface PlanPortion {
  step_id: number
  label: string
  /** Les minutes qu'on y consacre ce soir. */
  minutes: number
  /** Ce qu'il restait à faire sur l'étape avant ce soir. */
  reste_avant: number
  /** La part de ce reste que la soirée couvre, de 0 à 100. */
  pourcentage: number
  /** L'étape est couverte en entier ce soir. */
  entiere: boolean
  /** Le temps estimé est déjà consommé : il reste à la déclarer finie. */
  a_clore: boolean
  exit_criterion: string
}

export interface Proposal {
  /** Quelle piste la décision engage. L'Atelier la plupart du temps ; le Corps
   *  quand sa semaine est sur le point d'être ratée (§11.4). */
  track: 'atelier' | 'corps'
  project: { id: number; name: string; color: string; emblem: string; completion: number }
  minutes: number
  /** Ce que le créneau couvre, étape par étape, dans l'ordre de la roadmap.
   *  Plusieurs entrées = la soirée enchaîne ; la dernière peut être une
   *  fraction quand l'étape déborde du temps disponible. */
  plan?: PlanPortion[]
  /** La dernière étape du plan sera laissée en cours. */
  plan_coupe?: boolean
  /** La soirée couvre plus d'une étape. */
  plan_enchaine?: boolean
  /** Le bloc suivant du parcours, quand la roadmap vient de se vider. C'est le
   *  seul moment où la question se pose — et sans lui, un parcours de quatorze
   *  blocs s'arrêtait au premier. */
  next_bloc?: { id: number; name: string; resource: string } | null
  /** Le rendez-vous fixe du jour, s'il y en a un (§11.2). Il vient avec la
   *  proposition pour que la ponctualité se décide **avant** de démarrer :
   *  une prime qu'on ne découvre qu'au décompte final ne change rien. */
  creneau: {
    heure: string
    minutes: number
    /** La demi-heure autour du rendez-vous qui vaut « à l'heure ». */
    tolerance: number
    /** Où l'on en est, calculé par le serveur : lui seul sait que la journée
     *  du coach bascule à 4h, et un client qui comparerait à `new Date()`
     *  annoncerait « dans 20 heures » un créneau qui vient d'être manqué. */
    statut?: 'a_venir' | 'maintenant' | 'passe'
    ecart_minutes?: number
  } | null
  step: {
    id: number
    label: string
    needs_split: boolean
    exit_criterion: string
    resource: string
    url: string
    scope: string
  } | null
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
  /** L'objectif annoncé au démarrage. Il monte quand on prolonge, jamais l'inverse. */
  planned_minutes: number
  extensions?: number
}

/** Ce que rend une prolongation : le nouvel objectif, et depuis combien de
 *  temps la séance tourne — c'est ce dont l'anneau a besoin pour repartir. */
export interface SessionExtended {
  id: number
  planned_minutes: number
  extensions: number
  elapsed_minutes: number
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
  resource: string
  url: string
  scope: string
  load: string
  exit_criterion: string
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
  objective: string
  frame: string
  open_steps: number
  steps: ParsedStep[]
  parcours: Omit<ProjectBlocView, 'id'>[]
  ecartees: Omit<DiscardedResourceView, 'id'>[]
  warnings: string[]
  /** Les lignes que le parseur n'a pas su placer. Non vide = il y a plus dans
   *  le document que ce qui vient d'être lu, et une relecture vaut le coup. */
  ignored: string[]
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
  /** « avant 7h30 » pour une habitude horaire, vide pour toutes les autres.
   *  Le §11.9 ancre les routines sur un geste et pas sur une horloge ; se lever
   *  et se coucher sont les deux exceptions, parce que l'heure *est* l'habitude. */
  window: string
  /** Cochée aujourd'hui, mais hors fenêtre : le fait est gardé, il ne compte pas. */
  late_today: boolean
  /** Ce que les sondes disent de l'habitude horaire : `corrobore`, `contredit`,
   *  ou `sans_signal`. Le §6 vaut ici dans les deux sens — une contradiction ne
   *  retire rien, une corroboration ne paie rien. */
  corroboration: 'corrobore' | 'contredit' | 'sans_signal'
  corroboration_line: string
}

/** Une capacité constatée : datée, binaire, vérifiable par quelqu'un d'autre. */
export interface PreuveEntry {
  id: number
  critere: string
  projet: string
  couleur: string
  obtained_on: string
}

/** Le troisième axe, à côté du volume et de la fiabilité. Les deux nombres ne
 *  fusionnent jamais : un score unique monterait en ne faisant que des heures. */
export interface CapacitePanel {
  preuves: number
  heures: number
  heures_par_preuve: number | null
  liste: PreuveEntry[]
}

/** Une chose à faire une fois — ni projet, ni routine. Ne rapporte rien, et
 *  n'apparaît jamais sur l'écran du soir (§11.1). */
export interface PonctuelEntry {
  id: number
  label: string
  due_on: string | null
  done: boolean
  late: boolean
  due_today: boolean
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
  /** La piste Corps, côte à côte avec l'Atelier — jamais fusionnées en un
   *  score unique (§11.4). `null` quand aucune activité physique n'est suivie. */
  corps: CorpsPanel | null
  entretien: EntretienPanel
  gardes: GardesPanel
  relax_used: boolean
  /** Les cartes équipées, enfin appliquées. */
  cosmetics: Cosmetics
}

/** La piste Corps (§11.4) : objectif hebdomadaire, streak de **semaines**.
 *
 * Pas de bouclier ici, et ce n'est pas un oubli : le battement est déjà dans
 * l'objectif — viser deux séances quand la semaine en compte sept laisse cinq
 * jours de marge.
 */
export interface CorpsPanel {
  objectif: number
  faites: number
  restantes: number
  tenue: boolean
  ratio: number
  streak: number
  best: number
  semaines_tenues: number
  message: string
  plancher: number
  degrade: number
  jours_restants: number
  /** De 0 à 1. Au-delà du seuil, la piste prend la décision du soir. */
  priorite: number
  projets: { id: number; name: string; color: string; emblem: string }[]
}

export interface SessionResult {
  session_id: number
  minutes: number
  /** L'objectif annoncé au démarrage, et ce qu'il est devenu. Le minuteur ne
   *  plafonne plus les minutes (elles comptent toutes), il reste la promesse
   *  qu'on a faite en démarrant — et la clôture dit si elle a été tenue. */
  objectif: number
  objectif_tenu: boolean
  depassement: number
  extensions: number
  xp: number
  breakdown: {
    base: number
    /** Ce que les minutes tardives valent en plus. 0 sous 25 minutes. */
    duration_premium: number
    first_of_day: number
    /** La prime de ponctualité : le créneau annoncé tenu à la demi-heure près.
     *  Elle a remplacé le forfait « avant 20h », qui payait l'horloge plutôt
     *  que la parole donnée. 0 quand aucun créneau n'était déclaré — rien à
     *  tenir n'est pas un échec. */
    punctual: number
    streak_multiplier: number
    momentum_multiplier: number
    degressivity: number
    /** L'XP avant le critique. Égale à `total` quand il n'y en a pas. */
    base_total: number
    crit: boolean
    crit_multiplier: number
    crit_bonus: number
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
  /** La phase de boss franchie par cette session, s'il y en a une. */
  boss_phase: BossPhaseCrossed | null
  /** Le coup critique (§12). `null` neuf fois sur dix. */
  crit: Crit | null
  cards: LootCardDrawn[]
  relics: RelicGranted[]
}

export interface BossPhaseCrossed {
  index: number
  name: string
  line: string
  intensity: number
  final: boolean
  previous_name: string
}

export interface Crit {
  hit: boolean
  multiplier: number
  bonus: number
  forced: boolean
  label: string
  line: string
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

/** Les compteurs qui ne redescendent jamais (§17 de la liste du 17 août).
 *
 * Aucun champ de ce type ne peut baisser, et c'est une contrainte de fond, pas
 * une remarque : l'écran s'ouvre le soir où le streak vient de casser, et un
 * seul compteur qui redescendrait suffirait à l'annuler.
 */
/** L'assistant qui agit sur l'app (§5 étendu).
 *
 * Une action proposée n'est **pas** une action faite. `state` vaut « attente »
 * tant que personne n'a cliqué, et le front ne doit jamais laisser croire
 * l'inverse — c'est la même règle que la porte de qualité applique au texte du
 * modèle, appliquée à l'interface.
 */
export interface ActionProposee {
  id: number
  key: string
  label: string
  domain: string
  summary: string
  params: Record<string, unknown>
  before: string
  after: string
  warning: string
  state: 'attente' | 'appliquee' | 'ecartee' | 'perimee'
  detail: string
}

export interface TourAssistant {
  id: number
  role: 'user' | 'assistant'
  text: string
  at: string
  model: string
  tokens: number
  actions: ActionProposee[]
}

export interface FilAssistant {
  conversation_id: number
  started_at: string
  turns: TourAssistant[]
}

/** Les hauts faits, et les trois plus proches de tomber. */
export interface HautsFaits {
  obtenus: { key: string; label: string; description: string; registre: string; at: string }[]
  total: number
  prochains: {
    key: string
    label: string
    description: string
    registre: string
    valeur: number
    seuil: number
    part: number
  }[]
}

/** Les cosmétiques équipés, résolus en valeurs affichables (§12.6).
 *
 * Le serveur envoie une couleur, un glyphe ou un mot — jamais une clé de carte
 * que le front devrait retrouver dans un catalogue qu'il n'a pas.
 *
 * **Rien de tout ça n'entre dans un calcul.** Le §17 est formel : le loot est
 * de l'apparence, jamais du pouvoir.
 */
export interface CosmeticSlot {
  key: string
  label: string
  value: string
  rarity: string
}

export type Cosmetics = Partial<
  Record<'theme' | 'emblem' | 'frame' | 'title' | 'finisher', CosmeticSlot>
>

/** Le bilan de la journée écoulée (§13.1).
 *
 * Recalculé à chaque lecture côté serveur : une sonde qui remonte ses minutes
 * en retard doit pouvoir corriger le tableau du matin plutôt que le laisser
 * faux. Rien n'est stocké, donc rien ne se fige à tort.
 */
export interface BilanDuJour {
  jour: string
  /** Vrai les jours où il n'y a rien à dire. La règle du silence est calculée
   *  côté serveur, la même que celle de la notification de la nuit. */
  silencieux: boolean
  disponibles: number
  travaillees: number
  /** De 0 à 1 : la barre du §13.1, et rien d'autre. */
  part: number
  creneau_prevu: boolean
  creneau_tenu: boolean
  repartition: { label: string; minutes: number }[]
  phrase: string
}

/** Les séries des douze dernières semaines (J6, §16).
 *
 * À ne pas confondre avec `TraceLongue`, qui ne rend que des compteurs
 * monotones : celle-ci descend, et c'est son intérêt.
 */
export interface StatsLongues {
  depuis: string
  semaines: { debut: string; minutes: number; sessions: number; jours_travailles: number }[]
  jours: { index: number; label: string; minutes: number; sessions: number; jours_tenus: number }[]
  projets: { nom: string; couleur: string; minutes: number; sessions: number }[]
  heures: { heure: number; minutes: number }[]
  seances: {
    moyenne: number
    plus_longue: number
    total: number
    longues: number
    part_longues: number
  }
  etapes: number
}

export interface TraceLongue {
  since: string | null
  days_since: number
  compteurs: { label: string; value: number; unit: string }[]
  branches: { key: string; label: string; color: string; hours: number; title: string }[]
  titres: string[]
}

export interface SeasonOffer {
  index: number
  /** La clé de l'identité — c'est elle que l'emblème attend, pas le nom. */
  key: string
  name: string
  accent: string
  baseline: string
  /** Où cette saison entre dans la trame, et pourquoi (§12.2). */
  acte: ActeDeSaison
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
  contract: SeasonContractOffer
}

/** Ce qu'on propose de signer à l'ouverture (§16 de la liste du 17 août).
 *
 * `terms` vient du serveur : c'est lui qui écrit ce qu'on signe. Le front ne
 * remplace que le nombre dedans quand le curseur bouge — signer sans avoir vu
 * le total sur la saison entière, c'est régler un curseur, pas s'engager.
 */
export interface SeasonContractOffer {
  proposed: number
  minimum: number
  maximum: number
  weeks: number
  total: number
  projects: string[]
  terms: string[]
}

/** Le contrat signé, et où il en est. `null` quand la saison n'a rien signé. */
export interface SeasonContract {
  sessions_per_week: number
  projects: string[]
  weeks: number
  total: number
  done: number
  signed_on: string
  terms: string[]
  line: string
}

/** Une année accomplie : douze saisons closes, et la voie qui s'ouvre après.
 *
 * `voie` est vide tant que le choix n'est pas fait, et tant qu'il ne l'est pas
 * l'ascendance n'ouvre **rien** — c'est ce qui rend le choix réel plutôt qu'une
 * formalité à cliquer plus tard.
 */
export interface AnneeAccomplie {
  year: number
  title: string
  seasons: number
  bosses_killed: number
  hours: number
  xp_at_reset: number
  level_at_reset: number
  rank_at_reset: string
  slots_engraved: number
  voie: string
  voies: { key: string; label: string; promesse: string; cout: string }[]
  garde: string
}

/** Où en est le **cycle** : à clore, à ouvrir, ou en cours.
 *
 * Renommée depuis `SeasonState`, qui existait déjà plus haut pour l'identité
 * d'une saison. Deux interfaces du même nom dans un même fichier ne s'annulent
 * pas : TypeScript les **fusionne**, et le type obtenu exigeait à la fois le
 * nom de la saison et l'état du cycle. Personne ne s'en apercevait parce que
 * les deux ne servent qu'à typer des réponses d'API, jamais à en construire —
 * et `App.tsx` renommait déjà l'import pour s'y retrouver.
 */
export interface SeasonPhase {
  pending_close: boolean
  running: boolean
  /** La porte de sortie du palier 3 (§14). Proposée, jamais prise d'office. */
  exit_offer: { season: string; days_left: number; stake_at_risk: number } | null
  /** L'année close dont la voie n'a pas été choisie. Passe avant tout le reste. */
  annee: AnneeAccomplie | null
  offer: SeasonOffer | null
  /** Le mode extra du §12.4 : le boss est tombé avant la fin, la saison
   *  suivante est engagée et attend sa date. `null` le reste du temps. */
  extra: ModeExtra | null
}

/** Ce qu'il reste à attendre après une victoire anticipée, et ce qui est mis
 *  de côté d'ici là. Le §12.4 : « les jours restants alimentent directement le
 *  score de la saison suivante ». */
export interface ModeExtra {
  name: string
  accent: string
  starts_on: string
  days_until: number
  minutes: number
}

/** Où en est le fantôme **à cette heure-ci** (§12.7).
 *
 * `measured` dit si la position vient de la répartition horaire réelle du
 * travail passé ou du repli linéaire. Le front ne s'en sert pas pour changer
 * le texte — le serveur l'a déjà écrit — mais pour ne pas dessiner un repère
 * qui aurait l'air mesuré alors qu'il ne l'est pas.
 */
export interface PhantomLive {
  available: boolean
  line: string
  ahead: boolean
  delta: number
  mine: number
  theirs: number
  /** Les deux mêmes, ramenés à aujourd'hui : la jauge du soir ne peut afficher
   *  que des minutes de ce soir. */
  mine_today: number
  theirs_today: number
  delta_today: number
  share: number
  measured: boolean
}

export interface Phantom {
  line: string
  live: PhantomLive
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
  /** Le prix de forge, présent seulement quand la voie « Forge » est ouverte. */
  forge_price?: number
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
    /** La Forge est ouverte par une ascendance. Fermée, aucune carte ne se
     *  fabrique et les Éclats n'ont toujours nulle part où aller. */
    forge_open: boolean
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
/** L'écart de fuseau constaté entre le profil et l'appareil (§1 étendu).
 *
 * `proposed` est faux quand il n'y a rien à faire — même fuseau, ou même
 * décalage aujourd'hui. Le front n'a alors rien à afficher : proposer une
 * bascule qui ne change rien ce soir serait du bruit.
 */
export interface TimezoneCheck {
  timezone: string
  detected: string
  offset_minutes: number
  proposed: boolean
  line: string
}

export interface WeeklyPanel {
  actif: boolean
  destinataire_configure: boolean
  desactivation_demandee_le: string | null
  desactivation_effective_le: string | null
  non_lus: number
  seuil_non_lus: number
  /** Ce qu'on propose quand le destinataire ne lit plus (§4.7).
   *
   * Le constat des trois semaines existait déjà ; c'est la suite qui manquait,
   * et un constat sans suite se lit deux fois puis s'ignore. */
  remplacement: { non_lus: number; line: string; action: string } | null
  rapports: {
    week_start: string
    body: string
    sent_at: string | null
    read_at: string | null
  }[]
}

/** La revue du dimanche (§5.3, §13.3). */
/** Une entrée de journal d'il y a quatre semaines, ressortie dans la revue.
 *
 * Elle sort telle quelle, sans commentaire : le §17 interdit au système de
 * juger, et « regarde le chemin parcouru » est un jugement même flatteur.
 */
export interface RappelDuMois {
  day: string
  project: string
  color: string
  note: string
  next_action: string
}

export interface Revue {
  week_start: string
  il_y_a_quatre_semaines: RappelDuMois | null
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
