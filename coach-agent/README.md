# coach-agent — la sonde PC

Elle regarde ce qui se passe sur la machine et envoie au coach **des catégories
et des durées**. Jamais un titre de fenêtre, jamais une URL, jamais une capture.

La correspondance entre un domaine et sa catégorie vit dans `categories.toml`,
sur cette machine, dans un fichier que tu es seul à éditer. Le serveur reçoit
« reseaux : 14 minutes » et n'apprend jamais lequel.

## Ce qu'elle fait aujourd'hui

- Lit **ActivityWatch** sur `localhost:5600` — fenêtre active, inactivité,
  multi-écran, veille. L'agent n'implémente pas son propre suivi : ActivityWatch
  le fait déjà bien (SPEC §8.4).
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

4. Vérifie :

   ```bash
   python agent.py --once
   ```

5. Laisse tourner :

   ```bash
   python agent.py
   ```

## Régler la catégorisation

`categories.toml` contient des fragments cherchés dans le nom de l'application
ou du domaine. `reddit` attrape `old.reddit.com`.

La catégorie `adulte` est **vide par défaut**, volontairement : cette liste te
regarde, et elle ne quitte jamais cette machine. Remplis-la toi-même.

Une application non reconnue tombe dans `autre`, qui n'est pas envoyée du tout.
