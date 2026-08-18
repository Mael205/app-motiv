import { motion } from 'motion/react'
import type { BossState, SeasonState } from '../types'
import './BossBar.css'

/** La barre de vie du boss de saison (SPEC §12.4).
 *
 * Elle répond à « à quoi ça sert, ce soir » mieux qu'un compteur d'XP : les
 * dégâts viennent des minutes travaillées et des étapes terminées.
 */
export function BossBar({
  boss,
  season,
  lastDamage,
}: {
  boss: BossState
  season: SeasonState | null
  lastDamage?: number
}) {
  const percent = boss.ratio * 100
  const segments = 24

  return (
    <section className="boss">
      <header className="row row--between">
        <div className="row boss__identity">
          <span className="boss__sigil" aria-hidden>
            ☠
          </span>
          <div className="stack">
            <span className="boss__name display">{boss.name}</span>
            {season && (
              <span className="label">
                Jour {season.day_index} / {season.days_total} · {season.days_left} restants
                {season.closes_the_year && ' · dernière saison de l’année'}
              </span>
            )}
          </div>
        </div>
        <div className="stack boss__hp">
          <span className="num">{boss.current_hp.toLocaleString('fr-FR')}</span>
          <span className="label">/ {boss.max_hp.toLocaleString('fr-FR')} pv</span>
        </div>
      </header>

      <div className="boss__track">
        <motion.div
          className="boss__fill"
          initial={false}
          animate={{ scaleX: percent / 100 }}
          transition={{ type: 'spring', stiffness: 120, damping: 24 }}
        />
        <div className="boss__segments" aria-hidden>
          {Array.from({ length: segments }, (_, i) => (
            <span key={i} />
          ))}
        </div>

        {lastDamage ? (
          <motion.span
            key={lastDamage}
            className="boss__damage num"
            initial={{ opacity: 0, y: 6, scale: 0.8 }}
            animate={{ opacity: [0, 1, 1, 0], y: [6, -14, -18, -26], scale: [0.8, 1.15, 1, 1] }}
            transition={{ duration: 1.6, times: [0, 0.15, 0.6, 1] }}
          >
            −{lastDamage}
          </motion.span>
        ) : null}
      </div>

      {boss.is_dead && <p className="boss__dead display">Boss abattu. Saison en mode extra.</p>}
    </section>
  )
}
