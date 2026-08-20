import type { ModeExtra as Etat } from '../types'
import './ModeExtra.css'

/** Le mode extra (SPEC §12.4).
 *
 * Le boss est tombé avant la fin des quatre semaines. La saison est close, son
 * titre décerné, sa mise résolue — et la suivante ne commence pas tout de
 * suite. Ces jours-là ne sont pas vides : **tout ce qui s'y pose est mis de
 * côté pour la saison suivante**, qui démarre donc avec de l'avance.
 *
 * **Pourquoi cet écran existe.** Sans lui, une victoire anticipée retirait le
 * boss, le fantôme, le modificateur et la mise pendant deux semaines, sans une
 * ligne d'explication. Une récompense qu'on ne distingue pas d'une panne est
 * une punition : c'est l'endroit exact où quelqu'un se dit que l'app est
 * cassée, et ferme.
 *
 * Il ne demande rien et ne propose rien. La décision du soir continue en
 * dessous, inchangée — les minutes comptent toujours pour le streak, pour l'XP
 * et pour les projets. Seule la couche de saison est en pause.
 */
export function ModeExtra({ extra }: { extra: Etat }) {
  return (
    <section className="extra" style={{ ['--extra' as string]: extra.accent }}>
      <div className="extra__head">
        <span className="label">Mode extra</span>
        <span className="extra__compte num">
          {extra.days_until} <span className="label">jour{extra.days_until > 1 ? 's' : ''}</span>
        </span>
      </div>

      <p className="extra__texte">
        Le boss est tombé avant la fin. Tout ce que tu poses d'ici là est mis de côté pour{' '}
        <strong className="extra__nom">{extra.name}</strong>.
      </p>

      {/* Le compteur d'avance. Il monte, il ne redescend jamais — c'est un
          report de travail, pas un objectif à remplir. */}
      <p className="extra__mise">
        <span className="num">{duree(extra.minutes)}</span> déjà d'avance
      </p>
    </section>
  )
}

function duree(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const h = Math.floor(minutes / 60)
  const reste = minutes % 60
  return reste ? `${h}h${String(reste).padStart(2, '0')}` : `${h}h`
}
