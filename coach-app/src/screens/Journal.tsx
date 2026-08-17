import { useEffect, useState } from 'react'
import { api } from '../api'
import { BuddyReport } from '../components/BuddyReport'
import { Constats } from '../components/Constats'
import type { JournalEntry } from '../types'
import './Journal.css'

/** L'onglet Journal : la trace relisible.
 *
 * C'est ce qui répond au « ça devient flou » du diagnostic. Chronologique,
 * groupé par jour, avec l'amorce laissée à chaque fois.
 *
 * Les constats du §13.5 et le bilan à l'ami (§4.7) vivent ici et pas à
 * l'accueil : le §11.1 veut que l'accueil ne porte qu'une décision, et rien de
 * tout ça ne se fait maintenant. Ce sont des choses qu'on **relit**, et le
 * journal est l'endroit où l'on relit.
 */
export function Journal() {
  const [entries, setEntries] = useState<JournalEntry[] | null>(null)

  useEffect(() => {
    api.journal().then(setEntries)
  }, [])

  if (!entries) return <p className="muted">Chargement…</p>

  if (entries.length === 0) {
    return (
      <div className="journal__empty">
        <h2 className="section-title display">Journal</h2>
        <p className="muted">
          Rien encore. Chaque session terminée écrit une ligne ici — c'est ce qui rend les semaines
          relisibles au lieu de floues.
        </p>
        <Constats />
        <BuddyReport />
      </div>
    )
  }

  const byDay = entries.reduce<Record<string, JournalEntry[]>>((acc, entry) => {
    ;(acc[entry.day] ??= []).push(entry)
    return acc
  }, {})

  const totalMinutes = entries.reduce((sum, e) => sum + e.minutes, 0)

  return (
    <div className="journal">
      <header>
        <h2 className="section-title display">Journal</h2>
        <p className="section-hint">
          <span className="num">{entries.length}</span> sessions ·{' '}
          <span className="num">{Math.round((totalMinutes / 60) * 10) / 10}</span> heures cumulées
        </p>
      </header>

      <Constats />

      {Object.entries(byDay).map(([day, dayEntries]) => (
        <section key={day} className="jday">
          <h3 className="jday__date label">
            {new Date(day).toLocaleDateString('fr-FR', {
              weekday: 'long',
              day: 'numeric',
              month: 'long',
            })}
          </h3>

          {dayEntries.map((entry) => (
            <article key={entry.id} className="jentry" style={{ ['--project' as string]: entry.color }}>
              <div className="jentry__head">
                <span className="jentry__project">{entry.project}</span>
                <span className="num jentry__minutes">{entry.minutes} min</span>
              </div>
              {entry.note && <p className="jentry__note">{entry.note}</p>}
              {entry.next_action && (
                <p className="jentry__next">
                  <span className="label">Amorce</span> {entry.next_action}
                </p>
              )}
            </article>
          ))}
        </section>
      ))}

      <BuddyReport />
    </div>
  )
}
