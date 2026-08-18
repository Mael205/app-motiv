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

  async function toggleHold(project: ProjectDetail, endsOn: string, reason: string) {
    // Le refus vient du serveur, avec sa phrase. Recopier ici les bornes —
    // trois jours, quatorze jours, une raison nommée — les laisserait diverger
    // de celles qui font foi.
    if (project.hold) await api.releaseProject(project.id)
    else await api.holdProject(project.id, endsOn, reason)
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
          <ProjectCard
            key={project.id}
            project={project}
            onComplete={completeStep}
            onHold={toggleHold}
          />
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

        <LienDeFrigo />
      </section>
    </div>
  )
}

/** Le lien à épingler sur l'écran d'accueil du téléphone (§11.7).
 *
 * L'idée qui arrive en cours de journée est perdue si la capturer demande
 * d'ouvrir l'app, de trouver l'onglet et de taper. Un raccourci vers une page à
 * champ unique la garde. C'est ce que le bot Telegram devait faire, et le lien
 * signé le fait sans compte ni application de plus.
 */
function LienDeFrigo() {
  const [url, setUrl] = useState<string | null>(null)

  if (!url) {
    return (
      <button className="ghost lien-frigo" onClick={async () => setUrl((await api.issueLink('frigo')).url)}>
        Créer un lien à épingler
      </button>
    )
  }

  return (
    <div className="lien-frigo__resultat">
      <p className="section-hint">
        Ouvre-le sur le téléphone, puis « Ajouter à l'écran d'accueil ». Une idée, une phrase, sans
        ouvrir l'app.
      </p>
      <code className="lien-frigo__url">{url}</code>
    </div>
  )
}

function ProjectCard({
  project,
  onComplete,
  onHold,
}: {
  project: ProjectDetail
  onComplete: (stepId: number) => void
  onHold?: (project: ProjectDetail, endsOn: string, reason: string) => Promise<void>
}) {
  const done = project.steps.filter((s) => s.state === 'done').length
  const percent = Math.round(project.completion * 100)

  return (
    <article
      className={`pcard${project.hold ? ' pcard--hold' : ''}`}
      style={{ ['--project' as string]: project.color }}
    >
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

      {onHold && <HoldPanel project={project} onHold={onHold} />}

      <Roadmap steps={project.steps} onComplete={onComplete} />
    </article>
  )
}

/** L'attente déclarée d'un projet bloqué par un tiers.
 *
 * Deux champs et un bouton, sur une seule ligne quand rien n'est en cours. La
 * raison est obligatoire côté serveur, donc le bouton reste éteint tant qu'elle
 * est vide — refuser tôt évite un aller-retour dont la réponse serait connue
 * d'avance, et c'est la seule règle que le front ait le droit d'anticiper :
 * « ce champ est vide » n'est pas une règle métier.
 */
function HoldPanel({
  project,
  onHold,
}: {
  project: ProjectDetail
  onHold: (project: ProjectDetail, endsOn: string, reason: string) => Promise<void>
}) {
  const [ouvert, setOuvert] = useState(false)
  const [fin, setFin] = useState(dansUneSemaine())
  const [raison, setRaison] = useState('')
  const [refus, setRefus] = useState('')

  async function envoyer() {
    setRefus('')
    try {
      await onHold(project, fin, raison)
      setOuvert(false)
      setRaison('')
    } catch (error) {
      setRefus(error instanceof Error ? error.message : 'Refusé.')
    }
  }

  if (project.hold) {
    return (
      <div className="hold hold--active">
        <p className="hold__line">{project.hold.line}</p>
        <button className="ghost" onClick={envoyer}>
          Ce n'est plus bloqué
        </button>
      </div>
    )
  }

  if (!ouvert) {
    return (
      <button className="ghost hold__open" onClick={() => setOuvert(true)}>
        Bloqué par autre chose que moi
      </button>
    )
  }

  return (
    <div className="hold">
      <label className="hold__field">
        <span className="label">Ce qui bloque</span>
        <input
          value={raison}
          onChange={(e) => setRaison(e.target.value)}
          placeholder="j'attends l'accès au dépôt"
        />
      </label>
      <label className="hold__field hold__field--date">
        <span className="label">Jusqu'au</span>
        <input type="date" value={fin} onChange={(e) => setFin(e.target.value)} />
      </label>
      <div className="row">
        <button className="ghost" disabled={!raison.trim()} onClick={envoyer}>
          Déclarer l'attente
        </button>
        <button className="ghost" onClick={() => setOuvert(false)}>
          Annuler
        </button>
      </div>
      <p className="section-hint">
        Le slot reste pris. La détection « projet mort » se tait, et la semaine
        ne compte pas contre le rang.
      </p>
      {refus && <p className="hold__refus">{refus}</p>}
    </div>
  )
}

function dansUneSemaine(): string {
  const d = new Date()
  d.setDate(d.getDate() + 7)
  return d.toISOString().slice(0, 10)
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
