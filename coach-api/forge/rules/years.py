"""L'année de douze saisons, et l'ascendance qui la clôt (§12.2 étendu).

Une saison dure 28 jours plus 2 de pause : trente jours. Douze saisons font
donc trois cent soixante jours — une année, à cinq jours près. L'année du coach
dérive doucement du calendrier, et c'est le choix le plus simple : la douzième
saison n'a aucun traitement à part, pas de boss à redimensionner, pas de
contrat tronqué.

## Deux horizons qui bougent, aucune donnée qui disparaît

**L'XP et le niveau repartent.** Pas parce qu'ils sont mérités à moitié, mais
parce qu'ils cessent de vouloir dire quelque chose : entre le niveau 41 et le
42, il n'y a plus d'information. Une courbe qui ne monte plus perceptiblement ne
mesure plus rien. La remettre à plat lui rend sa lisibilité.

**Le rang repart aussi.** Il se recompte sur les semaines tenues depuis
l'ascendance : on redescend en F et on regravit — vite, parce qu'on sait
comment. C'est le seul endroit où l'année deux est *plus simple* que la fin de
l'année une, et c'est voulu : un prestige qui ne rend rien à regagner n'est
qu'une remise à zéro.

**Mais les slots acquis sont gravés.** Le rang les reprendrait, et le §4.3
l'interdit — « les projets ne sont pas supprimés ». Un rang remis à zéro qui
retirerait deux slots gèlerait deux projets en cours du jour au lendemain. Les
slots sont donc la seule récompense de rang qui devienne permanente à
l'ascendance ; les boucliers, les jours off et le plancher, eux, se regagnent.

**Rien n'est effacé.** Les deux resets déplacent un horizon de calcul, ils ne
suppriment aucune session ni aucune semaine : la trace longue continue de porter
le cumul de toujours. C'est la seule façon de faire un reset sans mentir sur le
passé, et le §17 ne laisse pas le choix. L'arbre, les reliques, la collection et
les hauts faits ne bougent pas non plus — l'arbre compte des heures réellement
travaillées (§12.9), les remettre à zéro serait un mensonge sur ce qui a eu lieu.

## Ce qu'une voie a le droit de donner

Dans la plupart des jeux, le prestige rend la partie suivante plus facile *et*
plus riche : on regagne ce qu'on avait, mais on débloque des systèmes qui
n'existaient pas. C'est la seconde moitié qui compte ici, parce que la première
seule serait absurde — le produit existe pour tenir un cadre, pas pour l'abaisser
une fois qu'on a tenu un an.

D'où la règle, et c'est la seule qui compte dans ce module :

> **Une voie ouvre une mécanique, une capacité ou un choix. Jamais de la
> puissance.**

Un slot de plus n'est pas un avantage : c'est un projet de plus à tenir, et le
rang exige que *tous* les engagements d'une semaine soient tenus — donc une
chance de plus de rater la semaine. Cinq modificateurs au lieu de trois, ce
n'est pas un meilleur modificateur, c'est un choix plus large. La Forge ne
distribue rien : elle donne enfin une dépense à une monnaie qui ne faisait que
monter. Le plancher qui remonte est une exigence assumée, payée en Éclats —
c'est-à-dire en cosmétique, la seule chose que le système puisse donner sans
fausser sa propre mesure.

Une voie se prend **une fois** et ne se reprend jamais. Aucune n'est réversible :
choisir compte, sinon ce n'est pas un choix.
"""

from __future__ import annotations

from dataclasses import dataclass

SAISONS_PAR_AN = 12


