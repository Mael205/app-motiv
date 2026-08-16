import { memo } from 'react'
import type { SkillBranch } from '../types'
import './SkillTree.css'

/** L'arbre de compétences (SPEC §12.9).
 *
 * Le §12.9 dit pourquoi il existe, et ce n'est pas pour récompenser :
 *
 * > Rend visible ce qu'un compteur par projet cache : que 40h dispersées sur
 * > trois projets de moteur de jeu constituent quand même 40h de moteur de jeu.
 *
 * D'où deux décisions d'affichage qui vont à contre-courant de l'habitude.
 *
 * **Les branches vides sont montrées.** Une liste qui ne contiendrait que ce
 * qui progresse serait flatteuse et inutile ; ce qu'on vient chercher ici,
 * c'est aussi ce qui est à l'arrêt depuis six semaines. Elles sont rendues en
 * creux, lisibles, sans reproche attaché.
 *
 * **Les six paliers sont visibles d'emblée**, y compris ceux qui sont loin.
 * Une progression qui ne montre que le palier suivant cache la forme du
 * chemin, et c'est la forme qui donne envie.
 */
export const SkillTree = memo(function SkillTree({
  branches,
  tiers,
  compact = false,
}: {
  branches: SkillBranch[]
  tiers: number[]
  compact?: boolean
}) {
  const ordered = [...branches].sort((a, b) => b.minutes - a.minutes)

  return (
    <section className={`tree${compact ? ' tree--compact' : ''}`}>
      <div className="tree__head">
        <span className="label">Arbre de compétences</span>
        <span className="tree__total num">
          {Math.round(branches.reduce((s, b) => s + b.minutes, 0) / 60)} h
        </span>
      </div>

      <ul className="tree__list">
        {ordered.map((b) => (
          <li
            key={b.key}
            className={`tree__branch${b.minutes === 0 ? ' tree__branch--idle' : ''}`}
            style={{ ['--branch' as string]: b.color }}
          >
            <div className="tree__row">
              <span className="tree__emblem" aria-hidden>
                {b.emblem || '·'}
              </span>
              <span className="tree__name">{b.label}</span>
              <span className="tree__hours num">{b.hours} h</span>
            </div>

            {b.title && <p className="tree__title">{b.title}</p>}

            {/* Les six paliers, dont ceux qu'on n'atteindra pas cette annee.
                Voir le chemin entier est ce qui donne sa profondeur a l'arbre. */}
            <ol className="tree__tiers" aria-label={`Palier ${b.tier} sur ${tiers.length}`}>
              {tiers.map((seuil, i) => (
                <li
                  key={seuil}
                  className={`tree__tier${i < b.tier ? ' tree__tier--on' : ''}${
                    i === b.tier ? ' tree__tier--next' : ''
                  }`}
                  title={`${seuil} h`}
                >
                  {/* Le palier en cours porte sa progression : le segment se
                      remplit au lieu de s'allumer d'un coup. */}
                  {i === b.tier && (
                    <span className="tree__tier-fill" style={{ width: `${b.progress * 100}%` }} />
                  )}
                </li>
              ))}
            </ol>

            <p className="tree__next muted">
              {b.maxed
                ? 'Dernier palier atteint.'
                : b.minutes === 0
                  ? `Rien pour l'instant. Premier palier à ${b.next_hours} h.`
                  : `${b.next_hours} h pour le palier suivant.`}
            </p>
          </li>
        ))}
      </ul>
    </section>
  )
})
