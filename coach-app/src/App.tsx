import { useCallback, useEffect, useState } from 'react'
import { ApiError, api, login, storedToken } from './api'
import type { HomeState } from './types'
import { Home } from './screens/Home'
import { SessionScreen } from './screens/SessionScreen'
import './App.css'

export default function App() {
  const [state, setState] = useState<HomeState | null>(null)
  const [error, setError] = useState('')
  const [authed, setAuthed] = useState(() => Boolean(storedToken()))
  const [now, setNow] = useState(new Date())

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
    // Repli de synchronisation en attendant le flux SSE du jalon suivant.
    const id = setInterval(load, 10_000)
    return () => clearInterval(id)
  }, [authed, load])

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

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

  if (state.running_session) {
    return <SessionScreen session={state.running_session} onFinished={load} />
  }

  return <Home state={state} now={now} onStarted={load} onRefresh={load} />
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
