import { useEffect, useState } from 'react'
import { api } from '../api'
import type { CapacitePanel } from '../types'
import './Capacite.css'

/** Le troisième axe : ce que tu sais faire, et non combien tu as travaillé.
 *
 * **Le manque auquel ce panneau répond.** Tout le reste de cette fiche mesure du
 * volume — XP, niveau, heures par branche — ou de la régularité — rang, semaines
 * tenues, streak. Aucun des deux ne dit qu'on est devenu meilleur : quarante
 * heures de mauvaise pratique donnent exactement le même titre d'arbre que
 * quarante heures de bonne, parce que le titre se calcule sur les heures.
 *
 * Les deux nombres restent **côte à côte et ne fusionnent jamais**, comme les
 * deux pistes du §11.4 et les deux axes du §4.4. Un score unique monterait en
 * ne faisant que des heures, donc il aurait précisément le défaut à corriger.
 *
 * Le rapport heures / preuve n'est pas une note. Il sert à une seule question,
 * celle qu'on ne se pose jamais tout seul : combien d'heures pour la dernière
 * chose que je sais faire ?
 */
export function Capacite() {
  const [panel, setPanel] = useState<CapacitePanel | null>(null)

  /* Le `catch` aligne ce panneau sur ses deux voisins, `Trace` et
   * `HautsFaits`, qui l'avaient déjà : un panneau consultatif absent se tait,
   * il ne fait pas remonter une promesse rejetée jusqu'en haut. L'écran, lui,
   * dit déjà que le serveur ne répond pas — le redire trois fois n'aiderait
   * personne. */
  useEffect(() => {
    api.preuves()
      .then(setPanel)
      .catch(() => setPanel(null))
  }, [])

  if (!panel) return null

  return (
    <section className="panel capacite">
      <div className="char__head">
        <span className="label">Capacité</span>
        <span className="capacite__ratio muted">
          {panel.heures_par_preuve === null
            ? `${panel.heures} h, aucune preuve`
            : `${panel.heures_par_preuve} h par preuve`}
        </span>
      </div>

      <div className="capacite__chiffres">
        <div className="capacite__bloc">
          <span className="capacite__nombre num">{panel.preuves}</span>
          <span className="label">preuve{panel.preuves > 1 ? 's' : ''}</span>
        </div>
        <div className="capacite__bloc capacite__bloc--faible">
          <span className="capacite__nombre num">{panel.heures}</span>
          <span className="label">heures</span>
        </div>
      </div>

      {panel.preuves === 0 ? (
        <p className="capacite__vide muted">
          Une preuve est un fait daté que quelqu'un d'autre pourrait constater — « les 100 % de
          labs Apprentice validés », pas « j'ai progressé ». Elle se déclare depuis un bloc du
          parcours, dans l'onglet Projets, quand son critère de sortie est atteint.
        </p>
      ) : (
        <ul className="capacite__liste">
          {panel.liste.map((preuve) => (
            <li key={preuve.id} style={{ ['--project' as string]: preuve.couleur }}>
              <p className="capacite__critere">{preuve.critere}</p>
              <p className="capacite__source muted">
                {preuve.projet} · {formatDate(preuve.obtained_on)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function formatDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })
}
