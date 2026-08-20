/** Le son des séquences (SPEC §7).
 *
 * **Synthétisé, pas enregistré.** Aucun fichier audio n'entre dans le dépôt, et
 * ce n'est pas une économie de place : un son de jeu tiré d'une banque a une
 * signature sonore qui n'est pas celle-ci, et quatre timbres cousus depuis
 * quatre sources différentes ne forment pas une famille. Ici les cinq sons
 * descendent des mêmes oscillateurs et de la même enveloppe, donc ils
 * s'entendent comme un seul instrument.
 *
 * **La règle du §7 vaut pour l'oreille comme pour l'œil.** Quatre moments
 * seulement portent des effets riches ; partout ailleurs l'interface est
 * calme — donc silencieuse. Il n'y a pas de son de survol, pas de son de
 * navigation, pas de clic générique. Un son qui se déclenche cent fois par
 * soirée cesse d'être une récompense et devient une nuisance, exactement comme
 * une animation trop fréquente.
 *
 * **Trois contraintes de navigateur décident du reste :**
 *
 * 1. Un contexte audio créé avant un geste de l'utilisateur naît suspendu.
 *    Il est donc créé paresseusement, au premier son demandé, et repris si le
 *    navigateur l'a suspendu entre-temps.
 * 2. Un son qui part alors que la page est cachée n'a aucun destinataire mais
 *    fait sursauter quand on revient. On ne joue rien si le document est caché.
 * 3. La coupure doit survivre au rechargement, parce qu'on ne coupe pas le son
 *    d'une app qu'on ouvre le soir une fois par soir.
 */

const CLE = 'coach.sound'

let ctx: AudioContext | null = null
let master: GainNode | null = null
let coupe = lireCoupure()

function lireCoupure(): boolean {
  try {
    return localStorage.getItem(CLE) === 'off'
  } catch {
    return false
  }
}

export function soundMuted(): boolean {
  return coupe
}

export function setSoundMuted(valeur: boolean): void {
  coupe = valeur
  try {
    localStorage.setItem(CLE, valeur ? 'off' : 'on')
  } catch {
    /* mode privé : la préférence ne survit pas, le son marche quand même */
  }
  if (master && ctx) master.gain.setTargetAtTime(valeur ? 0 : 0.9, ctx.currentTime, 0.02)
}

function audio(): AudioContext | null {
  if (coupe || typeof window === 'undefined') return null
  if (document.hidden) return null

  if (!ctx) {
    const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!Ctor) return null
    ctx = new Ctor()
    master = ctx.createGain()
    master.gain.value = 0.9
    master.connect(ctx.destination)
  }
  // Safari et Chrome suspendent le contexte tant qu'aucun geste n'a eu lieu, et
  // le resuspendent après une longue inactivité d'onglet.
  if (ctx.state === 'suspended') void ctx.resume()
  return ctx
}

/** Une enveloppe percussive : attaque courte, extinction exponentielle.
 *
 * Toujours exponentielle, jamais linéaire. Une extinction linéaire s'entend
 * comme une coupure nette parce que l'oreille perçoit l'intensité en
 * logarithme — c'est le défaut qui fait qu'un son synthétisé sonne « bip ».
 */
function enveloppe(gain: GainNode, t: number, attaque: number, duree: number, pic: number) {
  gain.gain.setValueAtTime(0.0001, t)
  gain.gain.exponentialRampToValueAtTime(Math.max(0.0002, pic), t + attaque)
  gain.gain.exponentialRampToValueAtTime(0.0001, t + duree)
}

type NoteOpts = {
  freq: number
  duree?: number
  gain?: number
  type?: OscillatorType
  attaque?: number
  retard?: number
  /** Glissando : fréquence d'arrivée. Un son qui monte se lit comme un gain. */
  vers?: number
}

