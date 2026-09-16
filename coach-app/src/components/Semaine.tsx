import { useEffect, useState } from 'react'
import { api } from '../api'
import type { CreneauxPanel } from '../types'
import './Semaine.css'

const JOURS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'] as const

/** La semaine : quel projet, quel jour, quelle heure (§11.2, §11.11).
 *
 * Elle se **lit tous les jours** et ne s'**écrit que le dimanche**. C'est la
 * même raison qu'ailleurs dans le produit : ce qui se décide au calme tient, ce
 * qui se décide un soir de fatigue est exactement ce dont le dispositif
 * protège — déplacer mardi soir le rendez-vous de mardi soir, ce n'est pas
 * l'ajuster, c'est l'annuler avec une étape de plus.
 *
 * La lecture reste ouverte en semaine parce que c'est cette grille qui dit ce
 * que la journée demande. La cacher six jours sur sept reviendrait à cacher le
 * contrat qu'on est en train de tenir.
 */
export function Semaine() {
  const [panel, setPanel] = useState<CreneauxPanel | null>(null)
  const [erreur, setErreur] = useState('')
  const [ajout, setAjout] = useState<{ weekday: number } | null>(null)
  const [projet, setProjet] = useState<number | null>(null)
  const [heure, setHeure] = useState('20:30')
  const [busy, setBusy] = useState(false)

  async function charger() {
    try {
      setPanel(await api.creneaux())
    } catch (e) {
      setErreur(e instanceof Error ? e.message : 'Semaine illisible.')
    }
  }

  useEffect(() => {
    charger()
  }, [])

  if (!panel) return null

  const parJour = JOURS.map((_, weekday) =>
    panel.projets.flatMap((p) =>
      p.creneaux
        .filter((c) => c.weekday === weekday)
        .map((c) => ({ ...c, name: p.name, color: p.color, emblem: p.emblem })),
    ).sort((a, b) => a.heure.localeCompare(b.heure)),
  )

  async function poser(weekday: number) {
    if (!projet) return
    setBusy(true)
    setErreur('')
    try {
      await api.poserCreneau({ project_id: projet, weekday, heure })
      setAjout(null)
      await charger()
    } catch (e) {
      setErreur(e instanceof Error ? e.message : 'Créneau refusé.')
    } finally {
      setBusy(false)
    }
  }

  async function retirer(id: number) {
    setBusy(true)
    setErreur('')
    try {
      await api.retirerCreneau(id)
      await charger()
    } catch (e) {
      setErreur(e instanceof Error ? e.message : 'Retrait refusé.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="semaine">
      <h2 className="section-title display">Ta semaine</h2>
      <p className="section-hint">
        {panel.ouvert
          ? `C'est dimanche : la semaine se règle. Chaque rendez-vous demande ${panel.requis_minutes} min, et ce qui n'est pas fait à ${panel.heure_de_blocage}h ferme les réseaux.`
          : `${panel.motif} Prochain réglage dans ${panel.jours_avant_ouverture} jour(s).`}
      </p>

      {erreur && <p className="semaine__erreur">{erreur}</p>}

      <ol className="semaine__grille">
        {JOURS.map((nom, weekday) => (
          <li key={nom} className={`semaine__jour${parJour[weekday].length ? '' : ' semaine__jour--vide'}`}>
            <span className="semaine__nom label">{nom}</span>

            {parJour[weekday].map((c) => (
              <span
                key={c.id}
                className="semaine__creneau"
                style={{ ['--project' as string]: c.color }}
              >
                <span className="semaine__heure num">{c.heure}</span>
                <span className="semaine__projet">
                  {c.emblem} {c.name}
                </span>
                {panel.ouvert && (
                  <button
                    type="button"
                    className="semaine__retirer"
                    onClick={() => retirer(c.id)}
                    disabled={busy}
                    aria-label={`Retirer ${c.name} le ${nom}`}
                  >
                    ×
                  </button>
                )}
              </span>
            ))}

            {parJour[weekday].length === 0 && <span className="semaine__libre">libre</span>}

            {panel.ouvert &&
              (ajout?.weekday === weekday ? (
                <span className="semaine__ajout">
                  <select
                    value={projet ?? ''}
                    onChange={(e) => setProjet(Number(e.target.value))}
                    aria-label="Projet"
                  >
                    <option value="">Quel projet ?</option>
                    {panel.projets.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                  <input
                    type="time"
                    value={heure}
                    onChange={(e) => setHeure(e.target.value)}
                    aria-label="Heure"
                  />
                  <button type="button" onClick={() => poser(weekday)} disabled={busy || !projet}>
                    Poser
                  </button>
                  <button type="button" className="ghost" onClick={() => setAjout(null)}>
                    Annuler
                  </button>
                </span>
              ) : (
                <button
                  type="button"
                  className="semaine__plus ghost"
                  onClick={() => setAjout({ weekday })}
                >
                  + ajouter
                </button>
              ))}
          </li>
        ))}
      </ol>
    </section>
  )
}
