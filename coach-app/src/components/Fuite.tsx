import { useEffect, useState } from 'react'
import { api } from '../api'
import type { RapportDeFuite } from '../types'
import './Fuite.css'

/** Le rapport de fuite de temps (§13.2).
 *
 * Replié par défaut, et ce n'est pas de la place gagnée : le §13.2 dit que le
 * but est de **trouver l'heure charnière, pas de culpabiliser sur un total**.
 * L'heure tient sur une ligne, elle est visible tout de suite, et c'est la seule
 * chose sur laquelle on peut agir dès le lendemain. L'histogramme est là pour
 * qui veut vérifier, pas pour être regardé chaque soir.
 *
 * Le coût est affiché en unités du système — sessions, points de vie du boss.
 * Ni « perdu », ni « gaspillé » : le §17 interdit le score de productivité, et
 * un taux de change n'en est pas un.
 */
export function Fuite() {
  const [rapport, setRapport] = useState<RapportDeFuite | null>(null)
  const [ouvert, setOuvert] = useState(false)

  useEffect(() => {
    api.leak().then(setRapport).catch(() => setRapport(null))
  }, [])

  if (!rapport || (rapport.tranches.length === 0 && !rapport.sans_horodatage)) return null

  const sommet = Math.max(1, ...rapport.tranches.map((t) => t.minutes))

  return (
    <section className="fuite">
      <button className="fuite__entete" onClick={() => setOuvert((o) => !o)}>
        <span className="label">Où part le temps</span>
        <span className="fuite__resume">
          {rapport.charniere
            ? `ça commence vers ${rapport.charniere.libelle}`
            : 'pas encore d’heure nette'}
        </span>
      </button>

      {ouvert && (
        <div className="fuite__detail">
          <p className="fuite__cout">{rapport.cout_semaine.phrase}, cette semaine.</p>

          <div className="fuite__histo" role="img" aria-label="Scroll par tranche de 30 minutes">
            {rapport.tranches.map((tranche, rang) => (
              <div
                key={tranche.debut}
                className="fuite__colonne"
                style={{ ['--rang' as string]: rang }}
              >
                <div
                  className={`fuite__barre${
                    rapport.charniere?.libelle === tranche.libelle ? ' fuite__barre--pivot' : ''
                  }`}
                  style={{ height: `${Math.round((tranche.minutes / sommet) * 100)}%` }}
                  title={`${tranche.libelle} — ${tranche.minutes} min`}
                />
                <span className="fuite__heure num">{tranche.libelle.slice(0, 2)}</span>
              </div>
            ))}
          </div>

          <dl className="fuite__surfaces">
            <div>
              <dt>PC</dt>
              <dd className="num">
                {rapport.par_surface.pc.semaine} min <span>cette semaine</span>
              </dd>
            </div>
            <div>
              <dt>Téléphone</dt>
              <dd className="num">
                {rapport.par_surface.mobile.semaine} min <span>cette semaine</span>
              </dd>
            </div>
          </dl>

          {rapport.declencheurs.length > 0 && (
            <p className="fuite__correlation">
              Le plus souvent {rapport.declencheurs[0].quoi} (
              {Math.round(rapport.declencheurs[0].part * 100)} % des fois). Corrélation observée,
              rien de plus.
            </p>
          )}

          {rapport.sans_horodatage > 0 && (
            <p className="fuite__note">
              {rapport.sans_horodatage} min remontées sans heure : comptées dans le total, absentes
              de l'histogramme.
            </p>
          )}
        </div>
      )}
    </section>
  )
}
