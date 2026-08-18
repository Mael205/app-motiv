import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Burst, Rays, sfx, useReducedMotion, useTrauma } from '../juice'
import { LootReveal } from './LootReveal'
import { RankBadge } from './art/RankBadge'
import type { SessionResult } from '../types'
import './Ascension.css'

/** Combien de temps chaque temps se charge avant d'éclater.
 *
 * Réglé au même endroit que le reste de la graduation. La carte est à zéro : le
 * tirage porte déjà sa propre charge, et deux charges enchaînées feraient deux
 * secondes d'attente pour un seul événement.
 */
const CHARGES: Record<string, number> = {
  boss: 1000,
  phase: 900,
  level: 820,
  branch: 680,
  relic: 760,
  card: 0,
}

type Beat =
  | { kind: 'boss'; name: string; season: string; daysLeft: number }
  | { kind: 'phase'; name: string; previous: string; line: string; index: number; final: boolean }
  | { kind: 'level'; level: number }
  | { kind: 'branch'; label: string; title: string; emblem: string; color: string; hours: number }
  | { kind: 'relic'; label: string; lore: string; emblem: string }
  | { kind: 'card'; index: number }

/** La séquence 3 du §7 : passage de niveau, palier, relique, carte.
 *
 * > **Passage de niveau / rang** — plein écran, 1,5 s, emblème du nouveau rang,
 * > tirage de carte de loot si applicable.
 *
 * Le point de conception est l'**enchaînement**, pas chaque effet pris à part.
 * Une soirée peut produire quatre bonnes nouvelles d'un coup ; les afficher
 * ensemble les annulerait mutuellement, et les afficher en file d'attente
 * silencieuse ferait quinze secondes de spectacle à un moment où l'on veut
 * aller se coucher.
 *
 * Chaque temps est donc **court, distinct, et passable d'un clic n'importe où**.
 * L'ordre suit l'importance décroissante : le niveau, puis le palier de
 * branche, puis les reliques, puis les cartes.
 *
 * En mouvement réduit, la séquence ne disparaît pas — elle se joue sans
 * animation, comme le §7 l'exige. Perdre l'information serait pire que perdre
 * l'effet.
 */
