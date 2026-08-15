# Vérification automatique — les options, projet par projet

Le §6 veut un streak crédible à ses propres yeux. Une session déclarée sans
aucune trace rend le compteur décoratif, et un compteur décoratif ne tient
personne.

Ce document liste, pour chaque projet et chaque habitude réels, ce qui est
**automatisable aujourd'hui**, ce qui demande du travail, et ce qui n'a pas de
solution honnête. Trois choses sont vraies partout :

- une détection **marque**, une absence de détection **ne certifie rien**
  (§11.10) ;
- aucune preuve n'invalide jamais une session (§6) ;
- la catégorisation se fait sur l'appareil, jamais sur le serveur.

Légende : ✅ prêt · 🔨 à coder · ⛔ pas de solution honnête.

---

## Les projets

| Projet | Moyen | État | Ce que ça vaut |
|---|---|---|---|
| Prototype UE5 | `git` sur le dépôt | ✅ | Fort, si tu commites. Les `.uasset` binaires passent très bien en commit. |
| | `fichiers` sur `Content/` | ✅ | Meilleur pour du level design : tu modifies des assets sans commiter à chaque session. |
| Outils Dofus 3 | `git` | ✅ | Rien à ajouter, c'est le cas idéal. |
| Bot Slay the Spire 2 | `git` | ✅ | Idem. |
| | runs d'entraînement | ✅ | Un checkpoint PPO écrit pendant la session est une preuve plus juste qu'un commit : l'entraînement tourne sans qu'on commite. Se ramène à `fichiers` sur le dossier de checkpoints. |
| Développement du coach | `git` | ✅ | Déjà déclaré, dépôt `C:\Dev\app-motiv`. |
| App Django préfecture | `git` | ✅ | Si le dépôt est local. S'il est sur une machine du travail, `manuelle` assumée. |
| Roadmap cybersécurité | `fichiers` sur les notes | ✅ | Apprendre ne produit pas de commit. Un dossier de notes modifié est la trace la plus proche du réel. |
| | `premier_plan` | 🔨 | Faible mais disponible : TryHackMe ou la doc au premier plan. Déclarable, mais pas encore rattaché à une session — voir le point 4 de l'ordre recommandé. |
| Musculation | voir plus bas | | |

### Ce qu'il reste à coder pour les projets

**`fichiers` — fait.** Le scan parcourt le dossier déclaré et remonte les
fichiers dont la date de modification tombe dans la fenêtre de session. Les
sorties de build sont **élaguées à la descente**, pas filtrées après : `.git/`,
`node_modules/`, `.venv/`, et côté Unreal `Binaries/`, `Intermediate/`,
`DerivedDataCache/`, `Saved/`.

Mesuré sur `C:\Dev\app-motiv` : 136 fichiers visités au lieu de plusieurs
dizaines de milliers. Le scan reste sous la seconde.

La preuve affiche un échantillon lisible mais compte le total réel — les
confondre ferait afficher « 40 fichiers » sur une session qui en a touché six
cents, et une preuve qui sous-estime le travail est un bug.

**`premier_plan`** — les signaux d'ActivityWatch arrivent déjà, mais ils ne sont
pas encore rattachés à une session précise. Il manque le calcul « pourcentage de
la session où l'application déclarée était devant », c'est-à-dire la *qualité de
session* du §6.

---

## La musculation

C'est le cas le plus difficile, et j'ai changé d'avis en le regardant de près.
Détecter *l'entraînement* n'est pas faisable proprement. Détecter *le fait d'y
être allé* l'est très bien.

