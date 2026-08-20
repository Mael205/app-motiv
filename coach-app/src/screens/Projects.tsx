import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { DiscardedResourceView, ProjectBlocView, ProjectDetail } from '../types'
import { Icon } from '../components/art/Icons'
import { NewProject } from '../components/NewProject'
import { Ponctuels } from '../components/Ponctuels'
import { Roadmap } from '../components/Roadmap'
import { EnCharge, EnErreur } from '../components/EtatCharge'
import { animerAnneau, quandVisible, useInclinaison, useRevelation } from '../juice'
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
  const [erreur, setErreur] = useState('')

  /* Les deux appels sont attrapés ensemble : ils viennent du même serveur,
     et si l'un tombe l'autre tombe. Sans ce `catch`, la promesse rejetée
     laissait `projects` à `null` — donc l'écran sur « Chargement… » pour
     toujours, sans message ni sortie. */
  async function load() {
    try {
      setErreur('')
      setProjects(await api.projects())
      setIdeas(await api.fridge())
    } catch (e) {
      setErreur(e instanceof Error ? e.message : 'Chargement impossible.')
    }
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

  const slots = projects?.filter((p) => p.slot !== null && !p.is_coach_project) ?? []
  const others = projects?.filter((p) => p.slot === null || p.is_coach_project) ?? []

  /* Les cartes et les idées se lèvent quand le défilement les atteint. Le
     drapeau attend les données : observer un « Chargement… » reviendrait à
     n'observer jamais les cartes qui le remplacent. */
  const scene = useRevelation(
    { devoiler: '.section-title', lever: '.pcard, .ideas li, .ponctuel' },
    Boolean(projects),
  )

  /* Les cartes s'inclinent vers le pointeur. La signature les fait
     re-brancher quand la liste change : une etape cochee remplace les nœuds,
     et des ecouteurs poses sur des cartes detachees n'inclineraient plus. */
  useInclinaison(scene, '.pcard', projects?.map((p) => p.id).join(','))

  if (erreur) return <EnErreur message={erreur} onRetry={load} />
  if (!projects) return <EnCharge />

  return (
    <div className="projects" ref={scene}>
      {/* Deux colonnes au-delà du seuil bureau. En une seule, les cartes
          s'étiraient sur treize cents pixels : les libellés d'étape et leurs
          pastilles de charge se retrouvaient à un mètre l'un de l'autre, et
          aucune ligne ne se lisait d'un seul regard. Ce qu'on fait à gauche,
          ce qu'on range à droite. */}
      <div className="projects__main">
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
      </div>

      <div className="projects__side">
        <section>
          <h2 className="section-title display">
            <Icon.fridge size={19} /> Le frigo
          </h2>
          <p className="section-hint">
            {ideas.length === 0
              ? 'Vide. La prochaine idée excitante atterrit ici au lieu de te coûter un projet.'
              : `${ideas.length} idée(s) en attente. Elles ne prennent aucun slot.`}
          </p>

          <div className="field-row fridge">
            <input
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

        {/* Les courses vivent dans l'onglet où l'on range, à côté du frigo et
            jamais sur l'accueil : le §11.1 veut une décision qui domine, et une
            liste de choses faisables en deux minutes juste à côté du bouton
            « Démarrer » en ferait une option confortable. */}
        <Ponctuels />
      </div>
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
        <ProgressRing percent={percent} />

        <div className="pcard__titles">
          <h3 className="pcard__name">
            <span className="pcard__emblem" aria-hidden="true">
              {project.emblem}
            </span>
            {project.name}
          </h3>
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

      {/* L'objectif est la condition de fin du projet, pas son thème. Il est
          au-dessus de la roadmap parce que c'est lui qui dit si les étapes
          mènent quelque part — une roadmap se lit toujours comme cohérente
          quand on ne sait plus ce qu'elle vise. */}
      {project.objective && (
        <p className="pcard__objective">
          <span className="label">Fini quand</span> {project.objective}
        </p>
      )}
      {project.frame && <p className="pcard__frame">{project.frame}</p>}

      <Roadmap steps={project.steps} onComplete={onComplete} />

      {/* Sous la roadmap, et non au-dessus. Le bouton « Bloqué par autre chose
          que moi » flottait entre l'objectif et la première étape, sans rien à
          quoi se rattacher visuellement. C'est une sortie de secours : elle se
          lit après le chemin qu'elle interrompt. Que le projet soit en attente
          reste visible en haut — la carte s'éteint et l'anneau pâlit. */}
      {onHold && <HoldPanel project={project} onHold={onHold} />}

      {project.parcours.length > 0 && <Parcours blocs={project.parcours} projectId={project.id} />}
      {project.ecartees.length > 0 && <Ecartees items={project.ecartees} />}
    </article>
  )
}

/** Le parcours : les blocs de plusieurs mois, sous la roadmap du moment.
 *
 * Replié par défaut, et c'est le seul endroit du produit où un dépliant se
 * justifie : le parcours ne sert jamais le soir. Il sert le jour où l'on se
 * demande combien il reste, ou pourquoi on fait ce bloc-là. Déplié en
 * permanence, il noierait les quatre étapes qui, elles, servent ce soir.
 */
