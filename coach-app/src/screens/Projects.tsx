import { useEffect, useState } from 'react'
import { api } from '../api'
import type { ProjectDetail } from '../types'
import { Icon } from '../components/art/Icons'
import './Projects.css'

/** L'onglet Projets : les trois slots, leurs roadmaps, le frigo.
 *
 * C'est ici qu'on consulte et qu'on range — jamais sur l'écran du soir, dont
 * le seul rôle est de déclencher une session.
 */
export function Projects({ onChanged }: { onChanged: () => void }) {
  const [projects, setProjects] = useState<ProjectDetail[] | null>(null)
  const [ideas, setIdeas] = useState<{ id: number; text: string }[]>([])
  const [draft, setDraft] = useState('')

  async function load() {
    setProjects(await api.projects())
    setIdeas(await api.fridge())
  }

  useEffect(() => {
    load()
  }, [])

  async function completeStep(id: number) {
    await api.completeStep(id)
    await load()
    onChanged()
  }

  async function addIdea() {
    if (!draft.trim()) return
    await api.addIdea(draft.trim())
    setDraft('')
    await load()
  }

  if (!projects) return <p className="muted">Chargement…</p>

  const slots = projects.filter((p) => p.slot !== null && !p.is_coach_project)
  const others = projects.filter((p) => p.slot === null || p.is_coach_project)

  return (
    <div className="projects">
      <section>
        <h2 className="section-title display">Les trois slots</h2>
        <p className="section-hint">
          Trois projets actifs, pas quatre. Une nouvelle idée va au frigo, pas dans un slot.
        </p>

        {slots.map((project) => (
          <ProjectCard key={project.id} project={project} onComplete={completeStep} />
        ))}
      </section>

      {others.length > 0 && (
        <section>
          <h2 className="section-title display">Hors slot</h2>
          {others.map((project) => (
            <ProjectCard key={project.id} project={project} onComplete={completeStep} />
          ))}
        </section>
      )}

      <section>
        <h2 className="section-title display">
          <Icon.fridge size={19} /> Le frigo
        </h2>
        <p className="section-hint">
          {ideas.length === 0
            ? 'Vide. La prochaine idée excitante atterrit ici au lieu de te coûter un projet.'
            : `${ideas.length} idée(s) en attente. Elles ne prennent aucun slot.`}
        </p>

        <div className="row fridge">
          <input
            className="fridge__input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addIdea()}
            placeholder="Une idée qui vient d'arriver…"
            aria-label="Nouvelle idée de projet"
          />
          <button className="ghost" onClick={addIdea}>
            Congeler
          </button>
        </div>

        <ul className="ideas">
          {ideas.map((idea) => (
            <li key={idea.id}>{idea.text}</li>
          ))}
        </ul>
      </section>
    </div>
  )
}

function ProjectCard({
  project,
  onComplete,
}: {
  project: ProjectDetail
  onComplete: (stepId: number) => void
}) {
  const done = project.steps.filter((s) => s.state === 'done').length

  return (
    <article className="pcard" style={{ ['--project' as string]: project.color }}>
      <header className="pcard__head">
        <span className="pcard__emblem">{project.emblem}</span>
        <div className="pcard__titles">
          <h3 className="pcard__name">{project.name}</h3>
          <span className="label">
            {project.slot ? `Slot ${project.slot}` : 'Hors slot'} · {done}/{project.steps.length} étapes ·
            engagement {project.weekly_commitment}/semaine
          </span>
        </div>
        <span className="num pcard__percent">{Math.round(project.completion * 100)}%</span>
      </header>

      <div className="pcard__bar">
        <div className="pcard__bar-fill" style={{ width: `${project.completion * 100}%` }} />
      </div>

      <ol className="steps">
        {project.steps.map((step) => (
          <li key={step.id} className={`step step--${step.state}`}>
            <button
              className="step__box"
              onClick={() => step.state !== 'done' && onComplete(step.id)}
              disabled={step.state === 'done'}
              aria-label={`Terminer : ${step.label}`}
            >
              {step.state === 'done' ? <Icon.check size={14} /> : null}
            </button>
            <span className="step__label">{step.label}</span>
            {step.needs_split && <span className="step__split">à découper</span>}
            <span className="num step__estimate">{step.estimated_sessions}×</span>
          </li>
        ))}
      </ol>
    </article>
  )
}
