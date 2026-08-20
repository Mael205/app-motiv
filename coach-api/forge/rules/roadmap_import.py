"""Import d'un projet écrit en markdown (SPEC §4.5).

Le §5.6 — le choix entre modèle local et modèle distant — n'est pas construit,
et l'interrogation qui produit une bonne roadmap se fait donc ailleurs : dans un
chat, avec le prompt de ``docs/prompt-nouveau-projet.md``. Ce module est le point
d'entrée du résultat.

Le format est délibérément petit et tolérant, parce qu'il est écrit par un
modèle et relu par un humain sur un téléphone :

    # Outils Dofus 3 — rentabilité craft

    Branche: backend
    Couleur: #4FC4B4
    Emblème: ◈
    Engagement: 3

    ## Roadmap

    - [x] Scraper les prix de l'HDV (2)
    - [>] Modèle de coût de craft (2)
    - [ ] API de comparaison des recettes (3)
    - [ ] Interface de consultation (2)

``[ ]`` à faire, ``[>]`` en cours, ``[x]`` fait. Le nombre entre parenthèses est
l'estimation en sessions.

Le parseur ne rejette presque rien : il **avertit**. Une roadmap dont une étape
dépasse trois sessions reste importable, mais l'étape est signalée « à
découper » — le §4.5 traite une étape floue comme un défaut du système, et un
défaut se montre, il ne bloque pas la création.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import slots, verification

MAX_SESSIONS_PER_STEP = 3
DEFAULT_ESTIMATE = 2
DEFAULT_COLOR = "#E8A33D"
DEFAULT_EMBLEM = "◆"
DEFAULT_COMMITMENT = 3

TODO, DOING, DONE = "todo", "doing", "done"

_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_ESTIMATE = re.compile(r"\s*\((?P<n>\d+)(?:\s*sessions?)?\)\s*$", re.IGNORECASE)

# Le gras et l'italique sont du bruit de mise en forme : un modèle écrit
# « **Domaine :** savoir » aussi souvent que « Domaine: savoir ». On les efface
# avant de lire, plutôt que de doubler chaque motif.
_MARQUAGE = re.compile(r"\*\*|__|`")

# Une barre de séparation — « --- », « *** », « ___ ». Sans cette règle, « --- »
# se lisait comme une puce dont le libellé valait « -- » : une étape fantôme au
# milieu de la roadmap.
_BARRE = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")

# La puce. Trois changements, tous appris d'un collage réel :
#
# - ``\*(?!\*)`` refuse le gras. L'ancienne version acceptait ``*`` comme puce,
#   si bien que **chaque ligne en gras** — donc toutes les métadonnées d'un
#   document écrit par un chat — devenait une étape.
# - ``\d+[.)]`` accepte les listes numérotées. Un modèle numérote ses étapes une
#   fois sur deux ; elles étaient purement et simplement perdues.
# - la marque d'état reste facultative.
_BULLET = re.compile(
    r"^\s*(?:[-+]|\*(?!\*)|\d+[.)])\s*(?:\[(?P<mark>[ xX>])\]\s*)?(?P<label>.+?)\s*$"
)

# Une ligne de tableau. Les ressources écartées sortent souvent en tableau à
# deux colonnes — nom, raison —, ce que le format attend justement.
_TABLEAU = re.compile(r"^\s*\|(?P<cellules>.*)\|\s*$")
_TABLEAU_SEPARATEUR = re.compile(r"^[\s|:\-]+$")
_TABLEAU_ENTETE = {"ressource", "nom", "outil", "ecartee", "ecartees"}

# Les clés de métadonnées sont normalisées sans accent ni casse : le markdown
# vient d'un chat, pas d'un formulaire.
_META_KEYS = {
    "branche": "branch",
    "couleur": "color",
    "embleme": "emblem",
    "engagement": "weekly_commitment",
    "domaine": "domain",
    "verification": "verification",
    "depot": "repo_path",
    "objectif": "objective",
    "but": "objective",
    "cadre": "frame",
    "sessions par semaine": "weekly_commitment",
    "chemin": "repo_path",
}

# L'indentation des attributs. Deux espaces suffisent à les distinguer des
# métadonnées du projet, qui vivent en colonne zéro.
ATTR_INDENT = "  "

# La clé peut faire jusqu'à trois mots — « Critère de sortie », « Ressource
# principale » —, parce que c'est ainsi qu'un modèle l'écrit quand on ne lui
# impose pas le format. L'indentation n'est plus exigée : elle disparaît dès
# qu'un chat pose ses attributs sous un titre plutôt que sous une puce, et c'est
# désormais la **clé connue** qui dit qu'on lit un attribut, pas l'espacement.
_ATTR = re.compile(
    r"^\s*(?P<key>[A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+){0,2})\s*:\s*(?P<value>.+?)\s*$"
)

# Les attributs portés par une étape, un bloc de parcours ou une ressource
# écartée. Le même vocabulaire sert aux trois : « Charge » veut dire la même
# chose partout, et un lecteur n'a qu'une grammaire à apprendre.
#
# Les synonymes sont là pour un seul cas, mais il est fréquent : le markdown
# collé depuis un chat n'a pas été écrit contre ce format.
_ATTR_KEYS = {
    "ressource": "resource",
    "ressource principale": "resource",
    "adresse": "url",
    "lien": "url",
    "url": "url",
    "perimetre": "scope",
    "perimetre exact": "scope",
    "charge": "load",
    "charge estimee": "load",
    "sortie": "exit_criterion",
    "critere de sortie": "exit_criterion",
    "resultat": "outcome",
    "raison": "reason",
    "pourquoi": "reason",
    "cout": "cost",
    "prix": "cost",
    "optionnel": "optional",
}

# « Optionnel: oui » se lit en booléen. Le reste — « non », vide, absent — vaut
# faux : un bloc n'est optionnel que s'il le dit franchement.
_OUI = {"oui", "true", "1", "vrai"}

_META_SECTION = "meta"
_ROADMAP_SECTION = "roadmap"
_PARCOURS_SECTION = "parcours"
_ECARTEES_SECTION = "ecartees"
_AUTRE_SECTION = "autre"

_MARKS = {" ": TODO, "": TODO, ">": DOING, "x": DONE, "X": DONE}


@dataclass
class ParsedStep:
    """Une étape, et ce qui la rend exécutable sans réfléchir.

    Les quatre champs qui suivent le libellé ne sont pas de la décoration. Une
    étape qui dit « réviser le réseau » sans nommer sa ressource, son périmètre
    et son critère de sortie est une intention : le soir venu, elle demande de
    décider quoi faire, ce que le §4.5 refuse. Ils restent facultatifs parce
    qu'ils n'ont pas toujours de sens — « appeler le plombier » n'a ni
    ressource ni charge.
    """

    label: str
    state: str = TODO
    estimated_sessions: int = DEFAULT_ESTIMATE
    resource: str = ""
    url: str = ""
    scope: str = ""
    load: str = ""
    exit_criterion: str = ""

    @property
    def needs_split(self) -> bool:
        return self.estimated_sessions > MAX_SESSIONS_PER_STEP


@dataclass
class ParsedBloc:
    """Un bloc du parcours : l'échelle des mois, pas celle de la soirée.

    Le parcours existe parce qu'une roadmap d'étapes de 25 minutes ne peut pas
    porter un objectif à deux ans sans faire trois cents lignes. Le bloc dit où
    l'on va ; les étapes disent quoi faire ce soir. Seul le bloc en cours est
    explosé en étapes — les suivants attendent leur tour avec leur ressource et
    leur charge, ce qui suffit à savoir ce qui reste.
    """

    name: str = ""
    outcome: str = ""
    resource: str = ""
    url: str = ""
    load: str = ""
    cost: str = ""
    optional: bool = False
    exit_criterion: str = ""


@dataclass
class ParsedEcartee:
    """Une ressource écartée, et la raison.

    Sur un sujet documenté il existe dix ressources concurrentes. Sans la
    raison écrite, on refait l'arbitrage à chaque fois qu'on en croise une —
    sans les éléments qui avaient servi à trancher.
    """

    name: str = ""
    reason: str = ""


@dataclass
class ParsedProject:
    """Un projet lu depuis du markdown, pas encore écrit en base."""

    name: str = ""
    branch: str = ""
    domain: str = slots.CODE
    verification: str = verification.MANUELLE
    repo_path: str = ""
    color: str = DEFAULT_COLOR
    emblem: str = DEFAULT_EMBLEM
    weekly_commitment: int = DEFAULT_COMMITMENT
    objective: str = ""
    frame: str = ""
    steps: list[ParsedStep] = field(default_factory=list)
    parcours: list[ParsedBloc] = field(default_factory=list)
    ecartees: list[ParsedEcartee] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Les lignes que le parseur n'a pas su placer. Elles étaient jetées en
    # silence, et c'était le défaut le plus coûteux du module : un document
    # riche pouvait perdre les trois quarts de son contenu en rendant
    # ``valid = True``. Ce qui est perdu se montre, et se propose à l'IA.
    ignorees: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        """Le minimum pour créer quelque chose : un nom et au moins une étape."""
        return bool(self.name) and bool(self.steps)

    @property
    def open_steps(self) -> int:
        return sum(1 for s in self.steps if s.state in (TODO, DOING))


def _strip_accents(value: str) -> str:
    table = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")
    return value.lower().translate(table)


def parse(markdown: str) -> ParsedProject:
    """Lit un projet en markdown. N'écrit rien, ne lève rien : avertit.

    Le document a désormais trois sections possibles — ``Parcours``,
    ``Roadmap``, ``Écartées`` —, et la section décide de ce qu'une puce
    signifie. Avant, toute puce du document devenait une étape : une liste de
    ressources écartées se serait transformée en huit étapes fantômes.
    """
    parsed = ParsedProject()
    section = _META_SECTION
    courant: object = None      # la dernière entrée ouverte, qui reçoit les attributs

    for raw in markdown.splitlines():
        # Le gras est effacé avant toute lecture. Sans ça « **Domaine :** savoir »
        # n'était ni une métadonnée ni un attribut : c'était une puce, parce que
        # l'astérisque du gras se lisait comme une puce.
        line = _MARQUAGE.sub("", raw).rstrip()
        if not line.strip():
            continue
        if _BARRE.match(line):
            continue

        if line.startswith("#"):
            section, courant = _titre(parsed, line, section=section)
            continue

        # Une ligne « Clé: valeur » appartient à l'entrée ouverte — dès lors que
        # la clé est du vocabulaire des attributs. C'est la clé qui décide, plus
        # l'indentation : un chat écrit ses attributs au ras de la marge.
        attribut = _ATTR.match(line)
        if attribut:
            cle = _strip_accents(attribut.group("key")).strip()
            if courant is not None and cle in _ATTR_KEYS:
                _apply_attr(courant, attribut.group("key"), attribut.group("value"))
                continue
            if cle in _META_KEYS:
                # Les métadonnées du projet se lisent partout, pas seulement en
                # tête de document : un chat les pose volontiers sous un titre.
                _apply_meta(parsed, attribut.group("key"), attribut.group("value"))
                continue

        bullet = _BULLET.match(line)
        if bullet:
            # Une sous-puce « - Ressource : … » est un attribut, pas une étape.
            # C'est la façon dont un chat attache ses précisions à une étape
            # numérotée, et sans cette lecture chaque précision devenait une
            # étape fantôme de deux sessions.
            interne = _ATTR.match(bullet.group("label"))
            if (
                courant is not None
                and interne
                and _strip_accents(interne.group("key")).strip() in _ATTR_KEYS
            ):
                _apply_attr(courant, interne.group("key"), interne.group("value"))
                continue

            # Seules deux sections détournent une puce de son sens par défaut.
            # Partout ailleurs — y compris avant tout titre — une puce reste une
            # étape : un markdown collé depuis un chat n'a pas toujours son
            # « ## Roadmap », et le refuser pour ça serait de la paperasse.
            if section == _PARCOURS_SECTION:
                courant = ParsedBloc(name=bullet.group("label"))
                parsed.parcours.append(courant)
            elif section == _ECARTEES_SECTION:
                courant = ParsedEcartee(name=bullet.group("label"))
                parsed.ecartees.append(courant)
            else:
                courant = _step_from(bullet)
                parsed.steps.append(courant)
            continue

        tableau = _TABLEAU.match(line)
        if tableau:
            if section == _ECARTEES_SECTION:
                # En-tête et ligne de séparation ne sont pas des données : les
                # signaler comme perdues serait un faux avertissement.
                ecartee = _ecartee_de_tableau(tableau.group("cellules"))
                if ecartee is not None:
                    parsed.ecartees.append(ecartee)
                    courant = ecartee
            elif not _TABLEAU_SEPARATEUR.match(line):
                parsed.ignorees.append(line.strip())
            continue

        parsed.ignorees.append(line.strip())

    _add_warnings(parsed)
    return parsed


def _titre(parsed: ParsedProject, line: str, *, section: str) -> tuple[str, object]:
    """Lit un titre et rend la section ouverte, plus l'entrée courante.

    Le niveau trois n'était traité nulle part, et c'est par lui qu'un parcours
    écrit par un chat se perdait en entier : « ### Bloc A — Fondamentaux » ne
    ressemble ni à une puce ni à une métadonnée, donc le bloc et ses attributs
    tombaient à côté.
    """
    niveau = len(line) - len(line.lstrip("#"))
    titre = line[niveau:].strip()

    if niveau == 1:
        if not parsed.name and titre:
            parsed.name = titre
        return section, None
    if niveau == 2:
        return _section_de(titre), None

    # Un sous-titre ouvre une entrée dans les sections qui en attendent une.
    if section == _PARCOURS_SECTION:
        bloc = ParsedBloc(name=titre)
        parsed.parcours.append(bloc)
        return section, bloc
    if section == _ECARTEES_SECTION:
        ecartee = ParsedEcartee(name=titre)
        parsed.ecartees.append(ecartee)
        return section, ecartee
    return section, None


def _ecartee_de_tableau(cellules: str) -> ParsedEcartee | None:
    """Une ligne de tableau à deux colonnes : le nom, puis la raison.

    Rend ``None`` pour la ligne de séparation et pour l'en-tête, qui ne sont pas
    des données. Un tableau est la forme que prend spontanément une liste de
    ressources écartées, et l'ignorer coûtait la section entière.
    """
    valeurs = [c.strip() for c in cellules.split("|")]
    valeurs = [v for v in valeurs if v]
    if len(valeurs) < 2:
        return None
    if _strip_accents(valeurs[0]).strip() in _TABLEAU_ENTETE:
        return None
    if all(_TABLEAU_SEPARATEUR.match(v) for v in valeurs):
        return None
    return ParsedEcartee(name=valeurs[0], reason=valeurs[1])


def _section_de(titre: str) -> str:
    """La section ouverte par un titre de niveau deux.

    Le mot-clé est cherché **partout dans le titre**, pas seulement au début.
    Un chat écrit « ## Le parcours (24 mois) », « ## La roadmap du bloc A »,
    « ## Ressources écartées » : aucun de ces trois titres ne commençait par son
    mot-clé, donc aucune section n'était reconnue — le parcours entier
    retombait en étapes, et les écartées avec.
    """
    nom = _strip_accents(titre).strip()
    if "ecartee" in nom or "ecarte" in nom:
        return _ECARTEES_SECTION
    if "parcours" in nom:
        return _PARCOURS_SECTION
    if "roadmap" in nom or "etape" in nom:
        return _ROADMAP_SECTION
    return _AUTRE_SECTION


def _apply_attr(cible: object, cle: str, valeur: str) -> None:
    """Pose un attribut sur l'entrée ouverte. Une clé inconnue est ignorée.

    Ignorer plutôt qu'avertir est délibéré : le markdown peut venir d'un chat,
    et une clé en trop est un détail de rédaction, pas une erreur de structure.
    """
    champ = _ATTR_KEYS.get(_strip_accents(cle))
    if not champ or not hasattr(cible, champ):
        return
    if champ == "optional":
        setattr(cible, champ, _strip_accents(valeur).strip() in _OUI)
    else:
        setattr(cible, champ, valeur.strip())


def _step_from(match: re.Match[str]) -> ParsedStep:
    label = match.group("label")
    estimate = DEFAULT_ESTIMATE

    found = _ESTIMATE.search(label)
    if found:
        estimate = max(1, int(found.group("n")))
        label = label[: found.start()].rstrip()

    mark = match.group("mark")
    state = _MARKS.get(mark if mark is not None else "", TODO)
    return ParsedStep(label=label, state=state, estimated_sessions=estimate)


def _apply_meta(parsed: ParsedProject, key: str, value: str) -> None:
    field_name = _META_KEYS.get(_strip_accents(key))
    if field_name is None:
        return

    if field_name == "color":
        if _COLOR.match(value):
            parsed.color = value.upper()
        else:
            parsed.warnings.append(f"Couleur « {value} » ignorée : il faut un code du type #4FC4B4.")
    elif field_name == "weekly_commitment":
        digits = re.search(r"\d+", value)
        if digits:
            parsed.weekly_commitment = max(1, min(7, int(digits.group())))
    elif field_name == "emblem":
        parsed.emblem = value[:8]
    elif field_name == "verification":
        kind = verification.normalise(value)
        if kind:
            parsed.verification = kind
        else:
            parsed.warnings.append(
                f"Vérification « {value} » inconnue, « manuelle » retenue. "
                f"Attendues : {', '.join(verification.KINDS)}."
            )
    elif field_name == "repo_path":
        parsed.repo_path = value[:500]
    elif field_name == "domain":
        candidate = _strip_accents(value).strip()
        if candidate in slots.DOMAINS:
            parsed.domain = candidate
        else:
            parsed.warnings.append(
                f"Domaine « {value} » inconnu, « code » retenu par défaut. "
                f"Attendus : {', '.join(slots.DOMAINS)}."
            )
    elif field_name == "objective":
        parsed.objective = value[:500]
    elif field_name == "frame":
        parsed.frame = value[:500]
    elif field_name == "branch":
        parsed.branch = value[:32]
    # Aucun « else » : il affectait à la branche toute clé non traitée, si bien
    # qu'ajouter une métadonnée la faisait silencieusement écraser la branche.


def _add_warnings(parsed: ParsedProject) -> None:
    """Les avertissements sont ce que l'écran de confirmation doit montrer."""
    if parsed.ignorees:
        # Le silence était le vrai défaut : un document dont vingt lignes
        # tombaient à côté se présentait comme parfaitement lu, et on validait un
        # projet amputé sans jamais l'apprendre.
        exemples = " ; ".join(f"« {l[:60]} »" for l in parsed.ignorees[:3])
        parsed.warnings.append(
            f"{len(parsed.ignorees)} ligne(s) n'ont pas été comprises et seront "
            f"perdues : {exemples}."
        )
    if not parsed.name:
        parsed.warnings.append("Aucun titre trouvé : il faut une ligne « # Nom du projet ».")
    if not parsed.steps:
        parsed.warnings.append("Aucune étape trouvée : il faut au moins une ligne « - [ ] … ».")
        return

    for step in parsed.steps:
        if step.needs_split:
            parsed.warnings.append(
                f"« {step.label} » est estimée à {step.estimated_sessions} sessions. "
                "Au-delà de trois, l'étape est à découper (§4.5)."
            )

    if parsed.open_steps == 0:
        parsed.warnings.append(
            "Toutes les étapes sont faites : un projet actif doit garder une étape à faire ou en cours (§4.5)."
        )

    ready = verification.readiness(parsed.verification, has_path=bool(parsed.repo_path))
    if not ready.ready:
        parsed.warnings.append(ready.detail)

    doing = sum(1 for s in parsed.steps if s.state == DOING)
    if doing > 1:
        parsed.warnings.append(
            f"{doing} étapes sont marquées « en cours ». Une seule étape courante rend la proposition du soir nette."
        )


