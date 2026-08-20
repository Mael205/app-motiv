# Ce qui reste ouvert

Ce fichier existe parce que plusieurs choses attendent une information ou un
geste que seul l'utilisateur peut fournir, et qu'elles se perdaient d'une
conversation à l'autre. Il ne remplace pas les jalons du §16 de la spec — il
recense ce qui **bloque quelque chose de déjà construit**.

Pour l'inventaire complet — ce qui existe, ce qui reste, et les tensions
assumées —, voir [etat-des-lieux.md](etat-des-lieux.md). Ce fichier-ci ne garde
que ce qui attend quelqu'un.

---

## Attend une information de ta part

### Chemins de dépôts

Trois projets déclarent la vérification `git` sans dépôt renseigné. Le système
les signale comme non vérifiés, ce qui est le comportement voulu — mais tant que
le chemin manque, la preuve de travail ne fonctionne pas pour eux.

| Projet | Manque |
|---|---|
| Bot Slay the Spire 2 — RL | Le dépôt n'est pas déclaré sur ce PC. Soit tu le clones, soit tu donnes son chemin s'il est ailleurs. |
| Outils Dofus 3 — rentabilité craft | Idem. |
| Prototype UE5 — 4v1 asymétrique | Idem. |

S'il n'y a pas de dépôt du tout, passe le projet en `manuelle` : c'est un choix
honnête, pas un pis-aller. Se croire vérifié est pire qu'assumer le manuel.

Une fois le chemin connu, depuis l'app : Projets → le projet → déclarer le
dépôt. Ou en ligne de commande :

```bash
cd coach-api
.venv/Scripts/python -c "
import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup()
from forge.models import Project
p = Project.objects.get(name__startswith='Outils Dofus')
p.repos.get_or_create(path=r'C:\chemin\vers\le\depot')
"
```

### L'adresse publique et le destinataire du bilan

Sans `Profile.public_base_url`, le bilan du §4.7 part sans son bouton « vu ».
Ni l'adresse ni le webhook de l'ami ne s'inventent.

Depuis le 20 août, cette adresse manquante coûte une chose de plus : **la
question de la revue du dimanche ne part pas**. Elle voyage dans un lien signé,
et un lien vers `127.0.0.1` ne mène nulle part depuis un téléphone. Le
déclencheur préfère se taire — poser une question sans donner le moyen d'y
répondre n'ajoute qu'une chose à faire plus tard.

### Les clés VAPID, si les notifications système doivent arriver

`python manage.py vapid_keys` les génère. Sans elles, le canal Web Push se
déclare indisponible et tout passe par Discord — y compris le gardien du soir,
qui perd alors ses deux boutons. L'abonnement du navigateur, lui, se fait
maintenant tout seul : onglet Journal, « Activer les notifications ».

---

## Résolu depuis

- **Les roadmaps vides** (résolu). Bestiaire, Evolve et la roadmap cyber ont
  chacun leurs étapes. C'était le point le plus bloquant du lot.
- **L'extension temporaire** (résolu le 19 août 2026). Voir plus bas.

---

## Attend un geste que je ne peux pas faire

| Quoi | Pourquoi moi non | Combien de temps |
|---|---|---|
| Créer le compte addons.mozilla.org et sa clé API, puis `npm run sign` | Un compte ne se crée pas à ta place | 5 minutes, **une seule fois** — la suite est automatique |
| Installer la tâche de blocage en administrateur | Élévation : ni l'agent ni moi ne l'avons, et c'est la règle du §8 | 2 minutes, commande dans `coach-agent/README.md` |
| DNS du téléphone → l'IP du PC | Réglages Wi-Fi d'Android, et à faire sur ton réseau définitif | 1 minute |
| Installer AdGuard en service | Fait, mais à refaire si tu changes de machine | — |
| Donner l'adresse publique du serveur et le webhook de l'ami | Ni l'un ni l'autre ne s'inventent : sans eux le bilan du §4.7 ne part pas, ou part sans son bouton « vu » | 2 minutes |
| Donner les trois chemins de dépôt ci-dessus | Ils ne sont pas sur cette machine | 2 minutes |

---

## Décidé, pas encore construit

Il n'en reste **qu'un**, et il est bloqué par la machine et non par une
décision. Tout le reste de cette section a été construit le 20 août 2026 — le
détail est plus bas.

- **Sonde Android native (§9.2).** Le lecteur `UsageStats` est écrit et n'a
  jamais été compilé : il n'y a **ni SDK Android, ni Gradle, ni Kotlin** sur
  cette machine, seulement un Java 8 hérité d'autre chose. Rien de ce fichier
  ne peut donc être vérifié ici, et écrire un projet Gradle qu'on ne peut pas
  construire produirait du code non testé qui pourrit — le contraire de ce que
  le reste du dépôt fait.

  Le §9.2 la voulait déjà en second : la recette MacroDroid marque la journée,
  ce dont une garde a besoin (§11.10), et seule la *mesure* des minutes réelles
  manque. À reprendre le jour où un SDK est installé, et pas avant.

