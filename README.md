# Coach

Système de discipline personnel. Le cadre, pas les encouragements.

La spécification complète est dans [SPEC_COACH.md](SPEC_COACH.md) — elle fait autorité
sur le code. Toute mécanique retirée doit être vérifiée contre la table de
traçabilité du §15 avant suppression.

## Composants

| Dossier | Rôle | État |
|---|---|---|
| `coach-api/` | Django 5 + DRF — source de vérité, logique métier | **J0/J1 en cours** |
| `coach-app/` | React + Vite, PWA installable — PC et mobile | **J0/J1 en cours** |
| `coach-agent/` | Python, Windows — lancement, sessions fantômes, sondes | **J4 fait** |
| `coach-ext/` | Extension navigateur — sonde web par domaine | **première version** |
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

## Tests

```bash
cd coach-api && .venv/Scripts/python -m pytest      # 522 tests, l'API
.venv/Scripts/python -m pytest ../coach-agent        # 24 tests, la sonde PC
```

546 tests couvrent ce qu'un bug détruirait en premier : l'évaluation du streak et
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
- Niveaux, rangs F→SS, saisons de 4 semaines avec identité tirée d'un réservoir,
  boss dont la vie descend avec le travail réel, hauts faits.
- Piste Entretien : routines courtes ancrées sur un geste, mesurées à la semaine,
  sans streak cassable, payées en Éclats et jamais en XP (§11.9).
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
- **Modificateurs de saison appliqués (§12.5)** : « Aube » paie le matin,
  « Marathon » paie les longues et ferme le mode dégradé, « Fragmentation »
  ouvre une quatrième session à plein tarif sans supprimer le plafond, « Siège »
  gonfle le boss et double la mise. Une clé inconnue reste neutre, et le neutre
  calcule exactement comme avant — ajouter la mécanique ne change pas les
  parties déjà jouées.
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

L'utilisateur `demo` (`manage.py demodata`) sert à ça : une interface de jeu
jugée sur des compteurs à zéro se conçoit mal, parce que les problèmes de
densité n'y apparaissent jamais.

## Conventions

- Commits atomiques, messages en français.
- Le serveur décide, le client affiche. Aucune règle métier dans `coach-app`.
- Les timestamps viennent du serveur. Le client ne décide jamais de l'heure.