# --------------------------------------------------------------------------
# L'écriture du format, symétrique de sa lecture
# --------------------------------------------------------------------------

def render(donnees: dict) -> str:
    """Écrit le markdown canonique à partir de champs structurés.

    **Pourquoi cette fonction existe.** Un modèle à qui l'on demande de produire
    ce format le rate régulièrement : il met les métadonnées en gras, numérote
    les étapes, ajoute une section « objectif ». Le résultat est souvent un
    meilleur document — et un échec complet, parce que le parseur y perd la
    vérification et le chemin du dépôt sans que rien ne le signale.

    Trois tours de reproche n'ont pas suffi à le corriger, et c'était la bonne
    leçon : on ne fiabilise pas une grammaire en la répétant plus fort. Le modèle
    rend donc des **champs**, que cette fonction met en forme. Le format devient
    juste par construction, et il n'y a plus rien à vérifier de ce côté.

    Vit ici, à côté de ``parse``, pour que les deux ne puissent pas diverger :
    le test qui compte est l'aller-retour.
    """
    lignes = [f"# {donnees['nom']}", ""]

    meta = [
        ("Domaine", donnees.get("domaine")),
        ("Vérification", donnees.get("verification")),
        ("Dépôt", donnees.get("depot")),
        ("Branche", donnees.get("branche")),
        ("Couleur", donnees.get("couleur")),
        ("Emblème", donnees.get("embleme")),
        ("Engagement", donnees.get("engagement")),
        ("Objectif", donnees.get("objectif")),
        ("Cadre", donnees.get("cadre")),
    ]
    lignes += [f"{cle}: {valeur}" for cle, valeur in meta if valeur not in (None, "", 0)]

    # Les attributs d'une entrée sont indentés sous elle. L'indentation est ce
    # qui les distingue des métadonnées du projet, qui vivent en colonne zéro :
    # sans elle, un « Charge: 8 h » d'étape se lirait comme une clé du projet.
    def attributs(source: dict, paires: list[tuple[str, str]]) -> list[str]:
        return [
            f"{ATTR_INDENT}{etiquette}: {source[cle]}"
            for etiquette, cle in paires
            if source.get(cle)
        ]

    parcours = donnees.get("parcours") or []
    if parcours:
        lignes += ["", "## Parcours", ""]
        for bloc in parcours:
            lignes.append(f"- {bloc['nom']}")
            lignes += attributs(
                bloc,
                [("Résultat", "resultat"), ("Ressource", "ressource"),
                 ("Adresse", "url"), ("Charge", "charge"), ("Coût", "cout"),
                 ("Sortie", "critere_sortie")],
            )
            # Le booléen ne passe pas par `attributs`, qui saute les valeurs
            # fausses — or c'est justement « oui » qu'on veut voir écrit.
            if bloc.get("optionnel"):
                lignes.append(f"{ATTR_INDENT}Optionnel: oui")

    lignes += ["", "## Roadmap", ""]

    marques = {DOING: ">", DONE: "x", TODO: " "}
    for etape in donnees.get("etapes", []):
        marque = marques.get(etape.get("etat", TODO), " ")
        sessions = etape.get("sessions") or DEFAULT_ESTIMATE
        lignes.append(f"- [{marque}] {etape['libelle']} ({sessions})")
        lignes += attributs(
            etape,
            [("Ressource", "ressource"), ("Adresse", "url"), ("Périmètre", "perimetre"),
             ("Charge", "charge"), ("Sortie", "critere_sortie")],
        )

    ecartees = donnees.get("ecartees") or []
    if ecartees:
        lignes += ["", "## Écartées", ""]
        for item in ecartees:
            lignes.append(f"- {item['nom']}")
            lignes += attributs(item, [("Raison", "raison")])

    return "\n".join(lignes) + "\n"
