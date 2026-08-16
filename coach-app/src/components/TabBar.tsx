import { Icon } from './art/Icons'
import './TabBar.css'

export type Tab = 'soir' | 'projets' | 'perso' | 'journal'

const TABS: { id: Tab; label: string; icon: (p: { size?: number }) => React.ReactElement }[] = [
  { id: 'soir', label: 'Ce soir', icon: Icon.target },
  { id: 'projets', label: 'Projets', icon: Icon.map },
  { id: 'perso', label: 'Personnage', icon: Icon.shield },
  { id: 'journal', label: 'Journal', icon: Icon.book },
]

/** La navigation.
 *
 * Quatre onglets, pas plus. L'accueil ne porte que la décision du soir : tout
 * ce qui se consulte — roadmaps, arbre, collection, journal — vit ailleurs,
 * sinon l'écran qui doit déclencher l'action devient un tableau de bord.
 *
 * « Personnage » est le seul onglet où l'on a le droit de flâner, et c'est
 * assumé : le §0.10 dit qu'une version fonctionnellement parfaite mais sans
 * identité ne sera pas utilisée.
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
