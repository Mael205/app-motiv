"""Le catalogue des actions que l'assistant a le droit de proposer (§5 étendu).

L'assistant peut agir sur l'app : renommer un projet, découper une étape,
fusionner deux routines, poser un créneau, régler la fenêtre du soir. C'est un
pouvoir réel, et ce module est l'endroit où il est borné.

## Trois murs, dans cet ordre

**Un catalogue fermé.** La clé d'action est une énumération dans le schéma
envoyé au modèle : il ne peut pas nommer un verbe qui n'existe pas ici. Ce
n'est pas une consigne de prompt — une consigne se contourne, une énumération
non. Tout ce que l'assistant sait faire est écrit dans ce fichier, et se lit en
une fois.

**Rien ne s'écrit sans un geste.** Le modèle ne fait que *proposer* : chaque
action passe par un aperçu avant/après et attend qu'on l'applique. C'est la
règle que ``coaching`` posait déjà pour le briefing — « aucune réponse de
modèle ne devient une écriture en base sans passer par un geste de
l'utilisateur » — et l'assistant ne l'assouplit pas, il l'étend à des verbes
plus nombreux.

**Aucune action ne fabrique du travail.** C'est le mur le plus important, et
c'est pour lui que ce catalogue existe sous forme de données plutôt que de
fonctions éparpillées : on peut le relire d'un coup d'œil et vérifier qu'il n'y
a pas de verbe qui crée une session, allonge des minutes, valide une journée,
distribue de l'XP, des Éclats, des boucliers ou des cartes. Le §17 l'interdit,
et un assistant conversationnel est exactement le chemin par lequel ça
rentrerait : il suffirait de demander gentiment. ``TOUCHE_LA_MESURE`` liste ces
verbes-là pour qu'un test puisse affirmer qu'aucun n'existe.

## Ce que « destructive » veut dire ici

Pas « dangereux » : **coûteux à défaire**. Renommer un projet se défait en
renommant. Archiver une routine perd son historique de coches, fusionner deux
routines n'a pas d'inverse. Les actions marquées ainsi portent un avertissement
dans l'aperçu — pas une confirmation de plus, l'application est déjà un geste
explicite, mais la phrase change de ton.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Les domaines, dans l'ordre où ils apparaissent à l'écran
# --------------------------------------------------------------------------

PROJETS = "projets"
ENTRETIEN = "entretien"
CADRE = "cadre"                 # slots, engagements, créneaux
SAISON = "saison"

DOMAINE_LABELS = {
    PROJETS: "Projets et roadmaps",
    ENTRETIEN: "Entretien",
    CADRE: "Slots, engagements et créneaux",
    SAISON: "Saison, jours off et réglages",
}

# Les verbes que ce catalogue n'aura jamais, et la raison — une seule, la même
# pour tous : ils fabriqueraient du travail qui n'a pas eu lieu. Un test relit
# cette liste contre les clés existantes ; si quelqu'un ajoute un jour
# « session.creer », il tombera dessus avant de l'avoir fini.
TOUCHE_LA_MESURE = (
    "session",       # créer, allonger, revalider une session
    "xp",
    "eclats",
    "shards",
    "streak",
    "bouclier",
    "shield",
    "journee",       # « valider la journée » sans avoir travaillé
    "minutes",
    "carte",
    "loot",
    "relique",
    "rang",
    "boss",
)


@dataclass(frozen=True)
class Param:
    nom: str
    type: str                      # "texte", "entier", "date", "liste", "booleen"
    requis: bool = True
    description: str = ""


@dataclass(frozen=True)
class Action:
    """Un verbe du catalogue. Données seulement — l'exécution vit ailleurs."""

    cle: str
    label: str
    domaine: str
    quoi: str                      # ce que ça fait, pour le modèle et pour l'aperçu
    params: tuple[Param, ...] = ()
    destructive: bool = False

    @property
    def requis(self) -> tuple[str, ...]:
        return tuple(p.nom for p in self.params if p.requis)


def _p(nom: str, type_: str, description: str, requis: bool = True) -> Param:
    return Param(nom=nom, type=type_, requis=requis, description=description)


