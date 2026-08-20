import type { HomeState } from './types'

/** Ce qui peint l'interface : deux accents, le cadre d'avatar, le mode terne.
 *
 * La fonction vit dans son propre module et non dans `App.tsx` pour pouvoir se
 * tester : `App.tsx` importe tout l'arbre de l'application — écrans, API,
 * animations —, et un test qui doit monter tout ça pour vérifier deux variables
 * CSS ne s'écrit jamais. Ici il n'y a que le DOM, donc jsdom suffit.
 *
 * Elle est appelée à chaque lecture de l'accueil, toutes les dix secondes. Elle
 * doit donc être **idempotente et complète** : chaque appel repose l'état
 * entier, y compris en retirant ce qui n'a plus lieu d'être. Une propriété
 * inline posée sur le <body> ne disparaît pas toute seule, et un état qui ne
 * sait que s'ajouter finit par afficher la couleur d'une carte déséquipée
 * jusqu'au prochain rechargement.
 */
export function applySeasonTheme(home: HomeState) {
  const root = document.body

  // --accent appartient à la saison, et rien ne le lui prend : c'est ce qui
  // porte son identité sur le HUD, les onglets, les jauges et le boss.
  const saison = home.season?.accent ?? ''
  if (saison) root.style.setProperty('--accent', saison)
  else root.style.removeProperty('--accent')

  // --perso appartient au joueur. Le thème équipé ne **remplace** plus l'accent
  // de saison, il peint les surfaces qui sont les siennes — fiche de
  // personnage, collection, révélation de carte. Les deux restent visibles en
  // même temps, là où une variable unique en effaçait forcément un des deux.
  //
  // L'écran de session reste sur --accent : il se teinte déjà à la couleur du
  // projet, et l'effet de fin a son propre emplacement (`finisher`).
  //
  // Le repli se calcule ici et non en CSS. La déclaration `--perso: var(--accent)`
  // de theme.css vit sur :root, alors que l'accent de saison est posé en style
  // inline sur <body> : la substitution s'y ferait contre l'or par défaut de
  // :root et non contre la saison, et les surfaces personnelles resteraient
  // dorées sur une saison verte.
  const theme = home.cosmetics?.theme?.value
  const perso = theme || saison
  if (perso) root.style.setProperty('--perso', perso)
  else root.style.removeProperty('--perso')

  // Le cadre d'avatar est une classe sur le document : la fiche de personnage
  // et le bandeau le lisent tous les deux, et une variable CSS ne saurait pas
  // porter une texture.
  root.dataset.frame = home.cosmetics?.frame?.value ?? ''
  root.dataset.finisher = home.cosmetics?.finisher?.value ?? ''

  // Le mode terne est la sanction de palier 1 : l'interface s'éteint jusqu'à la
  // prochaine session.
  root.classList.toggle('terne', home.streak.sanction_level >= 1 && !home.validated_today)
}
