/* Les notifications, côté service worker (SPEC §11.7).
 *
 * Ce fichier est importé par le service worker généré au build. Il n'est pas
 * compilé : ce qui tourne ici doit tourner tel quel dans un worker réveillé
 * seul, sans l'app, sans React, et parfois sans que le navigateur soit ouvert.
 *
 * **Le worker ne décide de rien.** Chaque bouton arrive avec l'adresse à
 * appeler, décidée à l'émission par le serveur — c'est la règle des liens
 * signés du §11.7, et elle vaut double ici : un worker n'a pas de jeton (il ne
 * partage ni le stockage local ni la session de l'app), donc tout ce qu'il peut
 * faire, il le fait avec ce que la notification lui donne. Un lien porte un
 * seul geste et expire avec la soirée.
 *
 * **Pourquoi des boutons plutôt qu'un simple clic.** Le gardien tombe le soir
 * où l'on n'ouvre pas l'app — c'est sa définition. Lui répondre demandait
 * jusqu'ici d'ouvrir, de lire, de choisir une durée et de démarrer : quatre
 * gestes au moment précis où l'on n'en fera aucun. « Démarrer 10 min » en fait
 * un seul. Et « Reporter » est la seule réponse honnête à « pas maintenant » :
 * sans lui, la seule façon de faire taire une notification est de la balayer,
 * c'est-à-dire de la perdre.
 */

/* eslint-env serviceworker */

self.addEventListener('push', (event) => {
  let charge = {}
  try {
    charge = event.data ? event.data.json() : {}
  } catch {
    // Une charge illisible ne doit pas faire disparaître la notification : mieux
    // vaut un titre nu qu'un gardien qui n'arrive pas.
    charge = { title: 'Coach', body: '' }
  }

  const actions = Array.isArray(charge.actions) ? charge.actions : []

  event.waitUntil(
    self.registration.showNotification(charge.title || 'Coach', {
      body: charge.body || '',
      icon: '/icon-192.png',
      badge: '/icon-192.png',
      // Une notification par type et par soir : un gardien reporté remplace le
      // gardien, il ne s'empile pas dessus. Une pile de trois gardiens le même
      // soir se lit comme un harcèlement, et le §17 l'interdit.
      tag: charge.kind || 'info',
      renotify: true,
      data: charge,
      // Deux boutons au maximum : au-delà, Android n'en montre pas plus, et le
      // troisième existerait sans jamais être vu.
      actions: actions.slice(0, 2).map((bouton) => ({
        action: bouton.action,
        title: bouton.title,
      })),
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  const charge = event.notification.data || {}
  const actions = Array.isArray(charge.actions) ? charge.actions : []
  const choisi = actions.find((bouton) => bouton.action === event.action)

  event.notification.close()

  event.waitUntil(
    (async () => {
      if (choisi && choisi.post) {
        try {
          await fetch(choisi.post, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: '{}',
          })
        } catch {
          // Hors ligne : le geste est perdu, et c'est le comportement voulu.
          // Le rejouer plus tard ferait démarrer une séance ou reporter un
          // gardien à un moment que personne n'a choisi.
        }
      }

      // Reporter ne demande pas d'ouvrir quoi que ce soit : c'est tout le sens
      // du bouton — « pas maintenant » suivi d'une app qui s'ouvre serait une
      // contradiction.
      if (event.action === 'reporter') return

      await ouvrirLApp(charge)
    })(),
  )
})

/** Ramène la fenêtre existante plutôt que d'en ouvrir une seconde.
 *
 * Deux onglets du coach côte à côte affichent deux états qui divergent dès la
 * première action, et c'est la façon la plus sûre de croire qu'une séance n'a
 * pas démarré alors qu'elle tourne.
 */
async function ouvrirLApp(charge) {
  const cible = charge.action_url || '/'
  const fenetres = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })

  for (const fenetre of fenetres) {
    if ('focus' in fenetre) {
      if (charge.action_url && 'navigate' in fenetre) {
        try {
          await fenetre.navigate(cible)
        } catch {
          /* même origine seulement : sinon on se contente du focus */
        }
      }
      return fenetre.focus()
    }
  }

  if (self.clients.openWindow) return self.clients.openWindow(cible)
}
