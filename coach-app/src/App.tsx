import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api, login, storedToken } from './api'
import type {
  AnneeAccomplie,
  HomeState,
  ModeExtra,
  SeasonOffer,
  SeasonPhase,
  SeasonReport,
} from './types'
import { Comeback } from './components/Comeback'
import { SeasonCeremony } from './components/SeasonCeremony'
import { Home } from './screens/Home'
import { Character } from './screens/Character'
import { Journal } from './screens/Journal'
import { Projects } from './screens/Projects'
import { SessionScreen } from './screens/SessionScreen'
import { Ascendance } from './components/Ascendance'
import { Assistant, AssistantButton } from './components/Assistant'
import { Partage } from './components/Partage'
import { TabBar, type Tab } from './components/TabBar'
import { TimezoneNotice } from './components/TimezoneNotice'
import { applySeasonTheme } from './accents'
import { reparerLAbonnement } from './push'
import { animerEntree } from './juice'
import './App.css'

export default function App() {
  const [state, setState] = useState<HomeState | null>(null)
  const [error, setError] = useState('')
  const [authed, setAuthed] = useState(() => Boolean(storedToken()))
  const [tab, setTab] = useState<Tab>('soir')
  const [assistant, setAssistant] = useState(false)
  const [annee, setAnnee] = useState<AnneeAccomplie | null>(null)
  // La cérémonie du §7.4 : une saison finie pendant qu'on ne regardait pas doit
  // se conclure quand on revient, pas rester en suspens jusqu'à un déclencheur.
  const [ceremony, setCeremony] = useState<{ report: SeasonReport | null; offer: SeasonOffer } | null>(null)
  // La porte de sortie du §14. Gardée à part de la cérémonie : celle-ci
  // s'impose, celle-là se propose et peut rester ignorée des semaines.
  const [exitOffer, setExitOffer] = useState<SeasonPhase['exit_offer']>(null)
  /** Le mode extra du §12.4 : le boss est tombé, la saison suivante attend sa
   *  date. Sans cet état, l'écran ne montrait plus ni saison ni explication —
   *  et l'offre se reproposait en boucle. */
  const [extra, setExtra] = useState<ModeExtra | null>(null)

  const checkSeason = useCallback(async () => {
    try {
      const etat = await api.seasonState()
      setExitOffer(etat.exit_offer)
      setExtra(etat.extra)
      // L'année close dont la voie n'a pas été tranchée passe avant tout : une
      // treizième saison ouverte sans ascendance repartirait sur l'ancienne
      // échelle d'XP, et le choix serait perdu.
      setAnnee(etat.annee)
      if (etat.pending_close) {
        const bilan = await api.closeSeason()
        // L'offre peut manquer : une saison suivante déjà engagée qui attend sa
        // date n'est plus re-proposée (mode extra du §12.4). La cérémonie ne se
        // monte alors pas, plutôt que de se monter sans ce qu'elle demande.
        const offre = bilan.offer ?? etat.offer
        setCeremony(offre ? { report: bilan, offer: offre } : null)
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

  /** Un abonnement Web Push expire tout seul au bout de quelques semaines, et
   *  personne ne s'en aperçoit : les notifications cessent simplement d'arriver.
   *  On le répare à chaque ouverture, en silence et **sans jamais demander la
   *  permission** — celle-ci se demande sur un geste, dans le journal. */
  useEffect(() => {
    if (authed) reparerLAbonnement()
  }, [authed])

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

  // L'ascendance passe avant la cérémonie de saison : elle est plus rare, et
  // la saison suivante ne doit pas s'ouvrir avant que la voie soit gravée.
  if (annee) {
    return (
      <Ascendance
        annee={annee}
        onDone={() => {
          setAnnee(null)
          load()
          checkSeason()
        }}
      />
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
        {/* Au-dessus de tout, y compris de la décision : un écart de fuseau
            rend faux tout ce qui suit — la fenêtre du soir, l'heure du gardien,
            la journée à laquelle une session sera comptée. */}
        <TimezoneNotice />

        {/* Les quatre onglets se remplaçaient sans transition : le contenu
            changeait entre deux images, et rien ne disait ni qu'il avait
            changé, ni d'où il venait. C'est de l'orientation, pas de la
            décoration, et le §7 l'autorise à ce titre.

            Pas de `key` ici : le conteneur doit survivre au changement
            d'onglet pour se souvenir duquel on vient, et c'est ce souvenir qui
            donne sa direction à l'entrée. Ce sont les écrans à l'intérieur qui
            se remontent, puisque leur type change. */}
        <ScreenTransition tab={tab}>
          {tab === 'soir' && <Home state={state} extra={extra} onStarted={load} />}
          {tab === 'projets' && <Projects onChanged={load} />}
          {tab === 'perso' && <Character locked={locked} phantom={state.phantom} />}
          {tab === 'journal' && <Journal />}
        </ScreenTransition>
      </main>
      {/* La vitrine fermée grise l'onglet mais ne le retire pas : un onglet qui
          disparaît se lit comme une panne, et le §14 veut une sanction lisible
          comme telle. */}
      <TabBar active={tab} onChange={setTab} lockedTabs={locked ? ['perso'] : []} />

      {/* L'assistant n'est pas un onglet : les onglets sont les endroits où
          l'on va, lui est quelque chose qu'on appelle. Un cinquième onglet en
          aurait fait une destination, donc un endroit où traîner un soir de
          fatigue — ce que le §11.1 cherche à éviter. */}
      {/* Ce qui arrive du menu « Partager » d'Android. Au-dessus des onglets et
          hors de tous : un partage ne vient d'aucun écran. */}
      <Partage />

      {!assistant && <AssistantButton onOpen={() => setAssistant(true)} />}
      {assistant && (
        <Assistant onClose={() => setAssistant(false)} onApplied={load} />
      )}
    </>
  )
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
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Utilisateur"
          aria-label="Utilisateur"
        />
        <input
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

/** L'ordre des onglets, tel qu'il est peint dans la barre. Il sert à savoir de
 *  quel côté un écran arrive : c'est ce qui rend la barre spatiale. */
const ORDRE: Tab[] = ['soir', 'projets', 'perso', 'journal']

/** L'entrée d'un écran d'onglet.
 *
 * Un seul mouvement, sur le conteneur, et il vient du côté d'où l'on vient :
 * aller vers la droite de la barre fait entrer l'écran par la droite. Un fondu
 * seul disait « autre chose » ; la direction dit « autre chose, **par là** »,
 * et c'est ce qui fait qu'on garde la carte des quatre onglets en tête.
 *
 * Pas de cascade par section — les onglets Projets et Personnage en portent
 * plus de dix, et un décalage par section ferait attendre une demi-seconde
 * avant que le bas de l'écran existe. Ce sont les cartes elles-mêmes qui se
 * lèvent au défilement, une fois l'écran posé.
 *
 * Sur le conteneur et non sur son contenu : Projets et Journal affichent
 * « Chargement… » avant leurs données, et animer le contenu revenait à animer
 * ce mot puis à laisser le reste surgir d'un coup.
 *
 * `prefers-reduced-motion` est géré dans `animerEntree`, qui pose alors l'état
 * final sans animer.
 */
function ScreenTransition({ tab, children }: { tab: Tab; children: React.ReactNode }) {
  const boite = useRef<HTMLDivElement>(null)
  const precedent = useRef<Tab | null>(null)

  useEffect(() => {
    if (!boite.current) return
    const avant = precedent.current
    precedent.current = tab
    // Zéro au premier montage : rien ne précède, donc rien n'a de côté.
    const sens = avant === null ? 0 : Math.sign(ORDRE.indexOf(tab) - ORDRE.indexOf(avant))
    return animerEntree(boite.current, sens)
  }, [tab])

  return (
    <div className="screen" ref={boite}>
      {children}
    </div>
  )
}
