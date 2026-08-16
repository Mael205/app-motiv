import { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { Burst, Rays, useReducedMotion } from '../juice'
import type { LootCardDrawn } from '../types'
import './LootReveal.css'

const KIND_LABELS: Record<string, string> = {
  theme: 'Thème',
  emblem: 'Emblème',
  frame: "Cadre d'avatar",
  title: 'Titre',
  finisher: 'Effet de fin de session',
}

/** Le tirage d'une carte (SPEC §12.6, §7 séquence 3).
 *
 * > Cartes de loot … avec raretés et **animation d'ouverture**.
 *
 * Toute la mise en scène tient dans un principe : **la rareté se devine avant
 * d'être lue**. La carte arrive dos face à l'écran, sa lueur et l'intensité de
 * ses rayons trahissent ce qu'elle vaut, et le retournement ne fait que
 * confirmer. Sans ce délai, l'animation ne serait qu'un décor posé sur une
 * information déjà donnée.
 *
 * Une légendaire secoue, éclate et brille ; une commune se retourne sobrement.
 * C'est la règle du skill `game-feel` : la juice se dose sur l'importance de
 * l'événement, sinon plus rien ne se distingue.
 *
 * **Un doublon n'est jamais un échec affiché comme tel.** Il annonce ses
 * Éclats, parce que le §12.6 veut qu'aucun tirage ne soit vide.
 */
export function LootReveal({
  card,
  onDone,
}: {
  card: LootCardDrawn
  onDone: () => void
}) {
  const reduced = useReducedMotion()
  const [flipped, setFlipped] = useState(reduced)
  const rare = card.rarity === 'epique' || card.rarity === 'legendaire'

  useEffect(() => {
    if (reduced) return
    // Le suspense est court : une seconde d'attente est du théâtre, trois sont
    // une punition pour quelqu'un qui vient de finir sa session.
    const t = setTimeout(() => setFlipped(true), rare ? 900 : 620)
    return () => clearTimeout(t)
  }, [reduced, rare])

  return (
    <div className="loot" style={{ ['--rarity' as string]: card.color }}>
      <p className="loot__reason label">{card.reason_label || 'Récompense'}</p>

      <div className="loot__stage">
        {flipped && rare && <Rays count={rare ? 18 : 12} color={card.color} />}

        <motion.div
          className={`loot__card loot__card--${card.rarity}${flipped ? ' loot__card--open' : ''}`}
          initial={reduced ? false : { scale: 0.4, y: 40, rotateY: 180 }}
          animate={{
            scale: 1,
            y: 0,
            rotateY: flipped ? 0 : 180,
          }}
          transition={{
            scale: { duration: 0.5, ease: [0.34, 1.56, 0.64, 1] },
            y: { duration: 0.5, ease: [0.34, 1.56, 0.64, 1] },
            rotateY: { duration: 0.55, ease: [0.22, 1, 0.36, 1] },
          }}
        >
          {/* Le dos. Visible tant que la carte n'est pas retournee. */}
          <div className="loot__face loot__back" aria-hidden>
            <span className="loot__sigil">◈</span>
          </div>

          <div className="loot__face loot__front">
            <span className="loot__rarity">{card.rarity_label}</span>
            <span className="loot__glyph" aria-hidden>
              {card.kind === 'emblem' ? card.payload : card.kind === 'theme' ? '◐' : '✦'}
            </span>
            <h3 className="loot__name display">{card.label}</h3>
            <p className="loot__kind muted">{KIND_LABELS[card.kind] ?? card.kind}</p>

            {card.duplicate && (
              <p className="loot__dup">
                Déjà obtenue · <span className="num">+{card.shards}</span> Éclats
              </p>
            )}
          </div>
        </motion.div>

        {/* La gerbe part au retournement, et seulement pour ce qui le merite. */}
        {flipped && rare && (
          <Burst
            color={card.color}
            count={card.rarity === 'legendaire' ? 46 : 28}
            spread={card.rarity === 'legendaire' ? 340 : 240}
          />
        )}
      </div>

      <button className="ghost loot__next" onClick={onDone}>
        Continuer
      </button>
    </div>
  )
}
