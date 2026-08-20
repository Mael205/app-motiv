import { useState } from 'react'
import { api } from '../api'
import './Export.css'

/** L'export complet (J6, §16).
 *
 * **Pourquoi un bouton et pas une commande.** Une sauvegarde qui demande
 * d'ouvrir un terminal ne se fait pas. Le 19 août 2026, un projet de cent vingt
 * étapes a été effacé sans sauvegarde et n'était pas récupérable ; ce bouton ne
 * remplace pas une copie de la base, mais il met le travail hors de portée d'un
 * accident en un clic.
 *
 * Le fichier se fabrique côté client à partir du JSON reçu, plutôt que de
 * suivre l'en-tête de téléchargement du serveur : la requête part avec le jeton
 * d'authentification, ce qu'un lien ordinaire ne sait pas faire.
 */
export function Export() {
  const [etat, setEtat] = useState<'pret' | 'en_cours' | 'rate'>('pret')

  async function exporter() {
    setEtat('en_cours')
    try {
      const tout = await api.exportTout()
      const fichier = new Blob([JSON.stringify(tout, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(fichier)
      const lien = document.createElement('a')
      lien.href = url
      // La date dans le nom : deux exports sans date dans un dossier de
      // téléchargements sont deux fichiers qu'on n'ose plus effacer.
      lien.download = `coach-${new Date().toISOString().slice(0, 10)}.json`
      lien.click()
      URL.revokeObjectURL(url)
      setEtat('pret')
    } catch {
      setEtat('rate')
    }
  }

  return (
    <div className="export">
      <p className="export__texte">
        Tout ce qui a été fait — sessions, notes, amorces, étapes, saisons — dans un fichier JSON
        lisible sans le coach. Aucun jeton ni webhook n'y figure : il se copie et s'envoie sans
        risque.
      </p>
      <button className="ghost" onClick={exporter} disabled={etat === 'en_cours'}>
        {etat === 'en_cours' ? 'Un instant…' : 'Exporter mes données'}
      </button>
      {etat === 'rate' && <p className="export__rate">Le serveur n'a pas répondu. Rien n'a été écrit.</p>}
    </div>
  )
}
