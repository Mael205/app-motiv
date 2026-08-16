# Direction visuelle et juice — ce qui est validé

Ce document existe parce que la direction des séquences d'ascension a été
**validée explicitement** le 16 août 2026 : *« c'est exactement ce que je
voulais pour les ascensions, t'as parfaitement compris »*.

Ce qui suit n'est donc pas une proposition. C'est la référence à respecter et à
étendre — pour la fin de saison, l'ouverture de saison, et tout ce qui portera
du juice plus tard. Une deuxième direction visuelle inventée à côté ferait
perdre ce qui a été trouvé.

Le §7 de la spec reste au-dessus de ce document en cas de contradiction.

---

## Ce qui fait que ça marche

Cinq décisions portent l'effet. Elles se retrouvent dans chaque séquence.

### 1. L'entrée « slam » — arriver de loin, dépasser, se poser

L'élément central arrive à `scale: 2.6`, en flou (`blur(14px)`), opacité zéro,
et se pose en 520 ms sur une courbe qui **dépasse la cible avant de revenir**
(`cubic-bezier(0.16, 1.2, 0.3, 1)`).

Le dépassement est le point. Une arrivée qui s'arrête pile à sa taille finale
est correcte et morte ; celle qui déborde de quelques pour cent puis se tasse
donne du poids à l'objet. Le flou qui se résorbe fait le reste : l'œil lit une
mise au point, donc une arrivée, pas une apparition.

### 2. La couronne de rayons — vive au centre, éteinte au bord

Quatorze à dix-huit rayons, de largeurs **irrégulières** — un sur trois nettement
plus fin. Rotation lente et continue sur 26 secondes, jamais de clignotement.

Deux erreurs ont été commises et corrigées ici, elles valent d'être notées :

- **Le dégradé était inversé.** Plein à l'extérieur, transparent au centre : ça
  lisait comme des barres posées sur l'écran. Il faut la couleur **au centre**
  et la transparence au bord, pour que la lumière irradie au lieu de rayonner.
- **Il manquait le flou.** `filter: blur(1.5px)` fait toute la différence entre
  une lueur et des rayons de vélo. Sans lui chaque rayon garde une arête nette
  qui attire l'œil sur le trait au lieu de le conduire vers le centre.

### 3. Le chiffre géant

`clamp(88px, 22vw, 148px)`, dans l'accent de saison, avec **deux ombres portées
superposées** — une serrée à 60 px et une très large à 140 px. C'est la double
portée qui donne l'impression que le chiffre éclaire la page plutôt que d'être
posé dessus.

Rien d'autre ne doit être aussi gros sur l'écran à ce moment-là.

### 4. Les canaux empilés

Le skill `game-feel` le formule ainsi : *un impact satisfaisant, c'est cinq à
huit petites réponses qui partent ensemble en moins de 100 ms.* Ici, sur un
passage de niveau : éclair blanc de 90 ms, secousse d'écran, couronne qui
apparaît, écusson qui slam, chiffre qui s'allume, gerbe de particules.

Chacun pris seul est faible. Empilés, ils lisent comme un seul événement.

**Et ils se dosent sur l'importance** — c'est l'autre moitié de la règle :

| Événement | Secousse | Gerbe | Couronne |
|---|---|---|---|
| Passage de niveau | 0,85 | 40 particules | 16 rayons |
| Palier de branche | 0,50 | 26 particules | 12 rayons |
| Relique | 0,30 | — | 14 rayons |
| Carte commune | — | — | — |
| Carte légendaire | — | 46 particules | 18 rayons |

Si tout scintille, plus rien ne scintille.

### 5. La rareté se devine avant d'être lue

La carte arrive **dos face à l'écran**. Sa lueur et l'intensité de ses rayons
trahissent ce qu'elle vaut, et le retournement ne fait que confirmer. Sans ce
délai — 620 ms pour une commune, 900 ms pour une épique ou mieux —, l'animation
ne serait qu'un décor posé sur une information déjà donnée.

La légendaire porte en plus un liseré qui balaie la carte en boucle et un
`box-shadow` à trois couches dont une très large. Elle seule : réservé, sinon le
signal s'use.

---

## Les règles qui ne se négocient pas

Elles viennent du §7 et elles ont toutes une raison pratique.

**Jamais d'animation sur le chemin critique.** Le bouton « Démarrer » répond
immédiatement ; l'effet se joue par-dessus. Une interface qui fait attendre au
moment où l'on a enfin décidé de s'y mettre est une interface qu'on referme.

**Chaque temps est passable d'un clic n'importe où.** Une soirée peut produire
quatre bonnes nouvelles ; quinze secondes de spectacle à 23h sont une punition.

**`prefers-reduced-motion` désactive l'animation, jamais l'information.** Chaque
séquence a une variante non animée qui montre exactement les mêmes faits.

**Les particules en canvas, pas en DOM.** Trente nœuds animés forcent un
recalcul de layout par frame — précisément ce qui fait ramer sur le téléphone
une interface conçue pour faire plaisir.

**Rien de cliquable ne bouge pendant une secousse.** Viser une cible mouvante
est une faute d'ergonomie, pas un effet. La secousse déplace un conteneur
visuel, jamais un bouton.

**Pas de stroboscope.** L'éclair d'ouverture dure 90 ms et ne se répète pas.

---

## Où c'est implémenté

| Quoi | Où |
|---|---|
| Primitives (secousse, compteurs, gerbes, rayons) | `coach-app/src/juice/` |
| Séquence d'ascension | `coach-app/src/components/Ascension.tsx` |
| Tirage de carte | `coach-app/src/components/LootReveal.tsx` |
| Braise de momentum | `coach-app/src/components/MomentumEmber.tsx` |
| Banc d'essai | `coach-app/juice.html` — **dev seulement** |

Le banc d'essai est le point important pour la suite : une séquence de passage
de niveau ne se règle pas en la déclenchant pour de vrai, il faudrait travailler
une heure entre deux essais. Toute nouvelle séquence s'y ajoute.

---

## Ce qui reste à porter à ce niveau

- **Ouverture de saison** (§12.2) — *« le seul moment où l'interface a le droit
  d'être théâtrale »*. Nom en grand, emblème, modificateur tiré, boss.
- **Fin de saison** (§7, séquence 4) — score final, comparaison au fantôme,
  titre décerné, ouverture de la suivante.
- **Démarrage de session** (§7, séquence 1) — l'interface se replie sur le
  timer, tout le reste s'éteint, l'emblème du projet s'imprime.
- **Mort du boss** — non prévue par la spec comme séquence, mais c'est le seul
  événement de la saison qui mérite le traitement du passage de niveau.
