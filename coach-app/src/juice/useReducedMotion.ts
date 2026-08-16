import { useEffect, useState } from 'react'

/** Respecte `prefers-reduced-motion` (SPEC §7), et réagit à son changement.
 *
 * Lu en direct plutôt que capturé au montage : quelqu'un qui active le réglage
 * système pendant une nausée ne doit pas avoir à recharger l'app pour que ça
 * prenne effet.
 */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches,
  )

  useEffect(() => {
    const mq = matchMedia('(prefers-reduced-motion: reduce)')
    const onChange = () => setReduced(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  return reduced
}
