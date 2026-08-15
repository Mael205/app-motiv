/** Sonde web du coach (SPEC §9.1).
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

/** Adaptateur Chrome / Firefox.
 *
 * Firefox expose `browser.*` avec des promesses ; Chrome expose `api.*`,
 * qui rend des promesses en MV3. Passer par cette variable évite de dépendre
 * du comportement de `api.*` sous Firefox, qui a changé selon les versions.
 */
const api = globalThis.browser ?? globalThis.chrome

const FLUSH_ALARM = 'coach-flush'
const FLUSH_MINUTES = 5
const IDLE_SECONDS = 120

let current = { category: AUTRE, since: Date.now() }
let buffer = {}
let bufferSince = Date.now()

async function settings() {
  const stored = await api.storage.local.get(['apiUrl', 'token', 'rules'])
  return {
    apiUrl: stored.apiUrl || 'http://127.0.0.1:8000',
    token: stored.token || '',
    rules: stored.rules || DEFAULT_RULES,
  }
}

/** Ferme la tranche en cours et en ouvre une nouvelle. */
function accumulate(nextCategory) {
  const now = Date.now()
  const elapsed = now - current.since
  if (elapsed > 0 && current.category !== AUTRE) {
    buffer[current.category] = (buffer[current.category] || 0) + elapsed
  }
  current = { category: nextCategory, since: now }
}

async function refresh() {
  const state = await api.idle.queryState(IDLE_SECONDS)
  if (state !== 'active') return accumulate(AUTRE)

  const [tab] = await api.tabs.query({ active: true, lastFocusedWindow: true })
  if (!tab || !tab.url) return accumulate(AUTRE)

  const { rules } = await settings()
  accumulate(categoryOf(tab.url, rules))
}

async function flush() {
  accumulate(current.category)          // ferme la tranche sans changer d'état
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
    await api.storage.local.set({ lastFlush: new Date().toISOString(), lastError: '' })
  } catch {
    // Serveur éteint : le tampon reste, rien n'est perdu.
  }
}

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