- **J1 attend toujours sa condition de passage : sept jours d'usage réel.** Le
  §16 conditionne chaque jalon au précédent, et J6 vient d'être construit —
  c'est-à-dire que **plus rien de ce qui reste n'est du code**.

---

## Tranché le 19 août 2026 — les deux questions ouvertes

Elles étaient laissées ouvertes faute de vécu. Les deux ont été tranchées dans
le même sens : le système mesurait du volume découpé en sessions, et ne voyait
pas la différence entre deux plongées de vingt-cinq minutes et une d'une heure.

- **Une séance longue vaut plus qu'une courte**, et la durée annoncée devient
  un objectif au lieu d'un plafond. Voir la ligne « Le minuteur cesse de rogner
  le travail » plus bas.
- **Une étape longue ne vaut plus la même carte qu'une étape expédiée.** Le
  déclencheur reste *terminer* — rien ne tombe pour avoir peiné sans finir —,
  mais les heures posées dessus inclinent le tirage vers le haut.

Reste une question, elle, toujours ouverte :

- **Les phases de boss ne changent que la mise en scène.** Nom, phrase,
  intensité. Faut-il qu'une phase change aussi un *comportement* ? À laisser
  dormir tant que les trois phases n'ont pas été vues en vrai.

---

## Décidé le 17 août 2026 — tout est construit

Les dix-sept ajouts tranchés ce jour-là sont faits, dans l'ordre où ils avaient
été rangés : d'abord ce qui parait une situation sans issue, puis le jeu, puis
les raisons de revenir. Le détail est plus bas.

Ce qui reste ouvert dans ce fichier ne vient donc plus de cette liste. Ce sont
les choses des sections précédentes — les chemins de dépôt, les gestes que je ne
peux pas faire à ta place, et J6 — et **le §16 : J1 attend toujours sa condition
de passage, sept jours d'usage réel.** Ce qui manque maintenant n'est plus du
code.

Les deux questions laissées ouvertes ce jour-là ont été tranchées le 19 août :
voir la section « Tranché le 19 août 2026 » plus haut. La seule qui dorme
encore est celle des phases de boss.

---

## Fait depuis

- **Les saisons racontent quelque chose** (20 août 2026). « Wacken » ne vient de
  nulle part : c'est le festival de métal allemand, inscrit dans le réservoir de
  départ du §12.2 à côté de Hellfest. Le vrai défaut n'était ni l'anglais — c'est
  un village allemand — ni le style : **un nom de festival désigne un lieu et une
  foule, pas un état**. Tous les autres décrivent le mois qui vient. Il est
  remplacé par **L'Éveil**, avec son emblème — un œil qui s'ouvre dans un cercle
  brisé.

  Et l'ordre a changé de nature. Les identités sortaient d'une permutation
  retirée au sort chaque année : ça empêchait la répétition, et ça empêchait
  aussi toute histoire. Les vingt-quatre forment maintenant une **trame en deux
  voies de douze**, et c'est le résultat de la saison précédente qui décide de
  la tienne — la **Voie des Cimes** après une saison tenue, la **Voie des
  Braises** après une saison ratée. Chaque voie avance à son rythme : on reprend
  la voie basse là où on l'avait laissée, donc une année en dents de scie
  tricote les deux et aucun parcours ne se ressemble, sans qu'aucun tirage
  n'intervienne.

  **La voie basse ne retire rien** — même mise, même boss, mêmes règles. Le §17
  interdit d'ajouter une sanction, et une histoire qui punirait doublerait celle
  que la mise a déjà réglée. Ce qui change est le décor, et un mois raté raconté
  comme une descente aux forges est plus tenable qu'un mois raté raconté avec
  les mots d'un sommet.

  Un défaut trouvé en chemin : l'écran d'ouverture de saison passait le **nom**
  de la saison à l'emblème, qui attend une **clé**. Il a donc affiché le glyphe
  de repli sur toutes les saisons depuis qu'il existe.

- **Le boss abattu ne vidait pas seulement la saison, il vidait le mois**
  (20 août 2026). Mesuré, pas déduit : boss tué au jour 11, saison suivante
  **dans vingt jours**. La pause de deux jours était ancrée sur la date de fin
  *prévue*, jamais sur la victoire — donc trois semaines sans boss, sans
  fantôme, sans modificateur et sans mise. Pire, l'écran reproposait d'ouvrir
  une saison en boucle : `current_season` ne rend que les saisons commencées,
  donc l'app voyait « aucune saison » et offrait la suivante, puis la suivante
  encore.

  Le §12.4 avait pourtant tout prévu — « les jours restants alimentent
  directement le score de la saison suivante » — et ce **mode extra** n'avait
  jamais été construit. Il l'est : la saison se clôt le jour de la victoire, la
  suivante est engagée et attend sa date, et les minutes posées entre les deux
  sont mises de côté pour elle. Les deux jours de pause entrent dans la même
  fenêtre : travailler entre deux saisons ne doit jamais valoir moins que ne
  rien faire. Un panneau prend la place du bandeau de saison et dit ce qui se
  passe — sans écran, une récompense qu'on ne distingue pas d'une panne est une
  punition.

