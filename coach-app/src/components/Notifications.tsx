import { useState } from 'react'
import {
  activerLesNotifications,
  etatDesNotifications,
  type EtatDesNotifications,
} from '../push'
import './Notifications.css'

/** L'interrupteur des notifications système (SPEC §11.2).
 *
 * Il vit dans le journal et pas sur l'accueil : c'est un réglage, et l'accueil
 * ne porte qu'une décision (§11.1). Il ne s'affiche que lorsqu'il a quelque
 * chose à dire — permission jamais demandée, ou refusée.
 *
 * **Une seule ligne quand tout va bien, rien du tout après.** Un panneau
 * « notifications activées ✓ » affiché en permanence est un félicitation
 * déguisée, et le §17 n'en veut pas plus ici qu'ailleurs.
 */
export function Notifications() {
  const [etat, setEtat] = useState<EtatDesNotifications>(etatDesNotifications)
  const [occupe, setOccupe] = useState(false)

  if (etat === 'actif') return null

  if (etat === 'impossible') {
    return (
      <p className="notifs notifs--muet">
        Ce navigateur ne sait pas afficher de notification système. Le gardien du soir passe par
        Discord.
      </p>
    )
  }

  if (etat === 'refuse') {
    return (
      <p className="notifs notifs--muet">
        Les notifications sont refusées pour ce site. Le navigateur ne repose pas la question : il
        faut la rouvrir dans ses réglages de site. En attendant, le gardien passe par Discord.
      </p>
    )
  }

  return (
    <div className="notifs">
      <p className="notifs__texte">
        Le gardien du soir, le rappel de créneau et le bilan du matin peuvent arriver en
        notification système — avec « Démarrer 10 min » et « Reporter » dessus. Sans ça, ils
        n'arrivent que sur Discord.
      </p>
      <button
        className="ghost"
        disabled={occupe}
        onClick={async () => {
          setOccupe(true)
          setEtat(await activerLesNotifications())
          setOccupe(false)
        }}
      >
        {occupe ? 'Un instant…' : 'Activer les notifications'}
      </button>
    </div>
  )
}
