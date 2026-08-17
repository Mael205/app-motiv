/** Ce qui est bloqué, et ce qui ne l'est jamais (SPEC §8.5, §9.1).
 *
 * Deux règles seulement, et elles tiennent dans une phrase du §9.1 : rediriger
 * `/shorts`, masquer le feed d'accueil, **laisser passer la recherche, les
 * vidéos longues et la documentation**. Ce qui est bloqué ici est la surface de
 * défilement infini, pas YouTube.
 *
 * Cette distinction est tout le produit. Le §17 interdit de bloquer les jeux
 * parce qu'un blocage vécu comme injuste fait désinstaller l'ensemble ; un
 * blocage qui empêcherait de chercher une réponse technique à 21h aurait
 * exactement le même effet, en pire — il punirait le travail.
 *
 * Les domaines pleins (TikTok, X, Instagram, Reddit) ne passent pas par ici :
 * le §8.5 les confie au fichier hosts, donc à l'agent. Une extension qui
 * essaierait de les couvrir ne tiendrait que dans le navigateur où elle est
 * installée.
 *
 * Module sans API navigateur : tout y est testable à la main dans une console.
 */

const SHORTS = /^\/shorts\/([A-Za-z0-9_-]{5,})/

/** Les hôtes YouTube, mobile et sans www compris. */
export function estYoutube(hote) {
  return /(^|\.)youtube\.com$/.test(hote) || hote === 'youtu.be'
}

/** L'adresse où renvoyer, ou `null` s'il n'y a rien à rediriger.
 *
 * Un Short est **la même vidéo** que sur la page normale : on redirige vers
 * `/watch`, on ne refuse pas. Le contenu reste accessible, la mécanique de
 * défilement disparaît — et c'est elle qui fait les trois heures du §0.5.
 */
export function redirection(adresse) {
  let url
  try {
    url = new URL(adresse)
  } catch {
    return null
  }
  if (!estYoutube(url.hostname)) return null

  const trouve = url.pathname.match(SHORTS)
  if (!trouve) return null

  return `${url.origin}/watch?v=${trouve[1]}`
}

/** La surface à masquer sur la page courante, ou une chaîne vide.
 *
 * Seul l'accueil est concerné. `/results`, `/watch`, `/feed/subscriptions` et
 * tout le reste sont laissés intacts : chercher une vidéo est un geste
 * volontaire, tomber dans le feed n'en est pas un.
 */
export function surfaceMasquee(adresse) {
  let url
  try {
    url = new URL(adresse)
  } catch {
    return ''
  }
  if (!estYoutube(url.hostname)) return ''

  return url.pathname === '/' || url.pathname === '' ? 'accueil' : ''
}
