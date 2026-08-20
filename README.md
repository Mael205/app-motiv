# Coach

Système de discipline personnel. Le cadre, pas les encouragements.

La spécification complète est dans [SPEC_COACH.md](SPEC_COACH.md) — elle fait autorité
sur le code. Toute mécanique retirée doit être vérifiée contre la table de
traçabilité du §15 avant suppression.

L'inventaire de ce qui existe et de ce qui reste est dans
[docs/etat-des-lieux.md](docs/etat-des-lieux.md), et l'installation sur PC et
téléphone dans [docs/installer.md](docs/installer.md).

## Composants

| Dossier | Rôle | État |
|---|---|---|
| `coach-api/` | Django 5 + DRF — source de vérité, logique métier | **J0/J1 en cours** |
| `coach-app/` | React + Vite, PWA installable — PC et mobile | **J0/J1 en cours** |
| `coach-agent/` | Python, Windows — lancement, sessions fantômes, sondes | **J4 fait** |
| `coach-ext/` | Extension navigateur — sonde web par domaine | **signée, permanente** |
| `coach-mobile/` | Sonde Android — temps d'écran | recette MacroDroid + natif à bâtir |

## Démarrer en local

Deux terminaux, moins de cinq minutes.

### 1. L'API

```bash
cd coach-api
python -m venv .venv
.venv/Scripts/pip install django djangorestframework django-cors-headers \
    djangorestframework-simplejwt python-dotenv dj-database-url pytest pytest-django
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py seed          # projets réels + saison ouverte
.venv/Scripts/python manage.py runserver
```

L'API écoute sur `http://127.0.0.1:8000`. Le seed crée l'utilisateur `arthur` /
mot de passe `coach`.

SQLite par défaut pour tenir la promesse des cinq minutes. En production,
`DATABASE_URL` pointe sur le Postgres managé et rien d'autre ne change.

### 2. Le front

```bash
cd coach-app
npm install
npm run dev
```

L'interface est sur `http://localhost:5173`, et proxifie `/api` vers Django.

### 3. L'assistant — facultatif

Rien à faire si le CLI `claude` est déjà installé et connecté : le coach le
détecte et passe par lui, donc par l'abonnement. Sinon :

```bash
npm install -g @anthropic-ai/claude-code
claude          # ouvre la connexion, puis quitte avec /exit
```

Pour vérifier, ouvre l'accueil : le bloc de décision se recharge après quelques
secondes et affiche « Décidé pour ce soir » au lieu de « Ton amorce ».

Deux réglages, tous deux facultatifs :

| Variable | Défaut | Effet |
|---|---|---|
| `COACH_AI_ENABLED` | `1` | `0` coupe l'IA. L'app reste entière — c'est le but du test. |
| `COACH_AI_BACKEND` | `auto` | `cli` impose l'abonnement, `api` impose `ANTHROPIC_API_KEY`. |

**Sans rien de tout ça, l'app fonctionne.** Chaque appel de modèle a un repli
déterministe, et l'accueil s'affiche à la même vitesse qu'avant : le briefing
part en fond une fois l'écran déjà utilisable, et ne remplace la proposition que
s'il arrive et passe la porte de qualité.

Deux exceptions assumées, sans repli : l'entretien de projet, et l'assistant.
Aucun algorithme ne sait interroger quelqu'un sur son projet, ni comprendre
« fusionne mes deux routines du matin ». Quand le modèle manque, les deux
écrans le disent et renvoient vers les chemins manuels, qui font la même chose.

### L'année, et l'ascendance

Douze saisons de trente jours font une année du coach. Chaque identité de saison
sort exactement une fois par an, chaque boss aussi, dans un ordre qui change
d'une année à l'autre.

À la douzième clôture, l'**ascendance** : l'XP, le niveau et le rang repartent
de zéro, et une **voie** se choisit parmi six — un slot de plus, un plancher
plus haut payé en Éclats, le fantôme nommé, cinq modificateurs au lieu de trois,
le contrat annuel, ou la Forge.

Deux choses à savoir, parce que ce sont les deux questions qu'on se pose :

- **rien n'est effacé.** Les resets déplacent un horizon de lecture — l'XP se
  compte depuis l'ascendance, les semaines tenues aussi. Aucune session, aucune
  semaine ne disparaît, et la trace longue garde le cumul de toujours ;
