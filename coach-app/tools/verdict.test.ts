import { describe, it, expect } from 'vitest'
// @ts-expect-error — module CommonJS sans typage, volontairement : les outils de
// mesure sont en .cjs et n'ont pas de raison de migrer pour un test.
import { verdictAudit, verdictFold, verdictSon } from './verdict.cjs'

/* Ce que ces tests gardent : la capacité des outils à **échouer**.
 *
 * Avant, les trois scripts imprimaient du JSON et sortaient en 0 quoi qu'ils
 * trouvent. On ne pouvait donc pas savoir s'ils attrapaient quoi que ce soit
 * sans fabriquer un vrai défaut dans l'application — ce que personne ne fait.
 * Le cas qui échoue est le seul des deux qui compte, et c'est celui qui n'avait
 * jamais été vérifié.
 */

describe("l'audit visuel", () => {
  it('passe sur un rapport propre', () => {
    const v = verdictAudit([{ taille: 'phone', tab: 'Ce soir', overflow: [], overlap: [] }])
    expect(v.ok).toBe(true)
    expect(v.total).toBe(0)
  })

  it('échoue sur un débordement', () => {
    const v = verdictAudit([{ overflow: [{ sel: '.hud', left: 0, right: 900, vw: 390 }] }])
    expect(v.ok).toBe(false)
    expect(v.total).toBe(1)
    expect(v.message).toContain('ECHOUE')
  })

  it('additionne les familles sur toutes les combinaisons', () => {
    const v = verdictAudit([
      { overflow: [1, 2], overlap: [3] },
      { invisible: [4], layout: [5, 6] },
    ])
    expect(v.total).toBe(6)
    expect(v.compte).toEqual({ overflow: 2, overlap: 1, invisible: 1, layout: 2 })
  })

  it('compte une erreur de console comme un défaut', () => {
    // Une exception au chargement casse l'écran sans le déformer : aucune des
    // quatre familles géométriques ne la verrait.
    const v = verdictAudit([{ console: ['TypeError: undefined'] }])
    expect(v.ok).toBe(false)
  })

  it("ignore `animations`, qui liste ce qui existe et non ce qui est cassé", () => {
    const v = verdictAudit([{ animations: [{ name: 'pulse', state: 'running' }] }])
    expect(v.ok).toBe(true)
  })

  it('supporte un rapport vide sans exploser', () => {
    expect(verdictAudit([]).ok).toBe(true)
    expect(verdictAudit(undefined).ok).toBe(true)
  })
})

describe('la ligne de flottaison', () => {
  it('passe quand le bouton est visible partout', () => {
    const v = verdictFold([
      { taille: 'phone', visible: true, marge: 80 },
      { taille: 'laptop', visible: true, marge: 368 },
    ])
    expect(v.ok).toBe(true)
  })

  it('échoue dès une seule taille où il passe dessous', () => {
    // Le défaut que cet outil existe pour attraper, et qui s'est déjà produit
    // deux fois sur téléphone.
    const v = verdictFold([
      { taille: 'phone', visible: false, marge: -42 },
      { taille: 'laptop', visible: true, marge: 368 },
    ])
    expect(v.ok).toBe(false)
    expect(v.message).toContain('phone')
    expect(v.message).toContain('-42')
  })
})

describe('le son', () => {
  it('passe quand la coupure est nette et rien n’est muet', () => {
    const v = verdictSon({ 'Entrée en session': 6, 'Carte Légendaire': 15, 'coupé': 0 })
    expect(v.ok).toBe(true)
  })

  it('échoue si la coupure laisse passer des voix', () => {
    const v = verdictSon({ 'Entrée en session': 6, 'coupé': 3 })
    expect(v.ok).toBe(false)
    expect(v.message).toContain('3 voix')
  })

  it('échoue sur une séquence muette', () => {
    // Zéro voix programmée : le son est absent, pas seulement inaudible sur la
    // machine du jour.
    const v = verdictSon({ 'Mort du boss': 0, 'coupé': 0 })
    expect(v.ok).toBe(false)
    expect(v.message).toContain('Mort du boss')
  })
})
