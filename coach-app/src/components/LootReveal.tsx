import { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { Burst, Rays, sfx, useHitStop, useReducedMotion, useTrauma } from '../juice'
import type { LootCardDrawn } from '../types'
import './LootReveal.css'

const KIND_LABELS: Record<string, string> = {
  theme: 'Thème',
  emblem: 'Emblème',
  frame: "Cadre d'avatar",
  title: 'Titre',
  finisher: 'Effet de fin de session',
}

/** Ce qui change d'une rareté à l'autre — et c'est d'abord **le geste**.
 *
 * Les quatre raretés partageaient un seul mouvement : le retournement. Elles
 * différaient par l'attente, la lueur, les rayons, la gerbe — tout sauf ce que
 * l'œil lit en premier, qui est la façon dont la carte s'ouvre. Une commune qui
 * s'ouvre comme une légendaire dévalue la légendaire, et quatre variations
 * d'intensité sur un même geste ne font pas quatre événements.
 *
 * Chaque rareté a donc sa **mécanique d'ouverture**, et elles ne se ressemblent
 * pas :
 *
 * - **Commune — elle se pose.** Aucune ouverture : la carte arrive déjà face
 *   visible, tombe, rebondit une fois. C'est le tirage le plus fréquent ; lui
 *   donner une cérémonie rendrait la cérémonie ordinaire.
 * - **Rare — elle se retourne.** Le flip devient la signature du rare au lieu
 *   d'être le geste universel. Un anneau marque l'instant où elle cède.
 * - **Épique — elle se fend.** Le dos se sépare en deux volets qui s'écartent
 *   et pivotent, la face monte dessous. C'est un dos qu'on ouvre, pas une carte
 *   qu'on tourne : le geste dit qu'il y avait quelque chose enfermé.
 * - **Légendaire — elle se brise.** Le dos éclate en cinq morceaux qui partent
 *   en tournant, la face émerge d'un flou dans un flash, l'écran encaisse une
 *   secousse et un arrêt sur image. Rien d'autre dans le produit ne casse.
 *
 * `suspense` est le temps d'attente avant l'ouverture. Il monte avec la rareté
 * sans jamais dépasser une seconde et demie : une seconde d'attente est du
 * théâtre, trois sont une punition pour quelqu'un qui vient de finir sa session.
 */
type Geste = 'posee' | 'retournee' | 'fendue' | 'brisee'

type Mise = {
  geste: Geste
  suspense: number
  entree: { raideur: number; amorti: number; depart: number; monte: number }
  rayons: number
  gerbe: number
  ecart: number
  trauma: number
  arret: number
  charge: boolean
  frisson: boolean
}

const MISES: Record<string, Mise> = {
  commun: {
    geste: 'posee',
    // Le seul « suspense » qui n'en est pas un : c'est le temps que met la
    // carte à toucher le fond. Le son part au contact, pas après.
    suspense: 170,
    entree: { raideur: 520, amorti: 30, depart: 0.86, monte: 16 },
    rayons: 0,
    gerbe: 0,
    ecart: 0,
    trauma: 0,
    arret: 0,
    charge: false,
    frisson: false,
  },
  rare: {
    geste: 'retournee',
    suspense: 620,
    entree: { raideur: 380, amorti: 18, depart: 0.68, monte: 30 },
    rayons: 10,
    gerbe: 16,
    ecart: 170,
    trauma: 0,
    arret: 0,
    charge: false,
    frisson: false,
  },
  epique: {
    geste: 'fendue',
    suspense: 900,
    entree: { raideur: 300, amorti: 15, depart: 0.5, monte: 44 },
    rayons: 18,
    gerbe: 30,
    ecart: 250,
    trauma: 0.18,
    arret: 70,
    charge: false,
    frisson: true,
  },
  legendaire: {
    geste: 'brisee',
    suspense: 1150,
    entree: { raideur: 220, amorti: 13, depart: 0.34, monte: 62 },
    rayons: 26,
    gerbe: 48,
    ecart: 360,
    trauma: 0.42,
    arret: 110,
    charge: true,
    frisson: true,
  },
}

/** Les cinq éclats d'une légendaire.
 *
 * Découpés à la main plutôt qu'au hasard : des morceaux tirés aléatoirement
 * donnent des échardes molles et symétriques, alors qu'une vraie casse fait des
 * pièces inégales. Chacun part dans sa direction avec sa rotation — deux
 * éclats qui partiraient de la même façon se liraient comme un fondu.
 */
const ECLATS = [
  { clip: 'polygon(0 0, 54% 0, 38% 46%, 0 62%)', x: -180, y: -120, rot: -38 },
  { clip: 'polygon(54% 0, 100% 0, 100% 34%, 38% 46%)', x: 190, y: -96, rot: 30 },
  { clip: 'polygon(100% 34%, 100% 100%, 62% 100%, 38% 46%)', x: 210, y: 140, rot: 44 },
  { clip: 'polygon(62% 100%, 0 100%, 0 62%, 38% 46%)', x: -150, y: 175, rot: -26 },
  { clip: 'polygon(0 62%, 38% 46%, 0 100%)', x: -240, y: 40, rot: -62 },
]

/** Le tirage d'une carte (SPEC §12.6, §7 séquence 3).
 *
 * > Cartes de loot … avec raretés et **animation d'ouverture**.
 *
 * Toute la mise en scène tient dans un principe : **la rareté se devine avant
 * d'être lue**. La carte arrive dos face à l'écran, sa lueur et l'intensité de
 * ses rayons trahissent ce qu'elle vaut, et l'ouverture ne fait que confirmer.
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
  const [ouverte, setOuverte] = useState(reduced)
  const { style: secousse, shake } = useTrauma()
  const [fige, figer] = useHitStop()
  const mise = MISES[card.rarity] ?? MISES.commun
  const posee = mise.geste === 'posee'

  useEffect(() => {
    if (reduced) return
    // Le grondement de charge accompagne l'attente au lieu de la précéder :
    // c'est lui qui rend l'attente lisible comme du suspense et non comme une
    // lenteur.
    if (mise.charge) sfx.cardCharge(mise.suspense / 1000)

    const t = setTimeout(() => {
      setOuverte(true)
      ouverture(mise.geste)
      sfx.cardReveal(card.rarity)
      if (mise.trauma) shake(mise.trauma)
      // L'arrêt sur image ne gèle que le visuel, jamais l'entrée : un clic
      // pendant les 110 ms passe normalement.
      if (mise.arret) figer(mise.arret)
    }, mise.suspense)
    return () => clearTimeout(t)
  }, [reduced, mise, card.rarity, shake, figer])

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
        {ouverte && mise.rayons > 0 && <Rays count={mise.rayons} color={card.color} />}

        {/* Le flash d'ouverture d'une légendaire : 120 ms, une seule fois. Il
            couvre l'instant où le dos disparaît, ce qui évite de voir la face
            « apparaître » — on voit une casse, pas une substitution. */}
        {ouverte && mise.geste === 'brisee' && !reduced && (
          <motion.span
            className="loot__flash"
            aria-hidden
            initial={{ opacity: 0.9 }}
            animate={{ opacity: 0 }}
            transition={{ duration: 0.32, ease: 'linear' }}
          />
        )}

        {ouverte && mise.ecart > 0 && (
          <motion.span
            className="loot__ring"
            aria-hidden
            initial={{ scale: 0.2, opacity: 0.85 }}
            animate={{ scale: mise.ecart / 130, opacity: 0 }}
            transition={{ duration: 0.85, ease: [0.16, 1, 0.3, 1] }}
          />
        )}

        {/* Le frisson vit sur cette enveloppe et non sur la carte.
            La carte a déjà un `transform` piloté par le moteur d'animation :
            une seconde animation dessus l'écraserait, et la contourner par une
            marge animée ferait recalculer la mise en page onze fois par
            seconde. Une enveloppe a son propre transform, donc les deux
            mouvements cohabitent sur le compositeur. */}
        <div
          className={`loot__shell${!ouverte && mise.frisson ? ' loot__shell--frisson' : ''}${
            card.rarity === 'legendaire' ? ' loot__shell--fort' : ''
          }`}
        >
          <motion.div
            className={`loot__card loot__card--${card.rarity}${ouverte ? ' loot__card--open' : ''}`}
            initial={
              reduced
                ? false
                : {
                    scale: mise.entree.depart,
                    y: mise.entree.monte,
                    // Seule la rare part retournée : les autres n'ont pas de
                    // rotation du tout, leur dos est un couvercle posé dessus.
                    rotateY: mise.geste === 'retournee' ? 180 : 0,
                  }
            }
            animate={{
              // L'arrêt sur image se voit ici : la carte reste une fraction de
              // seconde plus grande que sa taille finale, puis se pose. C'est
              // ce décalage qui donne du poids à l'ouverture.
              scale: fige ? 1.06 : 1,
              y: 0,
              rotateY: mise.geste === 'retournee' && !ouverte ? 180 : 0,
            }}
            transition={{
              scale: { type: 'spring', stiffness: fige ? 900 : mise.entree.raideur, damping: fige ? 40 : mise.entree.amorti },
              y: { type: 'spring', stiffness: mise.entree.raideur, damping: mise.entree.amorti },
              // Le retournement est plus lent quand la carte est lourde : une
              // rare qui pivoterait aussi vite qu'une commune se lirait comme
              // une commune.
              rotateY: { duration: 0.36 + mise.suspense / 4200, ease: [0.22, 1, 0.36, 1] },
            }}
          >
            {/* Le dos en 3D, pour la rare seule : c'est la seule qui tourne. */}
            {mise.geste === 'retournee' && (
              <div className="loot__face loot__back" aria-hidden>
                <span className="loot__sigil">◈</span>
              </div>
            )}

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

            {/* Le couvercle des gestes qui n'ont pas de rotation. Il est
                au-dessus de la face, et c'est **lui** qui s'ouvre. */}
            {!posee && mise.geste !== 'retournee' && (
              <div className="loot__cover" aria-hidden>
                {mise.geste === 'fendue' &&
                  [-1, 1].map((sens) => (
                    <motion.span
                      key={sens}
                      className={`loot__volet loot__volet--${sens < 0 ? 'g' : 'd'}`}
                      initial={{ x: 0, rotateY: 0, opacity: 1 }}
                      animate={
                        ouverte
                          ? { x: sens * 150, rotateY: sens * 62, opacity: 0 }
                          : { x: 0, rotateY: 0, opacity: 1 }
                      }
                      transition={{ duration: 0.5, ease: [0.3, 0.9, 0.2, 1] }}
                    >
                      {sens < 0 && <span className="loot__sigil">◈</span>}
                    </motion.span>
                  ))}

                {mise.geste === 'brisee' &&
                  ECLATS.map((eclat, i) => (
                    <motion.span
                      key={i}
                      className="loot__eclat"
                      style={{ clipPath: eclat.clip }}
                      initial={{ x: 0, y: 0, rotate: 0, opacity: 1 }}
                      animate={
                        ouverte
                          ? { x: eclat.x, y: eclat.y, rotate: eclat.rot, opacity: 0 }
                          : { x: 0, y: 0, rotate: 0, opacity: 1 }
                      }
                      transition={{
                        duration: 0.72,
                        delay: ouverte ? i * 0.018 : 0,
                        ease: [0.15, 0.85, 0.25, 1],
                      }}
                    >
                      {i === 0 && <span className="loot__sigil">◈</span>}
                    </motion.span>
                  ))}
              </div>
            )}
          </motion.div>
        </div>

        {/* La gerbe part à l'ouverture, et seulement pour ce qui le mérite. */}
        {ouverte && mise.gerbe > 0 && (
          <Burst color={card.color} count={mise.gerbe} spread={mise.ecart} />
        )}
      </div>

      <button className="ghost loot__next" onClick={onDone}>
        Continuer
      </button>
    </div>
  )
}

/** Le son du geste, distinct du son de rareté qui le suit.
 *
 * Deux couches, comme à l'image : ce que fait la carte, puis ce qu'elle vaut.
 * Les confondre en un seul son reviendrait à refaire ce qu'on vient de défaire.
 */
function ouverture(geste: Geste) {
  if (geste === 'posee') return sfx.cardSlide()
  if (geste === 'retournee') return sfx.cardFlip()
  if (geste === 'fendue') return sfx.cardSplit()
  return sfx.cardShatter()
}
