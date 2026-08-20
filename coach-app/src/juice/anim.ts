/** Le mouvement du produit, joué par anime.js.
 *
 * Le §7 limite les effets *riches* à quatre moments et interdit l'animation
 * sur le chemin critique. Rien ici ne contredit ces deux règles : ce fichier
 * ne porte que du mouvement d'**entrée** — ce qui apparaît, et comment. Aucune
 * de ces fonctions ne s'interpose entre un doigt et une action ; le bouton
 * « Démarrer » répond toujours à zéro milliseconde, et son écran de session se
 * monte sans passer par ici.
 *
 * Quatre gestes, et un seul vocabulaire :
 *
 *   — `animerEntree`   l'écran d'onglet arrive, avec sa direction.
 *   — `revelerAuDefilement`  les cartes se lèvent quand on les atteint.
 *   — `devoilerTitre`  le titre se découvre de gauche à droite.
 *   — `animerAnneau`   le trait de complétion se trace.
 *
 * Tous respectent `prefers-reduced-motion` en posant l'état final
 * immédiatement — jamais en supprimant l'élément, ce qui ferait perdre
 * l'information plutôt que le mouvement.
 */

import { animate, createAnimatable, cubicBezier, stagger, utils } from 'animejs'

/** Les courbes du système de design, dans la syntaxe d'anime.js.
 *
 * `ENTREE` sort fort et s'arrête net : c'est ce qui donne l'impression que la
 * chose *arrive* au lieu de se fondre. `IMPACT` dépasse sa cible de quelques
 * pour cent avant de revenir — réservé à ce qui doit se faire remarquer une
 * fois, jamais à ce qui se répète.
 *
 * Des **fonctions**, pas des chaînes : anime.js v4 a retiré du cœur la syntaxe
 * `ease: 'cubicBezier(...)'`. Elle ne lève pas d'erreur — elle émet un
 * avertissement en console et retombe sur la courbe par défaut, si bien que
 * tout paraît animé mais qu'aucune des courbes choisies ne s'applique. */
const ENTREE = cubicBezier(0.22, 1, 0.36, 1)
const IMPACT = cubicBezier(0.34, 1.4, 0.64, 1)

