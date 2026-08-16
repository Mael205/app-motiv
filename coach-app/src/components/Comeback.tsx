import { useState } from 'react'
import { motion } from 'motion/react'
import { api } from '../api'
import type { Proposal } from '../types'
import { Icon } from './art/Icons'
import { SessionEntry } from './SessionEntry'
import './Comeback.css'

/** Le palier 3 du §14 : la rampe de retour.
 *
 * À partir de trois jours d'arrêt, le système **change de registre**. Rien ne
 * s'ajoute aux sanctions déjà là, et l'accueil se réduit à une tâche et un
 * bouton. Le §14 est explicite sur ce qui ne doit pas y figurer : *pas de
 * chiffres, pas de streak à zéro affiché en grand, pas de bilan de ce qui a
 * été perdu.*
 *
 * D'où trois absences volontaires, qui sont le contenu réel du composant :
 *
 * - **aucun compteur.** Ni streak, ni jours manqués, ni XP, ni barre de boss.
 *   Le seul chiffre affiché est la durée du bouton, et c'est un engagement, pas
 *   un bilan.
 * - **aucune autre durée.** Le bloc de décision normal propose 10, 25 et 50 ;
 *   ici la seule option est dix minutes. Un choix à faire est une occasion de
 *   ne pas commencer.
 * - **aucun retour en arrière.** L'écran n'a pas de bouton pour aller voir le
 *   reste : ce qui est verrouillé l'est déjà côté serveur, et proposer d'aller
 *   regarder ce qui est éteint n'aiderait personne à s'y remettre.
 *
 * La porte de sortie du §14 apparaît au-delà de cinq jours, en bas, discrète et
 * jamais préselectionnée : elle existe pour être trouvée avant d'être inventée
 * sous forme de désinstallation.
 */
export function Comeback({
  proposal,
  exitOffer,
  onStarted,
  onExit,
}: {
  proposal: Proposal | null
  exitOffer: { season: string; days_left: number; stake_at_risk: number } | null
  onStarted: () => void
  onExit: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [entering, setEntering] = useState(false)
  const [error, setError] = useState('')
  const [askExit, setAskExit] = useState(false)

  async function start() {
    if (!proposal) return
    setBusy(true)
    setError('')
    setEntering(true)
    try {
      await api.startSession(proposal.project.id, proposal.minutes)
      onStarted()
    } catch (e) {
      setEntering(false)
      setError(e instanceof Error ? e.message : 'Impossible de démarrer.')
      setBusy(false)
    }
  }

  if (entering && proposal) {
    return (
      <SessionEntry
        project={proposal.project.name}
        minutes={proposal.minutes}
        emblem={proposal.project.emblem}
        color={proposal.project.color}
      />
    )
  }

  const task = proposal?.amorce || proposal?.step?.label

  return (
    <div className="comeback">
      <section
        className="comeback__card"
        style={{ ['--project' as string]: proposal?.project.color ?? 'var(--accent)' }}
      >
        <p className="comeback__lede">On reprend.</p>

        {proposal ? (
          <>
            <div className="comeback__project">
              <span className="comeback__emblem" aria-hidden>
                {proposal.project.emblem}
              </span>
              <h1 className="display comeback__name">{proposal.project.name}</h1>
            </div>

            {task && <p className="comeback__task">{task}</p>}

            <motion.button
              className="cta cta--main"
              onClick={start}
              disabled={busy}
              whileTap={{ scale: 0.985 }}
            >
              <Icon.bolt size={22} />
              <span>Démarrer</span>
              <span className="cta__minutes num">{proposal.minutes} min</span>
            </motion.button>
          </>
        ) : (
          <p className="muted">
            Aucun projet actif. Ouvre un slot dans Projets, et le coach aura de quoi proposer.
          </p>
        )}

        {error && <p className="comeback__error">{error}</p>}
      </section>

      {exitOffer && (
        <section className="comeback__exit">
          {askExit ? (
            <>
              <p className="comeback__exit-text">
                {exitOffer.season} se clôt maintenant, et la suivante s'ouvre dans la foulée.
                {exitOffer.stake_at_risk > 0 && (
                  <> La mise de {exitOffer.stake_at_risk} Éclats ne revient pas.</>
                )}
              </p>
              <div className="comeback__exit-actions">
                <button className="ghost" onClick={() => setAskExit(false)}>
                  Continuer la saison
                </button>
                <button className="ghost ghost--strong" onClick={onExit}>
                  Clore et repartir
                </button>
              </div>
            </>
          ) : (
            <button className="comeback__exit-link" onClick={() => setAskExit(true)}>
              Repartir sur une saison neuve
            </button>
          )}
        </section>
      )}
    </div>
  )
}
