import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { api } from '../api'
import { useInclinaison, useRevelation } from '../juice'
import { EnCharge, EnErreur } from '../components/EtatCharge'
import { MomentumEmber } from '../components/MomentumEmber'
import { PhantomRace } from '../components/PhantomRace'
import { Capacite } from '../components/Capacite'
import { SkillTree } from '../components/SkillTree'
import { HautsFaits } from '../components/HautsFaits'
import { Statistiques } from '../components/Statistiques'
import { Trace } from '../components/Trace'
import { LootReveal } from '../components/LootReveal'
import type { LootCardDrawn, Phantom, ProgressionPanel } from '../types'
import './Character.css'

const SLOT_LABELS: Record<string, string> = {
  theme: 'Thèmes',
  emblem: 'Emblèmes',
  frame: "Cadres d'avatar",
  title: 'Titres',
  finisher: 'Effets de fin de session',
}

/** La fiche de personnage : arbre, reliques, collection (SPEC §12).
 *
 * C'est l'écran qu'on ouvre quand on ne travaille pas — celui qui donne envie
 * de revenir, au sens du §0.10 : *une version fonctionnellement parfaite mais
 * sans identité ne sera pas utilisée*.
 *
 * Il est délibérément séparé de l'accueil. Le §11.1 veut un écran du soir qui
 * ne présente **qu'une décision** ; y empiler une collection de cartes et un
 * arbre à six branches détruirait exactement ce qu'il protège. Ici, à
 * l'inverse, on a le droit de flâner.
 *
 * Sauf après un jour raté. C'est la *vitrine fermée* du §14 : on ne consulte
 * pas ses trophées un soir où l'on n'a rien fait. Le serveur refuse en 423 —
 * le `locked` reçu ici ne sert qu'à ne pas demander pour rien, et la garde
 * réelle est côté API.
 */
