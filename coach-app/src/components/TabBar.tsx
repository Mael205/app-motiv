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
 * identité ne sera pas utilisée. C'est aussi pour ça qu'il se ferme au palier 1
 * du §14 — on ne consulte pas ses trophées un soir où l'on n'a rien fait.
 *
 * Un onglet verrouillé reste **cliquable**. Le désactiver ne dirait pas
 * pourquoi, et une sanction qu'on prend pour un bug ne sanctionne rien : le
 * cadenas annonce, l'écran explique.
 */
export function TabBar({
  active,
  onChange,
  lockedTabs = [],
}: {
  active: Tab
  onChange: (tab: Tab) => void
  lockedTabs?: Tab[]
}) {
  return (
    <nav className="tabbar">
      {TABS.map((tab) => {
        const Glyph = tab.icon
        const locked = lockedTabs.includes(tab.id)
        return (
          <button
            key={tab.id}
            className={`tabbar__item${active === tab.id ? ' tabbar__item--active' : ''}${
              locked ? ' tabbar__item--locked' : ''
            }`}
            onClick={() => onChange(tab.id)}
            aria-current={active === tab.id}
          >
            <Glyph size={21} />
            {/* Espace insécable : en colonne sur téléphone, un espace ordinaire
                renvoyait le cadenas à la ligne sous le libellé. */}
            <span aria-label={locked ? `${tab.label}, fermé jusqu'à la prochaine session` : undefined}>
              {locked ? `${tab.label} ⌧` : tab.label}
            </span>
          </button>
        )
      })}
    </nav>
  )
}
