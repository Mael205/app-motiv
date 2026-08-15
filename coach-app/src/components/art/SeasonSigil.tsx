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

const SIGILS: Record<string, (p: SigilProps) => React.ReactElement> = {
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

  /* Wacken — cornes */
  wacken: (p) => (
    <Frame {...p}>
      <path {...P} d="M24 34c-8 0-14-5-14-12 0-4 2-8 4-10 0 5 3 8 10 8s10-3 10-8c2 2 4 6 4 10 0 7-6 12-14 12Z" />
      <path {...P} d="M18 22v4M30 22v4" opacity=".7" />
      <path {...P} d="M14 38h20" opacity=".5" />
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

/** Frise d'ornement du bandeau, différente par saison — elle donne sa texture
 *  au haut de l'écran sans jamais gêner la lecture du texte. */
export function SeasonOrnament({ seasonKey }: { seasonKey?: string }) {
  const motifs: Record<string, string> = {
    hellfest: 'M0 8 Q5 0 10 8 T20 8',
    heavens_paradise: 'M0 8 Q5 2 10 8 Q15 14 20 8',
    ragnarok: 'M0 4h6l2 8 2-8h6l2 8 2-8',
    purgatoire: 'M0 8h4l3-5 3 10 3-10 3 5h4',
    faille_s: 'M0 8 5 2 10 8 15 14 20 8',
    solstice_noir: 'M0 8a4 4 0 0 1 8 0 4 4 0 0 0 8 0 4 4 0 0 1 4 0',
    wacken: 'M0 12c4 0 4-8 8-8s4 8 8 8 4-8 4-8',
    dernier_rempart: 'M0 12V6h4v6h4V6h4v6h4V6h4v6',
    aube_rouge: 'M0 12a10 10 0 0 1 20 0',
    nadir: 'M0 4l5 8 5-8 5 8 5-8',
    inferno: 'M0 12 5 2l5 10 5-10 5 10',
    vigie: 'M0 8h6a4 4 0 0 1 8 0h6',
  }
  const d = motifs[seasonKey ?? ''] ?? 'M0 8h20'

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
