import { useEffect, useState } from 'react'
import { api } from '../api'
import type { RappelDuMois, Revue as RevueData } from '../types'
import './Revue.css'

/** La revue du dimanche (§5.3, §13.3).
 *
 * Le seul moment de la semaine où l'app pose des questions — et elle arrive
 * **avec les constats déjà faits**. Chaque question montre le fait qui l'a
 * provoquée : « Mardi : créneau prévu sur le bot, aucune session. » Sans le
 * fait, ce serait une page blanche, c'est-à-dire le mode de défaillance que le
 * §0.9 décrit.
 *
 * Deux phrases suffisent à chaque réponse, et on peut n'en donner aucune : le
 * bouton de clôture est actif dès le début. Une revue qui exigerait le dialogue
 * pour exister ne serait faite qu'une fois.
 */
export function Revue() {
  const [revue, setRevue] = useState<RevueData | null>(null)
  const [brouillons, setBrouillons] = useState<Record<number, string>>({})

  useEffect(() => {
    api.review().then(setRevue).catch(() => setRevue(null))
  }, [])

  if (!revue) return null

  async function envoyer(index: number) {
    const texte = (brouillons[index] ?? '').trim()
    if (!texte) return
    setRevue(await api.answerReview(index, texte))
    setBrouillons((d) => ({ ...d, [index]: '' }))
  }

  const semaine = new Date(revue.week_start).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
  })

  if (revue.closed) {
    return (
      <section className="revue">
        <h3 className="revue__titre rule-title">Revue de la semaine du {semaine}</h3>

        <div className="revue__bloc">
          <span className="revue__etiquette label">Ce qui a marché</span>
          <p>{revue.report.a_marche}</p>
        </div>
        <div className="revue__bloc">
          <span className="revue__etiquette label">Ce qui n'a pas marché</span>
          <p>{revue.report.n_a_pas_marche}</p>
        </div>
        <div className="revue__bloc revue__bloc--seul">
          <span className="revue__etiquette label">La seule chose à changer</span>
          <p>{revue.report.seule_chose}</p>
        </div>

        {revue.report.note && <p className="revue__note">{revue.report.note}</p>}

        {revue.il_y_a_quatre_semaines && (
          <IlYAQuatreSemaines rappel={revue.il_y_a_quatre_semaines} />
        )}

        <Contrat revue={revue} onApplied={setRevue} />
      </section>
    )
  }

  return (
    <section className="revue">
      <h3 className="revue__titre rule-title">Revue de la semaine du {semaine}</h3>
      <p className="revue__intro">
        Quatre questions, deux phrases chacune. Tu peux aussi n'en remplir aucune : la revue
        s'écrira quand même, en le disant.
      </p>

      {revue.il_y_a_quatre_semaines && (
        <IlYAQuatreSemaines rappel={revue.il_y_a_quatre_semaines} />
      )}

      {revue.questions.map((q, index) => (
        <article key={q.question + index} className="revue__q">
          <p className="revue__fait">{q.fait}</p>
          <p className="revue__question">{q.question}</p>

          {q.reponse ? (
            <p className="revue__reponse">{q.reponse}</p>
          ) : (
            <div className="revue__saisie">
              <textarea
                value={brouillons[index] ?? ''}
                onChange={(e) => setBrouillons((d) => ({ ...d, [index]: e.target.value }))}
                placeholder="Deux phrases suffisent…"
                rows={2}
              />
              <button className="ghost" onClick={() => envoyer(index)}>
                Répondre
              </button>
            </div>
          )}
        </article>
      ))}

      <button className="cta revue__clore" onClick={async () => setRevue(await api.closeReview())}>
        Écrire la revue{revue.answered === 0 ? ' sans réponses' : ''}
      </button>
    </section>
  )
}

/** Une note d'il y a quatre semaines, ressortie telle quelle.
 *
 * C'est le seul bloc de la revue qui ne compte rien. Les bilans mesurent, les
 * constats comparent, la trace additionne : tous disent *combien*. Une note
 * écrite il y a un mois dit *ce qu'on faisait*, et c'est la seule chose qui
 * rende visible qu'un projet a avancé — une roadmap à 60 % ne se souvient pas
 * d'avoir été à 20 %.
 *
 * Sans commentaire, et ce n'est pas un oubli : « regarde le chemin parcouru »
 * serait un jugement, même flatteur, et le §17 les interdit tous.
 */
function IlYAQuatreSemaines({ rappel }: { rappel: RappelDuMois }) {
  const jour = new Date(rappel.day).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
  })

  return (
    <aside className="rappel" style={{ ['--project' as string]: rappel.color }}>
      <span className="revue__etiquette label">Il y a quatre semaines</span>
      <p className="rappel__meta muted">
        {jour} · {rappel.project}
      </p>
      <p className="rappel__note">{rappel.note}</p>
      {rappel.next_action && (
        <p className="rappel__suite muted">Tu notais ensuite : {rappel.next_action}</p>
      )}
    </aside>
  )
}

/** Le contrat de la semaine suivante, ajusté au réel observé (§5.3).
 *
 * Proposé, jamais appliqué tout seul : le §17 interdit qu'un système baisse un
 * engagement de lui-même. Le bouton est le geste, et il n'y en a qu'un.
 */
function Contrat({ revue, onApplied }: { revue: RevueData; onApplied: (r: RevueData) => void }) {
  const changements = revue.contract.filter((l) => l.propose !== l.actuel)
  if (changements.length === 0) return null

  return (
    <div className="contrat">
      <span className="revue__etiquette label">Contrat proposé</span>
      <ul>
        {changements.map((ligne) => (
          <li key={ligne.projet}>
            <span className="contrat__projet">{ligne.projet}</span>
            <span className="num contrat__chiffres">
              {ligne.actuel} → {ligne.propose}
            </span>
            <span className="contrat__raison">{ligne.raison}</span>
          </li>
        ))}
      </ul>

      {revue.contract_applied ? (
        <p className="revue__note">Contrat appliqué.</p>
      ) : (
        <button className="ghost" onClick={async () => onApplied((await api.applyContract()).revue)}>
          Appliquer
        </button>
      )}
    </div>
  )
}
