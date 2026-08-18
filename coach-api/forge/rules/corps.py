"""La piste Corps : objectif hebdomadaire, streak de semaines (SPEC §11.4).

Le §11.4 lui donne trois choses que l'Atelier n'a pas :

> Piste **Corps** : objectif hebdomadaire (2 séances par défaut), streak
> hebdomadaire propre, mode dégradé = 15 min à la maison.

Rien de tout cela n'existait. Seuls les deux slots étaient codés, et le reste
vivait dans la spec sans une ligne en face. Une séance de sport s'enregistrait,
donnait de l'XP et des dégâts au boss, et c'était tout : aucun compteur ne la
lisait, aucun écran ne la montrait, et la proposition du soir ne l'a jamais
proposée une seule fois.

## Pourquoi la semaine et non le jour

L'Atelier se compte en jours parce qu'un projet avance par petites touches et
qu'une soirée sautée se rattrape le lendemain. Le corps ne fonctionne pas ainsi :
deux séances par semaine avec du repos entre elles valent mieux que sept séances
molles, et un streak quotidien pousserait exactement au contraire.

**Il n'y a donc pas de bouclier ici.** Le battement est déjà dans l'objectif :
viser deux séances quand la semaine en compte sept laisse cinq jours de marge.
C'est le mécanisme du §11.9 pour l'Entretien — le rythme et le seuil sont deux
réglages distincts, et l'écart entre eux absorbe les imprévus mieux qu'un
bouclier.

## Une séance de sport ne valide jamais l'Atelier

La règle dure du §11.4, et elle vaut dans les deux sens. Ce module ne connaît
que des séances de la piste Corps, et ``streak`` ne connaît que l'Atelier. Ils
ne partagent aucune fonction, ce qui est la façon la plus sûre de garantir
qu'ils ne se contamineront jamais : une garde par test se contourne par
distraction, une séparation de modules non.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

# Deux séances par semaine, le défaut du §11.4.
OBJECTIF_PAR_DEFAUT = 2

# Le plancher d'une séance qui compte. Plus haut que celui de l'Atelier : dix
# minutes de sport ne sont pas une séance, alors que dix minutes de code sont un
# vrai début — c'est la différence entre une activité qui demande de se changer
# et une qui demande d'ouvrir un éditeur.
PLANCHER = 30

# « 15 min à la maison » (§11.4) : le mode dégradé du corps, celui des soirs où
# la salle est fermée ou le corps refuse.
DEGRADE = 15

# Au-delà, ce n'est plus un objectif mais un programme. Cinq séances demandent
# une récupération que ce système ne sait pas mesurer, et le §17 lui interdit de
# prétendre le contraire.
OBJECTIF_MAX = 5


@dataclass(frozen=True)
class Semaine:
    """Une semaine de la piste, close ou en cours."""

    lundi: date
    seances: int
    objectif: int

    @property
    def tenue(self) -> bool:
        return self.seances >= self.objectif

    @property
    def restantes(self) -> int:
        return max(0, self.objectif - self.seances)

    @property
    def ratio(self) -> float:
        return min(1.0, self.seances / max(1, self.objectif))


@dataclass
class CorpsState:
    """L'état de la piste. Le streak se compte en **semaines**, jamais en jours."""

    current: int = 0
    best: int = 0
    semaines_tenues: int = 0
    semaine_en_cours: Semaine | None = None
    historique: list[Semaine] = field(default_factory=list)

    @property
    def objectif(self) -> int:
        return self.semaine_en_cours.objectif if self.semaine_en_cours else OBJECTIF_PAR_DEFAUT

    @property
    def faites(self) -> int:
        return self.semaine_en_cours.seances if self.semaine_en_cours else 0

    @property
    def restantes(self) -> int:
        return self.semaine_en_cours.restantes if self.semaine_en_cours else self.objectif

    @property
    def tenue(self) -> bool:
        return bool(self.semaine_en_cours and self.semaine_en_cours.tenue)


def evaluate(semaines: list[Semaine], *, en_cours: Semaine | None = None) -> CorpsState:
    """Rejoue l'historique et rend l'état. ``semaines`` va du plus ancien au plus récent.

    La semaine en cours est passée à part et **n'entre pas dans le streak** :
    tant qu'elle n'est pas finie, elle n'est ni tenue ni ratée. Même précaution
    que pour la journée en cours de l'Atelier, et elle évite le mensonge le plus
    visible qui soit — un streak qui tombe le lundi matin.
    """
    etat = CorpsState(semaine_en_cours=en_cours, historique=list(semaines))

    for semaine in semaines:
        if semaine.tenue:
            etat.current += 1
            etat.semaines_tenues += 1
            etat.best = max(etat.best, etat.current)
        else:
            etat.current = 0

    return etat


def message_for(etat: CorpsState) -> str:
    """La ligne affichée. Un constat, jamais un reproche (§17).

    Aucune formule ne dit « il te reste » ni « plus que ». Le corps est le
    domaine où la culpabilisation marche le moins bien et se retourne le plus
    vite : une phrase qui presse produit une semaine sautée, puis l'abandon de
    la piste entière.
    """
    if etat.semaine_en_cours is None:
        return "Aucune activité sur la piste Corps."

    faites, objectif = etat.faites, etat.objectif
    if etat.tenue:
        extra = faites - objectif
        if extra > 0:
            return f"Semaine tenue — {faites} séances, {extra} au-delà de l'objectif."
        return f"Semaine tenue — {faites} séances sur {objectif}."

    if faites == 0:
        return f"Objectif de la semaine : {objectif} séances."
    return f"{faites} séance{'s' if faites > 1 else ''} sur {objectif} cette semaine."


def plancher_du_jour(*, degrade: bool = False) -> int:
    return DEGRADE if degrade else PLANCHER


def semaine_de(jour: date) -> date:
    """Le lundi de la semaine d'un jour."""
    return jour - timedelta(days=jour.weekday())


def priorite(etat: CorpsState, *, jours_restants: int) -> float:
    """À quel point la piste Corps mérite la décision de ce soir, de 0 à 1.

    Sert à la proposition du §11.1 pour arbitrer entre l'Atelier et le Corps.
    Elle monte quand la semaine avance sans que l'objectif suive : à deux
    séances manquantes et deux jours restants, elle vaut 1 — c'est ce soir ou
    la semaine est ratée.

    Rend 0 dès que la semaine est tenue. Le §17 interdit de pousser au-delà de
    l'objectif : c'est un objectif, pas un plancher à dépasser.
    """
    if etat.semaine_en_cours is None or etat.tenue:
        return 0.0
    return round(min(1.0, etat.restantes / max(1, jours_restants)), 3)
