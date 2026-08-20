import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

/* Config séparée de `vite.config.ts` volontairement : celle-ci charge le plugin
 * PWA, qui génère un service worker et n'a rien à faire dans une passe de
 * tests. Vitest préfère ce fichier quand il existe.
 *
 * jsdom parce que ce qu'on teste ici touche au DOM — des variables CSS posées
 * sur le <body>, des écrans montés et leurs états de panne — sans jamais avoir
 * besoin d'un vrai navigateur. Les mesures qui en exigent un vivent dans
 * `tools/`, et leurs règles de verdict sont, elles, testées ici sans navigateur
 * du tout.
 *
 * Le plugin React est là depuis que les tests montent des composants : sans
 * lui, un `.tsx` ne se transforme pas et le fichier ne se charge même pas.
 * `include` couvre donc les deux extensions — la précédente ne prenait que
 * `.test.ts`, si bien qu'un test de composant posé à côté n'aurait jamais été
 * exécuté, et personne ne l'aurait su. */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}', 'tools/**/*.test.{ts,tsx}'],
    setupFiles: ['src/test/setup.ts'],
    globals: false,
    restoreMocks: true,
  },
})
