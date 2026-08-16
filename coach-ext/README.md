# coach-ext — la sonde web

ActivityWatch ne voit souvent que « chrome.exe ». Cette extension voit le
domaine, et c'est elle qui permet de distinguer réellement une catégorie d'une
autre sur le web (SPEC §9.1).

## Ce qu'elle mesure

Le temps passé sur l'onglet **actif d'une fenêtre ayant le focus**, machine non
inactive. Un onglet ouvert en arrière-plan pendant six heures ne compte pas :
ce serait mesurer des onglets, pas un usage.

Toutes les 5 minutes, elle envoie des couples `(catégorie, minutes)`.

## Ce qui ne sort jamais

- **Aucune URL, aucun domaine, aucun titre de page.** La table qui relie un
  domaine à une catégorie vit dans le stockage local du navigateur. Le serveur
  reçoit « reseaux : 14 » et n'apprend jamais lequel.
- La chaîne de requête et le fragment sont écartés avant même la
  catégorisation : `x.com/page?token=SECRET` devient `x.com/page`.
- Ce qui tombe dans `autre` n'est pas envoyé du tout.

Et comme partout ailleurs : **une détection marque, une absence de détection ne
certifie rien** (SPEC §11.10). L'extension ne déclare jamais une journée tenue.

## Installation

1. Émets un jeton de sonde — il ne peut **que** poster des signaux, il ne donne
   accès à rien d'autre :

   ```bash
   cd coach-api
   .venv/Scripts/python manage.py probetoken --issue ext --name "Chrome"
   ```

   Copie-le : seule son empreinte est stockée, il ne sera plus jamais affiché.

2. **Firefox** — c'est la cible par défaut, `manifest.json` est déjà le sien.

   Va sur `about:debugging` → **Ce Firefox** → **Charger un module temporaire**,
   et choisis le fichier `coach-ext/manifest.json`.

   **Chrome ou Edge** : il faut d'abord échanger les manifestes, Firefox et
   Chrome n'acceptant pas la même forme de script de fond :

   ```bash
   cd coach-ext
   mv manifest.json manifest.firefox.json && mv manifest.chrome.json manifest.json
   ```

   Puis `chrome://extensions` → **Mode développeur** → **Charger l'extension non
   empaquetée** → choisis le dossier `coach-ext/`.

3. Clique sur l'icône de l'extension. Colle l'adresse de l'API
   (`http://127.0.0.1:8000`) et le jeton de `token.local.txt`.

4. Dans le champ **Catégories**, remplace le contenu par celui de
   `rules.local.json` — ce fichier est ignoré par git et contient les listes
   complètes, y compris celles qui ne regardent personne d'autre. Puis
   **Enregistrer**, et supprime `token.local.txt`.

5. Le premier envoi arrive au bout de 5 minutes. La date du dernier envoi
   s'affiche dans le même panneau.

> **Si rien n'arrive au bout de 10 minutes sous Firefox**, va dans `about:addons`
> → l'extension → **Permissions**, et vérifie que l'accès à `127.0.0.1:8000` est
> accordé. Firefox traite les permissions d'hôte du manifeste V3 comme
> facultatives : elles peuvent demander une validation explicite, là où Chrome
> les accorde d'office.

## Régler les catégories

Le champ JSON du panneau contient la table. `reddit` attrape `old.reddit.com`,
`youtube.com/shorts` attrape les Shorts **sans** attraper les vidéos longues —
c'est voulu : le §17 interdit de bloquer ce qui n'est pas du scroll passif, et
la mesure suit la même ligne.

La catégorie `adulte` est **vide par défaut**, volontairement. Cette liste te
regarde, et elle ne quitte jamais ce navigateur. Remplis-la toi-même, ou
laisse-la vide et garde cette garde en déclaration manuelle.

## Limites connues

- **Un seul navigateur.** Une extension chargée dans Chrome ne voit ni Firefox,
  ni un autre profil, ni la navigation privée. C'est exactement pourquoi le
  silence d'une sonde ne prouve rien.
- **Non empaquetée.** Chrome affichera un avertissement au démarrage tant que
  l'extension est chargée en mode développeur. Sous Firefox, elle est retirée
  à chaque fermeture du navigateur.
- Le blocage des Shorts et du feed d'accueil (§9.1) n'est **pas** dans cette
  version : il dépend de l'état « armé » côté serveur, et un blocage permanent
  serait contraire au §17. Il viendra avec le sas de détente.