CATALOGUE: tuple[Action, ...] = (
    # ---- Projets et roadmaps ---------------------------------------------
    Action(
        cle="projet.renommer",
        label="Renommer un projet",
        domaine=PROJETS,
        quoi="Change le nom d'un projet existant.",
        params=(_p("projet", "texte", "Nom exact du projet à renommer."),
                _p("nom", "texte", "Le nouveau nom.")),
    ),
    Action(
        cle="projet.apparence",
        label="Changer couleur ou emblème",
        domaine=PROJETS,
        quoi="Change la couleur et/ou le glyphe d'un projet.",
        params=(_p("projet", "texte", "Nom exact du projet."),
                _p("couleur", "texte", "Couleur hexadécimale, #RRGGBB.", requis=False),
                _p("embleme", "texte", "Un seul glyphe.", requis=False)),
    ),
    Action(
        cle="projet.branche",
        label="Rattacher à une branche",
        domaine=PROJETS,
        quoi="Rattache le projet à une branche de l'arbre de compétences.",
        params=(_p("projet", "texte", "Nom exact du projet."),
                _p("branche", "texte", "Clé de branche existante.")),
    ),
    Action(
        cle="projet.verification",
        label="Changer le mode de preuve",
        domaine=PROJETS,
        quoi="Change la façon dont le projet prouve qu'on a travaillé dessus (§6).",
        params=(_p("projet", "texte", "Nom exact du projet."),
                _p("mode", "texte", "git, fichiers ou manuelle."),
                _p("chemin", "texte", "Dépôt ou dossier, si le mode en demande un.", requis=False)),
    ),
    Action(
        cle="projet.engagement",
        label="Changer l'engagement hebdomadaire",
        domaine=CADRE,
        quoi="Change le nombre de sessions visées par semaine. Baisser est "
             "possible en semaine, monter attend dimanche (§4.3).",
        params=(_p("projet", "texte", "Nom exact du projet."),
                _p("sessions", "entier", "Sessions visées par semaine.")),
    ),
    Action(
        cle="projet.frigo",
        label="Mettre au frigo",
        domaine=CADRE,
        quoi="Sort le projet des slots. Son slot devient libre pour autre chose.",
        params=(_p("projet", "texte", "Nom exact du projet."),),
        destructive=True,
    ),
    Action(
        cle="projet.reprendre",
        label="Sortir du frigo",
        domaine=CADRE,
        quoi="Remet un projet du frigo dans un slot libre.",
        params=(_p("projet", "texte", "Nom exact du projet."),),
    ),
    Action(
        cle="projet.attente",
        label="Déclarer une attente",
        domaine=PROJETS,
        quoi="Le projet est bloqué par un tiers ou du matériel. Le slot reste pris.",
        params=(_p("projet", "texte", "Nom exact du projet."),
                _p("jusqu_a", "date", "Dernier jour de l'attente, AAAA-MM-JJ."),
                _p("raison", "texte", "Ce qui bloque, en quelques mots.")),
    ),
    Action(
        cle="projet.fin_attente",
        label="Lever une attente",
        domaine=PROJETS,
        quoi="Le projet n'est plus bloqué : il redevient proposable ce soir.",
        params=(_p("projet", "texte", "Nom exact du projet."),),
    ),
    Action(
        cle="etape.ajouter",
        label="Ajouter une étape",
        domaine=PROJETS,
        quoi="Ajoute une étape à la roadmap d'un projet.",
        params=(_p("projet", "texte", "Nom exact du projet."),
                _p("libelle", "texte", "L'étape, commençant par un verbe d'action."),
                _p("sessions", "entier", "Sessions estimées, 1 à 3.", requis=False),
                _p("apres", "texte", "Libellé de l'étape après laquelle l'insérer.", requis=False)),
    ),
    Action(
        cle="etape.renommer",
        label="Reformuler une étape",
        domaine=PROJETS,
        quoi="Change le libellé d'une étape sans toucher à son état.",
        params=(_p("projet", "texte", "Nom exact du projet."),
                _p("etape", "texte", "Libellé actuel de l'étape."),
                _p("libelle", "texte", "Le nouveau libellé.")),
    ),
    Action(
        cle="etape.decouper",
        label="Découper une étape",
        domaine=PROJETS,
        quoi="Remplace une étape trop grosse par plusieurs étapes d'une session (§4.5).",
        params=(_p("projet", "texte", "Nom exact du projet."),
                _p("etape", "texte", "Libellé de l'étape à découper."),
                _p("morceaux", "liste", "Les étapes qui la remplacent, dans l'ordre.")),
        destructive=True,
    ),
    Action(
        cle="etape.reordonner",
        label="Réordonner la roadmap",
        domaine=PROJETS,
        quoi="Change l'ordre des étapes non terminées d'un projet.",
        params=(_p("projet", "texte", "Nom exact du projet."),
                _p("ordre", "liste", "Tous les libellés non terminés, dans le nouvel ordre.")),
    ),
    Action(
        cle="etape.terminer",
        label="Terminer une étape",
        domaine=PROJETS,
        quoi="Marque une étape comme faite. Inflige ses dégâts au boss et lâche sa carte.",
        params=(_p("projet", "texte", "Nom exact du projet."),
                _p("etape", "texte", "Libellé de l'étape terminée.")),
    ),
    Action(
        cle="etape.supprimer",
        label="Retirer une étape",
        domaine=PROJETS,
        quoi="Retire une étape jamais commencée de la roadmap.",
        params=(_p("projet", "texte", "Nom exact du projet."),
                _p("etape", "texte", "Libellé de l'étape à retirer.")),
        destructive=True,
    ),
    # ---- Entretien --------------------------------------------------------
    Action(
        cle="routine.creer",
        label="Créer une routine",
        domaine=ENTRETIEN,
        quoi="Ajoute une routine courte à la piste Entretien (§11.9).",
        params=(_p("nom", "texte", "Nom de la routine."),
                _p("ancrage", "texte", "reveil, apres_douche, fin_de_session, avant_coucher ou libre.", requis=False),
                _p("jours", "liste", "Jours où elle est proposée, 0 = lundi. Vide = tous les jours.", requis=False),
                _p("cible", "entier", "Nombre de fois par semaine qui rend la semaine tenue.", requis=False),
                # La fenêtre horaire ne concerne que le lever et le coucher.
                # Elle reste vide partout ailleurs : le §11.9 ancre les routines
                # sur un geste et pas sur une horloge, et une heure posée sur du
                # skincare ferait rater la routine pour trois minutes de retard.
                _p("heure", "texte", "Heure limite, « 07:30 ». Seulement pour se lever ou se coucher.", requis=False),
                _p("sens", "texte", "avant ou apres. Défaut : avant.", requis=False)),
    ),
    Action(
        cle="routine.renommer",
        label="Renommer une routine",
        domaine=ENTRETIEN,
        quoi="Change le nom d'une routine.",
        params=(_p("routine", "texte", "Nom actuel de la routine."),
                _p("nom", "texte", "Le nouveau nom.")),
    ),
    Action(
        cle="routine.regler",
        label="Régler une routine",
        domaine=ENTRETIEN,
        quoi="Change l'ancrage, les jours, le seuil hebdomadaire ou la fenêtre horaire d'une routine.",
        params=(_p("routine", "texte", "Nom de la routine."),
                _p("ancrage", "texte", "Nouvel ancrage.", requis=False),
                _p("jours", "liste", "Nouveaux jours, 0 = lundi.", requis=False),
                _p("cible", "entier", "Nouveau seuil hebdomadaire.", requis=False),
                _p("heure", "texte", "Heure limite, « 07:30 ». « aucune » la retire.", requis=False),
                _p("sens", "texte", "avant ou apres.", requis=False)),
    ),
    Action(
        cle="routine.fusionner",
        label="Fusionner des routines",
        domaine=ENTRETIEN,
        quoi="Réunit plusieurs routines en une seule. Les autres sont archivées.",
        params=(_p("routines", "liste", "Noms des routines à fusionner, au moins deux."),
                _p("nom", "texte", "Nom de la routine qui reste."),
                _p("ancrage", "texte", "Ancrage de la routine fusionnée.", requis=False),
                _p("cible", "entier", "Seuil hebdomadaire de la routine fusionnée.", requis=False)),
        destructive=True,
    ),
    Action(
        cle="routine.archiver",
        label="Archiver une routine",
        domaine=ENTRETIEN,
        quoi="Retire une routine de la piste sans effacer son historique.",
        params=(_p("routine", "texte", "Nom de la routine."),),
        destructive=True,
    ),
    Action(
        cle="routine.reordonner",
        label="Réordonner l'Entretien",
        domaine=ENTRETIEN,
        quoi="Change l'ordre d'affichage des routines actives.",
        params=(_p("ordre", "liste", "Tous les noms de routines actives, dans le nouvel ordre."),),
    ),
    # ---- Créneaux ---------------------------------------------------------
    Action(
        cle="creneau.poser",
        label="Poser un créneau",
        domaine=CADRE,
        quoi="Pose un rendez-vous hebdomadaire fixe sur un projet.",
        params=(_p("projet", "texte", "Nom exact du projet."),
                _p("jour", "entier", "0 = lundi."),
                _p("heure", "texte", "HH:MM."),
                _p("minutes", "entier", "Durée du créneau.", requis=False)),
    ),
    Action(
        cle="creneau.deplacer",
        label="Déplacer un créneau",
        domaine=CADRE,
        quoi="Change le jour, l'heure ou la durée d'un créneau existant.",
        params=(_p("projet", "texte", "Nom exact du projet."),
                _p("jour_actuel", "entier", "Jour du créneau à déplacer, 0 = lundi."),
                _p("jour", "entier", "Nouveau jour.", requis=False),
                _p("heure", "texte", "Nouvelle heure, HH:MM.", requis=False),
                _p("minutes", "entier", "Nouvelle durée.", requis=False)),
    ),
    Action(
        cle="creneau.retirer",
        label="Retirer un créneau",
        domaine=CADRE,
        quoi="Supprime un rendez-vous hebdomadaire.",
        params=(_p("projet", "texte", "Nom exact du projet."),
                _p("jour", "entier", "Jour du créneau, 0 = lundi.")),
        destructive=True,
    ),
    # ---- Saison et réglages ----------------------------------------------
    Action(
        cle="saison.signer",
        label="Signer le contrat de saison",
        domaine=SAISON,
        quoi="Signe le contrat de la saison en cours, s'il ne l'est pas déjà.",
        params=(_p("sessions", "entier", "Sessions par semaine engagées."),),
    ),
    Action(
        cle="jour_off.declarer",
        label="Déclarer un jour off",
        domaine=SAISON,
        quoi="Pose un jour off à venir. Jamais rétroactif (§11.5).",
        params=(_p("jour", "date", "AAAA-MM-JJ, aujourd'hui ou plus tard."),),
    ),
    Action(
        cle="veille.declarer",
        label="Déclarer une veille",
        domaine=SAISON,
        quoi="Une pause longue : tout gèle, la saison est rendue intacte au retour.",
        params=(_p("debut", "date", "Premier jour, AAAA-MM-JJ."),
                _p("fin", "date", "Dernier jour, AAAA-MM-JJ."),
                _p("raison", "texte", "Pourquoi, en quelques mots.", requis=False)),
    ),
    Action(
        cle="veille.terminer",
        label="Sortir de veille",
        domaine=SAISON,
        quoi="Met fin à la veille en cours, tout de suite.",
    ),
    Action(
        cle="fenetre.regler",
        label="Régler la fenêtre du soir",
        domaine=SAISON,
        quoi="Change l'heure de début et de fin de la fenêtre du soir, sur les jours visés.",
        params=(_p("debut", "texte", "HH:MM."),
                _p("fin", "texte", "HH:MM."),
                _p("jours", "liste", "Jours concernés, 0 = lundi. Vide = tous.", requis=False)),
    ),
    Action(
        cle="reglages.gardien",
        label="Régler l'heure du gardien",
        domaine=SAISON,
        quoi="Change de combien de minutes le gardien du soir précède la fin de la fenêtre.",
        params=(_p("minutes", "entier", "Minutes avant la fin de la fenêtre."),),
    ),
    Action(
        cle="reglages.amorce_matin",
        label="Régler le rappel du matin",
        domaine=SAISON,
        quoi="Change l'heure du rappel du matin, ou le coupe.",
        params=(_p("heure", "texte", "HH:MM, ou vide pour couper.", requis=False),),
    ),
    Action(
        cle="reglages.fuseau",
        label="Changer de fuseau horaire",
        domaine=SAISON,
        quoi="Change le fuseau qui sert à la fenêtre du soir et à la bascule de 4h.",
        params=(_p("fuseau", "texte", "Nom IANA, par exemple Europe/Paris."),),
    ),
)