function Parcours({ blocs, projectId }: { blocs: ProjectBlocView[]; projectId: number }) {
  const charge = blocs.filter((b) => b.load).map((b) => b.load)

  return (
    <details className="parcours">
      <summary className="parcours__summary">
        <span className="label">Le parcours</span>
        <span className="parcours__count num">{blocs.length} blocs</span>
        {charge.length > 0 && <span className="parcours__load muted">{charge.join(' · ')}</span>}
      </summary>

      <ol className="parcours__list">
        {blocs.map((bloc) => (
          <li key={bloc.id} className={`parcours__bloc${bloc.optional ? ' parcours__bloc--opt' : ''}`}>
            <p className="parcours__name">
              {bloc.name}
              {bloc.optional && <span className="parcours__tag">facultatif</span>}
            </p>
            {bloc.outcome && <p className="parcours__outcome">{bloc.outcome}</p>}
            <p className="parcours__meta muted">
              {bloc.url ? (
                <a href={bloc.url} target="_blank" rel="noreferrer">
                  {bloc.resource || bloc.url}
                </a>
              ) : (
                bloc.resource
              )}
              {bloc.load && <span> · {bloc.load}</span>}
              {/* Le prix est écrit même quand il est nul : une ressource
                  payante découverte à mi-parcours arrête le parcours. */}
              {bloc.cost && <span> · {bloc.cost}</span>}
            </p>
            {bloc.exit_criterion && (
              <>
                <p className="parcours__exit">Sortie : {bloc.exit_criterion}</p>
                {/* Le critère de sortie a été écrit à froid, des mois avant
                    d'être atteint. C'est ce qui fait de sa validation une
                    preuve et non une auto-évaluation : on ne peut pas déplacer
                    une barre qu'on a posée avant de savoir où elle tomberait. */}
                <PreuveBouton projectId={projectId} blocId={bloc.id} critere={bloc.exit_criterion} />
              </>
            )}
          </li>
        ))}
      </ol>
    </details>
  )
}

/** Le bouton qui transforme un critère atteint en capacité constatée.
 *
 * Il ne se coche pas et ne se dégrise pas : rien dans le système ne sait si le
 * critère est rempli, et prétendre le savoir serait mentir. Il demande une
 * confirmation, parce qu'une preuve ne se retire jamais (§17) — c'est la seule
 * écriture du produit qu'on ne peut pas défaire.
 */
function PreuveBouton({
  projectId,
  blocId,
  critere,
}: {
  projectId: number
  blocId: number
  critere: string
}) {
  const [etat, setEtat] = useState<'repos' | 'confirme' | 'fait'>('repos')

  if (etat === 'fait') return <p className="parcours__preuve-ok">Preuve enregistrée.</p>

  if (etat === 'confirme') {
    return (
      <div className="parcours__preuve">
        <p className="parcours__preuve-question">
          « {critere} » — c'est constaté, pas presque ?
        </p>
        <div className="row">
          <button
            className="ghost"
            onClick={async () => {
              await api.declarerPreuve(projectId, critere, blocId)
              setEtat('fait')
            }}
          >
            Oui, c'est fait
          </button>
          <button className="ghost" onClick={() => setEtat('repos')}>
            Pas encore
          </button>
        </div>
      </div>
    )
  }

  return (
    <button className="ghost parcours__preuve-open" onClick={() => setEtat('confirme')}>
      Ce critère est atteint
    </button>
  )
}

/** Les ressources écartées, et pourquoi.
 *
 * Sans la raison écrite, on refait l'arbitrage chaque fois qu'on recroise la
 * ressource — sans les éléments qui avaient servi à trancher.
 */
function Ecartees({ items }: { items: DiscardedResourceView[] }) {
  return (
    <details className="parcours parcours--ecartees">
      <summary className="parcours__summary">
        <span className="label">Écartées</span>
        <span className="parcours__count num">{items.length}</span>
      </summary>
      <ul className="parcours__list">
        {items.map((item) => (
          <li key={item.id} className="parcours__bloc">
            <p className="parcours__name">{item.name}</p>
            <p className="parcours__outcome muted">{item.reason}</p>
          </li>
        ))}
      </ul>
    </details>
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

/** Anneau de complétion. Le pourcentage, seul, au centre.
 *
 * L'emblème du projet y tenait aussi, et les deux se chevauchaient : un glyphe
 * emoji déborde largement de sa taille de police, et soixante pixels de
 * diamètre ne logent pas deux textes centrés. L'emblème est parti sur la ligne
 * du titre, où il a la place de se lire — l'anneau ne dit plus qu'une chose,
 * qui est ce qu'on vient y chercher. */
function ProgressRing({ percent }: { percent: number }) {
  const radius = 26
  const circumference = 2 * Math.PI * radius
  const cercle = useRef<SVGCircleElement>(null)
  const chiffre = useRef<HTMLSpanElement>(null)

  /* Le trait se trace au lieu d'apparaître tracé, et le chiffre monte avec
     lui. La feuille de style demandait déjà une transition sur
     `stroke-dashoffset`, mais une transition n'a rien à interpoler au premier
     rendu — l'anneau arrivait plein — et ne sait pas écrire dans un texte.
     Les deux sont sur la même horloge : un chiffre qui atteindrait sa valeur
     avant la fin du tour ferait mentir la forme. */
  useEffect(() => {
    const trait = cercle.current
    if (!trait) return
    return quandVisible(trait, () => animerAnneau(trait, circumference, percent, chiffre.current))
  }, [circumference, percent])

  return (
    <div className="ring-mini">
      <svg viewBox="0 0 64 64" width="64" height="64" aria-label={`${percent}% de la roadmap`}>
        <circle className="ring-mini__track" cx="32" cy="32" r={radius} />
        <circle
          ref={cercle}
          className="ring-mini__fill"
          cx="32"
          cy="32"
          r={radius}
          strokeDasharray={circumference}
          strokeDashoffset={circumference}
        />
      </svg>
      <span className="ring-mini__percent num" aria-hidden="true">
        {/* Le contenu du chiffre est écrit par l'animation, pas par React :
            c'est pourquoi il part de zéro ici. La valeur juste reste portée
            par l'`aria-label` du SVG, qui, lui, ne bouge jamais. */}
        <span ref={chiffre}>0</span>
        <i>%</i>
      </span>
    </div>
  )
}
