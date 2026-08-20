import './EtatCharge.css'

/** Les deux états qu'un écran traverse avant d'avoir ses données.
 *
 * Ils vivaient dans chaque écran, écrits à chaque fois un peu différemment :
 * l'onglet Personnage attrapait ses erreurs et affichait un paragraphe gris,
 * Projets et Journal n'en attrapaient aucune et restaient sur « Chargement… »
 * **indéfiniment** — mesuré en coupant l'API : aucun message, aucun bouton,
 * aucune sortie. Trois écrans, trois comportements face à la même panne.
 *
 * Le bouton « Réessayer » est ce qui distingue les deux composants. Une erreur
 * sans moyen de la lever oblige à recharger l'application entière, et le §11.1
 * n'a pas prévu que la première action d'une soirée soit F5.
 */

export function EnCharge({ quoi = 'Chargement…' }: { quoi?: string }) {
  return (
    <p className="etat-charge" role="status">
      {quoi}
    </p>
  )
}

export function EnErreur({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="etat-erreur" role="alert">
      <p className="etat-erreur__texte">{message}</p>
      {onRetry && (
        <button className="ghost" onClick={onRetry}>
          Réessayer
        </button>
      )}
    </div>
  )
}
