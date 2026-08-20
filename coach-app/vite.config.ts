import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      /* Le service worker généré importe nos deux gestionnaires : `push` et
       * `notificationclick` (§11.7). C'est volontairement un `importScripts`
       * plutôt qu'un worker écrit à la main — Workbox garde la précache et la
       * mise à jour automatique, et le seul code que nous maintenons est celui
       * qui nous appartient : quarante lignes de notification, pas une
       * réimplémentation de cache. */
      workbox: { importScripts: ['/push-sw.js'] },
      manifest: {
        name: 'Coach',
        short_name: 'Coach',
        description: 'Le cadre, pas les encouragements.',
        lang: 'fr',
        theme_color: '#191320',
        background_color: '#191320',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
        /* La cible de partage Android (§11.7). Le coach apparaît dans le menu
         * « Partager » de n'importe quelle app : une vidéo, un article, un
         * message deviennent une idée au frigo sans ouvrir quoi que ce soit.
         *
         * En GET et non en POST, à dessein : un partage en POST oblige le
         * service worker à intercepter la requête et à rejouer la navigation
         * lui-même, donc à faire dépendre la capture d'un worker installé et
         * réveillé. Le GET arrive dans l'URL, l'app le lit au démarrage, et ça
         * marche même au premier lancement. */
        share_target: {
          action: '/',
          method: 'GET',
          params: { title: 'titre', text: 'texte', url: 'adresse' },
        },
      },
    }),
  ],
  server: {
    port: 5173,
    /* Les hôtes autorisés à atteindre le serveur de développement.
     *
     * Vite refuse par défaut toute requête dont l'en-tête `Host` n'est pas
     * `localhost` — c'est sa protection contre le « DNS rebinding », qui
     * permettrait à une page malveillante de piloter le serveur de dev depuis
     * le navigateur. Le refus est une coupure de connexion sèche, sans page
     * d'erreur : en passant par un tunnel ou par Tailscale pour installer la
     * PWA sur le téléphone (docs/installer.md), on ne voit rien d'autre qu'un
     * « site inaccessible », et rien n'indique d'où ça vient.
     *
     * D'où la variable plutôt qu'un `true` en dur : la protection reste active
     * par défaut, et ne s'ouvre que sur les noms qu'on nomme, le temps d'une
     * session.
     *
     *   COACH_HOSTS=xxx.trycloudflare.com npm run dev
     *   COACH_HOSTS=mon-pc.mon-reseau.ts.net npm run dev
     */
    allowedHosts: process.env.COACH_HOSTS?.split(',').filter(Boolean),
    proxy: {
      // L'API est la source de vérité : le front ne recalcule jamais une règle.
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  /* `npm run preview` sert la version construite — c'est elle qu'on installe
   * pour de vrai — et applique la même vérification d'hôte. */
  preview: {
    allowedHosts: process.env.COACH_HOSTS?.split(',').filter(Boolean),
  },
})
