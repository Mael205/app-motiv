import { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { Burst, Rays, sfx, useReducedMotion, useTrauma } from '../juice'
import type { LootCardDrawn } from '../types'
import './LootReveal.css'

const KIND_LABELS: Record<string, string> = {
  theme: 'Thème',
  emblem: 'Emblème',
  frame: "Cadre d'avatar",
  title: 'Titre',
  finisher: 'Effet de fin de session',
}

/** Ce qui change d'une rareté à l'autre — et c'est presque tout.
 *
 * Le tirage donnait déjà des lueurs graduées, mais **la même chorégraphie pour
 * les quatre** : même attente, même arrivée, même retournement. Or la mise en
 * scène est le seul endroit où la rareté peut se faire sentir avant d'être lue,
 * et une commune qui s'ouvre comme une légendaire dévalue la légendaire.
 *
 * Quatre gestes distincts, gradués par ce que la carte vaut :
 *
 * - **Commune** : elle est simplement là. Pas d'attente, pas de gerbe, pas de
 *   rayons. Elle glisse et se retourne en un demi-temps. C'est le tirage le
 *   plus fréquent : lui donner une cérémonie rendrait la cérémonie ordinaire.
 * - **Rare** : une arrivée avec un léger dépassement, et un anneau qui s'ouvre
 *   au retournement. Un accent, pas un événement.
 * - **Épique** : le suspense s'installe — la carte *tremble* avant de céder.
 *   Ce frémissement est le cœur de la séquence : il annonce qu'il se passe
 *   quelque chose sans dire quoi, ce qui est exactement ce qu'on veut d'un
 *   suspense.
 * - **Légendaire** : la charge monte, l'écran se serre, la carte se retourne
 *   dans un éclat, l'écran encaisse une secousse, et la carte continue de
 *   respirer ensuite. Le seul tirage à toucher au trauma.
 *
 * `duree` est le temps de suspense. Il monte avec la rareté sans jamais
 * dépasser une seconde : une seconde d'attente est du théâtre, trois sont une
 * punition pour quelqu'un qui vient de finir sa session.
 */
type Mise = {
  suspense: number
  entree: { raideur: number; amorti: number; depart: number; monte: number }
  rayons: number
  gerbe: number
  ecart: number
  trauma: number
  charge: boolean
  frisson: boolean
}

const MISES: Record<string, Mise> = {
  commun: {
    suspense: 380,
    entree: { raideur: 520, amorti: 30, depart: 0.86, monte: 16 },
    rayons: 0,
    gerbe: 0,
    ecart: 0,
    trauma: 0,
    charge: false,
    frisson: false,
  },
  rare: {
    suspense: 620,
    entree: { raideur: 380, amorti: 18, depart: 0.68, monte: 30 },
    rayons: 10,
    gerbe: 16,
    ecart: 170,
    trauma: 0,
    charge: false,
    frisson: false,
  },
  epique: {
    suspense: 900,
    entree: { raideur: 300, amorti: 15, depart: 0.5, monte: 44 },
    rayons: 18,
    gerbe: 30,
    ecart: 250,
    trauma: 0.18,
    charge: false,
    frisson: true,
  },
  legendaire: {
    suspense: 1150,
    entree: { raideur: 220, amorti: 13, depart: 0.34, monte: 62 },
    rayons: 26,
    gerbe: 48,
    ecart: 360,
    trauma: 0.42,
    charge: true,
    frisson: true,
  },
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
  const { style: secousse, shake } = useTrauma()
  const mise = MISES[card.rarity] ?? MISES.commun

  useEffect(() => {
    if (reduced) return
    // Le grondement de charge accompagne l'attente au lieu de la précéder :
    // c'est lui qui rend l'attente lisible comme du suspense et non comme une
    // lenteur.
    if (mise.charge) sfx.cardCharge(mise.suspense / 1000)

    const t = setTimeout(() => {
      setFlipped(true)
      sfx.cardFlip()
      sfx.cardReveal(card.rarity)
      if (mise.trauma) shake(mise.trauma)
    }, mise.suspense)
    return () => clearTimeout(t)
  }, [reduced, mise, card.rarity, shake])

  // En mouvement réduit, la carte est déjà ouverte au montage : le son reste,
  // parce que couper le son n'est pas ce que `prefers-reduced-motion` demande.
  useEffect(() => {
    if (reduced) sfx.cardReveal(card.rarity)
  }, [reduced, card.rarity])

  return (
    <div
      className={`loot loot--${card.rarity}`}
      style={{ ['--rarity' as string]: card.color, ...secousse }}
    >
      <p className="loot__reason label">{card.reason_label || 'Récompense'}</p>

      <div className="loot__stage">
        {flipped && mise.rayons > 0 && <Rays count={mise.rayons} color={card.color} />}

        {/* L'anneau ne part qu'au retournement, et seulement au-dessus du
            commun : il matérialise l'instant précis où la carte cède. */}
        {flipped && mise.ecart > 0 && (
          <motion.span
            className="loot__ring"
            aria-hidden
            initial={{ scale: 0.2, opacity: 0.85 }}
            animate={{ scale: mise.ecart / 130, opacity: 0 }}
            transition={{ duration: 0.85, ease: [0.16, 1, 0.3, 1] }}
          />
        )}

        {/* Le frisson vit sur cette enveloppe et non sur la carte.
            La carte a déjà un `transform` piloté par le moteur d'animation
            (rotateY, scale, y) : une seconde animation dessus l'écraserait, et
            la contourner par une marge animée ferait recalculer la mise en page
            onze fois par seconde. Une enveloppe a son propre transform, donc les
            deux mouvements cohabitent sur le compositeur. */}
        <div
          className={`loot__shell${!flipped && mise.frisson ? ' loot__shell--frisson' : ''}${
            card.rarity === 'legendaire' ? ' loot__shell--fort' : ''
          }`}
        >
        <motion.div
          className={`loot__card loot__card--${card.rarity}${flipped ? ' loot__card--open' : ''}`}
          initial={reduced ? false : { scale: mise.entree.depart, y: mise.entree.monte, rotateY: 180 }}
          animate={{ scale: 1, y: 0, rotateY: flipped ? 0 : 180 }}
          transition={{
            scale: { type: 'spring', stiffness: mise.entree.raideur, damping: mise.entree.amorti },
            y: { type: 'spring', stiffness: mise.entree.raideur, damping: mise.entree.amorti },
            // Le retournement est plus lent quand la carte est lourde : une
            // légendaire qui pivoterait aussi vite qu'une commune se lirait
            // comme une commune.
            rotateY: { duration: 0.36 + mise.suspense / 4200, ease: [0.22, 1, 0.36, 1] },
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
        </div>

        {/* La gerbe part au retournement, et seulement pour ce qui le merite. */}
        {flipped && mise.gerbe > 0 && (
          <Burst color={card.color} count={mise.gerbe} spread={mise.ecart} />
        )}
      </div>

      <button className="ghost loot__next" onClick={onDone}>
        Continuer
      </button>
    </div>
  )
}
