import { useEffect, useState } from 'react'
import { api } from '../api'
import type { HautsFaits as HautsFaitsData } from '../types'
import './HautsFaits.css'

/** Les hauts faits obtenus, et les trois plus proches de tomber (§12.3).
 *
 * Les trois prochains sont triés par **part parcourue** et non par distance :
 * « 9 sur 10 » est plus proche que « 90 sur 1000 », alors que la distance brute
 * dit l'inverse. C'est la part qui donne envie de finir.
 *
 * Aucun de ces titres n'est un compliment. Ils décrivent ce qui a eu lieu — le
 * §0.2 dit que le système n'est pas là pour motiver, et un haut fait qui
 * féliciterait serait la porte d'entrée du contraire.
 */
export function HautsFaits() {
  const [panel, setPanel] = useState<HautsFaitsData | null>(null)

  useEffect(() => {
    api.achievements().then(setPanel).catch(() => setPanel(null))
  }, [])

  if (!panel) return null

  return (
    <section className="panel hf">
      <header className="hf__head">
        <span className="label">Hauts faits</span>
        <span className="hf__compte num">
          {panel.obtenus.length} / {panel.total}
        </span>
      </header>

      {panel.prochains.length > 0 && (
        <ul className="hf__prochains">
          {panel.prochains.map((p) => (
            <li key={p.key} className="proche">
              <div className="proche__texte">
                <span className="proche__label">{p.label}</span>
                <span className="proche__desc muted">{p.description}</span>
              </div>
              <div className="proche__jauge" aria-hidden>
                <span style={{ transform: `scaleX(${p.part})` }} />
              </div>
              <span className="proche__compte num">
                {p.valeur} / {p.seuil}
              </span>
            </li>
          ))}
        </ul>
      )}

      {panel.obtenus.length > 0 && (
        <ul className="hf__obtenus">
          {panel.obtenus.map((o) => (
            <li key={o.key} className={`hf__item hf__item--${o.registre}`} title={o.description}>
              {o.label}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
