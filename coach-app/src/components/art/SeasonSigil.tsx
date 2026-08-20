/** Emblèmes de saison.
 *
 * Chaque saison porte son propre dessin : c'est ce qui lui donne une direction
 * artistique reconnaissable en une seconde, au-delà de la couleur d'accent
 * (SPEC §12.2). Tout est en SVG monochrome qui hérite de `currentColor`, donc
 * l'accent de la saison le teinte sans qu'on redessine quoi que ce soit.
 */

type SigilProps = { size?: number; className?: string }

const P = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' } as const

function Frame({ size = 44, className, children }: SigilProps & { children: React.ReactNode }) {
  return (
    <svg viewBox="0 0 48 48" width={size} height={size} className={className} aria-hidden>
      {children}
    </svg>
  )
}

export const SIGILS: Record<string, (p: SigilProps) => React.ReactElement> = {
  /* La Porte d'Ivoire — le double portail de Virgile. Par l'une passent les
     songes trompeurs, par l'autre ce qui arrive vraiment. Deux battants, un
     seul ouvert. */
  porte_ivoire: (p) => (
    <Frame {...p}>
      <path {...P} d="M10 42V18a14 14 0 0 1 28 0v24" />
      <path {...P} d="M24 8v34" />
      <path {...P} d="M17 42V20a7 7 0 0 1 7-7" opacity=".55" />
      <path {...P} d="M31 42V20a7 7 0 0 0-7-7" opacity=".8" />
      <path {...P} d="M6 42h36" />
    </Frame>
  ),

  /* Élysion — les champs. Trois épis et une ligne d'horizon : le repos se
     gagne, c'est tout ce qui le distingue de l'oubli. */
  elysion: (p) => (
    <Frame {...p}>
      <path {...P} d="M6 38h36" />
      <path {...P} d="M16 38V20M24 38V14M32 38V22" />
      <path {...P} d="M16 20c-4-2-5-5-4-8 3 1 5 4 4 8ZM16 20c4-2 5-5 4-8-3 1-5 4-4 8Z" opacity=".8" />
      <path {...P} d="M24 14c-4-2-5-5-4-8 3 1 5 4 4 8ZM24 14c4-2 5-5 4-8-3 1-5 4-4 8Z" />
      <path {...P} d="M32 22c-4-2-5-5-4-8 3 1 5 4 4 8ZM32 22c4-2 5-5 4-8-3 1-5 4-4 8Z" opacity=".8" />
    </Frame>
  ),

  /* Ascension — l'escalier qui monte vers un arc de lumière. Personne ne monte
     par accident : les marches sont dessinées, pas suggérées. */
  ascension: (p) => (
    <Frame {...p}>
      <path {...P} d="M6 42h8v-7h8v-7h8v-7h8V14" />
      <path {...P} d="M32 8a10 10 0 0 1 10 10" opacity=".7" />
      <path {...P} d="M24 6v6M18 9l3 4M30 9l-3 4" opacity=".5" />
    </Frame>
  ),

  /* Valhalla — la grande salle. Un fronton, des lances en appui, et la porte
     par laquelle on entre une fois le travail fini. */
  valhalla: (p) => (
    <Frame {...p}>
      <path {...P} d="M6 22 24 8l18 14" />
      <path {...P} d="M10 22v20h28V22" />
      <path {...P} d="M20 42V30a4 4 0 0 1 8 0v12" />
      <path {...P} d="M14 26v10M34 26v10" opacity=".55" />
    </Frame>
  ),

  /* Couronne Solaire — l'anneau qu'on ne voit que pendant l'éclipse. Le disque
     est plein et sombre ; ce sont les rais qui portent la saison. */
  couronne_solaire: (p) => (
    <Frame {...p}>
      <circle {...P} cx="24" cy="24" r="9" />
      <path {...P} d="M24 4v7M24 37v7M4 24h7M37 24h7" />
      <path {...P} d="M10 10l5 5M33 33l5 5M38 10l-5 5M15 33l-5 5" opacity=".75" />
      <path {...P} d="M24 8.5 26 12h-4l2-3.5ZM24 39.5 22 36h4l-2 3.5Z" opacity=".5" />
    </Frame>
  ),

  /* Apothéose — la figure qui se dresse, bras ouverts, dans un cercle achevé.
     Le mois où l'on cesse d'être celui qui essaie. */
  apotheose: (p) => (
    <Frame {...p}>
      <circle {...P} cx="24" cy="24" r="18" opacity=".45" />
      <circle {...P} cx="24" cy="14" r="4" />
      <path {...P} d="M24 18v14M24 32l-6 8M24 32l6 8" />
      <path {...P} d="M12 20c5 4 8 5 12 5s7-1 12-5" />
    </Frame>
  ),

  /* L'Empyrée — le ciel de feu, tout en haut. Trois arcs concentriques et un
     point : il n'y a rien au-dessus, et le dessin s'arrête donc net. */
  empyree: (p) => (
    <Frame {...p}>
      <path {...P} d="M8 34a16 16 0 0 1 32 0" />
      <path {...P} d="M14 34a10 10 0 0 1 20 0" opacity=".8" />
      <path {...P} d="M19 34a5 5 0 0 1 10 0" opacity=".6" />
      <circle {...P} cx="24" cy="10" r="2.5" />
      <path {...P} d="M6 42h36" opacity=".5" />
    </Frame>
  ),

  /* La Chute — la figure qui tombe, et la ligne d'où elle est partie. Elle a
     déjà eu lieu : la ligne est en haut, hors d'atteinte. */
  chute: (p) => (
    <Frame {...p}>
      <path {...P} d="M8 10h32" opacity=".6" />
      <circle {...P} cx="24" cy="22" r="4" />
      <path {...P} d="M24 26v8M24 30l-7 5M24 30l7 5M24 34l-3 8M24 34l3 8" />
      <path {...P} d="M14 14l4 5M34 14l-4 5" opacity=".45" />
    </Frame>
  ),

  /* Le Styx — le fleuve et la barque. On ne le traverse pas deux fois : une
     seule rame, et une seule rive dessinée. */
  styx: (p) => (
    <Frame {...p}>
      <path {...P} d="M6 34c6-4 12-4 18 0s12 4 18 0" />
      <path {...P} d="M6 40c6-4 12-4 18 0s12 4 18 0" opacity=".55" />
      <path {...P} d="M14 28h20l-4 6H18l-4-6Z" />
      <path {...P} d="M30 28 34 12" />
      <path {...P} d="M32 12h5" opacity=".7" />
    </Frame>
  ),

  /* Cendres — ce qui reste, et ce qui retombe. Un monticule et trois flocons
     en suspension : ça fertilise ou ça stérilise, et ça se décide maintenant. */
  cendres: (p) => (
    <Frame {...p}>
      <path {...P} d="M8 40c4-10 10-14 16-14s12 4 16 14Z" />
      <path {...P} d="M16 18a3 3 0 1 1 0-.1M27 12a2.5 2.5 0 1 1 0-.1M34 22a2 2 0 1 1 0-.1" opacity=".7" />
      <path {...P} d="M24 26c-2-4-1-7 2-9-1 4 1 6 2 9" opacity=".5" />
    </Frame>
  ),

  /* Phénix — les ailes ouvertes au-dessus du bûcher. Il ne revient pas malgré
     le feu : il revient par lui, et les flammes sont donc dessous, pas autour. */
  phenix: (p) => (
    <Frame {...p}>
      <path {...P} d="M24 10c-2 4-2 7 0 10 2-3 2-6 0-10Z" />
      <path {...P} d="M23 22c-5-6-11-9-17-9 4 5 5 10 3 15 6 1 11-1 14-6Z" />
      <path {...P} d="M25 22c5-6 11-9 17-9-4 5-5 10-3 15-6 1-11-1-14-6Z" />
      <path {...P} d="M24 24c2 5 3 8 3 11a3 3 0 0 1-6 0c0-3 1-6 3-11Z" />
      <path {...P} d="M14 42h20" opacity=".55" />
    </Frame>
  ),

  /* Hellfest — trident de flammes */
  hellfest: (p) => (
    <Frame {...p}>
      <path {...P} d="M24 6c3 6-1 8 0 12 2-2 3-5 3-8 4 4 6 9 6 14a9 9 0 0 1-18 0c0-5 3-10 9-18Z" />
      <path {...P} d="M24 26c1.5 2 2.5 3.5 2.5 5.5A2.5 2.5 0 0 1 24 34a2.5 2.5 0 0 1-2.5-2.5c0-2 1-3.5 2.5-5.5Z" />
      <path {...P} d="M10 40h28M14 44h20" opacity=".55" />
    </Frame>
  ),

  /* Heaven's Paradise — halo et ailes */
  heavens_paradise: (p) => (
    <Frame {...p}>
      <ellipse {...P} cx="24" cy="13" rx="9" ry="3.5" />
      <path {...P} d="M23 22c-4-4-9-6-15-6 3 5 3 10 0 15 6 0 11-2 15-6Z" />
      <path {...P} d="M25 22c4-4 9-6 15-6-3 5-3 10 0 15-6 0-11-2-15-6Z" />
      <path {...P} d="M24 20v18" opacity=".6" />
    </Frame>
  ),

  /* Ragnarök — marteau et runes */
  ragnarok: (p) => (
    <Frame {...p}>
      <path {...P} d="M12 12h24v10a4 4 0 0 1-4 4H16a4 4 0 0 1-4-4V12Z" />
      <path {...P} d="M24 26v16M19 42h10" />
      <path {...P} d="M17 16v6M24 15v8M31 16v6" opacity=".55" />
    </Frame>
  ),

  /* Purgatoire — balance suspendue */
  purgatoire: (p) => (
    <Frame {...p}>
      <path {...P} d="M24 8v32M12 14h24M18 42h12" />
      <path {...P} d="M12 14 7 26a5 5 0 0 0 10 0L12 14Z" />
      <path {...P} d="M36 14l-5 12a5 5 0 0 0 10 0l-5-12Z" />
    </Frame>
  ),

  /* Faille S — rift qui s'ouvre */
  faille_s: (p) => (
    <Frame {...p}>
      <path {...P} d="M24 4 34 24 24 44 14 24 24 4Z" />
      <path {...P} d="M24 12 29 24l-5 12-5-12 5-12Z" opacity=".7" />
      <path {...P} d="M6 24h6M36 24h6" opacity=".5" />
    </Frame>
  ),

  /* Solstice Noir — éclipse */
  solstice_noir: (p) => (
    <Frame {...p}>
      <circle {...P} cx="24" cy="24" r="11" />
      <path {...P} d="M24 13a11 11 0 0 0 0 22 8 8 0 0 1 0-22Z" opacity=".8" />
      <path {...P} d="M24 4v5M24 39v5M4 24h5M39 24h5M10 10l3.5 3.5M34.5 34.5 38 38M38 10l-3.5 3.5M13.5 34.5 10 38" opacity=".6" />
    </Frame>
  ),

  /* L'Éveil — un œil qui s'ouvre dans un cercle brisé.
     La première saison de la voie haute, et celle de l'essai : ce qui dormait
     se lève. Le cercle est ouvert en haut à dessein — rien n'est refermé. */
  eveil: (p) => (
    <Frame {...p}>
      <path {...P} d="M34 10a17 17 0 1 1-20 0" />
      <path {...P} d="M8 24c5-6 11-9 16-9s11 3 16 9c-5 6-11 9-16 9s-11-3-16-9Z" />
      <circle {...P} cx="24" cy="24" r="4" />
      <path {...P} d="M24 4v6" opacity=".55" />
    </Frame>
  ),

  /* Dernier Rempart — tour crénelée */
  dernier_rempart: (p) => (
    <Frame {...p}>
      <path {...P} d="M12 18h24v24H12V18Z" />
      <path {...P} d="M12 18V10h4v4h4v-4h8v4h4v-4h4v8" />
      <path {...P} d="M21 42V30h6v12" />
      <path {...P} d="M18 24h4M26 24h4" opacity=".6" />
    </Frame>
  ),

  /* Aube Rouge — soleil levant */
  aube_rouge: (p) => (
    <Frame {...p}>
      <path {...P} d="M8 34h32" />
      <path {...P} d="M13 34a11 11 0 0 1 22 0" />
      <path {...P} d="M24 8v8M10 16l4 5M38 16l-4 5M4 27h5M39 27h5" opacity=".65" />
      <path {...P} d="M14 40h20" opacity=".45" />
    </Frame>
  ),

  /* Nadir — descente abyssale */
  nadir: (p) => (
    <Frame {...p}>
      <circle {...P} cx="24" cy="24" r="16" opacity=".5" />
      <path {...P} d="M24 10v22M17 25l7 8 7-8" />
      <path {...P} d="M14 38h20" opacity=".6" />
    </Frame>
  ),

  /* Inferno — magma */
  inferno: (p) => (
    <Frame {...p}>
      <path {...P} d="M24 5 41 40H7L24 5Z" />
      <path {...P} d="M24 20l7 14H17l7-14Z" opacity=".75" />
      <path {...P} d="M12 44h24" opacity=".5" />
    </Frame>
  ),

  /* Vigie — œil de garde */
  vigie: (p) => (
    <Frame {...p}>
      <path {...P} d="M4 24s7-11 20-11 20 11 20 11-7 11-20 11S4 24 4 24Z" />
      <circle {...P} cx="24" cy="24" r="5.5" />
      <path {...P} d="M24 6v4M24 38v4" opacity=".55" />
    </Frame>
  ),

  /* ---- Second réservoir (J6) --------------------------------------------
   *
   * Douze dessins de plus, parce que douze identités de plus. Le repli existe
   * et fonctionne, mais une saison qui s'ouvre sur le glyphe générique n'a plus
   * d'identité du tout — et le §12.2 fait de l'emblème la moitié de ce qui
   * distingue une saison de la précédente.
   */

  /* Obsidienne — éclat de verre volcanique */
  obsidienne: (p) => (
    <Frame {...p}>
      <path {...P} d="M24 4 38 20 30 44 16 40 10 18 24 4Z" />
      <path {...P} d="M24 4 22 26l8 18M10 18l12 8 16-6" opacity=".55" />
    </Frame>
  ),

  /* Acier froid — lame trempée */
  acier_froid: (p) => (
    <Frame {...p}>
      <path {...P} d="M24 4 30 14v18l-6 6-6-6V14L24 4Z" />
      <path {...P} d="M14 38h20M24 38v6" />
      <path {...P} d="M24 10v22" opacity=".5" />
    </Frame>
  ),

  /* Méridien — globe et ligne */
  meridien: (p) => (
    <Frame {...p}>
      <circle {...P} cx="24" cy="24" r="17" />
      <path {...P} d="M24 7c6 5 6 29 0 34-6-5-6-29 0-34Z" />
      <path {...P} d="M7 24h34" opacity=".55" />
    </Frame>
  ),

  /* Sanctuaire — arche */
  sanctuaire: (p) => (
    <Frame {...p}>
      <path {...P} d="M12 42V22a12 12 0 0 1 24 0v20" />
      <path {...P} d="M18 42V24a6 6 0 0 1 12 0v18" opacity=".6" />
      <path {...P} d="M8 42h32" />
    </Frame>
  ),

  /* Orbite basse — satellite */
  orbite_basse: (p) => (
    <Frame {...p}>
      <circle {...P} cx="24" cy="26" r="9" />
      <ellipse {...P} cx="24" cy="26" rx="20" ry="8" transform="rotate(-24 24 26)" opacity=".6" />
      <circle {...P} cx="38" cy="14" r="2.5" />
    </Frame>
  ),

  /* Tonnerre — éclair encadré */
  tonnerre: (p) => (
    <Frame {...p}>
      <path {...P} d="M26 6 14 26h8l-4 16 16-22h-9l5-14Z" />
      <path {...P} d="M8 12c-3 4-3 20 0 24M40 12c3 4 3 20 0 24" opacity=".5" />
    </Frame>
  ),

  /* Veine mère — filon */
  veine_mere: (p) => (
    <Frame {...p}>
      <path {...P} d="M8 40 20 8l8 14 6-6 6 24" />
      <path {...P} d="M6 44h36" />
      <path {...P} d="M20 22l6 8" opacity=".55" />
    </Frame>
  ),

  /* Quartier nord — immeubles */
  quartier_nord: (p) => (
    <Frame {...p}>
      <path {...P} d="M8 42V18h10v24M22 42V10h10v32M36 42V24h6v18" />
      <path {...P} d="M11 24h4M25 18h4M25 28h4" opacity=".55" />
    </Frame>
  ),

  /* Cendre haute — braise sous la cendre */
  cendre_haute: (p) => (
    <Frame {...p}>
      <path {...P} d="M24 8c4 8-2 10 0 16 3-2 4-6 4-9 5 6 6 11 6 15a10 10 0 0 1-20 0c0-6 4-13 10-22Z" />
      <path {...P} d="M10 42h28" opacity=".55" />
    </Frame>
  ),

  /* Prisme — décomposition */
  prisme: (p) => (
    <Frame {...p}>
      <path {...P} d="M24 8 40 38H8L24 8Z" />
      <path {...P} d="M4 26h12M32 22l12-6M32 26h12M32 30l12 6" opacity=".6" />
    </Frame>
  ),

  /* Dernière forge — enclume */
  derniere_forge: (p) => (
    <Frame {...p}>
      <path {...P} d="M8 18h20l8 6h6l-6 8H16l-8-8v-6Z" />
      <path {...P} d="M20 32v6h-6v4h20v-4h-6v-6" />
    </Frame>
  ),

  /* Marche haute — sommet */
  marche_haute: (p) => (
    <Frame {...p}>
      <path {...P} d="M4 40h10V28h10V16h10V6h10" />
      <path {...P} d="M4 44h40" opacity=".55" />
    </Frame>
  ),
}

