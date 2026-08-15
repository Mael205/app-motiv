import { useEffect, useState } from 'react'
import { api } from '../api'
import type { EntretienPanel } from '../types'
import './RoutinePanel.css'

/** Le panneau de quêtes d'entretien (SPEC §11.9).
 *
 * Registre de panneau de quêtes assumé, mécanique punitive non empruntée : une
 * journée où rien n'est coché a exactement le même panneau qu'une journée
 * pleine, à la coche près. Aucun compte à rebours, aucune mise en scène de
 * l'échec, aucune XP — la récompense est en Éclats et s'arrête à l'objectif
 * hebdomadaire.
 *
 * Le seul grand chiffre est le cumul de semaines tenues, qui ne redescend
 * jamais : c'est la seule progression strictement monotone du système.
 */
export function RoutinePanel({ initial }: { initial: EntretienPanel }) {
  const [panel, setPanel] = useState(initial)
  const [busy, setBusy] = useState<number | null>(null)
  const [message, setMessage] = useState('')

  useEffect(() => setPanel(initial), [initial])

  async function toggle(id: number, checked: boolean) {
    setBusy(id)
    setMessage('')
    try {
      const result = checked ? await api.uncheckRoutine(id) : await api.checkRoutine(id)
      setPanel(result.panel)
      if (result.shards > 0) setMessage(`+${result.shards} Éclats`)
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Coche impossible.')
    } finally {
      setBusy(null)
    }
  }

  if (panel.due_today === 0) return null

  return (
    <section className="panel routines">
      <header className="routines__head">
        <h2 className="display routines__title">Entretien</h2>
        <span className="routines__count">
          {panel.done_today} / {panel.due_today}
        </span>
      </header>

      {panel.groups.map((group) => (
        <div key={group.anchor} className="routines__group">
          <p className="routines__anchor">{group.label}</p>
          <ul className="routines__list">
            {group.routines.map((routine) => (
              <li key={routine.id}>
                <button
                  type="button"
                  className={`routine${routine.checked ? ' routine--done' : ''}`}
                  onClick={() => toggle(routine.id, routine.checked)}
                  disabled={busy === routine.id}
                  aria-pressed={routine.checked}
                >
                  <span className="routine__mark" aria-hidden>
                    {routine.checked ? '◆' : '◇'}
                  </span>
                  <span className="routine__name">{routine.name}</span>
                  <span
                    className={`routine__week${routine.week_held ? ' routine__week--held' : ''}`}
                    title={
                      routine.slack > 0
                        ? `${routine.slack} oubli${routine.slack > 1 ? 's' : ''} toléré${
                            routine.slack > 1 ? 's' : ''
                          } cette semaine`
                        : 'Aucun battement : objectif à sept jours sur sept'
                    }
                  >
                    {routine.week_label}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}

      <footer className="routines__foot">
        <span className="routines__weeks">
          {panel.held_weeks} semaine{panel.held_weeks > 1 ? 's' : ''} tenue
          {panel.held_weeks > 1 ? 's' : ''}
        </span>
        {message && <span className="routines__flash">{message}</span>}
      </footer>
    </section>
  )
}
