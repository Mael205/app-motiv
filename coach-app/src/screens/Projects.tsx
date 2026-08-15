import { useEffect, useState } from 'react'
import { api } from '../api'
import type { ProjectDetail } from '../types'
import { Icon } from '../components/art/Icons'
import { NewProject } from '../components/NewProject'
import { Roadmap } from '../components/Roadmap'
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

        <NewProject
          onCreated={() => {
            load()
            onChanged()
          }}
        />
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
  const percent = Math.round(project.completion * 100)

  return (
    <article className="pcard" style={{ ['--project' as string]: project.color }}>
      <header className="pcard__head">
        <ProgressRing percent={percent} emblem={project.emblem} />

        <div className="pcard__titles">
          <h3 className="pcard__name">{project.name}</h3>
          <span className="label">
            {project.slot ? `Slot ${project.slot}` : 'Hors slot'} · {project.domain_label} · {done} sur{' '}
            {project.steps.length} étapes
          </span>
          <span className="pcard__commit">
            <Icon.target size={13} /> {project.weekly_commitment} sessions visées par semaine
          </span>
          <span className="label">
            Vérification : {project.verification_label}
            {project.verification !== 'manuelle' && project.repos === 0 && ' — aucun dépôt déclaré'}
          </span>
        </div>
      </header>

      <Roadmap steps={project.steps} onComplete={onComplete} />
    </article>
  )
}

/** Anneau de complétion, avec l'emblème du projet au centre. */
function ProgressRing({ percent, emblem }: { percent: number; emblem: string }) {
  const radius = 26
  const circumference = 2 * Math.PI * radius

  return (
    <div className="ring-mini">
      <svg viewBox="0 0 64 64" width="60" height="60" aria-label={`${percent}% de la roadmap`}>
        <circle className="ring-mini__track" cx="32" cy="32" r={radius} />
        <circle
          className="ring-mini__fill"
          cx="32"
          cy="32"
          r={radius}
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - percent / 100)}
        />
      </svg>
      <span className="ring-mini__emblem">{emblem}</span>
      <span className="ring-mini__percent num">{percent}%</span>
    </div>
  )
}
