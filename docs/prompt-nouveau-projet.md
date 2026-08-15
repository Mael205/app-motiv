# Créer un projet — le prompt à coller dans un chat

Le coach n'a pas encore sa couche IA (SPEC §5.6). En attendant, l'interrogation
qui produit une bonne roadmap se fait dans un chat, et le résultat se colle dans
l'app : **Projets → Nouveau projet → coller → confirmer**.

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
> Contraintes non négociables sur le résultat :
>
> - Chaque étape doit tenir en **3 sessions de 25 minutes maximum**. Au-delà,
>   découpe-la. Une étape à 5 sessions est un défaut, pas une étape.
> - Chaque étape doit être **exécutable sans réfléchir** : un verbe, un objet
>   précis, et si possible le fichier ou l'écran concerné. « Avancer sur l'API »
>   est refusé. « Écrire l'endpoint POST /recettes et son test » est bon.
> - Les étapes sont **ordonnées** : la première doit être démarrable ce soir,
>   sans rien attendre.
> - **Une seule étape en cours** au maximum.
> - Entre 4 et 12 étapes. Si le projet en demande plus, c'est qu'il faut le
>   réduire à un premier jalon livrable.
>
> Quand tout est clair, rends-moi **uniquement** un bloc markdown à ce format,
> sans commentaire autour :
>
> ```markdown
> # Nom du projet
>
> Branche: backend
> Couleur: #4FC4B4
> Emblème: ◈
> Engagement: 3
>
> ## Roadmap
>
> - [x] Une étape déjà faite (2)
> - [>] L'étape en cours (2)
> - [ ] La suivante (3)
> - [ ] Celle d'après (1)
> ```
>
> Règles de format : `[ ]` à faire, `[>]` en cours, `[x]` fait. Le nombre entre
> parenthèses est l'estimation en sessions de 25 minutes. `Branche` est une
> parmi `moteur_de_jeu`, `backend`, `data_rl`, `web`, `cyber`, `corps`.
> `Engagement` est le nombre de sessions visées par semaine, entre 1 et 7.

---

## Ce que l'app fait du markdown

L'écran de confirmation te montre ce qu'elle a compris **avant** d'écrire quoi
que ce soit, avec les avertissements :

- une étape estimée à plus de 3 sessions est signalée « à découper » ;
- plusieurs étapes « en cours » sont signalées ;
- une roadmap entièrement faite est signalée — un projet actif doit garder une
  étape ouverte (§4.5).

Aucun de ces avertissements ne bloque la création. Ils se montrent, tu décides.

**Slots.** Si un des trois slots est libre, le projet y atterrit et devient
actif. Si les trois sont pris, il part **au frigo** — la limite du §4.3 ne se
contourne pas, mais l'idée ne se perd pas. L'échange de slot reste un geste du
dimanche.

**Le format est stable.** Le jour où la couche IA du §5.6 existera, la
conversation se fera dans l'app et produira exactement ce même markdown, lu par
le même parseur (`forge/rules/roadmap_import.py`). Rien de ce que tu écris
aujourd'hui n'est à refaire.
