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
