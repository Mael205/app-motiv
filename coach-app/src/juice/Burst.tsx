import { useEffect, useRef } from 'react'
import { useReducedMotion } from './useReducedMotion'

/** Une gerbe de particules, en canvas, jetable.
 *
 * En canvas et non en DOM : trente nœuds animés forcent le navigateur à
 * recalculer un layout trente fois par frame, et c'est exactement le genre de
 * détail qui fait qu'une interface « juicy » rame sur le téléphone où elle
 * devait faire plaisir. Un seul canvas, une seule couche composite.
 *
 * Le composant se démonte tout seul quand la gerbe est finie : rien à nettoyer
 * côté appelant, qui a d'autres soucis au moment où il en déclenche une.
 */
export function Burst({
  x = 0.5,
  y = 0.5,
  count = 26,
  color = '#E8A33D',
  spread = 260,
  gravity = 420,
  life = 900,
  onDone,
}: {
  x?: number
  y?: number
  count?: number
  color?: string
  spread?: number
  gravity?: number
  life?: number
  onDone?: () => void
}) {
  const ref = useRef<HTMLCanvasElement>(null)
  const reduced = useReducedMotion()

  useEffect(() => {
    if (reduced) {
      onDone?.()
      return
    }
    const canvas = ref.current
    if (!canvas) return

    const dpr = Math.min(2, devicePixelRatio || 1)
    const w = canvas.offsetWidth
    const h = canvas.offsetHeight
    canvas.width = w * dpr
    canvas.height = h * dpr
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.scale(dpr, dpr)

    const particles = Array.from({ length: count }, () => {
      const angle = Math.random() * Math.PI * 2
      // Racine carrée du hasard : sans elle les particules s'agglutinent au
      // centre, parce qu'un disque a plus de surface à sa périphérie.
      const speed = spread * (0.35 + Math.sqrt(Math.random()) * 0.65)
      return {
        x: x * w,
        y: y * h,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - spread * 0.35,
        size: 1.5 + Math.random() * 2.5,
        rot: Math.random() * Math.PI,
        spin: (Math.random() - 0.5) * 12,
      }
    })

    let raf = 0
    let last = performance.now()
    const start = last

    const tick = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000)
      last = now
      const age = (now - start) / life

      ctx.clearRect(0, 0, w, h)
      if (age >= 1) {
        onDone?.()
        return
      }

      ctx.globalAlpha = 1 - age * age
      ctx.fillStyle = color

      for (const p of particles) {
        p.vy += gravity * dt
        p.x += p.vx * dt
        p.y += p.vy * dt
        p.rot += p.spin * dt

        ctx.save()
        ctx.translate(p.x, p.y)
        ctx.rotate(p.rot)
        // Des éclats allongés plutôt que des ronds : ils portent une direction,
        // donc ils lisent le mouvement au lieu de flotter.
        ctx.fillRect(-p.size, -p.size * 0.4, p.size * 2.6, p.size * 0.8)
        ctx.restore()
      }

      raf = requestAnimationFrame(tick)
    }

    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [reduced])

  if (reduced) return null

  return (
    <canvas
      ref={ref}
      aria-hidden
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 3,
      }}
    />
  )
}