export function Ascension({ result, onDone }: { result: SessionResult; onDone: () => void }) {
  const reduced = useReducedMotion()
  const { shake, style } = useTrauma()

  const beats = useMemo<Beat[]>(() => {
    const list: Beat[] = []
    // Le boss d'abord : c'est l'événement le plus rare de la saison, et il
    // ouvre la fin de saison en avance (§12.4). Le montrer après un palier de
    // branche l'aurait fait passer pour une conséquence de celui-ci.
    if (result.boss_killed) {
      list.push({
        kind: 'boss',
        name: result.boss_killed.name,
        season: result.boss_killed.season,
        daysLeft: result.boss_killed.days_left,
      })
    }
    // La phase de boss juste après sa mort — dans les faits jamais les deux le
    // même soir, le serveur ne rend pas l'une quand il rend l'autre. Elle passe
    // avant le niveau parce qu'elle raconte l'adversaire et non le joueur : le
    // niveau se comprend mieux quand on sait à qui on a affaire maintenant.
    if (result.boss_phase) {
      list.push({
        kind: 'phase',
        name: result.boss_phase.name,
        previous: result.boss_phase.previous_name,
        line: result.boss_phase.line,
        index: result.boss_phase.index,
        final: result.boss_phase.final,
      })
    }
    if (result.levelled_up) list.push({ kind: 'level', level: result.level_after })
    if (result.branch_tier) {
      list.push({
        kind: 'branch',
        label: result.branch_tier.label,
        title: result.branch_tier.title,
        emblem: result.branch_tier.emblem,
        color: result.branch_tier.color,
        hours: result.branch_tier.hours,
      })
    }
    for (const relic of result.relics ?? []) {
      list.push({ kind: 'relic', label: relic.label, lore: relic.lore, emblem: relic.emblem })
    }
    ;(result.cards ?? []).forEach((_, i) => list.push({ kind: 'card', index: i }))
    return list
  }, [result])

  const [step, setStep] = useState(0)
  const beat = beats[step]

  // Le temps de charge, avant la révélation. C'est ce qui manquait : un palier
  // arrivait déjà atteint, sans qu'on ait vu la montée. Une évolution se
  // regarde *pendant* qu'elle se fait — l'emblème pulse de plus en plus vite,
  // le grondement monte, et c'est seulement après que ça éclate.
  //
  // Gradué comme tout le reste : le boss charge une seconde, une relique un peu
  // moins, une carte pas du tout (elle a déjà la sienne).
  const charge = beat ? CHARGES[beat.kind] : 0
  const [chargeEnCours, setChargeEnCours] = useState(false)

  // La charge démarre au montage du temps ; la révélation attend qu'elle
  // finisse. Un clic pendant la charge la purge au lieu de passer au temps
  // suivant : on saute l'attente, jamais la récompense.
  useEffect(() => {
    if (!beat || reduced || !charge) {
      setChargeEnCours(false)
      return
    }
    setChargeEnCours(true)
    sfx.charge(charge / 1000)
    const t = setTimeout(() => setChargeEnCours(false), charge)
    return () => clearTimeout(t)
  }, [step, beat, reduced, charge])

  // La secousse part à la **révélation**, pas au montage : elle marque la fin
  // de la charge, ce qui est tout l'intérêt d'avoir une charge.
  useEffect(() => {
    if (!beat || chargeEnCours) return
    // Dosage sur l'importance (voir docs/direction-visuelle.md). La mort du
    // boss est le seul événement qui dépasse le passage de niveau : elle
    // n'arrive qu'une fois par saison, et parfois pas du tout.
    shake(
      beat.kind === 'boss'
        ? 1
        : beat.kind === 'level'
          ? 0.85
          : beat.kind === 'phase'
            ? 0.7
            : beat.kind === 'branch'
              ? 0.5
              : 0.3,
    )

    // Le son suit la même graduation, et **chaque temps a le sien**. Le palier
    // de branche et la relique partageaient celui de fin de session — un accord
    // qui descend, juste pour poser un travail, faux pour franchir un palier.
    // Ce qui monte se lit comme un gain, ce qui descend comme une clôture, et
    // l'oreille ne se trompe jamais là-dessus.
    //
    // Le temps « card » ne joue rien ici : le tirage a déjà son son de geste et
    // son son de rareté. Deux sons superposés pour un seul événement
    // s'entendent comme un bug, pas comme une emphase.
    if (beat.kind === 'boss') sfx.bossKill()
    else if (beat.kind === 'phase') sfx.bossPhase()
    else if (beat.kind === 'level') sfx.levelUp()
    else if (beat.kind === 'branch') sfx.branchTier()
    else if (beat.kind === 'relic') sfx.relic()
  }, [step, beat, shake, chargeEnCours])

  const next = () => {
    if (chargeEnCours) return setChargeEnCours(false)
    return step + 1 >= beats.length ? onDone() : setStep(step + 1)
  }

  if (!beat) return null

  return (
    <motion.div
      className="asc"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.22 }}
      onClick={beat.kind === 'card' ? undefined : next}
      role="dialog"
      aria-label="Récompense"
    >
      {/* L'eclair d'ouverture : 90 ms, une seule fois, sur le premier temps. */}
      {!reduced && step === 0 && <span className="asc__flash" aria-hidden />}

      {/* L'onde de choc part du centre à chaque temps fort. Elle ne remplace
          pas la secousse : la secousse dit la force, l'onde dit d'où elle
          vient. Les deux ensemble donnent un point d'impact. */}
      {!reduced && (beat.kind === 'boss' || beat.kind === 'phase' || beat.kind === 'level') && (
        <motion.span
          key={`onde-${step}`}
          className={`asc__onde${beat.kind === 'boss' ? ' asc__onde--boss' : ''}`}
          aria-hidden
          initial={{ scale: 0.15, opacity: 0.8 }}
          animate={{ scale: 3.4, opacity: 0 }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
        />
      )}

      <motion.div className="asc__stage" style={style}>
        <AnimatePresence mode="wait">
          {chargeEnCours && (
            <motion.div
              key={`charge-${step}`}
              className="asc__charge"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 1.4, transition: { duration: 0.12 } }}
              transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
              style={{ ['--charge' as string]: `${charge}ms` }}
            >
              <span className="asc__charge-halo" aria-hidden />
              <span className="asc__charge-glyphe" aria-hidden>
                {beat.kind === 'boss' || beat.kind === 'phase'
                  ? '☠'
                  : beat.kind === 'level'
                    ? '▲'
                    : beat.kind === 'branch'
                      ? '◆'
                      : '◈'}
              </span>
            </motion.div>
          )}

          {!chargeEnCours && beat.kind === 'boss' && (
            <motion.div key="boss" className="asc__beat asc__beat--boss" {...enterSlam(reduced)}>
              <Rays count={20} color="var(--rose)" />
              <p className="label asc__over asc__over--boss" style={cascade(reduced, 0)}>
                Boss abattu
              </p>
              <h2 className="asc__boss display" style={cascade(reduced, 1)}>
                {beat.name}
              </h2>
              <p className="asc__sub muted" style={cascade(reduced, 2)}>
                {beat.season} · il restait <span className="num">{beat.daysLeft}</span> jour
                {beat.daysLeft > 1 ? 's' : ''}. La saison se clôt en avance.
              </p>
              <Burst count={44} color="#DE5F7E" spread={380} />
            </motion.div>
          )}

          {!chargeEnCours && beat.kind === 'phase' && (
            <motion.div key="phase" className="asc__beat asc__beat--phase" {...enterSlam(reduced)}>
              <Rays count={14} color="var(--rose)" />
              {/* Le nom d'avant est barré et celui d'après le remplace : c'est
                  la transformation qu'on regarde, pas le nouvel état. Sans
                  l'ancien nom à côté, la phase 2 se lit comme un autre boss. */}
              <p className="label asc__over asc__over--boss" style={cascade(reduced, 0)}>
                Phase {beat.index}
                {beat.final ? ' · dernier quart' : ''}
              </p>
              <p className="asc__phase-avant" style={cascade(reduced, 1)}>
                <s>{beat.previous}</s>
              </p>
              <h2 className="asc__boss display" style={cascade(reduced, 2)}>
                {beat.name}
              </h2>
              <p className="asc__sub muted" style={cascade(reduced, 3)}>
                {beat.line}
              </p>
              <Burst count={26} color="#DE5F7E" spread={280} />
            </motion.div>
          )}

          {!chargeEnCours && beat.kind === 'level' && (
            <motion.div key="level" className="asc__beat" {...enterSlam(reduced)}>
              <Rays count={16} />
              <div className="asc__badge">
                <RankBadge rank={result.rank ?? 'F'} level={beat.level} size={132} />
              </div>
              <p className="label asc__over" style={cascade(reduced, 0)}>Niveau atteint</p>
              <h2 className="asc__big display" style={cascade(reduced, 1)}>{beat.level}</h2>
              <p className="asc__sub muted" style={cascade(reduced, 2)}>
                +<span className="num">{result.xp}</span> XP cette session
              </p>
              <Burst count={34} spread={330} />
            </motion.div>
          )}

          {!chargeEnCours && beat.kind === 'branch' && (
            <motion.div
              key="branch"
              className="asc__beat"
              style={{ ['--branch' as string]: beat.color }}
              {...enterSlam(reduced)}
            >
              <Rays count={12} color={beat.color} />
              <span className="asc__emblem" aria-hidden>
                {beat.emblem}
              </span>
              <p className="label asc__over" style={cascade(reduced, 0)}>{beat.label}</p>
              <h2 className="asc__title display" style={cascade(reduced, 1)}>{beat.title}</h2>
              <p className="asc__sub muted" style={cascade(reduced, 2)}>
                <span className="num">{beat.hours}</span> heures cumulées sur cette branche
              </p>
              <Burst count={26} color={beat.color} spread={240} />
            </motion.div>
          )}

          {!chargeEnCours && beat.kind === 'relic' && (
            <motion.div key={`relic-${step}`} className="asc__beat" {...enterSlam(reduced)}>
              <Rays count={14} />
              <span className="asc__emblem asc__emblem--relic" aria-hidden>
                {beat.emblem}
              </span>
              <p className="label asc__over" style={cascade(reduced, 0)}>Relique</p>
              <h2 className="asc__title display" style={cascade(reduced, 1)}>{beat.label}</h2>
              <p className="asc__lore" style={cascade(reduced, 2)}>{beat.lore}</p>
              <p className="asc__sub muted" style={cascade(reduced, 3)}>
                À équiper dans ta fiche de personnage.
              </p>
            </motion.div>
          )}

          {beat.kind === 'card' && (
            <motion.div key={`card-${beat.index}`} className="asc__beat" {...enterSoft(reduced)}>
              <LootReveal card={result.cards![beat.index]} onDone={next} />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {beat.kind !== 'card' && (
        <p className="asc__hint muted">
          {step + 1 < beats.length ? 'Toucher pour la suite' : 'Toucher pour fermer'}
          {beats.length > 1 && ` · ${step + 1}/${beats.length}`}
        </p>
      )}
    </motion.div>
  )
}

