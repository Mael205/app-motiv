import { memo } from 'react'
import type { Momentum } from '../types'
import './MomentumEmber.css'

/** La jauge de chaleur, en braise (SPEC §12.10).
 *
 * > Visualisée comme une **braise qui s'intensifie**. Un jour raté la fait
 * > tiédir, pas s'éteindre.
 *
 * Le choix de la braise plutôt que d'une barre n'est pas décoratif : une barre
 * dit « il t'en manque tant », une braise dit « voilà où tu en es ». La
 * première invite à combler un vide, la seconde à entretenir un état — et
 * l'anti-fragilité du §4.2 vit dans cette nuance.
 *
 * L'intensité, la vitesse de pulsation et la portée du halo suivent toutes le
 * niveau. C'est le principe du skill `game-feel` : plusieurs canaux dans le
 * même sens lisent comme une seule chose, alors qu'un seul canal lit comme un
 * réglage.
 *
 * Les sept jours sont montrés dessous, en points. Sans eux la jauge serait un
 * chiffre sans cause ; avec eux on voit *pourquoi* la braise est où elle est,
 * et notamment que le jour manqué de mardi n'a pas tout effacé.
 */
export const MomentumEmber = memo(function MomentumEmber({ momentum }: { momentum: Momentum }) {
  const { level, percent, multiplier, label, detail, days, cooling } = momentum

  return (
    <section
      className={`ember${cooling ? ' ember--cooling' : ''}`}
      style={{
        ['--heat' as string]: level,
        // La pulsation ralentit quand la braise faiblit : une braise mourante
        // ne clignote pas plus vite, elle respire plus lentement.
        ['--beat' as string]: `${3.4 - level * 1.6}s`,
      }}
    >
      <div className="ember__head">
        <span className="label">Momentum</span>
        <span className="ember__mult num">×{multiplier.toFixed(2)}</span>
      </div>

      <div className="ember__body">
        <div className="ember__core" aria-hidden>
          <span className="ember__glow" />
          <span className="ember__flame" />
          <span className="ember__flame ember__flame--b" />
        </div>

        <div className="ember__read">
          <p className="ember__label display">{label}</p>
          <p className="ember__detail muted">{detail}</p>
        </div>
      </div>

      <div className="ember__track" role="img" aria-label={`Chaleur ${percent} %`}>
        <span className="ember__fill" style={{ width: `${percent}%` }} />
      </div>

      <ol className="ember__days">
        {days.map((worked, i) => (
          <li
            key={i}
            className={`ember__day${worked ? ' ember__day--on' : ''}`}
            aria-label={worked ? 'travaillé' : 'manqué'}
          />
        ))}
      </ol>
    </section>
  )
})