- **Le boss suivant rétrécissait à chaque victoire** (20 août 2026). Sa vie
  valait le score en minutes ×1,05, alors que les dégâts viennent aussi des
  étapes de roadmap — soixante points chacune. Un boss de 1800 abattu avec 600
  minutes de session donnait un boss suivant à **630 points**, soit dix heures
  là où le précédent en demandait trente, et le suivant encore moins. La courbe
  s'effondrait, exactement à l'inverse de ce que le ×1,05 promet. La performance
  est maintenant le maximum entre les minutes et les dégâts infligés, plafonnés
  à la vie du boss : le coup fatal dépasse presque toujours, et compter le
  débordement ferait monter la barre d'un hasard.

- **Le gros bouton du soir annonçait cinquante minutes** (20 août 2026). La
  durée proposée reprenait celle déclarée sur le créneau, et deux créneaux en
  déclarent cinquante. C'est le contraire de ce que le §4.1 cherche : le
  plancher est ridicule à dessein pour survivre aux mauvais soirs, et un
  engagement d'une heure affiché à 21h30 est une raison de ne pas appuyer. Le
  bouton annonce désormais le plancher du rang — vingt-cinq minutes au rang F —
  et la séance **monte** avec « +15 minutes ». La durée du créneau reste ce
  qu'elle a toujours été : une intention, que le rappel et le gardien
  continuent d'annoncer.

- **L'heure annoncée pèse enfin** (20 août 2026). C'est la contrepartie de la
  veille, et elle manquait : si une séance compte à n'importe quelle heure, un
  rendez-vous que personne ne constate n'est plus un rendez-vous, c'est une
  préférence — alors que le §11.2 en fait le cœur du dispositif. Le créneau
  était devenu un post-it : le tenir ne rapportait rien, le manquer ne se disait
  qu'au bilan du lendemain matin.

  **La prime de ponctualité remplace le forfait « avant 20h ».** L'ancienne
  règle payait l'horloge : 19h58 payait, 20h02 non, et un créneau déclaré à 21h
  ne pouvait jamais y toucher — une app qui dit « 20h30 » et qui paie « avant
  20h » se contredit à voix haute. La nouvelle paie le rendez-vous tenu à la
  demi-heure près, à n'importe quelle heure. Sans créneau déclaré, il n'y a rien
  à tenir : pas de prime, **et rien de retiré**. Le §17 interdit d'ajouter une
  punition, et le soir où l'on rentre à 22h est celui qui décide du streak.

  **Le gardien de créneau** tombe vingt minutes après un rendez-vous passé sans
  rien de lancé. Il ne parle ni de streak ni de boucliers — c'est le gardien du
  soir qui porte l'enjeu de la journée — et se tait si le projet a déjà eu sa
  séance, même décalée. Il porte les deux boutons du §11.7.

  Deux effets de bord traités au passage. Deux reliques visaient le forfait
  disparu : l'une suit la nouvelle règle et change de nom, l'autre — « Souffle
  long », cinquante séances de cinquante minutes — pointe désormais la prime de
  durée, qui lui ressemble enfin. Et **la jauge du soir mentait** : une séance
  de 10h était dessinée collée à 18h, parce que son ratio était borné à la
  fenêtre. La bande s'élargit maintenant à ce qui a réellement eu lieu, et la
  fenêtre reste affichée à part.

- **Le minuteur cesse de rogner le travail** (19 août 2026). La clôture
  plafonnait les minutes à la durée annoncée : quarante minutes travaillées sur
  un minuteur de vingt-cinq en perdaient quinze, sans un mot. C'était le seul
  endroit du produit où du travail réel disparaissait, et le §17 l'interdit dans
  les deux sens — on ne paie pas ce qui n'a pas eu lieu, on ne raye pas ce qui a
  eu lieu.

  Une séance compte désormais ce qu'elle a duré et **se clôture à tout moment**,
  avant ou après le terme. Trois choses gardent un sens à la durée annoncée :
  elle reste la promesse faite au démarrage et la clôture dit si elle a été
  tenue ; le bouton **« +15 minutes »**, promis par le glossaire depuis le début
  et qui n'existait nulle part, la *rehausse* au lieu de l'effacer ; et un
  garde-fou dur à quatre heures empêche une séance oubliée toute la nuit de
  créditer une nuit de travail.

  **La prime de durée** va avec, et son calibrage a un critère plutôt qu'un
  goût : couper une soirée en deux paie *deux fois* les forfaits — première
  session, avant 20h —, donc une prime plus faible que ce que le fractionnement
  duplique ferait dire à la règle le contraire de ce qu'elle annonce. Un test
  tient cette propriété. Le plafond de régime du §0.2 n'est pas touché : il
  compte des sessions, et prolonger n'en ajoute pas une.

