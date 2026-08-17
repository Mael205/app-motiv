import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Burst, Rays, sfx, useReducedMotion, useTrauma } from '../juice'
import { LootReveal } from './LootReveal'
import { RankBadge } from './art/RankBadge'
import type { SessionResult } from '../types'
import './Ascension.css'

type Beat =
  | { kind: 'boss'; name: string; season: string; daysLeft: number }
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

  // La secousse part au montage de chaque temps, calibrée sur son importance —
  // un palier de branche n'est pas un passage de niveau.
  useEffect(() => {
    if (!beat) return
    // Dosage sur l'importance (voir docs/direction-visuelle.md). La mort du
    // boss est le seul événement qui dépasse le passage de niveau : elle
    // n'arrive qu'une fois par saison, et parfois pas du tout.
    shake(
      beat.kind === 'boss'
        ? 1
        : beat.kind === 'level'
          ? 0.85
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
    else if (beat.kind === 'level') sfx.levelUp()
    else if (beat.kind === 'branch') sfx.branchTier()
    else if (beat.kind === 'relic') sfx.relic()
  }, [step, beat, shake])

  const next = () => (step + 1 >= beats.length ? onDone() : setStep(step + 1))

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
      {!reduced && (beat.kind === 'boss' || beat.kind === 'level') && (
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
          {beat.kind === 'boss' && (
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
              <Burst count={54} color="#DE5F7E" spread={380} />
              <Burst count={30} spread={260} />
            </motion.div>
          )}

          {beat.kind === 'level' && (
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
              <Burst count={40} spread={330} />
            </motion.div>
          )}

          {beat.kind === 'branch' && (
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

          {beat.kind === 'relic' && (
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

/** L'entrée « slam » : arrive de loin, dépasse, se pose. Réservée aux temps forts. */
function enterSlam(reduced: boolean) {
  if (reduced) return { initial: false as const }
  return {
    initial: { scale: 2.6, opacity: 0, filter: 'blur(14px)' },
    animate: { scale: 1, opacity: 1, filter: 'blur(0px)' },
    exit: { scale: 0.82, opacity: 0, transition: { duration: 0.18 } },
    transition: { duration: 0.52, ease: [0.16, 1.2, 0.3, 1] as const },
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
