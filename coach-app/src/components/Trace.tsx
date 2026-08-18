import { useEffect, useState } from 'react'
import { api } from '../api'
import type { TraceLongue } from '../types'
import './Trace.css'

/** La trace longue : les compteurs qui ne redescendent jamais.
 *
 * Tout le reste du produit mesure du **présent** — le streak en cours, la
 * semaine en cours, la vie du boss, l'écart au fantôme aujourd'hui. C'est ce
 * qu'il faut pour décider quoi faire ce soir (§11.1), et c'est aussi ce qui
 * rend un jour raté brutal : au matin du jour 1, tous les chiffres de l'app
 * disent zéro, et aucun ne dit qu'on a travaillé cent quarante heures.
 *
 * Aucun compteur affiché ici ne peut baisser. Pas de série en cours, pas de
 * moyenne, pas de pourcentage hebdomadaire : un seul suffirait à annuler
 * l'écran, puisqu'on l'ouvre en ayant déjà perdu quelque chose.
 *
 * **Aucune phrase.** Pas de « tu as déjà fait tellement », pas de « ça repart
 * demain ». Le §17 interdit au système d'encourager comme il lui interdit de
 * reprocher — un commentaire tombe toujours à côté un jour ou l'autre, et ce
 * jour-là il coûte plus qu'il n'a jamais rapporté. Il n'y a que des nombres et
 * leur date.
 */
export function Trace({ compact = false }: { compact?: boolean }) {
  const [trace, setTrace] = useState<TraceLongue | null>(null)

  useEffect(() => {
    api.trace().then(setTrace).catch(() => setTrace(null))
  }, [])

  if (!trace) return null

  const depuis = trace.since
    ? new Date(trace.since).toLocaleDateString('fr-FR', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      })
    : null

  return (
    <section className="panel trace">
      <header className="trace__head">
        <span className="label">La trace</span>
        {depuis && (
          <span className="trace__depuis muted">
            depuis le {depuis} · <span className="num">{trace.days_since}</span> jours
          </span>
        )}
      </header>

      <ul className="trace__grid">
        {trace.compteurs.map((c) => (
          <li key={c.label} className="trace__cell">
            <span className="trace__value num">
              {c.value.toLocaleString('fr-FR')}
              {c.unit}
            </span>
            <span className="trace__label">{c.label}</span>
          </li>
        ))}
      </ul>

      {!compact && trace.branches.length > 0 && (
        <ul className="trace__branches">
          {trace.branches.map((b) => (
            <li key={b.key} style={{ ['--branch' as string]: b.color }}>
              <span className="trace__branch-name">{b.label}</span>
              <span className="num">{b.hours} h</span>
            </li>
          ))}
        </ul>
      )}

      {!compact && trace.titres.length > 0 && (
        <p className="trace__titres muted">{trace.titres.join(' · ')}</p>
      )}
    </section>
  )
}
