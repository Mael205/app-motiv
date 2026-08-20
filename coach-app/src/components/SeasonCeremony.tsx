import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { api } from '../api'
import { Burst, CountUp, Rays, sfx, useReducedMotion, useTrauma } from '../juice'
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
type Beat = 'score' | 'phantom' | 'title' | 'cards' | 'bilan' | 'offer'

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
    // Le §13.4 arrive après les récompenses, jamais avant : une question sur ce
    // qui a cassé, posée avant le titre gagné, ferait de la cérémonie un bilan
    // de fautes. Elle est le dernier temps, et c'est celui qu'on emporte.
    if (!report.comparaison.premiere) list.push('bilan')
    list.push('offer')
    return list
  }, [report])

  const [step, setStep] = useState(0)
  const [card, setCard] = useState(0)
  const beat = beats[step]

  // La montée avant les deux temps qui comptent. Une saison se termine une fois
  // par mois : lui donner une seconde et demie d'attente n'est pas une lenteur,
  // c'est la seule chose qui la distingue d'un écran de résultat.
  const charge = beat === 'score' ? 1400 : beat === 'title' ? 1100 : 0
  const [chargeEnCours, setChargeEnCours] = useState(false)

  useEffect(() => {
    if (!charge || reduced) {
      setChargeEnCours(false)
      return
    }
    setChargeEnCours(true)
    sfx.charge(charge / 1000)
    const t = setTimeout(() => setChargeEnCours(false), charge)
    return () => clearTimeout(t)
  }, [step, charge, reduced])

  useEffect(() => {
    if (chargeEnCours) return
    if (beat === 'title') {
      shake(0.8)
      // Le seul son long du produit, pour le seul moment qui arrive une fois
      // par mois. Il est posé sur le titre et non sur le score : c'est le
      // titre qui reste dans la collection.
      sfx.seasonEnd()
    } else if (beat === 'score') {
      shake(0.35)
      sfx.sessionEnd()
    }
  }, [beat, shake, chargeEnCours])

  const next = () => {
    // Un clic pendant la montée la purge : on saute l'attente, jamais le
    // résultat.
    if (chargeEnCours) return setChargeEnCours(false)
    return step + 1 >= beats.length ? onDone() : setStep(step + 1)
  }
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
          {chargeEnCours && (
            <motion.div
              key={`charge-${step}`}
              className="cer__charge"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 1.5, transition: { duration: 0.14 } }}
              transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
              style={{ ['--charge' as string]: `${charge}ms` }}
            >
              <span className="cer__charge-halo" aria-hidden />
              <span className="cer__charge-glyphe display" aria-hidden>
                {beat === 'score' ? '◇' : '❖'}
              </span>
            </motion.div>
          )}

          {!chargeEnCours && beat === 'score' && report && (
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

          {!chargeEnCours && beat === 'bilan' && report && (
            <motion.div key="bilan" className="cer__beat cer__beat--bilan" {...slam(reduced)}>
              <p className="label cer__over">Comparé à tes autres saisons</p>

              <ul className="cer__evolutions">
                {report.comparaison.evolutions.slice(0, 4).map((evolution) => (
                  <li key={evolution.mesure} className={`cer__evo cer__evo--${evolution.sens}`}>
                    {evolution.phrase}
                  </li>
                ))}
              </ul>

              {report.comparaison.causes.length > 0 && (
                <div className="cer__causes">
                  <span className="label">Ce que tes revues disaient</span>
                  <ul>
                    {report.comparaison.causes.map((cause) => (
                      <li key={cause}>{cause}</li>
                    ))}
                  </ul>
                </div>
              )}

              <p className="cer__question">{report.comparaison.question}</p>
            </motion.div>
          )}

          {!chargeEnCours && beat === 'phantom' && report && (
            <motion.div key="phantom" className="cer__beat" {...slam(reduced)}>
              <p className="label cer__over">Contre {report.phantom.reference}</p>
              <h2 className={`cer__delta display${report.phantom.ahead ? ' cer__delta--ahead' : ''}`}>
                {report.phantom.ahead ? '+' : '−'}
                {formatEcart(report.phantom.delta)}
              </h2>
              <p className="cer__sub muted">{report.phantom.line}</p>
            </motion.div>
          )}

          {!chargeEnCours && beat === 'title' && report && (
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

              {/* Ce que le palier 2 du §14 avait déjà pris en cours de route.
                  Le dire ici évite la seule lecture qui serait fausse : croire
                  que la clôture a résolu la mise entière. */}
              {report.stake_forfeited > 0 && (
                <p className="cer__sub muted">
                  <span className="num">{report.stake_forfeited}</span> éclats étaient déjà
                  partis en cours de saison.
                </p>
              )}
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
  // Le contrat (§16 de la liste du 17 août). Il part à ce que valent déjà les
  // engagements pris : une proposition qui reprend ce qu'on fait se signe sans
  // négocier, et c'est la lecture des termes qui compte, pas le réglage.
  const [contrat, setContrat] = useState(offer.contract.proposed)
  const [signe, setSigne] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const choisi = offer.modifiers.find((m) => m.key === modifier)

  async function open() {
    setBusy(true)
    setError('')
    try {
      await api.openSeason({ modifier, phantom, stake, contract: signe ? contrat : 0 })
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
        <SeasonSigil seasonKey={offer.key} size={64} />
        <p className="label open__index">Saison {offer.index}</p>
        <h2 className="open__name display">{offer.name}</h2>
        {/* D'où vient cette saison, avant même son nom de code. C'est la seule
            ligne qui relie deux saisons entre elles : sans elle, la voie basse
            ressemble à un tirage malchanceux plutôt qu'à la suite de ce qui
            vient de se passer. */}
        {offer.acte && (
          <p className={`open__voie open__voie--${offer.acte.voie}`}>
            {offer.acte.voie_nom} · {offer.acte.nom}
            <span className="open__voie-raison">{offer.acte.voie_ligne}</span>
          </p>
        )}
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

      {/* Le contrat. Il ne bloque pas l'ouverture — refuser d'ouvrir tant que
          personne n'a signé ferait du rituel un formulaire, et un formulaire se
          remplit sans le lire. Les termes sont donc affichés **avant** la case,
          et ils se recalculent quand le nombre bouge : signer sans avoir vu le
          total sur la saison, c'est régler un curseur. */}
      <section className="open__block open__block--contract">
        <p className="label">Contrat — ce que tu t'engages à tenir</p>
        <div className="open__row open__contract-row">
          <input
            className="open__contract-input"
            type="number"
            min={offer.contract.minimum}
            max={offer.contract.maximum}
            value={contrat}
            onChange={(e) => {
              setContrat(Number(e.target.value))
              setSigne(false)
            }}
          />
          <span className="muted">sessions par semaine</span>
        </div>

        <ul className="open__contract-terms">
          {termesPour(offer, contrat).map((ligne) => (
            <li key={ligne}>{ligne}</li>
          ))}
        </ul>

        <label className="open__sign">
          <input type="checkbox" checked={signe} onChange={(e) => setSigne(e.target.checked)} />
          <span>Je signe ces termes pour {offer.contract.weeks} semaines.</span>
        </label>
        {!signe && (
          <p className="section-hint">
            Sans signature, la saison s'ouvre quand même — et la clôture n'aura
            rien à relire.
          </p>
        )}
      </section>

      {error && <p className="open__error">{error}</p>}

      <button className="cta" onClick={open} disabled={busy}>
        {busy ? 'Ouverture…' : `Ouvrir ${offer.name}`}
      </button>
    </div>
  )
}

/** Les termes recalculés pour le nombre affiché.
 *
 * Le serveur en rend une version pour sa proposition d'origine ; dès que le
 * nombre bouge, la seule ligne qui change est le total, et la recalculer ici
 * évite un aller-retour par frappe au clavier. Les phrases, elles, viennent du
 * serveur — c'est lui qui écrit ce qu'on signe.
 */
function termesPour(offer: SeasonOffer, parSemaine: number): string[] {
  const total = Math.max(0, parSemaine) * offer.contract.weeks
  return offer.contract.terms.map((ligne) =>
    ligne
      .replace(/^\d+ sessions par semaine/, `${parSemaine} sessions par semaine`)
      .replace(/Soit \d+ sessions au total/, `Soit ${total} sessions au total`),
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
