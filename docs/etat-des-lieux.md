# État des lieux — 19 août 2026

Ce document répond à une seule question : **qu'est-ce qui existe, et qu'est-ce
qui reste ?** Il est écrit en relisant le code, pas les intentions — chaque
ligne de la colonne « fait » correspond à quelque chose qui tourne et qui est
couvert par un test.

Il complète, sans les remplacer :

- [SPEC_COACH.md](../SPEC_COACH.md) — la spécification, qui fait autorité sur le
  code. Ce document-ci ne décide de rien ;
- [a-faire.md](a-faire.md) — ce qui **bloque** quelque chose de déjà construit,
  et attend un geste ou une information ;
- [installer.md](installer.md) — installer la PWA sur PC et sur téléphone ;
- [direction-visuelle.md](direction-visuelle.md), [verification.md](verification.md),
  [prompt-nouveau-projet.md](prompt-nouveau-projet.md) — les trois sujets qui
  ont leur propre document.

**Chiffres du jour :** 1008 tests API, 42 tests agent, 21 tests front — tous
verts, et la suite API tourne en 19 secondes contre 440 le matin même. 45
modèles, 65 endpoints, 39 modules de règles pures sans aucun import Django. Les
trois outils de mesure visuelle (`audit`, `fold`, `sound`) rendent un verdict
vert.

---

## 1. Ce qui est fait

### Le noyau — la mécanique quotidienne

| Mécanique | §  | État | Où |
|---|---|---|---|
| Streak, boucliers, trois états de journée | 4.2 | fait | `rules/streak.py` |
| Bascule de journée à 4h, fenêtre du soir par jour de semaine | 1 | fait | `rules/calendar.py` |
| Plancher progressif par rang, dégradé figé à 10 min | 4.1 | fait | `rules/ranks.py` |
| XP, bonus de première session, avant 20h, streak, momentum, plafond de régime | 4.4 | fait | `rules/xp.py` |
| Niveaux, rangs F→SS, deux axes séparés XP / fiabilité | 4.4 | fait | `rules/ranks.py` |
| Slots : 3 de base, 2 max par domaine, 4ᵉ au rang B, 5ᵉ au rang A | 4.3 | fait | `rules/slots.py` |
| Frigo, échange de slot le dimanche, libération immédiate d'un projet fini | 4.3 | fait | `services.py` |
| Projet en attente déclarée (bloqué par un tiers) | 13.5 | fait | `rules/holds.py` |
| Amorce obligatoire à la clôture | 11.3 | fait | `api.py` |
| Proposition unique du soir : projet, durée, tâche | 11.1 | fait | `services.propose` |
| Jours off déclarés | 11.5 | fait | `models.DayOff` |
| Sas de détente | 4.6 | fait | `models.RelaxWindow` |

### Les pistes

| Piste | §  | État |
|---|---|---|
| Atelier — les projets | 4 | fait |
| Corps — deux slots qui ne bougent jamais | 11.4 | fait |
| Entretien — routines courtes, sans streak, payées en Éclats | 11.9 | fait |
| **Habitudes horaires — lever et coucher**, corroborées par les sondes | 11.9 étendu, 6 | **fait le 19 août 2026** |
| Gardes — budget hebdomadaire, cumul qui ne redescend jamais | 11.10 | fait |

### Le jeu

Saisons de 4 semaines avec identité tirée d'un réservoir · boss dont la vie
descend avec le travail réel · phases de boss (mise en scène seulement) · coup
critique · modificateurs de saison appliqués · fantôme de saison, y compris en
direct · Éclats, mise, résolution · loot à quatre raretés avec pitié
progressive · reliques plafonnées à trois · arbre de compétences à neuf
branches · momentum qui tiédit sans s'éteindre · hauts faits · année de douze
saisons · ascendance et ses six voies · Forge.

Les quatre séquences de juice du §7 sont faites, plus la mort du boss. Le son
est synthétisé, pas enregistré. Chaque rareté a sa propre chorégraphie.

### La capacité — le troisième axe

