/** L'atmosphère d'une saison : le décor du bandeau.
 *
 * Vingt-quatre saisons ne se distinguaient que par une teinte. Le sceau et la
 * frise changeaient bien, mais dans un cadre identique — Hellfest et Nadir
 * étaient la même boîte repeinte, et une saison qu'on ne reconnaît pas d'un
 * regard n'a pas d'identité au sens du §0.10.
 *
 * Neuf atmosphères, chacune un vrai traitement : de la lave qui palpite sous
 * des fissures, des ailes et des rais de lumière, de la cendre qui tombe, un
 * abysse traversé de bulles. Chaque saison en reçoit une, et reste unique dans
 * son atmosphère par sa **paire** de couleurs — `--accent` et `--accent2`
 * viennent du serveur, l'atmosphère ne fait que s'en peindre.
 *
 * Pourquoi neuf et pas vingt-quatre : une illustration par saison serait vingt-
 * quatre fichiers que personne ne pourrait tenir à jour, et qu'on ne pourrait
 * pas vérifier. Neuf familles bien tenues, croisées avec vingt-quatre paires de
 * couleurs, vingt-quatre sceaux et vingt-quatre frises, donnent vingt-quatre
 * écrans qui ne se ressemblent pas — sans jamais un pixel qu'on ne sache
 * redessiner.
 *
 * Tout est SVG et CSS. Aucune image, aucun `filter: blur` sur un chemin
 * critique, et l'ensemble est décoratif : `aria-hidden` partout, et rien ici ne
 * capte un clic.
 */

import './SeasonAtmosphere.css'

type Props = { ambiance?: string }

/** Un identifiant de dégradé unique par atmosphère. Deux `<defs>` portant le
 *  même `id` dans un document se marchent dessus — le second est ignoré, et la
 *  seconde atmosphère se peint avec les couleurs de la première. */
const ID = (nom: string) => `atm-${nom}`

