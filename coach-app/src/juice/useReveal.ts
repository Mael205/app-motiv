/** Le crochet React qui branche le mouvement d'entrée sur le cycle de vie.
 *
 * Séparé de `anim.ts` pour que celui-ci reste du DOM pur : c'est ce qui permet
 * de le tester sans monter un composant, et de l'appeler depuis un endroit qui
 * n'est pas React — la cérémonie de saison, par exemple.
 */

import { useEffect, useRef } from 'react'
import { inclinerAuPointeur, revelerAuDefilement, type Geste } from './anim'

/**
 * Révèle au défilement ce qui, dans le conteneur, correspond aux sélecteurs.
 *
 * La clé de l'objet est le geste, la valeur le sélecteur : `lever` pour les
 * cartes et les lignes, `devoiler` pour les titres, qui se découvrent de
 * gauche à droite comme un trait qu'on tire. Un seul crochet pour les deux,
 * parce qu'un élément ne peut porter qu'une `ref` — deux crochets voudraient
 * dire deux conteneurs.
 *
 * `pret` existe parce que les écrans chargent leurs données après leur premier
 * rendu : sans lui, on observerait un « Chargement… » et jamais les cartes qui
 * le remplacent. Passer `false` tant que les données manquent, `true` ensuite.
 */
export function useRevelation(
  selecteurs: Partial<Record<Geste, string>>,
  pret: boolean = true,
): React.RefObject<HTMLDivElement | null> {
  const boite = useRef<HTMLDivElement>(null)

  // Sérialisé plutôt que passé tel quel : un objet littéral écrit dans le JSX
  // est une nouvelle référence à chaque rendu, et relancerait l'observation
  // — donc recacherait tout — à chaque battement de l'horloge de l'accueil.
  const cle = JSON.stringify(selecteurs)

  useEffect(() => {
    if (!pret || !boite.current) return
    const racine = boite.current
    const arrets = Object.entries(JSON.parse(cle) as Record<Geste, string>).map(
      ([geste, selecteur]) =>
        revelerAuDefilement(
          Array.from(racine.querySelectorAll<HTMLElement>(selecteur)),
          geste as Geste,
        ),
    )
    return () => arrets.forEach((arret) => arret())
  }, [cle, pret])

  return boite
}

/**
 * Rend inclinables toutes les surfaces du conteneur qui correspondent au
 * sélecteur.
 *
 * Un crochet séparé de `useRevelation` parce que les deux ne visent pas les
 * mêmes choses : on révèle une ligne de liste, on n'incline qu'une carte —
 * quelque chose d'assez grand pour que huit degrés se voient, et d'assez épais
 * pour que le relief ait un sens.
 *
 * Il se réattache quand `signature` change : les cartes de projet sont
 * remplacées à chaque rechargement, et des écouteurs posés sur des nœuds
 * détachés n'inclineraient plus rien.
 */
export function useInclinaison(
  conteneur: React.RefObject<HTMLElement | null>,
  selecteur: string,
  signature: unknown = null,
): void {
  useEffect(() => {
    const racine = conteneur.current
    if (!racine) return
    const arrets = Array.from(racine.querySelectorAll<HTMLElement>(selecteur)).map((carte) =>
      inclinerAuPointeur(carte),
    )
    return () => arrets.forEach((arret) => arret())
  }, [conteneur, selecteur, signature])
}
