import { useState } from 'react'
import { api } from '../api'
import type { Proposal } from '../types'
import { Icon } from './art/Icons'
import './AutrePiste.css'

/** L'autre séance possible aujourd'hui (SPEC §11.1, §11.4).
 *
 * La décision du soir reste unique et garde tout le poids visuel. Celle-ci se
 * pose dessous, en une ligne, sans plan ni créneau de durée : elle dit qu'une
 * seconde séance tient dans la journée, et elle se lance en un geste.
 *
 * Sans elle, la piste Corps n'était atteignable que les soirs où elle prenait
 * la décision — c'est-à-dire seulement quand la semaine était déjà en train
 * d'être ratée. Aller à la salle un mardi était impossible à déclarer.
 */
export function AutrePiste({ proposal, onStarted }: { proposal: Proposal; onStarted: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function start() {
    setBusy(true)
    setError('')
    try {
      await api.startSession(proposal.project.id, proposal.minutes)
      onStarted()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Impossible de démarrer.')
      setBusy(false)
    }
  }

  const piste = proposal.track === 'corps' ? 'Corps' : 'Atelier'

  return (
    <section className="autre" aria-label={`Autre séance possible : ${piste}`}>
      <p className="autre__intro">
        <span className="label">Aussi possible aujourd'hui</span>
      </p>

      <div className="autre__ligne">
        <span className="autre__pastille" style={{ background: proposal.project.color }} aria-hidden />
        <span className="autre__nom">{proposal.project.name}</span>
        <span className="autre__piste">{piste}</span>
        <button className="autre__btn" onClick={start} disabled={busy}>
          <Icon.bolt size={15} />
          Lancer
          <span className="num">{proposal.minutes} min</span>
        </button>
      </div>

      {/* La raison porte déjà le créneau quand il y en a un : la redoubler
          ici donnait « Créneau à 20h30. Créneau du jour, 20h30. » */}
      <p className="autre__raison">{proposal.reason}</p>

      {error && <p className="autre__error">{error}</p>}
    </section>
  )
}
