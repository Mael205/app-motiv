"""Saisons : identité, boss, modificateurs, fantôme.

Le moteur narratif du produit (SPEC §12). Une saison dure 4 semaines, porte un
nom et une couleur, un boss dont la vie descend avec le travail réel, un
modificateur qui change les règles, et un fantôme — la courbe d'une saison
passée — auquel se comparer jour après jour.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from . import years

SEASON_DAYS = 28
SEASON_PAUSE_DAYS = 2

# La saison d'essai. Index 0, et elle est la seule à porter ce numéro : les
# saisons réelles commencent à 1 et se suivent.
#
# Elle existe pour une raison précise. Découvrir le système coûte quelques
# jours — on règle ses créneaux, on comprend les boucliers, on rate une soirée
# pour une mauvaise raison. Faire porter ces jours-là par une vraie saison
# fausse tout ce qui vient après : le boss de la saison suivante se dimensionne
# sur le score précédent (§12.4), et le fantôme se choisit parmi les saisons
# passées (§12.7). Une saison d'apprentissage rangée parmi les vraies devient
# donc un adversaire artificiellement faible, pour toujours.
#
# D'où la règle : **une saison d'essai ne se compare jamais.** Elle ne
# dimensionne aucun boss, elle n'entre dans aucun réservoir de fantômes, et sa
# mise vaut zéro — il n'y a rien à perdre sur une saison qui ne compte pas.
# Elle garde en revanche ses sessions, son XP et ses cartes : le §17 interdit
# d'effacer du travail réel, et le travail d'un essai reste du travail.
ESSAI_INDEX = 0


def est_essai(index: int) -> bool:
    """Cette saison compte-t-elle dans les comparaisons ?"""
    return index == ESSAI_INDEX

# --------------------------------------------------------------------------
# La trame : deux voies, et c'est la saison précédente qui décide de la tienne
# --------------------------------------------------------------------------
#
# **L'ordre était tiré au sort ; il raconte maintenant quelque chose** (20 août
# 2026). Les identités sortaient d'une permutation qui changeait chaque année,
# pour que deux années ne se ressemblent pas. Ça marchait comme anti-répétition
# et ratait tout le reste : une saison tombait sans rapport avec la précédente,
# et son nom n'était qu'une étiquette de couleur. Douze étiquettes tirées au
# sort ne font pas une histoire, et le §0.10 dit que ce qui n'a pas d'identité
# ne se garde pas.
#
# ## Deux voies, pas une
#
# Une trame unique aurait raconté la même chose à tout le monde, quoi qu'il se
# soit passé. Or le produit sait déjà distinguer une saison tenue d'une saison
# ratée — c'est ce que le §12.6 tranche pour résoudre la mise. La trame suit
# donc ce résultat :
#
#   **Voie des Cimes** — après une saison tenue. Ça s'ouvre, ça monte, ça finit
#   en haut : l'éveil, la faille, le méridien franchi, le sommet.
#
#   **Voie des Braises** — après une saison ratée. Ça descend jusqu'au fond,
#   puis ça creuse et ça forge : Nadir, le purgatoire, le rempart, l'enclume.
#
# **La voie basse n'est pas une punition, et c'est la condition pour qu'elle
# soit tenable.** Elle ne retire rien : même mise, même boss, mêmes règles. Le
# §17 interdit d'ajouter une sanction, et une histoire qui punirait doublerait
# celle qui a déjà été payée. Ce qui change est le décor — un mois raté raconté
# comme une descente aux forges est plus juste, et surtout plus tenable, qu'un
# mois raté raconté avec les mots d'un sommet.
#
# **Chaque voie avance à son propre rythme.** On ne saute pas de la troisième
# saison des Cimes à la troisième des Braises : on reprend la voie basse là où
# on l'avait laissée. Une année en dents de scie tricote donc les deux, et deux
# parcours n'ont jamais la même suite — sans qu'aucun tirage n'intervienne.
#
# Le **boss**, lui, reste tiré d'un tour à l'autre. La trame dit ce qu'on
# traverse, pas qui l'on affronte.
VOIE_CIMES = "cimes"
VOIE_BRAISES = "braises"

VOIES: dict[str, dict] = {
    VOIE_CIMES: {
        "nom": "Voie des Cimes",
        "ligne": "La saison a été tenue. Ça monte.",
        "actes": {1: "Le Seuil", 2: "La Montée"},
    },
    VOIE_BRAISES: {
        "nom": "Voie des Braises",
        "ligne": "La saison n'a pas été tenue. Ça descend, puis ça forge.",
        "actes": {1: "La Descente", 2: "La Forge"},
    },
}

TRAME: dict[str, tuple[dict, ...]] = {
    # ---- VOIE DES CIMES ----------------------------------------------------
    VOIE_CIMES: (
        # Acte I — Le Seuil
        {"key": "eveil", "name": "L'Éveil", "accent": "#8FD14F", "acte": 1, "registre": "éveil",
         "baseline": "Ce qui dormait se lève. À toi de savoir quoi."},
        {"key": "faille_s", "name": "Faille S", "accent": "#43D9E0", "acte": 1, "registre": "sci-fi",
         "baseline": "La faille est ouverte. Rang S ou rien."},
        {"key": "meridien", "name": "Méridien", "accent": "#E8B44A", "acte": 1, "registre": "navigation",
         "baseline": "Une ligne, et tout ce qui est à l'ouest est derrière."},
        {"key": "prisme", "name": "Prisme", "accent": "#5FD6B4", "acte": 1, "registre": "sci-fi",
         "baseline": "Une lumière entre, six sortent."},
        {"key": "vigie", "name": "Vigie", "accent": "#4FC4B4", "acte": 1, "registre": "sobriété",
         "baseline": "Tenir le poste. Rien de plus, rien de moins."},
        {"key": "marche_haute", "name": "Marche Haute", "accent": "#B8C46A", "acte": 1, "registre": "montagne",
         "baseline": "Celle qu'on monte à contrecœur, et qu'on ne redescend pas."},
        # Acte II — La Montée
        {"key": "orbite_basse", "name": "Orbite Basse", "accent": "#4FA3E0", "acte": 2, "registre": "sci-fi",
         "baseline": "Assez haut pour voir, assez bas pour retomber."},
        {"key": "sanctuaire", "name": "Sanctuaire", "accent": "#C8A2D8", "acte": 2, "registre": "dark fantasy",
         "baseline": "L'endroit qu'on défend n'est pas celui où l'on dort."},
        {"key": "aube_rouge", "name": "Aube Rouge", "accent": "#D1403F", "acte": 2, "registre": "épique",
         "baseline": "Vingt-huit levers. Compte-les."},
        {"key": "hellfest", "name": "Hellfest", "accent": "#E0533D", "acte": 2, "registre": "métal",
         "baseline": "Quatre semaines. Le feu ne demande pas la permission."},
        {"key": "ragnarok", "name": "Ragnarök", "accent": "#8FA9C4", "acte": 2, "registre": "nordique",
         "baseline": "Tout finit. La question est ce que tu auras bâti avant."},
        {"key": "heavens_paradise", "name": "Heaven's Paradise", "accent": "#F2E6C2", "acte": 2,
         "registre": "métal céleste", "baseline": "On monte, ou on regarde monter."},
    ),
    # ---- VOIE DES BRAISES --------------------------------------------------
    VOIE_BRAISES: (
        # Acte I — La Descente
        {"key": "nadir", "name": "Nadir", "accent": "#3E6FA8", "acte": 1, "registre": "sci-fi froid",
         "baseline": "Le point le plus bas est un point de départ comme un autre."},
        {"key": "purgatoire", "name": "Purgatoire", "accent": "#8A6FB0", "acte": 1, "registre": "dark fantasy",
         "baseline": "Ni en haut, ni en bas. Vingt-huit jours pour trancher."},
        {"key": "quartier_nord", "name": "Quartier Nord", "accent": "#7A8FA6", "acte": 1, "registre": "urbain",
         "baseline": "Personne ne vient te chercher ici."},
        {"key": "obsidienne", "name": "Obsidienne", "accent": "#6E5B8F", "acte": 1, "registre": "minéral",
         "baseline": "Le verre volcanique casse net. Pas avant."},
        {"key": "solstice_noir", "name": "Solstice Noir", "accent": "#B98A2E", "acte": 1, "registre": "dark fantasy",
         "baseline": "La nuit la plus longue se travaille."},
        {"key": "cendre_haute", "name": "Cendre Haute", "accent": "#A89484", "acte": 1, "registre": "post-apo",
         "baseline": "Ce qui a brûlé fertilise ou stérilise. Ça se décide maintenant."},
        # Acte II — La Forge
        {"key": "dernier_rempart", "name": "Dernier Rempart", "accent": "#C0574F", "acte": 2, "registre": "siège",
         "baseline": "Ils passeront par toi."},
        {"key": "acier_froid", "name": "Acier Froid", "accent": "#9FB3C8", "acte": 2, "registre": "forge",
         "baseline": "On trempe ce qui a été chauffé."},
        {"key": "veine_mere", "name": "Veine Mère", "accent": "#C98F3A", "acte": 2, "registre": "mine",
         "baseline": "Vingt-huit jours à creuser au même endroit."},
        {"key": "derniere_forge", "name": "Dernière Forge", "accent": "#E0703D", "acte": 2, "registre": "forge",
         "baseline": "Le feu s'éteint à la fin du mois. Pas avant."},
        {"key": "tonnerre", "name": "Tonnerre", "accent": "#D6543C", "acte": 2, "registre": "métal",
         "baseline": "Le bruit arrive après. Toujours."},
        {"key": "inferno", "name": "Inferno", "accent": "#F07A20", "acte": 2, "registre": "métal",
         "baseline": "Ça chauffe à partir de maintenant."},
    ),
}

# Le catalogue à plat. Il ne sert qu'aux vérifications d'ensemble — unicité des
# clés, couverture des emblèmes — jamais au tirage.
SEASON_POOL: tuple[dict, ...] = TRAME[VOIE_CIMES] + TRAME[VOIE_BRAISES]

SAISONS_PAR_VOIE = len(TRAME[VOIE_CIMES])


def voie_apres(reussie: bool | None) -> str:
    """La voie qu'ouvre le résultat de la saison précédente.

    ``None`` — aucune saison avant, ou résultat inconnu — mène aux Cimes : on
    commence par l'éveil, pas par le fond.
    """
    return VOIE_BRAISES if reussie is False else VOIE_CIMES


def identite_de_voie(voie: str, position: int) -> dict:
    """L'identité à cette position de cette voie. Les deux bouclent à douze.

    ``position`` est le **nombre de saisons déjà passées sur cette voie**, pas
    l'index de la saison. Reprendre la voie basse là où on l'avait laissée est
    ce qui fait qu'une année en dents de scie raconte une suite plutôt qu'un
    tirage.
    """
    ligne = TRAME.get(voie) or TRAME[VOIE_CIMES]
    return ligne[max(0, position) % len(ligne)]


def acte_de_voie(voie: str, position: int) -> dict:
    """L'acte auquel appartient une position : son numéro, son nom, sa voie."""
    identite = identite_de_voie(voie, position)
    infos = VOIES.get(voie) or VOIES[VOIE_CIMES]
    numero = identite.get("acte", 1)
    return {
        "numero": numero,
        "nom": infos["actes"].get(numero, ""),
        "total": len(infos["actes"]),
        "voie": voie,
        "voie_nom": infos["nom"],
        "voie_ligne": infos["ligne"],
    }


