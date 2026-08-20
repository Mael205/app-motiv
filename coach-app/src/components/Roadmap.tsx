import { motion } from 'motion/react'
import type { RoadmapStepView } from '../types'
import { Icon } from './art/Icons'
import './Roadmap.css'

/** La roadmap, dessinée comme un chemin.
 *
 * Une liste à cases ne dit pas où tu en es : elle dit ce qu'il reste. Le
 * chemin, lui, montre le parcouru, le point courant et ce qui vient — et
 * l'étape en cours est la seule à porter du relief, parce que c'est la seule
 * sur laquelle on peut agir ce soir.
 */
export function Roadmap({
  steps,
  onComplete,
}: {
  steps: RoadmapStepView[]
  onComplete: (id: number) => void
}) {
  const doneCount = steps.filter((s) => s.state === 'done').length
  const progress = steps.length ? doneCount / steps.length : 0

  // L'étape sur laquelle on peut agir : celle en cours, sinon la première non
  // faite. C'est la seule qui déplie ses attributs. Les afficher partout
  // rendrait la roadmap illisible, et les cacher partout les rendrait inutiles
  // — ils existent pour le soir où l'on démarre, donc pour une seule étape.
  const courante = steps.find((s) => s.state === 'doing') ?? steps.find((s) => s.state !== 'done')

  return (
    <ol className="rm">
      {/* Le rail parcouru, tracé une seule fois derrière les nœuds. */}
      <div className="rm__rail" aria-hidden>
        <motion.div
          className="rm__rail-done"
          initial={false}
          animate={{ scaleY: progress }}
          transition={{ type: 'spring', stiffness: 90, damping: 22 }}
        />
      </div>

      {steps.map((step, index) => (
        <li key={step.id} className={`rm__step rm__step--${step.state}`}>
          <button
            className="rm__node"
            onClick={() => step.state !== 'done' && onComplete(step.id)}
            disabled={step.state === 'done'}
            aria-label={step.state === 'done' ? step.label : `Terminer : ${step.label}`}
            title={step.state === 'done' ? 'Terminée' : 'Marquer comme terminée (60 dégâts au boss)'}
          >
            {step.state === 'done' ? (
              <Icon.check size={13} />
            ) : (
              <span className="rm__node-index num">{index + 1}</span>
            )}
          </button>

          <div className="rm__body">
            <p className="rm__label">{step.label}</p>

            <div className="rm__meta">
              {step.state === 'doing' && <span className="rm__badge rm__badge--doing">en cours</span>}
              {step.needs_split && (
                <span className="rm__badge rm__badge--split" title="Plus de 3 sessions : trop grosse pour être démarrée telle quelle">
                  à découper
                </span>
              )}
              {step.load && <span className="rm__load">{step.load}</span>}
              <span className="rm__pips" title={`${step.estimated_sessions} session(s) estimée(s)`}>
                {Array.from({ length: Math.min(step.estimated_sessions, 6) }, (_, i) => (
                  <span key={i} className="rm__pip" />
                ))}
              </span>
            </div>

            {/* Le plan ne s'affiche que s'il a quelque chose à dire. Sans cette
                garde, une étape courante sans ressource ni périmètre ni critère
                rendait un `<dl>` vide — une barre grise de la largeur de la
                carte, que rien ne distinguait d'un champ cassé. */}
            {step.id === courante?.id && (step.resource || step.scope || step.exit_criterion) && (
              <dl className="rm__plan">
                {step.resource && (
                  <div className="rm__plan-line">
                    <dt>Ressource</dt>
                    <dd>
                      {step.url ? (
                        <a href={step.url} target="_blank" rel="noreferrer">
                          {step.resource}
                        </a>
                      ) : (
                        step.resource
                      )}
                    </dd>
                  </div>
                )}
                {step.scope && (
                  <div className="rm__plan-line">
                    <dt>Périmètre</dt>
                    <dd>{step.scope}</dd>
                  </div>
                )}
                {step.exit_criterion && (
                  <div className="rm__plan-line rm__plan-line--exit">
                    <dt>Fini quand</dt>
                    <dd>{step.exit_criterion}</dd>
                  </div>
                )}
              </dl>
            )}
          </div>
        </li>
      ))}
    </ol>
  )
}
