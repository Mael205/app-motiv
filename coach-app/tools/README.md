# Outils de vérification visuelle

Deux scripts Playwright pour **regarder** l'interface au lieu de la deviner.

Ils existent parce qu'une mise en page se juge à l'œil : le HUD à trois
colonnes, la collision de classes `.hud`, la décision repoussée sous la ligne
de flottaison sur téléphone — aucun de ces trois défauts n'aurait été trouvé
par un test unitaire ou par `tsc`.

## `screens.cjs` — l'app réelle

```bash
# Les deux serveurs doivent tourner (coach-api sur 8000, vite sur 5173).
USER_NAME=demo USER_PASS=demo SHOTS=/chemin/sortie TABS="Accueil,Personnage" node tools/screens.cjs
```

Capture chaque onglet en 1440, 1280 et 390 px de large, et écrit les erreurs de
console dans `errors.txt`. Les trois largeurs comptent : les bascules du HUD
sont à 1160 px, et le téléphone doit rester le cas nominal.

Utiliser l'utilisateur `demo` (voir `manage.py demodata`) plutôt que le compte
réel : une interface de jeu jugée sur des compteurs à zéro se conçoit mal,
parce que les problèmes de densité n'y apparaissent jamais.

## `bench.cjs` — les séquences de juice

```bash
SHOTS=/chemin/sortie node tools/bench.cjs
```

Capture les temps de la séquence du §7.3 depuis `/juice.html`, la page d'essai
servie **uniquement en développement** (Vite ne construit que `index.html`).

Elle existe parce qu'un passage de niveau ne se règle pas en le déclenchant
pour de vrai : il faudrait travailler une heure entre deux essais.