# Modificateurs façon roguelike : trois sont proposés, un seul est choisi — cinq
# après la voie « Écho » de l'ascendance. Douze entrées pour que deux saisons
# consécutives ne se ressemblent pas : avec six, le tirage de trois recouvrait la
# moitié du catalogue à chaque fois.
#
# **Aucun ne rend le jeu plus facile sans contrepartie.** Chacun déplace une
# contrainte : ce qu'il donne d'un côté, il le reprend de l'autre. Un
# modificateur purement favorable serait celui qu'on choisirait toujours, et le
# choix du §12.5 n'existerait plus.
MODIFIERS: tuple[dict, ...] = (
    {"key": "aube", "name": "Aube", "effet": "XP ×1,3 avant 20h, mais le gardien passe à 21h.",
     "params": {"early_multiplier": 1.3, "guardian_hour": 21}},
    {"key": "marathon", "name": "Marathon", "effet": "Sessions de 50 min ×1,5. Mode dégradé désactivé.",
     "params": {"long_multiplier": 1.5, "degraded_enabled": False}},
    {"key": "fragmentation", "name": "Fragmentation", "effet": "Quatre sessions comptent au lieu de trois.",
     "params": {"full_xp_sessions": 4}},
    {"key": "siege", "name": "Siège", "effet": "Le boss a 20 % de vie en plus, la mise est doublée.",
     "params": {"boss_hp_multiplier": 1.2, "stake_multiplier": 2}},
    {"key": "discipline", "name": "Discipline", "effet": "Aucun jour off, mais un bouclier de plus au départ.",
     "params": {"days_off_allowed": 0, "starting_shields": 3}},
    {"key": "deux_fronts", "name": "Deux fronts", "effet": "La piste Corps inflige des dégâts doubles au boss.",
     "params": {"body_damage_multiplier": 2}},
    {"key": "veille_haute", "name": "Veille haute", "effet": "Le gardien passe à 22h, mais le boss a 15 % de vie en plus.",
     "params": {"guardian_hour": 22, "boss_hp_multiplier": 1.15}},
    {"key": "premiere_lumiere", "name": "Première lumière", "effet": "XP ×1,5 avant 18h. Après 22h, plus rien ne compte.",
     "params": {"early_multiplier": 1.5, "guardian_hour": 20}},
    {"key": "austerite", "name": "Austérité", "effet": "Une seule session compte plein par jour, mais la mise est triplée.",
     "params": {"full_xp_sessions": 1, "stake_multiplier": 3}},
    {"key": "forge", "name": "Forge", "effet": "Sessions de 50 min ×1,3 et boss à 130 % de vie.",
     "params": {"long_multiplier": 1.3, "boss_hp_multiplier": 1.3}},
    {"key": "corde_raide", "name": "Corde raide", "effet": "Aucun bouclier au départ, mais le boss n'a que 80 % de vie.",
     "params": {"starting_shields": 0, "boss_hp_multiplier": 0.8}},
    {"key": "clemence", "name": "Clémence", "effet": "Trois jours off par semaine, et le mode dégradé disparaît.",
     "params": {"days_off_allowed": 3, "degraded_enabled": False}},
)

