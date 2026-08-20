/** Chaque saison a son identité complète — sceau, frise, atmosphère.
 *
 * Le défaut que ce test empêche est le plus discret de tous : une saison sans
 * sceau tombe sur le glyphe de repli, une saison sans frise sur un trait droit,
 * une saison sans atmosphère sur un fond nu. Rien ne casse, rien n'avertit —
 * la saison est simplement plus pauvre que les autres, et on ne s'en aperçoit
 * qu'en la vivant, c'est-à-dire un mois plus tard.
 *
 * C'est déjà arrivé : l'écran d'ouverture passait le **nom** de la saison à
 * l'emblème, qui attend une **clé**, et il a donc dessiné le glyphe de repli
 * sur toutes les saisons depuis qu'il existe.
 *
 * La liste des clés est recopiée du serveur (`forge/rules/seasons.py`) et non
 * importée : le front n'a pas accès au Python, et une liste qui diverge est
 * précisément ce que ce test doit faire échouer.
 */

import { describe, expect, it } from 'vitest'
import { AMBIANCES, MOTIFS, SIGILS } from './SeasonSigil'

const CLES_DE_SAISON = [
  // Voie des Cimes — du réveil à l'Empyrée.
  'eveil', 'aube_rouge', 'porte_ivoire', 'sanctuaire', 'elysion', 'ascension',
  'valhalla', 'ragnarok', 'couronne_solaire', 'heavens_paradise', 'apotheose', 'empyree',
  // Voie des Braises — la chute, le feu, la reforge.
  'chute', 'nadir', 'styx', 'purgatoire', 'solstice_noir', 'cendres',
  'hellfest', 'inferno', 'tonnerre', 'dernier_rempart', 'derniere_forge', 'phenix',
]

describe('l’identité visuelle des saisons', () => {
  it('couvre les vingt-quatre saisons de la trame', () => {
    expect(CLES_DE_SAISON).toHaveLength(24)
    expect(new Set(CLES_DE_SAISON).size).toBe(24)
  })

  it.each(CLES_DE_SAISON)('« %s » a son sceau dessiné', (cle) => {
    expect(SIGILS[cle], `pas de sceau pour ${cle} : elle tomberait sur le glyphe de repli`).toBeTypeOf(
      'function',
    )
  })

  it.each(CLES_DE_SAISON)('« %s » a sa frise', (cle) => {
    expect(MOTIFS[cle], `pas de frise pour ${cle} : elle tomberait sur un trait droit`).toBeTruthy()
  })

  /* Les atmosphères sont neuf familles, pas vingt-quatre dessins : ce qu'on
     vérifie ici est qu'aucune n'a été nommée côté serveur sans être dessinée
     côté client — une `ambiance` inconnue rend un bandeau nu. */
  it('dessine les neuf atmosphères que le serveur sait nommer', () => {
    const attendues = ['lave', 'forge', 'ailes', 'or', 'aurore', 'vitrail', 'orage', 'abysse', 'cendre']
    for (const nom of attendues) {
      expect(AMBIANCES, `atmosphère « ${nom} » nommée par le serveur mais non dessinée`).toContain(nom)
    }
  })
})
