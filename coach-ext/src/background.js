/** Sonde web du coach, et blocage du défilement (SPEC §9.1, §8.5).
 *
 * Deux rôles qui ne se parlent pas : mesurer, et bloquer. La mesure part vers
 * `/api/signals`, le blocage vient de `/api/agent/state`. C'est le serveur qui
 * décide qu'il est armé — l'extension n'a ni l'heure du gardien, ni l'état du
 * sas, ni les sanctions du §14, et n'en a pas besoin.
 *
 * Elle compte le temps passé par catégorie sur l'onglet **actif d'une fenêtre
 * ayant le focus**, et s'arrête quand la machine est inactive. Un onglet ouvert
 * en arrière-plan pendant six heures ne compte pas : ce serait mesurer des
 * onglets, pas un usage.
 *
 * Ce qui sort d'ici : des couples (catégorie, minutes). Rien d'autre. La table
 * qui relie un domaine à une catégorie reste dans le stockage local.
 */

import { AUTRE, DEFAULT_RULES, categoryOf, toEntries } from './categories.js'
import { redirection, surfaceMasquee } from './blocking.js'

/** Adaptateur Chrome / Firefox.
 *
 * Firefox expose `browser.*` avec des promesses ; Chrome expose `api.*`,
 * qui rend des promesses en MV3. Passer par cette variable évite de dépendre
 * du comportement de `api.*` sous Firefox, qui a changé selon les versions.
 */
const api = globalThis.browser ?? globalThis.chrome

const FLUSH_ALARM = 'coach-flush'
// Une minute, pas cinq. C'est le minimum qu'acceptent les alarmes, et
// l'attente n'achetait rien : le tampon vit maintenant dans le stockage, donc
// rien ne se perd entre deux envois. Cinq minutes rendaient surtout le
// diagnostic impossible — on ne sait pas si ça ne marche pas ou si ça n'a pas
// encore eu lieu.
const FLUSH_MINUTES = 1
const IDLE_SECONDS = 120

/* La mesure vit dans le stockage, pas en mémoire.
 *
 * **Le défaut que ça corrige.** En manifeste V3, le script de fond est une
 * page d'événements : le navigateur la suspend dès qu'elle ne fait rien, et la
 * relance au prochain événement. Toutes les variables de module repartent
 * alors de zéro. Le tampon des minutes se vidait donc régulièrement **avant**
 * l'alarme des cinq minutes, et l'envoi ne partait jamais — sans erreur, sans
 * trace, puisqu'il n'y avait plus rien à envoyer.
 *
 * Les trois valeurs sont donc relues avant chaque usage et réécrites après
 * chaque modification. Le coût est négligeable — quelques écritures par minute
 * — et c'est la seule façon de survivre à une suspension.
 */
const ETAT_MESURE = 'coach-mesure'

let current = { category: AUTRE, since: Date.now() }
let buffer = {}
let bufferSince = Date.now()

async function chargerMesure() {
  const stocke = (await api.storage.local.get(ETAT_MESURE))[ETAT_MESURE]
  if (!stocke) return
  buffer = stocke.buffer || {}
  bufferSince = stocke.bufferSince || Date.now()
  current = stocke.current || { category: AUTRE, since: Date.now() }
}

async function sauverMesure() {
  await api.storage.local.set({ [ETAT_MESURE]: { buffer, bufferSince, current } })
}

async function settings() {
  const stored = await api.storage.local.get(['apiUrl', 'token', 'rules'])
  return {
    apiUrl: stored.apiUrl || 'http://127.0.0.1:8000',
    token: stored.token || '',
    rules: stored.rules || DEFAULT_RULES,
  }
}

/** Ferme la tranche en cours et en ouvre une nouvelle. */
async function accumulate(nextCategory) {
  const now = Date.now()
  const elapsed = now - current.since
  if (elapsed > 0 && current.category !== AUTRE) {
    buffer[current.category] = (buffer[current.category] || 0) + elapsed
  }
  current = { category: nextCategory, since: now }
  await sauverMesure()
}

