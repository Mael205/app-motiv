import { useState } from 'react'
import { api } from '../api'
import { Icon } from './art/Icons'
import './RelaxGate.css'

/** Le sas de détente.
 *
 * Il veut parfois scroller avant de bosser. On ne l'interdit pas, on le cadre :
 * trente minutes sans jugement, une fois par soir, puis une notification ferme
 * (SPEC §4.6). Le bouton est volontairement discret — il existe, il n'appelle
 * pas.
 *
 * Il disparaît au palier 1 du §14 : *le privilège de scroller avant de bosser
 * se perd quand la soirée précédente est partie en scroll*. Le refus est dit
 * ici plutôt que découvert au clic — le serveur répond 403 de toute façon, mais
 * un bouton qui échoue se lit comme une panne, pas comme une sanction.
 */
export function RelaxGate({
  used,
  revoked = false,
  onStarted,
}: {
  used: boolean
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

  if (used) {
    return (
      <p className="relax relax--used">
        <Icon.clock size={15} /> Sas déjà pris ce soir. Le prochain est demain.
      </p>
    )
  }

  return (
    <div className="relax">
      <button className="relax__btn" onClick={start} disabled={busy}>
        <Icon.clock size={15} />
        Sas de détente · 30 min
      </button>
      <span className="relax__hint">Sans jugement. Une fois par soir.</span>
      {message && <p className="relax__error">{message}</p>}
    </div>
  )
}
