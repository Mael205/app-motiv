import { StrictMode, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Ascension } from '../components/Ascension'
import { SessionEntry } from '../components/SessionEntry'
import { LootReveal } from '../components/LootReveal'
import { MomentumEmber } from '../components/MomentumEmber'
import { SkillTree } from '../components/SkillTree'
import type { LootCardDrawn, SessionResult } from '../types'
import '../styles/theme.css'
import '../App.css'

/** Banc d'essai des sequences du §7. **Dev seulement.**
 *
 * Existe parce qu'une sequence de passage de niveau ne se regle pas en la
 * declenchant pour de vrai : il faudrait travailler une heure entre deux essais.
 * Ici chaque effet se rejoue d'un clic.
 *
 * Servi sur /juice.html par le serveur de dev. Vite ne construit que index.html
 * par defaut, donc cette page ne part jamais en production.
 */

const CARDS: LootCardDrawn[] = [
  { key: 'theme_eclipse', label: 'Éclipse', rarity: 'legendaire', rarity_label: 'Légendaire',
    color: '#E8A33D', kind: 'theme', payload: '#E85F9F', duplicate: false, shards: 0,
    reason: 'niveau', reason_label: 'Passage de niveau' },
  { key: 'emb_sceau', label: 'Sceau', rarity: 'epique', rarity_label: 'Épique',
    color: '#8B6FE8', kind: 'emblem', payload: '❖', duplicate: false, shards: 0,
    reason: 'semaine', reason_label: 'Semaine tenue' },
  { key: 'emb_rune', label: 'Rune', rarity: 'rare', rarity_label: 'Rare',
    color: '#5FA8DE', kind: 'emblem', payload: 'ᚦ', duplicate: true, shards: 15,
    reason: 'semaine', reason_label: 'Semaine tenue' },
  { key: 'theme_braise', label: 'Braise', rarity: 'commun', rarity_label: 'Commun',
    color: '#9A8CAE', kind: 'theme', payload: '#E8843D', duplicate: false, shards: 0,
    reason: 'semaine', reason_label: 'Semaine tenue' },
]

const RESULT: SessionResult = {
  session_id: 1, minutes: 50, xp: 118,
  objectif: 50, objectif_tenu: true, depassement: 0, extensions: 0,
  breakdown: { base: 50, duration_premium: 14, first_of_day: 20, punctual: 10, streak_multiplier: 1.3,
    momentum_multiplier: 1.25, degressivity: 1, base_total: 118, crit: false,
    crit_multiplier: 1, crit_bonus: 0, total: 118, notes: [] },
  boss_damage: 62,
  achievements: [{ key: 'increvable', label: 'Increvable', description: '28 jours sans bouclier.' }],
  level_before: 11, level_after: 12, levelled_up: true, total_xp: 1218, rank: 'B',
  progression: { level: 12, into_level: 118, needed: 1200, ratio: 0.1 },
  momentum: { level: 0.92, percent: 92, multiplier: 1.23, label: 'incandescente',
    detail: 'Tu es à la chaleur maximale.', days_worked: 6, cooling: false,
    days: [true, true, true, false, true, true, true] },
  branch_tier: { branch: 'moteur_de_jeu', label: 'Moteur de jeu', color: '#8B6FE8',
    tier: 3, title: 'Machiniste', emblem: '◆', hours: 50 },
  boss_killed: null,
  boss_phase: null,
  crit: null,
  cards: [CARDS[0]],
  relics: [{ key: 'coeur_increvable', label: 'Cœur increvable',
    lore: 'Vingt-huit jours sans céder un bouclier. Le corps se souvient.',
    emblem: '◈', effect: 'bouclier_supp', value: 1 }],
}

const BRANCHES = [
  { key: 'moteur_de_jeu', label: 'Moteur de jeu', color: '#8B6FE8', minutes: 3060, hours: 51,
    tier: 3, title: 'Machiniste', emblem: '◆', next_hours: 100, progress: 0.02, maxed: false },
  { key: 'cyber', label: 'Reverse & cyber', color: '#4FC4B4', minutes: 1580, hours: 26.3,
    tier: 2, title: 'Fouineur', emblem: '◇', next_hours: 50, progress: 0.05, maxed: false },
  { key: 'corps', label: 'Corps', color: '#7ED08C', minutes: 640, hours: 10.7,
    tier: 1, title: 'Debout', emblem: '◦', next_hours: 25, progress: 0.05, maxed: false },
  { key: 'data_rl', label: 'Data & RL', color: '#5FA8DE', minutes: 0, hours: 0,
    tier: 0, title: '', emblem: '', next_hours: 10, progress: 0, maxed: false },
]

function Bench() {
  const [scene, setScene] = useState<string>('')
  const [card, setCard] = useState(0)

  return (
    <main className="shell" style={{ maxWidth: 760, paddingTop: 30 }}>
      <h1 className="display" style={{ fontSize: 34, color: 'var(--accent)' }}>Banc d'essai — juice</h1>
      <p className="muted" style={{ fontSize: 13 }}>
        Dev seulement. Chaque bouton rejoue une séquence du §7.
      </p>

      <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
        <button className="ghost" onClick={() => setScene('asc')}>Ascension complète</button>
        <button className="ghost" onClick={() => setScene('boss')}>Mort du boss</button>
        <button className="ghost" onClick={() => setScene('phase')}>Phase de boss</button>
        <button className="ghost" onClick={() => { setScene('entry'); setTimeout(() => setScene(''), 2600) }}>
          Entrée en session
        </button>
        {CARDS.map((c, i) => (
          <button key={c.key} className="ghost" onClick={() => { setCard(i); setScene('loot') }}>
            Carte {c.rarity_label}
          </button>
        ))}
      </div>

      <MomentumEmber momentum={RESULT.momentum} />

      <section className="panel">
        <SkillTree branches={BRANCHES} tiers={[10, 25, 50, 100, 200, 400]} />
      </section>

      {scene === 'asc' && <Ascension result={RESULT} onDone={() => setScene('')} />}

      {scene === 'boss' && (
        <Ascension
          result={{
            ...RESULT,
            levelled_up: false,
            branch_tier: null,
            relics: [],
            cards: [],
            boss_killed: { name: 'La Scroll-Hydre', max_hp: 4200, season: 'Purgatoire', days_left: 6 },
          }}
          onDone={() => setScene('')}
        />
      )}

      {/* La bascule de phase (§12.4) : elle se règle ici pour la même raison que
          le reste — attendre d'avoir entamé un vrai boss de moitié prendrait
          deux semaines. */}
      {scene === 'phase' && (
        <Ascension
          result={{
            ...RESULT,
            levelled_up: false,
            branch_tier: null,
            relics: [],
            cards: [],
            boss_phase: {
              index: 2,
              name: 'La Scroll-Hydre décapitée',
              previous_name: 'La Scroll-Hydre',
              line: 'Les têtes repoussent moins vite qu\'avant.',
              intensity: 1.35,
              final: false,
            },
          }}
          onDone={() => setScene('')}
        />
      )}

      {scene === 'entry' && (
        <SessionEntry project="Evolve — prototype 4v1" minutes={50} emblem="◈" color="#8B6FE8" />
      )}

      {scene === 'loot' && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 80, display: 'grid',
          placeItems: 'center', background: 'rgba(8,5,12,.93)', padding: 24 }}>
          <LootReveal card={CARDS[card]} onDone={() => setScene('')} />
        </div>
      )}
    </main>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Bench />
  </StrictMode>,
)