- **les slots acquis sont gravés.** Le rang les reprendrait en repartant de F,
  et le §4.3 l'interdit : un rang remis à zéro qui retirerait deux slots
  gèlerait deux projets en cours du jour au lendemain.

Une voie ouvre une mécanique, une capacité ou un choix — jamais de la puissance.
La **Forge** est la plus nette : elle permet de fabriquer une carte précise
contre des Éclats, à six fois ce qu'un doublon rapporte. Elle répond à un défaut
qui ne se voyait qu'au bout de plusieurs mois — les Éclats ne se dépensaient
nulle part, et une monnaie qui ne descend jamais est un compteur.

### L'assistant, et ce qu'il a le droit de faire

Le bouton ✦ ouvre un fil où l'on demande des choses en français. L'assistant y
répond par des **actions proposées** — trente-deux verbes, listés dans
`coach-api/forge/rules/actions.py` — chacune affichée avec son avant/après et
son bouton. Trois murs le bornent :

- **le catalogue est fermé.** La clé d'action est une énumération dans le
  schéma envoyé au modèle : il ne peut pas nommer un verbe qui n'existe pas.
  Pas « il ne devrait pas » — il ne peut pas ;
- **rien ne s'écrit sans un geste.** Un tour de conversation ne modifie jamais
  la base, quoi que réponde le modèle. Une carte, un bouton, une écriture —
  il n'y a pas de « tout appliquer » ;
- **aucun verbe ne fabrique du travail.** Ni session, ni XP, ni Éclats, ni
  boucliers, ni journée validée. Un test relit le catalogue et le prouve.

Chaque action passe par le service qui existe déjà : baisser un engagement
appelle la règle du §4.3, terminer une étape appelle le même code que le
bouton de la roadmap. L'assistant ne peut rien faire qu'on ne puisse déjà
faire à la main — c'est la seule raison pour laquelle il est sûr.

## Tests

```bash
cd coach-api && .venv/Scripts/python -m pytest      # 1008 tests, l'API
.venv/Scripts/python -m pytest ../coach-agent        # 42 tests, la sonde PC
cd ../coach-app && npm test                          # 21 tests, le front
```

La suite entière tourne en **20 secondes**. Elle en demandait 440 jusqu'au
19 août, et la cause n'était pas le code testé : Django 5 hache les mots de
passe en PBKDF2 à 1,2 million d'itérations — 0,89 seconde par appel sur cette
machine — et presque chaque test crée un utilisateur dans sa fixture. La suite
passait donc l'essentiel de son temps à prouver qu'un mot de passe de test est
bien haché. `forge/tests/conftest.py` bascule sur MD5 le temps de la session,
et rien d'autre n'a changé. Une suite qui prend sept minutes n'est plus lancée
avant de commiter, ce qui coûte beaucoup plus cher que ce qu'elle protège.

1071 tests couvrent ce qu'un bug détruirait en premier : l'évaluation du streak et
des boucliers dans ses trois états de journée, la bascule de journée à 4h, le
calcul d'XP avec sa dégressivité, les saisons, le parcours complet d'une session,
la lecture du markdown de création de projet, les deux limites dures de
l'attribution de slot, et la preuve de travail lue dans git.

Plusieurs gardent des promesses plutôt que des calculs, et ce sont peut-être les
plus importants : aucun compteur d'Entretien ne redescend, aucune routine ne
rapporte d'XP, aucun message de dépassement d'une garde ne contient un mot de
jugement, et **aucune sonde ne peut déclarer une journée tenue**. Ces règles-là
se perdent au premier refactoring si personne ne les surveille.

Les tests du §14 sont écrits sur le même principe, et un seul y vérifie un
barème : les autres exigent qu'une session dégradée éteigne **tout** ce qui est
réparable, que le palier 3 n'ajoute rien à ce que le palier 2 avait déjà pris,
qu'aucun mot de reproche n'entre dans un texte affiché, et que relire l'accueil
cinq fois de suite laisse le boss et les Éclats identiques. C'est la mécanique
qui dérive le plus facilement — chaque sanction ajoutée paraît justifiée prise
seule, et l'empilement produit le mode de défaillance n°1 du §0.3.

Les tests du briefing suivent la même idée et un seul d'entre eux vérifie le cas
nominal : tous les autres coupent le modèle, le font halluciner un projet,
répondre en prose ou proposer deux options, et exigent qu'il reste **une action
décidée à l'écran**. C'est le chemin qu'on emprunte un soir de panne, et celui
qu'on n'essaie jamais à la main.

