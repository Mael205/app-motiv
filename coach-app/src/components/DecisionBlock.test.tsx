/** Ouvrir le bloc suivant du parcours.
 *
 * Ce test existe parce que la fonctionnalité était **à moitié écrite** et que
 * rien ne le disait à l'usage. Le bouton était dessiné, la route serveur
 * existait, le client d'API aussi — mais le gestionnaire `ouvrirLeBloc` et son
 * état `ouverture` n'avaient jamais été écrits. Le seul symptôme était deux
 * erreurs de compilation, donc un `npm run build` en échec : l'application
 * entière était indéployable à cause d'un bouton que personne n'avait fini.
 *
 * C'est le moment le plus fragile du produit — la roadmap vient de se vider,
 * et sans ce bouton le soir n'a plus rien à proposer.
 */

import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ApiError, api } from '../api'
import type { Proposal } from '../types'
import { DecisionBlock } from './DecisionBlock'

/** Une roadmap vide, avec une suite de parcours disponible.
 *
 * `step: null` **est** le sujet du test : c'est ce qui fait basculer l'écran
 * dans son état « plus rien à faire », le seul où la question du bloc suivant
 * se pose. Le type est écrit en entier plutôt qu'approché — `tsc` refuse un
 * fixture partiel, et c'est lui qui garde ces tests honnêtes : Vitest, seul,
 * les aurait laissés passer avec un objet à moitié faux. */
const ROADMAP_VIDE: Proposal = {
  track: 'atelier',
  project: { id: 7, name: 'Outils Dofus 3', color: '#4fc4b4', emblem: '◆', completion: 1 },
  minutes: 25,
  creneau: null,
  step: null,
  amorce: '',
  reason: '',
  next_bloc: { id: 42, name: 'Bloc 3 — interface de consultation', resource: 'la doc Qt' },
}

describe('quand la roadmap est vide et que le parcours a une suite', () => {
  it('ouvre le bloc suivant et prévient le parent', async () => {
    const ouvrir = vi.spyOn(api, 'openNextBloc').mockResolvedValue({
      bloc: { id: 42, name: 'Bloc 3' },
      created: 4,
      detail: 'quatre étapes écrites',
    })
    const onStarted = vi.fn()
    render(<DecisionBlock proposal={ROADMAP_VIDE} onStarted={onStarted} />)

    await userEvent.click(screen.getByRole('button', { name: /ouvrir ce bloc/i }))

    await waitFor(() => expect(ouvrir).toHaveBeenCalledWith(7))
    // Le rechargement vient du parent : c'est lui qui tient l'état du soir, et
    // la roadmap fraîche change la proposition entière.
    await waitFor(() => expect(onStarted).toHaveBeenCalledTimes(1))
  })

  it("dit ce qui s'est passé si le serveur refuse, au lieu de se taire", async () => {
    vi.spyOn(api, 'openNextBloc').mockRejectedValue(
      new ApiError('Le bloc courant a encore des étapes ouvertes.', 409),
    )
    render(<DecisionBlock proposal={ROADMAP_VIDE} onStarted={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: /ouvrir ce bloc/i }))

    expect(await screen.findByText(/encore des étapes ouvertes/i)).toBeInTheDocument()
  })

  it('ne propose rien à ouvrir quand le parcours est terminé', () => {
    render(
      <DecisionBlock proposal={{ ...ROADMAP_VIDE, next_bloc: null }} onStarted={vi.fn()} />,
    )

    expect(screen.queryByRole('button', { name: /ouvrir ce bloc/i })).not.toBeInTheDocument()
    expect(screen.getByText(/écris le prochain jalon/i)).toBeInTheDocument()
  })
})