/** L'entrée « slam » : arrive de loin, dépasse, se pose. Réservée aux temps forts.
 *
 * **Sans flou, et c'est une correction.** La première version animait un
 * `filter: blur(14px)` sur un bloc plein écran : le navigateur refloutait toute
 * la scène à chaque image, ce qui se voyait comme un à-coup sur les deux
 * premières dixièmes de seconde — précisément là où la séquence doit être la
 * plus nette. `transform` et `opacity` seuls passent par le compositeur et ne
 * coûtent rien. L'échelle de départ descend de 2,6 à 1,9 pour la même raison :
 * un élément agrandi de deux fois et demie fait dessiner deux fois et demie
 * trop de pixels.
 */
function enterSlam(reduced: boolean) {
  if (reduced) return { initial: false as const }
  return {
    initial: { scale: 1.9, opacity: 0 },
    animate: { scale: 1, opacity: 1 },
    exit: { scale: 0.82, opacity: 0, transition: { duration: 0.18 } },
    transition: { duration: 0.46, ease: [0.16, 1.2, 0.3, 1] as const },
  }
}

/** La cascade des lignes de texte à l'intérieur d'un temps.
 *
 * Quarante millisecondes d'écart, quatre lignes au maximum : le total reste
 * sous les 300 ms que la règle fixe pour un stagger. L'ordre suit la lecture —
 * l'étiquette, le titre, le détail —, ce qui donne à l'œil un chemin au lieu
 * d'un bloc qui apparaît d'un coup.
 *
 * En `style` plutôt qu'en composant `motion` : ces lignes vivent déjà dans un
 * parent animé, et empiler deux moteurs d'animation sur un même nœud est le
 * meilleur moyen d'écraser un transform avec l'autre.
 */
function cascade(reduced: boolean, index: number): React.CSSProperties {
  if (reduced) return {}
  return {
    animation: `asc-ligne 0.42s cubic-bezier(0.22, 1, 0.36, 1) ${0.14 + index * 0.04}s both`,
  }
}

function enterSoft(reduced: boolean) {
  if (reduced) return { initial: false as const }
  return {
    initial: { opacity: 0, y: 24 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -16, transition: { duration: 0.18 } },
    transition: { duration: 0.34, ease: [0.22, 1, 0.36, 1] as const },
  }
}