# Douze boss pour douze saisons : chaque saison de l'année a le sien, et on ne
# revoit pas le même adversaire deux fois en un an. Six suffisaient tant qu'une
# année n'existait pas ; avec elle, ils seraient revenus tous les six mois.
#
# Chacun nomme une façon précise de ne pas travailler. C'est le point : un boss
# qui s'appellerait « la Paresse » ne dirait rien, alors que « le Veilleur de
# 23h » se reconnaît le soir même où on le rencontre.
BOSSES: tuple[dict, ...] = (
    {"key": "procrastin", "name": "Procrastin, l'Ajourneur"},
    {"key": "scrollhydre", "name": "La Scroll-Hydre"},
    {"key": "veilleur", "name": "Le Veilleur de 23h"},
    {"key": "eparpilleur", "name": "L'Éparpilleur"},
    {"key": "jour_six", "name": "Jour Six"},
    {"key": "brouillard", "name": "Le Brouillard"},
    {"key": "presque_pret", "name": "Presque Prêt"},
    {"key": "grand_refacteur", "name": "Le Grand Refacteur"},
    {"key": "onglet_trente", "name": "L'Onglet Trente"},
    {"key": "demain_matin", "name": "Demain Matin"},
    {"key": "collectionneur", "name": "Le Collectionneur de Débuts"},
    {"key": "juste_un_episode", "name": "Juste Un Épisode"},

    # -- Second réservoir, pour la même raison que les identités : douze boss
    # tenaient exactement une année, donc le treizième mois ramenait Procrastin.
    # Chacun continue de nommer une façon précise de ne pas travailler — c'est
    # ce qui fait qu'on le reconnaît le soir où on le rencontre, et un boss
    # abstrait ne se reconnaît jamais.
    {"key": "encore_cinq", "name": "Encore Cinq Minutes"},
    {"key": "grand_nettoyage", "name": "Le Grand Nettoyage"},
    {"key": "tutoriel_sans_fin", "name": "Le Tutoriel Sans Fin"},
    {"key": "outil_parfait", "name": "L'Outil Parfait"},
    {"key": "veille_technologique", "name": "La Veille Technologique"},
    {"key": "pas_le_bon_moment", "name": "Pas Le Bon Moment"},
    {"key": "quand_j_aurai", "name": "Quand J'aurai Le Temps"},
    {"key": "second_ecran", "name": "Le Second Écran"},
    {"key": "refonte_totale", "name": "La Refonte Totale"},
    {"key": "avis_des_autres", "name": "L'Avis Des Autres"},
    {"key": "dimanche_soir", "name": "Dimanche Soir"},
    {"key": "presque_fini", "name": "Presque Fini"},
)

