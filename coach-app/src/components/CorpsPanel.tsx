import { memo } from 'react'
import { motion } from 'motion/react'
import type { CorpsPanel as CorpsData } from '../types'
import './CorpsPanel.css'

/** La piste Corps, à côté de l'Atelier (SPEC §11.4).
 *
 * « Les deux pistes apparaissent côte à côte sur l'accueil, jamais fusionnées
 * en un score unique. » Elle n'y était pas du tout : la piste existait dans la
 * base, donnait de l'XP, et aucun écran ne la montrait.
 *
 * Ce panneau ne demande rien. Quand la semaine du Corps est sur le point d'être
 * ratée, ce n'est pas ici que ça se voit — c'est la décision du soir elle-même
 * qui devient une séance. Un panneau qui réclamerait en plus ferait deux
 * demandes à l'écran, et le §11.1 n'en autorise qu'une.
 *
 * Le streak se compte en **semaines**, jamais en jours : deux séances par
 * semaine avec du repos entre elles valent mieux que sept séances molles, et un
 * compteur quotidien pousserait exactement au contraire.
 */
export const CorpsPanel = memo(function CorpsPanel({ corps }: { corps: CorpsData }) {
  return (
    <section className={`corps${corps.tenue ? ' corps--tenue' : ''}`}>
      <header className="row row--between corps__head">
        <span className="label">Corps</span>
        {corps.streak > 0 && (
          <span className="corps__streak" title={`Meilleure série : ${corps.best} semaines`}>
            <span className="num">{corps.streak}</span> semaines d'affilée
          </span>
        )}
      </header>

      <div className="corps__pastilles" role="img" aria-label={corps.message}>
        {Array.from({ length: corps.objectif }, (_, i) => (
          <motion.span
            key={i}
            className={`pastille${i < corps.faites ? ' pastille--pleine' : ''}`}
            initial={false}
            animate={{ scale: i < corps.faites ? 1 : 0.82 }}
            transition={{ type: 'spring', stiffness: 380, damping: 20 }}
          />
        ))}
        {/* Les séances au-delà de l'objectif se montrent aussi. Les cacher
            reviendrait à dire qu'elles n'ont pas eu lieu. */}
        {corps.faites > corps.objectif && (
          <span className="corps__extra num">+{corps.faites - corps.objectif}</span>
        )}
      </div>

      <p className="corps__message muted">{corps.message}</p>

      <p className="corps__projets muted">
        {corps.projets.map((p) => p.name).join(' · ')}
      </p>
    </section>
  )
})