const ATMOSPHERES: Record<string, () => React.ReactElement> = {
  /* Lave — Hellfest, Inferno, Phénix.
     Des fissures incandescentes sous une croûte sombre, et des braises qui
     montent. La palpitation est lente : c'est une masse en fusion, pas un feu
     de camp. */
  lave: () => (
    <>
      <svg className="atm__scene" viewBox="0 0 400 140" preserveAspectRatio="none" aria-hidden>
        <defs>
          <linearGradient id={ID('lave')} x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="var(--accent2)" stopOpacity="0.55" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <rect width="400" height="140" fill={`url(#${ID('lave')})`} />
        <g className="atm__fissures" stroke="var(--accent2)" fill="none" strokeLinecap="round">
          <path d="M-10 128 L60 112 L96 122 L150 104 L210 118 L268 100 L330 114 L410 98" strokeWidth="2" />
          <path d="M-10 138 L48 130 L110 136 L168 124 L230 134 L300 122 L360 132 L410 120" strokeWidth="1.2" opacity=".6" />
          <path d="M40 140 L58 120 L52 104" strokeWidth="1" opacity=".45" />
          <path d="M250 140 L262 118 L256 102" strokeWidth="1" opacity=".45" />
        </g>
      </svg>
      <span className="atm__braises" aria-hidden>
        {Array.from({ length: 14 }, (_, i) => (
          <i key={i} style={{ ['--i' as string]: i }} />
        ))}
      </span>
    </>
  ),

  /* Forge — Dernier Rempart, Dernière Forge.
     Pas de lave libre : du métal chauffé, une enclume, des étincelles courtes
     et sèches qui partent sur les côtés au lieu de monter. */
  forge: () => (
    <>
      <svg className="atm__scene" viewBox="0 0 400 140" preserveAspectRatio="none" aria-hidden>
        <defs>
          <radialGradient id={ID('forge')} cx="0.5" cy="1" r="0.9">
            <stop offset="0%" stopColor="var(--accent2)" stopOpacity="0.5" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </radialGradient>
        </defs>
        <ellipse cx="200" cy="150" rx="220" ry="80" fill={`url(#${ID('forge')})`} />
        {/* L'enclume et le lit de braises. La version précédente n'avait qu'un
            halo et deux traits : sur la planche, la forge était la seule
            atmosphère qu'on ne distinguait pas d'un fond vide. */}
        {/* L'enclume, avec sa corne et son pied — la silhouette est ce qui la
            rend reconnaissable. Un simple trapèze se lisait comme une forme
            posée là, sans nom. */}
        <path
          className="atm__metal"
          d="M158 128h84v-6h-14v-8h22l-10-8h-80l-10 8h22v8h-14Z"
          fill="var(--accent2)"
          opacity=".5"
        />
        <path d="M182 106h36v-8h-36Z" fill="var(--accent)" opacity=".45" />
        <g stroke="var(--accent2)" fill="none" strokeWidth="1.6" opacity=".5">
          <path d="M0 132h400" />
          <path d="M0 122h130M270 122h130" opacity=".7" />
        </g>
        <g fill="var(--accent2)" opacity=".35">
          <circle cx="52" cy="136" r="3" />
          <circle cx="96" cy="132" r="2" />
          <circle cx="330" cy="134" r="3" />
          <circle cx="366" cy="130" r="2" />
        </g>
      </svg>
      <span className="atm__etincelles" aria-hidden>
        {Array.from({ length: 10 }, (_, i) => (
          <i key={i} style={{ ['--i' as string]: i }} />
        ))}
      </span>
    </>
  ),

  /* Ailes — Ascension, Heaven's Paradise, L'Empyrée.
     Des rais de lumière qui descendent, et deux arcs de plumes qui s'ouvrent.
     Le blanc vient de `--accent2` : ces saisons-là l'ont à blanc pur. */
  ailes: () => (
    <>
      <svg className="atm__scene" viewBox="0 0 400 140" preserveAspectRatio="none" aria-hidden>
        <defs>
          <linearGradient id={ID('ailes')} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent2)" stopOpacity="0.42" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <g className="atm__rais" fill={`url(#${ID('ailes')})`}>
          <path d="M120 -20 L150 -20 L92 150 L54 150 Z" />
          <path d="M200 -20 L222 -20 L186 150 L158 150 Z" opacity=".7" />
          <path d="M290 -20 L318 -20 L272 150 L236 150 Z" opacity=".5" />
        </g>
        <g stroke="var(--accent2)" fill="none" strokeWidth="1.3" opacity=".5">
          <path d="M40 96c26-22 54-30 84-24-24 6-42 18-54 34" />
          <path d="M360 96c-26-22-54-30-84-24 24 6 42 18 54 34" />
        </g>
      </svg>
      <span className="atm__plumes" aria-hidden>
        {Array.from({ length: 9 }, (_, i) => (
          <i key={i} style={{ ['--i' as string]: i }} />
        ))}
      </span>
    </>
  ),

  /* Or — Valhalla, Couronne Solaire, Apothéose.
     Une couronne de rayons qui tourne très lentement, et une poussière dorée
     en suspension. Rien ne tombe et rien ne monte : ça rayonne. */
  or: () => (
    <>
      <svg className="atm__scene atm__scene--or" viewBox="0 0 400 140" preserveAspectRatio="none" aria-hidden>
        <defs>
          <radialGradient id={ID('or')} cx="0.5" cy="0.35" r="0.7">
            <stop offset="0%" stopColor="var(--accent2)" stopOpacity="0.55" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </radialGradient>
        </defs>
        <ellipse cx="200" cy="50" rx="200" ry="90" fill={`url(#${ID('or')})`} />
        <g className="atm__couronne" stroke="var(--accent2)" strokeWidth="1.2" opacity=".45">
          {Array.from({ length: 16 }, (_, i) => {
            const a = (i / 16) * Math.PI * 2
            return (
              <line
                key={i}
                x1={200 + Math.cos(a) * 34}
                y1={50 + Math.sin(a) * 34}
                x2={200 + Math.cos(a) * 58}
                y2={50 + Math.sin(a) * 58}
              />
            )
          })}
        </g>
      </svg>
      <span className="atm__poussiere" aria-hidden>
        {Array.from({ length: 12 }, (_, i) => (
          <i key={i} style={{ ['--i' as string]: i }} />
        ))}
      </span>
    </>
  ),

  /* Aurore — L'Éveil, Aube Rouge, Élysion.
     Deux voiles qui ondulent lentement, comme une aurore basse sur l'horizon.
     Aucune particule : c'est le seul décor entièrement calme. */
  aurore: () => (
    <svg className="atm__scene" viewBox="0 0 400 140" preserveAspectRatio="none" aria-hidden>
      <defs>
        <linearGradient id={ID('aurore')} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.45" />
          <stop offset="50%" stopColor="var(--accent2)" stopOpacity="0.32" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.08" />
        </linearGradient>
      </defs>
      <path
        className="atm__voile"
        fill={`url(#${ID('aurore')})`}
        d="M-20 96C60 60 120 108 200 78s140 4 220-30v100H-20Z"
      />
      <path
        className="atm__voile atm__voile--deux"
        fill={`url(#${ID('aurore')})`}
        opacity=".55"
        d="M-20 118C70 92 130 128 210 104s130 10 210-16v52H-20Z"
      />
    </svg>
  ),

  /* Vitrail — La Porte d'Ivoire, Sanctuaire.
     Des ogives et des meneaux. La lumière passe à travers, elle ne vient pas
     du décor : c'est une architecture, pas un phénomène. */
  vitrail: () => (
    <svg className="atm__scene" viewBox="0 0 400 140" preserveAspectRatio="none" aria-hidden>
      <defs>
        <linearGradient id={ID('vitrail')} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.4" />
          <stop offset="100%" stopColor="var(--accent2)" stopOpacity="0.05" />
        </linearGradient>
      </defs>
      <g fill={`url(#${ID('vitrail')})`} stroke="var(--accent2)" strokeWidth="1" opacity=".7">
        <path d="M40 140V70a26 26 0 0 1 52 0v70Z" />
        <path d="M118 140V56a30 30 0 0 1 60 0v84Z" opacity=".8" />
        <path d="M204 140V44a34 34 0 0 1 68 0v96Z" opacity=".6" />
        <path d="M298 140V64a28 28 0 0 1 56 0v76Z" opacity=".45" />
      </g>
      <g stroke="var(--accent2)" strokeWidth="0.8" opacity=".35">
        <path d="M66 140V72M148 140V58M238 140V46M326 140V66" />
      </g>
    </svg>
  ),

  /* Orage — Ragnarök, Tonnerre.
     Un front de nuages bas et un éclair qui frappe rarement. La rareté est le
     sujet : un éclair toutes les deux secondes serait un stroboscope. */
  orage: () => (
    <>
      <svg className="atm__scene" viewBox="0 0 400 140" preserveAspectRatio="none" aria-hidden>
        <defs>
          <linearGradient id={ID('orage')} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent2)" stopOpacity="0.5" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.05" />
          </linearGradient>
        </defs>
        <path
          fill={`url(#${ID('orage')})`}
          d="M-20 0h440v54c-40 18-72-6-112 4s-58 22-96 12-62-26-104-14S10 78-20 62Z"
        />
        {/* Le ventre des nuages, marqué. Un front dessiné d'un seul aplat se
            perdait dans le fond du panneau ; ce sont ses bosses qui disent
            « bas et lourd ». */}
        {/* Un seul contour, pas trois aplats. La version à ellipses pleines
            donnait de grandes taches pâles qu'on lisait comme des salissures :
            c'est le **dessous** d'un front qui dit « bas et lourd », pas sa
            masse. */}
        <path
          d="M-20 58c34-22 62 4 98-6s54-26 92-16 60 30 98 20 44-20 72-8"
          fill="none"
          stroke="var(--accent2)"
          strokeWidth="2"
          opacity=".38"
        />
        <path
          d="M-20 46c30-18 58 2 90-6s50-22 84-14 56 26 90 18 42-18 66-6"
          fill="none"
          stroke="var(--accent2)"
          strokeWidth="1.2"
          opacity=".22"
        />
        <path className="atm__eclair" stroke="var(--accent2)" strokeWidth="3" fill="none"
          d="M214 44l-20 40h24l-18 42" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="atm__pluie" aria-hidden>
        {Array.from({ length: 16 }, (_, i) => (
          <i key={i} style={{ ['--i' as string]: i }} />
        ))}
      </span>
    </>
  ),

  /* Abysse — La Chute, Nadir, Le Styx.
     Le fond est plus sombre en bas qu'en haut, l'inverse de tout le reste, et
     des bulles rares remontent. Rien ne descend : on est déjà au fond. */
  abysse: () => (
    <>
      <svg className="atm__scene" viewBox="0 0 400 140" preserveAspectRatio="none" aria-hidden>
        <defs>
          <linearGradient id={ID('abysse')} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.34" />
            <stop offset="100%" stopColor="var(--accent2)" stopOpacity="0.72" />
          </linearGradient>
        </defs>
        <rect width="400" height="140" fill={`url(#${ID('abysse')})`} />
        {/* Les colonnes de lumière qui plongent depuis la surface, et le relief
            du fond. Sans elles, l'abysse n'était qu'un dégradé sombre : trois
            saisons sur une planche de vingt-quatre ne montraient rien du tout,
            ce qui se lit comme un décor manquant plutôt que comme un fond. */}
        <g className="atm__colonnes" fill="var(--accent)" opacity=".22">
          <path d="M70 -10h26L78 150H44Z" />
          <path d="M190 -10h18l-14 160h-26Z" opacity=".7" />
          <path d="M310 -10h30l-26 160h-40Z" opacity=".5" />
        </g>
        <g stroke="var(--accent)" fill="none" strokeWidth="1.4" opacity=".45">
          <path d="M-10 110c60-14 100 10 160-4s120 12 260-8" />
          <path d="M-10 128c70-10 110 12 170 0s110 10 250-10" opacity=".6" />
        </g>
        <path d="M-10 140l60-26 50 16 70-22 60 20 70-24 110 30v6H-10Z"
          fill="var(--accent2)" opacity=".8" />
      </svg>
      <span className="atm__bulles" aria-hidden>
        {Array.from({ length: 8 }, (_, i) => (
          <i key={i} style={{ ['--i' as string]: i }} />
        ))}
      </span>
    </>
  ),

  /* Cendre — Le Purgatoire, Solstice Noir, Cendres.
     Elle tombe, lentement, en dérivant. C'est le seul décor où quelque chose
     descend — et c'est exactement ce que ces trois saisons racontent. */
  cendre: () => (
    <>
      <svg className="atm__scene" viewBox="0 0 400 140" preserveAspectRatio="none" aria-hidden>
        <defs>
          <linearGradient id={ID('cendre')} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent2)" stopOpacity="0.42" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.14" />
          </linearGradient>
        </defs>
        <rect width="400" height="140" fill={`url(#${ID('cendre')})`} />
        <g fill="var(--accent)" opacity=".28">
          <path d="M-10 140l70-34 52 20 68-30 74 26 66-24 90 32v10Z" />
        </g>
        {/* Ce qui rougeoie encore sous la cendre. C'est le détail qui sépare
            « éteint » de « refroidi », et les trois saisons de cet acte parlent
            précisément de cette différence. */}
        <g className="atm__tisons" fill="var(--accent)" opacity=".5">
          <circle cx="66" cy="118" r="2.5" />
          <circle cx="176" cy="122" r="2" />
          <circle cx="252" cy="116" r="3" />
          <circle cx="338" cy="124" r="2" />
        </g>
      </svg>
      <span className="atm__cendre" aria-hidden>
        {Array.from({ length: 18 }, (_, i) => (
          <i key={i} style={{ ['--i' as string]: i }} />
        ))}
      </span>
    </>
  ),
}

export function SeasonAtmosphere({ ambiance }: Props) {
  const Decor = ATMOSPHERES[ambiance ?? '']
  // Sans atmosphère connue — une saison d'archive dont la clé a quitté la
  // trame —, on ne dessine rien plutôt qu'un décor au hasard : un fond neutre
  // se lit comme une saison ancienne, un mauvais décor se lit comme un bug.
  if (!Decor) return null

  return (
    <div className={`atm atm--${ambiance}`} aria-hidden>
      <Decor />
    </div>
  )
}
