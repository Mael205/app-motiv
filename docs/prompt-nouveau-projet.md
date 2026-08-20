# Créer un projet — le prompt à coller dans un chat

Le coach n'a pas encore sa couche IA (SPEC §5.6). En attendant, l'interrogation
qui produit une bonne roadmap se fait dans un chat, et le résultat se colle dans
l'app : **Projets → Nouveau projet → coller → confirmer**.

> Le prompt est aussi **embarqué dans l'app**, copiable en un tap depuis l'écran
> « Nouveau projet ». C'est la version à utiliser sur le téléphone : ce fichier
> sert de référence, pas de source unique.

Ce prompt existe pour une raison précise. Une roadmap dont l'étape courante est
floue est traitée par le §4.5 comme un **défaut du système**, pas comme un état
normal : le soir, le coach doit pouvoir proposer « étape 3, écrire le test de
collision, fichier X, 25 min ». Un chat laissé libre produit des étapes du type
« avancer sur le backend », qui ne se démarrent pas. Les contraintes ci-dessous
sont là pour empêcher ça.

---

## À copier tel quel

> Tu m'aides à découper un projet en roadmap pour mon système de discipline
> personnel. Interroge-moi d'abord, une question à la fois, jusqu'à ce que tu
> puisses écrire des étapes concrètes. Ne me propose pas de roadmap avant
> d'avoir compris ce que je veux construire, où j'en suis déjà, et ce qui est
> déjà fait.
>
> Un projet n'est pas forcément du code. Ce peut être un cursus, une discipline
> physique, une pratique artistique, un artisanat : apprendre le pentesting,
> tenir un carnet de cuisine, progresser en danse, préparer un examen. N'impose
> pas le vocabulaire du code à un projet qui n'en est pas.
>
> Je veux un **plan de travail documenté**, pas une liste de tâches. Concrètement :
>
> - **Une ressource principale nommée, avec son adresse.** Pas « faire des
>   exercices en ligne » mais « OverTheWire Bandit —
>   https://overthewire.org/wargames/bandit/ ». Une seule ressource par
>   compétence : deux qui enseignent la même chose, c'est de l'indécision.
> - **Un périmètre exact, y compris ce qu'il faut sauter.** « CS50x, semaines 0
>   à 7 uniquement ; la semaine 4 sur la mémoire est la plus importante ; ne fais
>   pas les semaines 8 à 10. »
> - **Une charge estimée en heures**, fourchette honnête même large. Sans elle je
>   me crois en retard au bout de trois soirs.
> - **Un critère de sortie vérifiable**, qui est un contrat : tant qu'il n'est pas
>   rempli je ne passe pas à la suite, même si je m'ennuie.
> - **Ce que tu écartes, et pourquoi.** Nomme les ressources concurrentes que tu
>   n'as pas retenues avec la raison, pour que je ne refasse pas l'arbitrage dans
>   trois semaines.
> - Si le sujet est **légalement encadré ou dangereux**, pose le cadre en une
>   ligne factuelle avant la première étape.
>
> Rends-moi **deux échelles**, et ne les confonds pas :
>
> - le **parcours** — les grands blocs ordonnés jusqu'au bout de l'objectif, même
>   si cela représente deux ans. L'ordre y est une dépendance, pas une suggestion.
> - la **roadmap** — le détail exécutable du **premier bloc non terminé, et de lui
>   seul**. Les blocs suivants attendent leur tour avec leur ressource et leur
>   charge ; on les découpera quand on y sera.
>
> Contraintes non négociables sur les étapes de la roadmap :
>
> - Chaque étape doit tenir en **3 sessions de 25 minutes maximum**. Au-delà,
>   découpe-la. Une étape à 5 sessions est un défaut, pas une étape.
> - Chaque étape doit être **exécutable sans réfléchir** : un verbe, un objet
>   précis. « Avancer sur l'API » est refusé, « Écrire l'endpoint POST /recettes
>   et son test » est bon. « Travailler la souplesse » est refusé, « Tenir un
>   grand écart facial 3×30 s après échauffement, filmer et noter l'écart au
>   sol » est bon.
> - Les étapes sont **ordonnées** : la première doit être démarrable ce soir,
>   sans rien attendre.
> - **Une seule étape en cours** au maximum.
> - Entre 4 et 12 étapes pour le bloc en cours. S'il en demande plus, c'est qu'il
>   fallait le couper en deux blocs.
> - Comment ce projet **prouve** qu'on a travaillé dessus. C'est un vrai choix, pose-moi la question si ce n'est pas évident. Quatre valeurs possibles pour `Vérification` :
>   - `git` — des commits pendant la session. Le plus fort. Exige `Dépôt` : le chemin local du dépôt.
>   - `fichiers` — des fichiers du dossier ont été modifiés. Pour ce qui ne se commite pas : assets, maquettes, notes. Exige `Dépôt` aussi.
>   - `premier_plan` — l'application était au premier plan. Le plus faible : être devant un éditeur n'est pas travailler.
>   - `manuelle` — aucune preuve automatique, et c'est assumé. Choisis-la franchement plutôt que d'annoncer `git` sur un projet qui ne commite jamais.
>
> Quand tout est clair, rends-moi **uniquement** un bloc markdown à ce format,
> sans commentaire autour :
>
> ```markdown
> # Nom du projet
>
> Domaine: savoir
> Vérification: git
> Dépôt: ~/labs-cyber
> Branche: cyber
> Couleur: #4FC4B4
> Emblème: ◈
> Engagement: 3
> Objectif: Compromettre une machine Easy inconnue en moins de 3 h sans aide.
> Cadre: Articles 323-1 et suivants — lab local ou autorisation écrite uniquement.
>
> ## Parcours
>
> - Bloc A — Fondamentaux
>   Résultat: ligne de commande et réseau acquis
>   Ressource: OverTheWire Bandit
>   Adresse: https://overthewire.org/wargames/bandit/
>   Charge: 25–40 h
>   Sortie: niveau 34 terminé, et j'explique find et xargs sans notes
> - Bloc B — Sécurité web
>   Résultat: les six familles de failles web
>   Ressource: PortSwigger Web Security Academy
>   Adresse: https://portswigger.net/web-security
>   Charge: 200–280 h
>   Sortie: 100 % des labs Apprentice et Practitioner validés
>
> ## Roadmap
>
> - [>] Terminer les niveaux 0 à 10 de Bandit (3)
>   Ressource: OverTheWire Bandit
>   Adresse: https://overthewire.org/wargames/bandit/
>   Périmètre: niveaux 0 à 10 seulement, dans l'ordre
>   Charge: 6–8 h
>   Sortie: niveau 10 atteint sans avoir ouvert un writeup
> - [ ] Créer le dépôt ~/labs-cyber avec un writeup.md type (1)
> - [ ] Terminer les niveaux 11 à 20 de Bandit (3)
> - [ ] Écrire trois scripts bash utiles et les commiter (2)
>
> ## Écartées
>
> - TryHackMe
>   Raison: redondant avec HTB, et le tier gratuit est bridé
> - Linux Journey
>   Raison: redondant avec Bandit
> ```
>
> Règles de format : `[ ]` à faire, `[>]` en cours, `[x]` fait. Le nombre entre
> parenthèses est l'estimation en sessions de 25 minutes. Les lignes `Clé: valeur`
> **indentées sous une puce** appartiennent à cette puce ; celles en colonne zéro,
> en haut du document, décrivent le projet. Toutes sont facultatives : une étape
> qui n'a ni ressource ni charge — « appeler le plombier » — s'écrit toute seule.
>
> `Domaine` est un parmi `code`, `corps`, `creatif`, `savoir`, `pratique`. Il sert
> à garder mes trois projets actifs variés : je ne peux pas avoir plus de deux
> projets du même domaine en même temps. Demande-le-moi si ce n'est pas évident.
>
> `Branche` est une parmi `moteur_de_jeu`, `backend`, `data_rl`, `web`, `cyber`,
> `corps`, `savoir`, `artisanat`, `scene`. Les trois dernières couvrent
> respectivement les cursus et les langues, la cuisine et le travail manuel, la
> danse et la musique. `Engagement` est le nombre de sessions visées par semaine,
> entre 1 et 7.
>
> Omets la ligne `Dépôt` si la vérification est `premier_plan` ou `manuelle`, et
> la ligne `Cadre` si le sujet n'a rien de sensible.