async function refresh() {
  await chargerMesure()

  const state = await api.idle.queryState(IDLE_SECONDS)
  if (state !== 'active') return accumulate(AUTRE)

  const [tab] = await api.tabs.query({ active: true, lastFocusedWindow: true })
  if (!tab || !tab.url) return accumulate(AUTRE)

  const { rules } = await settings()
  await accumulate(categoryOf(tab.url, rules))

  // Dès qu'une minute pleine existe, elle part. L'attente n'apportait rien —
  // le serveur reçoit de toute façon une fenêtre horaire, pas un instant — et
  // elle coûtait cher : tant qu'aucun envoi n'a eu lieu, il est impossible de
  // distinguer « ça ne marche pas » de « ça n'a pas encore eu lieu ».
  if (toEntries(buffer).length > 0) await flush()
}

async function flush() {
  await chargerMesure()
  await accumulate(current.category)    // ferme la tranche sans changer d'état
  const entries = toEntries(buffer)
  if (entries.length === 0) return

  // La fenêtre du tampon : sans elle, le serveur saurait « 14 minutes dans la
  // journée » sans savoir lesquelles, et ne pourrait rien rattacher à une
  // session (SPEC §6).
  const windowStart = new Date(bufferSince).toISOString()
  const windowEnd = new Date().toISOString()
  const dated = entries.map((entry) => ({ ...entry, started_at: windowStart, ended_at: windowEnd }))

  const { apiUrl, token } = await settings()
  if (!token) return                     // pas configurée : on garde le tampon

  try {
    const response = await fetch(`${apiUrl.replace(/\/$/, '')}/api/signals`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Probe-Token': token },
      body: JSON.stringify({ source: 'ext', entries: dated }),
    })
    if (response.status === 401) {
      // Jeton mort : inutile de réessayer en boucle avec un secret périmé.
      await api.storage.local.set({ lastError: 'Jeton refusé. Réémets-en un.' })
      return
    }
    if (!response.ok) return             // on garde le tampon pour le prochain envoi
    buffer = {}
    bufferSince = Date.now()
    await sauverMesure()
    await api.storage.local.set({ lastFlush: new Date().toISOString(), lastError: '' })
  } catch {
    // Serveur éteint : le tampon reste, rien n'est perdu.
  }
}

/* ------------------------------------------------------------------------
 * Le blocage (SPEC §8.5, §9.1)
 * ---------------------------------------------------------------------- */

/** Durée de validité de l'état armé.
 *
 * L'heure d'armement ne bouge pas d'une minute à l'autre, mais le
 * **désarmement** doit être rapide : quelqu'un qui vient de faire ses 25
 * minutes et retourne sur YouTube ne doit pas retomber sur un feed masqué. Une
 * demi-minute est le compromis — assez court pour que ça ne se remarque pas,
 * assez long pour ne pas interroger le serveur à chaque clic dans une page.
 */
const ETAT_TTL_MS = 30_000

let etat = { arme: false, vu: 0 }

async function etatDuServeur() {
  if (Date.now() - etat.vu < ETAT_TTL_MS) return etat.arme

  const { apiUrl, token } = await settings()
  if (!token) return false

  try {
    const response = await fetch(`${apiUrl.replace(/\/$/, '')}/api/agent/state`, {
      headers: { 'X-Probe-Token': token },
    })
    if (!response.ok) return etat.arme      // on garde le dernier état connu
    const data = await response.json()
    etat = { arme: Boolean(data.block_scroll && data.block_scroll.armed), vu: Date.now() }
    await api.storage.local.set({ armed: etat.arme })
  } catch {
    // Serveur éteint : on ne bloque pas plus fort parce qu'on ne sait plus. Un
    // blocage qui survit à la panne du système qui l'a décidé est un blocage
    // que plus personne ne peut lever.
    etat = { arme: false, vu: Date.now() }
    await api.storage.local.set({ armed: false })
  }
  return etat.arme
}