def annee_de(index: int) -> int:
    """L'année à laquelle appartient une saison. La première année est 1."""
    return ((max(1, index) - 1) // SAISONS_PAR_AN) + 1


def rang_dans_l_annee(index: int) -> int:
    """Le numéro de la saison dans son année, de 1 à 12."""
    return ((max(1, index) - 1) % SAISONS_PAR_AN) + 1


def ferme_l_annee(index: int) -> bool:
    """Cette saison est-elle la douzième de son année ?"""
    return rang_dans_l_annee(index) == SAISONS_PAR_AN


def saisons_restantes(index: int) -> int:
    """Combien de saisons avant la fin de l'année en cours, celle-ci comprise."""
    return SAISONS_PAR_AN - rang_dans_l_annee(index) + 1


def ordre_des_identites(annee: int, total: int) -> list[int]:
    """L'ordre dans lequel les identités de saison sortent, pour une année donnée.

    Chaque identité sort **exactement une fois par an**, ce qui rend l'année
    lisible : arrivé à la neuvième, il en reste trois, et on les a toutes vues
    à la fin. Un tirage libre produirait des répétitions et des absences, et
    l'année ne se compterait plus.

    L'ordre change d'une année à l'autre par un pas premier avec le total —
    la deuxième année ne rejoue donc pas la première dans le même ordre, sans
    qu'il faille stocker quoi que ce soit.
    """
    if total <= 0:
        return []
    pas = _pas_premier_avec(total, annee)
    depart = (annee * 5) % total
    return [(depart + i * pas) % total for i in range(total)]


def place_dans_le_reservoir(annee: int, rang: int, total: int, *, decalage: int = 0) -> int:
    """L'indice tiré du réservoir pour la ``rang``-ième saison d'une année.

    Un réservoir **plus grand qu'une année** (J6) ne se consomme pas en un an :
    il se vide sur plusieurs années avant d'être rebattu. Vingt-quatre identités
    pour douze saisons donnent donc deux ans de noms inédits, puis un nouveau
    tirage d'ordre.

    C'est la correction d'un défaut qui n'apparaissait qu'en agrandissant le
    catalogue : réutiliser ``ordre_des_identites`` par année et n'en garder que
    les douze premières places donnait deux progressions arithmétiques
    différentes sur le même cycle — qui se recouvrent largement. On voyait donc
    revenir la moitié des noms l'année suivante, alors qu'il y avait douze
    identités inutilisées dans le réservoir.

    ``decalage`` décale le tirage d'un tour, pour que deux catalogues de même
    taille — les identités et les boss — ne s'apparient pas à l'identique
    d'une année sur l'autre.

    Suppose que ``total`` soit un multiple de ``SAISONS_PAR_AN`` ; sinon une
    année finirait à cheval sur deux tours, et une identité pourrait sortir
    deux fois dans les douze.
    """
    if total <= 0:
        return 0

    annees_par_tour = max(1, total // SAISONS_PAR_AN)
    tour = (annee - 1) // annees_par_tour
    annee_dans_le_tour = (annee - 1) % annees_par_tour
    ordre = ordre_des_identites(tour + 1 + decalage, total)
    return ordre[(annee_dans_le_tour * SAISONS_PAR_AN + rang - 1) % total]


def _pas_premier_avec(total: int, annee: int) -> int:
    """Un pas qui parcourt tout le cycle sans jamais retomber avant la fin.

    Choisi **parmi tous** les pas possibles et non au premier trouvé : la
    première version prenait toujours le même, et l'année deux rejouait alors
    l'année une simplement décalée — mêmes voisinages, même impression de
    répétition. Sur douze identités, quatre pas et douze départs donnent
    quarante-huit ordres distincts, ce qui suffit largement.
    """
    possibles = [pas for pas in range(1, total) if _pgcd(pas, total) == 1] or [1]
    return possibles[(annee - 1) % len(possibles)]


def _pgcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a


# --------------------------------------------------------------------------
# Les voies d'ascendance
# --------------------------------------------------------------------------

AMPLEUR = "ampleur"
EXIGENCE = "exigence"
MEMOIRE = "memoire"
ECHO = "echo"
SERMENT = "serment"
FORGE = "forge"

# Le plafond dur du §4.3 : cinq slots, jamais plus. « Ampleur » se prend donc
# deux fois au maximum, et la troisième n'est plus proposée.
SLOTS_MAX = 5

# Ce que « Exigence » ajoute au plancher, par prise. Cinq minutes : assez pour
# se sentir, trop peu pour casser quelqu'un — et le mode dégradé monte de la
# même quantité, sinon l'écart entre les deux se creuserait jusqu'à faire du
# mode dégradé la seule option des mauvais soirs.
EXIGENCE_MINUTES = 5
EXIGENCE_MAX = 2

# La contrepartie d'Exigence, en Éclats. De la monnaie cosmétique (§12.6) : la
# seule chose que le système puisse donner sans fausser sa propre mesure.
EXIGENCE_ECLATS = 0.5


@dataclass(frozen=True)
class Voie:
    cle: str
    label: str
    promesse: str          # ce que ça ouvre
    cout: str              # ce que ça coûte, dit franchement
    prises_max: int = 1


CATALOGUE: tuple[Voie, ...] = (
    Voie(
        cle=AMPLEUR,
        label="Ampleur",
        promesse="Un slot de projet de plus, jusqu'à cinq.",
        cout="Un projet de plus à tenir. Le rang exige que tous les engagements "
             "d'une semaine soient tenus : c'est une chance de plus de rater la semaine.",
        prises_max=2,
    ),
    Voie(
        cle=EXIGENCE,
        label="Exigence",
        promesse="Les Éclats gagnés augmentent de moitié.",
        cout=f"Le plancher quotidien monte de {EXIGENCE_MINUTES} minutes, et le mode "
             "dégradé avec lui. Définitivement.",
        prises_max=EXIGENCE_MAX,
    ),
    Voie(
        cle=MEMOIRE,
        label="Mémoire",
        promesse="Le fantôme peut être une saison précise, choisie par son nom, "
                 "au lieu de la meilleure, la dernière ou la moyenne.",
        cout="Aucun. Elle ne donne rien d'autre que le droit de choisir contre "
             "quoi tu cours.",
    ),
    Voie(
        cle=ECHO,
        label="Écho",
        promesse="Cinq modificateurs proposés à l'ouverture d'une saison au lieu de trois.",
        cout="Aucun non plus. Un choix plus large n'est pas un meilleur modificateur — "
             "les cinq sont tirés du même catalogue, et un seul reste actif.",
    ),
    Voie(
        cle=FORGE,
        label="Forge",
        promesse="Fabriquer une carte précise en dépensant des Éclats, au lieu "
                 "d'attendre qu'elle tombe.",
        cout="Aucun, et c'est le but : les Éclats ne se dépensaient nulle part. "
             "Ils montaient, et une monnaie qui ne descend jamais n'est pas une "
             "monnaie, c'est un compteur.",
    ),
    Voie(
        cle=SERMENT,
        label="Serment",
        promesse="Le contrat se signe sur l'année entière plutôt que sur une saison, "
                 "et la mise se joue sur les douze.",
        cout="Douze saisons d'engagement pris d'un coup, relu à chaque clôture. "
             "Ce qui se tient mieux se rate aussi plus visiblement.",
    ),
)

PAR_CLE = {v.cle: v for v in CATALOGUE}


def voies_disponibles(prises: list[str], *, slots_actuels: int = 3) -> list[Voie]:
    """Les voies qu'on peut encore prendre, vu ce qui l'a déjà été.

    « Ampleur » disparaît quand les cinq slots du §4.3 sont atteints, même si
    elle n'a été prise qu'une fois : le plafond de la spec ne se contourne pas
    par une mécanique ajoutée par-dessus.
    """
    compte = {cle: prises.count(cle) for cle in PAR_CLE}
    ouvertes = []
    for voie in CATALOGUE:
        if compte.get(voie.cle, 0) >= voie.prises_max:
            continue
        if voie.cle == AMPLEUR and slots_actuels >= SLOTS_MAX:
            continue
        ouvertes.append(voie)
    return ouvertes


@dataclass(frozen=True)
class Effets:
    """Le cumul des voies prises. Additif, comme les reliques du §12.8."""

    slots_bonus: int = 0
    plancher_bonus: int = 0
    eclats_bonus: float = 0.0
    fantome_nomme: bool = False
    modificateurs_proposes: int = 3
    serment_annuel: bool = False
    forge_ouverte: bool = False

    @property
    def any(self) -> bool:
        return bool(
            self.slots_bonus
            or self.plancher_bonus
            or self.eclats_bonus
            or self.fantome_nomme
            or self.serment_annuel
            or self.forge_ouverte
            or self.modificateurs_proposes != 3
        )


def effets(prises: list[str]) -> Effets:
    """Ce que les voies prises changent, une fois cumulées."""
    compte = {cle: list(prises).count(cle) for cle in PAR_CLE}

    return Effets(
        slots_bonus=min(compte.get(AMPLEUR, 0), CATALOGUE[0].prises_max),
        plancher_bonus=min(compte.get(EXIGENCE, 0), EXIGENCE_MAX) * EXIGENCE_MINUTES,
        eclats_bonus=min(compte.get(EXIGENCE, 0), EXIGENCE_MAX) * EXIGENCE_ECLATS,
        fantome_nomme=bool(compte.get(MEMOIRE, 0)),
        modificateurs_proposes=5 if compte.get(ECHO, 0) else 3,
        serment_annuel=bool(compte.get(SERMENT, 0)),
        forge_ouverte=bool(compte.get(FORGE, 0)),
    )


def titre_de_l_annee(annee: int, saisons_gagnees: int) -> str:
    """Le titre décerné à l'ascendance. Le titre raté existe aussi (§12.3).

    Une année n'a pas de « perdu » : elle a eu lieu, quel qu'ait été son
    contenu. Ce qui change est ce qu'on en dit, et aucune de ces formules ne
    porte de jugement — elles décrivent un décompte.
    """
    if saisons_gagnees >= SAISONS_PAR_AN:
        return f"An {annee} — les douze boss sont tombés"
    if saisons_gagnees >= 9:
        return f"An {annee} — {saisons_gagnees} boss sur douze"
    if saisons_gagnees >= 1:
        return f"An {annee} — {saisons_gagnees} boss abattus"
    return f"An {annee} — aucun boss abattu"
