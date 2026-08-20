import { useState } from 'react'
import { ProjectInterview } from './ProjectInterview'
import { api, ApiError } from '../api'
import { PROJECT_PROMPT } from '../lib/projectPrompt'
import type { ProjectPreview } from '../types'
import './NewProject.css'

const MARKS: Record<string, string> = { done: '◆', doing: '◈', todo: '◇' }

/** Créer un projet en collant le markdown produit par un chat (SPEC §4.5).
 *
 * L'interrogation qui produit une bonne roadmap se fait ailleurs tant que la
 * couche IA du §5.6 n'existe pas — le prompt est dans
 * `docs/prompt-nouveau-projet.md`. Ici, on relit et on confirme.
 *
 * L'aperçu est obligatoire : rien n'est écrit avant que l'écran ait montré ce
 * qu'il a compris. Les avertissements se montrent, ils ne bloquent pas — une
 * étape trop grosse est un défaut à corriger, pas un refus de création.
 */
export function NewProject({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false)
  const [markdown, setMarkdown] = useState('')
  const [preview, setPreview] = useState<ProjectPreview | null>(null)
  const [showPrompt, setShowPrompt] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const [aiNote, setAiNote] = useState('')

  async function copyPrompt() {
    try {
      await navigator.clipboard.writeText(PROJECT_PROMPT)
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    } catch {
      // Presse-papiers refusé (contexte non sécurisé, permission) : on montre
      // le texte, l'utilisateur le sélectionne à la main.
      setShowPrompt(true)
    }
  }

  async function analyse() {
    setBusy(true)
    setError('')
    try {
      setPreview(await api.previewProject(markdown))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Lecture impossible.')
    } finally {
      setBusy(false)
    }
  }

  /** Faire ranger le document par le coach quand le parseur a laissé des restes.
   *
   * On remplace le markdown par celui qui revient : la personne voit le format
   * canonique et peut le corriger avant de créer. Le cacher donnerait un aperçu
   * sans rapport visible avec ce qui est dans la zone de texte.
   */
  async function reread() {
    setBusy(true)
    setError('')
    try {
      const recu = await api.rereadProject(markdown)
      setMarkdown(recu.markdown)
      setPreview(recu.preview)
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 503
          ? `Relecture indisponible (${e.message}). Ce qui est lu ci-dessous reste créable tel quel.`
          : e instanceof Error
            ? e.message
            : 'Relecture impossible.',
      )
    } finally {
      setBusy(false)
    }
  }

  async function create() {
    setBusy(true)
    setError('')
    try {
      const result = await api.importProject(markdown)
      setMarkdown('')
      setPreview(null)
      setOpen(false)
      onCreated()
      window.alert(result.detail)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Création impossible.')
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <button className="ghost newproject__open" onClick={() => setOpen(true)}>
        Nouveau projet
      </button>
    )
  }

  return (
    <div className="newproject">
      {/* L'entretien en premier : c'est le chemin normal depuis le §5.6. Le
          collage reste dessous parce qu'il marche sans IA, et parce qu'il sert
          aussi quand on a deja une roadmap ecrite ailleurs. */}
      {!aiNote && (
        <ProjectInterview
          onProposed={(md) => {
            setMarkdown(md)
            setPreview(null)
          }}
          onUnavailable={setAiNote}
        />
      )}

      <p className="section-hint">
        {aiNote
          ? `Entretien indisponible (${aiNote}). Copie le prompt, fais-toi interroger dans un chat, puis colle le markdown obtenu ici.`
          : 'Ou colle directement le markdown d’une roadmap deja ecrite.'}
      </p>

      <div className="row">
        <button className="ghost" onClick={copyPrompt}>
          {copied ? 'Prompt copié' : 'Copier le prompt'}
        </button>
        <button className="ghost" onClick={() => setShowPrompt((v) => !v)}>
          {showPrompt ? 'Masquer' : 'Le lire'}
        </button>
      </div>

      {showPrompt && <pre className="newproject__prompt">{PROJECT_PROMPT}</pre>}

      <textarea
        className="newproject__input"
        value={markdown}
        onChange={(e) => {
          setMarkdown(e.target.value)
          setPreview(null)
        }}
        rows={10}
        placeholder={'# Nom du projet\n\nBranche: backend\n\n## Roadmap\n\n- [ ] La première étape (2)'}
        aria-label="Markdown du projet"
      />

      <div className="row">
        <button className="ghost" onClick={analyse} disabled={busy || !markdown.trim()}>
          Analyser
        </button>
        <button
          className="ghost"
          onClick={() => {
            setOpen(false)
            setPreview(null)
          }}
        >
          Annuler
        </button>
      </div>

      {error && <p className="newproject__error">{error}</p>}

      {preview && (
        <div className="newproject__preview">
          <h3 className="newproject__name">
            <span style={{ color: preview.color }}>{preview.emblem}</span> {preview.name || 'Sans titre'}
          </h3>
          <p className="label">
            {preview.domain_label} · {preview.branch || 'branche non précisée'} ·{' '}
            {preview.weekly_commitment} sessions/semaine · {preview.open_steps} étape(s) ouverte(s)
          </p>
          <p className="label">
            Vérification : {preview.verification_label}
            {preview.repo_path && ` · ${preview.repo_path}`}
          </p>

          {/* Ce qui a été compris au-delà de la liste d'étapes. Un aperçu qui
              cache la moitié du document laisse valider une roadmap qu'on n'a
              pas vue — et l'objectif est justement la partie qu'un modèle rate
              le plus souvent. */}
          {preview.objective && <p className="newproject__objective">{preview.objective}</p>}
          {(preview.parcours.length > 0 || preview.ecartees.length > 0) && (
            <p className="label">
              {preview.parcours.length > 0 && `${preview.parcours.length} bloc(s) de parcours`}
              {preview.parcours.length > 0 && preview.ecartees.length > 0 && ' · '}
              {preview.ecartees.length > 0 && `${preview.ecartees.length} ressource(s) écartée(s)`}
            </p>
          )}

          <ul className="newproject__steps">
            {preview.steps.map((step, i) => (
              <li key={i} className={step.needs_split ? 'newproject__step--split' : undefined}>
                <span className="newproject__mark" aria-hidden>
                  {MARKS[step.state] ?? '◇'}
                </span>
                {step.label}
                <span className="newproject__estimate">{step.estimated_sessions}</span>
              </li>
            ))}
          </ul>

          {/* Ce que le parseur n'a pas su placer, et la porte de sortie. Le
              montrer est le point important : un document à moitié lu se
              présentait comme parfaitement lu, et on créait un projet amputé
              sans jamais l'apprendre. */}
          {preview.ignored.length > 0 && (
            <div className="newproject__unread">
              <p className="label">
                {preview.ignored.length} ligne(s) non comprises, perdues si tu crées maintenant
              </p>
              <ul className="newproject__unread-lines">
                {preview.ignored.slice(0, 5).map((line, i) => (
                  <li key={i}>{line}</li>
                ))}
              </ul>
              <button className="ghost" onClick={reread} disabled={busy}>
                {busy ? 'Le coach relit…' : 'Faire relire par le coach'}
              </button>
            </div>
          )}

          {preview.warnings.length > 0 && (
            <ul className="newproject__warnings">
              {preview.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}

          <button className="newproject__create" onClick={create} disabled={busy || !preview.valid}>
            {preview.valid ? 'Créer le projet' : 'Markdown incomplet'}
          </button>
        </div>
      )}
    </div>
  )
}
