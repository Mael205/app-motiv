import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Derive } from '../types'
import './Constats.css'

/** Les sept détections continues du §13.5.
 *
 * Elles arrivent **déjà faites** : c'est tout leur intérêt (§0.9). Repérer
 * soi-même qu'un projet n'a pas bougé depuis dix jours est exactement le
 * travail qu'on ne fait pas, et une app qui le demande ne sert à rien.
 *
 * Chaque constat porte une proposition, et la proposition attend un geste. Rien
 * ne se ferme ni ne se baisse tout seul (§17).
 *
 * Le panneau **disparaît quand il n'y a rien à dire** — pas de « tout va bien »,
 * pas de coche verte. Un bloc qui affiche du vide toutes les semaines apprend à
 * être ignoré, et le jour où il parle vraiment il ne se voit plus.
 */

/** Ce qui presse, et ce qui peut attendre dimanche.
 *
 * Le sur-régime et la fin de soirée annoncent un arrêt à venir ; les autres
 * décrivent un état installé. La distinction ne sert qu'à la couleur : le §17
 * interdit d'en faire une alarme.
 */
const URGENTS = new Set<Derive['kind']>(['sur_regime', 'fin_de_soiree', 'migration_scroll'])

export function Constats() {
  const [derives, setDerives] = useState<Derive[] | null>(null)

  useEffect(() => {
    api.detections().then(setDerives).catch(() => setDerives([]))
  }, [])

  if (!derives || derives.length === 0) return null

  return (
    <section className="constats">
      <h3 className="constats__titre label">
        Ce qui se voit dans les chiffres
        <span className="num constats__compte">{derives.length}</span>
      </h3>

      {derives.map((derive) => (
        <article
          key={`${derive.kind}-${derive.constat}`}
          className={`constat${URGENTS.has(derive.kind) ? ' constat--tot' : ''}`}
        >
          <p className="constat__fait">{derive.constat}</p>
          <p className="constat__suite">{derive.proposition}</p>
        </article>
      ))}
    </section>
  )
}
