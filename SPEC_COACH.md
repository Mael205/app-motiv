# SPEC — Système de discipline personnel ("le Coach")

> Document à donner à Claude Code comme brief initial de projet.
> Développeur solo. Communication directe attendue, pas de flatterie, pas de jugement esthétique non sollicité.
> Commits atomiques en français.

---

## 0. Ce qu'il faut comprendre avant de coder

Ce n'est **pas** une todo-list ni un habit tracker de plus. Le système est conçu contre un profil précis, et chaque mécanique répond à un point de diagnostic. Si tu proposes une simplification qui casse une de ces mécaniques, dis-le, mais explique quel point du diagnostic tu sacrifies.

**Profil de l'utilisateur :**

1. **Aucune contrainte interne.** Tout ce qui a marché historiquement venait de l'extérieur (cours obligatoires, deadlines subies, compétition). Dès que le cadre externe disparaît, tout s'arrête. → L'app doit **tenir le cadre**, pas encourager.
2. **Trop de motivation, pas trop peu.** Il démarre beaucoup, abandonne au jour 5-7 quand un projet plus excitant apparaît. → Le problème n'est pas la motivation, c'est l'absence de plafond.
3. **Le tueur réel : "j'ai oublié une fois, donc j'arrête."** Un streak fragile type Duolingo l'achèverait. → Le streak doit **survivre à un jour raté, pas à deux**.
4. **Concentration ≈ 1h max.** C'est normal, ce n'est pas à corriger. Le problème est le nombre de sessions, pas leur durée.
5. **Fuite de temps : YouTube / réseaux, pas les jeux.** Il rentre à 18h, se couche à 23h, ~3h réellement dispo. Il veut parfois se détendre *avant* de bosser, et parfois ça bouffe la soirée entière.
6. **Contraintes acceptées :** streak public non falsifiable, bilan hebdo automatique envoyé à un ami (1×/semaine, PAS une notif à chaque échec — il a explicitement rejeté ça).
7. **Contrainte refusée :** blocage des jeux (Dofus, Smash = détente légitime). Le blocage ne doit viser que le scroll passif.
8. **Ce qui lui donne le sentiment d'avancer :** roadmap + compteur d'heures + journal relisible, **et surtout un aspect jeu, dopamine, un peu addictif**.
9. **Il travaille bien avec un plan clair et tracé, mal avec un cadre ouvert.** « Avance sur le projet » ne produit rien ; « étape 3, écrire le test de collision, fichier *X*, 25 min » produit une session. Ce n'est pas un manque d'autonomie, c'est un coût de décision qu'il paie en abandon. → Le système doit **toujours présenter la prochaine action déjà décidée**, jamais un espace vide à remplir. Concrètement : le briefing IA sort une seule tâche et jamais une liste (§5.1), l'accueil propose un seul bouton (§11.1), la session se ferme sur l'amorce de la suivante (§11.3), et une étape de roadmap trop grosse pour tenir en une session est un défaut à corriger, pas une étape valide (§4.5).
10. **Il aime l'histoire autour du produit.** L'univers, les noms de saison, les rangs, la mise en scène ne sont pas de la décoration : c'est le carburant qui lui fait ouvrir l'app. Une version fonctionnellement parfaite mais sans identité ne sera pas utilisée. Le §7 et le §13 sont donc des exigences produit, pas du confort.

**Projets réels à préseeder** (modifiables) : prototype de jeu UE5 (4v1 asymétrique, budget zéro), outils Dofus 3 (analyseur de rentabilité craft, simulateur de combat), bot Slay the Spire 2 (RL, C#), app Django de la préfecture (gestion des absences), musculation, roadmap cybersécurité.

---

## 1. Décisions d'architecture arrêtées

Ces points ont été tranchés avec l'utilisateur. Ne pas les rouvrir sans raison, mais signaler si l'implémentation révèle une incohérence.

| Sujet | Décision |
|---|---|
| Dépôt | **Monorepo** : `coach-api/`, `coach-app/`, `coach-agent/`, `coach-mobile/`, `coach-ext/` |
| Temps réel | **SSE** serveur→clients + polling 10 s en repli ; les écritures restent des POST (voir §2) |
| Offline | Autorisé partout ; une session démarrée hors ligne est rejouée et marquée **`non vérifiée`** (§6) |
| Bascule de journée | **4h du matin**, heure serveur. Une session finie à 00h30 valide la veille |
| Fenêtre du soir | **Paramétrable par jour de semaine** (18h–23h en semaine, libre le week-end) |
| Streak | **Deux compteurs** : streak de saison (affiché en grand) + streak historique global (stats) |
| Jour off déclaré | État **neutre** : ni validé ni raté, ne consomme pas de bouclier, **mais remet à zéro la progression vers le prochain bouclier** |
| Projet « coach » | **Hors slot, aucune restriction, aucun quota bloquant.** Ses heures sont mesurées et affichées, rien de plus (§11.6) |
| LLM | **Hybride local/distant** avec porte de qualité obligatoire (§5.6) |
| Notifications | **Natives sur les deux surfaces** : Windows via l'agent, Web Push sur le téléphone. Telegram en redondance et en canal d'entrée rapide |
| Mesure d'activité PC | **Intégration d'ActivityWatch** (open source, local) plutôt qu'une réimplémentation |
| Mesure d'usage mobile | **Mini-app Android compagnon** lisant `UsageStatsManager` |
| Blocage YouTube | **Extension navigateur**, Shorts et feed d'accueil uniquement |
| Enjeu de saison | **Mise symbolique en Éclats**, monnaie interne. Jamais d'argent réel |
| Jalons | **Aucune restriction auto-imposée sur le développement du coach** tant que le projet n'est pas fini |

---

## 2. Contrainte produit centrale : PC + téléphone liés

**Non négociable :** une app PC et une app téléphone, **synchronisées en temps quasi réel**, sur le même compte. Un état, deux surfaces.

| Surface | Rôle |
|---|---|
| **Téléphone** | Notifications push, validation rapide d'une session, capture d'idée dans le frigo, consultation du streak, debrief vocal/texte, remontée du temps d'écran. C'est la surface de *rappel* et de *responsabilisation*. |
| **PC** | Là où le travail réel se fait. Timer, briefing IA, lancement automatique de l'environnement de travail, détection d'activité, journal auto depuis git. C'est la surface d'*exécution*. |

**Règles de sync :**

- Le serveur est la source de vérité. Timestamps serveur uniquement (§6).
- Transport temps réel : **SSE** (`GET /stream`, `text/event-stream`). Le flux ne va que du serveur vers les clients — toutes les écritures passent par des POST classiques, donc un canal bidirectionnel n'apporte rien. SSE reconnecte seul, traverse les proxys, survit aux free tiers, et l'agent PC comme le téléphone consomment le même flux. Repli automatique en polling 10 s si le flux tombe deux fois de suite.
- Écriture offline autorisée sur les deux surfaces, file d'attente locale, rejeu à la reconnexion, résolution par `client_uuid` idempotent.
- Une session démarrée sur PC est visible sur téléphone en < 5 s.
- Si une session tourne sur PC, le téléphone affiche un écran dédié "session en cours" avec le chrono et un bouton d'arrêt d'urgence.

---

## 3. Architecture

Monorepo, cinq composants.

```
coach-api/      Django 5 + DRF + PostgreSQL       → source de vérité, logique métier, appels IA
coach-app/      React + Vite, PWA installable     → UI unique PC (navigateur/desktop) et mobile
coach-agent/    Python, Windows, tray             → automatisation locale, mesure d'activité, blocage
coach-ext/      Extension navigateur (MV3)        → filtrage Shorts/feed, mesure du temps web
coach-mobile/   Android, Kotlin, minimal          → temps d'écran via UsageStatsManager, notifs natives
```

**Pourquoi une PWA et pas deux apps natives :** un seul frontend à maintenir, installable sur Android et Windows, notifications système réelles via Web Push, coût zéro. `coach-mobile` n'est pas une seconde interface : c'est une sonde de ~300 lignes sans écran significatif, dont le seul rôle est de remonter le temps d'écran que le navigateur ne peut pas lire.

**Notifications — réponse à « comme une appli normale » :** oui, ce sont de vraies notifications système sur les deux surfaces.
- **PC :** l'agent local envoie des notifications Windows natives (toasts avec boutons d'action). Fiabilité totale, aucun serveur impliqué, elles marchent même si le navigateur est fermé.
- **Téléphone :** Web Push via le service worker de la PWA installée. Ce sont de vraies notifications Android, avec icône, actions et son. Deux limites connues : l'optimisation de batterie d'Android peut les retarder de quelques minutes, et une notification programmée exige que le serveur soit réveillé à l'heure dite.
- **Filet de sécurité :** Telegram double les notifications critiques (gardien de 21h30, rappel de créneau) et sert de canal d'entrée rapide (valider une session, jeter une idée au frigo, envoyer un vocal) sans ouvrir l'app.
- Le serveur planifie ses déclencheurs avec un vrai ordonnanceur persistant (Celery beat ou APScheduler + table de jobs) ; un cron externe de ping empêche le free tier de s'endormir avant 21h30.

