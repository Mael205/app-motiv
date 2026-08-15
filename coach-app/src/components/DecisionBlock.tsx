import { memo, useState } from 'react'
import { motion } from 'motion/react'
import { api } from '../api'
import type { Proposal } from '../types'
import { Icon } from './art/Icons'
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
  proposal: Proposal
  onStarted: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function start(minutes: number) {
    setBusy(true)
    setError('')
    try {
      await api.startSession(proposal.project.id, minutes)
      onStarted()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Impossible de démarrer.')
      setBusy(false)
    }
  }

  const task = proposal.amorce || proposal.step?.label
  const taskKind = proposal.amorce ? 'Ton amorce' : 'Étape en cours'

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
