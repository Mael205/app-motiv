import { useCallback, useEffect, useState } from 'react'
import { useRevelation } from '../juice'
import { EnCharge, EnErreur } from '../components/EtatCharge'
import { api } from '../api'
import { BilanRelu } from '../components/BilanDuMatin'
import { BuddyReport } from '../components/BuddyReport'
import { Constats } from '../components/Constats'
import { Export } from '../components/Export'
import { Fuite } from '../components/Fuite'
import { Notifications } from '../components/Notifications'
import { Revue } from '../components/Revue'
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
  const [erreur, setErreur] = useState('')

  /* `.then(setEntries)` sans `.catch` laissait l'écran sur « Chargement… »
     indéfiniment dès que l'API ne répondait pas, et rejetait une promesse dans
     le vide. Le rechargement est nommé pour que « Réessayer » puisse le
     rappeler. */
  const charger = useCallback(async () => {
    try {
      setErreur('')
      setEntries(await api.journal())
    } catch (e) {
      setErreur(e instanceof Error ? e.message : 'Chargement impossible.')
    }
  }, [])

  useEffect(() => {
    charger()
  }, [charger])

  /* Les entrees et les rubriques se levent au defilement ; le journal est
     l'ecran le plus long du produit, et tout faire entrer au montage revenait
     a n'animer que les deux premieres lignes. */
  const scene = useRevelation(
    { devoiler: '.section-title, .rule-title', lever: '.jentry, .revue__q, .revue__bloc' },
    Boolean(entries),
  )

  if (erreur) return <EnErreur message={erreur} onRetry={charger} />
  if (!entries) return <EnCharge />

  if (entries.length === 0) {
    return (
      <div className="journal__empty" ref={scene}>
        <h2 className="section-title display">Journal</h2>
        <p className="muted">
          Rien encore. Chaque session terminée écrit une ligne ici — c'est ce qui rend les semaines
          relisibles au lieu de floues.
        </p>
        <BilanRelu />
        <Constats />
        <Revue />
        <Fuite />
        <BuddyReport />
        <Notifications />
        <Export />
      </div>
    )
  }

  const byDay = entries.reduce<Record<string, JournalEntry[]>>((acc, entry) => {
    ;(acc[entry.day] ??= []).push(entry)
    return acc
  }, {})

  const totalMinutes = entries.reduce((sum, e) => sum + e.minutes, 0)

  return (
    <div className="journal" ref={scene}>
      <header>
        <h2 className="section-title display">Journal</h2>
        <p className="section-hint">
          <span className="num">{entries.length}</span> sessions ·{' '}
          <span className="num">{Math.round((totalMinutes / 60) * 10) / 10}</span> heures cumulées
        </p>
      </header>

      <BilanRelu />
      <Constats />
      <Revue />

      {Object.entries(byDay).map(([day, dayEntries]) => (
        <section key={day} className="jday">
          <h3 className="jday__date rule-title">
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

      <Fuite />
      <BuddyReport />
      <Notifications />
      <Export />
    </div>
  )
}
