/* La mesure survit-elle à une suspension du script de fond ?
 *
 * **Le défaut que ces tests gardent, et il a coûté deux essais à l'utilisateur.**
 * En manifeste V3, le script de fond est une page d'événements : le navigateur
 * la suspend dès qu'elle ne fait rien et la relance au prochain événement. Les
 * variables de module repartent alors de zéro. Le tampon des minutes se vidait
 * donc avant l'alarme des cinq minutes, et l'envoi ne partait jamais.
 *
 * Le symptôme est le pire qui soit : aucune erreur, aucun refus, aucun message.
 * L'extension affichait un état vide, ce qui est **aussi** ce qu'elle affiche
 * quand il n'y a réellement rien à envoyer — un cas normal et fréquent, puisque
 * tout ce qui tombe dans « autre » n'est jamais transmis. Les deux situations
 * étaient donc indiscernables à l'œil, et seule la lecture du journal du
 * serveur pouvait les séparer.
 *
 * Un test ne peut pas suspendre un vrai navigateur. Il peut faire l'équivalent
 * exact : jeter le module et le réimporter, en gardant le stockage. C'est ce
 * que `relancerLeScript` fait.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/** Un faux navigateur, réduit à ce que le script de fond touche vraiment. */
function faireNavigateur() {
  const stockage = new Map()
  const ecouteurs = { alarme: [], onglet: [] }

  return {
    ecouteurs,
    alarmes: [],
    storage: {
      local: {
        async get(cles) {
          const liste = Array.isArray(cles) ? cles : [cles]
          const out = {}
          for (const cle of liste) if (stockage.has(cle)) out[cle] = stockage.get(cle)
          return out
        },
        async set(objet) {
          for (const [cle, valeur] of Object.entries(objet)) stockage.set(cle, valeur)
        },
      },
    },
    alarms: {
      _posees: new Map(),
      create(nom, options) {
        this._creees = this._creees || []
        this._creees.push({ nom, options })
        this._posees.set(nom, options)
      },
      async get(nom) {
        return this._posees.get(nom)
      },
      onAlarm: { addListener: (fn) => ecouteurs.alarme.push(fn) },
    },
    tabs: {
      _actif: { url: 'https://github.com/mael/coach' },
      async query() {
        return [this._actif]
      },
      onActivated: { addListener: () => {} },
      onUpdated: { addListener: () => {} },
    },
    windows: { onFocusChanged: { addListener: () => {} } },
    idle: {
      _etat: 'active',
      async queryState() {
        return this._etat
      },
      onStateChanged: { addListener: () => {} },
    },
    runtime: {
      onMessage: { addListener: () => {} },
      onInstalled: { addListener: () => {} },
      onStartup: { addListener: () => {} },
    },
  }
}

let navigateur
let envois

/** Charge le script de fond à neuf, en gardant le stockage : c'est exactement
 *  ce que fait le navigateur quand il relance une page d'événements. */
async function relancerLeScript() {
  vi.resetModules()
  await import('./background.js')
  await laisserFinir()
}

/** Laisse les chaînes asynchrones se terminer.
 *
 * L'import déclenche `refresh()`, qui enchaîne stockage, idle, onglets,
 * réglages, écriture, puis parfois un envoi complet. Compter les tours à la
 * main est le meilleur moyen d'écrire un test qui passe pour de mauvaises
 * raisons : on en met assez pour le cas du jour, et le test devient faux au
 * prochain `await` ajouté. On vide la file, point.
 */
async function laisserFinir() {
  for (let i = 0; i < 50; i++) await Promise.resolve()
}

/** Déclenche l'alarme d'envoi, comme le navigateur le ferait. */
async function sonnerLAlarme() {
  for (const fn of navigateur.ecouteurs.alarme) await fn({ name: 'coach-flush' })
  await laisserFinir()
}

beforeEach(async () => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-08-19T10:00:00Z'))

  navigateur = faireNavigateur()
  globalThis.browser = navigateur
  globalThis.chrome = undefined

  envois = []
  globalThis.fetch = vi.fn(async (url, options) => {
    envois.push({ url, body: options?.body ? JSON.parse(options.body) : null })
    return { ok: true, status: 200, json: async () => ({ block_scroll: { armed: false } }) }
  })

  await navigateur.storage.local.set({ apiUrl: 'http://127.0.0.1:8000', token: 'jeton-de-test' })
})

afterEach(() => {
  vi.useRealTimers()
})

