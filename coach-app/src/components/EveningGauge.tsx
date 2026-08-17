import { memo } from 'react'
import { motion } from 'motion/react'
import { useReducedMotion } from '../juice'
import { useNow } from '../hooks/useNow'
import type { Evening } from '../types'
import './EveningGauge.css'

/** L'élément signature (SPEC §7).
 *
 * Une bande unique représentant la fenêtre du soir, la zone écoulée en creux,
 * les blocs de session posés dessus et un curseur temps réel. Elle dit une
 * seule chose : voilà ce qu'il te reste ce soir.
 */
export const EveningGauge = memo(function EveningGauge({ evening }: { evening: Evening }) {
  const now = useNow()
  const reduced = useReducedMotion()
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
        <div className="gauge__spent" style={{ transform: `scaleX(${elapsed})` }} />

        {hours.map((h) => (
          <div key={h.label} className="gauge__tick" style={{ left: `${h.ratio * 100}%` }}>
            <span className="gauge__tick-label">{h.label}</span>
          </div>
        ))}

        {evening.blocks.map((block, i) => {
          // Le dernier bloc est celui qui vient de tomber : il **se pose**,
          // avec l'écrasement au contact que demande la séquence 2 du §7. Les
          // précédents montent simplement — rejouer l'impact sur toute la
          // soirée à chaque affichage transformerait un événement en décor.
          const frais = !reduced && i === evening.blocks.length - 1 && !block.running
          return (
          <motion.div
            key={`${block.project}-${i}`}
            className={`gauge__block${block.running ? ' gauge__block--running' : ''}`}
            initial={frais ? { scaleY: 1.45, y: -12, opacity: 0 } : { scaleY: 0.2, opacity: 0 }}
            animate={
              frais
                ? { scaleY: [1.45, 0.78, 1.08, 1], y: [-12, 0, 0, 0], opacity: 1 }
                : { scaleY: 1, opacity: 1 }
            }
            transition={
              frais
                ? { duration: 0.5, times: [0, 0.42, 0.68, 1], ease: [0.22, 1, 0.36, 1] }
                : { type: 'spring', stiffness: 420, damping: 22, delay: 0.05 * i }
            }
            style={{
              left: `${block.start_ratio * 100}%`,
              width: `${Math.max(1.2, (block.end_ratio - block.start_ratio) * 100)}%`,
              ['--block' as string]: block.color,
            }}
            title={`${block.project} — ${block.minutes} min`}
          />
          )
        })}

        <div className="gauge__rail" style={{ transform: `translateX(${elapsed * 100}%)` }}>
          <div className="gauge__cursor">
            <span className="gauge__cursor-dot" />
          </div>
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
})
