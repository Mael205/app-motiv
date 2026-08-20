# Installer l'app — PC et téléphone

Le coach n'est pas sur un magasin d'applications, et il n'y sera pas. C'est une
**PWA** : une page web qui s'installe. Une fois installée, elle a son icône,
s'ouvre en plein écran sans barre d'adresse, reçoit des notifications, et se met
à jour toute seule au lancement suivant.

Ce n'est pas un pis-aller. Le §2 impose PC **et** téléphone liés en permanence :
un binaire par plateforme demanderait deux compilations, un compte développeur
Apple, et une revue de magasin à chaque correction — pour une app qui n'a qu'un
seul utilisateur.

---

## Ce dont l'installation a besoin

Une seule contrainte, et elle décide de tout le reste : **un navigateur
n'installe une PWA que depuis `localhost` ou une adresse en HTTPS.** C'est une
règle de sécurité des navigateurs, pas un réglage — un service worker servi en
HTTP simple sur `192.168.1.x` est refusé sans appel.

Donc :

| Depuis | Marche ? |
|---|---|
| Le PC qui fait tourner le serveur, sur `http://localhost:5173` | **oui**, `localhost` est une exception |
| Le téléphone, sur `http://192.168.1.x:5173` | **non** — la page s'affiche, l'installation est refusée |
| N'importe où, en HTTPS | **oui** |

---

## Sur le PC — deux minutes

Les deux serveurs tournent (`runserver` et `npm run dev`, voir le
[README](../README.md)), puis :

1. ouvre `http://localhost:5173` dans Chrome ou Edge ;
2. dans la barre d'adresse, à droite, une icône d'installation apparaît — un
   écran avec une flèche. Sinon : menu ⋮ → **Installer Coach** ;
3. l'app s'ouvre dans sa propre fenêtre, et une icône est posée dans le menu
   Démarrer.

**Firefox ne sait pas installer une PWA sur ordinateur.** Le support a été
retiré, et n'est pas revenu. Ce n'est pas gênant ici : le PC est justement la
machine où l'agent tourne, et où le navigateur porte l'extension.

Pour l'usage réel, sers la version construite plutôt que le serveur de
développement — elle est plus rapide et fonctionne hors ligne :

```bash
cd coach-app
npm run build
npm run preview        # sert dist/ sur http://localhost:4173
```

---

## Sur le téléphone — la vraie question

Le téléphone a besoin d'une adresse HTTPS. Trois façons d'en avoir une, de la
plus simple à la plus propre.

### 1. Un tunnel — cinq minutes, rien à configurer

Un tunnel expose ton serveur local derrière une vraie adresse HTTPS, sans
toucher à ta box. `cloudflared` est le plus direct :

```bash
cloudflared tunnel --url http://localhost:5173
```

Il affiche une adresse en `https://xxx.trycloudflare.com`. Ouvre-la sur le
téléphone → menu ⋮ → **Ajouter à l'écran d'accueil**.

**Ce que ça coûte :** l'adresse change à chaque lancement, donc l'app installée
pointe vers une adresse morte le lendemain. C'est parfait pour essayer, mauvais
pour vivre avec. Un tunnel nommé (compte Cloudflare gratuit) garde la même
adresse.

### 2. Tailscale — la bonne réponse pour un usage perso

Tailscale relie tes appareils par un réseau privé, avec des noms stables et des
certificats HTTPS valides, sans rien ouvrir sur Internet :

```bash
tailscale serve https / http://localhost:5173
```

Ton téléphone accède alors à `https://ton-pc.ton-réseau.ts.net`. Adresse stable,
donc installation durable — et **rien n'est exposé publiquement**, ce qui compte
pour une app qui contient ton historique complet.

C'est l'option que je recommande tant que le serveur tourne sur ton PC.

### 3. Un vrai déploiement

Le jour où le serveur ne vit plus sur ta machine : un petit VPS, Postgres via
`DATABASE_URL`, le front construit servi en statique, et un certificat Let's
Encrypt. Rien d'autre ne change dans le code — c'est ce que le §1 prévoyait en
gardant SQLite en local et `DATABASE_URL` pour le reste.

---

## Après l'installation, deux réglages

**L'adresse publique.** Renseigne `Profile.public_base_url` avec l'adresse que
tu viens d'obtenir. Sans elle, le bilan du dimanche part sans son lien de
lecture (§4.7) — un lien vers `127.0.0.1` ne mène nulle part chez l'ami, donc le
système préfère n'en mettre aucun.

**Les notifications.** Elles demandent les clés VAPID :

```bash
cd coach-api
.venv/Scripts/python manage.py vapid_keys
```

Puis autorise les notifications à la première demande de l'app. Sur Android,
pense à sortir le coach de l'optimisation de batterie : sinon les notifications
arrivent avec quelques minutes de retard, ce qui est sans importance pour le
bilan du matin et gênant pour le gardien du soir.

---

## Ce qui ne marchera pas, et pourquoi

- **iOS** installe les PWA, mais les notifications push n'y fonctionnent que
  depuis un écran d'accueil, jamais depuis Safari. Rien à faire de particulier :
  installe, et elles marchent.
- **Le mode hors ligne ne remplace pas le serveur.** L'app affiche ce qu'elle a
  en cache, mais le §1 est clair — le serveur décide, le client affiche. Sans
  serveur joignable, on peut lire, pas démarrer une session.
- **Deux installations ne se synchronisent pas entre elles**, elles se
  synchronisent au serveur. C'est le point : il n'y a qu'une seule vérité, et
  elle n'est pas dans le téléphone.
