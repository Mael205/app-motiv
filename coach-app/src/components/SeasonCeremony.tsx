import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { api } from '../api'
import { Burst, CountUp, Rays, useReducedMotion, useTrauma } from '../juice'
import { LootReveal } from './LootReveal'
import { SeasonSigil } from './art/SeasonSigil'
import type { SeasonOffer, SeasonReport } from '../types'
import './SeasonCeremony.css'

/** La quatrième séquence du §7, et l'ouverture du §12.2.
 *
 * > **Fin de saison** — séquence dédiée : score final, comparaison au fantôme,
 * > titre décerné, ouverture de la saison suivante.
 *
 * > L'écran d'ouverture affiche le nom en grand, l'emblème, le modificateur
 * > tiré et le boss. **C'est le seul moment où l'interface a le droit d'être
 * > théâtrale.**
 *
 * Les deux vivent dans le même composant parce qu'ils sont le même moment :
 * séparer la clôture de l'ouverture laisserait un état sans saison — donc sans
 * boss, sans mise et sans horizon — exactement là où l'on avait le plus besoin
 * de relancer.
 *
 * La grammaire vient de `docs/direction-visuelle.md` : entrée slam avec
 * dépassement, couronne de rayons vive au centre, chiffre géant à double ombre
 * portée, canaux empilés et dosés. Le titre décerné reçoit le traitement le
 * plus fort de l'app après le passage de niveau — c'est ce qui reste de quatre
 * semaines.
 *
 * **Le choix n'est jamais animé.** Une fois arrivé sur les modificateurs, tout
 * se calme : on est en train de décider de son mois, pas de regarder un
 * spectacle.
 */
type Beat = 'score' | 'phantom' | 'title' | 'cards' | 'offer'

