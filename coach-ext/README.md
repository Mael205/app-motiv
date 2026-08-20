# coach-ext — la sonde web et le blocage YouTube

ActivityWatch ne voit souvent que « chrome.exe ». Cette extension voit le
domaine, et c'est elle qui permet de distinguer réellement une catégorie d'une
autre sur le web (SPEC §9.1).

## Ce qu'elle mesure

Le temps passé sur l'onglet **actif d'une fenêtre ayant le focus**, machine non
inactive. Un onglet ouvert en arrière-plan pendant six heures ne compte pas :
ce serait mesurer des onglets, pas un usage.

Toutes les 5 minutes, elle envoie des couples `(catégorie, minutes)`.

## Ce qui ne sort jamais

- **Aucune URL, aucun domaine, aucun titre de page.** La table qui relie un
  domaine à une catégorie vit dans le stockage local du navigateur. Le serveur
  reçoit « reseaux : 14 » et n'apprend jamais lequel.
- La chaîne de requête et le fragment sont écartés avant même la
  catégorisation : `x.com/page?token=SECRET` devient `x.com/page`.
- Ce qui tombe dans `autre` n'est pas envoyé du tout.

Et comme partout ailleurs : **une détection marque, une absence de détection ne
certifie rien** (SPEC §11.10). L'extension ne déclare jamais une journée tenue.

## Ce qu'elle bloque, quand elle est armée

L'extension demande son état à `/api/agent/state` — c'est le serveur qui décide,
à la fin du sas de détente, à l'heure du gardien, ou plus tôt si une sanction du
§14 avance le palier. L'extension n'a aucune de ces règles et n'en a pas besoin.

Armée, elle fait deux choses sur YouTube, et rien ailleurs :

- **`/shorts/<id>` renvoie vers `/watch?v=<id>`.** La vidéo reste accessible ;
  c'est le défilement qui disparaît. Le lien vers Shorts est aussi retiré du
  rail de gauche, sinon on y retourne d'un clic depuis la page d'arrivée.
- **Le feed d'accueil est masqué**, remplacé par une ligne factuelle.

Ce qui n'est **jamais** touché : la recherche, les vidéos longues, les
abonnements, et tout le reste du web. Le §17 interdit de bloquer ce qui n'est
pas du scroll passif — un blocage qui empêcherait de chercher une réponse
technique à 21h punirait le travail, et serait désinstallé dans la semaine.

**La porte de sortie**, exigée par le §8.5 : le panneau de l'extension a un
bouton « Lever le blocage ». Deux clics, avec soixante secondes entre les deux,
et le blocage se lève pour deux heures — assez pour une soirée, et demain repart
armé. La friction suffit, l'emprisonnement non. La levée est locale au
navigateur : le serveur, lui, reste armé, et le gardien ne change pas d'avis
parce qu'on a fermé un masque de feed.

## Installation

1. Émets un jeton de sonde — il ne peut **que** poster des signaux, il ne donne
   accès à rien d'autre :

   ```bash
   cd coach-api
   .venv/Scripts/python manage.py probetoken --issue ext --name "Firefox"
   ```

   Copie-le : seule son empreinte est stockée, il ne sera plus jamais affiché.

