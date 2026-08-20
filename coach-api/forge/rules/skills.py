"""L'arbre de compétences (SPEC §12.9).

Le §12.9 dit exactement pourquoi cette mécanique existe, et ce n'est pas pour
faire joli :

> Rend visible ce qu'un compteur par projet cache : que 40h dispersées sur trois
> projets de moteur de jeu constituent quand même 40h de moteur de jeu.

C'est une correction de perception, pas une récompense. Quelqu'un qui a mené
trois prototypes UE5 de vingt heures chacun se voit trois projets inachevés ; le
même travail lu par branche donne soixante heures de moteur de jeu, ce qui est
la vérité. Le découragement du §0.2 se nourrit du premier récit alors que le
second est le bon.

**Une branche par domaine, jamais par projet.** Un projet abandonné ne retire
donc rien à sa branche : les heures ont été faites, la compétence a été
acquise, et le §17 interdit de reprendre du travail réel.

Les paliers montent en heures cumulées et ne redescendent jamais. Ils
débloquent un titre et un emblème — du cosmétique, conformément au §12.6 :
*aucune carte ne donne d'XP ni ne modifie une règle*.
"""

from __future__ import annotations

from dataclasses import dataclass

# Les branches techniques du §12.9. Les clés sont celles du champ
# ``Project.branch``, et le lien entre un projet et sa branche est une donnée du
# projet, pas une déduction depuis son nom.
MOTEUR_DE_JEU = "moteur_de_jeu"
CYBER = "cyber"
BACKEND = "backend"
DATA_RL = "data_rl"
CORPS = "corps"
WEB = "web"

# Les branches non techniques. L'arbre ne couvrait que du code et du corps, ce
# qui forçait un projet de cuisine ou de danse à se déclarer « backend » pour
# exister. Une branche fausse fausse tout ce qui en dérive — les heures
# cumulées, le palier, le titre —, et le §12.9 veut que quarante heures
# dispersées sur trois projets d'une même discipline restent quarante heures de
# cette discipline. Trois entrées suffisent : elles couvrent ce qui ne rentrait
# nulle part sans ouvrir un catalogue que personne ne maintiendrait.
SAVOIR = "savoir"          # cursus, cours, révisions, langues
ARTISANAT = "artisanat"    # cuisine, travail manuel, réparation
SCENE = "scene"            # danse, musique, jeu, prise de parole

BRANCHES = (
    MOTEUR_DE_JEU, CYBER, BACKEND, DATA_RL, WEB, CORPS,
    SAVOIR, ARTISANAT, SCENE,
)

BRANCH_LABELS = {
    MOTEUR_DE_JEU: "Moteur de jeu",
    CYBER: "Reverse & cyber",
    BACKEND: "Backend & web",
    DATA_RL: "Data & RL",
    WEB: "Web & interface",
    CORPS: "Corps",
    SAVOIR: "Savoir & cursus",
    ARTISANAT: "Artisanat & cuisine",
    SCENE: "Scène & interprétation",
}

# Chaque branche porte une couleur pour que l'arbre se lise d'un coup d'œil,
# sans légende. Elles restent dans la palette du §7.
BRANCH_COLORS = {
    MOTEUR_DE_JEU: "#8B6FE8",
    CYBER: "#4FC4B4",
    BACKEND: "#E8A33D",
    DATA_RL: "#5FA8DE",
    WEB: "#DE5F7E",
    CORPS: "#7ED08C",
    SAVOIR: "#C9A227",
    ARTISANAT: "#D2764A",
    SCENE: "#B06FD0",
}

# Les paliers du §12.9, en heures cumulées. La progression est délibérément
# géométrique : le premier palier tombe vite pour que l'arbre ne soit pas vide
# la première semaine, et le dernier est un objectif d'année.
TIER_HOURS = (10, 25, 50, 100, 200, 400)

