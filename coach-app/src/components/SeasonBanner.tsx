import { memo, useState } from 'react'
import { motion } from 'motion/react'
import { Glossary } from './Glossary'
import { setSoundMuted, soundMuted } from '../juice'
import type { Progression, SeasonState, Streak } from '../types'
import { RankBadge } from './art/RankBadge'
import { SeasonOrnament, SeasonSigil } from './art/SeasonSigil'
import { Icon } from './art/Icons'
import './SeasonBanner.css'

/** Zone 1 : qui tu es, dans quelle saison.
 *
 * L'identité tient le haut de l'écran — emblème dessiné, nom de saison, rang
 * ailé, barre d'XP. C'est la seule zone décorative de l'interface, et elle
 * porte la direction artistique de la saison en cours.
 *
 * **Elle a été raccourcie, et pour une raison mesurée.** Sur un téléphone de
 * 844 px, le bandeau plein poussait le bouton « Démarrer » sous la ligne de
 * flottaison : on ouvrait l'app le soir et il fallait faire défiler pour
 * trouver la seule chose à faire. C'est le défaut que le §11.1 ne tolère pas,
 * et c'est la deuxième fois qu'il apparaît — la première fois par les panneaux
 * consultatifs, cette fois par le bandeau lui-même.
 *
 * Ce qui est parti : la ligne de saison en toutes lettres, qui se cassait en
 * trois sur téléphone, et la baseline, qui est de la saveur déjà servie en
 * grand à l'ouverture de la saison. Ce qui reste est ce qu'on relit : où on en
 * est dans la saison, le rang, l'XP, le streak et les boucliers.
 */
export const SeasonBanner = memo(function SeasonBanner({
  season,
  progression,
  streak,
  unlock,
}: {
  season: SeasonState | null
  progression: Progression
  streak: Streak
  unlock?: string | null
}) {
  const [helpOpen, setHelpOpen] = useState(false)
  // La coupure du son vit ici plutôt que dans un écran de réglages : on la
  // cherche à l'instant où un son vient de se jouer, pas trois écrans plus loin.
  const [muet, setMuet] = useState(soundMuted)

  return (
    <header className="banner">
      <div className="banner__glow" aria-hidden />

      <div className="banner__top">
        <SeasonSigil seasonKey={season?.key} size={34} className="banner__sigil" />
        <div className="banner__titles">
          <h1 className="banner__name display">{season?.name ?? 'Hors saison'}</h1>
          {season && (
            // Abrégé jusqu'à tenir dans le rail de 262 px sans être coupé. Le
            // texte entier reste en infobulle : une ligne tronquée par des
            // points de suspension donne moins qu'une ligne courte assumée.
            <span
              className="label banner__when"
              title={`Saison ${season.index}, jour ${season.day_index} sur ${season.days_total}. ${season.days_left} jours avant la fin.`}
            >
              J{season.day_index}/{season.days_total} · {season.days_left} j
            </span>
          )}
        </div>
        <button
          className="helpbtn"
          onClick={() => {
            setSoundMuted(!muet)
            setMuet(!muet)
          }}
          aria-pressed={muet}
          aria-label={muet ? 'Réactiver le son' : 'Couper le son'}
          title={muet ? 'Réactiver le son' : 'Couper le son des séquences'}
        >
          {muet ? '🔇' : '🔊'}
        </button>
        <button
          className="helpbtn"
          onClick={() => setHelpOpen(true)}
          aria-label="Ce que veulent dire les chiffres"
          title="Ce que veulent dire les chiffres"
        >
          ?
        </button>
      </div>

      <Glossary open={helpOpen} onClose={() => setHelpOpen(false)} />

      <SeasonOrnament seasonKey={season?.key} />

      <div className="banner__body">
        {/* Sans `size` : c'est la feuille de style qui décide, parce qu'elle
            seule sait dans quel contenant le bandeau est posé. */}
        <RankBadge rank={progression.rank} level={progression.level} />

        <div className="banner__stats">
          <div className="row row--between banner__xp-head">
            <span className="label">XP vers le niv. {progression.level + 1}</span>
            <span className="banner__xp-num">
              <span className="num">{progression.into_level}</span>
              <span className="muted num"> / {progression.next_level_xp - progression.level_floor_xp}</span>
            </span>
          </div>

          <div className="xpbar">
            <motion.div
              className="xpbar__fill"
              initial={false}
              animate={{ scaleX: progression.ratio }}
              transition={{ type: 'spring', stiffness: 90, damping: 20 }}
            />
            <div className="xpbar__shine" />
          </div>

          <div className="banner__counters">
            <span
              className="counter"
              title="Jours consécutifs où tu as validé le plancher. Il survit à un jour raté, jamais à deux."
            >
              <Icon.flame size={17} />
              <span className="num">{streak.current}</span>
              <span className="label">
                {streak.current > 1 ? 'jours d’affilée' : 'jour d’affilée'}
              </span>
            </span>

            <span
              className="counter counter--shields"
              title={`${streak.shields} bouclier(s) sur 3. Un jour raté en consomme un et le streak continue. Prochain dans ${streak.to_next_shield} jour(s) validé(s).`}
            >
              <span className="label">Boucliers</span>
              {[0, 1, 2].map((i) => (
                <Icon.shield key={i} size={17} className={i < streak.shields ? 'shield--on' : 'shield--off'} />
              ))}
            </span>
          </div>
        </div>
      </div>

      {/* Le prochain droit ouvert par le rang, en pied de bandeau plutôt qu'en
          paragraphe séparé sous le panneau : c'est une propriété du rang, pas
          une information de plus. */}
      {unlock && <p className="banner__unlock">{unlock}</p>}
    </header>
  )
})
