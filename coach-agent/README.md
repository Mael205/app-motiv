# coach-agent — la sonde PC

Elle regarde ce qui se passe sur la machine et envoie au coach **des catégories
et des durées**. Jamais un titre de fenêtre, jamais une URL, jamais une capture.

La correspondance entre un domaine et sa catégorie vit dans `categories.toml`,
sur cette machine, dans un fichier que tu es seul à éditer. Le serveur reçoit
« reseaux : 14 minutes » et n'apprend jamais lequel.

## Ce qu'elle fait aujourd'hui

- **Ouvre l'environnement d'un projet** quand une session démarre : dossiers,
  éditeur, onglets. C'est le gain du §8.1 — ne plus perdre dix minutes à se
  remettre en place.
- **Détecte les sessions fantômes** : une session lancée puis oubliée est
  signalée au serveur, qui la clôture au dernier instant d'activité prouvé.
- **Affiche les notifications en natif** sur Windows, sans dépendance à
  installer.
- Lit **ActivityWatch** sur `localhost:5600` — fenêtre active, inactivité,
  multi-écran, veille. L'agent n'implémente pas son propre suivi : ActivityWatch
  le fait déjà bien (SPEC §8.4).
- Lit **AdGuard Home**, s'il est configuré — le seul point qui voit *tous* les
  appareils du réseau, téléphone compris.
- Catégorise localement, agrège, poste sur `/api/signals`.
- Les gardes dont la catégorie a été détectée sont **marquées automatiquement**.

## Ce qu'elle ne fait pas, et ne fera pas

- Aucune capture d'écran, aucun keylogging (SPEC §17).
- Aucune URL, aucun titre de page ne quitte la machine (SPEC §11.10).
- **Elle ne déclare jamais une journée tenue.** Une détection marque ; une
  absence de détection ne prouve rien. Navigation privée, autre appareil,
  téléphone : la sonde ne voit qu'une partie du monde, et le système refuse de
  conclure à partir de son silence.

## Installation

1. Installe [ActivityWatch](https://activitywatch.net/). Sans lui, l'agent
   tourne mais ne mesure rien, et il le dit.

2. Émets un jeton de sonde. Ce n'est pas un jeton de connexion : il ne donne
   accès qu'à `/api/signals`, il n'expire pas, et il est révocable à tout
   moment par `--revoke`.

   ```bash
   cd ../coach-api
   .venv/Scripts/python manage.py probetoken --issue agent --name "PC fixe"
   ```

   Copie-le : seule son empreinte est stockée, il ne sera plus jamais affiché.

3. Crée `config.local.toml` à côté de `agent.py` — il est ignoré par git et
   n'est **jamais** modifiable via l'API (SPEC §8) :

   ```toml
   api_url = "http://127.0.0.1:8000"
   token = "<le jeton affiché>"
   interval_seconds = 600
   ```

   La section `[adguard]` est facultative, voir plus bas.

4. Vérifie :

   ```bash
   python agent.py --once
   ```

5. Laisse tourner :

   ```bash
   python agent.py
   ```

## Profils de lancement

Copie le modèle, puis remplis-le avec tes chemins :

```bash
cd coach-agent
cp profiles.example.toml profiles.local.toml
```

Le nom de section doit être **exactement** le nom du projet dans le coach —
attention aux tirets longs des noms créés par le seed.

### Pourquoi ce fichier et pas le serveur

Le §8 pose une règle non négociable : *le serveur ne peut jamais faire exécuter
une commande arbitraire*. Le serveur envoie donc uniquement le **nom** du
projet, et l'agent le cherche dans ce fichier-ci. Un projet absent ne lance
rien.

La conséquence vaut d'être dite : même si le serveur était compromis, ou si une
réponse de modèle était détournée, le pire cas resterait l'ouverture d'un
programme que tu as toi-même écrit dans ce fichier. C'est pour ça qu'il n'est
pas modifiable via l'API, et qu'il n'est pas dans git.

## Sessions fantômes

Une session lancée puis oubliée fausse tout : elle compterait sa durée prévue,
c'est-à-dire du temps non travaillé, ce que le §17 interdit.

L'agent **rapporte ce qu'il a mesuré**, le serveur **décide**. Deux conditions
sont exigées, et il faut les deux : un dépassement d'au moins 15 minutes au-delà
de la durée prévue, et aucune activité depuis 15 minutes. La session est alors
close au dernier instant d'activité prouvé — jamais à l'instant courant, puisque
le temps entre les deux n'a pas été travaillé.

**Sans mesure d'activité, rien n'est clôturé.** C'est la même asymétrie qu'au
§11.10 : fermer une session sur une absence de données effacerait du travail
réel, et cette faute-là est invisible.

## AdGuard Home — couvrir le téléphone sans app Android

L'extension ne voit qu'un navigateur, ActivityWatch ne voit que ce PC. Un
résolveur DNS voit tout ce qui passe par le réseau, y compris la navigation
privée et le téléphone.

**Auto-hébergé, et c'est tout l'intérêt.** Un résolveur tiers recevrait chaque
domaine que tu résous sur chaque appareil — exactement l'inverse de ce que ce
système protège partout ailleurs. Ici, AdGuard tourne chez toi, l'agent lit les
domaines en local, les traduit en catégories avec `categories.toml`, et **seules
les catégories sortent**.

### Installation

1. Installe [AdGuard Home](https://adguard.com/adguard-home.html) sur ce PC ou
   sur un Raspberry Pi, et pointe le DNS de ta box dessus.
2. Ajoute la section à `config.local.toml` :

   ```toml
   [adguard]
   url = "http://127.0.0.1:3000"
   username = "admin"
   password = "…"
   ```

3. `python agent.py --once` affichera les catégories vues sur la fenêtre.

### Ce que ça mesure, et ce que ça ne mesure pas

**Une requête DNS est un événement, pas une durée.** L'agent ne prétend donc pas
mesurer un temps d'usage : il regroupe les requêtes d'une même catégorie en
*rafales* et rend l'amplitude de chaque rafale. C'est une estimation d'activité,
assumée comme telle.

Conséquence voulue : une requête isolée produit une rafale d'une minute, sous le
seuil de marquage du serveur. Un tracker embarqué ou un préchargement de
navigateur ne marquera jamais une journée à lui seul.

**Le téléphone n'est couvert qu'en Wi-Fi à la maison.** En 4G, il ne passe plus
par ton résolveur. Pour le couvrir dehors il faudrait un tunnel WireGuard vers
chez toi — une autre soirée, et pas indispensable pour commencer.

## Régler la catégorisation

`categories.toml` contient des fragments cherchés dans le nom de l'application
ou du domaine. `reddit` attrape `old.reddit.com`.

La catégorie `adulte` est **vide par défaut**, volontairement : cette liste te
regarde, et elle ne quitte jamais cette machine. Remplis-la toi-même.

Une application non reconnue tombe dans `autre`, qui n'est pas envoyée du tout.


## Tests

```bash
coach-api/.venv/Scripts/python -m pytest coach-agent
```