**Ajouté le 19 août 2026, en réponse à un manque réel.** Tout le reste du
système mesure du volume (XP, minutes, heures par branche) ou de la régularité
(rang, semaines tenues). Ni l'un ni l'autre ne dit qu'on est devenu meilleur :
quarante heures de mauvaise pratique donnent le même titre d'arbre que quarante
heures de bonne, parce que le titre se calcule sur les heures.

| Mécanique | État |
|---|---|
| **Preuve** — capacité datée, binaire, constatable par un tiers | fait |
| Critère refusé s'il ne dit rien (« j'ai progressé » n'en est pas un) | fait |
| Paie en Éclats, **jamais** en XP — une capacité n'est pas un volume | fait |
| **Difficulté ressentie** déclarée au debrief, en un tap | fait |
| Constat « trois sessions d'affilée trop faciles » | fait |
| Preuves et heures affichées côte à côte, jamais fusionnées | fait |

Deux propriétés portent tout le reste. D'abord, la preuve vient du **critère de
sortie d'un bloc de parcours**, écrit à la création du projet — donc décidé à
froid, des mois avant d'être atteint. C'est la seule façon de ne pas déplacer la
barre après coup. Ensuite, la difficulté **n'entre dans aucun calcul** : ni XP,
ni streak, ni dégâts. C'est précisément ce qui permet d'y répondre honnêtement,
et c'est le seul constat du système déclenché par une bonne nouvelle apparente —
sur tous les autres compteurs, trois sessions faciles sont une belle série.

### Les sanctions

Le §14 est fait en entier : mode terne, vitrine fermée, sas révoqué, boss qui
régénère, dette, gel du slot gagné, titre en sursis, prélèvement sur la mise,
écran unique de reprise au palier 3, porte de sortie de saison. Les deux
écritures sensibles — régénération et prélèvement — sont **recalculées depuis
l'historique** à chaque lecture, jamais incrémentées.

### L'IA

| Usage | §  | Repli sans modèle |
|---|---|---|
| Briefing de session | 5.1 | proposition déterministe, calculée d'abord |
| Debrief | 5.2 | formulaire manuel |
| Gardien de fin de soirée | 5.4 | amorce déterministe |
| Revue du dimanche | 5.3 | revue sans réponses, causes dites hypothèses |
| Bilan à l'ami | 4.7 | phrase déterministe, filet de relecture |
| Entretien de projet | 4.5 | **aucun** — assumé, renvoie au collage de markdown |
| Assistant à 32 verbes | 5.6 | **aucun** — assumé |

Deux backends derrière la même abstraction : le CLI `claude` (abonnement) en
premier, le SDK ensuite. Porte de qualité qui refuse un briefing à plusieurs
pistes ou une tâche floue.

### Les sondes et le blocage

Agent PC (ActivityWatch + AdGuard Home) · extension navigateur par domaine ·
recette MacroDroid pour le téléphone · jetons de sonde limités à
`/api/signals` · blocage du scroll passif des deux côtés, avec porte de sortie
à deux clics · service élevé qui n'accepte que `block`/`unblock`.

### Les analyses

Bilan quotidien · rapport de fuite de temps avec sa charnière · revue du
dimanche · bilan de saison comparé à toutes les saisons passées · sept
détections continues · trace longue · contrat de saison signé.

### Ce qui a été ajouté le 19 août 2026

**Le plan de travail détaillé traverse maintenant jusqu'à l'écran.** Le format
de création de projet portait déjà l'objectif, le cadre, le parcours en blocs,
les ressources écartées et cinq attributs par étape — ressource, adresse,
périmètre, charge, critère de sortie. Le parseur les lisait ; **l'écriture en
base les jetait tous, sans rien signaler.** L'entretien de projet faisait donc
produire au modèle une information qui disparaissait à la validation. C'est
réparé : deux modèles nouveaux (`ProjectBloc`, `DiscardedResource`), sept champs
nouveaux, et le critère de sortie voyage jusqu'à la décision du soir — « fini
quand » a désormais un repli déterministe le soir sans modèle.

