import { useEffect } from 'react'
import { motion } from 'motion/react'
import { Burst, sfx, useReducedMotion, useTrauma } from '../juice'
import './SessionEntry.css'

/** La première séquence du §7 : entrer dans la session.
 *
 * > **Démarrage de session** — l'interface se replie sur le timer, tout le
 * > reste s'éteint, l'emblème du projet s'imprime. Séquence courte, sensation
 * > d'**entrer quelque part**.
 *
 * Cette séquence est la seule des quatre à jouer pendant qu'une requête est en
 * vol, et c'est ce qui contraint tout son dessin. Le §7 est catégorique :
 *
 * > **Jamais d'animation sur le chemin critique** — le bouton « Démarrer »
 * > répond immédiatement et l'effet se joue par-dessus.
 *
 * Elle ne retarde donc rien. L'appel `POST /sessions/start` part au clic ; ce
 * composant se monte au même instant et couvre l'attente. S'il n'y avait pas
 * de séquence, on regarderait un bouton grisé pendant six cents millisecondes —
 * exactement au moment où l'on vient enfin de décider de s'y mettre.
 *
 * **L'emblème s'imprime, il n'apparaît pas.** Il arrive de loin, légèrement
 * de travers, et se pose à plat avec un anneau d'impact qui se propage. C'est
 * le vocabulaire du tampon, choisi parce qu'il dit « c'est acté » là où une
 * apparition en fondu dirait seulement « voici ».
 */
export function SessionEntry({
  project,
  minutes,
  emblem,
  color,
}: {
  project: string
  minutes: number
  emblem: string
  color: string
}) {
  const reduced = useReducedMotion()
  const { shake, style } = useTrauma()

  // La secousse part au moment où l'emblème se pose, pas au montage : c'est
  // l'impact qui secoue, et il arrive 260 ms après le début de la course.
  //
  // Le son part au même instant que la secousse et jamais avant. Un son en
  // avance sur l'image se remarque immédiatement comme un défaut, alors qu'un
  // décalage de quelques millisecondes en retard passe inaperçu — l'oreille
  // est bien plus stricte que l'œil sur ce sens-là.
  useEffect(() => {
    if (reduced) {
      sfx.sessionStart()
      return
    }
    const t = setTimeout(() => {
      shake(0.55)
      sfx.sessionStart()
    }, 260)
    return () => clearTimeout(t)
  }, [shake, reduced])

  return (
    <motion.div
      className="entry"
      style={{ ['--project' as string]: color }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      role="status"
      aria-label={`Démarrage de ${project}`}
    >
      {/* Les volets. Le reste de l'interface s'eteint derriere eux : c'est le
          « tout le reste s'eteint » du §7, joue comme une fermeture et non
          comme un fondu. */}
      {!reduced && (
        <>
          <motion.span
            className="entry__shutter entry__shutter--top"
            initial={{ scaleY: 0 }}
            animate={{ scaleY: 1 }}
            transition={{ duration: 0.34, ease: [0.16, 1.2, 0.3, 1] }}
          />
          <motion.span
            className="entry__shutter entry__shutter--bottom"
            initial={{ scaleY: 0 }}
            animate={{ scaleY: 1 }}
            transition={{ duration: 0.34, ease: [0.16, 1.2, 0.3, 1] }}
          />
        </>
      )}

      <motion.div className="entry__core" style={style}>
        <motion.div
          className="entry__stamp"
          initial={reduced ? false : { scale: 3.4, rotate: -22, opacity: 0, filter: 'blur(16px)' }}
          animate={{ scale: 1, rotate: 0, opacity: 1, filter: 'blur(0px)' }}
          transition={{ duration: 0.42, ease: [0.16, 1.2, 0.3, 1] }}
        >
          <span className="entry__emblem" aria-hidden>
            {emblem}
          </span>
          {/* L'anneau d'impact : il naît sous l'emblème au moment du contact et
              se propage vers l'exterieur en s'effaçant. */}
          {!reduced && <span className="entry__ring" />}
        </motion.div>

        <motion.p
          className="entry__project display"
          initial={reduced ? false : { opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
        >
          {project}
        </motion.p>

        <motion.p
          className="entry__minutes num"
          initial={reduced ? false : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.38, duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
        >
          {minutes} min
        </motion.p>

        <Burst count={18} color={color} spread={190} life={700} />
      </motion.div>
    </motion.div>
  )
}
