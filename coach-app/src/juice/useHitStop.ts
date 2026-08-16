import { useCallback, useState } from 'react'
import { useReducedMotion } from './useReducedMotion'

/** Arrêt sur image très bref, pour vendre un impact (SPEC §7, séquence 2).
 *
 * Le piège documenté par `game-feel` est de faire un hit-stop qui bloque
 * l'entrée. Ici il ne gèle rien du tout : il rend un drapeau que les éléments
 * *visuels* consultent pour suspendre leur transition. Un clic pendant le
 * hit-stop passe normalement.
 *
 * Durées très courtes — 60 à 120 ms. Au-delà on ne lit plus un impact mais une
 * saccade.
 */
export function useHitStop(): [boolean, (ms?: number) => void] {
  const [frozen, setFrozen] = useState(false)
  const reduced = useReducedMotion()

  const freeze = useCallback(
    (ms = 90) => {
      if (reduced) return
      setFrozen(true)
      window.setTimeout(() => setFrozen(false), ms)
    },
    [reduced],
  )

  return [frozen, freeze]
}
