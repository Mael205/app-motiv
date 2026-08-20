import { describe, expect, test } from 'vitest'
import { grouper, isoDans } from './ponctuels'
import type { PonctuelEntry } from '../types'

/* Ce qui est testé ici est ce qui casse en silence : un groupe qui avale une
 * ligne, et une date décalée d'un jour. Ni l'un ni l'autre ne lève d'erreur —
 * ils affichent simplement la mauvaise chose, au moment où l'on compte dessus.
 */

function ligne(p: Partial<PonctuelEntry>): PonctuelEntry {
  return {
    id: 1,
    label: 'Commander la carte mère',
    due_on: null,
    done: false,
    late: false,
    due_today: false,
    ...p,
  }
}

describe('les groupes de ponctuels', () => {
  test('classent dans l’ordre où ça presse', () => {
    const groupes = grouper([
      ligne({ id: 1 }),
      ligne({ id: 2, due_on: '2026-08-25' }),
      ligne({ id: 3, due_on: '2026-08-19', late: true }),
      ligne({ id: 4, due_on: '2026-08-20', due_today: true }),
    ])
    expect(groupes.map((g) => g.titre)).toEqual([
      'En retard',
      "Aujourd'hui",
      'Plus tard',
      'Sans date',
    ])
  })

  test('ne rendent aucun groupe vide', () => {
    const groupes = grouper([ligne({ id: 1 })])
    expect(groupes).toHaveLength(1)
    expect(groupes[0].titre).toBe('Sans date')
  })

  test('une ligne faite ne reste pas « en retard »', () => {
    // Le serveur laisse `late` à faux dès que c'est fait, mais la garde est
    // ici aussi : une course faite en retard ne doit pas continuer à presser.
    const groupes = grouper([ligne({ id: 1, done: true, late: true, due_on: '2026-08-01' })])
    expect(groupes.map((g) => g.titre)).toEqual(['Faites'])
  })

  test('gardent l’ordre du serveur à l’intérieur d’un groupe', () => {
    const groupes = grouper([
      ligne({ id: 7, due_on: '2026-08-22' }),
      ligne({ id: 3, due_on: '2026-08-30' }),
    ])
    expect(groupes[0].lignes.map((l) => l.id)).toEqual([7, 3])
  })
})

describe('les raccourcis d’échéance', () => {
  test('« demain » est bien le lendemain local', () => {
    expect(isoDans(1, new Date(2026, 7, 20, 10, 0))).toBe('2026-08-21')
  })

  test('ne basculent pas en UTC le soir', () => {
    // 23h à Paris est déjà le lendemain en UTC : `toISOString` rendrait le 21
    // pour « aujourd'hui », et la course serait notée pour demain.
    expect(isoDans(0, new Date(2026, 7, 20, 23, 30))).toBe('2026-08-20')
  })

  test('passent le changement de mois', () => {
    expect(isoDans(7, new Date(2026, 7, 28, 9, 0))).toBe('2026-09-04')
  })
})