- **L'effort posé sur une étape incline son tirage** (19 août 2026). Réponse à
  la seconde question ouverte. Les minutes travaillées depuis le démarrage de
  l'étape déplacent une part des poids du commun vers le rare et l'épique,
  plafonnées à cinq heures — au-delà, une étape n'est plus longue, elle est
  bloquée, et le §13.5 a déjà un constat pour ça. Une **séance longue** peut en
  plus faire tomber une carte, avec une probabilité qui monte avec les minutes :
  probabiliste et non garantie, sinon une carte par soir inonderait la
  collection en un mois.

- **Le canal entrant est complet** (20 août 2026). Il manquait les deux bouts
  qui évitent d'ouvrir l'app — c'est-à-dire tout l'intérêt du §11.7.

  Les **boutons du gardien** : « Démarrer 10 min » et « Reporter 15 min ».
  Répondre demandait quatre gestes au moment précis où l'on n'en fait aucun. Le
  service worker n'a aucun jeton — il ne partage ni le stockage local ni la
  session — donc chaque bouton arrive avec un **lien signé** qui porte son seul
  geste et expire avec la soirée. Le report est tenu par l'ordonnanceur du
  serveur et **ne part pas s'il arrive en retard** : une notification à
  contretemps est celle qui apprend à ignorer toutes les autres.

  La **cible de partage Android** : le coach figure dans le menu « Partager » du
  téléphone, et ce qui y arrive va au frigo — jamais en projet, qui coûte un
  slot.

  Au passage, un défaut trouvé par son propre test : la fonction qui rend le
  *titre* d'un lien s'était mise à **exécuter** son geste. Une messagerie qui
  pré-charge un lien aurait démarré une séance que personne n'avait demandée.
  Rien de ce qui agit ne vit plus derrière un GET.

  Et une découverte en chemin : **la PWA ne s'est jamais abonnée au Web Push**.
  `pushKey` et `subscribePush` existaient dans le client d'API et personne ne les
  appelait ; le gardien partait donc sur Discord ou dans les logs, jamais en
  notification système. La permission se demande maintenant sur un geste, dans
  le journal, et l'abonnement se répare tout seul à chaque ouverture — il expire
  de lui-même au bout de quelques semaines, en silence.

- **Le bilan quotidien a enfin un écran** (20 août 2026). `/api/daily` rendait
  la barre, la répartition et la phrase depuis le 17 ; rien ne les montrait au
  réveil. Une tuile paraît sur l'accueil **avant l'ouverture de la fenêtre du
  soir** et disparaît ensuite : le matin il n'y a rien à décider, donc le §11.1
  n'est pas entamé. Elle ne demande rien, se referme d'un « vu » qui tient
  jusqu'au lendemain, et **se tait les jours sans rien à dire** — la même règle
  que la notification de la nuit, calculée côté serveur pour que les deux ne
  divergent jamais.

- **La revue du dimanche se répond depuis la notification** (20 août 2026). Le
  type `reponse` existait et la page savait l'afficher ; personne n'émettait ces
  liens. Une question part le dimanche soir avec son **fait daté** — le §13.3 en
  fait la moitié de la question —, et la réponse atterrit dans la revue. Une
  seule question par lien : une notification porte une phrase, pas un
  questionnaire. Sans `public_base_url`, rien ne part du tout, parce qu'une
  question sans moyen d'y répondre n'ajoute qu'une chose à faire plus tard.

- **J6, le dernier jalon** (20 août 2026). Quatre choses, aucune ne débloque
  quoi que ce soit :

  * **les séries longues** — douze semaines, par soir, par heure de démarrage,
    par projet, sur la fiche de personnage. À distinguer de la trace longue, qui
    ne rend que des compteurs incapables de baisser : celle-ci descend, donc on
    ne l'ouvre pas le même soir. Les semaines vides y figurent explicitement,
    c'est même l'information qu'on vient y chercher ;
  * **l'export** — tout ce qui a été fait, en JSON lisible sans le coach, et
    **aucun secret** : ni jeton de sonde, ni lien signé, ni abonnement, ni
    webhook. Un export se copie sur une clé et s'envoie ; les secrets se
    régénèrent en une commande, le travail non ;
  * **trente et une cartes de plus**, catalogue à cent. La raison est
    arithmétique : à ce rythme de tirage, soixante-neuf cartes se complétaient
    en un an, et une collection complète cesse d'être un moteur ;
  * **le réservoir de saisons doublé** — vingt-quatre identités, vingt-quatre
    boss. Douze tenaient exactement une année, donc la deuxième rejouait la
    première dans un autre ordre. Un défaut trouvé en agrandissant : garder les
    douze premières places d'une permutation par année faisait revenir la moitié
    des noms alors que douze identités dormaient inutilisées. Le réservoir se
    consomme maintenant **sur deux ans** avant d'être rebattu.