**Hébergement, budget quasi nul :** Postgres managé gratuit (Neon / Supabase), API sur Fly.io ou Railway free tier, front en statique (Cloudflare Pages). Documente le déploiement dans `DEPLOY.md`. Seul coût réel possible : les appels au modèle distant (§5.6), de l'ordre de 1 à 3 €/mois, réductible à zéro quand le local suffit.

**Auth :** un seul utilisateur au départ mais modélise proprement (JWT, refresh long sur mobile). Pas de compte à créer sur le téléphone : QR code d'appairage généré depuis le PC.

---

## 4. Mécaniques du système

### 4.1 Le plancher quotidien

- **Une session de 25 minutes valide la journée.** Pas 3h. Le plancher est volontairement ridicule pour survivre aux mauvais soirs.
- **Mode dégradé :** 10 minutes. Valide le streak. Existe uniquement pour empêcher le "j'ai rien fait donc j'arrête tout".
- Durées proposées : 10 (dégradé) / 25 / 50. Pas plus de 50.
- **Le mode dégradé garde son bonus de première session du jour** (décision assumée : le point dur est le démarrage, pas la durée ; récompenser fortement le fait de s'y mettre est le comportement qu'on cherche à installer).
- **Bouton « prolonger »** : à la fin d'un dégradé, une proposition unique de continuer 15 min de plus. Accepter convertit la session en session normale et complète l'XP. C'est le vrai levier : une fois lancé, continuer est facile.

### 4.2 Le streak et les boucliers

L'anti-fragilité est la mécanique la plus importante du produit.

