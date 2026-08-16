import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { api } from '../api'
import { MomentumEmber } from '../components/MomentumEmber'
import { SkillTree } from '../components/SkillTree'
import { LootReveal } from '../components/LootReveal'
import type { LootCardDrawn, ProgressionPanel } from '../types'
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
export function Character({ locked = false }: { locked?: boolean }) {
  const [panel, setPanel] = useState<ProgressionPanel | null>(null)
  const [error, setError] = useState('')
  const [queue, setQueue] = useState<LootCardDrawn[]>([])
  const [slot, setSlot] = useState<string>('theme')

  async function load() {
    try {
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

  if (locked) return <Showcase />
  if (error) return <p className="muted">{error}</p>
  if (!panel) return <p className="muted">Chargement…</p>

  const cards = panel.collection.slots[slot] ?? []

  return (
    <div className="char">
      <div className="char__col">
        <MomentumEmber momentum={panel.momentum} />

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
