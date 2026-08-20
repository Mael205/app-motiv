/** Banc d'essai des saisons — les vingt-quatre côte à côte.
 *
 * Une identité de saison ne se juge pas une saison à la fois : la question
 * n'est pas « Hellfest est-il beau ? » mais « reconnaît-on Hellfest de Nadir
 * sans lire leur nom ? ». Il fallait vingt-huit jours pour voir la suivante,
 * donc deux ans pour comparer les vingt-quatre — autant dire jamais.
 *
 * Ouvrir `/saisons.html` avec le serveur de développement.
 *
 * La table est recopiée du serveur (`forge/rules/seasons.py`) et non lue par
 * l'API : ce banc doit pouvoir afficher une saison qu'on est en train
 * d'écrire, avant même qu'elle existe en base.
 */

import { createRoot } from 'react-dom/client'
import { SeasonAtmosphere } from '../components/art/SeasonAtmosphere'
import { SeasonOrnament, SeasonSigil } from '../components/art/SeasonSigil'
import '../styles/theme.css'
import '../components/SeasonBanner.css'
import './saisons.css'

type Identite = {
  key: string
  name: string
  accent: string
  accent2: string
  ambiance: string
  baseline: string
}

const CIMES: Identite[] = [
  { key: 'eveil', name: "L'Éveil", accent: '#8FD14F', accent2: '#E4F7B0', ambiance: 'aurore', baseline: 'Ce qui dormait se lève. À toi de savoir quoi.' },
  { key: 'aube_rouge', name: 'Aube Rouge', accent: '#E8734A', accent2: '#F5C177', ambiance: 'aurore', baseline: 'Vingt-huit levers. Compte-les.' },
  { key: 'porte_ivoire', name: "La Porte d'Ivoire", accent: '#E8DCC0', accent2: '#B9A47A', ambiance: 'vitrail', baseline: "Par l'une passent les songes, par l'autre ce qui arrive." },
  { key: 'sanctuaire', name: 'Sanctuaire', accent: '#C8A2D8', accent2: '#7E6BA8', ambiance: 'vitrail', baseline: "L'endroit qu'on défend n'est pas celui où l'on dort." },
  { key: 'elysion', name: 'Élysion', accent: '#A9D9A2', accent2: '#E6DC92', ambiance: 'aurore', baseline: "Le repos se gagne. C'est tout ce qui le distingue de l'oubli." },
  { key: 'ascension', name: 'Ascension', accent: '#6FC4E8', accent2: '#D2ECFA', ambiance: 'ailes', baseline: 'Personne ne monte par accident.' },
  { key: 'valhalla', name: 'Valhalla', accent: '#D4A94E', accent2: '#8C6B3A', ambiance: 'or', baseline: "La salle est pleine de gens qui ont fini ce qu'ils avaient commencé." },
  { key: 'ragnarok', name: 'Ragnarök', accent: '#8FA9C4', accent2: '#4A5A72', ambiance: 'orage', baseline: 'Tout finit. La question est ce que tu auras bâti avant.' },
  { key: 'couronne_solaire', name: 'Couronne Solaire', accent: '#F0C040', accent2: '#FFF2B8', ambiance: 'or', baseline: "On ne la voit que pendant l'éclipse. Vingt-huit jours." },
  { key: 'heavens_paradise', name: "Heaven's Paradise", accent: '#F2E6C2', accent2: '#FFFFFF', ambiance: 'ailes', baseline: 'On monte, ou on regarde monter.' },
  { key: 'apotheose', name: 'Apothéose', accent: '#FFD86B', accent2: '#FFF7D6', ambiance: 'or', baseline: "Le mois où l'on cesse d'être celui qui essaie." },
  { key: 'empyree', name: "L'Empyrée", accent: '#BFE3FF', accent2: '#FFFFFF', ambiance: 'ailes', baseline: "Le ciel de feu, tout en haut. Il n'y a rien au-dessus." },
]

