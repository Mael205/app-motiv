import type { HomeState } from '../types'
import { DecisionBlock } from '../components/DecisionBlock'
import { GardePanel } from '../components/GardePanel'
import { NightHud } from '../components/NightHud'
import { RelaxGate } from '../components/RelaxGate'
import { RoutinePanel } from '../components/RoutinePanel'
import { SeasonBanner } from '../components/SeasonBanner'
import './Home.css'

/** L'écran du soir. Trois zones, une seule décision.
 *
 * 1. Qui tu es, dans quelle saison (identité, art, rang).
 * 2. Ce que tu fais maintenant — le bloc dominant.
 * 3. Où en est la soirée — HUD compact, secondaire.
 *
 * Tout le reste (roadmaps, frigo, journal) vit dans les autres onglets : un
 * écran qui doit déclencher une action ne peut pas être un tableau de bord.
 */
export function Home({ state, onStarted }: { state: HomeState; onStarted: () => void }) {
  return (
    <>
      <SeasonBanner season={state.season} progression={state.progression} streak={state.streak} />

      {state.rank.next_unlock && (
        <p className="muted rank-next">
          {state.rank.weeks_kept} semaine{state.rank.weeks_kept > 1 ? 's' : ''} d'engagements tenus.{' '}
          {state.rank.next_unlock}
        </p>
      )}

      {state.streak.message && (
        <div className={`notice notice--${state.streak.sanction_level >= 2 ? 'hard' : 'soft'}`}>
          {state.streak.message}
        </div>
      )}

      {state.proposal ? (
        <DecisionBlock proposal={state.proposal} onStarted={onStarted} />
      ) : (
        <section className="panel empty">
          <h2 className="display empty__title">Aucun projet actif</h2>
          <p className="muted">
            Ouvre un slot dans l'onglet Projets pour que le coach ait quelque chose à proposer ce soir.
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

      {state.quests.length > 0 && (
        <ul className="questline">
          {state.quests.map((quest) => (
            <li key={quest.label} className={`questline__item${quest.done ? ' questline__item--done' : ''}`}>
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
    </>
  )
}
