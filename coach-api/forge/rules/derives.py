"""Les détections automatiques continues (SPEC §13.5).

Sept signaux, calculés en permanence, remontés dès qu'ils se déclenchent au lieu
d'attendre le dimanche. Ils partagent une intention, et elle vient du §0.9 : le
système doit **arriver avec les constats déjà faits**. Une analyse qui demande à
l'utilisateur de repérer lui-même qu'il n'a pas touché un projet depuis dix
jours lui redonne exactement le travail qu'il ne fait pas.

Deux règles de ton, qui expliquent la forme des messages ci-dessous :

- **Un constat, pas un reproche.** Le §17 interdit le jugement, et ces signaux
  se déclenchent précisément dans les semaines où ça va mal. Chacun dit ce qui
  est observé et ce qu'on peut en faire — jamais ce qu'il aurait fallu faire.
- **Une proposition chiffrée.** « Tu t'es surengagé » ne se corrige pas ;
  « passer de 3 à 2 sessions par semaine sur ce projet » se corrige d'un tap.

Module **pur** : des chiffres entrent, des constats sortent. Aucun accès base,
aucune date d'aujourd'hui implicite. C'est ce qui permet de tester les sept sur
des historiques fabriqués, y compris ceux qui n'arrivent qu'une fois par an.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# Les sept, nommés une fois. Un signal absent de cette liste n'existe pas.
PROJET_MORT = "projet_mort"
ETAPE_FIGEE = "etape_figee"
ENGAGEMENT_IRREALISTE = "engagement_irrealiste"
CONCENTRATION = "concentration"
FIN_DE_SOIREE = "fin_de_soiree"
MIGRATION_SCROLL = "migration_scroll"
SUR_REGIME = "sur_regime"

# Les seuils du §13.5, tous écrits ici pour qu'aucun ne se cache dans une
# fonction. Les changer est une décision de produit, pas un réglage.
JOURS_PROJET_MORT = 10
JOURS_ETAPE_FIGEE = 21
SEMAINES_ENGAGEMENT = 3
PART_CONCENTRATION = 0.70
JOURS_FIN_DE_SOIREE = 10
RETARD_MINIMUM = 30            # minutes de dérive avant de dire quoi que ce soit
SESSIONS_SUR_REGIME = 3
JOURS_SUR_REGIME = 3

# En dessous, un pourcentage ne veut rien dire : 100 % d'une semaine à 25
# minutes n'est pas une dérive de concentration, c'est une semaine vide.
MINUTES_MINIMALES = 120


@dataclass(frozen=True)
class Derive:
    """Un constat. ``proposition`` est ce qu'on peut faire, en une phrase."""

    kind: str
    constat: str
    proposition: str
    donnees: dict = field(default_factory=dict)


def projet_mort(nom: str, jours_sans_session: int) -> Derive | None:
    """Projet actif laissé de côté depuis dix jours (§13.5).

    Pas de suppression, pas de rappel culpabilisant : une **proposition de
    sortie** au dimanche suivant. Un projet qu'on ne touche plus occupe un slot,
    et les slots sont la ressource rare du §4.3 — mais c'est à l'utilisateur de
    trancher, un projet peut dormir dix jours pour de bonnes raisons.
    """
    if jours_sans_session < JOURS_PROJET_MORT:
        return None
    return Derive(
        kind=PROJET_MORT,
        constat=f"{nom} : aucune session depuis {jours_sans_session} jours.",
        proposition="Le mettre au frigo libérerait son slot. À trancher dimanche.",
        donnees={"projet": nom, "jours": jours_sans_session},
    )


def etape_figee(nom: str, libelle: str, jours_en_cours: int) -> Derive | None:
    """Même étape « en cours » depuis trois semaines (§13.5).

    Le diagnostic du §4.5 est qu'une étape qui ne bouge pas est presque toujours
    une étape trop grosse, pas un manque de volonté. La proposition est donc de
    la découper, jamais de « s'y remettre ».
    """
    if jours_en_cours < JOURS_ETAPE_FIGEE:
        return None
    return Derive(
        kind=ETAPE_FIGEE,
        constat=f"« {libelle} » est en cours depuis {jours_en_cours} jours.",
        proposition="Une étape qui ne bouge pas est presque toujours trop grosse. La découper.",
        donnees={"projet": nom, "etape": libelle, "jours": jours_en_cours},
    )


def engagement_irrealiste(nom: str, semaines: list[tuple[int, int]]) -> Derive | None:
    """Engagement non tenu trois semaines de suite (§13.5).

    ``semaines`` va de la plus récente à la plus ancienne, en ``(tenues,
    prises)``. La proposition est **chiffrée** : la moyenne réellement faite,
    arrondie vers le bas, et jamais moins d'une. Ajuster l'engagement au réel
    observé est le geste du §5.3 ; le laisser à l'ambition déclarée fabrique
    trois échecs par mois.
    """
    recentes = semaines[:SEMAINES_ENGAGEMENT]
    if len(recentes) < SEMAINES_ENGAGEMENT:
        return None
    if any(tenues >= prises for tenues, prises in recentes):
        return None

    pris = recentes[0][1]
    moyenne = sum(tenues for tenues, _ in recentes) // len(recentes)
    cible = max(1, moyenne)
    if cible >= pris:
        return None

    return Derive(
        kind=ENGAGEMENT_IRREALISTE,
        constat=f"{nom} : {pris} sessions prises par semaine, jamais tenues depuis "
        f"{SEMAINES_ENGAGEMENT} semaines.",
        proposition=f"Descendre l'engagement à {cible}. Un engagement tenu vaut mieux qu'un affiché.",
        donnees={"projet": nom, "pris": pris, "propose": cible},
    )


