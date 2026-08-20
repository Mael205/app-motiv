/** Ce que le client d'API fait d'une panne de réseau.
 *
 * Une requête qui n'atteint pas le serveur ne lève pas une `ApiError` : le
 * navigateur lève un `TypeError` dont le message est « Failed to fetch ». Il
 * remontait tel quel jusqu'à l'écran — c'était la seule phrase de
 * l'application que personne n'avait écrite, et la seule en anglais.
 *
 * Le statut 0 est ce qui la distingue d'une réponse : le serveur n'a pas
 * refusé, il n'a pas été joint. Un écran peut donc en dire quelque chose de
 * différent d'un 500, ce que le message seul ne permettait pas.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('le client d’API face au réseau', () => {
  it('traduit une panne de réseau en ApiError française, sans « Failed to fetch »', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new TypeError('Failed to fetch')),
    )

    const echec = await api.journal().catch((e: unknown) => e)

    expect(echec).toBeInstanceOf(ApiError)
    expect((echec as ApiError).status).toBe(0)
    expect((echec as ApiError).message).toMatch(/serveur ne répond pas/i)
    expect((echec as ApiError).message).not.toMatch(/failed to fetch/i)
  })

  it('garde le message du serveur quand celui-ci répond en erreur', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'Trois projets actifs, pas quatre.' }),
      }),
    )

    const echec = await api.journal().catch((e: unknown) => e)

    expect(echec).toBeInstanceOf(ApiError)
    expect((echec as ApiError).status).toBe(400)
    expect((echec as ApiError).message).toBe('Trois projets actifs, pas quatre.')
  })
})