describe('la mesure du temps par catégorie', () => {
  it('envoie les minutes passées sur un site connu', async () => {
    await relancerLeScript()

    // Deux minutes sur GitHub, puis l'alarme.
    vi.setSystemTime(new Date('2026-08-19T10:02:00Z'))
    await sonnerLAlarme()

    const signaux = envois.find((e) => e.url.endsWith('/api/signals'))
    expect(signaux).toBeTruthy()
    expect(signaux.body.source).toBe('ext')
    expect(signaux.body.entries).toEqual([
      expect.objectContaining({ category: 'travail_projet', minutes: 2 }),
    ])
  })

  it('survit à une suspension du script de fond', async () => {
    // C'est **le** test. Sans le tampon persistant, la relance repartait d'un
    // tampon vide et l'envoi ne partait jamais.
    await relancerLeScript()

    vi.setSystemTime(new Date('2026-08-19T10:03:00Z'))
    await relancerLeScript() // le navigateur a suspendu puis relancé

    vi.setSystemTime(new Date('2026-08-19T10:04:00Z'))
    await sonnerLAlarme()

    const signaux = envois.find((e) => e.url.endsWith('/api/signals'))
    expect(signaux).toBeTruthy()
    expect(signaux.body.entries[0].minutes).toBeGreaterThanOrEqual(3)
  })

  it('compte la page déjà ouverte, sans attendre un changement d’onglet', async () => {
    // Sans l'appel à `refresh()` au chargement, la catégorie restait « autre »
    // jusqu'au premier changement d'onglet : rester une heure sur la même page
    // de documentation ne comptait rien. Le défaut ne produit pas une mesure
    // fausse mais une absence de mesure, ce qui ne se remarque jamais.
    await relancerLeScript()
    vi.setSystemTime(new Date('2026-08-19T10:05:00Z'))
    await sonnerLAlarme()

    const signaux = envois.find((e) => e.url.endsWith('/api/signals'))
    expect(signaux.body.entries[0].category).toBe('travail_projet')
  })

  it('n’envoie rien pour un site hors catégorie', async () => {
    navigateur.tabs._actif = { url: 'https://un-site-quelconque.example/page' }
    await relancerLeScript()

    vi.setSystemTime(new Date('2026-08-19T10:10:00Z'))
    await sonnerLAlarme()

    expect(envois.find((e) => e.url.endsWith('/api/signals'))).toBeUndefined()
  })

  it('n’envoie rien quand la machine est inactive', async () => {
    navigateur.idle._etat = 'idle'
    await relancerLeScript()

    vi.setSystemTime(new Date('2026-08-19T10:10:00Z'))
    await sonnerLAlarme()

    expect(envois.find((e) => e.url.endsWith('/api/signals'))).toBeUndefined()
  })

  it('envoie dès qu’une minute pleine existe, sans attendre l’alarme', async () => {
    // L'attente n'achetait rien : le serveur reçoit une fenêtre horaire, pas un
    // instant. Elle coûtait en revanche le diagnostic — tant qu'aucun envoi n'a
    // eu lieu, « ça ne marche pas » et « ça n'a pas encore eu lieu » se
    // ressemblent trait pour trait.
    await relancerLeScript()

    // Une minute plus tard, un simple réveil du script suffit : la mesure se
    // ferme et part, sans qu'aucune alarme n'ait sonné.
    vi.setSystemTime(new Date('2026-08-19T10:01:00Z'))
    await relancerLeScript()

    expect(envois.find((e) => e.url.endsWith('/api/signals'))).toBeTruthy()
  })

  it('ne repose pas une alarme qui existe déjà', async () => {
    // Le défaut qui empêchait tout envoi : `alarms.create` remplace l'alarme du
    // même nom et remet son minuteur à zéro. La page d'événements se réveillant
    // toutes les une ou deux minutes, une alarme recréée à chaque réveil
    // n'atteignait jamais son échéance.
    await relancerLeScript()
    const apres_un = navigateur.alarms._creees.length

    await relancerLeScript()
    await relancerLeScript()

    expect(navigateur.alarms._creees.length).toBe(apres_un)
  })

  it('crée son alarme au chargement, pas seulement à l’installation', async () => {
    // `onInstalled` et `onStartup` ne repassent jamais après une suspension.
    // Une extension dont l'alarme a disparu ne s'en plaint pas : elle cesse
    // simplement d'envoyer.
    await relancerLeScript()
    expect(navigateur.alarms._creees).toEqual([
      expect.objectContaining({ nom: 'coach-flush' }),
    ])
  })

  it('vide le tampon après un envoi réussi', async () => {
    await relancerLeScript()
    vi.setSystemTime(new Date('2026-08-19T10:02:00Z'))
    await sonnerLAlarme()

    envois.length = 0
    vi.setSystemTime(new Date('2026-08-19T10:02:30Z'))
    await sonnerLAlarme()

    // Trente secondes ne font pas une minute pleine : rien de plus à envoyer,
    // et surtout pas les deux minutes déjà transmises.
    expect(envois.find((e) => e.url.endsWith('/api/signals'))).toBeUndefined()
  })
})