/** L'état effectif, pause locale comprise.
 *
 * La pause est **locale au navigateur** : le serveur reste armé, et c'est
 * voulu. Lever le blocage n'est pas déclarer la soirée finie — le gardien, la
 * jauge et les sanctions du §14 ne changent pas d'avis parce qu'on a fermé un
 * masque de feed.
 */
async function bloqueMaintenant() {
  const { pauseUntil } = await api.storage.local.get('pauseUntil')
  if (pauseUntil && Date.now() < pauseUntil) return false
  return etatDuServeur()
}

api.runtime.onMessage.addListener((message, _sender, repondre) => {
  if (!message) return false

  if (message.type === 'coach-envoyer') {
    // Le bouton du panneau. Il ne sert pas qu'au confort : sans lui, vérifier
    // qu'une sonde fonctionne demande d'attendre sans savoir combien de temps,
    // ce qui est la pire façon de diagnostiquer quoi que ce soit.
    refresh()
      .then(() => flush())
      .then(async () => {
        const { lastFlush, lastError } = await api.storage.local.get(['lastFlush', 'lastError'])
        repondre({ lastFlush: lastFlush || '', lastError: lastError || '' })
      })
    return true
  }

  if (message.type === 'coach-etat') {
    // Le panneau demande l'état pour l'afficher : il ne parle d'aucune page.
    bloqueMaintenant().then((arme) => repondre({ arme }))
    return true
  }

  if (message.type !== 'coach-page') return false

  bloqueMaintenant().then((arme) =>
    repondre({
      arme,
      redirection: arme ? redirection(message.url) : null,
      surface: arme ? surfaceMasquee(message.url) : '',
    }),
  )
  return true                              // réponse asynchrone
})

api.tabs.onActivated.addListener(refresh)
api.tabs.onUpdated.addListener((_id, change) => change.url && refresh())
api.windows.onFocusChanged.addListener(refresh)
api.idle.onStateChanged.addListener(refresh)

api.runtime.onInstalled.addListener(() => {
  api.alarms.create(FLUSH_ALARM, { periodInMinutes: FLUSH_MINUTES })
})
api.runtime.onStartup.addListener(() => {
  api.alarms.create(FLUSH_ALARM, { periodInMinutes: FLUSH_MINUTES })
})
api.alarms.onAlarm.addListener((alarm) => alarm.name === FLUSH_ALARM && flush())

/** Pose l'alarme **seulement si elle n'existe pas déjà.**
 *
 * Le test d'existence n'est pas une précaution, c'est la correction d'un défaut
 * qui empêchait tout envoi. `alarms.create` **remplace** l'alarme du même nom
 * et remet son minuteur à zéro. Or la page d'événements se réveille à chaque
 * message du panneau ou d'un onglet, soit toutes les une ou deux minutes : une
 * alarme recréée à chaque réveil n'atteignait jamais son échéance, et ne
 * sonnait donc jamais.
 *
 * Poser l'alarme au chargement reste nécessaire — `onInstalled` et `onStartup`
 * ne repassent jamais après une suspension. Il fallait les deux : la poser, et
 * ne pas la reposer.
 */
async function assurerLAlarme() {
  const existante = await api.alarms.get(FLUSH_ALARM)
  if (!existante) api.alarms.create(FLUSH_ALARM, { periodInMinutes: FLUSH_MINUTES })
}

assurerLAlarme()

/* `refresh()` au chargement. Sans lui, la catégorie courante reste « autre »
 * jusqu'au premier changement d'onglet : rester une heure sur la même page de
 * documentation ne comptait rien du tout. C'est le cas le plus fréquent quand
 * on travaille, et celui qu'on ne remarque jamais — il ne produit pas une
 * mesure fausse mais une absence de mesure.
 */
refresh()
