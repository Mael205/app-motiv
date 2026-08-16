import { useCallback, useEffect, useState } from 'react'
import { ApiError, api, login, storedToken } from './api'
import type { HomeState, SeasonOffer, SeasonReport, SeasonState as SeasonPhase } from './types'
import { Comeback } from './components/Comeback'
import { SeasonCeremony } from './components/SeasonCeremony'
import { Home } from './screens/Home'
import { Character } from './screens/Character'
import { Journal } from './screens/Journal'
import { Projects } from './screens/Projects'
import { SessionScreen } from './screens/SessionScreen'
import { TabBar, type Tab } from './components/TabBar'
import './App.css'

export default function App() {
  const [state, setState] = useState<HomeState | null>(null)
  const [error, setError] = useState('')
  const [authed, setAuthed] = useState(() => Boolean(storedToken()))
  const [tab, setTab] = useState<Tab>('soir')
  // La cérémonie du §7.4 : une saison finie pendant qu'on ne regardait pas doit
  // se conclure quand on revient, pas rester en suspens jusqu'à un déclencheur.
  const [ceremony, setCeremony] = useState<{ report: SeasonReport | null; offer: SeasonOffer } | null>(null)
  // La porte de sortie du §14. Gardée à part de la cérémonie : celle-ci
  // s'impose, celle-là se propose et peut rester ignorée des semaines.
  const [exitOffer, setExitOffer] = useState<SeasonPhase['exit_offer']>(null)

  const checkSeason = useCallback(async () => {
    try {
      const etat = await api.seasonState()
      setExitOffer(etat.exit_offer)
      if (etat.pending_close) {
        const bilan = await api.closeSeason()
        setCeremony({ report: bilan, offer: bilan.offer ?? etat.offer! })
      } else if (!etat.running && etat.offer) {
        setCeremony({ report: null, offer: etat.offer })
      } else {
        setCeremony(null)
      }
    } catch {
      /* la cérémonie n'est jamais bloquante : sans elle l'app reste entière */
    }
  }, [])

  const load = useCallback(async () => {
    try {
      const home = await api.home()
      setState(home)
      setError('')
      applySeasonTheme(home)
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setAuthed(false)
      else setError(e instanceof Error ? e.message : 'Le serveur ne répond pas.')
    }
  }, [])

  useEffect(() => {
    if (!authed) return
    load()
    checkSeason()
    // Repli de synchronisation en attendant le flux SSE du jalon suivant.
    const id = setInterval(load, 10_000)
    return () => clearInterval(id)
  }, [authed, load, checkSeason])

  if (!authed) return <LoginScreen onDone={() => setAuthed(true)} />

  if (error) {
    return (
      <div className="shell boot">
        <p className="boot__error">{error}</p>
        <button className="ghost" onClick={load}>
          Réessayer
        </button>
      </div>
    )
  }

  if (!state) {
    return (
      <div className="shell boot">
        <span className="label">Chargement…</span>
      </div>
    )
  }

  // La cérémonie passe avant tout le reste : elle occupe l'écran entier, et
  // c'est ce qui la distingue d'une notification.
  if (ceremony) {
    return (
      <SeasonCeremony
        report={ceremony.report}
        offer={ceremony.offer}
        onDone={() => {
          setCeremony(null)
          load()
          checkSeason()
        }}
      />
    )
  }

  // Une session en cours prend tout l'écran : plus d'onglets, plus de HUD.
  if (state.running_session) {
    return <SessionScreen session={state.running_session} onFinished={load} />
  }

  // Le palier 3 du §14 prend l'écran entier, barre d'onglets comprise. C'est le
  // sens de « l'accueil devient un écran unique de reprise » : laisser les
  // onglets, ce serait laisser la possibilité d'aller regarder ailleurs, et
  // c'est justement ce qu'on ne propose plus à quelqu'un qui revient.
  if (state.sanctions.comeback) {
    return (
      <Comeback
        proposal={state.proposal}
        exitOffer={exitOffer}
        onStarted={load}
        onExit={async () => {
          const bilan = await api.closeSeason(true)
          setCeremony({ report: bilan, offer: bilan.offer! })
        }}
      />
    )
  }

  const locked = state.sanctions.showcase_locked

  return (
    <>
      <main className="shell">
        {tab === 'soir' && <Home state={state} onStarted={load} />}
        {tab === 'projets' && <Projects onChanged={load} />}
        {tab === 'perso' && <Character locked={locked} phantom={state.phantom} />}
        {tab === 'journal' && <Journal />}
      </main>
      {/* La vitrine fermée grise l'onglet mais ne le retire pas : un onglet qui
          disparaît se lit comme une panne, et le §14 veut une sanction lisible
          comme telle. */}
      <TabBar active={tab} onChange={setTab} lockedTabs={locked ? ['perso'] : []} />
    </>
  )
}

/** L'accent de saison surcharge une seule variable. Le mode terne est la
 *  sanction de palier 1 : l'interface s'éteint jusqu'à la prochaine session. */
function applySeasonTheme(home: HomeState) {
  const root = document.body
  if (home.season) root.style.setProperty('--accent', home.season.accent)
  root.classList.toggle('terne', home.streak.sanction_level >= 1 && !home.validated_today)
}

function LoginScreen({ onDone }: { onDone: () => void }) {
  const [username, setUsername] = useState('arthur')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    try {
      await login(username, password)
      onDone()
    } catch {
      setError('Identifiants refusés.')
    }
  }

  return (
    <div className="shell boot">
      <h1 className="boot__title">Coach</h1>
      <p className="muted">Le cadre, pas les encouragements.</p>
      <form className="stack boot__form" onSubmit={submit}>
        <input
          className="fridge__input"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Utilisateur"
          aria-label="Utilisateur"
        />
        <input
          className="fridge__input"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Mot de passe"
          aria-label="Mot de passe"
        />
        {error && <p className="boot__error">{error}</p>}
        <button className="cta" type="submit">
          Entrer
        </button>
      </form>
    </div>
  )
}
