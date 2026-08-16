/** Les courbes du §7. Aucune linéaire sauf le curseur de temps.
 *
 * Les noms disent l'usage, pas la forme mathématique : au moment de choisir,
 * la question est « ça entre ou ça encaisse ? », jamais « quel est le second
 * point de contrôle ? ».
 */
export const EASE = {
  /** Entrées, apparitions. Décélération franche. */
  enter: [0.22, 1, 0.36, 1] as const,
  /** Déplacements, panneaux, tiroirs. */
  move: [0.25, 1, 0.5, 1] as const,
  /** Le « pop » : dépasse la cible puis revient. Réservé aux compteurs et impacts. */
  pop: [0.34, 1.56, 0.64, 1] as const,
  /** L'impact : très rapide au début, s'écrase à la fin. */
  slam: [0.16, 1.2, 0.3, 1] as const,
} as const