function motionReduite(): boolean {
  return typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Retarde un geste jusqu'à ce que son élément soit à l'écran.
 *
 * Sans ça, une animation d'arrivée se joue au montage pour les quarante cartes
 * de la page, dont trente-cinq sont hors champ : on descend ensuite sur du
 * contenu déjà posé, et le mouvement n'a servi à personne.
 */
export function quandVisible(element: Element, geste: () => () => void): () => void {
  let nettoyer: (() => void) | null = null

  const observateur = new IntersectionObserver(
    (entrees) => {
      if (!entrees.some((e) => e.isIntersecting)) return
      observateur.disconnect()
      nettoyer = geste()
    },
    { threshold: 0.1 },
  )
  observateur.observe(element)

  return () => {
    observateur.disconnect()
    nettoyer?.()
  }
}

/**
 * Trace l'anneau depuis zéro jusqu'à sa valeur, et fait courir le pourcentage
 * avec lui.
 *
 * Les deux sont sur la même horloge : un chiffre qui atteindrait sa valeur
 * avant que le trait ait fini de tourner ferait mentir la forme. C'est aussi
 * pourquoi anime.js est ici et pas une transition CSS — une transition n'a
 * rien à interpoler au premier rendu, et ne sait pas écrire dans un texte.
 */
export function animerAnneau(
  cercle: SVGCircleElement,
  circonference: number,
  pourcent: number,
  chiffre?: HTMLElement | null,
  retard = 0,
): () => void {
  const offsetFinal = circonference * (1 - pourcent / 100)

  if (motionReduite()) {
    utils.set(cercle, { strokeDashoffset: offsetFinal })
    if (chiffre) chiffre.textContent = String(pourcent)
    return () => {}
  }

  const compteur = { valeur: 0 }
  const anim = animate(cercle, {
    strokeDashoffset: [circonference, offsetFinal],
    duration: 1100,
    delay: retard,
    ease: ENTREE,
    onUpdate: (self) => {
      if (!chiffre) return
      compteur.valeur = pourcent * self.progress
      chiffre.textContent = String(Math.round(compteur.valeur))
    },
    onComplete: () => {
      if (chiffre) chiffre.textContent = String(pourcent)
    },
  })

  return () => anim.revert()
}

/**
 * Fait entrer un écran d'onglet, dans le sens du déplacement.
 *
 * `sens` vaut +1 quand on va vers la droite de la barre d'onglets, −1 vers la
 * gauche. L'écran arrive donc du côté d'où il vient : c'est ce qui rend la
 * barre d'onglets spatiale au lieu d'être une liste de boutons qui remplacent
 * le contenu. Zéro au premier montage — rien ne précède, rien n'a de côté.
 *
 * Le mouvement est porté par le **conteneur**, jamais par son contenu :
 * Projets et Journal affichent « Chargement… » avant leurs données, et animer
 * le contenu revenait à animer ce mot puis à laisser le reste surgir d'un coup.
 */
export function animerEntree(element: HTMLElement, sens = 0): () => void {
  if (motionReduite()) {
    utils.set(element, { opacity: 1, x: 0, y: 0 })
    return () => {}
  }

  const anim = animate(element, {
    opacity: [0, 1],
    perspective: 1400,
    // L'ecran pivote autour de son bord d'arrivee et revient de loin : on ne
    // remplace pas une image par une autre, on tourne un panneau vers soi.
    rotateY: sens === 0 ? [0, 0] : [sens * 9, 0],
    z: [-140, 0],
    x: sens === 0 ? [0, 0] : [sens * 34, 0],
    y: sens === 0 ? [14, 0] : [0, 0],
    duration: 460,
    ease: ENTREE,
    /* La transformation est effacée à l'arrivée, et pas seulement remise à
       zéro : un élément transformé — même d'une matrice identité à
       perspective — devient le bloc conteneur de ses descendants en
       `position: fixed`. Les surcouches plein écran qui vivent *dans* un
       onglet, comme la révélation de carte de la fiche de personnage, se
       seraient ancrées sur ce conteneur au lieu de la fenêtre. */
    onComplete: () => {
      element.style.transform = ''
    },
  })

  return () => anim.revert()
}

/**
 * Incline une surface vers le pointeur, et fait glisser un reflet avec lui.
 *
 * C'est le seul endroit du produit ou une animation suit le doigt en continu.
 * Elle tient pour trois raisons : elle n'existe que sur pointeur fin — au
 * doigt, il n'y a pas de survol, donc pas d'inclinaison a defaire ; elle ne
 * lit la geometrie de l'element qu'a l'entree du pointeur, jamais a chaque
 * mouvement, ce qui serait un calcul de mise en page par image ; et elle
 * n'intercepte aucun clic.
 *
 * `createAnimatable` plutot qu'un `animate` par mouvement : l'objet garde une
 * inertie propre, si bien que la carte *rattrape* le pointeur au lieu de lui
 * etre collee. C'est cette latence qui fait la difference entre une surface
 * qui a du poids et un calque qui suit la souris.
 */
export function inclinerAuPointeur(element: HTMLElement, amplitude = 8): () => void {
  if (motionReduite()) return () => {}
  if (typeof matchMedia !== 'undefined' && !matchMedia('(hover: hover) and (pointer: fine)').matches) {
    return () => {}
  }

  utils.set(element, { perspective: 900 })

  const suivi = createAnimatable(element, {
    rotateX: 340,
    rotateY: 340,
    z: 340,
    ease: 'out(3)',
  })

  let cadre: DOMRect | null = null

  function entrer() {
    cadre = element.getBoundingClientRect()
  }

  function bouger(e: PointerEvent) {
    if (!cadre) cadre = element.getBoundingClientRect()
    const px = (e.clientX - cadre.left) / cadre.width
    const py = (e.clientY - cadre.top) / cadre.height
    suivi.rotateY((px - 0.5) * amplitude * 2)
    suivi.rotateX((0.5 - py) * amplitude * 2)
    suivi.z(22)
    // Le reflet est peint par le CSS ; on ne lui donne qu'une position.
    element.style.setProperty('--gx', `${px * 100}%`)
    element.style.setProperty('--gy', `${py * 100}%`)
    element.style.setProperty('--glare', '1')
  }

  function partir() {
    cadre = null
    suivi.rotateX(0)
    suivi.rotateY(0)
    suivi.z(0)
    element.style.setProperty('--glare', '0')
  }

  element.addEventListener('pointerenter', entrer)
  element.addEventListener('pointermove', bouger)
  element.addEventListener('pointerleave', partir)

  return () => {
    element.removeEventListener('pointerenter', entrer)
    element.removeEventListener('pointermove', bouger)
    element.removeEventListener('pointerleave', partir)
    suivi.revert()
    element.style.removeProperty('--glare')
  }
}

/**
 * Découvre un titre de gauche à droite, comme un trait qu'on tire.
 *
 * Un masque plutôt qu'un fondu, et surtout plutôt qu'un découpage en lettres :
 * découper le texte demande de réécrire le contenu de l'élément, or React en
 * est propriétaire et le remet en place au premier rendu suivant. Le masque
 * obtient le même geste sans toucher au DOM que React tient.
 */
export function devoilerTitre(element: HTMLElement, retard = 0): () => void {
  if (motionReduite()) {
    utils.set(element, { opacity: 1, clipPath: 'inset(0 0 0 0)' })
    return () => {}
  }

  const anim = animate(element, {
    opacity: [0, 1],
    clipPath: ['inset(0 100% 0 0)', 'inset(0 0% 0 0)'],
    y: [6, 0],
    duration: 620,
    delay: retard,
    ease: ENTREE,
  })

  return () => anim.revert()
}

/**
 * Lève les éléments un par un, quand le défilement les atteint.
 *
 * Ce qui est déjà à l'écran au montage entre en cascade tout de suite ; le
 * reste attend d'être approché. Sans cette distinction, une page de projets
 * jouerait quarante animations d'un coup dont trente-cinq hors champ, et
 * l'utilisateur arriverait en bas sur du contenu déjà posé.
 *
 * Le déclencheur est un `IntersectionObserver` — le navigateur le calcule hors
 * du fil principal, là où un écouteur de défilement recalculerait la position
 * de chaque carte à chaque image.
 */
export type Geste = 'lever' | 'devoiler'

/** L'état de départ et le mouvement de chaque geste, au même endroit : c'est
 *  ce qui garantit qu'un élément caché avant l'observation est bien celui que
 *  l'animation ramène, et qu'aucun ne reste invisible. */
const GESTES: Record<Geste, { depart: Parameters<typeof utils.set>[1]; vers: Parameters<typeof animate>[1] }> = {
  /* La carte se **redresse** au lieu de monter à plat : elle part couchée en
     arrière de dix-huit degrés et reculée de quarante pixels, et elle se lève
     face à nous. C'est le même geste qu'une carte qu'on relève sur une table,
     et c'est ce que le fondu-glissement ne dit pas.
     La perspective est écrite sur l'élément lui-même — mille pixels, un point
     de fuite par carte. Une perspective posée sur le parent donnerait un point
     de fuite commun, donc des cartes de plus en plus tordues à mesure qu'on
     s'éloigne du centre de la colonne. */
  lever: {
    depart: { opacity: 0, perspective: 1000, y: 26, z: -40, rotateX: -18 },
    vers: {
      opacity: [0, 1],
      y: [26, 0],
      z: [-40, 0],
      rotateX: [-18, 0],
      duration: 620,
      ease: ENTREE,
    },
  },
  /* Le titre se découvre de gauche à droite, comme un trait qu'on tire.
     L'état caché est une **opacité**, jamais le découpage : un élément en
     `clip-path: inset(0 100% 0 0)` a une aire visible nulle, et
     l'IntersectionObserver ne le voit donc jamais entrer — il se rendait
     lui-même inobservable et restait invisible pour toujours. Le découpage
     n'existe que dans la valeur de départ de l'animation, posée au moment où
     elle démarre, c'est-à-dire après l'observation. */
  devoiler: {
    depart: { opacity: 0 },
    vers: {
      opacity: [0, 1],
      clipPath: ['inset(0 100% 0 0)', 'inset(0 0% 0 0)'],
      duration: 640,
      ease: ENTREE,
    },
  },
}

export function revelerAuDefilement(elements: HTMLElement[], geste: Geste = 'lever'): () => void {
  if (elements.length === 0) return () => {}

  const { depart, vers } = GESTES[geste]
  const finale = { opacity: 1, x: 0, y: 0, z: 0, rotateX: 0, clipPath: 'none' }

  if (motionReduite()) {
    utils.set(elements, finale)
    return () => {}
  }

  utils.set(elements, depart)

  const lot: HTMLElement[] = []
  let planifie = 0

  /** Les éléments qui franchissent le seuil dans la même image entrent en
   *  cascade ensemble. Les vider un par un donnerait un décalage lié à l'ordre
   *  de notification du navigateur, qui n'est pas l'ordre de lecture. */
  function viderLeLot() {
    planifie = 0
    const cibles = lot.splice(0, lot.length)
    if (cibles.length === 0) return
    animate(cibles, { ...vers, delay: stagger(cibles.length > 8 ? 28 : 55) })
  }

  const observateur = new IntersectionObserver(
    (entrees) => {
      for (const entree of entrees) {
        if (!entree.isIntersecting) continue
        lot.push(entree.target as HTMLElement)
        observateur.unobserve(entree.target)
      }
      if (lot.length && !planifie) planifie = requestAnimationFrame(viderLeLot)
    },
    /* Seuil zéro, et c'est la marge négative qui décide du moment : la carte
       entre quand elle a dépassé de soixante pixels le bas de la fenêtre. Un
       seuil exprimé en proportion de l'aire se laisse piéger par tout état
       caché qui réduit la surface visible — une rotation marquée, un
       découpage — et l'élément attend alors un déclenchement qui ne vient
       jamais. La marge, elle, ne dépend que de la position. */
    { threshold: 0, rootMargin: '0px 0px -60px 0px' },
  )

  elements.forEach((e) => observateur.observe(e))

  /* Le nettoyage repose l'état final plutôt que l'état de départ : si l'écran
     est démonté au milieu d'une cascade, ce qui reste doit rester lisible. */
  return () => {
    observateur.disconnect()
    if (planifie) cancelAnimationFrame(planifie)
    utils.set(elements, finale)
  }
}

/**
 * La secousse d'une valeur qui vient de changer.
 *
 * Un seul rebond, court, sur `scale` : c'est le retour qu'on donne à un
 * compteur qui monte, et il ne se joue que sur une valeur déjà à l'écran —
 * jamais sur son apparition, qui a déjà son mouvement.
 */
export function pulser(element: HTMLElement): () => void {
  if (motionReduite()) return () => {}

  const anim = animate(element, {
    scale: [1, 1.14, 1],
    duration: 420,
    ease: IMPACT,
  })

  return () => anim.revert()
}
