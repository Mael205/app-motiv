/** Applique le blocage sur la page (SPEC §8.5, §9.1).
 *
 * Ce script ne décide rien, et n'a même pas les règles : il envoie l'adresse
 * courante au script de fond et exécute la réponse. Deux raisons, une de forme
 * et une de fond.
 *
 * De forme : un script de contenu n'est pas un module ES — ni Chrome ni Firefox
 * n'y acceptent `import`. Laisser les règles dans le script de fond évite le
 * détour par une ressource accessible au web, et donc d'exposer la mécanique du
 * blocage à n'importe quelle page.
 *
 * De fond : l'état armé vient du serveur, la décision reste donc du même côté
 * que lui. La page, elle, ne sait rien qu'elle pourrait contredire.
 *
 * YouTube est une application à page unique : passer de l'accueil à une vidéo
 * ne recharge rien, et un script qui ne s'exécuterait qu'au chargement serait
 * inactif dix minutes plus tard. D'où l'écoute de `yt-navigate-finish`, et le
 * filet qui compare l'adresse toutes les secondes — l'événement est privé à
 * YouTube et peut disparaître, la comparaison d'adresse ne peut pas.
 */

const api = globalThis.browser ?? globalThis.chrome

async function appliquer() {
  const racine = document.documentElement

  let ordre
  try {
    ordre = await api.runtime.sendMessage({ type: 'coach-page', url: location.href })
  } catch {
    // Extension rechargée ou script de fond endormi : on ne bloque pas. Un
    // blocage qui se déclenche sur une erreur interne est un blocage qu'on
    // désinstalle.
    racine.removeAttribute('data-coach-block')
    return
  }

  if (!ordre || !ordre.arme) {
    racine.removeAttribute('data-coach-block')
    return
  }

  if (ordre.redirection) {
    // `replace` et non `assign` : le Short ne doit pas rester dans
    // l'historique, sinon le bouton « précédent » le rouvre.
    location.replace(ordre.redirection)
    return
  }

  if (ordre.surface) racine.setAttribute('data-coach-block', ordre.surface)
  else racine.removeAttribute('data-coach-block')
}

let derniere = location.href

document.addEventListener('yt-navigate-finish', () => {
  derniere = location.href
  appliquer()
})

setInterval(() => {
  if (location.href === derniere) return
  derniere = location.href
  appliquer()
}, 1000)

appliquer()
