"""La revue du dimanche, côté règles (SPEC §5.3, §13.3).

C'est le seul moment de la semaine où l'app pose des questions, et le §13.3 dit
comment : **elle arrive avec les constats déjà faits**. Jamais « comment s'est
passée ta semaine ? », qui est une page blanche et donc, d'après le §0.9, le
mode de défaillance du produit. Les questions portent sur des faits précis :
« Mardi, créneau à 20h30 sur le bot, aucune session et 2h10 de YouTube. Qu'est-ce
qui s'est passé ? »

Ce module fabrique **les questions déterministes** et **le contrat proposé**. Un
modèle peut faire mieux sur la formulation ; il ne peut pas faire mieux sur le
choix des faits, qui est déjà tranché par les chiffres. Et sans lui, la revue a
lieu quand même — c'est la règle du reste du produit et il n'y a pas de raison
d'y déroger le dimanche.

La sortie tient en trois blocs (§13.3) : ce qui a marché **avec sa cause**, ce
qui n'a pas marché, et **la seule chose** à changer. Une seule, pas trois. Trois
changements simultanés ne se tiennent pas une semaine, et n'en tenir aucun est
la façon la plus sûre d'arrêter de faire des revues.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# Le §13.3 : quatre à cinq. En dessous ce n'est plus une revue, au-dessus c'est
# un questionnaire — et un questionnaire le dimanche soir ne se remplit pas.
MIN_QUESTIONS = 3
MAX_QUESTIONS = 5

JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


@dataclass(frozen=True)
class Question:
    """Une question, et le fait qui l'a provoquée. Le fait est montré avec."""

    fait: str
    question: str


@dataclass(frozen=True)
class LigneDeContrat:
    projet: str
    actuel: int
    propose: int
    raison: str

    @property
    def change(self) -> bool:
        return self.propose != self.actuel


def questions(
    *,
    creneaux_manques: list[tuple[int, str]],
    constats: list[tuple[str, str]],
    projets_avances: list[tuple[str, int]],
) -> list[Question]:
    """Les questions de la revue, de la plus concrète à la plus générale.

    ``creneaux_manques`` : ``(jour de la semaine, projet)`` d'un rendez-vous fixe
    sans session. Ce sont les meilleures questions du lot — un créneau manqué est
    un fait daté, et on s'en souvient.

    ``constats`` : ``(constat, proposition)`` venant du §13.5.

    ``projets_avances`` : ``(projet, minutes)``, pour la seule question qui porte
    sur ce qui a marché. Elle n'est pas là par politesse : le §13.3 demande la
    **cause** de ce qui a marché, et la cause ne se lit pas dans les chiffres.
    """
    posees: list[Question] = []

    for jour, projet in creneaux_manques[:2]:
        posees.append(
            Question(
                fait=f"{JOURS[jour].capitalize()} : créneau prévu sur {projet}, aucune session.",
                question="Qu'est-ce qui s'est passé ce soir-là ?",
            )
        )

    for constat, _ in constats[:2]:
        posees.append(
            Question(fait=constat, question="Tu l'expliques par quoi ?")
        )

    if projets_avances:
        nom, minutes = max(projets_avances, key=lambda item: item[1])
        posees.append(
            Question(
                fait=f"{nom} a avancé de {minutes} minutes cette semaine.",
                question="Qu'est-ce qui a rendu ces soirs-là plus faciles que les autres ?",
            )
        )

    if len(posees) < MIN_QUESTIONS:
        posees.append(
            Question(
                fait="La semaine se termine.",
                question="Qu'est-ce qui t'a le plus gêné, cette semaine ?",
            )
        )

    return posees[:MAX_QUESTIONS]


def contrat(lignes: list[tuple[str, int, list[int]]]) -> list[LigneDeContrat]:
    """Le contrat de la semaine suivante, ajusté au réel observé (§5.3).

    ``lignes`` : ``(projet, engagement actuel, sessions faites les dernières
    semaines)``, la plus récente d'abord.

    La règle tient en une phrase : **on propose ce qui a été tenu**, pas ce qui
    avait été annoncé. Un engagement calé sur l'ambition fabrique trois échecs
    par mois, et le §0.2 dit où ça mène. On ne descend jamais sous une session —
    zéro n'est pas un engagement, c'est un abandon déguisé — et on ne monte que
    d'un cran à la fois, parce que le sur-régime est l'autre façon de tomber.
    """
    sortie: list[LigneDeContrat] = []

    for projet, actuel, faites in lignes:
        if not faites:
            sortie.append(
                LigneDeContrat(projet, actuel, actuel, "aucune semaine observée, on garde")
            )
            continue

        moyenne = sum(faites) / len(faites)
        propose = max(1, min(actuel + 1, round(moyenne)))

        if propose < actuel:
            raison = f"{_arrondi(moyenne)} tenues en moyenne, contre {actuel} prises"
        elif propose > actuel:
            raison = f"{_arrondi(moyenne)} tenues en moyenne : il y a de la marge"
        else:
            raison = "l'engagement colle au réel"

        sortie.append(LigneDeContrat(projet, actuel, propose, raison))

    return sortie


def _arrondi(valeur: float) -> str:
    return f"{valeur:.1f}".rstrip("0").rstrip(".")


def compte_rendu(
    *,
    a_marche: str,
    n_a_pas_marche: str,
    seule_chose: str,
    dialogue: bool,
) -> dict:
    """Les trois blocs du §13.3, plus la mention d'un dialogue esquivé.

    « Si le dialogue est esquivé, la revue se génère quand même sans les
    réponses, en le notant. » Le noter n'est pas un reproche : c'est ce qui
    permet de relire la revue dans un mois en sachant qu'elle a été écrite sans
    l'intéressé.
    """
    return {
        "a_marche": a_marche,
        "n_a_pas_marche": n_a_pas_marche,
        "seule_chose": seule_chose,
        "dialogue": dialogue,
        "note": "" if dialogue else "Revue écrite sans réponses : les causes sont des hypothèses.",
    }


def semaine_suivante(semaine: date) -> date:
    return semaine + timedelta(days=7)
