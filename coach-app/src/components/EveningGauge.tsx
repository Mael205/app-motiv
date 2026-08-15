import { motion } from 'motion/react'
import type { Evening } from '../types'
import './EveningGauge.css'

/** L'élément signature (SPEC §7).
 *
 * Une bande unique représentant la fenêtre du soir, la zone écoulée en creux,
 * les blocs de session posés dessus et un curseur temps réel. Elle dit une
 * seule chose : voilà ce qu'il te reste ce soir.
 */
export function EveningGauge({ evening, now }: { evening: Evening; now: Date }) {
  const start = new Date(evening.start)
  const end = new Date(evening.end)
  const total = end.getTime() - start.getTime()
  const elapsed = Math.min(1, Math.max(0, (now.getTime() - start.getTime()) / total))

  const hours: { ratio: number; label: string }[] = []
  const cursor = new Date(start)
  cursor.setMinutes(0, 0, 0)
  if (cursor < start) cursor.setHours(cursor.getHours() + 1)
  while (cursor <= end) {
    hours.push({
      ratio: (cursor.getTime() - start.getTime()) / total,
      label: `${cursor.getHours()}h`,
    })
    cursor.setHours(cursor.getHours() + 1)
  }

  const workedMinutes = evening.blocks.reduce((sum, b) => sum + b.minutes, 0)
  const remainingMinutes = Math.max(0, Math.round((1 - elapsed) * evening.total_minutes))

  return (
    <section className="gauge">
      <header className="row row--between gauge__head">
        <span className="label">La soirée</span>
        <span className="gauge__remaining">
          <span className="num">{remainingMinutes}</span>
          <span className="label"> min restantes</span>
        </span>
      </header>

      <div className="gauge__track" role="img" aria-label={`${remainingMinutes} minutes restantes ce soir`}>
        <div className="gauge__spent" style={{ width: `${elapsed * 100}%` }} />

        {hours.map((h) => (
          <div key={h.label} className="gauge__tick" style={{ left: `${h.ratio * 100}%` }}>
            <span className="gauge__tick-label">{h.label}</span>
          </div>
        ))}

        {evening.blocks.map((block, i) => (
          <motion.div
            key={`${block.project}-${i}`}
            className={`gauge__block${block.running ? ' gauge__block--running' : ''}`}
            initial={{ scaleY: 0.2, opacity: 0 }}
            animate={{ scaleY: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 420, damping: 22, delay: 0.05 * i }}
            style={{
              left: `${block.start_ratio * 100}%`,
              width: `${Math.max(1.2, (block.end_ratio - block.start_ratio) * 100)}%`,
              ['--block' as string]: block.color,
            }}
            title={`${block.project} — ${block.minutes} min`}
          />
        ))}

        <div className="gauge__cursor" style={{ left: `${elapsed * 100}%` }}>
          <span className="gauge__cursor-dot" />
        </div>
      </div>

      <footer className="row row--between gauge__foot">
        <span className="muted gauge__hint">
          {workedMinutes > 0 ? (
            <>
              <span className="num">{workedMinutes}</span> min travaillées
            </>
          ) : (
            'Rien de posé pour l’instant.'
          )}
        </span>
        <span className="muted gauge__hint">
          {start.getHours()}h — {end.getHours()}h
        </span>
      </footer>
    </section>
  )
}
