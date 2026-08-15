/** Catégorisation locale — la table ne quitte jamais le navigateur.
 *
 * L'extension envoie « reseaux : 14 minutes ». Elle n'envoie jamais quel
 * domaine, jamais le titre de la page, jamais l'URL (SPEC §11.10). Cette table
 * est modifiable dans les options et vit dans le stockage local.
 */

export const AUTRE = 'autre'

export const DEFAULT_RULES = {
  travail_projet: ['localhost', 'github.com', 'stackoverflow.com', 'developer.mozilla.org', 'docs.djangoproject.com'],
  reseaux: ['instagram.com', 'x.com', 'twitter.com', 'facebook.com', 'linkedin.com', 'snapchat.com'],
  scroll_passif: ['tiktok.com', 'youtube.com/shorts', 'reddit.com', 'twitch.tv', '9gag.com'],
  // Vide par défaut, volontairement : cette liste te regarde (voir README).
  adulte: [],
  jeu: ['dofus.com', 'steampowered.com'],
  sport: ['strava.com'],
}

/** Extrait « host + chemin » sans jamais conserver la requête ni le fragment. */
export function siteOf(url) {
  try {
    const parsed = new URL(url)
    if (!parsed.protocol.startsWith('http')) return ''
    return (parsed.hostname + parsed.pathname).toLowerCase()
  } catch {
    return ''
  }
}

export function categoryOf(url, rules) {
  const site = siteOf(url)
  if (!site) return AUTRE
  for (const [category, fragments] of Object.entries(rules)) {
    if (fragments.some((fragment) => site.includes(fragment.toLowerCase()))) return category
  }
  return AUTRE
}

/** Minutes par catégorie, en jetant tout ce qui est sous la minute. */
export function toEntries(millisByCategory) {
  return Object.entries(millisByCategory)
    .filter(([category]) => category !== AUTRE)
    .map(([category, ms]) => ({ category, minutes: Math.floor(ms / 60000) }))
    .filter((entry) => entry.minutes > 0)
}
