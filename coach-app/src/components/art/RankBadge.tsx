import { memo } from 'react'
import './RankBadge.css'

/** Le rang, avec ses ailes.
 *
 * Les ailes poussent avec le rang : deux plumes en F, six en SS. C'est la
 * seule progression cosmétique visible en permanence, et elle rend lisible
 * d'un coup d'œil que le rang est la trace longue — celle qui ne redescend
 * jamais (SPEC §12.3).
 */

const TIERS = ['F', 'E', 'D', 'C', 'B', 'A', 'S', 'SS']

export const RankBadge = memo(function RankBadge({
  rank,
  level,
  size = 104,
}: {
  rank: string
  level: number
  size?: number
}) {
  const tier = Math.max(0, TIERS.indexOf(rank))
  const feathers = 2 + Math.floor(tier * 0.6)   // 2 plumes en F, 6 en SS
  const spread = 0.55 + tier * 0.05

  return (
    <div className="rankbadge" style={{ width: size * 1.9 }}>
      <div className="rankbadge__crest" style={{ height: size }}>
        <svg viewBox="0 0 190 100" width={size * 1.9} height={size} aria-label={`Rang ${rank}`}>
          <defs>
            <linearGradient id="rb-plate" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="rgba(255,255,255,0.16)" />
              <stop offset="1" stopColor="rgba(0,0,0,0.35)" />
            </linearGradient>
          </defs>

          <Wing side="left" feathers={feathers} spread={spread} />
          <Wing side="right" feathers={feathers} spread={spread} />

          {/* L'écu hexagonal */}
          <path
            className="rankbadge__plate"
            d="M95 8 L124 25 L124 59 L95 76 L66 59 L66 25 Z"
            fill="url(#rb-plate)"
          />
          <path className="rankbadge__edge" d="M95 8 L124 25 L124 59 L95 76 L66 59 L66 25 Z" />
          <path className="rankbadge__inner" d="M95 14 L119 28 L119 56 L95 70 L71 56 L71 28 Z" />
        </svg>

        <span className="rankbadge__code display">{rank}</span>
      </div>

      {/* Le niveau vit sous l'écu, pas dessus : il empiétait sur le glyphe. */}
      <span className="rankbadge__level num">niv. {level}</span>
    </div>
  )
})

/** Une aile = un seul groupe animé.
 *
 * Avant, chaque plume portait sa propre animation décalée : jusqu'à douze
 * animations simultanées sur des `transform` de nœuds SVG, que le navigateur
 * ne peut pas composer sur le GPU. Une seule animation d'opacité par aile
 * suffit à donner la respiration, et elle est compositée.
 */
function Wing({ side, feathers, spread }: { side: 'left' | 'right'; feathers: number; spread: number }) {
  const dir = side === 'left' ? -1 : 1
  const originX = side === 'left' ? 64 : 126
  const paths: React.ReactElement[] = []

  for (let i = 0; i < feathers; i++) {
    const t = i / Math.max(1, feathers - 1)
    const length = 30 + t * 26 * spread
    const drop = 6 + t * 26
    const x = originX + dir * length
    const y = 30 + drop
    paths.push(
      <path
        key={i}
        className="rankbadge__feather"
        d={`M${originX} ${28 + i * 4}
            Q${originX + dir * length * 0.55} ${20 + drop * 0.35}
             ${x} ${y}
            Q${originX + dir * length * 0.45} ${y - 6}
             ${originX} ${34 + i * 4} Z`}
      />,
    )
  }

  return (
    <g className={`rankbadge__wing rankbadge__wing--${side}`} opacity="0.92">
      {paths}
    </g>
  )
}