**Un défaut trouvé en écrivant ce test :** `current_step` triait les états par
`order_by("-state")`, c'est-à-dire des chaînes en ordre décroissant, où « todo »
passe devant « doing ». Une étape déjà commencée était systématiquement doublée
par la première étape non touchée. Invisible — les deux libellés sont plausibles
le soir venu — et couvert par aucun test.

**Les habitudes horaires.** Une routine peut porter une fenêtre : « debout avant
7h30 », « au lit avant 23h30 ». Hors fenêtre, la coche est **gardée mais ne
compte pas** — ni semaine, ni Éclats. La comparaison se fait en minutes depuis
la bascule de journée, ce qui est la seule façon correcte : une coche « au lit »
à 00h20 est tard dans la journée d'hier, pas tôt dans celle d'aujourd'hui.

**Les ponctuels.** Une chose à faire une fois — commander, appeler, poster.
Ni XP, ni Éclats, ni coche, ni streak, et **jamais sur l'écran du soir**. Voir
§3 ci-dessous pour la tension avec le §0, qui est réelle et assumée.

**L'extension est devenue permanente.** Elle se fait signer par Mozilla en canal
`unlisted` — validation automatique, pas de revue humaine, pas de publication —
et s'installe alors définitivement sur un Firefox standard. Le module temporaire
d'`about:debugging` reste l'outil de développement, plus le mode d'installation.

---

## 2. Ce qui reste

### Bloquant, et qui n'est plus du code

**Le §16 conditionne chaque jalon au précédent, et J1 attend toujours sa
condition de passage : sept jours d'usage réel.** C'est la seule ligne de ce
document qui compte vraiment. Tout le reste ci-dessous est petit à côté.

### Attend une information

Trois projets déclarent une vérification `git` **sans dépôt renseigné** — leur
preuve de travail ne fonctionne pas, et le système les signale comme non
vérifiés, ce qui est le comportement voulu :

| Projet | Manque |
|---|---|
| Bot Slay the Spire 2 — RL | le chemin du dépôt |
| Outils Dofus 3 — rentabilité craft | le chemin du dépôt |
| Prototype UE5 — 4v1 asymétrique | le chemin du dépôt |

Il manque aussi `Profile.public_base_url` — sans elle, le bilan du dimanche part
sans son lien de lecture, et un lien vers `127.0.0.1` ne mène nulle part chez
l'ami — ainsi que l'adresse du destinataire.

### Attend un geste

| Quoi | Combien de temps |
|---|---|
| Compte addons.mozilla.org + clé API, puis `npm run sign` dans `coach-ext` | 5 min, **une seule fois** |
| Installer la tâche de blocage en administrateur | 2 min, commande dans `coach-agent/README.md` |
| DNS du téléphone → l'IP du PC | 1 min, sur le réseau définitif |

### Décidé, pas construit

- **La progression reste partiellement mesurée.** L'axe capacité dit *ce qui a
  été constaté* ; il ne dit toujours pas *à quel niveau* par rapport à un
  extérieur. Un étalon vraiment externe — un rang HTB, un compte de labs, un
  classement — demanderait de lire un service tiers par projet, ce qui n'est pas
  fait et n'est pas trivial. En attendant, le critère de sortie écrit à froid
  en est la meilleure approximation disponible.
- **Le découpage du bloc suivant du parcours.** Seul le premier bloc est explosé
  en étapes ; les suivants attendent avec leur ressource et leur charge. Rien ne
  découpe le suivant quand le premier se termine — il faut le demander à
  l'assistant ou le coller à la main. C'est le prolongement naturel du travail
  du 19 août.
- **Sonde Android native (§9.2).** Le lecteur `UsageStats` est écrit, jamais
  compilé — ni SDK Android, ni Gradle, ni Kotlin sur cette machine. À ne faire
  que si MacroDroid et AdGuard ne suffisent pas.

*Construits le 20 août 2026, et retirés de cette liste :* l'écran du bilan
quotidien, l'émission des liens de revue le dimanche, le reste du canal entrant
(§11.7, réécrit dans la spec), et **J6 en entier** — séries longues, export,
cosmétiques, réservoir de saisons doublé.

### La question laissée ouverte exprès