La logique vit dans `coach-api/forge/rules/`, sans aucun import Django, et n'est
dupliquée nulle part ailleurs — surtout pas côté client.

Les vingt et un tests du front (vitest, jsdom) ne dupliquent aucune règle métier :
ils gardent les deux seules choses que le client décide seul. D'abord la
séparation des accents — la saison peint `--accent`, la carte thème équipée peint
`--perso`, et l'un ne prend jamais la place de l'autre. Ce test-là existe parce
que la première version du repli était écrite en CSS, qu'elle passait `tsc` et le
lint, et qu'elle était fausse : `--perso: var(--accent)` déclaré sur `:root` se
résout contre l'or par défaut et non contre la saison, puisque l'accent de saison
est posé en style inline sur le `<body>`. Seule une capture d'écran l'a montré.

Ensuite les règles de verdict des outils de `tools/`, sorties dans
`tools/verdict.cjs` pour être testables sans navigateur. Le cas vérifié n'est pas
celui qui passe, c'est celui qui **échoue** : un débordement, un bouton sous la
ligne de flottaison, une séquence muette. C'était le seul des deux qui n'avait
jamais été essayé.

## Ce qui est déjà là

- Streak, boucliers, trois états de journée, règle « jamais deux fois d'affilée »,
  reprise après décrochage qui rend un bouclier.
- **Plancher progressif (§4.1)** : la session normale suit le rang — 25 min de F
  à C, 30 au rang B, 35 au rang A, plafond à 35 —, tandis que le **mode dégradé
  reste à 10 minutes pour toujours**. Il y a deux seuils et un seul monte :
  l'exigence, jamais l'issue de secours. Un plancher qui monterait partout
  fermerait la porte exactement le soir où l'on rentre à 22h, c'est-à-dire le
  soir qui décide du streak. Indexé sur le rang et jamais sur l'XP (§4.4) :
  l'XP monte avec le volume, donc un plancher indexé dessus en demanderait plus
  à quelqu'un précisément parce qu'il vient de forcer.
- Bascule de journée à 4h, fenêtre du soir paramétrable par jour de semaine.
- XP avec bonus de première session, bonus avant 20h, multiplicateurs de streak
  et de momentum, **et le plafond de régime** qui éteint la récompense au-delà de
  trois sessions par jour.
- **La durée annoncée est un objectif, pas un plafond (§4.1).** Une séance compte
  ce qu'elle a duré et se clôture **à tout moment** — avant le terme, après, bien
  après. Auparavant les minutes étaient rognées à la durée prévue : quarante
  minutes sur un minuteur de vingt-cinq en perdaient quinze, en silence, ce qui
  faisait de la clôture le seul endroit du produit où du travail réel
  disparaissait. Le minuteur garde trois rôles : il porte la promesse faite au
  démarrage et la clôture dit si elle a été tenue, il sert de repère à la
  détection de session fantôme (§8.7), et le bouton **« +15 minutes »** le
  *rehausse* au lieu de l'effacer. Un garde-fou dur à quatre heures empêche une
  séance oubliée toute la nuit de créditer une nuit de travail.
- **Une séance longue vaut plus que la même durée coupée en deux.** Les minutes
  au-delà de 25 comptent une fois et demie, celles au-delà de 45 une fois trois
  quarts, et la prime s'arrête là. Le calibrage a un critère, pas un goût :
  couper une soirée en deux paie **deux fois** les forfaits — première session,
  avant 20h —, donc une prime plus faible que ce que le fractionnement duplique
  ferait dire à la règle le contraire de ce qu'elle annonce ; un test tient cette
  propriété. Le plafond de régime n'est pas touché : il compte des sessions, et
  prolonger n'en ajoute pas une.
- **L'heure annoncée pèse (§11.2).** Corollaire de ce qui précède : une séance
  comptant à n'importe quelle heure, un rendez-vous que personne ne constate
  n'est plus un rendez-vous. La **prime de ponctualité** remplace le forfait
  « avant 20h » — elle paie le créneau tenu à la demi-heure près, à n'importe
  quelle heure, là où l'ancienne payait l'horloge et ne pouvait jamais toucher
  un créneau de 21h. Le **gardien de créneau** constate vingt minutes après :
  « 20h30 est passé, rien de lancé », avec la tâche et les deux boutons du
  §11.7. **Aucun malus** dans l'un ni dans l'autre : sans créneau déclaré il n'y
  a rien à tenir, et travailler hors rendez-vous ne coûte rien — c'est l'absence
  de promesse, pas un échec.
