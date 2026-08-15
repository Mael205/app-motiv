import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { api } from '../api'
import type { RunningSession, SessionResult } from '../types'
import './SessionScreen.css'

type Phase = 'running' | 'debrief' | 'result'

/** L'écran de session.
 *
 * Tout le reste de l'interface s'éteint : on entre quelque part. À la
 * clôture, l'amorce est obligatoire — on paie le démarrage à froid maintenant,
 * pendant que le contexte est encore chaud (SPEC §11.3).
 */
export function SessionScreen({
  session,
  onFinished,
}: {
  session: RunningSession
  onFinished: () => void
}) {
  const [phase, setPhase] = useState<Phase>('running')
  const [elapsed, setElapsed] = useState(0)
  const [note, setNote] = useState('')
  const [nextAction, setNextAction] = useState('')
  const [result, setResult] = useState<SessionResult | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const planned = session.planned_minutes * 60
  const started = new Date(session.started_at).getTime()

  useEffect(() => {
    const tick = () => setElapsed(Math.floor((Date.now() - started) / 1000))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [started])

  const remaining = Math.max(0, planned - elapsed)
  const ratio = Math.min(1, elapsed / planned)
  const minutes = String(Math.floor(remaining / 60)).padStart(2, '0')
  const seconds = String(remaining % 60).padStart(2, '0')
  const over = remaining === 0

  async function submit() {
    if (!nextAction.trim()) {
      setError('L’amorce est obligatoire. Une phrase concrète, exécutable demain.')
      return
    }
    setBusy(true)
    setError('')
    try {
      setResult(await api.endSession(session.id, note, nextAction.trim()))
      setPhase('result')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La clôture a échoué.')
    } finally {
      setBusy(false)
    }
  }

  async function abandon() {
    await api.abandonSession(session.id)
    onFinished()
  }

  const radius = 128
  const circumference = 2 * Math.PI * radius

  return (
    <div className="session" style={{ ['--project' as string]: session.color }}>
      <AnimatePresence mode="wait">
        {phase === 'running' && (
          <motion.div
            key="running"
            className="session__stage"
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.03 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            <span className="label">{session.project}</span>

            <div className="ring">
              <svg viewBox="0 0 300 300" aria-hidden>
                <circle className="ring__track" cx="150" cy="150" r={radius} />
                <circle
                  className="ring__progress"
                  cx="150"
                  cy="150"
                  r={radius}
                  strokeDasharray={circumference}
                  strokeDashoffset={circumference * (1 - ratio)}
                />
              </svg>
              <div className="ring__center">
                <span className={`ring__time num${over ? ' ring__time--over' : ''}`}>
                  {minutes}:{seconds}
                </span>
                <span className="label">{over ? 'temps écoulé' : 'restantes'}</span>
              </div>
            </div>

            <button className="cta" onClick={() => setPhase('debrief')}>
              {over ? 'Clôturer' : 'Terminer maintenant'}
            </button>
            <button className="ghost session__abandon" onClick={abandon}>
              Abandonner la session
            </button>
          </motion.div>
        )}

        {phase === 'debrief' && (
          <motion.div
            key="debrief"
            className="session__stage session__stage--form"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.3 }}
          >
            <h2 className="session__title">Debrief</h2>

            <label className="field">
              <span className="label">Ce que tu as fait</span>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                placeholder="Deux phrases suffisent."
              />
            </label>

            <label className="field">
              <span className="label">L’amorce — première action de la prochaine session</span>
              <textarea
                value={nextAction}
                onChange={(e) => setNextAction(e.target.value)}
                rows={2}
                placeholder="Ex. : écrire le test de collision du monstre, fichier Monster.cpp"
                autoFocus
              />
            </label>

            {error && <p className="session__error">{error}</p>}

            <button className="cta" onClick={submit} disabled={busy}>
              {busy ? 'Enregistrement…' : 'Clôturer la session'}
            </button>
          </motion.div>
        )}

        {phase === 'result' && result && (
          <ResultStage key="result" result={result} onDone={onFinished} />
        )}
      </AnimatePresence>
    </div>
  )
}

/** La séquence de fin de session : un des quatre moments qui portent du juice. */
function ResultStage({ result, onDone }: { result: SessionResult; onDone: () => void }) {
  const [shown, setShown] = useState(0)

  useEffect(() => {
    if (shown >= result.xp) return
    const step = Math.max(1, Math.round(result.xp / 30))
    const id = setTimeout(() => setShown((v) => Math.min(result.xp, v + step)), 24)
    return () => clearTimeout(id)
  }, [shown, result.xp])

  const b = result.breakdown

  return (
    <motion.div
      className="session__stage"
      initial={{ opacity: 0, scale: 0.94 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: 'spring', stiffness: 240, damping: 20 }}
    >
      <span className="label">Session terminée</span>

      <motion.div
        className="result__xp"
        initial={{ scale: 0.7 }}
        animate={{ scale: [0.7, 1.12, 1] }}
        transition={{ duration: 0.5, times: [0, 0.6, 1], ease: 'easeOut' }}
      >
        <span className="num result__xp-value">{shown}</span>
        <span className="label">xp</span>
      </motion.div>

      <ul className="result__lines">
        <li>
          <span>{result.minutes} minutes</span>
          <span className="num">+{b.base}</span>
        </li>
        {b.first_of_day > 0 && (
          <li>
            <span>Première session du jour</span>
            <span className="num">+{b.first_of_day}</span>
          </li>
        )}
        {b.early > 0 && (
          <li>
            <span>Démarrée avant 20h</span>
            <span className="num">+{b.early}</span>
          </li>
        )}
        {b.streak_multiplier > 1 && (
          <li>
            <span>Streak</span>
            <span className="num">×{b.streak_multiplier.toFixed(2)}</span>
          </li>
        )}
        {b.momentum_multiplier > 1 && (
          <li>
            <span>Momentum</span>
            <span className="num">×{b.momentum_multiplier.toFixed(2)}</span>
          </li>
        )}
        {b.degressivity < 1 && (
          <li className="result__cap">
            <span>Plafond de régime</span>
            <span className="num">×{b.degressivity}</span>
          </li>
        )}
        <li className="result__damage">
          <span>Dégâts au boss</span>
          <span className="num">−{result.boss_damage}</span>
        </li>
      </ul>

      {b.notes.map((note) => (
        <p key={note} className="result__note">
          {note}
        </p>
      ))}

      {result.achievements.map((achievement) => (
        <motion.div
          key={achievement.key}
          className="result__achievement"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <span className="label">Haut fait débloqué</span>
          <strong className="display">{achievement.label}</strong>
          <span className="muted">{achievement.description}</span>
        </motion.div>
      ))}

      <button className="cta" onClick={onDone}>
        Retour
      </button>
    </motion.div>
  )
}