def concentration(minutes_par_projet: dict[str, int]) -> Derive | None:
    """Plus de 70 % des heures de la semaine sur un seul projet (§13.5).

    Ce n'est pas une faute — une semaine de sprint sur un projet est parfois
    exactement ce qu'il faut. C'est un fait qui, répété, vide les autres slots
    et fait mourir les projets qui les occupent.
    """
    total = sum(minutes_par_projet.values())
    if total < MINUTES_MINIMALES or len(minutes_par_projet) < 2:
        return None

    nom, minutes = max(minutes_par_projet.items(), key=lambda item: item[1])
    part = minutes / total
    if part < PART_CONCENTRATION:
        return None

    return Derive(
        kind=CONCENTRATION,
        constat=f"{round(part * 100)} % des heures de la semaine sur {nom}.",
        proposition="Les autres projets s'éteignent doucement. Un créneau ailleurs suffit.",
        donnees={"projet": nom, "part": round(part, 2)},
    )


def fin_de_soiree(demarrages: list[tuple[date, int]]) -> Derive | None:
    """Les sessions démarrent de plus en plus tard sur dix jours glissants (§13.5).

    ``demarrages`` est une liste de ``(jour, minutes depuis minuit)``, dans
    l'ordre. On compare la première moitié à la seconde : une tendance, pas un
    écart isolé. Le signal a une valeur précise dans ce système — le §14 montre
    que le décrochage commence par des soirées qui glissent, pas par un arrêt
    net.
    """
    if len(demarrages) < JOURS_FIN_DE_SOIREE:
        return None

    recents = demarrages[-JOURS_FIN_DE_SOIREE:]
    moitie = len(recents) // 2
    avant = [minutes for _, minutes in recents[:moitie]]
    apres = [minutes for _, minutes in recents[moitie:]]

    # La **médiane**, pas la moyenne. Un seul soir à 22h30 déplace une moyenne de
    # cinq valeurs de quarante minutes et déclencherait le signal : on
    # annoncerait une dérive là où il y a une soirée. Ce qu'on cherche est un
    # rythme qui s'est déplacé, et il faut la moitié des soirs pour ça.
    retard = _mediane(apres) - _mediane(avant)
    if retard < RETARD_MINIMUM:
        return None

    return Derive(
        kind=FIN_DE_SOIREE,
        constat=f"Les sessions démarrent {round(retard)} minutes plus tard qu'il y a dix jours.",
        proposition="Le créneau glisse vers la fin de fenêtre. L'avancer d'une demi-heure.",
        donnees={"retard_minutes": round(retard)},
    )


def _mediane(valeurs: list[int]) -> float:
    tries = sorted(valeurs)
    milieu = len(tries) // 2
    if len(tries) % 2:
        return float(tries[milieu])
    return (tries[milieu - 1] + tries[milieu]) / 2


def migration_scroll(mobile_avant: int, mobile_apres: int, pc_avant: int, pc_apres: int) -> Derive | None:
    """Le scroll passe du PC au téléphone quand le blocage est armé (§13.5).

    Le contournement le plus probable, et celui qui doit rester visible : sans
    lui, le blocage se croit efficace alors qu'il a seulement déplacé la fuite.

    **Approximation assumée** : on compare deux fenêtres de sept jours plutôt
    que les seules heures réellement armées. L'état armé n'est pas historisé —
    il se recalcule —, et l'historiser pour ce seul usage coûterait plus que ce
    que la précision rapporte. Ce qui est cherché ici est un basculement franc,
    pas une corrélation fine.
    """
    if mobile_apres <= mobile_avant or pc_apres >= pc_avant:
        return None

    gagne = mobile_apres - mobile_avant
    perdu = pc_avant - pc_apres
    if gagne < 30 or gagne < perdu / 2:
        return None

    return Derive(
        kind=MIGRATION_SCROLL,
        constat=f"Le scroll PC baisse de {perdu} min, le téléphone monte de {gagne} min.",
        proposition="Le blocage déplace la fuite plus qu'il ne la ferme. Le DNS du téléphone la couvrirait.",
        donnees={"mobile_gagne": gagne, "pc_perdu": perdu},
    )


def sur_regime(sessions_par_jour: list[int]) -> Derive | None:
    """Plus de trois sessions par jour, trois jours de suite (§13.5).

    Le signal précoce du §0.2 : la motivation excessive du début, et le crash du
    jour 5 à 7 qu'elle prépare. C'est le seul de ces sept constats qui se
    déclenche pendant une **bonne** semaine, et c'est pour ça qu'il compte — il
    arrive avant que quoi que ce soit ait l'air d'aller mal.
    """
    if len(sessions_par_jour) < JOURS_SUR_REGIME:
        return None

    fenetre = sessions_par_jour[-JOURS_SUR_REGIME:]
    if any(n <= SESSIONS_SUR_REGIME for n in fenetre):
        return None

    return Derive(
        kind=SUR_REGIME,
        constat=f"{min(fenetre)} sessions ou plus par jour depuis {JOURS_SUR_REGIME} jours.",
        proposition="C'est le rythme qui précède l'arrêt du jour 6. Une soirée off, maintenant.",
        donnees={"jours": fenetre},
    )
