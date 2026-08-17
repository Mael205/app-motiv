# coach-ext — la sonde web et le blocage YouTube

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

## Ce qu'elle bloque, quand elle est armée

L'extension demande son état à `/api/agent/state` — c'est le serveur qui décide,
à la fin du sas de détente, à l'heure du gardien, ou plus tôt si une sanction du
§14 avance le palier. L'extension n'a aucune de ces règles et n'en a pas besoin.

Armée, elle fait deux choses sur YouTube, et rien ailleurs :

- **`/shorts/<id>` renvoie vers `/watch?v=<id>`.** La vidéo reste accessible ;
  c'est le défilement qui disparaît. Le lien vers Shorts est aussi retiré du
  rail de gauche, sinon on y retourne d'un clic depuis la page d'arrivée.
- **Le feed d'accueil est masqué**, remplacé par une ligne factuelle.

Ce qui n'est **jamais** touché : la recherche, les vidéos longues, les
abonnements, et tout le reste du web. Le §17 interdit de bloquer ce qui n'est
pas du scroll passif — un blocage qui empêcherait de chercher une réponse
technique à 21h punirait le travail, et serait désinstallé dans la semaine.

**La porte de sortie**, exigée par le §8.5 : le panneau de l'extension a un
bouton « Lever le blocage ». Deux clics, avec soixante secondes entre les deux,
et le blocage se lève pour deux heures — assez pour une soirée, et demain repart
armé. La friction suffit, l'emprisonnement non. La levée est locale au
navigateur : le serveur, lui, reste armé, et le gardien ne change pas d'avis
parce qu'on a fermé un masque de feed.

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
- **Le blocage ne couvre que YouTube.** TikTok, X, Instagram et Reddit sont des
  domaines pleins : le §8.5 les confie au fichier hosts, donc à l'agent. Une
  extension ne les fermerait que dans le navigateur où elle est installée.
- Si le serveur est injoignable, **rien n'est bloqué**. Un blocage qui survit à
  la panne du système qui l'a décidé est un blocage que plus personne ne peut
  lever.
