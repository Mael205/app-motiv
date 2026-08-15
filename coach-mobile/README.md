# coach-mobile — la sonde Android

C'est l'angle mort du dispositif. ActivityWatch ne voit que le PC, l'extension
ne voit qu'un navigateur, et une bonne partie du scroll se passe sur le
téléphone. Tant que cette sonde n'existe pas, l'automatisation est à moitié
aveugle — et c'est précisément pour ça que le §11.10 refuse de conclure quoi
que ce soit du silence des sondes.

Deux chemins, dans l'ordre où ils deviennent utiles.

---

## Chemin 1 — MacroDroid ou Tasker (utilisable ce soir)

Aucune compilation, aucun sideload de code maison. Une app d'automatisation
Android déclenche une requête HTTP quand tu ouvres une application surveillée.

**Ce que ça donne :** un **marquage** honnête. Tu as ouvert l'app, la journée
est marquée. C'est exactement ce dont une garde a besoin (§11.10).

**Ce que ça ne donne pas :** une mesure. Les minutes envoyées sont nominales,
pas réelles. Le rapport de fuite de temps du §13.2 ne doit pas s'appuyer
dessus — le chemin 2 existe pour ça.

### La recette

1. Émets un jeton, côté PC :

   ```bash
   cd coach-api
   .venv/Scripts/python manage.py probetoken --issue mobile --name "Pixel"
   ```

2. Dans **MacroDroid** (gratuit) ou **Tasker**, crée une macro :

   - **Déclencheur** — « Application lancée », et coche les applications d'une
     même catégorie. Une macro par catégorie.
   - **Contrainte** — ajoute une limite de déclenchement, par exemple une fois
     toutes les 30 minutes. Sans elle, ouvrir l'app dix fois enverrait dix
     signaux.
   - **Action** — « Requête HTTP » :

     ```
     Méthode  POST
     URL      http://<adresse-de-ton-api>/api/signals
     En-tête  X-Probe-Token: <ton jeton>
     En-tête  Content-Type: application/json
     Corps    {"source":"mobile","entries":[{"category":"reseaux","minutes":5}]}
     ```

   Remplace `reseaux` par `scroll_passif` ou `adulte` selon la macro.

3. Répète pour chaque catégorie que tu veux suivre.

**Le nom des applications ne quitte pas le téléphone :** c'est la macro qui
connaît la liste, le serveur ne reçoit que la catégorie. Même garantie que sur
les autres surfaces.

**Attention à l'adresse.** Si ton API tourne sur `127.0.0.1`, le téléphone ne
la joindra pas : il lui faut l'IP de ton PC sur le réseau local, et le serveur
Django lancé avec `runserver 0.0.0.0:8000`. Hors de chez toi, il faudra un
déploiement — c'est un sujet séparé.

---

## Chemin 2 — la sonde native (à construire)

Une petite application Android qui lit `UsageStatsManager` et pousse chaque
nuit le temps réel par application, catégorisé localement (SPEC §9.2).

`UsageStatsReader.kt` contient le cœur : la lecture des statistiques, la
catégorisation locale et l'envoi. C'est la partie qui demande de la réflexion.

> **Ce fichier n'a été ni compilé ni exécuté.** Il n'y a pas de SDK Android sur
> la machine où il a été écrit. Traite-le comme un point de départ relu, pas
> comme du code livré.

### Ce qu'il reste à faire

1. Android Studio → nouveau projet **Empty Activity**, Kotlin, `minSdk 26`.
2. Copier `UsageStatsReader.kt` dans le paquet de l'application.
3. Dans le manifeste :

   ```xml
   <uses-permission android:name="android.permission.PACKAGE_USAGE_STATS"
                    tools:ignore="ProtectedPermissions" />
   <uses-permission android:name="android.permission.INTERNET" />
   ```

4. La permission ne se demande pas par une boîte de dialogue : il faut envoyer
   l'utilisateur dans `Settings.ACTION_USAGE_ACCESS_SETTINGS` et le laisser
   l'accorder à la main, une fois.
5. Un `WorkManager` périodique (une fois par nuit) qui appelle le lecteur.
6. Un écran unique : état de connexion, bouton de synchronisation manuelle.
   Rien d'autre (§9.2).

### Pourquoi ce n'est pas fait tout de suite

C'est le morceau le plus long du lot, il ne se vérifie pas sans appareil, et il
suppose un environnement Android complet. Le chemin 1 couvre le besoin réel
— marquer les gardes — dès ce soir, avec zéro compilation.
