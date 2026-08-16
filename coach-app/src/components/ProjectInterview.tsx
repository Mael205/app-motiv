import { useState } from 'react'
import { api, ApiError } from '../api'
import type { Interview } from '../types'
import './ProjectInterview.css'

/** L'entretien du §4.5 : le coach interroge, puis écrit la roadmap.
 *
 * Remplace le va-et-vient vers un chat externe. Une question à la fois, jamais
 * un formulaire — un questionnaire à cases produit exactement les roadmaps
 * floues que le §4.5 traite comme des défauts du système.
 *
 * **Sans modèle, ce composant s'efface au lieu d'insister.** L'entretien est le
 * seul service du coach sans repli déterministe : aucun algorithme ne sait
 * interroger quelqu'un sur son projet. Quand le serveur répond 503, on renvoie
 * donc vers le collage de markdown, qui marche sans IA et produit le même
 * résultat par le même parseur.
 */
export function ProjectInterview({
  onProposed,
  onUnavailable,
}: {
  onProposed: (markdown: string) => void
  onUnavailable: (reason: string) => void
}) {
  const [interview, setInterview] = useState<Interview | null>(null)
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function run<T>(action: () => Promise<T>): Promise<T | null> {
    setBusy(true)
    setError('')
    try {
      return await action()
    } catch (e) {
      // Un 503 n'est pas une panne à afficher : c'est l'absence du service, et
      // elle a une porte de sortie utilisable tout de suite.
      if (e instanceof ApiError && e.status === 503) onUnavailable(e.message)
      else setError(e instanceof Error ? e.message : 'Entretien interrompu.')
      return null
    } finally {
      setBusy(false)
    }
  }

  async function start() {
    const recu = await run(() => api.startInterview())
    if (recu) setInterview(recu)
  }

  async function reply() {
    if (!interview || !answer.trim()) return
    const recu = await run(() => api.replyInterview(interview.id, answer))
    if (!recu) return
    setAnswer('')
    setInterview(recu)
    if (recu.status === 'propose') onProposed(recu.markdown)
  }

  if (!interview) {
    return (
      <button className="ghost interview__open" onClick={start} disabled={busy}>
        {busy ? 'Le coach prépare ses questions…' : 'Se faire interroger par le coach'}
      </button>
    )
  }

  const question = interview.messages[interview.messages.length - 1]?.content ?? ''

  return (
    <section className="interview">
      <div className="interview__head">
        <span className="label">Entretien</span>
        <span className="interview__count num">
          {interview.questions_posees} / {interview.max_questions}
        </span>
      </div>

      {/* L'échange déjà eu reste lisible : on répond mieux en voyant ce qu'on a
          déjà dit, et une réponse mal comprise se repère là. */}
      {interview.messages.length > 1 && (
        <ol className="interview__log">
          {interview.messages.slice(0, -1).map((m, i) => (
            <li key={i} className={`interview__line interview__line--${m.role}`}>
              {m.content}
            </li>
          ))}
        </ol>
      )}

      {interview.status === 'en_cours' ? (
        <>
          <p className="interview__question">{question}</p>

          <textarea
            className="interview__answer"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            rows={3}
            placeholder="Réponds comme tu parles. Le coach relance si c'est trop vague."
            aria-label="Ta réponse"
            autoFocus
          />

          {error && <p className="interview__error">{error}</p>}

          <button className="cta" onClick={reply} disabled={busy || !answer.trim()}>
            {busy ? 'Le coach réfléchit…' : 'Répondre'}
          </button>
        </>
      ) : (
        <p className="muted">
          Roadmap écrite. Relis-la ci-dessous avant de créer le projet — rien n'est
          encore enregistré.
        </p>
      )}
    </section>
  )
}
