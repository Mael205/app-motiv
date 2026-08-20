import { api } from './api'

/** L'abonnement Web Push (SPEC §11.2, §11.7).
 *
 * Le serveur savait envoyer depuis le début, la PWA n'a **jamais demandé à
 * recevoir** : `pushKey` et `subscribePush` existaient dans le client d'API et
 * personne ne les appelait. Le gardien du soir partait donc sur Discord ou dans
 * les logs, jamais en notification système — c'est-à-dire jamais là où on le
 * lit. Un déclencheur qui n'arrive pas est un déclencheur qui n'existe pas
 * (§11.2), et c'était le cas du principal.
 *
 * **La permission ne se demande pas au chargement.** Une demande qui tombe
 * avant qu'on ait compris à quoi elle sert se refuse par réflexe, et un refus
 * ne se reprend pas : le navigateur ne repose plus la question. Elle est donc
 * demandée sur un geste explicite, et seulement là. Au démarrage, on se
 * contente de **réparer** un abonnement déjà accordé — c'est silencieux, ça ne
 * demande rien, et ça couvre le cas réel : un abonnement expire tout seul au
 * bout de quelques semaines.
 */

export type EtatDesNotifications = 'impossible' | 'a_demander' | 'refuse' | 'actif'

export function etatDesNotifications(): EtatDesNotifications {
  if (typeof Notification === 'undefined' || !('serviceWorker' in navigator)) return 'impossible'
  if (Notification.permission === 'granted') return 'actif'
  if (Notification.permission === 'denied') return 'refuse'
  return 'a_demander'
}

/** Réabonne l'appareil si la permission est déjà accordée. Ne demande rien. */
export async function reparerLAbonnement(): Promise<boolean> {
  if (etatDesNotifications() !== 'actif') return false
  return abonner()
}

/** Demande la permission, puis abonne. À n'appeler que depuis un geste. */
export async function activerLesNotifications(): Promise<EtatDesNotifications> {
  if (etatDesNotifications() === 'impossible') return 'impossible'
  const reponse = await Notification.requestPermission()
  if (reponse !== 'granted') return reponse === 'denied' ? 'refuse' : 'a_demander'
  await abonner()
  return 'actif'
}

async function abonner(): Promise<boolean> {
  try {
    const registration = await navigator.serviceWorker.ready
    const { public_key } = await api.pushKey()
    // Sans clé VAPID configurée côté serveur, le canal est inactif et le dit
    // (`WebPushChannel.available`). S'abonner quand même produirait un
    // abonnement que personne ne peut utiliser.
    if (!public_key) return false

    const existant = await registration.pushManager.getSubscription()
    const abonnement =
      existant ??
      (await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: cleEnOctets(public_key),
      }))

    await api.subscribePush(abonnement.toJSON(), nomDeLAppareil(), typeDAppareil())
    return true
  } catch {
    // Un abonnement raté n'est jamais bloquant : le §11.2 prévoit la redondance
    // des canaux précisément pour ça, et Discord reste debout.
    return false
  }
}

/** Le nom sert à ne pas empiler dix abonnements pour la même machine : côté
 *  serveur, `update_or_create` se fait sur (utilisateur, nom). */
function nomDeLAppareil(): string {
  return typeDAppareil() === 'phone' ? 'Téléphone' : 'PC'
}

function typeDAppareil(): 'pc' | 'phone' {
  const mobile = /android|iphone|ipad|ipod/i.test(navigator.userAgent)
  return mobile ? 'phone' : 'pc'
}

/** base64url → octets, ce que `pushManager.subscribe` exige.
 *
 * Le tampon est alloué explicitement : `Uint8Array.from` rend un tableau dont
 * le tampon peut être partagé du point de vue des types, et l'API des
 * abonnements n'accepte qu'un `ArrayBuffer` ordinaire.
 */
function cleEnOctets(base64: string): ArrayBuffer {
  const rembourrage = '='.repeat((4 - (base64.length % 4)) % 4)
  const brut = atob((base64 + rembourrage).replace(/-/g, '+').replace(/_/g, '/'))
  const tampon = new ArrayBuffer(brut.length)
  const octets = new Uint8Array(tampon)
  for (let i = 0; i < brut.length; i += 1) octets[i] = brut.charCodeAt(i)
  return tampon
}