export function SeasonCeremony({
  report,
  offer,
  onDone,
}: {
  report: SeasonReport | null
  offer: SeasonOffer
  onDone: () => void
}) {
  const reduced = useReducedMotion()
  const { shake, style } = useTrauma()

  // Sans bilan — première saison de la vie — on ouvre directement.
  const beats = useMemo<Beat[]>(() => {
    if (!report) return ['offer']
    const list: Beat[] = ['score']
    if (report.phantom.available) list.push('phantom')
    list.push('title')
    if (report.cards.length) list.push('cards')
    list.push('offer')
    return list
  }, [report])

  const [step, setStep] = useState(0)
  const [card, setCard] = useState(0)
  const beat = beats[step]

  useEffect(() => {
    if (beat === 'title') shake(0.8)
    else if (beat === 'score') shake(0.35)
  }, [beat, shake])

  const next = () => (step + 1 >= beats.length ? onDone() : setStep(step + 1))
  const avancable = beat !== 'offer' && beat !== 'cards'

  return (
    <motion.div
      className="cer"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      onClick={avancable ? next : undefined}
      role="dialog"
      aria-label="Saison"
    >
      <motion.div className="cer__stage" style={avancable ? style : undefined}>
        <AnimatePresence mode="wait">
          {beat === 'score' && report && (
            <motion.div key="score" className="cer__beat" {...slam(reduced)}>
              <p className="label cer__over">{report.season.name} — terminée</p>
              <div className="cer__big display">
                <CountUp to={report.hours} duration={1400} suffix=" h" />
              </div>
              <p className="cer__sub muted">
                <span className="num">{report.season.days}</span> jours ·{' '}
                <span className="num">{report.boss.ratio_killed * 100}</span> % du boss{' '}
                {report.boss.name}
              </p>
              <Burst count={24} spread={230} />
            </motion.div>
          )}

          {beat === 'phantom' && report && (
            <motion.div key="phantom" className="cer__beat" {...slam(reduced)}>
              <p className="label cer__over">Contre {report.phantom.reference}</p>
              <h2 className={`cer__delta display${report.phantom.ahead ? ' cer__delta--ahead' : ''}`}>
                {report.phantom.ahead ? '+' : '−'}
                {formatEcart(report.phantom.delta)}
              </h2>
              <p className="cer__sub muted">{report.phantom.line}</p>
            </motion.div>
          )}

          {beat === 'title' && report && (
            <motion.div key="title" className="cer__beat" {...slam(reduced)}>
              <Rays count={18} />
              <p className="label cer__over">Titre décerné</p>
              <h2 className="cer__title display">{report.title}</h2>

              {/* Le titre rate est annonce aussi franchement que l'autre : une
                  collection sans trous n'a aucune valeur (§12.3). */}
              <p className="cer__sub muted">
                {report.won
                  ? 'Le boss est tombé. La mise revient doublée.'
                  : 'Le boss tient encore. La mise est perdue.'}
                {report.stake > 0 && (
                  <>
                    {' '}
                    <span className="num">
                      {report.stake_delta > 0 ? '+' : ''}
                      {report.stake_delta}
                    </span>{' '}
                    éclats.
                  </>
                )}
              </p>
              {report.won && <Burst count={44} spread={340} />}
            </motion.div>
          )}

          {beat === 'cards' && report && (
            <motion.div key={`card-${card}`} className="cer__beat" {...soft(reduced)}>
              <LootReveal
                card={report.cards[card]}
                onDone={() => (card + 1 < report.cards.length ? setCard(card + 1) : next())}
              />
            </motion.div>
          )}

          {beat === 'offer' && (
            <motion.div key="offer" className="cer__beat cer__beat--offer" {...soft(reduced)}>
              <Opening offer={offer} onOpened={onDone} />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {avancable && (
        <p className="cer__hint muted">
          Toucher pour la suite · {step + 1}/{beats.length}
        </p>
      )}
    </motion.div>
  )
}

/** L'ouverture (§12.2) — le seul moment où l'interface a le droit d'être théâtrale.
 *
 * Théâtrale sur l'identité, sobre sur les choix. Le nom, l'emblème et la
 * baseline reçoivent la mise en scène ; les trois modificateurs et les fantômes
 * sont des boutons calmes, parce qu'on décide de son mois et qu'un choix
 * pressé par une animation n'est pas un choix.
 */
function Opening({ offer, onOpened }: { offer: SeasonOffer; onOpened: () => void }) {
  const [modifier, setModifier] = useState(offer.modifiers[0]?.key ?? '')
  const [phantom, setPhantom] = useState(
    offer.phantoms.find((p) => p.available)?.key ?? 'meilleure',
  )
  const [stake, setStake] = useState(Math.min(100, offer.shards))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const choisi = offer.modifiers.find((m) => m.key === modifier)

  async function open() {
    setBusy(true)
    setError('')
    try {
      await api.openSeason({ modifier, phantom, stake })
      onOpened()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ouverture impossible.')
      setBusy(false)
    }
  }

  return (
    <div className="open" style={{ ['--accent' as string]: offer.accent }}>
      <div className="open__hero">
        <Rays count={14} color={offer.accent} />
        <SeasonSigil seasonKey={offer.name} size={64} />
        <p className="label open__index">Saison {offer.index}</p>
        <h2 className="open__name display">{offer.name}</h2>
        <p className="open__baseline">« {offer.baseline} »</p>
      </div>

      <section className="open__block">
        <p className="label">Modificateur — un seul pour quatre semaines</p>
        <ul className="open__choices">
          {offer.modifiers.map((m) => (
            <li key={m.key}>
              <button
                className={`open__choice${modifier === m.key ? ' open__choice--on' : ''}`}
                onClick={() => setModifier(m.key)}
              >
                <span className="open__choice-head">
                  <span className="open__choice-name display">{m.name}</span>
                  {m.hard && <span className="open__hard">difficile</span>}
                </span>
                <span className="open__choice-effet muted">{m.effet}</span>
                <span className="open__choice-cost num">
                  Boss {m.boss_hp}
                  {m.stake_multiplier > 1 && ` · mise ×${m.stake_multiplier}`}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="open__block">
        <p className="label">Fantôme — contre quoi tu cours</p>
        <div className="open__row">
          {offer.phantoms.map((p) => (
            <button
              key={p.key}
              className={`open__pill${phantom === p.key ? ' open__pill--on' : ''}`}
              disabled={!p.available}
              onClick={() => setPhantom(p.key)}
              title={p.available ? `${p.hours} h` : 'Aucune saison passée'}
            >
              {p.label}
              {p.available && <span className="num"> · {p.hours} h</span>}
            </button>
          ))}
        </div>
      </section>

      <section className="open__block">
        <p className="label">
          Mise — <span className="num">{offer.shards}</span> éclats disponibles
        </p>
        <input
          className="open__stake"
          type="range"
          min={0}
          max={offer.shards}
          step={10}
          value={stake}
          onChange={(e) => setStake(Number(e.target.value))}
        />
        <p className="open__stake-read">
          <span className="num">{stake * (choisi?.stake_multiplier ?? 1)}</span> éclats engagés.
          Saison réussie, la mise revient doublée. Ratée, elle est perdue.
        </p>
      </section>

      {error && <p className="open__error">{error}</p>}

      <button className="cta" onClick={open} disabled={busy}>
        {busy ? 'Ouverture…' : `Ouvrir ${offer.name}`}
      </button>
    </div>
  )
}

function formatEcart(minutes: number): string {
  const total = Math.abs(minutes)
  const h = Math.floor(total / 60)
  const m = total % 60
  return h ? `${h}h${String(m).padStart(2, '0')}` : `${m} min`
}

function slam(reduced: boolean) {
  if (reduced) return { initial: false as const }
  return {
    initial: { scale: 2.4, opacity: 0, filter: 'blur(12px)' },
    animate: { scale: 1, opacity: 1, filter: 'blur(0px)' },
    exit: { scale: 0.85, opacity: 0, transition: { duration: 0.18 } },
    transition: { duration: 0.55, ease: [0.16, 1.2, 0.3, 1] as const },
  }
}

function soft(reduced: boolean) {
  if (reduced) return { initial: false as const }
  return {
    initial: { opacity: 0, y: 22 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -14, transition: { duration: 0.18 } },
    transition: { duration: 0.36, ease: [0.22, 1, 0.36, 1] as const },
  }
}
