import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Briefing, Proposal } from '../types'

/** Va chercher le briefing du §5.1 **après** que l'écran est déjà utilisable.
 *
 * L'ordre est le point important. `/home` rend la proposition déterministe tout
 * de suite ; le briefing part ensuite, en fond, et remplace le bloc quand il
 * arrive. Un appel de modèle avec un effort élevé peut prendre vingt secondes —
 * les attendre derrière un écran de chargement transformerait le moment où on
 * décide de s'y mettre en moment où on attend, et c'est exactement là qu'on
 * ouvre autre chose.
 *
 * Conséquence assumée : le bloc peut changer sous les yeux. C'est préférable à
 * l'inverse, et c'est pour ça que l'origine de la décision est affichée.
 *
 * Aucune erreur n'est remontée. Le serveur ne renvoie jamais d'échec pour une
 * raison d'IA — il rend le repli et dit pourquoi dans `ai_note`. Si l'appel
 * échoue quand même (réseau coupé), on garde simplement ce qui est à l'écran.
 */
export function useBriefing(fallback: Proposal | null, key: unknown): Briefing | null {
  const [briefing, setBriefing] = useState<Briefing | null>(null)

  useEffect(() => {
    if (!fallback) return
    let vivant = true

    setBriefing(null)
    api
      .briefing()
      .then((recu) => {
        if (vivant) setBriefing(recu)
      })
      .catch(() => {
        /* on garde la proposition déterministe déjà affichée */
      })

    return () => {
      vivant = false
    }
    // `key` change quand la soirée change d'état (session finie, jour tourné) :
    // c'est le seul moment où redemander un briefing a un sens.
  }, [key, Boolean(fallback)])

  return briefing
}