function note({ freq, duree = 0.3, gain = 0.18, type = 'triangle', attaque = 0.008, retard = 0, vers }: NoteOpts) {
  const c = audio()
  if (!c || !master) return
  const t = c.currentTime + retard

  const osc = c.createOscillator()
  osc.type = type
  osc.frequency.setValueAtTime(freq, t)
  if (vers) osc.frequency.exponentialRampToValueAtTime(vers, t + duree * 0.85)

  const g = c.createGain()
  enveloppe(g, t, attaque, duree, gain)

  osc.connect(g).connect(master)
  osc.start(t)
  osc.stop(t + duree + 0.05)
}

/** Souffle filtré : le composant « air » des impacts et des balayages. */
function souffle({ duree = 0.3, gain = 0.12, retard = 0, coupure = 1800, q = 0.7, vers }: {
  duree?: number
  gain?: number
  retard?: number
  coupure?: number
  q?: number
  vers?: number
}) {
  const c = audio()
  if (!c || !master) return
  const t = c.currentTime + retard

  const frames = Math.max(1, Math.floor(c.sampleRate * duree))
  const buffer = c.createBuffer(1, frames, c.sampleRate)
  const data = buffer.getChannelData(0)
  for (let i = 0; i < frames; i++) data[i] = Math.random() * 2 - 1

  const src = c.createBufferSource()
  src.buffer = buffer

  const filtre = c.createBiquadFilter()
  filtre.type = 'bandpass'
  filtre.frequency.setValueAtTime(coupure, t)
  if (vers) filtre.frequency.exponentialRampToValueAtTime(vers, t + duree)
  filtre.Q.value = q

  const g = c.createGain()
  enveloppe(g, t, 0.01, duree, gain)

  src.connect(filtre).connect(g).connect(master)
  src.start(t)
  src.stop(t + duree + 0.05)
}

/** Un accord, joué en arpège serré plutôt que plaqué.
 *
 * Quelques millisecondes d'écart entre les notes suffisent à faire entendre un
 * accord plutôt qu'un bloc : plaqué à l'échantillon près, il sonne électronique.
 */
function accord(freqs: number[], opts: Omit<NoteOpts, 'freq'> & { ecart?: number } = {}) {
  const { ecart = 0.045, retard = 0, ...reste } = opts
  freqs.forEach((f, i) => note({ ...reste, freq: f, retard: retard + i * ecart }))
}

// Gamme de référence : une pentatonique mineure sur La. Elle n'a pas de
// dissonance possible, donc deux sons qui se chevauchent ne jurent jamais —
// ce qui arrive dès qu'une session se termine sur un passage de niveau.
const LA3 = 220
const DO4 = 261.63
const RE4 = 293.66
const MI4 = 329.63
const SOL4 = 392
const LA4 = 440
const DO5 = 523.25
const MI5 = 659.25
const LA5 = 880

