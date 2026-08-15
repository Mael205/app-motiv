import { useEffect, useState } from 'react'

/** Horloge locale, cantonnée aux composants qui en ont réellement besoin.
 *
 * Elle vivait dans `App`, ce qui re-rendait tout l'arbre chaque seconde — y
 * compris le rang et ses ailes, dont le SVG était reconstruit soixante fois
 * par minute. Seule la jauge du soir a besoin de la seconde qui passe.
 */
export function useNow(intervalMs = 1000): Date {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), intervalMs)
    return () => clearInterval(id)
  }, [intervalMs])

  return now
}
