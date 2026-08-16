import { memo, useMemo } from 'react'
import type { Phantom } from '../types'
import './PhantomRace.css'

/** Le fantôme de saison (SPEC §12.7).
 *
 * > Reprise directe du contre-la-montre de jeu de course… **il performe contre
 * > un adversaire, pas contre une intention**.
 *
 * C'est ce qui décide du dessin. Une barre de progression vers un objectif
 * dirait « il t'en manque tant » — une intention, donc négociable un mardi
 * soir. Deux courbes côte à côte disent qui est devant, ce qui ne se négocie
 * pas.
 *
 * **Le tracé du fantôme va jusqu'au bout de la saison, le tien s'arrête
 * aujourd'hui.** On voit donc où l'adversaire *sera*, pas seulement où il est —
 * c'est ce qui fait lire le graphique comme une course plutôt que comme un
 * bilan.
 *
 * Aucune couleur d'alerte quand on est derrière. Le §0.2 pose que le système
 * n'est pas là pour motiver : le rose du thème signale un bouclier consommé,
 * pas un retard, et emprunter ce registre ici transformerait un fait en
 * reproche.
 */
export const PhantomRace = memo(function PhantomRace({ phantom }: { phantom: Phantom }) {
  const { series, line, available, ahead, day_index, days_total, choice_label } = phantom

  const geom = useMemo(() => {
    const values = series.flatMap((p) => [p.mine ?? 0, p.phantom ?? 0])
    const max = Math.max(1, ...values)
    const x = (i: number) => (i / Math.max(1, days_total - 1)) * 100
    const y = (v: number) => 100 - (v / max) * 100

    const path = (key: 'mine' | 'phantom') => {
      const points = series
        .map((p, i) => (p[key] == null ? null : `${x(i).toFixed(2)},${y(p[key]!).toFixed(2)}`))
        .filter(Boolean)
      return points.length > 1 ? `M ${points.join(' L ')}` : ''
    }

    return { mine: path('mine'), phantom: path('phantom'), x, y, max }
  }, [series, days_total])

  return (
    <section className={`race${ahead ? ' race--ahead' : ''}`}>
      <div className="race__head">
        <span className="label">Fantôme</span>
        {available && <span className="race__ref">{choice_label}</span>}
      </div>

      <p className="race__line">{line}</p>

      {available && (
        <div className="race__chart">
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
            {/* Le fantome d'abord, donc dessous : c'est le decor contre lequel
                on court, pas le sujet. */}
            <path className="race__path race__path--phantom" d={geom.phantom} />
            <path className="race__path race__path--mine" d={geom.mine} />
          </svg>

          {/* Le curseur du jour courant, comme sur la jauge du soir. */}
          <span
            className="race__now"
            style={{ left: `${(day_index / Math.max(1, days_total - 1)) * 100}%` }}
          />
        </div>
      )}

      {available && (
        <div className="race__foot">
          <span className="race__key race__key--mine">Toi</span>
          <span className="race__day num">
            J{day_index + 1} / {days_total}
          </span>
          <span className="race__key race__key--phantom">Fantôme</span>
        </div>
      )}
    </section>
  )
})
