import { useEffect, useState } from 'react'
import { api } from '../api'
import { Icon } from './art/Icons'
import './RelaxGate.css'

/** Le sas de détente.
 *
 * Il **interrompt** la soirée au lieu de la précéder (16 septembre 2026) : la
 * journée est déjà libre jusqu'à l'heure de blocage, donc un sas qui précède
 * n'ouvrait plus rien. Pris pendant un blocage, il rouvre tout — projet du jour
 * et couvre-feu — le temps que le régime de la saison lui laisse : vingt minutes
 * la première, dix au plancher.
 *
 * C'est la soupape qui évite que la seule issue soit la porte de sortie de
 * l'extension, qui lève deux heures d'un coup. Le bouton reste volontairement
 * discret — il existe, il n'appelle pas.
 *
 * Il disparaît au palier 1 du §14 : *le privilège de scroller avant de bosser
 * se perd quand la soirée précédente est partie en scroll*. Le refus est dit
 * ici plutôt que découvert au clic — le serveur répond 403 de toute façon, mais
 * un bouton qui échoue se lit comme une panne, pas comme une sanction.
 */
export function RelaxGate({
  used,
  minutes,
  actif = false,
  attente = false,
  ouvreA = null,
  revoked = false,
  onStarted,
}: {
  used: boolean
  minutes: number
  actif?: boolean
  attente?: boolean
  ouvreA?: string | null
  revoked?: boolean
  onStarted: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  async function start() {
    setBusy(true)
    try {
      await api.startRelax()
      onStarted()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Sas indisponible.')
    } finally {
      setBusy(false)
    }
  }

  if (revoked) {
    return (
      <p className="relax relax--used">
        <Icon.clock size={15} /> Sas indisponible ce soir. Il revient dès que la journée est
        validée.
      </p>
    )
  }

  // Les soixante secondes d'attente, comptées à l'écran. C'est le mécanisme,
  // pas un délai technique : on regarde passer l'impulsion.
  if (attente) {
    return <Attente ouvreA={ouvreA} minutes={minutes} onOuvert={onStarted} />
  }

  if (actif) {
    return (
      <p className="relax relax--used">
        <Icon.clock size={15} /> Sas en cours. Tout est rouvert le temps qu'il dure.
      </p>
    )
  }

  if (used) {
    return (
      <p className="relax relax--used">
        <Icon.clock size={15} /> Sas déjà pris aujourd'hui. Le prochain est demain.
      </p>
    )
  }

  return (
    <div className="relax">
      <button className="relax__btn" onClick={start} disabled={busy}>
        <Icon.clock size={15} />
        Sas de détente · {minutes} min
      </button>
      <span className="relax__hint">Rouvre tout. Une fois par jour, couvre-feu compris.</span>
      {message && <p className="relax__error">{message}</p>}
    </div>
  )
}

/** Le décompte avant ouverture. Il ne propose pas d'annuler : le sas est déjà
 *  consommé, et un bouton « annuler » ferait de l'attente une formalité à
 *  cliquer plutôt qu'un temps à passer. */
function Attente({
  ouvreA,
  minutes,
  onOuvert,
}: {
  ouvreA: string | null
  minutes: number
  onOuvert: () => void
}) {
  const [restant, setRestant] = useState(() => secondesAvant(ouvreA))

  useEffect(() => {
    const id = setInterval(() => {
      const reste = secondesAvant(ouvreA)
      setRestant(reste)
      if (reste <= 0) onOuvert()
    }, 1000)
    return () => clearInterval(id)
  }, [ouvreA, onOuvert])

  return (
    <p className="relax relax--used">
      <Icon.clock size={15} /> Sas dans <span className="num">{restant}</span> s, puis {minutes} min
      d'ouverture.
    </p>
  )
}

function secondesAvant(quand: string | null): number {
  if (!quand) return 0
  return Math.max(0, Math.ceil((new Date(quand).getTime() - Date.now()) / 1000))
}