PAR_CLE = {a.cle: a for a in CATALOGUE}
CLES = tuple(a.cle for a in CATALOGUE)


@dataclass(frozen=True)
class Verdict:
    ok: bool
    raison: str = ""
    params: dict = field(default_factory=dict)


def verifier_forme(cle: str, params: dict) -> Verdict:
    """La forme d'une action proposée : clé connue, paramètres présents et typés.

    **Ne vérifie aucune règle métier.** C'est délibéré : ce module est pur, et
    « ce slot est-il libre », « est-on dimanche », « cette étape existe-t-elle »
    demandent la base. La forme est refusée ici, le fond l'est à la résolution —
    et l'utilisateur voit la même chose dans les deux cas, une phrase qui dit
    pourquoi.
    """
    action = PAR_CLE.get(cle)
    if action is None:
        return Verdict(False, f"« {cle} » n'est pas une action que je sais faire.")

    if not isinstance(params, dict):
        return Verdict(False, "Paramètres illisibles.")

    propres: dict = {}
    for param in action.params:
        brut = params.get(param.nom)
        vide = brut is None or (isinstance(brut, str) and not brut.strip())

        if vide:
            if param.requis:
                return Verdict(False, f"Il manque « {param.nom} » pour {action.label.lower()}.")
            continue

        valeur = _convertir(brut, param.type)
        if valeur is None:
            return Verdict(False, f"« {param.nom} » n'a pas la forme attendue ({param.type}).")
        propres[param.nom] = valeur

    inconnus = set(params) - {p.nom for p in action.params}
    if inconnus:
        # Refusé plutôt qu'ignoré : un paramètre inventé signale que le modèle a
        # compris autre chose que ce que le catalogue propose, et l'appliquer
        # quand même ferait une action à moitié juste — le pire des cas.
        return Verdict(False, f"Paramètres inconnus : {', '.join(sorted(inconnus))}.")

    return Verdict(True, params=propres)


def _convertir(brut, type_: str):
    """Rend la valeur convertie, ou ``None`` si la forme ne va pas."""
    if type_ == "texte":
        return str(brut).strip() if isinstance(brut, (str, int)) else None
    if type_ == "entier":
        try:
            return int(brut)
        except (TypeError, ValueError):
            return None
    if type_ == "booleen":
        return bool(brut)
    if type_ == "date":
        texte = str(brut).strip()
        return texte if len(texte) == 10 and texte[4] == texte[7] == "-" else None
    if type_ == "liste":
        if not isinstance(brut, (list, tuple)) or not brut:
            return None
        return [x for x in brut]
    return None


def resume(cle: str, params: dict) -> str:
    """Une ligne qui dit ce que l'action va faire. Sert de titre à la carte."""
    action = PAR_CLE.get(cle)
    if action is None:
        return cle
    cibles = [
        str(params[nom])
        for nom in ("projet", "routine", "etape")
        if params.get(nom)
    ]
    if params.get("routines"):
        cibles.append(", ".join(str(x) for x in params["routines"]))
    return f"{action.label} — {' · '.join(cibles)}" if cibles else action.label
