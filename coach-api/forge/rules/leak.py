"""Le rapport de fuite de temps, côté règles (SPEC §13.2).

Le point 5 du diagnostic — trois heures de scroll par soir — est le seul qui se
mesure vraiment. Encore faut-il en faire quelque chose d'utilisable, et le §13.2
est explicite sur ce que ça veut dire :

> L'objectif est de trouver **l'heure charnière**, pas de culpabiliser sur un
> total.

Un total est une note ; une heure est une décision. Savoir qu'on perd deux
heures par soir n'apprend rien qu'on ne sache déjà. Savoir que ça commence
presque toujours entre 19h30 et 20h dit **où poser le créneau**, et c'est
actionnable dès le lendemain.

D'où la forme : un histogramme par tranche de trente minutes sur quatre semaines
glissantes, la charnière calculée dessus, et le coût converti en unités du
système plutôt qu'en morale — « 1h40 = 4 sessions = 12 % de la vie du boss ». Le
§17 interdit le score de productivité et le jugement ; une conversion en
sessions n'est ni l'un ni l'autre, c'est un taux de change.

Module pur. Les fenêtres entrent en minutes depuis minuit, les tranches sortent.
"""

from __future__ import annotations

from dataclasses import dataclass

TRANCHE = 30
TRANCHES_PAR_JOUR = 24 * 60 // TRANCHE

# En dessous, une tranche est du bruit de mesure : deux minutes de scroll à 3h
# du matin sur quatre semaines ne décrivent aucune habitude.
MINUTES_VISIBLES = 10

# La charnière ne se déclare pas sur un frémissement. Il faut que la tranche
# pèse au moins ça sur quatre semaines pour qu'on la nomme — sinon on désignerait
# un soir particulier comme s'il était une habitude.
CHARNIERE_MINIMUM = 45


@dataclass(frozen=True)
class Tranche:
    debut: int                       # minutes depuis minuit
    minutes: int

    @property
    def libelle(self) -> str:
        return f"{self.debut // 60:02d}h{self.debut % 60:02d}"


def repartir(fenetres: list[tuple[int, int, int]]) -> list[Tranche]:
    """Étale des fenêtres mesurées sur les tranches de trente minutes.

    ``fenetres`` : ``(début, fin, minutes)`` en minutes depuis minuit. Les
    sondes ne rendent pas un instant par minute observée : elles rendent « 14
    minutes de scroll entre 19h05 et 19h35 ». On étale donc **au prorata** de ce
    que la fenêtre couvre de chaque tranche.

    C'est une approximation, et elle est la bonne : la seule alternative serait
    de faire remonter aux sondes un horodatage par minute, ce que le §11.10
    interdit d'esprit — moins une sonde en dit, mieux c'est.
    """
    seaux = [0.0] * TRANCHES_PAR_JOUR

    for debut, fin, minutes in fenetres:
        duree = max(1, fin - debut)
        for index in range(TRANCHES_PAR_JOUR):
            borne_basse = index * TRANCHE
            borne_haute = borne_basse + TRANCHE
            recouvrement = min(fin, borne_haute) - max(debut, borne_basse)
            if recouvrement > 0:
                seaux[index] += minutes * (recouvrement / duree)

    return [
        Tranche(index * TRANCHE, round(valeur))
        for index, valeur in enumerate(seaux)
        if round(valeur) >= MINUTES_VISIBLES
    ]


def charniere(tranches: list[Tranche]) -> Tranche | None:
    """La tranche où le décrochage commence réellement.

    Pas la plus lourde — celle-là est au milieu du décrochage, et il est déjà
    trop tard pour agir dessus. Celle où la **montée** est la plus forte : c'est
    le moment où l'on bascule, et le seul sur lequel un créneau placé juste
    avant peut mordre.
    """
    if not tranches:
        return None

    par_index = {t.debut // TRANCHE: t for t in tranches}
    meilleure, saut_max = None, 0

    for index, tranche in sorted(par_index.items()):
        if tranche.minutes < CHARNIERE_MINIMUM:
            continue
        precedente = par_index.get(index - 1)
        saut = tranche.minutes - (precedente.minutes if precedente else 0)
        if saut > saut_max:
            meilleure, saut_max = tranche, saut

    return meilleure


@dataclass(frozen=True)
class Cout:
    minutes: int
    sessions: int
    part_du_boss: float

    @property
    def phrase(self) -> str:
        heures, reste = divmod(self.minutes, 60)
        duree = f"{heures}h{reste:02d}" if heures else f"{reste} min"
        morceaux = [duree, f"{self.sessions} session(s) de 25 min"]
        if self.part_du_boss:
            morceaux.append(f"{round(self.part_du_boss * 100)} % de la vie du boss")
        return " = ".join(morceaux)


def cout(minutes: int, *, degats_par_session: int = 0, pv_du_boss: int = 0) -> Cout:
    """Le coût en unités du système, jamais en morale (§13.2).

    « 1h40 de Shorts = 4 sessions de 25 min = 12 % de la vie du boss. » La phrase
    ne dit pas que c'est mal ; elle dit ce que ça vaut dans la monnaie du jeu, et
    c'est à la personne d'en faire ce qu'elle veut. Le §17 interdit le score de
    productivité — un taux de change n'en est pas un.
    """
    sessions = minutes // 25
    part = 0.0
    if sessions and degats_par_session and pv_du_boss:
        part = min(1.0, sessions * degats_par_session / pv_du_boss)
    return Cout(minutes=minutes, sessions=sessions, part_du_boss=round(part, 4))


@dataclass(frozen=True)
class Declencheur:
    quoi: str
    occurrences: int
    total: int

    @property
    def part(self) -> float:
        return round(self.occurrences / self.total, 2) if self.total else 0.0


def declencheurs(precedents: list[str]) -> list[Declencheur]:
    """Ce qui précède immédiatement le décrochage, présenté comme une corrélation.

    Le §13.2 insiste sur la présentation : « corrélation observée, présentée
    comme telle ». Ce module compte des occurrences et n'en tire aucune cause —
    quatre soirs sur cinq après une session ratée ne veut pas dire que la
    session ratée provoque le scroll, et l'écrire ainsi ferait dire aux chiffres
    ce qu'ils ne disent pas.
    """
    total = len(precedents)
    if not total:
        return []

    comptes: dict[str, int] = {}
    for quoi in precedents:
        comptes[quoi] = comptes.get(quoi, 0) + 1

    return sorted(
        (Declencheur(quoi, n, total) for quoi, n in comptes.items()),
        key=lambda d: d.occurrences,
        reverse=True,
    )
