/** Jeu d'icônes de l'interface.
 *
 * Trait unique, 1.6 d'épaisseur, hérité de `currentColor` : elles se posent
 * partout sans jamais jurer avec l'accent de la saison en cours.
 */

type IconProps = { size?: number; className?: string }

const S = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const

function Svg({ size = 18, className, children }: IconProps & { children: React.ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} className={className} aria-hidden>
      {children}
    </svg>
  )
}

export const Icon = {
  shield: (p: IconProps) => (
    <Svg {...p}>
      <path {...S} d="M12 2.5 20 6v6.5c0 5-3.4 8-8 9.5-4.6-1.5-8-4.5-8-9.5V6l8-3.5Z" />
    </Svg>
  ),

  flame: (p: IconProps) => (
    <Svg {...p}>
      <path {...S} d="M12 2c2 4-1 5.5 0 8 1.3-1.2 2-3 2-4.5 2.7 2.5 4 5.7 4 9a6 6 0 0 1-12 0c0-3.5 2-6.8 6-12.5Z" />
    </Svg>
  ),

  sword: (p: IconProps) => (
    <Svg {...p}>
      <path {...S} d="M20 3v5l-9 9-2-2 9-9h2ZM7 15l2 2M4.5 18.5 8 22M3 20l3-3" />
    </Svg>
  ),

  clock: (p: IconProps) => (
    <Svg {...p}>
      <circle {...S} cx="12" cy="12" r="9" />
      <path {...S} d="M12 7v5.5l3.5 2" />
    </Svg>
  ),

  target: (p: IconProps) => (
    <Svg {...p}>
      <circle {...S} cx="12" cy="12" r="8.5" />
      <circle {...S} cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="12" r="1.6" fill="currentColor" />
    </Svg>
  ),

  fridge: (p: IconProps) => (
    <Svg {...p}>
      <path {...S} d="M6 3h12v18H6V3ZM6 10h12" />
      <path {...S} d="M9 6.5v1.5M9 13v2.5" />
    </Svg>
  ),

  map: (p: IconProps) => (
    <Svg {...p}>
      <path {...S} d="M9 4 3 6.5v14L9 18l6 2.5 6-2.5v-14L15 6.5 9 4Z" />
      <path {...S} d="M9 4v14M15 6.5v14" />
    </Svg>
  ),

  book: (p: IconProps) => (
    <Svg {...p}>
      <path {...S} d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v17H6.5A2.5 2.5 0 0 0 4 21.5v-17Z" />
      <path {...S} d="M8 7h8M8 11h6" />
    </Svg>
  ),

  bolt: (p: IconProps) => (
    <Svg {...p}>
      <path {...S} d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />
    </Svg>
  ),

  check: (p: IconProps) => (
    <Svg {...p}>
      <path {...S} d="m4 12.5 5 5L20 6.5" />
    </Svg>
  ),
}
