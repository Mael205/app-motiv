import { memo, useState } from 'react'
import { motion } from 'motion/react'
import { api } from '../api'
import type { Briefing, Proposal } from '../types'
import { Icon } from './art/Icons'
import { SessionEntry } from './SessionEntry'
import './DecisionBlock.css'

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
      await api.startSession(proposal.project.id, minutes)
      onStarted()
    } catch (e) {
      setEntering(0)
      setError(e instanceof Error ? e.message : 'Impossible de démarrer.')
      setBusy(false)
    }
  }

  const brief = 'source' in proposal ? proposal : null
  const task = proposal.amorce || proposal.step?.label

  // D'ou vient la tache affichee. Le dire n'est pas de la transparence pour la
  // forme : une tache decidee par un modele et une amorce qu'on a ecrite
  // soi-meme la veille ne se relisent pas avec la meme confiance.
  const taskKind = brief?.source === 'modele' ? 'Décidé pour ce soir' : proposal.amorce ? 'Ton amorce' : 'Étape en cours'

  if (entering) {
    return (
      <SessionEntry
        project={proposal.project.name}
        minutes={entering}
        emblem={proposal.project.emblem}
        color={proposal.project.color}
      />
    )
  }

  return (
    <section className="decision" style={{ ['--project' as string]: proposal.project.color }}>
      <div className="decision__head">
        <span className="label">Ce soir</span>
        <span className="decision__reason">{proposal.reason}</span>
      </div>

      <div className="decision__project">
        <span className="decision__emblem">{proposal.project.emblem}</span>
        <h2 className="decision__name display">{proposal.project.name}</h2>
      </div>

      <div className="decision__progress" title={`${Math.round(proposal.project.completion * 100)}% de la roadmap`}>
        <div
          className="decision__progress-fill"
          style={{ width: `${proposal.project.completion * 100}%` }}
        />
      </div>

      {task ? (
        <div className="decision__task">
          <span className="label">{taskKind}</span>
          <p className="decision__task-text">{task}</p>
          {brief?.definition_de_fini && (
            <p className="decision__done">Fini quand : {brief.definition_de_fini}</p>
          )}
          {proposal.step?.needs_split && (
            <p className="decision__warn">Cette étape est trop grosse : elle demande un découpage.</p>
          )}
        </div>
      ) : (
        <div className="decision__task decision__task--empty">
          <p className="decision__task-text muted">
            Aucune étape exploitable. Écris le prochain jalon avant de démarrer.
          </p>
        </div>
      )}

      <motion.button className="cta cta--main" onClick={() => start(proposal.minutes)} disabled={busy} whileTap={{ scale: 0.985 }}>
        <Icon.bolt size={22} />
        <span>Démarrer</span>
        <span className="cta__minutes num">{proposal.minutes} min</span>
      </motion.button>

      <div className="decision__alts">
        <button className="ghost" onClick={() => start(10)} disabled={busy}>
          <Icon.clock size={15} /> Dégradé · 10
        </button>
        <button className="ghost" onClick={() => start(50)} disabled={busy}>
          <Icon.clock size={15} /> Longue · 50
        </button>
      </div>

      {error && <p className="decision__error">{error}</p>}
    </section>
  )
})