- Niveaux, rangs F→SS, saisons de 4 semaines avec identité tirée d'un réservoir
  de **vingt-quatre identités et vingt-quatre boss** — deux ans avant qu'un nom
  revienne, là où douze faisaient de la deuxième année une rotation de la
  première —, boss dont la vie descend avec le travail réel, hauts faits.
- Piste Entretien : routines courtes ancrées sur un geste, mesurées à la semaine,
  sans streak cassable, payées en Éclats et jamais en XP (§11.9).
- **Habitudes horaires** : une routine peut porter une fenêtre — « debout avant
  7h30 », « au lit avant 23h30 ». Hors fenêtre, la coche est **gardée et ne
  compte pas** : ni semaine, ni Éclats. Le §11.9 ancre les routines sur un geste
  et pas sur une horloge, et il a raison — mais deux habitudes échappent à la
  règle parce que l'heure *est* l'habitude. La comparaison se fait en minutes
  depuis la bascule de journée, seule façon correcte : une coche « au lit » à
  00h20 est **tard** dans la journée d'hier, pas tôt dans celle d'aujourd'hui.
  Les sondes **cochent même toutes seules** quand elles ont la preuve : une
  activité observée à 7h05 vaut mieux qu'un tap, qu'on peut faire en se
  recouchant. Elles ne cochent jamais sur un silence, ne décochent jamais, et
  attendent la bascule de 4h pour juger un coucher — avant, l'absence
  d'activité après 23h30 ne prouve rien, il est 22h. Elles **corroborent ou
  contredisent** sinon, sans jamais rien retirer ni rien payer : le §6 interdit qu'une preuve d'activité invalide une
  déclaration, et un PC resté allumé la nuit suffirait à produire une fausse
  accusation. Le constat est affiché comme un fait, sans adjectif.
- **La capacité, troisième axe (§4.4 étendu)** : l'XP mesure le volume, le rang
  mesure la fiabilité, et ni l'un ni l'autre ne dit qu'on est devenu meilleur —
  quarante heures de mauvaise pratique donnent le même titre d'arbre que
  quarante heures de bonne. Une **preuve** est un fait daté, binaire et
  constatable par quelqu'un d'autre : « les 100 % de labs Apprentice validés »,
  pas « j'ai progressé ». Elle vient du critère de sortie d'un bloc de parcours,
  écrit **à froid** des mois avant d'être atteint — la seule façon de ne pas
  déplacer la barre après coup. Elle paie en Éclats et jamais en XP : une
  capacité n'est pas un volume. Preuves et heures s'affichent côte à côte et ne
  fusionnent jamais.
- **La difficulté ressentie**, déclarée au debrief en un tap. Elle n'entre dans
  **aucun** calcul, et c'est ce qui permet d'y répondre honnêtement. Trois
  sessions d'affilée « trop facile » déclenchent le seul constat du système
  provoqué par une bonne nouvelle apparente : sur tous les autres compteurs,
  c'est une belle série ; en réalité, on a cessé d'apprendre.
- **Ponctuel** : les choses à faire une fois — commander, appeler, poster. Ni
  XP, ni Éclats, ni coche, ni streak, et **jamais sur l'écran du soir**. La
  saisie tient en un champ : l'échéance est repliée derrière trois raccourcis,
  le focus reste après validation, et la liste se groupe — en retard,
  aujourd'hui, plus tard, sans date. Ce qui est devenu plus rapide, c'est
  d'écrire ; ce qui n'a **pas** été rendu plus satisfaisant, c'est de cocher —
  pas de vert, pas d'animation, pas de son. Une course cochée ne doit jamais
  ressembler à une session faite. Le §0
  refuse la todo-list, et cette liste n'en devient une que si on lui donne de la
  valeur : elle n'en a aucune, par construction et par test. Elle existe pour la
  raison inverse — une course qu'on garde en tête occupe la place d'une session.
