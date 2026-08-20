import { useEffect, useState } from 'react'
import { api } from '../api'
import type { BilanDuJour } from '../types'
import './BilanDuMatin.css'

/** La tuile du bilan quotidien (§13.1).
 *
 * `/api/daily` existait depuis le 17 août, la notification partait la nuit, et
 * **rien ne le montrait au réveil** : le seul endroit où lire le bilan était la
 * notification, c'est-à-dire un objet qui disparaît dès qu'on l'a balayé.
 *
 * Sa contrainte n'est pas ce qu'il dit, c'est ce qu'il **demande** : rien.
 * Aucun champ, aucun bouton d'action, aucune proposition. Un seul geste existe,
 * « vu », et il ne fait que refermer la tuile — c'est ce qui la distingue d'une
 * notification qu'on subit et d'un panneau qu'on doit traiter.
 *
 * **Pourquoi elle a le droit d'être sur l'accueil.** Le §11.1 veut que
 * l'accueil ne porte qu'une décision, et cette tuile n'en porte aucune. Elle ne
 * paraît qu'avant l'ouverture de la fenêtre du soir : le matin, il n'y a rien à
 * décider, et le soir elle a déjà disparu. Les deux ne se croisent jamais.
 *
 * **Elle se tait les jours où elle n'aurait rien à dire.** Le serveur tranche —
 * la même règle que la notification de la nuit, calculée une fois. Un bandeau
 * qui annonce tous les matins zéro minute travaillée devient un compteur de
 * reproches, ce que le §17 refuse.
 */
export function BilanDuMatin({ avantLaSoiree }: { avantLaSoiree: boolean }) {
  const [bilan, setBilan] = useState<BilanDuJour | null>(null)
  const [ferme, setFerme] = useState(false)

  useEffect(() => {
    if (!avantLaSoiree) return
    api
      .daily()
      .then(setBilan)
      .catch(() => setBilan(null))
  }, [avantLaSoiree])

  /** « Vu » tient jusqu'au lendemain, et pas plus. La clé porte la journée : le
   *  bilan du jour suivant reparaît de lui-même, sans qu'aucun compteur ne soit
   *  remis à zéro nulle part. */
  const cle = bilan ? `bilan-vu-${bilan.jour}` : ''
  useEffect(() => {
    if (cle) setFerme(localStorage.getItem(cle) === '1')
  }, [cle])

  if (!avantLaSoiree || !bilan || bilan.silencieux || ferme) return null

  return (
    <Tuile
      bilan={bilan}
      onVu={() => {
        localStorage.setItem(cle, '1')
        setFerme(true)
      }}
    />
  )
}

/** La même tuile, sans le geste « vu » ni la fenêtre horaire.
 *
 * Dans le journal, le bilan d'hier est une trace qu'on relit, pas une chose qui
 * vient de tomber : la refermer n'aurait aucun sens, et la cacher passé midi
 * non plus.
 */
export function BilanRelu() {
  const [bilan, setBilan] = useState<BilanDuJour | null>(null)

  useEffect(() => {
    api
      .daily()
      .then(setBilan)
      .catch(() => setBilan(null))
  }, [])

  if (!bilan || bilan.silencieux) return null
  return <Tuile bilan={bilan} />
}

function Tuile({ bilan, onVu }: { bilan: BilanDuJour; onVu?: () => void }) {
  return (
    <section className="bilanj">
      <header className="bilanj__head">
        <span className="label">Hier</span>
        {onVu && (
          <button className="bilanj__vu" onClick={onVu} aria-label="Fermer le bilan d'hier">
            vu
          </button>
        )}
      </header>

      {/* La barre du §13.1 : la part de la fenêtre du soir réellement
          travaillée. Sans repère chiffré ni objectif dessiné dessus — ce n'est
          pas une jauge à remplir, c'est une proportion à constater. */}
      <div className="bilanj__barre" aria-hidden>
        <div className="bilanj__part" style={{ transform: `scaleX(${bilan.part})` }} />
      </div>

      <p className="bilanj__phrase">{bilan.phrase}</p>

      {bilan.repartition.length > 0 && (
        <ul className="bilanj__repartition">
          {bilan.repartition.map((ligne) => (
            <li key={ligne.label}>
              <span>{ligne.label}</span>
              <span className="num">{duree(ligne.minutes)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/** « 1h20 », « 45 min ». Même forme que côté serveur, parce que les deux textes
 *  se lisent dans la même phrase — celle du serveur au-dessus, celle-ci en
 *  dessous — et que deux formats donneraient l'impression de deux mesures. */
function duree(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const heures = Math.floor(minutes / 60)
  const reste = minutes % 60
  return reste ? `${heures}h${String(reste).padStart(2, '0')}` : `${heures}h`
}