2. **Firefox — installation permanente.** C'est la cible par défaut,
   `manifest.json` est déjà le sien.

   Firefox standard refuse d'installer durablement une extension non signée.
   C'est pour ça que `about:debugging` ne propose qu'un module **temporaire**,
   retiré à la fermeture du navigateur : une sonde qui disparaît chaque soir ne
   mesure rien, et un blocage qui disparaît le soir disparaît exactement quand
   il servait.

   La sortie n'est pas de changer de navigateur, c'est de faire signer
   l'extension. Le canal **`unlisted`** (auto-distribution) fait signer par
   Mozilla **sans publier** sur addons.mozilla.org : validation automatique,
   aucune revue humaine, aucun délai d'attente, et l'extension ne devient
   visible pour personne d'autre.

   Une fois, pour ouvrir le compte :

   - crée un compte sur [addons.mozilla.org](https://addons.mozilla.org/) ;
   - va sur [les identifiants de l'API](https://addons.mozilla.org/developers/addon/api/key/)
     et génère une clé. Tu obtiens un **JWT issuer** (`user:1234:567`) et un
     **JWT secret**. Le secret ne s'affiche qu'une fois.

   Puis, à chaque version :

   ```bash
   cd coach-ext
   npm install                    # la première fois seulement
   npm run lint                   # doit sortir « errors 0 »
   $env:WEB_EXT_API_KEY = "user:1234:567"
   $env:WEB_EXT_API_SECRET = "le-secret"
   npm run sign
   ```

   Le `.xpi` signé arrive dans `web-ext-artifacts/` en quelques minutes.
   Ouvre-le avec Firefox — glisse-le sur une fenêtre, ou `about:addons` →
   l'engrenage → **Installer un module depuis un fichier**. Il survit au
   redémarrage, aux mises à jour de Firefox, et ne demande plus rien.

   Les deux variables d'environnement ne vivent que dans le terminal qui signe.
   Elles ne sont jamais lues par le coach, et n'ont pas à être enregistrées :
   `web-ext` ne les utilise que pour parler à Mozilla.

   > **Mozilla refuse deux fois le même numéro de version.** Avant de resigner,
   > incrémente `version` dans `manifest.json` — sans ça, la signature échoue
   > avec un message qui ne dit pas ça clairement.

   **Pendant le développement**, le module temporaire reste le bon outil : il se
   recharge à chaud et ne demande aucune signature. `npm run dev` ouvre un
   Firefox jetable avec l'extension déjà chargée, ou `about:debugging` → **Ce
   Firefox** → **Charger un module temporaire** → `coach-ext/manifest.json`.

   **Chrome ou Edge** : rien à signer, une extension non empaquetée y persiste
   entre les redémarrages. Il faut d'abord échanger les manifestes, Firefox et
   Chrome n'acceptant pas la même forme de script de fond :

   ```bash
   cd coach-ext
   mv manifest.json manifest.firefox.json && mv manifest.chrome.json manifest.json
   ```

   Puis `chrome://extensions` → **Mode développeur** → **Charger l'extension non
   empaquetée** → choisis le dossier `coach-ext/`.

3. Clique sur l'icône de l'extension. Colle l'adresse de l'API
   (`http://127.0.0.1:8000`) et le jeton de `token.local.txt`.

4. Dans le champ **Catégories**, remplace le contenu par celui de
   `rules.local.json` — ce fichier est ignoré par git et contient les listes
   complètes, y compris celles qui ne regardent personne d'autre. Puis
   **Enregistrer**, et supprime `token.local.txt`.

5. Le premier envoi arrive au bout de 5 minutes. La date du dernier envoi
   s'affiche dans le même panneau.

> **Si rien n'arrive au bout de 10 minutes sous Firefox**, va dans `about:addons`
> → l'extension → **Permissions**, et vérifie que l'accès à `127.0.0.1:8000` est
> accordé. Firefox traite les permissions d'hôte du manifeste V3 comme
> facultatives : elles peuvent demander une validation explicite, là où Chrome
> les accorde d'office.

## Régler les catégories

Le champ JSON du panneau contient la table. `reddit` attrape `old.reddit.com`,
`youtube.com/shorts` attrape les Shorts **sans** attraper les vidéos longues —
c'est voulu : le §17 interdit de bloquer ce qui n'est pas du scroll passif, et
la mesure suit la même ligne.

La catégorie `adulte` est **vide par défaut**, volontairement. Cette liste te
regarde, et elle ne quitte jamais ce navigateur. Remplis-la toi-même, ou
laisse-la vide et garde cette garde en déclaration manuelle.

## Tests

```bash
cd coach-ext && npm test        # 9 tests, la mesure du temps
```

Ils gardent un défaut qui ne se voit pas à l'œil. En manifeste V3, le script de
fond est une page d'événements : le navigateur la suspend dès qu'elle ne fait
rien et la relance au prochain événement, et toutes les variables de module
repartent de zéro. Le tampon des minutes se vidait donc **avant** l'alarme des
cinq minutes, et l'envoi ne partait jamais.

Le symptôme était le pire possible : aucune erreur, aucun refus, aucun message.
Le panneau affichait un état vide — ce qui est **aussi** ce qu'il affiche quand
il n'y a réellement rien à envoyer, un cas normal et fréquent puisque tout ce
qui tombe dans `autre` n'est jamais transmis. Les deux situations étaient
indiscernables, et seule la lecture du journal du serveur pouvait les séparer.

Un défaut de la même famille a suivi, et il venait de la correction précédente :
poser l'alarme au chargement la **remplaçait**, donc remettait son minuteur à
zéro. La page d'événements se réveillant toutes les une ou deux minutes, une
alarme de cinq minutes n'atteignait jamais son échéance. Elle n'est reposée que
si elle n'existe pas.

L'envoi ne l'attend plus, d'ailleurs : **dès qu'une minute pleine existe, elle
part**. L'attente n'achetait rien — le serveur reçoit une fenêtre horaire, pas
un instant — et elle coûtait le diagnostic, puisque « ça ne marche pas » et
« ça n'a pas encore eu lieu » se ressemblent trait pour trait. Le panneau a
pour la même raison un bouton **Envoyer maintenant**, qui dit franchement
« rien à envoyer » quand c'est le cas.

Un test ne peut pas suspendre un vrai navigateur, mais il peut faire
l'équivalent exact : jeter le module et le réimporter en gardant le stockage.
Les cinq tests qui comptent ont été vérifiés à l'envers — correctifs retirés,
ils échouent.

## Limites connues

- **Un seul navigateur.** Une extension chargée dans Chrome ne voit ni Firefox,
  ni un autre profil, ni la navigation privée. C'est exactement pourquoi le
  silence d'une sonde ne prouve rien.
- **Non empaquetée sous Chrome.** Chrome affichera un avertissement au
  démarrage tant que l'extension est chargée en mode développeur. Sous Firefox,
  la version signée n'a pas ce défaut — c'est le module *temporaire*, réservé au
  développement, qui est retiré à chaque fermeture.
- **Le blocage ne couvre que YouTube.** TikTok, X, Instagram et Reddit sont des
  domaines pleins : le §8.5 les confie au fichier hosts, donc à l'agent. Une
  extension ne les fermerait que dans le navigateur où elle est installée.
- Si le serveur est injoignable, **rien n'est bloqué**. Un blocage qui survit à
  la panne du système qui l'a décidé est un blocage que plus personne ne peut
  lever.
