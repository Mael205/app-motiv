import { motion } from 'motion/react'
import type { Progression, RankState, SeasonState, Streak } from '../types'
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
  rank,
}: {
  progression: Progression
  streak: Streak
  season: SeasonState | null
  rank: RankState
}) {
  // Le rang dit ce qu'il a coûté, pas seulement sa lettre : sans ça, il
  // ressemble à une récompense d'XP, ce qu'il n'est justement plus (SPEC §4.4).
  const rankTitle = `Rang ${rank.code} — ${rank.weeks_kept} semaine${
    rank.weeks_kept > 1 ? 's' : ''
  } d'engagements tenus`

  return (
    <section className="hero panel panel--accent">
      {season && (
        <div className="hero__season">
          <span className="hero__season-name display">{season.name}</span>
          <span className="label">Saison {season.index}</span>
        </div>
      )}

      <div className="row hero__main">
        <div className="rank" title={rankTitle}>
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
