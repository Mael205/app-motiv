import { AnimatePresence, motion } from 'motion/react'
import './Glossary.css'

/** Le glossaire.
 *
 * Chaque chiffre de l'interface répond à une règle précise, et une règle qu'on
 * ne comprend pas ne tient pas le cadre. Tout est expliqué ici, en une phrase,
 * dans le ton du coach : ce que c'est, et ce que ça change pour toi.
 */

const ENTRIES: { term: string; what: string; why: string }[] = [
  {
    term: 'Saison',
    what: 'Un cycle de 4 semaines avec son nom, sa couleur et son boss. Ensuite, 2 jours de pause et une nouvelle démarre.',
    why: 'Quand une semaine casse, la suivante recommence dans quelques jours. C’est ce qui remplace « j’ai raté, donc j’arrête ».',
  },
  {
    term: 'Rang',
    what: 'De F à SS. Il monte avec ton niveau global et ne redescend jamais, quoi qu’il arrive.',
    why: 'C’est la trace longue : elle prouve que six mois de travail ont produit quelque chose, même après une mauvaise saison.',
  },
  {
    term: 'Niveau et XP',
    what: 'L’XP vient uniquement des sessions terminées. La barre montre ce qu’il reste avant le niveau suivant.',
    why: 'Aucune action dans l’app ne donne d’XP — ni planifier, ni ranger le frigo. Seul le travail réel compte.',
  },
  {
    term: 'Streak',
    what: 'Le nombre de jours consécutifs où tu as validé le plancher.',
    why: 'Il survit à un jour raté grâce aux boucliers, mais jamais à deux d’affilée. La règle est : jamais deux fois.',
  },
  {
    term: 'Boucliers',
    what: 'Tu en as 3 au maximum, +1 tous les 5 jours validés. Un jour raté en consomme un automatiquement.',
    why: 'Sans bouclier disponible, un seul jour raté remet le streak à zéro. Ils absorbent les accidents, pas le décrochage.',
  },
  {
    term: 'Plancher',
    what: '25 minutes valident la journée. 10 minutes en mode dégradé la valident aussi.',
    why: 'Volontairement ridicule pour survivre aux mauvais soirs. Le but n’est pas de faire 3h, c’est de ne pas faire zéro.',
  },
  {
    term: 'Mode dégradé',
    what: 'Une session de 10 minutes. Elle valide la journée et garde le bonus de première session.',
    why: 'Le point dur, c’est de s’y mettre. Une fois lancé, un bouton te propose de prolonger de 15 minutes.',
  },
  {
    term: 'Jauge du soir',
    what: 'Ta fenêtre de travail du jour, avec le curseur du temps réel et un bloc par session posée.',
    why: 'Elle rend visible le temps qui fond. C’est le seul chiffre qui diminue tout seul pendant que tu regardes ailleurs.',
  },
  {
    term: 'Boss',
    what: 'Sa vie descend avec ton travail réel : 1 point par minute, 60 par étape de roadmap terminée.',
    why: 'Il répond à « à quoi ça sert, ce soir » mieux qu’un compteur d’XP. Le tuer avant la fin de la saison ouvre un mode extra.',
  },
  {
    term: 'Amorce',
    what: 'La première action de ta prochaine session, écrite à la fin de celle-ci. Obligatoire.',
    why: 'Le démarrage à froid est le coût le plus élevé du système. On le paie maintenant, pendant que le contexte est chaud.',
  },
  {
    term: 'Les 3 slots',
    what: 'Trois projets actifs maximum. L’échange se fait le dimanche uniquement.',
    why: 'C’est le cœur du dispositif anti-dispersion. Une quatrième idée va au frigo, elle ne prend pas la place d’un projet.',
  },
  {
    term: 'Le frigo',
    what: 'La liste des idées capturées mais non démarrées.',
    why: 'La prochaine idée excitante arrivera. Elle atterrit là au lieu de te coûter un projet en cours.',
  },
  {
    term: 'Plafond de régime',
    what: 'Les 3 premières sessions du jour rapportent plein, la 4ᵉ à moitié, la 5ᵉ plus rien. Les minutes restent comptées.',
    why: 'Ton problème n’est pas le manque de motivation, c’est le sur-régime du jour 2 qui produit l’abandon du jour 6.',
  },
  {
    term: 'Quêtes du jour',
    what: 'Une quête plancher obligatoire, une quête bonus contextuelle.',
    why: 'Elles disent quoi faire quand tu ne veux pas choisir. Aucune ne rapporte quoi que ce soit sans travail réel.',
  },
]

export function Glossary({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="glossary__backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.aside
            className="glossary"
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 30, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-label="Ce que veulent dire les chiffres"
          >
            <header className="glossary__head">
              <h2 className="display">Ce que veulent dire les chiffres</h2>
              <button className="ghost" onClick={onClose}>
                Fermer
              </button>
            </header>

            <dl className="glossary__list">
              {ENTRIES.map((entry) => (
                <div key={entry.term} className="glossary__entry">
                  <dt className="glossary__term">{entry.term}</dt>
                  <dd>
                    <p className="glossary__what">{entry.what}</p>
                    <p className="glossary__why">{entry.why}</p>
                  </dd>
                </div>
              ))}
            </dl>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
