import { useEffect, useState } from 'react'
import { api } from '../api'
import type { GardesPanel } from '../types'
import './GardePanel.css'

/** Les gardes : ce qu'il s'agit de ne pas faire (SPEC §11.10).
 *
 * Aucune garde ne vise zéro — chacune porte un budget hebdomadaire, et rester
 * dessous **est** l'objectif atteint. Le grand chiffre est le cumul de jours
 * tenus, qui ne redescend jamais : un dépassement n'efface rien.
 *
 * Le ton est une règle, pas une préférence. Ce composant n'affiche jamais de
 * rouge, jamais de point d'exclamation, jamais de félicitation. Une journée
 * marquée se déclare aussi calmement qu'une journée tenue — c'est justement
 * pour ça qu'elle sera déclarée honnêtement.
 */
export function GardePanel({ initial }: { initial: GardesPanel }) {
  const [panel, setPanel] = useState(initial)
  const [busy, setBusy] = useState<number | null>(null)

  useEffect(() => setPanel(initial), [initial])

  async function declare(id: number, occurred: boolean) {
    setBusy(id)
    try {
      setPanel(await api.declareGarde(id, occurred))
    } finally {
      setBusy(null)
    }
  }

  if (panel.gardes.length === 0) return null

  return (
    <section className="panel gardes">
      <header className="gardes__head">
        <h2 className="display gardes__title">Gardes</h2>
        <span className="gardes__count">
          {panel.to_declare === 0 ? 'journée déclarée' : `${panel.to_declare} à déclarer`}
        </span>
      </header>

      <ul className="gardes__list">
        {panel.gardes.map((garde) => (
          <li key={garde.id} className="garde">
            <div className="garde__row">
              <span className="garde__name">{garde.name}</span>
              <span className={`garde__week${garde.week_held ? '' : ' garde__week--over'}`}>
                {garde.week_label}
              </span>
            </div>

            <div className="garde__actions">
              <button
                className={`garde__btn${
                  garde.declared_today && !garde.occurred_today ? ' garde__btn--on' : ''
                }`}
                onClick={() => declare(garde.id, false)}
                disabled={busy === garde.id}
              >
                Tenue
              </button>
              <button
                className={`garde__btn${
                  garde.declared_today && garde.occurred_today ? ' garde__btn--on' : ''
                }`}
                onClick={() => declare(garde.id, true)}
                disabled={busy === garde.id}
              >
                C'est arrivé
              </button>
              <span className="garde__total">{garde.held_days} j tenus</span>
            </div>

            {garde.declared_today && <p className="garde__message">{garde.message}</p>}
          </li>
        ))}
      </ul>

      <p className="gardes__foot">
        Un budget, pas une interdiction. Rester dessous est l'objectif, pas un compromis.
      </p>
    </section>
  )
}
