import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { grouper, isoDans, RACCOURCIS } from '../lib/ponctuels'
import type { PonctuelEntry } from '../types'
import { Icon } from './art/Icons'
import { EnErreur } from './EtatCharge'
import './Ponctuels.css'

/** Les choses à faire une fois : commander, appeler, poster.
 *
 * **Pourquoi ça existe alors que le §0 refuse la todo-list.** Une course qu'on
 * garde en tête occupe la place d'une session — c'est la même charge mentale
 * que le frigo enlève aux idées de projet, sur un objet différent. L'écrire la
 * sort de la tête.
 *
 * **Pourquoi ça ne ressemble pas à une todo-list.** Rien ici ne rapporte : ni
 * XP, ni Éclats, ni coche de routine, ni journée validée. Rien n'apparaît sur
 * l'écran du soir, qui ne porte qu'une décision (§11.1). Trois courses cochées
 * ressemblent à une soirée productive, et c'est exactement le mode de
 * défaillance que tout le reste du système combat — la liste vit donc ici,
 * dans l'onglet où l'on range, jamais dans celui où l'on démarre.
 *
 * ## Ce que la refonte du 20 août 2026 change, et pourquoi
 *
 * Le contenu est identique ; c'est **la saisie** qui a été reprise. Une course
 * arrive en une seconde et repart aussi vite : si la noter demande de viser
 * trois champs sur une seule ligne — texte, date, bouton, tous à la même
 * taille —, elle ne se note pas, et la liste ne sert plus à rien.
 *
 * Trois décisions :
 *
 * - **un seul champ visible.** Le texte, pleine largeur, et Entrée qui valide.
 *   L'échéance est un second temps, replié, parce que la plupart des courses
 *   n'en ont pas — le modèle le dit déjà : une date obligatoire ferait inventer
 *   des dates, et une date inventée dépassée est une fausse alerte ;
 * - **des raccourcis d'échéance** plutôt qu'un calendrier. « Demain » se tape
 *   en un geste au doigt, là où un sélecteur de date natif demande de
 *   comprendre un mois. Le champ date reste, pour les vraies dates ;
 * - **des groupes** — en retard, aujourd'hui, plus tard, sans date. Une liste à
 *   plat trie correctement mais ne se lit pas : ce qui presse et ce qui attend
 *   ont exactement la même apparence, donc on relit tout à chaque fois.
 *
 * Une ligne faite reste barrée un jour puis disparaît d'elle-même. La retirer
 * immédiatement priverait du seul retour que la mécanique offre ; la garder
 * pour toujours referait la liste que personne ne relit.
 */
