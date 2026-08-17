import { useEffect, useState } from 'react'
import { api } from '../api'
import type { WeeklyPanel } from '../types'
import './BuddyReport.css'

/** Le bilan envoyé à un ami (§4.7).
 *
 * Deux choses à montrer, et une seule action possible.
 *
 * **Ce qui est parti, mot pour mot.** Un bilan recalculé à l'affichage ne dirait
 * pas ce que l'ami a lu, et c'est justement la question quand plus rien n'est
 * lu depuis trois semaines.
 *
 * **L'arrêt, qui coûte 24 heures.** C'est le seul mécanisme volontairement
 * difficile à désarmer du produit : le bouton existe, il est visible, et il ne
 * coupe rien avant le lendemain. Annuler, en revanche, est immédiat — seul
 * l'arrêt coûte du temps. Cacher le bouton serait pire que l'afficher : un
 * mécanisme qu'on ne sait pas comment lever se contourne en désinstallant.
 */
export function BuddyReport() {
  const [panel, setPanel] = useState<WeeklyPanel | null>(null)
  const [ouvert, setOuvert] = useState<string | null>(null)

  useEffect(() => {
    api.weekly().then(setPanel).catch(() => setPanel(null))
  }, [])

  if (!panel) return null

  if (!panel.destinataire_configure) {
    return (
      <section className="buddy">
        <h3 className="buddy__titre label">Bilan hebdomadaire</h3>
        <p className="buddy__vide">
          Aucun destinataire. C'est le seul point d'appui extérieur du système : sans lui, tout ce
          qui tient le cadre vient de toi, et c'est précisément ce qui n'a jamais marché.
        </p>
      </section>
    )
  }

  const alerte = panel.non_lus >= panel.seuil_non_lus

  async function demanderArret() {
    await api.requestWeeklyStop()
    setPanel(await api.weekly())
  }

  async function annulerArret() {
    await api.cancelWeeklyStop()
    setPanel(await api.weekly())
  }

  return (
    <section className="buddy">
      <h3 className="buddy__titre label">Bilan hebdomadaire</h3>

      {alerte && (
        <p className="buddy__alerte">
          {panel.non_lus} bilans partis sans être lus. Un contrôleur qui ne regarde pas ne contrôle
          rien — change de destinataire.
        </p>
      )}

      {panel.desactivation_effective_le && (
        <div className="buddy__arret">
          <p>
            Arrêt demandé. Le bilan part encore jusqu'au{' '}
            <span className="num">
              {new Date(panel.desactivation_effective_le).toLocaleString('fr-FR', {
                weekday: 'long',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
            .
          </p>
          <button type="button" className="buddy__annuler" onClick={annulerArret}>
            Annuler l'arrêt
          </button>
        </div>
      )}

      <ul className="buddy__liste">
        {panel.rapports.map((rapport) => (
          <li key={rapport.week_start}>
            <button
              type="button"
              className="buddy__ligne"
              onClick={() => setOuvert(ouvert === rapport.week_start ? null : rapport.week_start)}
            >
              <span className="buddy__semaine num">
                {new Date(rapport.week_start).toLocaleDateString('fr-FR', {
                  day: 'numeric',
                  month: 'short',
                })}
              </span>
              <span className={`buddy__etat${rapport.read_at ? ' buddy__etat--lu' : ''}`}>
                {!rapport.sent_at ? 'non envoyé' : rapport.read_at ? 'lu' : 'non lu'}
              </span>
            </button>
            {ouvert === rapport.week_start && <pre className="buddy__corps">{rapport.body}</pre>}
          </li>
        ))}
      </ul>

      {panel.actif && !panel.desactivation_effective_le && (
        <button type="button" className="buddy__stop" onClick={demanderArret}>
          Arrêter le bilan (effectif dans 24 h)
        </button>
      )}
    </section>
  )
}