- **Un plan de travail, pas une liste de tâches (§4.5)** : un projet porte son
  objectif — sa condition de fin —, son cadre, son **parcours** en blocs de
  plusieurs mois, les ressources **écartées** avec leur raison, et cinq attributs
  par étape : ressource, adresse, périmètre, charge, **critère de sortie**. Ce
  dernier remonte jusqu'à la décision du soir : « fini quand » s'affiche avant
  de démarrer, même sans modèle. Une étape qui dit « réviser le réseau » sans
  ressource ni critère est une intention, et le soir venu elle demande de décider
  quoi faire — ce que le §4.5 refuse.
- **Entretien de projet dans l'app (§4.5)** : le coach interroge une question à
  la fois, puis rend le projet en **champs structurés** que le serveur met en
  forme. Ce dernier point vient d'un vrai raté — un modèle à qui l'on demande ce
  markdown produit régulièrement un document plus agréable à lire et
  inexploitable, où le parseur perd la vérification `git` et le chemin du dépôt
  **sans rien signaler**. Trois tours de reproche n'y ont rien changé ; laisser
  le serveur écrire le format le rend juste par construction.
- Le collage de markdown reste, en second : il marche sans IA, sert quand une
  roadmap existe déjà, et passe par le même parseur. Le prompt est embarqué dans
  l'app et documenté dans
  [docs/prompt-nouveau-projet.md](docs/prompt-nouveau-projet.md).
- **Deux axes séparés** (§4.4) : l'XP mesure le volume et ne paie qu'en loot,
  dégâts au boss et Éclats ; le **rang** mesure la fiabilité — les semaines où
  tous les engagements ont été tenus — et lui seul ouvre des droits. Un système
  qui débloque sur l'XP récompenserait ce qui fait décrocher (§0.2).
- Slots : trois de base, deux au maximum par domaine, un 4ᵉ au rang B et un 5ᵉ
  au rang A. La piste Corps a ses deux slots, qui ne bougent jamais.
- Un projet terminé libère son slot le jour même ; les autres échanges attendent
  le dimanche, et un slot laissé vacant doit y être repris.
- Gardes : budget hebdomadaire au lieu d'une abstinence, cumul de jours tenus
  qui ne redescend jamais, aucun jugement dans les messages, et rien qui sorte
  de l'app (§11.10).
- Sondes : l'agent PC lit ActivityWatch et un **AdGuard Home auto-hébergé**
  (le seul point qui voit tous les appareils du réseau), l'extension mesure le
  web par domaine, et le téléphone passe par une recette MacroDroid. Toutes
  catégorisent **localement** et marquent les gardes détectées. Une détection
  marque, une absence de détection ne certifie rien.
- Jetons de sonde : longs, révocables, et limités au seul endpoint `/api/signals`.
  Un secret qui fuit d'une extension ne donne accès à rien d'autre.
- L'agent ouvre l'environnement d'un projet au démarrage d'une session, détecte
  les sessions fantômes et affiche les notifications en natif (§8). La liste de
  ce qu'il peut exécuter vit **chez lui**, jamais sur le serveur.
- **Briefing et debrief assistés (§5.1, §5.2)**, avec une architecture inversée :
  le serveur calcule d'abord sa proposition sans IA, puis demande au modèle s'il
  ferait mieux. Modèle absent, lent, ou réponse refusée par la porte de qualité
  — l'utilisateur voit la proposition déterministe et l'app ne ralentit pas.
  L'IA ne peut rien casser parce qu'elle n'est jamais le chemin principal.
- Deux backends derrière la même abstraction : le **CLI `claude`**, qui passe
  par l'abonnement déjà payé et que le coach choisit en premier, et le SDK pour
  les machines sans CLI. Le routage envoie le jugement à Opus et la
  transformation à Sonnet, et la **porte de qualité** refuse un briefing qui
  propose plusieurs pistes (§0.9) ou une tâche floue (§4.5).
- Preuve de travail sans saisie : chaque projet déclare **comment il se vérifie**
  à sa création (`git`, `fichiers`, `premier_plan`, `manuelle`), et un projet qui
  annonce `git` sans dépôt est signalé — se croire vérifié est pire qu'assumer
  le manuel. Les options par projet et par habitude sont dans
  [docs/verification.md](docs/verification.md). `git` et `fichiers` sont
  implémentés ; la preuve appliquée est celle que le projet a déclarée, jamais
  une autre. Les trois moyens automatiques — `git`, `fichiers`, `premier_plan` —
  sont implémentés.
