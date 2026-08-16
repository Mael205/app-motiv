/** La boîte à outils de juice (SPEC §7).
 *
 * Le §7 est catégorique sur deux points qui contraignent tout ce dossier :
 *
 * > Juice — fort mais canalisé. **Quatre moments seulement** portent des effets
 * > riches ; partout ailleurs l'interface reste calme.
 *
 * > **Jamais d'animation sur le chemin critique** — le bouton « Démarrer »
 * > répond immédiatement et l'effet se joue par-dessus.
 *
 * Ces primitives sont donc conçues pour être *superposées* à une interface qui
 * a déjà fait son travail. Aucune n'attend, aucune ne bloque un clic, aucune ne
 * retarde une requête. Elles se jouent pendant que le reste avance.
 *
 * `prefers-reduced-motion` est respecté partout, avec une variante non animée
 * pour chacune des quatre séquences — le §7 l'exige nommément, et une séquence
 * qui disparaîtrait au lieu de se simplifier ferait perdre l'information.
 */

export { useTrauma } from './useTrauma'
export { useHitStop } from './useHitStop'
export { useReducedMotion } from './useReducedMotion'
export { CountUp } from './CountUp'
export { Burst } from './Burst'
export { Rays } from './Rays'
export { EASE } from './easing'
