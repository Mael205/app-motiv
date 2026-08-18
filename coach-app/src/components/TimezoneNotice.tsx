import { useEffect, useState } from 'react'
import { api } from '../api'
import type { TimezoneCheck } from '../types'
import './TimezoneNotice.css'

/** L'écart de fuseau constaté, et la proposition de basculer (§1 étendu).
 *
 * Tout le produit est indexé sur deux choses : la fenêtre du soir et la
 * bascule de 4h. Les deux se calculent dans le fuseau du profil, réglé une
 * fois à l'installation. Un voyage casse les deux **en silence** — à Montréal
 * la fenêtre « 20h–23h » s'ouvre à 14h heure locale, le gardien part au milieu
 * de l'après-midi, et rien ne dit pourquoi.
 *
 * Détecté, jamais appliqué. Une escale de trois heures n'est pas un
 * déménagement, et le §11.1 n'autorise le système à décider que de ce qu'on
 * fait maintenant. D'où le bouton, et d'où le second — « je ne fais que
 * passer » range la bande pour la session sans rien changer au profil.
 *
 * Le refus est gardé en mémoire de session et non en stockage durable : au
 * retour du voyage, la question ne se pose plus d'elle-même, et si elle se
 * repose c'est qu'on a vraiment déménagé.
 */
export function TimezoneNotice() {
  const [ecart, setEcart] = useState<TimezoneCheck | null>(null)
  const [range, setRange] = useState(
    () => sessionStorage.getItem('coach.tz.ignore') === '1',
  )

  useEffect(() => {
    const appareil = Intl.DateTimeFormat().resolvedOptions().timeZone
    if (!appareil) return
    api
      .checkTimezone(appareil)
      .then((recu) => setEcart(recu.proposed ? recu : null))
      .catch(() => setEcart(null))
  }, [])

  if (!ecart || range) return null

  return (
    <div className="tznotice">
      <p className="tznotice__line">{ecart.line}</p>
      <div className="row">
        <button
          className="ghost"
          onClick={async () => {
            await api.switchTimezone(ecart.detected)
            location.reload()
          }}
        >
          Basculer sur {ecart.detected}
        </button>
        <button
          className="ghost"
          onClick={() => {
            sessionStorage.setItem('coach.tz.ignore', '1')
            setRange(true)
          }}
        >
          Je ne fais que passer
        </button>
      </div>
    </div>
  )
}