- Proposition unique côté serveur : projet, durée, tâche. Aucun écran de choix.
- Amorce obligatoire à la clôture d'une session.
- **Le jeu (§12)** : arbre de compétences par branche — quarante heures
  dispersées sur trois projets de moteur de jeu restent quarante heures de
  moteur de jeu —, cartes de loot à quatre raretés avec pitié progressive,
  reliques gagnées par haut fait et plafonnées à trois, et une jauge de
  momentum qui **tiédit sans s'éteindre** : deux jours manqués pour effacer un
  jour fait, jamais l'inverse.
- **Ce qui déclenche un tirage, et sur quel mode.** Ce qui est rare se donne, ce
  qui est fréquent se tire : une étape terminée rend une carte garantie, une
  séance longue en rend une avec une probabilité qui monte avec les minutes
  (nulle sous 25 min, plafonnée à un quart). Et **l'effort incline le tirage sans
  l'acheter** : les heures posées sur une étape avant de la finir déplacent une
  part des poids vers le rare et l'épique, plafonnées à cinq heures — au-delà,
  une étape n'est plus longue, elle est bloquée, et le §13.5 a déjà un constat
  pour ça. Le déclencheur reste **terminer** : rien ne tombe pour avoir peiné
  sans finir.
- **Modificateurs de saison appliqués (§12.5)** : « Aube » paie le matin,
  « Marathon » paie les longues et ferme le mode dégradé, « Fragmentation »
  ouvre une quatrième session à plein tarif sans supprimer le plafond, « Siège »
  gonfle le boss et double la mise. Une clé inconnue reste neutre, et le neutre
  calcule exactement comme avant — ajouter la mécanique ne change pas les
  parties déjà jouées.
