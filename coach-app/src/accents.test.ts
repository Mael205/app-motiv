import { describe, it, expect, beforeEach } from 'vitest'
import { applySeasonTheme } from './accents'
import type { HomeState } from './types'

/* Ce que ces tests gardent : la séparation des deux accents (§12.6).
 *
 * Le défaut qu'ils auraient attrapé existait vraiment. La première version du
 * repli était écrite en CSS — `--perso: var(--accent)` sur :root — et elle
 * compilait, passait `tsc` et passait le lint. Elle était fausse : l'accent de
 * saison est posé en style inline sur le <body>, donc la substitution se faisait
 * contre l'or par défaut de :root. Seule une capture d'écran l'a montré.
 */

const WACKEN = '#8FD14F'
const BRAISE = '#E8843D'

function accueil(patch: Record<string, unknown> = {}): HomeState {
  return {
    season: { accent: WACKEN },
    cosmetics: {},
    streak: { sanction_level: 0 },
    validated_today: true,
    ...patch,
  } as unknown as HomeState
}

const lu = (nom: string) => document.body.style.getPropertyValue(nom)

beforeEach(() => {
  document.body.removeAttribute('style')
  document.body.removeAttribute('class')
})

describe("l'accent de saison", () => {
  it('peint --accent', () => {
    applySeasonTheme(accueil())
    expect(lu('--accent')).toBe(WACKEN)
  })

  it("se retire quand il n'y a plus de saison", () => {
    applySeasonTheme(accueil())
    applySeasonTheme(accueil({ season: null }))
    expect(lu('--accent')).toBe('')
  })
})

describe('le thème équipé', () => {
  it('peint --perso sans toucher à --accent', () => {
    applySeasonTheme(accueil({ cosmetics: { theme: { value: BRAISE } } }))

    // Le cœur de la séparation : les deux couleurs coexistent. Avant, le thème
    // écrasait --accent et la saison perdait sa teinte pendant vingt-huit jours.
    expect(lu('--perso')).toBe(BRAISE)
    expect(lu('--accent')).toBe(WACKEN)
  })

  it("retombe sur l'accent de saison quand rien n'est équipé", () => {
    applySeasonTheme(accueil())
    expect(lu('--perso')).toBe(WACKEN)
  })

  it('ne laisse pas sa couleur derrière lui après un retrait', () => {
    applySeasonTheme(accueil({ cosmetics: { theme: { value: BRAISE } } }))
    expect(lu('--perso')).toBe(BRAISE)

    // Le bouton « Retirer » passe exactement par là. Sans remise à jour, la
    // fiche restait orange sur une saison verte jusqu'au rechargement.
    applySeasonTheme(accueil())
    expect(lu('--perso')).toBe(WACKEN)
  })

  it('reste stable si on la réapplique — elle tourne toutes les dix secondes', () => {
    const etat = accueil({ cosmetics: { theme: { value: BRAISE } } })
    applySeasonTheme(etat)
    applySeasonTheme(etat)
    applySeasonTheme(etat)

    expect(lu('--perso')).toBe(BRAISE)
    expect(lu('--accent')).toBe(WACKEN)
  })
})

describe('les emplacements portés par le document', () => {
  it('exposent le cadre et l\'effet de fin, et les vident sinon', () => {
    applySeasonTheme(
      accueil({ cosmetics: { frame: { value: 'givre' }, finisher: { value: 'eclat' } } }),
    )
    expect(document.body.dataset.frame).toBe('givre')
    expect(document.body.dataset.finisher).toBe('eclat')

    applySeasonTheme(accueil())
    expect(document.body.dataset.frame).toBe('')
    expect(document.body.dataset.finisher).toBe('')
  })
})

describe('le mode terne', () => {
  it("s'allume sous sanction tant que la journée n'est pas validée", () => {
    applySeasonTheme(accueil({ streak: { sanction_level: 1 }, validated_today: false }))
    expect(document.body.classList.contains('terne')).toBe(true)
  })

  it("s'éteint dès que la journée est validée, même sous sanction", () => {
    applySeasonTheme(accueil({ streak: { sanction_level: 2 }, validated_today: true }))
    expect(document.body.classList.contains('terne')).toBe(false)
  })

  it('ne touche pas une interface sans sanction', () => {
    applySeasonTheme(accueil({ streak: { sanction_level: 0 }, validated_today: false }))
    expect(document.body.classList.contains('terne')).toBe(false)
  })
})