# Dégâts infligés au boss, en points. Une minute travaillée = un point ; une
# étape de roadmap terminée pèse une heure ; un engagement tenu, trois quarts.
DAMAGE_PER_MINUTE = 1
DAMAGE_PER_STEP = 60
DAMAGE_PER_COMMITMENT = 45
BOSS_REGEN_ON_MISSED_DAY = 45     # sanction du palier 1 (SPEC §14)


@dataclass(frozen=True)
class SeasonPlan:
    index: int
    key: str
    name: str
    accent: str
    baseline: str
    boss_key: str
    boss_name: str
    boss_hp: int
    modifier_key: str
    starts_on: date
    ends_on: date

    @property
    def days_total(self) -> int:
        return (self.ends_on - self.starts_on).days + 1

    @property
    def year(self) -> int:
        return years.annee_de(self.index)

    @property
    def rank_in_year(self) -> int:
        return years.rang_dans_l_annee(self.index)

    @property
    def closes_the_year(self) -> bool:
        return years.ferme_l_annee(self.index)


def pick_identity(index: int, *, voie: str = VOIE_CIMES, position: int | None = None) -> dict:
    """L'identité d'une saison : sa voie, et sa place sur cette voie.

    ``position`` est le nombre de saisons déjà passées sur ``voie``. Quand elle
    n'est pas fournie — un appel qui ne connaît que l'index, comme la saison
    d'essai — on retombe sur le rang dans l'année, ce qui donne le début de la
    voie haute : l'éveil.
    """
    if position is None:
        position = years.rang_dans_l_annee(index) - 1
    return identite_de_voie(voie, position)


