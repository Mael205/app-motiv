import { memo, useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { api } from '../api'
import type { Briefing, Proposal } from '../types'
import { Icon } from './art/Icons'
import { SessionEntry } from './SessionEntry'
import './DecisionBlock.css'

/** Les créneaux proposés, en multiples de la session du §4.1.
 *
 * Une étape est estimée en sessions de vingt-cinq minutes : les paliers suivent
 * donc la même unité, sans quoi un bouton promettrait une durée qui ne
 * correspond à aucun découpage possible.
 */
const DUREES = [
  { minutes: 10, nom: 'Dégradé' },
  { minutes: 25, nom: 'Courte' },
  { minutes: 50, nom: 'Longue' },
  { minutes: 75, nom: 'Soirée' },
] as const

/** Zone 2 : la décision, et rien d'autre.
 *
 * Un projet, une tâche, un bouton (SPEC §11.1). C'est le bloc le plus grand et
 * le plus lumineux de l'écran ; tout le reste est secondaire par construction.
 * Les autres durées sont accessibles mais visuellement subordonnées.
 */
export const DecisionBlock = memo(function DecisionBlock({
  proposal,
  onStarted,
}: {
  proposal: Proposal | Briefing
  onStarted: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [entering, setEntering] = useState(0)

  // La proposition affichée. Elle part de celle du serveur et change quand on
  // touche une durée : une durée ne règle pas seulement le chronomètre, elle
  // décide de l'étape — celle qui tient dans ce temps-là.
  const [vue, setVue] = useState<Proposal | Briefing>(proposal)
  const [chargement, setChargement] = useState(0)

  useEffect(() => setVue(proposal), [proposal])

  /** Le chemin critique du §7 : la requête part **avant** toute animation.
   *
   * L'ordre des deux premières lignes est le sujet. La séquence d'entrée se
   * monte au même instant que l'appel et couvre son attente ; elle ne la
   * précède pas et ne l'allonge pas. Sans elle on regarderait un bouton grisé
   * pendant une demi-seconde, exactement au moment où l'on vient de décider de
   * s'y mettre.
   *
   * En cas d'échec, la séquence se retire et le motif s'affiche : une erreur
   * masquée par un bel effet serait la pire des deux.
   */
  async function start(minutes: number) {
    setBusy(true)
    setError('')
    setEntering(minutes)
    try {
      await api.startSession(vue.project.id, minutes)
      onStarted()
    } catch (e) {
      setEntering(0)
      setError(e instanceof Error ? e.message : 'Impossible de démarrer.')
      setBusy(false)
    }
  }

  /** Toucher une durée : on demande au serveur ce qu'il proposerait pour ce
   *  temps-là, et on l'affiche. Toucher la durée déjà affichée démarre.
   *
   *  Deux gestes au maximum, et le premier est réversible. Démarrer d'emblée
   *  sur un simple effleurement — ce que faisaient les deux boutons avant —
   *  engageait la soirée sans avoir montré sur quoi.
   */
  async function choisir(minutes: number) {
    if (minutes === vue.minutes) return start(minutes)
    setChargement(minutes)
    setError('')
    try {
      setVue(await api.proposalFor(minutes))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Impossible de changer de durée.')
    } finally {
      setChargement(0)
    }
  }

  /** Ouvrir le bloc suivant du parcours.
   *
   * Le geste est manuel, et le §11.6 le veut ainsi : ouvrir un bloc engage
   * plusieurs semaines, et le serveur découpe alors le bloc en étapes. C'est
   * la seule action de cet écran qui ne démarre pas une session — elle rend au
   * lendemain une roadmap qui s'était vidée.
   *
   * `ouverture` est distinct de `busy` : le bouton dit ce qu'il est en train de
   * faire — « le coach découpe le bloc » — pendant que le grand bouton reste
   * grisé pour la même raison. Un seul drapeau les rendrait muets tous les deux.
   */
  const [ouverture, setOuverture] = useState(false)

  async function ouvrirLeBloc() {
    setOuverture(true)
    setBusy(true)
    setError('')
    try {
      await api.openNextBloc(vue.project.id)
      // Le rechargement vient du parent : c'est lui qui tient l'état du soir,
      // et la roadmap fraîche change la proposition entière, pas ce bloc-ci.
      onStarted()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Impossible d'ouvrir le bloc.")
    } finally {
      setOuverture(false)
      setBusy(false)
    }
  }

  const brief = 'source' in vue ? vue : null
  const task = vue.amorce || vue.step?.label

  // Le plan de la soirée. `coupee` est la portion qu'on ne finira pas ce soir —
  // toujours la dernière, par construction du planificateur.
  const plan = vue.plan ?? []
  const coupee = plan.length && !plan[plan.length - 1].entiere ? plan[plan.length - 1] : null
  const aClore = plan.some((p) => p.a_clore)

  // D'ou vient la tache affichee. Le dire n'est pas de la transparence pour la
  // forme : une tache decidee par un modele et une amorce qu'on a ecrite
  // soi-meme la veille ne se relisent pas avec la meme confiance.
  const taskKind = brief?.source === 'modele' ? 'Décidé pour ce soir' : vue.amorce ? 'Ton amorce' : 'Étape en cours'

  if (entering) {
    return (
      <SessionEntry
        project={vue.project.name}
        minutes={entering}
        emblem={vue.project.emblem}
        color={vue.project.color}
      />
    )
  }

  return (
    <section className="decision" style={{ ['--project' as string]: vue.project.color }}>
      <div className="decision__head">
        {/* Quelle piste la soirée engage. Sans ce mot, une séance de sport
            proposée un vendredi se lit comme un projet d'atelier au nom
            bizarre — et le §11.4 tient à ce que les deux ne se confondent
            jamais. */}
        <span className="label">{vue.track === 'corps' ? 'Ce soir · Corps' : 'Ce soir'}</span>
        <span className="decision__reason">{vue.reason}</span>
        {/* Où l'on en est du rendez-vous. La ligne n'existe que s'il y en a un,
            et elle ne reproche rien quand il est passé : le §17 interdit le
            jugement, et « créneau passé de 40 min » est un fait. C'est aussi la
            seule façon pour la prime de ponctualité de peser sur une décision —
            une prime qu'on découvre au décompte final ne change rien. */}
        {vue.creneau?.statut && (
          <span className={`decision__creneau decision__creneau--${vue.creneau.statut}`}>
            {ligneDeCreneau(vue.creneau)}
          </span>
        )}
      </div>

      <div className="decision__project">
        <span className="decision__emblem">{vue.project.emblem}</span>
        <h2 className="decision__name display">{vue.project.name}</h2>
      </div>

      {/* Une activité physique n'a pas de roadmap : la barre resterait à zéro
          en permanence, ce qui se lirait comme un projet à l'arrêt. */}
      {vue.track !== 'corps' && (
        <div className="decision__progress" title={`${Math.round(vue.project.completion * 100)}% de la roadmap`}>
          <div
            className="decision__progress-fill"
            style={{ transform: `scaleX(${vue.project.completion})` }}
          />
        </div>
      )}

      {task ? (
        <div className="decision__task">
          <span className="label">{taskKind}</span>
          <p className="decision__task-text">{task}</p>
          {/* « Fini quand » a maintenant deux sources, et l'ordre compte : la
              définition du modèle est taillée pour ce soir, le critère de
              sortie de l'étape a été écrit à la création du projet et vaut pour
              toutes ses sessions. Le repli existe surtout pour le soir sans
              modèle — c'est là qu'on démarrait sans savoir où s'arrêter. */}
          {(brief?.definition_de_fini || vue.step?.exit_criterion) && (
            <p className="decision__done">
              Fini quand : {brief?.definition_de_fini || vue.step?.exit_criterion}
            </p>
          )}
          {/* La ressource ne se devine pas à 21h. L'ouvrir depuis ici évite le
              détour par l'onglet Projets, qui est un détour par tout le reste. */}
          {vue.step?.resource && (
            <p className="decision__resource">
              {vue.step.url ? (
                <a href={vue.step.url} target="_blank" rel="noreferrer">
                  {vue.step.resource}
                </a>
              ) : (
                vue.step.resource
              )}
              {vue.step.scope && <span className="muted"> · {vue.step.scope}</span>}
            </p>
          )}
          {/* Ce que le créneau couvre. Le dire avant de démarrer est tout
              l'intérêt : sinon on découvre à 22h qu'on est au milieu de
              quelque chose, ce qui se lit comme un échec alors que c'était un
              calibrage annoncé. La première portion est déjà le titre
              ci-dessus ; on n'affiche la liste que si la soirée enchaîne. */}
          {plan.length > 1 && (
            <ol className="decision__plan">
              {plan.map((portion) => (
                <li key={portion.step_id} className={portion.entiere ? undefined : 'decision__plan--coupe'}>
                  <span className="decision__plan-minutes num">{portion.minutes}</span>
                  <span className="decision__plan-label">{portion.label}</span>
                  {!portion.entiere && (
                    <span className="muted"> · {portion.pourcentage} %</span>
                  )}
                </li>
              ))}
            </ol>
          )}

          {/* La coupe, en toutes lettres. « Tu en fais la moitié » est une
              information, pas un reproche : le reste est crédité et la
              prochaine séance reprendra où celle-ci s'arrête. */}
          {coupee && (
            <p className="decision__warn">
              {coupee.pourcentage} % de « {coupee.label} » ce soir — {coupee.minutes} min sur
              les {coupee.reste_avant} qui restent. Le temps passé est gardé, la suite reprendra là.
            </p>
          )}

          {aClore && (
            <p className="decision__warn">
              Le temps estimé de cette étape est écoulé. Termine-la et coche-la, ou découpe ce qui reste.
            </p>
          )}

          {vue.step?.needs_split && (
            <p className="decision__warn">Cette étape est trop grosse : elle demande un découpage.</p>
          )}
        </div>
      ) : (
        <div className="decision__task decision__task--empty">
          {/* La roadmap est vide. Si le parcours a une suite, c'est ici qu'elle
              s'ouvre : c'est exactement le moment où le produit s'arrêtait,
              avec treize blocs planifiés et plus rien à faire le soir. */}
          {vue.next_bloc ? (
            <>
              <p className="decision__task-text">
                Bloc terminé. La suite du parcours : <strong>{vue.next_bloc.name}</strong>
                {vue.next_bloc.resource && <span className="muted"> · {vue.next_bloc.resource}</span>}
              </p>
              <button className="ghost" onClick={ouvrirLeBloc} disabled={busy}>
                {ouverture ? 'Le coach découpe le bloc…' : 'Ouvrir ce bloc'}
              </button>
            </>
          ) : (
            <p className="decision__task-text muted">
              Aucune étape exploitable. Écris le prochain jalon avant de démarrer.
            </p>
          )}
        </div>
      )}

      <motion.button className="cta cta--main" onClick={() => start(vue.minutes)} disabled={busy} whileTap={{ scale: 0.985 }}>
        <Icon.bolt size={22} />
        <span>Démarrer</span>
        <span className="cta__minutes num">{vue.minutes} min</span>
      </motion.button>

      {/* Les créneaux. Toucher l'un d'eux change **la tâche**, pas seulement le
          chronomètre : on montre l'étape qui tient dans ce temps-là, et un
          second toucher démarre.

          Les paliers suivent la session de vingt-cinq minutes du §4.1, parce
          que c'est l'unité dans laquelle les étapes sont estimées. Un palier à
          soixante minutes n'apporterait rien : il retiendrait exactement les
          mêmes étapes que cinquante, tout en promettant dix minutes de plus. */}
      <div className="decision__alts" role="group" aria-label="Durée de la séance">
        {DUREES.map(({ minutes, nom }) => (
          <button
            key={minutes}
            className={`ghost${vue.minutes === minutes ? ' ghost--on' : ''}`}
            onClick={() => choisir(minutes)}
            disabled={busy || !!chargement}
            aria-pressed={vue.minutes === minutes}
          >
            <Icon.clock size={15} />{' '}
            {chargement === minutes ? '…' : `${nom} · ${minutes}`}
          </button>
        ))}
      </div>

      {error && <p className="decision__error">{error}</p>}
    </section>
  )
})

/** Ce que dit la ligne de créneau, selon où l'on en est.
 *
 * Trois phrases, aucune de plus. « Tu es en retard » n'y figure pas : le fait
 * suffit, et un reproche sur l'écran où l'on décide de s'y mettre est la façon
 * la plus sûre de ne pas s'y mettre.
 */
function ligneDeCreneau(creneau: NonNullable<Proposal['creneau']>): string {
  // L'heure elle-même est déjà dans la raison, juste au-dessus. Cette ligne ne
  // dit que *où l'on en est* : la répéter ferait lire deux fois la même chose,
  // et c'est l'écart qui décide de démarrer maintenant ou pas.
  const ecart = Math.abs(creneau.ecart_minutes ?? 0)
  if (creneau.statut === 'maintenant') return "C'est l'heure"
  if (creneau.statut === 'a_venir') return `Dans ${ecart} min`
  return `Passé de ${ecart} min`
}
