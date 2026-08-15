import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
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
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      // L'API est la source de vérité : le front ne recalcule jamais une règle.
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