def pick_boss(index: int) -> dict:
    """Le boss d'une saison. Un par saison de l'année, jamais deux fois.

    Le tirage est décalé d'un tour par rapport aux identités : sans ce décalage,
    « Hellfest » affronterait Procrastin chaque année, et les deux catalogues
    n'en formeraient plus qu'un.
    """
    return BOSSES[
        years.place_dans_le_reservoir(
            years.annee_de(index), years.rang_dans_l_annee(index), len(BOSSES), decalage=1
        )
    ]


def propose_modifiers(index: int, count: int = 3) -> list[dict]:
    """Trois modificateurs proposés à l'ouverture — un choix, pas une subissance."""
    start = (index * count) % len(MODIFIERS)
    doubled = list(MODIFIERS) * 2
    return doubled[start : start + count]


def boss_hp(previous_score: int | None, contract_sessions_per_week: int = 3) -> int:
    """Vie du boss : la saison précédente + 5 %, ou l'estimation du contrat."""
    if previous_score:
        return int(previous_score * 1.05)
    estimate = contract_sessions_per_week * 4 * 25 * DAMAGE_PER_MINUTE
    return max(1500, estimate)


def damage_of(minutes: int = 0, steps_done: int = 0, commitments_kept: int = 0) -> int:
    return (
        minutes * DAMAGE_PER_MINUTE
        + steps_done * DAMAGE_PER_STEP
        + commitments_kept * DAMAGE_PER_COMMITMENT
    )


def plan_season(
    index: int,
    starts_on: date,
    *,
    previous_score: int | None = None,
    contract_sessions_per_week: int = 3,
    identite: dict | None = None,
) -> SeasonPlan:
    """Le plan d'une saison. ``contract_sessions_per_week`` ne sert qu'à la
    première : sans score précédent, la seule estimation honnête du volume à
    venir est celle que quelqu'un vient d'annoncer en signant son contrat."""
    identity = identite or pick_identity(index)
    boss = pick_boss(index)
    return SeasonPlan(
        index=index,
        key=identity["key"],
        name=identity["name"],
        accent=identity["accent"],
        baseline=identity["baseline"],
        boss_key=boss["key"],
        boss_name=boss["name"],
        boss_hp=boss_hp(previous_score, contract_sessions_per_week),
        modifier_key=propose_modifiers(index)[0]["key"],
        starts_on=starts_on,
        ends_on=starts_on + timedelta(days=SEASON_DAYS - 1),
    )


