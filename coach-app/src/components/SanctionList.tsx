import type { Sanctions } from '../types'
import './SanctionList.css'

/** Ce qui est éteint ce soir (SPEC §14, paliers 1 et 2).
 *
 * Une liste de constats, et rien de plus. Les libellés viennent **entiers du
 * serveur** : le §14 fait du ton une règle — *« la sanction est un état de
 * fait affiché, chiffré, pas un jugement »* — et un texte réécrit dans un
 * composant serait un texte que le test du ton ne surveille plus.
 *
 * Le composant ne se rend pas au palier 3 : le serveur y renvoie une liste
 * vide, parce qu'énumérer ce qui est perdu à quelqu'un qui n'a rien fait
 * depuis trois jours est exactement ce que le §14 interdit.
 *
 * Le pied de bloc dit toujours comment ça se répare. C'est le premier des
 * quatre invariants du §14 — *réparable en dix minutes* — et une sanction dont
 * la sortie n'est pas écrite se lit comme une punition sans fin.
 *
 * L'en-tête ne promet aucune durée, parce que les lignes n'ont pas toutes la
 * même : la vitrine rouvre ce soir, le titre demande trois journées. Chaque
 * ligne porte donc ses propres termes, et l'en-tête se contente de nommer.
 */
export function SanctionList({ sanctions }: { sanctions: Sanctions }) {
  if (!sanctions.lines.length) return null

  return (
    <section className="sanctions" aria-label="Ce qui est éteint">
      <span className="label sanctions__head">Ce qui est éteint</span>

      <ul className="sanctions__list">
        {sanctions.lines.map((line) => (
          <li key={line} className="sanctions__item">
            <span className="sanctions__mark" aria-hidden>
              ·
            </span>
            {line}
          </li>
        ))}
      </ul>

      <p className="sanctions__out">Dix minutes suffisent.</p>
    </section>
  )
}
