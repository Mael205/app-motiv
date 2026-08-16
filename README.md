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
cd coach-api && .venv/Scripts/python -m pytest      # 348 tests, l'API
.venv/Scripts/python -m pytest ../coach-agent        # 24 tests, la sonde PC
```

372 tests couvrent ce qu'un bug détruirait en premier : l'évaluation du streak et
des boucliers dans ses trois états de journée, la bascule de journée à 4h, le
calcul d'XP avec sa dégressivité, les saisons, le parcours complet d'une session,
la lecture du markdown de création de projet, les deux limites dures de
l'attribution de slot, et la preuve de travail lue dans git.

Plusieurs gardent des promesses plutôt que des calculs, et ce sont peut-être les
plus importants : aucun compteur d'Entretien ne redescend, aucune routine ne
rapporte d'XP, aucun message de dépassement d'une garde ne contient un mot de
jugement, et **aucune sonde ne peut déclarer une journée tenue**. Ces règles-là
se perdent au premier refactoring si personne ne les surveille.

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
- Bascule de journée à 4h, fenêtre du soir paramétrable par jour de semaine.
- XP avec bonus de première session, bonus avant 20h, multiplicateurs de streak
  et de momentum, **et le plafond de régime** qui éteint la récompense au-delà de
  trois sessions par jour.
- Niveaux, rangs F→SS, saisons de 4 semaines avec identité tirée d'un réservoir,
  boss dont la vie descend avec le travail réel, hauts faits.
- Piste Entretien : routines courtes ancrées sur un geste, mesurées à la semaine,
  sans streak cassable, payées en Éclats et jamais en XP (§11.9).
- Création d'un projet en collant le markdown produit par un chat, avec aperçu
  avant écriture. Le prompt est embarqué dans l'app, copiable en un tap, et
  documenté dans [docs/prompt-nouveau-projet.md](docs/prompt-nouveau-projet.md).
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
- Interface : jauge du soir, fiche de personnage, barre de boss, écran de session
  avec sa séquence de fin.

## Conventions

- Commits atomiques, messages en français.
- Le serveur décide, le client affiche. Aucune règle métier dans `coach-app`.
- Les timestamps viennent du serveur. Le client ne décide jamais de l'heure.