- **Une trame en deux voies (§12.2).** Les vingt-quatre identités de saison ne
  sont plus tirées au sort : elles forment une histoire, et c'est le résultat de
  la saison précédente qui décide de la voie — la **Voie des Cimes** après une
  saison tenue (L'Éveil, la faille, le méridien franchi, le sommet), la **Voie
  des Braises** après une ratée (Nadir, le purgatoire, le rempart, l'enclume).
  Chaque voie avance à son rythme : on reprend la basse là où on l'avait
  laissée, donc une année en dents de scie tricote les deux sans qu'aucun
  tirage n'intervienne. **La voie basse ne retire rien** — même mise, même boss,
  mêmes règles : le §17 interdit d'ajouter une sanction, et le décor n'est pas
  une punition. Le boss, lui, reste tiré : la trame dit ce qu'on traverse, pas
  qui l'on affronte.
- **Le boss abattu, et le mode extra (§12.4).** Tuer le boss clôt la saison le
  jour même : titre, mise résolue, cérémonie. La suivante est engagée aussitôt
  mais démarre à sa date prévue, et les jours entre les deux sont des **jours
  extra** — ce qu'on y pose est mis de côté pour elle. Un panneau le dit à
  l'accueil, parce qu'une récompense qu'on ne distingue pas d'une panne est une
  punition. La vie du boss suivant suit les **dégâts réellement infligés** et
  non les minutes seules : les étapes de roadmap valent soixante points, et
  mesurer en minutes faisait rétrécir le boss à chaque saison gagnée par
  l'avancement — l'inverse de ce que le ×1,05 promet.
- **Fantôme de saison (§12.7)** : deux courbes cumulées côte à côte, la tienne
  s'arrêtant aujourd'hui et celle du fantôme allant jusqu'au bout — on voit où
  l'adversaire *sera*. Comparé en minutes travaillées et non en XP : l'XP porte
  des multiplicateurs qui diffèrent d'une saison à l'autre, et comparer des XP
  reviendrait à comparer des règles plutôt que du travail.
- **La frontière du loot est tenue par des tests**, pas par une intention :
  aucune carte n'a d'effet, les cartes et les reliques ne partagent aucune
  table, et équiper un cosmétique ne peut toucher aucune session. Le §17 pose
  que récompenser la chance plutôt que le travail est le pire mode de
  défaillance ; sa disparition serait invisible, l'app marcherait encore.
- **Le prix du décrochage (§14)** : mode terne, vitrine fermée, sas révoqué,
  boss qui récupère 45 min de vie par jour raté, dette de 10 min, slot gagné
  gelé, titre en sursis, quart de la mise prélevé au streak cassé, et au
  troisième jour un **écran unique de reprise** — une tâche, dix minutes,
  aucun chiffre. Deux choix de fond y tiennent le reste :
  - Les deux écritures — régénération du boss et prélèvement sur la mise — sont
    **recalculées depuis l'historique** à chaque lecture, jamais incrémentées.
    Le streak l'est déjà, et un incrément posé par un déclencheur nocturne se
    doublerait au premier rejeu et disparaîtrait au premier cron manqué. Un
    test relit l'accueil cinq fois de suite et exige un boss identique.
  - Le palier 3 **n'ajoute aucune sanction** et n'énumère rien. Punir plus au
    troisième jour est le meilleur moyen de faire désinstaller ; la liste des
    lignes affichées est vide, pas adoucie.
- **Cycle de saison complet (§12.2, §7.4)** : clôture avec score en minutes,
  comparaison au fantôme, titre décerné — *Déserteur de Purgatoire* aussi
  franchement que *Vainqueur*, parce qu'une collection sans trous n'a aucune
  valeur — et résolution de la mise, seul endroit du système où quelque chose
  se perd. Puis l'ouverture enchaîne : trois modificateurs qui **annoncent leur
  prix** (vie du boss, multiplicateur de mise, mention « difficile »), trois
  fantômes avec leur total en heures, et la mise à engager.
- **Les quatre séquences de juice du §7 sont faites** — entrée en session, fin
  de session, passage de niveau, fin de saison — plus la mort du boss, ajoutée
  parce que c'est le seul événement d'une saison qui dépasse le passage de
  niveau en rareté. Secousse par trauma décroissant, compteurs à décélération
  marquée, gerbes en canvas, couronnes de rayons ; chaque temps court et
  passable d'un clic, et `prefers-reduced-motion` désactive l'animation sans
  jamais supprimer l'information. La grammaire commune est écrite dans
  [docs/direction-visuelle.md](docs/direction-visuelle.md).
- L'entrée en session **ne retarde rien** : la requête part au clic et la
  séquence couvre son attente. Le §7 l'exige — jamais d'animation sur le chemin
  critique.
- Interface : jauge du soir, fiche de personnage, barre de boss, écran de session
  avec sa séquence de fin, et un **HUD à trois colonnes** au-delà de 1160 px —
  la décision garde sa largeur de téléphone, donc sa dominance.
- **L'accueil ne montre plus que ce qui sert le soir.** La braise de momentum et
  l'arbre de compétences y étaient *en double* avec l'onglet Personnage ; le
  fantôme y garde une phrase et laisse sa courbe sur la fiche. Un doublon ne
  coûte pas que de la place : il enseigne que l'accueil est l'endroit où tout se
  consulte, ce qui est exactement ce que le §11.1 interdit.
- **Son des séquences, synthétisé et non enregistré** ([juice/sound.ts](coach-app/src/juice/sound.ts)).
  Aucun fichier audio dans le dépôt : les cinq sons descendent des mêmes
  oscillateurs et de la même enveloppe, donc ils s'entendent comme un seul
  instrument, là où quatre extraits d'une banque n'auraient pas formé une
  famille. Même règle que pour l'image : **seuls les moments du §7 sonnent**,
  aucun son de survol ni de navigation. La coupure est dans le bandeau, à côté
  du « ? », et elle survit au rechargement.
- **Chaque rareté de carte a sa propre chorégraphie.** Une commune glisse et se
  retourne en un demi-temps ; une légendaire charge, tremble, éclate et secoue
  l'écran. La gradation est celle du son : deux voix pour une commune, douze
  pour une légendaire. Une commune qui s'ouvrirait comme une légendaire
  dévaluerait la légendaire.

- **Le canal entrant est complet (§11.7).** Le bot Telegram de la spec a été
  remplacé par des **liens signés** : une adresse courte, un secret qui n'existe
  qu'à l'émission, un seul geste décidé à l'avance, aucune lecture de la base, et
  un second clic qui dit « déjà fait » plutôt qu'« erreur ». Cinq gestes —
  frigo, accusé de lecture d'un bilan, réponse à une question de revue, démarrer
  la séance proposée, reporter le gardien.
  - Le **gardien du soir porte deux boutons** : « Démarrer 10 min » et
    « Reporter 15 min ». Le service worker n'a aucun jeton — il ne partage ni le
    stockage local ni la session de l'app —, donc chaque bouton arrive avec son
    lien signé, qui expire avec la soirée. Le report est tenu par l'ordonnanceur
    du serveur, jamais par le worker qui dort bien avant l'échéance, et **ne part
    pas s'il arrive en retard**.
  - La **cible de partage Android** met le coach dans le menu « Partager » du
    téléphone. Ce qui y arrive va au frigo, jamais en projet — un projet coûte un
    slot (§4).
  - La PWA **s'abonne enfin au Web Push** : `pushKey` et `subscribePush`
    existaient et personne ne les appelait, donc le gardien ne partait que sur
    Discord. La permission se demande sur un geste, dans le journal ; l'abonnement
    se répare tout seul à chaque ouverture, parce qu'il expire de lui-même.
- **Le bilan quotidien a un écran (§13.1).** Une tuile paraît sur l'accueil avant
  l'ouverture de la fenêtre du soir, puis disparaît : le matin il n'y a rien à
  décider, donc le §11.1 n'est pas entamé. Elle ne demande rien, se referme d'un
  « vu » qui tient jusqu'au lendemain, et se tait les jours sans rien à dire — la
  règle du silence est calculée côté serveur, la même que celle de la
  notification de la nuit.
- **La revue du dimanche se répond depuis la notification (§5.3).** Une question
  part avec son fait daté et son lien signé ; la réponse atterrit dans la revue.
  Une seule question par lien : une notification porte une phrase, pas un
  questionnaire. Sans `public_base_url`, rien ne part — poser une question sans
  moyen d'y répondre n'ajoute qu'une chose à faire plus tard.
- **J6, le confort (§16)** : les **séries des douze dernières semaines** sur la
  fiche de personnage — par semaine, par soir, par heure de démarrage, par
  projet —, à distinguer de la trace longue qui ne rend que des compteurs
  incapables de baisser ; l'**export** JSON complet, qui contient tout le travail
  et **aucun secret** ; un catalogue de cartes porté à **cent** ; et le réservoir
  de saisons doublé.

## Regarder l'interface, et la mesurer

Six scripts Playwright dans [coach-app/tools/](coach-app/tools/) capturent l'app
à trois largeurs, rejouent les séquences de juice sur `/juice.html`, et
**mesurent** ce que l'œil ne tranche pas.

Ils ne sont pas du confort. Les défauts trouvés par eux, et seulement par eux :
une collision de classes `.hud`, une couronne de rayons au dégradé inversé, la
décision du soir repoussée sous la ligne de flottaison sur téléphone — deux
fois, d'abord par les panneaux consultatifs puis par le bandeau lui-même —, une
container query écrite sur la boîte de bordure quand elle mesure la boîte de
contenu, et une taille passée en style inline qui rendait cette même règle
valide et sans effet.

Trois d'entre eux comptent au lieu de regarder, et c'est là qu'est le vrai
gain : l'œil se trompe dans les deux sens. Une animation d'ailes qui parcourait
3,5° et 1,9 px passait pour cassée alors qu'elle tournait — mesurée, corrigée à
9° et 3,8 px, elle se voit. Deux transitions sur `width` et `left` relancées
chaque seconde par l'horloge du soir ne se voyaient pas du tout, et coûtaient un
recalcul de mise en page par image pendant toute la soirée. Et un son ne se
teste pas à l'oreille sur la machine du jour : on compte les voix qu'il
programme.

**Trois d'entre eux rendent un verdict**, et pas seulement une mesure :
`audit.cjs`, `fold.cjs` et `sound.cjs` sortent en 1 quand ils trouvent un défaut.
Ils imprimaient auparavant du JSON et sortaient en 0 quoi qu'ils trouvent, ce qui
en faisait des instruments à lire plutôt que des portes à passer — inutilisables
en CI, et sans effet le jour où plus personne ne lit la sortie. Les règles de
décision vivent dans `tools/verdict.cjs`, et sont couvertes par `npm test`.

L'utilisateur `demo` (`manage.py demodata`) sert à ça : une interface de jeu
jugée sur des compteurs à zéro se conçoit mal, parce que les problèmes de
densité n'y apparaissent jamais.

## Conventions

- Commits atomiques, messages en français.
- Le serveur décide, le client affiche. Aucune règle métier dans `coach-app`.
- Les timestamps viennent du serveur. Le client ne décide jamais de l'heure.
