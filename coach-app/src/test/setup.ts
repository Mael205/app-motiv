/** Ce que jsdom ne fournit pas, et dont l'application dépend.
 *
 * Chaque bouchon ici correspond à une API que le navigateur a et que jsdom n'a
 * pas. Aucun ne remplace du code à nous : ce sont des trous de l'environnement
 * de test, pas des raccourcis sur ce qu'on vérifie.
 */

import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

/* `IntersectionObserver` n'existe pas dans jsdom, et la révélation au
 * défilement s'en sert partout (`revelerAuDefilement`). Le bouchon
 * **déclenche immédiatement** l'entrée plutôt que de ne rien faire : sans ça,
 * tout élément révélé resterait à `opacity: 0` dans les tests, et une
 * assertion sur ce qui est visible mentirait dans les deux sens. */
class ObservateurImmediat implements IntersectionObserver {
  readonly root = null
  readonly rootMargin = ''
  readonly scrollMargin = ''
  readonly thresholds: ReadonlyArray<number> = []
  private rappel: IntersectionObserverCallback

  constructor(rappel: IntersectionObserverCallback) {
    this.rappel = rappel
  }

  observe(cible: Element): void {
    this.rappel(
      [{ target: cible, isIntersecting: true } as IntersectionObserverEntry],
      this,
    )
  }

  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return []
  }
}

vi.stubGlobal('IntersectionObserver', ObservateurImmediat)

/* jsdom n'implémente pas `matchMedia`. On répond « non » à tout : les tests
 * s'exécutent donc dans le cas *animé* et *pointeur fin*, celui qui a le plus
 * de code, plutôt que dans la voie de repli de `prefers-reduced-motion`. */
vi.stubGlobal(
  'matchMedia',
  vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
)

/* Le démontage entre deux tests. Sans lui, deux rendus du même écran
 * coexistent dans le document et `getByText` échoue sur un doublon dont la
 * cause n'a rien à voir avec ce qu'on teste. */
afterEach(() => {
  cleanup()
})
