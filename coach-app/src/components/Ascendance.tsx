import { useState } from 'react'
import { motion } from 'motion/react'
import { api } from '../api'
import { Rays, sfx, useReducedMotion, useTrauma } from '../juice'
import type { AnneeAccomplie } from '../types'
import './Ascendance.css'

/** La clôture d'une année et le choix de la voie (§12.2 étendu).
 *
 * Elle arrive une fois tous les douze mois de jeu, et c'est le seul écran du
 * produit qui a le droit d'en faire autant. Deux temps, dans cet ordre, et
 * l'ordre est le sujet :
 *
 * 1. **le bilan** — douze saisons, les boss abattus, les heures, et ce qui va
 *    repartir de zéro. Dit en toutes lettres, parce que c'est la question qu'on
 *    se pose en arrivant ici et qu'un doute là-dessus coûte plus cher que
 *    l'écran entier ;
 * 2. **la voie** — un choix parmi celles qui restent, définitif.
 *
 * Choisir avant d'avoir lu ce qu'on a fait de l'année n'aurait aucun sens, d'où
 * les deux temps plutôt qu'un écran unique où tout cohabite.
 */
export function Ascendance({ annee, onDone }: { annee: AnneeAccomplie; onDone: () => void }) {
  const reduced = useReducedMotion()
  const { shake, style } = useTrauma()
  const [temps, setTemps] = useState<'bilan' | 'voie'>('bilan')
  const [choisie, setChoisie] = useState('')
  const [busy, setBusy] = useState(false)
  const [erreur, setErreur] = useState('')

  async function graver() {
    if (!choisie || busy) return
    setBusy(true)
    setErreur('')
    try {
      await api.chooseVoie(choisie)
      sfx.seasonEnd()
      onDone()
    } catch (error) {
      setErreur(error instanceof Error ? error.message : 'Impossible de graver la voie.')
      setBusy(false)
    }
  }

  return (
    <motion.div
      className="asc-annee"
      initial={reduced ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      style={style}
    >
      {temps === 'bilan' ? (
        <section className="annee">
          {!reduced && <Rays count={18} color="var(--or, #E8A33D)" />}

          <p className="label annee__over">Année accomplie</p>
          <h2 className="annee__titre display">{annee.title}</h2>

          <ul className="annee__chiffres">
            <Chiffre valeur={annee.seasons} label="saisons closes" />
            <Chiffre valeur={annee.bosses_killed} label="boss abattus" />
            <Chiffre valeur={annee.hours} label="heures" unite="h" />
            <Chiffre valeur={annee.level_at_reset} label="niveau atteint" />
          </ul>

          {/* La garde. Ce n'est pas une petite ligne en bas : c'est ce qu'on
              vient chercher, et le serveur l'écrit pour que le front ne puisse
              pas en adoucir la formulation. */}
          <p className="annee__garde">{annee.garde}</p>

          <button
            className="cta"
            onClick={() => {
              shake(0.8)
              setTemps('voie')
            }}
          >
            Choisir la voie
          </button>
        </section>
      ) : (
        <section className="annee annee--voie">
          <p className="label annee__over">Une voie, définitive</p>
          <h2 className="annee__titre display">An {annee.year + 1}</h2>
          <p className="annee__sous muted">
            Elle ne se reprend pas. Une voie qu'on pourrait échanger le mois suivant
            serait un réglage, pas un choix.
          </p>

          <ul className="voies">
            {annee.voies.map((voie) => (
              <li key={voie.key}>
                <button
                  className={`voie${choisie === voie.key ? ' voie--on' : ''}`}
                  onClick={() => setChoisie(voie.key)}
                >
                  <span className="voie__nom display">{voie.label}</span>
                  <span className="voie__promesse">{voie.promesse}</span>
                  {/* Le coût est affiché aussi grand que la promesse. Une voie
                      dont on ne lirait que ce qu'elle ouvre serait un piège. */}
                  <span className="voie__cout muted">{voie.cout}</span>
                </button>
              </li>
            ))}
          </ul>

          {erreur && <p className="annee__erreur">{erreur}</p>}

          <button className="cta" onClick={graver} disabled={!choisie || busy}>
            {busy ? 'Gravure…' : choisie ? 'Graver cette voie' : 'Choisis une voie'}
          </button>
        </section>
      )}
    </motion.div>
  )
}

function Chiffre({ valeur, label, unite = '' }: { valeur: number; label: string; unite?: string }) {
  return (
    <li className="chiffre">
      <span className="chiffre__valeur num">
        {valeur.toLocaleString('fr-FR')}
        {unite}
      </span>
      <span className="chiffre__label">{label}</span>
    </li>
  )
}