export function Ponctuels() {
  const [items, setItems] = useState<PonctuelEntry[] | null>(null)
  const [draft, setDraft] = useState('')
  const [due, setDue] = useState('')
  const [dateOuverte, setDateOuverte] = useState(false)
  const [busy, setBusy] = useState(false)
  const champ = useRef<HTMLInputElement>(null)

  const [erreur, setErreur] = useState('')

  /* Toute requête de cette feuille passe par ici.
   *
   * Les quatre appels — charger, noter, cocher, retirer — étaient tous nus :
   * un serveur muet rejetait la promesse dans le vide, et comme la liste rend
   * `null` tant qu'elle n'a rien, **la section Ponctuel disparaissait
   * entièrement** de l'onglet, sans un mot. Une feuille qui s'efface se lit
   * comme « il n'y a rien à faire », c'est-à-dire l'inverse de la vérité. */
  async function tenter(geste: () => Promise<unknown>) {
    try {
      setErreur('')
      await geste()
    } catch (e) {
      setErreur(e instanceof Error ? e.message : 'Action impossible.')
    }
  }

  async function load() {
    await tenter(async () => setItems(await api.ponctuels()))
  }

  /** Un geste de ligne : on le joue, puis on relit la liste depuis le serveur.
   *  Les deux sont dans la même garde — si la coche échoue, on ne recharge pas
   *  pour rien, et le message vient d'un seul endroit. */
  async function agirSurLaLigne(geste: () => Promise<unknown>) {
    await tenter(async () => {
      await geste()
      setItems(await api.ponctuels())
    })
  }

  useEffect(() => {
    load()
  }, [])

  async function add() {
    const texte = draft.trim()
    if (!texte || busy) return
    setBusy(true)
    try {
      await tenter(async () => {
        await api.addPonctuel(texte, due || null)
        setDraft('')
      setDue('')
      setDateOuverte(false)
        await load()
        // Le champ garde le focus : on note rarement une seule course. Le
        // reprendre à la main entre deux lignes est le genre de friction qui
        // fait qu'on note la première et qu'on oublie la seconde.
        champ.current?.focus()
      })
    } finally {
      setBusy(false)
    }
  }

  const groupes = useMemo(() => grouper(items ?? []), [items])

  // La section reste, même sans données, dès lors qu'il y a quelque chose à
  // dire. Elle ne s'efface que pendant le chargement initial, qui est bref.
  if (!items && !erreur) return null

  const restants = (items ?? []).filter((i) => !i.done).length

  return (
    <section>
      <h2 className="section-title display">
        <Icon.check size={18} /> Ponctuel
      </h2>
      <p className="section-hint">
        {restants === 0
          ? "Rien en attente. Ce qui s'écrit ici ne rapporte rien — c'est fait exprès."
          : `${restants} chose(s) à faire une fois. Aucune ne compte comme du travail.`}
      </p>

      {erreur && <EnErreur message={erreur} onRetry={load} />}

      <div className="ponctuels__saisie">
        <div className="ponctuels__ligne field-row">
          <input
            ref={champ}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && add()}
            placeholder="Commander la carte mère…"
            aria-label="Nouvelle chose à faire"
          />
          <button className="ghost ponctuels__noter" onClick={add} disabled={!draft.trim() || busy}>
            Noter
          </button>
        </div>

        {/* L'échéance, en second temps. Repliée tant qu'on n'en demande pas :
            elle concerne une minorité de lignes, et un champ affiché en
            permanence se lit comme un champ à remplir. */}
        <div className="ponctuels__quand">
          {!dateOuverte && !due ? (
            <button className="ponctuels__lien" onClick={() => setDateOuverte(true)}>
              + une échéance
            </button>
          ) : (
            <>
              {RACCOURCIS.map((raccourci) => {
                const valeur = isoDans(raccourci.jours)
                return (
                  <button
                    key={raccourci.label}
                    className={`ponctuels__chip${due === valeur ? ' ponctuels__chip--actif' : ''}`}
                    onClick={() => setDue(due === valeur ? '' : valeur)}
                  >
                    {raccourci.label}
                  </button>
                )
              })}
              <input
                type="date"
                className="ponctuels__date"
                value={due}
                onChange={(e) => setDue(e.target.value)}
                aria-label="Échéance, facultative"
              />
              <button
                className="ponctuels__lien"
                onClick={() => {
                  setDue('')
                  setDateOuverte(false)
                }}
              >
                sans date
              </button>
            </>
          )}
        </div>
      </div>

      {groupes.map(({ titre, lignes }) => (
        <div key={titre} className="ponctuels__groupe">
          {/* Le titre du groupe n'apparaît que s'il y a plusieurs groupes :
              « Sans date » écrit au-dessus d'une liste de trois courses toutes
              sans date est un intertitre qui ne distingue rien. */}
          {groupes.length > 1 && <h3 className="ponctuels__titre label">{titre}</h3>}
          <ul className="ponctuels">
            {lignes.map((item) => (
              <Ligne key={item.id} item={item} onAction={agirSurLaLigne} />
            ))}
          </ul>
        </div>
      ))}
    </section>
  )
}

function Ligne({
  item,
  onAction,
}: {
  item: PonctuelEntry
  /** Joue le geste, puis recharge — le tout sous la garde d'erreur du parent.
   *  Cocher et retirer partaient auparavant en requêtes nues : une coche
   *  refusée par le serveur ne laissait aucune trace, et la case restait dans
   *  l'état où le doigt l'avait mise. */
  onAction: (geste: () => Promise<unknown>) => Promise<void>
}) {
  return (
    <li
      className={`ponctuel${item.done ? ' ponctuel--done' : ''}${
        item.late ? ' ponctuel--late' : ''
      }`}
    >
      {/* Une case, pas une pastille décorative : la cible fait quarante-quatre
          pixels de haut, ce qui est la taille minimale d'une chose qu'on coche
          au doigt d'une main, debout, dans un couloir. */}
      <button
        className="ponctuel__check"
        onClick={async () => {
          await onAction(() => api.togglePonctuel(item.id))
        }}
        aria-pressed={item.done}
        aria-label={item.done ? `Rouvrir : ${item.label}` : `Fait : ${item.label}`}
      >
        <span className="ponctuel__case" aria-hidden />
      </button>

      <span className="ponctuel__label">{item.label}</span>

      {item.due_on && !item.done && (
        <span className="ponctuel__due">
          {item.late ? 'en retard' : item.due_today ? "aujourd'hui" : formatDate(item.due_on)}
        </span>
      )}

      <button
        className="ponctuel__remove"
        onClick={async () => {
          await onAction(() => api.removePonctuel(item.id))
        }}
        aria-label={`Retirer : ${item.label}`}
      >
        ×
      </button>
    </li>
  )
}

/** « 24 août ». La date vient du serveur en ISO ; seul l'affichage est local. */
function formatDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })
}
