import { useEffect, useState } from 'react'
import { api } from '../api'
import './Partage.css'

/** Ce qui arrive par le menu « Partager » d'Android (SPEC §11.7).
 *
 * Le dernier morceau du canal entrant. Le lien signé couvrait déjà la capture
 * sans ouvrir l'app, mais il fallait l'avoir épinglé et penser à l'ouvrir. Une
 * cible de partage enlève ce dernier détour : la vidéo qu'on regarde, l'article
 * qu'on lit, le message qu'on reçoit se jettent au frigo depuis l'app où on est
 * déjà, en deux tapes.
 *
 * **Ça ne crée jamais un projet, seulement une idée au frigo.** Le §4 fait d'un
 * projet une décision qui coûte un slot ; en fabriquer un depuis un partage
 * reviendrait à ouvrir un chantier par accident. Le frigo est exactement le bon
 * niveau d'engagement : ça attend dimanche et ça ne prend rien.
 *
 * L'URL est nettoyée aussitôt lue. Sans ça, un rafraîchissement rejetterait la
 * même idée au frigo, et l'historique du navigateur garderait un partage qu'on
 * a déjà traité.
 */
export function Partage() {
  const [texte, setTexte] = useState<string | null>(null)
  const [etat, setEtat] = useState<'lu' | 'garde' | 'rate'>('lu')

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const morceaux = [params.get('titre'), params.get('texte'), params.get('adresse')]
      .map((m) => (m || '').trim())
      .filter(Boolean)
    if (morceaux.length === 0) return

    // Dédoublonné : Android envoie souvent le titre *et* l'adresse, et certaines
    // apps mettent l'adresse dans le texte. Trois fois la même ligne dans le
    // frigo se lit comme un bug.
    const partage = [...new Set(morceaux)].join(' — ')
    setTexte(partage)
    window.history.replaceState({}, '', window.location.pathname)

    api
      .addIdea(partage)
      .then(() => setEtat('garde'))
      .catch(() => setEtat('rate'))
  }, [])

  if (!texte) return null

  return (
    <div className="partage" role="status">
      <span className="label">
        {etat === 'garde' ? 'Au frigo' : etat === 'rate' ? 'Non enregistré' : 'Reçu'}
      </span>
      <p className="partage__texte">{texte}</p>
      {etat === 'rate' && (
        <p className="partage__rate">
          Le serveur n'a pas répondu. Recopie-le si ça compte — rien n'a été gardé.
        </p>
      )}
      <button className="ghost partage__fermer" onClick={() => setTexte(null)}>
        Fermer
      </button>
    </div>
  )
}