- **La saisie des ponctuels** (20 août 2026). Le contenu n'a pas bougé ; c'est
  le geste qui a été repris. Trois champs de même taille sur une ligne — texte,
  date, bouton — font qu'une course de cinq secondes ne se note pas, et une
  liste qu'on ne remplit pas ne sert à rien. Un seul champ visible, l'échéance
  repliée avec trois raccourcis (« aujourd'hui », « demain », « dans 7 jours »),
  le focus qui reste après validation, et des groupes — en retard, aujourd'hui,
  plus tard, sans date. Ce qui devient plus rapide, c'est d'écrire ; ce qui ne
  devient **pas** plus satisfaisant, c'est de cocher : pas de vert, pas
  d'animation, pas de son. Une course cochée ne doit jamais ressembler à une
  session faite.


- **Une absence ne contredit jamais** (19 août 2026, corrigé le jour même).
  Dès le premier signal reçu, l'écran a affiché « debout avant 7h30 —
  contredit ». La sonde web venait d'être installée à 17h ; le matin, elle ne
  tournait pas. La première activité observée était donc 17h48, et la règle en
  concluait un lever tardif.

  Une activité tardive ne dit pas « il s'est levé tard », elle dit « je n'ai
  rien vu plus tôt ». C'est une absence, et le §6 refuse qu'une absence
  invalide quoi que ce soit. D'où l'asymétrie, désormais explicite : **le lever
  ne peut être que corroboré ou muet** — se lever tôt sans toucher un écran ne
  laisse aucune trace —, tandis que **le coucher peut être contredit**, parce
  qu'une activité à 1h12 est une preuve *positive* d'être éveillé. Et il ne se
  juge qu'une fois la journée close : à 18h, la soirée n'a pas eu lieu.

- **La sonde web ne mesurait rien, pour trois raisons empilées** (19 août 2026).
  Trouvées l'une après l'autre en lisant le journal du serveur, parce qu'aucune
  ne produit d'erreur — elles produisent une **absence**, ce qui est
  indiscernable d'un « rien à signaler » légitime.

  1. **CORS.** L'en-tête `X-Probe-Token` n'était pas autorisé : le préflight
     répondait 200 en le refusant, et le navigateur n'envoyait jamais la vraie
     requête. Seules les sondes de navigateur étaient touchées — l'agent PC
     parle en Python, donc sans CORS, et fonctionnait.
  2. **Le tampon vivait en mémoire.** En manifeste V3 le script de fond est une
     page d'événements, suspendue dès qu'elle ne fait rien. Les minutes
     accumulées disparaissaient avant l'alarme des cinq minutes. Il vit
     maintenant dans `storage.local`.
  3. **Rien ne comptait la page déjà ouverte.** `refresh()` n'était appelé que
     sur un changement d'onglet : rester une heure sur la même page de
     documentation ne mesurait rien. Il est appelé au chargement.

  4. **L'alarme se remettait à zéro toute seule**, et ce défaut-là venait de la
     correction du point 3 : poser l'alarme au chargement la *remplace*, donc
     redémarre son minuteur. La page d'événements se réveillant toutes les une
     ou deux minutes, une alarme de cinq minutes n'atteignait jamais son
     échéance. Elle n'est reposée que si elle n'existe pas.

  L'envoi ne dépend plus de l'alarme : **dès qu'une minute pleine existe, elle
  part**, et le panneau a un bouton « Envoyer maintenant » qui répond
  franchement « rien à envoyer » quand c'est le cas. L'attente n'achetait rien
  et coûtait tout le diagnostic.

  Neuf tests couvrent maintenant le script de fond (`cd coach-ext && npm test`),
  et les cinq qui comptent ont été vérifiés à l'envers.

- **La sonde web n'a jamais pu parler au serveur** (19 août 2026). Trouvé en
  cherchant pourquoi l'extension n'envoyait rien : le journal ne contenait que
  des `OPTIONS` réussis et pas une seule vraie requête. L'en-tête
  `X-Probe-Token` n'était pas dans la liste autorisée par CORS — la liste par
  défaut de django-cors-headers ne connaît que les usuels. Le préflight
  répondait donc **200 en refusant l'en-tête**, et le navigateur n'envoyait
  jamais la requête.

  Le symptôme est ce qui rend ce défaut méchant : aucune erreur, aucun refus,
  aucun message. L'extension affichait un état vide, et la seule lecture
  possible était « il n'y a rien à envoyer » — qui est par ailleurs un cas
  normal et fréquent, puisque tout ce qui tombe dans `autre` n'est pas envoyé.

  Il ne touchait que les sondes vivant dans un navigateur : l'agent PC parle en
  Python, donc sans CORS, et il fonctionnait. C'est ce qui l'a caché. Quatre
  tests gardent maintenant le préflight, et ils ont été vérifiés à l'envers —
  correctif retiré, ils échouent.

- **Le lever et le coucher cochés par les sondes** (19 août 2026). L'agent PC
  date la première et la dernière activité de la journée ; ces deux bornes
  suffisent à cocher « debout » et « au lit » sans un geste. Trois bornes que
  l'automatisation ne franchit pas : elle ne coche que sur **preuve positive**
  — un silence ne coche rien —, elle ne **décoche jamais** et ne marque jamais
  d'échec (§6), et le coucher **attend la bascule de 4h**, parce qu'avant, une
  absence d'activité après 23h30 ne prouve rien : il est 22h.

  C'est **l'ancre** qui décide de la borne qui juge, et ce point vient d'un
  défaut trouvé par un test : la première version lisait les deux bornes pour
  toute habitude, et cochait donc « au lit avant 23h30 » dès qu'une activité
  était vue à 20h. La borne était bien dans la fenêtre, la conclusion absurde.

  Une fenêtre posée sur une routine sans ancre de lever ou de coucher reste
  vérifiable au tap : aucune sonde ne saura la corroborer, c'est tout.

- **Une perte de données, et le garde-fou qui manquait** (19 août 2026). En
  régénérant le jeu de démonstration avec `manage.py demodata`, j'ai effacé un
  projet qui vivait sous le compte `demo` sans avoir été créé par cette
  commande : « Parcours Pentesting — linéaire », **120 étapes**. Il n'y a pas de
  sauvegarde de `db.sqlite3`, et le markdown d'origine n'est nulle part dans le
  dépôt. Il n'est pas récupérable.

  La cause est nette. `Project.user` est en PROTECT, exprès, pour que personne
  ne puisse effacer des heures de travail par cascade (§17). Mais `demodata`
  démontait ensuite tout **explicitement**, ce qui contournait la protection.
  La commande refuse désormais de toucher à un projet qu'elle n'a pas créé, et
  demande `--force` pour passer outre. La leçon vaut au-delà : le compte `demo`
  est jetable **par conception**, donc rien de réel ne doit y être rangé.

- **La saison d'essai** (19 août 2026). Index 0, mise nulle, durée libre, et
  surtout **exclue de toute comparaison** : elle ne dimensionne aucun boss et
  n'entre dans aucun réservoir de fantômes. Les premiers jours servent à régler
  ses créneaux ; leur score est faussement bas, et une saison d'apprentissage
  rangée parmi les vraies resterait un adversaire trop faible pour toujours. Son
  boss est mis à l'échelle de sa durée réelle.

- **La création d'une habitude horaire** (19 août 2026). La mécanique existait
  depuis le matin, le geste non : une routine ne se crée que par l'assistant, et
  son verbe ignorait la fenêtre. « Debout avant 7h30 » était donc **incréable** —
  rien n'échouait, la chose n'existait pas. Les verbes `routine.creer` et
  `routine.regler` prennent maintenant `heure` et `sens`. Le catalogue reste à
  trente-deux verbes, et un test le vérifie.

- **La capacité, la difficulté, l'installation** (19 août 2026, second lot).
  Le système ne mesurait que du volume et de la régularité — rien ne disait
  qu'on était devenu meilleur. Trois ajouts : la **preuve**, fait daté et
  constatable par un tiers, tirée du critère de sortie d'un bloc de parcours
  écrit à froid ; la **difficulté ressentie** au debrief, qui n'entre dans aucun
  calcul et déclenche un constat au bout de trois sessions trop faciles ; et la
  **corroboration** des habitudes horaires par les sondes, qui ne retire jamais
  rien et ne paie jamais rien (§6). L'installation PWA sur PC et téléphone est
  documentée dans [installer.md](installer.md).

- **Le plan de travail qui traverse, les habitudes horaires, les ponctuels,
  l'extension permanente** (19 août 2026). Quatre choses, dont une réparation.

  Le format de création de projet portait déjà l'objectif, le cadre, le parcours
  en blocs, les ressources écartées et cinq attributs par étape. Le parseur les
  lisait ; **l'écriture en base les jetait tous, sans rien signaler.**
  L'entretien de projet faisait donc produire au modèle une information qui
  disparaissait à la validation — le pire des deux modes de perte, parce qu'il
  ne laisse pas de trace. Le critère de sortie voyage maintenant jusqu'à la
  décision du soir : « fini quand » a enfin un repli déterministe.

  Un défaut trouvé en écrivant ce test-là : `current_step` triait les états par
  `order_by("-state")`, donc des chaînes en ordre décroissant, où « todo » passe
  devant « doing ». Une étape déjà commencée était systématiquement doublée par
  la première étape non touchée. Invisible, et couvert par aucun test.

  Les **habitudes horaires** : une routine peut porter une fenêtre — « debout
  avant 7h30 ». Hors fenêtre, la coche est gardée mais ne compte pas. La
  comparaison se fait en minutes depuis la bascule de journée, seule façon
  correcte : une coche « au lit » à 00h20 est tard dans la journée d'hier.

  Les **ponctuels** : une chose à faire une fois, sans XP, sans Éclats, sans
  streak, et jamais sur l'écran du soir. La tension avec le §0 est réelle et
  documentée dans [etat-des-lieux.md](etat-des-lieux.md).

  L'**extension permanente**, enfin — voir la ligne barrée des limites assumées.

- **Le fuseau horaire, le remplaçant de l'ami, le gardien de secours local**
  (18 août 2026). Trois pannes qui ne se voyaient pas. Voyager décalait la
  fenêtre du soir et la bascule de 4h en silence : l'écart est maintenant
  constaté sur le décalage effectif — deux noms au même décalage ne proposent
  rien — et jamais appliqué tout seul. Un ami qui n'ouvre plus les bilans
  laissait croire à une surveillance qui n'existait pas : changer de
  destinataire est immédiat, sans les 24 heures du désarmement, et l'ancien est
  prévenu — c'est ce qui empêche le remplacement d'être un désarmement déguisé.
  Un serveur injoignable à 21h30 faisait disparaître le gardien : l'agent rejoue
  la consigne datée qu'il avait reçue au dernier contact, sans rien décider
  lui-même, et se tait si elle date d'hier.

- **Le contrat de saison signé, la trace longue, « il y a quatre semaines »**
  (18 août 2026). L'engagement hebdomadaire existait déjà ; ce qui manquait
  était le geste. Le contrat écrit ses termes en toutes lettres avant qu'on
  signe, se date, ne bouge plus, et se relit à la clôture comme un écart —
  jamais comme une note. La trace ne rend que des compteurs qui ne peuvent pas
  baisser, et reste ouverte quand la vitrine du §14 est fermée : la vitrine
  ferme les récompenses, pas le relevé du travail fait. Et la revue du dimanche
  ressort une note d'il y a un mois, telle quelle, sans commentaire.

- **Le projet en attente déclarée** (18 août 2026). Un projet bloqué par
  quelqu'un d'autre était lu comme un abandon : au dixième jour on proposait le
  frigo, et l'engagement manqué faisait tomber la semaine, donc le rang. Deux
  semaines au maximum, jamais rétroactive, une raison nommée — et surtout : le
  slot **reste pris**. C'est ce qui la distingue du frigo, et si elle le
  libérait, la déclarer coûterait une renégociation de slots, donc personne ne
  la déclarerait.

- **Le coup critique, les phases de boss, le butin d'étape, le fantôme en
  direct, le dernier round** (17 août 2026). Du jeu ajouté sans toucher à la
  mesure : le critique double l'XP et rien d'autre, les phases ne changent
  aucune règle, le dernier round ne rend aucun multiplicateur — il change une
  unité. Au passage, `complete_step` n'était pas idempotent : un double-clic
  infligeait une heure de dégâts au boss pour du travail qui n'avait pas eu
  lieu.


- **Le bilan de saison comparé** (17 août 2026). Comparaison à toutes les
  saisons passées et non à la dernière, régressions dites en premier, et la date
  de rupture calculée : le début de la plus longue série de jours non tenus, pas
  le premier jour raté. La question de fin de saison est toujours la même, et le
  système n'apporte que la date — la cause, il vient la chercher.

  Les trois causes probables sortent des revues du dimanche. Elles ne sont pas
  devinées : c'est ce qui a été écrit chaque semaine pendant qu'elle était
  fraîche.

- **Le rapport de fuite de temps** (17 août 2026). Histogramme par tranche de 30
  minutes sur quatre semaines, et surtout la **charnière** : pas la tranche la
  plus lourde, celle où la montée est la plus forte. C'est là qu'on bascule, et
  le seul endroit où un créneau placé juste avant peut mordre.

  Le coût est en unités du système — sessions, points de vie du boss — et jamais
  en morale. Une fenêtre remontée sans heure compte dans le total mais pas dans
  l'histogramme : l'inventer déplacerait la charnière.

- **La revue du dimanche** (17 août 2026). Quatre ou cinq questions portant
  chacune sur un fait daté — un créneau manqué se retient, une semaine en
  général ne se retient pas. Elle a lieu **sans réponses** si le dialogue est
  esquivé, en notant que les causes sont alors des hypothèses. Sortie en trois
  blocs, dont une seule chose à changer, et un contrat calé sur ce qui a été
  tenu plutôt que sur ce qui avait été annoncé — appliqué sur un geste, jamais
  tout seul.

- **Le bilan quotidien, et les écrans des constats** (17 août 2026). Le §13.1
  part après la bascule de 4h : une phrase, des chiffres, aucun adjectif, et le
  silence les jours où il n'aurait rien à dire. Les constats du §13.5 et le
  bilan à l'ami sont dans l'onglet Journal — pas à l'accueil, qui ne porte
  qu'une décision (§11.1).

- **Les sept détections continues** (17 août 2026). Projet mort, étape figée,
  engagement irréaliste, concentration, fin de soirée qui glisse, migration du
  scroll, sur-régime. Logique pure, donc les cas rares se testent en trois
  lignes. Chacune porte une proposition chiffrée, aucune ne décide quoi que ce
  soit — le §17 interdit qu'un système retire seul.

- **Le lien signé et le bilan à l'ami** (17 août 2026). Le canal entrant du
  §11.7 : une page sans compte ni script, un lien qui fait une seule chose et ne
  lit rien. Le bilan du §4.7 part le dimanche à 20h avec son bouton « vu », le
  désarmement coûte 24 heures et l'annulation est immédiate, et trois bilans
  sans lecture sont signalés.

  Ce qui n'y figure jamais : qualité de session, temps d'écran, fuites, gardes.
  Un filet relit le texte complet avant l'envoi et écarte la phrase du modèle si
  elle a dérivé. C'est la ligne à ne pas franchir — du bruit envoyé à un tiers
  devient un jugement social, et une bonne raison de couper le bilan.

  **Il manque l'adresse publique** : sans `Profile.public_base_url`, le bilan
  part sans son lien de lecture. Un lien vers `127.0.0.1` ne mène nulle part
  chez l'ami, donc mieux vaut pas de lien du tout.

- **Le blocage du scroll passif** (17 août 2026). L'état armé existait côté
  serveur depuis le §14 sans que personne ne le lise ; les deux surfaces le
  lisent maintenant.

  L'extension ferme YouTube — `/shorts/<id>` renvoie vers `/watch?v=<id>`, le
  feed d'accueil est masqué, le lien Shorts disparaît du rail. La recherche, les
  vidéos longues et les abonnements ne sont jamais touchés. L'agent ferme les
  domaines pleins par le fichier hosts, en passant par un service élevé qui
  n'accepte que `block` et `unblock` et lit la liste lui-même : l'agent, lui,
  reste en utilisateur normal, comme le §8 l'exige.

  Deux exclusions qui ne doivent pas se perdre : un chemin n'est pas un domaine
  — `youtube.com/shorts` dans hosts fermerait YouTube en entier —, et la
  catégorie `adulte` n'est pas bloquée, parce qu'une garde du §11.10 se tient à
  un budget et jamais à un mur.

  La porte de sortie du §8.5 existe des deux côtés : deux clics, soixante
  secondes, deux heures de répit. Locale à la machine — le serveur reste armé.

  **Reste à installer la tâche planifiée en administrateur**, une fois, avec la
  commande du `README` de l'agent. Tant qu'elle ne tourne pas, l'extension
  bloque seule et l'agent le signale sans se plaindre.

- **Le gardien découpe sa tâche** (17 août 2026). Il reprenait le libellé de
  l'étape et écrivait « 10 min » devant, alors qu'une étape vaut une à trois
  séances de vingt-cinq minutes : la promesse était fausse, et elle était lue le
  soir où l'on cherche une raison de ne pas commencer. Le modèle en extrait
  maintenant le premier geste réel, avec l'amorce et les blocages du dernier
  debrief en contexte. Le projet reste choisi par le code, la porte refuse le
  flou et la morale, et le repli déterministe part à l'identique dès que le
  modèle manque ou dérape.

- **Le §14 en entier** (16 août 2026). Régénération du boss — le champ existait
  sans que rien ne l'écrive —, vitrine fermée, gel du slot gagné, titre en
  sursis, quart de la mise prélevé, écran de reprise du palier 3 et porte de
  sortie de saison au-delà de cinq jours.
- **Les planchers progressifs** (16 août 2026). La session normale suit le
  rang : 25 min de F à C, 30 au rang B, 35 au rang A, plafond à 35. Le **mode
  dégradé reste à 10 minutes, définitivement**.

  La note précédente se lisait à l'envers, et la lecture juste est celle de
  l'utilisateur : *monter en rang, c'est qu'on attend plus de moi*. Il y a deux
  seuils, pas un. Celui qui monte est la barre normale ; celui qui ne bouge
  jamais est l'issue de secours, celle du soir où l'on rentre à 22h — et c'est
  ce soir-là que tout se joue.

  Indexé sur le rang et jamais sur l'XP (§4.4) : l'XP monte avec le volume, et
  un plancher indexé dessus demanderait plus à quelqu'un précisément parce
  qu'il vient de forcer.

---

## Limites assumées, à ne pas « corriger »

Ces points reviennent régulièrement ; ils sont notés ici pour ne pas être
re-débattus à chaque fois.

- **Le téléphone n'est couvert qu'en Wi-Fi.** En 4G il ne passe plus par
  AdGuard. Un tunnel WireGuard le couvrirait, ce n'est pas nécessaire pour
  commencer.
- ~~**L'extension Firefox disparaît à la fermeture du navigateur.**~~ Réglé le
  19 août 2026, et la sortie n'était ni de changer de navigateur ni de recharger
  chaque matin : le canal **`unlisted`** d'addons.mozilla.org fait signer une
  extension **sans la publier**, par validation automatique et sans revue
  humaine. Signée, elle s'installe définitivement sur un Firefox standard. Le
  module temporaire reste l'outil de développement, plus le mode d'installation.
  La marche à suivre est dans `coach-ext/README.md`.
- **La muscu n'a pas de détection fiable** sans salle de sport ni objet
  connecté. Déclaration manuelle assumée.
- **L'apprentissage reste un domaine, pas une piste** (tranché le 16 août 2026).
  Le domaine `savoir` le distingue déjà et lui garde une place via la règle des
  deux slots par domaine. Une piste aurait ajouté un streak séparé, donc un
  deuxième compteur à tenir — ce n'est pas ce qui était voulu.
