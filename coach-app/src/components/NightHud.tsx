import { motion } from 'motion/react'
import type { BossState, Evening, HomeState } from '../types'
import { EveningGauge } from './EveningGauge'
import { Icon } from './art/Icons'
import './NightHud.css'

/** Zone 3 : l'état de la soirée, en un seul bloc.
 *
 * Avant, la jauge, le boss et le plancher occupaient trois panneaux séparés de
 * poids visuel identique à la décision — d'où l'impression de fourre-tout à
 * moitié vide. Les trois sont maintenant un HUD unique, secondaire par
 * construction : on le consulte, on ne le lit pas.
 */
export function NightHud({
  evening,
  boss,
  now,
  minutesToday,
  requiredMinutes,
  validated,
}: {
  evening: Evening
  boss: BossState | null
  now: Date
  minutesToday: number
  requiredMinutes: number
  validated: HomeState['validated_today']
}) {
  const floorRatio = Math.min(1, minutesToday / requiredMinutes)

  return (
    <section className="hud">
      <EveningGauge evening={evening} now={now} />

      <div className="hud__split" />

      <div className="hud__rows">
        <div className="hud__row">
          <span className="hud__icon hud__icon--floor">
            {validated ? <Icon.check size={17} /> : <Icon.target size={17} />}
          </span>
          <span className="hud__label">{validated ? 'Journée validée' : 'Plancher du jour'}</span>
          <div className="minibar">
            <motion.div
              className="minibar__fill"
              initial={false}
              animate={{ width: `${floorRatio * 100}%` }}
              transition={{ type: 'spring', stiffness: 120, damping: 22 }}
            />
          </div>
          <span className="hud__value num">
            {minutesToday}
            <span className="muted">/{requiredMinutes}</span>
          </span>
        </div>

        {boss && (
          <div className="hud__row">
            <span className="hud__icon hud__icon--boss">
              <Icon.sword size={17} />
            </span>
            <span className="hud__label" title={boss.name}>
              {boss.name}
            </span>
            <div className="minibar minibar--boss">
              <motion.div
                className="minibar__fill"
                initial={false}
                animate={{ width: `${boss.ratio * 100}%` }}
                transition={{ type: 'spring', stiffness: 120, damping: 24 }}
              />
              <div className="minibar__segments" aria-hidden>
                {Array.from({ length: 16 }, (_, i) => (
                  <span key={i} />
                ))}
              </div>
            </div>
            <span className="hud__value num">{Math.round(boss.ratio * 100)}%</span>
          </div>
        )}
      </div>
    </section>
  )
}
