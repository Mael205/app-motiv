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
| `ant auth login` | Ouvre un navigateur pour l'authentification de ton abonnement Claude | 30 secondes |
| Charger l'extension dans Firefox | Manipulation dans l'interface du navigateur | 2 minutes |
| DNS du téléphone → l'IP du PC | Réglages Wi-Fi d'Android, et à faire sur ton réseau définitif | 1 minute |
| Installer AdGuard en service | Fait, mais à refaire si tu changes de machine | — |

---

## Décidé, pas encore construit

- **Piste Corps à deux slots.** La règle est codée et testée. Danse et course
  occupent les deux slots ; musculation et foot sont au frigo de la piste.
- **Sonde Android native (§9.2).** Le lecteur `UsageStats` est écrit mais n'a
  jamais été compilé — il n'y a pas de SDK Android sur cette machine. À ne faire
  que si la recette MacroDroid et AdGuard ne suffisent pas.
- **Blocage du scroll passif (§8.5, §9.1).** L'extension mesure mais ne bloque
  pas. Le blocage dépend de l'état « armé » côté serveur, qui vient avec le sas
  de détente.

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
