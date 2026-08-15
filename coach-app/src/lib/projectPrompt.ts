/** Le prompt d'interrogation pour créer un projet (SPEC §4.5).
 *
 * Il vit dans l'app et pas seulement dans `docs/`, parce qu'on en a besoin sur
 * le téléphone, au moment où l'envie de nouveau projet arrive — pas devant le
 * dépôt. Un tap le copie, on le colle dans un chat.
 *
 * Les contraintes qu'il porte ne sont pas décoratives : sans elles un chat rend
 * « avancer sur le backend », qui ne se démarre pas un mardi à 21h.
 */
export const PROJECT_PROMPT = `Tu m'aides à découper un projet en roadmap pour mon système de discipline personnel. Interroge-moi d'abord, une question à la fois, jusqu'à ce que tu puisses écrire des étapes concrètes. Ne me propose pas de roadmap avant d'avoir compris ce que je veux construire, où j'en suis déjà, et ce qui est déjà fait.

Contraintes non négociables sur le résultat :

- Chaque étape doit tenir en 3 sessions de 25 minutes maximum. Au-delà, découpe-la. Une étape à 5 sessions est un défaut, pas une étape.
- Chaque étape doit être exécutable sans réfléchir : un verbe, un objet précis, et si possible le fichier ou l'écran concerné. « Avancer sur l'API » est refusé. « Écrire l'endpoint POST /recettes et son test » est bon.
- Les étapes sont ordonnées : la première doit être démarrable ce soir, sans rien attendre.
- Une seule étape en cours au maximum.
- Entre 4 et 12 étapes. Si le projet en demande plus, réduis-le à un premier jalon livrable.
- Comment ce projet prouve qu'on a travaillé dessus. C'est un vrai choix, pose-moi la question si ce n'est pas évident. Quatre valeurs possibles pour Vérification :
  - git — des commits pendant la session. Le plus fort. Exige la ligne Dépôt : le chemin local du dépôt.
  - fichiers — des fichiers du dossier ont été modifiés. Pour ce qui ne se commite pas : assets, maquettes, notes. Exige la ligne Dépôt aussi.
  - premier_plan — l'application était au premier plan. Le plus faible : être devant un éditeur n'est pas travailler.
  - manuelle — aucune preuve automatique, et c'est assumé. Choisis-la franchement plutôt que d'annoncer git sur un projet qui ne commite jamais.

Quand tout est clair, rends-moi uniquement un bloc markdown à ce format, sans commentaire autour :

\`\`\`markdown
# Nom du projet

Domaine: code
Vérification: git
Dépôt: C:/Dev/mon-projet
Branche: backend
Couleur: #4FC4B4
Emblème: ◈
Engagement: 3

## Roadmap

- [x] Une étape déjà faite (2)
- [>] L'étape en cours (2)
- [ ] La suivante (3)
- [ ] Celle d'après (1)
\`\`\`

Règles de format : [ ] à faire, [>] en cours, [x] fait. Le nombre entre parenthèses est l'estimation en sessions de 25 minutes.

Domaine est un parmi : code, corps, creatif, savoir, pratique. Il sert à garder mes trois projets actifs variés — je ne peux pas avoir plus de deux projets du même domaine en même temps. Demande-le-moi si ce n'est pas évident.

Branche est une parmi : moteur_de_jeu, backend, data_rl, web, cyber, corps. Engagement est le nombre de sessions visées par semaine, entre 1 et 7.

Omets la ligne Dépôt si la vérification est premier_plan ou manuelle.`
