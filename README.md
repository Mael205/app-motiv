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
| `coach-agent/` | Python, Windows, tray — automatisation locale | à venir (J4) |
| `coach-ext/` | Extension navigateur — filtrage Shorts | à venir (J5) |
| `coach-mobile/` | Sonde Android — temps d'écran | à venir (J5) |

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

## Tests

```bash
cd coach-api && .venv/Scripts/python -m pytest
```

179 tests couvrent ce qu'un bug détruirait en premier : l'évaluation du streak et
des boucliers dans ses trois états de journée, la bascule de journée à 4h, le
calcul d'XP avec sa dégressivité, les saisons, le parcours complet d'une session,
la lecture du markdown de création de projet et les deux limites dures de
l'attribution de slot.

Trois d'entre eux gardent des promesses plutôt que des calculs, et ce sont
peut-être les plus importants : aucun compteur d'Entretien ne redescend, aucune
routine ne rapporte d'XP, et aucun message de dépassement d'une garde ne contient
un mot de jugement. Ces règles-là se perdent au premier refactoring si personne
ne les surveille.

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
- Deux limites dures sur les slots : trois projets actifs, et deux au maximum
  par domaine — pas trois projets de code en même temps (§4.3).
- Gardes : budget hebdomadaire au lieu d'une abstinence, cumul de jours tenus
  qui ne redescend jamais, aucun jugement dans les messages, et rien qui sorte
  de l'app (§11.10).
- Proposition unique côté serveur : projet, durée, tâche. Aucun écran de choix.
- Amorce obligatoire à la clôture d'une session.
- Interface : jauge du soir, fiche de personnage, barre de boss, écran de session
  avec sa séquence de fin.

## Conventions

- Commits atomiques, messages en français.
- Le serveur décide, le client affiche. Aucune règle métier dans `coach-app`.
- Les timestamps viennent du serveur. Le client ne décide jamais de l'heure.
