import { motion } from 'motion/react'
import type { Progression, SeasonState, Streak } from '../types'
import { RankBadge } from './art/RankBadge'
import { SeasonOrnament, SeasonSigil } from './art/SeasonSigil'
import { Icon } from './art/Icons'
import './SeasonBanner.css'

/** Zone 1 : qui tu es, dans quelle saison.
 *
 * L'identité tient tout le haut de l'écran — emblème dessiné, nom de saison,
 * rang ailé, barre d'XP. C'est la seule zone décorative de l'interface, et
 * elle porte toute la direction artistique de la saison en cours.
 */
export function SeasonBanner({
  season,
  progression,
  streak,
}: {
  season: SeasonState | null
  progression: Progression
  streak: Streak
}) {
  return (
    <header className="banner">
      <div className="banner__glow" aria-hidden />

      <div className="banner__top">
        <SeasonSigil seasonKey={season?.key} size={40} className="banner__sigil" />
        <div className="banner__titles">
          <h1 className="banner__name display">{season?.name ?? 'Hors saison'}</h1>
          {season && (
            <span className="label">
              Saison {season.index} · jour {season.day_index}/{season.days_total} ·{' '}
              {season.days_left} restants
            </span>
          )}
        </div>
      </div>

      <SeasonOrnament seasonKey={season?.key} />

      <div className="banner__body">
        <RankBadge rank={progression.rank} level={progression.level} size={96} />

        <div className="banner__stats">
          <div className="row row--between banner__xp-head">
            <span className="label">Expérience</span>
            <span>
              <span className="num">{progression.into_level}</span>
              <span className="muted num"> / {progression.next_level_xp - progression.level_floor_xp}</span>
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

          <div className="banner__counters">
            <span className="counter" title="Jours d'affilée">
              <Icon.flame size={17} />
              <span className="num">{streak.current}</span>
              <span className="label">jours</span>
            </span>

            <span className="counter counter--shields" title={`${streak.shields} bouclier(s)`}>
              {[0, 1, 2].map((i) => (
                <Icon.shield key={i} size={17} className={i < streak.shields ? 'shield--on' : 'shield--off'} />
              ))}
            </span>
          </div>
        </div>
      </div>

      {season?.baseline && <p className="banner__baseline">« {season.baseline} »</p>}
    </header>
  )
}