---

## Ce que l'app fait du markdown

L'écran de confirmation te montre ce qu'elle a compris **avant** d'écrire quoi
que ce soit, avec les avertissements :

- une étape estimée à plus de 3 sessions est signalée « à découper » ;
- plusieurs étapes « en cours » sont signalées ;
- une roadmap entièrement faite est signalée — un projet actif doit garder une
  étape ouverte (§4.5) ;
- **une vérification annoncée sans les moyens de la faire** — `git` sans dépôt —
  est signalée immédiatement. Un projet qui se croit vérifié sans l'être est
  pire qu'un projet en déclaration manuelle assumée.

Aucun de ces avertissements ne bloque la création. Ils se montrent, tu décides.

**Slots.** Si un slot compatible est libre, le projet y atterrit et devient
actif. Deux limites dures s'appliquent (§4.3) : trois projets actifs au maximum,
et **deux slots au maximum par domaine** — trois projets de code dans les trois
slots, c'est une seule vie déguisée en trois. Sinon, le projet part **au frigo** :
la limite ne se contourne pas, mais l'idée ne se perd pas. L'échange de slot
reste un geste du dimanche.

**Le format est stable.** Le jour où la couche IA du §5.6 existera, la
conversation se fera dans l'app et produira exactement ce même markdown, lu par
le même parseur (`forge/rules/roadmap_import.py`). Rien de ce que tu écris
aujourd'hui n'est à refaire.