const BRAISES: Identite[] = [
  { key: 'chute', name: 'La Chute', accent: '#6E5B8F', accent2: '#2E2340', ambiance: 'abysse', baseline: "Elle a déjà eu lieu. Reste à savoir jusqu'où." },
  { key: 'nadir', name: 'Nadir', accent: '#3E6FA8', accent2: '#16283F', ambiance: 'abysse', baseline: 'Le point le plus bas est un point de départ comme un autre.' },
  { key: 'styx', name: 'Le Styx', accent: '#4C7A6B', accent2: '#14261F', ambiance: 'abysse', baseline: 'On ne traverse pas deux fois le même fleuve. On le traverse une.' },
  { key: 'purgatoire', name: 'Le Purgatoire', accent: '#8A6FB0', accent2: '#4A3866', ambiance: 'cendre', baseline: 'Ni en haut, ni en bas. Vingt-huit jours pour trancher.' },
  { key: 'solstice_noir', name: 'Solstice Noir', accent: '#B98A2E', accent2: '#3A2E14', ambiance: 'cendre', baseline: 'La nuit la plus longue se travaille.' },
  { key: 'cendres', name: 'Cendres', accent: '#A89484', accent2: '#4A3E36', ambiance: 'cendre', baseline: 'Ce qui a brûlé fertilise ou stérilise. Ça se décide maintenant.' },
  { key: 'hellfest', name: 'Hellfest', accent: '#E0533D', accent2: '#FF9A2B', ambiance: 'lave', baseline: 'Quatre semaines. Le feu ne demande pas la permission.' },
  { key: 'inferno', name: 'Inferno', accent: '#F07A20', accent2: '#FFB347', ambiance: 'lave', baseline: 'Ça chauffe à partir de maintenant.' },
  { key: 'tonnerre', name: 'Tonnerre', accent: '#D6543C', accent2: '#9FB3C8', ambiance: 'orage', baseline: 'Le bruit arrive après. Toujours.' },
  { key: 'dernier_rempart', name: 'Le Dernier Rempart', accent: '#C0574F', accent2: '#7A3F3A', ambiance: 'forge', baseline: 'Ils passeront par toi.' },
  { key: 'derniere_forge', name: 'La Dernière Forge', accent: '#E0703D', accent2: '#FFB067', ambiance: 'forge', baseline: "Le feu s'éteint à la fin du mois. Pas avant." },
  { key: 'phenix', name: 'Phénix', accent: '#FF9A3C', accent2: '#FFE39A', ambiance: 'lave', baseline: 'Il ne revient pas malgré le feu. Il revient par lui.' },
]

function Carte({ s, rang }: { s: Identite; rang: number }) {
  return (
    <article
      className="essai"
      style={{ ['--accent' as string]: s.accent, ['--accent2' as string]: s.accent2 }}
    >
      <SeasonAtmosphere ambiance={s.ambiance} />
      <div className="essai__corps">
        <div className="essai__tete">
          <SeasonSigil seasonKey={s.key} size={46} className="essai__sigil" />
          <div>
            <h2 className="essai__nom display">{s.name}</h2>
            <span className="essai__meta">
              {rang} · {s.ambiance} · {s.accent} / {s.accent2}
            </span>
          </div>
        </div>
        <p className="essai__baseline">{s.baseline}</p>
        <SeasonOrnament seasonKey={s.key} />
      </div>
    </article>
  )
}

function Banc() {
  return (
    <main className="banc">
      <h1 className="banc__titre display">Les vingt-quatre saisons</h1>
      <p className="banc__note">
        Deux voies de douze. La haute s'ouvre après une saison tenue, la basse après une saison
        ratée — et la basse ne retire rien : même mise, même boss, seul le décor change.
      </p>

      <h2 className="banc__voie display">Voie des Cimes — du réveil à l'Empyrée</h2>
      <div className="banc__grille">
        {CIMES.map((s, i) => (
          <Carte key={s.key} s={s} rang={i + 1} />
        ))}
      </div>

      <h2 className="banc__voie display">Voie des Braises — la chute, le feu, la reforge</h2>
      <div className="banc__grille">
        {BRAISES.map((s, i) => (
          <Carte key={s.key} s={s} rang={i + 1} />
        ))}
      </div>
    </main>
  )
}

createRoot(document.getElementById('root')!).render(<Banc />)
