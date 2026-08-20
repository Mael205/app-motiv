import type { HomeState, ModeExtra as EtatExtra } from '../types'
import { useRevelation } from '../juice'
import { useBriefing } from '../hooks/useBriefing'
import { BilanDuMatin } from '../components/BilanDuMatin'
import { CorpsPanel } from '../components/CorpsPanel'
import { DecisionBlock } from '../components/DecisionBlock'
import { GardePanel } from '../components/GardePanel'
import { ModeExtra } from '../components/ModeExtra'
import { NightHud } from '../components/NightHud'
import { RelaxGate } from '../components/RelaxGate'
import { RoutinePanel } from '../components/RoutinePanel'
import { SanctionList } from '../components/SanctionList'
import { SeasonBanner } from '../components/SeasonBanner'
import './Home.css'

/** L'écran du soir. Une seule décision, quelle que soit la largeur.
 *
 * Le §11.1 impose qu'une seule chose soit décidée ici. Sur téléphone c'était
 * automatique — il n'y a pas de place pour autre chose. Sur un grand écran, la
 * colonne unique laissait deux tiers de vide, ce qui ne respectait pas mieux la
 * règle : ça donnait un téléphone agrandi, pas une interface de bureau.
 *
 * D'où trois zones, qui ne changent **rien** à la hiérarchie :
 *
 * - **Gauche** : qui tu es. Saison, rang, XP. Consultatif.
 * - **Centre** : ce que tu fais maintenant. Largeur inchangée, donc dominance
 *   inchangée — c'est le point important, une colonne qui s'élargirait avec
 *   l'écran diluerait le seul élément qui doit rester écrasant.
 * - **Droite** : où en est la soirée. Quêtes, routines, gardes.
 *
 * Les rails sont `display: contents` sous le seuil : leur contenu retombe dans
 * le flux vertical du téléphone, dans l'ordre du DOM, sans duplication ni rendu
 * conditionnel. Une mise en page qui monterait deux arbres selon la largeur
 * finirait par en avoir un des deux cassé sans que personne ne le voie.
 *
 * **Ce que cet écran ne montre plus.** La braise de momentum et l'arbre de
 * compétences vivaient ici *et* dans l'onglet Personnage — le même panneau,
 * deux fois. Un doublon ne coûte pas seulement de la place : il enseigne que
 * l'accueil est l'endroit où tout se consulte, ce qui est exactement ce que le
 * §11.1 interdit. Ils ne vivent plus qu'à un seul endroit, celui où l'on a le
 * droit de flâner.
 *
 * Le fantôme suit la même logique mais garde une ligne ici : *où j'en suis
 * face à mon adversaire* est une information de ce soir, alors que la courbe
 * sur vingt-huit jours est une information de saison. La phrase reste,
 * le graphe part sur la fiche.
 *
 * Il reste donc, à gauche, un bandeau et deux lignes — et sur téléphone le
 * bouton « Démarrer » repasse au-dessus de la ligne de flottaison, ce qui est
 * la mesure qui décide de tout le reste.
 *
 * **La vitrine fermée du §14 vide les deux rails.** Fantôme, modificateur,
 * quêtes : tout ce qui se *consulte* disparaît après un jour raté, et il ne
 * reste que ce sur quoi on *agit* — la décision, la soirée, les routines et
 * les gardes. Ces deux derniers restent parce qu'ils ne sont pas des trophées :
 * l'Entretien n'a pas de streak à admirer (§11.9) et une garde se déclare le
 * soir même ou pas du tout.
 */
