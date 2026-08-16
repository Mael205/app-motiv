import { useMemo } from 'react'
import { useReducedMotion } from './useReducedMotion'
import './Rays.css'

/** La couronne de rayons derrière un emblème (SPEC §7, séquence 3).
 *
 * C'est le cliché assumé du passage de niveau dans les jeux — et il est repris
 * ici parce qu'il fonctionne : les rayons donnent une direction à l'œil, qui
 * converge sur l'emblème au lieu de balayer un écran plein.
 *
 * Deux précautions pour qu'il ne fasse pas cheap. D'abord des largeurs
 * irrégulières : douze rayons parfaitement identiques lisent comme une roue de
 * chargement. Ensuite une rotation lente et continue, jamais un clignotement —
 * le §7 interdit le stroboscope autant par goût que par sécurité.
 */
export function Rays({
  count = 14,
  color = 'var(--accent)',
  className = '',
}: {
  count?: number
  color?: string
  className?: string
}) {
  const reduced = useReducedMotion()

  const rays = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => ({
        angle: (360 / count) * i,
        // Irrégularité déterministe : deux rendus donnent la même couronne, et
        // un rayon sur trois est nettement plus fin.
        width: i % 3 === 0 ? 1.6 : i % 2 === 0 ? 3.4 : 2.2,
        length: i % 4 === 0 ? 46 : 40,
      })),
    [count],
  )

  if (reduced) return null

  return (
    <div className={`rays ${className}`} aria-hidden>
      {rays.map((r, i) => (
        <span
          key={i}
          className="rays__ray"
          style={{
            transform: `rotate(${r.angle}deg)`,
            width: `${r.width}px`,
            height: `${r.length}%`,
            // Vif au centre, eteint vers l'exterieur. L'inverse — teste et
            // corrige — donnait des rayons a bout franc qui lisaient comme des
            // barres posees sur l'ecran au lieu d'une lueur qui irradie.
            background: `linear-gradient(to top, ${color}, transparent)`,
          }}
        />
      ))}
    </div>
  )
}
