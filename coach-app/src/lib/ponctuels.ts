import type { PonctuelEntry } from '../types'

/** La logique de la liste des ponctuels, séparée de son rendu.
 *
 * Elle vit ici pour être testable sans monter un composant : ce sont des règles
 * de tri et de dates, et une règle de date se casse silencieusement — un décalage
 * d'un jour ne lève aucune erreur, il affiche simplement la mauvaise chose.
 */

export const GROUPES = ['En retard', "Aujourd'hui", 'Plus tard', 'Sans date', 'Faites'] as const

export type Groupe = { titre: string; lignes: PonctuelEntry[] }

/** Quatre groupes plus les faites, dans l'ordre où ils pressent.
 *
 * **L'ordre à l'intérieur d'un groupe reste celui du serveur**, et c'est la
 * règle importante : lui seul sait quel jour il est pour le coach, dont la
 * journée bascule à 4h. Un tri refait ici se tromperait toutes les nuits entre
 * minuit et la bascule — de même que `late` et `due_today` sont calculés côté
 * serveur et jamais recalculés à partir d'un `new Date()`.
 *
 * Les groupes vides ne sortent pas : un intertitre au-dessus de rien est un
 * intertitre qui apprend à sauter les intertitres.
 */
export function grouper(items: PonctuelEntry[]): Groupe[] {
  const par: Record<string, PonctuelEntry[]> = Object.fromEntries(GROUPES.map((g) => [g, []]))

  for (const item of items) {
    if (item.done) par['Faites'].push(item)
    else if (item.late) par['En retard'].push(item)
    else if (item.due_today) par["Aujourd'hui"].push(item)
    else if (item.due_on) par['Plus tard'].push(item)
    else par['Sans date'].push(item)
  }

  return GROUPES.filter((titre) => par[titre].length > 0).map((titre) => ({
    titre,
    lignes: par[titre],
  }))
}

/** La date ISO locale dans `jours` jours.
 *
 * Construite champ par champ et non via `toISOString`, qui convertit en UTC :
 * un raccourci « demain » cliqué à 23h en France rendrait aujourd'hui.
 */
export function isoDans(jours: number, depuis: Date = new Date()): string {
  const d = new Date(depuis)
  d.setDate(d.getDate() + jours)
  const mois = String(d.getMonth() + 1).padStart(2, '0')
  const jour = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mois}-${jour}`
}

/** Les raccourcis d'échéance. Trois, pas dix : au-delà, choisir prend plus de
 *  temps que taper une date. */
export const RACCOURCIS = [
  { label: "aujourd'hui", jours: 0 },
  { label: 'demain', jours: 1 },
  { label: 'dans 7 jours', jours: 7 },
] as const
