import { Icon } from './art/Icons'
import './TabBar.css'

export type Tab = 'soir' | 'projets' | 'journal'

const TABS: { id: Tab; label: string; icon: (p: { size?: number }) => React.ReactElement }[] = [
  { id: 'soir', label: 'Ce soir', icon: Icon.target },
  { id: 'projets', label: 'Projets', icon: Icon.map },
  { id: 'journal', label: 'Journal', icon: Icon.book },
]

/** La navigation.
 *
 * Trois onglets, pas plus. L'accueil ne porte que la décision du soir : tout
 * ce qui se consulte (roadmaps, journal, frigo) vit ailleurs, sinon l'écran
 * qui doit déclencher l'action devient un tableau de bord.
 */
export function TabBar({ active, onChange }: { active: Tab; onChange: (tab: Tab) => void }) {
  return (
    <nav className="tabbar">
      {TABS.map((tab) => {
        const Glyph = tab.icon
        return (
          <button
            key={tab.id}
            className={`tabbar__item${active === tab.id ? ' tabbar__item--active' : ''}`}
            onClick={() => onChange(tab.id)}
            aria-current={active === tab.id}
          >
            <Glyph size={21} />
            <span>{tab.label}</span>
          </button>
        )
      })}
    </nav>
  )
}
