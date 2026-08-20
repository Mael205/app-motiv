import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { api } from '../api'
import { Ascension } from '../components/Ascension'
import { Burst, CountUp, sfx, useTrauma } from '../juice'
import type { DebriefSuggestion, RunningSession, SessionResult } from '../types'
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
  const [suggesting, setSuggesting] = useState(false)
  const [suggestion, setSuggestion] = useState<DebriefSuggestion | null>(null)
  /** La difficulté ressentie, en un tap. Facultative — un champ obligatoire de
   *  plus à la clôture ferait renoncer à clôturer, et une clôture manquée coûte
   *  bien plus qu'une difficulté inconnue. Elle n'entre dans aucun calcul :
   *  c'est ce qui garantit qu'on peut répondre honnêtement. */
  const [difficulty, setDifficulty] = useState<1 | 2 | 3 | null>(null)

  /** Propose une amorce a partir des notes brutes. **Ne cloture rien.**
   *
   * Le §11.3 fait de l'amorce le prix paye pour le demarrage a froid de la
   * prochaine session. La faire ecrire par un modele sans relecture viderait
   * l'exercice de son sens : on validerait par reflexe une consigne que
   * personne n'a comprise, et la session suivante demarrerait a faux. Elle
   * arrive donc dans le champ, modifiable, et c'est toujours l'utilisateur qui
   * cloture. */
  async function suggest() {
    if (!note.trim()) return
    setSuggesting(true)
    setError('')
    try {
      const recu = await api.debrief(session.id, note)
      setSuggestion(recu)
      if (recu.amorce) setNextAction(recu.amorce)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Suggestion indisponible.')
    } finally {
      setSuggesting(false)
    }
  }

  /** L'objectif vit en local **et** en props : la prolongation doit se voir au
   *  clic, pas au prochain rafraîchissement de l'accueil dix secondes plus
   *  tard. Le serveur reste la source de vérité — il rend le nouvel objectif,
   *  et c'est lui qu'on affiche. */
  const [objectif, setObjectif] = useState(session.planned_minutes)
  const [prolongations, setProlongations] = useState(session.extensions ?? 0)
  const [prolongeant, setProlongeant] = useState(false)
  useEffect(() => setObjectif(session.planned_minutes), [session.planned_minutes])

  const planned = objectif * 60
  const started = new Date(session.started_at).getTime()

  useEffect(() => {
    const tick = () => setElapsed(Math.floor((Date.now() - started) / 1000))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [started])

  const remaining = Math.max(0, planned - elapsed)
  const ratio = Math.min(1, elapsed / planned)
  const over = remaining === 0
  /** Passé le terme, l'anneau compte **à l'endroit** : le temps en plus est du
   *  travail qui compte désormais, et un 00:00 figé le disait perdu. */
  const affiche = over ? elapsed - planned : remaining
  const minutes = String(Math.floor(affiche / 60)).padStart(2, '0')
  const seconds = String(affiche % 60).padStart(2, '0')

  /** Prolonge de quinze minutes. C'est le seul geste qui fasse monter
   *  l'objectif : il n'a pas d'inverse, parce que raccourcir une promesse en
   *  cours revient à clôturer, et le bouton existe juste en dessous. */
  async function prolonger() {
    setProlongeant(true)
    setError('')
    try {
      const etat = await api.extendSession(session.id)
      setObjectif(etat.planned_minutes)
      setProlongations(etat.extensions)
      sfx.sessionExtend()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La prolongation a échoué.')
    } finally {
      setProlongeant(false)
    }
  }

  async function submit() {
    if (!nextAction.trim()) {
      setError('L’amorce est obligatoire. Une phrase concrète, exécutable demain.')
      return
    }
    setBusy(true)
    setError('')
    try {
      setResult(await api.endSession(session.id, note, nextAction.trim(), difficulty))
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
                  {over ? '+' : ''}
                  {minutes}:{seconds}
                </span>
                {/* Le mot change parce que le compteur a changé de sens : avant
                    le terme il décompte une promesse, après il compte du travail
                    qui s'ajoute. */}
                <span className="label">{over ? 'en plus, et ça compte' : 'restantes'}</span>
              </div>
            </div>

            {/* L'objectif annoncé reste écrit. Sans lui, un minuteur qu'on peut
                dépasser et clôturer à volonté n'annonce plus rien — et c'est
                justement ce que le §11.1 fait dire au démarrage : une durée. */}
            <p className="session__objectif">
              Objectif <span className="num">{objectif}</span> min
              {prolongations ? ` · prolongée ${prolongations}×` : ''}
            </p>

            <button className="cta" onClick={() => setPhase('debrief')}>
              {over ? 'Clôturer' : 'Terminer maintenant'}
            </button>
            <button className="ghost session__extend" onClick={prolonger} disabled={prolongeant}>
              {prolongeant ? 'Un instant…' : '+15 minutes'}
            </button>
            <button className="ghost session__abandon" onClick={abandon}>
              Abandonner la session
            </button>
            {error && <p className="session__error">{error}</p>}
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

            <button
              className="ghost session__suggest"
              onClick={suggest}
              disabled={suggesting || !note.trim()}
            >
              {suggesting ? 'Lecture des notes…' : 'Proposer une amorce à partir des notes'}
            </button>

            {suggestion?.ai_note && <p className="muted session__hint">{suggestion.ai_note}</p>}

            {suggestion && suggestion.blocages.length > 0 && (
              <ul className="session__blocks">
                {suggestion.blocages.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            )}

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

            {/* La seule question du système qui porte sur la qualité et non sur
                le volume. Trois sessions d'affilée « trop facile » ne veulent
                pas dire qu'on travaille mal — ça veut dire qu'on a cessé
                d'apprendre, et aucun autre compteur ne le voit : sur tous les
                autres, c'est même une bonne série. */}
            <div className="difficulte">
              <span className="label">Le niveau, honnêtement</span>
              <div className="difficulte__choix">
                {([[1, 'Trop facile'], [2, 'Juste'], [3, 'Trop dur']] as const).map(([n, mot]) => (
                  <button
                    key={n}
                    type="button"
                    className={`difficulte__bouton${difficulty === n ? ' difficulte__bouton--actif' : ''}`}
                    onClick={() => setDifficulty(difficulty === n ? null : n)}
                    aria-pressed={difficulty === n}
                  >
                    {mot}
                  </button>
                ))}
              </div>
              <p className="difficulte__note">
                N'entre dans aucun calcul : ni XP, ni streak. C'est ce qui permet d'y répondre
                honnêtement.
              </p>
            </div>

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

/** La séquence 2 du §7 : l'impact de fin de session.
 *
 * > le bloc se pose sur la jauge du soir avec un impact (léger hit-stop puis
 * > rebond), la barre d'XP se remplit avec un compteur qui défile et une
 * > **décélération marquée**, les dégâts au boss s'affichent en chiffres qui
 * > montent.
 *
 * Les canaux sont empilés comme le recommande `game-feel` : secousse, gerbe,
 * compteur, et un décalage entre l'XP et les dégâts au boss pour qu'on ait le
 * temps de lire les deux. Le tout dure moins d'une seconde et demie — au-delà,
 * on attend au lieu de savourer.
 *
 * La séquence 3 (niveau, palier, relique, carte) s'enchaîne ensuite, et
 * seulement s'il y a quelque chose à montrer.
 */
/** La gerbe de fin, selon l'effet de fin équipé.
 *
 * Lue sur `data-finisher` du document plutôt que passée en props : la séquence
 * de fin est loin de l'endroit qui charge l'état, et faire descendre un
 * cosmétique à travers quatre composants pour changer une couleur de
 * particules coûterait plus cher que ce que ça rapporte.
 *
 * Aucune de ces variantes ne change un chiffre. Elles changent un nombre de
 * particules et une couleur — c'est tout ce qu'un cosmétique a le droit de
 * faire (§17).
 */
function finisseur(): { count: number; spread: number; color?: string } {
  const effet = typeof document !== 'undefined' ? document.body.dataset.finisher : ''
  switch (effet) {
    case 'shockwave':
      return { count: 34, spread: 320 }
    case 'fracture':
      return { count: 44, spread: 280, color: '#8B6FE8' }
    case 'ascension':
      return { count: 56, spread: 400, color: '#E8A33D' }
    case 'frost':
      return { count: 26, spread: 240, color: '#5FA8DE' }
    case 'slash':
      return { count: 18, spread: 420 }
    case 'seal':
      return { count: 30, spread: 180, color: '#C9A227' }
    case 'eclipse':
      return { count: 60, spread: 340, color: '#E85F9F' }
    case 'ember':
      return { count: 24, spread: 210, color: '#E8843D' }
    case 'dust':
      return { count: 16, spread: 160 }
    /* Troisième vague (J6). Chacune change un nombre de particules et une
       couleur, jamais un chiffre : le §17 interdit qu'un cosmétique devienne du
       pouvoir, et une gerbe reste une gerbe. */
    case 'filings':
      return { count: 20, spread: 190, color: '#9FB3C8' }
    case 'breath':
      return { count: 28, spread: 260, color: '#7FD8C0' }
    case 'anvil':
      return { count: 38, spread: 200, color: '#C87D4A' }
    case 'dawn':
      return { count: 52, spread: 360, color: '#F0E2B6' }
    default:
      return { count: 22, spread: 200 }
  }
}

function ResultStage({ result, onDone }: { result: SessionResult; onDone: () => void }) {
  const { shake, style } = useTrauma()
  const [xpDone, setXpDone] = useState(false)
  const [ascending, setAscending] = useState(false)

  // Le coup critique se joue en **deux temps** : le compteur monte d'abord au
  // total normal, puis repart et double. Afficher directement le total doublé
  // reviendrait à ne rien montrer du tout — on ne saurait pas ce qui a doublé,
  // seulement qu'un nombre est gros. C'est la même règle que partout ailleurs
  // dans le §7 : ce qui se met en scène est le franchissement, pas l'état.
  const crit = result.crit
  const [critLance, setCritLance] = useState(false)

  const hasAscension =
    result.levelled_up ||
    !!result.branch_tier ||
    !!result.relics?.length ||
    !!result.cards?.length ||
    !!result.boss_phase

  // L'impact part au montage, calibré sur la taille de la session : une session
  // dégradée de dix minutes ne secoue pas comme une longue de cinquante.
  useEffect(() => {
    shake(Math.min(0.7, 0.22 + result.minutes / 120))
  }, [shake, result.minutes])

  const b = result.breakdown

  if (ascending) return <Ascension result={result} onDone={onDone} />

  return (
    <motion.div
      className="session__stage"
      style={style}
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
        {/* L'effet de fin équipé (§12.6). Il change la gerbe, jamais le nombre :
            le §17 interdit qu'un cosmétique touche à la mesure, et une carte qui
            modifierait l'XP affichée serait exactement ça. */}
        <Burst {...finisseur()} />
        {crit && !critLance ? (
          <CountUp
            to={b.base_total}
            duration={1100}
            className="result__xp-value"
            onDone={() => {
              sfx.crit()
              shake(0.6)
              setCritLance(true)
            }}
          />
        ) : (
          <CountUp
            to={result.xp}
            from={crit ? b.base_total : 0}
            duration={crit ? 620 : 1100}
            className={`result__xp-value${crit ? ' result__xp-value--crit' : ''}`}
            onDone={() => setXpDone(true)}
          />
        )}
        <span className="label">xp</span>
        {crit && critLance && (
          <motion.span
            className="result__crit"
            initial={{ opacity: 0, scale: 0.6, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 420, damping: 16 }}
          >
            {crit.label} ×{crit.multiplier}
          </motion.span>
        )}
      </motion.div>

      {/* L'objectif annoncé, relu à la clôture. Ni félicitation ni reproche :
          deux nombres et un verbe, comme le §17 l'impose au bilan quotidien. */}
      <p className="result__objectif">
        {result.objectif_tenu
          ? `Objectif ${result.objectif} min tenu${
              result.depassement ? ` · ${result.depassement} min en plus` : ''
            }`
          : `Objectif ${result.objectif} min · clôturée à ${result.minutes}`}
      </p>

      <ul className="result__lines">
        <li>
          <span>{result.minutes} minutes</span>
          <span className="num">+{b.base}</span>
        </li>
        {b.duration_premium > 0 && (
          <li>
            <span>Prime de durée</span>
            <span className="num">+{b.duration_premium}</span>
          </li>
        )}
        {b.first_of_day > 0 && (
          <li>
            <span>Première session du jour</span>
            <span className="num">+{b.first_of_day}</span>
          </li>
        )}
        {b.punctual > 0 && (
          <li>
            <span>Créneau tenu</span>
            <span className="num">+{b.punctual}</span>
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
        {crit && (
          <li className="result__crit-line">
            <span>{crit.label}</span>
            <span className="num">×{crit.multiplier}</span>
          </li>
        )}
        <li className="result__damage">
          <span>Dégâts au boss</span>
          {xpDone ? (
            <CountUp to={result.boss_damage} duration={600} prefix="−" />
          ) : (
            <span className="num">−0</span>
          )}
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

      <button className="cta" onClick={() => (hasAscension ? setAscending(true) : onDone())}>
        {hasAscension ? 'Voir les récompenses' : 'Retour'}
      </button>
    </motion.div>
  )
}