const FALLBACK = (p: SigilProps) => (
  <Frame {...p}>
    <path {...P} d="M24 5 41 15v18L24 43 7 33V15L24 5Z" />
    <path {...P} d="M24 16v16M17 24h14" opacity=".7" />
  </Frame>
)

export function SeasonSigil({ seasonKey, size = 44, className }: { seasonKey?: string } & SigilProps) {
  const Sigil = (seasonKey && SIGILS[seasonKey]) || FALLBACK
  return <Sigil size={size} className={className} />
}

/** Les frises, indexées par clé de saison.
 *
 * Hissée hors du composant pour qu'un test puisse vérifier qu'aucune saison
 * de la trame n'en manque : sans frise, le bandeau tombe sur un trait droit —
 * rien ne casse, la saison est juste plus pauvre que les autres, et on ne le
 * découvre qu’en la vivant.
 *
 * Les clés retirées de la trame restent : l'historique en contient encore.
 */
export const MOTIFS: Record<string, string> = {
  porte_ivoire: 'M0 12V7a4 4 0 0 1 8 0v5M12 12V7a4 4 0 0 1 8 0v5',
  elysion: 'M0 12h20M4 12V7M10 12V5M16 12V8',
  ascension: 'M0 12h4V9h4V6h4V3h8',
  valhalla: 'M0 12 5 6l5 6 5-6 5 6',
  couronne_solaire: 'M0 8h3M6 8h3M12 8h3M18 8h2M10 2v3M10 11v3',
  apotheose: 'M0 12a10 8 0 0 1 20 0M10 4v8',
  empyree: 'M0 12a10 7 0 0 1 20 0M4 12a6 4 0 0 1 12 0',
  chute: 'M0 2h20M4 6v6M10 5v7M16 7v5',
  styx: 'M0 8c4-3 8-3 12 0s6 3 8 0',
  cendres: 'M0 12c4-6 8-6 12 0s6 3 8 0',
  phenix: 'M0 10c4-5 8-6 10-2 2-4 6-3 10 2',
  hellfest: 'M0 8 Q5 0 10 8 T20 8',
  heavens_paradise: 'M0 8 Q5 2 10 8 Q15 14 20 8',
  ragnarok: 'M0 4h6l2 8 2-8h6l2 8 2-8',
  purgatoire: 'M0 8h4l3-5 3 10 3-10 3 5h4',
  faille_s: 'M0 8 5 2 10 8 15 14 20 8',
  solstice_noir: 'M0 8a4 4 0 0 1 8 0 4 4 0 0 0 8 0 4 4 0 0 1 4 0',
  eveil: 'M0 8a6 4 0 0 1 12 0a6 4 0 0 1-12 0M14 8h6',
  dernier_rempart: 'M0 12V6h4v6h4V6h4v6h4V6h4v6',
  aube_rouge: 'M0 12a10 10 0 0 1 20 0',
  nadir: 'M0 4l5 8 5-8 5 8 5-8',
  inferno: 'M0 12 5 2l5 10 5-10 5 10',
  vigie: 'M0 8h6a4 4 0 0 1 8 0h6',
  obsidienne: 'M0 12 5 4l5 8 5-8 5 8',
  acier_froid: 'M0 8h5l3-4 3 8 3-4h6',
  meridien: 'M0 8a10 5 0 0 0 20 0M10 3v10',
  sanctuaire: 'M0 12V9a5 5 0 0 1 10 0v3M10 12V9a5 5 0 0 1 10 0v3',
  orbite_basse: 'M0 8a10 4 0 0 0 20 0',
  tonnerre: 'M0 12 8 2l-2 6h6l-6 4',
  veine_mere: 'M0 12 6 4l4 6 4-8 6 10',
  quartier_nord: 'M0 12V7h4v5h4V4h4v8h4V8h4v4',
  cendre_haute: 'M0 10c4 0 4-6 8-6s4 6 8 6 4-4 4-4',
  prisme: 'M0 12 6 3l6 9M12 8h8',
  derniere_forge: 'M0 10h8l3 3h9M4 13h6',
  marche_haute: 'M0 12h5V9h5V6h5V3h5',
}

/** Les atmosphères que `SeasonAtmosphere` sait dessiner. Le serveur en nomme
 *  une par saison ; celle qu'il nommerait sans qu'elle existe ici rendrait un
 *  bandeau nu. */
export const AMBIANCES = [
  'lave',
  'forge',
  'ailes',
  'or',
  'aurore',
  'vitrail',
  'orage',
  'abysse',
  'cendre',
] as const

/** Frise d'ornement du bandeau, différente par saison — elle donne sa texture
 *  au haut de l'écran sans jamais gêner la lecture du texte. */
export function SeasonOrnament({ seasonKey }: { seasonKey?: string }) {
  const d = MOTIFS[seasonKey ?? ''] ?? 'M0 8h20'

  return (
    <svg className="ornament" height="14" width="100%" aria-hidden preserveAspectRatio="none">
      <defs>
        <pattern id={`orn-${seasonKey}`} width="20" height="14" patternUnits="userSpaceOnUse">
          <path d={d} fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
        </pattern>
      </defs>
      <rect width="100%" height="14" fill={`url(#orn-${seasonKey})`} />
    </svg>
  )
}
