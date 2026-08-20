/** Ce que les écrans font quand le serveur ne répond pas.
 *
 * Ces tests existent parce que ces cas-là étaient tous cassés, et qu'aucun
 * d'eux ne se voyait : mesuré le 20 août 2026 en coupant l'API, Projets et
 * Journal restaient sur « Chargement… » **indéfiniment**, sans message, sans
 * bouton, en rejetant deux promesses dans le vide. Personnage, lui, affichait
 * bien une erreur mais ne s'en relevait jamais — son `load` ne remettait pas
 * le message à zéro, si bien qu'un « Réessayer » qui aboutissait laissait
 * l'écran en panne devant des données pourtant chargées.
 *
 * Aucun de ces trois défauts n'aurait survécu à une seule assertion. C'est
 * pourquoi la panne se teste ici en premier, avant le cas passant : c'est le
 * chemin que personne ne regarde.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ApiError, api } from '../api'
import type { ProgressionPanel, TreeShape } from '../types'
import { Projects } from './Projects'
import { Journal } from './Journal'
import { Character } from './Character'

const SHAPE: TreeShape = {
  total_minutes: 0,
  branches_actives: 0,
  dominante: null,
  a_l_arret: [],
  concentration: 0,
}

const PANNE = () => Promise.reject(new ApiError('Le serveur ne répond pas. Vérifie la connexion.', 0))

/* Un panneau vide mais **conforme au type**. Les champs imbriqués comptent :
   la première version de ce fixture donnait `relics: []` là où l'écran lit
   `panel.relics.relics`, et le test passait au vert pendant que React levait
   une exception non rattrapée à côté. Un fixture approximatif ne teste rien —
   il déplace juste l'endroit où ça casse. */
const PROGRESSION: ProgressionPanel = {
  showcase_locked: false,
  skills: { branches: [], shape: SHAPE, tiers: [] },
  momentum: {
    level: 0,
    percent: 0,
    multiplier: 1,
    label: 'Éteinte',
    detail: 'Rien depuis un moment.',
    days_worked: 0,
    cooling: false,
    days: [],
  },
  relics: { max: 3, equipped_count: 0, relics: [], bonuses: {} },
  collection: {
    slots: {},
    forge_open: false,
    owned: 0,
    total: 0,
    shards: 0,
    equipped: {},
  },
  pending_cards: [],
}

/** Monte l'écran, attend que sa première requête ait été jouée. */
async function attendreLaPanne() {
  expect(await screen.findByRole('alert')).toHaveTextContent(/serveur ne répond pas/i)
  return screen.getByRole('button', { name: /réessayer/i })
}

describe('Projets — quand le serveur ne répond pas', () => {
  beforeEach(() => {
    vi.spyOn(api, 'fridge').mockResolvedValue([])
  })

  it('affiche la panne au lieu de rester sur « Chargement… »', async () => {
    vi.spyOn(api, 'projects').mockImplementation(PANNE)
    render(<Projects onChanged={() => {}} />)

    await attendreLaPanne()
    expect(screen.queryByText('Chargement…')).not.toBeInTheDocument()
  })

  it('se relève quand « Réessayer » aboutit', async () => {
    const projets = vi.spyOn(api, 'projects').mockImplementationOnce(PANNE).mockResolvedValue([])
    render(<Projects onChanged={() => {}} />)

    await userEvent.click(await attendreLaPanne())

    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    expect(screen.getByText(/les trois slots/i)).toBeInTheDocument()
    expect(projets).toHaveBeenCalledTimes(2)
  })
})

describe('Journal — quand le serveur ne répond pas', () => {
  it('affiche la panne au lieu de rester sur « Chargement… »', async () => {
    vi.spyOn(api, 'journal').mockImplementation(PANNE)
    render(<Journal />)

    await attendreLaPanne()
    expect(screen.queryByText('Chargement…')).not.toBeInTheDocument()
  })

  it('se relève quand « Réessayer » aboutit', async () => {
    vi.spyOn(api, 'journal').mockImplementationOnce(PANNE).mockResolvedValue([])
    render(<Journal />)

    await userEvent.click(await attendreLaPanne())

    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  })
})

describe('Personnage — quand le serveur ne répond pas', () => {
  it('affiche la panne', async () => {
    vi.spyOn(api, 'progression').mockImplementation(PANNE)
    render(<Character />)

    await attendreLaPanne()
  })

  /* Le défaut précis : `load` n'appelait jamais `setError('')`. La requête de
     reprise réussissait, les données arrivaient, et l'écran continuait
     d'afficher l'ancien message parce que `if (error)` passe avant tout. */
  it("efface le message quand la reprise réussit, et n'y reste pas coincé", async () => {
    vi.spyOn(api, 'progression')
      .mockImplementationOnce(PANNE)
      .mockResolvedValue(PROGRESSION)
    render(<Character />)

    await userEvent.click(await attendreLaPanne())

    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  })
})