# Un titre par palier et par branche. Ce sont les seuls mots que le système
# décerne à quelqu'un — ils se lisent comme un grade, pas comme un compliment
# (§0.2 : le système n'est pas là pour motiver).
TITLES: dict[str, tuple[str, ...]] = {
    MOTEUR_DE_JEU: ("Assembleur", "Bâtisseur de niveaux", "Machiniste", "Architecte du réel", "Démiurge", "Faiseur de mondes"),
    CYBER: ("Curieux", "Fouineur", "Démonteur", "Analyste", "Briseur de scellés", "Spectre"),
    BACKEND: ("Plombier", "Routier", "Ingénieur de flux", "Bâtisseur de socles", "Cartographe des systèmes", "Fondation"),
    DATA_RL: ("Observateur", "Statisticien", "Dresseur", "Modeleur", "Théoricien", "Oracle"),
    WEB: ("Maquettiste", "Façonneur", "Compositeur", "Metteur en scène", "Styliste du réel", "Vitrail"),
    CORPS: ("Debout", "Régulier", "Endurant", "Aguerri", "Increvable", "Airain"),
    SAVOIR: ("Lecteur", "Étudiant", "Praticien", "Érudit", "Spécialiste", "Autorité"),
    ARTISANAT: ("Apprenti", "Tourne-main", "Façonnier", "Compagnon", "Maître d'œuvre", "Main sûre"),
    SCENE: ("Débutant", "Répétiteur", "Exécutant", "Interprète", "Soliste", "Présence"),
}

# Un emblème par palier, commun à toutes les branches : la forme dit le niveau,
# la couleur dit la branche. Deux informations, aucune légende.
TIER_EMBLEMS = ("◦", "◇", "◆", "❖", "✦", "✵")


@dataclass(frozen=True)
class BranchState:
    """L'état d'une branche. Tout est dérivé des heures, rien n'est stocké."""

    key: str
    label: str
    color: str
    minutes: int
    tier: int                      # 0 = aucun palier atteint
    title: str
    emblem: str
    next_hours: int | None         # None quand le dernier palier est atteint
    progress: float                # 0..1 vers le palier suivant

    @property
    def hours(self) -> float:
        return round(self.minutes / 60, 1)

    @property
    def maxed(self) -> bool:
        return self.next_hours is None


def tier_for(minutes: int) -> int:
    """Le palier atteint, de 0 à 6. Ne redescend jamais — les heures sont faites."""
    heures = minutes / 60
    return sum(1 for seuil in TIER_HOURS if heures >= seuil)


def branch_state(key: str, minutes: int) -> BranchState:
    """L'état complet d'une branche pour un total de minutes."""
    palier = tier_for(minutes)
    heures = minutes / 60

    if palier >= len(TIER_HOURS):
        suivant, progression = None, 1.0
    else:
        suivant = TIER_HOURS[palier]
        precedent = TIER_HOURS[palier - 1] if palier else 0
        largeur = suivant - precedent
        progression = min(1.0, max(0.0, (heures - precedent) / largeur)) if largeur else 0.0

    return BranchState(
        key=key,
        label=BRANCH_LABELS.get(key, key),
        color=BRANCH_COLORS.get(key, "#9A8CAE"),
        minutes=minutes,
        tier=palier,
        title=TITLES.get(key, ("",) * 6)[palier - 1] if palier else "",
        emblem=TIER_EMBLEMS[palier - 1] if palier else "",
        next_hours=suivant,
        progress=round(progression, 3),
    )


def tree(minutes_by_branch: dict[str, int]) -> list[BranchState]:
    """L'arbre entier, branches vides comprises.

    Les branches à zéro sont rendues **exprès**. Une branche vide n'est pas une
    absence de donnée : c'est l'information la plus utile de l'écran, celle qui
    dit ce qui n'a pas été touché depuis des semaines. La revue de saison
    l'appelle « la forme de l'arbre : ce qui pousse, ce qui est à l'arrêt ».
    """
    return [branch_state(cle, minutes_by_branch.get(cle, 0)) for cle in BRANCHES]


def newly_reached(before_minutes: int, after_minutes: int) -> int | None:
    """Le palier franchi entre deux totaux, ou ``None``.

    Sert à déclencher la séquence de juice au bon moment, et une seule fois :
    c'est le franchissement qui se fête, pas l'état.
    """
    avant, apres = tier_for(before_minutes), tier_for(after_minutes)
    return apres if apres > avant else None


def shape(states: list[BranchState]) -> dict:
    """La forme de l'arbre pour la revue de saison (§12.9).

    Rend les deux faits qu'on veut voir : ce qui domine, et ce qui est à
    l'arrêt. La dispersion dit si le travail est concentré ou éparpillé — sans
    jugement attaché, parce que les deux sont légitimes selon le moment.
    """
    actives = [s for s in states if s.minutes > 0]
    total = sum(s.minutes for s in states)

    return {
        "total_minutes": total,
        "branches_actives": len(actives),
        "dominante": max(actives, key=lambda s: s.minutes).key if actives else None,
        "a_l_arret": [s.key for s in states if s.minutes == 0],
        # Part de la branche dominante. Proche de 1 : tout est au même endroit.
        "concentration": (
            round(max(s.minutes for s in actives) / total, 3) if total else 0.0
        ),
    }
