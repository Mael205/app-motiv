import { useEffect, useRef, useState } from 'react'
import { useReducedMotion } from './useReducedMotion'

/** Un compteur qui défile avec une décélération marquée (SPEC §7, séquence 2).
 *
 * > la barre d'XP se remplit avec un compteur qui défile et une **décélération
 * > marquée**, les dégâts au boss s'affichent en chiffres qui montent.
 *
 * La décélération est le sujet. Un compteur linéaire donne l'information sans
 * la sensation : c'est la fin qui ralentit qui fait qu'on regarde le nombre
 * arriver au lieu de le lire. La courbe est donc une puissance 4 en sortie,
 * beaucoup plus brutale qu'un `ease-out` de CSS.
 *
 * Le `scale` accompagne : léger gonflement pendant la course, retour à 1 à
 * l'arrivée. C'est le squash & stretch discret que le §7 demande sur les
 * compteurs — discret, donc 4 % et pas 40 %.
 */
export function CountUp({
  to,
  from = 0,
  duration = 900,
  prefix = '',
  suffix = '',
  className = '',
  onDone,
}: {
  to: number
  from?: number
  duration?: number
  prefix?: string
  suffix?: string
  className?: string
  onDone?: () => void
}) {
  const reduced = useReducedMotion()
  const [value, setValue] = useState(reduced ? to : from)
  const [scale, setScale] = useState(1)
  const done = useRef(false)

  useEffect(() => {
    if (reduced) {
      setValue(to)
      onDone?.()
      return
    }

    done.current = false
    let raf = 0
    const start = performance.now()

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      // Puissance 4 : arrive vite, s'arrête longuement. Le nombre « atterrit ».
      const eased = 1 - Math.pow(1 - t, 4)

      setValue(Math.round(from + (to - from) * eased))
      // Le gonflement culmine au milieu de la course puis se résorbe.
      setScale(1 + 0.04 * Math.sin(Math.PI * t))

      if (t < 1) raf = requestAnimationFrame(tick)
      else if (!done.current) {
        done.current = true
        setScale(1)
        onDone?.()
      }
    }

    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [to, from, duration, reduced])

  return (
    <span
      className={`num ${className}`}
      style={{ display: 'inline-block', transform: `scale(${scale})`, willChange: 'transform' }}
    >
      {prefix}
      {value.toLocaleString('fr-FR')}
      {suffix}
    </span>
  )
}
