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
| Donner l'adresse publique du serveur et le webhook de l'ami | Ni l'un ni l'autre ne s'inventent : sans eux le bilan du §4.7 ne part pas, ou part sans son bouton « vu » | 2 minutes |

---

## Décidé, pas encore construit

- **Piste Corps à deux slots.** La règle est codée et testée. Danse et course
  occupent les deux slots ; musculation et foot sont au frigo de la piste.
- **Sonde Android native (§9.2).** Le lecteur `UsageStats` est écrit mais n'a
  jamais été compilé — il n'y a pas de SDK Android sur cette machine. À ne faire
  que si la recette MacroDroid et AdGuard ne suffisent pas.
- **Le reste du canal entrant (§11.7).** Le lien signé est fait, et il porte
  déjà les trois usages. Restent deux commodités qui ne débloquent rien mais
  enlèvent des frottements : les **boutons d'action** d'une notification Web
  Push (démarrer 10 min, reporter 15 min), et la **cible de partage Android**
  de la PWA, qui enverrait au frigo un texte partagé depuis n'importe quelle
  app sans passer par le lien.

  Le §11.7 de la spec parle encore de Telegram et devra être réécrit.

- **J6 — confort (§16).** Statistiques longues, export, cosmétiques
  supplémentaires, réservoir de saisons étendu. Rien n'y bloque quoi que ce
  soit : c'est du confort au sens propre, à prendre quand les jalons précédents
  auront tourné pour de vrai.

  Le §16 conditionne chaque jalon au précédent, et J1 attend toujours sa
  **condition de passage : sept jours d'usage réel**. Ce qui manque maintenant
  n'est plus du code.

- **L'écran du bilan quotidien.** `/api/daily` rend la barre, la répartition et
  la phrase ; la notification part la nuit. Il n'y a pas encore de tuile qui le
  montre au réveil.

- **Les questions de la revue par lien signé.** Le type `reponse` existe et la
  page sait l'afficher ; personne n'émet encore ces liens le dimanche soir.
  C'est ce qui permettrait de répondre depuis la notification, sans ouvrir
  l'app.

---

## Décidé le 17 août 2026, à construire

Dix-sept ajouts tranchés en une fois : du jeu, de la raison de revenir, et les
situations que le système ne savait pas encaisser. L'ordre est celui de
construction, pas d'importance égale.

### Parer ce qui n'est pas couvert

1. **Le mode veille.** Une à quatre semaines déclarées : tout gèle, aucune
   notification, aucun jour raté, aucune sanction. C'est le manque le plus
   dangereux du lot — les jours off sont plafonnés à 2 par semaine, ce qui ne
   couvre ni des vacances, ni une grippe, ni des partiels, et la seule issue
   actuelle est la désinstallation.
2. **Le gel de saison.** Le statut `paused` existe dans le modèle et ne sert
   nulle part. Une absence longue suspend la saison au lieu de la laisser mourir.
3. **Baisser un engagement à tout moment, le monter seulement le dimanche.**
   Le dimanche protège de l'abandon impulsif, pas de l'ajustement honnête.
4. **Le projet en attente déclarée.** Bloqué par un tiers ou du matériel : deux
   semaines où la détection « projet mort » se tait sans libérer le slot.
5. **Le gardien de secours local.** Serveur injoignable à 21h30 : l'agent
   connaît l'heure et la dernière tâche, il lève le sien.
6. **Le fuseau horaire.** Voyager casse silencieusement la fenêtre du soir et la
   bascule de 4h. Détecter l'écart et proposer de basculer.
7. **Le remplaçant de l'ami.** Trois semaines sans lecture sont signalées, mais
   rien n'est proposé ensuite. Changer de destinataire ne doit pas coûter les
   24 heures du désarmement.

### Le jeu

8. **Les quêtes du jour et de la semaine (§4.4).** Spécifiées, jamais
   construites : une quête plancher, une quête bonus contextuelle, une quête
   hebdo posée le dimanche.
9. **Le coup critique.** Une session sur dix rapporte le double, avec son effet.
   Récompense variable posée sur du travail réel.
10. **Les phases de boss.** À 50 % et 25 %, il change de nom et de
    comportement. Aucune règle modifiée, de la mise en scène là où la saison
    s'aplatit.
11. **Le butin d'étape.** Terminer une étape lâche une carte garantie : c'est
    l'action la plus structurante du système et la moins fêtée.
12. **Le fantôme en direct.** Sa position à cette heure-ci, sur la jauge du
    soir. Aujourd'hui la comparaison n'existe qu'en fin de journée.
13. **Le dernier round.** Les trois derniers jours, la vie du boss s'affiche en
    sessions restantes. Informatif seulement — un bonus de fin encouragerait le
    sur-régime exactement là où il fait le plus de dégâts.

### Revenir

14. **La notification du matin.** L'amorce, à l'heure de ton choix : « ce soir,
    brancher le raycast ». Le déclencheur le moins cher du lot.
15. **« Il y a quatre semaines ».** Une entrée de journal d'il y a un mois,
    ressortie dans la revue du dimanche.
16. **Le contrat de saison signé.** Un engagement pris explicitement se tient
    mieux qu'un réglage modifié en passant.
17. **La trace longue.** Un écran des seuls compteurs qui ne redescendent
    jamais, à consulter le soir où le streak vient de casser.

---

## Fait depuis

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
