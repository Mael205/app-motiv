import { motion } from 'motion/react'
import type { Progression, SeasonState, Streak } from '../types'
import './CharacterHeader.css'

/** La fiche de personnage : rang, niveau, barre d'XP, streak et boucliers.
 *
 * Le rang est la trace longue (il ne redescend jamais), le streak est la
 * trace courte. Les deux cohabitent sans se confondre.
 */
export function CharacterHeader({
  progression,
  streak,
  season,
}: {
  progression: Progression
  streak: Streak
  season: SeasonState | null
}) {
  return (
    <section className="hero panel panel--accent">
      {season && (
        <div className="hero__season">
          <span className="hero__season-name display">{season.name}</span>
          <span className="label">Saison {season.index}</span>
        </div>
      )}

      <div className="row hero__main">
        <div className="rank" title={`Rang ${progression.rank}`}>
          <span className="rank__code display">{progression.rank}</span>
          <span className="rank__level num">{progression.level}</span>
        </div>

        <div className="stack hero__xp">
          <div className="row row--between">
            <span className="label">Niveau {progression.level}</span>
            <span className="hero__xp-values">
              <span className="num">{progression.into_level}</span>
              <span className="muted num">
                {' '}
                / {progression.next_level_xp - progression.level_floor_xp}
              </span>
            </span>
          </div>

          <div className="xpbar">
            <motion.div
              className="xpbar__fill"
              initial={false}
              animate={{ width: `${progression.ratio * 100}%` }}
              transition={{ type: 'spring', stiffness: 90, damping: 20 }}
            />
            <div className="xpbar__shine" />
          </div>

          <div className="row row--between hero__streak">
            <span className="hero__streak-count">
              <span className="num">{streak.current}</span>
              <span className="label"> jours d’affilée</span>
            </span>
            <span className="shields" title={`${streak.shields} bouclier(s)`}>
              {[0, 1, 2].map((i) => (
                <span key={i} className={`shield${i < streak.shields ? ' shield--full' : ''}`} />
              ))}
            </span>
          </div>
        </div>
      </div>

      {season?.baseline && <p className="hero__baseline">{season.baseline}</p>}
    </section>
  )
}