def next_season_start(ends_on: date) -> date:
    """Deux jours de pause explicite entre deux saisons (jours neutres)."""
    return ends_on + timedelta(days=SEASON_PAUSE_DAYS + 1)


# --------------------------------------------------------------------------
# Le dernier round (ajout du 17 août 2026)
# --------------------------------------------------------------------------

FINAL_ROUND_DAYS = 3
FINAL_ROUND_SESSION_MINUTES = 25


@dataclass(frozen=True)
class FinalRound:
    """La vie du boss traduite en sessions, les trois derniers jours.

    **Informatif seulement, et c'est la décision qui fait tout le reste.** Un
    bonus de fin de saison — dégâts doublés, XP majorée, mise récupérable —
    encouragerait trois soirées de rattrapage à quatre sessions, c'est-à-dire
    exactement le sur-régime du §0.2, et il le ferait au pire moment : celui où
    la saison suivante s'ouvre le lendemain. Ce module ne rend donc **aucun
    multiplicateur**. Il change une unité, rien d'autre.

    Le changement d'unité est tout ce qu'on peut honnêtement offrir. « 2 340
    points de vie » ne se compare à rien ; « quatre sessions » se compare à une
    soirée, et la comparaison se fait toute seule — on sait si on peut ou non,
    et personne n'a eu besoin de le dire.
    """

    active: bool
    days_left: int
    sessions_left: int
    minutes_left: int
    session_minutes: int
    reachable: bool
    line: str


def final_round(
    *,
    days_left: int,
    current_hp: int,
    is_dead: bool = False,
    session_minutes: int = FINAL_ROUND_SESSION_MINUTES,
    sessions_per_day: int = 3,
) -> FinalRound:
    """Traduit la vie restante en sessions, dans les trois derniers jours.

    ``reachable`` compare le nombre de sessions nécessaires au plafond de régime
    (§0.2) sur les jours qui restent : au-delà, le boss ne tombera pas, et le
    dire est plus honnête que de laisser espérer. Ce n'est pas un reproche —
    c'est la même information, avec sa borne.
    """
    par_session = max(1, session_minutes * DAMAGE_PER_MINUTE)
    restantes = 0 if is_dead else -(-max(0, current_hp) // par_session)
    possible = max(0, days_left) * max(1, sessions_per_day)

    if is_dead:
        ligne = "Dernier round — il est déjà tombé. Ce qui suit est du rab."
    elif restantes <= possible:
        pluriel = "s" if restantes > 1 else ""
        ligne = (
            f"Dernier round — {restantes} session{pluriel} de {session_minutes} min "
            f"pour l'abattre, {days_left} jour{'s' if days_left > 1 else ''} devant."
        )
    else:
        ligne = (
            f"Dernier round — il faudrait {restantes} sessions en {days_left} "
            f"jour{'s' if days_left > 1 else ''}. Il tiendra jusqu'au bout."
        )

    return FinalRound(
        active=0 <= days_left <= FINAL_ROUND_DAYS,
        days_left=max(0, days_left),
        sessions_left=restantes,
        minutes_left=0 if is_dead else max(0, current_hp) // max(1, DAMAGE_PER_MINUTE),
        session_minutes=session_minutes,
        reachable=is_dead or restantes <= possible,
        line=ligne,
    )


def ghost_delta(day_index: int, mine: list[int], ghost: list[int]) -> int:
    """Écart au fantôme à un jour donné, en points cumulés (SPEC §12.7)."""
    def at(curve: list[int]) -> int:
        if not curve:
            return 0
        return curve[min(day_index, len(curve) - 1)]

    return at(mine) - at(ghost)


def title_for(score_ratio: float, season_name: str) -> str:
    """Titre décerné à la clôture. Le titre raté existe aussi, sans humiliation."""
    if score_ratio >= 1.0:
        return f"Vainqueur de {season_name}"
    if score_ratio >= 0.7:
        return f"Survivant de {season_name}"
    if score_ratio >= 0.3:
        return f"Vétéran de {season_name}"
    return f"Déserteur de {season_name}"
