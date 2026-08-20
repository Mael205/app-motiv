import { DEFAULT_RULES } from './categories.js'

/** Adaptateur Chrome / Firefox.
 *
 * Firefox expose `browser.*` avec des promesses ; Chrome expose `api.*`,
 * qui rend des promesses en MV3. Passer par cette variable évite de dépendre
 * du comportement de `api.*` sous Firefox, qui a changé selon les versions.
 */
const api = globalThis.browser ?? globalThis.chrome

const $ = (id) => document.getElementById(id)

const stored = await api.storage.local.get(['apiUrl', 'token', 'rules', 'lastFlush', 'lastError'])
$('apiUrl').value = stored.apiUrl || 'http://127.0.0.1:8000'
$('token').value = stored.token || ''
$('rules').value = JSON.stringify(stored.rules || DEFAULT_RULES, null, 2)

const state = $('state')
if (stored.lastError) {
  state.textContent = stored.lastError
  state.className = 'state err'
} else if (stored.lastFlush) {
  state.textContent = `Dernier envoi : ${new Date(stored.lastFlush).toLocaleString('fr-FR')}`
}

/* ------------------------------------------------------------------------
 * Le blocage, et sa porte de sortie (SPEC §8.5)
 * ---------------------------------------------------------------------- */

/** Ce que coûte la levée : deux clics et soixante secondes.
 *
 * Le §8.5 fixe les deux, et donne la raison de ne pas faire plus : « la
 * friction suffit, l'emprisonnement non ». Un blocage impossible à lever
 * finit contourné par le navigateur d'à côté, et l'extension désinstallée le
 * jour où elle gêne pour de bon. Une minute d'attente suffit à ce que
 * l'impulsion passe, et c'est tout ce qu'on lui demande.
 */
const ATTENTE_SECONDES = 60
const PAUSE_MS = 2 * 60 * 60 * 1000

const bloc = $('bloc')
const blocEtat = $('blocEtat')
const lever = $('lever')

async function peindreBlocage() {
  const { pauseUntil } = await api.storage.local.get('pauseUntil')
  const enPause = pauseUntil && Date.now() < pauseUntil

  // On demande au script de fond plutôt qu'au stockage : sans ça, le panneau
  // afficherait l'état du dernier passage sur YouTube, qui peut dater d'hier.
  let armed = false
  try {
    const reponse = await api.runtime.sendMessage({ type: 'coach-etat' })
    armed = Boolean(reponse && reponse.arme)
  } catch {
    const cache = await api.storage.local.get('armed')
    armed = Boolean(cache.armed)
  }

  bloc.classList.toggle('arme', armed && !enPause)
  lever.hidden = !armed || enPause

  if (enPause) {
    const fin = new Date(pauseUntil).toLocaleTimeString('fr-FR', {
      hour: '2-digit',
      minute: '2-digit',
    })
    blocEtat.textContent = `Levé jusqu'à ${fin}.`
    return
  }
  blocEtat.textContent = armed
    ? 'Armé. Le feed d’accueil est masqué, les Shorts renvoient vers la vidéo. La recherche reste ouverte.'
    : 'Au repos. Rien n’est masqué.'
}

// `null` tant que rien n'est demandé, puis le nombre de secondes restantes.
// Zéro veut dire « l'attente est purgée, un clic lève ».
let restant = null

lever.addEventListener('click', async () => {
  if (restant === null) {
    restant = ATTENTE_SECONDES
    lever.textContent = `Confirmer dans ${restant} s`
    const compte = setInterval(() => {
      restant -= 1
      lever.textContent = restant > 0 ? `Confirmer dans ${restant} s` : 'Confirmer la levée'
      if (restant <= 0) clearInterval(compte)
    }, 1000)
    return
  }

  if (restant > 0) return                  // le second clic ne raccourcit rien

  await api.storage.local.set({ pauseUntil: Date.now() + PAUSE_MS })
  restant = null
  lever.textContent = 'Lever le blocage'
  await peindreBlocage()
})

await peindreBlocage()

$('save').addEventListener('click', async () => {
  let rules
  try {
    rules = JSON.parse($('rules').value)
  } catch {
    state.textContent = 'Le JSON des catégories est invalide — rien n’a été enregistré.'
    state.className = 'state err'
    return
  }
  await api.storage.local.set({
    apiUrl: $('apiUrl').value.trim(),
    token: $('token').value.trim(),
    rules,
    lastError: '',
  })
  state.textContent = 'Enregistré.'
  state.className = 'state'
})


/** Le bouton « Envoyer maintenant ».
 *
 * Il existe pour une raison de diagnostic, pas de confort. Tant qu'aucun envoi
 * n'a eu lieu, l'état affiché est vide — et un état vide veut dire deux choses
 * indiscernables : « rien à envoyer », qui est le cas normal et fréquent
 * puisque tout ce qui tombe dans « autre » n'est jamais transmis, et « ça ne
 * marche pas ». Ce bouton sépare les deux en une seconde.
 */
document.getElementById('envoyer').addEventListener('click', async () => {
  const etat = document.getElementById('state')
  etat.textContent = 'Envoi…'
  try {
    const reponse = await api.runtime.sendMessage({ type: 'coach-envoyer' })
    if (reponse && reponse.lastError) {
      etat.textContent = reponse.lastError
    } else if (reponse && reponse.lastFlush) {
      etat.textContent = `Dernier envoi : ${new Date(reponse.lastFlush).toLocaleString('fr-FR')}`
    } else {
      // Le cas honnête : il n'y avait rien à envoyer. Le dire évite de chercher
      // une panne là où il n'y en a pas.
      etat.textContent = "Rien à envoyer : aucune minute pleine sur un site catégorisé."
    }
  } catch (erreur) {
    etat.textContent = `Échec : ${erreur.message}`
  }
})
