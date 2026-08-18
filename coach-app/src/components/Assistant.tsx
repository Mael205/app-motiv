import { useEffect, useRef, useState } from 'react'
import { motion } from 'motion/react'
import { api } from '../api'
import { useReducedMotion } from '../juice'
import type { ActionProposee, FilAssistant } from '../types'
import './Assistant.css'

/** L'écran de conversation avec l'assistant (§5 étendu).
 *
 * Le seul endroit du produit où l'on discute. Partout ailleurs, l'app décide et
 * l'on agit (§0.9, §11.1) ; ici on demande, en français, et l'assistant répond
 * par des **actions proposées** — chacune avec son avant/après et son bouton.
 *
 * **Il n'a pas d'onglet, et c'est délibéré.** La barre en compte quatre et
 * n'en veut pas cinq : les onglets sont les endroits où l'on va, l'assistant
 * est quelque chose qu'on appelle. Un cinquième onglet en aurait fait une
 * destination — donc un endroit où traîner un soir de fatigue, c'est-à-dire
 * exactement ce que le §11.1 cherche à éviter.
 *
 * **Une carte, un bouton, une écriture.** Pas de « tout appliquer » : cinq
 * écritures derrière un seul bouton se cliquent sans lire les cinq, et
 * l'aperçu ne servirait plus à rien.
 */
export function Assistant({ onClose, onApplied }: { onClose: () => void; onApplied: () => void }) {
  const reduced = useReducedMotion()
  const [fil, setFil] = useState<FilAssistant | null>(null)
  const [texte, setTexte] = useState('')
  const [busy, setBusy] = useState(false)
  const [erreur, setErreur] = useState('')
  const bas = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.assistant().then(setFil).catch(() => setFil(null))
  }, [])

  useEffect(() => {
    bas.current?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth' })
  }, [fil, reduced])

  async function envoyer() {
    const demande = texte.trim()
    if (!demande || busy) return
    setBusy(true)
    setErreur('')
    setTexte('')
    try {
      setFil(await api.ask(demande))
    } catch (error) {
      setErreur(error instanceof Error ? error.message : 'Envoi impossible.')
      // La demande revient dans le champ : la retaper serait la punition d'une
      // panne dont on n'est pas responsable.
      setTexte(demande)
      setFil(await api.assistant().catch(() => fil))
    } finally {
      setBusy(false)
    }
  }

  async function agir(action: ActionProposee, appliquer: boolean) {
    setErreur('')
    try {
      setFil(appliquer ? await api.applyAction(action.id) : await api.dismissAction(action.id))
      if (appliquer) onApplied()
    } catch (error) {
      setErreur(error instanceof Error ? error.message : 'Action impossible.')
    }
  }

  return (
    <motion.div
      className="assistant"
      initial={reduced ? false : { opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
    >
      <header className="assistant__head">
        <div className="stack">
          <span className="label">L'assistant</span>
          <span className="assistant__sous muted">
            Il propose, tu appliques. Rien ne s'écrit tant que tu n'as pas cliqué.
          </span>
        </div>
        <div className="row">
          <button
            className="ghost"
            onClick={async () => setFil(await api.newThread())}
            title="Ferme ce fil et en ouvre un neuf"
          >
            Nouveau fil
          </button>
          <button className="ghost" onClick={onClose}>
            Fermer
          </button>
        </div>
      </header>

      <div className="assistant__fil">
        {fil?.turns.length === 0 && <Amorces onPick={setTexte} />}

        {fil?.turns.map((tour) => (
          <article key={tour.id} className={`tour tour--${tour.role}`}>
            {tour.text && <p className="tour__texte">{tour.text}</p>}

            {tour.actions.length > 0 && (
              <ul className="tour__actions">
                {tour.actions.map((action) => (
                  <CarteAction key={action.id} action={action} onAgir={agir} />
                ))}
              </ul>
            )}

            {tour.role === 'assistant' && tour.model && (
              <p className="tour__meta muted">
                {tour.model} · <span className="num">{tour.tokens}</span> jetons
              </p>
            )}
          </article>
        ))}

        {busy && <p className="assistant__attente muted">…</p>}
        <div ref={bas} />
      </div>

      {erreur && <p className="assistant__erreur">{erreur}</p>}

      <div className="assistant__saisie">
        <textarea
          value={texte}
          onChange={(e) => setTexte(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              envoyer()
            }
          }}
          placeholder="fusionne mes deux routines du matin…"
          rows={2}
        />
        <button className="cta" onClick={envoyer} disabled={busy || !texte.trim()}>
          {busy ? 'Un instant…' : 'Demander'}
        </button>
      </div>
    </motion.div>
  )
}

/** Une action proposée : ce que ça change, et le geste qui l'écrit.
 *
 * L'avant/après est la pièce maîtresse. Sans lui, appliquer serait un pari sur
 * ce que l'assistant a compris — et une action au mauvais objet est le pire
 * résultat possible, pire qu'un refus.
 */
function CarteAction({
  action,
  onAgir,
}: {
  action: ActionProposee
  onAgir: (action: ActionProposee, appliquer: boolean) => void
}) {
  const attente = action.state === 'attente'

  return (
    <li className={`acte acte--${action.state}`}>
      <header className="acte__head">
        <span className="acte__label">{action.label}</span>
        <span className={`acte__etat acte__etat--${action.state}`}>{ETATS[action.state]}</span>
      </header>

      {attente || action.state === 'appliquee' ? (
        <div className="acte__diff">
          <p className="acte__avant">{action.before}</p>
          <span className="acte__fleche" aria-hidden>
            →
          </span>
          <p className="acte__apres">{action.after}</p>
        </div>
      ) : (
        <p className="acte__detail">{action.detail}</p>
      )}

      {attente && action.warning && <p className="acte__warning">{action.warning}</p>}

      {attente && (
        <div className="row acte__boutons">
          <button className="ghost acte__ok" onClick={() => onAgir(action, true)}>
            Appliquer
          </button>
          <button className="ghost" onClick={() => onAgir(action, false)}>
            Non
          </button>
        </div>
      )}
    </li>
  )
}

const ETATS: Record<ActionProposee['state'], string> = {
  attente: 'à appliquer',
  appliquee: 'appliquée',
  ecartee: 'écartée',
  perimee: 'périmée',
}

/** Trois exemples, sur un fil vide.
 *
 * Un champ de saisie vide face à un assistant capable de trente-deux choses est
 * un espace à remplir, et le §0.9 les interdit. Trois phrases concrètes disent
 * en une seconde ce qu'on a le droit de demander.
 */
function Amorces({ onPick }: { onPick: (texte: string) => void }) {
  const exemples = [
    'fusionne mes deux routines du matin',
    "découpe l'étape la plus grosse de mon projet en cours",
    'passe la fenêtre du soir à 19h–23h en semaine',
  ]

  return (
    <div className="amorces">
      <p className="muted">
        Demande en français. Il te répondra par des changements à appliquer, un par un.
      </p>
      <ul>
        {exemples.map((exemple) => (
          <li key={exemple}>
            <button className="ghost" onClick={() => onPick(exemple)}>
              {exemple}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Le bouton qui appelle l'assistant. Discret, présent partout, jamais un onglet. */
export function AssistantButton({ onOpen }: { onOpen: () => void }) {
  return (
    <button className="assistant__appel" onClick={onOpen} aria-label="Parler à l'assistant">
      <span aria-hidden>✦</span>
    </button>
  )
}