- **Les phases de boss ne changent que la mise en scène.** Faut-il qu'une phase
  change un *comportement* ? Chaque idée de ce genre est une règle de plus à
  comprendre le soir où l'on n'a pas envie de comprendre. À trancher sur du
  vécu, pas au jugé.

La seconde — *une étape longue vaut-elle la même carte qu'une étape courte ?* —
a été tranchée le 19 août : non. Le déclencheur reste *terminer*, mais les
heures posées sur l'étape inclinent le tirage vers le haut, sans rien garantir.

---

## 3. Les tensions assumées

Ces points reviennent régulièrement. Ils sont notés ici pour ne pas être
re-débattus à chaque fois.

**Les ponctuels contre le §0.** La spec dit en toutes lettres que ce n'est pas
une todo-list, et le §11.1 interdit une liste à arbitrer avant de démarrer. La
mécanique ajoutée le 19 août tient sur trois murs, et elle ne vaut que tant
qu'ils tiennent : aucune récompense d'aucune sorte, aucune présence sur l'écran
du soir, un traitement visuel délibérément plus pauvre que celui des projets.
Trois courses cochées ne doivent jamais ressembler à une soirée productive —
c'est précisément le mode de défaillance que tout le reste combat. Un test
vérifie qu'un ponctuel ne rapporte rien et n'apparaît pas dans `/api/home`.

**Ce que la corroboration du sommeil ne fait pas.** Une habitude horaire est
corroborée ou contredite par ce que les sondes ont vu — première et dernière
activité de la journée. Le §6 impose la limite dans les deux sens : une
contradiction **ne retire rien** (un PC resté allumé, un téléphone qui se
synchronise, une soirée ailleurs : trois façons d'être contredit à tort), et une
corroboration **ne paie rien** (payer la corroboration reviendrait à récompenser
le fait d'avoir laissé une sonde tourner). Elle est calculée à la lecture,
jamais stockée : un coucher ne peut être jugé qu'une fois la nuit passée.

**Les habitudes horaires contre le §11.9.** Le §11.9 ancre les routines sur un
geste et non sur une heure, avec une bonne raison — « après la douche » arrive
au bon moment sans réveil. Deux habitudes échappent à la règle par nature,
parce que l'heure *est* l'habitude. Toutes les autres routines gardent
`deadline` vide et se comportent exactement comme avant ; un test le vérifie.

**Le téléphone n'est couvert qu'en Wi-Fi.** En 4G il ne passe plus par AdGuard.
Un tunnel WireGuard le couvrirait ; ce n'est pas nécessaire pour commencer.

**La muscu n'a pas de détection fiable** sans salle ni objet connecté.
Déclaration manuelle assumée.

**L'apprentissage reste un domaine, pas une piste** (tranché le 16 août 2026).
Le domaine `savoir` le distingue déjà et lui garde une place via la règle des
deux slots par domaine. Une piste aurait ajouté un streak séparé, donc un
deuxième compteur à tenir.

**Chrome ne voit pas Firefox.** Une extension chargée dans un navigateur ne voit
ni l'autre, ni un autre profil, ni la navigation privée. C'est exactement
pourquoi le silence d'une sonde ne prouve rien.

---

## 4. Où vit quoi

```
coach-api/forge/rules/     37 modules de logique pure, aucun import Django
coach-api/forge/services.py  l'orchestration : lit la base, appelle les règles
coach-api/forge/api.py       63 endpoints, aucune règle métier
coach-api/forge/llm/         l'abstraction modèle, ses deux backends, la porte
coach-app/src/screens/       4 écrans : accueil, projets, personnage, journal
coach-app/src/components/    les blocs, dont un par mécanique visible
coach-app/src/juice/         les séquences du §7 et le son synthétisé
coach-app/tools/             6 scripts Playwright, dont 3 rendent un verdict
coach-agent/                 la sonde PC, le gardien de secours, le blocage
coach-ext/                   la sonde web et la fermeture du scroll passif
```

**La règle qui ne se négocie pas :** la logique vit dans `forge/rules/`, sans
aucun import Django, et n'est dupliquée nulle part — surtout pas côté client.
Le serveur décide, le client affiche.
