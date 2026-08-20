/* Les règles qui décident si une mesure passe ou échoue.
 *
 * Elles vivent ici, et non dans les trois scripts, pour une seule raison : un
 * outil qui ouvre un navigateur ne se teste pas. Tant que la règle était noyée
 * dans `audit.cjs`, la seule façon de savoir si elle attrapait un défaut était
 * d'en fabriquer un dans l'app. Personne ne le fait, donc personne ne savait.
 *
 * Sorties ici, ce sont des fonctions pures sur des tableaux : le cas qui échoue
 * se teste aussi facilement que le cas qui passe, et c'est le seul des deux qui
 * compte vraiment.
 */

/** Audit visuel. `animations` est volontairement absent : il liste ce qui
 *  existe, pas ce qui est cassé. Les erreurs de console comptent comme un
 *  défaut — une exception au chargement casse l'écran sans le déformer. */
const FAMILLES = ['overflow', 'overlap', 'invisible', 'layout']

function verdictAudit(rapport) {
  const compte = {}
  let total = 0

  for (const ligne of rapport || []) {
    for (const f of [...FAMILLES, 'console']) {
      const n = (ligne[f] || []).length
      if (n) {
        compte[f] = (compte[f] || 0) + n
        total += n
      }
    }
  }

  return {
    ok: total === 0,
    total,
    compte,
    message:
      total === 0
        ? `AUDIT OK — ${(rapport || []).length} combinaisons, aucun defaut.`
        : `AUDIT ECHOUE — ${total} defaut(s) : ${JSON.stringify(compte)}`,
  }
}

/** Ligne de flottaison : le bouton de démarrage doit être visible à chaque
 *  taille. Un `visible: false` est le défaut que l'outil existe pour attraper. */
function verdictFold(resultats) {
  const rates = (resultats || []).filter((r) => !r.visible)

  return {
    ok: rates.length === 0,
    rates,
    message:
      rates.length === 0
        ? `FOLD OK — visible sur les ${(resultats || []).length} tailles.`
        : `FOLD ECHOUE — le bouton passe sous la ligne sur : ${rates
            .map((r) => `${r.taille} (${r.marge}px)`)
            .join(', ')}`,
  }
}

/** Son. Deux défauts, dont aucun ne s'entend sur la machine du jour : la
 *  coupure qui laisse passer des voix, et une séquence muette. */
function verdictSon(resultats) {
  const griefs = []
  const r = resultats || {}

  if (r['coupé'] > 0) griefs.push(`la coupure laisse passer ${r['coupé']} voix`)
  for (const [nom, n] of Object.entries(r)) {
    if (nom !== 'coupé' && !n) griefs.push(`« ${nom} » est muet`)
  }

  return {
    ok: griefs.length === 0,
    griefs,
    message:
      griefs.length === 0
        ? 'SON OK — coupure nette, aucune sequence muette.'
        : `SON ECHOUE — ${griefs.join(' ; ')}`,
  }
}

/** Applique un verdict : l'imprime, et pose le code de sortie. */
function conclure(verdict) {
  console.error(`\n${verdict.message}`)
  if (!verdict.ok) process.exitCode = 1
  return verdict.ok
}

module.exports = { verdictAudit, verdictFold, verdictSon, conclure }
