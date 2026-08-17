# Ce qui reste ouvert

Ce fichier existe parce que plusieurs choses attendent une information ou un
geste que seul l'utilisateur peut fournir, et qu'elles se perdaient d'une
conversation à l'autre. Il ne remplace pas les jalons du §16 de la spec — il
recense ce qui **bloque quelque chose de déjà construit**.

---

## Attend une information de ta part

### Chemins de dépôts et de dossiers

Trois projets déclarent un moyen de vérification sans en avoir les moyens. Le
système les signale comme non vérifiés, ce qui est le comportement voulu — mais
tant que le chemin manque, la preuve de travail ne fonctionne pas pour eux.

| Projet | Déclare | Manque |
|---|---|---|
| Roadmap cybersécurité | `fichiers` | Le dossier où tu écris tes notes. S'il n'y en a pas, passe le projet en `manuelle` : c'est un choix honnête, pas un pis-aller. |
| Bot Smash v2 | `git` | Le dépôt n'est pas cloné sur ce PC. Soit tu le clones, soit tu donnes son chemin s'il est ailleurs. |
| Analyseur Smash | `git` | Idem. |

Une fois le chemin connu :

```bash
cd coach-api
.venv/Scripts/python -c "
import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup()
from forge.models import Project
p = Project.objects.get(name__startswith='Roadmap cyber')
p.repos.get_or_create(path=r'C:\\chemin\\vers\\tes\\notes')
"
```

### Roadmaps des projets actifs

Bestiaire, Evolve et la roadmap cyber n'ont **aucune étape**. C'est le point le
plus bloquant du lot : sans étape ouverte, le coach n'a rien à proposer le soir,
et le §4.5 interdit de démarrer une session sur un projet dont la roadmap est
vide.

En attendant l'assistant IA du §5, la voie est le collage de markdown :
Projets → Nouveau projet → Copier le prompt.

---

## Attend un geste que je ne peux pas faire

| Quoi | Pourquoi moi non | Combien de temps |
|---|---|---|
| Charger l'extension dans Firefox | Manipulation dans l'interface du navigateur | 2 minutes |
| Installer la tâche de blocage en administrateur | Élévation : ni l'agent ni moi ne l'avons, et c'est la règle du §8 | 2 minutes, commande dans `coach-agent/README.md` |
| DNS du téléphone → l'IP du PC | Réglages Wi-Fi d'Android, et à faire sur ton réseau définitif | 1 minute |
| Installer AdGuard en service | Fait, mais à refaire si tu changes de machine | — |

---

## Décidé, pas encore construit

- **Piste Corps à deux slots.** La règle est codée et testée. Danse et course
  occupent les deux slots ; musculation et foot sont au frigo de la piste.
- **Sonde Android native (§9.2).** Le lecteur `UsageStats` est écrit mais n'a
  jamais été compilé — il n'y a pas de SDK Android sur cette machine. À ne faire
  que si la recette MacroDroid et AdGuard ne suffisent pas.
- **Un canal entrant, à la place de Telegram (§11.7, §4.7, §5.3).** Le bot a été
  remplacé par le Web Push et un webhook Discord, et c'est un bon échange pour
  tout ce qui **sort**. Mais un webhook ne reçoit rien, et trois choses écrites
  dans la spec en dépendent : l'accusé de lecture du bilan de l'ami — le seul
  mécanisme externe du produit, aujourd'hui non implémentable —, les 4 à 5
  questions de la revue du dimanche, et la capture d'une idée au frigo sans
  ouvrir l'app.

  Trois pièces suffisent, toutes dans la PWA existante, aucun bot ni compte à
  créer : les **boutons d'action** d'une notification Web Push (démarrer 10 min,
  reporter 15 min) ; un **lien signé** vers une page à écran unique — répondre,
  dicter, marquer « vu » — que l'ami ouvre sans rien installer ; et la **cible
  de partage Android** de la PWA, qui envoie au frigo un texte partagé depuis
  n'importe quelle app. Commencer par le lien signé : il débloque les trois
  usages à lui seul.

  Le §11.7 de la spec parle encore de Telegram et devra être réécrit.

---

## Fait depuis

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
- **L'extension Firefox disparaît à la fermeture du navigateur.** Un module
  temporaire n'est pas persistant, et une extension non signée ne peut pas
  l'être sur Firefox standard. À recharger au démarrage, ou passer par Firefox
  Developer Edition.
- **La muscu n'a pas de détection fiable** sans salle de sport ni objet
  connecté. Déclaration manuelle assumée.
- **L'apprentissage reste un domaine, pas une piste** (tranché le 16 août 2026).
  Le domaine `savoir` le distingue déjà et lui garde une place via la règle des
  deux slots par domaine. Une piste aurait ajouté un streak séparé, donc un
  deuxième compteur à tenir — ce n'est pas ce qui était voulu.