export function Character({
  locked = false,
  phantom = null,
}: {
  locked?: boolean
  phantom?: Phantom | null
}) {
  const [panel, setPanel] = useState<ProgressionPanel | null>(null)
  const [error, setError] = useState('')
  const [queue, setQueue] = useState<LootCardDrawn[]>([])
  const [slot, setSlot] = useState<string>('theme')
  const [forging, setForging] = useState('')

  async function load() {
    try {
      // L'erreur se lève avant l'appel, pas après son succès : sans cette
      // ligne, un « Réessayer » qui aboutissait laissait l'ancien message
      // affiché — l'écran restait en panne alors que les données étaient là.
      setError('')
      const recu = await api.progression()
      setPanel(recu)
      // Les cartes de la semaine tombent a l'ouverture : elles se jouent tout
      // de suite plutot que de s'accumuler dans un coin ou personne ne clique.
      if (recu.pending_cards.length) setQueue(recu.pending_cards)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Chargement impossible.')
    }
  }

  useEffect(() => {
    if (!locked) load()
  }, [locked])

  /* Les reliques et les cartes de collection se comptent par dizaines : sans
     revelation au defilement, cent animations se jouent au montage dont
     quatre-vingt-dix hors champ. */
  const scene = useRevelation(
    { lever: '.relics > li, .collection > li, .panel' },
    Boolean(panel),
  )

  /* Les cartes de collection s'inclinent aussi : c'est la surface la plus
     proche d'un objet a manipuler de tout le produit. */
  useInclinaison(scene, '.slotcard__btn', `${slot}:${panel?.collection.slots[slot]?.length ?? 0}`)

  if (locked) return <Showcase />
  if (error) return <EnErreur message={error} onRetry={load} />
  if (!panel) return <EnCharge />

  const cards = panel.collection.slots[slot] ?? []

  return (
    <div className="char" ref={scene}>
      <div className="char__col">
        <MomentumEmber momentum={panel.momentum} />

        {/* La course sur vingt-huit jours : une information de saison, donc de
            fiche. L'accueil n'en garde que la phrase du soir. */}
        {phantom?.available && <PhantomRace phantom={phantom} />}

        <Trace compact />

        {/* Les compteurs qui ne baissent pas d'abord, les courbes ensuite : on
            lit ce qui est acquis avant ce qui varie. */}
        <Statistiques />

        <HautsFaits />

        {/* La capacité est posée **avant** l'arbre, et c'est délibéré : l'arbre
            convertit des heures en titres, donc il se lit comme une mesure de
            niveau alors qu'il mesure du temps. Les deux l'un sous l'autre
            rendent la différence visible sans qu'on ait à l'expliquer. */}
        <Capacite />

        <section className="panel">
          <SkillTree branches={panel.skills.branches} tiers={panel.skills.tiers} />
          <p className="char__shape muted">{describeShape(panel.skills.shape)}</p>
        </section>
      </div>

      <div className="char__col">
        {/* --- Reliques -------------------------------------------------- */}
        <section className="panel">
        <div className="char__head">
          <span className="label">Reliques</span>
          <span className="num char__count">
            {panel.relics.equipped_count} / {panel.relics.max}
          </span>
        </div>
        <p className="section-hint">
          Les seuls bonus du système, et ils se gagnent par un haut fait — jamais
          par un tirage. Trois équipées au maximum : le plafond existe pour que le
          choix se sente.
        </p>

        <ul className="relics">
          {panel.relics.relics.map((r) => (
            <li
              key={r.key}
              className={`relic${r.owned ? '' : ' relic--locked'}${r.equipped ? ' relic--on' : ''}`}
            >
              <button
                className="relic__btn"
                disabled={!r.owned}
                onClick={async () => {
                  try {
                    setPanel({ ...panel, relics: await api.toggleRelic(r.key) })
                  } catch (e) {
                    setError(e instanceof Error ? e.message : '')
                  }
                }}
              >
                <span className="relic__emblem" aria-hidden>
                  {r.owned ? r.emblem : '·'}
                </span>
                <span className="relic__text">
                  <span className="relic__label">{r.owned ? r.label : 'Relique scellée'}</span>
                  <span className="relic__lore muted">
                    {r.owned ? r.lore : `Se débloque avec le haut fait « ${r.achievement} ».`}
                  </span>
                </span>
                {r.equipped && <span className="relic__on">Équipée</span>}
              </button>
            </li>
          ))}
        </ul>
      </section>

      {/* --- Collection -------------------------------------------------- */}
      <section className="panel">
        <div className="char__head">
          <span className="label">Collection</span>
          <span className="num char__count">
            {panel.collection.owned} / {panel.collection.total} · {panel.collection.shards} éclats
          </span>
        </div>

        <div className="char__tabs">
          {Object.keys(SLOT_LABELS).map((k) => (
            <button
              key={k}
              className={`char__tab${slot === k ? ' char__tab--on' : ''}`}
              onClick={() => setSlot(k)}
            >
              {SLOT_LABELS[k]}
            </button>
          ))}
        </div>

        <ul className="collection">
          {cards.map((c) => (
            <li
              key={c.key}
              className={`slotcard slotcard--${c.rarity}${c.owned ? '' : ' slotcard--locked'}${
                c.equipped ? ' slotcard--on' : ''
              }`}
              style={{ ['--rarity' as string]: c.color }}
            >
              <button
                className="slotcard__btn"
                disabled={!c.owned}
                onClick={async () => {
                  await api.equipCard(c.key)
                  load()
                }}
              >
                <span className="slotcard__glyph" aria-hidden>
                  {c.owned ? (c.kind === 'emblem' ? c.payload : '◈') : '?'}
                </span>
                <span className="slotcard__name">{c.owned ? c.label : '—'}</span>
                <span className="slotcard__rarity">{c.rarity_label}</span>
                {c.copies > 1 && <span className="slotcard__copies num">×{c.copies}</span>}
              </button>

              {/* Le retrait explicite. La bascule du serveur retire déjà la
                  carte au second clic, mais elle le faisait sans le dire : le
                  seul retour visuel était l'accent du site qui changeait, ce
                  qui se lit comme un changement de saison et non comme le
                  résultat d'un clic. Le bouton n'apparaît que sur la carte
                  équipée — il marque donc aussi l'emplacement occupé. */}
              {c.equipped && (
                <button
                  className="slotcard__unequip"
                  onClick={async () => {
                    await api.equipCard(c.key)
                    load()
                  }}
                >
                  Retirer
                </button>
              )}

              {/* La Forge : le seul endroit du produit où des Éclats sortent.
                  Le bouton n'apparaît que sur une carte qu'on n'a pas, et reste
                  éteint faute d'Éclats — un prix affiché sans être atteignable
                  vaut mieux qu'un bouton qui refuse après coup. */}
              {panel.collection.forge_open && !c.owned && c.forge_price !== undefined && (
                <button
                  className="slotcard__forge"
                  disabled={panel.collection.shards < c.forge_price || forging === c.key}
                  onClick={async () => {
                    setForging(c.key)
                    try {
                      const carte = await api.forgeCard(c.key)
                      setQueue([carte])
                      await load()
                    } finally {
                      setForging('')
                    }
                  }}
                >
                  Forger · <span className="num">{c.forge_price}</span>
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>

      </div>

      <AnimatePresence>
        {queue.length > 0 && (
          <motion.div
            className="char__reveal"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <LootReveal
              card={queue[0]}
              onDone={() => {
                const reste = queue.slice(1)
                setQueue(reste)
                if (!reste.length) load()
              }}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/** La vitrine fermée (§14, palier 1).
 *
 * Elle dit ce qui est fermé, jusqu'à quand, et rien d'autre. Pas d'aperçu
 * grisé de la collection derrière : montrer ce qu'on ne peut pas ouvrir est
 * une frustration entretenue, et le §14 ne veut pas d'un système qui tente.
 * Rien n'est perdu — c'est écrit, parce que c'est la question qu'on se pose.
 */
function Showcase() {
  return (
    <div className="char char--locked">
      <section className="panel char__locked">
        <span className="label">Vitrine fermée</span>
        <p className="char__locked-text">
          L'arbre, les reliques et la collection rouvrent à la prochaine session. Dix minutes
          suffisent.
        </p>
        <p className="char__locked-text muted">
          Rien n'a bougé derrière : les heures, les hauts faits et les cartes sont acquis.
        </p>
      </section>

      {/* La trace reste ouverte, et c'est ici qu'elle sert. La vitrine ferme
          les *récompenses* — on ne consulte pas ses trophées un soir où l'on
          n'a rien fait. La trace n'est pas une récompense : c'est le relevé du
          travail déjà accompli, et le fermer reviendrait à retirer des faits à
          quelqu'un en guise de sanction. */}
      <Trace />
    </div>
  )
}

/** La forme de l'arbre en une phrase (§12.9). Constat, jamais reproche. */
function describeShape(shape: ProgressionPanel['skills']['shape']): string {
  if (!shape.total_minutes) return "Aucune heure enregistrée. L'arbre pousse à partir de la première session."

  const heures = Math.round(shape.total_minutes / 60)
  const concentre = shape.concentration >= 0.7
  const arret = shape.a_l_arret.length

  return (
    `${heures} h réparties sur ${shape.branches_actives} branche${shape.branches_actives > 1 ? 's' : ''}. ` +
    (concentre
      ? "L'essentiel est au même endroit."
      : 'Le travail est réparti.') +
    (arret ? ` ${arret} branche${arret > 1 ? 's' : ''} à l'arrêt.` : '')
  )
}