| Option | État | Remarque |
|---|---|---|
| Géorepérage MacroDroid sur la salle | ✅ recette | Déclencheur « entrée dans une zone », action HTTP vers `/api/signals` avec `sport`. Marche ce soir, aucun code. **La meilleure option si tu vas en salle.** |
| Appairage Bluetooth | 🔨 recette | Déclencheur « écouteurs connectés » + contrainte horaire. Utile si tu t'entraînes chez toi. Faible : tu peux les mettre pour autre chose. |
| Health Connect | 🔨 natif | Le vrai signal — séances, fréquence cardiaque. Exige la sonde Android native du §9.2. |
| Strava | 🔨 API | OAuth + webhook. Propre, mais seulement si tu y enregistres tes séances. |
| Détection de mouvement seule | ⛔ | Un accéléromètre ne distingue pas une séance d'un trajet en bus. Un faux positif sur une piste où tu comptes des séances est pire que rien. |

**Recommandation :** géorepérage si tu vas en salle, sinon `manuelle` assumée en
attendant Health Connect. Une coche honnête vaut mieux qu'une détection qui se
trompe une fois sur trois.

---

## Les routines d'entretien

Skincare et étirements durent trois minutes, à la maison, sans appareil
impliqué. Il n'y a rien à mesurer.

| Option | État | Remarque |
|---|---|---|
| Tag NFC collé sur le miroir | 🔨 recette | Un pack de tags coûte quelques euros. Tu poses le téléphone dessus, MacroDroid envoie le signal. Une seconde, pas d'app à ouvrir, et impossible à déclencher par accident. **La meilleure option.** |
| Brosse à dents connectée | 🔨 | Marche pour le soir si la tienne remonte quelque chose. Anecdotique. |
| Rien, coche manuelle | ✅ | C'est déjà un tap dans le panneau du soir. Le coût est presque nul. |

**Recommandation :** un tag NFC pour le skincare du soir si tu veux vraiment
supprimer la friction, manuel pour le reste. Automatiser une action d'un tap par
une action d'un tap n'a pas d'intérêt.

---

## Les gardes

| Garde | Option | État |
|---|---|---|
| Réseaux sociaux | Extension navigateur (web) | ✅ |
| | Agent PC via ActivityWatch | ✅ |
| | MacroDroid « app lancée » (mobile) | 🔨 recette |
| Scroll passif | Identique aux réseaux | ✅ |
| Porno | Extension navigateur, liste locale à remplir | ✅ |
| | **DNS filtrant, tous appareils** | 🔨 |

### Le DNS filtrant, l'option qui règle l'angle mort

L'extension ne voit qu'un navigateur, l'agent ne voit que le PC, MacroDroid ne
voit que les applications. Aucun ne voit un autre navigateur, un autre appareil
ou une navigation privée.

Un résolveur DNS de type **NextDNS** voit tout ce qui passe par le réseau, sur
tous les appareils, y compris en navigation privée. Il classe déjà les domaines
par catégorie et expose une API d'analytique.

Un poller dans `coach-agent` lirait les **compteurs par catégorie** — jamais la
liste des domaines — et posterait des signaux. C'est de loin le meilleur rapport
couverture / effort du lot, et c'est le seul moyen d'éteindre l'angle mort du
téléphone sans écrire d'application Android.

À peser franchement : cela veut dire faire passer ton DNS par un tiers. Le
compromis est réel, et il n'est pas neutre. C'est ton appel.

---

## Ordre recommandé

1. ~~**`fichiers`**~~ — fait. Débloque la roadmap cyber, les assets UE5 et les
   checkpoints RL.
2. ~~**Géorepérage muscu**~~ — recette écrite, voir `coach-mobile/README.md`.
3. **DNS filtrant** — la seule option qui couvre le téléphone sans app native.
   **Demande ton arbitrage** : cela fait passer ton DNS par un tiers.
4. **Qualité de session** — rattacher les signaux à une session. Bloqué par le
   modèle : un `Signal` porte une journée, pas un intervalle. Il faudra lui
   ajouter une fenêtre avant que `premier_plan` puisse fonctionner.
5. **Sonde Android native** — le plus long, à ne faire que si le DNS ne suffit
   pas.