export function Home({
  state,
  extra = null,
  onStarted,
}: {
  state: HomeState
  extra?: EtatExtra | null
  onStarted: () => void
}) {
  // Le briefing arrive apres coup et remplace la proposition ; tant qu'il n'est
  // pas la, l'ecran est deja complet et deja actionnable.
  const briefing = useBriefing(state.proposal, state.day + state.minutes_today)
  const decision = briefing ?? state.proposal
  const locked = state.sanctions.showcase_locked

  /** Le bilan d'hier ne paraît qu'**avant** l'ouverture de la fenêtre du soir.
   *
   * C'est ce qui le rend compatible avec le §11.1 : le matin, l'accueil ne
   * porte aucune décision — la soirée n'a pas commencé, il n'y a rien à
   * démarrer — et une tuile qui ne demande rien y a sa place. Passé l'heure,
   * elle disparaît d'elle-même et l'écran redevient ce qu'il doit être : une
   * décision et rien d'autre. Les deux dates viennent du serveur, jamais d'un
   * `new Date()` local qui se tromperait entre minuit et la bascule de 4h. */
  const avantLaSoiree = state.now < state.evening.start

  /* Les panneaux consultatifs se levent quand on les atteint — jamais le bloc
     de decision, qui doit exister a l'image zero. Le §7 interdit l'animation
     sur le chemin critique, et un bouton « Demarrer » qui attend d'etre
     observe pour devenir visible en serait le pire exemple. */
  const scene = useRevelation({ lever: '.deck__consult > *, .deck__rail--right > *' })

  return (
    <div className="deck" ref={scene}>
      {/* ---- Rail gauche : qui tu es ----------------------------------- */}
      <aside className="deck__rail deck__rail--left">
        {/* Pendant le mode extra, il n'y a pas de saison à montrer — et c'est
            précisément ce qu'il faut expliquer. Le bandeau cède sa place plutôt
            que d'afficher un vide à la forme de saison. */}
        {extra ? (
          <ModeExtra extra={extra} />
        ) : (
          <SeasonBanner
            cosmetics={state.cosmetics}
            season={state.season}
            progression={state.progression}
            streak={state.streak}
            unlock={state.rank.next_unlock}
          />
        )}

        {/* Consultatif : dans le rail a gauche sur grand ecran, mais rejete
            APRES la decision sur telephone — voir la note de mise en page.
            Entierement retire quand la vitrine est fermee. */}
        {!locked && (
          <div className="deck__consult">
            {state.modifier?.active && (
              <p className="modifier">
                <span className="modifier__name">{state.modifier.name}</span>
                <span className="modifier__effet">{state.modifier.effet}</span>
              </p>
            )}

            {state.phantom?.available && (
              <p className="ghostline">
                <span className="label">Fantôme</span>
                {state.phantom.line}
              </p>
            )}
          </div>
        )}
      </aside>

      {/* ---- Centre : la décision, et rien d'autre --------------------- */}
      <div className="deck__main">
        {/* Le bilan de la nuit (§13.1), le matin seulement. Il ne demande rien,
            donc il ne dispute rien à la décision — qui n'existe pas encore à
            cette heure-là. */}
        <BilanDuMatin avantLaSoiree={avantLaSoiree} />

        {state.streak.message && (
          <div className={`notice notice--${state.streak.sanction_level >= 2 ? 'hard' : 'soft'}`}>
            {state.streak.message}
          </div>
        )}

        <SanctionList sanctions={state.sanctions} />

        {decision ? (
          <DecisionBlock proposal={decision} onStarted={onStarted} />
        ) : (
          <section className="panel empty">
            <h2 className="display empty__title">Aucun projet actif</h2>
            <p className="muted">
              Ouvre un slot dans l'onglet Projets pour que le coach ait quelque chose à proposer ce
              soir.
            </p>
          </section>
        )}

        <NightHud
          evening={state.evening}
          boss={state.boss}
          phantom={locked ? null : state.phantom?.live}
          minutesToday={state.minutes_today}
          requiredMinutes={state.required_minutes}
          validated={state.validated_today}
        />

        {!state.validated_today && (
          <RelaxGate
            used={state.relax_used}
            revoked={state.sanctions.relax_revoked}
            onStarted={onStarted}
          />
        )}
      </div>

      {/* ---- Rail droit : où en est la soirée --------------------------- */}
      <aside className="deck__rail deck__rail--right">
        {!locked && state.quests.length > 0 && (
          <ul className="questline">
            {state.quests.map((quest) => (
              <li
                key={quest.label}
                className={`questline__item${quest.done ? ' questline__item--done' : ''}`}
              >
                <span className="questline__mark" aria-hidden>
                  {quest.done ? '◆' : '◇'}
                </span>
                {quest.label}
              </li>
            ))}
          </ul>
        )}

        {/* Côte à côte avec l'Atelier, jamais fusionnées en un score unique
            (§11.4). Elle reste visible même vitrine fermée : ce n'est pas un
            trophée, c'est l'état d'une piste sur laquelle on peut encore agir. */}
        {state.corps && <CorpsPanel corps={state.corps} />}

        <RoutinePanel initial={state.entretien} />

        <GardePanel initial={state.gardes} />
      </aside>
    </div>
  )
}
