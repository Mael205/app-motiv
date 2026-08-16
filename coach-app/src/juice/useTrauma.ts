import { useCallback, useEffect, useRef, useState } from 'react'
import { useReducedMotion } from './useReducedMotion'

/** Secousse d'écran par « trauma » décroissant.
 *
 * Le modèle vient du skill `game-feel`, et ses deux idées comptent autant l'une
 * que l'autre :
 *
 * 1. **Les impacts ajoutent du trauma, ils ne le remettent pas à zéro.** Deux
 *    coups rapprochés secouent donc plus fort qu'un seul, ce qui est ce que
 *    l'œil attend.
 * 2. **L'amplitude est le carré du trauma.** Un petit événement bouge à peine,
 *    un gros frappe — là où une relation linéaire rend tout pareillement mou.
 *
 * Le décalage est produit par des sinus déphasés et non par un aléa par frame :
 * un aléa pur grésille comme de la neige au lieu de secouer.
 *
 * Ne bouge qu'un conteneur visuel. Rien de ce qui est cliquable ne doit être
 * déplacé pendant une secousse — viser une cible mouvante est une faute
 * d'ergonomie, pas un effet.
 */
export function useTrauma() {
  const [offset, setOffset] = useState({ x: 0, y: 0, rot: 0 })
  const trauma = useRef(0)
  const raf = useRef<number>(0)
  const reduced = useReducedMotion()

  const shake = useCallback(
    (amount: number) => {
      if (reduced) return
      trauma.current = Math.min(1, trauma.current + amount)
    },
    [reduced],
  )

  useEffect(() => {
    let t = 0
    let last = performance.now()

    const loop = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000)
      last = now
      raf.current = requestAnimationFrame(loop)

      if (trauma.current <= 0) return

      trauma.current = Math.max(0, trauma.current - 1.6 * dt)
      const s = trauma.current * trauma.current
      t += dt * 34

      setOffset({
        x: 14 * s * Math.sin(t * 1.7),
        y: 9 * s * Math.sin(t * 2.3),
        rot: 0.55 * s * Math.sin(t * 1.1),
      })

      if (trauma.current === 0) setOffset({ x: 0, y: 0, rot: 0 })
    }

    raf.current = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf.current)
  }, [])

  const style =
    offset.x || offset.y
      ? { transform: `translate3d(${offset.x}px, ${offset.y}px, 0) rotate(${offset.rot}deg)` }
      : undefined

  return { shake, style }
}