export const sfx = {
  /** Entrée en session : un élan, pas une fanfare.
   *
   * L'ancienne version montait de deux notes en 360 ms et s'entendait comme un
   * accusé de réception. Celle-ci ajoute deux choses et pas une de plus :
   *
   * - **une aspiration** avant l'attaque, filtre qui s'ouvre en 90 ms. C'est
   *   elle qui donne l'impression d'entrer quelque part au lieu d'appuyer sur
   *   un bouton ;
   * - **quatre notes au lieu de deux**, resserrées à 55 ms d'écart, qui montent
   *   d'une octave complète. La montée fait l'enthousiasme ; le resserrement
   *   fait qu'elle reste légère.
   *
   * Toujours sous 500 ms au total, et sans grave appuyé : ce son se joue tous
   * les soirs. Ce qui se répète doit rester léger, sinon on finit par couper le
   * son de l'app — et le §7 perd sa moitié sonore d'un coup.
   */
  sessionStart() {
    souffle({ duree: 0.16, gain: 0.055, coupure: 320, vers: 3200, q: 0.5 })
    accord([LA3, DO4, MI4, LA4], {
      duree: 0.34,
      gain: 0.115,
      type: 'triangle',
      ecart: 0.055,
      retard: 0.05,
    })
    // Une pointe claire tout en haut, très courte : l'étincelle du départ.
    note({ freq: MI5, duree: 0.2, gain: 0.05, type: 'sine', retard: 0.22 })
  },

  /** Fin de session : accord chaud qui redescend. Le travail est posé. */
  sessionEnd() {
    accord([LA4, MI4, DO4], { duree: 0.8, gain: 0.13, type: 'sine', ecart: 0.06 })
    note({ freq: LA3 / 2, duree: 0.9, gain: 0.1, type: 'sine' })
  },

  /** Prolongation : deux notes qui montent d'un ton, et rien de plus.
   *
   * Volontairement plus discret que l'entrée en session. Prolonger n'est pas un
   * événement : c'est la même séance qui continue, et un son de récompense
   * ferait du bouton une chose à cliquer plutôt qu'une chose à décider.
   */
  sessionExtend() {
    accord([MI4, SOL4], { duree: 0.26, gain: 0.09, type: 'triangle', ecart: 0.06 })
  },

  /** Passage de niveau : arpège ascendant. L'événement le plus fréquent des rares. */
  levelUp() {
    accord([LA4, DO5, MI5, LA5], { duree: 0.55, gain: 0.14, type: 'triangle', ecart: 0.07 })
    souffle({ duree: 0.5, gain: 0.05, coupure: 900, vers: 5200, retard: 0.05 })
  },

  /** Mort du boss : impact grave, puis une quinte qui s'ouvre. */
  bossKill() {
    note({ freq: 90, duree: 0.7, gain: 0.3, type: 'sine', vers: 45 })
    souffle({ duree: 0.55, gain: 0.16, coupure: 2600, vers: 200 })
    accord([LA3, MI4, LA4], { duree: 1.1, gain: 0.12, type: 'sawtooth', ecart: 0.08, retard: 0.16 })
  },

  /** Le coup critique : **deux fois le même son**, à 70 ms d'écart.
   *
   * C'est tout le sujet. Un critique double une valeur ; un son qui double
   * l'annonce sans qu'on ait à lire le mot. Un timbre inédit aurait dit
   * « autre chose s'est passé », alors qu'il ne s'est rien passé d'autre — la
   * même session, comptée deux fois.
   *
   * La seconde frappe est plus haute d'une quinte et plus courte : c'est la
   * répétition qui porte l'information, et une répétition identique
   * s'entendrait comme un écho, donc comme un défaut.
   */
  crit() {
    souffle({ duree: 0.05, gain: 0.1, coupure: 6000, q: 3 })
    note({ freq: LA4, duree: 0.16, gain: 0.18, type: 'square', attaque: 0.003 })
    note({ freq: MI5, duree: 0.12, gain: 0.16, type: 'square', attaque: 0.003, retard: 0.07 })
    note({ freq: LA5, duree: 0.5, gain: 0.07, type: 'triangle', retard: 0.075, attaque: 0.02 })
  },

  /** Le boss change de phase (§12.4). Il ne gagne rien : il se réveille.
   *
   * Donc pas d'arpège montant — ce qui monte se lit comme un gain, et rien
   * n'est gagné ici. Un grave qui **descend** sous un souffle qui s'ouvre : la
   * même bête, plus près.
   */
  bossPhase() {
    note({ freq: 130.81, duree: 0.9, gain: 0.22, type: 'sawtooth', vers: 98 })
    souffle({ duree: 0.7, gain: 0.1, coupure: 300, vers: 2400 })
    note({ freq: LA3, duree: 1.2, gain: 0.06, type: 'triangle', retard: 0.12, attaque: 0.09 })
  },

  /** Fin de saison : un son long, le seul du lot. Il arrive une fois par mois. */
  seasonEnd() {
    note({ freq: 110, duree: 2.2, gain: 0.2, type: 'sine' })
    accord([LA3, DO4, MI4, SOL4], { duree: 1.8, gain: 0.1, type: 'triangle', ecart: 0.11, retard: 0.1 })
    souffle({ duree: 1.6, gain: 0.06, coupure: 400, vers: 3000 })
  },

  /** Le palier d'une branche de compétences (§12.9).
   *
   * Il partageait le son de fin de session — un accord qui **descend**, ce qui
   * est juste pour poser un travail et faux pour franchir un palier. Ce qui
   * monte se lit comme un gain ; ce qui descend se lit comme une clôture, et
   * l'oreille ne se trompe jamais là-dessus.
   *
   * Le timbre est celui d'une enclume : une attaque métallique très courte, deux
   * notes qui montent d'une quinte, et une queue brillante. Une branche est un
   * métier qu'on pousse d'un cran — c'est le seul son du produit qui a du
   * marteau dedans.
   */
  branchTier() {
    souffle({ duree: 0.09, gain: 0.13, coupure: 5200, q: 2.4 })
    note({ freq: MI4, duree: 0.28, gain: 0.16, type: 'square', attaque: 0.004 })
    note({ freq: LA4, duree: 0.5, gain: 0.13, type: 'triangle', retard: 0.085, vers: LA4 * 1.005 })
    note({ freq: MI5, duree: 0.9, gain: 0.05, type: 'sine', retard: 0.1, attaque: 0.06 })
  },

  /** Une relique (§12.8). Elle ne se gagne pas, elle se **trouve**.
   *
   * Première version : deux sinus à attaque lente. Sans attaque, un son n'a pas
   * de point de départ — l'oreille ne sait pas quand il commence, donc il ne
   * marque rien. C'était mou, et « mou » est exactement ce qu'une relique ne
   * doit pas être.
   *
   * Deuxième version, celle-ci : **une cloche frappée**. Une cloche n'est pas
   * un accord — ses partiels ne sont pas des multiples entiers de la
   * fondamentale, et c'est cette inharmonicité qui fait qu'on la reconnaît
   * entre mille. Les rapports employés ici (2,76 · 5,40 · 8,93) sont ceux d'une
   * cloche de bronze réelle, et chaque partiel s'éteint d'autant plus vite
   * qu'il est aigu, comme dans le métal.
   *
   * Frappée doucement, mais frappée : il y a un instant zéro. Le sub qui suit
   * lui donne son poids, et la quinte qui monte à la toute fin dit qu'on a
   * trouvé quelque chose plutôt que reçu quelque chose.
   */
  relic() {
    const fondamentale = 146.83                    // ré grave, dans la pentatonique
    const partiels = [
      { rapport: 1, duree: 2.6, gain: 0.2 },
      { rapport: 2.76, duree: 1.9, gain: 0.1 },
      { rapport: 5.4, duree: 1.1, gain: 0.055 },
      { rapport: 8.93, duree: 0.7, gain: 0.03 },
    ]
    partiels.forEach(({ rapport, duree, gain }) => {
      note({
        freq: fondamentale * rapport,
        duree,
        gain,
        type: 'sine',
        // Attaque très courte : c'est le coup de marteau. Sans lui, la cloche
        // n'est plus une cloche, c'est une nappe.
        attaque: 0.004,
      })
    })
    // Le coup lui-même : un souffle métallique de 40 ms, l'attaque du bronze.
    souffle({ duree: 0.05, gain: 0.09, coupure: 3800, q: 1.8 })
    // Le poids en dessous.
    note({ freq: fondamentale / 2, duree: 2.2, gain: 0.13, type: 'sine', attaque: 0.02 })
    // Et la quinte qui monte à la fin : quelque chose se réveille.
    note({
      freq: LA3,
      duree: 1.6,
      gain: 0.05,
      type: 'triangle',
      attaque: 0.5,
      retard: 0.55,
      vers: MI4,
    })
  },

  /** Le retournement d'une **rare** : le souffle sec d'une carte qu'on tourne. */
  cardFlip() {
    souffle({ duree: 0.17, gain: 0.09, coupure: 3200, vers: 800, q: 1.1 })
  },

  /** Une **commune** se pose, elle ne s'ouvre pas : un contact mat, très court. */
  cardSlide() {
    souffle({ duree: 0.07, gain: 0.07, coupure: 900, q: 1.6 })
  },

  /** Une **épique** se fend : une déchirure, deux fois plus longue que le flip. */
  cardSplit() {
    souffle({ duree: 0.34, gain: 0.12, coupure: 700, vers: 4800, q: 0.8 })
    note({ freq: 140, duree: 0.3, gain: 0.1, type: 'sawtooth', vers: 320 })
  },

  /** Une **légendaire** se brise : trois éclats qui partent, et un sub qui tombe. */
  cardShatter() {
    ;[0, 0.045, 0.11].forEach((retard, i) => {
      souffle({
        duree: 0.22 - i * 0.05,
        gain: 0.13 - i * 0.03,
        coupure: 6400 - i * 1500,
        q: 3.2,
        retard,
      })
    })
    note({ freq: 120, duree: 0.8, gain: 0.22, type: 'sine', vers: 42 })
  },

  /** La montée avant une révélation : le grondement qui rend l'attente lisible.
   *
   * Deux couches qui montent ensemble — un sub qui glisse d'une octave et un
   * souffle dont le filtre s'ouvre. L'attaque occupe les sept dixièmes de la
   * durée : l'oreille entend une **arrivée**, pas un son posé qui dure.
   *
   * Utilisée par l'ascension et par la carte légendaire, à dessein : c'est le
   * même geste, donc le même son. Deux grondements différents pour la même
   * fonction se seraient entendus comme un défaut.
   */
  charge(duree = 0.85) {
    note({ freq: 62, duree, gain: 0.13, type: 'sawtooth', vers: 168, attaque: duree * 0.72 })
    souffle({ duree, gain: 0.055, coupure: 260, vers: 3000, q: 0.4 })
    // Trois battements qui s'accélèrent, calés sur la pulsation visuelle : ce
    // sont eux qui font entendre que quelque chose se prépare.
    ;[0.12, 0.42, 0.68].forEach((part, i) => {
      note({
        freq: 180 + i * 40,
        duree: 0.09,
        gain: 0.05 + i * 0.02,
        type: 'triangle',
        retard: duree * part,
      })
    })
  },

  /** La charge d'une légendaire. Alias historique de `charge`. */
  cardCharge(duree = 0.85) {
    note({ freq: 70, duree, gain: 0.11, type: 'sawtooth', vers: 150, attaque: duree * 0.7 })
    souffle({ duree, gain: 0.05, coupure: 300, vers: 2600, q: 0.4 })
  },

  /** La révélation, graduée par rareté — c'est ici que la hiérarchie s'entend.
   *
   * Le nombre de notes, leur registre et la longueur de la queue montent avec
   * la rareté. Une commune tient en un huitième de seconde ; une légendaire
   * dure une seconde et demie et descend dans les graves, seul endroit du son
   * du produit où l'on va chercher le sub. */
  cardReveal(rarete: string) {
    switch (rarete) {
      case 'legendaire':
        note({ freq: 55, duree: 1.4, gain: 0.26, type: 'sine' })
        accord([LA4, DO5, MI5, LA5], { duree: 1.5, gain: 0.13, type: 'triangle', ecart: 0.085 })
        souffle({ duree: 1.2, gain: 0.07, coupure: 600, vers: 7000, retard: 0.04 })
        note({ freq: LA5 * 2, duree: 1.6, gain: 0.045, type: 'sine', retard: 0.3, attaque: 0.25 })
        break
      case 'epique':
        note({ freq: 110, duree: 0.6, gain: 0.16, type: 'sine' })
        accord([MI4, LA4, DO5], { duree: 0.85, gain: 0.13, type: 'triangle', ecart: 0.06 })
        souffle({ duree: 0.6, gain: 0.05, coupure: 1200, vers: 5000 })
        break
      case 'rare':
        accord([LA4, MI5], { duree: 0.5, gain: 0.12, type: 'triangle', ecart: 0.05 })
        break
      default:
        // Commune : un seul coup mat. Le §12.6 veut qu'aucun tirage ne soit
        // vide, pas que chacun soit une fanfare.
        note({ freq: RE4, duree: 0.16, gain: 0.1, type: 'sine' })
        break
    }
  },
}

export type Sfx = typeof sfx