- Streak = nombre de jours consécutifs avec au moins une session validée. **Deux compteurs tenus en parallèle :** le *streak de saison* (grand chiffre de l'accueil, 0–28) et le *streak historique* (jamais remis à zéro, visible dans les stats).
- **Boucliers** : stock de 2 au départ, max 3, +1 tous les 5 jours validés consécutifs.
- Un jour raté consomme automatiquement un bouclier, le streak continue. **Pas de bouclier disponible → streak à 0.**
- Deux jours ratés d'affilée cassent le streak même avec des boucliers en stock (règle « jamais deux fois »).
- **Trois états de journée, pas deux** : `validé`, `raté`, `neutre`. Seuls les `raté` comptent dans la règle « jamais deux fois ». Les jours neutres sont retirés du calcul de continuité.
- Sont neutres : les **jours off déclarés** (§11.5) et les **2 jours de pause entre deux saisons** (§12.4). Le streak reprend au même chiffre après.
- Un jour neutre **remet à zéro la progression vers le prochain bouclier** (`consecutive_for_shield`). Il ne coûte rien, mais il ne construit rien.
- Le message affiché après un jour raté ne culpabilise pas. Il dit exactement : *"Bouclier consommé. Il t'en reste N. La règle : jamais deux fois d'affilée."*
- Évaluation du streak **côté serveur**, à chaque lecture, avec bascule de journée à **4h du matin**.

### 4.3 Trois slots actifs + le frigo

- **Maximum 3 projets actifs.** Hard limit. C'est le cœur du dispositif anti-dispersion.
- **Le frigo** : capture illimitée d'idées de projets. Champ libre, 5 secondes, accessible en un tap depuis le téléphone ou en un message Telegram.
- **Échange de slot uniquement le dimanche.** Le reste de la semaine, le bouton est désactivé avec la date du prochain créneau. Un projet sorti d'un slot va en archive, pas à la poubelle : ses heures et son journal restent.
- Chaque projet actif porte un **engagement hebdo** : nombre de sessions visées cette semaine (défaut 3). La somme des engagements est plafonnée à ce que la fenêtre du soir permet réellement — refuse et affiche l'incohérence s'il sur-engage.
- L'engagement est **historisé par semaine** (table dédiée), sinon "engagements tenus vs pris" est incalculable.
- Le projet « développement du coach » **ne consomme pas de slot** et n'est soumis à aucun quota bloquant (§11.6).

### 4.4 Progression, XP et plafond

C'est demandé explicitement : *"un peu addictif, un peu dopamine"*. Assume-le, mais sans mécaniques prédatrices : pas de FOMO artificiel, pas de perte rétroactive, pas de notification manipulatrice le soir.

**Calcul d'XP d'une session :**

```
base       = minutes effectives
+ 20       si première session du jour (mode dégradé inclus)
+ 10       si démarrée avant 20h
× (1 + min(streak_saison, 10) × 0.05)      multiplicateur de streak, max ×1.5
× momentum                                  jauge de chaleur hebdo (§13.3), 1.0 → 1.25
× dégressivité                              1.0 / 1.0 / 1.0 / 0.5 / 0.0 selon le rang de la session dans la journée
```

- **Le plafond manquant est ici.** À partir de la 4ᵉ session du jour l'XP est divisée par deux, à partir de la 5ᵉ elle est nulle. La session reste enregistrée, les heures comptent, la roadmap avance — seule la récompense s'éteint. Répond au diagnostic §0.2 : le sur-régime du jour 2 est ce qui produit l'abandon du jour 6.
- Un message factuel accompagne le dépassement : *"4ᵉ session. Ton rythme tenable observé est de 2,3 sessions/jour. Au-delà, l'XP ne compte plus."*
- **Niveaux** à courbe croissante, **rangs F→SS** (§12.3), titres de saison.
- **Quêtes du jour** : 1 quête plancher (obligatoire), 1 quête bonus contextuelle. Plus une **quête hebdomadaire** plus ambitieuse, posée le dimanche.
- **Loot cosmétique** au passage de niveau et en fin de semaine (§12.6). Aucune récompense ne donne d'XP sans travail réel.
- **Aucune XP pour l'usage de l'app** : planifier, éditer la roadmap, ranger le frigo, configurer un thème ne rapportent rien. Sinon le système récompense l'optimisation du système.
- **Jauge du soir** (élément signature, §7) : la fenêtre du jour remplie par les blocs de session, avec curseur temps réel.

### 4.5 Roadmap, heures, journal

- Chaque projet a une **roadmap** : liste ordonnée d'étapes, chacune avec état (à faire / en cours / fait) et estimation en sessions. Pourcentage de complétion affiché.
- **Granularité imposée (§0.9) :** une étape estimée à plus de 3 sessions est marquée *à découper*, et le découpage est proposé par l'IA (§5.1). Une roadmap dont l'étape courante est floue est traitée comme un défaut du système, pas comme un état normal.
- Un projet actif doit avoir **au moins une étape `à faire` ou `en cours`** en permanence. Si la roadmap est vide ou terminée, l'app réclame le prochain jalon avant d'autoriser une session sur ce projet.
- **Import de roadmap** depuis un `TODO.md` / `ROADMAP.md` du dépôt déclaré : l'agent lit le fichier, l'IA le convertit en étapes, confirmation en un tap.
- **Compteur d'heures cumulées** par projet, par branche de compétence, par semaine, par saison et total.
- **Journal** : chaque session produit obligatoirement une entrée, relisible chronologiquement et filtrable par projet.

### 4.6 Le sas de détente

Il veut parfois scroller avant de bosser. Ne pas l'interdire — le cadrer.

- Bouton **"Sas de détente : 30 min"**. Pendant ce temps, rien n'est bloqué, aucune notification, aucun jugement.
- À la fin du sas : notification ferme sur les deux surfaces, et l'agent PC arme le blocage du scroll passif jusqu'à la validation de la session du jour.
- Le sas est limité à **une utilisation par soir**. Deuxième tentative → refusée, avec le temps restant avant la fin de la fenêtre affiché.
- **Le blocage ne vise jamais les jeux.** Liste blanche explicite : Steam, Dofus, émulateurs. Liste noire : scroll passif uniquement. YouTube est traité par l'extension (§9.1) : Shorts et feed d'accueil bloqués, recherche et vidéos longues accessibles.
- Le sas est disponible dès J1 sans blocage (timer + notification ferme). Le blocage effectif arrive avec l'agent.

### 4.7 Bilan hebdo envoyé à un ami

- **Une fois par semaine, dimanche soir.** Jamais de notification à un tiers lors d'un échec individuel.
- Contenu : streak, heures par projet, étapes terminées, engagements tenus vs pris, avancement du boss de saison, titre courant, une phrase de synthèse écrite par l'IA (factuelle, pas humiliante).
- **N'y figure pas :** la qualité de session, le temps d'écran, les fuites de temps. Ces signaux sont bruités ; les envoyer à un tiers transforme du bruit en jugement social et donnerait une bonne raison de couper le bilan.
- Envoi par email ou webhook (Discord/Telegram). Le destinataire est configuré une fois, et **le désactiver demande une confirmation à 24h de délai**. C'est le seul mécanisme volontairement difficile à désarmer du produit.
- **Accusé de lecture** : un bouton "vu" dans le message. Si l'ami ne lit pas 3 semaines de suite, l'app le signale et propose un autre destinataire — un contrôleur qui ne regarde pas ne contrôle rien.

---

## 5. L'IA comme coach actif

L'IA n'est pas un chatbot collé sur le côté. Elle occupe cinq rôles précis, chacun déclenché automatiquement.

### 5.1 Le briefing de session

**Déclencheur :** clic sur "Lancer une session".

**Entrée :** roadmap du projet, 5 dernières entrées de journal, amorce laissée à la session précédente, blocages non résolus, commits git récents (fournis par l'agent), durée choisie, heure, niveau d'énergie déclaré.

**Sortie, en JSON strict :** **une seule** tâche dimensionnée pour la durée ; une checklist de 2 à 4 sous-étapes vérifiables ; la définition de terminé en une phrase ; les commandes shell prêtes à coller ; les fichiers concernés.

**Règle dure :** si la roadmap est trop floue pour produire une tâche de 25 min, le modèle ne doit pas inventer une tâche vague. Il répond que la prochaine action est de découper l'étape, et propose le découpage. Le flou est l'ennemi identifié n°1 (§0.9).

### 5.2 Le debrief et la prise de notes automatique

**Déclencheur :** fin de session.

- Champ pré-rempli à partir des **commits git de la fenêtre de session** — l'agent lit `git log` sur les dépôts déclarés. Commits atomiques et en français = excellent signal brut.
- **Debrief vocal** : dictée transcrite localement (Whisper via l'agent, ou l'API si le PC est éteint), puis structurée. Parler 40 secondes est beaucoup moins coûteux que taper, donc beaucoup plus susceptible d'être fait tous les jours.
- L'IA reformule en entrée de journal propre, **propose la mise à jour des étapes de roadmap** (confirmation en un tap, jamais d'écriture silencieuse), et extrait les points bloquants.
- **Vérificateur :** si la note est vague ("j'ai avancé"), une seule relance avec une question précise. Pas de harcèlement.
- Blocage détecté → stocké et **réinjecté dans le briefing suivant**.
- **Amorce obligatoire** (§11.3) avant clôture.

### 5.3 La revue hebdomadaire et l'analyse dialoguée

**Déclencheur :** dimanche soir, automatique. Détail complet en §13.

- Détecte la **dérive** : concentration excessive sur un projet, étape figée depuis 3 semaines, engagement systématiquement non tenu.
- Propose le **contrat de la semaine suivante**, ajusté au réel observé et pas à l'ambition déclarée.
- Gère l'échange de slot du dimanche et le tri du frigo.
- Ouvre une **session de questions-réponses** (4 à 5 questions ciblées) dont les réponses alimentent le compte-rendu.
- Génère le texte du bilan envoyé à l'ami.

### 5.4 Le gardien de fin de soirée

**Déclencheur :** 21h30 (ou fin de fenêtre − 90 min), si aucune session validée et si le créneau du jour a été manqué.

- Notification native sur les deux surfaces. Ton direct : rappel du plancher, boucliers restants, état du boss de saison, et **une proposition de tâche de 10 minutes précise** issue de la roadmap. Pas "tu devrais bosser", mais "10 min : écrire le test de collision du monstre, fichier *X*".
- Version déterministe disponible sans IA (construite depuis la roadmap), pour que le gardien existe dès J1 et ne tombe jamais.

### 5.5 L'analyste

**Déclencheur :** chaque nuit après la bascule de 4h, et en fin de saison. Détail en §13. Produit les constats factuels sur le temps réel, les fuites, les créneaux de décrochage, les corrélations observées.

### 5.6 Implémentation technique de l'IA

- Appels **côté serveur uniquement** (clé API jamais dans le client).
- Abstraction `LLMProvider` avec deux backends : `local` (Ollama sur le PC, exposé au serveur par l'agent via un tunnel sortant authentifié) et `remote` (API Claude).
- **Routage :** briefing et debrief → local si le PC est en ligne, sinon distant. Revue hebdo, analyse de saison, gardien du soir → toujours distant (enjeu élevé, ou PC potentiellement éteint).
- **Porte de qualité obligatoire avant d'activer le local.** Le local n'est pas activé par confiance mais par mesure : un jeu de 20 cas réels (roadmaps floues, roadmaps nettes, notes vagues, notes riches) est rejoué contre les deux backends, avec un score sur trois critères — validité du schéma JSON, unicité de la tâche proposée, présence de fichiers et de commandes exploitables. **Si le local passe sous 90 % du score distant, il est désactivé automatiquement** et un bandeau le dit. Pas de dégradation silencieuse de la qualité du coaching pour économiser trois centimes.
- **Sorties structurées** : schéma JSON strict, validation Pydantic, retry puis **fallback déterministe** (briefing minimal construit sans IA depuis la roadmap). L'app n'est **jamais** bloquée par une panne d'API.
- Cache des briefings 10 minutes.
- **Ton du coach, encodé dans le system prompt :** français, tutoiement, direct, factuel, zéro flatterie, zéro "bravo champion". Il constate, il chiffre, il propose la prochaine action. Il ne fait pas de morale et ne commente jamais la valeur des projets. Il peut employer le vocabulaire de l'univers de la saison en cours, jamais au prix de la clarté.

---

## 6. Non-falsifiabilité

Le streak doit être crédible à ses propres yeux, sinon tout le système est décoratif.

- **Timestamps serveur** dès que la connexion existe. Le client ne décide jamais de l'heure.
- Une session est créée à son démarrage (`status: running`) puis clôturée. Impossible de déclarer après coup une session de 3h.
- **Sessions hors ligne :** autorisées, rejouées à la reconnexion, et marquées **`non vérifiée`** de façon visible (badge sur la session, mention dans les stats). Limite de **2 par semaine** ; au-delà, refus. Une session non vérifiée valide le streak mais ne compte pas dans les records de saison. Le compromis est assumé : mieux vaut une session tracée honnêtement comme incertaine qu'une soirée de travail perdue.
- Édition rétroactive d'une entrée de journal : autorisée 24h, tracée (`edited_at`), et les minutes ne sont **jamais** modifiables.
- **Preuve d'activité optionnelle** (§9.4) : pourcentage de temps où une application déclarée du projet était au premier plan, et temps d'inactivité. Affiché comme *qualité de session* (0-100 %), **n'invalide jamais une session**, reste local et n'est jamais envoyé à l'ami.
- Un log d'événements append-only, non éditable depuis l'UI.

---

## 7. Direction visuelle et juice

Interface unique responsive (mobile d'abord, s'étale proprement en desktop). Fiche de personnage RPG assumée, mais sobre — pas de skeuomorphisme, pas de parchemin.

**Palette de base** (à respecter, pas de gris bleuté générique) :
- fond `#191320` (prune très sombre)
- panneaux `#241A33`
- accent principal `#E8A33D` (or) — XP, streak, actions
- accent secondaire `#4FC4B4` (turquoise) — progression, roadmap
- alerte douce `#DE5F7E` (rose) — bouclier consommé, dérive
- texte `#EDE6F5` / atténué `#9A8CAE`

**Chaque saison surcharge un accent et une texture** (§12.2), jamais le fond ni la lisibilité. L'identité de saison se voit en 2 secondes sans qu'aucun texte ne devienne moins lisible.

**Typographie :** display condensé, capitales, interlettrage serré pour les titres et les rangs. Chiffres en **monospace systématiquement** (heures, XP, streak, minutes) — les données doivent avoir une texture différente du texte.

**Élément signature : la jauge du soir.** Bande horizontale unique représentant la fenêtre du jour, curseur temps réel, blocs de session posés dessus, zone écoulée en creux. Premier élément de l'écran d'accueil. Elle dit une seule chose : *voilà ce qu'il te reste ce soir*.

**Juice — fort mais canalisé.** Quatre moments seulement portent des effets riches ; partout ailleurs l'interface reste calme.

1. **Démarrage de session** — l'interface se replie sur le timer, tout le reste s'éteint, l'emblème du projet s'imprime. Séquence courte, sensation d'entrer quelque part.
2. **Fin de session** — le bloc se pose sur la jauge du soir avec un impact (léger *hit-stop* puis rebond), la barre d'XP se remplit avec un compteur qui défile et une décélération marquée, les dégâts au boss de saison s'affichent en chiffres qui montent.
3. **Passage de niveau / rang** — plein écran, 1,5 s, emblème du nouveau rang, tirage de carte de loot si applicable.
4. **Fin de saison** — séquence dédiée : score final, comparaison au fantôme (§12.7), titre décerné, ouverture de la saison suivante.

Règles de mise en œuvre : easing systématique (jamais de linéaire sauf le curseur de temps), squash & stretch discret sur les compteurs, `prefers-reduced-motion` respecté avec une variante non animée pour chacune des quatre séquences, aucune animation supérieure à 400 ms hors séquences 3 et 4, **jamais d'animation sur le chemin critique** — le bouton "Démarrer" répond immédiatement et l'effet se joue par-dessus. Les skills `game-feel`, `game-ui-ux` et `framer-motion` installés dans le dépôt servent de référence d'implémentation.

**Ton de l'interface :** français, tutoiement, phrases courtes, actives. Les états vides sont des invitations à agir, pas des blagues. Les erreurs disent quoi faire.

---

## 8. L'agent local (automatisation PC)

`coach-agent`, Python, Windows, icône dans la barre système, démarrage automatique.

**Communication :** l'agent consomme le flux SSE et poste ses événements. Il n'expose aucun port entrant.

**Sécurité — non négociable :** l'agent n'exécute **que des actions d'une liste blanche déclarée localement** dans un fichier de config que seul l'utilisateur édite, non modifiable via l'API. Le serveur ne peut jamais faire exécuter une commande arbitraire. Même si la réponse d'un modèle est compromise, le pire cas est le lancement d'une application déjà autorisée.

**Capacités :**

1. **Profils de travail par projet.** Chaque projet déclare : exécutables (Unreal, VS Code, Rider, terminal), dossiers, URLs, commandes de démarrage. Un clic sur "Lancer une session" → l'environnement complet s'ouvre. C'est l'automatisation attendue : ne plus perdre les 10 premières minutes à se remettre en place.
2. **Fermeture de fin de session** (optionnelle, à confirmer) : ferme les onglets et apps de distraction, jamais l'environnement de travail.
3. **Journal automatique depuis git** : `git log --since=<début de session>` sur les dépôts déclarés, envoyé pour pré-remplir le debrief. Lit aussi `TODO.md` pour l'import de roadmap.
4. **Mesure d'activité via ActivityWatch.** L'agent n'implémente pas son propre suivi de fenêtre : il lit l'API locale d'ActivityWatch (`localhost:5600`), qui gère déjà proprement la fenêtre active, l'inactivité clavier/souris, le multi-écran et la veille. L'agent se contente de catégoriser (travail du projet / travail hors projet / scroll passif / jeu / autre) et d'agréger. Si ActivityWatch n'est pas installé, l'agent le signale et la qualité de session est simplement absente. **Aucune capture d'écran, aucun keylogging** — même pour soi, la ligne est là.
5. **Blocage du scroll passif** : actif uniquement après le sas de détente ou après le gardien du soir sans session. Domaines pleins (TikTok, X, Instagram, Reddit) via fichier hosts, YouTube via l'extension. L'élévation nécessaire au fichier hosts est isolée dans un petit service Windows séparé qui n'accepte que deux ordres, `block` et `unblock`, via un pipe local — l'agent lui-même tourne en utilisateur normal. Toujours désactivable en 2 clics avec temporisation de 60 secondes : la friction suffit, l'emprisonnement non.
6. **Notifications Windows natives** relayant les mêmes déclencheurs que le push mobile, avec boutons d'action (démarrer 10 min, reporter 15 min).
7. **Détection de session fantôme** : si une session tourne depuis > durée + 15 min sans activité, l'agent alerte le serveur qui clôture au temps réellement actif.
8. **Transcription vocale locale** (Whisper) pour le debrief, et pont vers Ollama pour le backend LLM local.

---

## 9. Les autres surfaces

### 9.1 `coach-ext` — extension navigateur (MV3)

- Redirige `/shorts`, masque le feed d'accueil YouTube et les Reels intégrés quand le blocage est armé. Laisse la recherche, les vidéos longues et la documentation accessibles.
- Mesure le temps réel par domaine, complément d'ActivityWatch qui ne voit que "navigateur".
- Fonctionne sans privilège administrateur.

### 9.2 `coach-mobile` — sonde Android

- Lit `UsageStatsManager` (permission `PACKAGE_USAGE_STATS`, accordée une fois à la main) et pousse chaque nuit le temps par application.
- Catégorisation : scroll passif / jeux / utile / autre, éditable.
- Relaie aussi les notifications natives si le Web Push se montre peu fiable.
- Pas d'écran au-delà d'un état de connexion et d'un bouton de synchronisation manuelle.

---

## 10. Modèle de données

```
User(id, timezone, day_rollover_hour=4, buddy_channel, buddy_disable_requested_at,
     telegram_chat_id, current_season)
DayWindow(user, weekday, start_time, end_time)              # fenêtre du soir par jour
Device(id, user, kind[pc|phone], name, paired_at, push_subscription)

Track(id, user, kind[atelier|corps|entretien])
Project(id, user, track, name, status[active|fridge|archived], slot[1..3|null], color,
        emblem, is_coach_project, created_at, archived_at)
ProjectRepo(id, project, path, remote)
WorkProfile(id, project, executables[], folders[], urls[], commands[])
RoadmapStep(id, project, order, label, state[todo|doing|done], estimated_sessions,
            needs_split, done_at)
TimeSlot(id, project, weekday, start_time, duration_minutes, active)     # rendez-vous fixes
Commitment(id, project, week_start, planned_sessions, done_sessions)     # historisé

Session(id, user, project, started_at, ended_at, planned_minutes, actual_minutes,
        mode[normal|degraded], status[running|done|abandoned], xp_awarded,
        multipliers_json, rank_in_day, focus_quality, energy_level,
        verification[server|unverified], client_uuid, season)
JournalEntry(id, session, raw_note, ai_summary, blockers[], next_action, source, edited_at)
Briefing(id, session, task, checklist[], done_definition, commands[], files[],
         model_used, backend[local|remote])
FridgeIdea(id, user, text, created_at, promoted_at, source)

StreakState(id, user, track, scope[season|global], current, best, shields,
            last_validated_date, consecutive_for_shield)
DayStatus(id, user, track, date, status[validé|raté|neutre], shield_consumed, reason)
DayOff(id, user, date, declared_at, season)

Season(id, user, index, name, theme_key, modifier_key, started_at, ends_at,
       stake_shards, status[running|closed|paused])
SeasonBoss(id, season, name, max_hp, current_hp, art_key)
SeasonScore(id, season, hours, sessions, steps_done, commitments_kept, xp, final_rank)
Ghost(id, season, day_index, cumulative_xp, cumulative_hours)            # courbe de référence
Quest(id, user, scope[jour|semaine], date_or_week, kind[plancher|bonus|hebdo], label,
      target, progress, state, reward_xp)

Routine(id, user, track, name, anchor[reveil|apres_douche|avant_coucher|fin_de_session|libre],
        weekdays[], weekly_target, reward_shards, order, active, created_at, archived_at)
RoutineCheck(id, routine, day, checked_at, source, shards_awarded)      # unique (routine, day)
RoutineWeek(id, routine, week_start, done, target, held, bonus_awarded) # semaines tenues, cumulatif

RankState(user, code[F|E|D|C|B|A|S|SS], level, xp_total)
SkillBranch(id, user, key, hours, tier)
Achievement(id, user, key, unlocked_at)                                  # hauts faits
Relic(id, user, key, effect_json, unlocked_at)                           # bonus passifs
LootCard(id, user, key, rarity, obtained_at, equipped)
Wallet(user, shards)

RelaxWindow(id, user, date, started_at, ends_at)
BlockPolicy(user, blacklist[], whitelist[], youtube_mode, armed_until)

DailyReport(id, user, date, stats_json, leaks_json, ai_text)
WeeklyReview(id, user, week_start, stats_json, dialogue_json, ai_text, sent_at, buddy_read_at)
SeasonReview(id, season, stats_json, deltas_json, ai_text)
TimeLeak(id, user, date, source[pc|web|mobile], category, minutes, hour_bucket)
PhoneUsage(id, user, date, package, minutes, category)
AgentEvent(id, user, type, payload, created_at)                          # append-only
```

---

## 11. Mécaniques complémentaires

### 11.1 L'app décide, l'utilisateur exécute

À 21h, fatigué, face à 3 projets, il ne choisit pas : il ouvre YouTube. **La paralysie du choix est un mode de défaillance réel, pas une hypothèse.**

- L'écran d'accueil affiche **une seule proposition** : projet + durée + tâche, avec un bouton unique "Démarrer".
- Le projet est calculé côté serveur : engagement hebdo restant, retard relatif, dernier passage, créneau du jour, état du boss.
- Changer de projet reste possible mais coûte un tap supplémentaire ("autre chose") — jamais au même niveau visuel que le bouton principal.
- Aucun écran de sélection au démarrage. La liste des projets vit dans un autre onglet.

### 11.2 Rendez-vous fixes plutôt qu'intentions

"Je bosserai ce soir" se rate ; "mardi 20h30, bot STS2" se tient.

- Chaque projet actif porte des **créneaux hebdomadaires fixes** (jour + heure), définis lors du contrat du dimanche.
- Export `.ics`, notification native 10 min avant sur les deux surfaces.
- Le gardien du soir (§5.4) ne se déclenche que si le créneau du jour a été manqué.

### 11.3 L'amorce

Le démarrage à froid est le coût le plus élevé du système. On le paie à la fin de la session précédente, quand le contexte est encore chaud.

- Avant de clôturer une session, champ obligatoire : **la première action de la prochaine session**, une phrase concrète et exécutable.
- Affichée telle quelle au démarrage suivant, et entrée prioritaire du briefing IA.
- Si l'amorce est vague, le vérificateur relance une fois.

### 11.4 Deux pistes indépendantes : Atelier et Corps

La musculation ne doit **pas** occuper un des 3 slots — sinon elle tue un projet, ou un projet la tue.

- Piste **Atelier** : 3 slots, streak propre, plancher 1 session/jour.
- Piste **Corps** : objectif hebdomadaire (2 séances par défaut), streak hebdomadaire propre, mode dégradé = 15 min à la maison.
- **Règle dure : une séance de sport ne valide jamais le streak Atelier**, et réciproquement.
- Les deux pistes apparaissent côte à côte sur l'accueil, jamais fusionnées en un score unique.

### 11.5 Jours off déclarés

- Un jour off **déclaré au moins la veille** est **neutre** : ne consomme pas de bouclier, ne casse pas le streak, n'apparaît pas comme un échec.
- Il **remet à zéro la progression vers le prochain bouclier**. Coût nul, bénéfice nul.
- Déclaré le jour même après le début de la fenêtre, ou après coup : refusé, c'est un jour raté normal.
- Plafond de 2 par semaine, 6 par saison.
- Objectif : rendre la planification rentable par rapport à la subissance. C'est la compétence qui manque, autant la récompenser directement.

### 11.6 L'app est elle-même un piège à surveiller — version informative

Ce projet est excitant, technique, avec de l'IA dedans : exactement le profil de ce qui a tué les projets précédents. Le risque réel est qu'il code le coach au lieu de coder ses projets.

- Le développement du coach **est déclaré comme projet du système**, hors des 3 slots, et ses heures sont mesurées comme les autres.
- **Aucune restriction bloquante, aucun quota, aucune fenêtre de modification** tant que le projet n'est pas terminé — décision explicite de l'utilisateur.
- Le système se contente d'**afficher la part** des heures du mois allée dans le coach. Information, pas barrière.
- Une bascule `coach_quota_enabled` existe dans les réglages, désactivée par défaut. Le jour où il veut se mettre la contrainte, elle s'active sans redéveloppement.

### 11.7 Canal Telegram et debrief vocal

- Bot Telegram en redondance de notification et en canal d'entrée rapide : valider une session, jeter une idée au frigo, envoyer un vocal, demander l'état du jour — sans ouvrir l'app.
- **Debrief par message vocal** : transcription locale (Whisper) puis structuration par l'IA.
- Le frigo doit être alimentable en une phrase vocale, à tout moment.

### 11.8 Énergie et sommeil (léger, non médical)

- Déclaration d'énergie en un tap au démarrage (3 niveaux), heure de coucher optionnelle.
- Les analyses peuvent signaler une corrélation observée, en restant factuelles.
- **L'app ne diagnostique rien et ne donne aucun conseil médical.** Une fatigue persistante relève d'une prise de sang, pas d'un tracker.

### 11.9 Piste Entretien — les routines courtes

Skincare, étirements, et les gestes du même ordre : courts, quotidiens ou presque, à coût de démarrage nul. Ils ne relèvent ni de l'Atelier ni du Corps, et ils sont **le pire terrain possible pour une mécanique de streak**. Une session de travail ratée a une excuse — la fatigue, la soirée qui déborde. Une routine de trois minutes n'en a aucune : l'oubli est pur, donc la rupture fait plus mal (§0.3). Une chaîne quotidienne cassable posée sur du skincare est le chemin le plus court vers « j'ai oublié une fois, donc j'arrête ».

D'où une piste séparée, dont les règles sont délibérément différentes des deux autres.

**Structure.** Troisième `Track`, `kind = entretien`, à côté d'Atelier et Corps. La règle dure du §11.4 s'étend telle quelle : **une routine cochée ne valide jamais le streak Atelier ni le streak Corps**, et réciproquement. Les trois pistes ne fusionnent jamais en un score unique.

**Rythme et seuil sont deux réglages distincts.** Chaque routine porte :

- les **jours où elle est proposée** — tous les jours, ou certains jours de semaine ;
- son **objectif hebdomadaire** — le nombre de fois qui rend la semaine *tenue*.

Les deux ne sont pas liés, et c'est là que se loge l'anti-fragilité. Une routine proposée les 7 jours avec un objectif à 6 est *quotidienne* dans la présentation et *indulgente* dans le score : elle apparaît tous les soirs, et un oubli isolé ne coûte rien. Le battement joue ici le rôle que le bouclier joue au §4.2 — même intention, mécanique adaptée au rythme.

**Aucun compteur ne redescend.** Il n'existe pas de streak d'entretien. La semaine est *tenue* ou *non tenue*, et le seul compteur affiché en grand est le **total cumulé de semaines tenues**, qui ne diminue jamais. Une mauvaise semaine ne retire rien : elle n'ajoute pas. C'est la seule progression du système qui soit strictement monotone, et c'est volontaire.

**Récompense en Éclats, jamais en XP.**

- Quelques Éclats par routine cochée, **dans la limite de l'objectif hebdomadaire**. Au-delà, la coche est enregistrée et l'historique la garde, mais elle ne rapporte plus — même principe que la dégressivité du §4.4 : le plafond éteint la récompense, jamais le fait.
- Bonus d'Éclats à la semaine tenue, routine par routine.
- **Aucune XP, en aucun cas.** Cocher des routines ne doit jamais compenser une soirée sans session. L'XP mesure le travail réel ; le niveau et le rang restent adossés à l'Atelier et au Corps. Sans cette règle, la piste Entretien devient le moyen le moins cher de monter en niveau, et le système récompense le contournement.

**Ancrage sur un geste, pas sur une heure.** Le §11.2 impose des rendez-vous horaires aux projets, parce qu'une session se planifie. Une routine, non : elle tient par chaînage à un geste déjà présent dans la journée — après la douche, avant le coucher, au réveil. Chaque routine déclare donc son **ancre**, et le panneau les regroupe par ancre plutôt que par heure. Une notification à 22h30 arrive quand il est déjà ailleurs ; « après la douche » arrive au bon moment sans horloge.

**Présentation : le panneau de quêtes.** Registre Solo Leveling assumé, cohérent avec le §12.2 et le §0.10.

- Un panneau unique, ouvert d'un tap depuis l'accueil, listant les routines attendues aujourd'hui, groupées par ancre.
- Coche en un tap, sans confirmation, sans écran intermédiaire.
- Sous chaque ligne, l'état de la semaine en clair : *4 / 6 cette semaine*.
- **Aucune pénalité, aucun compte à rebours menaçant, aucune mise en scène de l'échec.** Le registre visuel est emprunté, la mécanique punitive ne l'est pas (§17). Le panneau d'une journée où rien n'est coché est identique à celui d'une journée pleine, à la coche près.

**Ce que la piste ne fait pas.** Elle ne consomme aucun des 3 slots (§4.3), ne pèse sur aucun engagement hebdomadaire, ne déclenche pas le gardien du soir (§5.4), et n'apparaît pas dans le bilan envoyé à l'ami (§4.7) — l'ami reçoit un état du travail, pas un relevé d'hygiène.

---

## 12. Saisons, univers et progression

C'est le moteur narratif du produit (§0.10). Il exploite un trait précis : très performant en compétition sur courte durée, incapable de tenir la distance sur un horizon ouvert.

### 12.1 Structure de saison

- Une **saison dure 4 semaines**, avec un score final : heures, sessions, étapes de roadmap terminées, engagements tenus, XP.
- Le classement se fait **contre ses propres saisons passées uniquement**. Aucun inconnu, aucun social.
- **2 jours de pause explicite** entre deux saisons, comptés comme jours neutres (§4.2) : le streak survit.
- **Bénéfice principal, à ne pas perdre de vue :** quand tout casse en semaine 3, la saison suivante démarre dans 8 jours. Ça convertit "j'ai raté, donc j'arrête définitivement" en "j'attends la prochaine saison". Un streak infini n'offre pas cette porte de sortie, et c'est précisément le mode de défaillance principal.
- La **revue de fin de saison** est le seul moment où le nombre de slots, les engagements et les créneaux se revoient en profondeur.

### 12.2 Identité de saison — mélange de registres assumé

Chaque saison tire un nom, un emblème, un accent de couleur, une texture de fond et une phrase d'ouverture. Les registres se mélangent volontairement : métal/festival, dark fantasy, sci-fi.

Réservoir de départ (extensible, éditable) :

| Nom | Registre | Accent |
|---|---|---|
| Hellfest | métal | rouge braise `#E0533D` |
| Heaven's Paradise | métal céleste | or blanc `#F2E6C2` |
| Ragnarök | mythologie nordique | acier froid `#8FA9C4` |
| Purgatoire | dark fantasy | violet cendré `#8A6FB0` |
| Faille S | sci-fi | cyan électrique `#43D9E0` |
| Solstice Noir | dark fantasy | or sombre `#B98A2E` |
| Wacken | métal | vert toxique `#8FD14F` |
| Dernier Rempart | siège | pierre et sang `#C0574F` |
| Aube Rouge | épique | rouge profond `#D1403F` |
| Nadir | sci-fi froid | bleu abyssal `#3E6FA8` |
| Inferno | métal | orange magma `#F07A20` |
| Vigie | sobriété | turquoise `#4FC4B4` |

L'écran d'ouverture de saison affiche le nom en grand, l'emblème, le modificateur tiré et le boss. C'est le seul moment où l'interface a le droit d'être théâtrale.

### 12.3 Rangs et niveaux

- **Rang permanent** sur l'échelle `F → E → D → C → B → A → S → SS`, dérivé du niveau global cumulé. Il ne redescend jamais. C'est la trace longue, celle qui rend visible que six mois de travail ont produit quelque chose.
- **Niveau** numérique à courbe croissante, avec la barre d'XP toujours visible.
- **Titre de saison** décerné à la clôture selon la performance : *Survivant du Hellfest*, *Vainqueur de la Faille S*, *Déserteur de Ragnarök* si la saison est abandonnée — le titre raté existe aussi, factuel et sans humiliation, parce qu'une collection sans trous n'a aucune valeur.

### 12.4 Le boss de saison

- Chaque saison a un boss avec une **barre de vie** dimensionnée sur la performance de la saison précédente × 1,05 (première saison : sur l'estimation du contrat).
- Les dégâts viennent du **travail réel** : minutes de session, étapes de roadmap terminées (gros dégâts), engagements hebdo tenus, séances de la piste Corps.
- La barre de vie est visible en permanence sur l'accueil, sous la jauge du soir. Elle répond à la question "à quoi ça sert, ce soir" mieux qu'un compteur d'XP.
- Tuer le boss avant la fin des 4 semaines déclenche la séquence de fin de saison en avance et ouvre un **mode extra** : les jours restants alimentent directement le score de la saison suivante.

### 12.5 Modificateur de saison

Emprunté aux roguelikes : chaque saison porte un **modificateur** tiré parmi une liste, qui change les règles pour 4 semaines. Il évite que la saison 5 soit identique à la saison 1.

Exemples : *Aube* (XP avant 20h ×1,3, mais le gardien passe à 21h) · *Marathon* (sessions de 50 min ×1,5, dégradé désactivé) · *Fragmentation* (les 4 premières sessions du jour comptent au lieu de 3) · *Siège* (le boss a 20 % de vie en plus, la mise est doublée) · *Discipline* (aucun jour off, mais +1 bouclier au départ) · *Deux fronts* (la piste Corps inflige des dégâts doubles au boss).

Le modificateur est **tiré au sort parmi 3 propositions** à l'ouverture — un choix, pas une subissance.

### 12.6 Éclats, mise et loot

- Les **Éclats** sont la monnaie interne. Gagnés par les sessions, les hauts faits et les fins de saison.
- **Mise de saison** : à l'ouverture, il mise un montant d'Éclats. Saison réussie → mise doublée. Saison ratée → mise perdue. Enjeu réel, aucune conséquence matérielle.
- Les Éclats achètent uniquement du **cosmétique** : thèmes, emblèmes, effets de la séquence de fin de session, titres, cadres d'avatar.
- **Cartes de loot** au passage de niveau et à la clôture de semaine, avec raretés (commun / rare / épique / légendaire) et animation d'ouverture. Aucune carte ne donne d'XP ni ne modifie une règle.

### 12.7 Le fantôme

Reprise directe du contre-la-montre de jeu de course, et c'est la mécanique de compétition qui lui correspond le mieux : il performe contre un adversaire, pas contre une intention.

- Pendant toute la saison, une courbe **fantôme** superposée à la sienne : celle de sa **meilleure saison passée**, jour par jour.
- Affichage permanent en une ligne : *"Jour 12 — tu es à +2h40 sur Ragnarök"* ou *"−1h10, le fantôme est devant"*.
- Choix du fantôme à l'ouverture : la meilleure saison, la dernière, ou la moyenne. Pas de fantôme pour la première saison, remplacée par la trajectoire du contrat.

### 12.8 Hauts faits et reliques

- **Hauts faits** (vocabulaire Dofus assumé) : accomplissements permanents à débloquer — *Premier sang* (première session), *Increvable* (28 jours sans bouclier), *Chirurgien* (10 étapes de roadmap terminées dans une saison), *Retour du néant* (reprendre après un streak cassé), *Ermite* (une semaine sans une minute de scroll passif), *Polyvalent* (trois branches de compétences progressent la même semaine).
- **Reliques** : quelques hauts faits rares donnent un **bonus passif permanent et modéré** — un 4ᵉ bouclier maximum, un jour off supplémentaire par saison, +5 % d'XP avant 20h. Plafonnées à 3 reliques équipées, pour que la progression reste sensible sans devenir absurde.

### 12.9 Arbre de compétences

- Les heures alimentent des **branches réelles** : Moteur de jeu, Reverse & cyber, Backend & web, Data & RL, Corps. Une branche par domaine, pas par projet — deux projets UE5 nourrissent la même branche.
- Chaque branche a des paliers d'heures (10, 25, 50, 100, 200, 400) qui débloquent des titres et des emblèmes.
- Rend visible ce qu'un compteur par projet cache : que 40h dispersées sur trois projets de moteur de jeu constituent quand même 40h de moteur de jeu.
- La revue de saison affiche la **forme de l'arbre** : ce qui pousse, ce qui est à l'arrêt.

### 12.10 Momentum

- Une **jauge de chaleur** hebdomadaire qui monte à chaque jour travaillé de la semaine (1,0 → 1,25 de multiplicateur d'XP) et **redescend progressivement**, jamais d'un coup.
- Visualisée comme une braise qui s'intensifie. Un jour raté la fait tiédir, pas s'éteindre — cohérent avec l'anti-fragilité du §4.2.

---

## 13. Analyses : ce qui marche, ce qui ne marche pas, où part le temps

Quatre niveaux d'analyse, du plus automatique au plus dialogué. Tout ce qui peut être calculé sans intervention l'est.

### 13.1 Bilan automatique quotidien (sans lui)

Généré chaque nuit après la bascule de 4h, lisible en 10 secondes le lendemain matin, poussé sur le téléphone.

- Temps disponible de la fenêtre vs temps réellement travaillé, en une barre.
- Répartition : travail projet / travail hors projet / scroll passif / jeux / hors PC.
- L'écart avec le plan du jour (créneau prévu, tenu ou non).
- Une phrase de constat, jamais plus. *"3h05 disponibles, 50 min travaillées, 1h20 de scroll entre 19h et 20h30."*
- Aucune interaction demandée. Rien à remplir.

### 13.2 Rapport de fuite de temps

Alimenté par ActivityWatch (PC), l'extension (web) et la sonde Android (mobile). Consolidé côté serveur.

- **Créneaux de décrochage** : histogramme par tranche de 30 min, sur 4 semaines glissantes, qui montre où le scroll commence réellement. L'objectif est de trouver l'heure charnière, pas de culpabiliser sur un total.
- **Déclencheurs** : ce qui précède immédiatement le décrochage (fin de session, retour à la maison, blocage technique déclaré dans un debrief). Corrélation observée, présentée comme telle.
- **Comparaison PC / téléphone** : le scroll qui migre du PC vers le téléphone quand le blocage est armé est le contournement le plus probable, et il doit être visible sinon le blocage se croit efficace à tort.
- **Coût affiché en unités du système**, pas en morale : *"1h40 de Shorts cette semaine = 4 sessions de 25 min = 12 % de la vie du boss."*
- Ces données restent **strictement locales à l'utilisateur** : jamais dans le bilan de l'ami (§4.7).

### 13.3 Analyse hebdomadaire dialoguée (avec lui)

Dimanche soir, après la génération des chiffres. C'est le seul moment de la semaine où l'app pose des questions.

- L'IA arrive **avec les constats déjà faits**, jamais avec une page blanche (§0.9). Elle pose **4 à 5 questions ciblées** sur des faits précis : *"Mardi, créneau à 20h30 sur le bot STS2, aucune session et 2h10 de YouTube. Qu'est-ce qui s'est passé ?"*
- Réponses en texte ou en vocal, deux phrases suffisent.
- Sortie : un compte-rendu structuré en trois blocs — **ce qui a marché** (avec la cause identifiée, pas juste le résultat), **ce qui n'a pas marché**, **la seule chose à changer la semaine prochaine**. Une seule, pas trois.
- Le contrat de la semaine suivante est proposé à partir de ça, ajusté au réel observé.
- Si le dialogue est esquivé, la revue se génère quand même sans les réponses, en le notant.

### 13.4 Bilan de saison comparé

À la clôture des 4 semaines.

- Comparaison chiffrée avec **toutes** les saisons passées : heures, sessions, régularité, étapes terminées, engagements tenus, fuites de temps.
- Progressions et régressions explicites, avec les 3 causes les plus probables identifiées à partir des revues hebdo de la saison.
- Forme de l'arbre de compétences, écart au fantôme jour par jour, part du coach dans les heures du mois.
- **La question de fin de saison, toujours la même :** qu'est-ce qui a cassé, et à quelle date exactement. Le système connaît la date ; c'est la cause qu'il vient chercher.

### 13.5 Détection automatique continue

Signaux calculés en permanence, remontés dès qu'ils se déclenchent, sans attendre le dimanche.

- **Projet mort** : projet actif sans session depuis 10 jours → proposition de sortie au dimanche suivant.
- **Étape figée** : même étape `en cours` depuis 3 semaines → proposition de découpage.
- **Engagement irréaliste** : engagement pris non tenu 3 semaines de suite → proposition de baisse chiffrée.
- **Dérive de concentration** : plus de 70 % des heures de la semaine sur un seul projet.
- **Dérive de fin de soirée** : les sessions démarrent de plus en plus tard sur 10 jours glissants.
- **Migration du scroll** : le temps mobile monte quand le blocage PC est armé.
- **Sur-régime** : plus de 3 sessions/jour sur 3 jours consécutifs — signal précoce du crash du jour 6 (§0.2).

---

## 14. Le prix du décrochage — sanctions chiantes mais tankables

Le streak et les boucliers empêchent l'effondrement, mais rater un jour ne coûte actuellement presque rien, et un système sans coût n'est pas un cadre. Il faut donc des sanctions **réelles et désagréables**, sans jamais retomber dans la culpabilisation ni dans la spirale d'abandon.

**Les quatre règles auxquelles toute sanction doit obéir :**

1. **Réparable en 10 minutes.** Toute sanction s'annule par une seule session dégradée. C'est ce qui la rend tankable : elle pique, elle ne condamne pas.
2. **Jamais rétroactive.** On ne retire jamais de l'XP acquise, une heure travaillée, une étape terminée, un haut fait. Ce qui est gagné est gagné — c'est le socle de la crédibilité du système.
3. **Jamais morale.** Aucun texte de reproche. La sanction est un état de fait affiché, chiffré, pas un jugement.
4. **Jamais sociale.** Rien ne sort vers l'ami en dehors du bilan hebdo.

**Palier 1 — un jour raté (bouclier consommé) :**

- **Terne.** L'interface perd sa couleur d'accent de saison et repasse en gris jusqu'à la prochaine session validée. Rien n'est cassé, tout est éteint. C'est visuel, immédiat, chiant, et ça se répare en 10 min.
- **Vitrine fermée.** Les écrans de stats, de collection, de hauts faits et de cosmétiques sont verrouillés jusqu'à la prochaine session. On ne consulte pas ses trophées un soir où on n'a rien fait. L'accueil ne montre plus que la tâche de 10 minutes.
- **Momentum tiédi.** La jauge de chaleur redescend d'un cran (§12.10).
- **Le boss se régénère.** Il récupère l'équivalent d'une session moyenne de vie. Le coût est exprimé dans la seule unité qui compte pour la saison en cours : *"Le boss a récupéré 45 min de vie."*
- **Sas de détente révoqué** pour le lendemain. Le privilège de scroller avant de bosser se perd quand la soirée précédente est partie en scroll. Rendu automatiquement après une journée validée.

**Palier 2 — deuxième jour raté d'affilée (streak cassé, règle « jamais deux fois ») :**

- Tout le palier 1, plus :
- **Blocage anticipé.** Le lendemain, le blocage du scroll passif s'arme à l'ouverture de la fenêtre du soir au lieu de 21h30, et se lève à la validation de la session. Le retour est conditionné, pas puni.
- **Dette de 10 minutes.** La journée suivante demande 35 min au lieu de 25 pour être validée. Une seule journée, non cumulable, jamais plus de 10 min de dette au total. Assez pour être ressenti, trop peu pour décourager.
- **Titre en sursis.** Le titre de saison en cours passe visiblement en sursis. Il se récupère par 3 jours validés consécutifs.
- **Mise entamée.** 25 % de la mise d'Éclats de la saison est perdue. C'est le seul coût irréversible du système, et il est purement symbolique par construction (§12.6).

**Palier 3 — trois jours ou plus (décrochage installé) :**

Ici, punir davantage serait le meilleur moyen de le faire désinstaller. Le système change de registre et devient une rampe de retour.

- Plus aucune sanction ajoutée. Les paliers 1 et 2 restent actifs, rien ne s'empile.
- L'accueil devient un **écran unique de reprise** : une tâche de 10 minutes, tirée de l'étape la plus avancée, avec son fichier et sa commande. Pas de chiffres, pas de streak à zéro affiché en grand, pas de bilan de ce qui a été perdu.
- Le retour déclenche le haut fait **Retour du néant** (§12.8) et rend immédiatement 1 bouclier. Reprendre doit rapporter plus que ne pas s'être arrêté n'aurait coûté — c'est l'inverse exact du réflexe "j'ai raté, donc j'arrête".
- Si le décrochage dépasse 5 jours, l'app propose de **clore la saison en avance** et d'en ouvrir une neuve. La porte de sortie est offerte avant qu'il l'invente lui-même sous forme de désinstallation.

**Ce qui n'est jamais une sanction :** retirer un slot, effacer une roadmap, supprimer des heures, réduire un rang, verrouiller un projet, alerter qui que ce soit, afficher un décompte de jours perdus en gros. Toutes ces mécaniques produisent l'abandon définitif, qui est le mode de défaillance n°1 (§0.3).

---

## 15. Vérification : chaque point du diagnostic est-il réellement couvert ?

Table de traçabilité à tenir à jour. Toute mécanique retirée doit être vérifiée ici avant suppression : si une ligne se retrouve sans mécanique, le produit ne répond plus à son diagnostic et redevient un habit tracker.

| # | Problème | Ce qui le traite | Ce qui casse si on l'enlève |
|---|---|---|---|
| 1 | Aucune contrainte interne, tout venait de l'extérieur | Bilan hebdo à l'ami avec désarmement à 24h (§4.7) · créneaux fixes (§11.2) · gardien du soir (§5.4) · sanctions du §14 · saison à échéance datée (§12.1) | Il ne reste que la bonne volonté, c'est-à-dire ce qui a déjà échoué |
| 2 | Trop de motivation, crash au jour 5-7 | Plafond d'XP dégressif (§4.4) · détection de sur-régime (§13.5) · 3 slots · engagements ajustés au réel observé (§5.3) | Le sur-régime revient, et avec lui l'abandon du jour 6 |
| 3 | « J'ai raté une fois, donc j'arrête » | Boucliers (§4.2) · jours neutres · saisons de 4 semaines avec redémarrage à 8 jours (§12.1) · palier 3 du §14 · haut fait *Retour du néant* · objectif hebdomadaire indulgent et absence totale de streak sur la piste Entretien (§11.9) | Le produit devient un Duolingo, c'est-à-dire un générateur d'abandon |
| 4 | Concentration ≈ 1h | Durées plafonnées à 50 min · plancher à 25 · dégradé à 10 · bouton prolonger (§4.1) | Des sessions trop longues, donc non démarrées |
| 5 | Fuite de temps : scroll passif, 3h/soir | Jauge du soir (§7) · sas de détente cadré (§4.6) · blocage ciblé (§8.5, §9.1) · rapport de fuite de temps PC/web/mobile (§13.2) · détection de migration du scroll | La fuite redevient invisible, donc infinie |
| 6 | Contraintes acceptées : streak public, bilan hebdo | Non-falsifiabilité (§6) · bilan dominical avec accusé de lecture (§4.7) | Le seul point d'appui externe disparaît |
| 7 | Ne pas bloquer les jeux | Liste blanche explicite (§4.6) · catégorie « jeux » distincte dans les analyses (§13.2) | Rejet du produit entier |
| 8 | Ce qui lui donne le sentiment d'avancer | Roadmap et compteurs (§4.5) · journal (§5.2) · saisons, boss, rangs, arbre de compétences (§12) · juice canalisé (§7) | Il n'ouvre plus l'app, et une app fermée ne coache personne |
| 9 | Travaille mal en cadre ouvert | Proposition unique à l'accueil (§11.1) · briefing à une seule tâche (§5.1) · amorce (§11.3) · granularité imposée de la roadmap (§4.5) · analyses qui arrivent avec les constats déjà faits (§13.3) | Le coût de décision revient, et il se paie en abandon |
| 10 | A besoin de l'histoire pour accrocher | Univers et noms de saison (§12.2) · rangs F→SS · boss · modificateurs · fantôme · hauts faits · quatre séquences de juice (§7) | Produit correct, jamais ouvert |

**Les trois soirées à faire fonctionner en priorité.** Un jalon n'est réussi que si ces trois scénarios se déroulent proprement de bout en bout :

- **La soirée normale.** 18h, il rentre. 20h15 la notification de créneau tombe. Il ouvre : un bouton, un projet, une tâche déjà décidée. L'agent ouvre l'environnement. 25 min. Le bloc se pose sur la jauge, le boss perd de la vie, l'amorce est écrite. Coût de décision total : zéro.
- **La mauvaise soirée.** 18h, sas de détente, 30 min de scroll. 21h30, aucune session : notification ferme avec une tâche de 10 min précise, blocage armé. Il fait 10 min. La journée est validée, le streak tient, l'interface reste allumée.
- **Le retour après décrochage.** Il n'a rien fait depuis 4 jours et rouvre l'app. Aucun décompte de honte, aucun bilan de ce qui est perdu. Un écran, une tâche de 10 min, un bouclier rendu à la reprise, et la saison suivante annoncée dans N jours.

Si l'un de ces trois scénarios n'est pas fluide, ce n'est pas un défaut d'ergonomie : c'est le produit qui ne répond pas à son diagnostic.

---

## 16. Jalons

Chaque jalon est conditionné au précédent. **Aucune restriction auto-imposée sur le temps de développement du coach** : l'utilisateur les posera lui-même quand le projet sera fini.

**J0 — Socle.** Monorepo, Django + Postgres, auth JWT, appairage par QR, déploiement fonctionnel, SSE en place, seed des projets réels. Rien de visible, tout de nécessaire.

**J1 — Le noyau *et ses déclencheurs*.**
Projets et slots, sessions avec timer, streak et boucliers, jours off, journal manuel, XP avec plafond, jauge du soir, frigo. **Plus, obligatoirement :** créneaux hebdomadaires fixes, notifications natives sur les deux surfaces, gardien du soir en version déterministe, amorce de fin de session, sas de détente sans blocage, bot Telegram. Squelette de saison : nom, compte à rebours 4 semaines, niveau et rang.
*Justification :* un noyau sans déclencheur ne teste que la contrainte interne, dont le §0.1 dit qu'elle n'existe pas. Les déclencheurs listés ici ne demandent aucune IA et coûtent peu.
*Condition de passage : 7 jours d'usage réel.* Corriger les bugs pendant ces 7 jours est normal et attendu.

**J2 — La saison et le jeu.** Boss, modificateurs, fantôme, Éclats et mise, hauts faits, arbre de compétences, momentum, cartes de loot, et les quatre séquences de juice du §7. C'est ce qui rend le système désirable ; le repousser trop loin, c'est risquer de ne jamais y arriver.

**J3 — L'IA.** Briefing, debrief, mise à jour de roadmap, gardien enrichi, revue hebdo dialoguée, bilan à l'ami. Abstraction `LLMProvider` avec sa porte de qualité et le backend distant. Local ensuite.

**J4 — L'agent PC.** Profils de lancement, journal git automatique, intégration ActivityWatch, transcription vocale locale, détection de session fantôme, notifications Windows natives.

**J5 — Blocage et analyses.** Service de blocage, extension navigateur, sonde Android, bilans quotidiens, rapport de fuite de temps, détections automatiques continues.

**J6 — Confort.** Statistiques longues, export, cosmétiques supplémentaires, réservoir de saisons étendu.

---

## 17. Anti-features

À ne pas construire, même si ça semble une bonne idée :

- Pas de notification à l'ami en cas d'échec ponctuel. Hebdo uniquement.
- Pas de blocage des jeux. Jamais.
- Pas de streak qui casse au premier jour manqué.
- Pas de score de productivité global, pas de comparaison sociale, pas de classement avec des inconnus. Le seul adversaire est son propre fantôme.
- Pas de "bravo, tu es incroyable". Le ton reste factuel, y compris dans l'univers de saison.
- Pas de plus de 3 projets actifs, quelle que soit l'insistance.
- Pas de capture d'écran ni de keylogging par l'agent.
- Pas de saisie manuelle d'une session terminée dans le passé.
- Pas d'écran ouvert du type « qu'est-ce que tu veux faire ce soir ? », pas de champ libre à remplir avant de démarrer, pas de liste de tâches à arbitrer soi-même. Toute décision que le système peut prendre à sa place, il la prend (§0.9). Un espace vide au démarrage est un mode de défaillance, pas de la liberté.
- Pas d'XP ni de récompense pour l'usage de l'app elle-même.
- Pas de streak quotidien cassable sur les routines d'entretien, et pas d'XP pour une routine cochée (§11.9). Une routine se mesure à la semaine et se paie en Éclats — sinon le skincare devient un moyen de monter en niveau sans travailler.
- Pas de cosmétique qui modifie une règle. Le loot est de l'apparence, jamais du pouvoir — sinon le système récompense la chance et plus le travail.
- Pas d'argent réel en jeu. La mise est en Éclats.
- Pas de qualité de session, de temps d'écran ni de fuite de temps dans le bilan envoyé à l'ami.
- Pas d'animation sur le chemin critique d'une action.
- Pas de sanction rétroactive : jamais de retrait d'XP acquise, d'heures travaillées, d'étapes terminées, de niveau ou de haut fait. Une sanction éteint ou verrouille temporairement, elle n'efface rien (§14).
- Pas de sanction qui s'empile au-delà du troisième jour de décrochage. Passé ce seuil, le système devient une rampe de retour, pas une facture.

---

## 18. Attentes techniques

- Tests sur la logique métier critique : évaluation du streak et des boucliers avec les trois états de journée, bascule de 4h, calcul d'XP avec dégressivité et momentum, règle des 3 slots, échange du dimanche, dégâts au boss, mise de saison. Ce sont les endroits où un bug détruit la confiance dans le système.
- Le calcul du streak est une **fonction pure testable** prenant l'historique des `DayStatus` et rendant l'état ; aucune logique de streak dispersée dans les vues.
- Migrations propres, seed de développement avec les projets réels du §0 et deux saisons passées fictives pour tester le fantôme et les comparaisons.
- `README.md` : lancer les cinq composants en local en moins de 5 minutes.
- Commits atomiques, messages en français.
- Pose des questions avant de coder si un arbitrage d'architecture t'engage sur le long terme. Ne pars pas sur une hypothèse silencieuse.
