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

const FLUSH_ALARM = 'coach-flush'
const FLUSH_MINUTES = 5
const IDLE_SECONDS = 120

let current = { category: AUTRE, since: Date.now() }
let buffer = {}

async function settings() {
  const stored = await chrome.storage.local.get(['apiUrl', 'token', 'rules'])
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
  const state = await chrome.idle.queryState(IDLE_SECONDS)
  if (state !== 'active') return accumulate(AUTRE)

  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true })
  if (!tab || !tab.url) return accumulate(AUTRE)

  const { rules } = await settings()
  accumulate(categoryOf(tab.url, rules))
}

async function flush() {
  accumulate(current.category)          // ferme la tranche sans changer d'état
  const entries = toEntries(buffer)
  if (entries.length === 0) return

  const { apiUrl, token } = await settings()
  if (!token) return                     // pas configurée : on garde le tampon

  try {
    const response = await fetch(`${apiUrl.replace(/\/$/, '')}/api/signals`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Probe-Token': token },
      body: JSON.stringify({ source: 'ext', entries }),
    })
    if (response.status === 401) {
      // Jeton mort : inutile de réessayer en boucle avec un secret périmé.
      await chrome.storage.local.set({ lastError: 'Jeton refusé. Réémets-en un.' })
      return
    }
    if (!response.ok) return             // on garde le tampon pour le prochain envoi
    buffer = {}
    await chrome.storage.local.set({ lastFlush: new Date().toISOString(), lastError: '' })
  } catch {
    // Serveur éteint : le tampon reste, rien n'est perdu.
  }
}

chrome.tabs.onActivated.addListener(refresh)
chrome.tabs.onUpdated.addListener((_id, change) => change.url && refresh())
chrome.windows.onFocusChanged.addListener(refresh)
chrome.idle.onStateChanged.addListener(refresh)

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(FLUSH_ALARM, { periodInMinutes: FLUSH_MINUTES })
})
chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create(FLUSH_ALARM, { periodInMinutes: FLUSH_MINUTES })
})
chrome.alarms.onAlarm.addListener((alarm) => alarm.name === FLUSH_ALARM && flush())
