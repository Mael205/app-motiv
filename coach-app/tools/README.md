# Outils de vérification visuelle

Des scripts Playwright pour **regarder** l'interface au lieu de la deviner, et
pour **mesurer** ce que l'œil ne peut pas trancher.

Ils existent parce qu'une mise en page se juge à l'œil : le HUD à trois
colonnes, la collision de classes `.hud`, la décision repoussée sous la ligne
de flottaison sur téléphone — aucun de ces défauts n'aurait été trouvé par un
test unitaire ou par `tsc`.

Mais l'œil ne suffit pas non plus, et c'est la raison des trois derniers. Une
animation d'ailes qui parcourait 3,5° passait pour cassée alors qu'elle
tournait ; une transition sur `width` relancée chaque seconde ne se voit pas du
tout ; et un son qu'on n'entend pas peut être coupé, absent, ou simplement
inaudible sur la machine où l'on teste. Ces trois-là se comptent, ils ne se
regardent pas.

Tous prennent `ORIGIN` (défaut `http://localhost:5173`) et supposent les deux
serveurs lancés. Utiliser l'utilisateur `demo` (voir `manage.py demodata`)
plutôt que le compte réel : une interface de jeu jugée sur des compteurs à zéro
se conçoit mal, parce que les problèmes de densité n'y apparaissent jamais.

## `screens.cjs` — l'app réelle

```bash
SHOTS=/chemin/sortie TABS="Ce soir,Personnage" node tools/screens.cjs
```

Capture chaque onglet en 1440, 1280 et 390 px de large. Les trois largeurs
comptent : les bascules du HUD sont à 1160 px, et le téléphone doit rester le
cas nominal.

## `audit.cjs` — ce qui est cassé sans se voir

```bash
SHOTS=/chemin/sortie node tools/audit.cjs
```

Capture comme `screens.cjs`, et rend en plus un `audit.json` avec quatre
familles de défauts :

- **débordement** — un élément qui sort du viewport, en ignorant ceux qu'un
  ancêtre en `overflow: hidden` clippe déjà (sans ce filtre, tout ce qui se
  déplace par `transform` dans une piste remonte en faux positif) ;
- **chevauchement** — deux panneaux qui se recouvrent de plus de 4 px ;
- **layout** — une transition sur `width`, `left`, `top` ou `height`. C'est le
  défaut le plus coûteux et le plus invisible : la jauge du soir en portait deux,
  relancées chaque seconde, donc un recalcul de mise en page par image pendant
  toute la soirée ;
- **console** — les erreurs JavaScript, souvent le vrai motif d'un écran vide.

## `fold.cjs` — la seule mesure qui décide de l'accueil

```bash
node tools/fold.cjs
```

Le bouton « Démarrer » est-il entièrement visible sans défiler, et sans passer
sous la barre d'onglets, en 390×844, 360×740 et 1280×800 ?

Ce défaut s'est produit **deux fois** : d'abord par les panneaux consultatifs,
puis par le bandeau de saison lui-même. Le §11.1 veut que la décision domine
l'écran, et sur téléphone « dominer » commence par « être là quand on ouvre
l'app ». Une marge négative est un échec, pas un détail.

## `bench.cjs` — les séquences de juice

```bash
SHOTS=/chemin/sortie node tools/bench.cjs
```

Capture les temps de la séquence du §7.3 depuis `/juice.html`, la page d'essai
servie **uniquement en développement** (Vite ne construit que `index.html`).

Elle existe parce qu'un passage de niveau ne se règle pas en le déclenchant
pour de vrai : il faudrait travailler une heure entre deux essais.

## `rarities.cjs` — les quatre raretés côte à côte

```bash
SHOTS=/chemin/sortie node tools/rarities.cjs
```

Deux prises par carte — pendant le suspense, puis après le retournement. C'est
la seule façon de vérifier que les quatre se distinguent : chacune prise
isolément paraît toujours correcte, et une épique qui s'ouvre comme une rare ne
se remarque qu'en comparaison.

## `sound.cjs` — le son, sans écouter

```bash
node tools/sound.cjs
```

Remplace le contexte audio par un espion et compte les voix programmées par
chaque séquence. Vérifie trois choses qu'on ne peut pas voir :

- aucune séquence n'est muette ;
- la hiérarchie s'entend — commune 2 voix, rare 3, épique 6, légendaire 12 ;
- la coupure coupe vraiment, à zéro voix programmée.
