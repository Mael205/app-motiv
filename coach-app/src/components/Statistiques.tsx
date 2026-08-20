import { useEffect, useState } from 'react'
import { api } from '../api'
import type { StatsLongues } from '../types'
import './Statistiques.css'

/** Les séries des douze dernières semaines (J6, §16).
 *
 * **Ce n'est pas la trace longue, et la différence compte.** La trace ne rend
 * que des compteurs incapables de baisser, pour le soir où le streak vient de
 * casser. Celle-ci rend des courbes — qui montent, qui descendent, qui montrent
 * les semaines vides. On ne l'ouvre pas le même soir, et c'est pour ça qu'elle
 * vit sur la fiche de personnage, l'endroit où l'on a le droit de flâner, et
 * jamais à l'accueil.
 *
 * **Rien n'y est commenté.** Pas de « ton lundi est ton pire jour », pas de
 * moyenne annoncée comme un objectif, pas de couleur d'alarme sur une semaine
 * creuse. Le §17 interdit le jugement, et une statistique est exactement
 * l'endroit où il revient sans qu'on s'en aperçoive : il suffit d'un adjectif.
 * Ici il n'y a que des barres et des nombres.
 */
export function Statistiques() {
  const [stats, setStats] = useState<StatsLongues | null>(null)

  useEffect(() => {
    api
      .stats()
      .then(setStats)
      .catch(() => setStats(null))
  }, [])

  if (!stats) return null

  const total = stats.semaines.reduce((somme, s) => somme + s.minutes, 0)
  if (total === 0) return null

  const plafond = Math.max(...stats.semaines.map((s) => s.minutes), 1)
  const plafondJour = Math.max(...stats.jours.map((j) => j.minutes), 1)
  const plafondHeure = Math.max(...stats.heures.map((h) => h.minutes), 1)

  return (
    <section className="panel stats">
      <div className="char__head">
        <span className="label">Douze semaines</span>
        <span className="num char__count">{heures(total)}</span>
      </div>
      <p className="section-hint">
        Ce que les compteurs cumulés ne montrent pas : le rythme. Les semaines
        vides y sont, à leur place.
      </p>

      {/* --- Par semaine ---------------------------------------------------
          Les barres sont ancrées en bas et gardent leur largeur : une semaine à
          zéro doit occuper autant de place qu'une pleine, sinon l'arrêt se
          referme visuellement et disparaît de la lecture. */}
      <ul className="stats__barres" aria-label="Minutes par semaine">
        {stats.semaines.map((semaine) => (
          <li key={semaine.debut} className="stats__barre">
            <span
              className="stats__barre-corps"
              style={{ height: `${Math.round((semaine.minutes / plafond) * 100)}%` }}
              title={`${dateCourte(semaine.debut)} · ${heures(semaine.minutes)} · ${semaine.jours_travailles} jour(s)`}
            />
          </li>
        ))}
      </ul>
      <div className="stats__bornes">
        <span>{dateCourte(stats.semaines[0].debut)}</span>
        <span>{dateCourte(stats.semaines[stats.semaines.length - 1].debut)}</span>
      </div>

      {/* --- Par jour de semaine ---
          La seule série du panneau qui porte sur une décision qu'on peut
          réellement prendre : déplacer un créneau. Les autres décrivent. */}
      <h4 className="stats__titre label">Par soir</h4>
      <ul className="stats__lignes">
        {stats.jours.map((jour) => (
          <li key={jour.index}>
            <span className="stats__nom">{jour.label}</span>
            <span className="stats__jauge">
              <span style={{ transform: `scaleX(${jour.minutes / plafondJour})` }} />
            </span>
            <span className="num stats__valeur">{heures(jour.minutes)}</span>
          </li>
        ))}
      </ul>

      {stats.heures.length > 0 && (
        <>
          <h4 className="stats__titre label">Heure de démarrage</h4>
          <ul className="stats__lignes">
            {stats.heures.map((tranche) => (
              <li key={tranche.heure}>
                <span className="stats__nom num">{tranche.heure}h</span>
                <span className="stats__jauge">
                  <span style={{ transform: `scaleX(${tranche.minutes / plafondHeure})` }} />
                </span>
                <span className="num stats__valeur">{heures(tranche.minutes)}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      <h4 className="stats__titre label">Séances</h4>
      <ul className="stats__faits">
        <li>
          <span>Durée moyenne</span>
          <span className="num">{stats.seances.moyenne} min</span>
        </li>
        <li>
          <span>La plus longue</span>
          <span className="num">{stats.seances.plus_longue} min</span>
        </li>
        <li>
          {/* Depuis le 19 août, une longue rapporte plus qu'une courte. Savoir
              quelle part des séances est longue est la seule façon de voir ce
              que cette règle donne en vrai. */}
          <span>Au moins 45 min</span>
          <span className="num">
            {stats.seances.longues} / {stats.seances.total}
          </span>
        </li>
        <li>
          <span>Étapes finies</span>
          <span className="num">{stats.etapes}</span>
        </li>
      </ul>

      {stats.projets.length > 0 && (
        <>
          <h4 className="stats__titre label">Par projet</h4>
          <ul className="stats__lignes">
            {stats.projets.map((projet) => (
              <li key={projet.nom}>
                <span className="stats__nom">{projet.nom}</span>
                <span className="stats__jauge">
                  <span
                    style={{
                      transform: `scaleX(${projet.minutes / stats.projets[0].minutes})`,
                      background: projet.couleur,
                    }}
                  />
                </span>
                <span className="num stats__valeur">{heures(projet.minutes)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

function heures(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const h = Math.floor(minutes / 60)
  const reste = minutes % 60
  return reste ? `${h}h${String(reste).padStart(2, '0')}` : `${h}h`
}

function dateCourte(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })
}
