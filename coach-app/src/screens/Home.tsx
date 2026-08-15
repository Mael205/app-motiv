import { useState } from 'react'
import { motion } from 'motion/react'
import { api } from '../api'
import type { HomeState } from '../types'
import { BossBar } from '../components/BossBar'
import { CharacterHeader } from '../components/CharacterHeader'
import { EveningGauge } from '../components/EveningGauge'
import './Home.css'

/** L'écran d'accueil.
 *
 * Une seule proposition, un seul bouton (SPEC §11.1). Changer de projet reste
 * possible mais coûte un tap de plus et n'est jamais au même niveau visuel.
 */
export function Home({
  state,
  now,
  onStarted,
  onRefresh,
}: {
  state: HomeState
  now: Date
  onStarted: () => void
  onRefresh: () => void
}) {
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState('')
  const [idea, setIdea] = useState('')
  const proposal = state.proposal

  async function start(minutes: number) {
    if (!proposal) return
    setStarting(true)
    setError('')
    try {
      await api.startSession(proposal.project.id, minutes)
      onStarted()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Impossible de démarrer.')
      setStarting(false)
    }
  }

  async function throwInFridge() {
    if (!idea.trim()) return
    await api.addIdea(idea.trim())
    setIdea('')
    onRefresh()
  }

  return (
    <div className="shell">
      <CharacterHeader progression={state.progression} streak={state.streak} season={state.season} />

      {state.streak.message && (
        <div className={`notice notice--${state.streak.sanction_level >= 2 ? 'hard' : 'soft'}`}>
          {state.streak.message}
        </div>
      )}

      <div className="panel">
        <EveningGauge evening={state.evening} now={now} />
      </div>

      {state.boss && (
        <div className="panel">
          <BossBar boss={state.boss} season={state.season} />
        </div>
      )}

      {proposal ? (
        <section className="panel panel--accent proposal">
          <span className="label">Ce soir</span>

          <div className="row proposal__project">
            <span className="proposal__emblem" style={{ color: proposal.project.color }}>
              {proposal.project.emblem}
            </span>
            <div className="stack">
              <h2 className="proposal__name">{proposal.project.name}</h2>
              <span className="muted proposal__reason">{proposal.reason}</span>
            </div>
          </div>

          {proposal.amorce ? (
            <p className="proposal__task">
              <span className="label">L’amorce</span>
              {proposal.amorce}
            </p>
          ) : proposal.step ? (
            <p className="proposal__task">
              <span className="label">Étape en cours</span>
              {proposal.step.label}
              {proposal.step.needs_split && (
                <em className="proposal__split"> — trop grosse, à découper.</em>
              )}
            </p>
          ) : (
            <p className="proposal__task muted">
              Aucune étape exploitable. Écris le prochain jalon avant de démarrer.
            </p>
          )}

          <motion.button
            className="cta"
            onClick={() => start(proposal.minutes)}
            disabled={starting}
            whileTap={{ scale: 0.985 }}
          >
            Démarrer · {proposal.minutes} min
          </motion.button>

          <div className="row proposal__alts">
            <button className="ghost" onClick={() => start(10)} disabled={starting}>
              Mode dégradé · 10 min
            </button>
            <button className="ghost" onClick={() => start(50)} disabled={starting}>
              50 min
            </button>
          </div>

          {error && <p className="proposal__error">{error}</p>}
        </section>
      ) : (
        <section className="panel">
          <p className="muted">
            Aucun projet actif. Ouvre un slot pour que le coach ait quelque chose à proposer.
          </p>
        </section>
      )}

      <div className="grid-2">
        <section className="panel">
          <span className="label">Le plancher</span>
          <p className="floor">
            <span className="num floor__done">{state.minutes_today}</span>
            <span className="muted num"> / {state.required_minutes} min</span>
          </p>
          <p className="muted floor__hint">
            {state.validated_today
              ? 'Journée validée. Le reste est du bonus.'
              : `Une session de ${state.required_minutes} minutes valide la journée.`}
          </p>
        </section>

        <section className="panel">
          <span className="label">Le frigo</span>
          <p className="muted floor__hint">Une idée qui arrive ? Elle attend ici, elle ne prend pas de slot.</p>
          <div className="row fridge">
            <input
              className="fridge__input"
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && throwInFridge()}
              placeholder="Nouvelle idée…"
              aria-label="Nouvelle idée de projet"
            />
            <button className="ghost" onClick={throwInFridge}>
              Jeter
            </button>
          </div>
        </section>
      </div>

      {state.quests.length > 0 && (
        <section className="panel">
          <span className="label">Quêtes du jour</span>
          <ul className="quests">
            {state.quests.map((quest) => (
              <li key={quest.label} className={`quest${quest.done ? ' quest--done' : ''}`}>
                <span className="quest__mark" aria-hidden>
                  {quest.done ? '◆' : '◇'}
                </span>
                <span className="quest__label">{quest.label}</span>
                <span className="num quest__progress">
                  {quest.progress}/{quest.target}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
