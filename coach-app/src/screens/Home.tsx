import type { HomeState } from '../types'
import { useBriefing } from '../hooks/useBriefing'
import { DecisionBlock } from '../components/DecisionBlock'
import { GardePanel } from '../components/GardePanel'
import { MomentumEmber } from '../components/MomentumEmber'
import { NightHud } from '../components/NightHud'
import { RelaxGate } from '../components/RelaxGate'
import { RoutinePanel } from '../components/RoutinePanel'
import { SeasonBanner } from '../components/SeasonBanner'
import { SkillTree } from '../components/SkillTree'
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
 * - **Gauche** : qui tu es. Saison, rang, momentum, arbre. Consultatif.
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
 * **Une exception, et elle compte.** Sur téléphone, la braise et l'arbre
 * placés dans le rail gauche repoussaient le bouton « Démarrer » sous la ligne
 * de flottaison : on ouvrait l'app le soir et il fallait faire défiler pour
 * trouver la seule chose à faire. Le §11.1 ne tolère pas ça. Ils sont donc
 * groupés dans `.deck__consult`, qui passe **après** la décision en dessous du
 * seuil et reste dans le rail au-dessus.
 */
export function Home({ state, onStarted }: { state: HomeState; onStarted: () => void }) {
  // Le briefing arrive apres coup et remplace la proposition ; tant qu'il n'est
  // pas la, l'ecran est deja complet et deja actionnable.
  const briefing = useBriefing(state.proposal, state.day + state.minutes_today)
  const decision = briefing ?? state.proposal
  const grown = state.skills?.filter((b) => b.minutes > 0) ?? []

  return (
    <div className="deck">
      {/* ---- Rail gauche : qui tu es ----------------------------------- */}
      <aside className="deck__rail deck__rail--left">
        <SeasonBanner season={state.season} progression={state.progression} streak={state.streak} />

        {state.rank.next_unlock && (
          <p className="muted rank-next">
            {state.rank.weeks_kept} semaine{state.rank.weeks_kept > 1 ? 's' : ''} d'engagements
            tenus. {state.rank.next_unlock}
          </p>
        )}

        {/* Consultatif : dans le rail a gauche sur grand ecran, mais rejete
            APRES la decision sur telephone — voir la note de mise en page. */}
        <div className="deck__consult">
          {state.momentum && <MomentumEmber momentum={state.momentum} />}

          {grown.length > 0 && (
            <section className="panel">
              <SkillTree branches={grown} tiers={[10, 25, 50, 100, 200, 400]} compact />
            </section>
          )}
        </div>
      </aside>

      {/* ---- Centre : la décision, et rien d'autre --------------------- */}
      <div className="deck__main">
        {state.streak.message && (
          <div className={`notice notice--${state.streak.sanction_level >= 2 ? 'hard' : 'soft'}`}>
            {state.streak.message}
          </div>
        )}

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
          minutesToday={state.minutes_today}
          requiredMinutes={state.required_minutes}
          validated={state.validated_today}
        />

        {!state.validated_today && <RelaxGate used={state.relax_used} onStarted={onStarted} />}
      </div>

      {/* ---- Rail droit : où en est la soirée --------------------------- */}
      <aside className="deck__rail deck__rail--right">
        {state.quests.length > 0 && (
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

        <RoutinePanel initial={state.entretien} />

        <GardePanel initial={state.gardes} />
      </aside>
    </div>
  )
}
