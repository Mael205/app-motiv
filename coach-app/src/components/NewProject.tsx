import { useState } from 'react'
import { api } from '../api'
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
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

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
      <p className="section-hint">
        Fais-toi interroger dans un chat avec le prompt de{' '}
        <code>docs/prompt-nouveau-projet.md</code>, puis colle le markdown ici.
      </p>

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
            {preview.branch || 'branche non précisée'} · {preview.weekly_commitment} sessions/semaine ·{' '}
            {preview.open_steps} étape(s) ouverte(s)
          </p>

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
